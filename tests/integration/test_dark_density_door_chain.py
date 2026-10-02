"""The dark-current-density door, end to end (Gap 135).

Lives here rather than in ``detector/tests/`` because it drives the chain
through the public ``Sensor``: a stage test may not import the top-level API,
since ``radiant`` reaches ``radiant.api`` / ``radiant.io`` and the
physics-stages-import-only-core contract is machine-enforced by import-linter.
The conversion itself, and the ``A/m2`` unit-registry entry, are unit-tested
next to the module in
``src/radiant/detector/tests/test_dark_density_door.py``.
"""

from __future__ import annotations

import math

import pytest

from radiant import RadiantError, Sensor
from radiant.core.parameters import ParameterBoundsError
from radiant.detector.dark_current import dark_rate_e_per_s_from_density

_PITCH_M = 20e-6
_AREA_M2 = _PITCH_M**2


class TestTheDoor:
    """The parameter, end to end through the public surface."""

    @staticmethod
    def _sensor(*, release_rate: bool = True):  # type: ignore[no-untyped-def]
        """The example at a 20 um pitch, with the rate door released.

        ``examples/mwir_leo_minimal.yaml`` declares ``dark_rate_e_per_s``
        explicitly, so a density entered on top of it is genuinely
        over-specified — RADIANT rejects that, and `release_rate` is what a real
        user does instead: clear the door they did not mean. The well is widened
        because a routine LWIR density over a 5 ms frame legitimately saturates
        the example's 2 Me- well, which is a separate (and correct) behaviour
        this door's tests should not be entangled with.
        """
        s = Sensor.from_yaml("examples/mwir_leo_minimal.yaml")
        s.set("detector.pixel_pitch_x_um", 20.0)
        s.set("detector.pixel_pitch_y_um", 20.0)
        s.set("readout.full_well_capacity_e", 1e11)
        s.set("readout.gain_e_per_dn", 1e6)
        s.set("readout.adc_bits", 24)
        if release_rate:
            s.reset("detector.dark_rate_e_per_s")
        return s

    def test_density_reproduces_the_equivalent_explicit_rate(self) -> None:
        """The two doors onto the same quantity must agree exactly."""
        rate = dark_rate_e_per_s_from_density(1.0e-4, _AREA_M2)

        by_rate = self._sensor(release_rate=False)
        by_rate.set("detector.dark_rate_e_per_s", rate)
        by_density = self._sensor()
        by_density.set("detector.dark_current_density_a_per_cm2", 1.0e-4)

        a = by_rate.evaluate().stage_outputs["detector"]["dark_e"]
        b = by_density.evaluate().stage_outputs["detector"]["dark_e"]
        assert b == pytest.approx(a, rel=1e-12)

    def test_the_a_per_m2_spelling_gives_the_same_answer(self) -> None:
        """Entering 1 A/m^2 must equal entering 1e-4 A/cm^2."""
        in_cm2 = self._sensor()
        in_cm2.set("detector.dark_current_density_a_per_cm2", 1.0e-4)
        in_m2 = self._sensor()
        in_m2.set("detector.dark_current_density_a_per_cm2", 1.0, unit="A/m2")
        assert in_m2.get("detector.dark_current_density_a_per_cm2") == pytest.approx(
            1.0e-4, rel=1e-12
        )
        a = in_cm2.evaluate().stage_outputs["detector"]["dark_e"]
        b = in_m2.evaluate().stage_outputs["detector"]["dark_e"]
        assert b == pytest.approx(a, rel=1e-12)

    def test_the_converted_rate_is_published_for_inspection(self) -> None:
        """Rule 16 / Gap 134: a value RADIANT derived must be inspectable."""
        s = self._sensor()
        s.set("detector.dark_current_density_a_per_cm2", 1.0e-4)
        out = s.evaluate().stage_outputs["detector"]
        assert out["dark_rate_e_per_s"] == pytest.approx(
            dark_rate_e_per_s_from_density(1.0e-4, _AREA_M2), rel=1e-9
        )

    def test_default_is_unset_and_changes_nothing(self) -> None:
        """The example declares a rate and no density, so nothing moves."""
        plain = Sensor.from_yaml("examples/mwir_leo_minimal.yaml")
        assert plain.get("detector.dark_current_density_a_per_cm2") == 0.0
        assert plain.evaluate().stage_outputs["detector"]["dark_e"] == pytest.approx(0.5, rel=1e-12)

    def test_both_doors_set_is_rejected_as_over_specified(self) -> None:
        s = self._sensor(release_rate=False)
        s.set("detector.dark_rate_e_per_s", 1000.0)
        s.set("detector.dark_current_density_a_per_cm2", 1.0e-4)
        with pytest.raises(RadiantError, match="over-specified"):
            s.evaluate()

    def test_density_under_a_predictive_model_is_rejected(self) -> None:
        """A measured density contradicts a derived law, exactly as a rate does."""
        s = self._sensor()
        s.set("detector.dark_model", "rule07")
        s.set("detector.dark_cutoff_um", 5.0)
        s.set("detector.dark_current_density_a_per_cm2", 1.0e-4)
        with pytest.raises(RadiantError, match="over-specified"):
            s.evaluate()

    def test_density_scales_with_arrhenius_like_a_rate(self) -> None:
        """The density is a measured value at the reference temperature."""
        s = self._sensor()
        s.set("detector.dark_current_density_a_per_cm2", 1.0e-4)
        s.set("detector.dark_activation_energy_eV", 0.5)
        s.set("detector.dark_reference_temperature_K", 77.0)
        s.set("detector.detector_temperature_K", 80.0)
        warm = s.evaluate().stage_outputs["detector"]["dark_e"]

        cold = self._sensor()
        cold.set("detector.dark_current_density_a_per_cm2", 1.0e-4)
        cold.set("detector.dark_activation_energy_eV", 0.5)
        cold.set("detector.dark_reference_temperature_K", 77.0)
        cold.set("detector.detector_temperature_K", 77.0)
        assert warm > cold.evaluate().stage_outputs["detector"]["dark_e"]

    def test_negative_density_is_rejected(self) -> None:
        s = self._sensor()
        s.set("detector.dark_current_density_a_per_cm2", -1.0)
        with pytest.raises(ParameterBoundsError):
            s.get("detector.dark_current_density_a_per_cm2")

    def test_a_routine_lwir_density_is_expressible(self) -> None:
        """The CU-382 case, now stated in its native unit."""
        s = self._sensor()
        s.set("detector.dark_current_density_a_per_cm2", 1.0, unit="A/m2")
        rate = s.evaluate().stage_outputs["detector"]["dark_rate_e_per_s"]
        assert rate == pytest.approx(2.4969e9, rel=1e-3)
        assert math.isfinite(rate)
