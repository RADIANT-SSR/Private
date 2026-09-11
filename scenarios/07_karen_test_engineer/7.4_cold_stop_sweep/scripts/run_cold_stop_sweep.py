"""Scenario 7.4: Cold-Stop Undersizing Sweep — How Much Tolerancing Margin Can I Afford?

Karen (test engineer) is running a TVAC background characterization. The cold
stop in her MWIR camera is the aperture stop, and it is built slightly smaller
than the primary so that alignment and thermal tolerances can never let the FPA
see past it to warm structure. Undersizing buys margin — and costs photons.
Her question is the trade: how much undersizing can the camera afford?

Model rules this scenario exercises (Gap 128, owner-ratified 2026-09-09):

  * The cold stop IS the aperture stop.  ``optics.cold_stop_undersize_frac``
    (u [-]) reduces the pupil DIAMETER: D_eff = (1 − u)·D.  Everything the
    pupil sets follows from that ONE number — the collecting area A_collect
    [m²] (∝ (1 − u)²), the working f-number N_eff = f/D_eff [-], the
    diffraction PSF and MTF (Rule 4: both spatial paths, one pupil), and the
    étendue acceptance cone Ω_cone [sr].
  * Warm-optics emission is seen through Ω_cone and nothing else.  A cold stop
    CANNOT attenuate in-cone emission — that light arrives through the imaging
    path itself — so the old ``optics.nearfield_fraction`` "leakage" knob is
    gone.  Out-of-cone warm structure is taken to be blocked completely.
  * Signal and near-field therefore fall TOGETHER as u rises.  The trade is not
    "less background for free"; it is signal, SNR, and resolution traded for
    the certainty that no warm structure is in view.

This script:
  1. Reads Karen's spreadsheet (vendor/lab units: cm, mm, %, °C, nm, ms, fA)
     and converts to RADIANT canonical units (m, fractions, K, µm, s, e⁻/s).
  2. Builds the warm train as what it physically is — three fold mirrors at
     R = 0.98 [-] (ε = 1 − R each, Kirchhoff, Rule 5) plus an AR-coated cold
     window carrying the balance of the workbook's end-to-end τ.
  3. Sweeps ``optics.cold_stop_undersize_frac`` over 0–10 % and reports, at
     every point: near-field [e⁻], total shuttered background [e⁻], signal
     [e⁻], SNR [-], NEDT [mK], MTF at Nyquist [-], and A_collect [m²].
  4. Assesses the shuttered-background requirement against the model.
  5. Compares Karen's lab measurements against the model's single predicted
     background — under the new rules a cold stop cannot manufacture excess
     background, so a measurement above prediction is evidence about the
     OPTICS (temperature, coating emissivity), not about stop alignment.
  6. Writes plots and an output workbook.

Usage:
    python run_cold_stop_sweep.py
"""

import math
from pathlib import Path

import numpy as np
import openpyxl
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side

import matplotlib

matplotlib.use("Agg")  # headless-safe: plt.show() is a no-op, so the runner completes in CI/batch
import matplotlib.pyplot as plt  # noqa: E402

from radiant.api import Sensor  # noqa: E402

# ---------------------------------------------------------------------------
# Warm-train coating model (Gap 128)
# ---------------------------------------------------------------------------
# The workbook quotes ONE end-to-end transmission and (historically) read the
# whole 1 − τ loss as absorption — the ε = 1 − τ fallacy, which over-states
# warm-optics emission several-fold. A real MWIR camera loses most of that τ at
# coatings and the cold filter. Three fold mirrors plus an AR-coated cold window
# reproduce the workbook's net τ EXACTLY while emitting a realistic ε.
MIRROR_R = 0.98  # [-] per-surface reflectance, protected gold
N_MIRRORS = 3  # three-mirror fore-optics

# The undersizing sweep: 0–10 % of the pupil diameter, the tolerancing range a
# cold-stop design actually lives in.
UNDERSIZE_SWEEP = np.linspace(0.0, 0.10, 21)  # [-]

# ---------------------------------------------------------------------------
# Step 1: Read Karen's spreadsheet
# ---------------------------------------------------------------------------
# Three sheets:
#   "Instrument Spec Sheet"    — vendor specs in lab/vendor units
#   "Background Measurements"  — lab data at various cold stop positions
#   "Performance Requirements" — pass/fail thresholds

INPUT_FILE = Path(__file__).parent.parent / "inputs" / "karen_cold_stop_data.xlsx"

wb = openpyxl.load_workbook(INPUT_FILE)

ws_spec = wb["Instrument Spec Sheet"]
specs: dict[str, object] = {}
for row in ws_spec.iter_rows(min_row=6, max_col=4, values_only=False):
    name = row[0].value
    value = row[1].value
    if name and value is not None:
        # Skip section headers (blue-filled rows)
        fill = row[0].fill
        if fill and fill.start_color and fill.start_color.rgb == "002E75B6":
            continue
        specs[name] = value

ws_meas = wb["Background Measurements"]
lab_data: list[dict] = []
for row in ws_meas.iter_rows(min_row=6, max_col=6, values_only=True):
    if row[0] and row[1] is not None and isinstance(row[1], (int, float)):
        lab_data.append({
            "test_id": row[0],
            "position_mm": float(row[1]),
            "dn_mean": float(row[2]),
            "dn_sigma": float(row[3]),
            "bkg_e": float(row[4]),
            "notes": row[5] or "",
        })

ws_req = wb["Performance Requirements"]
reqs: dict[str, object] = {}
for row in ws_req.iter_rows(min_row=5, max_col=4, values_only=True):
    if row[0] and row[1] is not None:
        reqs[row[0]] = row[1]


# ---------------------------------------------------------------------------
# Step 2: Convert to RADIANT canonical units
# ---------------------------------------------------------------------------
# RADIANT expects: meters, fractions, seconds, µm, K, e⁻/s
# Karen's spreadsheet has: cm, mm, %, °C, nm, ms, fA/pixel

aperture_m = float(specs["Primary aperture diameter"]) / 100.0    # cm → m
focal_length_m = float(specs["Effective focal length"]) / 1000.0  # mm → m
f_number = float(specs["f-number"])                                # dimensionless
transmission = float(specs["End-to-end optical transmission"]) / 100.0  # % → fraction
optics_temp_K = float(specs["Optics barrel temperature"]) + 273.15     # °C → K
# The workbook's "cold stop design efficiency" is a BLOCKED-fraction number that
# no longer maps to a RADIANT parameter (Gap 128): out-of-cone structure is
# always fully blocked, and in-cone emission cannot be blocked at all. It is
# carried for the narrative only.
cold_stop_design = float(specs["Cold stop design efficiency"]) / 100.0  # % → fraction
window_T = transmission / MIRROR_R**N_MIRRORS  # [-] balance of the workbook τ
wfe_waves = float(specs["WFE (RMS)"])                              # already in waves

pixel_pitch_um = float(specs["Pixel pitch"])                       # already µm
qe = float(specs["Average QE (in-band)"]) / 100.0                 # % → fraction
# Dark current: fA/pixel → e⁻/s.  I_dark [fA] = Q_dark [e⁻/s] × q_e [C]
dark_fA = float(specs["Dark current (mean)"])
dark_rate_e_per_s = dark_fA * 1e-15 / 1.602e-19                   # fA → e⁻/s
operating_temp_K = float(specs["Operating temperature"])           # already K
fwc = float(specs["Full well capacity"])                           # already e⁻
read_noise = float(specs["Read noise (CDS)"])                      # already e⁻ RMS
adc_bits = int(specs["ADC resolution"])                            # already bits
gain = float(specs["System gain"])                                 # already e⁻/DN

bb_temp_K = float(specs["Blackbody temperature"]) + 273.15        # °C → K
bb_emiss = float(specs["Blackbody emissivity"])                    # dimensionless
shroud_temp_K = float(specs["Chamber shroud temperature"]) + 273.15  # °C → K
shroud_emiss = float(specs["Chamber shroud emissivity"])           # dimensionless

band_str = str(specs["Cold filter passband"])
band_parts = band_str.replace("–", "-").replace("—", "-").split("-")
band_min_um = float(band_parts[0].strip()) / 1000.0               # nm → µm
band_max_um = float(band_parts[1].strip()) / 1000.0               # nm → µm

t_int_s = float(specs["Integration time"]) / 1000.0               # ms → s


def _warm_train() -> list[dict]:
    """The defined optical train: emitting mirrors + a non-absorbing cold window."""
    return [
        *(
            {
                "name": f"fold_mirror_{i + 1}",
                "transfer_mode": "REFLECTIVE",
                "kind": "MIRROR",
                "reflectance": MIRROR_R,        # [-]
                "temperature_K": optics_temp_K,  # K
            }
            for i in range(N_MIRRORS)
        ),
        {
            "name": "cold_window",
            "transfer_mode": "REFRACTIVE",
            "kind": "WINDOW",
            "transmittance": window_T,      # [-] AR-coated; ε = 0 (Gap 127)
            "temperature_K": optics_temp_K,  # K
        },
    ]


config = {
    "source": {
        "target": {"temperature": bb_temp_K, "emissivity": bb_emiss},
        "background": {"temperature": shroud_temp_K, "emissivity": shroud_emiss},
    },
    "atmosphere": {"model": "exo"},   # Vacuum — TVAC chamber, no atmosphere
    "geometry": {"sensor_altitude_m": 0.0},   # Lab test — not orbital
    "platform": {
        # The "exo" backend routes through the no_atmosphere 'space' sub-case,
        # whose Earth-limb intercept check requires a positive sensor altitude.
        # 1.0 m ≈ optical-bench height; no radiometric effect in this lab setup.
        "h_sensor": 1.0,
    },
    "optics": {
        "aperture_diameter_m": aperture_m,
        "focal_length_m": focal_length_m,
        # The swept variable. 0 = the cold stop matches the primary exactly.
        "cold_stop_undersize_frac": 0.0,
    },
    "optical_elements": _warm_train(),
    "detector": {
        "pixel_pitch_x_um": pixel_pitch_um,
        "pixel_pitch_y_um": pixel_pitch_um,
        "qe_value": qe,
        "dark_rate_e_per_s": dark_rate_e_per_s,
        "detector_temperature_K": operating_temp_K,
    },
    "spectral_integration": {
        "filter_min_um": band_min_um,
        "filter_max_um": band_max_um,
        "integration_time_s": t_int_s,
    },
    "readout": {
        "read_noise_e_rms": read_noise,
        "gain_e_per_dn": gain,
        "adc_bits": adc_bits,
        "full_well_capacity_e": fwc,
    },
    # CU-178: config outside the GIQE-5 envelope → NIIRS N/A by default; opt into
    # the extrapolated NIIRS trend (read as relative, not calibrated).
    "performance": {"niirs": {"allow_extrapolated": True}},
}


def _shuttered_config(undersize: float) -> dict:
    """The shuttered-aperture case: a 77 K cold plate blocking the aperture.

    With the aperture shuttered the FPA sees only the cold plate (negligible in
    MWIR) plus the warm-optics near-field, which is exactly what Karen measures.
    """
    shut = {k: (dict(v) if isinstance(v, dict) else v) for k, v in config.items()}
    shut["source"] = {
        "target": {"temperature": 77.0, "emissivity": 0.98},      # cold plate [K]
        "background": {"temperature": 77.0, "emissivity": 0.98},  # shroud blocked
    }
    shut["optics"] = dict(config["optics"])
    shut["optics"]["cold_stop_undersize_frac"] = float(undersize)
    return shut


def _illuminated_config(undersize: float) -> dict:
    """The illuminated case: the 308 K calibration blackbody filling the FOV."""
    illum = {k: (dict(v) if isinstance(v, dict) else v) for k, v in config.items()}
    illum["optics"] = dict(config["optics"])
    illum["optics"]["cold_stop_undersize_frac"] = float(undersize)
    return illum


def main() -> None:
    """Run the scenario analysis."""
    OUTPUT_FILE = Path(__file__).parent.parent / "outputs" / "cold_stop_sweep_results.xlsx"
    PLOT_DIR = Path(__file__).parent.parent / "outputs"
    PLOT_DIR.mkdir(parents=True, exist_ok=True)

    print("=== Instrument Spec Sheet (vendor units) ===")
    print(f"  {'Parameter':<35s} {'Value':>14s}  {'Unit'}")
    print(f"  {'-' * 35} {'-' * 14}  {'-' * 12}")
    for label, key, unit in [
        ("Primary aperture diameter", "Primary aperture diameter", "cm"),
        ("Effective focal length", "Effective focal length", "mm"),
        ("f-number", "f-number", "—"),
        ("End-to-end optical transmission", "End-to-end optical transmission", "%"),
        ("Optics barrel temperature", "Optics barrel temperature", "°C"),
        ("Cold stop design efficiency", "Cold stop design efficiency", "%"),
        ("Pixel pitch", "Pixel pitch", "µm"),
        ("Average QE (in-band)", "Average QE (in-band)", "%"),
        ("Dark current (mean)", "Dark current (mean)", "fA/pixel"),
        ("Operating temperature", "Operating temperature", "K"),
        ("Read noise (CDS)", "Read noise (CDS)", "e⁻ RMS"),
        ("ADC resolution", "ADC resolution", "bits"),
        ("System gain", "System gain", "e⁻/DN"),
    ]:
        print(f"  {label:<35s} {specs[key]:>14}  {unit}")
    print(f"  {'Full well capacity':<35s} {specs['Full well capacity']:>14.0f}  e⁻")

    print("\n=== Lab Background Measurements ===")
    print(f"  {'Test Point':<14s} {'Pos [mm]':>10s}  {'Bkg DN':>10s}  {'σ DN':>8s}  {'Bkg [e⁻]':>12s}")
    print(f"  {'-' * 14} {'-' * 10}  {'-' * 10}  {'-' * 8}  {'-' * 12}")
    for d in lab_data:
        print(f"  {d['test_id']:<14s} {d['position_mm']:>10.1f}  {d['dn_mean']:>10.0f}"
              f"  {d['dn_sigma']:>8.0f}  {d['bkg_e']:>12.0f}")

    print("\n=== Performance Requirements ===")
    for req_name, req_val in reqs.items():
        print(f"  {req_name:<45s}  {req_val}")

    print("\n=== Converted to RADIANT canonical units ===")
    print(f"  {'Parameter':<35s} {'Value':>14s}  {'Unit':<15s}  {'Conversion'}")
    print(f"  {'-' * 35} {'-' * 14}  {'-' * 15}  {'-' * 25}")
    print(f"  {'Aperture diameter':<35s} {aperture_m:>14.4f}  {'m':<15s}  cm ÷ 100")
    print(f"  {'Focal length':<35s} {focal_length_m:>14.4f}  {'m':<15s}  mm ÷ 1000")
    print(f"  {'f-number (primary)':<35s} {f_number:>14.1f}  {'—':<15s}  no conversion")
    print(f"  {'Optical transmission (net)':<35s} {transmission:>14.4f}  {'fraction':<15s}  % ÷ 100")
    print(f"  {'  → fold mirrors':<35s} {MIRROR_R:>14.4f}  {'R each':<15s}  {N_MIRRORS} surfaces")
    print(f"  {'  → cold window':<35s} {window_T:>14.4f}  {'T':<15s}  τ ÷ R^{N_MIRRORS}")
    print(f"  {'Optics temperature':<35s} {optics_temp_K:>14.2f}  {'K':<15s}  °C + 273.15")
    print(f"  {'Emitting ε (mirrors only)':<35s} {N_MIRRORS * (1.0 - MIRROR_R):>14.4f}"
          f"  {'fraction':<15s}  Σ(1 − R), Kirchhoff")
    print(f"  {'WFE (RMS)':<35s} {wfe_waves:>14.4f}  {'waves':<15s}  no conversion")
    print(f"  {'Pixel pitch':<35s} {pixel_pitch_um:>14.1f}  {'µm':<15s}  no conversion")
    print(f"  {'Quantum efficiency':<35s} {qe:>14.4f}  {'fraction':<15s}  % ÷ 100")
    print(f"  {'Dark current':<35s} {dark_fA:>14.1f}  {'fA/pixel':<15s}  (input)")
    print(f"  {'Dark current (converted)':<35s} {dark_rate_e_per_s:>14.1f}  {'e⁻/s':<15s}"
          f"  fA × 1e-15 ÷ q_e")
    print(f"  {'Detector temperature':<35s} {operating_temp_K:>14.1f}  {'K':<15s}  no conversion")
    print(f"  {'Read noise':<35s} {read_noise:>14.1f}  {'e⁻ RMS':<15s}  no conversion")
    print(f"  {'System gain':<35s} {gain:>14.1f}  {'e⁻/DN':<15s}  no conversion")
    print(f"  {'Blackbody temperature':<35s} {bb_temp_K:>14.2f}  {'K':<15s}  °C + 273.15")
    print(f"  {'Shroud temperature':<35s} {shroud_temp_K:>14.2f}  {'K':<15s}  °C + 273.15")
    print(f"  {'Band':<35s} {band_min_um:>6.2f}–{band_max_um:<6.2f}  {'µm':<15s}  nm ÷ 1000")
    print(f"  {'Integration time':<35s} {t_int_s:>14.6f}  {'s':<15s}  ms ÷ 1000")
    print()
    print(f"  UNMAPPED VENDOR NUMBER (Gap 128): 'Cold stop design efficiency' "
          f"= {cold_stop_design * 100:.0f} %")
    print("  is a BLOCKED-fraction figure that no longer corresponds to any RADIANT")
    print("  parameter.  A cold stop cannot attenuate in-cone warm-optics emission —")
    print("  that light arrives through the imaging path itself — and out-of-cone warm")
    print("  structure is taken to be blocked completely.  What a cold stop DOES set is")
    print("  the size of the pupil: optics.cold_stop_undersize_frac, swept below.")

    # -----------------------------------------------------------------------
    # Step 3: Baseline at u = 0 (cold stop matched to the primary)
    # -----------------------------------------------------------------------
    print("\n=== Baseline: cold stop matched to the primary (u = 0.00) ===")
    baseline = Sensor.from_dict(_illuminated_config(0.0)).evaluate()
    opt = baseline.stage_outputs["optics"]
    si = baseline.stage_outputs["spectral_integration"]

    regime = opt["regime"]
    baseline_nearfield_e = si["nearfield_e"]
    baseline_background_e = si["background_e"]
    baseline_signal_e = baseline.stage_outputs["readout"]["signal_e_final"]
    baseline_snr = baseline.metrics["snr"]
    baseline_nedt = baseline.metrics.get("nedt_K")
    baseline_mtf_nyq = baseline.metrics.get("mtf_at_nyquist")

    print(f"  Regime: {regime} — the extended-area blackbody at {bb_temp_K:.1f} K fills the FOV.")
    print("  UNUSED PARAMETER NOTE: in the extended regime the target fills the pixel")
    print("  IFOV, so RADIANT skips the separate scene-background photon term")
    print(f"  (background_e = {baseline_background_e:.0f} e⁻ by design — matrix Decision #13).")
    print(f"  The chamber shroud ({shroud_temp_K:.1f} K) stays in the config for descriptor")
    print("  completeness but contributes no photons here; the background terms are")
    print("  warm-optics near-field and dark current.")
    print()
    print("  THE EFFECTIVE PUPIL (Gap 128) — one number, five consequences:")
    print(f"    D_eff              = {opt['D_eff_m']:.5f} m      (= (1 − u)·D)")
    print(f"    obscuration_eff    = {opt['obscuration_eff']:.4f} [-]")
    print(f"    f/#_eff            = {opt['f_number_eff']:.4f} [-]   (= f / D_eff)")
    print(f"    A_collect          = {opt['A_collect']:.6f} m²")
    print(f"    Ω_cone             = {opt['Omega_cone']:.6f} sr   (= 2π(1 − cos θ),"
          " θ = arctan(1/(2·f/#_eff)))")
    print("    The same effective pupil feeds the complex pupil function, so the")
    print("    diffraction PSF and the MTF product both see the cold stop (Rule 4).")
    print()
    print("  WARM-OPTICS EMISSIVITY (Kirchhoff, Rule 5; Gap 127):")
    print(f"    Emission derives ONLY from defined elements: {N_MIRRORS} fold mirrors at")
    print(f"    R = {MIRROR_R:.2f} [-] ⇒ ε = {1.0 - MIRROR_R:.2f} [-] each. The AR-coated cold")
    print("    window is non-absorbing (ε = 0 [-]) and only attenuates what is upstream.")
    print(f"    Net train throughput τ = {transmission:.2f} [-], the workbook value, exactly.")
    print()
    print(f"  Near-field at u = 0:  {baseline_nearfield_e:,.0f} e⁻")
    print(f"  Signal at u = 0:      {baseline_signal_e:,.0f} e⁻")
    print(f"  SNR at u = 0:         {baseline_snr:.1f} [-]")
    if baseline_nedt is not None:
        print(f"  NEDT at u = 0:        {baseline_nedt * 1e3:.2f} mK")
    if baseline_mtf_nyq is not None:
        print(f"  MTF@Nyquist at u = 0: {baseline_mtf_nyq:.4f} [-]")

    print("\n  Noise breakdown at u = 0:")
    nd0 = {nt.name: nt.value_e for nt in baseline.noise_terms}
    print(f"  {'Noise Term':<35s} {'Value [e⁻ RMS]':>14s}")
    print(f"  {'-' * 35} {'-' * 14}")
    for name in ["signal_shot", "background_shot", "nearfield_shot", "dark_shot",
                 "read_noise", "quantization"]:
        if name in nd0:
            print(f"  {name:<35s} {nd0[name]:>14.2f}")

    # -----------------------------------------------------------------------
    # Step 4: The undersizing sweep
    # -----------------------------------------------------------------------
    n = len(UNDERSIZE_SWEEP)
    sw_d_eff = np.zeros(n)         # m
    sw_f_eff = np.zeros(n)         # [-]
    sw_a_collect = np.zeros(n)     # m²
    sw_omega_cone = np.zeros(n)    # sr
    sw_nearfield_e = np.zeros(n)   # e⁻
    sw_signal_e = np.zeros(n)      # e⁻
    sw_snr = np.zeros(n)           # [-]
    sw_nedt = np.full(n, np.nan)   # K
    sw_mtf_nyq = np.full(n, np.nan)  # [-]
    sw_nf_shot = np.zeros(n)       # e⁻ RMS
    sw_shut_total_e = np.zeros(n)  # e⁻

    print(f"\n=== Sweeping optics.cold_stop_undersize_frac from "
          f"{UNDERSIZE_SWEEP[0] * 100:.0f} % to {UNDERSIZE_SWEEP[-1] * 100:.0f} % ===")

    for i, u in enumerate(UNDERSIZE_SWEEP):
        r_ill = Sensor.from_dict(_illuminated_config(u)).evaluate()
        o = r_ill.stage_outputs["optics"]
        s_i = r_ill.stage_outputs["spectral_integration"]
        sw_d_eff[i] = o["D_eff_m"]
        sw_f_eff[i] = o["f_number_eff"]
        sw_a_collect[i] = o["A_collect"]
        sw_omega_cone[i] = o["Omega_cone"]
        sw_nearfield_e[i] = s_i["nearfield_e"]
        sw_signal_e[i] = r_ill.stage_outputs["readout"]["signal_e_final"]
        sw_snr[i] = r_ill.metrics["snr"]
        nedt_val = r_ill.metrics.get("nedt_K")
        if nedt_val is not None:
            sw_nedt[i] = nedt_val
        mtf_val = r_ill.metrics.get("mtf_at_nyquist")
        if mtf_val is not None:
            sw_mtf_nyq[i] = mtf_val
        sw_nf_shot[i] = {nt.name: nt.value_e for nt in r_ill.noise_terms}.get(
            "nearfield_shot", 0.0
        )

        r_shut = Sensor.from_dict(_shuttered_config(u)).evaluate()
        s_s = r_shut.stage_outputs["spectral_integration"]
        sw_shut_total_e[i] = s_s["nearfield_e"] + s_s["background_e"]

    print(f"\n  {'u [%]':>7s}  {'D_eff [m]':>10s}  {'f/#_eff':>8s}  {'Ω_cone [sr]':>12s}"
          f"  {'NF [e⁻]':>11s}  {'Signal [e⁻]':>12s}  {'SNR [-]':>9s}  {'NEDT [mK]':>10s}"
          f"  {'MTF_nyq':>8s}")
    print(f"  {'-' * 7}  {'-' * 10}  {'-' * 8}  {'-' * 12}  {'-' * 11}  {'-' * 12}"
          f"  {'-' * 9}  {'-' * 10}  {'-' * 8}")
    for i in range(0, n, 2):
        nedt_str = f"{sw_nedt[i] * 1e3:>10.2f}" if not np.isnan(sw_nedt[i]) else f"{'N/A':>10s}"
        mtf_str = f"{sw_mtf_nyq[i]:>8.4f}" if not np.isnan(sw_mtf_nyq[i]) else f"{'N/A':>8s}"
        print(f"  {UNDERSIZE_SWEEP[i] * 100:>7.1f}  {sw_d_eff[i]:>10.5f}  {sw_f_eff[i]:>8.4f}"
              f"  {sw_omega_cone[i]:>12.6f}  {sw_nearfield_e[i]:>11,.0f}"
              f"  {sw_signal_e[i]:>12,.0f}  {sw_snr[i]:>9.2f}  {nedt_str}  {mtf_str}")

    u_max = UNDERSIZE_SWEEP[-1]
    print(f"\n  The trade over 0 → {u_max * 100:.0f} % undersizing:")
    print(f"    A_collect  {sw_a_collect[0]:.6f} → {sw_a_collect[-1]:.6f} m²"
          f"   ({(sw_a_collect[-1] / sw_a_collect[0] - 1) * 100:+.1f} %)")
    print(f"    Ω_cone     {sw_omega_cone[0]:.6f} → {sw_omega_cone[-1]:.6f} sr"
          f"   ({(sw_omega_cone[-1] / sw_omega_cone[0] - 1) * 100:+.1f} %)")
    print(f"    Near-field {sw_nearfield_e[0]:,.0f} → {sw_nearfield_e[-1]:,.0f} e⁻"
          f"   ({(sw_nearfield_e[-1] / sw_nearfield_e[0] - 1) * 100:+.1f} %)")
    print(f"    Signal     {sw_signal_e[0]:,.0f} → {sw_signal_e[-1]:,.0f} e⁻"
          f"   ({(sw_signal_e[-1] / sw_signal_e[0] - 1) * 100:+.1f} %)")
    print(f"    SNR        {sw_snr[0]:.2f} → {sw_snr[-1]:.2f} [-]"
          f"   ({(sw_snr[-1] / sw_snr[0] - 1) * 100:+.1f} %)")
    if not np.isnan(sw_mtf_nyq[0]):
        print(f"    MTF@Nyq    {sw_mtf_nyq[0]:.4f} → {sw_mtf_nyq[-1]:.4f} [-]"
              f"   ({(sw_mtf_nyq[-1] / sw_mtf_nyq[0] - 1) * 100:+.1f} %)")
    print()
    print("    Signal and near-field fall TOGETHER, because both are set by the same")
    print("    effective pupil. Undersizing is not a way to buy a darker background for")
    print("    free — it buys the CERTAINTY that no warm structure is in view, and pays")
    print("    for it in aperture, resolution, and SNR.")

    # -----------------------------------------------------------------------
    # Step 5: Requirement assessment
    # -----------------------------------------------------------------------
    MAX_BKG_E = float(reqs["Max background signal (shuttered)"])  # e⁻

    print("\n=== Requirements Assessment ===")
    print(f"  Maximum allowed shuttered background: {MAX_BKG_E:,.0f} e⁻")
    print(f"  Model prediction at u = 0:            {sw_shut_total_e[0]:,.0f} e⁻"
          f"  [{'PASS' if sw_shut_total_e[0] <= MAX_BKG_E else 'FAIL'}]")
    print(f"  Model prediction at u = {u_max * 100:.0f} %:           "
          f"{sw_shut_total_e[-1]:,.0f} e⁻"
          f"  [{'PASS' if sw_shut_total_e[-1] <= MAX_BKG_E else 'FAIL'}]")
    print()
    print("  Undersizing lowers the shuttered background only as fast as Ω_cone falls")
    print(f"  ({(sw_shut_total_e[-1] / sw_shut_total_e[0] - 1) * 100:+.1f} % over the sweep)."
          "  It is not a background-control knob:")
    print("  the levers that matter are the optics temperature and the coating")
    print("  emissivity, both of which scale the near-field directly.")

    # -----------------------------------------------------------------------
    # Step 6: Lab measurements against the model
    # -----------------------------------------------------------------------
    print("\n=== Lab Measurements vs. Model ===")
    print("  Under the Gap-128 rules a cold stop cannot MANUFACTURE background: it")
    print("  cannot attenuate in-cone emission, and out-of-cone structure is taken to be")
    print("  blocked completely. So the cold-stop POSITION column below no longer has a")
    print("  model knob to be inverted onto — the 'best-fit leakage fraction' the old")
    print("  model reported was an artifact of a knob that should never have existed.")
    print("  What the measurements now bound is the WARM TRAIN itself: near-field scales")
    print("  linearly with the emitting emissivity Σ(1 − R) at fixed Ω_cone and T_optics,")
    print("  so each measurement inverts to an implied per-mirror reflectance.")
    print()
    eps_model = N_MIRRORS * (1.0 - MIRROR_R)  # [-] assumed emitting emissivity
    model_bkg = float(sw_shut_total_e[0])  # e⁻ at u = 0
    print(f"  {'Test Point':<14s} {'Pos [mm]':>10s}  {'Meas [e⁻]':>12s}  {'Model [e⁻]':>12s}"
          f"  {'Δ [%]':>8s}  {'implied ε':>10s}  {'implied R':>10s}  {'Status':>8s}")
    print(f"  {'-' * 14} {'-' * 10}  {'-' * 12}  {'-' * 12}  {'-' * 8}  {'-' * 10}"
          f"  {'-' * 10}  {'-' * 8}")
    for d in lab_data:
        delta_pct = (d["bkg_e"] / model_bkg - 1.0) * 100.0
        eps_implied = eps_model * d["bkg_e"] / model_bkg          # [-]
        r_implied = 1.0 - eps_implied / N_MIRRORS                 # [-] per mirror
        status = "PASS" if d["bkg_e"] <= MAX_BKG_E else "FAIL"
        print(f"  {d['test_id']:<14s} {d['position_mm']:>10.1f}  {d['bkg_e']:>12,.0f}"
              f"  {model_bkg:>12,.0f}  {delta_pct:>+8.1f}  {eps_implied:>10.4f}"
              f"  {r_implied:>10.4f}  {status:>8s}")

    best = min(d["bkg_e"] for d in lab_data)
    worst = max(d["bkg_e"] for d in lab_data)
    print()
    print(f"  Every measurement sits BELOW the modelled {model_bkg:,.0f} e⁻, so the assumed")
    print(f"  R = {MIRROR_R:.2f} [-] per mirror is pessimistic for this camera: the lab data")
    print(f"  bracket the real train at R ≈ {1.0 - eps_model * worst / model_bkg / N_MIRRORS:.3f}"
          f"–{1.0 - eps_model * best / model_bkg / N_MIRRORS:.3f} [-] (or, equivalently, a")
    print("  barrel colder than the assumed 20 °C). That is a statement about coatings and")
    print("  thermal design — testable, and physically meaningful — where the old model")
    print("  offered only a fitted leakage fraction that hid the same disagreement.")
    print(f"  The {(worst - best) / best * 100:.0f} % spread ACROSS cold-stop positions is what the")
    print("  new rules cannot explain: with a cold stop present, position should not move")
    print("  the background at all. A monotone rise with offset therefore points at warm")
    print("  structure entering the acceptance cone as the stop shifts — i.e. the stop is")
    print("  no longer the aperture stop at those offsets, which is outside this model's")
    print("  scope (accepted limitation, Gap 128) and is itself the finding.")

    # -----------------------------------------------------------------------
    # Step 7: Plots
    # -----------------------------------------------------------------------
    u_pct = UNDERSIZE_SWEEP * 100.0

    # ---- Plot 1: signal and near-field fall together ----------------------
    fig1, ax1 = plt.subplots(figsize=(9, 6))
    ax1.plot(u_pct, sw_signal_e / 1e3, "b-", linewidth=2, label="Signal [ke⁻]")
    ax1.plot(u_pct, sw_nearfield_e / 1e3, "r--", linewidth=2, label="Near-field [ke⁻]")
    ax1.set_xlabel("Cold-stop undersizing u [% of pupil diameter]", fontsize=11)
    ax1.set_ylabel("Charge [ke⁻]", fontsize=11)
    ax1.set_title("Signal and Near-Field Fall Together with the Effective Pupil",
                  fontsize=13, fontweight="bold")
    ax1.legend(loc="best", fontsize=9)
    ax1.grid(True, alpha=0.3)
    fig1.tight_layout()
    fig1.savefig(PLOT_DIR / "fig1_signal_and_nearfield_vs_undersize.png", dpi=150)
    print(f"\n  Saved {PLOT_DIR / 'fig1_signal_and_nearfield_vs_undersize.png'}")

    # ---- Plot 2: SNR and MTF — the cost of margin -------------------------
    fig2, ax2a = plt.subplots(figsize=(9, 5))
    ax2a.plot(u_pct, sw_snr, "b-", linewidth=2, label="SNR [-]")
    ax2a.set_xlabel("Cold-stop undersizing u [% of pupil diameter]", fontsize=11)
    ax2a.set_ylabel("SNR [-]", fontsize=11, color="blue")
    ax2a.tick_params(axis="y", labelcolor="blue")
    ax2b = ax2a.twinx()
    ax2b.plot(u_pct, sw_mtf_nyq, "g--", linewidth=1.5, label="MTF at Nyquist [-]")
    ax2b.set_ylabel("MTF at Nyquist [-]", fontsize=11, color="green")
    ax2b.tick_params(axis="y", labelcolor="green")
    lines_a, labels_a = ax2a.get_legend_handles_labels()
    lines_b, labels_b = ax2b.get_legend_handles_labels()
    ax2a.legend(lines_a + lines_b, labels_a + labels_b, loc="center right", fontsize=9)
    ax2a.set_title("The Cost of Tolerancing Margin: SNR and Resolution",
                   fontsize=13, fontweight="bold")
    ax2a.grid(True, alpha=0.3)
    fig2.tight_layout()
    fig2.savefig(PLOT_DIR / "fig2_snr_and_mtf_vs_undersize.png", dpi=150)
    print(f"  Saved {PLOT_DIR / 'fig2_snr_and_mtf_vs_undersize.png'}")

    # ---- Plot 3: shuttered background vs requirement, with lab points -----
    fig3, ax3 = plt.subplots(figsize=(9, 6))
    ax3.plot(u_pct, sw_shut_total_e / 1e3, "b-", linewidth=2,
             label="Model: shuttered background")
    ax3.axhline(MAX_BKG_E / 1e3, color="red", linestyle="--", linewidth=1.2,
                label=f"Requirement: {MAX_BKG_E / 1e3:.0f} ke⁻")
    for d in lab_data:
        ax3.axhline(d["bkg_e"] / 1e3, color="gray", linestyle=":", linewidth=0.8)
        ax3.annotate(f"{d['test_id']} ({d['bkg_e'] / 1e3:.1f} ke⁻)",
                     xy=(u_pct[-1], d["bkg_e"] / 1e3),
                     textcoords="offset points", xytext=(-140, 3), fontsize=7,
                     color="darkred")
    ax3.set_xlabel("Cold-stop undersizing u [% of pupil diameter]", fontsize=11)
    ax3.set_ylabel("Shuttered background [ke⁻]", fontsize=11)
    ax3.set_title("Shuttered Background vs. Undersizing — and Karen's Measurements",
                  fontsize=13, fontweight="bold")
    ax3.legend(loc="center left", fontsize=9)
    ax3.grid(True, alpha=0.3)
    fig3.tight_layout()
    fig3.savefig(PLOT_DIR / "fig3_shuttered_background_vs_undersize.png", dpi=150)
    print(f"  Saved {PLOT_DIR / 'fig3_shuttered_background_vs_undersize.png'}")

    # ---- Plot 4: the pupil itself -----------------------------------------
    fig4, ax4a = plt.subplots(figsize=(9, 5))
    ax4a.plot(u_pct, sw_a_collect * 1e4, "b-", linewidth=2, label="A_collect [cm²]")
    ax4a.set_xlabel("Cold-stop undersizing u [% of pupil diameter]", fontsize=11)
    ax4a.set_ylabel("A_collect [cm²]", fontsize=11, color="blue")
    ax4a.tick_params(axis="y", labelcolor="blue")
    ax4b = ax4a.twinx()
    ax4b.plot(u_pct, sw_omega_cone * 1e3, "r--", linewidth=1.5, label="Ω_cone [msr]")
    ax4b.set_ylabel("Ω_cone [msr]", fontsize=11, color="red")
    ax4b.tick_params(axis="y", labelcolor="red")
    lines_a, labels_a = ax4a.get_legend_handles_labels()
    lines_b, labels_b = ax4b.get_legend_handles_labels()
    ax4a.legend(lines_a + lines_b, labels_a + labels_b, loc="upper right", fontsize=9)
    ax4a.set_title("One Effective Pupil: Collecting Area and Acceptance Cone",
                   fontsize=13, fontweight="bold")
    ax4a.grid(True, alpha=0.3)
    fig4.tight_layout()
    fig4.savefig(PLOT_DIR / "fig4_pupil_vs_undersize.png", dpi=150)
    print(f"  Saved {PLOT_DIR / 'fig4_pupil_vs_undersize.png'}")

    plt.show()

    # -----------------------------------------------------------------------
    # Step 8: Output workbook
    # -----------------------------------------------------------------------
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    wb_out = openpyxl.Workbook()

    header_font_out = Font(bold=True, size=11)
    pass_fill = PatternFill(start_color="C6EFCE", end_color="C6EFCE", fill_type="solid")
    fail_fill = PatternFill(start_color="FFC7CE", end_color="FFC7CE", fill_type="solid")
    thin_border = Border(
        left=Side(style="thin"), right=Side(style="thin"),
        top=Side(style="thin"), bottom=Side(style="thin"),
    )

    ws1 = wb_out.active
    ws1.title = "Undersizing Sweep"
    ws1["A1"] = "Scenario 7.4: Cold-Stop Undersizing Sweep"
    ws1["A1"].font = Font(bold=True, size=14)
    for col, width in zip("ABCDEFGHIJ", [12, 12, 10, 14, 14, 14, 14, 10, 12, 10]):
        ws1.column_dimensions[col].width = width

    sweep_headers = [
        "u [-]", "D_eff [m]", "f/#_eff [-]", "A_collect [m^2]", "Omega_cone [sr]",
        "Nearfield [e-]", "Signal [e-]", "SNR [-]", "NEDT [mK]", "MTF_nyq [-]",
    ]
    for col, h_text in enumerate(sweep_headers, 1):
        cell = ws1.cell(row=3, column=col, value=h_text)
        cell.font = header_font_out
        cell.border = thin_border
        cell.alignment = Alignment(horizontal="center")

    for i in range(n):
        r = i + 4
        values = [
            round(float(UNDERSIZE_SWEEP[i]), 4),
            round(float(sw_d_eff[i]), 6),
            round(float(sw_f_eff[i]), 4),
            round(float(sw_a_collect[i]), 8),
            round(float(sw_omega_cone[i]), 8),
            round(float(sw_nearfield_e[i]), 0),
            round(float(sw_signal_e[i]), 0),
            round(float(sw_snr[i]), 3),
            round(float(sw_nedt[i]) * 1e3, 3) if not np.isnan(sw_nedt[i]) else "N/A",
            round(float(sw_mtf_nyq[i]), 5) if not np.isnan(sw_mtf_nyq[i]) else "N/A",
        ]
        for col, value in enumerate(values, 1):
            ws1.cell(row=r, column=col, value=value).border = thin_border

    ws2 = wb_out.create_sheet("Lab Comparison")
    ws2["A1"] = "Lab shuttered background vs. model prediction"
    ws2["A1"].font = Font(bold=True, size=14)
    for col, width in zip("ABCDE", [16, 16, 18, 18, 14]):
        ws2.column_dimensions[col].width = width
    lab_headers = ["Test Point", "Position [mm]", "Meas Bkg [e-]", "Model Bkg [e-]", "Status"]
    for col, h_text in enumerate(lab_headers, 1):
        cell = ws2.cell(row=3, column=col, value=h_text)
        cell.font = header_font_out
        cell.border = thin_border
        cell.alignment = Alignment(horizontal="center")
    for i, d in enumerate(lab_data, 4):
        ws2.cell(row=i, column=1, value=d["test_id"]).border = thin_border
        ws2.cell(row=i, column=2, value=d["position_mm"]).border = thin_border
        ws2.cell(row=i, column=3, value=d["bkg_e"]).border = thin_border
        ws2.cell(row=i, column=4, value=round(model_bkg, 0)).border = thin_border
        status = "PASS" if d["bkg_e"] <= MAX_BKG_E else "FAIL"
        status_cell = ws2.cell(row=i, column=5, value=status)
        status_cell.border = thin_border
        status_cell.fill = pass_fill if status == "PASS" else fail_fill

    ws3 = wb_out.create_sheet("Summary")
    ws3["A1"] = "Scenario 7.4: Cold-Stop Undersizing Summary"
    ws3["A1"].font = Font(bold=True, size=14)
    ws3.column_dimensions["A"].width = 45
    ws3.column_dimensions["B"].width = 30

    summary_items = [
        ("Instrument", ""),
        ("Aperture (primary)", f"{aperture_m * 100:.0f} cm"),
        ("f-number (primary)", f"{f_number}"),
        ("Optics temperature", f"{optics_temp_K:.1f} K"),
        ("Warm train", f"{N_MIRRORS} mirrors at R = {MIRROR_R:.2f} + AR window "
                       f"T = {window_T:.3f}"),
        ("Net train transmission", f"{transmission:.2f} [-]"),
        ("Emitting emissivity", f"{N_MIRRORS * (1.0 - MIRROR_R):.3f} [-]"),
        ("Spectral band", f"{band_min_um:.2f} – {band_max_um:.2f} µm"),
        ("Integration time", f"{t_int_s * 1000:.0f} ms"),
        ("", ""),
        ("Baseline (u = 0, stop matched to primary)", ""),
        ("D_eff [m]", f"{sw_d_eff[0]:.5f}"),
        ("f/#_eff [-]", f"{sw_f_eff[0]:.4f}"),
        ("Omega_cone [sr]", f"{sw_omega_cone[0]:.6f}"),
        ("Nearfield [e-]", f"{baseline_nearfield_e:.0f}"),
        ("Signal [e-]", f"{baseline_signal_e:.0f}"),
        ("SNR [-]", f"{baseline_snr:.2f}"),
        ("NEDT [mK]", f"{baseline_nedt * 1e3:.2f}" if baseline_nedt is not None else "N/A"),
        ("MTF at Nyquist [-]",
         f"{baseline_mtf_nyq:.4f}" if baseline_mtf_nyq is not None else "N/A"),
        ("", ""),
        (f"At u = {u_max * 100:.0f} % undersizing", ""),
        ("A_collect change [%]", f"{(sw_a_collect[-1] / sw_a_collect[0] - 1) * 100:+.1f}"),
        ("Omega_cone change [%]", f"{(sw_omega_cone[-1] / sw_omega_cone[0] - 1) * 100:+.1f}"),
        ("Nearfield change [%]", f"{(sw_nearfield_e[-1] / sw_nearfield_e[0] - 1) * 100:+.1f}"),
        ("SNR change [%]", f"{(sw_snr[-1] / sw_snr[0] - 1) * 100:+.1f}"),
        ("", ""),
        ("Requirements", ""),
        ("Max shuttered background [e-]", f"{MAX_BKG_E:.0f}"),
        ("Model shuttered background at u = 0 [e-]", f"{sw_shut_total_e[0]:.0f}"),
        ("", ""),
        ("Lab Results", ""),
    ]
    for d in lab_data:
        status = "PASS" if d["bkg_e"] <= MAX_BKG_E else "FAIL"
        summary_items.append(
            (f"{d['test_id']} ({d['position_mm']:.1f} mm offset)",
             f"{d['bkg_e']:.0f} e- [{status}]")
        )

    for i, (label, value) in enumerate(summary_items, 3):
        cell_a = ws3.cell(row=i, column=1, value=label)
        ws3.cell(row=i, column=2, value=value)
        if label and not value:
            cell_a.font = Font(bold=True, size=11)

    wb_out.save(OUTPUT_FILE)
    print(f"\nResults written to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
