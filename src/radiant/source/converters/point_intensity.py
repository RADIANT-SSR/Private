"""Point-source radiant intensity from convenience inputs (Gap B / S10).

Two friendlier ways to specify the spectral intensity ``I(λ)`` [W/sr/µm] of an
unresolved (point-source) target than hand-authoring a CSV
(:mod:`radiant.source.converters.user_intensity`):

* **Blackbody emitter** — ``I(λ) = ε · A_emit · B(λ, T)`` for a heated object (an
  SDA thermal satellite, a star treated as a graybody). Delegates the Planck
  math to :class:`~radiant.source.point_source_blackbody.BlackbodyIntensitySource`.
* **Scalar band-integrated intensity** — a single ``I_band`` [W/sr] taken as the
  in-band integral ``∫ I(λ) dλ`` over the filter band. Modeled as a spectrally
  **flat** intensity ``I(λ) = I_band / (λ_max − λ_min)`` inside the band and zero
  outside, so the band integral recovers ``I_band`` exactly. This is the analyst's
  explicit assumption (owner 2026-07-18): the scalar is the integrated value over
  the specified band, not a per-µm density.

Both return a plain ``I(λ)`` array on the chain grid; the inferrer wraps it in a
:class:`~radiant.core.spectral.SpectralData` and routes it through
:func:`~radiant.source.converters.user_intensity.user_intensity_to_descriptor` to
the one :class:`T7IntensityAtSource` descriptor — so all three point-source
intensity inputs (CSV, blackbody, scalar) converge on the same chain path.

Rule 19 — this module owns exactly the two convenience→I(λ) conversions.
"""

from __future__ import annotations

import numpy as np
import numpy.typing as npt

from radiant.core.parameters import ParameterBoundsError
from radiant.source.point_source_blackbody import BlackbodyIntensitySource


def blackbody_point_intensity(
    wavelength_um: npt.NDArray[np.float64],
    temperature_K: float,
    area_m2: float,
    emissivity: float,
) -> npt.NDArray[np.float64]:
    """``I(λ) = ε · A_emit · B(λ, T)`` [W/sr/µm] on the given wavelength grid.

    Validation (positive T and area, ε ∈ [0, 1]) is delegated to
    :class:`BlackbodyIntensitySource`, which raises an actionable
    ``SourceValidationError`` — but callers should pre-check the area so the
    message names ``point_intensity_area_m2`` (see the inferrer).
    """
    source = BlackbodyIntensitySource(
        temperature_K=temperature_K,
        projected_area_m2=area_m2,
        emissivity=emissivity,
        name="point_intensity",
    )
    return source.spectral_intensity(wavelength_um)


def scalar_band_intensity(
    wavelength_um: npt.NDArray[np.float64],
    band_W_per_sr: float,
    filter_min_um: float,
    filter_max_um: float,
) -> npt.NDArray[np.float64]:
    """Spectrally flat ``I(λ)`` [W/sr/µm] whose band integral equals ``band_W_per_sr``.

    ``I(λ) = band_W_per_sr / (filter_max − filter_min)`` for ``λ`` in
    ``[filter_min_um, filter_max_um]``, zero outside — so
    ``∫ I(λ) dλ = band_W_per_sr`` [W/sr] over the band.

    Raises
    ------
    ParameterBoundsError
        If the band is empty/inverted or the intensity is negative (Rule 15/17).
    """
    if filter_max_um <= filter_min_um:
        raise ParameterBoundsError(
            what=(
                f"scalar band intensity: filter band [{filter_min_um}, {filter_max_um}] µm "
                "is empty or inverted"
            ),
            why=(
                "The band width (filter_max − filter_min) is the denominator of the flat intensity."
            ),
            action="Set spectral_integration.filter_min_um < filter_max_um.",
            context={"filter_min_um": filter_min_um, "filter_max_um": filter_max_um},
        )
    if band_W_per_sr < 0.0:
        raise ParameterBoundsError(
            what=f"scalar band intensity = {band_W_per_sr} W/sr is negative",
            why="Radiant intensity (power per solid angle) is non-negative by definition.",
            action="Set source.target.point_intensity_band_W_per_sr ≥ 0.",
            context={"value": band_W_per_sr},
        )
    lam = np.asarray(wavelength_um, dtype=np.float64)
    density = band_W_per_sr / (filter_max_um - filter_min_um)  # W/sr/µm
    in_band = (lam >= filter_min_um) & (lam <= filter_max_um)
    return np.where(in_band, density, 0.0).astype(np.float64)
