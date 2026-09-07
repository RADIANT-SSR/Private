"""BiasTerm and ChainState.with_bias (Gap 120 Phase 0, ADR-0012).

The accuracy-budget accumulator: validation, immutability, and the
noise/bias type separation. Also pins the CALIBRATION_TERMS classification
invariants the sqrt(N)-exemption contract rests on.
"""

from __future__ import annotations

import numpy as np
import pytest

from radiant.core.chain import ChainState
from radiant.core.exceptions import CoreValidationError
from radiant.core.noise_budget import (
    ALL_NOISE_TERMS,
    CALIBRATION_TERMS,
    COUNTING_TERMS,
    SPATIAL_TERMS,
    TEMPORAL_TERMS,
)
from radiant.core.radiometry import BiasTerm


def _bias(value_frac: float = 0.016) -> BiasTerm:
    return BiasTerm(
        name="source_temp",
        value_frac=value_frac,
        origin="calibration.source_temp_uncertainty_K",
        physical_basis="Planck dL/dT at T_cal",
    )


def _state() -> ChainState:
    return ChainState(wavelength_um=np.linspace(8.0, 12.0, 5))


class TestBiasTermValidation:
    def test_valid_term_constructs(self) -> None:
        term = _bias()
        assert term.value_frac == pytest.approx(0.016, rel=1e-12)

    def test_zero_is_valid(self) -> None:
        assert _bias(0.0).value_frac == 0.0

    def test_negative_rejected(self) -> None:
        with pytest.raises(CoreValidationError, match="negative"):
            _bias(-0.01)

    def test_nan_rejected(self) -> None:
        with pytest.raises(CoreValidationError, match="not finite"):
            _bias(float("nan"))

    def test_inf_rejected(self) -> None:
        with pytest.raises(CoreValidationError, match="not finite"):
            _bias(float("inf"))

    def test_empty_origin_rejected(self) -> None:
        with pytest.raises(CoreValidationError, match="origin"):
            BiasTerm(name="gain", value_frac=0.01, origin="", physical_basis="scale")


class TestWithBias:
    def test_appends_and_returns_new_state(self) -> None:
        s0 = _state()
        s1 = s0.with_bias(_bias())
        assert s0.bias_terms == ()
        assert len(s1.bias_terms) == 1
        assert s1.bias_terms[0].name == "source_temp"

    def test_accumulates_in_order(self) -> None:
        s = (
            _state()
            .with_bias(_bias())
            .with_bias(
                BiasTerm(
                    name="gain",
                    value_frac=0.02,
                    origin="calibration.gain_uncertainty_pct",
                    physical_basis="radiance scale",
                )
            )
        )
        assert tuple(t.name for t in s.bias_terms) == ("source_temp", "gain")

    def test_default_state_has_no_bias_terms(self) -> None:
        assert _state().bias_terms == ()

    def test_bias_does_not_touch_noise(self) -> None:
        """The type separation: with_bias never changes noise_terms."""
        s = _state().with_bias(_bias())
        assert s.noise_terms == ()


class TestCalibrationTermClassification:
    """Invariants the plan §6 contract tests build on."""

    def test_calibration_terms_are_spatial(self) -> None:
        assert CALIBRATION_TERMS <= SPATIAL_TERMS

    def test_calibration_terms_in_all(self) -> None:
        assert CALIBRATION_TERMS <= ALL_NOISE_TERMS

    def test_calibration_disjoint_from_counting(self) -> None:
        assert frozenset() == CALIBRATION_TERMS & COUNTING_TERMS

    def test_calibration_terms_not_temporal(self) -> None:
        assert frozenset() == CALIBRATION_TERMS & TEMPORAL_TERMS

    def test_expected_member_names(self) -> None:
        assert {"nuc_residual", "gain_drift", "offset_drift"} == CALIBRATION_TERMS
