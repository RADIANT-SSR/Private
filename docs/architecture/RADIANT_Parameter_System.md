# RADIANT Parameter System Design

**Date:** 2026-04-06  
**Status:** Accepted  
**Depends on:** RADIANT_Conventions.md  
**Scope:** Defines the parameter representation, resolution, validation, and provenance system that underlies all RADIANT computation.

---

## Critical Decision: Spectral Arrays

### Choice: **(c) Hybrid**

Scalar parameters go through the full parameter system (named, typed, validated, toleranced, dependency-tracked, provenanced). Spectral arrays — wavelength-dependent quantities like QE(λ), τ_atm(λ), T_filter(λ) — live in a parallel **SpectralDataStore**, not in the scalar parameter resolver.

### Justification

**Why not (a) — treat spectral arrays as parameters:**
- A QE(λ) curve has 500–5000 points. Putting each through the resolver with validation, tolerance, provenance tracking is absurd overhead.
- Tolerance on a spectral curve is ambiguous: do you perturb each point independently? Shift the curve? Scale it? The answer depends on the physics (QE tolerance is a peak-QE uncertainty + cutoff-wavelength uncertainty — both scalar).
- Users don't "set" QE(λ) point by point. They select a detector material or load a file. The scalar parameter is the material name or file path; the array is derived.

**Why not (b) — scalars only, arrays in computation layer:**
- Some spectral data IS user input (a MODTRAN tape7 file, a measured QE curve). It needs to be loaded, validated, and tracked — it can't just appear inside a computation module with no provenance.
- Filter transmission is defined by scalar parameters (λ_c, Δλ, T_peak, OOB_rejection) but consumed as an array T_filter(λ). There must be a defined place where this computation happens.

**Why (c) — hybrid:**
- Clean separation of concerns: scalar parameters are *configuration*, spectral data is *physical state*.
- Many spectral arrays are computed from scalar parameters: QE from (material, cutoff_wavelength, peak_qe); filter from (λ_c, Δλ, T_peak, shape); emissivity from (material_name). The scalars go through the resolver; the arrays are generated downstream.
- Some spectral arrays are loaded from files (MODTRAN output, measured data). The file path is a parameter; the loaded data goes into the SpectralDataStore.
- All spectral data is interpolated onto a common wavelength grid before any physics computation. The grid definition (λ_min, λ_max, N_points) is itself a set of scalar parameters.
- Tolerances are clean: perturb the scalar parameters (peak_QE ± 5%, cutoff_wavelength ± 0.1 µm), regenerate the spectral curve. No ambiguity.

### Architecture

```
┌─────────────────────┐         ┌──────────────────────┐
│   ParameterSet      │         │  SpectralDataStore    │
│  (scalar values)    │────────▶│  (wavelength arrays)  │
│                     │ generates│                      │
│  - aperture_diam    │         │  - qe(λ)             │
│  - focal_length     │         │  - tau_atm(λ)        │
│  - peak_qe          │─────┐   │  - filter_t(λ)       │
│  - filter_center_wl │     │   │  - emissivity(λ)     │
│  - modtran_file     │──┐  │   │  - solar_irrad(λ)    │
│  ...                │  │  │   │  ...                  │
└─────────────────────┘  │  │   └──────────────────────┘
                         │  │            ▲
                    load │  │ compute    │ interpolate to
                    file │  │ from       │ common grid
                         │  │ scalars    │
                         ▼  ▼            │
                   ┌─────────────────────┘
                   │  SpectralGenerators
                   │  (one per spectral quantity)
                   └──────────────────────
```

---

## Parameter Class Design

### ParameterDef — Schema Definition

Every parameter in RADIANT is defined once in a schema. The schema is the single source of truth for what parameters exist, what they mean, and what values are legal.

```python
@dataclass(frozen=True)
class ParameterDef:
    name: str               # Dot-path: "optics.aperture_diameter_m"
    description: str        # Dense, specific: "Entrance pupil diameter"
    dtype: type             # float, int, str, bool
    canonical_unit: str     # Internal unit per Conventions: "m", "rad", "s", "e-/s"
    input_unit: str         # User-facing unit: "m", "deg", "urad", "ms"
    default: Any | None = None      # Default value in input_unit; None means required
    bounds: tuple[float, float] | None = None  # (min, max) in input_unit
    enum_values: tuple[str, ...] | None = None  # For categorical (dtype=str only)
    group: str | None = None        # Consistency group name: "fnumber"
    tags: frozenset[str] = frozenset()  # Metadata: {"detector", "noise", "mwir"}
    default_justification: str = ""     # One-line rationale for a non-obvious default
    deprecated_aliases: frozenset[str] = frozenset()  # Old names (renames), warn + redirect
    required_unless: str | None = None  # Alternative param that supersedes this one (Gap 66)
    is_file_path: bool = False          # str value names a data file — stored portably (CU-177)
```

Key properties:
- `frozen=True`: definitions are immutable after creation.
- `bounds` are in `input_unit`, not `canonical_unit`. The user thinks in input units; validation should too.
- `default=None` means the parameter is **required** — the resolver will error if it's not provided.
- `tags` enable filtering ("show me all detector parameters", "what parameters matter in LWIR?").
- `deprecated_aliases` (Gap 12): old dot-paths for renamed parameters. `set`/`get`/`set_tolerance`/`clear_input` resolve an alias to the canonical name with a `DeprecationWarning`. Aliases may not collide with defined names and are validated at `ParameterSet` construction. Current aliases: `optics.cold_stop_efficiency` → `optics.nearfield_fraction`.
- `tags` regime-relevance convention (Gap 85, 2026-07-16): a tag of the form `regime:<scene_type>` (`regime:extended` / `regime:sub_pixel` / `regime:point_source`) declares that the parameter matters only for those **declared** scene types (`source.scene_type`). A def with no `regime:` tag is regime-independent. Consumed by the GUI Source form, which disables (never hides) irrelevant rows with an explanatory tooltip when a scene type is declared; `auto` gates nothing. Currently authored on the source-stage background / contrast-reference / fill-fraction parameters; other stages are unauthored (relevance there is regime-independent until tagged).
- `required_unless` (Gap 66; comma-list since Gap 69): names one or more comma-separated alternative parameters, any of which supersedes this required one. When the alternative is explicitly set (non-empty, non-None input), the requirement is waived and the parameter is left **unresolved** — `get()` raises if any code path reads it anyway, so no phantom value is ever consumed. An explicitly-set empty string does not waive the requirement. Only valid on required (`default=None`) parameters. Current use: `detector.qe_value` is required unless **either** `detector.qe_table_path` **or** `detector.qe_material` is set (`required_unless="detector.qe_table_path,detector.qe_material"`, `detector/_schema.py`) — a spectral QE curve (from file or the bundled library) supersedes the scalar.
- `is_file_path` (CU-177): marks a `dtype=str` parameter whose value names a data file on disk (a CSV of ε(λ)/ρ(λ)/L(λ), a QE table, a Zernike file, a tabulated-atmosphere file). **Serialization stores such a value relative to the output YAML's directory** (`save_config` / `Sensor.save` / `Sensor.to_yaml(relative_to=...)`), and **loading resolves it back to absolute against the source YAML's directory** (`load_config` when the source is a file). A config that references a repo-internal data file therefore stays portable across checkout locations, machines, and OSes (relative paths are written forward-slashed, Rule 30); configs written before CU-177 with absolute paths still load unchanged. Not set for system/environment paths that are **not** part of the portable config surface — `atmosphere.modtran.binary_path`, `atmosphere.modtran.cache_dir`, `atmosphere.interpolated_data_dir`, and the staged MODTRAN `tape7_*`/`flux_path` files, which stay verbatim. A relative path loaded from a bare dict (no file anchor) is left as-is.

### Unit Conversion

Units are **not** runtime types (no astropy.units). The Conventions document locks all canonical units. Each ParameterDef carries a conversion factor computed once at schema load:

```python
# Precomputed conversion table
UNIT_CONVERSIONS = {
    ("deg", "rad"): math.pi / 180,
    ("urad", "rad"): 1e-6,
    ("ms", "s"): 1e-3,
    ("us", "s"): 1e-6,
    ("cm", "m"): 1e-2,
    ("km", "m"): 1e3,
    ("mm", "m"): 1e-3,
    ("K", "K"): 1.0,        # identity
    ("m", "m"): 1.0,
    ("s", "s"): 1.0,
    ("rad", "rad"): 1.0,
    ("e-", "e-"): 1.0,
    ("e-/s", "e-/s"): 1.0,
    # ...
}

def convert(value, from_unit, to_unit):
    if from_unit == to_unit:
        return value
    return value * UNIT_CONVERSIONS[(from_unit, to_unit)]
```

Conversion happens exactly once: on `set()`. Internally, everything is in canonical units. On `get()` for display, convert back to input units.

**Unit-aware input (Gap 6).** `ParameterSet.set(name, value, unit=...)` (and `Sensor.set(dotpath, value, unit=...)`) accepts the caller's native unit and converts at the set boundary — the only place user-unit conversion happens (Rule 2). The value is converted `unit → canonical → input_unit` through the registered conversion table, then follows the normal input-unit validation path (bounds are checked after conversion, so `set("detector.qe_value", 150, unit="%")` fails the [0, 1] bounds check as 1.5). Percent (`"%"` → fraction) and `min` → s are registered for this purpose. Unknown units raise an actionable `ValueError` naming the parameter's native unit. The original value and unit are recorded in the resolved provenance `source` string. Without `unit=`, values are taken in `input_unit` (historical behavior, unchanged).

---

## Parameter Naming Convention

### Dot-path namespaces

Parameters are organized hierarchically by dot-separated namespaces:

```
optics.aperture_diameter_m            # m
optics.focal_length_m                 # m
optics.f_number                       # dimensionless
optics.obscuration_ratio              # dimensionless (0–1)
optics.wfe_rms_waves                  # waves (at optics.wfe_reference_wavelength_um)
optics.zernike_file                   # path — Zemax 'Zernike Standard Coefficients' export; loaded
                                      #   pre-chain (Rule 6), injects a ZERNIKE WavefrontError that
                                      #   supersedes the scalar WFE; report wavelength honored,
                                      #   wfe_reference_wavelength_um is the no-header fallback
optics.transmission_scalar            # dimensionless (0–1)
optics.scalar_emissivity              # dimensionless (0–1), scalar mode only; declared lumped-train emissivity, ε + τ ≤ 1
optics.optics_temperature_K           # K
optics.defocus_um                     # µm
optics.surface_roughness_nm           # nm, effective train RMS roughness (TIS scatter; 0 = off)
optics.scatter_halo_sigma_um          # µm, Gaussian scatter-halo width on the focal plane
optics.nearfield_fraction             # dimensionless (0–1); 0 = perfect cold stop, 1 = uncooled. INVERTED from vendor "cold stop efficiency" (= 1 − vendor). Deprecated alias: optics.cold_stop_efficiency (warns, Gap 12)
optics.stray.veiling_glare_fraction   # dimensionless (0–1)
optics.stray.veiling_glare_mtf        # int 0/1; 1 = spatial halo model (kernel + MTF pair), 0 = pedestal-only (default)
optics.stray.halo_sigma_um            # µm, Gaussian veiling-glare halo width on the focal plane

readout.electronics_sigma_um          # µm, equivalent Gaussian blur from amplifier bandwidth (x-axis only)

detector.pixel_pitch_x_um             # µm
detector.pixel_pitch_y_um             # µm
detector.fill_factor                  # dimensionless (0–1)
detector.qe_value                     # dimensionless (0–1)
detector.dark_rate_e_per_s            # e-/s/pixel (at reference temp)
detector.detector_temperature_K       # K
detector.ipc_coupling                 # dimensionless (0–1)
detector.charge_diffusion_length_m    # m
detector.n_pixels_cross               # int (cross-track)

readout.read_noise_e_rms              # e- RMS
readout.gain_e_per_dn                 # e-/DN
readout.adc_bits                      # int
readout.full_well_capacity_e          # e- (analog_well only — rejected if explicitly set under digital_counting)
readout.architecture                  # enum: "analog_well", "digital_counting" — DROIC dispatch (Gap 117;
                                      #   digital_counting is schema-only until Digital_Pixel_Readout_Plan Phase 1
                                      #   lands: ReadoutStage validates the parameters, then raises an actionable
                                      #   not-implemented error before any physics)
readout.counter_bits                  # int — in-pixel counter depth N; effective well = 2^N × count_packet_e
                                      #   (counting-only: rejected if explicitly set under analog_well)
readout.count_packet_e                # e- per count — charge-subtraction quantum (counting-only; REQUIRED > 0
                                      #   when architecture = digital_counting; schema default 0.0 = unset sentinel)
readout.residue_readout               # bool — read the analog residue through the existing ADC model
                                      #   (counting-only)
readout.max_count_rate_hz             # Hz — comparator dead-time flux ceiling (counting-only; 0.0 = unset
                                      #   ⇒ no ceiling, counter rollover governs)
readout.counting_mode                 # enum: "up", "up_down" — signed-differential background subtraction
                                      #   (plan Phase 4, D1/D6; counting-only; reference params rejected under "up")
readout.reference_source              # enum: "background_term" (sub-pixel/point-source only, D6),
                                      #   "user_level" (extended-scene fallback); up_down-only
readout.reference_rate_e_per_s        # e-/s — down-phase reference charge rate (REQUIRED > 0 under
                                      #   "user_level"; 0.0 = unset sentinel); up_down-only
readout.reference_integration_s       # s — down-phase duration (0.0 = unset ⇒ equal to the scene
                                      #   integration time, D7); up_down-only
readout.cds_enabled                   # int (1 = yes, 0 = no; dtype=int, default 1)
readout.n_tdi                         # int
readout.n_coadds                      # int
readout.binning_x_onchip              # int
readout.binning_y_onchip              # int

spectral_integration.filter_min_um    # µm
spectral_integration.filter_max_um    # µm
spectral_integration.integration_time_s  # s

geometry.sensor_altitude_m            # m
geometry.target_altitude_m            # m
geometry.site_elevation_m             # m — terrain elevation under the LOS (default 0 = MSL);
                                      #     references the Hufnagel-Valley Cn² SURFACE term only
                                      #     (CU-262, RADIANT_Atmosphere.md §7.1). Not derived from
                                      #     the LOS lower endpoint — see that section.
geometry.target.shape                 # enum: none/sphere/cylinder/flat_plate/box/cone — target spatial extent (ADR-0008; was source.target.shape, now a deprecated alias)
geometry.target.shape_radius_m        # m   (+ shape_length_m/width_m/height_m/base_radius_m)
geometry.target.shape_yaw_rad         # rad (+ shape_pitch_rad/shape_roll_rad) — body ZYX Euler
geometry.target.projected_area_m2     # m²  — projected area facing observer (0.0 = extended default)
geometry.path_zenith_rad              # rad (input: deg)
geometry.solar_zenith_rad             # rad (input: deg)
geometry.solar_azimuth_rad            # rad (input: deg)
geometry.ground_speed_m_s             # m/s
# Consumed by AtmosphereStage, PlatformStage, PerformanceStage,
# and (post-CU-009) by SourceStage's `_infer_los` for
# `LineOfSightGeometry` construction.  See RADIANT_Atmosphere.md §6.5.

atmosphere.model                      # enum: "simple", "exo", "tabulated", "modtran", "interpolated"
atmosphere.visibility_km              # km
atmosphere.precipitable_water_cm      # cm
atmosphere.standard_atmosphere        # enum: "tropical", "midlat_summer", "midlat_winter",
                                      #        "subarctic_summer", "subarctic_winter", "us_standard"
atmosphere.modtran.binary_path        # str (file path)
atmosphere.modtran.h2o_scale          # dimensionless
atmosphere.r0_m                       # m (Fried parameter)

source.target.temperature             # K
source.target.emissivity              # dimensionless (0–1)
source.target.emissivity_path         # str — 2-col CSV ε(λ); spectral thermal target ε(λ)·B(λ,T) (Gap 47); mutually exclusive with scalar ε / reflective / radiance / brightness-temp surfaces
source.target.is_hot_target           # bool — MWIR routing opt-out (CU-007); see source._inferrer matrix §3.2
source.target.reflectance             # dimensionless (0–1), Lambertian
# Target spatial extent (shape/dims/orientation/projected_area) moved to the
# geometry.target.* namespace (ADR-0008); source.target.shape*/projected_area_m2
# remain as deprecated aliases. Spectral/material params above stay in source.
source.target.range_m                 # m — deprecated alias of geometry.target_range_m (ADR-0006)
source.target.fill_fraction           # dimensionless (0–1) — sub-pixel, stays in source
source.background.temperature         # K
source.background.emissivity          # dimensionless (0–1)

platform.jitter_rms_urad              # rad (input: µrad)
platform.ground_velocity_m_s          # m/s
platform.smear_length_um              # µm (image-plane smear)

performance.detection_snr_threshold   # dimensionless; SNR at which a point
                                      # target counts as detected (Gap 77).
                                      # Default 5.0 (Rose criterion). The
                                      # in-chain detection-range solver bisects
                                      # to this threshold.
```

The nine parameter namespaces are `geometry`, `source`, `atmosphere`, `optics`, `platform`, `spectral_integration`, `detector`, `readout`, and `performance`. Every first segment is an owning stage — since ADR-0006 `geometry.*` is owned by `GeometryStage` (stage 0), which resolves the scene-geometry input modes and publishes the derived quantities; it is no longer a stage-less shared block. `performance` holds only analyst-tuned metric thresholds — most performance metrics are derived from upstream chain quantities and take no parameters.

Renames use `ParameterDef.deprecated_aliases` (warn-and-redirect at `set()`/`get()`): `source.target.range_m` → `geometry.target_range_m` and `platform.h_sensor` → `geometry.sensor_altitude_m` (CU-090 fold) — both ADR-0006, 2026-07-12.

### Naming rules (per ADR-D, `docs/adr/ADR-D-parameter-naming.md`, 2026-07-06)

1. All lowercase, underscores separating words: `aperture_diameter_m`, not `ApertureDiameter` or `aperture-diameter`.
2. Every dimensioned parameter carries a unit suffix: `_m`, `_um`, `_urad`, `_K`, `_rad`, `_s`, `_hz`, `_km`, `_cm`, `_e`, `_e_per_s`, `_e_rms`, `_m_s`, `_W_m2`, `_eV`, `_pct`, `_waves`, … (e.g. `optics.aperture_diameter_m`, `detector.pixel_pitch_x_um`). The suffix names the **input unit** — the unit a user supplies to `params.set()`, exactly as declared in the schema's `input_unit`. It usually coincides with the canonical unit; where they differ, the suffix follows the input unit (`pixel_pitch_x_um` accepts µm, stores meters canonically; `jitter_rms_urad` accepts µrad, stores rad). Dimensionless parameters (ratios, counts, flags, enums) have no suffix (`optics.f_number`, `detector.fill_factor`). The suffix is a human affordance; the `ParameterDef` remains the single source of truth for conversion.
3. Namespace depth is 2 or 3: `stage.parameter_name` or `stage.group.parameter_name`, where the group names a cohesive sub-model (`source.target.*`, `source.background.*`, `optics.stray.*`, `atmosphere.modtran.*`). The first segment is the owning stage; there is no `sensor.` super-prefix.
4. Boolean parameters are named as adjectives or states: `cds_enabled`, not `use_cds` or `cds`.
5. Count parameters are prefixed with `n_`: `n_tdi`, `n_coadds`, `n_pixels_cross`.

---

## Defaults

Each parameter definition includes a default value or `None` (required).

### Default categories

1. **Required (no default):** Parameters that fundamentally define the scenario. There is no sensible default for aperture diameter — the user must choose a sensor.
   - `optics.aperture_diameter_m`: None (required)
   - `optics.focal_length_m`: None (required, unless derived via the `fnumber` group)
   - `detector.pixel_pitch_x_um`: None (required)
   - `detector.pixel_pitch_y_um`: None (required)

2. **Defaulted to common value:** Parameters where a reasonable assumption covers 80% of use cases.
   - `readout.cds_enabled`: 1 (dtype=int, 1=yes/0=no; most modern ROICs use CDS)
   - `readout.n_coadds`: 1
   - `readout.n_tdi`: 1 (no TDI)
   - `readout.binning_x_onchip`: 1
   - `readout.binning_y_onchip`: 1
   - `optics.obscuration_ratio`: 0.0 (unobscured by default)
   - `detector.fill_factor`: 1.0
   - `source.target.temperature`: 300.0 K
   - `source.background.temperature`: 290.0 K

3. **Defaulted to "off" for optional effects:** Optional parameters default to the value that disables the effect.
   - `platform.jitter_rms_urad`: 0.0 (no jitter)
   - `detector.ipc_coupling`: 0.0 (no inter-pixel capacitance)
   - `detector.clutter_sigma`: 0.0 (no clutter)
   - `optics.defocus_um`: 0.0 (in focus)

### Default documentation

Every default value includes a one-line justification in the schema:

```python
ParameterDef(
    name="readout.cds_enabled",
    description="Correlated double sampling active",
    dtype=bool,
    canonical_unit="",
    input_unit="",
    default=True,
    bounds=None,
    default_justification="CDS is standard on modern HgCdTe and CMOS ROICs; "
                          "eliminates kTC noise"
)
```

---

## Tolerances

### Specification

Any scalar parameter can carry a tolerance specification for Monte Carlo / sensitivity analysis:

```python
@dataclass
class Tolerance:
    distribution: str          # "gaussian", "uniform", "truncated_gaussian", "log_normal"
    params: dict               # distribution-specific parameters, in input_unit

# Examples (all in input units):
# ±5% QE: 
Tolerance("gaussian", {"std_fraction": 0.05})  # std = 5% of nominal value

# Absolute jitter uncertainty:
Tolerance("gaussian", {"std": 0.5})            # ±0.5 µrad (in input_unit)

# Operating temperature range:
Tolerance("uniform", {"low": 75, "high": 85})  # 75–85 K

# WFE with hard limits:
Tolerance("truncated_gaussian", {"std": 0.02, "low": 0.0, "high": 0.2})  # waves
```

### Monte Carlo execution

1. For each trial, the resolver samples each toleranced parameter from its distribution.
2. The full dependency graph is re-resolved with the sampled values.
3. Spectral data is regenerated from the sampled scalars (e.g., sampled cutoff_wavelength → new QE(λ)).
4. The signal chain runs with the sampled parameter set.
5. Results are collected across N trials for statistical analysis.

### Sensitivity analysis

Single-parameter sensitivity: perturb one parameter by ±1σ, hold all others at nominal, record output change. This is a 2N+1 evaluation (N parameters × 2 perturbations + 1 nominal). Cheaper than full Monte Carlo for identifying dominant sensitivities.

---

## Consistency Groups

### Problem

Some parameters are linked by physics constraints: f/# = f / D. Given any 2 of {f, D, f/#}, the third is derived. The parameter system must handle this without requiring the user to know which one to leave unspecified.

### Design

A consistency group defines:
- A set of N linked parameters
- N derivation rules (one for each parameter that could be the free variable)
- The constraint equation for validation

```python
@dataclass(frozen=True)
class ConsistencyGroup:
    name: str
    parameters: tuple[str, ...]
    constraint: str                            # human-readable: "f_number = focal_length_m / aperture_diameter_m"
    derivations: dict[str, Callable]           # {free_param: function(known_values) -> value}
    tolerance: float = 1e-9                    # relative tolerance for the over-specification check
```

### Resolution algorithm

1. Count how many parameters in the group are user-specified.
2. If exactly N−1 are specified: derive the Nth using the appropriate rule. Set provenance = DERIVED.
3. If all N are specified: validate consistency. If |computed − specified| > tolerance, raise error with diagnostic message showing the inconsistency.
4. If fewer than N−1 are specified: check if any have defaults. Apply defaults, then re-evaluate. If still underdetermined, raise an error listing what's missing.

### v1 consistency groups

Groups are assembled in `radiant/api/_param_registry.py` (there is no module-level constant in `radiant.core.parameters`) and passed to the `ParameterSet` constructor: `ParameterSet(schema, groups)`. Two groups are defined:

```python
# radiant/api/_param_registry.py
_FNUMBER_GROUP = ConsistencyGroup(
    name="fnumber",
    parameters=(
        "optics.aperture_diameter_m",
        "optics.focal_length_m",
        "optics.f_number",
    ),
    constraint="f_number = focal_length_m / aperture_diameter_m",
    derivations={
        "optics.f_number": lambda kv: (
            kv["optics.focal_length_m"] / kv["optics.aperture_diameter_m"]
        ),
        "optics.focal_length_m": lambda kv: (
            kv["optics.aperture_diameter_m"] * kv["optics.f_number"]
        ),
        "optics.aperture_diameter_m": lambda kv: (
            kv["optics.focal_length_m"] / kv["optics.f_number"]
        ),
    },
    tolerance=1e-3,
)

def build_parameter_set() -> ParameterSet:
    schema = list(SRC_PARAMS + ATMO_PARAMS + OPT_PARAMS + ...)
    return ParameterSet(schema, [_FNUMBER_GROUP, _GROUND_SPEED_GROUP])
```

The second group **collapses a duplicate parameter** (Gap 75, 2026-07-11).
`platform.ground_velocity_m_s` (consumed by smear) and
`geometry.ground_speed_m_s` (consumed by the access-rate metric) are the same
physical quantity — the along-track ground velocity. Linking them as an
identity consistency group means setting either derives the other (one number
feeds both consumers) and setting both to disagreeing values raises the
over-specification error instead of silently using two different velocities:

```python
_GROUND_SPEED_GROUP = ConsistencyGroup(
    name="ground_speed",
    parameters=("platform.ground_velocity_m_s", "geometry.ground_speed_m_s"),
    constraint="platform.ground_velocity_m_s == geometry.ground_speed_m_s",
    derivations={
        "platform.ground_velocity_m_s": lambda kv: kv["geometry.ground_speed_m_s"],
        "geometry.ground_speed_m_s": lambda kv: kv["platform.ground_velocity_m_s"],
    },
    tolerance=1e-6,
)
```

Both parameters default to `0.0`, so an unset pair resolves to `0` (no motion).
The `Sensor.set_ground_velocity_from_orbit()` helper (Gap 75) derives the value
from `geometry.sensor_altitude_m` via `radiant.core.orbit.ground_track_speed_m_s`
for orbital platforms. The analogous altitude duplicate has been collapsed:
`platform.h_sensor` is now a **deprecated alias** of `geometry.sensor_altitude_m`
(warn-and-redirect at `set()`/`get()`, CU-090 fold / ADR-0006, 2026-07-12) — see
the `deprecated_aliases` note earlier in this section.

### Target-spec exclusivity — the resolve-time seam (CU-244)

The `source.target.*` user-entry surfaces (Target Definition Matrix §1 spec
forms) carry a family of **cross-parameter mutual-exclusivity rules** that are
not consistency groups — there is no derivation between the members, only the
constraint "set at most one door": the reflectance/albedo aliases (scalar and
`_path`), ρ vs the legacy (ε, T) thermal pair, ρ vs the S8/S10 absolute
radiance/intensity paths, ρ vs the S11/S12 brightness/radiance-temperature
forms, and the S11/S12 internal pairings.

These guards live in `radiant.source.target_spec` (one door-check function per
spec door, run in the inferrer's dispatch order S11 → S12 → S4/S5/S6 → S8 →
S10b → S10 → S1-with-ε(λ)) and are called from **two** places:

1. **Evaluate time** — the source inferrer's door builders call the door
   checks at the same points the historical inline blocks occupied, so
   `evaluate()` behaviour is unchanged (defence in depth). The message text is
   unchanged too, with one deliberate exception: CU-295 retargeted the `what=`
   prefix from `"source._inferrer: "` to `"source.target_spec: "`, because the
   named module no longer holds the check.
2. **Resolve time** — `Sensor.validate_target_spec()` runs the same functions
   with no physics, file I/O, or resolve required. Both views apply the same
   provenance rule — a resolved set reads `get_resolved(...).provenance`, an
   unresolved set reads `input_provenances()`, and `DEFAULT` and `DERIVED` both
   read as *not* user-set (CU-300: an over-specification is a statement about
   user input, so a value RADIANT computed must never trigger one; `SAMPLED`
   does count, a sweep axis being user intent). The GUI's clone-validate edit
   discipline calls this after each candidate `set` and rejects a conflict
   *the edit introduces* at the door — with the identical what/why/action
   `ParameterBoundsError` the evaluate-time path produces, by construction
   (same code).

Completeness checks ("S12 also needs its band edges") are deliberately **not**
part of the seam: a half-entered spec is a legitimate intermediate state while
a user types, and `evaluate()` remains the surface that reports what is
missing.

**The two entry points are symmetric (CU-293, owner ruling 2026-08-01).** They
were not, on landing: CU-244 left the S8, S10 and S10b door guards inlined in
the inferrer — so a conflict entered purely through those doors slipped past
the GUI editor and failed only at `evaluate()` — and the S11 door had no guard
against its S12 twin at all, so a `brightness_temperature_*` +
`radiance_temperature_K` pair *raised at the seam but evaluated silently*, the
S11 builder dispatching first and discarding the radiance-temperature surface
(a Rule-17 violation). CU-293 moved the three remaining door blocks into
`check_user_radiance_conflicts` / `check_point_intensity_conflicts` /
`check_user_intensity_conflicts` and added the missing S11-vs-S12 guard to
`check_brightness_temperature_conflicts`. CU-318 moved the last inlined door
guard, the ε(λ) door's `check_emissivity_path_conflicts`. Every door guard is
now registered at both entry points, so a pair either door knows about is
refused with the same message at both.

**The last asymmetry is closed (CU-323, owner ruling 2026-08-02).** CU-318
measured one residual case: the ε(λ) door dispatches *after* every other door,
and nine of the ten surfaces its guard lists open a door of their own, so at
`evaluate()` those doors returned first, the ε(λ) guard was never reached, and
`source.target.emissivity_path` was discarded in silence (a Rule-17 defect of
the same class CU-293 closed for S11/S12) while the seam refused the same
pairs. The owner extended the CU-293 ruling class: refusal is the correct
behaviour, so `check_emissivity_path_conflicts` is no longer a per-door guard
sitting last in dispatch order — it is a **pre-dispatch** check, run first in
`validate_target_spec` and first in `_inferrer._build_target_descriptor`. It is
a no-op unless `emissivity_path` is user-set and non-empty, so no single-door
spec can newly raise (measured at the ruling: none of the 67 shipped YAML
configs sets the surface). Running it in the same position at both entry points
also makes them report the same *first* error for a config that over-specifies
in more than one way, not just for a two-surface pair.

---

## Dependency Tracking

### DAG structure

Parameters can depend on other parameters via derivation rules. The resolver maintains a directed acyclic graph (DAG):

```
optics.aperture_diameter_m ──┐
                             ├──▶ optics.f_number (derived)
optics.focal_length_m ───────┘
                             │
                             ├──▶ _ifov (derived)
detector.pixel_pitch_x_um ───┘
                             │
                             ├──▶ _gsd (derived)
source.target.range_m ───────┘
```

### Resolution algorithm

1. **Collect inputs:** User-set values + config file values + defaults.
2. **Validate inputs:** Type check, bounds check, enum check on all provided values.
3. **Convert units:** All input-unit values → canonical-unit values.
4. **Resolve consistency groups:** Process each group as described above.
5. **Topological sort:** Order the derivation rules so that dependencies are computed before dependents.
6. **Execute derivations:** Compute each derived parameter in topological order.
7. **Post-validation:** Check all derived values against bounds.
8. **Freeze:** The resolved parameter set is immutable. Changing a parameter requires creating a new resolution pass.

### Cycle detection

The DAG is validated at schema registration time. If a cycle is detected (A depends on B depends on A), that's a schema bug, not a runtime error. Raise immediately with the cycle path.

### Invalidation

When a parameter changes (e.g., in a parametric sweep):
1. Find all downstream dependents via the DAG.
2. Mark them as stale.
3. Re-resolve only the stale subgraph, not the entire parameter set.
4. Regenerate any spectral data that depends on changed parameters.

---

## Provenance

### Provenance tags

```python
class Provenance(Enum):
    USER_SET = "user_set"       # Explicitly provided by user
    CONFIG_FILE = "config_file" # Loaded from a sensor/scenario config file
    DEFAULT = "default"         # From schema default
    DERIVED = "derived"         # Computed from other parameters
    SAMPLED = "sampled"         # Generated by Monte Carlo sampling
    PRESET = "preset"           # Applied from a named FPA preset (Gap 119)
```

`PRESET` (added at Gap 119 Phase 0) labels values applied from a named FPA
preset (`radiant.data.FPALibrary`); its `source` string is
`fpa:<part-name>/<source-key>` so every preset value traces to the citation in
the preset document. The apply path itself lands in the plan's Phase 2; user
and config values set later override preset values through the ordinary
last-write path, and the override is reported.

### Tracking

Every resolved parameter carries:

```python
@dataclass
class ResolvedValue:
    value: Any                             # In canonical units
    input_value: Any                       # In input units (as the user provided it)
    provenance: Provenance
    source: str                            # "user", "/path/to/sensor_abc.yaml", "default", "derived:f/D"
    derived_from: dict[str, Any] | None    # For DERIVED: {param_name: value_used}
    timestamp: str                         # ISO 8601 when this value was set/computed
```

**Source strings in use.** `source` is a free-form human-readable origin, not an enum;
the writers that populate it are:

| `source` | Written by |
|---|---|
| `"user"`, `"Sensor.set"`, `"Sensor.set_many"` | interactive / scripting edits |
| the YAML file path (or `"dict"`) | `radiant.io.config.load_config` |
| `"default: <justification>"` | schema defaults applied during resolution |
| `"derived: <constraint>"` | consistency-group derivation |
| `"config:<name>"` | a **configured** parameter's value, materialized for the configuration named `<name>` by `ConfigurationSet.sensor_for` (ADR-0010 D-C) |

The `config:<name>` form is what lets `Sensor.resolved()` / `Sensor.explain()` name the
owning configuration of a multi-configuration study with **zero new provenance
machinery**: a materialized configuration is an ordinary `Sensor` whose configured
values were set with `Provenance.USER_SET` and that source string. Note the ADR-0010
D-10 disambiguation convention: `<name>` here is a **configuration** (a member of a
configuration set), never a config *file* — file-sourced values carry the file path.

### Provenance audit

The entire resolved parameter set can be serialized to a provenance record:

```json
{
    "radiant_version": "0.1.0",
    "resolved_at": "2026-04-06T14:30:00Z",
    "parameters": {
        "optics.aperture_diameter_m": {
            "value": 0.3,
            "canonical_unit": "m",
            "input_value": 0.3,
            "input_unit": "m",
            "provenance": "user_set",
            "source": "user"
        },
        "optics.f_number": {
            "value": 4.0,
            "canonical_unit": "",
            "input_value": 4.0,
            "input_unit": "",
            "provenance": "derived",
            "source": "derived:focal_length_m/aperture_diameter_m",
            "derived_from": {
                "optics.focal_length_m": 1.2,
                "optics.aperture_diameter_m": 0.3
            }
        }
    }
}
```

This per-parameter dict is the `parameter_set` block of the §C13 provenance record returned by `ChainResult.to_provenance_record()`. The record also carries `input_file_hashes` — an ordered list of `(path, sha256)` pairs for every YAML consumed during the run. `radiant.io.config.load_config` populates this list by calling `ParameterSet.record_loaded_file(path, sha256)` after a successful YAML parse; in-memory dict sources record nothing (no path to hash).

Given the provenance record, any result is exactly reproducible.

---

## Explainability

Every parameter can answer: "why does this have this value?"

```python
params.explain("optics.f_number")
# Returns:
# "optics.f_number = 4.0 (dimensionless)
#  Provenance: DERIVED
#  Rule: f_number = focal_length_m / aperture_diameter_m
#  From: optics.focal_length_m = 1.2 m (USER_SET)
#        optics.aperture_diameter_m = 0.3 m (USER_SET)
#  Consistency group: fnumber"

params.explain("readout.cds_enabled")
# Returns:
# "readout.cds_enabled = 1
#  Provenance: DEFAULT
#  Justification: CDS is standard on modern HgCdTe and CMOS ROICs; eliminates kTC noise"
```

For downstream outputs, explainability is exposed by these **shipped** surfaces (there is no single `result.explain("snr")` method — it is a design target):

```python
# Noise breakdown for a computed metric (shipped):
result.explain_noise("dark")     # ChainResult.explain_noise(term) — io/results.py
result.noise_terms               # tuple[NoiseTerm] — the full per-term budget

# Parameter-level explanation (shipped):
sensor.explain("readout.cds_enabled")   # Sensor.explain(dotpath) — api/sensor.py

# Sweeps and sensitivities are Sensor / radiant.api surfaces (NOT ParameterSet):
sensor.sweep("optics.aperture_diameter_m", [0.15, 0.30, 0.45, 0.60])
```

**[DESIGN-TARGET]** A single unified `result.explain("snr")` that folds the signal chain, the full noise budget, and the top-3 parameter sensitivities into one narrative does not exist yet; assemble it today from `explain_noise` + the sensitivity API.

---

## Schema Introspection (Gap 70, 2026-07-11)

`ParameterSet` exposes a public introspection surface so GUIs, CLIs, and sweep
tooling never touch private state. This is the enumeration contract the GUI
parameter panel generates from.

```python
ps.parameter_defs()      # Mapping[str, ParameterDef] — read-only live view of the
                         # full schema keyed by dot-path; each ParameterDef carries
                         # dtype, canonical/input units, bounds, enum_values,
                         # default, description, tags, group, deprecated_aliases.
ps.parameter_def(name)   # Single ParameterDef; alias-aware (DeprecationWarning);
                         # unknown names raise UnknownParameterError (a
                         # RadiantError co-inheriting KeyError) with a
                         # did-you-mean hint (CU-073).
ps.consistency_groups()  # tuple[ConsistencyGroup, ...] in registration order.
ps.tolerances()          # Mapping[str, Tolerance] — read-only view.
ps.inputs()              # Mapping[str, Any] — explicit inputs only (name → raw
                         # input-unit value); defaults/derived excluded. The
                         # persistence surface: re-setting exactly these on a
                         # fresh set reproduces this resolution (Gap 67).
ps.is_resolved           # bool property: resolve() has run and no input changed.
ps.copy()                # Unresolved deep-enough copy: schema, groups, inputs
                         # (with provenance), tolerances, loaded-file records.
                         # The supported way to build sweep/clone variants.
```

The read-only views are `MappingProxyType` wrappers: mutation raises
`TypeError`, and the schema itself is fixed at `ParameterSet` construction.
Framework consumers (`cli/schema_cmd.py`, `api/sensitivity.py`,
`api/sweep.py`, `api/tolerance.py`, `api/sensor.py`) use only this surface —
`_defs`, `_groups`, `_inputs`, `_tolerances`, `_resolved_flag` are private and
carry no compatibility guarantee.

---

## Spectral Data Store

### Common wavelength grid

All spectral data is interpolated onto a single common wavelength grid before any physics computation. There is **no `spectral.*` parameter namespace**; the grid is built from the filter bandpass plus a point count:

```
grid = numpy.linspace(
    spectral_integration.filter_min_um,   # µm — lower filter edge (schema parameter)
    spectral_integration.filter_max_um,   # µm — upper filter edge (schema parameter)
    wavelength_points,                    # Sensor(...) constructor argument, NOT a schema param
)
```

The grid is uniform in wavelength (`Sensor._wavelength_grid`, `api/sensor.py`). MODTRAN and every other spectral table are interpolated **onto** this grid; there is no `grid_type` enum and no "use the MODTRAN grid directly" mode at this layer.

### SpectralData class

```python
@dataclass
class SpectralData:
    name: str                           # "qe", "tau_atm", "filter_transmission"
    wavelength_um: np.ndarray           # ascending, in µm
    values: np.ndarray                  # same length, in canonical units
    unit: str                           # "dimensionless", "W/m2/sr/um", etc.
    source: str                         # "file:data/qe_hgcdte.csv",
                                        # "computed:from filter_center_wavelength, filter_bandwidth",
                                        # "modtran:tape7.out"
    source_parameters: dict[str, Any]   # scalar params used to generate this data
```

### SpectralDataStore

```python
class SpectralDataStore:
    def __init__(self, grid: np.ndarray):
        self._grid = grid                       # common wavelength grid (µm, ascending)
        self._data: dict[str, np.ndarray] = {}  # name -> values on common grid
        self._metadata: dict[str, SpectralData] = {}  # name -> full SpectralData
    
    def add(self, data: SpectralData) -> None:
        """Interpolate data onto common grid and store."""
    
    def get(self, name: str) -> np.ndarray:
        """Return values on common grid."""
    
    def get_metadata(self, name: str) -> SpectralData:
        """Return full metadata including source and provenance."""
```

### Spectral generators

Each spectral quantity has a registered generator that either computes from scalar parameters or loads from a file:

| Spectral Data | Generator Input | Source |
|---------------|----------------|--------|
| `qe` | `detector.qe_value` (flat), `detector.qe_table_path` (file), or `detector.qe_material` (bundled library curve — Gap 69; path > material > scalar) | Constant array, loaded file, or library curve (0 past data span) |
| `filter_transmission` | `spectral_integration.filter_min_um`, `spectral_integration.filter_max_um` | Computed top-hat bandpass |
| `tau_atm` | `atmosphere.model` + model params (e.g. `atmosphere.tabulated_transmittance_file`) | Loaded from file or computed from simple model |
| `path_radiance` | `atmosphere.model` + model params | Loaded from file or computed |
| `atm_emission` | `atmosphere.model` + model params | Loaded from file or computed |
| `solar_irradiance` | None (reference spectrum) | Loaded from built-in data file |
| `optical_transmission` | `optics.transmission_scalar` or per-element data (`optics.transmission_input_mode`) | Computed or loaded |
| `target_emissivity` | `source.target.emissivity` (scalar) or `source.target.reflectance_path` | Scalar → constant array, or loaded from spectral library |

---

## Configuration File Format

Parameters are specified in YAML. The dot-path namespace maps to YAML nesting:

```yaml
# scenario_example.yaml — top-level keys are the stage namespaces
source:
  target:
    temperature: 300.0           # K
    emissivity: 0.95
  background:
    temperature: 290.0           # K
    emissivity: 0.96

atmosphere:
  standard_atmosphere: midlat_summer

geometry:
  sensor_altitude_m: 8000.0      # m

optics:
  aperture_diameter_m: 0.30      # m
  focal_length_m: 1.20           # m  (f/4.0)
  obscuration_ratio: 0.33
  wfe_rms_waves: 0.07            # waves
  optics_temperature_K: 280.0    # K
  transmission_scalar: 0.70

detector:
  pixel_pitch_x_um: 18.0         # µm
  pixel_pitch_y_um: 18.0         # µm
  qe_value: 0.70
  dark_rate_e_per_s: 100.0       # e-/s

spectral_integration:
  filter_min_um: 3.5             # µm
  filter_max_um: 5.0             # µm
  integration_time_s: 0.005      # s  (5 ms)

readout:
  read_noise_e_rms: 5.0          # e- RMS
  gain_e_per_dn: 32.0            # e-/DN
  adc_bits: 16
  cds_enabled: 1
  n_tdi: 1

platform:
  jitter_rms_urad: 3.0           # µrad
```

### Loading precedence

1. Schema defaults (lowest priority)
2. Sensor config file (e.g., `sensors/baseline_mwir.yaml`)
3. Scenario config file (e.g., `scenarios/desert_noon.yaml`)
4. Programmatic overrides via `params.set()` (highest priority)

Each layer records its provenance. If the same parameter appears in multiple layers, the highest-priority layer wins, and the provenance shows the winning source.

---

## Design Implications from Personas

| Persona | Parameter system requirement | How it's met |
|---------|----------------------------|-------------|
| Sarah (P1) | Sweep one parameter, hold others constant | `Sensor.sweep("optics.aperture_diameter_m", [0.15, 0.20, ..., 0.60])` (`api/sensor.py`; sweeps live on `Sensor`/`radiant.api`, not `ParameterSet`) |
| Mike (P2) | Inspect every noise term independently | Provenance + explainability on all derived noise values |
| Raj (P3) | Load a sensor config and specify only the scenario | Config file layering: sensor config + scenario overrides |
| Lisa (P4) | Batch run across target × atmosphere × sensor | Cross-product of config files → list of ParameterSets |
| Tom (P5) | Override WFE, see MTF effect | Direct `params.set()` override with instant re-resolution |
| Dr. Chen (P6) | Full provenance for reproducibility | Provenance audit record attached to every output |
| Karen (P7) | Compare predicted vs. measured; adjust one param to close gap | Sensitivity analysis via `Sensor.sensitivity("snr", "detector.dark_rate_e_per_s")` (`api/sensor.py`; on `Sensor`/`radiant.api`, not `ParameterSet`) |
