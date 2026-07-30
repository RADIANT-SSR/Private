"""Direction dispatch, up/level composition, and the capability refusal.

Supersedes ``test_uplooking_guard.py`` (Rule 27 — the Phase-1 blanket refusal
is retired by the capability the refusal was waiting for).  What it asserts:

* **zero drift** — a down-looking path is not rerouted, byte for byte;
* **dispatch** — ``up`` / ``level`` take the segment composition;
* **capability** — an unsupported backend fails *actionably*, naming what is
  supported, rather than silently producing a down-looking column;
* **reciprocity** — the up-looking column τ equals the down-looking τ of the
  same physical path, exactly (ADR-0011 decision 3);
* **the vacuum arms** — LEO→GEO and the Gap-95 exo target still hold.
"""

from __future__ import annotations

import math
import warnings

import numpy as np
import pytest

from radiant.atmosphere._schema import ALL_PARAMETERS as ATMO_PARAMS
from radiant.atmosphere.exo import ExoAtmosphere
from radiant.atmosphere.simple import SimpleAtmosphere
from radiant.atmosphere.stage import AtmosphereStage
from radiant.atmosphere.topology import evaluate_path_topology
from radiant.core.chain import ChainState
from radiant.core.constants import R_EARTH_M
from radiant.core.descriptors import GroundBackground, SkyBackground, T1Thermal
from radiant.core.los_geometry import LineOfSightGeometry
from radiant.core.parameters import ParameterBoundsError, ParameterSet
from radiant.core.spectral import SpectralData
from radiant.core.viewing_triangle import eta_from_theta_o
from radiant.geometry._schema import ALL_PARAMETERS as GEO_PARAMS

H_ATM_TOP_M = 1.0e5
H_GEO_M = 3.5786e7
H_LEO_M = 5.0e5


@pytest.fixture
def wl() -> np.ndarray:
    return np.linspace(3.5, 5.0, 60)


@pytest.fixture
def atm() -> SimpleAtmosphere:
    return SimpleAtmosphere(standard_atmosphere="midlat_summer")


def _params(sensor_alt_m: float, model: str = "simple") -> ParameterSet:
    ps = ParameterSet(list(GEO_PARAMS + ATMO_PARAMS))
    ps.set("geometry.sensor_altitude_m", sensor_alt_m)
    ps.set("atmosphere.model", model)
    ps.resolve()
    return ps


def _state(
    wl: np.ndarray,
    los: LineOfSightGeometry,
    h_tgt_m: float,
    background: object = None,
) -> ChainState:
    epsilon = SpectralData(
        name="target.epsilon",
        wavelength_um=wl,
        values=np.full_like(wl, 0.95),
        unit="",
        source="test",
    )
    target = T1Thermal(
        T_t=300.0,
        epsilon=epsilon,
        scene_type="point_source",
        target_location="airborne",
        h_tgt=h_tgt_m,
    )
    state = ChainState(wavelength_um=wl)
    state = state.with_stage_output("source", "target", target)
    state = state.with_stage_output("source", "background", background)
    return state.with_stage_output("source", "los_geometry", los)


def _quiet(fn, *args, **kwargs):  # type: ignore[no-untyped-def]
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        return fn(*args, **kwargs)


class TestDownLookingIsNotRerouted:
    @pytest.mark.level0
    def test_endo_down_looking_is_the_backend_call_itself(
        self, atm: SimpleAtmosphere, wl: np.ndarray
    ) -> None:
        """Zero drift, stated as an identity: every field is the backend's own."""
        los = LineOfSightGeometry(
            h_tgt=0.0, h_sensor=800_000.0, theta_o=0.4, theta_s=0.6, h_atm_top=H_ATM_TOP_M
        )
        ps = _params(800_000.0)
        via = _quiet(evaluate_path_topology, atm, wl, los, ps)
        direct = _quiet(atm.evaluate, wl, los, ps)
        for field in (
            "tau_sun",
            "tau_up",
            "tau_full_up",
            "E_TOA",
            "E_sky_scattered",
            "E_sky_thermal",
            "L_path_up",
            "L_path_full",
        ):
            np.testing.assert_array_equal(
                getattr(via.quantities, field), getattr(direct, field), err_msg=field
            )
        assert via.sky_radiance_at_aperture is None

    @pytest.mark.level1
    def test_down_looking_stage_still_runs(self, wl: np.ndarray) -> None:
        los = LineOfSightGeometry(h_tgt=0.0, h_sensor=8_000.0, theta_o=0.0, h_atm_top=H_ATM_TOP_M)
        out = _quiet(AtmosphereStage().run, _state(wl, los, 0.0), _params(8_000.0))
        assert "at_aperture" in out.frames


class TestUpLookingComposition:
    @pytest.mark.level1
    def test_ground_to_air_runs_end_to_end(self, wl: np.ndarray) -> None:
        """E2 — the owner's priority-1 class: ground site, 10 km aircraft."""
        los = LineOfSightGeometry(
            h_tgt=10_000.0,
            h_sensor=0.0,
            theta_o=math.radians(150.0),
            theta_s=0.6,
            delta_phi=0.0,
            h_atm_top=H_ATM_TOP_M,
        )
        out = _quiet(
            AtmosphereStage().run,
            _state(wl, los, 10_000.0, background=SkyBackground()),
            _params(0.0),
        )
        assert "at_aperture" in out.frames
        assert "at_aperture_background" in out.frames
        q = out.stage_outputs["atmosphere"]["atm_quantities"]
        assert float(q.tau_up.min()) > 0.0 and float(q.tau_up.max()) < 1.0
        assert float(q.L_path_up.min()) >= 0.0
        bg = out.frames["at_aperture_background"].spectral_radiance
        assert np.all(np.isfinite(bg)) and float(bg.min()) >= 0.0

    @pytest.mark.level0
    def test_transmittance_is_reciprocal(self, atm: SimpleAtmosphere, wl: np.ndarray) -> None:
        """ADR-0011 decision 3 / arch §4.4: one τ per segment.

        The same physical 0 ↔ 10 km line, expressed down-looking and
        up-looking, must give the same transmittance.  Both resolve to the
        same ``AtmosphericGeometry`` air mass over the same column, so the
        agreement is exact in exact arithmetic; the residual is the
        ``asin``/``sin`` round trip used to re-express θ_o at the other
        vertex, which costs at most an ULP (measured: 7.7e-16 relative).
        The exactly-vertical case below has no round trip and IS bit-exact.
        """
        h_low, h_high = 0.0, 10_000.0
        zeta_low = math.radians(35.0)

        down = LineOfSightGeometry(
            h_tgt=h_low, h_sensor=h_high, theta_o=zeta_low, h_atm_top=H_ATM_TOP_M
        )
        q_down = _quiet(evaluate_path_topology, atm, wl, down, _params(h_high)).quantities

        # Same line read from the other vertex: θ_o at the 10 km end is the
        # supplement of the interior angle η at that end.
        eta = eta_from_theta_o(zeta_low, h_high, h_low)
        up = LineOfSightGeometry(
            h_tgt=h_high, h_sensor=h_low, theta_o=math.pi - eta, h_atm_top=H_ATM_TOP_M
        )
        q_up = _quiet(evaluate_path_topology, atm, wl, up, _params(h_low)).quantities

        np.testing.assert_allclose(q_up.tau_up, q_down.tau_up, rtol=1e-14, atol=0.0)

    @pytest.mark.level1
    def test_vertical_up_look_matches_the_vertical_down_look(
        self, atm: SimpleAtmosphere, wl: np.ndarray
    ) -> None:
        """The degenerate check: θ_o = π up vs θ_o = 0 down, same column."""
        down = LineOfSightGeometry(h_tgt=0.0, h_sensor=20_000.0, theta_o=0.0, h_atm_top=H_ATM_TOP_M)
        up = LineOfSightGeometry(
            h_tgt=20_000.0, h_sensor=0.0, theta_o=math.pi, h_atm_top=H_ATM_TOP_M
        )
        q_down = _quiet(evaluate_path_topology, atm, wl, down, _params(20_000.0)).quantities
        q_up = _quiet(evaluate_path_topology, atm, wl, up, _params(0.0)).quantities
        np.testing.assert_array_equal(q_up.tau_up, q_down.tau_up)

    @pytest.mark.level1
    def test_ground_to_space_sst_has_a_sky(self, atm: SimpleAtmosphere) -> None:
        """E3 — exo target seen from inside the column.

        The observer leg is the whole atmosphere and everything beyond the
        target is vacuum, but the sensor is on the ground: it still looks up
        through 100 km of air, so the sky background is emphatically **not**
        zero.  Before CU-254/CU-260 it was exactly zero — the sky was rooted at
        the *target* plane and short-circuited for ``h_tgt ≥ h_atm_top``, so
        every ground-to-space and air-to-space scene ran against a black sky
        with no warning.
        """
        wl_vis = np.linspace(0.4, 1.0, 31)
        los = LineOfSightGeometry(
            h_tgt=8.0e5,
            h_sensor=0.0,
            theta_o=math.pi,
            theta_s=0.6,
            h_atm_top=H_ATM_TOP_M,
        )
        products = _quiet(evaluate_path_topology, atm, wl_vis, los, _params(0.0))
        q = products.quantities
        assert float(q.tau_up.max()) < 1.0  # a real column was traversed
        np.testing.assert_array_equal(q.tau_sun, np.ones_like(wl_vis))  # vacuum solar leg
        np.testing.assert_array_equal(q.E_sky_scattered, np.zeros_like(wl_vis))
        sky = products.sky_radiance_at_aperture
        assert sky is not None
        assert float(sky.min()) > 0.0
        # The sensor-rooted sky is the ground-level vertical column, so it must
        # equal a direct evaluation of exactly that — no target dependence.
        from radiant.atmosphere.sky_radiance import sky_radiance_along_los

        direct = _quiet(
            sky_radiance_along_los, atm, wl_vis, 0.0, 0.0, theta_s_rad=0.6, delta_phi_rad=-math.pi
        )
        np.testing.assert_allclose(sky, direct, rtol=1e-14)

    @pytest.mark.level1
    def test_sky_background_is_the_sky_itself(self, atm: SimpleAtmosphere, wl: np.ndarray) -> None:
        """L_bg,aperture = L_sky — the arm is a pass-through (CU-254)."""
        from radiant.atmosphere.assembly import assemble_background_at_aperture

        los = LineOfSightGeometry(
            h_tgt=10_000.0, h_sensor=0.0, theta_o=math.radians(150.0), h_atm_top=H_ATM_TOP_M
        )
        p = _quiet(evaluate_path_topology, atm, wl, los, _params(0.0))
        bg = assemble_background_at_aperture(
            SkyBackground(), p.quantities, los, sky_radiance_at_aperture=p.sky_radiance_at_aperture
        )
        np.testing.assert_array_equal(bg, p.sky_radiance_at_aperture)  # type: ignore[arg-type]

    @pytest.mark.level1
    def test_sky_background_does_not_depend_on_the_target_altitude(
        self, atm: SimpleAtmosphere, wl: np.ndarray
    ) -> None:
        """CU-254, stated as the invariant it violated.

        Hold the sensor and the *pointing direction at the sensor* fixed and
        slide the target along the ray.  The background behind the target
        cannot depend on where along the ray the target sits, so every
        altitude must give the identical array — including a target above
        ``h_atm_top``, where the whole continuation is vacuum.
        """
        zeta_sensor = math.radians(30.0)
        skies = []
        for h_tgt in (1_000.0, 10_000.0, 20_000.0, 99_000.0, 500_000.0):
            # theta_o is the zenith AT THE TARGET of the target→sensor
            # direction; r·sin ζ is invariant along the ray, so the sensor-side
            # zenith fixes it.
            sin_arg = R_EARTH_M * math.sin(zeta_sensor) / (R_EARTH_M + h_tgt)
            los = LineOfSightGeometry(
                h_tgt=h_tgt,
                h_sensor=0.0,
                theta_o=math.pi - math.asin(sin_arg),
                h_atm_top=H_ATM_TOP_M,
            )
            p = _quiet(evaluate_path_topology, atm, wl, los, _params(0.0))
            assert p.sky_radiance_at_aperture is not None
            skies.append(p.sky_radiance_at_aperture)
        for other in skies[1:]:
            # Not bit-identical: the sensor-side zenith is recovered from θ_o
            # through the viewing triangle, so each altitude carries its own
            # few-ULP round-off in that inversion.  Measured spread over this
            # sweep is 5.7e-16 relative; the tolerance is two orders above the
            # residual and eleven below the 12.3 % defect it guards.
            np.testing.assert_allclose(other, skies[0], rtol=1e-13, atol=0.0)


class TestLevelComposition:
    @pytest.mark.level1
    def test_air_to_air_level_runs(self, wl: np.ndarray) -> None:
        """E5 — 150 km level arm at 10 km (inside the warn shoulder)."""
        phi = 150_000.0 / R_EARTH_M
        los = LineOfSightGeometry(
            h_tgt=10_000.0,
            h_sensor=10_000.0,
            theta_o=math.pi / 2.0 + phi / 2.0,
            h_atm_top=H_ATM_TOP_M,
        )
        out = _quiet(
            AtmosphereStage().run,
            _state(wl, los, 10_000.0, background=SkyBackground()),
            _params(10_000.0),
        )
        q = out.stage_outputs["atmosphere"]["atm_quantities"]
        assert 0.0 < float(q.tau_up.max()) < 1.0
        assert "at_aperture_background" in out.frames

    @pytest.mark.level1
    def test_short_level_arm_uses_the_grazing_sky(self, atm: SimpleAtmosphere) -> None:
        """E1 — two 30 m towers 8 km apart.  The continuation leaves at
        89.96°, past the column ceiling, so the sky must come from the
        spherical slant integral rather than raising."""
        wl_lwir = np.linspace(8.0, 13.0, 51)
        phi = 8_000.0 / R_EARTH_M
        los = LineOfSightGeometry(
            h_tgt=30.0,
            h_sensor=30.0,
            theta_o=math.pi / 2.0 + phi / 2.0,
            h_atm_top=H_ATM_TOP_M,
        )
        p = _quiet(evaluate_path_topology, atm, wl_lwir, los, _params(30.0))
        assert p.sky_radiance_at_aperture is not None
        assert np.all(np.isfinite(p.sky_radiance_at_aperture))
        assert float(p.sky_radiance_at_aperture.min()) > 0.0

    @pytest.mark.level1
    def test_level_arm_transmittance_falls_with_range(self, atm: SimpleAtmosphere) -> None:
        wl_lwir = np.linspace(8.0, 13.0, 51)
        taus = []
        for arc_m in (10_000.0, 50_000.0, 100_000.0):
            phi = arc_m / R_EARTH_M
            los = LineOfSightGeometry(
                h_tgt=3_000.0,
                h_sensor=3_000.0,
                theta_o=math.pi / 2.0 + phi / 2.0,
                h_atm_top=H_ATM_TOP_M,
            )
            q = _quiet(evaluate_path_topology, atm, wl_lwir, los, _params(3_000.0)).quantities
            taus.append(float(np.median(q.tau_up)))
        assert taus[0] > taus[1] > taus[2]


class TestCapabilityRefusal:
    @pytest.mark.level0
    def test_unsupported_backend_fails_actionably(self, wl: np.ndarray) -> None:
        """Rule 15/17: an up-looking request on a backend that cannot serve it
        raises, naming exactly what IS supported — it never silently falls back
        to the down-looking column."""
        los = LineOfSightGeometry(
            h_tgt=10_000.0, h_sensor=0.0, theta_o=math.pi, h_atm_top=H_ATM_TOP_M
        )
        with pytest.raises(ParameterBoundsError) as exc:
            evaluate_path_topology(ExoAtmosphere(), wl, los, _params(0.0))
        message = str(exc.value)
        assert "cannot serve" in message
        assert "atmosphere.model='simple'" in message
        assert "h_atm_top" in message
        # Rule 15: not a backend-internal message from three layers down.
        assert "ZENITH_CEILING" not in message

    @pytest.mark.level1
    def test_unsupported_backend_level_path_also_refused(self, wl: np.ndarray) -> None:
        phi = 100_000.0 / R_EARTH_M
        los = LineOfSightGeometry(
            h_tgt=5_000.0,
            h_sensor=5_000.0,
            theta_o=math.pi / 2.0 + phi / 2.0,
            h_atm_top=H_ATM_TOP_M,
        )
        with pytest.raises(ParameterBoundsError, match="cannot serve"):
            evaluate_path_topology(ExoAtmosphere(), wl, los, _params(5_000.0))

    @pytest.mark.level1
    def test_ground_background_on_an_uplooking_path_is_refused(self, wl: np.ndarray) -> None:
        """There is no ground behind an up-looking target (Rule B)."""
        epsilon_g = SpectralData(
            name="bg.epsilon",
            wavelength_um=wl,
            values=np.full_like(wl, 0.95),
            unit="",
            source="test",
        )
        los = LineOfSightGeometry(
            h_tgt=10_000.0, h_sensor=0.0, theta_o=math.pi, h_atm_top=H_ATM_TOP_M
        )
        with pytest.raises(ParameterBoundsError) as exc:
            AtmosphereStage().run(
                _state(
                    wl,
                    los,
                    10_000.0,
                    background=GroundBackground(epsilon_g=epsilon_g, T_g=290.0),
                ),
                _params(0.0),
            )
        assert "SkyBackground" in str(exc.value)


class TestVacuumArms:
    @pytest.mark.level1
    def test_leo_to_geo_still_runs(self, wl: np.ndarray) -> None:
        """Phase-1 quick win, unchanged by the fold."""
        los = LineOfSightGeometry(
            h_tgt=H_GEO_M, h_sensor=H_LEO_M, theta_o=math.pi, h_atm_top=H_ATM_TOP_M
        )
        out = AtmosphereStage().run(_state(wl, los, H_GEO_M), _params(H_LEO_M))
        np.testing.assert_array_equal(out.stage_outputs["atmosphere"]["tau_atm"], np.ones_like(wl))

    @pytest.mark.level0
    def test_leo_to_geo_bundle_is_exactly_vacuum(
        self, atm: SimpleAtmosphere, wl: np.ndarray
    ) -> None:
        los = LineOfSightGeometry(
            h_tgt=H_GEO_M, h_sensor=H_LEO_M, theta_o=math.pi, h_atm_top=H_ATM_TOP_M
        )
        with warnings.catch_warnings():
            warnings.simplefilter("error", UserWarning)
            q = evaluate_path_topology(atm, wl, los, _params(H_LEO_M)).quantities
        for field in ("tau_sun", "tau_up", "tau_full_up"):
            np.testing.assert_array_equal(getattr(q, field), np.ones_like(wl))
        for field in ("L_path_up", "L_path_full", "E_sky_scattered", "E_sky_thermal"):
            np.testing.assert_array_equal(getattr(q, field), np.zeros_like(wl))
        assert np.any(q.E_TOA > 0.0)

    @pytest.mark.level1
    def test_down_looking_exo_keeps_the_full_column(
        self, atm: SimpleAtmosphere, wl: np.ndarray
    ) -> None:
        los = LineOfSightGeometry(
            h_tgt=150_000.0, h_sensor=800_000.0, theta_o=0.0, h_atm_top=H_ATM_TOP_M
        )
        q = _quiet(evaluate_path_topology, atm, wl, los, _params(800_000.0)).quantities
        np.testing.assert_array_equal(q.tau_up, np.ones_like(wl))
        assert float(q.tau_full_up.min()) < 1.0


class TestPerAltitudeIllumination:
    @pytest.mark.level1
    def test_shadowed_target_gets_zero_solar_transmittance(
        self, atm: SimpleAtmosphere, wl: np.ndarray
    ) -> None:
        """GF-9: sun 10° below the horizontal, target at 2 km — in shadow."""
        theta_s = math.pi / 2.0 + math.radians(10.0)
        los = LineOfSightGeometry(
            h_tgt=2_000.0,
            h_sensor=0.0,
            theta_o=math.pi,
            theta_s=theta_s,
            h_atm_top=H_ATM_TOP_M,
        )
        q = _quiet(evaluate_path_topology, atm, wl, los, _params(0.0)).quantities
        np.testing.assert_array_equal(q.tau_sun, np.zeros_like(wl))
        np.testing.assert_array_equal(q.E_sky_scattered, np.zeros_like(wl))

    @pytest.mark.level1
    def test_sunlit_target_over_dark_ground_gets_the_twilight_transit(
        self, atm: SimpleAtmosphere
    ) -> None:
        """The headline GF-9 case: 5° depression, 60 km target (shadow ≈ 24 km)."""
        wl_vis = np.linspace(0.4, 1.0, 31)
        theta_s = math.pi / 2.0 + math.radians(5.0)
        los = LineOfSightGeometry(
            h_tgt=60_000.0,
            h_sensor=0.0,
            theta_o=math.pi,
            theta_s=theta_s,
            h_atm_top=H_ATM_TOP_M,
        )
        q = _quiet(evaluate_path_topology, atm, wl_vis, los, _params(0.0)).quantities
        assert float(q.tau_sun.min()) > 0.0
        assert float(q.tau_sun.max()) < 1.0

    @pytest.mark.level1
    def test_daylight_solar_leg_is_the_backend_column(
        self, atm: SimpleAtmosphere, wl: np.ndarray
    ) -> None:
        """θ_s ≤ π/2 must not be rerouted through the twilight machinery."""
        import dataclasses

        los = LineOfSightGeometry(
            h_tgt=10_000.0,
            h_sensor=0.0,
            theta_o=math.pi,
            theta_s=0.7,
            h_atm_top=H_ATM_TOP_M,
        )
        q = _quiet(evaluate_path_topology, atm, wl, los, _params(0.0)).quantities
        proxy = dataclasses.replace(los, h_sensor=H_ATM_TOP_M, theta_o=0.0)
        expected = _quiet(atm.evaluate, wl, proxy, _params(0.0))
        np.testing.assert_array_equal(q.tau_sun, expected.tau_sun)
        np.testing.assert_array_equal(q.E_TOA, expected.E_TOA)
        np.testing.assert_array_equal(q.E_sky_thermal, expected.E_sky_thermal)
