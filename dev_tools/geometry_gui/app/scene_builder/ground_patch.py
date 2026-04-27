"""Ground patch — replaces the full Earth sphere in the target-centric layout.

Phase 8 redesign (PLAN.md §11): the Earth no longer dominates the figure. We
draw only a curved cap of the surface beneath the target, sized so its
curvature is just-visible and it acts as a horizon reference rather than the
scene's main object. Day/night terminator shading still uses the sun direction.

The cap is a parametric piece of the Earth-radius sphere, but rendered in
display units where the cap's lateral extent is `GROUND_PATCH_HALF_EXTENT`
(display) and the target sits roughly `BACKGROUND_DISPLAY_DISTANCE_BELOW_TARGET`
above the surface. Real altitudes are reported in glyph labels, not encoded
in scene position (PLAN.md C7).
"""

from __future__ import annotations

from typing import Final

import numpy as np
import numpy.typing as npt
import plotly.graph_objects as go

# Display-frame extent of the visible ground patch, half-side in display units.
GROUND_PATCH_HALF_EXTENT: Final[float] = 2.5

# Target sits this far above the patch in display units (illustrative — true
# altitudes are reported in the readout / glyph labels per C7).
BACKGROUND_DISPLAY_DISTANCE_BELOW_TARGET: Final[float] = 1.5

# Curvature: the patch is a cap of a sphere whose center is below the patch by
# this much. Larger ⇒ flatter-looking cap. 6.0 keeps just-visible curvature
# across the half-extent.
_CAP_SPHERE_RADIUS: Final[float] = 6.0

_N_U: Final[int] = 24
_N_V: Final[int] = 24

_DAY_COLOR: Final[str] = "#7fa07f"  # green-ish ground
_NIGHT_COLOR: Final[str] = "#2b3b2b"  # dark ground (night-side cap)


def ground_patch_traces(
    sun_dir_scene: npt.NDArray[np.float64] | None = None,
) -> list[go.Mesh3d]:
    """Curved-cap ground beneath the target.

    The cap center sits at (0, 0, target_z - BACKGROUND_DISPLAY_DISTANCE_BELOW_TARGET)
    and the patch covers x, y in [-GROUND_PATCH_HALF_EXTENT, +GROUND_PATCH_HALF_EXTENT].
    `sun_dir_scene` (toward the sun) shades vertices on the night side darker;
    `None` paints the whole patch with `_DAY_COLOR`.
    """
    u = np.linspace(-GROUND_PATCH_HALF_EXTENT, GROUND_PATCH_HALF_EXTENT, _N_U)
    v = np.linspace(-GROUND_PATCH_HALF_EXTENT, GROUND_PATCH_HALF_EXTENT, _N_V)
    uu, vv = np.meshgrid(u, v, indexing="ij")
    # Curved cap: z = z0 - (R - sqrt(R^2 - x^2 - y^2)). The patch's apex sits
    # at z = z0 (highest point) and falls off at the edges.
    rho2 = uu**2 + vv**2
    rho2 = np.minimum(rho2, _CAP_SPHERE_RADIUS**2 - 1e-9)
    z_local = -(_CAP_SPHERE_RADIUS - np.sqrt(_CAP_SPHERE_RADIUS**2 - rho2))
    z_offset = -BACKGROUND_DISPLAY_DISTANCE_BELOW_TARGET

    x = uu.ravel()
    y = vv.ravel()
    z = (z_local + z_offset).ravel()

    base_kwargs: dict = dict(
        x=x,
        y=y,
        z=z,
        alphahull=0,
        opacity=0.55,
        name="Ground (illustrative)",
        hoverinfo="name",
        showscale=False,
    )

    if sun_dir_scene is None:
        return [go.Mesh3d(color=_DAY_COLOR, **base_kwargs)]

    n = np.asarray(sun_dir_scene, dtype=np.float64)
    n = n / np.linalg.norm(n)
    # Surface normal at each cap vertex points from the (virtual) cap-sphere
    # center upward through the vertex. Center is at (0,0,z_offset - R).
    cap_center_z = z_offset - _CAP_SPHERE_RADIUS
    normals = np.column_stack([x, y, z - cap_center_z])
    norms = np.linalg.norm(normals, axis=1, keepdims=True)
    normals /= norms
    illum = normals @ n
    vertex_colors = np.where(illum >= 0.0, _DAY_COLOR, _NIGHT_COLOR)
    base_kwargs.pop("color", None)
    return [go.Mesh3d(vertexcolor=vertex_colors, **base_kwargs)]
