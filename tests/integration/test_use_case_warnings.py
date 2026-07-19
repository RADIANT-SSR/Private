"""Integration coverage for matrix §7 warning-level validators.

This file is the warning-coverage companion to
``tests/integration/test_use_case_matrix.py``.  Gap #3 in
``docs/archive/Use_Case_gaps.md``: the 90-cell pass/raise sweep does not assert
that the matrix §7 *warnings* fire — it only suppresses them so the
chain-run assertion dominates.  That leaves silent-drift risk if a
future refactor removes a ``warnings.warn`` call; the unit tests in
``src/radiant/core/tests/test_descriptors.py`` and
``src/radiant/optics/tests/test_psf_regime_validation.py`` would still
pass on their own synthetic inputs while the cells that depend on the
warning at the matrix level stop emitting it.

This file parametrizes over the matrix cells that straddle each
warning boundary and asserts the warning fires at the point the user's
configuration would trigger it.  It does **not** re-run the 90-cell
sweep — cell numbering here refers back to ``RADIANT_Use_Case_Matrix.md``
§3.2 / §3.3 for traceability only.

Four warning boundaries are covered:

1. SWIR hot-target (T_t > 700 K with T1Thermal) — matrix §3.2 line 318.
2. T2Reflective + sun below horizon (θ_s > π/2) — matrix §7.
3. Sub-pixel descriptor that has collapsed to a point source
   (√A_t/d < 0.01·PSF_FWHM) — matrix §1.1.
4. Point-source descriptor with resolved angular size
   (√A_t/d > 0.1·PSF_FWHM) — matrix §7 (raises, not warns).

Reference: ``docs/Option_C_Implementation_Plan.md`` Stage 8;
``docs/archive/Use_Case_gaps.md`` Gap #3.
"""

from __future__ import annotations

import math
import warnings

import numpy as np
import pytest

from radiant.api.session import RadiantSession
from radiant.core.descriptors import (
    T1Thermal,
    T2Reflective,
    warn_if_reflective_and_sun_below_horizon,
)
from radiant.core.los_geometry import LineOfSightGeometry
from radiant.core.parameters import ParameterBoundsError
from radiant.core.reflectance import ScalarLambertianReflectance
from radiant.core.spectral import SpectralData

# ---------------------------------------------------------------------------
# Regime grids — mirror test_use_case_matrix.py so cell numbering lines up.
# ---------------------------------------------------------------------------


_REGIME_GRIDS: dict[str, np.ndarray] = {
    "VIS": np.linspace(0.4, 0.7, 31),
    "NIR": np.linspace(0.7, 1.0, 31),
    "SWIR": np.linspace(1.0, 2.5, 61),
    "MWIR": np.linspace(3.0, 5.0, 41),
    "LWIR": np.linspace(8.0, 13.0, 51),
}


def _grey_sd(wl: np.ndarray, value: float, name: str = "eps") -> SpectralData:
    return SpectralData(
        name=name,
        wavelength_um=np.asarray(wl, dtype=np.float64),
        values=np.full_like(wl, value, dtype=np.float64),
        unit="",
        source="test_use_case_warnings",
    )


def _seed_optics_detector_readout(params, regime: str) -> None:
    """Seed a minimal imaging system appropriate for the given regime.

    Mirrors the fixture layout in ``test_use_case_matrix.py`` so cells
    configured here run through the same optical/detector defaults.
    """
    if regime in ("VIS", "NIR"):
        pixel_pitch_um, read_noise_e, qe, dark_rate, t_int = 5.0, 5.0, 0.85, 50.0, 0.002
    elif regime == "SWIR":
        pixel_pitch_um, read_noise_e, qe, dark_rate, t_int = 15.0, 20.0, 0.70, 500.0, 0.005
    elif regime == "MWIR":
        pixel_pitch_um, read_noise_e, qe, dark_rate, t_int = 18.0, 20.0, 0.60, 800.0, 0.008
    else:
        pixel_pitch_um, read_noise_e, qe, dark_rate, t_int = 20.0, 12.0, 0.55, 800.0, 0.010

    wl = _REGIME_GRIDS[regime]
    params.set("optics.aperture_diameter_m", 0.15)
    params.set("optics.focal_length_m", 0.45)
    params.set("optics.transmission_scalar", 0.62)
    params.set("detector.pixel_pitch_x_um", pixel_pitch_um)
    params.set("detector.pixel_pitch_y_um", pixel_pitch_um)
    params.set("detector.qe_value", qe)
    params.set("detector.dark_rate_e_per_s", dark_rate)
    params.set("spectral_integration.filter_min_um", float(wl[0]))
    params.set("spectral_integration.filter_max_um", float(wl[-1]))
    params.set("spectral_integration.integration_time_s", t_int)
    params.set("readout.read_noise_e_rms", read_noise_e)
    params.set("readout.gain_e_per_dn", 2.0)
    params.set("readout.adc_bits", 14)


# ---------------------------------------------------------------------------
# 1. SWIR hot-target warning — T1Thermal with T_t > 700 K in the SWIR band.
# ---------------------------------------------------------------------------


# Cells in each table where the regime is SWIR: (cell_id, target_location).
# Cell numbering from RADIANT_Use_Case_Matrix.md §3.2 (primary cells)
# and §3.3 (sub-case cells).  Only scene_type='extended' is listed; the
# warning is about T_t crossing 700 K and fires identically for sub_pixel
# / point_source in the same regime — the extended cell is the canonical
# representative per table to keep the parametrization readable.
_SWIR_EXTENDED_CELLS: tuple[tuple[str, str], ...] = (
    ("7", "at_aperture"),   # not used — at_aperture uses T5AtAperture (no T_t).
    ("22", "terrestrial"),
    ("37", "airborne"),
    ("52", "no_atm_space"),
    ("G7", "ground_test"),
    ("L7", "lab_test"),
)


# Cells at_aperture use T5AtAperture which has no T_t field — the
# SWIR-hot warning is inapplicable there.  Skip cell 7 in parametrization.
_SWIR_T1_CELLS = tuple((c, loc) for c, loc in _SWIR_EXTENDED_CELLS if loc != "at_aperture")


@pytest.mark.level2
class TestSwirHotTargetWarning:
    """Matrix §3.2 line 318 — T1Thermal in SWIR with T_t > 700 K warns."""

    @pytest.mark.parametrize("cell_id,target_location", _SWIR_T1_CELLS)
    def test_hot_swir_t1_warns(self, cell_id: str, target_location: str) -> None:
        """Constructing T1Thermal with a SWIR ε grid and T_t = 750 K warns."""
        wl = _REGIME_GRIDS["SWIR"]
        epsilon = _grey_sd(wl, 0.95)
        subcase = None
        h_tgt: float | None = 0.0
        if target_location == "no_atmosphere":
            subcase = "space"
            h_tgt = 0.0
        if target_location in ("no_atm_space",):
            target_location_str = "no_atmosphere"
            subcase = "space"
        elif target_location in ("ground_test", "lab_test"):
            target_location_str = "no_atmosphere"
            subcase = target_location
        else:
            target_location_str = target_location

        with pytest.warns(UserWarning, match=r"SWIR.*700"):
            T1Thermal(
                scene_type="extended",
                target_location=target_location_str,  # type: ignore[arg-type]
                no_atmosphere_subcase=subcase,  # type: ignore[arg-type]
                h_tgt=h_tgt,
                epsilon=epsilon,
                T_t=750.0,
            )

    def test_warm_swir_t1_does_not_warn(self) -> None:
        """T_t = 400 K (matrix harness default) does not trigger the warning."""
        wl = _REGIME_GRIDS["SWIR"]
        with warnings.catch_warnings():
            warnings.simplefilter("error", UserWarning)
            T1Thermal(
                scene_type="extended",
                target_location="terrestrial",
                h_tgt=0.0,
                epsilon=_grey_sd(wl, 0.95),
                T_t=400.0,
            )

    def test_hot_non_swir_t1_does_not_warn(self) -> None:
        """T_t = 750 K in LWIR does NOT trigger the SWIR-specific warning.

        The SWIR-hot warning is gated on the spectral grid overlapping
        1–3 µm; an LWIR grid with a hot target is a different scenario
        (and a perfectly valid one — think rocket plume imaged in LWIR).
        """
        wl = _REGIME_GRIDS["LWIR"]
        with warnings.catch_warnings():
            warnings.simplefilter("error", UserWarning)
            T1Thermal(
                scene_type="extended",
                target_location="terrestrial",
                h_tgt=0.0,
                epsilon=_grey_sd(wl, 0.95),
                T_t=750.0,
            )


# ---------------------------------------------------------------------------
# 2. T2Reflective + sun below horizon warning (θ_s > π/2).
# ---------------------------------------------------------------------------


# T2 is a reflective-only descriptor, so this warning is only meaningful
# for reflective-dominated regimes (VIS / NIR / SWIR).  MWIR and LWIR use
# T3Mixed or T1Thermal — T2 would itself be flagged by the MWIR-non-mixed
# warning before we even reach θ_s.  We parametrize over the three
# reflective regimes.
_REFLECTIVE_REGIMES = ("VIS", "NIR", "SWIR")


@pytest.mark.level2
class TestT2BelowHorizonWarning:
    """Matrix §7 — T2Reflective with θ_s > π/2 warns at SourceStage."""

    @pytest.mark.parametrize("regime", _REFLECTIVE_REGIMES)
    def test_sun_below_horizon_warns(self, regime: str) -> None:
        """θ_s = π/2 + 0.2 rad with T2Reflective warns per matrix §7."""
        wl = _REGIME_GRIDS[regime]
        target = T2Reflective(
            scene_type="extended",
            target_location="terrestrial",
            h_tgt=0.0,
            rho=ScalarLambertianReflectance(
                reflectance=_grey_sd(wl, 0.3, name="rho"),
            ),
        )
        los = LineOfSightGeometry(
            h_tgt=0.0,
            theta_o=0.0,
            theta_s=math.pi / 2.0 + 0.2,
        )
        with pytest.warns(UserWarning, match=r"below the horizon"):
            warn_if_reflective_and_sun_below_horizon(target, los.theta_s)

    @pytest.mark.parametrize("regime", _REFLECTIVE_REGIMES)
    def test_sun_above_horizon_does_not_warn(self, regime: str) -> None:
        """θ_s = π/4 (sun well above horizon) does not warn."""
        wl = _REGIME_GRIDS[regime]
        target = T2Reflective(
            scene_type="extended",
            target_location="terrestrial",
            h_tgt=0.0,
            rho=ScalarLambertianReflectance(
                reflectance=_grey_sd(wl, 0.3, name="rho"),
            ),
        )
        with warnings.catch_warnings():
            warnings.simplefilter("error", UserWarning)
            warn_if_reflective_and_sun_below_horizon(target, math.pi / 4.0)


# ---------------------------------------------------------------------------
# 3. Sub-pixel descriptor that has collapsed to a point source.
# ---------------------------------------------------------------------------


# Sub-pixel cells in Tables B / C / D-space: (cell_id, target_location).
# The warning fires when √A_t/d < 0.01·PSF_FWHM after OpticsStage
# finalizes the regime.  At the matrix-harness defaults
# (projected_area_m2=100, range_m=1e6, aperture=0.15, focal=0.45) the
# ratio is well above 0.01; to trigger the warning we shrink the target
# by 6 orders of magnitude so √A_t/d ≈ 10⁻⁷ rad, which is ≪ 0.01·PSF_FWHM
# for any of the matrix regimes.
_SUBPIXEL_CELLS: tuple[tuple[str, str, str], ...] = (
    # Table B terrestrial sub-pixel: cells 17 (VIS), 20 (NIR), 23 (SWIR),
    # 26 (MWIR), 29 (LWIR).  Pick one per regime in LWIR-dominated bands
    # where the thermal signal is non-zero.
    ("29", "terrestrial", "LWIR"),
    # Table C airborne sub-pixel LWIR (cell 44).
    ("44", "airborne", "LWIR"),
    # Table D space sub-pixel LWIR (cell 59).
    ("59", "no_atm_space", "LWIR"),
)


@pytest.mark.level2
class TestSubPixelCollapsesToPointSource:
    """Matrix §1.1 — sub-pixel with √A_t/d ≪ 0.01·PSF_FWHM warns.

    The warning is emitted from ``OpticsStage._validate_psf_regime_consistency``
    (optics/stage.py) after the regime is finalized.  This test runs the
    full chain with an extreme small-target/large-range geometry so the
    ratio clears the 0.01 threshold from below.
    """

    @pytest.mark.parametrize("cell_id,target_location,regime", _SUBPIXEL_CELLS)
    def test_tiny_subpixel_warns_collapse(
        self, cell_id: str, target_location: str, regime: str
    ) -> None:
        wl = _REGIME_GRIDS[regime]
        session = RadiantSession(wavelength_um=wl)
        params = session.default_params()

        params.set("source.target.temperature", 300.0)
        params.set("source.target.emissivity", 0.95)
        params.set("source.target_location", "auto")
        params.set("source.scene_type", "sub_pixel")
        params.set("source.target.fill_fraction", 0.001)

        # Tiny target (1 µm² cross-section), very long range → √A_t/d ≈ 1e-9
        # rad, which is ≪ 0.01·PSF_FWHM for a 0.15 m aperture at 10 µm.
        params.set("source.target.projected_area_m2", 1.0e-12)
        params.set("geometry.target_range_m", 1.0e8)

        if target_location == "airborne":
            params.set("geometry.target_altitude_m", 10_000.0)
            params.set("atmosphere.model", "simple")
            params.set("atmosphere.standard_atmosphere", "midlat_summer")
            params.set("geometry.sensor_altitude_m", 800_000.0)
        elif target_location == "no_atm_space":
            params.set("atmosphere.model", "exo")
            params.set("geometry.sensor_altitude_m", 800_000.0)
        else:
            params.set("geometry.target_altitude_m", 0.0)
            params.set("atmosphere.model", "simple")
            params.set("atmosphere.standard_atmosphere", "midlat_summer")
            params.set("geometry.sensor_altitude_m", 800_000.0)

        _seed_optics_detector_readout(params, regime)
        params.resolve()

        with pytest.warns(UserWarning, match=r"effectively a point source"):
            session.run(params)


# ---------------------------------------------------------------------------
# 4. Point-source descriptor with resolved angular size — raises.
# ---------------------------------------------------------------------------


# Point-source cells in Tables B / C / D-space: (cell_id, target_location).
# OpticsStage raises when √A_t/d > 0.1·PSF_FWHM.  To trigger it we
# oversize the projected area (10⁴ m²) at a modest range (10 km) so
# √A_t/d ≈ 0.01 rad — orders of magnitude above 0.1·PSF_FWHM ≈ 1e-5 rad.
_POINT_SOURCE_CELLS: tuple[tuple[str, str, str], ...] = (
    ("30", "terrestrial", "LWIR"),
    ("45", "airborne", "LWIR"),
    ("60", "no_atm_space", "LWIR"),
)


@pytest.mark.level2
class TestPointSourceAngularSizeRaise:
    """Matrix §7 — point_source with √A_t/d > 0.1·PSF_FWHM raises.

    This is a raise, not a warn, because the point-source approximation
    has become non-physical (the target is resolved).  The matrix-level
    sweep in ``test_use_case_matrix.py`` configures point-source cells
    inside the guard, so the raise never fires there; this test
    deliberately oversizes the target so the guard trips.
    """

    @pytest.mark.parametrize("cell_id,target_location,regime", _POINT_SOURCE_CELLS)
    def test_oversized_point_source_raises(
        self, cell_id: str, target_location: str, regime: str
    ) -> None:
        wl = _REGIME_GRIDS[regime]
        session = RadiantSession(wavelength_um=wl)
        params = session.default_params()

        params.set("source.target.temperature", 300.0)
        params.set("source.target.emissivity", 0.95)
        params.set("source.target_location", "auto")
        params.set("source.scene_type", "point_source")
        params.set("source.target.fill_fraction", 1.0)

        # Oversized target: 10 km × 10 km at 10 km range → √A_t/d ≈ 1 rad,
        # which is ≫ 0.1·PSF_FWHM for any matrix regime.
        params.set("source.target.projected_area_m2", 1.0e8)
        params.set("geometry.target_range_m", 1.0e4)

        if target_location == "airborne":
            params.set("geometry.target_altitude_m", 10_000.0)
            params.set("atmosphere.model", "simple")
            params.set("atmosphere.standard_atmosphere", "midlat_summer")
            params.set("geometry.sensor_altitude_m", 800_000.0)
        elif target_location == "no_atm_space":
            params.set("atmosphere.model", "exo")
            params.set("geometry.sensor_altitude_m", 800_000.0)
        else:
            params.set("geometry.target_altitude_m", 0.0)
            params.set("atmosphere.model", "simple")
            params.set("atmosphere.standard_atmosphere", "midlat_summer")
            params.set("geometry.sensor_altitude_m", 800_000.0)

        _seed_optics_detector_readout(params, regime)
        params.resolve()

        with (
            pytest.raises(ParameterBoundsError, match=r"point.source"),
            warnings.catch_warnings(),
        ):
            warnings.simplefilter("ignore", UserWarning)
            session.run(params)
