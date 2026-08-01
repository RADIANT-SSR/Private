"""Thread-local warning capture — each thread records only the warnings it raised.

Why this module exists (CU-110)
-------------------------------
``warnings.catch_warnings(record=True)`` is the obvious way to collect the
warnings one evaluation raised, and it is what
:meth:`radiant.api.config_set.ConfigurationSet._evaluate_one` used to do. It has
one property that only bites in a threaded process: its capture list is
**process-global**. ``warnings.showwarning`` is a module attribute, so while a
capture window is open *every* thread's warnings land in *that* window's list —
and they land there silently, because the window also swallows them out of the
default handler. Two RADIANT worker threads (the main window's evaluation worker
plus any of the sweep / solve / evaluate-all dialog workers, none of which are
serialized against it) therefore either cross-attribute their warnings or lose
them entirely.

What this module provides instead
---------------------------------
:func:`capture_warnings` is a context manager with the same shape as
``catch_warnings(record=True)`` — it yields a list that fills with
:class:`warnings.WarningMessage` records — but the list is bound to the
**calling thread**:

* A warning raised on a thread that has an open capture is appended to that
  thread's innermost list (captures nest).
* A warning raised on a thread with **no** open capture is forwarded to the
  ``showwarning`` handler that was in place before any capture was installed,
  so it still reaches the user (Rule 17: nothing is swallowed). This is
  strictly better than the ``catch_warnings`` behaviour it replaces, which
  quietly ate such a warning into an unrelated thread's window.

The one piece of global state that remains is the **filter**: while any capture
is open the process filter is ``simplefilter("always")``, exactly as the
``catch_warnings`` window set it. That is deliberate and cannot be made
thread-local — CPython has no per-thread warning filters, and the "always"
action is what makes the capture independent of the ambient filter state
(nothing is deduplicated away by the once-per-location ``__warningregistry__``,
and an ambient ``filterwarnings=error`` cannot convert a chain warning into an
exception inside the window). The difference from ``catch_warnings`` is that
this mutation is now **reference-counted under a lock**: concurrent captures all
want the same "always" state, the first one installs it and the last one
restores it, so one thread's exit can no longer clobber another thread's filter
state. That was CU-110's actual defect.

The saved filter/handler pair is held in a single :class:`warnings.catch_warnings`
object entered on install and exited on uninstall (public API — no reach into
``warnings`` internals). It is not thread-affine: entering on one thread and
exiting on another restores exactly the state that was saved.
"""

from __future__ import annotations

import threading
import warnings
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import TextIO

__all__ = ["capture_warnings"]

#: The ``warnings.showwarning`` signature, spelled once so the dispatcher and the
#: saved fallback handler are typed identically.
ShowWarning = Callable[[Warning | str, type[Warning], str, int, TextIO | None, str | None], None]

# Per-thread stack of open capture lists; the innermost one receives records.
_local = threading.local()

# Guards the install/uninstall transition and the three globals below it.
_install_lock = threading.Lock()

# How many captures are currently open across all threads.
_open_captures = 0

# The saved-state holder, live only while ``_open_captures > 0``.
_saved: warnings.catch_warnings | None = None

# The ``showwarning`` handler in place before the first capture installed ours —
# where a warning from a thread with no open capture is sent. Written on the
# 0 -> 1 install transition and deliberately NOT cleared on uninstall: the
# dispatcher is only ever reachable after an install has set it, and keeping the
# last-known-good handler removes any window in which a warning could arrive with
# nowhere to go.
_fallback_showwarning: ShowWarning = warnings.showwarning


def _thread_stack() -> list[list[warnings.WarningMessage]]:
    """This thread's stack of open capture lists (created on first use)."""
    stack: list[list[warnings.WarningMessage]] | None = getattr(_local, "stack", None)
    if stack is None:
        stack = []
        _local.stack = stack
    return stack


def _dispatch(
    message: Warning | str,
    category: type[Warning],
    filename: str,
    lineno: int,
    file: TextIO | None = None,
    line: str | None = None,
) -> None:
    """Route one warning to this thread's capture, or to the pre-capture handler.

    Installed as ``warnings.showwarning`` while at least one capture is open.
    The thread that raised the warning decides where it goes, which is the
    whole point: a worker records its own warnings and nobody else's, and a
    thread that is not capturing keeps the default behaviour rather than
    donating its warning to somebody else's list.
    """
    stack = _thread_stack()
    if stack:
        stack[-1].append(warnings.WarningMessage(message, category, filename, lineno, file, line))
        return
    _fallback_showwarning(message, category, filename, lineno, file, line)


def _install() -> None:
    """Reference-counted install of the "always" filter + the dispatch handler."""
    global _open_captures, _saved, _fallback_showwarning
    with _install_lock:
        if _open_captures == 0:
            saved = warnings.catch_warnings()
            saved.__enter__()
            _saved = saved
            _fallback_showwarning = warnings.showwarning
            warnings.simplefilter("always")
            warnings.showwarning = _dispatch
        _open_captures += 1


def _uninstall() -> None:
    """Reference-counted restore of whatever filter/handler preceded the first capture."""
    global _open_captures, _saved
    with _install_lock:
        _open_captures -= 1
        if _open_captures == 0:
            saved, _saved = _saved, None
            if saved is not None:
                saved.__exit__(None, None, None)


@contextmanager
def capture_warnings() -> Iterator[list[warnings.WarningMessage]]:
    """Record the warnings raised **on this thread** inside the ``with`` block.

    Drop-in replacement for ``warnings.catch_warnings(record=True)`` plus
    ``simplefilter("always")``, differing only in that the yielded list is
    thread-local: another thread's warnings never appear in it, and a warning
    raised on a thread with no capture open still reaches the pre-capture
    ``showwarning`` handler instead of being swallowed here (Rule 17).

    Yields
    ------
    list[warnings.WarningMessage]
        Filled in raise order while the block runs; complete on exit.
    """
    records: list[warnings.WarningMessage] = []
    _install()
    stack = _thread_stack()
    stack.append(records)
    try:
        yield records
    finally:
        stack.pop()
        _uninstall()
