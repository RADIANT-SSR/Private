# Target Definition Matrix — Implementation Plan

**Date**: 2026-04-21
**Audit input**: [`Target_Definition_gaps.md`](Target_Definition_gaps.md) (all 14 claims verified 2026-04-21)
**Spec input**: [`RADIANT_Target_Definition_Matrix.md`](RADIANT_Target_Definition_Matrix.md)
**Q-resolutions this plan delivers**: Q1 (S11/S12 first-class), Q3 (shape wins over `projected_area_m2`), Q4 (`ReflectanceDescriptor` stub)

---

## Execution Rules (apply to every step)

1. **One step = one conversation.** Do not combine steps. Do not implement features from future steps.
2. **Every step is either Category B or C** (Core Abstractions or Physics). Report per [`CLAUDE.md`](../CLAUDE.md) §"Structured Report Template".
3. **Regression gate is MANDATORY before declaring a step complete.** The exact commands are listed at the top of each step. If any regression fails, stop — fix or escalate before continuing.
4. **New tests are MANDATORY in the same commit as the implementation.** No "tests to follow." A step is incomplete without its test file landed and passing.
5. **No golden-value changes** unless a step explicitly authorizes it. If a golden drifts unexpectedly, stop and investigate — do not "update to make it pass."
6. **Every step ends by re-running the full regression suite** and pasting results into the structured report.

### Standing regression command set

```
pytest src/ -v -m "not golden"                               # fast suite, all stages
pytest tests/integration/ -v                                  # 90-cell matrix + warnings + Table C
pytest tests/integration/test_use_case_matrix.py -v           # matrix coverage (80 pass / 10 raise)
pytest tests/integration/test_use_case_warnings.py -v         # 19 warning-path tests
mypy --strict src/radiant/core src/radiant/api                 # type gate
import-linter --config pyproject.toml                         # import rules
ruff check src/                                                # lint gate
```

All six commands must exit zero at the end of every step. This is the regression gate.

---

## Phase Map

| Phase | Scope | Priority | Category | Estimated days |
|-------|-------|----------|----------|----------------|
| 1 | Shape wiring (Q3) | P0 | C | 2–3 |
| 2 | S11/S12 boundary converters (Q1) | P0 | C | 1–2 |
| 3 | S4/S5/S6 reflective user-input paths | P1 | C | 1–2 |
| 4 | S8 user-radiance-at-source escape hatch | P1 | B |  ≤1 |
| 5 | S10 user-intensity point-source escape hatch | P1 | B |  ≤1 |
| 6 | `ReflectanceDescriptor` stub base (Q4) | P2 | B | 1–2 |
| 7 | Matrix coverage harness extension (S4–S12) | P0 | D | 1 |

Phases 1, 2, 7 are release-critical. 3–6 are scoped additions that each stand alone.

---

## Phase 1 — Shape Wiring (Q3)

**Goal**: When a scenario YAML specifies a shape (sphere, cylinder, flat_plate, box, cone), the source stage constructs a concrete `TargetShape` instance, wires it into descriptor construction, and uses `shape.projected_area(view_direction)` for sub-pixel projected area. When a user supplies both `shape` and `projected_area_m2`, `shape` wins and a `UserWarning` fires (Rule 17).

**Read first**:
- [`docs/RADIANT_Target_Definition_Matrix.md`](RADIANT_Target_Definition_Matrix.md) §3 (shape catalog)
- [`src/radiant/source/shape.py`](../src/radiant/source/shape.py) (protocol)
- [`src/radiant/source/shapes/`](../src/radiant/source/shapes/) (concretions)
- [`src/radiant/source/resolvers/geometry.py`](../src/radiant/source/resolvers/geometry.py) (existing `shape.projected_area` call at line 68)
- [`src/radiant/source/_inferrer.py`](../src/radiant/source/_inferrer.py) (specifically the `shape=None` hardcode around line 337)
- [`src/radiant/source/_schema.py`](../src/radiant/source/_schema.py)
- `CLAUDE.md` Rules 2, 12, 15, 17, 19

### Step 1.1 — Shape schema parameters

**Category**: B — Core Abstractions

**Prompt to paste**:
```
Category B task: add shape-selection parameters to the source schema.

Read first: docs/RADIANT_Target_Definition_Matrix.md §3, src/radiant/source/_schema.py,
src/radiant/source/shape.py, src/radiant/source/shapes/.

Scope — modify only:
  - src/radiant/source/_schema.py
  - src/radiant/source/tests/test_schema.py (add cases)

Add these ParameterDefs (follow existing schema style):
  - source.target.shape: str | None, default None, enum {"sphere","cylinder",
    "flat_plate","box","cone"}. Lowercase. Validate against enum in schema.
  - source.target.shape_params: dict | None, default None. Free-form dict whose
    expected keys depend on shape (sphere: radius_m; cylinder: radius_m,length_m;
    flat_plate: width_m,height_m,normal; box: length_m,width_m,height_m;
    cone: radius_m,height_m). DO NOT validate contents here — validation belongs
    in the resolver (Step 1.2). Schema only checks type == dict.

Do NOT wire these into the inferrer in this step. This step only registers
the parameters so the YAML loader accepts them.

Regression gate (must all pass):
  pytest src/ -v -m "not golden"
  pytest tests/integration/ -v
  mypy --strict src/radiant/core src/radiant/api
  import-linter --config pyproject.toml
  ruff check src/

New tests (MANDATORY in this commit):
  - test_schema accepts shape="sphere" with shape_params={"radius_m": 1.0}
  - test_schema rejects shape="pyramid" (not in enum)
  - test_schema accepts shape=None (default)
  - test_schema rejects shape_params when not a dict

Report per CLAUDE.md Category B template. Include dimensional audit for
shape_params keys (all lengths → m, angles → rad).
```

### Step 1.2 — Shape resolver and `_inferrer` wiring (with conflict warning)

**Category**: C — Physics Implementation

**Prompt to paste**:
```
Category C task: wire the source.target.shape schema into descriptor construction
and enforce Q3 resolution (shape wins over projected_area_m2 with a warning).

Read first: src/radiant/source/shape.py, src/radiant/source/shapes/,
src/radiant/source/resolvers/geometry.py (line 68 uses projected_area already),
src/radiant/source/_inferrer.py (find the shape=None hardcode around line 337),
docs/RADIANT_Target_Definition_Matrix.md §3, §4 Q3 resolution.

Scope — modify only:
  - src/radiant/source/_inferrer.py (shape wiring at descriptor construction)
  - src/radiant/source/resolvers/shape_factory.py (NEW FILE — Rule 19: one
    computation per module; this file ONLY builds TargetShape instances from
    (shape_str, shape_params_dict))
  - src/radiant/core/descriptors.py ONLY IF T1/T2/T3 don't already accept a
    shape field. If they do, leave descriptors alone.
  - src/radiant/source/tests/test_inferrer_shape.py (NEW TEST FILE)

Implementation:
  1. In resolvers/shape_factory.py, write build_shape(shape: str | None,
     params: dict | None) -> TargetShape | None. Dispatch on the enum,
     construct the concrete shape, validate its params (radius_m > 0, etc.)
     via ParameterBoundsError (Rule 15). Return None when shape is None.

  2. In _inferrer.py, after the user parameters are loaded and BEFORE the
     T1/T2/T3 descriptor is constructed:
     - Call build_shape(...) once.
     - If a shape is built AND projected_area_m2 is also user-set (>0), compute
       A_shape = shape.projected_area(view_direction) and emit:
         warnings.warn(f"Both shape={shape_name} and projected_area_m2="
                       f"{user_val} supplied; shape wins (A_projected={A_shape} m²).",
                       UserWarning)
     - Use A_shape when shape is non-None; fall back to projected_area_m2
       otherwise (back-compat).
     - Attach the TargetShape instance to the descriptor's shape field (descriptors
       already carry shape: TargetShape | None — check first; if they only carry
       shape: str | None change it to Optional[TargetShape]).

  3. view_direction for shape.projected_area: use the observer→target line-of-sight
     unit vector from LineOfSightGeometry. Do NOT hardcode +Z boresight — pull
     from state/params consistently with Rule 3.

Regression gate (must all pass):
  pytest src/ -v -m "not golden"
  pytest tests/integration/ -v
  pytest tests/integration/test_use_case_matrix.py -v  (80/10 baseline — must not drift)
  mypy --strict src/radiant/core src/radiant/api
  import-linter --config pyproject.toml
  ruff check src/

New tests (MANDATORY):
  test_inferrer_shape.py — at minimum:
    1. shape="sphere" with radius=1m → descriptor.shape is a Sphere, projected
       area is πr² when viewed along +Z (truth anchor: analytic).
    2. shape="cylinder" radius=1m length=10m, view normal to axis → projected
       area is 2rL=20 m² (analytic truth anchor).
    3. shape="flat_plate" oriented with normal parallel to view → projected
       area is W*H. Normal perpendicular → 0.
    4. shape + projected_area_m2 conflict → exactly ONE UserWarning fires with
       match=r"shape.*wins"; use pytest.warns.
    5. shape=None, projected_area_m2=5.0 → no warning, A_proj=5.0 (back-compat).
    6. shape="sphere" with radius=-1 → ParameterBoundsError (not ValueError).

Numerical truth anchors (Category C §1):
  - Anchor 1: Sphere projected area = πr² (closed-form).
  - Anchor 2: Cylinder (side view) = 2rL (closed-form).
  - Anchor 3: Flat plate (normal view) = WH; (edge view) = 0 (closed-form).

Dimensional audit table MANDATORY. Fragility analysis: what happens when
view_direction is zero vector? Shape radii at 0? Flat plate normal not unit?

Report per CLAUDE.md Category C template. Include the three truth anchors
with actual vs. expected values.
```

### Step 1.3 — Use-case matrix coverage for shape-driven sub_pixel cells

**Category**: D — Integration and UX

**Prompt to paste**:
```
Category D task: extend the 90-cell use-case coverage harness to exercise
shape-driven sub_pixel targets.

Read first: tests/integration/test_use_case_matrix.py, tests/integration/test_use_case_warnings.py,
docs/RADIANT_Target_Definition_Matrix.md §3.

Scope — modify only:
  - tests/integration/test_use_case_shapes.py (NEW FILE — do NOT edit
    test_use_case_matrix.py in place; follow the same pattern as
    test_use_case_warnings.py which is a sibling test file)

New tests (MANDATORY):
  For each shape in {sphere, cylinder, flat_plate, box, cone}, parametrize
  across a representative sub_pixel cell from each scene type family:
    - Terrestrial sub_pixel LWIR (Cell 29 analog)
    - Airborne sub_pixel MWIR (Cell 44 analog)
    - Space sub_pixel VIS (Cell 59 analog)

  For each (shape, cell) combination, assert:
    1. session.run(params) completes (no raise).
    2. result.observed_signal_DN > 0 (sanity).
    3. The descriptor's shape attribute is the expected concrete type.
    4. SNR is finite.

  Plus a negative-path test: shape="sphere" + target_location="at_aperture"
  → ParameterBoundsError (shape is not compatible with S9).

Regression gate:
  pytest src/ -v -m "not golden"
  pytest tests/integration/ -v          (must be full green)
  pytest tests/integration/test_use_case_matrix.py -v   (80/10 unchanged)
  mypy --strict src/radiant/core src/radiant/api
  import-linter --config pyproject.toml
  ruff check src/

Regression check (Category D §8): confirm no golden results in
src/radiant/source/tests/snapshots/ changed. If any did, STOP and report.

Report per Category D template.
```

---

## Phase 2 — S11/S12 Boundary Converters (Q1)

**Goal**: Users can specify targets in brightness temperature `T_B(λ)` (S11) or band-averaged radiance temperature `T_R` (S12). Both convert at the boundary (Rule 2) to canonical descriptors — no new descriptor variant.

**Read first**:
- [`docs/RADIANT_Target_Definition_Matrix.md`](RADIANT_Target_Definition_Matrix.md) §1 rows S11, S12
- [`src/radiant/core/constants.py`](../src/radiant/core/constants.py) (h, c, k_B)
- [`src/radiant/source/emitted.py`](../src/radiant/source/emitted.py) (Planck implementation already in-tree)
- `CLAUDE.md` Rules 2, 12, 13, 19

### Step 2.1 — S11: `brightness_temperature` converter

**Category**: C

**Prompt to paste**:
```
Category C task: add a boundary converter that turns user-supplied brightness
temperature T_B(λ) into a T1Thermal descriptor with ε ≡ 1.

Read first: src/radiant/core/constants.py, src/radiant/source/emitted.py
(for the canonical Planck formula), src/radiant/core/descriptors.py T1Thermal,
docs/RADIANT_Target_Definition_Matrix.md S11.

Scope — NEW FILE ONLY:
  - src/radiant/source/converters/brightness_temperature.py (Rule 19)
  - src/radiant/source/converters/__init__.py (NEW, if needed)
  - src/radiant/source/tests/test_brightness_temperature_converter.py (NEW)

Also add schema param:
  - src/radiant/source/_schema.py: source.target.brightness_temperature
    (SpectralData, canonical unit K, optional).

Wire into inferrer:
  - src/radiant/source/_inferrer.py: when brightness_temperature is set AND
    temperature/emissivity are not, emit a T1Thermal where:
      T_t = <user-requested effective radiance temp; use a single-value choice:
             since ε≡1, T_t is simply the mean of T_B(λ) over the chain grid>
      epsilon(λ) = 1.0 (constant SpectralData)
    Document clearly in docstring that this is the S11 lossless form when
    the user supplies T_B(λ) directly; downstream radiance L(λ) = B(λ, T_B(λ)).

    IMPORTANT: if T_B varies with λ, the single-temperature T1Thermal cannot
    exactly reproduce L(λ). The correct implementation stores L_source = B(λ, T_B(λ))
    and routes to TabulatedRadianceSource (S8 path) instead. Do this — do not
    silently average T_B. Emit a UserWarning if T_B is (near-)constant so user
    knows collapse-to-T1 could have been used.

Truth anchors (MANDATORY 3):
  - Anchor 1: T_B = 300 K flat → L(10 µm) = B(10 µm, 300 K) to within 1e-6.
  - Anchor 2: T_B(λ) varying → confirm tabulated L(λ) matches hand-computed
    Planck values at three wavelengths.
  - Anchor 3: Round-trip: descriptor → L(λ) → invert Planck → T_B(λ) matches
    within 1e-4 K.

Regression gate:
  pytest src/ -v -m "not golden"
  pytest tests/integration/ -v
  mypy --strict src/radiant/core src/radiant/api
  import-linter --config pyproject.toml
  ruff check src/

New tests (MANDATORY):
  - Constant T_B emits T1Thermal directly, ε≡1.
  - Varying T_B(λ) emits TabulatedRadianceSource; raises no silent warning
    only if T_B is actually λ-dependent (peak-to-peak > 1 K).
  - Round-trip parity to 1e-4 K.
  - Negative: T_B < 0 → ParameterBoundsError.
  - Negative: T_B > 10000 K → ParameterBoundsError.

Dimensional audit: K → W/m²/sr/µm via Planck; µm throughout.
Fragility: cancellation when T_B is below the Planck low-T tail.

Report per Category C.
```

### Step 2.2 — S12: `radiance_temperature` converter

**Category**: C

**Prompt to paste**:
```
Category C task: add a band-radiance-temperature (T_R) boundary converter.

Read first: same as Step 2.1; plus the MWIR/LWIR band definitions in
docs/RADIANT_Conventions.md if present.

Scope — NEW FILE:
  - src/radiant/source/converters/radiance_temperature.py (Rule 19)
  - src/radiant/source/tests/test_radiance_temperature_converter.py

Schema additions:
  - source.target.radiance_temperature: float, K (optional)
  - source.target.radiance_temperature_band: tuple[float, float], µm (required
    when radiance_temperature is set)

Converter contract:
  Given T_R and band (λ1, λ2):
    Solve for T_equiv such that  ∫_{band} B(λ, T_equiv) dλ = ∫_{band} L_target(λ) dλ
    where L_target is assumed to be a blackbody at T_R. In the simple case where
    the user ONLY supplies T_R and band (no ε), T_equiv = T_R exactly and we emit
    T1Thermal(T_t=T_R, ε≡1). The function's purpose is forward-compatible: the
    inversion harness is there so a future user-supplied in-band L_band can invert
    to T_equiv.

  First version: emit T1Thermal(T_t=T_R, ε(λ)≡1). Write the inversion helper
  invert_band_radiance_to_temperature(L_band, band) separately (new file,
  Rule 19) with truth anchors; do NOT wire to user input yet.

Truth anchors (MANDATORY 3):
  - Anchor 1: T_R=300 K, band=(8,12) µm → inversion of the band-integrated Planck
    recovers 300 K to 1e-3 K.
  - Anchor 2: T_R=500 K, band=(3,5) µm → same parity.
  - Anchor 3: T_R=2000 K, band=(0.7,1.0) µm → same parity (Wien regime).

Regression gate: (same six commands)

New tests (MANDATORY):
  - Constant-T_R round-trip parity in three bands.
  - Validation: radiance_temperature set without band → raise.
  - Validation: band inverted (λ2 < λ1) → raise.
  - Validation: T_R ≤ 0 → raise.

Report per Category C.
```

---

## Phase 3 — S4 / S5 / S6 Reflective User-Input Paths

**Goal**: Users can specify pure-reflective targets (`ρ(λ)` or `albedo(λ)`) directly, without going through T3Mixed (which forces ε+T and Kirchhoff inverse). Descriptor is T2Reflective.

**Read first**:
- `src/radiant/core/descriptors.py` T2Reflective (lines 369–395)
- `src/radiant/source/reflected.py`
- `src/radiant/source/_inferrer.py`
- `docs/RADIANT_Target_Definition_Matrix.md` S4/S5/S6 rows

### Step 3.1 — Reflectance schema params

**Category**: B

**Prompt to paste**:
```
Category B task: expose reflectance / albedo as first-class source params.

Scope — modify only:
  - src/radiant/source/_schema.py
  - src/radiant/source/tests/test_schema.py

Add:
  - source.target.reflectance: SpectralData | float | None, default None,
    canonical unit dimensionless [0,1]. Accepts scalar (lifts to constant
    SpectralData in _inferrer, not here).
  - source.target.albedo: alias of reflectance. If both are set, raise
    ParameterBoundsError in the schema validator.

Regression gate: all six commands.

New tests (MANDATORY):
  - Scalar reflectance=0.3 accepted.
  - Array reflectance accepted.
  - reflectance + albedo together → raise.
  - reflectance > 1 or < 0 → raise.

Report per Category B.
```

### Step 3.2 — Inferrer wiring for T2Reflective (S4/S5/S6)

**Category**: C

**Prompt to paste**:
```
Category C task: wire reflectance/albedo into inferrer so T2Reflective is
reachable from user input.

Read first: src/radiant/source/_inferrer.py, src/radiant/core/descriptors.py
T2Reflective, docs/RADIANT_Target_Definition_Matrix.md §1 S4/S5/S6 and §2
compatibility matrix (reflective-only is VIS/NIR/SWIR-only for practical
scenes; MWIR → warn via Rule 17 but do not hard-raise since Q1 hot/cold rules
already handle edge cases).

Scope — modify only:
  - src/radiant/source/_inferrer.py
  - src/radiant/source/tests/test_inferrer_reflective.py (NEW)

Inference rule:
  If reflectance/albedo is set AND temperature/emissivity are absent
  → build T2Reflective(rho=<SpectralData>). Illumination path is the normal
    solar/ambient chain (already wired via T2Reflective).
  If reflectance AND temperature are BOTH set → raise (over-specified; user
  should use T3Mixed path via emissivity only).

Truth anchors (3 MANDATORY):
  - Anchor 1: Scalar ρ=0.5, solar VIS, extended Lambertian scene →
    L_reflected(λ) = ρ·E_solar(λ)/π to 1e-6 rel. (pure Lambertian identity)
  - Anchor 2: Spectral ρ(λ) Heaviside (0 below 0.5µm, 1 above) → at-aperture
    radiance has same step.
  - Anchor 3: Cross-check S5 vs T3Mixed with ε=1−ρ at same ρ → identical
    at-aperture radiance to 1e-6 rel. This proves the S4/S5 and S7 paths
    give physically identical results.

Regression gate: all six commands.

New tests (MANDATORY):
  - Three truth anchors above.
  - T2Reflective is actually constructed (assert isinstance on descriptor).
  - Negative: reflectance + temperature together → raise.
  - Negative: reflectance=0.5 with MWIR scene → UserWarning (not a raise).

Report per Category C.
```

---

## Phase 4 — S8 User-Radiance-at-Source Escape Hatch

**Read first**:
- `src/radiant/source/tabulated.py` (TabulatedRadianceSource already exists)
- `src/radiant/source/_inferrer.py`

### Step 4.1 — Wire `user_radiance` YAML key through `TabulatedRadianceSource`

**Category**: B

**Prompt to paste**:
```
Category B task: expose TabulatedRadianceSource at the YAML surface.

Scope — modify only:
  - src/radiant/source/_schema.py (add source.target.user_radiance:
    SpectralData | None)
  - src/radiant/source/_inferrer.py (route to TabulatedRadianceSource +
    emit T1Thermal OR a new S8-specific descriptor — DO NOT create a new
    descriptor variant; reuse T1Thermal wrapping or T5AtAperture semantics
    where atmosphere still runs. If the existing descriptor family cannot
    express S8 cleanly, STOP and report; do not invent a new variant without
    an ADR.)
  - src/radiant/source/tests/test_inferrer_user_radiance.py (NEW)

Regression gate: all six commands; 80/10 matrix unchanged.

New tests (MANDATORY):
  - user_radiance + extended → chain runs, output nonzero.
  - user_radiance + temperature together → raise (over-specified).
  - user_radiance with negative values → raise.

Report per Category B (dimensional audit, failure modes).
```

---

## Phase 5 — S10 User-Intensity Point-Source Escape Hatch

### Step 5.1 — Wire `user_intensity` through `DirectIntensitySource`

**Category**: B

**Prompt to paste**:
```
Category B task: expose DirectIntensitySource at the YAML surface for
point_source targets (S10).

Scope — modify only:
  - src/radiant/source/_schema.py (source.target.user_intensity:
    SpectralData | None, canonical unit W/sr/µm)
  - src/radiant/source/_inferrer.py (when user_intensity is set AND
    scene_type=="point_source", route to resolve_direct_intensity;
    when user_intensity set with other scene_types → raise)
  - src/radiant/source/tests/test_inferrer_user_intensity.py (NEW)

Regression gate: all six commands.

New tests (MANDATORY):
  - user_intensity + point_source → chain runs, projected_area=0.
  - user_intensity + extended → raise.
  - user_intensity + sub_pixel → raise.
  - user_intensity negative → raise.

Report per Category B.
```

---

## Phase 6 — `ReflectanceDescriptor` Stub Base (Q4)

### Step 6.1 — Introduce the base and refactor `LambertianBRDF` / `PhongBRDF` under it

**Category**: B

**Prompt to paste**:
```
Category B task: introduce ReflectanceDescriptor protocol and slot existing
BRDF classes under it without breaking T2Reflective.

Read first: src/radiant/source/brdf_lambertian.py, src/radiant/source/brdf_phong.py,
src/radiant/core/descriptors.py T2Reflective, docs/RADIANT_Target_Definition_Matrix.md
§4 Q4 resolution.

Scope — modify only:
  - NEW: src/radiant/core/reflectance.py (protocol)
  - src/radiant/source/brdf_lambertian.py (make implement the protocol)
  - src/radiant/source/brdf_phong.py (same)
  - src/radiant/core/descriptors.py (T2Reflective.rho accepts Union[SpectralData,
    ReflectanceDescriptor] — preserve existing API)
  - src/radiant/source/tests/test_reflectance_descriptor.py (NEW)

Contract:
  class ReflectanceDescriptor(Protocol):
      def reflectance_at(self, wavelength_um: ndarray, view_dir: ndarray,
                         illumination_dir: ndarray) -> ndarray: ...

  Existing scalar ρ(λ) SpectralData wraps in a ScalarLambertianReflectance
  adapter automatically; no user-visible change.

Regression gate: all six commands; T2Reflective contract tests unchanged.

New tests (MANDATORY):
  - ScalarLambertianReflectance(ρ=0.3).reflectance_at(...) returns 0.3 regardless
    of view/illumination (Lambertian definition).
  - LambertianBRDF implements the protocol (runtime_checkable isinstance check).
  - PhongBRDF implements the protocol.
  - T2Reflective accepts both SpectralData and ReflectanceDescriptor without
    breaking existing tests.
  - Pre-existing tests pass unchanged (regression).

Report per Category B (no physics change; emphasize no golden drift).
```

---

## Phase 7 — Matrix Coverage Extension (S4–S12)

**Goal**: Extend [`tests/integration/test_use_case_matrix.py`](../tests/integration/test_use_case_matrix.py) (or a sibling) so every newly-supported spec form from Phases 1–6 is exercised end-to-end at the matrix level, and the coverage JSON reflects S-form coverage.

### Step 7.1 — Matrix S-form coverage

**Category**: D

**Prompt to paste**:
```
Category D task: extend the use-case coverage harness to track spec form
S1–S12 alongside scene_type × wavelength_regime × target_location.

Read first: tests/integration/test_use_case_matrix.py,
tests/integration/_use_case_coverage.json,
docs/RADIANT_Target_Definition_Matrix.md §1 and §2.

Scope — NEW FILE:
  - tests/integration/test_spec_form_matrix.py (mirrors _REGIME_GRIDS pattern)

For each spec form successfully implemented through Phases 1–6
(S1,S2,S3,S4,S5,S6,S7,S8,S9,S10,S11,S12), parametrize one representative
cell per scene_type from the compatibility matrix §2. For invalid
combinations (e.g., S10 + extended), assert raise.

Extend _use_case_coverage.json to add a "spec_forms" sub-object with
{S1..S12: ✅|⚠|❌} so the ergonomics of matrix coverage carry the S-axis.

Regression gate: all six commands; 80/10 cell counts unchanged.

New tests (MANDATORY): one parametrized test class per spec form with
representative cells.

Report per Category D, including a table of per-S-form status AFTER the
implementation phases have landed.
```

---

## Final Acceptance (end of Phase 7)

After Phase 7, the following must be true; paste the exact command output in the final report:

1. `pytest -v` — full suite green, zero fails, zero unexpected skips.
2. `pytest tests/integration/test_use_case_matrix.py -v` — 80 pass / 10 raise unchanged.
3. `pytest tests/integration/test_spec_form_matrix.py -v` — all 12 S-forms covered, correct statuses.
4. `mypy --strict src/radiant/core src/radiant/api` — clean.
5. `import-linter --config pyproject.toml` — clean.
6. `ruff check src/` — zero findings.
7. [`Target_Definition_gaps.md`](Target_Definition_gaps.md) updated: every row marked ✅ except any items the user explicitly deferred.
8. [`RADIANT_Target_Definition_Matrix.md`](RADIANT_Target_Definition_Matrix.md) revision log amended with an entry marking Q1/Q3/Q4 delivered.

---

## Change Control

- **Do not reorder phases** without user approval. Phase 1 (shape) and Phase 2 (S11/S12) are P0 and independent; either can go first. Phases 3–6 each stand alone after Phase 1. Phase 7 is last.
- **Do not batch multiple steps into a single conversation.** The prompting sequence is designed for one step per conversation so regression evidence is tight and reviewable.
- **If any regression command fails**, STOP. Do not mask with `xfail`, do not update goldens, do not bypass. Report the failure and wait for guidance.
- **If an architecture contradiction is found** (e.g., a new descriptor variant is required to implement S8 cleanly), STOP at that step and escalate — do not invent a variant; open an ADR under `docs/adr/`.

---

## Revision log

- **2026-04-21**: Initial plan. 7 phases, 10 steps, each with its own regression gate and mandatory new-test contract.
