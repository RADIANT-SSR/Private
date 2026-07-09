# T3–T4 Gap Closure Plan

Status: Active (2026-07-08)
Author: Coding agent, approved by project owner
Scope: Close the framework gaps discovered while executing the Tier-3 and
Tier-4 scenarios — registry entries **Gap 42–54** in
`docs/tracking/gaps.md` (Rule 25 — referenced, not re-enumerated). Distinct
from the archived `Gap_Closure_Plan.md`, which closed the earlier
refresh-scenario gaps.
Process rules: `CLAUDE.md` (the 29 rules), `docs/guides/scenario_testing.md`
for any scenario reruns.

---

## Ground rules (every gap)

1. **One computation, one module** (Rule 19): each new metric/model/helper
   gets its own file with Level-0 truth-anchor tests written first (Rule 18).
2. **Doc + CHANGELOG lock-step** (Rules 20, 29): a public-surface or
   results-affecting change updates the matching `RADIANT_*.md` and adds a
   `[Unreleased]` CHANGELOG entry in the same commit.
3. **Default preserves results.** New parameters/metrics default to the
   historical behavior; verify byte-identical goldens for anything that
   touches the chain (per the Wave-A/B "zero result-risk" claim).
4. **CU closure protocol** (Rule 22): each gap is closed by moving its
   `gaps.md` entry to a RESOLVED state with the linked commit SHA; the
   Summary-Table row is updated to FIXED.
5. **Gates before each commit:** `pytest` (touched suites), `ruff`,
   `lint-imports`, `mypy --strict` on core/api, `check_org_rules.py`.

---

## Wave A — Zero result-risk additions (metrics, models, helpers)

These add new outputs, standalone models, or analysis helpers. None change
any existing computed value, so no golden review is needed — only a
byte-identical spot check where the chain is touched.

| Gap | Deliverable | Location | Effort |
|-----|-------------|----------|--------|
| **49** | Diffraction-limited-resolution metric (`1.22 λ · range / D` → ground; and the angular form) | new `performance/diffraction_limit.py` + `stage.py` metric wiring | Trivial |
| **50** | Sampling-regime label metric (detector- vs diffraction-limited from `q_center`) | `performance/stage.py` (+ tiny helper module) | Trivial |
| **51** | Revisit / repeat-ground-track model (nodal regression, J2 repeat cycle, track spacing) | new `core/repeat_ground_track.py`, consumes `core.orbit` | Medium |
| **54** | Arbitrary/measured pupil-mask injection (`mask_override` array) | `optics/pupil_amplitude.py`, threaded like `SpiderVaneSpec` | Low–Med |
| **45** | Detector-comparison metrics (BLIP T, dark-current crossover T, NEI) | new `api/detector_compare.py` (or `performance/`) helper | Small |
| **46** | Calibration-analysis helpers (responsivity, linearity, calibration uncertainty) | new `api/calibrate.py` (sweep → fit report) | Small |

**Order:** 49 → 50 (fastest, immediate scenario value) → 54 → 51 → 45 → 46.

## Wave B — Config-surface / spectral-input family (result-preserving when unset)

A shared theme: physics exists internally but has no user-facing input
path. These are result-preserving because the default leaves the new input
unset (scalar/legacy behavior). Gaps 44 and 47 share tabulated-spectral
plumbing and should be done adjacently.

| Gap | Deliverable | Location | Effort | Status |
|-----|-------------|----------|--------|--------|
| **44** | Spectral QE config path (wire `detector.qe_table_path`) | `api/session.py` (Rule 6 IO) | Medium | **DONE (dd1529f)** |
| **48** | QE temperature dependence (QE(T)) | `api/session.py` + `detector/_schema.py` | Small–Med | **DONE (b4b7d2e)** |
| **47** | Spectral target emissivity path (`source.target.emissivity_path` → spectral thermal descriptor) | `source/_schema.py` + `source/_inferrer.py` | Medium | **RECLASSIFIED — architecture task (see below)** |
| **42** | `lab_test` / `ground_test` sub-cases reachable from config | `io/config.py` + source background | Small→Medium | **RECLASSIFIED — architecture task (see below)** |

**Done (44, 48):** both reused the existing `spectral_integration.qe_curve`
injection hook and are result-preserving by default (goldens intact).

**Reclassified out of Wave B (47, 42):** on inspection these are not the
simple config wiring the plan assumed — they extend architecture and carry
real blast radius, so each becomes its own focused task:
- **47** touches `source/_inferrer.py`, the ADR-governed source **spec-form
  router** (S8/S11/S1…), and needs a new `emissivity_path` input mode with
  mutual-exclusivity validation against `brightness_temperature_path` /
  `user_radiance_path` / scalar emissivity. The physics is already
  supported (`SurfaceMaterial.emissivity` accepts `ε(λ)` arrays); the risk
  is the router logic, where a subtle bug mis-builds the source for many
  configs beyond the golden set. Working S8 workaround exists (scenario 4.3).
- **42** touches `io/config.py` config-loading + the source-background
  injection path, with an "illumination follow-on ADR" anchor. Working
  `space`-subcase workaround exists (scenario 7.4).

Both should be started with the relevant ADR + internals read first, then a
full source-suite + golden run. Not blocking — documented workarounds ship.

## Wave C — Results-affecting fidelity (golden review required)

These change computed numbers. Each needs the golden-update protocol
(`RADIANT_Testing_Validation.md §5.3`), a **Results-affecting:** CHANGELOG
entry with direction/magnitude, and explicit owner-visible justification.

| Gap | Deliverable | Result impact | Effort | Status |
|-----|-------------|---------------|--------|--------|
| **43** | NEDT exact `dS/dT` path (retire the single-λ Planck-factor approximation) | NEDT shifts slightly for all thermal configs | Small (code) + golden review | **DONE (0b33061)** |
| **52** | First-class extended target-vs-background differential | `contrast_snr` a true differential in EXTENDED | Medium + golden review | **DONE (3192f67) — ADR-0005 Option A** |

**Gap 43 done (owner-greenlit golden change):** exact band-integrated dS/dT
via the Planck log-derivative; reduces to the old single-λ form exactly in
the narrow-band limit; NEDT shifts ~±0.3% LWIR / +4.5% wide MWIR. No golden
asserted NEDT; two Option-C anchors repinned with provenance.

**Gap 52 done (3192f67) — ADR-0005 Option A implemented.** New opt-in
`source.contrast_reference.*` makes the extended `contrast_snr` a true
two-pixel differential (nulls at radiance crossover), combined noise
√(N_t²+N_ref²); the reference is noise-decoupled, so Decision #13's SNR
architecture (and the Option-C anchors) is preserved and Decision #15's
deprecated params are untouched. Default leaves all results unchanged
(verified: 10 golden + 8 anchor + 817 unit tests). ADR-0005 → Accepted.
Optional follow-on: migrate scenarios 4.3/4.4 off the manual workaround.

## Deferred — own charter

| Gap | Why deferred | Re-audit |
|-----|--------------|----------|
| **53** | Johnson MRC/MRT contrast-limited DRI is Medium–Large and couples to a rescope of scenario 4.2. It needs its own Category-C charter (MRC/MRT curve from the system MTF + noise, then a contrast-limited `johnson_range_m` variant). Not blocking — the sampling-limited geometric bound is shipped and documented. | When scenario 4.2 is rescoped, or 2026-10-01 |
| **47** | Source spec-form router extension (see Wave B note). Architecture task; ε(λ) descriptor support already exists, S8 workaround ships. | Next source-subsystem task, or 2026-10-01 |
| **42** | Config-loading + source-background architecture (see Wave B note). `space`-subcase workaround ships. | Next io/config task, or 2026-10-01 |

Also **out of this plan:** the 4.5 (microbolometer) / 6.1 (D*/NETD) noise-spec
converter design decision — that is a *scenario* prerequisite tracked in the
Scenario Execution Plan, not a T3/T4 registry gap.

---

## Exit criteria

- **Closed (10):** Gaps 43, 44, 45, 46, 48, 49, 50, 51, 52, 54 — RESOLVED in
  `gaps.md` with commit SHAs, Summary-Table rows FIXED.
- **Deferred with re-audit records (3):** Gaps 47, 42 (architecture tasks)
  and 53 (own charter) — see the Deferred table (Rule 22).
- Only Gap 43 changed results (NEDT, small, owner-greenlit, provenance-
  pinned); the other 9 closed gaps are additive or default-preserving
  (Gap 52's contrast reference is opt-in).
- Every closed gap has a Level-0 test; `mypy --strict` clean on core/api;
  import-linter and org-rules pass. ✓
- Plan archived per Rule 24 once the four deferrals are done or re-docketed;
  until then it stays Active (the deferrals keep it open).

---

## Progress log

- **2026-07-08 — Wave C, Gap 43 closed (0b33061).** Exact band-integrated
  NEDT dS/dT (Planck log-derivative) in `SpectralIntegrationStage`;
  `PerformanceStage` uses σ/(dS/dT), single-λ form as fallback. Reduces to
  the old formula exactly in the narrow-band limit; NEDT shifts ~±0.3% LWIR,
  +4.5% wide MWIR. No golden asserted NEDT; 2 Option-C anchors repinned.
  4 new tests. **Owner greenlit the golden change.**
- **2026-07-08 — Wave C, Gap 52: ADR drafted, accepted, implemented
  (f302f48 → 3192f67).** ADR-0005 Option A: opt-in
  `source.contrast_reference.*` → extended `contrast_snr` is a true
  two-pixel differential nulling at crossover, combined noise, noise-
  decoupled (Decisions #13/#15 preserved). Default unchanged; 5 tests +
  goldens/anchors verified. **Gap-closure pass complete: 10 gaps closed
  (Wave A ×6, B ×2, C ×2); 3 deferred (47, 42, 53) with re-audit records.**

- **2026-07-08 — Wave A, Gaps 49 + 50 closed (63f599d).**
  `performance/diffraction_limit.py` (`diffraction_limit_angular_urad`,
  `diffraction_limit_ground_m`) and `performance/sampling_regime.py`
  (`sampling_regime_code`), wired into `PerformanceStage`. Additive
  metrics; 10/10 goldens unchanged; 16 Level-0 tests. `gaps.md` entries
  RESOLVED, Summary-Table rows FIXED.
- **2026-07-08 — Wave A, Gap 51 closed (c4c01b7).**
  `core/repeat_ground_track.py` — J2 nodal regression, sun-sync
  inclination, ground-track spacing, first-order revisit; adds `J2_earth`.
  Standalone model, no chain change; 12 Level-0 tests. Exact repeat-cycle
  revisit noted out-of-scope. RESOLVED / FIXED.
- **2026-07-08 — Wave A, Gaps 45 + 46 closed (d916bd3).**
  Gap 45: `performance/dark_crossover_rate.py`, `blip_rate.py`,
  `noise_equivalent_irradiance.py` (detector FOM). Gap 46:
  `api/calibration_analysis.py` (`analyze_calibration` → `CalibrationReport`).
  18 Level-0 tests; pure helpers, no chain change.
- **2026-07-08 — Wave A complete: Gap 54 closed (f4224ad).**
  `make_pupil_amplitude` `mask_override`, injected via
  `optics_config["pupil_mask_override"]`; threaded into both PSF and MTF
  paths (Rule 4). Default byte-identical — 504 optics + 10 golden tests
  unchanged; 8 tests. **Wave A (Gaps 45, 46, 49, 50, 51, 54) done.**
- **2026-07-08 — Wave B, Gap 44 closed (dd1529f).** `RadiantSession` wires
  `detector.qe_table_path` → `io.qe_csv` → injected `qe_curve` (Rule 6).
  Default byte-identical (goldens intact); 4 integration tests. import-linter
  whitelist extended for the new api→io.qe_csv→core edge.
- **2026-07-08 — Wave B, Gap 48 closed (b4b7d2e).** QE(T) via
  `detector.qe_temperature_coeff_per_K` + `qe_temperature_ref_K`, applied
  at the API layer (option b — Rule 11 keeps it out of the stage).
  Results-affecting only when coeff≠0; default byte-identical; 4 tests.
- **2026-07-08 — Wave B halted after 44 + 48; Gaps 47 & 42 reclassified.**
  On reading the internals, 47 (source spec-form router) and 42 (config +
  source background) proved to be architecture extensions, not simple
  config wiring — reclassified as own-charter tasks with re-audit records
  (see Deferred). Owner-approved stop. **8 gaps closed total this pass
  (Wave A ×6 + 44 + 48); Wave C awaits the golden-review gate.**
