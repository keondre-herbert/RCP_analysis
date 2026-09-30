from __future__ import annotations

from PyQt5.QtWidgets import QWidget

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
}

UI_FONT = "Segoe UI"
MONO_FONT = "Consolas"


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
