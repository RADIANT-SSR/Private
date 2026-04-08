# RADIANT Phase 1 Implementation Plan

**Date:** 2026-04-07
**Status:** Authoritative
**Scope:** Defines the Phase 1 implementation plan organized as phases 1a through 1e. Each phase includes deliverables, "done" criteria, dependencies, effort estimates, risks, and parallelization guidance.

---

## Overview

Phase 1 delivers a fully functional RADIANT command-line and scripting-API tool with no GUI. The output: a `radiant run config.yaml` command that produces correct SNR, NEDT, NIIRS, and noise/MTF budgets for single-band VIS, MWIR, and LWIR sensors.

**Total estimated effort:** 10 person-weeks (solo) or 5 weeks with 2 developers working phases 1b + 1c in parallel.

**The parallelization constraint:** Phase 1a must complete before any other phase begins. Phases 1b and 1c can run in parallel. Phase 1d requires both 1b and 1c complete. Phase 1e requires 1d complete.

---

## Sequencing Diagram

```
Week 1–2                   Week 3–4                   Week 5–6                   Week 7–8         Week 9–10
┌──────────────────┐
│  Phase 1a        │
│  Core infra      │
│  (serial)        │
└────────┬─────────┘
         │
         ├──────────────────────────────────────────────────────────────────────────────────────────┐
         │                                                                                          │
         ▼                                                                                          ▼
┌──────────────────┐                                                              ┌──────────────────┐
│  Phase 1b        │                                                              │  Phase 1c        │
│  Source +        │                                                              │  Optics +        │
│  Atmosphere      │◄── can run in parallel ──────────────────────────────────────│  Platform +      │
│                  │                                                              │  SpectralInt     │
└────────┬─────────┘                                                              └──────┬───────────┘
         │                                                                               │
         └────────────────────────────────────────┬──────────────────────────────────────┘
                                                  │  (both required)
                                                  ▼
                                       ┌──────────────────┐
                                       │  Phase 1d        │
                                       │  Detector +      │
                                       │  Readout +       │
                                       │  Performance     │
                                       └────────┬─────────┘
                                                │
                                                ▼
                                       ┌──────────────────┐
                                       │  Phase 1e        │
                                       │  I/O + API +     │
                                       │  CLI + IntTests  │
                                       └──────────────────┘
```

---

## Phase 1a — Core Infrastructure

**Duration:** 2 weeks  
**Developer:** Solo (must be serial — all other phases depend on this)

### Deliverables

| File | Content |
|------|---------|
| `src/radiant/core/constants.py` | CODATA 2018 constants: h, c, k_B, σ_SB, q |
| `src/radiant/core/units.py` | `UNIT_CONVERSIONS` dict; `convert(value, from_unit, to_unit)` |
| `src/radiant/core/parameters.py` | `ParameterDef`, `Tolerance`, `ConsistencyGroup`, `ParameterSet`, `ResolvedValue`, `Provenance` enum |
| `src/radiant/core/spectral.py` | `SpectralData`, `SpectralDataStore` |
| `src/radiant/core/chain.py` | `Stage` Protocol, `ChainState` (frozen dataclass), `ChainRunner` |
| `src/radiant/core/radiometry.py` | `RadiometricFrame`, `NoiseTerm`, forward-factor registry |
| `src/radiant/core/geometry.py` | `ObserverGeometry`, `TargetGeometry`, `SceneGeometry`; GSD, slant range, IFOV |
| `src/radiant/core/regime.py` | `RadiometricRegime` enum (EXTENDED, POINT_SOURCE, SUB_PIXEL); classify() |
| `src/radiant/exceptions.py` | Full exception hierarchy (`RadiantError` → all subtypes) |
| `src/radiant/core/tests/` | Level 0 + Level 1 tests for all core modules |

### "Done" Criteria

- [ ] All Level 0 tests in `core/tests/` pass: Planck integral ≈ σT⁴, Wien peak, shot noise formula, quantization noise formula, Beer-Lambert, unit conversion roundtrips
- [ ] `ParameterSet` can load the MWIR baseline YAML (when given a pre-assembled schema) and resolve all parameters including derived `f_number`
- [ ] `ConsistencyGroup("optics_fno")` correctly derives `f_number` from `focal_length / aperture_diameter`, raises `ConsistencyError` when all three are over-specified inconsistently
- [ ] `ChainState` is immutable: `state.with_frame(...)` returns a new state; the original is unchanged
- [ ] `SpectralDataStore` interpolates a 100-point QE curve onto a 500-point common grid without NaN or out-of-bounds values
- [ ] `RadiantError` hierarchy: all exception subclasses have `what`, `why`, `action` fields; `str(error)` is readable
- [ ] `pytest --cov=radiant.core --cov-fail-under=95` passes

### Dependencies

None. This phase can begin immediately.

### Risks and Mitigations

| Risk | Probability | Impact | Mitigation |
|------|------------|--------|-----------|
| `ParameterSet` resolution logic is more complex than estimated (cycles in consistency groups, partial specification ambiguity) | Medium | Medium | Write the resolution algorithm with explicit test cases before implementation. The algorithm is specified in RADIANT_Parameter_System.md §resolution algorithm. |
| `ChainState` frozen dataclass with dict fields causes performance issues in sweep loops | Low | Low | Profile with 100-point sweep before optimizing. `replace()` on a frozen dataclass is fast for small state. |

---

## Phase 1b — Source and Atmosphere

**Duration:** 2 weeks  
**Can run in parallel with Phase 1c**

### Deliverables

| File | Content |
|------|---------|
| `src/radiant/source/_schema.py` | ParameterDefs for all `target.*`, `background.*` parameters |
| `src/radiant/source/blackbody.py` | `planck_spectral_radiance(wl_um, T_K)`, `planck_total_radiance(T_K, lam_min, lam_max)` |
| `src/radiant/source/solar.py` | Load Kurucz spectrum; `solar_spectral_irradiance(wl_um)` interpolated to grid |
| `src/radiant/source/reflected.py` | Lambertian reflected radiance: `L_refl = ρ × E_solar × τ_solar / π` |
| `src/radiant/source/emitted.py` | `L_emitted = ε × Planck(T, λ)` |
| `src/radiant/source/background.py` | Background spectral radiance (extended scene) |
| `src/radiant/source/emissivity.py` | Gray-body scalar → constant spectral array; file-loaded spectral emissivity |
| `src/radiant/source/stage.py` | `SourceStage`: assembles target + background; tentative regime; populates `at_target` frame |
| `src/radiant/atmosphere/_schema.py` | ParameterDefs for all `atmosphere.*` parameters |
| `src/radiant/atmosphere/modtran.py` | MODTRAN tape7 reader: wavenumber→wavelength, W/cm²→W/m², ascending sort |
| `src/radiant/atmosphere/simple.py` | Beer-Lambert transmittance; constant path radiance |
| `src/radiant/atmosphere/standard.py` | 6 standard atmosphere profiles (US76, tropical, midlat summer/winter, subarctic summer/winter) |
| `src/radiant/atmosphere/transmittance.py` | `SpectralTransmittance` container |
| `src/radiant/atmosphere/path_radiance.py` | `SpectralPathRadiance` container |
| `src/radiant/atmosphere/thermal_emission.py` | Atmospheric downwelling emission (simple model) |
| `src/radiant/atmosphere/turbulence.py` | Fried r0, turbulence MTF (stub for v1 ground-based; not applicable to space-based) |
| `src/radiant/atmosphere/stage.py` | `AtmosphereStage`: applies τ_atm × L_source + L_path + L_atm; populates `at_aperture` frame |
| `data/solar/kurucz_1nm.csv` | Kurucz solar reference spectrum (W/m²/µm at 1 AU) |
| `data/solar/astm_e490.csv` | ASTM E490 solar spectrum (alternative reference) |

### "Done" Criteria

- [ ] `SourceStage` run with T=300K, ε=0.95 produces `at_target` frame with spectral radiance peak near 9.7 µm (within 0.5% of Wien's law)
- [ ] `SourceStage` run with Lambertian ρ=0.5, E_solar loaded: at-target reflected radiance equals E_solar × ρ / π within 0.1%
- [ ] MODTRAN tape7 reader: load `tests/fixtures/sample_tape7.txt`; verify ascending wavelength, W/m²/sr/µm units, τ_atm(4.2 µm) ∈ [0.5, 1.0]
- [ ] `AtmosphereStage` full pass: L_at_aperture(λ) = τ × L_source + L_path + L_atm; spot-check at 4.2 µm against manual calculation
- [ ] Simple Beer-Lambert model: τ(10 km, α=0.1 km⁻¹) = exp(-1) ± 0.01%
- [ ] `SourceStage` regime classification: 100 m² target at 10 km → extended; 0.01 m² at 10 km → point
- [ ] All tests in `src/radiant/source/tests/` and `src/radiant/atmosphere/tests/` pass

### Dependencies

Phase 1a (core) must be complete.

### Risks and Mitigations

| Risk | Probability | Impact | Mitigation |
|------|------------|--------|-----------|
| MODTRAN tape7 fixture file format varies between MODTRAN versions | Medium | Medium | Document the exact tape7 format expected; include a small known-good fixture file in the repo |
| Solar spectrum file loading fails due to data packaging issues | Low | Low | Use `importlib.resources` for data files; test data loading at import time in `conftest.py` |

---

## Phase 1c — Optics, Platform, Spectral Integration

**Duration:** 2 weeks  
**Can run in parallel with Phase 1b**

### Deliverables

| File | Content |
|------|---------|
| `src/radiant/optics/_schema.py` | ParameterDefs for `sensor.optics.*`, `sensor.filter.*` |
| `src/radiant/optics/psf.py` | `PSF` container; PSF → OTF via FFT; PSF moments |
| `src/radiant/optics/diffraction.py` | `circular_aperture_mtf(freq, D, f, lam)`; Airy disk; `airy_first_dark_ring_rad()` |
| `src/radiant/optics/aberrations.py` | Marechal Strehl; WFE → MTF (Gaussian approximation); interface for Zernike (stub) |
| `src/radiant/optics/defocus.py` | Defocus MTF (sinc-based) |
| `src/radiant/optics/obscuration.py` | Central obscuration MTF correction |
| `src/radiant/optics/throughput.py` | Optical transmission stack; warm-optics emission; cold stop efficiency |
| `src/radiant/optics/filter.py` | Bandpass filter: tophat, Gaussian, Butterworth; `filter_transmission(wl, λ_c, Δλ, shape)` |
| `src/radiant/optics/ee_box.py` | `encircled_energy_airy(r, D, f, lam)`; `ee_box_pixel(pixel_pitch, D, f, lam)` |
| `src/radiant/optics/stage.py` | `OpticsStage`: throughput, MTF terms, EE_box, final regime, populates `post_optics` frame |
| `src/radiant/platform/_schema.py` | ParameterDefs for `platform.*`, `geometry.*` |
| `src/radiant/platform/geometry.py` | GSD, IFOV, slant range computation |
| `src/radiant/platform/smear.py` | Along-track smear MTF (rect/sinc); `smear_mtf(freq, v_img, t_int)` |
| `src/radiant/platform/jitter.py` | Jitter MTF (Gaussian); `jitter_mtf(freq, sigma_jitter_rad)` |
| `src/radiant/platform/sampling.py` | `pixel_aperture_mtf(freq, pixel_pitch)` |
| `src/radiant/platform/stage.py` | `PlatformStage`: smear + jitter MTF terms |
| `src/radiant/spectral_integration/_schema.py` | ParameterDefs for spectral grid |
| `src/radiant/spectral_integration/grid.py` | Common wavelength grid construction |
| `src/radiant/spectral_integration/integration.py` | Spectral integration: `∫ L × A × Ω × τ × QE × λ/(hc) dλ`; trapezoid rule |
| `src/radiant/spectral_integration/stage.py` | `SpectralIntegrationStage`: applies EE_box, produces photoelectrons, populates `at_fpa` + `photoelectrons` frames |

### "Done" Criteria

- [ ] `diffraction_mtf(f=0)` = 1.0; `diffraction_mtf(f=f_cutoff)` < 1e-6 for D=0.30m, λ=4.2µm, f=1.20m
- [ ] `encircled_energy_airy(r_first_dark)` = 0.838 ± 0.002 (Born & Wolf reference value)
- [ ] `pixel_aperture_mtf(f_nyquist, p)` = sinc(0.5) ≈ 0.6366 ± 1e-6
- [ ] `smear_mtf(f, v=0, t_int)` = 1.0 (no smear → unity MTF)
- [ ] `smear_mtf(f_nyquist, v, t_int)` where v×t_int = 1 pixel → sinc(1) ≈ 0 (1-pixel smear kills MTF at Nyquist)
- [ ] `OpticsStage`: f/# consistency group resolved; A_collect = π(D/2)² × (1 - ε_obs²); Ω_pixel = (p/f)²
- [ ] `SpectralIntegrationStage` extended-scene photoelectrons: manual integral of Planck × filter × QE agrees within 0.5%
- [ ] `SpectralIntegrationStage` point-source regime: photoelectrons = signal_extended × EE_box within 1%
- [ ] All tests in `optics/tests/`, `platform/tests/`, `spectral_integration/tests/` pass

### Dependencies

Phase 1a (core) must be complete. Phase 1b is not required — optics and platform depend only on `radiant.core`.

### Risks and Mitigations

| Risk | Probability | Impact | Mitigation |
|------|------------|--------|-----------|
| Numerical integration of Planck × QE × filter has convergence issues near filter edges | Medium | Low | Use trapezoid rule on 500-point grid; verify against analytic approximation (narrow-band approximation) |
| PSF → OTF FFT produces numerical noise at high spatial frequencies | Low | Medium | Apply Hanning window before FFT; normalize OTF to 1.0 at f=0 |
| EE_box numerical integration for obscured aperture is slow | Low | Low | Pre-compute EE(r) on a 200-point grid and interpolate |

---

## Phase 1d — Detector, Readout, Performance

**Duration:** 3 weeks  
**Requires phases 1b and 1c complete**

This is the largest phase. It implements all noise terms, completes the signal chain, and produces all performance metrics.

### Deliverables

| File | Content |
|------|---------|
| `src/radiant/detector/_schema.py` | ParameterDefs for `sensor.detector.*` |
| `src/radiant/detector/qe.py` | HgCdTe, InSb, InGaAs, Si QE models; file-loaded QE |
| `src/radiant/detector/dark_current.py` | Rule 07 model; activation energy model; `dark_current_electrons_per_s(T_K, cutoff_um, material)` |
| `src/radiant/detector/shot_noise.py` | `photon_shot_noise_electrons(signal_e)`, `dark_current_shot_noise(J_dark, t_int)` |
| `src/radiant/detector/prnu.py` | PRNU model: fractional nonuniformity; residual after 2-point NUC |
| `src/radiant/detector/nonlinearity.py` | Polynomial nonlinearity model |
| `src/radiant/detector/saturation.py` | Full-well check; saturation flag in ChainState |
| `src/radiant/detector/ipc.py` | IPC MTF: `ipc_mtf(freq, alpha, pixel_pitch)` |
| `src/radiant/detector/diffusion.py` | Charge-diffusion MTF (Gaussian); `diffusion_mtf(freq, diffusion_length, pixel_pitch)` |
| `src/radiant/detector/stage.py` | `DetectorStage`: signal in e-, all detector noise terms, pixel MTF, IPC MTF, diffusion MTF |
| `src/radiant/readout/_schema.py` | ParameterDefs for `sensor.readout.*` |
| `src/radiant/readout/read_noise.py` | Fowler-N, CDS, single-sample read noise |
| `src/radiant/readout/one_over_f.py` | 1/f noise model; corner frequency |
| `src/radiant/readout/ktc.py` | kTC noise; CDS cancellation |
| `src/radiant/readout/adc.py` | `quantization_noise_electrons(lsb_e)` = LSB/√12; DN range |
| `src/radiant/readout/gain.py` | System gain e-/DN; GNNU stub |
| `src/radiant/readout/fixed_pattern.py` | DSNU and column FPN; residual after NUC |
| `src/radiant/readout/stage.py` | `ReadoutStage`: applies TDI/coadds/gain/ADC; finalizes noise budget |
| `src/radiant/performance/_schema.py` | ParameterDefs for performance parameters |
| `src/radiant/performance/snr.py` | `snr(signal_e, noise_budget)` |
| `src/radiant/performance/nedt.py` | `nedt(snr, T_target, wl, params)` via dL/dT |
| `src/radiant/performance/system_mtf.py` | System MTF = ∏ all MTF terms in ChainState |
| `src/radiant/performance/giqe.py` | GIQE5 implementation (EO-NIIRS) |
| `src/radiant/performance/iirs.py` | IIRS implementation (IR NIIRS) |
| `src/radiant/performance/niirs.py` | Dispatcher: GIQE5 vs. IIRS based on band + regime |
| `src/radiant/performance/detection_range.py` | Detection range from SNR threshold |
| `src/radiant/performance/stage.py` | `PerformanceStage`: system MTF product; SNR, NEDT, NIIRS, RER, GSD |

### "Done" Criteria

- [ ] Full chain (SourceStage → PerformanceStage) runs for MWIR baseline config without exceptions
- [ ] SNR is in a physically plausible range for the baseline config (10 < SNR < 200 for 300K target at 600 km with 0.3m aperture)
- [ ] Noise budget sums to correct total: `σ_total = √(Σ σᵢ²)` within 0.01%
- [ ] Dark current noise: `σ_dark = √(J_dark × t_int)` exactly (Level 0 test)
- [ ] CDS enabled: kTC noise term = 0.0 exactly; CDS disabled: kTC ≠ 0
- [ ] `system_mtf = ∏(individual MTFs)`: spot check at 3 frequencies; all agree within 1e-10
- [ ] GIQE5 produces NIIRS within ±0.1 of published NGA reference case
- [ ] NEDT: numerical dL/dT agrees with analytic Planck derivative within 1%
- [ ] `DetectorStage` flags saturation when signal > full_well
- [ ] All tests in `detector/tests/`, `readout/tests/`, `performance/tests/` pass with ≥ 85% line coverage

### Dependencies

Phases 1a, 1b, and 1c all complete.

### Risks and Mitigations

| Risk | Probability | Impact | Mitigation |
|------|------------|--------|-----------|
| GIQE5 implementation: NGA reference cases not publicly available | Medium | Medium | Use published descriptions of GIQE5 from open literature; validate qualitative behavior (NIIRS increases with SNR and decreases with GSD) |
| Noise budget total exceeds signal (SNR < 1) for extreme parameter sets | Low | Low | This is valid physics; test for it explicitly, ensure no NaN or negative SNR |
| Rule 07 dark current model: disagreement with measured data for specific cutoff wavelengths | Low | Medium | Implement Rule 07 exactly as published; add a `dark_current_override` parameter for measured data |

---

## Phase 1e — I/O, API, CLI, Integration Tests

**Duration:** 3 weeks  
**Requires phase 1d complete**

### Deliverables

| File | Content |
|------|---------|
| `src/radiant/io/config.py` | YAML loader with `_extends`, `_imports`, `_vars` support; Pydantic validation |
| `src/radiant/io/modtran_reader.py` | MODTRAN tape7/tape8 parser (moved from atmosphere; io owns file parsing) |
| `src/radiant/io/spectral_library.py` | Generic CSV spectral file reader |
| `src/radiant/io/results.py` | `RadiantResult` container; JSON/dict serialization; provenance record generation |
| `src/radiant/io/hdf5.py` | HDF5 batch results write/read (optional, behind `h5py` check) |
| `src/radiant/api/session.py` | `RadiantSession` / `Sensor` class: load, set, evaluate, validate, explain |
| `src/radiant/api/sensor.py` | `SensorConfig` fluent builder |
| `src/radiant/api/scenario.py` | `ScenarioConfig` fluent builder |
| `src/radiant/api/batch.py` | `BatchRunner`: cross-product sweep, parallel execution |
| `src/radiant/api/sweep.py` | `SweepResult`, `Sweep2DResult` |
| `src/radiant/api/montecarlo.py` | `MonteCarloResult`, `SensitivityResult` |
| `src/radiant/cli/main.py` | Click entry point; registered as `radiant` in pyproject.toml |
| `src/radiant/cli/run.py` | `radiant run <config.yaml> [--set k=v] [--var K=V]` |
| `src/radiant/cli/explain.py` | `radiant explain <config.yaml> <param>` |
| `src/radiant/cli/validate.py` | `radiant validate <config.yaml>` |
| `tests/integration/` | 4 full-chain integration tests (VNIR, MWIR, LWIR, point source) |
| `tests/golden/` | Golden JSON files for 4 integration test scenarios |
| `examples/` | `vnir_trade.py`, `mwir_crossover.py`, `batch_mc.py` |

### "Done" Criteria

- [ ] `radiant run configs/mwir_leo_baseline.yaml` produces output with SNR, NEDT, NIIRS, GSD, MTF budget — no exceptions
- [ ] `radiant validate configs/mwir_leo_baseline.yaml` prints "OK: no validation errors"
- [ ] `radiant validate configs/invalid.yaml` prints all validation errors (not just the first one) and exits non-zero
- [ ] `radiant explain configs/mwir_leo_baseline.yaml sensor.optics.f_number` prints provenance chain
- [ ] `Sensor.load("configs/mwir_leo_baseline.yaml").evaluate().snr()` returns a float in (10, 200)
- [ ] `sensor.sweep("sensor.optics.aperture_diameter", np.linspace(0.15, 0.60, 10))` returns a `SweepResult` with 10 entries
- [ ] `sensor.monte_carlo(n_trials=100)` runs without exception; `mc.mean("snr")` is a float
- [ ] All 4 integration tests pass with Level 2 tolerances from RADIANT_Testing_Validation.md
- [ ] Golden files frozen; `pytest -m golden` passes
- [ ] `radiant reproduce tests/golden/mwir_leo_baseline.json` reproduces the same result
- [ ] `pyproject.toml` has correct entry points, dependencies, and version `0.1.0`
- [ ] `pip install -e .` works from a clean virtualenv

### Dependencies

Phase 1d complete. The `io/` and `api/` layers depend on all physics stages being in place.

### Risks and Mitigations

| Risk | Probability | Impact | Mitigation |
|------|------------|--------|-----------|
| YAML `_extends` + `_imports` deep merge has edge cases (list merging, null override) | Medium | Medium | Write 20+ unit tests for the YAML loader covering all merge scenarios before implementing other `io/` code |
| BatchRunner parallel execution has race conditions under multiprocessing | Low | Medium | Each worker gets a deep copy of `Sensor`; no shared mutable state; test with `n_jobs=4` |
| `radiant reproduce` fails when numpy version differs (floating-point result changes) | Medium | Low | Document that bit-exact reproduction requires identical dependency versions; warn (don't error) on version mismatch |
| Click CLI entry point not found after `pip install -e .` | Low | Low | Test `pip install -e .` and `radiant --help` explicitly in CI |

---

## CLAUDE.md Reference

See the project-root `CLAUDE.md` for coding agent instructions. The CLAUDE.md distills all architectural rules into a compact reference that coding agents should read before making any change.

---

## Success Metrics for Phase 1 Completion

Phase 1 is complete when all of the following are true:

1. `pytest` passes with no failures across all levels (0, 1, 2, and golden)
2. `pytest --cov=radiant --cov-fail-under=85` passes
3. `mypy --strict src/radiant/core src/radiant/api` passes with no errors
4. `ruff check src/` passes with no errors
5. `import-linter --config pyproject.toml` passes (no illegal imports)
6. `radiant run configs/mwir_leo_baseline.yaml` produces physically correct output (SNR ∈ [10, 200], NEDT ∈ [5, 100] mK, NIIRS ∈ [3, 8])
7. `Sensor.load("configs/mwir_leo_baseline.yaml").evaluate()` runs in < 1 second
8. The examples in `examples/` all run without modification
