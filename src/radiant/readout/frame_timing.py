"""Frame-rate / duty-cycle derivation (RADIANT_Conventions.md §4).

Integration time and frame period are independent quantities: integration time
is how long charge accumulates; the frame period is the time between frame
starts. This module derives the frame rate and duty cycle from the two,
implementing the §4 contract:

    frame_rate = 1 / frame_period
    duty_cycle = t_int / frame_period            (0 < duty_cycle ≤ 1)

If only the integration time is given (``frame_period_s`` unset, i.e. ≤ 0),
the frame period defaults to the integration time — frame rate = 1/t_int,
duty cycle = 1.0 (continuous readout, no dead time) — with a logged warning,
exactly as §4 specifies. A duty cycle > 1 (integration longer than the frame
period) is physically impossible and raises (Rule 15/17); nothing is clamped
silently.

Rule 19 — this module owns exactly the frame-timing derivation.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from radiant.readout.errors import ReadoutValidationError

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class FrameTiming:
    """Derived frame timing in canonical units.

    Attributes
    ----------
    frame_period_s:
        Time between frame starts [s]. Equals the integration time when the
        frame period was unset.
    frame_rate_hz:
        Frame rate [Hz] = 1 / frame_period_s.
    duty_cycle:
        Integration duty cycle = t_int / frame_period_s, in (0, 1]. 1.0 means
        continuous readout (no dead time between frames).
    frame_period_defaulted:
        True when ``frame_period_s`` was unset on input and defaulted to the
        integration time (duty cycle 1.0) — the case that logs a warning.
    """

    frame_period_s: float
    frame_rate_hz: float
    duty_cycle: float
    frame_period_defaulted: bool


def compute_frame_timing(
    integration_time_s: float, frame_period_s: float, *, warn: bool = True
) -> FrameTiming:
    """Derive ``FrameTiming`` from integration time and (optional) frame period.

    Parameters
    ----------
    integration_time_s:
        Integration time ``t_int`` [s]. Must be strictly positive.
    frame_period_s:
        Frame period [s]. ``≤ 0`` means *unset* — the frame period defaults to
        ``integration_time_s`` (duty cycle 1.0), and (when ``warn``) logs the
        §4 warning.
    warn:
        Emit the §4 "defaulting to 1/t_int" logged warning when the frame
        period is unset. Default ``True`` for direct/API callers. The chain
        (``ReadoutStage``) passes ``warn=False`` so an ordinary default-config
        evaluation stays warning-free (CU-166 bar) — the unset case is instead
        surfaced by :attr:`FrameTiming.frame_period_defaulted` in the readout
        stage outputs.

    Returns
    -------
    FrameTiming

    Raises
    ------
    ReadoutValidationError
        If ``integration_time_s ≤ 0``, or the frame period is set but shorter
        than the integration time (duty cycle > 1, physically impossible).
    """
    if integration_time_s <= 0.0:
        raise ReadoutValidationError(
            f"compute_frame_timing: integration_time_s = {integration_time_s} s is invalid. "
            "Integration time must be strictly positive. Set "
            "spectral_integration.integration_time_s > 0."
        )

    if frame_period_s <= 0.0:
        # Unset: default the frame period to the integration time (§4).
        if warn:
            logger.warning(
                "readout.frame_period_s is unset; defaulting the frame period to the "
                "integration time t_int = %.6g s (frame rate = 1/t_int = %.6g Hz, "
                "duty cycle = 1.0). Set readout.frame_period_s to model dead time "
                "between frames.",
                integration_time_s,
                1.0 / integration_time_s,
            )
        return FrameTiming(
            frame_period_s=integration_time_s,
            frame_rate_hz=1.0 / integration_time_s,
            duty_cycle=1.0,
            frame_period_defaulted=True,
        )

    duty_cycle = integration_time_s / frame_period_s
    if duty_cycle > 1.0:
        raise ReadoutValidationError(
            f"compute_frame_timing: duty cycle = t_int/frame_period = "
            f"{integration_time_s} / {frame_period_s} = {duty_cycle:.4g} > 1. "
            "The integration time cannot exceed the frame period. Increase "
            "readout.frame_period_s (≥ t_int) or reduce "
            "spectral_integration.integration_time_s."
        )

    return FrameTiming(
        frame_period_s=frame_period_s,
        frame_rate_hz=1.0 / frame_period_s,
        duty_cycle=duty_cycle,
        frame_period_defaulted=False,
    )
