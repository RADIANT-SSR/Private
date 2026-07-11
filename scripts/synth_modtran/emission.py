"""Multi-layer Planck/Schwarzschild thermal path radiance.

Independent of RADIANT's own atmosphere module — pure Planck's law
(CODATA constants) plus the standard discretized radiative-transfer
sum over the layer stack built by ``layers.py``.
"""

from __future__ import annotations

import numpy as np

# CODATA 2018 constants (independent of radiant.core.constants).
_H_PLANCK_J_S = 6.62607015e-34
_C_LIGHT_CM_S = 2.99792458e10  # cm/s, so hc*nu[cm-1] has energy units directly
_K_BOLTZMANN_J_K = 1.380649e-23


def planck_radiance_W_cm2_sr_cm1(wavenumber_cm1: np.ndarray, temperature_K: float) -> np.ndarray:
    """Spectral radiance B(nu, T) in MODTRAN-native W/cm^2/sr/cm^-1.

    Standard Planck's law in wavenumber space; unit derivation and a
    Stefan-Boltzmann cross-check live in
    scripts/synth_modtran/tests/test_emission_sanity.py.
    """
    nu = np.asarray(wavenumber_cm1, dtype=np.float64)
    x = _H_PLANCK_J_S * _C_LIGHT_CM_S * nu / (_K_BOLTZMANN_J_K * temperature_K)
    x = np.clip(x, 1e-12, 700.0)  # avoid overflow in exp for very high nu/low T
    # Working entirely in CGS-with-wavenumber units (c in cm/s, nu in
    # cm^-1) is already dimensionally self-consistent for B_nu in
    # W/cm^2/sr/cm^-1 -- no further unit-conversion factor is needed.
    # Verified against the Stefan-Boltzmann integral in
    # scripts/synth_modtran/tests/test_emission_sanity.py.
    prefactor = 2.0 * _H_PLANCK_J_S * _C_LIGHT_CM_S**2 * nu**3
    return prefactor / (np.exp(x) - 1.0)


def path_thermal_radiance_W_cm2_sr_cm1(
    wavenumber_cm1: np.ndarray,
    temperatures_near_to_far_K: list[float],
    delta_tau_near_to_far: list[np.ndarray],
) -> np.ndarray:
    """Discretized Schwarzschild upwelling path radiance at the sensor.

    ``temperatures_near_to_far_K[i]`` / ``delta_tau_near_to_far[i]`` must
    be ordered from the layer NEAREST the sensor (index 0) to farthest.
    """
    L = np.zeros_like(wavenumber_cm1, dtype=np.float64)
    cumulative_trans = np.ones_like(wavenumber_cm1, dtype=np.float64)
    for T_i, dtau_i in zip(temperatures_near_to_far_K, delta_tau_near_to_far, strict=True):
        B_i = planck_radiance_W_cm2_sr_cm1(wavenumber_cm1, T_i)
        emission_i = B_i * (1.0 - np.exp(-dtau_i))
        L += emission_i * cumulative_trans
        cumulative_trans = cumulative_trans * np.exp(-dtau_i)
    return L
