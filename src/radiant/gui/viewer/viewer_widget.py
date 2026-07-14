"""``GeometryViewer`` — the embedded 3D geometry panel for the Geometry screen.

Renders the static bound scene (:func:`radiant.gui.viewer.scene.build_static_scene`) from
a :class:`~radiant.gui.viewer.viewer_state.ViewerState` after each evaluation. Mounts in
the Geometry stage's center, "3D View" tab (arch doc §4.4, GUI plan Phase 7).

**Three backends, resolved once at construction (GUI plan §4.4, VTK-offscreen risk row).**
Embedding a live ``pyvistaqt.QtInteractor`` needs a real display; under the Qt
``offscreen`` platform plugin its construction *segfaults* (uncatchable), so it is only
attempted when a display is present. The viewer therefore selects, in order:

1. **live** — a ``QtInteractor`` viewport (interactive), when a display can host it;
2. **image** — a static render via ``pyvista.Plotter(off_screen=True)`` shown in a
   ``QLabel`` (Part A is a *static* scene, so an offscreen image is faithful) when a live
   interactor cannot be embedded but VTK renders headless;
3. **unavailable** — an **actionable** panel ("3D viewer unavailable: <reason>; the rest
   of the app works") when even the offscreen render fails.

Every failure is surfaced (logged, and shown when it reaches the panel), never swallowed,
and never crashes the shell (Rules 14/15/17).

All color/typography comes from the QSS theme via object names (GUI plan §4.9); this file
holds no color or font literal (the physics-domain glyph palette the design allows lives
inside the scene library, not here).
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import QApplication, QLabel, QVBoxLayout, QWidget

from radiant.gui.themes.tokens import LIGHT
from radiant.gui.viewer.scene import build_static_scene
from radiant.gui.viewer.viewer_state import ViewerState

if TYPE_CHECKING:
    from radiant.api import ChainResult
    from radiant.gui.themes.tokens import Theme
    from radiant.gui.viewer.viewer_state import ParamGetter

_log = logging.getLogger(__name__)

# Default offscreen render size when the widget has not yet been laid out.
_DEFAULT_IMAGE_SIZE: tuple[int, int] = (960, 640)


def _display_can_host_interactor() -> bool:
    """True when the Qt platform can host a live embedded VTK interactor.

    The ``offscreen`` (and the null ``minimal``) platform plugins cannot: constructing a
    ``QtInteractor`` on them segfaults rather than raising, so it must be avoided
    proactively. A real windowing platform (cocoa / xcb / windows) can.
    """
    app = QApplication.instance()
    if app is None:
        return False
    return app.platformName() not in ("offscreen", "minimal", "")


def _create_interactor(parent: QWidget) -> Any:
    """Create the live ``pyvistaqt.QtInteractor`` for *parent* (isolated for monkeypatch)."""
    from pyvistaqt import QtInteractor

    return QtInteractor(parent)


class GeometryViewer(QWidget):
    """The 3D geometry viewport (live / static-image / actionable-panel).

    Parameters
    ----------
    parent:
        The owning widget, if any.
    theme:
        The design-system theme the viewport chrome follows (default: the light launch
        theme). :meth:`set_theme` re-applies a new theme on the next render (Phase 9).
    """

    def __init__(self, parent: QWidget | None = None, theme: Theme | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("geometryViewer")
        self._theme: Theme = theme if theme is not None else LIGHT
        self._result: ChainResult | None = None
        self._params: ParamGetter | None = None

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(0)

        self._interactor: Any | None = None
        self._image_label: QLabel | None = None
        self._unavailable_reason: str | None = None
        self._mode: str = "unavailable"

        # Part-B view state (angle annotations + RPY triad), both off by default so the
        # first render is the static scene. Mutating either re-renders the bound result.
        self._revealed_arcs: set[str] = set()
        self._show_triad: bool = False

        if _display_can_host_interactor():
            try:
                self._interactor = _create_interactor(self)
            except Exception as exc:  # noqa: BLE001 — surfaced, not swallowed
                _log.warning("live 3D interactor unavailable, falling back to image: %s", exc)
                self._begin_image_mode()
            else:
                self._layout.addWidget(self._interactor)
                self._mode = "live"
        else:
            # Headless / offscreen: a live interactor would segfault — render statically.
            self._begin_image_mode()

    # -- backend setup -----------------------------------------------------

    def _begin_image_mode(self) -> None:
        """Enter the static-image backend (a ``QLabel`` populated on each render)."""
        self._image_label = QLabel("", self)
        self._image_label.setObjectName("geometryViewerImage")
        self._image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._layout.addWidget(self._image_label)
        self._mode = "image"

    def _enter_unavailable(self, reason: str) -> None:
        """Replace the viewport with the actionable degradation panel."""
        if self._image_label is not None:
            self._image_label.setParent(None)
            self._image_label.deleteLater()
            self._image_label = None
        self._interactor = None
        self._unavailable_reason = reason
        self._mode = "unavailable"
        panel = QLabel(
            f"3D viewer unavailable: {reason}\n\n"
            "The rest of the app works — the geometry angles and ranges are on the "
            "Inputs tab. A working OpenGL/VTK stack is needed to enable the 3D view.",
            self,
        )
        panel.setObjectName("viewerUnavailable")
        panel.setWordWrap(True)
        panel.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._layout.addWidget(panel)
        _log.warning("3D geometry viewer unavailable: %s", reason)

    # -- accessors ---------------------------------------------------------

    @property
    def mode(self) -> str:
        """The active backend: ``"live"``, ``"image"``, or ``"unavailable"``."""
        return self._mode

    @property
    def is_available(self) -> bool:
        """True when a scene is shown (live viewport or static image)."""
        return self._mode in ("live", "image")

    @property
    def is_degraded(self) -> bool:
        """True when the actionable degradation panel is shown."""
        return self._mode == "unavailable"

    @property
    def unavailable_reason(self) -> str | None:
        """The degradation reason string, or ``None`` when a scene is shown."""
        return self._unavailable_reason

    @property
    def interactor(self) -> Any | None:
        """The embedded live ``QtInteractor`` (``None`` unless mode is ``"live"``)."""
        return self._interactor

    @property
    def revealed_angles(self) -> frozenset[str]:
        """The angle-annotation names currently revealed in the scene (Part B)."""
        return frozenset(self._revealed_arcs)

    @property
    def triad_visible(self) -> bool:
        """True when the target RPY body-axes triad is shown (Part B)."""
        return self._show_triad

    # -- Part-B view controls ----------------------------------------------

    def set_angle_revealed(self, name: str, revealed: bool) -> None:
        """Reveal (or hide) the named angle annotation and re-render.

        *name* is an ``angle_annotations`` catalog name (``"off_nadir"`` / ``"sun_zenith"``
        / ``"phase_angle"``). A no-op when the state is unchanged so redundant toggles do
        not force a re-render.
        """
        changed = (name in self._revealed_arcs) != revealed
        if revealed:
            self._revealed_arcs.add(name)
        else:
            self._revealed_arcs.discard(name)
        if changed:
            self._rerender()

    def set_triad_visible(self, visible: bool) -> None:
        """Show or hide the target RPY body-axes triad and re-render."""
        if visible == self._show_triad:
            return
        self._show_triad = visible
        self._rerender()

    def _rerender(self) -> None:
        """Re-render the currently bound result with the current Part-B view state."""
        if self._result is not None and self._params is not None:
            self.show_result(self._result, self._params)

    # -- rendering ---------------------------------------------------------

    def set_theme(self, theme: Theme) -> None:
        """Adopt *theme* and re-render if a result is already bound (Phase 9 toggle)."""
        self._theme = theme
        if self._result is not None and self._params is not None:
            self.show_result(self._result, self._params)

    def show_result(self, result: ChainResult, params: ParamGetter) -> None:
        """Render the static scene bound to *result* (+ its *params*) after an evaluate.

        A no-op when already degraded. *params* is the parameter read surface (the live
        :class:`~radiant.api.Sensor`) the adapter needs for the target shape and sampling.
        A render failure surfaces the actionable panel rather than raising.
        """
        self._result = result
        self._params = params
        if self._mode == "unavailable":
            return
        state = ViewerState.from_chain_result(result, params)
        try:
            if self._mode == "live":
                self._render_live(state)
            else:
                self._render_image(state)
        except Exception as exc:  # noqa: BLE001 — degrade to the actionable panel
            self._enter_unavailable(str(exc))

    def _arc_value_texts(self) -> dict[str, str]:
        """Format the stage-output value for each revealed, stage-backed angle arc.

        The value is read **verbatim** from ``stage_outputs["geometry"]`` (the single
        source of angle truth, arch doc §6.3) and formatted with its ``rad`` unit exactly
        as the shared readout does — never recomputed from the scene geometry. Arcs with
        no stage-output key (the phase angle) are absent, so they render symbol-only.
        """
        from radiant.gui.param_format import format_value
        from radiant.gui.viewer.scene import angle_annotations

        if self._result is None:
            return {}
        geometry = self._result.stage_outputs.get("geometry", {})
        texts: dict[str, str] = {}
        for name in self._revealed_arcs:
            key = angle_annotations.annotation(name).stage_key
            if key is not None and key in geometry:
                texts[name] = format_value(geometry[key], "rad")
        return texts

    def _render_live(self, state: ViewerState) -> None:
        """Rebuild the live interactor's scene from *state*."""
        assert self._interactor is not None
        self._interactor.clear()
        build_static_scene(
            state,
            plotter=self._interactor,
            theme=self._theme,
            revealed_arcs=tuple(self._revealed_arcs),
            arc_value_texts=self._arc_value_texts(),
            show_triad=self._show_triad,
        )
        self._interactor.render()

    def _render_image(self, state: ViewerState) -> None:
        """Render *state* offscreen and show it in the image label."""
        assert self._image_label is not None
        width = max(self._image_label.width(), _DEFAULT_IMAGE_SIZE[0])
        height = max(self._image_label.height(), _DEFAULT_IMAGE_SIZE[1])
        arr = self._render_offscreen_array(state, (width, height))
        arr = np.ascontiguousarray(arr[:, :, :3], dtype=np.uint8)
        h, w, _ = arr.shape
        image = QImage(arr.tobytes(), w, h, 3 * w, QImage.Format.Format_RGB888)
        self._image_label.setPixmap(QPixmap.fromImage(image))

    def _render_offscreen_array(self, state: ViewerState, size: tuple[int, int]) -> np.ndarray:
        """Render *state* with an offscreen ``pyvista.Plotter`` and return the RGB array."""
        import pyvista as pv

        plotter = pv.Plotter(off_screen=True, window_size=list(size))
        try:
            build_static_scene(
                state,
                plotter=plotter,
                theme=self._theme,
                revealed_arcs=tuple(self._revealed_arcs),
                arc_value_texts=self._arc_value_texts(),
                show_triad=self._show_triad,
            )
            return np.asarray(plotter.screenshot(return_img=True))
        finally:
            plotter.close()

    def close_viewer(self) -> None:
        """Release the live interactor's render window (teardown / test cleanup)."""
        if self._interactor is not None:
            self._interactor.close()


__all__ = ["GeometryViewer"]
