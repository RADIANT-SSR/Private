#!/usr/bin/env python3
"""Scenario 5.5 — stray-light / veiling-glare impact on contrast and NIIRS.

Tom has a FRED stray-light analysis: veiling-glare index 3 %, out-of-field
stray irradiance 2.5 W/m², and a full 2-D stray-light PSF he cannot feed to
RADIANT (scalar inputs only). He wants the contrast, SNR, and NIIRS impact,
and the veiling-glare tolerance.

Scene: daytime VNIR pan band (0.5–0.8 µm), rooftop target (ρ = 0.30) against
vegetation (ρ = 0.15), airborne, solar zenith 30°.

Two RADIANT stray-light levers, and an important caveat:
  - `absolute_irradiance` mode is correct: Tom's 2.5 W/m² out-of-field stray
    injects a real electron pedestal → shot noise → SNR/NIIRS loss.
  - `veiling_glare` mode is CURRENTLY BROKEN (CU-062): it scales the in-FOV
    irradiance by the pixel IFOV solid angle instead of the f-cone, so it
    under-reports stray by ~(D/pitch)²·π/4 ≈ 10⁷–10⁸ and reports ZERO impact
    for any VGI. This script demonstrates that, then routes Tom's 3 % VGI
    through the correct physics via the identity  stray_e = VGI · S_scene
    (a uniform scene scatters VGI of its own per-pixel flux onto each pixel),
    expressed as an equivalent absolute irradiance so the chain — including
    its GIQE/NIIRS — sees the right pedestal.

RADIANT models stray light as a uniform NOISE pedestal only: it adds shot
noise and, because the pedestal is common to target and background, leaves
the contrast SIGNAL unchanged (contrast degrades purely through added
noise). The classic veiling-glare MTF / contrast-modulation reduction is NOT
modelled (gaps.md).

Every printed number carries units; the model's assumptions and the VGI-mode
bug are called out inline (house rules).

Run from the repo root:
    python scenarios/05_tom_optical_designer/5.5_stray_light_veiling_glare/\
scripts/run_straylight_analysis.py
"""

from __future__ import annotations

import math
import warnings
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from radiant.api import Sensor

warnings.filterwarnings("ignore")

HERE = Path(__file__).resolve().parent
SCEN = HERE.parent
OUTPUTS = SCEN / "outputs"
OUTPUTS.mkdir(exist_ok=True)

# --- Scene + sensor (tom_straylight.xlsx) -----------------------------
RHO_TARGET = 0.30
RHO_BG = 0.15
BAND = (0.5, 0.8)
APERTURE_M = 0.15
FOCAL_M = 0.90  # f/6
PITCH_UM = 15.0
QE = 0.60
DARK_E_PER_S = 2.0e4
T_DET_K = 290.0
T_INT_S = 5.0e-3
READ_E = 30.0
FWC_E = 3.0e5
ALT_M = 7000.0
SOLAR_ZENITH_RAD = math.radians(30.0)

VGI_FRED = 0.03  # Tom's FRED veiling-glare index
STRAY_ABS_W_M2 = 2.5  # Tom's out-of-field stray irradiance
NIIRS_DROP_BUDGET = 0.2  # a 0.2-NIIRS loss is Tom's tolerance
SNR_FLOOR = 50.0  # contrast-SNR floor for the task


def build(
    rho: float, *, mode: str = "veiling_glare", vgi: float = 0.0, abs_irr: float = 0.0
) -> Sensor:
    s = Sensor()
    s.set("source.scene_type", "extended")
    s.set("source.target.reflectance", rho)
    s.set("atmosphere.model", "simple")
    s.set("atmosphere.standard_atmosphere", "us_standard")
    s.set("geometry.sensor_altitude_m", ALT_M)
    s.set("geometry.path_zenith_rad", 0.0)
    s.set("geometry.solar_zenith_rad", SOLAR_ZENITH_RAD)
    s.set("optics.aperture_diameter_m", APERTURE_M)
    s.set("optics.focal_length_m", FOCAL_M)
    s.set("optics.transmission_scalar", 0.8)
    s.set("optics.stray.input_mode", mode)
    s.set("optics.stray.veiling_glare_fraction", vgi)
    s.set("optics.stray.absolute_irradiance_W_m2", abs_irr)
    s.set("detector.pixel_pitch_x_um", PITCH_UM)
    s.set("detector.pixel_pitch_y_um", PITCH_UM)
    s.set("detector.qe_value", QE)
    s.set("detector.dark_rate_e_per_s", DARK_E_PER_S)
    s.set("detector.detector_temperature_K", T_DET_K)
    s.set("spectral_integration.filter_min_um", BAND[0])
    s.set("spectral_integration.filter_max_um", BAND[1])
    s.set("spectral_integration.integration_time_s", T_INT_S)
    s.set("readout.read_noise_e_rms", READ_E)
    s.set("readout.full_well_capacity_e", FWC_E)
    return s


def _run(rho: float, *, mode: str = "veiling_glare", vgi: float = 0.0, abs_irr: float = 0.0):
    r = build(rho, mode=mode, vgi=vgi, abs_irr=abs_irr).evaluate()
    si = r.stage_outputs["spectral_integration"]
    det = r.stage_outputs["detector"]
    return {
        "signal_e": si["signal_e"],
        "snr": r.metrics["snr"],
        "niirs": r.metrics.get("niirs"),
        "stray_e": det.get("stray_e", 0.0),
        "noise_e": si["signal_e"] / r.metrics["snr"],
    }


def _contrast_snr(t: dict, b: dict) -> float:
    return (t["signal_e"] - b["signal_e"]) / math.sqrt(t["noise_e"] ** 2 + b["noise_e"] ** 2)


def main() -> None:
    print("=" * 80)
    print("SCENARIO 5.5 — STRAY-LIGHT / VEILING-GLARE IMPACT ON CONTRAST & NIIRS")
    print("=" * 80)
    print(
        f"Daytime VNIR {BAND[0]}–{BAND[1]} µm, rooftop ρ={RHO_TARGET} vs veg ρ={RHO_BG}, "
        f"solar zenith {math.degrees(SOLAR_ZENITH_RAD):.0f}°, D {APERTURE_M * 100:.0f} cm "
        f"f/{FOCAL_M / APERTURE_M:.0f}."
    )
    print()

    # --- Clean baseline ------------------------------------------------
    ct = _run(RHO_TARGET)
    cb = _run(RHO_BG)
    c_csnr = _contrast_snr(ct, cb)
    s_scene = 0.5 * (ct["signal_e"] + cb["signal_e"])  # mean in-FOV per-pixel flux
    print("-" * 80)
    print("1. CLEAN BASELINE (no stray light)")
    print("-" * 80)
    print(
        f"  target signal {ct['signal_e']:.3e} e-, background {cb['signal_e']:.3e} e-; "
        f"SNR {ct['snr']:.1f}, contrast SNR {c_csnr:.1f}, NIIRS {ct['niirs']:.3f}."
    )

    # --- Demonstrate the veiling_glare-mode bug (CU-062) ---------------
    vgi_run = _run(RHO_TARGET, mode="veiling_glare", vgi=0.10)
    print()
    print("-" * 80)
    print("2. NATIVE veiling_glare MODE IS INERT (bug CU-062)")
    print("-" * 80)
    print(
        f"  optics.stray.veiling_glare_fraction = 0.10 → stray_e = "
        f"{vgi_run['stray_e']:.3e} e- (should be ~0.10 × {s_scene:.2e} ≈ "
        f"{0.10 * s_scene:.2e} e-). SNR {vgi_run['snr']:.1f} vs clean {ct['snr']:.1f} — "
        "UNCHANGED. The native mode scales by the pixel IFOV solid angle, not the "
        "f-cone; it under-reports stray by ~(D/pitch)²·π/4 and does nothing. "
        "Below we route VGI through the correct physics."
    )

    # --- Calibrate stray_e per W/m² from the correct absolute mode -----
    ref_irr = 1.0
    k_e_per_W = _run(RHO_TARGET, mode="absolute_irradiance", abs_irr=ref_irr)["stray_e"] / ref_irr
    print(f"\n  Calibration: absolute-irradiance mode gives {k_e_per_W:.3e} stray e- per W/m².")

    # --- Tom's two FRED inputs, done correctly -------------------------
    print()
    print("-" * 80)
    print("3. STRAY-LIGHT IMPACT — Tom's FRED inputs (correct physics)")
    print("-" * 80)
    print(f"{'case':>28}{'stray e-':>13}{'SNR':>9}{'contrast SNR':>15}{'NIIRS':>9}{'ΔNIIRS':>9}")

    def stray_case(label: str, abs_irr: float) -> dict:
        t = _run(RHO_TARGET, mode="absolute_irradiance", abs_irr=abs_irr)
        b = _run(RHO_BG, mode="absolute_irradiance", abs_irr=abs_irr)
        csnr = _contrast_snr(t, b)
        dn = t["niirs"] - ct["niirs"]
        print(
            f"{label:>28}{t['stray_e']:>13.3e}{t['snr']:>9.1f}{csnr:>15.1f}"
            f"{t['niirs']:>9.3f}{dn:>9.3f}"
        )
        return {"snr": t["snr"], "csnr": csnr, "niirs": t["niirs"], "stray_e": t["stray_e"]}

    print(
        f"{'clean':>28}{0.0:>13.3e}{ct['snr']:>9.1f}{c_csnr:>15.1f}{ct['niirs']:>9.3f}{0.0:>9.3f}"
    )
    # VGI 3% → equivalent absolute irradiance via stray_e = VGI·S_scene
    vgi_abs = VGI_FRED * s_scene / k_e_per_W
    stray_case(f"veiling glare {VGI_FRED:.0%} (corrected)", vgi_abs)
    stray_case(f"out-of-field {STRAY_ABS_W_M2} W/m²", STRAY_ABS_W_M2)
    print(
        f"\n  Tom's 3 % veiling glare adds {VGI_FRED * s_scene:.2e} stray e- (≈ 3 % of the "
        "scene) — a modest noise penalty. His 2.5 W/m² out-of-field stray is far worse: "
        f"{k_e_per_W * STRAY_ABS_W_M2:.2e} e-, several × the signal, cutting SNR and "
        "costing NIIRS. Stray light degrades contrast SNR purely by added shot noise — "
        "the uniform pedestal cancels in the target−background difference, so the "
        "contrast SIGNAL is unchanged (RADIANT does not model the veiling-glare MTF "
        "reduction; gaps.md)."
    )

    # --- VGI tolerance sweep -------------------------------------------
    vgis = np.linspace(0.0, 0.10, 21)
    sweep = []
    for v in vgis:
        abs_irr = v * s_scene / k_e_per_W
        t = _run(RHO_TARGET, mode="absolute_irradiance", abs_irr=abs_irr)
        b = _run(RHO_BG, mode="absolute_irradiance", abs_irr=abs_irr)
        sweep.append((v, t["snr"], _contrast_snr(t, b), t["niirs"]))
    # tolerance: largest VGI keeping ΔNIIRS ≤ budget AND contrast SNR ≥ floor
    tol_vgi = 0.0
    for v, _snr, csnr, niirs in sweep:
        if (ct["niirs"] - niirs) <= NIIRS_DROP_BUDGET and csnr >= SNR_FLOOR:
            tol_vgi = v
    print()
    print("-" * 80)
    print("4. VEILING-GLARE TOLERANCE (sweep 0–10 %)")
    print("-" * 80)
    print(
        f"  Largest VGI holding ΔNIIRS ≤ {NIIRS_DROP_BUDGET} AND contrast SNR ≥ "
        f"{SNR_FLOOR:.0f}: VGI ≈ {tol_vgi:.1%}. Tom's 3 % sits "
        f"{'inside' if tol_vgi >= VGI_FRED else 'OUTSIDE'} that budget."
    )

    _figure_sweep(sweep, tol_vgi, ct["niirs"])
    _figure_budget(ct, cb, stray_e_abs=k_e_per_W * STRAY_ABS_W_M2)

    print()
    print("=" * 80)
    print(
        "SUMMARY: 3 % veiling glare is a mild noise penalty; the 2.5 W/m² out-of-field "
        "stray is the real threat. NB: the native veiling_glare mode is inert (CU-062); "
        "route VGI through absolute irradiance until fixed. See outputs/ + MANIFEST.md."
    )
    print("=" * 80)


def _figure_sweep(sweep: list, tol_vgi: float, niirs_clean: float) -> None:
    v = [s[0] * 100 for s in sweep]
    csnr = [s[2] for s in sweep]
    dniirs = [niirs_clean - s[3] for s in sweep]
    fig, ax1 = plt.subplots(figsize=(9, 6))
    ax1.plot(v, csnr, "-o", color="#264478", ms=3, label="contrast SNR")
    ax1.axhline(SNR_FLOOR, color="#264478", ls=":", lw=1, label=f"SNR floor {SNR_FLOOR:.0f}")
    ax1.set_xlabel("Veiling glare index (%)")
    ax1.set_ylabel("Contrast SNR", color="#264478")
    ax1.tick_params(axis="y", labelcolor="#264478")
    ax2 = ax1.twinx()
    ax2.plot(v, dniirs, "-s", color="#C55A11", ms=3, label="ΔNIIRS")
    ax2.axhline(
        NIIRS_DROP_BUDGET, color="#C55A11", ls=":", lw=1, label=f"ΔNIIRS budget {NIIRS_DROP_BUDGET}"
    )
    ax2.set_ylabel("NIIRS loss", color="#C55A11")
    ax2.tick_params(axis="y", labelcolor="#C55A11")
    ax1.axvline(VGI_FRED * 100, color="black", ls="--", lw=1, label=f"FRED VGI {VGI_FRED:.0%}")
    ax1.axvspan(0, tol_vgi * 100, color="green", alpha=0.08)
    ax1.set_title("Scenario 5.5 — veiling-glare tolerance (contrast SNR & NIIRS loss)")
    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, loc="center right", fontsize=8)
    fig.tight_layout()
    out = OUTPUTS / "fig1_vgi_tolerance.png"
    fig.savefig(out, dpi=130)
    plt.close(fig)
    print(f"\nWrote {out.name}")


def _figure_budget(ct: dict, cb: dict, stray_e_abs: float) -> None:
    # Noise-term comparison: clean vs +2.5 W/m² stray (shot on signal + stray).
    shot_clean = math.sqrt(ct["signal_e"])
    read_dark = math.sqrt(max(0.0, ct["noise_e"] ** 2 - ct["signal_e"]))
    stray_shot = math.sqrt(stray_e_abs)
    labels = ["shot (signal)", "read+dark", "stray shot"]
    clean = [shot_clean, read_dark, 0.0]
    strayed = [shot_clean, read_dark, stray_shot]
    x = np.arange(len(labels))
    w = 0.38
    fig, ax = plt.subplots(figsize=(8, 6))
    ax.bar(x - w / 2, clean, w, label="clean", color="#7F7F7F")
    ax.bar(x + w / 2, strayed, w, label="+2.5 W/m² stray", color="#C0392B")
    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.set_ylabel("Noise (e- RMS)")
    ax.set_title("Scenario 5.5 — noise budget: stray-light shot noise dominates")
    ax.legend(fontsize=9)
    for i, b in enumerate(strayed):
        if b > 0:
            ax.annotate(
                f"{b:.0f}",
                (i + w / 2, b),
                textcoords="offset points",
                xytext=(0, 3),
                ha="center",
                fontsize=8,
            )
    fig.tight_layout()
    out = OUTPUTS / "fig2_noise_budget.png"
    fig.savefig(out, dpi=130)
    plt.close(fig)
    print(f"Wrote {out.name}")


if __name__ == "__main__":
    main()
