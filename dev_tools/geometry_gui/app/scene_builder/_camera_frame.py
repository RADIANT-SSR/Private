"""Camera auto-frame helper.

Phase 11 (PLAN.md §12). Earlier phases used a hard-coded
`camera.eye = (1.8, 1.8, 1.4)` regardless of how far the scene's annotations
extended. When the user dialed up an extreme look angle or relative
azimuth, the off-axis arcs / rays would push outside the camera's frame.
This helper computes the eye distance from the bounding box of the
always-on base-scene traces so the camera stays consistent.

Calibration: for the default `SceneState` the bounding-box half-extent
along the longest axis is ≈ ``REFERENCE_HALF_EXTENT``, and the eye
returned is ``DEFAULT_EYE`` — i.e. unchanged. A regression test pins the
default-state framing to today's value within ε.

This file is internal to the scene-builder package.
"""

from __future__ import annotations

from typing import Final, Iterable

import numpy as np
import plotly.graph_objects as go

# Calibrated to the default-state base scene: observer at distance 4.0
# (−X/+Z), sun glyph at distance 6.0 along the sun direction, and the
# ground patch / background point B clipped at z = -1. The longest
# half-extent is the sun-glyph z-component (≈ +5 for default zenith), so
# we calibrate against the longer extent of the scene rather than the
# fixed sun distance — this keeps the default eye unchanged.
DEFAULT_EYE: Final[tuple[float, float, float]] = (1.8, 1.8, 1.4)
REFERENCE_HALF_EXTENT: Final[float] = 6.0


def _trace_bbox_extents(
    traces: Iterable[go.Mesh3d | go.Scatter3d | go.Cone],
) -> float:
    """Return max(|x|, |y|, |z|) across every trace's coordinate arrays.

    Cones expose `x/y/z` for the tail position; `u/v/w` are vector lengths
    that we add to the tail to get the head, so both endpoints are
    accounted for. Traces with no `x` attribute (or empty arrays) are
    skipped.
    """
    half: float = 0.0
    for trace in traces:
        xs = getattr(trace, "x", None)
        ys = getattr(trace, "y", None)
        zs = getattr(trace, "z", None)
        if xs is None or ys is None or zs is None:
            continue
        x_arr = np.asarray(xs, dtype=np.float64).ravel()
        y_arr = np.asarray(ys, dtype=np.float64).ravel()
        z_arr = np.asarray(zs, dtype=np.float64).ravel()
        if x_arr.size == 0 or y_arr.size == 0 or z_arr.size == 0:
            continue
        u = getattr(trace, "u", None)
        v = getattr(trace, "v", None)
        w = getattr(trace, "w", None)
        if u is not None and v is not None and w is not None:
            u_arr = np.asarray(u, dtype=np.float64).ravel()
            v_arr = np.asarray(v, dtype=np.float64).ravel()
            w_arr = np.asarray(w, dtype=np.float64).ravel()
            if u_arr.size == x_arr.size:
                x_arr = np.concatenate([x_arr, x_arr + u_arr])
                y_arr = np.concatenate([y_arr, y_arr + v_arr])
                z_arr = np.concatenate([z_arr, z_arr + w_arr])
        half = max(
            half,
            float(np.max(np.abs(x_arr))),
            float(np.max(np.abs(y_arr))),
            float(np.max(np.abs(z_arr))),
        )
    return half


def camera_eye_from_traces(
    traces: Iterable[go.Mesh3d | go.Scatter3d | go.Cone],
) -> dict[str, float]:
    """Plotly `camera.eye` dict scaled to the bounding-box half-extent.

    Returns ``DEFAULT_EYE`` for any scene whose half-extent is at or below
    ``REFERENCE_HALF_EXTENT`` (the calibration anchor — default state).
    Larger scenes scale the eye outward so the same fraction of bbox is
    visible.
    """
    half = _trace_bbox_extents(traces)
    if half <= 0.0:
        return {"x": DEFAULT_EYE[0], "y": DEFAULT_EYE[1], "z": DEFAULT_EYE[2]}
    scale = max(1.0, half / REFERENCE_HALF_EXTENT)
    return {
        "x": DEFAULT_EYE[0] * scale,
        "y": DEFAULT_EYE[1] * scale,
        "z": DEFAULT_EYE[2] * scale,
    }
