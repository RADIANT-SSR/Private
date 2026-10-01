"""The silently-zero near-field advisory, end to end (CU-380).

Lives here rather than in ``optics/tests/`` because it drives the chain through
the public ``Sensor``: a stage test may not import the top-level API, since
``radiant`` reaches ``radiant.api`` / ``radiant.io`` and the
physics-stages-import-only-core contract is machine-enforced by import-linter.
The predicate's own truth table is unit-tested next to the module, in
``src/radiant/optics/tests/test_nearfield_advisory.py``.
"""

from __future__ import annotations

import math
import warnings

import pytest

from radiant import Sensor


class TestNearfieldAdvisoryEndToEnd:
    def test_a_thermal_scalar_config_warns(self) -> None:
        """The exact mechanism that shipped silently through v0.2.0 and v0.3.0.

        The shipped examples now set ``nearfield_enabled: 0`` explicitly, so the
        case is reconstructed here by turning the term back on — which is what a
        user copying the file and declaring a scalar transmission would get.
        """
        sensor = Sensor.from_yaml("examples/mwir_leo_minimal.yaml")
        sensor.set("optics.nearfield_enabled", 1)
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            sensor.evaluate()
        messages = [str(w.message) for w in caught]
        assert any("Warm-optics irradiance is therefore identically zero" in m for m in messages)

    def test_shipped_examples_are_silent(self) -> None:
        """Both examples state the omission explicitly, so neither warns."""
        for path in ("examples/mwir_leo_minimal.yaml", "examples/ground_truth_mwir.yaml"):
            sensor = Sensor.from_yaml(path)
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always")
                sensor.evaluate()
            messages = [str(w.message) for w in caught]
            assert not any("identically zero" in m for m in messages), path

    def test_declaring_a_warm_train_silences_it_and_moves_the_answer(self) -> None:
        reflectance = math.sqrt(0.70)
        sensor = Sensor.from_yaml("examples/mwir_leo_minimal.yaml")
        sensor.set("optics.nearfield_enabled", 1)
        sensor.set_optical_elements(
            [
                {
                    "name": name,
                    "transfer_mode": "REFLECTIVE",
                    "kind": "MIRROR",
                    "reflectance": reflectance,
                    "temperature_K": 290.0,
                }
                for name in ("primary", "secondary")
            ]
        )
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            result = sensor.evaluate()
        messages = [str(w.message) for w in caught]
        assert not any("identically zero" in m for m in messages)
        # And the term it was omitting is large: 37 % of signal here.
        detector = result.stage_outputs["detector"]
        assert detector["nearfield_e"] == pytest.approx(4.652e5, rel=1e-2)
        assert detector["nearfield_e"] / detector["signal_e"] == pytest.approx(0.368, rel=5e-2)
