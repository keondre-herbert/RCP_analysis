from __future__ import annotations

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from veles.ui.header import make_logo
from veles.ui.theme import restyle

STEPS = ["Animal", "Sessions", "Conditions", "Scripts", "Review"]
STEP_TITLES = [
    "Which animal?",
    "Which sessions?",
    "Which conditions?",
    "What do you want to produce?",
    "Review and start",
]


class StepButton(QPushButton):
    """One stepper entry: a 4px bar on top, then '01  Animal'. States: 'current', 'done', 'todo'."""

    def __init__(self, index: int, label: str, parent: QWidget | None = None):
        super().__init__(parent)
        self.setProperty("role", "step")
        self.setFixedHeight(64)
        self.number = QLabel(f"{index + 1:02d}")
        self.number.setProperty("role", "step-number")
        self.label = QLabel(label)
        self.label.setProperty("role", "step-label")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 14, 0, 10)
        layout.setSpacing(14)
        for part in (self.number, self.label):
            part.setAttribute(Qt.WA_TransparentForMouseEvents)  # clicks go to the button
            layout.addWidget(part)
        layout.addStretch(1)
        self.set_state("todo")

    def set_state(self, state: str) -> None:
        for widget in (self, self.number, self.label):
            restyle(widget, state=state)
        self.setCursor(Qt.PointingHandCursor if state == "done" else Qt.ArrowCursor)


class PlaceholderStep(QWidget):
    def __init__(self, title: str, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("Page")
        heading = QLabel(title)
        heading.setProperty("role", "title")
        note = QLabel("This step is built in Milestone 4.")
        note.setProperty("role", "muted")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 44, 40, 40)
        layout.setSpacing(10)
        layout.addWidget(heading)
        layout.addWidget(note)
        layout.addStretch(1)


class WizardView(QWidget):
    """New run: its own header, a 5-step stepper, the step pages and a Back / Next footer."""

    cancelled = pyqtSignal()
    start_requested = pyqtSignal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.current = 0   # index of the step on screen
        self.furthest = 0  # highest step reached so far; steps up to here count as visited

        self.stack = QStackedWidget()
        for title in STEP_TITLES:
            self.stack.addWidget(PlaceholderStep(title))

        self.step_buttons = [StepButton(i, label) for i, label in enumerate(STEPS)]
        for i, button in enumerate(self.step_buttons):
            button.clicked.connect(lambda _checked=False, i=i: self.go_to_step(i))

        self.back_button = QPushButton("Back to home")
        self.next_button = QPushButton(f"Next: {STEPS[1]}")
        self.next_button.setProperty("role", "primary")
        self.summary = QLabel("")
        self.summary.setProperty("role", "muted")
        self.back_button.clicked.connect(lambda: self.go_to_step(self.current - 1))
        self.next_button.clicked.connect(lambda: self.go_to_step(self.current + 1))

        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.cancelled)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._top_bar(cancel))
        layout.addWidget(self._stepper())
        layout.addWidget(self.stack, stretch=1)
        layout.addWidget(self._footer())

    def _top_bar(self, cancel: QPushButton) -> QWidget:
        bar = QWidget()
        bar.setObjectName("WizardTop")
        bar.setAttribute(Qt.WA_StyledBackground)
        name = QLabel("VELES")
        name.setObjectName("AppName")
        divider = QFrame()
        divider.setObjectName("VDivider")
        divider.setFixedSize(1, 28)
        title = QLabel("New run")
        title.setObjectName("WizardTitle")
        row = QHBoxLayout(bar)
        row.setContentsMargins(34, 14, 34, 14)
        row.setSpacing(18)
        for widget in (make_logo(), name, divider, title):
            row.addWidget(widget)
        row.addStretch(1)
        row.addWidget(cancel)
        return bar

    def _stepper(self) -> QWidget:
        bar = QWidget()
        bar.setObjectName("Stepper")
        bar.setAttribute(Qt.WA_StyledBackground)
        row = QHBoxLayout(bar)
        row.setContentsMargins(34, 14, 34, 4)
        row.setSpacing(14)
        for button in self.step_buttons:
            row.addWidget(button, stretch=1)
        return bar

    def _footer(self) -> QWidget:
        bar = QWidget()
        bar.setObjectName("Footer")
        bar.setAttribute(Qt.WA_StyledBackground)
        row = QHBoxLayout(bar)
        row.setContentsMargins(34, 16, 34, 16)
        row.setSpacing(18)
        row.addWidget(self.back_button)
        row.addStretch(1)
        row.addWidget(self.summary)
        row.addWidget(self.next_button)
        return bar

    def reset(self) -> None:
        """Start a fresh run at step 1 with nothing visited."""
        self.current = 0
        self.furthest = 0
        self.go_to_step(0)

    def go_to_step(self, index: int) -> None:
        """Show step `index`. Called by Next (current + 1), Back (current - 1) and stepper clicks.

        index may be -1 (Back on the first step) or len(STEPS) (Next on the last step).
        """
        # TODO(human)
        self.current = index
        self.stack.setCurrentIndex(index)
