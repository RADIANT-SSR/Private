"""Beer-Lambert-consistent spectral resample of transmittance (log-τ).

Transmittance obeys ``τ = exp(−OD)``: the optical depth ``OD``, not τ
itself, is the quantity that varies smoothly and additively with path
length, absorber amount, and — across a narrow wavelength cell — with
wavelength.  Carrying τ onto a different wavelength grid therefore has to
happen in ``ln τ`` space; interpolating τ linearly returns the arithmetic
mean of two bracketing samples where the physics gives the geometric mean,
which is systematically high and costs percent-level relative τ at cell
midpoints on a coarse stored grid.

This module holds the one implementation every backend uses:

- :class:`~radiant.atmosphere.interpolated.InterpolatedAtmosphere` shares
  :data:`TAU_FLOOR` with it and resamples its already-log-space family
  interpolation directly (CU-306);
- :class:`~radiant.atmosphere.tabulated.TabulatedAtmosphere` and
  :class:`~radiant.atmosphere.modtran.ModtranAtmosphere` call
  :func:`resample_transmittance` for every τ-like array they serve
  (CU-316).

**Radiances are deliberately NOT resampled through here.**  ``L_path`` and
``L_atm_down`` are additive emission terms with no Beer-Lambert exponential
in path length, so log-space has no physical basis for them; they stay
linear in every backend.

Zero and opaque bands
---------------------
τ is floored at :data:`TAU_FLOOR` (1e-30 ≡ OD ≈ 69, far beyond any real
atmosphere) before the log, so ``ln τ`` is finite by construction and an
opaque band resamples to that floor rather than to ``−inf``.  Values above
the floor are carried through untouched.

Out-of-range input
------------------
The floor is a *lower* clamp only.  τ > 1 is not capped: an over-unity
column is invalid data, and leaving it uncapped preserves the loud
downstream failure in ``AtmosphericQuantities.__post_init__`` (Rule 17)
rather than silently snapping it to a plausible value.  Negative τ cannot
be floored without erasing the same signal, so it raises here instead.
"""

from __future__ import annotations

import numpy as np

from radiant.atmosphere.errors import AtmosphereValidationError
from radiant.core.spectral import SpectralData, SpectralGrid

# Minimum transmittance value before taking log, to avoid log(0) = -inf.
# 1e-30 corresponds to OD ~ 69, well beyond any realistic atmosphere.
TAU_FLOOR: float = 1e-30


def resample_transmittance(source: SpectralData, target_grid: SpectralGrid) -> SpectralData:
    """Resample a transmittance spectrum onto *target_grid* in log-τ space.

    Parameters
    ----------
    source:
        Transmittance [dimensionless] on its native wavelength grid.
    target_grid:
        Destination wavelength grid in µm.  Must lie inside the source
        range — extrapolation is never performed (the underlying
        :meth:`SpectralData.resample` fails loud).

    Returns
    -------
    SpectralData
        Transmittance on *target_grid*, in linear τ.  ``name``, ``unit``,
        ``source`` and ``source_parameters`` are carried over unchanged, so
        an out-of-range query still names the array the caller asked for.

    Notes
    -----
    When the source already lives on *target_grid* the stored values are
    returned **bit-identically**: ``exp(log(τ))`` is not the identity in
    floating point, so the no-resample case short-circuits rather than
    round-tripping through the log.
    """
    lam_target = np.asarray(target_grid.wavelengths_um, dtype=np.float64)
    lam_source = np.asarray(source.wavelength_um, dtype=np.float64)
    values = np.asarray(source.values, dtype=np.float64)

    if np.array_equal(lam_source, lam_target):
        return SpectralData(
            name=source.name,
            wavelength_um=lam_target.copy(),
            values=values.copy(),
            unit=source.unit,
            source=source.source,
            source_parameters=dict(source.source_parameters),
        )

    if np.any(values < 0.0):
        raise AtmosphereValidationError(
            f"{source.name}: transmittance has negative values "
            f"(min={float(values.min()):g}), which have no logarithm. "
            "Transmittance is a probability and must be ≥ 0 — check the "
            "source table or tape7 columns for a mis-scaled or corrupt "
            "file before resampling onto the chain grid."
        )

    log_source = SpectralData(
        name=source.name,
        wavelength_um=lam_source,
        values=np.log(np.maximum(values, TAU_FLOOR)),
        unit=source.unit,
        source=source.source,
        source_parameters=dict(source.source_parameters),
    )
    resampled = log_source.resample(target_grid)

    return SpectralData(
        name=source.name,
        wavelength_um=resampled.wavelength_um,
        values=np.exp(resampled.values),
        unit=source.unit,
        source=source.source,
        source_parameters=dict(source.source_parameters),
    )
