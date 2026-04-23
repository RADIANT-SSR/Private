# RADIANT Target Definition Matrix — Draft

**Date**: 2026-04-21
**Status**: Draft for review — enumerates all the ways a target's radiation can be specified, the scene-type compatibility, and the shape catalog for sub-pixel targets. This is the *spec* the codebase will be audited against, not a description of what the code does today.
**Related**: [`RADIANT_Use_Case_Matrix.md`](RADIANT_Use_Case_Matrix.md) (axes: scene_type × wavelength_regime × target_location); this document expands the **target-specification** axis that the use-case matrix treats as a single "T-code" (T1..T5) discriminator.

---

## Scope

Three axes define a RADIANT target:

| Axis | Values | Purpose |
|------|--------|---------|
| **A. Radiometric specification form** | S1..S12 (below) | *How* the user describes the target's radiation — input form |
| **B. Scene type** | extended · sub_pixel · point_source | Pixel-filling regime (inherited from use-case matrix §1.1) |
| **C. Shape** | plate · sphere · cylinder · ellipsoid · polygon · STL | Geometry of the physical target — determines projected area and illuminated fraction. Meaningful only for sub_pixel (and indirectly for point_source intensity). |

This document enumerates Axis A in full, cross-products it against Axis B to produce the compatibility matrix, and catalogs Axis C.

Axis A is intentionally richer than the existing T1..T5 discriminated union in [`src/radiant/core/descriptors.py`](../src/radiant/core/descriptors.py). T1..T5 are the *assembled* descriptor variants; S1..S12 are the *user-facing input forms* that map (possibly many-to-one) onto those variants.

---

## §1 — Radiometric Specification Forms (Axis A)

Each spec form is one way the user can tell RADIANT "here is the target's radiation." The column "Maps to existing descriptor" identifies the closest v1 descriptor; `—` means no direct mapping exists today.

| Code | Name | Inputs | Derived | Domain | Maps to existing descriptor |
|------|------|--------|---------|--------|------------------------------|
| **S1** | Blackbody | `T` [K] | `ε(λ) ≡ 1`; `L(λ) = B(λ, T)` | Thermal sources at any λ | T1Thermal (ε=1 spectral data) |
| **S2** | Graybody scalar | `T` [K], `ε` [dimensionless, scalar] | `L(λ) = ε · B(λ, T)` | Thermal sources, grey approximation | T1Thermal (constant ε(λ) = ε) |
| **S3** | Graybody spectral | `T` [K], `ε(λ)` | `L(λ) = ε(λ) · B(λ, T)` | Thermal sources, real materials | T1Thermal (ε(λ) SpectralData) |
| **S4** | Reflective scalar | `ρ` [dimensionless, scalar], `E_illum(λ)` | `L(λ) = ρ · E_illum(λ) / π` (Lambertian) | Reflective-dominated bands (VIS/NIR/SWIR) | T2Reflective (constant ρ(λ) = ρ) |
| **S5** | Reflective spectral | `ρ(λ)`, `E_illum(λ)` | `L(λ) = ρ(λ) · E_illum(λ) / π` | Reflective with material spectrum | T2Reflective (ρ(λ) SpectralData) |
| **S6** | Albedo | `α(λ)`, `E_illum(λ)` | `L(λ) = α(λ) · E_illum(λ) / π` | Synonym for S5 under Lambertian assumption; distinguished from S5 only because "albedo" is a common user-facing term | T2Reflective (ρ ≡ α) |
| **S7** | Mixed emit + reflect | `ε(λ)`, `T` [K], `E_illum(λ)` | Kirchhoff: `ρ(λ) = 1 − ε(λ)`; `L(λ) = ε(λ)·B(λ, T) + (1 − ε(λ))·E_illum(λ)/π` | MWIR ambient; hot-target SWIR (matrix §3.2) | T3Mixed |
| **S8** | User radiance at source | `L_source(λ)` [W/m²/sr/µm] | none (runs through full atmosphere transport) | Custom spectra (measured or modeled); bypasses S1–S7 physics | — (not in v1) |
| **S9** | User radiance at aperture | `L_aperture(λ)` [W/m²/sr/µm] | none (bypasses atmosphere transport — `target_location=at_aperture`) | Lab-injected or pre-propagated spectra | T5AtAperture |
| **S10** | Intensity (point source) | `I(λ)` [W/sr/µm] | Pre-integrated over target area; no A_t or shape needed downstream | Stars, unresolved targets where A_t is unknowable | — (not in v1; matrix defers to T5 for at-aperture point sources) |
| **S11** | Brightness temperature | `T_B(λ)` [K] | Inverse Planck: `L(λ) = B(λ, T_B(λ))` — equivalent to S3 with implied `ε(λ) ≡ 1` on a per-wavelength basis | IR radiometry convention; pyrometer outputs | — (not in v1 — derive to S8) |
| **S12** | Radiance temperature (in-band) | `T_R` [K], `band = [λ_min, λ_max]` | Scalar temperature matching in-band integrated radiance: `∫B(λ, T_R)dλ = ∫L_target(λ)dλ` over the band | Single-number legacy specs (e.g., "the plume is 850 K equivalent in LWIR") | — (not in v1 — derive to S1 over band) |

**Excluded from v1 (explicitly deferred):**

- **BRDF** `ρ_bd(λ, θ_i, φ_i, θ_o, φ_o)` — non-Lambertian reflectance. Matrix §1 assumes Lambertian throughout; BRDF lifts the 1/π factor into a full bidirectional term. Would require a new descriptor variant (T6? T2b?) and a DirectionalReflectanceStage-level change.
- **Polarized radiance** `L(λ, p)` — polarization state. RADIANT is scalar-radiance throughout.
- **Temperature distribution / thermal gradient** — the spec forms above all assume uniform target T. A thermally-layered plume or hot engine with a cool skin would need a spatial T field.

---

## §2 — Scene-Type Compatibility Matrix (Axis A × Axis B)

Columns: valid (✓), invalid by construction (✗), requires conversion (→Sx), or deferred (⚠).

| Spec | Extended | Sub-pixel | Point source | Notes |
|------|----------|-----------|--------------|-------|
| **S1 Blackbody** | ✓ | ✓ (with A_t, shape, range) | → S10 via `I(λ) = L(λ) · A_proj` | Thermal from any shape; point-source form requires pre-integration |
| **S2 Graybody scalar** | ✓ | ✓ | → S10 | Same as S1 with constant ε scaling |
| **S3 Graybody spectral** | ✓ | ✓ | → S10 | Most common thermal spec (real materials) |
| **S4 Reflective scalar** | ✓ | ✓ | → S10 | Needs E_illum transported to target (E_TOA · τ_sun or E_sky) |
| **S5 Reflective spectral** | ✓ | ✓ | → S10 | Same as S4 with ρ(λ) |
| **S6 Albedo** | ✓ | ✓ | → S10 | Synonym for S5; Lambertian assumed |
| **S7 Mixed emit+reflect** | ✓ | ✓ | → S10 | MWIR ambient mandatory per matrix §3.2 |
| **S8 User radiance at source** | ✓ | ✓ | → S10 | Runs through full atmosphere transport |
| **S9 User radiance at aperture** | ✓ | ✗ (matrix §7: at_aperture ⇒ extended only) | ✗ (same) | T5 pairs only with extended. Sub-pixel/point at_aperture would need `I_aperture` — deferred |
| **S10 Intensity (point source)** | ✗ | ✗ | ✓ | Spec is defined post-area-integration; not valid for resolved targets |
| **S11 Brightness temperature** | → S3/S8 | → S3/S8 | → S10 via S3/S8 | Pure input convention — convert at boundary |
| **S12 Radiance temperature** | → S1 over band | → S1 over band | → S10 via S1 | Single-scalar convenience — convert at boundary |

**Reading the table:**

- `✓` — v1 supports this combination (though not necessarily via a named user-facing input — see the code-audit step in §4).
- `✗` — invalid by physics or by matrix §7 rule; must raise at input validation.
- `→ Sx` — input form is re-expressed as another spec form at a boundary converter (Rule 2).
- `⚠` — valid but deferred to a future version.

---

## §3 — Shape Catalog (Axis C)

Shape enters the computation only when the target is **resolved in area** — i.e., sub_pixel (where A_t contributes to `L_pixel = ff · L_t + (1−ff) · L_bg`) and indirectly point_source (where `I = L · A_proj` requires A_proj).

For extended scenes, shape is irrelevant — the pixel is fully filled and A_t / A_proj never enters.

| Shape | Parameters | A_projected formula | Illuminated-fraction (for S4–S7) | Notes |
|-------|-----------|---------------------|----------------------------------|-------|
| **Disk (frontal)** | `r` [m] | `π r²` (independent of orientation when facing the sensor) | `1.0` (fully facing sun) | Simplest default — matches "flat target perpendicular to LOS" |
| **Flat plate** | `L, W` [m], orientation `(θ_n, φ_n)` (surface normal) | `L·W·|cos(θ_n − θ_o)|` (LOS projection) | `|cos(θ_n − θ_s)|` if positive, else 0 | Canonical for painted panels, solar cells, building facets |
| **Sphere** | `r` [m] | `π r²` (always; projected area of a sphere is invariant to orientation) | `0.5` (half-lit under parallel illumination; diffuse-integrated over the day-hemisphere) | Canonical for balloons, small spherical targets |
| **Cylinder (long axis)** | `r, L` [m], axis orientation `(θ_a, φ_a)` | Depends on view angle: `2 r L · sin(θ)` (side-on) to `π r²` (end-on) | Similar dependence on sun angle | Rockets, missiles, columns |
| **Ellipsoid** | `a, b, c` [m], orientation | Formula per viewing geometry (general-case solid-angle integral) | Per-facet integral | Aircraft bodies, fuel tanks, asteroids |
| **Polygon (2D silhouette)** | vertex list `[(x_i, y_i)]`, orientation | Shoelace formula projected onto LOS plane | Per-facet if 3D, else 1.0 for flat | Vehicle silhouettes, building outlines |
| **STL / mesh (3D)** | triangulated mesh, orientation | Sum of per-triangle projections onto LOS | Per-triangle visibility (ray-trace or bounding-box) | High-fidelity targets (aircraft, satellites); v2 scope |

**Minimum v1 shape set**: Disk, Flat plate, Sphere. These cover >80% of scenario use cases and require no ray-tracing. The rest are growth paths.

**Shape + spec-form interactions:**

- **S1–S3 (thermal)**: shape affects `A_proj` only; self-emission is isotropic (Lambertian assumption) so orientation doesn't change `L_per_A`.
- **S4–S7 (reflective)**: shape affects both `A_proj` (for intensity) and illuminated fraction (for reflected-solar term). A facing-sun flat plate reflects ~full solar irradiance; a shaded side reflects zero; a sphere averages to `0.5`.
- **S8 (user L at source)**: shape enters only via `A_proj` for the sub-pixel fill-fraction. User is responsible for any orientation-dependent effects baked into their L spectrum.
- **S9 (user L at aperture)**: extended only; shape irrelevant.
- **S10 (intensity)**: `I(λ)` is already area-integrated; shape unused. If the user has `L(λ)` and a shape, convert via `I = L · A_proj` at the boundary.

---

## §4 — Next Steps (not yet executed)

This document is the **target spec**; it does not yet describe what the codebase does. The next task is a codebase audit: for each (Spec, SceneType) cell in the compatibility matrix, answer:

1. **Does a user-facing input path exist?** (scenario YAML key, `params.set(...)` path, or direct descriptor construction)
2. **Does the input get normalized to the right descriptor?** (e.g., S2 "graybody scalar" must expand to an ε(λ) constant array before reaching T1Thermal)
3. **Is the shape honored for sub-pixel projection and illumination?** The [`TargetShape`](../src/radiant/source/shape.py) protocol and concrete shapes (`sphere`, `cylinder`, `flat_plate`, `box`, `cone`) exist — is the descriptor pipeline actually calling `shape.projected_area(view_direction)`, and does shape override `projected_area_m2` with a warning (Q3 resolution)?
4. **Is there a validator for incompatible combinations?** (e.g., S10 + extended → raise)
5. **Are there truth-anchor tests for this spec form?**

Audit deliverable: a companion `docs/Target_Definition_gaps.md` structured like `Use_Case_gaps.md` — one row per ✓ cell in §2 listing current state, gaps, and effort to close.

**Resolutions (2026-04-21):**

- **Q1 — RESOLVED: first-class.** S11 (brightness temperature `T_B(λ)`) and S12 (radiance temperature `T_R + band`) are first-class user inputs with boundary converters (Rule 2: convert at boundaries). Converters emit the canonical descriptor (T1Thermal or T5AtAperture as appropriate) so downstream stages see no new variant.
- **Q2 — RESOLVED: reuse existing class.** The [`TargetShape`](../src/radiant/source/shape.py) protocol and [`src/radiant/source/shapes/`](../src/radiant/source/shapes/) package (`box`, `cone`, `cylinder`, `flat_plate`, `sphere`) already exist. The audit will check whether these are actually wired into descriptor construction for sub-pixel targets, not create a new `ShapeDescriptor` class.
- **Q3 — RESOLVED: shape wins.** When both `shape` and `projected_area_m2` are supplied, `shape.projected_area(view_direction)` overrides `projected_area_m2`. Emit a consistency warning so the conflict is not silent (Rule 17). Audit must check this precedence is actually enforced.
- **Q4 — RESOLVED: add stub base.** Introduce a lightweight `ReflectanceDescriptor` base that today's scalar ρ(λ) / albedo(λ) inputs normalize into. BRDF (Lambertian, Phong, measured) extends it later without breaking T2Reflective. Existing [`brdf_lambertian.py`](../src/radiant/source/brdf_lambertian.py) and [`brdf_phong.py`](../src/radiant/source/brdf_phong.py) are candidate initial concretions to slot under the base.

---

## Revision log

- **2026-04-21**: Initial draft. Axes A/B/C defined; spec forms S1–S12 enumerated; §4 audit plan sketched.
- **2026-04-21**: Q1–Q4 resolved. S11/S12 first-class with boundary converters; reuse existing `TargetShape` protocol and `source/shapes/` package (no new class); shape wins over `projected_area_m2` with consistency warning; add `ReflectanceDescriptor` stub base for future BRDF extension.
- **2026-04-22**: **Q1 / Q3 / Q4 delivered.** Target Definition Implementation Plan Phases 1–7 landed.
  - **Q1 (S11/S12 first-class)**: boundary converters in [`src/radiant/source/converters/brightness_temperature.py`](../src/radiant/source/converters/brightness_temperature.py) and [`src/radiant/source/converters/radiance_temperature.py`](../src/radiant/source/converters/radiance_temperature.py) with the band-inversion helper [`invert_band_radiance.py`](../src/radiant/source/converters/invert_band_radiance.py). Scalar inputs wired end-to-end; λ-varying `brightness_temperature_path` CSV shares the deferred loader follow-up (see [`Target_Definition_gaps.md`](Target_Definition_gaps.md) Gap G).
  - **Q3 (shape wins)**: [`shape_factory.build_shape`](../src/radiant/source/resolvers/shape_factory.py) wires `source.target.shape` + `source.target.shape_params` through the inferrer; conflict with `projected_area_m2` emits a `UserWarning` and the shape value is used. Matrix coverage in [`tests/integration/test_use_case_shapes.py`](../tests/integration/test_use_case_shapes.py).
  - **Q4 (ReflectanceDescriptor stub)**: [`src/radiant/core/reflectance.py`](../src/radiant/core/reflectance.py) defines the `runtime_checkable` protocol + `ScalarLambertianReflectance` adapter; [`LambertianBRDF`](../src/radiant/source/brdf_lambertian.py) and [`PhongBRDF`](../src/radiant/source/brdf_phong.py) satisfy the protocol. `T2Reflective.rho` accepts either `SpectralData` or a `ReflectanceDescriptor`. Automatic wrap at assembly is deferred to the first protocol consumer (Gap H in the gaps doc).
  - S4/S5/S6 (Phase 3) and S8/S10 (Phases 4–5) user-input paths also landed alongside the Q-resolutions; see [`Target_Definition_gaps.md`](Target_Definition_gaps.md) for per-form status.
  - 36-cell spec-form coverage harness at [`tests/integration/test_spec_form_matrix.py`](../tests/integration/test_spec_form_matrix.py); aggregated status in [`tests/integration/_use_case_coverage.json`](../tests/integration/_use_case_coverage.json) `spec_forms` block.
