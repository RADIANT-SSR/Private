"""PlatformStage consumption of the published relative LOS rate (Gap 111).

Two things are under test and they pull in opposite directions:

* **The new arm.** When GeometryStage resolved the LOS rate through a
  kinematics door (K1 direct rate / K2 target velocity), that *one* rate —
  which already carries both endpoints' motion — becomes the *one* smear
  extent, feeding both Rule-4 paths (the rect PSF kernel and ``mtf_smear_y``).
* **Zero drift.** When no kinematics door was used, the stage must run the
  pre-Gap-111 velocity/range door and return the bit-identical number, guards
  and warnings included. The differential grid at the bottom of this module is
  the proof (exact ``==`` over 576 configurations).

GeometryStage is not imported here (Rule 11 / import-linter): its published
contract is a plain dict, so it is spelled out literally. The string coupling
between the two stages (``los_rate_mode``) is pinned end-to-end against the
real GeometryStage in ``tests/integration/test_moving_target_smear.py``.
"""

from __future__ import annotations

import itertools
import warnings

import numpy as np
import pytest

from radiant.core.chain import ChainState
from radiant.core.parameters import ParameterSet
from radiant.core.viewing_triangle import slant_range_from_theta_o_m
from radiant.optics.psf.builder import build_effective_psf
from radiant.optics.psf.effective import EffectivePSF
from radiant.platform.errors import PlatformValidationError
from radiant.platform.smear import smear_mtf_1d, smear_width_m
from radiant.platform.stage import PlatformStage

FOCAL_LENGTH_M = 5.0
T_INT_S = 1.0e-3

# GeometryStage's platform-only mode strings (radiant.geometry.modes.resolve_los_rate).
MODE_PLATFORM_ONLY = "platform-only (derived)"
MODE_NO_PATH = "platform-only (no path — coincident endpoints)"
MODE_K1 = "geometry.los_angular_rate_rad_s"
MODE_K2 = "target velocity (K2)"
MODE_BOTH = "geometry.los_angular_rate_rad_s + target velocity (K2) (consistent)"


def _make_params(
    overrides: dict[str, object] | None = None, *, with_t_int: bool = True
) -> ParameterSet:
    """Platform + optics + geometry + timing parameters, as the stage reads them.

    ``with_t_int=False`` omits ``spectral_integration.integration_time_s`` from
    the schema entirely — the CU-085 "partial fixture" shape, and the only way
    to reach the missing-integration-time guard (the schema's lower bound is
    1e-9 s, so a zero cannot be *set*).
    """
    from radiant.geometry._schema import (
        PATH_ZENITH_RAD,
        SENSOR_ALTITUDE_M,
        TARGET_ALTITUDE_M,
    )
    from radiant.optics._schema import ALL_PARAMETERS as OPT_PARAMS
    from radiant.platform._schema import ALL_PARAMETERS as PLAT_PARAMS
    from radiant.spectral_integration._schema import INTEGRATION_TIME_S

    schema = list(PLAT_PARAMS + OPT_PARAMS) + [
        SENSOR_ALTITUDE_M,
        TARGET_ALTITUDE_M,
        PATH_ZENITH_RAD,
    ]
    if with_t_int:
        schema.append(INTEGRATION_TIME_S)
    ps = ParameterSet(schema, [])
    defaults: dict[str, object] = {
        "platform.jitter_rms_urad": 0.0,
        "platform.jitter_axes": "isotropic",
        "platform.jitter_rms_x_urad": 0.0,
        "platform.jitter_rms_y_urad": 0.0,
        "optics.aperture_diameter_m": 0.5,
        "optics.focal_length_m": FOCAL_LENGTH_M,
        "optics.f_number": 10.0,
        "geometry.sensor_altitude_m": 600_000.0,
        "geometry.target_altitude_m": 0.0,
    }
    if with_t_int:
        defaults["spectral_integration.integration_time_s"] = T_INT_S
    defaults.update(overrides or {})
    for key, value in defaults.items():
        ps.set(key, value)
    ps.resolve()
    return ps


def _geometry_out(
    *,
    slant_range_m: float | None = 600_000.0,
    los_angular_rate_rad_s: float | None = 0.0,
    los_rate_mode: str = MODE_PLATFORM_ONLY,
) -> dict[str, object]:
    """The subset of ``stage_outputs['geometry']`` PlatformStage reads."""
    return {
        "slant_range_m": slant_range_m,
        "los_angular_rate_rad_s": los_angular_rate_rad_s,
        "los_rate_mode": los_rate_mode,
    }


def _epsf() -> EffectivePSF:
    from radiant.optics.psf_mono import compute_psf
    from radiant.optics.sampling import compute_sampling

    config = compute_sampling(
        wavelength_m=0.575e-6,
        focal_length_m=FOCAL_LENGTH_M,
        aperture_diameter_m=0.5,
        pixel_pitch_m=8e-6,
        pupil_npix=128,
        psf_oversample=8,
    )
    return build_effective_psf(
        compute_psf(config, obscuration_ratio=0.0),
        kernels=[],
        sample_spacing_m=config.focal_spacing_m,
        pixel_pitch_m=8e-6,
        wavelength_um=0.575,
    )


def _state(geometry: dict[str, object] | None, *, with_freq: bool = False) -> ChainState:
    wl = np.array([0.45, 0.575, 0.70])
    freq = np.linspace(0.0, 60.0, 64) if with_freq else None
    state = ChainState(wavelength_um=wl, spatial_freq_cycles_per_mrad=freq)
    state = state.with_stage_output("optics", "effective_psf", _epsf())
    if geometry is not None:
        for key, value in geometry.items():
            state = state.with_stage_output("geometry", key, value)
    return state


def _run(params: ParameterSet, geometry: dict[str, object] | None, **kw: bool) -> ChainState:
    return PlatformStage().run(_state(geometry, **kw), params)


# ---------------------------------------------------------------------------
# The new arm — the published relative rate becomes the smear
# ---------------------------------------------------------------------------


class TestPublishedRateConsumed:
    """A kinematics-resolved rate drives the smear, whatever the platform does."""

    @pytest.mark.level1
    @pytest.mark.parametrize("mode", [MODE_K1, MODE_K2, MODE_BOTH])
    def test_rate_times_focal_times_t_int(self, mode: str) -> None:
        """s = ω · f · t_int — the charter's crossing-target anchor.

        ω = 200 m/s / 20 km = 0.01 rad/s.  The charter's t_int = 10 ms is
        exercised on the pure function (``test_relative_motion_smear.py``) and
        end-to-end (``tests/integration/test_moving_target_smear.py``); here
        t_int = 1 ms keeps the rect kernel inside this fixture's PSF grid, so
        the same product is checked without the grid-clamp path.
        """
        params = _make_params()
        result = _run(
            params,
            _geometry_out(slant_range_m=20_000.0, los_angular_rate_rad_s=0.01, los_rate_mode=mode),
        )
        smear = result.stage_outputs["platform"]["smear_width_m"]
        assert smear == 0.01 * FOCAL_LENGTH_M * T_INT_S
        assert smear == pytest.approx(1.0e-5 * FOCAL_LENGTH_M, rel=1e-13)

    @pytest.mark.level1
    def test_moving_target_smears_a_static_platform(self) -> None:
        """The pre-Gap-111 stage returned 0 here (no platform velocity)."""
        params = _make_params({"platform.ground_velocity_m_s": 0.0})
        result = _run(
            params,
            _geometry_out(
                slant_range_m=20_000.0, los_angular_rate_rad_s=0.01, los_rate_mode=MODE_K2
            ),
        )
        assert result.stage_outputs["platform"]["smear_width_m"] > 0.0

    @pytest.mark.level1
    def test_platform_velocity_is_not_added_again(self) -> None:
        """v_rel is composed upstream: the published rate IS the whole smear.

        Same published rate, wildly different ``platform.ground_velocity_m_s``
        ⇒ identical smear. An RSS (or any second platform term) would make
        these three differ.
        """
        widths = set()
        for v_g in (0.0, 7000.0, 20_000.0):
            params = _make_params({"platform.ground_velocity_m_s": v_g})
            result = _run(
                params,
                _geometry_out(
                    slant_range_m=20_000.0,
                    los_angular_rate_rad_s=0.01,
                    los_rate_mode=MODE_K2,
                ),
            )
            widths.add(result.stage_outputs["platform"]["smear_width_m"])
        assert len(widths) == 1

    @pytest.mark.level1
    def test_zero_rate_gives_exactly_zero_smear(self) -> None:
        """A receding target (ω = 0 after the radial projection) adds nothing."""
        params = _make_params({"platform.ground_velocity_m_s": 0.0})
        result = _run(
            params,
            _geometry_out(
                slant_range_m=20_000.0, los_angular_rate_rad_s=0.0, los_rate_mode=MODE_K1
            ),
        )
        assert result.stage_outputs["platform"]["smear_width_m"] == 0.0


class TestBothRule4Paths:
    """Rule 4: the same generalized rate reaches the PSF kernel and the MTF."""

    @pytest.mark.level1
    def test_psf_kernel_and_mtf_share_the_rate(self) -> None:
        params = _make_params()
        result = _run(
            params,
            _geometry_out(
                slant_range_m=20_000.0, los_angular_rate_rad_s=0.01, los_rate_mode=MODE_K2
            ),
            with_freq=True,
        )
        smear = result.stage_outputs["platform"]["smear_width_m"]
        epsf = result.stage_outputs["platform"]["effective_psf"]

        # PSF path: the rect kernel was convolved in.
        assert any("smear" in entry for entry in epsf.convolution_history)
        # MTF path: the analytic sinc for the SAME width.
        freq_m = np.linspace(0.0, 60.0, 64) / (FOCAL_LENGTH_M * 1e-3)
        assert np.array_equal(result.mtf_terms["mtf_smear_y"], smear_mtf_1d(freq_m, smear))
        assert np.array_equal(result.mtf_terms["mtf_smear_x"], np.ones_like(freq_m))

    @pytest.mark.level1
    def test_moving_target_degrades_the_along_smear_axis(self) -> None:
        """Physics direction check: more relative motion ⇒ lower MTF, wider PSF."""
        params = _make_params()
        still = _run(
            params,
            _geometry_out(los_angular_rate_rad_s=0.0, los_rate_mode=MODE_K2),
            with_freq=True,
        )
        moving = _run(
            params,
            _geometry_out(
                slant_range_m=20_000.0, los_angular_rate_rad_s=0.002, los_rate_mode=MODE_K2
            ),
            with_freq=True,
        )
        assert moving.mtf_terms["mtf_smear_y"][-1] < still.mtf_terms["mtf_smear_y"][-1]
        assert moving.stage_outputs["platform"]["effective_psf"].fwhm("y") > still.stage_outputs[
            "platform"
        ]["effective_psf"].fwhm("y")


# ---------------------------------------------------------------------------
# Guards (Rules 15/17) — nothing is dropped silently
# ---------------------------------------------------------------------------


class TestGuards:
    @pytest.mark.level1
    def test_direct_override_wins_but_warns(self) -> None:
        params = _make_params({"platform.smear_length_um": 10.0})
        with pytest.warns(UserWarning, match="overrides the relative line-of-sight rate"):
            result = _run(
                params,
                _geometry_out(los_angular_rate_rad_s=0.01, los_rate_mode=MODE_K2),
            )
        assert result.stage_outputs["platform"]["smear_width_m"] == pytest.approx(10e-6, rel=1e-12)

    @pytest.mark.level1
    def test_missing_integration_time_warns_and_returns_zero(self) -> None:
        params = _make_params(with_t_int=False)
        with pytest.warns(UserWarning, match="integration_time_s is missing or"):
            result = _run(
                params,
                _geometry_out(los_angular_rate_rad_s=0.01, los_rate_mode=MODE_K2),
            )
        assert result.stage_outputs["platform"]["smear_width_m"] == 0.0

    @pytest.mark.level1
    def test_kinematics_mode_without_a_rate_raises(self) -> None:
        """Unreachable through GeometryStage — named, never silently zeroed."""
        params = _make_params()
        with pytest.raises(PlatformValidationError, match="published no rate"):
            _run(
                params,
                _geometry_out(
                    slant_range_m=None, los_angular_rate_rad_s=None, los_rate_mode=MODE_K2
                ),
            )

    @pytest.mark.level1
    def test_negative_published_rate_raises(self) -> None:
        params = _make_params()
        with pytest.raises(PlatformValidationError, match="non-negative"):
            _run(
                params,
                _geometry_out(los_angular_rate_rad_s=-0.01, los_rate_mode=MODE_K1),
            )


# ---------------------------------------------------------------------------
# Zero drift — the platform-only path is untouched
# ---------------------------------------------------------------------------


class TestPlatformOnlyPathUnchanged:
    @pytest.mark.level1
    @pytest.mark.parametrize("mode", [MODE_PLATFORM_ONLY, MODE_NO_PATH])
    def test_platform_only_mode_ignores_the_published_rate(self, mode: str) -> None:
        """The gate is the mode, not the presence of a number.

        A deliberately wrong published rate (10× the platform-only value)
        must not reach the smear when no kinematics door was used.
        """
        params = _make_params(
            {
                "platform.ground_velocity_m_s": 7000.0,
                "geometry.sensor_altitude_m": 600_000.0,
            }
        )
        result = _run(
            params,
            _geometry_out(
                slant_range_m=600_000.0,
                los_angular_rate_rad_s=10.0 * 7000.0 / 600_000.0,
                los_rate_mode=mode,
            ),
        )
        expected = smear_width_m(7000.0, T_INT_S, FOCAL_LENGTH_M, 600_000.0)
        assert result.stage_outputs["platform"]["smear_width_m"] == expected

    @pytest.mark.level1
    def test_no_geometry_outputs_at_all_uses_the_legacy_door(self) -> None:
        """CU-096 partial fixtures: no geometry stage ran, nothing changes."""
        params = _make_params(
            {
                "platform.ground_velocity_m_s": 7000.0,
                "geometry.sensor_altitude_m": 600_000.0,
            }
        )
        result = _run(params, None)
        expected = smear_width_m(7000.0, T_INT_S, FOCAL_LENGTH_M, 600_000.0)
        assert result.stage_outputs["platform"]["smear_width_m"] == expected

    @pytest.mark.level1
    def test_cu085_altitude_warning_still_fires(self) -> None:
        params = _make_params(
            {
                "platform.ground_velocity_m_s": 7000.0,
                "geometry.sensor_altitude_m": 0.0,
            }
        )
        with pytest.warns(UserWarning, match="sensor_altitude_m is missing"):
            result = _run(params, _geometry_out(slant_range_m=None, los_rate_mode=MODE_NO_PATH))
        assert result.stage_outputs["platform"]["smear_width_m"] == 0.0


class TestDifferentialZeroDrift:
    """Exact-equality grid: 576 pre-Gap-111 configurations, bit for bit.

    The pre-change definition of the smear width is still in the tree
    (``smear.py::smear_width_m`` over the published slant range, or the
    θ_o-derived range for a partial fixture), so the differential is run
    against it directly rather than against a stored baseline.
    """

    ALTITUDES_M = (7_000.0, 20_000.0, 400_000.0, 600_000.0)
    THETA_O_RAD = (0.0, 0.15, 0.4, 0.7)
    VELOCITIES_M_S = (0.0, 1.0, 230.0, 7000.0)
    T_INTS_S = (1e-5, 1e-3, 0.1)
    MODES = (None, MODE_PLATFORM_ONLY, MODE_NO_PATH)

    @pytest.mark.level1
    def test_grid_is_bit_identical(self) -> None:
        compared = 0
        for alt, theta_o, v_g, t_int, mode in itertools.product(
            self.ALTITUDES_M,
            self.THETA_O_RAD,
            self.VELOCITIES_M_S,
            self.T_INTS_S,
            self.MODES,
        ):
            params = _make_params(
                {
                    "platform.ground_velocity_m_s": v_g,
                    "geometry.sensor_altitude_m": alt,
                    "geometry.path_zenith_rad": theta_o,
                    "spectral_integration.integration_time_s": t_int,
                }
            )
            slant = slant_range_from_theta_o_m(theta_o, alt, 0.0)
            geometry = (
                None
                if mode is None
                else _geometry_out(
                    slant_range_m=slant,
                    # Deliberately not the platform-only value: if the gate
                    # leaked, the mismatch would be unmissable.
                    los_angular_rate_rad_s=3.0 * v_g / slant,
                    los_rate_mode=mode,
                )
            )
            # A fixture with NO published geometry gets the nadir proxy
            # ``slant = altitude`` since the CU-096 fallback retirement
            # (Geometry-Flexibility Phase 5 / G4): the θ_o-triangle derivation
            # is gone, so off-nadir smear geometry requires GeometryStage.
            effective_slant = alt if mode is None else slant
            expected = (
                0.0 if v_g <= 0.0 else smear_width_m(v_g, t_int, FOCAL_LENGTH_M, effective_slant)
            )
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", UserWarning)
                actual = PlatformStage._compute_smear_width(
                    params,
                    FOCAL_LENGTH_M,
                    published_slant_m=None if geometry is None else slant,
                    published_los_rate_rad_s=(None if geometry is None else 3.0 * v_g / slant),
                    los_rate_mode=None if geometry is None else mode,
                )
            assert actual == expected, (
                f"smear drifted: alt={alt} m theta_o={theta_o} rad v={v_g} m/s "
                f"t_int={t_int} s mode={mode!r}: {actual} != {expected}"
            )
            compared += 1
        assert compared == 576  # 4 × 4 × 4 × 3 × 3
