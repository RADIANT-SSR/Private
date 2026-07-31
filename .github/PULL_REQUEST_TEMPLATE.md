# Pull Request

## Summary

<!-- 1-3 bullets describing the change and why -->

## Test plan

<!-- How was this verified? Which tests run? -->

- [ ] `pytest src/ -v -m "not golden"` passes
- [ ] `mypy --strict src/radiant/core src/radiant/api` passes
- [ ] `lint-imports --config pyproject.toml` passes (all contracts KEPT)
- [ ] `ruff check src/` clean
- [ ] If golden snapshots changed: review protocol per `RADIANT_Testing_Validation.md §5.3` followed

## CLAUDE.md R20 / R21 / R22 checklist

These checks come from CLAUDE.md's non-negotiable rules. Reviewers reject PRs that fail any of them rather than filing a follow-up.

- [ ] **R20 — Doc-and-Code Lock-Step.** Does this PR change a documented surface (public API name, parameter schema, error class, stage protocol, `ChainState` field, public method on `Sensor` / `ChainResult` / `SweepResult`, or an architectural rule)?
  - If **yes**: which `RADIANT_*.md` doc(s) does this PR update in the same commit set? List them: <!-- e.g., RADIANT_Master_Architecture.md §C12, RADIANT_Scripting_API.md §3 -->
  - If **no**: confirm this is a code-only change that does not cross a documented surface.

- [ ] **R21 — Every Finding Is Recorded (two-tier).** Did this work uncover any latent issue orthogonal to the stated task (placeholder implementation, suppressed warning, dead helper, schema mismatch, doc claim that doesn't match code, golden-result tolerance bumped, hardcoded value that should be a parameter)?
  - If **yes** and it passes an intake test (results-affecting / owner-gated / blocking / workflow-visible): link the new CU entry in `docs/tracking/Cleanup_Backlog.md`.
  - If **yes** but below CU grade: link the appended `docs/tracking/Findings_Log.md` line.
  - If **no**: explicitly confirm "no latent issues uncovered."

- [ ] **R22 — CU Closure Is Recorded and Verifiable.** Does this PR close any existing CU?
  - If **yes** (code-backed): confirm the closing commit carries a `CU-Closes: NNN` message trailer, moves the entry to Resolved in that same commit with `(commit trailer)` + date + one-line resolution summary, and bundles the CHANGELOG/doc lock-step updates.
  - If **yes** (ruling-backed): confirm the heading carries ACCEPTED / DECLINED / FOLDED / DEMOTED with its `no commit — <reason>` clause.
  - For stage-deferred CUs (or family heads) whose gating stage this PR lands without resolving: confirm the entry was re-audited and either closed or refreshed with new gating stage + new re-audit date.

## Scope discipline

- [ ] Implements only what the task requested; no "while I was here" additions
- [ ] Did not modify files outside the task's stated scope
- [ ] No invented abstractions outside the architecture documents
- [ ] Validation report (per task category A/B/C/D) attached or linked below if required

## Organization hygiene (CLAUDE.md R23–R29, `docs/OPERATING_MODEL.md`)

- [ ] Placement & naming: every new/moved file is in its Rule-23 home and follows OPERATING_MODEL §5 naming (no PM docs in packages, nothing new at docs/ top level, no status/version words in filenames)
- [ ] Lifecycle: no doc in `plans/` or `architecture/` has an expired claim (completed plan still live, ✅ banner in live tree); completed plans moved to `archive/` in this PR
- [ ] Registry: new findings are recorded per Rule 21 (CU in `docs/tracking/Cleanup_Backlog.md`, or a `docs/tracking/Findings_Log.md` line) — not a new tracking file
- [ ] Artifacts: committed binaries are (a) test-asserted goldens or (b) doc-referenced figures, with generator named; superseded sets deleted in this PR
- [ ] Audits: any audit findings this PR actions carry a disposition (CU'd / Planned / Declined)
- [ ] Changelog (R29): if this PR changes computed results or a public surface (API, parameter, metric, error class, config field), an entry was added under `CHANGELOG.md [Unreleased]`; **Results-affecting:** prefix used where golden values / defaults / physics changed

## Self-review

- [ ] Physics: units traced, signs verified, no eyebrow-raising intermediates
- [ ] Code: docstrings match behavior; tests would fail if the implementation were gutted
- [ ] Architecture: respects all 29 non-negotiable rules in CLAUDE.md

<!-- Validation report for Category B/C/D tasks goes here, or link to the task report file -->
