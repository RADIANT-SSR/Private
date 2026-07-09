"""Multi-frame persistence — residual (ghost) signal decay over a sequence.

After a bright exposure fills charge traps, a detector releases that charge
over subsequent frames as a decaying residual (ghost) signal. The
single-frame noise term (`detector.noise.other.persistence_noise`) gives
only one frame's contribution; this module models the temporal sequence
that scenario 2.4 needs.

Model — the residual signal in frame *n* after a bright prior exposure of
``prior_signal_e`` decays exponentially with the trap time constant τ:

    residual_e(n) = prior_signal_e · f · exp(−(n−1)·Δt_frame / τ)

where ``f`` (``persistence_fraction``) is the residual fraction remaining
in the first frame after the bright exposure and ``Δt_frame`` is the frame
interval. Each frame's residual carries shot noise ``√residual_e``. The
ghost is cleared once the residual drops below one LSB (``gain_e_per_dn``).
"""

from __future__ import annotations

import math

import numpy as np
import numpy.typing as npt

from radiant.core.exceptions import RadiantError

__all__ = [
    "PersistenceSequenceError",
    "frames_to_clear",
    "persistence_residual_e",
    "persistence_residual_sequence_e",
]


class PersistenceSequenceError(RadiantError):
    """Raised for out-of-range persistence-sequence inputs."""


def _validate(
    prior_signal_e: float, persistence_fraction: float, tau_s: float, frame_interval_s: float
) -> None:
    if prior_signal_e < 0.0:
        raise PersistenceSequenceError(f"prior_signal_e must be ≥ 0, got {prior_signal_e}.")
    if not 0.0 <= persistence_fraction <= 1.0:
        raise PersistenceSequenceError(
            f"persistence_fraction must be in [0, 1], got {persistence_fraction}."
        )
    if tau_s <= 0.0:
        raise PersistenceSequenceError(f"persistence_tau_s must be positive, got {tau_s}.")
    if frame_interval_s <= 0.0:
        raise PersistenceSequenceError(
            f"frame_interval_s must be positive, got {frame_interval_s}."
        )


def persistence_residual_e(
    prior_signal_e: float,
    persistence_fraction: float,
    persistence_tau_s: float,
    frame_interval_s: float,
    frame_number: int,
) -> float:
    """Residual (ghost) signal [e-] in frame *frame_number* (1-indexed).

    ``prior_signal_e · f · exp(−(n−1)·Δt / τ)``.
    """
    _validate(prior_signal_e, persistence_fraction, persistence_tau_s, frame_interval_s)
    if frame_number < 1:
        raise PersistenceSequenceError(f"frame_number must be ≥ 1, got {frame_number}.")
    decay = math.exp(-(frame_number - 1) * frame_interval_s / persistence_tau_s)
    return prior_signal_e * persistence_fraction * decay


def persistence_residual_sequence_e(
    prior_signal_e: float,
    persistence_fraction: float,
    persistence_tau_s: float,
    frame_interval_s: float,
    n_frames: int,
) -> npt.NDArray[np.float64]:
    """Residual signal [e-] for frames 1..``n_frames`` (1-indexed)."""
    if n_frames < 1:
        raise PersistenceSequenceError(f"n_frames must be ≥ 1, got {n_frames}.")
    _validate(prior_signal_e, persistence_fraction, persistence_tau_s, frame_interval_s)
    n = np.arange(n_frames, dtype=np.float64)  # 0..n_frames-1
    decay = np.exp(-n * frame_interval_s / persistence_tau_s)
    return prior_signal_e * persistence_fraction * decay


def frames_to_clear(
    prior_signal_e: float,
    persistence_fraction: float,
    persistence_tau_s: float,
    frame_interval_s: float,
    threshold_e: float,
) -> int:
    """Number of frames until the residual first drops below ``threshold_e``.

    Returns the 1-indexed frame number n at which
    ``residual_e(n) < threshold_e`` (e.g. threshold = gain_e_per_dn = 1 LSB).
    Returns 1 if the first frame is already below threshold.
    """
    _validate(prior_signal_e, persistence_fraction, persistence_tau_s, frame_interval_s)
    if threshold_e <= 0.0:
        raise PersistenceSequenceError(f"threshold_e must be positive, got {threshold_e}.")
    first = prior_signal_e * persistence_fraction
    if first < threshold_e:
        return 1
    # residual(n) = first · exp(−(n−1)Δt/τ) < threshold
    # ⇒ n − 1 > τ/Δt · ln(first/threshold)
    n_minus_1 = (persistence_tau_s / frame_interval_s) * math.log(first / threshold_e)
    return int(math.ceil(n_minus_1)) + 1
