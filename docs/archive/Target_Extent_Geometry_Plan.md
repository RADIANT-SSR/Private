# Target-Extent-to-Geometry Migration Plan

> **⚠ HISTORICAL — COMPLETE.** Archived 2026-07-16. All actionable steps are resolved:
> **Phase A** shipped (`ecf96c5`), **Phase B** closed as structurally infeasible (ADR-0008
> Amendment 3), **Phase G** shipped (`da00f34`), **T2** shipped (`995782f`), and **T3** handed
> off to GUI Phase II (Gap 85). The shipped surfaces are described by ADR-0008 (+ its amendments)
> and `RADIANT_Source_Target_System.md`; this plan is retained as the historical record only and
> is no longer edited.

**Status:** Complete — archived 2026-07-16. *(Prior: Active, drafted 2026-07-15.)* **Phase A shipped**
(`ecf96c5`). **Phase B CLOSED** — not implemented (ADR-0008 Amendment 3): projected-area relocation is
blocked by the T7 descriptor coupling + Rule 7, so it stays in Source. **Phase G shipped** (`da00f34`).
**T2 shipped** (`995782f`). **T3 handed off** to GUI Phase II (Gap 85). The **§4 Update Matrix "B"
column is moot** (Phase B not implemented; Rule 10 unchanged).
**Date:** 2026-07-15
**Implements:** `docs/adr/0008-target-extent-to-geometry-and-scenario-type.md` (Accepted 2026-07-15)
**Depends on:** ADR-0006 (Geometry Stage 0, Accepted) — this plan completes the extent it left in Source
**Executes as:** one phase = one agent task = one conversation (per CLAUDE.md task discipline)
**Gates GUI:** GUI Development Plan is Complete/archived (v1 = "GUI Phase I"); **GUI Phase II must not
start until Phase G of this plan is green** (the migrated boundary + Phase-I GUI regression).

This plan sequences the work; **ADR-0008 defines the what and why and is not re-enumerated here**
(Rule 25/20). Where this plan and the ADR differ, the ADR governs the decision and this plan governs
the sequence.

---

## 1. Goal

Move the target's spatial extent (shape / dimensions / orientation → projected area) and the
**tentative** regime classification from the Source stage to the Geometry stage, leaving Source a
pure spectral/material layer; add a declared `scenario.type` with a declared-vs-derived cross-check;
and do it **results-neutral** (golden byte-identical) while keeping the shipped v1 GUI green. The
end state is the clean stage boundary GUI Phase II builds on: Geometry owns "where / how big / how
oriented / what regime," Source owns "what it radiates."

---

## 2. Ground Rules (binding on every phase)

1. **Results-neutral gate.** Every phase through G relocates computation without changing it. The
   **full golden suite must be byte-identical** and is the acceptance gate; a golden diff is a defect
   that blocks the phase (not a baseline to update). State the pass count in each phase report.
2. **Deprecation-alias mechanics (Rule 7/12).** Every migrated parameter keeps its old dot-path as a
   **deprecated alias** resolving to the new canonical name, with a `DeprecationWarning` on use, for a
   full deprecation window. Precedent: CU-090 (`platform.h_sensor` → `geometry.sensor_altitude_m`),
   CU-093 (range). Provenance records the canonical name; a round-trip test proves alias → canonical.
3. **Stage-output keys are NOT aliased.** `stage_outputs["source"]["regime_tentative"]` /
   `["projected_area_m2"]` move to `["geometry"][...]`. Every reader (API `stage_output_units.py`,
   GUI, tests) is migrated in the same phase that moves the key — there is no back-compat shim for
   stage-output dict keys.
4. **Doc lock-step (Rule 20).** Each phase updates the architecture docs in the Update Matrix (§4)
   **in the same PR** as the code. A code-only PR crossing a documented surface is rejected. CLAUDE.md
   **Rule 10** wording is a first-class lock-step target (tentative owner: SourceStage → GeometryStage).
5. **GUI regression is a first-class gate**, not an afterthought. Phase G runs the full
   `pytest src/radiant/gui/tests/` suite (399 tests as of 2026-07-15) plus a fast full-chain smoke; a
   red GUI suite blocks the migration exactly like a golden diff.
6. **Import rules (Rule 11).** Extent computation moving into `geometry/` must not introduce a
   cross-stage physics import; `import-linter` stays clean. Geometry already imports only
   `radiant.core`.
7. **CHANGELOG (Rule 29).** Each phase that renames/adds a public parameter surface adds an
   `[Unreleased]` entry — a **public-surface** entry (param rename with alias / new `scenario.type`),
   explicitly stating **goldens are byte-identical** (surface change, not results change).
8. **CU discipline (Rule 21/22).** CU-146 (§8 name drift) closes in Phase A. CU-122 (attitude owner)
   is re-audited in Phase B (the tentative-regime relocation is the natural moment). Any new finding
   is CU'd before its phase merges.

---

## 3. Phase Sequence

Effort key: S ≈ one short session, M ≈ one full session, L ≈ may need a split.
Each phase's report carries the §5 Checkpoint. Category per CLAUDE.md validation framework.

### Phase A — Parameter migration (`source.target.*` → `geometry.target.*`)
**Category:** C · **Effort:** M · **Gate in:** none (ADR accepted).
**Scope:** Relocate the extent ParameterDefs from `source/_schema.py` to `geometry/_schema.py`:
`shape`, `shape_radius_m`, `shape_length_m`, `shape_width_m`, `shape_height_m`, `shape_base_radius_m`,
`shape_{yaw,pitch,roll}_rad`, `projected_area_m2` (and any `source.target.*` extent sibling). New
canonical namespace `geometry.target.*`; old paths become deprecated aliases. **No computation moves
yet** — `SourceStage` reads the params through the canonical/alias resolver, so behaviour is
identical. Close **CU-146** by rewriting RADIANT_Source_Target_System §8.2/§8.3 to the canonical names.
**Files:** `geometry/_schema.py` (add), `source/_schema.py` (remove + alias), the alias registry,
`source/stage.py` / `source/_inferrer.py` (read new path).
**Gate:** goldens byte-identical; `sensor.set("source.target.shape", …)` still works and warns;
provenance shows `geometry.target.shape`; round-trip test passes.
**Docs:** §4 rows A.

### Phase B — CLOSED, not implemented (ADR-0008 Amendment 3, owner-ratified 2026-07-16)
**Status: CLOSED — the projected-area computation stays in SourceStage.** Tracing the actual
consumers showed the relocation is structurally blocked: the sole functional reader of the published
area (`spectral_integration/stage.py`) needs the **T7 reference-area** value, which is
descriptor-type-dependent and computable only in SourceStage; and **Rule 7** forbids SourceStage from
writing the adjusted value back into `stage_outputs["geometry"]`. So the key cannot move and Source
must keep computing it; a parallel Geometry computation would be pure redundancy for no gain. The
spatial-vs-spectral value ADR-0008 targeted — the `geometry.target.*` **parameter-namespace** split and
GUI Geometry-tab ownership of shape/orientation — **shipped in Phase A** (`ecf96c5`). Full rationale:
ADR-0008 Amendment 3. **Follow-ups:** CU-147 (write-only `desc.shape`), CU-148 (the both-set area
inconsistency). CU-122 (attitude) stays deferred — no computation moved, so Geometry gained no new
consumer. **No code, no golden change; Rule 10 unchanged.**

### Phase G — GUI Phase-I regression + backend migration (no UX change)
**Category:** D · **Effort:** M · **Gate in:** Phase B merged.
**Scope:** Migrate the **79** `source.target.*` references across the 8 GUI files
(`stage_views.py`, `viewer/viewer_state.py`, `widgets/geometry_angle_panel.py`,
`widgets/target_shape_panel.py`, `widgets/stage_center.py`, + the 3 GUI test files) to
`geometry.target.*`, and move GUI reads of `stage_outputs["source"]["regime_tentative"/"projected_area_m2"]`
to `["geometry"]`. **Intent: zero UX change** — the shipped v1 GUI looks and behaves identically; this
is a pure backend-path migration + regression. Run the **full GUI suite (399)** and a fast full-chain
smoke as the regression gate.
Also migrate the **2 affected scenario scripts** (`4.1_target_detection_matrix`,
`1.3_dual_band_mwir_lwir`) from `source.target.projected_area_m2`/extent paths to canonical
`geometry.target.*`, and smoke-run just those two (§5b) — the exemplar scripts stay warning-free.
**Gate:** full `pytest src/radiant/gui/tests/` green; the shipped Geometry/Source instruments render
identical values (units intact); no extent-path `source.target.{shape,projected_area,shape_*_rad}`
string remains in `src/radiant/gui/` or the 2 scenario scripts except an intentional alias-compat test;
the 2 smoke-run scenarios execute cleanly.
**Docs:** §4 rows G (GUI arch doc note that instruments read `geometry.target.*`; the *presentation
regroup* itself is Phase II, not here).

### Phase T2 — Declared-vs-derived cross-check (build on the existing `source.scene_type`)
**Category:** C–D · **Effort:** S–M · **Gate in:** Phase B merged (G may run in parallel).
**REVISED per ADR-0008 Amendment 1 (2026-07-16):** do **NOT** add a new `scenario.type` param — the
declared axis already exists as **`source.scene_type`** (enum `auto/extended/sub_pixel/point_source`,
wins over inference, drives descriptor spec-form) and the force axis already exists as
**`source.regime_override`**. T2's only new work is the cross-check + doc clarification.
**Scope:** (a) a post-evaluate **declared-vs-derived** cross-check comparing the declared
`source.scene_type` (or its implied regime) against the **OpticsStage final** regime, raising a
**non-fatal, surfaced** warning on mismatch (Rule 17 — named, never silent) on the result object;
(b) docs clarifying `scene_type` = declared intent (guides + cross-checked, non-binding) vs
`regime_override` = hard force (binding). GUI: surface the warning in the Messages panel; no selector
UI yet. Relevance metadata is T3. Naming of `source.scene_type` is left as-is unless T2 shows cause
(Amendment 1 default).
**Files:** the cross-check site (result assembly / performance surface), `api` result surface, GUI
Messages binding. **No new schema param.**
**Gate:** a declared `scene_type='extended'` config whose derived final regime is `point_source`
surfaces the warning; no results change (warning-only surface); goldens byte-identical.
**Docs:** §4 rows T2 + RADIANT_Source_Target_System §7/§8.10 (scene_type vs regime_override distinction).

### Phase T3 — Gap-85 guided setup — HANDED OFF to GUI Phase II (2026-07-16)
**Status: HANDED OFF.** Per this plan's own §7 hand-off provision, T3 (per-regime
parameter-**relevance metadata** on `_schema.py` + API relevance surface + GUI scenario-type selector
+ relevance filtering/badging) is sequenced as **GUI Phase II** instrument work, not the tail of this
plan. Rationale: it is subjective per-parameter physics judgment (owner-guided), it is Phase-II-scale,
and it no longer gates on the ADR-0008 migration. **Gap 85** is updated to PARTIAL → handed to GUI
Phase II. Note: Gap 85 sub-part (c)'s **declared-vs-derived cross-check** already shipped as **T2**
(`995782f`) — only the relevance metadata/selector remains, and that is the Phase-II task.

---

## 4. Architecture Document Update Matrix (Rule 20 lock-step)

Every documented surface this migration crosses, and the phase that updates it **in the same PR**.

| Document / surface | A | B | G | T2 | T3 | What changes |
|---|:-:|:-:|:-:|:-:|:-:|---|
| `docs/adr/0008-*` | — | — | — | — | — | The spec (Accepted; append-only — not edited) |
| **CLAUDE.md Rule 10** | | ✎ | | | | Tentative regime owner: SourceStage → **GeometryStage**; stage-2 final in Optics unchanged |
| **CLAUDE.md** package layout / stage table | | ✎ | | | | Geometry owns target extent + tentative regime; Source = spectral only |
| `RADIANT_Master_Architecture.md` | | ✎ | | ✎ | | Stage-ownership map; scenario.type as a declared surface |
| `RADIANT_Geometry.md` | ✎ | ✎ | | | | Geometry now owns `geometry.target.*` extent, projected area, tentative regime |
| `RADIANT_Source.md` | ✎ | ✎ | | | ✎ | Source loses extent/regime; reads `projected_area_m2` from geometry; relevance |
| `RADIANT_Source_Target_System.md` | ✎ (CU-146) | ✎ | | | ✎ | §5 target geometry, §7 two-stage dispatch (tentative moves), §8 inventory → `geometry.target.*` |
| `RADIANT_Signal_Chain_Architecture.md` | | ✎ | | ✎ | | ChainState flow: which stage emits `regime_tentative`/`projected_area_m2`; cross-check surface |
| `RADIANT_Parameter_System.md` | ✎ | | | ✎ | ✎ | New `geometry.target.*` names + aliases; `scenario.type`; relevance metadata field |
| `RADIANT_GUI_Architecture.md` §4.4.1 | | | ✎ | ✎ | ✎ | Instruments read `geometry.target.*`; **Phase-II regroup + scenario.type selector spec** |
| `RADIANT_File_Tree.md` | ✎ | ✎ | | | | Any file moves (shape modules) + schema ownership |
| `RADIANT_Conventions.md` | | ✎ | | | | Regime/scenario convention note if touched |
| `docs/tracking/Cleanup_Backlog.md` | ✎ (close CU-146) | ✎ (CU-122 re-audit) | | | | CU closures/re-audits |
| `docs/tracking/gaps.md` | | | | | ✎ | Gap 85 status transitions |
| `CHANGELOG.md` | ✎ | ✎ | ✎ | ✎ | ✎ | Public-surface entries; each states goldens byte-identical |

`✎` = updated in that phase. A phase is not done until its matrix rows are updated (self-review, Rule 20).

---

## 5. GUI: Phase-I Regression → Phase-II Handoff

**Phase-I regression (Phase G) is mandatory and inside this plan** because the migration renames
params (79 GUI references) and relocates stage-output keys the shipped instruments read. Phase G proves
the v1 GUI is byte-for-byte unchanged in behaviour against the migrated backend — a required gate.

**GUI Phase II starts only after Phase G is green.** The clean boundary this plan produces is exactly
what Phase II needs. The first Phase-II tasks (specified in `RADIANT_GUI_Architecture.md` §4.4.1, updated
in Phase G/T2) are:
1. **Geometry-tab regroup** — host the target shape/orientation controls (now genuinely `geometry.target.*`)
   on the Geometry tab beside the engagement geometry; the Source tab becomes spectral/material only.
   This is a *presentation* change enabled by — but deliberately separate from — the architecture move
   (kept out of Phase G, which is regression-only).
2. **`scenario.type` selector** on the Geometry/Source header (consumes T2's declared type + cross-check).
3. **Relevance badging** (T3) once the metadata lands.

Handoff artifact: when Phase G + T2 merge, update the GUI arch doc §4.4.1 and open a GUI Phase II plan
(or reopen the sequence) with these as its first instrument tasks. **This plan does not itself execute
the Phase-II regroup** — it hands off a correct, regression-proven boundary.

---

## 5b. Scenario Impact & Regression Scope

The migration **splits** the `source.target.*` namespace — it does **not** rename it wholesale. Only
the *extent* params move to `geometry.target.*` (`projected_area_m2`, `shape*`, orientation); every
spectral/material param (`source.target.temperature`/`emissivity`/`reflectance`/`user_radiance_path`/
`is_hot_target`/`fill_fraction`) **stays in Source**. This bounds the scenario blast radius sharply.

**Impact (measured 2026-07-15):**
- **Affected:** exactly the extent-setters — **2 scenario scripts, ~4 references** (`4.1_target_detection_matrix`,
  `1.3_dual_band_mwir_lwir`, via `sensor.set("source.target.projected_area_m2", …)`). Deprecation
  aliases keep them working (with a `DeprecationWarning`) — **nothing breaks**.
- **Unaffected:** every scenario setting spectral/material `source.target.*` props (5.5, 6.1, 6.3, 6.4,
  7.2, 7.5, 4.3, 4.4, 4.5, …) — those paths do not move.
- **Numerically results-neutral:** scenario outputs are byte-identical (the migration relocates, never
  recomputes), so no scenario's expected values drift.

**Regression decision — do NOT re-run all 37 scenarios.**
- Scenarios are **not automated** (nothing in `tests/`/CI references `scenarios/`) — they are manual
  example scripts + walkthroughs. Re-running all of them would be manual effort that the **golden suite
  already subsumes**: byte-identical goldens are a stronger numerical-equivalence proof than re-executing
  examples.
- **In-scope regression work** (folded into Phase A/G): (1) migrate the **2 affected scripts** to canonical
  `geometry.target.*`; (2) **smoke-run only those 2** post-migration to confirm clean execution; (3) update
  stale extent-name prose in those 2 walkthrough/`gui_workflow.md` files **only if** the phase already
  touches them (point-in-time records otherwise — no mandatory churn).
- The golden suite (ground rule 1) remains the authoritative numerical regression for all scenario physics.

## 6. Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| A relocated computation subtly changes a golden | Every phase A–G is results-neutral by construction; the full golden suite is the gate; a diff blocks the phase. Phase B is the high-risk one (computation actually moves stage) — diff the pre/post `stage_outputs` for a golden config as an extra check. |
| Stage-output key move breaks an un-migrated reader | Ground rule 3: keys are not aliased; grep every reader (`api`, `gui`, tests) and migrate in the same phase. Phase G's "no `source.target.*` remains" grep is the backstop. |
| Deprecation alias drifts (old path silently wrong) | Round-trip test (alias → canonical) + provenance assertion per Phase A; `DeprecationWarning` surfaced. |
| Rule 10 change ripples into other rule text | CLAUDE.md Rule 10 + Master Architecture updated together in Phase B; self-review checks all rule cross-refs. |
| Scenario.type cross-check tempts a physics override | ADR is explicit: declaration never overrides derivation; T2 is warning-only; goldens byte-identical proves it. |
| CU-122 (attitude) re-audit expands scope | Re-audit only records close/refresh in Phase B; the attitude *implementation* stays deferred (no v1 consumer) unless the owner charters it. |
| GUI Phase II blocked waiting on T3 | T3 (relevance) is explicitly allowed to trail into Phase II; the regroup (Phase-II task 1) needs only Phase G. |

---

## 7. What Done Looks Like

- `geometry.target.*` owns shape/dims/orientation/projected-area; `source.target.*` resolves as
  deprecated aliases; provenance shows canonical names.
- `GeometryStage` emits `projected_area_m2` + `regime_tentative`; `SourceStage` reads them and is
  purely spectral/material; `OpticsStage` final regime unchanged.
- `scenario.type` declares intent, seeds the override default, and cross-checks against the derived
  regime with a surfaced warning — never overriding the physics.
- The full golden suite is **byte-identical** to pre-migration through Phase G; the full GUI suite is
  green with **zero UX change**.
- Every doc in the §4 matrix is updated; CLAUDE.md Rule 10 names GeometryStage; CU-146 closed;
  CU-122 re-audited; Gap 85 advanced.
- GUI Phase II can begin from a correct, regression-proven boundary; §4.4.1 specifies the regroup.
- This plan moves to `docs/archive/` with a completion banner when Phase G + T2 land (T3 may hand off
  to the GUI Phase II plan) — Rule 24.
