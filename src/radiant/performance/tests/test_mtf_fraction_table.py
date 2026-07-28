"""Level-0 tests for the MTF fraction table (walkthrough item 10).

The expected values are hand-constructed analytic curves, not values taken from
other RADIANT code (Rule 18): a linear ramp whose value at any frequency is
known by inspection, and a constant curve.
"""

from __future__ import annotations

import numpy as np
import pytest

from radiant.performance.errors import PerformanceValidationError
from radiant.performance.mtf_fraction_table import (
    DEFAULT_FRACTIONS,
    compute_mtf_fraction_table,
)

_NYQUIST = 40.0  # cycles/mrad


class _FakeBudget:
    """A budget carrying analytic curves whose sampled values are known by hand."""

    def __init__(self, freq: np.ndarray, per_term: dict, system_x, system_y) -> None:
        self.freq_cycles_per_mrad = freq
        self.per_term = per_term
        self.system_mtf_x = system_x
        self.system_mtf_y = system_y


def _budget() -> _FakeBudget:
    # Frequency 0 -> 80 cycles/mrad, so Nyquist (40) sits mid-axis and 1.0N is in range.
    freq = np.linspace(0.0, 80.0, 81)
    # A ramp falling linearly 1 -> 0 across 0 -> 80: value at f is 1 - f/80.
    ramp = 1.0 - freq / 80.0
    flat = np.ones_like(freq)
    return _FakeBudget(
        freq,
        {"mtf_ramp_x": ramp, "mtf_flat_x": flat, "mtf_ramp_y": ramp * 0.5 + 0.5},
        system_x=ramp,
        system_y=flat,
    )


class TestSampledValues:
    """A linear ramp's value at each fraction is arithmetic, not a fitted number."""

    @pytest.mark.parametrize(
        ("fraction_index", "expected"),
        # target = fraction x 40; ramp = 1 - target/80  ->  0.875, 0.75, 0.625, 0.5
        [(0, 0.875), (1, 0.75), (2, 0.625), (3, 0.5)],
    )
    def test_ramp_values(self, fraction_index: int, expected: float) -> None:
        table = compute_mtf_fraction_table(_budget(), _NYQUIST, "x")
        assert table.per_term["mtf_ramp"][fraction_index] == pytest.approx(expected, abs=1e-12)

    def test_flat_curve_is_unity_everywhere(self) -> None:
        table = compute_mtf_fraction_table(_budget(), _NYQUIST, "x")
        assert all(v == pytest.approx(1.0, abs=1e-12) for v in table.per_term["mtf_flat"])

    def test_system_row_is_sampled_too(self) -> None:
        table = compute_mtf_fraction_table(_budget(), _NYQUIST, "x")
        assert table.system[3] == pytest.approx(0.5, abs=1e-12)


class TestAxisSelection:
    def test_only_the_requested_axis_is_sampled(self) -> None:
        """An ``_x`` request must not pick up the ``_y`` contributor."""
        table = compute_mtf_fraction_table(_budget(), _NYQUIST, "x")
        assert set(table.term_names()) == {"mtf_ramp", "mtf_flat"}

    def test_y_axis_reads_its_own_curves(self) -> None:
        table = compute_mtf_fraction_table(_budget(), _NYQUIST, "y")
        assert set(table.term_names()) == {"mtf_ramp"}
        # y ramp = 0.5*ramp + 0.5; at 1.0N ramp is 0.5 -> 0.75
        assert table.per_term["mtf_ramp"][3] == pytest.approx(0.75, abs=1e-12)

    def test_suffix_is_stripped_from_the_name(self) -> None:
        table = compute_mtf_fraction_table(_budget(), _NYQUIST, "x")
        assert "mtf_ramp_x" not in table.per_term


class TestOutOfRangeIsNoneNotExtrapolated:
    def test_fraction_beyond_the_axis_yields_none(self) -> None:
        """4.0 x Nyquist = 160 cycles/mrad, past the 80 the budget computed."""
        table = compute_mtf_fraction_table(_budget(), _NYQUIST, "x", fractions=(1.0, 4.0))
        assert table.per_term["mtf_ramp"][0] is not None
        assert table.per_term["mtf_ramp"][1] is None

    def test_system_row_also_reports_none(self) -> None:
        table = compute_mtf_fraction_table(_budget(), _NYQUIST, "x", fractions=(4.0,))
        assert table.system == (None,)


class TestDefaults:
    def test_default_fractions_are_the_owner_requested_ladder(self) -> None:
        assert DEFAULT_FRACTIONS == (0.25, 0.5, 0.75, 1.0)

    def test_fractions_are_carried_on_the_result(self) -> None:
        table = compute_mtf_fraction_table(_budget(), _NYQUIST, "x")
        assert table.fractions == DEFAULT_FRACTIONS
        assert table.nyquist_cycles_per_mrad == pytest.approx(_NYQUIST, rel=1e-12)


class TestValidation:
    def test_bad_axis_raises(self) -> None:
        with pytest.raises(PerformanceValidationError, match="axis must be"):
            compute_mtf_fraction_table(_budget(), _NYQUIST, "z")

    def test_non_positive_nyquist_raises(self) -> None:
        with pytest.raises(PerformanceValidationError, match="must be > 0"):
            compute_mtf_fraction_table(_budget(), 0.0, "x")

    def test_non_positive_fraction_raises(self) -> None:
        with pytest.raises(PerformanceValidationError, match="fraction must be > 0"):
            compute_mtf_fraction_table(_budget(), _NYQUIST, "x", fractions=(0.0, 1.0))

    def test_missing_frequency_axis_raises(self) -> None:
        empty = _FakeBudget(np.empty(0), {}, None, None)
        with pytest.raises(PerformanceValidationError, match="no frequency axis"):
            compute_mtf_fraction_table(empty, _NYQUIST, "x")
