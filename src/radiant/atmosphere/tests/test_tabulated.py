"""Tests for radiant.atmosphere.tabulated.

Category C validation for TabulatedAtmosphere:
- Round-trip CSV and NPZ loading
- Resampling correctness (linear interpolation)
- Validation: non-ascending wavelength, tau out of bounds, negative radiance
- Optional L_atm_down defaults to zeros
- Extrapolation rejection
- Cross-model: SimpleAtmosphere output saved and reloaded matches
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from radiant.atmosphere.protocol import (
    Atmosphere,
    AtmosphericGeometry,
    AtmosphericState,
)
from radiant.atmosphere.simple import SimpleAtmosphere
from radiant.atmosphere.tabulated import TabulatedAtmosphere, _load_csv
from radiant.core.spectral import SpectralData

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def default_geometry() -> AtmosphericGeometry:
    return AtmosphericGeometry(
        sensor_altitude_m=10_000.0,
        target_altitude_m=0.0,
        path_zenith_rad=0.0,
        solar_zenith_rad=0.5,
        solar_azimuth_rad=0.0,
    )


@pytest.fixture()
def reference_wavelengths() -> np.ndarray:
    return np.linspace(3.0, 5.0, 100)


@pytest.fixture()
def simple_state(
    reference_wavelengths: np.ndarray,
    default_geometry: AtmosphericGeometry,
) -> AtmosphericState:
    """A SimpleAtmosphere state to use as reference data."""
    model = SimpleAtmosphere(visibility_km=23.0, precipitable_water_cm=1.4)
    return model.build_state(reference_wavelengths, default_geometry)


# ---------------------------------------------------------------------------
# CSV round-trip
# ---------------------------------------------------------------------------


def _write_csv(path: Path, wavelength_um: np.ndarray, values: np.ndarray,
               header: bool = True) -> None:
    lines = []
    if header:
        lines.append("wavelength_um,value")
    for w, v in zip(wavelength_um, values, strict=False):
        lines.append(f"{w},{v}")
    path.write_text("\n".join(lines))


class TestCSVRoundTrip:
    """Load data from CSV files and verify values match."""

    def test_round_trip_with_header(
        self, tmp_path: Path, simple_state: AtmosphericState,
        default_geometry: AtmosphericGeometry,
    ) -> None:
        wl = simple_state.wavelength_um
        tau_file = tmp_path / "tau.csv"
        lp_file = tmp_path / "lpath.csv"
        ld_file = tmp_path / "ldown.csv"

        _write_csv(tau_file, wl, simple_state.transmittance.values)
        _write_csv(lp_file, wl, simple_state.path_radiance.values)
        _write_csv(ld_file, wl, simple_state.atm_emission_down.values)

        model = TabulatedAtmosphere.from_csv(tau_file, lp_file, ld_file)
        result = model.build_state(wl, default_geometry)

        np.testing.assert_allclose(
            result.transmittance.values,
            simple_state.transmittance.values,
            rtol=1e-12,
        )
        np.testing.assert_allclose(
            result.path_radiance.values,
            simple_state.path_radiance.values,
            rtol=1e-12,
        )
        np.testing.assert_allclose(
            result.atm_emission_down.values,
            simple_state.atm_emission_down.values,
            rtol=1e-12,
        )

    def test_round_trip_no_header(
        self, tmp_path: Path, simple_state: AtmosphericState,
        default_geometry: AtmosphericGeometry,
    ) -> None:
        wl = simple_state.wavelength_um
        tau_file = tmp_path / "tau.csv"
        lp_file = tmp_path / "lpath.csv"

        _write_csv(tau_file, wl, simple_state.transmittance.values, header=False)
        _write_csv(lp_file, wl, simple_state.path_radiance.values, header=False)

        model = TabulatedAtmosphere.from_csv(tau_file, lp_file)
        result = model.build_state(wl, default_geometry)

        np.testing.assert_allclose(
            result.transmittance.values,
            simple_state.transmittance.values,
            rtol=1e-12,
        )

    def test_optional_ldown_defaults_to_zeros(
        self, tmp_path: Path, simple_state: AtmosphericState,
        default_geometry: AtmosphericGeometry,
    ) -> None:
        wl = simple_state.wavelength_um
        tau_file = tmp_path / "tau.csv"
        lp_file = tmp_path / "lpath.csv"

        _write_csv(tau_file, wl, simple_state.transmittance.values)
        _write_csv(lp_file, wl, simple_state.path_radiance.values)

        model = TabulatedAtmosphere.from_csv(tau_file, lp_file)
        result = model.build_state(wl, default_geometry)

        np.testing.assert_array_equal(result.atm_emission_down.values, 0.0)


# ---------------------------------------------------------------------------
# NPZ round-trip
# ---------------------------------------------------------------------------


class TestNPZRoundTrip:
    """Load data from NPZ files and verify values match."""

    def test_round_trip_full(
        self, tmp_path: Path, simple_state: AtmosphericState,
        default_geometry: AtmosphericGeometry,
    ) -> None:
        npz_file = tmp_path / "atm.npz"
        np.savez(
            npz_file,
            wavelength_um=simple_state.wavelength_um,
            transmittance=simple_state.transmittance.values,
            path_radiance=simple_state.path_radiance.values,
            atm_emission_down=simple_state.atm_emission_down.values,
        )

        model = TabulatedAtmosphere.from_npz(npz_file)
        result = model.build_state(simple_state.wavelength_um, default_geometry)

        np.testing.assert_allclose(
            result.transmittance.values,
            simple_state.transmittance.values,
            rtol=1e-12,
        )
        np.testing.assert_allclose(
            result.path_radiance.values,
            simple_state.path_radiance.values,
            rtol=1e-12,
        )

    def test_npz_missing_ldown_defaults_to_zeros(
        self, tmp_path: Path, simple_state: AtmosphericState,
        default_geometry: AtmosphericGeometry,
    ) -> None:
        npz_file = tmp_path / "atm.npz"
        np.savez(
            npz_file,
            wavelength_um=simple_state.wavelength_um,
            transmittance=simple_state.transmittance.values,
            path_radiance=simple_state.path_radiance.values,
        )

        model = TabulatedAtmosphere.from_npz(npz_file)
        result = model.build_state(simple_state.wavelength_um, default_geometry)
        np.testing.assert_array_equal(result.atm_emission_down.values, 0.0)


# ---------------------------------------------------------------------------
# Resampling
# ---------------------------------------------------------------------------


class TestResampling:
    """Verify resampling onto a different wavelength grid."""

    def test_resample_to_coarser_grid(
        self, tmp_path: Path, simple_state: AtmosphericState,
        default_geometry: AtmosphericGeometry,
    ) -> None:
        """Load on a fine grid, query on a coarser sub-grid."""
        wl_fine = simple_state.wavelength_um
        # Query on a coarser grid strictly within the source range.
        wl_coarse = np.linspace(
            float(wl_fine[5]), float(wl_fine[-6]), 20,
        )

        npz_file = tmp_path / "atm.npz"
        np.savez(
            npz_file,
            wavelength_um=wl_fine,
            transmittance=simple_state.transmittance.values,
            path_radiance=simple_state.path_radiance.values,
        )

        model = TabulatedAtmosphere.from_npz(npz_file)
        result = model.build_state(wl_coarse, default_geometry)

        assert result.transmittance.values.shape == wl_coarse.shape
        # Values should be interpolated: check they are bounded by
        # min/max of the source data.
        assert float(result.transmittance.values.min()) >= float(
            simple_state.transmittance.values.min() - 1e-10
        )
        assert float(result.transmittance.values.max()) <= float(
            simple_state.transmittance.values.max() + 1e-10
        )

    def test_resample_at_source_points_is_exact(
        self, tmp_path: Path, default_geometry: AtmosphericGeometry,
    ) -> None:
        """Querying at the exact source wavelengths returns exact values."""
        wl = np.array([3.0, 4.0, 5.0])
        tau = np.array([0.9, 0.7, 0.5])
        lp = np.array([0.01, 0.02, 0.03])

        npz_file = tmp_path / "atm.npz"
        np.savez(npz_file, wavelength_um=wl, transmittance=tau, path_radiance=lp)

        model = TabulatedAtmosphere.from_npz(npz_file)
        result = model.build_state(wl, default_geometry)

        np.testing.assert_allclose(
            result.transmittance.values, tau, atol=1e-15,
        )
        np.testing.assert_allclose(
            result.path_radiance.values, lp, atol=1e-15,
        )

    def test_linear_interpolation_midpoint(
        self, tmp_path: Path, default_geometry: AtmosphericGeometry,
    ) -> None:
        """Verify linear interpolation at the midpoint of two samples."""
        wl = np.array([3.0, 5.0])
        tau = np.array([0.8, 0.4])
        lp = np.array([0.01, 0.05])

        npz_file = tmp_path / "atm.npz"
        np.savez(npz_file, wavelength_um=wl, transmittance=tau, path_radiance=lp)

        model = TabulatedAtmosphere.from_npz(npz_file)
        query_wl = np.array([3.0, 4.0, 5.0])
        result = model.build_state(query_wl, default_geometry)

        # Midpoint of linear interpolation.
        assert result.transmittance.values[1] == pytest.approx(0.6, abs=1e-12)
        assert result.path_radiance.values[1] == pytest.approx(0.03, abs=1e-12)


# ---------------------------------------------------------------------------
# Extrapolation rejection
# ---------------------------------------------------------------------------


class TestExtrapolationRejection:
    """Query grid extending beyond source data must raise."""

    def test_query_beyond_source_raises(
        self, tmp_path: Path, default_geometry: AtmosphericGeometry,
    ) -> None:
        wl = np.array([3.0, 5.0])
        tau = np.array([0.9, 0.5])
        lp = np.array([0.01, 0.02])

        npz_file = tmp_path / "atm.npz"
        np.savez(npz_file, wavelength_um=wl, transmittance=tau, path_radiance=lp)

        model = TabulatedAtmosphere.from_npz(npz_file)
        with pytest.raises(ValueError, match="extends outside source range"):
            model.build_state(np.array([2.0, 3.0, 4.0, 5.0]), default_geometry)


# ---------------------------------------------------------------------------
# Validation failures
# ---------------------------------------------------------------------------


class TestValidationFailures:
    """Invalid inputs must produce actionable errors."""

    def test_tau_out_of_bounds(self) -> None:
        wl = np.array([3.0, 4.0, 5.0])
        with pytest.raises(ValueError, match="transmittance values out of"):
            TabulatedAtmosphere(
                transmittance_data=SpectralData(
                    name="tau", wavelength_um=wl, values=np.array([1.1, 0.5, 0.3]),
                    unit="", source="test",
                ),
                path_radiance_data=SpectralData(
                    name="lp", wavelength_um=wl, values=np.zeros(3),
                    unit="W/m²/sr/µm", source="test",
                ),
                atm_emission_down_data=SpectralData(
                    name="ld", wavelength_um=wl, values=np.zeros(3),
                    unit="W/m²/sr/µm", source="test",
                ),
            )

    def test_negative_path_radiance(self) -> None:
        wl = np.array([3.0, 4.0, 5.0])
        with pytest.raises(ValueError, match="path_radiance has negative"):
            TabulatedAtmosphere(
                transmittance_data=SpectralData(
                    name="tau", wavelength_um=wl, values=np.array([0.9, 0.5, 0.3]),
                    unit="", source="test",
                ),
                path_radiance_data=SpectralData(
                    name="lp", wavelength_um=wl, values=np.array([-0.01, 0.0, 0.01]),
                    unit="W/m²/sr/µm", source="test",
                ),
                atm_emission_down_data=SpectralData(
                    name="ld", wavelength_um=wl, values=np.zeros(3),
                    unit="W/m²/sr/µm", source="test",
                ),
            )

    def test_csv_file_not_found(self) -> None:
        with pytest.raises(FileNotFoundError, match="not found"):
            TabulatedAtmosphere.from_csv("/nonexistent/tau.csv", "/nonexistent/lp.csv")

    def test_npz_file_not_found(self) -> None:
        with pytest.raises(FileNotFoundError, match="not found"):
            TabulatedAtmosphere.from_npz("/nonexistent/atm.npz")

    def test_npz_missing_key(self, tmp_path: Path) -> None:
        npz_file = tmp_path / "bad.npz"
        np.savez(npz_file, wavelength_um=np.array([3.0, 5.0]))
        with pytest.raises(ValueError, match="missing required key"):
            TabulatedAtmosphere.from_npz(npz_file)

    def test_non_ascending_wavelength_csv(self, tmp_path: Path) -> None:
        f = tmp_path / "bad.csv"
        f.write_text("5.0,0.9\n3.0,0.8\n")
        with pytest.raises(ValueError, match="strictly ascending"):
            _load_csv(f)  # raw loader doesn't check, but SpectralData will
            TabulatedAtmosphere.from_csv(f, f)

    def test_empty_csv(self, tmp_path: Path) -> None:
        f = tmp_path / "empty.csv"
        f.write_text("")
        with pytest.raises(ValueError, match="empty"):
            _load_csv(f)


# ---------------------------------------------------------------------------
# Protocol conformance
# ---------------------------------------------------------------------------


class TestProtocol:
    """TabulatedAtmosphere satisfies the Atmosphere protocol."""

    def test_isinstance_check(self, tmp_path: Path) -> None:
        wl = np.array([3.0, 4.0, 5.0])
        npz = tmp_path / "atm.npz"
        np.savez(
            npz,
            wavelength_um=wl,
            transmittance=np.array([0.9, 0.8, 0.7]),
            path_radiance=np.zeros(3),
        )
        model = TabulatedAtmosphere.from_npz(npz)
        assert isinstance(model, Atmosphere)

    def test_geometry_does_not_affect_values(
        self, tmp_path: Path,
    ) -> None:
        """Values are the same regardless of query geometry."""
        wl = np.array([3.0, 4.0, 5.0])
        npz = tmp_path / "atm.npz"
        np.savez(
            npz,
            wavelength_um=wl,
            transmittance=np.array([0.9, 0.8, 0.7]),
            path_radiance=np.array([0.01, 0.02, 0.03]),
        )
        model = TabulatedAtmosphere.from_npz(npz)

        geom1 = AtmosphericGeometry(
            sensor_altitude_m=10_000.0, target_altitude_m=0.0,
            path_zenith_rad=0.0, solar_zenith_rad=0.5,
        )
        geom2 = AtmosphericGeometry(
            sensor_altitude_m=20_000.0, target_altitude_m=0.0,
            path_zenith_rad=0.5, solar_zenith_rad=0.3,
        )

        r1 = model.build_state(wl, geom1)
        r2 = model.build_state(wl, geom2)

        np.testing.assert_array_equal(
            r1.transmittance.values, r2.transmittance.values,
        )
        np.testing.assert_array_equal(
            r1.path_radiance.values, r2.path_radiance.values,
        )

    def test_deterministic(
        self, tmp_path: Path, default_geometry: AtmosphericGeometry,
    ) -> None:
        wl = np.array([3.0, 4.0, 5.0])
        npz = tmp_path / "atm.npz"
        np.savez(
            npz,
            wavelength_um=wl,
            transmittance=np.array([0.9, 0.8, 0.7]),
            path_radiance=np.zeros(3),
        )
        model = TabulatedAtmosphere.from_npz(npz)
        r1 = model.build_state(wl, default_geometry)
        r2 = model.build_state(wl, default_geometry)

        np.testing.assert_array_equal(
            r1.transmittance.values, r2.transmittance.values,
        )


# ---------------------------------------------------------------------------
# Cross-model: SimpleAtmosphere -> CSV -> TabulatedAtmosphere
# ---------------------------------------------------------------------------


class TestCrossModelConsistency:
    """SimpleAtmosphere output saved as CSV, reloaded as Tabulated, matches."""

    def test_simple_to_csv_round_trip(
        self, tmp_path: Path, simple_state: AtmosphericState,
        default_geometry: AtmosphericGeometry,
    ) -> None:
        wl = simple_state.wavelength_um
        tau_file = tmp_path / "tau.csv"
        lp_file = tmp_path / "lpath.csv"
        ld_file = tmp_path / "ldown.csv"

        _write_csv(tau_file, wl, simple_state.transmittance.values)
        _write_csv(lp_file, wl, simple_state.path_radiance.values)
        _write_csv(ld_file, wl, simple_state.atm_emission_down.values)

        tab = TabulatedAtmosphere.from_csv(tau_file, lp_file, ld_file)
        result = tab.build_state(wl, default_geometry)

        np.testing.assert_allclose(
            result.transmittance.values,
            simple_state.transmittance.values,
            rtol=1e-10,
        )
        np.testing.assert_allclose(
            result.path_radiance.values,
            simple_state.path_radiance.values,
            rtol=1e-10,
        )
        np.testing.assert_allclose(
            result.atm_emission_down.values,
            simple_state.atm_emission_down.values,
            rtol=1e-10,
        )
