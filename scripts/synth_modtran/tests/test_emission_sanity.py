"""Stefan-Boltzmann cross-check for the synthetic-tape7 Planck function.

Not part of the RADIANT test suite (radiant.core already has its own
Planck implementation with its own tests) -- this only exists to catch
unit-conversion bugs in scripts/synth_modtran/emission.py before it
feeds hours of RADIS compute.
"""

from __future__ import annotations

import numpy as np
import pytest

from scripts.synth_modtran.emission import planck_radiance_W_cm2_sr_cm1

_SIGMA_SB_W_M2_K4 = 5.670374419e-8  # CODATA


@pytest.mark.parametrize("temperature_K", [220.0, 288.15, 300.0, 1000.0])
def test_integral_matches_stefan_boltzmann(temperature_K: float) -> None:
    nu = np.linspace(1.0, 200_000.0, 2_000_000)  # cm-1, covers ~all thermal emission
    B = planck_radiance_W_cm2_sr_cm1(nu, temperature_K)
    integral = np.trapezoid(B, nu)  # W/cm^2/sr
    expected = _SIGMA_SB_W_M2_K4 * temperature_K**4 / np.pi / 1e4  # W/cm^2/sr
    assert integral == pytest.approx(expected, rel=1e-4)
