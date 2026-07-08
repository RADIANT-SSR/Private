#!/usr/bin/env python3
"""Scenario 1.5 — obscured aperture & spider vanes.

Sarah's Cassegrain telescope has a central obscuration (the secondary
mirror) and four spider arms that support it. She asks: how much do the
obscuration and the struts degrade image quality versus an ideal
unobstructed aperture, and how does the degradation grow with strut width?

The scenario exercises the new spider-vane pupil masking
(`optics.n_spiders`, `optics.spider_width_m`). Because RADIANT builds both
the PSF and the optical MTF from the same complex pupil, the struts enter
both spatial paths (Rule 4) — the visible signature is the four-point
diffraction spike, which scatters energy out of the PSF core.

Every printed number carries units. The regime, the metrics, and the
non-obvious physics (why Strehl is unmoved but EE/RER fall) are explained
inline (house rules).

Run from the repo root:
    python scenarios/01_sarah_systems_engineer/1.5_obscured_aperture_spider_vanes/scripts/run_obscured_aperture.py
"""

from __future__ import annotations

import math
import warnings
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import LogNorm

from radiant.api import Sensor

warnings.filterwarnings("ignore")  # scenario-level noise suppression; physics still raises

HERE = Path(__file__).resolve().parent
SCEN = HERE.parent
OUTPUTS = SCEN / "outputs"
OUTPUTS.mkdir(exist_ok=True)

# --- Telescope config (from sarah_cassegrain.xlsx) --------------------
APERTURE_M = 0.50
OBSCURATION = 0.30
FOCAL_M = 6.0
PITCH_UM = 6.5
TRANSMISSION = 0.85
QE = 0.85
ALT_M = 500e3
SOLAR_ZENITH_DEG = 30.0
REFLECTANCE = 0.30
T_INT_S = 0.5e-3
DARK_E_PER_S = 50.0
TEMP_K = 280.0
READ_NOISE_E = 20.0
FULL_WELL_E = 30000.0
GAIN_E_PER_DN = 5.0
ADC_BITS = 12
BAND_MIN_UM, BAND_MAX_UM = 0.45, 0.70


def build_sensor(obscuration: float, n_spiders: int, spider_width_m: float) -> Sensor:
    """VNIR Cassegrain configuration with the given pupil geometry."""
    s = Sensor()
    s.set("source.scene_type", "extended")
    s.set("source.target.reflectance", REFLECTANCE)
    s.set("atmosphere.model", "simple")
    s.set("atmosphere.standard_atmosphere", "us_standard")
    s.set("geometry.sensor_altitude_m", ALT_M)
    s.set("geometry.path_zenith_rad", 0.0)
    s.set("geometry.solar_zenith_rad", math.radians(SOLAR_ZENITH_DEG))
    s.set("optics.aperture_diameter_m", APERTURE_M)
    s.set("optics.focal_length_m", FOCAL_M)
    s.set("optics.transmission_scalar", TRANSMISSION)
    s.set("optics.obscuration_ratio", obscuration)
    s.set("optics.n_spiders", n_spiders)
    s.set("optics.spider_width_m", spider_width_m)
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


def metrics_of(result: object) -> dict[str, float]:
    m = result.metrics  # type: ignore[attr-defined]
    return {
        "snr": m["snr"],
        "ee_3x3": m.get("ee_3x3", float("nan")),
        "rer": m.get("rer", float("nan")),
        "mtf_nyq": m.get("mtf_at_nyquist", float("nan")),
        "strehl": m.get("strehl", float("nan")),
    }


def psf_core(result: object, half: int = 80) -> np.ndarray:
    """Central crop of the effective PSF for display."""
    data = result.stage_outputs["optics"]["effective_psf"].data  # type: ignore[attr-defined]
    c = data.shape[0] // 2
    return data[c - half : c + half, c - half : c + half]


def main() -> None:
    print("=" * 74)
    print("SCENARIO 1.5 — OBSCURED APERTURE & SPIDER VANES")
    print("=" * 74)
    print(
        f"Cassegrain: {APERTURE_M*100:.0f} cm primary, obscuration ε = {OBSCURATION}, "
        f"4 spider arms; f/{FOCAL_M/APERTURE_M:.0f}, VNIR pan."
    )
    print(
        "Regime: EXTENDED. Struts enter the pupil mask → both PSF and MTF (Rule 4); "
        "they also subtract from the radiometric clear area (lower SNR)."
    )
    print()

    # --- Three reference apertures --------------------------------------
    configs = [
        ("Unobstructed", 0.0, 0, 0.0),
        ("Obscured only (ε=0.30)", OBSCURATION, 0, 0.0),
        ("Obscured + 4× 3 cm spiders", OBSCURATION, 4, 0.03),
    ]
    print("-" * 74)
    print("APERTURE COMPARISON")
    print("-" * 74)
    print(f"{'Configuration':<30}{'SNR':>8}{'EE_3x3':>9}{'RER':>8}{'MTF@Nyq':>10}{'Strehl':>9}")
    results = {}
    for label, obs, ns, w in configs:
        r = build_sensor(obs, ns, w).evaluate()
        results[label] = r
        mm = metrics_of(r)
        print(
            f"{label:<30}{mm['snr']:>8.1f}{mm['ee_3x3']:>9.4f}{mm['rer']:>8.4f}"
            f"{mm['mtf_nyq']:>10.4f}{mm['strehl']:>9.4f}"
        )
    base = metrics_of(results["Unobstructed"])
    spid = metrics_of(results["Obscured + 4× 3 cm spiders"])
    print(
        f"\n  Unobstructed → full Cassegrain: SNR {base['snr']:.1f} → {spid['snr']:.1f} "
        f"({(spid['snr']/base['snr']-1)*100:+.1f}%), "
        f"EE_3x3 {base['ee_3x3']:.3f} → {spid['ee_3x3']:.3f} "
        f"({(spid['ee_3x3']/base['ee_3x3']-1)*100:+.1f}%)."
    )
    print(
        "  Strehl is ~1 in every row: it is a WFE metric, and the reference PSF "
        "carries the same aperture geometry, so obscuration/vanes cancel. The "
        "vane cost shows up in EE_3x3, RER, and SNR — not in Strehl."
    )

    # --- Spider-width sweep --------------------------------------------
    print()
    print("-" * 74)
    print("SPIDER-WIDTH SWEEP (obscuration fixed at ε=0.30, 4 arms)")
    print("-" * 74)
    widths_cm = np.array([0.0, 1.0, 2.0, 3.0, 4.0, 5.0])
    snr = np.zeros_like(widths_cm)
    ee = np.zeros_like(widths_cm)
    rer = np.zeros_like(widths_cm)
    print(f"{'width':>8}{'SNR':>9}{'EE_3x3':>10}{'RER':>9}")
    for i, wcm in enumerate(widths_cm):
        r = build_sensor(OBSCURATION, 4 if wcm > 0 else 0, wcm / 100.0).evaluate()
        mm = metrics_of(r)
        snr[i], ee[i], rer[i] = mm["snr"], mm["ee_3x3"], mm["rer"]
        print(f"{wcm:>6.0f}cm{snr[i]:>9.1f}{ee[i]:>10.4f}{rer[i]:>9.4f}")
    print(
        "\n  EE_3x3 and RER fall monotonically with strut width — each cm of strut "
        "scatters more core energy into the diffraction spikes and shaves the "
        "collecting area. Sarah's 3 cm baseline costs "
        f"{(1 - ee[3]/ee[0])*100:.0f}% of the encircled energy vs no struts."
    )

    # ---------------------------------------------------------------
    # FIGURE 1 — PSF cores (log scale) showing the diffraction spikes.
    # ---------------------------------------------------------------
    fig, axes = plt.subplots(1, 3, figsize=(15, 5.2))
    for ax, (label, obs, ns, w) in zip(axes, configs):
        core = psf_core(results[label])
        vmax = core.max()
        ax.imshow(core, norm=LogNorm(vmin=vmax * 1e-5, vmax=vmax), cmap="inferno")
        ax.set_title(label, fontsize=10)
        ax.set_xticks([])
        ax.set_yticks([])
    fig.suptitle(
        "Scenario 1.5 — effective PSF core (log scale): obscuration + spider spikes",
        fontsize=12,
    )
    fig.tight_layout()
    fig1 = OUTPUTS / "fig1_psf_diffraction_spikes.png"
    fig.savefig(fig1, dpi=130)
    plt.close(fig)
    print(f"\nWrote {fig1.name}")

    # ---------------------------------------------------------------
    # FIGURE 2 — EE / RER / SNR vs spider width.
    # ---------------------------------------------------------------
    fig, ax1 = plt.subplots(figsize=(9, 6))
    ax1.plot(widths_cm, ee / ee[0], "o-", color="#375623", label="EE_3x3 (normalised)")
    ax1.plot(widths_cm, rer / rer[0], "s-", color="#2E75B6", label="RER (normalised)")
    ax1.plot(widths_cm, snr / snr[0], "^-", color="#C55A11", label="SNR (normalised)")
    ax1.set_xlabel("Spider arm width (cm)")
    ax1.set_ylabel("Metric relative to no-strut value")
    ax1.set_title("Scenario 1.5 — image-quality degradation vs spider width\n(ε=0.30, 4 arms)")
    ax1.legend()
    ax1.grid(alpha=0.3)
    fig.tight_layout()
    fig2 = OUTPUTS / "fig2_degradation_vs_width.png"
    fig.savefig(fig2, dpi=130)
    plt.close(fig)
    print(f"Wrote {fig2.name}")

    print()
    print("=" * 74)
    print("DONE — see outputs/ for figures and MANIFEST.md.")
    print("=" * 74)


if __name__ == "__main__":
    main()
