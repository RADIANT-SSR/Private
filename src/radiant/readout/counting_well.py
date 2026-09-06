"""Digital-pixel counting well — effective well, dead-time ceiling, count conversion.

Implements ``docs/archive/Digital_Pixel_Readout_Plan.md`` §2.1 and §2.3 (Gap 117
Phase 1). The in-pixel comparator + N-bit counter with charge-subtraction
reset gives an effective well

    Q_eff = 2^N · Q_pkt      [e-]

with counter rollover treated as saturation (clip, ruling D1) and an optional
comparator dead-time flux ceiling

    Q_dead = f_max · t_int · Q_pkt      [e-]

so the counting saturation bound is Q_sat = min(Q_eff, Q_dead). Integrated
charge converts to a counter word and an analog residue:

    n_counts = floor(Q_int / Q_pkt),   Q_res = Q_int mod Q_pkt

All quantities in canonical units: charge in e-, rates in Hz, time in s.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from radiant.readout.errors import ReadoutValidationError

# Schema bounds for readout.counter_bits (kept in lock-step with _schema.py;
# re-validated here because these are pure functions callable outside a
# ParameterSet, Rule 16).
_MIN_BITS = 1
_MAX_BITS = 32


@dataclass(frozen=True)
class CountConversion:
    """Result of converting integrated charge to a counter word + residue.

    Parameters
    ----------
    n_counts:
        Comparator trip count (exact integer, pre-clip).
    residue_e:
        Sub-packet analog residue [e-], in ``[0, count_packet_e)``.
    """

    n_counts: int
    residue_e: float


def _validate_packet(count_packet_e: float) -> None:
    if not math.isfinite(count_packet_e) or count_packet_e <= 0.0:
        raise ReadoutValidationError(
            f"count_packet_e = {count_packet_e} e- is invalid: the charge "
            f"packet per count must be a positive finite number of electrons. "
            f"0.0 is the schema's 'unset' sentinel — set "
            f"readout.count_packet_e to the ROIC's charge-subtraction "
            f"quantum before computing counting physics."
        )


def _validate_bits(counter_bits: int) -> None:
    if not (_MIN_BITS <= counter_bits <= _MAX_BITS):
        raise ReadoutValidationError(
            f"counter_bits = {counter_bits} is out of the valid domain "
            f"[{_MIN_BITS}, {_MAX_BITS}]: an in-pixel counter needs at least "
            f"one bit, and no fielded DROIC exceeds 32."
        )


def effective_well_e(counter_bits: int, count_packet_e: float) -> float:
    """Effective well depth ``2^N × Q_pkt`` [e-].

    Parameters
    ----------
    counter_bits:
        Counter depth N (1–32).
    count_packet_e:
        Charge packet per count Q_pkt [e-], > 0.
    """
    _validate_bits(counter_bits)
    _validate_packet(count_packet_e)
    return float(1 << counter_bits) * count_packet_e


def dead_time_ceiling_e(
    max_count_rate_hz: float,
    integration_time_s: float,
    count_packet_e: float,
) -> float | None:
    """Comparator dead-time charge ceiling ``f_max · t_int · Q_pkt`` [e-].

    Parameters
    ----------
    max_count_rate_hz:
        Maximum in-pixel count rate f_max [Hz]. ``0.0`` is the schema's
        'unset' sentinel — returns ``None`` (no dead-time ceiling; the
        rollover bound alone governs).
    integration_time_s:
        Integration time t_int [s], > 0.
    count_packet_e:
        Charge packet per count Q_pkt [e-], > 0.
    """
    if not math.isfinite(max_count_rate_hz) or max_count_rate_hz < 0.0:
        raise ReadoutValidationError(
            f"max_count_rate_hz = {max_count_rate_hz} Hz is invalid: the "
            f"comparator dead-time ceiling must be a non-negative finite "
            f"rate (0.0 = no ceiling)."
        )
    if not math.isfinite(integration_time_s) or integration_time_s <= 0.0:
        raise ReadoutValidationError(
            f"integration_time_s = {integration_time_s} s is invalid: the "
            f"dead-time charge ceiling is defined per integration and needs "
            f"a positive finite integration time."
        )
    _validate_packet(count_packet_e)
    if max_count_rate_hz == 0.0:
        return None
    return max_count_rate_hz * integration_time_s * count_packet_e


def counting_saturation(
    counter_bits: int,
    count_packet_e: float,
    max_count_rate_hz: float,
    integration_time_s: float,
) -> tuple[float, str]:
    """Counting saturation bound and its governing mechanism.

    Q_sat = min(2^N·Q_pkt, f_max·t_int·Q_pkt), plan §2.3. On an exact tie
    the mechanism reports ``"rollover"`` — the counter physically stops.

    Returns
    -------
    tuple[float, str]
        ``(Q_sat [e-], mechanism)`` with mechanism ``"rollover"`` or
        ``"dead_time"``. Whether the pixel actually saturates (mechanism
        ``"none"`` in stage outputs) is the caller's comparison of the
        integrated charge against this bound.
    """
    q_rollover = effective_well_e(counter_bits, count_packet_e)
    q_dead = dead_time_ceiling_e(max_count_rate_hz, integration_time_s, count_packet_e)
    if q_dead is not None and q_dead < q_rollover:
        return q_dead, "dead_time"
    return q_rollover, "rollover"


def packet_reset_noise_e(n_counts: int, sigma_ktc_e: float) -> float:
    """Accumulated charge-subtraction reset noise ``√n_counts · σ_kTC`` [e- RMS].

    Each comparator trip resets the integration node, injecting one kTC
    noise sample; n independent resets accumulate in quadrature (plan §2.2).
    The caller passes the per-reset kTC noise already CDS-gated (the raw
    ``ktc_reset`` budget term is 0 when ``readout.cds_enabled`` — same gate).

    Parameters
    ----------
    n_counts:
        Number of comparator trips this integration, ≥ 0.
    sigma_ktc_e:
        Per-reset kTC noise [e- RMS], ≥ 0 (0 when CDS is on).
    """
    if n_counts < 0:
        raise ReadoutValidationError(
            f"n_counts = {n_counts} is invalid: the comparator trip count cannot be negative."
        )
    if not math.isfinite(sigma_ktc_e) or sigma_ktc_e < 0.0:
        raise ReadoutValidationError(
            f"sigma_ktc_e = {sigma_ktc_e} e- RMS is invalid: the per-reset "
            f"kTC noise must be a non-negative finite value."
        )
    return math.sqrt(float(n_counts)) * sigma_ktc_e


def convert_to_counts(charge_e: float, count_packet_e: float) -> CountConversion:
    """Convert integrated charge to counter word + analog residue (plan §2.1).

    Parameters
    ----------
    charge_e:
        Integrated charge Q_int [e-], ≥ 0 and finite (Rule 16: the caller
        resolves NaN/inf and sign before counting physics).
    count_packet_e:
        Charge packet per count Q_pkt [e-], > 0.
    """
    if not math.isfinite(charge_e) or charge_e < 0.0:
        raise ReadoutValidationError(
            f"charge = {charge_e} e- is invalid: the integrated charge "
            f"entering the counter must be a non-negative finite electron "
            f"count."
        )
    _validate_packet(count_packet_e)
    n_counts = int(charge_e // count_packet_e)
    residue_e = charge_e - n_counts * count_packet_e
    # Guard the half-open interval against float roundoff at exact multiples
    # (residue must satisfy 0 <= residue < Q_pkt).
    if residue_e >= count_packet_e:
        n_counts += 1
        residue_e = 0.0
    elif residue_e < 0.0:
        residue_e = 0.0
    return CountConversion(n_counts=n_counts, residue_e=residue_e)
