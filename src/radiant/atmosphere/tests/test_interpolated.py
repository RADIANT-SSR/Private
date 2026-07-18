"""Tests for radiant.atmosphere.interpolated.

Category C validation for InterpolatedAtmosphere:

Truth anchors:
1. Log-tau midpoint formula: at the midpoint of two points,
   tau_interp = exp(0.5 * ln(tau_0) + 0.5 * ln(tau_1))
             = sqrt(tau_0 * tau_1)  (geometric mean)
2. Exact reproduction at grid nodes.
3. Cross-model: SimpleAtmosphere at 3 zeniths, interpolated midpoint
   vs direct SimpleAtmosphere at that zenith (not exact but bounded).

Failure modes:
- Extrapolation rejection
- Mismatched wavelength grids
- Fewer than 2 points
- tau = 0 edge case (log clamping)
"""

from __future__ import annotations

import numpy as np
import pytest

from radiant.atmosphere.interpolated import (
    GeometryPoint,
    InterpolatedAtmosphere,
)
from radiant.atmosphere.protocol import (
    Atmosphere,
    AtmosphericGeometry,
)
from radiant.atmosphere.simple import SimpleAtmosphere
from radiant.core.spectral import SpectralData

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_spectral(
    name: str,
    wavelength_um: np.ndarray,
    values: np.ndarray,
    unit: str = "",
) -> SpectralData:
    return SpectralData(
        name=name,
        wavelength_um=wavelength_um,
        values=values,
        unit=unit,
        source="test",
    )


def _make_point(
    coords: dict[str, float],
    wl: np.ndarray,
    tau: np.ndarray,
    lpath: np.ndarray | None = None,
    ldown: np.ndarray | None = None,
) -> GeometryPoint:
    if lpath is None:
        lpath = np.zeros_like(wl)
    if ldown is None:
        ldown = np.zeros_like(wl)
    return GeometryPoint(
        coordinates=coords,
        transmittance=_make_spectral("tau", wl, tau),
        path_radiance=_make_spectral("lp", wl, lpath, "W/m²/sr/µm"),
        atm_emission_down=_make_spectral("ld", wl, ldown, "W/m²/sr/µm"),
    )


@pytest.fixture()
def wl() -> np.ndarray:
    return np.linspace(3.0, 5.0, 50)


# ---------------------------------------------------------------------------
# Level 0: key equation — log-tau midpoint
# ---------------------------------------------------------------------------


class TestLogTauInterpolation:
    """Verify the core interpolation formula in log-transmittance space."""

    @pytest.mark.level0
    def test_midpoint_is_geometric_mean(self, wl: np.ndarray) -> None:
        """On a zenith axis, log-tau interpolates linearly in AIRMASS
        sec(θ), not the angle itself (CU-160 — key equation):

            f = (sec θ_q − sec θ_0) / (sec θ_1 − sec θ_0)
            ln τ(θ_q) = (1 − f)·ln τ_0 + f·ln τ_1
            τ(θ_q) = τ_0^(1−f) · τ_1^f
        """
        tau_0 = 0.9 * np.ones_like(wl)
        tau_1 = 0.4 * np.ones_like(wl)
        theta_0, theta_1, theta_q = 0.0, 1.0, 0.5
        sec = lambda t: 1.0 / np.cos(t)  # noqa: E731
        frac = (sec(theta_q) - sec(theta_0)) / (sec(theta_1) - sec(theta_0))
        expected_tau = tau_0 ** (1.0 - frac) * tau_1**frac

        points = [
            _make_point({"path_zenith_rad": theta_0}, wl, tau_0),
            _make_point({"path_zenith_rad": theta_1}, wl, tau_1),
        ]
        model = InterpolatedAtmosphere(points, axes=["path_zenith_rad"])

        geom = AtmosphericGeometry(
            sensor_altitude_m=10_000.0,
            target_altitude_m=0.0,
            path_zenith_rad=theta_q,
            solar_zenith_rad=0.3,
        )
        result = model.build_state(wl, geom)

        np.testing.assert_allclose(
            result.transmittance.values,
            expected_tau,
            rtol=1e-10,
        )

    @pytest.mark.level0
    def test_beer_lambert_exact_on_zenith_axis(self, wl: np.ndarray) -> None:
        """The marquee CU-160 property: if the nodes follow Beer-Lambert
        exactly — τ(θ) = τ_vert^sec(θ) — then airmass-space log-τ
        interpolation reproduces Beer at EVERY query angle, not just the
        nodes. (Linear-in-angle interpolation cannot do this; it carried
        a measured ~−4% in-band bias at the real B-fan midpoint.)"""
        tau_vert = 0.7
        thetas = (0.0, np.radians(30.0), np.radians(60.0))
        sec = lambda t: 1.0 / np.cos(t)  # noqa: E731
        points = [
            _make_point(
                {"path_zenith_rad": th}, wl, (tau_vert ** sec(th)) * np.ones_like(wl)
            )
            for th in thetas
        ]
        model = InterpolatedAtmosphere(points, axes=["path_zenith_rad"])

        for query_deg in (15.0, 37.5, 45.0, 52.0):
            theta_q = np.radians(query_deg)
            geom = AtmosphericGeometry(
                sensor_altitude_m=10_000.0,
                target_altitude_m=0.0,
                path_zenith_rad=theta_q,
                solar_zenith_rad=0.3,
            )
            result = model.build_state(wl, geom)
            np.testing.assert_allclose(
                result.transmittance.values,
                tau_vert ** sec(theta_q),
                rtol=1e-10,
                err_msg=f"Beer-Lambert not reproduced at {query_deg} deg",
            )

    @pytest.mark.level0
    def test_quarter_point_interpolation(self, wl: np.ndarray) -> None:
        """Altitude axes have no angle transform — plain log-τ linear in
        the coordinate. At 1/4 of the way between two points:
        ln(tau) = 0.75 * ln(tau_0) + 0.25 * ln(tau_1)
        tau = tau_0^0.75 * tau_1^0.25
        """
        tau_0 = 0.9 * np.ones_like(wl)
        tau_1 = 0.4 * np.ones_like(wl)
        expected_tau = tau_0**0.75 * tau_1**0.25

        points = [
            _make_point({"target_altitude_m": 0.0}, wl, tau_0),
            _make_point({"target_altitude_m": 1000.0}, wl, tau_1),
        ]
        model = InterpolatedAtmosphere(points, axes=["target_altitude_m"])

        geom = AtmosphericGeometry(
            sensor_altitude_m=10_000.0,
            target_altitude_m=250.0,
            path_zenith_rad=0.25,
            solar_zenith_rad=0.3,
        )
        result = model.build_state(wl, geom)

        np.testing.assert_allclose(
            result.transmittance.values,
            expected_tau,
            rtol=1e-10,
        )

    @pytest.mark.level0
    def test_lpath_interpolation_is_linear(self, wl: np.ndarray) -> None:
        """L_path interpolates linearly (not log) — checked on an altitude
        axis where the coordinate is untransformed."""
        lp_0 = 0.01 * np.ones_like(wl)
        lp_1 = 0.05 * np.ones_like(wl)
        expected_lp = 0.03 * np.ones_like(wl)  # midpoint

        points = [
            _make_point({"target_altitude_m": 0.0}, wl, np.ones_like(wl), lp_0),
            _make_point({"target_altitude_m": 1000.0}, wl, np.ones_like(wl), lp_1),
        ]
        model = InterpolatedAtmosphere(points, axes=["target_altitude_m"])

        geom = AtmosphericGeometry(
            sensor_altitude_m=10_000.0,
            target_altitude_m=500.0,
            path_zenith_rad=0.5,
            solar_zenith_rad=0.3,
        )
        result = model.build_state(wl, geom)

        np.testing.assert_allclose(
            result.path_radiance.values,
            expected_lp,
            rtol=1e-10,
        )

    @pytest.mark.level0
    def test_horizon_zenith_node_refused(self, wl: np.ndarray) -> None:
        """sec(θ) diverges at the horizon: a zenith NODE at
        ≥ _MAX_ZENITH_RAD is refused at construction (CU-160 guard).
        A horizon-ward QUERY beyond the node range is already caught by
        the ordinary no-extrapolation bounds check."""
        from radiant.atmosphere.errors import AtmosphereValidationError

        points = [
            _make_point({"path_zenith_rad": 0.0}, wl, 0.9 * np.ones_like(wl)),
            _make_point({"path_zenith_rad": 1.56}, wl, 0.4 * np.ones_like(wl)),
        ]
        with pytest.raises(AtmosphereValidationError, match="airmass"):
            InterpolatedAtmosphere(points, axes=["path_zenith_rad"])


# ---------------------------------------------------------------------------
# Exact reproduction at grid nodes
# ---------------------------------------------------------------------------


class TestExactAtNodes:
    """Querying at an existing grid point reproduces the original values."""

    @pytest.mark.level0
    def test_exact_at_endpoints(self, wl: np.ndarray) -> None:
        tau = np.linspace(0.9, 0.3, len(wl))
        lp = np.linspace(0.01, 0.05, len(wl))

        points = [
            _make_point({"path_zenith_rad": 0.0}, wl, tau, lp),
            _make_point({"path_zenith_rad": 1.0}, wl, 0.5 * tau, 2.0 * lp),
        ]
        model = InterpolatedAtmosphere(points, axes=["path_zenith_rad"])

        geom = AtmosphericGeometry(
            sensor_altitude_m=10_000.0,
            target_altitude_m=0.0,
            path_zenith_rad=0.0,
            solar_zenith_rad=0.3,
        )
        result = model.build_state(wl, geom)

        np.testing.assert_allclose(result.transmittance.values, tau, rtol=1e-10)
        np.testing.assert_allclose(result.path_radiance.values, lp, rtol=1e-10)

    @pytest.mark.level0
    def test_exact_at_interior_node(self, wl: np.ndarray) -> None:
        """3 points; query at the middle one."""
        tau_vals = [0.9 * np.ones_like(wl), 0.6 * np.ones_like(wl), 0.3 * np.ones_like(wl)]
        zeniths = [0.0, 0.5, 1.0]

        points = [
            _make_point({"path_zenith_rad": z}, wl, t)
            for z, t in zip(zeniths, tau_vals, strict=False)
        ]
        model = InterpolatedAtmosphere(points, axes=["path_zenith_rad"])

        geom = AtmosphericGeometry(
            sensor_altitude_m=10_000.0,
            target_altitude_m=0.0,
            path_zenith_rad=0.5,
            solar_zenith_rad=0.3,
        )
        result = model.build_state(wl, geom)

        np.testing.assert_allclose(
            result.transmittance.values,
            0.6,
            rtol=1e-10,
        )


# ---------------------------------------------------------------------------
# 2D interpolation
# ---------------------------------------------------------------------------


class TestMultiAxisInterpolation:
    """Interpolation over multiple geometry axes."""

    @pytest.mark.level1
    def test_2d_structured_grid(self, wl: np.ndarray) -> None:
        """2x2 grid of (zenith, altitude); verify interior interpolation."""
        zeniths = [0.0, 1.0]
        altitudes = [5_000.0, 20_000.0]

        points = []
        for z in zeniths:
            for a in altitudes:
                tau = (0.9 - 0.3 * z) * (1.0 - a / 40_000.0) * np.ones_like(wl)
                points.append(
                    _make_point(
                        {"path_zenith_rad": z, "sensor_altitude_m": a},
                        wl,
                        np.clip(tau, 0.01, 1.0),
                    )
                )

        model = InterpolatedAtmosphere(
            points,
            axes=["path_zenith_rad", "sensor_altitude_m"],
        )
        assert model.grid_type == "regular"
        assert model.n_points == 4

        # Query at center: zenith=0.5, altitude=12500
        geom = AtmosphericGeometry(
            sensor_altitude_m=12_500.0,
            target_altitude_m=0.0,
            path_zenith_rad=0.5,
            solar_zenith_rad=0.3,
        )
        result = model.build_state(wl, geom)

        # Values should be between extremes.
        assert float(result.transmittance.values.min()) > 0.0
        assert float(result.transmittance.values.max()) <= 1.0

    @pytest.mark.level1
    def test_scattered_points(self, wl: np.ndarray) -> None:
        """Non-grid points should use LinearNDInterpolator."""
        # 4 non-collinear points that don't form a 2x2 grid.
        points = [
            _make_point(
                {"path_zenith_rad": 0.0, "sensor_altitude_m": 10_000.0},
                wl,
                0.9 * np.ones_like(wl),
            ),
            _make_point(
                {"path_zenith_rad": 1.0, "sensor_altitude_m": 10_000.0},
                wl,
                0.5 * np.ones_like(wl),
            ),
            _make_point(
                {"path_zenith_rad": 0.0, "sensor_altitude_m": 20_000.0},
                wl,
                0.85 * np.ones_like(wl),
            ),
            _make_point(
                {"path_zenith_rad": 0.5, "sensor_altitude_m": 15_000.0},
                wl,
                0.7 * np.ones_like(wl),
            ),
        ]
        model = InterpolatedAtmosphere(
            points,
            axes=["path_zenith_rad", "sensor_altitude_m"],
        )
        assert model.grid_type == "scattered"

        # Query at the exact interior point.
        geom = AtmosphericGeometry(
            sensor_altitude_m=15_000.0,
            target_altitude_m=0.0,
            path_zenith_rad=0.5,
            solar_zenith_rad=0.3,
        )
        result = model.build_state(wl, geom)

        # Should reproduce the exact point at (0.5, 15000).
        np.testing.assert_allclose(
            result.transmittance.values,
            0.7,
            rtol=1e-4,
        )


# ---------------------------------------------------------------------------
# Cross-model: SimpleAtmosphere verification
# ---------------------------------------------------------------------------


class TestCrossModelConsistency:
    """Interpolated SimpleAtmosphere states should bracket the truth."""

    @pytest.mark.level1
    def test_simple_atmosphere_interpolation_bounded(self) -> None:
        """Build from 3 SimpleAtmosphere runs at different zeniths.
        The interpolated result at the midpoint should be bounded by
        the adjacent direct SimpleAtmosphere evaluations.
        """
        wl = np.linspace(3.0, 5.0, 100)
        zeniths = [0.0, 0.4, 0.8]
        simple = SimpleAtmosphere(visibility_km=23.0)

        states = []
        geom_dicts = []
        for z in zeniths:
            geom = AtmosphericGeometry(
                sensor_altitude_m=10_000.0,
                target_altitude_m=0.0,
                path_zenith_rad=z,
                solar_zenith_rad=0.5,
            )
            states.append(simple.build_state(wl, geom))
            geom_dicts.append({"path_zenith_rad": z})

        model = InterpolatedAtmosphere.from_states(
            states,
            geom_dicts,
            axes=["path_zenith_rad"],
        )

        # Interpolate at z=0.2 (between first two nodes).
        query_geom = AtmosphericGeometry(
            sensor_altitude_m=10_000.0,
            target_altitude_m=0.0,
            path_zenith_rad=0.2,
            solar_zenith_rad=0.5,
        )
        result = model.build_state(wl, query_geom)

        # Transmittance at z=0.2 should be between z=0 and z=0.4
        tau_lo = states[1].transmittance.values  # z=0.4, lower tau
        tau_hi = states[0].transmittance.values  # z=0.0, higher tau
        assert np.all(result.transmittance.values >= tau_lo - 1e-10)
        assert np.all(result.transmittance.values <= tau_hi + 1e-10)


# ---------------------------------------------------------------------------
# Extrapolation rejection
# ---------------------------------------------------------------------------


class TestExtrapolationRejection:
    """Queries outside the available range must raise."""

    @pytest.mark.level0
    def test_beyond_upper_bound(self, wl: np.ndarray) -> None:
        points = [
            _make_point({"path_zenith_rad": 0.0}, wl, 0.9 * np.ones_like(wl)),
            _make_point({"path_zenith_rad": 0.5}, wl, 0.7 * np.ones_like(wl)),
        ]
        model = InterpolatedAtmosphere(points, axes=["path_zenith_rad"])

        geom = AtmosphericGeometry(
            sensor_altitude_m=10_000.0,
            target_altitude_m=0.0,
            path_zenith_rad=0.8,  # beyond max=0.5
            solar_zenith_rad=0.3,
        )
        with pytest.raises(ValueError, match="outside the available range"):
            model.build_state(wl, geom)

    @pytest.mark.level0
    def test_below_lower_bound(self, wl: np.ndarray) -> None:
        points = [
            _make_point({"path_zenith_rad": 0.2}, wl, 0.9 * np.ones_like(wl)),
            _make_point({"path_zenith_rad": 0.8}, wl, 0.5 * np.ones_like(wl)),
        ]
        model = InterpolatedAtmosphere(points, axes=["path_zenith_rad"])

        geom = AtmosphericGeometry(
            sensor_altitude_m=10_000.0,
            target_altitude_m=0.0,
            path_zenith_rad=0.1,  # below min=0.2
            solar_zenith_rad=0.3,
        )
        with pytest.raises(ValueError, match="outside the available range"):
            model.build_state(wl, geom)


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Edge cases: tau=0, tau=1, mismatched grids."""

    @pytest.mark.level0
    def test_tau_near_zero_clamped(self, wl: np.ndarray) -> None:
        """tau=0 should be clamped to TAU_FLOOR before log; no NaN."""
        points = [
            _make_point({"path_zenith_rad": 0.0}, wl, np.zeros_like(wl)),
            _make_point({"path_zenith_rad": 1.0}, wl, 0.5 * np.ones_like(wl)),
        ]
        model = InterpolatedAtmosphere(points, axes=["path_zenith_rad"])

        geom = AtmosphericGeometry(
            sensor_altitude_m=10_000.0,
            target_altitude_m=0.0,
            path_zenith_rad=0.5,
            solar_zenith_rad=0.3,
        )
        result = model.build_state(wl, geom)

        assert not np.any(np.isnan(result.transmittance.values))
        assert np.all(result.transmittance.values >= 0.0)

    @pytest.mark.level0
    def test_tau_one_exo_like(self, wl: np.ndarray) -> None:
        """tau=1 everywhere (exo-like); log(1)=0 should work."""
        points = [
            _make_point({"path_zenith_rad": 0.0}, wl, np.ones_like(wl)),
            _make_point({"path_zenith_rad": 1.0}, wl, np.ones_like(wl)),
        ]
        model = InterpolatedAtmosphere(points, axes=["path_zenith_rad"])

        geom = AtmosphericGeometry(
            sensor_altitude_m=10_000.0,
            target_altitude_m=0.0,
            path_zenith_rad=0.5,
            solar_zenith_rad=0.3,
        )
        result = model.build_state(wl, geom)

        np.testing.assert_allclose(result.transmittance.values, 1.0, atol=1e-15)

    @pytest.mark.level1
    def test_mismatched_wavelength_grids_raises(self) -> None:
        wl1 = np.linspace(3.0, 5.0, 50)
        wl2 = np.linspace(3.0, 5.0, 60)  # different grid

        points = [
            _make_point({"path_zenith_rad": 0.0}, wl1, 0.9 * np.ones(50)),
            _make_point({"path_zenith_rad": 1.0}, wl2, 0.5 * np.ones(60)),
        ]
        with pytest.raises(ValueError, match="different wavelength grid"):
            InterpolatedAtmosphere(points, axes=["path_zenith_rad"])

    @pytest.mark.level1
    def test_in_range_query_grid_is_resampled(self, wl: np.ndarray) -> None:
        """CU-156: a query grid inside the stored spectral range is served by
        linear resampling of the geometry-interpolated spectra (the
        TabulatedAtmosphere pattern). Spectrally-flat data resample exactly."""
        points = [
            _make_point({"path_zenith_rad": 0.0}, wl, 0.9 * np.ones_like(wl)),
            _make_point({"path_zenith_rad": 1.0}, wl, 0.5 * np.ones_like(wl)),
        ]
        model = InterpolatedAtmosphere(points, axes=["path_zenith_rad"])

        different_wl = np.linspace(3.0, 5.0, 30)  # same range, different sampling
        geom = AtmosphericGeometry(
            sensor_altitude_m=10_000.0,
            target_altitude_m=0.0,
            path_zenith_rad=0.0,
            solar_zenith_rad=0.3,
        )
        state = model.build_state(different_wl, geom)
        assert state.transmittance.wavelength_um.shape == different_wl.shape
        np.testing.assert_allclose(state.transmittance.values, 0.9, rtol=1e-12)

    def test_query_grid_outside_stored_range_raises(self, wl: np.ndarray) -> None:
        """CU-156: no spectral extrapolation — an out-of-range query fails loud."""
        points = [
            _make_point({"path_zenith_rad": 0.0}, wl, 0.9 * np.ones_like(wl)),
            _make_point({"path_zenith_rad": 1.0}, wl, 0.5 * np.ones_like(wl)),
        ]
        model = InterpolatedAtmosphere(points, axes=["path_zenith_rad"])

        beyond_wl = np.linspace(2.0, 6.0, 30)  # extends past [3, 5] µm stored range
        geom = AtmosphericGeometry(
            sensor_altitude_m=10_000.0,
            target_altitude_m=0.0,
            path_zenith_rad=0.5,
            solar_zenith_rad=0.3,
        )
        with pytest.raises(ValueError, match="outside source range"):
            model.build_state(beyond_wl, geom)


# ---------------------------------------------------------------------------
# Validation failures
# ---------------------------------------------------------------------------


class TestValidationFailures:
    """Invalid constructor inputs."""

    @pytest.mark.level0
    def test_fewer_than_2_points(self, wl: np.ndarray) -> None:
        points = [_make_point({"path_zenith_rad": 0.0}, wl, 0.9 * np.ones_like(wl))]
        with pytest.raises(ValueError, match="at least 2"):
            InterpolatedAtmosphere(points, axes=["path_zenith_rad"])

    @pytest.mark.level0
    def test_no_axes(self, wl: np.ndarray) -> None:
        points = [
            _make_point({"path_zenith_rad": 0.0}, wl, 0.9 * np.ones_like(wl)),
            _make_point({"path_zenith_rad": 1.0}, wl, 0.5 * np.ones_like(wl)),
        ]
        with pytest.raises(ValueError, match="at least one"):
            InterpolatedAtmosphere(points, axes=[])

    @pytest.mark.level0
    def test_invalid_axis_name(self, wl: np.ndarray) -> None:
        points = [
            _make_point({"path_zenith_rad": 0.0}, wl, 0.9 * np.ones_like(wl)),
            _make_point({"path_zenith_rad": 1.0}, wl, 0.5 * np.ones_like(wl)),
        ]
        with pytest.raises(ValueError, match="not a valid geometry"):
            InterpolatedAtmosphere(points, axes=["invalid_field"])

    @pytest.mark.level0
    def test_missing_coordinate(self, wl: np.ndarray) -> None:
        points = [
            _make_point({"path_zenith_rad": 0.0}, wl, 0.9 * np.ones_like(wl)),
            _make_point({}, wl, 0.5 * np.ones_like(wl)),  # missing coord
        ]
        with pytest.raises(ValueError, match="missing coordinate"):
            InterpolatedAtmosphere(points, axes=["path_zenith_rad"])

    @pytest.mark.level0
    def test_invalid_method(self, wl: np.ndarray) -> None:
        points = [
            _make_point({"path_zenith_rad": 0.0}, wl, 0.9 * np.ones_like(wl)),
            _make_point({"path_zenith_rad": 1.0}, wl, 0.5 * np.ones_like(wl)),
        ]
        with pytest.raises(ValueError, match="not supported"):
            InterpolatedAtmosphere(points, axes=["path_zenith_rad"], method="cubic")


# ---------------------------------------------------------------------------
# Protocol and properties
# ---------------------------------------------------------------------------


class TestProtocol:
    """InterpolatedAtmosphere satisfies the Atmosphere protocol."""

    @pytest.mark.level1
    def test_isinstance_check(self, wl: np.ndarray) -> None:
        points = [
            _make_point({"path_zenith_rad": 0.0}, wl, 0.9 * np.ones_like(wl)),
            _make_point({"path_zenith_rad": 1.0}, wl, 0.5 * np.ones_like(wl)),
        ]
        model = InterpolatedAtmosphere(points, axes=["path_zenith_rad"])
        assert isinstance(model, Atmosphere)

    @pytest.mark.level0
    def test_coordinate_bounds(self, wl: np.ndarray) -> None:
        points = [
            _make_point({"path_zenith_rad": 0.2}, wl, 0.9 * np.ones_like(wl)),
            _make_point({"path_zenith_rad": 0.8}, wl, 0.5 * np.ones_like(wl)),
        ]
        model = InterpolatedAtmosphere(points, axes=["path_zenith_rad"])
        bounds = model.coordinate_bounds()
        assert bounds["path_zenith_rad"] == pytest.approx((0.2, 0.8))

    @pytest.mark.level1
    def test_deterministic(self, wl: np.ndarray) -> None:
        points = [
            _make_point({"path_zenith_rad": 0.0}, wl, 0.9 * np.ones_like(wl)),
            _make_point({"path_zenith_rad": 1.0}, wl, 0.5 * np.ones_like(wl)),
        ]
        model = InterpolatedAtmosphere(points, axes=["path_zenith_rad"])

        geom = AtmosphericGeometry(
            sensor_altitude_m=10_000.0,
            target_altitude_m=0.0,
            path_zenith_rad=0.5,
            solar_zenith_rad=0.3,
        )
        r1 = model.build_state(wl, geom)
        r2 = model.build_state(wl, geom)

        np.testing.assert_array_equal(
            r1.transmittance.values,
            r2.transmittance.values,
        )

    @pytest.mark.level1
    def test_from_states_factory(self) -> None:
        """from_states class method works correctly."""
        wl = np.linspace(3.0, 5.0, 50)
        simple = SimpleAtmosphere(visibility_km=23.0)
        states = []
        geom_dicts = []
        for z in [0.0, 0.5, 1.0]:
            geom = AtmosphericGeometry(
                sensor_altitude_m=10_000.0,
                target_altitude_m=0.0,
                path_zenith_rad=z,
                solar_zenith_rad=0.5,
            )
            states.append(simple.build_state(wl, geom))
            geom_dicts.append({"path_zenith_rad": z})

        model = InterpolatedAtmosphere.from_states(
            states,
            geom_dicts,
            axes=["path_zenith_rad"],
        )
        assert model.n_points == 3
        assert model.grid_type == "regular"
