#!/usr/bin/env python3
"""Basic evaluation — load YAML config, evaluate, print metrics.

Usage::

    python examples/scripts/basic_evaluation.py
"""

from __future__ import annotations

from pathlib import Path

from radiant.api.sensor import Sensor

CONFIG = Path(__file__).resolve().parent.parent / "mwir_leo_minimal.yaml"


def main() -> None:
    # Load configuration
    sensor = Sensor.from_yaml(CONFIG)

    # Evaluate the signal chain
    result = sensor.evaluate()

    # Print metrics
    print("=== RADIANT Basic Evaluation ===")
    print(f"Config: {CONFIG.name}")
    print()
    for name, value in sorted(result.metrics.items()):
        print(f"  {name:20s} = {value:.6g}")

    # Print noise terms
    print()
    print("Noise budget:")
    for nt in result.noise_terms:
        print(f"  {nt.name:25s}  {nt.value_e:.4f} e- RMS")

    # Print stage history
    print()
    print(f"Stages executed: {' → '.join(result.history)}")


if __name__ == "__main__":
    main()
