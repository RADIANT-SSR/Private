#!/usr/bin/env python3
"""Scenario 6.1 — benchmark RADIANT against a published detector datasheet.

Dr. Chen has a published cooled-LWIR HgCdTe FPA datasheet (specific
detectivity D* and NETD at stated reference conditions). She configures
RADIANT to those conditions, runs the chain, and checks that the chain's
computed noise reproduces the published D* and NETD — validating RADIANT's
electron-domain noise model against the literature.

The bridge from the chain's electron-domain noise to the datasheet's
optical-power figures of merit is the new D*/NEP/NETD converter set:

    NEP = σ_e · h·c / (η·λ·t_int)          (electrons → optical power)
    D*  = √(A_d · Δf) / NEP                 (NEP → detectivity), Δf = 1/(2·t)

Every printed number carries units; the model, the reference conditions,
and the physics of any residual are explained inline (house rules).

Run from the repo root:
    python scenarios/06_dr_chen_researcher/6.1_published_snr_benchmark/scripts/run_datasheet_benchmark.py
"""

from __future__ import annotations

import warnings
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from radiant.api import Sensor
from radiant.performance.detectivity import dstar_from_nep, nep_from_dstar
from radiant.performance.nep_electrons import (
    integrating_bandwidth_hz,
    noise_electrons_from_nep,
    nep_from_noise_electrons,
)

warnings.filterwarnings("ignore")  # scenario-level noise suppression; physics still raises

HERE = Path(__file__).resolve().parent
SCEN = HERE.parent
OUTPUTS = SCEN / "outputs"
OUTPUTS.mkdir(exist_ok=True)

# --- Published datasheet (chen_lwir_datasheet.xlsx) -------------------
DSTAR_SPEC = 2.0e11  # cm·Hz^½/W (Jones)
NETD_SPEC_MK = 25.0  # mK
BAND = (8.0, 12.0)
PITCH_UM = 30.0
FNUM = 2.0
SCENE_TEMP_K = 300.0
T_INT_S = 30e-6
QE = 0.75
DARK_E_PER_S = 1.0e5
READ_NOISE_E = 60.0
FULL_WELL_E = 1.0e7
TRANSMISSION = 0.85
TOLERANCE_PCT = 15.0

LAMBDA_C_UM = 0.5 * (BAND[0] + BAND[1])
AREA_CM2 = (PITCH_UM * 1e-4) ** 2  # pixel area [cm²]
DELTA_F_HZ = integrating_bandwidth_hz(T_INT_S)


def build_sensor() -> Sensor:
    """LWIR FPA configured to the datasheet reference conditions."""
    aperture = 0.05
    focal = aperture * FNUM  # f/# = focal / aperture
    s = Sensor()
    s.set("source.scene_type", "extended")
    s.set("source.target.temperature", SCENE_TEMP_K, unit="K")
    s.set("source.target.emissivity", 0.98)
    s.set("atmosphere.model", "simple")
    s.set("atmosphere.standard_atmosphere", "us_standard")
    s.set("geometry.sensor_altitude_m", 1000.0)
    s.set("geometry.path_zenith_rad", 0.0)
    s.set("optics.aperture_diameter_m", aperture)
    s.set("optics.focal_length_m", focal)
    s.set("optics.transmission_scalar", TRANSMISSION)
    s.set("detector.pixel_pitch_x_um", PITCH_UM)
    s.set("detector.pixel_pitch_y_um", PITCH_UM)
    s.set("detector.qe_value", QE)
    s.set("detector.dark_rate_e_per_s", DARK_E_PER_S)
    s.set("detector.detector_temperature_K", 77.0)
    s.set("spectral_integration.filter_min_um", BAND[0])
    s.set("spectral_integration.filter_max_um", BAND[1])
    s.set("spectral_integration.integration_time_s", T_INT_S)
    s.set("readout.read_noise_e_rms", READ_NOISE_E)
    s.set("readout.gain_e_per_dn", 5.0)
    s.set("readout.adc_bits", 14)
    s.set("readout.full_well_capacity_e", FULL_WELL_E)
    return s


def main() -> None:
    print("=" * 74)
    print("SCENARIO 6.1 — PUBLISHED-DATASHEET BENCHMARK (D*/NETD)")
    print("=" * 74)
    print(
        f"Datasheet: cooled LWIR HgCdTe, D* = {DSTAR_SPEC:.2e} Jones, "
        f"NETD = {NETD_SPEC_MK:.0f} mK @ f/{FNUM:.0f}, {SCENE_TEMP_K:.0f} K, "
        f"{BAND[0]:.0f}–{BAND[1]:.0f} µm, {PITCH_UM:.0f} µm pixel."
    )
    print(
        f"Pixel area {AREA_CM2:.2e} cm², noise bandwidth Δf = 1/(2·t_int) = "
        f"{DELTA_F_HZ/1e3:.1f} kHz."
    )
    print()

    # --- Converter round-trip (sanity: the converters are self-inverse) ---
    nep_spec = nep_from_dstar(DSTAR_SPEC, AREA_CM2, DELTA_F_HZ)
    sigma_e_spec = noise_electrons_from_nep(nep_spec, QE, LAMBDA_C_UM, T_INT_S)
    print("-" * 74)
    print("DATASHEET D* → NEP → equivalent noise electrons (converter chain)")
    print("-" * 74)
    print(f"  NEP(D*)               = {nep_spec:.3e} W")
    print(f"  σ_e equivalent        = {sigma_e_spec:,.0f} e⁻ (total noise the D* implies)")
    print(
        "  (This is the TOTAL noise the datasheet D* implies at the reference "
        "bandwidth — for a BLIP LWIR detector it is dominated by photon shot "
        "noise, not read noise.)"
    )
    print()

    # --- Run the chain and derive its D* / NETD ------------------------
    r = build_sensor().evaluate()
    signal_e = r.stage_outputs["spectral_integration"]["signal_e"]
    snr = r.metrics["snr"]
    noise_e = signal_e / snr
    nedt_chain_mk = r.metrics["nedt_K"] * 1e3
    well_pct = r.stage_outputs["readout"]["signal_e_final"] / FULL_WELL_E * 100.0

    nep_chain = nep_from_noise_electrons(noise_e, QE, LAMBDA_C_UM, T_INT_S)
    dstar_chain = dstar_from_nep(nep_chain, AREA_CM2, DELTA_F_HZ)

    print("-" * 74)
    print("CHAIN RESULT → D* / NETD (via the converters)")
    print("-" * 74)
    print(f"  Signal                = {signal_e:.3e} e⁻   (well {well_pct:.0f}%)")
    print(f"  Total noise σ_e       = {noise_e:,.0f} e⁻   (√signal = {signal_e**0.5:,.0f} → BLIP)")
    print(f"  NEP(chain)            = {nep_chain:.3e} W")
    print(f"  D*(chain)             = {dstar_chain:.3e} Jones")
    print(f"  NETD(chain)           = {nedt_chain_mk:.2f} mK")
    print()

    # --- Benchmark comparison ------------------------------------------
    dstar_resid = (dstar_chain / DSTAR_SPEC - 1.0) * 100.0
    netd_resid = (nedt_chain_mk / NETD_SPEC_MK - 1.0) * 100.0
    dstar_ok = abs(dstar_resid) <= TOLERANCE_PCT
    netd_ok = abs(netd_resid) <= TOLERANCE_PCT

    print("-" * 74)
    print(f"BENCHMARK (tolerance ±{TOLERANCE_PCT:.0f}%)")
    print("-" * 74)
    print(f"{'Metric':<12}{'Datasheet':>14}{'Chain':>14}{'Residual':>12}{'Verdict':>10}")
    print(
        f"{'D* [Jones]':<12}{DSTAR_SPEC:>14.2e}{dstar_chain:>14.2e}"
        f"{dstar_resid:>+11.1f}%{'PASS' if dstar_ok else 'FAIL':>10}"
    )
    print(
        f"{'NETD [mK]':<12}{NETD_SPEC_MK:>14.1f}{nedt_chain_mk:>14.1f}"
        f"{netd_resid:>+11.1f}%{'PASS' if netd_ok else 'FAIL':>10}"
    )
    print(
        "\n  Interpretation: the chain is photon-shot- (BLIP-) limited (σ_e ≈ "
        "√signal), so its system D* reflects the background-limited detectivity "
        "at these conditions. Agreement within tolerance validates RADIANT's "
        "noise model against the published figure; a residual would flag a "
        "background-flux or QE mismatch versus the datasheet reference."
    )

    # ---------------------------------------------------------------
    # FIGURE 1 — datasheet vs chain for D* and NETD.
    # ---------------------------------------------------------------
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 5))
    ax1.bar(["Datasheet", "Chain"], [DSTAR_SPEC, dstar_chain], color=["#264478", "#2E75B6"])
    ax1.axhspan(
        DSTAR_SPEC * (1 - TOLERANCE_PCT / 100),
        DSTAR_SPEC * (1 + TOLERANCE_PCT / 100),
        color="green", alpha=0.12, label=f"±{TOLERANCE_PCT:.0f}% band",
    )
    ax1.set_ylabel("D* (Jones)")
    ax1.set_title(f"Specific detectivity (residual {dstar_resid:+.1f}%)")
    ax1.legend(fontsize=8)
    ax2.bar(["Datasheet", "Chain"], [NETD_SPEC_MK, nedt_chain_mk], color=["#264478", "#2E75B6"])
    ax2.axhspan(
        NETD_SPEC_MK * (1 - TOLERANCE_PCT / 100),
        NETD_SPEC_MK * (1 + TOLERANCE_PCT / 100),
        color="green", alpha=0.12,
    )
    ax2.set_ylabel("NETD (mK)")
    ax2.set_title(f"NETD (residual {netd_resid:+.1f}%)")
    fig.suptitle("Scenario 6.1 — RADIANT vs published LWIR datasheet", fontsize=12)
    fig.tight_layout()
    fig1 = OUTPUTS / "fig1_datasheet_benchmark.png"
    fig.savefig(fig1, dpi=130)
    plt.close(fig)
    print(f"\nWrote {fig1.name}")

    print()
    print("=" * 74)
    print("DONE — see outputs/ for the figure and MANIFEST.md.")
    print("=" * 74)


if __name__ == "__main__":
    main()
