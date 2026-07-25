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


if __name__ == "__main__":
    main()
