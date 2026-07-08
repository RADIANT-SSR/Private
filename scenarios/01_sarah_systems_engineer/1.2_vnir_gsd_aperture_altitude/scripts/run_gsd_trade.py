#!/usr/bin/env python3
"""Scenario 1.2 — VNIR pan imager: GSD vs aperture vs altitude trade.

Sarah is sizing a sun-synchronous panchromatic imager. The panchromatic
GSD requirement is fixed at 0.5 m. She wants to know, across a range of
apertures and orbit altitudes, (1) what SNR she gets while holding that
0.5 m GSD, (2) where the system crosses from detector-limited to
diffraction-limited sampling, and (3) how the SNR moves across the four
seasons as the sun angle changes for her 10:30 LTAN orbit.

Design choice that defines the trade:
    GSD = pitch · altitude / focal_length  (nadir, small-angle)
so to HOLD GSD = 0.5 m at every altitude the focal length is DERIVED:
    focal_length(alt) = pitch · alt / 0.5 m
Then f/# = focal_length / aperture. Higher altitude ⇒ longer focal ⇒
higher f/# ⇒ less irradiance per pixel (extended source ∝ 1/f/#²) ⇒
lower SNR; larger aperture pulls f/# back down. That is the aperture-vs-
altitude trade AT CONSTANT GSD, and it is what the contour shows.

Illumination comes from the new solar-geometry model:
    LTAN 10:30 → local solar time → solar zenith θ_z(latitude, day).

Every printed number carries units. Regime, unused parameters, and the
non-obvious physics are explained inline (house rules).

Run from the repo root:
    python scenarios/01_sarah_systems_engineer/1.2_vnir_gsd_aperture_altitude/scripts/run_gsd_trade.py
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
from radiant.core.solar_geometry import (
    local_solar_time_from_ltan,
    solar_declination_deg,
    solar_zenith_angle_rad,
)
from radiant.io.qe_csv import load_qe_csv

warnings.filterwarnings("ignore")  # scenario-level noise suppression; physics still raises

HERE = Path(__file__).resolve().parent
SCEN = HERE.parent
INPUTS = SCEN / "inputs"
OUTPUTS = SCEN / "outputs"
OUTPUTS.mkdir(exist_ok=True)

# --- Fixed design (from sarah_vnir_design.xlsx; hard-coded so the script is
#     self-contained and reproducible) --------------------------------------
GSD_TARGET_M = 0.5
PITCH_UM = 6.5
PITCH_M = PITCH_UM * 1e-6
BAND_MIN_UM, BAND_MAX_UM = 0.45, 0.70
BAND_CENTER_UM = 0.5 * (BAND_MIN_UM + BAND_MAX_UM)  # 0.575 µm
TRANSMISSION = 0.85
DARK_E_PER_S = 50.0
TEMP_K = 280.0
READ_NOISE_E = 20.0
FULL_WELL_E = 30000.0
GAIN_E_PER_DN = 8.0
ADC_BITS = 12
T_INT_S = 0.5e-3
REFLECTANCE = 0.30
SNR_SPEC = 50.0
LTAN_HR = 10.5
TARGET_LAT_DEG = 35.0

# Sweep ranges
APERTURES_M = np.linspace(0.20, 0.80, 13)  # 20–80 cm
ALTITUDES_M = np.linspace(400e3, 600e3, 11)  # 400–600 km

SEASONS = [
    ("Spring equinox", 80),
    ("Summer solstice", 172),
    ("Autumn equinox", 266),
    ("Winter solstice", 355),
]
REF_ALT_M = 500e3
REF_APERTURE_M = 0.50


def build_sensor(aperture_m: float, altitude_m: float, solar_zenith_rad: float) -> Sensor:
    """One VNIR reflective configuration at fixed GSD = 0.5 m.

    Focal length is derived from the GSD requirement, so f/# rises with
    altitude. QE comes from the digitized silicon-CCD datasheet curve
    (band-averaged over the pan band).
    """
    focal_m = PITCH_M * altitude_m / GSD_TARGET_M
    qe = load_qe_csv(INPUTS / "silicon_ccd_qe.csv")
    qe_band = qe.band_averaged_qe(BAND_MIN_UM, BAND_MAX_UM)

    s = Sensor()
    # Reflective sunlit scene that fills the pixel → EXTENDED regime.
    s.set("source.scene_type", "extended")
    s.set("source.target.reflectance", REFLECTANCE)
    s.set("atmosphere.model", "simple")
    s.set("atmosphere.standard_atmosphere", "us_standard")
    s.set("geometry.sensor_altitude_m", altitude_m)
    s.set("geometry.path_zenith_rad", 0.0)  # nadir view
    s.set("geometry.solar_zenith_rad", solar_zenith_rad)
    s.set("optics.aperture_diameter_m", aperture_m)
    s.set("optics.focal_length_m", focal_m)
    s.set("optics.transmission_scalar", TRANSMISSION)
    s.set("detector.pixel_pitch_x_um", PITCH_UM)
    s.set("detector.pixel_pitch_y_um", PITCH_UM)
    s.set("detector.qe_value", qe_band)
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


def diffraction_limited_gsd_m(aperture_m: float, altitude_m: float) -> float:
    """Rayleigh angular resolution projected to the ground [m].

    θ_Rayleigh = 1.22 λ / D  (rad); ground = θ · altitude (nadir). This is
    the smallest resolvable ground detail the optics permit — independent
    of the detector. When it exceeds the 0.5 m sample, the image is
    optics- (diffraction-) limited; when smaller, detector-limited.
    """
    theta = 1.22 * (BAND_CENTER_UM * 1e-6) / aperture_m
    return theta * altitude_m


def main() -> None:
    print("=" * 74)
    print("SCENARIO 1.2 — VNIR PAN IMAGER: GSD vs APERTURE vs ALTITUDE")
    print("=" * 74)
    print(
        f"Fixed: GSD = {GSD_TARGET_M} m, pitch = {PITCH_UM} µm, "
        f"pan band {BAND_MIN_UM*1e3:.0f}–{BAND_MAX_UM*1e3:.0f} nm, "
        f"reflectance = {REFLECTANCE}"
    )
    print(
        f"Orbit: sun-sync, LTAN {LTAN_HR:.1f} hr (10:30 AM), "
        f"target latitude {TARGET_LAT_DEG}°N"
    )
    print(
        "Regime: EXTENDED (sunlit surface fills the pixel; EE_box not applied, "
        "background term is the scene itself)."
    )
    print(
        "Focal length is DERIVED per altitude to hold GSD = 0.5 m, so f/# rises "
        "with altitude — that coupling is the trade."
    )
    print()

    # --- Solar geometry across the four seasons -------------------------
    lst = local_solar_time_from_ltan(LTAN_HR)
    print("-" * 74)
    print("SOLAR ILLUMINATION (new radiant.core.solar_geometry model)")
    print("-" * 74)
    print(f"{'Season':<18}{'day':>5}{'declination':>14}{'solar zenith':>16}{'cos θ_z':>10}")
    season_zenith: dict[str, float] = {}
    for name, doy in SEASONS:
        decl = solar_declination_deg(doy)
        zen = solar_zenith_angle_rad(TARGET_LAT_DEG, doy, lst)
        season_zenith[name] = zen
        print(
            f"{name:<18}{doy:>5}{decl:>12.2f}°{math.degrees(zen):>14.2f}°"
            f"{math.cos(zen):>10.3f}"
        )
    print(
        "cos θ_z scales the top-of-atmosphere solar irradiance onto the surface; "
        "winter (low sun) is the worst-case illumination."
    )
    print()

    # Use the worst-case (largest zenith) season for the sizing contour so
    # the SNR map is a floor, not an optimistic best case.
    worst_season = max(season_zenith, key=lambda k: season_zenith[k])
    worst_zen = season_zenith[worst_season]
    print(
        f"Sizing contour uses worst-case season: {worst_season} "
        f"(θ_z = {math.degrees(worst_zen):.1f}°) — SNR floor across the year."
    )
    print()

    # --- Aperture × altitude SNR contour at fixed GSD -------------------
    print("-" * 74)
    print("APERTURE × ALTITUDE SNR (GSD held at 0.5 m; worst-case season)")
    print("-" * 74)
    snr_grid = np.zeros((len(ALTITUDES_M), len(APERTURES_M)))
    q_grid = np.zeros_like(snr_grid)
    well_grid = np.zeros_like(snr_grid)
    diff_gsd_grid = np.zeros_like(snr_grid)
    for i, alt in enumerate(ALTITUDES_M):
        for j, ap in enumerate(APERTURES_M):
            s = build_sensor(ap, alt, worst_zen)
            r = s.evaluate()
            snr_grid[i, j] = r.metrics["snr"]
            q_grid[i, j] = r.metrics.get("q_center", float("nan"))
            well_grid[i, j] = (
                r.stage_outputs["readout"]["signal_e_final"] / FULL_WELL_E * 100.0
            )
            diff_gsd_grid[i, j] = diffraction_limited_gsd_m(ap, alt)

    # Console summary at the corners + reference point
    def cell(ap: float, alt: float) -> tuple[float, float, float]:
        s = build_sensor(ap, alt, worst_zen)
        r = s.evaluate()
        return (
            r.metrics["snr"],
            r.metrics.get("q_center", float("nan")),
            build_sensor(ap, alt, worst_zen).get("optics.focal_length_m")
            / ap,  # f/#
        )

    print(f"{'aperture':>10}{'altitude':>11}{'f/#':>8}{'SNR':>9}{'Q':>8}{'diff-GSD':>11}")
    for ap in (APERTURES_M[0], REF_APERTURE_M, APERTURES_M[-1]):
        for alt in (ALTITUDES_M[0], REF_ALT_M, ALTITUDES_M[-1]):
            snr, q, fno = cell(ap, alt)
            dgsd = diffraction_limited_gsd_m(ap, alt)
            print(
                f"{ap*100:>8.0f}cm{alt/1e3:>9.0f}km{fno:>8.1f}"
                f"{snr:>9.1f}{q:>8.2f}{dgsd:>9.2f}m"
            )
    print(
        f"\nSPEC: SNR ≥ {SNR_SPEC:.0f}. Q = λ·(f/#)/pitch: Q<1 undersampled "
        "(detector/aliasing-limited), Q≳2 oversampled (diffraction-limited);"
    )
    print(
        "  diff-GSD > 0.5 m means the optics blur past the sample → "
        "diffraction-limited image quality despite the 0.5 m pixel."
    )

    # --- Per-season SNR at the reference design -------------------------
    print()
    print("-" * 74)
    print(
        f"SEASONAL SNR at reference design "
        f"(D = {REF_APERTURE_M*100:.0f} cm, alt = {REF_ALT_M/1e3:.0f} km)"
    )
    print("-" * 74)
    season_snr: dict[str, float] = {}
    for name, _doy in SEASONS:
        r = build_sensor(REF_APERTURE_M, REF_ALT_M, season_zenith[name]).evaluate()
        season_snr[name] = r.metrics["snr"]
        flag = "PASS" if r.metrics["snr"] >= SNR_SPEC else "FAIL"
        print(
            f"{name:<18} θ_z = {math.degrees(season_zenith[name]):>5.1f}°  "
            f"SNR = {r.metrics['snr']:>6.1f}  [{flag}]"
        )
    swing = (max(season_snr.values()) - min(season_snr.values())) / max(season_snr.values())
    print(f"\nSeasonal SNR swing: {swing*100:.0f}% (summer high → winter low).")

    # ---------------------------------------------------------------
    # FIGURE 1 — SNR contour over aperture × altitude, with the
    # diffraction-limit and SNR-spec constraint lines overlaid.
    # ---------------------------------------------------------------
    fig, ax = plt.subplots(figsize=(9, 6.5))
    AP_CM = APERTURES_M * 100
    ALT_KM = ALTITUDES_M / 1e3
    cf = ax.contourf(AP_CM, ALT_KM, snr_grid, levels=14, cmap="viridis")
    cbar = fig.colorbar(cf, ax=ax)
    cbar.set_label("SNR (dimensionless)")
    # SNR spec contour
    cs_spec = ax.contour(
        AP_CM, ALT_KM, snr_grid, levels=[SNR_SPEC], colors="white", linewidths=2.5
    )
    ax.clabel(cs_spec, fmt=f"SNR = {SNR_SPEC:.0f} (spec)", fontsize=9)
    # Diffraction-limit line: where diff-GSD == 0.5 m (optics just meet GSD)
    cs_diff = ax.contour(
        AP_CM,
        ALT_KM,
        diff_gsd_grid,
        levels=[GSD_TARGET_M],
        colors="red",
        linewidths=2.0,
        linestyles="--",
    )
    ax.clabel(cs_diff, fmt="diffraction limit = 0.5 m", fontsize=9)
    ax.set_xlabel("Aperture diameter (cm)")
    ax.set_ylabel("Orbit altitude (km)")
    ax.set_title(
        "Scenario 1.2 — VNIR pan SNR at fixed 0.5 m GSD\n"
        f"(worst-case season: {worst_season}, θ_z = {math.degrees(worst_zen):.0f}°)"
    )
    ax.text(
        0.02,
        0.02,
        "Left of red dashed line: diffraction blur > 0.5 m (optics-limited).\n"
        "Right of white line: meets SNR spec.",
        transform=ax.transAxes,
        fontsize=8,
        va="bottom",
        bbox=dict(boxstyle="round", fc="white", alpha=0.8),
    )
    fig.tight_layout()
    fig1 = OUTPUTS / "fig1_snr_aperture_altitude.png"
    fig.savefig(fig1, dpi=130)
    plt.close(fig)
    print(f"\nWrote {fig1.name}")

    # ---------------------------------------------------------------
    # FIGURE 2 — seasonal SNR bars at the reference design.
    # ---------------------------------------------------------------
    fig, ax = plt.subplots(figsize=(8, 5))
    names = [n for n, _ in SEASONS]
    vals = [season_snr[n] for n in names]
    zeniths = [math.degrees(season_zenith[n]) for n in names]
    colors = ["#2E75B6" if v >= SNR_SPEC else "#C00000" for v in vals]
    bars = ax.bar(names, vals, color=colors)
    ax.axhline(SNR_SPEC, color="black", ls="--", lw=1.5, label=f"SNR spec = {SNR_SPEC:.0f}")
    for b, v, z in zip(bars, vals, zeniths):
        ax.text(
            b.get_x() + b.get_width() / 2,
            v + 1,
            f"{v:.0f}\nθ_z={z:.0f}°",
            ha="center",
            va="bottom",
            fontsize=8,
        )
    ax.set_ylabel("SNR (dimensionless)")
    ax.set_title(
        f"Scenario 1.2 — seasonal SNR at reference design "
        f"(D={REF_APERTURE_M*100:.0f} cm, {REF_ALT_M/1e3:.0f} km)"
    )
    ax.legend()
    fig.tight_layout()
    fig2 = OUTPUTS / "fig2_seasonal_snr.png"
    fig.savefig(fig2, dpi=130)
    plt.close(fig)
    print(f"Wrote {fig2.name}")

    # --- Minimum aperture meeting spec at each altitude -----------------
    print()
    print("-" * 74)
    print("MINIMUM APERTURE MEETING SNR SPEC (worst-case season)")
    print("-" * 74)
    for i, alt in enumerate(ALTITUDES_M):
        row = snr_grid[i, :]
        ok = np.where(row >= SNR_SPEC)[0]
        if ok.size:
            min_ap = APERTURES_M[ok[0]] * 100
            print(f"  altitude {alt/1e3:>4.0f} km → min aperture {min_ap:>4.0f} cm")
        else:
            print(f"  altitude {alt/1e3:>4.0f} km → no aperture in range meets spec")
    print()
    print("=" * 74)
    print("DONE — see outputs/ for figures and MANIFEST.md.")
    print("=" * 74)


if __name__ == "__main__":
    main()
