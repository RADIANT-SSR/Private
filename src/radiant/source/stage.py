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
    - ``reflectance``: resolved target ρ(λ) as :class:`SpectralData`
      (dimensionless, on the chain grid) — present **only** for the two
      descriptors that carry a reflectance: ``T2Reflective`` (the
      ``ReflectanceDescriptor`` protocol) and ``T3Mixed`` (Kirchhoff
      ρ = 1 − ε).  Absent otherwise.  Purely additive: it is the surface
      property the analyst typed, published so the GUI can plot it; the
      radiance path resolves ρ through the same
      :mod:`radiant.core.target_reflectance` resolver (Rule 19) and is
      unchanged by this output.

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
from radiant.core.parameters import ParameterSet, Provenance
from radiant.core.regime import (
    REGIME_EXTENDED_IFOV_MULTIPLE,
    REGIME_POINT_SOURCE_IFOV_MULTIPLE,
    RadiometricRegime,
)
from radiant.core.spectral import SpectralData
from radiant.core.target_reflectance import target_reflectance_on_grid
from radiant.source._inferrer import infer_descriptors
from radiant.source.fill_fraction import fill_fraction_from_area


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

    if angular_extent >= REGIME_EXTENDED_IFOV_MULTIPLE * ifov:
        return RadiometricRegime.EXTENDED, angular_extent
    if angular_extent <= REGIME_POINT_SOURCE_IFOV_MULTIPLE * ifov:
        return RadiometricRegime.POINT_SOURCE, angular_extent
    return RadiometricRegime.SUB_PIXEL, angular_extent


# Canonical display units for this stage's scalar ``stage_outputs`` (CU-118) —
# declared next to the ``with_stage_output(...)`` emission sites and aggregated by
# ``radiant.api.stage_output_units``. "" marks a dimensionless numeric (bare number).
OUTPUT_UNITS: dict[str, str] = {
    "projected_area_m2": "m²",
    "range_m": "m",
    "fill_fraction": "",
    "angular_extent_rad": "rad",
}


class SourceStage:
    """Chain stage for target spectral radiance with regime classification."""

    @property
    def name(self) -> str:
        return "source"

    def run(self, state: ChainState, params: ParameterSet) -> ChainState:
        # --- Regime classification ---
        # 0.0 is the sentinel for "not provided" (see _schema.py).
        # Canonical name geometry.target.projected_area_m2 (ADR-0008); the
        # old source.target.projected_area_m2 survives as a deprecated alias.
        raw_area: float = params.get("geometry.target.projected_area_m2")
        # Canonical name geometry.target_range_m (ADR-0006); the old
        # source.target.range_m survives as a deprecated alias for users.
        raw_range: float = params.get("geometry.target_range_m")
        projected_area_m2: float | None = raw_area if raw_area > 0.0 else None
        range_m: float | None = raw_range if raw_range > 0.0 else None
        # Gap 98 C: when the target range is not set explicitly, fall back to the
        # slant range GeometryStage derived (ADR-0006 — from altitude + zenith, or
        # the orbit/site modes). Previously source.range_m was None whenever
        # geometry.target_range_m was unset, so the point_source signal (which reads
        # source.range_m) failed even though the chain already knew the slant range.
        if range_m is None:
            derived_range = state.stage_outputs.get("geometry", {}).get("slant_range_m")
            if derived_range is not None and derived_range > 0.0:
                range_m = float(derived_range)
        fill_fraction: float = params.get("source.target.fill_fraction")
        regime_override: str = params.get("source.regime_override")
        # Declared scene type ('auto' = no declaration). Published so OpticsStage
        # can run the declared-vs-derived regime cross-check (ADR-0008 T2) without
        # reaching back into a source param (which minimal stage tests may omit).
        scene_type_declared: str = params.get("source.scene_type")

        # Pixel pitch and focal length for IFOV.
        pixel_pitch_m: float = params.get("detector.pixel_pitch_x_um")
        pixel_pitch_y_m: float = params.get("detector.pixel_pitch_y_um")
        focal_length_m: float = params.get("optics.focal_length_m")
        # Gap 97: did the user set fill_fraction explicitly, or is it the schema
        # default? When it is the default AND a projected area is given, the fill
        # fraction is *derived* from geometry so the area actually drives the
        # sub-pixel signal (see below); an explicit fill_fraction is honored
        # (Path 3 — the analyst owns the fraction, geometry is skipped).
        fill_fraction_is_default: bool = (
            params.get_resolved("source.target.fill_fraction").provenance is Provenance.DEFAULT
        )

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
        # Declared scene type for the OpticsStage declared-vs-derived cross-check (T2).
        state = state.with_stage_output(
            "source",
            "scene_type_declared",
            scene_type_declared,
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
            # ADR-0006: adopt the scene LOS GeometryStage resolved (covers
            # the off-nadir / ground-range / elevation / site+time input
            # modes); None for legacy source-only fixtures, which fall back
            # to the param-built LOS inside the inferrer.
            scene_los=state.stage_outputs.get("geometry", {}).get("los_geometry"),
        )

        # Target Definition Matrix Q3: the descriptor's ``A_t`` is the
        # AUTHORITATIVE projected area — the inferrer already applied the
        # shape-wins-over-projected_area_m2 precedence when building it. Adopt
        # it unconditionally so the published area (→ regime classification and
        # the SpectralIntegrationStage solid angle) is the SAME area the
        # descriptor and the shape-wins warning report (CU-148). Previously this
        # only fired when the ``projected_area_m2`` param was unset, so a config
        # that set BOTH a shape and the param published the *param* area to the
        # regime/solid-angle path while the descriptor + warning used the *shape*
        # area — an inconsistency. For a shape-only or T7 config the value is
        # unchanged; only the both-set case now correctly resolves to shape.
        descriptor_area = getattr(target_desc, "A_t", None)
        # T7IntensityAtSource: point-source intensity carries no user A_t,
        # but SpectralIntegrationStage still needs a non-None projected
        # area to compute scene solid angle.  Publish the T7 reference
        # area (A_fict) — it cancels algebraically through the single
        # at-pixel camera equation to recover I · A_collect / R².  See
        # ADR-0004 §Assembly contract.
        if descriptor_area is None and isinstance(target_desc, T7IntensityAtSource):
            descriptor_area = T7IntensityAtSource.REFERENCE_AREA_M2
        if descriptor_area is not None:
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

        # --- Gap 97: derive the sub-pixel fill fraction from the projected area ---
        # The sub-pixel signal (SpectralIntegrationStage) mixes by
        # ``fill_fraction``. When the target is specified by radiance + projected
        # area and the analyst did NOT set an explicit fill_fraction, derive it
        # from the geometry — ff = A_proj / (R² · Ω_pixel) — so the area drives
        # the signal instead of silently falling back to the 1.0 default (which
        # yields an extended-scene signal regardless of area). An explicit
        # fill_fraction is left untouched (Path 3: geometry is skipped, the
        # analyst owns the fraction). Republishes the ``fill_fraction`` output
        # SpectralIntegrationStage reads.
        if fill_fraction_is_default and projected_area_m2 is not None and range_m is not None:
            derived_ff = fill_fraction_from_area(
                projected_area_m2,
                range_m,
                pixel_pitch_m,
                pixel_pitch_y_m,
                focal_length_m,
            )
            if derived_ff is not None:
                fill_fraction = derived_ff
                state = state.with_stage_output("source", "fill_fraction", fill_fraction)

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

        # Resolved target reflectance ρ(λ) on the chain grid (owner walkthrough
        # item 6).  The GUI's reflective view plots the *surface property* the
        # analyst typed, not the at-aperture radiance it eventually produces —
        # so it must be published, and published from the ONE resolver the
        # radiance path also uses (Rule 19).  ``None`` for every descriptor with
        # no reflectance (T1 pure-thermal, T5/T6/T7 user-supplied radiance /
        # intensity): the output is then simply absent, and the accessor that
        # reads it says so actionably rather than plotting a fabricated zero.
        rho_grid = target_reflectance_on_grid(
            target_desc,
            state.wavelength_um,
            los_geometry,
        )
        if rho_grid is not None:
            state = state.with_stage_output(
                "source",
                "reflectance",
                SpectralData(
                    name="target_reflectance",
                    wavelength_um=state.wavelength_um,
                    values=rho_grid,
                    unit="dimensionless",
                    source=f"resolved from {type(target_desc).__name__}",
                ),
            )

        return state.with_stage_output("source", "los_geometry", los_geometry)
