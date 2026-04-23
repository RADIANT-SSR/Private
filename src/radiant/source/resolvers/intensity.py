"""Path 4 — Direct intensity (point source) target resolver (deprecated).

Deprecated under ADR-0004 in favor of
:class:`~radiant.core.descriptors.T7IntensityAtSource` and the S10
boundary converter :func:`~radiant.source.converters.user_intensity.user_intensity_to_descriptor`.
This legacy resolver returns a :class:`ResolvedTarget` which the
Option C chain does not consume; it is kept for a single release so
out-of-tree callers can migrate, and will be removed in a follow-up.
"""

from __future__ import annotations

import warnings

from radiant.core.regime import RadiometricRegime, TargetInputPath
from radiant.source.protocol import SpectralRadianceSource
from radiant.source.resolvers.resolved_target import (
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
    """Path 4 — user provides I(λ) directly (deprecated, use T7IntensityAtSource).

    .. deprecated::
        ADR-0004: the Option C descriptor surface owns S10 via
        :class:`T7IntensityAtSource`.  This resolver returns a
        :class:`ResolvedTarget`, which the Option C chain does not
        consume.  For new code, construct T7 via
        ``user_intensity_to_descriptor(...)`` or the
        ``source.target.user_intensity_path`` YAML parameter.
    """
    warnings.warn(
        (
            "resolve_direct_intensity is deprecated and will be removed "
            "in a future release.  Use T7IntensityAtSource / "
            "radiant.source.converters.user_intensity.user_intensity_to_descriptor "
            "(ADR-0004) for user-supplied point-source intensity."
        ),
        DeprecationWarning,
        stacklevel=2,
    )
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
