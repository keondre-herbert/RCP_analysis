from __future__ import annotations

from typing import Any, Callable

from PyQt5.QtCore import QObject, QRunnable, QThreadPool, pyqtSignal


class _Signals(QObject):
    done = pyqtSignal(object)
    failed = pyqtSignal(object)


class _Job(QRunnable):
    def __init__(self, fn: Callable[[], Any], signals: _Signals):
        super().__init__()
        self.fn = fn
        self.signals = signals

    def run(self) -> None:
        try:
            result = self.fn()
        except Exception as error:  # handed to on_error on the UI thread
            self.signals.failed.emit(error)
        else:
            self.signals.done.emit(result)


_alive: set[_Signals] = set()


def run_in_background(fn: Callable[[], Any], on_done: Callable[[Any], None], on_error: Callable[[Exception], None]) -> None:
    """Run fn on a worker thread; on_done / on_error are called back on the UI thread (signals are queued)."""
    signals = _Signals()
    _alive.add(signals)  # keep it alive until the job reports back
    signals.done.connect(on_done)
    signals.failed.connect(on_error)
    signals.done.connect(lambda _: _alive.discard(signals))
    signals.failed.connect(lambda _: _alive.discard(signals))
    QThreadPool.globalInstance().start(_Job(fn, signals))
