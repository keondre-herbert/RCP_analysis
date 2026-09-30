from __future__ import annotations

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import QButtonGroup, QHBoxLayout, QLabel, QPushButton, QWidget

LOGO_SIZE = 34


def make_logo() -> QLabel:
    """Empty slot for the app icon (veles/assets/), styled as a placeholder until the icon exists."""
    logo = QLabel()
    logo.setObjectName("Logo")
    logo.setFixedSize(LOGO_SIZE, LOGO_SIZE)
    return logo


class Header(QWidget):
    """Top bar on Home/Runs/Pipeline: logo, VELES, underlined tabs, repo path on the right."""

    tab_changed = pyqtSignal(int)

    def __init__(self, tabs: list[str], repo_path: str, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("TopBar")
        self.setAttribute(Qt.WA_StyledBackground)  # plain QWidget subclasses ignore qss backgrounds otherwise

        name = QLabel("VELES")
        name.setObjectName("AppName")

        self.group = QButtonGroup(self)
        self.group.setExclusive(True)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(34, 0, 34, 0)
        layout.setSpacing(12)
        layout.addWidget(make_logo())
        layout.addWidget(name)
        layout.addSpacing(40)
        for index, text in enumerate(tabs):
            button = QPushButton(text)
            button.setProperty("role", "tab")
            button.setCheckable(True)
            self.group.addButton(button, index)
            layout.addWidget(button)
            layout.addSpacing(16)
        layout.addStretch(1)

        repo = QLabel(repo_path)
        repo.setObjectName("RepoPath")
        layout.addWidget(repo)

        self.group.button(0).setChecked(True)
        self.group.idClicked.connect(self.tab_changed)

    def set_tab(self, index: int) -> None:
        """Select a tab from code (e.g. Home's "All runs" button); emits tab_changed like a click would."""
        self.group.button(index).setChecked(True)
        self.tab_changed.emit(index)
