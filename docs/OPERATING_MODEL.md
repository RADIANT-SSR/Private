# RADIANT Documentation & Work-Tracking Operating Model

**Status:** Draft — pending owner approval (becomes normative when Rules 23–28 land in CLAUDE.md)
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
| `validation/` | Truth anchors, hand calculations, SHA-pinned baselines that current tests reference | Living | — |
| `tracking/` | **The work board.** Exactly two files: `Cleanup_Backlog.md` (all actionable debt, CU-numbered) and `gaps.md` (library capability gaps) | Living — the most-edited files in docs/ | **Exactly two files, forever.** A third tracking file is a rule violation (Rule 25) |
| `plans/` | Plans for work **not yet finished**. Status header mandatory | Living while active | **`plans/` empty ⇒ nothing is in flight.** That invariant is the point |
| `reports/` | Completed point-in-time records: audits, task reports, remediation records | **Immutable** — corrections are new documents | One folder per audit: `<topic>_<YYYY-MM>/` |
| `archive/` | Documents that once claimed to be current and no longer are. Flat, no subfolders. Every file carries a HISTORICAL banner with date + superseded-by | Frozen | — |
| Top-level files | `index.md` (mkdocs home), `OPERATING_MODEL.md` (this file) | — | **Nothing else at top level. Ever.** |

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
CU (debt)     → tracking/Cleanup_Backlog.md ## Open        → ## Resolved w/ commit SHA (Rule 22)
GAP           → tracking/gaps.md (open)                    → marked closed in place w/ commit SHA
```

**Explicit answers to recurring questions:**
- *Do audit results move to archive when actioned?* **No.** The audit stays in `reports/` forever. What "actioning" means: every finding gets a disposition (CU'd / Planned / Declined — Rule 28), and the *plan* that came out of it is what eventually retires to `archive/`.
- *Where does a finished plan go?* `archive/`, moved **in the same PR** that completes its last item. A "✅ COMPLETE" banner on a file still sitting in `plans/` is a violation (Rule 24).
- *Where do CU task briefs go?* `reports/cu_tasks/`. They are point-in-time task specs — records, not plans.
- *What if a spec becomes aspirational (describes unbuilt machinery)?* It stays in `architecture/` with a **DEFERRED** banner at top (e.g., Plugins, GUI). It moves to `archive/` only if the capability is cancelled.
- *Can I edit a report to fix an error?* No. Write a short correction doc in the same `reports/` folder referencing the original.

## 3. Work Tracking Without JIRA

The repo is the tracker. Three views replace a board:

| Board column | Where it lives |
|---|---|
| **Backlog / To-do** | `tracking/Cleanup_Backlog.md` → `## Open` (CU entries) and `tracking/gaps.md` open gaps |
| **In progress** | `docs/plans/` — every file in it is an in-flight effort; small CUs in progress are just a branch |
| **Done** | `Cleanup_Backlog.md` → `## Resolved` (with commit SHA) + `reports/` |

**Intake rule (one door):** anything actionable — bug, debt, doc drift, missing feature, audit finding — enters as a **CU entry** in `Cleanup_Backlog.md` (Rule 21 fields). Nothing is tracked in chat logs, memory, TODO comments, or side files.

**Sizing rule:** a CU that is one PR of work needs nothing else. A CU that needs multiple PRs or design gets a plan doc in `plans/` that references the CU(s) — the plan is the "epic," the CUs are the "tickets."

**The work loop (every effort, no exceptions):**
1. **Pick** — take a CU from `## Open` (or charter an audit per Rule 28).
2. **Branch** — one branch per CU or per plan phase.
3. **Do** — code + tests + lock-step doc updates (Rule 20).
4. **File** — any *new* latent issue found along the way → new CU before the PR merges (Rule 21).
5. **Close** — move the CU to `## Resolved` with SHA + date (Rule 22); if this PR finished a plan, `git mv` it to `archive/` now (Rule 24).
6. **Sweep** — run the hygiene checklist (§4) as part of the PR.

## 4. PR Hygiene Checklist

Every PR description ends with this five-line checklist (copy-paste; it belongs in `.github/PULL_REQUEST_TEMPLATE.md`):

```
- [ ] Placement: every new/moved file is in its Rule-23 home (no PM docs in packages, nothing new at docs/ top level)
- [ ] Lifecycle: no doc in plans/ or architecture/ has an expired claim (completed plan still live, ✅ banner in live tree)
- [ ] Registry: new findings are CUs in tracking/Cleanup_Backlog.md — not a new tracking file
- [ ] Artifacts: committed binaries are (a) test-asserted goldens or (b) doc-referenced figures, with generator named; superseded sets deleted
- [ ] Docs lock-step: touched public surface ⇒ matching RADIANT_*.md updated in this PR (Rule 20)
```

## 5. Naming Conventions

| Kind | Pattern | Example |
|---|---|---|
| Spec | `RADIANT_<Subsystem>.md` | `architecture/RADIANT_Optics.md` |
| ADR | `NNNN-<slug>.md` (4-digit, continue from 0005; legacy `ADR-A…D` keep their IDs) | `adr/0005-data-package-contract.md` |
| Plan | `<Topic>_Plan.md` + mandatory `Status:` header | `plans/Repo_Reorganization_Plan.md` |
| Audit folder | `<topic>_<YYYY-MM>/` | `reports/organization_audit_2026-07/` |
| CU task brief | `CU-NNN_<slug>_Task.md` | `reports/cu_tasks/CU-009_Observer_Geometry_Schema_Task.md` |
| Archived file | original name unchanged + HISTORICAL banner (date, superseded-by) | `archive/Option_C_Implementation_Plan.md` |

Project name is **RADIANT** in all documents. The repo folder name (`SSR_Tool`) is historical; noted once in the root README and nowhere else.

## 6. Boundary Rules (where docs may NOT live)

- No markdown project-management document inside a Python package (`src/`, `dev_tools/<tool>/`). Tool folders keep only `README.md`, `ARCHITECTURE.md`, `CONTRIBUTING.md`. Their plans/audits/reports live in `docs/plans/` and `docs/reports/<tool>/`.
- No tracking lists inside scenario folders beyond the per-scenario `gaps.md` (whose open items must also be mirrored as CUs or `tracking/gaps.md` entries to be actionable).
- No new top-level entries in `docs/` — the §1 table is closed.
