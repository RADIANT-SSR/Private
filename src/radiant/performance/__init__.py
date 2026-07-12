"""Stage 8: SNR, NEDT, NIIRS, system MTF, detection range, and saturation metrics."""

from radiant.performance.registry import (
    METRIC_SPECS,
    MetricSpec,
    available_metrics,
    can_compute,
    metric_info,
    missing_for,
)
from radiant.performance.snr import SNRResult

__all__ = [
    "METRIC_SPECS",
    "MetricSpec",
    "SNRResult",
    "available_metrics",
    "can_compute",
    "metric_info",
    "missing_for",
]
