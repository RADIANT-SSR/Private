# RADIANT File Tree and Module Layout

**Status:** Living reference (regenerated against current `src/`)
**Last regenerated:** 2026-07-06 (doc-reconciliation pass)
**Source of truth:** `find src/radiant -name '*.py'` — this doc is a derived
view, not a spec. When in doubt, run the find command.

**Current file count:** 348 `.py` files under `src/radiant/` (184 source +
128 test + 36 `__init__.py`), plus 15 integration tests under
`tests/integration/` and 3 top-level test files (`tests/test_public_api.py`,
`tests/test_exceptions.py`, `tests/test_provenance.py`).

---

## Design Principles

1. **One subpackage per signal chain stage.** Every physics module is isolated in its own subpackage. Cross-stage coupling flows through `ChainState`, not imports.
2. **`core/` has zero physics dependencies.** Core abstractions (constants, units, parameters, spectral store, chain protocol, geometry, radiometry) import only stdlib and numpy/scipy. Nothing in `core/` knows about specific sensor configurations.
3. **Physics modules import only `core/` and stdlib.** No physics module imports another physics module. Inter-stage communication is through `ChainState`. Enforced by `import-linter` in CI (5 contracts).
4. **`io/`, `api/`, `cli/` are the integration layers.** They may import from anything below them. Physics modules never import from these.
5. **Tests live alongside implementation.** Each subpackage has a `tests/` subdirectory. Cross-stage integration tests live in `tests/integration/`.
6. **`_schema.py` in every physics subpackage.** Each stage owns its `ParameterDef` registry. The top-level schema is assembled by `api/_param_registry.py`.
7. **Underscore-prefixed names are private.** Modules like `_schema.py`, `_inferrer.py`, `_param_registry.py`, `_helpers.py`, `_quantities.py` are package-internal — not part of the public surface and not stability-guaranteed.

---

## Subpackage Inventories

Counts below exclude `__init__.py` files. "Source" = production modules; "Tests" = `test_*.py` files. Run `find src/radiant/<pkg> -name '*.py'` for the full enumeration; this doc highlights the structure and the load-bearing modules per package.

### `core/` — 18 source + 15 tests

Foundational abstractions; no physics, no sensor knowledge. The only package physics modules may import from.

```
core/
├── constants.py         # CODATA 2018 physical constants (h, c, k_B, σ, ...)
├── units.py             # Unit conversion registry
├── parameters.py        # ParameterDef, ParameterSet, Tolerance, ConsistencyGroup
├── spectral.py          # SpectralData, SpectralDataStore
├── chain.py             # Stage Protocol, ChainState (frozen), ChainRunner
├── radiometry.py        # RadiometricFrame, NoiseTerm
├── quantity.py          # ChainQuantity, ReferenceFrame enum, signal_at, noise_at
├── regime.py            # RadiometricRegime enum (EXTENDED, POINT, SUB_PIXEL)
├── geometry.py          # spherical-Earth helpers (slant range, incidence, Euler)
├── viewing_triangle.py  # θ_o-referenced spherical-triangle solutions (ADR-0006)
├── los_geometry.py      # LineOfSightGeometry (frozen, kw_only)
├── blackbody.py         # Planck function (used by source/, atmosphere/)
├── solar.py             # Solar spectral irradiance loader
├── reflectance.py       # Reflectance descriptors
├── responsivity.py      # Detector responsivity descriptors
├── descriptors.py       # Generic descriptor base classes
├── noise_budget.py      # NoiseBudget aggregation helpers
├── exceptions.py        # RadiantError base class (Rule 15)
├── provenance.py        # run_id, git commit, dep versions, file hashing (§C13)
└── tests/               # 15 test files mirroring the source modules
```

### `geometry/` — stage 0 (ADR-0006)

```
geometry/
├── __init__.py          # GeometryStage, GeometrySpecificationError re-exports
├── _schema.py           # the geometry.* namespace (17 ParameterDefs)
├── errors.py            # GeometrySpecificationError (over/under-specification)
├── modes.py             # input-mode detection + resolution (V/S families)
├── stage.py             # GeometryStage — publishes stage_outputs["geometry"]
└── tests/               # mode matrix, stage contract, alias behavior
```

Stage 0: resolves the scene-geometry input mode and publishes LOS + derived
quantities. The θ_o-based spherical-triangle math lives in
`core/viewing_triangle.py` (core, like its η-based siblings in `core/geometry.py`).

### `source/` — 40 source + 27 tests

Stage 1: target + background spectral radiance. The largest physics package because of the spec-form fan-out (S1-S9), shape catalog, BRDF models, and converters.

Top-level: `stage.py`, `_inferrer.py` (spec-form router), `_schema.py`, `protocol.py`, plus per-spec-form modules (`emitted.py`, `reflected.py`, `combined.py`, `composite.py`, `tabulated.py`, `solar.py`, `material.py`, `shape.py`, `sub_pixel.py`, `point_source_blackbody.py`, `point_source_direct.py`, `brdf_lambertian.py`, `brdf_phong.py`).

Subpackages:
```
source/backgrounds/    # blackbody, constant, tabulated background descriptors
source/converters/     # CSV loader, brightness_temperature, radiance_temperature,
                       # reflectance, invert_band_radiance, user_intensity, user_radiance
source/resolvers/      # direct, geometry, intensity, physical, resolved_target,
                       # shape_factory, sub_pixel — pre-stage parameter resolution
source/shapes/         # box, cone, cylinder, flat_plate, sphere — projected_area
                       # implementations for sub-pixel target geometry
```

### `atmosphere/` — 12 source + 12 tests

Stage 2: τ_atm, L_path, L_atm.

```
atmosphere/
├── stage.py
├── _schema.py
├── _quantities.py       # internal radiometric helpers
├── protocol.py          # AtmosphereModel protocol
├── assembly.py          # composes selected model into stage outputs
├── loaders.py           # pre-chain model construction — Rule 6 file-I/O boundary
├── modtran.py           # MODTRAN tape7 reader + interface
├── simple.py            # Beer-Lambert / exponential model
├── exo.py               # exo-atmosphere (vacuum) — τ=1, L_path=0
├── tabulated.py         # user-supplied tabulated τ(λ) / L_path(λ)
├── interpolated.py      # spectral interpolation helpers
└── turbulence.py        # Fried r0, Cn² profile, turbulence MTF (ground only)
```

### `optics/` — 30 source + 19 tests

Stage 3: PSF (dual-path), MTF terms, throughput, EE_box, regime final. Largest package alongside `source/` and `performance/` because spatial physics (pupil → PSF → MTF) lives here.

Top-level modules group by concern:

- **Pupil + PSF (path-shared root):** `pupil_amplitude.py`, `pupil_phase.py`, `pupil_mtf.py`, `psf_mono.py`, `psf_poly.py`, `wavefront.py`, `zernike.py`, `zernike_opd.py`, `strehl.py`, `aperture.py`
- **Spatial-domain path:** `psf/` subpackage — `builder.py`, `data.py`, `effective.py` (the EffectivePSF that EE_box, RER, FWHM derive from)
- **MTF product path:** `pupil_mtf.py` (optical MTF from autocorrelation), `pixel_kernel.py`, `diffusion_kernel.py`, `sampling.py`
- **Throughput / element model:** `element.py`, `element_factories.py`, `system_transmission.py`, `transmission_modes.py`, `filters.py`, `cavity_model.py`, `stray_light.py`
- **Stage glue:** `stage.py`, `_schema.py`, `ee_box.py`, `fnumber.py`, `nearfield_irradiance.py`, `telescope.py`

### `platform/` — 6 source + 6 tests

Stage 4: smear MTF, jitter MTF, sampling, turbulence kernel.

```
platform/
├── stage.py
├── _schema.py
├── smear.py
├── jitter.py
├── sampling.py
└── turbulence_kernel.py    # spatial kernel that pairs with atmosphere turbulence MTF
```

### `spectral_integration/` — 2 source + 1 test

Stage 5: spectral → scalar (the only stage that collapses spectral arrays to per-pixel scalars; applies EE_box exactly once for point/sub-pixel regimes).

```
spectral_integration/
├── stage.py
└── _schema.py
```

### `detector/` — 14 source + 9 tests

Stage 6: QE, dark current, full well, noise terms, detector MTF.

Top-level: `stage.py`, `_schema.py`, `qe.py`, `dark_current.py`, `shot_noise.py`, `pixel.py`, `ipc.py`, `diffusion.py`.

`detector/noise/` subpackage:
```
noise/
├── budget.py             # noise budget aggregation
├── photon.py             # photon shot
├── detector_material.py  # material-specific terms (HgCdTe, InSb, Si)
├── fixed_pattern.py      # DSNU, PRNU residuals
├── roic.py               # ROIC contribution
└── other.py              # 1/f, glow, persistence, etc.
```

### `readout/` — 10 source + 8 tests

Stage 7: TDI, ADC, gain, read noise, binning, coadds, saturation.

```
readout/
├── stage.py
├── _schema.py
├── adc.py
├── read_noise.py
├── tdi_scaling.py
├── tdi_mtf.py
├── coadds.py
├── binning_onchip.py
├── binning_offchip.py
└── saturation.py
```

### `performance/` — 28 source + 16 tests

Stage 8: SNR, NEDT, NEDL, NEDR, NIIRS, GIQE, IIRS, MTF system + budget, detection range, GSD, swath, access, dynamic range, saturation. Each metric is its own module (Rule 19 — one computation, one module).

Notable modules: `stage.py`, `registry.py`, `system_mtf.py`, `mtf_budget.py`, `folded_mtf.py`, `qsample.py`, `consistency_check.py` (PSF/MTF dual-path agreement), `snr.py`, `nedt.py`, `nedl.py`, `nedr.py`, `niirs.py`, `giqe.py`, `iirs.py`, `gsd.py`, `ground_range.py`, `swath_width.py`, `access_rate.py`, `detection.py`, `detection_generic.py`, `detection_beer_lambert.py`, `dynamic_range.py`, `saturation_metrics.py`, `well_margin.py`, `adc_margin.py`, `contrast_snr.py`, `strehl.py` (wraps the optics Strehl into a metric), `turbulence_mtf_term.py`.

### `io/` — 3 source + 3 tests

I/O layer: YAML config, results container.

```
io/
├── config.py              # YAML sensor/scenario config loader → ParameterSet
├── element_config.py      # optical-element list config
└── results.py             # ChainResult: signal_at, noise_at, snr/nedt/niirs accessors
```

### `cli/` — 11 source + 1 test

Command-line interface (Click-based). Subcommand-per-file plus shared helpers.

```
cli/
├── main.py                # `radiant` entry point
├── _common.py             # shared CLI helpers
├── run.py                 # `radiant run`
├── validate.py            # `radiant validate`
├── explain.py             # `radiant explain` (param provenance)
├── compare.py             # `radiant compare` (two runs)
├── convert.py             # `radiant convert` (between config formats)
├── schema_cmd.py          # `radiant schema`
├── sweep_cmd.py           # `radiant sweep`
├── tolerance_cmd.py       # `radiant tolerance`
└── templates.py           # built-in scenario templates
```

### `api/` — 9 source + 7 tests

Public scripting API.

```
api/
├── sensor.py              # Sensor — public class (also re-exported at top level)
├── session.py             # RadiantSession — internal session orchestrator
├── sweep.py               # SweepResult, parameter sweeps
├── sensitivity.py         # finite-difference sensitivity
├── tolerance.py           # tolerance / Monte Carlo helpers
├── inspect.py             # post-run introspection helpers
├── plot.py                # plotting helpers (uses matplotlib if available)
├── units.py               # public unit-conversion helpers
└── _param_registry.py     # private — assembles the master schema
```

### `plugins/` — **removed 2026-07-06** (no longer in the tree)

`src/radiant/plugins/` no longer exists — the empty two-file stub was deleted
2026-07-06 (same day this doc was last regenerated; this row lagged the deletion).
The plugin extension system (SourcePlugin / AtmospherePlugin / MetricPlugin /
StagePlugin ABCs, entry-point discovery) is **deferred to v2** and returns as a
package only when implemented. See `docs/architecture/RADIANT_Plugins.md` (DEFERRED
banner) for the v2 design.

### `data/` — 1 source + 4 tests

Reference data accessors (solar spectra, detector libraries, scenario templates).

```
data/
└── library.py             # importlib.resources-backed access to packaged data
```

---

## Top-Level Repository Layout

```
SSR_Tool/
├── src/
│   └── radiant/                   # Package root (src layout)
│       └── ...                    # subpackages above
│
├── tests/
│   ├── test_public_api.py         # ADR-C top-level surface checks
│   ├── test_exceptions.py         # RadiantError hierarchy contract (Rule 15)
│   ├── test_provenance.py         # §C13 provenance record checks
│   └── integration/               # Cross-stage integration tests (15 files)
│       ├── fixtures/              # YAML configs + MODTRAN tape7 fixtures
│       ├── golden/                # Golden-result JSON snapshots
│       ├── snapshots/             # Per-test pytest-snapshot artifacts
│       ├── test_full_system.py
│       ├── test_chain_extended.py
│       ├── test_chain_spatial.py
│       ├── test_dual_path_mtf.py            # PSF/MTF consistency invariant
│       ├── test_golden_mwir_leo_minimal.py
│       ├── test_ground_truth_mwir.py
│       ├── test_mwir_leo_minimal.py
│       ├── test_no_atm_subcases.py
│       ├── test_option_c_anchors.py
│       ├── test_regime_continuity.py
│       ├── test_spec_form_matrix.py
│       ├── test_table_c_cells.py
│       ├── test_use_case_matrix.py
│       ├── test_use_case_shapes.py          # shape catalog × scene-type
│       └── test_use_case_warnings.py
│
├── docs/
│   ├── RADIANT_Master_Architecture.md     # the 22 non-negotiable rules
│   ├── RADIANT_Conventions.md
│   ├── RADIANT_Parameter_System.md
│   ├── RADIANT_Signal_Chain_Architecture.md
│   ├── RADIANT_File_Tree.md               # this document
│   ├── RADIANT_Source_*.md                # per-stage design docs
│   ├── RADIANT_Atmosphere.md
│   ├── RADIANT_Optics.md
│   ├── RADIANT_Spatial_Complete.md        # (being rewritten — see ADR-A)
│   ├── RADIANT_Detector.md
│   ├── RADIANT_Readout.md
│   ├── RADIANT_Performance.md
│   ├── RADIANT_IO.md
│   ├── RADIANT_API.md
│   ├── RADIANT_Scripting_API.md
│   ├── RADIANT_Plugins.md                 # v2 deferred — banner present
│   ├── RADIANT_Testing_Validation.md
│   ├── RADIANT_Target_Definition_Matrix.md
│   ├── adr/                               # ADR-A/B/C and ongoing
│   ├── archive/                           # historical RADIANT_Phase*.md
│   ├── audit_2026/                        # audit findings + reconciliation
│   ├── Cleanup_Backlog.md                 # CU tracking (R21/R22)
│   └── Reconciliation_Tasks.md            # post-audit execution plan
│
├── examples/
│   ├── mwir_leo_minimal.yaml              # smallest end-to-end scenario
│   └── ...
│
├── scenarios/                             # persona-driven worked examples
│
├── pyproject.toml                         # build config, deps, import-linter
├── README.md
├── CLAUDE.md                              # agent operating instructions
└── DEVELOPMENT.md
```

---

## File Count Summary

Numbers below exclude `__init__.py` files. Counts captured 2026-07-06.

| Subpackage             | Source | Tests | Notes |
|------------------------|--------|-------|-------|
| core/                  | 18     | 15    | foundational abstractions |
| source/                | 40     | 27    | spec-form fan-out + shape catalog |
| atmosphere/            | 12     | 12    | MODTRAN + simple + exo + tabulated + loaders |
| optics/                | 30     | 19    | dual-path PSF/MTF + element model |
| platform/              | 6      | 6     | smear, jitter, sampling, turbulence |
| spectral_integration/  | 2      | 1     | single-stage collapse |
| detector/              | 14     | 9     | includes `detector/noise/` subpackage |
| readout/               | 10     | 8     | TDI, ADC, binning, coadds |
| performance/           | 28     | 16    | one metric per module (Rule 19) |
| io/                    | 3      | 3     | config, results, element_config |
| cli/                   | 11     | 1     | subcommand-per-file |
| api/                   | 9      | 7     | public + internal session |
| **plugins/** | —  | —     | removed 2026-07-06 (v2-deferred; not in tree) |
| data/                  | 1      | 4     | packaged-data accessor |
| **Subtotal**           | **184**| **128**| 312 non-init files |
| Integration tests      | —      | 15    | `tests/integration/` |
| Top-level tests        | —      | 3     | `tests/test_public_api.py`, `tests/test_exceptions.py`, `tests/test_provenance.py` |
| **Grand total (non-init)** |    |       | **330** |

Including `__init__.py` files, total `.py` count under `src/radiant/` is 348 (36 `__init__.py`).

---

## Import Rules

Enforced by `import-linter` in CI (5 contracts in `pyproject.toml`):

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

1. `core/` → stdlib, numpy, scipy only. No other `radiant.*` imports.
2. Physics subpackages (`source/`, `atmosphere/`, `optics/`, `platform/`, `spectral_integration/`, `detector/`, `readout/`, `performance/`) → `radiant.core` only. **No cross-stage physics imports.**
3. `io/` → `radiant.core` + any physics subpackage (read-only access for schema introspection). No imports from `api/` or `cli/`.
4. `api/` → `radiant.core` + all physics subpackages + `radiant.io`. No `cli/` imports.
5. `cli/` → `radiant.api` + `radiant.io`. No direct physics imports.
6. `plugins/` (when populated for v2) → `radiant.core` only.

CI runs `import-linter --config pyproject.toml`; PRs that break a contract are blocked.

---

## Public vs. Private API

Per **ADR-C** (`docs/adr/ADR-C-public-api-surface.md`):

### Top-level package surface — minimal

`radiant.__all__` is exactly `{"Sensor", "__version__"}`. Documented usage:

```python
from radiant import Sensor

s = Sensor.from_yaml("examples/mwir_leo_minimal.yaml")
result = s.evaluate()
print(result.snr())
```

Anything else (SensorConfig, ScenarioConfig, BatchRunner, internal session) is reachable via the `radiant.api.*` submodule path but is **not** re-exported at the top level. Users who import from `radiant.api.*` accept the same stability contract as the top-level Sensor.

### Stable for plugin authors / advanced users (v2)

- `radiant.core.*` — stable abstractions; future plugin authors will compose against these.
- `radiant.io.config`, `radiant.io.results` — stable for integration scripts.

### Private — no stability guarantee

- All `_schema.py`, `_inferrer.py`, `_param_registry.py`, `_helpers.py`, `_quantities.py` files
- All stage `stage.py` modules (use `Sensor.evaluate()` / `RadiantSession.run()` instead)
- Anything under `cli/_common.py`

---

## `_schema.py` Convention

Every physics subpackage owns its parameter definitions in `_schema.py`:

```python
# source/_schema.py
from radiant.core.parameters import ParameterDef

SOURCE_PARAMS: list[ParameterDef] = [
    ParameterDef(
        name="source.target.temperature",
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

`api/_param_registry.py` assembles the master schema by importing all `*_PARAMS` lists and passing them to a single `ParameterSet`. Users never instantiate `ParameterSet` directly — `Sensor.from_yaml(...)` does it for them.

---

## Naming Conventions

- **Module files:** `snake_case.py`
- **Package-internal modules:** `_leading_underscore.py`
- **Classes:** `PascalCase`
- **Private class members:** `_leading_underscore`
- **Parameter dot-paths:** `stage.group.name` (e.g., `optics.aperture_diameter_m`, `detector.dark_rate_e_per_s`). Units are baked into the parameter name when ambiguity would otherwise arise; see `RADIANT_Parameter_System.md` for the canonical-unit rule.
- **MTF terms (`state.mtf_terms` keys):** stage prefix + effect (e.g., `optics.diffraction`, `platform.smear`, `platform.jitter`, `detector.pixel`, `detector.ipc`, `atmosphere.turbulence`).
- **Noise terms (`NoiseTerm.name`):** physics origin (e.g., `signal_shot`, `dark_shot`, `read_noise`, `quantization`).

---

## Dependencies

| Package | Role | Required |
|---------|------|----------|
| `numpy` | Array ops, spectral math | Yes |
| `scipy` | Integration, interpolation, special functions | Yes |
| `pyyaml` | YAML config loading | Yes |
| `click` | CLI framework | Yes |
| `h5py` | HDF5 output | Optional |
| `matplotlib` | Plotting (`api/plot.py`, examples) | Optional |
| `pytest` | Test runner | Dev |
| `import-linter` | Import-rule enforcement in CI | Dev |
| `mypy` | Type checking (`--strict` on `core/`, `api/`) | Dev |
| `ruff` | Format + lint | Dev |
| `hypothesis` | Property-based testing for physics | Dev |

MODTRAN itself is not a Python dependency — RADIANT wraps its file I/O via `atmosphere/modtran.py`.
