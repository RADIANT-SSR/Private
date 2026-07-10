"""SourceStage — chain wrapper for target descriptors with regime classification.

Stage 4 Option C — **SourceStage publishes zero radiance**.  All
radiance assembly happens in :class:`AtmosphereStage`.  SourceStage
publishes only descriptors plus tentative regime classification.

Stage outputs under ``stage_outputs["source"]``:
    - ``regime_tentative``: :class:`RadiometricRegime` enum value
    - ``projected_area_m2``: target projected area [m²]
    - ``range_m``: observer-to-target slant range [m]
    - ``fill_fraction``: sub-pixel fill fraction (1.0 = extended)
    - ``angular_extent_rad``: target angular extent [rad]
    - ``regime_override``: raw override string for OpticsStage
    - ``target``: :class:`TargetDescriptor` (T1/T2/T3/T5/T6/T7)
    - ``background``: :class:`BackgroundDescriptor` or ``None``
    - ``los_geometry``: :class:`LineOfSightGeometry` or ``None``

Tentative regime classification (Rule 10 — finalized in OpticsStage):
    angular_extent = sqrt(A_target) / R
    ifov = pixel_pitch / focal_length
    - angular_extent >= 2 × ifov → EXTENDED
    - angular_extent <= 0.25 × ifov → POINT_SOURCE
    - else → SUB_PIXEL
    - fill_fraction < 1.0 overrides to SUB_PIXEL
    - regime_override != "auto" forces the specified regime
"""

from __future__ import annotations

import math

from radiant.core.chain import ChainState
from radiant.core.descriptors import (
    T7IntensityAtSource,
    warn_if_reflective_and_sun_below_horizon,
)
from radiant.core.parameters import ParameterSet
from radiant.core.regime import RadiometricRegime
from radiant.source._inferrer import infer_descriptors


def _classify_regime(
    projected_area_m2: float | None,
    range_m: float | None,
    fill_fraction: float,
    pixel_pitch_m: float,
    focal_length_m: float,
    regime_override: str,
) -> tuple[RadiometricRegime, float]:
    """Tentative regime classification based on IFOV.

    Returns (regime, angular_extent_rad).

    If projected_area_m2 or range_m is None (not provided), defaults to
    EXTENDED regime with angular_extent_rad = inf (target fills the pixel).
    """
    # Override takes priority.
    if regime_override != "auto":
        # Map string to enum.
        regime = RadiometricRegime(regime_override)
        if projected_area_m2 is not None and range_m is not None and range_m > 0.0:
            angular_extent = math.sqrt(projected_area_m2) / range_m
        else:
            angular_extent = 0.0 if regime == RadiometricRegime.POINT_SOURCE else float("inf")
        return regime, angular_extent

    # Fill fraction < 1.0 forces sub-pixel.
    if fill_fraction < 1.0:
        if projected_area_m2 is not None and range_m is not None and range_m > 0.0:
            angular_extent = math.sqrt(projected_area_m2) / range_m
        else:
            angular_extent = 0.0
        return RadiometricRegime.SUB_PIXEL, angular_extent

    # If no geometry provided, default to extended.
    if projected_area_m2 is None or range_m is None or range_m <= 0.0:
        return RadiometricRegime.EXTENDED, float("inf")

    angular_extent = math.sqrt(projected_area_m2) / range_m
    ifov = pixel_pitch_m / focal_length_m

    if angular_extent >= 2.0 * ifov:
        return RadiometricRegime.EXTENDED, angular_extent
    if angular_extent <= 0.25 * ifov:
        return RadiometricRegime.POINT_SOURCE, angular_extent
    return RadiometricRegime.SUB_PIXEL, angular_extent


class SourceStage:
    """Chain stage for target spectral radiance with regime classification."""

    @property
    def name(self) -> str:
        return "source"

    def run(self, state: ChainState, params: ParameterSet) -> ChainState:
        # --- Regime classification ---
        # 0.0 is the sentinel for "not provided" (see _schema.py).
        raw_area: float = params.get("source.target.projected_area_m2")
        raw_range: float = params.get("source.target.range_m")
        projected_area_m2: float | None = raw_area if raw_area > 0.0 else None
        range_m: float | None = raw_range if raw_range > 0.0 else None
        fill_fraction: float = params.get("source.target.fill_fraction")
        regime_override: str = params.get("source.regime_override")

        # Pixel pitch and focal length for IFOV.
        pixel_pitch_m: float = params.get("detector.pixel_pitch_x_um")
        focal_length_m: float = params.get("optics.focal_length_m")

        regime, angular_extent_rad = _classify_regime(
            projected_area_m2=projected_area_m2,
            range_m=range_m,
            fill_fraction=fill_fraction,
            pixel_pitch_m=pixel_pitch_m,
            focal_length_m=focal_length_m,
            regime_override=regime_override,
        )

        # --- Store stage outputs ---
        state = state.with_stage_output(
            "source",
            "regime_tentative",
            regime,
        )
        state = state.with_stage_output(
            "source",
            "projected_area_m2",
            projected_area_m2,
        )
        state = state.with_stage_output("source", "range_m", range_m)
        state = state.with_stage_output(
            "source",
            "fill_fraction",
            fill_fraction,
        )
        state = state.with_stage_output(
            "source",
            "angular_extent_rad",
            angular_extent_rad,
        )
        # Pass through the raw override string so OpticsStage can honor it.
        state = state.with_stage_output(
            "source",
            "regime_override",
            regime_override,
        )

        # --- Option C descriptors — the authoritative Stage 4 output.
        # SourceStage publishes no radiance frames; all radiance assembly
        # happens in AtmosphereStage via :func:`assemble_target_at_aperture`
        # and :func:`assemble_background_at_aperture`.
        target_desc, background_desc, los_geometry = infer_descriptors(
            params=params,
            wavelength_um=state.wavelength_um,
            # CU-008: spectral ε_g(λ) resolved by the API layer (library
            # material / CSV override) and injected pre-chain (Rule 6).
            background_emissivity=state.stage_outputs.get("source_config", {}).get(
                "background_emissivity"
            ),
        )

        # Target Definition Matrix Q3: when the user supplies a geometric
        # shape (shape wins over projected_area_m2), the inferrer writes
        # the shape-derived A onto descriptor.A_t.  Republish it to
        # stage_outputs["source"]["projected_area_m2"] so downstream
        # stages (SpectralIntegrationStage point_source branch, regime
        # reclassification) see the shape area — without this propagation
        # a shape-only scenario reports A=None and spectral integration
        # raises in point/sub-pixel regimes.
        descriptor_area = getattr(target_desc, "A_t", None)
        # T7IntensityAtSource: point-source intensity carries no user A_t,
        # but SpectralIntegrationStage still needs a non-None projected
        # area to compute scene solid angle.  Publish the T7 reference
        # area (A_fict) — it cancels algebraically through the single
        # at-pixel camera equation to recover I · A_collect / R².  See
        # ADR-0004 §Assembly contract.
        if descriptor_area is None and isinstance(target_desc, T7IntensityAtSource):
            descriptor_area = T7IntensityAtSource.REFERENCE_AREA_M2
        if projected_area_m2 is None and descriptor_area is not None:
            projected_area_m2 = float(descriptor_area)
            regime, angular_extent_rad = _classify_regime(
                projected_area_m2=projected_area_m2,
                range_m=range_m,
                fill_fraction=fill_fraction,
                pixel_pitch_m=pixel_pitch_m,
                focal_length_m=focal_length_m,
                regime_override=regime_override,
            )
            state = state.with_stage_output(
                "source",
                "regime_tentative",
                regime,
            )
            state = state.with_stage_output(
                "source",
                "projected_area_m2",
                projected_area_m2,
            )
            state = state.with_stage_output(
                "source",
                "angular_extent_rad",
                angular_extent_rad,
            )

        # Matrix §7 cross-descriptor check: T2Reflective + θ_s > π/2 warns
        # (sun below horizon → zero reflected signal).  Requires both the
        # target descriptor and LOS geometry in scope, so runs here rather
        # than in the T2Reflective.__post_init__ (which only sees the
        # target).
        if los_geometry is not None:
            warn_if_reflective_and_sun_below_horizon(
                target_desc,
                los_geometry.theta_s,
            )

        state = state.with_stage_output("source", "target", target_desc)
        state = state.with_stage_output("source", "background", background_desc)
        return state.with_stage_output("source", "los_geometry", los_geometry)
