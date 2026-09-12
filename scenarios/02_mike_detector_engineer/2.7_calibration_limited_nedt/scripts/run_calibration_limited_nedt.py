"""Scenario 2.7: Calibration-limited NEDT — the floor the temporal budget hides.

Mike's LWIR staring camera reaches a temporal NEDT in the tens of mK, but the
achieved NEDT of a real staring LWIR system is usually set by the residual
fixed-pattern noise the two-point NUC leaves behind (Gap 120). This scenario
turns the calibration model on and shows the three headline behaviors:

  1. Scene-temperature sweep: the post-NUC residual is a parabola — zero at
     the two cal points (290/310 K), dominant away from them — so the
     achieved NEDT is calibration-limited outside the cal span.
  2. Time-since-cal sweep: drift re-grows the floor between cal events.
  3. Accuracy beside precision (ratified D6): the cal-source uncertainty is
     a BIAS, reported as radiometric accuracy [% and K] next to NEDT [mK] —
     never RSS'd into it.

Regime note: the scene is an extended-source thermal bench (atmosphere
"exo", no path — isolates the calibration physics). detector.noise_regime
stays at its default "imaging", which excludes the PRE-cal PRNU/DSNU as
"calibrated out"; the calibration model quantifies exactly what that
assumption leaves behind, so the floor appears in the imaging-regime NEDT —
that is the point (RADIANT_Calibration.md §1.1).

Usage:
    python run_calibration_limited_nedt.py
"""

from __future__ import annotations

import csv
import warnings
from pathlib import Path
from typing import Any

import yaml

from radiant.api import Sensor

_HERE = Path(__file__).resolve().parent
INPUT_FILE = _HERE.parent / "inputs" / "mike_calibration_specs.yaml"
OUTPUT_FILE = _HERE.parent / "outputs" / "calibration_limited_nedt_results.csv"

spec = yaml.safe_load(INPUT_FILE.read_text(encoding="utf-8"))
sys_s, fpa, roic, cal, study = (
    spec["system"],
    spec["fpa"],
    spec["analog_roic"],
    spec["calibration"],
    spec["study"],
)

# ---- Unit conversion at the boundary (Rule 2) ----
aperture_m = sys_s["aperture_diameter_cm"] / 100.0  # cm -> m
focal_m = sys_s["focal_length_cm"] / 100.0  # cm -> m
transmission = sys_s["optical_transmission_pct"] / 100.0  # % -> fraction
# Read from the datasheet for the narrative only: these scenarios run scalar
# transmission, which synthesizes no emitting surface (Gap 127), and the scalar
# optics.optics_temperature_K this used to feed was removed 2026-09-10 as inert.
# Model warm optics by defining elements with their own temperature_K.
optics_K = sys_s["optics_temperature_C"] + 273.15  # C -> K
band_min_um = sys_s["filter_cut_on_nm"] / 1000.0  # nm -> um
band_max_um = sys_s["filter_cut_off_nm"] / 1000.0  # nm -> um
qe = fpa["quantum_efficiency_pct"] / 100.0  # % -> fraction
fwc_e = roic["full_well_capacity_Me"] * 1.0e6  # Me- -> e-
t_int_s = study["integration_time_us"] / 1.0e6  # us -> s
cal_low_K = cal["cal_temp_low_C"] + 273.15  # C -> K
cal_high_K = cal["cal_temp_high_C"] + 273.15  # C -> K
gain_drift_pct_per_hr = cal["gain_drift_pct_per_hour"]  # schema input unit is %/hour
offset_drift_e_per_hr = cal["offset_drift_e_per_hour"]  # schema input unit is e-/hour


def make_config(
    target_temp_K: float, scheme: str, hours_since_cal: float, noise_regime: str = "imaging"
) -> dict[str, Any]:
    """RADIANT config for one scene temperature under one calibration scheme."""
    config: dict[str, Any] = {
        "source": {
            "target": {"temperature": target_temp_K, "emissivity": sys_s["target_emissivity"]},
            "background": {
                "temperature": sys_s["background_temperature_K"],
                "emissivity": sys_s["background_emissivity"],
            },
        },
        "atmosphere": {"model": "exo"},
        "geometry": {"sensor_altitude_m": 0.0},
        "platform": {"h_sensor": 1.0},  # bench height; limb check only (as 2.5/2.6)
        "optics": {
            "aperture_diameter_m": aperture_m,
            "focal_length_m": focal_m,
            "transmission_scalar": transmission,
        },
        "detector": {
            "pixel_pitch_x_um": fpa["pixel_pitch_um"],
            "pixel_pitch_y_um": fpa["pixel_pitch_um"],
            "qe_value": qe,
            "dark_rate_e_per_s": fpa["dark_current_e_per_s"],
            "detector_temperature_K": fpa["operating_temperature_K"],
            "noise_regime": noise_regime,
            # Pre-correction dispersions (Gap 120 D2): under an active scheme
            # these leave the noise budget and seed the residual model.
            "prnu_pct": fpa["prnu_pre_correction_pct"],
            "dsnu_e_rms": fpa["dsnu_pre_correction_e_rms"],
        },
        "spectral_integration": {
            "filter_min_um": band_min_um,
            "filter_max_um": band_max_um,
            "integration_time_s": t_int_s,
        },
        "readout": {
            "read_noise_e_rms": roic["read_noise_e_rms"],
            "gain_e_per_dn": roic["system_gain_e_per_dn"],
            "adc_bits": roic["adc_resolution_bits"],
            "full_well_capacity_e": fwc_e,
        },
        "calibration": {"scheme": scheme},
    }
    if scheme != "none":
        config["calibration"].update(
            {
                "cal_temp_low_K": cal_low_K,
                "cal_temp_high_K": cal_high_K,
                "nonlinearity_pct": cal["nonlinearity_pct"],
                "time_since_cal_s": hours_since_cal,  # schema input unit: hour
                "gain_drift_frac_per_s": gain_drift_pct_per_hr,  # input unit: %/hour
                "offset_drift_e_per_s": offset_drift_e_per_hr,  # input unit: e-/hour
                "source_emissivity": cal["source_emissivity"],
                "source_temp_uncertainty_K": cal["source_temp_uncertainty_K"],
                "source_emissivity_uncertainty": cal["source_emissivity_uncertainty"],
            }
        )
    return config


def evaluate(
    target_temp_K: float, scheme: str, hours: float = 0.0, noise_regime: str = "imaging"
) -> dict[str, Any]:
    """Evaluate one configuration and pull the NEDT/accuracy story out of it."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        result = Sensor.from_dict(
            make_config(target_temp_K, scheme, hours, noise_regime)
        ).evaluate()
    ro = result.stage_outputs["readout"]
    cal_out = result.stage_outputs.get("calibration", {})
    acc = result.stage_outputs.get("performance", {}).get("radiometric_accuracy_result")
    return {
        "scheme": scheme,
        "scene_temp_K": target_temp_K,
        "hours_since_cal": hours,
        "signal_e": ro["signal_e_final"],
        "well_fill_pct": 100.0 * ro["well_fill_fraction"],
        "sigma_temporal_e": ro["sigma_temporal_e"],
        "sigma_readout_total_e": ro["sigma_total_e"],
        "nuc_residual_e": cal_out.get("nuc_residual_e", 0.0),
        "gain_drift_e": cal_out.get("gain_drift_e", 0.0),
        "offset_drift_e": cal_out.get("offset_drift_e", 0.0),
        "sigma_calibration_e": cal_out.get("sigma_calibration_e", 0.0),
        "sigma_total_e": cal_out.get("sigma_total_e", ro["sigma_total_e"]),
        "nedt_mK": 1000.0 * result.metrics["nedt_K"] if "nedt_K" in result.metrics else None,
        "cal_floor_mK": 1000.0 * cal_out["calibration_nedt_K"]
        if "calibration_nedt_K" in cal_out
        else 0.0,
        "accuracy_pct": result.metrics.get("radiometric_accuracy_pct"),
        "accuracy_K": result.metrics.get("radiometric_accuracy_K"),
        "bias_K": acc.bias_K if acc is not None else None,
    }


def main() -> None:
    print("=" * 92)
    print("SCENARIO 2.7: Calibration-limited NEDT — LWIR staring HgCdTe, two-point NUC")
    print("=" * 92)
    print(
        f"\nSystem: {aperture_m * 100:.0f} cm aperture, f/{focal_m / aperture_m:.1f}, "
        f"{band_min_um:.0f}-{band_max_um:.0f} um LWIR, QE {qe * 100:.0f} %, "
        f"{fpa['pixel_pitch_um']:.0f} um pitch, t_int = {t_int_s * 1e6:.0f} us, "
        f"well {fwc_e / 1e6:.0f} Me-"
    )
    print(
        f"Calibration : two-point NUC at {cal_low_K:.0f} K / {cal_high_K:.0f} K, "
        f"nonlinearity dispersion {cal['nonlinearity_pct']:.1f} % (1-sigma), "
        f"pre-cal PRNU {fpa['prnu_pre_correction_pct']:.1f} %, "
        f"drift {gain_drift_pct_per_hr:.3f} %/hour gain + "
        f"{offset_drift_e_per_hr:.0f} e-/hour offset"
    )
    print(
        "\nPhysics: two-point NUC removes gain+offset dispersion exactly AT the cal\n"
        "points; the residual is the per-pixel NONLINEARITY parabola — zero at 290 K\n"
        "and 310 K, growing quadratically outside the span (Schulz & Caldwell form).\n"
        "It is added AFTER readout scaling (correlated: it does not average down) and\n"
        "detector.noise_regime='imaging' does not exclude it: the residual is exactly\n"
        "what 'FPN calibrated out' leaves behind (RADIANT_Calibration.md)."
    )

    rows: list[dict[str, Any]] = []

    # ---- 1. Scene-temperature sweep, freshly calibrated (t_cal = 0 h) ----
    print("\n--- 1. Scene sweep (freshly calibrated: drift = 0) ---")
    print(
        f"{'T_scene':>8} | {'NEDT old':>10} | {'NEDT uncal':>10} | {'NEDT 2-pt':>10} | "
        f"{'cal floor':>10} | {'nuc_resid':>10}"
    )
    print(
        f"{'[K]':>8} | {'[mK]':>10} | {'[mK]':>10} | {'[mK]':>10} | {'[mK]':>10} | {'[e- RMS]':>10}"
    )
    for temp_K in study["scene_temps_K"]:
        old_row = evaluate(temp_K, "none")  # imaging regime: FPN assumed away
        raw_row = evaluate(temp_K, "none", noise_regime="detection")  # raw FPN
        cal_row = evaluate(temp_K, "two_point")
        raw_row["scheme"] = "none_detection"
        rows.extend((old_row, raw_row, cal_row))
        print(
            f"{temp_K:8.0f} | {old_row['nedt_mK']:10.2f} | {raw_row['nedt_mK']:10.2f} | "
            f"{cal_row['nedt_mK']:10.2f} | {cal_row['cal_floor_mK']:10.2f} | "
            f"{cal_row['nuc_residual_e']:10.0f}"
        )
    print(
        "\nReading the three columns:\n"
        "  'NEDT old'   — scheme=none, imaging regime: the PRE-Gap-120 answer. FPN\n"
        "                 is assumed perfectly calibrated away; the tool reports the\n"
        "                 temporal floor and flatters the design at every scene temp.\n"
        "  'NEDT uncal' — scheme=none, detection regime: the raw 2 % PRNU in the\n"
        "                 budget — no calibration at all, the other extreme.\n"
        "  'NEDT 2-pt'  — the honest answer: two-point NUC removes the PRNU but\n"
        "                 leaves the nonlinearity residual — a parabola, ZERO at the\n"
        "                 cal points (290/310 K), dominant outside the span. The\n"
        "                 'cal floor' column is its NEDT-equivalent share."
    )

    # ---- 2. Time-since-cal sweep at the hot scene ----
    demo_K = study["drift_demo_scene_K"]
    print(f"\n--- 2. Drift: time-since-cal sweep at T_scene = {demo_K:.0f} K ---")
    print(
        f"{'t_cal':>8} | {'NEDT':>10} | {'nuc_resid':>10} | {'gain_drift':>10} | "
        f"{'off_drift':>10} | {'sigma_cal':>10}"
    )
    print(
        f"{'[hour]':>8} | {'[mK]':>10} | {'[e- RMS]':>10} | {'[e- RMS]':>10} | "
        f"{'[e- RMS]':>10} | {'[e- RMS]':>10}"
    )
    for hours in study["time_since_cal_hours"]:
        row = evaluate(demo_K, "two_point", hours)
        rows.append(row)
        print(
            f"{hours:8.1f} | {row['nedt_mK']:10.2f} | {row['nuc_residual_e']:10.0f} | "
            f"{row['gain_drift_e']:10.0f} | {row['offset_drift_e']:10.0f} | "
            f"{row['sigma_calibration_e']:10.0f}"
        )
    print(
        "\nReading: the NUC residual is drift-free (it is set by nonlinearity), but the\n"
        "gain/offset corrections decay — time-linear v1 (ratified D4) — so the floor\n"
        "re-grows between cal events. This is the cal-cadence trade in one table."
    )

    # ---- 3. Accuracy beside precision (ratified D3/D6) ----
    row = evaluate(300.0, "two_point")
    print("\n--- 3. Precision vs accuracy at T_scene = 300 K ---")
    print(f"  NEDT (precision)            : {row['nedt_mK']:8.2f} mK")
    print(f"  Radiometric accuracy (bias) : {row['accuracy_pct']:8.3f} % of radiance")
    print(f"  Radiometric accuracy (bias) : {1000.0 * row['accuracy_K']:8.1f} mK at scene temp")
    print(
        "\nReading: the cal-source uncertainty (dT_src = "
        f"{cal['source_temp_uncertainty_K']:.1f} K, d_eps = "
        f"{cal['source_emissivity_uncertainty']:.3f}) moves the whole radiometric\n"
        "SCALE — a bias. It is reported beside NEDT and never RSS'd into it: a\n"
        "temperature-retrieval product carries BOTH numbers (precision spread, bias\n"
        "offset). This is the ratified precision-vs-accuracy split (BiasTerm path)."
    )

    OUTPUT_FILE.parent.mkdir(exist_ok=True)
    with OUTPUT_FILE.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    print(f"\nWrote {OUTPUT_FILE.relative_to(_HERE.parent)} ({len(rows)} rows)")


if __name__ == "__main__":
    main()
