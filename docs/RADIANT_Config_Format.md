# RADIANT Configuration Format

**Date:** 2026-04-07
**Status:** Accepted
**Depends on:** RADIANT_Parameter_System.md, RADIANT_Conventions.md
**Scope:** Defines the canonical YAML configuration format, XLSX convenience view, Python API creation, CLI overrides, and validation. All RADIANT I/O flows through these interfaces.

---

## 1. YAML Canonical Format

YAML is the **source of truth** for all RADIANT configurations. Every other format (XLSX, JSON, Python dict) is derived from YAML or converts to it.

### 1.1 File Types

| File type | Naming convention | Purpose |
|-----------|------------------|---------|
| **Sensor config** | `sensors/<name>.yaml` | Defines a specific sensor: optics + detector + readout + filter. No target, geometry, or atmosphere. Reusable across scenarios. |
| **Scenario config** | `scenarios/<name>.yaml` | Defines a specific scenario: target + atmosphere + geometry + platform. References or overrides a sensor config. |
| **Full config** | `configs/<name>.yaml` | Complete self-contained run: all sections present. |
| **Partial config** | `partials/<name>.yaml` | Fragment imported by other configs. Contains only a subset of sections. |

A scenario config that imports a sensor config and overrides one parameter is the most common pattern. Both files together define the full parameter set.

### 1.2 YAML Structure and Naming

The dot-path parameter namespace maps directly to YAML nesting. A parameter `sensor.optics.aperture_diameter` maps to:

```yaml
sensor:
  optics:
    aperture_diameter: 0.30   # m
```

Top-level keys match the parameter namespace roots exactly:

| Top-level key | Parameter namespace | Contents |
|--------------|--------------------|-|
| `sensor` | `sensor.*` | `optics`, `detector`, `readout`, `filter` sub-keys |
| `geometry` | `geometry.*` | Observer/target positions, look angle, solar geometry |
| `atmosphere` | `atmosphere.*` | Model selection, MODTRAN file, standard atmosphere type |
| `target` | `target.*` | Temperature, emissivity, area, regime hints |
| `background` | `background.*` | Background temperature, emissivity, clutter |
| `platform` | `platform.*` | Jitter, drift, smear velocity |
| `mission` | `mission.*` | Age, radiation dose |
| `spectral` | `spectral.*` | Wavelength grid definition |

All parameter names follow the naming rules from RADIANT_Parameter_System.md: lowercase, underscore-separated, no unit in name.

**Inline comments are mandatory** for non-obvious values and any value not in SI base units:

```yaml
sensor:
  detector:
    dark_current: 500       # e-/s/pixel — at operating_temp; Rule 07 scaling enabled
    read_noise: 25          # e- RMS — Fowler-2 CDS mode
    full_well: 1.5e6        # e-
    operating_temp: 80      # K
    pixel_pitch: 18.0e-6    # m (= 18 µm)
    cutoff_wavelength: 5.0  # µm — HgCdTe cutoff
```

Scientific notation (`1.5e6`, `18.0e-6`) is preferred over long decimal strings. Units go in the comment.

### 1.3 Variable Substitution

Variables are defined at the top of a config in a `_vars:` block. They are substituted anywhere in the document using `${VAR_NAME}` syntax. Substitution is string-level: the YAML parser resolves variables before YAML is parsed. Arithmetic is not supported; use Python if you need arithmetic.

```yaml
_vars:
  ALT_M: 600000          # 600 km orbit altitude
  RANGE_M: 650000        # typical slant range at this altitude
  T_TINT_S: 0.005        # 5 ms integration time

geometry:
  observer_altitude: ${ALT_M}
  slant_range: ${RANGE_M}
  observer_type: space
  target_type: ground

sensor:
  readout:
    integration_time: ${T_TINT_S}
```

Variables can be overridden from the CLI: `radiant run config.yaml --var ALT_M=500000`. This is the primary mechanism for batch sweeps from shell scripts.

Variable names are SCREAMING_SNAKE_CASE to distinguish them from parameter names.

### 1.4 Inheritance (`_extends`)

A config file can declare a single parent config using `_extends:`. The parent is loaded first; the child's fields are deep-merged on top, field by field. Child fields override parent fields at any depth.

```yaml
# scenarios/mwir_clear.yaml — child
_extends: sensors/baseline_mwir.yaml

# Override only what differs from the sensor baseline:
geometry:
  observer_altitude: 600000
  slant_range: 650000
  look_angle: 0             # deg (nadir)
  solar_zenith: 30          # deg

atmosphere:
  model: modtran
  modtran_file: data/midlat_summer_mwir.tape7

target:
  temperature: 300
  emissivity: 0.95
  area: 10.0
```

```yaml
# sensors/baseline_mwir.yaml — parent
sensor:
  optics:
    aperture_diameter: 0.30
    focal_length: 1.20
    obscuration_ratio: 0.33
    wfe_rms: 0.07
    temperature: 280
  detector:
    material: HgCdTe
    pixel_pitch: 18.0e-6
    cutoff_wavelength: 5.0
    peak_qe: 0.75
    dark_current: 500
    read_noise: 25
    full_well: 1.5e6
    operating_temp: 80
  readout:
    integration_time: 0.005
    cds_enabled: true
    adc_bits: 14
    gain: 100
    n_tdi: 1
  filter:
    center_wavelength: 4.2
    bandwidth: 0.5
    peak_transmission: 0.9
    shape: tophat
```

**Deep merge rules:**
- Scalar values: child wins.
- Dict values: recursively merge. Child fields override parent fields; parent fields not in child are preserved.
- `_extends` chains are supported (grandparent → parent → child) up to 5 levels. Cycles are an error.
- `_extends` is resolved before `_imports`.

### 1.5 Imports (`_imports`)

A config file can include partial config files using `_imports:`. Each partial is a YAML file containing only a subset of the top-level keys. Partials are merged in order, then the current file's body is merged on top. This is the mechanism for composing sensor + atmosphere + target libraries.

```yaml
# configs/leo_mwir_clear_desert.yaml
_imports:
  - sensors/baseline_mwir.yaml
  - atmospheres/midlat_summer.yaml
  - targets/desert_vehicle.yaml

# Per-run overrides on top of the imports:
geometry:
  observer_altitude: 600000
  slant_range: 650000
  look_angle: 0
  solar_zenith: 30
```

`_imports` and `_extends` may coexist in one file. Resolution order:
1. Resolve `_extends` chain (grandparent → ... → parent)
2. Apply `_imports` in list order (each import deep-merged on top of prior state)
3. Apply current file body on top

This produces a deterministic, explicit merge. No implicit lookup paths.

### 1.6 Schema Version

Every config file should include a schema version comment at the top. This enables migration detection.

```yaml
# RADIANT config — schema v1
_extends: sensors/baseline_mwir.yaml
```

The schema version is not a validated field in v1, but the parser will log a warning if it is absent.

---

## 2. XLSX Convenience View

XLSX is not a source of truth. It is a **generated view** of a YAML config, editable in Excel, round-trippable back to YAML. Its purpose: reviewers and program managers who don't write YAML.

### 2.1 Generation

```bash
radiant export config.yaml --format xlsx --output config.xlsx
```

The generated workbook has one sheet per top-level namespace:

| Sheet | Contents |
|-------|---------|
| `sensor_optics` | All `sensor.optics.*` parameters |
| `sensor_detector` | All `sensor.detector.*` parameters |
| `sensor_readout` | All `sensor.readout.*` parameters |
| `sensor_filter` | All `sensor.filter.*` parameters |
| `geometry` | All `geometry.*` parameters |
| `atmosphere` | All `atmosphere.*` parameters |
| `target` | All `target.*` parameters |
| `background` | All `background.*` parameters |
| `platform` | All `platform.*` parameters |
| `provenance` | Run metadata: RADIANT version, generated date, source YAML path |

Each sheet has fixed columns:

| Column | Content |
|--------|---------|
| A — Parameter | Dot-path name (e.g., `sensor.optics.aperture_diameter`) |
| B — Value | Current value |
| C — Unit | User-facing unit |
| D — Description | One-line description from schema |
| E — Provenance | `user_set`, `default`, `derived`, `config_file` |
| F — Min | Lower bound (if any) |
| G — Max | Upper bound (if any) |

Cells in column B are editable. Column A, D, E, F, G are locked. Derived parameters (provenance = `derived`) are highlighted in light gray and their B cells are locked — they are shown for reference but cannot be set directly.

### 2.2 Round-Trip Back to YAML

```bash
radiant import config.xlsx --output config_edited.yaml
```

The importer reads column A (parameter name) and column B (value) from each sheet. It reconstructs the YAML nesting from the dot-path. The round-trip produces a flat YAML (no `_extends`, no `_imports`) with all parameters written explicitly. The user can then re-apply `_extends` manually if desired.

**Round-trip contract:**
- Scalar values only. Spectral arrays (QE curves, MODTRAN output) are not in the XLSX — those remain file references in the YAML.
- All values pass through validation before writing. Invalid values in the XLSX produce a column H error message.
- The round-tripped YAML is a `configs/<name>_from_xlsx.yaml` by convention.

---

## 3. Python API Creation

All config file formats can be constructed programmatically. The Python API is the primary development interface.

### 3.1 Creating a Sensor Config

```python
from radiant.api import SensorConfig

sensor = (
    SensorConfig("baseline_mwir")
    .optics(
        aperture_diameter=0.30,     # m
        focal_length=1.20,          # m
        # f_number is derived: 4.0
        obscuration_ratio=0.33,
        wfe_rms=0.07,               # waves RMS
        temperature=280,            # K
    )
    .detector(
        material="HgCdTe",
        pixel_pitch=18.0e-6,        # m
        cutoff_wavelength=5.0,      # µm
        peak_qe=0.75,
        dark_current=500,           # e-/s/pixel
        read_noise=25,              # e- RMS
        full_well=1.5e6,            # e-
        operating_temp=80,          # K
    )
    .readout(
        integration_time=0.005,     # s
        cds_enabled=True,
        adc_bits=14,
        gain=100,                   # e-/DN
    )
    .filter(
        center_wavelength=4.2,      # µm
        bandwidth=0.5,              # µm
        peak_transmission=0.90,
        shape="tophat",
    )
)

# Save to YAML
sensor.save("sensors/baseline_mwir.yaml")

# Or convert to dict
d = sensor.to_dict()
```

### 3.2 Creating a Scenario Config

```python
from radiant.api import ScenarioConfig

scenario = (
    ScenarioConfig("leo_mwir_clear")
    .geometry(
        observer_altitude=600_000,  # m
        observer_type="space",
        target_type="ground",
        look_angle=0,               # deg (nadir)
        solar_zenith=30,            # deg
    )
    .atmosphere(
        model="modtran",
        modtran_file="data/midlat_summer_mwir.tape7",
    )
    .target(
        temperature=300,            # K
        emissivity=0.95,
        area=10.0,                  # m²
    )
    .background(
        temperature=290,
        emissivity=0.96,
    )
    .platform(
        jitter_rms=3.0,             # µrad
    )
)

scenario.save("scenarios/leo_mwir_clear.yaml")
```

### 3.3 Combining Sensor and Scenario

```python
from radiant.api import Sensor

# From files:
sensor = Sensor.from_files(
    sensor="sensors/baseline_mwir.yaml",
    scenario="scenarios/leo_mwir_clear.yaml",
)

# From config objects:
sensor = Sensor.from_configs(sensor_cfg, scenario_cfg)

# From a single complete YAML:
sensor = Sensor.load("configs/leo_mwir_clear_full.yaml")

# From Python dict:
sensor = Sensor.from_dict({
    "sensor": {"optics": {"aperture_diameter": 0.30, ...}, ...},
    "geometry": {...},
    ...
})
```

---

## 4. CLI Overrides

The `radiant run` command accepts dot-path parameter overrides that override any value in the config file. CLI overrides have the highest priority in the loading precedence.

### 4.1 Syntax

```bash
# Single override
radiant run config.yaml --set sensor.optics.aperture_diameter=0.45

# Multiple overrides
radiant run config.yaml \
  --set sensor.optics.aperture_diameter=0.45 \
  --set sensor.readout.integration_time=0.008 \
  --set target.temperature=320

# Override a string parameter
radiant run config.yaml --set atmosphere.model=simple

# Override with a variable substitution
radiant run config.yaml --var ALT_M=500000 --var RANGE_M=550000
```

### 4.2 Output

```bash
# Write results to JSON
radiant run config.yaml --set sensor.optics.aperture_diameter=0.45 --output result.json

# Write provenance record
radiant run config.yaml --provenance provenance.json

# Dry run: validate only, no evaluation
radiant validate config.yaml --set sensor.optics.aperture_diameter=0.45

# Explain a derived parameter
radiant explain config.yaml sensor.optics.f_number
# → f_number = 4.0 (derived: focal_length / aperture_diameter)
#   focal_length = 1.20 m (user_set, config:sensors/baseline_mwir.yaml)
#   aperture_diameter = 0.45 m (user_set, cli_override)
```

### 4.3 Batch Sweep from CLI

A lightweight parameter sweep from the CLI using shell expansion. For proper sweeps with result collection, use the Python API.

```bash
for D in 0.15 0.20 0.25 0.30 0.35 0.40; do
  radiant run config.yaml \
    --set sensor.optics.aperture_diameter=$D \
    --output results/snr_D${D}.json
done
```

---

## 5. Validation

### 5.1 Pydantic Schema

Every YAML config is validated against a Pydantic model on load. The Pydantic model is generated from the RADIANT parameter schema (all `ParameterDef` objects from the `_schema.py` files assembled by `api/session.py`).

Validation levels, in order:

| Level | Check | Error type |
|-------|-------|-----------|
| 1 — Type | Value is the correct dtype (float, int, str, bool) | `ParameterTypeError` |
| 2 — Bounds | Value is within `[min, max]` if bounds defined | `ParameterBoundsError` |
| 3 — Enum | Value is one of the allowed enum values | `ParameterEnumError` |
| 4 — Unknown | No parameter exists at this dot-path | `UnknownParameterError` |
| 5 — Required | Required parameters (no default, not derivable) are present | `MissingParameterError` |
| 6 — Consistency | Consistency group constraints are satisfied | `ConsistencyError` |
| 7 — File | Referenced files (MODTRAN tape7, spectral data) exist and are readable | `FileReferenceError` |

All errors are reported together (not fail-fast), so the user sees all problems in one pass.

### 5.2 Physics-Informed Validation (Consistency Groups)

Beyond per-parameter bounds, consistency groups enforce multi-parameter physics constraints. From RADIANT_Parameter_System.md:

**optics_fno group:** `f_number = focal_length / aperture_diameter`. Given any 2, the 3rd is derived. All 3 specified → validated. Fewer than 2 non-defaulted → error.

**readout_timing group:** `integration_time × frame_rate ≤ 1.0` (duty cycle ≤ 1). If `frame_rate = 100 Hz` and `integration_time = 0.015 s`, duty cycle = 1.5 → `ConsistencyError`.

**spectral_grid group:** `filter.center_wavelength ± filter.bandwidth/2` must be within `[spectral.lambda_min, spectral.lambda_max]`. If the filter bandpass is not covered by the spectral grid, all spectral integrals are wrong. This is a `ConsistencyWarning` (not error) if the overlap is >95%, error if <50%.

**Additional physics-informed warnings:**
- `detector.dark_current` is anomalously low for the stated `detector.material` at `detector.operating_temp` (below Rule 07 floor by >10×) → warning: possible typo.
- `sensor.optics.wfe_rms > 0.25 waves` → warning: Strehl < 0.5; WFE MTF will severely degrade performance.
- `target.temperature < background.temperature` for MWIR/LWIR regime → warning: negative contrast; target will be cooler than background.
- `sensor.readout.n_tdi > 1` and `platform.smear_velocity = 0` → warning: TDI gain requires image motion matched to TDI rate.

### 5.3 Rich Error Messages

Every error includes:
1. The dot-path of the offending parameter
2. The invalid value and why it's invalid
3. The constraint or bound that was violated
4. The source of the value (user_set, config file name, cli override)
5. A suggested fix where possible

```
ConfigValidationError: 3 errors found in 'scenarios/leo_mwir_clear.yaml'

[1] ParameterBoundsError at sensor.detector.operating_temp
    Value: 400 K (from config:sensors/baseline_mwir.yaml)
    Allowed: 1 K ≤ operating_temp ≤ 300 K
    Fix: HgCdTe detectors operate at cryogenic temperature. Did you mean 80 K?

[2] ConsistencyError in group 'optics_fno'
    sensor.optics.f_number=4.0 specified directly, but
    sensor.optics.focal_length=1.20 m and sensor.optics.aperture_diameter=0.30 m
    imply f_number = 1.20/0.30 = 4.0 (within tolerance). ✓
    → Actually consistent; no action required. (This message should not appear.)

[3] MissingParameterError: target.temperature is required (no default)
    Source: not provided in scenario config or any imported partial
    Fix: add 'target:\n  temperature: 300  # K' to your scenario config
```

---

## 6. Five Complete YAML Configurations

### Config 1: MWIR LEO Pushbroom (Baseline)

```yaml
# RADIANT config — schema v1
# Baseline MWIR LEO pushbroom sensor, mid-latitude summer atmosphere,
# 300 K extended target at 600 km altitude. The reference scenario for
# aperture/integration-time trade studies.

_vars:
  ALT_M: 600000
  RANGE_M: 650000

sensor:
  optics:
    aperture_diameter: 0.30     # m
    focal_length: 1.20          # m — f/# = 4.0 (derived)
    obscuration_ratio: 0.33
    wfe_rms: 0.07               # waves RMS at 4.2 µm
    n_surfaces: 6
    temperature: 280            # K — warm optics; cold stop η = 0.90

  detector:
    material: HgCdTe
    pixel_pitch: 18.0e-6        # m (18 µm)
    cutoff_wavelength: 5.0      # µm
    peak_qe: 0.75
    dark_current: 500           # e-/s/pixel at 80 K
    read_noise: 25              # e- RMS (CDS)
    full_well: 1.5e6            # e-
    operating_temp: 80          # K
    ipc_coupling: 0.02
    n_pixels_x: 2048            # cross-track (pushbroom array)
    n_pixels_y: 1               # along-track (TDI handled in readout)

  readout:
    integration_time: 0.005     # s (5 ms)
    cds_enabled: true
    adc_bits: 14
    gain: 100                   # e-/DN
    n_tdi: 4                    # 4-stage TDI
    n_coadds: 1

  filter:
    center_wavelength: 4.2      # µm
    bandwidth: 0.5              # µm FWHM
    peak_transmission: 0.90
    shape: tophat

geometry:
  observer_altitude: ${ALT_M}   # m (600 km)
  observer_type: space
  target_type: ground
  look_angle: 0                 # deg (nadir)
  solar_zenith: 30              # deg
  solar_azimuth: 180            # deg (sun behind sensor)

atmosphere:
  model: modtran
  modtran_file: data/midlat_summer_mwir.tape7

target:
  temperature: 300              # K
  emissivity: 0.95
  area: 100.0                   # m² (extended scene)
  regime: auto

background:
  temperature: 290              # K
  emissivity: 0.96
  clutter_sigma: 0.0

platform:
  jitter_rms: 3.0               # µrad RMS
  drift_rate: 0.0               # µrad/s

spectral:
  lambda_min: 3.5               # µm
  lambda_max: 5.0               # µm
  n_points: 500
  grid_type: from_modtran
```

---

### Config 2: LWIR Geostationary Stare

```yaml
# RADIANT config — schema v1
# LWIR geostationary staring imager, 35786 km altitude, tropical atmosphere,
# 300 K extended background with 5 K hot target (wildfire detection scenario).

sensor:
  optics:
    aperture_diameter: 0.50     # m — large aperture for geo range
    focal_length: 2.50          # m — f/# = 5.0 (derived)
    obscuration_ratio: 0.35
    wfe_rms: 0.05               # waves RMS at 10.5 µm
    n_surfaces: 5
    temperature: 290            # K — ambient-temperature optics

  detector:
    material: HgCdTe
    pixel_pitch: 30.0e-6        # m (30 µm)
    cutoff_wavelength: 12.5     # µm — LWIR cutoff
    peak_qe: 0.65
    dark_current: 8.0e6         # e-/s/pixel at 77 K LWIR HgCdTe
    read_noise: 300             # e- RMS — staring ROIC
    full_well: 20.0e6           # e- — large well for high background
    operating_temp: 77          # K
    ipc_coupling: 0.015
    n_pixels_x: 1024
    n_pixels_y: 1024

  readout:
    integration_time: 0.010     # s (10 ms)
    cds_enabled: true
    adc_bits: 16
    gain: 500                   # e-/DN
    n_tdi: 1                    # staring (no TDI)
    n_coadds: 8                 # 8 coadds → effective 80 ms

  filter:
    center_wavelength: 10.5     # µm
    bandwidth: 4.0              # µm FWHM (8–13 µm)
    peak_transmission: 0.85
    shape: tophat

geometry:
  observer_altitude: 35786000   # m (geostationary orbit)
  observer_type: space
  target_type: ground
  look_angle: 0                 # deg (sub-satellite point)
  solar_zenith: 45              # deg

atmosphere:
  model: modtran
  standard_atmosphere: tropical
  modtran_file: data/tropical_lwir.tape7

target:
  temperature: 305              # K (5 K above background)
  temperature_hot: 1000         # K — fire component
  temperature_cool: 300         # K — cooler surrounding ground
  hot_fraction: 0.001           # 0.1% of pixel area on fire
  emissivity: 0.97
  area: 900.0                   # m² (30 m × 30 m = 1 GSD pixel at geo)
  regime: extended

background:
  temperature: 300              # K
  emissivity: 0.97
  clutter_sigma: 0.02           # 2% spatial clutter

platform:
  jitter_rms: 1.0               # µrad (ACS-controlled GEO platform)
  drift_rate: 0.05              # µrad/s

spectral:
  lambda_min: 7.5               # µm
  lambda_max: 14.0              # µm
  n_points: 500
  grid_type: from_modtran
```

---

### Config 3: Visible Aerial Pushbroom

```yaml
# RADIANT config — schema v1
# VIS/NIR pushbroom from manned aircraft at 3000 m AGL.
# Reflected solar illumination, 0.5 m GSD, mapping mission.

sensor:
  optics:
    aperture_diameter: 0.10     # m
    focal_length: 0.50          # m — f/# = 5.0 (derived)
    obscuration_ratio: 0.0      # unobscured refractive design
    wfe_rms: 0.04               # waves RMS at 0.65 µm
    n_surfaces: 8               # camera with multiple elements
    temperature: 293            # K — ambient temperature

  detector:
    material: Si                # Silicon CMOS, VIS range
    pixel_pitch: 5.0e-6         # m (5 µm)
    cutoff_wavelength: 1.0      # µm — Si cutoff
    peak_qe: 0.60               # at 0.65 µm
    dark_current: 10            # e-/s/pixel at 293 K (CMOS)
    read_noise: 3               # e- RMS (modern CMOS)
    full_well: 40000            # e- (40 ke-)
    operating_temp: 293         # K — uncooled
    ipc_coupling: 0.005
    n_pixels_x: 4096
    n_pixels_y: 1

  readout:
    integration_time: 0.001     # s (1 ms)
    cds_enabled: false          # CMOS rolling shutter
    adc_bits: 12
    gain: 1                     # e-/DN (unity gain)
    n_tdi: 1

  filter:
    center_wavelength: 0.65     # µm (panchromatic peak)
    bandwidth: 0.45             # µm (0.4–0.9 µm)
    peak_transmission: 0.95
    shape: tophat

geometry:
  observer_altitude: 3000       # m AGL
  target_altitude: 0            # m (ground)
  observer_type: airborne
  target_type: ground
  look_angle: 0                 # deg (nadir)
  solar_zenith: 25              # deg
  solar_azimuth: 135            # deg
  observer_latitude: 40         # deg N

atmosphere:
  model: simple
  visibility: 23000             # m (23 km — good visibility)
  standard_atmosphere: midlat_summer

target:
  temperature: 300              # K (for thermal emission; negligible in VIS)
  reflectance: 0.15             # Lambertian, moderate albedo (mixed vegetation)
  emissivity: 0.95
  area: 500.0                   # m² (extended)
  regime: extended

background:
  temperature: 295              # K
  reflectance: 0.12
  emissivity: 0.95
  clutter_sigma: 0.05           # 5% spatial variation in reflectance

platform:
  jitter_rms: 5.0               # µrad RMS (manned aircraft vibration)
  smear_velocity: 0.25          # m/s image plane velocity

spectral:
  lambda_min: 0.35              # µm
  lambda_max: 0.95              # µm
  n_points: 300
  grid_type: uniform_wavelength
```

---

### Config 4: Point Source Tracking

```yaml
# RADIANT config — schema v1
# MWIR sensor tracking an aircraft engine exhaust plume as a point source
# from a ground-based observatory at 20 km range. Detection range analysis.

sensor:
  optics:
    aperture_diameter: 0.40     # m
    focal_length: 3.20          # m — f/# = 8.0 (derived), long focal length for angular res
    obscuration_ratio: 0.30
    wfe_rms: 0.06               # waves RMS
    n_surfaces: 6
    temperature: 293            # K — ambient ground-based

  detector:
    material: InSb              # InSb — excellent MWIR QE
    pixel_pitch: 15.0e-6        # m (15 µm)
    cutoff_wavelength: 5.4      # µm — InSb cutoff
    peak_qe: 0.80
    dark_current: 200           # e-/s/pixel at 77 K
    read_noise: 20              # e- RMS
    full_well: 8.0e6            # e-
    operating_temp: 77          # K
    ipc_coupling: 0.01
    n_pixels_x: 640
    n_pixels_y: 512             # staring FPA

  readout:
    integration_time: 0.002     # s (2 ms) — short for high background
    cds_enabled: true
    adc_bits: 14
    gain: 80
    n_tdi: 1
    n_coadds: 1

  filter:
    center_wavelength: 4.3      # µm — CO2 emission band from exhaust
    bandwidth: 0.15             # µm narrow band
    peak_transmission: 0.85
    shape: tophat

geometry:
  observer_altitude: 500        # m (observatory elevation)
  target_altitude: 3000         # m (aircraft cruise)
  slant_range: 20000            # m — user-specified directly
  observer_type: ground
  target_type: airborne
  look_angle: 8.5               # deg elevation angle
  solar_zenith: 75              # deg — twilight conditions

atmosphere:
  model: modtran
  modtran_file: data/midlat_summer_mwir_slant.tape7
  visibility: 15000             # m (15 km)

target:
  temperature: 800              # K — exhaust plume temperature
  emissivity: 0.85              # exhaust plume emissivity
  area: 0.5                     # m² — effective plume cross-section
  regime: point                 # force point-source equations

background:
  temperature: 280              # K — sky background at 8.5 deg elevation
  emissivity: 0.10              # low sky emissivity in narrow MWIR band

platform:
  jitter_rms: 15.0              # µrad — ground-based mount with wind loading

spectral:
  lambda_min: 4.0               # µm
  lambda_max: 4.6               # µm
  n_points: 300
  grid_type: from_modtran
```

---

### Config 5: Sub-Pixel Target Detection

```yaml
# RADIANT config — schema v1
# LWIR staring sensor detecting a sub-pixel vehicle target (2 m²)
# against a warm ground background. NVTherm-style analysis.

sensor:
  optics:
    aperture_diameter: 0.15     # m — compact tactical sensor
    focal_length: 0.75          # m — f/# = 5.0 (derived)
    obscuration_ratio: 0.0
    wfe_rms: 0.10               # waves RMS — budget sensor
    n_surfaces: 4
    temperature: 290            # K

  detector:
    material: HgCdTe
    pixel_pitch: 15.0e-6        # m (15 µm)
    cutoff_wavelength: 10.5     # µm
    peak_qe: 0.70
    dark_current: 3.0e6         # e-/s/pixel at 77 K (LWIR)
    read_noise: 250             # e- RMS
    full_well: 10.0e6           # e-
    operating_temp: 77          # K
    ipc_coupling: 0.025         # LWIR detectors have higher IPC
    n_pixels_x: 640
    n_pixels_y: 480

  readout:
    integration_time: 0.010     # s (10 ms)
    cds_enabled: true
    adc_bits: 14
    gain: 400                   # e-/DN
    n_tdi: 1
    n_coadds: 1

  filter:
    center_wavelength: 9.0      # µm — LWIR atmospheric window
    bandwidth: 4.0              # µm (7–11 µm)
    peak_transmission: 0.88
    shape: tophat

geometry:
  observer_altitude: 500        # m — airborne tactical sensor
  target_altitude: 0            # m
  slant_range: 3000             # m — 3 km range
  observer_type: airborne
  target_type: ground
  look_angle: 9.5               # deg depression angle
  solar_zenith: 50              # deg

atmosphere:
  model: simple
  visibility: 8000              # m (8 km — hazy)
  standard_atmosphere: midlat_summer

target:
  temperature: 308              # K — vehicle hood (8 K above background)
  emissivity: 0.90
  area: 2.0                     # m² — sub-pixel (IFOV projects to ~50 m² at 3 km)
  regime: subpixel              # force sub-pixel equation for the 2 m² target

background:
  temperature: 300              # K
  emissivity: 0.95
  clutter_sigma: 0.04           # 4% terrain clutter

platform:
  jitter_rms: 8.0               # µrad (airborne pod vibration)

spectral:
  lambda_min: 7.0               # µm
  lambda_max: 12.0              # µm
  n_points: 400
  grid_type: uniform_wavelength
```

---

## 7. Loading Precedence Summary

Parameters are resolved in the following priority order (lowest to highest):

| Priority | Source | Provenance tag |
|----------|--------|----------------|
| 1 (lowest) | Schema defaults (`ParameterDef.default`) | `DEFAULT` |
| 2 | Grandparent config (if `_extends` chain > 1 level) | `CONFIG_FILE` |
| 3 | Parent config (direct `_extends` target) | `CONFIG_FILE` |
| 4 | Imported partials (`_imports`, in list order) | `CONFIG_FILE` |
| 5 | Current config file body | `CONFIG_FILE` |
| 6 | Programmatic `sensor.set()` calls | `USER_SET` |
| 7 (highest) | CLI `--set` overrides | `USER_SET` |

Every resolved parameter carries its provenance tag and source file. A parameter from the current config file at priority 5 that is also present in the parent at priority 3 retains the winning source: `config:scenarios/leo_mwir_clear.yaml`.

Derived parameters (computed from other parameters via consistency groups) carry provenance `DERIVED` with a `derived_from` record listing the inputs and values used. Derived parameters cannot be set at any priority level; setting them explicitly triggers a consistency check (and may produce a `ConsistencyError` if the explicit value conflicts with the derived value).
