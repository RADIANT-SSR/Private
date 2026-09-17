# Configuration Guide

*Persona: Sarah (systems engineer), Raj (mission planner), Lisa (analyst)*

How to define, customize, and manage RADIANT config files.

---

## YAML Structure

A RADIANT config file is a YAML document whose top-level keys are the signal-chain stage
names. There are ten parameter namespaces in all — `geometry`, `source`, `atmosphere`,
`optics`, `platform`, `spectral_integration`, `detector`, `readout`, `calibration`,
`performance` — and a config only names the ones it needs. Here is an annotated example
using the seven most commonly populated sections:

```yaml
# --- Source (target and background) ---
source:
  target:
    temperature: 300.0         # K — target kinetic temperature
    emissivity: 0.95           # dimensionless, 0–1
    # fill_fraction: 0.5       # for sub-pixel targets (0–1)
    # projected_area_m2: 4.0   # target cross-section (m^2)
    # range_m: 10000.0         # slant range to target (m)
  background:
    temperature: 290.0         # K — background temperature (default)
    emissivity: 0.95           # background emissivity (default)
  # regime_override: auto      # auto | extended | sub_pixel | point_source

# --- Atmosphere ---
atmosphere:
  standard_atmosphere: midlat_summer   # midlat_summer | midlat_winter | ...
  # model: simple                      # simple | exo | tabulated | modtran
  # visibility_km: 23.0               # meteorological visibility
  # precipitable_water_cm: 1.4        # precipitable water vapor

# --- Geometry ---
geometry:
  sensor_altitude_m: 8000.0   # m — sensor altitude above ground
  # target_altitude_m: 0.0    # m — target elevation
  # path_zenith_rad: 0.0      # rad — off-nadir angle (0 = nadir)

# --- Optics ---
optics:
  aperture_diameter_m: 0.30   # m
  focal_length_m: 1.20        # m → f/4.0 (derived)
  transmission_scalar: 0.70   # end-to-end optical transmission
  # obscuration_ratio: 0.0    # central obscuration ratio
  # wfe_rms_waves: 0.0        # wavefront error in waves

# --- Detector ---
detector:
  pixel_pitch_x_um: 18.0      # um — pixel pitch cross-track
  pixel_pitch_y_um: 18.0      # um — pixel pitch along-track
  qe_value: 0.70              # quantum efficiency (flat)
  dark_rate_e_per_s: 100.0    # e-/s — dark current
  # read_noise handled in readout section
  # fill_factor: 1.0          # pixel fill factor (default)

# --- Spectral Integration ---
spectral_integration:
  filter_min_um: 3.5           # um — bandpass start
  filter_max_um: 5.0           # um — bandpass end
  integration_time_s: 0.005    # s — detector integration time

# --- Readout ---
readout:
  read_noise_e_rms: 5.0       # e- RMS
  gain_e_per_dn: 1.0          # e-/DN — system gain
  adc_bits: 16                 # ADC bit depth
  # n_tdi: 1                  # TDI stages (default = 1 = off)
  # n_coadds: 1               # number of coadded frames
```

Besides the parameter namespaces, four top-level keys carry something other than
parameters. Each is covered in its own section below:

| Key | What it is |
|-----|-----------|
| `_radiant` | Session metadata: format marker, spectral grid density, tolerance distributions |
| `optical_elements` | A declarative optical-element train (ADR-0009) |
| `fpa` | The name of a bundled FPA preset to apply (Gap 119) |
| `configurations` | Turns the file into a multi-configuration *study* (ADR-0010) |

Three further top-level keys — `_extends`, `_imports`, `_vars` — are **reserved** for
config-inheritance features that are designed but not implemented. A config containing
one is rejected with an actionable error rather than loading with the directive silently
ignored, which would produce physics from a different parameter set than intended.

See the [Parameter Reference](parameter_reference.md) for the exhaustive list of all 218
parameters with types, defaults, bounds, and descriptions. That chapter is generated from
the schema registry, so it cannot drift from the code.

---

## Parameter Dot-Path Convention

Every parameter has a dot-separated path that maps directly to YAML nesting:

| Dot-path                           | YAML location                      |
|------------------------------------|------------------------------------|
| `optics.aperture_diameter_m`       | `optics: aperture_diameter_m:`     |
| `source.target.temperature`        | `source: target: temperature:`     |
| `spectral_integration.filter_min_um` | `spectral_integration: filter_min_um:` |

This path is used everywhere: CLI overrides, Python API, `explain`, `sweep`.

---

## Defaults and Required Parameters

Most parameters have sensible defaults. The minimum required set for a
working evaluation is:

- `source.target.temperature`
- `source.target.emissivity`
- `optics.aperture_diameter_m`
- `optics.focal_length_m`
- `detector.pixel_pitch_x_um` and `pixel_pitch_y_um`
- `detector.qe_value`
- `spectral_integration.filter_min_um` and `filter_max_um`
- `spectral_integration.integration_time_s`
- `readout.read_noise_e_rms`
- `readout.gain_e_per_dn`
- `readout.adc_bits`
- `geometry.sensor_altitude_m`

Everything else defaults to a physically reasonable value. Run
`radiant validate <config>` to check completeness.

---

## Overriding Parameters

### CLI: `--set`

```bash
radiant run config.yaml --set optics.aperture_diameter_m=0.50
radiant run config.yaml --set optics.aperture_diameter_m=0.50 \
                        --set detector.qe_value=0.80
```

### Python: `sensor.set()`

```python
from radiant.api import Sensor

sensor = Sensor.from_yaml("examples/mwir_leo_minimal.yaml")
sensor.set("optics.aperture_diameter_m", 0.50)
sensor.set("detector.qe_value", 0.80)
result = sensor.evaluate()
```

Or set multiple at once:

```python
from radiant.api import Sensor

sensor = Sensor.from_yaml("examples/mwir_leo_minimal.yaml")
sensor.set_many({
    "optics.aperture_diameter_m": 0.50,
    "detector.qe_value": 0.80,
})
result = sensor.evaluate()
```

---

## Consistency Groups

Some parameters are linked by physical relationships. The f-number
consistency group enforces:

$$f/\# = f / D$$

If you specify `aperture_diameter_m` and `focal_length_m`, then `f_number`
is derived automatically. If you specify all three and they conflict,
RADIANT raises an error.

Check how a derived value was computed:

```bash
radiant explain examples/mwir_leo_minimal.yaml optics.f_number
```

---

## Units

RADIANT uses canonical internal units (meters, radians, seconds, etc.) but
accepts common input units. The `radiant convert` utility helps:

```bash
radiant convert 18 um m          # 18 um = 1.8e-05 m
radiant convert 45 deg rad       # 45 deg = 0.785398 rad
radiant convert 5 ms s           # 5 ms = 0.005 s
```

Parameter values in YAML are in the input units documented in the
[Parameter Reference](parameter_reference.md) --- for example, pixel pitch
is specified in micrometers, altitude in meters.

---

## Resolution Precedence

Parameters resolve in a fixed priority order, lowest to highest:

| Priority | Source | Provenance tag |
|----------|--------|----------------|
| 1 (lowest) | Schema default (`ParameterDef.default`) | `DEFAULT` |
| 2 | An applied FPA preset | `PRESET` |
| 3 | The config-file body | `CONFIG_FILE` |
| 4 | `Sensor.set()` / `set_many()` | `USER_SET` |
| 5 (highest) | CLI `--set` | `USER_SET` |

An FPA preset sits below the config file deliberately: presets seed, explicit values win,
in any key order.

Every resolved parameter carries its provenance tag plus a source label — the config file
path, `Sensor.set`, or the CLI. Derived parameters carry `DERIVED` and a `derived_from`
record naming the inputs and their values, which is what `radiant explain` prints.

Setting every member of a consistency group explicitly triggers a consistency check; a
value conflicting with the derived one beyond the group tolerance is an error.

---

## File Paths Inside a Config

Parameters that name a file (a QE curve, a measured emissivity spectrum, a tape7, a
Zernike export) are resolved **relative to the config file's own directory**, not the
process working directory. A config and its data files therefore move together as a unit.

`Sensor.save()` and `to_yaml(relative_to=...)` write the reverse transform: an absolute
path stored in memory comes back out relative to the directory the YAML will live in.
That keeps a round-tripped config portable rather than pinned to one machine.

---

## Using Templates

RADIANT ships nine mission templates spanning VNIR, SWIR, MWIR, and LWIR bands at
altitudes from a 5 m lab bench to GEO, covering all three radiometric regimes. They are
the same set the GUI welcome screen offers.

```bash
radiant template list                        # see all available templates
radiant template show leo_mapping_extended   # print the YAML
radiant template create leo_mapping_extended # write leo_mapping_extended.yaml
```

The templates ship inside the package at `radiant/data/templates/` (CU-349 — they arrive
with `pip install radiant`; in a source checkout the same files sit at
`src/radiant/data/templates/`), so a template can also be run in place:

```bash
radiant run src/radiant/data/templates/leo_mapping_extended.yaml
```

The per-template table is in the [Command-Line Interface](tech_cli.md) chapter under
`radiant template`.

---

## Session Metadata — the `_radiant` Block

`Sensor.save(path)` writes an optional top-level `_radiant` mapping holding session state
that is not a chain parameter:

```yaml
_radiant:
  format: 1
  wavelength_points: 500          # spectral grid density
  tolerances:                     # only present when tolerances are set
    detector.qe_value:
      distribution: gaussian
      params: {std: 0.02}
optics:
  aperture_diameter_m: 0.3        # m
```

The loader strips the block before parameter flattening, applies `tolerances`, and raises
a `ConfigError` on a malformed block — a non-mapping, a missing `distribution` or
`params`, or an unknown parameter name. `wavelength_points` is session level:
`Sensor.load(path)` consumes it; a bare parameter load ignores it. Configs without a
`_radiant` block are unaffected, and a file `Sensor.save` wrote remains loadable by
`from_yaml` and the CLI.

Note what a saved file contains: **explicitly-set inputs only**, in input units. Defaults
and derived values are not written, so reloading reproduces the original resolution and
provenance exactly rather than freezing today's defaults into the file.

---

## Optical Element Trains — the `optical_elements` Section

A config may carry a declarative optical-element document instead of (or alongside) the
scalar `optics.transmission_scalar`. Each entry names an element, its transfer mode, its
temperature, and its reflectance or transmittance:

```yaml
optics:
  aperture_diameter_m: 0.3        # m
optical_elements:
  - {name: M1, transfer_mode: REFLECTIVE, reflectance: 0.97, temperature_K: 293.0}
  - {name: cold_filter, transfer_mode: REFRACTIVE, kind: FILTER,
     transmittance: 0.90, temperature_K: 240.0}
```

R and T values may be scalars, paths to a spectral CSV, or an inline spectral table
(`{wavelength_um: [...], values: [...]}` — the form the GUI's spectrum dialog writes,
which persists in the YAML with no external file).

**Emissivity never appears in an entry.** It is derived from Kirchhoff's law —
$\varepsilon = 1 - R$ for a mirror, $\varepsilon = 1 - T - R$ for a transmissive element.
An entry that supplies both R and $\varepsilon$ over-specifies the energy balance and is
rejected.

`Sensor.from_yaml` / `Sensor.load` / `Sensor.from_dict` parse and attach the section, and
`Sensor.save` writes it back out. Spectral-file references are made absolute on attach —
so the document evaluates from any working directory — and relative to the destination
directory on save, so a saved element-bearing config stays portable: move the config and
its data files together and the references still resolve.

`radiant run` and `radiant validate` both act on the section: run parses the document onto
the run grid, validate normalizes it and reports its errors.

---

## Named FPA Presets — the `fpa` Key

A scalar section naming one preset from the bundled FPA library:

```yaml
fpa: teledyne-h2rg-2p5
readout:
  read_noise_e_rms: 6.0   # e- RMS — explicit, wins over the preset's value
```

Every `detector.*` / `readout.*` value the preset carries is applied with provenance
`PRESET` **unless the config sets that dot-path explicitly — explicit values always win**,
in any key order. The applied set and the kept set are both reported through
`Sensor.fpa_applications()`.

`Sensor.save` writes the applied values as ordinary explicit inputs and does *not*
re-serialize the `fpa:` key: reloading a saved config reproduces the same numbers with
config-file provenance, while the preset attribution lives in the preset document. The
part list is in the [Data Libraries](tech_data_libraries.md) chapter.

---

## Atmosphere Configuration

RADIANT ships a real MODTRAN-derived atmosphere library, so a high-fidelity atmosphere
needs no MODTRAN license and no external files:

```yaml
atmosphere:
  model: interpolated        # measured MODTRAN data, interpolated over the scene geometry
```

With `interpolated` and no `atmosphere.interpolated_data_dir`, the loader selects the
bundled family that matches the scene's line-of-sight direction and the configured
`atmosphere.interpolation_axes`. The model does not extrapolate: outside a family's nodes
it refuses, by design, rather than inventing an answer. Point it at your own MODTRAN run
matrix with:

```yaml
atmosphere:
  model: interpolated
  interpolated_data_dir: path/to/my_runs   # directory of NPZ runs
```

`atmosphere.model` takes five values. `simple` is the always-works analytic baseline —
the only backend that can serve an arbitrary path topology, so it is the right answer
when you are unsure. `exo` is an explicitly vacuum path. The two file-driven backends are
geometry-agnostic by construction — they do not respond to the scene at all — and need
explicit paths:

```yaml
atmosphere:
  model: tabulated
  tabulated_transmittance_file: path/to/transmittance.csv   # or a single .npz
  tabulated_path_radiance_file: path/to/path_radiance.csv
  tabulated_downwelling_file: path/to/downwelling.csv       # optional
```

```yaml
atmosphere:
  model: modtran
  modtran:
    tape7_path: path/to/tape7
```

CSV files must have `wavelength_um` as the first column. Choosing between the five
backends for a given scene is the subject of the
[Atmosphere Selection Guide](atmosphere_selection.md).

The shipped families, their coverage, and the provenance of the underlying MODTRAN run
matrix are documented in the [Data Libraries](tech_data_libraries.md) chapter and in
`src/radiant/data/tables/atmospheres/README.md`. Ingest of external atmosphere data is
covered in [External Data Interfaces](tech_external_data.md).

---

## Configuration Sets --- Several Configurations in One File

One config file can describe **one modeling problem in up to twelve named
variants of itself**: MWIR vs. LWIR on the same telescope, nominal vs.
as-built, three off-nadir geometries. Add a top-level `configurations:` section
and the file becomes a **study**.

Three words, used consistently everywhere in RADIANT:

- **config file** --- the YAML artifact on disk.
- **configuration** --- one member of a configuration set (`MWIR`, `LWIR`).
- **configuration set** (or **study**) --- the whole document: the shared
  parameters plus the per-configuration ones.

Everything in the ordinary body of the file is **shared** --- one value for
every configuration. The `configurations:` section names the configurations and
lists only the parameters that *differ*, each as a dense list of values aligned
with the names:

```yaml
# --- shared body: an ordinary RADIANT config, one value for ALL configurations ---
_radiant:
  format: 1
  wavelength_points: 500        # shared spectral grid density
geometry:
  sensor_altitude_m: 8000.0     # m
optics:
  aperture_diameter_m: 0.30     # m
  focal_length_m: 1.20          # m -> f/4.0
  transmission_scalar: 0.70     # dimensionless
detector:
  pixel_pitch_x_um: 18.0        # um
  pixel_pitch_y_um: 18.0        # um
source:
  target:
    temperature: 300.0          # K
    emissivity: 0.95            # dimensionless

# --- what makes this file a study ---
configurations:
  names: [MWIR, LWIR]           # 1-12 unique names; defines the value order below
  active: MWIR                  # configuration the GUI opens on (optional)
  baseline: MWIR                # delta reference for comparisons (optional)
  wavelength_points:            # optional per-configuration grid density
    LWIR: 300                   # points (MWIR inherits the shared 500)
  parameters:                   # dot-path -> one value per name, in input units
    spectral_integration.filter_min_um: [3.5, 8.0]            # um
    spectral_integration.filter_max_um: [5.0, 12.0]           # um
    spectral_integration.integration_time_s: [0.005, 0.0005]  # s
    detector.qe_value: [0.70, 0.55]                           # dimensionless
    readout.full_well_capacity_e: [2.0e6, 6.0e6]              # e-
```

Read that as a table: `MWIR` is 3.5--5.0 um integrated 5.0 ms at QE 0.70,
`LWIR` is 8.0--12.0 um integrated 0.5 ms at QE 0.55, and both look through the
same 0.30 m f/4 telescope from 8000 m at the same 300 K scene. Change
`optics.aperture_diameter_m` once and both configurations move together --- the
study states what differs, not what is repeated.

The binding rules, all checked at load time with an error naming the file, the
configuration, and the parameter:

- **`names`** --- 1 to 12 unique, non-empty names (`ConfigurationSet.MAX_CONFIGS`, raised
  from 8 to 12 in 2026-09). This list defines the order of every value list below it.
- **`parameters`** --- every list has exactly as many values as there are names.
  The lists are dense by construction: there is no "unset for this
  configuration" and nothing is padded for you.
- **Shared or configured, never both.** A dot-path that appears in
  `configurations.parameters` must *not* also appear in the shared body ---
  the shared value would be silently shadowed. Move a parameter into the
  section, do not copy it.
- **Values are in input units** --- exactly the units the shared body uses, so
  `filter_min_um` is micrometers here too. Type, bounds, and enum checks run
  per configuration.
- **Shared regardless:** tolerance distributions, the `optical_elements`
  document, and the default `_radiant.wavelength_points`. Only the grid
  *density* is per configuration; each configuration's grid *span* already
  follows its own resolved band.

Running and validating a study from the CLI:

```bash
# One configuration by name --- required for a study file.
radiant run study.yaml --configuration LWIR

# Validate EVERY configuration; one line each, non-zero exit if any failed.
radiant validate study.yaml
```

In the GUI, a study file opens with a configuration tab strip above the
signal-chain strip, and **Edit -> Configurations...** adds, renames, reorders,
and duplicates configurations.

**Plain config files are unchanged.** A file with no `configurations:` key is
byte-for-byte today's format and loads everywhere exactly as before --- nothing
in this section is required, and nothing about it changed existing output. A
study file, conversely, is only loaded by tools that understand the section:
`radiant run --configuration` / `radiant validate` and, in Python,
`ConfigurationSet.load`. Loading one as a plain single sensor is refused with an
error pointing at the right entry point, so a study is never silently run as if
its shared body were the whole model.

For building, evaluating, and comparing a study, see the
[Trade Studies Guide](trade_studies.md); for the complete section
specification, `docs/architecture/RADIANT_Config_Format.md` §1.9.

---

## Common Patterns

### Change one parameter and re-run

```bash
radiant run config.yaml --set optics.aperture_diameter_m=0.40
```

### Compare two config files

```bash
radiant compare config_a.yaml config_b.yaml
```

This compares two *files* --- two separate designs. To compare named
configurations *within* one study file, see **Configuration Sets** above and
the [Trade Studies Guide](trade_studies.md).

### Batch many scenarios (Python)

```python
from radiant.api import Sensor

base = Sensor.from_yaml("examples/mwir_leo_minimal.yaml")
altitudes = [5000, 8000, 12000, 20000]

for alt in altitudes:
    s = base.clone()
    s.set("geometry.sensor_altitude_m", alt)
    r = s.evaluate()
    snr = r.metrics["snr"]
    # Process snr for each altitude
```
