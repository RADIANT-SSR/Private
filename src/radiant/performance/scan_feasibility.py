"""Pushbroom / TDI scan-timing feasibility (Gap 74, minimum slice).

The full scan/timing subsystem (`ScanMode`, line-rate derivation, cross-track
and target-motion smear) is not implemented. This module provides the one
feasibility guard the audit flagged as silently missing: the requested
integration time must not exceed the per-line **dwell time**, or the
along-track image smear exceeds one ground sample and the TDI timing is
unphysical — yet the reported SNR would still look authoritative.

For a pushbroom sensor the ground advances one along-track ground sample
distance (GSD) in the dwell time::

    t_dwell = GSD_along / v_ground

Each TDI stage must integrate within one dwell (the charge is clocked one
row per dwell to track the moving image). The configured per-stage
``spectral_integration.integration_time_s`` must therefore satisfy
``t_int ≤ t_dwell``; a longer integration smears the target across more than
one pixel per stage, breaking TDI registration.
"""

from __future__ import annotations

from dataclasses import dataclass

from radiant.performance.errors import PerformanceValidationError


@dataclass(frozen=True)
class ScanFeasibility:
    """Result of the pushbroom/TDI dwell-time feasibility check.

    Attributes
    ----------
    max_integration_time_s:
        Longest per-stage integration keeping along-track smear ≤ one
        ground sample (``GSD_along / v_ground``).
    requested_integration_time_s:
        The configured ``spectral_integration.integration_time_s``.
    smear_pixels:
        Along-track image smear during the requested integration, in
        pixels (``t_int / t_dwell``).
    feasible:
        ``True`` when ``requested ≤ max`` (smear ≤ one pixel).
    """

    max_integration_time_s: float
    requested_integration_time_s: float
    smear_pixels: float
    feasible: bool


def scan_feasibility(
    gsd_along_track_m: float,
    ground_velocity_m_s: float,
    integration_time_s: float,
) -> ScanFeasibility:
    """Check the pushbroom/TDI dwell-time constraint (Gap 74).

    Parameters
    ----------
    gsd_along_track_m:
        Along-track ground sample distance [m].
    ground_velocity_m_s:
        Platform along-track ground velocity [m/s]. Must be positive.
    integration_time_s:
        Configured per-stage integration time [s].

    Returns
    -------
    ScanFeasibility

    Raises
    ------
    PerformanceValidationError
        If any input is non-positive.
    """
    if gsd_along_track_m <= 0.0:
        raise PerformanceValidationError(
            f"gsd_along_track_m must be positive, got {gsd_along_track_m}"
        )
    if ground_velocity_m_s <= 0.0:
        raise PerformanceValidationError(
            f"ground_velocity_m_s must be positive, got {ground_velocity_m_s}"
        )
    if integration_time_s <= 0.0:
        raise PerformanceValidationError(
            f"integration_time_s must be positive, got {integration_time_s}"
        )

    t_dwell = gsd_along_track_m / ground_velocity_m_s
    smear_pixels = integration_time_s / t_dwell
    return ScanFeasibility(
        max_integration_time_s=t_dwell,
        requested_integration_time_s=integration_time_s,
        smear_pixels=smear_pixels,
        feasible=integration_time_s <= t_dwell,
    )
