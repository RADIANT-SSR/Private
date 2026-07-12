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

### Fixed
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
