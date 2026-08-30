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
2. **Atmospheric attenuation (secondary here).** The longer slant path
   transmits less contrast (`τ_atm` from the chain): over 1–11 km it drops
   0.92 → 0.69, a factor of 1.34 against the fill fraction's factor of 28.6.

Detection holds while `ff · ΔT · τ_atm ≥ threshold · NETD`. The
**detection ceiling** is the highest altitude satisfying it.

---

## Results (NETD 50 mK, 1 m target, ΔT 4 K, f/1, 486 µrad IFOV)

**Vendor NETD → optical-power figures (via the converters):**

| Quantity | Value |
|----------|-------|
| dP/dT (from the chain's dS/dT) | 1.516 × 10⁻¹⁰ W/K |
| NEP = NETD · dP/dT | 7.579 × 10⁻¹² W |
| **D\* = √(A·Δf)/NEP** | **1.254 × 10⁹ Jones** |

*Numbers refreshed 2026-08-02 from the unmodified runner. This table's previous
vintage is 2026-07-08 (`efea031`) — the 2026-07-20 commit on this file added
only the Gap-101 note and did not re-baseline. Dominant mover: **CU-161**
(commit `0aebdda`, 2026-07-18) — the gas-band recalibration plus Gap 94
elevated-target support, which reshapes τ(λ) inside 8–14 µm and rebuilds how
sensor altitude enters the absorbing column. Note dP/dT rises 7.7 % while
band-mean τ falls, so the driver is the spectral re-weighting inside the band
(where dB/dT is large), not the τ level. CU-267 contributes −0.21 % of τ on
8–14 µm. Neither CU-224 nor CU-321 reaches this scenario's headline metric:
apparent ΔT is `ff · ΔT · τ` with no radiance term for path emission to enter,
and τ is untouched by both. They do reach this converter table, which runs
through the chain's `dS/dT`: CU-321's height-resolved emission temperature
moves dP/dT −0.85 % (1.530 → 1.517 × 10⁻¹⁰ W/K) and D\* +0.8 % with it. The
altitude trade and the 7.5 km ceiling below are bit-identical.*

D\* ≈ 10⁹ Jones is the textbook value for an uncooled microbolometer —
about 100× below a cooled photon detector (scenario 6.1's 1.8 × 10¹¹). The
NETD spec is simply the practical way vendors carry that sensitivity.

**Altitude trade:**

| Altitude | GSD | Fill fraction | τ_atm | Apparent ΔT | Detect? |
|----------|-----|---------------|-------|-------------|---------|
| 1 km | 0.49 m | 1.000 | 0.921 | 3682 mK | yes |
| 3 km | 1.46 m | 0.471 | 0.807 | 1520 mK | yes |
| 5 km | 2.43 m | 0.170 | 0.748 | 508 mK | yes |
| 7 km | 3.40 m | 0.087 | 0.715 | 248 mK | yes |
| 9 km | 4.37 m | 0.052 | 0.695 | 145 mK | **no** |
| 11 km | 5.34 m | 0.035 | 0.681 | 95 mK | no |

*Numbers refreshed 2026-08-29 (CU-330, the 9.6 µm ozone region split: τ_atm
falls 0.1–0.7 % on every rung, apparent ΔT with it, and the 7.5 km detection
ceiling below is unchanged); previously 2026-08-02. Dominant mover across the
whole history remains **CU-161** (`0aebdda`, 2026-07-18) — gas-band
recalibration + Gap 94 elevated-target support. Its visible signature is the
shape of the τ_atm column: the old curve went nearly flat above 5 km
(0.878 → 0.869 across 5–11 km, as if the whole absorbing column sat below the
platform), while the refreshed one keeps falling (0.753 → 0.686). CU-267 adds
−0.21 % on 8–14 µm. GSD and fill fraction are pure geometry and did not move.*

- **Target goes sub-pixel at 2.1 km** (GSD = 1 m); above that the apparent
  contrast falls ∝ 1/altitude².
- **Detection ceiling: 7.5 km** — the highest altitude where the apparent
  ΔT stays above the 200 mK floor (4 × NETD). This is **1 km lower than the
  8.5 km this walkthrough previously reported**: the refreshed atmosphere is
  more absorbing on the long slant paths, so the contrast crosses the NETD
  floor sooner. An operator planning to the old ceiling would have flown 1 km
  above the detection limit.
- **The ceiling is still set by sub-pixel dilution, not atmosphere** — but by a
  narrower margin than before. Across the 1–11 km sweep the fill fraction falls
  ×28.6 (1.000 → 0.035) while τ_atm falls only ×1.34 (0.92 → 0.69), so dilution
  outweighs attenuation ~21:1 in the 38× total collapse of apparent ΔT. The
  earlier "τ_atm barely moves (0.94 → 0.87)" no longer holds — atmosphere is now
  a real, if secondary, term. The diagnosis is unchanged: the fix is resolution
  (longer focal length / closer approach), not a clearer sky.

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

**Known false saturation warning (Gap 101).** Evaluating this scenario emits a
`ReadoutStage: full well saturated` / `pixel saturated` warning. This is a
**modeling artifact, not a real clip of this detector**: the signal chain
converts flux to a photoelectron count and checks it against a charge-well
capacity, but an uncooled microbolometer is a *thermal* (bolometric) detector —
it measures a resistance change over its 16 ms thermal frame, not accumulated
charge. At that physically-required frame the photon-model count is ~5.5 × 10⁹
e⁻, which is 55× the schema's maximum `full_well_capacity_e` (1 × 10⁸ e⁻), so
there is no parameter re-center that clears the (inapplicable) check. The
scenario's actual metric — the ΔT-vs-NETD detection threshold — is independent
of the well/ADC path and is unaffected. Tracked as **Gap 101**; the SNR value
this baseline reports is a photon-FPA quantity with no bolometric meaning.

---

## Truth anchors for the converters

Verified in `src/radiant/performance/tests/test_noise_spec_converters.py`
(13 Level-0 tests). The scenario-level cross-check: an uncooled
microbolometer's NETD of 50 mK maps to D\* ≈ 1.24 × 10⁹ Jones — the
literature order of magnitude for uncooled LWIR. (Refreshed 2026-08-02 from
1.34 × 10⁹; the anchor is the order of magnitude, which is unaffected.)
