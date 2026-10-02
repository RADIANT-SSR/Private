"""Derived quantities, labelled and unit-bearing (Gap 134).

The external review's observation: *"Anything RADIANT computed from user input
is exactly what an external model will disagree about."* Its worked case was
`Omega_cone` — RADIANT uses the exact étendue cone
``2π(1 − cos(arctan(1/2N)))`` while hand-built models commonly use the paraxial
``π/(4N²)``, which is 18.4 % high at f/1. That single ratio accounted for an
entire warm-optics discrepancy in the reconciliation, and it was reachable only
by digging in ``stage_outputs``.

So this module answers: **what did RADIANT work out for itself, and from
which door?** Each entry carries a value, a unit, and a one-line source — never
a bare number, because a bare number is what forced the hand-arithmetic this
gap exists to remove.

It computes almost nothing. Nearly every entry is a value another stage already
published; the exceptions are the two the chain genuinely never exposed — the
IFOV that :mod:`radiant.performance.johnson_criteria` already *consumes*, and
the band-mean transmittance scenario 3.2 had to compute by hand. Those live in
their own modules (Rule 19) and are called here.

Four rows from the CU-387 scenario triage fold in here, because they were one
complaint wearing four hats: an effective integration time, a scalar band-mean
τ, a first-class total-noise value, and an MTF budget reachable only by
string-parsing ``*_x``/``*_y`` key suffixes.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

__all__ = ["DerivedQuantity", "collect_derived_quantities"]


@dataclass(frozen=True, slots=True)
class DerivedQuantity:
    """One value RADIANT worked out, with its unit and where it came from."""

    name: str
    value: float
    unit: str
    source: str

    def __str__(self) -> str:
        unit = f" {self.unit}" if self.unit else ""
        return f"{self.name} = {self.value:.6g}{unit}  [{self.source}]"


def _num(value: Any) -> float | None:
    """A finite float, or None — so a partial chain yields fewer rows, not junk."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    out = float(value)
    return out if math.isfinite(out) else None


def collect_derived_quantities(
    stage_outputs: Mapping[str, Mapping[str, Any]],
    *,
    ifov_x_rad: float | None = None,
    ifov_y_rad: float | None = None,
    tau_atm_band_mean: float | None = None,
    tau_opt_band_mean: float | None = None,
    t_int_effective_s: float | None = None,
    dark_rate_from_density: bool = False,
) -> tuple[DerivedQuantity, ...]:
    """Collect the derived values worth echoing, in reading order.

    A quantity absent from ``stage_outputs`` is simply omitted: this runs on
    partial chains too, and a row reading ``None`` would be noise. Order is
    chosen for a reader working outward from the optics, not alphabetical.
    """
    optics = stage_outputs.get("optics", {})
    readout = stage_outputs.get("readout", {})
    detector = stage_outputs.get("detector", {})

    rows: list[DerivedQuantity] = []

    def add(name: str, value: Any, unit: str, source: str) -> None:
        num = _num(value)
        if num is not None:
            rows.append(DerivedQuantity(name, num, unit, source))

    # --- Optics: the étendue cone is the review's own worked case ---
    add(
        "Omega_cone",
        optics.get("Omega_cone"),
        "sr",
        "exact etendue 2*pi*(1-cos(arctan(1/2N))) at the post-cold-stop f/# "
        "— NOT the paraxial pi/(4N^2), which is 18.4 % high at f/1",
    )
    add(
        "Omega_pixel",
        optics.get("Omega_pixel"),
        "sr",
        "pixel solid angle from pitch and focal length",
    )
    add("f_number_eff", optics.get("f_number_eff"), "", "effective (post-cold-stop) f/#")
    add(
        "D_eff_m",
        optics.get("D_eff_m"),
        "m",
        "effective pupil diameter after obscuration and cold stop",
    )
    add("A_collect", optics.get("A_collect"), "m^2", "collecting area, obscuration excluded")

    # --- Sampling ---
    if ifov_x_rad is not None:
        add("ifov_x_rad", ifov_x_rad, "rad", "pixel pitch / focal length (cross-track)")
    if ifov_y_rad is not None:
        add("ifov_y_rad", ifov_y_rad, "rad", "pixel pitch / focal length (along-track)")

    # --- Spectral scalars: what another model will quote for the band ---
    if tau_atm_band_mean is not None:
        add("tau_atm_band_mean", tau_atm_band_mean, "", "unweighted band mean of tau_atm(lambda)")
    if tau_opt_band_mean is not None:
        add("tau_opt_band_mean", tau_opt_band_mean, "", "unweighted band mean of tau_opt(lambda)")

    # --- Timing ---
    if t_int_effective_s is not None:
        add(
            "t_int_effective_s",
            t_int_effective_s,
            "s",
            "N_tdi x line period (effective integration)",
        )
    add("frame_rate_hz", readout.get("frame_rate_hz"), "Hz", "1 / readout.frame_period_s")
    add("duty_cycle", readout.get("duty_cycle"), "", "t_int / frame period")

    # --- The well, and WHICH well it is: the review asked for the provenance,
    #     not just the number, because a counter-derived well and an analog one
    #     are different parameters wearing the same name.
    well_source = (
        "2^counter_bits x count_packet_e (digital counting)"
        if _num(readout.get("counter_bits")) is not None
        else "readout.full_well_capacity_e (analog well)"
    )
    add("full_well_capacity_e", readout.get("full_well_capacity_e"), "e-", well_source)
    add(
        "total_well_e",
        readout.get("total_well_e"),
        "e-",
        "signal + dark + glow + nearfield + stray",
    )
    add("well_fill_fraction", readout.get("well_fill_fraction"), "", "total_well_e / full well")

    # --- Noise, first-class rather than re-RSS'd by every consumer ---
    add("sigma_total_e", readout.get("sigma_total_e"), "e- RMS", "RSS of the scaled noise budget")
    add("sigma_temporal_e", readout.get("sigma_temporal_e"), "e- RMS", "RSS of the temporal terms")
    add("sigma_spatial_e", readout.get("sigma_spatial_e"), "e- RMS", "RSS of the spatial/FPN terms")

    # --- Converted inputs: the per-pixel dark rate is the review's unit-table
    #     case, so say when it came from a density rather than being entered.
    add(
        "dark_rate_e_per_s",
        detector.get("dark_rate_e_per_s"),
        "e-/s",
        "converted from dark_current_density_a_per_cm2 as J*A_pixel/q"
        if dark_rate_from_density
        else "entered directly",
    )
    return tuple(rows)
