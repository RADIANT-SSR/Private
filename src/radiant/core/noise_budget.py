"""Noise budget types — shared between detector and readout stages.

These types live in ``radiant.core`` so both detector and readout stages
can import them without violating the cross-stage import rule (Rule 11).

``TEMPORAL_TERMS`` and ``SPATIAL_TERMS`` classify the 16 noise sources
for temporal/spatial RSS separation.

``NoiseBudget`` is the aggregator that stores all 16 raw (per-pixel,
pre-TDI) noise values.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

# ---------------------------------------------------------------------------
# Term classification (temporal vs. spatial)
# ---------------------------------------------------------------------------

TEMPORAL_TERMS: frozenset[str] = frozenset(
    {
        "signal_shot",
        "background_shot",
        "nearfield_shot",
        "straylight_shot",
        "dark_shot",
        "gr_noise",
        "johnson_noise",
        "flicker_1f",
        "read_noise",
        "ktc_reset",
        "quantization",
        "persistence_noise",
        "glow_shot",
        # Digital-pixel counting terms (Gap 117): under
        # readout.architecture = "digital_counting" the ReadoutStage swaps
        # "quantization" -> "counting_quantization" and "ktc_reset" ->
        # "packet_reset" (sqrt(n_counts) x per-reset kTC). At most 16 terms
        # are ever emitted per run — the swap keeps the count invariant.
        "counting_quantization",
        "packet_reset",
    }
)

SPATIAL_TERMS: frozenset[str] = frozenset(
    {
        "prnu",
        "dsnu",
        "clutter",
    }
)

ALL_NOISE_TERMS: frozenset[str] = TEMPORAL_TERMS | SPATIAL_TERMS

#: The two digital-counting substitution terms (Gap 117). They are emitted by
#: ReadoutStage's counting branch IN PLACE OF "quantization" / "ktc_reset" and
#: never appear in the detector's raw budget — compute_noise_budget always
#: builds exactly ALL_NOISE_TERMS − COUNTING_TERMS (the historical 16).
COUNTING_TERMS: frozenset[str] = frozenset({"counting_quantization", "packet_reset"})


# ---------------------------------------------------------------------------
# NoiseBudget aggregator
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class NoiseBudget:
    """Aggregated noise budget: all 16 terms in e- RMS.

    Parameters
    ----------
    terms:
        Dict mapping noise term name -> value in e- RMS.
    sigma_temporal_e:
        RSS of all temporal terms [e- RMS].
    sigma_spatial_e:
        RSS of all spatial terms [e- RMS].
    """

    terms: dict[str, float]
    sigma_temporal_e: float
    sigma_spatial_e: float

    @property
    def sigma_total_e(self) -> float:
        """Total noise: RSS of temporal + spatial [e- RMS]."""
        return math.sqrt(self.sigma_temporal_e**2 + self.sigma_spatial_e**2)

    def fractional_contributions(self) -> dict[str, float]:
        """Return each term's fractional contribution to total variance."""
        total_var = self.sigma_total_e**2
        if total_var == 0.0:
            return dict.fromkeys(self.terms, 0.0)
        return {k: (v**2 / total_var) for k, v in self.terms.items()}
