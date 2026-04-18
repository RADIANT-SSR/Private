# RADIANT — Coding Agent Instructions

This is the authoritative reference for all RADIANT coding agents. Read it fully before making any change. When in conflict with another document, this file governs agent behavior; `docs/RADIANT_Master_Architecture.md` governs architecture decisions.

---

## What Is This Codebase

RADIANT is a first-principles EO sensor performance modeling framework. It predicts SNR, NEDT, NIIRS, MTF, and detection range for space-based and airborne electro-optical sensors. The signal chain flows: source → atmosphere → optics → platform → spectral integration → detector → readout → performance metrics.

**Primary reference documents** (read before touching related code):
- `docs/RADIANT_Master_Architecture.md` — non-negotiable constraints (15 rules)
- `docs/RADIANT_Conventions.md` — units, coordinate system, spectral variable
- `docs/RADIANT_Signal_Chain_Architecture.md` — stage protocol, ChainState
- `docs/RADIANT_Parameter_System.md` — parameter naming, types, resolution
- `docs/RADIANT_Testing_Validation.md` — what and how to test

---

## Non-Negotiable Rules

These rules are absolute. No exception without explicit approval from the project owner.

### 1. Python ≥ 3.11 — Type Hints Everywhere
Type hints are required on **every** function and method — not just public ones. `mypy --strict` must pass on `radiant.core` and `radiant.api`.

### 2. Units — Convert at Boundaries Only
- Internal canonical units: wavelength in **µm**, angles in **radians**, time in **seconds**, length in **meters**, radiance in **W/m²/sr/µm**, noise in **e- RMS**.
- Unit conversions happen exactly once: at `params.set()` (user input) or in file readers (MODTRAN: ×1e4 for W/cm² → W/m²).
- No unit conversion inside physics modules. A `* math.pi / 180` or `* 1e4` in a physics module is a red flag — verify it is computing physics, not converting units.

### 3. Coordinate System
Right-handed. +Z toward target (along boresight). +X cross-track. +Y along-track. Euler: ZYX (yaw → pitch → roll). Pixel indexing: `[row, col] = [y, x]`, 0-indexed. See `docs/RADIANT_Conventions.md` §1 for full details.

### 4. EffectivePSF Is the Single Source of Truth for Spatial Metrics
**NEVER** compute MTF and encircled energy (EE_box) from different PSFs. Both must derive from the same `EffectivePSF` object. All spatial metrics — MTF curve, EE(r), EE_box, RER — are computed from a single PSF that accumulates all optical aberrations, diffraction, and defocus. Deriving MTF from one PSF and EE from another (e.g., diffraction-only) introduces an internal inconsistency that will silently produce wrong results.

### 5. Emissivity of Optical Elements Is Always Derived — Never Independent
For any optical element, emissivity must be derived from Kirchhoff's law:
- Mirrors: `ε = 1 − R`
- Transmissive elements: `ε = 1 − T − R`

**Never** accept emissivity as an independent input parameter for an optical surface. A user who specifies both reflectance and emissivity for an optical element is over-specifying the system. Validate and derive; do not accept both.

This rule does **not** apply to scene targets and backgrounds, where emissivity is a legitimate independent parameter (it describes a material property, not an energy balance constraint).

### 6. Stages Are Pure Functions
- Stage signature: `run(self, state: ChainState, params: ParameterSet) -> ChainState`
- Stages **do not** mutate inputs. Use `state.with_frame(...)`, `state.with_noise(...)`, `state.with_mtf(...)`, `state.with_stage_output(...)`.
- Stages **do not** read files. File I/O happens before chain execution in `SpectralDataStore`.
- Stages **do not** call other stages. All inter-stage data flows through `ChainState`.

### 7. ChainState Is Immutable
`ChainState` is a frozen dataclass. Never assign to its fields directly. Always use the `with_*` methods. Fields added by earlier stages are never removed or overwritten by later stages.

### 8. Spectral Integration Happens Exactly Once
Before `SpectralIntegrationStage`: spectral arrays (shape = N_wavelengths). After: per-pixel scalars (e-, DN). No other stage collapses spectral to scalar.

### 9. EE_box Applied Exactly Once
Applied in `SpectralIntegrationStage` only, only for point-source and sub-pixel target regimes, never to the background term in sub-pixel regime, never in extended-scene regime.

### 10. Regime Finalized in OpticsStage
- `SourceStage` tentative classification: `state.stage_outputs["source"]["regime_tentative"]`
- `OpticsStage` final classification: `state.stage_outputs["optics"]["regime"]`
- All downstream stages read `state.stage_outputs["optics"]["regime"]`. Never re-classify.

### 11. No Cross-Stage Imports in Physics Modules

```python
# FORBIDDEN in source, atmosphere, optics, platform,
# spectral_integration, detector, readout, performance:
from radiant.optics import psf        # cross-stage physics import — NO
from radiant.source import blackbody  # cross-stage — NO

# ALLOWED:
from radiant.core.chain import ChainState
from radiant.core.parameters import ParameterSet
from radiant.core.spectral import SpectralData
```

`import-linter` enforces this in CI and will block PRs that violate it.

### 12. Every Parameter Has a ParameterDef in `_schema.py`
New parameters go in the owning stage's `_schema.py` (not `parameters.py` — that name is used internally by `radiant.core.parameters`). Required fields: `name` (dot-path), `dtype`, `canonical_unit`, `input_unit`, `default` or `None`. Naming: `namespace.parameter_name` — lowercase, underscores, no units in name. All tuneable quantities are parameters; nothing is hardcoded in physics modules.

### 13. Physical Constants From `constants.py`
```python
# CORRECT:
from radiant.core.constants import h, c, k_B
L = (2 * h * c**2 / lam_m**5) / (np.exp(h * c / (lam_m * k_B * T)) - 1)

# FORBIDDEN:
L = (2 * 6.626e-34 * (3e8)**2 / lam_m**5) / ...  # magic numbers
```

### 14. No `print()` in Library Code
Use the standard `logging` module. `print()` is permitted only in `cli/` entry points and examples.

### 15. Errors Are Actionable
```python
# CORRECT:
raise ParameterBoundsError(
    what=f"sensor.detector.operating_temp = {T} K is out of bounds",
    why="HgCdTe operates at cryogenic temperature (1–300 K)",
    action="Set operating_temp to 77–120 K for HgCdTe detectors",
    context={"param": "sensor.detector.operating_temp", "value": T, "bounds": (1, 300)},
)

# FORBIDDEN:
raise ValueError("invalid temperature")
raise AssertionError("bad value")   # assert is for developer invariants only
```

### 16. Validate Before Compute
Validate all user-controlled inputs before doing any physics computation. Use `ParameterSet` — never pass raw dicts from user input to physics functions. Never return `NaN` or `inf` silently; raise `NumericalError` with context.

### 17. No Silent Failures
No `except Exception: pass`. No `except Exception: return default_value`. No logging a warning and continuing when physics is undefined. No clipping values to valid ranges without at minimum a `UserWarning`.

### 18. Test at Level 0 First
Write the Level 0 test that verifies the key equation **before** implementing the physics. Tests use known-good analytic values, not values computed by other RADIANT code. `pytest.approx` always uses explicit `rel=` or `abs=` tolerance — never the default.

### 19. One Computation, One Module
Each distinct physics calculation or metric (e.g., ground range, swath width, access rate, folded MTF) gets its own file. Do not bundle unrelated computations into a single module just because they share a stage or a prompt. A developer should be able to find a calculation by scanning file names, not by reading through a multi-purpose file.

**When this applies:**
- New standalone computations (pure functions with no shared mutable state)
- Metrics that could be tested, documented, or reused independently

**When bundling is acceptable:**
- Tightly coupled computations that share internal state or helper functions and would be meaningless apart (e.g., cavity T_sys and cavity eps_eff are one model, not two files)

---

## Agent Task Discipline

These rules govern how a coding agent handles a task. Violating them produces scope creep, architecture drift, or silent physics bugs.

- **One task per conversation.** Do only what the task specifies. Stop.
- **Read before writing.** Before writing any code, read the architecture document(s) listed in the task's "Read first:" section.
- **Do not implement unrequested features,** even obviously related ones. They get their own task.
- **Do not modify files outside the task's stated scope.**
- **Do not invent abstractions** not specified in the architecture documents.
- **Stop and ask if you encounter a contradiction** between the task and the architecture docs. Do not guess; do not resolve it silently.
- **Write tests as you go.** Do not batch tests at the end.
- **Run tests before declaring complete.** A task is not done until the tests pass.
- **Produce a structured report** when complete, following the category requirements below.

---

## Validation Framework

Every task is assigned a category (A–D). The category determines what the completion report must include. The category is declared at the top of each task prompt.

### Category A — Pure Infrastructure
Structured report + self-review checklist.

### Category B — Core Abstractions
All of A, plus:
- **Dimensional audit:** verify every quantity has correct units at every interface
- **Failure modes:** document what breaks if inputs are at or beyond bounds
- **Serialization round-trip:** verify objects serialize and deserialize without loss

### Category C — Physics Implementation
All of B, plus:
- **Numerical truth anchors:** 3 independent sources (literature, analytic result, or trusted tool) that confirm the computed values
- **Assumptions:** explicit list of what is assumed (linearity, small-angle, etc.)
- **Fragility analysis:** what inputs cause this model to break down or become inaccurate
- **Cross-model consistency:** verify this module's output is consistent with adjacent stages (e.g., at-aperture radiance going into optics makes physical sense given the source)

### Category D — Integration and UX
All of C, plus:
- **Integration tests:** full chain tests confirming this change integrates correctly
- **Regression checks:** confirm no golden results changed unexpectedly; if they did, explain why

---

## Validation Section Specifications

When a category requires a validation section, use the exact format below. These are not optional fields — every required section must appear in the task report.

### 1. Numerical Truth Anchors (Category C — mandatory)

Every numerical implementation validated against at least THREE independent sources. For each anchor:

```
Truth Anchor N: [Name]
  Source: [citation, URL, or "hand calculation"]
  Expected: [value with units]
  Actual: [value with units]
  Absolute error: [value]
  Relative error: [value]
  Regime notes: [whether error grows in any parameter regime, and why]
```

If fewer than three anchors are available, explicitly document which are missing and why.

### 2. Dimensional Consistency Audit (Categories B and C — mandatory)

Trace units through every stage of the computation as a table:

```
Stage           | Input Units         | Output Units       | Conversion   | Check
----------------|---------------------|--------------------|--------------|-------
Input λ         | µm                  | µm                 | none         | ✓
Planck          | µm, K               | W/m²/sr/µm         | constants.hc | ✓
Integrate dλ    | W/m²/sr/µm, µm      | W/m²/sr            | trapz        | ✓
× Ω             | W/m²/sr, sr         | W/m²               | multiply     | ✓
× A_pixel       | W/m², m²            | W                  | multiply     | ✓
÷ E_photon      | W, J/photon         | photon/s           | divide       | ✓
× t_int         | photon/s, s         | photon             | multiply     | ✓
```

Every row must check. Any mismatch must be either resolved or explicitly justified.

### 3. Failure Mode Tests (Categories B and C — mandatory)

Test at the edges. Required coverage:

- **Edge-of-domain:** zero, very small (underflow risk), very large (overflow risk), negative
- **Extreme physical cases:** zero transmission, T → 0 K, T → 10000 K, λ → 0, λ → ∞, infinite range
- **Invalid inputs:** wrong types, grid mismatches, over-constrained consistency groups, negative where positive required
- **Conflicting parameters:** specifying both X and derived(X), mutually exclusive modes

Report each case with expected vs. actual behavior.

### 4. Assumptions (Category C — mandatory)

Every physics implementation makes assumptions. Name them explicitly:

```
Assumption: [What is assumed]
  Why valid: [Physics justification]
  What breaks: [What happens if this assumption is violated]
  Detected how: [Runtime check / documentation / silently wrong]
```

### 5. Fragility Analysis (Category C — mandatory)

```
What breaks this implementation?
  - Numerical instability zones
  - Invalid physics regimes
  - Cancellation errors (large - large ≈ small)
  - Overflow / underflow thresholds

Mitigations:
  - Input validation
  - Alternative formulations for extreme regimes
  - Explicit warnings or errors
  - Documentation
```

### 6. Traceability and Reproducibility (All categories)

```
Same inputs → identical outputs: [verified / not verified — explain]
Deterministic seed where applicable: [yes / no — justify]
Intermediate values inspectable: [yes (via result.inspect()) / no — explain]
```

### 7. Cross-Model Consistency (Category C — when multiple methods exist)

When there are multiple ways to compute the same thing, they must agree:

```
Model A: [description]
Model B: [description]
Tolerance: [e.g., < 1% or mathematical identity]
Result: max absolute difference = X, max relative = Y
```

### 8. Integration and Regression (Category D and end of each sub-phase)

```
Existing golden tests: [pass count / total]
  If any failed: [which values changed, by how much, and why]
New golden tests added: [yes / no]
Physics changes documented in CHANGELOG: [yes / no / N/A]
```

---

## Self-Review Checklist

Run this mentally before declaring any task complete.

### Physics
- Did I confuse units anywhere? (Verify the dimensional audit.)
- Did I implement the formula, or did I interpret it and implement my interpretation?
- Are signs correct? Is energy flowing in the right direction?
- Would a physicist raise an eyebrow at any intermediate output?

### Code
- Does the code actually do what the docstring says?
- Are tests testing real behavior, or just passing trivially?
- Is there any test that would still pass if I gutted the implementation?
- Any hidden state, globals, or side effects I missed?

### Architecture
- Does this respect all 18 rules above?
- Did I invent any abstraction not in the architecture documents?
- Did I couple modules that should be independent?

### Scope
- Did I implement only what the task asked for?
- Any "while I was here" additions that should be separate tasks?

---

## Structured Report Template

Every task ends with a report in exactly this format. Omit sections not required by the task's category, but never omit required sections.

```
# Task Report: [Task Name]

## Category: [A / B / C / D]

## Files
Created:
  - path/to/file1
Modified:
  - path/to/file2
Tests added:
  - tests/path/test_file.py (N tests)

## Test Results
Total tests: N
Passing: N
Failing: 0
Coverage (this task): XX%
Coverage (overall): YY%

## Numerical Validation (Category C only)
### Truth Anchor 1: [Name]
  Source: ...
  Expected: ...
  Actual: ...
  Absolute error: ...
  Relative error: ...
  Regime notes: ...
### Truth Anchor 2: [Name]
  ...
### Truth Anchor 3: [Name]
  ...

## Dimensional Audit (Categories B, C)
[Table per spec above]
Issues: none / [describe]

## Failure Modes Tested
[List of edge cases with expected vs. actual behavior]

## Assumptions (Category C)
[List per spec above]

## Fragility Points (Category C)
[Known limitations with mitigations]

## Traceability
Same inputs → identical outputs: ...
Deterministic seed: ...
Intermediate values inspectable: ...

## Cross-Model Consistency (Category C, if applicable)
[Comparison results per spec above]

## Regression Status (Category D, or if existing code touched)
Existing golden tests: [pass / total]
Changes to golden values: none / [list with explanation]
New golden tests added: yes / no

## Self-Review
Physics: [notes]
Code: [notes]
Architecture: [notes]
Scope: [notes]

## Open Issues or Questions
[Anything unclear, any decisions that need human input]
```

---

## Package Layout

```
src/radiant/
├── core/           # Foundational abstractions — NO physics, NO sensor knowledge
│   ├── constants.py      # CODATA 2018 physical constants
│   ├── units.py          # Unit conversion registry
│   ├── parameters.py     # ParameterDef, ParameterSet, Tolerance, ConsistencyGroup
│   ├── spectral.py       # SpectralData, SpectralDataStore
│   ├── chain.py          # Stage Protocol, ChainState, ChainRunner
│   ├── radiometry.py     # RadiometricFrame, NoiseTerm
│   ├── geometry.py       # ObserverGeometry, SceneGeometry
│   └── regime.py         # RadiometricRegime enum
├── source/         # Stage 1: target + background spectral radiance
├── atmosphere/     # Stage 2: τ_atm, L_path, L_atm
├── optics/         # Stage 3: PSF, MTF, throughput, EE_box, regime final
├── platform/       # Stage 4: smear MTF, jitter MTF
├── spectral_integration/  # Stage 5: spectral → scalar (EE_box coupling)
├── detector/       # Stage 6: QE, noise terms, detector MTF
├── readout/        # Stage 7: TDI, ADC, gain, read noise
├── performance/    # Stage 8: SNR, NEDT, NIIRS, system MTF
├── io/             # I/O layer — YAML, MODTRAN, results
├── api/            # Public API — Sensor, SensorConfig, BatchRunner
├── cli/            # CLI — radiant run/validate/explain
└── plugins/        # Extension points — SourcePlugin, AtmospherePlugin, MetricPlugin
```

---

## Import Rules (Strict — Enforced by `import-linter`)

| Module | May import from |
|--------|----------------|
| `core/` | stdlib, numpy, scipy ONLY |
| Physics stages (source through performance) | `radiant.core` ONLY |
| `io/` | `radiant.core` + any physics stage (read-only for schema) |
| `api/` | `radiant.core` + all physics stages + `radiant.io` |
| `cli/` | `radiant.api` + `radiant.io` |
| `plugins/` | `radiant.core` ONLY (ABCs) |

---

## How to Find Things

| What you need | Where to look |
|--------------|--------------|
| Architecture overview | `docs/RADIANT_Master_Architecture.md` |
| Where files go | `docs/RADIANT_File_Tree.md` |
| All parameters | `docs/RADIANT_Parameter_System.md` |
| Subsystem design detail | `docs/RADIANT_<Subsystem>.md` |
| The code | `src/radiant/` |
| The tests | `src/radiant/<stage>/tests/` and `tests/integration/` |

---

## When Editing an Existing Stage

1. Read the stage's doc (e.g., `docs/RADIANT_Optics.md`) before changing anything.
2. Read the tests before changing the implementation. The tests define the contract.
3. Run the tests: `pytest src/radiant/<stage>/tests/ -v`
4. Do not add imports that violate the import rules. Check with `import-linter`.
5. Update `_schema.py` if adding or renaming parameters.
6. Do not change default values without reviewing all integration tests — defaults affect golden results.
7. Do not rename public API methods on `Sensor`, `ChainResult`, `SweepResult` without a deprecation warning.

---

## When Adding a New Stage

1. Create `src/radiant/<stage_name>/` directory.
2. Create `_schema.py` with all `ParameterDef` objects for this stage.
3. Create `stage.py` implementing the `Stage` protocol.
4. Create `tests/` with Level 0 tests for the key physics equations.
5. Register the stage in `api/session.py`'s `ChainRunner` stage list.
6. Add the stage to the document map in `docs/RADIANT_Master_Architecture.md`.

---

## Forbidden Actions

| Action | Why |
|--------|-----|
| `from radiant.optics import *` in a physics module | Violates import rules |
| `state.frames["name"] = frame` | Mutates frozen ChainState |
| Pass raw dict from user input to a physics function | Bypasses validation |
| Hardcode a physical constant anywhere except `constants.py` | Untracked magic number |
| Return `float("nan")` or `float("inf")` silently | Silent failure |
| `except Exception: continue` or `except Exception: pass` | Silent failure |
| `assert value > 0` for user input validation | Use `ParameterBoundsError` |
| `print()` in library code | Use logging |
| Compute MTF from one PSF and EE_box from a different PSF | Violates Rule 4 |
| Accept emissivity as independent parameter for an optical element | Violates Rule 5 |
| Modify a test's `pytest.approx` tolerance to make a failing test pass | Fix the physics, not the test |
| Update a golden file without the review protocol in `RADIANT_Testing_Validation.md §5.3` | Breaks reproducibility |
| Implement anything not requested by the task | Scope creep |

---

## Code Style

- **Formatter:** `ruff format`. Line length 100.
- **Linter:** `ruff check`. Zero warnings on `radiant.core` and `radiant.api`.
- **Type annotations:** Required on every function and method. `mypy --strict` must pass on `core/` and `api/`.
- **Docstrings:** All public functions and classes. One-line summary; Parameters/Returns section when non-obvious.
- **No `TODO`** in committed code without a linked GitHub issue number.

---

## Running Tests Locally

```bash
# Setup:
pip install -e ".[dev]"

# Fast tests (Level 0 + Level 1, no golden):
pytest src/ -v -m "not golden"

# Full suite:
pytest -v

# Coverage:
pytest --cov=radiant --cov-report=html

# Type check:
mypy --strict src/radiant/core src/radiant/api

# Import rules:
import-linter --config pyproject.toml

# Lint:
ruff check src/
```

All of these must pass before submitting a PR or declaring a task complete.
