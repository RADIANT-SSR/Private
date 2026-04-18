"""Path 5 — Physical object (expected unresolved) target resolver.

Identical computation to Path 2 (geometry integration), but the user
expects the target to be unresolved.

See RADIANT_Source_Target_System.md §6.5.
"""

from __future__ import annotations

import numpy as np
import numpy.typing as npt

from radiant.core.regime import RadiometricRegime, TargetInputPath
from radiant.source.material import SurfaceMaterial
from radiant.source.protocol import SpectralRadianceSource
from radiant.source.resolved_target import (
    ResolvedTarget,
    angular_extent,
    validate_area,
    validate_range,
)
from radiant.source.shape import TargetShape


def resolve_physical_object(
    *,
    name: str,
    shapes: tuple[TargetShape, ...],
    material: SurfaceMaterial,
    view_direction: npt.NDArray[np.float64],
    background_source: SpectralRadianceSource,
    range_m: float,
    solar_zenith_rad: float | None = None,
    observer_zenith_rad: float = 0.0,
    distance_au: float = 1.0,
    regime_override: RadiometricRegime | None = None,
) -> ResolvedTarget:
    """Path 5 — physical object expected to be unresolved.

    Identical computation to Path 2 (same geometry integration), but
    the user expects the target to be unresolved. The regime hint
    is computed normally and may end up POINT_SOURCE or SUB_PIXEL.

    Parameters
    ----------
    name:
        Target label.
    shapes:
        Tuple of TargetShape primitives.
    material:
        Surface material.
    view_direction:
        Unit 3-vector, target → observer, scene frame.
    background_source:
        Background radiance source.
    range_m:
        Observer–target distance [m].
    solar_zenith_rad:
        Solar zenith [rad]. If None, thermal-only.
    observer_zenith_rad:
        Observer zenith [rad].
    distance_au:
        Sun–target distance [AU].
    regime_override:
        Force regime (optional).
    """
    validate_range(range_m)
    v = np.asarray(view_direction, dtype=np.float64)

    projected_area = sum(s.projected_area(v) for s in shapes)
    validate_area(projected_area)

    source = material.create_source(
        solar_zenith_rad=solar_zenith_rad,
        observer_zenith_rad=observer_zenith_rad,
        distance_au=distance_au,
    )

    ang_ext = angular_extent(projected_area, range_m)
    regime = regime_override or RadiometricRegime.EXTENDED

    return ResolvedTarget(
        name=name,
        input_path=TargetInputPath.PHYSICAL_OBJECT,
        derivation_chain=(
            f"physical object: {len(shapes)} shape(s)",
            f"material: {material.name}",
            f"projected_area: {projected_area:.6e} m²",
        ),
        radiance_source=source,
        background_source=background_source,
        projected_area_m2=projected_area,
        angular_extent_rad=ang_ext,
        range_m=range_m,
        tentative_regime=regime,
        regime_override=regime_override,
        shapes=shapes,
        materials=(material,),
    )
