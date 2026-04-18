"""Path 1 — Direct radiance target resolver.

User provides L(λ) directly. See RADIANT_Source_Target_System.md §6.1.
"""

from __future__ import annotations

from radiant.core.regime import RadiometricRegime, TargetInputPath
from radiant.source.protocol import SpectralRadianceSource
from radiant.source.resolved_target import (
    ResolvedTarget,
    angular_extent,
    validate_area,
    validate_range,
)


def resolve_direct_radiance(
    *,
    name: str,
    radiance_source: SpectralRadianceSource,
    background_source: SpectralRadianceSource,
    projected_area_m2: float,
    range_m: float,
    regime_override: RadiometricRegime | None = None,
) -> ResolvedTarget:
    """Path 1 — user provides L(λ) directly.

    Parameters
    ----------
    name:
        Target label.
    radiance_source:
        Source object producing L(λ) [W/m²/sr/µm].
    background_source:
        Source object producing L_bg(λ).
    projected_area_m2:
        Projected area [m²].
    range_m:
        Observer–target distance [m].
    regime_override:
        Force regime classification (optional).
    """
    validate_range(range_m)
    validate_area(projected_area_m2)

    ang_ext = angular_extent(projected_area_m2, range_m)
    regime = regime_override or RadiometricRegime.EXTENDED

    return ResolvedTarget(
        name=name,
        input_path=TargetInputPath.DIRECT_RADIANCE,
        derivation_chain=("user-provided L(λ)",),
        radiance_source=radiance_source,
        background_source=background_source,
        projected_area_m2=projected_area_m2,
        angular_extent_rad=ang_ext,
        range_m=range_m,
        tentative_regime=regime,
        regime_override=regime_override,
    )
