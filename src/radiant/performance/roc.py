"""ROC curve — detection probability vs false-alarm rate from SNR.

For the canonical single-look Gaussian detection problem (signal-present
mean μ_s = SNR·σ over signal-absent mean 0, common noise σ), a threshold t
gives:

    P_fa = P(x > t | H0) = Q(t/σ)
    P_d  = P(x > t | H1) = Q(t/σ − SNR)

Eliminating the threshold parameterises the ROC by the false-alarm rate:

    P_d(P_fa) = Q( Q⁻¹(P_fa) − SNR )      (Q = Gaussian upper tail)

The area under the ROC has the closed form ``AUC = Φ(SNR/√2)`` for the
equal-variance Gaussian model. SNR here is the (contrast) detection index
d′. Gap for scenario 6.4.
"""

from __future__ import annotations

import numpy as np
import numpy.typing as npt
from scipy.stats import norm  # type: ignore[import-untyped]

from radiant.core.exceptions import RadiantError

__all__ = ["RocError", "detection_probability", "roc_auc", "roc_curve"]

FloatArray = npt.NDArray[np.float64]


class RocError(RadiantError):
    """Raised for out-of-range ROC inputs."""


def detection_probability(snr: float, p_fa: float) -> float:
    """Detection probability ``P_d = Q(Q⁻¹(P_fa) − SNR)`` at a false-alarm rate.

    ``snr`` is the detection index d′ (contrast SNR); ``p_fa`` ∈ (0, 1).
    """
    if snr < 0.0:
        raise RocError(f"snr must be ≥ 0, got {snr}.")
    if not 0.0 < p_fa < 1.0:
        raise RocError(f"p_fa must be in (0, 1), got {p_fa}.")
    return float(norm.sf(norm.isf(p_fa) - snr))


def roc_curve(snr: float, n_points: int = 200) -> tuple[FloatArray, FloatArray]:
    """ROC curve ``(P_fa, P_d)`` for a detection index ``snr``.

    P_fa is log-spaced over [1e-6, 1] so the low-false-alarm knee is
    resolved. Returns two arrays of length ``n_points``.
    """
    if snr < 0.0:
        raise RocError(f"snr must be ≥ 0, got {snr}.")
    if n_points < 2:
        raise RocError(f"n_points must be ≥ 2, got {n_points}.")
    p_fa = np.logspace(-6.0, 0.0, n_points)
    p_fa[-1] = 1.0 - 1e-12  # keep strictly < 1 for the inverse
    p_d = norm.sf(norm.isf(p_fa) - snr)
    return p_fa, np.asarray(p_d, dtype=np.float64)


def roc_auc(snr: float) -> float:
    """Area under the ROC, ``Φ(SNR/√2)`` (equal-variance Gaussian model).

    0.5 at SNR = 0 (chance), → 1 as SNR → ∞.
    """
    if snr < 0.0:
        raise RocError(f"snr must be ≥ 0, got {snr}.")
    return float(norm.cdf(snr / np.sqrt(2.0)))
