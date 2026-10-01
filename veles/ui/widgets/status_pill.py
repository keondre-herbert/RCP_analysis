from __future__ import annotations

from PyQt5.QtWidgets import QLabel, QWidget

from veles.ui.theme import restyle


class StatusPill(QLabel):
    """Small mono tag with a square dot, e.g. '■ 21 sessions'. Kinds: neutral, ink, stale, fail."""

    def __init__(self, text: str = "", kind: str = "neutral", parent: QWidget | None = None):
        super().__init__(parent)
        self.setProperty("role", "pill")
        self.set(text, kind)

    def set(self, text: str, kind: str = "neutral") -> None:
        self.setText(f"■  {text}" if text else "")
        self.setVisible(bool(text))
        restyle(self, kind=kind)
