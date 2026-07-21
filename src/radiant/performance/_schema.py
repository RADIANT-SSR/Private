"""Parameter definitions for the performance stage.

Performance metrics are mostly derived from upstream chain quantities and
need no parameters. The exceptions are metric *thresholds* the analyst
tunes — currently the point-source detection SNR threshold (Gap 77) — and
the metric-**selection** flags (Gap 96): five boolean group toggles that
choose which metric families PerformanceStage computes and surfaces.
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

# --- Metric-selection group flags (Gap 96) ---------------------------------
# One boolean per metric group. A group's metrics are *surfaced* (emitted +
# shown) iff its flag is True; PerformanceStage still computes any hidden
# prerequisites via the dependency closure (radiant.performance.metric_selection).
# All default True — the change is additive and alters no golden results until
# an analyst (or CU-166's applicability defaults) turns a group off.
_METRICS_TAGS = frozenset({"performance", "metrics", "selection"})
_METRICS_JUSTIFICATION = (
    "All metric groups default ON so the selection is additive (no golden "
    "results change); the analyst opts out of families they don't need."
)

METRICS_RADIOMETRIC = ParameterDef(
    name="performance.metrics.radiometric",
    description=(
        "Surface the Radiometric metric group: snr, contrast_snr, scnr, "
        "detection_range_m, nedt_K. Off stops their computation and any "
        "warnings they emit (Gap 96)."
    ),
    dtype=bool,
    canonical_unit="",
    input_unit="",
    default=True,
    tags=_METRICS_TAGS,
    default_justification=_METRICS_JUSTIFICATION,
)

METRICS_SPATIAL_MTF = ParameterDef(
    name="performance.metrics.spatial_mtf",
    description=(
        "Surface the Spatial-MTF metric group: fwhm, rer, ee_1x1/3x3, "
        "mtf_at_nyquist, strehl(+marechal), mtf_system/folded/alias at "
        "Nyquist. Off stops the PSF/MTF spatial path (and its Rule-4 "
        "dual-path consistency check) unless an enabled metric needs a "
        "spatial input (Gap 96)."
    ),
    dtype=bool,
    canonical_unit="",
    input_unit="",
    default=True,
    tags=_METRICS_TAGS,
    default_justification=_METRICS_JUSTIFICATION,
)

METRICS_INTERPRETABILITY = ParameterDef(
    name="performance.metrics.interpretability",
    description=(
        "Surface the Interpretability metric group: niirs, "
        "niirs_extrapolated, mrt_at_nyquist_K. Off stops the GIQE/IIRS and "
        "MRT computation (Gap 96)."
    ),
    dtype=bool,
    canonical_unit="",
    input_unit="",
    default=True,
    tags=_METRICS_TAGS,
    default_justification=_METRICS_JUSTIFICATION,
)

METRICS_SAMPLING = ParameterDef(
    name="performance.metrics.sampling",
    description=(
        "Surface the Sampling/geometry metric group: gsd_*, ground_range_m, "
        "swath_width_m, access_rate_m2_s, q_*, sampling_regime_code, "
        "diffraction_limit_*, max_integration_time_s. Off stops their "
        "computation (Gap 96)."
    ),
    dtype=bool,
    canonical_unit="",
    input_unit="",
    default=True,
    tags=_METRICS_TAGS,
    default_justification=_METRICS_JUSTIFICATION,
)

METRICS_SATURATION = ParameterDef(
    name="performance.metrics.saturation",
    description=(
        "Surface the Saturation metric group: well_margin_dB, adc_margin_dB, "
        "dynamic_range_dB. Off stops their computation (Gap 96)."
    ),
    dtype=bool,
    canonical_unit="",
    input_unit="",
    default=True,
    tags=_METRICS_TAGS,
    default_justification=_METRICS_JUSTIFICATION,
)


# --- NIIRS applicability (CU-166 approach 2) --------------------------------
NIIRS_ALLOW_EXTRAPOLATED = ParameterDef(
    name="performance.niirs.allow_extrapolated",
    description=(
        "Report a NIIRS/IIRS value even when a GIQE-5 input (GSD, RER, or "
        "SNR) is outside the published calibration ranges. Default False: an "
        "out-of-envelope configuration gets NIIRS as N/A (a result-typed "
        "failure_reason on niirs_result, no niirs metric) because the fitted "
        "formula is unreliable there (CU-166; owner-ratified 2026-07-20 — "
        "strict refusal). True restores the extrapolated value, still "
        "flagged via niirs_extrapolated."
    ),
    dtype=bool,
    canonical_unit="",
    input_unit="",
    default=False,
    tags=frozenset({"performance", "niirs"}),
    default_justification=(
        "Outside its calibration envelope the GIQE-5 fit produces "
        "unphysical scores (e.g. NIIRS 20+ on a 0-9 scale for sub-envelope "
        "GSD); refusing by default keeps the headline metric trustworthy."
    ),
)

ALL_PARAMETERS: tuple[ParameterDef, ...] = (
    DETECTION_SNR_THRESHOLD,
    NIIRS_ALLOW_EXTRAPOLATED,
    METRICS_RADIOMETRIC,
    METRICS_SPATIAL_MTF,
    METRICS_INTERPRETABILITY,
    METRICS_SAMPLING,
    METRICS_SATURATION,
)
