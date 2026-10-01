from __future__ import annotations

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import QFrame, QLabel, QVBoxLayout, QWidget

from veles.wizard_state import WizardState


class StepPage(QWidget):
    """One wizard step. The wizard calls enter() when it's shown and asks is_complete() to enable Next.

    Emit `changed` whenever the user changes something, so the wizard refreshes Next, the summary and the stepper.
    """

    changed = pyqtSignal()

    def __init__(self, state: WizardState, parent: QWidget | None = None):
        super().__init__(parent)
        self.state = state
        self.setObjectName("Page")

    def reset(self) -> None:
        """A new run starts; forget anything the page remembers beyond the shared state."""

    def enter(self) -> None:
        pass

    def is_complete(self) -> bool:
        return True

    def summary(self) -> str:
        return ""


def panel() -> QFrame:
    frame = QFrame()
    frame.setProperty("role", "panel")
    return frame


def label(text: str, role: str = "", wrap: bool = False) -> QLabel:
    widget = QLabel(text)
    if role:
        widget.setProperty("role", role)
    widget.setWordWrap(wrap)
    widget.setTextInteractionFlags(Qt.NoTextInteraction)
    return widget


def column(*widgets: QWidget, spacing: int = 8, margins: tuple[int, int, int, int] = (0, 0, 0, 0)) -> QVBoxLayout:
    layout = QVBoxLayout()
    layout.setContentsMargins(*margins)
    layout.setSpacing(spacing)
    for w in widgets:
        layout.addWidget(w)
    return layout
