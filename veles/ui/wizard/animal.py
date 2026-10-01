from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import QFrame, QGridLayout, QHBoxLayout, QLabel, QRadioButton, QVBoxLayout, QWidget

from veles.data import STATUS_CSV_NAME, Session, animal_root, load_sessions
from veles.ui.background import run_in_background
from veles.ui.theme import restyle
from veles.ui.widgets.status_pill import StatusPill
from veles.ui.wizard.base import StepPage, label, panel
from veles.wizard_state import WizardState

ANIMALS = ("Nike", "Ada", "Bert")


@dataclass
class Probe:
    """What a quick look at an animal's folder found (before any scan)."""
    root: Path | None = None
    error: str = ""          # data root can't be resolved on this machine
    folder: bool = False
    status_csv: bool = False


@dataclass
class CardInfo:
    path: str
    pill: str
    pill_kind: str
    status_csv: str
    enabled: bool
    tooltip: str = ""


def probe(animal: str) -> Probe:
    try:
        root = animal_root(animal)
    except Exception as error:
        return Probe(error=str(error))
    return Probe(root=root, folder=root.is_dir(), status_csv=(root / STATUS_CSV_NAME).is_file())


def card_info(p: Probe | None, scan: dict[str, Session] | Exception | None, scanning: bool) -> CardInfo:
    if p is None:
        return CardInfo("", "Checking…", "neutral", "—", False)
    if p.error:
        return CardInfo(p.error, "No data root", "fail", "—", False)
    path = str(p.root)
    if not p.folder:
        return CardInfo(path, "Folder not found", "fail", "—", False)
    if not p.status_csv:
        return CardInfo(path, "No status CSV", "neutral", "Not found", False)
    if scanning:
        return CardInfo(path, "Scanning…", "neutral", "Found", True)
    if isinstance(scan, Exception):
        return CardInfo(path, "Scan failed", "fail", "Found", True, tooltip=str(scan))
    if scan is not None:
        return CardInfo(path, f"{len(scan)} sessions", "neutral", "Found", True)
    return CardInfo(path, "Not scanned", "neutral", "Found", True)


class AnimalCard(QFrame):
    clicked = pyqtSignal(str)

    def __init__(self, animal: str, parent: QWidget | None = None):
        super().__init__(parent)
        self.animal = animal
        self.setProperty("role", "card")
        self.setCursor(Qt.PointingHandCursor)

        self.radio = QRadioButton()
        self.radio.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.radio.setFocusPolicy(Qt.NoFocus)
        name = label(animal, "card-title")
        self.pill = StatusPill()
        self.path = label("", "path", wrap=True)
        self.path.setMinimumHeight(40)
        self.status_csv = label("—")
        line = QFrame()
        line.setObjectName("HLine")
        line.setFixedHeight(1)

        top = QHBoxLayout()
        top.setSpacing(12)
        top.addWidget(self.radio)
        top.addWidget(name)
        top.addStretch(1)
        top.addWidget(self.pill)

        facts = QGridLayout()
        facts.setHorizontalSpacing(32)
        facts.setVerticalSpacing(2)
        facts.addWidget(label("Last run", "field"), 0, 0)
        facts.addWidget(label("Status CSV", "field"), 0, 1)
        facts.addWidget(label("—"), 1, 0)  # filled from run records in Milestone 5
        facts.addWidget(self.status_csv, 1, 1)
        facts.setColumnStretch(2, 1)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(14)
        layout.addLayout(top)
        layout.addWidget(self.path)
        layout.addWidget(line)
        layout.addLayout(facts)

    def show_info(self, info: CardInfo, selected: bool) -> None:
        self.path.setText(info.path)
        self.pill.set(info.pill, info.pill_kind)
        self.status_csv.setText(info.status_csv)
        self.setToolTip(info.tooltip)
        self.radio.setChecked(selected)
        self.radio.setEnabled(info.enabled)
        self.setCursor(Qt.PointingHandCursor if info.enabled else Qt.ArrowCursor)
        restyle(self, selected="true" if selected else "false", enabled="true" if info.enabled else "false")
        self._enabled = info.enabled

    def mousePressEvent(self, event) -> None:
        if getattr(self, "_enabled", False) and event.button() == Qt.LeftButton:
            self.clicked.emit(self.animal)


class AnimalPage(StepPage):
    def __init__(self, state: WizardState, parent: QWidget | None = None):
        super().__init__(state, parent)
        self.probes: dict[str, Probe] = {}
        self.scans: dict[str, dict[str, Session] | Exception] = {}
        self.scanning: set[str] = set()
        self.chosen = ""

        self.cards = {a: AnimalCard(a) for a in ANIMALS}
        cards = QHBoxLayout()
        cards.setSpacing(28)
        for card in self.cards.values():
            card.clicked.connect(self.choose)
            cards.addWidget(card, stretch=1)

        info = panel()
        info_row = QHBoxLayout(info)
        info_row.setContentsMargins(24, 16, 24, 16)
        info_row.addWidget(label(
            "ⓘ  Only sessions with a Metadata/<session>_metadata.csv are listed; without it VELES can't read their "
            "conditions. Data roots come from config/machines.yaml for this computer.", "muted", wrap=True))

        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 40, 40, 32)
        layout.setSpacing(12)
        layout.addWidget(label("Which animal?", "title"))
        layout.addWidget(label(f"Each animal has its own data folder and its own {STATUS_CSV_NAME}.", "muted"))
        layout.addSpacing(22)
        layout.addLayout(cards)
        layout.addSpacing(18)
        layout.addWidget(info)
        layout.addStretch(1)

    def reset(self) -> None:
        self.chosen = ""  # scans stay cached; a new run just starts with no animal picked

    def enter(self) -> None:
        if not self.probes:
            run_in_background(lambda: {a: probe(a) for a in ANIMALS}, self._probed, self._probe_failed)
        self._show()

    def _probed(self, probes: dict[str, Probe]) -> None:
        self.probes = probes
        self._show()

    def _probe_failed(self, error: Exception) -> None:
        self.probes = {a: Probe(error=str(error)) for a in ANIMALS}
        self._show()

    def choose(self, animal: str) -> None:
        if animal == self.chosen and animal == self.state.animal:
            return  # same animal again: keep everything chosen after it
        self.chosen = animal
        scan = self.scans.get(animal)
        if isinstance(scan, dict):
            self.state.use_animal(animal, self.probes[animal].root, scan)
        elif animal not in self.scanning:
            self.scanning.add(animal)
            root = self.probes[animal].root
            run_in_background(lambda: load_sessions(root),
                              lambda result: self._scanned(animal, result),
                              lambda error: self._scanned(animal, error))
        self._show()
        self.changed.emit()

    def _scanned(self, animal: str, result: dict[str, Session] | Exception) -> None:
        self.scanning.discard(animal)
        self.scans[animal] = result
        if animal == self.chosen and isinstance(result, dict):
            self.state.use_animal(animal, self.probes[animal].root, result)
        self._show()
        self.changed.emit()

    def _show(self) -> None:
        for animal, card in self.cards.items():
            info = card_info(self.probes.get(animal), self.scans.get(animal), animal in self.scanning)
            card.show_info(info, selected=animal == self.chosen)

    def is_complete(self) -> bool:
        return bool(self.state.animal) and self.state.animal == self.chosen and bool(self.state.sessions)

    def summary(self) -> str:
        if self.chosen in self.scanning:
            return f"Scanning {self.chosen}…"
        return f"{self.state.animal} · {len(self.state.sessions)} sessions" if self.is_complete() else ""
