# Track C2 — Doc-vs-Code Drift: Optics / Spatial_Complete / Metrics / Parameter_System

Status: Complete
Produced by: read-only audit agent, 2026-07-22, against src/radiant at commit ed5e148.
Dispositions: see findings.md.

---

## Summary counts

| Doc | ENFORCED | TRUE-BUT-UNENFORCED | DRIFTED | UNVERIFIABLE |
|---|---|---|---|---|
| RADIANT_Optics.md | 7 | 4 | 3 (O1–O3) | 0 |
| RADIANT_Spatial_Complete.md | 7 | 3 | 6 (S1–S6) | 0 |
| RADIANT_Metrics.md | 11 | 2 | 2 (M1–M2) | 0 |
| RADIANT_Parameter_System.md | 7 | 4 | 3 (P1–P3) | 0 |
| **Total** | **32** | **13** | **14** | **0** |

(Claims verified end-to-end; parameter-table rows counted as one claim per table. Two doc-internal
inconsistencies found in passing, not counted as code drift: Spatial §9.2's "component count is 11,
not 12" note against its own 12-row table, and the Optics-vs-Spatial disagreement on the WFE
reference-wavelength default — Optics is correct.)

---

## DRIFTED findings (each verified against code twice)

**O1 — `optics.transmission_scalar` default.**
Doc (RADIANT_Optics.md §10.3 table): default `None` (mode 1). Code (`optics/_schema.py`,
TRANSMISSION_SCALAR): `default=0.7` ("typical end-to-end broadband throughput"). A user omitting
the parameter gets τ=0.7 silently, not a required-parameter error — changes what a config must
specify and what a default-provenance audit shows.

**O2 — `f_number` is not an optics stage output.**
Doc (§2 banner) lists `f_number` among `stage_outputs["optics"]` keys. Code: `optics/stage.py`
writes `A_collect`, `Omega_pixel` (ASCII), `tau_opt`, `tau_opt_spectral`, `effective_psf`,
`reference_psf`, `nearfield_irradiance_at_fpa`, `stray_light_irradiance_at_fpa`, `regime`, … —
no `f_number`. It lives only in the ParameterSet (fnumber consistency group).

**O3 — Ω cross-use "flagged by the type system" with names that don't exist.**
Doc (§9 rule 3) claims distinct names `omega_pixel_sr`/`omega_element_sr` and type-system
flagging. Neither identifier exists; actual names are `Omega_pixel` (stage output, plain float,
consumed in `spectral_integration/stage.py:61,152`) and `OpticalElement.nearfield_solid_angle_sr`
(`optics/element.py:271`). Both bare floats — no NewType/wrapper; separation is structural only.

**S1/S2 — Spatial §9.3 + §12 predate the CU-003 fix the same doc's §1.4 records.**
§9.3: "the rect kernel in `optics/pixel_kernel.py` is a binary mask … CU-003 tracks the planned
anti-aliased-rect fix"; §12 lists the anti-aliased kernel as out-of-scope for v1. Code
(`optics/pixel_kernel.py` docstring): "Sampling (CU-003, option a): each 1-D kernel sample
carries the exact area overlap … (anti-aliased edges)". Corroborated by
`performance/consistency_check.py` docstring and §1.4 of the same doc. Stale remnants
contradicting both the code and §1.4.

**S3 — RER: "averaged" vs geometric mean.**
Spatial §2 invariant 5 says RER is "averaged across the two axes". Code
(`optics/psf/effective.py::rer`): `sqrt(rer_x · rer_y)` — geometric mean (docstring says so);
RADIANT_Metrics.md §4.7 documents the geometric mean correctly. For anisotropic PSFs (smear)
arithmetic ≠ geometric mean — numerically wrong claim, not a wording nit.

**S4 — "Unconditional" consistency check is now conditionally gated.**
Spatial §0/§1.4/§5/§11 say the dual-path check is "unconditional — runs on every chain
execution". Code (`performance/stage.py`): the entire spatial pass including the check is
skipped when Gap-96 metric selection deselects the spatial group (owner-ratified comment at
stage.py:867-870), and additionally when `freq_mrad is None`, `mtf_terms` empty, or focal
length ≤ 0 (stage.py:225-231). The doc's own §9.3 carries the corrected Gap-96 wording —
§0/§1.4/§5/§11 were not updated in step (Rule-20 lock-step miss). CLAUDE.md Rule 4 carries the
corrected wording.

**S5 — `wfe_reference_wavelength_um` default.**
Spatial §10.1 table: default "(band-center)". Code (`optics/_schema.py`): `default=0.633`
(HeNe). Optics doc §10.2 has 0.633 correctly. Band-center vs 0.633 changes OPD scaling of any
nonzero `wfe_rms_waves`.

**S6 — `platform.h_sensor` is no longer a schema parameter.**
Spatial §10.2 lists it as shipped. Code: survives only as a deprecated alias of
`geometry.sensor_altitude_m` (`geometry/_schema.py:30-45`, folded per CU-090/ADR-0006).

**M1 — EE 5×5 and `ee_vs_offset` don't exist.**
Metrics §4.10 lists variants "1×1, 3×3, 5×5, and `ee_vs_offset(pitch)`". Code computes and
registers `ee_1x1`, `ee_3x3` only (`performance/stage.py:107-108`, registry). The doc's own §6
list is consistent with code — §4.10 was never trimmed.

**M2 — Clutter parameter namespace.**
Metrics §4.5 references `background.clutter_sigma`; actual parameter is
`detector.clutter_sigma` (`detector/_schema.py:307`). Parameter System doc has it right.

**P1 — Spectral-grid parameters don't exist.**
Param System doc claims grid parameters `spectral.lambda_min/lambda_max/n_points/grid_type`.
No `spectral.*` parameter exists in any `_schema.py`; the doc's own namespace list has nine
namespaces and `spectral` is not one. Actual grid: `spectral_integration.filter_min_um/max_um`
+ a `Sensor` constructor point count (`api/sensor.py:817-821`).

**P2 — Altitude duplicate "not yet collapsed" — it was.**
Doc says `geometry.sensor_altitude_m` vs `platform.h_sensor` is "not yet collapsed … see
CU-090". Code: folded as a deprecated alias per CU-090/ADR-0006 (`geometry/_schema.py:44`);
the doc's own naming section ~190 lines earlier records the fold correctly.

**P3 — Unimplemented API shown as working examples (no design-target banner).**
`result.explain("snr")` with noise budget + top-3 sensitivities: no `ChainResult.explain`
exists (real surfaces: `ChainResult.explain_noise(term)` at `io/results.py:227`,
`Sensor.explain(...)` at `api/sensor.py:782`). Persona rows show
`ParameterSet.sweep(...)`/`params.sensitivity(...)` — `ParameterSet` has neither method
(sweeps/sensitivity live on `Sensor`/`radiant.api`). Unlike Optics/Metrics, no banner.

---

## Top TRUE-BUT-UNENFORCED risks (ranked)

1. **The dual-path consistency invariant is warn-only in production.** A Rule-4 regression in a
   real run produces only a `logger.warning` and a stored result (`performance/stage.py:235-241`).
   No CI gate asserts `passed_x/passed_y` across the scenario-baseline set.
2. **Architecture-doc parameter tables have no freshness gate.** `gen_param_reference.py --check`
   guards `docs/reference`, not `docs/architecture`; this audit found three stale cells
   (O1, S5, S6) and nothing will catch the next one.
3. **`pupil_npix=128` / `psf_oversample=8` are load-bearing hard-coded literals**
   (`optics/sampling.py:83-84`); every spatial metric depends on them; only golden diffs would
   catch a silent change.
4. **Ω_pixel / Ω_element separation is structural, not typed** — both bare floats passed
   positionally; a cross-wire type-checks clean and surfaces only as wrong radiometry.
5. **Optics stage-output key names are stringly-typed contracts** hard-read downstream
   (`spectral_integration/stage.py:152`); nothing pins the names as a schema.
6. **Canonical convolution order and `convolution_history` content** implemented but untested;
   a reordering or dropped history entry passes silently.

---

## Full claim tables

### RADIANT_Optics.md

| Claim (section) | Classification | Evidence |
|---|---|---|
| Kirchhoff at construction; ε+T+R=1 ±1e-4; `declared_emissivity` only on LUMPED, else `KirchhoffViolationError` (§5.1, §6.1, §12) | ENFORCED | `optics/element.py:34,131-180`; `test_element.py`, `test_transmission_modes.py` |
| Spider params + pupil-mask entry into both spatial paths (§3.3) | ENFORCED | `optics/_schema.py`; `optics/aperture.py:49-60`; `test_spider_vanes.py` |
| Per-element Ω = π(D/2)²/d², clipped at 2π with logged warning (§7.3) | ENFORCED | `optics/element.py:271-286` |
| Veiling glare uses Ω_cone = A_collect/focal², not Ω_pixel (§8) | TRUE-BUT-UNENFORCED | `optics/stage.py:1080-1093`; no test pins the cone choice |
| `nearfield_fraction` default 1.0, alias `cold_stop_efficiency` deprecated (§7.4, §10.4) | ENFORCED | `optics/_schema.py` |
| TIS scatter params/formula/both-paths (§7.4b, §10.6) | ENFORCED | `optics/stage.py:997-1005`; `test_scatter.py` |
| Stray-light mode enum + defaults (§8, §10.5) | ENFORCED | `optics/_schema.py` |
| §10.1/§10.2 parameter tables | TRUE-BUT-UNENFORCED | Verified cell-by-cell; one drift (O1); no freshness gate |
| `transmission_scalar` default None (§10.3) | **DRIFTED (O1)** | Code default 0.7 |
| `f_number` in optics stage outputs (§2) | **DRIFTED (O2)** | Never written |
| `omega_pixel_sr`/`omega_element_sr` + type-system flagging (§9) | **DRIFTED (O3)** | Names don't exist; bare floats |
| DESIGN-TARGET banners (OpticsState, apodization, PupilDescription, …) | TRUE (correctly bannered) | Confirmed absent from code |
| Mode-1 lumped ε=0 default; scalar_emissivity ε+τ≤1 (§5.1) | ENFORCED | `optics/element.py:178-180,260` |
| `optics_distance_to_fpa_m` default "focal_length_m" (§10.3) | TRUE-BUT-UNENFORCED (wording) | Code: 0.0 sentinel meaning "use focal_length_m" |

### RADIANT_Spatial_Complete.md

| Claim (section) | Classification | Evidence |
|---|---|---|
| `EffectivePSF` fields + method surface (§2) | ENFORCED | `optics/psf/effective.py:25-39`; mypy strict; `test_psf.py` |
| `mtf_1d` ≡ slice of `mtf_2d`; single real-FFT convolve path (§2 inv. 1) | ENFORCED | `optics/psf/fft_convolve.py`; `test_fft_convolve.py` |
| `rer()` averaged across axes (§2 inv. 5) | **DRIFTED (S3)** | Code: geometric mean |
| Consistency check "unconditional" (§0, §1.4, §5, §11) | **DRIFTED (S4)** | Gap-96 gating in `performance/stage.py` |
| Tolerance 2e-2; `_EXCLUDED_PREFIXES=("mtf_tdi",)`; result fields; warn-don't-raise (§1.4, §9.3) | ENFORCED | `performance/consistency_check.py:23,26-35,42`; `test_consistency_check.py` |
| §9.3 "binary mask … CU-003 planned" | **DRIFTED (S1)** | Area-integrated since CU-003 |
| §12 anti-aliased kernel out of scope | **DRIFTED (S2)** | Implemented |
| Contributor MTF formulas (§9.2, §6) | ENFORCED | turbulence.py:57, diffusion.py:76, jitter.py:6, electronics_mtf.py:51, smear.py:29, ipc.py:72; per-module tests |
| Module-path claims (§1.2, §6, §9) | ENFORCED (existence) | All present |
| `pupil_npix=128`, `psf_oversample=8` hard-coded (§4, §10.1) | TRUE-BUT-UNENFORCED | `optics/sampling.py:83-84` |
| Zero-magnitude kernels logged `"name:zero"` (§6, §7) | ENFORCED | `optics/psf/builder.py:60,63,73` |
| §10.1 wfe_reference default "(band-center)" | **DRIFTED (S5)** | Schema: 0.633 |
| §10.2 `platform.h_sensor` shipped param | **DRIFTED (S6)** | Deprecated alias only |
| §10.2/§10.3 remaining rows | TRUE-BUT-UNENFORCED | All present with documented defaults |
| §9.2 "count is 11, not 12" note | Doc-internal staleness | Table itself lists 12 |

### RADIANT_Metrics.md

| Claim (section) | Classification | Evidence |
|---|---|---|
| `MetricRecord` in io/results; KeyError on registry drift (§2) | ENFORCED | `io/results.py:38,189-203`; `test_metric_registry_reconciliation.py` |
| §6 registered-key list matches PerformanceStage exactly | ENFORCED | `performance/registry.py:110-432` (33 names, one-for-one) |
| `MetricSpec` fields + introspection helpers (§6, §7) | ENFORCED | `performance/registry.py`; `test_registry.py` |
| §7a metric selection machinery | ENFORCED | `performance/_schema.py:43-116`, `metric_selection.py:36-137`, `api/metric_groups.py`; tests |
| NEDT via `ds_dt_e_per_K`; `compute_nedt_from_snr` fallback (§4.2) | ENFORCED | `spectral_integration/stage.py:397-399`, `performance/nedt.py:61,109` |
| GIQE-5 fit ranges + CU-166 strict-refusal + `allow_extrapolated` default False (§4.6) | ENFORCED | `performance/giqe.py:35-37,88,154-192`; `stage.py:736-757` |
| `strehl_marechal` formula (§4.11b) | ENFORCED | `performance/strehl.py:43-49` |
| PSF-derived strehl, same detector kernels both PSFs (§4.11) | ENFORCED | `performance/stage.py:116-122` |
| detection_range_m bisection, threshold default 5.0 (§4.12) | ENFORCED | `detection_beer_lambert.py`; `_schema.py:15-24` |
| Saturation margins + DR formulas (§4.13, §4.14) | ENFORCED | well_margin.py:39, adc_margin.py:39, dynamic_range.py:65 |
| EE variants incl. 5×5, ee_vs_offset (§4.10) | **DRIFTED (M1)** | Only ee_1x1/ee_3x3 exist |
| CSNR references `background.clutter_sigma` (§4.5) | **DRIFTED (M2)** | Actual: `detector.clutter_sigma` |
| NEΔL/NEΔρ/edge slope in "full v1 catalog" (§4.3, §4.4, §4.8) | TRUE-BUT-UNENFORCED (disclosed in §6, unbannered in §4) | nedl.py/nedr.py exist unwired (Gap 78) |
| §5 key map | TRUE (labeled illustrative) | Real keys confirmed |

### RADIANT_Parameter_System.md

| Claim (section) | Classification | Evidence |
|---|---|---|
| `ParameterDef` fields incl. `required_unless`, `is_file_path` | ENFORCED | `core/parameters.py:137-178`; mypy strict in CI |
| Unit-aware `set()`; %→fraction, min→s (Gap 6) | ENFORCED | `core/parameters.py:424-431`, `core/units.py:50-52` |
| Consistency groups `_FNUMBER_GROUP` (1e-3), `_GROUND_SPEED_GROUP` (1e-6) | ENFORCED | `api/_param_registry.py:22-79` verbatim |
| `required_unless` prose names one alternative | TRUE-BUT-UNENFORCED (understated) | Code: `"detector.qe_table_path,detector.qe_material"` (`detector/_schema.py:76`) |
| Alias list | ENFORCED (understated: 10 more shape-family aliases exist) | `optics/_schema.py:384`, `geometry/_schema.py:44,155` |
| Altitude duplicate "not yet collapsed … CU-090" | **DRIFTED (P2)** | Folded per CU-090/ADR-0006 |
| Spectral grid `spectral.*` parameters | **DRIFTED (P1)** | No such namespace/params |
| `result.explain("snr")` + ParameterSet.sweep/sensitivity examples | **DRIFTED (P3)** | Unimplemented, unbannered |
| Nine namespaces; naming rules | TRUE-BUT-UNENFORCED | All ~140 ParameterDefs conform; no automated lint |
| Defaults list (300 K/290 K/fill_factor 1.0/…) | TRUE-BUT-UNENFORCED | Verified; note `cds_enabled` shown as bool/True, real def int/1 |
| Introspection surface + read-only MappingProxy | ENFORCED | `core/parameters.py:779-849` |
| Tolerance/Provenance/ResolvedValue/explain surfaces | ENFORCED | `core/parameters.py:123,200,273,293,381,900-933` (explain() omits the doc's "Consistency group:" line) |
