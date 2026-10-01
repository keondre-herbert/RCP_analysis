from __future__ import annotations

import re

from PyQt5.QtCore import QAbstractTableModel, QModelIndex, QRectF, QSortFilterProxyModel, Qt
from PyQt5.QtGui import QBrush, QColor, QFont, QPainter, QPen
from PyQt5.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QStyledItemDelegate,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from veles.ui.theme import MONO_FONT, TOKENS
from veles.ui.widgets.status_pill import StatusPill
from veles.ui.wizard.base import StepPage, label, panel
from veles.wizard_state import STRIP, STRIP_LABELS, WizardState, last_processed, raw_file_problems, strip_state

CHECK, NAME, CONDITIONS = 0, 1, 2
FIRST_STRIP = 3
LAST = FIRST_STRIP + len(STRIP)
STATE_ROLE = Qt.UserRole + 1

STATUS_CHOICES = {"Missing or stale": {"missing", "stale"}, "Failed": {"failed"}, "Up to date": {"ok"}}


class SessionsModel(QAbstractTableModel):
    def __init__(self, state: WizardState):
        super().__init__()
        self.state = state
        self.names: list[str] = []
        self.strip: dict[tuple[str, str], str] = {}

    def reload(self) -> None:
        self.beginResetModel()
        self.names = list(self.state.sessions)
        self.strip = {(n, step): strip_state(s, step) for n, s in self.state.sessions.items() for step, _ in STRIP}
        self.endResetModel()

    def selection_changed(self) -> None:
        if self.names:
            self.dataChanged.emit(self.index(0, 0), self.index(len(self.names) - 1, LAST))

    def rowCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self.names)

    def columnCount(self, parent=QModelIndex()) -> int:
        return LAST + 1

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if orientation != Qt.Horizontal or role != Qt.DisplayRole:
            return None
        if FIRST_STRIP <= section < LAST:
            return STRIP[section - FIRST_STRIP][1]
        return {CHECK: "", NAME: "Session", CONDITIONS: "Conditions", LAST: "Last processed"}[section]

    def data(self, index, role=Qt.DisplayRole):
        name = self.names[index.row()]
        session = self.state.sessions[name]
        col = index.column()
        selected = name in self.state.selected
        if role == Qt.BackgroundRole and selected:
            return QBrush(QColor(TOKENS["subtle"]))
        if col == CHECK and role == Qt.CheckStateRole:
            return Qt.Checked if selected else Qt.Unchecked
        if col == NAME and role == Qt.DisplayRole:
            return name
        if col == NAME and role == Qt.FontRole:
            return QFont(MONO_FONT)
        if col == CONDITIONS and role == Qt.DisplayRole:
            return f"{len(session.conditions)} BR files"
        if FIRST_STRIP <= col < LAST:
            step, short = STRIP[col - FIRST_STRIP]
            value = self.strip[(name, step)]
            if role == STATE_ROLE:
                return value
            if role == Qt.ToolTipRole:
                return f"{short}: {STRIP_LABELS[value]}"
        if col == LAST:
            problems = raw_file_problems(session)
            if role == Qt.DisplayRole:
                if problems:
                    return f"{len(problems)} file{'s' if len(problems) > 1 else ''} missing"
                when = last_processed(session)
                return when.strftime("%b %d") if when else "—"
            if role == Qt.ForegroundRole and problems:
                return QBrush(QColor(TOKENS["fail_fg"]))
            if role == Qt.ToolTipRole and session.notes:
                return "\n".join(session.notes)
        return None

    def flags(self, index):
        base = Qt.ItemIsEnabled
        return base | Qt.ItemIsUserCheckable if index.column() == CHECK else base

    def setData(self, index, value, role=Qt.EditRole) -> bool:
        if index.column() != CHECK or role != Qt.CheckStateRole:
            return False
        name = self.names[index.row()]
        chosen = set(self.state.selected)
        chosen.symmetric_difference_update({name})
        self.state.set_selected(chosen)
        self.selection_changed()
        return True


class StripDelegate(QStyledItemDelegate):
    """Paints one status-strip cell as a small bar: filled, outlined (not run) or hatched (n/a)."""

    FILL = {"ok": "ink", "stale": "stale_mark", "failed": "fail_fg"}

    def paint(self, painter: QPainter, option, index) -> None:
        super().paint(painter, option, index)  # row background
        state = index.data(STATE_ROLE)
        rect = QRectF(option.rect).adjusted(5, 0, -5, 0)
        rect.setHeight(18)
        rect.moveCenter(QRectF(option.rect).center())
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)
        if state in self.FILL:
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(TOKENS[self.FILL[state]]))
        else:
            painter.setPen(QPen(QColor(TOKENS["line"]), 1))
            painter.setBrush(QBrush(QColor(TOKENS["line"]), Qt.BDiagPattern) if state == "na" else QColor(TOKENS["surface"]))
        painter.drawRoundedRect(rect, 3, 3)
        painter.restore()

    def initStyleOption(self, option, index) -> None:
        super().initStyleOption(option, index)
        option.text = ""


class SessionsPage(StepPage):
    def __init__(self, state: WizardState, parent: QWidget | None = None):
        super().__init__(state, parent)
        self.model = SessionsModel(state)
        self.proxy = QSortFilterProxyModel()
        self.proxy.setSourceModel(self.model)
        self.proxy.setFilterKeyColumn(NAME)
        self.proxy.setFilterCaseSensitivity(Qt.CaseInsensitive)
        self.model.dataChanged.connect(self._selection_changed)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(40, 32, 40, 32)
        layout.setSpacing(28)
        layout.addWidget(self._ways_panel(), stretch=0)
        layout.addWidget(self._table_panel(), stretch=1)

    # --- left: ways to select ---

    def _ways_panel(self) -> QWidget:
        box = panel()
        box.setFixedWidth(400)
        self.range_from, self.range_to = QComboBox(), QComboBox()
        self.status_kind, self.status_step = QComboBox(), QComboBox()
        self.status_kind.addItems(STATUS_CHOICES)
        for step, short in STRIP:
            self.status_step.addItem(short, step)
        self.status_step.setCurrentIndex(len(STRIP) - 1)
        self.paste = QPlainTextEdit()
        self.paste.setPlaceholderText("NRR_RW010, RW014, 016 …")
        self.paste.setFixedHeight(84)
        self.paste_error = label("", "error", wrap=True)
        self.select_all = QPushButton("Select all")
        clear = QPushButton("Clear")

        add_range, add_status, add_paste = QPushButton("Add"), QPushButton("Add"), QPushButton("Add")
        add_range.clicked.connect(self._add_range)
        add_status.clicked.connect(self._add_status)
        add_paste.clicked.connect(self._add_paste)
        self.select_all.clicked.connect(lambda: self._select(self.state.sessions, replace=True))
        clear.clicked.connect(lambda: self._select([], replace=True))

        def row(*widgets):
            line = QHBoxLayout()
            line.setSpacing(10)
            for w in widgets:
                line.addWidget(w, stretch=1 if isinstance(w, (QComboBox, QLineEdit)) else 0)
            return line

        v = QVBoxLayout(box)
        v.setContentsMargins(26, 24, 26, 22)
        v.setSpacing(10)
        v.addWidget(label("Ways to select", "h2"))
        v.addWidget(label("Each adds to the selection on the right.", "muted"))
        v.addSpacing(14)
        v.addWidget(label("Range", "field"))
        v.addLayout(row(self.range_from, label("to", "muted"), self.range_to, add_range))
        v.addSpacing(14)
        v.addWidget(label("By pipeline status", "field"))
        v.addLayout(row(self.status_kind, self.status_step, add_status))
        v.addSpacing(14)
        v.addWidget(label("Paste a list", "field"))
        v.addWidget(self.paste)
        v.addLayout(row(self.paste_error, add_paste))
        v.addStretch(1)
        v.addLayout(row(self.select_all, clear))
        return box

    # --- right: the table ---

    def _table_panel(self) -> QWidget:
        box = panel()
        self.count = StatusPill()
        self.filter = QLineEdit()
        self.filter.setPlaceholderText("Filter sessions…")
        self.filter.setFixedWidth(280)
        self.filter.textChanged.connect(self._filter)

        self.table = QTableView()
        self.table.setModel(self.proxy)
        self.table.setItemDelegate(QStyledItemDelegate(self.table))
        strip = StripDelegate(self.table)
        for col in range(FIRST_STRIP, LAST):
            self.table.setItemDelegateForColumn(col, strip)
        self.table.setShowGrid(False)
        self.table.setWordWrap(False)
        self.table.setSelectionMode(QAbstractItemView.NoSelection)
        self.table.setFocusPolicy(Qt.NoFocus)
        self.table.verticalHeader().hide()
        self.table.verticalHeader().setDefaultSectionSize(44)
        header = self.table.horizontalHeader()
        header.setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        header.setHighlightSections(False)
        for col, width in ((CHECK, 44), (NAME, 150), (CONDITIONS, 120)):
            header.setSectionResizeMode(col, QHeaderView.Fixed)
            header.resizeSection(col, width)
        for col in range(FIRST_STRIP, LAST):
            header.setSectionResizeMode(col, QHeaderView.Fixed)
            header.resizeSection(col, 56)
        header.setSectionResizeMode(LAST, QHeaderView.Stretch)

        self.shown = label("", "muted")
        legend = QHBoxLayout()
        legend.setSpacing(16)
        swatch = lambda token, mark="■": f'<span style="color:{TOKENS[token]}">{mark}</span>'
        legend.addWidget(label(
            f"Status from data_status_reaching.csv: &nbsp; {swatch('ink')} Up to date &nbsp; {swatch('stale_mark')} Stale"
            f" &nbsp; {swatch('fail_fg')} Failed &nbsp; {swatch('faint', '□')} Not run &nbsp; {swatch('faint', '▨')} n/a", "muted"))
        legend.addStretch(1)
        legend.addWidget(self.shown)

        top = QHBoxLayout()
        top.setSpacing(16)
        top.addWidget(label("Sessions", "h2"))
        top.addWidget(self.count)
        top.addStretch(1)
        top.addWidget(self.filter)

        v = QVBoxLayout(box)
        v.setContentsMargins(26, 20, 26, 16)
        v.setSpacing(14)
        v.addLayout(top)
        v.addWidget(self.table, stretch=1)
        v.addLayout(legend)
        return box

    # --- behaviour ---

    def enter(self) -> None:
        if self.model.names != list(self.state.sessions):
            self.model.reload()
            names = list(self.state.sessions)
            for combo in (self.range_from, self.range_to):
                combo.clear()
                combo.addItems(names)
            self.range_to.setCurrentIndex(len(names) - 1)
            self.select_all.setText(f"Select all {len(names)}")
        self._show_count()
        self._filter(self.filter.text())

    def _select(self, names, replace: bool = False) -> None:
        chosen = set(names) if replace else set(self.state.selected) | set(names)
        self.state.set_selected(chosen)
        self.model.selection_changed()

    def _add_range(self) -> None:
        names = list(self.state.sessions)
        a, b = sorted((self.range_from.currentIndex(), self.range_to.currentIndex()))
        if a >= 0:
            self._select(names[a:b + 1])

    def _add_status(self) -> None:
        wanted = STATUS_CHOICES[self.status_kind.currentText()]
        step = self.status_step.currentData()
        self._select(n for n in self.model.names if self.model.strip[(n, step)] in wanted)

    def _add_paste(self) -> None:
        tokens = [t for t in re.split(r"[\s,;]+", self.paste.toPlainText()) if t]
        found, missing = [], []
        for token in tokens:
            match = [n for n in self.state.sessions if n == token or n.endswith(token)]
            (found if len(match) == 1 else missing).append(match[0] if len(match) == 1 else token)
        self._select(found)
        self.paste_error.setText(f"Not found or ambiguous: {', '.join(missing)}" if missing else "")

    def _filter(self, text: str) -> None:
        self.proxy.setFilterFixedString(text)
        self.shown.setText(f"{self.proxy.rowCount()} of {len(self.model.names)} shown")

    def _show_count(self) -> None:
        self.count.set(f"{len(self.state.selected)} of {len(self.state.sessions)} selected")

    def _selection_changed(self, *_) -> None:
        self._show_count()
        self.changed.emit()  # only for user edits; entering the page must not count as a change

    def is_complete(self) -> bool:
        return bool(self.state.selected)

    def summary(self) -> str:
        chosen = self.state.selected
        if not chosen:
            return "Select at least one session"
        span = chosen[0] if len(chosen) == 1 else f"{chosen[0]} – {chosen[-1]}"
        return f"{len(chosen)} session{'s' if len(chosen) > 1 else ''} · {span}"
