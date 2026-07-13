"""Background worker threads for the RADIANT GUI.

The Qt main thread never runs the signal chain (arch doc §3.2): a full-chain
evaluation runs in a :class:`QThread` worker that emits its result by signal.
A full chain evaluates in ~0.22 s, so the worker reports only started / finished
/ failed — there is no per-stage progress stream (``Sensor.evaluate()`` takes no
progress callback).

Phase 1 (Task A) ships the *signature only*: the class, its signals, and the
constructor. GUI plan Phase 3 implements :meth:`EvaluationWorker.run` (wrapping
``sensor.evaluate()`` and emitting the outcome). Kept as a stub here so the
threading contract is fixed and importable before the evaluate loop is built.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QThread, Signal

if TYPE_CHECKING:
    from radiant.api.sensor import Sensor


class EvaluationWorker(QThread):
    """Run one full-chain ``sensor.evaluate()`` off the GUI thread.

    Signals
    -------
    finished_ok(object)
        Emitted with the ``ChainResult`` on success.
    failed(object)
        Emitted with the raised exception (``RadiantError`` or otherwise) on
        failure. The exception is re-emitted to the GUI thread, never swallowed
        (Rules 15/17); the GUI renders it as a what/why/action modal or a
        traceback dialog.

    Notes
    -----
    Phase 1 stub: :meth:`run` is intentionally unimplemented and raises
    :class:`NotImplementedError`. GUI plan Phase 3 fills it in.
    """

    finished_ok = Signal(object)  # ChainResult
    failed = Signal(object)  # Exception

    def __init__(self, sensor: Sensor) -> None:
        super().__init__()
        self._sensor = sensor

    def run(self) -> None:  # noqa: D102  (documented on the class; Phase 3 implements)
        raise NotImplementedError(
            "EvaluationWorker.run is implemented in GUI plan Phase 3 (evaluate loop). "
            "Phase 1 ships the threading-contract signature only."
        )
