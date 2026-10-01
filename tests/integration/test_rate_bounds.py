"""Rate-parameter ceilings must admit real detectors (CU-382).

The old ceilings (dark 1e9, DSNU 1e6, glow 1e6) were each the *default's*
rationale — a room-temperature Si CCD — applied to the bound. A default
describes the typical part; a bound describes every expressible part. These
tests pin the physical cases the old ceilings excluded, so a future narrowing
has to argue with a number rather than a habit.

Bounds are enforced at resolve time through the public ``Sensor`` surface, so
that is the level these assert at — which also means the file lives under
``tests/integration/`` rather than ``detector/tests/``: a stage test may not
import the top-level API, because ``radiant`` reaches ``radiant.readout`` and
the detector-may-not-import-readout contract is machine-enforced.
"""

from __future__ import annotations

import math

import pytest

from radiant import Sensor
from radiant.core.constants import q
from radiant.core.parameters import ParameterBoundsError

# A routine LWIR figure: 1 A/m^2 = 1e-4 A/cm^2 dark-current density.
_DENSITY_A_PER_M2 = 1.0
_PITCH_M = 20e-6
_EXAMPLE = "examples/mwir_leo_minimal.yaml"


def _rate_from_density(density_a_per_m2: float, pitch_m: float) -> float:
    """Dark-current density [A/m^2] -> per-pixel generation rate [e-/s]."""
    return density_a_per_m2 * pitch_m**2 / q


@pytest.fixture
def sensor() -> Sensor:
    return Sensor.from_yaml(_EXAMPLE)


class TestDarkRateCeiling:
    def test_routine_lwir_density_exceeds_the_old_ceiling(self) -> None:
        """The case that motivated the CU: it must be above 1e9, or the test is moot."""
        rate = _rate_from_density(_DENSITY_A_PER_M2, _PITCH_M)
        assert rate == pytest.approx(2.4969e9, rel=1e-3)
        assert rate > 1e9  # the old ceiling

    def test_routine_lwir_density_is_expressible(self, sensor: Sensor) -> None:
        rate = _rate_from_density(_DENSITY_A_PER_M2, _PITCH_M)
        sensor.set("detector.dark_rate_e_per_s", rate)
        assert sensor.get("detector.dark_rate_e_per_s") == pytest.approx(rate, rel=1e-12)

    def test_large_pixel_hot_detector_is_expressible(self, sensor: Sensor) -> None:
        """50 um at 10 A/m^2 — the headroom the new ceiling is sized for."""
        rate = _rate_from_density(10.0, 50e-6)
        assert rate == pytest.approx(1.5604e11, rel=1e-3)
        assert rate < 1e12
        sensor.set("detector.dark_rate_e_per_s", rate)
        assert sensor.get("detector.dark_rate_e_per_s") == pytest.approx(rate, rel=1e-12)

    def test_ceiling_still_rejects_the_absurd(self, sensor: Sensor) -> None:
        """Raising a bound is not removing it. Bounds bite at resolve, not set()."""
        sensor.set("detector.dark_rate_e_per_s", 1e13)
        with pytest.raises(ParameterBoundsError):
            sensor.get("detector.dark_rate_e_per_s")

    def test_negative_still_rejected(self, sensor: Sensor) -> None:
        sensor.set("detector.dark_rate_e_per_s", -1.0)
        with pytest.raises(ParameterBoundsError):
            sensor.get("detector.dark_rate_e_per_s")


class TestCoupledDarkCeilings:
    """DSNU and glow had to move with dark, not separately."""

    def test_dsnu_tracks_the_dark_signal_it_is_a_fraction_of(self, sensor: Sensor) -> None:
        # Dark SIGNAL at the LWIR rate over a 10 ms frame, at 5 % non-uniformity:
        # 2.497e9 * 0.01 * 0.05 = 1.25e6 e- RMS, above the old 1e6 DSNU ceiling.
        dark_signal_e = _rate_from_density(_DENSITY_A_PER_M2, _PITCH_M) * 0.01
        dsnu_e = 0.05 * dark_signal_e
        assert dsnu_e > 1e6  # the old ceiling
        sensor.set("detector.dsnu_e_rms", dsnu_e)
        assert sensor.get("detector.dsnu_e_rms") == pytest.approx(dsnu_e, rel=1e-12)

    def test_glow_shares_the_dark_rate_scale(self, sensor: Sensor) -> None:
        # Glow is the same physical quantity in the same units as dark, so a
        # ceiling three orders below dark's was indefensible on its own terms.
        rate = _rate_from_density(_DENSITY_A_PER_M2, _PITCH_M)
        sensor.set("detector.glow_e_per_s", rate)
        assert sensor.get("detector.glow_e_per_s") == pytest.approx(rate, rel=1e-12)


class TestHighDarkRatePropagates:
    """A raised bound is worthless if the chain mishandles the value."""

    def test_dark_electrons_scale_linearly_and_stay_finite(self, sensor: Sensor) -> None:
        rate = _rate_from_density(_DENSITY_A_PER_M2, _PITCH_M)
        sensor.set("detector.dark_rate_e_per_s", rate)
        # Hold the dark reference at the operating temperature so no Arrhenius
        # factor is folded in — this test is about magnitude handling — and open
        # the well so the check is not confounded by legitimate clipping.
        sensor.set(
            "detector.dark_reference_temperature_K",
            sensor.get("detector.detector_temperature_K"),
        )
        sensor.set("readout.full_well_capacity_e", 1e9)
        # Keep the ADC matched to the widened well so the only thing under
        # test is magnitude handling, not an ADC-mismatch advisory.
        sensor.set("readout.gain_e_per_dn", 1e9 / 2**16)
        result = sensor.evaluate()
        dark_e = result.stage_outputs["detector"]["dark_e"]
        t_int = sensor.get("spectral_integration.integration_time_s")
        assert math.isfinite(dark_e)
        assert dark_e == pytest.approx(rate * t_int, rel=1e-6)
