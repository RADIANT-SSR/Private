"""Scenario 8.1: Off-Nadir Angle Interpolation.

A customer requirement lands at 37.5 deg off-nadir -- not one of the
run matrix's zenith-fan points (A1=0, B1=30, B2=45, B3=60 deg, all
us_standard/100km-sensor/nadir-target). Demonstrates
scripts/synth_modtran/family_interpolate.py: log-transmittance-linear
interpolation between the two bracketing runs, quantified against the
naive "just use the nearest neighbor" alternative.

*** SYNTHETIC DATA, NOT REAL MODTRAN *** -- see modtran/synthetic/README.md.
This scenario demonstrates the INTERPOLATION METHOD (which is
independent of whether the underlying data is real or synthetic); the
absolute transmittance/SNR numbers are illustrative, not validated.

Usage:
    python run_off_nadir_interpolation.py
"""

from __future__ import annotations

import csv
import math
import tempfile
import warnings
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from radiant.api import Sensor

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))
from scripts.synth_modtran.family_interpolate import interpolate_family

OUTPUT_DIR = Path(__file__).parent.parent / "outputs"
FAMILY = "zenith_fan_us_standard"
QUERY_ZENITH_DEG = 37.5  # customer requirement, between B1=30 and B2=45
BAND_MIN_UM, BAND_MAX_UM = 3.5, 5.0


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


def _run_chain(trans_csv: str, radiance_csv: str, zenith_deg: float) -> dict:
    config = {
        "source": {
            "scene_type": "extended",
            "target": {"temperature": 300.0, "emissivity": 0.95},
            "background": {"temperature": 288.0, "emissivity": 0.95},
        },
        "geometry": {"sensor_altitude_m": 100_000.0, "path_zenith_rad": math.radians(zenith_deg)},
        "optics": {
            "aperture_diameter_m": 0.30,
            "focal_length_m": 0.75,
            "transmission_scalar": 0.85,
        },
        "detector": {
            "pixel_pitch_x_um": 20.0,
            "pixel_pitch_y_um": 20.0,
            "qe_value": 0.70,
            "dark_rate_e_per_s": 1.0e4,
            "detector_temperature_K": 120.0,
        },
        "spectral_integration": {
            "filter_min_um": BAND_MIN_UM,
            "filter_max_um": BAND_MAX_UM,
            "integration_time_s": 5.0e-4,
        },
        "readout": {
            "read_noise_e_rms": 20.0,
            "gain_e_per_dn": 16.0,
            "adc_bits": 14,
            "full_well_capacity_e": 2.0e6,
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
    print("=== Scenario 8.1: Off-Nadir Angle Interpolation ===")
    print(
        f"  Family: {FAMILY} (0/30/45/60 deg zenith fan, us_standard, 100km sensor, nadir target)"
    )
    print(f"  Query: {QUERY_ZENITH_DEG} deg off-nadir (customer requirement, not a matrix point)\n")

    wl_interp, trans_interp, lp_interp = interpolate_family(FAMILY, QUERY_ZENITH_DEG)
    wl_30, trans_30, lp_30 = interpolate_family(FAMILY, 30.0)
    wl_45, trans_45, lp_45 = interpolate_family(FAMILY, 45.0)

    band_mask = (wl_interp >= BAND_MIN_UM) & (wl_interp <= BAND_MAX_UM)
    tau_interp_inband = float(np.mean(trans_interp[band_mask]))
    tau_30_inband = float(np.mean(trans_30[band_mask]))
    tau_45_inband = float(np.mean(trans_45[band_mask]))

    # "Naive nearest neighbor" -- what an operator who just grabs the
    # closest matrix point (without interpolating) would have used.
    nearest_deg = 30.0 if abs(QUERY_ZENITH_DEG - 30.0) < abs(QUERY_ZENITH_DEG - 45.0) else 45.0
    tau_nearest_inband = tau_30_inband if nearest_deg == 30.0 else tau_45_inband

    print("=== In-band transmittance (3.5-5.0 um) ===")
    print(f"  30 deg (B1, exact matrix point):        {tau_30_inband:.4f}")
    print(f"  45 deg (B2, exact matrix point):         {tau_45_inband:.4f}")
    print(f"  37.5 deg, interpolated:                  {tau_interp_inband:.4f}")
    print(f"  37.5 deg, naive nearest-neighbor ({nearest_deg:.0f} deg): {tau_nearest_inband:.4f}")
    nn_error_pct = 100.0 * (tau_nearest_inband - tau_interp_inband) / tau_interp_inband
    print(f"  Nearest-neighbor error vs. interpolated: {nn_error_pct:+.1f}%")

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        trans_csv_i, lp_csv_i = _write_csvs(wl_interp, trans_interp, lp_interp, tmp_path, "interp")
        trans_csv_n, lp_csv_n = _write_csvs(
            wl_30 if nearest_deg == 30.0 else wl_45,
            trans_30 if nearest_deg == 30.0 else trans_45,
            lp_30 if nearest_deg == 30.0 else lp_45,
            tmp_path,
            "nearest",
        )

        r_interp = _run_chain(trans_csv_i, lp_csv_i, QUERY_ZENITH_DEG)
        r_nearest = _run_chain(trans_csv_n, lp_csv_n, QUERY_ZENITH_DEG)

    print("\n=== Full-chain SNR at the query geometry (37.5 deg) ===")
    print(f"  Using interpolated atmosphere:        SNR = {r_interp['snr']:.2f}")
    print(f"  Using naive nearest-neighbor atmosphere: SNR = {r_nearest['snr']:.2f}")
    snr_error_pct = 100.0 * (r_nearest["snr"] - r_interp["snr"]) / r_interp["snr"]
    print(f"  Nearest-neighbor SNR error vs. interpolated: {snr_error_pct:+.1f}%")
    print(
        "\n  Note: the chain is run at the SAME query geometry (37.5 deg path_zenith_rad) in both"
    )
    print("  cases -- only the ATMOSPHERE data source differs (interpolated vs. the nearest matrix")
    print(
        "  point's atmosphere data reused as-is). This isolates the interpolation method's value."
    )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(8, 5))
    taus = []
    for z in [0.0, 30.0, 45.0, 60.0]:
        _, t, _ = interpolate_family(FAMILY, z)
        taus.append(float(np.mean(t[band_mask])))
    ax.plot(
        [0.0, 30.0, 45.0, 60.0],
        taus,
        "o-",
        color="C0",
        label="Matrix points (exact)",
    )
    ax.plot(
        [QUERY_ZENITH_DEG],
        [tau_interp_inband],
        "s",
        color="C1",
        markersize=10,
        label="Interpolated query (37.5 deg)",
    )
    ax.plot(
        [QUERY_ZENITH_DEG],
        [tau_nearest_inband],
        "^",
        color="C3",
        markersize=10,
        label="Naive nearest-neighbor",
    )
    ax.set_xlabel("Off-nadir angle [deg]")
    ax.set_ylabel("In-band mean transmittance [-]")
    ax.set_title("Scenario 8.1: interpolated vs. nearest-neighbor atmosphere at 37.5 deg")
    ax.legend()
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig1_path = OUTPUT_DIR / "fig1_interpolation_vs_nearest_neighbor.png"
    fig.savefig(fig1_path, dpi=130)
    plt.close(fig)
    print(f"\nWrote {fig1_path}")


if __name__ == "__main__":
    main()
