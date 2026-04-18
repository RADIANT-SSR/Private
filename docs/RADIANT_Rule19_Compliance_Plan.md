# RADIANT Rule 19 Compliance Audit & Remediation Plan

**Date:** 2026-04-18 (updated 2026-04-18)  
**Status:** Phase 1 complete, Phase 2 complete, Phase 3 complete  
**Rule 19:** *"Each distinct physics calculation or metric gets its own file. Do not bundle unrelated computations into a single module just because they share a stage or a prompt."*  
**Exception:** *"Tightly coupled computations that share internal state or helper functions and would be meaningless apart."*

---

## Table of Contents

1. [Severity Classification](#1-severity-classification)
2. [Violation Register](#2-violation-register)
   - [Tier S1 — Hard Violations](#tier-s1--hard-violations-7-files)
   - [Tier S2 — Moderate Violations](#tier-s2--moderate-violations-10-files)
   - [Tier S3 — Borderline](#tier-s3--borderline-4-files)
3. [Special Analysis: psf.py vs Rule 4](#3-special-analysis-psfpy-vs-rule-4)
4. [Remediation Plan](#4-remediation-plan)
   - [Phase 1 — S1 Hard Violations](#phase-1-s1-hard-violations-7-prs)
   - [Phase 2 — S2 Moderate Violations](#phase-2-s2-moderate-violations-10-prs)
   - [Phase 3 — S3 Borderline + Cleanup](#phase-3-s3-borderline--cleanup-4-prs)
   - [Phase 4 — Folder Structure Restructuring](#phase-4-folder-structure-restructuring)
5. [Proposed Folder Structure](#5-proposed-folder-structure)
6. [Regression Testing Strategy](#6-regression-testing-strategy)
7. [Summary](#7-summary)

---

## 1. Severity Classification

| Tier | Definition | Risk |
|------|-----------|------|
| **S1 — Hard violation** | Multiple fully independent computations in one file; no shared internal state | Highest — developer cannot find a calculation by scanning file names |
| **S2 — Moderate violation** | Two independent computations bundled, or independent variants of the same concept that differ in physics | Medium — confusing but discoverable |
| **S3 — Borderline** | Multiple closely-related computations that share result types, validation, or internal helpers | Low — judgment call, but should still be separated for strict compliance |

---

## 2. Violation Register

**Total: 21 files violating Rule 19, bundling ~95 independent computations**

### Tier S1 — Hard Violations (7 files)

| # | File | Bundled Items | Why It Violates |
|---|------|--------------|-----------------|
| 1 | `src/radiant/detector/noise.py` | 16 independent noise source functions (`signal_shot_noise`, `background_shot_noise`, `nearfield_shot_noise`, `straylight_shot_noise`, `dark_shot_noise`, `gr_noise`, `johnson_noise`, `flicker_1f_noise`, `read_noise_func`, `ktc_reset_noise`, `quantization_noise`, `prnu_noise`, `dsnu_noise`, `clutter_noise`, `persistence_noise`, `glow_shot_noise`) | Each is a self-contained formula with no shared internal state. A developer looking for "johnson noise" must scan a 300+ line file |
| 2 | `src/radiant/optics/psf.py` | `PSFData` (raw PSF + MTF + EE + FWHM), `EffectivePSF` (MTF, EE, LSF, ERF, RER, FWHM, Strehl), `build_effective_psf` | PSFData and EffectivePSF are independent classes. The 8+ spatial metrics on EffectivePSF (mtf_2d, mtf_1d, ensquared_energy, lsf, erf, rer, fwhm, edge_slope, strehl) are each independent computations |
| 3 | `src/radiant/source/unified_target.py` | `ResolvedTarget` dataclass + 5 independent factory functions (`resolve_direct_radiance`, `resolve_geometry`, `resolve_sub_pixel`, `resolve_intensity`, `resolve_physical_object`) | Each factory is an independent input path with its own physics. They share the output type but not internal computation |
| 4 | `src/radiant/source/primitives.py` | 5 independent geometric shapes: `Sphere`, `FlatPlate`, `Box`, `Cylinder`, `Cone` | Each has its own projected-area formula. No shared state beyond a trivial validation helper |
| 5 | `src/radiant/readout/binning.py` | 8 independent scaling functions across two regimes (on-chip: 4, off-chip: 4) | On-chip and off-chip binning have different physics (single vs. multiple readouts). Independent computations bundled by proximity |
| 6 | `src/radiant/optics/transmission_modes.py` | 5 independent transmission resolution modes | Each mode is an independent code path with its own logic |
| 7 | `src/radiant/optics/filters.py` | 4 independent filter types (bandpass, longpass, shortpass, notch) + factory | Each filter type has its own transmission formula |

### Tier S2 — Moderate Violations (10 files)

| # | File | Bundled Items | Why It Violates |
|---|------|--------------|-----------------|
| 8 | `src/radiant/performance/nedt.py` | `compute_nedt` (from dS/dT), `compute_nedt_from_snr` (Planck approx), `compute_nedl` (L/SNR), `compute_nedr` (ρ/SNR) | NEDT, NEDL, NEDR are three distinct noise-equivalent metrics. Different physics, different inputs, different units |
| 9 | `src/radiant/performance/snr.py` | `compute_snr` (S/σ), `compute_contrast_snr` (ΔS/σ) | Different signal definitions, different use cases (absolute vs. detectability) |
| 10 | `src/radiant/performance/saturation_metrics.py` | `compute_well_margin`, `compute_adc_margin`, `compute_dynamic_range` | Three independent metrics sharing only a result dataclass |
| 11 | `src/radiant/performance/detection.py` | `detection_range_beer_lambert` (parametric), `detection_range_generic` (callback-based) | Two independent solver implementations |
| 12 | `src/radiant/readout/saturation.py` | `check_well_saturation`, `check_adc_saturation` | Two independent clip checks at different points in the signal chain |
| 13 | `src/radiant/readout/tdi.py` | TDI misalignment MTF (`tdi_misalign_mtf_1d`) + 4 TDI scaling functions (`tdi_scale_signal`, `tdi_scale_shot_noise`, `tdi_scale_read_noise`, `tdi_scale_fpn`) | MTF is a spatial metric; scaling is signal chain arithmetic. Unrelated |
| 14 | `src/radiant/source/background.py` | `BlackbodyBackground`, `TabulatedBackground`, `ConstantBackground` | Three independent source models with no shared state |
| 15 | `src/radiant/source/point_source.py` | `DirectIntensitySource`, `BlackbodyIntensitySource` | Two independent intensity source models |
| 16 | `src/radiant/source/brdf.py` | `LambertianBRDF`, `PhongBRDF` | Two independent scattering models with different physics |
| 17 | `src/radiant/optics/element_list.py` | System transmission chain + nearfield irradiance | Transmission and nearfield emission are independent calculations |

### Tier S3 — Borderline (4 files)

| # | File | Bundled Items | Notes |
|---|------|--------------|-------|
| 18 | `src/radiant/optics/diffraction.py` | `compute_psf_mono` + `compute_psf_polychromatic` | Polychromatic calls mono in a loop — genuine coupling. But these are two distinct algorithms (direct FFT vs. spectral-weighted sum). **Split recommended.** |
| 19 | `src/radiant/optics/wavefront.py` | `WavefrontError` with 4 modes (scalar, Zernike, OPD map, field-dependent) | Single class with multiple modes — borderline. Modes share the dataclass but compute differently. **Split recommended.** |
| 20 | `src/radiant/optics/stray_light.py` | 4 stray light input modes in one resolver | Similar pattern to wavefront — single config class dispatching to different physics. **Split recommended.** |
| 21 | `src/radiant/optics/element.py` | `OpticalElement` class + `CavityModel` + 4 factory functions | CavityModel is genuinely coupled to OpticalElement (it provides eps_eff). The factories are convenience constructors. **Borderline — CavityModel could be separate.** |

---

## 3. Special Analysis: psf.py vs Rule 4

The worst violation is `src/radiant/optics/psf.py`. It bundles:
- PSF container (`PSFData`)
- Effective PSF with all spatial metrics (`EffectivePSF`)
- PSF builder (`build_effective_psf`)

This means a developer searching for "how is RER computed" must scan 550 lines. A developer searching for "where is the LSF" must know it's a method on `EffectivePSF`, not in a file called `lsf.py`. This directly contradicts Rule 19's intent: *"A developer should be able to find a calculation by scanning file names."*

**However**, Rule 4 says *"EffectivePSF Is the Single Source of Truth for Spatial Metrics."* Splitting the spatial metric methods into separate files while keeping them as methods on `EffectivePSF` would require either:

- **(a) Mixin classes** — adds abstraction complexity
- **(b) Standalone functions** that take `EffectivePSF` as input — cleaner, recommended

**Recommendation: Option (b).** Spatial metrics become standalone functions taking `EffectivePSF` as first argument, not methods. `EffectivePSF` keeps only data fields + `with_kernel`. This preserves Rule 4 (all metrics derive from the same PSF data) while achieving Rule 19 compliance.

---

## 4. Remediation Plan

### Guiding Principles

1. **One file split per PR** — each split is an atomic, reviewable change
2. **Regression first** — run the full test suite before and after every split
3. **No physics changes** — only structural moves; no algorithm modifications
4. **Import compatibility** — all existing `from radiant.xxx import yyy` must continue to work via re-exports during transition, then cleaned up in a follow-up PR
5. **Prioritize S1 first** — highest impact, clearest violations

---

### Phase 1: S1 Hard Violations (7 PRs)

#### PR 1.1 — Split `detector/noise.py` → 5 family files

**Current:** 16 noise functions in one file  
**Target structure:**
```
detector/
├── noise_photon.py        # signal_shot, background_shot, nearfield_shot, straylight_shot
├── noise_detector.py      # dark_shot, gr_noise, johnson_noise, flicker_1f
├── noise_roic.py          # read_noise, ktc_reset, quantization
├── noise_fixed_pattern.py # prnu, dsnu, clutter
├── noise_other.py         # persistence, glow_shot
└── noise.py               # Re-exports only (backward compat), remove after Phase 3
```
**Regression:** `pytest src/radiant/detector/tests/ -v` + `pytest tests/integration/ -v`  
**Risk:** Low — pure functions, no shared state

---

#### PR 1.2 — Split `optics/psf.py` → 4 files

**Current:** PSFData + EffectivePSF (with 8 metrics) + builder  
**Target structure:**
```
optics/
├── psf_data.py            # PSFData container (raw optical PSF)
├── effective_psf.py       # EffectivePSF dataclass + with_kernel (keeps Rule 4)
├── spatial_metrics.py     # Free functions: mtf_2d(psf), mtf_1d(psf), ensquared_energy(psf),
│                          # lsf(psf), erf(psf), rer(psf), fwhm(psf), edge_slope(psf), strehl(psf)
├── psf_builder.py         # build_effective_psf()
└── psf.py                 # Re-exports only
```
**Key decision:** Spatial metrics become standalone functions taking `EffectivePSF` as first arg, not methods. `EffectivePSF` keeps only data fields + `with_kernel`. This preserves Rule 4 (single PSF source) while achieving Rule 19 (one calc per file).  
**Alternative:** If the team prefers methods, use a mixin pattern with one mixin per file. Less clean but keeps the method API.  
**Regression:** `pytest src/radiant/optics/tests/test_psf.py -v` + all integration tests  
**Risk:** Medium — widely referenced class; API surface may need updating

---

#### PR 1.3 — Split `source/unified_target.py` → 6 files

**Current:** ResolvedTarget + 5 factory functions  
**Target structure:**
```
source/
├── resolved_target.py       # ResolvedTarget dataclass only
├── resolve_direct.py        # resolve_direct_radiance()
├── resolve_geometry.py      # resolve_geometry()
├── resolve_sub_pixel.py     # resolve_sub_pixel()
├── resolve_intensity.py     # resolve_intensity()
├── resolve_physical.py      # resolve_physical_object()
└── unified_target.py        # Re-exports only
```
**Regression:** `pytest src/radiant/source/tests/test_unified_target.py -v` + integration  
**Risk:** Low — factories are independent

---

#### PR 1.4 — Split `source/primitives.py` → 5 files + subdirectory

**Current:** 5 shapes in one file  
**Target structure:**
```
source/shapes/
├── __init__.py          # Re-exports all shapes
├── _helpers.py          # _validate_positive, _view_to_body
├── sphere.py
├── flat_plate.py
├── box.py
├── cylinder.py
└── cone.py
```
**Regression:** `pytest src/radiant/source/tests/test_primitives.py -v`  
**Risk:** Low

---

#### PR 1.5 — Split `readout/binning.py` → 2 files

**Current:** On-chip + off-chip scaling bundled  
**Target structure:**
```
readout/
├── binning_onchip.py    # 4 on-chip scaling functions
├── binning_offchip.py   # 4 off-chip scaling functions
└── binning.py           # Re-exports only
```
**Regression:** `pytest src/radiant/readout/tests/test_binning.py -v`  
**Risk:** Low

---

#### PR 1.6 — Split `optics/transmission_modes.py` → per-mode files

**Target structure:**
```
optics/
├── transmission_scalar.py
├── transmission_file.py
├── transmission_telescope.py
├── transmission_key_elements.py
├── transmission_full_prescription.py
├── transmission_modes.py    # Re-exports + dispatcher only
```
**Regression:** `pytest src/radiant/optics/tests/test_transmission_modes.py -v`  
**Risk:** Low

---

#### PR 1.7 — Split `optics/filters.py` → per-filter files

**Target structure:**
```
optics/
├── filter_bandpass.py
├── filter_longpass.py
├── filter_shortpass.py
├── filter_notch.py
├── filters.py              # Re-exports + factory
```
**Regression:** `pytest src/radiant/optics/tests/test_filters.py -v`  
**Risk:** Low

---

### Phase 2: S2 Moderate Violations (10 PRs)

| PR | Current File | Split To | Regression Scope |
|----|-------------|----------|-----------------|
| 2.1 | `performance/nedt.py` | `nedt.py`, `nedl.py`, `nedr.py` | `test_nedt.py` + integration |
| 2.2 | `performance/snr.py` | `snr.py`, `contrast_snr.py` | `test_snr.py` + integration |
| 2.3 | `performance/saturation_metrics.py` | `well_margin.py`, `adc_margin.py`, `dynamic_range.py` | `test_saturation_metrics.py` + integration |
| 2.4 | `performance/detection.py` | `detection_beer_lambert.py`, `detection_generic.py` | `test_detection.py` + integration |
| 2.5 | `readout/saturation.py` | `well_saturation.py`, `adc_saturation.py` | `test_saturation.py` + integration |
| 2.6 | `readout/tdi.py` | `tdi_mtf.py` (misalignment MTF), `tdi_scaling.py` (signal/noise) | `test_tdi.py` + integration |
| 2.7 | `source/background.py` | `background_blackbody.py`, `background_tabulated.py`, `background_constant.py` | `test_background.py` + integration |
| 2.8 | `source/point_source.py` | `point_source_direct.py`, `point_source_blackbody.py` | `test_point_source.py` + integration |
| 2.9 | `source/brdf.py` | `brdf_lambertian.py`, `brdf_phong.py` | `test_brdf.py` + integration |
| 2.10 | `optics/element_list.py` | `system_transmission.py`, `nearfield_irradiance.py` | `test_element_list.py` + integration |

Each PR: split → re-export from old module → run stage tests + integration tests.

---

### Phase 3: S3 Borderline + Cleanup (4 PRs)

| PR | File | Action |
|----|------|--------|
| 3.1 | `optics/diffraction.py` | Split `compute_psf_mono` → `diffraction_mono.py`, `compute_psf_polychromatic` → `diffraction_poly.py` |
| 3.2 | `optics/wavefront.py` | Extract `FieldWfeSample` → `field_wfe.py`, keep scalar/Zernike in `wavefront.py` |
| 3.3 | `optics/stray_light.py` | Extract mode-specific resolvers if they grow beyond current size |
| 3.4 | **Remove all re-export shims** from Phase 1–2 old files. Update all imports project-wide. |

---

### Phase 4: Folder Structure Restructuring

After all splits are landed, reorganize into subdirectories where a stage now has >8 files. See [Section 5](#5-proposed-folder-structure) for the full layout.

---

## 5. Proposed Folder Structure

After full remediation, the recommended layout groups related-but-independent computations into subdirectories. Each file within a subdirectory is one computation. The subdirectory name answers "what family?" while the file name answers "which specific one?"

```
src/radiant/
├── source/
│   ├── shapes/              # Geometric primitives (from primitives.py)
│   │   ├── __init__.py
│   │   ├── _helpers.py      # _validate_positive, _view_to_body
│   │   ├── sphere.py
│   │   ├── flat_plate.py
│   │   ├── box.py
│   │   ├── cylinder.py
│   │   └── cone.py
│   ├── backgrounds/         # Background models (from background.py)
│   │   ├── __init__.py
│   │   ├── blackbody.py
│   │   ├── tabulated.py
│   │   └── constant.py
│   ├── resolvers/           # Target input paths (from unified_target.py)
│   │   ├── __init__.py
│   │   ├── direct.py
│   │   ├── geometry.py
│   │   ├── sub_pixel.py
│   │   ├── intensity.py
│   │   └── physical_object.py
│   ├── resolved_target.py   # ResolvedTarget dataclass only
│   ├── emitted.py
│   ├── reflected.py
│   ├── combined.py
│   ├── material.py
│   ├── solar.py
│   ├── brdf_lambertian.py
│   ├── brdf_phong.py
│   ├── point_source_direct.py
│   ├── point_source_blackbody.py
│   ├── sub_pixel.py
│   ├── tabulated.py
│   ├── protocol.py
│   ├── stage.py
│   └── _schema.py
│
├── optics/
│   ├── psf/                 # PSF family (from psf.py)
│   │   ├── __init__.py
│   │   ├── data.py          # PSFData
│   │   ├── effective.py     # EffectivePSF (data + with_kernel only)
│   │   ├── metrics.py       # Standalone spatial metric functions
│   │   └── builder.py       # build_effective_psf()
│   ├── transmission/        # Transmission modes (from transmission_modes.py)
│   │   ├── __init__.py
│   │   ├── scalar.py
│   │   ├── file.py
│   │   ├── telescope.py
│   │   ├── key_elements.py
│   │   └── full_prescription.py
│   ├── filters/             # Filter types (from filters.py)
│   │   ├── __init__.py
│   │   ├── bandpass.py
│   │   ├── longpass.py
│   │   ├── shortpass.py
│   │   └── notch.py
│   ├── aperture.py
│   ├── element.py
│   ├── system_transmission.py    # from element_list.py
│   ├── nearfield_irradiance.py   # from element_list.py
│   ├── diffraction_mono.py
│   ├── diffraction_poly.py
│   ├── wavefront.py
│   ├── field_wfe.py
│   ├── zernike.py
│   ├── defocus.py
│   ├── stray_light.py
│   ├── ee_box.py
│   ├── sampling.py
│   ├── stage.py
│   └── _schema.py
│
├── detector/
│   ├── noise/               # 16 noise sources (from noise.py)
│   │   ├── __init__.py      # Re-exports all + NoiseBudget
│   │   ├── photon.py        # signal_shot, background_shot, nearfield_shot, straylight_shot
│   │   ├── detector_material.py  # dark_shot, gr_noise, johnson_noise, flicker_1f
│   │   ├── roic.py          # read_noise, ktc_reset, quantization
│   │   ├── fixed_pattern.py # prnu, dsnu, clutter
│   │   └── other.py         # persistence, glow_shot
│   ├── dark_current.py
│   ├── qe.py
│   ├── shot_noise.py
│   ├── ipc.py
│   ├── diffusion.py
│   ├── pixel.py
│   ├── stage.py
│   └── _schema.py
│
├── readout/
│   ├── tdi_mtf.py           # TDI misalignment MTF (spatial concern)
│   ├── tdi_scaling.py       # TDI signal/noise scaling (readout arithmetic)
│   ├── binning_onchip.py
│   ├── binning_offchip.py
│   ├── well_saturation.py
│   ├── adc_saturation.py
│   ├── adc.py
│   ├── read_noise.py
│   ├── coadds.py
│   ├── stage.py
│   └── _schema.py
│
├── performance/
│   ├── snr.py
│   ├── contrast_snr.py
│   ├── nedt.py
│   ├── nedl.py
│   ├── nedr.py
│   ├── well_margin.py
│   ├── adc_margin.py
│   ├── dynamic_range.py
│   ├── detection_beer_lambert.py
│   ├── detection_generic.py
│   ├── niirs.py
│   ├── giqe.py
│   ├── gsd.py
│   ├── strehl.py
│   ├── folded_mtf.py
│   ├── system_mtf.py
│   ├── qsample.py
│   ├── access_rate.py
│   ├── ground_range.py
│   ├── swath_width.py
│   ├── registry.py
│   ├── stage.py
│   └── _schema.py
│
├── platform/                # NO VIOLATIONS — no changes needed
│   ├── jitter.py
│   ├── smear.py
│   ├── sampling.py
│   ├── geometry.py
│   ├── stage.py
│   └── _schema.py
│
├── atmosphere/              # NO VIOLATIONS — no changes needed
│   ├── simple.py
│   ├── exo.py
│   ├── tabulated.py
│   ├── modtran.py
│   ├── interpolated.py
│   ├── turbulence.py
│   ├── protocol.py
│   ├── stage.py
│   └── _schema.py
│
├── spectral_integration/    # NO VIOLATIONS — no changes needed
│   ├── stage.py
│   └── _schema.py
│
├── core/                    # NOT AUDITED (no physics — Rule 19 applies to physics modules)
├── io/
├── api/
├── cli/
└── plugins/
```

**Key structural changes:**
- **Subdirectories** (`shapes/`, `psf/`, `noise/`, `transmission/`, `filters/`, `backgrounds/`, `resolvers/`) group related-but-independent computations
- Each file within a subdirectory is one computation
- `__init__.py` in each subdirectory re-exports all public symbols so imports remain clean (e.g., `from radiant.optics.psf import EffectivePSF`)
- Test files should mirror the source structure (e.g., `source/shapes/tests/test_sphere.py`)

---

## 6. Regression Testing Strategy

### Existing Test Coverage

- **Unit tests:** 97 files across all physics stages
- **Integration tests:** 7 files in `tests/integration/` (chain, spatial, full system, ground truth, regime continuity, golden regression)
- **Golden data:** `tests/integration/golden/` and `tests/integration/fixtures/`

### Before Any Split — Capture Baseline

```bash
# Baseline pass/fail counts
pytest -v --tb=short 2>&1 | tee baseline_results.txt

# Baseline coverage
pytest --cov=radiant --cov-report=term-missing 2>&1 | tee baseline_coverage.txt

# Baseline type check
mypy --strict src/radiant/core src/radiant/api 2>&1 | tee baseline_mypy.txt

# Baseline import rules
import-linter --config pyproject.toml 2>&1 | tee baseline_imports.txt
```

### Per-PR Regression Protocol

For every single PR in Phases 1–3:

1. **Pre-split:** `pytest -v` — record pass count (expect 0 failures)
2. **Split files** — move code, add re-exports in old module
3. **Post-split with re-exports:** `pytest -v` — must match pre-split exactly (zero new failures)
4. **Import audit:** `ruff check src/` — no new lint errors
5. **Type check:** `mypy --strict src/radiant/core src/radiant/api` — must pass
6. **Import rules:** `import-linter --config pyproject.toml` — must pass
7. **Coverage check:** `pytest --cov=radiant` — delta ≤ 0.1% from baseline

### Phase 3.4 — Final Cleanup Regression

After all re-export shims are removed:

1. **Grep for old imports:** `grep -r "from radiant.detector.noise import" src/` — update all to new paths
2. **Remove re-export files** (or reduce to `__init__.py` in subdirectories)
3. **Final regression:** full test suite + coverage comparison against baseline
4. **Coverage delta:** must be ≤ 0.1% — no coverage loss from structural changes
5. **Golden test verification:** all golden values identical to baseline

---

## 7. Summary

| Category | Files | Bundled Computations | PRs Required |
|----------|-------|---------------------|--------------|
| S1 Hard | 7 | ~60 | 7 |
| S2 Moderate | 10 | ~25 | 10 |
| S3 Borderline | 4 | ~10 | 4 |
| **Total** | **21** | **~95** | **21** |

### Highest-Priority Splits

The three most impactful splits (resolving ~30 bundled computations — a third of all violations):

1. **`detector/noise.py`** — 16 independent formulas, easiest win
2. **`optics/psf.py`** — Rule 4 vs Rule 19 tension must be resolved explicitly
3. **`source/unified_target.py`** — 5 independent factory functions

### Stages With No Violations

These stages are already Rule 19 compliant:
- `platform/` — clean one-computation-per-file layout
- `atmosphere/` — clean one-model-per-file layout
- `spectral_integration/` — single stage file

### Files Not Audited

- `core/` — foundational abstractions, not physics modules (Rule 19 applies to physics)
- `io/`, `api/`, `cli/`, `plugins/` — infrastructure, not physics

---

## 8. Baseline Test Results

Captured 2026-04-18 before any structural changes.

```
Total:   2011 tests
Passed:  2007
Failed:  4 (pre-existing golden/ground-truth drift — NOT caused by this work)
```

Pre-existing failures (do not count against regression):
- `tests/integration/test_chain_spatial.py::TestSNRUnchanged::test_snr_value_matches_golden`
- `tests/integration/test_golden_mwir_leo_minimal.py::TestGoldenMWIRLeoMinimal::test_noise_rss`
- `tests/integration/test_golden_mwir_leo_minimal.py::TestGoldenMWIRLeoMinimal::test_snr`
- `tests/integration/test_ground_truth_mwir.py::TestGroundTruthMWIR::test_snr`

**Regression gate:** Every PR must finish with exactly 2007 passed, 4 failed (same 4).

---

## 9. Deprecated File Tracker

Files that have been split and converted to re-export shims. These files contain **no logic** — only `from new_module import *` re-exports for backward compatibility. They will be deleted in Phase 3.4.

| # | Deprecated File | Replaced By | Split PR | Shim Removed |
|---|----------------|-------------|----------|--------------|
| 1 | `src/radiant/detector/noise.py` | `noise_photon.py`, `noise_detector.py`, `noise_roic.py`, `noise_fixed_pattern.py`, `noise_other.py` | PR 1.1 | **Kept** — retains `compute_noise_budget` aggregator; re-export lines removed in PR 3.4 |
| 2 | `src/radiant/optics/psf.py` | `psf_data.py`, `effective_psf.py`, `psf_builder.py` | PR 1.2 | **Yes** — deleted in PR 3.4 |
| 3 | `src/radiant/source/unified_target.py` | `resolved_target.py`, `resolve_direct.py`, `resolve_geometry.py`, `resolve_sub_pixel.py`, `resolve_intensity.py`, `resolve_physical.py` | PR 1.3 | **Yes** — deleted in PR 3.4 |
| 4 | `src/radiant/source/primitives.py` | `shapes/sphere.py`, `shapes/flat_plate.py`, `shapes/box.py`, `shapes/cylinder.py`, `shapes/cone.py`, `shapes/_helpers.py` | PR 1.4 | **Yes** — deleted in PR 3.4 |
| 5 | `src/radiant/readout/binning.py` | `binning_onchip.py`, `binning_offchip.py` | PR 1.5 | **Yes** — deleted in PR 3.4 |
| 6 | `src/radiant/performance/snr.py` | `snr.py` (keeps SNRResult + compute_snr), `contrast_snr.py` | PR 2.2 | **Kept** — retains SNRResult + compute_snr; re-export line removed in PR 3.4 |
| 7 | `src/radiant/performance/nedt.py` | `nedt.py` (keeps NEDTResult + compute_nedt*), `nedl.py`, `nedr.py` | PR 2.1 | **Kept** — retains NEDTResult + compute_nedt/compute_nedt_from_snr; re-export lines removed in PR 3.4 |
| 8 | `src/radiant/performance/saturation_metrics.py` | `saturation_metrics.py` (keeps MarginResult), `well_margin.py`, `adc_margin.py`, `dynamic_range.py` | PR 2.3 | **Kept** — retains MarginResult shared type; re-export lines removed in PR 3.4 |
| 9 | `src/radiant/performance/detection.py` | `detection.py` (keeps DetectionRangeResult), `detection_beer_lambert.py`, `detection_generic.py` | PR 2.4 | **Kept** — retains DetectionRangeResult shared type; re-export lines removed in PR 3.4 |
| 10 | `src/radiant/readout/tdi.py` | `tdi_mtf.py`, `tdi_scaling.py` | PR 2.6 | **Yes** — deleted in PR 3.4 |
| 11 | `src/radiant/source/background.py` | `background_blackbody.py`, `background_tabulated.py`, `background_constant.py` | PR 2.7 | **Yes** — deleted in PR 3.4 |
| 12 | `src/radiant/source/point_source.py` | `point_source_direct.py`, `point_source_blackbody.py` | PR 2.8 | **Yes** — deleted in PR 3.4 |
| 13 | `src/radiant/source/brdf.py` | `brdf_lambertian.py`, `brdf_phong.py` | PR 2.9 | **Yes** — deleted in PR 3.4 |
| 14 | `src/radiant/optics/element_list.py` | `system_transmission.py`, `nearfield_irradiance.py` | PR 2.10 | **Yes** — deleted in PR 3.4 |
| 15 | `src/radiant/optics/diffraction.py` | `diffraction_mono.py`, `diffraction_poly.py`, `diffraction_strehl.py` | PR 3.1 | **Yes** — deleted in PR 3.4 |

**Notes:**
- PR 1.6 + 1.7 (transmission_modes.py, filters.py) were reclassified as dispatcher patterns — not violations. Private functions tightly coupled to a single public dispatcher.
- PR 2.5 (readout/saturation.py) was reclassified as acceptable — dual saturation checks are a natural pair sharing an enum, with very simple functions.
- PR 3.2 (optics/wavefront.py) was reclassified — FieldWfeSample is tightly coupled to WavefrontError, not independent.
- PR 3.3 (optics/stray_light.py) was reclassified — dispatcher pattern (same as transmission_modes.py, filters.py).

**Final regression after PR 3.4 shim removal:** 2007 passed, 4 failed (same 4 pre-existing).
