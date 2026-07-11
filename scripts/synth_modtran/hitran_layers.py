"""Per-layer molecular optical depth via RADIS (HITRAN line-by-line).

This is the genuinely-independent-physics piece of the synthetic
generator: real spectroscopic line data (HITRAN), not RADIANT's own
Beer-Lambert band-fit coefficients. Only the primary isotopologue
(isotope='1') is used per species — a standard simplification (main
isotopologues are >98% of atmospheric abundance for H2O/CO2/O3).
"""

from __future__ import annotations

import numpy as np
from radis import calc_spectrum

from scripts.synth_modtran.layers import Layer

SPECIES = ("H2O", "CO2", "O3")


def layer_optical_depth_vertical(
    layer: Layer,
    species: str,
    v1_cm1: float,
    v2_cm1: float,
) -> tuple[np.ndarray, np.ndarray]:
    """Vertical (nadir, one-pass) optical depth spectrum for one layer/species.

    Returns ``(wavenumber_cm1, optical_depth)`` on RADIS's native grid.
    Optical depth is ``-ln(transmittance)`` for the layer's vertical
    thickness — additive across layers, and linearly rescalable for a
    slant path via the airmass secant factor (Beer-Lambert).
    """
    mole_fraction = {
        "H2O": layer.h2o_mole_fraction,
        "CO2": layer.co2_mole_fraction,
        "O3": layer.o3_mole_fraction,
    }[species]
    path_length_cm = layer.thickness_km * 1.0e5

    spectrum = calc_spectrum(
        v1_cm1,
        v2_cm1,
        molecule=species,
        isotope="1",
        pressure=max(layer.pressure_bar, 1e-6),
        Tgas=layer.temperature_K,
        mole_fraction=max(mole_fraction, 1e-15),
        path_length=path_length_cm,
        databank="hitran",
        verbose=False,
        wstep="auto",
        warnings={"AccuracyWarning": "ignore", "MemoryUsageWarning": "ignore"},
    )
    w, transmittance = spectrum.get("transmittance_noslit", wunit="cm-1")
    transmittance = np.clip(np.asarray(transmittance), 1e-300, 1.0)
    optical_depth = -np.log(transmittance)
    return np.asarray(w), optical_depth
