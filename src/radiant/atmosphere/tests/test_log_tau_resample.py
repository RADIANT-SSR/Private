"""CU-316 — every backend carries τ onto the chain grid in log-τ.

CU-306 moved the ``InterpolatedAtmosphere`` wavelength resample into
ln(τ) space (Beer-Lambert: optical depth, not τ, is what varies smoothly).
``TabulatedAtmosphere`` and ``ModtranAtmosphere`` still resampled linearly
in τ, so the *same stored column* returned different numbers depending on
which backend served it — a pure convention divergence at the ~1.5 %
level, exactly the magnitude of the physics differences a fast-path vs
tabulated-truth comparison exists to expose.  This module pins the
convention on all three.

Truth anchor used throughout: for ``τ(λ) = exp(−a·λ)`` the optical depth
``a·λ`` is *exactly* linear in λ, so a log-linear resample is exact on
every grid and the closed form ``exp(−a·λ)`` holds at every query
wavelength.  A linear-in-τ resample instead returns the arithmetic mean of
the bracketing samples where the physics gives the geometric mean, and
misses by ~1 % at the midpoints of a coarse stored cell.
"""

from __future__ import annotations

import warnings

import numpy as np
import pytest

from radiant.atmosphere.interpolated import GeometryPoint, InterpolatedAtmosphere
from radiant.atmosphere.log_tau_resample import TAU_FLOOR, resample_transmittance
from radiant.atmosphere.modtran import ModtranAtmosphere, ModtranConfig, Tape7Import
from radiant.atmosphere.protocol import AtmosphericGeometry
from radiant.atmosphere.tabulated import TabulatedAtmosphere
from radiant.core.los_geometry import LineOfSightGeometry
from radiant.core.spectral import SpectralData, SpectralGrid

# Optical-depth slope of the analytic anchor column [1/µm].
A_OD: float = 1.0

# Deliberately COARSE stored grid (0.2 µm cells): a linear-in-τ resample of
# the curved exponential then carries a percent-level error, which is the
# defect this module pins.
STORED_WL: np.ndarray = np.linspace(3.0, 5.0, 11)

# Every stored cell's midpoint — the worst case for linear-vs-log.
MID_WL: np.ndarray = 0.5 * (STORED_WL[:-1] + STORED_WL[1:])


def _tau(wl: np.ndarray) -> np.ndarray:
    return np.exp(-A_OD * wl)


def _geometry() -> AtmosphericGeometry:
    return AtmosphericGeometry(
        sensor_altitude_m=100_000.0,
        target_altitude_m=0.0,
        path_zenith_rad=0.0,
        solar_zenith_rad=0.0,
        solar_azimuth_rad=0.0,
    )


def _spectral(name: str, wl: np.ndarray, values: np.ndarray, unit: str = "") -> SpectralData:
    return SpectralData(
        name=name,
        wavelength_um=wl,
        values=values,
        unit=unit,
        source="CU-316 analytic anchor",
    )


def _tabulated(
    wl: np.ndarray,
    tau: np.ndarray,
    lpath: np.ndarray | None = None,
    ldown: np.ndarray | None = None,
) -> TabulatedAtmosphere:
    zeros = np.zeros_like(wl)
    return TabulatedAtmosphere(
        transmittance_data=_spectral("tau", wl, tau),
        path_radiance_data=_spectral("lp", wl, zeros if lpath is None else lpath, "W/m²/sr/µm"),
        atm_emission_down_data=_spectral("ld", wl, zeros if ldown is None else ldown, "W/m²/sr/µm"),
        name="cu316",
        source_path="synthetic",
    )


def _tape7(wl: np.ndarray, tau: np.ndarray, lpath: float = 0.1) -> Tape7Import:
    return Tape7Import(
        wavelength_um=wl,
        transmittance=tau,
        path_radiance=np.full_like(wl, lpath),
        ground_reflected=np.zeros_like(wl),
        source_path="synthetic-tape7",
        content_key="cu316cu316cu316a",
    )


def _modtran(
    wl: np.ndarray,
    tau: np.ndarray,
    sun_tau: np.ndarray | None = None,
    up_tau: np.ndarray | None = None,
) -> ModtranAtmosphere:
    cfg = ModtranConfig(binary_path="nonexistent-modtran-binary", allow_fallback=False)
    return ModtranAtmosphere(
        cfg,
        tape7_import=_tape7(wl, tau),
        tape7_sun_import=None if sun_tau is None else _tape7(wl, sun_tau),
        tape7_up_import=None if up_tau is None else _tape7(wl, up_tau),
    )


def _modtran_params(wl: np.ndarray):  # type: ignore[no-untyped-def]
    """Minimal resolved ParameterSet for a MODTRAN evaluate() call."""
    from radiant.api.session import RadiantSession

    session = RadiantSession(wavelength_um=wl)
    params = session.default_params()
    params.set("source.target.temperature", 300.0)
    params.set("source.target.emissivity", 0.95)
    params.set("atmosphere.model", "modtran")
    params.set("geometry.sensor_altitude_m", 100_000.0)
    params.set("geometry.solar_zenith_rad", np.deg2rad(30.0))
    params.set("optics.aperture_diameter_m", 0.08)
    params.set("optics.focal_length_m", 0.20)
    params.set("optics.transmission_scalar", 0.60)
    params.set("detector.pixel_pitch_x_um", 17.0)
    params.set("detector.pixel_pitch_y_um", 17.0)
    params.set("detector.qe_value", 0.55)
    params.set("detector.dark_rate_e_per_s", 1000.0)
    params.set("spectral_integration.filter_min_um", float(wl[0]))
    params.set("spectral_integration.filter_max_um", float(wl[-1]))
    params.set("spectral_integration.integration_time_s", 0.015)
    params.set("readout.read_noise_e_rms", 20.0)
    params.set("readout.gain_e_per_dn", 2.0)
    params.set("readout.adc_bits", 14)
    params.resolve()
    return params


def _los() -> LineOfSightGeometry:
    return LineOfSightGeometry(
        h_tgt=0.0,
        h_sensor=100_000.0,
        theta_o=0.0,
        h_atm_top=1.0e5,
        theta_s=np.deg2rad(30.0),
        delta_phi=0.0,
    )


# ---------------------------------------------------------------------------
# Level 0 — the helper's key equation
# ---------------------------------------------------------------------------


class TestResampleTransmittanceHelper:
    """The shared log-τ resample, exercised directly."""

    @pytest.mark.level0
    def test_midpoint_is_geometric_mean(self) -> None:
        """Key equation: log-linear resample ⇒ τ(mid) = sqrt(τ_i · τ_i+1).

        A linear-in-τ resample returns the arithmetic mean instead, which is
        strictly larger (AM–GM) for any non-constant cell.
        """
        tau = _tau(STORED_WL)
        got = resample_transmittance(
            _spectral("tau", STORED_WL, tau), SpectralGrid(wavelengths_um=MID_WL)
        ).values

        expected = np.sqrt(tau[:-1] * tau[1:])
        np.testing.assert_allclose(got, expected, rtol=1e-14, atol=0.0)

        # And the analytic closed form, since ln τ is exactly linear in λ.
        np.testing.assert_allclose(got, _tau(MID_WL), rtol=1e-14, atol=0.0)

        # The old convention would have landed on the arithmetic mean.
        arithmetic = 0.5 * (tau[:-1] + tau[1:])
        assert np.all(arithmetic > expected)

    @pytest.mark.level0
    def test_native_grid_is_bit_identical(self) -> None:
        """No resample needed ⇒ exact no-op, not an exp(log(τ)) round trip."""
        tau = _tau(STORED_WL)
        got = resample_transmittance(
            _spectral("tau", STORED_WL, tau), SpectralGrid(wavelengths_um=STORED_WL)
        ).values
        np.testing.assert_array_equal(got, tau)

    @pytest.mark.level0
    def test_opaque_band_rides_the_floor(self) -> None:
        """τ = 0 bands stay finite, non-negative, and opaque — never −inf/NaN."""
        tau = np.where(STORED_WL >= 4.0, 0.0, _tau(STORED_WL))
        got = resample_transmittance(
            _spectral("tau", STORED_WL, tau), SpectralGrid(wavelengths_um=MID_WL)
        ).values

        assert np.all(np.isfinite(got))
        assert np.all(got >= 0.0)
        assert np.all(got <= 1.0)
        # Midpoints bracketed by two opaque samples sit at the floor itself.
        deep = MID_WL > 4.0
        np.testing.assert_allclose(got[deep], TAU_FLOOR, rtol=1e-12, atol=0.0)

    @pytest.mark.level0
    def test_over_unity_is_not_capped(self) -> None:
        """τ > 1 is invalid data — it must survive to the loud downstream check.

        The floor is a lower clamp only; capping at 1.0 here would convert a
        mis-scaled file into a plausible-looking column (Rule 17).
        """
        got = resample_transmittance(
            _spectral("tau", STORED_WL, np.full_like(STORED_WL, 1.5)),
            SpectralGrid(wavelengths_um=MID_WL),
        ).values
        np.testing.assert_allclose(got, 1.5, rtol=1e-14, atol=0.0)

    @pytest.mark.level0
    def test_negative_transmittance_raises(self) -> None:
        """Negative τ has no logarithm and must not be silently floored."""
        bad = _tau(STORED_WL).copy()
        bad[3] = -0.01
        with pytest.raises(Exception, match="negative values"):
            resample_transmittance(
                _spectral("tau", STORED_WL, bad), SpectralGrid(wavelengths_um=MID_WL)
            )

    @pytest.mark.level0
    def test_extrapolation_still_fails_loud(self) -> None:
        """The no-extrapolation guard survives the log-space detour."""
        outside = np.linspace(2.0, 6.0, 21)
        with pytest.raises(Exception, match="outside source range"):
            resample_transmittance(
                _spectral("tau", STORED_WL, _tau(STORED_WL)),
                SpectralGrid(wavelengths_um=outside),
            )


# ---------------------------------------------------------------------------
# Level 0/1 — TabulatedAtmosphere
# ---------------------------------------------------------------------------


class TestTabulatedLogTau:
    @pytest.mark.level0
    def test_stored_grid_query_is_bit_identical(self) -> None:
        """(a) Native-grid query is an exact no-op through build_state."""
        tau = _tau(STORED_WL)
        state = _tabulated(STORED_WL, tau).build_state(STORED_WL, _geometry())
        np.testing.assert_array_equal(state.transmittance.values, tau)

    @pytest.mark.level0
    def test_evaluate_stored_grid_query_is_bit_identical(self) -> None:
        """(a) Same for the evaluate() adapter's τ_sun/τ_up/τ_full_up."""
        tau = _tau(STORED_WL)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            q = _tabulated(STORED_WL, tau).evaluate(STORED_WL, _los(), None)  # type: ignore[arg-type]
        np.testing.assert_array_equal(q.tau_sun, tau)
        np.testing.assert_array_equal(q.tau_up, tau)
        np.testing.assert_array_equal(q.tau_full_up, tau)

    @pytest.mark.level0
    def test_offset_grid_midpoint_identity(self) -> None:
        """(b) The analytic identity collapses to machine precision off-node."""
        state = _tabulated(STORED_WL, _tau(STORED_WL)).build_state(MID_WL, _geometry())
        np.testing.assert_allclose(state.transmittance.values, _tau(MID_WL), rtol=1e-14, atol=0.0)

    @pytest.mark.level0
    def test_evaluate_offset_grid_midpoint_identity(self) -> None:
        """(b) Same identity through evaluate()."""
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            q = _tabulated(STORED_WL, _tau(STORED_WL)).evaluate(MID_WL, _los(), None)  # type: ignore[arg-type]
        np.testing.assert_allclose(q.tau_up, _tau(MID_WL), rtol=1e-14, atol=0.0)

    @pytest.mark.level0
    def test_opaque_band_survives(self) -> None:
        """(c) τ = 0 band through the floor: finite, bounded, still opaque."""
        tau = np.where(STORED_WL >= 4.0, 0.0, _tau(STORED_WL))
        got = _tabulated(STORED_WL, tau).build_state(MID_WL, _geometry()).transmittance.values
        assert np.all(np.isfinite(got))
        assert np.all((got >= 0.0) & (got <= 1.0))
        assert np.all(got[MID_WL > 4.0] <= 1e-29)

    @pytest.mark.level1
    def test_radiances_still_resample_linearly(self) -> None:
        """(d) L_path and L_atm_down are additive — they stay linear in τ-space.

        Pinned on a deliberately curved spectrum so linear and log differ.
        """
        curved = _tau(STORED_WL)
        state = _tabulated(STORED_WL, np.full_like(STORED_WL, 0.5), curved, curved).build_state(
            MID_WL, _geometry()
        )
        arithmetic = 0.5 * (curved[:-1] + curved[1:])
        np.testing.assert_allclose(state.path_radiance.values, arithmetic, rtol=1e-15, atol=0.0)
        np.testing.assert_allclose(state.atm_emission_down.values, arithmetic, rtol=1e-15, atol=0.0)


# ---------------------------------------------------------------------------
# Level 0/1 — ModtranAtmosphere
# ---------------------------------------------------------------------------


class TestModtranLogTau:
    @pytest.mark.level0
    def test_stored_grid_query_is_bit_identical(self) -> None:
        """(a) Native-grid query is an exact no-op through build_state."""
        tau = _tau(STORED_WL)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            state = _modtran(STORED_WL, tau).build_state(STORED_WL, _geometry())
        np.testing.assert_array_equal(state.transmittance.values, tau)

    @pytest.mark.level0
    def test_offset_grid_midpoint_identity(self) -> None:
        """(b) The analytic identity collapses to machine precision off-node."""
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            state = _modtran(STORED_WL, _tau(STORED_WL)).build_state(MID_WL, _geometry())
        np.testing.assert_allclose(state.transmittance.values, _tau(MID_WL), rtol=1e-14, atol=0.0)

    @pytest.mark.level0
    def test_opaque_band_survives(self) -> None:
        """(c) τ = 0 band through the floor."""
        tau = np.where(STORED_WL >= 4.0, 0.0, _tau(STORED_WL))
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            got = _modtran(STORED_WL, tau).build_state(MID_WL, _geometry()).transmittance.values
        assert np.all(np.isfinite(got))
        assert np.all((got >= 0.0) & (got <= 1.0))
        assert np.all(got[MID_WL > 4.0] <= 1e-29)

    @pytest.mark.level1
    def test_path_radiance_still_resamples_linearly(self) -> None:
        """(d) The MODTRAN path radiance stays linear."""
        curved = _tau(STORED_WL)
        atm = ModtranAtmosphere(
            ModtranConfig(binary_path="nonexistent-modtran-binary", allow_fallback=False),
            tape7_import=Tape7Import(
                wavelength_um=STORED_WL,
                transmittance=np.full_like(STORED_WL, 0.5),
                path_radiance=curved,
                ground_reflected=np.zeros_like(STORED_WL),
                source_path="synthetic-tape7",
                content_key="cu316cu316cu316b",
            ),
        )
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            state = atm.build_state(MID_WL, _geometry())
        arithmetic = 0.5 * (curved[:-1] + curved[1:])
        np.testing.assert_allclose(state.path_radiance.values, arithmetic, rtol=1e-15, atol=0.0)

    @pytest.mark.level1
    def test_sun_and_up_leg_tau_use_log_space(self) -> None:
        """(b) τ_sun and τ_up — the two-leg import arrays — obey the identity."""
        sun_slope, up_slope = 2.0, 3.0
        atm = _modtran(
            STORED_WL,
            _tau(STORED_WL),
            sun_tau=np.exp(-sun_slope * STORED_WL),
            up_tau=np.exp(-up_slope * STORED_WL),
        )
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            q = atm.evaluate(MID_WL, _los(), _modtran_params(MID_WL))

        np.testing.assert_allclose(q.tau_sun, np.exp(-sun_slope * MID_WL), rtol=1e-14, atol=0.0)
        np.testing.assert_allclose(q.tau_up, np.exp(-up_slope * MID_WL), rtol=1e-14, atol=0.0)
        np.testing.assert_allclose(q.tau_full_up, _tau(MID_WL), rtol=1e-14, atol=0.0)


# ---------------------------------------------------------------------------
# Level 1 — cross-backend consistency (the divergence CU-316 records)
# ---------------------------------------------------------------------------


class TestCrossBackendTauConsistency:
    """(e) One stored column, three backends, one answer.

    The same τ spectrum is served by ``TabulatedAtmosphere``,
    ``ModtranAtmosphere`` and ``InterpolatedAtmosphere`` on the *same*
    off-node chain grid.  The interpolated family uses two nodes carrying
    identical spectra, so its geometry interpolation is an exact identity
    and the only operation left under test is the spectral resample.
    Before CU-316 the tabulated/MODTRAN answers sat ~1.5 % above the
    interpolated one at cell midpoints (arithmetic vs geometric mean).
    """

    @staticmethod
    def _interpolated(wl: np.ndarray, tau: np.ndarray) -> InterpolatedAtmosphere:
        def _point(alt: float) -> GeometryPoint:
            return GeometryPoint(
                coordinates={"target_altitude_m": alt},
                transmittance=_spectral("tau", wl, tau),
                path_radiance=_spectral("lp", wl, np.zeros_like(wl), "W/m²/sr/µm"),
                atm_emission_down=_spectral("ld", wl, np.zeros_like(wl), "W/m²/sr/µm"),
            )

        return InterpolatedAtmosphere([_point(0.0), _point(1000.0)], axes=["target_altitude_m"])

    @pytest.mark.level1
    def test_three_backends_agree_on_an_off_node_grid(self) -> None:
        tau = _tau(STORED_WL)
        geom = _geometry()

        tab = _tabulated(STORED_WL, tau).build_state(MID_WL, geom).transmittance.values
        interp = self._interpolated(STORED_WL, tau).build_state(MID_WL, geom).transmittance.values
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            mod = _modtran(STORED_WL, tau).build_state(MID_WL, geom).transmittance.values

        # Residual pinned explicitly: the three paths differ only by the
        # order of identical float operations, so agreement is at ULP level.
        np.testing.assert_allclose(tab, interp, rtol=1e-14, atol=0.0)
        np.testing.assert_allclose(mod, interp, rtol=1e-14, atol=0.0)

    @pytest.mark.level1
    def test_realistic_chain_grid_agreement(self) -> None:
        """Same check on a realistic 200-point MWIR chain grid.

        A banded MWIR-like column (τ ≈ 0.012–0.22) on a 41-point stored grid
        served onto a 200-point chain grid — the configuration class the CU
        measured its ~1.5 % divergence on.  Under the old linear-in-τ
        convention these three backends disagree by 1.44 % here; they now
        agree to float round-off.
        """
        stored = np.linspace(3.0, 5.0, 41)
        chain = np.linspace(3.05, 4.95, 200)
        tau = np.exp(-(0.4 + 0.6 * np.sin(2.5 * stored) ** 2) * stored)
        geom = _geometry()

        tab = _tabulated(stored, tau).build_state(chain, geom).transmittance.values
        interp = self._interpolated(stored, tau).build_state(chain, geom).transmittance.values
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            mod = _modtran(stored, tau).build_state(chain, geom).transmittance.values

        assert float(np.max(np.abs(tab / interp - 1.0))) < 1e-14
        assert float(np.max(np.abs(mod / interp - 1.0))) < 1e-14
