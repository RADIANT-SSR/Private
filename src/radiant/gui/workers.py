"""Background worker threads for the RADIANT GUI.

The Qt main thread never runs the signal chain (arch doc §3.2, GUI plan §4.5): a
full-chain evaluation runs in a :class:`QThread` worker that emits its result by
signal. A full chain evaluates in **~0.8 s** on the shipped MWIR example (measured
2026-07-29, CU-249; the bulk of it is the optics stage's PSF/MTF FFTs on the
hardcoded 128-pixel pupil grid — see CU-288) and a configuration set is capped at
eight configurations, so the worker reports only finished / failed — there is no
per-stage progress stream; the status bar shows a plain busy indicator while it
runs.

Since the multi-configuration Phase 4a the session model is a
:class:`~radiant.api.config_set.ConfigurationSet` (the ordinary single-model
session is the degenerate one-configuration set), so the worker drives
``ConfigurationSet.evaluate_all`` — one call, every configuration, the displayed
one first.

The worker owns the set it evaluates. The caller hands it a **private snapshot**
(``config_set.clone()``, taken on the GUI thread at schedule time) so a parameter
edit that lands on the GUI thread while the chain is mid-run cannot race the
worker's read of the same object — the two threads never touch the same
:class:`~radiant.api.sensor.Sensor`. Cloning is the thread-isolation mechanism,
not a second API surface: the worker still performs exactly one ``evaluate_all()``
call (one GUI action ↔ one API call, GUI plan §4.1).

Warning capture lives in the API, not here: ``evaluate_all`` opens a
per-configuration ``warnings.catch_warnings`` window and records each
configuration's warnings on ``ConfigRun.warnings`` (already re-logged there), so a
second capture in this module would double-count them and destroy the
per-configuration attribution.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QThread, Signal

if TYPE_CHECKING:
    from radiant.api.config_set import ConfigurationSet


class ConfigSetEvaluationWorker(QThread):
    """Run one ``ConfigurationSet.evaluate_all()`` off the GUI thread.

    Parameters
    ----------
    config_set:
        The configuration set to evaluate. The caller passes a private
        ``clone()`` so the worker's read cannot race a concurrent GUI-thread
        edit (see the module docstring). Its ``active`` configuration is
        evaluated first, so the displayed views refresh at single-model latency.

    Signals
    -------
    finished_ok(object)
        Emitted on success with the
        :class:`~radiant.api.config_set.ConfigSetRunResult` — every
        configuration's :class:`~radiant.io.results.ChainResult` **or** its
        recorded failure, plus the warnings attributed to each (Rule 17: a
        failed configuration is data, never a silent drop).
    failed(object)
        Emitted with the raised exception when the *pass itself* could not run
        (a cancellation, or a non-``RadiantError`` bug — a per-configuration
        physics failure is recorded on the result instead). The exception is
        re-emitted to the GUI thread, never swallowed (Rules 15/17).
    """

    finished_ok = Signal(object)  # ConfigSetRunResult
    failed = Signal(object)  # Exception

    def __init__(self, config_set: ConfigurationSet) -> None:
        super().__init__()
        self._config_set = config_set

    def run(self) -> None:
        """Evaluate every configuration, emitting the outcome on the GUI thread.

        The ``except Exception`` is a thread-boundary hand-off, not a swallow
        (arch doc §3.2): the exception is re-emitted via :attr:`failed` to the
        GUI thread, which renders it (``RadiantError`` → what/why/action modal;
        anything else → traceback dialog). Nothing is silently dropped.
        """
        try:
            run = self._config_set.evaluate_all()
        except Exception as exc:  # re-emitted to the GUI thread, never swallowed
            self.failed.emit(exc)
            return
        self.finished_ok.emit(run)


__all__ = ["ConfigSetEvaluationWorker"]
