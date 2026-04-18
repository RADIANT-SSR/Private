"""Stage 6: detector quantum efficiency, noise terms, and detector MTF."""

from radiant.core.noise_budget import NoiseBudget
from radiant.detector.noise.budget import compute_noise_budget

__all__ = ["NoiseBudget", "compute_noise_budget"]
