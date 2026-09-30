from __future__ import annotations

import sys
import traceback
from pathlib import Path

from PyQt5.QtCore import QSettings, Qt
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import QApplication, QFileDialog, QMessageBox

from veles import paths
from veles.ui.main_window import MainWindow
from veles.ui.theme import UI_FONT, load_stylesheet


def show_error(exc_type, exc, tb) -> None:
    """Show uncaught errors in a dialog: a windowed .exe has no console, and PyQt would otherwise abort."""
    text = "".join(traceback.format_exception(exc_type, exc, tb))
    if sys.__stderr__ is not None:
        print(text, file=sys.__stderr__)
    box = QMessageBox(QMessageBox.Critical, "VELES error", f"{exc_type.__name__}: {exc}")
    box.setDetailedText(text)
    box.exec_()


def ask_for_repo(error: paths.LocationNotFound) -> Path | None:
    QMessageBox.information(
        None, "Locate the RCP_analysis repo",
        f"{error}\n\nChoose the RCP_analysis folder (the one containing config/params.yaml).",
    )
    while chosen := QFileDialog.getExistingDirectory(None, "RCP_analysis repo folder"):
        if paths.is_repo(Path(chosen)):
            return Path(chosen)
        QMessageBox.warning(None, "Not the repo", f"{chosen} has no config/params.yaml and {paths.HIERARCHY_FILE}.")
    return None


def ask_for_python(error: paths.LocationNotFound) -> Path | None:
    QMessageBox.information(
        None, "Locate the pipeline python",
        f"{error}\n\nChoose python.exe inside the '{paths.CONDA_ENV}' conda env (…/envs/{paths.CONDA_ENV}/python.exe).",
    )
    while chosen := QFileDialog.getOpenFileName(None, "pipeline python.exe", "", "Python (python*.exe)")[0]:
        if paths.is_python(Path(chosen)):
            return Path(chosen)
    return None


def resolve_locations(settings: QSettings) -> bool:
    """Pin the repo and the pipeline python, asking once if they can't be guessed. False if the user gives up."""
    chosen: dict[str, Path | None] = {"repo": None, "python": None}
    if paths.is_frozen():  # in development the checkout itself is always used
        repo, python = Path(settings.value("repo", "", str)), Path(settings.value("python", "", str))
        chosen["repo"] = repo if paths.is_repo(repo) else None
        chosen["python"] = python if paths.is_python(python) else None
    paths.use_locations(**chosen)

    for key, find, ask in (("repo", paths.repo_root, ask_for_repo), ("python", paths.pipeline_python, ask_for_python)):
        try:
            find()
        except paths.LocationNotFound as error:
            picked = ask(error)
            if picked is None:
                return False
            chosen[key] = picked
            settings.setValue(key, str(picked))
            paths.use_locations(**chosen)
    return True


def main() -> int:
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    app = QApplication(sys.argv)
    app.setOrganizationName("RCP")
    app.setApplicationName("VELES")
    app.setFont(QFont(UI_FONT, 10))
    sys.excepthook = show_error

    if not resolve_locations(QSettings()):
        return 1

    app.setStyleSheet(load_stylesheet())
    window = MainWindow(repo_path=str(paths.repo_root()))
    window.resize(1440, 900)
    window.show()
    return app.exec_()
