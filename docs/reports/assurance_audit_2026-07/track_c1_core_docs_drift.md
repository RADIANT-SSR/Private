# Track C1 — Doc-vs-Code Drift: Conventions / Master / Signal_Chain / Testing_Validation

Status: Complete
Produced by: read-only audit agent, 2026-07-22, against src/, tests/, .github/workflows/ci.yml, pyproject.toml.
Dispositions: see findings.md and docs/plans/assurance_audit_remediation.md.

**Headline:** the three architecture docs are structurally sound — code-shaped claims (ChainState,
ReferenceFrame, provenance keys, regime constants, import contracts) almost all check out, many with
named enforcing tests. The concentrated rot is in **RADIANT_Testing_Validation.md §5–§9**, which
describes a golden/provenance/CI toolchain (freeze-golden CLI, `radiant reproduce`, config_hash,
Hypothesis suite, coverage gates, test matrix) that largely does not exist, plus a stage-attribution
error for turbulence MTF in the Signal Chain doc.

## Counts

| Doc | ENFORCED | TRUE-BUT-UNENFORCED | DRIFTED | UNVERIFIABLE |
|---|---|---|---|---|
| RADIANT_Conventions.md | 6 | 4 | 2 (D1, D2) | 3 |
| RADIANT_Master_Architecture.md | 12 | 4 | 4 (D3, D4, D5, archive link) | 0 |
| RADIANT_Signal_Chain_Architecture.md | 12 | 1 | 6 (D6, D7×2, D8, D9×2) | 0 |
| RADIANT_Testing_Validation.md | 6 | 1 | 16 (D10–D18 + §2.1 sigma_SB, §2.5 √FF) | 3 |

## Verified-ENFORCED highlights

Conventions: spectral monotonicity (`core/spectral.py:81`); wavenumber-derived-only
(`core/units.py:117,134`); MODTRAN cm⁻¹→µm flip + ×1e4 + Jacobian once in the reader
(`atmosphere/modtran.py:749-772`, `test_modtran_tape7_import.py`); CODATA constants once
(`core/constants.py`).
Master: C4 frozen ChainState (`core/chain.py:55-150`); C7 regime thresholds
(`core/regime.py:38-39`, `optics/stage.py:605-606`); C9 import-linter in CI; C12 no-bare-raises
test (`tests/test_exceptions.py:177`); C13 provenance record key-for-key
(`io/results.py:483-542`, `tests/test_provenance.py:321`); C15 CI level gating.
Signal Chain: Stage protocol; ChainState fields + all seven with_* methods; frame registry exact
(6 ReferenceFrame positions, no at_fpa, source/detector/readout register none); transfer factors
(`core/quantity.py:67-139`); mixed-origin RSS raises (`core/quantity.py:326-332`); ChainRunner
uniqueness/run_id/initial_stage_outputs; EE_box computed in PlatformStage, applied once.
Testing: markers/strict-markers; golden job main-only; all §2 named code objects exist (verified
individually); exception base + the six listed subclasses; golden committed.

## DRIFTED findings — detail

**D1 — Conventions §4: frame-rate machinery does not exist.** Doc claims frame period/rate stored
separately, default 1/t_int with logged warning. Zero hits for `frame_rate`/`frame_period`/`duty`
anywhere in src/. Entire contract unimplemented.

**D2 — Conventions §5: angular input-naming contract contradicted by geometry schema.** Doc:
angular params named with user-facing-unit suffix (`solar_zenith_deg`), large angles input in
degrees. Code: `geometry/_schema.py:77` `geometry.solar_zenith_rad`, `input_unit="rad"`; same
`path_zenith_rad`:60, `elevation_angle_rad`:422. Small angles do follow the doc
(`platform.jitter_rms_urad`); some optics params take deg. The universal claim is false.

**D3 — Master C12: "every stage package carries a stage-scoped <Stage>ValidationError in its
errors.py".** `geometry/errors.py` has exactly one class, `GeometrySpecificationError(RadiantError)`
— no GeometryValidationError, no ValueError co-inherit. Universal quantifier false for one of ten
stage packages; C12's enumerated list silently omits geometry.

**D4 — Master C11: "Validation collects all errors before reporting … all execution modes: CLI,
scripting API, GUI".** Only the CLI has a collect-all path (`cli/validate.py:32`, and its resolve
step at :70 collapses to first exception). No `Sensor.validate()` exists; `io/config.py:208-222`
raises on first problem; `params.set()` raises immediately.

**D5 — Master §7.6: cli import row.** Doc: `cli/ → radiant.api, radiant.io`. Code:
`cli/gui.py:54` imports `radiant.gui` (lazy, by design; CLAUDE.md documents it; import-linter
permits it). Table also lacks rows for `data/` and `gui/`.

**D6 — Signal Chain §1/§2/§8: turbulence MTF attributed to the wrong stage.** Doc (three places):
AtmosphereStage adds turbulence MTF (ground-based only). Code: `atmosphere/stage.py` has zero
`with_mtf` calls — publishes only `r0_m` (:294). The term is written by **PerformanceStage**
(`performance/stage.py:203-204`), gated on `r0_m > 0`, not a ground-based check.

**D7 — Signal Chain §1/§2: Platform/Readout spatial-term ownership.** §1 claims PlatformStage adds
LOS drift, platform vibration, TDI alignment MTF — none exist in platform/ (only
`mtf_jitter_x/y`, `mtf_smear_x/y`, `platform/stage.py:231-242`). TDI MTF is written by ReadoutStage
(`readout/stage.py:380-381`) which also writes `mtf_electronics_x/y` (:388-389) — §2's empty
ReadoutStage spatial cell is wrong too.

**D8 — Signal Chain §5: `result.signal_at("electrons")` examples would raise.**
`io/results.py:323` does strict `ReferenceFrame(frame)`; valid values are
at_target/at_aperture/post_optics/photoelectrons/post_readout/dn. Executed:
`ReferenceFrame('electrons')` → ValueError. The doc's own frame table three paragraphs earlier is
correct.

**D9 — Signal Chain §8 worked example: phantom frames.** Step 1 "SourceStage … adds `at_target`
frame" (source registers none; no frame named at_target exists); step 5 "adds `at_fpa`" (no such
frame — §5 of the same document states both facts correctly).

**D10 — Testing §3.2 + §9.3: the described CI does not exist.** Only workflow is ci.yml — single
Python 3.11, ubuntu only, no `--cov` flag anywhere. Coverage thresholds (95/85/80/75 table)
enforced by nothing. The described `tests.yml` 3.11+3.12 × ubuntu+macos matrix with
`--cov-fail-under=85` is fictional.

**D11 — Testing §4.2 + §7.1: provenance record shape contradicts the canonical C13 record.**
Doc example keys (git_tag, dependencies, resolved_at, config_hash, parameters, active_models as
model-id dict) vs real record (run_id, radiant_version, git_commit, python_version,
dependency_versions, parameter_set, input_file_hashes list, active_models stage-name list;
`io/results.py:534-542`). `tests/test_provenance.py:321` asserts the key set exactly — the doc
shape is test-prohibited. Master C13 documents the real record correctly.

**D12 — Testing §5.1: golden file structure fictional.** Real golden
`tests/integration/golden/mwir_leo_minimal.json` has signal_e/noise_*/snr/_provenance{config,
wavelength_grid, chain_stages, generated_by, notes, last_updated}; none of the doc's
golden_version/config_hash/frozen_at/metrics/noise_budget/signal fields exist.

**D13 — Testing §5.2/§5.3: golden update toolchain does not exist.** No `radiant freeze-golden` /
`freeze-all-golden` / `compare-golden` commands (`cli/main.py:37-46`); no `radiant_golden` fixture
or `assert_within_tolerance` anywhere. Actual mechanism: `scripts/update_golden.py
--i-know-what-im-doing` with module-local fixtures.

**D14 — Testing §7.2/§7.3/§7.4: run-id console logging, config hash, and `radiant reproduce` all
unimplemented.** Zero grep hits for the log line, `config_hash`, or a reproduce command.

**D15 — Testing §8.4: `sensor.validate(verbose=True)` does not exist.** No `Sensor.validate`; no
`ConfigValidationError` (real class `ConfigError`, `io/config.py:58`).

**D16 — Testing §8.5: "Current hierarchy (matches code)" omits ~two-thirds of the hierarchy**
(Core/stage ValidationError-StateError families, GeometrySpecificationError, ParameterEnumError,
UnknownParameterError, OperationCancelledError, BatchRunnerError, GUI errors).

**D17 — Testing §9.1: fixture tree fictional.** No `tests/conftest.py`, no `tests/fixtures/*`
files listed, no `tests/golden/`; real path `tests/integration/golden/`.

**D18 — Testing §9.2: Hypothesis declared but never used.** `hypothesis>=6.90` is a dev
dependency; zero imports repo-wide; the named property tests do not exist.

Minor: §2.1 snippet imports `sigma_SB` (real name `sigma_sb`/`SIGMA_SB` — ImportError as
written); §2.5 pixel-MTF snippet omits the √fill-factor term the code applies
(`detector/stage.py:158-160`).

## Top TRUE-BUT-UNENFORCED risks (ranked)

1. **C2/Conventions §7 — "no unit conversion in physics modules"**: true today, nothing in CI
   catches a new `π/180` or `1e4` in a physics module. Cheap ruff/grep CI check.
2. **C3/C6 stage purity** (no file I/O, no global state) — rides on convention only.
3. **Explicit pytest.approx tolerances** — no lint; default-tolerance approx merges silently.
4. **C1 no hardcoded constants** — no scanner.
5. **Coverage thresholds** — nothing measures them at all today.
