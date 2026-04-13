"""Stage 6: detector quantum efficiency, noise terms, and detector MTF."""

from radiant.detector.noise import NoiseBudget, compute_noise_budget

__all__ = ["NoiseBudget", "compute_noise_budget"]
