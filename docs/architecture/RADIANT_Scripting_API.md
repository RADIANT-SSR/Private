# RADIANT Scripting API

**Status:** Authoritative — rewritten 2026-07-06 post-audit. Every symbol, signature, and example in this document was verified against the code on the date of the rewrite (a full-chain run of `examples/mwir_leo_minimal.yaml` plus import/`hasattr` checks). An earlier revision (2026-04-07) documented ~25 methods that did not exist; those are now listed in Appendix A as explicitly **not implemented**.
**Depends on:** RADIANT_Signal_Chain_Architecture.md, RADIANT_Parameter_System.md, RADIANT_Config_Format.md
**Scope:** Defines the Python scripting API. This is the primary user-facing interface for trade studies, sweeps, Monte Carlo analysis, and interactive exploration. MATLAB-like simplicity is the design goal.

---

## 1. Design Philosophy

The API exposes **one primary class**: `Sensor`. Everything a user needs for trade studies lives on this object. Complexity is in the implementation, not the interface.

**Goals:**
- Load a config, set a parameter, evaluate: 3 lines of code.
- Sweep any parameter: 1 more line.
- Monte Carlo: 1 more line.
- Every intermediate result is accessible without digging into internals (`result.stage_outputs`, `result.frames`, `result.noise_terms`, `inspect_result()`).

**Non-goals:**
- Configuring stages directly (that's for plugin authors; use `radiant.core`)
- Building custom signal chains (likewise)
- Bypassing validation

`Sensor` wraps `RadiantSession` (the internal session object that owns the `ChainRunner` and the wavelength grid). Users import from `radiant` directly:

```python
from radiant import Sensor
```

The top-level `radiant` package exports exactly three symbols: `Sensor`, `RadiantError`, and `__version__`. Result and analysis types are importable from `radiant.api` (see §10) but are normally obtained from `Sensor` methods, never constructed directly.

---

## 2. `Sensor` Class

### 2.1 Construction

```python
from radiant import Sensor

# From a YAML config file (most common):
s = Sensor.from_yaml("examples/mwir_leo_minimal.yaml")

# From a nested Python dict matching the YAML structure:
s = Sensor.from_dict({
    "optics": {"aperture_diameter_m": 0.30},          # m
    "source": {"target": {"temperature": 300.0}},     # K
})

# Fresh (empty) sensor — set everything programmatically:
s = Sensor()

# Reload a sensor saved with s.save(path) — restores parameters,
# tolerances, and wavelength_points from the file's _radiant block
# (Gap 67, 2026-07-11). Plain configs load exactly as from_yaml:
s = Sensor.load("saved_sensor.yaml")
```

`from_yaml`/`from_dict` accept an optional keyword `wavelength_points` (default **500**). The spectral evaluation grid spans `spectral_integration.filter_min_um` to `spectral_integration.filter_max_um` with that many points. `Sensor.load` reads `wavelength_points` from the file's `_radiant` metadata block when present.

There is no separate `sensor=`/`scenario=` two-file loader and no `Sensor.from_configs()` fluent-builder path. See Appendix A.

### 2.2 Core Methods

The full public surface of `Sensor` (verified against `src/radiant/api/sensor.py`):

| Method | Description |
|--------|-------------|
| `Sensor.from_yaml(path, *, wavelength_points=500)` | Classmethod. Load a YAML config file. Returns a new `Sensor`. |
| `Sensor.from_dict(data, *, wavelength_points=500)` | Classmethod. Load a nested config dict. Returns a new `Sensor`. |
| `s.set(dotpath, value)` | Set a parameter by dot-path (input units). Returns `self` for chaining. |
| `s.set_many({dotpath: value, ...})` | Set multiple parameters at once. Returns `self`. |
| `s.get(dotpath)` | Get a resolved parameter value in **canonical units** (m, rad, s, K, e-). |
| `s.get_input(dotpath)` | Get a resolved parameter value in **input (display) units** (e.g., µm for pixel pitch). |
| `s.reset(dotpath)` | Remove a user-set input so the parameter reverts to its schema default (or is re-derived) on the next resolve. Returns `self`. Raises `UnknownParameterError` (a `RadiantError` that co-inherits `KeyError`, with a did-you-mean suggestion) for unknown names, like `set()` (CU-073, 2026-07-11). |
| `s.parameter_defs()` | Read-only mapping of the full parameter schema keyed by dot-path (Gap 70). Each `ParameterDef` carries dtype, canonical/input units, bounds, enum values, default, description, and tags. |
| `s.parameter_def(dotpath)` | Single `ParameterDef` lookup. Alias-aware; unknown names raise `UnknownParameterError` with a did-you-mean suggestion. |
| `s.save(path)` | Write a YAML config restoring this Sensor via `Sensor.load` (Gap 67): explicitly-set inputs (input units) plus a `_radiant` block (`wavelength_points`, tolerance distributions). Defaults and derived values are *not* written, so reloading reproduces the original resolution — including provenance splits between explicit and defaulted parameters. Returns the written `Path`. |
| `s.to_yaml(scope="inputs")` | Serialize to a YAML **string** (Gap 88 — no temp file): `"inputs"` is byte-identical in body to `save()` (explicit inputs + `_radiant` meta + `optical_elements` section) and reloads exactly; `"resolved"` writes every resolved parameter (defaults + derived) as a documentation export. |
| `Sensor.load(path)` | Classmethod. Reload a `save()`d config (or any RADIANT YAML): parameters, tolerances, `wavelength_points`. |
| `s.reset_all(scope="user_set")` | Bulk reset by provenance (Gap 93): `"user_set"` clears every interactively-set input (note: an *edited* config value reverts to its schema default, not the file value — an edit replaces provenance; reload the file to revert exactly); `"all"` clears every explicit input. Returns `self`. Backed by the new `ParameterSet.input_provenances()` read-only snapshot. |
| `s.tolerances()` / `s.clear_tolerance(dotpath)` | Read-only view of the set tolerance distributions / remove one (GT-2). Feeds the GUI ± badges + the Monte-Carlo scaffold; the same data `save`/`to_yaml` persist in `_radiant.tolerances`. |
| `s.set_tolerance(dotpath, distribution, **kwargs)` | Attach a tolerance distribution for Monte Carlo / sensitivity. Distributions: `"gaussian"`, `"uniform"`, `"truncated_gaussian"`, `"log_normal"`. Returns `self`. |
| `s.set_ground_velocity_from_orbit()` | Derive `platform.ground_velocity_m_s` from the orbital altitude `geometry.sensor_altitude_m` (circular-orbit sub-satellite ground-track speed; Gap 75). Requires the altitude set first; orbital platforms only. The ground-speed parameters are a collapsed consistency group, so this one value feeds both smear and access-rate. Returns `self`. |
| `s.evaluate(extra_stage_outputs=None)` | Run the full signal chain. Returns `ChainResult` (§3). The keyword takes one-off non-scalar pre-chain injections (Gap 68), merged over any set via `set_stage_output`. |
| `s.set_stage_output(group, key, value)` | Attach a non-scalar pre-chain input (Gap 68 interim seam) used by `evaluate` **and** all trade studies: element lists, `WavefrontError` objects, spectral curves, filter stacks — e.g. `s.set_stage_output("optics_config", "element_list", elems)`. `value=None` removes it. Carried by `clone()`, **not** written by `save()` (arbitrary objects have no YAML form; for element trains use `set_optical_elements`, which does persist). An explicitly injected `element_list` overrides an attached element document for that run. Returns `self`. |
| `s.set_optical_elements(entries, base_dir=None)` | Attach a declarative `optical_elements` **document** (ADR-0009, §2.6): the same entry dicts the YAML section carries (`RADIANT_Config_Format.md` §1.8). Validated immediately through the io parser (fail-fast — Kirchhoff checks included; ε is always derived, never an input, Rule 5); relative spectral-file references under `base_dir` are absolutized; the document is parsed onto the evaluation grid per run and injected as `optics_config.element_list` (the optics stage then runs full-prescription). Unlike raw injections, the document **is** written by `save()` and restored by `load()` (persistence parity, ADR-0009 D4). `entries=None` removes it. Returns `self`. |
| `s.optical_elements()` | The attached element document (normalized deep copy), or `None`. |
| `s.sweep(param, values, *, metric="snr", keep_results=True, n_workers=1, progress=None, cancel=None)` | 1-D parameter sweep. Returns `SweepResult` (§6.1). |
| `s.sweep_2d(param1, values1, param2, values2, *, metric="snr")` | 2-D parameter sweep. Returns `Sweep2DResult` (§6.2). |
| `s.monte_carlo(n_trials=1000, seed=42, *, metric_names=None, keep_results=False)` | Monte Carlo tolerance analysis. Returns `MonteCarloResult` (§7). |
| `s.sensitivity(*, metric="snr", param_names=None, delta_fraction=0.01)` | One-at-a-time sensitivity analysis. Returns `SensitivityResult` (§8). |
| `s.solve_for(param, target, *, bounds, metric="snr", rtol=1e-6)` | Inverse solve (Gap 10): Brent root-finding for the parameter value where *metric* equals *target* over the `bounds` bracket (input units). Returns `SolveResult` (solution, achieved, n_evaluations, full `ChainResult`). Raises `SolveBracketError` with both endpoint metric values when the target is not bracketed — note a saturated (plateaued) metric cannot be bracketed. |
| `s.clone()` | Deep copy of the Sensor (parameters, tolerances). Use before sweeps/what-ifs to keep the original unchanged. |
| `s.summary()` | Return (not print) a human-readable string of all resolved parameters, grouped by namespace, with input units and provenance tags. |
| `s.explain(dotpath=None)` | Return a string. With a dot-path: that parameter's value, units, provenance, and derivation chain. With no argument: evaluates the chain and returns a stage-by-stage walkthrough with intermediate values. |

Note the canonical-vs-input units distinction:

```python
s = Sensor.from_yaml("examples/mwir_leo_minimal.yaml")
s.get("detector.pixel_pitch_x_um")        # → 1.8e-05  (canonical: m)
s.get_input("detector.pixel_pitch_x_um")  # → 18.0     (input unit: µm)
```

Parameter names carry their input unit as a suffix (`_m`, `_um`, `_K`, `_s`, `_rad`, `_e_rms`, ...). See `docs/architecture/RADIANT_Parameter_System.md` for the full registry (129 parameters as of this rewrite).

### 2.3 Sweep

```python
sweep = s.sweep(param, values, metric="snr")
```

- `param`: dot-path string, e.g., `"optics.aperture_diameter_m"`
- `values`: list or numpy array of values to sweep (in canonical units)
- `metric`: string key looked up in `result.metrics` (§3.4), or a callable `f(ChainResult) -> float`
- `keep_results`: if `True` (default), stores the full `ChainResult` at every point (enables `sweep["other_metric"]` lookup; memory-heavy for large sweeps)
- `n_workers`: parallel workers; `1` (default) = sequential. Parallel execution falls back to sequential with a logged warning when the run function, parameter sets, **or returned results** cannot be pickled — the failure is caught both at submit time and at result time (CU-072, 2026-07-11).
- `progress` / `cancel` (Gap 72, 2026-07-11 — also on `sweep_2d`, `monte_carlo`, `sensitivity`, and `BatchRunner.run`): `progress(done, total)` is called after each completed unit of work (sweep point, grid cell, MC trial, perturbed parameter, batch cell); `cancel()` is polled before each unit and returning `True` aborts by raising `radiant.api.OperationCancelledError` (a `RadiantError` carrying `operation`, `done`, `total`). No partial result is returned on cancel. Both callbacks run on the calling thread. `solve_for` has neither (its Brent iteration count is not predictable).

Returns `SweepResult` (§6.1).

```python
sweep2d = s.sweep_2d(param1, values1, param2, values2, metric="snr")
```

Returns `Sweep2DResult` (§6.2) — a 2-D metric grid indexed `(param1, param2)`.

### 2.4 Monte Carlo

```python
mc = s.monte_carlo(n_trials=1000, seed=42)
```

Requires at least one tolerance set via `s.set_tolerance(...)` — raises `ValueError` otherwise. Each trial samples all toleranced parameters, re-resolves, re-evaluates the chain, and records all metrics (or only `metric_names` if given). Returns `MonteCarloResult` (§7).

### 2.5 Sensitivity Analysis

```python
sens = s.sensitivity(metric="snr", param_names=None, delta_fraction=0.01)
```

Perturbs each parameter by `±delta_fraction × value` (central difference) and computes the normalized elasticity `(ΔM/M)/(Δp/p)`. If `param_names` is `None`, uses the toleranced parameters; if no tolerances are set, uses all non-zero float parameters (expensive). Returns `SensitivityResult` (§8).

### 2.5b Multi-Config Comparison — `compare_configs` (Gap 79, 2026-07-16)

```python
from radiant.api import compare_configs
cmp = compare_configs([("baseline", r0), ("50 cm", r1)], baseline=0)
cmp.row("snr").deltas      # per-config value − baseline value (None where absent)
print(cmp.to_table())      # aligned text table, * marks best-per-metric
```

Takes **pre-evaluated** `(label, ChainResult)` pairs (the caller controls when chains run).
Rows cover the union of metric names with units/descriptions from the metric registry; a
metric absent from a config shows `None`, never a zero-fill. Best-per-metric marking is
conservative: higher-is-better default, NEDT/GSD/FWHM lower-is-better, flags/codes unmarked.
Raises `ComparisonError` (a `RadiantError`) on fewer than two configs or a bad baseline index.

### 2.6 Optical-Element Documents — `radiant.api.config_io` (ADR-0009, 2026-07-16)

The config-document facade: structured configuration is authored as **declarative documents**
(the `optical_elements:` entry dicts of `RADIANT_Config_Format.md` §1.8) and bridged to the io
parsers here — the GUI cannot import `radiant.io` (import contract), and validation lives in
exactly one place (`io.element_config.parse_element_entries`).

```python
from radiant.api import preview_optical_elements, normalize_element_document

entries = [
    {"name": "M1", "transfer_mode": "REFLECTIVE", "reflectance": 0.97,
     "temperature_K": 293.0, "diameter_m": 0.30, "distance_to_fpa_m": 0.9},
    {"name": "cold_filter", "transfer_mode": "REFRACTIVE", "kind": "FILTER",
     "transmittance": 0.90, "temperature_K": 240.0},
]
previews = preview_optical_elements(entries)      # no sensor, no mutation
previews[0].emissivity_mean                       # 0.03 — Kirchhoff-derived (1 − R), never an input
s.set_optical_elements(entries)                   # validate + attach; persists via s.save()
s.save("with_train.yaml"); s2 = Sensor.load("with_train.yaml")   # round-trips exactly
```

| Function | Purpose |
|----------|---------|
| `preview_optical_elements(entries, *, wavelength_um=None, base_dir=None)` | Parse a document through the real io parser and return `ElementPreview` tuples (name, kind, transfer mode, T/geometry scalars, band-mean R/T/**derived ε**, which keys referenced spectral files). Feeds the GUI import-preview dialog (ADR-0009 D5); a document that previews cleanly attaches cleanly. Band means use the 0.4–20 µm preview grid unless a band is passed. |
| `normalize_element_document(entries, *, base_dir=None)` | Validate (fail-fast) and return a deep copy with relative spectral-file references absolutized against `base_dir` — the form `Sensor.set_optical_elements` stores and `Sensor.save` writes. |

Both raise `ElementConfigError` (a `RadiantError`) with the same actionable message attach-time
parsing would produce. Errors name the element and the missing/invalid field.

R/T values in an entry may be a scalar, a spectral-CSV path, or an **inline spectral table**
(`{"wavelength_um": [...], "values": [...]}` — persists in the YAML, no external file).
Spectral inputs carrying their own grid are **resampled onto the evaluation grid** at parse
time (linear; never silently extrapolated — a run band wider than the table raises the
actionable range error). Facade validation/preview runs on each entry's native grid, so a
narrow-band coating table validates regardless of any assumed default band.

---

## 3. `ChainResult`

The object returned by `s.evaluate()` (`src/radiant/io/results.py`). It is a read-only view over the final `ChainState`.

### 3.1 Properties

| Property | Type | Description |
|----------|------|-------------|
| `result.metrics` | `Mapping[str, float]` | All computed performance metrics (§3.4). |
| `result.frames` | `Mapping[str, RadiometricFrame]` | Registered radiometric frames (§3.5). |
| `result.noise_terms` | `tuple[NoiseTerm, ...]` | All noise contributions, each with `.name` and `.value_e` (e- RMS). |
| `result.stage_outputs` | `Mapping[str, Mapping[str, Any]]` | Per-stage metadata (§3.6). |
| `result.history` | `tuple[str, ...]` | Ordered stage names that executed. |
| `result.wavelength_um` | `np.ndarray` | The common spectral grid [µm]. |
| `result.state` | `ChainState` | The underlying frozen state (advanced use, e.g., `result.state.mtf_terms`). |

### 3.2 Signal and Noise at Any Reference Frame

`signal_at` / `noise_at` express the (in-band, scalar) signal or noise at any point in the chain via backward/forward propagation through recorded transfer factors. They return a `ChainQuantity` — a small frozen object with `.value` (float), `.unit` (str), `.frame` (enum), `.name` (str).

Valid frame strings (the `ReferenceFrame` enum values): `"at_target"`, `"at_aperture"`, `"post_optics"`, `"photoelectrons"`, `"post_readout"`, `"dn"`.

> **Derived, not stored (CU-049):** for pre-integration frames (`at_target`, `at_aperture`, `post_optics`) the corresponding `result.frames[...]` object carries `in_band_value = None` — those frames are spectral-only by design (Rule 8: spectral integration happens exactly once; `RadiometricFrame` enforces spectral XOR scalar). `signal_at` is the only way to read an in-band scalar at such a frame: it derives the value by propagating the post-integration signal backward. Seeing `None` on the frame while `signal_at` returns a number is the documented contract, not an inconsistency.

```python
result = s.evaluate()

q = result.signal_at("photoelectrons")
print(f"{q.value:,.0f} {q.unit}")          # 750,264 e-

q = result.signal_at("dn")
print(f"{q.value:,.1f} {q.unit}")          # 23,445.8 DN

q = result.signal_at("at_target")
print(f"{q.value:.3f} {q.unit}")           # 1.080 W/m²/sr/µm  (band-effective)

n = result.noise_at("photoelectrons")                    # total noise (RSS)
print(f"{n.value:.1f} {n.unit} RMS")       # 866.2 e- RMS

n = result.noise_at("photoelectrons", "dark_shot")       # single term
print(f"{n.name}: {n.value:.2f} {n.unit}") # dark_shot: 0.71 e-
```

Note: these return **scalars**, not spectral arrays. For spectral data use `result.frames` (§3.5).

Noise term names in a standard run: `signal_shot`, `background_shot`, `nearfield_shot`, `straylight_shot`, `dark_shot`, `gr_noise`, `johnson_noise`, `flicker_1f`, `read_noise`, `ktc_reset`, `quantization`, `prnu`, `dsnu`, `clutter`, `persistence_noise`, `glow_shot`. (Which terms are non-zero depends on the detector noise regime and scenario.)

A `ChainQuantity` can also be re-expressed at another frame explicitly:

```python
from radiant.core.quantity import ReferenceFrame
q_dn = result.signal_at("photoelectrons").to(ReferenceFrame.DN, result.state)
```

**Deprecated aliases:** `result.signal_at_frame(...)` and `result.noise_at_frame(...)` still work but issue `DeprecationWarning` and will be removed in RADIANT 0.2.0. Use `signal_at` / `noise_at`.

### 3.3 Metric Convenience Accessors

Exactly three metric accessors exist as methods; each raises `KeyError` if the metric was not computed for the run (inspect `result.metrics` to see what was):

```python
result.snr()      # float, dimensionless      — reads metrics["snr"]
result.nedt()     # float, kelvin             — reads metrics["nedt_K"]
result.niirs()    # float, NIIRS scale        — reads metrics["niirs"]
```

There are **no** `detection_range()`, `rer()`, `gsd()`, `mtf_at_nyquist()`, `mtf_curve()`, or `noise_budget()` methods. RER, GSD, and MTF-at-Nyquist are plain keys in `result.metrics` (§3.4); the noise budget is `result.noise_terms`; MTF curves live in `result.state.mtf_terms` (§3.7).

**Full-well saturation status (CU-101).** `result.well_status()` returns a `WellStatus` record (importable as `radiant.api.WellStatus`) surfacing the readout stage's well-capacity clip decision so a GUI banner (or script) reads a first-class result instead of digging into `stage_outputs["readout"]`. It carries the clip state plus the supporting well-charge numbers, each with its unit documented on the dataclass:

```python
ws = result.well_status()
ws.status                # "ok" | "clipped" — equals stage_outputs["readout"]["well_status"]
ws.is_saturated          # bool — True iff status == "clipped"
ws.fill_fraction         # dimensionless — total_well_e / full_well_capacity_e (> 1.0 iff clipped)
ws.total_well_e          # e- — accumulated well charge before clipping
ws.full_well_capacity_e  # e- — readout.full_well_capacity_e
```

`"clipped"` means the accumulated well charge exceeded `full_well_capacity_e` and the signal was hard-clipped; downstream SNR/NEDT/NIIRS then reflect the clipped signal and stop responding to scene/atmosphere changes (the silent-clip trap of Gap 65). Raises `KeyError` if the readout stage did not run for this result (mirrors `snr()`). The values live in `stage_outputs` so they survive `save()`/`load()`. This is a status accessor, not a metric — `well_status` is not in `result.metrics`.

### 3.4 Performance Metrics (`result.metrics`)

`result.metrics` is the bare name → float mapping. For unit-labelled access — the project hard rule for anything displayed — use `result.metric_records()` (Gap 71, 2026-07-11): a tuple of `MetricRecord(name, value, unit, description, kind)` sorted by name, joined from the metric registry (`RADIANT_Metrics.md` §6). `kind` distinguishes physical floats from 0/1 flags (`niirs_extrapolated`) and enum codes (`sampling_regime_code`). Single-metric metadata: `radiant.performance.metric_info(name)`.

Keys observed in a standard extended-scene run (`examples/mwir_leo_minimal.yaml`); presence is scenario-dependent:

| Key | Unit | Meaning |
|-----|------|---------|
| `snr` | — | Signal-to-noise ratio |
| `contrast_snr` | — | Contrast SNR (target − background) |
| `nedt_K` | K | Noise-equivalent delta temperature |
| `niirs` | — | GIQE-based NIIRS rating |
| `gsd_cross_track_m`, `gsd_along_track_m`, `gsd_geometric_mean_m` | m | Ground sample distance |
| `ground_range_m` | m | Ground range to target |
| `rer` | — | Relative edge response (GIQE input) |
| `ee_1x1`, `ee_3x3` | — | Ensquared energy in 1×1 / 3×3 pixel box, from the degraded PSF |
| `fwhm_x_m`, `fwhm_y_m` | m | PSF full width at half maximum (focal plane) |
| `strehl` | — | **PSF-derived** Strehl ratio: degraded-PSF peak over the diffraction-limited reference-PSF peak (Rule 4 path) |
| `strehl_marechal` | — | Analytic Maréchal approximation — a small-aberration **diagnostic**, not the reported Strehl |
| `mtf_at_nyquist` | — | System MTF at Nyquist (PSF-path) |
| `mtf_system_at_nyquist_x`, `mtf_system_at_nyquist_y` | — | System MTF at Nyquist from the MTF-product budget |
| `mtf_folded_at_nyquist`, `alias_fraction_at_nyquist` | — | Aliasing diagnostics |
| `q_center`, `q_min`, `q_max` | — | Detector sampling Q over the band |
| `diffraction_limit_angular_urad` | µrad | Rayleigh angular resolution `1.22 λ_c / D` (optics-only floor) |
| `diffraction_limit_ground_m` | m | Rayleigh resolution projected to the ground at the slant range (companion to GSD; requires altitude) |
| `sampling_regime_code` | — | 0 = detector-limited (Q<1), 1 = near-critical (1≤Q≤2), 2 = diffraction-limited (Q>2), from `q_center` |
| `mrt_at_nyquist_K` | K | Minimum resolvable temperature at Nyquist = k·NETD/MTF_Nyq (contrast-limited resolution; requires NEDT + MTF) |
| `well_margin_dB`, `adc_margin_dB`, `dynamic_range_dB` | dB | Saturation and dynamic-range margins |
| `swath_width_m`, `access_rate_m2_s` | m, m²/s | Scenario-dependent (require ground-speed / swath geometry inputs) |

```python
result = s.evaluate()
result.metrics["snr"]          # 866.1  (dimensionless)
result.metrics["nedt_K"]       # 0.0307 K  (= 30.7 mK)
result.metrics["gsd_geometric_mean_m"]   # 0.12 m
```

**Strehl note (2026-07):** `metrics["strehl"]` is computed from the actual degraded `EffectivePSF` against the diffraction-limited reference PSF built from the same pupil. `metrics["strehl_marechal"]` is the analytic `exp(-(2π·WFE)²)` diagnostic. When comparing against WFE budgets, use `strehl`; `strehl_marechal` is only a cross-check.

### 3.5 Radiometric Frames (`result.frames`)

Frames registered in a standard run: `at_source_target`, `at_aperture`, `at_aperture_target`, `post_optics`, `photoelectrons` (plus `at_source_background` / `at_aperture_background` when a background descriptor is present). `at_source_target` / `at_source_background` are the **pre-atmosphere** source emission (`L_source`); `at_aperture*` are the **post-atmosphere** at-aperture radiances (Gap 91). Each `RadiometricFrame` has:

- `.name` — frame name
- `.wavelength_um` — spectral grid [µm]
- `.spectral_radiance` — L(λ) [W/m²/sr/µm] (or `None` for scalar frames)
- `.spectral_irradiance` — E(λ) [W/m²/µm] (where applicable)
- `.photon_rate` — [photon/s] (where applicable)
- `.in_band_value`, `.in_band_unit` — band-integrated scalar (where applicable)
- `.notes` — free-text provenance

```python
frame = result.frames["at_aperture"]
frame.wavelength_um        # ndarray shape (500,), 3.5–5.0 µm
frame.spectral_radiance    # ndarray [W/m²/sr/µm]
```

### 3.6 Stage Outputs (`result.stage_outputs`)

Every stage publishes named intermediate values. Keys observed in a standard run:

| Stage | Selected keys |
|-------|---------------|
| `source` | `regime_tentative`, `fill_fraction`, `projected_area_m2`, `range_m`, `angular_extent_rad`, `target`, `background` |
| `atmosphere` | `tau_atm`, `L_path`, `E_sky_thermal`, `E_sky_scattered` |
| `optics` | `regime` (final — Rule 10), `A_collect` [m²], `Omega_pixel` [sr], `tau_opt`, `effective_psf`, `reference_psf`, `wavefront_error`, `stray_light_irradiance_at_fpa`, `pupil_amplitude` [transmission], `pupil_phase_waves` [waves], `pupil_wavelength_um` [µm], `pupil_plane_extent_m` [m] (Gap 89) |
| `platform` | `EE_box`, `effective_psf` (fully degraded), `jitter_sigma_x_m`, `jitter_sigma_y_m`, `smear_width_m` |
| `spectral_integration` | `signal_e`, `background_e`, `contrast_e`, `e_rate_per_s`, `qe_scalar` |
| `detector` | `signal_e`, `background_e`, `dark_e`, `noise_budget_raw` |
| `readout` | `signal_e_final`, `signal_dn_final`, `sigma_total_e`, `well_status`, `well_fill_fraction`, `total_well_e` [e-], `full_well_capacity_e` [e-], `adc_status`, `noise_regime` |
| `performance` | `mtf_budget`, `mtf_x`, `mtf_y`, `folded_mtf_x`, `snr_result`, `nedt_result`, `niirs_result`, `dual_path_consistency` |

**EE_box note (2026-07):** the ensquared-energy coupling factor is computed in **PlatformStage** from the fully degraded PSF (optics × jitter × smear × turbulence) and published as `stage_outputs["platform"]["EE_box"]`. It is applied exactly once, in `SpectralIntegrationStage`, only for point-source and sub-pixel regimes (Rule 9). For extended scenes `EE_box = 1.0` and it is not applied.

```python
result.stage_outputs["optics"]["regime"]        # RadiometricRegime.EXTENDED
result.stage_outputs["optics"]["A_collect"]     # 0.0707 m²
result.stage_outputs["platform"]["EE_box"]      # 1.0 (extended scene)
```

`stage_outputs` keys carry **no stability guarantee** (§11) — prefer `metrics` and the documented accessors where possible.

**Display units (`radiant.api.stage_output_units`).** Stage outputs are computed values, not parameters, so they carry no per-field unit metadata. For a renderer that must label each scalar with its canonical unit (the R-UNITS rule — every displayed numeric carries its unit), `stage_output_unit(stage, key) -> str` returns the canonical unit string for a scalar output (`"m²"` for `optics.A_collect`, `"sr"` for `optics.Omega_pixel`, `"e-/s"` for `spectral_integration.e_rate_per_s`, …), `""` for a genuinely dimensionless numeric (a fraction such as `platform.EE_box`), and `""` for any key not in the table (honest — a bare number, never a guessed unit). The full table is `STAGE_OUTPUT_UNITS`. This is display metadata only (Rule 2 — no unit arithmetic). The GUI's per-stage Outputs readout reads it; the longer-term fix is per-stage output-unit declaration (CU-118, aligned with Gap 87).

```python
from radiant.api.stage_output_units import stage_output_unit
stage_output_unit("optics", "A_collect")   # "m²"
stage_output_unit("optics", "Omega_pixel")  # "sr"
stage_output_unit("platform", "EE_box")     # "" (dimensionless fraction)
```

### 3.7 MTF Terms

Per-axis MTF contributor arrays live on the state:

```python
dict(result.state.mtf_terms).keys()
# mtf_optics_x/y, mtf_pixel_aperture_x/y, mtf_jitter_x/y, mtf_smear_x/y,
# mtf_charge_diffusion_x/y, mtf_ipc_x/y, mtf_tdi_x/y

freq = result.state.spatial_freq_cycles_per_mrad   # ndarray [cycles/mrad]
```

The assembled per-axis system MTF and frequency axes are in `stage_outputs["performance"]` (`mtf_x`, `mtf_y`, `mtf_freq_x`, `mtf_freq_y`, `mtf_budget`).

### 3.8 Provenance

```python
record = result.to_provenance_record()   # JSON-serialisable dict
```

Keys: `run_id` (UUID4), `radiant_version`, `git_commit`, `python_version`, `dependency_versions`, `parameter_set` (every resolved parameter with value, units, provenance), `input_file_hashes` (SHA-256 of every loaded config file), `active_models` (stage names that ran). Serialize it yourself:

```python
import json
with open("run_provenance.json", "w") as f:
    json.dump(result.to_provenance_record(), f, indent=2)
```

`result.to_records()` returns metrics as plain dicts (name/value/unit/description) and `result.to_csv(path)` writes them as CSV (Gap 88, 2026-07-16); `SweepResult` / `Sweep2DResult` / `MonteCarloResult` carry matching `to_csv`. There is still no `result.to_json()` (the `.radiant` archive in §3.9 is the full-fidelity persistence).

### 3.9 Persistence (Gap 67, 2026-07-11)

```python
result.save("run.radiant")            # single-file zip archive
r2 = ChainResult.load("run.radiant")  # full-fidelity reload
```

The archive (zip: `manifest.json` + `arrays.npz`) holds the complete `ChainState` — frames, noise terms, stage outputs, MTF terms, metrics, history — plus the provenance record **frozen at save time**: `r2.to_provenance_record()` reports the run that produced the archive (original `run_id`, versions, git commit, parameters), never the loading environment. All accessors work on the reloaded result, including `signal_at`/`noise_at`.

Fidelity contract: JSON primitives, non-finite floats, dtype-preserving numpy arrays, tuples vs lists, str-keyed mappings, and radiant-defined enums/dataclasses all round-trip exactly; for the shipped chain **nothing is skipped** (enforced by `tests/integration/test_persistence_roundtrip.py`). A value the codec cannot encode (e.g. injected by a custom script) is listed in the manifest with a `UserWarning` at save time and reloads as an `UnserializedValue` placeholder — never silently dropped. Reload instantiates only `radiant.*` classes and reads arrays with `allow_pickle=False`; unlike pickle there is no arbitrary-code path. A reloaded result has no attached `ParameterSet` (resolved parameters live in the provenance record). Archives embedding full-resolution PSFs run tens of MB.

---

### 3.10 Inspect + Explain Accessors (Gap 87, 2026-07-17)

```python
print(result.inspect())            # the full readable tree (== inspect_result(result))
print(result.inspect("optics"))    # one stage's outputs
exp = result.explain_noise("dark_shot")
exp.value_e, exp.origin_frame, exp.physical_basis, exp.share_of_variance
print(exp.description)             # rendered text incl. units + variance share
```

`explain_noise` returns a structured `NoiseExplanation` (name, σ in e- RMS at the origin
frame, mechanism tag, budgets, **share of total variance** — the pie fraction, shares sum to
1); unknown terms raise `KeyError` naming the available set. The GUI Variables/Noise surfaces
can now consume these instead of their Gap-87 workarounds (adoption tracked separately).

## 4. Inspection

### 4.1 `inspect_result()` — tree view

```python
from radiant.api.inspect import inspect_result

result = s.evaluate()
print(inspect_result(result))            # full tree: metrics, noise, MTF, frames, stages
print(inspect_result(result, "optics"))  # single stage
```

`inspect_result` returns a formatted string (metrics, noise terms in e- RMS, MTF term summaries, frame names, and every stage output). There is no `result.inspect()` method and no interactive widget (Appendix A).

### 4.2 `Sensor.summary()` and `Sensor.explain()`

```python
print(s.summary())
# RADIANT Sensor — Parameter Summary
# [optics]
#   optics.aperture_diameter_m = 0.3 m  [config_file]
#   optics.f_number = 4.0  [derived]
#   ...

print(s.explain("optics.f_number"))
# optics.f_number = 4.0  (canonical: 4.0)
#   Description: Dimensionless f/# = focal_length_m / aperture_diameter_m. ...
#   Provenance: derived
#   Source: derived: f_number = focal_length_m / aperture_diameter_m
#   Derived from:
#     optics.aperture_diameter_m = 0.3
#     optics.focal_length_m = 1.2

print(s.explain())   # no argument: evaluates and prints a full chain walkthrough
```

Both return strings — `print()` them.

---

## 5. Plotting

matplotlib is an **optional** dependency; all plot helpers import it lazily and raise a clear `ImportError` if missing. Everything returns a `matplotlib.figure.Figure` — call `.savefig(...)` on it. Every returned figure uses matplotlib **constrained layout** (`plt.subplots(constrained_layout=True)`), so titles, axis labels, and legends always keep a reserved margin and re-fit when the figure is resized (e.g. embedded in a GUI canvas) — no clipped titles on `savefig` or on window resize.

Axis labels use the **symbol + unit** form (e.g. `τ_atm (dimensionless)`, `L_path (W/m²/sr/µm)`, `Radiance (W/m²/sr/µm)`), never a spelled-out descriptive phrase — the unit is always retained (R-UNITS), but the long spelled-out prefix that overflowed a narrow embedded twin-axis pane is dropped.

### 5.1 Module functions — `radiant.api.plot`

```python
from radiant.api.plot import (
    plot_sweep,          # SweepResult → metric-vs-param line plot
    plot_sweep_2d,       # Sweep2DResult → filled contour
    plot_noise_budget,   # tuple of NoiseTerm → horizontal bar chart [e- RMS]
    plot_psf,            # EffectivePSF → log-scaled 2-D image
    plot_mtf_terms,      # {name: MTF array}, freq axis → all terms on one axis (see legend note)
    plot_spectral,       # wavelength [µm], radiance → spectral line plot
    plot_spectral_multi, # wavelength [µm], {label: radiance} → multi-curve spectral plot
    plot_atmosphere_spectral,  # wavelength [µm], τ_atm, L_path → twin-axis spectral plot
)

fig = plot_sweep(sweep)
fig.savefig("snr_vs_aperture.png")

frame = result.frames["at_aperture"]
fig = plot_spectral(frame.wavelength_um, frame.spectral_radiance,
                    title="At-aperture spectral radiance")
```

**`plot_mtf_terms` legend (CU-117).** A contributor's along-track (`_x`) and cross-track
(`_y`) curves are merged into **one** legend entry when they coincide (drawn as a single
representative line), so a full 8-contributor × x/y overlay shows ~8 labels instead of 16;
`_x`/`_y` that visibly differ keep both curves and both labels (a real anisotropy is never
hidden). The legend is placed **below** the axes in a compact multi-column block (not inside
the axes), so it never covers the curves in a narrow embedded pane. All contributor curves
are always plotted — only the labelling is de-densified.

### 5.2 Result plot namespace — `ResultPlotNamespace`

A thin convenience wrapper around the same functions:

```python
from radiant.api.inspect import ResultPlotNamespace

plots = ResultPlotNamespace(result)
plots.psf()                # 2-D effective PSF (from stage_outputs["optics"]["effective_psf"])
plots.psf_pixel_grid()     # psf() + the detector pixel grid overlaid, cropped to the PSF core
plots.pupil_amplitude()    # 2-D pupil apodization/amplitude map [transmission, dimensionless] (Gap 89)
plots.pupil_phase()        # 2-D pupil wavefront-error map [waves] (Gap 89)
plots.noise_budget()       # horizontal bar chart of result.noise_terms [e- RMS]
plots.noise_pie()          # pie of result.noise_terms by VARIANCE share (σ_i²; e- RMS on labels)
plots.mtf()                # all MTF terms vs spatial frequency [cycles/mrad]
plots.mtf_budget()         # per-contributor MTF-at-Nyquist bar chart (Gap 19)
plots.spectral_source()          # target (+ background) at-aperture radiance vs λ [W/m²/sr/µm]
plots.spectral_source_emission() # target (+ background) PRE-atmosphere source radiance vs λ [W/m²/sr/µm]
plots.spectral_atmosphere()      # τ_atm(λ) [dimensionless] + L_path(λ) [W/m²/sr/µm] on twin axes
plots.spectral_inband()          # band-filtered post-optics radiance vs λ [W/m²/sr/µm]
plots.optical_throughput()       # system τ_opt(λ) vs λ [dimensionless] (Gap 90)
plots.coating_spectra()          # per-element R / T / ε vs λ [dimensionless] (Gap 90)
```

The spectral accessors (Gap 86, Gap 91) plot **only** real stored arrays, no
recomputation:

| Accessor | Source | Notes |
|----------|--------|-------|
| `spectral_source()` | `frames["at_aperture_target"]` (falls back to `at_aperture`) + optional `frames["at_aperture_background"]` | The **at-aperture** (post-atmosphere) radiance — earliest stored radiance conflating source + atmosphere. |
| `spectral_source_emission()` | `frames["at_source_target"]` + optional `frames["at_source_background"]` | Gap 91 — the **pre-atmosphere** emitted+reflected radiance *leaving the source* (`L_source`), before the up-leg τ/L_path. AtmosphereStage persists it; `at_aperture_target ≈ τ_up · at_source_target + L_path_up`. Isolates what the target emits from what reaches the aperture. |
| `spectral_atmosphere()` | `stage_outputs["atmosphere"]["tau_atm"]` + `["L_path"]` | Twin, unit-labelled y-axes (τ is dimensionless; L_path is W/m²/sr/µm). |
| `spectral_inband()` | `frames["post_optics"]` | The band-filtered at-FPA radiance SpectralIntegrationStage integrates; the collapsed in-band scalar is a single value, not a spectrum. |

The optics coating accessors (Gap 90) plot the stored optics `SpectralData`
verbatim — no physics, no recomputation:

| Accessor | Source | Notes |
|----------|--------|-------|
| `optical_throughput()` | `stage_outputs["optics"]["tau_opt_spectral"]` | The assembled **system** transmission τ_opt(λ) [dimensionless] — product of every element's net throughput — on its own wavelength grid; y-axis bounded [0, 1.05]. |
| `coating_spectra()` | `stage_outputs["optics"]["elements"]` | One overlaid curve per element × quantity: reflectance R, transmittance T, and Kirchhoff-derived emissivity ε (`element.emissivity`; ε = 1 − R for mirrors, declared train ε for lumped, 0 for simple refractives) — all dimensionless, one y-axis. A curve that is identically zero is omitted (a mirror shows R + ε only; a simple refractive shows T + R only). Each curve carries its own wavelength grid. |

The pupil accessors (Gap 89) render the two diagnostic faces of the **same
complex pupil** OpticsStage builds for the MTF autocorrelation — both are stored
verbatim, no recomputation (Rule 4's pupil→MTF path is untouched):

| Accessor | Source | Notes |
|----------|--------|-------|
| `pupil_amplitude()` | `stage_outputs["optics"]["pupil_amplitude"]` | Dimensionless transmission mask across the pupil — central obscuration, spider vanes, and any measured `pupil_mask_override` included. Colorbar "transmission (dimensionless)". |
| `pupil_phase()` | `stage_outputs["optics"]["pupil_phase_waves"]` | Wavefront error in **waves** (`phase_radians / 2π`) at `stage_outputs["optics"]["pupil_wavelength_um"]`, zero outside the clear aperture. Band centre for polychromatic runs. Colorbar "wavefront error (waves)"; symmetric diverging colormap so an unaberrated pupil renders flat. |

Axes are scaled to `stage_outputs["optics"]["pupil_plane_extent_m"]` (physical
pupil diameter) when present, else labelled in sample indices. `pupil_phase()`
raises when no pupil-phase representation exists (a WFE mode such as `opd_map`);
`pupil_amplitude` is still persisted in that case.

Each raises `ApiValidationError` (an actionable `ValueError` subclass) when the
required frame or stage output is absent, rather than drawing a blank figure.

There is **no** `result.plot` attribute on `ChainResult` — construct the namespace explicitly (or call the module functions). The previously documented `result.plot.snr_breakdown()`, `.spectral_all()`, `.ee_curve()`, `.transmission()` do not exist (Appendix A).

---

## 6. `SweepResult` and `Sweep2DResult`

Both are frozen dataclasses in `radiant.api.sweep`.

### 6.1 SweepResult

```python
import numpy as np
s = Sensor.from_yaml("examples/mwir_leo_minimal.yaml")
sweep = s.sweep("optics.aperture_diameter_m", np.linspace(0.10, 0.60, 21), metric="snr")

# Attributes:
sweep.param_name       # "optics.aperture_diameter_m"
sweep.values           # ndarray of swept values [m]
sweep.metric_values    # ndarray of metric values (dimensionless SNR here)
sweep.metric_name      # "snr"
sweep.results          # tuple[ChainResult, ...] (empty if keep_results=False)

# Any other metric across the sweep (requires keep_results=True):
sweep["nedt_K"]        # ndarray [K] — raises KeyError if results were not kept

# First point where metric >= threshold (returns None if never exceeded):
sweep.at_metric_threshold(800.0)
# → (0.30, 866.1)  — (aperture diameter [m], SNR [-])

# Plot / export:
from radiant.api.plot import plot_sweep
fig = plot_sweep(sweep)

import pandas as pd
df = pd.DataFrame({"aperture_diameter_m": sweep.values,
                   "snr": sweep.metric_values,
                   "nedt_K": sweep["nedt_K"]})
df.to_csv("aperture_sweep.csv", index=False)
```

`SweepResult` has **no** `.plot()`, `.to_dataframe()`, or `.to_csv()` methods, and `at_metric_threshold` has no `from_above=` argument — it finds the first crossing from below only. Build DataFrames yourself as above.

### 6.2 Sweep2DResult

```python
sweep2d = s.sweep_2d(
    "optics.aperture_diameter_m",            np.linspace(0.15, 0.60, 10),   # m
    "spectral_integration.integration_time_s", np.array([0.002, 0.005, 0.010, 0.020]),  # s
    metric="snr",
)

# Attributes:
sweep2d.param1_name, sweep2d.param2_name
sweep2d.values1        # ndarray, axis 1 [m]
sweep2d.values2        # ndarray, axis 2 [s]
sweep2d.grid           # 2-D ndarray, shape (10, 4) — SNR [-]
sweep2d.metric_name    # "snr"

from radiant.api.plot import plot_sweep_2d
fig = plot_sweep_2d(sweep2d, levels=[200, 400, 600, 800, 1000])
```

There is no `sweep2d.plot.*` namespace and no `.to_dataframe()`.

---

## 7. `MonteCarloResult`

Frozen dataclass in `radiant.api.tolerance`.

```python
s = Sensor.from_yaml("examples/mwir_leo_minimal.yaml")

# Tolerances (all distribution parameters in canonical units):
s.set_tolerance("detector.qe_value",            "gaussian", std=0.03)
s.set_tolerance("optics.aperture_diameter_m",   "gaussian", std=0.003)     # ±3 mm
s.set_tolerance("detector.detector_temperature_K", "uniform", low=78.0, high=82.0)  # K

mc = s.monte_carlo(n_trials=1000, seed=42)

# Attributes:
mc.n_trials            # 1000
mc.seed                # 42
mc.metric_names        # tuple of recorded metric keys (all of result.metrics by default)
mc.metric_array        # ndarray (n_trials, n_metrics)
mc.sampled_params      # {param_name: ndarray of sampled values per trial}
mc.results             # tuple[ChainResult, ...] (empty unless keep_results=True)

# Statistical summaries (NaN-tolerant):
mc.mean("snr")                              # float [-]
mc.std("snr")                               # float [-] (ddof=1)
mc.percentile("snr", 5.0)                   # P5
mc.percentile("snr", 95.0)                  # P95
mc.probability_of_exceeding("snr", 800.0)   # fraction of trials with SNR ≥ 800
mc.correlation("snr")                       # {param_name: Pearson r} — ranks drivers
mc.to_dict()                                # {metric_name: 1-D trial array}
```

Plot distributions with matplotlib directly — there is no `mc.plot.*` namespace:

```python
import matplotlib.pyplot as plt
snr_trials = mc.to_dict()["snr"]            # ndarray [-]
plt.hist(snr_trials, bins=50)
plt.xlabel("SNR (-)"); plt.ylabel("Trials")
```

---

## 8. `SensitivityResult`

Frozen dataclass in `radiant.api.sensitivity`. Entries are sorted by absolute sensitivity, descending.

```python
sens = s.sensitivity(
    metric="snr",
    param_names=["optics.aperture_diameter_m", "detector.qe_value"],
    delta_fraction=0.01,                       # ±1% perturbation
)

sens.metric_name       # "snr"
sens.param_names       # tuple of dot-paths, ranked
sens.sensitivities     # ndarray of normalized elasticities (ΔM/M)/(Δp/p) [-]
sens.to_dict()         # {param_name: sensitivity}

for e in sens.entries: # SensitivityEntry objects
    print(f"{e.param_name}: S = {e.sensitivity:+.3f}  "
          f"(nominal = {e.nominal_value:g}, metric {e.metric_minus:.1f} → {e.metric_plus:.1f})")
# optics.aperture_diameter_m: S = +1.000  (extended scene: SNR ∝ D)
# detector.qe_value:          S = +0.500  (shot-limited: SNR ∝ √QE)
```

Each `SensitivityEntry` carries: `param_name`, `nominal_value`, `metric_nominal`, `metric_plus`, `metric_minus`, `sensitivity`, `delta_fraction`. There is no `sens.table()` or `sens.plot.*` (Appendix A) — format `entries` yourself.

---

## 9. Usage Examples

All examples below were executed against `examples/mwir_leo_minimal.yaml` (0.30 m aperture, f/4, 18 µm pixels, MWIR 3.5–5.0 µm, 5 ms integration, 300 K extended scene at 8 km) on 2026-07-06. Numbers shown are the actual outputs.

### Example 1: Single evaluation, read out key metrics

```python
from radiant import Sensor

s = Sensor.from_yaml("examples/mwir_leo_minimal.yaml")
result = s.evaluate()

print(f"SNR   = {result.snr():.1f} (-)")                              # SNR   = 866.1 (-)
print(f"NEDT  = {result.nedt() * 1e3:.1f} mK")                        # NEDT  = 30.7 mK
print(f"NIIRS = {result.niirs():.2f}")                                # NIIRS = 10.83
print(f"GSD   = {result.metrics['gsd_geometric_mean_m']:.2f} m")      # GSD   = 0.12 m
```

### Example 2: Override parameters and re-evaluate

```python
s = Sensor.from_yaml("examples/mwir_leo_minimal.yaml")
s.set("optics.aperture_diameter_m", 0.45)      # m
s.set("source.target.temperature", 320.0)      # K

result = s.evaluate()
print(f"SNR = {result.snr():.1f} (-)")
```

`set()` returns `self`, so calls chain: `s.set(...).set(...)`. Or use `set_many`:

```python
s.set_many({
    "optics.aperture_diameter_m": 0.45,        # m
    "source.target.temperature": 320.0,        # K
})
```

### Example 3: Aperture trade — SNR vs. aperture diameter

```python
import numpy as np
import matplotlib.pyplot as plt
from radiant import Sensor
from radiant.api.plot import plot_sweep

s = Sensor.from_yaml("examples/mwir_leo_minimal.yaml")
sweep = s.sweep("optics.aperture_diameter_m", np.linspace(0.10, 0.60, 26), metric="snr")

fig = plot_sweep(sweep)
ax = fig.axes[0]
ax.axhline(800.0, color="red", linestyle="--", label="SNR requirement (-)")
ax.legend()
fig.savefig("snr_vs_aperture.png")

hit = sweep.at_metric_threshold(800.0)
if hit is not None:
    print(f"Minimum aperture for SNR ≥ 800: {hit[0]:.2f} m (SNR = {hit[1]:.1f})")
# → Minimum aperture for SNR ≥ 800: 0.30 m (SNR = 866.1)
```

### Example 4: Multi-metric sweep export

```python
import numpy as np, pandas as pd
from radiant import Sensor

s = Sensor.from_yaml("examples/mwir_leo_minimal.yaml")
sweep = s.sweep("optics.aperture_diameter_m", np.linspace(0.10, 0.60, 26))  # keep_results=True

pd.DataFrame({
    "aperture_diameter_m": sweep.values,       # m
    "snr":     sweep["snr"],                   # -
    "nedt_K":  sweep["nedt_K"],                # K
    "niirs":   sweep["niirs"],                 # -
}).to_csv("aperture_trade.csv", index=False)
```

### Example 5: 2-D sweep — SNR vs. aperture and integration time

```python
import numpy as np
from radiant import Sensor
from radiant.api.plot import plot_sweep_2d

s = Sensor.from_yaml("examples/mwir_leo_minimal.yaml")
sweep2d = s.sweep_2d(
    "optics.aperture_diameter_m",              np.linspace(0.15, 0.50, 8),    # m
    "spectral_integration.integration_time_s", np.array([0.002, 0.005, 0.010, 0.020]),  # s
    metric="snr",
)
fig = plot_sweep_2d(sweep2d)
fig.savefig("snr_aperture_tint.png")
# Spot check: D = 0.20 m, t_int = 2 ms → SNR = 365.1; D = 0.40 m, t_int = 10 ms → SNR = 1414.2
```

### Example 6: NEDT vs. detector temperature (detector engineer workflow)

```python
import numpy as np
from radiant import Sensor
from radiant.api.plot import plot_sweep

s = Sensor.from_yaml("examples/mwir_leo_minimal.yaml")
s.set("detector.dark_activation_energy_eV", 0.23)     # eV — ~Eg for 5 µm cutoff HgCdTe
s.set("detector.dark_reference_temperature_K", 80.0)  # K  — dark_rate_e_per_s quoted at 80 K

temps_K = np.arange(70.0, 131.0, 10.0)                # K
sweep = s.sweep("detector.detector_temperature_K", temps_K, metric="nedt_K")
fig = plot_sweep(sweep)     # y-axis: NEDT [K]
# Verified output: 30.7 mK flat from 70–100 K, then 30.8 / 31.4 / 34.3 mK at
# 110 / 120 / 130 K — the knee where Arrhenius dark shot noise starts competing
# with photon shot noise in this bright extended MWIR scene.
#
# Regime note: the schema default detector.dark_activation_energy_eV = 0 eV
# disables temperature scaling entirely (dark rate is then constant at
# detector.dark_rate_e_per_s), so sweeping temperature without setting the
# activation energy produces a perfectly flat NEDT curve.
```

### Example 7: Noise budget breakdown

```python
from radiant import Sensor
from radiant.api.inspect import ResultPlotNamespace

s = Sensor.from_yaml("examples/mwir_leo_minimal.yaml")
result = s.evaluate()

total = result.noise_at("photoelectrons")
print(f"Total noise: {total.value:.1f} {total.unit} RMS")     # Total noise: 866.2 e- RMS
for nt in sorted(result.noise_terms, key=lambda t: -t.value_e):
    print(f"  {nt.name:20s} {nt.value_e:10.2f} e- RMS")

ResultPlotNamespace(result).noise_budget()     # horizontal bar chart [e- RMS]
ResultPlotNamespace(result).noise_pie()        # pie by variance share (σ_i²; e- RMS on labels)
```

### Example 8: Spectral data at chain frames

```python
import matplotlib.pyplot as plt
from radiant import Sensor

s = Sensor.from_yaml("examples/mwir_leo_minimal.yaml")
result = s.evaluate()

fig, ax = plt.subplots()
for name in ["at_aperture", "post_optics"]:
    frame = result.frames[name]
    ax.plot(frame.wavelength_um, frame.spectral_radiance, label=name)
ax.set_xlabel("Wavelength (µm)")
ax.set_ylabel("Spectral radiance (W/m²/sr/µm)")
ax.legend()
```

### Example 9: MTF budget

```python
from radiant import Sensor
from radiant.api.inspect import ResultPlotNamespace

s = Sensor.from_yaml("examples/mwir_leo_minimal.yaml")
result = s.evaluate()

ResultPlotNamespace(result).mtf()   # all contributors vs frequency [cycles/mrad]

print(f"MTF at Nyquist (PSF path):    {result.metrics['mtf_at_nyquist']:.3f} (-)")   # 0.253
print(f"MTF at Nyquist (budget, x):   {result.metrics['mtf_system_at_nyquist_x']:.3f} (-)")
print(f"RER: {result.metrics['rer']:.3f} (-)")                                        # 0.601
```

### Example 10: Monte Carlo tolerance analysis

```python
from radiant import Sensor

s = Sensor.from_yaml("examples/mwir_leo_minimal.yaml")
s.set_tolerance("detector.qe_value",          "gaussian", std=0.03)
s.set_tolerance("optics.aperture_diameter_m", "gaussian", std=0.003)   # ±3 mm
s.set_tolerance("readout.read_noise_e_rms",   "uniform", low=4.0, high=8.0)  # e- RMS

mc = s.monte_carlo(n_trials=2000, seed=0)

print(f"SNR: {mc.mean('snr'):.1f} ± {mc.std('snr'):.1f} (-)")
print(f"P5 / P95: {mc.percentile('snr', 5):.1f} / {mc.percentile('snr', 95):.1f} (-)")
print(f"P(SNR ≥ 800): {mc.probability_of_exceeding('snr', 800.0):.1%}")
for pname, r in sorted(mc.correlation("snr").items(), key=lambda kv: -abs(kv[1])):
    print(f"  {pname}: r = {r:+.3f}")     # which tolerance drives the SNR spread
```

### Example 11: Sensitivity ranking

```python
from radiant import Sensor

s = Sensor.from_yaml("examples/mwir_leo_minimal.yaml")
sens = s.sensitivity(
    metric="snr",
    param_names=[
        "optics.aperture_diameter_m",
        "optics.transmission_scalar",
        "detector.qe_value",
        "spectral_integration.integration_time_s",
    ],
    delta_fraction=0.01,
)
for e in sens.entries:
    print(f"{e.param_name:45s} S = {e.sensitivity:+.3f}")
# optics.aperture_diameter_m                    S = +1.000
# detector.qe_value                             S = +0.500
# optics.transmission_scalar                    S = +0.500
# spectral_integration.integration_time_s       S = +0.500
# (extended shot-limited scene: SNR ∝ D·√(τ·QE·t_int))
```

### Example 12: Parameter explanation and provenance

```python
from radiant import Sensor

s = Sensor.from_yaml("examples/mwir_leo_minimal.yaml")
print(s.explain("optics.f_number"))
# optics.f_number = 4.0  (canonical: 4.0)
#   Description: Dimensionless f/# = focal_length_m / aperture_diameter_m. Part of the
#   {D, f, f/#} consistency group; supply any two and the third is derived.
#   Provenance: derived
#   Source: derived: f_number = focal_length_m / aperture_diameter_m
#   Derived from:
#     optics.aperture_diameter_m = 0.3
#     optics.focal_length_m = 1.2
```

### Example 13: Exoatmospheric mode (no atmosphere)

`atmosphere.model` accepts: `"simple"`, `"exo"`, `"tabulated"`, `"modtran"`, `"interpolated"`. The `"exo"` backend gives unity transmission and zero path radiance; its space sub-case requires the sensor altitude for the Earth-intercept LOS check:

```python
from radiant import Sensor

s = Sensor.from_yaml("examples/mwir_leo_minimal.yaml")
s.set_many({
    "atmosphere.model": "exo",              # τ(λ) = 1, L_path = 0
    "platform.h_sensor": 800e3,             # m — required by the space sub-case LOS check
    "geometry.sensor_altitude_m": 800e3,    # m
    "source.target.range_m": 800e3,         # m
})
result = s.evaluate()
print(f"NEDT: {result.nedt() * 1e3:.2f} mK")   # NEDT: 21.66 mK  (τ_atm = 1 everywhere)
```

The `ground_test` / `lab_test` no-atmosphere sub-cases (`source.no_atmosphere_subcase`) require injecting a `UserSpectralBackground` descriptor and are **not reachable from the scripting API** yet — see `tests/integration/test_no_atm_subcases.py` for the descriptor-injection pattern.

### Example 14: Clone before a what-if

```python
from radiant import Sensor

baseline = Sensor.from_yaml("examples/mwir_leo_minimal.yaml")
variant = baseline.clone().set("optics.aperture_diameter_m", 0.45)   # m

r0, r1 = baseline.evaluate(), variant.evaluate()
print(f"SNR: {r0.snr():.1f} → {r1.snr():.1f} (-)")   # SNR: 866.1 → 1299.2 (-)
```

### Example 15: Batch run across multiple configs

```python
import pandas as pd
from radiant import Sensor

configs = [
    "examples/mwir_leo_minimal.yaml",
    "examples/ground_truth_mwir.yaml",
]
rows = []
for path in configs:
    result = Sensor.from_yaml(path).evaluate()
    rows.append({
        "config":   path,
        "snr":      result.metrics["snr"],           # -
        "nedt_mK":  result.metrics["nedt_K"] * 1e3,  # mK
        "niirs":    result.metrics.get("niirs"),     # -
    })
print(pd.DataFrame(rows).to_string(index=False))
```

There is no `BatchRunner`; loop (or use `concurrent.futures`) as above.

### Example 16: Reproducibility via the provenance record

```python
import json
from radiant import Sensor

s = Sensor.from_yaml("examples/mwir_leo_minimal.yaml")
result = s.evaluate()

record = result.to_provenance_record()
with open("run_provenance.json", "w") as f:
    json.dump(record, f, indent=2)

# The record carries every resolved parameter with provenance, plus SHA-256
# hashes of every loaded config file — enough to audit or manually rebuild
# the run. (Automatic Sensor.from_provenance_record reconstruction is not
# implemented — Appendix A.)
```

### Example 17: Handling framework errors

```python
from radiant import RadiantError, Sensor

try:
    s = Sensor.from_yaml("my_config.yaml")
    result = s.evaluate()
except RadiantError as exc:
    # Every framework-defined error (parameter bounds, config errors,
    # Kirchhoff violations, MODTRAN parse failures) lands here.
    print(f"RADIANT rejected the run: {exc}")
```

---

## 10. Public API Summary

Top-level package — exactly three exports:

```python
from radiant import Sensor, RadiantError, __version__
```

Result and analysis types (obtained from `Sensor` methods; importable for type annotations):

```python
from radiant.api import (
    Sensor,             # same class as radiant.Sensor
    ChainResult,        # from s.evaluate()
    SweepResult,        # from s.sweep()
    Sweep2DResult,      # from s.sweep_2d()
    MonteCarloResult,   # from s.monte_carlo()
    SensitivityResult,  # from s.sensitivity()
)
```

Helper modules:

```python
from radiant.api.inspect import inspect_result, ResultPlotNamespace
from radiant.api.plot import (
    plot_sweep, plot_sweep_2d, plot_noise_budget,
    plot_psf, plot_mtf_terms, plot_spectral,
)
from radiant.api.session import RadiantSession   # advanced: run a chain on a custom grid
```

**Under the hood:** `Sensor.evaluate()` builds a `RadiantSession` on the configured wavelength grid and calls `session.run(params)`. `RadiantSession.run` pre-builds the configured atmosphere model via `radiant.atmosphere.loaders.build_atmosphere_model(params)` — all file I/O happens there, before chain execution (Rule 6) — and injects it via `ChainRunner.run(initial_stage_outputs={"atmosphere_config": {"model": ...}})`. The returned `ChainResult` carries the resolved `ParameterSet` so `to_provenance_record()` can report parameters and input-file hashes.

**Error budgets (Gaps 23 + 28).** `radiant.api.error_budget` provides a generic quadrature budget: `ErrorBudget(name, unit, contributors=(BudgetContributor(name, rms, note), ...), allocation=req)` with `rss_total`, `margin`, `over_budget`, `remaining_allocation()` (RSS headroom `sqrt(alloc² − total²)`), immutable `with_contributor(...)`, a formatted `table()` with per-contributor variance share, and `to_dict`/`from_dict`. One model serves jitter budgets (µrad) and WFE budgets (waves) — the math is unit-agnostic RSS; the unit field is display metadata.

**Zemax Zernike import (Gap 26).** `radiant.io.zemax_zernike.load_zemax_zernike(path)` parses a Zemax "Zernike Standard Coefficients" text export (Noll-indexed waves; UTF-8 / UTF-16 tolerant; the `.txt` analysis report, not the `.ZMX` prescription) into a `ZemaxZernikeResult`; `to_wavefront_error()` feeds the Gap 24/25 Zernike pipeline directly (`WavefrontError`, `WfeMode.ZERNIKE`). Single-field per file — multi-field exports are rejected with an actionable `ZemaxParseError` (export per field).

**Measurement import and comparison (Gap 30).** `radiant.io.measurement.load_measured_curve(path, x_column=, y_column=, delimiter=, skip_header="auto", x_unit=)` reads a measured CSV curve into a validated `MeasuredCurve` (comments/blank lines skipped, auto header detection, actionable `MeasurementParseError`; Excel is out of scope — export to CSV). `radiant.api.compare.compare_mtf(result, measured, axis=, frequency_unit=, pixel_pitch_m=, focal_length_m=)` interpolates the predicted MTF onto the measured frequency points (unit-aware via `convert_spatial_frequency`; overlap-only, never extrapolated) and returns an `MtfComparisonResult` with residuals, `rms_residual`, `max_abs_residual`, exclusion counts, and a formatted `table()`.

**Batch matrix execution (scenario 4.1).** `radiant.api.batch.BatchRunner(base_config, axes)` — the `BatchRunner` named in the package layout — runs one evaluation per cell of a labeled cartesian grid: `axes` is an ordered sequence of `(axis_name, {label: {dotpath: value}})` pairs (last axis varies fastest), each cell starts from `Sensor.from_dict(base_config)` plus that cell's overrides, and `run(evaluate)` calls `evaluate(sensor, labels) -> mapping` for the physics (a plain `evaluate()`, a `solve_for`, or any custom search). Failure policy per Rule 17: a cell that raises a `RadiantError` becomes a row with a populated `error` column — recorded, never dropped; non-RADIANT exceptions propagate. Returns a `BatchResult` (tidy `rows`, `n_failed`, `pivot(value, rows=, cols=)`).

**Target-library import (scenario 4.1).** `radiant.io.target_library.load_target_library(path, sheet=)` reads a mission target list from an Excel workbook (columns `target_name, length_m, width_m, height_m, temperature_K, emissivity, material`, any column order) into validated `TargetEntry` objects with the derived `projected_area_m2 = length × width` (overhead-look footprint). Duplicate names, non-numeric cells, and unphysical values raise `TargetLibraryError`. openpyxl is imported lazily (it lives in the `[scenarios]` extra) with an actionable error naming the extra — same optional-dependency pattern as the MODTRAN backend.

**Johnson-criteria DRI ranges (scenario 4.2).** `radiant.performance.johnson_criteria` computes Detection/Recognition/Identification ranges from the resolved-cycles model. `johnson_range_m(critical_dimension_m, ifov_rad, n50_cycles)` (`R = D / (2·IFOV·N50)`), `resolved_cycles(critical_dimension_m, ifov_rad, range_m)`, and the standard `JOHNSON_N50` table (detection 1.0, orientation 1.4, recognition 4.0, identification 6.4). Sampling-limited form — counts geometric cycles across the target, does not fold in the MTF/contrast (MRT/MRC). Out-of-range inputs raise `JohnsonCriteriaError`.

**Orbit-kinematics calculator (scenario 3.1).** `radiant.core.orbit` converts a circular LEO altitude into the orbital quantities coverage calculations consume (pure kinematics — same `core` category as `solar_geometry`). `orbital_velocity_m_s(altitude_m)` (`v = √(μ/a)`), `orbital_period_s(altitude_m)` (`T = 2π√(a³/μ)`), and `ground_track_speed_m_s(altitude_m)` (`v_g = v·R_E/a`, non-rotating Earth). Feeds the `ground_speed_m_s` input of `performance.access_rate`. New Earth constant `mu_earth_m3_s2` in `core.constants`; out-of-range altitude raises `OrbitError`.

**Repeat-ground-track & revisit (Gap 51).** `radiant.core.repeat_ground_track` adds the orbit-plane / ground-track layer above `orbit`. `nodal_regression_rate_deg_per_day(altitude_m, inclination_deg)` (J2 secular Ω̇), `sun_synchronous_inclination_deg(altitude_m)` (solves Ω̇ = 360°/yr — ~98° across LEO), `equatorial_ground_track_spacing_m(altitude_m)`, and `revisit_interval_days(altitude_m, swath_width_m, latitude_deg=0)` (first-order nadir estimate; exact repeat-cycle out of scope). New Earth constant `J2_earth`; out-of-range inputs raise `RepeatGroundTrackError`.

**Solar-geometry calculator (scenario 1.2).** `radiant.core.solar_geometry` converts date/latitude/time into the solar zenith angle for illumination geometry (pure kinematics — same `core` category as `slant_range_spherical_m`). `solar_declination_deg(day_of_year)` (Spencer's series, ~0.01°), `solar_zenith_angle_rad(latitude_deg, day_of_year, local_solar_time_hr)` (`cos θ_z = sin φ sin δ + cos φ cos δ cos h`), and `local_solar_time_from_ltan(ltan_hours)` (a sun-sync orbit holds ~constant local solar time along the daylit track, so LTAN ≈ target LST — documented approximation). Feeds `geometry.solar_zenith_rad`. Out-of-range inputs raise `SolarGeometryError`.

**ASTER spectral-library import (scenario 1.3).** `radiant.io.aster_library.load_aster_spectrum(path)` parses one JPL/NASA ASTER library text file (`Name:`/`Y Units:` metadata header + two whitespace-separated columns, wavelength [µm] and reflectance, native descending order sorted ascending on load) into an `AsterSpectrum` with fractional reflectance. `emissivity()` gives ε(λ) = 1 − ρ(λ) (opaque scene material — the legitimate independent-emissivity case; Rule 5 binds optical elements, not targets) and `band_averaged_emissivity(lam_min, lam_max)` the per-band scalar; both refuse to extrapolate outside the measured range. Unrecognizable `Y Units:` headers raise `AsterLibraryError` rather than guessing.

**Vendor detector-datasheet import (scenario 2.1).** Two domain loaders built on `load_measured_curve`, converting to canonical units at the file-reader boundary (Rule 2). `radiant.io.qe_csv.load_qe_csv(path, wavelength_column=, qe_column=, delimiter=, wavelength_unit="auto", qe_unit="auto")` reads a wavelength-vs-QE vendor CSV into a `QeCurve` (µm, fraction): units resolve from the header tokens (`nm`/`um`/`µm`, `pct`/`percent`/`%`) or explicit arguments — no magnitude guessing; QE > 1 in fraction mode raises with a pointer at `qe_unit="percent"`. `QeCurve.evaluate(wavelength_um, out_of_range="error"|"zero"|"clamp")` interpolates onto a chain grid (default refuses to extrapolate past the measured cutoff), and `band_averaged_qe(lam_min, lam_max)` gives the scalar for `detector.qe_value`. `radiant.io.dark_current_csv.load_dark_current_csv(path)` reads a `T_K, Jdark_A_cm2` vendor CSV into a `DarkCurrentCurve`: `j_dark_at(T)` interpolates ln(J) linearly in 1/T (Arrhenius-faithful; refuses to extrapolate), `dark_rate_e_per_s(T, pixel_pitch_m=)` converts to the canonical dark rate (`J · A_pixel / q`) for `detector.dark_rate_e_per_s`, and `temperature_at_rate(rate, pixel_pitch_m=)` is the exact inverse (e.g. dark-current crossover temperatures). Errors: `QeCsvParseError`, `DarkCurrentCsvParseError` (both `RadiantError`).

`RadiantSession.run` also accepts `extra_stage_outputs` (Gap 17): a dict of additional pre-chain injections merged over the built-in ones — the Rule 6 route for non-scalar inputs. Example: decouple polychromatic PSF weighting from the scene spectrum with `extra_stage_outputs={"optics_config": {"psf_weighting_spectrum": spectral_data}}` (a `SpectralData` in W/m²/sr/µm; must overlap the sensor band). The chosen weighting source is recorded in `stage_outputs["optics"]["psf_weighting_source"]` (`override:<name>` / `post_optics` / `at_aperture` / `flat`).

---

## 11. API Stability Contract

| Symbol | Stability |
|--------|----------|
| `radiant.Sensor` public methods (§2.2) | Stable across minor versions |
| `radiant.RadiantError` | Stable |
| `ChainResult` properties and methods (§3) | Stable across minor versions |
| `ChainResult.signal_at_frame` / `noise_at_frame` | **Deprecated** — removed in 0.2.0 |
| `SweepResult`, `Sweep2DResult`, `MonteCarloResult`, `SensitivityResult` public attributes | Stable |
| `ErrorBudget`, `BudgetContributor` (`radiant.api.error_budget`, Gaps 23+28) | Stable |
| `SolveResult` (`radiant.api.solve`, Gap 10) | Stable |
| `compare_mtf`, `MtfComparisonResult` (`radiant.api.compare`, Gap 30) | Stable |
| `load_measured_curve`, `MeasuredCurve` (`radiant.io.measurement`, Gap 30) | Stable |
| `load_zemax_zernike`, `ZemaxZernikeResult` (`radiant.io.zemax_zernike`, Gap 26) | Stable |
| `load_qe_csv`, `QeCurve` (`radiant.io.qe_csv`, scenario 2.1) | Stable |
| `load_dark_current_csv`, `DarkCurrentCurve` (`radiant.io.dark_current_csv`, scenario 2.1) | Stable |
| `BatchRunner`, `BatchResult` (`radiant.api.batch`, scenario 4.1) | Stable |
| `load_target_library`, `TargetEntry` (`radiant.io.target_library`, scenario 4.1) | Stable |
| `load_aster_spectrum`, `AsterSpectrum` (`radiant.io.aster_library`, scenario 1.3) | Stable |
| `solar_zenith_angle_rad`, `solar_declination_deg` (`radiant.core.solar_geometry`, scenario 1.2) | Stable |
| `orbital_period_s`, `orbital_velocity_m_s`, `ground_track_speed_m_s` (`radiant.core.orbit`, scenario 3.1) | Stable |
| `nodal_regression_rate_deg_per_day`, `sun_synchronous_inclination_deg`, `equatorial_ground_track_spacing_m`, `revisit_interval_days` (`radiant.core.repeat_ground_track`, Gap 51) | Stable |
| `dark_shot_crossover_rate_e_per_s`, `blip_rate_e_per_s`, `noise_equivalent_irradiance_ph_s_cm2` (`radiant.performance`, Gap 45) | Stable |
| `nep_from_dstar`/`dstar_from_nep` (`performance.detectivity`), `nep_from_noise_electrons`/`noise_electrons_from_nep`/`integrating_bandwidth_hz` (`performance.nep_electrons`), `netd_from_nep`/`nep_from_netd` (`performance.nep_netd`) — D*/NEP/NETD converters (scenarios 6.1, 4.5) | Stable |
| `minimum_resolvable_temperature_K`/`minimum_resolvable_contrast` (`performance.minimum_resolvable`, Gap 53) | Stable |
| `retrieve_temperature_K`, `band_planck_radiance`, `emissivity_jacobian`, `temperature_jacobian` (`performance.temperature_retrieval`, scenario 6.5) | Stable |
| `persistence_residual_sequence_e`, `persistence_residual_e`, `frames_to_clear` (`detector.persistence_sequence`, scenario 2.4) | Stable |
| `roc_curve`, `detection_probability`, `roc_auc` (`performance.roc`, scenario 6.4) | Stable |
| `analyze_calibration` + `CalibrationReport` (`radiant.api.calibration_analysis`, Gap 46) | Stable |
| `johnson_range_m`, `resolved_cycles`, `JOHNSON_N50` (`radiant.performance.johnson_criteria`, scenario 4.2) | Stable |
| `radiant.api.plot`, `radiant.api.inspect` helpers | Stable |
| `radiant.api.session.RadiantSession` | Semi-stable (wrapped by `Sensor`; not an alias) |
| `radiant.core.*` | Semi-stable (plugin API) |
| `stage_outputs` keys, `ChainState` internals | No stability guarantee |

Breaking changes require a major version bump and a deprecation cycle of at least one minor release.

---

## Appendix A — Not Yet Implemented

The 2026-04-07 revision of this document described the surface below. **None of it exists in the code.** It is retained here only so readers migrating old scripts know what to replace; do not call any of these.

| Documented (old) | Status / replacement |
|------------------|----------------------|
| `Sensor.load(sensor=..., scenario=...)` two-file form | Not implemented. Single-path `Sensor.load(path)` landed with Gap 67 (2026-07-11); merge scenario overrides with `set_many()`. |
| `Sensor.from_configs(...)`, `SensorConfig`, `ScenarioConfig` builders | Not implemented. Use YAML or `from_dict()`. |
| `s.validate()` | Not implemented as a separate step. Validation happens at `set()`/resolve/evaluate; catch `RadiantError`. |
| `s.schema()`, `s.params` proxy, parameter tab-completion | Schema enumeration landed as `s.parameter_defs()` / `s.parameter_def(dotpath)` (Gap 70, 2026-07-11). No `s.params` proxy or tab-completion. |
| `s.copy()` | Use `s.clone()`. |
| `s.save(path)` | Landed with Gap 67 (2026-07-11) — see §2.2. |
| `Sensor.load_result(...)`, `Sensor.from_provenance_record(...)` | Not implemented. Use `ChainResult.load(path)` on an archive written by `result.save(path)` (§3.9). |
| `result.background_at(...)`, `result.target_at(...)` | Not implemented. Use `stage_outputs["spectral_integration"]["background_e"]` / `["signal_e"]` (e-). |
| `result.noise_budget()` (NoiseBudget object with `.table()`/`.to_dataframe()`) | Use `result.noise_terms` + `inspect_result()` / `plot_noise_budget()`. |
| `result.mtf_at_nyquist()`, `result.mtf_curve(term)`, `result.mtf_budget()` | Use `result.metrics["mtf_at_nyquist"]`, `result.state.mtf_terms`, `stage_outputs["performance"]["mtf_budget"]`. |
| `result.detection_range()`, `result.rer()`, `result.gsd()` | RER/GSD are `metrics` keys (`rer`, `gsd_*_m`). Detection range is not a computed metric; sweep `source.target.range_m` against an SNR threshold. |
| `result.metrics()` as a method | `metrics` is a **property** (mapping), not a method. |
| `result.to_json(path)`, `result.to_csv(path)` | Not implemented. `json.dump(result.to_provenance_record(), ...)` covers provenance. |
| `result.inspect()` method / Jupyter tree widget | Use `inspect_result(result)` from `radiant.api.inspect`. |
| `result.plot.*` attribute (`snr_breakdown`, `spectral`, `spectral_all`, `ee_curve`, `transmission`) | Construct `ResultPlotNamespace(result)` (only `psf`, `noise_budget`, `mtf`) or use `radiant.api.plot` functions. |
| `result.stage(name)`, `result.frame(name)` methods | Use the `stage_outputs` and `frames` mapping properties. |
| `SweepResult.plot()`, `.to_dataframe()`, `.to_csv()` | Use `plot_sweep(sweep)`; build DataFrames from `values` / `metric_values` / `sweep[key]`. |
| `SweepResult.at_metric_threshold(x, from_above=True)` | `from_above` does not exist; first-crossing-from-below only. |
| `Sweep2DResult.plot.contour()` / `.heatmap()` / `.to_dataframe()` | Use `plot_sweep_2d(sweep2d)` and the `grid` attribute. |
| `MonteCarloResult.plot.*` (`histogram`, `cdf`, `scatter`, `tornado`) | Use matplotlib on `mc.to_dict()[metric]`. |
| `SensitivityResult.table()`, `.dataframe()`, `.plot.tornado()` | Iterate `sens.entries`. |
| `BatchRunner` | Not implemented. Loop over configs (Example 15). |
| Chain-injection parameters (`_chain.start_at`, `_inject.photoelectrons`) | Not implemented. |

If one of these becomes genuinely needed, file it as a feature task — do not document it here until it exists (CLAUDE.md Rule 20).
