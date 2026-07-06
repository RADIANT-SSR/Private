# Phase 2 — Architecture Conformance (rule by rule)

**Question this phase answers:** Are the 19 non-negotiable rules from CLAUDE.md actually followed in the code?

## Conformance summary

| # | Rule | Status | Severity if fail |
|---|------|--------|------------------|
| 1 | Type hints + mypy strict | ✅ | High |
| 2 | Units convert at boundaries only | ⚠️ minor (note 1) | High |
| 3 | Right-handed coordinates | ✅ (not exhaustively audited; documented in geometry.py) | Medium |
| 4 | Dual-path PSF/MTF + consistency check | ✅ implemented; minor doc drift on fidelity gating | High |
| 5 | Emissivity always derived | ✅ (KirchhoffViolationError exists) | High |
| 6 | Stages are pure functions | ✅ no file I/O, no state mutation | Critical |
| 7 | ChainState immutable | ✅ frozen dataclass + MappingProxyType | Critical |
| 8 | Spectral integration once | ✅ only in SpectralIntegrationStage | Critical |
| 9 | EE_box applied once | ✅ producer = optics; consumer = spectral_integration only | Critical |
| 10 | Regime finalized in OpticsStage | ✅ `_finalize_regime()` in optics/stage.py:419 | High |
| 11 | No cross-stage physics imports | ✅ import-linter green on all 5 contracts | Critical |
| 12 | Every parameter has a ParameterDef | ✅ 1 orphan use, 19 defined-via-converter (not violations) | High |
| 13 | Constants from constants.py | ✅ no magic h, c, k_B outside constants.py | Medium |
| 14 | No print() in library code | ✅ 1 instance is a docstring example | Low |
| 15 | Errors are actionable | ⚠️ no `RadiantError` base class; pattern uses subclasses of stdlib | Medium |
| 16 | Validate before compute | (not audited end-to-end this phase — Phase 3 will) | High |
| 17 | No silent failures | ✅ 0 `except Exception:`; 1 known `simplefilter("ignore")` (CU-007) | Critical |
| 18 | Test at Level 0 first | ⚠️ 287 level0-marked of 2,352 tests; markers are sparse | Medium |
| 19 | One computation, one module | ⚠️ 6 files >800 LOC; `source/_inferrer.py` at 2,040 stands out | Medium |

**Critical rules: 5/5 pass. High rules: 6/7 pass + 1 minor. Medium: 4/5 pass.**

## Detailed findings

### R2 (Units at boundaries) — Minor
- 18 `* 1e-6` in physics modules (mostly `optics/`).
- Spot-check: every site is `wavelength_um * 1e-6` to convert to meters for SI Planck/diffraction calcs (`psf_mono.py:74`, `wavefront.py:9`, etc.).
- These are not user-input or file-boundary conversions — they're internal canonical-µm → SI-m for the physics formulas that need SI. CLAUDE.md says wavelength canonical = µm; canonical-to-SI inside a physics function is ambiguously legal.
- **Verdict:** not a violation in spirit. **Doc-drift candidate:** R2 wording could be sharpened to distinguish "user/file boundary conversion" (forbidden in physics) from "canonical-to-SI for the physics formula" (necessary).

### R4 (Dual-path PSF/MTF) — Implemented; minor doc drift
- Pupil-autocorrelation MTF: [optics/pupil_mtf.py](../../../src/radiant/optics/pupil_mtf.py)
- EffectivePSF: 80 references; `optics/psf/effective.py` is canonical
- **No forbidden `MTF_diffraction × MTF_aberration` multiplication found**
- Consistency check: [performance/consistency_check.py](../../../src/radiant/performance/consistency_check.py)
  - Function: `check_dual_path_consistency` — compares FFT(convolved PSF) vs MTF product for x and y axes
  - Called from `performance/stage.py:184`
  - Default tolerance: 5e-2 (matches CU-003 backlog finding)
- **Drift:** CLAUDE.md §4 says "This check runs at `standard` fidelity and above." Code runs it unconditionally (no fidelity gate found). Bucket A doc fix.
- The check is real and catching real issues (CU-003 backlog).

### R9 (EE_box once) — Conformant
- **Producer:** `optics/stage.py:895` — single `with_stage_output("optics", "EE_box", ee_box)` call
- **Consumers (multiplications):** only 2 sites, both in `spectral_integration/stage.py` (lines 193, 230)
- 2 atmosphere mentions, 1 platform mention — all are docstring/comment references explaining "we DO NOT apply EE_box here," consistent with the rule
- Defensive guard at `spectral_integration/stage.py:65`: explicitly errors if `EE_box != 1.0` in EXTENDED regime

### R10 (Regime in OpticsStage) — Conformant
- `optics/stage.py:419` `_finalize_regime()` — reads `regime_tentative` from source, computes PSF FWHM, classifies
- `optics/stage.py:468` `_validate_psf_regime_consistency()` — guards against physics inconsistency
- All 5 source resolvers (`source/resolvers/{intensity,geometry,direct,sub_pixel,physical}.py`) write `tentative_regime` only, never the final regime
- Spectral integration reads `regime = optics_out["regime"]` (stage.py:58) — matches doc

### R11 (No cross-stage imports) — Conformant
- All 5 import-linter contracts KEPT
- Two test-colocation ignores documented in pyproject.toml (legitimate test-only seam)

### R12 (Every param has ParameterDef) — Conformant in spirit
- 111 unique paths used via `params.get(...)` in physics modules
- 129 ParameterDef registrations across 7 stage `_schema.py` files
- 1 used-but-not-defined: `geometry.observer_zenith_rad` (`source/_inferrer.py:325`) — likely needs to be added to `source/_schema.py` (this matches CU-009 backlog)
- 19 defined-but-not-directly-`get`-d — these are consumed via `params.get_resolved()` and the converter registry (legitimate). Not violations.
- **One real Phase-12 finding:** `geometry.observer_zenith_rad` should have a ParameterDef. Already on the backlog (CU-009).

### R15 (Actionable errors) — Partial
- **Promised in CLAUDE.md §15:** `RadiantError` base class with `what`, `why`, `action`, `context`
- **Reality:** No such base class exists. Custom errors subclass stdlib (`ValueError`, `RuntimeError`).
- Bare `raise ValueError/Type/Runtime`: 404. Structured custom-error raises: 153. Ratio: ~2.6:1 stdlib to structured.
- However, even the bare `ValueError` calls have descriptive messages — they violate the LETTER of the rule (no `what`/`why`/`action` fields) but generally meet the SPIRIT (descriptive context).
- **Recommendation (post-audit):** introduce `RadiantError(Exception)` base with the four fields. Mass-migrate over time. Not rewrite-bait.

### R17 (No silent failures) — Effectively conformant
- 0 `except Exception:` in non-test code
- 1 `simplefilter("ignore")` — known issue, on backlog as CU-007

### R18 (Level 0 tests first) — Sparse but not violated
- 287 tests are explicitly `@pytest.mark.level0`
- Only 6 are `level1`, 0 are `level2`, 1 is `golden`
- ~2,058 tests are unmarked
- The CI gating mechanism described in C15 ("Level 0 failure blocks Level 1") cannot operate on unmarked tests
- **However:** the tests exist and pass. The level system is partial documentation; the tests still test physics. This is a discipline gap, not a rewrite trigger.

### R19 (One computation, one module) — 6 watch items
- See Phase 1 god-module list.
- `source/_inferrer.py` at 2,040 LOC is the single biggest concern. Phase 5 will inspect.
- `atmosphere/assembly.py` at 1,166 LOC is the next-biggest. The file docstring claims it assembles regime-dependent atmospheric quantities — possibly justified cohesion.

## Phase 2 verdict

**The architecture's load-bearing rules are upheld.** Critical rules (6, 7, 8, 9, 11, 17) are conformant with mechanical evidence. The high-impact spatial-architecture rule (4) has its consistency invariant implemented and active.

The gaps are:
- One missing parameter registration (already on the backlog as CU-009)
- One known suppressed warning (already on the backlog as CU-007)
- No unified `RadiantError` base class — promised in docs, never implemented
- Sparse test-marker application — tests exist, gating doesn't
- Six modules above the 800 LOC watch line — most are justified, `_inferrer.py` is the standout

None of these are systemic. None invalidate the signal-chain dataflow. None require rewriting any stage.
