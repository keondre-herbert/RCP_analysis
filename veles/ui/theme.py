from __future__ import annotations

import sys

from PyQt5.QtGui import QColor, QFont, QPalette
from PyQt5.QtWidgets import QApplication, QWidget

from veles import paths

# SPEC §7 colour tokens. veles.qss refers to them as @name; widgets that paint themselves read them from here.
TOKENS: dict[str, str] = {
    "ground": "#EEEEEE",
    "surface": "#FFFFFF",
    "subtle": "#F6F6F6",
    "line": "#D4D4D4",
    "divider": "#E5E5E5",
    "ink": "#111111",
    "ink_hover": "#333333",
    "muted": "#5A5A5A",
    "faint": "#8C8C8C",
    "stale_bg": "#FFF0BF",
    "stale_fg": "#6E5200",
    "fail_bg": "#FCE3E4",
    "fail_fg": "#B42318",
    "stale_mark": "#EFC64B",  # solid yellow for small status marks (strip cells), where stale_bg is too pale
}

if sys.platform == "darwin":
    UI_FONT, MONO_FONT = "Helvetica Neue", "Menlo"
elif sys.platform == "win32":
    UI_FONT, MONO_FONT = "Segoe UI", "Consolas"
else:
    UI_FONT, MONO_FONT = "DejaVu Sans", "DejaVu Sans Mono"


def load_stylesheet() -> str:
    qss = paths.resource("veles.qss").read_text(encoding="utf-8")
    for name in sorted(TOKENS, key=len, reverse=True):  # longest first so @ink_hover isn't hit by @ink
        qss = qss.replace(f"@{name}", TOKENS[name])
    return qss.replace("@mono", MONO_FONT)


def restyle(widget: QWidget, **properties: str) -> None:
    """Set dynamic properties used by veles.qss selectors (e.g. state="current") and re-apply the style."""
    for name, value in properties.items():
        widget.setProperty(name, value)
    widget.style().unpolish(widget)
    widget.style().polish(widget)


def apply_theme(app: QApplication) -> None:
    """Same light look on every OS: Fusion style, a palette from TOKENS (so dark mode can't turn text white), fonts, qss."""
    app.setStyle("Fusion")
    c = {name: QColor(value) for name, value in TOKENS.items()}
    palette = QPalette()
    for role, token in (
        (QPalette.Window, "ground"), (QPalette.WindowText, "ink"), (QPalette.Base, "surface"),
        (QPalette.AlternateBase, "subtle"), (QPalette.Text, "ink"), (QPalette.Button, "surface"),
        (QPalette.ButtonText, "ink"), (QPalette.Highlight, "ink"), (QPalette.HighlightedText, "surface"),
        (QPalette.ToolTipBase, "surface"), (QPalette.ToolTipText, "ink"), (QPalette.PlaceholderText, "faint"),
        (QPalette.Light, "surface"), (QPalette.Mid, "line"), (QPalette.Dark, "faint"),
    ):
        palette.setColor(role, c[token])
    for role in (QPalette.Text, QPalette.WindowText, QPalette.ButtonText):
        palette.setColor(QPalette.Disabled, role, c["faint"])
    app.setPalette(palette)
    font = QFont(UI_FONT)
    font.setPixelSize(14)
    app.setFont(font)
    app.setStyleSheet(load_stylesheet())
