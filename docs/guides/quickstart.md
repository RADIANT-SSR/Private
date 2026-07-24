# Quickstart

*Persona: Sarah (systems engineer), Raj (mission planner)*

Get from zero to a working sensor evaluation in under 5 minutes.

---

## Installation

Requires **Python 3.11 or 3.12**.

```bash
git clone https://github.com/RADIANT-SSR/Private.git SSR_Tool && cd SSR_Tool
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\Activate.ps1
pip install -e ".[dev]"
```

Verify the install:

```bash
radiant --version
```

For prerequisites, optional extras, and troubleshooting, see the
[project README](../../README.md) and the [developer guide](../../DEVELOPMENT.md).

---

## Your First Evaluation

RADIANT ships a reference MWIR config at `examples/mwir_leo_minimal.yaml` ---
a 300 K target viewed from 8 km altitude through a 0.30 m aperture.

### CLI

```bash
radiant run examples/mwir_leo_minimal.yaml
```

Output includes SNR, contrast SNR, MTF at Nyquist, RER, and encircled energy.

Override a parameter on the fly:

```bash
radiant run examples/mwir_leo_minimal.yaml --set optics.aperture_diameter_m=0.50
```

### Python

```python
from radiant.api import Sensor

sensor = Sensor.from_yaml("examples/mwir_leo_minimal.yaml")
result = sensor.evaluate()

snr = result.metrics["snr"]
mtf_nyq = result.metrics["mtf_at_nyquist"]
```

---

## Your First Sweep

Sweep aperture diameter from 0.10 m to 0.60 m and see how SNR responds.

### CLI

```bash
radiant sweep examples/mwir_leo_minimal.yaml optics.aperture_diameter_m \
    --min 0.10 --max 0.60 --steps 6 --metric snr
```

### Python

```python
from radiant.api import Sensor
import numpy as np

sensor = Sensor.from_yaml("examples/mwir_leo_minimal.yaml")
result = sensor.sweep(
    "optics.aperture_diameter_m",
    np.linspace(0.10, 0.60, 6),
    metric="snr",
)
for val, snr in zip(result.values, result.metric_values):
    pass  # val is aperture, snr is the corresponding SNR
```

---

## Exploring Results

### Inspect a parameter's provenance

```bash
radiant explain examples/mwir_leo_minimal.yaml optics.f_number
```

### Python equivalent

```python
from radiant.api import Sensor

sensor = Sensor.from_yaml("examples/mwir_leo_minimal.yaml")
explanation = sensor.explain("optics.f_number")
```

The `f_number` is derived from `focal_length_m / aperture_diameter_m` via a
consistency group --- `explain` shows this derivation chain.

### Available metrics

After `sensor.evaluate()`, `result.metrics` is a dict with keys including:

| Key              | Description                        |
|------------------|------------------------------------|
| `snr`            | Signal-to-noise ratio              |
| `contrast_snr`   | Target-minus-background SNR       |
| `mtf_at_nyquist` | System MTF at Nyquist frequency   |
| `rer`            | Relative Edge Response             |
| `ee_1x1`         | Ensquared energy in 1x1 pixel     |
| `ee_3x3`         | Ensquared energy in 3x3 pixels    |
| `fwhm_x_m`       | PSF FWHM in x (meters)           |
| `fwhm_y_m`       | PSF FWHM in y (meters)           |
| `well_margin_dB`  | Margin to full-well capacity     |
| `adc_margin_dB`   | Margin to ADC saturation         |
| `dynamic_range_dB` | Dynamic range in dB             |

---

## Validate a Configuration

Check that a YAML file has all required parameters and passes physics checks:

```bash
radiant validate examples/mwir_leo_minimal.yaml
```

---

## Next Steps

- [Configuration Guide](configuration.md) --- YAML structure, defaults, overrides
- [Scripting Guide](scripting.md) --- Python API for sweeps, Monte Carlo, sensitivity
- [Trade Studies](trade_studies.md) --- worked examples of common trade study workflows
- [Parameter Reference](parameter_reference.md) --- all 91 parameters with types and defaults
- [Regime Selection](regime_selection.md) --- extended-scene vs. sub-pixel vs. point-source
