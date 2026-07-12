# RADIANT Master Architecture

**Date:** 2026-04-07
**Status:** Authoritative — this document supersedes any conflicting statement in any other RADIANT document.
**Read this first.** All other documents are reference material consulted as needed.

---

## 1. What Is RADIANT

RADIANT is a first-principles electro-optical sensor performance modeling framework. Given a sensor specification (aperture, detector, optics), an observation geometry (altitude, range, look angle), an atmospheric model (MODTRAN or analytic), and a target/background description, RADIANT predicts radiometric performance metrics — SNR, NEDT, NIIRS, detection range, and system MTF — by propagating spectral radiance through a physically correct signal chain from source to digitized output, accumulating all noise terms and MTF contributors at the stages where they originate. Every result carries a complete provenance record.

---

## 2. Document Map

Read documents in this order. Stop when you have what you need for your task.

| Document | When to read | Core content |
|----------|-------------|--------------|
| **This document** | First, always | Architecture overview, constraints, implementation rules |
| [RADIANT_Scope_Decisions.md](RADIANT_Scope_Decisions.md) | Before adding any new physics | What is in v1, what is stubbed, what is deferred |
| [RADIANT_Conventions.md](RADIANT_Conventions.md) | Before writing any code | Units, coordinate system, spectral variable, physical constants |
| [RADIANT_Parameter_System.md](RADIANT_Parameter_System.md) | Before adding parameters | How parameters are defined, resolved, validated, and tracked |
| [RADIANT_Signal_Chain_Architecture.md](RADIANT_Signal_Chain_Architecture.md) | Before implementing any stage | Stage protocol, ChainState, reference frames, regime dispatch |
| [RADIANT_Reference_Frames.md](RADIANT_Reference_Frames.md) | Working on `signal_at`/`noise_at` or frame conversion | `ReferenceFrame` enum, `ChainQuantity`, transfer-factor chain, backward propagation, saturated-well fallback |
| [RADIANT_Spectral_Integration.md](RADIANT_Spectral_Integration.md) | Implementing Stage 5 | Spectral→scalar collapse, regime signal assembly, EE_box coupling, fill factor, background pedestal |
| [RADIANT_Geometry.md](RADIANT_Geometry.md) | Working on GeometryStage, scene setup, or input modes | Stage-0 contract: geometry.* parameters, input modes (V/S families), published outputs, mode-resolution rules |
| [RADIANT_Geometry_Orbital.md](RADIANT_Geometry_Orbital.md) | Working on geometry, GSD, orbit, or revisit | Slant range, incidence, GSD, orbital velocity, J2 sun-sync, revisit, solar geometry |
| [RADIANT_Physics_Inventory.md](RADIANT_Physics_Inventory.md) | Reference for physics scope | Complete inventory of physical effects by signal chain stage |
| [RADIANT_Source_Target_System.md](RADIANT_Source_Target_System.md) | Implementing source/target | Source radiance models, BRDF, regime classification |
| [RADIANT_Atmosphere.md](RADIANT_Atmosphere.md) | Implementing atmosphere | MODTRAN interface, simple model, turbulence |
| [RADIANT_Optics.md](RADIANT_Optics.md) | Implementing optics | PSF, MTF terms, throughput, warm optics, EE_box |
| [RADIANT_Spatial_Complete.md](RADIANT_Spatial_Complete.md) | Implementing spatial effects | Smear, jitter, sampling, diffraction, pixel MTF |
| [RADIANT_Detector_Complete.md](RADIANT_Detector_Complete.md) | Implementing detector/readout | All noise terms, QE models, dark current, IPC, ADC |
| [RADIANT_Metrics.md](RADIANT_Metrics.md) | Implementing performance stage | SNR, NEDT, NIIRS (GIQE5/IIRS), detection range, RER |
| [RADIANT_Scan_Timing.md](RADIANT_Scan_Timing.md) | Implementing TDI/scan | TDI alignment, frame timing, duty cycle |
| [RADIANT_Config_Format.md](RADIANT_Config_Format.md) | Implementing I/O | YAML format, inheritance, validation, example configs |
| [RADIANT_Scripting_API.md](RADIANT_Scripting_API.md) | Implementing the user API | `Sensor` class, sweep, Monte Carlo, plotting |
| [RADIANT_GUI_Architecture.md](RADIANT_GUI_Architecture.md) | Phase 2 GUI work only | PySide6 layout, GUI-backend interface |
| [RADIANT_Testing_Validation.md](RADIANT_Testing_Validation.md) | Before writing any test | Test hierarchy, 10 reference cases, provenance tracking |
| [RADIANT_Plugins.md](RADIANT_Plugins.md) | Writing a plugin or extension | Plugin ABCs, entry points, spectral libraries, templates |
| [RADIANT_File_Tree.md](RADIANT_File_Tree.md) | Locating code | Package structure, import rules, public/private API |
| [RADIANT_Personas.md](RADIANT_Personas.md) | Design decisions | User personas, priority matrix, design implications |
| [RADIANT_Metric_Dependencies.md](RADIANT_Metric_Dependencies.md) | Dependency analysis | Metric ↔ parameter dependency graph |

**Document conflicts:** If any document conflicts with this one, this document wins. If two non-master documents conflict, open an issue. Do not resolve document conflicts by choosing the one you prefer.

---

## 3. Key Architectural Decisions

These are non-negotiable constraints. No implementation detail, user request, or shortcut justifies violating them.

### C1 — Physics Before Code
Every physics quantity, formula, and model must be traceable to a specific literature reference or first-principles derivation. Magic numbers (hardcoded values without citation) are bugs. Physical constants are defined once in `radiant.core.constants` using CODATA 2018 values and imported everywhere else.

### C2 — One Unit System, One Conversion Point
Internal canonical units are defined in RADIANT_Conventions.md and are absolute. Spectral radiance: W/m²/sr/µm. Angles: radians. Time: seconds. Length: meters. Conversion happens at a single point: on ingestion from user input (`params.set()`) or from external files (MODTRAN reader). No conversion happens in physics modules. Violation: if any physics module contains a multiplication by 1e4, `math.pi/180`, or `1e-6` that is a unit conversion rather than physics, that is a bug.

### C3 — Stages Are Pure Functions
Every signal chain `Stage` is a pure function of `(ChainState, ParameterSet) → ChainState`. Stages do not: mutate their inputs, read from files, write to files, access global state, call other stages, or produce side effects. Any I/O (MODTRAN file loading, QE curve loading) happens before chain execution, in the `SpectralDataStore`, accessed via `ParameterSet`.

### C4 — ChainState Is Immutable and Accumulating
`ChainState` is a frozen dataclass. Stages add fields via `state.with_frame(...)`, `state.with_noise(...)`, `state.with_mtf(...)`. They never remove or overwrite fields. After the chain runs, the state contains a complete history of every intermediate quantity. This history is the audit record.

### C5 — Spectral Integration Happens Exactly Once
Before `SpectralIntegrationStage`: all quantities are spectral arrays (W/m²/sr/µm, dimension = N_wavelengths). After `SpectralIntegrationStage`: all quantities are per-pixel scalars (e⁻, DN). No physics module upstream of `SpectralIntegrationStage` may produce a scalar radiometric quantity. No physics module downstream may produce a spectral array.

### C6 — EE_box Applied Exactly Once
The encircled energy fraction (fraction of PSF energy landing in the pixel footprint) is applied exactly once, in `SpectralIntegrationStage`, only for point-source and sub-pixel target regimes. It does not appear in any other stage, in any other regime, or in the background term of the sub-pixel equation.

### C7 — Regime Finalized in OpticsStage
Target regime classification (extended / point / sub-pixel) is tentatively set in `SourceStage` and finalized in `OpticsStage` after the diffraction PSF diameter is computed. All downstream stages read from `state.stage_outputs["optics"]["regime"]`. No stage may re-classify the regime.

### C8 — Noise in Electrons at Origin Frame
Every noise term carries a value in electrons RMS and an origin frame (the reference frame where the noise was generated). Conversion to other reference frames (DN, aperture-referred noise) happens at query time via the stored forward factors. No noise term is stored in any other unit or converted at generation time.

### C9 — No Cross-Stage Imports in Physics Modules
Physics subpackages (`geometry`, `source`, `atmosphere`, `optics`, `platform`, `spectral_integration`, `detector`, `readout`, `performance`) import only from `radiant.core`. They never import from each other. All inter-stage communication flows through `ChainState`. Enforcement: `import-linter` in CI.

### C10 — Every Parameter Has a ParameterDef
Every user-facing parameter is defined once in a `_schema.py` file within its owning physics subpackage. The definition specifies: name (dot-path), dtype, canonical unit, input unit, default, bounds, enum values, consistency group, and tags. Parameters without a `ParameterDef` cannot exist in a valid RADIANT config.

### C11 — Validate Before Compute
The full validation pipeline (type → bounds → enum → required → consistency → file) runs and completes before any physics computation begins. A config with validation errors never reaches the chain runner. Validation collects all errors before reporting (not fail-fast). This applies in all execution modes: CLI, scripting API, GUI.

### C12 — Every Error Is Actionable
Every exception raised by RADIANT inherits from `RadiantError` (base class in `radiant.core.exceptions`, re-exported as `radiant.RadiantError`). Concrete subclasses (`ParameterBoundsError`, `KirchhoffViolationError`, `ModtranUnavailableError`, `Tape7ParseError`, `ConfigError`, `ElementConfigError`) live with the module that raises them; in addition, every stage package carries a stage-scoped `<Stage>ValidationError(RadiantError, ValueError)` (plus a `...StateError(RadiantError, RuntimeError)` where invalid-chain-state raises exist) in its `errors.py`, used by all generic input/argument guards (CU-043 migration — the ValueError co-inheritance is the sanctioned Rule 15 back-compat carve-out, so historical `except ValueError` call sites keep working). The user-facing actionability contract — what went wrong (specific, not generic), why it is wrong (physics or logic reason), what the user should do (specific fix) — is carried as a structured `what / why / action / context` payload on every raise site. `ParameterBoundsError` formalizes that payload as constructor fields; other subclasses include the same information in their message strings until the carve-out is generalized. Exceptions that say only "invalid parameter" are bugs.

### C13 — Provenance Is Mandatory
Every `ChainResult` carries a complete provenance record: run ID, RADIANT version, git commit, Python version, dependency versions, resolved parameter set with per-parameter provenance, input file hashes, and active model identifiers. Provenance is not optional and cannot be disabled. Given a provenance record, the result must be reproducible.

The canonical accessor is `ChainResult.to_provenance_record() -> dict[str, Any]`, which returns a JSON-serialisable dict with exactly these keys:

| Key | Type | Source |
|-----|------|--------|
| `run_id` | `str \| None` | UUID4 minted by `ChainRunner.run` (or caller-supplied), carried on `ChainState.run_id`; `None` only for synthetic states constructed outside a runner |
| `radiant_version` | `str` | `radiant.__version__` |
| `git_commit` | `str` | short SHA of working-tree HEAD; `"unknown"` outside a git repo |
| `python_version` | `str` | `MAJOR.MINOR.PATCH` of the running interpreter |
| `dependency_versions` | `dict[str, str]` | `{name: version}` for the declared runtime deps (numpy, scipy, pyyaml, click); missing packages map to `"unknown"` |
| `parameter_set` | `dict[str, dict]` | `{dotpath: ResolvedValue.to_dict()}` for every resolved parameter — values, units, and per-parameter provenance |
| `input_file_hashes` | `list[dict]` | ordered list of `{"path": str, "sha256": str}` for every config file consumed via `radiant.io.config.load_config` |
| `active_models` | `list[str]` | ordered stage names that ran; mirrors `ChainResult.history` |

The pure helpers that assemble the record (`new_run_id`, `git_commit`, `python_version_string`, `dependency_versions`, `hash_file`) live in `radiant.core.provenance` so they are import-safe from anywhere in the codebase. Loaders populate the file-hash list by calling `ParameterSet.record_loaded_file(path, sha256)`. Provenance helpers never raise on environmental edge cases (no git, missing dep) — they degrade to `"unknown"` rather than blocking a chain run.

### C14 — The Scripting API Is the Stable Surface
The public API (`radiant.Sensor`, `radiant.RadiantError` — the top-level `__all__` in `src/radiant/__init__.py`) is the only surface with stability guarantees. `ChainResult` is importable from `radiant.io.results` but is not re-exported at the top level; `SensorConfig` and `ScenarioConfig` were dropped (see `docs/adr/ADR-C`). `BatchRunner` was dropped from the top-level surface by ADR-C but a `BatchRunner` class was subsequently re-added under `radiant.api.batch` (commit `6492028`, scenario 4.1 prerequisite — ADR-C anticipated this "if batch features grow, file a Category B task" trigger); it is a semi-public `api.batch` class, NOT re-exported at the top level. (Note: ADR-C's literal "no BatchRunner exists anywhere" statement predates that re-addition and needs an amendment.) Internal modules (`radiant.core.*`, individual stage implementations) are semi-public at best. Breaking changes to the public API require a major version bump and a deprecation cycle.

### C15 — Test at Level 0 Before Level 2
Physics correctness tests (Level 0) must pass before integration tests (Level 2) are trusted. A Level 2 test that passes while a Level 0 test fails is meaningless — the right answer for the wrong reason. CI enforces: Level 0 failure blocks Level 1; Level 1 failure blocks Level 2.

---

## 4. Scope Summary

Full detail in RADIANT_Scope_Decisions.md. Summary:

### In v1 (fully implemented)

| Category | What is included |
|----------|-----------------|
| Source | Planck thermal emission, Lambertian reflected solar, non-uniform temperature (hot-spot), gray body emissivity |
| Atmosphere | MODTRAN tape7 interface (τ, L_path, L_atm), simple Beer-Lambert model, 6 standard atmospheres |
| Optics | Optical MTF from pupil autocorrelation (circular aperture ± obscuration, WFE, defocus — Rule 4), PSF-derived Strehl (+ `strehl_marechal` diagnostic), throughput, warm optics emission, cold stop, filter bandpass, EE_box |
| Platform/Spatial | Smear MTF (sinc), jitter MTF (Gaussian), pixel aperture MTF (sinc), IPC MTF, charge-diffusion MTF |
| Detector | 12+ noise terms (shot, dark-current shot, read, 1/f, kTC, DSNU, PRNU, NUC residual, glow, IPC, quantization, persistence), Rule 07 dark current, HgCdTe/InSb/InGaAs/Si QE models |
| Readout | TDI signal/noise scaling, binning, coadds, CDS, Fowler-N, gain, 14/16-bit ADC, quantization |
| Performance | SNR, NEDT, GIQE5 (EO-NIIRS), IIRS (IR NIIRS), detection range, MTF budget, RER |
| Regimes | Extended scene, point source, sub-pixel target (auto-detect with user override) |

### Stubbed in v1 (returns placeholder, no error)

- Narcissus effect (LWIR self-emission of cold detector in warm optics)
- MODTRAN polarization
- Spectral radiometric nonlinearity
- Blooming / anti-blooming

(Zernike WFE is **not** stubbed: it is fully modeled via the complex-pupil
autocorrelation — `WfeMode.ZERNIKE`, injected as a `WavefrontError`. The
Maréchal approximation survives only as the separate `strehl_marechal`
diagnostic, not as a replacement for the Zernike OTF.)

### Deferred to v2 or later

- BRDF models beyond Lambertian
- Scene simulation (2D image generation)
- Hyperspectral (simultaneous multi-band)
- Real-time / stochastic signal generation
- GUI implementation (architecture designed in v1)
- MATLAB bridge

---

## 5. Document Supersession Table

When two documents address the same topic, this table shows which is authoritative.

| Topic | Authoritative document | Superseded document |
|-------|----------------------|-------------------|
| All architectural constraints | This document | Any other document |
| Unit conventions (internal) | RADIANT_Conventions.md | Any inline comment or code |
| Parameter naming, dot-paths | RADIANT_Parameter_System.md | RADIANT_Conventions.md (for parameters) |
| Signal chain stage protocol | RADIANT_Signal_Chain_Architecture.md | Stage-specific documents for chain structure |
| Noise terms list | RADIANT_Detector_Complete.md | RADIANT_Physics_Inventory.md (for noise detail) |
| MTF contributor list | RADIANT_Spatial_Complete.md | RADIANT_Physics_Inventory.md (for MTF detail) |
| YAML config format | RADIANT_Config_Format.md | RADIANT_Parameter_System.md §Configuration |
| Public API names | RADIANT_Scripting_API.md | RADIANT_File_Tree.md (for `api/` module structure) |
| Test tolerances | RADIANT_Testing_Validation.md | Any code-level comment claiming a tolerance |
| Plugin ABCs | RADIANT_Plugins.md | RADIANT_File_Tree.md (for `plugins/` structure) |

---

## 6. Implementation Order

Modules can only be implemented after their dependencies are stable. This order is dependency-correct; see [archive/RADIANT_Phase1_Plan.md](archive/RADIANT_Phase1_Plan.md) for the historical Phase 1 implementation plan.

```
Phase 1a — Core Infrastructure (no dependencies)
  radiant.core.constants
  radiant.core.units
  radiant.core.parameters
  radiant.core.spectral
  radiant.core.chain
  radiant.core.radiometry
  radiant.core.geometry
  radiant.core.regime

Phase 1b — Source + Atmosphere (depends: core)
  radiant.source.*       ←── can develop in parallel with:
  radiant.atmosphere.*

Phase 1c — Optics + Platform + Spectral Integration (depends: core)
  radiant.optics.*       ←── can develop in parallel with 1b
  radiant.platform.*
  radiant.spectral_integration.*

Phase 1d — Detector + Readout + Performance (depends: 1b + 1c complete)
  radiant.detector.*
  radiant.readout.*
  radiant.performance.*

Phase 1e — I/O + API + CLI (depends: 1d complete)
  radiant.io.*
  radiant.api.*
  radiant.cli.*
  Integration tests
```

Within each phase, modules can be implemented in parallel by different developers or agents. The constraint is between phases, not within them.

---

## 7. Rules for Implementers

### 7.1 Writing a New Stage

1. Read RADIANT_Signal_Chain_Architecture.md §2 (module interfaces) before starting.
2. Create `radiant/<stage>/stage.py` with a class inheriting the `Stage` protocol.
3. Create `radiant/<stage>/_schema.py` with all `ParameterDef` objects for this stage.
4. The stage's `run()` method must:
   - Accept `(state: ChainState, params: ParameterSet) → ChainState`
   - Not mutate `state` or `params`
   - Add at least one entry to `state.stage_outputs[self.name]`
   - Add a `RadiometricFrame` if the stage transforms radiometric quantities
   - Add `NoiseTerm` objects for any noise it generates
   - Add MTF arrays to `state.mtf_terms` for any spatial effect it models
5. Write Level 0 tests for every equation in the stage before writing the stage itself.
6. Write Level 1 tests for the stage before submitting the PR.

### 7.2 Adding a Parameter

1. Add a `ParameterDef` to the appropriate `_schema.py`.
2. Give it a dot-path name following the naming rules in RADIANT_Parameter_System.md §naming.
3. Specify canonical and input units. Do not omit units for dimensionless quantities — use `""`.
4. Specify `default=None` for required parameters; provide a justified default for optional ones.
5. Add `default_justification` to the `ParameterDef` if the default is non-obvious.
6. If the parameter participates in a consistency group, add it to the `ConsistencyGroup` definitions in `radiant/api/_param_registry.py` — groups are assembled there and passed to `ParameterSet(schema, groups)`.
7. Add the parameter to RADIANT_Parameter_System.md §parameter naming convention table.

### 7.3 Writing Tests

1. Write Level 0 tests first. No physics module is complete without Level 0 coverage of its key equations.
2. Every test that calls a physics function must use known-good analytic results as expected values — not results computed by other RADIANT code.
3. Use `pytest.approx` with explicit `rel=` or `abs=` tolerances from RADIANT_Testing_Validation.md §6. Never use default `pytest.approx` tolerance (1e-6 relative) for physics tests — set it explicitly.
4. Module-level tests (Level 1) must construct their own minimal `ParameterSet` — they do not load YAML files.
5. Tests must not call `time.sleep()`, `os.system()`, or any external process.
6. Every test function has a one-sentence docstring describing what physics property it verifies.

### 7.4 Error Handling

1. Use `RadiantError` subclasses (`RadiantError` lives in `radiant.core.exceptions`, re-exported at the top level as `radiant.RadiantError`). Concrete subclasses live with the module that raises them — `ParameterBoundsError` in `core/parameters.py`, `KirchhoffViolationError` in `optics/element.py`, `ModtranUnavailableError` and `Tape7ParseError` in `atmosphere/modtran.py`, `ConfigError` in `io/config.py`, `ElementConfigError` in `io/element_config.py`; generic per-stage guards use the stage's `errors.py` classes (`CoreValidationError`/`CoreStateError` in `core/exceptions.py`, `SourceValidationError`, `AtmosphereValidationError`/`AtmosphereStateError`, `OpticsValidationError`, `PlatformValidationError`, `SpectralIntegrationValidationError`/`SpectralIntegrationStateError`, `DetectorValidationError`, `ReadoutValidationError`, `PerformanceValidationError`, `ApiValidationError`). Never raise bare `ValueError`, `TypeError`, or `AssertionError` for user-facing errors — `tests/test_exceptions.py::TestNoBareBuiltinRaises` enforces this repo-wide.
2. Every `raise` must supply `what`, `why`, and `action` — either as `ParameterBoundsError` constructor fields or in the message string, until the carve-out is generalized.
3. `assert` is for developer invariants only (not user-input validation). A user who triggers an `AssertionError` has found a bug in RADIANT, not made a user error.
4. Catch exceptions at layer boundaries (e.g., `io/` catching file-not-found), re-raise as `RadiantError` with context.
5. Do not catch `RadiantError` inside physics modules. Let it propagate to the API layer.
6. Concrete subclasses MAY co-inherit from a built-in exception type (`ValueError`, `RuntimeError`) for back-compat with existing `except`/`pytest.raises` patterns; new RADIANT exception classes SHOULD inherit from `RadiantError` only.

### 7.5 Code Style

1. Follow PEP 8. Line length 100. Use `ruff` for formatting and linting.
2. Type annotations are required on all public functions and methods. `mypy --strict` must pass on `radiant.core` and `radiant.api`.
3. Docstrings on all public functions: one-line summary, then parameters and returns if non-obvious.
4. No magic numbers. Named constants or `ParameterDef` defaults. If a number is a physical quantity, it belongs in `constants.py`.
5. No `TODO` or `FIXME` in committed code without a linked GitHub issue number.
6. Import ordering: stdlib → third-party → `radiant.core` → never cross-stage.

### 7.6 Import Rules (Enforced by `import-linter`)

```
core/         → stdlib, numpy, scipy only
source/       → radiant.core only
atmosphere/   → radiant.core only
optics/       → radiant.core only
platform/     → radiant.core only
spectral_integration/ → radiant.core only
detector/     → radiant.core only
readout/      → radiant.core only
performance/  → radiant.core only
io/           → radiant.core, any physics subpackage (read-only)
api/          → radiant.core, all physics, radiant.io
cli/          → radiant.api, radiant.io
```

(The `plugins/` package was removed 2026-07-06 — it was an empty stub. The
extension-point design lives in `RADIANT_Plugins.md` under a DEFERRED banner;
its `plugins/ → radiant.core only` import rule returns with the package.)

Cross-stage imports at the physics level (e.g., `from radiant.optics import psf` inside `radiant.detector`) are never permitted. Shared physics must be promoted to `radiant.core`.
