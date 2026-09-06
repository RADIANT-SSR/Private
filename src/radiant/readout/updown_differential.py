"""Up/down differential counting — signed accumulator, capacity, reference noise.

Implements ``docs/plans/Digital_Pixel_Readout_Plan.md`` §2.4 (Gap 117
Phase 4, rulings D6/D7). The in-pixel counter becomes a **signed modulo
accumulator**: it increments during the scene (up) phase and decrements
during the reference (down) phase, ending at the differential

    ΔQ = Q_up − Q_down      [e-]

Counter wrap during the up phase is *not* a failure — modulo wrap is unwound
by the down phase — so the capacity constraint moves from rollover to the
signed differential:

    |ΔQ| ≤ 2^(N−1) · Q_pkt      [e-]

with clipping reported as ``"differential_overflow"``. The mean cancels
(background and dark for equal phases and reference = background) but the
noise does not: the down phase pays its own shot noise, σ_ref = √Q_down —
the up-to-√2 background-noise penalty vs a noiseless reference. Any model
subtracting the mean without adding reference-phase noise is flattering and
forbidden here (plan §2.4).

Signed count conversion uses floor semantics: ``n = floor(ΔQ/Q_pkt)`` with
``residue = ΔQ − n·Q_pkt ∈ [0, Q_pkt)`` — a two's-complement counter word
plus a non-negative analog residue, matching the D2 DN convention.

All quantities in canonical units: charge in e-, time in s.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from radiant.readout.errors import ReadoutValidationError

_MIN_BITS = 1
_MAX_BITS = 32


@dataclass(frozen=True)
class DifferentialResult:
    """Signed differential conversion result.

    Parameters
    ----------
    delta_q_e:
        Differential charge ΔQ [e-], clipped to ±2^(N−1)·Q_pkt.
    n_counts:
        Signed counter word ``floor(ΔQ/Q_pkt)`` (post-clip).
    residue_e:
        Non-negative analog residue [e-] in ``[0, Q_pkt)``.
    clipped:
        True when |ΔQ| exceeded the signed capacity (mechanism
        ``"differential_overflow"`` in stage outputs).
    """

    delta_q_e: float
    n_counts: int
    residue_e: float
    clipped: bool


def _validate_bits_packet(counter_bits: int, count_packet_e: float) -> None:
    if not (_MIN_BITS <= counter_bits <= _MAX_BITS):
        raise ReadoutValidationError(
            f"counter_bits = {counter_bits} is out of the valid domain "
            f"[{_MIN_BITS}, {_MAX_BITS}] for the signed accumulator."
        )
    if not math.isfinite(count_packet_e) or count_packet_e <= 0.0:
        raise ReadoutValidationError(
            f"count_packet_e = {count_packet_e} e- is invalid: the signed "
            f"differential needs a positive finite charge packet (0.0 is the "
            f"schema's 'unset' sentinel)."
        )


def differential_capacity_e(counter_bits: int, count_packet_e: float) -> float:
    """Signed differential capacity ``2^(N−1) × Q_pkt`` [e-] (plan §2.4)."""
    _validate_bits_packet(counter_bits, count_packet_e)
    return float(1 << (counter_bits - 1)) * count_packet_e


def updown_differential(
    q_up_e: float,
    q_down_e: float,
    *,
    counter_bits: int,
    count_packet_e: float,
) -> DifferentialResult:
    """Signed differential ΔQ = Q_up − Q_down, clipped at ±2^(N−1)·Q_pkt.

    Parameters
    ----------
    q_up_e:
        Scene-phase integrated charge [e-], ≥ 0 and finite.
    q_down_e:
        Reference-phase integrated charge [e-], ≥ 0 and finite.
    counter_bits:
        Counter depth N (1–32).
    count_packet_e:
        Charge packet per count Q_pkt [e-], > 0.
    """
    for label, q in (("up", q_up_e), ("down", q_down_e)):
        if not math.isfinite(q) or q < 0.0:
            raise ReadoutValidationError(
                f"{label}-phase charge = {q} e- is invalid: each phase's "
                f"integrated charge must be a non-negative finite electron "
                f"count."
            )
    _validate_bits_packet(counter_bits, count_packet_e)

    capacity = differential_capacity_e(counter_bits, count_packet_e)
    delta = q_up_e - q_down_e
    clipped = abs(delta) > capacity
    if clipped:
        delta = math.copysign(capacity, delta)

    n_counts = int(math.floor(delta / count_packet_e))
    residue = delta - n_counts * count_packet_e
    # Guard the half-open interval against float roundoff at exact multiples.
    if residue >= count_packet_e:
        n_counts += 1
        residue = 0.0
    elif residue < 0.0:
        residue = 0.0
    return DifferentialResult(
        delta_q_e=delta, n_counts=n_counts, residue_e=residue, clipped=clipped
    )


def reference_shot_noise_e(q_down_e: float) -> float:
    """Reference-phase shot noise ``√Q_down`` [e- RMS] (plan §2.4).

    The down phase's Poisson noise enters the budget in quadrature with the
    up-phase terms — the mean cancels, the noise does not.
    """
    if not math.isfinite(q_down_e) or q_down_e < 0.0:
        raise ReadoutValidationError(
            f"reference charge = {q_down_e} e- is invalid: the down-phase "
            f"integrated charge must be a non-negative finite electron count."
        )
    return math.sqrt(q_down_e)
