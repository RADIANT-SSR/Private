# RADIANT Cleanup Backlog

**Purpose**: track technical-debt and follow-up tasks discovered while executing feature work, so they don't get lost and don't contaminate the feature PR scope.

**Usage**: any stage/task that uncovers a latent issue orthogonal to its scope appends an entry here. Entries carry enough context (file paths, commands, symptoms) to be picked up cold. Closed entries move to the "Resolved" section at the bottom with the PR or commit that fixed them.

**Not for**: items inside the current feature's scope (those go in the feature plan), scenario-specific gaps (those go in the scenario's `gaps.md`), or operational/runtime gaps already tracked in `docs/gaps.md`.

---

## Open


### CU-003 — Pre-existing MTF tolerance warning on `swir_aerial_gas.yaml`

**Discovered**: Option C Stage 0 (2026-04-19)
**File**: `examples/swir_aerial_gas.yaml` (if that is the exact path — discovered via `scripts/capture_option_c_baseline.py`)
**Symptom**: MTF consistency check reports `max_err_x = 0.052` vs tolerance `0.050` (a narrow miss of ~4%).
**Why it matters**: Rule 4 requires PSF-path ↔ MTF-product-path consistency to ~1e-6; this scenario is ~10⁴ looser. Flagged now so Stage 3 reviewers don't mistake it for a new regression.
**Suggested fix**: investigate which degradation is split inconsistently across the two paths for this scenario; likely either a jitter kernel, smear term, or diffraction normalization drift. Low priority unless the scenario is promoted to a regression anchor.

### CU-004 — `mwir_ground_test.yaml` classification is ambiguous

**Discovered**: Option C Stage 0 (2026-04-19)
**File**: `tests/integration/snapshots/option_c_baseline.yaml` (scenario entry `mwir_ground_test`)
**Symptom**: classified as `expected_to_change_at_stage_6` by the wavelength-band heuristic, but it is likely also a Stage-7 `no_atmosphere (ground_test)` sub-case cell. Both stages will shift its values.
**Why it matters**: when Stage 3 shadow-mode fires, this cell may drift for two reasons at once; without a clean classification we can't tell whether Stage-3 drift alone is legitimate.
**Suggested fix**: before Stage 3 kicks off, manually review the scenario and set `classification: expected_to_change_at_stage_6_and_stage_7` (or split-categorize). Consider whether the YAML snapshot schema should allow a list of classifications rather than a single enum.

### CU-005 — `theta_o_from_eta` boundary converter is unwired

**Discovered**: Option C Stage 1 (2026-04-19)
**File**: `src/radiant/core/los_geometry.py`
**Symptom**: function is implemented and unit-tested but no stage calls it. A module-level comment flags it as deferred for Stage 7 / SensorDescriptor ADR.
**Why it matters**: dead-until-wired code risks bit-rot. If it's still unwired after Stage 8, reconsider whether it belongs in `core/` or in a stubbed `sensor/` module.
**Suggested fix**: revisit at Stage 7; either wire it into the Earth-LOS-intercept check (which needs `h_sensor`) or explicitly defer to the SensorDescriptor ADR with a link from the module comment.

### CU-006 — `LineOfSightGeometry` field ordering diverges from plan text

**Discovered**: Option C Stage 1 (2026-04-19)
**File**: `src/radiant/core/los_geometry.py`
**Symptom**: Python forbids non-default fields after default fields, so the implementation is `(h_tgt, theta_o, h_atm_top=1e5, theta_s=None, delta_phi=None)` rather than the plan's textual order `(h_tgt, h_atm_top=1e5, theta_o, theta_s, delta_phi)`.
**Why it matters**: positional construction would silently misassign `h_atm_top` ↔ `theta_o`.
**Suggested fix**: enforce keyword-only construction via `@dataclass(frozen=True, kw_only=True)` (Python 3.10+). Non-blocking since current call sites are test-only, but will bite once Stage 2's inferrer starts constructing descriptors from YAML.

### CU-007 — Stage-2 MWIR-mixed `UserWarning` is globally suppressed inside `_inferrer.py`

**Discovered**: Option C Stage 2 (2026-04-19)
**File**: `src/radiant/source/_inferrer.py::_build_target_descriptor`
**Symptom**: `T1Thermal.__post_init__` emits a `UserWarning` for MWIR cells that might be better modelled as T3Mixed. Stage 2 cannot distinguish MWIR-with-negligible-ρ (hot target, T1 correct) from MWIR-mixed (T3 correct) from the scalar ε+T legacy surface, so every MWIR snapshot scenario fires the warning. The inferrer currently wraps the `T1Thermal(...)` construction in `warnings.catch_warnings() / simplefilter("ignore", UserWarning)` to keep the snapshot logs clean.
**Why it matters**: the suppression is narrow (one constructor call), but it masks a legitimate modelling flag that Stage 3/6 MWIR-mixed work should re-expose once the spectral ρ(λ) surface lands.
**Suggested fix**: in Stage 3 (atmosphere) or Stage 6 (spectral_integration), once the mixed T3 branch is synthesised from atmosphere-aware metadata, remove the suppression here and let the warning fire for the remaining legacy cases (if any).

### CU-008 — Stage-2 `GroundBackground` placeholder is grey, not spectral

**Discovered**: Option C Stage 2 (2026-04-19)
**File**: `src/radiant/source/_inferrer.py::_build_background_descriptor`
**Symptom**: terrestrial / airborne sub-pixel or point-source cells build a `GroundBackground(epsilon_g=grey_array, T_g=scalar)` from `source.background.{emissivity,temperature}` and emit a `UserWarning` flagging the placeholder. The real spectral ε_g(λ) will come from the backgrounds subsystem in Stage 3.
**Why it matters**: spectral ε_g matters for radiometric fidelity when the bg surface has non-grey reflectance (vegetation / snow / urban). Stage 2 is deliberately permissive; Stage 3 must replace this.
**Suggested fix**: in Stage 3 of the Option C plan, route the background spectral emissivity through `SpectralDataStore` and remove the warning. Confirm the snapshot regression YAMLs under `src/radiant/source/tests/snapshots/` refresh cleanly.

### CU-009 — Stage-2 `LineOfSightGeometry` uses Kármán-line default instead of scenario-aware `h_atm_top`

**Discovered**: Option C Stage 2 (2026-04-19)
**File**: `src/radiant/source/_inferrer.py::_infer_los`
**Symptom**: every non-at-aperture scenario gets `LineOfSightGeometry(h_tgt=0.0, theta_o=0.0)` with `h_atm_top=1e5` (dataclass default). Observer geometry (solar zenith, azimuth, slant angle, airborne h_tgt) is not yet exposed on the SourceStage parameter surface.
**Why it matters**: path-radiance models in Stage 3 will want a real LOS. For now every scenario fires as nadir/surface/Kármán.
**Suggested fix**: Stage 5 of the Option C plan adds the partial-column atmosphere and introduces `source.observer_geometry.*` parameters. Wire those through `_infer_los` at that time.


### CU-011 — MODTRAN backend's `evaluate()` aliases two-leg τ (single-τ adapter)

**Discovered**: Option C Stage 3 (2026-04-19)
**File**: `src/radiant/atmosphere/modtran.py`
**Symptom**: the Stage 3 `evaluate()` adapter populates `tau_sun = tau_up = tau_full_up` from the legacy single-τ MODTRAN output and emits a one-time `UserWarning` flagging the degradation. Real two-leg fidelity requires either a second TAPE7 run at `θ_s` or an analytic split.
**Why it matters**: VIS/NIR reflective scenarios that use the MODTRAN backend will behave as if `τ_sun = τ_up`, losing the solar-zenith dependence that Stage 3's new two-leg model is designed to capture.
**Suggested fix**: in Stage 6 (spectral_integration), when `E_sky_scattered` is decomposed, also split `τ_sun` via a second MODTRAN call keyed on `(los.h_tgt, θ_s)`. Add the new key to the MODTRAN cache signature.

### CU-012 — Shadow-mode classification injection not wired

**Discovered**: Option C Stage 3 (2026-04-19)
**File**: `src/radiant/atmosphere/stage.py` (reads `state.stage_outputs["meta"]["option_c_classification"]`) and the integration harness.
**Symptom**: `AtmosphereStage` reads the per-scenario classification from a stage-output field that nothing currently populates. Today's integration tests therefore skip the shadow-mode comparison (the code branch `if classification is None: return`). The anchor tests exercise the assembly path directly and still pass, so no CI signal is lost — but the "invariant" hard-assert for Cells 28/58 only fires when the meta field is explicitly set.
**Why it matters**: the plan's shadow-mode policy expects every scenario run in the Stage 0 baseline snapshot to receive a classification; unclassified cells should fail loudly. Right now the stage silently bypasses the compare.
**Suggested fix**: add a pytest fixture in `tests/integration/conftest.py` that loads `tests/integration/snapshots/option_c_baseline.yaml`, matches the running scenario's YAML path or id, and injects `meta.option_c_classification` into the chain state (via a pre-stage hook or parameter). Fail loudly on cells present in the baseline but absent from the fixture.

### CU-013 — Shadow-mode `rtol=1e-6` may be too tight for Stage 6 heterogeneous cells

**Discovered**: Option C Stage 3 (2026-04-19)
**File**: `src/radiant/atmosphere/stage.py` (`_SHADOW_RTOL = 1e-6`)
**Symptom**: Stage 3 passes bit-exact on invariant cells. Stage 6 will introduce small-but-real spectral physics changes in cells classified `expected_to_change_at_stage_6`. If any residual invariant-classified cell has a ~1e-7 relative drift from accumulated floating-point noise at that time, the current threshold will false-trip.
**Why it matters**: a false-trip would block Stage 6 land while being a non-bug. Too-loose a threshold could hide a real bug.
**Suggested fix**: during Stage 6, run the full suite at `rtol=1e-9` first to survey real drift magnitudes, then set `_SHADOW_RTOL` to the largest invariant-cell residual plus one decade of margin. Document the chosen value and the survey data in the Stage 6 report.

### CU-014 — Stage-4 `GroundBackground` assembly is thermal-only (deferred reflected terms)

**Discovered**: Option C Stage 4 (2026-04-19)
**File**: `src/radiant/atmosphere/assembly.py::_assemble_ground_background`
**Symptom**: the v1 ground-background arm is `ε_g·B(T_g)·τ_full_up + L_path_full` — pure self-emission plus path radiance. The reflected-diffuse (`(1−ε_g)·E_sky/π`) and reflected-direct-solar (`(1−ε_g)·τ_sun·E_TOA·cos(θ_s)/π`) terms that a full T3 Kirchhoff treatment would include are **omitted**. Stage 3 wired them in, but Stage 4 removed them to preserve the Cell 28 / Cell 58 invariants (which were pinned against the legacy single-τ formulation that did not model reflected sky/solar on the background).
**Why it matters**: for MWIR sub-pixel cells where the ground background is treated as the fill-fraction-weighted "rest of the pixel," omitting the reflected-sky term under-estimates the background radiance in cases with substantial diffuse downwelling. Point-source cells bypass this entirely (`background_e = 0` in `spectral_integration/stage.py`), so the impact is restricted to sub-pixel cells and extended-scene contrast computations with non-vacuum atmospheres.
**Suggested fix**: in Stage 6 (E_sky decomposition) — since that stage is an authorized re-baseline for MWIR anchors — restore the reflected-diffuse and reflected-direct-solar branches on the ground background. Re-run `test_ground_background_thermal_only_at_h0` and update it to the full T3 form. Document the Cell 28/58 re-baseline magnitudes that the restoration induces.

---

## Resolved

### CU-001 — Pre-existing `lint-imports` contract breakages — RESOLVED 2026-04-24

Resolved by Phase 6 of the technical-debt cleanup (commits 2a70558, 7ab1251, bea406a). `cli/convert.py` was the only direct production violation; routed through new `radiant.api.units` re-export. All transitive cli→api→{core,platform,optics,io} edges enumerated in `pyproject.toml` `ignore_imports`. Test-colocation patterns (`radiant.*.tests.*`) granted explicit ignores with `unmatched_ignore_imports_alerting = "warn"`. All 5 import-linter contracts now KEPT.

### CU-002 — Pre-existing `mypy --strict` errors in non-`core`/`api` modules — RESOLVED 2026-04-24

Resolved by Phases 2–5 of the technical-debt cleanup. `core/responsivity.py` no-any-return wrapped with `np.asarray` (commit), `api/sweep.py` no-redef collapsed (commit), `api/tolerance.py` union-attr asserted (commit 2de6b76), `api/plot.py` × 6 + `api/tests/test_plot.py` × 1 wrapped with `cast(Figure, ...)` at the matplotlib seam (commit f9fcf3c). `mypy --strict src/radiant/core src/radiant/api` is now clean (51 source files).

### CU-010 — `test_inferrer.py` imports from `radiant.api` — RESOLVED 2026-04-24

Resolved by Phase 6.2 (commit 7ab1251). `pyproject.toml` import-linter contracts now exempt `radiant.*.tests.*` patterns from the physics-stage and cross-stage rules, matching CLAUDE.md's intent (Rule 11 governs production code; tests legitimately need api/io to build full-schema fixtures).

### CU-015 — `readout.stage` lazy-imports `detector.noise.budget` — RESOLVED 2026-04-24

Investigation showed the fallback (lines 140–149) was unreachable: `RadiantSession` always runs `DetectorStage` before `ReadoutStage`, and every test that exercises `ReadoutStage` directly populates `noise_budget_raw` itself. Replaced the fallback with a `ValueError` that explicitly tells the caller to populate `stage_outputs['detector']['noise_budget_raw']` (CLAUDE.md Rule 17 — fail loudly, not silently). Removed the corresponding `radiant.readout.stage -> radiant.detector.noise.budget` ignore from `pyproject.toml`. All five import contracts now KEPT without exceptions for production cross-stage imports.
