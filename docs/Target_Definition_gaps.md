# Target Definition Matrix — Codebase Audit Against Spec

**Original audit**: 2026-04-21 (against pre-implementation codebase)
**Post-implementation update**: 2026-04-22 (after Target Definition Implementation Plan Phases 1–7 landed)
**Gap G close-out**: 2026-04-23 (shared CSV loader delivered — all 12 spec forms fully supported)
**Audit scope**: 12 spec forms (S1–S12) × 3 scene types (extended, sub_pixel, point_source)
**Source of truth**: [`RADIANT_Target_Definition_Matrix.md`](RADIANT_Target_Definition_Matrix.md) (spec) vs. codebase (implementation)

---

## Executive Summary (post Gap G)

| Status | Count | Forms | Notes |
|--------|-------|-------|-------|
| ✅ Fully supported | 12 | S1–S12 | Scalar and CSV-path surfaces both wired; descriptor construction verified end-to-end; matrix coverage in [`tests/integration/test_spec_form_matrix.py`](../tests/integration/test_spec_form_matrix.py) |
| ⚠ Scalar-only (CSV loader deferred) | 0 | — | Closed 2026-04-23 by Gap G shared CSV loader |
| ❌ Not supported | 0 | — | — |

**Key findings (2026-04-22):**
- Q1 **delivered**: S11 (`brightness_temperature_K`) and S12 (`radiance_temperature_K` + band) boundary converters live in [`src/radiant/source/converters/`](../src/radiant/source/converters/), wired through the inferrer.
- Q3 **delivered**: `source.target.shape` + `shape_params` route through [`shape_factory.build_shape`](../src/radiant/source/resolvers/shape_factory.py); shape wins over `projected_area_m2` with a `UserWarning`.
- Q4 **delivered (stub)**: [`ReflectanceDescriptor`](../src/radiant/core/reflectance.py) protocol (`runtime_checkable`) + [`ScalarLambertianReflectance`](../src/radiant/core/reflectance.py) adapter; `LambertianBRDF` and `PhongBRDF` both satisfy the protocol; `T2Reflective.rho` accepts either `SpectralData` or a `ReflectanceDescriptor`.
- S4/S5/S6 (pure-reflective) reachable via `source.target.reflectance` / `.albedo` (scalar) and via `reflectance_path` / `albedo_path` CSV (Gap G Step G.2, closed 2026-04-23).
- S8, S10 wired at the YAML/params surface through Phase 4 / Phase 5.
- Matrix axes (scene_type, target_location, shape) enforced at descriptor level (`src/radiant/core/descriptors.py`).
- 36-cell spec-form coverage matrix ([`tests/integration/test_spec_form_matrix.py`](../tests/integration/test_spec_form_matrix.py)) green; aggregated into [`_use_case_coverage.json`](../tests/integration/_use_case_coverage.json) under the `spec_forms` block.

---

## Per-Spec-Form Audit

### S1 — Blackbody (T = K, ε ≡ 1)

| Aspect | Finding | Citation |
|--------|---------|----------|
| **User input path** | `source.target.temperature` + `source.target.emissivity = 1.0` (or default). | [`src/radiant/source/_schema.py`](../src/radiant/source/_schema.py) |
| **Normalization** | T1Thermal with ε = const(1.0). | [`src/radiant/source/_inferrer.py`](../src/radiant/source/_inferrer.py) |
| **Validation** | T1Thermal checks 0 ≤ ε ≤ 1 and T > 0 K. | [`src/radiant/core/descriptors.py`](../src/radiant/core/descriptors.py) |
| **Tests** | `test_descriptors.py`, `test_inferrer.py`, [`test_spec_form_matrix.py`](../tests/integration/test_spec_form_matrix.py) (S1 × 3 scene types) | — |
| **Status** | ✅ **Fully supported** |

### S2 — Graybody scalar (T, ε = const)

| Aspect | Finding | Citation |
|--------|---------|----------|
| **User input path** | `source.target.temperature` + `source.target.emissivity` (scalar). | [`_schema.py`](../src/radiant/source/_schema.py) |
| **Normalization** | T1Thermal with ε(λ) = const array. | [`_inferrer.py`](../src/radiant/source/_inferrer.py) |
| **Tests** | `test_inferrer.py`, [`test_spec_form_matrix.py`](../tests/integration/test_spec_form_matrix.py) (S2 × 3) | — |
| **Status** | ✅ **Fully supported** |

### S3 — Graybody spectral (T, ε(λ))

| Aspect | Finding | Citation |
|--------|---------|----------|
| **User input path** | `source.target.temperature` + scalar ε lifted to spectral (S3 scalar-constant limit) through the inferrer.  A λ-varying ε(λ) CSV surface is not yet exposed; the Gap G shared two-column loader at [`_csv.py`](../src/radiant/source/converters/_csv.py) is the template if one is added later. | [`_inferrer.py`](../src/radiant/source/_inferrer.py) |
| **Normalization** | T1Thermal(ε=SpectralData). | [`descriptors.py`](../src/radiant/core/descriptors.py) |
| **Tests** | `test_inferrer.py`, [`test_spec_form_matrix.py`](../tests/integration/test_spec_form_matrix.py) (S3 × 3) | — |
| **Status** | ✅ **Fully supported** (scalar limit exercised; no dedicated CSV surface — not needed for the current spec set) |

### S4 — Reflective scalar (ρ, E_illum)

| Aspect | Finding | Citation |
|--------|---------|----------|
| **User input path** | `source.target.reflectance` (scalar) wired through Phase 3 / Step 3.2. | [`_inferrer.py`](../src/radiant/source/_inferrer.py), [`test_inferrer_reflective.py`](../src/radiant/source/tests/test_inferrer_reflective.py) |
| **Normalization** | T2Reflective(rho=const SpectralData). | [`descriptors.py`](../src/radiant/core/descriptors.py) |
| **Validation** | T2Reflective requires 0 ≤ ρ ≤ 1. MWIR warning (Rule 17). | — |
| **Tests** | [`test_inferrer_reflective.py`](../src/radiant/source/tests/test_inferrer_reflective.py), [`test_spec_form_matrix.py`](../tests/integration/test_spec_form_matrix.py) (S4 × 3) | — |
| **Status** | ✅ **Fully supported** |

### S5 — Reflective spectral (ρ(λ), E_illum(λ))

| Aspect | Finding | Citation |
|--------|---------|----------|
| **User input path** | `source.target.reflectance_path` / `albedo_path` CSV routes through the shared two-column loader ([`_csv.py`](../src/radiant/source/converters/_csv.py)) into T2Reflective(rho=SpectralData). Scalar `source.target.reflectance` / `.albedo` path remains available. | [`_inferrer.py`](../src/radiant/source/_inferrer.py), [`_csv.py`](../src/radiant/source/converters/_csv.py) |
| **Normalization** | T2Reflective(rho=SpectralData). | [`descriptors.py`](../src/radiant/core/descriptors.py) |
| **Tests** | [`test_inferrer_reflective.py`](../src/radiant/source/tests/test_inferrer_reflective.py), [`test_spec_form_matrix.py`](../tests/integration/test_spec_form_matrix.py) (S5 × 3 — extended exercises the CSV path via `albedo_path`, sub_pixel / point_source exercise the scalar path). | — |
| **Status** | ✅ **Fully supported** |

### S6 — Albedo (α(λ), E_illum)

| Aspect | Finding | Citation |
|--------|---------|----------|
| **User input path** | `source.target.albedo` (scalar) wired as an alias for reflectance in Phase 3 / Step 3.2. Mutually exclusive with `reflectance` (raises). | [`_inferrer.py`](../src/radiant/source/_inferrer.py), [`test_inferrer_reflective.py`](../src/radiant/source/tests/test_inferrer_reflective.py) |
| **Normalization** | T2Reflective via the reflectance path. | — |
| **Tests** | [`test_inferrer_reflective.py`](../src/radiant/source/tests/test_inferrer_reflective.py), [`test_spec_form_matrix.py`](../tests/integration/test_spec_form_matrix.py) (S6 × 3) | — |
| **Status** | ✅ **Fully supported** |

### S7 — Mixed emit + reflect (ε, T, E_illum)

| Aspect | Finding | Citation |
|--------|---------|----------|
| **User input path** | `source.target.temperature` + `source.target.emissivity` (ε < 1) → auto-promotes to T3Mixed. | [`_inferrer.py`](../src/radiant/source/_inferrer.py) |
| **Normalization** | T3Mixed(ε, T); ρ = 1 − ε derived at assembly. | [`descriptors.py`](../src/radiant/core/descriptors.py) |
| **Tests** | `test_inferrer.py`, `test_combined.py`, [`test_spec_form_matrix.py`](../tests/integration/test_spec_form_matrix.py) (S7 × 3) | — |
| **Status** | ✅ **Fully supported** |

### S8 — User radiance at source (L_source(λ))

| Aspect | Finding | Citation |
|--------|---------|----------|
| **User input path** | `source.target.user_radiance_path` CSV wired through Phase 4 / Step 4.1 → T6TabulatedAtSource. | [`test_inferrer_user_radiance.py`](../src/radiant/source/tests/test_inferrer_user_radiance.py), [ADR-0003](adr/0003-t6-tabulated-at-source.md) |
| **Normalization** | T6TabulatedAtSource; atmosphere transport runs normally. | — |
| **Tests** | [`test_inferrer_user_radiance.py`](../src/radiant/source/tests/test_inferrer_user_radiance.py), [`test_spec_form_matrix.py`](../tests/integration/test_spec_form_matrix.py) (S8 × 3) | — |
| **Status** | ✅ **Fully supported** |

### S9 — User radiance at aperture (L_aperture(λ))

| Aspect | Finding | Citation |
|--------|---------|----------|
| **User input path** | T5AtAperture direct construction; `target_location="at_aperture"` requires `scene_type="extended"`. | [`descriptors.py`](../src/radiant/core/descriptors.py) |
| **Validation** | sub_pixel / point_source + at_aperture → `ParameterBoundsError` (matrix §7 Decision #2). | — |
| **Tests** | `test_descriptors.py`, `test_use_case_warnings.py`, [`test_spec_form_matrix.py`](../tests/integration/test_spec_form_matrix.py) (S9 extended = pass; others = raise) | — |
| **Status** | ✅ **Fully supported** |

### S10 — Intensity (point source; I(λ))

| Aspect | Finding | Citation |
|--------|---------|----------|
| **User input path** | `source.target.user_intensity_path` CSV wired through Phase 5 / Step 5.1 → T7IntensityAtSource (point-source only). | [`test_inferrer_user_intensity.py`](../src/radiant/source/tests/test_inferrer_user_intensity.py), [ADR-0004](adr/0004-t7-intensity-at-source.md) |
| **Normalization** | T7IntensityAtSource; projected area not used. | — |
| **Validation** | Boundary converter [`user_intensity_to_descriptor`](../src/radiant/source/converters/user_intensity.py) raises `ParameterBoundsError` for `scene_type ≠ point_source`. | — |
| **Tests** | [`test_inferrer_user_intensity.py`](../src/radiant/source/tests/test_inferrer_user_intensity.py), [`test_spec_form_matrix.py`](../tests/integration/test_spec_form_matrix.py) (S10 point_source = pass; others = raise) | — |
| **Status** | ✅ **Fully supported** |

### S11 — Brightness temperature (T_B(λ))

| Aspect | Finding | Citation |
|--------|---------|----------|
| **User input path** | Scalar `source.target.brightness_temperature_K` → T1Thermal(ε ≡ 1); λ-varying `source.target.brightness_temperature_path` CSV routes through the shared two-column loader ([`_csv.py`](../src/radiant/source/converters/_csv.py)) into T6TabulatedAtSource via Planck per-λ conversion. | [`brightness_temperature.py`](../src/radiant/source/converters/brightness_temperature.py), [`_csv.py`](../src/radiant/source/converters/_csv.py) |
| **Normalization** | Constant T_B → T1Thermal; λ-varying T_B → T6TabulatedAtSource. | — |
| **Validation** | T_B ≤ 0 or > 10000 K → raise (scalar and per-sample on CSV). | — |
| **Tests** | [`test_brightness_temperature_converter.py`](../src/radiant/source/tests/test_brightness_temperature_converter.py), [`test_spec_form_matrix.py`](../tests/integration/test_spec_form_matrix.py) (S11 × 3 — extended exercises the CSV path, sub_pixel / point_source exercise the scalar path). | — |
| **Status** | ✅ **Fully supported** |

### S12 — Radiance temperature in-band (T_R, band)

| Aspect | Finding | Citation |
|--------|---------|----------|
| **User input path** | `source.target.radiance_temperature_K` + band (`_band_lo_um`, `_band_hi_um`) wired through Phase 2 / Step 2.2 → T1Thermal. | [`src/radiant/source/converters/radiance_temperature.py`](../src/radiant/source/converters/radiance_temperature.py), [`invert_band_radiance.py`](../src/radiant/source/converters/invert_band_radiance.py), [`test_radiance_temperature_converter.py`](../src/radiant/source/tests/test_radiance_temperature_converter.py) |
| **Normalization** | T1Thermal(T_t = T_R, ε ≡ 1). Band-inversion helper is in place for forward-compatibility with user-supplied in-band L. | — |
| **Validation** | T_R ≤ 0 / inverted band / band missing → raise. | — |
| **Tests** | [`test_radiance_temperature_converter.py`](../src/radiant/source/tests/test_radiance_temperature_converter.py), [`test_spec_form_matrix.py`](../tests/integration/test_spec_form_matrix.py) (S12 × 3) | — |
| **Status** | ✅ **Fully supported** |

---

## Cross-Cutting Gaps (post-implementation)

### Gap A — Shape wiring (Q3 resolution)

**Status: ✅ CLOSED (Phase 1).**

`source.target.shape` + `source.target.shape_params` route through [`shape_factory.build_shape`](../src/radiant/source/resolvers/shape_factory.py). Sphere, cylinder, flat_plate, box, cone all covered. Shape wins over `projected_area_m2` with a `UserWarning` (Rule 17). Coverage in [`test_use_case_shapes.py`](../tests/integration/test_use_case_shapes.py) and [`test_inferrer_shape.py`](../src/radiant/source/tests/test_inferrer_shape.py).

### Gap B — S11/S12 boundary converters (Q1 resolution)

**Status: ✅ CLOSED (Phase 2).**

[`brightness_temperature.py`](../src/radiant/source/converters/brightness_temperature.py) and [`radiance_temperature.py`](../src/radiant/source/converters/radiance_temperature.py) with matching schema params and inferrer wiring. Scalar forms wired end-to-end; λ-varying `brightness_temperature_path` CSV delivered 2026-04-23 via the shared two-column loader (Gap G close-out).

### Gap C — ReflectanceDescriptor stub (Q4 resolution)

**Status: ✅ CLOSED (Phase 6, stub scope).**

[`ReflectanceDescriptor`](../src/radiant/core/reflectance.py) protocol + `ScalarLambertianReflectance` adapter; `LambertianBRDF` and `PhongBRDF` satisfy the protocol via `.reflectance_at(λ, view, illum)` returning total hemispherical ρ. `T2Reflective.rho` widened to `SpectralData | ReflectanceDescriptor | None`. Automatic wrapping of scalar ρ SpectralData into an adapter at assembly time was deferred in line with the "stub" framing — see Gap H.

### Gap D — S4/S5/S6 reflective user-input paths

**Status: ✅ CLOSED (Phase 3 + Gap G).**

`source.target.reflectance` / `source.target.albedo` (scalar) wired through the inferrer in Phase 3; mutual exclusion with temperature and with each other enforced; MWIR warning fires per Rule 17. λ-varying `reflectance_path` / `albedo_path` CSVs delivered 2026-04-23 via the shared two-column loader (Gap G close-out).

### Gap E — S8 (user L at source)

**Status: ✅ CLOSED (Phase 4).**

`source.target.user_radiance_path` CSV routes to T6TabulatedAtSource; scene compatibility covered by [`test_spec_form_matrix.py`](../tests/integration/test_spec_form_matrix.py).

### Gap F — S10 (intensity point source)

**Status: ✅ CLOSED (Phase 5).**

`source.target.user_intensity_path` CSV routes through `user_intensity_to_descriptor` → T7IntensityAtSource. Non-point-source inputs raise at the converter boundary.

### Gap G — Shared CSV loader for spectral user inputs

**Status: ✅ CLOSED (2026-04-23).**

Shared two-column loader [`load_two_column_csv`](../src/radiant/source/converters/_csv.py) now powers `source.target.reflectance_path`, `source.target.albedo_path`, and `source.target.brightness_temperature_path`. The loader parses `λ [µm], value` rows, validates monotonic λ, and returns a `SpectralData` on the caller-supplied grid; per-sample bounds checks (0 ≤ ρ ≤ 1 for reflectance/albedo; 0 < T_B ≤ 10000 K for brightness temperature) happen inside the calling converter. Matrix coverage ([`test_spec_form_matrix.py`](../tests/integration/test_spec_form_matrix.py)) exercises each CSV path at the extended scene_type; the `_use_case_coverage.json` `spec_forms` block shows S5/S6/S11 all-pass.

### Gap H — Automatic `ScalarLambertianReflectance` wrap at assembly (**new, open, low priority**)

| Finding | Impact | Next step |
|---------|--------|-----------|
| Phase 6 / Step 6.1 framed the `ScalarLambertianReflectance` adapter as the place existing scalar-ρ `SpectralData` would *automatically* wrap on its way through `T2Reflective`. The current implementation widens the type union but keeps `SpectralData` flowing through unchanged (no wrap at assembly). | No user-facing impact today — downstream code treats `SpectralData` and the adapter interchangeably. Relevant only when a later phase begins distinguishing the two in assembly. | Deferred; revisit when the first consumer of the protocol lands (full plumbing through `AtmosphereStage` assembly, per Phase 6 docstring). Low priority. |

---

## Summary Table: Spec Form Support (2026-04-23)

| Form | Name | User input | Normalization | Validation | Tests | Status |
|------|------|-----------|----------------|-----------|-------|--------------|
| **S1** | Blackbody | ✅ (T, ε=1) | ✅ T1Thermal | ✅ | ✅ | ✅ Fully |
| **S2** | Graybody scalar | ✅ (T, ε) | ✅ T1Thermal | ✅ | ✅ | ✅ Fully |
| **S3** | Graybody spectral | ✅ (scalar limit; no dedicated CSV surface) | ✅ T1Thermal | ✅ | ✅ | ✅ Fully |
| **S4** | Reflective scalar | ✅ `.reflectance` | ✅ T2Reflective | ✅ | ✅ | ✅ Fully |
| **S5** | Reflective spectral | ✅ `.reflectance_path` / `.albedo_path` CSV | ✅ T2Reflective | ✅ | ✅ | ✅ Fully |
| **S6** | Albedo | ✅ `.albedo` (scalar) / `.albedo_path` (CSV) | ✅ T2Reflective | ✅ | ✅ | ✅ Fully |
| **S7** | Mixed emit+reflect | ✅ (T, ε) | ✅ T3Mixed | ✅ | ✅ | ✅ Fully |
| **S8** | User L at source | ✅ `.user_radiance_path` | ✅ T6TabulatedAtSource | ✅ | ✅ | ✅ Fully |
| **S9** | User L at aperture | ✅ T5AtAperture | ✅ | ✅ (extended-only) | ✅ | ✅ Fully |
| **S10** | Intensity point | ✅ `.user_intensity_path` | ✅ T7IntensityAtSource | ✅ (point_source-only) | ✅ | ✅ Fully |
| **S11** | Brightness temp | ✅ `.brightness_temperature_K` (scalar) / `.brightness_temperature_path` (CSV) | ✅ T1Thermal / T6TabulatedAtSource | ✅ | ✅ | ✅ Fully |
| **S12** | Radiance temp | ✅ `.radiance_temperature_K` + band | ✅ T1Thermal | ✅ | ✅ | ✅ Fully |

---

## Remaining Work

| Priority | Item | Effort | Risk |
|----------|------|--------|------|
| P3 | Gap H — automatic `ScalarLambertianReflectance` wrap at assembly | ≤ 0.5 day | Low (no user-facing impact) |

---

## Revision log

- **2026-04-21**: Initial audit against pre-implementation codebase. 6 gaps (A–F) identified; 6 forms without user paths.
- **2026-04-22**: Post-implementation update. Phases 1–7 delivered. Gaps A–F closed. Two new open items (G, H) surfaced by the Phase 7.1 coverage harness. 10 of 12 forms fully supported; S5 and S11 have scalar forms wired with CSV path deferred.
- **2026-04-23**: Gap G closed. Shared two-column loader [`load_two_column_csv`](../src/radiant/source/converters/_csv.py) wired into `reflectance_path`, `albedo_path`, and `brightness_temperature_path` inferrer call sites; matrix now exercises the CSV surfaces for S5/S6/S11 at the extended scene; `_use_case_coverage.json` `spec_forms` block shows S5/S6/S11 all `pass`. All 12 forms now fully supported. Only Gap H (P3, no user-facing impact) remains open.
