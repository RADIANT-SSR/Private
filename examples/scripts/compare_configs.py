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
    # 91 columns: the manual quotes this table verbatim at text width.
    header = f"{'Metric':>27s}  {'Unit':<13s}  {'Baseline':>11s}  {'Modified':>11s}  {'Delta':>11s}"
    print(header + f"  {'%Change':>7s}")
    print("-" * 91)

    # metric_records() carries each metric's registered unit — a table of bare
    # numbers would violate the units-on-all-outputs rule.
    units = {rec.name: rec.unit for rec in baseline_result.metric_records()}
    units.update({rec.name: rec.unit for rec in modified_result.metric_records()})
    all_metrics = sorted(set(baseline_result.metrics.keys()) | set(modified_result.metrics.keys()))
    for name in all_metrics:
        v_base = baseline_result.metrics.get(name, float("nan"))
        v_mod = modified_result.metrics.get(name, float("nan"))
        delta = v_mod - v_base
        # A zero baseline has no percentage change: say so rather than print nan.
        pct_text = f"{delta / v_base * 100.0:+6.1f}%" if v_base != 0.0 else "    n/a"
        unit = units.get(name, "")
        print(
            f"{name:>27s}  {unit:<13s}  {v_base:11.4f}  {v_mod:11.4f}  {delta:+11.4f}  {pct_text}"
        )

    print()
    print("Changes applied:")
    print("  optics.aperture_diameter_m: 0.30 → 0.45 m")
    print("  spectral_integration.integration_time_s: 0.005 → 0.010 s")


if __name__ == "__main__":
    main()
