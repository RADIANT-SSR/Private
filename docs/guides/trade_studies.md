# Trade Studies Guide

*Persona: Sarah (systems engineer), Tom (optical designer)*

Workflows for parametric sweeps, tolerance analysis, sensitivity studies,
and configuration comparison.

---

## 1D Parameter Sweep

**Question**: "How does SNR vary with aperture diameter?"

### CLI

```bash
radiant sweep examples/mwir_leo_minimal.yaml optics.aperture_diameter_m \
    --min 0.10 --max 0.60 --steps 11 --metric snr
```

### Python

```python
from radiant.api import Sensor
import numpy as np

sensor = Sensor.from_yaml("examples/mwir_leo_minimal.yaml")
result = sensor.sweep(
    "optics.aperture_diameter_m",
    np.linspace(0.10, 0.60, 11),
    metric="snr",
)
# result.values — array of swept values
# result.metric_values — corresponding metric values
```

---

## 2D Parameter Sweep

**Question**: "How do aperture and integration time jointly affect SNR?"

```python
from radiant.api import Sensor
import numpy as np

sensor = Sensor.from_yaml("examples/mwir_leo_minimal.yaml")
result = sensor.sweep_2d(
    "optics.aperture_diameter_m", np.linspace(0.15, 0.50, 8),
    "spectral_integration.integration_time_s", np.array([0.001, 0.003, 0.005, 0.010]),
    metric="snr",
)
# result.grid — 2D array, shape (8, 4)
# result.values1, result.values2 — axis arrays
```

---

## Monte Carlo Tolerance Analysis

**Question**: "Given manufacturing tolerances, what is my SNR distribution?"

### CLI

```bash
radiant tolerance examples/mwir_leo_minimal.yaml \
    --tolerance "optics.transmission_scalar gaussian mean=0.70 std=0.03" \
    --tolerance "detector.qe_value gaussian mean=0.70 std=0.05" \
    --trials 500 --seed 42
```

### Python

```python
from radiant.api import Sensor

sensor = Sensor.from_yaml("examples/mwir_leo_minimal.yaml")
sensor.set_tolerance("optics.transmission_scalar", "gaussian", mean=0.70, std=0.03)
sensor.set_tolerance("detector.qe_value", "gaussian", mean=0.70, std=0.05)

mc = sensor.monte_carlo(n_trials=500, seed=42)
# mc.mean("snr"), mc.std("snr") — summary statistics
# mc.metric_names — tuple of available metric names
```

---

## Sensitivity Analysis

**Question**: "Which parameter has the largest impact on SNR?"

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

for entry in sa.entries[:5]:  # top 5 most sensitive
    pass
    # entry.param_name — parameter dot-path
    # entry.sensitivity — normalized sensitivity (dSNR/dp * p/SNR)
    # entry.baseline — metric at nominal
    # entry.perturbed — metric at +1% perturbation
```

The sensitivity is normalized: a value of 2.0 means a 1% change in the
parameter produces a 2% change in the metric. Negative sensitivity means
increasing the parameter decreases the metric.

---

## Comparing Two Config Files

**Question**: "How does my baseline differ from the upgraded design?"

### CLI

```bash
radiant compare examples/templates/mwir_leo_pushbroom.yaml \
                examples/templates/mwir_aerial_flir.yaml
```

### Python

```python
from radiant.api import Sensor

baseline = Sensor.from_yaml("examples/templates/mwir_leo_pushbroom.yaml")
upgraded = baseline.clone()
upgraded.set("optics.aperture_diameter_m", 0.50)
upgraded.set("detector.qe_value", 0.80)

r1 = baseline.evaluate()
r2 = upgraded.evaluate()

delta_snr = r2.metrics["snr"] - r1.metrics["snr"]
delta_mtf = r2.metrics["mtf_at_nyquist"] - r1.metrics["mtf_at_nyquist"]
```

---

## Multi-Configuration Study --- N Named Designs in One Document

**Question**: "I have one telescope operated three ways --- how do the numbers
line up side by side, and how do I keep the shared parts shared?"

A **configuration set** is one modeling problem carrying up to eight named
**configurations** of itself. Every parameter is **shared** (one value for all
configurations) until you explicitly `configure()` it, at which point it carries
one value per configuration --- densely, never sparsely. Editing a shared
parameter moves every configuration at once, which is exactly what you want when
the aperture, the scene, and the atmosphere are common to all the candidates and
only the band, the integration time, and the FPA settings differ.

### Building the study

```python
from radiant.api import ConfigurationSet, Sensor

# The shared base: one 0.30 m f/4 telescope at 8000 m altitude viewing a
# 300 K, emissivity-0.95 extended scene through a mid-latitude-summer atmosphere.
base = Sensor.from_yaml("examples/mwir_leo_minimal.yaml")
study = ConfigurationSet(base, names=["MWIR", "LWIR"])

# Configure only what differs — one value per configuration, in names() order.
study.configure("spectral_integration.filter_min_um", [3.5, 8.0])            # um
study.configure("spectral_integration.filter_max_um", [5.0, 12.0])           # um
study.configure("spectral_integration.integration_time_s", [0.005, 0.0005])  # s
study.configure("detector.qe_value", [0.70, 0.55])                           # dimensionless
study.configure("readout.full_well_capacity_e", [2.0e6, 6.0e6])              # e-
study.configure("readout.gain_e_per_dn", [32.0, 92.0])                       # e-/DN

study.set_wavelength_points("LWIR", 300)  # spectral points; MWIR keeps the shared default
study.baseline = "MWIR"   # deltas in compare() are measured against this
study.active = "MWIR"     # evaluated first
```

Later edits come in three flavors, and the distinction is the whole point of the
model:

```python
study.set_value("readout.gain_e_per_dn", "LWIR", 90.0)  # e-/DN — one configuration
study.set_values("detector.qe_value", [0.72, 0.55])     # the whole column at once
study.base.set("optics.aperture_diameter_m", 0.35)      # m — SHARED: moves both
```

`configure()` *moves* a parameter out of the shared base; `unconfigure()`
collapses it back to one shared value. A dot-path is never in both places, so
there is no question of which value won.

### Evaluating and comparing

```python
run = study.evaluate_all()      # every configuration in one pass, active first
print(run.summary())            # one triage line per configuration, metrics with units

run.n_failed                    # a configuration that errors is recorded, not raised
run.warnings                    # {name: messages} — only configurations that warned
run.result_for("LWIR").metrics["snr"]          # dimensionless
run.result_for("LWIR").metrics["nedt_K"]       # K

comparison = study.compare(run)     # metric x configuration matrix
print(comparison.to_table())        # aligned values, * marks best per metric
row = comparison.row("snr")
row.values      # SNR per configuration, in set order (dimensionless)
row.deltas      # each configuration minus the baseline configuration
row.unit        # the unit string the metric registry declares
```

Two behaviors worth knowing before you read the table:

- **Warnings are attributed.** Each configuration evaluates inside its own
  warning-capture window, so a saturation warning raised by one band lands on
  that configuration and nowhere else. Check `run.warnings` before trusting a
  winner --- a clipped signal can still collect the best raw SNR.
- **`compare()` refuses a partial matrix.** If any configuration failed, it
  raises rather than silently comparing the survivors, so a column always
  corresponds to the configuration you think it does. Use `run.summary()` to
  triage a partially-failed pass, or build a comparison over the subset you
  choose with `compare_configs` from `radiant.api`.

Persist the whole study as **one** config file with
`study.save("dual_band_study.yaml")` and reload it with
`ConfigurationSet.load(path)`: the names and their order, the `active` and
`baseline` designations, the per-configuration spectral grid density, and the
configured table all survive the round trip. `study.to_yaml()` returns the same
document as a string without touching disk.

### When to reach for a configuration set, and when to sweep

| Use | For |
|-----|-----|
| **Configuration set** | A handful of **named, discrete designs** --- MWIR vs. LWIR, nominal vs. as-built, three candidate geometries. Several parameters differ at once per design, each design gets a name you recognize in the output, and the whole study saves as one file. Up to 8. |
| **Sweep** (`sweep`, `sweep_2d`) | A **continuous axis** --- SNR vs. aperture from 0.10 m to 0.60 m in 20 steps. One parameter (or two) varies, the answer is a curve or a surface, and no individual point deserves a name. |

If you find yourself naming sweep points, you want a configuration set; if you
find yourself adding a ninth configuration to trace out a trend, you want a
sweep.

### From the CLI and the GUI

```bash
radiant run study.yaml --configuration LWIR   # one named configuration
radiant validate study.yaml                   # resolve-only check of EVERY configuration
```

The `--configuration` flag is required for a study file (the `active`
designation is GUI display state, never a batch default) and rejected for a
plain one. There is no whole-set CLI batch --- `evaluate_all()` is the API for
that.

In the GUI, a study opens with a configuration tab strip above the signal-chain
strip; **Edit -> Configurations...** adds, duplicates, renames, reorders, and
designates the baseline; parameter rows carry a "C" badge when they are
configured; and the Performance stage shows one column per configuration.

The file format is in the [Configuration Guide](configuration.md); the full API
contract is `docs/architecture/RADIANT_Scripting_API.md` §2.5c; the end-to-end
worked study --- three configurations, warning attribution, physics discussion,
and the save/load round trip --- is
`examples/scripts/dual_band_configuration_set.py`.

---

## Interpreting Results

### SNR vs. Aperture

SNR generally increases with aperture because more photons are collected.
At some point, background noise or detector noise dominates and the curve
flattens. Look for the "knee" --- the aperture where additional size gives
diminishing returns.

### Noise Budget

After evaluation, inspect which noise sources dominate:

```python
from radiant.api import Sensor

sensor = Sensor.from_yaml("examples/mwir_leo_minimal.yaml")
result = sensor.evaluate()

dominant = sorted(result.noise_terms, key=lambda nt: nt.value_e, reverse=True)
for nt in dominant[:5]:
    pass  # nt.name, nt.value_e
```

Common dominant sources:
- **Signal shot noise**: fundamental limit (BLIP regime)
- **Background shot noise**: scene thermal background
- **Nearfield shot noise**: warm optics thermal emission
- **Read noise**: electronics noise floor
- **Dark current shot noise**: detector leakage

### MTF Terms

The system MTF is the product of individual MTF components. Low system MTF
means degraded image sharpness. Check `mtf_at_nyquist` --- values below
~0.1 indicate severe resolution loss.

---

## Worked Example: "What Aperture Do I Need for SNR >= 50?"

Starting from the MWIR LEO pushbroom template:

```python
from radiant.api import Sensor
import numpy as np

sensor = Sensor.from_yaml("examples/templates/mwir_leo_pushbroom.yaml")

# Sweep aperture from 0.05 m to 0.60 m
sweep = sensor.sweep(
    "optics.aperture_diameter_m",
    np.linspace(0.05, 0.60, 20),
    metric="snr",
)

# Find the smallest aperture that gives SNR >= 50
threshold = 50.0
for aperture, snr in zip(sweep.values, sweep.metric_values):
    if snr >= threshold:
        break
# aperture is now the minimum diameter for SNR >= 50
```

For a more rigorous answer, also check that the MTF at Nyquist remains
acceptable at the chosen aperture:

```python
from radiant.api import Sensor
import numpy as np

sensor = Sensor.from_yaml("examples/templates/mwir_leo_pushbroom.yaml")
sweep_mtf = sensor.sweep(
    "optics.aperture_diameter_m",
    np.linspace(0.05, 0.60, 20),
    metric="mtf_at_nyquist",
)
# Compare sweep_mtf.metric_values against your MTF requirement
```

---

## See Also

- [Quickstart](quickstart.md) --- first evaluation and sweep
- [Scripting Guide](scripting.md) --- full Python API reference
- [Regime Selection](regime_selection.md) --- how target size affects SNR
- [Configuration Guide](configuration.md) --- the `configurations:` file format
- Example scripts: `examples/scripts/aperture_sweep.py`,
  `examples/scripts/tolerance_analysis.py`,
  `examples/scripts/dual_band_configuration_set.py`
