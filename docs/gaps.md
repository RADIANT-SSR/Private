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
| **Status** | OPEN |
| **Description** | RADIANT outputs total `nearfield_e` but does not break it down by optical element (primary mirror, secondary, fold mirror, field lens, filter). Test engineers need to know which element contributes most to nearfield emission to diagnose cold stop leakage directionality. |
| **Workaround** | None — requires changes to the optics stage internals. |
| **Impact** | Cold stop and stray light diagnostics. |
| **Fix location** | `radiant/optics/` — return per-element contributions in `stage_outputs`. |
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
| **Status** | OPEN |
| **Description** | RADIANT computes the pre-sampling (optical) MTF but does not model aliasing — spatial frequency folding at Nyquist. For undersampled systems (Q < 1), high-frequency scene content folds back below Nyquist, producing spurious apparent contrast. The reported MTF at Nyquist can be misleadingly high for aliased systems. |
| **Workaround** | None — aliasing analysis requires a folded-MTF computation not currently available. |
| **Impact** | Any undersampled system (Q < 1) analysis gives incomplete spatial performance picture. |
| **Fix location** | `radiant/performance/` or `radiant/optics/` — add folded MTF computation that sums optical MTF at multiples of Nyquist. |
| **Effort** | Medium — requires folded-MTF math and decision on where in the chain to apply. |
| **Scenarios blocked** | None (pre-sampling MTF is still useful). |
| **Rerun after fix** | Scenario 5.2 |

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
| **Status** | OPEN |
| **Description** | `compute_polychromatic_psf()` computes monochromatic PSFs at each wavelength internally but discards them after accumulation into the weighted average. Per-wavelength PSF arrays are never stored in `stage_outputs`. Chromatic PSF visualization requires N separate narrow-band evaluations. |
| **Workaround** | Run RADIANT N times with narrow bands (±50 nm) centered at each wavelength. |
| **Impact** | Chromatic PSF analysis, per-wavelength MTF overlays, FWHM(λ) plots. |
| **Fix location** | `radiant/optics/diffraction.py` — store per-λ PSFs during polychromatic computation, expose in `stage_outputs["optics"]`. |
| **Effort** | Small — loop already exists, just need to store intermediate arrays. |
| **Scenarios blocked** | None (workaround available but expensive). |
| **Rerun after fix** | Scenario 5.3 |

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
