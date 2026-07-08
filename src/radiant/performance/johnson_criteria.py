"""Johnson-criteria DRI ranges — Detection, Recognition, Identification.

The Johnson criteria relate a discrimination task to the number of
resolved cycles (line pairs) across a target's critical dimension. A task
is achieved (at 50 % probability) when the sensor resolves at least the
task's N50 cycles across the target:

    N_cycles(R) = critical_dimension / (2 · GSD(R))
                = critical_dimension / (2 · IFOV · R)      (nadir, small angle)

so the range at which a task's N50 is met is

    R_task = critical_dimension / (2 · IFOV · N50_task).

One resolved cycle is one line pair, which requires two samples — hence the
factor of two (Nyquist). This is the sampling-limited form of the Johnson
model; it counts geometric cycles across the target and does NOT fold in
scene contrast or the sensor MTF (a full treatment couples cycles to the
minimum-resolvable-contrast/temperature curve). See the module's caller
for the fragility note.

Standard N50 cycle criteria (Johnson 1958, as tabulated in the NATO / U.S.
Army Night Vision literature) are provided in :data:`JOHNSON_N50`.
"""

from __future__ import annotations

from radiant.core.exceptions import RadiantError

__all__ = [
    "JOHNSON_N50",
    "JohnsonCriteriaError",
    "johnson_range_m",
    "resolved_cycles",
]

# Johnson N50 cycle criteria across the target's critical dimension.
# Detection = "something is there", Recognition = "what class of object",
# Identification = "which specific object". Orientation is included for
# completeness. Values are the widely tabulated 50 %-probability figures.
JOHNSON_N50: dict[str, float] = {
    "detection": 1.0,
    "orientation": 1.4,
    "recognition": 4.0,
    "identification": 6.4,
}


class JohnsonCriteriaError(RadiantError):
    """Raised for out-of-range Johnson-criteria inputs."""


def _validate(critical_dimension_m: float, ifov_rad: float) -> None:
    if critical_dimension_m <= 0.0:
        raise JohnsonCriteriaError(
            f"critical_dimension_m must be positive, got {critical_dimension_m}."
        )
    if ifov_rad <= 0.0:
        raise JohnsonCriteriaError(f"ifov_rad must be positive, got {ifov_rad}.")


def resolved_cycles(critical_dimension_m: float, ifov_rad: float, range_m: float) -> float:
    """Cycles (line pairs) resolved across the target at *range_m*.

    N = critical_dimension / (2 · IFOV · range). One cycle per two ground
    samples (Nyquist).
    """
    _validate(critical_dimension_m, ifov_rad)
    if range_m <= 0.0:
        raise JohnsonCriteriaError(f"range_m must be positive, got {range_m}.")
    gsd_m = ifov_rad * range_m
    return critical_dimension_m / (2.0 * gsd_m)


def johnson_range_m(
    critical_dimension_m: float,
    ifov_rad: float,
    n50_cycles: float,
) -> float:
    """Range [m] at which *n50_cycles* are resolved across the target.

    R = critical_dimension / (2 · IFOV · N50). Larger targets, finer IFOV,
    or easier tasks (fewer required cycles) all push the range out.

    Parameters
    ----------
    critical_dimension_m:
        Target critical dimension [m] (conventionally √(height·width) or
        the minimum resolvable dimension for the task).
    ifov_rad:
        Instantaneous field of view [rad] = pixel_pitch / focal_length.
    n50_cycles:
        Required resolved cycles for the task (see :data:`JOHNSON_N50`).
    """
    _validate(critical_dimension_m, ifov_rad)
    if n50_cycles <= 0.0:
        raise JohnsonCriteriaError(f"n50_cycles must be positive, got {n50_cycles}.")
    return critical_dimension_m / (2.0 * ifov_rad * n50_cycles)
