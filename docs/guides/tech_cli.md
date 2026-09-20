# Command-Line Interface

Installing RADIANT puts a single console entry point on the path, `radiant`
(`radiant.cli.main:cli`). It is a Click command group: `radiant --help` lists the
subcommands, and `radiant <subcommand> --help` gives that subcommand's options.

```
Usage: radiant [OPTIONS] COMMAND [ARGS]...

  RADIANT — first-principles EO sensor performance modeling.

Options:
  --version  Show the version, load path, and git commit, then exit.
  --help     Show this message and exit.

Commands:
  compare    Compare two configurations side-by-side.
  convert    Convert a value between RADIANT-supported units.
  explain    Explain how a parameter got its value.
  gui        Launch the RADIANT desktop GUI, optionally on a YAML config file.
  run        Run the RADIANT signal chain from a YAML config file.
  schema     List all parameter definitions.
  sweep      Run a 1-D parameter sweep.
  template   Manage sensor configuration templates.
  tolerance  Run Monte Carlo tolerance analysis.
  validate   Validate a YAML config file without running the chain.
```

**Exit codes.** Every command exits 0 on success and 1 on a RADIANT-level failure — a
missing file, a validation error, an unknown parameter, an unresolvable config. Click
itself exits 2 for a malformed command line. That makes the CLI usable in a shell script
without parsing its text output.

**`--version` is a provenance tool, not a banner.** It prints the version, the directory
the running package was imported from, and the git commit — which is what a stale-install
mismatch actually needs:

```
$ radiant --version
radiant 0.1.0
  loaded from: /Users/example/ssr/src/radiant
  git commit:  738ad8c0 (dirty)
```

---

## `radiant run` — evaluate a config

```
Usage: radiant run [OPTIONS] CONFIG
```

| Option | Meaning |
|--------|---------|
| `--set TEXT` | Parameter override, `key=value`, repeatable |
| `--configuration NAME` | Which configuration of a study file to evaluate |
| `--wavelength-min FLOAT` | Override the spectral grid minimum [µm] |
| `--wavelength-max FLOAT` | Override the spectral grid maximum [µm] |
| `--wavelength-points INTEGER` | Grid point count (default 500 points) |
| `--output PATH` | Write results to a file |
| `--provenance PATH` | Write the provenance record to a JSON file |
| `--format [text\|json\|csv]` | Output format (default `text`) |
| `--quiet` | Suppress everything except the final metric summary |

```bash
radiant run examples/mwir_leo_minimal.yaml
radiant run examples/mwir_leo_minimal.yaml --set optics.aperture_diameter_m=0.5
radiant run examples/mwir_leo_minimal.yaml --format json --output result.json
radiant run examples/mwir_leo_minimal.yaml --provenance run_provenance.json
radiant run study.yaml --configuration LWIR
```

The default text output is the signal and the full noise budget, every term with units,
followed by the RSS total and the headline metric:

```
Signal:  1263548.28 e-
  signal_shot      1124.0766 e- RMS
  background_shot  0.0000 e- RMS
  dark_shot        0.7071 e- RMS
  read_noise       5.0000 e- RMS
  quantization     9.2376 e- RMS
  ...
Noise (RSS): 1124.1259 e- RMS
SNR:     1124.03
```

`--configuration` is **required** for a study file (one carrying a `configurations:`
section) and **rejected** for a plain config — a study is never silently run as if its
shared body were the whole model.

`--set` overrides sit at the top of the precedence ladder: schema default → config-file
body → programmatic `Sensor.set()` → CLI `--set`.

---

## `radiant validate` — check a config without running it

```
Usage: radiant validate [OPTIONS] CONFIG
```

Checks that the file parses, every parameter name is known, types are correct, and every
required parameter is set. It reports **all** errors at once rather than stopping at the
first — this collect-all behavior is specific to this command; the scripting API and the
GUI are fail-fast by design.

```bash
$ radiant validate examples/mwir_leo_minimal.yaml
Config OK: examples/mwir_leo_minimal.yaml
  218 parameters resolved.
```

A study file validates **every** configuration and prints one line each, so no
configuration's failure hides another's. The exit status is non-zero if any failed.

`--set` is accepted here too, so an override can be validated before it is run.

---

## `radiant explain` — where a value came from

```
Usage: radiant explain [OPTIONS] CONFIG PARAM
```

Prints the value, the unit, the provenance class, the source label, and the derivation
chain for one parameter:

```
$ radiant explain examples/mwir_leo_minimal.yaml optics.f_number
optics.f_number = 4.0  (canonical: 4.0 )
  Description: Dimensionless f/# = focal_length_m / aperture_diameter_m. Part of the
               {D, f, f/#} consistency group; supply any two and the third is derived.
  Provenance: derived
  Source: derived: f_number = focal_length_m / aperture_diameter_m
  Derived from:
    optics.aperture_diameter_m = 0.3
    optics.focal_length_m = 1.2
```

This is the command to reach for when a number is not what you expected: it distinguishes
"you set it", "the file set it", "the schema defaulted it", and "a consistency group
derived it from these two inputs".

---

## `radiant gui` — launch the desktop application

```
Usage: radiant gui [OPTIONS] [CONFIG]
```

```bash
radiant gui
radiant gui examples/mwir_leo_minimal.yaml
```

The GUI ships in the optional extra. Without it, the command exits 1 with an actionable
message naming the install:

```bash
pip install "radiant[gui]"
```

With no `CONFIG` the window opens on the welcome screen — mission-template cards, **Blank
config**, the worked examples and the recent-files list — exactly the surface **File ▸ New**
returns to. Passing a study file opens it with its configuration tab strip.

---

## `radiant sweep` — 1-D sweep from the shell

```
Usage: radiant sweep [OPTIONS] CONFIG PARAM
```

| Option | Meaning |
|--------|---------|
| `--min FLOAT` | Sweep minimum (required), in the parameter's input unit |
| `--max FLOAT` | Sweep maximum (required), in the parameter's input unit |
| `--steps INTEGER` | Number of points (default 10) |
| `--metric TEXT` | Metric key to report (default `snr`) |
| `--output PATH` | Save to JSON or CSV — the extension picks the format |
| `--plot PATH` | Save a PNG plot (requires matplotlib) |
| `--set TEXT` | Parameter override, repeatable |

```bash
radiant sweep examples/mwir_leo_minimal.yaml optics.aperture_diameter_m \
    --min 0.15 --max 0.60 --steps 10 --metric snr --output sweep.csv
```

---

## `radiant tolerance` — Monte Carlo from the shell

```
Usage: radiant tolerance [OPTIONS] CONFIG
```

| Option | Meaning |
|--------|---------|
| `--trials INTEGER` | Number of MC trials (default 100) |
| `--seed INTEGER` | Random seed (default 42) |
| `--tolerance TEXT` | `"param distribution key=val ..."`, repeatable |
| `--output PATH` | Save results to JSON |
| `--set TEXT` | Parameter override, repeatable |

```bash
radiant tolerance examples/mwir_leo_minimal.yaml --trials 50 \
    --tolerance "optics.aperture_diameter_m gaussian std_fraction=0.02" \
    --tolerance "optics.transmission_scalar gaussian std_fraction=0.05"
```

Tolerances may also live in the config's `_radiant.tolerances` block, in which case no
`--tolerance` flag is needed. The run is reproducible from `--seed`.

---

## `radiant compare` — two files side by side

```
Usage: radiant compare [OPTIONS] CONFIG1 CONFIG2
```

Evaluates both configs and prints a metric diff table; `--output PATH` saves it as JSON.

```bash
radiant compare config_a.yaml config_b.yaml
```

This compares two *files* — two separate designs. To compare named configurations
*within* one study file, use `ConfigurationSet` from Python (see the Configuration Guide).

---

## `radiant schema` — list the parameter definitions

```
Usage: radiant schema [OPTIONS]
```

| Option | Meaning |
|--------|---------|
| `--format [text\|json]` | Output format (default `text`) |
| `--stage TEXT` | Filter to one stage prefix, e.g. `optics`, `detector` |

```bash
radiant schema
radiant schema --stage optics
radiant schema --format json > schema.json
```

The same registry that backs this command generates the Parameter Reference chapter of
this volume, so the two never disagree.

---

## `radiant template` — bundled starting points

```
Usage: radiant template [OPTIONS] COMMAND [ARGS]...

Commands:
  create  Copy a template YAML to a file as a starting point.
  list    List the bundled mission templates (the GUI welcome-screen set).
  show    Print a template configuration as YAML.
```

```bash
radiant template list
radiant template show leo_mapping_extended
radiant template create leo_mapping_extended
```

The nine bundled mission templates are the same set the GUI welcome screen offers. Each
one is a complete, runnable config spanning a distinct band, altitude, and regime:

| Template | Band | Geometry | Regime |
|----------|------|----------|--------|
| `aerial_vnir_imaging` | VNIR 0.4–0.9 µm | 3 km nadir | extended reflective |
| `airborne_lwir_surveillance` | LWIR 8–12 µm | 8 km airborne | extended |
| `geo_lwir_staring` | LWIR 8–12 µm | GEO nadir | extended |
| `ground_to_air_mwir_detection` | MWIR 3–5 µm | up-looking, 60° zenith | point source |
| `lab_blackbody_calibration` | MWIR 3.5–5 µm | 5 m horizontal path | extended blackbody |
| `leo_mapping_extended` | MWIR 3.5–5 µm | 500 km nadir | extended |
| `leo_swir_mapping` | SWIR 1.0–2.5 µm | 500 km nadir | extended reflective |
| `maritime_subpixel_lwir` | LWIR 8–12 µm | 500 km LEO | sub-pixel vessel |
| `sda_space_to_space` | MWIR 3.5–5 µm | LEO → GEO, exo path | point source |

They ship inside the package at `radiant/data/templates/`, so they arrive with
`pip install radiant`; in a source checkout the same files sit at
`src/radiant/data/templates/`.

---

## `radiant convert` — scalar unit conversion

```
Usage: radiant convert [OPTIONS] VALUE FROM_UNIT TO_UNIT
```

```bash
$ radiant convert 18 um m
18.0 um = 1.8e-05 m

$ radiant convert 45 deg rad
45.0 deg = 0.785398 rad

$ radiant convert 5 ms s
5.0 ms = 0.005 s
```

A convenience calculator over the same unit registry the parameter boundary uses. It
converts scalars only — it does not read or write config files.
