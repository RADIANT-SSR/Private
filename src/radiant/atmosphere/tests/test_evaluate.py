"""Backend smoke tests for the Option C ``evaluate()`` protocol method.

These tests confirm that every concrete atmosphere backend produces a
well-formed :class:`AtmosphericQuantities` bundle for a minimal
:class:`LineOfSightGeometry` and that the bundle's contract invariants
(shapes match, τ ∈ [0, 1], energies ≥ 0) hold.

Truth anchors and full physics coverage live in
``tests/integration/test_option_c_anchors.py`` and
``src/radiant/atmosphere/tests/test_assembly.py`` — this file is the
Category B validation layer (Stage 3 plan deliverable): "every backend
answers evaluate() without erroring and returns shape-valid data".
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from radiant.api.session import RadiantSession
from radiant.atmosphere._quantities import AtmosphericQuantities
from radiant.atmosphere.exo import ExoAtmosphere
from radiant.atmosphere.simple import SimpleAtmosphere
from radiant.core.los_geometry import LineOfSightGeometry

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def lwir_wavelengths() -> np.ndarray:
    """Typical LWIR grid for the atmospheric evaluate() smoke tests."""
    return np.linspace(8.0, 13.0, 51)


@pytest.fixture
def vis_wavelengths() -> np.ndarray:
    """Typical VIS/NIR grid for the atmospheric evaluate() smoke tests."""
    return np.linspace(0.4, 1.0, 61)


@pytest.fixture
def terrestrial_los() -> LineOfSightGeometry:
    """Ground-target LOS at nadir, no explicit sun (pure-thermal case).

    ``h_sensor`` matches the 2000 m sensor altitude the ``*_params``
    fixtures pin: since ADR-0011 the sensor endpoint travels on the LOS and
    is the only source the backends read (guardrail G2).
    """
    return LineOfSightGeometry(
        h_tgt=0.0,
        h_sensor=2000.0,
        theta_o=0.0,
        h_atm_top=1.0e5,
        theta_s=None,
        delta_phi=None,
    )


@pytest.fixture
def vis_terrestrial_los() -> LineOfSightGeometry:
    """Ground-target LOS with a 30° sun for a reflective smoke test."""
    return LineOfSightGeometry(
        h_tgt=0.0,
        h_sensor=2000.0,
        theta_o=0.0,
        h_atm_top=1.0e5,
        theta_s=np.deg2rad(30.0),
        delta_phi=0.0,
    )


def _resolved_params(wavelength_um: np.ndarray, sensor_altitude_m: float = 2000.0):
    """Build a minimal resolved ParameterSet suitable for evaluate() tests."""
    session = RadiantSession(wavelength_um=wavelength_um)
    params = session.default_params()

    # Keep enough parameters to resolve without errors on any required field.
    params.set("source.target.temperature", 300.0)
    params.set("source.target.emissivity", 0.95)
    params.set("atmosphere.model", "simple")
    params.set("atmosphere.standard_atmosphere", "midlat_summer")
    params.set("geometry.sensor_altitude_m", sensor_altitude_m)
    params.set("optics.aperture_diameter_m", 0.08)
    params.set("optics.focal_length_m", 0.20)
    params.set("optics.transmission_scalar", 0.60)
    params.set("detector.pixel_pitch_x_um", 17.0)
    params.set("detector.pixel_pitch_y_um", 17.0)
    params.set("detector.qe_value", 0.55)
    params.set("detector.dark_rate_e_per_s", 1000.0)
    params.set(
        "spectral_integration.filter_min_um",
        float(wavelength_um[0]),
    )
    params.set(
        "spectral_integration.filter_max_um",
        float(wavelength_um[-1]),
    )
    params.set("spectral_integration.integration_time_s", 0.015)
    params.set("readout.read_noise_e_rms", 20.0)
    params.set("readout.gain_e_per_dn", 2.0)
    params.set("readout.adc_bits", 14)
    params.resolve()
    return params


@pytest.fixture
def lwir_params(lwir_wavelengths: np.ndarray):
    """A resolved ParameterSet appropriate for LWIR smoke tests."""
    return _resolved_params(lwir_wavelengths, sensor_altitude_m=2000.0)


@pytest.fixture
def vis_params(vis_wavelengths: np.ndarray):
    """A resolved ParameterSet appropriate for VIS smoke tests."""
    return _resolved_params(vis_wavelengths, sensor_altitude_m=2000.0)


# ---------------------------------------------------------------------------
# ExoAtmosphere
# ---------------------------------------------------------------------------


class TestExoAtmosphereEvaluate:
    """Exo backend: vacuum path — ``τ ≡ 1``, ``L_path ≡ 0``, ``E_sky ≡ 0``."""

    @pytest.mark.level1
    def test_returns_atmospheric_quantities(
        self,
        lwir_wavelengths: np.ndarray,
        lwir_params,
        terrestrial_los: LineOfSightGeometry,
    ) -> None:
        atm = ExoAtmosphere().evaluate(lwir_wavelengths, terrestrial_los, lwir_params)
        assert isinstance(atm, AtmosphericQuantities)

    @pytest.mark.level1
    def test_shape_matches_input_grid(
        self,
        lwir_wavelengths: np.ndarray,
        lwir_params,
        terrestrial_los: LineOfSightGeometry,
    ) -> None:
        atm = ExoAtmosphere().evaluate(lwir_wavelengths, terrestrial_los, lwir_params)
        n = lwir_wavelengths.size
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
            assert getattr(atm, field).shape == (n,), f"{field} shape mismatch"

    @pytest.mark.level1
    def test_tau_identically_one(
        self,
        lwir_wavelengths: np.ndarray,
        lwir_params,
        terrestrial_los: LineOfSightGeometry,
    ) -> None:
        atm = ExoAtmosphere().evaluate(lwir_wavelengths, terrestrial_los, lwir_params)
        assert np.all(atm.tau_sun == 1.0)
        assert np.all(atm.tau_up == 1.0)
        assert np.all(atm.tau_full_up == 1.0)

    @pytest.mark.level1
    def test_path_radiances_identically_zero(
        self,
        lwir_wavelengths: np.ndarray,
        lwir_params,
        terrestrial_los: LineOfSightGeometry,
    ) -> None:
        atm = ExoAtmosphere().evaluate(lwir_wavelengths, terrestrial_los, lwir_params)
        assert np.all(atm.L_path_up == 0.0)
        assert np.all(atm.L_path_full == 0.0)

    @pytest.mark.level1
    def test_sky_irradiances_identically_zero(
        self,
        lwir_wavelengths: np.ndarray,
        lwir_params,
        terrestrial_los: LineOfSightGeometry,
    ) -> None:
        atm = ExoAtmosphere().evaluate(lwir_wavelengths, terrestrial_los, lwir_params)
        assert np.all(atm.E_sky_scattered == 0.0)
        assert np.all(atm.E_sky_thermal == 0.0)

    @pytest.mark.level1
    def test_E_TOA_from_core_solar(
        self,
        lwir_wavelengths: np.ndarray,
        lwir_params,
        terrestrial_los: LineOfSightGeometry,
    ) -> None:
        """E_TOA must be non-negative and positive somewhere (sun is on)."""
        atm = ExoAtmosphere().evaluate(lwir_wavelengths, terrestrial_los, lwir_params)
        assert np.all(atm.E_TOA >= 0.0)
        assert np.any(atm.E_TOA > 0.0)


# ---------------------------------------------------------------------------
# SimpleAtmosphere — surface-target v1 scope (h_tgt == 0)
# ---------------------------------------------------------------------------


class TestSimpleAtmosphereEvaluate:
    """SimpleAtmosphere backend — surface (``h_tgt == 0``) and airborne (Stage 5)."""

    @pytest.mark.level1
    def test_airborne_target_above_sensor_raises(
        self,
        lwir_wavelengths: np.ndarray,
        lwir_params,
    ) -> None:
        """Looking-up configuration (h_sensor < h_tgt) must raise.

        Stage 5 (A3) adds partial-column support for ``0 < h_tgt < h_sensor``.
        A target higher than the sensor is a looking-up integration that the
        A3 model does not cover — the backend must surface the configuration
        error rather than silently return τ > 1 from a negative column.

        Pre-Stage-5 this test asserted that any ``h_tgt > 0`` raised
        ``NotImplementedError``; Stage 5 narrows the raise to the
        looking-up edge case.

        Since ADR-0011 the up-looking geometry is legal to *express*, so the
        LOS carries h_sensor = 2000 m below h_tgt = 5000 m with theta_o = π
        (the sensor straight below the target — the hemisphere invariant
        makes any acute theta_o inexpressible for this altitude pair).  The
        backend still refuses it: the direction-aware column is Phase 2
        (Gaps 108/109).  AtmosphereStage refuses the same geometry earlier;
        this is the direct-backend-call path.
        """
        los = LineOfSightGeometry(
            h_tgt=5000.0,  # airborne target above the sensor (h_sensor=2000)
            h_sensor=2000.0,
            theta_o=math.pi,
            h_atm_top=1.0e5,
        )
        atm = SimpleAtmosphere(
            visibility_km=23.0,
            aerosol_type="rural",
            precipitable_water_cm=1.4,
            standard_atmosphere="midlat_summer",
        )
        from radiant.core.parameters import ParameterBoundsError

        with pytest.raises(ParameterBoundsError, match="below h_tgt"):
            atm.evaluate(lwir_wavelengths, los, lwir_params)

    @pytest.mark.level1
    def test_returns_atmospheric_quantities(
        self,
        lwir_wavelengths: np.ndarray,
        lwir_params,
        terrestrial_los: LineOfSightGeometry,
    ) -> None:
        atm = SimpleAtmosphere(
            visibility_km=23.0,
            aerosol_type="rural",
            precipitable_water_cm=1.4,
            standard_atmosphere="midlat_summer",
        )
        q = atm.evaluate(lwir_wavelengths, terrestrial_los, lwir_params)
        assert isinstance(q, AtmosphericQuantities)

    @pytest.mark.level1
    def test_tau_bounded_0_1(
        self,
        lwir_wavelengths: np.ndarray,
        lwir_params,
        terrestrial_los: LineOfSightGeometry,
    ) -> None:
        atm = SimpleAtmosphere(
            visibility_km=23.0,
            aerosol_type="rural",
            precipitable_water_cm=1.4,
            standard_atmosphere="midlat_summer",
        )
        q = atm.evaluate(lwir_wavelengths, terrestrial_los, lwir_params)
        for arr_name in ("tau_sun", "tau_up", "tau_full_up"):
            arr = getattr(q, arr_name)
            assert np.all(arr >= 0.0), f"{arr_name} has negative values"
            assert np.all(arr <= 1.0), f"{arr_name} exceeds 1"

    @pytest.mark.level1
    def test_tau_up_equals_tau_full_up_for_surface_target(
        self,
        lwir_wavelengths: np.ndarray,
        lwir_params,
        terrestrial_los: LineOfSightGeometry,
    ) -> None:
        """For ``h_tgt == 0`` the surface-target column == full ground column."""
        atm = SimpleAtmosphere(
            visibility_km=23.0,
            aerosol_type="rural",
            precipitable_water_cm=1.4,
            standard_atmosphere="midlat_summer",
        )
        q = atm.evaluate(lwir_wavelengths, terrestrial_los, lwir_params)
        np.testing.assert_array_equal(q.tau_up, q.tau_full_up)
        np.testing.assert_array_equal(q.L_path_up, q.L_path_full)

    @pytest.mark.level1
    def test_E_sky_thermal_populated_for_cold_sky(
        self,
        lwir_wavelengths: np.ndarray,
        lwir_params,
        terrestrial_los: LineOfSightGeometry,
    ) -> None:
        """Downwelling sky emission is non-zero at warm ground altitude."""
        atm = SimpleAtmosphere(
            visibility_km=23.0,
            aerosol_type="rural",
            precipitable_water_cm=1.4,
            standard_atmosphere="midlat_summer",
        )
        q = atm.evaluate(lwir_wavelengths, terrestrial_los, lwir_params)
        assert np.all(q.E_sky_thermal >= 0.0)
        assert np.any(q.E_sky_thermal > 0.0)

    @pytest.mark.level1
    def test_E_sky_scattered_non_negative(
        self,
        lwir_wavelengths: np.ndarray,
        lwir_params,
        terrestrial_los: LineOfSightGeometry,
    ) -> None:
        """Stage 6 (Option C) — E_sky_scattered is physical and non-negative.

        Post-Stage-6 the scattered-solar diffuse field is populated via
        ``E_TOA · cos(θ_s) · ω₀ · (1 − τ_down,vert)``.  At LWIR the
        magnitude is small (Wien-tail E_TOA), but it must never go
        negative.  Non-negativity is the only invariant tested here; the
        Category-C truth anchors live in
        :mod:`radiant.atmosphere.tests.test_e_sky_decomposition`.
        """
        atm = SimpleAtmosphere(
            visibility_km=23.0,
            aerosol_type="rural",
            precipitable_water_cm=1.4,
            standard_atmosphere="midlat_summer",
        )
        q = atm.evaluate(lwir_wavelengths, terrestrial_los, lwir_params)
        assert np.all(q.E_sky_scattered >= 0.0)

    @pytest.mark.level1
    def test_vis_sun_on_produces_finite_L_path_up(
        self,
        vis_wavelengths: np.ndarray,
        vis_params,
        vis_terrestrial_los: LineOfSightGeometry,
    ) -> None:
        """With an explicit 30° sun the single-scatter L_path_up is positive."""
        atm = SimpleAtmosphere(
            visibility_km=23.0,
            aerosol_type="rural",
            precipitable_water_cm=1.4,
            standard_atmosphere="midlat_summer",
        )
        q = atm.evaluate(vis_wavelengths, vis_terrestrial_los, vis_params)
        assert np.all(q.L_path_up >= 0.0)
        assert np.any(q.L_path_up > 0.0)

    @pytest.mark.level1
    def test_determinism_same_inputs_same_outputs(
        self,
        lwir_wavelengths: np.ndarray,
        lwir_params,
        terrestrial_los: LineOfSightGeometry,
    ) -> None:
        """Same (λ, los, params) → bit-identical AtmosphericQuantities."""
        atm = SimpleAtmosphere(
            visibility_km=23.0,
            aerosol_type="rural",
            precipitable_water_cm=1.4,
            standard_atmosphere="midlat_summer",
        )
        q1 = atm.evaluate(lwir_wavelengths, terrestrial_los, lwir_params)
        q2 = atm.evaluate(lwir_wavelengths, terrestrial_los, lwir_params)
        for f in (
            "tau_sun",
            "tau_up",
            "tau_full_up",
            "E_TOA",
            "E_sky_scattered",
            "E_sky_thermal",
            "L_path_up",
            "L_path_full",
        ):
            np.testing.assert_array_equal(getattr(q1, f), getattr(q2, f))


# ---------------------------------------------------------------------------
# TabulatedAtmosphere & InterpolatedAtmosphere thin-adapter smoke
# ---------------------------------------------------------------------------


class TestTabulatedAtmosphereEvaluate:
    """Tabulated backend: the thin adapter collapses tau_sun == tau_up."""

    @pytest.mark.level1
    def test_smoke_with_synthetic_npz(
        self,
        tmp_path,
        lwir_wavelengths: np.ndarray,
        lwir_params,
        terrestrial_los: LineOfSightGeometry,
    ) -> None:
        from radiant.atmosphere.tabulated import TabulatedAtmosphere

        # Build a small synthetic file the tabulated backend can load.
        npz_path = tmp_path / "tabulated_smoke.npz"
        tau = 0.8 * np.ones_like(lwir_wavelengths)
        lpath = 0.05 * np.ones_like(lwir_wavelengths)
        ldown = 0.02 * np.ones_like(lwir_wavelengths)
        np.savez(
            npz_path,
            wavelength_um=lwir_wavelengths,
            transmittance=tau,
            path_radiance=lpath,
            atm_emission_down=ldown,
        )
        backend = TabulatedAtmosphere.from_npz(npz_path)

        # The thin adapter emits a UserWarning about the two-leg degradation;
        # swallow it so pytest doesn't flag it, but confirm the contract.
        with pytest.warns(UserWarning, match="two-leg"):
            q = backend.evaluate(lwir_wavelengths, terrestrial_los, lwir_params)
        assert isinstance(q, AtmosphericQuantities)
        # Adapter: tau_sun collapses onto tau_up.
        np.testing.assert_array_equal(q.tau_sun, q.tau_up)
        np.testing.assert_array_equal(q.tau_up, q.tau_full_up)
        np.testing.assert_array_equal(q.L_path_up, q.L_path_full)


# ---------------------------------------------------------------------------
# InterpolatedAtmosphere
# ---------------------------------------------------------------------------


def _spectral(name: str, wl: np.ndarray, values: np.ndarray, unit: str = ""):
    from radiant.core.spectral import SpectralData

    return SpectralData(
        name=name,
        wavelength_um=wl,
        values=values,
        unit=unit,
        source="test fixture",
    )


def _interp_with_target_axis(wl: np.ndarray):
    """Two-node grid over target_altitude_m: t=0 (τ=0.7) and t=10 km (τ=0.9)."""
    from radiant.atmosphere.interpolated import GeometryPoint, InterpolatedAtmosphere

    points = [
        GeometryPoint(
            coordinates={"target_altitude_m": 0.0},
            transmittance=_spectral("tau0", wl, 0.7 * np.ones_like(wl)),
            path_radiance=_spectral("lp0", wl, 0.05 * np.ones_like(wl), "W/m²/sr/µm"),
            atm_emission_down=_spectral("ld0", wl, 0.02 * np.ones_like(wl), "W/m²/sr/µm"),
        ),
        GeometryPoint(
            coordinates={"target_altitude_m": 10_000.0},
            transmittance=_spectral("tau1", wl, 0.9 * np.ones_like(wl)),
            path_radiance=_spectral("lp1", wl, 0.02 * np.ones_like(wl), "W/m²/sr/µm"),
            atm_emission_down=_spectral("ld1", wl, 0.01 * np.ones_like(wl), "W/m²/sr/µm"),
        ),
    ]
    return InterpolatedAtmosphere(points, axes=["target_altitude_m"])


class TestInterpolatedAtmosphereEvaluate:
    """Gap 94: the adapter serves h_tgt > 0 from a target_altitude_m axis."""

    @pytest.mark.level0
    def test_two_leg_split_for_airborne_target(
        self, lwir_wavelengths: np.ndarray, lwir_params
    ) -> None:
        """Level 0 anchor: log-τ interpolation at the grid midpoint.

        τ_up(h=5 km) = exp((ln 0.7 + ln 0.9)/2) = √0.63 ≈ 0.793725; the
        full column stays the t=0 node (τ=0.7).  L_path and L_atm_down
        interpolate linearly: L_path_up = 0.035, L_atm_down = 0.015
        [W/m²/sr/µm], E_sky_thermal = π·0.015 [W/m²/µm].
        """
        model = _interp_with_target_axis(lwir_wavelengths)
        los = LineOfSightGeometry(h_tgt=5_000.0, h_sensor=20_000.0, theta_o=0.0, h_atm_top=1.0e5)

        with pytest.warns(UserWarning, match="two-leg"):
            q = model.evaluate(lwir_wavelengths, los, lwir_params)

        assert isinstance(q, AtmosphericQuantities)
        expected_tau_up = float(np.sqrt(0.63))
        np.testing.assert_allclose(q.tau_up, expected_tau_up, rtol=1e-9)
        np.testing.assert_allclose(q.tau_full_up, 0.7, rtol=1e-9)
        np.testing.assert_allclose(q.L_path_up, 0.035, rtol=1e-9)
        np.testing.assert_allclose(q.L_path_full, 0.05, rtol=1e-9)
        # Sun leg still collapses onto the up leg (no sun-leg data set).
        np.testing.assert_array_equal(q.tau_sun, q.tau_up)
        # Downwelling comes from the up-leg (target-local) query.
        np.testing.assert_allclose(q.E_sky_thermal, np.pi * 0.015, rtol=1e-9)

    @pytest.mark.level1
    def test_surface_target_single_column_unchanged(
        self, lwir_wavelengths: np.ndarray, lwir_params
    ) -> None:
        """h_tgt = 0 keeps the pre-Gap-94 contract: one column, all legs alias."""
        model = _interp_with_target_axis(lwir_wavelengths)
        los = LineOfSightGeometry(h_tgt=0.0, h_sensor=2000.0, theta_o=0.0, h_atm_top=1.0e5)
        with pytest.warns(UserWarning, match="two-leg"):
            q = model.evaluate(lwir_wavelengths, los, lwir_params)
        np.testing.assert_allclose(q.tau_up, 0.7, rtol=1e-9)
        np.testing.assert_array_equal(q.tau_up, q.tau_full_up)
        np.testing.assert_array_equal(q.L_path_up, q.L_path_full)

    @pytest.mark.level1
    def test_airborne_without_target_axis_raises(
        self, lwir_wavelengths: np.ndarray, lwir_params
    ) -> None:
        """A grid without a target-altitude axis cannot supply both legs."""
        from radiant.atmosphere.interpolated import GeometryPoint, InterpolatedAtmosphere

        points = [
            GeometryPoint(
                coordinates={"path_zenith_rad": z},
                transmittance=_spectral(
                    "tau", lwir_wavelengths, t * np.ones_like(lwir_wavelengths)
                ),
                path_radiance=_spectral(
                    "lp", lwir_wavelengths, 0.05 * np.ones_like(lwir_wavelengths), "W/m²/sr/µm"
                ),
                atm_emission_down=_spectral(
                    "ld", lwir_wavelengths, 0.02 * np.ones_like(lwir_wavelengths), "W/m²/sr/µm"
                ),
            )
            for z, t in ((0.0, 0.8), (0.5, 0.7))
        ]
        model = InterpolatedAtmosphere(points, axes=["path_zenith_rad"])
        los = LineOfSightGeometry(h_tgt=5_000.0, h_sensor=20_000.0, theta_o=0.0, h_atm_top=1.0e5)
        with pytest.raises(NotImplementedError, match="target_altitude_m"):
            model.evaluate(lwir_wavelengths, los, lwir_params)

    @pytest.mark.level1
    def test_airborne_above_hull_refused(self, lwir_wavelengths: np.ndarray, lwir_params) -> None:
        """No extrapolation: h_tgt above the grid's target range fails loud."""
        from radiant.atmosphere.errors import AtmosphereValidationError

        model = _interp_with_target_axis(lwir_wavelengths)
        los = LineOfSightGeometry(h_tgt=90_000.0, h_sensor=95_000.0, theta_o=0.0, h_atm_top=1.0e5)
        with pytest.raises(AtmosphereValidationError, match="outside the available range"):
            model.evaluate(lwir_wavelengths, los, lwir_params)


# ---------------------------------------------------------------------------
# Stage-4 guard: ensure the deleted shadow-mode helper does not return.
# ---------------------------------------------------------------------------


@pytest.mark.level1
def test_shadow_mode_symbol_is_gone() -> None:
    """Stage 4 removed ``_shadow_mode_enabled`` from ``atmosphere.stage``.

    If someone reintroduces the helper they must also reintroduce the
    legacy dual-path code it gated — which is explicitly forbidden by the
    Option C plan.  This test fails early if the symbol comes back.
    """
    import radiant.atmosphere.stage as stage_module

    assert not hasattr(stage_module, "_shadow_mode_enabled")
