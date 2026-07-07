# RADIANT Rewrite-vs-Refactor Audit — Plan

**Date initiated:** 2026-04-24
**Auditor:** Claude (Opus 4.7), running unattended overnight
**Scope:** Read-only audit of `src/radiant/` against `docs/RADIANT_*.md`
**Question:** Should RADIANT be rewritten, partially rewritten, or continued with cleanup?

---

## Goal
Produce a defensible recommendation backed by quantitative and qualitative evidence — not vibes. Reconcile docs against code as a deliverable, regardless of which path wins.

User direction (2026-04-24):
- Audit is read-only on `src/` and `docs/RADIANT_*.md`. All output goes under `docs/reports/architecture_audit_2026-04/`.
- Ambiguities log to `findings/open_questions.md` and continue (no stop-and-ask overnight).
- Assume physics is correct. Focus is architecture, organization, and code-base assembly quality.

## Decision Framework (committed up-front)

**Recommend full rewrite only if ≥3 hold:**
- Systemic violation of the 18 non-negotiable rules in load-bearing physics paths
- The 8-stage signal chain is bypassed in production code paths
- Physics modules cross-import each other (Rule 11) in a way that can't be unwound
- Critical physics lack truth anchors *and* disagree with hand calculations (skipped per user direction — physics assumed correct)
- Doc-vs-code drift is so severe the docs themselves must be rewritten
- God modules (>1000 LOC) dominate; cleanup would require touching >40% of files

**Recommend partial rewrite** if 1–2 hold and they cluster in identifiable stages.

**Recommend continue + cleanup** otherwise.

## Phases

### Phase 0 — Calibration
Read the spec corpus, convert each of the 18 rules into a verifiable predicate.

### Phase 1 — Mechanical Health
LOC, file-size distribution, complexity, mypy/ruff/import-linter status, dependency graph, dead code, duplication, magic-number/print/except scans.

### Phase 2 — Architecture Conformance (rule-by-rule)
For each of the 18 rules, run the predicate and record file:line for every violation.

### Phase 3 — Physics Pipeline Tracing (structural only)
Trace SNR / NEDT / NIIRS pipelines end-to-end. Verify pipeline structure matches doc. *Numerical validation deferred per user direction.*

### Phase 4 — Doc-vs-Code Reconciliation
Extract falsifiable claims from docs; mark ✓/✗/?. Classify drift Bucket A/B/C.

### Phase 5 — Sloppiness Signals
Workarounds, `_v2`/`_legacy` symbols, swallowed warnings, dead helpers, schema drift, gutted-test patterns.

### Phase 6 — Synthesis & Recommendation
Score each criterion. Output three-option comparison.

## Deliverables (all under `docs/reports/architecture_audit_2026-04/`)
1. `Audit_Plan.md` — this file
2. `findings/phase1_mechanical.md`
3. `findings/phase2_rule_conformance.md`
4. `findings/phase3_physics_traces.md`
5. `findings/phase5_sloppiness.md`
6. `findings/open_questions.md` — ambiguities logged during the run
7. `Doc_Drift_Report.md`
8. `Doc_Reconciliation_Plan.md`
9. `Recommendation.md`
10. (Conditional) `Rewrite_Scope.md` if recommendation is rewrite

## Guardrails
- Read-only on `src/` and `docs/RADIANT_*.md`
- All findings cite `file:line`
- Ambiguities → `open_questions.md`, continue
- New debt → existing `docs/tracking/Cleanup_Backlog.md` format (logged in audit, not appended live)
