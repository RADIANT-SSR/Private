"""Tests for the thread-local warning capture (:mod:`radiant.api._warning_capture`, CU-110).

The defect this replaces: ``warnings.catch_warnings(record=True)`` records into a
**process-global** slot, so two evaluation threads either cross-attribute their
warnings or lose them, and one thread's exit restores the filter state the other
was still relying on. Every test below is written so that it **fails** against a
``catch_warnings``-based capture:

* the two-thread attribution test has both captures open simultaneously (barrier
  synchronised, no sleeps), which is exactly the interleaving ``catch_warnings``
  cannot survive;
* the uncaptured-thread test asserts a warning raised where no capture is open
  still reaches the ambient handler — ``catch_warnings(record=True)`` swallows it
  into the open window instead (Rule 17: nothing is silently dropped).

The remaining tests pin the behaviour that must **not** change: single-thread
records, the ``"always"`` action that defeats the once-per-location registry, and
full restoration of the caller's filters and ``showwarning`` on exit.
"""

from __future__ import annotations

import threading
import warnings
from typing import Any

import pytest

from radiant.api._warning_capture import capture_warnings

# Every barrier wait is bounded so a wiring bug fails the test instead of hanging
# the suite; the passing path never spends this long (both parties are already at
# the barrier).
_BARRIER_TIMEOUT_S = 20.0


def _messages(records: list[warnings.WarningMessage]) -> list[str]:
    return [str(record.message) for record in records]


class TestSingleThread:
    """Behaviour under one thread is exactly what ``catch_warnings`` gave."""

    def test_records_the_warnings_raised_in_the_block(self) -> None:
        with capture_warnings() as captured:
            warnings.warn("first", UserWarning, stacklevel=1)
            warnings.warn("second", FutureWarning, stacklevel=1)
        assert _messages(captured) == ["first", "second"]
        assert [r.category for r in captured] == [UserWarning, FutureWarning]

    def test_records_are_complete_before_the_block_exits(self) -> None:
        """The list fills live, so a ``finally`` inside the block can read it."""
        with capture_warnings() as captured:
            warnings.warn("live", UserWarning, stacklevel=1)
            assert _messages(captured) == ["live"]

    def test_always_action_defeats_the_once_per_location_registry(self) -> None:
        """The same warn site in two windows is captured twice, not deduplicated.

        This is what per-configuration attribution rests on: without the
        ``"always"`` action the second configuration's identical warning would be
        swallowed by the caller module's ``__warningregistry__``.
        """
        seen = []
        for _ in range(2):
            with capture_warnings() as captured:
                warnings.warn("repeated", UserWarning, stacklevel=1)
            seen.append(_messages(captured))
        assert seen == [["repeated"], ["repeated"]]

    def test_an_ambient_error_filter_cannot_raise_inside_the_window(self) -> None:
        """``filterwarnings=error`` outside must not convert a chain warning into a raise."""
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            with capture_warnings() as captured:
                warnings.warn("not an exception", UserWarning, stacklevel=1)
        assert _messages(captured) == ["not an exception"]

    def test_the_callers_filters_and_handler_are_restored(self) -> None:
        before_filters = list(warnings.filters)
        before_handler = warnings.showwarning
        with capture_warnings():
            warnings.warn("ignored", UserWarning, stacklevel=1)
        assert list(warnings.filters) == before_filters
        assert warnings.showwarning is before_handler

    def test_filters_are_restored_when_the_block_raises(self) -> None:
        before_filters = list(warnings.filters)
        before_handler = warnings.showwarning
        with pytest.raises(RuntimeError, match="boom"), capture_warnings():
            raise RuntimeError("boom")
        assert list(warnings.filters) == before_filters
        assert warnings.showwarning is before_handler

    def test_nested_captures_record_into_the_innermost(self) -> None:
        with capture_warnings() as outer:
            warnings.warn("outer-before", UserWarning, stacklevel=1)
            with capture_warnings() as inner:
                warnings.warn("inner", UserWarning, stacklevel=1)
            warnings.warn("outer-after", UserWarning, stacklevel=1)
        assert _messages(inner) == ["inner"]
        assert _messages(outer) == ["outer-before", "outer-after"]


class TestConcurrentThreads:
    """Two workers inside the capture window at the same time — CU-110's race."""

    def test_each_thread_captures_only_its_own_warnings(self) -> None:
        """Both captures are open simultaneously, and neither sees the other's warning.

        Deterministic by construction: the first barrier releases only once both
        threads have an open capture, the second only once both have warned — so
        the two windows provably overlap, with no sleeps and no timing luck.
        """
        both_open = threading.Barrier(2, timeout=_BARRIER_TIMEOUT_S)
        both_warned = threading.Barrier(2, timeout=_BARRIER_TIMEOUT_S)
        captured: dict[str, list[str]] = {}
        errors: list[BaseException] = []

        def worker(tag: str) -> None:
            try:
                with capture_warnings() as records:
                    both_open.wait()
                    warnings.warn(f"from {tag}", UserWarning, stacklevel=1)
                    both_warned.wait()
                    captured[tag] = _messages(records)
            except BaseException as exc:  # noqa: BLE001 — re-raised on the main thread
                errors.append(exc)
                both_open.abort()
                both_warned.abort()

        threads = [threading.Thread(target=worker, args=(tag,)) for tag in ("A", "B")]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=_BARRIER_TIMEOUT_S * 2)

        assert not errors, errors
        assert captured == {"A": ["from A"], "B": ["from B"]}

    def test_the_first_capture_to_exit_does_not_disarm_a_later_one(self) -> None:
        """Captures that open and close out of order stay independent.

        The worker's capture opens **first** and closes **first**, while this
        thread's capture is still open. ``catch_warnings`` is a save/restore
        stack that assumes strict LIFO nesting on one thread, so the worker's
        exit would restore the handler that predated *both* windows and this
        thread's still-open capture would silently record nothing.
        """
        first_open = threading.Barrier(2, timeout=_BARRIER_TIMEOUT_S)
        second_open = threading.Barrier(2, timeout=_BARRIER_TIMEOUT_S)
        first_closed = threading.Barrier(2, timeout=_BARRIER_TIMEOUT_S)
        late: list[str] = []
        errors: list[BaseException] = []

        def early_worker() -> None:
            try:
                with capture_warnings():
                    first_open.wait()
                    second_open.wait()
                first_closed.wait()
            except BaseException as exc:  # noqa: BLE001
                errors.append(exc)
                for barrier in (first_open, second_open, first_closed):
                    barrier.abort()

        thread = threading.Thread(target=early_worker)
        thread.start()
        try:
            first_open.wait(timeout=_BARRIER_TIMEOUT_S)
            with capture_warnings() as records:
                second_open.wait(timeout=_BARRIER_TIMEOUT_S)
                first_closed.wait(timeout=_BARRIER_TIMEOUT_S)
                warnings.warn("late", UserWarning, stacklevel=1)
                late.extend(_messages(records))
        finally:
            thread.join(timeout=_BARRIER_TIMEOUT_S * 2)

        assert not errors, errors
        assert late == ["late"]

    def test_a_warning_on_an_uncaptured_thread_reaches_the_ambient_handler(self) -> None:
        """Rule 17: a thread with no capture open keeps the default handler.

        ``catch_warnings(record=True)`` fails this — the warning would be eaten
        into the other thread's list and shown to nobody.
        """
        capture_open = threading.Barrier(2, timeout=_BARRIER_TIMEOUT_S)
        warned = threading.Barrier(2, timeout=_BARRIER_TIMEOUT_S)
        recorded: list[str] = []
        delivered: list[str] = []
        errors: list[BaseException] = []

        def capturing_worker() -> None:
            try:
                with capture_warnings() as records:
                    capture_open.wait()
                    warned.wait()
                    recorded.extend(_messages(records))
            except BaseException as exc:  # noqa: BLE001
                errors.append(exc)
                capture_open.abort()
                warned.abort()

        thread = threading.Thread(target=capturing_worker)
        # The sentinel handler is installed BEFORE the worker's capture opens, so
        # it is the handler the capture saves and forwards uncaptured warnings to.
        with warnings.catch_warnings():
            warnings.simplefilter("always")

            def sentinel(
                message: Warning | str,
                category: type[Warning],
                filename: str,
                lineno: int,
                file: Any = None,
                line: str | None = None,
            ) -> None:
                delivered.append(str(message))

            warnings.showwarning = sentinel
            thread.start()
            try:
                capture_open.wait(timeout=_BARRIER_TIMEOUT_S)
                warnings.warn("uncaptured", UserWarning, stacklevel=1)
                warned.wait(timeout=_BARRIER_TIMEOUT_S)
            finally:
                thread.join(timeout=_BARRIER_TIMEOUT_S * 2)

        assert not errors, errors
        assert delivered == ["uncaptured"]
        assert recorded == []
