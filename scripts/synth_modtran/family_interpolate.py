"""Lightweight per-family atmosphere interpolation — NOT a general database.

Design rationale (see conversation record / docs/archive/MODTRAN_Run_Matrix_Plan.md):
the 39-run matrix is not a dense N-D grid you could query at an arbitrary
point — it is several small, deliberately single-axis FAMILIES (the
B-block only varies zenith angle at fixed altitude; the C/G-blocks only
vary target altitude at fixed sensor/zenith). A general N-D interpolation
database (RADIANT already has one: `radiant.atmosphere.interpolated.
InterpolatedAtmosphere`) is the right tool for a genuine multi-dimensional
grid; it is NOT warranted here, where every family answers exactly one
question along exactly one axis.

This module does the simplest thing that is still correct: given a named
family (a fixed set of runs sharing every geometry axis except one) and a
query value on that one free axis, it interpolates LOG-transmittance
linearly (physically correct under Beer-Lambert — matches
InterpolatedAtmosphere's own convention) and path radiance linearly,
between the two bracketing runs. It refuses to extrapolate outside the
family's covered range — same "no silently invented data" discipline as
InterpolatedAtmosphere.

Families are a small, explicit, hand-curated registry (FAMILIES below),
not auto-detected from the CSV — auto-detection would be exactly the
unwarranted complexity the design conversation rejected.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np

from radiant.atmosphere.modtran import Tape7Reader

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_SYNTH_DIR = _REPO_ROOT / "modtran" / "synthetic"


@dataclass(frozen=True)
class Family:
    """A set of runs sharing every geometry axis except one continuous one."""

    name: str
    axis_name: str
    axis_unit: str
    run_ids: tuple[str, ...]
    axis_values: tuple[float, ...]
    fixed_geometry: str  # human-readable description of what's held constant

    def __post_init__(self) -> None:
        if len(self.run_ids) != len(self.axis_values):
            raise ValueError(f"Family {self.name}: run_ids and axis_values length mismatch")
        if list(self.axis_values) != sorted(self.axis_values):
            raise ValueError(f"Family {self.name}: axis_values must be ascending")


# Hand-curated from docs/plans/modtran_run_matrix.csv. Only families with
# a single clean continuous free axis are included -- e.g. the A-block
# (profile) is NOT here: profile is categorical, not a continuous
# physical quantity, so "interpolating between us_standard and tropical"
# is not a meaningful operation.
FAMILIES: dict[str, Family] = {
    "zenith_fan_us_standard": Family(
        name="zenith_fan_us_standard",
        axis_name="path_zenith_deg",
        axis_unit="deg",
        run_ids=("A1", "B1", "B2", "B3"),
        axis_values=(0.0, 30.0, 45.0, 60.0),
        fixed_geometry="us_standard profile, sensor_altitude=100km, target_altitude=0km",
    ),
    "altitude_ladder_stratospheric": Family(
        name="altitude_ladder_stratospheric",
        axis_name="target_altitude_km",
        axis_unit="km",
        run_ids=("C1", "C2", "C3", "C4", "C5", "C6"),
        axis_values=(0.0, 1.0, 5.0, 10.0, 20.0, 29.0),
        fixed_geometry="midlat_summer profile, sensor_altitude=35km, nadir",
    ),
    "altitude_ladder_space": Family(
        name="altitude_ladder_space",
        axis_name="target_altitude_km",
        axis_unit="km",
        run_ids=("G1", "G2", "G3", "G4", "G5"),
        axis_values=(1.0, 5.0, 10.0, 20.0, 29.0),
        fixed_geometry="midlat_summer profile, sensor_altitude=100km, nadir",
    ),
}


class FamilyInterpolationError(ValueError):
    """Raised when a query cannot be served by any family without extrapolating."""


def _load_tape7(run_id: str) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    tape7 = _SYNTH_DIR / f"{run_id}.synthetic.tp7"
    if not tape7.exists():
        raise FileNotFoundError(
            f"{tape7} not found. Generate it first:\n"
            f"  python scripts/generate_synthetic_tape7.py --run-id {run_id}"
        )
    import warnings

    with warnings.catch_warnings():
        warnings.simplefilter("error")
        wl_um, trans, path_radiance, _gr = Tape7Reader(tape7).to_radiant_units()
    return wl_um, trans, path_radiance


def interpolate_family(
    family_name: str, query_value: float
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Interpolate a family's transmittance + path radiance to a query point.

    Returns (wavelength_um, transmittance, path_radiance_W_m2_sr_um) on
    the bracketing runs' shared wavelength grid.

    Raises FamilyInterpolationError if query_value falls outside the
    family's covered axis range (no extrapolation, matching
    InterpolatedAtmosphere's own convention).
    """
    if family_name not in FAMILIES:
        raise FamilyInterpolationError(
            f"Unknown family {family_name!r}. Available: {sorted(FAMILIES)}"
        )
    family = FAMILIES[family_name]
    values = family.axis_values

    if query_value < values[0] or query_value > values[-1]:
        raise FamilyInterpolationError(
            f"{family_name}: query {family.axis_name}={query_value} {family.axis_unit} "
            f"is outside the covered range [{values[0]}, {values[-1]}] {family.axis_unit} "
            f"({family.fixed_geometry}). Interpolation does not extrapolate."
        )

    # Exact hit -- no interpolation needed.
    if query_value in values:
        idx = values.index(query_value)
        wl_um, trans, path_radiance = _load_tape7(family.run_ids[idx])
        return wl_um, trans, path_radiance

    # Bracket.
    hi_idx = next(i for i, v in enumerate(values) if v > query_value)
    lo_idx = hi_idx - 1
    frac = (query_value - values[lo_idx]) / (values[hi_idx] - values[lo_idx])

    wl_lo, trans_lo, lp_lo = _load_tape7(family.run_ids[lo_idx])
    wl_hi, trans_hi, lp_hi = _load_tape7(family.run_ids[hi_idx])
    if not np.array_equal(wl_lo, wl_hi):
        raise FamilyInterpolationError(
            f"{family_name}: bracketing runs {family.run_ids[lo_idx]}/"
            f"{family.run_ids[hi_idx]} are on different wavelength grids -- "
            "cannot interpolate directly."
        )

    # Log-transmittance interpolation (Beer-Lambert-consistent, matches
    # InterpolatedAtmosphere's own convention); path radiance linear.
    log_tau_lo = np.log(np.clip(trans_lo, 1e-300, 1.0))
    log_tau_hi = np.log(np.clip(trans_hi, 1e-300, 1.0))
    log_tau_interp = log_tau_lo + frac * (log_tau_hi - log_tau_lo)
    trans_interp = np.exp(log_tau_interp)
    path_radiance_interp = lp_lo + frac * (lp_hi - lp_lo)

    return wl_lo, trans_interp, path_radiance_interp
