"""Active-edit highlight overlay — re-stroke a clicked primitive in ``ACCENT_COLOR``.

Lifted (path-rewritten) from the prototype ``scene/highlight.py`` (ADR-0007 Phase 7 Part
B): when the user clicks a primitive (a vector, an arc, a glyph, the target body), the
matching mesh is re-stroked at ``ACCENT_COLOR`` / ``ACCENT_LINE_WIDTH`` so the active
selection is visually unambiguous.

What this module does NOT do:
  * It does not own selection state — the Qt widget does.
  * It does not pick — that is the live interactor's ``enable_point_picking``.

What it DOES:
  * Map a clickable primitive name to the set of actor names that re-stroke together.
  * Apply the highlight on a plotter.

The highlight *placement* is a pure function over actor names (Qt-free). Rule 19: own
file — highlighting is its own computation, distinct from the underlying primitive
rendering and from selection state. Imports only :mod:`scene.style` (no physics stage).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

from radiant.gui.viewer.scene import style

if TYPE_CHECKING:
    import pyvista as pv


# Each clickable "primitive" maps to a base actor name plus any composite parts (tip
# cones, break-marks) so the whole composite re-strokes together.
_ACTORS_PER_PRIMITIVE: Final[dict[str, tuple[str, ...]]] = {
    # Vectors: shaft + tip + (long-haul vectors only) break-mark zigzag.
    "vec_boresight": ("vec_boresight", "vec_boresight_tip", "vec_boresight_break"),
    "vec_surface_normal": ("vec_surface_normal", "vec_surface_normal_tip"),
    "vec_sun_ray": ("vec_sun_ray", "vec_sun_ray_tip", "vec_sun_ray_break"),
    "vec_sun_to_background": ("vec_sun_to_background", "vec_sun_to_background_tip"),
    # Arcs: tube + tip cone.
    "arc_off_nadir": ("arc_off_nadir", "arc_off_nadir_tip"),
    "arc_phase_angle": ("arc_phase_angle", "arc_phase_angle_tip"),
    "arc_sun_zenith": ("arc_sun_zenith", "arc_sun_zenith_tip"),
    # Glyphs.
    "glyph_observer": ("glyph_observer",),
    "glyph_sun": (
        "glyph_sun",
        "glyph_sun_ray_0",
        "glyph_sun_ray_1",
        "glyph_sun_ray_2",
        "glyph_sun_ray_3",
        "glyph_sun_ray_4",
        "glyph_sun_ray_5",
        "glyph_sun_ray_6",
        "glyph_sun_ray_7",
    ),
    "glyph_background": ("glyph_background",),
    # Target body + its RPY triad arms.
    "target": ("target", "body_axis_x", "body_axis_y", "body_axis_z"),
}


def selectable_primitives() -> tuple[str, ...]:
    """Return the primitive names a click can resolve to."""
    return tuple(_ACTORS_PER_PRIMITIVE.keys())


def actors_for_primitive(primitive_name: str) -> tuple[str, ...]:
    """Return the actor names that compose ``primitive_name`` (KeyError if unknown)."""
    return _ACTORS_PER_PRIMITIVE[primitive_name]


def apply_highlight(plotter: pv.Plotter, primitive_name: str | None) -> None:
    """Re-stroke ``primitive_name`` in ``ACCENT_COLOR``; a no-op when ``None``.

    Stamps the accent colour on every constituent actor. Restoring the original family
    colour on a selection change is handled by a full scene rebuild on the next render.
    """
    if primitive_name is None:
        return
    actors = _ACTORS_PER_PRIMITIVE.get(primitive_name)
    if actors is None:
        return
    accent = _hex_to_rgb_float(style.ACCENT_COLOR)
    for actor_name in actors:
        actor = plotter.actors.get(actor_name)
        if actor is None:
            continue
        prop = actor.GetProperty()
        prop.SetColor(*accent)
        prop.SetEdgeColor(*accent)
        prop.SetLineWidth(style.ACCENT_LINE_WIDTH)


def _hex_to_rgb_float(hex_color: str) -> tuple[float, float, float]:
    s = hex_color.lstrip("#")
    return (
        int(s[0:2], 16) / 255.0,
        int(s[2:4], 16) / 255.0,
        int(s[4:6], 16) / 255.0,
    )


__all__ = ["selectable_primitives", "actors_for_primitive", "apply_highlight"]
