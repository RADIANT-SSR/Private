# RADIANT Source / Target System

**Status**: Authoritative — first design pass, unified  
**Scope**: All target and source modeling. Anything that produces a `SpectralRadiance` or `SpectralIntensity` for the chain to consume.  
**Sister documents**: RADIANT_Conventions.md, RADIANT_Parameter_System.md, RADIANT_Signal_Chain_Architecture.md

---

## 1. Design Philosophy

The source/target system has one job: **deliver a `ResolvedTarget` to the chain**. Everything in this document — geometry, materials, BRDFs, MODTRAN-flavored solar spectra, sub-pixel fill fractions — exists to populate that single contract.

Five guiding rules:

1. **One contract, five input paths.** A user may specify a target by direct radiance, by geometry+materials, by sub-pixel parameters, by direct intensity, or by physical object → integrated intensity. All five paths produce the **same** `ResolvedTarget`. The chain has no idea which path was used.
2. **Source types are spectral models, not target types.** A "target" is *what is observed*. A "source" is *the physics that generates radiance from a material*. A target may have many sources (a metal plate has both thermal emission and reflected solar). Sources compose; targets aggregate.
3. **Kirchhoff is enforced, not assumed.** For opaque surfaces, ε(λ) + ρ(λ) = 1 must hold at every wavelength. If a material specifies both, it is validated. If only one is given, the other is derived.
4. **Backgrounds are first-class.** Background radiance feeds the noise budget regardless of regime. A "no background" scenario is `BlackbodyBackground(T=2.7)` (CMB), not `None`.
5. **Regime is detected, not declared.** The user does not say "this is a point source." Regime is computed from target angular extent vs. PSF and IFOV. The user *can* override, but the override is logged with provenance.

---

## 2. The `ResolvedTarget` Contract

```python
@dataclass(frozen=True)
class ResolvedTarget:
    """Everything the chain needs to know about a target.

    Produced by exactly one of the five input paths. Immutable.
    The chain consumes this and never inspects how it was built.
    """

    # ---- Identification & provenance --------------------------------------
    name: str
    input_path: TargetInputPath          # which of the 5 paths produced this
    derivation_chain: tuple[str, ...]    # human-readable build steps

    # ---- Spectral content (always present) -------------------------------
    spectral_radiance: SpectralData      # W/m²/sr/µm at the target surface
                                         # (extended-source representation)
    spectral_intensity: SpectralData     # W/sr/µm at the target
                                         # (point-source representation)
    background_radiance: SpectralData    # W/m²/sr/µm

    # ---- Geometric properties --------------------------------------------
    projected_area_m2: float             # area facing observer
    angular_extent_rad: float            # √(projected_area)/range
    centroid_position_m: tuple[float, float, float]  # scene frame
    range_m: float                       # observer → target

    # ---- Regime hint -----------------------------------------------------
    tentative_regime: RadiometricRegime  # POINT_SOURCE | SUB_PIXEL | EXTENDED
    regime_override: RadiometricRegime | None  # None = auto

    # ---- Optional: full geometry & materials (geometry path only) --------
    geometry: TargetGeometry | None
    materials: tuple[SurfaceMaterial, ...] | None
```

**Invariants:**

1. `spectral_radiance` and `spectral_intensity` are **both** populated, even when one is "not physical" for the regime. The chain dispatches on regime, not on which field is `None`. The two are related by `intensity(λ) = radiance(λ) × projected_area`.
2. `background_radiance` is always populated. For deep-space scenarios, it is the 2.7 K CMB.
3. `tentative_regime` is computed in `SourceStage` from `angular_extent / IFOV`. The OpticsStage may upgrade or downgrade this once the real PSF FWHM is known (per RADIANT_Signal_Chain_Architecture.md §6.2).
4. All wavelength grids are aligned to the global grid in `SpectralDataStore` before `ResolvedTarget` is constructed.

---

## 3. Source Type Taxonomy

A "source" is a spectral radiance generator. Sources are composable: a `SurfaceMaterial` may have multiple active sources, and the total radiance is their sum (Kirchhoff-consistent).

### 3.1 Class hierarchy

```
SpectralRadianceSource (ABC)
├── ThermalSource           — ε(λ) · B(λ, T)
├── ReflectedSolarSource    — BRDF(θ_i, θ_r) · E_sun(λ) · cos θ_i
├── CombinedSource          — ThermalSource + ReflectedSolarSource (Kirchhoff)
└── TabulatedRadianceSource — user-provided L(λ)

SpectralIntensitySource (ABC)
├── DirectIntensitySource           — user-provided I(λ)
├── BlackbodyIntensitySource        — A · ε(λ) · B(λ, T) integrated over area
└── IntegratedObjectIntensitySource — sums object facet intensities

BackgroundSource (ABC)
├── BlackbodyBackground     — Planck at T_bg with optional ε
├── SkyBackground           — atmospheric thermal + solar scattered downwelling
├── GroundBackground        — natural surface (soil/vegetation/water/concrete)
├── TabulatedBackground     — user-provided L_bg(λ)
└── ConstantBackground      — flat L_bg per band (for quick studies)
```

### 3.2 ThermalSource

**Physics**: `L_th(λ) = ε(λ) · B(λ, T)` where B is the Planck spectral radiance function (W/m²/sr/µm).

**Inputs**: `SurfaceMaterial` (provides ε(λ) and T).

**Notes**: Self-consistent at any wavelength. Dominates LWIR and contributes substantially to MWIR. Below ~3 µm at terrestrial temperatures, contribution is negligible — but RADIANT computes it anyway, because numerical zero is preferable to a regime-dependent if-statement.

### 3.3 ReflectedSolarSource

**Physics**:
```
L_refl(λ, θ_r) = ∫ BRDF(λ; θ_i, φ_i; θ_r, φ_r) · E_sun(λ) · cos θ_i  dΩ_i
```

For v1, the integral collapses because we treat the sun as a single direction:
```
L_refl(λ) = BRDF(λ; θ_sun, θ_r) · E_sun(λ) · cos θ_sun
```

**Inputs**: `SurfaceMaterial` (provides ρ(λ) and BRDF model), solar geometry (sun zenith, observer zenith), reference solar spectrum.

**BRDF models for v1**:
- **Lambertian**: `BRDF = ρ(λ) / π` (independent of angle).
- **Phong**: `BRDF = ρ_d(λ)/π + ρ_s(λ) · (n+2)/(2π) · cos^n(α)` where α is the angle between the reflection direction and the observer direction. The diffuse fraction sums with the specular fraction such that ρ_d + ρ_s = ρ(λ).

Both models satisfy energy conservation (∫BRDF·cosθ dΩ ≤ ρ).

**Solar spectrum sources**: Kurucz 1 nm, ASTM E490, blackbody at 5778 K, or user-tabulated. Distance scaling by `(1 AU / d)²` for non-Earth scenarios.

### 3.4 CombinedSource (Kirchhoff-consistent)

For an opaque surface in thermal equilibrium with its environment, Kirchhoff's law requires:
```
ε(λ) + ρ(λ) = 1   ∀λ
```

`CombinedSource` is the canonical "real surface" — both reflected solar and thermal emission contribute, and the radiance is:
```
L_total(λ) = ε(λ) · B(λ, T)  +  (1 - ε(λ)) · BRDF_normalized(λ; geometry) · E_sun(λ) · cos θ_sun
```

This is the most common source type and is the **default** when a `SurfaceMaterial` has both `temperature` and `solar_geometry` available. The MWIR crossover regime falls out of this naturally; nothing in the code knows about "MWIR." It's just where the two terms become comparable.

**Validation**: At construction, the source verifies that ε + ρ = 1 within tolerance (default 1e-6) at every wavelength on the spectral grid. Violations raise `KirchhoffViolationError` with the offending wavelengths.

### 3.5 TabulatedRadianceSource

User provides `L(λ)` directly. This is the escape hatch — for cases where the user has measured radiance, or has results from a higher-fidelity tool (e.g., DIRSIG), or wants to mock a source for unit tests. No physical model is applied. The user owns the physics.

### 3.6 Point source variants

A point source carries `I(λ)` (W/sr/µm) instead of `L(λ)`. Three ways to obtain it:

| Source | Input | Output |
|--------|-------|--------|
| `DirectIntensitySource` | `I(λ)` table | `I(λ)` |
| `BlackbodyIntensitySource` | `T`, `A`, `ε(λ)` | `I(λ) = A · ε(λ) · B(λ, T)` |
| `IntegratedObjectIntensitySource` | `TargetGeometry`, materials | `I(λ) = Σ_facets A_f · cos θ_f · L_f(λ)` |

The first is the escape hatch. The second is the "I have a heated rocket plume of effective area A and temperature T" case. The third is the "I have a real geometry but the target is unresolved" case — the same geometry that would feed an extended source is integrated over visible facets to produce an intensity.

### 3.7 Background sources

Backgrounds are *separate from* signal sources. They produce `L_bg(λ)` which:
- Adds to the in-pixel radiance for sub-pixel and point-source regimes (clutter that the target sits on)
- Drives a noise term in all regimes (background photon shot noise)
- Sets the contrast reference for detection metrics

Background source types:

| Type | Use case |
|------|----------|
| `BlackbodyBackground` | "Background is a 295 K graybody with ε=0.95" |
| `SkyBackground` | Looking up: atmospheric thermal + scattered solar downwelling |
| `GroundBackground` | Looking down: terrain BRDF + thermal emission |
| `TabulatedBackground` | User-supplied `L_bg(λ)` |
| `ConstantBackground` | Constant L_bg across all wavelengths (smoke tests) |

The `none` case is `BlackbodyBackground(T=2.7, emissivity=1.0)` — the cosmic microwave background. There is no `None` background, because every photon that arrives at the focal plane comes from somewhere, and the noise budget needs that number even when it's small.

---

## 4. Materials: `SurfaceMaterial`

A `SurfaceMaterial` is the bridge between geometry and source physics. It carries the optical properties needed by every source type.

```python
@dataclass(frozen=True)
class SurfaceMaterial:
    """Optical and thermal properties of a surface.

    All spectral properties are stored on the global wavelength grid.
    Kirchhoff consistency (ε + ρ = 1) is enforced at construction.
    """
    name: str

    # Thermal
    temperature_K: float                   # surface temperature

    # Spectral optical properties (one or both must be specified)
    emissivity: SpectralData               # ε(λ), dimensionless [0,1]
    reflectance: SpectralData              # ρ(λ), dimensionless [0,1]

    # BRDF model
    brdf_model: BRDFModel                  # LAMBERTIAN | PHONG
    brdf_params: dict                      # phong_exponent, specular_fraction, ...

    # Optional thermodynamic context
    in_thermal_equilibrium: bool = True    # if False, Kirchhoff not enforced

    def __post_init__(self):
        # Validate spectral grids match
        # Validate ε ∈ [0,1] and ρ ∈ [0,1]
        # If in_thermal_equilibrium and both provided:
        #     check ε(λ) + ρ(λ) = 1 ± 1e-6 at every λ
        # If only one provided:
        #     derive the other via Kirchhoff
        ...
```

**Construction shortcuts:**
- `SurfaceMaterial.graybody(T, emissivity_scalar)` — flat ε across all λ.
- `SurfaceMaterial.from_library(name)` — looks up in a built-in library (aluminum, paint_white, vegetation, water, concrete, ...).
- `SurfaceMaterial.from_file(path)` — reads ε(λ) or ρ(λ) from CSV/ENVI.

**Library scope for v1**: ~20 common materials. Library is a YAML file shipped under `data/materials/` keyed by name. Each entry has at minimum ε(λ) (or ρ(λ)) and a default temperature.

**Out of scope for v1**: Anisotropic materials, polarization-dependent BRDF, temperature-dependent ε(λ, T), bidirectional transmission (translucent materials).

---

## 5. Target Geometry

### 5.1 Primitive shapes

Each primitive is a parameterized surface that can compute `projected_area(view_direction)` and enumerate `visible_facets(view_direction)`.

| Primitive | Parameters | Faceting |
|-----------|------------|----------|
| `Sphere` | `radius` | Lat/lon mesh, default 32×16 |
| `Cylinder` | `radius`, `length` | Side: 32 strips; caps: 16 wedges |
| `Box` | `length`, `width`, `height` | 6 faces (1 facet each — flat) |
| `FlatPlate` | `length`, `width` | 1 facet (front), 1 facet (back) |
| `Cone` | `base_radius`, `height` | 16 lateral facets + 16 base wedges |

Faceting density is configurable via `geometry.facet_density` (multiplier on defaults). Each facet carries: vertices, area, outward normal, and a material reference (default = whole-object material).

### 5.2 `TargetGeometry`

```python
@dataclass
class TargetGeometry:
    """A complete target: one or more primitives with materials and orientation."""
    primitives: tuple[Primitive, ...]
    transforms: tuple[Transform, ...]      # one per primitive
    material_assignments: dict[FacetID, str]  # facet → material name
    orientation: EulerAngles               # body frame → scene frame
    position: tuple[float, float, float]   # body origin in scene frame, m

    def projected_area(self, view_direction: np.ndarray) -> float:
        """Sum of A_f · max(0, n̂_f · v̂) over all facets."""

    def visible_facets(self, view_direction: np.ndarray) -> list[Facet]:
        """Facets with n̂_f · v̂ > 0. No occlusion test in v1."""

    def centroid(self) -> tuple[float, float, float]: ...
```

**Coordinate convention**: Per RADIANT_Conventions.md, the body frame is right-handed with +Z aligned with the primitive's "long axis" where applicable. Euler angles are intrinsic ZYX (yaw, pitch, roll). The view direction is `(observer_position - target_position).normalized()` in the scene frame.

**Occlusion**: v1 does **not** perform self-occlusion or inter-primitive occlusion testing. A facet is "visible" if its outward normal has a positive component along the view direction. This is correct for convex single primitives and an approximation otherwise. Occlusion is on the deferred list with reason: "needed only for concave geometries; users with concavity can use a higher-fidelity tool."

**Composite assembly**: A target can be a list of primitives with per-primitive transforms. Materials are assigned per facet via the `material_assignments` dict. A common case ("the whole object is one material") is shorthand: a `default_material` field on `TargetGeometry` propagates to any unassigned facet.

### 5.3 Per-facet radiance

Once visible facets are known, each facet computes its radiance via its assigned source(s):

```
L_facet(λ) = Σ_sources L_source(λ; material, geometry_context)
```

The total observed radiance is the area-weighted average of visible-facet radiances:
```
L_target(λ) = (1 / A_proj) · Σ_visible A_f · cos θ_f · L_facet(λ)
```

This integral is what makes "geometry + materials" path produce the same `ResolvedTarget` shape as "direct radiance" path: both produce a single `L(λ)` and a single `A_proj`.

---

## 6. The Five Unified Input Paths

```
              ┌──────────────────────────────────┐
              │     User configuration           │
              └──────────────────────────────────┘
                              │
       ┌──────────┬───────────┼──────────┬──────────────────┐
       ▼          ▼           ▼          ▼                  ▼
  ┌────────┐ ┌─────────┐ ┌─────────┐ ┌──────────┐ ┌──────────────┐
  │ Direct │ │Geometry │ │Sub-pixel│ │  Direct  │ │  Physical    │
  │radiance│ │+materials│ │params  │ │intensity │ │object → I(λ) │
  └────────┘ └─────────┘ └─────────┘ └──────────┘ └──────────────┘
       │          │           │          │                  │
       └──────────┴───────────┼──────────┴──────────────────┘
                              ▼
              ┌──────────────────────────────────┐
              │       ResolvedTarget             │
              │  (consumed by SourceStage)       │
              └──────────────────────────────────┘
```

### Path 1: Direct radiance

**User provides**: `L(λ)`, `projected_area`, `range`, `background_radiance`.  
**Skipped**: All geometry, all material physics.  
**ResolvedTarget population**:
- `spectral_radiance` ← user input
- `spectral_intensity` ← `radiance × projected_area`
- `geometry` ← `None`
- `materials` ← `None`
- `input_path` ← `DIRECT_RADIANCE`

**Use case**: Sarah has a measured spectral radiance from a calibration target and wants to predict SNR.

### Path 2: Geometry + materials (the canonical path)

**User provides**: `TargetGeometry` (one or more primitives with materials), observer geometry, solar geometry (if reflected solar is in play).  
**Computed**: Visible facets, per-facet radiance, area-weighted integration, projected area.  
**ResolvedTarget population**:
- `spectral_radiance` ← integrated facet radiance
- `spectral_intensity` ← `radiance × projected_area`
- `geometry` ← user input (preserved)
- `materials` ← user input (preserved)
- `input_path` ← `GEOMETRY`

**Use case**: Mike has a 3D model of a satellite and wants to predict at-aperture irradiance from a ground sensor.

### Path 3: Sub-pixel parameters

**User provides**: `target_radiance` (or temperature → blackbody), `background_radiance` (or T_bg → blackbody), `fill_fraction` (target's fraction of pixel area).  
**Skipped**: All geometry. `projected_area` is computed as `fill_fraction × pixel_solid_angle × range²`.  
**ResolvedTarget population**:
- `spectral_radiance` ← `fill_fraction · L_target + (1 - fill_fraction) · L_background`  
  (i.e., the in-pixel mean radiance — the chain sees this as a single equivalent radiance)
- `spectral_intensity` ← computed from area
- `background_radiance` ← user-provided background
- `input_path` ← `SUB_PIXEL`
- `tentative_regime` ← forced to `SUB_PIXEL`

**Note on the radiance combination**: The sub-pixel math could equivalently keep `L_target` and `L_background` separate and let the chain combine them. We do the combination here so the chain sees one radiance everywhere — but we preserve the `background_radiance` for the noise budget. This is a deliberate denormalization: it makes the chain simpler at the cost of a small loss of inspectability.

**Use case**: Detection-of-small-targets analysis where the user has a SWAG on target temperature and wants to know detection range.

### Path 4: Direct intensity (point source)

**User provides**: `I(λ)` directly, `range`.  
**Skipped**: Geometry, materials, projected area (set to 0).  
**ResolvedTarget population**:
- `spectral_intensity` ← user input
- `spectral_radiance` ← `intensity / (small reference area)`. By convention, set to `intensity / (1e-12 m²)` so the chain has a non-degenerate "extended-source representation" if it ever needs one. The actual physics for point sources uses intensity, not radiance.
- `projected_area_m2` ← 0
- `angular_extent_rad` ← 0
- `input_path` ← `DIRECT_INTENSITY`
- `tentative_regime` ← forced to `POINT_SOURCE`

**Use case**: Star observations, missile plume models, calibrated point sources.

### Path 5: Physical object → integrated intensity

**User provides**: `TargetGeometry` + materials, but the user *expects* the target to be unresolved.  
**Computed**: Same per-facet integration as Path 2, but the result is converted to intensity:
```
I(λ) = Σ_visible A_f · cos θ_f · L_f(λ)
```
**ResolvedTarget population**:
- `spectral_intensity` ← integrated
- `spectral_radiance` ← `intensity / projected_area` (still well-defined)
- `geometry` ← preserved
- `input_path` ← `PHYSICAL_OBJECT`
- `tentative_regime` ← computed normally (may end up POINT_SOURCE *or* SUB_PIXEL depending on PSF)

**Distinction from Path 2**: Path 5 is identical to Path 2 in computation. The only difference is that Path 5 is *expected* to be unresolved by the user — and is the path users select when they want to clearly state intent. The actual regime is still computed.

**Use case**: Mike has a satellite model and wants to know at what range it becomes unresolved.

### Why five paths and not three?

We could collapse {Direct radiance, Direct intensity} into one and {Geometry, Physical object} into one. We don't, because:

1. **Direct radiance vs. direct intensity** is a regime-of-thought distinction, not just a computation. Users who think in radiance care about extended-source performance. Users who think in intensity care about point-source performance. Forcing them to convert (and choose a fictitious area) introduces error and confusion.
2. **Geometry vs. physical object** is the same distinction at a different level. Path 2 says "I want extended-target performance from this geometry." Path 5 says "I want point-source performance from this geometry." Both are valid, both call the same computational kernel.

The five-way taxonomy lines up with the user mental models documented in RADIANT_Personas.md.

---

## 7. Auto Regime Detection

### 7.1 Definitions

- `θ_target`: target angular extent at observer = `√(projected_area) / range`
- `θ_PSF`: PSF FWHM in radians (set in OpticsStage)
- `θ_IFOV`: instantaneous field of view per pixel = `pixel_pitch / focal_length`

### 7.2 Thresholds

```
POINT_SOURCE   if  θ_target  <  α_point  · θ_PSF
EXTENDED       if  θ_target  >  α_ext    · θ_IFOV
SUB_PIXEL      otherwise
```

Default values:
- `α_point = 0.3`  (point-source threshold)
- `α_ext   = 3.0`  (extended threshold)

These are exposed as parameters (`regime.point_source_threshold`, `regime.extended_threshold`) and can be overridden.

### 7.3 Two-stage dispatch

Per RADIANT_Signal_Chain_Architecture.md, regime is computed in two stages:

**Stage 1 — Tentative (in `SourceStage`)**: PSF is unknown. Use `θ_IFOV` as a proxy for PSF FWHM (this is correct for diffraction-unlimited systems and conservative otherwise):
```
tentative_regime = classify(θ_target, θ_IFOV, θ_IFOV)
```

**Stage 2 — Final (in `OpticsStage`)**: PSF is now known. Reclassify:
```
final_regime = classify(θ_target, θ_PSF, θ_IFOV)
```

If `final_regime ≠ tentative_regime`, the chain logs a regime transition with both values and the reason (e.g., "PSF FWHM 12 µrad > IFOV 8 µrad caused EXTENDED → SUB_PIXEL transition"). The downstream `SpectralIntegrationStage` and `PerformanceStage` always use `final_regime`.

### 7.4 Override

The user may force a regime via `regime.override`:
```
auto         — use computed regime (default)
force_point  — force POINT_SOURCE regardless of geometry
force_subpixel
force_extended
```

Overrides are recorded in the provenance record. Use cases:
- Comparing regime treatments on the same target (sensitivity studies)
- Debugging regime-boundary cases
- Reproducing third-party tool results that fix the regime

### 7.5 The boundary case

What if `θ_target` falls between `α_point · θ_PSF` and `α_ext · θ_IFOV`? It's `SUB_PIXEL`. The thresholds are intentionally chosen so that `SUB_PIXEL` is the catch-all middle band, because the sub-pixel math degrades gracefully into both endpoints:
- As `fill_fraction → 1`, sub-pixel reduces to extended.
- As `fill_fraction → 0`, sub-pixel reduces to point-source.

This is the reason the sub-pixel regime exists: it bridges the discontinuity between the other two.

---

## 8. Parameter Inventory

All parameters use the dot-path namespace `source.*` and `regime.*`. Tolerances are statistical defaults, not validation bounds. All values in the table are in `input_unit`; canonical units are listed when different.

### 8.1 Top-level dispatch (3 parameters)

| Name | Description | Type | Unit | Default | Range | Tolerance |
|------|-------------|------|------|---------|-------|-----------|
| `source.input_path` | Which of the 5 input paths to use | enum | — | — (required) | direct_radiance, geometry, sub_pixel, direct_intensity, physical_object | — |
| `source.name` | User-facing target name | str | — | "target" | — | — |
| `source.range_m` | Observer-target range | float | m | — (required) | [1.0, 1e9] | 1% |

### 8.2 Geometry shape parameters (Path 2 / Path 5) (15 parameters)

| Name | Description | Type | Unit | Default | Range |
|------|-------------|------|------|---------|-------|
| `source.geometry.shape` | Primitive type | enum | — | — | sphere, cylinder, box, flat_plate, cone, composite |
| `source.geometry.sphere.radius` | Sphere radius | float | m | — | (0, 1e6] |
| `source.geometry.cylinder.radius` | Cylinder radius | float | m | — | (0, 1e6] |
| `source.geometry.cylinder.length` | Cylinder length | float | m | — | (0, 1e6] |
| `source.geometry.box.length` | Box length (along body X) | float | m | — | (0, 1e6] |
| `source.geometry.box.width` | Box width (along body Y) | float | m | — | (0, 1e6] |
| `source.geometry.box.height` | Box height (along body Z) | float | m | — | (0, 1e6] |
| `source.geometry.flat_plate.length` | Flat plate length | float | m | — | (0, 1e6] |
| `source.geometry.flat_plate.width` | Flat plate width | float | m | — | (0, 1e6] |
| `source.geometry.cone.base_radius` | Cone base radius | float | m | — | (0, 1e6] |
| `source.geometry.cone.height` | Cone height | float | m | — | (0, 1e6] |
| `source.geometry.composite_file` | Path to composite definition (YAML) | str | — | — | — |
| `source.geometry.facet_density` | Facet count multiplier | float | — | 1.0 | [0.25, 16.0] |
| `source.geometry.position_x` | Body origin X in scene frame | float | m | 0.0 | [-1e9, 1e9] |
| `source.geometry.position_y` | Body origin Y in scene frame | float | m | 0.0 | [-1e9, 1e9] |
| `source.geometry.position_z` | Body origin Z in scene frame | float | m | 0.0 | [-1e9, 1e9] |

### 8.3 Geometry orientation (4 parameters)

| Name | Description | Type | Unit | Default | Range | Tolerance |
|------|-------------|------|------|---------|-------|-----------|
| `source.orientation.yaw` | Yaw (intrinsic Z) | float | deg → rad | 0.0 | [-180, 180] | 1.0 deg |
| `source.orientation.pitch` | Pitch (intrinsic Y) | float | deg → rad | 0.0 | [-90, 90] | 1.0 deg |
| `source.orientation.roll` | Roll (intrinsic X) | float | deg → rad | 0.0 | [-180, 180] | 1.0 deg |
| `source.orientation.frame` | Reference frame for Euler angles | enum | — | "scene" | scene, lvlh, eci | — |

### 8.4 Material parameters (single-material case) (12 parameters)

For multi-material objects, the user specifies a material map file (`source.material_map_file`) and material definitions live in a library or YAML.

| Name | Description | Type | Unit | Default | Range | Tolerance |
|------|-------------|------|------|---------|-------|-----------|
| `source.material.name` | Material name (library lookup if no spectral file) | str | — | "graybody" | — | — |
| `source.material.temperature` | Surface temperature | float | K | — | [0.0, 5000.0] | 5.0 K |
| `source.material.emissivity_value` | Scalar emissivity (used if no file) | float | — | 0.9 | [0.0, 1.0] | 0.05 |
| `source.material.emissivity_file` | Spectral emissivity CSV | str | — | — | — | — |
| `source.material.reflectance_value` | Scalar reflectance (derived if absent) | float | — | — | [0.0, 1.0] | 0.05 |
| `source.material.reflectance_file` | Spectral reflectance CSV | str | — | — | — | — |
| `source.material.brdf_model` | BRDF model | enum | — | "lambertian" | lambertian, phong | — |
| `source.material.brdf.phong_exponent` | Phong specular exponent | float | — | 10.0 | [1.0, 1000.0] | — |
| `source.material.brdf.specular_fraction` | Phong specular fraction | float | — | 0.0 | [0.0, 1.0] | 0.05 |
| `source.material.kirchhoff_enforce` | Enforce ε + ρ = 1 | bool | — | True | — | — |
| `source.material.kirchhoff_tolerance` | Allowed deviation | float | — | 1e-6 | [0.0, 1e-2] | — |
| `source.material_map_file` | Multi-material assignment CSV | str | — | — | — | — |

### 8.5 Source physics dispatch (8 parameters)

| Name | Description | Type | Unit | Default | Range |
|------|-------------|------|------|---------|-------|
| `source.thermal.enabled` | Compute thermal source | bool | — | True | — |
| `source.reflected_solar.enabled` | Compute reflected solar | bool | — | True | — |
| `source.combined.enabled` | Combine via Kirchhoff (if both above enabled) | bool | — | True | — |
| `source.tabulated.radiance_file` | User-supplied L(λ) (Path 1) | str | — | — | — |
| `source.tabulated.radiance_unit` | Unit of tabulated radiance | enum | — | "W/m2/sr/um" | W/m2/sr/um, W/cm2/sr/um |
| `source.tabulated.intensity_file` | User-supplied I(λ) (Path 4) | str | — | — | — |
| `source.tabulated.intensity_unit` | Unit of tabulated intensity | enum | — | "W/sr/um" | W/sr/um, W/sr/nm |
| `source.tabulated.projected_area` | Projected area (Path 1 only) | float | m² | — | (0, 1e12] |

### 8.6 Solar geometry (for reflected solar) (5 parameters)

| Name | Description | Type | Unit | Default | Range | Tolerance |
|------|-------------|------|------|---------|-------|-----------|
| `source.solar.spectrum` | Reference solar spectrum | enum | — | "kurucz" | kurucz, astm_e490, blackbody_5778, tabulated |
| `source.solar.spectrum_file` | Tabulated spectrum (if enum=tabulated) | str | — | — | — |
| `source.solar.distance_au` | Sun-target distance | float | AU | 1.0 | [0.1, 50.0] | 0.001 |
| `source.solar.zenith_angle` | Solar zenith at target | float | deg → rad | 30.0 | [0.0, 90.0] | 1.0 deg |
| `source.solar.azimuth_angle` | Solar azimuth at target | float | deg → rad | 0.0 | [0.0, 360.0] | 1.0 deg |

### 8.7 Sub-pixel path (Path 3) (8 parameters)

| Name | Description | Type | Unit | Default | Range | Tolerance |
|------|-------------|------|------|---------|-------|-----------|
| `source.sub_pixel.fill_fraction` | Target's fraction of pixel area | float | — | — | (0.0, 1.0] | 0.01 |
| `source.sub_pixel.target_radiance_file` | Spectral radiance of target | str | — | — | — | — |
| `source.sub_pixel.target_temperature` | Alt: target T (graybody) | float | K | — | [0.0, 5000.0] | 5.0 K |
| `source.sub_pixel.target_emissivity` | Alt: target ε (graybody) | float | — | 0.95 | [0.0, 1.0] | 0.02 |
| `source.sub_pixel.background_radiance_file` | Spectral radiance of background | str | — | — | — | — |
| `source.sub_pixel.background_temperature` | Alt: background T (graybody) | float | K | — | [0.0, 5000.0] | 5.0 K |
| `source.sub_pixel.background_emissivity` | Alt: background ε (graybody) | float | — | 0.95 | [0.0, 1.0] | 0.02 |
| `source.sub_pixel.contrast_definition` | How to compute target contrast | enum | — | "weber" | weber, michelson, log |

### 8.8 Point source path direct (Path 4) (3 parameters)

(`source.tabulated.intensity_file` and `source.tabulated.intensity_unit` from §8.5 are reused for Path 4.)

| Name | Description | Type | Unit | Default | Range | Tolerance |
|------|-------------|------|------|---------|-------|-----------|
| `source.point.intensity_value` | Scalar intensity (single-band) | float | W/sr | — | (0, 1e9] | 1% |
| `source.point.bandcenter` | Band center for scalar intensity | float | µm | — | [0.1, 30.0] | — |
| `source.point.bandwidth` | Equivalent bandwidth for scalar intensity | float | µm | — | (0, 30.0] | — |

### 8.9 Background source (8 parameters)

| Name | Description | Type | Unit | Default | Range | Tolerance |
|------|-------------|------|------|---------|-------|-----------|
| `source.background.type` | Background source model | enum | — | "blackbody" | blackbody, sky, ground, tabulated, constant |
| `source.background.temperature` | T for blackbody/sky/ground | float | K | 295.0 | [2.7, 5000.0] | 5.0 K |
| `source.background.emissivity` | ε for blackbody background | float | — | 0.95 | [0.0, 1.0] | 0.02 |
| `source.background.radiance_file` | L_bg(λ) for tabulated background | str | — | — | — | — |
| `source.background.constant_value` | Flat L_bg for constant background | float | W/m²/sr/µm | 0.0 | [0.0, 1e6] | — |
| `source.background.zenith_angle` | View zenith for sky/ground BG | float | deg → rad | 0.0 | [0.0, 90.0] | — |
| `source.background.material` | Material name (ground BG) | str | — | "concrete" | — | — |
| `source.background.include_in_signal` | Add BG to in-pixel radiance | bool | — | True | — | — |

### 8.10 Regime control (3 parameters)

| Name | Description | Type | Unit | Default | Range |
|------|-------------|------|------|---------|-------|
| `regime.point_source_threshold` | α_point | float | — | 0.3 | (0.0, 1.0] |
| `regime.extended_threshold` | α_ext | float | — | 3.0 | [1.0, 100.0] |
| `regime.override` | Force a regime | enum | — | "auto" | auto, force_point, force_subpixel, force_extended |

### 8.11 Parameter count

| Group | Count |
|-------|-------|
| Top-level dispatch | 3 |
| Geometry shapes | 16 |
| Geometry orientation | 4 |
| Material (single) | 12 |
| Source physics dispatch | 8 |
| Solar geometry | 5 |
| Sub-pixel | 8 |
| Point source direct | 3 |
| Background | 8 |
| Regime control | 3 |
| **Total** | **70** |

Comfortably inside the 50-100 target. The bulk are optional — a typical config sets 10-15 parameters and lets defaults fill in the rest.

---

## 9. Dispatch Logic

`SourceStage` runs this state machine on every chain invocation:

```python
def source_stage(state: ChainState, params: ParameterSet) -> ChainState:
    path = params.get("source.input_path")

    if path == "direct_radiance":
        target = build_from_direct_radiance(params)
    elif path == "geometry":
        geometry = build_geometry(params)
        materials = build_materials(params)
        target = build_from_geometry(geometry, materials, params, regime_as_extended=True)
    elif path == "sub_pixel":
        target = build_from_sub_pixel(params)
    elif path == "direct_intensity":
        target = build_from_direct_intensity(params)
    elif path == "physical_object":
        geometry = build_geometry(params)
        materials = build_materials(params)
        target = build_from_geometry(geometry, materials, params, regime_as_extended=False)
    else:
        raise ValueError(f"Unknown input_path: {path}")

    # Tentative regime classification
    target = classify_tentative_regime(target, params)

    # Build background and attach
    target = attach_background(target, params)

    return state.with_target(target)
```

Notes:
1. The five branches each return a `ResolvedTarget` with all fields populated. The downstream code does not branch on path.
2. `build_from_geometry` is called from both Path 2 and Path 5; the only difference is which projected-area-vs-PSF outcome is "expected." Both go through tentative regime classification, which may surprise the user — that's the point.
3. The validation work (Kirchhoff consistency, ε ∈ [0,1], spectral grid alignment) happens inside `build_materials` and is the same for all paths that use materials.
4. `attach_background` always runs, even for Path 4 point sources, because the noise budget needs the background contribution at the focal plane.

---

## 10. Construction Examples

### 10.1 Path 2: Spacecraft over a city

```python
from radiant.api import RadiantSession

session = RadiantSession.from_yaml("vnir_satellite.yaml")
session.set("source.input_path", "geometry")
session.set("source.geometry.shape", "box")
session.set("source.geometry.box.length", 4.0)
session.set("source.geometry.box.width", 2.0)
session.set("source.geometry.box.height", 1.5)
session.set("source.material.name", "aluminum_painted_white")
session.set("source.material.temperature", 290.0)
session.set("source.solar.zenith_angle", 30.0)
session.set("source.range_m", 500_000.0)
session.set("source.background.type", "ground")
session.set("source.background.material", "concrete")
result = session.run()
```

### 10.2 Path 4: Calibration star

```python
session.set("source.input_path", "direct_intensity")
session.set("source.tabulated.intensity_file", "vega.csv")
session.set("source.range_m", 7.7e16)         # 8.1 light years
session.set("source.background.type", "blackbody")
session.set("source.background.temperature", 2.7)
result = session.run()
```

### 10.3 Path 3: Sub-pixel target

```python
session.set("source.input_path", "sub_pixel")
session.set("source.sub_pixel.target_temperature", 600.0)
session.set("source.sub_pixel.target_emissivity", 0.85)
session.set("source.sub_pixel.background_temperature", 295.0)
session.set("source.sub_pixel.background_emissivity", 0.92)
session.set("source.sub_pixel.fill_fraction", 0.05)
session.set("source.range_m", 50_000.0)
result = session.run()
```

---

## 11. Open Design Questions

1. **Material library scope**: How many built-in materials ship with v1? Proposal: 20 (aluminum, paint_white, paint_black, paint_grey, vegetation_green, vegetation_dry, water_calm, water_rough, soil_dry, soil_wet, sand, snow, ice, concrete, asphalt, glass, steel, copper, gold, blackbody). Library file format: YAML, with each material's spectral data in a sibling CSV.

2. **Composite geometry file format**: Proposal: YAML with primitives, transforms, and material assignments inline. Schema TBD. Alternative: STL/OBJ import — deferred to v2 because mesh-based per-facet material assignment is a usability problem.

3. **`spectral_intensity` for extended sources**: We populate it as `radiance × projected_area`. This is correct for an isotropic emitter only. For non-isotropic targets, the proper calculation requires direction-dependent integration. For v1, document the assumption and accept the simplification. The extended-source chain doesn't use `spectral_intensity` anyway — it's there for inspectability and for the regime-transition case.

4. **Per-facet temperatures**: A `SurfaceMaterial` carries one temperature. Multi-temperature objects (sun-lit vs. shadowed surfaces of a satellite) need either multiple materials (one per facet group) or a per-facet temperature override. Proposal: support a `temperature_map_file` analogous to `material_map_file`. Out of scope for the parameter inventory above; revisit if needed.

5. **Background as a Source**: Should `BackgroundSource` inherit from `SpectralRadianceSource` and just be tagged "background"? Proposal: keep them separate. Backgrounds and signal sources have different downstream consumers (signal goes through EE_box; background goes through both EE_box and the noise budget) and unifying them obscures that.

6. **Tabulated input units**: Currently we accept a small fixed enum of units. Should we support arbitrary units via the unit registry? Proposal: yes — but only after the unit registry has the full set of radiometric units registered. Track via a TODO in `units.py`.

7. **Solar spectrum at non-Earth distances**: We scale `E_sun` by `(1 AU / d)²`. This assumes a point sun, which fails for very close encounters (Mercury, sun-grazers). Out of scope for v1.

8. **Polarization**: Out of scope per RADIANT_Scope_Decisions.md. This affects BRDF (we use unpolarized BRDF only) and filter transmission (we use intensity transmission). Documented here as a known approximation.

---

## 12. Cross-references

- `RadiometricFrame` and `NoiseTerm` definitions: RADIANT_Signal_Chain_Architecture.md §4
- Regime two-stage dispatch: RADIANT_Signal_Chain_Architecture.md §6.2
- ParameterDef and ParameterSet: RADIANT_Parameter_System.md §3
- Coordinate convention: RADIANT_Conventions.md §2
- Wavelength grid and SpectralData: RADIANT_Parameter_System.md §6
