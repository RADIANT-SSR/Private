"""The RADIANT main application window.

:class:`RADIANTMainWindow` lays out the top-level chrome described in
``RADIANT_GUI_Architecture.md`` §4 (contextual per-stage workspace, owner-ratified
2026-07-13): the menu bar (§10) with the global **Inspector** tool (§4.6), the 9-stage
geometry-first signal-chain strip (§4.2, the single primary navigation), the permanent
left parameter dock (§4.3), the central per-stage contextual view (§4.4), the persistent
right rail (Pinned / Edit Config / Messages, §4.5), and the status bar.

The signal-chain strip carries 9 stage chips with live health dots; clicking a stage
navigates the left tree and swaps the center to **that stage's contextual composite**
(its outputs, plot(s), and relocated detail content, §4.4). The full ``result.inspect()``
variable dump is the global Inspector tool (§4.6), not a docked panel. The bottom detail
tabs of the earlier layout are dissolved into the per-stage center and the Inspector
(§4.7); nothing is discarded, only relocated. Styling comes entirely from the
design-system QSS theme in :mod:`radiant.gui.themes`; this module sets structure and
object names only.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING, Any

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QAction, QKeySequence, QUndoStack
from PySide6.QtWidgets import (
    QApplication,
    QDockWidget,
    QFileDialog,
    QInputDialog,
    QMainWindow,
    QMenu,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QWidget,
)

from radiant.api.build_info import build_info
from radiant.api.sensor import Sensor
from radiant.core.exceptions import RadiantError
from radiant.gui.geometry_modes import implicated_families
from radiant.gui.param_format import format_value
from radiant.gui.settings_store import SettingsStore
from radiant.gui.themes import DARK, LIGHT, active_theme, apply_theme
from radiant.gui.widgets.actionable_error_dialog import ActionableErrorDialog
from radiant.gui.widgets.central_canvas import CentralCanvas
from radiant.gui.widgets.explain_dialog import ExplainDialog
from radiant.gui.widgets.inspector_dialog import InspectorDialog
from radiant.gui.widgets.parameter_panel import ParameterPanel
from radiant.gui.widgets.right_rail import RightRail
from radiant.gui.widgets.schema_browser_dialog import SchemaBrowserDialog
from radiant.gui.widgets.scripting_console import ScriptingConsole
from radiant.gui.widgets.scripting_window import ScriptingWindow
from radiant.gui.widgets.set_parameter_command import SetParameterCommand
from radiant.gui.widgets.stage_strip import STAGE_NAMESPACES, StageStrip
from radiant.gui.widgets.sweep_dialog import SweepDialog
from radiant.gui.widgets.unexpected_error_dialog import UnexpectedErrorDialog
from radiant.gui.widgets.yaml_editor_dialog import YamlEditorDialog
from radiant.gui.workers import EvaluationWorker


@lru_cache(maxsize=1)
def _build_label() -> str:
    """The running package's ``vX.Y.Z (+sha)`` label for the window title.

    Cached: :func:`build_info` shells out to git, and the title is recomposed on every
    dirty toggle / file change, so it is resolved exactly once per process.
    """
    return build_info().one_line()


if TYPE_CHECKING:
    from radiant.api import ChainResult

# Re-evaluation debounce window (arch doc §3.3): parameter edits within this
# window coalesce into a single full-chain run.
_DEBOUNCE_MS: int = 200

# Default window geometry and dock proportions, matching the mockup's balance
# (1440×900 with a ~360 px parameter dock and a ~260 px detail dock). The
# parameter dock is wide enough that a typical `sensor.*`/`target.*` leaf name
# reads in full at first launch — the Task-2A checkpoint flagged 300 px as
# truncating "sens…"/"targe…"; the stretchy Parameter column now has room.
_DEFAULT_WIDTH: int = 1440
_DEFAULT_HEIGHT: int = 900
_PARAM_DOCK_WIDTH: int = 360
_RAIL_DOCK_WIDTH: int = 288

# Undo/redo depth (arch doc §10, GUI plan Phase 9): the last ~20 parameter edits are
# reversible; older commands fall off the bottom of the stack.
_UNDO_LIMIT: int = 20

# The RADIANT config file filter for the Open / Save-As dialogs.
_YAML_FILTER: str = "RADIANT config (*.yaml *.yml);;All files (*)"


class RADIANTMainWindow(QMainWindow):
    """Top-level RADIANT GUI window with the Phase 3 evaluate loop wired in.

    The window opens on a :class:`~radiant.api.sensor.Sensor` (or empty). When a
    sensor is loaded, Evaluate (F5 / the Run button) runs the full chain on a
    worker thread (arch doc §3.2 — the GUI thread never runs the chain), and a
    parameter edit auto-re-evaluates after a 200 ms debounce (§3.3). Results fill
    the metric badges and the central plot; a failed evaluation leaves the previous
    result displayed with a visible stale state and shows the actionable error.

    Parameters
    ----------
    sensor:
        The :class:`~radiant.api.sensor.Sensor` the window opens on, or ``None``
        for an empty window.

    Signals
    -------
    evaluationFinished(object):
        Emitted after each evaluation attempt completes (success or failure), with
        the current :class:`~radiant.api.ChainResult` (or the previous one on
        failure, ``None`` if none yet). Tests use it to await the worker without
        sleeps.
    """

    evaluationFinished = Signal(object)

    def __init__(
        self,
        sensor: Sensor | None = None,
        *,
        path: str | None = None,
        settings: SettingsStore | None = None,
    ) -> None:
        super().__init__()
        self._sensor = sensor
        # Registry of every menu action by a stable key, so tests and later
        # phases can look one up without walking the menu tree.
        self._actions: dict[str, QAction] = {}

        # File-round-trip state (Phase 9): the config path the current sensor was
        # loaded from / last saved to (None → unsaved), and whether it carries
        # unsaved edits (the title's dirty marker). Preferences (recent files,
        # theme, panel state) persist through the injected settings store.
        self._settings: SettingsStore = settings if settings is not None else SettingsStore()
        self._current_path: Path | None = Path(path) if path else None
        self._dirty: bool = False

        # Undo/redo (Phase 9): a bounded stack of reversible parameter edits, plus a
        # snapshot of the committed input values so an edit's before-value is known
        # when the panel signals it (the signal fires after the set is applied).
        self._undo_stack = QUndoStack(self)
        self._undo_stack.setUndoLimit(_UNDO_LIMIT)
        self._input_snapshot: dict[str, Any] = {}

        # Evaluate-loop state (Phase 3): the in-flight worker, a coalescing flag
        # for edits that land mid-run, the most recent result, and a count of
        # completed evaluations (the debounce test asserts on it).
        self._worker: EvaluationWorker | None = None
        self._rerun_pending: bool = False
        self._last_result: ChainResult | None = None
        # GT-1: the last completed sweep (SweepResult | Sweep2DResult), for export.
        self.last_sweep_result: object | None = None
        self._evaluation_count: int = 0

        self.setObjectName("radiantMainWindow")
        self.setWindowTitle(self._compose_title())
        self.resize(_DEFAULT_WIDTH, _DEFAULT_HEIGHT)

        self._build_menu_bar()
        self._build_stage_strip()
        self._build_central_area()
        self._build_dock_panels()
        self._build_scripting_window()
        self._build_status_bar()
        self._apply_dock_proportions()
        self._wire_evaluate_loop()
        self._wire_file_menu()
        self._wire_edit_menu()
        self._wire_view_menu()
        # Custom-painted widgets read a stored theme, so a launch in the persisted
        # (possibly dark) theme must be pushed to them once the tree is built.
        self._central.stage_center.set_theme(active_theme())

        # Auto-evaluate once on load so the badges and plot populate immediately
        # (the D2 checkpoint opens on a filled dashboard). Deferred to the event
        # loop so the worker's signals are delivered after the window is shown.
        if self._sensor is not None:
            if self._current_path is not None:
                self._settings.add_recent_file(str(self._current_path))
                self._rebuild_recent_menu()
            if self._sensor_can_resolve(self._sensor):
                QTimer.singleShot(0, self._evaluate_now)
            else:
                # From-scratch launch (owner report 2026-07-17): an incomplete config
                # opens editable with guidance — never an auto-evaluate into a modal.
                self.statusBar().showMessage(
                    "Configuration incomplete — set required parameters, then Evaluate "
                    "(F5) to see what is still missing"
                )

    # -- public accessors ---------------------------------------------------

    @property
    def sensor(self) -> Sensor | None:
        """The sensor this window was opened on (``None`` if none)."""
        return self._sensor

    @property
    def stage_strip(self) -> StageStrip:
        """The 9-stage signal-chain strip (static in Phase 1)."""
        return self._stage_strip

    @property
    def central_canvas(self) -> CentralCanvas:
        """The central KPI-row-plus-plot canvas (static in Phase 1)."""
        return self._central

    @property
    def parameter_panel(self) -> ParameterPanel:
        """The parameter dock body: filter box + schema-driven tree (Phase 2 Task A)."""
        return self._parameter_panel

    @property
    def right_rail(self) -> RightRail:
        """The persistent right rail: Pinned cards / Edit Config (YAML) / Messages (§4.5)."""
        return self._right_rail

    @property
    def console(self) -> ScriptingConsole:
        """The scripting window's Command Window REPL (global tool, arch doc §4.6.1)."""
        return self._console

    @property
    def scripting_window(self) -> ScriptingWindow:
        """The separate top-level scripting window (Command Window + Workspace, §4.6.1)."""
        return self._scripting_window

    def action(self, key: str) -> QAction:
        """Return the menu :class:`QAction` registered under *key*.

        Keys are ``"<menu>.<slug>"`` (e.g. ``"file.quit"``, ``"run.evaluate"``).
        Raises :class:`KeyError` if the action does not exist — a programmer
        error, not user input, so a bare ``KeyError`` is correct here.
        """
        return self._actions[key]

    # -- construction helpers ----------------------------------------------

    def _compose_title(self) -> str:
        """Window title: ``[*] <file> — RADIANT`` (arch doc §10 / GUI plan Phase 9).

        With no sensor the title is the bare app name. A loaded/saved config shows its
        base file name; a sensor with no file yet (the script hand-off or File → New)
        shows ``untitled``. A leading ``*`` marks unsaved edits (the dirty marker), so
        the operator always sees whether the on-screen config matches the file on disk.
        """
        # The build label (version + git SHA) makes a stale/wrong install visible at a
        # glance — the provenance the Windows first-deploy report needed (WS-A3).
        suffix = f"RADIANT {_build_label()}"
        if self._sensor is None:
            return suffix
        name = self._current_path.name if self._current_path is not None else "untitled"
        marker = "* " if self._dirty else ""
        return f"{marker}{name} — {suffix}"

    def _add_action(
        self,
        menu: QMenu,
        key: str,
        text: str,
        *,
        enabled: bool,
        shortcut: QKeySequence.StandardKey | str | None = None,
    ) -> QAction:
        """Create, register, and add an action to *menu*.

        Every action is *present*; ``enabled`` gates whether it is clickable.
        Phase 1 enables only the actions it actually implements (Quit); the rest
        are visible-but-disabled so the menu reads as the full v1 surface while
        signalling what is not wired yet (arch doc §10).
        """
        action = QAction(text, self)
        if shortcut is not None:
            action.setShortcut(shortcut)
        action.setEnabled(enabled)
        menu.addAction(action)
        self._actions[key] = action
        return action

    def _build_menu_bar(self) -> None:
        """Populate File/Edit/View/Run/Tools/Help per arch doc §10.

        All actions are created; only those Phase 1 implements are enabled.
        """
        bar = self.menuBar()

        file_menu = bar.addMenu("&File")
        self._add_action(file_menu, "file.new", "New", enabled=False)
        self._add_action(
            file_menu,
            "file.open",
            "Open YAML…",
            enabled=False,
            shortcut=QKeySequence.StandardKey.Open,
        )
        # Open Recent is a live submenu, rebuilt from the persisted recent-files list
        # (QSettings, Phase 9). Disabled while the list is empty (nothing to reopen).
        self._recent_menu = file_menu.addMenu("Open Recent")
        self._recent_menu.setEnabled(False)
        self._add_action(
            file_menu, "file.save", "Save", enabled=False, shortcut=QKeySequence.StandardKey.Save
        )
        self._add_action(file_menu, "file.save_as", "Save As…", enabled=False)
        self._add_action(file_menu, "file.export_yaml", "Export YAML…", enabled=False)
        self._add_action(file_menu, "file.export_json", "Export JSON Result…", enabled=False)
        self._add_action(
            file_menu, "file.export_resolved_yaml", "Export Resolved YAML…", enabled=False
        )
        self._add_action(file_menu, "file.export_metrics_csv", "Export Metrics CSV…", enabled=False)
        self._add_action(file_menu, "file.export_sweep_csv", "Export Sweep CSV…", enabled=False)
        self._add_action(file_menu, "file.export_xlsx", "Export XLSX Workbook…", enabled=False)
        file_menu.addSeparator()
        quit_action = self._add_action(
            file_menu, "file.quit", "Quit", enabled=True, shortcut=QKeySequence.StandardKey.Quit
        )
        # Quit is the one Phase 1 action with behaviour: close the window cleanly.
        quit_action.triggered.connect(self.close)

        edit_menu = bar.addMenu("&Edit")
        self._add_action(
            edit_menu, "edit.undo", "Undo", enabled=False, shortcut=QKeySequence.StandardKey.Undo
        )
        self._add_action(
            edit_menu, "edit.redo", "Redo", enabled=False, shortcut=QKeySequence.StandardKey.Redo
        )
        self._add_action(edit_menu, "edit.reset_defaults", "Reset to Defaults", enabled=False)
        self._add_action(
            edit_menu,
            "edit.find",
            "Find Parameter",
            enabled=False,
            shortcut=QKeySequence.StandardKey.Find,
        )

        view_menu = bar.addMenu("&View")
        self._view_menu = view_menu
        self._add_action(
            view_menu,
            "view.toggle_params",
            "Show/Hide Parameter Panel",
            enabled=False,
            shortcut="F6",
        )
        self._add_action(view_menu, "view.theme", "Dark/Light Theme", enabled=False)
        self._add_action(view_menu, "view.font_larger", "Font Size +", enabled=False)
        self._add_action(view_menu, "view.font_smaller", "Font Size −", enabled=False)

        run_menu = bar.addMenu("&Run")
        evaluate_action = self._add_action(
            run_menu, "run.evaluate", "Evaluate", enabled=False, shortcut="F5"
        )
        # CU-142: a bare F5 needs the Fn modifier on stock macOS (top-row keys default
        # to hardware functions), so the app's most-used action would be unreachable by
        # keyboard there. Add a reachable chord alternate — Ctrl+Return maps to
        # ⌘+Return on macOS and Ctrl+Return on Windows/Linux — while keeping the
        # familiar F5=Run convention. (Ctrl+R is already bound to Validate Only.)
        evaluate_action.setShortcuts([QKeySequence("F5"), QKeySequence("Ctrl+Return")])
        self._add_action(
            run_menu, "run.validate", "Validate Only", enabled=False, shortcut="Ctrl+R"
        )
        run_menu.addSeparator()
        self._add_action(run_menu, "run.sweep", "Run Sweep…", enabled=False)
        self._add_action(run_menu, "run.monte_carlo", "Monte Carlo…", enabled=False)
        self._add_action(run_menu, "run.batch", "Batch Run…", enabled=False)

        tools_menu = bar.addMenu("&Tools")
        # The global Inspector (arch doc §4.6) — the full result.inspect() variable dump.
        # Disabled until the first result exists (nothing to dump); enabled in _on_eval_ok.
        inspector_action = self._add_action(
            tools_menu, "tools.inspector", "Inspector", enabled=False, shortcut="Ctrl+I"
        )
        inspector_action.triggered.connect(self._open_inspector)
        tools_menu.addSeparator()
        # The separate scripting window (arch doc §4.6.1) — the MATLAB-style Command Window +
        # Workspace, a global tool like the Inspector. Disabled until a sensor is loaded
        # (nothing to bind); enabled in _wire_evaluate_loop. Its trigger shows/raises the one
        # window instance (built later in __init__). Shortcut is Ctrl+Shift+P (⌘⇧P on macOS)
        # — deliberately NOT the older Ctrl+` : Qt maps portable "Ctrl" to the macOS Command
        # key, so Ctrl+` became ⌘`, an OS-reserved shortcut (cycle windows of the active app)
        # that never reached the app, so the console "wouldn't open" on macOS (owner report
        # 2026-07-15). ⌘⇧P is unreserved on macOS and free on Windows/Linux, and collides with
        # no other RADIANT binding (Ctrl+I, Ctrl+Z/Ctrl+Shift+Z, F5/F6/F7, Ctrl+1..9,
        # Ctrl+O/S/Q/F/R).
        scripting_action = self._add_action(
            tools_menu,
            "tools.scripting_window",
            "Scripting Window",
            enabled=False,
            shortcut="Ctrl+Shift+P",
        )
        scripting_action.setStatusTip(
            "Open the scripting window — command line + workspace (Ctrl+Shift+P)"
        )
        scripting_action.triggered.connect(self._show_scripting_window)
        self._add_action(tools_menu, "tools.schema", "Parameter Schema Browser", enabled=False)
        self._add_action(tools_menu, "tools.compare", "Compare Configurations…", enabled=False)
        self._add_action(tools_menu, "tools.mtf_overlay", "Compare Measured MTF…", enabled=False)
        self._add_action(tools_menu, "tools.solve", "Solve for Parameter…", enabled=False)
        self._add_action(tools_menu, "tools.explain", "Explain Parameter…", enabled=False)
        self._add_action(tools_menu, "tools.preferences", "Preferences…", enabled=False)

        help_menu = bar.addMenu("&Help")
        self._add_action(help_menu, "help.docs", "Documentation", enabled=False)
        self._add_action(help_menu, "help.examples", "Example Configs", enabled=False)
        self._add_action(help_menu, "help.about", "About RADIANT", enabled=False)

        # The wireframe's right-aligned "◈ Inspector" menu-bar affordance: a corner button
        # that triggers the same Tools → Inspector action (§4.1 menu bar). It shares the
        # action's enabled state, so it greys out pre-evaluate too.
        inspector_button = QPushButton("◈ Inspector", bar)
        inspector_button.setObjectName("inspectorMenuButton")
        inspector_button.setFlat(True)
        inspector_button.setEnabled(False)
        inspector_button.clicked.connect(self._open_inspector)
        bar.setCornerWidget(inspector_button, Qt.Corner.TopRightCorner)
        self._inspector_button = inspector_button

    def _build_stage_strip(self) -> None:
        """The clickable 9-stage signal-chain strip with live health dots (Phase 4).

        The :class:`StageStrip` renders the nine chips; a click emits the stage's real
        schema namespace, which navigates the parameter panel and swaps the canvas to
        that stage's default visualization (navigation only, no API call). The dots are
        driven live from the last run's health (:meth:`_on_eval_ok` / ``_failed`` /
        ``_on_parameter_edited``).
        """
        strip = StageStrip(self)
        strip.stageClicked.connect(self._on_stage_selected)
        self._stage_strip = strip

        # Docked at the top as a thin, non-floatable, non-closable band.
        dock = QDockWidget("", self)
        dock.setObjectName("stageStripDock")
        dock.setTitleBarWidget(QWidget(dock))  # hide the dock title bar
        dock.setFeatures(QDockWidget.DockWidgetFeature.NoDockWidgetFeatures)
        dock.setWidget(strip)
        self.addDockWidget(Qt.DockWidgetArea.TopDockWidgetArea, dock)
        self._stage_strip_dock = dock

    def _build_central_area(self) -> None:
        """The central canvas: KPI badge row above the plot placeholder (§4.4).

        Phase 3 fills the badges and swaps the placeholder for the matplotlib canvas.
        """
        central = CentralCanvas(self)
        self.setCentralWidget(central)
        self._central = central

    def _build_dock_panels(self) -> None:
        """Parameter (left) dock and the persistent right rail (§4.3, §4.5).

        The parameter dock holds the searchable schema-driven tree
        (:class:`ParameterPanel`); the right rail holds the Pinned cards, the Edit Config
        (YAML) button, and the Messages panel. The bottom detail dock of the earlier layout
        is gone — its tabs dissolved into the per-stage center and the Inspector (§4.7).
        """
        param_panel = ParameterPanel(self)
        # Populate the editable tree from the live sensor (GUI plan Phase 2);
        # None (bare launch) leaves the themed "no configuration loaded" state.
        param_panel.populate(self._sensor)
        # An accepted parameter edit means downstream results are out of date.
        # Phase 3 wires the re-evaluate loop; for now surface the stale state in
        # the status bar (the stage-strip dots are already stale pre-evaluate).
        param_panel.parameterEdited.connect(self._on_parameter_edited)
        param_dock = QDockWidget("Parameters", self)
        param_dock.setObjectName("parameterDock")
        param_dock.setWidget(param_panel)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, param_dock)
        self._parameter_dock = param_dock
        self._parameter_panel = param_panel

        # Right rail (arch doc §4.5): a persistent, full-height right column carrying
        # the Pinned metric cards, the Edit Config (YAML) button, and the Messages
        # panel. The rail owns no sensor, so its Edit Config click is surfaced and the
        # window opens the editor against the live sensor.
        right_rail = RightRail(self)
        right_rail.editConfigRequested.connect(self._on_edit_config_requested)
        rail_dock = QDockWidget("", self)
        rail_dock.setObjectName("rightRailDock")
        rail_dock.setTitleBarWidget(QWidget(rail_dock))  # hide the dock title bar
        rail_dock.setFeatures(QDockWidget.DockWidgetFeature.NoDockWidgetFeatures)
        # The rail must stay readable at small window sizes (owner report
        # 2026-07-17: pinned values clipped mid-glyph when not fullscreen) — give
        # the dock a floor instead of letting Qt squeeze it arbitrarily.
        right_rail.setMinimumWidth(240)
        rail_dock.setWidget(right_rail)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, rail_dock)
        self._right_rail_dock = rail_dock
        self._right_rail = right_rail

        # Pin affordances on the per-stage center's Outputs / Metrics rows route into the
        # rail's Pinned panel (arch doc §4.5, CU-115 Step-B): a stage-output value re-reads
        # from stage_outputs on each run; a metric pins from the metric surface.
        stage_center = self._central.stage_center
        stage_center.pinOutputRequested.connect(right_rail.pinned.pin_stage_output)
        stage_center.pinMetricRequested.connect(right_rail.pinned.pin)
        # Bind the live sensor + the panel's shared display-unit store into the per-stage
        # input forms (Geometry, GUI plan Phase 5); an edit made in a form re-evaluates and
        # refreshes the tree exactly like a tree edit.
        stage_center.bind_sensor(self._sensor, param_panel.display_units)
        stage_center.parameterEdited.connect(self._on_form_parameter_edited)
        stage_center.compoundParameterEdited.connect(self._on_compound_parameter_edited)

    def _build_scripting_window(self) -> None:
        """Build the separate scripting window (Command Window + Workspace, arch doc §4.6.1).

        The window is a :class:`~radiant.gui.widgets.scripting_window.ScriptingWindow` — a
        real separate top-level window (not a dock), hidden until launched from **Tools →
        Scripting Window**. Its Command Window's namespace is bound to the live ``sensor``
        here; ``result`` is bound after each evaluation (:meth:`_on_eval_ok`). The coherence
        wiring is unchanged from the retired dock: a console mutation raises the console's
        stale banner and marks the window stale (:meth:`_on_console_state_changed`); the
        Refresh button drives :meth:`_refresh_from_console` (explicit-and-honest, not magic
        sync). A single instance is kept, so re-launching raises it rather than duplicating.
        """
        scripting_window = ScriptingWindow(self, settings=self._settings)
        console = scripting_window.console
        console.bind_sensor(self._sensor)
        console.refreshRequested.connect(self._refresh_from_console)
        console.stateMaybeChanged.connect(self._on_console_state_changed)
        scripting_window.refresh_workspace()  # reflect the just-bound sensor in the Workspace
        self._scripting_window = scripting_window
        self._console = console

    def _show_scripting_window(self) -> None:
        """Handle Tools → Scripting Window: show/raise the single window instance.

        Idempotent — re-triggering raises and focuses the existing window rather than
        spawning a duplicate (the reference is held on ``self._scripting_window``).
        """
        self._scripting_window.show_and_raise()

    def _on_console_state_changed(self) -> None:
        """A console command may have mutated the sensor: mark the GUI's own state stale.

        The console already shows its 'console changed state — Refresh' banner; here the
        window echoes the staleness in its primary surfaces (stage-health dots + status bar)
        so the operator sees the GUI is out of date wherever they are looking (GUI plan
        Phase 8 — explicit, not magic). Refresh (or a normal Evaluate) clears it.
        """
        self._stage_strip.set_all_status("stale")
        self.statusBar().showMessage("Console changed the sensor — Refresh to re-read it")

    def _refresh_from_console(self) -> None:
        """Adopt the console's current ``sensor``, re-read it into the GUI, re-evaluate.

        This is the one-click Refresh (GUI plan Phase 8). Adopting the console namespace's
        ``sensor`` handles both an in-place ``sensor.set(...)`` (same object) and a full
        rebind ``sensor = Sensor.load(...)`` (a new object the window never saw) — the honest
        counterpart to magic live-sync. The parameter tree and the per-stage input forms are
        repopulated from the adopted sensor, the console is rebound so identities agree again,
        and a full re-evaluation refreshes every panel and the console's ``result``/``plot``.
        """
        console_sensor = self._console.namespace_sensor()
        if console_sensor is None:
            return
        # A console mutation may have edited the live sensor in place or rebound it to a
        # whole new object (`sensor = Sensor.load(...)`), so the undo stack is cleared and
        # the config is marked dirty (the console's changes are unsaved). The file path is
        # kept as-is — the console cannot report a new one. (GUI plan Phase 9: console /
        # YAML-editor changes reset the undo history; explicit beats a fragile merge.)
        self._adopt_sensor(
            console_sensor, path=self._current_path, dirty=True, add_recent=False, evaluate=True
        )

    def _on_parameter_edited(self, dotpath: str) -> None:
        """React to an accepted parameter edit: gray the dots + schedule a re-evaluate.

        A parameter edit makes every downstream result out of date, so all stage
        health dots flip back to gray/stale (§4.2) until the pending run lands. The
        full chain re-runs after the 200 ms debounce window (arch doc §3.3); rapid
        edits coalesce into a single run. There is no incremental engine (CU-079,
        declined) — every re-evaluation is a full chain.

        Any geometry conflict tint is cleared: the pending run re-highlights it only if
        the conflict survives (Rule 17 — the state is honest, never stale).

        The Geometry input form is re-synced immediately (CU-121) so a value edited in the
        parameter tree shows on the form at once, not only after the debounced run lands.
        This is safe on a mid-edit *invalid* sensor: ``refresh`` reads through the guarded
        accessors (``safe_provenance`` → "", ``field_display_text`` → "—", CU-105/CU-140),
        so an unresolvable sensor shows unset rather than raising, and the debounced
        re-evaluate still surfaces any genuine error through the normal failure path.
        """
        self._central.stage_center.clear_geometry_highlight()
        self._central.stage_center.refresh_forms()
        # Record the edit as a reversible command (Edit → Undo/Redo, Phase 9) and mark the
        # config dirty (its title * marker) — both before scheduling the re-run.
        self._push_edit_command(dotpath)
        self._mark_dirty()
        self._stage_strip.set_all_status("stale")
        self.statusBar().showMessage(f"Edited {dotpath} — re-evaluating…")
        self._debounce.start()

    def _on_compound_parameter_edited(self, dotpaths: list[str]) -> None:
        """Record a multi-dot-path edit (e.g. a shape pick + seeded dims) as one undo step.

        A single user action changed several parameters that must reverse atomically (CU-141).
        The individual :meth:`_push_edit_command` calls are wrapped in a ``QUndoStack`` macro so
        one Undo reverses the whole compound; the dirty / stale / re-evaluate side effects fire
        once, exactly as for a single edit. A single-element compound takes the ordinary path
        (no empty-macro artifact on the stack).
        """
        self._central.stage_center.clear_geometry_highlight()
        if len(dotpaths) > 1:
            self._undo_stack.beginMacro(f"Set {dotpaths[0]} (+{len(dotpaths) - 1} seeded)")
            for dotpath in dotpaths:
                self._push_edit_command(dotpath)
            self._undo_stack.endMacro()
        elif dotpaths:
            self._push_edit_command(dotpaths[0])
        self._mark_dirty()
        self._stage_strip.set_all_status("stale")
        self.statusBar().showMessage(f"Edited {dotpaths[0]} — re-evaluating…")
        self._debounce.start()

    def _on_form_parameter_edited(self, dotpath: str) -> None:
        """React to an accepted edit from the Geometry input form (GUI plan Phase 5).

        A form edit is validated on a throwaway clone (full resolve) before it touches the
        live sensor, so the live sensor is guaranteed to resolve cleanly here — the tree is
        safely repopulated so it reflects the new geometry value. Then the shared post-edit
        handling (stale dots + debounced re-evaluate) runs.
        """
        if self._sensor is not None:
            self._parameter_panel.populate(self._sensor)
        self._on_parameter_edited(dotpath)

    def _on_stage_selected(self, namespace: str) -> None:
        """Handle a stage-strip click: select the chip, navigate, swap the canvas.

        Navigation only (no API call beyond the one ``result.plot.*`` figure the
        stage's view names, GUI plan §4.1): the chip gets the selected state, the
        parameter panel scrolls to the stage's namespace group, and the canvas swaps
        to the stage's default visualization (arch doc §4.4). Pre-evaluate the canvas
        keeps its placeholder; the selection is remembered and rendered on the next
        result. A figure that fails to render is surfaced, never swallowed (Rules
        15/17).
        """
        self._stage_strip.select(namespace)
        self._parameter_panel.scroll_to_namespace(namespace)
        try:
            self._central.select_stage(namespace)
        except Exception as exc:  # rendering the API's own figure — surface, never swallow
            UnexpectedErrorDialog(exc, f"Rendering the {namespace} visualization", self).exec()

    def _build_status_bar(self) -> None:
        """Status bar with the initial ready/no-config message + a busy indicator.

        The busy indicator is an indeterminate progress bar shown only while a
        worker evaluation is in flight (arch doc §3.2: the status bar shows a busy
        indicator, there being no per-stage progress stream).
        """
        self._busy = QProgressBar(self)
        self._busy.setObjectName("busyIndicator")
        self._busy.setRange(0, 0)  # indeterminate
        self._busy.setTextVisible(False)
        self._busy.setFixedWidth(120)
        self._busy.setVisible(False)
        self.statusBar().addPermanentWidget(self._busy)

        message = "Ready" if self._sensor is None else "Ready — sensor loaded"
        self.statusBar().showMessage(message)

    def _apply_dock_proportions(self) -> None:
        """Size the left parameter dock and the right rail to the mockup's balance.

        ``resizeDocks`` gives an initial split; the user can re-drag afterwards.
        """
        self.resizeDocks(
            [self._parameter_dock, self._right_rail_dock],
            [_PARAM_DOCK_WIDTH, _RAIL_DOCK_WIDTH],
            Qt.Orientation.Horizontal,
        )

    # -- evaluate loop (GUI plan Phase 3) ----------------------------------

    @property
    def evaluation_count(self) -> int:
        """Number of evaluation attempts that have completed (ok or failed).

        The debounce test asserts that a burst of rapid edits produces exactly one
        additional completed evaluation.
        """
        return self._evaluation_count

    @property
    def last_result(self) -> ChainResult | None:
        """The most recent successful :class:`~radiant.api.ChainResult`, if any."""
        return self._last_result

    def _wire_evaluate_loop(self) -> None:
        """Enable and connect Evaluate (F5 / Run button) and the debounce timer.

        Evaluate is enabled only with a loaded sensor — there is nothing to run
        otherwise. The debounce timer is single-shot; each edit restarts it so a
        run fires only after edits go quiet for the window (arch doc §3.3).
        """
        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(_DEBOUNCE_MS)
        self._debounce.timeout.connect(self._evaluate_now)

        evaluate_action = self.action("run.evaluate")
        # The accent Run button now lives in the right-rail footer (§4.5); F5 / the Run menu
        # action and the footer button both drive the same evaluate slot.
        run_button = self._right_rail.run_button
        # Every sensor-gated action (Evaluate, the Run button, Edit Config, the console,
        # Save/Save As) is enabled together — a bare window with no sensor cannot run,
        # serialize, or save (arch doc §3.2/§4.5/§10). File → Open / New swap a sensor in
        # and re-enable them via _set_sensor_actions_enabled (Phase 9).
        self._set_sensor_actions_enabled(self._sensor is not None)
        # F5 / menu and the accent Run button both trigger an immediate run.
        evaluate_action.triggered.connect(self._evaluate_now)
        run_button.clicked.connect(self._evaluate_now)

    def _set_sensor_actions_enabled(self, enabled: bool) -> None:
        """Enable/disable every action that needs a loaded sensor (Phase 9).

        Evaluate + the right-rail Run button run the chain; Edit Config (YAML) and the
        scripting console bind the live sensor; Save / Save As serialize it. None of them
        makes sense on an empty window, so they toggle together as a sensor is loaded,
        swapped (File → Open / New), or when the window opens bare.
        """
        self.action("run.evaluate").setEnabled(enabled)
        self._right_rail.run_button.setEnabled(enabled)
        self._right_rail.yaml_button.setEnabled(enabled)
        self.action("tools.scripting_window").setEnabled(enabled)
        self.action("file.save").setEnabled(enabled)
        self.action("file.save_as").setEnabled(enabled)
        # GX-1 wire-ups: schema browser / explain / YAML export all read the live
        # sensor; JSON-result export additionally needs a result (armed with the
        # Inspector when the first result lands).
        self.action("file.export_yaml").setEnabled(enabled)
        self.action("file.export_resolved_yaml").setEnabled(enabled)
        if not enabled:
            self.action("file.export_metrics_csv").setEnabled(False)
            self.action("file.export_sweep_csv").setEnabled(False)
            self.action("file.export_xlsx").setEnabled(False)
        self.action("tools.schema").setEnabled(enabled)
        self.action("tools.explain").setEnabled(enabled)
        self.action("edit.reset_defaults").setEnabled(enabled)
        self.action("run.sweep").setEnabled(enabled)
        self.action("run.monte_carlo").setEnabled(enabled)
        self.action("tools.compare").setEnabled(enabled)
        self.action("tools.solve").setEnabled(enabled)
        self.action("run.batch").setEnabled(enabled)
        if not enabled:
            self.action("file.export_json").setEnabled(False)

    def _evaluate_now(self) -> None:
        """Start a full-chain evaluation, or coalesce if one is already running.

        The debounce timer is stopped (an explicit F5/Run pre-empts a pending
        debounced run). If a worker is already in flight, the request is remembered
        and re-issued when it finishes, so only one chain runs at a time.
        """
        if self._sensor is None:
            return
        self._debounce.stop()
        if self._worker is not None and self._worker.isRunning():
            self._rerun_pending = True
            return
        self._start_worker()

    def _start_worker(self) -> None:
        """Launch the evaluation worker on a private sensor snapshot (§3.2)."""
        sensor = self._sensor
        if sensor is None:  # pragma: no cover - guarded by caller
            return
        self._set_busy(True)
        # Clone on the GUI thread so a concurrent edit cannot race the worker's
        # read of the sensor (see workers.py). The worker still does one evaluate().
        worker = EvaluationWorker(sensor.clone())
        worker.finished_ok.connect(self._on_eval_ok)
        worker.failed.connect(self._on_eval_failed)
        worker.finished.connect(self._on_worker_finished)
        self._worker = worker
        worker.start()

    def _on_eval_ok(self, result: ChainResult, warnings: list[str]) -> None:
        """Render a successful result into the Pinned cards, Messages, banner, and plot.

        The performance metrics fill the right-rail *Pinned* panel (§4.5, the relocated
        badge row); chain warnings captured by the worker fill the right-rail *Messages*
        panel (a warning-free run clears it) rather than printing to the terminal (owner
        feedback 2026-07-13, Rule 17). Both are updated before the plot render so a render
        failure still leaves the metrics and warnings surfaced.
        """
        self._last_result = result
        # Bind the fresh result into the scripting console (updates `result`/`plot` and
        # clears its stale banner — the GUI and console now agree, arch doc §2.5), then
        # refresh the Workspace so it reflects the newly-bound `result` (a result re-bind
        # outside a command does not fire commandExecuted, arch doc §4.6.1).
        self._console.update_result(result)
        self._scripting_window.refresh_workspace()
        # A clean run means any prior geometry mode conflict is resolved — clear the tint,
        # and re-sync the Geometry input form to the (now clean) sensor so a value changed
        # in the parameter tree is reflected there too (GUI plan Phase 5).
        self._central.stage_center.clear_geometry_highlight()
        self._central.stage_center.refresh_forms()
        self._right_rail.pinned.update_from_result(result)
        self._right_rail.messages.set_warnings(warnings)
        # Drive the stage health dots (§4.2): green on a clean run, yellow when the
        # run carried any chain warning. Per-stage warning attribution is deferred —
        # the captured warnings are free-text and not reliably attributable to one
        # stage, so v1 marks the whole run yellow-on-any-warning (arch doc §4.2, the
        # documented decision). Done before the plot render so the health reflects the
        # run even if the figure fails.
        self._stage_strip.set_all_status("warn" if warnings else "ok")
        try:
            self._central.show_result(result)
        except Exception as exc:  # rendering the API's own figure — surface, never swallow
            self._central.mark_stale()
            UnexpectedErrorDialog(exc, "Rendering the evaluation result", self).exec()
            self.statusBar().showMessage("Evaluation succeeded, but the plot could not render")
            return
        # A result now exists: enable the global Inspector tool (§4.6). It opens against
        # the most recent result, so it stays enabled once armed.
        self.action("tools.inspector").setEnabled(True)
        self.action("file.export_json").setEnabled(True)
        self.action("file.export_metrics_csv").setEnabled(True)
        self.action("file.export_xlsx").setEnabled(True)
        self.action("tools.mtf_overlay").setEnabled(True)
        self._inspector_button.setEnabled(True)
        # A clean run is the committed baseline for undo: snapshot the resolved input
        # values so the next edit's before-value is known (the panel signals an edit only
        # after applying it, so the pre-edit value must come from this snapshot).
        self._refresh_snapshot()
        self.statusBar().showMessage(self._evaluated_message(result))

    def _on_eval_failed(self, exc: BaseException) -> None:
        """Handle a failed evaluation: keep the previous result, show it as stale.

        The previous badges and plot stay on screen (never a blank or partial mix)
        but are flagged stale; the actionable error is shown — a ``RadiantError``
        renders what/why/action, anything else gets a traceback dialog (Rules 15/17).

        Every stage dot goes red (§4.2). Per-stage failure attribution is deferred:
        the public exception surface does not reliably carry the originating stage, so
        v1 marks the whole run red rather than guessing a stage (arch doc §4.2, the
        documented decision).

        The error also surfaces in the right-rail *Messages* panel (§4.5, now carrying
        errors as well as warnings) and the still-displayed Pinned cards flip to their
        ``→?`` stale marker (§8.4), consistent with the stale plot notice.
        """
        self._stage_strip.set_all_status("err")
        self._central.mark_stale()
        self._right_rail.pinned.set_stale(True)
        self._right_rail.messages.set_error(exc)
        self.statusBar().showMessage("Evaluation failed — showing the previous result (stale)")
        # A geometry over/under-specification error localises to a mode family: tint the
        # offending selector and jump to the Geometry screen so the user sees which mode's
        # inputs conflict (GUI plan Phase 5 task 3). Purely a locator — the actionable text
        # is still shown below and in the Messages panel; no GUI-side geometry validation.
        self._highlight_geometry_conflict(exc)
        if isinstance(exc, RadiantError):
            ActionableErrorDialog(exc, "evaluate", self).exec()
        else:
            UnexpectedErrorDialog(exc, "Evaluating the signal chain", self).exec()

    def _highlight_geometry_conflict(self, exc: BaseException) -> None:
        """Tint + navigate to the geometry selector a mode conflict names (task 3).

        Reads the structured ``what`` / ``context`` off the error (a
        :class:`~radiant.geometry.errors.GeometrySpecificationError` carries both) and
        asks the stage center to highlight the implicated family. Navigates to the
        Geometry stage only when a family is actually implicated, so an unrelated error
        does not hijack the view.
        """
        what = str(getattr(exc, "what", "") or exc)
        raw_context = getattr(exc, "context", None)
        context = raw_context if isinstance(raw_context, dict) else None
        # implicated_families is pure (no resolve): decide first whether this is a geometry
        # conflict at all, so a non-geometry failure (e.g. a bounds error) never triggers a
        # form re-sync that would resolve an intentionally-broken sensor.
        if not implicated_families(what, context):
            self._central.stage_center.clear_geometry_highlight()
            return
        # A geometry over-spec is a stage check, not a bounds failure, so its parameters
        # still resolve individually — re-syncing the form to show the conflicting values
        # is safe. Then apply the tint and jump to the Geometry screen.
        self._central.stage_center.refresh_forms()
        self._central.stage_center.highlight_geometry_error(what, context)
        self._on_stage_selected("geometry")

    def _on_worker_finished(self) -> None:
        """Per-run cleanup: clear busy, count the attempt, re-run if one was queued."""
        self._evaluation_count += 1
        self._set_busy(False)
        self._worker = None
        self.evaluationFinished.emit(self._last_result)
        if self._rerun_pending:
            self._rerun_pending = False
            self._evaluate_now()

    def _set_busy(self, busy: bool) -> None:
        """Show/hide the status-bar busy indicator around a worker run."""
        self._busy.setVisible(busy)
        if busy:
            self.statusBar().showMessage("Evaluating…")

    # -- Global Inspector tool (arch doc §4.6) -----------------------------

    def open_inspector(self) -> InspectorDialog | None:
        """Build the Inspector dialog against the most recent result (``None`` if none).

        Returned (not exec'd) so tests can inspect the populated tree without blocking on
        a modal loop; the menu/toolbar handler shows it non-modally.
        """
        if self._last_result is None:
            return None
        return InspectorDialog(self._last_result, self)

    def _open_inspector(self) -> None:
        """Handle the Tools → Inspector action / corner button: show the dump non-modally."""
        dialog = self.open_inspector()
        if dialog is not None:
            dialog.show()

    # -- Edit Config (YAML) modal (arch doc §4.5) --------------------------

    def _on_edit_config_requested(self) -> None:
        """Handle the right-rail Edit Config (YAML) click: open the modal editor."""
        dialog = self.open_yaml_editor()
        if dialog is not None:
            dialog.exec()

    def open_yaml_editor(self) -> YamlEditorDialog | None:
        """Build the YAML editor against the live sensor, wired to apply-and-reevaluate.

        Returns the dialog (not yet exec'd) so tests can drive Apply/Revert without
        blocking on the modal event loop; the button handler exec's the returned dialog.
        ``None`` when no sensor is loaded (nothing to serialize).
        """
        if self._sensor is None:
            return None
        dialog = YamlEditorDialog(self._sensor, self)
        dialog.configApplied.connect(self._apply_new_config)
        return dialog

    def _apply_new_config(self, sensor: Sensor) -> None:
        """Swap the live sensor for the Apply-parsed one and re-evaluate the whole GUI.

        The new sensor was parsed on a throwaway in the dialog (the live sensor was never
        touched on failure); here it becomes the session sensor via the shared adopt path
        (parameter tree + forms + console rebind, then a full re-evaluation, §4.5). The
        edited YAML is unsaved (dirty) and keeps the current file path; the undo stack is
        reset (a whole-config replace, not a single reversible edit — GUI plan Phase 9).
        """
        self._adopt_sensor(
            sensor, path=self._current_path, dirty=True, add_recent=False, evaluate=True
        )

    # -- File round-trip (arch doc §10, GUI plan Phase 9) ------------------

    def _wire_file_menu(self) -> None:
        """Enable and connect New / Open / Open Recent / Save / Save As (Phase 9).

        New and Open work with or without a sensor already loaded; Save / Save As are
        gated on a sensor (:meth:`_set_sensor_actions_enabled`). All file I/O goes through
        :meth:`Sensor.load` / :meth:`Sensor.save` — the GUI owns no reader/writer (§4.1).
        """
        new_action = self.action("file.new")
        new_action.setEnabled(True)
        new_action.triggered.connect(self._on_new)
        open_action = self.action("file.open")
        open_action.setEnabled(True)
        open_action.triggered.connect(self._on_open)
        self.action("file.save").triggered.connect(self._on_save)
        self.action("file.save_as").triggered.connect(self._on_save_as)
        # GX-1: exports + schema/explain tools — every handler is one API call
        # (Sensor.save / ChainResult.to_provenance_record / parameter_defs / explain).
        self.action("file.export_yaml").triggered.connect(self._on_export_yaml)
        self.action("file.export_json").triggered.connect(self._on_export_json)
        # GT-4 (Tier-2): the FW-B export surfaces.
        self.action("file.export_resolved_yaml").triggered.connect(self._on_export_resolved_yaml)
        self.action("file.export_metrics_csv").triggered.connect(self._on_export_metrics_csv)
        self.action("file.export_sweep_csv").triggered.connect(self._on_export_sweep_csv)
        self.action("file.export_xlsx").triggered.connect(self._on_export_xlsx)
        self.action("tools.schema").triggered.connect(self._on_schema_browser)
        self.action("tools.explain").triggered.connect(self._on_explain_parameter)
        # GT-1 (Tier-2): the sweep surface — worker-threaded, Gap 72 progress/cancel.
        self.action("run.sweep").triggered.connect(self._on_run_sweep)
        # GT-2 (owner D3): MC/Batch are console workflows — the menu items open the
        # scripting window with a ready-to-run scaffold (the GUI teaches the API).
        self.action("run.monte_carlo").triggered.connect(self._on_monte_carlo_scaffold)
        self.action("run.batch").triggered.connect(self._on_batch_scaffold)
        # GT-3 (Tier-2): the comparison view over compare_configs (Gap 79).
        self.action("tools.compare").triggered.connect(self._on_compare_configs)
        # GT-5 (Tier-2): the measurement overlay (GUI-4) over compare_mtf.
        self.action("tools.mtf_overlay").triggered.connect(self._on_mtf_overlay)
        # GT-6 (Tier-2): the inverse-solve face on Sensor.solve_for (GUI-8).
        self.action("tools.solve").triggered.connect(self._on_solve)
        self._rebuild_recent_menu()

    def _adopt_sensor(
        self,
        sensor: Sensor | None,
        *,
        path: Path | None,
        dirty: bool,
        add_recent: bool,
        evaluate: bool,
    ) -> None:
        """Make *sensor* the session sensor and rebind every panel (the shared swap path).

        The one place a new sensor becomes live: File → Open / New, the YAML-editor Apply,
        and the console Refresh all route here. It rebinds the parameter tree, the per-stage
        input forms, and the console; resets the undo stack (a whole-sensor swap is not a
        reversible single edit); updates the title (file name + dirty marker); optionally
        records the file in the recent list; and either re-evaluates (a real config) or just
        snapshots the inputs (a blank File → New that cannot resolve yet).
        """
        self._sensor = sensor
        self._current_path = path
        self._dirty = dirty
        self._undo_stack.clear()
        self._set_sensor_actions_enabled(sensor is not None)
        self.setWindowTitle(self._compose_title())
        self._parameter_panel.populate(sensor)
        self._central.stage_center.bind_sensor(sensor, self._parameter_panel.display_units)
        self._console.bind_sensor(sensor)
        self._console.set_stale(False)
        self._scripting_window.refresh_workspace()  # the Workspace tracks the adopted sensor
        if add_recent and path is not None:
            self._settings.add_recent_file(str(path))
            self._rebuild_recent_menu()
        if evaluate and sensor is not None and self._sensor_can_resolve(sensor):
            self._evaluate_now()
        else:
            self._refresh_snapshot()
            if sensor is not None and evaluate:
                # A config that cannot resolve yet (from-scratch / blank New): do NOT
                # auto-evaluate into a modal error at open (owner report 2026-07-17) —
                # guide instead; Evaluate (F5) reports exactly what is missing.
                self.statusBar().showMessage(
                    "Configuration incomplete — set required parameters, then Evaluate (F5) "
                    "to see what is still missing"
                )

    def _confirm_discard_edits(self) -> bool:
        """CU-140 guard: with unsaved edits, offer Save / Discard / Cancel.

        Returns True when it is safe to replace the current config (clean state,
        the user saved, or the user chose Discard); False cancels the action.
        Save routes through the ordinary :meth:`_on_save` path (Save As when the
        config has no file yet) and re-checks the dirty flag — a cancelled Save
        As leaves the edits unsaved, so the swap is cancelled too.
        """
        if self._sensor is None or not self._dirty:
            return True
        answer = QMessageBox.question(
            self,
            "Unsaved changes",
            "The configuration has unsaved edits. Save them first?",
            QMessageBox.StandardButton.Save
            | QMessageBox.StandardButton.Discard
            | QMessageBox.StandardButton.Cancel,
        )
        if answer == QMessageBox.StandardButton.Save:
            self._on_save()
            return not self._dirty
        return answer == QMessageBox.StandardButton.Discard

    @staticmethod
    def _sensor_can_resolve(sensor: Sensor) -> bool:
        """Whether *sensor* resolves — gates the automatic adopt-time evaluation.

        A blank / incomplete config must open editable with guidance, not a modal
        error (owner report 2026-07-17). Checked on a clone; the live sensor's
        resolution state is untouched.
        """
        try:
            sensor.clone().get_input("optics.aperture_diameter_m")
        except (KeyError, RadiantError):
            return False
        return True

    def _on_new(self) -> None:
        """File → New: open a blank config (guarded against losing unsaved edits, CU-140)."""
        if not self._confirm_discard_edits():
            return
        self._adopt_sensor(Sensor(), path=None, dirty=False, add_recent=False, evaluate=False)
        self.statusBar().showMessage("New configuration — edit parameters, then Evaluate")

    def _on_open(self) -> None:
        """File → Open: pick a YAML and load it (guarded, CU-140)."""
        if not self._confirm_discard_edits():
            return
        start_dir = str(self._current_path.parent) if self._current_path is not None else ""
        filename, _ = QFileDialog.getOpenFileName(
            self, "Open RADIANT config", start_dir, _YAML_FILTER
        )
        if filename:
            self._open_path(filename)

    def _open_path(self, path: str) -> None:
        """Load *path* via :meth:`Sensor.load`, swap it in, and re-evaluate (Rule 15 errors).

        A malformed or missing config surfaces its actionable error (a ``RadiantError`` shows
        what/why/action; an I/O or parse error gets the traceback dialog) and leaves the
        current sensor untouched — never a blank or half-swapped state (Rules 15/17).
        """
        try:
            sensor = Sensor.load(path)
        except RadiantError as exc:
            ActionableErrorDialog(exc, "open", self).exec()
            return
        except (OSError, ValueError) as exc:
            UnexpectedErrorDialog(exc, f"Opening {path}", self).exec()
            return
        self._adopt_sensor(sensor, path=Path(path), dirty=False, add_recent=True, evaluate=True)
        self.statusBar().showMessage(f"Opened {Path(path).name}")

    def _rebuild_recent_menu(self) -> None:
        """Repopulate File → Open Recent from the persisted list (QSettings, Phase 9)."""
        self._recent_menu.clear()
        recent = self._settings.recent_files()
        self._recent_menu.setEnabled(bool(recent))
        for entry in recent:
            action = self._recent_menu.addAction(entry)
            action.triggered.connect(lambda _checked=False, p=entry: self._open_recent(p))

    def _open_recent(self, path: str) -> None:
        """Open a recent entry (guarded against losing unsaved edits, CU-140)."""
        if self._confirm_discard_edits():
            self._open_path(path)

    def _on_save(self) -> None:
        """File → Save: write to the current file, or fall back to Save As if none yet."""
        if self._current_path is None:
            self._on_save_as()
        else:
            self._save_to_path(self._current_path)

    def _on_save_as(self) -> None:
        """File → Save As: pick a destination and write through :meth:`Sensor.save`."""
        if self._sensor is None:
            return
        start = str(self._current_path) if self._current_path is not None else ""
        filename, _ = QFileDialog.getSaveFileName(self, "Save RADIANT config", start, _YAML_FILTER)
        if filename:
            self._save_to_path(Path(filename))

    def _save_to_path(self, path: Path) -> None:
        """Write the live sensor to *path* via :meth:`Sensor.save`; clear the dirty marker.

        A serialization failure (an unresolved config, an I/O error) surfaces its actionable
        error and leaves the dirty state as-is (Rules 15/17). On success the file becomes the
        current path, the title's ``*`` clears, and the file joins the recent list.
        """
        sensor = self._sensor
        if sensor is None:
            return
        try:
            written = sensor.save(path)
        except RadiantError as exc:
            ActionableErrorDialog(exc, "save", self).exec()
            return
        except OSError as exc:
            UnexpectedErrorDialog(exc, f"Saving {path}", self).exec()
            return
        self._current_path = Path(written)
        self._dirty = False
        self.setWindowTitle(self._compose_title())
        self._settings.add_recent_file(str(written))
        self._rebuild_recent_menu()
        self.statusBar().showMessage(f"Saved {Path(written).name}")

    def _mark_dirty(self) -> None:
        """Flag unsaved edits and refresh the title's ``*`` marker (idempotent)."""
        if self._sensor is not None and not self._dirty:
            self._dirty = True
            self.setWindowTitle(self._compose_title())

    # -- Undo / redo (arch doc §10, GUI plan Phase 9) ----------------------

    def _on_export_yaml(self) -> None:
        """File → Export YAML…: write the config to a chosen path (one Sensor.save call).

        Unlike Save As, exporting does not adopt the destination as the current file and
        does not clear the dirty marker — it is a snapshot, not a rebind.
        """
        sensor = self._sensor
        if sensor is None:
            return
        filename, _ = QFileDialog.getSaveFileName(self, "Export RADIANT config", "", _YAML_FILTER)
        if not filename:
            return
        try:
            sensor.save(Path(filename))
        except RadiantError as exc:
            ActionableErrorDialog(exc, "export_yaml", self).exec()
            return
        self.statusBar().showMessage(f"Exported config to {filename}")

    def _on_export_json(self) -> None:
        """File → Export JSON Result…: write the last result's provenance record as JSON.

        One API call (ChainResult.to_provenance_record) + json.dump. A value the record
        cannot serialize raises and surfaces — never a silently-truncated export (Rule 17).
        """
        result = self._last_result
        if result is None:
            return
        filename, _ = QFileDialog.getSaveFileName(
            self, "Export result (JSON)", "", "JSON (*.json);;All files (*)"
        )
        if not filename:
            return
        try:
            record = result.to_provenance_record()
            Path(filename).write_text(json.dumps(record, indent=2), encoding="utf-8")
        except (TypeError, ValueError, OSError) as exc:
            UnexpectedErrorDialog(exc, "Exporting the result as JSON", self).exec()
            return
        self.statusBar().showMessage(f"Exported result record to {filename}")

    def _on_run_sweep(self) -> None:
        """Run → Run Sweep… (GT-1): the 1-D/2-D sweep dialog over a sensor clone.

        Metric choices come from the last result when one exists (the live metric
        set), else a minimal default. The finished result is retained on the window
        (`last_sweep_result`) for export (`SweepResult.to_csv`, FW-B).
        """
        sensor = self._sensor
        if sensor is None:
            return
        if self._last_result is not None:
            metric_names = tuple(sorted(self._last_result.metrics))
        else:
            metric_names = ("snr",)
        dialog = SweepDialog(sensor, metric_names, self)
        dialog.exec()
        if dialog.sweep_result is not None:
            self.last_sweep_result = dialog.sweep_result
            self.action("file.export_sweep_csv").setEnabled(True)
            self.statusBar().showMessage(
                "Sweep complete — result retained (export via SweepResult.to_csv)"
            )

    def _on_solve(self) -> None:
        """Tools → Solve for Parameter… (GT-6): the GUI face on solve_for."""
        sensor = self._sensor
        if sensor is None:
            return
        metric_names = (
            tuple(sorted(self._last_result.metrics)) if self._last_result is not None else ("snr",)
        )
        from radiant.gui.widgets.solve_dialog import SolveDialog

        SolveDialog(sensor, metric_names, self).exec()

    def _on_mtf_overlay(self) -> None:
        """Tools → Compare Measured MTF… (GT-5): lab points over the predicted curve."""
        if self._last_result is None:
            return
        from radiant.gui.widgets.mtf_overlay_dialog import MtfOverlayDialog

        MtfOverlayDialog(self._last_result, self).exec()

    def _on_compare_configs(self) -> None:
        """Tools → Compare Configurations… (GT-3): current config vs loaded files."""
        if self._sensor is None:
            return
        from radiant.gui.widgets.comparison_dialog import ComparisonDialog

        ComparisonDialog(self._sensor, self).exec()

    def _open_script_scaffold(self, title: str, snippet: str) -> None:
        """Open the scripting window with *snippet* in a fresh editor tab (GT-2).

        Uses only the scripting window's existing public surface (show + editor
        new_tab + tab.set_text) — the console namespace already binds ``sensor``.
        """
        self._scripting_window.show_and_raise()
        tab = self._scripting_window.editor.new_tab()
        tab.set_text(snippet)
        self.statusBar().showMessage(f"{title} scaffold opened in the script editor — edit and Run")

    def _on_monte_carlo_scaffold(self) -> None:
        """Run → Monte Carlo…: prefill an MC script from current state (owner D3)."""
        sensor = self._sensor
        if sensor is None:
            return
        tolerances = sensor.tolerances()
        if tolerances:
            tol_lines = "\n".join(
                f"# toleranced: {name} ~ {tol.distribution}{dict(tol.params)}"
                for name, tol in sorted(tolerances.items())
            )
        else:
            tol_lines = (
                "# No tolerances set yet — annotate parameters first, e.g.:\n"
                '# sensor.set_tolerance("detector.qe_value", "gaussian", std=0.02)\n'
                "# (or use the Tolerance section in any parameter editor dialog)"
            )
        snippet = (
            "# Monte Carlo scaffold (Run → Monte Carlo…)\n"
            f"{tol_lines}\n"
            "mc = sensor.monte_carlo(n_trials=500, seed=42)\n"
            "for name in mc.metric_names:\n"
            "    p5 = mc.percentile(name, 5)\n"
            "    p50 = mc.percentile(name, 50)\n"
            "    p95 = mc.percentile(name, 95)\n"
            '    print(f"{name}: p5={p5:.4g}  median={p50:.4g}  p95={p95:.4g}")\n'
            '# mc.to_csv("mc_trials.csv")  # per-trial export (Gap 88)\n'
        )
        self._open_script_scaffold("Monte Carlo", snippet)

    def _on_batch_scaffold(self) -> None:
        """Run → Batch Run…: prefill a BatchRunner skeleton (owner D3)."""
        if self._sensor is None:
            return
        snippet = (
            "# Batch scaffold (Run → Batch Run…) — cartesian product of labeled axes\n"
            "from radiant.api.batch import BatchRunner\n"
            "\n"
            "base = {}  # or a nested config dict; cells start from Sensor.from_dict(base)\n"
            "axes = [\n"
            '    ("aperture", {"25cm": {"optics.aperture_diameter_m": 0.25},\n'
            '                  "35cm": {"optics.aperture_diameter_m": 0.35}}),\n'
            '    ("t_int",    {"2ms": {"spectral_integration.integration_time_s": 0.002},\n'
            '                  "5ms": {"spectral_integration.integration_time_s": 0.005}}),\n'
            "]\n"
            "\n"
            "def evaluate(cell_sensor, labels):\n"
            "    r = cell_sensor.evaluate()\n"
            '    return {"snr": r.metrics["snr"]}\n'
            "\n"
            "batch = BatchRunner(base, axes).run(evaluate)\n"
            'print(batch.pivot("snr", rows="aperture", cols="t_int"))\n'
            'print(f"failed cells: {batch.n_failed}")\n'
        )
        self._open_script_scaffold("Batch", snippet)

    def _save_dialog(self, title: str, default: str, filter_: str) -> str | None:
        filename, _ = QFileDialog.getSaveFileName(self, title, default, filter_)
        return filename or None

    def _on_export_resolved_yaml(self) -> None:
        """File → Export Resolved YAML… (GT-4): the fully-specified export (FW-B)."""
        sensor = self._sensor
        if sensor is None:
            return
        filename = self._save_dialog("Export resolved YAML", "resolved.yaml", _YAML_FILTER)
        if filename is None:
            return
        try:
            text = sensor.to_yaml(scope="resolved")
        except RadiantError as exc:
            ActionableErrorDialog(exc, "export_resolved_yaml", self).exec()
            return
        Path(filename).write_text(text, encoding="utf-8")
        self.statusBar().showMessage(f"Resolved config exported to {filename}")

    def _on_export_metrics_csv(self) -> None:
        """File → Export Metrics CSV… (GT-4): one ChainResult.to_csv call (FW-B)."""
        if self._last_result is None:
            return
        filename = self._save_dialog("Export metrics CSV", "metrics.csv", "CSV (*.csv)")
        if filename is None:
            return
        self._last_result.to_csv(filename)
        self.statusBar().showMessage(f"Metrics exported to {filename}")

    def _on_export_sweep_csv(self) -> None:
        """File → Export Sweep CSV… (GT-4): the retained sweep's to_csv (FW-B)."""
        sweep = self.last_sweep_result
        if sweep is None:
            return
        filename = self._save_dialog("Export sweep CSV", "sweep.csv", "CSV (*.csv)")
        if filename is None:
            return
        sweep.to_csv(filename)
        self.statusBar().showMessage(f"Sweep exported to {filename}")

    def _on_export_xlsx(self) -> None:
        """File → Export XLSX Workbook… (GT-4, owner D2): config + metrics + sweep."""
        sensor = self._sensor
        if sensor is None:
            return
        filename = self._save_dialog("Export XLSX workbook", "radiant.xlsx", "XLSX (*.xlsx)")
        if filename is None:
            return
        from radiant.gui.xlsx_export import export_workbook

        export_workbook(filename, sensor, self._last_result, self.last_sweep_result)
        self.statusBar().showMessage(f"Workbook exported to {filename}")

    def _on_schema_browser(self) -> None:
        """Tools → Parameter Schema Browser: the read-only Gap-70 schema tree."""
        if self._sensor is None:
            return
        SchemaBrowserDialog(self._sensor, self).exec()

    def _on_explain_parameter(self) -> None:
        """Tools → Explain Parameter…: pick a dot-path, show Sensor.explain(dotpath)."""
        sensor = self._sensor
        if sensor is None:
            return
        names = sorted(sensor.parameter_defs())
        dotpath, ok = QInputDialog.getItem(self, "Explain Parameter", "Parameter:", names, 0, False)
        if not ok or not dotpath:
            return
        ExplainDialog(dotpath, sensor.explain(dotpath), self).exec()

    def _wire_edit_menu(self) -> None:
        """Wire Edit → Undo / Redo to the parameter-edit :class:`QUndoStack` (Phase 9)."""
        undo_action = self.action("edit.undo")
        redo_action = self.action("edit.redo")
        undo_action.triggered.connect(self._undo_stack.undo)
        redo_action.triggered.connect(self._undo_stack.redo)
        # The stack drives the actions' enabled state so they grey out at the ends.
        self._undo_stack.canUndoChanged.connect(undo_action.setEnabled)
        self._undo_stack.canRedoChanged.connect(redo_action.setEnabled)
        undo_action.setEnabled(self._undo_stack.canUndo())
        redo_action.setEnabled(self._undo_stack.canRedo())
        # Gap 93 closed: Reset to Defaults reverts every USER_SET input (edits since
        # load) via the one Sensor.reset_all() call; config-file inputs survive.
        self.action("edit.reset_defaults").triggered.connect(self._on_reset_defaults)

    def _on_reset_defaults(self) -> None:
        """Edit → Reset to Defaults: discard every edit made since the config loaded.

        With a current file, the honest revert is a clean reload (one
        ``Sensor.load`` call) — an edit replaces an input's provenance, so a
        provenance-scoped reset cannot restore an edited config value (see
        ``Sensor.reset_all``). Without a file (File → New), every explicit input
        clears to schema defaults via ``Sensor.reset_all(scope="all")``. Both run
        behind an explicit confirmation and re-adopt through the shared swap path
        (rebind + undo-stack clear + re-evaluation).
        """
        sensor = self._sensor
        if sensor is None:
            return
        if self._current_path is not None:
            message = (
                f"Discard all edits and reload {self._current_path.name}?\n"
                "The configuration reverts exactly to the file on disk."
            )
        else:
            message = (
                "Reset every parameter to its schema default?\n"
                "This unsaved configuration has no file to revert to."
            )
        answer = QMessageBox.question(self, "Reset to Defaults", message)
        if answer != QMessageBox.StandardButton.Yes:
            return
        if self._current_path is not None:
            try:
                fresh = Sensor.load(self._current_path)
            except RadiantError as exc:
                ActionableErrorDialog(exc, str(self._current_path), self).exec()
                return
            self._adopt_sensor(
                fresh, path=self._current_path, dirty=False, add_recent=False, evaluate=True
            )
            self.statusBar().showMessage(f"Reverted to {self._current_path.name}")
        else:
            sensor.reset_all(scope="all")
            self._adopt_sensor(sensor, path=None, dirty=False, add_recent=False, evaluate=False)
            self.statusBar().showMessage("Reset to schema defaults")

    def _refresh_snapshot(self) -> None:
        """Snapshot the resolved input values (the undo before-value baseline).

        Rebuilt after each clean evaluation and on a sensor swap. Reads the public
        :meth:`Sensor.get_input` surface; a parameter that is present-but-unresolved raises
        ``KeyError`` (skipped), and a whole config that does not resolve yet (a blank File →
        New) raises a ``RadiantError`` — caught so the baseline is simply empty until the
        first clean run fills it. No silent physics swallow (Rule 17): this is undo
        bookkeeping over already-validated inputs.
        """
        snapshot: dict[str, Any] = {}
        sensor = self._sensor
        if sensor is not None:
            try:
                for dotpath in sensor.parameter_defs():
                    try:
                        value = sensor.get_input(dotpath)
                    except KeyError:
                        continue
                    if value is not None:
                        snapshot[dotpath] = value
            except RadiantError:
                snapshot = {}
        self._input_snapshot = snapshot

    def _push_edit_command(self, dotpath: str) -> None:
        """Record *dotpath*'s just-applied edit as a reversible command (Phase 9).

        The panel signals an edit only after applying it, so the *new* value is read from
        the sensor and the *old* value from the committed snapshot. A non-scalar, unresolved,
        or no-op edit records nothing (there is nothing meaningful to reverse). A shape pick
        and the dimensions seeded alongside it are recorded together under one undo macro via
        :meth:`_on_compound_parameter_edited` (CU-141), so they reverse as a single step.
        """
        sensor = self._sensor
        if sensor is None:
            return
        try:
            new_value = sensor.get_input(dotpath)
            pdef = sensor.parameter_def(dotpath)
        except (KeyError, RadiantError):
            return
        if new_value is None:
            return
        old_value = self._input_snapshot.get(dotpath, new_value)
        self._input_snapshot[dotpath] = new_value
        if old_value == new_value:
            return
        text = f"Set {dotpath} = {format_value(new_value, pdef.input_unit)}"
        command = SetParameterCommand(
            sensor,
            dotpath,
            old_value,
            new_value,
            pdef.input_unit or None,
            self._apply_undo_redo,
            text,
        )
        self._undo_stack.push(command)

    def _apply_undo_redo(self, dotpath: str) -> None:
        """Re-read the panels and re-evaluate after an undo/redo mutates the sensor.

        Called by :class:`~radiant.gui.widgets.set_parameter_command.SetParameterCommand`
        from within undo()/redo() — it must not push a new command (no recursion). Repopulates
        the parameter tree + geometry forms from the restored value, keeps the snapshot in
        step, marks the config dirty (it now differs from the file again), and schedules the
        debounced full-chain re-run.
        """
        sensor = self._sensor
        if sensor is not None:
            self._parameter_panel.populate(sensor)
            self._central.stage_center.refresh_forms()
            try:
                value = sensor.get_input(dotpath)
            except (KeyError, RadiantError):
                value = None
            if value is not None:
                self._input_snapshot[dotpath] = value
        self._mark_dirty()
        self._stage_strip.set_all_status("stale")
        self.statusBar().showMessage(f"{dotpath} — re-evaluating…")
        self._debounce.start()

    # -- View menu (arch doc §10, GUI plan Phase 9) ------------------------

    def _wire_view_menu(self) -> None:
        """Wire the View menu: theme toggle, panel show/hide, stage-jump shortcuts (Phase 9)."""
        # Light/Dark theme toggle. Checked ⇔ dark; the state is seeded from the theme the
        # app actually launched in (the persisted choice, applied in app.py).
        theme_action = self.action("view.theme")
        theme_action.setEnabled(True)
        theme_action.setCheckable(True)
        theme_action.setChecked(active_theme().name == DARK.name)
        theme_action.triggered.connect(self._on_toggle_theme)

        # Parameter-dock show/hide (F6), restored from the persisted panel state.
        params_action = self.action("view.toggle_params")
        params_action.setEnabled(True)
        params_action.setCheckable(True)
        params_visible = self._settings.panel_visible("parameters", True)
        self._parameter_dock.setVisible(params_visible)
        params_action.setChecked(params_visible)
        params_action.toggled.connect(self._on_toggle_params)

        # Right-rail show/hide (F7 — the arch-§10 "Detail Panel" slot; the rail is v1's
        # persistent detail column).
        rail_action = self._add_action(
            self._view_menu, "view.toggle_rail", "Show/Hide Right Rail", enabled=True, shortcut="F7"
        )
        rail_action.setCheckable(True)
        rail_visible = self._settings.panel_visible("right_rail", True)
        self._right_rail_dock.setVisible(rail_visible)
        rail_action.setChecked(rail_visible)
        rail_action.toggled.connect(self._on_toggle_rail)

        # Stage-jump shortcuts (Ctrl+1..9 → the nine signal-chain stages, arch doc §10).
        stage_menu = self._view_menu.addMenu("Go to Stage")
        for index, namespace in enumerate(STAGE_NAMESPACES, start=1):
            action = QAction(f"{index}  {namespace}", self)
            action.setShortcut(f"Ctrl+{index}")
            action.triggered.connect(
                lambda _checked=False, ns=namespace: self._on_stage_selected(ns)
            )
            stage_menu.addAction(action)
            self._actions[f"view.stage_{index}"] = action

    def _on_toggle_theme(self, _checked: bool = False) -> None:
        """Switch the app between the light and dark themes and re-theme every surface.

        Re-applies the design-system stylesheet + palette (restyling every QSS-driven
        widget), then re-themes the custom-painted widgets (the schematic viewer, the
        detector illustration — which read a stored theme, not QSS) and re-renders the
        current stage composite so its figures redraw in step. The choice persists via
        ``QSettings`` so the next launch reopens in the same theme (GUI plan Phase 9).
        """
        app = QApplication.instance()
        if not isinstance(app, QApplication):
            return
        new_theme = LIGHT if active_theme().name == DARK.name else DARK
        apply_theme(app, new_theme)
        self._central.stage_center.set_theme(new_theme)
        # The scripting window's Editor uses a QSyntaxHighlighter (outside QSS's reach), so its
        # glyph colours are re-applied here to keep the Editor in step with the toggle (§4.6.1).
        self._scripting_window.set_theme(new_theme)
        if self._last_result is not None:
            self._central.show_result(self._last_result)
        self._settings.set_theme_name(new_theme.name)
        self.action("view.theme").setChecked(new_theme.name == DARK.name)
        self.statusBar().showMessage(f"{new_theme.name.title()} theme")

    def _on_toggle_params(self, visible: bool) -> None:
        """Show/hide the parameter dock and persist the choice."""
        self._parameter_dock.setVisible(visible)
        self._settings.set_panel_visible("parameters", visible)

    def _on_toggle_rail(self, visible: bool) -> None:
        """Show/hide the right rail and persist the choice."""
        self._right_rail_dock.setVisible(visible)
        self._settings.set_panel_visible("right_rail", visible)

    @staticmethod
    def _evaluated_message(result: ChainResult) -> str:
        """A concise 'evaluated' status line: wavelength-grid size (arch doc §4.1)."""
        n_points = int(result.wavelength_um.size)
        return f"Evaluated — {n_points} wavelength points"
