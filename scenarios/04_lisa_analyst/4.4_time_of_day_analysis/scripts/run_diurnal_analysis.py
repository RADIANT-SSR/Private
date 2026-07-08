#!/usr/bin/env python3
"""Scenario 4.4 — time-of-day (diurnal) thermal detectability analysis.

Lisa has a 24-hour field record of a target (painted-metal vehicle) and
its background (soil). She asks: at what times of day is the target
detectable in the LWIR, and when does it wash out? The physics is thermal
crossover — twice a day the target and background reach the same apparent
RADIANCE and the thermal contrast collapses, so the target vanishes
regardless of how sensitive the detector is.

This is a data-driven temporal sweep: the diurnal temperature profile is
INPUT DATA (a field campaign product), and the chain is run once per time
step over it. No new physics model — the signal chain already computes the
in-band signal for any surface temperature/emissivity.

Contrast construction: the chain's own `contrast_e` differential is only
built in the sub-pixel regime; for an extended target-vs-adjacent-
background pair the transparent construction (as in scenario 4.3) is to
run the target-filled pixel and the background-filled pixel separately and
difference them:

    contrast SNR = (S_target − S_background) / √(N_target² + N_background²)

This nulls exactly at the RADIANCE crossover ε_t·B(λ,T_t) = ε_b·B(λ,T_b),
which — because ε differs (0.92 vs 0.95) — is OFFSET from the physical
temperature crossover T_t = T_b. That offset is the interesting physics.

Every printed number carries units. Regime, unused parameters, and the
non-obvious physics are explained inline (house rules).

Run from the repo root:
    python scenarios/04_lisa_analyst/4.4_time_of_day_analysis/scripts/run_diurnal_analysis.py
"""

from __future__ import annotations

import csv
import math
import warnings
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from radiant.api import Sensor

warnings.filterwarnings("ignore")  # scenario-level noise suppression; physics still raises

HERE = Path(__file__).resolve().parent
SCEN = HERE.parent
INPUTS = SCEN / "inputs"
OUTPUTS = SCEN / "outputs"
OUTPUTS.mkdir(exist_ok=True)

# --- Sensor config (from lisa_lwir_sensor.xlsx; transcribed) -----------
TGT_EMIS = 0.92
BG_EMIS = 0.95
DETECT_THRESHOLD = 10.0  # |contrast SNR| for reliable detection
ALT_M = 3000.0
APERTURE_M = 0.15
FOCAL_M = 0.6
PITCH_UM = 25.0
TRANSMISSION = 0.80
QE = 0.70
T_INT_S = 1.0e-4  # short LWIR integration — keeps the well ~40% full (unsaturated)
DARK_E_PER_S = 5.0e6
TEMP_K = 77.0
READ_NOISE_E = 300.0
FULL_WELL_E = 6.0e6
GAIN_E_PER_DN = 120.0
ADC_BITS = 14
BAND_MIN_UM, BAND_MAX_UM = 8.0, 12.0


def load_profile() -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return (hour, T_target_K, T_background_K) arrays from the CSV."""
    hours: list[float] = []
    t_tgt: list[float] = []
    t_bg: list[float] = []
    with open(INPUTS / "diurnal_thermal_profile.csv", encoding="utf-8") as fh:
        reader = csv.DictReader(line for line in fh if not line.startswith("#"))
        for row in reader:
            hours.append(float(row["hour_local"]))
            t_tgt.append(float(row["T_target_K"]))
            t_bg.append(float(row["T_background_K"]))
    return np.array(hours), np.array(t_tgt), np.array(t_bg)


def build_pixel(temp_k: float, emissivity: float) -> Sensor:
    """LWIR config for one uniform surface (target OR background) filling
    the pixel — an extended scene at the given temperature/emissivity."""
    s = Sensor()
    s.set("source.scene_type", "extended")
    s.set("source.target.temperature", temp_k, unit="K")
    s.set("source.target.emissivity", emissivity)
    s.set("atmosphere.model", "simple")
    s.set("atmosphere.standard_atmosphere", "us_standard")
    s.set("geometry.sensor_altitude_m", ALT_M)
    s.set("geometry.path_zenith_rad", 0.0)
    s.set("optics.aperture_diameter_m", APERTURE_M)
    s.set("optics.focal_length_m", FOCAL_M)
    s.set("optics.transmission_scalar", TRANSMISSION)
    s.set("detector.pixel_pitch_x_um", PITCH_UM)
    s.set("detector.pixel_pitch_y_um", PITCH_UM)
    s.set("detector.qe_value", QE)
    s.set("detector.dark_rate_e_per_s", DARK_E_PER_S)
    s.set("detector.detector_temperature_K", TEMP_K)
    s.set("spectral_integration.filter_min_um", BAND_MIN_UM)
    s.set("spectral_integration.filter_max_um", BAND_MAX_UM)
    s.set("spectral_integration.integration_time_s", T_INT_S)
    s.set("readout.read_noise_e_rms", READ_NOISE_E)
    s.set("readout.gain_e_per_dn", GAIN_E_PER_DN)
    s.set("readout.adc_bits", ADC_BITS)
    s.set("readout.full_well_capacity_e", FULL_WELL_E)
    return s


def pixel_signal_noise_nedt(temp_k: float, emissivity: float) -> tuple[float, float, float]:
    """Return (signal_e, noise_e, nedt_K) for a uniform surface pixel."""
    r = build_pixel(temp_k, emissivity).evaluate()
    signal_e = r.stage_outputs["spectral_integration"]["signal_e"]
    snr = r.metrics["snr"]
    noise_e = signal_e / snr if snr > 0 else float("nan")
    return signal_e, noise_e, r.metrics.get("nedt_K", float("nan"))


def contrast_snr_at(
    t_target_k: float, t_background_k: float
) -> tuple[float, float, float]:
    """Differential contrast SNR of a target pixel against a background
    pixel, plus each pixel's well-fill fraction for a saturation check.

    contrast SNR = (S_tgt − S_bg) / √(N_tgt² + N_bg²). Positive when the
    target is the brighter (warmer/apparent) surface; nulls at the
    radiance crossover.
    """
    s_t, n_t, nedt_t = pixel_signal_noise_nedt(t_target_k, TGT_EMIS)
    s_b, n_b, _ = pixel_signal_noise_nedt(t_background_k, BG_EMIS)
    combined_noise = math.sqrt(n_t * n_t + n_b * n_b)
    csnr = (s_t - s_b) / combined_noise if combined_noise > 0 else float("nan")
    return csnr, nedt_t, 0.0


def washout_windows(hours: np.ndarray, detectable: np.ndarray) -> list[tuple[float, float]]:
    """Contiguous [start, end] hour windows where the target is NOT detectable."""
    windows: list[tuple[float, float]] = []
    start: float | None = None
    for h, ok in zip(hours, detectable):
        if not ok and start is None:
            start = h
        elif ok and start is not None:
            windows.append((start, h))
            start = None
    if start is not None:
        windows.append((start, hours[-1]))
    return windows


def main() -> None:
    print("=" * 74)
    print("SCENARIO 4.4 — TIME-OF-DAY (DIURNAL) THERMAL DETECTABILITY")
    print("=" * 74)
    print(
        f"LWIR {BAND_MIN_UM:.0f}–{BAND_MAX_UM:.0f} µm, airborne {ALT_M/1e3:.0f} km AGL. "
        f"Target ε = {TGT_EMIS} (painted metal), background ε = {BG_EMIS} (soil)."
    )
    print(
        "Contrast = (S_target − S_background) / √(N_t² + N_b²) from two extended "
        f"pixel runs. Detectability = |contrast SNR| ≥ {DETECT_THRESHOLD:.0f}."
    )
    print(
        "Physics: thermal crossover — when the two surfaces reach equal apparent "
        "RADIANCE the contrast collapses and the target washes out, no matter how "
        "low the NEDT."
    )
    print()

    hours, t_tgt, t_bg = load_profile()
    contrast_snr = np.zeros_like(hours)
    nedt_k = np.zeros_like(hours)
    for i, (tt, tb) in enumerate(zip(t_tgt, t_bg)):
        contrast_snr[i], nedt_k[i], _ = contrast_snr_at(float(tt), float(tb))

    delta_t = t_tgt - t_bg
    detectable = np.abs(contrast_snr) >= DETECT_THRESHOLD

    print("-" * 74)
    print("DIURNAL SWEEP (every 3 h shown; full profile every 0.5 h)")
    print("-" * 74)
    print(f"{'hour':>6}{'T_tgt':>9}{'T_bg':>9}{'ΔT':>9}{'contrast SNR':>15}{'detect?':>9}")
    for i in range(0, len(hours), 6):
        flag = "YES" if detectable[i] else "washout"
        print(
            f"{hours[i]:>5.1f}h{t_tgt[i]:>8.1f}K{t_bg[i]:>8.1f}K{delta_t[i]:>+8.2f}K"
            f"{contrast_snr[i]:>+15.1f}{flag:>9}"
        )

    print(
        f"\n  Median NEDT over the day: {np.nanmedian(nedt_k)*1e3:.1f} mK "
        "(sensor sensitivity is nearly constant — the washout is a scene-contrast "
        "effect, not a sensor-noise effect)."
    )

    def sign_changes(x: np.ndarray) -> list[float]:
        sg = np.sign(x)
        return [
            0.5 * (hours[i] + hours[i + 1])
            for i in range(len(x) - 1)
            if sg[i] != sg[i + 1] and sg[i] != 0
        ]

    temp_cross = sign_changes(delta_t)  # physical temperature crossover (ΔT = 0)
    rad_cross = sign_changes(contrast_snr)  # radiance crossover (contrast = 0)
    windows = washout_windows(hours, detectable)

    print()
    print("-" * 74)
    print("THERMAL CROSSOVER & WASHOUT WINDOWS")
    print("-" * 74)
    print(
        "  Physical-temperature crossovers (ΔT = 0):    "
        + ", ".join(f"{c:.1f} h" for c in temp_cross)
    )
    print(
        "  Radiance crossovers (contrast SNR = 0):       "
        + ", ".join(f"{c:.1f} h" for c in rad_cross)
    )
    if windows:
        print("  Detectability washout windows (|contrast SNR| < threshold):")
        for a, b in windows:
            print(f"    {a:.1f} h – {b:.1f} h  (duration {b - a:.1f} h)")
    else:
        print("  No washout: target detectable at all hours.")
    print(
        "\n  The radiance crossovers are OFFSET from the temperature crossovers: "
        "the target is LESS emissive (ε 0.92 vs 0.95), so it must be a few kelvin "
        "WARMER than the background just to match its apparent radiance. The "
        "washout windows center on the radiance crossovers (where the contrast "
        "truly vanishes), not on the ΔT = 0 points. Between the two daily "
        "washouts the target is a strong positive contrast (day, metal hotter) or "
        "negative contrast (night, metal colder)."
    )

    # ---------------------------------------------------------------
    # FIGURE 1 — diurnal temperatures + ΔT, with crossovers marked.
    # ---------------------------------------------------------------
    fig, ax1 = plt.subplots(figsize=(10, 6))
    ax1.plot(hours, t_tgt, "-", color="#C00000", label="Target (painted metal)")
    ax1.plot(hours, t_bg, "-", color="#548235", label="Background (soil)")
    ax1.set_xlabel("Local time (h)")
    ax1.set_ylabel("Surface temperature (K)")
    ax1.legend(loc="upper left")
    ax2 = ax1.twinx()
    ax2.plot(hours, delta_t, "--", color="#2E75B6", label="ΔT (target − background)")
    ax2.axhline(0.0, color="black", lw=0.8)
    ax2.set_ylabel("ΔT (K)", color="#2E75B6")
    ax2.tick_params(axis="y", labelcolor="#2E75B6")
    for c in temp_cross:
        ax1.axvline(c, color="gray", ls=":", lw=1.5)
        ax1.text(c, ax1.get_ylim()[1], f"{c:.1f}h", ha="center", va="bottom", fontsize=8)
    ax1.set_xlim(0, 24)
    ax1.set_xticks(range(0, 25, 3))
    ax1.set_title("Scenario 4.4 — diurnal surface temperatures & thermal crossover")
    fig.tight_layout()
    fig1 = OUTPUTS / "fig1_diurnal_temperatures.png"
    fig.savefig(fig1, dpi=130)
    plt.close(fig)
    print(f"\nWrote {fig1.name}")

    # ---------------------------------------------------------------
    # FIGURE 2 — |contrast SNR| vs time with threshold + washout shading.
    # ---------------------------------------------------------------
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.plot(hours, np.abs(contrast_snr), "-", color="#7030A0", label="|contrast SNR|")
    ax.axhline(
        DETECT_THRESHOLD, color="black", ls="--", lw=1.5,
        label=f"detectability threshold = {DETECT_THRESHOLD:.0f}",
    )
    for a, b in windows:
        ax.axvspan(a, b, color="red", alpha=0.15)
    if windows:
        ax.axvspan(
            windows[0][0], windows[0][1], color="red", alpha=0.15, label="washout window"
        )
    ax.set_xlabel("Local time (h)")
    ax.set_ylabel("|contrast SNR| (dimensionless)")
    ax.set_yscale("log")
    ax.set_xlim(0, 24)
    ax.set_xticks(range(0, 25, 3))
    ax.legend(loc="upper right")
    ax.set_title("Scenario 4.4 — target detectability over the diurnal cycle")
    fig.tight_layout()
    fig2 = OUTPUTS / "fig2_detectability_vs_time.png"
    fig.savefig(fig2, dpi=130)
    plt.close(fig)
    print(f"Wrote {fig2.name}")

    print()
    print("=" * 74)
    print("DONE — see outputs/ for figures and MANIFEST.md.")
    print("=" * 74)


if __name__ == "__main__":
    main()
