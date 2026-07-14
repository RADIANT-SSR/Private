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

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QDockWidget,
    QMainWindow,
    QMenu,
    QProgressBar,
    QPushButton,
    QWidget,
)

from radiant.core.exceptions import RadiantError
from radiant.gui.widgets.actionable_error_dialog import ActionableErrorDialog
from radiant.gui.widgets.central_canvas import CentralCanvas
from radiant.gui.widgets.inspector_dialog import InspectorDialog
from radiant.gui.widgets.parameter_panel import ParameterPanel
from radiant.gui.widgets.right_rail import RightRail
from radiant.gui.widgets.stage_strip import StageStrip
from radiant.gui.widgets.unexpected_error_dialog import UnexpectedErrorDialog
from radiant.gui.widgets.yaml_editor_dialog import YamlEditorDialog
from radiant.gui.workers import EvaluationWorker

if TYPE_CHECKING:
    from radiant.api import ChainResult
    from radiant.api.sensor import Sensor

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

    def __init__(self, sensor: Sensor | None = None) -> None:
        super().__init__()
        self._sensor = sensor
        # Registry of every menu action by a stable key, so tests and later
        # phases can look one up without walking the menu tree.
        self._actions: dict[str, QAction] = {}

        # Evaluate-loop state (Phase 3): the in-flight worker, a coalescing flag
        # for edits that land mid-run, the most recent result, and a count of
        # completed evaluations (the debounce test asserts on it).
        self._worker: EvaluationWorker | None = None
        self._rerun_pending: bool = False
        self._last_result: ChainResult | None = None
        self._evaluation_count: int = 0

        self.setObjectName("radiantMainWindow")
        self.setWindowTitle(self._compose_title())
        self.resize(_DEFAULT_WIDTH, _DEFAULT_HEIGHT)

        self._build_menu_bar()
        self._build_stage_strip()
        self._build_central_area()
        self._build_dock_panels()
        self._build_status_bar()
        self._apply_dock_proportions()
        self._wire_evaluate_loop()

        # Auto-evaluate once on load so the badges and plot populate immediately
        # (the D2 checkpoint opens on a filled dashboard). Deferred to the event
        # loop so the worker's signals are delivered after the window is shown.
        if self._sensor is not None:
            QTimer.singleShot(0, self._evaluate_now)

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

    def action(self, key: str) -> QAction:
        """Return the menu :class:`QAction` registered under *key*.

        Keys are ``"<menu>.<slug>"`` (e.g. ``"file.quit"``, ``"run.evaluate"``).
        Raises :class:`KeyError` if the action does not exist — a programmer
        error, not user input, so a bare ``KeyError`` is correct here.
        """
        return self._actions[key]

    # -- construction helpers ----------------------------------------------

    def _compose_title(self) -> str:
        """Window title: app name plus the loaded config, if any."""
        if self._sensor is None:
            return "RADIANT"
        source = getattr(self._sensor, "source_path", None)
        return f"RADIANT — {source}" if source else "RADIANT"

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
        self._add_action(file_menu, "file.open_recent", "Open Recent", enabled=False)
        self._add_action(
            file_menu, "file.save", "Save", enabled=False, shortcut=QKeySequence.StandardKey.Save
        )
        self._add_action(file_menu, "file.save_as", "Save As…", enabled=False)
        self._add_action(file_menu, "file.export_yaml", "Export YAML…", enabled=False)
        self._add_action(file_menu, "file.export_json", "Export JSON Result…", enabled=False)
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
        self._add_action(run_menu, "run.evaluate", "Evaluate", enabled=False, shortcut="F5")
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
        self._add_action(tools_menu, "tools.console", "Python Console", enabled=False)
        self._add_action(tools_menu, "tools.schema", "Parameter Schema Browser", enabled=False)
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

    def _on_parameter_edited(self, dotpath: str) -> None:
        """React to an accepted parameter edit: gray the dots + schedule a re-evaluate.

        A parameter edit makes every downstream result out of date, so all stage
        health dots flip back to gray/stale (§4.2) until the pending run lands. The
        full chain re-runs after the 200 ms debounce window (arch doc §3.3); rapid
        edits coalesce into a single run. There is no incremental engine (CU-079,
        declined) — every re-evaluation is a full chain.
        """
        self._stage_strip.set_all_status("stale")
        self.statusBar().showMessage(f"Edited {dotpath} — re-evaluating…")
        self._debounce.start()

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
        has_sensor = self._sensor is not None
        evaluate_action.setEnabled(has_sensor)
        run_button.setEnabled(has_sensor)
        # The Edit Config (YAML) modal needs a sensor to serialize; gate it likewise.
        self._right_rail.yaml_button.setEnabled(has_sensor)
        # F5 / menu and the accent Run button both trigger an immediate run.
        evaluate_action.triggered.connect(self._evaluate_now)
        run_button.clicked.connect(self._evaluate_now)

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
        self._inspector_button.setEnabled(True)
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
        if isinstance(exc, RadiantError):
            ActionableErrorDialog(exc, "evaluate", self).exec()
        else:
            UnexpectedErrorDialog(exc, "Evaluating the signal chain", self).exec()

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
        touched on failure); here it becomes the session sensor, the parameter tree
        re-populates from it, and a full re-evaluation refreshes every panel (§4.5).
        """
        self._sensor = sensor
        self.setWindowTitle(self._compose_title())
        self._parameter_panel.populate(sensor)
        self._evaluate_now()

    @staticmethod
    def _evaluated_message(result: ChainResult) -> str:
        """A concise 'evaluated' status line: wavelength-grid size (arch doc §4.1)."""
        n_points = int(result.wavelength_um.size)
        return f"Evaluated — {n_points} wavelength points"
