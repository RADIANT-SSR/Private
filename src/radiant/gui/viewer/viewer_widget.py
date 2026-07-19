"""``GeometryViewer`` — the embedded 2D geometry schematic for the Geometry screen.

Renders the not-to-scale orthographic **schematic** (:class:`~radiant.gui.viewer.
schematic_view.SchematicView`) from a
:class:`~radiant.gui.viewer.viewer_state.ViewerState` after each evaluation. Mounts in the
Geometry stage's center, "Schematic" tab (arch doc §4.4 / §6).

**2D schematic pivot (ADR-0007 superseded 2026-07-14).** This widget was a PyVista/VTK
raster viewer with a three-backend degradation ladder (live ``QtInteractor`` / offscreen
image / actionable panel) because embedding VTK needs a real display and segfaults under
the Qt ``offscreen`` platform. The owner ratified replacing it with a pure-Qt 2D
orthographic schematic that reproduces the SVG-line-art mockup faithfully. A QPainter
canvas has **no** VTK/OpenGL dependency, so:

* the "3D viewer unavailable" fragility is **gone** — a 2D widget renders anywhere Qt
  runs, including the headless ``offscreen`` platform, with `QWidget.grab()` fully
  faithful (no segfault-prone live interactor);
* re-renders are a plain :meth:`~PySide6.QtWidgets.QWidget.update` — the live-repaint class
  of bug (owner report 2026-07-14: VTK ``render()`` not driving the Qt repaint) cannot
  occur.

A **minimal** guard remains: if building the scene from a result raises, an actionable
panel replaces the canvas (Rules 15/17) — but for a pure-Qt widget this is effectively
unreachable. The public surface :class:`~radiant.gui.widgets.stage_center.StagePane`
relies on is preserved: :meth:`show_result`, :meth:`set_angle_revealed` /
:meth:`set_triad_visible` (Pass 2 — these now reveal the angle arcs and the RPY triad on
the canvas and repaint), :meth:`close_viewer`, :meth:`set_theme`, and the availability
properties.

All colour/typography comes from the theme tokens + the allowlisted glyph palette (§4.9);
this file holds no colour or font literal.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from radiant.gui.themes.tokens import LIGHT
from radiant.gui.viewer.schematic_view import SchematicView
from radiant.gui.viewer.viewer_state import ViewerState

if TYPE_CHECKING:
    from radiant.api import ChainResult
    from radiant.gui.themes.tokens import Theme
    from radiant.gui.viewer.viewer_state import ParamGetter

_log = logging.getLogger(__name__)


class GeometryViewer(QWidget):
    """The 2D geometry schematic viewport (crisp orthographic line-art).

    Parameters
    ----------
    parent:
        The owning widget, if any.
    theme:
        The design-system theme the chrome follows (default: the light launch theme).
        :meth:`set_theme` re-applies a new theme (Phase 9).
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

        # View state (angle annotations + RPY triad) mirrored to the canvas on each toggle.
        self._revealed_arcs: set[str] = set()
        self._show_triad: bool = False

        self._canvas: SchematicView | None = SchematicView(self, theme=self._theme)
        self._layout.addWidget(self._canvas)
        # The bottom-left ANGLES reveal selector lives on the canvas (owner feedback
        # 2026-07-14 — moved out of the right-column accordion onto the plot). Wire each
        # toggle to the same reveal path the accordion used: checkbox → set_angle_revealed →
        # arc repaint. The overlay is a child of the canvas; the viewer owns the wiring.
        self._canvas.angle_overlay.angleToggled.connect(self.set_angle_revealed)
        self._unavailable_reason: str | None = None
        self._unavailable_panel: QLabel | None = None
        self._mode: str = "schematic"

    # -- accessors ---------------------------------------------------------

    @property
    def mode(self) -> str:
        """The active backend: ``"schematic"`` (drawn) or ``"unavailable"`` (guard hit)."""
        return self._mode

    @property
    def is_available(self) -> bool:
        """True when the schematic canvas is shown."""
        return self._mode == "schematic"

    @property
    def is_degraded(self) -> bool:
        """True when the (effectively unreachable) actionable guard panel is shown."""
        return self._mode == "unavailable"

    @property
    def unavailable_reason(self) -> str | None:
        """The degradation reason string, or ``None`` when the schematic is shown."""
        return self._unavailable_reason

    @property
    def canvas(self) -> SchematicView | None:
        """The embedded schematic canvas (``None`` only if the guard panel replaced it)."""
        return self._canvas

    @property
    def revealed_angles(self) -> frozenset[str]:
        """The angle-annotation names currently revealed on the canvas."""
        return frozenset(self._revealed_arcs)

    @property
    def triad_visible(self) -> bool:
        """True when the target RPY triad is drawn on the canvas."""
        return self._show_triad

    # -- Pass-2 view controls (arcs + RPY triad; CU-128 / CU-130) -----------

    def set_angle_revealed(self, name: str, revealed: bool) -> None:
        """Reveal/hide the *name* angle arc on the canvas and repaint (CU-128)."""
        if revealed:
            self._revealed_arcs.add(name)
        else:
            self._revealed_arcs.discard(name)
        if self._canvas is not None:
            self._canvas.set_revealed_angles(self._revealed_arcs)

    def set_triad_visible(self, visible: bool) -> None:
        """Show/hide the on-target RPY triad on the canvas and repaint (CU-130)."""
        self._show_triad = visible
        if self._canvas is not None:
            self._canvas.set_triad_visible(visible)

    # -- rendering ---------------------------------------------------------

    def set_theme(self, theme: Theme) -> None:
        """Adopt *theme* and repaint the canvas (Phase-9 toggle)."""
        self._theme = theme
        if self._canvas is not None:
            self._canvas.set_theme(theme)

    def show_result(self, result: ChainResult, params: ParamGetter) -> None:
        """Render the schematic bound to *result* (+ its *params*) after an evaluate.

        *params* is the parameter read surface (the live :class:`~radiant.api.Sensor`) the
        adapter needs for the target shape and sampling. A build failure surfaces the
        actionable guard panel rather than raising (Rules 15/17) — effectively unreachable
        for a pure-Qt widget, but kept so a malformed result never crashes the shell.
        The guard panel is **not** one-way (CU-163): a later evaluate that builds cleanly
        tears the panel down and restores the schematic, so one transient adapter error
        never disables the viewer for the rest of the session.
        """
        self._result = result
        self._params = params
        # Build the state first; only touch the canvas/panel on the known outcome.
        try:
            state = ViewerState.from_chain_result(result, params)
        except Exception as exc:  # noqa: BLE001 — degrade to the actionable panel
            self._enter_unavailable(str(exc))
            return
        # Clean build: restore the schematic canvas if the guard panel is up (CU-163).
        if self._mode == "unavailable" or self._canvas is None:
            self._restore_canvas()
        try:
            self._canvas.set_state(state)
        except Exception as exc:  # noqa: BLE001 — a render failure still degrades gracefully
            self._enter_unavailable(str(exc))

    def _enter_unavailable(self, reason: str) -> None:
        """Replace the canvas with the actionable guard panel (minimal; recoverable)."""
        if self._canvas is not None:
            self._canvas.setParent(None)
            self._canvas.deleteLater()
            self._canvas = None
        # A stale panel from an earlier failure is replaced, not stacked.
        if self._unavailable_panel is not None:
            self._unavailable_panel.setParent(None)
            self._unavailable_panel.deleteLater()
            self._unavailable_panel = None
        self._unavailable_reason = reason
        self._mode = "unavailable"
        panel = QLabel(
            f"Geometry schematic unavailable: {reason}\n\n"
            "The rest of the app works — the geometry angles and ranges are on the "
            "Inputs tab.",
            self,
        )
        panel.setObjectName("viewerUnavailable")
        panel.setWordWrap(True)
        panel.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._layout.addWidget(panel)
        self._unavailable_panel = panel
        _log.warning("geometry schematic unavailable: %s", reason)

    def _restore_canvas(self) -> None:
        """Rebuild the schematic canvas after the guard panel was shown (CU-163).

        Inverse of :meth:`_enter_unavailable`: drop the panel, recreate the
        :class:`SchematicView`, re-wire the angle-overlay signal, and re-apply
        the mirrored view state (theme, revealed arcs, triad) so the restored
        schematic matches the widget's current controls.
        """
        if self._unavailable_panel is not None:
            self._unavailable_panel.setParent(None)
            self._unavailable_panel.deleteLater()
            self._unavailable_panel = None
        self._canvas = SchematicView(self, theme=self._theme)
        self._layout.addWidget(self._canvas)
        self._canvas.angle_overlay.angleToggled.connect(self.set_angle_revealed)
        self._canvas.set_revealed_angles(self._revealed_arcs)
        self._canvas.set_triad_visible(self._show_triad)
        self._unavailable_reason = None
        self._mode = "schematic"

    def close_viewer(self) -> None:
        """Teardown hook (no VTK render window to release — kept for surface parity)."""


__all__ = ["GeometryViewer"]
