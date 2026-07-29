#!/usr/bin/env python
"""Update golden regression values.

Usage::

    python scripts/update_golden.py --i-know-what-im-doing

This script re-runs the MWIR LEO minimal chain and overwrites the
golden JSON file. It logs every value that changed.

NEVER run this without understanding WHY values changed. The golden
file is a regression anchor — updating it silently defeats its purpose.
"""

from __future__ import annotations

import json
import math
import sys
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

# Ensure the project is importable.
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from radiant.api.session import RadiantSession  # noqa: E402
from radiant.io.config import load_config  # noqa: E402

GOLDEN_PATH = ROOT / "tests" / "integration" / "golden" / "mwir_leo_minimal.json"
CONFIG_PATH = ROOT / "examples" / "mwir_leo_minimal.yaml"


def main() -> None:
    if "--i-know-what-im-doing" not in sys.argv:
        print(
            "ERROR: Golden values are regression anchors.\n"
            "       To update them, pass: --i-know-what-im-doing\n"
            "       Only do this after verifying the new values are correct.",
            file=sys.stderr,
        )
        sys.exit(1)

    # Load old golden values (if they exist).
    old: dict = {}
    if GOLDEN_PATH.exists():
        with open(GOLDEN_PATH, encoding="utf-8") as f:
            old = json.load(f)

    # Run the chain.
    wl = np.linspace(3.5, 5.0, 500)
    session = RadiantSession(wavelength_um=wl)
    params = session.default_params()
    load_config(CONFIG_PATH, params)
    params.resolve()
    r = session.run(params)

    pe = r.frames["photoelectrons"].in_band_value
    noise = {n.name: n.value_e for n in r.noise_terms}
    noise_rss = math.sqrt(sum(v**2 for v in noise.values()))
    snr = r.metrics["snr"]
    e_rate = r.stage_outputs["spectral_integration"]["e_rate_per_s"]
    A = r.stage_outputs["optics"]["A_collect"]
    omega = r.stage_outputs["optics"]["Omega_pixel"]

    new_values = {
        "signal_e": pe,
        "e_rate_per_s": e_rate,
        "A_collect": A,
        "Omega_pixel": omega,
        "noise_shot": noise["signal_shot"],
        "noise_dark_shot": noise["dark_shot"],
        "noise_read": noise["read_noise"],
        "noise_quantization": noise["quantization"],
        "noise_rss": noise_rss,
        "snr": snr,
    }

    # Compare and log changes.
    timestamp = datetime.now(UTC).isoformat()
    changes: list[str] = []
    for key, new_val in new_values.items():
        if key in old and isinstance(old[key], dict):
            old_val = old[key].get("value")
            if old_val is not None and old_val != new_val:
                rel = abs(new_val - old_val) / abs(old_val) if old_val != 0 else float("inf")
                changes.append(f"  {key}: {old_val} -> {new_val}  (rel change: {rel:.2e})")

    if changes:
        print(f"CHANGES detected at {timestamp}:")
        for c in changes:
            print(c)
    else:
        print(f"No changes detected at {timestamp}.")

    # Read old file to preserve provenance comments, then update values.
    if GOLDEN_PATH.exists():
        with open(GOLDEN_PATH, encoding="utf-8") as f:
            golden = json.load(f)
    else:
        golden = {}

    for key, new_val in new_values.items():
        if key in golden and isinstance(golden[key], dict):
            golden[key]["value"] = new_val
        else:
            golden[key] = {"value": new_val, "unit": "see code", "provenance": "auto-generated"}

    golden["_provenance"]["generated_by"] = "scripts/update_golden.py"
    golden["_provenance"]["last_updated"] = timestamp

    GOLDEN_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(GOLDEN_PATH, "w", encoding="utf-8") as f:
        json.dump(golden, f, indent=2)
        f.write("\n")

    print(f"Golden file written: {GOLDEN_PATH}")


if __name__ == "__main__":
    main()
