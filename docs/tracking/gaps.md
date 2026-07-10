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
| DEFERRED | Explicitly deferred with a gating condition + re-audit date (Rule 22/27 protocol) — not silently open |
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
| **Status** | FIXED (2026-07-07, Gap_Closure_Plan WP-3.1) |
| **Fix** | `ParameterSet.set(name, value, unit=...)` + `Sensor.set(dotpath, value, unit=...)` convert caller-native units at the set boundary (Rule 2): unit → canonical → input_unit via `core/units.py`. `"%"`→fraction and `min`→s registered. Bounds checked post-conversion; original value+unit recorded in provenance source; actionable error for unregistered units. 10 new tests with 3 anchors (30 cm→0.30 m, 5 ms→0.005 s, 70 %→0.70). Docs: RADIANT_Parameter_System.md §Unit Conversion. |
| **Rerun after fix** | Verified: Dr. Chen's native-unit inputs (cm, %, ms) set directly without manual conversion; 150 % correctly rejected by post-conversion bounds. GUI can now expose unit dropdowns per parameter. |
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
| **Status** | FIXED (2026-07-07, Gap_Closure_Plan WP-3.3) |
| **Fix** | `Sensor.solve_for(param, target, bounds=, metric=, rtol=)` backed by new `api/solve.py` (Rule 19): Brent root-finding on the forward chain; `SolveResult` carries solution, achieved metric, evaluation count, and the full `ChainResult` at the root. Actionable `SolveBracketError` reports both endpoint metric values when the target isn't bracketed. 4 integration tests incl. round-trip anchor (forward SNR at D=0.20 m recovered to rel 1e-4). Docs: RADIANT_Scripting_API.md §2.2 + stability row. |
| **Rerun after fix** | Verified: round-trip solve recovers a known aperture to 1e-4; unreachable targets produce the bracketing error (including the saturation-plateau case where SNR clips at FWC). |
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
| **Status** | FIXED (2026-07-07, Gap_Closure_Plan WP-2.4) |
| **Fix** | Renamed to `optics.nearfield_fraction` (the name now states the quantity: fraction of the FPA hemisphere filled by warm elements). New generic deprecation-alias mechanism in `core/parameters.py` (`ParameterDef.deprecated_aliases`; `set`/`get`/`set_tolerance`/`clear_input` resolve aliases with `DeprecationWarning`) keeps `optics.cold_stop_efficiency` working. Schema description + RADIANT_Optics.md §7.4 now state the vendor-convention relationship (`nearfield_fraction = 1 − vendor_efficiency`) — the required GUI tooltip text lives there. 7 new alias tests. Physics-function kwarg `compute_nearfield_irradiance(cold_stop_efficiency=...)` unchanged (internal). |
| **Rerun after fix** | Verified: old name sets/reads via alias with DeprecationWarning; nearfield integration suite green under the new name. |
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
| **Status** | FIXED (2026-07-07, Gap_Closure_Plan WP-2.3) |
| **Fix** | Injection route (Rule 6, non-scalar input): `RadiantSession.run(params, extra_stage_outputs={"optics_config": {"psf_weighting_spectrum": SpectralData}})`. OpticsStage uses the override for photon-flux weights (validated for band overlap), records provenance in `stage_outputs["optics"]["psf_weighting_source"]`. Radiometric chain untouched (signal_e bit-identical). 5 integration tests. Docs: RADIANT_Scripting_API.md. |
| **Rerun after fix** | Verified: blue- vs red-weighted overrides on a 3.5–5 µm chain shift the ePSF effective wavelength and FWHM in the expected directions with SNR/signal unchanged (scenario 5.3's isolated PSF-weighting comparison is now possible). |
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
| **Status** | FIXED (2026-07-07, Gap_Closure_Plan WP-3.7) |
| **Fix** | Phase-0 re-audit found the decomposition already existed (dual-path architecture: `MTFBudgetResult` in `performance/mtf_budget.py` with `per_term_at_nyquist`, dominant contributor per axis, system product, stored at `stage_outputs["performance"]["mtf_budget"]`) — the gap predated that work. Added the missing reporting layer: `MTFBudgetResult.table()` (per-contributor MTF-at-Nyquist table, worst-first, system + dominant rows) and `plot_mtf_budget` / `ResultPlotNamespace.mtf_budget()` grouped bar chart. 3 integration tests. Also corrected the `ResultPlotNamespace` docstring (it claimed a `result.plot` attribute that was never wired — the namespace is constructed explicitly; io may not import api). |
| **Rerun after fix** | Verified: MWIR chain with 2 µrad jitter — table lists optics/pixel/jitter/diffusion/IPC/TDI/electronics contributors with system product and dominant contributor; plot renders under Agg. |
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
| **Status** | FIXED (2026-07-07, Gap_Closure_Plan WP-2.1) |
| **Fix** | New `performance/giqe_sensitivity.py` (Rule 19 own-module): `giqe5_sensitivity()` → `GIQESensitivity` with analytic partials for all five GIQE-5 inputs plus exact per-+1% NIIRS deltas. 9 tests, 3 truth anchors (hand calc, registry formula, central finite difference of `compute_giqe5`). Docs: RADIANT_Metrics.md §4.6. |
| **Rerun after fix** | Verified: d(NIIRS)/d(RER) at RER=0.5 → 2.8837 (= 3.32/(0.5·ln10), the registry's own example formula); finite-difference agreement to rel 1e-5. |
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
| **Status** | DEFERRED (2026-07-07, Gap_Closure_Plan Phase 4) |
| **Deferral record** | Gating condition: a scenario or user request requiring colored-jitter blur/pointing partition (RMS assumption is standard for preliminary design; no scenario blocked). Re-audit: 2026-10-01. |
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
| **Status** | FIXED (2026-07-07, Gap_Closure_Plan WP-1.2) |
| **Fix** | Full published GIQE-5 fit ranges (Harrington 2015: GSD 3–80 cm, RER 0.2–0.95, SNR 2–130, both ends) checked in `performance/giqe.py`; `GIQEResult.extrapolated` flag + per-input warning strings; chain emits `UserWarning` and a `niirs_extrapolated` metric (0/1). IIRS dispatch inherits the checks. Replaces the old ad-hoc low-end-only checks (SNR<5, RER<0.2). 10 new tests. Docs: `RADIANT_Metrics.md` §4.6. |
| **Rerun after fix** | Verified 2026-07-07 (5.4 rerun-equivalent): MWIR LEO chain, jitter 0→20 µrad drives RER 0.601→0.254, NIIRS 4.19→2.95; `niirs_extrapolated=1.0` and UserWarning fire (baseline is itself out of calibration — GSD 295 inch, SNR 316 — correctly flagged). |
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
| **Status** | FIXED (2026-07-07, Gap_Closure_Plan WP-3.2 — merged with Gap 28) |
| **Fix** | Generic `ErrorBudget`/`BudgetContributor` in `radiant/api/error_budget.py` (one RSS model per the registry's own suggestion to merge with Gap 28): rss_total, allocation margin, over-budget flag, RSS headroom `sqrt(alloc²−total²)`, immutable extension, formatted budget table with variance shares, dict round-trip. Exported from `radiant.api`. 16 tests, 3 anchors (3-4-5 RSS, WFE hand calc, exact-consumption headroom). Docs: RADIANT_Scripting_API.md. |
| **Rerun after fix** | Verified: jitter-style budget (µrad) and WFE-style budget (waves) both exercise the same model; table output includes per-contributor variance share for allocation review. |
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
| **Status** | FIXED (2026-07-07, Gap_Closure_Plan WP-3.6) |
| **Fix** | New `io/zemax_zernike.py` (Rule 19): `load_zemax_zernike(path)` parses the Zemax "Zernike Standard Coefficients" text analysis export (scoped to the `.txt` report Tom actually exports, not the full `.ZMX` prescription) — Noll-indexed waves, `Z 1`/`Z1` styles, trailing polynomial formulas ignored, UTF-8/UTF-16 (Zemax-on-Windows BOM) tolerant. `ZemaxZernikeResult.to_wavefront_error()` feeds the Gap 24/25 Zernike pipeline directly. Single-field per file; duplicated Noll indices (concatenated multi-field export) rejected with an actionable `ZemaxParseError`. 27 tests with hand-valued fixtures (incl. UTF-16-LE BOM fixture + its generator per Rule 26). Docs: RADIANT_Scripting_API.md §10 + stability rows. |
| **Rerun after fix** | Verified: fixture exports parse to exact hand values; `to_wavefront_error()` round-trips mode/coeffs/reference wavelength. Tom's transcribe-to-spreadsheet step is eliminated. |
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
| **Status** | FIXED (2026-07-07, Gap_Closure_Plan WP-2.5) |
| **Fix** | (1) Phase-0 re-audit found the premise stale: PSF-path curves (`mtf_freq_x/y`) were already stored in cycles/m, not cycles/pixel. (2) New `performance/frequency_units.py` (Rule 19): `convert_spatial_frequency(freq, from_unit, to_unit, pixel_pitch_m=, focal_length_m=)` across cy/m ↔ cy/mm ↔ cy/mrad ↔ cy/pixel; 10 tests, 3 anchors (Nyquist=0.5 cy/pixel, IFOV-derived cy/mrad, SI prefix). (3) **Latent bug found and fixed in passing (Rule 21, inline-fix)**: the product-path grid `ChainState.spatial_freq_cycles_per_mrad` was computed with `× f·1e3` instead of `× f·1e-3` — stored values were 1e6× true cycles/mrad. Every consumer round-tripped with the same inverse factor, so all physics/metrics were unaffected; only the grid's unit claim (and the cycles/mrad axis on `plot_mtf_terms`) was wrong. Fixed symmetrically at all 7 src sites + mirrored test helpers. |
| **Rerun after fix** | Verified: 18 µm/f=1.2 m Nyquist now reads 33.33 cy/mrad on the product grid (was 3.33e7); all 78 MTF-path tests and dual-path consistency green. |
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
| **Status** | FIXED (2026-07-07, Gap_Closure_Plan WP-3.2 — merged with Gap 23) |
| **Fix** | Same `ErrorBudget` utility as Gap 23 (see that entry): the registry's suggested generic "error budget" framework. WFE usage: `ErrorBudget("wfe", "waves", contributors=(fabrication, alignment, thermal, gravity_release, ...), allocation=total_budget)`. |
| **Rerun after fix** | Verified: RSS(0.05, 0.03, 0.02) waves = 0.06164 waves anchor; headroom query answers "how much is left for a new contributor". |
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
| **Status** | FIXED (2026-07-07, Gap_Closure_Plan WP-3.4) |
| **Fix** | (1) `io/measurement.py`: `load_measured_curve(path, x_column=, y_column=, delimiter=, skip_header="auto", x_unit=)` → validated `MeasuredCurve` (comment/blank handling, auto header, strictly-ascending x, actionable `MeasurementParseError`). CSV via stdlib only — **Excel import is out of scope** (openpyxl not a dependency; export to CSV; see CU-057). (2) `api/compare.py`: `compare_mtf(result, measured, axis=, frequency_unit=, ...)` interpolates the predicted MTF onto the measured points (unit-aware via `convert_spatial_frequency`, overlap-only, never extrapolated) → `MtfComparisonResult` with residual = measured − predicted, rms/max stats, exclusion counts, `table()`. Exported from `radiant.api`. 33 tests incl. full-chain round-trip (measured = predicted + 0.02 → rms_residual = 0.02 to rel 1e-9, cy/mm unit path). Docs: RADIANT_Scripting_API.md §10 + stability rows. |
| **Rerun after fix** | Verified: real MWIR chain comparison with synthetic measured curve — residual sign convention, unit conversion, and exclusion counting all anchor-checked. Karen's 7.x measurement-vs-model workflow no longer needs manual interpolation. |
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
| **Status** | FIXED (2026-07-07, Gap_Closure_Plan WP-3.5 — TIS model; Harvey-Shack explicitly out of scope for v1) |
| **Fix** | New `optics/scatter.py` (Rule 19): TIS = 1 − exp(−(4πσ_s/λ)²) (Bennett & Porteus; validity warning above TIS 0.3), mixed kernel `(1−TIS)·δ + TIS·Gaussian(σ_halo)` and exact-Fourier-pair MTF `(1−TIS) + TIS·exp(−2π²σ_halo²f²)` — Rule 4 both paths, included in the consistency check (passes at TIS≈0.117). New params `optics.surface_roughness_nm` (default 0) + `optics.scatter_halo_sigma_um` (default 100 µm). 18 tests, 3 anchors (hand calc TIS=0.021620 at 50 nm/4.25 µm, small-σ limit, kernel-FFT ↔ analytic). Docs: Optics §7.4b, Spatial_Complete term 12, Parameter_System. |
| **Rerun after fix** | Verified: 120 nm roughness MWIR chain — TIS 0.117 stored, both-axis MTF drops, dual-path consistency green, signal path bit-identical (energy-conserving redistribution). Full 7.3 script rerun blocked on CU-057 (openpyxl). |
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
| **Status** | FIXED (2026-07-07, Gap_Closure_Plan WP-2.2) |
| **Fix** | New `readout/electronics_mtf.py` (Rule 19) + `readout.electronics_sigma_um` param (default 0 = ideal). Rule 4 both-paths: ReadoutStage pushes analytic `mtf_electronics_x` (`exp(-2π²σ²f²)`, y=1) and builds the matching Gaussian-in-x kernel; PerformanceStage convolves it into the ePSF like IPC (kernel travels via ChainState, Rule 11). Included in the dual-path consistency check (passes: max err 0.006/0.016 vs 0.05 tol at σ=9 µm). 15 new tests, 3 anchors (hand calc exp(-0.3084)=0.7346, kernel-FFT vs analytic, half-power frequency). Docs: RADIANT_Spatial_Complete.md §9.2 (term 11), RADIANT_Parameter_System.md. |
| **Rerun after fix** | Verified: σ=9 µm MWIR chain — mtf_at_nyquist drops, y-axis MTF bit-identical, dual-path consistency green. Full scenario 7.3 script rerun blocked on CU-057 (openpyxl). |
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

## Gap 37: Nearfield emission = 0 in scalar transmission mode

| Field | Value |
|-------|-------|
| **Found in** | Scenarios 7.1, 7.4, 2.2, 2.5, 3.2 (cross-scenario — MWIR/LWIR warm-optics systems) |
| **Status** | FIXED (2026-07-07, Gap_Closure_Plan WP-1.1) |
| **Severity** | **HIGH** |
| **Fix** | Added `optics.scalar_emissivity` (default 0.0 preserves ε=0 behavior). `OpticalElement.declared_emissivity` accepted on `kind=LUMPED` pseudo-elements only — the one sanctioned Rule 5 exception, since a lump is not a physical surface; construction enforces ε + τ + R ≤ 1 (`KirchhoffViolationError`). Wired scalar mode → `make_lumped_element(emissivity=...)` → nearfield. Warns if set in non-scalar modes. 14 new tests (element validation, factory, mode dispatch, Level 0 hand-calc E_nf = ε·B·Ω, full-chain integration: nearfield_shot 0 → 662.6 e⁻ RMS at ε=0.25/293 K MWIR, SNR decreases, signal path unchanged to 1e-12). Docs: RADIANT_Optics.md §2/§5.1/§5.2/§6.1/§10.3 (also fixed pre-existing doc drift claiming scalar mode synthesized ε = 1−τ — it never did), RADIANT_Parameter_System.md. |
| **Resolution note** | Fix targets scalar mode per the gap. Mode 2 (spectral_file) retains ε=0 with the workaround documented (use key_elements / full_prescription). |
| **Description** | In scalar transmission mode (`optics.mode: "scalar"`), the lumped optical element is treated as refractive and Kirchhoff's law gives `ε = 1 − T − R = 0` (since `T + R = 1` for refractive). Mirrors follow `ε = 1 − R` and should contribute self-emission, but scalar mode cannot distinguish refractive from reflective. Result: `nearfield_shot = 0` even with warm optics at 293 K in MWIR/LWIR bands. |
| **Impact** | (a) Under-predicts total noise for cold targets / point sources in warm-optics MWIR/LWIR (30–40% noise underestimate typical). (b) Cold stop efficiency sweeps (7.4) non-functional — no nearfield to reduce. (c) Explains a portion of predicted vs. measured NEDT gap in Karen's TVAC test (26 mK at 25°C). (d) NIIRS predictions slightly optimistic for thermal bands with warm optics (0.02–0.04 optimism). |
| **Evidence** | 7.1: nearfield_shot = 0 with 4 optics elements at 22°C. 2.5: nearfield_shot = 0 for 200 K cold target with 4 warm optics at 20°C. 3.2: nearfield_shot = 0 at 500 km LEO MWIR baseline. |
| **Workaround** | Use `optics.mode: "key_elements"` with per-surface emissivity derived from `ε = 1 − R` for mirrors. `full_prescription` mode for Zemax-exported designs. |
| **Fix location** | `radiant/optics/_schema.py` — add optional `optics.scalar_emissivity` parameter. Default None preserves current behavior; if set, overrides the refractive-lump assumption. Alternative: auto-detect lumped-mirror via `optics.n_mirror_surfaces` parameter. |
| **Effort** | Small (scalar_emissivity param) to Medium (auto-detection from surface counts). |
| **Scenarios affected** | 7.1, 7.4, 2.2, 2.5, 3.2 (all warm-optics thermal-band scenarios). |
| **Rerun after fix** | Verified 2026-07-07 (7.4 rerun-equivalent — the scripted sweep itself is blocked on CU-057 `openpyxl`): scalar mode, ε=0.25, T_optics=293 K, MWIR 3.5–5.0 µm; η_cold sweep 0→1 gives nearfield 0 → 439.0 ke⁻ (linear in η_cold) and SNR 316.1 → 136.2. Cold-stop sweeps are functional in scalar mode. |

---

---

## Gap 38: E_sky single-scatter ω₀ lacks aerosol / spectral fidelity

| Field | Value |
|-------|-------|
| **Found in** | Use-case matrix audit, Open Q §8.6 (folded from Use_Case_gaps.md, 2026-07-06) |
| **Status** | DEFERRED (2026-07-07, Gap_Closure_Plan Phase 4) |
| **Deferral record** | Gating condition: MODTRAN lookup-table wiring lands (same blocker family as Gap 39 — no MODTRAN access since 2026-04-21, reconfirmed by owner 2026-07-07). Re-audit: 2026-10-01 or on MODTRAN access, whichever comes first. |
| **Description** | The single-scatter sky irradiance formula `E_sky_scattered = E_TOA·cos(θ_s)·ω₀·(1−τ_down,vert)` is in place, but the single-scatter albedo ω₀ is a fixed scalar — it does not vary by aerosol regime or wavelength with MODTRAN-parity fidelity. Affects MWIR mixed emit+reflect scenes (use-case Cells 25, 40, 55) where thermal downwelling competes with scattered solar. No effect on LWIR (Cells 28, 58) or VIS/NIR-dominated cells. |
| **Workaround** | Accept ~10–30% error on MWIR-band radiance in mixed emit+reflect scenes; expressibility is unaffected. |
| **Impact** | MWIR mixed-scene radiance accuracy (~10–30%). Not a release blocker. |
| **Fix location** | `radiant/atmosphere/` — dedicated aerosol-parity task once MODTRAN-driven lookup tables are wired. |
| **Effort** | Medium — deferred behind MODTRAN lookup-table wiring. |
| **Scenarios blocked** | None. |
| **Rerun after fix** | Use-case matrix Cells 25, 40, 55 (`tests/integration/test_use_case_matrix.py`). |

---

## Gap 39: A3 partial-column MODTRAN parity — blocked on MODTRAN access

| Field | Value |
|-------|-------|
| **Found in** | Use-case matrix audit, Table C (folded from Use_Case_gaps.md, 2026-07-06) |
| **Status** | DEFERRED (2026-07-07, Gap_Closure_Plan Phase 4) |
| **Deferral record** | Gating condition: licensed MODTRAN install or donated tape7 fixtures (no access since 2026-04-21, reconfirmed by owner 2026-07-07). Re-audit: 2026-10-01 or on MODTRAN access, whichever comes first. ~2 days of work once unblocked. |
| **Description** | A3 partial-column transmission is wired end-to-end in `SimpleAtmosphere` and the Table C smoke tests pass monotonicity in h_tgt (`tests/integration/test_table_c_cells.py`), but MODTRAN-equivalent validation of τ(h_tgt, θ_o) requires a licensed MODTRAN install to generate reference tape7 fixtures. **BLOCKED: no MODTRAN access** (since 2026-04-21). The backend extension itself is ~2 days (two-run differential: full column + h_tgt→sensor legs, extending `ModtranAtmosphere.evaluate`). |
| **Workaround** | Rely on smoke-tested, monotone `SimpleAtmosphere` values; not pinned against an external reference. Alternative reference (`lowtran` port or Beer-Lambert thin-atmosphere hand check) adds a dependency — not recommended for closure. |
| **Impact** | Table C (use-case Cells 31–45) accuracy is unpinned against an external reference. |
| **Fix location** | `src/radiant/atmosphere/modtran.py` — extend `ModtranAtmosphere.evaluate` with the two-run differential once MODTRAN access (licensed install or donated tape7 fixtures) is available. |
| **Effort** | Small (~2 days) once unblocked. |
| **Scenarios blocked** | None. |
| **Rerun after fix** | Table C cells (`tests/integration/test_table_c_cells.py`, `test_use_case_matrix.py`). |

---

## Gap 40: Lab dark-cal mode is not a first-class parameter

| Field | Value |
|-------|-------|
| **Found in** | Use-case matrix audit, D-lab cells (folded from Use_Case_gaps.md, 2026-07-06) |
| **Status** | DEFERRED (2026-07-07, Gap_Closure_Plan Phase 4) |
| **Deferral record** | Gating condition: a user or GUI request for an explicit dark-cal flag (the registry entry itself says "when a user actually asks for it"; ergonomics only, not correctness). Re-audit: next GUI scenario touching D-lab cells. |
| **Description** | The use-case matrix's `no_atmosphere (lab_test)` dark-cal sub-mode (illumination=None) is expressible by simply not configuring a source illumination, but there is no positive assertion in the descriptor that this is dark-cal. The scenario YAML has no field explicitly flagging dark-cal vs lit-lab (~5 D-lab cells where illumination=None is intended). |
| **Workaround** | Omit source illumination; cells pass. Readability/ergonomics gap only, not correctness. |
| **Impact** | Scenario-YAML readability for D-lab dark-cal configurations; GUI clarity. |
| **Fix location** | Descriptor / schema — add an optional `lab_test_mode: "dark" \| "lit"` enum when a user actually asks for it. |
| **Effort** | Small. |
| **Scenarios blocked** | None. |
| **Rerun after fix** | D-lab cells in `tests/integration/test_use_case_matrix.py`. |

---

## Gap 41: Earth-LOS-intercept validator has no negative integration test

| Field | Value |
|-------|-------|
| **Found in** | Use-case matrix audit, D-space invalid configurations (folded from Use_Case_gaps.md, 2026-07-06) |
| **Status** | FIXED (2026-07-07, Gap_Closure_Plan WP-1.3) |
| **Fix** | `TestEarthLosInterceptNegativePath` in `tests/integration/test_use_case_matrix.py`: sensor (1 km) below space target (90 km) at nadir through the full RadiantSession → `assembly.validate_no_atmosphere_subcase` raises `ParameterBoundsError` ("intersects the Earth") end-to-end; control case (800 km sensor) runs clean. Note: with `theta_o` bounded [0, π/2), the intercept fires via the degenerate sensor-below-target branches of `intercepts_earth`, which is precisely the flipped-altitude case the gap prescribed. Test-only change. |
| **Description** | `LineOfSightGeometry.intercepts_earth(h_sensor)` is implemented (`src/radiant/core/los_geometry.py`) and unit-tested, but no integration test configures a "space" target with sensor below the target to confirm the validator raises end-to-end. The validator works in isolation; the negative integration path is not proven. |
| **Workaround** | None needed — unit coverage exists; only end-to-end negative-path proof is missing. |
| **Impact** | Silent-regression risk: a refactor could disconnect the validator from the chain without any integration test failing. |
| **Fix location** | `tests/integration/test_use_case_matrix.py` — add one negative-path test that flips sensor and target altitudes for Cell 58 and asserts a raise. |
| **Effort** | Trivial — one test. |
| **Scenarios blocked** | None. |
| **Rerun after fix** | N/A — test-only addition. |

---

## Gap 42: lab_test / ground_test sub-cases unreachable from the Sensor config surface

| Field | Value |
|-------|-------|
| **Found in** | Scenario 7.4 refresh (Scenario_Execution_Plan Phase R, 2026-07-07) |
| **Status** | RESOLVED 2026-07-08 (bf43d5f) — `no_atmosphere_subcase` ∈ {ground_test, lab_test} builds a grey-body chamber background `L_bg=ε_bg·B(T_bg)` from `source.background.*` (Decision #15 blesses them here) instead of raising; warns on the default chamber temp. Lab/TVAC scenarios now run from config; a measured `L_bg(λ)` can still be injected. Follow-on (optional): migrate the lab-bench scripts (7.1/7.3/7.4/2.2/2.5) off the `space`-subcase + placeholder `h_sensor` workaround. |
| **Description** | The `no_atmosphere` sub-cases `lab_test` and `ground_test` require a `UserSpectralBackground(L_bg: SpectralData)`, which can only be injected by constructing the descriptor manually and publishing it into `stage_outputs["source"]["background"]` (the integration-test pattern in `tests/integration/test_no_atm_subcases.py`). `Sensor.from_dict` / YAML has no L_bg path, and `atmosphere.model = "exo"` auto-infers sub-case `space`. Lab/TVAC scenarios therefore masquerade as `space`, which (a) forces a placeholder positive `platform.h_sensor` (e.g. 1.0 m bench height) to satisfy the Earth-limb validator, and (b) substitutes `ColdSpaceBackground` for the actual chamber radiance. |
| **Workaround** | Model the chamber as `space` sub-case with `platform.h_sensor = 1.0` m and represent the chamber contents (cold plate / blackbody) as the extended target; acceptable when the scene fills the FOV and the true background term is negligible (77 K cold plate in MWIR). Used by scenario 7.4. |
| **Impact** | Every lab/TVAC scenario (7.x family) carries a physically-mislabeled sub-case and a placeholder altitude; a lit-lab scenario whose chamber background is NOT negligible cannot be modeled from the config surface at all. |
| **Fix location** | `io/config.py` + `source/_schema.py` — YAML/dict path for `source.no_atmosphere_subcase` plus a user-supplied background spectral radiance (file or grey-body spec); the illumination follow-on ADR flagged in `source/_inferrer.py` is the anchor. |
| **Effort** | Medium. |
| **Scenarios blocked** | None outright (workaround exists); 7.2 radiometric calibration (T3) would benefit directly. |
| **Rerun after fix** | Scenario 7.4; then drop the placeholder `platform.h_sensor` from the lab-bench scripts that carry it (7.1, 7.3, 7.4, 2.2, 2.5). |

---

## Gap 43: NEDT stage uses the single-λ Planck-factor approximation; exact dS/dT path exists but is unwired

| Field | Value |
|-------|-------|
| **Found in** | Scenario 6.3 refresh (Scenario_Execution_Plan Phase R), 2026-07-07 |
| **Status** | RESOLVED 2026-07-08 (0b33061) — `SpectralIntegrationStage` computes exact band-integrated `dS/dT` (Planck log-derivative); `PerformanceStage` uses σ/(dS/dT). Results-affecting (NEDT small); repinned 2 Option-C anchors. |
| **Description** | `performance/stage.py` computes NEDT via `nedt.compute_nedt_from_snr` — the analytic approximation `NEDT = T / (SNR · x·eˣ/(eˣ−1))` at the band-effective wavelength. The exact formulation `nedt.compute_nedt(noise_e, ds_dt_e_per_K)` (σ/(dS/dT) with a band-integrated, photon-weighted derivative) exists in the same module but is never called by the chain. For scenario 6.3 (300 K target, 3.5–5 µm, daytime space sub-case) the approximation reads ~13% LOW (20.76 vs 23.92 mK exact) — the dominant bias is that SNR includes the temperature-independent reflected-solar signal (~9% of in-band e⁻), which inflates SNR without contributing to dS/dT, making the reported thermal sensitivity optimistic. |
| **Workaround** | Post-process: compute dS/dT by finite difference (two chain runs at T ± ΔT) and divide the total noise by it — scenario 6.3's hand model shows the recipe. |
| **Impact** | NEDT accuracy for wide bands, low-x regimes, and any daytime scene with a reflective signal component; NEDT-derived requirement verification inherits the bias. |
| **Fix location** | `performance/stage.py` — wire `compute_nedt` with a chain-side finite-difference dS/dT (re-evaluate the source photon integral at T ± ΔT; no extra full-chain run needed since only the source term varies). Results-affecting (NEDT values change ~10–15% in affected regimes) — Category C with truth anchors. |
| **Effort** | Medium. |
| **Scenarios blocked** | None (6.3 documents the discrepancy). |
| **Rerun after fix** | Scenario 6.3 (NEDT row should drop to <1%); NEDT consumers 7.1/7.5. |

---

## Gap 44: `detector.qe_table_path` is schema-only — spectral QE has no config surface

| Field | Value |
|-------|-------|
| **Found in** | Scenario 2.1 execution (Phase T3), 2026-07-08 |
| **Status** | RESOLVED 2026-07-08 (dd1529f) — `RadiantSession` loads `qe_table_path` via `io.qe_csv` and injects `spectral_integration.qe_curve` (Rule 6). |
| **Description** | `detector.qe_table_path` is defined in `detector/_schema.py` (with a comment promising a "Phase 2C stage wrapper" XOR against `qe_value`) but nothing in the chain, IO layer, or API reads it. Spectral QE reaches the chain only via `stage_outputs["spectral_integration"]["qe_curve"]` injected through `RadiantSession.run(extra_stage_outputs=...)` — API-level, no YAML/dict path. |
| **Workaround** | `radiant.io.qe_csv.load_qe_csv(...)` → `QeCurve.evaluate(wl_grid)` → inject (scenario 2.1 pattern). |
| **Impact** | Schema drift (a documented parameter silently ignores user input if set via YAML); GUI/config users cannot supply a QE curve. Same config-surface family as Gap 42 (lab_test) and the Zernike injection (5.1). |
| **Fix location** | `api/session.py` or `api/sensor.py` — when `detector.qe_table_path` is set, load via `load_qe_csv` at the Rule 6 boundary and inject; enforce the promised XOR with `qe_value`. |
| **Effort** | Small (the loader exists). |
| **Scenarios blocked** | None (injection route works); 1.3 dual-band also uses it. |
| **Rerun after fix** | Scenario 2.1 (replace the manual injection with the config path). |

---

## Gap 45: Detector-comparison metrics (BLIP T, dark-current crossover T, NEI) are script-side

| Field | Value |
|-------|-------|
| **Found in** | Scenario 2.1 execution (Phase T3), 2026-07-08 |
| **Status** | RESOLVED 2026-07-08 (d916bd3) — `performance/dark_crossover_rate.py`, `blip_rate.py`, `noise_equivalent_irradiance.py`. |
| **Description** | The three standard detector-trade numbers have no native home: BLIP temperature (dark rate = photon rate), dark-current crossover temperature (dark shot = read noise), and NEI (σ_total/(QE·A_pix·t_int)). Scenario 2.1 computes each in 1–3 lines using `DarkCurrentCurve.temperature_at_rate` and chain outputs. |
| **Workaround** | Script-side one-liners (scenario 2.1 shows all three, with definitions). |
| **Impact** | Low — ergonomics only now that the loaders exist; NEI as `result.metrics["nei_photons_s_cm2"]` would need only quantities the chain already carries. |
| **Fix location** | `radiant.api` detector-trade helper or `performance/` NEI metric module (Rule 19: one metric, one module). |
| **Effort** | Small. |
| **Scenarios blocked** | None. |
| **Rerun after fix** | Scenario 2.1. |

---

## Gap 46: Calibration-analysis helpers (responsivity, linearity, calibration uncertainty) are script-side

| Field | Value |
|-------|-------|
| **Found in** | Scenario 7.2 execution (Phase T3), 2026-07-08 |
| **Status** | RESOLVED 2026-07-08 (d916bd3) — `radiant.api.calibration_analysis` (`analyze_calibration` → `CalibrationReport`). |
| **Description** | The standard calibration-verification quantities have no native home: responsivity dDN/dT (finite difference on a temperature sweep) and dDN/dL (against Planck band radiance), the gain/offset decomposition (`measured = a·predicted + b`), the linearity fit (DN vs L(T), % full-scale residuals), and calibration uncertainty (σ_DN, σ_T with N-frame scaling). Scenario 7.2 computes all of them in a few lines each from `Sensor.sweep(keep_results=True)` results. |
| **Workaround** | Script-side recipes in scenario 7.2 (documented step by step). |
| **Impact** | Low — ergonomics; a `radiant.api.calibrate` helper (sweep → fit report) would serve every calibration campaign, but the primitives all exist. |
| **Fix location** | `radiant.api` calibration helper composing `Sensor.sweep`; Rule 19 — one analysis, one module. |
| **Effort** | Small. |
| **Scenarios blocked** | None. |
| **Rerun after fix** | Scenario 7.2. |

---

## Gap 47: Spectral target emissivity has no chain input (scalar ε only)

| Field | Value |
|-------|-------|
| **Found in** | Scenario 4.3 execution (Phase T3), 2026-07-08 |
| **Status** | RESOLVED 2026-07-08 (d5b3eb2) — new `source.target.emissivity_path` (2-col CSV ε(λ)); the inferrer builds the thermal descriptor with spectral ε(λ)·B(λ,T), reusing the `SpectralData` emissivity `T1Thermal`/`T3Mixed` already accept. Mutually exclusive with scalar ε and all reflective/radiance/brightness surfaces. Opt-in; goldens unchanged. Retires the S8 workaround for scenario 4.3. |
| **Description** | `source.target.emissivity` is a scalar; there is no `emissivity_path` for a tabulated ε(λ) the way `source.target.reflectance_path` / `albedo_path` exist for reflective targets. A spectral thermal-emission target (measured/ASTER ε(λ)) can reach the chain only by pre-composing the radiance `L_t(λ) = ε(λ)·B(λ,T_surface)` and injecting it via the S8 `user_radiance_path` (→ `T6TabulatedAtSource`, "no physical model applied") — so the USER owns the Planck integral and the assumed surface temperature; the chain does not apply its atmosphere-coupled thermal-emission model to a spectral-ε target. |
| **Workaround** | Compose L_t(λ) = ε(λ)·B(λ,T) at the file boundary and feed S8 (scenario 4.3 pattern). |
| **Impact** | Spectral-emissivity targets (camouflage, material ID, any ASTER-emitter scene) can't use the chain's thermal-emission physics directly; the user re-implements the Planck integral. Parallel to Gaps 42/44 (config-surface coverage) and the S8 sub-pixel composition note in scenario 4.3's gaps.md. |
| **Fix location** | `source/_schema.py` + `source/_inferrer.py` — add `source.target.emissivity_path` routing to a spectral `T1Thermal` descriptor (ε(λ) × Planck at the target temperature), mirroring the reflectance-path plumbing. |
| **Effort** | Medium. |
| **Scenarios blocked** | None (S8 workaround); 4.3 and any spectral-emitter scene would use it. |
| **Rerun after fix** | Scenario 4.3 (replace the manual L_t composition with the ε-path input). |

---

## Gap 48: QE has no temperature dependence in the chain

| Field | Value |
|-------|-------|
| **Found in** | Scenario 7.5 execution (Phase T3), 2026-07-08 |
| **Status** | RESOLVED 2026-07-08 (b4b7d2e) — `detector.qe_temperature_coeff_per_K` + `qe_temperature_ref_K`; linear QE(T) applied at the API layer. |
| **Description** | `detector.qe_value` (and the QE-curve path, Gap 44) are temperature-independent; there is no QE(T) or QE(λ,T) model. A TVAC operating-temperature sweep must interpolate a measured QE(T) table externally and set the scalar per operating point. |
| **Workaround** | Interpolate QE(T) and set `detector.qe_value` per sweep point (scenario 7.5 pattern). |
| **Impact** | Low — scenario 7.5 shows QE(T) is second-order vs dark current (9% QE swing vs 294,612× dark over 70–95 K). A native QE(T) would let the chain co-vary QE with `detector.detector_temperature_K` automatically. |
| **Fix location** | `detector/_schema.py` + QE evaluation — a `qe_temperature_ref_K` + coefficient, or a QE(λ,T) table. Related to Gaps 44 (QE-curve config path) and 47 (spectral emissivity). |
| **Effort** | Small–Medium. |
| **Scenarios blocked** | None. |
| **Rerun after fix** | Scenario 7.5. |

---

## Gap 49: No diffraction-limited-resolution metric in result.metrics

| Field | Value |
|-------|-------|
| **Found in** | Scenario 1.2 execution (Phase T4), 2026-07-08 |
| **Status** | RESOLVED 2026-07-08 (63f599d) — `performance/diffraction_limit.py`; metrics `diffraction_limit_angular_urad`, `diffraction_limit_ground_m`. |
| **Description** | The Rayleigh ground spot (`1.22 λ (f/#)`, i.e. `1.22 λ · altitude / D` at nadir) is the optics-only resolution floor and the natural companion to `gsd_geometric_mean_m`, but it is not a surfaced metric. Scenario 1.2 computes it locally to draw the diffraction-limit constraint line and decide detector- vs diffraction-limited sampling. All inputs (aperture, focal length, band-center wavelength, range) already live in the chain — this is a surfacing gap, not a physics gap. |
| **Workaround** | Compute `1.22 λ_center · altitude / D` script-side (scenario 1.2 `diffraction_limited_gsd_m`). |
| **Impact** | Low — ergonomics; a designer comparing optics-limited vs detector-limited resolution should read it from the result, not re-derive it. Pairs with Gap 50. |
| **Fix location** | `performance/` new one-computation module + `performance/stage.py` metric wiring (Rule 19). |
| **Effort** | Trivial. |
| **Scenarios blocked** | None. |
| **Rerun after fix** | Scenario 1.2. |

---

## Gap 50: No detector-vs-diffraction-limited sampling-regime flag

| Field | Value |
|-------|-------|
| **Found in** | Scenario 1.2 execution (Phase T4), 2026-07-08 |
| **Status** | RESOLVED 2026-07-08 (63f599d) — `performance/sampling_regime.py`; metric `sampling_regime_code` (0/1/2). |
| **Description** | `q_center` (= λ·f/#/pitch) is already a metric, but the qualitative call it implies — detector-limited (`Q < 1`, undersampled/aliasing-risk) vs diffraction-limited (`Q ≳ 2`, oversampled) — is not surfaced. Scenario 1.2's whole takeaway is *where the design crosses that boundary*, and each trade script re-derives it from `q_center`. A `sampling_regime` enum/label metric would make the crossover a first-class output. |
| **Workaround** | Threshold `q_center` script-side. |
| **Impact** | Low — ergonomics; pairs with Gap 49. |
| **Fix location** | `performance/stage.py` — derive a label from the existing `q_center`. |
| **Effort** | Trivial. |
| **Scenarios blocked** | None. |
| **Rerun after fix** | Scenario 1.2. |

---

## Gap 51: No revisit / repeat-ground-track model

| Field | Value |
|-------|-------|
| **Found in** | Scenario 3.1 execution (Phase T4), 2026-07-08 |
| **Status** | RESOLVED 2026-07-08 (c4c01b7) — `core/repeat_ground_track.py` (J2 nodal regression, sun-sync inclination, ground-track spacing, first-order revisit). Exact repeat-cycle revisit remains a documented out-of-scope extension. |
| **Description** | `radiant.core.orbit` gives single-orbit kinematics (period, velocity, ground-track speed). True revisit time for a target latitude needs the sun-sync nodal-regression rate, the J2 repeat-cycle ground-track spacing, and the swath / access-corridor overlap between adjacent tracks — none of which is modeled. Scenario 3.1 reports orbits/day (86400/period) and the cross-track access corridor as coverage proxies. |
| **Workaround** | Orbits/day + access-corridor half-width (scenario 3.1 pattern). |
| **Impact** | Medium for coverage/revisit planning; a repeat-ground-track calculator is the natural layer above the orbit-kinematics model. Not blocking — orbits/day and the corridor answer the sizing question. |
| **Fix location** | New `core/` or `performance/` module: nodal regression + repeat cycle + track spacing; consumes `radiant.core.orbit`. |
| **Effort** | Medium. |
| **Scenarios blocked** | None (proxy available); a dedicated revisit scenario would use it. |
| **Rerun after fix** | Scenario 3.1 (replace orbits/day proxy with true revisit). |

---

## Gap 52: No first-class extended target-vs-background differential

| Field | Value |
|-------|-------|
| **Found in** | Scenario 4.4 execution (Phase T4), 2026-07-08 |
| **Status** | RESOLVED 2026-07-08 (3192f67) — ADR-0005 Option A implemented. New opt-in `source.contrast_reference.*` makes the extended `contrast_snr` a true two-pixel differential (nulls at radiance crossover), combined noise √(N_t²+N_ref²); reference is noise-decoupled so Decision #13's SNR/anchors are preserved and #15's deprecated params untouched. Default (temperature=0) leaves all results unchanged. Follow-on (optional): migrate scenarios 4.3/4.4 off the manual two-pixel workaround to the native metric. |
| **Description** | `SpectralIntegrationStage` builds `contrast_e = signal_e − background_e` only when an `at_aperture_background` frame exists — which happens in the sub-pixel regime (and point-source, where contrast_e = signal_e). In the EXTENDED regime, even with `source.background.temperature` set, the background-reference frame is not built (`spectral_integration/stage.py:283`, the "no background descriptor" branch), so `contrast_e` collapses to the whole-scene `signal_e` and the `contrast_snr` metric reports the absolute-scene SNR — it does NOT null at thermal crossover. Any scenario needing the extended two-surface differential (diurnal washout 4.4, camouflage 4.3, "target patch on terrain") must construct it by running the two pixels separately and differencing. |
| **Workaround** | Run target-filled and background-filled extended pixels separately; contrast SNR = (S_t − S_b)/√(N_t²+N_b²) (scenarios 4.3, 4.4). |
| **Impact** | Medium — the `contrast_snr` metric is misleading in the extended regime (name implies a differential; value is whole-scene SNR). A user trusting it for an extended target-vs-background scene would get a contrast that never washes out. |
| **Fix location** | `spectral_integration/stage.py` — build the `at_aperture_background` reference frame whenever `source.background.temperature`/`emissivity` are set, not only in sub-pixel; then `contrast_e` is meaningful in the extended regime too. Coordinate with matrix Decision #13 (computed-extended cells deliberately skip the bg reference). |
| **Effort** | Medium. |
| **Scenarios blocked** | None (differencing workaround); 4.3 and 4.4 would use it. |
| **Rerun after fix** | Scenarios 4.3, 4.4 (replace the manual two-pixel differencing with the native metric). |

---

## Gap 53: Johnson DRI model is sampling-limited (no MRC/MRT coupling)

| Field | Value |
|-------|-------|
| **Found in** | Scenario 4.2 execution (Phase T4), 2026-07-08 |
| **Status** | RESOLVED 2026-07-08 (b8418c0) — `performance/minimum_resolvable.py` (MRT = k·NETD/MTF, MRC = k·NEΔρ/MTF) + additive metric `mrt_at_nyquist_K`. Contrast-limited companion to the sampling-limited Johnson model (both ship); a contrast-limited range is composable at the scenario level (Johnson cycles + MRT at the task frequency). No scenario-4.2 rescope needed. Consumed by scenario 3.5. |
| **Description** | `radiant.performance.johnson_criteria` computes DRI ranges by counting geometric resolved cycles across the target; it assumes adequate target contrast. A full acquisition model couples cycles to the minimum-resolvable-contrast (MRC, reflective) or minimum-resolvable-temperature (MRT, thermal) curve, which folds in the system MTF and scene contrast, so a low-contrast target identifies at shorter range than the geometric Johnson value. The current model is the optimistic (high-contrast) upper bound. |
| **Workaround** | Use the sampling-limited DRI range as the best-case; note contrast dependence qualitatively (scenario 4.2). |
| **Impact** | Medium — at resolution-limited ranges (small targets, low contrast, dusk) the true range is shorter; the model overstates it. Fine as a geometric bound and clearly documented as such. |
| **Fix location** | New `performance/` module (MRC/MRT curve from system MTF + noise) feeding a contrast-limited `johnson_range_m` variant; Rule 19 (one analysis, one module). Consumes the existing MTF product path. |
| **Effort** | Medium–Large. |
| **Scenarios blocked** | None (geometric bound available); 4.2 and any acquisition-range scenario would use it. |
| **Rerun after fix** | Scenario 4.2 (add contrast-limited ranges alongside the geometric ones). |

---

## Gap 54: No arbitrary / measured pupil mask (only parametric shapes)

| Field | Value |
|-------|-------|
| **Found in** | Scenario 1.5 execution (Phase T4), 2026-07-08 |
| **Status** | RESOLVED 2026-07-08 (f4224ad) — `make_pupil_amplitude` `mask_override`, injected via `optics_config["pupil_mask_override"]`; supersedes parametric geometry, enters both PSF and MTF paths. |
| **Description** | `make_pupil_amplitude` builds the pupil from parametric shapes: circular aperture + central obscuration + radial spider arms. There is no path to inject an arbitrary measured 2-D pupil mask (segmented aperture, non-circular primary, wavefront-sensor pupil image). The grid could accept an injected amplitude array. |
| **Workaround** | Use the parametric obscuration + spider shapes (cover the common Cassegrain/refractor cases). |
| **Impact** | Low–Medium — segmented/exotic apertures cannot be modelled; parametric shapes cover mainstream designs. |
| **Fix location** | `optics/pupil_amplitude.py` — optional `mask_override: NDArray` argument threaded like the `SpiderVaneSpec` (both PSF and MTF paths consume it → Rule 4 automatic). |
| **Effort** | Low–Medium. |
| **Scenarios blocked** | None; a segmented-aperture scenario would use it. |
| **Rerun after fix** | Scenario 1.5 (add a measured-pupil case). |

---

## Gap 55: No PDF spec-sheet parser

| Field | Value |
|-------|-------|
| **Found in** | Scenario 3.3 execution (Phase T4), 2026-07-08 |
| **Status** | OPEN |
| **Description** | Vendor sensor spec sheets arrive as PDFs (text + embedded QE plots); RADIANT has no PDF ingestion. Scenario 3.3 transcribes the vendor numbers into a workbook (the RADIANT-facing input) as the workaround. |
| **Workaround** | Transcribe vendor specs into a structured workbook (scenario 3.3 pattern). |
| **Impact** | Low — a manual transcription step for procurement comparisons; adequate for the workflow. |
| **Fix location** | New `io/` PDF importer (text extraction + embedded-plot digitisation); large, out of scope for scenario work. |
| **Effort** | Large. |
| **Scenarios blocked** | None (workbook workaround). |
| **Rerun after fix** | Scenario 3.3. |

---

## Gap 56: No multi-target spatial scene model (single-pixel radiometry only)

| Field | Value |
|-------|-------|
| **Found in** | Scenario 6.4 execution (Phase T4), 2026-07-09 |
| **Status** | OPEN |
| **Description** | RADIANT is a single-pixel / single-target radiometry engine: one run yields one pixel's signal + noise for one source against one background. There is no 2-D scene model — no way to place multiple targets spatially, PSF-convolve them into a shared focal plane, mix per-pixel radiance from overlapping sources, or lay out a background field. Scenario 6.4 fakes a multi-target scene by running the chain once per target and assembling a 1-D pixel strip in the script, applying an analytic fill-fraction dilution for sub-pixel targets. This covers the radiometry but not the *spatial* scene (no PSF blur between neighbours, no sub-pixel placement, no 2-D layout). |
| **Workaround** | Run the chain per target + background; assemble pixels in the scenario script; dilute sub-pixel targets by `ff = (size/GSD)²`. Works because extended per-pixel signals are range-independent (only `ff` varies). Adequate for per-target detectability/ROC studies; not for spatial-algorithm testing (edge detection, clutter, PSF-limited separation). |
| **Impact** | Medium — per-pixel radiometry and per-target ROC are available today; true scene-level and spatial-algorithm work is not. |
| **Fix location** | New `scene/` module (target masks, sub-pixel placement, PSF-convolved rendering, per-pixel mixed radiance). Large; belongs in the framework, not a scenario script. |
| **Effort** | Large. |
| **Scenarios blocked** | None outright (6.4 stopgap); a true spatial-scene scenario would need it. |
| **Rerun after fix** | Scenario 6.4 (replace the scripted strip with a rendered scene). |

---

## Gap 57: `standard_atmosphere` preset only sets emission temperature, not humidity/transmission

| Field | Value |
|-------|-------|
| **Found in** | Scenario 3.5 execution (Phase T4), 2026-07-09 |
| **Status** | RESOLVED 2026-07-09 — `build_atmosphere_model` now substitutes the profile's McClatchey/MODTRAN water column (`simple.PROFILE_PWV_CM`) when `precipitable_water_cm` is left at its schema default; explicit values win (provenance-based). Golden + Cell-28 anchor repinned; 10 Level-0 coupling tests. |
| **Description** | Selecting `atmosphere.standard_atmosphere = "tropical"` (or any of the six presets) changes only the downwelling **emission temperature** via the sea-level temperature table (`atmosphere/simple.py` `_T_SEA_LEVEL_K`: tropical 299.65 K vs us_standard 288.15 K, used in `_effective_atmospheric_temperature_K`). It does **not** set the profile-appropriate water-vapour column, ozone, or transmission. Precipitable water is a *separate* independent parameter (`atmosphere.precipitable_water_cm`, default 1.4 cm = US-standard mid-latitude). A user who selects "tropical" but leaves PWV at default gets tropical emission temperature with **US-standard transmission** — silently wrong for MWIR/LWIR window radiometry, where the tropical humidity column is the dominant effect. |
| **Workaround** | Set `precipitable_water_cm` explicitly to the climate-appropriate value alongside the preset (scenario 3.5 uses 4.1 cm for tropical). |
| **Impact** | Medium — transmission error can be large in humid columns; the preset name implies a full profile it does not deliver. |
| **Fix location** | `atmosphere/simple.py` — couple the preset to a default PWV (and ozone) table, or validate that PWV was set when a non-us_standard preset is chosen. Doc lock-step with `RADIANT_Atmosphere.md`. |
| **Effort** | Small–Medium. |
| **Scenarios blocked** | None (explicit-PWV workaround); any climate-zone scene relying on the preset alone is affected. |
| **Rerun after fix** | Scenario 3.5. |

---

## Gap 58: No GeoTIFF / raster reader for surface maps

| Field | Value |
|-------|-------|
| **Found in** | Scenario 3.5 execution (Phase T4), 2026-07-09 |
| **Status** | OPEN |
| **Description** | RADIANT has no importer for GeoTIFF (or any raster) surface-temperature or land-cover maps. Raj's NOAA land-surface-temperature map cannot be ingested; the scenario transcribes it to a 1-D CSV strip as the workaround. A real reader would ingest the 2-D field and — with Gap 56's scene model — drive a per-pixel background. |
| **Workaround** | Transcribe the raster to a CSV strip / scalar envelope (scenario 3.5 pattern). |
| **Impact** | Low–Medium — a manual transcription step; blocks true map-driven backgrounds. |
| **Fix location** | New `io/` raster reader (rasterio/GDAL or a minimal GeoTIFF parser); pairs with the `scene/` module (Gap 56). |
| **Effort** | Medium. |
| **Scenarios blocked** | None (CSV workaround); map-driven scenes need it. |
| **Rerun after fix** | Scenario 3.5. |

---

## Gap 59: No solar-dependence (day/night) analysis mode

| Field | Value |
|-------|-------|
| **Found in** | Scenario 3.5 execution (Phase T4), 2026-07-09 |
| **Status** | OPEN |
| **Description** | There is no first-class toggle to add/remove a reflected-solar term from an emissive scene and report the day/night delta. Scenario 3.5 computes the thermal-vs-reflected-solar comparison analytically (`core.blackbody`) script-side to demonstrate solar independence. A built-in mode would fold the reflected-solar term into the chain radiometry and expose a day/night comparison metric. |
| **Workaround** | Compute reflected-solar band radiance analytically and compare to thermal emission (scenario 3.5 pattern). |
| **Impact** | Low — the analytic side calculation is adequate; a mode would package it and couple it to the chain. |
| **Fix location** | `source/` reflective-solar term + a chain flag; relates to the existing E_sky single-scatter work (Gap 38). |
| **Effort** | Medium. |
| **Scenarios blocked** | None (analytic workaround). |
| **Rerun after fix** | Scenario 3.5. |

---

## Gap 60: Stray light is a scalar noise pedestal only (no 2-D PSF, no MTF impact)

| Field | Value |
|-------|-------|
| **Found in** | Scenario 5.5 execution (Phase T4), 2026-07-09 |
| **Status** | OPEN |
| **Description** | RADIANT models stray light as a spatially-uniform electron pedestal — veiling-glare fraction (`optics.stray.veiling_glare_fraction`, but see CU-062: currently inert) or absolute irradiance (`optics.stray.absolute_irradiance_W_m2`, correct) — that contributes shot noise to every pixel. It cannot ingest a 2-D stray-light PSF / PST map (FRED, Zemax `pst_file` mode raises `NotImplementedError`), and it does not model the veiling-glare **MTF / low-frequency contrast-modulation reduction**. The radiometric (noise) hit is captured; the spatial (resolution) hit is not. |
| **Workaround** | Use the scalar `absolute_irradiance` pedestal for the noise/SNR/NIIRS impact (scenario 5.5); accept that the MTF/contrast-modulation effect is unmodelled. |
| **Impact** | Low–Medium — noise impact is available; spatial-contrast impact and vendor-PSF ingestion are not. |
| **Fix location** | `optics/stray_light.py` PST-file mode + a stray-light MTF term feeding the MTF product (Rule 4); pairs with Gap 58 (raster reader). |
| **Effort** | Medium–Large. |
| **Scenarios blocked** | None (scalar workaround); a full stray-light-PSF scenario needs it. |
| **Rerun after fix** | Scenario 5.5. |

## Summary Table

| # | Gap | Effort | Scenarios impacted | Status |
|---|-----|--------|--------------------|--------|
| 1 | IPC not wired | Small | 1 | FIXED |
| 2 | SNR = 0 at orbital altitude | — | 7+ | FIXED |
| 3 | NEDT missing | Small | 10+ | FIXED |
| 4 | NIIRS missing | Small | 11 | FIXED |
| 5 | GSD missing | Trivial | 5+ | FIXED |
| 6 | Unit-aware input | Medium | All | FIXED |
| 7 | Parameter name discovery | Small | All | FIXED |
| 8 | Strehl ratio missing | Trivial | 2 | FIXED |
| 9 | Full MTF curve missing | Small | 4+ | FIXED |
| 10 | No inverse solver | Medium | Many | FIXED |
| 11 | No per-element nearfield breakdown | Medium | Few | CLOSED |
| 12 | cold_stop_efficiency naming | Small | Few | FIXED |
| 13 | Q parameter missing | Trivial | Few | FIXED |
| 14 | No aliased/folded MTF | Medium | Few | CLOSED |
| 15 | MTF = 0 at high Q (investigate) | Small | Few | CLOSED |
| 16 | Per-wavelength PSFs not exposed | Small | Few | CLOSED |
| 17 | No arbitrary PSF weighting spectrum | Small | Few | FIXED |
| 18 | Platform jitter not wired | — | 5.4 | FIXED |
| 19 | No MTF budget decomposition | Medium | 5.4, 7.3 | FIXED |
| 20 | No GIQE-5 sensitivity analysis | Small | 5.4 | FIXED |
| 21 | No jitter PSD / frequency dependence | Large | 5.4 | DEFERRED |
| 22 | RER below GIQE-5 calibration range | Small | 5.4 | FIXED |
| 23 | No jitter-source allocation tool | Medium | 5.4 | FIXED |
| 24 | No Zernike-to-PSF integration | Medium | 5.1 | CLOSED |
| 25 | No field-dependent WFE | Large | 5.1 | CLOSED |
| 26 | No Zemax Zernike importer | Medium | 5.1 | FIXED |
| 27 | MTF curve frequency axis units | Small | 5.1 | FIXED |
| 28 | No WFE allocation / error budget tool | Medium | 5.1 | FIXED |
| 29 | No defocus model (focus-shift) | Small | 7.3 | CLOSED |
| 30 | No measurement data import/overlay API | Medium | 7.x | FIXED |
| 31 | No scatter / surface roughness (TIS) | Medium | 7.3 | FIXED |
| 32 | No electronics MTF model | Small | 7.3 | FIXED |
| 33 | GSD not adjusted for off-nadir angle | Small | 3.4 | CLOSED |
| 34 | NIIRS not recomputed with off-nadir GSD | Small | 3.4 | CLOSED |
| 35 | No along/cross-track GSD at off-nadir | Medium | 3.4 | CLOSED |
| 36 | No swath width / access geometry | Medium | 3.4 | CLOSED |
| 37 | Nearfield emission = 0 in scalar transmission mode | Small-Medium | 7.1, 7.4, 2.2, 2.5, 3.2 | FIXED |
| 38 | E_sky ω₀ aerosol/spectral fidelity | Medium | UC Cells 25, 40, 55 | DEFERRED |
| 39 | A3 partial-column MODTRAN parity (blocked) | Small | UC Table C | DEFERRED |
| 40 | Lab dark-cal mode not first-class | Small | UC D-lab | DEFERRED |
| 41 | Earth-LOS negative integration test | Trivial | UC D-space | FIXED |
| 42 | lab_test/ground_test unreachable from config surface | Medium | 7.x lab family | FIXED |
| 43 | NEDT uses single-λ approximation; exact dS/dT unwired | Medium | 6.3, 7.1, 7.5 | FIXED |
| 44 | detector.qe_table_path schema-only; no config surface for spectral QE | Small | 2.1, 1.3 | FIXED |
| 45 | BLIP/crossover/NEI detector-trade metrics script-side | Small | 2.1 | FIXED |
| 46 | Calibration-analysis helpers script-side | Small | 7.2 | FIXED |
| 47 | Spectral target emissivity has no chain input (scalar only) | Medium | 4.3 | FIXED |
| 48 | QE has no temperature dependence | Small | 7.5 | FIXED |
| 49 | Diffraction-limited-resolution metric missing | Trivial | 1.2 | FIXED |
| 50 | Detector-vs-diffraction sampling-regime flag missing | Trivial | 1.2 | FIXED |
| 51 | No revisit / repeat-ground-track model | Medium | 3.1 | FIXED |
| 52 | No first-class extended target-vs-background differential | Medium | 4.3, 4.4 | FIXED (ADR-0005) |
| 53 | Johnson DRI model sampling-limited (no MRC/MRT) | Medium-Large | 4.2 | FIXED (MRT/MRC model) |
| 54 | No arbitrary/measured pupil mask (parametric only) | Low-Medium | 1.5 | FIXED |
| 55 | No PDF spec-sheet parser | Large | 3.3 | OPEN |
| 56 | No multi-target spatial scene model (single-pixel only) | Large | 6.4 | OPEN |
| 57 | standard_atmosphere preset sets emission temp only, not humidity | Small-Medium | 3.5 | FIXED |
| 58 | No GeoTIFF / raster reader for surface maps | Medium | 3.5 | OPEN |
| 59 | No solar-dependence (day/night) analysis mode | Medium | 3.5 | OPEN |
| 60 | Stray light is a scalar noise pedestal (no 2-D PSF, no MTF impact) | Medium-Large | 5.5 | OPEN |

---

## Scenario-Driven Capability Priority List

Source: `docs/guides/scenario_catalog.md` (formerly `docs/architecture/expanded_scenarios.md`) — 35 persona-driven scenarios grouped by implementation tier. Earlier tiers build capabilities that unlock later ones.

### Tier 1 — Executable today with scripting only (0 code changes)

| Priority | Scenario | Persona | Why first |
|----------|----------|---------|-----------|
| 1 | 6.3 | Dr. Chen | Verify noise model against hand calcs; all 16 noise terms already output |
| 2 | 2.3 | Mike | Sweep `ipc_coupling` (exists); compose with existing MTF/EE outputs |
| 3 | 7.4 | Karen | Sweep `cold_stop_efficiency` (exists); compare background signal |
| 4 | 5.2 | Tom | Sweep pixel pitch; Q = λf/#/p is trivial on existing outputs |
| 5 | 5.3 | Tom | Polychromatic PSF already implemented; script mono vs. poly |

### Tier 2 — Need 1–2 metric additions (performance stage only)

Changes concentrated in `src/radiant/performance/` — no signal-chain modifications.

| Priority | Scenario | Persona | New metric needed |
|----------|----------|---------|-------------------|
| 6 | 7.1 | Karen | NEDT (+ lab/exo atmosphere mode — already exists) |
| 7 | 2.2 | Mike | NEDT, noise breakdown vs. frame rate |
| 8 | 2.5 | Mike | Well fill fraction (trivial: signal_e / FWC) |
| 9 | 3.2 | Raj | NIIRS (GIQE-5 code exists, not surfaced), GSD |
| 10 | 5.4 | Tom | NIIRS, jitter sweep (platform params may need additions) |
| 11 | 1.4 | Sarah | NIIRS, saturation check, TDI sweep (`n_tdi` exists) |
| 12 | 5.1 | Tom | Strehl, full MTF curve, field-dependent WFE |
| 13 | 7.3 | Karen | Full MTF curve export, defocus model |
| 14 | 3.4 | Raj | GSD (along/cross-track), NIIRS, off-nadir geometry |

### Tier 3 — Need input parsers / format converters (io/ module only)

Changes concentrated in `src/radiant/io/` — no physics modifications.

| Priority | Scenario | Persona | Parser needed |
|----------|----------|---------|---------------|
| 15 | 2.1 | Mike | QE CSV (nm/pct → µm/frac), J_dark CSV (A/cm² → e⁻/s) |
| 16 | 6.2 | Dr. Chen | MODTRAN tape7 (wavenumber), libRadtran (nm/mW) |
| 17 | 1.1 | Sarah | MODTRAN tape7, ocean emissivity model |
| 18 | 4.1 | Lisa | Excel target library, batch scenario matrix |
| 19 | 7.2 | Karen | Lab calibration CSV, DN output |
| 20 | 1.3 | Sarah | ASTER spectral library, Excel detector specs |
| 21 | 4.3 | Lisa | Spectral emissivity input (curve, not scalar) |
| 22 | 7.5 | Karen | Measured J(T) curve, QE(T) table |

### Tier 4 — Need new models or capabilities (new modules)

Require new physics models, analysis modes, or architectural additions beyond metric reporting and I/O.

| Priority | Scenario | Persona | New capability |
|----------|----------|---------|----------------|
| ~~23~~ | ~~1.2~~ | ~~Sarah~~ | ~~Solar geometry calculator (LTAN/date/lat → zenith)~~ — **DONE** `radiant.core.solar_geometry` (00efcc5) |
| ~~24~~ | ~~3.1~~ | ~~Raj~~ | ~~Orbit → geometry calculator, pass planning~~ — **DONE** `radiant.core.orbit` (e32188e) |
| 25 | 4.4 | Lisa | Time-varying scenario (diurnal temperature sweep) |
| ~~26~~ | ~~4.2~~ | ~~Lisa~~ | ~~Johnson criteria / DRI range model~~ — **DONE** `radiant.performance.johnson_criteria` (0df9e15) |
| ~~27~~ | ~~1.5~~ | ~~Sarah~~ | ~~Arbitrary pupil mask (spider vanes), Strehl~~ — **DONE** spider vanes (36286e7); arbitrary mask → Gap 54 |
| ~~28~~ | ~~4.5~~ | ~~Lisa~~ | ~~Microbolometer noise model (NETD-specified)~~ — **DONE** via D*/NEP/NETD converters (ac59315) |
| ~~29~~ | ~~3.3~~ | ~~Raj~~ | ~~Multi-sensor comparison framework, compliance matrix~~ — **DONE** scenario (giqe_sensitivity reuse); PDF parser → Gap 55 |
| ~~30~~ | ~~6.1~~ | ~~Dr. Chen~~ | ~~D* / NETD / NEP → component noise converters~~ — **DONE** `performance.detectivity`/`nep_electrons`/`nep_netd` (ac59315) |
| ~~31~~ | ~~2.4~~ | ~~Mike~~ | ~~Multi-frame persistence model (temporal sequence)~~ — **DONE** `detector.persistence_sequence` (c4a3a28) |
| ~~32~~ | ~~6.5~~ | ~~Dr. Chen~~ | ~~Temperature retrieval (inverse), Jacobian~~ — **DONE** `performance.temperature_retrieval` (6623d0d) |
| 33 | 6.4 | Dr. Chen | Multi-target scene, per-pixel simulation, ROC curve |
| 34 | 3.5 | Raj | Tropical atmosphere, GeoTIFF reader, MRT metric |
| 35 | 1.3 | Sarah | Detection probability model, dual-band comparison |

### Key metric additions and how many scenarios they unlock

| Metric / Feature | Scenarios unlocked | Effort |
|------------------|--------------------|--------|
| **NEDT** | 7.1, 7.4, 7.5, 2.2, 2.5, 3.5, 4.5, 6.5, 1.1, 1.3 (10) | Small — σ / ∂L/∂T |
| **NIIRS** (surface GIQE-5) | 3.1, 3.2, 3.4, 5.1, 5.4, 1.1, 1.2, 1.4, 4.1, 4.2, 4.5 (11) | Small — code exists |
| **GSD** | 3.2, 3.4, 1.2, 4.5 (4) | Trivial — p·h/f |
| **Full MTF curve** | 5.1, 5.2, 5.3, 7.3 (4) | Medium — array output |
| **Strehl ratio** | 5.1, 1.5 (2) | Trivial — max(PSF)/max(Airy) |
| **Detection range** | 1.1, 4.1, 4.2, 4.3 (4) | Medium — range-SNR solver |
| **Lab/exo mode docs** | 7.1, 7.2, 2.1, 2.2 (4) | Zero — already exists |
