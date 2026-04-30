"""PySide6 entry point — the desktop window.

Phase 6 contract (PLAN_v2.md §14): app-shell polish on top of the Phase 5
interaction layer.

Wired in this phase (additive over Phase 5):
  * ``qt-material`` ``dark_teal`` theme applied at startup; user can
    switch to ``light_blue`` or "Follow OS" via the Settings dialog.
  * Real menu bar: File / View / Frame / Scene / Help — see ``_add_menu_bar``.
  * Status bar: left side reuses ``frame_indicator_text`` from Phase 5;
    right side reads ``regime [auto|override]  ·  A_t = ... m²``.
  * Settings + About + Shortcuts dialogs — each in its own module under
    ``app/dialogs/`` (Rule 19).
  * Window state persistence via ``QSettings`` — geometry, dock layout,
    theme, default frame all survive a quit/relaunch.

Unshipped Phase-6 items (filed as CUs in ``docs/Cleanup_Backlog.md``):
  * App icon (CU-041) — needs design pass.
  * Golden screenshot re-lock for both themes × 9 views (CU-042) — blocked
    by the QtInteractor offscreen-GL segfault on this dev machine.
  * Settings dialog units / font-size / label-density extras (CU-040).

D1 (PySide6) is selected via ``QT_API`` *before* importing ``pyvistaqt``;
``pyvistaqt`` honors the ``QT_API`` env var via ``qtpy``.
"""

from __future__ import annotations

import os
import sys

# Pin the Qt binding before any pyvistaqt / qtpy / qt_material import.
os.environ.setdefault("QT_API", "pyside6")

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtGui import QAction, QKeySequence, QShortcut  # noqa: E402
from PySide6.QtWidgets import (  # noqa: E402
    QApplication,
    QComboBox,
    QDialog,
    QDockWidget,
    QFileDialog,
    QFrame,
    QLabel,
    QMainWindow,
    QScrollArea,
    QStatusBar,
    QToolBar,
)
from pyvistaqt import QtInteractor  # noqa: E402

from dev_tools.geometry_gui_v2.app.dialogs.about import AboutDialog  # noqa: E402
from dev_tools.geometry_gui_v2.app.dialogs.settings import SettingsDialog  # noqa: E402
from dev_tools.geometry_gui_v2.app.dialogs.shortcuts import ShortcutsDialog  # noqa: E402
from dev_tools.geometry_gui_v2.app.interaction_state import (  # noqa: E402
    KEY_TO_VIEW,
    CanonicalView,
    DisplayFrame,
    InteractionState,
    frame_indicator_text,
)
from dev_tools.geometry_gui_v2.app.panels.parameters import ParametersPanel  # noqa: E402
from dev_tools.geometry_gui_v2.app.panels.readouts import ReadoutsPanel  # noqa: E402
from dev_tools.geometry_gui_v2.app.state import SceneState  # noqa: E402
from dev_tools.geometry_gui_v2.app.status_bar_text import status_bar_right_text  # noqa: E402
from dev_tools.geometry_gui_v2.app.theme import (  # noqa: E402
    DEFAULT_DARK_THEME,
    apply_theme,
)
from dev_tools.geometry_gui_v2.app.window_persistence import (  # noqa: E402
    load_default_frame,
    load_theme,
    load_window_state,
    save_default_frame,
    save_theme,
    save_window_state,
)
from dev_tools.geometry_gui_v2.scene import build_scene  # noqa: E402
from dev_tools.geometry_gui_v2.scene.camera_views import (  # noqa: E402
    camera_pose_for,
    set_default_camera,
)
from dev_tools.geometry_gui_v2.scene.framing import (  # noqa: E402
    default_camera_distance_m,
)
from dev_tools.geometry_gui_v2.scene.widgets.view_cube import (  # noqa: E402
    build_view_cube_widget,
)
from dev_tools.geometry_gui_v2.scene.widgets.world_axes_gnomon import (  # noqa: E402
    build_world_axes_widget,
)
from dev_tools.geometry_gui_v2.scene.highlight import (  # noqa: E402
    actors_for_primitive,
    apply_highlight,
    selectable_primitives,
)


WINDOW_TITLE = "RADIANT — Geometry"


# Reverse map: actor name → primitive name. Built once at import time so the
# pick callback resolves in O(1). (Phase 5.)
_ACTOR_TO_PRIMITIVE: dict[str, str] = {}
for _primitive in selectable_primitives():
    for _actor in actors_for_primitive(_primitive):
        _ACTOR_TO_PRIMITIVE[_actor] = _primitive


# Display label → primitive name for the Scene → Toggle ... menu entries.
_PRIMITIVE_DISPLAY_NAMES: dict[str, str] = {
    "vec_boresight": "Boresight (b̂)",
    "vec_surface_normal": "Surface normal (n̂)",
    "vec_sun_ray": "Sun ray (ŝ_t)",
    "vec_sun_to_background": "Sun→background (ŝ_B)",
    "arc_off_nadir": "Off-nadir arc (θ_o)",
    "arc_phase_angle": "Phase-angle arc (α_t)",
    "arc_sun_zenith": "Sun-zenith arc (θ_s)",
    "glyph_observer": "Observer glyph",
    "glyph_sun": "Sun glyph",
    "glyph_background": "Background glyph",
    "target": "Target body",
}


class GeometryMainWindow(QMainWindow):
    """Main window — viewport + dual docks + menu bar + status bar.

    Phase 6 polish on top of Phase 5: theme + dialogs + persistence.
    """

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(WINDOW_TITLE)
        self.resize(1280, 800)

        self.plotter = QtInteractor(parent=self)
        self.setCentralWidget(self.plotter.interactor)

        self._state = SceneState.default()
        # Restore the user's preferred default frame (or fall back to Body).
        try:
            persisted_frame = DisplayFrame(load_default_frame("body"))
        except ValueError:
            persisted_frame = DisplayFrame.BODY
        self._interaction = InteractionState(display_frame=persisted_frame)

        self._add_left_dock()
        self._add_right_dock()
        self._add_toolbar()
        self._add_menu_bar()
        self._add_status_bar()
        self._add_frame_indicator_overlay()

        build_scene(self._state, plotter=self.plotter)
        # R1/R2: build_scene installs the round-2 isometric default at the
        # extent-driven distance. Do NOT call ``plotter.reset_camera()``
        # afterward — it would discard the explicit pose and revert to
        # PyVista's default bounding-box framing.

        self._enable_view_cube()
        self._enable_world_axes_gnomon()
        self._enable_picking()
        self._install_shortcuts()
        self._install_label_camera_sync()

        self._readouts_panel.set_state(self._state)
        self._refresh_status_bar()

        # Restore window geometry + dock layout on launch (Phase 6 step 6).
        geom, win_state = load_window_state()
        if geom is not None:
            self.restoreGeometry(geom)
        if win_state is not None:
            self.restoreState(win_state)

    # ----- Layout ---------------------------------------------------------

    def _add_left_dock(self) -> None:
        dock = QDockWidget("Parameters", self)
        dock.setObjectName("dock_parameters")
        dock.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        # R8: build the real parameter panel — sliders, spinboxes, mode
        # toggles. Replaces the CU-043 placeholder. The panel is the
        # single surface for SceneState input; ``state_changed`` is the
        # contract that drives the rebuild path.
        self._parameters_panel = ParametersPanel()
        self._parameters_panel.set_state(self._state)
        self._parameters_panel.state_changed.connect(self._on_parameters_changed)
        scroll = QScrollArea()
        scroll.setWidget(self._parameters_panel)
        scroll.setWidgetResizable(True)
        scroll.setMinimumWidth(220)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setFrameShape(QFrame.NoFrame)
        dock.setWidget(scroll)
        self._left_dock = dock
        self.addDockWidget(Qt.LeftDockWidgetArea, dock)

    def _add_right_dock(self) -> None:
        dock = QDockWidget("Readouts", self)
        dock.setObjectName("dock_readouts")
        dock.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        self._readouts_panel = ReadoutsPanel()
        # R7: populate the Visibility section with one row per toggleable
        # primitive and wire ``visibility_changed`` to the same handler the
        # Scene menu uses. The Scene menu still works; this is an
        # additional surface, not a replacement.
        self._readouts_panel.populate_visibility_toggles(
            list(_PRIMITIVE_DISPLAY_NAMES.items())
        )
        self._readouts_panel.visibility_changed.connect(
            self._on_panel_visibility_toggled
        )
        scroll = QScrollArea()
        scroll.setWidget(self._readouts_panel)
        scroll.setWidgetResizable(True)
        scroll.setMinimumWidth(340)
        # T8 of the visual remediation: suppress the scrollbar artifacts
        # that the first-cut screenshot showed.
        #   - The horizontal scrollbar appeared when section content
        #     overflowed by 1-2 px; the panel is column-rigid by design
        #     so we never want a horizontal scroller.
        #   - The QScrollArea's etched frame border drew a hairline rect
        #     around the entire dock body, fighting the QGroupBox
        #     borders inside.
        # ``ScrollBarAsNeeded`` on the vertical axis stays default — long
        # readout lists (multi-facet explainer text) still need it.
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setFrameShape(QFrame.NoFrame)
        dock.setWidget(scroll)
        self._right_dock = dock
        self.addDockWidget(Qt.RightDockWidgetArea, dock)

    def _add_toolbar(self) -> None:
        toolbar = QToolBar("Frame", self)
        toolbar.setObjectName("toolbar_frame")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        toolbar.addWidget(QLabel("Frame:"))

        self._frame_combo = QComboBox()
        self._frame_combo.setObjectName("frame_combo")
        for frame in DisplayFrame:
            self._frame_combo.addItem(frame.display_name, frame)
        self._frame_combo.setCurrentIndex(
            list(DisplayFrame).index(self._interaction.display_frame)
        )
        self._frame_combo.currentIndexChanged.connect(self._on_frame_changed)
        toolbar.addWidget(self._frame_combo)

    def _add_menu_bar(self) -> None:
        """File / View / Frame / Scene / Help — full Phase-6 menu bar."""
        menubar = self.menuBar()

        # --- File ---------------------------------------------------------
        file_menu = menubar.addMenu("&File")

        new_scene = QAction("&New scene", self)
        new_scene.setShortcut("Ctrl+N")
        new_scene.triggered.connect(self._on_new_scene)
        file_menu.addAction(new_scene)

        save_screenshot = QAction("Save &screenshot…", self)
        save_screenshot.setShortcut("Ctrl+S")
        save_screenshot.triggered.connect(self._on_save_screenshot)
        file_menu.addAction(save_screenshot)

        file_menu.addSeparator()

        quit_action = QAction("&Quit", self)
        quit_action.setShortcut("Ctrl+Q")
        quit_action.triggered.connect(self.close)
        file_menu.addAction(quit_action)

        # --- View ---------------------------------------------------------
        view_menu = menubar.addMenu("&View")

        reset_cam = QAction("&Reset camera", self)
        reset_cam.setShortcut("R")
        reset_cam.triggered.connect(self._reset_camera)
        view_menu.addAction(reset_cam)

        view_menu.addSeparator()

        toggle_left = QAction("Toggle &left panel", self)
        toggle_left.setCheckable(True)
        toggle_left.setChecked(self._left_dock.isVisible())
        toggle_left.toggled.connect(self._left_dock.setVisible)
        view_menu.addAction(toggle_left)

        toggle_right = QAction("Toggle r&ight panel", self)
        toggle_right.setCheckable(True)
        toggle_right.setChecked(self._right_dock.isVisible())
        toggle_right.toggled.connect(self._right_dock.setVisible)
        view_menu.addAction(toggle_right)

        # Toggle view-cube visibility — wired with a noop fallback because
        # the orientation widget may have failed to install on headless GL.
        toggle_cube = QAction("Toggle view &cube", self)
        toggle_cube.setCheckable(True)
        toggle_cube.setChecked(True)
        toggle_cube.toggled.connect(self._toggle_view_cube)
        view_menu.addAction(toggle_cube)
        self._toggle_cube_action = toggle_cube

        # --- Frame --------------------------------------------------------
        frame_menu = menubar.addMenu("F&rame")
        for frame in DisplayFrame:
            act = QAction(f"&{frame.display_name}", self)
            act.setCheckable(True)
            act.setChecked(frame is self._interaction.display_frame)
            act.triggered.connect(
                lambda _checked=False, f=frame: self._select_frame_from_menu(f)
            )
            frame_menu.addAction(act)
        # Track the actions so they stay in sync with the toolbar combo.
        self._frame_menu_actions = {
            frame: act
            for frame, act in zip(DisplayFrame, frame_menu.actions())
        }

        # --- Scene --------------------------------------------------------
        scene_menu = menubar.addMenu("&Scene")
        self._scene_visibility_actions: dict[str, QAction] = {}
        for primitive, label in _PRIMITIVE_DISPLAY_NAMES.items():
            act = QAction(label, self)
            act.setCheckable(True)
            act.setChecked(True)
            act.toggled.connect(
                lambda visible, p=primitive: self._set_primitive_visibility(p, visible)
            )
            scene_menu.addAction(act)
            self._scene_visibility_actions[primitive] = act

        # --- Help ---------------------------------------------------------
        help_menu = menubar.addMenu("&Help")

        shortcuts_action = QAction("&Keyboard shortcuts", self)
        shortcuts_action.setShortcut(QKeySequence("?"))
        shortcuts_action.triggered.connect(self._show_shortcuts_dialog)
        help_menu.addAction(shortcuts_action)

        settings_action = QAction("S&ettings…", self)
        settings_action.triggered.connect(self._show_settings_dialog)
        help_menu.addAction(settings_action)

        about_action = QAction("&About", self)
        about_action.triggered.connect(self._show_about_dialog)
        help_menu.addAction(about_action)

    def _add_status_bar(self) -> None:
        bar = QStatusBar(self)
        bar.setObjectName("status_bar")
        self.setStatusBar(bar)

        # Left widget = frame indicator (re-uses Phase-5 helper).
        self._status_left = QLabel(frame_indicator_text(self._interaction))
        self._status_left.setObjectName("status_frame_indicator")
        bar.addWidget(self._status_left)

        # Right widget = regime + projected area, set by _refresh_status_bar().
        self._status_right = QLabel("")
        self._status_right.setObjectName("status_regime_area")
        bar.addPermanentWidget(self._status_right)

    def _add_frame_indicator_overlay(self) -> None:
        """Top-left HUD label — kept from Phase 5 for redundancy with the
        status-bar text. The overlay is more visible during full-window
        screenshots; the status bar reads when docks are floating."""
        label = QLabel(self.plotter.interactor)
        label.setObjectName("frame_indicator")
        label.setText(frame_indicator_text(self._interaction))
        label.setStyleSheet(
            "color: #E0E5EC; "
            "background-color: rgba(0, 0, 0, 140); "
            "padding: 4px 10px; "
            "border-radius: 4px; "
            "font-family: Menlo, 'JetBrains Mono', monospace; "
            "font-size: 10pt;"
        )
        label.adjustSize()
        label.move(12, 12)
        label.show()
        self._frame_indicator_label = label

    def resizeEvent(self, event):  # type: ignore[no-untyped-def]
        super().resizeEvent(event)
        if hasattr(self, "_frame_indicator_label"):
            self._frame_indicator_label.move(12, 12)

    # ----- Phase 5 interaction wiring (kept) ------------------------------

    def _enable_view_cube(self) -> None:
        """Install the T2 subdued view-cube in the top-right corner.

        Holds a reference to the widget on ``self`` so VTK doesn't garbage-
        collect it. Wires face-click to ``_snap_to_view`` via a custom
        observer.
        """
        try:
            # ``plotter.iren`` is PyVista's RenderWindowInteractor wrapper;
            # ``.interactor`` unwraps to the underlying ``vtkRenderWindowInteractor``
            # the orientation-marker widget needs.
            interactor = self.plotter.iren.interactor
            self._view_cube_widget = build_view_cube_widget(interactor)
        except Exception:
            self._view_cube_widget = None

    def _toggle_view_cube(self, visible: bool) -> None:
        """Show/hide the T2 subdued view-cube widget."""
        widget = getattr(self, "_view_cube_widget", None)
        if widget is None:
            # First-time init failed (no interactor yet); try again.
            if visible:
                self._enable_view_cube()
            return
        try:
            widget.SetEnabled(bool(visible))
            self.plotter.render()
        except Exception:
            pass

    def _enable_world_axes_gnomon(self) -> None:
        """Install the T4 corner gnomon in the bottom-left.

        Same lifecycle constraint as the view-cube: VTK garbage-collects the
        orientation-marker widget if no Python reference is retained, so the
        widget is parked on ``self``.
        """
        try:
            interactor = self.plotter.iren.interactor
            self._world_axes_widget = build_world_axes_widget(interactor)
        except Exception:
            self._world_axes_widget = None

    def _install_label_camera_sync(self) -> None:
        """Re-project label anchors after every camera interaction.

        Labels are screen-space text actors at fixed pixel positions
        (computed from the projected 3D anchor at scene-build time). When
        the user orbits the camera, the 3D anchors move on screen but the
        text actors stay nailed to their original pixels — labels and
        leader lines visibly detach from the diagram. Hooking
        ``EndInteractionEvent`` rebuilds the label set against the new
        projection so they re-attach as soon as the camera comes to rest.
        """
        try:
            interactor = self.plotter.iren.interactor
        except Exception:
            return

        def _on_interaction_end(_obj, _evt) -> None:  # type: ignore[no-untyped-def]
            self._rebuild_labels()

        # ``EndInteractionEvent`` covers orbit / pan (mouse drag), but the
        # scroll-wheel zoom path on PyVistaQt fires its own wheel events
        # without ever entering "interaction." Subscribe to all three so
        # the label re-projection runs after every camera change.
        self._label_sync_obs_ids: list[int] = []
        for evt_name in (
            "EndInteractionEvent",
            "MouseWheelForwardEvent",
            "MouseWheelBackwardEvent",
        ):
            try:
                obs_id = interactor.AddObserver(evt_name, _on_interaction_end)
                self._label_sync_obs_ids.append(obs_id)
            except Exception:
                pass

    def _rebuild_labels(self) -> None:
        from dev_tools.geometry_gui_v2.scene import labels

        try:
            labels.remove_from_plotter(self.plotter)
            labels.add_to_plotter(self.plotter, self._state)
            self.plotter.render()
        except Exception:
            # A label-rebuild failure must never crash the camera loop.
            pass

    def _enable_picking(self) -> None:
        try:
            self.plotter.enable_mesh_picking(
                callback=self._on_pick,
                show_message=False,
                show=False,
                left_clicking=True,
            )
        except Exception:
            pass

    def _on_pick(self, picked_mesh) -> None:  # type: ignore[no-untyped-def]
        if picked_mesh is None:
            self._set_active_edit(None)
            return
        for actor_name, actor in self.plotter.actors.items():
            if getattr(actor, "GetMapper", None) is None:
                continue
            mapper = actor.GetMapper()
            if mapper is None:
                continue
            if mapper.GetInput() is picked_mesh:
                primitive = _ACTOR_TO_PRIMITIVE.get(actor_name)
                if primitive is not None:
                    self._set_active_edit(primitive)
                return

    def _set_active_edit(self, primitive_name: str | None) -> None:
        self._interaction = self._interaction.with_active_edit(primitive_name)
        self.plotter.clear_actors()
        build_scene(self._state, plotter=self.plotter)
        if primitive_name is not None:
            apply_highlight(self.plotter, primitive_name)
        self.plotter.render()

    # ----- Keyboard shortcuts --------------------------------------------

    def _install_shortcuts(self) -> None:
        reset = QShortcut(QKeySequence("R"), self)
        reset.activated.connect(self._reset_camera)

        for key, view in KEY_TO_VIEW.items():
            sc = QShortcut(QKeySequence(key), self)
            sc.activated.connect(lambda v=view: self._snap_to_view(v))

        help_shortcut = QShortcut(QKeySequence("?"), self)
        help_shortcut.activated.connect(self._show_shortcuts_dialog)

    def _reset_camera(self) -> None:
        """R-key / View → Reset camera: recenter on target at default pose.

        R2 of round-2 visual remediation: instead of PyVista's
        ``reset_camera`` (which fits the bbox of all current actors,
        including the 500 m fade plane), recenter to the round-2
        isometric default with the extent-driven distance for the
        current ``SceneState``. ``force=True`` overrides any pose the
        user may have orbited to.
        """
        set_default_camera(
            self.plotter,
            distance=default_camera_distance_m(self._state),
            force=True,
        )
        self._rebuild_labels()
        self.plotter.render()

    def _snap_to_view(self, view: CanonicalView) -> None:
        # R2: route the iso-face click through the same extent-driven
        # default-camera path so clicking the iso face restores the
        # exact pose the app launches with.
        if view is CanonicalView.ISO:
            self._reset_camera()
            self._interaction = self._interaction.with_canonical_view(view)
            return
        position, focal, up = camera_pose_for(view.value)
        self.plotter.camera_position = [position, focal, up]
        self._interaction = self._interaction.with_canonical_view(view)
        self._rebuild_labels()
        self.plotter.render()

    # ----- File menu actions ---------------------------------------------

    def _on_new_scene(self) -> None:
        """Reset SceneState to default and rebuild the scene."""
        self._state = SceneState.default()
        self.plotter.clear_actors()
        build_scene(self._state, plotter=self.plotter)
        # R2: build_scene's set_default_camera is a no-op when the
        # plotter's ``camera_set`` flag is already True (it is, after
        # the prior session). Force the round-2 default so "New scene"
        # actually returns the user to the launch view.
        set_default_camera(
            self.plotter,
            distance=default_camera_distance_m(self._state),
            force=True,
        )
        self._parameters_panel.set_state(self._state)
        self._readouts_panel.set_state(self._state)
        self._refresh_status_bar()

    def _on_parameters_changed(self, state: SceneState) -> None:
        """R8: parameter panel committed a change — rebuild the scene
        and refresh every downstream surface.

        The rebuild path mirrors ``_on_new_scene`` (clear + build) but
        deliberately does *not* call ``set_default_camera`` — a slider
        drag must not snap the user out of their current camera pose.
        ``_rebuild_labels`` re-runs the deconfliction solver against
        the new geometry so anchors stay attached after the geometry
        moves.
        """
        self._state = state
        self.plotter.clear_actors()
        build_scene(self._state, plotter=self.plotter)
        self._rebuild_labels()
        self._readouts_panel.set_state(self._state)
        self._refresh_status_bar()
        self.plotter.render()

    def _on_save_screenshot(self) -> None:
        path, _filter = QFileDialog.getSaveFileName(
            self,
            "Save screenshot",
            "geometry.png",
            "PNG image (*.png);;All files (*)",
        )
        if not path:
            return
        try:
            self.plotter.screenshot(path)
        except Exception:
            # Screenshot can fail on offscreen-GL setups — surfacing in the
            # status bar is more useful than crashing the window.
            self.statusBar().showMessage(
                f"Screenshot failed (offscreen renderer): {path}", 5000
            )

    # ----- Help menu actions ---------------------------------------------

    def _show_shortcuts_dialog(self) -> None:
        ShortcutsDialog(self).exec()

    def _show_about_dialog(self) -> None:
        AboutDialog(self).exec()

    def _show_settings_dialog(self) -> None:
        current_theme = load_theme()
        dlg = SettingsDialog(current_theme, self._interaction.display_frame, self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        new_theme = dlg.selected_theme()
        new_frame = dlg.selected_default_frame()

        # Persist + apply theme. Theme application is on QApplication, not on
        # the window, so the settings dialog itself must close first to avoid
        # a partial-style flash.
        if new_theme != current_theme:
            save_theme(new_theme)
            app = QApplication.instance()
            if app is not None:
                apply_theme(app, new_theme)

        if new_frame is not self._interaction.display_frame:
            save_default_frame(new_frame.value)
            self._frame_combo.setCurrentIndex(list(DisplayFrame).index(new_frame))

    # ----- Frame switcher -------------------------------------------------

    def _on_frame_changed(self, index: int) -> None:
        frame = self._frame_combo.itemData(index)
        if not isinstance(frame, DisplayFrame):
            return
        self._interaction = self._interaction.with_display_frame(frame)

        text = frame_indicator_text(self._interaction)
        self._frame_indicator_label.setText(text)
        self._frame_indicator_label.adjustSize()
        self._status_left.setText(text)

        # Sync the Frame menu radio-style check state.
        if hasattr(self, "_frame_menu_actions"):
            for f, act in self._frame_menu_actions.items():
                act.setChecked(f is frame)

    def _select_frame_from_menu(self, frame: DisplayFrame) -> None:
        idx = list(DisplayFrame).index(frame)
        self._frame_combo.setCurrentIndex(idx)

    # ----- Scene menu (per-primitive visibility) -------------------------

    def _set_primitive_visibility(self, primitive_name: str, visible: bool) -> None:
        for actor_name in actors_for_primitive(primitive_name):
            actor = self.plotter.actors.get(actor_name)
            if actor is None:
                continue
            actor.SetVisibility(bool(visible))
        self.plotter.render()
        # Keep the readouts-panel checkbox in sync — the Scene menu and
        # the panel section are two surfaces over one piece of state.
        # set_primitive_visibility blocks signals on the receiving end so
        # this never re-enters the panel handler.
        self._readouts_panel.set_primitive_visibility(primitive_name, visible)

    def _on_panel_visibility_toggled(
        self, primitive_name: str, visible: bool
    ) -> None:
        """Round-2 R7: receive the panel's eye-icon toggle, apply to the
        plotter, and mirror into the Scene menu's checkable QAction so
        the menu state matches the panel state. This is the inbound side
        of the sync pair; ``_set_primitive_visibility`` is the outbound
        side (Scene menu → plotter + panel).
        """
        for actor_name in actors_for_primitive(primitive_name):
            actor = self.plotter.actors.get(actor_name)
            if actor is None:
                continue
            actor.SetVisibility(bool(visible))
        self.plotter.render()
        action = self._scene_visibility_actions.get(primitive_name)
        if action is not None:
            action.blockSignals(True)
            action.setChecked(bool(visible))
            action.blockSignals(False)

    # ----- Status bar -----------------------------------------------------

    def _refresh_status_bar(self) -> None:
        self._status_right.setText(status_bar_right_text(self._state))

    # ----- Window lifecycle ----------------------------------------------

    def closeEvent(self, event):  # type: ignore[no-untyped-def]
        # Persist window state before tearing down VTK (Phase 6 step 6).
        try:
            save_window_state(self.saveGeometry(), self.saveState())
        except Exception:
            # Persistence failures must never block a clean shutdown.
            pass
        self.plotter.close()
        super().closeEvent(event)


def _verify_mathtext_support() -> None:
    """Warn if VTK math-text is not available (subscripts fall back to ASCII).

    Called once at startup. The remediation T1 spec installs this canary so
    a platform with broken math-text rendering surfaces as a warning rather
    than a silent fallback to underscored labels.
    """
    try:
        import vtk

        renderer = vtk.vtkMathTextFreeTypeTextRenderer()
        if not renderer.MathTextIsSupported():
            import warnings

            warnings.warn(
                "VTK math-text rendering not available on this platform. "
                "Subscript labels will fall back to ASCII. "
                "See REMEDIATION_BLOCKERS.md.",
                stacklevel=2,
            )
    except Exception:  # noqa: BLE001 - vtk import or attr-access; never fatal
        # The check itself must never block app startup. Worst case the user
        # sees no warning; labels render whatever VTK supports.
        pass


def main() -> int:
    """Launch the desktop window. Returns the Qt exit code."""
    _verify_mathtext_support()
    app = QApplication.instance() or QApplication(sys.argv)

    # Apply the persisted theme (or the dark default on first launch).
    theme_xml = load_theme() or DEFAULT_DARK_THEME
    try:
        apply_theme(app, theme_xml)
    except Exception:
        # An unknown / corrupted theme key falls back to the dark default
        # rather than refusing to launch.
        apply_theme(app, DEFAULT_DARK_THEME)

    window = GeometryMainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
