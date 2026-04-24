"""Noise model — 16 noise sources + budget aggregator.

Family modules:
    photon.py           — Photon-shot (terms 1-4)
    detector_material.py — Detector-material (terms 5-8)
    roic.py             — ROIC (terms 9-11)
    fixed_pattern.py    — Fixed-pattern / spatial (terms 12-14)
    other.py            — Other (terms 15-16)
    budget.py           — compute_noise_budget aggregator
"""

from radiant.core.noise_budget import (
    ALL_NOISE_TERMS,
    SPATIAL_TERMS,
    TEMPORAL_TERMS,
    NoiseBudget,
)
from radiant.detector.noise.budget import compute_noise_budget

__all__ = [
    "ALL_NOISE_TERMS",
    "NoiseBudget",
    "SPATIAL_TERMS",
    "TEMPORAL_TERMS",
    "compute_noise_budget",
]
