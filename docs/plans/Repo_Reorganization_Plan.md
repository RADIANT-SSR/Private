# Repo Reorganization Plan

**Status:** Draft — awaiting owner approval of `docs/OPERATING_MODEL.md` and decision points below
**Source:** `docs/reports/organization_audit_2026-07/Project_Organization_Audit.md` (this plan is that audit's Rule-28 disposition)
**Scope:** Move/retire/fix every misplaced or stale artifact in the repo per the Operating Model. **No physics code changes.** The only `src/` edits permitted are mechanical docstring path fixups (Phase B) and none land until the in-flight `fix/architecture-audit-2026-07` branch merges.

---

## Execution Rules (how the remaining work runs)

1. **One phase = one branch = one PR.** Phases land in order A → E; each is independently revertable.
2. **Moves are `git mv`, never delete+recreate** — history must follow the file.
3. **Nothing in this plan touches** `src/` physics, `tests/`, `data/`, or any file the in-flight branch modifies (`Cleanup_Backlog.md`, `src/**` — see Phase E gating).
4. **Every phase PR ends with the §4 hygiene checklist** from OPERATING_MODEL.md and a link-integrity check: `grep -rn 'docs/[A-Z]' --include='*.md' --include='*.py' .` for the paths that phase moved.
5. **Each phase closes CUs it resolves and files CUs it uncovers** (Rules 21/22). This plan itself moves to `docs/archive/` in the Phase E PR (Rule 24).
6. When a step conflicts with something the other agent has changed since this plan was written, **stop and re-inventory that file** — don't force the move.

---

## Phase A — Git hygiene (~30 min, zero risk)

- [ ] Append to `.gitignore`: `.~lock.*#`
- [ ] `git rm --cached` the 3 tracked lock files (scenarios 2.3, 3.2, 6.3) and every tracked `.DS_Store` (`git ls-files | grep DS_Store`)
- [ ] Delete untracked junk: remaining `.~lock` (scenario 5.1), on-disk `.DS_Store` files
- [ ] Delete committed plot outputs: `examples/scripts/aperture_sweep_snr.png`, `scripts/spatial_audit_plots.png` (regenerable by their scripts)
- [ ] Delete `scenarios/07_karen_test_engineer/7.3_*/scripts/__pycache__/`

## Phase B — docs/ taxonomy (~half day)

Create `docs/architecture/`, `docs/tracking/`, `docs/plans/` (exists), `docs/reports/cu_tasks/`. Then execute the disposition table below. `docs/archive/` stays flat.

### Disposition table — every current file in docs/

**→ `architecture/`** (normative specs; filenames unchanged):
`RADIANT_Master_Architecture.md`, `RADIANT_Signal_Chain_Architecture.md`, `RADIANT_Conventions.md`, `RADIANT_Parameter_System.md`, `RADIANT_Testing_Validation.md`, `RADIANT_Config_Format.md`, `RADIANT_Scripting_API.md`, `RADIANT_Atmosphere.md`, `RADIANT_Optics.md`, `RADIANT_Detector_Complete.md`, `RADIANT_Spatial_Complete.md`, `RADIANT_Source_Target_System.md`, `RADIANT_Scan_Timing.md`, `RADIANT_Metrics.md`, `RADIANT_Metric_Dependencies.md`, `RADIANT_Physics_Inventory.md`, `RADIANT_Scope_Decisions.md`, `RADIANT_Personas.md`, `RADIANT_File_Tree.md`, `RADIANT_Use_Case_Matrix.md`, `RADIANT_Target_Definition_Matrix.md`, `RADIANT_Scenario_Testing_Instructions.md`, `expanded_scenarios.md`, plus deferred specs `RADIANT_GUI_Architecture.md` and `RADIANT_Plugins.md` (DEFERRED banners kept).

**→ `tracking/`** (deferred to Phase E — in-flight branch edits Cleanup_Backlog.md):
`Cleanup_Backlog.md`, `gaps.md`.

**→ `archive/`** (HISTORICAL banner added, with date + superseded-by/completed-by line):
`Gap_G_CSV_Loader_Plan.md`, `Gap_H_Wrap_At_Assembly_Plan.md`, `Option_C_Implementation_Plan.md`¹, `RADIANT_Rule19_Compliance_Plan.md`, `Target_Definition_Implementation_Plan.md`, `Technical_Debt_Cleanup_Plan.md`², `Cleanup_Backlog_Phase2_Plan.md`², `Use_Case_gaps.md`², `Target_Definition_gaps.md`², `adr/RADIANT_Optimized_Prompt_Sequence.md` (prompt playbook, not an ADR), `docs/archive/blocked_overnight_log.md` (then delete `notes/`).

¹ Option_C is referenced by Cleanup_Backlog CU-013 and `option_c_baseline.md` — update those two links in the same commit.
² Fold-then-archive: any still-open item is first copied into `tracking/Cleanup_Backlog.md` (as a CU) or `tracking/gaps.md`; the archived file gets a banner naming where each open item went. **Folding into Cleanup_Backlog.md waits for Phase E** (in-flight branch); the archive move of the two cleanup-plan docs waits with it.

**→ `reports/cu_tasks/`:**
`CU-003_Rect_Kernel_Fix_Task.md`, `CU-007_MWIR_T3Mixed_Routing_Task.md`, `CU-008_GroundBackground_Spectral_Task.md`, `CU-009_Observer_Geometry_Schema_Task.md`.

**→ `reports/architecture_audit_2026-04/`** (rename of `audit_2026/`, contents intact incl. `findings/` and its CU-020 brief — audit folders keep their own task briefs).

**Stays put:** `index.md`, `OPERATING_MODEL.md`, `adr/` (minus the misfiled playbook), `guides/`, `theory/` (+ `radiometric_model_mixed_train.md` moves in), `validation/` (+ `option_c_baseline.md` moves in — it anchors live golden tests), `reports/phase3/`, `reports/organization_audit_2026-07/`, existing `archive/` contents.

### Phase B closing steps
- [ ] Fix inbound references: `grep -rn` for each moved filename across `*.md`, `*.py`, `mkdocs.yml`; update paths. Docstring references to `docs/RADIANT_*` in `src/` are **deferred to Phase E** (post-merge of in-flight branch) — log the hit list in this PR.
- [ ] Update `mkdocs.yml` nav paths for the 5 dev docs it references; add an "Architecture Reference" nav section (Decision #4).
- [ ] `adr/README.md`: fix "SSR Tool" → RADIANT; document the ID scheme (legacy `0001–0004` + `ADR-A–D` frozen; new ADRs continue `0005-`); index all ADRs.
- [ ] Verify `scripts/test_docs_code.py` still passes (guide code blocks unaffected by moves, but run it).

## Phase C — dev_tools consolidation (~half day)

- [ ] **Rescue the v2 plan first:** `git add` `dev_tools/geometry_gui/PLAN_v2.md` → `git mv` to `docs/plans/Geometry_GUI_v2_Plan.md` (it is the *active* plan — Phase 7 in progress). Update the v2 README link to it.
- [ ] Move v2 PM docs out of the package → `docs/reports/geometry_gui_v2/`: `AUDIT_round2.md`, `AUDIT_round3.md`, `PLAN_v2_remediation_round2.md`, `PLAN_v2_remediation_round3.md`, `REMEDIATION_REPORT.md`, `REMEDIATION_REPORT_round3.md`, `REMEDIATION_BLOCKERS.md`. Package keeps `README.md`, `ARCHITECTURE.md`, `CONTRIBUTING.md`.
- [ ] **Delete `dev_tools/geometry_gui/` (v1) entirely** (Decision #1; explicitly closed — git history is the archive). First salvage: anything v2 docs reference by relative path into v1.
- [ ] Prune v2 golden screenshots to the sets its tests actually assert against (`tests/golden/round3/final/` + whatever `pytest dev_tools/geometry_gui_v2` proves it loads). Delete superseded rounds: `round2/`, `s1_after…s6_after/`, `round3_audit/`, `golden_phase1/`, `audit_round2/before|after_R*/` (Decision #6). **Gate: v2 test suite green after prune.**
- [ ] Resolve duplicate `glossary.yaml` — keep the copy the code loads, delete the other, update README's single-source-of-truth claim.
- [ ] File a CU for wiring v2 tests into CI if CU-046 doesn't already cover the specifics.

## Phase D — scenarios normalization (~2 h)

- [ ] Rewrite `scenarios/README.md` to the **actual** convention: per-sub-scenario layout (`inputs/` with generator + xlsx, `scripts/run_*.py`, `outputs/`), the mandatory trio (`walkthrough.md`, `gaps.md`, `gui_workflow.md`), definition-of-done, and a status table of all 35 sub-scenarios (implemented / stub).
- [ ] Delete duplicate stub `scenarios/05_*/5.3_polychromatic_psf_comparison/` (numbering collision with implemented `5.3_mono_vs_poly_psf`).
- [ ] Write the missing `gaps.md` for `6.3_noise_model_verification` (audit the run script's workarounds to populate it).
- [ ] Output provenance (Decision #2): add `outputs/MANIFEST.md` per implemented scenario — one line per artifact: generator script, input file, date, commit. If Decision #2 chooses regenerate-on-demand for `*_results.xlsx`, `git rm --cached` them and gitignore `scenarios/**/outputs/*.xlsx`.
- [ ] Mirror each scenario `gaps.md` open item into `tracking/gaps.md` (Phase E if gaps.md has moved by then) so scenario findings are actionable from one place.

## Phase E — conventions + registry consolidation (~2 h, **gated on in-flight branch merge**)

- [ ] Append Rules 23–28 to `CLAUDE.md` (text finalized in the audit report §5) and reference `docs/OPERATING_MODEL.md` from it; Rule 23's text must point to OPERATING_MODEL §5 as the binding naming convention for all non-source files.
- [ ] Naming sweep: grep for §5.3 prohibited patterns and §5.1-violating names (spaces, status/version words) across all non-source files; rename stragglers or file CUs. (Most current violators — v2 golden `round*/` trees, `docs_screenshots/` — are already deleted in Phase C.)
- [ ] `git mv Cleanup_Backlog.md gaps.md → docs/tracking/`; update all inbound references (CLAUDE.md mentions the backlog path ~5×).
- [ ] Fold open items from `Technical_Debt_Cleanup_Plan.md` + `Cleanup_Backlog_Phase2_Plan.md` into the backlog; archive both (completes Phase B footnote ²).
- [ ] Fold `Use_Case_gaps.md` + `Target_Definition_gaps.md` open items into `tracking/gaps.md`; archive both (Decision #3).
- [ ] Docstring path fixups deferred from Phase B (`docs/RADIANT_*` references in `src/`).
- [ ] CLAUDE.md accuracy fixes: add `src/radiant/data/` to Package Layout + Import Rules (+ file CU for an import-linter contract); name the third test bucket (`tests/` root = cross-cutting/public-surface); resolve `plugins/` per Decision #5.
- [ ] Add the §4 hygiene checklist to `.github/PULL_REQUEST_TEMPLATE.md`.
- [ ] Set OPERATING_MODEL.md Status → Active. Move this plan to `docs/archive/` with completion banner. Add disposition lines to the organization audit report (findings → CU'd / Planned / Declined).

---

## Open Decision Points (block the phases marked)

| # | Decision | Recommendation | Blocks |
|---|---|---|---|
| 1 | GUI v1: delete vs keep | Delete (closed; history preserves) | C |
| 2 | Scenario outputs: regenerate-on-demand vs commit+manifest | Manifest for walkthrough-referenced PNGs; un-track results.xlsx | D |
| 3 | Fold gap registries into one `gaps.md` | Yes | E |
| 4 | mkdocs: publish architecture specs | Yes — add nav section | B (nav step only) |
| 5 | `plugins/` stub package: delete until Phase 2 vs keep | Delete stub; spec keeps DEFERRED banner | E |
| 6 | Golden screenshots: current-baseline-only | Yes (~200 PNG reduction) | C |
