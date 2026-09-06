"""Scenario 2.7: Up/Down Counting — In-Pixel Background Subtraction Trade.

The plan §2.4 use case made workflow-visible: a dim 500 K point source over
a bright common background on a 14-bit DROIC. `up` counting spends the
counter range on the pedestal (background + dark fill the effective well and
eventually saturate it); `up_down` subtracts a reference phase in-pixel, so
the signed range is spent on the target — at the price of the reference
phase's own shot noise (up to sqrt(2) on the background terms) and a second
counting-chain read.

  1. Reads Mike's spec sheet (cm, nm, km, ke-, ms) and converts (Rule 2)
  2. Sweeps background temperature under counting_mode = up and up_down
  3. Compares well fill / mechanism, SNR, and the top noise terms
  4. Writes outputs/updown_trade_results.csv

Usage:
    python run_updown_trade.py
"""

from __future__ import annotations

import csv
import warnings
from pathlib import Path
from typing import Any

import yaml

from radiant.api import Sensor

_HERE = Path(__file__).resolve().parent
INPUT_FILE = _HERE.parent / "inputs" / "mike_updown_specs.yaml"
OUTPUT_FILE = _HERE.parent / "outputs" / "updown_trade_results.csv"

spec = yaml.safe_load(INPUT_FILE.read_text(encoding="utf-8"))
sys_s, tgt, bg, fpa, droic = (
    spec["system"],
    spec["target"],
    spec["background"],
    spec["fpa"],
    spec["droic"],
)
study = spec["study"]

# ---- Unit conversion at the boundary (Rule 2) ----
aperture_m = sys_s["aperture_diameter_cm"] / 100.0  # cm -> m
focal_m = sys_s["focal_length_cm"] / 100.0  # cm -> m
transmission = sys_s["optical_transmission_pct"] / 100.0  # % -> fraction
band_min_um = sys_s["filter_cut_on_nm"] / 1000.0  # nm -> um
band_max_um = sys_s["filter_cut_off_nm"] / 1000.0  # nm -> um
alt_m = sys_s["sensor_altitude_km"] * 1000.0  # km -> m
range_m = sys_s["target_range_km"] * 1000.0  # km -> m
qe = fpa["quantum_efficiency_pct"] / 100.0  # % -> fraction
packet_e = droic["charge_packet_ke"] * 1000.0  # ke- -> e-
t_int_s = study["integration_time_ms"] / 1000.0  # ms -> s

_N = droic["counter_depth_bits"]
EFFECTIVE_WELL_E = (1 << _N) * packet_e  # up-mode bound [e-]
SIGNED_CAPACITY_E = (1 << (_N - 1)) * packet_e  # up_down bound [e-]


def make_config(bg_temp_K: float, counting_mode: str) -> dict[str, Any]:
    readout: dict[str, Any] = {
        "architecture": "digital_counting",
        "counter_bits": _N,
        "count_packet_e": packet_e,
        "residue_readout": droic["residue_readout"],
        "adc_bits": droic["residue_adc_bits"],
        "read_noise_e_rms": droic["counting_chain_noise_e_rms"],
    }
    if counting_mode == "up_down":
        # background_term reference (ruling D6) — the point-source chain
        # carries a separate background term; equal phases (D7 default).
        readout["counting_mode"] = "up_down"
    return {
        "source": {
            "target": {"temperature": tgt["temperature_K"], "emissivity": tgt["emissivity"]},
            "background": {"temperature": bg_temp_K, "emissivity": bg["emissivity"]},
            "regime_override": "point_source",
        },
        "geometry": {
            "sensor_altitude_m": alt_m,
            "target_range_m": range_m,
            "target": {"projected_area_m2": tgt["projected_area_m2"]},
        },
        "atmosphere": {"standard_atmosphere": sys_s["standard_atmosphere"]},
        "optics": {
            "aperture_diameter_m": aperture_m,
            "focal_length_m": focal_m,
            "transmission_scalar": transmission,
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


def evaluate(bg_temp_K: float, counting_mode: str) -> dict[str, Any]:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")  # clip warnings summarized in the table
        result = Sensor.from_dict(make_config(bg_temp_K, counting_mode)).evaluate()
    ro = result.stage_outputs["readout"]
    terms = ro["scaled_noise_terms"]
    top = sorted(terms.items(), key=lambda kv: kv[1], reverse=True)[:2]
    return {
        "counting_mode": counting_mode,
        "bg_temp_K": bg_temp_K,
        "well_bound_e": ro["full_well_capacity_e"],
        "well_fill_pct": 100.0 * ro["well_fill_fraction"],
        "well_status": ro["well_status"],
        "mechanism": ro["saturation_mechanism"],
        "snr": result.metrics.get("snr", float("nan")),
        "sigma_total_e": ro["sigma_total_e"],
        "differential_e": ro.get("differential_e"),
        "top_terms": "; ".join(f"{k}={v:.0f} e-" for k, v in top),
    }


def main() -> None:
    print("=" * 92)
    print("SCENARIO 2.7: Up/Down Counting — dim 500 K point source over a bright background")
    print("=" * 92)
    print(
        f"\nSystem: {aperture_m * 100:.0f} cm f/{focal_m / aperture_m:.1f} MWIR "
        f"{band_min_um:.1f}-{band_max_um:.1f} um, target {tgt['temperature_K']:.0f} K "
        f"{tgt['projected_area_m2']:.2f} m^2 at {range_m / 1000:.0f} km, "
        f"t_int = {t_int_s * 1000:.0f} ms (phases equal, ruling D7)"
    )
    print(
        f"DROIC: 2^{_N} x {packet_e:.0f} e-/count = {EFFECTIVE_WELL_E / 1e6:.2f} Me- "
        f"up-mode well; signed up/down capacity 2^{_N - 1} x {packet_e:.0f} e- = "
        f"{SIGNED_CAPACITY_E / 1e6:.2f} Me-; counting-chain noise "
        f"{droic['counting_chain_noise_e_rms']:.0f} e- RMS per phase"
    )

    rows = [
        evaluate(temp_K, mode)
        for temp_K in bg["temperatures_K"]
        for mode in ("up", "up_down")
    ]

    header = (
        f"\n{'T_bg':>7} | {'mode':<8} | {'bound':>10} | {'fill':>7} | {'status':>22} | "
        f"{'SNR':>8} | {'sigma':>8} | top noise terms"
    )
    units = (
        f"{'[K]':>7} | {'':<8} | {'[e-]':>10} | {'[%]':>7} | {'':>22} | "
        f"{'[-]':>8} | {'[e-]':>8} | [e- RMS]"
    )
    print(header)
    print(units)
    print("-" * 110)
    for r in rows:
        status = "ok" if r["well_status"] == "ok" else f"SAT ({r['mechanism']})"
        print(
            f"{r['bg_temp_K']:7.0f} | {r['counting_mode']:<8} | {r['well_bound_e']:10.3g} | "
            f"{r['well_fill_pct']:7.1f} | {status:>22} | {r['snr']:8.1f} | "
            f"{r['sigma_total_e']:8.1f} | {r['top_terms']}"
        )

    print(
        "\nPhysics notes:\n"
        "  - Regime: point_source (forced via source.regime_override) — the chain "
        "carries the\n    target excess and the background pedestal as separate "
        "terms, which is what makes\n    reference_source = 'background_term' "
        "available (ruling D6).\n"
        "  - 'up' well fill counts the WHOLE pedestal (background + dark + target) "
        "against\n    2^N x Q_pkt [e-]; 'up_down' fill counts only |dQ| = "
        "|Q_up - Q_down| [e-] against the\n    signed 2^(N-1) x Q_pkt [e-] — the "
        "pedestal is subtracted in-pixel before readout.\n"
        "  - The price (plan §2.4): the reference phase's own Poisson noise "
        "(reference_shot =\n    sqrt(Q_down) [e- RMS], up to sqrt(2) on the "
        "background terms), a doubled packet-reset\n    accumulation, and the "
        "counting-chain read paid once per phase (x sqrt(2)).\n"
        "  - The SNR numerator is the target signal in e- in BOTH modes (plan "
        "§2.4 'Metrics');\n    the modes differ in noise and in which saturation "
        "bound governs.\n"
        "  - Unused here: readout.max_count_rate_hz (0.0 = no dead-time ceiling), "
        "analog\n    gain/full-well (rejected under counting), "
        "reference_rate_e_per_s (background_term\n    reference integrates the "
        "chain's own background)."
    )

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_FILE.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    print(f"\nWrote {OUTPUT_FILE.name}")


if __name__ == "__main__":
    main()
