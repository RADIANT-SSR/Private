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

## Comparing Configurations

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
- Example scripts: `examples/scripts/aperture_sweep.py`,
  `examples/scripts/tolerance_analysis.py`
