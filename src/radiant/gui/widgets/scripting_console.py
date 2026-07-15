"""The embedded scripting console — a global tool with live ``sensor`` / ``result``.

:class:`ScriptingConsole` is the MATLAB-style command window of the RADIANT GUI (arch doc
§2.5 Console row, §4.6 global-tool precedent; GUI plan Phase 8). It is a **global tool**,
not a per-stage tab: the window hosts it in a dockable :class:`QDockWidget` toggled from
**Tools → Python Console** (and the dock's View-menu toggle), mirroring the global
Inspector's wiring (§4.6). It embeds an interactive Python REPL whose namespace carries
live references to the GUI's objects:

* ``sensor``  — the window's live :class:`~radiant.api.sensor.Sensor` (the *same* object
  the parameter tree edits, so a ``sensor.set(...)`` in the console and an edit in the tree
  both mutate one object);
* ``result``  — the most recent :class:`~radiant.api.ChainResult` (refreshed after every
  evaluation);
* ``plot``    — ``ResultPlotNamespace(result)``, the public ``result.plot.*`` figure
  surface (``ChainResult`` carries no ``.plot`` property — Gap 87; the GUI builds the
  namespace exactly as :class:`~radiant.gui.widgets.matplotlib_canvas.MatplotlibCanvas`
  does, one GUI action ↔ one API call);
* ``inspect_result`` — the public :func:`radiant.api.inspect.inspect_result` convenience
  (``result.inspect()`` sugar does not exist — Gap 87).

**REPL vs qtconsole (CU-138).** The plan prefers a ``qtconsole`` in-process Jupyter kernel
(pinned in the ``gui`` extra) but explicitly sanctions a plain REPL over
:class:`code.InteractiveConsole` if qtconsole proves fragile or untestable offscreen. It is
both here (the module is not installed in this environment and an in-process kernel under
the ``offscreen`` QPA is hard to exercise headlessly), so this ships the sanctioned REPL
fallback — same live-object binding, fully testable offscreen. The decision is recorded as
**CU-138**.

**Figure behaviour.** A command that evaluates to a matplotlib ``Figure`` (e.g.
``plot.mtf()``) is **popped out into its own window** (a :class:`FigureCanvasQTAgg` in a
top-level :class:`QDialog`) rather than rendered inline — a dependency-light behaviour that
does not rely on an interactive matplotlib backend. The console keeps references to the
pop-out windows so they are not garbage-collected and closes them when it is destroyed.

**GUI ↔ console coherence (explicit, not magic).** A console command can mutate ``sensor``
behind the GUI's back. After such a command the console raises a visible **"console changed
state — Refresh"** banner and emits :attr:`stateMaybeChanged`; the one-click **Refresh**
button emits :attr:`refreshRequested`, which the window handles by *adopting* the console's
current ``sensor`` (this covers both in-place ``sensor.set(...)`` and a full rebind
``sensor = Sensor.load(...)``), re-reading it into the parameter tree + forms, and
re-evaluating. There is no magic live-sync (GUI plan Phase 8 — "explicit and honest beats
magic sync").

All colour/typography comes from the QSS theme (GUI plan §4.9); this file sets object names
only and holds no colour/font/size literal.
"""

from __future__ import annotations

import contextlib
import sys
from code import InteractiveConsole
from collections.abc import Callable
from typing import TYPE_CHECKING, Any, Final

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeyEvent, QTextCursor
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from radiant.api.inspect import ResultPlotNamespace, inspect_result

if TYPE_CHECKING:
    from matplotlib.figure import Figure

    from radiant.api import ChainResult
    from radiant.api.sensor import Sensor

_PROMPT: Final[str] = ">>> "
_CONT: Final[str] = "... "

# Minimum on-screen height (px) for the console. This is the floor that keeps a revealed
# console dock from collapsing to a zero/sliver height the operator cannot see — a failure
# observed when the bottom dock is revealed before layout on macOS/cocoa (owner report
# 2026-07-15). The window also resizes the dock to a larger target on reveal.
_CONSOLE_MIN_HEIGHT: Final[int] = 180

# A console command that mutates the live sensor makes the GUI stale. In-place mutation
# (a shared object) cannot be detected by identity, so the canonical mutation surface —
# ``sensor.set*`` and ``sensor.load`` (arch doc §3.1) — is detected in the command source;
# a full rebind is detected by object identity. See :meth:`_flag_if_mutated`.
_MUTATION_MARKERS: Final[tuple[str, ...]] = ("sensor.set", "sensor.load")

_BANNER: Final[str] = (
    "RADIANT scripting console — live  sensor  and  result  are bound.\n"
    "  result.snr            a metric with units\n"
    "  inspect_result(result)  the full variable dump (result.inspect() is Gap 87)\n"
    "  sensor.set('optics.aperture_diameter_m', 0.3)   then click Refresh\n"
    "  plot.mtf()            a figure — pops out into its own window\n"
)

_STALE_TEXT: Final[str] = "Console changed the sensor — the GUI is out of date."


class _ConsoleInput(QLineEdit):
    """The single-line REPL input, with Up/Down command-history navigation.

    Enter submits (via :attr:`~QLineEdit.returnPressed`); Up/Down request the previous/next
    history entry from the owning panel. Object name only — themed via QSS.
    """

    historyPrev = Signal()
    historyNext = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("consoleInput")

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802 (Qt override)
        if event.key() == Qt.Key.Key_Up:
            self.historyPrev.emit()
            return
        if event.key() == Qt.Key.Key_Down:
            self.historyNext.emit()
            return
        super().keyPressEvent(event)


class _LiveInteractiveConsole(InteractiveConsole):
    """An :class:`code.InteractiveConsole` whose ``write`` routes to a callback.

    Tracebacks and syntax errors the interpreter emits via ``write`` land in the console's
    output pane rather than the process stderr.
    """

    def __init__(self, namespace: dict[str, Any], write_cb: Callable[[str], None]) -> None:
        super().__init__(locals=namespace)
        self._write_cb = write_cb

    def write(self, data: str) -> None:  # noqa: D401 (Qt/console contract)
        self._write_cb(data)


class _StreamProxy:
    """A minimal file-like object forwarding ``write`` to a callback (stdout/stderr tee)."""

    def __init__(self, write_cb: Callable[[str], None]) -> None:
        self._write_cb = write_cb

    def write(self, data: str) -> int:
        self._write_cb(data)
        return len(data)

    def flush(self) -> None:  # pragma: no cover - nothing buffered
        return None


class ScriptingConsole(QWidget):
    """A dockable REPL panel with the live ``sensor`` / ``result`` bound (arch doc §2.5/§4.6).

    Parameters
    ----------
    parent:
        The owning widget, if any.

    Signals
    -------
    refreshRequested():
        The Refresh button was clicked — the window should adopt the console's current
        ``sensor`` and rebuild its views.
    stateMaybeChanged():
        A console command may have mutated ``sensor``; the window marks its state stale.
    figureProduced(object):
        A command evaluated to a matplotlib ``Figure`` (also popped out internally); emitted
        for observation/tests.
    commandExecuted(str):
        A full statement finished executing (emitted with its source); used by tests.
    """

    refreshRequested = Signal()
    stateMaybeChanged = Signal()
    figureProduced = Signal(object)
    commandExecuted = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("scriptingConsole")
        # Floor the height so a revealed console dock is always a visible panel, never a
        # zero/sliver strip (owner report 2026-07-15 — macOS/cocoa bottom-dock reveal).
        self.setMinimumHeight(_CONSOLE_MIN_HEIGHT)

        # Live-object namespace. `sensor`/`result`/`plot` are (re)bound by the window; the
        # convenience `inspect_result` is the public inspect surface (Gap 87 sugar), and
        # `Sensor` is bound so a script can rebind (`sensor = Sensor.load(...)`) — the
        # coherence model adopts whatever `sensor` becomes on Refresh.
        from radiant.api import Sensor

        self._namespace: dict[str, Any] = {
            "__name__": "__radiant_console__",
            "sensor": None,
            "result": None,
            "plot": None,
            "inspect_result": inspect_result,
            "Sensor": Sensor,
        }
        self._console = _LiveInteractiveConsole(self._namespace, self._append_text)

        # REPL state.
        self._pending: bool = False  # inside a multi-line block awaiting more input
        self._pending_source: list[str] = []
        self._stmt_before_sensor: Any = None  # sensor object before the current statement ran
        self._history: list[str] = []
        self._history_index: int = 0
        self._stale: bool = False

        # Pop-out figure windows (kept alive so they are not garbage-collected).
        self._figure_windows: list[QDialog] = []
        self._figures_produced: list[Figure] = []  # for tests

        self._build_ui()
        self._append_text(_BANNER)

    # -- construction -------------------------------------------------------

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        # Stale banner (hidden until a console command mutates the sensor).
        self._stale_banner = QFrame(self)
        self._stale_banner.setObjectName("consoleStaleBanner")
        banner_layout = QHBoxLayout(self._stale_banner)
        banner_layout.setContentsMargins(10, 6, 10, 6)
        banner_layout.setSpacing(10)
        banner_label = QLabel(_STALE_TEXT, self._stale_banner)
        banner_label.setObjectName("consoleStaleLabel")
        banner_label.setWordWrap(True)
        self._refresh_button = QPushButton("Refresh", self._stale_banner)
        self._refresh_button.setObjectName("consoleRefreshButton")
        self._refresh_button.clicked.connect(self.refreshRequested)
        banner_layout.addWidget(banner_label, 1)
        banner_layout.addWidget(self._refresh_button, 0)
        self._stale_banner.setVisible(False)
        layout.addWidget(self._stale_banner)

        # Output transcript (read-only).
        self._output = QPlainTextEdit(self)
        self._output.setObjectName("consoleOutput")
        self._output.setReadOnly(True)
        self._output.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        layout.addWidget(self._output, 1)

        # Input row: a prompt label + the single-line editor.
        input_row = QFrame(self)
        input_row.setObjectName("consoleInputRow")
        input_layout = QHBoxLayout(input_row)
        input_layout.setContentsMargins(0, 0, 0, 0)
        input_layout.setSpacing(6)
        self._prompt_label = QLabel(_PROMPT, input_row)
        self._prompt_label.setObjectName("consolePrompt")
        self._input = _ConsoleInput(input_row)
        self._input.returnPressed.connect(self._on_return_pressed)
        self._input.historyPrev.connect(self._history_prev)
        self._input.historyNext.connect(self._history_next)
        input_layout.addWidget(self._prompt_label, 0)
        input_layout.addWidget(self._input, 1)
        layout.addWidget(input_row)

    # -- public accessors ---------------------------------------------------

    @property
    def output(self) -> QPlainTextEdit:
        """The read-only transcript pane."""
        return self._output

    @property
    def input_box(self) -> _ConsoleInput:
        """The single-line REPL input editor."""
        return self._input

    @property
    def stale_banner(self) -> QFrame:
        """The 'console changed state — Refresh' banner (hidden until stale)."""
        return self._stale_banner

    @property
    def refresh_button(self) -> QPushButton:
        """The Refresh button inside the stale banner."""
        return self._refresh_button

    def is_stale(self) -> bool:
        """True once a console command has (maybe) mutated the sensor, until refreshed."""
        return self._stale

    def output_text(self) -> str:
        """The full transcript text (for tests)."""
        return self._output.toPlainText()

    def namespace_sensor(self) -> Sensor | None:
        """The ``sensor`` currently bound in the console namespace (post-mutation-aware)."""
        return self._namespace.get("sensor")

    def figures_produced(self) -> list[Figure]:
        """The matplotlib figures the console has popped out (for tests)."""
        return list(self._figures_produced)

    # -- live-object binding (called by the window) -------------------------

    def bind_sensor(self, sensor: Sensor | None) -> None:
        """Bind the window's live ``sensor`` into the namespace (on load / config swap)."""
        self._namespace["sensor"] = sensor

    def update_result(self, result: ChainResult | None) -> None:
        """Bind the latest ``result`` (and its ``plot`` surface) and clear the stale flag.

        A fresh evaluation means the GUI and the console now agree, so the stale banner is
        cleared. The ``plot`` convenience is ``ResultPlotNamespace(result)`` — the same
        public figure surface the embedded canvas uses (one GUI action ↔ one API call).
        """
        self._namespace["result"] = result
        self._namespace["plot"] = ResultPlotNamespace(result) if result is not None else None
        self.set_stale(False)

    # -- coherence ----------------------------------------------------------

    def set_stale(self, stale: bool) -> None:
        """Show/hide the stale banner and emit :attr:`stateMaybeChanged` on a rising edge."""
        rising = stale and not self._stale
        self._stale = stale
        self._stale_banner.setVisible(stale)
        if rising:
            self.stateMaybeChanged.emit()

    # -- REPL execution -----------------------------------------------------

    def run_command(self, source: str) -> None:
        """Execute *source* as if typed at the prompt (one or more lines; for tests too)."""
        for line in source.splitlines() or [""]:
            self._run_line(line)

    def _on_return_pressed(self) -> None:
        line = self._input.text()
        self._input.clear()
        if line.strip():
            self._history.append(line)
        self._history_index = len(self._history)
        self._run_line(line)

    def _run_line(self, line: str) -> None:
        """Echo, push one line to the interpreter, and handle continuation + coherence."""
        # Echo the line with the active prompt so the transcript reads like a session.
        self._append_text((_CONT if self._pending else _PROMPT) + line + "\n")

        if not self._pending:
            # Starting a fresh statement — snapshot the sensor to detect a rebind.
            self._stmt_before_sensor = self._namespace.get("sensor")
        self._pending_source.append(line)

        with self._captured_io():
            try:
                more = self._console.push(line)
            except SystemExit:
                # Never let a console `exit()`/`quit()` tear down the GUI process.
                self._append_text("(SystemExit ignored inside the embedded console)\n")
                more = False
                self._console.resetbuffer()

        if more:
            self._pending = True
            self._prompt_label.setText(_CONT)
            return

        # A full statement executed.
        self._pending = False
        self._prompt_label.setText(_PROMPT)
        source = "\n".join(self._pending_source)
        self._pending_source.clear()
        self._flag_if_mutated(source)
        self.commandExecuted.emit(source)

    @contextlib.contextmanager
    def _captured_io(self) -> Any:
        """Redirect stdout/stderr and the display hook into the console for one push."""
        import builtins

        old_stdout, old_stderr, old_hook = sys.stdout, sys.stderr, sys.displayhook
        proxy = _StreamProxy(self._append_text)
        sys.stdout = proxy  # type: ignore[assignment]
        sys.stderr = proxy  # type: ignore[assignment]
        sys.displayhook = self._displayhook
        try:
            yield
        finally:
            sys.stdout, sys.stderr, sys.displayhook = old_stdout, old_stderr, old_hook
            builtins._ = self._namespace.get("_")  # keep `_` reachable in the namespace too

    def _displayhook(self, value: Any) -> None:
        """Interactive display hook: pop out figures, else print the value's repr.

        Mirrors the standard hook (``None`` is silent; the value is bound to ``_``) but
        routes a matplotlib ``Figure`` to a pop-out window instead of printing an opaque
        ``<Figure …>`` repr into the transcript.
        """
        if value is None:
            return
        self._namespace["_"] = value
        if _is_figure(value):
            self._pop_out_figure(value)
            self._append_text("<figure opened in its own window>\n")
            return
        self._append_text(repr(value) + "\n")

    def _flag_if_mutated(self, source: str) -> None:
        """Raise the stale banner if the just-run command (maybe) mutated the sensor.

        Detection is honest, not magic: a full rebind (``sensor = …``) is caught by object
        identity; an in-place ``sensor.set*`` / ``sensor.load`` (a shared object, no identity
        change) is caught in the source text (arch doc §3.1 mutation surface). Reads never
        flag; the Refresh button is the always-available escape hatch regardless.
        """
        after = self._namespace.get("sensor")
        rebound = after is not self._stmt_before_sensor
        mutating_call = any(marker in source for marker in _MUTATION_MARKERS)
        if after is not None and (rebound or mutating_call):
            self.set_stale(True)

    # -- figure pop-out -----------------------------------------------------

    def _pop_out_figure(self, figure: Figure) -> None:
        """Show *figure* in its own top-level window, keeping a reference to it alive."""
        from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg

        window = QDialog(self)
        window.setObjectName("consoleFigureWindow")
        window.setWindowTitle("RADIANT — console figure")
        window.setModal(False)
        layout = QVBoxLayout(window)
        layout.setContentsMargins(0, 0, 0, 0)
        canvas = FigureCanvasQTAgg(figure)
        layout.addWidget(canvas)
        window.resize(640, 480)
        window.show()
        canvas.draw_idle()
        self._figure_windows.append(window)
        self._figures_produced.append(figure)
        self.figureProduced.emit(figure)

    # -- history ------------------------------------------------------------

    def _history_prev(self) -> None:
        if not self._history:
            return
        self._history_index = max(0, self._history_index - 1)
        self._input.setText(self._history[self._history_index])

    def _history_next(self) -> None:
        if not self._history:
            return
        self._history_index = min(len(self._history), self._history_index + 1)
        if self._history_index == len(self._history):
            self._input.clear()
        else:
            self._input.setText(self._history[self._history_index])

    # -- output -------------------------------------------------------------

    def _append_text(self, text: str) -> None:
        """Insert *text* verbatim at the end of the transcript and scroll into view."""
        cursor = self._output.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.insertText(text)
        self._output.setTextCursor(cursor)
        self._output.ensureCursorVisible()

    # -- teardown -----------------------------------------------------------

    def closeEvent(self, event: Any) -> None:  # noqa: N802 (Qt override)
        """Close any pop-out figure windows so app exit with the console open is clean."""
        for window in self._figure_windows:
            with contextlib.suppress(RuntimeError):
                window.close()
        self._figure_windows.clear()
        super().closeEvent(event)


def _is_figure(value: Any) -> bool:
    """True if *value* is a matplotlib ``Figure`` (lazy import; matplotlib is the gui extra)."""
    try:
        from matplotlib.figure import Figure
    except ImportError:  # pragma: no cover - matplotlib ships with the gui extra
        return False
    return isinstance(value, Figure)


__all__ = ["ScriptingConsole"]
