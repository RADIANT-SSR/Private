"""Shared two-point vector helper — tube + cone arrowhead.

Phase 3 (PLAN_v2.md §11 step 1): every geometric vector renders as a tube
with a cone arrowhead at the tip. Replaces the Phase 1 plain tube. The
helper also accepts an optional ``with_break_mark=True`` flag (Phase 3
step 4) that inserts a small zigzag at the midpoint of the line as a
"not to scale" indicator on the satellite/sun connecting rays.

Rule 19 carve-out: shared helper for the vectors/ family per CLAUDE.md
Rule 19's "tightly coupled computations that share internal state or
helper functions" exception. Each named vector keeps its own file.
"""

from __future__ import annotations

import numpy as np
import numpy.typing as npt
import pyvista as pv

# World-space tube radius. Phase 3 keeps the tube radius constant in world
# units; pixel-perfect screen-space line widths are a Phase 5/6 concern.
_TUBE_RADIUS_M = 0.012
_ARROW_TIP_LENGTH_FRAC = 0.10
_ARROW_TIP_RADIUS_M = 0.05

# T7 of the visual remediation: the Phase-3 break-mark used a smoothed
# 4-point spline at 0.7× tube radius, which read as a "wave" rather than
# a "this line is not to scale" symbol. T7 swaps the smoothed spline for
# a sharp Z polyline at full tube radius and widens the amplitude so the
# kink registers immediately at the canonical camera distance.
_BREAK_AMPLITUDE_FRAC = 0.09
_BREAK_HALF_LENGTH_FRAC = 0.06
_BREAK_TUBE_RADIUS_FRAC = 1.0


def add_vector_with_arrow(
    plotter: pv.Plotter,
    start: npt.NDArray[np.float64],
    end: npt.NDArray[np.float64],
    color: str,
    name: str,
    with_break_mark: bool = False,
) -> None:
    """Add a tube from ``start`` → ``end`` with a cone arrowhead at the tip.

    If ``with_break_mark`` is True, also draw a small zigzag at the
    midpoint signaling "not to scale" (used for the satellite and sun
    connecting rays whose schematic length doesn't match the physical
    600 km / 1.5e8 km distances).
    """
    direction = end - start
    length = float(np.linalg.norm(direction))
    if length < 1e-9:
        return
    unit = direction / length

    tip_length = max(length * _ARROW_TIP_LENGTH_FRAC, 0.05)
    shaft_end = end - unit * tip_length

    if with_break_mark:
        # Round-2 R5: split the shaft into two tubes with a gap so the
        # zigzag visibly *replaces* a section of line rather than overlaying
        # one. The plan §6 step 4 is explicit that overlaying loses the
        # "not to scale" semantic. Gap half-extent matches the break-mark's
        # span.
        mid = (start + shaft_end) * 0.5
        half_gap = length * _BREAK_HALF_LENGTH_FRAC
        gap_start = mid - unit * half_gap
        gap_end = mid + unit * half_gap
        seg_a = pv.Line(pointa=tuple(start), pointb=tuple(gap_start)).tube(
            radius=_TUBE_RADIUS_M
        )
        seg_b = pv.Line(pointa=tuple(gap_end), pointb=tuple(shaft_end)).tube(
            radius=_TUBE_RADIUS_M
        )
        blocks = pv.MultiBlock([seg_a, seg_b])
        plotter.add_mesh(blocks, color=color, name=name)
    else:
        line = pv.Line(pointa=tuple(start), pointb=tuple(shaft_end))
        tube = line.tube(radius=_TUBE_RADIUS_M)
        plotter.add_mesh(tube, color=color, name=name)

    arrow = pv.Cone(
        center=tuple(end - unit * (tip_length * 0.5)),
        direction=tuple(unit),
        height=tip_length,
        radius=_ARROW_TIP_RADIUS_M,
        resolution=24,
    )
    plotter.add_mesh(arrow, color=color, name=f"{name}_tip")

    if with_break_mark:
        _add_break_mark(plotter, start, end, length, color, f"{name}_break")


def add_tube(
    plotter: pv.Plotter,
    start: npt.NDArray[np.float64],
    end: npt.NDArray[np.float64],
    color: str,
    name: str,
) -> None:
    """Backwards-compatible plain-tube call — kept for the Phase 1 frames
    triad (body axes / world axes), which renders without arrowheads so
    the small tubes don't visually compete with the main vectors."""
    line = pv.Line(pointa=tuple(start), pointb=tuple(end))
    tube = line.tube(radius=_TUBE_RADIUS_M)
    plotter.add_mesh(tube, color=color, name=name)


def _add_break_mark(
    plotter: pv.Plotter,
    start: npt.NDArray[np.float64],
    end: npt.NDArray[np.float64],
    length: float,
    color: str,
    name: str,
) -> None:
    """Draw a sharp Z-shaped polyline at the line's midpoint.

    T7 of the visual remediation replaced the Phase-3 smoothed spline
    with a sharp polyline so the break reads as an engineering "not to
    scale" symbol rather than a gentle curve. The kink lies in the
    plane spanned by the line direction and the most-vertical
    perpendicular, so it stays oriented sensibly under camera rotation.
    """
    unit = (end - start) / length
    # Pick a perpendicular: prefer +Z; fall back to +X if line is along Z.
    up = np.array([0.0, 0.0, 1.0])
    if abs(np.dot(unit, up)) > 0.95:
        up = np.array([1.0, 0.0, 0.0])
    perp = np.cross(unit, up)
    perp /= np.linalg.norm(perp)

    mid = (start + end) * 0.5
    half_along = length * _BREAK_HALF_LENGTH_FRAC
    amp = length * _BREAK_AMPLITUDE_FRAC

    # Sharp Z: the corners are deliberately *not* smoothed so the break
    # reads as a kink. Each segment becomes its own tube; pv.MultiBlock
    # combines them into one named actor.
    p0 = mid - unit * half_along
    p1 = mid - unit * (half_along * 0.33) + perp * amp
    p2 = mid + unit * (half_along * 0.33) - perp * amp
    p3 = mid + unit * half_along
    radius = _TUBE_RADIUS_M * _BREAK_TUBE_RADIUS_FRAC
    blocks = pv.MultiBlock(
        [
            pv.Line(pointa=tuple(p0), pointb=tuple(p1)).tube(radius=radius),
            pv.Line(pointa=tuple(p1), pointb=tuple(p2)).tube(radius=radius),
            pv.Line(pointa=tuple(p2), pointb=tuple(p3)).tube(radius=radius),
        ]
    )
    plotter.add_mesh(blocks, color=color, name=name)
