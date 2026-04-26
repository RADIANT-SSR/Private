# RADIANT Cleanup Backlog

**Purpose**: track technical-debt and follow-up tasks discovered while executing feature work, so they don't get lost and don't contaminate the feature PR scope.

**Usage**: any stage/task that uncovers a latent issue orthogonal to its scope appends an entry here. Entries carry enough context (file paths, commands, symptoms) to be picked up cold. Closed entries move to the "Resolved" section at the bottom with the PR or commit that fixed them.

**Not for**: items inside the current feature's scope (those go in the feature plan), scenario-specific gaps (those go in the scenario's `gaps.md`), or operational/runtime gaps already tracked in `docs/gaps.md`.

---

## Open


### CU-020 — Pytest level0/1/2/golden marker sweep + CI gating per Testing_Validation §3

**Discovered**: 2026-04-25 audit, tracked as CU-NEW-05 in `audit_2026/Reconciliation_Tasks.md`. `RADIANT_Testing_Validation.md` §1 declares a four-level test hierarchy with strict gating (Level 0 blocks Level 1 blocks Level 2; golden in a separate job). The pytest config defines the four markers but only **362 of 2798 tests (12.9%)** currently carry one — and the `.github/workflows/` directory does not exist, so no CI gating is wired at all.

**Status**: Open / In Progress (slices 1–4b of 5 done; slice 5 still pending). The full repo (2798 tests) is now 100% marker-covered — every test in `pytest --collect-only` carries exactly one of `level0` / `level1` / `level2` / `golden`. Only the CI workflow remains. `--strict-markers` is in `addopts` (commit `b021d38`). Slice 1 (`src/radiant/core/tests/`) brought the directory to 100% marker coverage on 2026-04-25: 369/369 tests carry exactly one of `level0` (335) / `level1` (34); zero `level2` or `golden`. The slice also surfaced 9 unmarked tests in `test_parameters.py::TestParameterSuggestions` that the original inventory missed (they were silently uncategorized but passing); they are now `level0`. Slice 2 (`src/radiant/source/tests/` + `src/radiant/atmosphere/tests/`) brought both directories to 100% marker coverage on 2026-04-25: 665/665 tests carry exactly one of `level0` (318) / `level1` (344) / `level2` (3); zero `golden`. The slice surfaced 3 tests that genuinely run a full `RadiantSession` end-to-end and were therefore marked `level2` rather than `level1` (`test_inferrer_user_intensity.py::TestUserIntensityChainRun::test_chain_runs_on_vacuum_path`, `test_inferrer_user_radiance.py::TestUserRadianceChainRun::test_chain_runs_and_at_aperture_matches_user_radiance`, `test_e_sky_decomposition.py::TestStageOutputInspectability::test_components_published_on_stage_outputs`). Slice 3 (the optics-through-performance ring: `optics`, `platform`, `spectral_integration`, `detector`, `readout`, `performance`) brought all six directories to 100% marker coverage on 2026-04-25: 1052/1052 tests carry exactly one of `level0` (612) / `level1` (440); zero `level2` or `golden` (different from slice 2 — none of these stage tests build a full `Sensor` or call `ChainRunner.run()`; they exercise individual stages with hand-built `ChainState`). Two test files (`platform/tests/test_stage_mtf_term.py`, `performance/tests/test_consistency_check.py`) were missing `import pytest` and got that one-line addition alongside the markers. Slice 4 (`src/radiant/io/tests/` + `src/radiant/cli/tests/` + top-level `tests/`) brought those directories to 100% marker coverage on 2026-04-25: 529/529 tests carry exactly one of `level0` (38) / `level1` (82) / `level2` (399) / `golden` (10). The integration suite under `tests/integration/` is dominated by full-`RadiantSession.run()` tests, which is why slice 4's level2 count (399) is much higher than the upstream slices. Class-level `@pytest.mark.level2` decorators were used wherever the entire class drives `RadiantSession.run()` (8 files in `tests/integration/`); per-test markers were used in `io/tests/`, `cli/tests/`, and at the function level for parametrized integration tests. Slice 4b residual (discovered post-slice-4 verification): `src/radiant/api/tests/` (7 files), `src/radiant/data/tests/` (4 files), `src/radiant/source/converters/tests/` (1 file) total 179 unmarked tests — these were not in the original five-slice plan and are now flagged as a slice 4b before slice 5 (CI workflow) can gate the full repo. Slice 5 remains: `.github/workflows/ci.yml` wiring.

**File**: `pyproject.toml` (markers + addopts done); `.github/workflows/ci.yml` (does not exist yet); 100+ test files under `src/radiant/*/tests/`, `src/radiant/*/converters/tests/`, and `tests/` lacking marker decorators.

**Symptom** (post-slice-4b, 2026-04-26): `pytest -m level0` collects 1307/2798; `pytest -m level1` collects 1060/2798; `pytest -m level2` collects 421/2798; `pytest -m golden` collects 10/2798. Sum = 2798 — zero unmarked. `pytest --collect-only -m "not level0 and not level1 and not level2 and not golden"` collects zero tests. Slice 5 (`.github/workflows/ci.yml`) is the only remaining CU-020 work; the marker substrate it depends on is now complete.

**Why it still matters**: Without the markers, `pytest -m "not level0"` silently skips tests that *should* be Level 0 — meaning a PR that breaks Planck or Stefan-Boltzmann numerics could pass CI's Level-1/2 jobs (because nothing in those jobs touches the broken physics). C15 ("Test at Level 0 Before Level 2") becomes unenforceable in practice. CI gating is also a non-trivial separate task: there is no `.github/workflows/` directory yet, and adding one wants user input on runner choice, mypy/import-linter integration, and pre-merge vs post-merge job split.

**Suggested fix**: Per-directory ladder with one PR per slice — judgment-heavy enough that batched mechanical assignment risks misclassifying integration-style tests as Level 0. Proposed slice order:

1. ✅ `src/radiant/core/tests/` — landed 2026-04-25 (slice 1 of 5, commit `4f403c9`). 335 level0 + 34 level1. ChainState/ChainRunner state-machine tests + MTF accumulation went level1; transfer-factor crawl across multi-stage state went level1; BRDF protocol satisfaction tests (compose `radiant.source.brdf_*`) went level1; everything else level0.
2. ✅ `src/radiant/source/tests/` + `src/radiant/atmosphere/tests/` — landed 2026-04-25 (slice 2 of 5). 318 level0 + 344 level1 + 3 level2 across 665 tests in 36 files. Inferrer tests (`test_inferrer*.py`, `test_no_atmosphere_subcases.py`, `test_schema.py`, `test_stage.py`) went level1; pure-physics analytic tests (`test_brdf.py`, `test_primitives.py`, `test_solar.py`, `test_emitted.py`, `test_turbulence.py`, scalar-graybody / Planck-inversion converters) went level0; assembly/decomposition/evaluate tests on the atmosphere side went level1; 3 tests that actually run a full `RadiantSession` were marked level2.
3. ✅ `src/radiant/optics/tests/` + `src/radiant/platform/tests/` + `src/radiant/spectral_integration/tests/` + `src/radiant/detector/tests/` + `src/radiant/readout/tests/` + `src/radiant/performance/tests/` — landed 2026-04-25 (slice 3 of 5). 612 level0 + 440 level1 across 1052 tests in 59 files. Pure-physics analytic identities went level0 (Airy / Zernike / Strehl / WFE / GIQE / NEDT / Q-sample / GSD / shot noise / Arrhenius dark / ADC quantization / TDI scaling / pupil-MTF analytic identity / jitter Gaussian MTF / smear sinc MTF / aperture area). Stage protocol tests, MTF-product accumulators, `EffectivePSF` builders, polychromatic-PSF composition, noise-budget aggregation, and metric-registry plumbing all went level1. Zero level2 (none of these stage tests build a full `Sensor` or call `ChainRunner.run()` — different from slice 2). Two files (`platform/tests/test_stage_mtf_term.py`, `performance/tests/test_consistency_check.py`) needed an `import pytest` line added alongside the markers.
4. ✅ `src/radiant/io/tests/` + `src/radiant/cli/tests/` + `tests/` — landed 2026-04-25 (slice 4 of 5). 38 level0 + 82 level1 + 399 level2 + 10 golden across 529 tests. The integration suite is dominated by full-`RadiantSession.run()` tests, hence the high level2 count vs upstream slices. Class-level `@pytest.mark.level2` decorators were applied where every method in a class drives the full chain (8 files in `tests/integration/`); per-test/function markers were applied in `io/tests/`, `cli/tests/`, and parametrized integration test functions.
4b. ✅ `src/radiant/api/tests/` (7 files: `test_inspect.py`, `test_performance.py`, `test_plot.py`, `test_sensitivity.py`, `test_sensor.py`, `test_sweep.py`, `test_tolerance.py`) + `src/radiant/data/tests/` (4 files: `test_detectors.py`, `test_library.py`, `test_solar.py`, `test_templates.py`) + `src/radiant/source/converters/tests/test_csv_loader.py` — landed 2026-04-26 (slice 4b of 5). 179 tests now carry markers: 160 level1 + 19 level2. The level2 cohort is exclusively chain-running tests: `test_sensor.py::TestEvaluation` + `TestSweep` + `TestSummaryExplain::test_explain_chain` (all call `Sensor.evaluate()` or `Sensor.sweep()`), and `test_templates.py::TestTemplateFiles::test_template_loads_via_sensor` (calls `Sensor.from_yaml(...).evaluate()` against every shipped YAML template). All `data/tests/` mock-loader tests, `api/tests/` mock-`_run` sensitivity / sweep / tolerance / plot / inspect tests, and the `_csv` loader contract tests are level1. `test_performance.py` had to gain an `import pytest` line. `test_csv_loader.py` uses module-level `pytestmark = pytest.mark.level1` (13 bare functions, all the same level — keeps the diff tight). With slice 4b landed, the 5-slice repo coverage is **100% marker-covered (2798/2798 tests)**.
5. CI workflow (`.github/workflows/ci.yml`) — Level 0 → Level 1 → Level 2 gated jobs + golden job on main only, plus mypy --strict + lint-imports + ruff.

**Effort**: 1 day total across the five slices; category B (test-infrastructure cleanup, not physics).

### CU-003 — Pre-existing MTF tolerance warning on `swir_aerial_gas.yaml`

**Discovered**: Option C Stage 0 (2026-04-19)
**Investigated**: Phase 2 Track A (2026-04-24)
**Status**: escalated to a stand-alone Category C task (`docs/CU-003_Rect_Kernel_Fix_Task.md`) — this entry stays Open until the follow-on lands.

**File**: `examples/templates/swir_aerial_gas.yaml`
**Symptom**: MTF consistency check reports `max_err_x = max_err_y = 0.05196` vs tolerance `0.050` (~4% miss). All other 13 baseline scenarios pass cleanly.

**Reproducer numbers** (Phase 2 investigation, 2026-04-24):
- Aperture 0.12 m, focal 0.36 m (f/3.0), pixel pitch 20 µm, filter 2.0–2.5 µm.
- `Q = λ·F#/pitch ≈ 0.338` at 2.25 µm — the lowest Q in the suite (next-lowest, `vnir_leo_highres`, has Q ≈ 1.0).
- PSF spatial sampling: `sample_spacing = 1.6875 µm` → `pitch / sample_spacing ≈ 11.852` samples per pixel (non-integer).
- Residual peaks near Nyquist (idx 35 of 64), monotonic at low frequency.

**Per-term sensitivity** (drop-one-MTF-term probe on the product side, re-measure `max_err`):
| Term dropped | max_err |
|---|---|
| (none — baseline) | 0.05196 |
| optics | 0.131 |
| pixel_aperture | 0.546 |
| jitter / smear / ipc / diffusion | 0.05196 (no change) |

Only optics × pixel_aperture matter for this scenario. Decisive verification: substituting the *discrete* rect kernel's actual FFT into the product (in place of the analytic `sinc(π·pitch·f)`) collapses `max_err` to **0.00000** (floating-point identity), proving the entire residual is the pixel-aperture term's PSF-path/MTF-product-path discretization mismatch.

**Root cause**: `src/radiant/optics/pixel_kernel.py::_rect_1d` builds a binary mask `np.where(np.abs(x) <= pitch/2, 1.0, 0.0)` at `1.6875 µm` sample spacing. With `11.852` samples per pixel (non-integer), the kernel quantizes the rect's edges, so its FFT has lower roll-off than the analytic `sinc` that the MTF-product path uses. The PSF path therefore over-attenuates near Nyquist relative to the MTF-product path, and the divergence is greatest at low Q (when `pitch/λF#` is small the rect edges dominate).

**Branch classification (per Phase 2 plan §Track A)**:
- **Finding A** (real Rule-4 bug, missing/mis-applied degradation in one path) — **NO**. Both paths apply pixel-aperture; they disagree only on discretization.
- **Finding B** (numerical edge intrinsic to sampling) — **YES**. Q = 0.338 is the suite minimum; the scenario sits at a corner of the sampled-rect's accuracy regime.
- **Finding C** (inconsistent scenario YAML) — **NO**. The scenario inputs are self-consistent.

**Why this is not a Phase-2 inline fix**: a proper fix is Category C (touches optics physics path, requires three numerical truth anchors, dimensional audit, fragility analysis, and golden-snapshot sweep). Two candidate approaches exist:
1. Anti-aliased rect kernel — replace the binary mask in `_rect_1d` with an integrated rect (subpixel-area weighting at the edges, equivalent to convolving the binary rect with a sample-spacing impulse train and integrating). PSF-path FFT will then match the analytic `sinc` to ~1e-6 across all Q.
2. FFT-based product path — compute the pixel-aperture MTF on the product side from `FFT(_rect_1d(...))` instead of the analytic `sinc`. Symmetric: both paths see the same discretization. Cheaper but couples the product path to the PSF sampling grid.

Approach 1 is preferred (preserves the MTF-product path as the analytic reference; fixes the PSF path to match).

**Why "low priority unless promoted to a regression anchor" is no longer accurate**: the scenario *is* in `tests/integration/snapshots/option_c_baseline.yaml` and will be re-checked at every Option C stage. The miss is ~4% above tolerance, persistent, and the only failing cell. It needs a real fix before it gets confused with a Stage 6 physics drift.

### CU-005 — `theta_o_from_eta` boundary converter is unwired

**Discovered**: Option C Stage 1 (2026-04-19)
**Re-audited**: 2026-04-24 (Stages 7 and 8 have landed)
**Status**: stage-deferral expired — Stage 7 ("no_atmosphere sub-cases", commit `ecc22b4`) and Stage 8 ("90-cell matrix coverage", commit `9fc28aa`) both landed without wiring this function. Per the original CU body, the trigger to "reconsider whether it belongs in `core/` or in a stubbed `sensor/` module" has fired.

**File**: `src/radiant/core/los_geometry.py`
**Symptom (verified 2026-04-24)**: function still has zero non-test callers in `src/radiant/`. Only sites are the definition (`los_geometry.py`), the unit test (`core/tests/test_los_geometry.py`), and the `core/__init__.py` export.
**Why it still matters**: dead-until-wired code in `core/` is a Rule-19 / Rule-11 hazard — the converter sits in `core/` (which forbids cross-stage imports) precisely because it was supposed to be a sensor-side boundary helper, but eight Option C stages later there is no sensor consumer.
**Suggested fix**: pick one of three paths and commit explicitly — (a) wire it into the Earth-LOS-intercept check in `OpticsStage._finalize_regime()` if `h_sensor` is now available downstream of Stage 8; (b) move it to `radiant.api.geometry` (which can legitimately import sensor-side context), keeping a re-export shim from `core/`; (c) delete it and the unit test as truly unused. Decision belongs to whoever owns the SensorDescriptor follow-on ADR.

### CU-007 — Stage-2 MWIR-mixed `UserWarning` is globally suppressed inside `_inferrer.py`

**Discovered**: Option C Stage 2 (2026-04-19)
**Re-audited**: 2026-04-24 (Stage 6 has landed)
**Status**: stage-deferral expired — Stage 6 (E_sky decomposition, commit `b9244fd`) landed without removing the suppression. The MWIR-mixed T3 branch the original suggestion expected is in place, but the inferrer is still building T1Thermal under the warnings-suppressed wrapper for the legacy ε+T scalar surface.

**File**: `src/radiant/source/_inferrer.py::_build_target_descriptor`
**Symptom (verified 2026-04-24)**: `warnings.catch_warnings() / simplefilter("ignore", UserWarning)` still wraps the `T1Thermal(...)` construction at lines ~1670–1687 of `_inferrer.py`. Every MWIR snapshot scenario still triggers the suppression at runtime (silently); the only signal is that *no* warning ever surfaces from those scenarios.
**Why it still matters**: the suppression masks a legitimate modelling flag for any new MWIR cell that lands post-Stage-8 with the legacy scalar surface. With Stage 6's T3Mixed synthesis available, there is no longer a reason to gag the warning — the inferrer should now choose T3 for atmosphere-aware MWIR cases and leave T1 only for the `ρ ≈ 0` cases where the warning is genuinely a false positive.
**Suggested fix**: a stand-alone task that (1) audits which scenarios still flow through the legacy ε+T scalar branch post-Stage-8, (2) routes the atmosphere-aware MWIR cases through T3Mixed instead of T1Thermal, (3) removes the `simplefilter("ignore", UserWarning)` wrapper, (4) explicitly asserts the warning *does not* fire on the post-Stage-8 baseline. Estimate: 50–100 lines, Category B (no physics change, just inferrer routing).

### CU-008 — Stage-2 `GroundBackground` placeholder is grey, not spectral

**Discovered**: Option C Stage 2 (2026-04-19)
**Re-audited**: 2026-04-24 (Stages 3–8 have landed)
**Status**: stage-deferral expired — Stage 3 (atmosphere shadow-mode, commit `018e5a7`) was supposed to replace this, but the placeholder still fires.

**File**: `src/radiant/source/_inferrer.py::_build_background_descriptor`
**Symptom (verified 2026-04-24)**: `_inferrer.py` lines ~1842–1865 still call `_grey_spectraldata(wavelength_um=..., value=bg_eps_scalar, ...)` to construct `GroundBackground(epsilon_g=...)`. The `UserWarning` flagging "placeholder bg, will be replaced in Stage 3" is still emitted on every terrestrial / airborne sub-pixel scenario.
**Why it still matters**: spectral ε_g(λ) matters for radiometric fidelity on non-grey surfaces (vegetation / snow / urban). Stage 6's E_sky decomposition assumes a real spectral ε_g for the reflected-diffuse and reflected-direct-solar terms — the grey placeholder silently degrades those terms wherever it flows through.
**Suggested fix**: stand-alone task — route `source.background.emissivity` through `SpectralDataStore` instead of `_grey_spectraldata`, accept either a `SpectralData` reference or a scalar (with the scalar path explicitly opt-in for "true grey is the user's intent"), remove the placeholder warning, refresh the snapshot regression YAMLs under `src/radiant/source/tests/snapshots/`. Estimate: Category C (touches radiometric path); requires three numerical truth anchors (analytic grey limit, vegetation-spectral library, snow-spectral library).

### CU-009 — Stage-2 `LineOfSightGeometry` uses Kármán-line default instead of scenario-aware `h_atm_top`

**Discovered**: Option C Stage 2 (2026-04-19)
**Re-audited**: 2026-04-24 (Stage 5 has landed)
**Status**: stage-deferral expired — Stage 5 (A3 partial-column atmosphere, commit `4d2c57d`) landed but did *not* wire scenario-aware observer geometry through the inferrer. The partial-column atmosphere consumer side is in place; the producer side (this CU) is still hardcoded.

**File**: `src/radiant/source/_inferrer.py::_infer_los`
**Symptom (verified 2026-04-24)**: `_infer_los` at lines 286–292 still returns `LineOfSightGeometry(h_tgt=h_tgt_m, theta_o=0.0)` with `theta_s` and `delta_phi` unset and `h_atm_top` defaulting to 1e5 m. Only `h_tgt` is read from a parameter (`geometry.target_altitude_m`). No `source.observer_geometry.*` parameters exist on the schema.
**Why it still matters**: every reflective / two-leg / sky-decomposition scenario currently fires as nadir-surface-Kármán. Stage 6's E_sky decomposition has the *capability* to use real `θ_s` and `Δφ`, but the inferrer never supplies them, so the per-scenario radiance is computed at sun-overhead-and-on-axis regardless of the YAML's actual scene geometry.
**Suggested fix**: stand-alone Category B task — register `source.observer_geometry.theta_o`, `source.observer_geometry.theta_s`, `source.observer_geometry.delta_phi`, and `source.observer_geometry.h_atm_top` (optional; default 1e5) as `ParameterDef`s on the SourceStage schema. Wire them through `_infer_los`. Update the 14 baseline scenarios to specify their actual geometry. Expect a re-baseline of every reflective / two-leg cell — coordinate with whoever owns the post-Stage-8 anchor pinning.


### CU-011 — MODTRAN backend's `evaluate()` aliases two-leg τ (single-τ adapter)

**Discovered**: Option C Stage 3 (2026-04-19)
**Re-audited**: 2026-04-24 (Stage 6 has landed)
**Status**: stage-deferral expired — Stage 6 (E_sky decomposition, commit `b9244fd`) landed without splitting the MODTRAN τ. The decomposition operates on whatever the backend supplies; with the MODTRAN backend, that remains a single-τ alias.

**File**: `src/radiant/atmosphere/modtran.py`
**Symptom (verified 2026-04-24)**: `modtran.py` lines 730–752 still emit the `UserWarning` and set `tau_sun = tau`, `tau_up = tau.copy()`, `tau_full_up = tau.copy()`, `L_path_up = lpath`, `L_path_full = lpath.copy()` from a single MODTRAN call. No second TAPE7 run keyed on `θ_s`, no analytic split.
**Why it still matters**: VIS/NIR reflective scenarios that route through MODTRAN now silently lose the solar-zenith dependence that Stage 6's E_sky decomposition was designed to expose. The analytic backend is fine; the MODTRAN backend collapses the split. Mixed-backend test suites can therefore mask real two-leg bugs.
**Suggested fix**: stand-alone Category C task — add a second MODTRAN invocation keyed on `(los.h_tgt, los.theta_s)` to produce `tau_sun` independently from `tau_up`. Cache key must include θ_s. Expect a Cell 28/58 re-baseline conversation if any MWIR snapshot scenario routes through MODTRAN with non-zero θ_s. Block: requires CU-009 to land first (otherwise θ_s is always 0 and the new code path is exercised by zero scenarios).

### CU-012 — Shadow-mode classification injection not wired

**Discovered**: Option C Stage 3 (2026-04-19)
**Re-audited**: 2026-04-24 (Stages 3–8 have landed)
**Status**: stage-deferral expired — Stages 3 through 8 all landed without wiring this. Worse, audit shows zero occurrences of `option_c_classification` *anywhere* in `src/` or `tests/` as of 2026-04-24, suggesting either the field name has drifted or the entire shadow-mode pathway was reworked silently.

**File**: `src/radiant/atmosphere/stage.py` and the integration harness.
**Symptom (verified 2026-04-24)**: `grep -rn option_c_classification src/ tests/` returns zero matches. The CU originally referenced `state.stage_outputs["meta"]["option_c_classification"]`, but that field name no longer exists. The shadow-mode comparison may therefore be running on a different mechanism (anchor-tests-only, post-Stage-6 baseline) — or the per-scenario invariant assertion may have been quietly dropped.
**Why it still matters**: the post-Stage-6 baseline (`Post-Stage-6 baseline` in `Option_C_Implementation_Plan.md`) only pins Cells 28 and 58. Every other "invariant"-classified cell from the Stage 0 baseline snapshot is currently *not* hard-asserted on a per-scenario basis — drift can accumulate without CI signal.
**Suggested fix**: investigation task first (1–2 hours), not a code task — find where the shadow-mode comparison actually lives in post-Stage-8 code (likely renamed or moved to `tests/integration/`), audit which baseline cells are currently hard-asserted vs. soft-checked, then either revive the per-scenario assert with the current field name or document the post-Stage-6 narrowing of scope. Update or close this CU once the investigation lands.

### CU-013 — Shadow-mode `rtol=1e-6` may be too tight for Stage 6 heterogeneous cells

**Discovered**: Option C Stage 3 (2026-04-19)
**Re-audited**: 2026-04-24 (Stage 6 has landed)
**Status**: cannot verify in-place — `_SHADOW_RTOL` constant no longer exists in `src/radiant/atmosphere/stage.py` (`grep -rn _SHADOW_RTOL src/` returns zero matches as of 2026-04-24). Either the constant was renamed/relocated when Stage 6 landed, or the shadow-mode tolerance check was removed/restructured. Linked to CU-012's "the field name has drifted" finding.

**File**: previously `src/radiant/atmosphere/stage.py`; now unknown.
**Symptom (re-stated)**: Stage 6 introduced authorized physics changes to MWIR-mixed and ground-bg-reflected branches. The original concern was that floating-point drift on *invariant*-classified cells might exceed `rtol=1e-6` and false-trip the assertion. Whether that concern materialized depends on the post-Stage-6 tolerance value, which is currently unlocatable.
**Why it still matters**: if the tolerance was dropped entirely (rather than re-tuned), invariant cells now have no hard guard against drift. If it was loosened silently, the magnitude of legitimate drift Stage 6 produced is undocumented.
**Suggested fix**: investigation task — find where the post-Stage-6 invariant-cell assertion lives (or whether it was deleted), recover the chosen rtol and the survey data behind it, document in `docs/Option_C_Implementation_Plan.md` Regression Invariants section. Likely closes alongside CU-012 since they touch the same shadow-mode pathway.

---

## Resolved

### CU-001 — Pre-existing `lint-imports` contract breakages — RESOLVED 2026-04-24

Resolved by Phase 6 of the technical-debt cleanup (commits 2a70558, 7ab1251, bea406a). `cli/convert.py` was the only direct production violation; routed through new `radiant.api.units` re-export. All transitive cli→api→{core,platform,optics,io} edges enumerated in `pyproject.toml` `ignore_imports`. Test-colocation patterns (`radiant.*.tests.*`) granted explicit ignores with `unmatched_ignore_imports_alerting = "warn"`. All 5 import-linter contracts now KEPT.

### CU-002 — Pre-existing `mypy --strict` errors in non-`core`/`api` modules — RESOLVED 2026-04-24

Resolved by Phases 2–5 of the technical-debt cleanup. `core/responsivity.py` no-any-return wrapped with `np.asarray` (commit), `api/sweep.py` no-redef collapsed (commit), `api/tolerance.py` union-attr asserted (commit 2de6b76), `api/plot.py` × 6 + `api/tests/test_plot.py` × 1 wrapped with `cast(Figure, ...)` at the matplotlib seam (commit f9fcf3c). `mypy --strict src/radiant/core src/radiant/api` is now clean (51 source files).

### CU-010 — `test_inferrer.py` imports from `radiant.api` — RESOLVED 2026-04-24

Resolved by Phase 6.2 (commit 7ab1251). `pyproject.toml` import-linter contracts now exempt `radiant.*.tests.*` patterns from the physics-stage and cross-stage rules, matching CLAUDE.md's intent (Rule 11 governs production code; tests legitimately need api/io to build full-schema fixtures).

### CU-004 — `mwir_ground_test.yaml` classification is ambiguous — RESOLVED 2026-04-24 (commit `a880c94`)

Resolved by Phase 2 Track B via Path A (single-enum vocabulary expansion). Added `expected_to_change_at_stage_6_and_stage_7` to the legal-values list on `ScenarioResult` in `scripts/capture_option_c_baseline.py`, taught `_classify()` to apply the compound classification when the scenario name matches `mwir_ground_test`, and updated the `option_c_baseline.yaml` cell directly with a `classification_reason` justifying the dual-stage drift. Path B (`list[str]`) was rejected: today there are zero live consumers of the YAML's `classification` field (the shadow-mode reader CU-012 is unwired and reads from a different stage-output path), making the list-of-string promotion all churn for no gain. Regression gate green: 2360 src + 381 integration + mypy + ruff + 5/5 import contracts KEPT.

### CU-006 — `LineOfSightGeometry` field ordering diverges from plan text — RESOLVED 2026-04-24 (commit `5f07f76`)

Resolved by Phase 2 Track C. Added `kw_only=True` to the `@dataclass` decorator and re-ordered field declarations to match the plan's textual order `(h_tgt, h_atm_top=1e5, theta_o, theta_s=None, delta_phi=None)`. Positional construction now raises `TypeError` at construction time, closing the silent `h_atm_top ↔ theta_o` misassignment footgun before Stage 2's inferrer expands. All call sites already used keyword form; no test fixes required. Regression gate green: 2360 src + 381 integration, mypy/ruff/import-linter clean.

### CU-014 — Stage-4 `GroundBackground` assembly is thermal-only (deferred reflected terms) — RESOLVED 2026-04-24

Resolved by Stage 6 of Option C (commit `b9244fd`, "feat(option-c): Stage 6 — E_sky decomposition"). [src/radiant/atmosphere/assembly.py](../src/radiant/atmosphere/assembly.py) `_assemble_ground_background` (lines 1122–1158) now returns `(L_self + direct + diffuse) * tau_full_up + L_path_full`, where `L_self = epsilon_g * B(T_g)`, `direct = _direct_solar_term(rho_g, atm, cos_ts)` for the reflected-direct-solar term, and `diffuse = _diffuse_sky_term(rho_g, atm)` for the reflected-diffuse-sky term. Both branches that the original CU said were omitted are now present. Cell 28 and Cell 58 stayed bit-invariant because both anchors are `T1Thermal` with `ρ ≡ 0`, so the `(1−ε_g)` reflectance terms vanish identically — confirmed in [docs/Option_C_Implementation_Plan.md](Option_C_Implementation_Plan.md) Regression Invariants table. Verified during the 2026-04-24 stage-deferred audit.

### CU-015 — `readout.stage` lazy-imports `detector.noise.budget` — RESOLVED 2026-04-24 (commit `621414d`)

Investigation showed the fallback (lines 140–149) was unreachable: `RadiantSession` always runs `DetectorStage` before `ReadoutStage`, and every test that exercises `ReadoutStage` directly populates `noise_budget_raw` itself. Replaced the fallback with a `ValueError` that explicitly tells the caller to populate `stage_outputs['detector']['noise_budget_raw']` (CLAUDE.md Rule 17 — fail loudly, not silently). Removed the corresponding `radiant.readout.stage -> radiant.detector.noise.budget` ignore from `pyproject.toml`. All five import contracts now KEPT without exceptions for production cross-stage imports.

### CU-016 — `from radiant import Sensor` not re-exported at top level — RESOLVED 2026-04-25 (commit `52a1fba`)

**Discovered**: 2026-04-25 audit (audit_2026/) finding tracked as CU-NEW-02 in `Reconciliation_Tasks.md`. Doc examples in `RADIANT_Scripting_API.md` (and ADR-C decision Yes/No/No) showed users were expected to write `from radiant import Sensor`, but `radiant/__init__.py` did not re-export it; the only working path was the longer `from radiant.api.sensor import Sensor`.

**File**: `src/radiant/__init__.py`
**Resolution**: Added `from radiant.api.sensor import Sensor` and `__all__ = ["Sensor", "__version__"]` per ADR-C. SensorConfig / ScenarioConfig / BatchRunner were intentionally left out of the top-level surface — users wanting them go through `radiant.api.*` and accept the same stability contract. New tests in `tests/test_public_api.py` (3 tests, level0 + level1) verify (a) the top-level `Sensor` is the same class as `radiant.api.sensor.Sensor`, (b) `radiant.__all__` matches the ADR-C decision exactly, and (c) the doc-example pattern `Sensor.from_yaml(...).evaluate()` runs end-to-end against `examples/mwir_leo_minimal.yaml`. No doc edits were required because the docs were already written against the new (correct) API — the rename brought code into sync with the existing docs (R20 satisfied as a consequence).

### CU-017 — `ChainResult.{signal,noise}_at_frame` doesn't match documented `{signal,noise}_at` — RESOLVED 2026-04-25 (commit `a548c1e`)

**Discovered**: 2026-04-25 audit, tracked as CU-NEW-03. `RADIANT_Scripting_API.md` and `RADIANT_Signal_Chain_Architecture.md` documented `result.signal_at("dn")` / `result.noise_at("dn", term_name="read_noise")` but the implementation used `signal_at_frame` / `noise_at_frame`. Examples written verbatim from the docs would fail with `AttributeError`.

**File**: `src/radiant/io/results.py`
**Resolution**: Renamed methods to the documented names. Imports of the underlying core helpers were aliased (`from radiant.core.quantity import noise_at as _quantity_noise_at, signal_at as _quantity_signal_at`) to avoid name collision with the new method names. Backward-compat aliases `signal_at_frame` / `noise_at_frame` kept for one minor version, each emitting `DeprecationWarning(stacklevel=2)` with a removal note for RADIANT 0.2.0. Added convenience accessors `result.snr()` / `result.nedt()` (returns Kelvin, reads `metrics["nedt_K"]`) / `result.niirs()` per the documented quick-look pattern; missing keys raise `KeyError` (CLAUDE.md fail-loudly policy) rather than returning a sentinel. Test fixture `src/radiant/io/tests/test_results.py` updated to the new names with two new test classes covering deprecation warnings + value parity (3 tests) and metric accessors + KeyError path (4 tests). Two integration tests (`tests/integration/test_full_system.py`, `tests/integration/test_use_case_shapes.py`) updated to the new method names. Regression gate green: 14/14 io tests + 38/38 integration tests pass; mypy --strict clean on core+api (51 files); 5/5 import-linter contracts KEPT. No doc edits were needed (R20 satisfied — the rename brought code in sync with already-correct docs).

### CU-018 — `RadiantError` referenced in CLAUDE.md / docs but no base class existed in code — RESOLVED 2026-04-25 (commit `12d174d`)

**Discovered**: 2026-04-25 audit, tracked as CU-NEW-01 in `audit_2026/Reconciliation_Tasks.md`. `CLAUDE.md` Rule 15, `RADIANT_Master_Architecture.md` §C12/§7.4, and `RADIANT_Testing_Validation.md` §8.1/§8.5 all referenced `RadiantError` and an exception hierarchy "in `radiant.exceptions`", but no such module or base class existed in `src/`. The six concrete exception classes (`ParameterBoundsError`, `KirchhoffViolationError`, `ModtranUnavailableError`, `Tape7ParseError`, `ConfigError`, `ElementConfigError`) inherited only from built-ins (`ValueError`, `RuntimeError`, `Exception`). User code wanting a single `except RadiantError` clause to catch every framework-defined error had no way to do so.

**File**: `src/radiant/core/exceptions.py` (new); modifications to `src/radiant/__init__.py`, `src/radiant/core/parameters.py`, `src/radiant/optics/element.py`, `src/radiant/atmosphere/modtran.py`, `src/radiant/io/config.py`, `src/radiant/io/element_config.py`.
**Resolution**: Introduced `RadiantError(Exception)` in `radiant.core.exceptions` (placed under `core/` so other core modules can import it without violating the "core has no radiant imports" import-linter contract). Re-exported at the top level — `from radiant import RadiantError` — and added to `radiant.__all__`. Migrated all six concrete subclasses to inherit from `RadiantError`. Built-in co-inheritance (`ValueError`, `RuntimeError`) preserved on five of six classes for back-compat with existing `except ValueError` / `pytest.raises(ValueError, ...)` patterns scattered across the suite; this is documented in CLAUDE.md §15 and Master_Architecture §7.4 as a deliberate carve-out. New Level-0 hierarchy contract test in `tests/test_exceptions.py` (10 tests; lives outside any package boundary because it imports from `radiant.optics`/`radiant.atmosphere`/`radiant.io` and would violate the "core has no radiant imports" contract if placed under `core/tests/`). Pins (a) every concrete class is-a `RadiantError`, (b) back-compat co-inheritance still holds, and (c) top-level re-export is the same object as the core import. Doc updates per R20: CLAUDE.md §15 rewritten, `RADIANT_Master_Architecture.md` §C12 + §7.4 rewritten with concrete subclass inventory and built-in co-inheritance carve-out, `RADIANT_Testing_Validation.md` §8.1 updated to show actual class shape, §8.5 hierarchy regenerated to match code (the aspirational `PhysicsError` / `PluginError` / `ReproductionError` tiers and finer-grained `ParameterTypeError`/`ParameterEnumError`/etc. families were not implemented and are explicitly noted as deferred). Regression gate: 10/10 hierarchy tests + 0 regressions in existing exception-raise sites (`pytest.raises(ValueError, ...)` patterns still match because of co-inheritance).

### CU-019 — `ChainResult.to_provenance_record()` referenced in docs but no implementation existed — RESOLVED 2026-04-25 (commit `70e512d`)

**Discovered**: 2026-04-25 audit, tracked as CU-NEW-04 in `audit_2026/Reconciliation_Tasks.md`. `RADIANT_Master_Architecture.md` §C13, `RADIANT_Signal_Chain_Architecture.md` §7 (`ChainResult` interface listing), and `RADIANT_Parameter_System.md` provenance-audit section all promised that every `ChainResult` exposes a complete provenance record (run ID, RADIANT version, git commit, Python version, dependency versions, resolved parameter set, input file hashes, active models). The actual `radiant.io.results.ChainResult` had no `to_provenance_record()` method — and even if it had, none of the supporting plumbing existed: `ChainState` had no `run_id` field, no helper for `git_commit` / `dependency_versions` lived anywhere in `core/`, `ParameterSet` did not track which YAML files had been loaded, and `RadiantSession.run` did not pass `params` through to the result. A user calling the documented API would get `AttributeError: 'ChainResult' object has no attribute 'to_provenance_record'`.

**File**: `src/radiant/core/provenance.py` (new); modifications to `src/radiant/core/chain.py`, `src/radiant/core/parameters.py`, `src/radiant/io/config.py`, `src/radiant/io/results.py`, `src/radiant/api/session.py`.
**Resolution**: Built the §C13 contract end-to-end in five layers. (1) Pure helpers in `radiant.core.provenance`: `new_run_id()` (UUID4 string), `git_commit()` (short SHA, `"unknown"` outside a repo or with no git binary — never raises), `python_version_string()` (`MAJOR.MINOR.PATCH`), `dependency_versions()` (`{name: version}` for the four declared runtime deps; `"unknown"` for missing packages), `hash_file()` (SHA-256, 64 KiB chunks). Lives in `core/` so any module — including the rest of `core` — can import it without breaking the "core has no radiant imports" contract. (2) `ChainState.run_id: str | None` field; `ChainRunner.run` mints a fresh UUID4 if the caller doesn't supply one. (3) `ParameterSet._loaded_files` list + `record_loaded_file(path, sha256)` method + `loaded_files` property; loaders dedupe identical entries while letting same-path/new-hash through. (4) `radiant.io.config.load_config` calls `params.record_loaded_file(str(path), hash_file(path))` after a successful YAML parse, so every file the run consumed appears in the record. (5) `ChainResult.__init__` takes an optional `params: ParameterSet | None`; `RadiantSession.run` passes the resolved params through; `to_provenance_record() -> dict[str, Any]` returns the JSON-serialisable record with all eight §C13 keys. Provenance helpers degrade to `"unknown"` rather than raising on environmental edge cases — provenance must never block a chain run. While plumbing the field-hash list into `ParameterSet.__init__`, an in-place fix corrected an orphaned consistency-group validation block (the `for g in self._groups` loop sat after a `return` statement and was unreachable). New tests in `tests/test_provenance.py` (36 tests across 8 classes; lives outside any package boundary for the same reason as `tests/test_exceptions.py`): UUID4 shape + uniqueness, `git_commit` happy-path + non-repo + missing-binary fallbacks, Python version format, dependency completeness, `hash_file` known-digest + determinism + chunked-read + missing-file raise, `ChainState.run_id` default + round-trip, `ChainRunner` UUID-mint + caller-passthrough + per-run uniqueness, `ParameterSet.record_loaded_file` dedupe + same-path-new-hash, `load_config` records-on-YAML / records-nothing-on-dict, full §C13 contract from synthetic state, full end-to-end run from `examples/mwir_leo_minimal.yaml`. Doc updates per R20: `RADIANT_Master_Architecture.md` §C13 expanded with the canonical eight-field key table + helper-module pointer, `RADIANT_Signal_Chain_Architecture.md` `ChainState` skeletons gained the `run_id` field, `RADIANT_Parameter_System.md` provenance-audit section now records the `parameter_set` + `input_file_hashes` linkage to `ChainResult.to_provenance_record()` and the `record_loaded_file` plumbing. Regression gate: 36/36 new provenance tests + full suite (see commit body for counts) + 5/5 import-linter contracts kept + mypy --strict on core+api unchanged.
