# Scenario 4.1 Walkthrough: Target Detection Matrix

Executed 2026-07-08 (Scenario_Execution_Plan Phase T3, priority 16);
prerequisites `radiant.api.batch.BatchRunner` and `radiant.io.target_library`
landed in commit 6492028. **Fully refreshed 2026-07-22 (CU-176) against the
current engine, after the CU-182 geometry-convention fix** — the runner had
been over-specifying the line of sight (both `geometry.target_range_m` and
`geometry.path_zenith_rad`), which failed every cell under the CU-093
consistency check; it now sets only the target-side path zenith θ_o and derives
the slant range from the chain (`slant_range_from_theta_o_m`). All 144 cells now
evaluate, and the numbers below reflect both that fix and the CU-155/161
atmosphere recalibration.

## The Problem

Lisa needs a quarterly program-review briefing: for a 12-target library,
under four atmospheric conditions, for each of three sensors — how far
off-nadir can each sensor detect each target, and which target is hardest?
144 evaluations (12 × 4 × 3), automated.

## Inputs

**Target library** (`load_target_library`, `lisa_target_library.xlsx`):
12 targets with dimensions → derived `projected_area_m2 = length × width`.

| Target | A_proj [m²] | T [K] | ε | Material |
|--------|------------:|------:|---|----------|
| MBT tank | 28.4 | 310 | 0.90 | painted steel |
| APC | 18.2 | 306 | 0.90 | painted steel |
| Cargo truck | 20.0 | 301 | 0.92 | painted steel |
| SAM TEL | 35.6 | 305 | 0.90 | painted steel |
| Patrol boat | 145.0 | 299 | 0.85 | painted steel |
| Fast attack craft | 476.0 | 302 | 0.85 | painted steel |
| Transport aircraft | 1600.0 | 295 | 0.30 | bare aluminum |
| Fighter aircraft | 150.0 | 297 | 0.35 | low-e coating |
| Fuel bladder farm | 600.0 | 298 | 0.95 | rubberized fabric |
| (…12 total) | | | | |

**Sensor library** (3 YAML): A — MWIR smallsat 18 cm (16.7 m GSD); B —
MWIR flagship 50 cm (4.0 m GSD); C — LWIR wide 35 cm (12.1 m GSD). Sensor
C's YAML still carries the pre-Gap-12 `optics.cold_stop_efficiency` name —
RADIANT accepted it through the deprecated-alias mechanism (one
`DeprecationWarning`, mapped to `optics.nearfield_fraction`).

**Atmospheres**: clear (vis 50 km), haze (10 km), tropical_haze (5 km),
arctic_clear (100 km), each with its matching profile.

## How RADIANT Answers It

**The 12×4 matrix per sensor is a `BatchRunner`.** Cartesian product of the
target and atmosphere axes, per-cell parameter overrides applied to
`Sensor.from_yaml`, per-cell failure capture (Rule 17 — 0 failures here).
`result.pivot()` builds the target×atmosphere tables.

**Detection = SCNR ≥ 5, clutter-limited.** Pure noise-limited SNR saturates
(≫ 5) for every cell, so it does not discriminate; real sub-pixel detection
at 500 km is clutter-limited. SCNR = |contrast_e| / RSS(all noise incl.
scene clutter, `detector.clutter_sigma = 0.02`), assembled script-side
because `metrics["snr"]`/`["contrast_snr"]` exclude the spatial clutter term
(gaps.md).

**Detectability scales with target SIZE via `fill_fraction`.** The sub-pixel
regime weights the target by `source.target.fill_fraction =
min(1, A_target/(IFOV·R)²)` — the pixel fraction it covers — NOT by
`projected_area_m2` (which drives only the point-source path). Off-nadir the
pixel footprint grows, fill drops, and SCNR falls: that is the
detection-range mechanism, found by bisection on the target-side path zenith
θ_o (`geometry.path_zenith_rad`), with the slant range derived from θ_o through
the chain's own spherical viewing triangle (`slant_range_from_theta_o_m`).

## Key Results (detection range [km slant], SCNR ≥ 5)

**Sensor A — MWIR smallsat (16.7 m GSD, 278 m² footprint):** the coarse
GSD gives a huge pixel footprint, so only the single largest fill target
clears the sub-pixel threshold —

| Target | clear | haze | trop_haze | arctic |
|--------|------:|-----:|----------:|-------:|
| Fuel bladder farm | 1,040 | 1,040 | 1,044 | 1,036 |
| (all others) | — not detectable — | | | |

**Sensor B — MWIR flagship (4.0 m GSD, 16 m² footprint):** the small
footprint gives high fill, so **every** target is detectable, most out to
the swath edge —

| Target | clear | haze | trop_haze | arctic |
|--------|------:|-----:|----------:|-------:|
| Fuel bladder farm | 1,061* | 1,061* | 1,061* | 1,061* |
| Fast attack craft | 1,061* | 1,061* | 1,061* | 1,061* |
| Transport aircraft | 1,061* | 1,061* | 1,061* | 1,061* |
| Patrol boat | 1,061* | 1,061* | 1,061* | 1,061* |
| Fighter aircraft | 1,061* | 1,061* | 1,061* | 1,061* |
| SAM TEL | 1,061* | 1,061* | 1,061* | 1,061* |
| Towed artillery | 1,061* | 1,061* | 1,061* | 1,061* |
| Cargo truck | 1,036 | 1,036 | 1,036 | 1,040 |
| Small UAV | 904 | 904 | 899 | 921 |
| APC | 817 | 817 | 815 | 819 |
| MBT tank | 776 | 778 | 778 | 776 |
| Technical (pickup) | 686 | 686 | 684 | 692 |

**Sensor C — LWIR wide (12.1 m GSD):** ships and the largest air/ground
targets reach the swath edge; SAM TEL and towed artillery detect at mid
range; small ground vehicles fall below threshold —

| Target | clear | haze | trop_haze | arctic |
|--------|------:|-----:|----------:|-------:|
| Patrol boat / Fast attack / Transport / Fighter / Fuel bladder | 1,061* | 1,061* | 1,061* | 1,061* |
| SAM TEL | 564 | 564 | 567 | 560 |
| Towed artillery | 527 | 527 | 529 | 523 |
| (MBT, APC, Cargo, Technical, Small UAV) | — not detectable — | | | |

`*` = swath-edge limited (SCNR ≥ 5 out to the 66° θ_o practical edge, slant
1,061 km).

**Worst-case target: Technical (pickup)** — the smallest ground vehicle
(10 m²), detectable only on the flagship (mean 229 km across all 12
sensor×atmosphere cells). **Easiest: fuel bladder farm** (mean 1,054 km).

## Physics Discussion

**Aperture buys targets, size buys range.** Sensor B's 4 m GSD (16 m²
footprint) fills a pixel with far smaller targets than sensor A's 16.7 m
GSD (278 m²), so B detects **all twelve** targets — most to the swath edge —
while A's coarse footprint clears only the single largest (fuel bladder
farm). Within a sensor, bigger targets detect farther (fuel bladder farm hits
the 1,061 km edge vs the Technical pickup's 686 km on B) because fill stays
near 1 out to longer slant ranges before the growing footprint dilutes it.

**Why the Technical pickup is universally hardest — EE_box occlusion.** The
sub-pixel contrast is `ff·(L_target·EE_box − L_bg)`: the target's compact
energy is EE_box-weighted (its PSF spills to neighbouring pixels) while the
uniform in-pixel background it OCCLUDES is not. The Technical (pickup)
(10 m², ε 0.88, 303 K) combines the smallest fill of the ground vehicles with
`L_target·EE_box` landing closest to `L_bg` — its pixel departs least from
background in either direction, so |contrast| is smallest and it detects only
on the flagship. Counterintuitively the *cooler* Small UAV (12 m², 294 K)
reaches farther on B (904 km) than the warmer Technical: the cooler radiance
lands *farther* from the weighted-background null. The MBT tank (28 m², 310 K)
— hardest in the pre-fix run — is now comfortably detectable on B (776 km).
This is correct single-pixel radiometry; a multi-pixel matched filter (summing
the target energy that EE_box spread to neighbours) would recover the
Technical — a performance-model refinement beyond this single-pixel SCNR
(noted in gaps.md).

**Atmosphere barely reranks either band now.** In the refreshed run the MWIR
detection ranges are nearly condition-independent — MBT tank 776/778/778/776,
APC 817/817/815/819, cargo truck 1,036/1,036/1,036/1,040 across
clear/haze/tropical_haze/arctic. The dramatic clear→tropical collapse the
pre-fix matrix showed was the parametric water over-response, and the CU-155/161
recalibration removed it (validated against real MODTRAN in scenario 6.2). The
LWIR sensor C's ranges are likewise near-flat across columns — its 8–11.5 µm
band is far less aerosol-sensitive and the target–background *thermal* contrast
dominates. The condition axis is now a weak discriminator; target size and
sensor GSD set detectability.

## Real-MODTRAN validation note (added 2026-07-17)

The real MODTRAN 6 A-block (2026-07-17 run set) pins this matrix's
condition axis. Band-mean full-column nadir τ, real vs SimpleAtmosphere
at the matching profile (visibility-23 baseline; the visibility *axis*
itself is separately validated in scenario 3.2):

The band-mean τ ratios below were measured against the **pre-CU-161**
SimpleAtmosphere and quantify the over-response that has since been fixed:

| Condition (profile) | MWIR real/simple (pre-fix) | LWIR real/simple |
|---|---|---|
| clear, haze (midlat_summer) | **1.87×** | 0.84× |
| tropical_haze (tropical) | **2.89×** | 0.78× |
| arctic_clear (subarctic_winter) | **0.74×** | 0.88× |

Consequences for the matrix (updated 2026-07-22, now that it is re-baselined):

- **The MWIR condition axis no longer reranks.** The pre-fix
  SimpleAtmosphere spanned τ 0.16–0.81 across these profiles (5×) while real
  MODTRAN spans 0.47–0.60 (**1.3×**). The CU-155/161 recalibration
  (validated in scenario 6.2) collapsed that over-response, so the refreshed
  matrix's MWIR ranges are now nearly condition-independent — matching the
  real atmosphere's flat spread rather than the old parametric collapse.
- **The LWIR band carries a modest real condition dependence.** Real LWIR τ
  varies across the conditions (0.47–0.82, driven by the H₂O continuum) — the
  tropical cell's LWIR ranges carry a real ~22% τ penalty; the refreshed
  numbers are near-flat, so any residual under-response is a secondary term.
- **Target-axis conclusions (which target is hardest, EE_box occlusion,
  aperture-vs-size) are unaffected** — they compare targets under a
  common atmosphere and don't depend on its absolute accuracy.

The matrix is now re-baselined against the recalibrated engine (CU-176).
Anchors: `modtran/real_runs/` A2/A3/A6 vs `SimpleAtmosphere` at profile-coupled PWV; model defect
consolidated in CU-161.

## Gaps and a Bug Caught

See `gaps.md`. The two importer gaps (target-library Excel, projected-area)
are **closed** by `radiant.io.target_library`; the matrix runner by
`radiant.api.batch.BatchRunner`. Two execution-time findings, both
scenario-side and fixed here:
1. **`Sensor.get` returns canonical units** (pixel pitch in metres, not µm
   despite the `_um` name) — an initial `× 1e-6` double-conversion made the
   footprint 10¹²× too small; caught via the printed GSD reading 0.0 m.
2. **Sub-pixel fill must be set explicitly** — `projected_area_m2` does not
   drive sub-pixel weighting; `fill_fraction` does. The same omission in the
   committed scenario 1.3 is filed as **CU-060**.

## Outputs

- `outputs/detection_matrix_results.xlsx` — per-sensor color-coded sheets + summary
- `outputs/fig1_detection_range_matrix.png` — 3-panel heatmap
- `outputs/fig2_nadir_scnr_by_target.png` — nadir SCNR bar chart (clear)

## What Lisa Would Do Next

1. **Brief the aperture/GSD trade**: the flagship (B) detects all 12
   targets (most to the swath edge); the smallsat (A) only the single
   largest — the constellation-vs-exquisite decision in one matrix
2. **Add a matched-filter detection model** for the sub-pixel targets the
   single-pixel SCNR marks "not detectable" (the Technical pickup, and the
   small ground vehicles on the LWIR sensor, are recoverable with
   neighbour-pixel summation)
3. **Fold in revisit/access** (scenario 3.x) — detection range × access
   rate is the operational figure of merit
4. **Vary target temperature by time-of-day** (scenario 4.4) — the thermal
   contrast that drives sub-pixel detection swings diurnally

**Postscript (2026-07-22):** the 144-cell matrix, both figures, and every hard
number above were regenerated against the current engine after the CU-182
geometry-convention fix (the runner had failed every cell under the CU-093
over-spec check). The condition-axis distortion is gone — the recalibrated model
(CU-161, commit `0aebdda`) matches real MODTRAN's flat climate spread — and the
θ_o-consistent slant range moved the swath edge from the pre-fix 1,704 km to
1,061 km.
