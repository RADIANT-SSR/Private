# Error Taxonomy

Every exception RADIANT raises on purpose derives from `RadiantError`. That single base
class is what lets user code separate "the framework rejected my input" from "an
unrelated bug crashed the run":

```python
from radiant import RadiantError, Sensor

try:
    result = Sensor.from_yaml("my_config.yaml").evaluate()
except RadiantError as exc:
    # Every framework-defined rejection lands here.
    print(f"RADIANT rejected the run: {exc}")
```

`RadiantError` lives at `radiant.core.exceptions.RadiantError` and is re-exported at the
top level as `radiant.RadiantError`. It is one of the two names in the package's
stability-guaranteed surface.

---

## 1. The Actionability Contract

An exception that says only "invalid parameter" is a bug. Every raise site carries three
things:

| Field | Question it answers |
|-------|--------------------|
| **what** | What specifically is wrong — the parameter, the value, the file, the line |
| **why** | The physics or logic reason it is wrong |
| **action** | What the user should do to fix it |

Some classes formalize these as constructor fields, with an optional fourth `context`
dict of diagnostic values that tooling can render field by field instead of parsing a
message string:

```python
from radiant.core.parameters import ParameterBoundsError

raise ParameterBoundsError(
    what=f"sensor.detector.operating_temp = {T} K is out of bounds",
    why="HgCdTe operates at cryogenic temperature (1–300 K)",
    action="Set operating_temp to 77–120 K for HgCdTe detectors",
    context={"param": "sensor.detector.operating_temp", "value": T, "bounds": (1, 300)},
)
```

Rendered, the three fields flatten into one message:

```
Parameter 'source.target.emissivity' = 1.5 out of bounds [0.0, 1.0] (dimensionless)
 | Why: 'source.target.emissivity' must lie within its declared valid domain
        [0.0, 1.0] dimensionless
 | Action: Set 'source.target.emissivity' to a value in [0.0, 1.0] dimensionless
```

Classes that have not adopted the structured constructor carry the same three pieces of
information in the message string. The classes with structured `what`/`why`/`action`/
`context` fields are `ParameterBoundsError`, `ParameterEnumError`,
`AtmosphereCapabilityError`, `TurbulenceSpecificationError`, `FPAPresetError`,
`GeometrySpecificationError`, `ConfigSetError`, `ConfigurationScopeError`,
`GuiUnavailableError`, and `ZemaxParseError`.

### Built-in co-inheritance

Many classes co-inherit a built-in exception type — `ValueError`, `RuntimeError`,
`KeyError`, `NotImplementedError`. That is a deliberate back-compat carve-out from the
CU-043 migration: sites that historically raised a bare `ValueError` are caught as such
throughout the test suite and in user code, and those `except ValueError` blocks keep
working. `RadiantError` remains the canonical base. **New** RADIANT exception classes
should inherit from `RadiantError` only.

### What is never used for errors

- `assert` is for developer invariants only, never for validating user input.
- No physics-layer function returns `NaN` or `inf` silently — it raises.
- No `except Exception: pass`, no silent default substitution, no clipping a value into
  range without at minimum a `UserWarning`.

The one carve-out is the **metric layer**: computations under `radiant.performance/`
(`snr.py`, `nedt.py`, `niirs.py`) may return a result-typed failure carrying a structured
`failure_reason` field instead of raising, because a metric that cannot be computed for
this scene is a reportable outcome rather than a rejected input. The failure must be named
in the result object the caller already inspects; silent `NaN` propagation stays
forbidden. Physics-layer modules — source through readout — keep the universal raise rule.

---

## 2. The Tree

```
Exception
└── RadiantError
    ├── CoreValidationError (ValueError)
    │   └── RequiredParameterError
    ├── CoreStateError (RuntimeError)
    ├── <Stage>ValidationError (ValueError)      — one per physics stage
    │   ├── ReadoutValidationError
    │   │   ├── ArchitectureOverSpecificationError
    │   │   └── CountingConfigIncompleteError
    │   └── CalibrationValidationError
    │       └── CalibrationConfigIncompleteError
    ├── <Stage>StateError (RuntimeError)          — where invalid-chain-state raises exist
    └── ~50 module-scoped classes (below)
```

Most stage packages carry a stage-scoped `<Stage>ValidationError(RadiantError, ValueError)`
in their `errors.py`, used by the generic input and argument guards, plus a
`...StateError(RadiantError, RuntimeError)` where an invalid-chain-state raise exists.

**Geometry is the exception.** It raises `GeometrySpecificationError(RadiantError)` —
`RadiantError` only, no `ValueError` co-inheritance, no `GeometryValidationError`. The
"a `<Stage>ValidationError` in every stage" pattern is near-universal, not literally
universal.

---

## 3. Core — `radiant.core`

| Class | Bases | Module | What raises it, with an example message |
|-------|-------|--------|------------------------------------------|
| `CoreValidationError` | `RadiantError`, `ValueError` | `core.exceptions` | Generic `radiant.core` input rejection. *"RadiometricFrame 'at_aperture': wavelength_um must be a 1-D array with at least 2 samples, got shape (1,)."* |
| `CoreStateError` | `RadiantError`, `RuntimeError` | `core.exceptions` | A core object used before it is ready (e.g. reading a `ParameterSet` before `resolve()`). *"radiant.core.solar: calibration integral is non-positive. Check the solar model constants."* |
| `UnknownParameterError` | `RadiantError`, `KeyError` | `core.parameters` | A dot-path that is not in the schema; the message suggests near matches. *"Unknown parameter: 'optics.nonexistent_param'. Did you mean: 'optics.focal_length_m', 'optics.n_spiders', 'optics.defocus_um'?"* |
| `RequiredParameterError` | `CoreValidationError` | `core.parameters` | Resolution with a required parameter unset. *"Required parameter 'optics.aperture_diameter_m' is not set. … Set it via: params.set('optics.aperture_diameter_m', value)"* |
| `ParameterBoundsError` | `RadiantError`, `ValueError` | `core.parameters` | A value outside its declared physical domain. *"Parameter 'source.target.emissivity' = 1.5 out of bounds [0.0, 1.0] (dimensionless) \| Why: … \| Action: Set it to a value in [0.0, 1.0]"* |
| `ParameterEnumError` | `RadiantError`, `ValueError` | `core.parameters` | A fixed-choice parameter given a value outside its closed set. *"Parameter 'atmosphere.model' = 'fancy'; must be one of ['simple', 'exo', 'tabulated', 'modtran', 'interpolated'] \| … \| Action: Set it to one of […]"* |
| `OrbitError` | `RadiantError` | `core.orbit` | Invalid orbital input. *"altitude_m must be positive (a LEO altitude), got -100.0."* |
| `RepeatGroundTrackError` | `RadiantError` | `core.repeat_ground_track` | Invalid repeat-ground-track input. *"altitude_m must be positive, got 0.0."* |
| `SolarGeometryError` | `RadiantError` | `core.solar_geometry` | Invalid solar-geometry input. *"day_of_year must be in [1, 366], got 400."* |

`ParameterBoundsError` is by far the most frequently raised class in the framework (279
raise sites), because every bounded parameter and every geometric guard funnels through
it. `core.viewing_triangle` uses it for geometry-consistency violations, for example:

> `solve_viewing_triangle: h_sensor_m = 500.0 m is not above h_target_m = 8000.0 m, but`
> `theta_o_rad = 0.2 rad (11.459°) places the sensor in the above-the-horizon hemisphere`
> `seen from the target`

---

## 4. Physics Stages

| Class | Bases | Module | What raises it, with an example message |
|-------|-------|--------|------------------------------------------|
| `GeometrySpecificationError` | `RadiantError` | `geometry.errors` | An over- or under-specified geometry, or a scene-class assertion that contradicts the altitudes. *"geometry.scene_class asserts 'air_to_ground', but the altitudes derive 'space_to_ground' (sensor 600000 m ⇒ space, target 0 m ⇒ ground)"* — the classic 600 m / 600 km magnitude slip. |
| `SourceValidationError` | `RadiantError`, `ValueError` | `source.errors` | Source/target input guards. *"PhongBRDF: reflectance must be in [0, 1], got min=-0.2, max=1.4"* |
| `AtmosphereValidationError` | `RadiantError`, `ValueError` | `atmosphere.errors` | Atmosphere input and table guards. *"transmittance has negative values (min=-0.02), which have no logarithm. Transmittance is a probability and must be ≥ 0 — check the source table or tape7 columns."* |
| `AtmosphereStateError` | `RadiantError`, `RuntimeError` | `atmosphere.errors` | An atmosphere backend failed at run time. *"MODTRAN exited with code 2. stderr: …"* |
| `AtmosphereCapabilityError` | `RadiantError`, `NotImplementedError` | `atmosphere.errors` | The selected backend cannot serve this path topology (e.g. an up-looking scene on a down-looking family) — structured `what`/`why`/`action`. |
| `TurbulenceSpecificationError` | `RadiantError` | `atmosphere.errors` | An over- or under-specified turbulence input ($r_0$ vs. $C_n^2$ profile) — structured fields. |
| `ModtranUnavailableError` | `RadiantError`, `RuntimeError` | `atmosphere.modtran` | The MODTRAN binary is absent, the cache misses, and fallback is disabled. The message names the binary path that was tried. |
| `Tape7ParseError` | `RadiantError`, `ValueError` | `atmosphere.modtran` | A tape7 file that cannot be parsed. *"MODTRAN tape7 /path/tape7: fewer than 2 spectral data rows parsed. The output may be incomplete."* |
| `OpticsValidationError` | `RadiantError`, `ValueError` | `optics.errors` | Optics input guards. *"scalar_rms_zernike_coeffs: rms_waves must be >= 0, got -0.05. An RMS wavefront error is a magnitude; set optics.wfe_rms_waves >= 0."* |
| `KirchhoffViolationError` | `RadiantError`, `ValueError` | `optics.element` | An optical surface whose R and T violate energy conservation, or one given an independent emissivity. *"CavityModel: energy violation — T_sys + R_sys = 1.04 > 1. Check surface coating values."* |
| `PlatformValidationError` | `RadiantError`, `ValueError` | `platform.errors` | Platform input guards. *"smear_width_m must be non-negative, got -1e-05"* |
| `SpectralIntegrationValidationError` | `RadiantError`, `ValueError` | `spectral_integration.errors` | Missing or malformed spectral input at the collapse. *"SpectralIntegrationStage: 'post_optics' frame has no spectral_radiance."* |
| `SpectralIntegrationStateError` | `RadiantError`, `RuntimeError` | `spectral_integration.errors` | A Rule-9 invariant violated upstream. *"EE_box != 1.0 but regime is 'extended' (EE_box=0.82). In extended-scene mode, EE_box must not be applied (Rule 9). This is a programming error in PlatformStage."* |
| `DetectorValidationError` | `RadiantError`, `ValueError` | `detector.errors` | Detector input guards. *"diffusion_length_m must be non-negative, got -2e-06"* |
| `PersistenceSequenceError` | `RadiantError` | `detector.persistence_sequence` | Invalid persistence-sequence input. *"prior_signal_e must be ≥ 0, got -5.0."* |
| `ReadoutValidationError` | `RadiantError`, `ValueError` | `readout.errors` | Readout input guards. *"check_well_saturation: full_well_capacity_e = 0.0 must be > 0."* |
| `ArchitectureOverSpecificationError` | `ReadoutValidationError` | `readout.errors` | A readout architecture given a parameter its model derives. *"readout.full_well_capacity_e = 2e+06 e- is explicitly set while readout.architecture = 'digital_counting'. Under counting the effective well is 2^counter_bits × count_packet_e."* |
| `CountingConfigIncompleteError` | `ReadoutValidationError` | `readout.errors` | A digital-counting readout missing the parameter that sizes the count. *"readout.count_packet_e is required when readout.architecture = 'digital_counting'."* |
| `CalibrationValidationError` | `RadiantError`, `ValueError` | `calibration.errors` | Calibration input guards. *"signal_e = -3.0 must be finite and non-negative. Why: the gain-drift residual is proportional to signal. Action: supply the post-integration signal in electrons."* |
| `CalibrationConfigIncompleteError` | `CalibrationValidationError` | `calibration.errors` | An active NUC scheme with no cal point. *"calibration.scheme = 'two_point' needs a cal point, but calibration.cal_temp_low_K is unset. Why: an active NUC scheme corrects at known cal-source temperatures; without them there is nothing to correct against."* |
| `PerformanceValidationError` | `RadiantError`, `ValueError` | `performance.errors` | Metric input guards. *"GSD must be positive, got along=0.0, cross=0.35"* |

### Metric-specific classes

Each independently testable metric under `radiant.performance/` owns its own error class,
following the one-computation-one-module rule. All inherit `RadiantError` directly, and
all guard the same way: a domain violation on a metric input.

| Class | Module | Example message |
|-------|--------|-----------------|
| `BlipRateError` | `performance.blip_rate` | *"photon_signal_e must be ≥ 0, got -12.0."* |
| `DarkCrossoverError` | `performance.dark_crossover_rate` | *"read_noise_e must be ≥ 0, got -1.0."* |
| `DetectivityError` | `performance.detectivity` | *"area_cm2 must be positive, got 0.0."* |
| `DiffractionLimitError` | `performance.diffraction_limit` | *"wavelength_m must be positive, got 0.0."* |
| `FrequencyUnitError` | `performance.frequency_units` | *"convert_spatial_frequency: unknown unit 'cycles/pixel'. Supported: cycles/mm, cycles/mrad, …"* |
| `GIQESensitivityError` | `performance.giqe_sensitivity` | *"giqe5_sensitivity: rer = 0.0 must be positive — the GIQE-5 log terms are undefined at or below zero."* |
| `JohnsonCriteriaError` | `performance.johnson_criteria` | *"critical_dimension_m must be positive, got 0.0."* |
| `MinimumResolvableError` | `performance.minimum_resolvable` | *"noise_metric must be ≥ 0, got -0.1."* |
| `NepElectronsError` | `performance.nep_electrons` | *"qe must be in (0, 1], got 1.4."* |
| `NepNetdError` | `performance.nep_netd` | *"nep_w must be ≥ 0, got -1e-12."* |
| `NoiseEquivalentIrradianceError` | `performance.noise_equivalent_irradiance` | *"total_noise_e must be ≥ 0, got -4.0."* |
| `RocError` | `performance.roc` | *"snr must be ≥ 0, got -2.0."* |
| `SamplingRegimeError` | `performance.sampling_regime` | *"Q must be positive, got 0.0."* |
| `TemperatureRetrievalError` | `performance.temperature_retrieval` | *"wavelength_um_band must be a 1-D array with ≥ 2 points."* |

---

## 5. I/O and Data — `radiant.io`, `radiant.data`

| Class | Bases | Module | What raises it, with an example message |
|-------|-------|--------|------------------------------------------|
| `ConfigError` | `RadiantError` | `io.config` | A YAML config that cannot be loaded: malformed document, a reserved key, or a structured section this loader cannot attach. *"Top-level YAML must be a mapping, got list."* |
| `ElementConfigError` | `RadiantError`, `ValueError` | `io.element_config` | A malformed `optical_elements` entry, Kirchhoff violations included. *"Element 'M1': transfer_mode must be 'REFLECTIVE' or 'REFRACTIVE', got 'MIRROR'."* |
| `MeasurementParseError` | `RadiantError` | `io.measurement` | A measured-curve CSV that will not parse. *"line 14: row has 1 column(s) but x_column=0, y_column=1 require at least 2. Check the delimiter (currently splitting into ['0.5;0.83']) and the column indices."* |
| `QeCsvParseError` | `RadiantError` | `io.qe_csv` | A vendor QE CSV whose units cannot be resolved. *"cannot infer the wavelength unit from header column 'lambda'. Pass wavelength_unit=\"nm\" or \"um\" explicitly."* |
| `DarkCurrentCsvParseError` | `RadiantError` | `io.dark_current_csv` | A vendor dark-current CSV problem, including out-of-range temperature queries. *"file /path/jdark.csv does not exist or is not a file. Check the path; vendor dark-current data is the CSV export of the J_dark(T) datasheet plot."* |
| `ZemaxParseError` | `RadiantError` | `io.zemax_zernike` | A Zernike Standard Coefficients export that will not parse — wrong file kind, unknown encoding, or repeated Noll indices from a multi-field export. Structured `what`/`why`/`action`/`context`. |
| `AsterLibraryError` | `RadiantError` | `io.aster_library` | An ASTER spectral-library file problem. *"file /path/spectrum.txt does not exist or is not a file. Check the path to the ASTER library spectrum (speclib.jpl.nasa.gov text format)."* |
| `TargetLibraryError` | `RadiantError` | `io.target_library` | A target-list workbook problem, including the missing `openpyxl` extra. *"file /path/targets.xlsx does not exist or is not a file. Check the path to the target-library workbook."* |
| `ResultArchiveError` | `RadiantError` | `io.serialization` | A saved-result archive that cannot be read. *"Result archive not found: /path/run.zip. Check the path, or produce one with ChainResult.save(path)."* |
| `FPAPresetError` | `RadiantError` | `data.fpa` | A malformed or unknown FPA preset. Structured fields: *what* "Preset 'x.yaml' field 'vendor' is missing or not a non-empty string", *why* "Every preset names its part identity so provenance is auditable", *action* "Add 'vendor: \<text\>' to …". |

---

## 6. API and Front Ends

| Class | Bases | Module | What raises it, with an example message |
|-------|-------|--------|------------------------------------------|
| `ApiValidationError` | `RadiantError`, `ValueError` | `api.errors` | A `radiant.api` call given a bad argument. *"Sensor.load: '_radiant.wavelength_points' must be an integer >= 2, got 1 in my_config.yaml."* |
| `OperationCancelledError` | `RadiantError` | `api._progress` | A long-running operation aborted through its `cancel()` callback. Carries `operation`, `done`, `total`. *"sweep cancelled after 12/51 evaluations. No result is returned for a cancelled operation; re-run, or sweep in smaller chunks if partial results are needed."* |
| `SolveBracketError` | `RadiantError` | `api.solve` | `solve_for` given a bracket that does not contain the target; carries both endpoint metric values. *"solve_for('optics.aperture_diameter_m'): bounds must satisfy lo < hi, got (1.0, 0.05)."* |
| `BatchRunnerError` | `RadiantError` | `api.batch` | Invalid batch construction or an invalid pivot query. *"BatchRunner needs at least one axis; got an empty sequence."* |
| `ComparisonError` | `RadiantError` | `api.compare` | An invalid `compare_configs` request. *"compare_configs needs at least 2 configurations, got 1. Pass two or more (label, ChainResult) pairs."* |
| `MtfComparisonError` | `RadiantError` | `api.compare` | An invalid `compare_mtf` request. *"compare_mtf: axis must be 'x' or 'y', got 'z'. 'x' is cross-track, 'y' is along-track."* |
| `ConfigSetError` | `RadiantError` | `api.config_set` | An invalid configuration-set operation: a duplicate name, a value-list length mismatch, a parameter both shared and configured, more than `MAX_CONFIGS` names. Structured fields. |
| `ErrorBudgetError` | `RadiantError` | `api.error_budget` | A malformed error-budget contributor. *"BudgetContributor: name must be non-empty."* |
| `CalibrationAnalysisError` | `RadiantError` | `api.calibration_analysis` | An invalid calibration-analysis input. *"wavelength_um must be a 1-D array with ≥ 2 points."* |
| `GuiUnavailableError` | `RadiantError` | `cli.gui` | `radiant gui` without the GUI extra installed. Structured fields naming `pip install "radiant[gui]"`. |
| `GuiValidationError` | `RadiantError`, `ValueError` | `gui.errors` | A GUI-layer input rejection. *"RADIANT_GUI_DEBOUNCE_MS=-50 ms is negative — a debounce window cannot run backwards in time."* |
| `ConfigurationScopeError` | `RadiantError` | `gui.config_scope` | An edit applied at the wrong configuration scope (shared vs. per-configuration). Structured fields. |

---

## 7. Catching Selectively

Catch `RadiantError` when you want "the framework said no" and nothing else. Catch a
specific class when you intend to recover from that one condition:

```python
from radiant import RadiantError, Sensor
from radiant.api import OperationCancelledError
from radiant.core.parameters import ParameterBoundsError

sensor = Sensor.from_yaml("examples/mwir_leo_minimal.yaml")

try:
    sensor.set("source.target.emissivity", 1.5)
except ParameterBoundsError as exc:
    print(exc.what)                  # the specific violation
    print(exc.why)                   # the physics reason
    print(exc.action)                # the fix
    print(exc.context["bounds"])     # (0.0, 1.0) — structured, no string parsing
except RadiantError:
    raise
```

Because of the co-inheritance carve-out, `except ValueError` still catches the bounds and
enum errors, and `except KeyError` still catches `UnknownParameterError`. Code that wants
to be explicit about intent should name `RadiantError` or the concrete class instead.

A `BatchRunner` cell is the one place where a `RadiantError` is deliberately *recorded*
rather than propagated: the cell becomes a row with a populated `error` column. Any other
exception type is treated as a programming bug and propagates out of the batch.
