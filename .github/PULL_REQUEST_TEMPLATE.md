# Pull Request

## Summary

<!-- 1-3 bullets describing the change and why -->

## Test plan

<!-- How was this verified? Which tests run? -->

- [ ] `pytest src/ -v -m "not golden"` passes
- [ ] `mypy --strict src/radiant/core src/radiant/api` passes
- [ ] `import-linter --config pyproject.toml` passes (5/5 contracts KEPT)
- [ ] `ruff check src/` clean
- [ ] If golden snapshots changed: review protocol per `RADIANT_Testing_Validation.md §5.3` followed

## CLAUDE.md R20 / R21 / R22 checklist

These checks come from CLAUDE.md's non-negotiable rules. Reviewers reject PRs that fail any of them rather than filing a follow-up.

- [ ] **R20 — Doc-and-Code Lock-Step.** Does this PR change a documented surface (public API name, parameter schema, error class, stage protocol, `ChainState` field, public method on `Sensor` / `ChainResult` / `SweepResult`, or an architectural rule)?
  - If **yes**: which `RADIANT_*.md` doc(s) does this PR update in the same commit set? List them: <!-- e.g., RADIANT_Master_Architecture.md §C12, RADIANT_Scripting_API.md §3 -->
  - If **no**: confirm this is a code-only change that does not cross a documented surface.

- [ ] **R21 — Every Finding Becomes a Tracked CU.** Did this work uncover any latent issue orthogonal to the stated task (placeholder implementation, suppressed warning, dead helper, schema mismatch, doc claim that doesn't match code, golden-result tolerance bumped, hardcoded value that should be a parameter)?
  - If **yes**: link the new CU entry in `docs/Cleanup_Backlog.md`: <!-- e.g., CU-NEW-016 added at line 145 -->
  - If **no**: explicitly confirm "no latent issues uncovered."

- [ ] **R22 — CU Closure Is Commit-Linked.** Does this PR close any existing CU?
  - If **yes**: list the CU number(s), and confirm each Resolved entry in `docs/Cleanup_Backlog.md` carries (a) resolution date, (b) linked commit SHA (this PR's merge SHA can be added post-merge if not yet known), and (c) one-line resolution summary.
  - For stage-deferred CUs that this PR's gating stage lands without resolving: confirm the entry was re-audited and either closed or refreshed with new gating stage + new re-audit date.

## Scope discipline

- [ ] Implements only what the task requested; no "while I was here" additions
- [ ] Did not modify files outside the task's stated scope
- [ ] No invented abstractions outside the architecture documents
- [ ] Validation report (per task category A/B/C/D) attached or linked below if required

## Self-review

- [ ] Physics: units traced, signs verified, no eyebrow-raising intermediates
- [ ] Code: docstrings match behavior; tests would fail if the implementation were gutted
- [ ] Architecture: respects all 22 non-negotiable rules in CLAUDE.md

<!-- Validation report for Category B/C/D tasks goes here, or link to the task report file -->
