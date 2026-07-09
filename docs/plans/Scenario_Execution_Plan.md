# Scenario Execution Plan

Status: Active (2026-07-07; progress-refreshed 2026-07-08)
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

**Status: IN PROGRESS (5 of 12 done, 2026-07-08).** Work the priority list
order: 1.2 (solar geometry), 3.1 (orbit → geometry), 4.4 (diurnal sweep),
4.2 (Johnson DRI), 1.5 (pupil mask), 4.5 (microbolometer), 3.3
(multi-sensor), 6.1 (D*/NETD converters), 2.4 (persistence), 6.5
(retrieval), 6.4 (ROC), 3.5 (tropical/GeoTIFF/MRT). Each new model is its
own Category C task with truth anchors before the scenario that consumes it.

### Completed (each: model commit → scenario commit → MANIFEST-SHA commit)

| Scenario | New capability (Category C model) | Commits |
|----------|-----------------------------------|---------|
| **1.2** VNIR GSD vs aperture vs altitude | `core.solar_geometry` (LTAN/date/lat → solar zenith; Spencer declination + hour-angle) | model 00efcc5 → scenario b34e518 → manifest 93c7281 |
| **3.1** Orbit geometry & pass planning | `core.orbit` (period, orbital velocity, ground-track speed; adds `mu_earth_m3_s2`) | model e32188e → scenario 760472c → manifest 02eba95 |
| **4.4** Diurnal time-of-day detectability | data-driven (no new model — profile is input data) | scenario 6257eee → manifest 49733ff |
| **4.2** Maritime ship classification | `performance.johnson_criteria` (Detection/Recognition/ID ranges) | model 0df9e15 → scenario d1f2707 → manifest 89fe2ed |
| **1.5** Obscured aperture & spider vanes | spider-vane pupil masking (`optics.n_spiders`/`spider_width_m`/`spider_angle_deg`); implements RADIANT_Optics.md §3.3 | model 36286e7 (+style 6c35307) → scenario bbf9f6f → manifest 01da0e2 |

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

### Remaining (7 scenarios)

- **4.5** (microbolometer) and **6.1** (D*/NETD converters) — **PAUSED for a
  design decision.** Both are NETD/D*/NEP noise-spec converters and should
  share one model; whether that model is a NETD-input-mode, a scaling-law
  converter, or thermal-fluctuation-noise physics is a design call for the
  owner. Resolving it unblocks both.
- **3.3** (multi-sensor comparison framework), **2.4** (multi-frame
  persistence), **6.5** (temperature retrieval / Jacobian), **6.4**
  (multi-target scene / ROC curve), **3.5** (tropical atmosphere / GeoTIFF
  reader / MRT metric) — each a new-model Category C task, not yet started.

## Exit criteria

- 33 of 35 scenarios executed (all but MODTRAN-gated 1.1, 6.2, which carry
  deferral records); each meets the Definition of Done in
  `scenarios/README.md`.
- Registry hygiene: every scenario gap mirrored; plan archived per Rule 24
  when the last non-deferred scenario lands.
