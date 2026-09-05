"""Scenario 2.6: DROIC vs Analog ROIC — single-frame HDR on the 2.5 system.

Scenario 2.5 ended with a physical wall: Mike's 200-1500 K scene cannot fit
in one frame through a 2 Me- analog charge well at any integration time.
This scenario puts the SAME MWIR FPA behind a Senseeker-class digital-pixel
ROIC (readout.architecture = "digital_counting", Gap 117) and re-runs the
scene-temperature sweep at the 1 ms cold-target working point:

  1. Reads Mike's vendor-style spec sheet (cm, %, nm, ke-, MHz)
  2. Converts to RADIANT canonical units at the boundary (Rule 2)
  3. Evaluates every scene temperature under both ROICs
  4. Compares well fill / saturation, SNR, NEDT, and dynamic range [dB]
  5. Writes outputs/droic_vs_analog_results.csv

Usage:
    python run_droic_vs_analog.py
"""

from __future__ import annotations

import csv
import warnings
from pathlib import Path
from typing import Any

import yaml

from radiant.api import Sensor

_HERE = Path(__file__).resolve().parent
INPUT_FILE = _HERE.parent / "inputs" / "mike_droic_specs.yaml"
OUTPUT_FILE = _HERE.parent / "outputs" / "droic_vs_analog_results.csv"

spec = yaml.safe_load(INPUT_FILE.read_text(encoding="utf-8"))
sys_s, fpa, analog, droic = spec["system"], spec["fpa"], spec["analog_roic"], spec["droic"]
study = spec["study"]

# ---- Unit conversion at the boundary (Rule 2) ----
aperture_m = sys_s["aperture_diameter_cm"] / 100.0  # cm -> m
focal_m = sys_s["focal_length_cm"] / 100.0  # cm -> m
transmission = sys_s["optical_transmission_pct"] / 100.0  # % -> fraction
optics_K = sys_s["optics_temperature_C"] + 273.15  # C -> K
band_min_um = sys_s["filter_cut_on_nm"] / 1000.0  # nm -> um
band_max_um = sys_s["filter_cut_off_nm"] / 1000.0  # nm -> um
qe = fpa["quantum_efficiency_pct"] / 100.0  # % -> fraction
fwc_e = analog["full_well_capacity_Me"] * 1.0e6  # Me- -> e-
packet_e = droic["charge_packet_ke"] * 1000.0  # ke- -> e-
f_max_hz = droic["max_count_rate_MHz"] * 1.0e6  # MHz -> Hz
t_int_s = study["integration_time_ms"] / 1000.0  # ms -> s


def make_config(target_temp_K: float, architecture: str) -> dict[str, Any]:
    """RADIANT config for one scene temperature under one ROIC."""
    readout: dict[str, Any] = {
        "read_noise_e_rms": (
            analog["read_noise_e_rms"]
            if architecture == "analog_well"
            else droic["counting_chain_noise_e_rms"]  # same value; ruling D3 reuse
        ),
    }
    if architecture == "analog_well":
        readout.update(
            {
                "gain_e_per_dn": analog["system_gain_e_per_dn"],
                "adc_bits": analog["adc_resolution_bits"],
                "full_well_capacity_e": fwc_e,
            }
        )
    else:
        readout.update(
            {
                "architecture": "digital_counting",
                "counter_bits": droic["counter_depth_bits"],
                "count_packet_e": packet_e,
                "residue_readout": droic["residue_readout"],
                "max_count_rate_hz": f_max_hz,
                "adc_bits": droic["residue_adc_bits"],
                # full_well_capacity_e deliberately NOT set: the effective
                # well is 2^N x Q_pkt and an explicit FWC is rejected.
            }
        )
    return {
        "source": {
            "target": {"temperature": target_temp_K, "emissivity": sys_s["target_emissivity"]},
            "background": {
                "temperature": sys_s["background_temperature_K"],
                "emissivity": sys_s["background_emissivity"],
            },
        },
        "atmosphere": {"model": "exo"},
        "geometry": {"sensor_altitude_m": 0.0},
        # Stage-7 stop-gap (registry Gap 42), same as scenario 2.5: "exo"
        # routes through the no_atmosphere 'space' sub-case whose Earth-limb
        # check needs a positive platform.h_sensor; 1.0 m = bench height,
        # feeds only the limb check, no radiometric effect.
        "platform": {"h_sensor": 1.0},
        "optics": {
            "aperture_diameter_m": aperture_m,
            "focal_length_m": focal_m,
            "transmission_scalar": transmission,
            "optics_temperature_K": optics_K,
        },
        "detector": {
            "pixel_pitch_x_um": fpa["pixel_pitch_um"],
            "pixel_pitch_y_um": fpa["pixel_pitch_um"],
            "qe_value": qe,
            "dark_rate_e_per_s": fpa["dark_current_e_per_s"],
            "detector_temperature_K": fpa["operating_temperature_K"],
        },
        "spectral_integration": {
            "filter_min_um": band_min_um,
            "filter_max_um": band_max_um,
            "integration_time_s": t_int_s,
        },
        "readout": readout,
    }


def evaluate(target_temp_K: float, architecture: str) -> dict[str, Any]:
    """Evaluate one configuration; saturation warnings become row data."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")  # clip warnings summarized in the table
        result = Sensor.from_dict(make_config(target_temp_K, architecture)).evaluate()
    ro = result.stage_outputs["readout"]
    return {
        "architecture": architecture,
        "scene_temp_K": target_temp_K,
        "well_bound_e": ro["full_well_capacity_e"],
        "well_fill_pct": 100.0 * ro["well_fill_fraction"],
        "well_status": ro["well_status"],
        "saturation_mechanism": ro.get("saturation_mechanism", "charge_well"),
        "snr": result.metrics.get("snr", float("nan")),
        "nedt_mK": 1000.0 * result.metrics["nedt_K"] if "nedt_K" in result.metrics else None,
        "dynamic_range_dB": result.metrics.get("dynamic_range_dB", float("nan")),
        "sigma_total_e": ro["sigma_total_e"],
    }


def main() -> None:
    print("=" * 88)
    print("SCENARIO 2.6: DROIC vs Analog ROIC — single-frame HDR (same FPA, same optics)")
    print("=" * 88)
    print(
        f"\nSystem: {aperture_m * 100:.0f} cm aperture, f/{focal_m / aperture_m:.1f}, "
        f"{band_min_um:.1f}-{band_max_um:.1f} um MWIR, QE {qe * 100:.0f} %, "
        f"{fpa['pixel_pitch_um']:.0f} um pitch, t_int = {t_int_s * 1000:.1f} ms"
    )
    print(
        f"Analog ROIC : {fwc_e / 1e6:.1f} Me- well, {analog['adc_resolution_bits']}-bit ADC "
        f"at {analog['system_gain_e_per_dn']:.0f} e-/DN, "
        f"read noise {analog['read_noise_e_rms']:.0f} e- RMS"
    )
    eff_well_e = (1 << droic["counter_depth_bits"]) * packet_e
    dead_ceiling_e = f_max_hz * t_int_s * packet_e
    print(
        f"DROIC       : 2^{droic['counter_depth_bits']} x {packet_e:.0f} e-/count = "
        f"{eff_well_e / 1e6:.1f} Me- effective well; dead-time ceiling "
        f"{f_max_hz / 1e6:.0f} MHz x {t_int_s * 1000:.1f} ms x {packet_e:.0f} e- = "
        f"{dead_ceiling_e / 1e6:.1f} Me- (governs: "
        f"{'dead_time' if dead_ceiling_e < eff_well_e else 'rollover'}); "
        f"residue ADC {droic['residue_adc_bits']} bits, counting-chain noise "
        f"{droic['counting_chain_noise_e_rms']:.0f} e- RMS"
    )

    rows = [
        evaluate(temp_K, arch)
        for temp_K in study["scene_temperatures_K"]
        for arch in ("analog_well", "digital_counting")
    ]

    header = (
        f"\n{'T_scene':>9} | {'ROIC':<16} | {'well bound':>12} | {'fill':>7} | "
        f"{'status':>8} | {'SNR':>9} | {'NEDT':>9} | {'DR':>8}"
    )
    units = (
        f"{'[K]':>9} | {'':<16} | {'[e-]':>12} | {'[%]':>7} | "
        f"{'':>8} | {'[-]':>9} | {'[mK]':>9} | {'[dB]':>8}"
    )
    print(header)
    print(units)
    print("-" * len(header))
    for r in rows:
        nedt = f"{r['nedt_mK']:9.2f}" if r["nedt_mK"] is not None else f"{'—':>9}"
        status = r["well_status"] if r["well_status"] == "ok" else "SAT"
        mech = f" ({r['saturation_mechanism']})" if status == "SAT" else ""
        print(
            f"{r['scene_temp_K']:9.0f} | {r['architecture']:<16} | {r['well_bound_e']:12.4g} | "
            f"{r['well_fill_pct']:7.1f} | {status + mech:>8} | {r['snr']:9.1f} | "
            f"{nedt} | {r['dynamic_range_dB']:8.1f}"
        )

    print(
        "\nPhysics notes:\n"
        "  - Regime: extended scene (target fills the pixel), so `snr` is the "
        "whole-pixel signal SNR\n    and NEDT is the differential temperature "
        "resolution at the scene temperature.\n"
        "  - Both ROICs see identical photocurrent [e-/s]: photon collection, QE "
        "[-], and dark rate\n    [e-/s] are upstream of the readout dispatch — "
        "only charge-to-number conversion differs.\n"
        "  - Analog saturation clips at the 2 Me- charge well. DROIC saturation "
        "clips at\n    min(2^N x Q_pkt, f_max x t_int x Q_pkt) [e-]; at this "
        "working point the dead-time\n    ceiling (22.5 Me-) governs, not counter "
        "rollover (294.9 Me-).\n"
        "  - The analog ADC parameters (gain [e-/DN], bits) are UNUSED under "
        "digital_counting;\n    adc_bits is reinterpreted as the residue-ADC "
        "depth (full scale = one packet, D2).\n"
        "  - read_noise_e_rms [e- RMS] is reused as the per-frame counting-chain "
        "noise (D3).\n"
        "  - DROIC quantization: residue ADC step = "
        f"{packet_e:.0f} e- / 2^{droic['residue_adc_bits']} = "
        f"{packet_e / (1 << droic['residue_adc_bits']):.3f} e-/DN -> "
        f"{packet_e / (1 << droic['residue_adc_bits']) / 3.4641:.3f} e- RMS —\n"
        "    negligible against the counting-chain floor; without residue "
        f"readout it would be\n    {packet_e:.0f}/sqrt(12) = "
        f"{packet_e / 3.4641:.0f} e- RMS and dominate cold-scene noise.\n"
    )

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_FILE.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {OUTPUT_FILE.relative_to(_HERE.parent.parent.parent.parent)}")


if __name__ == "__main__":
    main()
