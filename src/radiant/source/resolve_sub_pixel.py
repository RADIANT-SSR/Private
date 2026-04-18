"""Path 3 — Sub-pixel parameters target resolver.

See RADIANT_Source_Target_System.md §6.3.
"""

from __future__ import annotations

from radiant.core.regime import RadiometricRegime, TargetInputPath
from radiant.source.protocol import SpectralRadianceSource
from radiant.source.resolved_target import (
    ResolvedTarget,
    validate_range,
)


def resolve_sub_pixel(
    *,
    name: str,
    target_source: SpectralRadianceSource,
    background_source: SpectralRadianceSource,
    fill_fraction: float,
    range_m: float,
    regime_override: RadiometricRegime | None = None,
) -> ResolvedTarget:
    """Path 3 — sub-pixel parameters.

    The radiance_source on the returned ResolvedTarget is the *target*
    source (not the mixed pixel radiance). The fill fraction is stored
    so the chain can perform the mixing. The background_source carries
    L_bg for the noise budget.

    Parameters
    ----------
    name:
        Target label.
    target_source:
        Source for target radiance L_target(λ).
    background_source:
        Source for background radiance L_bg(λ).
    fill_fraction:
        Target fill fraction in [0, 1].
    range_m:
        Observer–target distance [m].
    regime_override:
        Force regime (optional). Defaults to SUB_PIXEL.
    """
    validate_range(range_m)
    if not (0.0 < fill_fraction <= 1.0):
        raise ValueError(
            f"resolve_sub_pixel: fill_fraction must be in (0, 1], "
            f"got {fill_fraction}"
        )

    regime = regime_override or RadiometricRegime.SUB_PIXEL

    return ResolvedTarget(
        name=name,
        input_path=TargetInputPath.SUB_PIXEL,
        derivation_chain=(
            f"sub-pixel: ff={fill_fraction:.6e}",
        ),
        radiance_source=target_source,
        background_source=background_source,
        projected_area_m2=0.0,
        angular_extent_rad=0.0,
        range_m=range_m,
        tentative_regime=regime,
        regime_override=regime_override,
    )
