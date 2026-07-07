# RADIANT Project Organization Audit

**Date:** 2026-07-06
**Status:** Complete — dispositioned 2026-07-06 (Rule 28). Owner approved all six decision points; findings actioned via `docs/archive/Repo_Reorganization_Plan.md` (Planned → executed, commits ORG-0/A/B/C/D/E) and the registry folds (CU'd: Gaps 38–41 in `docs/tracking/gaps.md`; the cleanup-plan fold needed zero new CUs — every item was already tracked or commit-linked done). One finding Declined: the S3 λ-varying ε(λ) note stays with the archived Target_Definition_gaps doc per its own accounting. This report is immutable; path references reflect the pre-reorganization tree except where mechanically updated during the move.
**Scope:** Full-repository content accounting + reorganization recommendation + proposed execution ground rules. Read-only audit; no code, docs, or data were modified.
**Method:** Four parallel inventory sweeps (docs/, scenarios/, tooling dirs, src+tests) plus git-level hygiene analysis.

---

## 1. Executive Summary

**The code is healthy. The project management layer around it is what sprawled.**

The `src/` + `tests/` core is in good shape: 205 source files across 14 packages, 146 test files in a clean two-tier layout, five import-linter contracts enforcing the architecture, CI running static checks + three test tiers. The recent `audit_2026/` rewrite-vs-refactor audit correctly concluded "continue + cleanup."

The "everything feels all over the place" feeling comes from three specific, fixable failure modes:

1. **Project-management artifacts have no lifecycle.** Plans, audits, task briefs, and remediation reports are created next to whatever they concern and never move when finished. Five completed plans sit in the live `docs/` tree; eleven PM markdown files live inside the `geometry_gui_v2` Python package; the canonical v2 GUI plan is untracked and physically located inside the superseded v1 directory.
2. **Generated artifacts have no policy.** ~350 output files are committed ad hoc: 275 golden-screenshot PNGs in dev_tools (including multiple superseded remediation rounds), 48 scenario output files (figures + results workbooks), 2 loose plot PNGs, 3 LibreOffice lock files, and tracked `.DS_Store` files. `dev_tools/` is the largest tracked area in the repo (489 files — more than `src/` at 360), and it's almost entirely screenshots.
3. **Registries multiplied instead of consolidating.** Four documents track cleanup debt (`Cleanup_Backlog.md`, `Technical_Debt_Cleanup_Plan.md`, `Cleanup_Backlog_Phase2_Plan.md`, `audit_2026/Reconciliation_Tasks.md`). Four documents track gaps (`gaps.md`, `Use_Case_gaps.md`, `Target_Definition_gaps.md`, plus an archived variant). No index reconciles them.

Secondary issues: the mkdocs site publishes only 15 of ~70 docs (all stage-level architecture specs are orphaned from the nav); `scenarios/README.md` documents a convention (per-scenario README.md) that zero scenarios follow while the real convention (walkthrough/gaps/gui_workflow trio) is undocumented; 22 of 36 sub-scenarios are empty stubs; and the project is named "SSR Tool" in some docs and "RADIANT" in others.

---

## 2. Content Accounting

### 2.1 Tracked-file census by area

| Area | Tracked files | What it is | Health |
|---|---|---|---|
| `dev_tools/` | 489 (275 PNG, 183 py) | Two geometry GUI implementations (v1 closed, v2 active) | ⚠️ Bloated + ambiguous |
| `src/` | 360 | RADIANT library, 14 packages + colocated tests | ✅ Healthy |
| `scenarios/` | 240 | 7 personas × ~5 sub-scenarios; 14 implemented, 22 stubs | ⚠️ Inconsistent |
| `docs/` | 72 | ~25 architecture specs + plans/backlogs/reports/ADRs/guides | ⚠️ Specs healthy; PM layer sprawled |
| `data/` | 31 | Reference CSVs (emissivity, QE, solar) loaded by `src/radiant/data/library.py` | ✅ Healthy |
| `tests/` | 24 | Integration + golden + 3 cross-cutting tests | ✅ Healthy |
| `examples/` | 21 | 5 API demo scripts + 12 config templates + 2 reference YAMLs | ✅ Healthy |
| `scripts/` | 6 | Repo maintenance tooling (golden regen, param-ref generator, docs-code test) | ✅ Healthy |
| Root files | 7 | README, DEVELOPMENT, CLAUDE.md, mkdocs.yml, pyproject, pre-commit, gitignore | ✅ Healthy |
| `notes/` | 1 | `blocked.md` — fully-resolved April log, one entry now factually wrong | 🗑️ Stale |
| `.github/` | 2 | CI (static / level0-1 / level2 / golden) + PR template | ✅ Healthy (GUIs excluded) |

### 2.2 `src/` + `tests/` (healthy — three small drifts)

- 14 packages on disk vs 13 documented in CLAUDE.md. **`src/radiant/data/` is undocumented** — real package (`library.py` + 5 test files) absent from the Package Layout tree and the Import Rules table; no import-linter contract governs it. (Rule 20 drift.)
- **`plugins/` is the inverse**: fully documented (layout, import rule, linter contract, 25 KB spec) but contains two ~0-line stubs. The spec now carries a DEFERRED banner, which is correct — but the package itself is hollow.
- Test topology is two-tier and clean (128 colocated stage tests, 15 integration, golden JSON + snapshot baseline), except **3 cross-cutting tests** (`test_exceptions`, `test_provenance`, `test_public_api`) sit directly under `tests/` in a bucket CLAUDE.md doesn't name.
- `tests/integration/fixtures/` is an empty `.gitkeep` placeholder.

### 2.3 `docs/` (specs active and maintained; plan/tracking layer is the mess)

**Healthy core:** The authoritative `RADIANT_*` specs are current — a July 6 update cluster (Master_Architecture, Signal_Chain, Parameter_System, Config_Format, Scripting_API, ADR-D, Cleanup_Backlog) shows active maintenance. `archive/` is clean and correctly bannered. `guides/` and `theory/` are current and published.

**Problems:**

| # | Problem | Specifics |
|---|---|---|
| D1 | Completed plans not archived | `Gap_H_Wrap_At_Assembly_Plan.md` ("✅ COMPLETE"), `Gap_G_CSV_Loader_Plan.md`, `Option_C_Implementation_Plan.md` (all 8 stages landed; stays for inbound refs), `RADIANT_Rule19_Compliance_Plan.md`, `Target_Definition_Implementation_Plan.md` — all live at docs/ top level |
| D2 | 4 overlapping cleanup registries | `Cleanup_Backlog.md` (the real one, 29 CUs, active), `Technical_Debt_Cleanup_Plan.md`, `Cleanup_Backlog_Phase2_Plan.md` (draft), `audit_2026/Reconciliation_Tasks.md` |
| D3 | 4 overlapping gap registries | `gaps.md` (canonical), `Use_Case_gaps.md`, `Target_Definition_gaps.md` (mostly closed), archived pre-Option-C variant |
| D4 | mkdocs nav orphans 55 of ~70 docs | All stage specs (Atmosphere, Optics, Detector, Source/Target, Spatial, Metrics, Scan_Timing, Config_Format, Scripting_API, Metric_Dependencies), all ADRs, all plans/backlogs are unpublished |
| D5 | Ephemeral task briefs accumulate | `CU-003/007/008/009_*_Task.md` + `reports/phase3/prompt_*` — point-in-time execution artifacts never swept |
| D6 | ADR folder inconsistency | Two numbering schemes (`0001-…` vs `ADR-A-…`); `RADIANT_Optimized_Prompt_Sequence.md` (36 KB prompt playbook) misfiled in `adr/`; `adr/README.md` calls the project "SSR Tool" |
| D7 | Misleading filenames | `RADIANT_Spatial_Complete.md` / `RADIANT_Detector_Complete.md` — "_Complete" reads as lifecycle status but is naming residue (Spatial's title was already changed; filename kept for ~50 docstring links) |
| D8 | Deferred specs alongside authoritative ones | `RADIANT_Plugins.md`, `RADIANT_GUI_Architecture.md` describe unbuilt machinery (bannered, but not separated) |
| D9 | Audit findings gap | `audit_2026/findings/` jumps phase 3 → phase 5; no phase 4 file |

### 2.4 `scenarios/` (14 real, 22 empty, convention undocumented)

- **Implemented (14):** consistent internal shape — `inputs/` (`create_spreadsheet.py` + persona xlsx), `scripts/run_*.py` (585–916 LOC each; 10,129 LOC total), `outputs/` (results.xlsx + 0–5 PNGs), plus the walkthrough/gaps/gui_workflow trio.
- **Stubs (22):** `.gitkeep` skeletons only. Persona 04 (Lisa, analyst) is 0/5 implemented.
- **S1 — stale README:** `scenarios/README.md` mandates a per-scenario `README.md`; zero exist. The actual trio convention is undocumented anywhere in-repo (it lives only in agent memory).
- **S2 — duplicate 5.3:** `5.3_mono_vs_poly_psf` (implemented) and `5.3_polychromatic_psf_comparison` (empty) — abandoned rename, numbering collision.
- **S3 — missing gaps.md:** `6.3_noise_model_verification` is the only implemented scenario without one.
- **S4 — generated outputs committed:** all 34 PNGs + 14 results.xlsx tracked, with no manifest tying an output set to the script+input version that produced it. Inputs are doubly stored (generator script + committed xlsx), and lock files prove the xlsx get hand-edited after generation — so the generator and the binary have silently diverged.
- **S5 — junk committed:** 3 `.~lock.*#` files are *tracked* (2.3, 3.2, 6.3); a 4th is untracked (5.1). 7 `.DS_Store` on disk. `.gitignore` has no `.~lock` pattern.
- **S6 — scripts carry library workarounds:** run scripts re-implement physics the library lacks (e.g., 3.4 computes off-nadir GSD analytically and applies a manual NIIRS correction). The gaps.md files document these properly — but the workaround code has no path back into the library.

### 2.5 `dev_tools/` (the biggest single cleanup opportunity)

- **`geometry_gui/` (v1, 125 files):** Plotly Dash implementation, explicitly closed ("v1 is closed. No further work lands against it"). Retained in full: ~60 modules, 22 tests, golden artifacts, 8 phase-prompt briefs, 9 gallery screenshots.
- **`geometry_gui_v2/` (v2, 364 files):** PyVista/PySide6, active (Phases 0–6 shipped, Phase 7 in progress). Real code is ~90 modules + ~30 tests. The other ~250 files are golden screenshots across superseded remediation rounds (`round2/`, `round3/s1_after…s6_after/`, `audit_round2/before/after_R1..R6/`) — historical render sets kept past their usefulness.
- **T1 — the v2 master plan (`PLAN_v2.md`) is untracked and lives inside the v1 directory.** The referenced round-1 remediation doc doesn't exist in the tree at all. Anyone opening v2 cannot find the plan it implements.
- **T2 — 11 PM markdowns inside the v2 package root** (AUDIT_round2/3, PLAN_v2_remediation_round2/3, REMEDIATION_REPORT[_round3], REMEDIATION_BLOCKERS) alongside `pyproject.toml`.
- **T3 — duplicate `glossary.yaml`** (package root + `scene/labels/`), despite README calling it single-source-of-truth.
- **T4 — neither GUI runs in CI** (tracked as CU-046, still open).

### 2.6 `examples/`, `scripts/`, `data/`, `notes/`, root

- `examples/` and `scripts/` are **not** duplicates: user-facing API demos vs repo maintenance tools. Both current. Two committed plot PNGs (`examples/scripts/aperture_sweep_snr.png`, `scripts/spatial_audit_plots.png`) are the only issues. `scripts/capture_option_c_baseline.py` is a one-off tied to the completed Option C migration.
- `data/` is genuine reference data actively loaded by `src/radiant/data/library.py`; small (<100 KB); `atmospheres/` is a documented intentional placeholder.
- `docs/archive/blocked_overnight_log.md`: all entries resolved/deferred as of April; one entry ("no `data/detectors/` directory") is now factually contradicted by the codebase.
- Root files healthy. Repo weight: `.git` is 45 MB, driven by the screenshot corpus.

---

## 3. Root-Cause Diagnosis

Everything above reduces to five missing conventions:

1. **No artifact-placement rule.** Nothing says where a plan, audit, report, or task brief goes, so they land wherever the work happened — including inside Python packages.
2. **No lifecycle rule for PM docs.** CUs have a rigorous open→resolved protocol (Rules 21–22); plans and reports have nothing, so "done" documents are indistinguishable from live ones without reading them.
3. **No generated-artifact policy.** Outputs get committed by default; superseded baselines are never swept.
4. **No single-registry rule.** New tracking docs get created instead of extending existing ones.
5. **No canonical-version rule.** Superseded implementations (GUI v1, old golden rounds, old plan variants) are retained alongside their replacements instead of being deleted (git history is the archive).

---

## 4. Recommended Target Organization

### 4.1 Directory taxonomy (docs/ restructure)

```
docs/
├── architecture/     # Authoritative RADIANT_*.md specs ONLY (active, code-verified)
├── adr/              # Decision records only, one numbering scheme (ADR-NNNN)
├── guides/           # User guides (published)          — unchanged
├── theory/           # Theory docs (published)          — unchanged
├── validation/       # Truth-anchor references          — unchanged
├── tracking/         # LIVING registries: Cleanup_Backlog.md, gaps.md — and nothing else
├── plans/            # ACTIVE plans only; completed plans move to archive/ in the closing PR
├── reports/          # Point-in-time outputs: audits (audit_2026/), phase reports,
│                     #   CU task briefs, GUI remediation reports, THIS document
└── archive/          # Completed/superseded, bannered   — existing convention, extended
```

Top of `docs/`: only `index.md` and a short `README.md` stating the taxonomy and lifecycle rules. Everything currently at docs/ top level gets exactly one home in this tree.

**Specific moves** (execution phase, each a mechanical `git mv`):
- 5 completed plans → `archive/plans/` (Option_C keeps a redirect stub if inbound refs matter).
- `Technical_Debt_Cleanup_Plan.md` + `Cleanup_Backlog_Phase2_Plan.md`: fold any still-open items into `Cleanup_Backlog.md` CUs, then archive both. One cleanup registry.
- `Use_Case_gaps.md` + `Target_Definition_gaps.md`: fold open items into `gaps.md`, archive the rest. One gap registry.
- `CU-00N_*_Task.md` briefs + `reports/phase3/` → `reports/` (or archive if the CU is resolved).
- `RADIANT_Optimized_Prompt_Sequence.md` out of `adr/` → `reports/` or `archive/`.
- `RADIANT_Personas.md`, `RADIANT_Use_Case_Matrix.md`, `RADIANT_Target_Definition_Matrix.md`, `RADIANT_Physics_Inventory.md`, `RADIANT_Scope_Decisions.md` → `architecture/` (they are design references, not plans).
- Deferred specs (`RADIANT_Plugins.md`, `RADIANT_GUI_Architecture.md`) → `architecture/` with their DEFERRED banners kept (or a `architecture/deferred/` sub-folder if visual separation is preferred).

**Note on docstring links:** ~50 docstrings reference `RADIANT_Spatial_Complete.md` by name. Any rename/move of spec files must update those references in the same PR — or specs keep their filenames and only change directories, with a link-check pass after.

### 4.2 mkdocs nav

Add a "Architecture Reference" nav section covering the `architecture/` specs and `adr/`, or explicitly document (in the new docs/README.md) that the published site is user-facing-only and the specs are repo-internal. Either is fine; the current silent 21% coverage is not.

### 4.3 scenarios/

- Rewrite `scenarios/README.md` to document the **actual** convention: the walkthrough/gaps/gui_workflow trio, the inputs/scripts/outputs layout, and the definition-of-done for a scenario. Add a status table (implemented / stub) so 22 empty dirs are self-explaining.
- Delete the duplicate `5.3_polychromatic_psf_comparison` stub; add the missing `gaps.md` to 6.3.
- Keep the 22 stubs (they encode the persona test plan) but they need nothing beyond the README status table.
- **Provenance rule for outputs** (see decision point #2 in §6): at minimum, each `outputs/` set gets a one-line manifest (generating script + input file + date + commit). Preferred: commit only the figures that walkthroughs reference; results.xlsx become regenerate-on-demand.
- Un-track the 3 committed lock files; add `.~lock.*#` to `.gitignore`.

### 4.4 dev_tools/

- **Delete `geometry_gui/` (v1) from the working tree.** It is explicitly closed; git history is the archive. Before deletion: move `PLAN_v2.md` (the v2 master plan — currently untracked, in the wrong directory) into git under `docs/plans/` or v2's docs home, and salvage anything v2's docs reference by relative path.
- **Move the 11 PM markdowns out of the v2 package** → `docs/reports/geometry_gui_v2/` (audits, remediation reports) and `docs/plans/` (active plan docs). The package keeps README, ARCHITECTURE, CONTRIBUTING.
- **Prune golden screenshots to the current baseline set** (the `final/` renders the tests actually assert against). Superseded rounds (`round2/`, `s1_after…s6_after/`, `audit_round2/before/after_R*/`, v1 goldens) are deleted — recoverable from history. This alone removes ~200+ PNGs.
- Resolve the duplicate `glossary.yaml` (keep the one the code loads; delete the other).
- Wire the v2 test suite into CI (closes CU-046).

### 4.5 src/, tests/, misc

- Document `src/radiant/data/` in CLAUDE.md's Package Layout + Import Rules and add an import-linter contract for it (Rule 20 compliance).
- Decide `plugins/`: either delete the stub package until Phase 2 (spec already says deferred) or leave as-is; either way CLAUDE.md should match reality.
- Name the third test bucket in CLAUDE.md ("cross-cutting/public-surface tests live at `tests/` root") — 1-line doc fix.
- Delete `notes/` (fold the one contradicted entry's correction nowhere — it's resolved history; git keeps it) or move `blocked.md` to `docs/archive/`.
- Delete the two loose plot PNGs (`examples/scripts/`, `scripts/`); regenerate on demand.
- Move `scripts/capture_option_c_baseline.py` to archive or delete (its plan is complete).
- `git rm --cached` all tracked `.DS_Store`; the gitignore already covers future ones.
- Standardize the project name: **RADIANT** in all docs; note once in README that the repo folder is historically named SSR_Tool.

---

## 5. Proposed Execution Ground Rules

To be appended to CLAUDE.md as Rules 23–28 (numbering continues the existing 22) once approved:

### Rule 23 — Every Artifact Has One Defined Home
| Artifact type | Home |
|---|---|
| Library code | `src/radiant/<package>/` |
| Stage unit tests | `src/radiant/<package>/tests/` |
| Integration / golden / cross-cutting tests | `tests/` |
| Architecture spec / design reference | `docs/architecture/` |
| Decision record | `docs/adr/` (single ADR-NNNN scheme) |
| Active plan | `docs/plans/` |
| Living registry (CUs, gaps) | `docs/tracking/` — extend, never fork |
| Audit / task report / remediation record | `docs/reports/<topic>/` |
| Completed or superseded doc | `docs/archive/` with HISTORICAL banner |
| User guide / theory | `docs/guides/`, `docs/theory/` |
| Scenario content | `scenarios/NN_persona/N.M_name/` with the walkthrough/gaps/gui_workflow trio |
| Dev tool code | `dev_tools/<tool>/` — **code only**; its plans/audits/reports go to `docs/` per this table |
| Reference data | `data/` with a manifest |
| Repo maintenance script | `scripts/` |
| API usage example | `examples/` |

Markdown project-management documents never live inside a Python package.

### Rule 24 — Plans and Reports Have a Lifecycle (like CUs)
Every plan/audit/report starts with a status header: `Status: Draft | Active | Complete (date, closing commit) | Superseded (by X)`. The PR that completes a plan moves it to `docs/archive/` in the same PR — exactly parallel to Rule 22's CU-closure protocol. A "✅ COMPLETE" banner on a doc still sitting in the live tree is a rule violation.

### Rule 25 — One Registry Per Concern
Technical debt → `docs/tracking/Cleanup_Backlog.md`. Library/scenario gaps → `docs/tracking/gaps.md`. Creating a new tracking document requires retiring (folding + archiving) the one it replaces in the same PR. Plans may *reference* registry entries but never re-enumerate them.

### Rule 26 — Generated Artifacts Are Regenerable, Committed Only With Cause
A binary/derived file may be committed only if it is (a) a golden baseline a test asserts against, or (b) a figure a committed document references. Every committed artifact must name its generator (script + input) — in a manifest line or the referencing doc. When a baseline set is superseded, the old set is deleted in the same PR (git history is the archive). Everything else in `outputs/` is regenerate-on-demand and gitignored.

### Rule 27 — One Canonical Version
When an implementation, plan, or baseline is superseded, the old version is deleted from the working tree, not retained alongside. Git history is the archive; `docs/archive/` is for documents whose *content* still gets referenced. A closed version may persist only with an explicit deferral record (what gates its deletion + re-audit date), mirroring Rule 22's stage-deferral protocol.

### Rule 28 — Audit Protocol: Chartered In, Dispositioned Out
Audits are first-class work products with a defined trigger, home, and exit path — not ad-hoc documents.

**When audits run:**
- **Chartered audits** (architecture, physics, doc-drift, organization): owner-triggered, with a one-paragraph scope + decision framework written *before* the audit starts (`audit_2026/Audit_Plan.md` is the template).
- **Hygiene checks**: a lightweight pass against Rules 23–27 (artifact placement, lifecycle headers, registry uniqueness, superseded-artifact sweep) runs at every declared phase close, as an item in the closing PR's checklist — not a separate document unless findings warrant one.

**Where results go:** every chartered audit gets exactly one directory, `docs/reports/<topic>_<YYYY-MM>/`, containing its plan/scope, findings, and recommendation. Audit reports are **point-in-time records: immutable once complete**. Corrections and follow-ups are new documents that reference the original, never edits to it.

**How audits close (disposition rule):** an audit is not "done" when written — it is done when every finding has exactly one of three dispositions, recorded in the report or a companion disposition file:
1. **CU'd** — actionable debt becomes a `Cleanup_Backlog.md` entry (Rule 21 timing applies).
2. **Planned** — larger recommendations become a plan in `docs/plans/` (which then lives under Rule 24's lifecycle).
3. **Declined** — explicitly, with one line of rationale.

An audit with undispositioned findings is the organizational analog of a silent failure (Rule 17): observations that decay into folklore. This rule exists because the current sprawl is largely descendants of past audits whose outputs had no defined exit path — four cleanup registries, orphaned task briefs, completed-but-unarchived plans.

---

## 6. Decision Points for the Owner

1. **GUI v1 disposition:** delete from working tree (recommended — it's closed, history preserves it) vs move to `docs/archive/`-style cold storage vs keep as-is.
2. **Scenario outputs:** stop committing results.xlsx/PNGs and regenerate on demand (recommended for xlsx) vs keep committing with a provenance manifest (reasonable for walkthrough-referenced figures).
3. **Gap registries:** fold `Use_Case_gaps.md` + `Target_Definition_gaps.md` into `gaps.md` (recommended) vs keep separate with an index.
4. **mkdocs scope:** publish the architecture specs (recommended) vs declare the site user-facing-only.
5. **`plugins/` package:** delete stub until Phase 2 vs keep hollow package.
6. **Golden screenshot retention:** current-baseline-only (recommended, ~200 PNG reduction) vs keep last N rounds.

## 7. Proposed Execution Sequence (after approval)

Ordered so each phase is independently landable; **no phase touches `src/` physics** (Phase E is docs/config only). The in-flight `fix/architecture-audit-2026-07` branch modifies `src/` and `docs/tracking/Cleanup_Backlog.md` — Phases A–D avoid those files entirely; Phase E's registry consolidation waits until that branch lands.

| Phase | Content | Effort | Risk |
|---|---|---|---|
| A — Git hygiene | Un-track lock files + .DS_Store; add `.~lock.*#` to gitignore; delete 2 loose plot PNGs | ~30 min | None |
| B — docs/ taxonomy | Create the §4.1 tree; `git mv` all docs to their homes; archive completed plans; fix ADR folder; write docs/README.md | ~half day | Link breakage — run `scripts/test_docs_code.py` + a link check |
| C — dev_tools consolidation | Rescue PLAN_v2.md into git; move 11 PM docs to docs/reports/; delete v1; prune superseded goldens; fix glossary duplicate | ~half day | v2 tests must pass after (goldens the tests use stay) |
| D — scenarios normalization | Rewrite README to real convention + status table; delete dup 5.3 stub; add 6.3 gaps.md; output-provenance manifests | ~2 h | None |
| E — Convention updates | Append Rules 23–28 to CLAUDE.md; document `data` package + third test bucket; mkdocs nav; registry consolidation (D2/D3) | ~2 h | Coordinate with in-flight branch |

Each phase should file/close CUs in `Cleanup_Backlog.md` per Rules 21–22 as it lands.
