"""Schema tests for the calibration stage (Gap 120 Phase 0, Category B).

Level 0: the plan §4 parameter surface — names, dtypes, units, defaults,
sentinels — and the boundary unit conversions (Rule 2: hour→s, %/hour→1/s,
e-/hour→e-/s, %→fraction) verified against hand-computed factors.
"""

from __future__ import annotations

import pytest

from radiant.calibration._schema import ALL_PARAMETERS
from radiant.core.parameters import (
    ParameterBoundsError,
    ParameterEnumError,
    ParameterSet,
)


def _params(**overrides: object) -> ParameterSet:
    """Calibration-only ParameterSet with optional dot-path overrides."""
    ps = ParameterSet(list(ALL_PARAMETERS))
    for name, value in overrides.items():
        ps.set(name.replace("__", "."), value)
    ps.resolve()
    return ps


class TestSchemaDefs:
    """The plan §4 parameter surface exists with the ratified shapes."""

    @pytest.fixture()
    def defs(self) -> dict[str, object]:
        return {p.name: p for p in ALL_PARAMETERS}

    def test_all_eleven_parameters_present(self, defs: dict[str, object]) -> None:
        assert set(defs.keys()) == {
            "calibration.scheme",
            "calibration.cal_temp_low_K",
            "calibration.cal_temp_high_K",
            "calibration.nonlinearity_pct",
            "calibration.time_since_cal_s",
            "calibration.gain_drift_frac_per_s",
            "calibration.offset_drift_e_per_s",
            "calibration.source_temp_uncertainty_K",
            "calibration.source_emissivity_uncertainty",
            "calibration.source_emissivity",
            "calibration.gain_uncertainty_pct",
        }

    def test_scheme_enum_and_default(self) -> None:
        (scheme,) = [p for p in ALL_PARAMETERS if p.name == "calibration.scheme"]
        assert scheme.enum_values == ("none", "one_point", "two_point")
        assert scheme.default == "none"

    def test_defaults_are_the_none_limit(self) -> None:
        """Every default is the model-off value (plan §16 regression contract)."""
        ps = _params()
        assert ps.get("calibration.scheme") == "none"
        for name in (
            "calibration.cal_temp_low_K",
            "calibration.cal_temp_high_K",
            "calibration.nonlinearity_pct",
            "calibration.time_since_cal_s",
            "calibration.gain_drift_frac_per_s",
            "calibration.offset_drift_e_per_s",
            "calibration.source_temp_uncertainty_K",
            "calibration.source_emissivity_uncertainty",
            "calibration.gain_uncertainty_pct",
        ):
            assert ps.get(name) == 0.0, name
        assert ps.get("calibration.source_emissivity") == 1.0


class TestUnitConversions:
    """Rule 2 boundary conversions — hand-computed factors, exact."""

    def test_time_since_cal_hours_to_seconds(self) -> None:
        ps = _params(calibration__time_since_cal_s=2.0)  # input unit: hour
        assert ps.get("calibration.time_since_cal_s") == pytest.approx(7200.0, rel=1e-12)

    def test_gain_drift_pct_per_hour_to_frac_per_second(self) -> None:
        # 1 %/hour = 0.01 / 3600 s^-1 = 2.777...e-6 1/s
        ps = _params(calibration__gain_drift_frac_per_s=1.0)
        assert ps.get("calibration.gain_drift_frac_per_s") == pytest.approx(
            0.01 / 3600.0, rel=1e-12
        )

    def test_offset_drift_e_per_hour_to_e_per_second(self) -> None:
        ps = _params(calibration__offset_drift_e_per_s=3600.0)
        assert ps.get("calibration.offset_drift_e_per_s") == pytest.approx(1.0, rel=1e-12)

    def test_nonlinearity_percent_to_fraction(self) -> None:
        ps = _params(calibration__nonlinearity_pct=2.5)
        assert ps.get("calibration.nonlinearity_pct") == pytest.approx(0.025, rel=1e-12)

    def test_gain_uncertainty_percent_to_fraction(self) -> None:
        ps = _params(calibration__gain_uncertainty_pct=5.0)
        assert ps.get("calibration.gain_uncertainty_pct") == pytest.approx(0.05, rel=1e-12)


class TestFailureModes:
    """Category B failure-mode coverage: bounds, enums, wrong types."""

    def test_scheme_rejects_unknown_value(self) -> None:
        with pytest.raises(ParameterEnumError):
            _params(calibration__scheme="three_point")

    def test_negative_uncertainty_rejected(self) -> None:
        with pytest.raises(ParameterBoundsError):
            _params(calibration__source_temp_uncertainty_K=-1.0)

    def test_emissivity_above_one_rejected(self) -> None:
        with pytest.raises(ParameterBoundsError):
            _params(calibration__source_emissivity=1.2)

    def test_cal_temp_above_bound_rejected(self) -> None:
        with pytest.raises(ParameterBoundsError):
            _params(calibration__cal_temp_low_K=5000.0)

    def test_negative_time_since_cal_rejected(self) -> None:
        with pytest.raises(ParameterBoundsError):
            _params(calibration__time_since_cal_s=-1.0)


class TestSerializationRoundTrip:
    """Category B: values survive a set → resolve → read cycle unchanged."""

    def test_round_trip_all_values(self) -> None:
        ps = _params(
            calibration__scheme="two_point",
            calibration__cal_temp_low_K=290.0,
            calibration__cal_temp_high_K=310.0,
            calibration__nonlinearity_pct=1.0,
            calibration__time_since_cal_s=24.0,
            calibration__source_temp_uncertainty_K=0.5,
            calibration__source_emissivity=0.98,
        )
        assert ps.get("calibration.scheme") == "two_point"
        assert ps.get("calibration.cal_temp_low_K") == pytest.approx(290.0, rel=1e-12)
        assert ps.get("calibration.cal_temp_high_K") == pytest.approx(310.0, rel=1e-12)
        assert ps.get("calibration.time_since_cal_s") == pytest.approx(86400.0, rel=1e-12)
        assert ps.get("calibration.source_emissivity") == pytest.approx(0.98, rel=1e-12)
