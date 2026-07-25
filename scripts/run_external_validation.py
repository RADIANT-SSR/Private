"""Run the external-validation comparisons (External_Validation_Plan).

Currently implemented: Sentinel-2 MSI SNR @ L_ref (bands B2/B3/B4/B8 VNIR + B11 SWIR)
against ESA's published requirement and measured values. All instrument inputs and their
confidence classes are documented in ``docs/validation/sentinel2_msi_source_data.md`` —
this script encodes that table verbatim and prints a per-band comparison with units on
every value plus the regime/assumption discussion (owner hard rules).

Design: the published SNR is specified AT an at-sensor reference radiance L_ref, so each
band drives the chain with a flat user-radiance spectrum equal to L_ref through a vacuum
(``atmosphere.model = exo``) — the comparison isolates aperture-to-electrons radiometry
from scene/atmosphere modeling. Outputs are regenerable (Rule 26); nothing is committed
from a run.

Usage:  python scripts/run_external_validation.py
"""

from __future__ import annotations

import csv
import tempfile
import warnings
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from radiant.api.session import RadiantSession
from radiant.core.orbit import ground_track_speed_m_s

# --- Shared instrument (see sentinel2_msi_source_data.md for provenance) -----
APERTURE_D_M = 0.150  # m — published (pupil diameter)
FOCAL_LENGTH_M = 0.5895  # m — derived: p*h/GSD (7.5 µm * 786 km / 10 m)
TAU_OPTICS = 0.75  # — ASSUMPTION (envelope 0.60–0.85)
ALTITUDE_M = 786_000.0  # m — published
READ_NOISE_E = 15.0  # e- RMS — ASSUMPTION (envelope 5–30; non-binding at L_ref)
FULL_WELL_E = 500_000.0  # e- — ANALYSIS MODE: sized above signal(Lmax); never clips.
# Real MSI sizes per-band CTIA capacity/CVF to avoid Lmax saturation (eoPortal);
# charge collection at L_ref is unaffected by this choice.
ADC_BITS = 12  # — published
N_TDI = 2  # — published "1 TDI stage for 2 lines" modeled as 2-line charge sum


@dataclass(frozen=True)
class Band:
    name: str
    center_nm: float  # published (S2A)
    fwhm_nm: float  # published (S2A)
    l_ref: float  # W/m²/sr/µm — published
    snr_required: float  # — published
    snr_measured: float | None  # — published (S2C) where available
    qe: float  # — ASSUMPTION (per-band envelope in the data doc)
    qe_lo: float
    qe_hi: float
    pitch_um: float  # µm — published
    gsd_m: float  # m — published


BANDS: tuple[Band, ...] = (
    Band("B2", 492.7, 64.0, 128.00, 154.0, 162.0, 0.50, 0.35, 0.65, 7.5, 10.0),
    Band("B3", 559.8, 35.0, 128.00, 168.0, None, 0.55, 0.40, 0.70, 7.5, 10.0),
    Band("B4", 664.6, 30.0, 108.00, 142.0, 175.0, 0.55, 0.40, 0.70, 7.5, 10.0),
    Band("B8", 832.8, 118.0, 103.00, 174.0, None, 0.35, 0.25, 0.50, 7.5, 10.0),
    Band("B11", 1613.7, 88.0, 4.00, 100.0, 133.0, 0.75, 0.60, 0.85, 15.0, 20.0),
)

TAU_LO, TAU_HI = 0.60, 0.85  # optics-transmission envelope (assumption)


def _band_grid_um(band: Band, n: int = 41) -> np.ndarray:
    lo = (band.center_nm - band.fwhm_nm / 2.0) / 1000.0
    hi = (band.center_nm + band.fwhm_nm / 2.0) / 1000.0
    return np.linspace(lo, hi, n)


def _write_radiance_csv(path: Path, wl_um: np.ndarray, level: float) -> None:
    with path.open("w", newline="\n", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["wavelength_um", "radiance_w_m2_sr_um"])
        for w in wl_um:
            writer.writerow([f"{w:.6f}", f"{level:.6f}"])


def _run_band(band: Band, qe: float, tau: float, tmp: Path) -> tuple[float, float, float]:
    """Return (predicted SNR [-], signal [e-], well-fill fraction [-]) for one band at L_ref."""
    wl = _band_grid_um(band)
    csv_path = tmp / f"lref_{band.name}.csv"
    # Table padded ±2 nm past the band edges so the strict tabulated-range check
    # never trips on float equality at the grid endpoints.
    pad = 0.002
    _write_radiance_csv(csv_path, np.linspace(wl[0] - pad, wl[-1] + pad, len(wl) + 4), band.l_ref)

    line_time_s = band.gsd_m / ground_track_speed_m_s(ALTITUDE_M)

    session = RadiantSession(wavelength_um=wl)
    params = session.default_params()
    params.set("source.target.user_radiance_path", str(csv_path))
    params.set("source.target_location", "auto")
    params.set("source.scene_type", "extended")
    params.set("atmosphere.model", "exo")
    params.set("geometry.sensor_altitude_m", ALTITUDE_M)
    params.set("geometry.target_altitude_m", 0.0)
    params.set("optics.aperture_diameter_m", APERTURE_D_M)
    params.set("optics.focal_length_m", FOCAL_LENGTH_M)
    params.set("optics.transmission_scalar", tau)
    params.set("detector.pixel_pitch_x_um", band.pitch_um)
    params.set("detector.pixel_pitch_y_um", band.pitch_um)
    params.set("detector.qe_value", qe)
    params.set("detector.dark_rate_e_per_s", 100.0)  # assumption; non-binding in VNIR
    params.set("spectral_integration.filter_min_um", float(wl[0]))
    params.set("spectral_integration.filter_max_um", float(wl[-1]))
    params.set("spectral_integration.integration_time_s", line_time_s)
    params.set("readout.n_tdi", N_TDI)
    params.set("readout.read_noise_e_rms", READ_NOISE_E)
    params.set("readout.full_well_capacity_e", FULL_WELL_E)
    params.set("readout.adc_bits", ADC_BITS)
    params.set("readout.gain_e_per_dn", FULL_WELL_E / 2**ADC_BITS)
    params.resolve()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        result = session.run(params)
    well = float(result.stage_outputs["readout"]["well_fill_fraction"])
    return float(result.snr()), float(result.stage_outputs["readout"]["signal_e_final"]), well


def main() -> None:
    print("Sentinel-2 MSI — RADIANT predicted SNR @ L_ref vs ESA published")
    print("(exo atmosphere; extended scene; user-radiance = L_ref; signal in e-; see")
    print(" docs/validation/sentinel2_msi_source_data.md for provenance)\n")
    header = (
        f"{'band':<5} {'L_ref':>8} {'pred SNR':>9} {'envelope':>15} "
        f"{'req':>6} {'meas':>6} {'signal':>12} {'impl QE·τ':>10}"
    )
    print(header)
    print(
        f"{'':<5} {'[W/m²/sr/µm]':>8} {'[-]':>9} {'[- min–max]':>15} "
        f"{'[-]':>6} {'[-]':>6} {'[e-]':>12} {'[-]':>10}"
    )
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        for band in BANDS:
            snr, sig, well = _run_band(band, band.qe, TAU_OPTICS, tmp)
            snr_lo, _, _ = _run_band(band, band.qe_lo, TAU_LO, tmp)
            snr_hi, _, _ = _run_band(band, band.qe_hi, TAU_HI, tmp)
            meas = f"{band.snr_measured:.0f}" if band.snr_measured else "—"
            clip = f"  WELL-CLIPPED ({well:.0%} fill)" if well >= 0.999 else ""
            # Shot-limited inversion: SNR ∝ sqrt(QE·τ·t·N), so the measured SNR
            # implies a throughput product (QE·τ)_impl = (QE·τ)_assumed·(meas/pred)².
            if band.snr_measured:
                implied = band.qe * TAU_OPTICS * (band.snr_measured / snr) ** 2
                impl_txt = f"{implied:>10.3f}"
            else:
                impl_txt = f"{'—':>10}"
            print(
                f"{band.name:<5} {band.l_ref:>8.2f} {snr:>9.1f} "
                f"{snr_lo:>7.1f}–{snr_hi:<6.1f} {band.snr_required:>6.0f} "
                f"{meas:>6} {sig:>12.0f} {impl_txt}{clip}"
            )
    print(
        "\nRegime notes: extended scene (EE_box = 1 — no ensquared-energy factor);\n"
        "shot-noise-dominated at L_ref (read noise 15 e- RMS is non-binding);\n"
        "prediction scales as sqrt(QE·τ·t_int·N_TDI) in this limit, so the envelope\n"
        "spans the QE and τ assumption ranges. TDI modeled as 2-line charge sum\n"
        "(signal ×2, one read). Verdict criterion: CONSISTENT if the published value\n"
        "falls inside the assumption envelope. The implied-QE·τ column inverts the\n"
        "measured SNR for the throughput product it would require (shot limit) —\n"
        "judged plausible/implausible against detector-technology expectations."
    )


# ============================ Landsat 8 TIRS =================================
# Provenance: docs/validation/landsat_tirs_source_data.md. Validation target:
# measured NEdT (Montanaro 2014b Table 2). The published parameter set (CE 0.8%,
# tau 0.49) over-collects vs the published 5e6 e- full well at the 360 K
# calibrated ceiling, so the effective throughput is INVERTED from that
# saturation constraint (see data doc "Modeling notes"), then NEdT predicted.

TIRS_D_M = 0.1085  # m — derived (178 mm / f1.64), published components
TIRS_F_M = 0.178  # m — published
TIRS_TAU = 0.49  # — published system model value (Jhabvala 2011)
TIRS_CE_PUB = 0.008  # — published band-average conversion efficiency
TIRS_PITCH_UM = 25.0  # µm — published
TIRS_T_INT_S = 3.49e-3  # s — published (as flown)
TIRS_DARK_E_S = 4.0e7  # e-/s — published
TIRS_READ_LO = 260.0  # e- RMS — published ROIC typical
TIRS_READ_HI = 1033.0  # e- RMS — sqrt(260^2 + 1000^2), electronics spec ceiling
TIRS_FULL_WELL = 5.0e6  # e- — published (">5 million electrons")
TIRS_ALT_M = 705_000.0  # m — published
# Per-band published saturation temperatures (Reuter 2015) — the well is full there
# by definition, giving a published physical constraint to invert throughput from.
TIRS_SAT_K = {"B10": 400.0, "B11": 370.0}

TIRS_BANDS = (
    ("B10", 10.6, 11.2, {270.0: (0.56, 0.057), 300.0: (0.40, 0.049), 320.0: (0.35, 0.045)}),
    ("B11", 11.5, 12.5, {270.0: (0.53, 0.060), 300.0: (0.40, 0.052), 320.0: (0.35, 0.051)}),
)


def _run_tirs(lo_um: float, hi_um: float, scene_k: float, qe: float, read_e: float):
    """Run one TIRS band/temperature; return (NEDT [K], signal [e-], well fill [-])."""
    wl = np.linspace(lo_um, hi_um, 41)
    session = RadiantSession(wavelength_um=wl)
    params = session.default_params()
    params.set("source.target.temperature", scene_k)
    params.set("source.target.emissivity", 1.0)  # onboard-blackbody validation view
    params.set("source.scene_type", "extended")
    params.set("atmosphere.model", "exo")
    params.set("geometry.sensor_altitude_m", TIRS_ALT_M)
    params.set("geometry.target_altitude_m", 0.0)
    params.set("optics.aperture_diameter_m", TIRS_D_M)
    params.set("optics.focal_length_m", TIRS_F_M)
    params.set("optics.transmission_scalar", TIRS_TAU)
    params.set("detector.pixel_pitch_x_um", TIRS_PITCH_UM)
    params.set("detector.pixel_pitch_y_um", TIRS_PITCH_UM)
    params.set("detector.qe_value", qe)
    params.set("detector.dark_rate_e_per_s", TIRS_DARK_E_S)
    params.set("spectral_integration.filter_min_um", float(wl[0]))
    params.set("spectral_integration.filter_max_um", float(wl[-1]))
    params.set("spectral_integration.integration_time_s", TIRS_T_INT_S)
    params.set("readout.read_noise_e_rms", read_e)
    params.set("readout.full_well_capacity_e", TIRS_FULL_WELL)
    params.set("readout.adc_bits", 12)
    params.set("readout.gain_e_per_dn", TIRS_FULL_WELL / 2**12)
    params.resolve()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        result = session.run(params)
    nedt_k = float(result.nedt())
    sig = float(result.stage_outputs["readout"]["signal_e_final"])
    well = float(result.stage_outputs["readout"]["well_fill_fraction"])
    return nedt_k, sig, well


def tirs_main() -> None:
    print("\nLandsat 8 TIRS — RADIANT predicted NEdT vs published (Montanaro 2014b)")
    print("(300 K-class blackbody scene, exo path, extended; NEdT in mK;")
    print(" see docs/validation/landsat_tirs_source_data.md for provenance)\n")
    for name, lo, hi, table in TIRS_BANDS:
        # Bound A — raw published parameters (CE 0.8%, tau 0.49), no tuning. The raw
        # signal agrees with Jhabvala's published signal model within ~25%.
        _, sig_raw, well_raw = _run_tirs(lo, hi, 300.0, TIRS_CE_PUB, TIRS_READ_LO)
        # Bound B — CE inverted from the published per-band saturation temperature
        # (well full there by definition). Planck ratio taken unclipped via tiny qe.
        _, s300_tiny, _ = _run_tirs(lo, hi, 300.0, TIRS_CE_PUB * 1e-3, TIRS_READ_LO)
        _, s_sat_tiny, _ = _run_tirs(lo, hi, TIRS_SAT_K[name], TIRS_CE_PUB * 1e-3, TIRS_READ_LO)
        planck_ratio = s_sat_tiny / s300_tiny
        qe_eff = TIRS_CE_PUB * TIRS_FULL_WELL / (sig_raw * planck_ratio)
        scale = qe_eff / TIRS_CE_PUB
        print(
            f"{name}: raw model well fill {well_raw:.0%} at 300 K (signal {sig_raw:.3g} e-); "
            f"saturation inversion at {TIRS_SAT_K[name]:.0f} K -> "
            f"CE_eff = {qe_eff:.2e} [-] (x{scale:.2f} vs published CE)"
        )
        print(
            f"{'  T':>6} {'raw-CE pred [mK]':>17} {'sat-CE pred [mK]':>17} "
            f"{'spec [mK]':>10} {'meas [mK]':>10}"
        )
        for scene_k, (spec_k, meas_k) in table.items():
            raw_lo, _, _ = _run_tirs(lo, hi, scene_k, TIRS_CE_PUB, TIRS_READ_LO)
            raw_hi, _, _ = _run_tirs(lo, hi, scene_k, TIRS_CE_PUB, TIRS_READ_HI)
            inv_lo, _, _ = _run_tirs(lo, hi, scene_k, qe_eff, TIRS_READ_LO)
            inv_hi, _, well = _run_tirs(lo, hi, scene_k, qe_eff, TIRS_READ_HI)
            print(
                f"{scene_k:>5.0f}K {1e3 * raw_lo:>7.1f}\u2013{1e3 * raw_hi:<8.1f} "
                f"{1e3 * inv_lo:>7.1f}\u2013{1e3 * inv_hi:<8.1f} "
                f"{1e3 * spec_k:>10.0f} {1e3 * meas_k:>10.0f}   (well {well:.0%})"
            )
    print(
        "\nRegime notes: photon/dark/read floor only — the published Jhabvala budget is\n"
        "dominated by blackbody/optics temperature-INSTABILITY terms (calibration\n"
        "stability), which are not detector noise and are not modeled; the prediction\n"
        "should therefore sit at or below the measured NEdT, and far below the 400 mK\n"
        "spec. Read-noise envelope: 260 e- (ROIC typical) to 1033 e- (with the 1000 e-\n"
        "electronics spec ceiling RSS'd)."
    )


# ============================ MODIS TEB (Aqua) ===============================
# Provenance: docs/validation/modis_teb_source_data.md. Two-part validation:
# (1) the published L_typ column is 300 K band-averaged Planck radiance — a free
#     published anchor set for RADIANT's spectral chain (band_planck_radiance);
# (2) NEdT: the photon/read floor is predicted and the implied detector noise
#     inverted from the measured NEdT (MODIS TEBs are detector-noise-limited).

MODIS_D_M = 0.1778  # m — published aperture
MODIS_TAU_LO, MODIS_TAU_HI = 0.30, 0.50  # — ASSUMPTION (calibration-LUT internal)
MODIS_QE = 0.7  # — ASSUMPTION (PV eta 0.6-0.8; PC treated identically for the floor)
MODIS_ALT_M = 705_000.0  # m — published

# name, lo_um, hi_um, L_typ [W/m2/sr/um], NEdT spec [K], NEdT measured [K],
# focal [m], pitch [um], t_int [s]
MODIS_BANDS = (
    ("B20", 3.660, 3.840, 0.45, 0.05, 0.02, 0.380859, 540.0, 323.333e-6),
    ("B29", 8.400, 8.700, 9.58, 0.05, 0.02, 0.282118, 400.0, 293.332e-6),
    ("B31", 10.780, 11.280, 9.55, 0.05, 0.02, 0.282118, 400.0, 323.333e-6),
    ("B32", 11.770, 12.270, 8.94, 0.05, 0.03, 0.282118, 400.0, 323.333e-6),
)


def _run_modis(lo, hi, focal_m, pitch_um, t_int_s, tau):
    """One MODIS band at a 300 K blackbody scene; returns (NEdT [K], dS/dT [e-/K])."""
    wl = np.linspace(lo, hi, 41)
    session = RadiantSession(wavelength_um=wl)
    params = session.default_params()
    params.set("source.target.temperature", 300.0)
    params.set("source.target.emissivity", 1.0)
    params.set("source.scene_type", "extended")
    params.set("atmosphere.model", "exo")
    params.set("geometry.sensor_altitude_m", MODIS_ALT_M)
    params.set("geometry.target_altitude_m", 0.0)
    params.set("optics.aperture_diameter_m", MODIS_D_M)
    params.set("optics.focal_length_m", focal_m)
    params.set("optics.transmission_scalar", tau)
    params.set("detector.pixel_pitch_x_um", pitch_um)
    params.set("detector.pixel_pitch_y_um", pitch_um)
    params.set("detector.qe_value", MODIS_QE)
    params.set("detector.dark_rate_e_per_s", 1.0e6)  # ASSUMPTION; sub-dominant
    params.set("spectral_integration.filter_min_um", float(wl[0]))
    params.set("spectral_integration.filter_max_um", float(wl[-1]))
    params.set("spectral_integration.integration_time_s", t_int_s)
    params.set("readout.read_noise_e_rms", 500.0)  # ASSUMPTION; sub-dominant
    # PC HgCdTe integrates photocurrent — no discrete charge well; RADIANT's
    # well schema (max 1e8 e-) cannot represent that (same representational gap
    # as Gap 101's bolometers), so the floor is computed from the pre-readout
    # spectral_integration signal below rather than the well-clipped readout.
    params.set("readout.full_well_capacity_e", 1.0e8)
    params.set("readout.adc_bits", 12)
    params.set("readout.gain_e_per_dn", 1.0e8 / 2**12)
    params.resolve()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        result = session.run(params)
    ds_dt = float(result.stage_outputs["spectral_integration"]["ds_dt_e_per_K"])
    sig_e = float(result.stage_outputs["spectral_integration"]["signal_e"])
    dark_e = 1.0e6 * t_int_s
    sigma_floor = float(np.sqrt(sig_e + dark_e + 500.0**2))
    return sigma_floor / ds_dt, ds_dt


def modis_main() -> None:
    from radiant.performance.temperature_retrieval import band_planck_radiance

    print("\nMODIS TEB (Aqua) — spectral-chain anchors + NEdT floor vs published")
    print("(300 K blackbody, exo path; see docs/validation/modis_teb_source_data.md)\n")
    print("Part 1 — published L_typ vs RADIANT 300 K band-averaged Planck radiance:")
    print(f"{'band':<5} {'L_typ pub':>10} {'RADIANT':>9} {'diff':>7}   [W/m²/sr/µm]")
    for name, lo, hi, l_typ, *_ in MODIS_BANDS:
        l_rad = band_planck_radiance(300.0, np.linspace(lo, hi, 201)) / (hi - lo)
        print(f"{name:<5} {l_typ:>10.2f} {l_rad:>9.3f} {(l_rad / l_typ - 1):>+7.1%}")
    print(
        "\nPart 2 — NEdT: photon/read floor (tau 0.30-0.50) vs spec and measured;"
        "\nimplied detector noise = dS/dT x NEdT_meas (the named unknown):"
    )
    print(
        f"{'band':<5} {'floor [mK]':>12} {'spec [mK]':>10} {'meas [mK]':>10} "
        f"{'impl sigma_det [e-]':>20}"
    )
    for name, lo, hi, _l, spec_k, meas_k, focal, pitch, t_int in MODIS_BANDS:
        n_lo, ds_dt = _run_modis(lo, hi, focal, pitch, t_int, MODIS_TAU_HI)
        n_hi, _ = _run_modis(lo, hi, focal, pitch, t_int, MODIS_TAU_LO)
        sigma_det = ds_dt * meas_k
        print(
            f"{name:<5} {1e3 * n_lo:>5.2f}\u2013{1e3 * n_hi:<6.2f} "
            f"{1e3 * spec_k:>10.0f} {1e3 * meas_k:>10.0f} {sigma_det:>20.3g}"
        )
    print(
        "\nRegime notes: MODIS TEBs are detector/system-noise limited (PC HgCdTe G-R/1/f;"
        "\nPV crosstalk) — the measured 20-30 mK sits ~10-40x above the photon floor, so"
        "\nthe floor is a BOUND, not a prediction; the implied detector-noise column is"
        "\nthe quantity a detector model must reproduce. Part 1 is the direct spectral-"
        "\nchain validation: four independent published Planck anchors."
    )


if __name__ == "__main__":
    main()
    tirs_main()
    modis_main()
