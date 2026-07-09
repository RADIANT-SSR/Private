"""Minimum resolvable difference — MRT (thermal) and MRC (reflective).

The minimum resolvable temperature difference (MRT) and minimum resolvable
contrast (MRC) are the classic *contrast-limited* resolution metrics: the
smallest target-vs-background difference an observer can resolve at a given
spatial frequency. Both are the sensor's noise floor divided by the system
MTF at that frequency, scaled by an observer SNR threshold:

    MRT(f) = k · NETD / MTF_sys(f)          [K]
    MRC(f) = k · NEΔρ / MTF_sys(f)          [reflectance, dimensionless]

Same model, two noise metrics — MRT uses the noise-equivalent temperature
difference (`performance.nedt`), MRC the noise-equivalent reflectance
difference (`performance.nedr`). As `MTF_sys(f) → 0` toward the cutoff the
resolvable difference diverges: no target contrast, however large, resolves
detail the optics cannot pass. `k` is the observer signal-to-noise
threshold for 50 %-probability resolution (~2.25 in the NVESD literature).

This is the contrast-limited companion to the sampling-limited Johnson
model (`performance.johnson_criteria`): a task is achievable at range R only
when the target difference exceeds MRT/MRC at the task's spatial frequency
*and* the target subtends the Johnson N50 cycles. Gap 53.
"""

from __future__ import annotations

from radiant.core.exceptions import RadiantError

__all__ = [
    "DEFAULT_SNR_THRESHOLD",
    "MinimumResolvableError",
    "minimum_resolvable_contrast",
    "minimum_resolvable_temperature_K",
]

# Observer SNR threshold for 50 %-probability resolution (NVESD SNR_T).
DEFAULT_SNR_THRESHOLD = 2.25


class MinimumResolvableError(RadiantError):
    """Raised for out-of-range minimum-resolvable inputs."""


def _minimum_resolvable(
    noise_metric: float, mtf_value: float, threshold_snr: float, name: str
) -> float:
    if noise_metric < 0.0:
        raise MinimumResolvableError(f"{name} must be ≥ 0, got {noise_metric}.")
    if not 0.0 < mtf_value <= 1.0:
        raise MinimumResolvableError(f"mtf_value must be in (0, 1], got {mtf_value}.")
    if threshold_snr <= 0.0:
        raise MinimumResolvableError(f"threshold_snr must be positive, got {threshold_snr}.")
    return threshold_snr * noise_metric / mtf_value


def minimum_resolvable_temperature_K(
    netd_K: float, mtf_value: float, threshold_snr: float = DEFAULT_SNR_THRESHOLD
) -> float:
    """MRT [K] = ``k · NETD / MTF_sys(f)``.

    The smallest target-vs-background ΔT resolvable at the frequency where
    the system MTF is ``mtf_value``.
    """
    return _minimum_resolvable(netd_K, mtf_value, threshold_snr, "netd_K")


def minimum_resolvable_contrast(
    nedr: float, mtf_value: float, threshold_snr: float = DEFAULT_SNR_THRESHOLD
) -> float:
    """MRC [reflectance] = ``k · NEΔρ / MTF_sys(f)``.

    The smallest target-vs-background reflectance contrast resolvable at the
    frequency where the system MTF is ``mtf_value``.
    """
    return _minimum_resolvable(nedr, mtf_value, threshold_snr, "nedr")
