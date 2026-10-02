"""Band-mean of a spectral quantity — the scalar an external model quotes (Gap 134).

A spectral array is the honest internal representation and a useless thing to
compare against another model, which will quote one number for the band. So

    <X> = (1/Δλ) ∫ X(λ) dλ   over the band

is published alongside the array. The originating complaint was scenario 3.2's:
``tau_atm`` is a spectral array with no scalar band mean, so every reader
computed their own — and an unweighted mean, a photon-weighted mean and a
radiance-weighted mean are three different numbers.

**This is the unweighted mean, and that is a deliberate, stated choice.** It is
the one an external model's "band transmittance" almost always means, it needs
no assumption about the source, and it is reproducible from the array by anyone
checking. A weighted mean would silently bake in a spectrum the caller did not
choose — so if a weighted figure is wanted, the array is right there.
"""

from __future__ import annotations

import math

import numpy as np
import numpy.typing as npt

from radiant.performance.errors import PerformanceValidationError

__all__ = ["band_mean"]


def band_mean(wavelength_um: npt.NDArray[np.float64], values: npt.NDArray[np.float64]) -> float:
    """Unweighted band mean of ``values`` over ``wavelength_um``.

    Trapezoidal, divided by the band width, so a single-point band returns that
    point's value rather than dividing by zero.
    """
    if wavelength_um.shape != values.shape:
        raise PerformanceValidationError(
            f"band_mean: wavelength_um shape {wavelength_um.shape} does not "
            f"match values shape {values.shape}."
        )
    if wavelength_um.size == 0:
        raise PerformanceValidationError("band_mean: the band is empty.")
    if wavelength_um.size == 1:
        return float(values[0])
    width = float(wavelength_um[-1] - wavelength_um[0])
    if width <= 0.0:
        raise PerformanceValidationError(
            f"band_mean: the band has non-positive width ({width} um); "
            f"wavelength_um must be strictly increasing."
        )
    mean = float(np.trapezoid(values, wavelength_um)) / width
    if not math.isfinite(mean):
        raise PerformanceValidationError(
            f"band_mean: produced a non-finite mean ({mean}) — the input array "
            f"contains non-finite values."
        )
    return mean
