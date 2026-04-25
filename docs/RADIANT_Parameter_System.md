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
    name: str               # Dot-path: "sensor.optics.aperture_diameter"
    description: str        # Dense, specific: "Entrance pupil diameter"
    dtype: type             # float, int, str, bool
    canonical_unit: str     # Internal unit per Conventions: "m", "rad", "s", "e-/s"
    input_unit: str         # User-facing unit: "m", "deg", "urad", "ms"
    default: Any | None     # Default value in input_unit, or None if required
    bounds: tuple | None    # (min, max) in input_unit, or None
    enum_values: list | None  # For categorical: ["Si", "HgCdTe", "InSb", "InGaAs"]
    group: str | None       # Consistency group: "optics_fno"
    tags: set[str]          # Metadata: {"detector", "noise", "mwir", "lwir"}
```

Key properties:
- `frozen=True`: definitions are immutable after creation.
- `bounds` are in `input_unit`, not `canonical_unit`. The user thinks in input units; validation should too.
- `default=None` means the parameter is **required** — the resolver will error if it's not provided.
- `tags` enable filtering ("show me all detector parameters", "what parameters matter in LWIR?").

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

---

## Parameter Naming Convention

### Dot-path namespaces

Parameters are organized hierarchically by dot-separated namespaces:

```
sensor.optics.aperture_diameter       # m
sensor.optics.focal_length            # m
sensor.optics.f_number                # dimensionless
sensor.optics.obscuration_ratio       # dimensionless (0–1)
sensor.optics.wfe_rms                 # waves (at reference wavelength)
sensor.optics.n_surfaces              # int
sensor.optics.temperature             # K

sensor.detector.material              # enum: "HgCdTe", "InSb", "Si", "InGaAs"
sensor.detector.pixel_pitch           # m
sensor.detector.fill_factor           # dimensionless (0–1)
sensor.detector.cutoff_wavelength     # µm
sensor.detector.peak_qe              # dimensionless (0–1)
sensor.detector.dark_current          # e-/s/pixel (at operating temp)
sensor.detector.read_noise            # e- RMS
sensor.detector.full_well             # e-
sensor.detector.operating_temp        # K
sensor.detector.ipc_coupling          # dimensionless (0–1)
sensor.detector.diffusion_length      # m
sensor.detector.n_pixels_x            # int (cross-track)
sensor.detector.n_pixels_y            # int (along-track)

sensor.readout.integration_time       # s
sensor.readout.frame_rate             # Hz
sensor.readout.n_tdi                  # int
sensor.readout.cds_enabled            # bool
sensor.readout.n_coadds               # int
sensor.readout.adc_bits               # int
sensor.readout.gain                   # e-/DN
sensor.readout.binning_x              # int
sensor.readout.binning_y              # int

sensor.filter.center_wavelength       # µm
sensor.filter.bandwidth               # µm (FWHM)
sensor.filter.peak_transmission       # dimensionless (0–1)
sensor.filter.shape                   # enum: "gaussian", "tophat", "butterworth"
sensor.filter.oob_rejection           # dimensionless

geometry.observer_altitude            # m
geometry.target_altitude              # m
geometry.slant_range                  # m
geometry.look_angle                   # rad (input: deg)
geometry.solar_zenith                 # rad (input: deg)
geometry.solar_azimuth                # rad (input: deg)
geometry.observer_latitude            # rad (input: deg)
geometry.observer_type                # enum: "space", "airborne", "ground"
geometry.target_type                  # enum: "space", "airborne", "ground"

atmosphere.model                      # enum: "simple", "standard", "modtran"
atmosphere.visibility                 # m (input: km)
atmosphere.standard_atmosphere        # enum: "tropical", "midlat_summer", "midlat_winter",
                                      #        "subarctic_summer", "subarctic_winter", "us_standard"
atmosphere.modtran_file               # str (file path)
atmosphere.cloud_optical_depth        # dimensionless
atmosphere.cloud_fraction             # dimensionless (0–1)

target.temperature                    # K
target.temperature_hot                # K (for non-uniform: hot component)
target.temperature_cool               # K (for non-uniform: cool component)
target.hot_fraction                   # dimensionless (0–1)
target.emissivity                     # dimensionless (0–1), scalar or reference to spectral data
target.reflectance                    # dimensionless (0–1), Lambertian
target.area                           # m²
target.velocity                       # m/s (for smear computation)

background.temperature                # K
background.emissivity                 # dimensionless (0–1)
background.reflectance                # dimensionless (0–1)
background.clutter_sigma              # dimensionless (σ_clutter / L_background)

platform.jitter_rms                   # rad (input: µrad)
platform.drift_rate                   # rad/s (input: µrad/s)
platform.smear_velocity               # m/s (image plane velocity)

mission.age                           # s (input: years, for radiation damage)
mission.total_dose                    # krad (for radiation damage)
```

### Naming rules

1. All lowercase, underscores separating words: `aperture_diameter`, not `ApertureDiameter` or `aperture-diameter`.
2. No unit in the name. The unit is metadata on the definition. `aperture_diameter` not `aperture_diameter_m`.
3. Namespace depth is 2: `category.parameter_name`. No deeper nesting. The category groups parameters by physical subsystem.
4. Boolean parameters are named as adjectives or states: `cds_enabled`, not `use_cds` or `cds`.
5. Count parameters are prefixed with `n_`: `n_tdi`, `n_coadds`, `n_pixels_x`.

---

## Defaults

Each parameter definition includes a default value or `None` (required).

### Default categories

1. **Required (no default):** Parameters that fundamentally define the scenario. There is no sensible default for aperture diameter — the user must choose a sensor.
   - `sensor.optics.aperture_diameter`: None (required)
   - `sensor.detector.pixel_pitch`: None (required)
   - `target.temperature`: None (required)
   - `geometry.slant_range`: None (required)

2. **Defaulted to common value:** Parameters where a reasonable assumption covers 80% of use cases.
   - `sensor.readout.cds_enabled`: True (most modern ROICs use CDS)
   - `sensor.readout.n_coadds`: 1
   - `sensor.readout.n_tdi`: 1 (no TDI)
   - `sensor.readout.binning_x`: 1
   - `sensor.readout.binning_y`: 1
   - `sensor.optics.obscuration_ratio`: 0.0 (unobscured by default)
   - `sensor.detector.fill_factor`: 1.0
   - `sensor.detector.ipc_coupling`: 0.0
   - `atmosphere.cloud_fraction`: 0.0 (clear sky)
   - `atmosphere.cloud_optical_depth`: 0.0
   - `background.clutter_sigma`: 0.0

3. **Defaulted to "off" for optional effects:** Stubbed or optional parameters default to the value that disables the effect.
   - `platform.jitter_rms`: 0.0 (no jitter)
   - `platform.drift_rate`: 0.0 (no drift)
   - `target.hot_fraction`: 0.0 (uniform temperature)
   - `mission.age`: 0.0 (beginning of life)

### Default documentation

Every default value includes a one-line justification in the schema:

```python
ParameterDef(
    name="sensor.readout.cds_enabled",
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
@dataclass
class ConsistencyGroup:
    name: str
    parameters: list[str]
    constraint: str                            # human-readable: "f_number = focal_length / aperture_diameter"
    derivations: dict[str, Callable]           # {free_param: function(known_values) -> value}
```

### Resolution algorithm

1. Count how many parameters in the group are user-specified.
2. If exactly N−1 are specified: derive the Nth using the appropriate rule. Set provenance = DERIVED.
3. If all N are specified: validate consistency. If |computed − specified| > tolerance, raise error with diagnostic message showing the inconsistency.
4. If fewer than N−1 are specified: check if any have defaults. Apply defaults, then re-evaluate. If still underdetermined, raise an error listing what's missing.

### v1 consistency groups

```python
CONSISTENCY_GROUPS = [
    ConsistencyGroup(
        name="optics_fno",
        parameters=[
            "sensor.optics.f_number",
            "sensor.optics.focal_length",
            "sensor.optics.aperture_diameter",
        ],
        constraint="f_number = focal_length / aperture_diameter",
        derivations={
            "sensor.optics.f_number": lambda p: p["sensor.optics.focal_length"] / p["sensor.optics.aperture_diameter"],
            "sensor.optics.focal_length": lambda p: p["sensor.optics.f_number"] * p["sensor.optics.aperture_diameter"],
            "sensor.optics.aperture_diameter": lambda p: p["sensor.optics.focal_length"] / p["sensor.optics.f_number"],
        },
    ),
    ConsistencyGroup(
        name="readout_timing",
        parameters=[
            "sensor.readout.integration_time",
            "sensor.readout.frame_rate",
            # duty_cycle is derived from these two, not a group member
        ],
        constraint="frame_rate <= 1 / integration_time",
        derivations={
            "sensor.readout.integration_time": lambda p: 1.0 / p["sensor.readout.frame_rate"],
            "sensor.readout.frame_rate": lambda p: 1.0 / p["sensor.readout.integration_time"],
        },
    ),
    ConsistencyGroup(
        name="gsd",
        parameters=[
            "sensor.optics.focal_length",
            "sensor.detector.pixel_pitch",
            # GSD is a derived output, not a group member — it requires geometry too
        ],
        constraint="ifov = pixel_pitch / focal_length",
        derivations={
            "sensor.optics.focal_length": lambda p: p["sensor.detector.pixel_pitch"] / p["_ifov"],
            "sensor.detector.pixel_pitch": lambda p: p["_ifov"] * p["sensor.optics.focal_length"],
        },
    ),
]
```

---

## Dependency Tracking

### DAG structure

Parameters can depend on other parameters via derivation rules. The resolver maintains a directed acyclic graph (DAG):

```
sensor.optics.aperture_diameter ──┐
                                  ├──▶ sensor.optics.f_number (derived)
sensor.optics.focal_length ───────┘
                                  │
                                  ├──▶ _ifov (derived)
sensor.detector.pixel_pitch ──────┘
                                  │
                                  ├──▶ _gsd (derived)
geometry.slant_range ─────────────┘
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
```

### Tracking

Every resolved parameter carries:

```python
@dataclass
class ResolvedValue:
    value: Any                             # In canonical units
    input_value: Any                       # In input units (as the user provided it)
    provenance: Provenance
    source: str                            # "user", "config:sensor_abc.yaml", "default", "derived:f/D"
    derived_from: dict[str, Any] | None    # For DERIVED: {param_name: value_used}
    timestamp: str                         # ISO 8601 when this value was set/computed
```

### Provenance audit

The entire resolved parameter set can be serialized to a provenance record:

```json
{
    "radiant_version": "0.1.0",
    "resolved_at": "2026-04-06T14:30:00Z",
    "parameters": {
        "sensor.optics.aperture_diameter": {
            "value": 0.3,
            "canonical_unit": "m",
            "input_value": 0.3,
            "input_unit": "m",
            "provenance": "user_set",
            "source": "user"
        },
        "sensor.optics.f_number": {
            "value": 4.0,
            "canonical_unit": "",
            "input_value": 4.0,
            "input_unit": "",
            "provenance": "derived",
            "source": "derived:focal_length/aperture_diameter",
            "derived_from": {
                "sensor.optics.focal_length": 1.2,
                "sensor.optics.aperture_diameter": 0.3
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
params.explain("sensor.optics.f_number")
# Returns:
# "sensor.optics.f_number = 4.0 (dimensionless)
#  Provenance: DERIVED
#  Rule: f_number = focal_length / aperture_diameter
#  From: sensor.optics.focal_length = 1.2 m (USER_SET)
#        sensor.optics.aperture_diameter = 0.3 m (USER_SET)
#  Consistency group: optics_fno"

params.explain("sensor.readout.cds_enabled")
# Returns:
# "sensor.readout.cds_enabled = True
#  Provenance: DEFAULT
#  Justification: CDS is standard on modern HgCdTe and CMOS ROICs; eliminates kTC noise"
```

For downstream outputs (SNR, NEDT, NIIRS), the explainability chain extends through the computation:

```python
result.explain("snr")
# Returns:
# "SNR = 47.3
#  Signal: 12,450 e- (from source radiance × A × Ω × τ × QE × t_int)
#  Noise: 263 e- RMS (quadrature sum of 12 terms)
#    Shot noise: 111.6 e- (√signal)
#    Dark current noise: 89.2 e- (√(J_dark × t_int))
#    Read noise: 25.0 e- (spec)
#    ... [full noise budget]
#  Top 3 parameters by sensitivity:
#    sensor.optics.aperture_diameter: ∂SNR/∂D = +312 /m
#    sensor.readout.integration_time: ∂SNR/∂t = +2340 /s
#    sensor.detector.dark_current: ∂SNR/∂J = -0.0012 /(e-/s)"
```

---

## Spectral Data Store

### Common wavelength grid

All spectral data is interpolated onto a single common wavelength grid before any physics computation. The grid is defined by parameters:

```
spectral.lambda_min         # µm — default: auto from filter
spectral.lambda_max         # µm — default: auto from filter
spectral.n_points           # int — default: 500
spectral.grid_type          # enum: "uniform_wavelength", "uniform_wavenumber", "from_modtran"
```

If `spectral.grid_type = "from_modtran"`, the grid is extracted from the MODTRAN output file and used directly (no interpolation of MODTRAN data — everything else interpolates onto it).

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
| `qe` | `sensor.detector.material`, `sensor.detector.cutoff_wavelength`, `sensor.detector.peak_qe` | Computed from material model or loaded from file |
| `filter_transmission` | `sensor.filter.center_wavelength`, `sensor.filter.bandwidth`, `sensor.filter.peak_transmission`, `sensor.filter.shape` | Computed from analytical shape model |
| `tau_atm` | `atmosphere.modtran_file` or `atmosphere.model` + params | Loaded from MODTRAN or computed from simple model |
| `path_radiance` | `atmosphere.modtran_file` or `atmosphere.model` + params | Loaded from MODTRAN or computed |
| `atm_emission` | `atmosphere.modtran_file` or `atmosphere.model` + params | Loaded from MODTRAN or computed |
| `solar_irradiance` | None (reference spectrum) | Loaded from built-in data file |
| `optical_transmission` | `sensor.optics.n_surfaces`, per-surface reflectance, or bulk τ_opt | Computed or loaded |
| `target_emissivity` | `target.emissivity` (scalar) or file path | Scalar → constant array, or loaded from spectral library |

---

## Configuration File Format

Parameters are specified in YAML. The dot-path namespace maps to YAML nesting:

```yaml
# scenario_example.yaml
sensor:
  optics:
    aperture_diameter: 0.3       # m
    focal_length: 1.2            # m
    obscuration_ratio: 0.33
    wfe_rms: 0.07                # waves
    temperature: 280             # K

  detector:
    material: HgCdTe
    pixel_pitch: 18.0e-6         # m
    cutoff_wavelength: 5.0       # µm
    peak_qe: 0.75
    dark_current: 500            # e-/s/pixel
    read_noise: 25               # e-
    full_well: 1.5e6             # e-
    operating_temp: 80           # K

  readout:
    integration_time: 0.005      # s (= 5 ms)
    cds_enabled: true
    adc_bits: 14
    gain: 100                    # e-/DN
    n_tdi: 1

  filter:
    center_wavelength: 4.2       # µm
    bandwidth: 0.5               # µm
    peak_transmission: 0.9
    shape: tophat

geometry:
  observer_altitude: 600000      # m (= 600 km)
  observer_type: space
  target_type: ground
  look_angle: 0                  # deg (nadir)
  solar_zenith: 30               # deg

atmosphere:
  model: modtran
  modtran_file: data/midlat_summer_mwir.tape7

target:
  temperature: 300               # K
  emissivity: 0.95
  area: 10.0                     # m²

background:
  temperature: 290               # K
  emissivity: 0.96

platform:
  jitter_rms: 3.0                # µrad
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
| Sarah (P1) | Sweep one parameter, hold others constant | `ParameterSet.sweep("sensor.optics.aperture_diameter", [0.15, 0.20, ..., 0.60])` returns list of resolved sets |
| Mike (P2) | Inspect every noise term independently | Provenance + explainability on all derived noise values |
| Raj (P3) | Load a sensor config and specify only the scenario | Config file layering: sensor config + scenario overrides |
| Lisa (P4) | Batch run across target × atmosphere × sensor | Cross-product of config files → list of ParameterSets |
| Tom (P5) | Override WFE, see MTF effect | Direct `params.set()` override with instant re-resolution |
| Dr. Chen (P6) | Full provenance for reproducibility | Provenance audit record attached to every output |
| Karen (P7) | Compare predicted vs. measured; adjust one param to close gap | Sensitivity analysis via `params.sensitivity("snr", "sensor.detector.dark_current")` |
