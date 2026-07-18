"""Scenario 8.1: Off-Nadir Angle Interpolation.

A customer requirement lands at 37.5 deg off-nadir -- not one of the
run matrix's zenith-fan points (A1=0, B1=30, B2=45, B3=60 deg, all
us_standard/100km-sensor/nadir-target). Demonstrates
scripts/synth_modtran/family_interpolate.py: log-transmittance-linear
interpolation between the two bracketing runs, quantified against the
naive "just use the nearest neighbor" alternative.

ATMOSPHERE DATA SOURCE (auto-detected via family_interpolate):
real MODTRAN 6 (modtran/real_runs/, 2026-07-17 run set) when staged;
synthetic fallback with a loud banner otherwise. With real data this
adds a HOLDOUT VALIDATION the synthetic era could not: interpolate the
45 deg point from its 30/60 deg neighbors and compare against the real
45 deg run -- a ground-truth test of the log-tau method itself.

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
import sys

import matplotlib.pyplot as plt
import numpy as np

from radiant.api import Sensor

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))
from scripts.synth_modtran.family_interpolate import (
    DATA_IS_REAL,
    FAMILIES,
    interpolate_family,
    tape7_path,
)

OUTPUT_DIR = Path(__file__).parent.parent / "outputs"
FAMILY = "zenith_fan_us_standard"
QUERY_ZENITH_DEG = 37.5  # customer requirement, between B1=30 and B2=45
BAND_MIN_UM, BAND_MAX_UM = 3.5, 5.0
SOURCE_LABEL = "MODTRAN 6 (real)" if DATA_IS_REAL else "MODTRAN (synthetic)"


def _matrix_point_tape7(family_name: str, axis_value: float) -> Path:
    """The tape7 file behind an exact matrix point (real preferred)."""
    family = FAMILIES[family_name]
    run_id = family.run_ids[family.axis_values.index(axis_value)]
    return tape7_path(run_id)


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


def _run_chain(atmosphere: dict, zenith_deg: float) -> dict:
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
            "gain_e_per_dn": 125.0,  # ~FWC/2^14 so full well maps within ADC range (Gap 65)
            "adc_bits": 14,
            "full_well_capacity_e": 2.0e6,
        },
        "atmosphere": atmosphere,
    }
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        # Gap 65: never suppress saturation warnings -- blanket "ignore"
        # is how three scenarios missed silent full-well clipping.
        warnings.filterwarnings("default", message=".*saturated.*")
        result = Sensor.from_dict(config).evaluate()
    tau_atm = np.asarray(result.stage_outputs["atmosphere"]["tau_atm"])
    return {"snr": result.metrics["snr"], "tau_inband": float(np.mean(tau_atm))}


def main() -> None:
    print("=== Scenario 8.1: Off-Nadir Angle Interpolation ===")
    print(f"  Atmosphere data: {SOURCE_LABEL}", end="")
    print(" (2026-07-17 run set)" if DATA_IS_REAL else " -- see modtran/synthetic/README.md")
    print(
        f"  Family: {FAMILY} (0/30/45/60 deg zenith fan, us_standard, 100km sensor, nadir target)"
    )
    print(f"  Query: {QUERY_ZENITH_DEG} deg off-nadir (customer requirement, not a matrix point)\n")

    # ------------------------------------------------------------------
    # Holdout validation of the method itself (real data only): rebuild
    # the 45 deg point from its 30/60 deg neighbors and compare against
    # the real 45 deg run. frac = (45-30)/(60-30) = 0.5.
    # ------------------------------------------------------------------
    if DATA_IS_REAL:
        wl_b1, tau_b1, _ = interpolate_family(FAMILY, 30.0)  # exact node
        wl_b3, tau_b3, _ = interpolate_family(FAMILY, 60.0)  # exact node
        wl_b2, tau_b2, _ = interpolate_family(FAMILY, 45.0)  # exact node = truth
        tau_holdout = np.exp(
            0.5 * np.log(np.clip(tau_b1, 1e-300, 1.0))
            + 0.5 * np.log(np.clip(tau_b3, 1e-300, 1.0))
        )
        hold_mask = (wl_b2 >= BAND_MIN_UM) & (wl_b2 <= BAND_MAX_UM)
        tau_true = float(np.mean(tau_b2[hold_mask]))
        tau_pred = float(np.mean(tau_holdout[hold_mask]))
        holdout_err_pct = 100.0 * (tau_pred - tau_true) / tau_true
        # Nearest-neighbor "prediction" of 45 deg would grab 30 or 60.
        tau_nn_30 = float(np.mean(tau_b1[hold_mask]))
        nn_err_pct = 100.0 * (tau_nn_30 - tau_true) / tau_true
        # Airmass-space alternative (CU-160): optical depth scales with
        # airmass = sec(zenith), so interpolating log-tau linearly in
        # sec(theta) rather than theta is the physically exact axis.
        sec = lambda d: 1.0 / math.cos(math.radians(d))  # noqa: E731
        frac_sec = (sec(45.0) - sec(30.0)) / (sec(60.0) - sec(30.0))
        tau_sec = np.exp(
            (1.0 - frac_sec) * np.log(np.clip(tau_b1, 1e-300, 1.0))
            + frac_sec * np.log(np.clip(tau_b3, 1e-300, 1.0))
        )
        tau_sec_pred = float(np.mean(tau_sec[hold_mask]))
        sec_err_pct = 100.0 * (tau_sec_pred - tau_true) / tau_true
        print("=== Holdout validation: predict the 45 deg run from 30 + 60 deg ===")
        print(f"  Real 45 deg (B2) in-band tau [-]:         {tau_true:.4f}")
        print(
            f"  Log-tau, linear in angle (the method):    {tau_pred:.4f}  "
            f"({holdout_err_pct:+.2f}%)"
        )
        print(
            f"  Log-tau, linear in airmass sec(theta):    {tau_sec_pred:.4f}  "
            f"({sec_err_pct:+.2f}%)  <- CU-160"
        )
        print(f"  Nearest-neighbor (30 deg) for reference:  {tau_nn_30:.4f}  ({nn_err_pct:+.2f}%)")
        print("  => the method's real-data credential for the 37.5 deg query below.\n")

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
        # Interpolated arrays exist only in memory -- the tabulated-CSV
        # route is the right plumbing for them. The nearest-neighbor
        # case IS an exact matrix point, so its tape7 file feeds the
        # chain directly (atmosphere.modtran.tape7_path, no CSV round-trip).
        trans_csv_i, lp_csv_i = _write_csvs(wl_interp, trans_interp, lp_interp, tmp_path, "interp")

        r_interp = _run_chain(
            {
                "model": "tabulated",
                "tabulated_transmittance_file": trans_csv_i,
                "tabulated_path_radiance_file": lp_csv_i,
            },
            QUERY_ZENITH_DEG,
        )
        r_nearest = _run_chain(
            {
                "model": "modtran",
                "modtran": {"tape7_path": str(_matrix_point_tape7(FAMILY, nearest_deg))},
            },
            QUERY_ZENITH_DEG,
        )

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
        label=f"Matrix points ({SOURCE_LABEL})",
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
