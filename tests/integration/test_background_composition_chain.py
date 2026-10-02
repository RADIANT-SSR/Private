"""The background-composition breakdown, end to end (Gap 132).

Lives here rather than in ``performance/tests/`` because it drives the chain
through the public ``Sensor``: a stage test may not import the top-level API.
The arithmetic and edge behaviours are unit-tested next to the module.

What these pin is the *diagnostic claim* — that the breakdown makes a
silently-zero dominant term visible. That is the whole justification for the
gap, so it deserves a test rather than a docstring.
"""

from __future__ import annotations

import math
import warnings

import pytest

from radiant import Sensor

_EXAMPLE = "examples/mwir_leo_minimal.yaml"


def _composition(sensor: Sensor):  # type: ignore[no-untyped-def]
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        result = sensor.evaluate()
    return result.stage_outputs["performance"]["background_composition"]


class TestItReachesTheOutput:
    def test_every_run_publishes_a_composition(self) -> None:
        c = _composition(Sensor.from_yaml(_EXAMPLE))
        assert c.total_e >= 0.0
        assert set(c.terms) == {"nearfield", "scene", "dark", "stray", "glow"}

    def test_shares_sum_to_one_on_a_real_chain(self) -> None:
        c = _composition(Sensor.load("src/radiant/data/templates/geo_lwir_staring.yaml"))
        assert sum(c.shares.values()) == pytest.approx(1.0, rel=1e-12)

    def test_the_total_matches_the_detector_terms_it_views(self) -> None:
        """It is a view, not a second opinion — so it must reconcile exactly."""
        sensor = Sensor.load("src/radiant/data/templates/ground_to_air_mwir_detection.yaml")
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            result = sensor.evaluate()
        det = result.stage_outputs["detector"]
        c = result.stage_outputs["performance"]["background_composition"]
        expected = math.fsum(
            (
                det["nearfield_e"],
                det["background_e"],
                det["dark_e"],
                det["stray_e"],
                det["glow_e"],
            )
        )
        assert c.total_e == pytest.approx(expected, rel=1e-12)


class TestTheCu380Reading:
    """The case the gap exists for: a thermal term that is identically zero."""

    def test_a_thermal_scalar_mode_config_reports_nearfield_as_zero(self) -> None:
        sensor = Sensor.from_yaml(_EXAMPLE)
        sensor.set("optics.nearfield_enabled", 1)  # the pre-CU-380 posture
        c = _composition(sensor)
        assert c.terms["nearfield"] == 0.0
        assert "nearfield" in c.zero_terms()

    def test_a_declared_warm_train_makes_nearfield_dominant(self) -> None:
        """The same scene with real optics: warm optics takes over, as the
        review said it usually does in a thermal band."""
        sensor = Sensor.load("src/radiant/data/templates/geo_lwir_staring.yaml")
        c = _composition(sensor)
        assert c.dominant == "nearfield"
        assert c.share_pct("nearfield") > 90.0
        assert "nearfield" not in c.zero_terms()

    def test_a_cooled_point_source_design_is_split_between_optics_and_dark(self) -> None:
        """sda_space_to_space at its 150 K optics: background-limited, not
        optics-saturated — the regime CU-380's sweep chose it for."""
        c = _composition(Sensor.load("src/radiant/data/templates/sda_space_to_space.yaml"))
        assert c.dominant == "nearfield"
        assert 50.0 < c.share_pct("nearfield") < 95.0
        assert c.share_pct("dark") > 5.0
