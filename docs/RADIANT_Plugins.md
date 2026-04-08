# RADIANT Plugin and Extensibility System

**Date:** 2026-04-07
**Status:** Accepted
**Depends on:** RADIANT_Signal_Chain_Architecture.md, RADIANT_File_Tree.md
**Scope:** Defines the formal extension points for custom source models, atmosphere models, metrics, detector models, and file formats. Covers registration, discovery, namespace conflict resolution, and plugin validation.

---

## 1. Design Philosophy

### Core principle: extend, don't fork.

A user who needs a custom atmospheric model should not need to modify the RADIANT source tree, maintain a fork, or patch the package. They write a Python class, declare it in their `pyproject.toml`, and RADIANT discovers it at runtime.

### What plugins are for

| Use case | Plugin type |
|---------|------------|
| Custom thermal emission model (non-blackbody target) | `SourcePlugin` |
| Proprietary atmosphere model (replacing MODTRAN interface) | `AtmospherePlugin` |
| Organization-specific performance metric (e.g., PROBDET) | `MetricPlugin` |
| Custom detector material or readout architecture | `DetectorPlugin` |
| Custom file format (proprietary tape7 variant, HDF5 spectra) | `FileFormatPlugin` |

### What plugins are not for

- Working around architecture constraints. If a plugin needs to mutate `ChainState` from outside the defined extension points, that's a sign the architecture needs to be extended, not patched.
- Replacing core physics that is used by multiple stages. The parameter system, unit conversions, and spectral grid are not pluggable — they are invariants.

---

## 2. Plugin Types and Interfaces

All plugin ABCs are in `radiant.plugins.base`. Every plugin inherits from exactly one ABC.

### 2.1 SourcePlugin — Custom Source Radiance

Replaces or supplements the built-in `SourceStage` source computation. Use when: non-blackbody target model, hyperspectral library lookup, time-varying source, BRDF model.

```python
# radiant/plugins/base.py
from abc import ABC, abstractmethod
from radiant.core.chain import ChainState
from radiant.core.parameters import ParameterSet, ParameterDef
from radiant.core.spectral import SpectralData
import numpy as np

class SourcePlugin(ABC):
    """Custom target or background source model.

    The plugin computes a SpectralData object representing the
    at-target spectral radiance [W/m²/sr/µm] for the target or
    background, replacing or supplementing the built-in blackbody model.
    """

    name: str    # unique identifier, e.g., "hyperspectral_library"
                 # must be valid Python identifier, lowercase, underscores

    @abstractmethod
    def get_schema(self) -> list[ParameterDef]:
        """Return parameter definitions for this plugin's parameters."""
        ...

    @abstractmethod
    def compute_target(
        self,
        wavelength_um: np.ndarray,
        params: ParameterSet,
    ) -> SpectralData:
        """Compute at-target spectral radiance.

        Args:
            wavelength_um: the common wavelength grid [µm], ascending.
            params:         fully resolved parameter set.

        Returns:
            SpectralData with .values in W/m²/sr/µm on wavelength_um grid.
        """
        ...

    def compute_background(
        self,
        wavelength_um: np.ndarray,
        params: ParameterSet,
    ) -> SpectralData | None:
        """Optionally override background spectral radiance.

        Returns None to use the built-in background model.
        """
        return None
```

**Example:**

```python
# mypkg/hyperspectral_source.py
import numpy as np
from pathlib import Path
from radiant.plugins.base import SourcePlugin
from radiant.core.spectral import SpectralData
from radiant.core.parameters import ParameterDef

class HyperspectralLibrarySource(SourcePlugin):
    """Load target reflectance from a spectral library file.

    Computes at-target reflected radiance: ρ(λ) × E_solar(λ) / π
    """
    name = "hyperspectral_library"

    def get_schema(self) -> list[ParameterDef]:
        return [
            ParameterDef(
                name="source.spectral_library_file",
                description="Path to spectral reflectance file (CSV: wavelength_um, reflectance)",
                dtype=str,
                canonical_unit="",
                input_unit="",
                default=None,
                bounds=None,
                tags=frozenset({"source", "plugin"}),
            ),
            ParameterDef(
                name="source.library_target_name",
                description="Target name within spectral library",
                dtype=str,
                canonical_unit="",
                input_unit="",
                default=None,
                bounds=None,
                tags=frozenset({"source", "plugin"}),
            ),
        ]

    def compute_target(self, wavelength_um, params):
        lib_file = params.get("source.spectral_library_file")
        target_name = params.get("source.library_target_name")

        # Load reflectance from CSV (plugin's own I/O, not RADIANT's)
        data = np.loadtxt(lib_file, delimiter=",", skiprows=1)
        wl_lib, refl = data[:, 0], data[:, 1]

        # Interpolate to common grid
        refl_on_grid = np.interp(wavelength_um, wl_lib, refl, left=0.0, right=0.0)

        # Load solar irradiance from RADIANT's built-in data
        from radiant.source.solar import load_solar_irradiance
        E_solar = load_solar_irradiance(wavelength_um)    # W/m²/µm at TOA

        # Lambertian reflected radiance
        L_reflected = refl_on_grid * E_solar / np.pi     # W/m²/sr/µm

        return SpectralData(
            name="at_target",
            wavelength_um=wavelength_um,
            values=L_reflected,
            unit="W/m2/sr/um",
            source=f"hyperspectral_library:{lib_file}:{target_name}",
            source_parameters={
                "library_file": lib_file,
                "target_name": target_name,
            },
        )
```

---

### 2.2 AtmospherePlugin — Custom Atmosphere Model

Replaces the atmosphere stage's transmittance/path-radiance computation. Use when: proprietary atmospheric code, empirical lookup tables, coupled radiative transfer.

```python
class AtmospherePlugin(ABC):
    """Custom atmosphere model.

    Replaces the MODTRAN/simple/standard atmosphere interface.
    The plugin must compute all three outputs of the atmosphere stage:
    transmittance, path radiance, and atmospheric emission.
    """

    name: str

    @abstractmethod
    def get_schema(self) -> list[ParameterDef]:
        ...

    @abstractmethod
    def compute(
        self,
        wavelength_um: np.ndarray,
        params: ParameterSet,
    ) -> "AtmosphereResult":
        """Compute atmosphere outputs.

        Returns:
            AtmosphereResult with:
              .tau_atm(λ)    — spectral transmittance [0–1], dimensionless
              .L_path(λ)     — path radiance [W/m²/sr/µm]
              .L_atm(λ)      — atmospheric thermal emission [W/m²/sr/µm]
        """
        ...

    def compute_turbulence_mtf(
        self,
        spatial_freq: np.ndarray,
        params: ParameterSet,
    ) -> np.ndarray | None:
        """Optionally compute turbulence MTF. None → no turbulence term."""
        return None
```

**AtmosphereResult:**

```python
@dataclass
class AtmosphereResult:
    wavelength_um: np.ndarray
    tau_atm: np.ndarray        # spectral transmittance
    L_path: np.ndarray         # path radiance [W/m²/sr/µm]
    L_atm: np.ndarray          # atmospheric thermal emission [W/m²/sr/µm]
    source: str                # description for provenance
```

---

### 2.3 MetricPlugin — Custom Performance Metric

Adds a new metric to `PerformanceStage` output. Use when: organization-specific sensor figure of merit, detection-theoretic metrics (PROBDET, ROC), customer-defined quality thresholds.

```python
class MetricPlugin(ABC):
    """Custom performance metric.

    Computed after the full chain has run. The plugin receives the
    complete ChainState and ParameterSet and returns a named scalar value.
    """

    name: str    # dot-path metric name, e.g., "metrics.probdet"
                 # must start with "metrics."

    @abstractmethod
    def get_schema(self) -> list[ParameterDef]:
        ...

    @abstractmethod
    def compute(self, state: ChainState, params: ParameterSet) -> float:
        """Compute and return the metric value.

        The metric is stored in state.metrics[self.name] by the framework.
        """
        ...

    @property
    def unit(self) -> str:
        """Human-readable unit for display. Empty string for dimensionless."""
        return ""

    @property
    def description(self) -> str:
        """One-line description of what this metric measures."""
        return ""
```

**Example — detection probability metric:**

```python
class ProbdetMetric(MetricPlugin):
    """Detection probability from SNR via Gaussian ROC model.

    PROBDET = Φ(SNR - threshold) where Φ is the normal CDF.
    """
    name = "metrics.probdet"

    def get_schema(self):
        return [
            ParameterDef(
                name="metrics.probdet_threshold",
                description="SNR threshold for detection (false alarm rate parameter)",
                dtype=float,
                canonical_unit="",
                input_unit="",
                default=3.0,   # SNR=3 is a common threshold
                bounds=(0.1, 20.0),
                tags=frozenset({"metric", "plugin"}),
            ),
        ]

    def compute(self, state, params):
        from scipy.stats import norm
        snr = state.metrics.get("snr")
        if snr is None:
            raise RadiantError(
                what="ProbdetMetric requires 'snr' to be computed first",
                why="PerformanceStage must run before MetricPlugins",
                action="Do not run MetricPlugins before PerformanceStage",
                context={},
            )
        threshold = params.get("metrics.probdet_threshold")
        return float(norm.cdf(snr - threshold))

    @property
    def unit(self): return ""
    @property
    def description(self): return "Detection probability via Gaussian ROC model"
```

---

### 2.4 DetectorPlugin — Custom Detector Model

Replaces or augments the detector stage's QE, dark current, or noise models. Use when: custom detector material, novel readout architecture, empirically-characterized detector.

```python
class DetectorPlugin(ABC):
    """Custom detector model.

    Can override any of three computation hooks:
    - compute_qe:           QE(λ) spectral response
    - compute_dark_current: dark current [e-/s/pixel] vs. temperature
    - compute_noise_terms:  additional noise terms beyond built-in set
    """

    name: str

    @abstractmethod
    def get_schema(self) -> list[ParameterDef]:
        ...

    def compute_qe(
        self,
        wavelength_um: np.ndarray,
        params: ParameterSet,
    ) -> np.ndarray | None:
        """Return QE(λ) array on wavelength_um grid, or None to use built-in."""
        return None

    def compute_dark_current(
        self,
        params: ParameterSet,
    ) -> float | None:
        """Return dark current [e-/s/pixel] at operating_temp, or None to use built-in."""
        return None

    def compute_noise_terms(
        self,
        state: ChainState,
        params: ParameterSet,
    ) -> list["NoiseTerm"]:
        """Return additional noise terms not covered by built-in model."""
        return []
```

---

### 2.5 FileFormatPlugin — Custom File Format

Adds support for loading spectral data from a custom file format (proprietary tape7 variant, HDF5 spectra, binary format).

```python
class FileFormatPlugin(ABC):
    """Custom spectral file format reader.

    Registered for one or more file extensions. When RADIANT encounters
    a spectral file reference with a matching extension, it delegates
    loading to this plugin.
    """

    name: str
    file_extensions: tuple[str, ...]  # e.g., (".h5", ".hdf5")

    @abstractmethod
    def load(self, path: str, params: ParameterSet) -> "AtmosphereResult | SpectralData":
        """Load the file and return structured spectral data."""
        ...
```

---

## 3. Registration Mechanism

### 3.1 Entry Points in `pyproject.toml`

Plugin packages declare their plugins via `importlib.metadata` entry points. RADIANT discovers them at `RadiantSession` construction.

```toml
# In the plugin package's pyproject.toml:
[project.entry-points."radiant.plugins"]
hyperspectral_source = "mypkg.hyperspectral_source:HyperspectralLibrarySource"
probdet_metric       = "mypkg.metrics:ProbdetMetric"
custom_atmosphere    = "mypkg.atm:Proprietary7BandAtmosphere"
```

The left-hand side is the entry point name (a local identifier within the group). The right-hand side is a dotted Python path to the class. The class must be importable when RADIANT runs.

### 3.2 Manual Registration (Without `pyproject.toml`)

For development or in-process registration:

```python
from radiant.plugins import register_plugin
from mypkg.metrics import ProbdetMetric

register_plugin(ProbdetMetric())

# Or via the Sensor API:
s = Sensor.load("config.yaml")
s.register_plugin(ProbdetMetric())
```

Manual registration applies only to the current `RadiantSession` instance. It does not persist across sessions or affect other `Sensor` instances.

### 3.3 Decorator Registration (Alternative Syntax)

```python
from radiant.plugins import source_plugin, metric_plugin

@source_plugin
class HyperspectralLibrarySource(SourcePlugin):
    name = "hyperspectral_library"
    ...

@metric_plugin
class ProbdetMetric(MetricPlugin):
    name = "metrics.probdet"
    ...
```

The decorator registers the class at import time. Requires importing the module before creating a `RadiantSession`. Useful for development; entry points are preferred for distribution.

---

## 4. Discovery

### 4.1 Discovery at Session Construction

```python
# radiant/plugins/_registry.py

import importlib.metadata
from radiant.plugins.base import SourcePlugin, AtmospherePlugin, MetricPlugin, DetectorPlugin, FileFormatPlugin

_PLUGIN_REGISTRY: dict[str, object] = {}
_DISCOVERY_DONE: bool = False

def load_plugins() -> None:
    """Discover and register all installed RADIANT plugins.

    Called once at RadiantSession construction. Subsequent calls are no-ops.
    """
    global _DISCOVERY_DONE
    if _DISCOVERY_DONE:
        return

    eps = importlib.metadata.entry_points(group="radiant.plugins")
    for ep in eps:
        try:
            plugin_class = ep.load()
            instance = plugin_class()
            _register(instance)
        except Exception as e:
            # Plugin load failure: warn, don't crash RADIANT
            import warnings
            warnings.warn(
                f"RADIANT: Failed to load plugin '{ep.name}' from '{ep.value}': {e}. "
                f"This plugin will not be available.",
                stacklevel=2,
            )
    _DISCOVERY_DONE = True
```

Plugin load failures produce a `UserWarning`, not an exception. RADIANT continues with reduced capability. This allows a broken plugin package to be installed without breaking RADIANT entirely.

### 4.2 Listing Discovered Plugins

```python
from radiant.plugins import list_plugins

list_plugins()
# → {
#       "source":     ["hyperspectral_library"],
#       "atmosphere": ["proprietary_7band"],
#       "metric":     ["metrics.probdet", "metrics.mdtd_custom"],
#       "detector":   ["vo2_phase_change"],
#       "file":       [".h5", ".hdf5"]
#   }

# From the CLI:
radiant plugins list
# radiant.plugins:
#   source:     hyperspectral_library  (mypkg 1.2.0)
#   metric:     metrics.probdet        (mypkg 1.2.0)
#   atmosphere: (none)
#   detector:   (none)
#   file:       (none)
```

---

## 5. Namespace Conflicts

### 5.1 Name Collision Rules

1. **Plugin names within a type must be globally unique.** Two `SourcePlugin`s with `name = "custom_source"` from different packages raise `PluginConflictError`.
2. **Names cannot shadow built-in models.** Registering a plugin named `"modtran"` (a built-in atmosphere model name) is a `PluginConflictError`.
3. **Metric plugin names must start with `"metrics."`** to prevent collision with built-in metrics (`snr`, `nedt`, `niirs`).

```python
class PluginConflictError(RadiantError):
    """Two plugins attempt to register the same name."""
    pass
```

At discovery time, any conflict raises `PluginConflictError` immediately (not deferred). This makes plugin installation predictable: if two packages conflict, the user knows at session construction, not at evaluation time.

### 5.2 Conflict Resolution (User Override)

When a conflict is unavoidable (two versions of a plugin, or an organization wants to replace the built-in MODTRAN reader):

```python
# Explicit override: tell RADIANT to prefer a specific package's plugin
s = Sensor.load("config.yaml", plugin_priority={"atmosphere.modtran": "mypkg"})
```

This is a deliberate escape hatch, not the default behavior. The default is always `PluginConflictError`.

---

## 6. Expression-Based Custom Metrics

Users who need a simple derived metric — without writing a full `MetricPlugin` — can define one as a Python expression string referencing existing metric and parameter names.

### 6.1 Syntax

In YAML config:

```yaml
# User-defined derived metrics
custom_metrics:
  - name: metrics.snr_margin
    expression: "result.snr() / required_snr - 1.0"
    description: "SNR margin above requirement (0 = just meets)"
    vars:
      required_snr: 40.0

  - name: metrics.nedt_margin_mk
    expression: "(nedt_requirement - result.nedt()) * 1000"
    description: "NEDT margin in mK (positive = better than requirement)"
    vars:
      nedt_requirement: 0.030   # K

  - name: metrics.sensitivity_product
    expression: "result.snr() * result.niirs()"
    description: "Heuristic product of SNR and NIIRS"
```

### 6.2 Available Names in Expressions

| Name | Value |
|------|-------|
| `result.snr()` | SNR (dimensionless) |
| `result.nedt()` | NEDT (K) |
| `result.niirs()` | NIIRS |
| `result.gsd()` | GSD (m) |
| `result.mtf_at_nyquist()` | System MTF at Nyquist |
| `result.signal_at("electrons")` | Signal in electrons |
| `result.noise_at("electrons")` | Total noise in electrons |
| `params.<dot.path>` | Any resolved parameter |
| User-defined `vars` | Numeric constants from the `vars` block |
| Standard Python built-ins | `abs`, `max`, `min`, `round` |
| `math.*` | `math.log`, `math.sqrt`, etc. |

**Not allowed in expressions:** Any import, any file I/O, any function call that is not in the allowlist above. Expressions are evaluated in a restricted namespace. Security: the evaluator uses `ast.literal_eval`-compatible restriction; no `__builtins__` access.

### 6.3 Python API for Expression Metrics

```python
s = Sensor.load("config.yaml")
s.add_metric_expression(
    name="metrics.snr_margin",
    expression="result.snr() / required_snr - 1.0",
    vars={"required_snr": 40.0},
    description="SNR margin above 40 dB requirement",
)

result = s.evaluate()
print(result.metrics()["metrics.snr_margin"])   # e.g., 0.183 (18.3% above requirement)
```

---

## 7. User-Provided Spectral Libraries

Users can add spectral data files to their own library directory. RADIANT loads these at session construction and makes them available by name.

### 7.1 Library Directory

By default, RADIANT looks for user spectral libraries in:
1. `./spectra/` (relative to the config file)
2. `~/.radiant/spectra/` (user-level directory)
3. The path specified by `$RADIANT_SPECTRAL_PATH` environment variable
4. Directories declared in `pyproject.toml` under `[tool.radiant.spectral_paths]`

### 7.2 File Format Requirements

Spectral library files must be CSV with two columns:

```csv
wavelength_um,value
3.5,0.0
3.6,0.1
4.0,0.65
4.5,0.88
5.0,0.70
5.1,0.0
```

Column headers must be exactly `wavelength_um` and `value`. Units for `value` are inferred from the filename suffix:

| Suffix | Quantity | Unit |
|--------|----------|------|
| `_qe.csv` | Quantum efficiency | dimensionless (0–1) |
| `_refl.csv` | Reflectance | dimensionless (0–1) |
| `_emiss.csv` | Emissivity | dimensionless (0–1) |
| `_radiance.csv` | Spectral radiance | W/m²/sr/µm |
| `_transmission.csv` | Optical transmission | dimensionless (0–1) |

Any file not matching these suffixes requires an explicit unit declaration in a companion `.meta` file.

### 7.3 Referencing Library Files in Config

```yaml
sensor:
  detector:
    qe_file: spectra/my_detector_qe.csv   # overrides material-based QE model

target:
  emissivity_file: spectra/vegetation_emissivity_lwir.csv  # spectral emissivity

atmosphere:
  modtran_file: data/midlat_summer.tape7   # still supported (MODTRAN format)
```

When `qe_file` is specified, it overrides `detector.material` for QE computation. The material-based dark current model is still used unless `dark_current` is also specified directly.

---

## 8. User-Provided Sensor Templates

A **sensor template** is a YAML sensor config file that ships with a plugin package and is available by name (not path) in user configs.

### 8.1 Declaring a Template

In the plugin package's `pyproject.toml`:

```toml
[project.entry-points."radiant.templates"]
baseline_mwir = "mypkg:data/sensors/baseline_mwir.yaml"
high_res_vnir = "mypkg:data/sensors/high_res_vnir.yaml"
```

Templates are loaded from the installed package's data directory using `importlib.resources`.

### 8.2 Using a Template

```yaml
# User config: reference a named template instead of a file path
_extends: template://baseline_mwir

geometry:
  observer_altitude: 600000
  ...
```

```python
s = Sensor.load(sensor="template://baseline_mwir", scenario="scenarios/leo_clear.yaml")
```

Template names are globally unique within the `radiant.templates` entry point group. A conflict (two packages declare `baseline_mwir`) raises `PluginConflictError`.

### 8.3 Listing Available Templates

```bash
radiant templates list
# baseline_mwir   (mypkg 1.2.0) — 0.3m aperture MWIR LEO pushbroom
# high_res_vnir   (mypkg 1.2.0) — 0.1m aperture VNIR aerial
```

---

## 9. Plugin Validation and Testing

### 9.1 Plugin Contract Tests

RADIANT ships a `radiant.testing` module with contract validators. Plugin authors run these in their test suite.

```python
# In the plugin package's test suite:
from radiant.testing import assert_plugin_contract

def test_hyperspectral_source_contract():
    from mypkg.hyperspectral_source import HyperspectralLibrarySource
    plugin = HyperspectralLibrarySource()
    assert_plugin_contract(plugin)
```

`assert_plugin_contract` verifies:
1. `plugin.name` is a valid Python identifier, lowercase, no spaces
2. `plugin.get_schema()` returns a list of `ParameterDef` objects with valid names
3. All `ParameterDef` names start with the plugin's expected namespace
4. The plugin does not shadow built-in parameter names
5. The plugin's `compute*` method returns the expected type for controlled inputs
6. Exceptions raised by the plugin are `RadiantError` subclasses (not bare exceptions)

### 9.2 Plugin Integration Tests

Plugin authors should provide at least one integration test that runs the plugin within a full RADIANT chain:

```python
def test_hyperspectral_source_in_full_chain():
    from radiant import Sensor
    from mypkg.hyperspectral_source import HyperspectralLibrarySource

    s = Sensor.load("tests/fixtures/mwir_leo_baseline.yaml")
    s.register_plugin(HyperspectralLibrarySource())
    s.set("atmosphere.model", "simple")
    s.set("source.spectral_library_file", "tests/fixtures/vegetation_mwir.csv")
    s.set("source.library_target_name", "green_vegetation")

    result = s.evaluate()
    assert result.snr() > 0    # basic sanity
    assert result.snr() < 1000  # not obviously wrong
```

### 9.3 Required Plugin Documentation

Every plugin package must provide:
1. A YAML example config showing how to use the plugin
2. A `CHANGELOG.md` tracking changes that affect numerical results
3. A golden result file for at least one reference scenario
4. A `radiant_plugin_version` key in `pyproject.toml` indicating the minimum RADIANT version required
