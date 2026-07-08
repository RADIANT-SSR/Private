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
