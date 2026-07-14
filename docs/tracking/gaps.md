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
| **Status** | DEFERRED (refreshed 2026-07-10, Backlog_Closure_Plan Wave 0) — Large; needs a PSD input-format design decision. Gated on a future platform-modeling task; re-audit 2026-10-01. |
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
| **Status** | DEFERRED (refreshed 2026-07-10, Backlog_Closure_Plan Wave 0) — implementable without MODTRAN but not validatable to the parity fidelity the gap demands; owner reconfirmed no MODTRAN 2026-07-10. Re-audit 2026-10-01 or on MODTRAN access. |
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
| **Status** | DEFERRED (refreshed 2026-07-10, Backlog_Closure_Plan Wave 0) — owner reconfirmed no MODTRAN access. Re-audit 2026-10-01 or on MODTRAN access, whichever comes first. |
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
| **Status** | RESOLVED 2026-07-09 (commit `c8a6f70`, Backlog_Closure_Plan Wave 1) — `source.lab_test_mode ∈ {'', dark, lit}` positive assertion added; 'dark' validated against user-set reflectance (no external illumination), 'lit' recorded, '' back-compat. Owner's close-the-backlog directive 2026-07-10 satisfied the "when a user asks" gate. |
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
| **Status** | DECLINED 2026-07-10 — large build (text extraction + plot digitisation) for low value; workbook transcription (scenario 3.3 pattern) is the accepted workflow (Backlog_Closure_Plan Wave 0). |
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
| **Status** | DECLINED 2026-07-10 — owner decision: RADIANT stays a single-pixel model; 2-D scene work is out of scope. Re-open only on explicit re-scope (Backlog_Closure_Plan Wave 0). |
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
| **Status** | DEFERRED 2026-07-10 — value is predicated on map-driven backgrounds (Gap 56, declined); the CSV-transcription workaround is adequate. Gated on any future 2-D re-scope; re-audit alongside Gap 56. |
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
| **Status** | RESOLVED 2026-07-10 (commit `19ae3b9`, Backlog_Closure_Plan Wave 3) — `geometry.solar_illumination ∈ {day, night}` toggle; 'night' sets theta_s = None (assembly drops direct-solar + solar sky; thermal downwelling remains). Investigation found the chain ALREADY folds reflected solar into mixed scenes via T3Mixed — the missing piece was that the solar_zenith_rad default gave every T2/T3 scene a phantom sun, making night inexpressible. |
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
| **Status** | PARTIALLY RESOLVED 2026-07-10 (d3274ab) — MTF impact landed; PST/2-D import DEFERRED |
| **Description** | RADIANT modeled stray light as a spatially-uniform electron pedestal — veiling-glare fraction (`optics.stray.veiling_glare_fraction`; CU-062 inertness fixed 2026-07-07) or absolute irradiance (`optics.stray.absolute_irradiance_W_m2`) — that contributes shot noise to every pixel. It could not ingest a 2-D stray-light PSF / PST map (FRED, Zemax `pst_file` mode raises `NotImplementedError`) and did not model the veiling-glare **MTF / low-frequency contrast-modulation reduction**. |
| **Resolution (partial)** | Veiling-glare spatial halo landed (Backlog_Closure_Plan Wave 3c): opt-in `optics.stray.veiling_glare_mtf` + `optics.stray.halo_sigma_um` re-image the stray fraction as a Gaussian halo on BOTH spatial paths (Rule 4) via the Gap-31 scatter builders — kernel `(1−vgf)·δ + vgf·G(σ)` on the `EffectivePSF`, exact analytic Fourier pair `(1−vgf) + vgf·exp(−2π²σ²f²)` on the MTF product (`mtf_stray_x/y`). Consistency-check clean; default-off (pedestal-only) is bit-identical. See `RADIANT_Optics.md` §8.3 and `tests/integration/test_stray_halo_chain.py`. |
| **Deferred remainder** | 2-D PST / vendor-PSF ingestion (`pst_file` mode still raises `NotImplementedError`). Gating condition: the single-pixel scope decision (owner, 2026-07-07 — "not going to do 2D"); pairs with Gap 58 (raster reader). Re-audit when 2-D/imaging scope reopens. |
| **Workaround (for deferred part)** | The scalar pedestal + opt-in Gaussian halo cover noise and first-order contrast impact; a vendor-measured PST halo shape is not representable. |
| **Impact (remaining)** | Low — vendor-PSF ingestion only. |
| **Scenarios blocked** | None. |
| **Rerun after fix** | Scenario 5.5 (optionally with `veiling_glare_mtf=1` to quantify the contrast hit). |

## Gap 61: Emissivity library has no wind-state ocean or rust-specific hull materials

| Field | Value |
|-------|-------|
| **Found in** | Scenario 1.1 execution, 2026-07-11 |
| **Status** | OPEN |
| **Description** | `data/emissivity/` has one calm-water curve (`water_calm.csv`) and generic `steel.csv`; scenario 1.1's maritime target needs sea-state-3 (wind-roughened) ocean emissivity and a partially-rusted steel hull curve, neither of which exist. |
| **Workaround** | Use `water_calm` and generic `steel` — affects absolute SNR/detection-range numbers, not the relative SimpleAtmosphere-vs-MODTRAN comparison scenario 1.1 is actually demonstrating. |
| **Impact** | Low — cosmetic on a demonstration scenario; would matter more for a real maritime-sensor trade study. |
| **Fix location** | `data/emissivity/` — add wind-speed-parameterized ocean model (Cox-Munk-style) and a rusted-steel curve. |
| **Effort** | Small (data only) for a static rusted-steel curve; Medium for a real wind-state model. |
| **Scenarios blocked** | None (workaround adequate for 1.1's actual purpose). |
| **Rerun after fix** | Scenario 1.1. |

## Gap 62: No PowerPoint/slide-table export from scenario results

| Field | Value |
|-------|-------|
| **Found in** | Scenario 1.1 execution, 2026-07-11 (originally flagged in the scenario catalog, 2026-04-15) |
| **Status** | OPEN |
| **Description** | Several scenarios (1.1 among them) want a one-click slide-ready summary table; today every scenario prints a text table and/or an xlsx sheet, with no PPTX or slide-image export. |
| **Workaround** | Manual copy from the printed/xlsx summary table. |
| **Impact** | Low — cosmetic/ergonomic, cross-scenario. |
| **Fix location** | New small `radiant.io` or scenario-tooling helper (e.g. `python-pptx`-based table export); not chain-related. |
| **Effort** | Small. |
| **Scenarios blocked** | None. |
| **Rerun after fix** | N/A (tooling addition, not a physics rerun). |

## Gap 63: No libRadtran parser or implementation

| Field | Value |
|-------|-------|
| **Found in** | Scenario 6.2 execution, 2026-07-11 (originally flagged in the scenario catalog, 2026-04-15) |
| **Status** | OPEN |
| **Description** | No libRadtran output-format parser exists anywhere in this repo, and no real libRadtran run has ever been made against RADIANT. Scenario 6.2's intercomparison is 2-way (SimpleAtmosphere vs. MODTRAN-synthetic) instead of the catalog's intended 3-way. |
| **Workaround** | None by design — per the no-fabricated-independent-data policy (`modtran/synthetic/README.md`), hand-authoring plausible libRadtran numbers would defeat the purpose of an intercomparison the same way a fake MODTRAN dataset would. |
| **Impact** | Medium — blocks the 3-way comparison specifically; the 2-way MODTRAN comparison is otherwise complete. |
| **Fix location** | New `radiant.io` (or scenario-local) libRadtran output parser (nm, mW/m²/sr/nm — non-SI, needs unit conversion at the boundary like `Tape7Reader`); needs real libRadtran access or donated output to populate. |
| **Effort** | Medium (parser) + external dependency (real libRadtran access). |
| **Scenarios blocked** | Full 3-way completion of scenario 6.2. |
| **Rerun after fix** | Scenario 6.2. |

## Gap 64: No spectral residual / per-band error-analysis tool

| Field | Value |
|-------|-------|
| **Found in** | Scenario 6.2 execution, 2026-07-11 |
| **Status** | OPEN |
| **Description** | The catalog wants "spectral residuals: RADIANT minus MODTRAN" and "band-by-band error analysis: where does the simple model break down?" Scenario 6.2 computes only an in-band mean residual per profile; no reusable spectral-residual or per-band-error RADIANT capability exists. |
| **Workaround** | Ad-hoc `np.interp`-based comparison in the scenario script, not reusable. |
| **Impact** | Low-Medium — affects any future model-comparison scenario, not just 6.2. |
| **Fix location** | New small `radiant.performance` or scripting utility: two `SpectralData`-like series in, residual + per-band breakdown out. |
| **Effort** | Small-Medium. |
| **Scenarios blocked** | None (workaround adequate for 6.2's current scope). |
| **Rerun after fix** | Scenario 6.2 (richer residual figure). |

## Gap 65: Full-well saturation is a recurring, silent failure mode across scenario authoring

| Field | Value |
|-------|-------|
| **Found in** | Scenarios 6.1 (2026-07-10), 6.2, 8.2 (2026-07-11) — three independent occurrences |
| **Status** | FIXED 2026-07-11 |
| **Description** | A scenario config with too-long integration time / too-generous well-fill saturated the detector (`well_status: clipped`, `signal_e_final` pinned at `full_well_capacity_e`) with no error and no visible warning outside `stage_outputs`. Two configs that should produce different SNR (different atmosphere, different profile) instead produced bit-identical SNR, which read as "no effect" rather than "clipped" unless the author specifically checked `well_status`. |
| **Resolution** | Two-part fix. (1) `ReadoutStage` now emits a `UserWarning` when either the well-capacity or ADC saturation check clips — this was also a latent Rule 17 violation ("no clipping to valid ranges without at minimum a UserWarning"); both clips were silent. (2) Root-cause accomplice: the scenario scripts blanket-suppressed all warnings (`warnings.simplefilter("ignore")` to quiet GIQE-extrapolation noise), which had also been hiding CU-061's pre-existing `contrast_snr` saturation warning; the four affected scripts (1.1, 6.2, 8.1, 8.2) now re-enable any warning matching "saturated" through the blanket filter. The new warning immediately caught a second live instance: all four scenario configs were still **ADC**-saturating (gain 16 e-/DN with 14-bit ADC caps the representable signal at ~2.6e5 e-, far below each config's FWC) — fixed by matching gain to FWC/2^bits per standard detector design; walkthrough tables re-baselined (~0.1% SNR shifts from the higher quantization noise). |
| **Verification** | 3 new readout stage tests (warn on well clip, warn on ADC clip, no warning when unclipped); the original silently-failing 8.2 config now emits 3 warnings; all four scenario scripts run warning-free with corrected configs. |
| **Rerun after fix** | Done in the same change — all four scenario scripts re-run, tables updated. |

## Gap 66: `detector.qe_table_path` unusable without a meaningless scalar `qe_value`

| Field | Value |
|-------|-------|
| **Found in** | Scenario 1.1 execution (2026-07-11); same friction independently hit by scenario 1.2 earlier (both worked around by band-averaging the QE curve to a scalar) |
| **Status** | FIXED 2026-07-11 |
| **Description** | The schema documents `detector.qe_table_path` as **superseding** the scalar `detector.qe_value`, and the loading machinery honors that (the injected `qe_curve` wins in `SpectralIntegrationStage`; the scalar is never read). But `qe_value` has `default=None`, and `ParameterSet.resolve()` treated `default=None` as unconditionally required — rejecting a table-only config with "Required parameter 'detector.qe_value' is not set." The schema's own comment promised a "Phase 2C ConsistencyGroup" XOR enforcement that was never built. |
| **Resolution** | New generic `ParameterDef.required_unless` field: a required parameter names the alternative that supersedes it; when the alternative is explicitly set (non-empty), the requirement is waived and the parameter stays **unresolved** (`get()` raises if anything reads it — no phantom value). `detector.qe_value` now carries `required_unless="detector.qe_table_path"`. The required-parameter error message names the superseding alternative. 6 new core tests + 1 integration regression test (table-only config must produce bit-identical results to table+scalar, proving the scalar truly is superseded). |
| **Verification** | Table-only config evaluates; neither-set still raises actionably (with the new hint); explicitly-empty path does NOT waive the requirement; scalar-only historical path unchanged. |
| **Rerun after fix** | None required — scenarios 1.1/1.2's band-average workaround remains valid (it produces the same in-band result); future scenarios can now use the table directly. |

## Gap 67: No session/run persistence (Sensor.save/load, ChainResult serialize/reload)

| Field | Value |
|-------|-------|
| **Found in** | Capability audit 2026-07 (`docs/reports/capability_audit_2026-07/`, F-01), 2026-07-11 |
| **Status** | FIXED (2026-07-11, commit `addcf43`) — sweep/MC container persistence remains future work (see Impact) |
| **Description** | No `Sensor.save/load`, no `ChainResult` serialize/reload existed. Only metrics+noise JSON and provenance JSON existed (`cli/run.py`); `io/config.py:save_config` saved parameters only. |
| **Fix** | `Sensor.save(path)`/`Sensor.load(path)`: YAML round trip of explicit inputs + `_radiant` metadata block (wavelength_points, tolerance distributions) — reload reproduces resolution and provenance exactly (`RADIANT_Config_Format.md` §1.7). `ChainResult.save(path)`/`ChainResult.load(path)`: single-file zip archive (`radiant.io.serialization`, JSON manifest + npz) with full-fidelity ChainState reload — zero skipped values for the shipped chain (test-enforced), provenance frozen at save time, decode restricted to `radiant.*` classes (no pickle). Supporting surface: `ParameterSet.inputs()`, `save_config(scope=)`, `read_radiant_meta()`. 47 tests incl. `tests/integration/test_persistence_roundtrip.py`. |
| **Impact** | GUI File menu, session restore, and cross-session run comparison now have a backend. Residual scope: `SweepResult`/`MonteCarloResult` container save/load (per-run ChainResults are saveable individually; a sweep container format can ride the GUI phase that needs it). |
| **Rerun after fix** | None — new capability; scenario scripts unaffected. |

## Gap 68: Non-scalar chain inputs unreachable from Sensor/YAML; schema advertises modes that always raise

| Field | Value |
|-------|-------|
| **Found in** | Capability audit 2026-07 (F-02), 2026-07-11 |
| **Status** | FIXED (2026-07-11, commit `5d338d9`) — interim seam per plan; full YAML config-surface routes remain future work |
| **Description** | Element lists, Zernike/OPD wavefronts, pupil masks, and spectral injections required direct `RadiantSession.run(extra_stage_outputs=...)`; no `Sensor` method passed it. Schema-selectable modes raised unconditionally: optics transmission `spectral_file`/`telescope_plus_filters`/`key_elements`, stray-light `spectral_file`/`pst_file`, WFE `opd_map`. |
| **Fix** | `Sensor.set_stage_output(group, key, value)` (held injections, used by evaluate + all five trade studies) and `Sensor.evaluate(extra_stage_outputs=)` (one-off). Optics stage wired to consume `optics_config` injections for transmission modes 2–4 and stray `spectral_file`, with grid resampling and actionable route-naming errors. Always-raising modes un-advertised via enum_values: `opd_map` and `pst_file` removed; remaining modes validated. Docs: `RADIANT_Optics.md` §5/§8/§10, Scripting_API §2.2. |
| **Impact** | Optical-designer workflows (element trains, Zernike WFE, measured curves) now reach the chain through `Sensor`; schema-generated dropdowns no longer offer modes that error. Residual: YAML cannot express these objects — a config-surface route (file-path parameters + loaders) is GUI-phase work if needed. |
| **Rerun after fix** | Scenarios 5.x can migrate from `RadiantSession.run(extra_stage_outputs=...)` to the `Sensor` seam opportunistically; results identical (no rerun required). |

## Gap 69: Bundled reference libraries not selectable from config (detector.qe_material, source.target.material)

| Field | Value |
|-------|-------|
| **Found in** | Capability audit 2026-07 (F-08), 2026-07-11 |
| **Status** | OPEN |
| **Description** | `SpectralLibrary.detector_qe()` covers 6 materials but no `detector.qe_material` parameter exists (`api/session.py:_load_qe_curve` resolves only `qe_table_path`/`qe_value`); the 19-material emissivity library binds to `source.background.material` but there is no `source.target.material`. |
| **Impact** | The most natural GUI selections — detector-material and target-material dropdowns — have nothing to bind to; background/target panels are inconsistent. |
| **Workaround** | Export the library CSV and pass it as `qe_table_path` / `emissivity_path`. |

## Gap 70: No public parameter-schema introspection API

| Field | Value |
|-------|-------|
| **Found in** | Capability audit 2026-07 (F-03), 2026-07-11 |
| **Status** | FIXED (2026-07-11, commit `5a42649`) |
| **Description** | No public method enumerated ParameterDefs (dtype, bounds, enum values, units, defaults, descriptions, tags). Framework code itself read privates: `cli/schema_cmd.py:37` (`ps._defs`), `api/sensitivity.py:133`, `api/sweep.py:318` (`params._groups`). Related expandability holes: unit registry is a private pair table with no `register_unit()`/enumeration, and only one ConsistencyGroup (f/#) is registered though the resolver supports chains. |
| **Fix** | `ParameterSet` gained a public introspection surface: `parameter_defs()` (read-only mapping view), `parameter_def(name)` (alias-aware, did-you-mean KeyError), `consistency_groups()`, `tolerances()`, `is_resolved`, and `copy()` (the supported sweep/clone seam). `Sensor.parameter_defs()`/`parameter_def(dotpath)` passthroughs complete the GUI reachability chain. All five private consumers (`cli/schema_cmd`, `api/sensitivity`, `api/sweep`, `api/tolerance`, `api/sensor`) migrated in the same commit. Docs: `RADIANT_Parameter_System.md` §Schema Introspection; `RADIANT_Scripting_API.md` §2.2 + Appendix A. 16 new tests. The unit-registry `register_unit()`/enumeration and additional ConsistencyGroups remain planned work (audit F-09 disposition — not part of this gap's closure). |
| **Impact** | GUI parameter panels, unit dropdowns, bounds-aware widgets, and tooltips now bind to a stable public surface. |
| **Rerun after fix** | None — no scenario blocked on this; GUI work consumes it going forward. |

## Gap 71: result.metrics carries no units or metadata; no uniform metric contract

| Field | Value |
|-------|-------|
| **Found in** | Capability audit 2026-07 (F-04), 2026-07-11 |
| **Status** | FIXED (2026-07-11, commit `68e1fec`) — full MetricResult (regime/derivation_chain/inputs_used) remains a design target, banner in `RADIANT_Metrics.md` §2 |
| **Description** | `ChainResult.metrics` was a bare `Mapping[str, float]`; units lived only in some key suffixes; some entries are enums/booleans encoded as floats with nothing marking them. |
| **Fix** | Metric registry reconciled (CU-078, same commit) and made the single metadata source: every computed key has a `MetricSpec` with non-empty unit, description, and kind (float/flag/code). `ChainResult.metric_records()` returns unit-labelled `MetricRecord` tuples; `radiant.performance.metric_info(name)` for single lookups. Drift is CI-enforced (`tests/integration/test_metric_registry_reconciliation.py`): unregistered computed keys and can_compute contradictions fail. |
| **Impact** | GUI tables/plots/tooltips bind to registry metadata; no hand-maintained units map. Scenario scripts can migrate opportunistically. |
| **Rerun after fix** | None — additive surface; existing outputs unchanged. |

## Gap 72: No progress or cancellation hooks on long-running operations

| Field | Value |
|-------|-------|
| **Found in** | Capability audit 2026-07 (F-05), 2026-07-11 |
| **Status** | FIXED (2026-07-11, commit `537a3a8`) — per-stage timing seam on `ChainRunner.run` not included (single runs are 0.22 s; add if a GUI stage-strip spinner ever needs it) |
| **Description** | `sweep`, `sweep_2d`, `monte_carlo`, `sensitivity`, and `BatchRunner.run` were opaque blocking calls — no callback or cancel token anywhere in `api/`. |
| **Fix** | `progress(done, total)` and `cancel() -> bool` keyword arguments on all five operations (API functions + `Sensor` wrappers + `BatchRunner.run`); cancellation raises `radiant.api.OperationCancelledError` (a `RadiantError` carrying operation/done/total, no partial result). Plumbing in `api/_progress.py`. `solve_for` excluded (Brent iteration count unpredictable). Docs: Scripting_API §2.3. |
| **Impact** | GUI progress bars, cancel buttons, and Lisa 4.1's live progress grid have their seam. |
| **Rerun after fix** | None — additive surface. |

## Gap 73: Point-source regime silently zeroes background and path photon noise

| Field | Value |
|-------|-------|
| **Found in** | Capability audit 2026-07 (F-10), 2026-07-11 |
| **Status** | FIXED (2026-07-11, commit `2d06ca4`) |
| **Description** | The POINT_SOURCE branch hardcoded `background_e = 0.0` even when an at-aperture background frame existed — no background shot noise, no well fill from the sky pedestal. |
| **Fix** | For POINT_SOURCE with a background frame, `background_e` is now the full-pixel pedestal (Ω_pixel), computed by the shared `_background_pedestal_e` helper (Rule 19) — the same formula as the extended/sub-pixel background reference. It feeds background shot noise (detector) and the readout well-fill (regime-gated: added to the well only in point-source, since extended/sub-pixel carry the background inside `signal_e`). Target signal and `contrast_e = signal_e` unchanged; noise budget now continuous across the sub-pixel→point-source boundary. Signal-chain doc §4 updated. The "strips L_path" note in the original description was a correct target-signal behavior, not a defect — path radiance fills Ω_pixel via the pedestal, not the target's Ω_target term. |
| **Impact** | Point-target SNR/detection range against bright backgrounds is now realistic. Extended/sub-pixel and golden baseline unchanged. |
| **Rerun after fix** | Point-source scenarios against non-dark backgrounds (Chen 6.x if any) will show lower SNR — rerun opportunistically to confirm. |

## Gap 74: Scan/timing subsystem unimplemented (ScanMode, t_int derivation/feasibility, cross-track and target-motion smear)

| Field | Value |
|-------|-------|
| **Found in** | Capability audit 2026-07 (F-12), 2026-07-11 |
| **Status** | NARROWED (2026-07-11, commit `bdc5ca3`) — feasibility guard landed; full subsystem still deferred |
| **Description** | `RADIANT_Scan_Timing.md` (now banner-corrected to DESIGN TARGET) had zero code behind it: no ScanMode/TimingState, no t_int derivation from line/frame rate/dwell, no feasibility constraint (unphysical TDI timing accepted silently), and two of three documented smear sources (scan cross-track, target motion) have no ParameterDefs or kernels. |
| **Minimum slice landed** | The pushbroom/TDI dwell-time feasibility guard: `PerformanceStage` computes `t_dwell = GSD_along / v_ground` (`max_integration_time_s` metric) and warns when `integration_time_s` exceeds it (along-track smear > one ground sample — unphysical TDI timing). `radiant.performance.scan_feasibility`; parameter-gated on `platform.ground_velocity_m_s`. Closes the "SNR for unflyable timing looks authoritative" defect. |
| **Still deferred** | `ScanMode`/`TimingState` subsystem, t_int derivation from line/frame rate/dwell, cross-track scan smear and target-motion smear kernels + ParameterDefs — a chartered stand-alone task; the doc banner now marks the whole subsystem DESIGN TARGET. |
| **Impact** | Unflyable-timing SNR now warns loudly; full pushbroom/whiskbroom timing derivation and moving-target smear still hand-rolled. |
| **Workaround** | Hand-compute t_int and set `platform.smear_length_um` for along-track only; heed the new dwell-time warning. |

## Gap 75: Orbit/coverage kinematics unwired; duplicate ground-speed and altitude parameters

| Field | Value |
|-------|-------|
| **Found in** | Capability audit 2026-07 (F-13), 2026-07-11 |
| **Status** | NARROWED (2026-07-11, commit `6abef43`) — ground-speed collapsed + orbit velocity wired; altitude collapse deferred (CU-090) |
| **Description** | `core/orbit.py` ground-track speed was imported by nothing; ground velocity was never derived from altitude. Duplicate params could silently disagree: `platform.ground_velocity_m_s` vs `geometry.ground_speed_m_s`, and `platform.h_sensor` vs `geometry.sensor_altitude_m`. |
| **Landed** | `Sensor.set_ground_velocity_from_orbit()` wires `core/orbit.ground_track_speed_m_s` ("enter altitude, get velocity"). The ground-speed pair is now a collapsed identity consistency group (`_GROUND_SPEED_GROUP`): set either → both agree; set both to disagreeing values → over-specification error. |
| **Still deferred** | ~~The altitude duplicate~~ — **CU-090 RESOLVED 2026-07-12** (commit `f44c37a`): `platform.h_sensor` folded into `geometry.sensor_altitude_m` as a deprecated alias under ADR-0006. `core/repeat_ground_track.py` (revisit/sun-sync) remains unwired — coverage-metric surfacing is a GUI-phase feature. |
| **Impact** | "Enter altitude, get velocity" works and the two ground-speed fields can no longer silently disagree; altitude duplication and revisit/coverage kinematics remain. |
| **Workaround** | For the altitude pair, set both `sensor_altitude_m` and `h_sensor` to the same value until CU-090; call `core/orbit.py`/`repeat_ground_track.py` script-side for coverage. |

## Gap 76: Solar spectrum is a 5778 K blackbody only (no measured spectrum, no day-of-year)

| Field | Value |
|-------|-------|
| **Found in** | Capability audit 2026-07 (F-14), 2026-07-11 |
| **Status** | OPEN |
| **Description** | `core/solar.py` raises on any model other than `blackbody_5778`; the bundled AM0 CSV is itself a Planck fit (no Fraunhofer/molecular structure), validated only to ±5 % integrated TSI; no day-of-year/Earth-Sun distance variation though `core/solar_geometry.py` has the declination math and no `geometry.day_of_year` parameter exists. |
| **Impact** | 5-20 % band-dependent radiance error in narrow VNIR bands; seasonal studies inexpressible; solar spectral plots look visibly wrong to a radiometrist. |
| **Workaround** | None at the framework level. |

## Gap 77: No native SCNR metric and no in-chain detection-range solver

| Field | Value |
|-------|-------|
| **Found in** | Capability audit 2026-07 (F-15), 2026-07-11 — demanded independently by Sarah 1.1/1.3 and Lisa 4.1/4.2/4.3 |
| **Status** | NARROWED (2026-07-11, commit `133fa41`) — SCNR + constant-extinction detection range landed; geometry-aware slant-path refinement deferred |
| **Description** | `snr`/`contrast_snr` carried temporal (regime-dependent) noise only; the clutter-inclusive SCNR was assembled script-side. Detection range was never computed in-chain; only constant-extinction library helpers existed. |
| **Landed** | New `scnr` metric (`performance/scnr.py`) — contrast over the always-clutter-inclusive noise √(σ_temporal² + σ_spatial²). New `detection_range_m` metric — `PerformanceStage` bisects the Beer-Lambert solver in the point-source regime to `performance.detection_snr_threshold` (default 5.0), with constant extinction `α = −ln(τ̄)/R` (exact in vacuum). |
| **Still deferred** | The **geometry-aware** detection-range solve — α varying along a spherical-Earth slant path, τ_atm(R) recomputed per range — which matters for space targets whose path is mostly vacuum. The constant-α model is documented as a first-order approximation for atmospheric paths (`RADIANT_Metrics.md` §4.12). Effort M; category C. |
| **Impact** | SCNR and point-source detection range are now framework metrics; the geometry-aware range refinement for long slant paths remains a follow-up. |
| **Workaround** | For long-slant-path detection range, the script-side `detection_generic` callback solver still applies. |

## Gap 78: Decision-grade acquisition metrics are library-only (Pd/ROC, Johnson DRI, NEDL/NEDR/MRC, D*/NEP/NEI)

| Field | Value |
|-------|-------|
| **Found in** | Capability audit 2026-07 (F-15), 2026-07-11 |
| **Status** | OPEN — deferred to GUI-phase surfacing (2026-07-11 plan decision); SCNR + detection range split out and landed under Gap 77 |
| **Description** | `performance/roc.py`, `johnson_criteria.py`, `nedl.py`, `nedr.py`, `minimum_resolvable.py` (MRC branch), `detectivity.py`, `nep_*.py`, `noise_equivalent_irradiance.py`, `blip_rate.py`, `dark_crossover_rate.py`, `temperature_retrieval.py` are consumed only by tests and scenario scripts — never wired into PerformanceStage or `result.metrics`. No Pd-vs-range or contrast-limited DRI composition exists. **Deferral rationale**: each of these needs a study-specific input the chain does not carry (Pfa for Pd/ROC; target dimensions + a resolution criterion for Johnson DRI; scene reflectance for NEΔρ; an electrical bandwidth for D\*/NEP/NEI). Surfacing them well means defining those inputs — a natural GUI-phase task where the study parameters are entered — rather than guessing defaults now. The two members that DO have clean in-chain inputs (SCNR, point-source detection range) were split out and landed under Gap 77. |
| **Impact** | Analyst persona outputs (Pd at Pfa, DRI ranges, confidence-level ranges) and detector-trade numbers (BLIP T, crossover T, NEI) require re-derivation by every user; GUI has no reachable entry point. |
| **Workaround** | Import the library functions script-side (scenarios 4.x/6.x/2.x pattern). |

## Gap 79: No multi-config compare primitive; trade-study ergonomics are per-script boilerplate

| Field | Value |
|-------|-------|
| **Found in** | Capability audit 2026-07 (F-17), 2026-07-11 — demanded by Sarah 1.3, Raj 3.3, Lisa 4.1, Chen 6.1 |
| **Status** | OPEN |
| **Description** | No supported pattern for evaluating N sensor configs and diffing metrics as a table/compliance matrix; no sweep-level warning aggregation (~25 identical warnings across a 13×11 grid bury the one that matters); constrained two-axis sweeps (aperture×altitude at fixed GSD with focal length re-derived per point) are hand-rolled per scenario. |
| **Impact** | The dominant workflow shape for three personas is unsupported boilerplate; the GUI comparison table and matrix views have no backend primitive. |
| **Workaround** | Per-script config dicts + hand-built tables. |

## Gap 80: No multi-band / dual-band run concept

| Field | Value |
|-------|-------|
| **Found in** | Capability audit 2026-07 (F-16), 2026-07-11 |
| **Status** | OPEN |
| **Description** | Exactly one scalar `filter_min_um`/`filter_max_um` pair per run; no band-list structure anywhere in the API. Dual-band comparison (scenario 1.3) and band-set trades require externally orchestrated separate runs with hand-merged results. |
| **Impact** | GUI band-selector/dual-band comparison screens must implement N-run orchestration and result merging themselves; shared-scene consistency across bands is the caller's problem. |
| **Workaround** | Run per band and merge script-side (1.3 pattern). |

## Gap 81: MODTRAN sky terms not ingestable — downwelling thermal hard-zeroed, scattered solar zeroed

| Field | Value |
|-------|-------|
| **Found in** | Capability audit 2026-07 (F-19), re-verified 2026-07-11 against the landed MODTRAN rework (`d56fd9c`) — CU-086 re-audit |
| **Status** | NARROWED (2026-07-12, commit `17943ba`) — un-silenced with a warning; full `tape7_down_path` ingestion deferred on MODTRAN access |
| **Description** | `_build_state_from_arrays` constructs `atm_emission_down` as zeros, so `E_sky_thermal = π·ldown = 0` for every MODTRAN-backed run and `E_sky_scattered` is zeroed. There is no `tape7_down_path` to ingest a downwelling run. |
| **Landed** | `_build_state_from_arrays` now emits a `UserWarning` naming the zeroed downwelling/scatter sky terms and the deferred fix — switching `atmosphere.model` from `simple` to `modtran` no longer *silently* drops the thermal-band background (the "collapse warning does not mention it" defect). Test-covered. |
| **Still deferred** | The full ingestion — `atmosphere.modtran.tape7_down_path` mirroring the sun-leg import, plus the tape7 SOL SCAT column for `E_sky_scattered`. **Gating condition: MODTRAN access** — the import path has never run against a real binary and could only be validated synthetically (same gate as CU-011/065/070/087). Re-audit on MODTRAN access, alongside the first real run. Effort M; category C. |
| **Impact** | The downwelling reduction is now loud instead of silent; MODTRAN thermal-band background fidelity still requires the deferred ingestion. |
| **Workaround** | Use `atmosphere.model="simple"` for scenes where downwelling matters; heed the new warning. |

## Gap 82: No cloud, rain, or fog capability in any atmosphere model

| Field | Value |
|-------|-------|
| **Found in** | Capability audit 2026-07 (F-19), re-verified 2026-07-11 — CU-086 re-audit; independently demanded by Raj 3.2 (fog/cloud go/no-go below ~2 km visibility) |
| **Status** | OPEN |
| **Description** | `render_tape5` hardwires `ICLD=0`/`RAINRT=0.000`; no cloud-related ParameterDef exists in any `_schema.py`; SimpleAtmosphere's aerosol model bottoms out at heavy-haze visibility. `RADIANT_Atmosphere.md` §11's claim that v1 clouds are "off or MODTRAN's canned cloud model" overstates the shipped surface (CU-079 class). |
| **Impact** | Weather degradation is a first-class trade axis for EO sensor studies; a GUI scenario builder has no control to offer, and true fog/cloud go/no-go conditions are inexpressible. |
| **Workaround** | Treat heavy haze (low `visibility_km`) as the worst expressible weather. |

## Gap 83: No two-point geodetic geometry input (sensor lat/lon/alt + target lat/lon/alt)

| Field | Value |
|-------|-------|
| **Found in** | Geometry input-mode survey (`docs/plans/Geometry_Stage_Plan.md` §3, mode V5), 2026-07-12 |
| **Status** | OPEN |
| **Description** | The scene can only be defined sensor-relative (range, or altitude + an angle). Defining both endpoints geodetically — sensor lat/lon/alt and target lat/lon/alt, with range/zenith/azimuth derived from a spherical-Earth two-point solve — is the natural framing for airborne mission planning and site-specific studies, and would feed solar mode S3 (site latitude) for free. No solver exists in `core/`. |
| **Impact** | Users with waypoint- or site-based inputs must hand-convert to altitude+zenith outside RADIANT; a GUI map-pick workflow ("click sensor, click target") has no parameter surface to bind to. |
| **Workaround** | Convert lat/lon pairs to ground range and altitudes by hand (or script-side haversine), then use the altitude + ground-range mode (V3). |

## Gap 84: No time-based or orbital-ephemeris geometry (TLE/elements, trajectory time series, solar ephemeris)

| Field | Value |
|-------|-------|
| **Found in** | Geometry input-mode survey (`docs/plans/Geometry_Stage_Plan.md` §3, modes V7/V8/S4), 2026-07-12 |
| **Status** | OPEN |
| **Description** | Geometry is a single static snapshot. No path exists from orbital elements or a TLE + epoch to viewing geometry (V7 — needs a propagator; `RADIANT_Geometry_Orbital.md` scopes the theory but no code exists), from a platform trajectory time series to per-timestep geometry (V8 — pairs with the `SweepResult` machinery), or from an epoch + positions to an exact sun vector (S4). The circular-orbit shortcut (`core/orbit.py`, mode V6) and site+time solar (`core/solar_geometry.py`, mode S3) are the expressible ceiling. |
| **Impact** | Pass-geometry studies (access windows, grazing-to-nadir sweeps along a pass, terminator crossings) require external tooling (STK etc.) to generate per-point inputs; RADIANT cannot answer "what does this sensor see over this pass" natively. |
| **Workaround** | Propagate externally; feed each time step to RADIANT as a static V1/V2 geometry via `BatchRunner`. |

## Gap 85: No mission-type-driven parameter relevance (declared scenario type guiding parameter setup)

| Field | Value |
|-------|-------|
| **Found in** | Owner request, GUI Phase 3 checkpoint feedback, 2026-07-13 |
| **Status** | DEFERRED (post-v1; owner disposition 2026-07-13 "file for now, revisit after v1") |
| **Description** | RADIANT derives the radiometric regime (`RadiometricRegime`: `EXTENDED` / `SUB_PIXEL` / `POINT_SOURCE`) from the configured parameters — tentatively in `SourceStage`, finalized in `OpticsStage` (Rule 10). The owner wants the inverse workflow available to operators: declare the mission/scenario type up front and have the tool identify which parameters need setting and which are irrelevant for that declared type (e.g., an extended scene needs a background but not a target temperature, or vice versa for a point source). Landing this needs, in order: (a) per-regime parameter-relevance metadata authored on the stage `_schema.py` `ParameterDef`s — this does not exist today and is the load-bearing prerequisite; (b) an API surface exposing which parameters are relevant/irrelevant for a declared type; (c) GUI work: a scenario-type selector, relevance filtering/badging in the parameter tree, and a declared-vs-derived regime cross-check warning surfaced after evaluate. |
| **Impact** | Operators (all personas) have no setup guidance: they must know a priori which parameters matter for their mission type, and there is no guard that flags a declared extended-scene setup whose derived regime comes back point-source (or vice versa). The tool derives regime but never tells the user which knobs that regime actually consumes. |
| **Workaround** | Rely on operator knowledge of the regime rules; inspect the derived regime in results after a run and reconcile by hand. Natural v1.1 companion to the deferred library/preset browser (`RADIANT_GUI` arch doc §7.2 row 5). |

## Gap 86: `result.plot` exposes no spectral-radiance figure accessor (Source / Atmosphere / Spectral Integration default views)

| Field | Value |
|-------|-------|
| **Found in** | GUI Development Plan Phase 4 Task A (per-stage default visualizations), 2026-07-13 |
| **Status** | FIXED (2026-07-13, commit `f678dfd`) — three spectral accessors landed on `ResultPlotNamespace`; the GUI stage-view re-mapping (gap panel → `KIND_PLOT`) is the separate Phase 4B task. |
| **Description** | The public `result.plot` surface (`radiant.api.inspect.ResultPlotNamespace`) exposes exactly four figures — `mtf()`, `noise_budget()`, `psf()`, `mtf_budget()`. The arch-doc §4.4 per-stage default-visualization table names **spectral-domain radiance** figures for three stages that this surface does not carry: **Source** (`L_src(λ)` [W/m²/sr/µm]), **Atmosphere** (τ_atm(λ) with L_path(λ)/L_atm(λ) overlay), and **Spectral Integration** (in-band integrated radiance per frame). A module-level `radiant.api.plot.plot_spectral(wavelength_um, radiance, …)` function exists but is **not** wired onto the `result.plot` namespace and takes bare arrays, not a `ChainResult`, so the GUI cannot reach a stage's spectral radiance through the one-action-one-API-call surface. |
| **Impact** | The Source/Atmosphere/Spectral-Integration stage-strip buttons swap the canvas to a themed gap panel naming this gap instead of their intended spectral plot. No wrong figure is shown (the panel is honest), but three of nine stages lack their arch-doc default visualization until the accessor lands. Optics/Detector/Readout/Performance are unaffected — their §4.4 rows name figures (`mtf`, `noise_budget`) that `result.plot` already carries. |
| **Workaround** | Inspect spectral frames from the Phase-8 console via the module-level `radiant.api.plot.plot_spectral(...)` with arrays pulled from `result.frames` / `result.stage_outputs`. |
| **Fix location** | Add spectral accessors to `ResultPlotNamespace` (e.g. `spectral_source()`, `spectral_atmosphere()`, `spectral_inband()`) that pull the relevant frames/arrays off the `ChainResult` and delegate to the existing `plot_spectral`; then map those stages in `radiant.gui.stage_views.STAGE_VIEWS` from a gap view to a `KIND_PLOT` view. Effort S–M; category A (no physics, no results — a view accessor over already-computed frames). |
| **Resolution** | `f678dfd` (2026-07-13) added `spectral_source()` / `spectral_atmosphere()` / `spectral_inband()` to `ResultPlotNamespace`, plus `plot_spectral_multi` and `plot_atmosphere_spectral` in `radiant.api.plot`. Each plots only real stored frames / stage outputs (no recomputation) and raises `ApiValidationError` when the required frame is absent. Since SourceStage stores no radiance frame, `spectral_source()` plots the earliest stored radiance (`at_aperture_target` / `at_aperture`, + optional `at_aperture_background`); the §4.4 "at target" label is unattainable without recomputation and is documented as at-aperture in `RADIANT_Scripting_API.md` §5.2. The GUI `stage_views` re-mapping (gap panel → `KIND_PLOT`) is the separate GUI plan Phase 4B task. |

## Gap 87: `ChainResult` carries no public inspection/explanation convenience accessors (`result.inspect()`, `result.explain(term)`)

| Field | Value |
|-------|-------|
| **Found in** | GUI Development Plan Phase 4 Task B (Variables + Noise Budget detail tabs), 2026-07-13 |
| **Status** | OPEN — GUI works around it via public equivalents; no faked surface. |
| **Description** | Arch doc §4.5 names two `ChainResult` convenience accessors the detail tabs assume: **`result.inspect()`** (for the Variable Explorer tree) and **`result.explain(term)`** (a per-term noise explanation for the Noise Budget tab). Neither method exists on `ChainResult`. The public inspection surface is the module-level `radiant.api.inspect.inspect_result(result)`; there is **no** structured per-term noise-explanation accessor at all — the only per-term information is the `NoiseTerm` dataclass's own fields (`value_e`, `origin_frame`, `physical_basis`, `contributes_to`). |
| **Impact** | The GUI must reach for the module function rather than a `result.inspect()` method (a cosmetic ergonomics gap — one public call either way) and, for noise, must render the `NoiseTerm`'s stored metadata as an honest "describe" panel instead of a purpose-built explanation string (physical formula, dominant driver, referral factors). Per ground rule §4.1 the GUI does **not** invent physics text; it shows what the public surface carries. No wrong information is shown — only less than the arch-doc prose implies. |
| **Workaround** | Variable Explorer parses `inspect_result(result)`'s text into a tree (GUI plan Phase 4B); Noise Budget renders `describe_noise_term(term)` from the public `NoiseTerm` fields. |
| **Fix location** | Add `ChainResult.inspect(stage=None)` sugar delegating to `radiant.api.inspect.inspect_result`, and a structured per-term explanation accessor (e.g. `ChainResult.explain_noise(term_name) -> NoiseExplanation`) carrying the term's physics basis, referral factors, and contribution share. Effort S–M; category B (a new public accessor over already-computed values — no physics change). Update arch doc §4.5 and the GUI Noise/Variables tabs to consume it when it lands. |

## Gap 88: No in-memory / resolved-scope config serialize surface on the public API (only file-based `Sensor.save`, inputs scope)

| Field | Value |
|-------|-------|
| **Found in** | GUI Development Plan Phase 4 Task B (YAML detail tab), 2026-07-13 |
| **Status** | OPEN — GUI works around it via a temp-file round-trip; no faked surface. |
| **Description** | The public API's only config serialize surface is `Sensor.save(path)`, which writes to a **file** in the **inputs** scope (explicitly-set values plus a `_radiant` meta block; defaults and derived values are not written — they re-apply on load). There is no in-memory / string serialize (`Sensor.to_yaml() -> str`) and no public **resolved**-scope serialize (`radiant.io.config.save_config(..., scope="resolved")` exists but is not exposed on `Sensor`). |
| **Impact** | The YAML detail tab, which wants to *display* the current config as text, must save to a throwaway temp file and read it back (`serialize_yaml`). It can only show the **inputs** scope, so defaults and derived parameters do not appear as lines — a fully-resolved "everything the run used" export is unreachable from the GUI. The displayed text still round-trips through `Sensor.load` exactly (the contract the tab relies on). |
| **Workaround** | `radiant.gui.yaml_format.serialize_yaml(sensor)` saves to `tempfile.mkstemp` and reads the text back; the temp file is unlinked (a failed unlink is logged, not swallowed). |
| **Fix location** | Add `Sensor.to_yaml(scope="inputs"|"resolved") -> str` (a string serialize over `radiant.io.config`), then have `serialize_yaml` call it directly (no temp file) and offer a resolved-scope toggle in the YAML tab. Effort S; category B (public-surface addition, no physics/results change). |

## Gap 89: Optics complex-pupil diagnostics not exposed (pupil apodization/amplitude map + wavefront-error phase map)

| Field | Value |
|-------|-------|
| **Found in** | GUI Architecture redesign, Optics stage contextual view (arch doc §4.4.1), 2026-07-13 |
| **Status** | OPEN |
| **Description** | The owner-ratified Optics stage view asks for the **pupil apodization (amplitude) map** and the **pupil wavefront-error (phase) map**. `OpticsStage` **builds** the complex pupil internally each run — `make_pupil_amplitude(pupil_npix, obscuration, vanes, mask_override)` for the amplitude and `make_pupil_phase_for_wfe(...)` for the WFE phase (`src/radiant/optics/stage.py` `_compute_optical_mtf`) — but neither the amplitude array nor the phase array is **persisted** in `stage_outputs["optics"]` (only the derived `effective_psf`, `reference_psf`, `tau_opt*`, and scalar/aperture outputs are). The public `result.plot` surface (`ResultPlotNamespace`) has **no** pupil accessor (`psf`, `mtf`, `mtf_budget`, `noise_budget`, `spectral_*` only). Amplitude and phase are two faces of one complex pupil (Rule 4's single pupil root), so they are filed as one capability. |
| **Impact** | The Optics stage view cannot show the two most diagnostic optical figures — the apodization/obscuration mask (spider vanes, central obscuration, measured pupil override) and the aberration phase map (Zernike/WFE screen, defocus-as-Z4) — even though the chain computes both. A user debugging a WFE or obscuration budget (personas 5.1, 1.5) has no in-GUI view of the pupil that produced their PSF/MTF; only the downstream PSF is plottable. |
| **Workaround** | From the Phase-8 console, rebuild the pupil with the public optics helpers (`make_pupil_amplitude` / `make_pupil_phase_for_wfe`) at the run's parameters and image it by hand — a re-computation, not a view over stored state. |
| **Fix location** | Persist the complex pupil (or its amplitude and phase arrays, at the pupil sampling `pupil_npix`) in `stage_outputs["optics"]` (e.g. `pupil_amplitude`, `pupil_phase_waves`), then add `result.plot.pupil_amplitude()` / `pupil_phase()` accessors on `ResultPlotNamespace` delegating to a new `radiant.api.plot` imshow helper. Effort M; category A–B (a view/accessor over already-computed arrays — no physics, no results change). Update arch doc §4.4.1 when it lands. |

## Gap 90: Optics coating / element spectral performance not exposed as a figure (per-element R/T/ε + system throughput spectra)

| Field | Value |
|-------|-------|
| **Found in** | GUI Architecture redesign, Optics stage contextual view (arch doc §4.4.1), 2026-07-13 |
| **Status** | OPEN |
| **Description** | The Optics stage view asks for **coating performance and transmission spectra**. The data exists in `stage_outputs["optics"]`: `elements` is a `tuple[OpticalElement, ...]`, each carrying `transmittance`, `reflectance`, and (for lumped pseudo-elements) `declared_emissivity` as `SpectralData` (Kirchhoff-derived ε = 1 − R for mirrors, 1 − T − R for transmissive; `src/radiant/optics/element.py`), and `tau_opt_spectral` is the assembled **system throughput** `SpectralData`. But the public `result.plot` surface has **no** accessor to render per-element coating curves or the system-throughput spectrum — only the scalar `tau_opt` values feed downstream. |
| **Impact** | The Optics view cannot show how each coating/element contributes to (or limits) throughput across the band, nor the assembled system transmission curve — the natural companion to the MTF/PSF figures for an optics-train trade (per-element reflectance/transmission, cold-stop/emissivity contributions). The information is computed and stored but unreachable as a figure through the one-action-one-API-call surface. |
| **Workaround** | From the Phase-8 console, pull `result.stage_outputs["optics"]["elements"]` / `["tau_opt_spectral"]` and plot the `SpectralData` arrays by hand. |
| **Fix location** | Add `result.plot.optical_throughput()` (system `tau_opt_spectral`) and `result.plot.coating_spectra()` (per-element R/T/ε overlay) accessors on `ResultPlotNamespace`, delegating to `plot_spectral_multi` / a new twin-axis helper in `radiant.api.plot`. Effort S–M; category A (view accessor over stored `SpectralData` — no physics, no results change). Distinct capability from Gap 89 (pupil); update arch doc §4.4.1 when it lands. |

## Gap 91: No pre-atmosphere source-emission spectral frame (Source stage target/background radiance at the source)

| Field | Value |
|-------|-------|
| **Found in** | GUI Architecture redesign, Source stage contextual view (arch doc §4.4.1), 2026-07-13 |
| **Status** | OPEN |
| **Description** | The Source stage view asks for plots of **both target and background radiance** at the source — i.e. the emitted spectral radiance **before** atmosphere (the owner puts the *at-aperture* radiances under the Atmosphere stage, "now that atmosphere is applied"). `SourceStage` persists **descriptors** (`stage_outputs["source"]["target"]`, `["background"]`, ranges, tentative regime) but stores **no `RadiometricFrame`** — radiance assembly happens in `AtmosphereStage`, whose earliest stored radiance frames are `at_aperture_target` / `at_aperture_background` (post-atmosphere). The existing `result.plot.spectral_source()` therefore draws the **at-aperture** frames, not the source emission; its own docstring notes the "at target" label is unattainable without recomputation. There is no stored pre-atmosphere target/background emitted-radiance spectrum to plot. |
| **Impact** | The Source stage view cannot show the emitted target and background spectra on their own — the quantity that most directly reflects the *source* parameters (target/background temperature, emissivity, projected area) before the atmosphere modulates them. The GUI can only show the at-aperture result, which conflates source and atmosphere; separating "what the target emits" from "what reaches the aperture" (the owner's explicit Source-vs-Atmosphere split) is not possible with the stored frames. |
| **Workaround** | Show the at-aperture radiance (`spectral_source()`) in the Source view and label it as post-atmosphere; or, from the console, recompute the source Planck/emissivity radiance at the source parameters by hand. |
| **Fix location** | Have `SourceStage` (or the radiance-assembly step) persist a pre-atmosphere emitted-radiance frame for target and background (`at_source_target` / `at_source_background`, W/m²/sr/µm), then add a `result.plot.spectral_source_emission()` accessor. Effort M; category B–C (persisting an already-computed intermediate as a frame; verify no double-count with the at-aperture path). Update arch doc §4.4.1 and the Source default-view mapping when it lands. |

## Gap 92: No per-wavelength noise decomposition (noise terms are post-integration scalars)

| Field | Value |
|-------|-------|
| **Found in** | GUI Architecture redesign, Spectral Integration stage contextual view (arch doc §4.4.1), 2026-07-13 |
| **Status** | OPEN (runs against Rule 8's once-only spectral integration — a design question, not a defect) |
| **Description** | The Spectral Integration stage view asks for "final plots of **all** spectral radiances — signal **and** noise terms." The **signal** side exists (`result.plot.spectral_inband()` plots the post-optics integrand spectrum). The **noise** side does not exist as a spectrum: `NoiseTerm.value_e` is a **scalar** (electrons RMS) computed **after** spectral integration, per Rule 8 (spectral integration happens exactly once — before it, spectral arrays; after it, per-pixel scalars). There is no per-wavelength noise contribution stored anywhere, so noise cannot be plotted "as a spectrum" alongside the signal. |
| **Impact** | The Spectral Integration view can show the signal spectrum and the **scalar** noise budget (`result.plot.noise_budget()` bar / a GUI pie), but not a spectral (per-λ) decomposition of where noise accrues across the band — which is what the owner's "spectral … noise terms" phrasing implies. Whether this is wanted as a true capability or satisfied by pairing the signal spectrum with the scalar budget is an open design decision. |
| **Workaround** | Pair the signal spectrum (`spectral_inband()`) with the scalar noise budget (`noise_budget()`), presenting the two together in the stage view. |
| **Fix location** | If a true per-λ noise decomposition is wanted, add a pre-integration spectral noise accounting (per-λ shot/background/dark contributions) surfaced as a `result.plot.spectral_noise()` accessor — this is a genuine new capability that must be reconciled with Rule 8 (the collapse to scalars stays once-only; the per-λ arrays would be a diagnostic side-channel, not a second integration). Effort M–L; category C (new physics accounting). Confirm scope with the owner before building. |

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
| 40 | Lab dark-cal mode not first-class | Small | UC D-lab | FIXED |
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
| 55 | No PDF spec-sheet parser | Large | 3.3 | DECLINED |
| 56 | No multi-target spatial scene model (single-pixel only) | Large | 6.4 | DECLINED |
| 57 | standard_atmosphere preset sets emission temp only, not humidity | Small-Medium | 3.5 | FIXED |
| 58 | No GeoTIFF / raster reader for surface maps | Medium | 3.5 | DEFERRED |
| 59 | No solar-dependence (day/night) analysis mode | Medium | 3.5 | FIXED |
| 60 | Stray light is a scalar noise pedestal (no 2-D PSF, no MTF impact) | Medium-Large | 5.5 | PARTIAL — MTF halo landed 2026-07-10; PST import deferred (single-pixel) |
| 61 | Emissivity library has no wind-state ocean or rust-specific hull materials | Small-Medium | 1.1 | OPEN |
| 62 | No PowerPoint/slide-table export from scenario results | Small | 1.1 | OPEN |
| 63 | No libRadtran parser or implementation | Medium | 6.2 | OPEN |
| 64 | No spectral residual / per-band error-analysis tool | Small-Medium | 6.2 | OPEN |
| 65 | Full-well saturation is a recurring, silent failure mode | Small | 6.1, 6.2, 8.2 | FIXED 2026-07-11 |
| 66 | `detector.qe_table_path` unusable without a meaningless scalar `qe_value` | Small | 1.1, 1.2 | FIXED 2026-07-11 |
| 67 | No session/run persistence (save/load) | — | GUI File menu, session restore | FIXED 2026-07-11 |
| 68 | Non-scalar chain inputs unreachable from Sensor/YAML | — | 5.x | FIXED 2026-07-11 |
| 69 | Bundled libraries not selectable from config | Small | GUI material dropdowns | OPEN |
| 70 | No public parameter-schema introspection API | — | GUI | FIXED 2026-07-11 |
| 71 | result.metrics has no units/metadata | — | GUI | FIXED 2026-07-11 |
| 72 | No progress/cancellation hooks | — | GUI, 4.1 | FIXED 2026-07-11 |
| 73 | Point-source zeroes background/path photon noise | — | 6.x | FIXED 2026-07-11 |
| 74 | Scan/timing subsystem unimplemented | Large | pushbroom/TDI | NARROWED 2026-07-11 |
| 75 | Orbit/coverage kinematics unwired | Medium | 3.1 | NARROWED 2026-07-11 |
| 76 | Solar spectrum is 5778 K blackbody only | Medium | VNIR bands, seasonal | OPEN |
| 77 | No native SCNR / in-chain detection-range solver | Medium | 1.1, 1.3, 4.1–4.3 | NARROWED 2026-07-11 |
| 78 | Decision-grade acquisition metrics library-only | — | 4.x, 6.x, 2.x | OPEN |
| 79 | No multi-config compare primitive | — | 1.3, 3.3, 4.1, 6.1 | OPEN |
| 80 | No multi-band / dual-band run concept | — | 1.3 | OPEN |
| 81 | MODTRAN sky terms not ingestable (downwelling zeroed) | Medium | thermal-band scenes | NARROWED 2026-07-12 |
| 82 | No cloud/rain/fog capability | — | 3.2 | OPEN |
| 83 | No two-point geodetic geometry input | — | airborne mission planning (V5) | OPEN |
| 84 | No time-based / orbital-ephemeris geometry | — | pass-geometry (V7/V8/S4) | OPEN |
| 85 | No mission-type-driven parameter relevance (declared type → param setup guidance) | M–L | operator setup guidance (all personas) | DEFERRED (post-v1) |
| 86 | `result.plot` exposes no spectral-radiance figure accessor | S–M | Source/Atmosphere/Spectral-Integration GUI views | FIXED |
| 87 | `ChainResult` has no `inspect()` / `explain(term)` convenience accessors | S–M | GUI Variables + Noise Budget tabs | OPEN |
| 88 | No in-memory / resolved-scope config serialize surface (only file `Sensor.save`) | S | GUI YAML tab | OPEN |
| 89 | Optics complex-pupil diagnostics not exposed (apodization map + WFE phase map) | M | GUI Optics view (5.1, 1.5) | OPEN |
| 90 | Optics coating / element spectral performance not exposed as a figure | S–M | GUI Optics view | OPEN |
| 91 | No pre-atmosphere source-emission spectral frame (Source target/background radiance) | M | GUI Source view | OPEN |
| 92 | No per-wavelength noise decomposition (noise terms are post-integration scalars) | M–L | GUI Spectral-Integration view | OPEN |

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
