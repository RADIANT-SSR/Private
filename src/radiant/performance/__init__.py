"""Stage 8: SNR, NEDT, NIIRS, system MTF, detection range, and saturation metrics."""

from radiant.performance.registry import METRIC_SPECS, available_metrics, can_compute
from radiant.performance.snr import SNRResult

__all__ = [
    "METRIC_SPECS",
    "SNRResult",
    "available_metrics",
    "can_compute",
]
