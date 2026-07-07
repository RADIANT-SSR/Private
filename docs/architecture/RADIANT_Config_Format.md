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

A scenario config that imports a sensor config and overrides one parameter is the intended common pattern — but multi-file composition depends on `_extends`/`_imports`, which are not yet implemented (see the §1.3 status banner). Today, use a single complete config (see `examples/`) plus `Sensor.set()` or CLI `--set` overrides.

### 1.2 YAML Structure and Naming

The dot-path parameter namespace maps directly to YAML nesting (`radiant/io/config.py::_flatten`). A parameter `optics.aperture_diameter_m` maps to:

```yaml
optics:
  aperture_diameter_m: 0.30   # m
```

There is **no `sensor:` wrapper** — top-level keys are the stage namespace roots exactly as they appear in the parameter schema (`*/_schema.py`):

| Top-level key | Parameter namespace | Contents |
|--------------|--------------------|-|
| `source` | `source.*` | Target and background: `source.target.*`, `source.background.*` (temperature, emissivity, area, range, regime override) |
| `atmosphere` | `atmosphere.*` | Model selection (`unity`, `simple`, `tabulated`, `modtran`, `interpolated`, `exo`), standard atmosphere, `atmosphere.modtran.*` sub-keys |
| `geometry` | `geometry.*` | Sensor/target altitudes, path/solar zenith, solar azimuth, ground speed |
| `optics` | `optics.*` | Aperture, focal length, transmission, WFE, defocus, cold stop, `optics.stray.*` sub-keys |
| `platform` | `platform.*` | Jitter, ground velocity, smear |
| `spectral_integration` | `spectral_integration.*` | Filter bandpass (`filter_min_um`, `filter_max_um`), integration time |
| `detector` | `detector.*` | Pixel pitch, QE, dark current, noise parameters, IPC, diffusion |
| `readout` | `readout.*` | Read noise, gain, ADC, full well, CDS, TDI, binning, coadds |

Unknown parameter names raise `ConfigError` at load time (`Schema violations: Unknown parameter: '...'`).

All parameter names follow the naming rules from RADIANT_Parameter_System.md and ADR-D (`docs/adr/ADR-D-parameter-naming.md`, 2026-07-06): lowercase, underscore-separated, with the **input unit as a name suffix** for dimensioned quantities — `aperture_diameter_m`, `pixel_pitch_x_um`, `jitter_rms_urad`. Dimensionless parameters carry no suffix.

**Inline comments are mandatory** for non-obvious values and any value not in SI base units:

```yaml
detector:
  pixel_pitch_x_um: 18.0        # µm
  pixel_pitch_y_um: 18.0        # µm
  qe_value: 0.70
  dark_rate_e_per_s: 100.0      # e-/s — at reference temperature

readout:
  read_noise_e_rms: 5.0         # e- RMS
  full_well_capacity_e: 2000000.0  # e- (2 Me-, typical MWIR HgCdTe)
```

Scientific notation (`1.5e6`) is acceptable for large values. Units go in the name suffix and the comment.

### 1.3 Variable Substitution

> **Implementation status (2026-07-06):** `_vars`, `_extends`, and `_imports` (§1.3–1.5) are **design targets, not implemented**. The current loader (`radiant/io/config.py`) reserves these top-level keys and silently ignores them — no substitution, inheritance, or import merging is performed, and there is no CLI `--var` flag. Do not rely on these features until this banner is removed.

Variables are defined at the top of a config in a `_vars:` block. They are substituted anywhere in the document using `${VAR_NAME}` syntax. Substitution is string-level: the YAML parser resolves variables before YAML is parsed. Arithmetic is not supported; use Python if you need arithmetic.

```yaml
_vars:
  ALT_M: 600000          # 600 km orbit altitude
  RANGE_M: 650000        # typical slant range at this altitude
  T_TINT_S: 0.005        # 5 ms integration time

geometry:
  sensor_altitude_m: ${ALT_M}

source:
  target:
    range_m: ${RANGE_M}

spectral_integration:
  integration_time_s: ${T_TINT_S}
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
  sensor_altitude_m: 600000   # m
  solar_zenith_rad: 0.52      # rad (~30°)

atmosphere:
  model: modtran
  standard_atmosphere: midlat_summer

source:
  target:
    temperature: 300.0        # K
    emissivity: 0.95
    projected_area_m2: 10.0   # m²
```

```yaml
# sensors/baseline_mwir.yaml — parent
optics:
  aperture_diameter_m: 0.30   # m
  focal_length_m: 1.20        # m
  obscuration_ratio: 0.33
  wfe_rms_waves: 0.07         # waves
  optics_temperature_K: 280.0 # K
  transmission_scalar: 0.70

detector:
  pixel_pitch_x_um: 18.0      # µm
  pixel_pitch_y_um: 18.0      # µm
  qe_value: 0.75
  dark_rate_e_per_s: 500.0    # e-/s

spectral_integration:
  filter_min_um: 3.95         # µm
  filter_max_um: 4.45         # µm
  integration_time_s: 0.005   # s

readout:
  read_noise_e_rms: 25.0      # e- RMS
  cds_enabled: true
  adc_bits: 14
  gain_e_per_dn: 100.0        # e-/DN
  n_tdi: 1
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
  sensor_altitude_m: 600000   # m
  path_zenith_rad: 0.0        # rad (nadir)
  solar_zenith_rad: 0.52      # rad (~30°)
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

The schema version is a comment convention only — it is not a validated field in v1, and the current loader does not warn when it is absent. `save_config` writes the `# RADIANT config — schema v1` header on every file it produces.

---

## 2. XLSX Convenience View

> **Implementation status (2026-07-06):** the XLSX view is a **design target, not implemented**. There is no `radiant export` command and no XLSX code in `radiant/io/` (the existing `radiant convert` CLI is a scalar unit converter, unrelated). Sheet names below reflect the superseded `sensor.*` namespace and will be revised to the ADR-D namespaces when this feature is built.

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
| A — Parameter | Dot-path name (e.g., `optics.aperture_diameter_m`) |
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

Configs are constructed programmatically through the `Sensor` class (`radiant.Sensor`; see `radiant/api/sensor.py`). There are no `SensorConfig`/`ScenarioConfig` builder classes — they were dropped per `docs/adr/ADR-C`.

### 3.1 Creating a Sensor Programmatically

```python
from radiant import Sensor

sensor = (
    Sensor()
    .set("optics.aperture_diameter_m", 0.30)       # m
    .set("optics.focal_length_m", 1.20)            # m — f_number derived: 4.0
    .set("optics.obscuration_ratio", 0.33)
    .set("optics.wfe_rms_waves", 0.07)             # waves RMS
    .set("optics.optics_temperature_K", 280.0)     # K
    .set("detector.pixel_pitch_x_um", 18.0)        # µm
    .set("detector.pixel_pitch_y_um", 18.0)        # µm
    .set("detector.qe_value", 0.75)
    .set("detector.dark_rate_e_per_s", 500.0)      # e-/s
    .set("readout.read_noise_e_rms", 25.0)         # e- RMS
    .set("spectral_integration.filter_min_um", 3.95)
    .set("spectral_integration.filter_max_um", 4.45)
    .set("spectral_integration.integration_time_s", 0.005)
)

# Or set several at once:
sensor.set_many({
    "readout.cds_enabled": True,
    "readout.adc_bits": 14,
    "readout.gain_e_per_dn": 100.0,
})
```

### 3.2 Loading from YAML or Dict

```python
from radiant import Sensor

# From a complete YAML config:
sensor = Sensor.from_yaml("examples/mwir_leo_minimal.yaml")

# From a nested Python dict (same structure as the YAML):
sensor = Sensor.from_dict({
    "optics": {"aperture_diameter_m": 0.30, "focal_length_m": 1.20},
    "detector": {"pixel_pitch_x_um": 18.0, "pixel_pitch_y_um": 18.0},
})

# Override after loading, then run:
result = sensor.set("optics.aperture_diameter_m", 0.45).evaluate()
```

Splitting a sensor definition and a scenario across multiple YAML files is not supported by the current loader (see the §1.3 implementation-status banner); pass a single complete config, or load one file and apply per-scenario overrides via `set`/`set_many`.

---

## 4. CLI Overrides

The `radiant run` command accepts dot-path parameter overrides that override any value in the config file. CLI overrides have the highest priority in the loading precedence.

### 4.1 Syntax

```bash
# Single override
radiant run config.yaml --set optics.aperture_diameter_m=0.45

# Multiple overrides
radiant run config.yaml \
  --set optics.aperture_diameter_m=0.45 \
  --set spectral_integration.integration_time_s=0.008 \
  --set source.target.temperature=320

# Override a string parameter
radiant run config.yaml --set atmosphere.model=simple
```

(There is no `--var` flag; `_vars` substitution is unimplemented — see §1.3.)

### 4.2 Output

```bash
# Write results to JSON
radiant run config.yaml --set optics.aperture_diameter_m=0.45 --output result.json

# Write provenance record
radiant run config.yaml --provenance provenance.json

# Dry run: validate only, no evaluation
radiant validate config.yaml --set optics.aperture_diameter_m=0.45

# Explain a derived parameter
radiant explain config.yaml optics.f_number
# → f_number = 4.0 (derived: focal_length_m / aperture_diameter_m)
#   optics.focal_length_m = 1.20 m (user_set, config.yaml)
#   optics.aperture_diameter_m = 0.45 m (user_set, cli_override)
```

### 4.3 Batch Sweep from CLI

A lightweight parameter sweep from the CLI using shell expansion. For proper sweeps with result collection, use the Python API.

```bash
for D in 0.15 0.20 0.25 0.30 0.35 0.40; do
  radiant run config.yaml \
    --set optics.aperture_diameter_m=$D \
    --output results/snr_D${D}.json
done
```

---

## 5. Validation

### 5.1 Schema Validation

There is no Pydantic dependency. Every YAML config is validated against the RADIANT parameter schema itself: `radiant/io/config.py::load_config` flattens the nested YAML to dot-paths and calls `ParameterSet.set()` for each, and `ParameterSet.resolve()` (`radiant/core/parameters.py`) performs the remaining checks. The schema is the set of all `ParameterDef` objects from the `_schema.py` files, assembled by `radiant/api/_param_registry.py::build_parameter_set`.

Validation checks, in order:

| Check | Where | Error surface |
|-------|-------|--------------|
| Unknown name | `load_config` | `ConfigError` ("Schema violations: Unknown parameter: '…'"; all unknown names collected, not fail-fast) |
| Type | `ParameterSet.set` | `ValueError` with expected dtype |
| Bounds | `ParameterSet.set` | `ParameterBoundsError` (what/why/action/context per Rule 15) |
| Enum | `ParameterSet.set` | `ValueError` listing allowed values |
| Required | `ParameterSet.resolve` | `ValueError` ("Required parameter '…' is not set") |
| Consistency | `ParameterSet.resolve` | `ValueError` showing constraint, specified vs. computed value, and relative discrepancy vs. group tolerance |

Unknown-name errors are collected and reported together in one pass; type/bounds/enum errors raise on the first offending `set()`.

### 5.2 Physics-Informed Validation (Consistency Groups)

Beyond per-parameter bounds, consistency groups enforce multi-parameter physics constraints. v1 defines one group (`radiant/api/_param_registry.py`; see RADIANT_Parameter_System.md):

**fnumber group:** `f_number = focal_length_m / aperture_diameter_m`. Given any 2 of {`optics.f_number`, `optics.focal_length_m`, `optics.aperture_diameter_m`}, the 3rd is derived. All 3 specified → validated against the group tolerance (1e-3 relative); an inconsistent triple raises a `ValueError` naming the constraint, both values, and the discrepancy.

### 5.3 Rich Error Messages

Every error includes:
1. The dot-path of the offending parameter
2. The invalid value and why it's invalid
3. The constraint or bound that was violated
4. The source of the value (user_set, config file name, cli override)
5. A suggested fix where possible

```
ParameterBoundsError: detector.detector_temperature_K = 600 K is out of bounds
  Why: schema bounds for this parameter are (1.0, 500.0) K
  Action: set detector_temperature_K within bounds (77 K is typical for cooled IR)
  Context: {"param": "detector.detector_temperature_K", "value": 600, ...}

ValueError: Consistency group 'fnumber' is over-constrained:
  Constraint: f_number = focal_length_m / aperture_diameter_m
  User-specified 'optics.aperture_diameter_m' = 0.25
  Computed 'optics.aperture_diameter_m' from other parameters = 0.30
  Relative discrepancy: 2.000e-01 (tolerance: 1.000e-03)
  Fix: either remove 'optics.aperture_diameter_m' from inputs and let it be
  derived, or correct the inconsistent value.

ValueError: Required parameter 'optics.aperture_diameter_m' is not set.
  Description: Clear entrance-pupil diameter of the primary [m].
  Expected type: float in m
  Set it via: params.set('optics.aperture_diameter_m', value)
```

---

## 6. Complete YAML Configurations

Complete, loadable configurations live in the repository and are the authoritative examples — every file below passes `radiant validate`:

| File | Scenario |
|------|----------|
| `examples/mwir_leo_minimal.yaml` | Minimal MWIR LEO extended scene (reference case for `tests/integration/test_chain_extended.py`) |
| `examples/ground_truth_mwir.yaml` | Hand-computable single-wavelength MWIR ground truth (exo atmosphere) |
| `examples/templates/*.yaml` | Twelve band/platform templates (MWIR/LWIR/SWIR/VNIR × LEO/GEO/aerial/ground), served by `radiant template` |

Two of them, inline:

### Config 1: MWIR LEO Minimal (`examples/mwir_leo_minimal.yaml`)

```yaml
# RADIANT config — schema v1
# Minimal MWIR LEO extended-scene scenario.
# 300 K target, nadir view at 8 km altitude, midlat summer atmosphere.
# Matches the reference case in tests/integration/test_chain_extended.py.

source:
  target:
    temperature: 300.0        # K
    emissivity: 0.95

atmosphere:
  standard_atmosphere: midlat_summer

geometry:
  sensor_altitude_m: 8000.0   # m

optics:
  aperture_diameter_m: 0.30   # m
  focal_length_m: 1.20        # m  (f/4.0)
  transmission_scalar: 0.70

detector:
  pixel_pitch_x_um: 18.0      # um
  pixel_pitch_y_um: 18.0      # um
  qe_value: 0.70
  dark_rate_e_per_s: 100.0    # e-/s

spectral_integration:
  filter_min_um: 3.5           # um
  filter_max_um: 5.0           # um
  integration_time_s: 0.005    # s  (5 ms)

readout:
  read_noise_e_rms: 5.0       # e- RMS
  gain_e_per_dn: 32.0         # e-/DN (sized for FWC/2^16)
  adc_bits: 16
  full_well_capacity_e: 2000000.0  # e- (2 Me-, typical MWIR HgCdTe)
```

### Config 2: VNIR LEO High-Resolution (`examples/templates/vnir_leo_highres.yaml`)

```yaml
# RADIANT template: vnir_leo_highres
# High-resolution VNIR from LEO — 0.50m aperture, 0.45–0.70 µm
# Panchromatic high-GSD imaging satellite.

source:
  target:
    temperature: 300.0        # K (ground target)
    emissivity: 0.10

atmosphere:
  standard_atmosphere: midlat_summer

geometry:
  sensor_altitude_m: 600000.0  # m (600 km LEO)

optics:
  aperture_diameter_m: 0.50   # m
  focal_length_m: 5.00        # m  (f/10)
  transmission_scalar: 0.75

detector:
  pixel_pitch_x_um: 8.0       # µm
  pixel_pitch_y_um: 8.0       # µm
  qe_value: 0.80
  dark_rate_e_per_s: 15.0     # e-/s

spectral_integration:
  filter_min_um: 0.45          # µm
  filter_max_um: 0.70          # µm
  integration_time_s: 0.0005   # s  (0.5 ms)

readout:
  read_noise_e_rms: 4.0       # e- RMS
  gain_e_per_dn: 1.0          # e-/DN
  adc_bits: 12
```


## 7. Loading Precedence Summary

Parameters are resolved in the following priority order (lowest to highest):

| Priority | Source | Provenance tag |
|----------|--------|----------------|
| 1 (lowest) | Schema defaults (`ParameterDef.default`) | `DEFAULT` |
| 2 | Config file body | `CONFIG_FILE` |
| 3 | Programmatic `Sensor.set()` / `set_many()` calls | `USER_SET` |
| 4 (highest) | CLI `--set` overrides | `USER_SET` |

(When the `_extends`/`_imports` layering of §1.4–1.5 is implemented, parent and imported configs will slot in below the current file body at the `CONFIG_FILE` level.)

Every resolved parameter carries its provenance tag and source label (the config file path, `Sensor.set`, or the CLI). Derived parameters (computed from other parameters via consistency groups) carry provenance `DERIVED` with a `derived_from` record listing the inputs and values used. Setting all members of a group explicitly triggers a consistency check, which raises a `ValueError` if the explicit value conflicts with the derived value beyond the group tolerance.
