"""Scenario 6.2: Atmospheric Model Intercomparison.

Dr. Chen wants to compare RADIANT's own Beer-Lambert (SimpleAtmosphere)
transmittance against MODTRAN, across all six named standard-atmosphere
profiles, for the same nadir/100 km-sensor path.

*** ATMOSPHERE DATA IS SYNTHETIC, NOT REAL MODTRAN ***
Consumes modtran/synthetic/A1-A6.synthetic.tp7 (see
modtran/synthetic/README.md). TOT TRANS is genuine independent physics
(HITRAN line-by-line on an independently-built layered atmosphere);
treat this as demonstrating the comparison PIPELINE, not a validated
model-vs-model benchmark, until real MODTRAN data replaces A1-A6.

Deviation from the original catalog framing: the catalog specifies
"10 deg off-nadir, 500 km path, midlat summer" for a single profile;
the run matrix's A-block is nadir at 100 km sensor altitude for all
six profiles instead (a broader, more useful profile-family sweep at
a fixed geometry already available). See gaps.md.

libRadtran comparison is NOT included -- no libRadtran implementation,
parser, or real output exists in this repo, and (per the same
no-fabricated-independent-data policy established for MODTRAN)
hand-authoring plausible libRadtran numbers would defeat the purpose
of an intercomparison. Filed as an open gap, not faked.

This script:
  1. Loads all 6 A-block synthetic tape7s via Tape7Reader (for the
     spectral overlay) and feeds each file directly to the chain via
     atmosphere.model=modtran + atmosphere.modtran.tape7_path (the
     first-class tape7 import; no temp-CSV side door)
  2. Runs SimpleAtmosphere at the matching profile/geometry for each
  3. Overlays spectral transmittance (RADIANT vs MODTRAN-synthetic)
  4. Computes in-band mean transmittance + residual per profile
  5. Runs the full chain (fixed sensor) under both atmosphere sources
     to see the resulting SNR delta per profile

Usage:
    python run_atmospheric_intercomparison.py
"""

from __future__ import annotations

import warnings
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from radiant.api import Sensor
from radiant.atmosphere.modtran import Tape7Reader

SCENARIO_DIR = Path(__file__).parent.parent
MODTRAN_SYNTH_DIR = SCENARIO_DIR.parent.parent.parent / "modtran" / "synthetic"
OUTPUT_DIR = SCENARIO_DIR / "outputs"

PROFILES = [
    "us_standard",
    "tropical",
    "midlat_summer",
    "midlat_winter",
    "subarctic_summer",
    "subarctic_winter",
]
RUN_IDS = {
    "us_standard": "A1",
    "tropical": "A2",
    "midlat_summer": "A3",
    "midlat_winter": "A4",
    "subarctic_summer": "A5",
    "subarctic_winter": "A6",
}

# Fixed sensor for the chain-level SNR comparison (representative MWIR
# imager; not tied to any specific customer requirement -- purely to
# show how the atmosphere-source delta propagates to SNR).
BAND_MIN_UM, BAND_MAX_UM = 3.5, 5.0
SENSOR_ALTITUDE_M = 100_000.0  # matches the A-block's h1_sensor_km=100
APERTURE_M = 0.30
FOCAL_LENGTH_M = 0.75
PIXEL_PITCH_UM = 20.0


def _load_tape7(run_id: str) -> tuple[Path, np.ndarray, np.ndarray]:
    """Locate a synthetic tape7 and parse it (fail-loud) for the overlay.

    The chain itself consumes the file directly via
    atmosphere.modtran.tape7_path; this parse exists for the spectral
    figures/residuals and to fail loudly on the CU-066 fallback path
    before any chain runs.
    """
    tape7 = MODTRAN_SYNTH_DIR / f"{run_id}.synthetic.tp7"
    if not tape7.exists():
        raise FileNotFoundError(
            f"{tape7} not found. Generate it first:\n"
            f"  python scripts/generate_synthetic_tape7.py --run-id {run_id}"
        )
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        wl_um, trans, _path_radiance, _gr = Tape7Reader(tape7).to_radiant_units()
    return tape7, wl_um, trans


def _make_config(atmosphere_source: str, profile: str, tape7_path: Path | None) -> dict:
    config: dict = {
        "source": {
            "scene_type": "extended",
            "target": {"temperature": 300.0, "emissivity": 0.95},
            "background": {"temperature": 288.0, "emissivity": 0.95},
        },
        "geometry": {"sensor_altitude_m": SENSOR_ALTITUDE_M},
        "optics": {
            "aperture_diameter_m": APERTURE_M,
            "focal_length_m": FOCAL_LENGTH_M,
            "transmission_scalar": 0.85,
        },
        "detector": {
            "pixel_pitch_x_um": PIXEL_PITCH_UM,
            "pixel_pitch_y_um": PIXEL_PITCH_UM,
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
    }
    if atmosphere_source == "simple":
        config["atmosphere"] = {"model": "simple", "standard_atmosphere": profile}
    else:
        # First-class tape7 import: the file wins; no binary, no cache,
        # no fallback (RADIANT_Atmosphere.md §5.1).
        config["atmosphere"] = {
            "model": "modtran",
            "modtran": {"tape7_path": str(tape7_path)},
        }
    return config


def main() -> None:
    print("=== Scenario 6.2: Atmospheric Model Intercomparison ===")
    print("  *** Atmosphere source 'modtran' is SYNTHETIC, not real MODTRAN ***")
    print(
        "  *** See modtran/synthetic/README.md. libRadtran comparison NOT included -- see gaps.md ***\n"
    )

    results = []
    spectra = {}
    for profile in PROFILES:
        run_id = RUN_IDS[profile]
        tape7_path, wl_um, trans = _load_tape7(run_id)
        spectra[profile] = (wl_um, trans)

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            # Gap 65: never suppress saturation warnings -- blanket "ignore"
            # is how three scenarios missed silent full-well clipping.
            warnings.filterwarnings("default", message=".*saturated.*")
            s_simple = Sensor.from_dict(_make_config("simple", profile, None))
            r_simple = s_simple.evaluate()
            s_modtran = Sensor.from_dict(_make_config("modtran", profile, tape7_path))
            r_modtran = s_modtran.evaluate()

        tau_simple = np.asarray(r_simple.stage_outputs["atmosphere"]["tau_atm"])
        tau_modtran_inband = np.interp(
            np.linspace(BAND_MIN_UM, BAND_MAX_UM, len(tau_simple)), wl_um, trans
        )

        row = {
            "profile": profile,
            "run_id": run_id,
            "tau_simple_inband": float(np.mean(tau_simple)),
            "tau_modtran_inband": float(np.mean(tau_modtran_inband)),
            "snr_simple": r_simple.metrics["snr"],
            "snr_modtran": r_modtran.metrics["snr"],
        }
        row["tau_residual_pct"] = (
            100.0
            * (row["tau_modtran_inband"] - row["tau_simple_inband"])
            / row["tau_modtran_inband"]
        )
        row["snr_residual_pct"] = (
            100.0 * (row["snr_modtran"] - row["snr_simple"]) / row["snr_modtran"]
        )
        results.append(row)

    print(
        f"  {'Profile':<18s} {'tau_simple':>11s} {'tau_MODTRAN':>12s} {'residual%':>10s} "
        f"{'SNR_simple':>11s} {'SNR_MODTRAN':>12s} {'residual%':>10s}"
    )
    print(f"  {'-' * 18} {'-' * 11} {'-' * 12} {'-' * 10} {'-' * 11} {'-' * 12} {'-' * 10}")
    for r in results:
        print(
            f"  {r['profile']:<18s} {r['tau_simple_inband']:>11.4f} {r['tau_modtran_inband']:>12.4f} "
            f"{r['tau_residual_pct']:>9.1f}% {r['snr_simple']:>11.2f} {r['snr_modtran']:>12.2f} "
            f"{r['snr_residual_pct']:>9.1f}%"
        )

    worst = max(results, key=lambda r: abs(r["tau_residual_pct"]))
    print(
        f"\n  Largest transmittance residual: {worst['profile']} ({worst['tau_residual_pct']:.1f}%)"
    )
    print("  Interpretation caveat: since 'MODTRAN' here is HITRAN-line-by-line synthetic data")
    print("  (not real MODTRAN, and RADIANT's own SimpleAtmosphere uses a DIFFERENT simplified")
    print("  band-fit approach), this residual reflects a genuine difference in modeling approach")
    print("  (line-by-line vs. empirical band fit), not a validated 'error' in either model.")

    # -----------------------------------------------------------------
    # Figures
    # -----------------------------------------------------------------
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    fig, axes = plt.subplots(2, 3, figsize=(15, 8), sharex=True, sharey=True)
    for ax, profile in zip(axes.flat, PROFILES, strict=True):
        wl_um, trans = spectra[profile]
        mask = (wl_um >= BAND_MIN_UM) & (wl_um <= BAND_MAX_UM)
        ax.plot(wl_um[mask], trans[mask], lw=0.8, label="MODTRAN (synthetic)", color="C1")
        ax.axhline(
            next(r["tau_simple_inband"] for r in results if r["profile"] == profile),
            color="C0",
            linestyle="--",
            label="SimpleAtmosphere (band mean)",
        )
        ax.set_title(profile)
        ax.set_xlabel("Wavelength [um]")
        ax.set_ylabel("Transmittance [-]")
        ax.grid(alpha=0.3)
    axes.flat[0].legend(fontsize=8)
    fig.suptitle(
        "Scenario 6.2: RADIANT SimpleAtmosphere vs. MODTRAN-synthetic transmittance, 3.5-5.0 um"
    )
    fig.tight_layout()
    fig1_path = OUTPUT_DIR / "fig1_transmittance_overlay_by_profile.png"
    fig.savefig(fig1_path, dpi=130)
    plt.close(fig)
    print(f"\nWrote {fig1_path}")

    fig2, ax = plt.subplots(figsize=(8, 5))
    x = np.arange(len(PROFILES))
    ax.bar(x - 0.2, [r["tau_simple_inband"] for r in results], width=0.4, label="SimpleAtmosphere")
    ax.bar(
        x + 0.2, [r["tau_modtran_inband"] for r in results], width=0.4, label="MODTRAN (synthetic)"
    )
    ax.set_xticks(x)
    ax.set_xticklabels(PROFILES, rotation=30, ha="right")
    ax.set_ylabel("In-band mean transmittance [-]")
    ax.set_title("In-band transmittance by profile and atmosphere source")
    ax.legend()
    ax.grid(alpha=0.3, axis="y")
    fig2.tight_layout()
    fig2_path = OUTPUT_DIR / "fig2_inband_transmittance_by_profile.png"
    fig2.savefig(fig2_path, dpi=130)
    plt.close(fig2)
    print(f"Wrote {fig2_path}")


if __name__ == "__main__":
    main()
