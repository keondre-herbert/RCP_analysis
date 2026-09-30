from __future__ import annotations

from PyQt5.QtWidgets import QLabel, QVBoxLayout, QWidget


class RunsPage(QWidget):
    """Run history and live progress. Filled in Milestone 5."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("Page")
        title = QLabel("Runs")
        title.setProperty("role", "title")
        note = QLabel("Run history and live progress arrive with the runner (Milestone 5).")
        note.setProperty("role", "muted")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 44, 40, 40)
        layout.setSpacing(10)
        layout.addWidget(title)
        layout.addWidget(note)
        layout.addStretch(1)
