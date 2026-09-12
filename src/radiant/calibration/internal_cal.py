"""Internal-cal path mismatch — the fore-optics emission split (Gap 122 item 4).

An internal cal shutter/flag sits inside the optical train: during cal the
detector sees the flag plus every element BEHIND it, so the NUC correction
derived from that view absorbs the aft-element emission — but never the
emission of the elements in FRONT of the flag. In operation the fore-optics
emission returns as an offset the calibration cannot remove:

- an **offset bias** (`internal_cal_offset` BiasTerm): the fore-optics
  near-field electrons expressed as a fraction of the scene signal, and
- **narcissus-pattern FPN** (`narcissus_fpn` NoiseTerm, spatial): the part
  of that uncorrected offset that varies across the array (cold-stop
  reflections, vignetting of the warm fore-optics).

This module owns the split itself: the photon-weighted in-band fraction of
the near-field FPA irradiance contributed by the fore elements,

    f_fore = ∫_band Σ_fore E_i(λ)·λ dλ / ∫_band Σ_all E_i(λ)·λ dλ

(each W of in-band power carries λ/hc photons; hc cancels in the ratio).
The electron magnitude then rides the detector's own conversion:
``fore_e = nearfield_e × f_fore`` — no radiometry is re-derived here.

Assumption: the split weights per-element irradiance by photon count, not
by the QE spectrum; exact when QE is flat across the band, first-order
otherwise (the per-element spectra are same-family greybody curves, so the
QE weighting largely cancels in the ratio).

See RADIANT_Calibration.md §1.2 and §5 (the ADR-0012 ops-level growth path).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

import numpy as np

from radiant.calibration.errors import CalibrationValidationError
from radiant.core.spectral import SpectralData


def fore_optics_fraction(
    *,
    per_element: Mapping[str, SpectralData],
    fore_names: Sequence[str],
    lam_min_um: float,
    lam_max_um: float,
) -> float:
    """Photon-weighted in-band fraction of near-field irradiance from *fore_names*.

    Parameters
    ----------
    per_element:
        Per-element near-field FPA irradiance [W/m²/µm], keyed by element
        name (``stage_outputs["optics"]["nearfield_per_element"]``). Cold
        (0 K) elements are absent from the map — they emit nothing, so a
        fore name without an entry contributes zero rather than erroring.
    fore_names:
        Names of the elements in FRONT of the internal cal shutter (scene
        side) — the emission the cal never sees.
    lam_min_um, lam_max_um:
        The sensing band [µm]; emission outside it cannot bias the split.

    Returns
    -------
    float
        Fraction in [0, 1]; 0.0 when the map is empty or carries no
        in-band emission (no near-field → no mismatch, never a 0/0 NaN).
    """
    if not (0.0 < lam_min_um < lam_max_um):
        raise CalibrationValidationError(
            f"band [{lam_min_um}, {lam_max_um}] µm is invalid.\n"
            "  Why: the band integral needs 0 < lam_min < lam_max.\n"
            "  Action: check spectral_integration.filter_min_um / filter_max_um."
        )
    fore = set(fore_names)
    total = 0.0
    fore_sum = 0.0
    for name, sd in per_element.items():
        wl = sd.wavelength_um
        mask = (wl >= lam_min_um) & (wl <= lam_max_um)
        if int(mask.sum()) < 2:
            continue
        # Photon weighting: W/m²/µm × λ ∝ photons (hc cancels in the ratio).
        contrib = float(np.trapezoid(sd.values[mask] * wl[mask], wl[mask]))
        total += contrib
        if name in fore:
            fore_sum += contrib
    if total <= 0.0:
        return 0.0
    return fore_sum / total
