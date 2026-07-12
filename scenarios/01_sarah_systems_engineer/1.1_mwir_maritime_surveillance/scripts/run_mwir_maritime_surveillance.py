"""Scenario 1.1: MWIR Maritime Surveillance Trade Study.

Sarah is proposing a ship-detection sensor for a 500 km SSO. Customer wants
to detect a 30 m steel-hulled fishing vessel against open ocean, 20 deg
off-nadir, aperture 15-45 cm (f/2.5), 15 um InSb 640x512.

*** ATMOSPHERE DATA IS SYNTHETIC, NOT REAL MODTRAN ***
This scenario consumes modtran/synthetic/D2.synthetic.tp7 (maritime
aerosol, midlat_summer) -- a HITRAN-line-by-line-based synthetic tape7,
NOT a real MODTRAN run (see modtran/synthetic/README.md). TOT TRANS is
genuine independent physics (HITRAN); path radiance is not used here
(target is a reflective/point-source case, background computed by
RADIANT's own source model). Treat this scenario as a pipeline
demonstration, not a validated maritime-atmosphere trade study, until
real MODTRAN data replaces D2.

This script:
  1. Feeds D2's synthetic tape7 directly to RADIANT via
     atmosphere.model=modtran + atmosphere.modtran.tape7_path (the
     first-class tape7 import; no temp-CSV side door)
  2. Compares that MODTRAN-informed transmittance against RADIANT's own
     SimpleAtmosphere (maritime aerosol, same profile/geometry) at the
     same aperture sweep -- showing what the (synthetic) MODTRAN data
     changes relative to the parametric fallback
  3. Sweeps aperture 15-45 cm, computing SNR, NEDT, detection range
     (SNR=5 threshold), and NIIRS for both atmosphere sources
  4. Writes figures + a summary table

Usage:
    python run_mwir_maritime_surveillance.py
"""

from __future__ import annotations

import csv
import math
import warnings
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from radiant.api import Sensor
from radiant.atmosphere.modtran import Tape7Reader
from radiant.performance.detection_beer_lambert import detection_range_beer_lambert

SCENARIO_DIR = Path(__file__).parent.parent
D2_TAPE7 = SCENARIO_DIR.parent.parent.parent / "modtran" / "synthetic" / "D2.synthetic.tp7"
QE_CSV = SCENARIO_DIR / "inputs" / "insb_qe_representative.csv"
OUTPUT_DIR = SCENARIO_DIR / "outputs"

# ---------------------------------------------------------------------------
# System constants (customer requirements + InSb FPA specs, vendor units
# converted to RADIANT canonical units inline)
# ---------------------------------------------------------------------------
ALTITUDE_KM = 500.0  # SSO altitude [km]
OFF_NADIR_DEG = 20.0  # look angle from nadir [deg]
PIXEL_PITCH_UM = 15.0  # InSb pixel pitch [um]
F_NUMBER = 2.5  # optics f/#
BAND_MIN_UM, BAND_MAX_UM = 3.5, 5.0  # MWIR band [um]
INTEGRATION_TIME_S = 5.0e-3  # frame integration [s]
DETECTOR_TEMP_K = 77.0  # InSb operating temp [K]
DARK_RATE_E_S = 5.0e4  # InSb dark current @ 77K [e-/s], typical
READ_NOISE_E = 30.0  # e- RMS, typical InSb ROIC
FULL_WELL_E = 8.0e6  # e-, typical large-well InSb
APERTURES_CM = np.linspace(15.0, 45.0, 7)  # customer's aperture range [cm]

# Ship target: 30 m x 8 m steel hull, "about 0.7-0.85" per the catalog's
# vendor note -> use the library's generic "steel" emissivity as a
# representative curve (rust would raise this somewhat; not modeled --
# see gaps.md).
SHIP_LENGTH_M, SHIP_BEAM_M = 30.0, 8.0
SHIP_TEMP_K = 288.0  # steel hull near sea temperature
SHIP_EMISSIVITY_PATH = str(
    Path(__file__).resolve().parents[4] / "data" / "emissivity" / "steel.csv"
)

# Ocean background: catalog says ~0.98 emissivity, ~288 K, wind-state
# dependent (calm vs sea-state 3) -- RADIANT's library only has a calm-water
# curve; sea-state dependence is NOT modeled (Gap, see gaps.md).
OCEAN_TEMP_K = 288.0
OCEAN_MATERIAL = "water_calm"

SLANT_RANGE_M = ALTITUDE_KM * 1000.0 / math.cos(math.radians(OFF_NADIR_DEG))  # flat-Earth approx


def _band_average_qe() -> float:
    """Band-average the representative InSb QE curve over BAND_MIN..MAX_UM."""
    wl, qe = [], []
    with QE_CSV.open() as f:
        reader = csv.reader(f)
        next(reader)  # header
        for row in reader:
            wl.append(float(row[0]))
            qe.append(float(row[1]))
    wl_grid = np.linspace(BAND_MIN_UM, BAND_MAX_UM, 200)
    qe_interp = np.interp(wl_grid, wl, qe)
    return float(np.mean(qe_interp))


QE_BAND_AVERAGE = _band_average_qe()  # scalar QE, band-averaged from the InSb curve above


def _preflight_d2() -> None:
    """Fail loudly before the sweep if D2 is missing or would hit the
    CU-066 positional-fallback path (the loader's own parse happens
    inside the sweep's warning-suppression context)."""
    if not D2_TAPE7.exists():
        raise FileNotFoundError(
            f"{D2_TAPE7} not found. Generate it first:\n"
            "  python scripts/generate_synthetic_tape7.py --run-id D2"
        )
    with warnings.catch_warnings():
        warnings.simplefilter("error")  # fail loudly on the CU-066 fallback path
        Tape7Reader(D2_TAPE7).parse()


def make_config(
    aperture_m: float,
    atmosphere_source: str,
) -> dict:
    """Build a RADIANT config dict. atmosphere_source: 'simple' or 'modtran_d2'."""
    config: dict = {
        "source": {
            "scene_type": "sub_pixel",
            "regime_override": "sub_pixel",
            "target": {
                "temperature": SHIP_TEMP_K,
                "emissivity_path": SHIP_EMISSIVITY_PATH,
                "projected_area_m2": SHIP_LENGTH_M * SHIP_BEAM_M,
                "range_m": SLANT_RANGE_M,
            },
            "background": {
                "temperature": OCEAN_TEMP_K,
                "material": OCEAN_MATERIAL,
            },
        },
        "geometry": {
            "sensor_altitude_m": ALTITUDE_KM * 1000.0,
            "path_zenith_rad": math.radians(OFF_NADIR_DEG),
        },
        "optics": {
            "aperture_diameter_m": aperture_m,
            "focal_length_m": aperture_m * F_NUMBER,
            "transmission_scalar": 0.85,
        },
        "detector": {
            "pixel_pitch_x_um": PIXEL_PITCH_UM,
            "pixel_pitch_y_um": PIXEL_PITCH_UM,
            "qe_value": QE_BAND_AVERAGE,
            "dark_rate_e_per_s": DARK_RATE_E_S,
            "detector_temperature_K": DETECTOR_TEMP_K,
        },
        "spectral_integration": {
            "filter_min_um": BAND_MIN_UM,
            "filter_max_um": BAND_MAX_UM,
            "integration_time_s": INTEGRATION_TIME_S,
        },
        "readout": {
            "read_noise_e_rms": READ_NOISE_E,
            "gain_e_per_dn": 500.0,  # ~FWC/2^14 so full well maps within ADC range (Gap 65)
            "adc_bits": 14,
            "full_well_capacity_e": FULL_WELL_E,
        },
    }
    if atmosphere_source == "simple":
        config["atmosphere"] = {
            "model": "simple",
            "aerosol_type": "maritime",
            "standard_atmosphere": "midlat_summer",
        }
    else:
        # First-class tape7 import: the file wins; no binary, no cache,
        # no fallback (RADIANT_Atmosphere.md §5.1).
        config["atmosphere"] = {
            "model": "modtran",
            "modtran": {"tape7_path": str(D2_TAPE7)},
        }
    return config


def run_sweep(atmosphere_source: str) -> list[dict]:
    rows = []
    for ap_cm in APERTURES_CM:
        aperture_m = ap_cm / 100.0
        config = make_config(aperture_m, atmosphere_source)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            # Gap 65: never suppress saturation warnings -- blanket "ignore"
            # is how three scenarios missed silent full-well clipping.
            warnings.filterwarnings("default", message=".*saturated.*")
            sensor = Sensor.from_dict(config)
            result = sensor.evaluate()

        snr = result.metrics["snr"]
        noise_e = (
            result.stage_outputs["spectral_integration"]["signal_e"] / snr
            if snr > 0
            else float("nan")
        )
        signal_e = result.stage_outputs["spectral_integration"]["signal_e"]

        # Detection range via Beer-Lambert extrapolation from this aperture's
        # reference SNR: alpha derived from the in-band mean transmittance
        # at the actual slant range (tau = exp(-alpha * R) -> alpha = -ln(tau)/R).
        tau_atm = np.asarray(result.stage_outputs["atmosphere"]["tau_atm"])
        tau_ref = max(float(np.mean(tau_atm)), 1e-6)
        alpha = -math.log(tau_ref) / SLANT_RANGE_M
        det_result = detection_range_beer_lambert(
            signal_e_at_ref=signal_e,
            noise_e=noise_e,
            ref_range_m=SLANT_RANGE_M,
            extinction_coeff=alpha,
            snr_threshold=5.0,
        )

        rows.append(
            {
                "aperture_cm": ap_cm,
                "snr": snr,
                "nedt_K": result.metrics.get("nedt_K"),
                "niirs": result.metrics.get("niirs"),
                "detection_range_km": det_result.range_m / 1000.0
                if math.isfinite(det_result.range_m)
                else float("nan"),
                "tau_inband": tau_ref,
            }
        )
    return rows


def main() -> None:
    print("=== Scenario 1.1: MWIR Maritime Surveillance ===")
    print(
        f"  Altitude: {ALTITUDE_KM:.0f} km, off-nadir: {OFF_NADIR_DEG:.0f} deg, "
        f"slant range: {SLANT_RANGE_M / 1000.0:.1f} km"
    )
    print(f"  Target: {SHIP_LENGTH_M:.0f}x{SHIP_BEAM_M:.0f} m steel hull @ {SHIP_TEMP_K:.0f} K")
    print(
        f"  Band: {BAND_MIN_UM}-{BAND_MAX_UM} um, InSb {PIXEL_PITCH_UM:.0f} um pixel, f/{F_NUMBER}"
    )
    print()
    print("  *** Atmosphere: modtran_d2 uses SYNTHETIC (not real MODTRAN) data ***")
    print("  *** See modtran/synthetic/README.md for what's genuinely independent. ***")
    print()
    print("  PHYSICS NOTE: the aperture sweep holds f/# fixed at 2.5 (focal length")
    print("  scales with aperture). At fixed f/#, per-pixel etendue -- and thus")
    print("  photon flux for both the sub-pixel target and the extended ocean")
    print("  background -- is invariant with aperture, so SNR stays essentially")
    print("  flat across the sweep. The aperture benefit shows up entirely as")
    print("  improved resolution (NIIRS rises as the diffraction PSF shrinks),")
    print("  not as more signal. A 'more SNR from a bigger telescope' trade")
    print("  requires varying f/# (or fixing focal length), not just aperture.")

    _preflight_d2()

    print("\n=== Sweep: SimpleAtmosphere (maritime aerosol) ===")
    rows_simple = run_sweep("simple")
    for r in rows_simple:
        print(
            f"  D={r['aperture_cm']:5.1f} cm  SNR={r['snr']:7.2f}  NEDT={r['nedt_K']:.4f} K  "
            f"NIIRS={r['niirs']:.2f}  det.range={r['detection_range_km']:.1f} km  tau={r['tau_inband']:.4f}"
        )

    print("\n=== Sweep: MODTRAN-D2 (synthetic, maritime aerosol) ===")
    rows_modtran = run_sweep("modtran_d2")
    for r in rows_modtran:
        print(
            f"  D={r['aperture_cm']:5.1f} cm  SNR={r['snr']:7.2f}  NEDT={r['nedt_K']:.4f} K  "
            f"NIIRS={r['niirs']:.2f}  det.range={r['detection_range_km']:.1f} km  tau={r['tau_inband']:.4f}"
        )

    # -----------------------------------------------------------------
    # Summary table (the "PPT slide" deliverable)
    # -----------------------------------------------------------------
    print("\n=== Summary Table (aperture=30 cm, mid-range) ===")
    mid_idx = len(APERTURES_CM) // 2
    print(f"  {'Metric':<28s} {'SimpleAtmosphere':>18s} {'MODTRAN-D2 (synthetic)':>24s}")
    print(f"  {'-' * 28} {'-' * 18} {'-' * 24}")
    print(
        f"  {'SNR [-]':<28s} {rows_simple[mid_idx]['snr']:>18.2f} {rows_modtran[mid_idx]['snr']:>24.2f}"
    )
    print(
        f"  {'NEDT [K]':<28s} {rows_simple[mid_idx]['nedt_K']:>18.4f} {rows_modtran[mid_idx]['nedt_K']:>24.4f}"
    )
    print(
        f"  {'NIIRS [-]':<28s} {rows_simple[mid_idx]['niirs']:>18.2f} {rows_modtran[mid_idx]['niirs']:>24.2f}"
    )
    print(
        f"  {'Detection range @SNR=5 [km]':<28s} {rows_simple[mid_idx]['detection_range_km']:>18.1f} "
        f"{rows_modtran[mid_idx]['detection_range_km']:>24.1f}"
    )
    print(
        f"  {'In-band transmittance [-]':<28s} {rows_simple[mid_idx]['tau_inband']:>18.4f} "
        f"{rows_modtran[mid_idx]['tau_inband']:>24.4f}"
    )

    # -----------------------------------------------------------------
    # Figures
    # -----------------------------------------------------------------
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 4.5))
    ax1.plot(APERTURES_CM, [r["niirs"] for r in rows_simple], "o-", label="SimpleAtmosphere")
    ax1.plot(
        APERTURES_CM, [r["niirs"] for r in rows_modtran], "s--", label="MODTRAN-D2 (synthetic)"
    )
    ax1.set_xlabel("Aperture diameter [cm]")
    ax1.set_ylabel("NIIRS [-]")
    ax1.set_title("NIIRS vs. aperture (fixed f/2.5 -- SNR is flat, see walkthrough)")
    ax1.legend()
    ax1.grid(alpha=0.3)

    ax2.plot(
        APERTURES_CM, [r["detection_range_km"] for r in rows_simple], "o-", label="SimpleAtmosphere"
    )
    ax2.plot(
        APERTURES_CM,
        [r["detection_range_km"] for r in rows_modtran],
        "s--",
        label="MODTRAN-D2 (synthetic)",
    )
    ax2.axhline(SLANT_RANGE_M / 1000.0, color="gray", linestyle=":", label="Nominal slant range")
    ax2.set_xlabel("Aperture diameter [cm]")
    ax2.set_ylabel("Detection range @ SNR=5 [km]")
    ax2.set_title("Detection range vs. aperture")
    ax2.legend()
    ax2.grid(alpha=0.3)

    fig.tight_layout()
    fig1_path = OUTPUT_DIR / "fig1_snr_and_range_vs_aperture.png"
    fig.savefig(fig1_path, dpi=130)
    plt.close(fig)
    print(f"\nWrote {fig1_path}")


if __name__ == "__main__":
    main()
