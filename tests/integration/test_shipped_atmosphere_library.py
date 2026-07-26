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

_LIB = Path(__file__).resolve().parents[2] / "src" / "radiant" / "data" / "tables" / "atmospheres"

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

    def test_midlat_summer_carries_h5_downwelling(self) -> None:
        """midlat_summer gained real downwelling with the boost expansion
        (H5, plan §4.4): non-zero atm_emission_down, and π·band-integral is
        the warmer/wetter mid-latitude sky (~47 W/m² vs us_standard ~21)."""
        tab = TabulatedAtmosphere.from_npz(_LIB / "profiles" / "midlat_summer.npz")
        wl = tab.transmittance_data.wavelength_um
        ld = tab.atm_emission_down_data.values
        assert np.any(ld > 0.0)
        band = (wl >= 8.0) & (wl <= 12.0)
        e_sky = float(np.trapezoid(np.pi * ld[band], wl[band]))
        assert e_sky == pytest.approx(46.8, rel=0.03)

    def test_profiles_without_h_run_have_zero_downwelling(self) -> None:
        """The three profiles with no H-run (midlat_winter, subarctic
        summer/winter) omit the key and load as zeros (manifest-documented);
        us_standard/tropical/midlat_summer carry real H2/H4/H5 downwelling."""
        for profile in ("midlat_winter", "subarctic_summer", "subarctic_winter"):
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                tab = TabulatedAtmosphere.from_npz(_LIB / "profiles" / f"{profile}.npz")
            assert np.all(tab.atm_emission_down_data.values == 0.0), profile


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
            solar_zenith_rad=np.radians(30.0),
            solar_azimuth_rad=0.0,
        )
        state = fan.build_state(fan.wavelength_um, geom)
        wl = fan.wavelength_um
        tau_37 = _band_mean(wl, state.transmittance.values, 10.0, 12.0)
        # Between the 30° (0.8257) and 45° (0.7925) node values.
        assert 0.7925 < tau_37 < 0.8257

    def test_airborne_sensor_query_warns(self) -> None:
        """Boost plan §4.6 (2026-07-19 audit): the fan NPZs record their
        100 km run sensor, so an airborne-sensor query is now a LOUD
        substitution instead of silently receiving the space column."""
        fan = _load_interpolated("us_standard_zenith_fan", ["path_zenith_rad"])
        geom = AtmosphericGeometry(
            sensor_altitude_m=10_000.0,  # aircraft vs the recorded 100 km
            target_altitude_m=0.0,
            path_zenith_rad=np.radians(30.0),
            solar_zenith_rad=np.radians(30.0),
            solar_azimuth_rad=0.0,
        )
        with pytest.warns(UserWarning, match="sensor_altitude_m.*IGNORED"):
            fan.build_state(fan.wavelength_um, geom)

    def test_orbital_sensor_query_does_not_warn(self) -> None:
        """A LEO sensor above the recorded 100 km (TOA) run sees the
        identical column (vacuum above TOA) — exact, no warning."""
        fan = _load_interpolated("us_standard_zenith_fan", ["path_zenith_rad"])
        geom = AtmosphericGeometry(
            sensor_altitude_m=500_000.0,
            target_altitude_m=0.0,
            path_zenith_rad=np.radians(30.0),
            solar_zenith_rad=np.radians(30.0),
            solar_azimuth_rad=0.0,
        )
        with warnings.catch_warnings():
            warnings.simplefilter("error", UserWarning)
            fan.build_state(fan.wavelength_um, geom)  # must not warn

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
            solar_zenith_rad=np.radians(30.0),
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
            solar_zenith_rad=np.radians(30.0),
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
            solar_zenith_rad=np.radians(30.0),
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
                solar_zenith_rad=np.radians(30.0),
                solar_azimuth_rad=0.0,
            )
            state = ladders.build_state(ladders.wavelength_um, geom)
            taus.append(_band_mean(ladders.wavelength_um, state.transmittance.values, 8.0, 13.0))
        assert taus == sorted(taus)

    def test_evaluate_two_leg_airborne_target(self) -> None:
        """Gap 94: ``evaluate()`` serves h_tgt > 0 from the ladder grid.

        Consistency (not a new golden): the adapter's τ_up must equal the
        underlying interpolator queried at (sensor, h_tgt) and its
        τ_full_up the query at (sensor, 0) — two queries, one grid.
        """
        from radiant.core.los_geometry import LineOfSightGeometry

        ladders = _load_interpolated(
            "midlat_summer_ladders", ["sensor_altitude_m", "target_altitude_m"]
        )
        wl = ladders.wavelength_um
        session = RadiantSession(wavelength_um=wl)
        params = session.default_params()
        params.set("source.target.temperature", 300.0)
        params.set("source.target.emissivity", 0.95)
        params.set("atmosphere.model", "interpolated")
        params.set("atmosphere.interpolated_data_dir", str(_LIB / "midlat_summer_ladders"))
        params.set("atmosphere.interpolation_axes", "sensor_altitude_m,target_altitude_m")
        params.set("geometry.sensor_altitude_m", 100_000.0)
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

        los = LineOfSightGeometry(
            h_tgt=10_000.0, h_sensor=100_000.0, theta_o=0.0, h_atm_top=1.0e5
        )
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            q = ladders.evaluate(wl, los, params)

        up_ref = ladders.build_state(
            wl,
            AtmosphericGeometry(
                sensor_altitude_m=100_000.0,
                target_altitude_m=10_000.0,
                path_zenith_rad=0.0,
                solar_zenith_rad=np.radians(30.0),
                solar_azimuth_rad=0.0,
            ),
        )
        full_ref = ladders.build_state(
            wl,
            AtmosphericGeometry(
                sensor_altitude_m=100_000.0,
                target_altitude_m=0.0,
                path_zenith_rad=0.0,
                solar_zenith_rad=np.radians(30.0),
                solar_azimuth_rad=0.0,
            ),
        )
        np.testing.assert_array_equal(q.tau_up, up_ref.transmittance.values)
        np.testing.assert_array_equal(q.tau_full_up, full_ref.transmittance.values)
        np.testing.assert_array_equal(q.L_path_up, up_ref.path_radiance.values)
        np.testing.assert_array_equal(q.L_path_full, full_ref.path_radiance.values)
        # Physics: the partial column is more transparent than the full one.
        band_up = _band_mean(wl, q.tau_up, 8.0, 13.0)
        band_full = _band_mean(wl, q.tau_full_up, 8.0, 13.0)
        assert band_up > band_full
        # Same G3 anchor the build_state golden pins (slit-degraded ~0.923).
        assert band_up == pytest.approx(0.9253, abs=5e-3)

    def test_evaluate_pure_thermal_no_solar_mismatch_warning(self) -> None:
        """Boost plan §4.6: a pure-thermal scene (theta_s = None — no solar
        geometry declared) adopts the RECORDED run sun (30°) rather than a
        literal 0.0 that would spuriously trip the CU-167 solar mismatch.
        Only the pre-existing τ_sun collapse warning may fire."""
        from radiant.core.los_geometry import LineOfSightGeometry

        ladders = _load_interpolated(
            "midlat_summer_ladders", ["sensor_altitude_m", "target_altitude_m"]
        )
        wl = ladders.wavelength_um
        session = RadiantSession(wavelength_um=wl)
        params = session.default_params()
        params.set("source.target.temperature", 300.0)
        params.set("source.target.emissivity", 0.95)
        params.set("geometry.sensor_altitude_m", 100_000.0)
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

        los = LineOfSightGeometry(
            h_tgt=10_000.0, h_sensor=100_000.0, theta_o=0.0, h_atm_top=1.0e5
        )
        assert los.theta_s is None  # pure-thermal contract
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            ladders.evaluate(wl, los, params)
        solar_warnings = [w for w in caught if "solar_zenith_rad" in str(w.message)]
        assert solar_warnings == []
        # An EXPLICIT solar zenith differing from the recorded 30° still warns.
        los_sun = LineOfSightGeometry(
            h_tgt=10_000.0,
            h_sensor=100_000.0,
            theta_o=0.0,
            h_atm_top=1.0e5,
            theta_s=np.radians(60.0),
        )
        with pytest.warns(UserWarning, match="solar_zenith_rad.*IGNORED"):
            ladders.evaluate(wl, los_sun, params)


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


# ---------------------------------------------------------------------------
# Boost-ladder expansion families (MODTRAN_Boost_Ladder_Expansion_Plan §5).
# Scaffolded 2026-07-20 ahead of the 17-run delivery: each class skips until
# scripts/build_atmosphere_library.py has produced its family from the
# delivered tape7s. Numeric goldens (band-mean τ anchors, the CO₂ band-core
# threshold) are pinned AT BUILD TIME from the delivered runs — the plan's
# no-fabricated-data policy; the structural physics below needs no goldens.
# ---------------------------------------------------------------------------

_BOOST_LADDER_DIR = _LIB / "midlat_summer_boost_ladder"
_BOOST_OFFNADIR_DIR = _LIB / "midlat_summer_boost_offnadir"
_SENSOR_LADDER_DIR = _LIB / "midlat_summer_sensor_ladder"


@pytest.mark.level2
@pytest.mark.skipif(
    not _BOOST_LADDER_DIR.exists(),
    reason="boost-ladder family not yet built (plan §4.1; awaiting G7–G11 tape7s)",
)
class TestBoostLadder:
    """Nadir boost ladder: targets 0–100 km from a space sensor."""

    def _model(self) -> InterpolatedAtmosphere:
        return _load_interpolated(
            "midlat_summer_boost_ladder", ["sensor_altitude_m", "target_altitude_m"]
        )

    def test_tau_monotone_in_target_altitude_0_to_100km(self) -> None:
        """τ_up(h_tgt) increases with target altitude (less column below
        the sensor): band-mean 8–13 µm and 3.5–5 µm, nadir, 100 km sensor."""
        model = self._model()
        wl = model.wavelength_um
        heights_m = [0.0, 10_000.0, 29_000.0, 35_000.0, 50_000.0, 80_000.0, 100_000.0]
        for lo_um, hi_um in ((8.0, 13.0), (3.5, 5.0)):
            taus = []
            for h in heights_m:
                geom = AtmosphericGeometry(
                    sensor_altitude_m=100_000.0,
                    target_altitude_m=h,
                    path_zenith_rad=0.0,
                    solar_zenith_rad=np.radians(30.0),
                    solar_azimuth_rad=0.0,
                )
                state = model.build_state(wl, geom)
                taus.append(_band_mean(wl, state.transmittance.values, lo_um, hi_um))
            assert all(a < b + 1e-12 for a, b in zip(taus, taus[1:], strict=False)), (
                f"τ({lo_um}–{hi_um} µm) not monotone over target altitude: {taus}"
            )

    def test_band_mean_tau_anchors(self) -> None:
        """Pinned band-mean τ at the new boost rungs (plan §5), extracted
        from the delivered G7–G11 runs (slit-degraded, ±0.005). The
        existing 0/10/29 km rungs match the untouched ladder family."""
        model = self._model()
        wl = model.wavelength_um
        # h_tgt km -> (τ(8–13 µm), τ(3.5–5 µm)).
        anchors = {
            0.0: (0.557, 0.501),
            10.0: (0.923, 0.786),
            29.0: (0.978, 0.929),
            35.0: (0.989, 0.958),
            40.0: (0.994, 0.973),
            50.0: (0.999, 0.988),
            60.0: (1.000, 0.995),
            80.0: (1.000, 0.999),
        }
        for h_km, (lwir, mwir) in anchors.items():
            geom = AtmosphericGeometry(
                sensor_altitude_m=100_000.0,
                target_altitude_m=h_km * 1000.0,
                path_zenith_rad=0.0,
                solar_zenith_rad=np.radians(30.0),
                solar_azimuth_rad=0.0,
            )
            v = model.build_state(wl, geom).transmittance.values
            assert _band_mean(wl, v, 8.0, 13.0) == pytest.approx(lwir, abs=5e-3)
            assert _band_mean(wl, v, 3.5, 5.0) == pytest.approx(mwir, abs=5e-3)

    def test_vacuum_node_exact_at_100km(self) -> None:
        """The synthesized 100 km rung is the exact identity τ ≡ 1,
        L_path ≡ 0 W/m²/sr/µm — continuity into the Gap 95 exo branch."""
        model = self._model()
        wl = model.wavelength_um
        geom = AtmosphericGeometry(
            sensor_altitude_m=100_000.0,
            target_altitude_m=100_000.0,
            path_zenith_rad=0.0,
            solar_zenith_rad=np.radians(30.0),
            solar_azimuth_rad=0.0,
        )
        state = model.build_state(wl, geom)
        np.testing.assert_allclose(state.transmittance.values, 1.0, atol=1e-6)
        np.testing.assert_allclose(state.path_radiance.values, 0.0, atol=1e-12)

    def test_co2_band_core_real_at_50km(self) -> None:
        """The reason the boost rungs exist: the 4.20–4.45 µm CO₂ band core
        carries real stratospheric structure the rungs must resolve, not a
        vacuum interpolation. Pinned to the delivered G9 run
        (slit-degraded), which also guards against a future 'optimization'
        deleting the rungs — the band core climbs 0.58 (29 km) → 0.75
        (35 km) → 0.92 (50 km) → 1.0 (vacuum), a curve no two-node
        interpolation between 29 km and the 100 km vacuum reproduces
        (plan §5)."""
        model = self._model()
        wl = model.wavelength_um

        def _co2(h_km: float) -> float:
            geom = AtmosphericGeometry(
                sensor_altitude_m=100_000.0,
                target_altitude_m=h_km * 1000.0,
                path_zenith_rad=0.0,
                solar_zenith_rad=np.radians(30.0),
                solar_azimuth_rad=0.0,
            )
            return _band_mean(wl, model.build_state(wl, geom).transmittance.values, 4.20, 4.45)

        # Delivered-run band-core anchors (slit-degraded, ±0.02).
        assert _co2(29.0) == pytest.approx(0.580, abs=0.02)
        assert _co2(35.0) == pytest.approx(0.750, abs=0.02)
        assert _co2(50.0) == pytest.approx(0.923, abs=0.02)
        # Materially below 1 (real CO₂ residual) and strictly rising with
        # altitude — the structure the rungs exist to carry.
        assert _co2(29.0) < _co2(35.0) < _co2(50.0) < 0.98


@pytest.mark.level2
@pytest.mark.skipif(
    not _BOOST_OFFNADIR_DIR.exists(),
    reason="boost off-nadir family not yet built (plan §4.3; awaiting I1–I9 tape7s)",
)
class TestBoostOffNadir:
    """3-D target × zenith grid at the space sensor (I-block + nadir nodes)."""

    _AXES = ["sensor_altitude_m", "target_altitude_m", "path_zenith_rad"]

    def test_45deg_column_consistent_with_airmass_prediction(self) -> None:
        """B-fan holdout methodology at altitude (plan §5): rebuild the
        zenith axis from ONLY the 0° and 60° columns at h_tgt = 29 km,
        predict 45° via airmass-space interpolation (CU-160), and compare
        against the real 45° node. Envelope matches the CU-160 fan
        acceptance (0.5% band-mean τ)."""
        model = _load_interpolated("midlat_summer_boost_offnadir", self._AXES)
        wl = model.wavelength_um

        def _tau(zenith_rad: float) -> np.ndarray:
            geom = AtmosphericGeometry(
                sensor_altitude_m=100_000.0,
                target_altitude_m=29_000.0,
                path_zenith_rad=zenith_rad,
                solar_zenith_rad=np.radians(30.0),
                solar_azimuth_rad=0.0,
            )
            return model.build_state(wl, geom).transmittance.values

        tau_0, tau_45, tau_60 = _tau(0.0), _tau(np.radians(45.0)), _tau(np.radians(60.0))
        sec = lambda t: 1.0 / np.cos(t)  # noqa: E731
        frac = (sec(np.radians(45.0)) - sec(0.0)) / (sec(np.radians(60.0)) - sec(0.0))
        tau_45_pred = np.exp(
            (1.0 - frac) * np.log(np.clip(tau_0, 1e-30, 1.0))
            + frac * np.log(np.clip(tau_60, 1e-30, 1.0))
        )
        band_real = _band_mean(wl, tau_45, 8.0, 13.0)
        band_pred = _band_mean(wl, tau_45_pred, 8.0, 13.0)
        assert band_pred == pytest.approx(band_real, rel=5e-3)

    def test_vacuum_rung_exact_at_all_zeniths(self) -> None:
        """Plan §4.2 (2026-07-19 amendment): the synthesized 100 km rung
        holds at EVERY zenith column — τ ≡ 1 at 0°/45°/60°, so the
        acceptance sweep's 80–100 km band is inside the hull off-nadir."""
        model = _load_interpolated("midlat_summer_boost_offnadir", self._AXES)
        wl = model.wavelength_um
        for zen_deg in (0.0, 45.0, 60.0):
            geom = AtmosphericGeometry(
                sensor_altitude_m=100_000.0,
                target_altitude_m=100_000.0,
                path_zenith_rad=np.radians(zen_deg),
                solar_zenith_rad=np.radians(30.0),
                solar_azimuth_rad=0.0,
            )
            state = model.build_state(wl, geom)
            np.testing.assert_allclose(
                state.transmittance.values,
                1.0,
                atol=1e-6,
                err_msg=f"vacuum rung not exact at {zen_deg}°",
            )

    def test_tau_decreases_with_zenith_at_fixed_target(self) -> None:
        """Longer slant column → lower τ: 0° > 45° > 60° at h_tgt = 0."""
        model = _load_interpolated("midlat_summer_boost_offnadir", self._AXES)
        wl = model.wavelength_um
        taus = []
        for zen_deg in (0.0, 45.0, 60.0):
            geom = AtmosphericGeometry(
                sensor_altitude_m=100_000.0,
                target_altitude_m=0.0,
                path_zenith_rad=np.radians(zen_deg),
                solar_zenith_rad=np.radians(30.0),
                solar_azimuth_rad=0.0,
            )
            state = model.build_state(wl, geom)
            taus.append(_band_mean(wl, state.transmittance.values, 8.0, 13.0))
        assert taus[0] > taus[1] > taus[2]


@pytest.mark.level2
@pytest.mark.skipif(
    not _SENSOR_LADDER_DIR.exists(),
    reason="sensor-ladder family not yet built (plan §4.5; awaiting J1–J2 tape7s)",
)
class TestSensorLadder:
    """1-D airborne sensor-altitude family (F2/J1/J2/C1/A3 + orbital node)."""

    def test_tau_monotone_in_sensor_altitude(self) -> None:
        """More column below the sensor → lower τ: for a GROUND target,
        band-mean τ DECREASES as the sensor climbs (3 → 100 km sees more
        of the ground→sensor column), converging to the full-column value
        as the sensor approaches TOA. Pinned to the delivered runs
        (F2/J1/J2/C1/A3, slit-degraded, ±0.005)."""
        model = _load_interpolated("midlat_summer_sensor_ladder", ["sensor_altitude_m"])
        wl = model.wavelength_um
        expected = {3.0: 0.640, 10.0: 0.601, 20.0: 0.574, 35.0: 0.558, 100.0: 0.557}
        taus = []
        for h_km in (3.0, 10.0, 20.0, 35.0, 100.0):
            geom = AtmosphericGeometry(
                sensor_altitude_m=h_km * 1000.0,
                target_altitude_m=0.0,
                path_zenith_rad=0.0,
                solar_zenith_rad=np.radians(30.0),
                solar_azimuth_rad=0.0,
            )
            state = model.build_state(wl, geom)
            tau = _band_mean(wl, state.transmittance.values, 8.0, 13.0)
            assert tau == pytest.approx(expected[h_km], abs=5e-3)
            taus.append(tau)
        assert all(a > b - 1e-12 for a, b in zip(taus, taus[1:], strict=False)), (
            f"τ(8–13 µm) not monotone-decreasing over sensor altitude: {taus}"
        )

    def test_leo_query_inside_orbital_hull(self) -> None:
        """A 500 km LEO sensor lands inside the duplicated-node hull and
        matches the 100 km TOA column exactly (vacuum above TOA)."""
        model = _load_interpolated("midlat_summer_sensor_ladder", ["sensor_altitude_m"])
        wl = model.wavelength_um

        def _state(h_m: float):
            return model.build_state(
                wl,
                AtmosphericGeometry(
                    sensor_altitude_m=h_m,
                    target_altitude_m=0.0,
                    path_zenith_rad=0.0,
                    solar_zenith_rad=np.radians(30.0),
                    solar_azimuth_rad=0.0,
                ),
            )

        np.testing.assert_allclose(
            _state(500_000.0).transmittance.values,
            _state(100_000.0).transmittance.values,
            rtol=1e-10,
        )
