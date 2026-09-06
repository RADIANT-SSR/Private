# RADIANT Documentation & Work-Tracking Operating Model

**Status:** Active (2026-07-06) — normative; Rules 23–29 in CLAUDE.md bind to this document
**Purpose:** The single rulebook for where every document lives, how documents move through their lifecycle, and how work is tracked without an external ticket system. If a file placement question isn't answered here, the answer goes here.

---

## 1. The Folder Set (complete and closed)

`docs/` contains exactly these entries. Creating a new top-level folder or a new top-level file requires updating this document in the same PR.

| Folder | Contains | Mutability | Cardinality rule |
|---|---|---|---|
| `architecture/` | Normative specs — documents that describe how the system **is or must be** (all `RADIANT_*.md` specs, design matrices, scope decisions) | Living — updated in lock-step with code (Rule 20) | One spec per subsystem |
| `adr/` | Architecture Decision Records | **Immutable** once Accepted (superseding requires a new ADR) | One decision per file |
| `guides/` | User-facing how-to (published on mkdocs site) | Living | — |
| `theory/` | Physics background (published) | Living | — |
| `validation/` | Truth anchors, hand calculations, SHA-pinned baselines that current tests reference; `fpa_datasheets/` — committed reference PDFs cited by shipped FPA presets, hash-manifested per Rule 26(c) (Gap 119, owner-ratified 2026-09-06) | Living | — |
| `tracking/` | **The work board.** Exactly three files: `Cleanup_Backlog.md` (CU-grade debt, CU-numbered), `gaps.md` (library capability gaps), and `Findings_Log.md` (sub-CU findings, one line each — Rule 21 tier 2, added 2026-07-31) | Living — the most-edited files in docs/ | **Exactly three files, forever.** A fourth tracking file is a rule violation (Rule 25) |
| `plans/` | Plans for work **not yet finished**. Status header mandatory | Living while active | **`plans/` empty ⇒ nothing is in flight.** That invariant is the point |
| `reports/` | Completed point-in-time records: audits, task reports, remediation records | **Immutable** — corrections are new documents | One folder per audit: `<topic>_<YYYY-MM>/` |
| `archive/` | Documents that once claimed to be current and no longer are. Flat, no subfolders. Every file carries a HISTORICAL banner with date + superseded-by | Frozen | — |
| Top-level files | `index.md` (mkdocs home — the tool requires it at docs-root), `OPERATING_MODEL.md` (this file — it governs the taxonomy, so it sits above the folders it defines) | — | **Nothing else at top level. Ever.** |

**Repo root is a closed list too:** `README.md`, `DEVELOPMENT.md`, `CHANGELOG.md`, `CLAUDE.md`, `pyproject.toml`, `MANIFEST.in`, `mkdocs.yml`, `.gitignore`, `.gitattributes`, `.pre-commit-config.yaml` (plus `LICENSE` if one is added). `MANIFEST.in` is the setuptools sdist manifest that ships the bundled reference-data tree (`src/radiant/data/tables/`) into the distribution. Root-level `README`/`DEVELOPMENT`/`CHANGELOG` follow ecosystem convention — they are the files a newcomer looks for before knowing the taxonomy exists. `CHANGELOG.md` (added 2026-07-07) is the Rule-29 record of behavior-affecting changes: living, append-at-top, Keep-a-Changelog format; it complements the tracking registries, which remain the work board. Any other root file needs a row added here first.

**Enforcement:** `scripts/check_org_rules.py` mechanically checks the closed lists, the three-file `tracking/` rule, the no-PM-docs-in-packages rule, §5.3 prohibited names, registry-ID uniqueness, the ancestry of every commit SHA the registries cite (§2, Rule 22), the canonical form of every Resolved backlog heading (CU-282), the existence of a `CU-Closes` trailer commit for every trailer-closed entry (Rule 22, 2026-07-31), and the presence of a commit link on every gap marked closed (CU-281). It runs in the CI `static` job; a violation fails the build. (Per CLAUDE.md's final forbidden action, a normative claim with no enforcing check is aspirational drift — this file is normative *because* that script runs.)

## 2. Lifecycle Flows — what moves where, and when

The one distinction that answers most questions:

> **Reports record; everything else claims.**
> A report says "on this date, we found X" — that never stops being true, so **reports never move and are never edited**. A spec, plan, or registry claims to be *currently* true — when the claim expires, the file moves to `archive/` in the same PR that expires it.

```
                    created            while true              when done / superseded
SPEC          → architecture/     stays, updated w/ code   → archive/  (when replaced by new spec)
ADR           → adr/ (Proposed)   → Accepted, frozen       → never moves (superseded by new ADR)
PLAN          → plans/ (Draft)    → Active                 → archive/  (in the PR that finishes it)
AUDIT/REPORT  → reports/<t_YYYY-MM>/  immutable            → NEVER moves. reports/ is its grave and its home
CU (debt)     → tracking/Cleanup_Backlog.md ## Open        → ## Resolved w/ closure record (Rule 22:
                                                             CU-Closes trailer, SHA, or a ruling —
                                                             ACCEPTED / DECLINED / FOLDED / DEMOTED)
FINDING (sub-CU) → tracking/Findings_Log.md (one line)     → promoted to a CU, struck when fixed
                                                             in passing, or expired at the
                                                             quarterly sweep
GAP           → tracking/gaps.md (open)                    → marked closed in place w/ commit SHA
```

**Explicit answers to recurring questions:**
- *Do audit results move to archive when actioned?* **No.** The audit stays in `reports/` forever. What "actioning" means: every finding gets a disposition (CU'd / Planned / Declined — Rule 28), and the *plan* that came out of it is what eventually retires to `archive/`.
- *Where does a finished plan go?* `archive/`, moved **in the same PR** that completes its last item. A "✅ COMPLETE" banner on a file still sitting in `plans/` is a violation (Rule 24).
- *Where do CU task briefs go?* `reports/cu_tasks/`. They are point-in-time task specs — records, not plans.
- *What if a spec becomes aspirational (describes unbuilt machinery)?* It stays in `architecture/` with a **DEFERRED** banner at top (e.g., Plugins, GUI). It moves to `archive/` only if the capability is cancelled.
- *Can I edit a report to fix an error?* No. Write a short correction doc in the same `reports/` folder referencing the original.
- *What makes a closure SHA valid?* It must be an **ancestor of `HEAD`** — `scripts/check_org_rules.py` resolves every backticked hash in both registries and fails the gate on any that is not (CU-279: four cited hashes were real objects that no longer sat on `main`, pre-rebase/pre-amend twins that `git cat-file` happily resolved). This is why a closure SHA is stamped **after** the merge lands rather than written and then `--amend`ed: the amend rewrites the hash and the entry is stale the instant it is saved. A hash that is *deliberately* off-`main` — a cherry-pick source cited for provenance, or an audit quoting a dead hash as its own evidence — is written `` `452cccd` (not on main) ``; the marker is the escape hatch, and it lives next to the claim so a reader learns the hash is unverifiable where they meet it.
- *Where does the closure record go, exactly?* For a **CU**, in the entry's heading: `### CU-NNN — <title> — <DISPOSITION> <YYYY-MM-DD> (<clause>)`, disposition one of RESOLVED / CLOSED / DECLINED / SUPERSEDED / ACCEPTED / FOLDED / DEMOTED. The clause is `commit trailer` (the closing commit carries a `CU-Closes: NNN` message trailer — the canonical form since 2026-07-31, verified by check 10), or the legacy `` commit `sha` `` (mandatory for pre-2026-07-31 entries, frozen), or `no commit — <reason>` for ruling-backed closures (ACCEPTED writes `no commit — limitation: <one line>`; FOLDED writes `no commit — folded into CU-NNN`; DEMOTED writes `no commit — demoted to Findings Log`). Nuance goes in the `**Status**:` line, not the heading — the heading is the machine-readable index (check 8, CU-282; the canonical block lives in the registry header). For a **gap**, in the entry table, marked closed in place with a backticked SHA anywhere in the entry (check 9, CU-281). Both checks carry a **frozen** grandfather list of pre-convention entries — 7 CUs and 64 of the 84 closed gaps, which is the size of the hole those checks were filed to expose. Neither list may grow.
- *Why the trailer instead of a stamped SHA?* A heading cannot embed the hash of the commit that edits it, which is what forced the old stub → fix → closure → post-merge-stamp cycle (three to five commits per closure). A `CU-Closes: NNN` trailer names the CU from inside the closing commit, so git itself is the closure ledger (`git log --grep "CU-Closes"`), one commit closes a CU, and a commit cannot mislabel its own hash — the entire wrong-SHA failure class disappears going forward.
- *When is a finding a CU and when is it a log line?* Rule 21's four intake tests: results-affecting, owner-gated, blocking, or workflow-visible → CU. Everything else → one appended line in `Findings_Log.md`. The tiebreaker: "would the owner schedule work for this?"
- *Are process instructions and content catalogs architecture docs?* No. `architecture/` holds normative claims about the **system**; how-to process rulebooks and content catalogs are `guides/` (lowercase_snake, mkdocs-published). Ruled 2026-07-07 when `RADIANT_Scenario_Testing_Instructions.md` → `guides/scenario_testing.md` and `expanded_scenarios.md` → `guides/scenario_catalog.md`. (`RADIANT_Testing_Validation.md` stays in `architecture/` — it defines the system's validation contract, not a workflow.)

## 3. Work Tracking Without JIRA

The repo is the tracker. Three views replace a board:

| Board column | Where it lives |
|---|---|
| **Backlog / To-do** | `tracking/Cleanup_Backlog.md` → `## Open` (CU entries) and `tracking/gaps.md` open gaps |
| **In progress** | `docs/plans/` — every file in it is an in-flight effort; small CUs in progress are just a branch |
| **Done** | `Cleanup_Backlog.md` → `## Resolved` (with commit SHA) + `reports/` |

**Intake rule (one door, two tiers):** anything actionable — bug, debt, doc drift, missing feature, audit finding — enters through Rule 21's intake test: a **CU entry** in `Cleanup_Backlog.md` (Rule 21 fields) if it is results-affecting, owner-gated, blocking, or workflow-visible; a **one-line entry** in `Findings_Log.md` otherwise. Nothing is tracked in chat logs, memory, TODO comments, or side files.

**Sizing rule:** a CU that is one PR of work needs nothing else. A CU that needs multiple PRs or design gets a plan doc in `plans/` that references the CU(s) — the plan is the "epic," the CUs are the "tickets."

**The work loop (every effort, no exceptions):**
1. **Pick** — take a CU from `## Open` (or charter an audit per Rule 28).
2. **Branch** — one branch per CU or per plan phase.
3. **Do** — code + tests + lock-step doc updates (Rule 20).
4. **File** — any *new* latent issue found along the way → recorded before the PR merges (Rule 21): a CU if it passes the intake test, a `Findings_Log.md` line otherwise.
5. **Close** — move the CU to `## Resolved` with date + closure record in the same commit as the fix, with a `CU-Closes: NNN` trailer in its message (Rule 22); if this PR finished a plan, `git mv` it to `archive/` now (Rule 24).
6. **Sweep** — run the hygiene checklist (§4) as part of the PR.

## 4. PR Hygiene Checklist

Every PR description ends with this six-line checklist (copy-paste; it belongs in `.github/PULL_REQUEST_TEMPLATE.md`):

```
- [ ] Placement & naming: every new/moved file is in its Rule-23 home and follows §5 naming (no PM docs in packages, nothing new at docs/ top level, no status/version words in filenames)
- [ ] Lifecycle: no doc in plans/ or architecture/ has an expired claim (completed plan still live, ✅ banner in live tree)
- [ ] Registry: new findings are recorded per Rule 21 (CU in tracking/Cleanup_Backlog.md, or a Findings_Log.md line) — not a new tracking file
- [ ] Artifacts: committed binaries are (a) test-asserted goldens or (b) doc-referenced figures, with generator named; superseded sets deleted
- [ ] Docs lock-step: touched public surface ⇒ matching RADIANT_*.md updated in this PR (Rule 20)
- [ ] Changelog: results-affecting or public-surface change ⇒ entry under CHANGELOG.md [Unreleased] in this PR (Rule 29)
```

## 5. Naming & Format Conventions (everything except source code)

Source code naming is governed by CLAUDE.md / PEP 8 and is out of scope here. Everything else — markdown, audits, scenarios, data, configs, figures, folders — follows this section.

### 5.1 Global rules (all files, all folders)

1. **No spaces, ASCII only.** Allowed characters: letters, digits, `_`, `-`, `.`. Word separator is `_` (underscore); `-` appears only in ADR slugs and dates.
2. **Dates are ISO.** Folder-level: suffix `_<YYYY-MM>` (audit folders). File-level dated records: prefix `<YYYY-MM-DD>_` so they sort chronologically. Never `Jul6`, `final_v2`, `latest`.
3. **No status or version words in filenames.** `_Final`, `_Complete`, `_v2`, `_new`, `_old`, `_fixed`, `_Copy`, `round3`, `after_R1` are all forbidden — status lives in the `Status:` header, versions live in git history. (Two legacy exceptions, frozen for link stability: `RADIANT_Detector_Complete.md`, `RADIANT_Spatial_Complete.md` — "_Complete" there is naming residue, not a status claim. Do not copy the pattern.)
4. **The name states the content, not the event.** `wfe_budget_sweep.png`, not `output3.png` or `Screenshot 2026-07-06.png`. If you can't name what a file shows, it isn't ready to commit.
5. **Case by class:** `Title_Snake_Case.md` for governance docs (specs, plans, task briefs — anything with a Status header); `lowercase_snake` for everything else (guides, theory, scenario files, data, configs, figures, folders).
6. **Every `.md` opens with an H1 that matches its filename's meaning**, plus a `Status:` header where §2 requires a lifecycle.

### 5.2 Per-class patterns

| Class | Pattern | Example |
|---|---|---|
| Spec | `RADIANT_<Subsystem>.md` | `architecture/RADIANT_Optics.md` |
| ADR | `NNNN-<kebab-slug>.md` (4-digit, continue from 0005; legacy `ADR-A…D` frozen) | `adr/0005-data-package-contract.md` |
| Plan | `<Topic>_Plan.md` — the `_Plan` suffix is mandatory (grep-ability) | `plans/Repo_Reorganization_Plan.md` |
| Audit/report folder | `<topic>_<YYYY-MM>/` | `reports/organization_audit_2026-07/` |
| Files inside an audit folder | Role names: `Audit_Plan.md`, `Findings*.md`, `Recommendation.md`; corrections dated `<YYYY-MM-DD>_<slug>.md` | `reports/architecture_audit_2026-04/Recommendation.md` |
| CU task brief | `CU-NNN_<Slug>_Task.md` | `reports/cu_tasks/CU-009_Observer_Geometry_Schema_Task.md` |
| Tracking registry | Frozen names: `Cleanup_Backlog.md`, `gaps.md`, `Findings_Log.md` — no others, no renames | `tracking/Cleanup_Backlog.md` |
| Changelog | Frozen name `CHANGELOG.md`, repo root only, Keep-a-Changelog headings (Rule 29) | `CHANGELOG.md` |
| Guide / theory doc | `lowercase_snake.md` | `guides/regime_selection.md` |
| Archived file | Original name unchanged + HISTORICAL banner (date, superseded-by) | `archive/Option_C_Implementation_Plan.md` |
| Scenario persona dir | `NN_<first>_<role>/` (2-digit) | `scenarios/05_tom_optical_designer/` |
| Sub-scenario dir | `N.M_<snake_slug>/` — N.M unique within persona | `5.1_wfe_budget_allocation/` |
| Scenario trio | Exactly `walkthrough.md`, `gaps.md`, `gui_workflow.md` | — |
| Scenario input generator | `create_spreadsheet.py` (fixed name) | — |
| Scenario input data | `<persona>_<topic>_data.xlsx` | `tom_wfe_budget_data.xlsx` |
| Scenario run script | `run_<sub_scenario_slug>.py` | `run_wfe_budget_allocation.py` |
| Scenario outputs | `<slug>_results.xlsx`, figures `<slug>_<what_it_shows>.png`, plus `MANIFEST.md` | `wfe_budget_snr_vs_rms.png` |
| Reference data | `lowercase_snake.csv` + a `manifest.yaml` per data family | `data/emissivity/soil_dry.csv` |
| Config template | `<band>_<platform>_<variant>.yaml` | `examples/templates/mwir_leo_pushbroom.yaml` |
| Maintenance script | `<verb>_<object>.py` | `scripts/gen_param_reference.py` |
| Golden/test baseline | Named by what it asserts, in the suite that loads it | `tests/integration/golden/mwir_leo_minimal.json` |
| Committed figure | `<subject>_<view_or_metric>.png`, referenced by a doc or test | `docs_screenshots/` style names forbidden going forward |

### 5.3 Prohibited names (reject in review)

`misc*`, `temp*`, `scratch*`, `untitled*`, `notes.md` (unscoped), `stuff*`, `output*.png`, `test.py` outside a test suite, bare `data.csv`/`results.xlsx` without a scoping prefix, any name whose meaning requires opening the file.

Project name is **RADIANT** in all documents. The repo folder name (`SSR_Tool`) is historical; noted once in the root README and nowhere else.

### 5.4 LaTeX-convertible Markdown (owner-ratified 2026-07-24)

All project documents are authored in Markdown, single-sourced: typeset output (PDF via
Pandoc/XeLaTeX) is **generated**, never hand-rewritten — a parallel `.tex` version of any
document is a Rule-27 violation. To keep every document convertible:

1. **Math is written as Pandoc-compatible LaTeX** — inline `$...$`, display `$$...$$` —
   in all *new* documents and in any *new or edited* equation content in existing
   documents. Unicode math approximations (superscript runs, `√`, `×` chains standing in
   for an equation) are not used in new equation content. **Scope: equations and
   mathematical expressions only.** Unicode symbols in prose, tables, and unit strings
   (µm, °, θ_o as a *name*, e-, W/m²/sr/µm) are correct and stay — XeLaTeX handles them;
   converting prose units to math mode is churn, not compliance.
2. **Structure stays in the Pandoc subset**: GFM pipe tables, fenced code blocks with a
   language tag, images by relative path with alt text. No raw HTML blocks in documents
   intended for typeset output (manual-class docs: `theory/`, `guides/`, any future user
   manual). ASCII diagrams live in fenced blocks (they typeset verbatim).
3. **Grandfathering — no churn PRs.** Existing documents with Unicode math are compliant
   as-is until wholesale rewritten; a PR that only converts math notation is rejected.
   New sections added to a grandfathered doc follow this rule; mixed notation within one
   doc is acceptable during that transition.
4. **Build is regenerable (Rule 26).** The canonical conversion is
   `pandoc <files> --pdf-engine=xelatex -o <out>.pdf` (plus the repo template once one
   exists under `scripts/`); generated PDFs are gitignored unless a committed document
   references them, in which case the generator invocation is named in the referencing
   doc or manifest.

Enforcement is review-blocking per Rule 23, same as naming. Motivation: the theory manual
and the planned user manual publish as typeset documents; single-sourcing from Markdown
keeps them in Rule-20 lock-step with the code, which a hand-maintained LaTeX fork cannot.

## 6. Boundary Rules (where docs may NOT live)

- No markdown project-management document inside a Python package (`src/`, `dev_tools/<tool>/`). Tool folders keep only `README.md`, `ARCHITECTURE.md`, `CONTRIBUTING.md`. Their plans/audits/reports live in `docs/plans/` and `docs/reports/<tool>/`. **Carve-out:** the bundled reference-data tree `src/radiant/data/tables/` may keep `MANIFEST.md` / `README.md` files *beside the data they describe* — Rule 26 requires each generated-artifact family to name its generator in an adjacent manifest, and the data ships inside the package so a wheel install carries it. These are data manifests, not project-management markdown (`scripts/check_org_rules.py` skips this subtree).
- No tracking lists inside scenario folders beyond the per-scenario `gaps.md` (whose open items must also be mirrored as CUs or `tracking/gaps.md` entries to be actionable).
- No new top-level entries in `docs/` — the §1 table is closed.
