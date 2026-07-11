"""Scenario 8.2: Target-Altitude Interpolation.

A stratospheric-sensor mission wants atmosphere data for a target at
15 km -- not one of the run matrix's altitude-ladder points (C1=0,
C2=1, C3=5, C4=10, C5=20, C6=29 km, all midlat_summer/35km-sensor/
nadir). Demonstrates interpolate_family() bracketing C4/C5, quantified
against the naive nearest-neighbor alternative -- same method as 8.1,
different family (target altitude instead of zenith angle), showing
the tool generalizes across axis types.

*** SYNTHETIC DATA, NOT REAL MODTRAN *** -- see modtran/synthetic/README.md.

Usage:
    python run_target_altitude_interpolation.py
"""

from __future__ import annotations

import csv
import sys
import tempfile
import warnings
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from radiant.api import Sensor

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))
from scripts.synth_modtran.family_interpolate import FAMILIES, interpolate_family

OUTPUT_DIR = Path(__file__).parent.parent / "outputs"
FAMILY = "altitude_ladder_stratospheric"
QUERY_ALTITUDE_KM = 15.0  # between C4=10km and C5=20km
BAND_MIN_UM, BAND_MAX_UM = 8.0, 12.0  # LWIR -- typical stratospheric-sensor band


def _write_csvs(
    wl_um: np.ndarray, trans: np.ndarray, lp: np.ndarray, tmp_dir: Path, tag: str
) -> tuple[str, str]:
    trans_path = tmp_dir / f"{tag}_trans.csv"
    with trans_path.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["wavelength_um", "transmittance"])
        for wl, t in zip(wl_um, trans, strict=True):
            w.writerow([f"{wl:.6f}", f"{t:.6f}"])
    radiance_path = tmp_dir / f"{tag}_lpath.csv"
    with radiance_path.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["wavelength_um", "path_radiance_W_m2_sr_um"])
        for wl, v in zip(wl_um, lp, strict=True):
            w.writerow([f"{wl:.6f}", f"{v:.6e}"])
    return str(trans_path), str(radiance_path)


def _run_chain(trans_csv: str, radiance_csv: str) -> dict:
    config = {
        "source": {
            "scene_type": "extended",
            "target": {"temperature": 250.0, "emissivity": 0.95},
            "background": {"temperature": 220.0, "emissivity": 0.95},
        },
        "geometry": {"sensor_altitude_m": 35_000.0},
        "optics": {
            "aperture_diameter_m": 0.20,
            "focal_length_m": 0.60,
            "transmission_scalar": 0.80,
        },
        "detector": {
            "pixel_pitch_x_um": 25.0,
            "pixel_pitch_y_um": 25.0,
            "qe_value": 0.65,
            "dark_rate_e_per_s": 5.0e3,
            "detector_temperature_K": 77.0,
        },
        "spectral_integration": {
            "filter_min_um": BAND_MIN_UM,
            "filter_max_um": BAND_MAX_UM,
            "integration_time_s": 1.0e-4,
        },
        "readout": {
            "read_noise_e_rms": 25.0,
            "gain_e_per_dn": 16.0,
            "adc_bits": 14,
            "full_well_capacity_e": 3.0e6,
        },
        "atmosphere": {
            "model": "tabulated",
            "tabulated_transmittance_file": trans_csv,
            "tabulated_path_radiance_file": radiance_csv,
        },
    }
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        result = Sensor.from_dict(config).evaluate()
    tau_atm = np.asarray(result.stage_outputs["atmosphere"]["tau_atm"])
    return {"snr": result.metrics["snr"], "tau_inband": float(np.mean(tau_atm))}


def main() -> None:
    print("=== Scenario 8.2: Target-Altitude Interpolation ===")
    print(f"  Family: {FAMILY} (midlat_summer, 35km sensor, nadir target)")
    print(
        f"  Query: {QUERY_ALTITUDE_KM} km target altitude (mission requirement, not a matrix point)\n"
    )

    family = FAMILIES[FAMILY]
    wl_interp, trans_interp, lp_interp = interpolate_family(FAMILY, QUERY_ALTITUDE_KM)

    band_mask = (wl_interp >= BAND_MIN_UM) & (wl_interp <= BAND_MAX_UM)
    tau_interp_inband = float(np.mean(trans_interp[band_mask]))

    print("=== In-band transmittance across the full ladder (8-12 um) ===")
    ladder_taus = {}
    for alt in family.axis_values:
        _, t, _ = interpolate_family(FAMILY, alt)
        ladder_taus[alt] = float(np.mean(t[band_mask]))
        print(f"  {alt:5.1f} km: tau = {ladder_taus[alt]:.4f}")
    print(f"  {QUERY_ALTITUDE_KM:5.1f} km (interpolated): tau = {tau_interp_inband:.4f}")

    lo_alt, hi_alt = 10.0, 20.0  # brackets for 15 km
    nearest_alt = (
        lo_alt if abs(QUERY_ALTITUDE_KM - lo_alt) < abs(QUERY_ALTITUDE_KM - hi_alt) else hi_alt
    )
    tau_nearest_inband = ladder_taus[nearest_alt]
    nn_error_pct = 100.0 * (tau_nearest_inband - tau_interp_inband) / tau_interp_inband
    print(f"\n  Naive nearest-neighbor ({nearest_alt:.0f} km): tau = {tau_nearest_inband:.4f}")
    print(f"  Nearest-neighbor error vs. interpolated: {nn_error_pct:+.1f}%")

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        trans_csv_i, lp_csv_i = _write_csvs(wl_interp, trans_interp, lp_interp, tmp_path, "interp")
        _, trans_nearest, lp_nearest = interpolate_family(FAMILY, nearest_alt)
        trans_csv_n, lp_csv_n = _write_csvs(
            wl_interp, trans_nearest, lp_nearest, tmp_path, "nearest"
        )

        r_interp = _run_chain(trans_csv_i, lp_csv_i)
        r_nearest = _run_chain(trans_csv_n, lp_csv_n)

    print("\n=== Full-chain SNR at the query altitude (15 km) ===")
    print(f"  Using interpolated atmosphere:           SNR = {r_interp['snr']:.2f}")
    print(f"  Using naive nearest-neighbor atmosphere: SNR = {r_nearest['snr']:.2f}")
    snr_error_pct = 100.0 * (r_nearest["snr"] - r_interp["snr"]) / r_interp["snr"]
    print(f"  Nearest-neighbor SNR error vs. interpolated: {snr_error_pct:+.1f}%")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(8, 5))
    alts_sorted = sorted(family.axis_values)
    taus_sorted = [ladder_taus[a] for a in alts_sorted]
    ax.plot(alts_sorted, taus_sorted, "o-", color="C0", label="Matrix points (exact)")
    ax.plot(
        [QUERY_ALTITUDE_KM],
        [tau_interp_inband],
        "s",
        color="C1",
        markersize=10,
        label=f"Interpolated query ({QUERY_ALTITUDE_KM:.0f} km)",
    )
    ax.plot(
        [QUERY_ALTITUDE_KM],
        [tau_nearest_inband],
        "^",
        color="C3",
        markersize=10,
        label="Naive nearest-neighbor",
    )
    ax.set_xlabel("Target altitude [km]")
    ax.set_ylabel("In-band mean transmittance [-]")
    ax.set_title("Scenario 8.2: interpolated vs. nearest-neighbor atmosphere at 15 km")
    ax.legend()
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig1_path = OUTPUT_DIR / "fig1_interpolation_vs_nearest_neighbor.png"
    fig.savefig(fig1_path, dpi=130)
    plt.close(fig)
    print(f"\nWrote {fig1_path}")


if __name__ == "__main__":
    main()
