"""Radiometric accuracy — the bias budget (Gap 120, ADR-0012, ratified D3).

Consumes ``ChainState.bias_terms`` ONLY — the type-enforced counterpart of
SNR/NEDT consuming ``noise_terms`` only. Bias is never RSS'd into noise;
independent bias sources RSS *within* this budget. Reported both as a
fractional radiance bias and as K at the scene temperature (D3), the latter
via the chain's own thermal derivative:

    ΔT = (ΔL/L · S) / (dS/dT)

Result-typed failures per the Rule 17 metric-layer carve-out: a scene with
no thermal derivative reports the %-domain value with a named failure for
the K conversion, never NaN.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from radiant.core.chain import ChainState


@dataclass(frozen=True)
class RadiometricAccuracyResult:
    """Bias budget for a completed chain run.

    Parameters
    ----------
    bias_frac:
        Total fractional radiance bias (1-sigma, RSS of independent
        sources). 0.0 when no bias terms are present.
    bias_K:
        Bias expressed as K at the scene temperature — ``float('nan')``
        with ``failure_reason`` when the scene has no thermal derivative.
    per_source_frac:
        Fractional bias per source name (insertion order preserved).
    failure_reason:
        ``None`` on full success; names the failed conversion otherwise.
    """

    bias_frac: float
    bias_K: float
    per_source_frac: dict[str, float] = field(default_factory=dict)
    failure_reason: str | None = None


def compute_radiometric_accuracy(state: ChainState) -> RadiometricAccuracyResult:
    """Compute the accuracy budget from accumulated bias terms."""
    per_source = {t.name: t.value_frac for t in state.bias_terms}
    bias_frac = math.sqrt(sum(f**2 for f in per_source.values()))

    if not per_source:
        return RadiometricAccuracyResult(
            bias_frac=0.0,
            bias_K=0.0,
            per_source_frac={},
            failure_reason="no bias terms (calibration bias model not active)",
        )

    ro = state.stage_outputs.get("readout", {})
    si = state.stage_outputs.get("spectral_integration", {})
    signal_e = ro.get("signal_e_final")
    ds_dt = si.get("ds_dt_e_per_K")
    if signal_e is None or signal_e <= 0.0 or ds_dt is None or ds_dt <= 0.0:
        return RadiometricAccuracyResult(
            bias_frac=bias_frac,
            bias_K=float("nan"),
            per_source_frac=per_source,
            failure_reason=(
                "no thermal derivative (ds_dt_e_per_K) or signal — bias_K "
                "undefined for this scene; bias_frac remains valid"
            ),
        )
    bias_K = bias_frac * float(signal_e) / float(ds_dt)
    return RadiometricAccuracyResult(
        bias_frac=bias_frac,
        bias_K=bias_K,
        per_source_frac=per_source,
    )
