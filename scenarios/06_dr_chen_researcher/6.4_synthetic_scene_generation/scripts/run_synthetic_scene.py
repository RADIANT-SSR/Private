#!/usr/bin/env python3
"""Scenario 6.4 — synthetic scene generation for algorithm testing.

Dr. Chen needs RADIANT to generate pixel-level signal and noise for a
synthetic scene with 5 targets at different ranges (each a different
temperature/emissivity/size) against a uniform 290 K background, so he can
test a detection algorithm. He wants a 1-D pixel strip, per-pixel signal and
noise, a simulated noisy image, an SNR map, and a ROC curve per target.

Method (RADIANT-native): the chain provides the radiometry — one extended
run for the background (→ background signal and total noise σ) and one per
target temperature (→ its extended signal). Each target is sub-pixel at its
range, so its contrast is the fill-fraction-diluted signal difference:

    ff = (target_size / GSD)²,  GSD = IFOV · range
    contrast_e = ff · (S_target_full − S_background)
    contrast SNR = contrast_e / σ

The ROC per target follows from its contrast SNR (equal-variance Gaussian
detection model, `radiant.performance.roc`).

Every printed number carries units; the regime and the noise model are
explained inline (house rules). A fixed RNG seed makes the noisy strip
reproducible.

Run from the repo root:
    python scenarios/06_dr_chen_researcher/6.4_synthetic_scene_generation/\
scripts/run_synthetic_scene.py
"""

from __future__ import annotations

import warnings
from pathlib import Path
from typing import NamedTuple

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from radiant.api import Sensor
from radiant.performance.roc import roc_auc, roc_curve

warnings.filterwarnings("ignore")

HERE = Path(__file__).resolve().parent
SCEN = HERE.parent
OUTPUTS = SCEN / "outputs"
OUTPUTS.mkdir(exist_ok=True)

# --- Scene + sensor (chen_scene.xlsx) ---------------------------------
TARGETS = [
    # name, range_km, T_K, emissivity, size_m
    ("T1", 10.0, 330.0, 0.95, 3.0),
    ("T2", 20.0, 322.0, 0.93, 3.0),
    ("T3", 50.0, 316.0, 0.92, 3.0),
    ("T4", 100.0, 310.0, 0.95, 3.0),
    ("T5", 200.0, 305.0, 0.93, 3.0),
]
BG_TEMP_K = 290.0
BG_EMIS = 0.95
BAND = (8.0, 12.0)
APERTURE_M = 0.05
FOCAL_M = 1.0
PITCH_UM = 25.0
QE = 0.70
DARK_E_PER_S = 1.0e6
READ_NOISE_E = 100.0
T_INT_S = 0.5e-3
P_FA = 1.0e-4
IFOV_RAD = (PITCH_UM * 1e-6) / FOCAL_M
FWC_E = 4.0e6
SEED = 20260708


class Row(NamedTuple):
    """Per-target radiometry result for one nominal scene target."""

    name: str
    range_km: float
    gsd_m: float
    ff: float
    s_tg_e: float
    s_bg_e: float
    sigma_e: float
    contrast_e: float
    csnr: float


def build(temp_k: float, emis: float, altitude_m: float) -> Sensor:
    s = Sensor()
    s.set("source.scene_type", "extended")
    s.set("source.target.temperature", temp_k, unit="K")
    s.set("source.target.emissivity", emis)
    s.set("source.target.is_hot_target", True)
    s.set("atmosphere.model", "simple")
    s.set("atmosphere.standard_atmosphere", "us_standard")
    s.set("geometry.sensor_altitude_m", altitude_m)
    s.set("optics.aperture_diameter_m", APERTURE_M)
    s.set("optics.focal_length_m", FOCAL_M)
    s.set("optics.transmission_scalar", 0.8)
    s.set("detector.pixel_pitch_x_um", PITCH_UM)
    s.set("detector.pixel_pitch_y_um", PITCH_UM)
    s.set("detector.qe_value", QE)
    s.set("detector.dark_rate_e_per_s", DARK_E_PER_S)
    s.set("detector.detector_temperature_K", 77.0)
    s.set("spectral_integration.filter_min_um", BAND[0])
    s.set("spectral_integration.filter_max_um", BAND[1])
    s.set("spectral_integration.integration_time_s", T_INT_S)
    s.set("readout.read_noise_e_rms", READ_NOISE_E)
    s.set("readout.gain_e_per_dn", 50.0)
    s.set("readout.adc_bits", 14)
    s.set("readout.full_well_capacity_e", FWC_E)
    return s


def main() -> None:
    print("=" * 76)
    print("SCENARIO 6.4 — SYNTHETIC SCENE GENERATION FOR ALGORITHM TESTING")
    print("=" * 76)
    print(
        f"5 targets vs {BG_TEMP_K:.0f} K background, LWIR {BAND[0]:.0f}–{BAND[1]:.0f} µm, "
        f"IFOV {IFOV_RAD * 1e6:.0f} µrad."
    )
    print(
        f"  Sub-pixel onset (GSD = target size = 3 m) is at range "
        f"{3.0 / IFOV_RAD / 1e3:.0f} km. Nearer than that a 3 m target is RESOLVED "
        "(fill fraction capped at 1); farther, it dilutes as 1/range²."
    )
    print()

    # --- Per-target radiometry (chain) ---------------------------------
    print("-" * 76)
    print("PER-TARGET SIGNAL, NOISE, AND CONTRAST SNR")
    print("-" * 76)
    print(
        f"{'target':>7}{'range':>9}{'GSD':>9}{'fill frac':>11}{'S_tgt [e-]':>13}"
        f"{'contrast [e-]':>15}{'SNR':>9}"
    )
    rows: list[Row] = []
    for name, rng_km, t_k, emis, size_m in TARGETS:
        alt_m = rng_km * 1e3
        r_bg = build(BG_TEMP_K, BG_EMIS, alt_m).evaluate()
        r_tg = build(t_k, emis, alt_m).evaluate()
        s_bg = r_bg.stage_outputs["spectral_integration"]["signal_e"]
        s_tg = r_tg.stage_outputs["spectral_integration"]["signal_e"]
        sigma = s_bg / r_bg.metrics["snr"]  # total noise on the pixel
        gsd = IFOV_RAD * alt_m
        ff = min(1.0, (size_m / gsd) ** 2)
        contrast_e = ff * (s_tg - s_bg)
        csnr = contrast_e / sigma
        rows.append(Row(name, rng_km, gsd, ff, s_tg, s_bg, sigma, contrast_e, csnr))
        print(
            f"{name:>7}{rng_km:>7.0f}km{gsd:>8.2f}m{ff:>11.4f}{s_tg:>13.3e}"
            f"{contrast_e:>15.1f}{csnr:>9.2f}"
        )

    sigma0 = rows[0].sigma_e
    s_bg0 = rows[0].s_bg_e
    print(
        f"\n  Background pixel: {s_bg0:.3e} e-, noise σ = {sigma0:.0f} e- "
        "(shot-noise-limited). All five nominal targets are 40–15 K hotter than the "
        "290 K background, so per-pixel contrast SNR runs 59–548 — every one is "
        "trivially detected (P_d ≈ 1). That is the physically correct answer for a "
        "5 cm LWIR sensor at these ranges; it is also why a ROC of just these five "
        "targets is uninformative (all curves pinned at the corner). The detection "
        "SCIENCE lives at the sensitivity floor, swept next."
    )

    from radiant.performance.roc import detection_probability

    # --- ROC per nominal target (for completeness) ---------------------
    print()
    print("-" * 76)
    print(f"ROC / DETECTABILITY — nominal targets (P_fa reference = {P_FA:.0e})")
    print("-" * 76)
    print(f"{'target':>7}{'contrast SNR':>15}{'ROC AUC':>10}{'P_d @ P_fa':>13}")
    for row in rows:
        d = abs(row.csnr)
        auc, pd = roc_auc(d), detection_probability(d, P_FA)
        print(f"{row.name:>7}{row.csnr:>15.2f}{auc:>10.4f}{pd:>13.4f}")

    # --- Detection-range sweep (the informative ROC) -------------------
    # In the extended regime the per-pixel background and full-target signals
    # are RANGE-INDEPENDENT (radiance × fixed pixel solid angle). Only the
    # fill fraction ff = (size / (IFOV·range))² changes with range. So pushing
    # the reference target (T5: 305 K, 3 m, ε 0.93) outward is a pure analytic
    # dilution of its already-computed signal — no re-running the chain — and
    # it walks the contrast SNR down through the informative band.
    ref = rows[-1]  # T5 row: uses its S_tg, S_bg, sigma
    sigma_ref = ref.sigma_e
    ref_size_m = TARGETS[-1][4]
    delta_full_e = ref.s_tg_e - ref.s_bg_e
    sweep_km = [200.0, 500.0, 800.0, 1100.0, 1300.0, 1500.0, 2000.0]
    print()
    print("-" * 76)
    print("DETECTION-RANGE SWEEP — reference target 305 K / 3 m / ε 0.93")
    print(f"(extended-regime dilution; P_fa reference = {P_FA:.0e})")
    print("-" * 76)
    print(
        f"{'range':>9}{'GSD':>9}{'fill frac':>11}{'contrast [e-]':>15}"
        f"{'SNR':>8}{'ROC AUC':>10}{'P_d @ P_fa':>13}"
    )
    sweep_rows = []
    for rng_km in sweep_km:
        gsd = IFOV_RAD * rng_km * 1e3
        ff = min(1.0, (ref_size_m / gsd) ** 2)
        contrast_e = ff * delta_full_e
        csnr = contrast_e / sigma_ref
        pd = detection_probability(abs(csnr), P_FA)
        sweep_rows.append((rng_km, csnr, pd))
        print(
            f"{rng_km:>7.0f}km{gsd:>8.2f}m{ff:>11.4f}{contrast_e:>15.1f}"
            f"{csnr:>8.2f}{roc_auc(abs(csnr)):>10.4f}{pd:>13.4f}"
        )

    # Range where P_d @ P_fa crosses 0.9 and 0.5 (linear interp in log-range).
    def crossing_range(target_pd: float) -> float:
        prev_r, prev_pd = sweep_rows[0][0], sweep_rows[0][2]
        for r_km, _c, pd in sweep_rows[1:]:
            if (prev_pd - target_pd) * (pd - target_pd) <= 0 and prev_pd != pd:
                frac = (prev_pd - target_pd) / (prev_pd - pd)
                lr = np.log(prev_r) + frac * (np.log(r_km) - np.log(prev_r))
                return float(np.exp(lr))
            prev_r, prev_pd = r_km, pd
        return float("nan")

    r90 = crossing_range(0.9)
    r50 = crossing_range(0.5)
    print(
        f"\n  Detection stays reliable (P_d ≥ 0.9 @ P_fa {P_FA:.0e}) out to "
        f"≈ {r90:.0f} km; the 50/50 range is ≈ {r50:.0f} km. Between them is the "
        "operating band where Dr. Chen's detection algorithm actually earns its "
        "keep — the ROC curves there sweep from near-certain to coin-flip."
    )

    # --- Simulated 1-D pixel strip (Poisson + Gaussian noise) ----------
    rng = np.random.default_rng(SEED)
    n_bg = 12  # background pixels between targets
    strip_clean: list[float] = []
    strip_labels: list[str] = []
    for row in rows:
        strip_clean.extend([row.s_bg_e] * n_bg)
        strip_labels.extend([""] * n_bg)
        strip_clean.append(row.s_bg_e + row.contrast_e)  # target pixel
        strip_labels.append(row.name)
    strip_clean.extend([s_bg0] * n_bg)
    strip_labels.extend([""] * n_bg)
    clean = np.array(strip_clean)
    # Poisson shot on the signal + Gaussian read noise.
    noisy = rng.poisson(np.clip(clean, 0, None)) + rng.normal(0.0, READ_NOISE_E, size=clean.shape)

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(11, 8), sharex=True)
    px = np.arange(clean.size)
    ax1.plot(px, noisy, "-", color="#888888", lw=0.8, label="simulated (noisy)")
    ax1.plot(px, clean, "-", color="#264478", lw=1.5, label="clean signal")
    for i, lab in enumerate(strip_labels):
        if lab:
            ax1.annotate(
                lab,
                (i, clean[i]),
                textcoords="offset points",
                xytext=(0, 8),
                ha="center",
                fontsize=8,
                color="#C00000",
            )
    ax1.set_ylabel("Pixel signal (e-)")
    ax1.set_title("Scenario 6.4 — synthetic 1-D scene strip (5 targets vs background)")
    ax1.legend(loc="upper right", fontsize=8)
    # SNR map (contrast SNR at each target pixel)
    ax2.axhline(0, color="black", lw=0.6)
    for i, lab in enumerate(strip_labels):
        if lab:
            csnr = next(r.csnr for r in rows if r.name == lab)
            ax2.bar(i, csnr, width=3.0, color="#C55A11")
            ax2.annotate(
                f"{csnr:.0f}",
                (i, csnr),
                textcoords="offset points",
                xytext=(0, 3),
                ha="center",
                fontsize=8,
            )
    ax2.set_ylabel("Contrast SNR")
    ax2.set_xlabel("Pixel index (1-D strip)")
    ax2.set_yscale("symlog")
    fig.tight_layout()
    fig1 = OUTPUTS / "fig1_scene_strip.png"
    fig.savefig(fig1, dpi=130)
    plt.close(fig)
    print(f"\nWrote {fig1.name}")

    # --- ROC figure (the informative detection-range sweep) ------------
    fig, ax = plt.subplots(figsize=(8, 7))
    for rng_km, csnr, _pd in sweep_rows:
        pfa, pd = roc_curve(abs(csnr), n_points=300)
        ax.semilogx(pfa, pd, "-", lw=2, label=f"{rng_km:.0f} km  (SNR {abs(csnr):.1f})")
    ax.plot([1e-6, 1], [1e-6, 1], "k--", lw=0.8, alpha=0.5, label="chance")
    ax.axvline(P_FA, color="black", ls=":", lw=1, label=f"P_fa = {P_FA:.0e}")
    ax.set_xlim(1e-6, 1)
    ax.set_xlabel("False-alarm probability P_fa")
    ax.set_ylabel("Detection probability P_d")
    ax.set_title("Scenario 6.4 — ROC vs range (305 K / 3 m reference target)")
    ax.set_ylim(0, 1.02)
    ax.legend(loc="lower right", fontsize=8, title="range (dilution)")
    ax.grid(alpha=0.3, which="both")
    fig.tight_layout()
    fig2 = OUTPUTS / "fig2_roc_curves.png"
    fig.savefig(fig2, dpi=130)
    plt.close(fig)
    print(f"Wrote {fig2.name}")

    print()
    print("=" * 76)
    print("DONE — see outputs/ for figures and MANIFEST.md.")
    print("=" * 76)


if __name__ == "__main__":
    main()
