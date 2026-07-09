# Scenario Execution Plan

> **HISTORICAL — completed 2026-07-09.** All 33 non-MODTRAN scenarios are
> executed (the two MODTRAN-gated scenarios, 1.1 and 6.2, carry deferral
> records). Archived per Rule 24. Superseded by the executed scenarios
> themselves (each with its walkthrough/gaps/gui_workflow trio + MANIFEST)
> and the gap/CU registries; do not resume this plan — open a new one for
> any future scenario work.

Status: Complete (2026-07-07 → 2026-07-09; progress-refreshed 2026-07-08)
Author: Coding agent, approved by project owner
Scope: Execute the 21 remaining scenarios and refresh the 4 whose workarounds
the Gap_Closure_Plan made obsolete.
Order of record: the Scenario-Driven Capability Priority List in
`docs/tracking/gaps.md` (Rule 25 — referenced, not re-enumerated).
Process rules: `docs/guides/scenario_testing.md`. Definitions:
`docs/guides/scenario_catalog.md`.

---

## Ground rules (every scenario)

1. Follow `docs/guides/scenario_testing.md` exactly: vendor-format inputs,
   `create_spreadsheet.py` generator, `run_<slug>.py` driver, the mandatory
   `walkthrough.md` / `gaps.md` / `gui_workflow.md` trio, `outputs/MANIFEST.md`.
2. Units on every output number; regime and non-obvious physics explained in
   script output.
3. Every limitation hit → per-scenario `gaps.md` AND mirrored into
   `docs/tracking/gaps.md` (or a CU) before the scenario's PR merges.
4. Environment: `pip install -e ".[scenarios]"` (CU-057, resolved 0c14c9b).
5. One scenario per commit, walkthrough included.

## Phase R — refresh pass over executed scenarios (first)

**Status: COMPLETE 2026-07-07.** Scenario commits: 7.4 → 8333992, 7.3 →
0c1bed9, 5.1 → 6fa9c83, 6.3 → 253ffa5; sweep-pass h_sensor fixes (7.1, 2.2,
2.5) → e75136f. Side discoveries, all dispositioned: odd-kernel crash fixed
(8a5d9e8), CU-058 (defocus Rule 4 violation), CU-059 (stale non-Phase-R
outputs), registry Gaps 42 (lab_test unreachable from config) and 43 (NEDT
single-λ approximation). The remaining 8 terrestrial scripts were rerun and
pass; their regenerated outputs were restored pending CU-059.

The Gap_Closure_Plan (archived 2026-07-07) obsoleted these scenarios'
workarounds; refresh each script + walkthrough to the built-in capability and
rerun:

| Scenario | Replace workaround with | Also |
|----------|------------------------|------|
| 7.4 cold stop sweep | `Sensor.solve_for` (Gap 10); `optics.scalar_emissivity` (Gap 37); `nearfield_fraction` name (Gap 12) | **Fix known drift**: script predates the Stage-7 `platform.h_sensor` requirement — currently raises in `validate_no_atmosphere_subcase` (found 2026-07-07 during CU-057 verification; disposition: Planned, here) |
| 7.3 MTF measurement | `load_measured_curve` + `compare_mtf` (Gap 30); electronics MTF (Gap 32); scatter (Gap 31) as candidate residual explainers | |
| 5.1 WFE budget | `ErrorBudget` (Gaps 23+28); `load_zemax_zernike` (Gap 26) | |
| 6.3 noise verification | unit-aware `set(..., unit=)` (Gap 6) | |

Sweep check while in there: grep all 14 executed run scripts for the same
`h_sensor` drift and for the deprecated `cold_stop_efficiency` name; fix any
found in the same pass.

## Phase T3 — Tier 3 scenarios (priorities 15–22, parsers first)

Execution order (MODTRAN-gated items skipped, matching the Gap 38/39
deferrals):

1. **2.1** Mike — detector datasheet import. Prereq parsers: QE CSV
   (nm/% → µm/fraction), dark-current CSV (A/cm² → e⁻/s), each its own
   `io/` module (Rule 19) with Level 0 tests.
2. **4.1** Lisa — target library batch. Prereq: Excel target library reader,
   batch scenario matrix runner (may compose `Sensor.sweep`).
3. **7.2** Karen — radiometric calibration. Prereq: lab calibration CSV
   (Gap 30's `load_measured_curve` likely covers most of it), DN-domain output.
4. **1.3** Sarah — dual-band MWIR/LWIR. Prereq: ASTER spectral library reader,
   Excel detector specs.
5. **4.3** Lisa — spectral emissivity target. Prereq: spectral emissivity curve
   input (curve, not scalar).
6. **7.5** Karen — environmental temperature extremes. Prereq: measured J(T)
   curve + QE(T) table readers.

Skipped pending MODTRAN access: **6.2** (priority 16), **1.1** (priority 17) —
re-audit with Gaps 38/39 (2026-10-01 or on access).

## Phase T4 — Tier 4 scenarios (new models)

**Status: COMPLETE (13 of 13 done, 2026-07-09).** Priority-list order plus
one scenario (5.5) the priority list had omitted, discovered and executed on
the final pass. Each new model is its own Category C task with truth anchors
before the scenario that consumes it.

### Completed (each: model commit → scenario commit → MANIFEST-SHA commit)

| Scenario | New capability (Category C model) | Commits |
|----------|-----------------------------------|---------|
| **1.2** VNIR GSD vs aperture vs altitude | `core.solar_geometry` (LTAN/date/lat → solar zenith; Spencer declination + hour-angle) | model 00efcc5 → scenario b34e518 → manifest 93c7281 |
| **3.1** Orbit geometry & pass planning | `core.orbit` (period, orbital velocity, ground-track speed; adds `mu_earth_m3_s2`) | model e32188e → scenario 760472c → manifest 02eba95 |
| **4.4** Diurnal time-of-day detectability | data-driven (no new model — profile is input data) | scenario 6257eee → manifest 49733ff |
| **4.2** Maritime ship classification | `performance.johnson_criteria` (Detection/Recognition/ID ranges) | model 0df9e15 → scenario d1f2707 → manifest 89fe2ed |
| **1.5** Obscured aperture & spider vanes | spider-vane pupil masking (`optics.n_spiders`/`spider_width_m`/`spider_angle_deg`); implements RADIANT_Optics.md §3.3 | model 36286e7 (+style 6c35307) → scenario bbf9f6f → manifest 01da0e2 |
| **6.1** Published-datasheet benchmark | D*/NEP/NETD converters (`performance.detectivity`/`nep_electrons`/`nep_netd`) | model ac59315 → scenario 55b0175 → manifest 81a97bc |
| **4.5** Microbolometer UAV altitude trade | (same converters — NETD-specified detector) | scenario efea031 → manifest 521771d |
| **3.3** Multi-sensor procurement comparison | data-driven (vendor workbook; no new model) | scenario 4455ad8 → manifest 979537a |
| **2.4** Persistence / bright-source recovery | `detector.persistence_sequence` (multi-frame residual) | model c4a3a28 → scenario f0b6d34 → manifest 044b209 |
| **6.5** Emissivity sensitivity for retrieval | `performance.temperature_retrieval` (inverse + Jacobian) | model 6623d0d → scenario d01fbad → manifest 03b25b8 |
| **6.4** Synthetic scene / ROC | `performance.roc` (ROC curve, detection probability, AUC) | model c1ad64e → scenario 6ca0cb3 → manifest d9693f5 |
| **3.5** Nighttime MWIR feasibility | consumes NEDT/MRT/contrast-reference; analytic solar comparison (no new model) | scenario c19bd21 → manifest 668a56e |
| **5.5** Stray-light / veiling-glare (priority-list omission) | consumes existing stray-light surface; found bug CU-062 | scenario 124f09c → manifest 2ac2781 |

New registry gaps filed on the final pass: 56 (multi-target scene), 57
(preset humidity coupling), 58 (GeoTIFF reader), 59 (day/night mode), 60
(stray-light 2-D PSF / MTF). CUs: 061 (contrast_snr saturation),
062 (veiling_glare solid-angle bug).

Priority-list items 23/24/26/27 in `gaps.md` marked DONE. New registry gaps
filed: 49 (diffraction-limited-resolution metric), 50 (sampling-regime
flag), 51 (revisit/repeat-ground-track), 52 (extended target-vs-background
differential), 53 (Johnson MRC/MRT coupling), 54 (arbitrary pupil mask).
Rule 4 preserved for spider vanes (496 optics + 10 golden tests unchanged;
no-vane pupil byte-identical).

### Side discovery, dispositioned

Five executed-scenario folders had diverged from the canonical scaffold
names, creating duplicate directories (Rule 23/27 violation introduced in
T3/T4). Corrected in-tree: 3.1 relocated to `03_raj_mission_planner/
3.1_isr_pass_planning` (eacd980); 1.2/1.3/2.1/7.5 renamed to their canonical
scaffold names (f9d2426). Content unchanged; internal path references and
one Cleanup_Backlog reference fixed.

### 4.5 / 6.1 design decision — RESOLVED 2026-07-08

Both are NETD/D*/NEP noise-spec scenarios. Owner-approved design: **one
shared converter model** (`performance.detectivity` D*⇄NEP,
`performance.nep_electrons` NEP⇄σ_e, `performance.nep_netd` NEP⇄NETD) built
from standard radiometric definitions and reusing the exact `dS/dT`
(Gap 43) — not a first-principles thermal-noise model. Priority-list items
28 (4.5) and 30 (6.1) in `gaps.md` marked DONE. 6.1 benchmarks a published
datasheet (chain D* within 10% of spec); 4.5 turns a vendor NETD into D*
(1.34e9 Jones, uncooled) for a UAV altitude trade (ceiling 8.5 km,
sub-pixel-limited).

### Remaining

None — all Phase T4 scenarios are executed (see the completed table above).

## Exit criteria — MET 2026-07-09

- ✔ 33 of 35 scenarios executed (all but MODTRAN-gated 1.1, 6.2, which carry
  deferral records); each meets the Definition of Done in
  `scenarios/README.md`. Verified: 33 scenario folders carry a `walkthrough.md`.
- ✔ Registry hygiene: every scenario gap mirrored into `docs/tracking/gaps.md`
  (through Gap 60) and `Cleanup_Backlog.md` (through CU-062); this plan
  archived per Rule 24 on the landing of the last non-deferred scenario (5.5).
