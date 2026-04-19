"""SourceStage — chain wrapper for target spectral radiance with regime classification.

Wraps :class:`~radiant.source.emitted.ThermalSource` into the
:class:`~radiant.core.chain.Stage` protocol. Handles thermal
self-emission, tentative regime classification (IFOV-based), and
background radiance for sub-pixel mixing.

Produces
--------
Frame ``"at_target"`` with spectral radiance ``L(λ) = ε · B(λ, T)``
in W/m²/sr/µm.

Stage outputs under ``stage_outputs["source"]``:
    - ``regime_tentative``: :class:`RadiometricRegime` enum value
    - ``projected_area_m2``: target projected area [m²]
    - ``range_m``: observer-to-target slant range [m]
    - ``fill_fraction``: sub-pixel fill fraction (1.0 = extended)
    - ``L_background``: spectral radiance array for background [W/m²/sr/µm]
    - ``angular_extent_rad``: target angular extent [rad]

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

from radiant.core.blackbody import planck_spectral_radiance
from radiant.core.chain import ChainState
from radiant.core.parameters import ParameterSet
from radiant.core.radiometry import RadiometricFrame
from radiant.core.regime import RadiometricRegime
from radiant.source._inferrer import infer_descriptors
from radiant.source.emitted import ThermalSource


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
        temperature_K: float = params.get("source.target.temperature")
        emissivity: float = params.get("source.target.emissivity")

        source = ThermalSource(
            temperature_K=temperature_K,
            emissivity=emissivity,
            name="target",
        )

        L_target = source.spectral_radiance(state.wavelength_um)

        frame = RadiometricFrame(
            name="at_target",
            wavelength_um=state.wavelength_um,
            spectral_radiance=L_target,
            notes=f"Thermal: ε={emissivity}, T={temperature_K} K",
        )
        state = state.with_frame(frame)

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

        # --- Background radiance ---
        bg_temperature_K: float = params.get("source.background.temperature")
        bg_emissivity: float = params.get("source.background.emissivity")
        L_background = bg_emissivity * planck_spectral_radiance(
            state.wavelength_um, bg_temperature_K
        )

        # --- Store stage outputs ---
        state = state.with_stage_output(
            "source", "regime_tentative", regime,
        )
        state = state.with_stage_output(
            "source", "projected_area_m2", projected_area_m2,
        )
        state = state.with_stage_output("source", "range_m", range_m)
        state = state.with_stage_output(
            "source", "fill_fraction", fill_fraction,
        )
        state = state.with_stage_output(
            "source", "L_background", L_background,
        )
        state = state.with_stage_output(
            "source", "angular_extent_rad", angular_extent_rad,
        )
        # Pass through the raw override string so OpticsStage can honor it.
        state = state.with_stage_output(
            "source", "regime_override", regime_override,
        )

        # --- Option C descriptors (Stage 2 — additive bridge) ---
        # ADR-0002: SourceStage publishes TargetDescriptor +
        # BackgroundDescriptor + LineOfSightGeometry alongside the legacy
        # radiance frame and L_background stage_output.  Stage 3 starts
        # consuming these; Stage 4 removes the legacy path.  Zero
        # downstream stage reads these new keys today, so the additive
        # wiring is a pure superset of the current contract.
        target_desc, background_desc, los_geometry = infer_descriptors(
            params=params,
            wavelength_um=state.wavelength_um,
        )
        state = state.with_stage_output("source", "target", target_desc)
        state = state.with_stage_output("source", "background", background_desc)
        return state.with_stage_output("source", "los_geometry", los_geometry)
