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

> **Matrix refreshed 2026-08-30 from the unmodified runner. One mover:
> CU-335** — the calibrated gas table's VIS/NIR/SWIR rows were re-fitted against
> the post-CU-253 Rayleigh. Every sensor here is MWIR or LWIR, so the reach is
> only the λ⁻⁴ tail in the 2.40–5.00 µm floors (≤ 0.001 OD): **one cell in the
> whole 12 × 4 × 3 matrix moves**, sensor A's small UAV, 686 → 685 km. Nothing
> else changes to the printed precision and no status flips.
>
> **Prior vintage 2026-08-29. One mover: CU-324.**
> `E_sky_thermal`'s flux-diffusivity exponent became the geometric
> `sec 48.2° = 1.50030` — the secant of the angle every up-looking MODTRAN deck
> in the downwelling reference set was run at — instead of the CU-155 fitted
> `D = 1.1`, so the sky every ε < 1 target and the ground background reflect is
> brighter. Because the detection criterion is the *signed* sub-pixel contrast
> `ff·(L_target·EE_box − L_bg)` and both terms rise, the matrix moves both ways
> and by ≲ 1 % almost everywhere: most cells shift 0–4 km, no cell changes
> detectable/not-detectable status, and the hardest and easiest targets are
> unchanged. The two visible exceptions are sensor B's **transport aircraft**
> (1,061* → 1,047 clear, 1,061* → 1,022 haze, 813 → 737 tropical_haze) and
> **fighter aircraft** (1,061* → 1,059, 1,061* → 1,029, 821 → 753) — the two
> coldest, lowest-emissivity targets (ε 0.30 / 0.35 at 295 K), which sit *below*
> the weighted-background null, so a brighter reflected sky moves them back
> toward it and shortens their range. Same sign-dependence as the CU-188 epoch
> below, opposite direction.
>
> Prior vintage 2026-08-02, and the archaeology for it, below: the matrix had
> three earlier epochs of drift (CU-188, then CU-224, then CU-321) — see **Drift
> archaeology** for which landing did what and why the other candidates are
> excluded.

**Sensor A — MWIR smallsat (16.7 m GSD, 278 m² footprint):** the coarse
GSD gives a huge pixel footprint, so in the three temperate columns only the
single largest fill target clears the sub-pixel threshold. The cold, dry
arctic column is the exception: with far less atmospheric emission in the
path, three more large targets clear it —

| Target | clear | haze | trop_haze | arctic |
|--------|------:|-----:|----------:|-------:|
| Fuel bladder farm | 823 | 813 | 742 | 1,061* |
| Transport aircraft | — | — | — | 1,061* |
| Fast attack craft | — | — | — | 788 |
| Patrol boat | — | — | — | 534 |
| (all others) | — not detectable — | | | |

**Sensor B — MWIR flagship (4.0 m GSD, 16 m² footprint):** the small
footprint gives high fill, so **every target is detectable in every
condition** — three of the twelve out to the swath edge in the two clearest
columns —

| Target | clear | haze | trop_haze | arctic |
|--------|------:|-----:|----------:|-------:|
| Fuel bladder farm | 1,061* | 1,061* | 1,059 | 1,061* |
| Patrol boat | 1,061* | 1,061* | 998 | 1,061* |
| Fast attack craft | 1,061* | 1,061* | 924 | 1,061* |
| Fighter aircraft | 1,059 | 1,029 | 753 | 1,061* |
| Transport aircraft | 1,047 | 1,022 | 737 | 1,061* |
| Towed artillery | 893 | 883 | 800 | 1,061* |
| SAM TEL | 870 | 858 | 782 | 1,061* |
| Cargo truck | 773 | 763 | 699 | 1,029 |
| MBT tank | 696 | 688 | 560 | 901 |
| Small UAV | 685 | 678 | 621 | 901 |
| APC | 673 | 666 | 612 | 865 |
| Technical (pickup) | 575 | 570 | 527 | 718 |

**Sensor C — LWIR wide (12.1 m GSD):** ships and the largest air targets
reach or approach the swath edge; SAM TEL and towed artillery now detect only
in the arctic column; small ground vehicles fall below threshold everywhere —

| Target | clear | haze | trop_haze | arctic |
|--------|------:|-----:|----------:|-------:|
| Transport aircraft | 1,061* | 1,061* | 1,061* | 1,061* |
| Fast attack craft | 1,061* | 1,061* | 969 | 1,061* |
| Fuel bladder farm | 1,061* | 1,061* | 1,019 | 1,061* |
| Fighter aircraft | 924 | 912 | 771 | 1,061* |
| Patrol boat | 828 | 817 | 700 | 1,061* |
| SAM TEL | — | — | — | 561 |
| Towed artillery | — | — | — | 520 |
| (MBT, APC, Cargo, Technical, Small UAV) | — not detectable — | | | |

`*` = swath-edge limited (SCNR ≥ 5 out to the 66° θ_o practical edge, slant
1,061 km). `—` = not detectable in that cell.

*LWIR detection ranges refreshed 2026-08-29 from the unmodified runner —
**CU-330**, the 9.6 µm ozone region split: the model gains in-band opacity, so
every LWIR range shortens by 2–3 km (0.3–0.6 %). The MWIR columns and every
detect/no-detect verdict in the matrix are unchanged.*

**Worst-case target: Technical (pickup)** — mean 199 km across all 12
sensor×atmosphere cells, detectable only on the flagship. **Easiest: fuel
bladder farm** (mean 990 km).

## Drift archaeology — which landings moved this matrix

**Epoch 1 — 2026-07-22 → 2026-08-01 (the drift CU-317 was filed against).**
The qualitative changes recorded on the CU-317 entry — sensor A gaining the
patrol boat / fast attack craft / transport aircraft, sensor B's MBT rising
776 → 965 km, sensor C's MBT going from "not detectable" to 511 km — are
attributable to **CU-188** (2026-07-24), the cell-area-overlap EE_box
re-weighting. It is the only Results-affecting landing in that window whose
stated scope covers this matrix, and the mechanism is exact: this scenario's
detection criterion is the EE_box-weighted sub-pixel contrast
`ff·(L_target·EE_box − L_bg)`, and CU-188 removed an O(dx) box-edge bias that
had over-stated EE_box by ~24 % at critical sampling. Because the criterion
takes `|contrast|`, shrinking `L_target·EE_box` does not simply reduce
detectability — it moves each target *relative to the weighted-background
null*. Cold, low-emissivity targets (transport aircraft ε 0.30 at 295 K,
fighter ε 0.35) sit below the null, so a smaller `EE_box` pushes them
*further* from it and they became **more** detectable; targets sitting near
the null lost range. That sign-dependence is why the drift was qualitative
rather than a uniform scaling, and it is why it went unnoticed: nothing in the
machine baselines covers this script-side SCNR bisection.

The other candidates are excluded by their own scope statements, not by
assumption:
- **CU-263** (detection-range solvers) — verified excluded at filing time by a
  tripwire over all 144 cells: this matrix bisects a script-side SCNR and never
  enters a detection solver.
- **CU-253** (VIS/NIR Rayleigh, 2026-07-28) — its own entry bounds the effect
  at ≤ 0.03 τ points beyond 2 µm and +2.74 ppm at 8 µm. Both of this
  scenario's bands (3.6–4.9 µm, 8.0–11.5 µm) are past that; it is inert here.
- **CU-254 / CU-225 / CU-255 / CU-274** (the 2026-07-29 sky cluster) — all
  scoped to up-looking, level, or > 80° zenith geometry. This matrix is
  down-looking and stops at 66° θ_o.
- **CU-262** (site-elevation seeing, 2026-07-30) — moves results only when
  `geometry.site_elevation_m` is set non-zero; these three sensor YAMLs leave
  it at the 0 m default.
- **Gap 38** (`E_sky_scattered` ω₀_eff swap) and the **CU-155-era** emission
  work — both landed *before* the 2026-07-22 vintage, so they are already
  inside the numbers this table replaced.
- **CU-267** (gas-region blend) and **CU-209** (folded MTF) landed 2026-08-01,
  at the boundary; CU-209 does not touch detection, and CU-267 is a sub-percent
  τ term on these bands — a contributor to the third digit, not to a
  detectable/not-detectable flip.

**Epoch 2 — 2026-08-02 (CU-224).** **CU-224** landed the down-looking thermal
path term: `L_path_up` now carries `(1 − τ)·B(λ, T_eff)`, which had been absent
entirely, so the in-pixel background rose — and with it the 2 % scene-clutter
term this matrix is *limited by*. Ranges shortened across the board
(hardest-target mean 251 → 112 km; sensor C's MBT returned to "not detectable";
sensor B's MBT 965 → 837 km in the arctic column and dropped out of haze
altogether). It also restored the condition axis: because the added term scales
with how much warm air is in the path, the cold, dry `arctic_clear` column
pulled far ahead of the three temperate ones instead of matching them.

**Epoch 3 — 2026-08-02 (CU-321).** **CU-321** re-emits that same term at a
height-resolved `T_eff(λ)` over the column instead of at the column's
near-surface temperature. A 500 km path is mostly cold air, so the background
and its clutter fall back part of the way, and the ranges lengthen again:
hardest-target mean **112 → 199 km**, sensor B recovers *every* target in
*every* condition (MBT 837 → 901 km arctic, and back into haze at 688 km),
sensor A gains the arctic patrol boat and fast attack craft, and sensor C's
ships and air targets all lengthen by 5–10 %. Two qualitative verdicts move
with it, and both are corrected in the text above: the **hardest target flips
back from the MBT tank to the Technical pickup** — the EE_box null moved again
— and sensor B's "only the two hardest ground vehicles drop out under haze"
becomes "nothing drops out anywhere". The condition axis CU-224 restored
survives at reduced amplitude: `arctic_clear` still leads every temperate
column, by 25–35 % rather than by a detectability flip.

## Physics Discussion

**Aperture buys targets, size buys range.** Sensor B's 4 m GSD (16 m²
footprint) fills a pixel with far smaller targets than sensor A's 16.7 m
GSD (278 m²), so B detects **all twelve** targets in **every** condition
column, while A's coarse footprint clears only the single largest (fuel
bladder farm) except in the cold arctic column. Within a sensor, bigger
targets detect farther (fuel bladder farm to the 1,061 km swath edge in clear
vs the Technical pickup's 576 km on B) because fill stays near 1 out to longer
slant ranges before the growing footprint dilutes it.

**Why the Technical pickup is universally hardest — EE_box occlusion.** The
sub-pixel contrast is `ff·(L_target·EE_box − L_bg)`: the target's compact
energy is EE_box-weighted (its PSF spills to neighbouring pixels) while the
uniform in-pixel background it OCCLUDES is not. Detectability is therefore set
by how far the target pixel departs from background *in either direction*,
times fill fraction — not by `ε·B(T)·A`. The Technical pickup (10 m², ε 0.88,
303 K) is the target whose `L_target·EE_box` lands closest to `L_bg` after
weighting, so its pixel departs least and it is hardest to separate: mean
199 km, and it falls out entirely on the LWIR sensor. What the ordering is
*not* is a size or temperature ranking: the cool 12 m² Small UAV (294 K) and
the hot 28 m² MBT tank (310 K) sit within 1 % of each other on sensor B
(688 vs 695 km clear) and both beat the smaller, cooler Technical, because what
sets detectability is distance from the weighted-background null. This is
correct single-pixel radiometry; a multi-pixel
matched filter (summing the target energy that EE_box spread to neighbours)
would recover the hardest targets — a performance-model refinement beyond this
single-pixel SCNR (noted in gaps.md).

*(Which target sits at the null is itself model-dependent, and it has moved
twice: the Technical pickup held this position in the 2026-07-22 matrix,
CU-188's EE_box re-weighting plus CU-224's higher `L_bg` moved the null onto
the MBT tank, and CU-321's colder path emission — lowering `L_bg` again — moved
it back to the Technical. The mechanism the section describes is unchanged; the
target it lands on is not a stable property of the target library, and should
not be quoted as one.)*

**Atmosphere reranks both bands again.** The 2026-07-22 matrix was nearly
condition-independent — MBT tank 776/778/778/776, APC 817/817/815/819 across
clear/haze/tropical_haze/arctic — and this section previously concluded that
the condition axis had become a weak discriminator. **CU-224 reversed that,
and CU-321 halved the amplitude without undoing it.** Because the down-looking
path carries its own thermal emission, the in-pixel background (and its 2 %
clutter) scales with how much warm air the path contains, so the cold, dry
`arctic_clear` column stays ahead: sensor B's MBT runs 695 (clear) / 688 (haze)
/ 556 (tropical_haze) / 901 km (arctic), and sensor A detects three extra
targets in the arctic column that it cannot see in any temperate one. Under
CU-224 alone the same row read 503 / — / — / 837 km; the ordering is the same
physics, the detectability flips were an artefact of emitting the whole column
at its warmest temperature. What the CU-155/161
recalibration removed was the *parametric water over-response* — a spurious
clear→tropical collapse — and that remains removed; what has returned is a
real, physically-sourced condition dependence of the opposite origin
(atmospheric emission, not target-path absorption). The LWIR sensor C shows
the same pattern: SAM TEL and towed artillery are now arctic-only. Target
size and sensor GSD still set *which* targets are detectable at all;
atmosphere now sets how far.

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

- **The MWIR condition axis reranks again, for a different reason
  (restated 2026-08-02).** The pre-fix SimpleAtmosphere spanned τ 0.16–0.81
  across these profiles (5×) while real MODTRAN spans 0.47–0.60 (**1.3×**);
  the CU-155/161 recalibration (validated in scenario 6.2) collapsed that
  τ over-response, and it stays collapsed — this bullet's 2026-07-22 reading
  that the *ranges* were therefore condition-independent no longer follows.
  CU-224 added the down-looking thermal path term, so the condition axis now
  enters through atmospheric **emission** (and the clutter it feeds) rather
  than through target-path absorption. The spread is real physics, not the
  old parametric artefact: `arctic_clear` leads because a cold, dry column
  emits least.
- **The LWIR band carries a modest real condition dependence.** Real LWIR τ
  varies across the conditions (0.47–0.82, driven by the H₂O continuum) — the
  tropical cell's LWIR ranges carry a real ~22% τ penalty, and the refreshed
  matrix now shows a matching penalty (sensor C's fast attack craft and fuel
  bladder farm drop 1,061 → 912 km in the tropical column).
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

**Postscript (2026-08-02, CU-317):** the matrix, both figures and every number
above were regenerated again. The 2026-07-22 vintage had drifted twice without
being re-run — first under CU-188's EE_box re-weighting, then decisively under
CU-224's down-looking thermal path term — and the drift was qualitative, not
cosmetic: the hardest target changed identity (Technical pickup → MBT tank),
the hardest-target mean ran 229 → 251 → 112 km, and the "atmosphere barely
reranks" conclusion reversed. All epochs are attributed under **Drift
archaeology** above. The swath edge (1,061 km) and every geometry column are
unchanged. Nothing in this scenario's machine baseline covers the matrix — it
is a script-side SCNR bisection — which is why two results-affecting landings
passed through it unremarked.

**Postscript (2026-08-02, CU-321):** regenerated a third time in the same PR
as the landing, under the discipline CU-317 established. The height-resolved
emission temperature moved the hardest-target mean 112 → 199 km and flipped the
hardest target back to the Technical pickup; every table, both figures and the
two qualitative claims above were updated with it. This is what the CU-317
lesson looks like applied at landing time rather than archaeologically.
