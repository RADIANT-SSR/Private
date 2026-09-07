"""Scenario 1.4 calibration variant: the TDI answer changes at the correlated floor.

The base study (run_tdi_pushbroom_trade.py) found the optimal N_tdi assuming
every noise term averages down as sqrt(N). Calibration residuals do not
(Gap 120, ADR-0012): they are appended AFTER readout's TDI scaling, so their
signal-relative size is invariant in N — SNR plateaus at the correlated floor
instead of climbing.

Cal-point semantics on this REFLECTIVE scene (CU-346): the v1 mapping is
Planck-based and anchors to the declared target temperature, so the "290 K
cal point" resolves to the 290/300 K band Planck ratio of the SOLAR scene
signal (~13.8 % of S) — a deterministic stand-in, not the ~0 a blackbody
physically delivers in a 0.5-0.85 um band. The one_point residual is then
prnu·|S − S1| = prnu·(1 − r)·S with r = S1/S, an offset-cal-like floor:

    SNR_ceiling ≈ 1 / (prnu_frac · (1 − r)) ≈ 58 for r = 0.138

The DEMO'S POINT is mapping-independent: whatever S1 is, the residual is
appended after TDI scaling and its signal-relative size is N-invariant —
the plateau is structural (ADR-0012), only its exact level rides CU-346.

Reuses the base study's spreadsheet-driven configuration verbatim (imported,
not copied) and sweeps the same N_tdi points under scheme none vs one_point.

Usage:
    python run_tdi_calibration_floor.py
"""

from __future__ import annotations

import csv
import warnings
from pathlib import Path
from typing import Any

import run_tdi_pushbroom_trade as base  # the study's spec load + base_config

from radiant.api import Sensor

OUTPUT_FILE = Path(__file__).resolve().parent.parent / "outputs" / "tdi_calibration_floor.csv"

_PRNU_PCT = 2.0  # pre-correction gain dispersion (1-sigma), never flat-fielded
_CAL_TEMP_K = 290.0  # Planck-mapped stand-in on this reflective scene (CU-346)


def _config(n_tdi: int, scheme: str) -> dict[str, Any]:
    config = {k: ({**v} if isinstance(v, dict) else v) for k, v in base.base_config.items()}
    config["source"] = {
        "target": {**base.base_config["source"]["target"]},
        "background": {**base.base_config["source"]["background"]},
    }
    config["readout"] = {**base.base_config["readout"], "n_tdi": n_tdi}
    config["detector"] = {**base.base_config["detector"], "prnu_pct": _PRNU_PCT}
    config["calibration"] = {"scheme": scheme}
    if scheme != "none":
        config["calibration"]["cal_temp_low_K"] = _CAL_TEMP_K
    return config


def _evaluate(n_tdi: int, scheme: str) -> dict[str, Any]:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        result = Sensor.from_dict(_config(n_tdi, scheme)).evaluate()
    ro = result.stage_outputs["readout"]
    cal = result.stage_outputs.get("calibration", {})
    signal = ro["signal_e_final"]
    return {
        "scheme": scheme,
        "n_tdi": n_tdi,
        "signal_e": signal,
        "well_fill_pct": 100.0 * ro["well_fill_fraction"],
        "snr": result.metrics.get("snr", float("nan")),
        "sigma_temporal_e": ro["sigma_temporal_e"],
        "nuc_residual_e": cal.get("nuc_residual_e", 0.0),
        "temporal_ratio_pct": 100.0 * ro["sigma_temporal_e"] / signal,
        "cal_ratio_pct": 100.0 * cal.get("nuc_residual_e", 0.0) / signal,
    }


def main() -> None:
    print("=" * 88)
    print("SCENARIO 1.4 VARIANT: TDI optimization vs the calibration floor (Gap 120)")
    print("=" * 88)
    print(
        f"\nSame VNIR pushbroom as the base study (spreadsheet-driven config reused).\n"
        f"Calibration: one_point at {_CAL_TEMP_K:.0f} K on a REFLECTIVE "
        f"{base.band_min_um:.2f}-{base.band_max_um:.2f} um scene — the v1 Planck mapping\n"
        f"anchors the cal point at the 290/300 K band ratio of the solar signal "
        f"(CU-346 stand-in semantics; see module docstring).\n"
        f"PRNU {_PRNU_PCT:.1f} % (1-sigma) stays uncorrected on the departure -> "
        f"correlated SNR ceiling ~1/(prnu·(1−S1/S))."
    )
    print(
        "\nWhy the answer changes: the residual is appended AFTER TDI scaling\n"
        "(ADR-0012 ordering) — correlated along-column error does not average\n"
        "down. Temporal noise ratio falls ~sqrt(N); the calibration ratio is\n"
        "N-invariant, so SNR saturates where the two cross."
    )
    print(
        f"\n{'N_tdi':>6} | {'fill':>7} | {'SNR none':>9} | {'SNR cal':>8} | "
        f"{'tmp/S':>7} | {'cal/S':>7}"
    )
    print(
        f"{'[-]':>6} | {'[%]':>7} | {'[-]':>9} | {'[-]':>8} | {'[%]':>7} | {'[%]':>7}"
    )

    rows: list[dict[str, Any]] = []
    for n_tdi in base.tdi_values:
        none_row = _evaluate(n_tdi, "none")
        cal_row = _evaluate(n_tdi, "one_point")
        rows.extend((none_row, cal_row))
        print(
            f"{n_tdi:6d} | {cal_row['well_fill_pct']:7.1f} | {none_row['snr']:9.1f} | "
            f"{cal_row['snr']:8.1f} | {cal_row['temporal_ratio_pct']:7.3f} | "
            f"{cal_row['cal_ratio_pct']:7.3f}"
        )

    best_none = max((r for r in rows if r["scheme"] == "none"), key=lambda r: r["snr"])
    best_cal = max((r for r in rows if r["scheme"] == "one_point"), key=lambda r: r["snr"])
    print(
        f"\nOptimum WITHOUT the calibration model: N_tdi = {best_none['n_tdi']} "
        f"(SNR {best_none['snr']:.1f} [-])"
    )
    print(
        f"Optimum WITH the correlated floor    : SNR saturates at "
        f"~{best_cal['snr']:.1f} [-] (the 1/(prnu·(1−S1/S)) ceiling); stages beyond "
        f"the crossover buy MTF loss (TDI misalignment), not SNR."
    )
    print(
        "\nRegime/limitation notes: reflective extended scene (solar, midlat summer\n"
        "path, zenith per the base study). The v1 Planck cal-point mapping does not\n"
        "describe a reflective-band cal (integrating-sphere flat-field is\n"
        "inexpressible) — tracked as CU-346; the plateau conclusion is unaffected."
    )

    OUTPUT_FILE.parent.mkdir(exist_ok=True)
    with OUTPUT_FILE.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    print(f"\nWrote {OUTPUT_FILE.name} ({len(rows)} rows)")


if __name__ == "__main__":
    main()
