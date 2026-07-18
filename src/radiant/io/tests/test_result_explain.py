"""Tests for ChainResult.inspect() / explain_noise() (Gap 87)."""

from __future__ import annotations

import warnings
from pathlib import Path

import pytest

from radiant.api import Sensor
from radiant.io.results import NoiseExplanation

_REPO = Path(__file__).resolve()
while not (_REPO / "pyproject.toml").exists():
    _REPO = _REPO.parent
_EXAMPLE = _REPO / "examples" / "mwir_leo_minimal.yaml"


@pytest.fixture(scope="module")
def result():  # type: ignore[no-untyped-def]
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return Sensor.from_yaml(_EXAMPLE).evaluate()


class TestInspect:
    def test_full_tree_matches_module_function(self, result) -> None:  # type: ignore[no-untyped-def]
        from radiant.api.inspect import inspect_result

        assert result.inspect() == inspect_result(result)
        assert "metrics" in result.inspect()

    def test_stage_scoped(self, result) -> None:  # type: ignore[no-untyped-def]
        scoped = result.inspect("optics")
        assert "optics" in scoped
        assert len(scoped) < len(result.inspect())


class TestExplainNoise:
    def test_fields_match_term_and_shares_sum_to_one(self, result) -> None:  # type: ignore[no-untyped-def]
        shares = 0.0
        for term in result.noise_terms:
            exp = result.explain_noise(term.name)
            assert isinstance(exp, NoiseExplanation)
            assert exp.value_e == term.value_e
            assert exp.origin_frame == term.origin_frame
            assert exp.physical_basis == term.physical_basis
            assert exp.contributes_to == tuple(term.contributes_to)
            shares += exp.share_of_variance
        assert shares == pytest.approx(1.0, abs=1e-12)

    def test_description_carries_units_and_share(self, result) -> None:  # type: ignore[no-untyped-def]
        exp = result.explain_noise(result.noise_terms[0].name)
        assert "e- RMS" in exp.description  # R-UNITS
        assert "share of variance" in exp.description

    def test_unknown_term_raises_naming_available(self, result) -> None:  # type: ignore[no-untyped-def]
        with pytest.raises(KeyError, match="available"):
            result.explain_noise("flux_capacitor")
