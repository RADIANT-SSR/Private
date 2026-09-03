# Scripting Guide

*Persona: Sarah (systems engineer), Tom (optical designer), Dr. Chen (researcher)*

Using the Python API for programmatic sensor modeling, sweeps, and analysis.

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
# Typical: ['at_target', 'at_aperture', 'post_optics', 'photoelectrons']
```

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
# sa.entries — list of SensitivityEntry sorted by |sensitivity|
# Each entry: .param_name, .sensitivity, .baseline, .perturbed
```

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

The full member list is in `docs/architecture/RADIANT_Scripting_API.md` §2.5c,
and `examples/scripts/dual_band_configuration_set.py` is the worked study.

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
