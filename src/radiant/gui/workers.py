"""Background worker threads for the RADIANT GUI.

The Qt main thread never runs the signal chain (arch doc §3.2, GUI plan §4.5): a
full-chain evaluation runs in a :class:`QThread` worker that emits its result by
signal. A full chain evaluates in ~0.22 s, so the worker reports only finished /
failed — there is no per-stage progress stream (``Sensor.evaluate()`` takes no
progress callback); the status bar shows a plain busy indicator while it runs.

The worker owns the :class:`~radiant.api.sensor.Sensor` it evaluates. The caller
hands it a **private snapshot** (``sensor.clone()``, taken on the GUI thread at
schedule time) so a parameter edit that lands on the GUI thread while the chain
is mid-run cannot race the worker's read of the same sensor — the two threads
never touch the same object. Cloning is the thread-isolation mechanism, not a
second API surface: the worker still performs exactly one ``evaluate()`` call
(one GUI action ↔ one API call, GUI plan §4.1).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QThread, Signal

if TYPE_CHECKING:
    from radiant.api.sensor import Sensor


class EvaluationWorker(QThread):
    """Run one full-chain ``sensor.evaluate()`` off the GUI thread.

    Parameters
    ----------
    sensor:
        The sensor to evaluate. The caller passes a private ``clone()`` so the
        worker's read cannot race a concurrent GUI-thread edit (see module
        docstring).

    Signals
    -------
    finished_ok(object)
        Emitted with the ``ChainResult`` on success.
    failed(object)
        Emitted with the raised exception (``RadiantError`` or otherwise) on
        failure. The exception is re-emitted to the GUI thread, never swallowed
        (Rules 15/17); the GUI renders it as a what/why/action modal or a
        traceback dialog.
    """

    finished_ok = Signal(object)  # ChainResult
    failed = Signal(object)  # Exception

    def __init__(self, sensor: Sensor) -> None:
        super().__init__()
        self._sensor = sensor

    def run(self) -> None:
        """Evaluate the full chain, emitting the outcome on the GUI thread.

        The ``except Exception`` is a thread-boundary hand-off, not a swallow
        (arch doc §3.2): the exception is re-emitted via :attr:`failed` to the
        GUI thread, which renders it (``RadiantError`` → what/why/action modal;
        anything else → traceback dialog). Nothing is silently dropped.
        """
        try:
            result = self._sensor.evaluate()
        except Exception as exc:  # re-emitted to the GUI thread, never swallowed
            self.failed.emit(exc)
        else:
            self.finished_ok.emit(result)
