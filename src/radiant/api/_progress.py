"""Progress and cancellation plumbing for long-running API operations (Gap 72).

One concern (Rule 19): the callback types and the cancel check shared by
``sweep``/``sweep_2d``/``monte_carlo``/``sensitivity``/``BatchRunner``.

Contract
--------
``progress(done, total)`` is called after each completed unit of work
(sweep point, MC trial, perturbed parameter, batch cell). ``cancel()``
is polled before each unit; returning True aborts the operation by
raising :class:`OperationCancelledError`. Both callbacks run on the
calling thread — a GUI typically flips a flag from its event loop and
reads progress into a bar. Exceptions raised inside ``progress`` are
not swallowed (Rule 17): a broken callback fails the operation loudly.
"""

from __future__ import annotations

from collections.abc import Callable

from radiant.core.exceptions import RadiantError

ProgressFn = Callable[[int, int], None]
CancelFn = Callable[[], bool]


class OperationCancelledError(RadiantError):
    """A long-running operation was cancelled via its ``cancel`` callback.

    Carries ``operation``, ``done``, and ``total`` so callers can report
    how far the work had progressed. No partial result object is
    returned — a cancelled operation has no result (callers wanting
    partials should sweep in chunks).
    """

    def __init__(self, operation: str, done: int, total: int) -> None:
        self.operation = operation
        self.done = done
        self.total = total
        super().__init__(
            f"{operation} cancelled after {done}/{total} evaluations. "
            "No result is returned for a cancelled operation; re-run, or "
            "sweep in smaller chunks if partial results are needed."
        )


def check_cancel(cancel: CancelFn | None, operation: str, done: int, total: int) -> None:
    """Raise :class:`OperationCancelledError` if *cancel* reports True."""
    if cancel is not None and cancel():
        raise OperationCancelledError(operation, done, total)
