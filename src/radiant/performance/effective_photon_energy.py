"""The mean energy of a detected photon, computed rather than approximated (Gap 135).

Converting between photon units and radiometric units needs a photon energy,
``E = hc/λ``, and therefore an effective wavelength. The external review flagged
this as the hidden step in every such conversion: *"photon energy, hence an
effective wavelength"*. Pick it badly and the conversion carries a silent error
that no dimensional check catches.

RADIANT does not have to pick. The chain already integrates the detected
spectral flux, so the effective photon energy is the ratio of two integrals it
can take directly::

    E_eff = ∫ Φ(λ)·QE(λ)·(hc/λ) dλ  /  ∫ Φ(λ)·QE(λ) dλ        [J/photon]

which is the **detected-photon-weighted mean energy** — exactly the number that
turns a detected photon rate into the radiant power that produced it. No band
centre, no assumption about the source's shape.

Two things about the weighting are deliberate:

**It weights by the detected flux, not the incident flux.** The quantity being
converted is a count of photons that produced electrons, so the photons that
did not are not part of the average. A QE that falls across the band therefore
shifts ``E_eff``, which is correct and is the reason this is not simply the
band centre.

**It is an energy average, not a wavelength average.** ``hc/⟨λ⟩`` and
``⟨hc/λ⟩`` differ — by Jensen's inequality the energy average is the larger —
and it is the energy average that makes ``photons × E_eff = watts`` exact. The
reported ``lambda_eff_um`` is ``hc/E_eff`` back-solved from it, so it is the
wavelength whose photon energy *is* the mean, not the mean wavelength. Those
are different numbers and the docstring says which this is on purpose.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
import numpy.typing as npt

from radiant.core.constants import c, h
from radiant.performance.errors import PerformanceValidationError

__all__ = ["EffectivePhotonEnergy", "effective_photon_energy"]


@dataclass(frozen=True, slots=True)
class EffectivePhotonEnergy:
    """The detected-photon-weighted mean photon energy, and its wavelength."""

    energy_j: float
    lambda_eff_um: float


def effective_photon_energy(
    wavelength_um: npt.NDArray[np.float64],
    spectral_flux: npt.NDArray[np.float64],
    qe: npt.NDArray[np.float64] | None = None,
) -> EffectivePhotonEnergy:
    """Mean energy of a detected photon [J], weighted by the detected flux.

    ``spectral_flux`` is any per-wavelength photon-proportional quantity; only
    its *shape* matters, since the weighting normalises. ``qe`` is applied when
    given, so the average runs over photons that were actually detected.
    """
    if wavelength_um.shape != spectral_flux.shape:
        raise PerformanceValidationError(
            f"effective_photon_energy: wavelength_um shape {wavelength_um.shape} "
            f"does not match spectral_flux shape {spectral_flux.shape}."
        )
    if qe is not None and qe.shape != wavelength_um.shape:
        raise PerformanceValidationError(
            f"effective_photon_energy: qe shape {qe.shape} does not match "
            f"wavelength_um shape {wavelength_um.shape}."
        )
    if wavelength_um.size == 0:
        raise PerformanceValidationError("effective_photon_energy: the band is empty.")
    if np.any(wavelength_um <= 0.0):
        raise PerformanceValidationError(
            "effective_photon_energy: wavelength_um must be strictly positive."
        )

    weight = spectral_flux if qe is None else spectral_flux * qe
    if np.any(weight < 0.0):
        raise PerformanceValidationError(
            "effective_photon_energy: the weighting flux must be non-negative; a "
            "negative spectral flux is an upstream defect."
        )
    lam_m = wavelength_um * 1.0e-6  # units-ok: µm -> m at this boundary (Rule 2)
    photon_energy_j = h * c / lam_m

    if wavelength_um.size == 1:
        return EffectivePhotonEnergy(
            energy_j=float(photon_energy_j[0]), lambda_eff_um=float(wavelength_um[0])
        )

    denominator = float(np.trapezoid(weight, wavelength_um))
    if denominator <= 0.0:
        raise PerformanceValidationError(
            "effective_photon_energy: the weighting flux integrates to "
            f"{denominator}, so there are no detected photons to average over. "
            "A photon energy is undefined here rather than zero."
        )
    numerator = float(np.trapezoid(weight * photon_energy_j, wavelength_um))
    energy_j = numerator / denominator
    if not math.isfinite(energy_j) or energy_j <= 0.0:
        raise PerformanceValidationError(
            f"effective_photon_energy: produced a non-physical energy ({energy_j} J)."
        )
    return EffectivePhotonEnergy(energy_j=energy_j, lambda_eff_um=(h * c / energy_j) * 1.0e6)
