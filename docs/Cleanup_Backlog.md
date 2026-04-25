# RADIANT Cleanup Backlog

**Purpose**: track technical-debt and follow-up tasks discovered while executing feature work, so they don't get lost and don't contaminate the feature PR scope.

**Usage**: any stage/task that uncovers a latent issue orthogonal to its scope appends an entry here. Entries carry enough context (file paths, commands, symptoms) to be picked up cold. Closed entries move to the "Resolved" section at the bottom with the PR or commit that fixed them.

**Not for**: items inside the current feature's scope (those go in the feature plan), scenario-specific gaps (those go in the scenario's `gaps.md`), or operational/runtime gaps already tracked in `docs/gaps.md`.

---

## Open


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

### CU-004 — `mwir_ground_test.yaml` classification is ambiguous — RESOLVED 2026-04-24

Resolved by Phase 2 Track B via Path A (single-enum vocabulary expansion). Added `expected_to_change_at_stage_6_and_stage_7` to the legal-values list on `ScenarioResult` in `scripts/capture_option_c_baseline.py`, taught `_classify()` to apply the compound classification when the scenario name matches `mwir_ground_test`, and updated the `option_c_baseline.yaml` cell directly with a `classification_reason` justifying the dual-stage drift. Path B (`list[str]`) was rejected: today there are zero live consumers of the YAML's `classification` field (the shadow-mode reader CU-012 is unwired and reads from a different stage-output path), making the list-of-string promotion all churn for no gain. Regression gate green: 2360 src + 381 integration + mypy + ruff + 5/5 import contracts KEPT.

### CU-006 — `LineOfSightGeometry` field ordering diverges from plan text — RESOLVED 2026-04-24

Resolved by Phase 2 Track C. Added `kw_only=True` to the `@dataclass` decorator and re-ordered field declarations to match the plan's textual order `(h_tgt, h_atm_top=1e5, theta_o, theta_s=None, delta_phi=None)`. Positional construction now raises `TypeError` at construction time, closing the silent `h_atm_top ↔ theta_o` misassignment footgun before Stage 2's inferrer expands. All call sites already used keyword form; no test fixes required. Regression gate green: 2360 src + 381 integration, mypy/ruff/import-linter clean.

### CU-014 — Stage-4 `GroundBackground` assembly is thermal-only (deferred reflected terms) — RESOLVED 2026-04-24

Resolved by Stage 6 of Option C (commit `b9244fd`, "feat(option-c): Stage 6 — E_sky decomposition"). [src/radiant/atmosphere/assembly.py](../src/radiant/atmosphere/assembly.py) `_assemble_ground_background` (lines 1122–1158) now returns `(L_self + direct + diffuse) * tau_full_up + L_path_full`, where `L_self = epsilon_g * B(T_g)`, `direct = _direct_solar_term(rho_g, atm, cos_ts)` for the reflected-direct-solar term, and `diffuse = _diffuse_sky_term(rho_g, atm)` for the reflected-diffuse-sky term. Both branches that the original CU said were omitted are now present. Cell 28 and Cell 58 stayed bit-invariant because both anchors are `T1Thermal` with `ρ ≡ 0`, so the `(1−ε_g)` reflectance terms vanish identically — confirmed in [docs/Option_C_Implementation_Plan.md](Option_C_Implementation_Plan.md) Regression Invariants table. Verified during the 2026-04-24 stage-deferred audit.

### CU-015 — `readout.stage` lazy-imports `detector.noise.budget` — RESOLVED 2026-04-24

Investigation showed the fallback (lines 140–149) was unreachable: `RadiantSession` always runs `DetectorStage` before `ReadoutStage`, and every test that exercises `ReadoutStage` directly populates `noise_budget_raw` itself. Replaced the fallback with a `ValueError` that explicitly tells the caller to populate `stage_outputs['detector']['noise_budget_raw']` (CLAUDE.md Rule 17 — fail loudly, not silently). Removed the corresponding `radiant.readout.stage -> radiant.detector.noise.budget` ignore from `pyproject.toml`. All five import contracts now KEPT without exceptions for production cross-stage imports.
