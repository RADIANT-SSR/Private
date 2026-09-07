#!/usr/bin/env python3
"""Scenario 2.8 — real-part quick start: model a Teledyne GeoSnap-18 by name.

Loads the scenario config (whose ``fpa: geosnap-18`` key applies the bundled
library preset), reports what the preset supplied vs. what Mike pinned
explicitly, runs the chain, and prints the headline metrics — every number
with its unit, plus the regime and the physics worth knowing.
"""

from __future__ import annotations

import warnings
from pathlib import Path

from radiant.api.sensor import Sensor

CONFIG = Path(__file__).resolve().parents[1] / "inputs" / "geosnap18_mwir_leo.yaml"


def main() -> None:
    sensor = Sensor.from_yaml(CONFIG)

    report = sensor.fpa_applications[0]
    print("=== FPA preset application (Gap 119) ===")
    print(f"Part: {report.part}")
    print(f"Preset supplied {len(report.applied)} parameter(s):")
    for dotpath in report.applied:
        rv_source = "preset"
        print(f"  {dotpath}  [{rv_source}]")
    if report.skipped_existing:
        print("Explicit config values won over the preset for:")
        for dotpath in report.skipped_existing:
            print(f"  {dotpath}")
    else:
        print("No overrides: the config pinned nothing the preset carries.")

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")  # NIIRS extrapolation warning, unrelated here
        result = sensor.evaluate()

    ro = result.stage_outputs["readout"]
    regime = result.stage_outputs["optics"]["regime"]
    print()
    print("=== Chain result ===")
    print(f"Radiometric regime: {regime} (300 K scene fills the 18 um pixel at 8 km —")
    print("  extended-scene: per-pixel signal, no EE_box coupling applies)")
    print(f"Readout architecture: {ro['architecture']} (CTIA + on-chip 14-bit ADC —")
    print("  GeoSnap is a digital-interface FPA, NOT an in-pixel counter; see preset notes)")
    print(f"SNR: {result.metrics['snr']:.1f} (dimensionless)")
    if "nedt" in result.metrics:
        print(f"NEDT: {result.metrics['nedt'] * 1000.0:.2f} mK")
    print()
    print("Physics notes:")
    print("  - The preset's 400 e- RMS read noise is the vendor's ROIC-only figure for")
    print("    the 2.6 Me- well; the measured LW science device shows 360 e- RMS system")
    print("    noise (Bowens 2024) - within 10 % of the entry used here.")
    print("  - Dark rate 5.0e4 e-/s is Mike's explicit programme estimate (units: e-/s);")
    print("    the preset ships none because dark is cutoff- and temperature-dependent.")
    print("  - At 5 ms and 300 K the signal is background-shot-dominated; the 2.6 Me-")
    print("    well is the binding capacity, not the 14-bit ADC.")


if __name__ == "__main__":
    main()
