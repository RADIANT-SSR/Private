#!/usr/bin/env python3
"""Scenario 3.3 — multi-sensor comparison for procurement.

Raj is evaluating three competing MWIR sensor proposals. He runs each
through RADIANT at a common operating point, compares SNR / NIIRS / NEDT /
MTF-at-Nyquist / GSD, ranks them, checks each against the procurement
requirements (compliance matrix), and asks which single +10 % parameter
improvement would buy the most NIIRS (via the GIQE-5 sensitivity model).

Every printed number carries units; the regime and the comparison basis are
explained inline (house rules). PDF spec-sheet parsing is out of scope — the
vendor numbers are captured in the input workbook.

Run from the repo root:
    python scenarios/03_raj_mission_planner/3.3_multi_sensor_comparison/scripts/run_sensor_comparison.py
"""

from __future__ import annotations

import warnings
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from radiant.api import Sensor
from radiant.performance.giqe_sensitivity import giqe5_sensitivity

warnings.filterwarnings("ignore")

HERE = Path(__file__).resolve().parent
SCEN = HERE.parent
OUTPUTS = SCEN / "outputs"
OUTPUTS.mkdir(exist_ok=True)

# --- Proposals (raj_sensor_proposals.xlsx) ----------------------------
VENDORS = {
    "Vendor A": dict(aperture=0.30, fnum=4.0, pitch=18.0, band=(3.7, 4.8), qe=0.70,
                     dark=200.0, read=25.0, tdet=80.0, tau=0.82),
    "Vendor B": dict(aperture=0.25, fnum=3.0, pitch=24.0, band=(3.0, 5.0), qe=0.80,
                     dark=500.0, read=30.0, tdet=77.0, tau=0.85),
    "Vendor C": dict(aperture=0.35, fnum=5.0, pitch=10.0, band=(3.7, 4.8), qe=0.65,
                     dark=300.0, read=20.0, tdet=80.0, tau=0.80),
}
ALT_M = 600e3
SCENE_TEMP_K = 300.0
SCENE_EMIS = 0.95
T_INT_S = 8e-3
N_PIX_CROSS = 4096
# Requirements: (name, threshold, direction)
REQUIREMENTS = [
    ("snr", 50.0, ">="),
    ("niirs", 4.0, ">="),
    ("nedt_mK", 50.0, "<="),
    ("gsd_m", 1.5, "<="),
    ("mtf_nyq", 0.25, ">="),
]


def evaluate_vendor(spec: dict) -> dict:
    focal = spec["fnum"] * spec["aperture"]
    s = Sensor()
    s.set("source.scene_type", "extended")
    s.set("source.target.temperature", SCENE_TEMP_K, unit="K")
    s.set("source.target.emissivity", SCENE_EMIS)
    s.set("source.target.is_hot_target", True)
    s.set("atmosphere.model", "simple")
    s.set("atmosphere.standard_atmosphere", "us_standard")
    s.set("geometry.sensor_altitude_m", ALT_M)
    s.set("optics.aperture_diameter_m", spec["aperture"])
    s.set("optics.focal_length_m", focal)
    s.set("optics.transmission_scalar", spec["tau"])
    s.set("detector.pixel_pitch_x_um", spec["pitch"])
    s.set("detector.pixel_pitch_y_um", spec["pitch"])
    s.set("detector.qe_value", spec["qe"])
    s.set("detector.dark_rate_e_per_s", spec["dark"])
    s.set("detector.detector_temperature_K", spec["tdet"])
    s.set("detector.n_pixels_cross", N_PIX_CROSS)
    s.set("spectral_integration.filter_min_um", spec["band"][0])
    s.set("spectral_integration.filter_max_um", spec["band"][1])
    s.set("spectral_integration.integration_time_s", T_INT_S)
    s.set("readout.read_noise_e_rms", spec["read"])
    s.set("readout.gain_e_per_dn", 20.0)
    s.set("readout.adc_bits", 14)
    s.set("readout.full_well_capacity_e", 6e6)
    r = s.evaluate()
    m = r.metrics
    return {
        "snr": m["snr"],
        "niirs": m["niirs"],
        "nedt_mK": m.get("nedt_K", float("nan")) * 1e3,
        "gsd_m": m["gsd_geometric_mean_m"],
        "mtf_nyq": m.get("mtf_at_nyquist", float("nan")),
        "rer": m.get("rer", float("nan")),
    }


def main() -> None:
    print("=" * 78)
    print("SCENARIO 3.3 — MULTI-SENSOR COMPARISON FOR PROCUREMENT")
    print("=" * 78)
    print(
        f"Common operating point: {ALT_M/1e3:.0f} km, {SCENE_TEMP_K:.0f} K scene, "
        f"t_int {T_INT_S*1e3:.0f} ms, extended MWIR. PDF specs transcribed to the "
        "input workbook."
    )
    print()

    results = {name: evaluate_vendor(spec) for name, spec in VENDORS.items()}

    # --- Comparison table ----------------------------------------------
    print("-" * 78)
    print("COMPARISON TABLE")
    print("-" * 78)
    metrics = [("SNR", "snr", ""), ("NIIRS", "niirs", ""), ("NEDT [mK]", "nedt_mK", ""),
               ("GSD [m]", "gsd_m", ""), ("MTF@Nyq", "mtf_nyq", "")]
    header = f"{'Metric':<12}" + "".join(f"{v:>12}" for v in VENDORS)
    print(header)
    for label, key, _ in metrics:
        row = "".join(f"{results[v][key]:>12.3f}" for v in VENDORS)
        print(f"{label:<12}{row}")

    # --- Ranking (best per metric) -------------------------------------
    print("\n" + "-" * 78)
    print("RANKING (best vendor per metric)")
    print("-" * 78)
    better_high = {"snr", "niirs", "mtf_nyq"}
    for label, key, _ in metrics:
        vals = {v: results[v][key] for v in VENDORS}
        best = (max if key in better_high else min)(vals, key=vals.get)
        print(f"  {label:<12} best: {best} ({vals[best]:.3f})")

    # --- Compliance matrix ---------------------------------------------
    print("\n" + "-" * 78)
    print("COMPLIANCE MATRIX (vs procurement requirements)")
    print("-" * 78)
    print(f"{'Requirement':<16}" + "".join(f"{v:>12}" for v in VENDORS))
    passes = {v: 0 for v in VENDORS}
    for key, thr, direction in REQUIREMENTS:
        cells = []
        for v in VENDORS:
            val = results[v][key]
            ok = val >= thr if direction == ">=" else val <= thr
            passes[v] += int(ok)
            cells.append(f"{'PASS' if ok else 'FAIL':>12}")
        print(f"{key + ' ' + direction + ' ' + str(thr):<16}" + "".join(cells))
    print(f"{'TOTAL PASS':<16}" + "".join(f"{passes[v]:>10}/{len(REQUIREMENTS)}" for v in VENDORS))
    compliant = [v for v in VENDORS if passes[v] == len(REQUIREMENTS)]
    print(f"\n  Fully compliant: {', '.join(compliant) if compliant else 'none'}.")

    # --- Which +10% improvement buys the most NIIRS --------------------
    print("\n" + "-" * 78)
    print("HIGHEST-LEVERAGE +10% IMPROVEMENT (GIQE-5 sensitivity)")
    print("-" * 78)
    for v in VENDORS:
        rr = results[v]
        sens = giqe5_sensitivity(rr["gsd_m"], rr["rer"], rr["snr"])
        # per_percent is NIIRS change per +1%; ×10 for +10% (log terms).
        # Improving GSD means REDUCING it: use the magnitude for a 10% cut.
        gains = {
            "GSD −10%": abs(sens.per_percent["gsd"]) * 10,
            "RER +10%": sens.per_percent["rer"] * 10,
            "SNR +10%": sens.per_percent["snr"] * 10,
        }
        best = max(gains, key=gains.get)
        print(f"  {v}: best lever = {best} (+{gains[best]:.3f} NIIRS); "
              + ", ".join(f"{k} {gains[k]:+.3f}" for k in gains))

    # ---------------------------------------------------------------
    # FIGURE 1 — radar/spider chart (normalised metrics).
    # ---------------------------------------------------------------
    labels = ["SNR", "NIIRS", "NEDT⁻¹", "GSD⁻¹", "MTF@Nyq"]
    # Normalise each axis to the best vendor (higher = better; invert NEDT/GSD).
    def norm(key: str, invert: bool) -> dict:
        vals = {v: results[v][key] for v in VENDORS}
        if invert:
            vals = {v: 1.0 / x for v, x in vals.items()}
        mx = max(vals.values())
        return {v: vals[v] / mx for v in VENDORS}
    axes_norm = [norm("snr", False), norm("niirs", False), norm("nedt_mK", True),
                 norm("gsd_m", True), norm("mtf_nyq", False)]
    angles = np.linspace(0, 2 * np.pi, len(labels), endpoint=False).tolist()
    angles += angles[:1]
    fig, ax = plt.subplots(figsize=(7, 7), subplot_kw=dict(polar=True))
    colors = {"Vendor A": "#C55A11", "Vendor B": "#2E75B6", "Vendor C": "#548235"}
    for v in VENDORS:
        vals = [axis[v] for axis in axes_norm]
        vals += vals[:1]
        ax.plot(angles, vals, "o-", lw=2, color=colors[v], label=v)
        ax.fill(angles, vals, alpha=0.1, color=colors[v])
    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(labels)
    ax.set_ylim(0, 1.05)
    ax.set_title("Scenario 3.3 — sensor comparison (normalised, outer = better)")
    ax.legend(loc="upper right", bbox_to_anchor=(1.25, 1.1))
    fig.tight_layout()
    fig1 = OUTPUTS / "fig1_radar_comparison.png"
    fig.savefig(fig1, dpi=130)
    plt.close(fig)
    print(f"\nWrote {fig1.name}")

    print()
    print("=" * 78)
    print("DONE — see outputs/ for the radar chart and MANIFEST.md.")
    print("=" * 78)


if __name__ == "__main__":
    main()
