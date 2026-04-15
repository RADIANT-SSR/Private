#!/usr/bin/env python3
"""Custom loop — manual parameter sweep with custom post-processing.

Demonstrates using Sensor.clone() + set() + evaluate() in a manual
loop, extracting and post-processing results outside the built-in
sweep API.

Usage::

    python examples/scripts/custom_loop.py
"""

from __future__ import annotations

import math
from pathlib import Path

from radiant.api.sensor import Sensor

CONFIG = Path(__file__).resolve().parent.parent / "mwir_leo_minimal.yaml"


def main() -> None:
    base = Sensor.from_yaml(CONFIG)

    # Custom sweep: vary integration time and report SNR,
    # plus a derived "time-normalized SNR" metric.
    t_int_values = [0.001, 0.002, 0.005, 0.010, 0.020, 0.050]

    print("=== Custom Loop: Integration Time Analysis ===")
    print()
    print(f"{'t_int (ms)':>12s}  {'SNR':>10s}  {'SNR/√t':>10s}  {'NEDT (K)':>10s}")
    print("-" * 46)

    for t_int in t_int_values:
        s = base.clone()
        s.set("spectral_integration.integration_time_s", t_int)
        result = s.evaluate()

        snr = result.metrics["snr"]
        nedt_val = result.metrics.get("nedt")
        nedt = float(nedt_val) if nedt_val is not None else float("nan")

        # Time-normalized SNR: SNR / sqrt(t_int) — useful for comparing
        # detector performance independent of integration time.
        snr_norm = snr / math.sqrt(t_int)

        print(f"{t_int * 1000:12.1f}  {snr:10.2f}  {snr_norm:10.2f}  {nedt:10.6f}")

    print()
    print("SNR/√t should be approximately constant if the system is")
    print("photon-noise-limited (shot noise ∝ √signal ∝ √t_int).")


if __name__ == "__main__":
    main()
