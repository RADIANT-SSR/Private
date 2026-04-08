# RADIANT File Tree and Module Layout

**Status**: Authoritative  
**Derived from**: RADIANT_Signal_Chain_Architecture.md, RADIANT_Parameter_System.md, RADIANT_Conventions.md  
**Target file count**: ~150 source files (excluding data assets)

---

## Design Principles

1. **One subpackage per signal chain stage.** Every physics module is isolated in its own subpackage. Cross-stage coupling flows through `ChainState`, not imports.
2. **`core/` has zero physics dependencies.** Core abstractions (constants, units, parameters, spectral store, chain protocol) import only stdlib and numpy/scipy. Nothing in `core/` knows about sensors.
3. **Physics modules import only `core/` and stdlib.** No physics module imports another physics module. Inter-stage communication is through `ChainState`.
4. **`io/`, `api/`, `cli/` are the integration layers.** They may import from anything below them. Physics modules never import from these.
5. **Tests live alongside implementation.** Each subpackage has a `tests/` subdirectory. Integration tests live in a top-level `tests/integration/`.
6. **`_schema.py` in every physics subpackage.** Each stage owns its `ParameterDef` registry. The top-level schema is assembled by `api/`.

---

## Full Directory Tree

```
radiant/                           # Single namespace package
├── __init__.py                    # Package version, public re-exports
│
├── core/                          # Foundational abstractions — no physics
│   ├── __init__.py
│   ├── constants.py               # CODATA 2018 exact physical constants
│   ├── units.py                   # Unit conversion registry (convert, inverse_convert)
│   ├── parameters.py              # ParameterDef, ParameterSet, ResolvedValue, Tolerance
│   ├── spectral.py                # SpectralData, SpectralDataStore
│   ├── chain.py                   # ChainState, Stage ABC, ChainRunner
│   ├── radiometry.py              # RadiometricFrame, NoiseTerm, NoiseFrame, EE_box coupling
│   ├── geometry.py                # ObserverGeometry, TargetGeometry, SceneGeometry
│   └── regime.py                  # RadiometricRegime enum (EXTENDED, POINT_SOURCE, SUB_PIXEL)
│   └── tests/
│       ├── __init__.py
│       ├── test_constants.py      # CODATA values, derived quantities
│       ├── test_units.py          # Conversion roundtrips, missing key errors
│       ├── test_parameters.py     # ParameterSet: resolve, derive, bounds, Monte Carlo
│       ├── test_spectral.py       # SpectralDataStore: add, interpolate, out-of-range
│       ├── test_chain.py          # ChainState immutability, Stage protocol
│       ├── test_geometry.py       # SceneGeometry construction, GSD/slant range
│       └── test_regime.py         # Regime classification logic
│
├── source/                        # Stage 1: Target + background spectral radiance
│   ├── __init__.py
│   ├── _schema.py                 # ParameterDefs: target_temp, emissivity_model, ...
│   ├── stage.py                   # SourceStage: populates at_target RadiometricFrame
│   ├── blackbody.py               # Planck function, integrated radiance, spectral exitance
│   ├── solar.py                   # Solar spectral irradiance loader and models
│   ├── reflected.py               # BRDF-weighted reflected solar radiance
│   ├── emitted.py                 # Thermal self-emission from target surface
│   ├── background.py              # Extended background / clutter spectral radiance
│   └── emissivity.py              # Emissivity spectral models (graybody, spectral lookup)
│   └── tests/
│       ├── __init__.py
│       ├── test_blackbody.py      # Planck vs. analytic integrals, Stefan-Boltzmann check
│       ├── test_solar.py          # Spectrum loading, unit conversion
│       ├── test_reflected.py      # BRDF models, lambertian limit
│       ├── test_emitted.py        # Emissivity × Planck consistency
│       └── test_background.py    # Background radiance integration
│
├── atmosphere/                    # Stage 2: Transmittance, path radiance, thermal emission
│   ├── __init__.py
│   ├── _schema.py                 # ParameterDefs: range_km, altitude_m, visibility_km, ...
│   ├── stage.py                   # AtmosphereStage: applies 3-output interface to at_target
│   ├── modtran.py                 # MODTRAN tape7/tape8 reader + interface wrapper
│   ├── simple.py                  # Beer-Lambert / exponential transmittance model
│   ├── standard.py                # Standard atmosphere profiles: US76, tropical, subarctic
│   ├── lowtran.py                 # LOWTRAN-style 7-band empirical transmittance (stub)
│   ├── transmittance.py           # SpectralTransmittance container + wavelength interpolation
│   ├── path_radiance.py           # SpectralPathRadiance container
│   ├── thermal_emission.py        # Atmospheric thermal emission (downwelling / upwelling)
│   └── turbulence.py              # Fried r0, Cn² profiles, turbulence MTF term
│   └── tests/
│       ├── __init__.py
│       ├── test_modtran.py        # Reader against known tape7 fixture
│       ├── test_simple.py         # Beer-Lambert vs. analytic, boundary cases
│       ├── test_transmittance.py  # Container interpolation, wavelength alignment
│       └── test_turbulence.py     # r0 from Cn², turbulence MTF shape
│
├── optics/                        # Stage 3: PSF, MTF terms, throughput, EE_box, regime final
│   ├── __init__.py
│   ├── _schema.py                 # ParameterDefs: aperture_diameter, focal_length, f_number, ...
│   ├── stage.py                   # OpticsStage: finalizes regime, computes EE_box
│   ├── psf.py                     # PSF container, PSF → MTF transform, PSF moments
│   ├── diffraction.py             # Circular aperture diffraction MTF (Airy, OTF)
│   ├── aberrations.py             # WFE → MTF: Marechal approximation + full OTF integral
│   ├── defocus.py                 # Defocus MTF (sinc-based)
│   ├── obscuration.py             # Central obscuration effect on diffraction MTF
│   ├── smear_optics.py            # Optical smear (vibration-driven, LOS wobble)
│   ├── throughput.py              # Optics transmission: coatings, windows, beamsplitters
│   ├── filter.py                  # Bandpass filter spectral transmission model
│   └── ee_box.py                  # EE_box computation from PSF over pixel footprint
│   └── tests/
│       ├── __init__.py
│       ├── test_psf.py            # PSF normalization, moments, OTF transform
│       ├── test_diffraction.py    # Airy disk limits, Rayleigh criterion
│       ├── test_aberrations.py    # Marechal vs. OTF integral agreement
│       ├── test_ee_box.py         # EE_box vs. analytic Airy integrals
│       ├── test_filter.py         # Bandpass shape, out-of-band rejection
│       └── test_throughput.py    # Transmission stack product
│
├── platform/                      # Stage 4: Smear, jitter, sampling MTF
│   ├── __init__.py
│   ├── _schema.py                 # ParameterDefs: velocity, altitude, integration_time, ...
│   ├── stage.py                   # PlatformStage: smear + jitter MTF terms
│   ├── geometry.py                # GSD, IFOV, slant range, look angle, ground projection
│   ├── smear.py                   # Image smear MTF: along-track (rect), cross-track
│   ├── jitter.py                  # LOS jitter MTF: Gaussian, sinusoidal models
│   └── sampling.py                # Pixel aperture MTF (rect); Nyquist / aliasing notes
│   └── tests/
│       ├── __init__.py
│       ├── test_geometry.py       # GSD vs. altitude/FL/pitch, slant range
│       ├── test_smear.py          # Smear MTF at zero → unity, at 1 pixel → sinc
│       └── test_jitter.py         # Jitter MTF normalization
│
├── spectral_integration/          # Stage 5: Spectral → scalar (applies EE_box coupling)
│   ├── __init__.py
│   ├── _schema.py                 # ParameterDefs: integration method, ...
│   ├── stage.py                   # SpectralIntegrationStage: EE_box × QE × spectral radiance
│   ├── integration.py             # Numerical integration: trapezoid, midpoint, Gauss-Legendre
│   └── grid.py                    # Wavelength grid construction, resolution management
│   └── tests/
│       ├── __init__.py
│       ├── test_integration.py    # ∫Planck dλ vs. σT⁴, bandpass consistency
│       └── test_grid.py           # Grid construction, resolution checks
│
├── detector/                      # Stage 6: QE, photoelectrons, detector MTF, detector noise
│   ├── __init__.py
│   ├── _schema.py                 # ParameterDefs: pitch, FWC, dark_current_rate, QE_model, ...
│   ├── stage.py                   # DetectorStage: radiance → photoelectrons + noise terms
│   ├── qe.py                      # Quantum efficiency: spectral model, temperature dependence
│   ├── dark_current.py            # Dark current: Rule 07, activation energy, ROIC contribution
│   ├── shot_noise.py              # Photon shot noise, dark current shot noise
│   ├── prnu.py                    # Photo-response nonuniformity model
│   ├── nonlinearity.py            # Detector nonlinearity: polynomial model
│   ├── saturation.py              # Full-well capacity, anti-blooming
│   ├── ipc.py                     # Inter-pixel capacitance MTF
│   └── diffusion.py               # Charge diffusion MTF (Gaussian model)
│   └── tests/
│       ├── __init__.py
│       ├── test_qe.py             # QE × photon flux = signal electrons
│       ├── test_dark_current.py   # Rule 07 regression, temperature scaling
│       ├── test_shot_noise.py     # Poisson statistics, sqrt(signal) limit
│       ├── test_ipc.py            # IPC MTF: α=0 → unity, α>0 → lowpass
│       └── test_diffusion.py      # Diffusion MTF: Gaussian shape, cutoff
│
├── readout/                       # Stage 7: Read noise, ADC, gain, fixed-pattern
│   ├── __init__.py
│   ├── _schema.py                 # ParameterDefs: read_noise_erms, gain_e_per_dn, bit_depth, ...
│   ├── stage.py                   # ReadoutStage: electrons → DN + noise terms
│   ├── read_noise.py              # Read noise (CDS, Fowler-N, up-the-ramp)
│   ├── one_over_f.py              # 1/f (flicker) noise model
│   ├── ktc.py                     # kTC (reset) noise; CDS cancellation
│   ├── adc.py                     # A/D conversion, quantization noise, DN range
│   ├── gain.py                    # System gain e⁻/DN, gain nonuniformity (GNNU)
│   └── fixed_pattern.py           # DSNU, column/row FPN
│   └── tests/
│       ├── __init__.py
│       ├── test_read_noise.py     # CDS, Fowler-N reduction factors
│       ├── test_ktc.py            # kTC magnitude, CDS cancellation
│       ├── test_adc.py            # Quantization noise = LSB/√12
│       └── test_gain.py           # Gain roundtrip, DN saturation level
│
├── performance/                   # Stage 8: SNR, NEDT, NIIRS, MTF, detection range
│   ├── __init__.py
│   ├── _schema.py                 # ParameterDefs: target_contrast, required_snr, ...
│   ├── stage.py                   # PerformanceStage: assembles all metrics from ChainState
│   ├── snr.py                     # SNR: signal / √(sum-quadrature noise)
│   ├── nedt.py                    # NEDT: ΔT → Δsignal via dL/dT at scene temperature
│   ├── nei.py                     # NEI: noise equivalent irradiance (point source)
│   ├── system_mtf.py              # System MTF: product of all MTF terms in ChainState
│   ├── giqe.py                    # GIQE5 implementation (EO-NIIRS)
│   ├── iirs.py                    # IIRS implementation (IR NIIRS)
│   ├── niirs.py                   # NIIRS dispatcher: selects GIQE5 vs. IIRS by regime/band
│   ├── detection_range.py         # Detection/acquisition range from SNR or MDTD
│   └── mdtd.py                    # MDTD / MRT (minimum resolvable temperature difference)
│   └── tests/
│       ├── __init__.py
│       ├── test_snr.py            # Known signal/noise → known SNR
│       ├── test_nedt.py           # dL/dT analytic check vs. finite difference
│       ├── test_giqe.py           # GIQE5 against published sample cases
│       ├── test_iirs.py           # IIRS against published sample cases
│       └── test_detection_range.py
│
├── io/                            # I/O layer: config, file readers, results serialization
│   ├── __init__.py
│   ├── config.py                  # YAML sensor config loader → ParameterSet
│   ├── modtran_reader.py          # MODTRAN tape5/tape7/tape8 parser
│   ├── spectral_library.py        # Generic spectral file reader: CSV, ASCII column, ENVI hdr
│   ├── results.py                 # RadiantResult container, JSON/dict serialization
│   └── hdf5.py                    # HDF5 read/write for spectral data and batch results
│   └── tests/
│       ├── __init__.py
│       ├── test_config.py         # YAML roundtrip, required vs. optional, bad values
│       ├── test_modtran_reader.py # Reader against fixture tape7 file
│       └── test_results.py        # Serialization roundtrip
│
├── cli/                           # Command-line interface
│   ├── __init__.py
│   ├── main.py                    # Entry point registered as `radiant` in pyproject.toml
│   ├── run.py                     # `radiant run <config.yaml>` subcommand
│   ├── explain.py                 # `radiant explain <param>` — provenance dump
│   └── validate.py                # `radiant validate <config.yaml>` — dry-run validation
│   └── tests/
│       ├── __init__.py
│       └── test_cli.py            # Click test-runner: run, explain, validate subcommands
│
├── api/                           # Scripting API: public, stable, version-guaranteed
│   ├── __init__.py                # Public symbols: RadiantSession, SensorConfig, ScenarioConfig
│   ├── session.py                 # RadiantSession: top-level object, run(), explain(), batch()
│   ├── sensor.py                  # SensorConfig: fluent builder for sensor parameters
│   ├── scenario.py                # ScenarioConfig: fluent builder for scene/geometry
│   └── batch.py                   # BatchRunner: parameter sweeps, Monte Carlo, multiprocessing
│   └── tests/
│       ├── __init__.py
│       ├── test_session.py        # End-to-end: session → result
│       └── test_batch.py          # Parameter sweep, result collection
│
└── plugins/                       # Extension point for third-party physics modules
    ├── __init__.py
    ├── _registry.py               # Plugin discovery via importlib.metadata entry_points
    ├── base.py                    # ABCs: SourcePlugin, AtmospherePlugin, MetricPlugin, StagePlugin
    └── tests/
        ├── __init__.py
        └── test_registry.py       # Discovery, registration, name collision handling
```

---

## Top-Level Repository Layout

```
SSR_Tool/
├── src/
│   └── radiant/                   # Package root (src layout)
│       └── ...                    # (tree above)
│
├── tests/
│   └── integration/               # Cross-stage integration tests
│       ├── __init__.py
│       ├── fixtures/
│       │   ├── sample_tape7.txt   # MODTRAN tape7 fixture for atmosphere tests
│       │   ├── vnir_config.yaml   # Complete VNIR sensor config
│       │   ├── mwir_config.yaml   # Complete MWIR sensor config
│       │   └── lwir_config.yaml   # Complete LWIR sensor config
│       ├── test_chain_vnir.py     # Full chain: VNIR extended target, SNR + NIIRS
│       ├── test_chain_mwir.py     # Full chain: MWIR dual-source (reflected + emitted)
│       ├── test_chain_lwir.py     # Full chain: LWIR thermal, NEDT + IIRS
│       └── test_chain_point.py    # Full chain: point source regime, NEI
│
├── data/
│   ├── solar/
│   │   ├── kurucz_1nm.csv         # Kurucz solar reference spectrum (W/m²/µm at 1 AU)
│   │   └── astm_e490.csv          # ASTM E490 extraterrestrial solar spectrum
│   ├── emissivity/
│   │   └── spectralon_reflectance.csv  # Reference reflectance panel
│   └── atmospheres/
│       └── us_standard_1976.csv   # US Standard Atmosphere 1976 profile
│
├── docs/
│   ├── adr/
│   │   ├── 0000-template.md
│   │   ├── 0001-scope-and-constraints.md
│   │   └── ...
│   ├── RADIANT_Physics_Inventory.md
│   ├── RADIANT_Scope_Decisions.md
│   ├── RADIANT_Personas.md
│   ├── RADIANT_Conventions.md
│   ├── RADIANT_Parameter_System.md
│   ├── RADIANT_Signal_Chain_Architecture.md
│   └── RADIANT_File_Tree.md       # This document
│
├── examples/
│   ├── vnir_trade.py              # VNIR aperture/altitude SNR trade script
│   ├── mwir_crossover.py          # MWIR crossover temperature analysis
│   └── batch_mc.py                # Monte Carlo tolerance analysis example
│
├── pyproject.toml                 # Build config, entry points, dependencies
└── README.md
```

---

## File Count Summary

| Subpackage           | Source | Tests | Total |
|----------------------|--------|-------|-------|
| core/                | 8      | 7     | 15    |
| source/              | 8      | 5     | 13    |
| atmosphere/          | 9      | 4     | 13    |
| optics/              | 11     | 6     | 17    |
| platform/            | 6      | 3     | 9     |
| spectral_integration/| 4      | 2     | 6     |
| detector/            | 10     | 5     | 15    |
| readout/             | 7      | 4     | 11    |
| performance/         | 10     | 5     | 15    |
| io/                  | 5      | 3     | 8     |
| cli/                 | 4      | 1     | 5     |
| api/                 | 5      | 2     | 7     |
| plugins/             | 3      | 1     | 4     |
| **Subtotal**         | **90** | **48**| **138**|
| integration tests    | —      | 5     | 5     |
| **Grand total**      |        |       | **143**|

---

## Import Rules

```
                    stdlib, numpy, scipy
                           │
                        core/
                           │
        ┌──────────────────┼──────────────────┐
        │                  │                  │
    source/          atmosphere/           optics/
    platform/      spectral_integration/  detector/
                      readout/           performance/
        │                  │                  │
        └──────────────────┼──────────────────┘
                           │
                          io/
                           │
                          api/
                           │
                          cli/
```

**Enforcement rules:**

1. `core/` → stdlib, numpy, scipy only. No other `radiant.*` imports.
2. Physics subpackages (`source/`, `atmosphere/`, `optics/`, `platform/`, `spectral_integration/`, `detector/`, `readout/`, `performance/`) → `radiant.core` only. No cross-stage physics imports.
3. `io/` → `radiant.core` + any physics subpackage (read-only access for schema introspection). No imports from `api/` or `cli/`.
4. `api/` → `radiant.core` + all physics subpackages + `radiant.io`. No `cli/` imports.
5. `cli/` → `radiant.api` + `radiant.io`. No direct physics imports.
6. `plugins/` → `radiant.core` only (defines ABCs; concrete plugins live outside the package).
7. No circular imports at any level. Enforced via `import-linter` in CI.

---

## Public vs. Private API

### Public (stable, versioned, user-facing)

| Symbol | Location |
|--------|----------|
| `RadiantSession` | `radiant.api.session` |
| `SensorConfig` | `radiant.api.sensor` |
| `ScenarioConfig` | `radiant.api.scenario` |
| `BatchRunner` | `radiant.api.batch` |
| `RadiantResult` | `radiant.io.results` |
| `SourcePlugin`, `AtmospherePlugin`, `MetricPlugin` | `radiant.plugins.base` |

All public symbols are re-exported from `radiant/__init__.py`.  
Public API is guaranteed stable across minor versions. Breaking changes require a major version bump.

### Semi-public (stable for plugin authors, not for end users)

| Module | Audience |
|--------|----------|
| `radiant.core.*` | Plugin authors, advanced users |
| `radiant.io.config`, `radiant.io.modtran_reader` | Integration scripts |

### Private (internal, no stability guarantee)

- All `_schema.py` files (assembled by `api/` into the master schema)
- All `_registry.py`, `_*.py` prefixed modules
- Individual stage `stage.py` implementations (accessed through `ChainRunner`, not directly)
- Sub-module internals within physics packages

---

## Plugin and Extension System

### Extension Points

Three formal plugin types, each with a defined ABC in `radiant.plugins.base`:

```
SourcePlugin          Custom target/background spectral radiance model
AtmospherePlugin      Custom atmosphere (replaces or wraps MODTRAN interface)
MetricPlugin          Custom performance metric appended to PerformanceStage output
```

A fourth informal extension point: `StagePlugin` allows injecting a new `Stage` into `ChainRunner`'s stage list. Use sparingly; prefer the three typed plugins.

### Registration

Plugins are discovered via `importlib.metadata` entry points declared in the plugin package's `pyproject.toml`:

```toml
[project.entry-points."radiant.plugins"]
my_atmosphere = "mypackage.atmosphere:MyAtmospherePlugin"
my_metric = "mypackage.metrics:ContrastMetricPlugin"
```

`radiant.plugins._registry.load_plugins()` is called once at `RadiantSession` construction.  
Name collisions raise `PluginConflictError` (explicit over implicit).

### Adding a Custom Source

```python
from radiant.plugins.base import SourcePlugin
from radiant.core.spectral import SpectralData
from radiant.core.chain import ChainState

class HyperspectralLibrarySource(SourcePlugin):
    name = "hyperspectral_library"

    def __init__(self, library_path: str) -> None:
        self._path = library_path

    def get_schema(self) -> list:           # returns list[ParameterDef]
        ...

    def compute(self, state: ChainState) -> SpectralData:
        ...                                 # returns target SpectralData
```

---

## `_schema.py` Convention

Every physics subpackage owns its parameter definitions. Format:

```python
# source/_schema.py
from radiant.core.parameters import ParameterDef

SOURCE_PARAMS: list[ParameterDef] = [
    ParameterDef(
        name="source.target_temperature",
        description="Target surface temperature",
        dtype=float,
        canonical_unit="K",
        input_unit="K",
        bounds=(0.0, 5000.0),
        tags=frozenset({"thermal", "source"}),
    ),
    ...
]
```

`api/session.py` assembles the master schema by importing all `*_PARAMS` lists and passing them to a single `ParameterSet`. Users never instantiate `ParameterSet` directly.

---

## Naming Conventions

- **Module files**: `snake_case.py`
- **Private modules**: `_snake_case.py`
- **Classes**: `PascalCase`
- **Private class members**: `_leading_underscore`
- **Parameter dot-paths**: `stage.group.name` (e.g., `optics.aperture_diameter`, `detector.fwc`)
- **MTF terms**: named by stage and effect (e.g., `mtf.diffraction`, `mtf.smear`, `mtf.jitter`)
- **Noise terms**: named by origin (e.g., `noise.photon_shot`, `noise.dark_current`, `noise.read`)

---

## Dependencies

| Package | Role | Required |
|---------|------|----------|
| `numpy` | Array ops, spectral math | Yes |
| `scipy` | Integration, interpolation, special functions | Yes |
| `pyyaml` | YAML config loading | Yes |
| `click` | CLI framework | Yes |
| `h5py` | HDF5 output | Optional |
| `matplotlib` | Plotting (examples only) | Optional |
| `pytest` | Test runner | Dev |
| `import-linter` | Import rule enforcement in CI | Dev |
| `hypothesis` | Property-based testing for physics | Dev |

`modtran` itself is not a Python dependency — RADIANT wraps its file I/O.

---

## Open Questions

1. **`spectral_integration/` naming**: Currently named to match signal chain stage terminology. Alternative: merge small modules into a single file. Decision deferred to implementation.
2. **`data/` packaging**: Reference data (solar spectra, US76) should ship with the package. Mechanism: `importlib.resources` with `data/` as a package resource. Large data files (e.g., full Kurucz spectrum) may need separate distribution.
3. **MTF frequency axis**: MTF arrays are functions of spatial frequency. Convention for the frequency grid (cycles/pixel vs. cycles/mm vs. cycles/mrad) TBD — will be established in the optics architecture prompt.
