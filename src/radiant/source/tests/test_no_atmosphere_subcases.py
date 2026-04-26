"""Stage 7 (Option C) tests for the ``no_atmosphere`` sub-cases.

Covers the three sub-case presets from matrix §3.3 and the failure modes
enumerated in matrix §7:

- ``space`` sub-case (default):
    * smoke-test: ColdSpaceBackground + T1Thermal + LWIR grid drives
      descriptor + assembly end-to-end (representative Table D cell).
    * fails when ``platform.h_sensor`` is left at its default (Rule 17).
    * fails when the LOS geometry intersects the Earth (matrix §7
      "no_atmosphere (space) + LOS intercepts Earth").

- ``ground_test`` sub-case:
    * smoke-test: T1Thermal + UserSpectralBackground drives descriptor +
      assembly (representative Table D-ground G13 LWIR cell).
    * fails when no UserSpectralBackground is supplied (matrix §7
      "no_atmosphere (ground_test / lab_test) without
      UserSpectralBackground").

- ``lab_test`` sub-case:
    * smoke-test: blackbody-standard dark-cal (no illumination) — T1Thermal
      + UserSpectralBackground (representative Table D-lab L13 cell).
    * fails when no UserSpectralBackground is supplied.

All tests bypass the legacy ``_inferrer`` for ground_test / lab_test (it
raises by design — the legacy surface has no user-L_bg path) and drive
``atmosphere.assembly.validate_no_atmosphere_subcase`` +
``assemble_*_at_aperture`` directly.  This validates the pure data-flow
path without requiring the full YAML-driven chain.
"""

from __future__ import annotations

import warnings

import numpy as np
import pytest

from radiant.atmosphere.assembly import (
    assemble_background_at_aperture,
    assemble_target_at_aperture,
    validate_no_atmosphere_subcase,
)
from radiant.atmosphere.exo import ExoAtmosphere
from radiant.core.descriptors import (
    ColdSpaceBackground,
    GroundBackground,
    T1Thermal,
    UserSpectralBackground,
)
from radiant.core.los_geometry import LineOfSightGeometry
from radiant.core.parameters import ParameterBoundsError
from radiant.core.spectral import SpectralData

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _lwir_grid() -> np.ndarray:
    """Representative LWIR grid (Tables D-58, G13, L13)."""
    return np.linspace(8.0, 13.0, 26)


def _vis_grid() -> np.ndarray:
    """Representative VIS grid (Tables G1, L1)."""
    return np.linspace(0.4, 0.7, 16)


def _grey_sd(wl: np.ndarray, value: float, name: str = "eps") -> SpectralData:
    return SpectralData(
        name=name,
        wavelength_um=wl,
        values=np.full_like(wl, value),
        unit="",
        source="test",
    )


def _user_lbg(wl: np.ndarray, L_value: float = 0.5) -> UserSpectralBackground:
    """Construct a UserSpectralBackground with a constant L_bg(λ)."""
    L_bg = SpectralData(
        name="test.user_L_bg",
        wavelength_um=wl,
        values=np.full_like(wl, L_value),
        unit="W/m²/sr/µm",
        source="test",
    )
    return UserSpectralBackground(L_bg=L_bg)


def _minimal_exo_bundle(wl: np.ndarray, los: LineOfSightGeometry):
    """Evaluate ExoAtmosphere and return the AtmosphericQuantities bundle."""
    from radiant.core.parameters import ParameterSet

    return ExoAtmosphere().evaluate(wl, los, ParameterSet([]))


def _seed_required_params(params) -> None:
    """Seed all ``default=None`` schema params so ``params.resolve()`` succeeds.

    The inferrer tests only care about source/atmosphere routing, but the
    full schema has several other required params (optics aperture/focal,
    detector pitch, spectral filter edges, integration time, QE).  The
    exact values are arbitrary — we seed representative LWIR space
    defaults so resolve() completes deterministically.
    """
    # f/# consistency group — supply D and f; f/# is derived.
    params.set("optics.aperture_diameter_m", 0.15)
    params.set("optics.focal_length_m", 0.45)
    # Sensor altitude (atmosphere schema).
    params.set("geometry.sensor_altitude_m", 800_000.0)
    # Filter bandpass + integration time.
    params.set("spectral_integration.filter_min_um", 8.0)
    params.set("spectral_integration.filter_max_um", 13.0)
    params.set("spectral_integration.integration_time_s", 0.010)
    # Detector pitch + QE.
    params.set("detector.pixel_pitch_x_um", 20.0)
    params.set("detector.pixel_pitch_y_um", 20.0)
    params.set("detector.qe_value", 0.55)


# ---------------------------------------------------------------------------
# Sub-case: ``space`` (Table D, representative LWIR extended — Cell 58)
# ---------------------------------------------------------------------------


class TestSpaceSubcaseSmoke:
    """Descriptor + assembly path for the Table D space sub-case."""

    @pytest.mark.level1
    def test_cold_space_background_assembly_is_zero(self) -> None:
        """Matrix §3.3: default ColdSpaceBackground is identically zero in v1."""
        wl = _lwir_grid()
        los = LineOfSightGeometry(h_tgt=0.0, theta_o=0.0)
        atm = _minimal_exo_bundle(wl, los)
        L_bg = assemble_background_at_aperture(ColdSpaceBackground(), atm, los)
        assert L_bg is not None
        assert np.all(L_bg == 0.0)

    @pytest.mark.level1
    def test_space_target_assembly_equals_thermal_self_emission(self) -> None:
        """Matrix §6.2: exo reduces to ε·B(T_t) + 0; Cell 58 LWIR extended."""
        wl = _lwir_grid()
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            target = T1Thermal(
                scene_type="extended",
                target_location="no_atmosphere",
                no_atmosphere_subcase="space",
                h_tgt=0.0,
                epsilon=_grey_sd(wl, 0.98),
                T_t=285.0,
            )
        los = LineOfSightGeometry(h_tgt=0.0, theta_o=0.0)
        atm = _minimal_exo_bundle(wl, los)
        L = assemble_target_at_aperture(target, atm, los)
        assert L.shape == wl.shape
        assert np.all(L > 0.0)
        # Sanity: ε·B(285 K) for LWIR is O(7 W/m²/sr/µm).
        assert np.all(L < 15.0)
        assert np.all(L > 3.0)

    @pytest.mark.level1
    def test_validate_space_leo_nadir_passes(self) -> None:
        """800 km LEO nadir clears the Earth limb — validator returns cleanly."""
        wl = _lwir_grid()
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            target = T1Thermal(
                scene_type="extended",
                target_location="no_atmosphere",
                no_atmosphere_subcase="space",
                h_tgt=0.0,
                epsilon=_grey_sd(wl, 0.98),
                T_t=285.0,
            )
        los = LineOfSightGeometry(h_tgt=0.0, theta_o=0.0)
        # Should NOT raise.
        validate_no_atmosphere_subcase(
            target=target,
            background=ColdSpaceBackground(),
            los=los,
            h_sensor=800_000.0,
            h_sensor_user_set=True,
        )


class TestSpaceSubcaseFailures:
    """Matrix §7 must-raise combinations for the space sub-case."""

    @pytest.mark.level1
    def test_missing_h_sensor_raises(self) -> None:
        """Rule 17: space sub-case without user-set h_sensor is rejected loudly."""
        wl = _lwir_grid()
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            target = T1Thermal(
                scene_type="extended",
                target_location="no_atmosphere",
                no_atmosphere_subcase="space",
                h_tgt=0.0,
                epsilon=_grey_sd(wl, 0.98),
                T_t=285.0,
            )
        los = LineOfSightGeometry(h_tgt=0.0, theta_o=0.0)
        with pytest.raises(ParameterBoundsError, match="platform.h_sensor"):
            validate_no_atmosphere_subcase(
                target=target,
                background=ColdSpaceBackground(),
                los=los,
                h_sensor=0.0,            # default sentinel
                h_sensor_user_set=False, # provenance = DEFAULT
            )

    @pytest.mark.level1
    def test_h_sensor_default_value_user_unset_raises(self) -> None:
        """Even if h_sensor=0.0 (the default), the ``user_set=False`` flag
        triggers the raise — silent default use is Rule-17 forbidden."""
        wl = _lwir_grid()
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            target = T1Thermal(
                scene_type="extended",
                target_location="no_atmosphere",
                no_atmosphere_subcase="space",
                h_tgt=0.0,
                epsilon=_grey_sd(wl, 0.98),
                T_t=285.0,
            )
        los = LineOfSightGeometry(h_tgt=0.0, theta_o=0.0)
        with pytest.raises(ParameterBoundsError):
            validate_no_atmosphere_subcase(
                target=target,
                background=ColdSpaceBackground(),
                los=los,
                h_sensor=0.0,
                h_sensor_user_set=False,
            )

    @pytest.mark.level1
    def test_los_intercepts_earth_raises(self) -> None:
        """Matrix §7: LOS from a low-altitude sensor looking down at a
        high-zenith angle will pass below the Earth surface toward an
        equally low target — must raise."""
        # Construct a geometry where the sensor is at 10 m altitude and
        # wants to see a high-altitude target at a large zenith — the
        # straight line between them dips through the Earth.  In practice
        # we flip the "who is above" by setting h_sensor < h_tgt: if a
        # sensor at 10 m looks at a target at 100 km with a large
        # zenith, the LOS from the sensor crosses the Earth at the limb.
        #
        # Simpler approach: build a geometry with theta_o near π/2 (grazing)
        # so the LOS closest approach to Earth centre drops below R_E.
        wl = _lwir_grid()
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            target = T1Thermal(
                scene_type="extended",
                target_location="no_atmosphere",
                no_atmosphere_subcase="space",
                h_tgt=400_000.0,   # 400 km target
                epsilon=_grey_sd(wl, 0.98),
                T_t=285.0,
            )
        # Sensor directly opposite target (sensor below horizon from
        # target's frame).  With theta_o = 1.55 rad (grazing), the line
        # passes close to the limb and below R_E — intercepts_earth
        # returns True.  NOTE: h_atm_top is bumped above h_tgt so the
        # LineOfSightGeometry constructor accepts this space-target geometry;
        # h_atm_top is irrelevant for intercepts_earth (which uses h_sensor).
        los = LineOfSightGeometry(h_tgt=400_000.0, theta_o=1.55, h_atm_top=500_000.0)
        with pytest.raises(ParameterBoundsError, match="intersects the Earth"):
            validate_no_atmosphere_subcase(
                target=target,
                background=ColdSpaceBackground(),
                los=los,
                h_sensor=100_000.0,   # sensor below target
                h_sensor_user_set=True,
            )

    @pytest.mark.level1
    def test_los_missing_raises(self) -> None:
        """Space sub-case with no LOS cannot run the Earth-intercept check."""
        wl = _lwir_grid()
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            target = T1Thermal(
                scene_type="extended",
                target_location="no_atmosphere",
                no_atmosphere_subcase="space",
                h_tgt=0.0,
                epsilon=_grey_sd(wl, 0.98),
                T_t=285.0,
            )
        with pytest.raises(ParameterBoundsError, match="requires a LineOfSightGeometry"):
            validate_no_atmosphere_subcase(
                target=target,
                background=ColdSpaceBackground(),
                los=None,
                h_sensor=800_000.0,
                h_sensor_user_set=True,
            )


# ---------------------------------------------------------------------------
# Sub-case: ``ground_test`` (Table D-ground G13, LWIR extended)
# ---------------------------------------------------------------------------


class TestGroundTestSubcaseSmoke:
    """Descriptor + assembly path for Table D-ground G13."""

    @pytest.mark.level1
    def test_user_spectral_background_passes_through(self) -> None:
        """UserSpectralBackground passes L_bg through the ExoAtmosphere
        bundle unmodified (atmosphere is A0 — no transport)."""
        wl = _lwir_grid()
        los = LineOfSightGeometry(h_tgt=0.0, theta_o=0.0)
        atm = _minimal_exo_bundle(wl, los)
        L_user = 0.42  # arbitrary W/m²/sr/µm constant
        bg = _user_lbg(wl, L_value=L_user)
        L_bg = assemble_background_at_aperture(bg, atm, los)
        assert L_bg is not None
        # Dimensional audit: user-supplied W/m²/sr/µm passes through unchanged.
        np.testing.assert_allclose(L_bg, L_user, atol=1e-15)

    @pytest.mark.level1
    def test_g13_lwir_ground_test_extended_end_to_end(self) -> None:
        """G13: LWIR extended thermal graybody + UserSpectralBackground."""
        wl = _lwir_grid()
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            target = T1Thermal(
                scene_type="extended",
                target_location="no_atmosphere",
                no_atmosphere_subcase="ground_test",
                h_tgt=0.0,
                epsilon=_grey_sd(wl, 0.96),
                T_t=320.0,   # hot target on test range
            )
        bg = _user_lbg(wl, L_value=1.2)  # user test-range background
        los = LineOfSightGeometry(h_tgt=0.0, theta_o=0.0)
        atm = _minimal_exo_bundle(wl, los)
        # Validator must accept this configuration.
        validate_no_atmosphere_subcase(
            target=target,
            background=bg,
            los=los,
            h_sensor=None,   # not required for ground_test
            h_sensor_user_set=False,
        )
        L_t = assemble_target_at_aperture(target, atm, los)
        L_bg = assemble_background_at_aperture(bg, atm, los)
        assert L_t.shape == wl.shape
        assert np.all(L_t > 0.0)
        assert L_bg is not None
        np.testing.assert_allclose(L_bg, 1.2, atol=1e-15)


class TestGroundTestSubcaseFailures:
    @pytest.mark.level1
    def test_no_user_background_raises(self) -> None:
        """Matrix §7: ground_test without UserSpectralBackground → raise."""
        wl = _lwir_grid()
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            target = T1Thermal(
                scene_type="extended",
                target_location="no_atmosphere",
                no_atmosphere_subcase="ground_test",
                h_tgt=0.0,
                epsilon=_grey_sd(wl, 0.96),
                T_t=320.0,
            )
        los = LineOfSightGeometry(h_tgt=0.0, theta_o=0.0)
        with pytest.raises(ParameterBoundsError, match="UserSpectralBackground"):
            validate_no_atmosphere_subcase(
                target=target,
                background=None,
                los=los,
                h_sensor=None,
                h_sensor_user_set=False,
            )

    @pytest.mark.level1
    def test_cold_space_background_for_ground_test_raises(self) -> None:
        """Matrix §7: wrong background variant for ground_test → raise."""
        wl = _lwir_grid()
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            target = T1Thermal(
                scene_type="extended",
                target_location="no_atmosphere",
                no_atmosphere_subcase="ground_test",
                h_tgt=0.0,
                epsilon=_grey_sd(wl, 0.96),
                T_t=320.0,
            )
        los = LineOfSightGeometry(h_tgt=0.0, theta_o=0.0)
        with pytest.raises(ParameterBoundsError, match="UserSpectralBackground"):
            validate_no_atmosphere_subcase(
                target=target,
                background=ColdSpaceBackground(),
                los=los,
                h_sensor=None,
                h_sensor_user_set=False,
            )

    @pytest.mark.level1
    def test_ground_background_for_ground_test_raises(self) -> None:
        """GroundBackground is for terrestrial/airborne, not ground_test."""
        wl = _lwir_grid()
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            target = T1Thermal(
                scene_type="extended",
                target_location="no_atmosphere",
                no_atmosphere_subcase="ground_test",
                h_tgt=0.0,
                epsilon=_grey_sd(wl, 0.96),
                T_t=320.0,
            )
        gb = GroundBackground(epsilon_g=_grey_sd(wl, 0.95), T_g=295.0)
        los = LineOfSightGeometry(h_tgt=0.0, theta_o=0.0)
        with pytest.raises(ParameterBoundsError, match="UserSpectralBackground"):
            validate_no_atmosphere_subcase(
                target=target,
                background=gb,
                los=los,
                h_sensor=None,
                h_sensor_user_set=False,
            )


# ---------------------------------------------------------------------------
# Sub-case: ``lab_test`` (Table D-lab L13, dark cal blackbody standard)
# ---------------------------------------------------------------------------


class TestLabTestSubcaseSmoke:
    """Descriptor + assembly path for Table D-lab L13 dark cal."""

    @pytest.mark.level1
    def test_l13_lwir_dark_cal_blackbody_standard(self) -> None:
        """L13 dark-cal: blackbody-standard target + chamber UserSpectralBackground,
        no illumination (illumination = None → T1Thermal, ρ=0)."""
        wl = _lwir_grid()
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            target = T1Thermal(
                scene_type="extended",
                target_location="no_atmosphere",
                no_atmosphere_subcase="lab_test",
                h_tgt=0.0,
                epsilon=_grey_sd(wl, 0.999),  # BB standard ε ≈ 1
                T_t=310.0,                    # calibration temperature
            )
        # Dark cal: chamber wall radiance at ambient; user supplies it.
        bg = _user_lbg(wl, L_value=0.3)
        los = LineOfSightGeometry(h_tgt=0.0, theta_o=0.0)  # no solar — dark cal
        atm = _minimal_exo_bundle(wl, los)
        validate_no_atmosphere_subcase(
            target=target,
            background=bg,
            los=los,
            h_sensor=None,
            h_sensor_user_set=False,
        )
        L_t = assemble_target_at_aperture(target, atm, los)
        L_bg = assemble_background_at_aperture(bg, atm, los)
        assert L_t.shape == wl.shape
        assert np.all(L_t > 0.0)
        assert L_bg is not None
        np.testing.assert_allclose(L_bg, 0.3, atol=1e-15)

    @pytest.mark.level1
    def test_lab_test_dark_cal_runs_without_illumination(self) -> None:
        """Illumination = None (θ_s = None) is permitted for lab_test."""
        wl = _lwir_grid()
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            target = T1Thermal(
                scene_type="extended",
                target_location="no_atmosphere",
                no_atmosphere_subcase="lab_test",
                h_tgt=0.0,
                epsilon=_grey_sd(wl, 0.999),
                T_t=310.0,
            )
        los = LineOfSightGeometry(
            h_tgt=0.0,
            theta_o=0.0,
            theta_s=None,        # dark cal: no illumination
            delta_phi=None,
        )
        atm = _minimal_exo_bundle(wl, los)
        L_t = assemble_target_at_aperture(target, atm, los)
        # Matrix §6.2: dark-cal thermal target → pure ε·B(T_t).
        assert np.all(L_t > 0.0)


class TestLabTestSubcaseFailures:
    @pytest.mark.level1
    def test_no_user_background_raises(self) -> None:
        """Matrix §7: lab_test without UserSpectralBackground → raise."""
        wl = _lwir_grid()
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            target = T1Thermal(
                scene_type="extended",
                target_location="no_atmosphere",
                no_atmosphere_subcase="lab_test",
                h_tgt=0.0,
                epsilon=_grey_sd(wl, 0.999),
                T_t=310.0,
            )
        los = LineOfSightGeometry(h_tgt=0.0, theta_o=0.0)
        with pytest.raises(ParameterBoundsError, match="UserSpectralBackground"):
            validate_no_atmosphere_subcase(
                target=target,
                background=None,
                los=los,
                h_sensor=None,
                h_sensor_user_set=False,
            )


# ---------------------------------------------------------------------------
# Round-trip: UserSpectralBackground dimensional invariance
# ---------------------------------------------------------------------------


class TestUserSpectralBackgroundRoundTrip:
    """Dimensional audit: user W/m²/sr/µm passes through unchanged.

    The lab_test / ground_test path does NOT transport L_bg through the
    atmosphere (atmosphere is A0 pass-through).  This test asserts that
    the L_bg values the user supplies are the exact L_bg values published
    at the aperture — no hidden unit conversion, no hidden transport.
    """

    @pytest.mark.level1
    @pytest.mark.parametrize("L_value", [0.0, 0.1, 1.0, 10.0, 1234.5])
    def test_pass_through_is_identity(self, L_value: float) -> None:
        wl = _lwir_grid()
        los = LineOfSightGeometry(h_tgt=0.0, theta_o=0.0)
        atm = _minimal_exo_bundle(wl, los)
        bg = _user_lbg(wl, L_value=L_value)
        L_out = assemble_background_at_aperture(bg, atm, los)
        assert L_out is not None
        np.testing.assert_allclose(L_out, L_value, atol=1e-15)

    @pytest.mark.level1
    def test_spectral_shape_preserved(self) -> None:
        """A non-constant L_bg(λ) must pass through with the same shape."""
        wl = _lwir_grid()
        # Emulate a chamber-wall radiance with a linear ramp.
        values = np.linspace(0.1, 0.5, wl.size)
        L_bg_sd = SpectralData(
            name="test.user_L_bg_shaped",
            wavelength_um=wl,
            values=values,
            unit="W/m²/sr/µm",
            source="test",
        )
        bg = UserSpectralBackground(L_bg=L_bg_sd)
        los = LineOfSightGeometry(h_tgt=0.0, theta_o=0.0)
        atm = _minimal_exo_bundle(wl, los)
        L_out = assemble_background_at_aperture(bg, atm, los)
        assert L_out is not None
        np.testing.assert_allclose(L_out, values, atol=1e-15)


# ---------------------------------------------------------------------------
# LOS Earth-intercept method (unit-level; matrix §7)
# ---------------------------------------------------------------------------


class TestIntercepsEarth:
    """Level-0 sanity tests for ``LineOfSightGeometry.intercepts_earth``."""

    @pytest.mark.level1
    def test_nadir_from_leo_does_not_intercept(self) -> None:
        """800 km LEO looking straight down at h_tgt=0 — no intercept."""
        los = LineOfSightGeometry(h_tgt=0.0, theta_o=0.0)
        assert not los.intercepts_earth(800_000.0)

    @pytest.mark.level1
    def test_nadir_from_ground_does_not_intercept(self) -> None:
        """A sensor at 1 m looking down at h_tgt=0 — degenerate but not an
        intercept (target and sensor both sit at/near the surface; the LOS
        is a radial segment above the centre)."""
        los = LineOfSightGeometry(h_tgt=0.0, theta_o=0.0)
        # Both endpoints at the surface → no dip below.
        assert not los.intercepts_earth(1.0)

    @pytest.mark.level1
    def test_grazing_los_below_limb_intercepts(self) -> None:
        """A pair at low altitude with θ_o close to π/2 — LOS dips below."""
        # h_atm_top bumped to admit the space-target geometry; the
        # Earth-intercept check does not use h_atm_top.
        los = LineOfSightGeometry(h_tgt=400_000.0, theta_o=1.55, h_atm_top=500_000.0)
        # A sensor at 100 km looking at a 400 km target at grazing zenith:
        # the line between them crosses below the Earth limb.
        assert los.intercepts_earth(100_000.0)

    @pytest.mark.level1
    def test_negative_h_sensor_raises(self) -> None:
        los = LineOfSightGeometry(h_tgt=0.0, theta_o=0.0)
        with pytest.raises(ParameterBoundsError, match="h_sensor"):
            los.intercepts_earth(-1.0)

    @pytest.mark.level1
    def test_two_space_objects_nadir_clear(self) -> None:
        """GEO looking at LEO from above — clear LOS."""
        # h_atm_top bumped to admit the space-target geometry; the
        # Earth-intercept check does not use h_atm_top.
        los = LineOfSightGeometry(h_tgt=800_000.0, theta_o=0.0, h_atm_top=1_000_000.0)
        # GEO sensor at ~35 786 km above a LEO target — nadir LOS is purely
        # radial and never dips through Earth.
        assert not los.intercepts_earth(35_786_000.0)


# ---------------------------------------------------------------------------
# Inferrer behaviour for the three sub-cases (legacy surface)
# ---------------------------------------------------------------------------


class TestInferrerSpaceSubcase:
    """The inferrer's ``space`` dispatch returns ColdSpaceBackground."""

    @pytest.mark.level1
    def test_exo_atm_model_routes_to_space_subcase(self) -> None:
        from radiant.api._param_registry import build_parameter_set
        from radiant.source._inferrer import infer_descriptors

        params = build_parameter_set()
        params.set("source.target.temperature", 285.0)
        params.set("source.target.emissivity", 0.98)
        params.set("atmosphere.model", "exo")
        _seed_required_params(params)
        params.resolve()
        wl = _lwir_grid()
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            target, background, los = infer_descriptors(params, wl)
        assert target.target_location == "no_atmosphere"
        assert target.no_atmosphere_subcase == "space"
        assert isinstance(background, ColdSpaceBackground)


class TestInferrerGroundTestSubcase:
    """The inferrer raises for ground_test (legacy surface has no L_bg path)."""

    @pytest.mark.level1
    def test_ground_test_without_user_background_raises(self) -> None:
        from radiant.api._param_registry import build_parameter_set
        from radiant.source._inferrer import infer_descriptors

        params = build_parameter_set()
        params.set("source.target.temperature", 320.0)
        params.set("source.target.emissivity", 0.96)
        params.set("atmosphere.model", "exo")
        params.set("source.target_location", "no_atmosphere")
        params.set("source.no_atmosphere_subcase", "ground_test")
        _seed_required_params(params)
        params.resolve()
        wl = _lwir_grid()
        with pytest.raises(ParameterBoundsError, match="UserSpectralBackground"):
            infer_descriptors(params, wl)


class TestInferrerLabTestSubcase:
    """The inferrer raises for lab_test (legacy surface has no L_bg path)."""

    @pytest.mark.level1
    def test_lab_test_without_user_background_raises(self) -> None:
        from radiant.api._param_registry import build_parameter_set
        from radiant.source._inferrer import infer_descriptors

        params = build_parameter_set()
        params.set("source.target.temperature", 310.0)
        params.set("source.target.emissivity", 0.999)
        params.set("atmosphere.model", "exo")
        params.set("source.target_location", "no_atmosphere")
        params.set("source.no_atmosphere_subcase", "lab_test")
        _seed_required_params(params)
        params.resolve()
        wl = _lwir_grid()
        with pytest.raises(ParameterBoundsError, match="UserSpectralBackground"):
            infer_descriptors(params, wl)


# ---------------------------------------------------------------------------
# Lossy-round-trip subset: lab_test descriptor scenario YAML (Category B)
# ---------------------------------------------------------------------------


class TestLabTestDescriptorRoundTrip:
    """Round-trip: descriptor params derived from a lab_test descriptor match
    the original target params.

    The lab_test path round-trips the target parameters (T_t, ε, A_t) but
    NOT the UserSpectralBackground L_bg (that's a spectrum, not a scalar
    parameter — the lossy boundary is documented in _inferrer).
    """

    @pytest.mark.level1
    def test_t1_lab_test_roundtrip(self) -> None:
        wl = _lwir_grid()
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            target = T1Thermal(
                scene_type="extended",
                target_location="no_atmosphere",
                no_atmosphere_subcase="lab_test",
                h_tgt=0.0,
                epsilon=_grey_sd(wl, 0.999),
                T_t=310.0,
            )
        from radiant.source._inferrer import descriptors_to_params

        d = descriptors_to_params(target, background=_user_lbg(wl, 0.3), los=None)
        assert d["source.target.temperature"] == pytest.approx(310.0, rel=1e-12)
        assert d["source.target.emissivity"] == pytest.approx(0.999, rel=1e-12)
        assert d["source.target_location"] == "no_atmosphere"
        assert d["source.no_atmosphere_subcase"] == "lab_test"
        assert d["source.scene_type"] == "extended"
