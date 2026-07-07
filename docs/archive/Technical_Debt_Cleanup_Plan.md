> **HISTORICAL — archived 2026-07-06 (Registry fold, Phase E of Repo_Reorganization_Plan).** All phases executed 2026-04-24 (commits `03644a2` … `ec4b56a`); the baseline inventory closed as CU-001, CU-002, and CU-010 — all in the Resolved section of `../tracking/Cleanup_Backlog.md`, the sole live registry. No open items remain in this plan.

# Technical Debt Cleanup Plan

**Status:** Active — started 2026-04-24
**Scope:** Pre-existing errors in the RADIANT codebase (not introduced by Gap G or Gap H).
**Governing doc:** `CLAUDE.md` (regression-gate mandate, one-task-per-commit discipline, Rule 11/17/19).

---

## Baseline Error Inventory (as of 2026-04-24, post-Gap-H)

### mypy --strict (core + api) — 10 errors in 5 files

| File | Line | Error |
|------|------|-------|
| `src/radiant/core/responsivity.py` | 75 | `no-any-return` |
| `src/radiant/api/sweep.py` | 187 | `no-redef` (`results_list`) |
| `src/radiant/api/tolerance.py` | 181 | `union-attr` (None guard needed) |
| `src/radiant/api/plot.py` | × 6 | matplotlib `Figure` vs `FigureBase` cast chain |
| `src/radiant/api/tests/test_plot.py` | × 1 | matplotlib cast |

### ruff — 173 errors (129 auto-fixable, 44 manual)

| Code | Count | Auto |
|------|------:|------|
| I001 unsorted-imports | 76 | ✓ |
| F401 unused-import | 45 | ✓ |
| E501 line-too-long | 16 | — |
| RET504 unnecessary-assign | 11 | — |
| E741 ambiguous-var-name | 7 | — |
| F841 unused-variable | 4 | — |
| F541 f-string-no-placeholders | 3 | ✓ |
| B905 zip-without-strict | 2 | — |
| SIM108 if-else-block | 2 | — |
| UP037 quoted-annotation | 2 | ✓ |
| B007 unused-loop-var | 1 | — |
| E402 import-not-at-top | 1 | — |
| RET505 superfluous-else-return | 1 | ✓ |
| SIM300 yoda-conditions | 1 | ✓ |
| UP035 deprecated-import | 1 | ✓ |

### import-linter — 4 broken contracts

1. Core tests importing from `radiant.source.brdf_*` (cross-stage test import).
2. Atmosphere tests importing from `radiant.api.session` (upward import).
3. CLI → platform (2 paths) (should route through `radiant.api`).

---

## Execution Principles

- **One error class per commit.** Never mix ruff fixes with mypy fixes in the same commit.
- **Regression gate is mandatory at every commit.** pytest src + integration + mypy + ruff + lint-imports all must pass before committing.
- **Fix root causes, not symptoms.** A `# type: ignore` is acceptable only when the cast is semantically correct but unexpressible in the type system.
- **Stop and ask** before proceeding if any of these triggers hit:
  - A fix would change physics behavior.
  - A fix would change a public API signature.
  - A golden test result drifts unexpectedly.
  - A fix would require > 50 lines of refactoring.
  - A type error turns out to mask a real bug.
- **Commit message format:** `chore(debt): <phase>.<commit>: <one-line summary>` with body describing the fix and verification steps run.

---

## Phase 0 — Baseline Snapshot (no commit)

Capture the current error state to `/tmp/debt_baseline_2026-04-24/` so we can diff against it after each phase:

```bash
mkdir -p /tmp/debt_baseline_2026-04-24
mypy --strict src/radiant/core src/radiant/api > /tmp/debt_baseline_2026-04-24/mypy.txt 2>&1 || true
ruff check src/ > /tmp/debt_baseline_2026-04-24/ruff.txt 2>&1 || true
lint-imports --config pyproject.toml > /tmp/debt_baseline_2026-04-24/lint_imports.txt 2>&1 || true
```

Confirm counts match the inventory above before proceeding.

---

## Phase 1 — Ruff (themed commits)

Lowest risk. Start here.

### Commit 1.1 — Auto-fixable subset (`ruff check src/ --fix`)
Handles 129 of 173: I001, F401, F541, UP037, UP035, RET505, SIM300. Diff is mechanical (import sorts, dead-import removal, f-string cleanup, annotation unquoting).
- Verify diff contains only the above codes.
- Regression gate.

### Commit 1.2 — E501 line-too-long (16)
Manual line-length fixes. Break long context dicts and nested f-strings; extract locals when expressions are deep.
- Regression gate.

### Commit 1.3 — RET504 unnecessary-assign (11)
Collapse `x = expr; return x` into `return expr` where local name isn't used elsewhere.
- Regression gate.

### Commit 1.4 — F841 unused-variable (4)
Before deleting: grep downstream branches to confirm no path uses the variable. If leftover, delete. If intentional, `# noqa: F841` with comment.
- Regression gate.

### Commit 1.5 — E741 ambiguous-var-name (7)
Rename single-letter `l`/`I`/`O` locals (typically `l → length` or `lam` for wavelength — verify each by context).
- Regression gate.

### Commit 1.6 — Remaining manual (B905, SIM108, B007, E402)
Small cluster — 6 errors total. Each is a one-line judgment call.
- Regression gate.

---

## Phase 2 — mypy: `core/responsivity.py:75` no-any-return

Likely a scipy/numpy return type. Inspect the function, add explicit return annotation or `cast`. One commit.
- Regression gate.

---

## Phase 3 — mypy: `api/sweep.py:187` no-redef `results_list`

Rename or restructure the variable shadowing. One commit.
- Regression gate.

---

## Phase 4 — mypy: `api/tolerance.py:181` union-attr

Missing None guard on an optional attribute access. Add guard. One commit.
- Regression gate.

---

## Phase 5 — mypy: matplotlib batch (`api/plot.py` × 6 + `api/tests/test_plot.py` × 1)

matplotlib's `Figure` vs `FigureBase` type split; `subplots()` returns `FigureBase` generically but we need `Figure`. One commit using `cast(Figure, fig)` at the seam.
- Regression gate.

---

## Phase 6 — import-linter (3 commits)

Highest architectural risk. Take last, so earlier cleanup hasn't touched these files.

### Commit 6.1 — Core tests → `radiant.source.brdf_*`
Move offending tests out of `radiant.core.tests` into the appropriate stage test dir, OR restructure so the test validates only core abstractions. Depends on what each test actually checks.
- **Stop trigger:** if moving tests reveals that the core abstraction is actually coupled to source physics, escalate.
- Regression gate.

### Commit 6.2 — Atmosphere tests → `radiant.api.session`
Same approach: move tests to `tests/integration/` where `api.session` imports are legitimate, OR refactor to not need the session.
- Regression gate.

### Commit 6.3 — CLI → platform (×2)
CLI should route through `radiant.api`. Expose needed platform surface via `radiant.api` and swap the import.
- **Stop trigger:** if the CLI needs something the API doesn't expose, that's a real API gap — raise it separately.
- Regression gate.

---

## Phase 7 — Final verification + backlog update

- Re-run `mypy --strict`, `ruff`, `lint-imports`. Expected result: all clean.
- Update `docs/Cleanup_Backlog.md` to remove resolved items.
- Final commit: `chore(debt): Phase 7 — baseline re-verified, backlog pruned`.

---

## Regression Gate (the five commands run before every commit)

```bash
pytest src/ -q                                                    # 2360 expected pass
pytest tests/integration/ -q                                      # 381 expected pass
mypy --strict src/radiant/core src/radiant/api
ruff check src/
lint-imports --config pyproject.toml
```

All must pass. If any command produces more failures than the baseline, the commit is blocked until the regression is resolved or the baseline is updated with justification.
