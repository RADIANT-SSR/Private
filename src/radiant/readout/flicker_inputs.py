"""Resolve the 1/f model's band inputs from the configured timing (CU-381).

:mod:`radiant.readout.flicker_transfer` is pure numerics: it takes an explicit
band and returns a variance. This module turns the schema's three *optional*
band parameters into that explicit band, which is a separate concern (Rule 19)
and the one that has to speak up when an input is missing.

Resolution rules
----------------
``detector.flicker_f_low_hz`` (0 = unset)
    Derived as ``1 / (n_coadds * frame_period_s)`` -- the reciprocal of the
    stack duration, which is the longest timescale the measurement is compared
    over. See ``flicker_transfer``'s docstring for why this cannot be derived
    away entirely for an un-referenced sum.

``detector.flicker_corner_hz`` (0 = unset)
    No universal value exists; it is a measured ROIC property. Unset with
    ``flicker_K > 0``, the band runs to the boxcar roll-off instead, which
    **overstates** the term -- the power above the real corner gets billed
    twice, once as flicker and once as read noise -- and a ``UserWarning`` says
    so. Overstating noise is the safe direction for an input nobody supplied;
    silently inventing a corner is not.

``detector.flicker_f_high_hz`` (0 = unset)
    An extra clamp, rarely needed, since the boxcar already rolls off at
    ``~1/t_int``.
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass

__all__ = ["FlickerBand", "resolve_flicker_band"]

#: Multiple of the boxcar roll-off frequency (1/t_int) used as the upper limit
#: when no corner frequency is supplied. Three decades past the roll-off the
#: sinc^2 weight has fallen by ~1e6 and contributes nothing further.
_BOXCAR_SPAN: float = 1.0e3


@dataclass(frozen=True)
class FlickerBand:
    """The explicit band ``flicker_transfer.flicker_noise_e`` needs."""

    f_low_hz: float
    corner_hz: float
    corner_was_supplied: bool


def resolve_flicker_band(
    *,
    flicker_K_e2: float,
    f_low_hz: float,
    corner_hz: float,
    f_high_hz: float,
    t_int_s: float,
    frame_period_s: float,
    n_coadds: int,
    warn: bool = True,
) -> FlickerBand:
    """Turn the three optional band parameters into an explicit band.

    Parameters are the raw schema values; 0.0 means unset for all three band
    parameters. ``warn=False`` suppresses the missing-corner advisory for
    callers that have already reported it.
    """
    if f_low_hz > 0.0:
        resolved_low = f_low_hz
    else:
        total_s = n_coadds * frame_period_s
        resolved_low = 1.0 / total_s

    corner_supplied = corner_hz > 0.0
    if corner_supplied:
        resolved_corner = corner_hz
    else:
        resolved_corner = _BOXCAR_SPAN / t_int_s
        if warn and flicker_K_e2 > 0.0:
            warnings.warn(
                f"ReadoutStage: detector.flicker_K = {flicker_K_e2:g} e-² is set but "
                f"detector.flicker_corner_hz is not, so the 1/f band runs to the "
                f"integration-time roll-off ({resolved_corner:g} Hz) instead of stopping "
                f"at the white-noise floor. The reported flicker_1f is therefore an "
                f"UPPER BOUND: power above the real corner is charged twice, once here "
                f"and once as read noise (measured overstatement 64–170 % at 30–120 Hz "
                f"for a 200 Hz corner). Set detector.flicker_corner_hz to the measured "
                f"ROIC corner frequency.",
                UserWarning,
                stacklevel=3,
            )

    if f_high_hz > 0.0:
        resolved_corner = min(resolved_corner, f_high_hz)

    return FlickerBand(
        f_low_hz=resolved_low,
        corner_hz=resolved_corner,
        corner_was_supplied=corner_supplied,
    )
