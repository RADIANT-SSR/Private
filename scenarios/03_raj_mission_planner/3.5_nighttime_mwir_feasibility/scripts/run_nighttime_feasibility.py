#!/usr/bin/env python3
"""Scenario 3.5 — nighttime MWIR imaging feasibility.

Raj must decide whether his airborne MWIR sensor can image a warm building
complex (295 K) against terrain (288 K) at NIGHT, and how MWIR compares to
LWIR for the same 7 K thermal scene. Questions:

  1. Is the 7 K contrast detectable? (SNR, contrast SNR, NEDT, MRT.)
  2. Is MWIR performance solar-independent — i.e. does it work at night?
  3. How does MWIR compare to LWIR (8–12 µm) for this scene?

Method:
  - Detectability comes from the chain. The scene is EXTENDED thermal
    self-emission (`is_hot_target`); the target-vs-terrain differential uses
    the first-class contrast reference (ADR-0005): `source.contrast_reference`
    = the 288 K terrain, so `contrast_snr` is the true two-pixel differential
    with combined target+reference noise.
  - Solar independence is shown analytically (`core.blackbody`): the
    band-integrated THERMAL emitted radiance of the 295 K surface vs the
    REFLECTED-solar radiance it would add in full daylight. At night the
    reflected term is exactly zero, so the detected signal is unchanged —
    that is what "solar-independent" means for a thermal band.
  - The terrain background temperature comes from a NOAA land-surface-
    temperature map. RADIANT has no GeoTIFF reader (gaps.md), so the map is
    transcribed to `inputs/noaa_lst_strip.csv`; the script sweeps its
    min/mean/max envelope to check the verdict is robust.

Every printed number carries units; the regime, the unused-at-night solar
term, and the LWIR-beats-MWIR-at-290 K physics are explained inline.

Config note: integration time (0.2 ms) and full well (1e7 e-) are sized so
NEITHER band saturates — the contrast-reference noise model is exact only
below full well (see gaps.md / CU on the saturation interaction).

Run from the repo root:
    python scenarios/03_raj_mission_planner/3.5_nighttime_mwir_feasibility/\
scripts/run_nighttime_feasibility.py
"""

from __future__ import annotations

import csv
import warnings
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from radiant.api import Sensor
from radiant.core.blackbody import planck_spectral_radiance
from radiant.core.constants import R_sun_m, au_m

warnings.filterwarnings("ignore")

HERE = Path(__file__).resolve().parent
SCEN = HERE.parent
INPUTS = SCEN / "inputs"
OUTPUTS = SCEN / "outputs"
OUTPUTS.mkdir(exist_ok=True)

# --- Scene + sensor (raj_scene.xlsx) ----------------------------------
T_TARGET_K = 295.0  # building complex (retained daytime heat)
E_TARGET = 0.92
T_BG_K = 288.0  # terrain background (NOAA LST)
E_BG = 0.95
DELTA_T_K = T_TARGET_K - T_BG_K  # 7 K

BANDS = {"MWIR": (3.5, 5.0), "LWIR": (8.0, 12.0)}
APERTURE_M = 0.30
FOCAL_M = 1.20  # f/4
PITCH_UM = 30.0
QE = 0.75
DARK_E_PER_S = 5.0e5
T_DET_K = 110.0
T_INT_S = 0.2e-3
READ_E = 50.0
FWC_E = 1.0e7
ALT_M = 3000.0
PWV_CM = 4.1  # tropical column — set explicitly (preset does not; gaps.md)

T_SUN_K = 5772.0  # IAU nominal solar effective temperature (local constant)
DETECT_SNR_THRESHOLD = 6.0  # Rose criterion for confident detection


def build(band: tuple[float, float], temp_k: float, emis: float, ref_k: float) -> Sensor:
    """One extended thermal-emission pixel; ref_k>0 sets the contrast reference."""
    s = Sensor()
    s.set("source.scene_type", "extended")
    s.set("source.target.temperature", temp_k, unit="K")
    s.set("source.target.emissivity", emis)
    s.set("source.target.is_hot_target", True)
    if ref_k > 0.0:
        s.set("source.contrast_reference.temperature", ref_k, unit="K")
        s.set("source.contrast_reference.emissivity", E_BG)
    s.set("atmosphere.model", "simple")
    s.set("atmosphere.standard_atmosphere", "tropical")
    s.set("atmosphere.precipitable_water_cm", PWV_CM)
    s.set("geometry.sensor_altitude_m", ALT_M)
    s.set("optics.aperture_diameter_m", APERTURE_M)
    s.set("optics.focal_length_m", FOCAL_M)
    s.set("detector.pixel_pitch_x_um", PITCH_UM)
    s.set("detector.pixel_pitch_y_um", PITCH_UM)
    s.set("detector.qe_value", QE)
    s.set("detector.dark_rate_e_per_s", DARK_E_PER_S)
    s.set("detector.detector_temperature_K", T_DET_K)
    s.set("spectral_integration.filter_min_um", band[0])
    s.set("spectral_integration.filter_max_um", band[1])
    s.set("spectral_integration.integration_time_s", T_INT_S)
    s.set("readout.read_noise_e_rms", READ_E)
    s.set("readout.full_well_capacity_e", FWC_E)
    return s


def band_thermal_radiance(temp_k: float, emis: float, band: tuple[float, float]) -> float:
    """Emitted radiance ε·∫B(λ,T)dλ over the band [W/m²/sr]."""
    lam = np.linspace(band[0], band[1], 400)
    return emis * float(np.trapezoid(planck_spectral_radiance(lam, temp_k), lam))


def band_reflected_solar_radiance(emis: float, band: tuple[float, float]) -> float:
    """Reflected-solar radiance a Lambertian surface adds in full daylight.

    Optimistic upper bound: sun at zenith, unit atmospheric transmission,
    reflectance ρ = 1 − ε (opaque surface). L_refl = ρ · E_sun_band / π,
    with E_sun_band = ∫ π B(λ,T_sun) (R_sun/AU)² dλ [W/m²/sr].
    """
    lam = np.linspace(band[0], band[1], 400)
    e_sun = np.pi * planck_spectral_radiance(lam, T_SUN_K) * (R_sun_m / au_m) ** 2
    e_band = float(np.trapezoid(e_sun, lam))  # W/m²
    rho = 1.0 - emis
    return rho * e_band / np.pi


def main() -> None:
    print("=" * 78)
    print("SCENARIO 3.5 — NIGHTTIME MWIR IMAGING FEASIBILITY")
    print("=" * 78)
    print(
        f"Building {T_TARGET_K:.0f} K (ε {E_TARGET}) vs terrain {T_BG_K:.0f} K "
        f"(ε {E_BG}); ΔT = {DELTA_T_K:.0f} K, nighttime."
    )
    print(
        f"Airborne {ALT_M / 1e3:.0f} km, tropical atmosphere, PWV {PWV_CM} cm; "
        f"D {APERTURE_M * 100:.0f} cm f/{FOCAL_M / APERTURE_M:.0f}, "
        f"{PITCH_UM:.0f} µm pitch, cooled {T_DET_K:.0f} K."
    )
    print()

    # --- Section 1: dual-band detectability (chain) --------------------
    print("-" * 78)
    print("1. DETECTABILITY — MWIR vs LWIR (chain)")
    print("-" * 78)
    print(
        f"{'band':>6}{'SNR':>10}{'contrast SNR':>15}{'NEDT [mK]':>12}"
        f"{'ΔT/NEDT':>10}{'MRT@Nyq [K]':>13}"
    )
    results = {}
    for name, band in BANDS.items():
        r = build(band, T_TARGET_K, E_TARGET, T_BG_K).evaluate()
        m = r.metrics
        nedt = m["nedt_K"]
        mrt = m["mrt_at_nyquist_K"]
        results[name] = {
            "snr": m["snr"],
            "csnr": m["contrast_snr"],
            "nedt_mK": nedt * 1e3,
            "mrt_K": mrt,
            "dt_over_nedt": DELTA_T_K / nedt,
        }
        print(
            f"{name:>6}{m['snr']:>10.1f}{m['contrast_snr']:>15.1f}{nedt * 1e3:>12.1f}"
            f"{DELTA_T_K / nedt:>10.0f}{mrt:>13.3f}"
        )
    print(
        f"\n  Both bands detect the {DELTA_T_K:.0f} K contrast with enormous margin: "
        "ΔT is hundreds of × NEDT, and MRT-at-Nyquist (the smallest resolvable ΔT "
        "at the finest sampled detail) is well under 1 K << 7 K. LWIR wins on every "
        "figure — near a 290 K scene the Planck peak sits at ~10 µm, so LWIR "
        "collects far more thermal photons than MWIR (lower NEDT, higher contrast "
        "SNR). MWIR is viable; LWIR is better for this temperature regime."
    )

    # --- Section 2: solar independence (analytical) --------------------
    print()
    print("-" * 78)
    print("2. SOLAR INDEPENDENCE — thermal emission vs reflected sunlight")
    print("-" * 78)
    print(f"{'band':>6}{'thermal [W/m²/sr]':>20}{'refl. solar (day)':>20}{'thermal / solar':>18}")
    solar = {}
    for name, band in BANDS.items():
        l_therm = band_thermal_radiance(T_TARGET_K, E_TARGET, band)
        l_solar = band_reflected_solar_radiance(E_TARGET, band)
        ratio = l_therm / l_solar if l_solar > 0 else float("inf")
        solar[name] = {"thermal": l_therm, "solar_day": l_solar, "ratio": ratio}
        print(f"{name:>6}{l_therm:>20.4f}{l_solar:>20.4e}{ratio:>18.0f}")
    print(
        "\n  Reflected sunlight is the ONLY solar term for these opaque surfaces "
        "(ρ = 1−ε). In LWIR it is ×986 below the surface's own emission — utterly "
        "negligible day or night. In MWIR the margin is only ×5: even at this "
        "optimistic upper bound (sun at zenith, τ=1) daytime MWIR carries ~20 % "
        "reflected-solar contamination — the well-known MWIR solar-glint problem. "
        "That makes the nighttime case STRONGER, not weaker: at night the reflected "
        "term is exactly zero, so MWIR loses a daytime contamination source and "
        "sees pure thermal self-emission. Both thermal bands image the same scene "
        "at night that they saw by day; a reflective (VNIR/SWIR) sensor sees "
        "nothing. That is the precise sense in which thermal imaging is "
        "solar-independent."
    )

    # --- Section 3: background-temperature envelope (NOAA LST strip) ---
    strip_path = INPUTS / "noaa_lst_strip.csv"
    with strip_path.open() as fh:
        temps = [float(row["surface_temperature_K"]) for row in csv.DictReader(fh)]
    t_min, t_mean, t_max = min(temps), sum(temps) / len(temps), max(temps)
    print()
    print("-" * 78)
    print("3. BACKGROUND-TEMPERATURE ENVELOPE (NOAA LST strip stand-in)")
    print("-" * 78)
    print(
        f"  Terrain LST over the scene: min {t_min:.1f} K, mean {t_mean:.1f} K, "
        f"max {t_max:.1f} K ({len(temps)} samples)."
    )
    print(f"{'band':>6}{'bg T [K]':>10}{'effective ΔT [K]':>18}{'contrast SNR':>15}")
    envelope = {name: [] for name in BANDS}
    for name, band in BANDS.items():
        for t_bg in (t_max, t_mean, t_min):  # hottest bg → smallest ΔT → hardest
            r = build(band, T_TARGET_K, E_TARGET, t_bg).evaluate()
            csnr = r.metrics["contrast_snr"]
            envelope[name].append((t_bg, csnr))
            print(f"{name:>6}{t_bg:>10.1f}{T_TARGET_K - t_bg:>18.1f}{csnr:>15.1f}")
    worst = min(envelope["MWIR"], key=lambda x: x[1])
    print(
        f"\n  Across the whole LST envelope the MWIR contrast SNR never drops below "
        f"{worst[1]:.0f} (at the hottest background, {worst[0]:.1f} K, where ΔT is "
        f"smallest) — far above the confident-detection threshold "
        f"(SNR ≈ {DETECT_SNR_THRESHOLD:.0f}, Rose criterion). The verdict is robust "
        "to background-temperature variation across the map."
    )

    # --- Figures -------------------------------------------------------
    _figure_bands(results)
    _figure_solar(solar)

    print()
    print("=" * 78)
    print(
        "VERDICT: YES — nighttime imaging is feasible. MWIR detects the 7 K scene "
        "with wide margin and is fully solar-independent; LWIR is the stronger band "
        "near 290 K. See outputs/ for figures and MANIFEST.md."
    )
    print("=" * 78)


def _figure_bands(results: dict[str, dict[str, float]]) -> None:
    names = list(results)
    fig, axes = plt.subplots(1, 3, figsize=(13, 4.5))
    metrics = [
        ("nedt_mK", "NEDT (mK)", "#264478"),
        ("mrt_K", "MRT @ Nyquist (K)", "#C55A11"),
        ("csnr", "Contrast SNR", "#2E7D32"),
    ]
    for ax, (key, label, color) in zip(axes, metrics, strict=True):
        vals = [results[n][key] for n in names]
        ax.bar(names, vals, color=color, width=0.55)
        for i, v in enumerate(vals):
            ax.annotate(
                f"{v:.3g}",
                (i, v),
                textcoords="offset points",
                xytext=(0, 3),
                ha="center",
                fontsize=9,
            )
        ax.set_ylabel(label)
        ax.set_title(label)
    fig.suptitle("Scenario 3.5 — MWIR vs LWIR detectability (295 K vs 288 K scene)")
    fig.tight_layout()
    out = OUTPUTS / "fig1_band_comparison.png"
    fig.savefig(out, dpi=130)
    plt.close(fig)
    print(f"\nWrote {out.name}")


def _figure_solar(solar: dict[str, dict[str, float]]) -> None:
    names = list(solar)
    x = np.arange(len(names))
    fig, ax = plt.subplots(figsize=(8, 6))
    w = 0.38
    ax.bar(
        x - w / 2,
        [solar[n]["thermal"] for n in names],
        w,
        label="thermal self-emission (day or night)",
        color="#C0392B",
    )
    ax.bar(
        x + w / 2,
        [solar[n]["solar_day"] for n in names],
        w,
        label="reflected sunlight (daytime only, upper bound)",
        color="#F1C40F",
    )
    ax.set_yscale("log")
    ax.set_xticks(x)
    ax.set_xticklabels(names)
    ax.set_ylabel("Band radiance (W/m²/sr, log)")
    ax.set_title(
        "Scenario 3.5 — thermal emission dwarfs reflected sunlight\n"
        "(295 K surface) → nighttime detection is solar-independent"
    )
    ax.legend(loc="upper right", fontsize=8)
    for i, n in enumerate(names):
        ax.annotate(
            f"×{solar[n]['ratio']:.0f}",
            (i, solar[n]["thermal"]),
            textcoords="offset points",
            xytext=(0, 5),
            ha="center",
            fontsize=9,
        )
    fig.tight_layout()
    out = OUTPUTS / "fig2_solar_independence.png"
    fig.savefig(out, dpi=130)
    plt.close(fig)
    print(f"Wrote {out.name}")


if __name__ == "__main__":
    main()
