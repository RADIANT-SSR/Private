#!/usr/bin/env python3
"""Aperture sweep — sweep aperture diameter and plot SNR vs D.

Usage::

    python examples/scripts/aperture_sweep.py

Produces: aperture_sweep_snr.png
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from radiant.api.plot import plot_sweep
from radiant.api.sensor import Sensor

CONFIG = Path(__file__).resolve().parent.parent / "mwir_leo_minimal.yaml"
OUTPUT = Path(__file__).resolve().parent / "aperture_sweep_snr.png"


def main() -> None:
    sensor = Sensor.from_yaml(CONFIG)

    # Sweep aperture diameter from 0.15 to 0.60 m
    apertures = np.linspace(0.15, 0.60, 10)
    result = sensor.sweep(
        "optics.aperture_diameter_m",
        apertures,
        metric="snr",
    )

    # Print results
    print("=== Aperture Sweep: SNR vs Aperture Diameter ===")
    print(f"{'D (m)':>10s}  {'SNR':>12s}")
    print("-" * 24)
    for d, snr in zip(result.values, result.metric_values):
        print(f"{d:10.3f}  {snr:12.2f}")

    # Save plot
    fig = plot_sweep(result)
    fig.savefig(OUTPUT, dpi=150)
    print(f"\nPlot saved to: {OUTPUT}")


if __name__ == "__main__":
    main()
