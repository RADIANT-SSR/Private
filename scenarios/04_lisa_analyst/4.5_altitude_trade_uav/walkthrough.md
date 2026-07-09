# Scenario 4.5 — Microbolometer UAV Altitude Trade (NETD-Specified)

**Persona:** Lisa, analyst planning a UAV thermal-ISR collection.
**Question:** With an uncooled microbolometer specified only by its NETD,
how high can the UAV fly and still detect a small warm ground target?

This scenario is the second consumer of the D*/NEP/NETD converter set
(`radiant.performance.detectivity`, `.nep_electrons`, `.nep_netd`): it
turns a **vendor NETD spec** — the way uncooled detectors are actually
quoted — into the optical-power figures (NEP, D*) and uses NETD as the
detection floor for an altitude trade.

---

## Inputs (vendor / mission format — non-RADIANT)

| File | Format | Represents |
|------|--------|-----------|
| `inputs/lisa_microbolometer_uav.xlsx` | Excel workbook (`UAV_IR` sheet) | Vendor microbolometer NETD spec, UAV optics, and the ground target |

`inputs/create_spreadsheet.py` regenerates it; values are transcribed into
the run script as constants for a self-contained, reproducible run.

---

## The physics of the ceiling

Two effects erode the target's apparent contrast as the UAV climbs:

1. **Sub-pixel dilution (dominant).** The ground pixel grows with altitude
   (`GSD = IFOV · altitude`). Once the fixed-size target is smaller than a
   pixel, it fills only `ff = (target / GSD)²` of it, so its apparent
   contrast is `ff · ΔT`. Since `GSD ∝ altitude`, `ff ∝ 1/altitude²` — a
   steep fall.
2. **Atmospheric attenuation (minor here).** The longer slant path
   transmits less contrast (`τ_atm` from the chain), but over 1–11 km it
   only drops 0.94 → 0.87.

Detection holds while `ff · ΔT · τ_atm ≥ threshold · NETD`. The
**detection ceiling** is the highest altitude satisfying it.

---

## Results (NETD 50 mK, 1 m target, ΔT 4 K, f/1, 486 µrad IFOV)

**Vendor NETD → optical-power figures (via the converters):**

| Quantity | Value |
|----------|-------|
| dP/dT (from the chain's dS/dT) | 1.42 × 10⁻¹⁰ W/K |
| NEP = NETD · dP/dT | 7.09 × 10⁻¹² W |
| **D\* = √(A·Δf)/NEP** | **1.34 × 10⁹ Jones** |

D\* ≈ 10⁹ Jones is the textbook value for an uncooled microbolometer —
about 100× below a cooled photon detector (scenario 6.1's 1.8 × 10¹¹). The
NETD spec is simply the practical way vendors carry that sensitivity.

**Altitude trade:**

| Altitude | GSD | Fill fraction | τ_atm | Apparent ΔT | Detect? |
|----------|-----|---------------|-------|-------------|---------|
| 1 km | 0.49 m | 1.000 | 0.944 | 3775 mK | yes |
| 3 km | 1.46 m | 0.471 | 0.895 | 1685 mK | yes |
| 5 km | 2.43 m | 0.170 | 0.878 | 595 mK | yes |
| 7 km | 3.40 m | 0.087 | 0.872 | 302 mK | yes |
| 9 km | 4.37 m | 0.052 | 0.870 | 182 mK | **no** |
| 11 km | 5.34 m | 0.035 | 0.869 | 122 mK | no |

- **Target goes sub-pixel at 2.1 km** (GSD = 1 m); above that the apparent
  contrast falls ∝ 1/altitude².
- **Detection ceiling: 8.5 km** — the highest altitude where the apparent
  ΔT stays above the 200 mK floor (4 × NETD).
- **The ceiling is set by sub-pixel dilution, not atmosphere.** τ_atm barely
  moves (0.94 → 0.87); the 30× collapse in apparent ΔT is almost entirely
  the `1/altitude²` fill-fraction effect. A UAV IR analyst who blamed
  "atmosphere" for lost detection would be mis-diagnosing — the fix is
  resolution (longer focal length / closer approach), not a clearer sky.

---

## Physics / modeling notes (house rule: explain the non-obvious)

- **NETD-specified detector.** Rather than dark/read/QE, the microbolometer
  is carried by its NETD. The converters translate it to NEP and D* using
  the chain's `dP/dT` (derived from the exact `dS/dT`, Gap 43) — so the
  sensitivity is expressed in whichever figure the comparison needs.
- **Sub-pixel contrast** uses the fill-fraction dilution `ff·ΔT`, the same
  physics as scenario 4.1's sub-pixel targets. The two-pixel/differential
  subtlety (Gap 52) does not arise here — this is an apparent-contrast
  threshold against NETD, not a chain `contrast_snr`.
- **Uncooled ⇒ integration-time-limited too.** The 16 ms frame is the
  microbolometer's thermal time constant; NETD is quoted at that frame.
- **Detection floor = 4 × NETD** is a recognition-grade SNR threshold; a
  detection-only task (≈2 × NETD) would push the ceiling higher.

---

## Truth anchors for the converters

Verified in `src/radiant/performance/tests/test_noise_spec_converters.py`
(13 Level-0 tests). The scenario-level cross-check: an uncooled
microbolometer's NETD of 50 mK maps to D\* ≈ 1.3 × 10⁹ Jones — the
literature order of magnitude for uncooled LWIR.
