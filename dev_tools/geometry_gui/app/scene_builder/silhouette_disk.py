"""Silhouette disk — visual confirmation that A_t on screen IS the projection.

Draws a translucent flat disk at the target position, oriented perpendicular
to the line-of-sight (target→observer). Its visible *display* size scales
with sqrt(A_t / pi), normalized so a sphere of radius 1 m (A_t = pi m^2)
renders at the same display radius as the target shape mesh
(`TARGET_DISPLAY_RADIUS` from `build_scene`). That keeps the disk visible
across orders of magnitude of real A_t while preserving the "bigger A_t →
bigger silhouette" cue.

Hover text reports A_t in real m^2 — the radiometric number, not the
display-scaled one.

Per Rule 19 (one computation, one module): this disk geometry is its own
file, separate from the shape mesh and the pixel-cell marker.
"""

from __future__ import annotations

import math
from typing import Final

import numpy as np
import numpy.typing as npt
import plotly.graph_objects as go

# Reference: a sphere of radius 1 m has A_t = pi m^2. Render that at exactly
# `TARGET_DISPLAY_RADIUS`, so 1-m sphere mesh and silhouette disk overlap.
# Phase 8 redesign (PLAN.md §11): TARGET_DISPLAY_RADIUS bumped from 0.04 → 1.0.
_REF_AREA_M2: Final[float] = math.pi
_REF_DISPLAY_RADIUS: Final[float] = 1.0  # = TARGET_DISPLAY_RADIUS in build_scene


def _orthonormal_basis(normal: npt.NDArray[np.float64]) -> tuple[
    npt.NDArray[np.float64], npt.NDArray[np.float64]
]:
    """Return two unit vectors spanning the plane orthogonal to `normal`.

    Picks the world axis least aligned with `normal` to avoid a degenerate
    cross product. Result is right-handed: (u, v, normal).
    """
    n = normal / np.linalg.norm(normal)
    helper = np.array([1.0, 0.0, 0.0]) if abs(n[0]) < 0.9 else np.array([0.0, 1.0, 0.0])
    u = np.cross(n, helper)
    u /= np.linalg.norm(u)
    v = np.cross(n, u)
    return u, v


def silhouette_disk_traces(
    target_pos_display: npt.NDArray[np.float64],
    view_dir_scene: npt.NDArray[np.float64],
    projected_area_m2: float,
    *,
    n_segments: int = 64,
) -> list[go.Mesh3d]:
    """Translucent disk perpendicular to `view_dir_scene`, area ∝ A_t.

    Parameters
    ----------
    target_pos_display
        Disk center in scene-display coordinates.
    view_dir_scene
        Unit vector target→observer in the scene frame. The disk's normal
        is set to this vector so the disk presents face-on to the observer
        (this is what "silhouette" means).
    projected_area_m2
        Real-world A_t [m^2]; controls the disk's *display* radius via
        `sqrt(A_t/pi) * (TARGET_DISPLAY_RADIUS/sqrt(REF/pi))` and is shown
        verbatim on hover.
    n_segments
        Number of triangles in the disk fan. 64 keeps the silhouette
        smooth without overwhelming the trace count.

    Returns an empty list when A_t == 0 (edge-on flat plate, zero-size
    shape, etc.) so degenerate cases produce no visible artefact.
    """
    if projected_area_m2 <= 0.0:
        return []

    # Display radius: keep the sphere(R=1m) case at TARGET_DISPLAY_RADIUS.
    real_radius_m = math.sqrt(projected_area_m2 / math.pi)
    ref_real_radius_m = math.sqrt(_REF_AREA_M2 / math.pi)  # = 1.0 m
    display_radius = _REF_DISPLAY_RADIUS * (real_radius_m / ref_real_radius_m)

    u, v = _orthonormal_basis(view_dir_scene)
    angles = np.linspace(0.0, 2.0 * math.pi, n_segments, endpoint=False)
    rim_offsets = (
        np.cos(angles)[:, None] * u[None, :]
        + np.sin(angles)[:, None] * v[None, :]
    ) * display_radius

    center = np.asarray(target_pos_display, dtype=np.float64)
    rim_points = center[None, :] + rim_offsets

    xs = np.concatenate(([center[0]], rim_points[:, 0]))
    ys = np.concatenate(([center[1]], rim_points[:, 1]))
    zs = np.concatenate(([center[2]], rim_points[:, 2]))

    # Triangle fan: (0=center, k+1, ((k+1) % n_segments) + 1) for k in 0..n-1.
    i = np.zeros(n_segments, dtype=np.int64)
    j = np.arange(1, n_segments + 1, dtype=np.int64)
    k = np.array([(idx % n_segments) + 1 for idx in range(1, n_segments + 1)], dtype=np.int64)

    hovertext = f"Silhouette: A_t = {projected_area_m2:.4g} m^2"
    return [
        go.Mesh3d(
            x=xs,
            y=ys,
            z=zs,
            i=i,
            j=j,
            k=k,
            color="cyan",
            opacity=0.25,
            flatshading=True,
            name=f"Silhouette (A_t = {projected_area_m2:.4g} m^2)",
            hovertext=hovertext,
            hoverinfo="text",
            showlegend=True,
        )
    ]
