#!/usr/bin/env python3
"""Scenario 4.2 — maritime ship classification via Johnson DRI ranges.

Lisa asks: with her airborne MWIR sensor, at what range can she Detect,
Recognize, and Identify each ship class? She uses the Johnson criteria —
Detection needs 1 resolved cycle across the target, Recognition 4,
Identification 6.4 — turned into a range by the new
radiant.performance.johnson_criteria model.

The second constraint is the horizon: an airborne sensor cannot see a
sea-level target beyond the geometric horizon regardless of resolution.
The binding range for each task is min(DRI range, horizon range). The
scenario's finding is that these two limits split the fleet: small craft
are resolution-limited, large ships are horizon-limited.

Every printed number carries units. The model, its simplifications, and
the binding-constraint logic are explained inline (house rules).

Run from the repo root:
    python scenarios/04_lisa_analyst/4.2_maritime_ship_classification/scripts/run_ship_classification.py
"""

from __future__ import annotations

import math
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from radiant.core.constants import R_EARTH_M
from radiant.performance.johnson_criteria import JOHNSON_N50, johnson_range_m

HERE = Path(__file__).resolve().parent
SCEN = HERE.parent
OUTPUTS = SCEN / "outputs"
OUTPUTS.mkdir(exist_ok=True)

# --- Sensor config (from lisa_ship_classes.xlsx SensorConfig) ---------
ALT_M = 5000.0
FOCAL_M = 1.2
PITCH_UM = 15.0
IFOV_RAD = (PITCH_UM * 1e-6) / FOCAL_M  # pixel_pitch / focal_length

# --- Ship classes (name, length_m, height_m) --------------------------
SHIPS = [
    ("Small boat", 6.0, 2.0),
    ("Patrol craft", 30.0, 6.0),
    ("Corvette", 90.0, 10.0),
    ("Frigate", 130.0, 15.0),
    ("Destroyer", 155.0, 18.0),
    ("Container ship", 300.0, 30.0),
]
TASKS = ["detection", "recognition", "identification"]


def horizon_range_m(altitude_m: float) -> float:
    """Geometric horizon distance [m] to a sea-level target: √(2·R_E·h).

    Refraction and target height above the waterline are neglected (both
    extend the true radar/optical horizon by ~5–15 %); this is the hard
    geometric line-of-sight limit for a sea-level waterline.
    """
    return math.sqrt(2.0 * R_EARTH_M * altitude_m)


def main() -> None:
    horizon_m = horizon_range_m(ALT_M)
    print("=" * 74)
    print("SCENARIO 4.2 — MARITIME SHIP CLASSIFICATION (JOHNSON DRI)")
    print("=" * 74)
    print(
        f"Airborne MWIR, altitude {ALT_M/1e3:.0f} km. IFOV = pitch/focal = "
        f"{PITCH_UM} µm / {FOCAL_M} m = {IFOV_RAD*1e6:.2f} µrad."
    )
    print(
        f"Geometric horizon to a sea-level target: {horizon_m/1e3:.0f} km "
        "(√(2·R_E·h); refraction and target freeboard neglected)."
    )
    print(
        "Johnson N50 cycles across the critical dimension √(L·H): "
        f"detection {JOHNSON_N50['detection']:.0f}, "
        f"recognition {JOHNSON_N50['recognition']:.0f}, "
        f"identification {JOHNSON_N50['identification']:.1f}."
    )
    print(
        "Binding range per task = min(DRI resolution range, horizon). Model is "
        "sampling-limited (counts geometric cycles; no MTF/contrast MRC folding)."
    )
    print()

    # --- DRI matrix -----------------------------------------------------
    print("-" * 74)
    print("DRI RANGES (km) — resolution limit, and [binding] after horizon cap")
    print("-" * 74)
    header = f"{'Ship class':<16}{'crit dim':>10}" + "".join(f"{t.capitalize():>16}" for t in TASKS)
    print(header)
    dri_km: dict[str, dict[str, float]] = {}
    binding_km: dict[str, dict[str, float]] = {}
    for name, length, height in SHIPS:
        crit = math.sqrt(length * height)
        dri_km[name] = {}
        binding_km[name] = {}
        cells = []
        for task in TASKS:
            r_res = johnson_range_m(crit, IFOV_RAD, JOHNSON_N50[task])
            r_bind = min(r_res, horizon_m)
            dri_km[name][task] = r_res / 1e3
            binding_km[name][task] = r_bind / 1e3
            tag = "H" if r_res > horizon_m else "R"  # horizon- vs resolution-limited
            cells.append(f"{r_res/1e3:>8.0f}[{r_bind/1e3:.0f}{tag}]")
        print(f"{name:<16}{crit:>8.1f}m" + "".join(f"{c:>16}" for c in cells))
    print(
        "\n  Each cell: resolution range [binding range + limit]. "
        "R = resolution-limited (DRI < horizon), H = horizon-limited "
        "(DRI beyond horizon, so line-of-sight binds)."
    )

    # --- Binding-constraint split --------------------------------------
    print()
    print("-" * 74)
    print("BINDING CONSTRAINT (identification task — the hardest)")
    print("-" * 74)
    for name, length, height in SHIPS:
        crit = math.sqrt(length * height)
        r_res = johnson_range_m(crit, IFOV_RAD, JOHNSON_N50["identification"])
        if r_res > horizon_m:
            print(
                f"  {name:<16} ID resolution range {r_res/1e3:>5.0f} km > horizon "
                f"{horizon_m/1e3:.0f} km → HORIZON-limited (identifiable anywhere in sight)"
            )
        else:
            print(
                f"  {name:<16} ID resolution range {r_res/1e3:>5.0f} km < horizon "
                f"{horizon_m/1e3:.0f} km → RESOLUTION-limited (must close to {r_res/1e3:.0f} km)"
            )
    print(
        "\n  The fleet splits: large ships are horizon-limited (resolution is "
        "ample, line-of-sight is the wall), small craft are resolution-limited "
        "(over the horizon they are still too few pixels to identify)."
    )

    # ---------------------------------------------------------------
    # FIGURE 1 — DRI range bars per ship, with horizon line.
    # ---------------------------------------------------------------
    fig, ax = plt.subplots(figsize=(11, 6.5))
    names = [s[0] for s in SHIPS]
    y = np.arange(len(names))
    bar_h = 0.25
    colors = {"detection": "#9DC3E6", "recognition": "#2E75B6", "identification": "#1F3864"}
    for k, task in enumerate(TASKS):
        vals = [min(dri_km[n][task], horizon_m / 1e3) for n in names]
        ax.barh(y + (1 - k) * bar_h, vals, height=bar_h, color=colors[task], label=task.capitalize())
    ax.axvline(horizon_m / 1e3, color="red", ls="--", lw=2, label=f"horizon {horizon_m/1e3:.0f} km")
    ax.set_yticks(y)
    ax.set_yticklabels(names)
    ax.set_xlabel("Range (km) — capped at horizon")
    ax.set_title(
        "Scenario 4.2 — maritime DRI ranges (Johnson criteria)\n"
        f"MWIR UAV, {IFOV_RAD*1e6:.1f} µrad IFOV, {ALT_M/1e3:.0f} km altitude"
    )
    ax.legend(loc="lower right")
    ax.grid(axis="x", alpha=0.3)
    fig.tight_layout()
    fig1 = OUTPUTS / "fig1_dri_ranges_by_ship.png"
    fig.savefig(fig1, dpi=130)
    plt.close(fig)
    print(f"\nWrote {fig1.name}")

    # ---------------------------------------------------------------
    # FIGURE 2 — resolved cycles vs range for representative ships.
    # ---------------------------------------------------------------
    fig, ax = plt.subplots(figsize=(10, 6))
    ranges_km = np.linspace(5, 300, 200)
    for name, length, height in [SHIPS[0], SHIPS[3], SHIPS[5]]:
        crit = math.sqrt(length * height)
        cycles = crit / (2.0 * IFOV_RAD * ranges_km * 1e3)
        ax.plot(ranges_km, cycles, label=f"{name} (crit {crit:.0f} m)")
    for task in TASKS:
        ax.axhline(JOHNSON_N50[task], color="gray", ls=":", lw=1)
        ax.text(295, JOHNSON_N50[task], f" {task[:3].upper()} N50={JOHNSON_N50[task]:.1f}",
                va="center", fontsize=8)
    ax.axvline(horizon_m / 1e3, color="red", ls="--", lw=1.5, label=f"horizon {horizon_m/1e3:.0f} km")
    ax.set_xlabel("Range (km)")
    ax.set_ylabel("Resolved cycles across target")
    ax.set_yscale("log")
    ax.set_ylim(0.3, 100)
    ax.set_title("Scenario 4.2 — resolved cycles vs range (Johnson task thresholds)")
    ax.legend(loc="upper right")
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig2 = OUTPUTS / "fig2_cycles_vs_range.png"
    fig.savefig(fig2, dpi=130)
    plt.close(fig)
    print(f"Wrote {fig2.name}")

    print()
    print("=" * 74)
    print("DONE — see outputs/ for figures and MANIFEST.md.")
    print("=" * 74)


if __name__ == "__main__":
    main()
