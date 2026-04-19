"""MTF budget from the MTF product path.

Multiplies all named MTF terms to produce system MTF for both x and y
axes. Identifies the dominant (worst) contributor at Nyquist for each axis.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

import numpy as np
import numpy.typing as npt


@dataclass(frozen=True)
class MTFBudgetResult:
    """Result of the MTF budget computation.

    Attributes
    ----------
    freq_cycles_per_mrad:
        Shared spatial frequency grid [cycles/mrad].
    system_mtf_x:
        Product of all ``_x`` MTF terms.
    system_mtf_y:
        Product of all ``_y`` MTF terms.
    per_term:
        All individual MTF term arrays, keyed by term name.
    per_term_at_nyquist:
        Each MTF term value at f_Nyquist, keyed by term name.
    system_mtf_at_nyquist_x:
        System MTF (product path) at Nyquist for x axis.
    system_mtf_at_nyquist_y:
        System MTF (product path) at Nyquist for y axis.
    dominant_contributor_at_nyquist_x:
        Name of the MTF term with the lowest value at Nyquist (x axis).
    dominant_contributor_at_nyquist_y:
        Name of the MTF term with the lowest value at Nyquist (y axis).
    """

    freq_cycles_per_mrad: npt.NDArray[np.float64]
    system_mtf_x: npt.NDArray[np.float64]
    system_mtf_y: npt.NDArray[np.float64]
    per_term: dict[str, npt.NDArray[np.float64]]
    per_term_at_nyquist: dict[str, float]
    system_mtf_at_nyquist_x: float
    system_mtf_at_nyquist_y: float
    dominant_contributor_at_nyquist_x: str
    dominant_contributor_at_nyquist_y: str


def compute_mtf_budget(
    mtf_terms: Mapping[str, npt.NDArray[np.float64]],
    freq_cycles_per_mrad: npt.NDArray[np.float64],
    pixel_pitch_m: float,
    focal_length_m: float,
) -> MTFBudgetResult:
    """Multiply all MTF terms to produce system MTF for both axes.

    Groups terms by ``_x`` / ``_y`` suffix. System MTF per axis is
    the product of all terms for that axis. Identifies the dominant
    (worst) contributor at Nyquist.

    Parameters
    ----------
    mtf_terms:
        Named MTF arrays from ``ChainState.mtf_terms``.
    freq_cycles_per_mrad:
        Shared spatial frequency grid [cycles/mrad].
    pixel_pitch_m:
        Detector pixel pitch [m] — used to compute Nyquist freq.
    focal_length_m:
        Effective focal length [m] — used for freq conversion.
    """
    freq_m = freq_cycles_per_mrad / (focal_length_m * 1e3)

    # Separate terms by axis.
    x_terms: dict[str, npt.NDArray[np.float64]] = {}
    y_terms: dict[str, npt.NDArray[np.float64]] = {}
    for name, arr in mtf_terms.items():
        if name.endswith("_x"):
            x_terms[name] = np.asarray(arr, dtype=np.float64)
        elif name.endswith("_y"):
            y_terms[name] = np.asarray(arr, dtype=np.float64)

    # System MTF = product of all terms per axis.
    n = len(freq_cycles_per_mrad)
    system_x = np.ones(n, dtype=np.float64)
    for arr in x_terms.values():
        system_x *= arr
    system_y = np.ones(n, dtype=np.float64)
    for arr in y_terms.values():
        system_y *= arr

    # Nyquist frequency.
    f_ny_m = 1.0 / (2.0 * pixel_pitch_m)

    # Interpolate each term at Nyquist.
    per_term_at_ny: dict[str, float] = {}
    for name, arr in mtf_terms.items():
        per_term_at_ny[name] = float(np.interp(f_ny_m, freq_m, arr, right=0.0))

    sys_at_ny_x = float(np.interp(f_ny_m, freq_m, system_x, right=0.0))
    sys_at_ny_y = float(np.interp(f_ny_m, freq_m, system_y, right=0.0))

    # Dominant (worst) contributor at Nyquist per axis.
    def _worst(terms: dict[str, npt.NDArray[np.float64]]) -> str:
        if not terms:
            return "none"
        return min(terms, key=lambda k: per_term_at_ny.get(k, 1.0))

    dom_x = _worst(x_terms)
    dom_y = _worst(y_terms)

    return MTFBudgetResult(
        freq_cycles_per_mrad=freq_cycles_per_mrad,
        system_mtf_x=system_x,
        system_mtf_y=system_y,
        per_term=dict(mtf_terms),
        per_term_at_nyquist=per_term_at_ny,
        system_mtf_at_nyquist_x=sys_at_ny_x,
        system_mtf_at_nyquist_y=sys_at_ny_y,
        dominant_contributor_at_nyquist_x=dom_x,
        dominant_contributor_at_nyquist_y=dom_y,
    )
