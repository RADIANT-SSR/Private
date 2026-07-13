"""The RADIANT main application window.

:class:`RADIANTMainWindow` lays out the top-level chrome described in
``RADIANT_GUI_Architecture.md`` §4: the menu bar (§10), the 9-stage geometry-first
signal-chain strip (§4.2), the dockable parameter and detail panels (§4.3, §4.5),
the central visualization area (§4.4), and the status bar.

In GUI plan Phase 1 (Task A) this is a *shell*: the layout regions exist as empty,
named placeholders and the menus are fully populated but every not-yet-implemented
action is disabled. Later phases fill the regions (parameter tree — Phase 2;
evaluate loop + canvas — Phase 3; stage strip + detail tabs — Phase 4) and enable
their menu actions. No styling is applied here; the design-system QSS theme is
GUI plan Phase 1 Task B and lives in :mod:`radiant.gui.themes`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QDockWidget,
    QLabel,
    QMainWindow,
    QMenu,
    QWidget,
)

if TYPE_CHECKING:
    from radiant.api.sensor import Sensor

# The signal chain in ADR-0006 order (geometry-first). Rendered as an empty,
# non-interactive placeholder strip in Phase 1; Phase 4 makes the stages
# clickable with health dots.
_STAGE_NAMES: tuple[str, ...] = (
    "Geometry",
    "Source",
    "Atmosphere",
    "Optics",
    "Platform",
    "Spectral",
    "Detector",
    "Readout",
    "Performance",
)


class RADIANTMainWindow(QMainWindow):
    """Top-level RADIANT GUI window (shell only in GUI plan Phase 1 Task A).

    Parameters
    ----------
    sensor:
        The :class:`~radiant.api.sensor.Sensor` the window opens on, or ``None``
        for an empty window. Stored for later phases (the parameter panel and
        evaluate loop read it); Phase 1 only records it and reflects its presence
        in the window title and status bar.
    """

    def __init__(self, sensor: Sensor | None = None) -> None:
        super().__init__()
        self._sensor = sensor
        # Registry of every menu action by a stable key, so tests and later
        # phases can look one up without walking the menu tree.
        self._actions: dict[str, QAction] = {}

        self.setObjectName("radiantMainWindow")
        self.setWindowTitle(self._compose_title())
        self.resize(1280, 800)

        self._build_menu_bar()
        self._build_stage_strip()
        self._build_central_area()
        self._build_dock_panels()
        self._build_status_bar()

    # -- public accessors ---------------------------------------------------

    @property
    def sensor(self) -> Sensor | None:
        """The sensor this window was opened on (``None`` if none)."""
        return self._sensor

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
        self._add_action(
            view_menu, "view.toggle_detail", "Show/Hide Detail Panel", enabled=False, shortcut="F7"
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
        self._add_action(tools_menu, "tools.console", "Python Console", enabled=False)
        self._add_action(tools_menu, "tools.schema", "Parameter Schema Browser", enabled=False)
        self._add_action(tools_menu, "tools.explain", "Explain Parameter…", enabled=False)
        self._add_action(tools_menu, "tools.preferences", "Preferences…", enabled=False)

        help_menu = bar.addMenu("&Help")
        self._add_action(help_menu, "help.docs", "Documentation", enabled=False)
        self._add_action(help_menu, "help.examples", "Example Configs", enabled=False)
        self._add_action(help_menu, "help.about", "About RADIANT", enabled=False)

    def _build_stage_strip(self) -> None:
        """Empty 9-stage strip placeholder (Phase 4 makes it interactive).

        A named container is created so the Phase 1 Task B theme and the Phase 4
        stage buttons have a stable anchor; it holds no interactive children yet.
        """
        strip = QWidget(self)
        strip.setObjectName("stageStrip")
        # A single non-interactive caption marks the region without pretending
        # to be the finished strip. No colours/fonts set (Task B owns styling).
        caption = QLabel(" · ".join(_STAGE_NAMES), strip)
        caption.setObjectName("stageStripPlaceholder")
        caption.setEnabled(False)
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
        """Empty central visualization area (Phase 3 adds the matplotlib canvas)."""
        central = QWidget(self)
        central.setObjectName("visualizationArea")
        self.setCentralWidget(central)
        self._central = central

    def _build_dock_panels(self) -> None:
        """Empty parameter (left) and detail (bottom) dock panels.

        Phase 2 fills the parameter tree; Phase 4 fills the detail tabs. Here they
        are empty, named, dockable containers so the layout — and later the theme —
        has its anchors from the start.
        """
        param_dock = QDockWidget("Parameters", self)
        param_dock.setObjectName("parameterDock")
        param_dock.setWidget(QWidget(param_dock))
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, param_dock)
        self._parameter_dock = param_dock

        detail_dock = QDockWidget("Detail", self)
        detail_dock.setObjectName("detailDock")
        detail_dock.setWidget(QWidget(detail_dock))
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, detail_dock)
        self._detail_dock = detail_dock

    def _build_status_bar(self) -> None:
        """Status bar with the initial ready/no-config message."""
        message = "Ready" if self._sensor is None else "Ready — sensor loaded"
        self.statusBar().showMessage(message)
