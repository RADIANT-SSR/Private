# CU Autonomous Cleanup Plan

**Status:** Active — 2026-07-19. Owner green-lit autonomous execution; owner-gated CUs
dispositioned 2026-07-19 (below) and scheduled into Waves 7–10.

## Owner decisions on the gated CUs (2026-07-19)

| CU | Decision | Disposition |
|----|----------|-------------|
| CU-122 + CU-082/053/054/056 | **Delete** the broken `geometry_gui_v2` VTK prototype (superseded by the 2D viewer) | Wave 7 — one deletion closes 5 CUs |
| CU-084 | **Delete** the unwired shadow legacy source (Rule 27) | Wave 7 |
| CU-077 | **Delete** the dead `read_noise_is_post_cds` param + doc-only `cds_1f_suppression` | Wave 7 |
| CU-104 | **Amend the design-system doc** (letter-spacing/casing are nominal; Qt QSS can't render them) | Wave 7 (doc-only) |
| CU-103 | **Keep the fallback** — do not bundle IBM Plex; close as won't-bundle (Declined) | Wave 7 (close-out) |
| CU-138 | **Restore** the qtconsole in-process kernel (headless test strategy or manual-verify; REPL stays fallback) | Wave 8 |
| CU-115 | Build pin-set persistence via `QSettings` | Wave 8 |
| CU-139 | Add a `dark=` seam to `radiant.api.plot` so the theme toggle re-renders dark figures | Wave 8 (stretch) |
| CU-120 | Expose the geometry mode manifest via a public accessor (design proposed in-wave) | Wave 8 |
| CU-096 | **Approved** — off-nadir θ_o/η fix; **Results-affecting** golden refresh | Wave 9 (physics) |
| CU-166 | **Approach 2** — PerformanceStage metric-applicability gating (NIIRS N/A when out of GIQE-5 envelope, opt-in for the extrapolated value) + MWIR→IIRS label routing | Wave 9 (metric layer) |
| CU-165 | **Approved** — profile + optimize the PSF-path grid sizing at high Q (Rule-4 consistency regression) | Wave 9 (PSF numerics) |
| CU-170 | Investigate each of the 12 saturating baselines' intent; re-center accidental ones, document deliberate ones | Wave 10 (per-scenario) |
| CU-116 | Attempt a safe-fix candidate (deferred close / non-pyplot figures) | Wave 10 |
| CU-164 | Focused per-file runner refactor + 20-figure regeneration + tooling cleanup | Wave 10 |
| CU-011, CU-087 | **Parked** — need a real MODTRAN *binary invocation* to validate; cannot be done here | not scheduled |
| CU-137 | **Parked** — needs an owner-facing cross-stage "Acquisition" grouping design (no yes/no) | not scheduled |

Risk ordering: Wave 7 (safe deletions + docs) → Wave 8 (GUI features) → Wave 9
(category-C physics/metric, golden-touching — full golden suite verified per CU) →
Wave 10 (investigation + careful refactors). Waves 9–10 checkpoint and merge individually.

### Waves 7–10 outcome (2026-07-19/20)

- **Wave 7 (done, merged):** deleted `geometry_gui_v2` → closed CU-082/053/054/056 + CU-122(i);
  CU-084 (dead source exports removed), CU-077 (dead CDS param removed + doc fix), CU-104 (typography
  spec amended), CU-103 (declined bundling). Full suite green.
- **Wave 8 (done, merged):** CU-139 (`plot_theme` dark-figure seam + GUI wiring), CU-115 (pin
  persistence via QSettings). CU-138 **blocked-on-dep** (qtconsole not installed here);
  CU-120 **needs a design pass** (mode structure is implicit in the resolvers). Full suite green.
- **Wave 9 (assessed → all flagged for focused passes):** CU-165 (PSF-perf hotspot located; both
  optimizations change PSF discretisation → need validated result-invariance), CU-096 (owner-approved
  fix **already landed** in Phase 2; residue is a subtle θ_o/η fallback correction no golden exercises),
  CU-166 (approach-2 is a metric-contract change needing a threshold/opt-in design + multi-scenario
  golden refresh). None rushed — category-C physics/metric risk.
- **Wave 10 (assessed → flagged):** CU-116 (proven to deadlock in matplotlib's Qt backend; both
  safe-fix candidates carry re-entrancy/api-wide risk), CU-164 (coupled 20-file refactor + 20-figure
  regen), CU-170 (per-scenario intent triage + golden-moving baseline re-centering).

**Disposition:** all remaining Open CUs are either owner-decision-closed (103 declined),
dependency-blocked (138, 011, 087), or **precisely-investigated focused-pass items** with
findings recorded in the backlog. No category-C physics/metric/numerics or golden-moving
scenario change was rushed at the tail of the run.

## Progress (2026-07-19)

**Resolved & merged to `main` (24):** Wave 1 — CU-149, 150, 151, 152. Wave 2 — CU-114,
100, 112, 102, 099, 089. Wave 3 — CU-136, 113, 135, 111. Wave 4 — CU-109, 105, 121, 108,
107, 118. Wave 5 — CU-070, 071, 085. Wave 6 — CU-080. Each: own commit + SHA-linked backlog
closure; every wave's static gates + full fast suite green (last: 4442 passed, 0 failed); no
golden physics result changed. Backlog Open count: 48 → 24.

**Flagged / gated (not done, each recorded in the backlog):**
- **CU-116** — INVESTIGATING: the mechanical fix deadlocks C-level in matplotlib's Qt
  backend under offscreen (faulthandler-confirmed); reverted, 3 safe-fix candidates recorded.
- **CU-164** — re-scoped: not a bulk guard-add but a coupled per-file refactor (separate
  interleaved analysis from importable factories across 20 scripts + regenerate 20 figures +
  drop the tooling halt-hack). Needs a focused, verified pass; still cleanly worked around today.
- **CU-110** — stays Open+**gated** (no concurrent evaluation; a lock would wrongly serialize
  whole evaluations, the thread-local fix isn't warranted yet).
- **CU-126** — stays Open+**gated** (the schematic's `°` display is provably correct for the
  angle-only arc catalog; radians `stage_output_unit` is not the right source until a non-angle
  arc is added).

**Remaining actionable:** none — CU-120 resolved 2026-07-20 (focused pass, commit
`41b8158`: manifest owned by `radiant.geometry.mode_manifest`, public via the
`radiant.api.geometry_modes` bridge; owner-ratified design); CU-139 resolved in Wave 8.

## Goal

Work through every open Cleanup-Backlog CU that can be resolved **without owner
feedback** — a well-specified, already-decided fix with no results-affecting golden
move and no architectural or product decision left open. Owner-gated CUs are
enumerated separately (below) so they can be unblocked deliberately, but this plan
does not wait on them.

Source of truth: `docs/tracking/Cleanup_Backlog.md` (48 open CUs as of 2026-07-19).

## Execution protocol (per repo rules)

- **One wave = one short-lived branch off `main`**, per-CU commits inside it, gates
  green, then merge the wave to `main` (fast-forward) in the same session and delete
  the branch. (Multi-Agent Git Hygiene; overnight-autonomy convention.)
- **Per-CU discipline:** R22 close-out (move the entry to Resolved with the commit
  SHA + date), R20 doc lock-step, R29 CHANGELOG under `[Unreleased]` for any
  user-observable change. Registry edits are small/append-only/committed immediately.
- **Gates before each wave merge:** `ruff check src/`, `mypy --strict src/radiant/core
  src/radiant/api`, `lint-imports`, `python scripts/check_org_rules.py`, and the
  relevant `pytest` scope (targeted per CU; full suite at wave close).
- **Stop-and-flag rule:** if any "autonomous-safe" CU turns out to move a golden,
  cross an architectural decision, or need a product call once opened, I stop that CU,
  leave it Open with a note, and continue with the rest — it becomes an owner-gated
  item, not a guess.

## Autonomous-safe waves (29 CUs)

### Wave 1 — Cross-platform (Rule 30) — category A/B, no macOS results change
- **CU-149** — add `encoding="utf-8"` to every text-mode `open`/`read_text`/`write_text`
  in `src/`, `scripts/`, `dev_tools/`; enable ruff `PLW1514`.
- **CU-150** — root `.gitattributes` (`* text=auto eol=lf` + binary `-text`); `newline="\n"`
  on the tape5 write.
- **CU-151** — MODTRAN `binary_path` default → platform-conditional (`shutil.which`) or
  required-in-MODTRAN-mode; Windows-example `action` text. (Check no golden depends on it.)
- **CU-152** — replace `install_deps.sh` with a cross-platform requirements file / Python
  script (or document the manual commands).

### Wave 2 — Doc & dead-code hygiene — category A
- **CU-114** — delete the dead `#stageGapPanel` QSS block.
- **CU-100** — import `R_EARTH_M` from `constants`, drop the local `EARTH_RADIUS_M`
  (values already equal — no numeric change).
- **CU-112** — regenerate the `RADIANT_File_Tree.md` `gui/widgets/` block from the live tree.
- **CU-102** — regenerate the `RADIANT_File_Tree.md` file-count totals.
- **CU-099** — add a CI/static check that `parameter_reference.md` matches the registry
  (pattern of `check_org_rules.py`); regenerate the committed copy.
- **CU-089** — `ruff check tests/ --fix` + hand-fix the remainder; widen the documented
  gate to `src/ tests/`.

### Wave 3 — GUI view-only polish — category A/D, no physics/results
- **CU-136** — relabel `plot_psf` default axes "x/y (PSF samples)".
- **CU-135** — render non-finite `angular_extent_rad` as a themed sentinel; skip
  `None`-valued descriptor keys in the Source Outputs readout.
- **CU-111** — Parameter Editor: after Apply, adopt the chosen combo unit on the Current line.
- **CU-113** — summarize nested ndarrays in `inspect_result` (`ndarray(shape=…, dtype=…)`).
- **CU-116** — bound the per-stage matplotlib figure count (close on deselect / lazy build).

### Wave 4 — Public-API accessors & their dependents — category A/B, no results (R20 doc lock-step)
- **CU-105** — `Sensor.provenance(dotpath)` structured accessor; delete `provenance_from_explain`.
  - **CU-121** *(depends on 105)* — refresh the Geometry form on tree edits via a resolvability guard.
- **CU-109** — `radiant.api.units.units_for(canonical_unit)` accessor; repoint GUI + CLI.
- **CU-108** — metric display-scaling helper (NEDT → mK, etc.) in `metric_format.py`.
- **CU-107** — resolver raises `ParameterBoundsError` (why/action/context) for bounds/enum
  violations instead of flat `CoreValidationError` (audit exact-type test asserts first).
- **CU-118** — stages declare scalar-output units at the emission site; accessor aggregates.
  - **CU-126** *(depends on 118)* — arc value-label unit sourced from the output key.
- **CU-120** — expose the geometry mode manifest through the public API; drop the literal grouping.
- **CU-110** — thread-local `showwarning` capture in `EvaluationWorker` (behavior-preserving today).

### Wave 5 — MODTRAN robustness + validation soft-spots — category A/B (limited testability — careful)
- **CU-070** — include the binary version/hash in the MODTRAN cache key.
- **CU-071** — validate arrays before clamping τ/L_path; raise on gross violations, clamp only float-noise.
- **CU-085** *(2 remaining sub-items)* — (7) add tests for the readout digital-TDI branches;
  (3) coverage-fraction threshold before warning on constant-extrapolated curves.

### Wave 6 — Reference-data provenance + runner guards — category A
- **CU-080** — provenance manifests (generator+source) for detector-QE / solar / emissivity
  grids; fix the atmospheres README; label synthetic curves.
- **CU-164** — add `if __name__ == "__main__": main()` guards to the 20 unguarded scenario
  runners; regenerate figures once to confirm byte-identical; drop the `_StopModuleExec` halt.

### Stretch (autonomous but larger surface — do if waves 1–6 land clean)
- **CU-139** — optional `dark=`/rcParams seam on `radiant.api.plot` so the theme toggle can
  request a dark figure through the public surface. (New public-API surface → R20 doc.)

## Owner-gated — excluded from autonomous execution (need a decision or move a golden)

| CU | Why it needs you |
|----|------------------|
| CU-166 | Four candidate approaches; **approach decision pending owner** (metric-applicability gating is a contract change). |
| CU-170 | Re-centering 12 shipped baselines **moves goldens**; each needs an intentional-vs-accidental-saturation call. |
| CU-096 | Off-nadir θ_o/η fix is **results-affecting** (Geometry_Stage_Plan Phase 2 scope). |
| CU-165 | PSF-path perf change touches the numerics (category C, golden-risk); wants owner awareness. |
| CU-104 | Owner call: render tracking/casing in Qt vs. amend the design-system doc. |
| CU-103 | Owner call: bundling IBM Plex `.ttf` is a licensing/packaging decision (font *resolution* already shipped, CU-169). |
| CU-138 | Owner call: restore the qtconsole kernel vs. drop the unused pin for v1. |
| CU-137 | Gated: no cross-stage "Acquisition" grouping is designed yet. |
| CU-122 | Architectural: `observer_*` attitude has no stage owner (ADR-0006 §4 open) + repair-or-delete the dev-tool shell. |
| CU-084 | Decide delete-as-unused vs. wire-and-document (with the CU-079 Source reconciliation). |
| CU-077 | Implement-both-or-delete + category-C physics (`cds_1f_suppression`). |
| CU-011 | MODTRAN two-leg τ aliasing — physics, needs real-MODTRAN validation. |
| CU-087 | Gated on CU-011 / the MODTRAN binary flavor becoming exercisable. |
| CU-115 | Gated on the Phase-9 preferences/`QSettings` surface (doesn't exist yet). |
| CU-082, CU-053, CU-054, CU-056 | The `geometry_gui_v2` prototype is **broken** (CU-122, imports deleted dataclasses); these perf/memory/record passes are moot until it is repaired-or-deleted. |

## Acceptance

- Every autonomous-safe CU is Resolved (moved to the Cleanup-Backlog Resolved section
  with a linked SHA + date), or left Open with a stop-and-flag note if it tripped the
  stop rule.
- All gates green on `main` after each wave merge; full suite green at plan close.
- No golden physics result changed (any that would have → escalated to owner-gated).
- A morning summary lists per-CU: SHA, what changed, and any escalations.
