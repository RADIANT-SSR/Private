# RADIANT Gap Registry

Canonical list of gaps discovered during scenario exercises. Each gap is
logged with the scenario that revealed it, a workaround (if any), and
which scenarios are blocked until it's resolved.

After a gap is fixed, rerun the originating scenario to verify the fix.

---

## Status Key

| Status | Meaning |
|--------|---------|
| OPEN | Not yet addressed |
| WORKAROUND | Scriptable workaround exists, not integrated into RADIANT |
| FIXED | Implemented and verified by rerunning originating scenario |

---

## Gap 1: IPC not wired into signal chain

| Field | Value |
|-------|-------|
| **Found in** | Scenario 2.3 (Mike — IPC impact on MTF) |
| **Status** | FIXED |
| **Description** | IPC is now wired end-to-end. The detector stage reads `detector.ipc_coupling`, generates a 3×3 IPC kernel via `ipc_kernel()`, and stores it in `stage_outputs["detector"]["ipc_kernel"]`. The performance stage applies it to the EffectivePSF via `epsf.with_kernel("ipc", kernel)` before computing all spatial metrics (MTF, EE, RER, FWHM). This ensures Rule 4 compliance — all spatial metrics derive from the same IPC-convolved PSF. |
| **Fix** | (1) Added `EffectivePSF.with_kernel()` method for post-hoc kernel convolution (7 tests in `test_psf.py`). (2) Detector stage stores IPC kernel when `ipc_coupling > 0`. (3) Performance stage applies IPC kernel before spatial metric computation. (4) 8 integration tests in `test_chain_spatial.py` (kernel stored, history tracking, MTF/RER/FWHM degradation, SNR unchanged, zero-IPC baseline). All tests pass, 0 regressions. |
| **Impact** | MTF, EE, RER, FWHM now fully reflect IPC degradation. Default `ipc_coupling = 0.0` preserves all existing results. |
| **Rerun after fix** | Scenario 2.3 |

---

## Gap 2: SNR = 0 at LEO orbital altitudes (500 km)

| Field | Value |
|-------|-------|
| **Found in** | Scenario 2.3 (Mike — IPC sweep, 500 km altitude) |
| **Previously seen** | GEO template (lwir_geo, 35,786 km) during Phase 2E.3 |
| **Status** | FIXED |
| **Description** | RADIANT returned SNR = 0.00 at 500 km orbit altitude with `atmosphere.model = "simple"`. Root cause: (1) `_h2o_extinction_km()` had no altitude scaling — sea-level H₂O extinction was applied over the full slant path; (2) the mean-altitude × slant-path approximation (`σ(h_mean) × L`) fails catastrophically when the path length far exceeds the species scale heights. |
| **Fix** | Replaced mean-altitude Beer-Lambert with column-integrated optical depth: `OD = σ₀ · H_s · [exp(-h_target/H_s) − exp(-h_sensor/H_s)] × airmass` for each species (Rayleigh H=8km, aerosol H=1.2km, H₂O H=2km). Added 3 new tests including orbital altitude regression test. Updated golden values and integration test parameters (FWC, gain) to accommodate the corrected higher atmospheric transmittance. |
| **Scenarios unblocked** | 1.1, 1.2, 1.4, 3.1, 3.2, 3.4, 3.5 and all orbital scenarios. |
| **Rerun after fix** | Scenario 2.3 (to verify SNR is now non-zero at 500 km) |

---

## Gap 3: NEDT not in result.metrics

| Field | Value |
|-------|-------|
| **Found in** | Scenario analysis (expanded_scenarios.md) |
| **Status** | FIXED |
| **Description** | NEDT is now computed via the Planck-derivative approximation (`compute_nedt_from_snr` in `nedt.py`, which already existed) and reported as `nedt_K` in `result.metrics`. Uses target temperature, SNR, and band-center wavelength. |
| **Fix** | Added `_compute_nedt_metric()` wiring in `stage.py`. 3 new wiring tests in `test_nedt.py` (metrics populated, consistent with pure function, zero-SNR skip). 1698 tests pass, 0 regressions. |
| **Impact** | 10+ scenarios now get NEDT automatically. |
| **Rerun after fix** | Verified: 310 K target, SNR=468, MWIR 4.25 µm → NEDT = 61 mK ✓ |

---

## Gap 4: NIIRS not surfaced in result.metrics

| Field | Value |
|-------|-------|
| **Found in** | Scenario analysis (expanded_scenarios.md) |
| **Status** | FIXED |
| **Description** | NIIRS is now computed via GIQE-5 (vis/nir) or IIRS (mwir/lwir) and reported as `niirs` in `result.metrics`. Band is auto-classified from filter center wavelength. Uses GSD, RER, and SNR from earlier metrics. Skips gracefully when GSD is unavailable (lab/TVAC). |
| **Fix** | Added `_classify_band()` and `_compute_niirs_metric()` wiring in `stage.py`. 14 new tests in `test_niirs.py` (7 band classification, 7 wiring — metrics populated, consistent with pure function, MWIR dispatch, missing GSD/RER/SNR skip, stage outputs). 281 tests pass, 0 regressions. |
| **Impact** | 11 scenarios now get NIIRS automatically. |
| **Rerun after fix** | First scenario that uses NIIRS |

---

## Gap 5: GSD not in result.metrics

| Field | Value |
|-------|-------|
| **Found in** | Scenario analysis (expanded_scenarios.md) |
| **Status** | FIXED |
| **Description** | Ground sample distance is now computed in `_compute_gsd()` in `radiant/performance/stage.py`. Reports `gsd_cross_track_m` and `gsd_along_track_m` in `result.metrics` when `geometry.sensor_altitude_m > 0`. Skips gracefully for lab/TVAC scenarios with no altitude. |
| **Fix** | Added `_compute_gsd()` to `PerformanceStage.run()`. 6 unit tests in `test_gsd.py` (LEO, GEO, airborne, rectangular pixels, no-altitude skip, zero-altitude skip). 1679 tests pass, 0 regressions. |
| **Impact** | 5+ scenarios now get GSD automatically (3.2, 3.4, 1.2, 4.5, 5.2). Also unblocks NIIRS via GIQE-5. |
| **Rerun after fix** | Verified: 18 µm pixel at 500 km, f=1.2 m → GSD = 7.50 m ✓ |

---

## Gap 6: Unit-aware parameter input

| Field | Value |
|-------|-------|
| **Found in** | Scenario 6.3 (Dr. Chen — noise verification) |
| **Status** | OPEN |
| **Description** | `Sensor.set()` only accepts RADIANT canonical units (m, fractions, s). Users must manually convert from their native units (cm, %, ms). `ParameterDef` already has `canonical_unit` and `input_unit` fields but they are not used by `set()`. |
| **Workaround** | Convert in script before calling `sensor.set()` or `Sensor.from_dict()`. |
| **Impact** | Every scenario with non-RADIANT inputs requires manual conversion. Major friction point for GUI. |
| **Fix location** | `radiant/core/parameters.py` — add unit argument to `ParameterSet.set()`. |
| **Effort** | Medium — need unit conversion registry and validation. |
| **Scenarios blocked** | None (workaround always available), but critical for GUI. |
| **Rerun after fix** | Scenario 6.3 |

---

## Gap 7: Parameter name discoverability

| Field | Value |
|-------|-------|
| **Found in** | Scenario 6.3 (Dr. Chen — noise verification) |
| **Status** | FIXED |
| **Description** | `ParameterSet.set()`, `.get()`, `.set_tolerance()`, and `.load_dict()` now include "Did you mean?" suggestions when an unknown parameter name is provided. Uses `difflib.get_close_matches` (cutoff=0.5, top 3 matches). Example: `atmosphere.mode` → `Did you mean: 'atmosphere.model'?` |
| **Fix** | Added `_suggest()` helper to `ParameterSet` in `radiant/core/parameters.py`. Updated 3 KeyError raise sites. 9 new tests in `test_parameters.py` (close match, correct name, mode→model, no match, get(), set_tolerance(), load_dict()). 200 tests pass, 0 regressions. |
| **Impact** | Better UX for all users; foundation for GUI autocomplete. |
| **Rerun after fix** | N/A — UX improvement |

---

## Gap 8: Strehl ratio not in result.metrics

| Field | Value |
|-------|-------|
| **Found in** | Scenario analysis (expanded_scenarios.md) |
| **Status** | FIXED |
| **Description** | Strehl ratio is now computed via the Marechal approximation: `S = exp(-(2π·OPD_rms/λ)²)` using WFE from optics params. Reported as `strehl` in `result.metrics`. |
| **Fix** | Added `strehl.py` with `compute_strehl()` pure function. Wired into `PerformanceStage` via `_compute_strehl_metric()`. 7 unit tests in `test_strehl.py` with 3 truth anchors (zero WFE, λ/14 at ref, λ/14 at MWIR). 1695 tests pass, 0 regressions. |
| **Rerun after fix** | Verified: 0.05 waves at 4.25 µm → Strehl = 0.906 ✓ |

---

## Gap 9: Full MTF curve not output

| Field | Value |
|-------|-------|
| **Found in** | Scenario analysis (expanded_scenarios.md) |
| **Status** | FIXED |
| **Description** | Full 1-D MTF curves (both x and y axes) are now stored in `result.stage_outputs["performance"]` as `mtf_freq_x`, `mtf_x`, `mtf_freq_y`, `mtf_y` (numpy arrays of spatial frequency in cycles/m and corresponding MTF values). The scalar `mtf_at_nyquist` metric is still computed from the x-axis curve. |
| **Fix** | Added 4 `with_stage_output` calls in `_compute_spatial_metrics`. 8 new tests in `test_chain_spatial.py` (presence, MTF(0)=1, monotonicity, non-negative, freq ordering, x/y symmetry, consistency with EffectivePSF). 289 tests pass, 0 regressions. |
| **Impact** | 4+ scenarios can now access full MTF curve directly from results. |
| **Rerun after fix** | Scenario 5.1 or 7.3 |

---

## Gap 10: No inverse solver / parameter matching

| Field | Value |
|-------|-------|
| **Found in** | Scenario 7.4 (Karen — cold stop sweep) |
| **Status** | OPEN |
| **Description** | RADIANT has no built-in mechanism to find the parameter value that produces a target output (e.g., "what `cold_stop_efficiency` gives 44,000 e⁻ background?"). A proper root-finding solver would be more efficient and generalizable than sweep + interpolation. |
| **Workaround** | Sweep the parameter space and linearly interpolate to the target value. |
| **Impact** | Any scenario requiring inverse analysis (matching measured data to model parameters). Common in test engineering workflows. |
| **Fix location** | `radiant/api/` — add `Sensor.solve_for(parameter, target_metric, target_value)` or similar. |
| **Effort** | Medium — needs root-finding wrapper around forward model. |
| **Scenarios blocked** | None (workaround available). |
| **Rerun after fix** | Scenario 7.4 |

---

## Gap 11: No per-element nearfield breakdown

| Field | Value |
|-------|-------|
| **Found in** | Scenario 7.4 (Karen — cold stop sweep) |
| **Status** | CLOSED |
| **Description** | RADIANT outputs total `nearfield_e` but does not break it down by optical element (primary mirror, secondary, fold mirror, field lens, filter). Test engineers need to know which element contributes most to nearfield emission to diagnose cold stop leakage directionality. |
| **Resolution** | `compute_nearfield_irradiance()` now returns `NearfieldResult` with `total` (SpectralData) and `per_element` (dict[str, SpectralData]). Each per-element contribution includes cold-stop efficiency scaling. Sum of per-element equals total (identity tested). OpticsStage stores `nearfield_per_element` in `stage_outputs["optics"]`. |
| **Impact** | Cold stop and stray light diagnostics. |
| **Fix location** | `radiant/optics/element_list.py`, `radiant/optics/stage.py` |
| **Effort** | Medium — element list already iterated, just need per-element bookkeeping. |
| **Scenarios blocked** | None (total nearfield is sufficient for basic analysis). |
| **Rerun after fix** | Scenario 7.4 |

---

## Gap 12: cold_stop_efficiency naming convention mismatch

| Field | Value |
|-------|-------|
| **Found in** | Scenario 7.4 (Karen — cold stop sweep) |
| **Status** | OPEN |
| **Description** | RADIANT's `cold_stop_efficiency` is the fraction of the FPA hemisphere filled by warm-emitting elements. η=0 means perfect cold stop, η=1 means no cold stop. This is **inverted** from vendor convention where "100% efficient cold stop" means complete blocking. The naming causes confusion. |
| **Workaround** | Scripts include explicit convention notes in output. |
| **Impact** | Every user working with cold stop specs from vendors will be confused. Critical for GUI tooltips. |
| **Fix location** | Consider renaming to `cold_stop_leakage` or `nearfield_fraction`, or add prominent documentation/GUI tooltip. |
| **Effort** | Small (rename) to Trivial (documentation). |
| **Scenarios blocked** | None. |
| **Rerun after fix** | Scenario 7.4 |

---

## Gap 13: No Q parameter (sampling ratio) in result.metrics

| Field | Value |
|-------|-------|
| **Found in** | Scenario 5.2 (Tom — pixel pitch optimization) |
| **Status** | FIXED |
| **Description** | The sampling parameter Q = λ·f/#/p is now computed in `radiant/performance/sampling.py` and reported as `q_center`, `q_min`, and `q_max` in `result.metrics`. Reports Q at band center and both band edges to show sampling variation across the spectral band. |
| **Fix** | Added `sampling.py` with `compute_q()` pure function and `SamplingResult` dataclass. Wired into `PerformanceStage` via `_compute_q_metrics()`. 7 unit tests in `test_sampling.py`. 1688 tests pass, 0 regressions. |
| **Rerun after fix** | Verified: f/4, 18 µm, 3.5–5.0 µm → Q = 0.944 (center), 0.778 (min), 1.111 (max) ✓ |

---

## Gap 14: No aliased / folded MTF model

| Field | Value |
|-------|-------|
| **Found in** | Scenario 5.2 (Tom — pixel pitch optimization) |
| **Status** | CLOSED (Prompt 3C.4) |
| **Description** | RADIANT computes the pre-sampling (optical) MTF but does not model aliasing — spatial frequency folding at Nyquist. For undersampled systems (Q < 1), high-frequency scene content folds back below Nyquist, producing spurious apparent contrast. The reported MTF at Nyquist can be misleadingly high for aliased systems. |
| **Workaround** | None — aliasing analysis requires a folded-MTF computation not currently available. |
| **Impact** | Any undersampled system (Q < 1) analysis gives incomplete spatial performance picture. |
| **Fix location** | `radiant/performance/` or `radiant/optics/` — add folded MTF computation that sums optical MTF at multiples of Nyquist. |
| **Effort** | Medium — requires folded-MTF math and decision on where in the chain to apply. |
| **Scenarios blocked** | None (pre-sampling MTF is still useful). |
| **Rerun after fix** | Scenario 5.2 |
| **Resolution** | New `performance/folded_mtf.py` computes MTF_folded(f) = Σ MTF_optical(|f + k·f_Ny|) for k=-3..+3. Returns `FoldedMTFResult` with folded MTF, alias fraction. Wired into `_compute_spatial_metrics` — always computed, stored as `folded_mtf_x/y` stage outputs and `mtf_folded_at_nyquist`, `alias_fraction_at_nyquist` metrics. |

---

## Gap 15: MTF = 0 at high-Q (small pixel) configurations — needs investigation

| Field | Value |
|-------|-------|
| **Found in** | Scenario 5.2 (Tom — pixel pitch optimization, 8 µm pixel at f/4) |
| **Status** | CLOSED (not a bug) |
| **Description** | **Investigated and confirmed physically correct.** At 8 µm pitch, f/4, λ=4.25 µm: detector Nyquist = 62,500 cy/m exceeds diffraction cutoff = 58,824 cy/m by 6.2%. The optics cannot pass spatial information at the Nyquist frequency, so MTF = 0 is the correct answer. PSF grid resolution verified adequate (32.9 samples across FWHM, FFT Nyquist 15× detector Nyquist). No interpolation or aliasing issues found. |
| **Fix** | Added a diagnostic `logger.warning` in `_compute_spatial_metrics` when Nyquist > diffraction cutoff. Warning includes both frequencies, wavelength, f/#, and Q value so users understand why MTF = 0 rather than suspecting a bug. 2 integration tests (warning fires for 8 µm pixel, no warning for 18 µm pixel). |
| **Impact** | Users now get clear diagnostic when operating in this regime. |
| **Rerun after fix** | N/A — behavior unchanged, diagnostic added |

---

## Gap 16: Per-wavelength PSFs not exposed from polychromatic computation

| Field | Value |
|-------|-------|
| **Found in** | Scenario 5.3 (Tom — mono vs. poly PSF) |
| **Status** | CLOSED (Prompt 3C.2) |
| **Description** | `compute_polychromatic_psf()` computes monochromatic PSFs at each wavelength internally but discards them after accumulation into the weighted average. Per-wavelength PSF arrays are never stored in `stage_outputs`. Chromatic PSF visualization requires N separate narrow-band evaluations. |
| **Workaround** | Run RADIANT N times with narrow bands (±50 nm) centered at each wavelength. |
| **Impact** | Chromatic PSF analysis, per-wavelength MTF overlays, FWHM(λ) plots. |
| **Fix location** | `radiant/optics/diffraction.py` — store per-λ PSFs during polychromatic computation, expose in `stage_outputs["optics"]`. |
| **Effort** | Small — loop already exists, just need to store intermediate arrays. |
| **Scenarios blocked** | None (workaround available but expensive). |
| **Rerun after fix** | Scenario 5.3 |
| **Resolution** | `PolychromaticPSFResult` dataclass stores `per_wavelength` dict when `store_per_wavelength=True`. `OpticsStage` stores `per_wavelength_psfs` as `dict[float, EffectivePSF]` in `stage_outputs["optics"]` when `psf_n_wavelengths > 1`. |

---

## Gap 17: No arbitrary source spectrum for PSF weighting

| Field | Value |
|-------|-------|
| **Found in** | Scenario 5.3 (Tom — mono vs. poly PSF) |
| **Status** | OPEN |
| **Description** | The polychromatic PSF weighting uses the scene source spectrum (post-atmosphere, post-optics photon flux). There is no mechanism to override this — e.g., to compare blackbody-weighted vs. solar-reflection-weighted PSFs for VNIR bands. Changing the source temperature also changes radiometric results (SNR, signal), making isolated PSF-weighting comparisons impossible. |
| **Workaround** | None — PSF weighting is coupled to the source spectrum. |
| **Impact** | Dual-use systems (thermal + reflected) where PSF weighting depends on the observation mode. |
| **Fix location** | `radiant/optics/_schema.py` + `diffraction.py` — add optional `optics.psf_weighting_spectrum` parameter. |
| **Effort** | Small. |
| **Scenarios blocked** | None. |
| **Rerun after fix** | Scenario 5.3 |

---

## Gap 18: Platform jitter not wired into signal chain

| Field | Value |
|-------|-------|
| **Found in** | Scenario 5.4 (Tom — jitter tolerance) |
| **Status** | FIXED |
| **Description** | Platform jitter math existed (`platform/jitter.py` with 4 functions, all tested) but was not wired into the chain. There was no `PlatformStage`, no `_schema.py` for jitter parameters, and `PerformanceStage` did not read jitter-degraded PSFs. Scenario 5.4 initially had to use analytic workarounds (erfinv/erf RER approximation) outside RADIANT. |
| **Fix** | (1) Created `platform/_schema.py` with 4 `ParameterDef` objects (`jitter_rms_urad`, `jitter_axes`, `jitter_rms_x_urad`, `jitter_rms_y_urad`). (2) Created `platform/stage.py` implementing `PlatformStage` — reads ePSF from optics, generates Gaussian jitter kernel, convolves via `epsf.with_kernel("jitter", kernel)`. (3) Registered in `api/session.py` (slot 4 of 8) and `api/_param_registry.py`. (4) Updated `PerformanceStage` to read platform ePSF first, falling back to optics. (5) 13 unit tests in `platform/tests/test_stage.py`. Default `jitter_rms_urad = 0.0` preserves all existing results. 1759 tests pass, 0 regressions. |
| **Impact** | Jitter tolerance studies now use full ePSF convolution instead of analytic approximation. Full-chain approach yields ~20% tighter (more conservative) jitter thresholds because it captures Airy ring tails. |
| **Rerun after fix** | Scenario 5.4 — rewritten and verified with full-chain results |

---

## Gap 19: No MTF budget decomposition

| Field | Value |
|-------|-------|
| **Found in** | Scenario 5.4 (Tom — jitter tolerance) |
| **Status** | OPEN |
| **Description** | RADIANT computes a system MTF but doesn't decompose it into individual contributors (optics, detector, jitter, smear, etc.) in a way that's easy to inspect. An MTF budget table showing each contributor's MTF at Nyquist would be valuable for optical designers. |
| **Workaround** | Compute individual MTF terms manually in scripts (e.g., MTF_jitter = exp(-2π²σ²f²)). |
| **Impact** | Optical design trade studies, jitter/smear allocation. |
| **Fix location** | `radiant/performance/stage.py` — decompose system MTF into per-contributor terms. |
| **Effort** | Medium — need to track per-kernel MTF contributions through ePSF convolution chain. |
| **Scenarios blocked** | None (workaround available). |
| **Rerun after fix** | Scenario 5.4, 7.3 |

---

## Gap 20: No GIQE-5 sensitivity analysis

| Field | Value |
|-------|-------|
| **Found in** | Scenario 5.4 (Tom — jitter tolerance) |
| **Status** | OPEN |
| **Description** | The GIQE-5 equation has terms for GSD, RER, SNR, H, and G. A built-in sensitivity analysis showing d(NIIRS)/d(parameter) for each would help designers understand which parameter to improve. For example, d(NIIRS)/d(RER) = 3.32 / (RER × ln(10)) — very steep near baseline RER. |
| **Workaround** | Compute partial derivatives analytically in scripts. |
| **Impact** | Any NIIRS optimization study. |
| **Fix location** | `radiant/performance/giqe.py` — add `giqe5_sensitivity()` function. |
| **Effort** | Small — analytic derivatives of GIQE-5 are straightforward. |
| **Scenarios blocked** | None. |
| **Rerun after fix** | Scenario 5.4 |

---

## Gap 21: No jitter-frequency dependence (PSD)

| Field | Value |
|-------|-------|
| **Found in** | Scenario 5.4 (Tom — jitter tolerance) |
| **Status** | OPEN |
| **Description** | The current jitter model assumes "well-sampled" jitter (many cycles during integration). Real jitter has a power spectral density (PSD). Low-frequency jitter (< 1/t_int) produces pointing error (frame shift), not blur. RADIANT should accept a jitter PSD and compute the in-band blur vs. out-of-band pointing error partition. |
| **Workaround** | None — requires PSD-aware jitter model. |
| **Impact** | Accurate jitter tolerance derivation for systems with colored jitter spectra. |
| **Fix location** | `radiant/platform/jitter.py` — add PSD-based sigma computation with integration-time-dependent frequency cutoff. |
| **Effort** | Large — requires PSD input format, frequency integration, and partition logic. |
| **Scenarios blocked** | None (RMS assumption is standard for preliminary design). |
| **Rerun after fix** | Scenario 5.4 |

---

## Gap 22: RER below GIQE-5 calibration range

| Field | Value |
|-------|-------|
| **Found in** | Scenario 5.4 (Tom — jitter tolerance) |
| **Status** | OPEN |
| **Description** | At moderate jitter (>2.5 µrad for scenario 5.4's system), RER drops below 0.2 which is outside the GIQE-5 calibration range. RADIANT computes NIIRS but does not flag the result as an extrapolation with reduced confidence. |
| **Workaround** | None — scripts can check RER manually but the chain should warn. |
| **Impact** | Any degraded-image-quality analysis where RER or SNR fall outside calibration range. |
| **Fix location** | `radiant/performance/giqe.py` — add calibration-range checks and warnings. |
| **Effort** | Small — bounds are well-documented in the GIQE-5 specification. |
| **Scenarios blocked** | None. |
| **Rerun after fix** | Scenario 5.4 |

---

## Gap 23: No jitter-source allocation tool

| Field | Value |
|-------|-------|
| **Found in** | Scenario 5.4 (Tom — jitter tolerance) |
| **Status** | OPEN |
| **Description** | Jitter from multiple sources (reaction wheels, solar pressure, cryo coolers, structural modes, ACS residual) adds in quadrature (RSS). RADIANT doesn't have a tool to allocate and track jitter budgets across multiple contributors. An "error budget table" feature would help systems engineers allocate tolerances. |
| **Workaround** | Manual RSS calculation in scripts. |
| **Impact** | Systems engineering jitter budget allocation. |
| **Fix location** | `radiant/api/` or `radiant/platform/` — add budget allocation utility. |
| **Effort** | Medium. |
| **Scenarios blocked** | None. |
| **Rerun after fix** | Scenario 5.4 |

---

## Gap 24: No Zernike-to-PSF integration

| Field | Value |
|-------|-------|
| **Found in** | Scenario 5.1 (Tom — WFE budget allocation) |
| **Status** | CLOSED (Prompt 3C.2) |
| **Description** | `WavefrontError` in `wavefront.py` defines `WfeMode.ZERNIKE` and accepts a `zernike_coeffs` dict, but `OpticsStage` only uses `scalar_rms` mode. It passes `wfe_rms_waves` to `make_pupil_phase()` which generates a random phase screen scaled to the requested RMS. The random screen gives the correct Strehl (same RMS = same Marechal) but NOT the correct PSF shape — coma produces a comet PSF, astigmatism produces a cross, the random screen produces neither. Tom's 12 Zernike coefficients can only be collapsed to a single RMS number today. |
| **Workaround** | Use scalar RMS (RSS of all coefficients). Correct for Strehl and total WFE budget, but cannot distinguish aberration types. |
| **Impact** | Any optical designer wanting to evaluate specific aberration contributions to PSF shape, MTF, and image quality. |
| **Fix location** | `radiant/optics/diffraction.py` — replace random phase screen with Zernike polynomial evaluation on the pupil grid when `WfeMode.ZERNIKE` is selected. |
| **Effort** | Medium — Zernike polynomial evaluation is well-defined math, but needs pupil coordinate handling with obscuration. |
| **Scenarios blocked** | 5.1 (partial — scalar RMS works for total budget). |
| **Rerun after fix** | Scenario 5.1 |
| **Resolution** | New `zernike.py` module evaluates Noll-indexed Zernike polynomials on the pupil grid. `compute_psf()` accepts `WavefrontError` and dispatches to `make_pupil_phase_zernike()` for `WfeMode.ZERNIKE`. `OpticsStage` threads injected `WavefrontError` from `optics_config` through the PSF pipeline. |

---

## Gap 25: No field-dependent WFE

| Field | Value |
|-------|-------|
| **Found in** | Scenario 5.1 (Tom — WFE budget allocation) |
| **Status** | CLOSED (Prompt 3C.3) |
| **Description** | `WfeMode.FIELD_DEPENDENT` exists with `FieldWfeSample` tuples (field_x, field_y, WFE at that point), but `OpticsStage` raises `NotImplementedError` if this mode is selected. Tom has Zernike sets at 4 field positions (on-axis + 3 off-axis) — he cannot evaluate edge-of-field performance where aberrations are typically 2-3x worse than on-axis. |
| **Workaround** | Run separate evaluations with different scalar RMS values representing each field position. Loses field-position coupling to PSF shape. |
| **Impact** | Any field-dependent image quality analysis. Wide-field imagers where edge performance drives the design. |
| **Fix location** | `radiant/optics/stage.py` — implement field-dependent WFE interpolation and per-field PSF computation. |
| **Effort** | Large — needs field-position interpolation, multiple PSF evaluations, field-averaged metrics. |
| **Scenarios blocked** | 5.1 (partial — on-axis only today). |
| **Rerun after fix** | Scenario 5.1 |
| **Resolution** | No interpolation: user selects exact field point via `optics.field_position_x/y` params. `at_field()` returns exact match, `at_field_nearest()` returns nearest with warning. Refractive systems carry `chromatic_zernikes` per field sample; polychromatic PSF uses nearest-wavelength Zernike set for each monochromatic PSF. `OpticsStage` dispatches field_dependent → ZERNIKE at selected field point. |

---

## Gap 26: No Zemax Zernike importer

| Field | Value |
|-------|-------|
| **Found in** | Scenario 5.1 (Tom — WFE budget allocation) |
| **Status** | OPEN |
| **Description** | Tom exports Zernike coefficients from Zemax (.ZMX format) which contains Zernike coefficients, prescription data, and field definitions. No parser exists in `radiant.io`. Tom must manually transcribe coefficients into a spreadsheet. |
| **Workaround** | Manual entry into spreadsheet or YAML. |
| **Impact** | Any optical designer using Zemax, Code V, or similar tools. |
| **Fix location** | `radiant/io/` — add Zemax .ZMX parser for Zernike coefficients. |
| **Effort** | Medium — need to reverse-engineer or document Zemax file format. |
| **Scenarios blocked** | None (manual entry always works). |
| **Rerun after fix** | Scenario 5.1 |

---

## Gap 27: MTF curve frequency axis units

| Field | Value |
|-------|-------|
| **Found in** | Scenario 5.1 (Tom — WFE budget allocation) |
| **Status** | OPEN |
| **Description** | RADIANT's MTF curves use normalized spatial frequency (cycles/pixel). Optical designers think in cycles/mm (focal plane) or cycles/mrad (angular). The conversion is straightforward (divide by pixel pitch) but should be built-in or configurable for plotting and export. |
| **Workaround** | Convert manually in scripts: `freq_cy_mm = freq_cy_px / (pixel_pitch_um * 1e-3)`. |
| **Impact** | Any MTF analysis or export for optical design review. |
| **Fix location** | `radiant/performance/` — add frequency unit options to MTF output, or provide a conversion utility. |
| **Effort** | Small — unit conversion only. |
| **Scenarios blocked** | None (workaround trivial). |
| **Rerun after fix** | Scenario 5.1 |

---

## Gap 28: No WFE allocation / error budget tool

| Field | Value |
|-------|-------|
| **Found in** | Scenario 5.1 (Tom — WFE budget allocation) |
| **Status** | OPEN |
| **Description** | In practice, Tom needs to partition his total WFE budget among contributors: fabrication (mirror figure), alignment, thermal distortion, gravity release, jitter. Each is specified as an RMS, combined via RSS: `WFE_total = sqrt(sum(WFE_i^2))`. RADIANT can sweep total WFE but has no sub-allocation or RSS combination tool. Similar in concept to Gap 23 (jitter-source allocation). |
| **Workaround** | Manual RSS calculation in scripts. |
| **Impact** | Systems engineering WFE budget allocation — standard workflow for optical telescope design. |
| **Fix location** | `radiant/api/` or `radiant/optics/` — add error budget utility with RSS combination and allocation tracking. |
| **Effort** | Medium — need budget data structure, RSS math, and reporting. Could be combined with Gap 23 into a generic "error budget" framework. |
| **Scenarios blocked** | None. |
| **Rerun after fix** | Scenario 5.1 |

---

## Gap 29: No defocus model (focus-shift parameter)

| Field | Value |
|-------|-------|
| **Found in** | Scenario 7.3 (Karen — MTF measurement vs. prediction) |
| **Status** | CLOSED |
| **Description** | RADIANT has no parameter for detector-plane defocus (linear focus shift from best focus). The `optics.wfe_rms_waves` parameter models wavefront error as a random phase screen, which is mathematically different from pure defocus (Zernike Z4). A 5 µm defocus at f/3 produces a geometric blur spot of 0.83 µm radius — negligible for this system but significant at faster f-numbers. Defocus is one of the most common as-built degradation modes and the first thing a test engineer checks. |
| **Resolution** | Added `optics.defocus_um` parameter (default 0.0, bounds [-500, 500] µm). Defocus generates an isotropic Gaussian kernel with σ = \|δ\|/(4·f/#·√3) applied via `epsf.with_kernel("defocus", ...)`. Warns when Z4 > 2 waves (Gaussian approximation breaks down). |
| **Impact** | Any lab MTF comparison where the sensor is not at perfect focus. Any through-focus analysis. |
| **Fix location** | `radiant/optics/defocus.py`, `radiant/optics/_schema.py`, `radiant/optics/stage.py` |
| **Effort** | Small — straightforward Gaussian blur kernel, one new parameter. |
| **Scenarios blocked** | None (workaround available). |
| **Rerun after fix** | Scenario 7.3 |

---

## Gap 30: No measurement data import / overlay API

| Field | Value |
|-------|-------|
| **Found in** | Scenario 7.3 (Karen — MTF measurement vs. prediction) |
| **Status** | OPEN |
| **Description** | RADIANT has no mechanism to import measured data (MTF curves, NEDT values, noise spectra) and compare against predictions. Test engineers always work in measurement-vs-model mode. Currently, all data import and comparison must be done manually in scripts outside RADIANT. |
| **Workaround** | Read measurement files (CSV, Excel) in scripts, interpolate onto RADIANT's frequency grid, compute residuals manually. |
| **Impact** | Every I&T scenario (7.x series), any model validation workflow. |
| **Fix location** | `radiant/io/` — add measurement import readers. `radiant/api/` — add `Sensor.compare_mtf(measured_data)` or similar comparison utilities. |
| **Effort** | Medium — need readers for common formats (CSV, Excel), unit conversion, interpolation, and residual computation. |
| **Scenarios blocked** | None (workaround always available). |
| **Rerun after fix** | Scenario 7.3 |

---

## Gap 31: No scatter / surface roughness (TIS) model

| Field | Value |
|-------|-------|
| **Found in** | Scenario 7.3 (Karen — MTF measurement vs. prediction) |
| **Status** | OPEN |
| **Description** | Real optical surfaces scatter light due to surface roughness (total integrated scatter, TIS). This transfers energy from the PSF core to a wide-angle halo, reducing MTF at all frequencies. RADIANT models diffraction and WFE but not surface scatter. The Harvey-Shack BRDF model or TIS = (4πσ/λ)² approximation would capture this. |
| **Workaround** | None — scatter is an unmodeled MTF loss source. |
| **Impact** | Lab MTF comparisons where scatter explains residual MTF loss after accounting for all other components. High-quality optics where scatter is comparable to WFE. |
| **Fix location** | `radiant/optics/` — add scatter model (TIS fraction, Harvey-Shack parameters, or scatter kernel). |
| **Effort** | Medium — TIS is straightforward; full Harvey-Shack is large. |
| **Scenarios blocked** | None. |
| **Rerun after fix** | Scenario 7.3 |

---

## Gap 32: No electronics MTF model (amplifier bandwidth)

| Field | Value |
|-------|-------|
| **Found in** | Scenario 7.3 (Karen — MTF measurement vs. prediction) |
| **Status** | OPEN |
| **Description** | Detector readout electronics have finite bandwidth, producing a low-pass filter that degrades cross-scan MTF. This "electronics MTF" is typically Gaussian: `MTF_elec = exp(-2π²σ_e²f²)` with σ_e determined by the amplifier bandwidth and pixel clock rate. RADIANT does not model this. For CCD and CMOS sensors, electronics MTF can be comparable to pixel aperture MTF at high readout speeds. |
| **Workaround** | Include as a charge diffusion term if the functional form is similar. |
| **Impact** | Lab MTF comparisons at high pixel clock rates. |
| **Fix location** | `radiant/readout/` — add electronics MTF parameter and computation. |
| **Effort** | Small — single Gaussian parameter. |
| **Scenarios blocked** | None. |
| **Rerun after fix** | Scenario 7.3 |

---

## Gap 33: GSD not adjusted for off-nadir angle

| Field | Value |
|-------|-------|
| **Found in** | Scenario 3.4 (Raj — off-nadir agility) |
| **Status** | CLOSED (Phase 3, Prompt 3A.1) |
| **Description** | `compute_gsd()` in `radiant/performance/gsd.py` uses nadir formula `GSD = pixel_pitch × altitude / focal_length` and does not account for `geometry.path_zenith_rad`. At 45 deg off-nadir from 600 km, the true slant range is 815 km, giving cross-track GSD of 1.86 m vs. the reported 1.37 m — a 26% error. GSD should use slant range: `GSD = pixel_pitch × slant_range / focal_length`. |
| **Workaround** | Compute slant range and off-nadir GSD manually in scripts. |
| **Impact** | Any off-nadir or agile pointing analysis reports incorrect GSD. NIIRS derived from incorrect GSD is also wrong (Gap 34). |
| **Fix location** | `radiant/performance/gsd.py` — read `geometry.path_zenith_rad` and compute slant range. |
| **Effort** | Small — slant range formula already exists in atmosphere module. |
| **Resolution** | Added `path_zenith_rad` parameter to `compute_gsd()`. Uses spherical-Earth ray-sphere intersection (`core.geometry.slant_range_spherical_m`) for correct slant range. Default zenith=0 preserves nadir behavior. Note: the original gap description's reference values (815 km slant, 1.86 m GSD) used the atmospheric slant-path formula, not geometric ray-sphere intersection. Correct values at 45°/600 km: slant = 892 km, cross-track GSD = 2.68 m. |
| **Scenarios blocked** | None (workaround available). |
| **Rerun after fix** | Scenario 3.4 |

---

## Gap 34: NIIRS not recomputed with off-nadir GSD

| Field | Value |
|-------|-------|
| **Found in** | Scenario 3.4 (Raj — off-nadir agility) |
| **Status** | CLOSED (Phase 3, Prompt 3A.1) |
| **Description** | Because GSD is computed at nadir (Gap 33), NIIRS from GIQE-5 does not reflect the true off-nadir GSD. At 45 deg, NIIRS is approximately 0.67 points too optimistic. Fixing Gap 33 would automatically fix this, since NIIRS reads GSD from `result.metrics`. |
| **Workaround** | Correct NIIRS using GSD scaling: `dNIIRS = -3.32 × log10(GSD_true / GSD_nadir)`. |
| **Impact** | Any off-nadir NIIRS analysis. |
| **Fix location** | Resolved automatically when Gap 33 is fixed. |
| **Effort** | None beyond Gap 33. |
| **Resolution** | Resolved automatically by Gap 33 fix. NIIRS reads GSD from `state.metrics`, which now reflects off-nadir corrected values when `geometry.path_zenith_rad` is set. |
| **Scenarios blocked** | None. |
| **Rerun after fix** | Scenario 3.4 |

---

## Gap 35: No along-track vs cross-track GSD distinction at off-nadir

| Field | Value |
|-------|-------|
| **Found in** | Scenario 3.4 (Raj — off-nadir agility) |
| **Status** | CLOSED (Phase 3, Prompt 3A.1) |
| **Description** | At off-nadir angles, the ground sample is no longer square. Cross-track GSD scales as `slant_range / f` but along-track GSD scales as `slant_range / (f × cos(incidence_angle))` due to ground projection foreshortening. At 45 deg off-nadir, along-track GSD is 2.94 m vs. cross-track 1.86 m — a 58% asymmetry. RADIANT's GSD metric always reports equal cross-track and along-track values (from pixel pitch ratio only, no angle). |
| **Workaround** | Compute the projection-corrected along-track GSD externally. |
| **Impact** | Any off-nadir analysis, NIIRS prediction (GIQE-5 uses geometric mean of cross/along GSD). |
| **Fix location** | `radiant/performance/gsd.py` — add incidence angle correction for along-track GSD. |
| **Effort** | Medium — needs incidence angle computation from zenith angle and Earth geometry. |
| **Resolution** | Along-track GSD now uses `slant_range / (f × cos(incidence))` where incidence is computed via `core.geometry.incidence_angle_rad()` (sine-rule spherical Earth). Cross-track and along-track are reported separately; `geometric_mean_m` property added for GIQE-5. Note: original gap reference values (2.94 m along, 1.86 m cross) used wrong slant range formula. Correct values at 45°/600 km: along = 4.23 m, cross = 2.68 m. |
| **Scenarios blocked** | None. |
| **Rerun after fix** | Scenario 3.4 |

---

## Gap 36: No swath width or access geometry calculator

| Field | Value |
|-------|-------|
| **Found in** | Scenario 3.4 (Raj — off-nadir agility) |
| **Status** | CLOSED |
| **Resolution** | Prompt 3A.2. Added `performance/ground_range.py`, `performance/swath_width.py`, `performance/access_rate.py`. Wired into PerformanceStage via `_compute_access_metrics()`. New params: `detector.n_pixels_cross`, `geometry.ground_speed_m_s`. Ground range uses law of cosines on ray-sphere triangle. All metrics skip gracefully when inputs not provided. |
| **Description** | RADIANT has no built-in computation for swath width, ground range, or access area rate. Mission planners need these to evaluate the trade between image quality and collection capability. The math is straightforward geometry (swath = n_pixels × GSD_cross, ground_range from Earth geometry). |
| **Workaround** | N/A — fixed. |
| **Impact** | Mission planning and agile pointing trade studies. |
| **Fix location** | `radiant/performance/ground_range.py`, `radiant/performance/swath_width.py`, `radiant/performance/access_rate.py`, `radiant/performance/stage.py` |
| **Effort** | Medium — need Earth geometry, swath, ground range, access rate calculations. |
| **Scenarios blocked** | None. |
| **Rerun after fix** | Scenario 3.4 |

---

## Summary Table

| # | Gap | Effort | Scenarios impacted | Status |
|---|-----|--------|--------------------|--------|
| 1 | IPC not wired | Small | 1 | FIXED |
| 2 | SNR = 0 at orbital altitude | — | 7+ | FIXED |
| 3 | NEDT missing | Small | 10+ | FIXED |
| 4 | NIIRS missing | Small | 11 | FIXED |
| 5 | GSD missing | Trivial | 5+ | FIXED |
| 6 | Unit-aware input | Medium | All | OPEN |
| 7 | Parameter name discovery | Small | All | FIXED |
| 8 | Strehl ratio missing | Trivial | 2 | FIXED |
| 9 | Full MTF curve missing | Small | 4+ | FIXED |
| 10 | No inverse solver | Medium | Many | OPEN |
| 11 | No per-element nearfield breakdown | Medium | Few | OPEN |
| 12 | cold_stop_efficiency naming | Small | Few | OPEN |
| 13 | Q parameter missing | Trivial | Few | FIXED |
| 14 | No aliased/folded MTF | Medium | Few | OPEN |
| 15 | MTF = 0 at high Q (investigate) | Small | Few | CLOSED |
| 16 | Per-wavelength PSFs not exposed | Small | Few | OPEN |
| 17 | No arbitrary PSF weighting spectrum | Small | Few | OPEN |
| 18 | Platform jitter not wired | — | 5.4 | FIXED |
| 19 | No MTF budget decomposition | Medium | 5.4, 7.3 | OPEN |
| 20 | No GIQE-5 sensitivity analysis | Small | 5.4 | OPEN |
| 21 | No jitter PSD / frequency dependence | Large | 5.4 | OPEN |
| 22 | RER below GIQE-5 calibration range | Small | 5.4 | OPEN |
| 23 | No jitter-source allocation tool | Medium | 5.4 | OPEN |
| 24 | No Zernike-to-PSF integration | Medium | 5.1 | OPEN |
| 25 | No field-dependent WFE | Large | 5.1 | OPEN |
| 26 | No Zemax Zernike importer | Medium | 5.1 | OPEN |
| 27 | MTF curve frequency axis units | Small | 5.1 | OPEN |
| 28 | No WFE allocation / error budget tool | Medium | 5.1 | OPEN |
| 29 | No defocus model (focus-shift) | Small | 7.3 | OPEN |
| 30 | No measurement data import/overlay API | Medium | 7.x | OPEN |
| 31 | No scatter / surface roughness (TIS) | Medium | 7.3 | OPEN |
| 32 | No electronics MTF model | Small | 7.3 | OPEN |
| 33 | GSD not adjusted for off-nadir angle | Small | 3.4 | OPEN |
| 34 | NIIRS not recomputed with off-nadir GSD | Small | 3.4 | OPEN |
| 35 | No along/cross-track GSD at off-nadir | Medium | 3.4 | OPEN |
| 36 | No swath width / access geometry | Medium | 3.4 | CLOSED |
