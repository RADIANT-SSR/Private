"""Sampling regime — detector-limited vs diffraction-limited classification.

The sampling parameter ``Q = λ · (f/#) / pitch`` sets whether the detector
or the optics limits image resolution:

    Q < 1   detector-limited  (undersampled, aliasing risk; the pixel is
            coarser than the optical blur — resolution set by the detector)
    1 ≤ Q ≤ 2  near-critical  (well matched; Q = 2 is Nyquist-critical)
    Q > 2   diffraction-limited  (oversampled; the optics out-resolve the
            pixel — resolution set by the aperture)

This is the frequency-domain twin of the diffraction-GSD-vs-GSD comparison
in :mod:`radiant.performance.diffraction_limit`. The classification is
exposed as an integer code so it fits the float metric map:

    0.0 = detector-limited, 1.0 = near-critical, 2.0 = diffraction-limited

Gap 50 (Phase T4): scenario 1.2 re-derived this from ``q_center`` each run;
it belongs as a first-class result flag.
"""

from __future__ import annotations

from radiant.core.exceptions import RadiantError

__all__ = [
    "DIFFRACTION_LIMITED",
    "DETECTOR_LIMITED",
    "NEAR_CRITICAL",
    "SamplingRegimeError",
    "classify_sampling_regime",
    "sampling_regime_label",
]

DETECTOR_LIMITED = 0.0
NEAR_CRITICAL = 1.0
DIFFRACTION_LIMITED = 2.0

_LABELS = {
    DETECTOR_LIMITED: "detector-limited",
    NEAR_CRITICAL: "near-critical",
    DIFFRACTION_LIMITED: "diffraction-limited",
}


class SamplingRegimeError(RadiantError):
    """Raised for out-of-range sampling-regime inputs."""


def classify_sampling_regime(q: float) -> float:
    """Classify the sampling parameter Q into a regime code.

    Returns 0.0 (detector-limited, Q < 1), 1.0 (near-critical, 1 ≤ Q ≤ 2),
    or 2.0 (diffraction-limited, Q > 2).
    """
    if q <= 0.0:
        raise SamplingRegimeError(f"Q must be positive, got {q}.")
    if q < 1.0:
        return DETECTOR_LIMITED
    if q <= 2.0:
        return NEAR_CRITICAL
    return DIFFRACTION_LIMITED


def sampling_regime_label(code: float) -> str:
    """Human-readable label for a regime code (0.0 / 1.0 / 2.0)."""
    if code not in _LABELS:
        raise SamplingRegimeError(f"unknown sampling-regime code {code}.")
    return _LABELS[code]
