# Scenario 4.1 Walkthrough: Target Detection Matrix

Executed 2026-07-08 (Scenario_Execution_Plan Phase T3, priority 16). First
execution; prerequisites `radiant.api.batch.BatchRunner` and
`radiant.io.target_library` landed in commit 6492028.

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
detection-range mechanism, found by bisection on zenith (spherical-Earth
slant range, the same function GSD uses).

## Key Results (detection range [km slant], SCNR ≥ 5)

**Sensor A — MWIR smallsat (16.7 m GSD, 278 m² footprint):** only the
largest targets clear the sub-pixel threshold —

| Target | clear | haze | trop_haze | arctic |
|--------|------:|-----:|----------:|-------:|
| Transport aircraft | 1,139 | 968 | 831 | 1,146 |
| Fuel bladder farm | 555 | 534 | 515 | 557 |
| (all others) | — not detectable — | | | |

**Sensor B — MWIR flagship (4.0 m GSD, 16 m² footprint):** the small
footprint gives high fill, so most targets are detectable —

| Target | clear | haze | trop_haze | arctic |
|--------|------:|-----:|----------:|-------:|
| Fuel bladder farm | 1,704* | 1,704* | 1,693 | 1,704* |
| Patrol boat | 1,487 | 1,354 | 1,226 | 1,501 |
| Fast attack craft | 1,102 | 1,032 | 951 | 1,114 |
| Towed artillery | 826 | 813 | 800 | 829 |
| SAM TEL | 772 | 761 | 748 | 774 |
| Cargo truck | 698 | 689 | 678 | 700 |
| Small UAV | 609 | 602 | 594 | 610 |
| APC | 575 | 568 | 561 | 576 |
| Technical | 505 | 502 | not det. | 506 |
| MBT tank / Transport / Fighter | — not detectable — | | | |

**Sensor C — LWIR wide (12.1 m GSD):** large targets and ships; the LWIR
band's temperature contrast is atmosphere-insensitive (identical across
columns), so the ranking is size-driven.

`*` = swath-edge limited (SCNR ≥ 5 out to the 66° practical edge, 1,704 km).

**Worst-case target: MBT tank** — not detectable by *any* sensor (mean
0 km). **Easiest: fuel bladder farm** (mean 1,315 km).

## Physics Discussion

**Aperture buys targets, size buys range.** Sensor B's 4 m GSD (16 m²
footprint) fills a pixel with far smaller targets than sensor A's 16.7 m
GSD (278 m²), so B detects nine targets to A's two. Within a sensor, bigger
targets detect farther (fuel bladder 1,704 km vs APC 575 km on B) because
fill stays near 1 out to longer slant ranges before the growing footprint
dilutes it.

**Why the tank is universally hardest — EE_box occlusion.** The sub-pixel
contrast is `ff·(L_target·EE_box − L_bg)`: the target's compact energy is
EE_box-weighted (its PSF spills to neighbouring pixels) while the uniform
in-pixel background it OCCLUDES is not. The MBT tank (28 m², ε 0.90, 310 K)
lands with `L_target·EE_box` closest to `L_bg` for all three sensors — its
pixel departs least from background in either direction, so |contrast| is
smallest. Counterintuitively the cooler APC (18 m², 306 K) is detectable on
sensor B while the hotter tank is not: the tank's warmer radiance lands
*nearer* the weighted-background null. This is correct single-pixel
radiometry; a multi-pixel matched filter (summing the target energy that
EE_box spread to neighbours) would recover the tank — a performance-model
refinement beyond this single-pixel SCNR (noted in gaps.md).

**Atmosphere matters for MWIR, not LWIR here.** MWIR ranges drop clear →
tropical_haze (aerosol extinction); the LWIR sensor C's ranges are
identical across columns because its 8–11.5 µm band is far less
aerosol-sensitive and the target–background *thermal* contrast dominates.

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

1. **Brief the aperture/GSD trade**: the flagship (B) detects 9 of 12
   targets; the smallsat (A) only the two largest — the constellation-vs-
   exquisite decision in one matrix
2. **Add a matched-filter detection model** for the sub-pixel targets the
   single-pixel SCNR marks "not detectable" (the tank is recoverable with
   neighbour-pixel summation)
3. **Fold in revisit/access** (scenario 3.x) — detection range × access
   rate is the operational figure of merit
4. **Vary target temperature by time-of-day** (scenario 4.4) — the thermal
   contrast that drives sub-pixel detection swings diurnally
