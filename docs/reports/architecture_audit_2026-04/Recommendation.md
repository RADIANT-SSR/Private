# RADIANT Audit — Recommendation

**Date:** 2026-04-24 → 2026-04-25 (overnight unattended audit)
**Auditor:** Claude (Opus 4.7), read-only
**Scope:** Architecture and code-base assembly quality. Physics correctness assumed (per user direction).
**Question:** Should RADIANT be rewritten, partially rewritten, or continued with cleanup?

---

## Recommendation: **Continue + Cleanup. Do not rewrite.**

The "code base has gotten sloppy and disorganized and strung together haphazardly" hypothesis is **not supported by the evidence**. RADIANT is a young (70 commits), disciplined codebase with strong mechanical guardrails, near-complete adherence to its own architecture rules, and a healthy debt-tracking culture. The drift between docs and code is real but bounded — roughly 4 person-days of work, broken into independent commits, none of it rewrite-bait.

A full or partial rewrite would discard a fully green CI/CD-gated 8-stage pipeline, ~35,000 LOC of production code with a 0.93 test-LOC ratio, 100% test pass rate on 2,741 tests, and a working dual-path PSF/MTF consistency invariant that is actively catching real physics bugs. There is no architectural problem to rewrite *around*.

---

## Decision-criteria scorecard

The audit committed up-front (`Audit_Plan.md` §Decision Framework) to recommending rewrite only if **≥3** of the following criteria hold. Scoring against the Phase 1–5 evidence:

| # | Criterion | Holds? | Evidence |
|---|-----------|--------|----------|
| 1 | Systemic violation of the 19 non-negotiable rules in load-bearing physics paths | **No** | Phase 2: 5/5 critical rules conformant; 6/7 high rules + 1 minor; the only soft-fails (no `RadiantError` base, sparse test markers) are bottom-up gaps, not load-bearing-path violations |
| 2 | The 8-stage signal chain is bypassed in production code paths | **No** | Phase 3: single assembly point at [api/session.py:41-50](../../src/radiant/api/session.py#L41-L50); no bypass paths; EE_box single-producer/two-consumer pattern verified; regime finalized exactly once in OpticsStage |
| 3 | Physics modules cross-import each other (Rule 11) in unwindable ways | **No** | Phase 1: `import-linter` green on all 5 contracts; 0 cross-stage physics imports |
| 4 | Critical physics lack truth anchors and disagree with hand calculations | **N/A** | Skipped per user direction (physics assumed correct) |
| 5 | Doc-vs-code drift so severe the docs themselves must be rewritten | **No** | Phase 4: 16 drift findings — 7 Bucket-A (mechanical doc fixes), 5 Bucket-B (small code-side cleanups), 3 Bucket-C (ADR decisions). Total reconciliation: ~4 person-days |
| 6 | God modules dominate; cleanup requires touching >40% of files | **No** | Phase 1+5: 7 files >800 LOC (3.2% of 217 production files). All carry justifying docstrings or are intrinsic state machines. The largest, `source/_inferrer.py` at 2,040 LOC, is a deliberate documented compatibility-bridge module |

**Score: 0 of 5 applicable criteria hold.** Recommendation: **Continue + Cleanup**.

---

## Three-option comparison

| Aspect | Option 1 — Continue + Cleanup *(recommended)* | Option 2 — Partial Rewrite | Option 3 — Full Rewrite |
|--------|-----------------------------------------------|----------------------------|-------------------------|
| Effort | ~4 person-days for doc reconciliation + Bucket B/CU-NEW backlog. Existing CU backlog (8 open) on its current cadence absorbs the rest. | ~3–6 person-months. Would target `source/_inferrer.py` and the descriptor surface. | ~12–18 person-months. Throws away 70 commits of working physics, all golden tests, and a battle-tested CI gate set. |
| Risk to physics correctness | Low. No physics changes; cleanup is doc + structural. | Medium. Re-scoping the inferrer touches the descriptor surface, which is the boundary that all 8 stages downstream consume. | High. Re-implementing 35,000 LOC of physics with no guarantee the new code preserves the 14 baseline scenarios' values. |
| Risk to the 5 import contracts | None — they stay green. | Medium — refactors that move logic between stages risk new contract breaches. | High — rebuilding the contract surface from scratch. |
| Risk to the 2,741 tests | None | Re-baselining required for any module the partial rewrite touches | Total re-baselining required |
| Time-to-restore current capability | Immediate (no regression) | Months of partial degradation | A year+ of degradation |
| What it solves | The 16 drift items + 8 open CUs on the existing backlog | Possibly the `source/_inferrer.py` size concern (2,040 LOC) — though Phase 5 found that file is documented and rule-conformant, not crufty | Nothing the audit identified; the architecture is already what a rewrite would target |
| What it does *not* solve | Nothing the audit identified as systemic | Doc drift would still need reconciliation alongside | Doc drift would still need reconciliation alongside |

The cost/benefit is asymmetric: Options 2 and 3 throw away a working pipeline to fix problems the audit did not find, while Option 1 closes the actual identified gaps in days, not months.

---

## What "Continue + Cleanup" looks like in practice

Sequenced from the [Doc_Reconciliation_Plan.md](Doc_Reconciliation_Plan.md):

### Week 1 — Decisions
1. Resolve **ADR-A** (FidelityPreset: keep or drop)
2. Resolve **ADR-B** (SNR/metrics: confirm soft-fail SNRResult pattern)
3. Resolve **ADR-C** (top-level public API surface)

### Week 1 — Mechanical doc updates (after ADRs)
- A1 `RADIANT_Spatial_Complete.md` — rewrite or retire (1 day)
- A2 `RADIANT_File_Tree.md` — regenerate from `find` (1 hour)
- A3 `RADIANT_Signal_Chain_Architecture.md` §2/§7 — fix Stage protocol snippet (30 min)
- A4 CLAUDE.md "18 rules" → "19 rules" (5 min)
- A5 Mark Phase{1,2,3} docs as `[archive]` (30 min)
- A6 Mark `RADIANT_Plugins.md` as `[v2 deferred]` (5 min)

### Week 2 — Code cleanups (file as CU-NEW-01 through CU-NEW-05)
- **CU-NEW-01**: Introduce `radiant.exceptions.RadiantError` base; migrate existing custom errors (4–6 hours)
- **CU-NEW-02**: Add top-level `Sensor` re-export to `__init__.py` (5 min)
- **CU-NEW-03**: Rename `signal_at_frame` → `signal_at` with deprecation alias (30 min)
- **CU-NEW-04**: Complete `ChainResult.to_provenance_record()` per C13 (1–2 days)
- **CU-NEW-05**: Apply `level0`/`level1`/`level2` markers across the test suite + wire CI gating (1 day)

### Concurrent — Existing CU backlog (the 8 open items)
The team is already running a healthy weekly cadence (CU-001/002/004/006/010/014/015 all closed in the past week). Continue. The most physics-touching open items (CU-003 rect-kernel fix, CU-009 observer-geometry parameters, CU-011 MODTRAN two-leg τ) are the right next focus.

**Total scoped effort: ~4 person-days for the audit-derived items**, on top of the existing CU cadence. Independent commits, low risk, no rewrite-bait.

---

## What the evidence actually says about the code base

Pulling together the strongest signals from Phases 1–5:

**Mechanical health (Phase 1):**
- All 5 import-linter contracts KEPT
- `mypy --strict` green on `core` and `api`
- `ruff check` green
- 2,741 tests collected; 100% pass on the measured 2,280 non-optics + 461 optics
- 0 `except Exception:` swallowing, 0 file I/O in stages, 0 direct `ChainState` mutations, 0 magic constants, 0 `print()` in lib code (1 docstring example)

**Architecture conformance (Phase 2):**
- 5/5 critical rules (R6 purity, R7 immutability, R8 single-spectral-integration, R9 EE_box once, R11 no cross-stage, R17 no silent failures) — conformant
- The dual-path PSF/MTF consistency invariant (R4, the central architectural commitment) is implemented, active, unconditional, and is *catching real bugs* (CU-003)

**Pipeline structure (Phase 3):**
- 8-stage assembly matches the doc exactly
- SNR / NEDT / NIIRS chains are pure functions reading from `ChainState` — no side channels, no bypass paths

**Doc reconciliation (Phase 4):**
- 16 drift items found, all bounded and fixable. None invalidate the architecture. Most are doc-side stale (7 Bucket-A items).

**Sloppiness (Phase 5):**
- 0 TODO/FIXME/HACK markers in production code
- 0 `_v2`/`_legacy`/`_deprecated` symbols
- 0 gutted or skipped tests (1 graceful matplotlib skip)
- 1 production-code warning suppression (CU-007)
- 1 orphan ParameterDef (CU-009)
- Every code-side debt category the audit found was already on the existing CU backlog with a remediation plan

**The codebase shows no signs of haphazard assembly.** What it shows is a young, disciplined first-principles physics framework that has built its architectural rules into automated CI gates, kept those gates green, refactored in place rather than spawning parallel versions, and tracked debt openly with explicit deferral expiry. That is the opposite profile of a codebase that should be rewritten.

---

## Open questions for human review

(Logged in [findings/open_questions.md](findings/open_questions.md) — none accumulated during the run; all ambiguities resolved by user pre-direction or by the doc supersession table.)

The three Bucket-C decisions (ADR-A, ADR-B, ADR-C) are the only items that need human judgment before the cleanup work proceeds. None of them are rewrite triggers; they are scope decisions on an already-working pipeline.

---

## Conditional rewrite-scope document

Per the Audit_Plan.md guardrails, a `Rewrite_Scope.md` would be produced only if the recommendation were rewrite or partial rewrite. Because the recommendation is Continue + Cleanup, no `Rewrite_Scope.md` is generated. The forward-looking work is captured in [Doc_Reconciliation_Plan.md](Doc_Reconciliation_Plan.md) and the existing [docs/tracking/Cleanup_Backlog.md](../Cleanup_Backlog.md).
