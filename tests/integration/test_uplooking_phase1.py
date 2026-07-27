"""Integration proof for Geometry-Flexibility **Phase 1** (ADR-0011).

Phase 1 makes the *geometry core* direction-general: ``theta_o`` spans the
closed domain ``[0, π]``, ``LineOfSightGeometry`` carries both endpoints, and
the two-topology horizon guard replaces the old blanket ``h_sensor >
h_target`` rejection.  The **atmosphere** is deliberately untouched — it is
still direction-blind and Phase 2 work (Gaps 108/109).

This module pins the four seams where those two facts meet:

1. **The LEO→GEO quick win** (plan §4 Phase 1 exit criterion (a)) — an
   up-looking space-to-space scene runs end-to-end, vertically
   (``theta_o = π`` *exactly*) and on a slant, because both endpoints sit
   above ``h_atm_top`` so the whole path is vacuum by construction.
2. **The ground→air seam** — a ground→air up-looking scene is accepted by
   the geometry layer and, since **Phase 2** (2026-07-26), served by the
   direction-aware atmosphere; the refusal that remains is the *capability*
   one for a backend without up-looking run families, and it still must not
   surface as a backend-internal ``ZENITH_CEILING`` message (Rule 15).
3. **The horizon guard**, exercised through ``GeometryStage`` rather than in
   unit isolation: an interior-tangent level path warns, an
   endpoint-minimum grazing path raises, a short tower-to-tower arm is
   clean.
4. **Serialization** of the extended contract, including the
   pre-ADR-0011 payload shape.

Down-looking behaviour is *not* re-tested here: zero drift for the existing
scenes is the whole golden suite's job (plan §3 principle 3).
"""

from __future__ import annotations

import math
import warnings

import numpy as np
import pytest

from radiant.api.session import RadiantSession
from radiant.core.chain import ChainRunner, ChainState
from radiant.core.constants import R_EARTH_M
from radiant.core.los_geometry import LineOfSightGeometry
from radiant.core.parameters import ParameterBoundsError, ParameterSet
from radiant.core.regime import RadiometricRegime
from radiant.core.solar import toa_solar_spectral_irradiance
from radiant.geometry.stage import GeometryStage

# ---------------------------------------------------------------------------
# Scenario constants
# ---------------------------------------------------------------------------

VIS_WL = np.linspace(0.45, 0.80, 141)
MWIR_WL = np.linspace(3.5, 5.0, 61)

H_LEO_M = 500_000.0
H_GEO_M = 35_786_000.0
TARGET_RHO = 0.25  # dimensionless Lambertian reflectance
TARGET_AREA_M2 = 20.0  # m² projected area of the GEO bus
THETA_S_RAD = 0.6  # rad, solar zenith at the target


def _seed_system(params: ParameterSet, band: str) -> None:
    """Seed a minimal, physically sane imaging system for *band*.

    Nothing here is under test; these are the parameters ``params.resolve()``
    requires before any chain can run.
    """
    if band == "VIS":
        params.set("optics.aperture_diameter_m", 0.30)
        params.set("optics.focal_length_m", 3.0)
        params.set("detector.pixel_pitch_x_um", 10.0)
        params.set("detector.pixel_pitch_y_um", 10.0)
        params.set("detector.qe_value", 0.75)
        params.set("detector.dark_rate_e_per_s", 50.0)
        params.set("spectral_integration.filter_min_um", 0.45)
        params.set("spectral_integration.filter_max_um", 0.80)
        params.set("spectral_integration.integration_time_s", 0.10)
        params.set("readout.read_noise_e_rms", 5.0)
    else:  # MWIR
        params.set("optics.aperture_diameter_m", 0.30)
        params.set("optics.focal_length_m", 1.5)
        params.set("detector.pixel_pitch_x_um", 15.0)
        params.set("detector.pixel_pitch_y_um", 15.0)
        params.set("detector.qe_value", 0.70)
        params.set("detector.dark_rate_e_per_s", 1000.0)
        params.set("spectral_integration.filter_min_um", 3.5)
        params.set("spectral_integration.filter_max_um", 5.0)
        params.set("spectral_integration.integration_time_s", 0.005)
        params.set("readout.read_noise_e_rms", 30.0)
    params.set("optics.transmission_scalar", 0.60)
    params.set("readout.gain_e_per_dn", 2.0)
    params.set("readout.adc_bits", 14)


def _deselect_ground_metrics(params: ParameterSet) -> None:
    """Turn off the metric groups that project onto the ground (Gap 96).

    GSD, ground range, swath, access rate (``sampling``) and NIIRS
    (``interpretability``) are all defined against a *ground* target through
    ``incidence_angle_rad ∈ [0, π/2)``.  For a space-to-space scene there is
    no ground to project onto, so they are deselected exactly as the metric
    selection machinery intends — the Phase 3 scene-class → relevance map
    (guardrail G3) is what will eventually make this the default.
    """
    params.set("performance.metrics.sampling", False)
    params.set("performance.metrics.interpretability", False)


def _leo_to_geo_params(session: RadiantSession, *, zeta_low_rad: float | None) -> ParameterSet:
    """LEO(500 km) → GEO(35 786 km) sunlit VIS point source.

    ``zeta_low_rad`` is entered at the path's **lower** endpoint (ADR-0011
    decision 3), which for this scene is the *sensor*.  ``None`` leaves the
    schema default (0 rad = target straight overhead) in place, which
    resolves to ``theta_o = π`` exactly.
    """
    p = session.default_params()
    p.set("source.target.reflectance", TARGET_RHO)
    p.set("source.scene_type", "point_source")
    p.set("atmosphere.model", "exo")  # → no_atmosphere / space sub-case
    p.set("geometry.sensor_altitude_m", H_LEO_M)
    p.set("geometry.target_altitude_m", H_GEO_M)
    if zeta_low_rad is not None:
        p.set("geometry.path_zenith_rad", zeta_low_rad)
    p.set("geometry.solar_illumination", "day")
    p.set("geometry.solar_zenith_rad", THETA_S_RAD)
    p.set("geometry.target.projected_area_m2", TARGET_AREA_M2)
    _seed_system(p, "VIS")
    _deselect_ground_metrics(p)
    p.resolve()
    return p


def _run_geometry_only(params: ParameterSet, wavelength_um: np.ndarray) -> ChainState:
    """Run ``GeometryStage`` alone.

    The horizon guard lives on the ``LineOfSightGeometry`` this stage
    publishes, so its verdict is observable here — and observable *without*
    the Phase-2 atmosphere refusal that a full chain would hit first for the
    level and up-looking scenes below.
    """
    return ChainRunner([GeometryStage()]).run(params, wavelength_um)


def _horizon_warnings(records: list[warnings.WarningMessage]) -> list[str]:
    """Messages of the ``UserWarning``s raised by the horizon guard."""
    return [
        str(r.message)
        for r in records
        if issubclass(r.category, UserWarning) and "horizon guard" in str(r.message)
    ]


# ---------------------------------------------------------------------------
# 1. LEO → GEO up-looking quick win (Phase 1 exit criterion (a))
# ---------------------------------------------------------------------------


@pytest.mark.level2
class TestLeoToGeoUpLooking:
    """Up-looking space-to-space, end-to-end through the real session.

    Worked example E9's up-looking arm (`RADIANT_Use_Case_Matrix.md` §3.4).
    The exo backend already handled this composition; the *only* blocker was
    the geometry gate, which is what Phase 1 removes.
    """

    def test_vertical_uplooking_resolves_theta_o_exactly_pi(self) -> None:
        """θ_o = π **exactly** — the domain must be closed at π.

        A LEO sensor directly beneath a GEO bus is not an edge case to be
        approximated: it is the mirror of the nadir view (θ_o = 0) and lands
        on the endpoint of the domain.  ADR-0011 writes "[0, π)"; the closed
        interval is what the geometry requires and what is implemented
        (flagged notation slip, pending owner confirmation).
        """
        session = RadiantSession(wavelength_um=VIS_WL)
        params = _leo_to_geo_params(session, zeta_low_rad=None)

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            result = session.run(params)

        geom = result.stage_outputs["geometry"]
        assert geom["theta_o_rad"] == math.pi
        assert geom["los_direction"] == "up"
        # Radial path: slant range is the altitude difference, exactly.
        assert geom["slant_range_m"] == pytest.approx(H_GEO_M - H_LEO_M, abs=1e-6)
        assert geom["ground_range_m"] == pytest.approx(0.0, abs=1e-9)

    def test_vertical_uplooking_runs_end_to_end_in_vacuum(self) -> None:
        session = RadiantSession(wavelength_um=VIS_WL)
        params = _leo_to_geo_params(session, zeta_low_rad=None)

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            result = session.run(params)

        los = result.stage_outputs["geometry"]["los_geometry"]
        assert los.h_sensor == H_LEO_M
        assert los.h_tgt == H_GEO_M
        assert los.is_uplooking is True
        # No earthlimb transit — the LOS climbs radially away from Earth.
        assert los.intercepts_earth(H_LEO_M) is False

        # Vacuum path: every transport term is the exact identity, on BOTH
        # the target leg and the "full column" terms (there is no ground
        # behind an up-looking target — the LOS terminates on deep space).
        q = result.stage_outputs["atmosphere"]["atm_quantities"]
        ones = np.ones_like(VIS_WL)
        zeros = np.zeros_like(VIS_WL)
        np.testing.assert_array_equal(q.tau_up, ones)
        np.testing.assert_array_equal(q.tau_sun, ones)
        np.testing.assert_array_equal(q.tau_full_up, ones)
        np.testing.assert_array_equal(q.L_path_up, zeros)
        np.testing.assert_array_equal(q.L_path_full, zeros)
        np.testing.assert_array_equal(q.E_sky_scattered, zeros)
        np.testing.assert_array_equal(q.E_sky_thermal, zeros)

        # At-aperture target radiance is the exo vacuum expectation:
        #   L_t = ρ · E_TOA(λ) · cos(θ_s) / π   [W/m²/sr/µm]
        L_t = result.frames["at_aperture_target"].spectral_radiance
        expected = (
            TARGET_RHO
            * np.asarray(toa_solar_spectral_irradiance(VIS_WL))
            * math.cos(THETA_S_RAD)
            / math.pi
        )
        assert np.all(np.isfinite(L_t))
        np.testing.assert_allclose(L_t, expected, rtol=1e-12)

        # Background is cold space (B1): identically zero radiance.
        background = result.stage_outputs["source"]["background"]
        assert type(background).__name__ == "ColdSpaceBackground"
        L_bg = result.frames["at_aperture_background"].spectral_radiance
        np.testing.assert_array_equal(L_bg, zeros)

        # And the chain produced a finite, positive detection metric.
        assert result.stage_outputs["optics"]["regime"] is RadiometricRegime.POINT_SOURCE
        snr = float(result.metrics["snr"])
        assert math.isfinite(snr) and snr > 0.0

    def test_slant_uplooking_runs_and_differs_from_the_vertical_case(self) -> None:
        """A 0.30 rad slant at the sensor — the non-degenerate up-looking path.

        Two things matter here: the obtuse θ_o is *derived* from the
        lower-endpoint entry (θ_o = π − ζ_up, ADR-0011 decision 3) rather
        than entered, and the resulting geometry is a genuinely different
        triangle — longer slant, non-zero ground arc — so the test cannot
        pass by accidentally re-running the vertical case.
        """
        session = RadiantSession(wavelength_um=VIS_WL)
        zeta_low = 0.30
        params = _leo_to_geo_params(session, zeta_low_rad=zeta_low)

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            result = session.run(params)

        geom = result.stage_outputs["geometry"]
        theta_o = float(geom["theta_o_rad"])
        assert geom["los_direction"] == "up"
        assert math.pi / 2.0 < theta_o < math.pi

        # θ_o = π − asin((r_sensor / r_target) · sin ζ_low) — the law of
        # sines read from the lower (sensor) endpoint.
        r_s = R_EARTH_M + H_LEO_M
        r_t = R_EARTH_M + H_GEO_M
        expected_theta_o = math.pi - math.asin((r_s / r_t) * math.sin(zeta_low))
        assert theta_o == pytest.approx(expected_theta_o, rel=1e-12)

        # Genuinely off-axis: longer than the radial path, non-zero arc.
        assert float(geom["slant_range_m"]) > H_GEO_M - H_LEO_M
        assert float(geom["ground_range_m"]) > 0.0

        los = geom["los_geometry"]
        assert los.intercepts_earth(H_LEO_M) is False

        q = result.stage_outputs["atmosphere"]["atm_quantities"]
        np.testing.assert_array_equal(q.tau_up, np.ones_like(VIS_WL))
        np.testing.assert_array_equal(q.L_path_up, np.zeros_like(VIS_WL))

        L = result.frames["at_aperture"].spectral_radiance
        assert np.all(np.isfinite(L))
        assert np.all(L >= 0.0)
        snr = float(result.metrics["snr"])
        assert math.isfinite(snr) and snr > 0.0


# ---------------------------------------------------------------------------
# 2. Layered rejection — geometry accepts, atmosphere refuses (Phase 2)
# ---------------------------------------------------------------------------


@pytest.mark.level2
class TestUpLookingThroughAtmosphere:
    """Ground site → 10 km airborne target on the simple atmosphere.

    Worked example E2 (owner priority 1).  Phase 1 accepted the geometry and
    **Phase 2 supplies the radiometry** (2026-07-26), so this scene now runs
    end-to-end: the Phase-1 pending-capability refusal this class used to
    assert is lifted, and what replaces it is the full-chain proof plus the
    *capability* refusal that survives it (a backend without up-looking run
    families still fails actionably).
    """

    @staticmethod
    def _params(session: RadiantSession) -> ParameterSet:
        p = session.default_params()
        p.set("source.target.temperature", 500.0)
        p.set("source.target.emissivity", 0.9)
        p.set("source.scene_type", "point_source")
        p.set("atmosphere.model", "simple")
        p.set("atmosphere.standard_atmosphere", "midlat_summer")
        p.set("geometry.sensor_altitude_m", 0.0)  # ground site
        p.set("geometry.target_altitude_m", 10_000.0)  # airborne target
        # 20° from the sensor's zenith — entered at the LOWER endpoint.
        p.set("geometry.path_zenith_rad", math.radians(20.0))
        # Deliberately tiny: at 10 km with this optic a real aircraft is
        # resolved, and the point-source guard (matrix §7) rightly refuses it.
        # The scene under test is the atmosphere, not the target model.
        p.set("geometry.target.projected_area_m2", 1.0e-4)
        _seed_system(p, "MWIR")
        _deselect_ground_metrics(p)
        p.resolve()
        return p

    def test_geometry_layer_accepts_the_uplooking_scene(self) -> None:
        """Phase 1 half of the contract: the geometry itself is legal."""
        session = RadiantSession(wavelength_um=MWIR_WL)
        params = self._params(session)

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            state = _run_geometry_only(params, MWIR_WL)

        geom = state.stage_outputs["geometry"]
        assert geom["los_direction"] == "up"
        theta_o = float(geom["theta_o_rad"])
        assert theta_o > math.pi / 2.0
        assert geom["los_geometry"].h_sensor == 0.0

    def test_ground_to_air_runs_end_to_end(self) -> None:
        """Phase 2 half of the contract: the radiometry is there now."""
        session = RadiantSession(wavelength_um=MWIR_WL)
        params = self._params(session)

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            result = session.run(params)

        geom = result.stage_outputs["geometry"]
        assert geom["los_direction"] == "up"

        q = result.stage_outputs["atmosphere"]["atm_quantities"]
        # A real column was traversed, in both directions of the product:
        # attenuating (τ < 1 everywhere) and emitting (L_path > 0).
        assert float(q.tau_up.max()) < 1.0
        assert float(q.tau_up.min()) > 0.0
        assert float(q.L_path_up.min()) > 0.0
        # Rule 16/17: nothing silently non-finite reaches the assembly.
        for field in ("tau_sun", "tau_up", "tau_full_up", "L_path_up", "L_path_full"):
            assert np.all(np.isfinite(getattr(q, field))), field

        # The scene is a SkyBackground scene by Rule B — the LOS continues
        # past the aircraft and leaves the atmosphere.
        background = result.stage_outputs["source"]["background"]
        assert type(background).__name__ == "SkyBackground"
        assert "at_aperture_background" in result.frames

        # And the chain produced a usable answer, not a NaN.
        signal = result.stage_outputs["spectral_integration"]["signal_e"]
        assert math.isfinite(float(signal)) and float(signal) > 0.0

    def test_uplooking_transmittance_is_reciprocal_with_the_down_look(self) -> None:
        """ADR-0011 decision 3: one τ per segment, keyed to the lower endpoint.

        The ground→10 km up-look at ζ_low = 20° and the 10 km→ground
        down-look over the same column must agree.  Entered from the lower
        endpoint both times, so no ``asin``/``sin`` round trip intervenes and
        the agreement is exact.
        """
        from radiant.atmosphere.simple import SimpleAtmosphere
        from radiant.atmosphere.topology import evaluate_path_topology

        session = RadiantSession(wavelength_um=MWIR_WL)
        params = self._params(session)
        atm = SimpleAtmosphere(standard_atmosphere="midlat_summer")
        zeta_low = math.radians(20.0)

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            state = _run_geometry_only(params, MWIR_WL)
            up_los = state.stage_outputs["geometry"]["los_geometry"]
            up = evaluate_path_topology(atm, MWIR_WL, up_los, params).quantities
            down_los = LineOfSightGeometry(
                h_tgt=0.0, h_sensor=10_000.0, theta_o=zeta_low, h_atm_top=1.0e5
            )
            down = evaluate_path_topology(atm, MWIR_WL, down_los, params).quantities

        np.testing.assert_allclose(up.tau_up, down.tau_up, rtol=1e-12, atol=0.0)


# ---------------------------------------------------------------------------
# 3. Horizon guard, exercised through GeometryStage
# ---------------------------------------------------------------------------


@pytest.mark.level2
class TestHorizonGuardThroughGeometryStage:
    """Both guard topologies, reached through real parameter entry.

    Thresholds are the provisional plan-§8.3 values (0.5° / 2° angular;
    100 m / 2 km tangent depression), calibrated in Phase 2 against a
    MODTRAN refraction on/off deck pair.
    """

    @staticmethod
    def _params(session: RadiantSession, **geometry: float) -> ParameterSet:
        p = session.default_params()
        p.set("source.target.temperature", 500.0)
        p.set("source.target.emissivity", 0.9)
        for name, value in geometry.items():
            p.set(f"geometry.{name}", value)
        _seed_system(p, "MWIR")
        p.resolve()
        return p

    def test_level_200_km_air_to_air_computes_with_a_warning(self) -> None:
        """Interior-tangent topology, shoulder band (§8.3 answer 1).

        Two aircraft at 10 km, 200 km apart: the chord sags Δh ≈ L²/8R_E ≈
        784 m below the endpoints, inside the 100 m – 2 km warn band.  This
        is the ratified "long-range air-to-air stays usable at first
        delivery" case, and the warning must *quantify* the sag rather than
        say "near the horizon".
        """
        session = RadiantSession(wavelength_um=MWIR_WL)
        params = self._params(
            session,
            sensor_altitude_m=10_000.0,
            target_altitude_m=10_000.0,
            target_range_m=200_000.0,
        )

        with warnings.catch_warnings(record=True) as records:
            warnings.simplefilter("always")
            state = _run_geometry_only(params, MWIR_WL)

        messages = _horizon_warnings(records)
        assert len(messages) >= 1, "level 200 km path must warn"
        message = messages[0]
        assert "interior tangent" in message
        assert "refraction" in message
        # Quantified, not qualitative: the message states Δh in metres, and
        # the value matches the small-angle form Δh ≈ L²/8R_E to well under
        # a percent, inside the 100 m – 2 km warn band.
        dh_reported = float(message.split("interior tangent point ")[1].split(" m below")[0])
        dh_small_angle = 200_000.0**2 / (8.0 * R_EARTH_M)
        assert dh_reported == pytest.approx(dh_small_angle, rel=5e-3)
        assert 100.0 < dh_reported < 2000.0

        geom = state.stage_outputs["geometry"]
        assert geom["los_direction"] == "level"
        # Level path: θ_o = π/2 + φ/2 with φ the central angle.
        phi = 2.0 * math.asin(200_000.0 / (2.0 * (R_EARTH_M + 10_000.0)))
        assert float(geom["theta_o_rad"]) == pytest.approx(math.pi / 2.0 + phi / 2.0, rel=1e-12)
        assert float(geom["slant_range_m"]) == pytest.approx(200_000.0, rel=1e-9)

    def test_down_looking_89_7_deg_raises(self) -> None:
        """Endpoint-minimum topology, hard band: 0.3° from the horizontal."""
        session = RadiantSession(wavelength_um=MWIR_WL)
        params = self._params(
            session,
            sensor_altitude_m=500_000.0,
            target_altitude_m=0.0,
            path_zenith_rad=math.radians(89.7),
        )

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            with pytest.raises(ParameterBoundsError) as excinfo:
                _run_geometry_only(params, MWIR_WL)

        message = str(excinfo.value)
        assert "horizon guard" in message
        assert "refraction" in message
        assert excinfo.value.context["topology"] == "endpoint_minimum"
        assert math.degrees(excinfo.value.context["band_rad"]) == pytest.approx(0.3, abs=1e-9)

    def test_two_towers_8_km_apart_compute_clean(self) -> None:
        """Interior-tangent topology, clean band — and guardrail G4.

        Two 30 m towers 8 km apart sag Δh ≈ 1.3 m: benign, and a pure
        angular test would have rejected it (θ_o ≈ 90.04°).  This scene is
        also the one that used to hit the *collocated no-triangle carve-out*
        — equal altitudes now resolve to a real horizontal triangle with a
        slant range and a ground arc, which is what retires the carve-out.
        """
        session = RadiantSession(wavelength_um=MWIR_WL)
        params = self._params(
            session,
            sensor_altitude_m=30.0,
            target_altitude_m=30.0,
            target_range_m=8_000.0,
        )

        with warnings.catch_warnings(record=True) as records:
            warnings.simplefilter("always")
            state = _run_geometry_only(params, MWIR_WL)

        assert _horizon_warnings(records) == []

        geom = state.stage_outputs["geometry"]
        assert geom["los_direction"] == "level"
        theta_o_deg = math.degrees(float(geom["theta_o_rad"]))
        assert 90.0 < theta_o_deg < 90.1
        # The carve-out is gone: a real triangle, not three Nones.
        assert float(geom["slant_range_m"]) == pytest.approx(8_000.0, rel=1e-9)
        assert float(geom["ground_range_m"]) == pytest.approx(8_000.0, rel=1e-4)
        assert geom["eta_rad"] is not None

    def test_long_level_transit_raises_as_limb_like(self) -> None:
        """Interior-tangent topology, raise band: 500 km at 5 km sags ≈ 4.9 km.

        The counterpart of the tower case — a blanket equal-altitude
        exemption would have accepted this limb-like transit.
        """
        session = RadiantSession(wavelength_um=MWIR_WL)
        params = self._params(
            session,
            sensor_altitude_m=5_000.0,
            target_altitude_m=5_000.0,
            target_range_m=500_000.0,
        )

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            with pytest.raises(ParameterBoundsError) as excinfo:
                _run_geometry_only(params, MWIR_WL)

        assert excinfo.value.context["topology"] == "interior_tangent"
        assert excinfo.value.context["tangent_depression_m"] > 2000.0
        assert "limb-like transit" in str(excinfo.value)

    def test_down_looking_shoulder_now_warns_where_it_was_silent(self) -> None:
        """Deliberate consequence of the guard, recorded so it is not a surprise.

        A down-looking θ_o in (88°, 90°) used to be accepted silently (the
        old schema bound stopped at 89.5°).  It now falls in the shoulder
        band and warns.  No shipped scenario or golden baseline is anywhere
        near it — the existing set tops out around 75° — so this changes no
        result, only the warning surface.
        """
        session = RadiantSession(wavelength_um=MWIR_WL)
        params = self._params(
            session,
            sensor_altitude_m=500_000.0,
            target_altitude_m=0.0,
            path_zenith_rad=math.radians(89.0),
        )

        with warnings.catch_warnings(record=True) as records:
            warnings.simplefilter("always")
            state = _run_geometry_only(params, MWIR_WL)

        messages = _horizon_warnings(records)
        assert len(messages) >= 1
        assert "1.0000°" in messages[0]
        assert state.stage_outputs["geometry"]["los_direction"] == "down"


# ---------------------------------------------------------------------------
# 4. Serialization of the extended contract
# ---------------------------------------------------------------------------


class TestLineOfSightGeometrySerialization:
    """``h_sensor`` joins the contract without breaking older payloads."""

    def test_round_trip_with_sensor_endpoint(self) -> None:
        los = LineOfSightGeometry(
            h_tgt=H_GEO_M,
            h_sensor=H_LEO_M,
            theta_o=math.pi,
            theta_s=THETA_S_RAD,
            delta_phi=-0.4,
        )
        payload = los.to_dict()
        assert payload["h_sensor"] == H_LEO_M

        restored = LineOfSightGeometry.from_dict(payload)
        assert restored == los
        assert restored.h_sensor == H_LEO_M
        assert restored.los_direction == "up"
        assert restored.to_dict() == payload

    def test_round_trip_without_sensor_endpoint_omits_the_key(self) -> None:
        """A LOS that does not carry the endpoint serializes to the old shape.

        This is what keeps every existing descriptor snapshot byte-identical:
        ``h_sensor`` appears only when it is actually carried.
        """
        los = LineOfSightGeometry(h_tgt=0.0, theta_o=0.3, theta_s=0.5, delta_phi=0.1)
        payload = los.to_dict()
        assert "h_sensor" not in payload
        assert set(payload) == {"h_tgt", "h_atm_top", "theta_o", "theta_s", "delta_phi"}

        restored = LineOfSightGeometry.from_dict(payload)
        assert restored == los
        assert restored.h_sensor is None

    def test_legacy_payload_without_the_key_loads_as_none(self) -> None:
        """Pre-ADR-0011 dict: the key is absent, not null."""
        legacy = {
            "h_tgt": 0.0,
            "h_atm_top": 1.0e5,
            "theta_o": 0.25,
            "theta_s": 0.5,
            "delta_phi": 0.1,
        }
        restored = LineOfSightGeometry.from_dict(legacy)
        assert restored.h_sensor is None
        # Direction still resolves — from θ_o alone, per the fallback rule.
        assert restored.los_direction == "down"

    def test_explicit_null_and_absent_key_are_the_same_state(self) -> None:
        absent = LineOfSightGeometry.from_dict({"h_tgt": 0.0, "theta_o": 0.25})
        explicit_null = LineOfSightGeometry.from_dict(
            {"h_tgt": 0.0, "theta_o": 0.25, "h_sensor": None}
        )
        assert absent == explicit_null
        assert absent.h_sensor is None
