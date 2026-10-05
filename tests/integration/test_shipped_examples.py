"""Truth bar for the bundled worked examples (Gap 126).

Every example that ships in the wheel must load through its documented door
and evaluate warning-clean. Values are deliberately NOT pinned: the examples
are curated snapshots of their source scenarios and may drift numerically
without harm — what must never regress is that a new user's first open works.
"""

from __future__ import annotations

import warnings

import pytest

from radiant.api import Sensor
from radiant.api.config_set import ConfigurationSet
from radiant.api.mission_templates import discover_examples

_EXAMPLES = discover_examples()


def test_the_bundled_set_is_the_curated_seven() -> None:
    """Six mission snapshots plus one syntax reference.

    ``transmission_doors`` is different in kind from the other six: it is not a
    curated snapshot of a scenario but a deliberately unrealistic train that uses
    every way of defining optical transmission at once, so an analyst can read the
    syntax side by side and diff their own config against it. It meets the same bar
    as the rest — it loads through its documented door and evaluates warning-clean.
    """
    assert len(_EXAMPLES) == 7
    assert "transmission_doors" in {info.path.stem for info in _EXAMPLES}


@pytest.mark.parametrize("info", _EXAMPLES, ids=lambda i: i.path.stem)
def test_example_loads_and_evaluates_warning_clean(info) -> None:  # type: ignore[no-untyped-def]
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        if "landsat" in info.path.name:
            cs = ConfigurationSet.load(info.path)
            result = cs.sensor_for(cs.active).evaluate()
        else:
            result = Sensor.load(info.path).evaluate()
    user_warnings = [w for w in caught if issubclass(w.category, UserWarning)]
    assert not user_warnings, [str(w.message) for w in user_warnings]
    assert result.metrics["snr"] > 0.0


@pytest.mark.parametrize("info", _EXAMPLES, ids=lambda i: i.path.stem)
def test_example_metadata_is_complete(info) -> None:  # type: ignore[no-untyped-def]
    assert info.name and info.blurb and info.specs
    assert info.tune_next, f"{info.path.name} names no tune-next parameters"
