# Backlog Reduction Plan

**Status:** Active — opened 2026-07-28. Supersedes `docs/archive/CU_Autonomous_Cleanup_Plan.md`,
whose charter (the 48 CUs open on 2026-07-19) was fulfilled 2026-07-20.

## Why a new plan rather than more waves on the old one

The previous plan's admission test was *"resolvable without owner feedback, no
results-affecting golden move, no architectural or product decision left open,"* and its
acceptance criterion is literally **"No golden physics result changed."** The backlog it
was written against no longer resembles today's:

| | 2026-07-19 (old plan) | 2026-07-28 (this plan) |
|---|---|---|
| Open CUs | 48 | **62** |
| Category C | few | **19** |
| Marked results-affecting | 0 admitted | **10** |

Ten open CUs are explicitly results-affecting (CU-181, 209, 224, 225, 226, 228, 236, 253,
263, 267). Admitting them would make the old plan's acceptance line false by construction,
and Rule 27 says a superseded plan is replaced, not reopened. Most of the new volume came
from one source — the Geometry-Flexibility Phase-5 validation sweep (CU-246…269) — which is
why so much of it clusters into coupled families rather than independent tickets.

## Structure: three tracks, not one wave list

The tracks exist because **the merge gate differs per track**, not for tidiness. Mixing them
is what would force the whole plan to the slowest gate.

| Track | CUs | Gate before merge |
|---|---|---|
| **A — Hygiene** | 27 Category-A items | Standard gate battery. No golden may move; if one does, the CU stops and escalates. |
| **B — GUI / UX** | CU-116, 122, 126, 137, 138, 216, 217, 219, 220, 239, 240, 241, 242, 243, 244, 246, 248, 250 | Gate battery + GUI suite. Owner-directed specs (242, 243) execute as written. |
| **C — Physics / results** | 19 Category-C + coupled B items | Gate battery + **full golden suite**, and for the 10 results-affecting ones, the `RADIANT_Testing_Validation.md` §5.3 baseline-review protocol **and an owner call first**. |

Track A runs autonomously. Track B runs autonomously except where a CU says
owner-directed. **Track C does not run unattended** — see §Owner triage.

## Carried forward from the archived plan (Rule 22 re-audit)

All nine still-open CUs the old plan named carry over. Rule 22 forbids carrying a deferral
record across a gating-stage landing without re-auditing it, and two of these gates have
moved, so they are re-audited here rather than pasted:

| CU | Track | Re-audit (2026-07-28) |
|---|---|---|
| CU-116 | B | Pair with **CU-248** — the same figure leak from two ends (116 = per-stage retention, 248 = un-closed consumption). Working them apart is how 116's deadlock got re-discovered. Do not schedule separately. |
| CU-164 | A | Pair with **CU-207** — both are the scenario-runner surface. |
| CU-137 | B | **No longer independently deferred.** Its gate was "no cross-stage Acquisition grouping is designed yet"; **CU-242** is now an owner-directed spec for that exact screen. Fold in, do not carry. |
| CU-126 | B | Gate is "until a non-angle arc is added." **CU-250** is queued schematic work — re-audit when 250 lands. Deferral refreshed: gating item CU-250, re-audit 2026-08-31. |
| CU-110 | A | ⚠️ **Gate premise is now stale.** The record justifies the global-`warnings` mutation because "the window runs at most one evaluation worker at a time." There are now **four** worker classes — `ConfigSetEvaluationWorker`, `_SweepWorker`, `_SolveWorker`, `_EvaluateAllWorker`. The single-worker invariant must be re-established or the CU re-scoped **before** anything else touches it. |
| CU-122 (ii) | B | Gating stage **has landed** — the record defers on ADR-0006 §4 attitude ownership, and Geometry-Flexibility Phases 0–5 have since completed. Re-audit due now; the deferral may no longer be valid. |
| CU-138 | Parked | Gate unchanged — re-verified 2026-07-28: `import qtconsole` still fails in this environment. Trigger: qtconsole becomes installable. |
| CU-011 | Parked | Gate unchanged: needs a real MODTRAN **binary invocation**, not a deck import. Trigger: the binary flavor becomes exercisable. |
| CU-087 | Parked | Gated on CU-011. Same trigger. |

Parked ≠ deferred-and-forgotten: each carries a named trigger, and the next PR touching that
area re-audits it (Rule 22).

## Track A — Hygiene (autonomous)

Mechanical, no physics, no goldens, no product decisions. Ordered so the gate hole closes first.

### Wave A1 — the gate can't see itself
- **CU-252** — 36 files fail `ruff format --check`; the documented gate battery runs only
  `ruff check`, so formatter drift is invisible to the thing protecting `main`. Reformat, then
  **widen the gate** to include `ruff format --check`. Subsumes **CU-215** (same defect, one file).
- **CU-227** — two architecture docs name turbulence parameters that do not exist
  (`turbulence_enabled`, `r0_cm`). Doc-only.
- **CU-230** — `display_in_unit`'s docstring denies the affine conversion table it can reach.
  Doc-only.
- **CU-245** — `test_inferrer_reflective.py` documents the S5 ρ(λ) CSV path as deferred; it
  shipped. That stale claim is why the ρ(λ) input stayed unmounted until walkthrough item 6.

### Wave A2 — dead code and dead signals
CU-217 (unreferenced `gui/yaml_format.py`), CU-221 (`scripts/test_docs_code.py` always reports
3 failures, so its signal is dead), CU-207 + CU-164 (scenario-runner surface), CU-249 (one GUI
test file an order of magnitude slower per test than the rest of the suite).

### Wave A3 — doc and provenance accuracy
CU-229 (File_Tree counts stale across every package — fix by generating them and adding the
check to `check_org_rules.py`, per the CU's own note that a hand-maintained count of a growing
tree is a Rule-20 drift generator), CU-266, CU-268, CU-269, CU-218, CU-237 (Rule-19 hoist),
CU-251, CU-240.

### Wave A4 — the re-audit that Wave A1–A3 must not pre-empt
- **CU-110** — re-establish or retire the single-worker invariant (see the carry-forward table).
  Scheduled last in Track A because its finding may re-scope it out of Category A entirely.

## Track B — GUI / UX

**B1 (scaffold first):** CU-241 — three instances now across two stages (Optics pupil/PSF,
Detector Noise pie, Detector + PSF), so it is one shared-scaffold fix plus a minimum readable
width under `PANEL_BESIDE`; fixing cards one at a time is what made it recur. Then CU-116 +
CU-248 together, CU-216.

**B2 (owner-directed specs, execute as written):** CU-242 (+ CU-137 folded in), CU-243.

**B3 (operator traps):** CU-239 + CU-240 (one trap, two layers), CU-244, CU-219, CU-220.

**B4 (geometry presentation):** CU-246, CU-250, then CU-126's re-audit; CU-122 (ii) re-audit.

## Track C — Physics / results (owner triage required)

Not scheduled into waves yet, deliberately. These are **coupled families**, so scheduling them
as independent tickets would duplicate the analysis and the golden refreshes:

**Refreshed 2026-07-29** (Rule 24 — the table below had gone stale enough to mislead:
every question in the original owner-triage list was already answered, and 12 of the 22
CUs it named were already Resolved). Struck-through ids are closed.

| Family | CUs | Note |
|---|---|---|
| Simple-model τ | ~~253~~, 267 | **253 resolved** (the ~8× VIS inflation — dimensionless vertical OD used as a km⁻¹ coefficient). 267 is the same table's piecewise-constant region steps; still open. |
| Up-looking atmosphere | ~~254~~, ~~255~~, 260, 224, ~~225~~, 223, 181 | **Mostly closed 2026-07-29** (`5c0f3dd`): segment composition and the grazing hand-over are done, along with ~~274~~. **260** stays open for the species-split half only (its stated mechanism was corrected — ω₀ → 1, not 0). **224** and **223** are now Stage-deferred behind the MODTRAN batch-2 upwelling families, i.e. behind **226**. **181** untouched. New from that pass: **275** (no near-horizon route for the down-looking/solar columns) and **276** (level topology keeps the target-position dependence). |
| T7 intensity door | 256, ~~258~~, ~~259~~, 264 | **256 and 264 ruled 2026-07-29**: both raise — a declared extent alongside the intensity door is an over-specification, and the silent `sub_pixel` promotion becomes an error. Both are **breaking changes** for configs that pass today; each needs a CHANGELOG entry and a sweep of `scenarios/`+`examples/` before it lands. |
| Turbulence / seeing | 262, ~~228~~, 257 | **262 ruled 2026-07-29**: add `geometry.site_elevation_m`, default 0 (bit-identical today). The per-topology question — whose site, and none at all for a level path — is part of the task, not settled by the ruling. |
| Detection range | 263, 236 | Unchanged. Both change a headline trade-study number. 263 is the reference-range dependence (123 km vs 183 km on one unchanged config). |
| Sampling | 209 | Unchanged. Folded MTF replication frequency. |
| Reachability | 226, ~~261~~, ~~265~~, ~~232~~, ~~231~~, ~~247~~ | **226 is the only one left, and it is now the highest-leverage item in Track C**: wiring the shipped up-looking family into the chain retires 223's deferral and supplies the upwelling anchor that 224 and half of 260 are both waiting on. |

### Owner triage — status

The three questions this section originally posed are **all answered** (CU-253 fixed and its
goldens refreshed; CU-231 and CU-247 both resolved), so Track C is no longer blocked on them.
Rulings taken 2026-07-29 and recorded on the entries themselves: **CU-256** (reject the
over-specification), **CU-264** (both raise), **CU-262** (add the parameter, default 0).

Still owner-gated:
1. **CU-271** — `examples/MWIR_Jason.yaml`: delete as scratch, or rename to a content-stating
   slug? It may be in personal use, so it is not an autonomous delete.
2. **CU-250** — down-looking schematic pixels, under active owner review.
3. **CU-236** — down-looking detection range; the entry itself is marked owner-decision.

## Execution protocol

Unchanged from the archived plan, and still the repo rules:

- **One wave = one short-lived branch off `main`**, per-CU commits inside it, gates green, merge
  to `main` in the same session, delete the branch and its worktree.
- **Per-CU:** Rule 22 close-out (move the entry to Resolved with SHA + date), Rule 20 doc
  lock-step, Rule 29 CHANGELOG for any user-observable change. Registry edits small,
  append-only, committed immediately, and the ID reserved on `origin/main` before use
  (two ID collisions happened on 2026-07-27 and again on 2026-07-28 — CU-242/243).
- **Gate battery:** `pytest` (scoped per CU; full suite at wave close), `mypy --strict
  src/radiant/core src/radiant/api`, `ruff check src/ tests/`, **`ruff format --check`**
  (added by CU-252), `lint-imports`, `check_org_rules.py`, `gen_param_reference.py --check`.
- **Stop-and-flag:** any Track-A or Track-B CU that turns out to move a golden, cross an
  architectural decision, or need a product call is stopped, left Open with a note, and
  reclassified to Track C. It is never guessed at.

## Acceptance

- Track A and Track B CUs each Resolved with a SHA-linked closure, or Open with a
  stop-and-flag note.
- No golden result changed by Track A or Track B. Any that would have → escalated to Track C.
- Track C is not started until the owner triage above is answered.
- This plan moves to `docs/archive/` in the PR that closes its last actionable item (Rule 24).
