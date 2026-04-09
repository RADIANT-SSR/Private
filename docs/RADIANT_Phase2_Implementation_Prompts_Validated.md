# RADIANT — Phase II Implementation Prompt Sequence (Validated)

## Purpose of This Document

This is the authoritative Phase II implementation plan, integrating
rigorous validation requirements into every task. It assumes Phase I
was executed using the optimized prompt sequence, producing a clean
set of ~20 architecture documents.

The core improvement over the previous version is **mandatory validation
at multiple levels** — every physics implementation must be defended
against independent references, dimensional audits, failure modes,
and adversarial review.

**Guiding principle:** Correctness > speed. Physics > convenience.
Validation > assumption. Every computed value must be defensible.

---

## Path and Naming Conventions (Authoritative Overlay)

The authoritative package layout is [`docs/RADIANT_File_Tree.md`](RADIANT_File_Tree.md)
and the "Package Layout" section of [`CLAUDE.md`](../CLAUDE.md). Where
this document and the file tree disagree, **the file tree wins**.
Implement every prompt under the conventions below; read any
superseded path in a "Produce:" list as if it had been written with
the correct path.

- **Core abstractions live in `src/radiant/core/`.** Constants, units,
  parameters, spectral data, chain/ChainState/Stage protocol, geometry,
  radiometry, and regime enum are all single files under `core/`, not
  standalone subpackages. Write `src/radiant/core/constants.py`, not
  `src/radiant/constants.py`. Write `src/radiant/core/spectral.py`
  (containing both `SpectralGrid` and `SpectralData`), not
  `src/radiant/spectral/grid.py` + `array.py`. Write
  `src/radiant/core/parameters.py` (containing `ParameterDef`,
  `Tolerance`, `ParameterSet`, and parameter exceptions), not a
  `src/radiant/parameter/` subpackage. Write
  `src/radiant/core/geometry.py`, not `src/radiant/geometry/...`.
- **Physics-stage packages are singular.** `source/`, `atmosphere/`,
  `optics/`, `platform/`, `spectral_integration/`, `detector/`,
  `readout/`, `performance/`. Never `sources/`, never `detectors/`.
- **Parameter definitions are in `<stage>/_schema.py`.** Never
  `<stage>/parameters.py` — that name collides with
  `radiant.core.parameters`. This is non-negotiable per CLAUDE.md
  Rule 12.
- **Stage tests are co-located** at `src/radiant/<stage>/tests/`, not
  at `tests/<stage>/`. The top-level `tests/` directory is reserved
  for cross-stage integration tests (`tests/integration/`).
- **Chain concerns are split per architecture.** The Stage protocol,
  `ChainState`, and `ChainRunner` live in `src/radiant/core/chain.py`.
  Result containers live in `src/radiant/io/results.py`. The
  session/scenario/sensor fluent API lives in `src/radiant/api/`.
  There is no `src/radiant/chain/` subpackage.
- **No `src/radiant/spatial/` or `src/radiant/metrics/` subpackage.**
  Spatial computations (PSF, MTF, EE, diffraction, aberrations,
  EE_box) live in `optics/`. Motion terms (smear, jitter, TDI,
  sampling MTF) live in `platform/`. Metrics (SNR, NEΔT, NIIRS, system
  MTF, detection range) live in `performance/`.
- **No `src/radiant/target_geometry/` subpackage.** Target geometry
  primitives and materials live under `source/` per
  [`RADIANT_Source_Target_System.md`](RADIANT_Source_Target_System.md).
- **Canonical file names inside `source/`.** Use `blackbody.py` for
  Planck and integrated exitance (not `planck.py`). Use `emitted.py`
  for `ThermalSource` (not `thermal.py`). Use `emissivity.py`,
  `reflected.py`, `solar.py`, `background.py` per file tree.

If a prompt's "Produce:" list is ambiguous against the file tree, open
the file tree and pick the closest canonical file — do not introduce
new subpackages.

---

## VALIDATION FRAMEWORK

This framework scales with task complexity. Not every prompt needs
every section, but physics tasks need ALL of them.

### Task Categories

```
CATEGORY A: Pure Infrastructure
  (project scaffold, file layout, tool configs)
  Required: structured report only
  Example: Prompt 2A.1

CATEGORY B: Core Abstractions
  (parameter system, spectral grid, coordinates)
  Required: structured report, failure modes, serialization
  Example: Prompts 2A.2–2A.5

CATEGORY C: Physics Implementation
  (Planck, atmosphere, optics, PSF, noise)
  Required: ALL validation sections (Truth Anchors, Dimensional Audit,
            Failure Modes, Assumptions, Fragility, Self-Review)
  Example: Most 2B, 2C, 2D prompts

CATEGORY D: Integration and UX
  (chain assembly, CLI, scripting API, docs)
  Required: structured report, integration tests, regression checks
  Example: 2B.5, 2B.8, 2E prompts
```

Every prompt declares its category up front so both the agent and
the reviewer know what's required.

---

## THE NINE VALIDATION SECTIONS

When a prompt requires "full validation" (Category C tasks), the agent
must produce ALL of these sections in its report. Lower-category tasks
require a subset.

### 1. Numerical Truth Anchors (CATEGORY C — mandatory)

Every numerical implementation validated against at least THREE sources:

```
Truth Anchor 1: Analytical limit
  (e.g., Rayleigh-Jeans limit of Planck at long wavelength)

Truth Anchor 2: Published/tabulated reference
  (e.g., NIST blackbody tables, textbook values, peer-reviewed data)

Truth Anchor 3: Independent implementation
  (different code path, different library, or hand calculation —
  NOT the function being tested, NOT a wrapper around it)

For each anchor, report:
  - Source (with citation or URL)
  - Expected value
  - Actual value
  - Absolute error
  - Relative error
  - Whether error grows in any parameter regime, and why
```

If fewer than three anchors are available (rare), explicitly document
which are missing and why.

### 2. Dimensional Consistency Audit (CATEGORY B and C — mandatory)

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

Every row must check. Any mismatch must be either resolved or
explicitly justified (e.g., "this factor of 1e6 is µm → m conversion").

### 3. Failure Mode Tests (CATEGORY B, C — mandatory)

Every implementation must be tested at the edges:

```
Edge-of-domain inputs:
  - Zero (what should it do?)
  - Very small (numerical underflow risk)
  - Very large (overflow risk)
  - Negative (valid or error?)

Extreme physical cases:
  - Zero transmission
  - Infinite range
  - T → 0 K
  - T → 10000 K
  - λ → 0 (UV limit)
  - λ → ∞ (long-wave limit)

Invalid inputs (must error with clear messages):
  - Wrong types
  - Grid mismatches
  - Over-constrained consistency groups
  - Negative where positive required

Conflicting parameters:
  - Specifying both X and derived(X)
  - Mutually exclusive modes
```

Report each tested case with expected vs actual behavior.

### 4. Assumptions (CATEGORY C — mandatory)

Every physics implementation makes assumptions. Name them.

```
Assumption: [What]
  Why valid: [Physics justification]
  What breaks: [What happens if violated]
  Detected how: [Runtime check, documentation, or silently wrong]
```

Example: "Rayleigh-Jeans approximation valid when hc/(λkT) << 1.
At 300 K and 3 µm, hc/λkT ≈ 16, so full Planck is required. Breaks
silently if user assumes RJ applies — we always use full Planck."

### 5. Fragility Analysis (CATEGORY C — mandatory)

Every numerical implementation has failure modes beyond the validated range.

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

Example for Planck: "Direct exp(hc/λkT) overflows for short λ at low T.
Mitigation: compute in log space or use the expm1 formulation."

### 6. Traceability and Reproducibility (All categories)

```
Same inputs → identical outputs: verified
Deterministic seed where applicable: yes / no (justify)
Intermediate values inspectable: yes (via result.inspect())
```

### 7. Cross-Model Consistency (CATEGORY C — when multiple methods exist)

When there are multiple ways to compute the same thing, they must agree:

```
Model A: [description]
Model B: [description]
Tolerance: < 1% (or tighter for mathematical identities)
Result: max absolute difference = X, max relative = Y
```

Examples:
- Scalar transmission mode vs full element list for a simple case
- Extended chain at ff=1 vs sub-pixel chain at ff=1
- MTF from FFT of PSF vs MTF from multiplicative budget

### 8. Integration and Regression (CATEGORY D and end of each sub-phase)

When a task changes existing behavior:

```
Existing golden tests: still passing? yes / no
  If no: which values changed, by how much, and why?
New golden tests: added for new functionality? yes / no
Physics changes: documented in CHANGELOG?
```

### 9. Self-Review Checklist (ALL categories — mandatory)

Before declaring complete, the agent answers these questions in writing:

```
Physics:
  - Did I confuse units anywhere? (check the dimensional audit)
  - Did I implement a formula or interpret it? (common bug source)
  - Are signs right? (energy flows the right direction)
  - Would a physicist raising an eyebrow at my output be justified?

Code:
  - Does the code actually do what the docstring says?
  - Are the tests testing real behavior or just passing?
  - Any test that would still pass if I gutted the implementation?
  - Hidden state, globals, or side effects I missed?

Architecture:
  - Does this respect the CLAUDE.md rules?
  - Did I invent any abstraction not in the architecture docs?
  - Did I couple modules that should be independent?

Scope:
  - Did I implement only what the task asked for?
  - Any "while I was here" additions that should be separate tasks?
```

This is the fast, built-in version of the reviewer step. Full
adversarial review happens at sub-phase boundaries.

---

## STRUCTURED REPORT TEMPLATE

Every task ends with a report in this format:

```
# Task Report: [Task Name]

## Category: [A / B / C / D]

## Files
Created:
  - path/to/file1
  - path/to/file2
Modified:
  - path/to/file3
Tests added:
  - tests/path/test_file1.py (N tests)
  - tests/path/test_file2.py (M tests)

## Test Results
Total tests: N
Passing: N
Failing: 0
Coverage (this task): XX%
Coverage (overall): YY%

## Numerical Validation (Category C only)
### Truth Anchor 1: [Name]
  Expected: ...
  Actual: ...
  Error: ... (abs), ... (rel)
### Truth Anchor 2: [Name]
  ...
### Truth Anchor 3: [Name]
  ...

## Dimensional Audit Summary (Categories B, C)
[Table as shown above]
Any issues: none / [describe]

## Failure Modes Tested
[List of edge cases with results]

## Assumptions
[List with validity conditions]

## Fragility Points
[Known limitations with mitigations]

## Cross-Model Consistency (if applicable)
[Comparison results]

## Regression Status (if existing code touched)
Existing golden tests: [pass count / total]
Changes to golden values: [none / list]

## Self-Review
Physics: [notes]
Code: [notes]
Architecture: [notes]
Scope: [notes]

## Open Issues or Questions
[Anything unclear, any decisions that need human input]
```

---

## SUB-PHASE REVIEWER PROTOCOL

At the end of each sub-phase (2A, 2B, 2C, 2D, 2E), a dedicated
adversarial review pass runs BEFORE the human checkpoint.

### Reviewer prompt template

```
You are a scientific reviewer for the RADIANT project. Your job is to
find bugs, physics violations, and weak tests.

ASSUME the implementation has errors. Your success metric is how many
legitimate issues you find, not how many things look correct.

Read:
- All files implemented in sub-phase [2A / 2B / 2C / 2D / 2E]
- The corresponding architecture documents
- All test files for the sub-phase
- The task reports from each prompt

Find:
1. PHYSICS VIOLATIONS
   - Wrong formulas
   - Missing factors (π, 4π, etc.)
   - Sign errors
   - Confused units
   - Misapplied approximations

2. TEST WEAKNESSES
   - Tests that would pass even if the implementation were wrong
   - Tests with suspiciously loose tolerances
   - Untested edge cases
   - Tests that test trivial properties (e.g., "function returns a number")

3. HIDDEN ASSUMPTIONS
   - Implicit assumptions not documented
   - Assumptions that would silently break under common user inputs
   - Violated invariants

4. ARCHITECTURAL DRIFT
   - Code that contradicts design decisions in docs/
   - New abstractions not in the architecture
   - Inappropriate coupling between modules

5. SCOPE VIOLATIONS
   - Features implemented that weren't in the task spec
   - Missing required features
   - Stubs where full implementations were required

For each issue found, report:
  - Severity: CRITICAL / HIGH / MEDIUM / LOW
  - Location: file:line
  - Description: what's wrong
  - Fix: what should change
  - Test to add: how to prevent regression

Do NOT fix anything. Just report.

If you find fewer than 3 issues in a full sub-phase review, review
again — you missed something.
```

The reviewer's findings are reviewed by the human, who decides which
to fix and schedules the fixes as follow-up prompts before the next
sub-phase begins.

---

# PHASE 2A — FOUNDATION (5 prompts)

Category B tasks. Infrastructure with validation requirements.

## Prompt 2A.1 — Project scaffold

```
Task: Create the RADIANT project scaffold.
Category: A (pure infrastructure)

Read first:
- docs/RADIANT_File_Tree.md
- docs/RADIANT_Master_Architecture.md
- DEVELOPMENT.md
- CLAUDE.md (repo root)

Produce:
1. Directory structure exactly matching docs/RADIANT_File_Tree.md.
   Empty __init__.py in every package.
2. pyproject.toml with dependencies and tool configs per DEVELOPMENT.md
3. tests/ mirroring src/radiant/
4. README.md, .gitignore, .pre-commit-config.yaml

Verification:
- `pip install -e .[dev]` succeeds
- `pytest` runs (zero tests, framework functional)
- `ruff check .` passes
- `mypy src/radiant` passes

Report format: structured report (Category A — report + self-review only).
```

## Prompt 2A.2 — Constants and units

```
Task: Implement physical constants and unit conversions.
Category: B (core abstraction, numerical)

Read first:
- docs/RADIANT_Conventions.md

Produce:
1. src/radiant/core/constants.py
   - All physical constants with CODATA values via scipy.constants
   - Each with docstring: value, units, source, CODATA version
   - Derived convenience values (hc, 2hc², etc.)
2. src/radiant/core/units.py
   - Wavelength ↔ wavenumber (with documented sign conventions)
   - Photon energy and rate at given wavelength
   - Angular unit conversions
3. src/radiant/core/tests/test_constants.py
   - Each constant matches CODATA to 10 significant figures
4. src/radiant/core/tests/test_units.py
   - Invertibility: f(f⁻¹(x)) == x to machine precision
   - Edge cases: zero, very small, very large

Validation requirements (B):
- Structured report with dimensional audit
- Failure modes: what if user passes 0? negative? infinity?
- Serialization: to_dict/from_dict round trip test for any classes
- Self-review checklist

Report format: Category B (report + dimensional audit + failure modes
+ serialization + self-review).
```

## Prompt 2A.3 — Spectral grid and spectral array

```
Task: Implement SpectralGrid and SpectralArray.
Category: B (core abstraction with numerical operations)

Read first:
- docs/RADIANT_Conventions.md
- docs/RADIANT_Parameter_System.md

Produce:
1. src/radiant/core/spectral.py  (contains both SpectralGrid and
   SpectralData in a single module, per file tree)
2. src/radiant/core/tests/test_spectral.py

Validation requirements (B):

Numerical validation:
- integrate() against analytical cases:
  * Constant function: ∫c dλ = c×(λ_max - λ_min)
  * Linear function: ∫(a+bλ) dλ = a×Δλ + b×(λ_max² - λ_min²)/2
  * Gaussian: ∫exp(-(λ-λ₀)²/2σ²) dλ ≈ σ√(2π) (for σ << range)
  Report absolute and relative error for each.

- Resampling conservation:
  Resample a known function to a coarser grid, then integrate.
  Result should match analytical integral within interpolation error.

Dimensional audit:
- Every method documents input and output units
- Arithmetic operations preserve units correctly
- Grid-mismatch operations raise clear errors

Failure modes:
- Grid with n_points < 2
- Grid with negative wavelengths
- SpectralArray with wrong-length values
- Arithmetic with mismatched grids
- Resampling to a grid outside the original range

Serialization:
- SpectralGrid.to_dict/from_dict round trip
- SpectralArray.to_dict/from_dict round trip (values preserved to
  machine precision)

Self-review:
- Confirmed: integrate uses trapezoidal rule (np.trapz)
- Confirmed: arithmetic checks grid identity (not just shape)
- Confirmed: plot() uses lazy matplotlib import

Report format: Category B (full).
```

## Prompt 2A.4 — Parameter system

```
Task: Implement Parameter class and ParameterResolver.
Category: B (core abstraction)

Read first:
- docs/RADIANT_Parameter_System.md (single complete document)

Produce:
1. src/radiant/core/parameters.py  (single module containing
   ParameterDef, Tolerance, ConsistencyGroup, ParameterSet, and the
   parameter exception hierarchy — per file tree)
2. src/radiant/core/tests/test_parameters.py

Validation requirements (B):

Functional validation:
- Dependency chain (linear A→B→C→D): resolve order correct
- Diamond dependency (A→B, A→C, B→D, C→D): both paths resolved
- Circular dependency: detected and raised
- Consistency group: f/# from EFL and D; any 2 of 3 resolve the third

Error message quality:
- Missing required parameter: message names the parameter AND
  the metric that needed it
- Over-constrained consistency group: message lists conflicting values
- Circular dependency: message shows the cycle

Failure modes:
- Parameter with contradictory dtype and default
- Parameter with value outside valid_range
- Parameter with invalid valid_options
- Resolver asked for unknown parameter
- Tolerance with impossible distribution parameters

Serialization:
- Parameter.to_dict/from_dict round trip
- ResolvedParameters snapshot can be saved and reloaded

Self-review:
- Confirmed: topological sort handles ties deterministically
- Confirmed: explain() traces back through dependency chain
- Confirmed: tolerance sampling respects correlation groups

Report format: Category B (full).

Note: Include at least 5 examples of error messages so the reviewer
can verify quality.
```

## Prompt 2A.5 — Geometry

```
Task: Implement coordinate system and ViewingGeometry.
Category: B (core abstraction, numerical)

Read first:
- docs/RADIANT_Conventions.md (coordinate section)

Produce:
1. src/radiant/core/geometry.py  (single module containing the
   coordinate-system helpers, ObserverGeometry, and SceneGeometry —
   per file tree)
2. src/radiant/core/tests/test_geometry.py

Validation requirements (B):

Numerical validation:
- Rotation round-trip: euler → matrix → euler matches within 1e-12
- Known rotations (90° about each axis): matrix matches exact values
- Composition: R(A)R(B) ≠ R(B)R(A) for non-commuting (verify)
- Orthogonality: det(R) = 1, R × R^T = I
- Slant range at nadir (zenith=0) equals altitude
- Slant range at horizon-grazing (zenith ≈ 90°) is much larger

Dimensional audit: angles in radians internally, conversions explicit.

Failure modes:
- Slant range with negative altitude
- Zenith angle > 90° (below horizon)
- Non-orthogonal input matrix passed to euler decomposition

Serialization: ViewingGeometry.to_dict/from_dict

Report format: Category B (full).
```

**CHECKPOINT 2A:**

1. Human runs full test suite, verifies all pass.
2. Human verifies coverage > 90% on all 2A files.
3. Human runs `mypy --strict` and `ruff check` — both clean.
4. **Reviewer pass:** Run the reviewer prompt on all 2A deliverables.
   Expect at least 3–5 findings. Fix CRITICAL and HIGH before 2B.
5. Do not proceed to 2B until 2A is solid.

---

# PHASE 2B — MINIMUM VIABLE CHAIN (9 prompts)

The ninth prompt is new: the ground truth case.

## Prompt 2B.1 — Source protocol and Planck

```
Task: Implement Source protocol and ThermalSource.
Category: C (physics implementation)

Read first:
- docs/RADIANT_Source_Target_System.md (ThermalSource section only)
- docs/RADIANT_Signal_Chain_Architecture.md (protocols)

Produce:
1. src/radiant/source/protocol.py
   - SpectralRadianceSource structural Protocol (typing.Protocol)
2. src/radiant/source/blackbody.py
   - planck_spectral_radiance(wavelength_um, temperature_K) → W/m²/sr/µm
   - planck_spectral_radiance_dT (for NEΔT later)
   - Use expm1 or log-space for numerical stability
3. src/radiant/source/emitted.py
   - ThermalSource with scalar or spectral emissivity
4. src/radiant/source/_schema.py
5. src/radiant/source/tests/test_blackbody.py
6. src/radiant/source/tests/test_emitted.py

NOTE: Completed 2026-04-07. See the co-located files above.

Validation requirements (C — FULL):

Numerical truth anchors (MANDATORY — at least 3):
1. Stefan-Boltzmann law: ∫B(λ,T) dλ = σT⁴/π over all λ
   Verify at T = 300 K, 1000 K, 3000 K
   Tolerance: better than 0.1%
2. Wien displacement: λ_peak × T = 2898 µm·K
   Verify at T = 300 K, 1000 K, 3000 K
   Tolerance: better than 0.01%
3. Independent comparison: astropy.modeling.BlackBody OR hand-computed
   values from Wolfram Alpha OR tabulated reference
   (if astropy unavailable, use hand-computed values from NIST tables)
   At least 5 points spanning different wavelength-temperature regimes
   Tolerance: better than 0.01%

Additional limits to verify:
- Rayleigh-Jeans at long wavelength: B → 2ckT/λ⁴ (within 1% when hc/λkT < 0.1)
- Wien approximation at short wavelength: B → (2hc²/λ⁵)exp(-hc/λkT)
  (within 1% when hc/λkT > 10)

Dimensional audit:
Stage               | Input                | Output          | Check
--------------------|----------------------|-----------------|------
planck_spectral     | λ [µm], T [K]        | W/m²/sr/µm      | ✓
                    |                      |                 |
× emissivity        | W/m²/sr/µm, [dim]   | W/m²/sr/µm      | ✓

Verify the conversion factors in the Planck formula explicitly:
- hc/λkT must be dimensionless
- 2hc²/λ⁵ must have units W/m²/sr/µm (NOT W/m²/sr/m — watch the wavelength unit)

Failure modes:
- T = 0 K (should return 0 or raise, document choice)
- T → ∞ (should not overflow)
- λ → 0 (Wien regime, exp underflow — must handle gracefully)
- λ → ∞ (Rayleigh-Jeans regime — must not underflow)
- Negative T (error)
- Negative λ (error)
- Very small hc/λkT (< 1e-10): Taylor expansion to avoid loss of precision

Assumptions:
- Planck's law assumes thermodynamic equilibrium: valid for real bodies
  at single temperature, fails for non-LTE plasmas (out of scope)
- Emissivity independent of direction (Lambertian): scalar ε is isotropic
- Unpolarized radiation: polarization deferred

Fragility:
- exp(hc/λkT) overflows for hc/λkT > 700 (≈ 2 µm at 10 K)
- Mitigation: expm1 formulation OR log-space computation
- Document the numerically safe domain

Cross-model consistency:
Compare full Planck vs Rayleigh-Jeans approximation in the RJ regime.
Compare full Planck vs Wien approximation in the Wien regime.
Both should agree with full formula within their respective validity ranges.

Self-review:
- Confirmed: Planck uses expm1 for numerical stability
- Confirmed: units are W/m²/sr/µm, not W/m²/sr/m
- Confirmed: the 2hc²/λ⁵ factor uses λ in meters internally,
  converted to µm at output OR computed directly in µm consistently

Report format: Category C (full — all nine sections).

Follow-up: your report will be reviewed adversarially. A reviewer
will check whether your truth anchors are independent (not wrappers
around the function you're testing) and whether your failure modes
actually exercise the edges.
```

## Prompt 2B.2 — Simple atmosphere

```
Task: Implement Atmosphere protocol and SimpleAtmosphere.
Category: C (physics implementation)

Read first:
- docs/RADIANT_Atmosphere.md

Produce:
1. src/radiant/atmosphere/protocol.py
2. src/radiant/atmosphere/simple.py
3. src/radiant/atmosphere/exo.py  (new file within the stage package —
   thin wrapper returning τ = 1, L_path = 0)
4. src/radiant/atmosphere/_schema.py
5. src/radiant/atmosphere/tests/test_simple.py
6. src/radiant/atmosphere/tests/test_exo.py

Validation requirements (C):

Numerical truth anchors:
1. Analytical: τ(z, zenith) = exp(-path × extinction), should match
   the model at any single wavelength where only one absorber matters
2. Published: verify τ at 4.3 µm is low (CO₂ band) and τ at 4.0 µm
   is high (atmospheric window). Specific values from a MODTRAN
   reference or handbook.
3. Independent: compare to a simpler single-species Beer's law
   calculation for a single absorber case

Dimensional audit:
- τ_atm is dimensionless, values in [0, 1]
- L_path in W/m²/sr/µm
- Path length in km, converted to meters internally for optical depth

Failure modes:
- Zenith = 0 (nadir): slant = altitude
- Zenith = 90° (horizon): slant → ∞ conceptually, clamp or raise
- Zenith > 90° (pointing down from orbit): error
- Negative visibility: error
- ExoAtmosphere at any geometry: τ = 1, L_path = 0 exactly

Assumptions:
- Plane-parallel atmosphere below ~80° zenith (curvature ignored)
- No time variation within a single evaluation
- Spectral grid resolution adequate for the narrowest absorption feature
  being modeled (warn if grid too coarse)

Fragility:
- Slant path calculation singular at zenith = 90°
- Mitigation: clamp at 89° or use proper spherical atmosphere

Cross-model consistency:
- SimpleAtmosphere with visibility → ∞ should approach (not equal)
  ExoAtmosphere
- Document why they're not exactly equal (Rayleigh scattering still
  present in SimpleAtmosphere)

Self-review: confirm all assumptions documented.

Report format: Category C (full).

Deliverable: save a transmittance plot (0.4 to 14 µm, standard MLS
conditions) to src/radiant/atmosphere/tests/artifacts/ for visual
inspection.
```

## Prompt 2B.3 — Optics (scalar mode)

```
Task: Implement optics with scalar transmission only.
Category: B (geometric + light numerical)

Read first:
- docs/RADIANT_Optics.md (Mode 1 only)

Produce:
1. src/radiant/optics/aperture.py  (new file — circular/obscured
   aperture geometry, f/# consistency group helpers)
2. src/radiant/optics/telescope.py  (new file — scalar throughput
   container composing aperture + filter + coating stack)
3. src/radiant/optics/_schema.py
4. src/radiant/optics/tests/test_aperture.py
5. src/radiant/optics/tests/test_telescope.py

Validation requirements (B):

Numerical validation:
- Circular aperture area = π(D/2)²
- Obscured aperture area = π/4 × (D² - d²)
- f/# consistency: if any 2 of {EFL, D, f/#} specified, third derives
- Solid angle Ω = π / (4 × f/#²) — verify at f/1 (Ω = π/4), f/∞ (Ω → 0)

Dimensional audit:
- Diameter [m], focal length [mm] internally consistent (pick one)
- Ω [sr]

Failure modes:
- Obscuration ratio ≥ 1 (error)
- Negative diameter (error)
- Specifying all three of {EFL, D, f/#} with inconsistent values: error
  with message showing the discrepancy

Serialization: to_dict/from_dict for all classes.

Self-review.

Report format: Category B.
```

## Prompt 2B.4 — Detector (basic)

```
Task: Basic detector with minimum noise for SNR.
Category: C (physics — noise statistics)

Read first:
- docs/RADIANT_Detector_Complete.md (QE, pixel, basic noise sections)

Produce:
1. src/radiant/detector/qe.py
2. src/radiant/detector/pixel.py  (new — pixel geometry container)
3. src/radiant/detector/stage.py  (per file tree — DetectorStage
   implementing the Stage protocol, not a file named detector.py)
4. src/radiant/detector/shot_noise.py  (photon + dark shot noise)
   src/radiant/detector/dark_current.py  (dark rate model)
   Read noise and quantization noise live in `readout/` per the
   file tree — implement the minimum stubs there as well:
   src/radiant/readout/read_noise.py  (MINIMUM: Gaussian 1σ),
   src/radiant/readout/adc.py  (quantization only).
5. src/radiant/detector/_schema.py
   src/radiant/readout/_schema.py
6. Tests co-located under each stage's tests/ directory.

Validation requirements (C):

Numerical truth anchors:
1. Poisson statistics: for Poisson process with mean μ, variance = μ,
   so σ = √μ. Verify shot noise calculation follows this.
2. Published: compare HgCdTe MWIR QE library values to a published
   reference curve (spot-check 3+ wavelengths)
3. Independent: hand-compute electron count for 300 K blackbody,
   ideal optics, 1 ms integration — compare to the function output

Dimensional audit:
| Stage | Input | Output | Check |
| power | W | W | ✓ |
| photons | W, J/photon (hc/λ) | photon/s | ✓ |
| × QE | photon/s, dim | e⁻/s | ✓ |
| × t_int | e⁻/s, s | e⁻ | ✓ |
| sqrt(e⁻) | e⁻ | e⁻ (noise) | ✓ |

Failure modes:
- Zero signal (shot noise = 0, handled)
- Negative signal (should error — unphysical)
- QE > 1 (error or warning)
- QE curve outside the evaluation grid (interpolation vs error)
- Very large signal (watch for float precision in sqrt)

Assumptions:
- Photon shot noise is Poisson (classical light, not coherent)
- QE wavelength-independent within sub-band: false in general, justify
- Read noise is Gaussian (spec says 1σ)

Cross-model consistency:
- RSS combination: σ_total² = σ₁² + σ₂² + ... — verify for independent sources
- For equal sources: σ_total = σ × √N

Self-review.

Report format: Category C (full).
```

## Prompt 2B.5 — Chain skeleton and extended-scene chain

```
Task: Signal chain skeleton and extended-scene chain.
Category: C (integration of physics modules)

Read first:
- docs/RADIANT_Signal_Chain_Architecture.md
- notes/blocked.md (Blocker 3 carry-forward, dated 2026-04-08)
- This prompt's "Design decisions" section below — these are
  Jason-confirmed and override the architecture doc where they
  differ.

Design decisions (Jason-confirmed 2026-04-09):
1. ChainState collections (frames, stage_outputs, mtf_terms, metrics)
   are typed as Mapping[...] and frozen at construction via
   types.MappingProxyType so direct mutation raises TypeError.
   Convention is not enough — the immutability must be enforceable.
2. SpectralIntegrationStage is its own stage (not folded into
   DetectorStage). It owns the EE_box coupling per CLAUDE.md Rule 9.
3. OpticsStage stubs EE_box = 1.0 and final regime = "extended" for
   2B.5, with an inline TODO pointing at Phase 2C.4 (EffectivePSF).
   This is the *only* stub in the wrappers.
4. PlatformStage is skipped entirely in 2B.5 — not registered in the
   runner, no stub. Phase 2C.3 will append it.
5. Per-wrapper unit tests are required IN ADDITION to the
   end-to-end integration test. ~6 tests, one per stage wrapper,
   each asserting that a hand-crafted input ChainState produces the
   expected output frame and stage_output keys.
6. ChainResult in 2B.5 is minimal: it exposes raw state.frames /
   state.noise_terms / state.stage_outputs only. The signal_at /
   noise_at / noise_budget propagation queries are deferred to a
   post-2B.6 task because they need forward-factor backward-prop
   machinery (architecture doc §5) that no primitive supports yet.

Produce:

A. Core scaffolding (radiant.core, no physics imports):
1. src/radiant/core/radiometry.py
   - RadiometricFrame (frozen dataclass with shape validation against
     wavelength_um, XOR between spectral arrays and in_band_value)
   - NoiseTerm (frozen dataclass; value_e ≥ 0)
2. src/radiant/core/chain.py
   - Stage Protocol (runtime_checkable; .name + .run(state, params))
   - ChainState frozen dataclass with Mapping fields wrapped in
     MappingProxyType in __post_init__
   - with_frame / with_stage_output / with_noise / with_mtf /
     with_metric / with_history helpers — each returns a NEW state
   - ChainRunner: validates name uniqueness up front, iterates
     stages, auto-records history if a stage didn't self-record
3. src/radiant/core/tests/test_radiometry.py
4. src/radiant/core/tests/test_chain.py
   - Includes a test that direct mutation of state.frames raises

B. Stage wrappers (one per physics package; ~80–120 LOC each):
5. src/radiant/source/stage.py
   - SourceStage wrapping ThermalSource.spectral_radiance
   - Writes frame "at_target", stage_output["source"]["regime_tentative"]
6. src/radiant/atmosphere/stage.py
   - AtmosphereStage wrapping SimpleAtmosphere/ExoAtmosphere
   - Reads frame "at_target", writes frame "at_aperture" (radiance
     attenuated by τ_atm + L_path), stashes τ_atm and L_atm_down
     in stage_outputs["atmosphere"]
7. src/radiant/optics/stage.py
   - OpticsStage wrapping ScalarTelescope
   - Reads "at_aperture", writes frame "post_optics" (× transmission)
   - Stashes A_collect, Omega_pixel in stage_outputs["optics"]
   - Stubs EE_box = 1.0, regime = "extended" with TODO(2C.4) comment
8. src/radiant/spectral_integration/__init__.py
   src/radiant/spectral_integration/stage.py
   src/radiant/spectral_integration/_schema.py (filter band, t_int)
   src/radiant/spectral_integration/tests/test_stage.py
   - SpectralIntegrationStage: reads "post_optics", computes
     photon_rate(λ) = L · A_collect · Ω_pixel · τ_opt · (λ/hc),
     applies QE(λ), integrates over filter bandpass, multiplies by
     t_int, writes "photoelectrons" frame with in_band_value (e-).
     Reads regime + EE_box from stage_outputs["optics"]; for
     "extended" regime EE_box does NOT apply (Rule 9). Asserts
     EE_box-ne-1 + extended is a programming error.
9. src/radiant/detector/stage.py
   - DetectorStage assembling QuantumEfficiency, DarkCurrent,
     PixelGeometry, shot_noise primitives.
   - Enforces detector.qe_value XOR detector.qe_table_path via a
     ConsistencyGroup at the resolver layer (Blocker 4 carry-forward
     from 2B.4); dispatches to QuantumEfficiency.constant or
     QuantumEfficiency.from_spectral.
   - Reads "photoelectrons" frame in_band_value, emits NoiseTerms:
     shot (Poisson on signal e-), dark_shot (Poisson on
     dark_e_accumulated). All NoiseTerms have origin_frame =
     "photoelectrons".
10. src/radiant/readout/stage.py
    - ReadoutStage wrapping read_noise + adc primitives.
    - Adds NoiseTerms: read (origin "photoelectrons"), quantization
      (origin "photoelectrons", LSB/√12 in equivalent e-).
    - Optionally writes a "dn" RadiometricFrame with in_band_value =
      signal converted via gain (or leave for the next task; pick
      one and document).

C. Result + integration:
11. src/radiant/io/results.py
    - ChainResult (minimal): wraps a ChainState, exposes .frames,
      .noise_terms, .stage_outputs, .history, .wavelength_um as
      read-only properties. NO signal_at / noise_at queries.
12. src/radiant/api/session.py
    - RadiantSession that builds a ChainRunner with the 6 stages
      (no PlatformStage, no PerformanceStage in 2B.5) and exposes
      .run(params) -> ChainResult.

D. Tests:
13. Per-wrapper unit tests, one file per stage in
    src/radiant/<stage>/tests/test_stage.py — each asserts that a
    hand-crafted input ChainState produces the expected output frame
    name(s), stage_output keys, and (where applicable) noise terms.
14. tests/integration/test_chain_extended.py
    - One reference case: MWIR staring sensor, 300 K extended
      scene, nadir, SimpleAtmosphere mid-latitude summer, scalar
      optics (D=0.30 m, f=1.20 m), pixel pitch 18 µm, t_int 5 ms.
    - Asserts every intermediate value matches a hand calculation
      to within 1e-3 relative.

Validation requirements (C):

Numerical truth anchors (3+):
For the reference case above, compute and report every intermediate:
- L_source(4.0 µm) [W/m²/sr/µm]
- τ_atm(4.0 µm) [dimensionless]
- L_at_aperture(4.0 µm) [W/m²/sr/µm]
- τ_optics(4.0 µm) [dimensionless]
- L_post_optics(4.0 µm) [W/m²/sr/µm]
- photon_rate(4.0 µm) at FPA [photons/s/pixel/µm]
- in-band photoelectrons per integration [e-]
- shot, dark_shot, read, quantization noise [e- RMS each]

Each value must be hand-verifiable. The integration test checks all
of them.

Dimensional audit table: full chain from L_source [W/m²/sr/µm] to
photoelectrons [e-]. Every row checks.

Failure modes:
- Zero transmission (τ_atm = 0): all downstream frames present
  with zero values, noise terms still defined, no NaN, no crash.
- Wavelength grid mismatch between stages: clear error before any
  physics runs.
- Direct mutation of state.frames: TypeError from MappingProxyType.
- Missing required parameter: ParameterBoundsError with field name.
- Detector QE both qe_value and qe_table_path set:
  ConsistencyGroup violation with both field names.
- Detector QE neither set: ConsistencyGroup violation.

Energy conservation check:
- Power at detector ≤ power at aperture (× A_collect, × τ_opt).
- No stage adds energy beyond what physics allows
  (atmosphere may ADD path radiance, but the aperture-frame
  radiance bound by sensor-scene-emission limits is an overall
  spot-check, not a stage-by-stage equality).

Cross-model consistency:
- Run the chain twice with identical inputs → state.frames and
  state.noise_terms are identical to machine precision.
- Perturb t_int by +10% → photoelectrons scales by +10%, shot σ
  scales by √1.1.

Self-review: verify the chain respects the 8 architectural invariants
in RADIANT_Signal_Chain_Architecture.md §9 — especially Rule 7
(immutability), Rule 8 (single spectral integration), Rule 9 (single
EE_box site), and Rule 11 (no cross-stage physics imports — verified
by import-linter).

Report format: Category C (full).
```

## Prompt 2B.6 — SNR metric and YAML I/O

```
Task: SNR metric and YAML configuration I/O.
Category: D (integration and UX)

Read first:
- docs/RADIANT_Metrics.md (SNR section)
- docs/RADIANT_Config_Format.md

Produce:
1. src/radiant/performance/snr.py  (per file tree — metrics live in
   performance/, not metrics/)
2. src/radiant/performance/stage.py  (PerformanceStage — may already
   exist as a stub; extend to assemble SNR from ChainState)
3. src/radiant/io/config.py  (YAML sensor config loader → ParameterSet,
   per file tree — replaces yaml_io.py / schema.py split)
4. src/radiant/performance/tests/test_snr.py
5. src/radiant/io/tests/test_config.py
6. examples/mwir_leo_minimal.yaml
7. tests/integration/test_mwir_leo_minimal.py

Validation requirements (D):

Functional tests:
- SNR formula correctness at several signal/noise regimes
- YAML round-trip: save, load, compare (deep equality)
- Invalid YAML: clear error message indicating file, line, problem
- Schema violation: clear error with the offending field

Failure modes:
- YAML with missing required fields
- YAML with wrong types
- YAML referencing non-existent library items
- SNR with zero noise (infinity or error, documented)
- SNR with zero signal (zero, documented)

Regression:
- Store golden value for the minimal config, verify reproducibility

Report format: Category D (report + functional validation + regression
+ self-review).
```

## Prompt 2B.7 — CLI skeleton

```
Task: Minimal CLI.
Category: D (UX integration)

Read first:
- docs/RADIANT_Config_Format.md (CLI section)

Produce:
1. src/radiant/cli/main.py  (Click entry point)
   src/radiant/cli/run.py  (run subcommand)
   src/radiant/cli/validate.py  (validate subcommand)
2. pyproject.toml entry point  (already registered as `radiant`)
3. src/radiant/cli/tests/test_cli.py

Validation:
- `radiant run examples/mwir_leo_minimal.yaml` works and produces
  sensible output
- `radiant run ... --set optics.aperture.diameter=0.5` overrides work
- `radiant validate ...` catches invalid configs
- Clear help text

Failure modes:
- Config file not found: clear error
- Invalid override path (e.g., --set typo.path=X): clear error
- Invalid override value type: clear error

Report format: Category D.
```

## Prompt 2B.8 — Golden regression baseline

```
Task: First golden regression test.
Category: D (integration, regression infrastructure)

Read first:
- docs/RADIANT_Testing_Validation.md

Produce:
1. tests/integration/golden/mwir_leo_minimal.json
   - Every key output stored with provenance comment:
     "signal_electrons: 45234.5  # hand-verified 2026-04-15, see notes"
2. tests/integration/test_golden_mwir_leo_minimal.py
   - Tolerance 0.1% (floating-point, not physics)
3. scripts/update_golden.py
   - Requires --i-know-what-im-doing flag
   - Logs what changed and why
4. Full test suite with coverage report

Every golden value MUST have a provenance comment explaining where
the number came from:
- "hand calculation" (with reference to the computation)
- "independent tool: <name, version>"
- "previous implementation verified against <anchor>"

Report: coverage, test output, provenance of every golden value.
```

## Prompt 2B.9 — Ground truth case (NEW)

```
Task: Establish the fully hand-computable ground truth case.
Category: C (physics validation)

This is the single most important test in Phase 2B. It's the
reference all other tests point back to.

Read first:
- docs/RADIANT_Signal_Chain_Architecture.md
- docs/RADIANT_Radiometric_Chain_Regimes.md (or the equivalent in
  your architecture)

Construct a case where every intermediate value can be computed
by hand with a calculator, end-to-end:

Parameters:
- Single wavelength: λ = 4.0 µm exactly (or very narrow grid)
- Atmosphere: ExoAtmosphere (τ = 1, L_path = 0)
- Optics: D = 0.3 m, f/5, τ_optics = 0.75 (scalar)
- Detector: QE = 0.70 constant, pitch = 15 µm, fill = 1.0, dark = 0,
  read noise = 30 e⁻, ADC irrelevant
- Target: thermal, T = 300 K, ε = 1.0 (pure blackbody)
- Integration: 5 ms
- Regime: extended scene

Hand-compute step by step:
1. Planck radiance at 4 µm, 300 K → L [W/m²/sr/µm]
2. L_aperture = L × 1 × 1 (exo, perfect τ) = L [W/m²/sr/µm]
3. Ω = π / (4 × 25) = π/100 [sr]
4. A_pixel = (15e-6)² [m²]
5. E_fpa = L × Ω × τ_optics × 1 [W/m²/µm] (spectral)
6. At single λ, integration is just E × Δλ (for a narrow grid) OR
   use a dirac-like case
7. Photons/s = E × A_pixel × QE × λ/hc × 1 [photon/s/µm × µm]
8. Electrons = photons/s × t_int
9. Shot noise = √electrons
10. Read noise = 30
11. Total noise = √(shot² + read²)
12. SNR = electrons / total noise

Produce:
1. docs/validation/ground_truth_mwir_singlewave.md
   - Every step above with the actual numerical value computed by hand
   - Uncertainty analysis: which steps have roundoff or approximation error
2. tests/integration/test_ground_truth_mwir.py
   - Load the exact config
   - Run the chain
   - Verify each intermediate matches the hand calculation within 1e-4
3. examples/ground_truth_mwir.yaml
   - The exact config

This test is the reference. Any future change that breaks it is a
physics-relevant change that requires explicit documentation and
golden-value updates.

Report format: Category C with FULL step-by-step hand calculation
visible in the report. Do NOT just say "agrees with hand calculation" —
show the actual numbers.
```

**CHECKPOINT 2B:**

1. Run full test suite, verify all pass including ground truth.
2. Run CLI example and inspect numerical output — does it make physical
   sense for MWIR, 300 K, 300 mm aperture?
3. **Reviewer pass:** Full adversarial review of all 2B deliverables.
4. Fix any CRITICAL/HIGH findings before 2C.
5. Ground truth test must pass at this checkpoint and at every future
   checkpoint. If it ever fails, stop and investigate.

---

# PHASE 2C — SPATIAL MODEL (7 prompts)

The spatial model has the strictest invariant requirements because
MTF, EE, and PSF must all agree.

## Prompt 2C.1 — Diffraction engine

```
Task: Pupil function and FFT-based PSF computation.
Category: C (physics with numerical subtleties)

Read first:
- docs/RADIANT_Spatial_Complete.md (diffraction and sampling sections)

Produce:
1. src/radiant/optics/sampling.py  (PSF sampling configuration:
   pupil grid, focal-plane oversample, FFT sizing helpers)
2. src/radiant/optics/diffraction.py  (pupil function + circular
   aperture diffraction PSF/OTF — may already exist as a stub per
   file tree; extend it here)
3. src/radiant/optics/psf.py  (PSF container and PSF→OTF transform,
   per file tree)
4. src/radiant/optics/tests/test_sampling.py
5. src/radiant/optics/tests/test_diffraction.py
6. src/radiant/optics/tests/test_psf.py

Validation requirements (C):

Numerical truth anchors:
1. Analytical: Airy pattern for circular aperture
   - Peak at origin
   - First zero at r = 1.22 × λ × f/D
   - FWHM = 1.028 × λ × f/D
   Verify all three to within 0.5% for aperture sampled at 512 points
2. Published: Strehl ratio = 1.0 for unaberrated pupil
   - Strehl = exp(-(2π × WFE_rms / λ)²) for small WFE
   - Verify at WFE = 0 (Strehl = 1) and WFE = λ/14 (Strehl ≈ 0.80)
3. Independent: compare to scipy.special.jn (Bessel) for analytical Airy:
   I(r) = [2 × J1(π r / r_airy) / (π r / r_airy)]²
   Verify your numerical PSF matches within interpolation error

Dimensional audit:
- Pupil grid sample spacing [m]
- Focal plane sample spacing [µm]
- FFT relation: Δx_focal = λ × f / (N × Δx_pupil)
  Verify this relation holds in your implementation

Failure modes:
- Pupil undersampled (grid too coarse): PSF has aliasing artifacts
  Detection: warn user
- Focal plane undersampled (psf_oversample too low): MTF has aliasing
  Detection: warn user
- Zero aperture: PSF is delta or error
- Negative obscuration ratio: error
- WFE larger than physically reasonable (> λ): warn

Assumptions:
- Scalar diffraction (polarization ignored)
- Paraxial approximation (valid for f/# > 2)
- Spatially coherent pupil (OK for imaging with extended sources)

Fragility:
- FFT aliasing if sampling insufficient
- Log-scale PSF dynamic range: cap at 1e-10 to avoid log(0)

Cross-model consistency:
- Computed PSF integrates to total pupil energy (Parseval)
- PSF at focal plane matches analytical Airy for simple cases

Self-review.

Report format: Category C (full).

Deliverable: save Airy pattern plot to
src/radiant/optics/tests/artifacts/ with analytical overlay for
visual verification.
```

## Prompt 2C.2 — Detector PSF effects

```
Task: Pixel aperture and charge diffusion kernels.
Category: C

Read first:
- docs/RADIANT_Spatial_Complete.md (detector integration section)

Produce:
1. src/radiant/detector/diffusion.py  (Gaussian charge-diffusion MTF)
2. src/radiant/detector/ipc.py  (inter-pixel capacitance MTF)
3. src/radiant/platform/sampling.py  (pixel-aperture / rect MTF)
4. src/radiant/detector/tests/test_diffusion.py
5. src/radiant/detector/tests/test_ipc.py
6. src/radiant/platform/tests/test_sampling.py

Validation requirements (C):

Numerical truth anchors:
1. Pixel aperture MTF: analytical sinc(π × f × pitch) per axis
   Verify numerical FFT matches within 0.1%
2. Charge diffusion MTF: exp(-2 × (π × σ × f)²) for Gaussian kernel
   Verify analytical vs numerical within 0.1%
3. Independent: kernel total energy = 1 (verifies proper normalization)

Dimensional audit: kernel sample spacing matches PSF sample spacing.

Failure modes:
- Pixel pitch smaller than sample spacing (oversampled): kernel is
  a few-cell box
- Pixel pitch much larger than PSF grid: kernel exceeds grid (error or
  auto-resize)
- Zero charge diffusion σ: kernel is delta

Cross-model consistency:
- Convolution in real space ≡ multiplication in Fourier space
- Verify explicitly: real-space convolved PSF vs IFFT(MTF × OTF) match

Report format: Category C.
```

## Prompt 2C.3 — Motion kernels

```
Task: Smear, jitter, TDI, and turbulence kernels.
Category: C

Read first:
- docs/RADIANT_Spatial_Complete.md (motion section)

Produce:
1. src/radiant/platform/smear.py  (platform, scan, target smear MTF)
2. src/radiant/platform/jitter.py  (scalar + anisotropic jitter MTF)
3. src/radiant/readout/tdi.py  (TDI in the readout stage per file
   tree — TDI is a readout-architecture concern, not a motion term)
4. src/radiant/atmosphere/turbulence.py  (Kolmogorov stub — lives in
   atmosphere/ per file tree)
5. Tests co-located under each stage's tests/ directory.

Validation requirements (C):

Numerical truth anchors:
1. Smear: MTF = |sinc(π × f × smear_width)|
   Verify at several smear widths
2. Jitter: MTF = exp(-2 × (π × σ × f)²)
   Verify σ by measuring 1/e half-width of Gaussian kernel
3. Independent: each kernel integrates to 1 (energy-preserving)

Failure modes:
- Zero motion → delta kernel
- Motion larger than grid → kernel exceeds grid (error or auto-resize)
- Anisotropic jitter with σ_x = 0: degenerate to 1D
- Target motion with tracking enabled: should be cancelled out

Cross-model consistency:
- Smear kernel rotated 90° should match cross-track smear implementation
- Isotropic jitter should equal anisotropic with σ_x = σ_y

Report format: Category C.
```

## Prompt 2C.4 — EffectivePSF (the critical class)

```
Task: Implement EffectivePSF with mandatory mathematical invariants.
Category: C (most critical physics task in Phase 2)

Read first CAREFULLY:
- docs/RADIANT_Spatial_Complete.md (EffectivePSF section)

Single-source-of-truth principle: MTF, EE, LSF, ERF, RER MUST ALL be
derived from the same PSF data. NEVER compute any of these independently.

Produce:
1. src/radiant/optics/psf.py  (extend the PSF container from 2C.1
   with EffectivePSF — the single source of truth for MTF, EE, LSF,
   ERF, RER. Per CLAUDE.md Rule 4 and the file tree, this lives in
   optics/.)
2. src/radiant/optics/ee_box.py  (EE_box computation from the
   EffectivePSF — per file tree)
3. src/radiant/optics/tests/test_psf.py  (extend with EffectivePSF
   invariants 1–9 below)
4. src/radiant/optics/tests/test_ee_box.py

MANDATORY INVARIANTS (tests must explicitly check these):

Invariant 1: Energy conservation
  ∑ PSF.data = 1.0 (within 1e-10)

Invariant 2: MTF(0) = 1
  (the DC component of a unit-energy PSF is 1)

Invariant 3: Parseval's theorem
  ∑|PSF|² = ∑|FFT(PSF)|² / N²
  Verify to 1e-10

Invariant 4: Convolution order independence
  build_effective_psf([A, B, C]) should equal build_effective_psf([C, B, A])
  (convolution is commutative)
  Verify to 1e-10

Invariant 5: EE monotonicity
  EE(box_size) must be monotonically non-decreasing
  EE(full_grid) = 1.0

Invariant 6: MTF budget consistency (THE critical check)
  MTF_from_FFT = mtf_2d() of the EffectivePSF
  MTF_from_budget = product of individual kernel MTFs
  max |MTF_from_FFT - MTF_from_budget| < 1e-3 (0.1%)
  This must be explicitly tested and reported.

Invariant 7: Strehl = 1 for unaberrated, no motion
  Strehl(diffraction only) = 1.0 within numerical error

Invariant 8: FWHM monotonic in degradations
  FWHM(diffraction) < FWHM(diffraction + detector) < FWHM(+ motion)

Invariant 9: RER decreases with degradation
  RER(ideal) > RER(realistic)

Stability sweep:
- Vary psf_oversample from 2 to 8
- Metrics (FWHM, EE_peak, MTF@Nyquist) should converge as oversample
  increases, with changes < 1% between oversample=4 and oversample=8
- If not converged at oversample=4, flag as under-sampled

Failure modes:
- Kernels with different sample spacing (error)
- Grid too small for PSF wings (warn)
- Zero kernel (identity, should work)
- Conflicting motion specifications (error)

Cross-model consistency:
- Compare full build (diff + det + motion) vs skipping one component —
  difference should match the skipped component's contribution exactly

Self-review: PARTICULARLY rigorous for this class. Re-read the
single-source-of-truth principle and verify NO code path computes
MTF or EE from anything other than the EffectivePSF.data array.

Report format: Category C (full), with each invariant reported
numerically with its worst-case error observed.
```

## Prompt 2C.5 — Spatial metrics and NIIRS

```
Task: GSD, IFOV, Nyquist, NIIRS.
Category: C

Read first:
- docs/RADIANT_Metrics.md (spatial and NIIRS)
- docs/RADIANT_Metric_Dependencies.md (NIIRS tree)

Produce:
1. src/radiant/platform/geometry.py  (GSD, IFOV, slant range, look
   angle helpers — per file tree, these live in platform/)
2. src/radiant/performance/system_mtf.py  (system MTF / Nyquist
   reporting — per file tree, metrics live in performance/)
3. src/radiant/performance/niirs.py  (NIIRS dispatcher)
   src/radiant/performance/giqe.py  (GIQE5)
   src/radiant/performance/iirs.py  (IIRS)
4. Tests co-located under each stage's tests/ directory.

Validation requirements (C):

Numerical truth anchors:
1. GSD = pitch × altitude / focal_length (trivial, verify at known values)
2. IFOV = pitch / focal_length (trivial, verify)
3. NIIRS from published GIQE-5 test cases (at least 3 from literature)

Failure modes:
- Zero focal length: error
- GIQE inputs out of model validity range: warn
- Negative SNR: error

Cross-model consistency: GSD and IFOV are redundant representations
of the same quantity, they should be consistent.

Report format: Category C.
```

## Prompt 2C.6 — Spatial integration with chain

```
Task: Integrate spatial model into chain.
Category: D (integration)

Read first:
- docs/RADIANT_Signal_Chain_Architecture.md

Produce:
1. Updated src/radiant/api/session.py  (ChainRunner now composes the
   spatial stages — optics PSF → platform motion → detector MTF)
2. Updated src/radiant/io/results.py  (RadiantResult gains spatial
   fields: effective_psf, system_mtf, EE, FWHM, etc.)
3. Updated examples/mwir_leo_minimal.yaml
4. Updated tests/integration/golden/mwir_leo_minimal.json  (spatial
   metrics appended with provenance comments)
5. tests/integration/test_chain_extended_with_spatial.py

Regression requirement:
- Ground truth test from 2B.9 must still pass
- All 2B golden tests must still pass (spatial addition should not
  affect non-spatial values)
- New golden values for spatial metrics with provenance comments

Report format: Category D with explicit regression results.
```

## Prompt 2C.7 — Spatial subsystem audit

```
Task: Comprehensive validation of the spatial subsystem.
Category: D (validation, no new features)

Produce a diagnostic script:
scripts/spatial_audit.py  (top-level scripts/ directory, same
location as scripts/update_golden.py from 2B.8)

For a reference configuration, print:
- Every MTF component at Nyquist
- Every EE value (1×1, 3×3, 5×5, vs offset)
- FWHM in both axes
- RER, Strehl, NIIRS
- Sampling configuration used
- Numerical verification of all 9 invariants
- Budget MTF vs EffectivePSF MTF (max difference)

Add tests to bring any file below 85% coverage up to 85%.

Report: coverage delta, diagnostic output, invariant check results.
```

**CHECKPOINT 2C:**

1. Human reviews PSF plots, runs spatial audit, checks numbers.
2. Ground truth test still passing.
3. **Reviewer pass:** Full adversarial review of 2C.
4. Particular focus: does any code path violate the single-source-of-truth
   principle for the PSF?
5. Fix findings before 2D.

---

# PHASE 2D — FULL SIGNAL CHAIN (10 prompts)

Same validation framework as previous phases. All physics prompts
are Category C.

## Prompt 2D.1 — Complete source system

```
Task: All remaining source types.
Category: C

Read first:
- docs/RADIANT_Source_Target_System.md (complete)

Produce:
1. src/radiant/source/reflected.py  (BRDF-weighted reflected solar)
2. src/radiant/source/combined.py  (Kirchhoff-consistent
   CombinedSource — new file within source/)
3. src/radiant/source/sub_pixel.py  (sub-pixel regime source — new)
4. src/radiant/source/point_source.py  (point-source intensity
   variants — new)
5. src/radiant/source/background.py  (extended / clutter backgrounds)
6. src/radiant/source/tabulated.py  (escape-hatch L(λ) — new)
7. src/radiant/source/brdf.py  (Lambertian, Phong — new)
8. src/radiant/source/solar.py  (ASTM G-173)
9. Tests co-located under src/radiant/source/tests/

Validation requirements (C):

Numerical truth anchors per source:
- ReflectedSolarSource: for Lambertian surface with ρ = 0.5 at noon,
  compare to hand calculation
- CombinedSource: Kirchhoff consistency (ε + ρ = 1 for opaque), verify
  at several wavelengths
- SubPixelSource: at ff = 1, should equal extended scene; at ff → 0,
  should approach background
- PointSource: check 1/R² scaling by computing at two ranges
- BRDF Lambertian: ∫BRDF × cos(θ) dΩ = ρ (energy conservation)
- BRDF Phong: verify specular peak at reflection angle

Failure modes:
- Negative reflectance (error)
- Reflectance + emissivity > 1 (error)
- Solar zenith > 90° (sun below horizon, return 0)
- Sub-pixel with ff > 1 (clip or error)
- Point source at R = 0 (error)

Cross-model consistency:
- SubPixelSource at ff = 1 produces same result as ThermalSource directly
  (verify to 1e-6 for a matched case)
- CombinedSource with ε = 1, solar off = ThermalSource
- CombinedSource with ε = 0, thermal off = ReflectedSolarSource

Report format: Category C.
```

## Prompt 2D.2 — Target geometry and unified resolver

```
Task: Target geometry, materials, unified target resolver.
Category: C

Read first:
- docs/RADIANT_Source_Target_System.md (geometry and unified sections)

Produce:
1. src/radiant/source/shape.py  (target shape protocol — new file
   within source/, not a separate target_geometry subpackage)
2. src/radiant/source/primitives.py  (sphere, cylinder, box, flat
   plate, cone — new)
3. src/radiant/source/composite.py  (composite target — new)
4. src/radiant/source/material.py  (SurfaceMaterial — per
   RADIANT_Source_Target_System.md §4)
5. src/radiant/source/unified_target.py  (unified ResolvedTarget
   resolver — new file within source/)

Validation requirements (C):

Numerical truth anchors:
1. Analytical projected areas:
   - Sphere: π r² (orientation-independent)
   - Box: L×W for broadside, L×H for front-on (depends on orientation)
   - Cylinder broadside: 2 r × L
   - Flat plate normal: L × W; edge-on: 0
2. Published: projected area formulas from any standard geometry reference
3. Independent: Monte Carlo estimate via random ray intersection
   (for complex orientations)

Failure modes:
- Negative dimensions (error)
- Orientation with NaN (error)
- Composite with self-intersecting primitives (undefined but shouldn't crash)

Cross-model consistency:
- Composite of a single sphere = bare sphere
- Unified resolver: all 5 input paths for the same target produce
  identical ResolvedTarget (within physics-relevant precision)

Report format: Category C with a table of projected areas for each
primitive at 0°, 30°, 45°, 60°, 90° orientations, hand-verified.
```

## Prompt 2D.3 — Point source and sub-pixel chains

```
Task: Implement remaining regime chains.
Category: C

Read first:
- docs/RADIANT_Signal_Chain_Architecture.md (three regimes section)

Produce:
1. Updated src/radiant/source/stage.py  (SourceStage gains point-
   source and sub-pixel tentative-regime classification per
   Signal_Chain_Architecture §6)
2. Updated src/radiant/spectral_integration/stage.py  (EE_box
   coupling for point-source + sub-pixel regimes per Rule 9)
3. Updated src/radiant/api/session.py  (ChainRunner dispatch across
   regimes — regime is read from state.stage_outputs["optics"]["regime"]
   per Rule 10)
4. Tests co-located under each stage's tests/; regime-continuity
   integration test at tests/integration/test_regime_continuity.py

Validation requirements (C):

Numerical truth anchors:
1. Point source SNR scales as 1/R² (double range, quarter signal)
2. Sub-pixel contrast ΔL computation: hand-verify for T_target=400K,
   T_bg=300K at 4 µm
3. Ground truth ground-truth case for point source: satellite-like
   intensity source at known range, known aperture, hand-verify

REGIME CONTINUITY (critical new test):

At boundaries between regimes, the chains should match (or match
after a documented step):
- At ff = 1.0: sub-pixel chain = extended chain (verify within 0.1%)
- At ff = 0.01: sub-pixel chain approaches point source chain × ff
  (but not exactly — document the difference)
- Point source with angular extent → pixel IFOV: should match
  extended chain result for the same source

Failure modes:
- ff > 1 in sub-pixel: error or clip
- Range = 0 in point source: error
- Regime dispatch ambiguity: document tie-breaking rule

Cross-model consistency: extended chain should reproduce the 2B.9
ground truth case identically.

Report format: Category C with regime continuity table.
```

## Prompts 2D.4 through 2D.10

For brevity, prompts 2D.4 through 2D.10 follow the same pattern as
the unenhanced version but with:

- Category C designation (physics) or D (integration)
- Mandatory truth anchors for any physics
- Dimensional audits
- Failure modes
- Cross-model consistency checks
- Self-review

The specific technical content is unchanged from the previous version.
Refer to `RADIANT_Phase2_Implementation_Prompts_Clean.md` for 2D.4
through 2D.10 and apply the validation framework above to each.

Key additions to flag:

**2D.6 (Complete detector with all noise sources):**
- Each noise source isolated: enable only that source, verify value
- Combined total = RSS of individual sources (verify)
- Dominant noise regime check: in BLIP regime, shot noise dominates;
  in read-limited regime, read noise dominates
- Noise budget table with fractional contributions

**2D.7 (Remaining metrics):**
- NEΔT should be inverse-proportional to sqrt(signal electrons) in BLIP
- NIIRS should decrease with larger GSD (verify)
- Detection range should follow 1/R² relationship (verify sensitivity)

**2D.8 (Backward propagation):**
- Round-trip invariance: forward then backward = identity (to 1e-10)
- Unit consistency at every frame conversion
- Band-integrated and spectral representations consistent for
  band-flat sources

**2D.9 (Sweeps and tolerance):**
- Sensitivity sanity checks:
  * Aperture ↑ → SNR ↑ (monotonic)
  * Integration time ↑ → SNR ↑ (sqrt relationship in shot-noise regime)
  * Dark current ↑ → SNR ↓
  * Read noise ↑ → SNR ↓
- Any violation is a bug

**CHECKPOINT 2D:**

- Full reviewer pass (this is the biggest review — 10 prompts worth)
- Ground truth test still passing
- Regime continuity tests passing
- Sensitivity sanity checks passing
- Noise budget physically reasonable for each reference scenario

---

# PHASE 2E — UX AND POLISH (6 prompts)

Same pattern. Category D throughout. Focus on regression safety and
documentation validation.

## Additional requirements for Phase 2E

**Prompt 2E.4 (Documentation):**

Code-in-docs test is mandatory:
```
tests/integration/test_docs_code_blocks.py
- Extract every python code block from docs/guides/*.md
- Execute each
- Verify no errors, verify any asserted values hold
```

**Prompt 2E.6 (Release prep):**

Output versioning:
```
Every ChainResult must include:
- config_hash: SHA256 of the resolved config
- code_version: radiant.__version__
- timestamp: ISO 8601
- dependency_versions: {numpy: ..., scipy: ..., ...}
```

Performance budgets:
```
Define and verify:
- Draft fidelity eval: < 1 second mean, < 2 seconds P95
- Standard fidelity: < 5 seconds mean
- Publication fidelity: < 30 seconds mean
- 1000-point sweep (draft): < 60 seconds
Report actual vs budget. If over budget, identify bottleneck and
decide: optimize now, or document and defer.
```

---

# GLOBAL OPERATING PRINCIPLES

These apply to every prompt, every task, every conversation.

1. **One task per conversation.** Never combine.
2. **Read first is mandatory.** No exceptions.
3. **Category determines rigor.** Category A/B/C/D maps to required
   validation sections. Don't cut corners on Category C.
4. **Numerical truth anchors require independence.** Your own function
   is NOT an independent check. A different library, analytical limit,
   or hand calculation IS.
5. **Tests that would pass a stub fail the review.** Tests must actually
   exercise the claim being tested.
6. **Golden values have provenance comments.** No unexplained magic numbers.
7. **Regression is sacred.** Ground truth test from 2B.9 must pass at
   every future checkpoint. If it fails, stop.
8. **Architecture violations are stop-the-line.** Ask the human, don't guess.
9. **Scope is hard.** "While I'm here" features are their own task.
10. **Self-review before declaring done.** Answer the 4-section checklist
    in writing.
11. **Reviewer pass at sub-phase boundaries.** Adversarial review catches
    what self-review missed.

---

# FINAL COMPLETION CRITERIA

A prompt is NOT complete until:

- ✅ All code files created
- ✅ All tests passing
- ✅ Required validation sections present in report (per category)
- ✅ All numerical truth anchors documented with expected/actual/error
- ✅ Dimensional audit table present (Category B/C)
- ✅ Failure modes tested (Category B/C)
- ✅ Self-review checklist answered in writing
- ✅ Structured report produced in the standard format
- ✅ No CRITICAL findings from adversarial review (Category C at checkpoints)
- ✅ Ground truth test still passes (from 2B.9 onward)
- ✅ Regression tests pass

Partial completion is not complete.

---

# DEFERRED WORK CARRIED FORWARD (logged 2026-04-09)

This section records work that was scoped out of the prompts above
during execution and must be picked up by a later prompt. Each entry
names the originating prompt, what shipped, what was deferred, and
which prompt must absorb the deferred work.

## From Prompts 2B.1–2B.4 → must land in **Prompt 2B.5 (Chain skeleton)**

Prompts 2B.1 through 2B.4 shipped physics primitives (`ThermalSource`,
`SimpleAtmosphere` / `ExoAtmosphere`, `ScalarTelescope`, and the
detector primitives `qe.py` / `pixel.py` / `shot_noise.py` /
`dark_current.py` / `readout/read_noise.py` / `readout/adc.py`) but did
**not** ship stage wrappers, because `radiant.core.chain` did not yet
exist. See `notes/blocked.md` 2026-04-08 — DetectorStage / Stage
protocol — DEFERRED.

Prompt 2B.5 must therefore land the chain scaffold **and** the stage
wrappers in this order:

1. `radiant.core.chain` — `Stage` Protocol, frozen `ChainState` with
   `with_frame` / `with_noise` / `with_mtf` / `with_stage_output`
   helpers (CLAUDE.md Rule 7), `ChainRunner`.
2. `radiant.core.radiometry` — `RadiometricFrame`, `NoiseTerm`.
3. Stage wrappers over the existing primitives, in order:
   - `src/radiant/source/stage.py` over `ThermalSource` etc.
   - `src/radiant/atmosphere/stage.py` over
     `SimpleAtmosphere` / `ExoAtmosphere`.
   - `src/radiant/optics/stage.py` — owns regime finalisation
     (CLAUDE.md Rule 10).
   - `src/radiant/detector/stage.py` over `qe` / `pixel` / `shot_noise`
     / `dark_current` (+ `mtf_terms` registration).
   - `src/radiant/readout/stage.py` over `read_noise` / `adc`.
4. Wire each stage's existing `_schema.py` into the `ChainRunner`
   stage registration.

## From Prompt 2B.4 → enforced inside **Prompt 2B.5 detector wrapper**

`detector.qe_value` (scalar) and `detector.qe_table_path` (str) were
added to `src/radiant/detector/_schema.py` as the only two QE input
modes (Blocker 4 resolution, see `notes/blocked.md` 2026-04-08). Both
default to `None`. The detector stage wrapper added in 2B.5 must
enforce the XOR (exactly one set) via a `ConsistencyGroup` and dispatch
to either `QuantumEfficiency.constant(value)` or
`QuantumEfficiency.from_spectral(SpectralDataStore.load(path))`.

---

# EFFORT ESTIMATE (Validated Version)

The additional validation adds overhead but catches bugs early.
Estimate vs the unvalidated version:

| Phase | Unvalidated | Validated |
|-------|------------|-----------|
| 2A | 8-12 hours | 10-14 hours |
| 2B | 14-18 hours | 18-24 hours |
| 2C | 11-16 hours | 16-22 hours |
| 2D | 22-30 hours | 28-38 hours |
| 2E | 14-18 hours | 16-22 hours |
| **Total** | **69-94 hours** | **88-120 hours** |

The validated version takes ~25% more effort but produces code that
is significantly more defensible. For a physics-critical tool like
RADIANT, this is the right tradeoff — discovering a sign error in
Phase 2B during validation is ~10× cheaper than discovering it in
Phase 2D integration testing, and ~100× cheaper than discovering
it in a user's published paper.

The time you spend validating is time you don't spend debugging
mysterious numerical drift later.

---

# CLOSING NOTE

Two metaphors for the difference this framework makes:

**Without validation framework:** building a house and checking at the
end whether it's plumb. By then, fixing requires tearing walls down.

**With validation framework:** checking plumb at every floor as you
build. Slower per floor, much faster overall, and the house is
actually plumb.

For RADIANT, "plumb" is "the physics is right." You will not know
the physics is right unless you check at every step, against
independent references, with structured reporting. That's what this
framework enforces.
