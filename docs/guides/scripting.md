# Scripting Guide

*Persona: Sarah (systems engineer), Tom (optical designer), Dr. Chen (researcher)*

Using the Python API for programmatic sensor modeling, sweeps, and analysis.

---

## The Import Surface

Two names are guaranteed stable and live at the top level:

```python
from radiant import Sensor, RadiantError
```

Everything else is reached through `radiant.api` (`ChainResult`, `SweepResult`,
`MonteCarloResult`, `SensitivityResult`, `SolveResult`, `ConfigurationSet`,
`ErrorBudget`, `compare_configs`, the plotting helpers) or, for the batch matrix,
`radiant.api.batch`. `from radiant.api import Sensor` resolves to the same class as the
top-level import.

There are no `SensorConfig` or `ScenarioConfig` builder classes. `Sensor.from_yaml()`
and `Sensor.from_dict()` already accept everything such a wrapper would have carried.

---

## The Sensor Class

`Sensor` is the primary Python entry point. It wraps configuration, parameter
resolution, and chain execution into a single object.

### Creating a Sensor

From a YAML file:

```python
from radiant.api import Sensor

sensor = Sensor.from_yaml("examples/mwir_leo_minimal.yaml")
```

From a Python dict:

```python
from radiant.api import Sensor

config = {
    "source": {"target": {"temperature": 300.0, "emissivity": 0.95}},
    "geometry": {"sensor_altitude_m": 8000.0},
    "optics": {"aperture_diameter_m": 0.30, "focal_length_m": 1.20,
               "transmission_scalar": 0.70},
    "detector": {"pixel_pitch_x_um": 18.0, "pixel_pitch_y_um": 18.0,
                 "qe_value": 0.70, "dark_rate_e_per_s": 100.0},
    "spectral_integration": {"filter_min_um": 3.5, "filter_max_um": 5.0,
                             "integration_time_s": 0.005},
    "readout": {"read_noise_e_rms": 5.0, "gain_e_per_dn": 1.0, "adc_bits": 16},
}
sensor = Sensor.from_dict(config)
```

Both constructors take `wavelength_points` (default 500 points), the number of samples on
the common spectral grid. The grid always spans the sensor's own resolved
`spectral_integration.filter_min_um` … `filter_max_um`; only the density is set here.

```python
from radiant.api import Sensor

sensor = Sensor.from_yaml("examples/mwir_leo_minimal.yaml", wavelength_points=1000)
sensor.wavelength_points                 # 1000 points
coarse = sensor.with_wavelength_points(200)   # a clone; `sensor` is untouched
```

`with_wavelength_points(n)` rejects `n < 2` with an `ApiValidationError` — the same check
`Sensor.load()` applies to the `_radiant.wavelength_points` metadata field.

`Sensor.load(path)` is the counterpart of `Sensor.save()`: it restores parameters,
tolerance distributions, and the grid size from the file's `_radiant` block. A plain
config loads exactly as through `from_yaml`.

### Setting and Getting Parameters

```python
from radiant.api import Sensor

sensor = Sensor.from_yaml("examples/mwir_leo_minimal.yaml")
sensor.set("optics.aperture_diameter_m", 0.50)
diameter = sensor.get("optics.aperture_diameter_m")
```

`set()` returns the sensor for chaining:

```python
from radiant.api import Sensor

sensor = Sensor.from_yaml("examples/mwir_leo_minimal.yaml")
sensor.set("optics.aperture_diameter_m", 0.50).set("detector.qe_value", 0.80)
result = sensor.evaluate()
```

### Resetting a parameter to its default

```python
from radiant.api import Sensor

sensor = Sensor.from_yaml("examples/mwir_leo_minimal.yaml")
sensor.set("detector.dark_rate_e_per_s", 500.0)
sensor.reset("detector.dark_rate_e_per_s")  # back to config-file value
```

`reset_all(scope="user_set")` (the default) drops every input whose provenance is
`USER_SET`; inputs still carrying config-file provenance survive. Note that an edit
*replaces* an input's provenance, so a config value that was later edited reverts to its
schema default, not to the file value — there is no layered history. To get the file back
exactly, reload it. `reset_all(scope="all")` removes every explicit input, leaving pure
schema defaults.

### Entering a Value in Your Own Unit

`set()` takes a `unit=` keyword and converts at that boundary — the single conversion
point for user input. The value you pass is in *your* unit; what gets stored is canonical.

```python
from radiant.api import Sensor

sensor = Sensor.from_yaml("examples/mwir_leo_minimal.yaml")
sensor.set("optics.aperture_diameter_m", 30.0, unit="cm")     # 30 cm -> 0.30 m
sensor.set("geometry.solar_zenith_rad", 30.0, unit="deg")     # 30 deg -> 0.5236 rad
sensor.set("source.target.temperature", 27.0, unit="degC")    # 27 degC -> 300.15 K
```

`set()` also takes `source=`, the human-readable provenance label recorded with the
input and shown by `resolved()` and `explain()`. It defaults to `"Sensor.set"`; a caller
setting values on behalf of a named context passes its own label. The provenance *class*
stays `USER_SET` either way.

### Inspecting Parameters and Provenance

```python
from radiant.api import Sensor

sensor = Sensor.from_yaml("examples/mwir_leo_minimal.yaml")

sensor.get("optics.f_number")            # resolved canonical value (derived here)
sensor.get_input("optics.aperture_diameter_m")   # the value as entered, input units
sensor.inputs()                          # read-only mapping of every explicit input
sensor.resolved("optics.f_number")       # ResolvedValue: value, units, provenance
sensor.provenance("optics.f_number")     # Provenance enum member (DERIVED here)

sensor.parameter_defs()                  # dot-path -> ParameterDef, the whole schema
sensor.parameter_def("detector.qe_value")        # one ParameterDef

print(sensor.summary())                  # every resolved parameter, grouped, with units
print(sensor.explain("optics.f_number")) # one parameter's value and derivation chain
print(sensor.explain())                  # full chain walkthrough of the latest run
```

`Provenance` members are `USER_SET`, `CONFIG_FILE`, `DEFAULT`, `DERIVED`, `SAMPLED`, and
`PRESET`.

### Saving a Sensor

```python
from radiant.api import Sensor

sensor = Sensor.from_yaml("examples/mwir_leo_minimal.yaml")
sensor.set("optics.aperture_diameter_m", 0.50)

sensor.save("my_design.yaml")            # explicit inputs + _radiant metadata block
yaml_text = sensor.to_yaml()             # the same document as a string, no temp file
full = sensor.to_yaml(scope="resolved")  # every resolved parameter, for documentation
```

`save()` writes only the explicitly-set inputs, in input units, plus a `_radiant` block
carrying `wavelength_points` and any tolerance distributions. Reloading reproduces the
sensor exactly: defaults re-apply, consistency groups re-derive, and the provenance
distinction between explicit and defaulted values survives. The file is an ordinary
RADIANT config — `from_yaml` and the CLI read it too.

`to_yaml(relative_to=...)` rewrites absolute file-path parameters relative to the
directory the emitted YAML will live in, so an element-bearing config stays portable.

### Applying an FPA Preset

```python
from radiant.api import Sensor

sensor = Sensor.from_yaml("examples/mwir_leo_minimal.yaml")
report = sensor.apply_fpa("teledyne-h2rg-2p5")

report.part               # 'teledyne-h2rg-2p5'
report.applied            # dot-paths the preset set, with Provenance.PRESET
report.skipped_existing   # dot-paths the config had set explicitly — those won
report.qe_material        # the QE library curve the preset selected, or None
sensor.fpa_applications()   # the live report(s), for provenance inspection
sensor.remove_fpa()         # returns the dot-paths cleared
```

Presets seed; explicit values win, in any order. Values applied by a preset persist
through `save()` as ordinary explicit inputs — the `fpa:` key itself is not
re-serialized. The bundled part list is in the **Data Libraries** chapter.

### Attaching an Optical Element Train

```python
from radiant.api import Sensor

sensor = Sensor.from_yaml("examples/mwir_leo_minimal.yaml")
sensor.set_optical_elements([
    {"name": "M1", "transfer_mode": "REFLECTIVE", "reflectance": 0.97,
     "temperature_K": 293.0},
    {"name": "cold_filter", "transfer_mode": "REFRACTIVE", "kind": "FILTER",
     "transmittance": 0.90, "temperature_K": 240.0},
])
sensor.optical_elements()     # the stored document, or None
```

The document is validated immediately through the io parser — including the Kirchhoff
check, so an entry carrying both reflectance and emissivity is rejected — normalized, and
parsed onto the current wavelength grid at every evaluation. Unlike raw stage-output
injections it *is* written by `save()` and restored by `load()`. Pass `None` to remove it.

### Injecting Non-Scalar Inputs

Stages never read files, so file-derived objects are built before the chain and
injected as pre-chain stage outputs:

```python
from radiant.api import Sensor

sensor = Sensor.from_yaml("examples/mwir_leo_minimal.yaml")
sensor.set_stage_output("optics_config", "psf_weighting_spectrum", spectrum)

# Or one-off, for a single run:
result = sensor.evaluate(extra_stage_outputs={"optics_config": {"element_list": elements}})
```

Injections set via `set_stage_output` apply to every evaluation, including sweeps and
Monte Carlo runs. They are **not** serialized by `save()` — only the declarative
`optical_elements` document is.

---

## Working with ChainResult

`sensor.evaluate()` returns a `ChainResult` with several views into the
completed signal chain.

```python
from radiant.api import Sensor

sensor = Sensor.from_yaml("examples/mwir_leo_minimal.yaml")
result = sensor.evaluate()
```

### Metrics

`result.metrics` is a dict of computed performance numbers:

```python
from radiant.api import Sensor

sensor = Sensor.from_yaml("examples/mwir_leo_minimal.yaml")
result = sensor.evaluate()
snr = result.metrics["snr"]
contrast_snr = result.metrics["contrast_snr"]
mtf_nyq = result.metrics["mtf_at_nyquist"]
rer = result.metrics["rer"]
ee_1x1 = result.metrics["ee_1x1"]
```

`result.metrics` is a bare name → value mapping and carries no units. For anything a
human will read, use `metric_records()` instead — every value arrives with its unit and
description from the metric registry:

```python
from radiant.api import Sensor

sensor = Sensor.from_yaml("examples/mwir_leo_minimal.yaml")
result = sensor.evaluate()

for rec in result.metric_records():
    print(f"{rec.name} = {rec.value:.4g} {rec.unit}  ({rec.kind}) — {rec.description}")
```

Each `MetricRecord` carries `name`, `value`, `unit` (always a non-empty string),
`description`, and `kind` — `"float"`, `"flag"` (a 0/1 boolean), or `"code"` (an
enumeration encoded as a float, with the levels named in the description). Records come
back in sorted-name order.

Two export views build on the same records:

```python
result.to_records()          # list of {name, value, unit, description} dicts
result.to_csv("metrics.csv") # name,value,unit,description — UTF-8
```

There are also convenience accessors for the three headline metrics; each raises
`KeyError` if that metric was not computed for the run:

```python
result.snr()      # dimensionless
result.nedt()     # K    — reads metrics['nedt_K']
result.niirs()    # dimensionless
```

### Stage Outputs

Each stage stores intermediate results accessible via `result.stage_outputs`:

```python
from radiant.api import Sensor

sensor = Sensor.from_yaml("examples/mwir_leo_minimal.yaml")
result = sensor.evaluate()
regime = result.stage_outputs["optics"]["regime"]
tau_atm = result.stage_outputs["atmosphere"]["tau_atm"]
```

### Radiometric Frames

Frames are snapshots of the signal at key propagation points:

```python
from radiant.api import Sensor

sensor = Sensor.from_yaml("examples/mwir_leo_minimal.yaml")
result = sensor.evaluate()
frame_names = list(result.frames.keys())
# For examples/mwir_leo_minimal.yaml: ['at_aperture_target', 'at_aperture',
# 'at_source_target', 'at_source_target_reflected', 'post_optics', 'photoelectrons']
```

Which frames exist depends on the scene: a reflective scene registers
`at_source_target_reflected`, a point-source run registers the intensity frames. Use
`result.signal_at(...)` (below) when you want a value at a *named reference frame*
regardless of which snapshots this particular run happened to register.

### Noise Terms

Individual noise contributions (in electrons):

```python
from radiant.api import Sensor

sensor = Sensor.from_yaml("examples/mwir_leo_minimal.yaml")
result = sensor.evaluate()
for nt in result.noise_terms:
    if nt.value_e > 0.1:
        pass  # nt.name, nt.value_e are the key attributes
```

`explain_noise(name)` returns a structured account of one term rather than prose fields
you have to assemble yourself:

```python
from radiant.api import Sensor

sensor = Sensor.from_yaml("examples/mwir_leo_minimal.yaml")
result = sensor.evaluate()

exp = result.explain_noise("signal_shot")
exp.value_e             # e- RMS at its origin frame
exp.origin_frame        # where the noise was generated
exp.physical_basis      # the mechanism tag
exp.contributes_to      # which budgets it sums into
exp.share_of_variance   # value^2 / sum(value^2) — the pie-chart fraction
print(exp.description)  # the same fields pre-formatted, with units
```

An unknown term name raises `KeyError` listing the available terms — never a `None`.

### Reading a Value at Another Reference Frame

Signal and noise can be read at any point in the chain, propagated through the stored
transfer factors:

```python
from radiant.api import Sensor

sensor = Sensor.from_yaml("examples/mwir_leo_minimal.yaml")
result = sensor.evaluate()

q = result.signal_at("at_aperture")   # ChainQuantity: .value, .frame, .unit, .name
n = result.noise_at("dn")             # total noise expressed in DN
n_shot = result.noise_at("dn", "signal_shot")  # one term at that frame
```

The six frames are `at_target`, `at_aperture`, `post_optics`, `photoelectrons`,
`post_readout`, and `dn` (the `ReferenceFrame` enum in `radiant.core.quantity`; a plain
string works too). Pre-integration frames are spectral-only by design — the chain allows
exactly one spectral collapse — so `result.frames["at_aperture"].in_band_value` is
deliberately `None` and `signal_at` is the only way to read an in-band scalar there.

### Saturation Status

```python
from radiant.api import Sensor

sensor = Sensor.from_yaml("examples/mwir_leo_minimal.yaml")
result = sensor.evaluate()

well = result.well_status()
well.status                 # the clip state string
well.fill_fraction          # dimensionless, 0-1
well.total_well_e           # e-
well.full_well_capacity_e   # e-
well.is_saturated           # bool
```

### Browsing the Whole Result

```python
print(result.inspect())            # the full readable result tree
print(result.inspect("optics"))    # scoped to one stage
```

### Saving and Reloading a Result

```python
from radiant.api import ChainResult

path = result.save("run_042.zip")       # single-file zip archive: JSON + npz
again = ChainResult.load("run_042.zip")
again.metrics["snr"]                     # every state accessor works as before
```

The archive holds the full `ChainState` — frames, noise terms, stage outputs, MTF terms,
metrics, history — plus the provenance record frozen at save time. A reloaded result has
no attached `ParameterSet`; the run's resolved parameters live in the provenance record,
returned unchanged by `to_provenance_record()`.

### Provenance

```python
rec = result.to_provenance_record()
rec["run_id"]               # UUID4 minted by the chain runner
rec["radiant_version"]      # e.g. '0.1.0'
rec["git_commit"]           # short SHA, or 'unknown' outside a git repo
rec["python_version"]       # 'MAJOR.MINOR.PATCH'
rec["dependency_versions"]  # {name: version} for numpy, scipy, pyyaml, click
rec["parameter_set"]        # {dotpath: ResolvedValue.to_dict()} — every parameter
rec["input_file_hashes"]    # [{'path': ..., 'sha256': ...}] for every config consumed
rec["active_models"]        # the ordered stage names that ran
```

Provenance is mandatory and cannot be disabled. The helpers never raise on environmental
edge cases — no git, a missing dependency — they degrade to `"unknown"` rather than
blocking a run.

---

## Parameter Sweeps

### 1D Sweep

```python
from radiant.api import Sensor
import numpy as np

sensor = Sensor.from_yaml("examples/mwir_leo_minimal.yaml")
result = sensor.sweep(
    "optics.aperture_diameter_m",
    np.linspace(0.10, 0.60, 11),
    metric="snr",
)
# result.values — array of aperture values
# result.metric_values — corresponding SNR values
```

`SweepResult` carries `param_name`, `values`, `metric_values`, `metric_name`, and — when
`keep_results=True` (the default) — the full `ChainResult` at every point in `results`.
Any other metric can then be pulled across the whole sweep, and the sweep exports
directly:

```python
snr_curve  = result["snr"]                 # KeyError if keep_results was False
nedt_curve = result["nedt_K"]              # K
result.to_csv("aperture_sweep.csv")        # param column + every kept metric
first = result.at_metric_threshold(50.0)   # (param_value, metric_value) or None
```

`metric` also accepts a callable `(ChainResult) -> float`, so a derived quantity can be
swept without adding a metric:

```python
result = sensor.sweep(
    "optics.aperture_diameter_m",
    np.linspace(0.10, 0.60, 11),
    metric=lambda r: r.metrics["snr"] / r.metrics["mtf_at_nyquist"],
)
```

`n_workers` above 1 runs the points in parallel processes; `keep_results=False` drops the
per-point `ChainResult` objects when only the metric curve is wanted.

### 2D Sweep

```python
from radiant.api import Sensor
import numpy as np

sensor = Sensor.from_yaml("examples/mwir_leo_minimal.yaml")
result = sensor.sweep_2d(
    "optics.aperture_diameter_m", np.linspace(0.10, 0.60, 6),
    "spectral_integration.integration_time_s", np.array([0.001, 0.005, 0.010]),
    metric="snr",
)
# result.grid — 2D array, shape (len(values1) x len(values2))
```

`Sweep2DResult` carries `param1_name`, `param2_name`, `values1`, `values2`, `grid`, and
`metric_name`. `result.to_csv(path)` writes the grid in long form
(`param1, param2, metric`).

---

## Solving for a Parameter Value

The inverse of a sweep: find the parameter value that hits a target metric. Brent root
finding runs on the forward model over the given bracket, in input units.

```python
from radiant.api import Sensor

sensor = Sensor.from_yaml("examples/mwir_leo_minimal.yaml")
res = sensor.solve_for(
    "optics.aperture_diameter_m",
    50.0,                       # target SNR (dimensionless)
    bounds=(0.05, 1.0),         # m
    metric="snr",
)
res.solution     # aperture [m] that gives SNR = 50
```

If the target is not bracketed by the two endpoints, `solve_for` raises
`radiant.api.solve.SolveBracketError` carrying both endpoint metric values — so the
message tells you which way to widen the bracket.

---

## Monte Carlo Tolerance Analysis

Assign statistical tolerances to parameters and run a Monte Carlo ensemble:

```python
from radiant.api import Sensor

sensor = Sensor.from_yaml("examples/mwir_leo_minimal.yaml")
sensor.set_tolerance("optics.transmission_scalar", "gaussian", mean=0.70, std=0.03)
sensor.set_tolerance("detector.qe_value", "gaussian", mean=0.70, std=0.05)

mc = sensor.monte_carlo(n_trials=200, seed=42)
# mc.mean("snr"), mc.std("snr") — summary statistics
# mc.metric_names — tuple of available metric names
# mc.metric_array — 2D array (n_trials x n_metrics)
```

The supported distributions are `"gaussian"`, `"uniform"`, `"truncated_gaussian"`, and
`"log_normal"`; the keyword arguments are the distribution's own parameters.
`sensor.tolerances()` is the read-back view and `clear_tolerance(dotpath)` removes one.
Tolerances persist through `save()` / `to_yaml()` in the `_radiant.tolerances` block.

`MonteCarloResult` carries `n_trials`, `seed`, `metric_names`, `metric_array`,
`sampled_params` (dot-path → the per-trial sampled values), and — with
`keep_results=True` — every `ChainResult`. Its query surface:

```python
mc.mean("snr")                              # dimensionless
mc.std("snr")                               # dimensionless
mc.percentile("snr", 5.0)                   # 5th-percentile SNR
mc.probability_of_exceeding("snr", 20.0)    # fraction of trials with SNR > 20
mc.correlation("snr")                       # {param: Pearson r} against each sampled input
mc.to_dict()                                # {metric or param: 1-D array}
mc.to_csv("tolerance_trials.csv")           # one row per trial
```

The run is fully deterministic in `seed`: the same seed and the same tolerances give
identical trials.

---

## Sensitivity Analysis

Determine which parameters have the largest impact on a metric:

```python
from radiant.api import Sensor

sensor = Sensor.from_yaml("examples/mwir_leo_minimal.yaml")
sa = sensor.sensitivity(
    metric="snr",
    param_names=[
        "optics.aperture_diameter_m",
        "optics.focal_length_m",
        "optics.transmission_scalar",
        "detector.qe_value",
        "spectral_integration.integration_time_s",
    ],
)
for e in sa.entries:          # sorted by |sensitivity|, descending
    print(f"{e.param_name}: {e.sensitivity:+.3f} "
          f"(nominal {e.nominal_value:g}, metric {e.metric_nominal:.4g})")

sa.param_names       # dot-paths in ranked order
sa.sensitivities     # the ranked sensitivity values
sa.to_dict()         # {dot-path: sensitivity}
```

Each `SensitivityEntry` carries `param_name`, `nominal_value`, `metric_nominal`,
`metric_plus`, `metric_minus`, `sensitivity`, and `delta_fraction`. The sensitivity is
normalized and therefore dimensionless:

$$S = \frac{\Delta M / M}{\Delta p / p}$$

so an $S$ of $+2.0$ means a 1% increase in the parameter raises the metric by about 2%.
With `param_names=None` the analysis perturbs the toleranced parameters if any are set,
otherwise every float parameter. `delta_fraction=0.01` is a $\pm 1\%$ perturbation.

---

## Progress Reporting and Cancellation

`sweep`, `sweep_2d`, `monte_carlo`, `sensitivity`, and `BatchRunner.run` all accept the
same two callbacks:

- `progress(done, total)` is called after each completed unit of work — a sweep point, a
  grid cell, an MC trial, a perturbed parameter.
- `cancel() -> bool` is polled *before* each unit; returning `True` aborts with
  `OperationCancelledError`.

```python
from radiant.api import OperationCancelledError, Sensor
import numpy as np

stop = False
sensor = Sensor.from_yaml("examples/mwir_leo_minimal.yaml")

try:
    result = sensor.sweep(
        "optics.aperture_diameter_m",
        np.linspace(0.10, 0.60, 51),
        progress=lambda done, total: print(f"{done}/{total} points"),
        cancel=lambda: stop,
    )
except OperationCancelledError as exc:
    print(f"{exc.operation} stopped after {exc.done}/{exc.total} evaluations")
```

Both callbacks run on the calling thread — a GUI typically flips a flag from its event
loop and reads progress into a bar. An exception raised inside `progress` is **not**
swallowed: a broken callback fails the operation loudly. A cancelled operation returns no
partial result; sweep in chunks if partials are needed.

---

## Batch Matrices

`BatchRunner` evaluates the cartesian product of labeled axes — N targets × M atmospheres
× K sensors — and returns a tidy table. The runner owns the mechanics (product, per-cell
overrides, per-cell failure capture); the caller supplies the physics in a callback.

```python
from radiant.api.batch import BatchRunner

base = {
    "source": {"target": {"temperature": 300.0, "emissivity": 0.95}},
    "geometry": {"sensor_altitude_m": 8000.0},
    "optics": {"aperture_diameter_m": 0.30, "focal_length_m": 1.20,
               "transmission_scalar": 0.70},
    "detector": {"pixel_pitch_x_um": 18.0, "pixel_pitch_y_um": 18.0,
                 "qe_value": 0.70, "dark_rate_e_per_s": 100.0},
    "spectral_integration": {"filter_min_um": 3.5, "filter_max_um": 5.0,
                             "integration_time_s": 0.005},
    "readout": {"read_noise_e_rms": 5.0, "gain_e_per_dn": 1.0, "adc_bits": 16},
}

axes = [
    ("target", {
        "tank":  {"source.target.temperature": 310.0},   # K
        "truck": {"source.target.temperature": 305.0},   # K
    }),
    ("altitude", {
        "low":  {"geometry.sensor_altitude_m": 5000.0},   # m
        "high": {"geometry.sensor_altitude_m": 12000.0},  # m
    }),
]

batch = BatchRunner(base, axes).run(
    lambda sensor, labels: {"snr": sensor.evaluate().metrics["snr"]}
)

batch.rows        # one dict per cell: axis labels + outputs + 'error'
batch.n_failed    # cells whose evaluation raised a RadiantError
batch.pivot("snr", rows="target", cols="altitude")
```

The last axis varies fastest, and axis names become result columns — so `"error"` is
reserved. A cell whose evaluation raises a `RadiantError` becomes a row with a populated
`error` column: recorded data, never a silent drop. Any *other* exception is a
programming bug and propagates. Failed cells appear as `None` in a pivot.

---

## Using the Data Library

The `SpectralLibrary` provides bundled material emissivity, detector QE, and
solar irradiance data:

```python
from radiant.data import SpectralLibrary

lib = SpectralLibrary()
materials = lib.materials()       # list of 19 material names
emiss = lib.material("aluminum")  # SpectralData object

detectors = lib.detectors()           # list of 6 detector names
qe = lib.detector_qe("silicon")      # SpectralData object

solar = lib.solar()               # AM0 solar irradiance
```

Each returns a `SpectralData` object with `.wavelength_um` and `.values`
arrays, plus `.unit`, `.source`, and `.name` metadata.

---

## Cloning for Comparison

```python
from radiant.api import Sensor

baseline = Sensor.from_yaml("examples/mwir_leo_minimal.yaml")
upgraded = baseline.clone()
upgraded.set("optics.aperture_diameter_m", 0.50)

r_base = baseline.evaluate()
r_upgrade = upgraded.evaluate()
delta_snr = r_upgrade.metrics["snr"] - r_base.metrics["snr"]
```

---

## Configuration Sets

Cloning gives you two independent sensors. A `ConfigurationSet` instead keeps
**one** document with up to twelve named *configurations* of the same problem: a
parameter is **shared** by default and carries one value per configuration only
once you `configure()` it. Shared edits move every configuration at once, and
the whole study saves as a single config file.

```python
from radiant.api import ConfigurationSet, Sensor

base = Sensor.from_yaml("examples/mwir_leo_minimal.yaml")
cs = ConfigurationSet(base, names=["MWIR", "LWIR"])

# Configured: one value per configuration, in names() order, in input units.
cs.configure("spectral_integration.filter_min_um", [3.5, 8.0])            # um
cs.configure("spectral_integration.filter_max_um", [5.0, 12.0])           # um
cs.configure("spectral_integration.integration_time_s", [0.005, 0.0005])  # s
cs.configure("readout.full_well_capacity_e", [2.0e6, 6.0e6])              # e-
cs.configure("detector.qe_value", [0.70, 0.55])                           # dimensionless
cs.set_value("detector.qe_value", "LWIR", 0.62)                           # one configuration
cs.base.set("optics.aperture_diameter_m", 0.35)      # m — shared: moves both
cs.baseline = "MWIR"                                 # delta reference

cs.names()              # ('MWIR', 'LWIR') — set order
cs.configured()         # dot-path -> one value per configuration
cs.validate_all()       # {name: None or error} — resolve-only, no physics
lwir = cs.sensor_for("LWIR")       # materialize one configuration as a Sensor

run = cs.evaluate_all()            # every configuration, active first
run.result_for("LWIR").metrics["snr"]     # dimensionless
run.warnings                       # {name: messages} — attributed per configuration
print(run.summary())               # one triage line per configuration, with units
print(cs.compare(run).to_table())  # metric x configuration, deltas vs the baseline

yaml_text = cs.to_yaml()           # the whole study as one document
```

`cs.save(path)` writes that document and `ConfigurationSet.load(path)` reads it
back --- names and order, `active` / `baseline`, per-configuration
`wavelength_points`, and the configured table all round-trip. A plain config
file loads as the degenerate one-configuration set; a study file loaded through
`Sensor.from_yaml` raises an error pointing at `ConfigurationSet.load`.

The repository's scripting-API specification carries the full member list, and
`examples/scripts/dual_band_configuration_set.py` is the worked study.

---

## Exporting Results

### CLI export

```bash
radiant run examples/mwir_leo_minimal.yaml --format json --output result.json
radiant run examples/mwir_leo_minimal.yaml --format csv --output result.csv
```

### Python — extract to dict

```python
from radiant.api import Sensor

sensor = Sensor.from_yaml("examples/mwir_leo_minimal.yaml")
result = sensor.evaluate()
metrics_dict = dict(result.metrics)
# Write to CSV/JSON with standard Python libraries
```

---

## See Also

Example scripts in `examples/scripts/`:

- `basic_evaluation.py` --- load, evaluate, inspect
- `aperture_sweep.py` --- 1D sweep with plotting
- `tolerance_analysis.py` --- Monte Carlo workflow
- `compare_configs.py` --- side-by-side comparison of two `Sensor` objects
- `custom_loop.py` --- advanced iteration patterns
- `dual_band_configuration_set.py` --- a `ConfigurationSet` study (MWIR vs LWIR
  on one telescope), worked end to end: see **Configuration Sets** above

Plot functions are available in `radiant.api.plot` for sweep results,
noise budgets, PSF images, MTF curves, and spectral data visualization.
