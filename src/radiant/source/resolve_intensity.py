"""Path 4 — Direct intensity (point source) target resolver.

See RADIANT_Source_Target_System.md §6.4.
"""

from __future__ import annotations

from radiant.core.regime import RadiometricRegime, TargetInputPath
from radiant.source.protocol import SpectralRadianceSource
from radiant.source.resolved_target import (
    ResolvedTarget,
    validate_range,
)


def resolve_direct_intensity(
    *,
    name: str,
    intensity_source: SpectralRadianceSource,
    background_source: SpectralRadianceSource,
    range_m: float,
    regime_override: RadiometricRegime | None = None,
) -> ResolvedTarget:
    """Path 4 — user provides I(λ) directly.

    The ``intensity_source`` is treated as producing intensity values
    (W/sr/µm). It is stored as the radiance_source for chain access;
    the chain uses the POINT_SOURCE regime to interpret it correctly.
    ``projected_area_m2`` is set to 0.

    Parameters
    ----------
    name:
        Target label.
    intensity_source:
        Source producing I(λ) values. For BlackbodyIntensitySource,
        ``spectral_radiance()`` returns ε·B(λ,T) and
        ``spectral_intensity()`` returns A·ε·B(λ,T).
    background_source:
        Background radiance source.
    range_m:
        Observer–target distance [m].
    regime_override:
        Force regime (optional). Defaults to POINT_SOURCE.
    """
    validate_range(range_m)

    regime = regime_override or RadiometricRegime.POINT_SOURCE

    return ResolvedTarget(
        name=name,
        input_path=TargetInputPath.DIRECT_INTENSITY,
        derivation_chain=("user-provided I(λ)",),
        radiance_source=intensity_source,
        background_source=background_source,
        projected_area_m2=0.0,
        angular_extent_rad=0.0,
        range_m=range_m,
        tentative_regime=regime,
        regime_override=regime_override,
    )
