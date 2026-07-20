"""Tests for SpectralGrid, SpectralData, and SpectralDataStore.

Category B — Core Abstractions.

All tests use @pytest.mark.level0 and explicit tolerances on pytest.approx.
"""

from __future__ import annotations

import math
import warnings

import numpy as np
import pytest

from radiant.core.spectral import SpectralData, SpectralDataStore, SpectralGrid

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_sd(
    name: str = "test",
    lam_min: float = 1.0,
    lam_max: float = 5.0,
    n: int = 1000,
    values: np.ndarray | None = None,
) -> SpectralData:
    wl = np.linspace(lam_min, lam_max, n)
    v = np.ones(n) if values is None else values
    return SpectralData(
        name=name,
        wavelength_um=wl,
        values=v,
        unit="W/m²/sr/µm",
        source="test",
    )


# ===========================================================================
# SpectralGrid tests
# ===========================================================================


class TestSpectralGridUniform:
    @pytest.mark.level0
    def test_uniform_basic(self) -> None:
        grid = SpectralGrid.uniform(1.0, 5.0, 401)
        assert grid.n_points == 401
        assert grid.lam_min == pytest.approx(1.0, abs=1e-15)
        assert grid.lam_max == pytest.approx(5.0, abs=1e-15)
        assert grid.span == pytest.approx(4.0, abs=1e-15)

    @pytest.mark.level0
    def test_uniform_two_points(self) -> None:
        grid = SpectralGrid.uniform(0.5, 2.5, 2)
        assert grid.n_points == 2
        assert grid.span == pytest.approx(2.0, abs=1e-15)

    @pytest.mark.level0
    def test_uniform_ascending(self) -> None:
        grid = SpectralGrid.uniform(1.0, 5.0, 50)
        diffs = np.diff(grid.wavelengths_um)
        assert np.all(diffs > 0)


class TestSpectralGridValidation:
    @pytest.mark.level0
    def test_n_points_lt_2_raises(self) -> None:
        with pytest.raises(ValueError, match="at least 2 points"):
            SpectralGrid(wavelengths_um=np.array([1.0]))

    @pytest.mark.level0
    def test_negative_wavelength_raises(self) -> None:
        with pytest.raises(ValueError, match="non-negative"):
            SpectralGrid(wavelengths_um=np.array([-0.1, 1.0, 2.0]))

    @pytest.mark.level0
    def test_non_ascending_raises(self) -> None:
        with pytest.raises(ValueError, match="strictly ascending"):
            SpectralGrid(wavelengths_um=np.array([1.0, 3.0, 2.0, 4.0]))

    @pytest.mark.level0
    def test_non_ascending_constant_raises(self) -> None:
        with pytest.raises(ValueError, match="strictly ascending"):
            SpectralGrid(wavelengths_um=np.array([1.0, 1.0, 2.0]))

    @pytest.mark.level0
    def test_uniform_n_points_lt_2_raises(self) -> None:
        with pytest.raises(ValueError, match="n_points"):
            SpectralGrid.uniform(1.0, 5.0, 1)

    @pytest.mark.level0
    def test_uniform_lam_min_ge_lam_max_raises(self) -> None:
        with pytest.raises(ValueError, match="lam_min"):
            SpectralGrid.uniform(5.0, 1.0, 10)


class TestSpectralGridSerialization:
    @pytest.mark.level0
    def test_round_trip(self) -> None:
        grid = SpectralGrid.uniform(0.4, 14.0, 137)
        d = grid.to_dict()
        grid2 = SpectralGrid.from_dict(d)
        assert np.array_equal(grid.wavelengths_um, grid2.wavelengths_um)

    @pytest.mark.level0
    def test_round_trip_machine_precision(self) -> None:
        wl = np.linspace(1.0, 5.0, 1000)
        grid = SpectralGrid(wavelengths_um=wl)
        d = grid.to_dict()
        grid2 = SpectralGrid.from_dict(d)
        # JSON round-trip through float list — values should match to float64 repr
        np.testing.assert_array_equal(grid.wavelengths_um, grid2.wavelengths_um)


class TestSpectralGridEqualityHash:
    @pytest.mark.level0
    def test_equal_same_arrays(self) -> None:
        wl = np.linspace(1.0, 5.0, 100)
        g1 = SpectralGrid(wavelengths_um=wl)
        g2 = SpectralGrid(wavelengths_um=wl.copy())
        assert g1 == g2

    @pytest.mark.level0
    def test_not_equal_different_arrays(self) -> None:
        g1 = SpectralGrid.uniform(1.0, 5.0, 100)
        g2 = SpectralGrid.uniform(1.0, 5.0, 101)
        assert g1 != g2

    @pytest.mark.level0
    def test_not_equal_different_range(self) -> None:
        g1 = SpectralGrid.uniform(1.0, 5.0, 100)
        g2 = SpectralGrid.uniform(2.0, 5.0, 100)
        assert g1 != g2

    @pytest.mark.level0
    def test_hash_same_grid(self) -> None:
        wl = np.linspace(1.0, 5.0, 100)
        g1 = SpectralGrid(wavelengths_um=wl)
        g2 = SpectralGrid(wavelengths_um=wl.copy())
        assert hash(g1) == hash(g2)

    @pytest.mark.level0
    def test_hash_different_grids(self) -> None:
        g1 = SpectralGrid.uniform(1.0, 5.0, 100)
        g2 = SpectralGrid.uniform(1.0, 5.0, 101)
        assert hash(g1) != hash(g2)

    @pytest.mark.level0
    def test_eq_non_grid_returns_not_implemented(self) -> None:
        g = SpectralGrid.uniform(1.0, 5.0, 10)
        result = g.__eq__("not a grid")
        assert result is NotImplemented

    @pytest.mark.level0
    def test_usable_as_dict_key(self) -> None:
        g1 = SpectralGrid.uniform(1.0, 5.0, 50)
        g2 = SpectralGrid.uniform(1.0, 5.0, 50)
        d: dict[SpectralGrid, str] = {g1: "value"}
        assert d[g2] == "value"


# ===========================================================================
# SpectralData tests
# ===========================================================================


class TestSpectralDataValidation:
    @pytest.mark.level0
    def test_wrong_length_values_raises(self) -> None:
        wl = np.linspace(1.0, 5.0, 100)
        with pytest.raises(ValueError, match="length mismatch"):
            SpectralData(
                name="bad",
                wavelength_um=wl,
                values=np.ones(50),
                unit="W/m²/sr/µm",
                source="test",
            )

    @pytest.mark.level0
    def test_non_ascending_wavelength_raises(self) -> None:
        with pytest.raises(ValueError, match="strictly ascending"):
            SpectralData(
                name="bad",
                wavelength_um=np.array([1.0, 3.0, 2.0, 4.0]),
                values=np.ones(4),
                unit="W/m²/sr/µm",
                source="test",
            )


class TestSpectralDataIntegrate:
    @pytest.mark.level0
    def test_integrate_constant(self) -> None:
        """∫c dλ = c*(λ_max - λ_min).

        Analytical value: 2.0 * (5.0 - 1.0) = 8.0 W/m²/sr
        """
        n = 1000
        wl = np.linspace(1.0, 5.0, n)
        sd = SpectralData(
            name="constant",
            wavelength_um=wl,
            values=np.full(n, 2.0),
            unit="W/m²/sr/µm",
            source="test",
        )
        result = sd.integrate()
        analytical = 2.0 * (5.0 - 1.0)  # 8.0
        assert result == pytest.approx(analytical, abs=1e-10)

    @pytest.mark.level0
    def test_integrate_linear(self) -> None:
        """∫(a + b*λ) dλ = a*(λ_max - λ_min) + b*(λ_max² - λ_min²)/2.

        a=1.0, b=0.5, λ ∈ [1, 5]:
        Analytical: 1.0*4.0 + 0.5*(25 - 1)/2 = 4.0 + 6.0 = 10.0
        """
        n = 1000
        wl = np.linspace(1.0, 5.0, n)
        a, b = 1.0, 0.5
        sd = SpectralData(
            name="linear",
            wavelength_um=wl,
            values=a + b * wl,
            unit="W/m²/sr/µm",
            source="test",
        )
        result = sd.integrate()
        analytical = a * (5.0 - 1.0) + b * (5.0**2 - 1.0**2) / 2.0  # 10.0
        assert result == pytest.approx(analytical, abs=1e-10)

    @pytest.mark.level0
    def test_integrate_gaussian(self) -> None:
        """∫exp(-(λ-λ₀)²/(2σ²)) dλ ≈ σ*sqrt(2π) when domain >> σ.

        λ₀=3.0, σ=0.1, λ ∈ [1.0, 5.0], n=10000.
        Analytical: 0.1 * sqrt(2π) ≈ 0.25066283
        """
        n = 10_000
        lam0, sigma = 3.0, 0.1
        wl = np.linspace(1.0, 5.0, n)
        sd = SpectralData(
            name="gaussian",
            wavelength_um=wl,
            values=np.exp(-((wl - lam0) ** 2) / (2 * sigma**2)),
            unit="dimensionless",
            source="test",
        )
        result = sd.integrate()
        analytical = sigma * math.sqrt(2 * math.pi)  # 0.25066283...
        assert result == pytest.approx(analytical, rel=1e-4)


class TestSpectralDataResample:
    @pytest.mark.level0
    def test_resample_linear_function(self) -> None:
        """Resample a linear function from fine grid to coarse grid.

        The integrated result on the coarse grid should be close to analytical.
        f(λ) = 1 + 0.5*λ, λ ∈ [1, 5].
        Analytical integral = 10.0
        """
        wl_fine = np.linspace(1.0, 5.0, 2000)
        a, b = 1.0, 0.5
        sd_fine = SpectralData(
            name="linear_fine",
            wavelength_um=wl_fine,
            values=a + b * wl_fine,
            unit="W/m²/sr/µm",
            source="test",
        )
        coarse_grid = SpectralGrid.uniform(1.0, 5.0, 50)
        sd_coarse = sd_fine.resample(coarse_grid)

        assert len(sd_coarse.wavelength_um) == 50
        result = sd_coarse.integrate()
        analytical = 10.0
        # Coarse grid with linear interpolation of a linear function — should be exact
        assert result == pytest.approx(analytical, rel=1e-4)

    @pytest.mark.level0
    def test_resample_out_of_range_raises(self) -> None:
        sd = _make_sd(lam_min=2.0, lam_max=4.0, n=100)
        target = SpectralGrid.uniform(1.0, 5.0, 50)  # outside [2, 4]
        with pytest.raises(ValueError, match="extends outside"):
            sd.resample(target)

    @pytest.mark.level0
    def test_resample_out_of_range_low_raises(self) -> None:
        sd = _make_sd(lam_min=2.0, lam_max=4.0, n=100)
        target = SpectralGrid.uniform(1.0, 4.0, 50)  # low end outside
        with pytest.raises(ValueError, match="extends outside"):
            sd.resample(target)

    @pytest.mark.level0
    def test_resample_out_of_range_high_raises(self) -> None:
        sd = _make_sd(lam_min=2.0, lam_max=4.0, n=100)
        target = SpectralGrid.uniform(2.0, 5.0, 50)  # high end outside
        with pytest.raises(ValueError, match="extends outside"):
            sd.resample(target)

    @pytest.mark.level0
    def test_resample_preserves_name_unit_source(self) -> None:
        sd = _make_sd(name="mydata", lam_min=1.0, lam_max=5.0, n=200)
        target = SpectralGrid.uniform(2.0, 4.0, 20)
        sd2 = sd.resample(target)
        assert sd2.name == "mydata"
        assert sd2.unit == sd.unit
        assert sd2.source == sd.source


class TestSpectralDataArithmetic:
    @pytest.mark.level0
    def test_add_spectraldata(self) -> None:
        wl = np.linspace(1.0, 5.0, 100)
        a = SpectralData("a", wl, np.ones(100) * 3.0, "W/m²/sr/µm", "test")
        b = SpectralData("b", wl, np.ones(100) * 2.0, "W/m²/sr/µm", "test")
        c = a + b
        np.testing.assert_array_almost_equal(c.values, np.ones(100) * 5.0)
        assert "a" in c.name
        assert "b" in c.name

    @pytest.mark.level0
    def test_sub_spectraldata(self) -> None:
        wl = np.linspace(1.0, 5.0, 100)
        a = SpectralData("a", wl, np.ones(100) * 5.0, "W/m²/sr/µm", "test")
        b = SpectralData("b", wl, np.ones(100) * 2.0, "W/m²/sr/µm", "test")
        c = a - b
        np.testing.assert_array_almost_equal(c.values, np.ones(100) * 3.0)

    @pytest.mark.level0
    def test_mul_scalar(self) -> None:
        wl = np.linspace(1.0, 5.0, 100)
        a = SpectralData("a", wl, np.ones(100) * 3.0, "W/m²/sr/µm", "test")
        c = a * 2.0
        np.testing.assert_array_almost_equal(c.values, np.ones(100) * 6.0)

    @pytest.mark.level0
    def test_rmul_scalar(self) -> None:
        wl = np.linspace(1.0, 5.0, 100)
        a = SpectralData("a", wl, np.ones(100) * 3.0, "W/m²/sr/µm", "test")
        c = 2.0 * a
        np.testing.assert_array_almost_equal(c.values, np.ones(100) * 6.0)

    @pytest.mark.level0
    def test_div_scalar(self) -> None:
        wl = np.linspace(1.0, 5.0, 100)
        a = SpectralData("a", wl, np.ones(100) * 6.0, "W/m²/sr/µm", "test")
        c = a / 2.0
        np.testing.assert_array_almost_equal(c.values, np.ones(100) * 3.0)

    @pytest.mark.level0
    def test_add_different_grids_raises(self) -> None:
        wl1 = np.linspace(1.0, 5.0, 100)
        wl2 = np.linspace(1.0, 5.0, 101)
        a = SpectralData("a", wl1, np.ones(100), "W/m²/sr/µm", "test")
        b = SpectralData("b", wl2, np.ones(101), "W/m²/sr/µm", "test")
        with pytest.raises(ValueError, match="identical wavelength grids"):
            _ = a + b

    @pytest.mark.level0
    def test_mul_different_grids_raises(self) -> None:
        wl1 = np.linspace(1.0, 5.0, 100)
        wl2 = np.linspace(2.0, 5.0, 100)
        a = SpectralData("a", wl1, np.ones(100), "W/m²/sr/µm", "test")
        b = SpectralData("b", wl2, np.ones(100), "W/m²/sr/µm", "test")
        with pytest.raises(ValueError, match="identical wavelength grids"):
            _ = a * b


class TestSpectralDataSerialization:
    @pytest.mark.level0
    def test_round_trip_all_fields(self) -> None:
        wl = np.linspace(0.5, 14.0, 137)
        values = np.random.default_rng(42).random(137)
        sd = SpectralData(
            name="qe_model",
            wavelength_um=wl,
            values=values,
            unit="dimensionless",
            source="analytic",
            source_parameters={"T": 300.0, "band": "MWIR"},
        )
        d = sd.to_dict()
        sd2 = SpectralData.from_dict(d)

        assert sd2.name == sd.name
        assert sd2.unit == sd.unit
        assert sd2.source == sd.source
        assert sd2.source_parameters == sd.source_parameters
        np.testing.assert_array_equal(sd2.wavelength_um, sd.wavelength_um)
        np.testing.assert_array_equal(sd2.values, sd.values)

    @pytest.mark.level0
    def test_round_trip_machine_precision(self) -> None:
        wl = np.linspace(1.0, 5.0, 1000)
        values = np.linspace(0.0, 1.0, 1000)
        sd = SpectralData("x", wl, values, "W/m²/sr/µm", "test")
        sd2 = SpectralData.from_dict(sd.to_dict())
        np.testing.assert_array_equal(sd2.wavelength_um, sd.wavelength_um)
        np.testing.assert_array_equal(sd2.values, sd.values)


class TestSpectralDataGrid:
    @pytest.mark.level0
    def test_grid_property(self) -> None:
        wl = np.linspace(1.0, 5.0, 100)
        sd = SpectralData("a", wl, np.ones(100), "W/m²/sr/µm", "test")
        grid = sd.grid
        assert isinstance(grid, SpectralGrid)
        np.testing.assert_array_equal(grid.wavelengths_um, wl)


class TestSpectralDataPlot:
    @pytest.mark.level0
    def test_plot_does_not_raise(self) -> None:
        pytest.importorskip("matplotlib")
        import matplotlib

        matplotlib.use("Agg")  # non-interactive backend for CI
        sd = _make_sd()
        ax = sd.plot()
        assert ax is not None

    @pytest.mark.level0
    def test_plot_with_existing_ax(self) -> None:
        plt = pytest.importorskip("matplotlib.pyplot")
        import matplotlib

        matplotlib.use("Agg")
        _, ax = plt.subplots()
        sd = _make_sd()
        returned_ax = sd.plot(ax=ax)
        assert returned_ax is ax


# ===========================================================================
# SpectralDataStore tests
# ===========================================================================


class TestSpectralDataStore:
    @pytest.mark.level0
    def test_basic_add_get(self) -> None:
        store = SpectralDataStore(np.linspace(1.0, 5.0, 100))
        sd = _make_sd()
        store.add(sd)
        assert store.has("test")
        arr = store.get("test")
        assert arr.shape == (100,)
        assert store.names() == ["test"]

    @pytest.mark.level0
    def test_duplicate_add_raises(self) -> None:
        store = SpectralDataStore(np.linspace(1.0, 5.0, 100))
        sd = _make_sd()
        store.add(sd)
        with pytest.raises(ValueError, match="already in store"):
            store.add(sd)

    @pytest.mark.level0
    def test_get_unknown_raises(self) -> None:
        store = SpectralDataStore(np.linspace(1.0, 5.0, 100))
        with pytest.raises(KeyError, match="not in store"):
            store.get("nonexistent")

    @pytest.mark.level0
    def test_accepts_spectral_grid(self) -> None:
        grid = SpectralGrid.uniform(1.0, 5.0, 100)
        store = SpectralDataStore(grid)
        sd = _make_sd()
        store.add(sd)
        assert store.has("test")

    @pytest.mark.level0
    def test_has_returns_false_before_add(self) -> None:
        store = SpectralDataStore(np.linspace(1.0, 5.0, 100))
        assert not store.has("test")

    @pytest.mark.level0
    def test_full_coverage_curve_is_quiet(self, caplog) -> None:  # type: ignore[no-untyped-def]
        """CU-085 #3: a curve covering the grid warns/logs nothing."""
        import logging

        store = SpectralDataStore(np.linspace(2.0, 4.0, 100))
        with warnings.catch_warnings(), caplog.at_level(logging.DEBUG, "radiant.core.spectral"):
            warnings.simplefilter("error", UserWarning)  # any warning would raise
            store.add(_make_sd("full", lam_min=1.0, lam_max=5.0))
        assert not any("extrapolated" in r.message for r in caplog.records)

    @pytest.mark.level0
    def test_near_edge_extrapolation_is_debug_not_warning(self, caplog) -> None:  # type: ignore[no-untyped-def]
        """A curve stopping just short of the band (< 20% of grid) stays a quiet debug log."""
        import logging

        # Grid [2, 4]; curve [2.05, 4] leaves ~2.5% of the grid extrapolated on the low edge.
        store = SpectralDataStore(np.linspace(2.0, 4.0, 100))
        with warnings.catch_warnings(), caplog.at_level(logging.DEBUG, "radiant.core.spectral"):
            warnings.simplefilter("error", UserWarning)  # a UserWarning would raise
            store.add(_make_sd("near_edge", lam_min=2.05, lam_max=4.0))
        assert any("constant-extrapolated" in r.message for r in caplog.records)

    @pytest.mark.level0
    def test_gross_extrapolation_warns(self) -> None:
        """A curve covering < 80% of the band (> 20% extrapolated) raises a UserWarning."""
        # Grid [2, 4]; curve [3.0, 4.0] → the lower half (~50%) is constant-extrapolated.
        store = SpectralDataStore(np.linspace(2.0, 4.0, 100))
        with pytest.warns(UserWarning, match="constant-extrapolated"):
            store.add(_make_sd("gross", lam_min=3.0, lam_max=4.0))

    @pytest.mark.level0
    def test_names_empty(self) -> None:
        store = SpectralDataStore(np.linspace(1.0, 5.0, 100))
        assert store.names() == []

    @pytest.mark.level0
    def test_get_metadata(self) -> None:
        store = SpectralDataStore(np.linspace(1.0, 5.0, 100))
        sd = _make_sd(name="qe")
        store.add(sd)
        meta = store.get_metadata("qe")
        assert meta.name == "qe"
