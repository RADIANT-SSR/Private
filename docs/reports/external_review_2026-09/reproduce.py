"""Reproduce the measurements in ``verification.md`` (external review 2026-09-30).

Point-in-time record (Rule 24). Run from the repo root::

    PYTHONPATH=./src python docs/reports/external_review_2026-09/reproduce.py

Written against ``v0.3.0-1-g8948dd43``. Once CU-380/CU-381 land, Finding 1's
case emits a warning and Finding 2's scaling changes — that is the point; this
script records what the engine did *before* the fixes.
"""

from __future__ import annotations

import math
import warnings
from pathlib import Path

import numpy as np

from radiant import Sensor
from radiant.readout.coadds import CoaddMode, coadd_scale_fpn, coadd_scale_temporal_noise

EXAMPLE = Path("examples/mwir_leo_minimal.yaml")


def finding_1() -> None:
    """Warm-optics nearfield is identically zero in scalar transmission mode."""
    print("=== Finding 1 — warm optics silently zero ===")
    sensor = Sensor.from_yaml(str(EXAMPLE))
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        result = sensor.evaluate()
        messages = [str(w.message) for w in caught]
    optics = result.stage_outputs["optics"]
    detector = result.stage_outputs["detector"]
    nearfield = optics["nearfield_irradiance_at_fpa"]
    print(f"  elements:                 {[(e.name, e.temperature_K) for e in optics['elements']]}")
    print(f"  nearfield irradiance sum: {float(np.sum(nearfield.values))} W/m^2/um")
    print(f"  nearfield_per_element:    {optics['nearfield_per_element']}")
    print(f"  detector.nearfield_e:     {detector['nearfield_e']} e-")
    print(f"  warnings raised:          {messages}")

    # The same net transmission, declared as two warm mirrors.
    reflectance = math.sqrt(0.70)
    warm = Sensor.from_yaml(str(EXAMPLE))
    warm.set_optical_elements(
        [
            {
                "name": name,
                "transfer_mode": "REFLECTIVE",
                "kind": "MIRROR",
                "reflectance": reflectance,
                "temperature_K": 290.0,
            }
            for name in ("primary", "secondary")
        ]
    )
    warm_result = warm.evaluate()
    snr_scalar = result.metrics["snr"]
    snr_warm = warm_result.metrics["snr"]
    print(f"  scalar:       nearfield_e = {detector['nearfield_e']:.5g} e-, SNR = {snr_scalar:.2f}")
    print(
        f"  290 K train:  nearfield_e = "
        f"{warm_result.stage_outputs['detector']['nearfield_e']:.5g} e-, SNR = {snr_warm:.2f}"
    )
    print(f"  SNR ratio (scalar / train): {snr_scalar / snr_warm:.4f}\n")


def finding_2() -> None:
    """Co-add scaling treats 1/f as uncorrelated."""
    print("=== Finding 2 — 1/f co-added as uncorrelated ===")
    for k in (1, 100, 500):
        temporal = coadd_scale_temporal_noise(1.0, k, CoaddMode.SUM)
        fpn = coadd_scale_fpn(1.0, k, CoaddMode.SUM)
        print(f"  K={k:4d}  temporal x{temporal:8.3f}   fpn x{fpn:8.1f}")
    print(f"  sqrt(500) = {math.sqrt(500)}\n")


if __name__ == "__main__":
    finding_1()
    finding_2()
