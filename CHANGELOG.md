# Changelog

All notable changes to RADIANT are recorded here, per CLAUDE.md Rule 29.

Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Newest entries
at the top of `[Unreleased]`; on release, `[Unreleased]` rolls into a dated
version heading. Categories: **Added** / **Changed** / **Deprecated** /
**Removed** / **Fixed**. Entries that change computed numbers (physics models,
parameter defaults, golden baselines) are prefixed **Results-affecting:** and
state the direction and rough magnitude of the change.

What gets an entry (Rule 29): changes to computed results, public API surface
(methods, parameters, metrics, error classes, config fields), and capability
additions or removals. What does not: refactors, doc-only, test-only, and
internal changes with no observable effect.

This changelog begins 2026-07-07. Earlier history lives in `git log`,
`docs/tracking/gaps.md`, and `docs/tracking/Cleanup_Backlog.md` and is not
retroactively reconstructed.

## [Unreleased]

### Added
- **`radiant.api.geometry_modes` — public geometry input-mode manifest (CU-120).** The
  ADR-0006 family → mode → parameter structure (viewing V0–V4, solar S1–S3 + night,
  kinematics direct/circular: entry dot-paths, anchors, default doors, and provenance-based
  `active_mode_key` detection) is now owned by `radiant.geometry.mode_manifest` and
  re-exported through `radiant.api.geometry_modes` (the `metric_groups` precedent). The GUI
  Geometry screen consumes it instead of a hand-transcribed grouping and keeps only display
  labels. No results change.
- **`radiant.api.plot.plot_theme(dark=…)` context manager (CU-139).** A public seam that
  applies a dark or light matplotlib *chrome* theme (background/axes/text/ticks/grid) around
  figure production, so GUI/notebook callers can request a dark-styled `result.plot.*` figure
  without restyling it themselves. The GUI theme toggle now re-renders its stage plots through
  it, ending the bright-rectangle-in-dark-mode look. Data-series colours are unchanged.
- **`Sensor.resolved(dotpath)` and `Sensor.provenance(dotpath)` accessors (CU-105).**
  Structured, machine-readable passthroughs to the resolved parameter record — value,
  units, `provenance` (a `Provenance` enum), and source — replacing the need to parse the
  human-readable `Sensor.explain` string. The GUI now reads provenance through these.
- **Named unit-enumeration accessors on `radiant.api.units` (CU-109).** New public
  `units_for(canonical_unit)`, `input_units()`, and `targets_for(from_unit)` replace
  reaching into the underscored `_CONVERSIONS` registry, which is no longer re-exported
  from `radiant.api.units` (it stays private to `radiant.core.units`). The GUI unit
  selector and the `radiant convert` CLI now use these accessors. No results change.
- **Per-metric group selection for performance metrics (Gap 96).** Five new
  boolean parameters — `performance.metrics.radiometric`,
  `performance.metrics.spatial_mtf`, `performance.metrics.interpretability`,
  `performance.metrics.sampling`, `performance.metrics.saturation` (all default
  `True`) — select which metric families `PerformanceStage` computes and
  surfaces. Turning a group off stops the *computation* of its metrics (and any
  warnings they emit), not merely their display; hidden prerequisites are still
  computed via the metric dependency closure (enabling only Interpretability
  computes `snr`/`rer`/`gsd_*` for NIIRS but does not surface them). Saved in
  YAML and scriptable; the GUI Performance stage adds a "Metric selection" card
  of five checkboxes (one toggle ↔ one `sensor.set`). New public surface:
  `radiant.api.metric_groups` (`GROUP_PARAMS`, `METRIC_GROUPS`,
  `resolve_selection`, `group_of`) and `ChainState.without_metric`. **Not
  results-affecting**: the all-on default reproduces every existing metric
  exactly.
- **GUI: point-source intensity inputs on the Source instrument (Gap 98 D).**
  A new "Target — point source" tab exposes the point-intensity inputs
  (`point_intensity_temperature_K`/`_area_m2`/`_emissivity`, `_band_W_per_sr`),
  gated ON only for a declared `point_source` scene (schema `regime:point_source`
  tag); conversely the surface-radiance `source.target.temperature`/`emissivity`
  rows gate OFF for point-source (a point source is defined by intensity, not
  radiance × area). Completes Gap 98 (with the A/C engine fixes above).
- **Point-source intensity convenience inputs (Gap B).** A true point source
  (SDA object, star) is defined by radiant intensity `I(λ)` [W/sr/µm], not
  surface radiance × area. Two new opt-in ways to supply it without a CSV, both
  routing to the same `T7IntensityAtSource` (point-source regime):
  - **Blackbody emitter** — `source.target.point_intensity_temperature_K`,
    `point_intensity_area_m2`, `point_intensity_emissivity` →
    `I(λ) = ε·A·B(λ,T)`.
  - **Scalar band flux** — `source.target.point_intensity_band_W_per_sr`, taken
    as the in-band integral `∫ I(λ) dλ` [W/sr] over the filter band and modeled
    as spectrally flat within it.
  Mutually exclusive with each other, the CSV intensity path, and the
  surface-radiance (ε, T) path (actionable errors on conflict / zero area). New
  module `radiant.source.converters.point_intensity`. Not results-affecting for
  existing configs (all params default to their "not set" sentinel).
- **GUI: the Target-shape panel gains a Projected-area field, mutually exclusive
  with the shape dimensions.** When the shape library is `none`, the panel shows a
  scalar **Projected area** field (`geometry.target.projected_area_m2`); when a
  shape is selected it shows that shape's dimensions instead — never both. Shape
  and projected area are two ways to size the same target, so the GUI now enforces
  "one or the other" by construction (the engine's shape-wins precedence remains
  the backstop for raw configs that set both). Previously a shapeless target's area
  could be set only from the parameter tree.
- **GUI: the Geometry Schematic now shows the target's projected area (CU-168).**
  A leader-label pill by the target reads `A_t  <area> m²  ·  <n> px` (the pixel
  multiple is √A/range over the detector IFOV — the sub-pixel-vs-resolved cue),
  drawn whenever a target area is defined. Previously a target sized only by
  `geometry.target.projected_area_m2` (shape library = "none") drew a bare point
  marker, so a defined area was visible only in the parameter tree. Read verbatim
  from `stage_outputs["source"]`; no physics change.
- **Results-affecting (opt-in): MODTRAN flux-file downwelling on the tape7-import
  path (CU-157).** New parameter `atmosphere.modtran.flux_path` names a Block E
  spectral flux CSV (`*_flux.csv`) alongside `atmosphere.modtran.tape7_path`.
  When set, the run's ground-level DOWN irradiance feeds the sky-reflection
  terms — `E_sky_thermal` from the thermal band (≥ 4 µm) and `E_sky_scattered`
  from the reflective-solar band (< 4 µm) — superseding the Gap 81 zeros for
  flux-equipped imports (no more zero-downwelling warning). This raises reflected-
  sky background for low-ε / mixed emit+reflect targets on the MODTRAN-import
  path (e.g. E1 LWIR downwelling ≈ 24.6 W/m², VIS ≈ 124 W/m², previously 0).
  Only affects configurations that set `flux_path`; all existing scenarios and
  goldens (none set it) are unchanged. New `FluxImport` public class.
- **Exo-altitude targets over an atmospheric background (Gap 95).**
  `LineOfSightGeometry` now accepts any target altitude ≥ 0 m; a target at or
  above the atmosphere top (default 100 km — satellite, post-burnout booster)
  is served by every atmosphere backend with the exact vacuum target leg
  (τ_up ≡ 1, L_path_up ≡ 0, τ_sun ≡ 1) while the ground→sensor full column
  (τ_full_up, L_path_full) is retained for the background/noise branch —
  identical to a surface-target evaluation of the same backend. Implemented
  once, model-agnostically (`atmosphere/exo_target.py`), so single-column file
  imports work too. Previously these configurations were rejected at LOS
  construction. The 29–100 km band remains data-limited pending the boost-ladder
  run set (`docs/plans/MODTRAN_Boost_Ladder_Expansion_Plan.md`; 14 runs appended
  to the run matrix).
- **`InterpolatedAtmosphere` warns when non-axis query geometry is ignored
  (CU-167).** Querying a data set at a geometry the samples don't cover in a
  non-interpolated dimension (e.g. the nadir-only ladders at 45° LOS zenith) now
  emits a `UserWarning` naming the ignored field and the value actually served
  (~1°/1 m tolerance), instead of silently substituting the stored column; a
  recorded non-axis field that varies across sample points is refused at
  construction.
- **Airborne targets (h_tgt > 0) on the file-backed atmosphere paths (Gap 94).**
  (1) `InterpolatedAtmosphere.evaluate()` now serves elevated targets when the grid
  carries a `target_altitude_m` axis — two interpolator queries give the real two-leg
  split (target→sensor τ_up/L_path_up at `h_tgt`, ground→sensor τ_full_up/L_path_full
  at 0 m), which un-strands the shipped `data/atmospheres/midlat_summer_ladders/`
  family (0–29 km targets, 35 km–GEO sensors) for boost-phase / near-space scenarios.
  No extrapolation: targets beyond the grid hull are still refused loud.
  (2) New parameter `atmosphere.modtran.tape7_up_path`: a second target→sensor tape7
  (a MODTRAN run with H2 = target altitude) imported alongside `tape7_path`'s full
  column, enabling h_tgt > 0 on the tape7 file-import path. Surface-target results are
  unchanged on both paths (previously these configurations raised
  `NotImplementedError`). The no-sun-file collapse warning on both backends now states
  precisely what is aliased (τ_sun onto τ_up).
- **GUI: Browse… picker on path parameters.** The Parameter Editor dialog adds a native
  file/directory picker next to the value field for every `*_path`/`*_file`/`*_dir`
  parameter (e.g. `atmosphere.interpolated_data_dir`), so paths no longer have to be
  typed by hand. Commit still goes through the single validated `sensor.set` on Apply.
  An empty field's picker opens on the parameter's shipped-data home (`atmosphere.*` →
  `data/atmospheres/`, `detector.*` → `data/detectors/`, `source.*` →
  `data/emissivity/`), not the working directory.
- **`atmosphere.model = "interpolated"` works out of the box.** With
  `atmosphere.interpolated_data_dir` unset, the loader now defaults to the shipped
  library family matching `atmosphere.interpolation_axes` (`path_zenith_rad` →
  `us_standard_zenith_fan`; `sensor_altitude_m,target_altitude_m` →
  `midlat_summer_ladders`), with a logged notice; an explicit directory always wins and
  uncovered axes still raise the actionable error. Previously an unset directory always
  errored. Pointing `interpolated_data_dir` at a library ROOT (e.g. `data/atmospheres/`
  itself) now descends into the family folder matching the axes instead of failing with
  "found 0 NPZ files"; a directory with no matching family fails with the family
  subfolders listed.
- **`InterpolatedAtmosphere` accepts any query wavelength grid inside the stored
  spectral range (CU-156).** `build_state` linearly resamples the
  geometry-interpolated spectra onto the query grid (the `TabulatedAtmosphere`
  pattern) instead of requiring an exact grid match; out-of-range queries still fail
  loud. Sessions no longer need to run on the library's grid to use the shipped
  interpolated families.

### Fixed
- **GUI pinned-panel set persists across sessions (CU-115).** Pinning/unpinning a metric
  or stage-output card is now saved via `QSettings` and restored on the next launch (falling
  back to the default five-metric set when none is stored). Previously the pin set reset
  every relaunch.
- **`SpectralDataStore` warns on gross spectral extrapolation (CU-085).** When a curve
  covers less than ~80% of the requested band (> 20% constant-extrapolated), the store now
  raises a `UserWarning` naming the extrapolated fraction instead of a silent debug log;
  legitimate near-edge extrapolation (≤ 20%) stays quiet, so shipped scenarios remain
  warning-free. Also added test coverage for the digital-TDI noise-scaling branches.
- **MODTRAN cache key fingerprints the binary (CU-070).** The binary-invocation cache
  key now includes a hash of the MODTRAN executable's bytes, so upgrading the binary
  invalidates stale entries instead of silently serving the old version's results. The
  fingerprint is read from the executable's bytes (never by invoking it). Existing
  binary-path caches regenerate on first use.
- **MODTRAN state validates arrays before clamping (CU-071, Rule 17).** A tape7 import
  or cached array with transmittance well outside [0, 1] or a clearly-negative path
  radiance now raises an actionable `AtmosphereValidationError` (naming the likely
  unit-confusion / corrupt-file cause) instead of being silently snapped into range;
  only ≤1e-12 float noise is still clipped. Matches `TabulatedAtmosphere`.
- **GUI NEDT metric badge displays in mK (CU-108).** The NEDT badge now shows its
  canonical Kelvin value at a legible milli-Kelvin scale (0.045 K → 45 mK) via a single
  per-metric display-scale table in `metric_format`; the base unit still comes from the
  registry and the stored result is unchanged. Display-only.
- **GUI Geometry form re-syncs immediately on a parameter-tree edit (CU-121).** A
  geometry value edited in the left parameter tree now updates the Geometry Inputs/Schematic
  form at once, instead of only after the next debounced evaluation. Display-only.
- **GUI Parameter Editor: Current/Bounds rows follow the chosen unit after Apply
  (CU-111).** Applying a new unit without closing the dialog now re-expresses the
  informative Current and Bounds rows in that unit (e.g. `8 km`, not `8000 m`), so they
  agree with the unit combo. Display-only; the canonical value is unchanged.
- **GUI Source Outputs readout: `inf`/`None` render cleanly (CU-135).** An
  extended-target angular extent shows `∞` instead of `inf rad`, and an absent
  (`None`) background descriptor is skipped rather than shown as a backwards `— ` row.
  Display-only.
- **`inspect_result` summarises nested NumPy arrays (CU-113).** Arrays reached only
  via a stage-output object's own `repr` (tuples, dataclasses) are now collapsed to
  NumPy's summarized `[a, b, … y, z]` form instead of dumping hundreds of
  continuation lines — the shipped-example dump drops from ~3900 lines to ~230. The
  structural tree is unchanged; only oversized array bodies shrink.
- **`result.plot.psf()` default axes labelled "x/y (PSF samples)" (CU-136).** The
  default (non-grid) render's imshow extent is the PSF sample grid, not the detector
  pixel grid, so the previous "x/y (pixels)" labels were misleading for an oversampled
  PSF. Label-only; no data change.
- **Warning-free evaluate: four informational chain warnings reclassified (owner
  bar — a valid scenario evaluates warning-free).** These fired a `UserWarning`
  on every evaluate for a *documented, legitimate* behavior, so they polluted the
  GUI Messages panel and console on valid scenarios: (C) the detector
  temperature-inert dark-rate note (CU-081) is now `stage_outputs["detector"]
  ["dark_temperature_note"]` (rendered once in the Outputs readout); (A) the
  SimpleAtmosphere Ångström aerosol clamp beyond 5 µm (CU-088), (B) the
  extended-scene "background.* ignored" notice (ADR-0002 #15), and (D) the MWIR
  non-mixed model advisory (matrix §3.2) now log at `debug` (quiet by default,
  discoverable) instead of warning. Saturation warnings (full-well/ADC/pixel)
  stay as-is — they signal untrustworthy results. The 36 shipped configs now
  evaluate with zero non-deprecation warnings except genuine saturation. No
  physics/results change. (`docs/plans/Warning_Free_UX_Plan.md`.)
- **GUI: no more `qt.qpa.fonts` warning on launch (CU-169).** The theme's font
  stacks led with "IBM Plex Sans"/"IBM Plex Mono", which are usually not
  installed, so Qt logged `Populating font family aliases took … ms. Replace uses
  of missing font family "IBM Plex Mono" …` (and paid a ~170 ms cost) every
  launch. The generated stylesheet now names only families Qt actually has —
  unavailable design fonts are dropped from each stack (Qt was already falling
  back to the same next family, so the UI look is unchanged) — and a startup hook
  registers any IBM Plex `.ttf` bundled under `gui/assets/fonts/` (CU-103
  infrastructure) so the design font is used when shipped. First item of the
  Warning-Free UX campaign (`docs/plans/Warning_Free_UX_Plan.md`).
- **Point-source workflow: range fallback + actionable "no intensity" error (Gap 98 A/C).**
  (C) A `point_source` target no longer requires `geometry.target_range_m` to be set
  explicitly — `source.range_m` falls back to the GeometryStage-derived slant range
  (from altitude + zenith / orbit / site modes), so a point-source config that derives
  its range now runs instead of failing with "requires … range_m". (A) When a
  `point_source` target has no radiant intensity, the error now steers to the intensity
  inputs (`point_intensity_*` / `user_intensity_path`) instead of pointing back to
  `projected_area_m2` — a point source is defined by intensity, not radiance × area.
  Not results-affecting for existing configs (only enables previously-erroring ones).
- **Results-affecting: sub-pixel signal now derives `fill_fraction` from the target
  projected area (Gap 97).** In the `sub_pixel` regime the target's share of the
  pixel was taken from `source.target.fill_fraction` (default 1.0) and never from
  `geometry.target.projected_area_m2` — so a specified target area was silently
  ignored and the chain computed an extended-scene signal regardless of target
  size. `SourceStage` now derives `fill_fraction = A_proj / (Ω_pixel · range²)`
  (clamped to 1.0 on overfill) whenever a projected area is given and no explicit
  `fill_fraction` is set; an explicit `fill_fraction` is still honored. **Direction/
  magnitude:** only affects sub-pixel targets specified by area without an explicit
  fill fraction; for genuinely sub-pixel targets it *reduces* the target signal /
  contrast by the fill factor (e.g. a 24 m² target at 532 km, 15 µm/0.75 m optics:
  `contrast_snr` −84 → −17, a ~4.8× correction). Shipped scenarios are unchanged
  (1.1 maritime overfills → clamps to 1.0; 1.3 sets `fill_fraction` explicitly);
  no golden moved. New module `radiant.source.fill_fraction`.
- **GUI: File → New (or opening an incomplete config) no longer wedges the window.**
  A result belongs to the sensor that produced it; the stage center now drops its
  stored result when the sensor is swapped, so navigating to a stage after a swap
  shows the placeholder instead of re-populating the *stale* result against the new
  live sensor. Previously that re-render resolved the new (blank) sensor through the
  geometry viewer and crashed with `CoreValidationError: Circular dependency …
  ['optics.aperture_diameter_m', 'optics.focal_length_m', 'optics.f_number']`,
  leaving the whole window unusable behind a modal error (screens would not switch).
- **GUI: the geometry schematic's "unavailable" guard panel now recovers (CU-163).**
  A build failure during `show_result` still surfaces the actionable panel, but a
  later evaluate that builds cleanly rebuilds the canvas and re-enters schematic
  mode — one transient adapter error no longer disables the viewer for the rest
  of the session (previously the panel was one-way and required restarting the app).
- **GUI: night scenes no longer kill the geometry schematic.** With
  `geometry.solar_illumination = "night"` the geometry stage publishes the solar
  angles as `None`; the schematic adapter crashed on `float(None)` and the viewer
  degraded to its permanent "unavailable" panel. Night scenes now render with the sun
  (glyph, SUN→TARGET / SUN→GROUND vectors, drop lines, legend rows, and the θ_s / Δφ /
  phase angle annotations) simply absent; the sensor/target geometry is unchanged.

### Removed
- **Dead `readout.read_noise_is_post_cds` parameter (CU-077).** The parameter was never
  read by any code (no pre/post-CDS √2 scaling is modelled); removed from the schema.
  Enter `read_noise_e_rms` as the effective per-frame (post-CDS) value. The likewise-unimplemented
  `cds_1f_suppression` was doc-only and the `RADIANT_Detector_Complete.md` CDS table is
  corrected to match the code (neither factor is applied).
- **Dead source exports `CompositeTarget` and `SubPixelSource` (CU-084).** These two
  `radiant.source` classes had no live constructor in the chain (self-references only);
  removed along with their modules and tests. The rest of the former "shadow" source
  system (`ThermalSource`/`ReflectedSolarSource`/`CombinedSource`/`SurfaceMaterial`/the
  `resolvers`) is now the wired live source-object system and is unaffected.

### Changed
- **Structured errors for parameter bounds/enum rejection (CU-107).** The
  `ParameterSet` resolver now raises `ParameterBoundsError` (out-of-bounds) and the new
  `ParameterEnumError` (invalid enum choice) — each carrying a `what / why / action /
  context` payload (Rule 15) — instead of a flat `CoreValidationError`, so the GUI's
  actionable dialog can show why and how to fix, not just what. Both co-inherit
  `ValueError` + `RadiantError`, so existing `except ValueError` / `except RadiantError`
  and message-match callers are unaffected. No results change.
- **Cross-platform text I/O: explicit `encoding="utf-8"` everywhere (CU-149).** All
  text-mode `open()`/`read_text()`/`write_text()` call sites in `src/`, `scripts/`, and
  `dev_tools/` now pass `encoding="utf-8"`, so UTF-8 data/config files (containing `µ`,
  `°`, `⁻`) decode correctly on stock Windows (cp1252 locale) instead of raising or
  silently mojibaking. Ruff `PLW1514` (`unspecified-encoding`) is enabled to prevent
  regression. Not results-affecting on macOS/Linux (UTF-8 is already the default).
- **Cross-platform MODTRAN `binary_path` default (CU-151).** The default MODTRAN
  executable path now resolves to `modtran` on `PATH`, else the per-platform install
  location (POSIX `/usr/local/bin/modtran`; Windows `C:\Program Files\MODTRAN\modtran.exe`),
  instead of a hardcoded POSIX path that could never exist on Windows.
  `ModtranUnavailableError` names both a Windows and a POSIX example. Not
  results-affecting (the macOS default string is unchanged).
- **Pinned line endings via `.gitattributes` (CU-150).** A root `.gitattributes`
  (`* text=auto eol=lf` + `-text` for binary assets) keeps tracked text at LF in the
  working tree, so byte-level comparisons (golden baselines, checksummed reference data,
  MODTRAN decks) stay identical across macOS/Windows. The MODTRAN deck writers also pass
  `newline="\n"` explicitly. Not results-affecting.
- **NIIRS out-of-calibration is now structured status, not a per-evaluate warning
  (CU-166).** When a NIIRS/IIRS input falls outside the GIQE-5 calibration band the
  chain no longer emits a `UserWarning` (nor a `logger.warning`) on every evaluate —
  the condition is carried solely on the result (`GIQEResult.extrapolated`,
  `.warnings`, and the `niirs_extrapolated` metric), which was always available.
  This stops the warning flood in sweeps / Monte-Carlo / the GUI console (owner bar:
  a valid, nominally-operating scenario evaluates warning-free). No computed value
  changes. Up-front metric-applicability gating and the MWIR→IIRS/GIQE-5 routing
  question remain deferred, gated on the Gap 96 metric-selection decision.
- **Results-affecting (simple-atmosphere scenes with a reflected-sky term):
  SimpleAtmosphere downwelling sky emission rebuilt against the real MODTRAN 6
  up-looking runs (CU-155).** `E_sky_thermal` (and the legacy `L_atm_down`) now
  use a target-anchored emission temperature `T(h_tgt + 200 m)` with a
  flux-diffusivity exponent `D = 1.1` on the **vertical target→h_atm_top**
  column — the sensor's altitude and viewing zenith no longer enter (the old
  model evaluated `T` at `0.5·h_sensor`, clamping every space column to the
  216.65 K tropopause). Direction/magnitude: downwelling sky irradiance rises
  ~5× in LWIR and ~40× in MWIR for space-sensor columns, landing within
  [0.7, 1.4]× of the real H-run references (was 0.02–0.21×). Scenes with
  low-emissivity targets/backgrounds gain reflected-sky signal and background;
  high-ε scenes shift little (golden `mwir_leo_minimal`, ε = 0.95: signal_e
  +1.48%, SNR +0.74% — re-baselined per Testing §5.3 with provenance). The
  MWIR crossover anchor re-calibrated to the corrected thermal (ratio bound
  10 → 20 at 4 µm, intent unchanged).
- **Results-affecting (all simple-atmosphere configs): SimpleAtmosphere recalibrated against
  the real MODTRAN 6 run set (CU-161).** Two model changes: (1) the five-Lorentzian water fit —
  whose far wings made the MWIR water response ~5× too steep — is replaced by a 15-region
  curve-of-growth model `OD_h2o = k(λ)·w_eff^b(λ)` fit to the real water ladder (D4/A1/D5,
  H₂O ×0.5/×1/×2; sub-linear b in saturated bands, super-linear b≈1.3–1.75 in the LWIR
  continuum); (2) a **well-mixed-gas absorption floor** (CO₂ 4.3/15 µm, N₂O, O₃ 9.6 µm, O₂/CH₄)
  is added per region — the term whose absence made the old model attribute the MWIR CO₂ floor
  to water. The gas term also enters the single-scattering-albedo denominator (pure absorber),
  improving the ω₀ ≈ 1 space-column defect (Gap 38). **Direction/magnitude:** MWIR signals rise
  substantially where water over-absorbed (golden `mwir_leo_minimal` signal_e +147%, SNR
  616→968 — verified against a real-MODTRAN chain run at 869k e-/SNR 932: the old golden was
  2.3× too low, the new model is within 8% of truth); LWIR at-aperture spectra reshape
  (brighter 8–9 µm, darker 12–13 µm, toward the real anchors); dry/arctic profiles darken
  slightly. Cross-validated to ≤ ±0.012 band-mean τ on five non-calibration profile anchors;
  partial-column parity vs the real C-ladder tightens 3–5× (envelope now two-sided
  [−0.04, +0.05] band-mean). Goldens re-baselined per Testing §5.3: `mwir_leo_minimal.json`,
  Cell 28 NEDT/L_aperture, `test_chain_spatial` SNR (604.97→945.94), table-C envelope.
  Calibration generator: `scripts/fit_simple_atmosphere_gas_bands.py`; anchors pinned in
  `test_simple.py::test_cu161_water_ladder_anchor`.
- **Results-affecting (off-node zenith queries only): `InterpolatedAtmosphere` and the
  run-matrix family interpolator now interpolate zenith-angle axes in airmass sec(θ) space
  (CU-160).** Optical depth scales with airmass, so log-τ linear in sec(θ) is Beer-Lambert-
  exact between nodes; the previous linear-in-angle axis carried a measured −4% in-band τ
  bias at fan midpoints. Direction/magnitude: mid-angle zenith queries of angle-gridded data
  (e.g. the shipped `us_standard_zenith_fan/`) gain up to ~+4% band-mean τ, converging on the
  real MODTRAN holdout truth (45° from 30°/60°: −0.10% vs −4.07%). Node queries are unchanged.
  Zenith nodes ≥ ~88.8° are now refused (sec diverges at the horizon). Level-0 Beer-exactness
  tests + a committed-library holdout test pin the property.
- **Scenario 8.1 (off-nadir interpolation) upgraded to the real MODTRAN 6 zenith fan**, adding a
  holdout validation of the interpolation method itself: predicting the real 45° run from its
  30°/60° neighbors lands −4.07% (log-τ linear in angle) vs +6.84% for nearest-neighbor — and
  −0.10% when interpolated in airmass sec(θ) space, filed as CU-160 (also affects the shipped
  zenith-fan library's off-node queries). Figure/walkthrough regenerated from real data.
- **Scenarios 1.1 (MWIR maritime) and 6.2 (atmospheric intercomparison) upgraded from
  synthetic to real MODTRAN 6 data (2026-07-17 run set).** Both scripts auto-detect the
  staged real runs (synthetic remains a loud fallback); walkthroughs, figures, and results
  tables regenerated. The comparisons are now validated benchmarks: SimpleAtmosphere
  over-responds to profile water vapor (6.2: in-band MWIR τ spans 0.16–0.81 vs real
  MODTRAN's 0.42–0.57, near-exact at us_standard, ±40–60% at climate extremes; 1.1:
  maritime τ 0.239 vs real 0.432 → detection range understated by ~25%). Model behavior
  is unchanged — these are data/scenario updates; the SimpleAtmosphere accuracy findings
  are tracked in Gap 38/gaps.md and CU-155.
- **Gap 39 closed (A3 partial-column MODTRAN parity):** the chain's τ_up(h_tgt) is now
  pinned against real MODTRAN C-ladder goldens on every test run
  (`tests/integration/test_table_c_cells.py::TestTableCModtranPinned`), with the
  characterized envelope (simple optimistic by up to +0.13 band-mean τ at low altitude)
  recorded in the registry.

### Added
- **Shipped nominal atmosphere library (`data/atmospheres/`).** Committed NPZ spectra derived
  from the real 2026-07-17 MODTRAN 6 run matrix: six standard-profile nadir columns (tabulated;
  us_standard/tropical include real downwelling sky radiance from the up-looking H-runs), a
  us_standard LOS-zenith fan 0–60° (interpolated), and a midlat_summer sensor×target-altitude
  grid spanning 35 km–GEO × 0–29 km (interpolated, with a 40,000 km duplicate node so orbital
  sensors fall inside the hull). Slit-degraded to 5 cm⁻¹ FWHM (~4 MB). Users without a MODTRAN
  license now get real-radiative-transfer atmospheres via `atmosphere.model="tabulated"` /
  `"interpolated"`. Generator: `scripts/build_atmosphere_library.py`; design record:
  `data/atmospheres/MANIFEST.md`. Known limitation: the interpolated families require the
  session to run on the library grid (CU-156).
- **`ModtranFluxReader` — reader for MODTRAN 6 spectral flux CSVs (CU-154).** Block E irradiance
  runs export their direct/diffuse solar irradiance to a separate `*_flux.csv` (UP/DOWN/SOLAR per
  altitude level), a format nothing read before. `parse()` returns per-level native flux
  (`ModtranFluxOutput`); `to_radiant_units()` returns ground-level `(wavelength_um, e_direct,
  e_diffuse_down)` in W/m²/µm via the same ν² Jacobian as the radiance path. Validated on the real
  E1 run (LWIR direct beam = 0, downwelling diffuse ≈ π·B near surface, VIS direct ≈ TOA·τ·cos θ_s).
  Not yet wired into the chain — that is the open Gap 38 decision.
- **`Tape7Reader` now reads MODTRAN 6 tape7 output (CU-154).** The parser recognised only the
  classic space-delimited column vocabulary (`TOT TRANS`, `PTH THRML`, `SOL SCAT`, `GRND RFLT`);
  the first real MODTRAN run set (2026-07-17) is MODTRAN 6, whose tape7 uses underscore labels
  (`TOT_TRANS`, `THRML_EM`, `GRND_RFLT`) and splits the combined solar-scatter column into
  `MULT_SCAT` + `SING_SCAT`. Both vocabularies are now accepted (one reader per binary);
  `path_scattered_radiance` uses the classic `SOL_SCAT` when present, else the `MULT_SCAT +
  SING_SCAT` sum. MODTRAN's `-9999.` end-of-block sentinel is now detected and excluded. This is
  the enabling change for real-MODTRAN integration (Gap 39/38, CU-011, the shipped atmosphere
  library); the delivered 39-run matrix all parses. No change to results for existing
  (synthetic-fixture / SimpleAtmosphere) configs.

### Fixed
- **GUI: undoing a target-shape pick now also reverses the dimensions seeded alongside it, in one
  step (CU-141, view-only).** Picking a shape auto-seeds any still-unset required dimensions to
  nominal values (CU-125); previously Undo reversed only the shape enum and left the seeds behind.
  The shape edit and its seeds are now recorded under a single `QUndoStack` macro, so one Undo
  restores the exact pre-pick state (shape *and* dimensions). Golden results untouched.
- **GUI: Evaluate gains a `Ctrl+Return` (⌘+Return on macOS) shortcut alongside `F5` (CU-142,
  view-only).** A bare `F5` needs the Fn modifier on stock macOS, leaving the app's most-used action
  keyboard-unreachable there; the added chord fixes reachability while keeping the familiar F5=Run
  convention. Menu items and the Run button are unchanged.
- **Results-affecting (both-set configs only): `geometry.target.shape` now wins over
  `geometry.target.projected_area_m2` in the *published* projected area, not just the descriptor
  (CU-148).** When a config set **both** a concrete shape and an explicit `projected_area_m2`, the
  inferrer applied "shape wins" to the descriptor `A_t` and emitted a `shape wins` warning, but
  `SourceStage` still published the **param** area to the regime classification and the
  SpectralIntegration solid angle — so the SNR-bearing path silently used a different area than the
  descriptor and the warning reported. `SourceStage` now adopts the descriptor's authoritative `A_t`
  unconditionally, so the published area, the descriptor, and the warning agree. **Direction/magnitude:**
  affects only configs that set both a shape and `projected_area_m2`; for those, regime and SNR shift by
  the ratio of shape-area to param-area. **No existing golden or example uses that combination, so all
  baselines are byte-identical** (verified full-suite); a new `test_stage.py` both-set test covers the fix.

### Added
- **Scene-type parameter relevance gating (Gap 85 partial, results-neutral).** Source-stage
  parameters now carry `regime:<scene_type>` schema tags (background + contrast-reference +
  fill-fraction); with a declared `source.scene_type`, the GUI Source form **disables** (never
  hides) rows irrelevant to that type with a tooltip naming the relevant regimes — declare
  `extended` and the sub-pixel knobs gate off, declare `sub_pixel` and the contrast reference
  gates off, `auto` gates nothing. Metadata-only schema change; no computed value changes.
- **GUI: confirm-before-Apply import previews (ADR-0009 D5, results-neutral).** New shared
  `ImportPreviewDialog`: pick a file, see the parsed curve + unit-labeled parse facts (point
  count, λ span, value ranges), then Apply commits the path with one `sensor.set` — or the
  loader's actionable error shows inline and Apply stays disabled. Wired for vendor QE CSVs
  (Detector → "Import QE curve (preview)…" → `detector.qe_table_path`) and MODTRAN tape7s
  (Atmosphere → MODTRAN → "Import tape7 (preview)…" → `atmosphere.modtran.tape7_path`; shows
  transmittance + path radiance). Backed by the new `radiant.api.preview_spectral_import`.
- **Zemax Zernike wavefront via config (`optics.zernike_file`) + GUI import (GS-4 split 2).**
  New parameter: point at a Zemax 'Zernike Standard Coefficients' export and the API layer loads
  it pre-chain, injecting the ZERNIKE-mode wavefront (supersedes the scalar WFE; the report's
  reference wavelength is honored, `optics.wfe_reference_wavelength_um` is the fallback). Persists
  via Save/Open and works from the CLI. The Optics Inputs card gains the WFE fields (reference
  wavelength, Zernike file, defocus) and an **Import Zemax Zernike…** button with a
  confirm-before-Apply summary (terms, non-piston RSS waves, reference λ — new
  `radiant.api.preview_zemax_zernike`). Results-neutral unless the parameter is set.
- **GUI: unsaved-edit guards, script-editor line numbers, File → New crash fix (CU-140 /
  CU-144 / CU-145, results-neutral).** File → New / Open / Open Recent now ask
  Save / Discard / Cancel when the config has unsaved edits; closing a dirty script tab asks
  Discard / Cancel; the script Editor pane gains a theme-aware line-number margin.
  **Fixed:** File → New crashed (uncaught resolution error) — every provenance/value display
  surface now falls back to an unset display on a not-yet-resolvable config (new
  `safe_provenance` helper used across the parameter tree, geometry forms, YAML view, and the
  editor dialog), so a blank config is editable as intended.
- **Bulk parameter reset + CLI element-config support + integration-time mirror (Gap 93 /
  CU-153, results-neutral).** New `Sensor.reset_all(scope="user_set"|"all")` (over the new
  `ParameterSet.input_provenances()` snapshot); the GUI's Edit → Reset to Defaults is now live —
  with a current file it reverts by clean reload (exact file state), without one it clears to
  schema defaults, both behind confirmation. `radiant run`/`validate` now accept
  `optical_elements`-bearing configs (CU-153): run injects the parsed train pre-chain, validate
  checks the section through the same facade the API uses. The Readout card additionally shows
  the (shared) `spectral_integration.integration_time_s` under an "Acquisition" heading —
  presentation only, same parameter, no schema change.
- **Inline spectral tables + type-or-paste spectrum entry (owner request, ADR-0009 follow-on).**
  Element-document R/T values now accept an inline `{wavelength_um: [...], values: [...]}` table
  (persists in the YAML — no external CSV needed) alongside scalars and CSV paths. New GUI
  `SpectralTableDialog`: define a spectral response by typing rows or pasting two columns from a
  spreadsheet (live validation; λ-sorted). Wired in two places: the Optics element editor's
  **Spectrum…** button (per-row R/T λ-table) and the Detector form's **Define QE(λ) table…**
  button (writes a QE CSV and sets `detector.qe_table_path` in one call). **Fixed (latent
  engine bug):** spectral element inputs carrying their own grid (coating CSVs, inline tables)
  previously broadcast-crashed the optics stage when their grid differed from the run grid —
  `_scalar_to_spectral` now resamples onto the evaluation grid (linear, never silent
  extrapolation; a run band wider than the table raises the actionable range error). Facade
  validation/preview now runs on each entry's native grid. GUI polish: FieldRow value buttons
  are width-capped so labels no longer truncate in wide panes; element-editor Kind column locks
  to mirror on reflective rows.
- **GUI: existing-API menu wire-ups (GUI Capability Expansion plan GX-1, results-neutral).**
  Enabled four disabled menu placeholders, each one API call: File → Export YAML…
  (`Sensor.save` snapshot — does not rebind the current file), File → Export JSON Result…
  (`ChainResult.to_provenance_record` as JSON, armed once a result exists), Tools → Parameter
  Schema Browser (new read-only, filterable tree over `Sensor.parameter_defs()`, Gap 70), and
  Tools → Explain Parameter… (parameter picker → `Sensor.explain`). Run-menu sweep/MC/Batch
  placeholders stay disabled (deferred tier, owner ruling 2026-07-16); Edit → Reset to Defaults
  stays disabled pending a public provenance/reset-all accessor (new Gap 93). View-only.
- **GUI: Optics element-train editor (GUI Capability Expansion plan GS-4, results-neutral).**
  New **Elements** tab on the Optics stage: author the mixed-train element list in a table
  (per-element name, transfer mode, kind, R/T as scalar or spectral-CSV path, temperature,
  geometry); *Apply* commits through one `Sensor.set_optical_elements` call (io-parser
  validation — a Kirchhoff violation or bad file shows the actionable dialog and never touches
  the live sensor); ε is a **derived read-only** column (Rule 5); the authored train persists
  through Save/Open (ADR-0009 D4) and drives full-prescription optics on the next evaluation.
  Also fixed: an empty/directory spectral-file reference in `io/element_config.py` now raises
  the actionable `ElementConfigError` instead of leaking `IsADirectoryError` (Rule 15).
- **GUI: Source Inputs — reflective/solar pathway + scene-type declaration (GUI Capability
  Expansion plan GS-1, results-neutral).** The Source card grows from 6 thermal fields to four
  groups: Thermal (T/ε + hot-target opt-out), **Reflective (solar)** (`source.target.reflectance`
  pure-ρ pathway + `geometry.solar_illumination` day/night + solar zenith/azimuth), Background &
  contrast reference (+ `source.background.material` library name), and **Scene type & regime**
  (`source.scene_type` declared, `source.regime_override` force, fill fraction). VIS reflective
  and MWIR mixed emit+reflect scenarios are now configurable in the GUI; the ADR-0008 T2
  declared-vs-derived warning surfaces in the Messages panel. View-only — no computed value
  changes.
- **GUI: Detector Inputs expanded to the full schema (GUI Capability Expansion plan GS-3,
  results-neutral).** The Detector Inputs tab grows from 6 fields to every `detector.*`
  parameter (27), grouped: pixel geometry & temperature, QE (scalar / CSV curve import /
  temperature coefficients), dark current & glow, 1/f noise, G-R & Johnson, fixed-pattern
  noise & regime, persistence, IPC & diffusion. A manifest-equals-schema test keeps the form
  complete as the schema grows. View-only — no computed value changes.
- **GUI: Atmosphere stage Inputs card (GUI Capability Expansion plan GS-2, results-neutral).**
  The Atmosphere stage gains its first editable inputs (audit A-1…A-4): the `atmosphere.model`
  selector (`simple`/`exo`/`tabulated`/`modtran`/`interpolated`) showing only the active
  backend's parameter group (simple profile/aerosol/visibility/PWV; MODTRAN tape7 import +
  profile/aerosol/H₂O/O₃ scaling; tabulated file paths; interpolated run-matrix dir/axes/method;
  exo note) plus turbulence r₀ — all schema-driven `FieldRow`s, one `sensor.set` per edit. The
  stage also gains a scalar Outputs readout and tells propagation as before/after: pre-atmosphere
  emission (`spectral_source_emission`) beside τ/L_path and the at-aperture radiance. View-only —
  no computed value changes.
- **Optical-element document facade + config persistence (ADR-0009 / GUI plan FW-1,
  results-neutral).** New public surface for authoring the mixed-train element list as a
  declarative document: `Sensor.set_optical_elements(entries, base_dir=...)` /
  `Sensor.optical_elements()` (validate-and-attach; parsed onto the evaluation grid per run and
  injected as `optics_config.element_list`), and `radiant.api.preview_optical_elements` /
  `normalize_element_document` / `ElementPreview` (parse-for-display without mutation — feeds the
  GUI import-preview dialog; emissivity reported Kirchhoff-derived per Rule 5). The
  `optical_elements:` YAML section now **round-trips**: `Sensor.save` writes it and
  `Sensor.load` / `from_yaml` / `from_dict` re-attach it (previously the section was
  API-injection-only and vanished on save). A bare `io.config.load_config` call now **raises an
  actionable `ConfigError`** on a section-bearing config instead of the old "Unknown parameter"
  failure (never a silent skip; opt-in via new `sections_out=`); `save_config` gains
  `sections=`. `io.element_config.parse_element_entries` is the new document-level parser seam
  under `load_element_list`. Goldens byte-identical (view/plumbing only — an attached train
  changes results exactly as the same train injected manually always did).
- **Declared-vs-derived regime cross-check (ADR-0008 T2, results-neutral).** When a config
  **declares** an explicit `source.scene_type` (`extended` / `sub_pixel` / `point_source`, i.e. not
  `auto`) that disagrees with the radiometric regime the chain **derives** from the target angular
  size vs the PSF/IFOV, OpticsStage now surfaces a `UserWarning` naming both (Rule 17 — never silent).
  The run still uses the derived regime; to *force* a regime, use `source.regime_override` (the hard
  binding) rather than `scene_type` (the soft declaration). Warning-only — no computed value changes;
  goldens byte-identical. Clarifies the `scene_type` (declared intent) vs `regime_override` (hard
  force) distinction in `RADIANT_Source_Target_System` §8.10.
- **RADIANT Desktop GUI v1 — complete (GUI Development Plan closed, view-only capability).**
  `radiant gui [config.yaml]` launches the PySide6 contextual per-stage workspace: a 9-stage
  geometry-first strip, a schema-driven All-Parameters tree, per-stage **instruments** for all
  nine stages at the Geometry gold standard (Inputs → one `sensor.set` per edit / unit-carrying
  Outputs from `stage_outputs` / stage plots from `result.plot.*`), a persistent right rail
  (pinned metric cards, Edit-Config-YAML modal, Messages, Evaluate footer), the 2D `QPainter`
  geometry schematic viewer (ADR-0007), the embedded scripting window (Command Window + Workspace
  + multi-tab script Editor), and full File round-trip / undo-redo / light-dark theme toggle. The
  four framework-plot additions that back the Source and Optics instruments ship as public
  accessors — `result.plot.spectral_source_emission()` (Gap 91), `pupil_amplitude()` / `pupil_phase()`
  (Gap 89), `optical_throughput()` / `coating_spectra()` (Gap 90), plus `noise_pie()` /
  `psf_pixel_grid()` — reusable from any script or the console. The GUI is a pure view over the
  scripting API (one action ↔ one API call); **golden results are byte-identical to pre-GUI**.
  Out-of-v1 GUI features and the v1.1 Sweep/Batch tab are tracked in `docs/tracking/gaps.md`
  (GUI-1…GUI-17); the completed plan is archived at `docs/archive/GUI_Development_Plan.md`. The
  entries below record the individual phases that composed this capability.
- **GUI scripting window — Pass 2: the multi-tab script Editor (arch doc §4.6.1, view-only).**
  The scripting window now hosts all three MATLAB-style panes: a new **Editor** (top pane) over
  the Pass-1 Command Window + Workspace. The Editor opens, writes, saves, and **runs** multiple
  Python scripts at once — a tabbed set of `.py` buffers each with a file name + unsaved-edits
  (`*`) marker, plain-text **New / Open / Open Recent / Save / Save As** (a persisted
  recent-scripts list, kept distinct from the config recent list), syntax highlighting, and a
  File/Run menu + toolbar (Run = F5 / ⌘⏎, Run Selection). **Run** executes the active tab in the
  *same* namespace the Command Window and Workspace share, so a script's `x = result.snr()`
  leaves `x` usable at the command line and visible in the Workspace; stdout/stderr and any
  traceback route to the Command Window (surfaced, not swallowed), and a `sensor.set(...)` in a
  script marks the main GUI stale exactly like a typed command. Completes the ratified
  scripting-window vision (CU-143 closed).
- **GUI scripting window — Pass 1: separate window + Command Window + Workspace (arch doc
  §4.6.1, view-only).** The MATLAB-style scripting environment is now a **separate top-level
  window** ("RADIANT Scripting"), launched from **Tools → Scripting Window** (`Ctrl+Shift+P`)
  — movable to a second monitor, and re-launching raises the single existing instance rather
  than spawning a duplicate. It hosts the reused **Command Window** REPL (live
  `sensor`/`result`/`plot`/`inspect_result`, history, figure pop-out) beside a new live
  **Workspace** variable browser that lists each namespace variable's name, type, and a short
  value/size summary (e.g. `x: ndarray (500,)`, `snr: float 616.0`), refreshing after each
  command and after every evaluate/refresh, with a detail dump (a `ChainResult`'s inspect
  tree, else `repr`) for the selected variable. A `sensor.set(...)` typed in the window still
  marks the main GUI stale and offers one-click Refresh (coherence unchanged). The multi-tab
  script Editor is Pass 2 (deferred, CU-143).
- **GUI file round-trip, undo/redo, and the light/dark theme toggle (GUI plan Phase 9, arch
  doc §10, view-only).** The **File** menu is complete: New, Open, **Open Recent** (persisted
  across launches via `QSettings`), Save, and Save As — all file I/O through `Sensor.load()` /
  `Sensor.save()` only (one action ↔ one API call, §4.1). The window **title** shows the current
  config's file name with a `*` **dirty marker** that sets on any edit (tree, stage form, YAML
  editor, console) and clears on save; Open / New swap the sensor through the shared adopt path
  so every panel + the console rebind and re-evaluate, and a bad file surfaces an actionable
  error (Rule 15). **Edit → Undo / Redo** (Ctrl+Z / Ctrl+Shift+Z) reverse the last ~20 parameter
  edits via a `QUndoStack` of named `sensor.set` commands (each labelled e.g. *"Set
  optics.aperture_diameter_m = 0.5 m"*); an undo re-reads the value into the parameter panel/forms
  and re-evaluates. Whole-config swaps (Open / New / YAML-editor Apply / console Refresh) clear the
  undo history (documented — explicit beats a fragile merge). **View** menu: a **light/dark theme
  toggle** that re-applies the design-system QSS + palette, re-themes the custom-painted widgets
  (the 2D schematic viewer and the detector pixel illustration via their `set_theme`), and
  persists the choice (`QSettings`) so the next launch reopens in the same theme; plus panel
  show/hide (Parameter Panel F6, Right Rail F7, both persisted) and stage-jump shortcuts
  (Ctrl+1..9). New public entry surface: `launch_gui(sensor, path=...)` threads the launched
  config path into the title/recent list. Golden suite untouched (a view over the scripting API;
  no physics, schema, or result changed).
- **GUI embedded scripting console (GUI plan Phase 8, arch doc §4.6.1, view-only).** A
  MATLAB-style command window as a **global tool** — a dockable `ScriptingConsole` (bottom
  `QDockWidget`, hidden at launch) opened from **Tools → Python Console** (`Ctrl+`` ` ``) or the
  View-menu toggle; enabled once a sensor is loaded. Its REPL namespace binds live objects:
  `sensor` (the window's live `Sensor`), `result` (the last `ChainResult`, re-bound after each
  evaluation), `plot` (`ResultPlotNamespace(result)` — the public `result.plot.*` figure surface),
  plus `inspect_result` and `Sensor` conveniences. A command that returns a matplotlib `Figure`
  (e.g. `plot.mtf()`) pops out into its own window. **GUI ↔ console coherence** is explicit, not
  magic: after a command that mutates the sensor the console shows a *"console changed state —
  Refresh"* banner and the window marks itself stale (stage dots + status bar); one-click
  **Refresh** adopts the console's current `sensor` (covering both in-place `sensor.set(...)` and a
  full `sensor = Sensor.load(...)` rebind), re-reads it into the parameter tree + input forms, and
  re-evaluates. **Decision (CU-138):** shipped as a REPL over `code.InteractiveConsole`, not the
  preferred `qtconsole` in-process kernel (not installed here + fragile/untestable under the
  offscreen QPA) — the plan-sanctioned fallback; the `qtconsole` pin is retained for the deferred
  kernel path. Golden suite untouched (a view over the scripting API).
- **GUI Platform + Readout stage instruments (GUI plan Phase PS-5, arch doc §4.4.1
  Platform/Readout rows, v1-minimal, view-only).** Both stages' contextual centers become clean
  minimal instruments (single flat panes): editable schema-driven inputs as shared `FieldRow`s
  beside the scalar outputs readout and a themed *v1-minimal* note. **Platform** — a new
  `PlatformInputsForm` (jitter RMS isotropic + cross/along-track under a *Jitter* heading,
  `ground_velocity_m_s` + `smear_length_um` under a *Motion & smear* heading) beside the
  outputs (`jitter_sigma_x_m`/`jitter_sigma_y_m`/`smear_width_m` in m, `EE_box` fraction); no
  dedicated MTF (owner-ratified — the smear/jitter MTF terms stay in the Optics/Performance
  overlays). **Readout** — a new `ReadoutInputsForm` (`read_noise_e_rms` under *Read noise*,
  `gain_e_per_dn` + `adc_bits` under *ADC*, `full_well_capacity_e` under *Full well*) beside the
  outputs (`signal_dn_final` DN, `sigma_total_e`/`total_well_e` e-, `well_fill_fraction`, …) and
  the scalar noise budget (`result.plot.noise_budget()` — read noise + quantization live in this
  stage; §4.7 relocates the Noise Budget detail tab to the Detector/Readout views). Editing any
  input is one `sensor.set` (validate-on-a-clone reject discipline) and re-evaluates so the
  outputs (and the Readout noise budget) refresh (edit-and-watch). Group headings are a
  presentation choice only — **no schema change**. Golden suite untouched (view over the API).
- **GUI Performance stage instrument metric-failure surfacing (GUI plan Phase PS-6, arch doc
  §4.4.1 Performance row, view-only).** The Performance center's metric summary
  (`OutputsReadout.show_metrics` over `result.metric_records()`) now renders a **result-typed
  metric failure** — a non-finite metric value (Rule 17 carve-out for the `radiant.performance`
  metric layer, e.g. an SNR/NEDT that could not compute) — as `n/a (<failure_reason>)`, reading
  the structured `failure_reason` from the metric's result object (`stage_outputs["performance"]`),
  never a bare `nan` and never a blank. Finite metrics render value + registry unit unchanged
  (SNR/NEDT/NIIRS/GSD/MTF@Nyquist and every other `metric_records()` entry), above the system-MTF
  (`result.plot.mtf()`) and MTF-budget (`result.plot.mtf_budget()`) plots. This completes all nine
  per-stage instruments. Golden suite untouched.
- **GUI Spectral-Integration stage instrument (GUI plan Phase PS-4, arch doc §4.4.1
  Spectral-Integration rows, view-only).** The Spectral-Integration stage's contextual center
  becomes an instrument (a single flat pane, owner judgment): editable band + acquisition
  inputs (a new `SpectralIntegrationInputsForm` — the filter bandpass edges
  `spectral_integration.filter_min_um` / `filter_max_um` under a *Filter bandpass* heading and
  `integration_time_s` under an *Acquisition* heading, per the §4.4.1 GUI-grouping note — as
  shared `FieldRow`s), the scalar electron-budget outputs readout (`signal_e`, `e_rate_per_s`,
  `background_e`, `contrast_e`, `qe_scalar`, …, units from `api.stage_output_units`), the in-band
  signal spectral radiance as the primary plot (`result.plot.spectral_inband()`), and a themed
  note that the per-λ noise spectrum is deferred (Gap 92; noise is scalar per term, computed once
  post-integration — Rule 8). Editing any input is one `sensor.set` (validate-on-a-clone reject
  discipline) and re-evaluates, so the in-band spectrum re-clips to the new band and the electron
  budget re-scales with the integration time (edit-and-watch). The `integration_time_s` grouping
  is a presentation choice only — **no schema change** (the sensor path is unchanged). Golden
  suite untouched (the GUI is a view over the scripting API).
- **`result.plot.noise_pie()` framework accessor (GUI plan Phase PS-3 Part A, owner-ratified
  §8 decision 2, results-neutral).** A new pie-chart accessor on `ResultPlotNamespace` (builder
  `radiant.api.plot.plot_noise_pie`), the pie sibling of the shipped `noise_budget()` bar over
  the same `result.noise_terms` data. Presentation choice (documented): noise adds in
  **quadrature** (σ_total² = Σ σ_i²), so the slices are proportional to each term's **variance**
  (σ_i²) and sum to 100 % of the noise **power**; each wedge is labelled with the term name, its
  σ_i in **e- RMS**, and its % of the variance (zero terms omitted). Raises `ApiValidationError`
  when the result carries no noise terms. Purely additive — no computed result changes; the
  golden suite is byte-identical.
- **`result.plot.psf_pixel_grid()` framework accessor (GUI plan Phase PS-3 Part B,
  results-neutral).** `psf()` with the **detector pixel grid** overlaid — pixel-boundary
  gridlines at the detector pixel pitch (`EffectivePSF.pixel_pitch_m` over samples spaced at
  `sample_spacing_m`), cropped to the PSF core, with the pitch (µm) in the title. Implemented as
  an optional `pixel_grid` parameter on `plot_psf` (default `False` leaves the shipped image
  unchanged). A view over already-computed data — no results change.
- **GUI Detector stage instrument (GUI plan Phase PS-3, arch doc §4.4.1 Detector rows,
  view-only).** The Detector stage's contextual center becomes a tabbed instrument (the §4.4
  sub-view hook, now used by Geometry, Optics, and Detector): three tabs — **Inputs** (editable
  detector `FieldRow`s — quantum efficiency / dark rate / pixel pitch x,y / fill factor /
  detector temperature — beside the scalar outputs readout, `signal_e`/`dark_e`/…), **Noise**
  (the ratified `noise_pie()` variance pie as the primary chart above the per-term table +
  click-to-explain; the redundant bar is suppressed), and **Detector + PSF** (a new Qt-drawn
  pixel illustration labelled with the pitch in µm + fill factor, beside `psf_pixel_grid()`).
  Editing any detector input is one `sensor.set` (validate-on-a-clone reject discipline) and
  re-evaluates, so every tab refreshes — editing the dark rate shifts the noise pie, editing the
  pixel pitch redraws the illustration and the PSF grid (edit-and-watch). New widgets
  `DetectorInputsForm`, `DetectorIllustration`; `NoiseBudgetPanel` gains a `show_chart` toggle.
  Golden suite untouched (the GUI is a view over the scripting API).
- **GUI Optics stage instrument (GUI plan Phase PS-2, arch doc §4.4.1 Optics rows,
  view-only).** The Optics stage's contextual center becomes the richest per-stage view and
  the **first production use of the tabbed sub-view hook** (`StageComposition.subviews`): four
  tabs — **Inputs** (editable optics `FieldRow`s — aperture / focal length / f-number /
  obscuration / spiders / scalar throughput / WFE / optics temperature — beside the
  **FINAL-regime** outputs readout, `stage_outputs["optics"]["regime"]`, Rule 10), **MTF** (the
  per-term MTF@Nyquist table + `mtf()` overlay via `MtfPanel`, plus the `mtf_budget()` bar),
  **PSF + Pupil** (`psf()` beside the FP-2 `pupil_amplitude()` apodization map and
  `pupil_phase()` wavefront-error map in waves), and **Throughput** (the FP-3
  `optical_throughput()` τ_opt(λ) + per-element `coating_spectra()`). Editing any optics input
  is one `sensor.set` (validate-on-a-clone reject discipline) and re-evaluates, so every tab
  refreshes — editing `wfe_rms_waves` makes the pupil-phase map gain structure, editing the
  aperture updates MTF/PSF, editing the coating updates throughput (edit-and-watch). New widget
  `OpticsInputsForm`; the `optics` composition gains its four `StageSubView` tabs (the hook is
  now used by Geometry and Optics). Golden suite untouched (the GUI is a view over the scripting
  API).
- **GUI Source stage instrument (GUI plan Phase PS-1, arch doc §4.4.1 Source rows,
  view-only).** The Source stage's contextual center is brought to the Geometry-screen
  standard. It now shows: the pre-atmosphere **target + background emission spectra**
  (`result.plot.spectral_source_emission()`, FP-1) as the primary plot, with the at-aperture
  radiance (`spectral_source()`) kept as a secondary plot; editable **radiometric inputs**
  (`source.target`/`background`/`contrast_reference` ε & T) as shared `FieldRow`s, one
  `sensor.set` per edit with the validate-on-a-clone reject discipline; the shared
  **shape / size / orientation** editor (`source.target.shape*`) — the same `TargetShapePanel`
  the Geometry Schematic tab mounts, with nominal-dim seeding on shape-select (CU-125); and an
  **Outputs readout** carrying the tentative regime (`stage_outputs["source"]["regime_tentative"]`,
  Rule 10) plus `projected_area_m2`/`range_m`/`fill_fraction`/`angular_extent_rad`, each with its
  unit. Editing any input re-evaluates and the spectra + readout refresh (edit-and-watch). New
  widgets `TargetShapePanel` (factored out of the Geometry `GeometryAnglePanel` — one
  target-shape editor, two homes, Rule 19) and `SourceInputsForm`; `OutputsReadout` now renders
  an enum output (the regime) by its value; `radiant.api.stage_output_units` gains the Source
  scalar-output units. Golden suite untouched (the GUI is a view over the scripting API).
  Per-scenario-type input relevance stays deferred (Gap 85).
- **Complex-pupil diagnostic maps + `result.plot.pupil_amplitude()` / `pupil_phase()` (Gap 89,
  GUI plan Phase FP-2).** `OpticsStage` now persists the two diagnostic faces of the complex
  pupil it already builds for the MTF autocorrelation: `pupil_amplitude` (dimensionless
  apodization/transmission mask — central obscuration, spider vanes, and any measured
  `pupil_mask_override` included) and `pupil_phase_waves` (the wavefront-error map in **waves**,
  `phase_radians / 2π`, at `pupil_wavelength_um` — band centre for polychromatic runs — masked
  to zero outside the clear aperture), plus `pupil_plane_extent_m` (physical pupil diameter for
  axis scaling) in `stage_outputs["optics"]`. New public accessors
  `ResultPlotNamespace.pupil_amplitude()` (colorbar "transmission (dimensionless)") and
  `pupil_phase()` (colorbar "wavefront error (waves)"), mirroring `psf()` (2-D imshow +
  colorbar). Purely additive diagnostic views captured verbatim from the same arrays the
  autocorrelation consumes — never read back into the PSF/MTF path (Rule 4 untouched); the full
  golden suite is **byte-identical**. Also renames the internal
  `pupil_mtf._resolve_wfe_for_wavelength` → `resolve_wfe_for_wavelength` (module-internal helper,
  no public surface).
- **Optics coating / throughput spectra — `result.plot.optical_throughput()` /
  `coating_spectra()` (Gap 90, GUI plan Phase FP-3).** Two additive view accessors on
  `ResultPlotNamespace` render the optics `SpectralData` OpticsStage already stores, with no
  physics or results change. `optical_throughput()` plots the assembled system transmission
  `stage_outputs["optics"]["tau_opt_spectral"]` — τ_opt(λ) [dimensionless] — vs wavelength.
  `coating_spectra()` overlays, per element in `stage_outputs["optics"]["elements"]`, its
  reflectance R, transmittance T, and Kirchhoff-derived emissivity ε (`element.emissivity`;
  ε = 1 − R for mirrors, declared train ε for lumped, 0 for simple refractives) — all
  dimensionless on one y-axis; an identically-zero curve is omitted (a mirror shows R + ε, a
  simple refractive shows T + R). New plot builders `plot_optical_throughput` /
  `plot_coating_spectra` in `radiant.api.plot`. Each accessor raises `ApiValidationError` when
  the optics outputs / elements are absent. Purely additive: the golden suite is
  **byte-identical**.
- **Pre-atmosphere source-emission frames + `result.plot.spectral_source_emission()` (Gap 91,
  GUI plan Phase FP-1).** `AtmosphereStage` now persists two additive `RadiometricFrame`s —
  `at_source_target` (always) and `at_source_background` (when a background descriptor is
  present) — carrying the emitted+reflected spectral radiance *leaving the source*
  (`L_source`, W/m²/sr/µm) **before** the atmospheric up-leg, satisfying
  `at_aperture_target ≈ τ_up · at_source_target + L_path_up`. New public accessor
  `ResultPlotNamespace.spectral_source_emission()` draws the target (+ optional background)
  emission spectrum, isolating what the target emits from what reaches the aperture (vs the
  post-atmosphere `spectral_source()`). New assembly functions
  `assemble_target_source_emission` / `assemble_background_source_emission`. Purely additive:
  the new frames feed no metric and the full golden suite is **byte-identical** (505/505
  integration tests pass unchanged).
- **GUI geometry schematic — ground vectors for elevated targets (owner feedback 2026-07-14,
  view-only).** When the target is above the ground (`geometry.target_altitude_m > 0`) the
  Schematic tab now additionally draws a **SENSOR→GROUND** vector (blue, dashed) and a
  **SUN→GROUND** vector (amber, dashed), both landing at the target's **ground projection**
  (nadir footprint, directly below the body on the ground plane). The VECTORS legend gains
  matching rows, shown only when the vectors are present. A ground target (altitude 0) has
  target == ground, so the two vectors are degenerate and absent — unchanged behaviour there.
  Colours come from the allowlisted physics palette (sensor = blue, sun = amber). Golden
  untouched (the GUI is a view over the scripting API).
- **GUI geometry Schematic tab — editable + nominal shape dims (owner feedback 2026-07-14,
  view-only).** Three changes to the Geometry stage's Schematic tab (golden untouched — the
  GUI is a view over the scripting API): (1) **Geometry is now settable from the Schematic
  tab.** Its side panel gains a **Geometry inputs** accordion page hosting the reusable
  Phase-5 `GeometryModeForm`, wired through the same edit → one `sensor.set` → debounced
  re-evaluate → schematic re-render path as the Inputs tab, so the user can edit geometry and
  watch the schematic + arcs move. Both geometry forms (Inputs + Schematic) read the one live
  sensor and re-sync on the next clean evaluation. New public GUI surface:
  `GeometryAnglePanel.geometry_form` property; `StagePane.refresh_geometry_forms`. (2)
  **Shapes load with nominal dimensions (CU-125).** Selecting a target shape whose required
  dimensions are still the `0.0` "not set" sentinel now seeds them to nominal non-zero values
  (`geometry_angle_panel.NOMINAL_SHAPE_DIMENSIONS`) — one `sensor.set` each, only where unset,
  never overwriting a user value — so the re-evaluate succeeds instead of tripping the
  `radiant.source` shape factory. The schema keeps the `0.0` Rule-12 default; the nominal map
  is a GUI-side UX default only.
- **GUI geometry schematic — Pass 2 (annotations + shape editing; ADR-0007, view-only).**
  The 2D orthographic schematic gains the annotations and shape-editing the mockup/owner
  specify. (1) **Angle arcs + degree labels (CU-128):** revealable arcs for off-nadir η,
  sun-zenith θ_s, relative-azimuth Δφ (ground), and phase α_t, each drawn with the ported
  projection math but labelled with the angle **value from `stage_outputs["geometry"]`**
  (bound verbatim into `ViewerState`) shown in **degrees** (§6.3); the phase arc is
  symbol-only (no stage-output phase angle). The side-panel angle toggles now reveal/hide
  the arcs and repaint. (2) **Altitude leader labels (CU-129):** `h_s` / `h_t` pills in
  km/m, the not-to-scale magnitude annotation (§6.1). (3) **Full shape library + ALL
  dimension inputs (CU-131 + owner request):** the schematic draws distinct
  sphere/box/cylinder/cone/flat-plate wireframes (aspect ratio from the shape's own dims,
  never metric magnitude), and the side panel exposes every relevant dimension input for
  the selected shape (radius / length / width / height / base-radius), showing only the
  subset the shape uses, each one `sensor.set` per edit. (4) **RPY triad (CU-130):** the
  on-target body-axes gizmo (roll +X′ pink / pitch +Y′ green / yaw +Z′ purple) from
  `source.target.shape_{yaw,pitch,roll}_rad`, with the body wireframe rotated by the same
  ZYX Euler. New public GUI surface: `GeometryAnglePanel.dimensionRequested` signal +
  `set_dimension_bounds`/`set_dimensions`/`dimension_spin`; `SchematicView.set_revealed_angles`;
  new modules `radiant.gui.viewer.angle_catalog` / `radiant.gui.viewer.angle_truth`. A
  **binding angle-truth consistency test** asserts the viewer's local angle recomputation
  agrees with `stage_outputs["geometry"]` within `ANGLE_CONSISTENCY_ABS_TOL_RAD = 1e-9` rad
  (measured residual ~1e-16). No computed results change (the stage remains the single
  source of angle truth); golden untouched.

### Removed
- **`gui` extra no longer pins `pyvista` / `pyvistaqt` (CU-134, GUI plan Phase 9).** The 2D
  `QPainter` schematic viewer (ADR-0007) replaced the PyVista/VTK 3D viewer, and no
  `radiant.gui` module imports pyvista/pyvistaqt/vtk (grep-guarded by
  `test_no_pyvista_import_in_gui`), so the two pins were dropped from the optional `gui`
  extra. `pip install "radiant[gui]"` no longer pulls the VTK native dependency chain;
  `matplotlib` and `qtconsole` remain pinned. No runtime behavior change (the pins were unused).
- **GUI geometry Schematic tab — redundant derived-angles table removed (owner feedback
  2026-07-14, view-only).** The Schematic tab's side panel no longer carries the derived
  "Geometry — derived angles & ranges" `GeometryReadout` (it duplicated the Inputs tab; the
  key derived values surface on the schematic itself as arc degree labels + altitude leader
  labels). The angle-arc reveal toggles remain; the Inputs-tab readout is unchanged. Removed
  public GUI surface: `GeometryAnglePanel.readout` property + `populate_readout` method.
- **GUI lifted VTK/PyVista scene library removed (CU-132, ADR-0007 Rule 27).** The
  superseded `radiant.gui.viewer.scene` render library (~3.9 kLoC across `builder`,
  `arcs/`, `frames/`, `glyphs/`, `ground/`, `labels/`, `target/`, `vectors/`) is deleted now
  that the 2D `QPainter` schematic fully replaces it; only the allowlisted glyph-colour
  module `radiant.gui.viewer.scene.palette` survives. `radiant.gui.viewer` no longer imports
  `pyvista`/`pyvistaqt`/`vtk` (the `gui`-extra pins are retained pending a dependency-drop
  audit — CU-134).

### Changed
- **Target spatial extent moved from the `source.target.*` to the `geometry.target.*` parameter
  namespace (ADR-0008 Phase A, public surface — goldens byte-identical).** The target's shape,
  dimensions, orientation, and projected area — `shape`, `shape_radius_m`, `shape_length_m`,
  `shape_width_m`, `shape_height_m`, `shape_base_radius_m`, `shape_yaw_rad`, `shape_pitch_rad`,
  `shape_roll_rad`, `projected_area_m2` — are now defined under `geometry.target.*` (the Geometry
  stage owns the extent → projected-area → angular-subtense chain). The old `source.target.*`
  names keep working as **deprecated aliases** (a `DeprecationWarning` redirects them; provenance
  records the canonical name). The **spectral/material** target params (`source.target.temperature`,
  `emissivity`, `reflectance`, BRDF) and the sub-pixel `source.target.fill_fraction` are **unchanged**
  — the namespace was split, not renamed wholesale. Results-neutral: this relocates parameter
  definitions only; no computation changed and the full golden suite is byte-identical. Closes the
  §8 inventory drift (CU-146).
- **GUI scripting window — Editor Run auto-displays top-level bare expressions (arch doc §4.6.1,
  view-only).** A whole-script **Run** now behaves like the command line: `run_script` executes the
  source one top-level statement at a time, so a bare expression on its own line (e.g. `plot.mtf()`
  or `result.snr()`) fires the display hook — a Figure pops out into its own window, any other value
  echoes its `repr`, `None` stays silent. A script's bare `plot.mtf()` therefore pops its figure with
  **no** `show()` / `sys.displayhook(...)` wrapper (the MATLAB "run a script, see the plots"
  behaviour). Statement order and side effects are preserved; the explicit `sys.displayhook(fig)`
  pattern still works; a runtime exception still surfaces its traceback and halts the run (Rule 17).
- **GUI: `Tools → Python Console` (a bottom dock) → `Tools → Scripting Window` (a separate
  window), view-only.** The menu action is renamed and repurposed to open the new separate
  scripting window (action key `tools.console` → `tools.scripting_window`, shortcut unchanged
  at `Ctrl+Shift+P`). The old `View → Show/Hide Python Console` dock toggle (`view.toggle_console`)
  and the bottom-dock console host (`consoleDock`) are removed (Rule 27); the launcher replaces
  them. No change to the REPL's behaviour, binding, or coherence model.
- **GUI geometry Schematic tab — Target shape & orientation fields restyled to match the
  Geometry inputs (owner feedback 2026-07-14, view-only).** The **Target shape & orientation**
  accordion page's controls previously rendered with default-Qt chrome (a plain combo, and
  `QDoubleSpinBox`es with native up/down arrows for the dimension and yaw/pitch/roll values),
  which looked nothing like the styled **Geometry inputs** fields. They are now built from the
  **same** building blocks as the `GeometryModeForm`: `geoModeFamily` cards, a
  `geoModeSelector`-styled shape combo, and the shared `FieldRow` (label + value button) —
  factored into a new `radiant.gui.widgets.field_row` module (`FieldRow`, `ElidingLabel`) that
  both surfaces import, so they cannot visually diverge again. Editing a dimension or RPY value
  now opens the shared `ParameterEditorDialog` (value + unit + validate-on-a-clone reject path,
  one `sensor.set` on commit) instead of a bare spin box, matching the Inputs-tab fields.
  Changed public GUI surface: `GeometryAnglePanel` replaces its `dimensionRequested(str,float)`
  / `orientationRequested(str,float)` signals + `dimension_spin` / `rpy_spin` accessors with a
  single `editRequested(str)` signal + `dimension_row` / `rpy_row` (returning `FieldRow`), and
  drops `set_orientation_bounds` / `set_dimension_bounds` (the dialog now enforces schema
  bounds). Golden untouched (the GUI is a view over the scripting API).
- **GUI geometry Schematic tab — angle-arc selector moved to a plot overlay (owner feedback
  2026-07-14, view-only).** The angle-arc reveal toggles (θ_s sun zenith, Δφ relative
  azimuth, α_t phase angle, η off nadir) moved **out** of the right-column accordion's
  "Angles" page and **onto the schematic plot** as a compact **bottom-left overlay**
  (`AngleToggleOverlay`, new module `radiant.gui.viewer.angle_overlay`), mirroring the
  top-left VECTORS legend. It is a real child `QWidget` on the `SchematicView` canvas,
  repositioned bottom-left on resize, and stays interactive — each checkbox still reveals its
  arc via `GeometryViewer.set_angle_revealed` (reveal path unchanged). The right-column
  accordion now holds only the **Geometry inputs** and **Target shape & orientation** pages.
  Removed public GUI surface: `GeometryAnglePanel.angleToggled` signal + `angle_checkbox`
  accessor (both now on `SchematicView.angle_overlay`). Golden untouched (the GUI is a view
  over the scripting API).
- **GUI geometry viewer reimplemented as a 2D orthographic schematic — view-only
  (ADR-0007 superseded 2026-07-14, Pass 1).** The Geometry stage's viewer is no longer a
  PyVista/VTK render but a crisp, antialiased **2D orthographic line-schematic** drawn with
  `QPainter`, porting the `geometry_viewer` mockup's `geometry.js` projection (new modules
  `radiant.gui.viewer.projection` + `radiant.gui.viewer.schematic_view`). The Geometry
  center tab is renamed **"3D View" → "Schematic"**. Pass 1 draws the ground grid, X/Y/Z
  axes, the four labelled vectors (sun→target, sensor→target, sun→ground, zenith),
  sun/sensor glyphs, a wireframe target (sphere/box/point), ground drop-lines, and the
  VECTORS legend, with orthographic yaw/pitch by mouse drag. The `GeometryViewer` public
  surface (`show_result`, `set_angle_revealed`/`set_triad_visible` as Pass-2 no-op-safe
  stubs, `close_viewer`, `set_theme`) and the `ViewerState` adapter are preserved. The
  three-backend "3D viewer unavailable" degradation ladder is removed — a pure-Qt canvas
  has no VTK/OpenGL dependency and renders/tests faithfully headless. No computed results
  change (the stage remains the single source of angle truth). Deferred to Pass 2: angle
  arcs, altitude leader labels, RPY triad, shape library + dimensions, the angle-truth
  test, and removal of the now-unwired lifted VTK scene library (CU-128–CU-133).

### Fixed
- **GUI: three widget validation guards now raise a `RadiantError` subclass, not bare
  `ValueError` (Rule 15).** `HealthDot.set_status`, `StageChip.set_status`, and the `StageStrip`
  namespace-drift check raised bare `ValueError`, tripping the `tests/test_exceptions.py`
  no-bare-builtin-raises guard on the full suite (they were missed by the scoped GUI test runs).
  New `radiant.gui.errors.GuiValidationError(RadiantError, ValueError)` (mirrors
  `SourceValidationError`) — co-inherits `ValueError` so any `except ValueError` still works.
  Also fixes a stale `test_gui_cli` double whose `fake_launch` did not accept the `path=` kwarg
  the CLI passes since the Phase-9 `launch_gui(sensor, path=...)` signature. No behavior change.
- **GUI scripting console now opens on macOS (owner report 2026-07-15, view-only).** The
  **Tools → Python Console** shortcut was the portable ``Ctrl+` ``, which Qt maps to ⌘` on
  macOS — an OS-reserved shortcut (cycle windows) that never reaches the app, so the console
  "wouldn't open". Rebound to **Ctrl+Shift+P** (⌘⇧P on macOS; unreserved and free on
  Windows/Linux, no collision with existing bindings). The reveal path is also hardened so
  the menu item and shortcut always produce a clearly-visible console: the dock is raised
  front-most and resized to a usable height on reveal, and the console carries a ≥180 px
  minimum height so it is never a zero/sliver-height strip. Golden untouched.
- **GUI geometry Schematic tab — inputs no longer clipped horizontally (owner bug
  2026-07-14, view-only).** The right-column "Geometry inputs" form was wider than its
  accordion column, so the value fields (e.g. `8000 m`, `1.5708 rad`) were cut off behind a
  horizontal scrollbar. The mode-selector combos and field-value editors now size to the
  available column width (expanding, minimum-contents sizing) instead of forcing their
  content width, the long form title wraps, and the raw dot-path field labels elide (full
  name on hover) — so the form fits its column and scrolls only vertically when tall, never
  clipping horizontally. Golden untouched.
- **GUI geometry schematic — centred + framed, no longer bottom-anchored (view-only).**
  The 2D orthographic schematic rendered anchored to the *bottom* of its panel with the
  canvas above it empty (owner screenshot 2026-07-14). Two compounding causes fixed:
  (1) the schematic canvas ballooned taller than its tab viewport — the Geometry
  "Schematic" tab shares a `QTabWidget` stack with the tall "Inputs" tab, whose full-height
  derived-angles readout inflated the shared minimum height; each non-canvas sub-view is now
  wrapped in its own `QScrollArea` so the canvas fills the viewport (with a sensible
  `Expanding` policy + 360×360 minimum + concrete `sizeHint`) instead of growing unbounded;
  (2) the orthographic fit anchored the scene origin low (`cy = 0.72·height`) with a
  width-limited scale, so on a too-tall canvas the scene clustered near the bottom — the
  camera now scales the projected scene bounding box to the *live* paint rect with a
  symmetric margin and centres it on both axes, recomputed every paint so the scene stays
  centred and framed on resize (short / tall / wide). No computed results change; golden
  untouched.

### Added
- **GUI 3D geometry viewer — interactions: angle annotations, shape library, RPY triad
  (GUI plan Phase 7 Part B, ADR-0007).** The Geometry "3D View" becomes a split of the
  viewport and a new accordion side panel (`GeometryAnglePanel`). (1) **Click-to-reveal
  angle annotations:** per-angle toggles reveal an arc (off-nadir η, sun-zenith θ_s,
  phase-angle α_t) with the numeric value pinned from `stage_outputs["geometry"]` verbatim
  (never recomputed; the phase angle is symbol-only as it has no stage-output truth), split
  target-frame vs ground-frame to match the Phase-5 readout — which the panel **shares**,
  not duplicates. (2) **Target shape library:** a shape combo populated from the
  `source.target.shape` schema `enum_values`; selecting a shape performs one `sensor.set`
  and re-renders. (3) **RPY triad:** an on-target body-axes gizmo (pink=Roll / green=Pitch /
  purple=Yaw) rendered from `source.target.shape_{yaw,pitch,roll}_rad`; editing those tilts
  the triad and the orientation-dependent geometry. A **binding consistency test** asserts
  the viewer's local angle recomputation (ported `geometry.js` math, used only for
  camera/picking) agrees with the stage outputs within 1e-9 rad — the stage is the single
  source of angle truth. In-scene VTK picking and platform-attitude are deferred
  (CU-124/CU-122). View-only — no computed results change.
- **GUI 3D geometry viewer — static bound scene (GUI plan Phase 7 Part A, ADR-0007).** The
  Geometry stage center becomes a two-tab composite — **Inputs** (the mode forms + angle
  readout) and **3D View** — the latter embedding a new `GeometryViewer`
  (`radiant.gui.viewer`). It renders a not-to-scale PyVista schematic of the sun / sensor /
  target geometry (ground reference, target/regime glyph, the four vectors, sun/sensor
  glyphs, deconflicted leader labels) bound to `stage_outputs["geometry"]` + the final
  optics regime after each evaluate, via the new `ViewerState` adapter. The Qt-free scene
  library is lifted from `dev_tools/geometry_gui_v2` into `radiant.gui.viewer.scene`
  (imports no physics stage; gui → api + core kept). Viewport background and label/leader
  chrome follow the design-system `Theme`; the physics-domain glyph palette
  (sun = amber, sensor = blue, normal = green, target = teal) lives in one allowlisted
  module. Three render backends (live `QtInteractor` / static offscreen image / actionable
  degradation panel) keep the app alive where OpenGL/VTK is unavailable. `StageComposition`
  and `StageSubView` gained a `geometry_viewer` field. Angle-arc annotations, the shape
  library, and the RPY triad are deferred to Part B. View-only — no computed results change.
- **GUI Geometry screen — stage-0 input-mode forms + frame-grouped derived-angle readout
  (GUI plan Phase 5).** The Geometry stage's contextual center gains a `GeometryModeForm`
  (new `radiant.gui.widgets.geometry_mode_form`, over a Qt-free `radiant.gui.geometry_modes`
  manifest): a mode selector per family (viewing V0–V4 / solar S1–S3+night / kinematics
  direct-or-circular) with only the active mode's fields editable, all fields schema-driven,
  each edit one `sensor.set` through the shared Parameter Editor (validate-on-clone reject,
  display-unit aware). The `GeometryReadout` now groups its values by reference frame
  (target-frame vs ground/platform frame vs resolution), each with unit and symbol. An
  over-/under-specified geometry (the stage's `GeometrySpecificationError`) highlights the
  offending mode selector and navigates to the Geometry screen. `StageComposition` gained a
  `geometry_form` field. View-only — no computed results change.
- **GUI per-stage center tabbed sub-view hook (provision only, deferred content).** A stage's
  center composite can now be presented as multiple named tabs: `StageComposition` (in
  `radiant.gui.stage_views`) gained an optional `subviews` field of the new `StageSubView`,
  and `StagePane` renders a `QTabWidget` when two or more are declared, falling back to the
  current single pane otherwise. **No v1 stage declares any sub-view** — every stage renders
  exactly as before; this is the seam a later per-stage phase fills. View-only — no computed
  results change.
- **`radiant.api.stage_output_units.stage_output_unit(stage, key)` — canonical display unit
  for a scalar stage output.** Stage outputs are computed values with no per-field unit
  metadata (Gap 87); this new public accessor (and its `STAGE_OUTPUT_UNITS` table) supplies
  the canonical unit string a renderer needs to honour the R-UNITS rule. View-only — no
  computed results change.

### Fixed
- **GUI Geometry derived-angles readout had a short scrollbar that did not span the table
  (owner report 2026-07-14).** On the Geometry "Inputs" tab the derived-angles readout sat
  in its own inner scroll area *inside* the stage pane's outer scroll; the tall input form
  above it crushed the readout to a ~100 px sliver, so its inner scrollbar covered only that
  sliver instead of the full table. `GeometryReadout` gains a `scrollable` flag (default
  `True`, keeping the inner scroll for the compact 3D-view accordion side panel); the Inputs
  tab now uses `scrollable=False` so the table sizes to its full content and the pane's outer
  scroll owns scrolling — one full-height scrollbar spans the whole form + derived table. The
  stage pane omits its trailing stretch when a filling section (the readout or the 3D-view
  split) is present so that section absorbs the slack. View-only — no computed results change.
- **GUI 3D geometry viewer did not visually update on re-render (owner report 2026-07-14).**
  Parameter edits, re-evaluations, and annotation/triad toggles reached the viewer, but the
  embedded viewport showed the stale scene. On the live pyvistaqt `QtInteractor` (macOS /
  real display) a `clear()` → rebuild → `render()` sequence does not reliably repaint the GL
  widget — the VTK `render()` alone can be a no-visual-op after a scene rebuild. `_render_live`
  now follows the VTK `render()` with an explicit Qt `update()` of the interactor widget, and
  the static-image backend now calls `update()` after `setPixmap`, so both backends repaint on
  every re-render. The user's current camera is preserved (PyVista's `camera_set` flag survives
  `clear()`, so the default-camera call is a no-op after the first render — the view is never
  snapped back). View-only — no computed results change.
- **GUI Evaluate button relocated to the right-rail footer (owner feedback 2026-07-13).**
  The accent Evaluate (F5) button sat in a thin run bar in the center of the window, which
  read as out-of-place. It now lives as a persistent footer pinned at the bottom-right of
  the right rail (the persistence area), below the Messages panel, so it never scrolls away.
  The center run bar is removed. F5 and Run ▸ Evaluate still drive the same evaluation.
  View-only — no computed results change.
- **Twin-axis plot y-labels clipped at the figure edges in the narrow embedded pane (owner
  feedback 2026-07-13).** The Atmosphere plot's rotated y-axis labels were spelled-out and
  long — `"Transmittance τ_atm (dimensionless)"` and `"Path radiance L_path (W/m²/sr/µm)"` —
  and overflowed the figure edges at GUI embedded width even under constrained_layout.
  `plot_atmosphere_spectral` now labels the axes with the symbol + unit form only
  (`"τ_atm (dimensionless)"`, `"L_path (W/m²/sr/µm)"`); the unit is always retained (R-UNITS).
  All other builders already used short symbol + unit labels. View-only — no computed
  results change.
- **MTF Budget overlay legend blanketed the curves in the narrow embedded pane (CU-117).**
  `plot_mtf_terms` drew one legend entry per term — ~16 for an 8-contributor × x/y overlay —
  inside the axes, covering much of the curve area at GUI embedded width. Each contributor's
  `_x`/`_y` are now merged into a single legend entry when they coincide (~16 → ~8 labels;
  differing x/y keep both), and the legend is placed below the axes in a compact multi-column
  block so it never overlaps the curves. All contributor curves are still plotted. View-only —
  no computed results change.
- **GUI stage Outputs readout showed dimensional values as bare numbers (R-UNITS
  violation).** The per-stage Outputs readout inferred a value's unit from the output key's
  trailing suffix, so keys without a canonical suffix (`optics.A_collect`, `optics.Omega_pixel`)
  rendered unit-free and a mid-key token (`readout.signal_e_final`, `spectral_integration.e_rate_per_s`)
  was mislabelled or dropped. Units now come from the single authoritative framework table
  (`radiant.api.stage_output_units`): `A_collect` → `m²`, `Omega_pixel` → `sr`,
  `e_rate_per_s` → `e-/s`, etc. Booleans/strings and genuine dimensionless numerics stay
  unit-free. View-only — no computed results change.

- **GUI contextual per-stage center + global Inspector (contextual-layout retrofit
  Step B, arch doc §4.4 / §4.6 / §4.7).** Selecting a stage in the signal-chain strip now
  makes the center show **only that stage's contextual composite** — its outputs readout
  (scalar `stage_outputs` values with units, or the performance metric surface), its
  plot(s) drawn from the public `result.plot.*` accessors, and its relocated detail content
  (the MTF per-term table + overlay on Optics, the noise-budget table + bars + click-explain
  on Detector, the geometry angle readout on Geometry). This replaces the single shared
  canvas. Every Outputs / Metrics row carries a **pin affordance** that adds the value to
  the right-rail Pinned panel — a stage-output pin re-reads `stage_outputs` on each run; a
  metric pin reads the metric surface (CU-115 Step-B clause delivered). A new global
  **Inspector** tool (Tools → Inspector / the menu-bar `◈ Inspector` button, `Ctrl+I`) opens
  the full `inspect_result(result)` variable dump as a collapsible tree; it is disabled
  until the first evaluation.
- **GUI contextual-layout right rail — Pinned / Edit Config (YAML) / Messages
  (contextual-layout retrofit Step A, arch doc §4.5).** A persistent right-side dock now
  carries three sections: a **Pinned** panel of metric cards (default set = SNR · NEDT ·
  NIIRS · GSD · MTF@Nyquist, each value + unit sourced from `ChainResult.metric_records()`,
  with unpin and a `+ Pin…` picker over the metric surface; session-scoped); an **Edit
  Config (YAML)** button that opens a roomy modal editor preloaded with the current config
  and re-parses the edited text through `Sensor.load` on Apply (invalid YAML shows the
  actionable error and leaves the live config untouched — validated on a throwaway sensor);
  and a **Messages** panel listing chain warnings and errors (the widened warning strip),
  each clickable to its full-text dialog. The full-well saturation banner stays in the
  center column (high-signal, non-dismissible).
- **GUI detail tabs — Spectral, MTF, Noise Budget, Variables, YAML (GUI plan
  Phase 4 Task B).** The bottom detail dock's five tabs are now live, each its own
  widget class and each populated on every successful evaluation from a public API
  surface (no plotting or physics in GUI code): **Spectral** (a themed selector over
  `result.plot.spectral_source()` / `spectral_atmosphere()` / `spectral_inband()`,
  showing the accessor's actionable message when a frame is absent for the regime);
  **MTF** (per-contributor MTF@Nyquist table discovered from the result's
  `mtf_budget.per_term_at_nyquist`, x/y columns, dimensionless → bare numbers, plus the
  `result.plot.mtf()` overlay); **Noise Budget** (per-term σ table in e- RMS from
  `result.noise_terms`, `result.plot.noise_budget()` bars, and a click-a-term describe
  panel from the `NoiseTerm` metadata); **Variables** (`radiant.api.inspect.inspect_result`
  re-rendered as a collapsible tree); and **YAML** (read-only provenance-coloured current
  config via `Sensor.save`, with an Export… button — the tab's only file I/O). Units on
  every numeric cell (R-UNITS); all styling from theme tokens. Visual/UX capability only;
  results-neutral.
- **Spectral-radiance figure accessors on `result.plot.*` (Gap 86).** The
  `ResultPlotNamespace` gains three accessors — `spectral_source()` (target +
  optional background at-aperture radiance vs λ [W/m²/sr/µm]),
  `spectral_atmosphere()` (τ_atm(λ) [dimensionless] and L_path(λ) [W/m²/sr/µm]
  on twin unit-labelled axes), and `spectral_inband()` (band-filtered
  post-optics radiance vs λ [W/m²/sr/µm]) — plus two supporting module
  functions in `radiant.api.plot` (`plot_spectral_multi`,
  `plot_atmosphere_spectral`). Each accessor plots only real stored frames /
  stage outputs (no recomputation) and raises an actionable `ApiValidationError`
  when the required frame is absent. This carries the arch-doc §4.4 Source /
  Atmosphere / Spectral-Integration default views and unblocks the GUI Phase 4B
  Spectral detail tab. Public-surface addition; results-neutral.
- **GUI stage-strip navigation, per-stage default visualizations, and live health
  dots (GUI plan Phase 4 Task A).** The 9-stage signal-chain strip is now clickable:
  a click scrolls the parameter panel to that stage's namespace group and swaps the
  central canvas to the stage's default visualization (arch doc §4.4) — the derived
  geometry angle/range **readout** (values with units + symbols) for Geometry, an
  MTF overlay (`result.plot.mtf()`) for Optics/Platform/Performance, a noise-budget
  bar chart (`result.plot.noise_budget()`) for Detector/Readout, and a themed
  "visualization not yet available (Gap 86)" panel for Source/Atmosphere/Spectral
  Integration whose spectral-radiance figure the `result.plot` surface does not yet
  carry (no faked figure — ground rule §4.1). Every figure is one call on the public
  `result.plot.*` surface (no plotting in GUI code). The per-stage **health dots**
  now update live: gray/stale before a run and on any parameter edit, green after a
  clean run, yellow on a run with chain warnings (whole-run, not per-stage), red on a
  failed evaluation. Selecting a stage highlights its chip. Visual/UX capability
  only; results-neutral.
- **GUI display units — rows and the Parameter Editor show the user's unit (GUI
  plan Phase 3 checkpoint punch-list round 2, owner feedback 2026-07-13).** A
  parameter row now displays its value in the unit the user chose (an altitude set
  as 500 km reads `500 km`, not `500000 m`), not always the schema canonical/input
  unit. Committing a Parameter-Editor edit with an explicit unit adopts that unit as
  the row's display unit; the editor opens on it (Current line, value field, unit
  combo, and bounds), and inline Value-column edits interpret the typed number in it
  and write it back with the same unit (type `550` into a km row → `550000 m`
  canonical, row shows `550 km`). All canonical↔display conversion routes through the
  public `radiant.api.units` seam (no ad-hoc GUI maths); a unit that is not soundly
  convertible (offset/one-way) falls back to the canonical unit. The unit suffix is
  always part of the string. Session-scoped (QSettings persistence lands in Phase 9).
  Visual/UX capability only; results-neutral.
- **GUI in-window chain-warning strip (GUI plan Phase 3 checkpoint punch-list round
  2, owner feedback 2026-07-13).** Chain `UserWarning`s (saturation clip, NIIRS
  extrapolation, …) — which previously printed only to the terminal — are now
  captured by the evaluation worker and shown in a themed **warn-token** strip
  between the KPI badges and the canvas, reading `⚠ N warnings` with the first
  message inline and, clicked, opening a dialog listing all messages verbatim. The
  strip clears on a warning-free evaluation. Captured warnings are also re-logged, so
  nothing is swallowed (Rule 17). Visual/UX capability only; results-neutral.
- **`radiant.api.units.inverse_convert` re-export.** The public units seam now
  re-exports `inverse_convert` (canonical → display-unit) alongside `convert` and
  `_CONVERSIONS`, the sanctioned surface for output-side conversion (used by the GUI
  display-unit feature). Additive-offset and one-way units remain unregistered, so it
  is sound (invertible) for every registered conversion.
- **GUI Parameter Editor dialog (GUI plan Phase 3 checkpoint punch-list).** The
  parameter panel gains a full-detail editor box that opens on a parameter
  (double-click its Parameter or Source column, or right-click → **Edit…**) and
  shows the complete dot-path the narrow tree truncates, the schema description,
  the current value with unit + provenance, the bounds, and the derived/read-only
  state. It edits the value with a per-dtype control and, for a dimensional
  parameter, a **unit selector** populated from the units the conversion registry
  can convert to the canonical unit (public `radiant.api.units` seam, never a
  hardcode); it previews the resulting canonical value (enter `8` `km` → `= 8000 m`)
  and commits one `sensor.set(dotpath, value, unit=…)`, validated on a clone so a
  rejected value never touches the live sensor and its actionable error renders in
  the dialog. Derived parameters open read-only. The Value column keeps its
  existing fast in-place editor (two complementary edit paths). Visual/UX capability
  only; results-neutral.
- **GUI evaluate loop, live metric badges, and saturation banner (GUI plan
  Phase 3 — Milestone A / D2).** `radiant gui` now runs the full chain: opening
  or editing a config evaluates `sensor.evaluate()` on a background worker thread
  (the Qt thread never runs the chain), driven by Run → Evaluate (F5) or the
  accent Run button, and auto-re-evaluated after a 200 ms debounce on any
  parameter edit (full chain — no incremental engine, CU-079). The five KPI
  badges (SNR · NEDT · NIIRS · GSD · MTF@Nyquist) fill from the `ChainResult`
  metric surface with each value's unit sourced from the result metadata
  (`metric_records()`), a result-typed metric failure shows its `failure_reason`
  (never a blank), and the central matplotlib canvas renders the existing
  `result.plot.*` figure (default: the MTF overlay). A failed evaluation keeps
  the previous result on screen, flagged stale ("last evaluation failed"), and
  shows the actionable error (`RadiantError` → what/why/action; otherwise a
  traceback dialog). A **non-dismissible saturation banner** appears whenever
  `result.well_status().is_saturated`, showing the fill fraction and the
  accumulated-vs-capacity electrons with units, and clears on the next
  unsaturated result. Visual/UX capability only; the GUI is results-neutral (no
  computed-result or public-API change).
- **`ChainResult.well_status()` — full-well saturation on the result surface
  (CU-101).** The readout stage's well-capacity clip decision is now a
  first-class accessor returning a `WellStatus` record (exported as
  `radiant.api.WellStatus`): `.status` (`"ok"`/`"clipped"`, equal to
  `stage_outputs["readout"]["well_status"]`), `.is_saturated`, `.fill_fraction`
  (dimensionless), `.total_well_e` [e-], and `.full_well_capacity_e` [e-]. The
  readout stage additionally publishes `well_fill_fraction`, `total_well_e`, and
  `full_well_capacity_e` to `stage_outputs["readout"]` (serialization-safe, so
  the surface survives `save()`/`load()`). Lets the GUI saturation banner — and
  scripting users — read a metric instead of digging into `stage_outputs`; the
  underlying silent-clip trap (Gap 65) is now surfaced. Public-surface addition
  only; no computed-result change.
- **Schema-driven parameter tree in the GUI (GUI plan Phase 2, Task A —
  read-only half).** The parameter dock now populates a Parameter / Value /
  Source tree generated entirely from `Sensor.parameter_defs()` (never a
  transcribed list), grouped by dot-path namespace in chain order (geometry
  first). Each row shows the resolved value with its schema unit suffix; derived
  parameters carry a ⚡ marker; the Source column shows provenance (config /
  default / derived / user-set) read from the resolved set. A live filter box
  narrows rows by substring across dot-paths. Launched on a config the tree is
  populated; launched bare it shows a "no configuration loaded" state. Visual/UX
  capability only; no computed-result or public-API change.
  **Task B (editing):** non-derived rows are now editable in place — a
  schema-typed editor (combo for enums with schema-sourced choices, checkbox for
  bools, spin box for ints, line edit for floats/strings), each commit one
  `sensor.set`; rejected values (bounds / enum / consistency-group) render their
  actionable what/why/action inline and in a modal and never stick; right-click
  gives Copy dot-path, Explain (`sensor.explain`), and Reset to Default
  (`sensor.reset`).
- **`radiant gui` entry point and the `radiant.gui` package (GUI plan Phase 1,
  Task A).** A new PySide6 desktop-GUI shell — `launch_gui(sensor=None)` and the
  `radiant gui [CONFIG.yaml]` CLI subcommand — behind a new optional dependency
  group, `pip install "radiant[gui]"`. The GUI is a view over the scripting API
  (no physics, no computed-result changes); this phase ships only the window
  shell (menus, empty stage strip, dock panels, status bar). Without the `gui`
  extra installed, `radiant gui` raises an actionable error naming the remedy and
  the rest of RADIANT is unaffected. Not results-affecting.
- **GUI design-system theme (GUI plan Phase 1, Task B).** The shell now boots with
  the ratified design-system look (arch doc §8): a **light** QSS theme is applied at
  startup (the v1 launch default) with a **dark** alternate deriving from the same
  token set. `radiant.gui.themes` is the single owner of every colour, font, and
  spacing value; a mechanical test blocks any hardcoded colour/font literal elsewhere
  in the GUI. Visual change only — no computed results, no public API change beyond
  the internal `themes` helpers.

### Fixed
- **Embedded matplotlib plots no longer clip titles / axis labels / legends
  (owner feedback 2026-07-13).** Every `radiant.api.plot` builder (and thus every
  `ResultPlotNamespace` / `result.plot.*` figure) now uses matplotlib constrained
  layout instead of a one-shot `tight_layout()`, so titles, axis labels, and legends
  keep a reserved margin and re-fit on resize — fixing the cut-off "Source spectral
  radiance" title, the "MTF Budget" title overlapped by its legend, and edge-crowded
  axis labels in the GUI (and improving `savefig` output for script users too). The
  dense MTF-terms legend now sits inside the axes so it never reaches the title band at
  any canvas width. In the GUI, the MTF per-term table's first column shows its full
  "Contributor" header (was truncated to "trib…") and every column sizes to its
  contents; the MTF/noise panels' embedded canvases keep a minimum height so a short
  window scrolls rather than collapsing the figure. Visual only — no computed results
  changed.
- **GUI Parameter-Editor unit dropdown no longer clips (GUI plan Phase 3
  checkpoint punch-list round 2, owner feedback 2026-07-13).** The unit selector's
  popup previously truncated unit names to ~2 characters ("cr", "kı"); the combo now
  sizes to its contents and its popup view is sized to the widest unit label, so every
  unit reads in full. Visual only.

### Changed
- **Results-affecting: Earth radius unified to 6371.0 km mean (CU-097).**
  RADIANT previously used two Earth radii: the atmospheric slant-path /
  airmass geometry ran on the WGS-84 equatorial radius (6378.137 km) while
  slant range, incidence, ground range, and orbital kinematics used the
  6371.0 km mean radius. Both now use the single canonical
  `constants.R_EARTH_M = 6.371e6 m` (IUGG / US Standard 1976 mean). Nadir
  results are unchanged; off-nadir atmospheric path lengths and airmass
  shift at the sub-percent level (−0.11 % radius, e.g. the 60° reference
  slant path drops 195601 → 195566 m, ~0.018 %), in the
  correct-consistency direction (one triangle, one Earth). No golden
  baseline changed (all 14 sit at the nadir default).

### Removed
- **GUI bottom detail-tabs dock (contextual-layout retrofit Step B, arch doc §4.7).**
  The bottom `DetailTabs` dock and its five tab widgets are removed; their content is
  **relocated**, not discarded: the MTF and Noise Budget tabs became the embeddable
  `MtfPanel` / `NoiseBudgetPanel` (Optics / Detector center views), the Spectral tab's
  three figures became per-stage plot sections (Source / Atmosphere / Spectral
  Integration), the Variable Explorer tab became the global `InspectorDialog` tool, and
  the read-only YAML tab was superseded by the Step-A right-rail Edit Config (YAML) modal.
  The `View → Show/Hide Detail Panel` action is removed with the dock it toggled.
- **GUI global metric-badge row and floating warning strip (contextual-layout
  retrofit Step A).** The `KpiBadgeRow`, `MetricBadge`, and `WarningStrip` widget
  classes are retired: the metrics relocated to the right-rail Pinned cards and the
  warnings to the Messages panel (nothing user-facing is lost — badges → pinnable
  cards, strip → Messages). The accent Evaluate button that lived in the badge row
  moved to the central canvas run bar.
- `radiant.core` no longer exports `ObserverGeometry`, `TargetGeometry`,
  `SceneGeometry` (CU-094, ADR-0006 Phase 4). The flat-Earth scene
  dataclasses had zero consumers outside their own tests and were
  superseded by GeometryStage + `core.viewing_triangle`. The module's
  live functions (`slant_range_spherical_m`, `incidence_angle_rad`,
  Euler helpers) are unchanged.

### Deprecated
- `platform.h_sensor` → folded into `geometry.sensor_altitude_m` (CU-090,
  ADR-0006 Phase 3). One sensor altitude, one owner; the old name keeps
  working via `deprecated_aliases` (warn-and-redirect) for one release
  cycle. The no_atmosphere 'space' Earth-limb check now reads the
  canonical name (its error message names `geometry.sensor_altitude_m`).

### Added
- **Range-consistency enforcement (CU-093).** `geometry.target_range_m`
  set together with an explicit viewing angle now must agree with the
  angle-implied slant range within 1% or GeometryStage raises an
  actionable `GeometrySpecificationError`. A user range combined with
  *defaulted* viewing angles (mode V0) keeps the historical behavior —
  range drives regime/detection, nadir drives spatial metrics — but the
  previously silent disagreement now emits a `UserWarning` naming both
  distances.

### Fixed
- Lab/bench configurations with `geometry.sensor_altitude_m = 0` (sensor
  and target collocated) no longer trip the GeometryStage viewing
  triangle: the degenerate case publishes `None` slant/ground/incidence
  and the chain proceeds on the V0 range/regime path. (Regression
  introduced by the Phase-1 stage landing earlier today; caught in the
  CU-090 call-site audit — lab scenario scripts are not in the test
  suite.) Uplooking (`sensor below target`) still raises, per the
  owner-ratified v1 policy.

### Changed
- **Geometry input modes now steer the whole chain (ADR-0006 Phase 2).**
  SourceStage adopts the GeometryStage-published scene LOS (so the off-nadir /
  ground-range / elevation / site+time / night modes reach the atmospheric
  assembly and shape view directions); PlatformStage consumes the published
  slant range for velocity smear; PerformanceStage consumes the published
  slant range, incidence angle, ground range, and ground speed (GSD, ground
  metrics, diffraction ground projection, access rate — `circular_orbit`
  now yields `access_rate_m2_s` with no manual speed entry).
- **Results-affecting (off-nadir configurations only):** GSD, ground range,
  diffraction ground projection, and velocity smear now derive from the
  canonical target-side zenith θ_o via one spherical triangle
  (`core.viewing_triangle`, R_E = 6378.137 km), where they previously
  re-derived from `geometry.path_zenith_rad` *misread as the sensor-side
  off-nadir angle* on a 6371 km Earth (CU-096; CU-097). At nadir — every
  shipped golden baseline — values are unchanged (verified byte-identical).
  At off-nadir the new values are the physically consistent ones; e.g. at
  h = 500 km, θ_o = 45°: slant range 683.1 km (was 737.3 km when 45° was
  treated as the sensor-side η) — metrics that scale with slant range shrink
  by ~7 % there, more at steeper angles.

### Added
- `performance.gsd.compute_gsd_from_geometry` — GSD from already-derived
  (slant range, incidence angle); the legacy `compute_gsd(altitude, angle)`
  remains for direct callers (CU-096 tracks retiring it).

### Added
- **GeometryStage — geometry is stage 0 of the chain (ADR-0006).** The signal
  chain is now `geometry → source → … → performance` (9 stages;
  `ChainResult.history` and provenance `active_models` gain a leading
  `"geometry"` entry). The new stage owns the `geometry.*` namespace, resolves
  the scene-geometry input mode, and publishes every derived quantity once via
  `stage_outputs["geometry"]` (`los_geometry`, `theta_o_rad`, `eta_rad`,
  `slant_range_m`, `ground_range_m`, `incidence_angle_rad`, solar geometry,
  ground speed, and the mode labels). Zero numerical drift: existing
  configurations resolve exactly as before (all goldens byte-identical);
  downstream stages still read the canonical parameters until the Phase-2
  re-plumb (`docs/plans/Geometry_Stage_Plan.md`).
- **New geometry input modes** (published by the stage; chain-steering lands
  with Phase 2): `geometry.sensor_off_nadir_rad` (off-nadir η — wires the
  CU-005-reserved `theta_o_from_eta` converter), `geometry.ground_range_m`
  (surface-arc entry), `geometry.elevation_angle_rad` (grazing-angle entry),
  `geometry.solar_elevation_rad`, site+time solar inputs
  (`geometry.site_latitude_rad`, `geometry.day_of_year`,
  `geometry.local_solar_time_h`, `geometry.ltan_h` — wires the previously
  consumer-less `core.solar_geometry`), and `geometry.circular_orbit`
  (derives ground-track speed and orbital period from altitude via
  `core.orbit`). Over-specified or mutually inconsistent entries raise the
  new actionable `radiant.geometry.GeometrySpecificationError`.
- `core.viewing_triangle` — θ_o-referenced spherical viewing-triangle
  solutions (`eta_from_theta_o`, `slant_range_from_theta_o_m`,
  `ground_range_from_theta_o_m`, `theta_o_from_ground_range_m`).

### Deprecated
- `source.target.range_m` → renamed `geometry.target_range_m` (ADR-0006).
  The old name keeps working via `deprecated_aliases` (set/get redirect with
  a `DeprecationWarning`) for one release cycle.

### Changed
- Uplooking configurations (`geometry.sensor_altitude_m` at or below
  `geometry.target_altitude_m`) are now rejected by GeometryStage at the head
  of the chain with an actionable error, instead of surfacing later as the
  atmosphere Earth-limb check. Same v1 policy (uplooking rejection,
  owner-ratified 2026-07-11); earlier, clearer error site.

### Added
- MODTRAN downwelling zeroing now warns (Gap 81, partial): a
  MODTRAN-backed atmospheric state emits a `UserWarning` that the
  downwelling sky emission (`atm_emission_down` / `E_sky_thermal`) and
  scattered-solar sky radiance are set to zero (the standard IEMSCT=2
  tape7 carries no downwelling column) — switching `atmosphere.model`
  from `simple` to `modtran` no longer *silently* drops the thermal-band
  background terms. The full fix (ingest a separate downwelling run via
  `atmosphere.modtran.tape7_down_path`) is deferred on MODTRAN access.

### Fixed
- **Results-affecting (`simple` atmosphere, wavelengths > 5 µm only):**
  the aerosol Ångström power law is now clamped at the MWIR–LWIR boundary
  (5 µm) instead of extrapolating toward zero into the LWIR, where real
  aerosol extinction is absorption-dominated and roughly flat (CU-088).
  Beyond 5 µm the extinction is frozen at its 5 µm value (raising LWIR
  aerosol extinction vs the old extrapolation), and `SimpleAtmosphere`
  warns once per run when the clamp engages. MWIR (≤ 5 µm) and the golden
  baseline are unchanged; the clamp only affects LWIR `simple`-model runs.

### Changed
- **Results-affecting (only when `dark_activation_energy_eV > 0` and the
  reference was left at its default):** `detector.dark_reference_temperature_K`
  default changed 300 K → 77 K to match the `detector_temperature_K` default
  (CU-081), so the default config is self-consistent. With the default
  `dark_activation_energy_eV = 0` the dark rate is temperature-inert, so
  `dark_e` is unchanged for the default config and the golden baseline.

### Added
- Enum validation on `readout.tdi_mode` (`analog`/`digital`) and
  `detector.noise_regime` (`imaging`/`detection`) (CU-076): a typo now
  raises at resolve instead of silently selecting the wrong model
  (analog scaling / dropped spatial noise).
- Dark-current temperature-inertness warning (CU-081): when
  `detector_temperature_K` differs from the reference and
  `dark_activation_energy_eV = 0`, `DetectorStage` warns that the
  temperature setting has no effect on dark noise (a GUI temperature
  slider that silently does nothing).
- Validation hardening (CU-085): `Tolerance` now validates its
  distribution and required spread parameters at construction (a
  parameter-less gaussian previously sampled zero spread silently); the
  consistency-group over-specification check no longer skips when the
  first parameter lacks a derivation rule; velocity smear warns instead
  of silently returning 0 when altitude/integration time is missing; the
  IPC y-axis MTF uses the y pitch (was x — wrong for rectangular pixels);
  the CLI provenance version reads `radiant.__version__` (was hardcoded
  "0.1.0"); the `pixel_pitch_y_um` "defaults to x pitch" description
  (false — it is required) is corrected.
- SCNR and in-chain point-source detection range (Gap 77): new `scnr`
  metric (signal-to-clutter-plus-noise — target contrast over the
  clutter-inclusive total noise √(σ_temporal² + σ_spatial²), the detection
  figure of merit, unlike `snr`/`contrast_snr` which respect
  `noise_regime`); new `detection_range_m` metric, computed in the
  point-source regime by bisecting the Beer-Lambert solver to the range
  where SNR falls to the new `performance.detection_snr_threshold`
  parameter (default 5.0). New modules `radiant.performance.scnr` and a
  `radiant.performance._schema`. The detection range uses a constant
  atmospheric extinction (exact in vacuum; first-order for atmospheric
  paths) — the geometry-aware slant-path refinement is deferred (Gap 77
  narrowed). The wider acquisition-metric family (Pd/ROC, Johnson DRI,
  NEΔL/NEΔρ, D*/NEP/NEI) stays library-only pending GUI-phase surfacing
  (Gap 78).
- Orbit-derived ground velocity + duplicate collapse (Gap 75):
  `Sensor.set_ground_velocity_from_orbit()` derives
  `platform.ground_velocity_m_s` from `geometry.sensor_altitude_m` via the
  circular-orbit sub-satellite ground-track speed (`radiant.core.orbit`,
  previously wired to nothing). `platform.ground_velocity_m_s` and
  `geometry.ground_speed_m_s` — the same physical quantity, previously two
  independent fields that could silently disagree — are now a collapsed
  identity consistency group: setting either derives the other, and
  setting both to disagreeing values raises an over-specification error.
  (The analogous altitude duplicate `sensor_altitude_m` vs
  `platform.h_sensor` is deferred — CU-090.)
- Pushbroom/TDI scan-timing feasibility guard (Gap 74, minimum slice):
  when `platform.ground_velocity_m_s` is set, `PerformanceStage` computes
  the per-line dwell `t_dwell = GSD_along / v_ground`, stores it as the new
  `max_integration_time_s` metric, and warns when
  `spectral_integration.integration_time_s` exceeds it (the along-track
  image smears more than one ground sample per integration — an unphysical
  TDI timing whose SNR would otherwise look authoritative). New module
  `radiant.performance.scan_feasibility`. Parameter-gated: inert without a
  ground velocity, so existing results are unchanged.

### Fixed
- `ChainResult.signal_at(DN)` (and DN propagation generally) no longer
  raises when the well fully saturates (`signal_e_final = 0`) — a state
  now reachable when a bright point-source background pedestal fills the
  well (Gap 73). The `post_readout→dn` transfer factor falls back to the
  linear `1/gain` conversion, so a saturated pixel reports 0 DN instead
  of a missing-transfer-factor error. New readout output `gain_e_per_dn`.
- **Results-affecting (IPC coupling > 0 only):** the PSF-path IPC kernel is
  now resampled to the PSF sample grid (CU-083). The raw 3×3 kernel was
  convolved onto the sub-µm PSF grid, placing its α couplings one *sample*
  (not one pixel pitch) away — so the PSF-path IPC blur was orders of
  magnitude too small and diverged from the analytic MTF-product term.
  Now `ipc_kernel_pitch_spaced` places the couplings at ±pitch, so RER,
  FWHM, EE, and MTF-at-Nyquist reflect the correct IPC degradation
  (e.g. MTF at Nyquist × (1−4α)) and the dual-path consistency check
  passes. At `ipc_coupling = 0` (default, golden baseline) no kernel is
  built — golden unchanged. New `detector` stage output `ipc_kernel_psf`;
  the raw 3×3 `ipc_kernel` output is retained for provenance.
- **Results-affecting (fill_factor < 1 only):** `detector.fill_factor` now
  couples consistently across all three affected paths (CU-074). It is the
  areal photosensitive fraction, so a square photosite has linear width
  `pitch·√FF`: this width now drives BOTH the PSF-path pixel-aperture
  kernel and the MTF-product pixel sinc (previously the sinc used the full
  pitch, diverging the two Rule-4 paths and warning on every FF<1 run), and
  the collecting area `pitch²·FF` scales the radiometric signal (previously
  the full-pitch area was used, overcounting signal). Nearfield and stray
  electrons also scale by FF. Direction at FF<1: signal ↓ by factor FF,
  pixel MTF ↑ (narrower photosite). At FF=1 (the default and the golden
  baseline) every change is an exact no-op — golden unchanged.
- **Results-affecting (point-source regime only):** point targets now sit
  on a full-pixel background pedestal (Gap 73). Previously the
  point-source branch hardcoded `background_e = 0`, so a compact target
  against a bright background (daytime sky, sunlit cloud) had zero
  background shot noise and zero well fill from the sky — optimistic
  SNR/detection-range, and a discontinuous noise budget across the
  sub-pixel→point-source boundary. Now `background_e` is the full-pixel
  pedestal (same formula as the extended/sub-pixel background reference)
  when an at-aperture background frame exists; it feeds background shot
  noise and the readout well-fill (regime-gated — the pedestal is
  additional well charge only in point-source, where signal_e is
  target-only). Target signal and `contrast_e = signal_e` are unchanged;
  extended/sub-pixel results and the golden baseline are unchanged.
  Direction: point-source SNR against non-dark backgrounds decreases;
  magnitude scales with background radiance.

### Added
- Progress and cancellation hooks (Gap 72): `progress(done, total)` and
  `cancel() -> bool` keyword arguments on `Sensor.sweep`/`sweep_2d`/
  `monte_carlo`/`sensitivity` (and the underlying API functions) and
  `BatchRunner.run`. Cancellation raises the new
  `radiant.api.OperationCancelledError` (a `RadiantError` carrying
  operation/done/total). `solve_for` is excluded (unpredictable
  iteration count).
- `UnknownParameterError` (CU-073): typo'd parameter names in
  `set`/`get`/`reset`/`set_tolerance`/`parameter_def` now raise a
  `RadiantError` subclass (co-inheriting `KeyError` for back-compat)
  with the did-you-mean suggestion — the documented `except
  RadiantError` boundary now catches the most common user mistake.

### Fixed
- Parallel sweep crash (CU-072): `n_workers > 1` no longer dies with an
  unhandled `PicklingError` when the run function or its returned
  `ChainResult` cannot pickle (the common case — results carry
  `MappingProxyType` fields). Pickling failures are now caught at both
  submit time and result time and the sweep falls back to sequential
  with a logged warning, as originally documented.

### Added
- Non-scalar input reachability (Gap 68): `Sensor.set_stage_output(group,
  key, value)` and `Sensor.evaluate(extra_stage_outputs=...)` forward
  pre-chain injections to every evaluation, including all trade studies
  (sweep/sweep_2d/monte_carlo/sensitivity/solve_for). Optics
  transmission modes `spectral_file`/`telescope_plus_filters`/
  `key_elements` and stray-light `spectral_file` now actually consume
  their `optics_config` injections (previously these schema-selectable
  modes raised unconditionally); injected curves are resampled onto the
  chain grid with a loud out-of-coverage error.

### Changed
- `optics.transmission_input_mode`, `optics.wfe_mode`, and
  `optics.stray.input_mode` now validate against explicit enum values
  (Gap 68). The always-raising modes `opd_map` (no pupil-phase
  representation in v1) and `pst_file` (needs a scene radiance
  distribution v1 lacks) are no longer offered — setting them now fails
  at `params.set`/resolve with the allowed list instead of deep in the
  optics stage.

### Added
- Metric metadata contract (Gap 71): every computed metric now carries a
  non-empty unit, description, and kind via the reconciled metric
  registry; new `ChainResult.metric_records()` returns unit-labelled
  `MetricRecord` tuples, and `radiant.performance.metric_info(name)`
  exposes single-metric metadata. `MetricSpec` gains
  `unit`/`description`/`kind`/`requires_mtf_terms` fields.

### Removed
- Metric registry phantoms (CU-078): the never-computed registry
  entries `nedt`, `nedl`, `nedr`, `csnr`, `ee`, `edge_slope`,
  `detection_range`, `saturation_margin`, `dynamic_range` are gone;
  the catalog now registers exactly the 32 keys the performance stage
  computes (real keys: `nedt_K`, `ee_1x1`/`ee_3x3`,
  `well_margin_dB`/`adc_margin_dB`, `dynamic_range_dB`, …).
  NEΔL/NEΔρ/edge-slope/detection-range specs return with the commits
  that compute them (Gaps 77/78). Reconciliation is CI-enforced.

### Added
- Persistence (Gap 67): `Sensor.save(path)` / `Sensor.load(path)` —
  YAML round trip of explicit inputs, tolerance distributions, and
  `wavelength_points` via a new `_radiant` config metadata block
  (`RADIANT_Config_Format.md` §1.7); reloading reproduces the original
  resolution and provenance exactly. `ChainResult.save(path)` /
  `ChainResult.load(path)` — single-file zip archive (JSON manifest +
  npz arrays) holding the full ChainState with dtype-preserving,
  full-fidelity reload and the provenance record frozen at save time.
  Supporting public surface: `ParameterSet.inputs()`,
  `radiant.io.config.read_radiant_meta()`, `save_config(scope=)`,
  `radiant.io.serialization` (`ResultArchiveError`,
  `UnserializedValue`).
- Public schema-introspection API (Gap 70): `ParameterSet.parameter_defs()`,
  `parameter_def(name)`, `consistency_groups()`, `tolerances()`,
  `is_resolved`, and `copy()`, plus `Sensor.parameter_defs()` /
  `Sensor.parameter_def(dotpath)` passthroughs. GUIs/CLIs/sweep tooling
  can now enumerate the full parameter schema (dtype, units, bounds,
  enums, defaults, descriptions, tags) without touching private state;
  all framework consumers migrated off the `_defs`/`_groups`/`_inputs`/
  `_tolerances`/`_resolved_flag` privates. Side effect: sweep- and
  sensitivity-cloned ParameterSets now carry loaded-file provenance
  records (previously dropped by the private clone path).

### Fixed
- **CU-065 (deck-side):** `render_tape5` now converts RADIANT's
  lower-endpoint path zenith to MODTRAN's Card 3 ANGLE-at-H1
  convention: downlooking decks render `180° − zenith` (a nadir
  space sensor renders ANGLE = 180, previously 0), uplooking decks
  are unchanged. Matches `modtran_run_matrix.csv`'s hand-worked
  `modtran_angle_at_h1_deg` column for every ITYPE=2 row; the
  rendered decks in `modtran/decks/` (regenerable) are what a real
  MODTRAN run will consume. No computed chain result changes (no
  binary has ever run), but downlooking tape5 decks — and therefore
  their SHA-256 cache keys — differ from pre-fix renders. CU-065's
  remaining residue: confirm the convention against the MODTRAN
  manual on access.

### Added
- `atmosphere.modtran.tape7_sun_path` (CU-011, file flavor): optional
  sun-leg tape7 for the Option C two-leg split. When set (requires
  `tape7_path`), `tau_sun` comes from the sun-leg file's transmittance
  instead of aliasing the up-leg value, the single-τ collapse
  `UserWarning` is not emitted, and the assembly's direct-solar term
  consumes the split. Unset, behavior is unchanged (alias + warning).
  The binary-invocation two-run flavor and real-MODTRAN physics parity
  remain deferred under CU-011.
- `atmosphere.modtran.tape7_path`: first-class MODTRAN tape7 file import.
  Setting it (with `atmosphere.model="modtran"`) builds the atmospheric
  state directly from a tape7 file produced elsewhere — parsed before
  chain execution (Rule 6), no MODTRAN binary, cache, or fallback
  involved. Replaces the manual side-door (Tape7Reader → temp CSVs →
  `atmosphere.model="tabulated"`) that every consumer hand-rolled;
  outputs are identical to that side-door (integration-tested to exact
  equality). Unset, the binary/cache/fallback behavior is unchanged.
  Like tabulated files, an imported tape7 is geometry-agnostic, and
  airborne targets (`h_tgt > 0`) are rejected. See
  `RADIANT_Atmosphere.md` §5.1.

### Changed
- **CU-066:** `Tape7Reader` now locates MODTRAN tape7 columns by their
  header label (left-to-right order of appearance), not a fixed token
  index. The prior positional mapping would have silently swapped
  `path_scattered_radiance` and `ground_reflected_radiance` with the
  wrong columns (THRML SCT / SURF EMIS instead of SOL SCAT / GRND
  RFLT) on real MODTRAN output, and could ingest numeric card-echo
  lines as spectral data. No shipped result is affected — no
  MODTRAN-derived value has ever been computed by RADIANT. Tape7
  files with no recognisable header now emit a `UserWarning` and use
  the old positional mapping as a documented fallback.
- **Results-affecting (NEDT, small):** exact band-integrated NEDT dS/dT
  (Gap 43). `SpectralIntegrationStage` now computes
  `dS/dT = ∫ (signal integrand)·(∂B/∂T)/B dλ` — the exact Planck
  log-derivative over the band — and `PerformanceStage` uses it (σ/(dS/dT))
  in place of the single-λ (band-center) Planck-factor approximation. The
  two agree **exactly** in the narrow-band limit; over a wide band NEDT
  shifts by the Planck band curvature: ~+0.3% / −0.2% for LWIR cells,
  ~+4.5% for a 3.5–5 µm MWIR band. No golden baseline asserted NEDT; the
  two pinned Option-C LWIR anchors were repinned with provenance. The
  single-λ form remains the fallback when no target temperature is set.

### Added
- `ParameterDef.required_unless` (Gap 66): a required parameter may now
  name an alternative that supersedes it — when the alternative is
  explicitly set, the requirement is waived and the parameter is left
  unresolved (never phantom-populated). First use: `detector.qe_value`
  is required unless `detector.qe_table_path` is set, so a spectral QE
  CSV now works WITHOUT also setting a meaningless scalar QE — the
  schema always documented the table as superseding the scalar, but the
  resolver rejected the config ("Required parameter 'detector.qe_value'
  is not set"); scenarios 1.1 and 1.2 both hit this and worked around
  it by band-averaging. The required-parameter error message now also
  names the superseding alternative when one exists.
- Saturation warnings (Gap 65, Rule 17): `ReadoutStage` now emits a
  `UserWarning` whenever the well-capacity or ADC saturation check clips
  the signal, naming the exceeded ceiling, the clipped value, and the
  remedies (integration time / gain / ADC bits / FWC). Previously both
  clips were silent outside `stage_outputs["readout"]["well_status"]` /
  `["adc_status"]`, which cost three scenarios (6.1, 6.2, 8.2) real
  debugging time on bit-identical "no effect" results. No computed
  values change — warning only.
- MODTRAN deck-builder fields, opt-in (CU-063/064/069): `ModtranConfig.visibility_km`
  (`float | None`, default `None` = IHAZE default) threads to Card 2 VIS;
  `ModtranConfig.itype` (`int`, default `2`) and `ModtranConfig.iemsct`
  (`int`, default `2`) thread to Card 1, adding ITYPE=3 (slant path to
  space) and IEMSCT=3 (solar/lunar irradiance mode). All defaults
  reproduce the pre-change tape5 deck byte-for-byte.
- Veiling-glare spatial halo, opt-in (Gap 60 partial): new parameters
  `optics.stray.veiling_glare_mtf` (int 0/1, default 0) and
  `optics.stray.halo_sigma_um` (default 50 µm). When enabled with
  `veiling_glare_fraction > 0`, the stray fraction is re-imaged as a
  Gaussian halo entering BOTH spatial paths (Rule 4): kernel
  `(1−vgf)·δ + vgf·G(σ)` on the `EffectivePSF` and the exact Fourier
  pair `(1−vgf) + vgf·exp(−2π²σ²f²)` on the MTF product
  (`mtf_stray_x/y`) — the low-frequency contrast-modulation loss the
  CU-062 radiometric pedestal cannot express. Default-off: existing
  results are bit-identical; enabling it is results-affecting for
  veiling-glare configs (MTF/RER/NIIRS drop toward the (1−vgf) floor).
  The 2-D PST/vendor-PSF import (`pst_file`) stays deferred
  (single-pixel scope decision).
- ROC / detection-probability model (scenario 6.4):
  `radiant.performance.roc` — `roc_curve` (P_d vs P_fa from a detection
  index / contrast SNR), `detection_probability` (`Q(Q⁻¹(P_fa)−SNR)`), and
  `roc_auc` (`Φ(SNR/√2)`) for the equal-variance Gaussian model. New error
  class `RocError`. No chain change.
- Multi-frame persistence sequence (scenario 2.4):
  `radiant.detector.persistence_sequence` — `persistence_residual_e` /
  `persistence_residual_sequence_e` (residual ghost signal
  `prior·f·exp(−(n−1)Δt/τ)` over a frame sequence) and `frames_to_clear`
  (frames until the residual drops below one LSB). Extends the existing
  single-frame `persistence_noise` term to the temporal domain. New error
  class `PersistenceSequenceError`. No chain change.
- Temperature retrieval + emissivity/temperature Jacobian (scenario 6.5):
  `radiant.performance.temperature_retrieval` — `retrieve_temperature_K`
  (invert a measured band radiance for surface T given an assumed ε, via
  Brent), `band_planck_radiance`, and the Jacobians `emissivity_jacobian`
  (∂L/∂ε = B̄(T)) and `temperature_jacobian` (∂L/∂T = ε·∫dB/dT). New error
  class `TemperatureRetrievalError`. Analysis model — no chain change.

### Added
- `geometry.solar_illumination` day/night toggle (Gap 59): `night` removes
  the solar terms for reflective/mixed (T2/T3) targets (`theta_s = None` —
  no direct-solar reflection, no single-scatter solar sky) while thermal
  self-emission and reflected thermal downwelling remain. Previously the
  `solar_zenith_rad` schema default (0.5 rad) gave every T2/T3 scene a
  phantom daytime sun and night was inexpressible. The `day` default
  preserves every existing configuration bit-for-bit.
- Spectral GroundBackground ε_g(λ) (CU-008): two new parameters give the
  sub-pixel/point-source background a spectral emissivity surface —
  `source.background.material` (a named `radiant.data.SpectralLibrary`
  entry: vegetation_green, snow, soil_dry, asphalt, … ; default `grey`
  keeps the exact scalar back-compat path) and
  `source.background.emissivity_path` (measured two-column CSV; wins over
  material). Resolution happens in the API layer pre-chain (Rule 6) and is
  injected via `stage_outputs["source_config"]["background_emissivity"]`.
  The Stage-2 "grey placeholder" `UserWarning` is removed — grey is now an
  explicit choice, and all existing sub-pixel configs are numerically
  unchanged. Unknown material names are rejected with the legal
  vocabulary.
- `source.lab_test_mode` parameter (Gap 40): positive `dark`/`lit`
  assertion for the ground_test/lab_test sub-cases. `dark` declares a
  no-external-illumination configuration (the D-lab dark-cal sub-mode) and
  is validated — a user-set `source.target.reflectance` contradicts it and
  is rejected with an actionable error; `lit` is a recorded assertion;
  the empty-string default is unasserted and preserves every existing
  config byte-for-byte.
- Stage-scoped error classes (CU-043, Rule 15): every stage package now
  exposes a `<Stage>ValidationError(RadiantError, ValueError)` — plus
  `CoreStateError`, `AtmosphereStateError`, and
  `SpectralIntegrationStateError` co-inheriting `RuntimeError` — in its
  `errors.py` (`CoreValidationError`/`CoreStateError` live in
  `core/exceptions.py`). All 428 bare `raise ValueError`/`RuntimeError`
  sites across core, the eight physics stages, and `api/` were migrated to
  these classes, so `except RadiantError` now catches every framework
  rejection. **No behavioral change for existing code**: the classes
  co-inherit their historical built-in type (the sanctioned Rule 15
  back-compat carve-out), so `except ValueError` /
  `pytest.raises(ValueError)` call sites keep working unchanged. A
  regression guard (`tests/test_exceptions.py::TestNoBareBuiltinRaises`)
  forbids new bare built-in raises.

### Changed
- **Results-affecting (PSF-path spatial metrics; small):** the
  pixel-aperture rect kernel is now sampled by exact area overlap
  (anti-aliased edges) instead of a binary inside/outside mask (CU-003
  option a). The binary mask quantised the rect width to the PSF sample
  grid, over- or under-blurring by up to half a sample; MTF-at-Nyquist,
  RER, and EE shift by a few percent in configurations where the grid did
  not divide the pitch (Option-C anchors: Cell 28 MTF@Ny +5.6%, Cell 58
  +7.9% — repinned with provenance). FFT-vs-analytic-sinc agreement
  improves ~13× (4.5e-2 → 3.6e-3 at Nyquist, worst config); the worst
  full-chain dual-path residual drops from ~5.8e-2 to ~1e-2. Radiometric
  goldens (signal/noise/SNR) are unaffected.
- Dual-path consistency default tolerance tightened 5e-2 → 2e-2 (CU-045):
  ~2× margin over the worst measured full-chain residual after CU-003.
  The check remains warn-only by design — it is a diagnostic invariant,
  and raising would abort runs whose physics is otherwise valid.
- **Results-affecting (non-default atmosphere profiles; large in
  water-sensitive bands):** the `atmosphere.standard_atmosphere` preset now
  carries its standard water column (Gap 57). When
  `precipitable_water_cm` is left at its schema default, the simple-model
  loader substitutes the profile's McClatchey/MODTRAN column
  (tropical 4.11 cm, midlat_summer 2.92, midlat_winter 0.85,
  subarctic_summer 2.08, subarctic_winter 0.42; us_standard stays 1.4) —
  previously "tropical" silently ran US-standard humidity. An explicitly
  set `precipitable_water_cm` always wins (provenance-based). Configs
  using a non-default profile without explicit PWV shift: the
  `mwir_leo_minimal` golden (midlat_summer) drops 52% in signal / 31% in
  SNR (more water → less MWIR transmission; regenerated via
  `update_golden.py` with the §5.3 protocol), and the Cell-28 LWIR anchor
  repins NEDT +0.9% / L@8µm −34%. Default-everything (us_standard)
  configs are bit-identical.

### Fixed
- **Results-affecting (defocused configs; moderate):** defocus is now
  unified as pupil Zernike Z4 on BOTH spatial paths (CU-058, Rule 4). The
  PSF path previously applied a Gaussian kernel (σ = |δ|/(4·f/#·√3)) while
  the MTF product path folded Z4 into the pupil — and, when scalar-RMS WFE
  was combined with defocus, discarded the RMS screen entirely, so any such
  config structurally failed the dual-path consistency check (scenario 7.3:
  max_err 0.169 vs tol 0.05). Now `_add_defocus_to_wfe` preserves the
  scalar-RMS screen (screen + Z4 in one pupil phase), the fold happens once
  before both paths, and the former Gaussian defocus kernel — plus the
  `optics.defocus` module (`defocus_kernel_2d`, `defocus_sigma_m`) and the
  `defocus_sigma_m` stage output — are removed. PSF-path spatial metrics for
  defocused systems change (Gaussian → true Z4 defocus OTF, ~few % at
  moderate defocus); configs with `defocus_um = 0` (all goldens) are
  unchanged. Also fixes a latent reference-wavelength bug: the folded Z4 is
  now rescaled to the WFE's reference wavelength, so the defocus OPD is
  correct when `reference_wavelength_um` differs from band center. All three
  pupil-phase dispatch sites now share one builder
  (`pupil_phase.make_pupil_phase_for_wfe`).
- Saturated `contrast_snr` is now flagged, not reported silently (CU-061).
  When the pixel saturates the readout caps the signal (and its shot noise)
  at full well but the contrast ΔS is not re-derived from the clipped
  signals, so `contrast_snr = ΔS/σ` was inflated and unreliable.
  `compute_contrast_snr` now detects the clip (`signal_e_final < signal_e`),
  emits a `UserWarning`, and sets `failure_reason` on the `contrast_snr_result`
  (so `.ok` is False). The metric value is unchanged for unsaturated runs
  (no golden impact); only the flag/warning are new.
- **Results-affecting (stray light / noise; large where used):** veiling-glare
  stray light (`optics.stray.input_mode = veiling_glare`) was effectively
  inert (CU-062). `OpticsStage` scaled the in-FOV image-plane irradiance by
  the pixel IFOV solid angle `Ω_pixel = pitch²/focal²` instead of the f-cone
  solid angle `Ω_cone = A_collect/focal²`, under-counting stray by
  `A_collect/A_pixel ≈ (D/pitch)²·π/4` (~10⁷–10⁸) so any `veiling_glare_fraction`
  produced ~zero stray. Now `stray_e = vgf × signal_e` for a uniform extended
  scene. Only affects runs using `veiling_glare` mode with a non-zero fraction
  (default 0.0 → no change; goldens unaffected); such runs gain the correct
  stray-light shot-noise penalty (lower SNR/NIIRS). `absolute_irradiance` and
  `spectral_file` modes were already correct.

### Changed
- Lab/ground-test scenarios reachable from the config surface (Gap 42):
  `source.no_atmosphere_subcase` ∈ {`ground_test`, `lab_test`} now builds a
  grey-body chamber/test-range background `L_bg(λ) = ε_bg·B(λ, T_bg)` from
  `source.background.temperature`/`.emissivity` (which Decision #15 makes
  valid for the no-atmosphere sub-cases) instead of raising and requiring a
  manual `UserSpectralBackground` injection. Warns if the chamber
  temperature is left at the schema default (Rule 17). A measured `L_bg(λ)`
  can still be injected directly. **Behaviour change:** these sub-cases
  previously raised `ParameterBoundsError` at inference; they now run. No
  golden change (no golden used these sub-cases).

### Added
- Spectral target emissivity input (Gap 47): new parameter
  `source.target.emissivity_path` — a 2-column `(wavelength_um, emissivity)`
  CSV. When set, the source inferrer builds the thermal descriptor with a
  spectral ε(λ) (`L_t(λ) = ε(λ)·B(λ, source.target.temperature)`) instead of
  a grey scalar, reusing the existing `SpectralData` emissivity that
  `T1Thermal`/`T3Mixed` already accept. Mutually exclusive with the scalar
  `source.target.emissivity` and every reflective / radiance /
  brightness-temperature surface (raises `ParameterBoundsError`). Opt-in;
  goldens unchanged. Retires the S8 `user_radiance_path` workaround for
  spectral-emissivity thermal targets (scenario 4.3).
- Minimum resolvable temperature / contrast (Gap 53):
  `radiant.performance.minimum_resolvable` —
  `minimum_resolvable_temperature_K` (MRT = k·NETD/MTF_sys(f)) and
  `minimum_resolvable_contrast` (MRC = k·NEΔρ/MTF_sys(f)), the
  contrast-limited resolution metrics (k = 2.25 observer SNR default). New
  metric `mrt_at_nyquist_K` (additive; requires NEDT + MTF). New error
  class `MinimumResolvableError`. Companion to the sampling-limited Johnson
  model; consumed by scenario 3.5.
- Extended target-vs-background contrast (ADR-0005, Gap 52): new
  parameters `source.contrast_reference.temperature` and
  `source.contrast_reference.emissivity` make `contrast_snr` a true
  two-pixel spatial differential in the extended regime — `ΔS = S_target −
  S_reference`, combined noise `√(N_t² + N_ref²)` — which nulls at the
  radiance crossover. The reference is metric-only: it never enters the
  noise budget, so absolute SNR (and Decision #13's pinned anchors) are
  unchanged. Opt-in (`temperature = 0` disables it, the default), so no
  golden result moves. Supersedes the two-pixel-differencing workaround in
  scenarios 4.3/4.4. New error class n/a; explicitly distinct from the
  deprecated `source.background.*` (Decision #15).
- D*/NEP/NETD noise-spec converters (scenarios 6.1, 4.5 prerequisite):
  `performance/detectivity.py` (`nep_from_dstar`/`dstar_from_nep`,
  `D* = √(A·Δf)/NEP`), `performance/nep_electrons.py`
  (`nep_from_noise_electrons`/`noise_electrons_from_nep`,
  `NEP = σ_e·hc/(η·λ·t_int)`, plus `integrating_bandwidth_hz`), and
  `performance/nep_netd.py` (`netd_from_nep`/`nep_from_netd`,
  `NETD = NEP/(dP/dT)`). Standard radiometric definitions relating
  datasheet detector figures of merit to the chain's electron-domain
  noise. New error classes `DetectivityError`, `NepElectronsError`,
  `NepNetdError`. No chain change.
- QE temperature dependence (Gap 48): new parameters
  `detector.qe_temperature_coeff_per_K` and `detector.qe_temperature_ref_K`
  apply a linear QE(T) factor `1 + coeff·(T_det − T_ref)` to the scalar
  `qe_value` or the `qe_table_path` curve, folded in at the API layer.
  **Results-affecting only when `coeff ≠ 0`** (lower/higher QE shifts SNR
  and NEDT); the default `coeff = 0` is byte-identical (goldens intact).
  QE is clamped to [0, 1] with a `UserWarning` if the factor pushes it out
  of range (Rule 17).
- Spectral QE from a file (Gap 44): `detector.qe_table_path` — a
  schema-only parameter until now — is wired. When set, `RadiantSession`
  loads the wavelength-vs-QE CSV (`io.qe_csv`, Rule 6: file I/O in the api
  layer) onto the wavelength grid and applies it spectrally, superseding
  the scalar `detector.qe_value`; QE past the measured cutoff is zero.
  Absent a path, the scalar `qe_value` behaviour is unchanged (goldens
  intact).
- Arbitrary / measured pupil-mask injection (Gap 54): inject
  `optics_config["pupil_mask_override"]` (a `(pupil_npix, pupil_npix)`
  amplitude array) via `extra_stage_outputs` to supersede the parametric
  circular/obscuration/spider pupil — for segmented or non-circular
  apertures. Threaded through `make_pupil_amplitude` into both the PSF and
  MTF paths (Rule 4). No default-behavior change (absent ⇒ parametric
  mask; 504 optics + 10 golden tests unchanged).
- Detector figures of merit (Gap 45): `performance/dark_crossover_rate.py`
  (`dark_shot_crossover_rate_e_per_s` = σ_read²/t_int),
  `performance/blip_rate.py` (`blip_rate_e_per_s` = signal_e/t_int), and
  `performance/noise_equivalent_irradiance.py`
  (`noise_equivalent_irradiance_ph_s_cm2`). Standalone helpers for the
  detector cooler-budget/sensitivity trade; new error classes. No chain
  change.
- Radiometric-calibration analysis (Gap 46):
  `radiant.api.calibration_analysis` — `analyze_calibration` → a
  `CalibrationReport` (gain/offset fit, temperature & radiance
  responsivity, linearity residuals % full-scale, N-frame temperature
  uncertainty), plus the underlying `gain_offset_fit`,
  `linearity_residuals_pct_fs`, etc. New error `CalibrationAnalysisError`.
  Pure sweep-array analysis; no chain change.
- Repeat-ground-track & revisit model (Gap 51):
  `radiant.core.repeat_ground_track` — `nodal_regression_rate_deg_per_day`
  (J2 secular Ω̇), `sun_synchronous_inclination_deg`,
  `equatorial_ground_track_spacing_m`, and a first-order
  `revisit_interval_days`. New Earth constant `J2_earth`; new error class
  `RepeatGroundTrackError`. Standalone analysis model — no chain change.
- Diffraction-limited-resolution metrics (Gap 49):
  `diffraction_limit_angular_urad` (Rayleigh `1.22 λ_c / D`) and
  `diffraction_limit_ground_m` (projected to the slant range, companion to
  GSD) in the new `performance/diffraction_limit.py`. Analysis outputs
  only — no existing result changes.
- Sampling-regime flag (Gap 50): `sampling_regime_code` metric
  (0 detector-limited / 1 near-critical / 2 diffraction-limited, from
  `q_center`) in the new `performance/sampling_regime.py`. New error
  classes `DiffractionLimitError`, `SamplingRegimeError`. Additive
  metrics; goldens unchanged.
- Spider-vane / secondary-support struts (scenario 1.5 prerequisite):
  new optics parameters `optics.n_spiders`, `optics.spider_width_m`,
  `optics.spider_angle_deg` implement RADIANT_Optics.md §3.3 (previously
  aspirational). Struts enter the pupil amplitude mask
  (`make_pupil_amplitude` via the new `SpiderVaneSpec`), so they degrade
  **both** spatial paths (PSF and MTF) per Rule 4, and subtract from the
  radiometric clear area (`CircularAperture.clear_area_m2`).
  **Results-affecting only when `n_spiders > 0` and `spider_width_m > 0`**
  — lowers SNR (less collecting area), EE_box, and RER (diffraction
  spikes); the `strehl` metric is unaffected (vanes are common-mode in
  the WFE reference). Default (no struts) reproduces all existing results
  byte-for-byte (496 optics + 10 golden tests unchanged).
- Johnson-criteria DRI calculator (scenario 4.2 prerequisite):
  `radiant.performance.johnson_criteria` — `johnson_range_m`,
  `resolved_cycles`, and the standard `JOHNSON_N50` cycle table
  (detection/orientation/recognition/identification). Computes the range
  at which a discrimination task's N50 cycles are resolved across a
  target's critical dimension (`R = D / (2·IFOV·N50)`). Sampling-limited
  form (no MRT/MRC coupling). New error class `JohnsonCriteriaError`.
- Orbit-kinematics calculator (scenario 3.1 prerequisite):
  `radiant.core.orbit` — `orbital_velocity_m_s`, `orbital_period_s`, and
  `ground_track_speed_m_s` for a circular LEO altitude (two-body,
  spherical Earth, non-rotating ground track). Feeds the
  `ground_speed_m_s` input that `performance.access_rate` could not
  itself compute. New Earth gravitational-parameter constant
  `mu_earth_m3_s2` in `core.constants`; new error class `OrbitError`.
- Solar-geometry calculator (scenario 1.2 prerequisite):
  `radiant.core.solar_geometry` — `solar_zenith_angle_rad(latitude_deg,
  day_of_year, local_solar_time_hr)`, `solar_declination_deg`
  (Spencer's series), and `local_solar_time_from_ltan` for
  sun-synchronous orbits. Converts date/latitude/LTAN into the solar
  zenith angle for `geometry.solar_zenith_rad`. New error class
  `SolarGeometryError`.
- ASTER spectral-library import (scenario 1.3 prerequisite):
  `radiant.io.aster_library.load_aster_spectrum` parses JPL/NASA ASTER
  library text files (metadata header + wavelength/reflectance columns,
  descending order handled) into an `AsterSpectrum` with `emissivity()`
  (ε = 1 − ρ, opaque scene material) and `band_averaged_emissivity()`.
  New error class `AsterLibraryError`. No extrapolation outside the
  measured range.
- Batch matrix execution (scenario 4.1 prerequisite):
  `radiant.api.batch.BatchRunner` — the `BatchRunner` named in the
  architecture's api layout — runs one evaluation per cell of a labeled
  cartesian grid (targets × atmospheres × sensors), with per-cell
  parameter overrides and Rule 17 failure capture (a failed cell is a
  recorded `error` row, never silently dropped). Returns a `BatchResult`
  with a `pivot()` helper. New error class `BatchRunnerError`.
- Target-library import (scenario 4.1 prerequisite):
  `radiant.io.target_library.load_target_library` reads a mission target
  list workbook into validated `TargetEntry` objects with derived
  `projected_area_m2`; lazy openpyxl (actionable error naming the
  `[scenarios]` extra). New error class `TargetLibraryError`.
- Vendor detector-datasheet importers (scenario 2.1 prerequisites):
  `radiant.io.qe_csv.load_qe_csv` reads wavelength-vs-QE vendor CSVs
  (nm/µm × percent/fraction, header-token or explicit unit resolution)
  into a canonical-units `QeCurve` with grid evaluation and band
  averaging; `radiant.io.dark_current_csv.load_dark_current_csv` reads
  `T_K, Jdark_A_cm2` curves into a `DarkCurrentCurve` with
  Arrhenius-faithful interpolation (ln J linear in 1/T),
  `dark_rate_e_per_s(T, pixel_pitch_m=)` conversion (J·A_pixel/q), and
  the inverse `temperature_at_rate`. New error classes `QeCsvParseError`
  and `DarkCurrentCsvParseError` (both `RadiantError`). Neither loader
  extrapolates outside the measured range by default.

### Fixed
- Scatter (Gap 31) and defocus (Gap 29) kernel sizing crashed with
  `ValueError: npix must be a positive odd integer, got 256` whenever
  the 6σ kernel span exceeded the PSF grid — the odd-forcing happened
  before the cap to the (even) grid size. The cap now clamps to the
  largest odd size within the grid. Fine-spacing configurations (VNIR
  band, small pixels) with `optics.surface_roughness_nm` or large
  `optics.defocus_um` now run; no numeric change for configurations
  that previously ran. Found by the scenario 7.3 refresh.

### Deprecated
- `optics.cold_stop_efficiency` renamed to `optics.nearfield_fraction`
  (Gap 12) — the old name inverted the vendor convention ("100%
  efficient cold stop" = complete blocking, but η=1 here means *no*
  cold stop). Same semantics, no numeric change:
  `nearfield_fraction = 1 − vendor_cold_stop_efficiency`. The old name
  still works via a new parameter-alias mechanism
  (`ParameterDef.deprecated_aliases`) with a `DeprecationWarning`, and
  will be removed in a future release.

### Fixed
- **Results-affecting (labels/exports only):** the MTF product-path
  frequency grid `ChainState.spatial_freq_cycles_per_mrad` (and
  `MTFBudgetResult.freq_cycles_per_mrad`) stored values 1e6× true
  cycles/mrad (conversion used `× f·1e3` instead of `× f·1e-3`). All
  internal consumers round-tripped with the same inverse factor, so
  MTF curves, metrics, and golden results are unchanged — but the grid
  values themselves and the cycles/mrad axis of `result.plot.mtf()`
  now read correctly (e.g. 33.3 cy/mrad at Nyquist for an 18 µm pixel
  at f = 1.2 m, previously 3.33e7). Found during Gap 27.

### Added
- `scenarios` optional-dependency group (`pip install -e ".[scenarios]"`):
  openpyxl + matplotlib, required by the scenario run scripts (CU-057).
- Zemax Zernike importer (Gap 26): `radiant.io.zemax_zernike.
  load_zemax_zernike` parses "Zernike Standard Coefficients" text
  exports (Noll-indexed waves, UTF-8/UTF-16 tolerant) into the existing
  Zernike WFE pipeline via `ZemaxZernikeResult.to_wavefront_error()`.
- Measurement import + comparison (Gap 30):
  `radiant.io.measurement.load_measured_curve` (CSV → `MeasuredCurve`)
  and `radiant.api.compare.compare_mtf` (unit-aware measured-vs-predicted
  MTF residuals, overlap-only interpolation). Excel import out of scope
  (CSV export required).
- Surface-roughness scatter (Gap 31): new `optics.surface_roughness_nm`
  and `optics.scatter_halo_sigma_um` parameters drive a TIS model
  (`optics/scatter.py`): TIS = 1 − exp(−(4πσ/λ)²), scattered fraction
  into a Gaussian halo. **Results-affecting only when roughness is set
  nonzero** — lowers MTF/RER at all frequencies via both spatial paths
  (Rule 4 Fourier pair); default 0 preserves all results.
- MTF budget reporting (Gap 19): `MTFBudgetResult.table()` and
  `plot_mtf_budget` / `ResultPlotNamespace.mtf_budget()` — human-facing
  views over the existing per-contributor MTF-at-Nyquist decomposition.
- `Sensor.solve_for(param, target, bounds=, metric=)` (Gap 10): inverse
  solver — Brent root-finding for the parameter value that hits a target
  metric, replacing sweep-and-interpolate. New `api/solve.py` module,
  `SolveResult` exported from `radiant.api`.
- `ErrorBudget` / `BudgetContributor` (Gaps 23+28): generic RSS error
  budget with allocation tracking, headroom queries, budget table, and
  dict round-trip — one model for jitter (µrad) and WFE (waves)
  budgets. Exported from `radiant.api`.
- Unit-aware parameter input (Gap 6): `ParameterSet.set(name, value,
  unit=...)` and `Sensor.set(dotpath, value, unit=...)` convert from the
  caller's native unit (cm, ms, %, min, …) at the set boundary. Bounds
  validated after conversion; original value+unit recorded in
  provenance. Omitting `unit=` keeps historical input-unit behavior —
  no result changes.
- `convert_spatial_frequency()` (Gap 27): cy/m ↔ cy/mm ↔ cy/mrad ↔
  cy/pixel conversion utility in the new
  `performance/frequency_units.py` module.
- PSF weighting spectrum override (Gap 17): `RadiantSession.run` gains an
  `extra_stage_outputs` injection argument;
  `optics_config["psf_weighting_spectrum"]` (SpectralData) decouples
  polychromatic PSF weighting from the scene spectrum. Radiometry is
  unaffected; weighting provenance recorded in
  `stage_outputs["optics"]["psf_weighting_source"]`. No default-behavior
  change.
- Electronics MTF (Gap 32): new `readout.electronics_sigma_um` parameter
  (default 0.0 = ideal electronics, no result change) models readout
  amplifier bandwidth as a Gaussian blur along the readout (x) axis.
  **Results-affecting only when set nonzero** — enters both the
  EffectivePSF and the MTF product per Rule 4, lowering x-axis MTF,
  RER, and NIIRS. New `readout/electronics_mtf.py` module and
  `mtf_electronics_x/_y` product terms.
- `giqe5_sensitivity()` (Gap 20): analytic d(NIIRS)/d(GSD, RER, SNR, H, G)
  partials and exact per-+1% deltas in the new
  `performance/giqe_sensitivity.py` module. Analysis utility only — no
  chain output changes.
- GIQE-5 calibration-range flagging (Gap 22): NIIRS results outside the
  published fit ranges (GSD 3–80 cm, RER 0.2–0.95, SNR 2–130) now carry
  `GIQEResult.extrapolated=True`, a `UserWarning`, and a new
  `niirs_extrapolated` metric (0.0/1.0). The NIIRS value itself is
  unchanged — flagging only. The prior ad-hoc low-end checks (SNR < 5,
  RER < 0.2) are replaced by the spec-based ranges, both ends.
- `optics.scalar_emissivity` parameter (default 0.0): declared effective
  emissivity of the lumped train in scalar transmission mode, enabling
  warm-optics nearfield emission from the simplest input mode (Gap 37).
  **Results-affecting only when set nonzero** — it adds nearfield background
  and shot noise (lower SNR, higher NEDT) for warm-optics MWIR/LWIR
  configurations; the default preserves all existing results (`ε = 0`,
  nearfield dark). `OpticalElement` gains a `declared_emissivity` field,
  legal only on `kind=LUMPED` pseudo-elements; `KirchhoffViolationError`
  on physical surfaces or when `ε + τ + R > 1`.
