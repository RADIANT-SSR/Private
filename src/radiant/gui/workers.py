"""Background worker threads for the RADIANT GUI.

The Qt main thread never runs the signal chain (arch doc §3.2, GUI plan §4.5): a
full-chain evaluation runs in a :class:`QThread` worker that emits its result by
signal. A full chain evaluates in **~0.8 s** on the shipped MWIR example (measured
2026-07-29, CU-249; the bulk of it is the optics stage's PSF/MTF FFTs on the
hardcoded 128-pixel pupil grid — see CU-288) and a configuration set is capped at
twelve configurations, so the worker reports only finished / failed — there is no
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

The worker is **cancellable and joinable**, which is what makes closing the
window safe (CU-353). ``evaluate_all`` polls a caller-supplied ``cancel()``
before each configuration (Gap 72), so :meth:`ConfigSetEvaluationWorker.request_cancel`
stops a multi-configuration pass at the next configuration boundary; the
configuration already in flight still finishes (~0.8 s), and the host joins it
with :meth:`QThread.wait`. Nothing here can abandon a running thread: a
``QThread`` destroyed while its thread is still running calls ``std::terminate``
and takes the process down — which is exactly what a close during a burst of
evaluations did (owner walkthrough 2026-09-10, "QThread: Destroyed while thread
'' is still running").

Warning capture lives in the API, not here: ``evaluate_all`` opens a
per-configuration, **thread-local** capture window
(``radiant.api._warning_capture``, CU-110) and records each configuration's
warnings on ``ConfigRun.warnings`` (already re-logged there), so a second capture
in this module would double-count them and destroy the per-configuration
attribution. Because the capture is thread-local, this worker running beside a
sweep/solve/evaluate-all dialog worker no longer cross-attributes warnings.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QThread, Signal

from radiant.api import OperationCancelledError

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
        (a non-``RadiantError`` bug — a per-configuration physics failure is
        recorded on the result instead). The exception is re-emitted to the GUI
        thread, never swallowed (Rules 15/17).
    cancelled()
        Emitted when the pass stopped because :meth:`request_cancel` was called.
        A deliberate stop is not a failure and carries nothing to render, so it
        is its own signal rather than a ``failed`` the host has to classify —
        but it is still *named*, never a silent return (Rule 17).
    """

    finished_ok = Signal(object)  # ConfigSetRunResult
    failed = Signal(object)  # Exception
    cancelled = Signal()

    def __init__(self, config_set: ConfigurationSet) -> None:
        super().__init__()
        self._config_set = config_set
        # Written on the GUI thread, read on the worker thread. A lone bool
        # needs no lock: CPython's attribute store is atomic, the transition is
        # one-way (False → True), and a poll that reads the stale value simply
        # cancels one configuration later. Same shape as ``_SweepWorker``.
        self._cancel = False

    def request_cancel(self) -> None:
        """Ask the pass to stop at the next configuration boundary (thread-safe).

        The configuration already being evaluated runs to completion — the chain
        has no interior cancellation point — so a caller that must not outlive
        the thread still has to :meth:`QThread.wait` for it.
        """
        self._cancel = True

    def run(self) -> None:
        """Evaluate every configuration, emitting the outcome on the GUI thread.

        The ``except Exception`` is a thread-boundary hand-off, not a swallow
        (arch doc §3.2): the exception is re-emitted via :attr:`failed` to the
        GUI thread, which renders it (``RadiantError`` → what/why/action modal;
        anything else → traceback dialog). Nothing is silently dropped.
        """
        try:
            run = self._config_set.evaluate_all(cancel=lambda: self._cancel)
        except OperationCancelledError:
            # Asked for, by us — there is no result to render and no error to
            # report, only the fact that the pass stopped.
            self.cancelled.emit()
            return
        except Exception as exc:  # re-emitted to the GUI thread, never swallowed
            self.failed.emit(exc)
            return
        self.finished_ok.emit(run)


__all__ = ["ConfigSetEvaluationWorker"]
