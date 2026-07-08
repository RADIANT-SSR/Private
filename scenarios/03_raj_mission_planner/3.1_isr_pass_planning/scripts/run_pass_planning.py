#!/usr/bin/env python3
"""Scenario 3.1 — orbit → geometry, pass planning and off-nadir access.

Raj plans collections from a 600 km sun-synchronous orbit. He needs:
  1. Orbit kinematics — period, ground-track speed, passes/day — from the
     new radiant.core.orbit model.
  2. How far off-nadir he can point before image quality (GSD, NIIRS)
     drops below spec, and how wide that makes his cross-track access
     corridor.
  3. His area-coverage rate — nadir swath × ground-track speed — which
     needs the ground speed the chain cannot itself compute (the gap the
     orbit model fills; performance.access_rate takes it as an input).

Every printed number carries units. Regime, unused parameters, and the
non-obvious physics are explained inline (house rules).

Run from the repo root:
    python scenarios/03_raj_mission_planner/3.1_isr_pass_planning/scripts/run_pass_planning.py
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
from radiant.core.orbit import (
    ground_track_speed_m_s,
    orbital_period_s,
    orbital_velocity_m_s,
)
from radiant.performance.access_rate import compute_access_rate_m2_s

warnings.filterwarnings("ignore")  # scenario-level noise suppression; physics still raises

HERE = Path(__file__).resolve().parent
SCEN = HERE.parent
OUTPUTS = SCEN / "outputs"
OUTPUTS.mkdir(exist_ok=True)

# --- Mission config (from raj_orbit_sensor.xlsx; transcribed for a
#     self-contained, reproducible run) ---------------------------------
ALT_M = 600e3
MAX_SLEW_DEG = 45.0
NIIRS_FLOOR = 6.0
APERTURE_M = 0.50
FOCAL_M = 6.0
PITCH_UM = 6.5
N_PIX_CROSS = 8000
TRANSMISSION = 0.85
QE = 0.85
BAND_MIN_UM, BAND_MAX_UM = 0.45, 0.70
T_INT_S = 0.5e-3
DARK_E_PER_S = 50.0
TEMP_K = 280.0
READ_NOISE_E = 20.0
FULL_WELL_E = 30000.0
GAIN_E_PER_DN = 8.0
ADC_BITS = 12
REFLECTANCE = 0.30
SOLAR_ZENITH_DEG = 35.0


def build_sensor(off_nadir_deg: float) -> Sensor:
    """VNIR pan config pointed *off_nadir_deg* from nadir (path zenith)."""
    s = Sensor()
    s.set("source.scene_type", "extended")
    s.set("source.target.reflectance", REFLECTANCE)
    s.set("atmosphere.model", "simple")
    s.set("atmosphere.standard_atmosphere", "us_standard")
    s.set("geometry.sensor_altitude_m", ALT_M)
    s.set("geometry.path_zenith_rad", math.radians(off_nadir_deg))
    s.set("geometry.solar_zenith_rad", math.radians(SOLAR_ZENITH_DEG))
    s.set("optics.aperture_diameter_m", APERTURE_M)
    s.set("optics.focal_length_m", FOCAL_M)
    s.set("optics.transmission_scalar", TRANSMISSION)
    s.set("detector.pixel_pitch_x_um", PITCH_UM)
    s.set("detector.pixel_pitch_y_um", PITCH_UM)
    s.set("detector.qe_value", QE)
    s.set("detector.dark_rate_e_per_s", DARK_E_PER_S)
    s.set("detector.detector_temperature_K", TEMP_K)
    s.set("detector.n_pixels_cross", N_PIX_CROSS)
    s.set("spectral_integration.filter_min_um", BAND_MIN_UM)
    s.set("spectral_integration.filter_max_um", BAND_MAX_UM)
    s.set("spectral_integration.integration_time_s", T_INT_S)
    s.set("readout.read_noise_e_rms", READ_NOISE_E)
    s.set("readout.gain_e_per_dn", GAIN_E_PER_DN)
    s.set("readout.adc_bits", ADC_BITS)
    s.set("readout.full_well_capacity_e", FULL_WELL_E)
    return s


def main() -> None:
    print("=" * 74)
    print("SCENARIO 3.1 — ORBIT GEOMETRY & PASS PLANNING")
    print("=" * 74)
    print(
        f"Orbit: circular sun-sync, altitude {ALT_M/1e3:.0f} km. "
        f"Sensor: {APERTURE_M*100:.0f} cm aperture, f = {FOCAL_M} m, "
        f"{PITCH_UM} µm pixels, {N_PIX_CROSS} cross-track."
    )
    print(
        "Regime: EXTENDED (sunlit surface fills the pixel). Off-nadir pointing "
        "is set via geometry.path_zenith_rad; GSD, ground range, and swath are "
        "the chain's off-nadir-corrected metrics."
    )
    print()

    # --- 1. Orbit kinematics (new radiant.core.orbit model) ------------
    period_s = orbital_period_s(ALT_M)
    v_orb = orbital_velocity_m_s(ALT_M)
    v_ground = ground_track_speed_m_s(ALT_M)
    passes_per_day = 86400.0 / period_s
    print("-" * 74)
    print("ORBIT KINEMATICS (radiant.core.orbit)")
    print("-" * 74)
    print(f"  Orbital period          {period_s:8.1f} s   ({period_s/60:.1f} min)")
    print(f"  Orbital velocity        {v_orb:8.1f} m/s ({v_orb/1e3:.2f} km/s, inertial)")
    print(f"  Ground-track speed      {v_ground:8.1f} m/s ({v_ground/1e3:.2f} km/s, sub-satellite)")
    print(f"  Orbits per day          {passes_per_day:8.1f}   (86400 s / period)")
    print(
        "  Ground speed < orbital speed because the nadir point traces a smaller "
        "circle (× R_E/a). Earth rotation neglected."
    )
    print()

    # --- 2. Off-nadir image-quality degradation ------------------------
    print("-" * 74)
    print("OFF-NADIR IMAGE QUALITY (pointing to reach off-track targets)")
    print("-" * 74)
    angles = np.linspace(0.0, MAX_SLEW_DEG, 16)
    gsd_m = np.zeros_like(angles)
    niirs = np.zeros_like(angles)
    snr = np.zeros_like(angles)
    ground_range_km = np.zeros_like(angles)
    swath_km = np.zeros_like(angles)
    for i, ang in enumerate(angles):
        r = build_sensor(ang).evaluate()
        gsd_m[i] = r.metrics["gsd_geometric_mean_m"]
        niirs[i] = r.metrics["niirs"]
        snr[i] = r.metrics["snr"]
        ground_range_km[i] = r.metrics["ground_range_m"] / 1e3
        swath_km[i] = r.metrics["swath_width_m"] / 1e3

    print(f"{'off-nadir':>10}{'GSD':>10}{'NIIRS':>8}{'SNR':>8}{'gnd range':>12}{'swath':>10}")
    for i in (0, 5, 10, 15):
        print(
            f"{angles[i]:>8.0f}°{gsd_m[i]:>9.2f}m{niirs[i]:>8.2f}{snr[i]:>8.1f}"
            f"{ground_range_km[i]:>10.0f}km{swath_km[i]:>8.1f}km"
        )

    # Largest off-nadir angle that still meets the NIIRS floor.
    meets = np.where(niirs >= NIIRS_FLOOR)[0]
    max_slew_for_niirs = angles[meets[-1]] if meets.size else float("nan")
    print(
        f"\nNIIRS floor = {NIIRS_FLOOR:.1f}. Largest off-nadir angle meeting it: "
        f"{max_slew_for_niirs:.0f}° "
        f"(GSD grows ∝ 1/cos²(off-nadir) roughly, dragging NIIRS down; SNR rises "
        "slightly as the ground footprint per pixel grows)."
    )

    # --- 3. Access corridor & coverage rate ----------------------------
    # At the slew limit the ground range from the sub-satellite point is the
    # half-width of the cross-track access corridor (targets within ± that
    # arc distance are reachable on a single pass).
    r_slew = build_sensor(MAX_SLEW_DEG).evaluate()
    r_niirs_limit = build_sensor(max_slew_for_niirs).evaluate()
    access_half_agility_km = r_slew.metrics["ground_range_m"] / 1e3
    access_half_niirs_km = r_niirs_limit.metrics["ground_range_m"] / 1e3

    # Nadir coverage rate = nadir swath × ground-track speed (the orbit model
    # supplies the ground speed that performance.access_rate needs).
    swath_nadir_m = build_sensor(0.0).evaluate().metrics["swath_width_m"]
    access_rate_m2_s = compute_access_rate_m2_s(swath_nadir_m, v_ground)
    access_rate_km2_s = access_rate_m2_s / 1e6

    print()
    print("-" * 74)
    print("ACCESS CORRIDOR & AREA COVERAGE RATE")
    print("-" * 74)
    print(
        f"  Cross-track access half-width (agility {MAX_SLEW_DEG:.0f}°): "
        f"{access_half_agility_km:6.0f} km"
    )
    print(
        f"  Cross-track access half-width (NIIRS≥{NIIRS_FLOOR:.0f}, "
        f"{max_slew_for_niirs:.0f}°):  {access_half_niirs_km:6.0f} km"
    )
    print(
        f"  Nadir swath width                     {swath_nadir_m/1e3:6.1f} km "
        f"({N_PIX_CROSS} px × {swath_nadir_m/N_PIX_CROSS:.2f} m GSD)"
    )
    print(
        f"  Nadir area coverage rate              {access_rate_km2_s:6.1f} km²/s "
        f"(swath × ground speed = {swath_nadir_m/1e3:.1f} km × {v_ground/1e3:.2f} km/s)"
    )
    print(
        f"  Per-pass daylight coverage (~{period_s/60/2:.0f} min lit)  "
        f"≈ {access_rate_km2_s * (period_s/2):,.0f} km²"
    )
    print(
        "\n  The agility limit (45°) reaches wider than the NIIRS-quality limit — "
        "Raj can SEE targets he cannot image at spec quality; the usable corridor "
        "is set by NIIRS, not by spacecraft agility."
    )

    # ---------------------------------------------------------------
    # FIGURE 1 — GSD and NIIRS vs off-nadir angle (dual axis).
    # ---------------------------------------------------------------
    fig, ax1 = plt.subplots(figsize=(9, 6))
    ax1.plot(angles, gsd_m, "o-", color="#C55A11", label="GSD")
    ax1.set_xlabel("Off-nadir pointing angle (deg)")
    ax1.set_ylabel("GSD (m)", color="#C55A11")
    ax1.tick_params(axis="y", labelcolor="#C55A11")
    ax2 = ax1.twinx()
    ax2.plot(angles, niirs, "s-", color="#2E75B6", label="NIIRS")
    ax2.axhline(NIIRS_FLOOR, color="black", ls="--", lw=1.5)
    ax2.set_ylabel("NIIRS", color="#2E75B6")
    ax2.tick_params(axis="y", labelcolor="#2E75B6")
    if not math.isnan(max_slew_for_niirs):
        ax1.axvline(max_slew_for_niirs, color="green", ls=":", lw=2)
        ax1.text(
            max_slew_for_niirs - 1,
            ax1.get_ylim()[1] * 0.9,
            f"NIIRS floor at {max_slew_for_niirs:.0f}°",
            ha="right",
            color="green",
            fontsize=9,
        )
    ax2.text(
        angles[-1],
        NIIRS_FLOOR + 0.03,
        f"NIIRS floor = {NIIRS_FLOOR:.0f}",
        ha="right",
        va="bottom",
        fontsize=8,
    )
    ax1.set_title(
        f"Scenario 3.1 — off-nadir image quality "
        f"({ALT_M/1e3:.0f} km, {APERTURE_M*100:.0f} cm aperture)"
    )
    fig.tight_layout()
    fig1 = OUTPUTS / "fig1_offnadir_image_quality.png"
    fig.savefig(fig1, dpi=130)
    plt.close(fig)
    print(f"\nWrote {fig1.name}")

    # ---------------------------------------------------------------
    # FIGURE 2 — access corridor: ground range vs off-nadir angle.
    # ---------------------------------------------------------------
    fig, ax = plt.subplots(figsize=(9, 5.5))
    ax.plot(angles, ground_range_km, "o-", color="#548235")
    ax.set_xlabel("Off-nadir pointing angle (deg)")
    ax.set_ylabel("Ground range from nadir (km)")
    ax.axvline(MAX_SLEW_DEG, color="red", ls="--", lw=1.5, label=f"agility limit {MAX_SLEW_DEG:.0f}°")
    if not math.isnan(max_slew_for_niirs):
        ax.axvline(
            max_slew_for_niirs, color="green", ls=":", lw=2,
            label=f"NIIRS≥{NIIRS_FLOOR:.0f} limit {max_slew_for_niirs:.0f}°",
        )
    ax.set_title("Scenario 3.1 — cross-track access corridor half-width")
    ax.legend()
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig2 = OUTPUTS / "fig2_access_corridor.png"
    fig.savefig(fig2, dpi=130)
    plt.close(fig)
    print(f"Wrote {fig2.name}")

    print()
    print("=" * 74)
    print("DONE — see outputs/ for figures and MANIFEST.md.")
    print("=" * 74)


if __name__ == "__main__":
    main()
