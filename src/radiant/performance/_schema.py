"""Parameter definitions for the performance stage.

Performance metrics are mostly derived from upstream chain quantities and
need no parameters. The exceptions are metric *thresholds* the analyst
tunes — currently the point-source detection SNR threshold (Gap 77).
"""

from __future__ import annotations

from radiant.core.parameters import ParameterDef

DETECTION_SNR_THRESHOLD = ParameterDef(
    name="performance.detection_snr_threshold",
    description=(
        "SNR at which a point target counts as detected — the threshold the "
        "in-chain detection-range solver bisects to (Gap 77). 5.0 is the "
        "classic Rose-criterion / SNR=5 detection threshold."
    ),
    dtype=float,
    canonical_unit="",
    input_unit="",
    default=5.0,
    bounds=(0.5, 100.0),
    tags=frozenset({"performance", "detection"}),
    default_justification="SNR=5 is the standard point-target detection threshold.",
)


ALL_PARAMETERS: tuple[ParameterDef, ...] = (DETECTION_SNR_THRESHOLD,)
