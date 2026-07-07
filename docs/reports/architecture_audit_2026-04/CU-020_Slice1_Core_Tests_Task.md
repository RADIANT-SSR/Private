# Task: CU-020 Slice 1 — Apply pytest level markers to `src/radiant/core/tests/`

**Category**: B (test infrastructure cleanup; no physics changes)
**Effort**: ~2 hours
**Parent CU**: CU-020 in `docs/tracking/Cleanup_Backlog.md` (slice 1 of 5)
**Stand-alone**: yes — can land independently of slices 2–5.

---

## Read first

- `docs/architecture/RADIANT_Testing_Validation.md` §1 (Test Hierarchy), §2 (Level 0), §3 (Level 1), §4 (Level 2)
- `docs/tracking/Cleanup_Backlog.md` → CU-020 entry (the parent's per-directory ladder)
- `pyproject.toml` `[tool.pytest.ini_options]` — markers already declared; `--strict-markers` already enforced (commit `b021d38`)
- Existing marked examples for the pattern:
  - `src/radiant/core/tests/test_constants.py` (21 marks — read this first; canonical Level 0)
  - `src/radiant/core/tests/test_blackbody.py` (17 marks — Level 0 against literature)
  - `src/radiant/core/tests/test_geometry.py` (24 marks — mixed Level 0/1)

---

## Problem statement

`src/radiant/core/tests/` is the slice with the cleanest classification — `core/` contains the foundational abstractions (constants, units, parameters, spectral, chain, geometry, radiometry, blackbody, quantity), so its tests are almost entirely Level 0 (single equations / contracts) or Level 1 (module-level behavior). 7 of the 16 test files in this directory carry markers today; 9 do not.

Current state (as of `b021d38`, 2026-04-25):

| File | Marked? | Notes |
|------|---------|-------|
| `test_constants.py` | yes (21 marks) | reference pattern |
| `test_blackbody.py` | yes (17 marks) | reference pattern |
| `test_geometry.py` | yes (24 marks) | reference pattern |
| `test_los_geometry.py` | yes (27 marks) | reference pattern |
| `test_units.py` | yes (28 marks) | reference pattern |
| `test_parameters.py` | yes (36 marks) | reference pattern |
| `test_spectral.py` | yes (48 marks) | reference pattern |
| `test_descriptors.py` | yes (63 marks) | reference pattern |
| `test_chain.py` | **no** | likely Level 1 (state-machine + ChainRunner contract) |
| `test_chain_mtf.py` | **no** | likely Level 1 (MTF accumulation across stages) |
| `test_quantity.py` | **no** | likely Level 0 (forward/back propagation algebra) + some Level 1 |
| `test_radiometry.py` | **no** | likely Level 0 (RadiometricFrame / NoiseTerm dataclass contracts) |
| `test_responsivity.py` | **no** | likely Level 0 (h·c/λ photon-energy identity) |
| `test_solar.py` | **no** | likely Level 0 (solar irradiance literature anchors) |
| `test_reflectance_descriptor.py` | **no** | likely Level 0/1 (descriptor algebra) |

Goal: every test in `src/radiant/core/tests/` carries exactly one of `@pytest.mark.level0` / `level1` / `level2` / `golden` (golden does not apply in `core/`; level2 unlikely too).

---

## Classification rules (per Testing_Validation §1)

- **level0**: single equation or contract validated against an analytic / literature value. Uses `pytest.approx(..., rel=...)` with explicit tolerance. Touches at most `radiant.core.constants`, `radiant.core.units`, and pure stdlib/numpy/scipy. Runs in <1s.
- **level1**: module-level behavior — exercises one class or function with controlled inputs, may compose 2–3 helpers from the same package. Runs in <10s.
- **level2**: end-to-end through `ChainRunner` or full `RadiantSession`. Touches multiple physics stages.
- **golden**: regression against a frozen JSON output file (`tests/integration/test_golden_*`).

If a single class mixes Level 0 and Level 1 tests, mark each test/method individually rather than the class — one of the marked reference files (likely `test_geometry.py`) already does this pattern; copy it.

---

## Acceptance

1. Every test under `src/radiant/core/tests/` has exactly one level marker.
2. `pytest src/radiant/core/tests/ --collect-only -m level0 | tail -1` count + `pytest ... -m level1` count + `pytest ... -m level2` count = total tests in that directory (no unmarked tests).
3. `pytest src/radiant/core/tests/` passes (no marker-related collection errors under `--strict-markers`).
4. Full regression: `pytest -q` stays at 2798/2798 passing (or grows if you discovered tests that were silently disabled — flag any such finding).
5. R20 doc updates: none expected for this slice — Testing_Validation already declares the markers; this slice fills them in. If you discover that the doc's Level 0 / Level 1 distinction is unclear or contradicts the code, that's a new CU, not a doc edit in this PR.
6. R21: any latent issue uncovered (a test that's actually broken, a test that imports across stage boundaries violating import rules, a test using `pytest.approx` without explicit tolerance per Rule 18) gets a CU entry before the PR merges.

---

## Out of scope

- Marker sweep in any other directory (slices 2–5 — separate tasks).
- Wiring `.github/workflows/ci.yml` (slice 5 of CU-020 — needs user input).
- Reclassifying tests that already have markers — only fill in missing ones. If you think an existing mark is wrong, flag it as a new CU and leave it alone.
- Reorganizing `core/tests/` file layout.

---

## Closure

Move CU-020 to "In Progress (slice 1 done, slices 2–5 open)" in `Cleanup_Backlog.md` rather than fully Resolved — CU-020 only closes when all five slices land.

Commit message stub:
```
test(markers): CU-020 slice 1 — mark every core/tests/ test (level0/level1)

<n> tests across <m> files now carry an explicit level marker, per
Testing_Validation §1 + R18. Strict-markers already enforced
(b021d38); this fills in core/tests/ to 100% coverage so the
directory can be gated by `pytest -m level0` / `pytest -m level1`.

No test logic changed. Sweep classifications:
- Level 0: <count> tests (analytic against literature)
- Level 1: <count> tests (module-level / dataclass contracts)
- (Level 2 / golden: zero — neither applies in core/)

Regression: 2798/2798 pytest passing; <strict-markers collection clean>.
```
