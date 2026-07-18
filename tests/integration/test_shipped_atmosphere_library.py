"""Integration: the shipped atmosphere library under ``data/atmospheres/``.

The library is committed data generated from the real 2026-07-17
MODTRAN 6 run set by ``scripts/build_atmosphere_library.py`` (see
``data/atmospheres/MANIFEST.md``). These tests are the Rule-26
justification for committing it: golden assertions that the shipped
files load through their intended runtime paths and carry the physics
the manifest claims.

Pinned reference values are band means of the slit-degraded (5 cm⁻¹
FWHM) library content, extracted at generation time — they differ from
the full-resolution tape7 goldens elsewhere by ≲0.003 in band-mean τ.
"""

from __future__ import annotations

import warnings
from pathlib import Path

import numpy as np
import pytest

from radiant.api.session import RadiantSession
from radiant.atmosphere.interpolated import GeometryPoint, InterpolatedAtmosphere
from radiant.atmosphere.protocol import AtmosphericGeometry
from radiant.atmosphere.tabulated import TabulatedAtmosphere

_LIB = Path(__file__).resolve().parents[2] / "data" / "atmospheres"

_PROFILES = (
    "us_standard",
    "tropical",
    "midlat_summer",
    "midlat_winter",
    "subarctic_summer",
    "subarctic_winter",
)


def _band_mean(wl: np.ndarray, values: np.ndarray, lo: float, hi: float) -> float:
    band = (wl >= lo) & (wl <= hi)
    return float(values[band].mean())


def _load_interpolated(subdir: str, axes: list[str]) -> InterpolatedAtmosphere:
    """Load a library family the way ``loaders._build_interpolated`` does."""
    points = []
    for npz_file in sorted((_LIB / subdir).glob("*.npz")):
        data = np.load(npz_file, allow_pickle=True)
        coords = data["geometry"].item()
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")  # zero-downwelling default notice
            tab = TabulatedAtmosphere.from_npz(npz_file)
        points.append(
            GeometryPoint(
                coordinates=coords,
                transmittance=tab.transmittance_data,
                path_radiance=tab.path_radiance_data,
                atm_emission_down=tab.atm_emission_down_data,
            )
        )
    return InterpolatedAtmosphere(points, axes=axes)


@pytest.mark.level2
class TestShippedProfiles:
    """profiles/ — six tabulated nadir full columns."""

    @pytest.mark.parametrize("profile", _PROFILES)
    def test_loads_and_is_physical(self, profile: str) -> None:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            tab = TabulatedAtmosphere.from_npz(_LIB / "profiles" / f"{profile}.npz")
        wl = tab.transmittance_data.wavelength_um
        tau = tab.transmittance_data.values
        assert np.all(np.diff(wl) > 0.0)
        assert wl[0] == pytest.approx(0.375, abs=2e-3)
        assert wl[-1] == pytest.approx(14.28, abs=2e-2)
        assert np.all((tau >= 0.0) & (tau <= 1.0))
        assert np.all(tab.path_radiance_data.values >= 0.0)

    def test_us_standard_band_goldens(self) -> None:
        """Slit-degraded A1 content: LWIR-window band-mean τ and the real
        H2 downwelling attached as atm_emission_down."""
        tab = TabulatedAtmosphere.from_npz(_LIB / "profiles" / "us_standard.npz")
        wl = tab.transmittance_data.wavelength_um
        # Full-resolution A1 golden is 0.8461 (test_modtran_real_runs);
        # the 5 cm⁻¹ slit shifts the band mean by < 0.003.
        assert _band_mean(wl, tab.transmittance_data.values, 10.0, 12.0) == pytest.approx(
            0.846, abs=5e-3
        )
        # π × band-integrated downwelling ≈ the H2 E_sky_thermal golden.
        ld = tab.atm_emission_down_data.values
        band = (wl >= 8.0) & (wl <= 12.0)
        e_sky = float(np.trapezoid(np.pi * ld[band], wl[band]))
        assert e_sky == pytest.approx(20.87, rel=0.02)

    def test_profiles_without_h_run_have_zero_downwelling(self) -> None:
        """Only us_standard/tropical have real H-run downwelling; the
        other four omit the key and load as zeros (manifest-documented)."""
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            tab = TabulatedAtmosphere.from_npz(_LIB / "profiles" / "midlat_summer.npz")
        assert np.all(tab.atm_emission_down_data.values == 0.0)


@pytest.mark.level2
class TestShippedZenithFan:
    """us_standard_zenith_fan/ — 1-D interpolation over path zenith."""

    def test_regular_grid_and_bracketing(self) -> None:
        fan = _load_interpolated("us_standard_zenith_fan", ["path_zenith_rad"])
        assert fan.grid_type == "regular"
        assert fan.n_points == 4

        geom = AtmosphericGeometry(
            sensor_altitude_m=100_000.0,
            target_altitude_m=0.0,
            path_zenith_rad=np.radians(37.0),
            solar_zenith_rad=0.5,
            solar_azimuth_rad=0.0,
        )
        state = fan.build_state(fan.wavelength_um, geom)
        wl = fan.wavelength_um
        tau_37 = _band_mean(wl, state.transmittance.values, 10.0, 12.0)
        # Between the 30° (0.8257) and 45° (0.7925) node values.
        assert 0.7925 < tau_37 < 0.8257

    def test_airmass_interpolation_holdout_45deg(self) -> None:
        """CU-160 acceptance on committed data: build the fan from ONLY the
        30° and 60° nodes, query 45°, and compare against the real 45° node
        (zen45.npz) held out as truth. Airmass-space interpolation lands
        within 0.5% band-mean τ (measured −0.1%); the pre-CU-160
        linear-in-angle axis was −4%."""
        points = []
        for name in ("zen30", "zen60"):
            npz_file = _LIB / "us_standard_zenith_fan" / f"{name}.npz"
            data = np.load(npz_file, allow_pickle=True)
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                tab = TabulatedAtmosphere.from_npz(npz_file)
            points.append(
                GeometryPoint(
                    coordinates=data["geometry"].item(),
                    transmittance=tab.transmittance_data,
                    path_radiance=tab.path_radiance_data,
                    atm_emission_down=tab.atm_emission_down_data,
                )
            )
        fan_2node = InterpolatedAtmosphere(points, axes=["path_zenith_rad"])

        geom = AtmosphericGeometry(
            sensor_altitude_m=100_000.0,
            target_altitude_m=0.0,
            path_zenith_rad=np.radians(45.0),
            solar_zenith_rad=0.5,
            solar_azimuth_rad=0.0,
        )
        predicted = fan_2node.build_state(fan_2node.wavelength_um, geom)
        wl = fan_2node.wavelength_um
        tau_pred = _band_mean(wl, predicted.transmittance.values, 3.5, 5.0)

        truth = TabulatedAtmosphere.from_npz(_LIB / "us_standard_zenith_fan" / "zen45.npz")
        tau_true = _band_mean(
            truth.transmittance_data.wavelength_um, truth.transmittance_data.values, 3.5, 5.0
        )
        assert tau_pred == pytest.approx(tau_true, rel=5e-3), (
            f"45° holdout: predicted {tau_pred:.4f} vs real node {tau_true:.4f} — "
            "airmass-space interpolation (CU-160) should land within 0.5%"
        )

    def test_refuses_extrapolation_beyond_60deg(self) -> None:
        from radiant.atmosphere.errors import AtmosphereValidationError

        fan = _load_interpolated("us_standard_zenith_fan", ["path_zenith_rad"])
        geom = AtmosphericGeometry(
            sensor_altitude_m=100_000.0,
            target_altitude_m=0.0,
            path_zenith_rad=np.radians(75.0),
            solar_zenith_rad=0.5,
            solar_azimuth_rad=0.0,
        )
        with pytest.raises(AtmosphereValidationError, match="outside the available range"):
            fan.build_state(fan.wavelength_um, geom)


@pytest.mark.level2
class TestShippedLadders:
    """midlat_summer_ladders/ — 2-D grid over sensor × target altitude,
    with the 100 km states duplicated at 40,000 km (orbital hull)."""

    def test_grid_covers_orbital_altitudes(self) -> None:
        ladders = _load_interpolated(
            "midlat_summer_ladders", ["sensor_altitude_m", "target_altitude_m"]
        )
        assert ladders.grid_type == "regular"
        assert ladders.n_points == 18  # 3 sensor nodes × 6 target altitudes
        bounds = ladders.coordinate_bounds()
        assert bounds["sensor_altitude_m"] == (35_000.0, 40_000_000.0)
        assert bounds["target_altitude_m"] == (0.0, 29_000.0)

    def test_leo_query_matches_toa_column(self) -> None:
        """A 500 km sensor interpolates between the duplicated 100 km and
        40,000 km nodes — identical states, so the result equals the TOA
        column exactly (the added path is vacuum). Golden: G3 (h_tgt
        10 km) band mean 0.9253 full-res, ~0.923 slit-degraded."""
        ladders = _load_interpolated(
            "midlat_summer_ladders", ["sensor_altitude_m", "target_altitude_m"]
        )
        geom = AtmosphericGeometry(
            sensor_altitude_m=500_000.0,
            target_altitude_m=10_000.0,
            path_zenith_rad=0.0,
            solar_zenith_rad=0.5,
            solar_azimuth_rad=0.0,
        )
        state = ladders.build_state(ladders.wavelength_um, geom)
        tau = _band_mean(ladders.wavelength_um, state.transmittance.values, 8.0, 13.0)
        assert tau == pytest.approx(0.9253, abs=5e-3)

    def test_target_altitude_monotonicity(self) -> None:
        """τ rises with target altitude at fixed sensor (same physics the
        C-ladder goldens pin at full resolution)."""
        ladders = _load_interpolated(
            "midlat_summer_ladders", ["sensor_altitude_m", "target_altitude_m"]
        )
        taus = []
        for h_tgt in (1_000.0, 5_000.0, 10_000.0, 20_000.0, 29_000.0):
            geom = AtmosphericGeometry(
                sensor_altitude_m=35_000.0,
                target_altitude_m=h_tgt,
                path_zenith_rad=0.0,
                solar_zenith_rad=0.5,
                solar_azimuth_rad=0.0,
            )
            state = ladders.build_state(ladders.wavelength_um, geom)
            taus.append(_band_mean(ladders.wavelength_um, state.transmittance.values, 8.0, 13.0))
        assert taus == sorted(taus)


@pytest.mark.level2
def test_chain_end_to_end_on_shipped_profile() -> None:
    """Category D: a full chain run on the shipped us_standard profile via
    atmosphere.model='tabulated' produces finite metrics."""
    wl = np.linspace(8.0, 13.0, 251)
    session = RadiantSession(wavelength_um=wl)
    params = session.default_params()
    params.set("source.target.temperature", 300.0)
    params.set("source.target.emissivity", 0.95)
    params.set("atmosphere.model", "tabulated")
    npz = str(_LIB / "profiles" / "us_standard.npz")
    params.set("atmosphere.tabulated_transmittance_file", npz)
    params.set("atmosphere.tabulated_path_radiance_file", npz)
    params.set("geometry.sensor_altitude_m", 500_000.0)
    params.set("optics.aperture_diameter_m", 0.10)
    params.set("optics.focal_length_m", 0.25)
    params.set("optics.transmission_scalar", 0.60)
    params.set("detector.pixel_pitch_x_um", 17.0)
    params.set("detector.pixel_pitch_y_um", 17.0)
    params.set("detector.qe_value", 0.55)
    params.set("detector.dark_rate_e_per_s", 1000.0)
    params.set("spectral_integration.filter_min_um", 8.0)
    params.set("spectral_integration.filter_max_um", 13.0)
    params.set("spectral_integration.integration_time_s", 0.015)
    params.set("readout.read_noise_e_rms", 20.0)
    params.set("readout.gain_e_per_dn", 2.0)
    params.set("readout.adc_bits", 14)
    params.resolve()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        result = session.run(params)
    assert result is not None
    assert np.isfinite(float(result.metrics["snr"]))
    assert float(result.metrics["snr"]) > 0.0
