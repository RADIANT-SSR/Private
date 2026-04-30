"""Active-edit highlight overlay — re-stroke a primitive in ACCENT_COLOR.

Phase 5 (PLAN_v2.md §13 step 3): when the user clicks a primitive, the
matching mesh is re-stroked at ``ACCENT_COLOR`` / ``ACCENT_LINE_WIDTH``
so the active selection is visually unambiguous. The animated dashed
pulse (v1's CU-031) is a Phase-5 polish concern that needs a QTimer;
the highlight *placement* is a pure function over actor names and
lives here in the scene library (Qt-free per C7).

What this module does NOT do:
  * It does not own selection state — that's ``InteractionState``.
  * It does not animate — the QTimer driving the pulse lives in the
    Qt shell.
  * It does not pick — that's ``plotter.enable_picking`` in main.py.

What it DOES:
  * Map an active-edit primitive name (``vec_boresight``, ``arc_alpha``,
    etc.) to the set of actor names that should re-stroke.
  * Apply / clear the highlight on a plotter.

Rule 19: own file. Highlighting is its own computation, distinct from
the underlying primitive rendering and from selection state.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

from dev_tools.geometry_gui_v2.scene import style

if TYPE_CHECKING:
    import pyvista as pv


# Each "primitive" the user can click maps to a base actor name. The
# highlight covers the base actor + its tip cone (vectors, arcs) so the
# whole composite is visually selected.
_ACTORS_PER_PRIMITIVE: Final[dict[str, tuple[str, ...]]] = {
    # Vectors: shaft + tip + (for the long-haul vectors) break-mark zigzag.
    # Round-2 R5 restored the break-marks on the boresight and sun-ray
    # only; surface-normal and sun-to-background remain break-mark-less.
    "vec_boresight": ("vec_boresight", "vec_boresight_tip", "vec_boresight_break"),
    "vec_surface_normal": ("vec_surface_normal", "vec_surface_normal_tip"),
    "vec_sun_ray": ("vec_sun_ray", "vec_sun_ray_tip", "vec_sun_ray_break"),
    "vec_sun_to_background": ("vec_sun_to_background", "vec_sun_to_background_tip"),
    # Arcs: tube + tip cone.
    "arc_off_nadir": ("arc_off_nadir", "arc_off_nadir_tip"),
    "arc_phase_angle": ("arc_phase_angle", "arc_phase_angle_tip"),
    "arc_sun_zenith": ("arc_sun_zenith", "arc_sun_zenith_tip"),
    # Glyphs: single actor.
    "glyph_observer": ("glyph_observer",),
    # R3: sun glyph is now disc + 8 ray tubes; highlight covers all 9 actors
    # so clicking any part selects the whole glyph composite.
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
    # Target body.
    "target": ("target",),
}


def selectable_primitives() -> tuple[str, ...]:
    """Return the primitive names a click can resolve to."""
    return tuple(_ACTORS_PER_PRIMITIVE.keys())


def actors_for_primitive(primitive_name: str) -> tuple[str, ...]:
    """Return the actor names that compose ``primitive_name``.

    Raises ``KeyError`` for unknown primitives. The Qt-side picking
    callback should validate the picked name against
    ``selectable_primitives()`` before calling this.
    """
    return _ACTORS_PER_PRIMITIVE[primitive_name]


def apply_highlight(plotter: "pv.Plotter", primitive_name: str | None) -> None:
    """Re-stroke ``primitive_name`` in ACCENT_COLOR; clear when None.

    Stamps the accent color via the actor's GetProperty().SetColor / SetEdgeColor
    on every constituent actor. Restoring the original family color when
    the active edit changes is a Phase-5 polish item — for now we rely
    on a full ``build_scene`` rebuild on selection change to reset.
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
