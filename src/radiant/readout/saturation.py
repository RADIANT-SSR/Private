"""Dual saturation checks — well capacity and ADC dynamic range.

Per ``docs/RADIANT_Detector_Complete.md`` §6, RADIANT has two
independent saturation points:

1. **Well capacity** (analog, after TDI accumulation): signal clipped
   at ``full_well_capacity_e``.
2. **ADC saturation** (digital, after gain conversion): signal clipped
   at ``2^n_bits - 1`` DN.

Both are hard clips. A frame can saturate at one without saturating
the other.
"""

from __future__ import annotations

import enum


class SaturationStatus(enum.Enum):
    """Saturation check result."""

    OK = "ok"
    CLIPPED = "clipped"


def check_well_saturation(
    signal_e: float,
    full_well_capacity_e: float,
) -> tuple[float, SaturationStatus]:
    """Check and clip signal against well capacity.

    Parameters
    ----------
    signal_e:
        Accumulated signal in electrons (post-TDI, post-binning).
    full_well_capacity_e:
        Full well capacity [e-]. Must be > 0.

    Returns
    -------
    tuple[float, SaturationStatus]
        (clipped_signal_e, status). If ``signal_e > FWC``, the signal
        is clipped to FWC and status is CLIPPED.
    """
    if full_well_capacity_e <= 0.0:
        raise ValueError(
            f"check_well_saturation: full_well_capacity_e = {full_well_capacity_e} must be > 0."
        )
    if signal_e <= full_well_capacity_e:
        return signal_e, SaturationStatus.OK
    return full_well_capacity_e, SaturationStatus.CLIPPED


def check_adc_saturation(
    signal_dn: float,
    max_dn: int,
) -> tuple[float, SaturationStatus]:
    """Check and clip digital signal against ADC full scale.

    Parameters
    ----------
    signal_dn:
        Signal in digital numbers (after gain conversion).
    max_dn:
        Maximum ADC output (``2^n_bits - 1``). Must be > 0.

    Returns
    -------
    tuple[float, SaturationStatus]
        (clipped_dn, status). If ``signal_dn > max_dn``, clipped to
        max_dn and status is CLIPPED.
    """
    if max_dn <= 0:
        raise ValueError(f"check_adc_saturation: max_dn = {max_dn} must be > 0.")
    if signal_dn <= float(max_dn):
        return signal_dn, SaturationStatus.OK
    return float(max_dn), SaturationStatus.CLIPPED
