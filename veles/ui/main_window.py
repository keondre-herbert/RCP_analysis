from __future__ import annotations

from PyQt5.QtWidgets import QMainWindow, QStackedWidget, QVBoxLayout, QWidget

from veles.ui.header import Header
from veles.ui.home import HomePage
from veles.ui.pipeline_page import PipelinePage
from veles.ui.runs import RunsPage
from veles.ui.wizard.wizard import WizardView

TABS = ["Home", "Runs", "Pipeline"]
HOME, RUNS, PIPELINE = range(3)


class MainWindow(QMainWindow):
    """Swaps between the tab view (Home / Runs / Pipeline) and the New run wizard, which has its own header."""

    def __init__(self, repo_path: str, version: str = ""):
        super().__init__()
        self.setWindowTitle("VELES")
        self.setMinimumSize(1100, 720)

        self.home = HomePage(version)
        self.runs = RunsPage()
        self.pipeline = PipelinePage()
        self.pages = QStackedWidget()
        for page in (self.home, self.runs, self.pipeline):
            self.pages.addWidget(page)

        self.header = Header(TABS, repo_path)
        self.header.tab_changed.connect(self.pages.setCurrentIndex)

        tab_view = QWidget()
        column = QVBoxLayout(tab_view)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(0)
        column.addWidget(self.header)
        column.addWidget(self.pages, stretch=1)

        self.wizard = WizardView()
        self.root = QStackedWidget()
        self.root.addWidget(tab_view)
        self.root.addWidget(self.wizard)
        self.setCentralWidget(self.root)

        self.home.new_run_requested.connect(self.start_wizard)
        self.home.runs_requested.connect(lambda: self.header.set_tab(RUNS))
        self.home.pipeline_requested.connect(lambda: self.header.set_tab(PIPELINE))
        self.wizard.cancelled.connect(self.close_wizard)
        self.wizard.start_requested.connect(self.close_wizard)  # Milestone 5: start the run, then show Home

    def start_wizard(self) -> None:
        self.wizard.reset()
        self.root.setCurrentWidget(self.wizard)

    def close_wizard(self) -> None:
        self.root.setCurrentIndex(0)
        self.header.set_tab(HOME)
