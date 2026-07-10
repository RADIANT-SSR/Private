"""Dual-path MTF consistency check.

Compares FFT(convolved EffectivePSF) against the MTF product for both
x and y axes. A failure means a degradation was added to one path
but not the other (Rule 4).

Terms whose degradation kernels are NOT convolved into the PSF (e.g.
TDI misalignment, which is a readout effect with no spatial kernel)
are excluded from the product comparison.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

import numpy as np
import numpy.typing as npt

# MTF terms that are NOT convolved into the ePSF and should be
# excluded from the dual-path comparison.
_EXCLUDED_PREFIXES = ("mtf_tdi",)


@dataclass(frozen=True)
class DualPathConsistencyResult:
    """Result of comparing PSF-path FFT vs MTF product."""

    passed_x: bool
    passed_y: bool
    max_absolute_error_x: float
    max_absolute_error_y: float
    tolerance: float


def check_dual_path_consistency(
    epsf: Any,
    mtf_terms: Mapping[str, npt.NDArray[np.float64]],
    freq_cycles_per_mrad: npt.NDArray[np.float64],
    focal_length_m: float,
    tolerance: float = 2e-2,
) -> DualPathConsistencyResult:
    """Compare FFT(convolved PSF) vs MTF product for both x and y.

    Parameters
    ----------
    epsf:
        The fully convolved EffectivePSF (duck-typed, must have
        ``mtf_1d(axis)`` method returning ``(freq_m, mtf)``).
    mtf_terms:
        All MTF terms from ``ChainState.mtf_terms``.
    freq_cycles_per_mrad:
        Shared spatial frequency grid [cycles/mrad].
    focal_length_m:
        Effective focal length [m].
    tolerance:
        Maximum allowed absolute error between paths. Default 2e-2
        (CU-045, 2026-07-10): the worst measured full-chain residual after
        the CU-003 area-integrated pixel kernel is ~1e-2 (undersampled
        Q ≈ 0.2 VNIR), so the default carries ~2x margin. The check stays
        warn-only by design — it is a diagnostic invariant, and raising
        would abort user runs whose physics is otherwise valid.

    Returns
    -------
    DualPathConsistencyResult
        Whether each axis passed and the maximum error observed.
    """
    results = {}

    for axis in ("x", "y"):
        # PSF-path: FFT of the convolved ePSF.
        freq_psf_m, mtf_psf = epsf.mtf_1d(axis)
        freq_psf_mrad = freq_psf_m * focal_length_m * 1e-3

        # MTF product path: multiply all non-excluded terms for this axis.
        suffix = f"_{axis}"
        product = np.ones_like(freq_cycles_per_mrad, dtype=np.float64)
        for name, arr in mtf_terms.items():
            if not name.endswith(suffix):
                continue
            if any(name.startswith(prefix) for prefix in _EXCLUDED_PREFIXES):
                continue
            product *= arr

        # Interpolate product onto PSF frequency grid for comparison.
        product_interp = np.interp(freq_psf_mrad, freq_cycles_per_mrad, product, right=0.0)

        # Compare only the first half (below Nyquist) where both are reliable.
        n_compare = len(freq_psf_mrad) // 2
        if n_compare < 2:
            results[axis] = (True, 0.0)
            continue

        errors = np.abs(product_interp[:n_compare] - mtf_psf[:n_compare])
        max_err = float(np.max(errors))
        results[axis] = (max_err <= tolerance, max_err)

    return DualPathConsistencyResult(
        passed_x=results["x"][0],
        passed_y=results["y"][0],
        max_absolute_error_x=results["x"][1],
        max_absolute_error_y=results["y"][1],
        tolerance=tolerance,
    )
