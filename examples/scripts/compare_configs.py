#!/usr/bin/env python3
"""Compare configs — evaluate two configurations, diff the metrics.

Usage::

    python examples/scripts/compare_configs.py
"""

from __future__ import annotations

from pathlib import Path

from radiant.api.sensor import Sensor

CONFIG = Path(__file__).resolve().parent.parent / "mwir_leo_minimal.yaml"


def main() -> None:
    # Baseline configuration
    baseline = Sensor.from_yaml(CONFIG)
    baseline_result = baseline.evaluate()

    # Modified configuration: larger aperture, longer integration
    modified = baseline.clone()
    modified.set("optics.aperture_diameter_m", 0.45)
    modified.set("spectral_integration.integration_time_s", 0.010)
    modified_result = modified.evaluate()

    # Compare metrics
    print("=== Configuration Comparison ===")
    print()
    print(f"{'Metric':>20s}  {'Baseline':>12s}  {'Modified':>12s}  {'Delta':>12s}  {'%Change':>10s}")
    print("-" * 70)

    all_metrics = sorted(
        set(baseline_result.metrics.keys()) | set(modified_result.metrics.keys())
    )
    for name in all_metrics:
        v_base = baseline_result.metrics.get(name, float("nan"))
        v_mod = modified_result.metrics.get(name, float("nan"))
        delta = v_mod - v_base
        pct = (delta / v_base * 100.0) if v_base != 0.0 else float("nan")
        print(f"{name:>20s}  {v_base:12.4f}  {v_mod:12.4f}  {delta:+12.4f}  {pct:+9.1f}%")

    print()
    print("Changes applied:")
    print("  optics.aperture_diameter_m: 0.30 → 0.45 m")
    print("  spectral_integration.integration_time_s: 0.005 → 0.010 s")


if __name__ == "__main__":
    main()
