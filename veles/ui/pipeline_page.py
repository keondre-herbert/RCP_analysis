from __future__ import annotations

from PyQt5.QtWidgets import QLabel, QVBoxLayout, QWidget


class PipelinePage(QWidget):
    """How the pipeline works, rendered from the repo's README.md in Milestone 6."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("Page")
        title = QLabel("How the pipeline works")
        title.setProperty("role", "title")
        note = QLabel("The README schematic and text will be shown here (Milestone 6).")
        note.setProperty("role", "muted")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 44, 40, 40)
        layout.setSpacing(10)
        layout.addWidget(title)
        layout.addWidget(note)
        layout.addStretch(1)
