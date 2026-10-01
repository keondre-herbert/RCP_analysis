from __future__ import annotations

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from veles.ui.header import make_logo


class HomePage(QWidget):
    """Hero + entry points. Running now, recent runs and data locations arrive in Milestone 6."""

    new_run_requested = pyqtSignal()
    runs_requested = pyqtSignal()
    pipeline_requested = pyqtSignal()

    def __init__(self, version: str = "", parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("Page")

        logo = make_logo()
        logo.setFixedSize(130, 130)

        title = QLabel("VELES")
        title.setProperty("role", "hero")
        version_label = QLabel(f"[{version}]" if version else "")
        version_label.setProperty("role", "version")

        lead = QLabel(
            "VELES - Versatile Electrophysiology and Limb-motion Evaluation Suite\n"
            "Veles: a slavic deity of magic, knowledge, divination, and poetry, "
            "providing wisdom and guidance to his shamans, governing the world outside "
            "the fences of human dwellings.\n"
            "Like the god Veles, may this app provide us a view into the unknown!\n" \
            "Runs RCP analysis Pipeline"
        )
        lead.setProperty("role", "lead")
        lead.setWordWrap(True)
        lead.setMaximumWidth(960)

        new_run = QPushButton("+  New run")
        new_run.setProperty("role", "primary")
        all_runs = QPushButton("All runs")
        how = QPushButton("How the pipeline works")
        new_run.clicked.connect(self.new_run_requested)
        all_runs.clicked.connect(self.runs_requested)
        how.clicked.connect(self.pipeline_requested)

        title_row = QHBoxLayout()
        title_row.setSpacing(18)
        title_row.addWidget(title)
        title_row.addWidget(version_label, alignment=Qt.AlignBottom)
        title_row.addStretch(1)

        buttons = QHBoxLayout()
        buttons.setSpacing(16)
        for button in (new_run, all_runs, how):
            buttons.addWidget(button)
        buttons.addStretch(1)

        text = QVBoxLayout()
        text.setSpacing(18)
        text.addLayout(title_row)
        text.addWidget(lead)
        text.addSpacing(12)
        text.addLayout(buttons)

        hero = QHBoxLayout()
        hero.setSpacing(38)
        hero.addWidget(logo, alignment=Qt.AlignTop)
        hero.addLayout(text, stretch=1)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 44, 40, 40)
        layout.addLayout(hero)
        layout.addStretch(1)
