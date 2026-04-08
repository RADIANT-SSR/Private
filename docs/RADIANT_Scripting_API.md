# RADIANT Scripting API

**Date:** 2026-04-07
**Status:** Accepted
**Depends on:** RADIANT_Signal_Chain_Architecture.md, RADIANT_Parameter_System.md, RADIANT_Config_Format.md
**Scope:** Defines the Python scripting API. This is the primary user-facing interface for trade studies, sweeps, Monte Carlo analysis, and interactive exploration. MATLAB-like simplicity is the design goal.

---

## 1. Design Philosophy

The API exposes **one primary class**: `Sensor`. Everything a user needs for trade studies lives on this object. Complexity is in the implementation, not the interface.

**Goals:**
- Load a config, set a parameter, evaluate: 3 lines of code.
- Sweep any parameter: 1 more line.
- Monte Carlo: 1 more line.
- Tab-complete in IPython/Jupyter: every parameter and method autocompletes.
- Every intermediate result is accessible without digging into internals.

**Non-goals:**
- Configuring stages directly (that's for plugin authors; use `radiant.core`)
- Building custom signal chains (likewise)
- Bypassing validation

The `Sensor` class wraps `RadiantSession` (the internal session object). Users import from `radiant` directly.

```python
from radiant import Sensor
```

---

## 2. `Sensor` Class

### 2.1 Construction

```python
from radiant import Sensor

# From config files (most common)
s = Sensor.load("configs/leo_mwir_clear.yaml")

# From separate sensor + scenario files
s = Sensor.load(
    sensor="sensors/baseline_mwir.yaml",
    scenario="scenarios/leo_mwir_clear.yaml",
)

# From Python dict
s = Sensor.from_dict({"sensor": {"optics": {"aperture_diameter": 0.30}}, ...})

# From fluent builders (see Config Format doc)
from radiant.api import SensorConfig, ScenarioConfig
s = Sensor.from_configs(sensor_cfg, scenario_cfg)

# Fresh (empty) sensor — set everything programmatically
s = Sensor()
```

### 2.2 Core Methods

| Method | Description |
|--------|-------------|
| `s.load(path)` | Load config file(s). Returns `self` for chaining. |
| `s.set(param, value)` | Set a parameter by dot-path. Triggers immediate re-resolution. |
| `s.get(param)` | Get a resolved parameter value (in input units). |
| `s.evaluate()` | Run the full signal chain. Returns `ChainResult`. |
| `s.validate()` | Validate configuration without evaluating. Returns list of errors/warnings. |
| `s.explain(param)` | Print provenance and derivation chain for a parameter. |
| `s.schema()` | Return all parameter definitions (ParameterDef objects). |
| `s.params()` | Return all resolved parameters as a dict. |
| `s.copy()` | Deep copy. Useful before sweeps so the original is unchanged. |
| `s.save(path)` | Serialize current parameter state to YAML. |

### 2.3 Sweep

```python
result_list = s.sweep(param, values, metric="snr")
```

- `param`: dot-path string, e.g., `"sensor.optics.aperture_diameter"`
- `values`: list or numpy array of values to sweep
- `metric`: string key of the output metric, or a callable `f(result) -> float`
- Returns: `SweepResult` (described in §6)

```python
result_2d = s.sweep_2d(param1, values1, param2, values2, metric="snr")
```

Returns: `Sweep2DResult` — a 2D array of metric values indexed by `(param1, param2)`.

### 2.4 Monte Carlo

```python
mc_result = s.monte_carlo(n_trials=1000, seed=42)
```

Requires at least one `Tolerance` specification (set via `s.set_tolerance(param, dist, **kwargs)`). Each trial samples all toleranced parameters from their distributions, re-evaluates the chain, and records all metrics. Returns `MonteCarloResult`.

### 2.5 Sensitivity Analysis

```python
sens = s.sensitivity(metric="snr", params=None, delta_fraction=0.01)
```

Perturbs each toleranced (or all) parameter by `±delta_fraction × value`, evaluates the chain, and returns `dmetric/dparam` for each. Cheaper than Monte Carlo for identifying dominant parameters.

---

## 3. `ChainResult`

The object returned by `s.evaluate()`.

### 3.1 Signal at Any Frame

```python
result = s.evaluate()

result.signal_at("electrons")          # float: 12,450 e-
result.signal_at("dn")                 # float: 124.5 DN
result.signal_at("at_aperture")        # SpectralArray: L(λ) at entrance pupil [W/m²/sr/µm]
result.signal_at("at_target")          # SpectralArray: source radiance
result.signal_at("post_optics")        # SpectralArray: after optical throughput

result.background_at("electrons")      # background signal component
result.target_at("electrons")          # target signal component (sub-pixel regime)
```

### 3.2 Noise Budget

```python
result.noise_at("electrons")           # float: total noise 263 e- RMS
result.noise_at("dn")                  # float: noise in DN
result.noise_at("electrons", term="dark")   # float: dark noise alone 89.2 e-

budget = result.noise_budget()          # NoiseBudget object
budget.table()                          # prints formatted table
budget.to_dataframe()                   # pandas DataFrame
budget.to_dict()                        # dict: {term: {value_e, fraction, origin_frame}}
```

**Noise budget table format:**

```
Noise Budget — Signal: 12,450 e-  Total Noise: 263 e- RMS  SNR: 47.3
─────────────────────────────────────────────────────────────────────
Term                  σ (e-)   σ (DN)   % Total   Physical basis
─────────────────────────────────────────────────────────────────────
photon_shot           111.6    1.12     18.0%      Poisson: √(signal)
dark_current_shot      89.2    0.89     11.5%      Poisson: √(J·t_int)
read_noise             25.0    0.25      0.9%      Spec: Fowler-2 CDS
1_over_f               12.0    0.12      0.2%      1/f: f_corner model
ipc_crosstalk           8.1    0.08      0.09%     IPC: α=0.02
prnu_residual           7.3    0.07      0.08%     PRNU: 0.3% residual NUC
dsnu_residual           4.2    0.04      0.03%     DSNU: 0.1% residual
quantization            3.2    0.03      0.02%     ADC: LSB/√12
ktc                     0.0    0.00      0.00%     kTC: suppressed by CDS
─────────────────────────────────────────────────────────────────────
Total (RSS)           263.3    2.63    100.00%
```

### 3.3 MTF Budget

```python
result.mtf_at_nyquist()                 # float: system MTF at Nyquist 0.42
result.mtf_curve("system")              # SpectralArray (spatial freq, MTF)
result.mtf_curve("diffraction")         # individual term
result.mtf_curve("wfe")
result.mtf_curve("smear")
result.mtf_curve("jitter")
result.mtf_curve("pixel")
result.mtf_curve("ipc")

budget = result.mtf_budget()             # dict: {term: MTF(f) array}
```

### 3.4 Performance Metrics

```python
result.snr()                            # float
result.nedt()                           # float, in K
result.niirs()                          # float (GIQE5 or IIRS depending on band/regime)
result.detection_range()                # float, in m
result.rer()                            # float — Relative Edge Response (for GIQE)
result.gsd()                            # float, in m

# All metrics as dict:
result.metrics()
# → {"snr": 47.3, "nedt": 0.023, "niirs": 5.4, "gsd": 3.6, "rer": 0.28, ...}
```

### 3.5 Provenance

```python
result.to_provenance_record()           # dict — full audit record
result.to_json("run_result.json")       # serialize result + provenance
result.to_csv("noise_budget.csv")       # export noise budget
```

### 3.6 Intermediate Inspection

```python
result.inspect()                        # Opens variable explorer (§5.3)

# Access any stage output directly:
result.stage("source").regime           # "extended"
result.stage("optics").ee_box           # 0.82 (82% of PSF in pixel box)
result.stage("optics").strehl           # 0.87
result.stage("detector").photoelectrons # 12450.0

# All frame names:
result.frames()                         # ["at_target", "at_aperture", "post_optics", ...]
result.frame("at_aperture")             # RadiometricFrame object
result.frame("at_aperture").spectral_radiance   # np.ndarray [W/m²/sr/µm]
result.frame("at_aperture").wavelength_um       # np.ndarray [µm]
```

---

## 4. Plotting (`result.plot.*`)

Every result object has a `.plot` namespace for quick visualization. No matplotlib boilerplate required.

```python
result.plot.snr_breakdown()             # bar chart: signal vs. noise terms
result.plot.noise_budget()              # horizontal bar chart of noise budget
result.plot.mtf()                       # system MTF + all individual terms
result.plot.spectral(frame="at_aperture")  # L(λ) at specified frame
result.plot.spectral_all()              # all frames overlaid
result.plot.psf()                       # 2D PSF image
result.plot.ee_curve()                  # ensquared energy vs. box size
result.plot.transmission()              # optical + atmospheric transmission product
```

Every `SpectralArray`, `MTFArray`, and `PSF` object also has its own `.plot()` method for quick display:

```python
frame = result.frame("at_aperture")
frame.spectral_radiance.plot(title="At-aperture spectral radiance")

mtf = result.mtf_curve("system")
mtf.plot(label="System MTF", nyquist_line=True)
```

All plot methods return a `matplotlib.figure.Figure` object. Callers can modify the figure or call `.savefig()` before display.

---

## 5. Variable Explorer and Tab Completion

### 5.1 Tab Completion

Tab completion works in IPython and Jupyter without any extra configuration. The `Sensor` class exposes all parameter dot-paths via `__dir__` and a dynamic attribute proxy.

```python
s = Sensor.load("config.yaml")

# Tab-complete parameter access:
s.params.sensor.optics.aperture_diameter    # → 0.30 (float)
s.params.sensor.detector.material           # → "HgCdTe" (str)

# Tab-complete set:
s.set("sensor.optics.<TAB>")
# Shows: aperture_diameter, focal_length, f_number, obscuration_ratio, ...

# Tab-complete sweep:
s.sweep("sensor.optics.<TAB>", ...)
```

The `s.params` proxy is a read-only view. Mutations go through `s.set()`.

### 5.2 Result Tab Completion

```python
result = s.evaluate()

result.plot.<TAB>
# Shows: snr_breakdown, noise_budget, mtf, spectral, spectral_all, psf, ee_curve, transmission

result.stage("<TAB>")
# Shows: source, atmosphere, optics, platform, spectral_integration, detector, readout, performance

result.noise_at("electrons", term="<TAB>")
# Shows: photon_shot, dark_current_shot, read_noise, 1_over_f, ipc_crosstalk, ...
```

### 5.3 Variable Explorer (`result.inspect()`)

`result.inspect()` launches an interactive variable browser. In Jupyter it renders as a collapsible tree widget. In terminal it prints a formatted tree.

```
result.inspect()

ChainResult
├── metrics
│   ├── snr: 47.3
│   ├── nedt: 0.023 K
│   ├── niirs: 5.4
│   └── gsd: 3.6 m
├── frames
│   ├── at_target: L(λ) [0.54 W/m²/sr/µm peak at 4.2 µm] (500 pts)
│   ├── at_aperture: L(λ) [0.41 W/m²/sr/µm peak at 4.2 µm] (500 pts)
│   ├── post_optics: L(λ) + warm-optics term (500 pts)
│   └── photoelectrons: 12,450 e-
├── noise_budget
│   ├── photon_shot: 111.6 e- (18.0%)
│   ├── dark_current_shot: 89.2 e- (11.5%)
│   └── ... [7 more terms]
├── mtf_terms
│   ├── diffraction: MTF(f), Nyquist=0.68
│   ├── wfe: MTF(f), Nyquist=0.87
│   ├── smear: MTF(f), Nyquist=0.93
│   └── ... [5 more terms]
└── stage_outputs
    ├── source: regime=extended, target_solid_angle=1.23e-9 sr
    ├── optics: ee_box=0.82, strehl=0.87, A_collect=0.0707 m²
    └── ...
```

---

## 6. `SweepResult` and `Sweep2DResult`

### 6.1 SweepResult

```python
s = Sensor.load("config.yaml")
sweep = s.sweep("sensor.optics.aperture_diameter", np.linspace(0.10, 0.60, 21), metric="snr")

# Access results:
sweep.values          # np.ndarray of swept parameter values
sweep.metric_values   # np.ndarray of metric values
sweep.results         # list[ChainResult] — full result at each sweep point

# Quick access to any metric across sweep:
sweep["snr"]          # np.ndarray (same as sweep.metric_values if metric="snr")
sweep["nedt"]         # np.ndarray — NEDT at each sweep point
sweep["niirs"]        # np.ndarray

# Find the knee/threshold:
sweep.at_metric_threshold(40)   # (param_value, metric_value) where metric first exceeds 40

# Plot:
sweep.plot()                    # line plot: param vs. metric
sweep.plot(y=["snr", "nedt"])  # multi-axis plot

# Export:
sweep.to_dataframe()            # pandas DataFrame: columns = [param, snr, nedt, niirs, ...]
sweep.to_csv("aperture_sweep.csv")
```

### 6.2 Sweep2DResult

```python
sweep2d = s.sweep_2d(
    param1="sensor.optics.aperture_diameter",
    values1=np.linspace(0.15, 0.60, 10),
    param2="sensor.readout.integration_time",
    values2=np.array([0.002, 0.005, 0.010, 0.020]),
    metric="snr",
)

sweep2d.grid                    # 2D np.ndarray (10 × 4) of SNR values
sweep2d.plot.contour()          # filled contour plot
sweep2d.plot.heatmap()          # heatmap
sweep2d.to_dataframe()          # long-form DataFrame with param1, param2, metric columns
```

---

## 7. `MonteCarloResult`

```python
# Set tolerances:
s.set_tolerance("sensor.detector.peak_qe",     "gaussian", std_fraction=0.05)
s.set_tolerance("sensor.optics.aperture_diameter", "gaussian", std=0.005)   # ±5 mm
s.set_tolerance("sensor.detector.operating_temp",  "uniform", low=78, high=82)

mc = s.monte_carlo(n_trials=1000, seed=42)

# Statistical summaries:
mc.mean("snr")            # float
mc.std("snr")             # float
mc.percentile("snr", 5)   # 5th percentile (P5)
mc.percentile("snr", 95)  # 95th percentile (P95)
mc.probability_of_exceeding("snr", threshold=40)   # fraction of trials where SNR ≥ 40

# Distributions:
mc.plot.histogram("snr")          # histogram with mean ± 1σ marked
mc.plot.cdf("snr")                # CDF with P5/P50/P95 marked
mc.plot.scatter("snr", "nedt")    # scatter plot of two metrics

# Correlation (which sampled parameters drive SNR variation most?):
mc.plot.tornado("snr")            # tornado chart: ∂SNR/∂param at ±1σ
mc.correlation("snr")             # Pearson correlation: {param: r} dict
```

---

## 8. Sensitivity Analysis

```python
sens = s.sensitivity(metric="snr")

# Results:
sens.table()
# Parameter                          ∂SNR/∂param (norm.)   ±1σ impact   Rank
# sensor.optics.aperture_diameter    +6.2 %/1%              ±0.62        1
# sensor.readout.integration_time    +4.8 %/1%              ±0.48        2
# sensor.detector.dark_current       -1.2 %/1%              ±0.12        3
# sensor.detector.peak_qe            +1.0 %/1%              ±0.10        4

sens.plot.tornado()               # tornado chart
sens.dataframe()                  # pandas DataFrame
```

---

## 9. Usage Examples

### Example 1: Single evaluation, read out key metrics

```python
from radiant import Sensor

s = Sensor.load("configs/leo_mwir_clear.yaml")
result = s.evaluate()

print(f"SNR = {result.snr():.1f}")
print(f"NEDT = {result.nedt()*1000:.1f} mK")
print(f"NIIRS = {result.niirs():.2f}")
print(f"GSD = {result.gsd():.1f} m")
```

---

### Example 2: Override a parameter and re-evaluate

```python
s = Sensor.load("configs/leo_mwir_clear.yaml")
s.set("sensor.optics.aperture_diameter", 0.45)   # m
s.set("target.temperature", 320)                  # K

result = s.evaluate()
print(result.snr())
```

---

### Example 3: Aperture trade — sweep SNR vs. aperture diameter

```python
import numpy as np
from radiant import Sensor
import matplotlib.pyplot as plt

s = Sensor.load("configs/leo_mwir_clear.yaml")

sweep = s.sweep(
    "sensor.optics.aperture_diameter",
    np.linspace(0.10, 0.60, 26),
    metric="snr",
)

sweep.plot()
plt.axhline(40, color="red", linestyle="--", label="SNR requirement")
plt.legend()
plt.show()

print(f"Minimum aperture for SNR ≥ 40: {sweep.at_metric_threshold(40)[0]:.2f} m")
```

---

### Example 4: Multi-metric aperture sweep

```python
s = Sensor.load("configs/leo_mwir_clear.yaml")
sweep = s.sweep("sensor.optics.aperture_diameter", np.linspace(0.10, 0.60, 26))

df = sweep.to_dataframe()
df[["aperture_diameter", "snr", "nedt", "niirs"]].to_csv("aperture_trade.csv", index=False)
```

---

### Example 5: 2D sweep — SNR vs. aperture and integration time

```python
import numpy as np
from radiant import Sensor

s = Sensor.load("configs/leo_mwir_clear.yaml")

sweep2d = s.sweep_2d(
    "sensor.optics.aperture_diameter",  np.linspace(0.15, 0.50, 8),
    "sensor.readout.integration_time",  np.array([0.002, 0.005, 0.010, 0.015, 0.020]),
    metric="snr",
)

sweep2d.plot.contour(levels=[20, 30, 40, 50, 60, 80], cmap="viridis")
```

---

### Example 6: NEDT vs. operating temperature (detector engineer workflow)

```python
import numpy as np
from radiant import Sensor

s = Sensor.load("configs/leo_mwir_clear.yaml")

temps = np.arange(70, 100, 2)   # 70 K to 98 K
sweep = s.sweep("sensor.detector.operating_temp", temps, metric="nedt")

sweep.plot()
# Rule 07 dark current kicks in above ~80 K for 5 µm cutoff HgCdTe;
# NEDT should show a knee at that temperature.
```

---

### Example 7: Full noise budget breakdown

```python
s = Sensor.load("configs/leo_mwir_clear.yaml")
result = s.evaluate()

result.noise_budget().table()                     # print to console
df = result.noise_budget().to_dataframe()
df.to_csv("noise_budget.csv", index=False)
result.plot.noise_budget()                        # bar chart
```

---

### Example 8: Access spectral data at every stage

```python
s = Sensor.load("configs/leo_mwir_clear.yaml")
result = s.evaluate()

import matplotlib.pyplot as plt

wl = result.frame("at_target").wavelength_um
fig, ax = plt.subplots()
for frame_name in ["at_target", "at_aperture", "post_optics"]:
    frame = result.frame(frame_name)
    ax.plot(wl, frame.spectral_radiance, label=frame_name)
ax.set_xlabel("Wavelength (µm)")
ax.set_ylabel("Spectral Radiance (W/m²/sr/µm)")
ax.legend()
plt.show()
```

---

### Example 9: MTF budget — system MTF with all components

```python
s = Sensor.load("configs/leo_mwir_clear.yaml")
result = s.evaluate()

result.plot.mtf()    # system + all individual terms on one plot

print(f"MTF at Nyquist: {result.mtf_at_nyquist():.3f}")
print(f"RER: {result.rer():.3f}")
```

---

### Example 10: Monte Carlo tolerance analysis

```python
import numpy as np
from radiant import Sensor

s = Sensor.load("configs/leo_mwir_clear.yaml")

# Define tolerances (all in input units):
s.set_tolerance("sensor.detector.peak_qe",        "gaussian", std_fraction=0.05)
s.set_tolerance("sensor.detector.dark_current",    "log_normal", sigma=0.20)
s.set_tolerance("sensor.optics.aperture_diameter", "gaussian", std=0.003)   # ±3 mm
s.set_tolerance("sensor.optics.wfe_rms",           "truncated_gaussian", std=0.02, low=0.0, high=0.15)
s.set_tolerance("sensor.detector.operating_temp",  "uniform", low=78, high=82)

mc = s.monte_carlo(n_trials=2000, seed=0)

print(f"SNR: {mc.mean('snr'):.1f} ± {mc.std('snr'):.1f}")
print(f"P5/P95: {mc.percentile('snr', 5):.1f} / {mc.percentile('snr', 95):.1f}")
print(f"P(SNR ≥ 40): {mc.probability_of_exceeding('snr', 40):.1%}")

mc.plot.histogram("snr")
mc.plot.tornado("snr")    # shows which tolerances dominate SNR spread
```

---

### Example 11: Sensitivity analysis — identify top 5 parameters driving SNR

```python
from radiant import Sensor

s = Sensor.load("configs/leo_mwir_clear.yaml")

# Tolerance on all parameters for sensitivity (perturbation ±1%):
sens = s.sensitivity(metric="snr", delta_fraction=0.01)
sens.table()                          # ranked by impact
sens.plot.tornado()
```

---

### Example 12: Parameter explanation and provenance

```python
s = Sensor.load("configs/leo_mwir_clear.yaml")
s.set("sensor.optics.focal_length", 1.50)   # override focal length

s.explain("sensor.optics.f_number")
# → sensor.optics.f_number = 5.0 (dimensionless)
#   Provenance: DERIVED
#   Rule: f_number = focal_length / aperture_diameter
#   From: sensor.optics.focal_length = 1.50 m (USER_SET — cli override)
#         sensor.optics.aperture_diameter = 0.30 m (CONFIG_FILE — sensors/baseline_mwir.yaml)
```

---

### Example 13: Lab mode (blackbody, no atmosphere)

```python
from radiant import Sensor

# Simulate a lab calibration: 300 K blackbody filling the aperture, no atmosphere.
s = Sensor.load("sensors/baseline_mwir.yaml")

# Override to lab mode:
s.set("atmosphere.model", "none")           # no atmosphere (unity transmission)
s.set("target.regime", "extended")          # blackbody fills aperture
s.set("target.temperature", 300)            # K — blackbody temperature
s.set("target.emissivity", 1.0)             # ideal blackbody
s.set("geometry.observer_type", "ground")
s.set("geometry.target_type", "ground")
s.set("geometry.slant_range", 1.0)          # m — 1 m to source (effectively at aperture)

result = s.evaluate()
print(f"Predicted NEDT: {result.nedt()*1000:.1f} mK")
result.noise_budget().table()
```

---

### Example 14: Component isolation — detector-only analysis

```python
from radiant import Sensor

s = Sensor.load("sensors/baseline_mwir.yaml")

# Fix at-aperture radiance, bypass atmosphere/optics computation:
s.set("_chain.start_at", "detector")        # start chain from detector stage
s.set("_inject.photoelectrons", 12450)      # inject signal in electrons

result = s.evaluate()
result.noise_budget().table()               # noise budget for specified signal level

# Sweep integration time → NEDT curve:
import numpy as np
sweep = s.sweep("sensor.readout.integration_time",
                np.logspace(-3, -1, 20),
                metric="nedt")
sweep.plot()
```

---

### Example 15: Batch run across multiple configs

```python
from radiant import Sensor

configs = [
    ("sensors/baseline_mwir.yaml", "scenarios/midlat_clear.yaml"),
    ("sensors/baseline_mwir.yaml", "scenarios/tropical_clear.yaml"),
    ("sensors/wide_swath.yaml",    "scenarios/midlat_clear.yaml"),
    ("sensors/wide_swath.yaml",    "scenarios/tropical_clear.yaml"),
]

rows = []
for sensor_path, scenario_path in configs:
    s = Sensor.load(sensor=sensor_path, scenario=scenario_path)
    result = s.evaluate()
    rows.append({
        "sensor": sensor_path,
        "scenario": scenario_path,
        "snr": result.snr(),
        "nedt_mk": result.nedt() * 1000,
        "niirs": result.niirs(),
    })

import pandas as pd
df = pd.DataFrame(rows)
print(df.to_string(index=False))
```

---

### Example 16: BatchRunner for parallel execution

```python
from radiant.api import BatchRunner
import numpy as np

runner = BatchRunner(n_jobs=-1)   # use all CPU cores

# Cross-product sweep: 4 sensors × 10 apertures × 5 ranges = 200 evaluations
results = runner.cross_product(
    sensor=["sensors/baseline_mwir.yaml", "sensors/high_res.yaml",
            "sensors/wide_swath.yaml", "sensors/lwir.yaml"],
    overrides={
        "sensor.optics.aperture_diameter": np.linspace(0.15, 0.60, 10),
        "geometry.slant_range": np.array([300, 400, 500, 600, 700]) * 1e3,
    },
    metrics=["snr", "nedt", "niirs", "gsd"],
)

df = results.to_dataframe()
df.to_csv("batch_results.csv", index=False)
```

---

### Example 17: NIIRS vs. WFE trade (optical designer workflow)

```python
import numpy as np
from radiant import Sensor

s = Sensor.load("configs/leo_mwir_clear.yaml")

# WFE sweep — fix all other parameters, vary WFE:
sweep = s.sweep(
    "sensor.optics.wfe_rms",
    np.linspace(0.0, 0.25, 26),   # 0 to 0.25 waves RMS
    metric="niirs",
)

sweep.plot()
# Can also plot RER vs. WFE:
rer_values = [r.rer() for r in sweep.results]
import matplotlib.pyplot as plt
fig, ax = plt.subplots()
ax.plot(sweep.values, rer_values)
ax.axhline(0.25, color="red", linestyle="--", label="RER = 0.25 (GIQE knee)")
ax.set_xlabel("WFE RMS (waves)")
ax.set_ylabel("RER")
ax.legend()
plt.show()
```

---

### Example 18: PSF and ensquared energy

```python
s = Sensor.load("configs/leo_mwir_clear.yaml")
result = s.evaluate()

result.plot.psf()             # 2D Airy + WFE PSF
result.plot.ee_curve()        # ensquared energy vs. box size (in µm, pixels, µrad)

optics = result.stage("optics")
print(f"EE in 1 pixel: {optics.ee_box:.3f}")
print(f"Strehl ratio:  {optics.strehl:.3f}")
```

---

### Example 19: Reproduce a result from a provenance record

```python
from radiant import Sensor

# Load result and provenance from a prior run:
result = Sensor.load_result("run_20260407_143000_result.json")

# Reconstruct the exact Sensor object that produced this result:
s = Sensor.from_provenance_record("run_20260407_143000_result.json")

# Re-evaluate — should produce identical results:
result2 = s.evaluate()
assert abs(result2.snr() - result.snr()) < 1e-10   # bitwise reproducible
```

---

### Example 20: Validation dry-run before a batch

```python
from radiant import Sensor

configs = ["configs/scenario_A.yaml", "configs/scenario_B.yaml", "configs/scenario_C.yaml"]

for path in configs:
    s = Sensor.load(path)
    errors = s.validate()
    if errors:
        print(f"FAIL: {path}")
        for e in errors:
            print(f"  {e}")
    else:
        print(f"OK: {path}")
```

---

### Example 21: Access detection range and range sweep

```python
import numpy as np
from radiant import Sensor

s = Sensor.load("configs/point_source_tracking.yaml")

# Sweep slant range from 5 km to 50 km:
sweep = s.sweep(
    "geometry.slant_range",
    np.linspace(5000, 50000, 50),
    metric="snr",
)

# Find maximum detection range (where SNR drops below threshold):
max_range = sweep.at_metric_threshold(10, from_above=True)   # SNR drops below 10
print(f"Detection range at SNR ≥ 10: {max_range[0]/1000:.1f} km")

sweep.plot()
```

---

### Example 22: Compare two sensors at the same scenario

```python
from radiant import Sensor

scenario_overrides = {
    "geometry.observer_altitude": 600_000,
    "geometry.slant_range": 650_000,
    "atmosphere.model": "modtran",
    "atmosphere.modtran_file": "data/midlat_summer_mwir.tape7",
    "target.temperature": 300,
    "target.emissivity": 0.95,
}

sensors = {
    "baseline": Sensor.load("sensors/baseline_mwir.yaml"),
    "high_res":  Sensor.load("sensors/high_res_mwir.yaml"),
}

for name, s in sensors.items():
    for param, value in scenario_overrides.items():
        s.set(param, value)
    result = s.evaluate()
    print(f"{name:12s}  SNR={result.snr():.1f}  NEDT={result.nedt()*1000:.1f} mK  "
          f"NIIRS={result.niirs():.2f}  GSD={result.gsd():.1f} m")
```

---

## 10. Public API Summary

All public symbols are importable from `radiant` directly:

```python
from radiant import (
    Sensor,           # primary user-facing class
    SensorConfig,     # fluent sensor builder
    ScenarioConfig,   # fluent scenario builder
    BatchRunner,      # parallel batch execution
    # Result types (usually obtained from sensor.evaluate(), not constructed directly):
    ChainResult,
    SweepResult,
    Sweep2DResult,
    MonteCarloResult,
    SensitivityResult,
)
```

The `Sensor` class is the only entry point the majority of users will need. `SensorConfig` and `ScenarioConfig` are for users who build configs programmatically. `BatchRunner` is for users running large parallel studies.

---

## 11. API Stability Contract

| Symbol | Stability |
|--------|----------|
| `Sensor.*` public methods | Stable across minor versions |
| `ChainResult.*` public methods | Stable across minor versions |
| `SweepResult`, `Sweep2DResult`, `MonteCarloResult` public attributes | Stable |
| `radiant.core.*` | Semi-stable (plugin API) |
| `radiant.api.session.RadiantSession` | Stable (same class, `Sensor` is an alias) |
| Internal `_chain.*`, `stage_outputs` keys | No stability guarantee |

Breaking changes require a major version bump and a deprecation cycle of at least one minor release.
