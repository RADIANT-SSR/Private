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
| `atmosphere` | `atmosphere.*` | Model selection (`simple`, `exo`, `tabulated`, `modtran`, `interpolated`), standard atmosphere, `atmosphere.modtran.*` sub-keys |
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

> **Not the multi-configuration feature (ADR-0010, 2026-07-25):** `_extends`/`_imports`/`_vars` are *file-composition* directives — one config file built from several. A **configuration set** (§1.9) is the unrelated in-file feature: one config file holding up to 8 named configurations of the same problem, via the `configurations:` structured section. Configuration sets do **not** use, need, or imply `_extends`; the directives below remain unimplemented and still raise.

> **Implementation status (2026-07-06):** `_vars`, `_extends`, and `_imports` (§1.3–1.5) are **design targets, not implemented**. The current loader (`radiant/io/config.py`) **raises `ConfigError`** when any of these top-level keys is present (CU-050; previously they were silently stripped, which loaded the config with the directive ignored — a Rule 17 antipattern). Inline the parent/imported values into a single complete config. There is no CLI `--var` flag. Do not rely on these features until this banner is removed.

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

Not to be confused with configuration sets (§1.9): `_extends` composes **one** parameter set from several files; a configuration set holds **several** configurations in one file. Band or as-built variants are expressed with §1.9, not with `_extends`.

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

As in §1.4, this is file composition, not the in-file configuration sets of §1.9.

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

### 1.7 Session Metadata Block (`_radiant`) — implemented (Gap 67, 2026-07-11)

`Sensor.save(path)` writes an optional top-level `_radiant` mapping carrying session-level state that is not a chain parameter:

```yaml
_radiant:
  format: 1
  wavelength_points: 500
  tolerances:                      # only present when tolerances are set
    detector.qe_value:
      distribution: gaussian
      params: {std: 0.02}
optics:
  aperture_diameter_m: 0.3
# ... explicitly-set inputs only — defaults and derived values are NOT written,
# so reloading reproduces the original resolution and provenance exactly.
```

Loader behavior: `load_config` strips the block before parameter flattening, applies `tolerances` via `ParameterSet.set_tolerance`, and raises `ConfigError` on a malformed block (non-mapping, missing `distribution`/`params`, unknown parameter name). `wavelength_points` is session-level: `Sensor.load(path)` consumes it (via `read_radiant_meta`); a bare `load_config` ignores it. Configs without `_radiant` are unaffected, and a `Sensor.save` file remains loadable by `from_yaml` and the CLI. `save_config(..., scope="inputs")` writes only explicit inputs (the `Sensor.save` mode); the default `scope="resolved"` remains the fully-specified documentation export.

### 1.8 Structured Document Sections (`optical_elements`) — implemented (ADR-0009, 2026-07-16)

A config may carry **structured document sections**: top-level keys that hold a declarative
document rather than parameters. The one registered section is `optical_elements` — the
mixed-train element list (`io/element_config.py` schema; per-element `name`, `transfer_mode`,
`kind`, `temperature_K`, geometry, and R/T values that are scalars, spectral-CSV paths, **or inline spectral tables** — `{wavelength_um: [...], values: [...]}`, the form the GUI's type-or-paste spectrum dialog writes; it persists in the YAML with no external file).
Emissivity never appears in an entry — it is Kirchhoff-derived (Rule 5).

```yaml
optics:
  aperture_diameter_m: 0.3
optical_elements:
  - {name: M1, transfer_mode: REFLECTIVE, reflectance: 0.97, temperature_K: 293.0,
     diameter_m: 0.30, distance_to_fpa_m: 0.9}
  - {name: cold_filter, transfer_mode: REFRACTIVE, kind: FILTER, transmittance: 0.90,
     temperature_K: 240.0}
```

Loader behavior (Rule 17 — never a silent skip): `Sensor.from_yaml` / `Sensor.load` /
`Sensor.from_dict` parse and **attach** the section (equivalent to
`Sensor.set_optical_elements`); the document then persists back out through `Sensor.save`
(relative spectral-file paths are absolutized at attach so the saved config loads from
anywhere). A **bare** `load_config` call raises an actionable `ConfigError` on a
section-bearing config unless the caller opts in via `sections_out` — a loader that cannot
attach the section must not silently drop physics the config describes. `radiant run` and
`radiant validate` opt in and act on the section (CU-153): run parses the element document
onto the run grid, validate normalizes it and reports its errors.

### 1.9 Configuration Sets (`configurations`) — implemented (ADR-0010, 2026-07-25)

The second registered structured section. It turns one config file into one **study**: the shared parameter document exactly as §1.7–1.8 describe it, plus the per-configuration state of a `ConfigurationSet` (`RADIANT_Scripting_API.md` §2.5c) — up to **8** named *configurations* of the same modeling problem (band variants, geometry variants, nominal vs. as-built).

Terminology (ADR-0010 D-10): the on-disk artifact is a **config file**; a **configuration** is a member of a configuration set.

```yaml
# ... shared parameters exactly as today ...
_radiant:
  format: 1
  wavelength_points: 500          # the SHARED grid point count
optics:
  aperture_diameter_m: 0.30       # shared: one value for every configuration

configurations:
  names: [MWIR, LWIR]             # 1–8, unique, non-empty; defines the column order
  active: MWIR                    # GUI resume state   (optional; default names[0])
  baseline: MWIR                  # delta reference    (optional; default names[0])
  wavelength_points:              # optional; omitted names use _radiant.wavelength_points
    LWIR: 300
  parameters:                     # dot-path → list aligned with `names`
    spectral_integration.filter_min_um: [3.95, 8.0]
    spectral_integration.filter_max_um: [4.45, 12.0]
    detector.qe_value: [0.75, 0.62]
```

Binding rules, all enforced at load with a `ConfigError` naming the config file, the configuration, and the parameter (`radiant/io/config_set_section.py`):

| Rule | Violation |
|---|---|
| `names`: 1–8 unique, non-empty strings | missing/empty list, duplicate name, 9th name, non-string |
| `active` / `baseline` optional, each names a member | a name not in `names` |
| `wavelength_points`: mapping of member name → `int >= 2` | non-member key, `< 2`, non-integer |
| `parameters`: mapping of dot-path → list, **every list length = `len(names)`** | a short or long list — dense by construction (ADR-0010 D-A), never padded |
| Dot-paths validate against the schema (alias-aware) | unknown name → error with the usual did-you-mean; the same parameter twice (canonical + deprecated alias) |
| A dot-path is in the shared body **or** in `parameters`, never both | the single-store invariant (ADR-0010 D-B) — the shared value would be silently shadowed |
| Values are **input-unit scalars** | type/bounds/enum are validated on the ordinary parameter path, per configuration |
| `is_file_path` values relativize on save and resolve on load against the config file's directory | — (CU-177 parity with shared values) |
| `optical_elements`: optional mapping of member name → replace-by-name element overrides | non-member key, an entry naming no shared element, an entry the element parser rejects (see below) |

#### Per-configuration optical elements — `configurations.optical_elements` (Gap 103 v1.1, 2026-09-02)

The `optical_elements` document (§1.8) stays **shared** and is stated once. A configuration
may replace individual entries of it, keyed by configuration name:

```yaml
optical_elements:                 # the shared train — stated once
  - {name: M1, transfer_mode: REFLECTIVE, reflectance: 0.97, temperature_K: 293.0}
  - {name: band_filter, transfer_mode: REFRACTIVE, kind: FILTER,
     transmittance: data/filter_b01.csv, temperature_K: 240.0}

configurations:
  names: [B1_CA, B2_Blue]
  optical_elements:               # optional; member name → replace-by-name overrides
    B2_Blue:
      - {name: band_filter, transfer_mode: REFRACTIVE, kind: FILTER,
         transmittance: data/filter_b02.csv, temperature_K: 240.0}
    # B1_CA is absent — it inherits the shared train unchanged
```

Semantics are **replace-by-name** (owner-ratified 2026-09-02): each override entry is a
**complete** element entry that replaces the shared entry with the same `name`; every shared
entry not named is inherited, **in shared order**. There is no field-level merge, so there is
no patch-resolution semantics; and an override never *adds* or *removes* an element, so a
configuration's train is always the shared document with named entries swapped. The effective
train of a configuration is what `ConfigurationSet.sensor_for(name)` attaches and what
`cs.effective_optical_elements(name)` reports.

Binding rules, all enforced at load with a `ConfigError` naming the config file and the
configuration:

| Rule | Violation |
|---|---|
| `optical_elements`: mapping of **member name** → non-empty list of complete element entries | non-member key, non-mapping, empty list, non-mapping entry |
| Each entry carries a `name` that **matches a shared element** | a missing `name`; a name not in the shared `optical_elements` document (replace-by-name never adds); the same name twice in one configuration (overridden **or** inherited, never both) |
| Each entry re-validates through the element parser (`io/element_config.py`) — Kirchhoff included (Rule 5) | any entry the shared document's own parser would reject, failing at **load** rather than at evaluation |
| Overrides require a shared `optical_elements` document | an override in a config file whose body has no element document |
| Spectral-file references inside an entry relativize on save and resolve on load against the config file's directory | — (CU-177 parity with configured values) |

Loader behavior (Rule 17 — never a silent skip): `ConfigurationSet.load(path)` reads the whole document (shared body, `_radiant` meta, `optical_elements`, and this section); `ConfigurationSet.save(path)` writes it. A section-bearing config file loaded through `Sensor.load` / `Sensor.from_yaml` / `Sensor.from_dict` or a bare `load_config` raises an actionable `ConfigError` — "this config file is a configuration set — load it with `ConfigurationSet.load(path)`" — rather than running one config file's shared body as if it were the whole study. A caller that knows how to handle the section opts in via `sections_out=` (the ADR-0009 mechanism), which is what `ConfigurationSet.load` does — and which `radiant run` / `radiant validate` do on the caller's behalf (§4.4). The `radiant explain` / `sweep` / `compare` / `tolerance` subcommands load through `Sensor.from_yaml` and therefore still raise that error on a study config file.

Scope, and what stays shared: tolerance distributions and `_radiant.wavelength_points` are the **shared** defaults (per-configuration tolerances are out of the v1 model); the `optical_elements` document is shared across all configurations, with per-configuration **replace-by-name overrides** of individual entries (the sub-key above — Gap 103 v1.1, the additive extension ADR-0010 D-7 anticipated; element *addition and removal* per configuration remain out of scope); stage-output injections (Gap 68) have no YAML form and are unaffected.

**Backward compatibility is structural, not a migration:** a config file with no `configurations:` key is byte-for-byte today's format and loads everywhere unchanged — registering the key changed no existing output. `ConfigurationSet.save` always writes the section, including for the degenerate single-configuration set with an empty table (the file then differs from `Sensor.save` output by the section alone), so the file is self-identifying as a study and the configuration's name survives the round trip. `ConfigurationSet.load` accepts a config file with **no** section and returns that degenerate one-configuration set.

There is no `scope="resolved"` export for a configuration set: writing every resolved value of the base would place configured dot-paths in the shared body as well, violating the invariant the file exists to persist.

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

**Provenance record shape (CU-218).** `--provenance` writes **one** schema
whichever config it was given: the run record from
`ChainResult.to_provenance_record()` — `run_id`, `radiant_version`, `git_commit`,
`parameter_set`, and the rest — plus a `configuration` key naming the
configuration a study run used, or `null` for a plain single-configuration run.
Before CU-218 a plain config wrote a different, three-key record
(`ParameterSet.to_provenance_record`: `radiant_version`, `resolved_at`,
`parameters`) while a `--configuration` run wrote the run record, so a consumer
had to detect which shape it had received. Scripts that read the old plain-path
`parameters` key should read `parameter_set` instead.

### 4.3 Batch Sweep from CLI

A lightweight parameter sweep from the CLI using shell expansion. For proper sweeps with result collection, use the Python API.

```bash
for D in 0.15 0.20 0.25 0.30 0.35 0.40; do
  radiant run config.yaml \
    --set optics.aperture_diameter_m=$D \
    --output results/snr_D${D}.json
done
```

### 4.4 Study Config Files — `--configuration` (ADR-0010, 2026-07-25)

A config file carrying a `configurations:` section (§1.9) is a **study**, and the CLI
treats it as one. Terminology per ADR-0010 D-10: the file is a *config file*, a
*configuration* is a member of the set.

```bash
# Run one named configuration. Required for a study file.
radiant run study.yaml --configuration LWIR

# Validate EVERY configuration; one line each, non-zero exit if any failed.
radiant validate study.yaml
```

`radiant run --configuration NAME` is thin by construction: `ConfigurationSet.load(path)`
→ `ConfigurationSet.sensor_for(NAME)` → the ordinary `Sensor.evaluate()` path. Contract:

| Invocation | Behavior |
|---|---|
| `run study.yaml --configuration NAME` | Evaluates that configuration. Every output form names it: a `Configuration: NAME` header line (text), a `configuration` key (`--format json`, `--output`, `--provenance`), a leading `configuration` column (`--format csv`). Plain config files keep their existing output shapes exactly. |
| `run study.yaml` (no flag) | **Error**, listing every configuration name and the flag. The study's `active` designation is GUI display state, not a scripting default — honoring it would make a batch result depend on where the selector was last left. |
| `run plain.yaml --configuration NAME` | **Error** — a plain config file has no named configurations. |
| `run study.yaml --configuration NAME --set p=v` | The override applies to the **materialized** configuration (last word, as on a plain config file), including a configured parameter's value for that configuration. |
| `run … --wavelength-min/--wavelength-max` with `--configuration` | **Error** — each configuration spans its own resolved `filter_min_um … filter_max_um` band (ADR-0010 D-F). Override the band itself with `--set`. |
| `run … --wavelength-points N` with `--configuration` | Honored only when given explicitly; otherwise each configuration's own point count (§1.9) stays in force. |
| `validate study.yaml` | `ConfigurationSet.validate_all()` — resolve-only, every configuration reported independently as `ok` (with its band in µm and its grid-point count) or `ERROR` with the actionable what-line. Exit status 1 if any configuration failed. |
| `validate study.yaml --set p=v` | Applies to the **shared** base. A *configured* dot-path is refused: one value has no unambiguous target across N configurations — edit `configurations.parameters`, or use `ConfigurationSet.set_value(s)`. |

There is no `--all-configurations` batch flag; running the whole study is
`ConfigurationSet.evaluate_all()` in the scripting API, or a shell loop over the
configuration names (gap-tracked: `docs/tracking/gaps.md` Gap 105).

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
