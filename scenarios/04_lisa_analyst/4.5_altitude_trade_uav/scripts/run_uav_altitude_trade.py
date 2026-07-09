#!/usr/bin/env python3
"""Scenario 4.5 — uncooled microbolometer UAV altitude trade (NETD-specified).

Lisa's UAV carries an uncooled microbolometer specified the way vendors
quote it — by NETD, not by component noise. She asks: how high can the UAV
fly and still detect a small warm ground target?

Two things degrade the target as the UAV climbs:
  1. Sub-pixel dilution — a fixed-size target fills less of the growing
     ground pixel (GSD ∝ altitude), so its apparent contrast is
     ff·ΔT with ff = (target / GSD)² once the target is sub-pixel.
  2. Atmospheric attenuation — the longer path transmits less of the
     thermal contrast (τ_atm from the chain).

Detection holds while the apparent contrast ff·ΔT·τ_atm stays above the
detection floor threshold·NETD. The **NETD-specified** detector is turned
into optical-power figures (NEP, D*) via the new D*/NEP/NETD converters.

Every printed number carries units; the model and the physics of the
ceiling are explained inline (house rules).

Run from the repo root:
    python scenarios/04_lisa_analyst/4.5_altitude_trade_uav/scripts/run_uav_altitude_trade.py
"""

from __future__ import annotations

import warnings
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from radiant.api import Sensor
from radiant.core.constants import hc
from radiant.performance.detectivity import dstar_from_nep
from radiant.performance.nep_electrons import integrating_bandwidth_hz
from radiant.performance.nep_netd import nep_from_netd

warnings.filterwarnings("ignore")  # scenario-level noise suppression; physics still raises

HERE = Path(__file__).resolve().parent
SCEN = HERE.parent
OUTPUTS = SCEN / "outputs"
OUTPUTS.mkdir(exist_ok=True)

# --- Microbolometer + UAV + target (lisa_microbolometer_uav.xlsx) -----
NETD_MK = 50.0
NETD_K = NETD_MK * 1e-3
BAND = (8.0, 14.0)
PITCH_UM = 17.0
QE = 0.70
T_INT_S = 16e-3
APERTURE_M = 0.035
FOCAL_M = 0.035  # f/1
TRANSMISSION = 0.90
TARGET_SIZE_M = 1.0
TARGET_DT_K = 4.0
BG_TEMP_K = 295.0
THRESHOLD = 4.0  # apparent ΔT ≥ THRESHOLD · NETD
ALT_MIN_KM, ALT_MAX_KM = 1.0, 12.0

LAMBDA_C_UM = 0.5 * (BAND[0] + BAND[1])
IFOV_RAD = (PITCH_UM * 1e-6) / FOCAL_M
AREA_CM2 = (PITCH_UM * 1e-4) ** 2
DELTA_F_HZ = integrating_bandwidth_hz(T_INT_S)
DETECT_FLOOR_K = THRESHOLD * NETD_K


def build_sensor(altitude_m: float) -> Sensor:
    """Microbolometer UAV looking down from *altitude_m*."""
    s = Sensor()
    s.set("source.scene_type", "extended")
    s.set("source.target.temperature", BG_TEMP_K + TARGET_DT_K, unit="K")
    s.set("source.target.emissivity", 0.95)
    s.set("atmosphere.model", "simple")
    s.set("atmosphere.standard_atmosphere", "us_standard")
    s.set("geometry.sensor_altitude_m", altitude_m)
    s.set("geometry.path_zenith_rad", 0.0)
    s.set("optics.aperture_diameter_m", APERTURE_M)
    s.set("optics.focal_length_m", FOCAL_M)
    s.set("optics.transmission_scalar", TRANSMISSION)
    s.set("detector.pixel_pitch_x_um", PITCH_UM)
    s.set("detector.pixel_pitch_y_um", PITCH_UM)
    s.set("detector.qe_value", QE)
    s.set("detector.dark_rate_e_per_s", 1e6)
    s.set("detector.detector_temperature_K", 300.0)
    s.set("spectral_integration.filter_min_um", BAND[0])
    s.set("spectral_integration.filter_max_um", BAND[1])
    s.set("spectral_integration.integration_time_s", T_INT_S)
    s.set("readout.read_noise_e_rms", 500.0)
    s.set("readout.gain_e_per_dn", 1000.0)
    s.set("readout.adc_bits", 14)
    s.set("readout.full_well_capacity_e", 1e7)
    return s


def band_tau(result: object) -> float:
    """Band-averaged atmospheric transmission from the chain."""
    ta = result.stage_outputs["atmosphere"]["tau_atm"]  # type: ignore[attr-defined]
    return float(np.mean(ta))


def main() -> None:
    print("=" * 74)
    print("SCENARIO 4.5 — MICROBOLOMETER UAV ALTITUDE TRADE (NETD-SPECIFIED)")
    print("=" * 74)
    print(
        f"Uncooled microbolometer: NETD {NETD_MK:.0f} mK, {PITCH_UM:.0f} µm pixel, "
        f"{BAND[0]:.0f}–{BAND[1]:.0f} µm, f/{FOCAL_M/APERTURE_M:.0f}, "
        f"IFOV {IFOV_RAD*1e6:.0f} µrad."
    )
    print(
        f"Target: {TARGET_SIZE_M:.0f} m, ΔT {TARGET_DT_K:.0f} K over {BG_TEMP_K:.0f} K "
        f"background. Detection floor = {THRESHOLD:.0f}·NETD = {DETECT_FLOOR_K*1e3:.0f} mK."
    )
    print()

    # --- NETD-specified detector → NEP → D* (converters) ---------------
    # dP/dT from the chain's dS/dT: dS/dT [e-/K] = dP/dT · QE·λ/(hc)·t_int.
    ref = build_sensor(2000.0).evaluate()
    ds_dt = ref.stage_outputs["spectral_integration"]["ds_dt_e_per_K"]
    lam_m = LAMBDA_C_UM * 1e-6
    dp_dt = ds_dt * hc / (QE * lam_m * T_INT_S)  # W/K
    nep = nep_from_netd(NETD_K, dp_dt)
    dstar = dstar_from_nep(nep, AREA_CM2, DELTA_F_HZ)
    print("-" * 74)
    print("VENDOR NETD → NEP → D* (converter chain)")
    print("-" * 74)
    print(f"  dP/dT (from chain dS/dT)  = {dp_dt:.3e} W/K")
    print(f"  NEP = NETD · dP/dT        = {nep:.3e} W")
    print(f"  D*  = √(A·Δf)/NEP         = {dstar:.3e} Jones")
    print(
        f"  (Uncooled microbolometer D* ~1e9 Jones — ~100× below a cooled photon\n"
        f"   detector; the NETD spec is the practical way to carry that.)"
    )
    print()

    # --- Altitude trade ------------------------------------------------
    print("-" * 74)
    print("ALTITUDE TRADE — apparent target contrast vs the NETD floor")
    print("-" * 74)
    altitudes_km = np.linspace(ALT_MIN_KM, ALT_MAX_KM, 23)
    gsd_m = np.zeros_like(altitudes_km)
    fill_frac = np.zeros_like(altitudes_km)
    tau = np.zeros_like(altitudes_km)
    apparent_dt = np.zeros_like(altitudes_km)
    for i, alt_km in enumerate(altitudes_km):
        alt_m = alt_km * 1e3
        gsd = IFOV_RAD * alt_m
        ff = min(1.0, (TARGET_SIZE_M / gsd) ** 2)
        t = band_tau(build_sensor(alt_m).evaluate())
        gsd_m[i], fill_frac[i], tau[i] = gsd, ff, t
        apparent_dt[i] = ff * TARGET_DT_K * t

    print(f"{'alt':>7}{'GSD':>9}{'fill frac':>11}{'τ_atm':>8}{'apparent ΔT':>14}{'detect?':>9}")
    for i in range(0, len(altitudes_km), 4):
        det = "YES" if apparent_dt[i] >= DETECT_FLOOR_K else "no"
        print(
            f"{altitudes_km[i]:>5.0f}km{gsd_m[i]:>8.2f}m{fill_frac[i]:>11.3f}"
            f"{tau[i]:>8.3f}{apparent_dt[i]*1e3:>11.0f}mK{det:>9}"
        )

    # Detection ceiling: highest altitude with apparent ΔT ≥ floor.
    detectable = apparent_dt >= DETECT_FLOOR_K
    ceiling_km = altitudes_km[detectable].max() if detectable.any() else float("nan")
    # Altitude where the target goes sub-pixel (GSD = target size).
    subpixel_km = TARGET_SIZE_M / IFOV_RAD / 1e3
    print(
        f"\n  Target goes sub-pixel (GSD = {TARGET_SIZE_M:.0f} m) at "
        f"{subpixel_km:.1f} km; above that apparent contrast falls ∝ 1/altitude²."
    )
    print(
        f"  DETECTION CEILING: {ceiling_km:.1f} km — the highest altitude where "
        f"apparent ΔT ≥ {DETECT_FLOOR_K*1e3:.0f} mK. Above it the target dilutes "
        "below the microbolometer's NETD floor."
    )
    print(
        "  The ceiling is set by sub-pixel dilution (∝1/alt²), not atmosphere "
        f"(τ_atm only drops {tau[0]:.2f}→{tau[-1]:.2f} over the sweep)."
    )

    # ---------------------------------------------------------------
    # FIGURE 1 — apparent ΔT vs altitude with the NETD floor + ceiling.
    # ---------------------------------------------------------------
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.semilogy(altitudes_km, apparent_dt * 1e3, "o-", color="#843C0C", label="apparent ΔT")
    ax.axhline(
        DETECT_FLOOR_K * 1e3, color="black", ls="--", lw=1.5,
        label=f"detection floor = {THRESHOLD:.0f}·NETD = {DETECT_FLOOR_K*1e3:.0f} mK",
    )
    ax.axhline(NETD_MK, color="gray", ls=":", lw=1, label=f"NETD = {NETD_MK:.0f} mK")
    if not np.isnan(ceiling_km):
        ax.axvline(ceiling_km, color="green", ls="-", lw=1.5, label=f"ceiling {ceiling_km:.1f} km")
    ax.axvline(subpixel_km, color="blue", ls=":", lw=1, label=f"sub-pixel at {subpixel_km:.1f} km")
    ax.set_xlabel("UAV altitude (km)")
    ax.set_ylabel("Apparent target ΔT (mK)")
    ax.set_title(
        "Scenario 4.5 — microbolometer UAV: apparent contrast vs altitude\n"
        f"(NETD {NETD_MK:.0f} mK, {TARGET_SIZE_M:.0f} m target, ΔT {TARGET_DT_K:.0f} K)"
    )
    ax.legend(fontsize=8)
    ax.grid(alpha=0.3, which="both")
    fig.tight_layout()
    fig1 = OUTPUTS / "fig1_altitude_trade.png"
    fig.savefig(fig1, dpi=130)
    plt.close(fig)
    print(f"\nWrote {fig1.name}")

    print()
    print("=" * 74)
    print("DONE — see outputs/ for the figure and MANIFEST.md.")
    print("=" * 74)


if __name__ == "__main__":
    main()
