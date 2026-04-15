#!/usr/bin/env python3
"""Tolerance analysis — Monte Carlo on 3 parameters, print stats.

Usage::

    python examples/scripts/tolerance_analysis.py
"""

from __future__ import annotations

from pathlib import Path

from radiant.api.sensor import Sensor

CONFIG = Path(__file__).resolve().parent.parent / "mwir_leo_minimal.yaml"


def main() -> None:
    sensor = Sensor.from_yaml(CONFIG)

    # Add tolerances to three parameters
    sensor.set_tolerance(
        "optics.aperture_diameter_m",
        "gaussian",
        std_fraction=0.02,  # 2% manufacturing tolerance
    )
    sensor.set_tolerance(
        "optics.transmission_scalar",
        "gaussian",
        std_fraction=0.05,  # 5% coating variation
    )
    sensor.set_tolerance(
        "detector.qe_value",
        "gaussian",
        std_fraction=0.03,  # 3% QE variation
    )

    # Run Monte Carlo with 50 trials (fast for demo)
    mc_result = sensor.monte_carlo(n_trials=50, seed=42)

    # Print statistics
    print("=== Monte Carlo Tolerance Analysis ===")
    print(f"Trials: {mc_result.n_trials}")
    print(f"Seed:   {mc_result.seed}")
    print()

    for metric in mc_result.metric_names:
        mean = mc_result.mean(metric)
        std = mc_result.std(metric)
        p5 = mc_result.percentile(metric, 5.0)
        p95 = mc_result.percentile(metric, 95.0)
        print(f"{metric}:")
        print(f"  Mean:  {mean:.4f}")
        print(f"  Std:   {std:.4f}")
        print(f"  5th %%: {p5:.4f}")
        print(f"  95th %%: {p95:.4f}")
        print()

    # Correlations with SNR
    if "snr" in mc_result.metric_names:
        print("Correlation with SNR:")
        corr = mc_result.correlation("snr")
        for param, r in sorted(corr.items(), key=lambda kv: abs(kv[1]), reverse=True):
            print(f"  {param:40s}  r = {r:+.4f}")


if __name__ == "__main__":
    main()
