# RADIANT — Phase II Implementation Prompt Sequence (Clean Start Version)

> **HISTORICAL — for current architecture see [RADIANT_Master_Architecture.md](../RADIANT_Master_Architecture.md).** Phase II completed; superseded by the Validated variant in this archive folder. Preserved for traceability.

## How to use this document

This sequence assumes Phase I was executed using the optimized prompt
sequence in `RADIANT_Optimized_Prompt_Sequence.md`, producing a clean
set of architecture documents:

```
docs/
├── RADIANT_Master_Architecture.md       (entry point)
├── RADIANT_Physics_Inventory.md         (Phase 1.1)
├── RADIANT_Scope_Decisions.md           (Phase 1.2)
├── RADIANT_Personas.md                  (Phase 1.3)
├── RADIANT_Conventions.md               (Phase 2.1)
├── RADIANT_Parameter_System.md          (Phase 2.2)
├── RADIANT_Signal_Chain_Architecture.md (Phase 2.3)
├── RADIANT_File_Tree.md                 (Phase 2.4)
├── RADIANT_Source_Target_System.md      (Phase 3.1 — unified)
├── RADIANT_Atmosphere.md                (Phase 3.2)
├── RADIANT_Optics.md                    (Phase 3.3 — complete, incl stray light)
├── RADIANT_Spatial_Complete.md          (Phase 3.4 — PSF/MTF/EE/motion unified)
├── RADIANT_Detector_Complete.md         (Phase 3.5 — incl TDI/binning/coadds/readout/noise)
├── RADIANT_Scan_Timing.md               (Phase 3.6)
├── RADIANT_Metrics.md                   (Phase 4.1)
├── RADIANT_Metric_Dependencies.md       (Phase 4.2)
├── RADIANT_Config_Format.md             (Phase 5.1)
├── RADIANT_Scripting_API.md             (Phase 5.2)
├── RADIANT_GUI_Architecture.md          (Phase 5.3 — design only, not implemented)
├── RADIANT_Testing_Validation.md        (Phase 6.1)
├── RADIANT_Plugins.md                   (Phase 6.2)
├── RADIANT_Phase1_Plan.md               (Phase 7.2)
├── CLAUDE.md                            (Phase 7.2 — agent guide)
└── DEVELOPMENT.md                       (Phase 7.2 — dev quickstart)
```

Total: ~20 documents, each with a single unambiguous name.
No versioning ambiguity, no supersession table, no duplicates.

**Key differences from the ad-hoc Phase 2 sequence:**
- Every "Read first:" references ONE document per subsystem
- No "both versions of X" instructions
- Unified subsystems mean simpler integration tasks
- CLAUDE.md was written during Phase 1 (not Phase 2)

**Estimated effort:** 70–100 agent-hours across 6–9 weeks. Somewhat
faster than the ad-hoc version because there's less ambiguity
to resolve during coding.

---

## BEFORE YOU START

### Prerequisites

You should have:
- `docs/` directory containing all ~20 architecture documents from
  Phase 1 (listed above)
- `docs/CLAUDE.md` already written (Phase 7.2 produced it)
- `docs/DEVELOPMENT.md` already written (Phase 7.2 produced it)
- `docs/RADIANT_Phase1_Plan.md` describing the implementation phasing
  (Phase 7.2 produced it — verify it matches this sequence)

If any of these are missing, go back and complete Phase 1 first.
Do not start Phase 2 with an incomplete design.

### Repository setup

```bash
git init radiant
cd radiant
mkdir -p docs src tests examples
# Copy all Phase 1 documents into docs/
# The CLAUDE.md and DEVELOPMENT.md go in the repo root, not docs/
cp docs/CLAUDE.md .
cp docs/DEVELOPMENT.md .
```

### Install development environment

Follow the instructions in `DEVELOPMENT.md`. The agent will use
these conventions.

---

## PHASE 2A — FOUNDATION (5 prompts)

These build the core infrastructure that everything depends on.
Everything is tested thoroughly before any physics is implemented.

### Prompt 2A.1 — Project scaffold

```
Task: Create the RADIANT project scaffold.

Read first:
- docs/RADIANT_File_Tree.md
- docs/RADIANT_Master_Architecture.md
- DEVELOPMENT.md

Produce:
1. Full directory structure under src/radiant/ exactly matching
   docs/RADIANT_File_Tree.md. Empty __init__.py in every package.
2. pyproject.toml with project metadata, dependencies, and tool
   configs (ruff, mypy, pytest, black) exactly as specified in
   DEVELOPMENT.md
3. tests/ directory mirroring src/radiant/ structure
4. README.md — one paragraph + pointer to docs/RADIANT_Master_Architecture.md
5. .gitignore for Python
6. .pre-commit-config.yaml

Do NOT write any physics code yet. Scaffold only.

Verify:
- `pip install -e .[dev]` succeeds
- `pytest` runs (zero tests, but framework works)
- `ruff check .` passes (no Python files yet)
- `mypy src/radiant` passes

Report: directory tree, verification results.
```

### Prompt 2A.2 — Constants and units

```
Task: Implement physical constants and unit conversion helpers.

Read first:
- docs/RADIANT_Conventions.md

Produce:
1. src/radiant/constants.py
   - All physical constants used anywhere in RADIANT
   - CODATA values via scipy.constants where possible
   - Each constant has docstring with value, units, source
   - Derived convenience values (e.g., hc/λ at common wavelengths)
2. src/radiant/units.py
   - Wavelength ↔ wavenumber conversion
   - Unit prefix conversions (µm ↔ nm ↔ cm⁻¹, rad ↔ deg ↔ µrad)
   - Photon energy from wavelength
   - Photon rate from power at given wavelength
   - Plain Python functions, no astropy.units dependency
3. tests/test_constants.py — verify against CODATA
4. tests/test_units.py — verify invertibility, edge cases

Report: files, test output (all pass), coverage for these files.
```

### Prompt 2A.3 — Spectral grid and spectral array

```
Task: Implement SpectralGrid and SpectralArray.

Read first:
- docs/RADIANT_Conventions.md (spectral conventions section)
- docs/RADIANT_Parameter_System.md (how spectral quantities relate
  to the parameter system)

Produce:
1. src/radiant/spectral/grid.py
   - SpectralGrid (immutable)
   - Factories: linear, log, custom, preset (VIS, SWIR, MWIR, LWIR)
   - Methods: contains, intersect, merge, resample_onto
2. src/radiant/spectral/array.py
   - SpectralArray (name, unit, grid, values)
   - Arithmetic (+, -, *, /) with broadcasting rules
   - integrate(), band_average(), resample(new_grid), to_dataframe(),
     plot() (lazy matplotlib import)
   - Grid-match enforcement on binary operations
3. tests/spectral/test_grid.py
4. tests/spectral/test_array.py
   - Construction, arithmetic, grid-mismatch errors
   - Integration against analytical cases (constant, linear, Gaussian)
   - Resampling conservation

Report: files, tests, coverage.
```

### Prompt 2A.4 — Parameter system

```
Task: Implement the Parameter class and ParameterResolver.

Read first:
- docs/RADIANT_Parameter_System.md (complete — one document, no versions)

Produce:
1. src/radiant/parameter/parameter.py — Parameter dataclass
2. src/radiant/parameter/tolerance.py — Tolerance class with sampling
3. src/radiant/parameter/resolver.py — ParameterResolver with
   topological sort, consistency groups, incremental recompute
4. src/radiant/parameter/exceptions.py — all error types with
   what/why/what-to-do messages
5. tests/parameter/test_parameter.py
6. tests/parameter/test_resolver.py
   - Dependency chains (linear, diamond)
   - Circular dependency detection
   - Consistency group resolution (f/# from EFL, D)
   - Missing required parameter messages
   - Over-constrained consistency group messages

Report: files, tests, coverage. Verify error messages actually tell
users what to do.
```

### Prompt 2A.5 — Geometry and viewing geometry

```
Task: Implement geometry primitives.

Read first:
- docs/RADIANT_Conventions.md (coordinate system section)

Produce:
1. src/radiant/geometry/coordinates.py
   - Right-handed, +Z toward target
   - ZYX Euler (yaw-pitch-roll) conversions
   - Vec3, Mat3 type aliases
2. src/radiant/geometry/viewing.py
   - ViewingGeometry dataclass
   - Slant range from altitudes and zenith angle
   - Solar geometry
3. tests/geometry/test_coordinates.py — rotation round-trip, known rotations
4. tests/geometry/test_viewing.py — slant range against hand-worked cases

Report: files, tests, coverage.
```

**CHECKPOINT 2A:** Run full test suite with coverage. Verify:
- All tests pass
- Coverage > 90% on these files (they're pure infrastructure,
  no reason for lower coverage)
- `mypy --strict` passes
- `ruff check` passes

Do not proceed to 2B until 2A is solid.

---

## PHASE 2B — MINIMUM VIABLE CHAIN (8 prompts)

Goal: first end-to-end SNR calculation.

### Prompt 2B.1 — Source protocol and Planck

```
Task: Implement the Source protocol and ThermalSource.

Read first:
- docs/RADIANT_Source_Target_System.md (ThermalSource section only)
- docs/RADIANT_Signal_Chain_Architecture.md (protocols)

Produce:
1. src/radiant/sources/protocol.py — Source Protocol
2. src/radiant/sources/planck.py
   - planck_spectral_radiance(wavelength_um, T_K) → W/m²/sr/µm
   - planck_spectral_radiance_dT (for NEΔT later)
   - Vectorized, numerically stable at extreme values
3. src/radiant/sources/thermal.py
   - ThermalSource implementing Source protocol
   - Scalar or spectral emissivity
4. src/radiant/sources/parameters.py — all parameters for this module
5. tests/sources/test_planck.py
   - Stefan-Boltzmann: ∫B dλ = σT⁴/π
   - Wien displacement: λ_peak × T = 2898 µm·K
   - Rayleigh-Jeans limit at long λ
   - Tabulated values from NIST or hand calculation
6. tests/sources/test_thermal.py

Do NOT implement other source types yet.

Report: files, tests, AND numerical comparison of your Planck
implementation against an independent calculation at multiple
wavelengths and temperatures. Spot-check at 300 K, 4 µm.
```

### Prompt 2B.2 — Simple atmosphere

```
Task: Implement the Atmosphere protocol and SimpleAtmosphere.

Read first:
- docs/RADIANT_Atmosphere.md (all — single document)

Produce:
1. src/radiant/atmosphere/protocol.py — Atmosphere Protocol
2. src/radiant/atmosphere/simple.py
   - Parametric band model (H₂O, CO₂, O₃, Rayleigh, aerosol)
   - Path length scaling with zenith angle
   - Returns transmittance AND path radiance
3. src/radiant/atmosphere/exo.py — τ=1, L_path=0
4. src/radiant/atmosphere/parameters.py
5. tests/atmosphere/test_simple.py
   - τ in [0, 1]
   - L_path ≥ 0
   - Slant path increases τ-losses with zenith
   - Spot check CO₂ at 4.3 µm
6. tests/atmosphere/test_exo.py

Do NOT implement tabulated or MODTRAN yet.

Report: files, tests, coverage, and a plot of simple atm transmittance
from 0.4 to 14 µm showing absorption bands (save to tests/artifacts/).
```

### Prompt 2B.3 — Optics (scalar transmission only)

```
Task: Implement basic optics with scalar transmission.

Read first:
- docs/RADIANT_Optics.md (Mode 1 — scalar transmission only)

Produce:
1. src/radiant/optics/aperture.py — Aperture class (circular only)
2. src/radiant/optics/telescope.py
   - Telescope class
   - Scalar transmission
   - f-number consistency group (focal_length, diameter, f/#)
   - solid_angle_sr()
3. src/radiant/optics/parameters.py
4. tests/optics/test_aperture.py — areas for unobscured/obscured
5. tests/optics/test_telescope.py — f/#, Ω=π/(4f²), consistency group

Do NOT implement WFE, filters, nearfield, element lists, or stray
light yet. Those come in Phase 2D.

Report: files, tests, coverage.
```

### Prompt 2B.4 — Detector (QE, pixel, basic noise)

```
Task: Implement basic detector with minimum noise for SNR.

Read first:
- docs/RADIANT_Detector_Complete.md (QE, pixel, and noise sections only)

Produce ONLY what's needed for a first SNR calculation:
1. src/radiant/detectors/qe.py — QECurve, library access (Si, HgCdTe MW)
2. src/radiant/detectors/pixel.py — Pixel geometry (pitch, fill factor)
3. src/radiant/detectors/detector.py — Detector container
4. src/radiant/detectors/noise.py
   - NoiseModel with ONLY: shot_signal, shot_background, dark, read,
     quantization
   - total() method (RSS)
5. src/radiant/detectors/parameters.py
6. tests/detectors/test_qe.py
7. tests/detectors/test_pixel.py
8. tests/detectors/test_noise.py
   - Poisson statistics (mean = variance)
   - RSS combination
   - Read-noise-limited and shot-noise-limited regimes

Do NOT implement: TDI, binning, coadds, full readout chain, PRNU/DSNU,
G-R, Johnson, 1/f, kTC. Those come in Phase 2D.

Report: files, tests, and verify a 300 K blackbody through a perfect
telescope produces the expected electron count for a hand-calculated
case.
```

### Prompt 2B.5 — Chain skeleton and extended-scene chain

```
Task: Implement the signal chain architecture with extended-scene chain.

Read first:
- docs/RADIANT_Signal_Chain_Architecture.md (complete)

Produce:
1. src/radiant/chain/result.py — ChainResult with nested fields
   (source, atmosphere, optics, detector, metrics)
2. src/radiant/chain/extended.py
   - ExtendedSceneChain
   - evaluate(source, atmosphere, optics, detector, geometry) → ChainResult
   - Follows the extended scene equations from RADIANT_Signal_Chain_Architecture.md
3. src/radiant/chain/chain.py — Chain entry point (only extended for now)
4. tests/chain/test_extended.py
   - Thermal source + simple atm + scalar optics + basic detector
   - Unit consistency at every stage
   - Hand-verified numerical result

Do NOT implement point source or sub-pixel chains yet. Those come in 2D.
Do NOT implement backward propagation yet.

Report: files, tests, AND a worked example with printed intermediates
for an MWIR LEO scenario. Verify every number against hand calculation.
```

### Prompt 2B.6 — SNR metric and YAML I/O

```
Task: Implement SNR metric and YAML config loading.

Read first:
- docs/RADIANT_Metrics.md (SNR section)
- docs/RADIANT_Config_Format.md

Produce:
1. src/radiant/metrics/snr.py — snr_extended function, edge cases
2. src/radiant/metrics/protocol.py — Metric Protocol (for later metrics)
3. src/radiant/io/yaml_io.py — load_config, save_config
4. src/radiant/io/schema.py — Pydantic models for implemented sections
5. tests/metrics/test_snr.py
6. tests/io/test_yaml_io.py — round-trip test
7. examples/mwir_leo_minimal.yaml — minimum viable config
8. tests/integration/test_mwir_leo_minimal.py
   - Load, run, verify SNR equals a known value

Report: files, tests, and the SNR value from the example.
```

### Prompt 2B.7 — CLI skeleton

```
Task: Implement minimal CLI.

Read first:
- docs/RADIANT_Config_Format.md (CLI section)

Produce:
1. src/radiant/cli/main.py
   - `radiant run <config>` → runs chain, prints summary
   - `radiant run <config> --set path.to.param=value` for overrides
   - `radiant validate <config>` → checks without running
2. pyproject.toml entry point: `radiant = radiant.cli.main:app`
3. tests/cli/test_main.py

Do NOT implement other commands (sweep, tolerance, new, template,
explain, convert, library, schema). Those come in Phase 2E.

Report: CLI help text, test results.
```

### Prompt 2B.8 — First golden regression test

```
Task: Establish the golden regression baseline.

Read first:
- docs/RADIANT_Testing_Validation.md (golden test section)

Produce:
1. tests/golden/mwir_leo_minimal.json — stored expected values
2. tests/integration/test_golden_mwir_leo_minimal.py
   - Load config, run chain
   - Compare every key output (signal, noise, SNR) against stored values
   - Tolerance: 0.1% (floating point, not physics)
3. scripts/update_golden.py
   - Regenerates golden values when physics intentionally changes
   - Requires --i-know-what-im-doing flag
   - Logs what changed
4. Full test suite run with coverage report

Report: golden values, coverage percentage, any files below 85%.
```

**CHECKPOINT 2B:** Run CLI with example. Verify SNR makes physical sense.
Hand-verify the full signal chain intermediates for one case. This is
the "works end-to-end" milestone. Do not proceed until satisfied.

---

## PHASE 2C — SPATIAL MODEL (7 prompts)

Goal: complete spatial model with EffectivePSF as the single source
of truth.

### Prompt 2C.1 — Pupil function and diffraction engine

```
Task: Implement pupil function and FFT-based PSF computation.

Read first:
- docs/RADIANT_Spatial_Complete.md (diffraction and sampling sections)

Produce:
1. src/radiant/spatial/sampling/config.py
   - SamplingConfig with three-way consistency group:
     psf_oversample, psf_sample_spacing_um, min_samples_per_pixel
   - Fidelity presets: draft, standard, high, publication
2. src/radiant/spatial/diffraction/pupil.py
   - PupilFunction class
   - Generate pupil amplitude (circular, obscuration, apodization)
   - Apply WFE as phase (scalar RMS only for now)
3. src/radiant/spatial/diffraction/engine.py
   - DiffractionEngine
   - compute_mono_psf via FFT with zero-padding
   - compute_poly_psf via wavelength Gaussian quadrature
4. tests/spatial/test_sampling.py
5. tests/spatial/test_pupil.py — areas, obscuration
6. tests/spatial/test_diffraction_engine.py
   - Airy pattern: first zero at 1.22 λf/D
   - FWHM = 1.028 λf/D for circular unobscured
   - Strehl = 1 for unaberrated
   - Energy conservation

Do NOT implement detector effects, motion, or EffectivePSF yet.

Report: files, tests, and a plot of the computed Airy pattern with
analytical overlay.
```

### Prompt 2C.2 — Detector PSF effects

```
Task: Implement pixel aperture and charge diffusion kernels.

Read first:
- docs/RADIANT_Spatial_Complete.md (detector integration section)

Produce:
1. src/radiant/spatial/detector_integration.py
   - pixel_aperture_kernel (2D rect)
   - charge_diffusion_kernel (2D Gaussian)
   - convolve_psf_with_kernel (Fourier-domain for efficiency)
2. tests/spatial/test_detector_integration.py
   - Pixel aperture MTF = sinc
   - Charge diffusion MTF = Gaussian
   - Convolution preserves total energy

Report: files, tests, MTF plots.
```

### Prompt 2C.3 — Motion kernels (smear, jitter, TDI)

```
Task: Implement all motion blur kernels.

Read first:
- docs/RADIANT_Spatial_Complete.md (motion section — includes
  smear, jitter, TDI, turbulence)

Produce:
1. src/radiant/spatial/motion/smear.py
   - platform_smear_kernel, scan_smear_kernel, target_smear_kernel
   - Each produces a 2D rect kernel at the appropriate angle
2. src/radiant/spatial/motion/jitter.py
   - jitter_kernel_scalar (isotropic Gaussian)
   - jitter_kernel_anisotropic (elliptical Gaussian)
3. src/radiant/spatial/motion/tdi.py
   - tdi_misalignment_kernel
4. src/radiant/spatial/motion/turbulence.py
   - kolmogorov_mtf (stubbed per RADIANT_Scope_Decisions.md —
     just the Kolmogorov formula, no wavefront simulation)
5. tests/spatial/test_smear.py
6. tests/spatial/test_jitter.py
7. tests/spatial/test_tdi.py
8. tests/spatial/test_turbulence.py

Each test verifies:
- Zero parameter → delta function (kernel = identity)
- Non-zero → expected shape
- Kernel MTF has expected analytical form

Report: files, tests, kernel plots.
```

### Prompt 2C.4 — EffectivePSF (the critical class)

```
Task: Implement EffectivePSF. This is the most important class in
the spatial subsystem.

Read first (CAREFULLY):
- docs/RADIANT_Spatial_Complete.md (EffectivePSF section —
  the single-source-of-truth principle)

CRITICAL CONSTRAINT: MTF, EE, LSF, ERF, RER MUST ALL be derived from
the same PSF data. Never compute any of these independently.

Consistency check: MTF_system from the multiplicative budget must
equal MTF_2d from FFT of the effective PSF to within numerical precision.

Produce:
1. src/radiant/spatial/effective_psf.py
   - EffectivePSF dataclass
   - Fields: data, pixel_scale_um, grid_size, component_contributions
   - Methods (ALL derived from .data):
     mtf_2d(), mtf_1d(axis)
     ensquared_energy(box_half_width_um, offset_x, offset_y)
     ensquared_energy_nxn(n_pixels, pitch, offset)
     ee_vs_box_size(pitch, max_pixels)
     ee_vs_offset(pitch, n_offsets)
     encircled_energy(radius_um)
     lsf(angle_deg), erf(angle_deg)
     edge_slope(angle_deg), rer()
     fwhm(axis), strehl()
2. src/radiant/spatial/builder.py
   - build_effective_psf(optical_psf, detector_kernels, motion_kernels)
   - All convolutions in Fourier domain
   - Track which components contributed
3. tests/spatial/test_effective_psf.py
   - CRITICAL: MTF from .mtf_2d() must equal product of individual
     kernel MTFs to within 0.1%
   - EE monotonic with box size, EE(full grid) = 1
   - FWHM increases with motion
   - Strehl decreases with WFE and motion
   - RER decreases with motion

Report: files, tests, AND the numerical consistency check result
(budget product MTF vs FFT-derived MTF, with max absolute difference).
```

### Prompt 2C.5 — Spatial metrics and NIIRS

```
Task: Implement spatial metrics and NIIRS.

Read first:
- docs/RADIANT_Metrics.md (spatial and NIIRS sections)
- docs/RADIANT_Metric_Dependencies.md (NIIRS dependency tree)

Produce:
1. src/radiant/spatial/metrics.py
   - gsd, ifov, nyquist_freq_cy_mm
2. src/radiant/metrics/niirs.py
   - niirs_giqe5(gsd_m, rer, snr, overshoot, height_overshoot)
3. tests/spatial/test_metrics.py
4. tests/metrics/test_niirs.py
   - Known NIIRS values from literature
   - GIQE-5 formula verification

Report: files, tests.
```

### Prompt 2C.6 — Integrate spatial into chain

```
Task: Connect the spatial model to the signal chain.

Read first:
- docs/RADIANT_Signal_Chain_Architecture.md (spatial integration section)

Produce:
1. Update src/radiant/chain/extended.py:
   - Build EffectivePSF during evaluation
   - Attach to ChainResult.spatial
   - Compute NIIRS, MTF at Nyquist, EE values
2. Update src/radiant/chain/result.py with spatial fields
3. Extend examples/mwir_leo_minimal.yaml with spatial parameters
4. Update tests/golden/mwir_leo_minimal.json with spatial metrics
5. tests/chain/test_extended_with_spatial.py
   - End-to-end with spatial model active

Report: updated test output, new golden values.
```

### Prompt 2C.7 — Spatial subsystem audit

```
Task: Comprehensive validation of the spatial subsystem.

Run full test suite with coverage focused on src/radiant/spatial/.

For any file below 85% coverage, add tests.

Produce a diagnostic script:
1. tests/diagnostics/spatial_audit.py
   - For a reference configuration, print:
     * Every MTF component at Nyquist
     * Every EE value (1×1, 3×3, 5×5, vs offset)
     * FWHM in both axes
     * RER
     * NIIRS
     * Sampling configuration used
   - Consistency check: budget MTF vs EffectivePSF MTF
   - All numbers self-consistent

Do NOT add new features. Audit and test only.

Report: coverage delta, diagnostic output, any issues found.
```

**CHECKPOINT 2C:** Human reviews PSF plots, runs the spatial audit,
sanity-checks numbers against analytical expectations for simple cases.

---

## PHASE 2D — FULL SIGNAL CHAIN (10 prompts)

Goal: all three regimes, complete source/target system, full optics,
full detector, backward propagation, sweeps, tolerance.

### Prompt 2D.1 — Complete source system

```
Task: Implement all remaining source types.

Read first:
- docs/RADIANT_Source_Target_System.md (full document — this is
  the unified source/target/material document from Phase 3.1)

Produce:
1. src/radiant/sources/reflected.py — ReflectedSolarSource
2. src/radiant/sources/combined.py — CombinedSource (Kirchhoff)
3. src/radiant/sources/sub_pixel.py — SubPixelSource
4. src/radiant/sources/point_source.py — PointSource
5. src/radiant/sources/background.py — BackgroundModel
6. src/radiant/sources/tabulated.py — TabulatedSource
7. src/radiant/sources/brdf.py — Lambertian, Phong
8. src/radiant/sources/solar.py — Solar spectral irradiance reference
9. Tests for each

Verify:
- Kirchhoff consistency (ε + ρ = 1 for opaque)
- BRDF energy conservation
- ReflectedSolarSource against hand calculation

Do NOT implement target geometry in this prompt. That's 2D.2.

Report: files, tests, and a plot of CombinedSource for a gray
surface at 300 K under noon sun.
```

### Prompt 2D.2 — Target geometry and unified resolver

```
Task: Implement target geometry, materials, and the unified resolver.

Read first:
- docs/RADIANT_Source_Target_System.md (geometry, material, and
  unified resolver sections — this is all ONE document)

Produce:
1. src/radiant/target_geometry/shape.py — TargetShape Protocol
2. src/radiant/target_geometry/primitives.py
   - Sphere, Cylinder, Box, FlatPlate, Cone
3. src/radiant/target_geometry/composite.py — CompositeShape
4. src/radiant/target_geometry/material.py — SurfaceMaterial
5. src/radiant/sources/unified_target.py
   - UnifiedTargetResolver
   - All five input paths from docs/RADIANT_Source_Target_System.md
   - Returns ResolvedTarget (regime + source + background)
   - Auto regime detection from angular extent vs PSF/IFOV
6. Tests:
   - Projected area for each shape against analytical
   - Sphere orientation-invariant
   - Composite = sum of primitives
   - Auto regime detection for extended/sub-pixel/point cases
   - All five input paths produce consistent ResolvedTarget

Report: files, tests, and a projected-area table for a 2×1×1 m box
at multiple orientations.
```

### Prompt 2D.3 — Point source and sub-pixel chains

```
Task: Implement the other two regime chains.

Read first:
- docs/RADIANT_Signal_Chain_Architecture.md (three regimes section)

Produce:
1. src/radiant/chain/point_source.py — PointSourceChain
2. src/radiant/chain/sub_pixel.py — SubPixelChain
3. Update src/radiant/chain/chain.py with regime dispatch
4. Update src/radiant/chain/result.py with regime-specific fields
5. tests/chain/test_point_source.py
   - 1/R² scaling
   - A_aperture coupling (not Ω × A_pixel)
   - EE_peak effect on SNR
6. tests/chain/test_sub_pixel.py
   - Contrast ΔL computation
   - Fill fraction coupling
   - CSNR formula

Report: files, tests, worked examples for all three regimes showing
the unit differences between them.
```

### Prompt 2D.4 — Tabulated and MODTRAN atmosphere

```
Task: Implement remaining atmosphere models.

Read first:
- docs/RADIANT_Atmosphere.md (tabulated and MODTRAN sections)

Produce:
1. src/radiant/atmosphere/tabulated.py
2. src/radiant/atmosphere/modtran.py
   - Card deck builder
   - Tape7 parser
   - Cache keyed by config hash
   - Graceful failure if MODTRAN not installed (clear error)
3. tests/atmosphere/test_tabulated.py
4. tests/atmosphere/test_modtran.py (skip if MODTRAN unavailable)

Report: files, tests, comparison of simple vs tabulated for a
matching scenario.
```

### Prompt 2D.5 — Full optics (all five transmission modes, nearfield, stray light)

```
Task: Implement the complete optics subsystem.

Read first:
- docs/RADIANT_Optics.md (the complete document — includes all five
  transmission modes, nearfield, and stray light in one unified design)

Produce:
1. src/radiant/optics/filters.py — bandpass, longpass, shortpass, notch
2. src/radiant/optics/element.py
   - OpticalElement (mirror, lens, window, filter)
   - Kirchhoff-derived emissivity (ε = 1-R or 1-T-R)
   - NEVER accept emissivity as independent parameter
3. src/radiant/optics/element_list.py
   - System transmission AND nearfield from element list
   - Downstream attenuation for nearfield
4. src/radiant/optics/transmission_modes.py
   - Auto-detect and handle all five modes:
     scalar, spectral file, telescope+filters, key elements, full list
   - Each produces the same internal element list representation
5. src/radiant/optics/wavefront.py
   - Scalar RMS, Zernike, measured OPD
6. src/radiant/optics/stray_light.py
   - Four modes: veiling glare, at-FPA, spectral file, PST stub
   - PST stub raises NotImplementedError with helpful message
     (unless fallback provided)
7. Tests for each
8. Integration test: element-by-element vs scalar should agree for
   simple cases within expected bounds

Report: files, tests, and a worked nearfield example for a 3-mirror
telescope.
```

### Prompt 2D.6 — Complete detector (all 14 noise sources, TDI, binning, coadds, readout)

```
Task: Implement all remaining detector features.

Read first:
- docs/RADIANT_Detector_Complete.md (complete document — this is
  the unified detector design including all 14 noise sources, TDI,
  binning, coadds, and the full readout chain)

Produce:
1. Extend src/radiant/detectors/noise.py with all 14 sources:
   - Temporal: shot (signal, bg, nf, stray), dark, G-R, Johnson,
     1/f, read, kTC, quantization
   - Spatial: PRNU, DSNU, clutter
   - Temporal-only vs temporal+spatial modes
2. src/radiant/detectors/tdi.py — analog accumulation, CTE, misalignment
3. src/radiant/detectors/binning.py — on-chip and off-chip
4. src/radiant/detectors/coadds.py — sum, average, median
5. src/radiant/detectors/readout.py
   - Complete chain in correct order:
     signal → TDI → on-chip bin → well check → nonlinearity → read
     noise → gain → ADC → off-chip bin → coadds → DN
   - Dual saturation check (well + ADC)
   - Dynamic range
6. Update src/radiant/chain/*.py to use complete readout chain
7. Tests:
   - Each noise source activated individually
   - Interaction matrix for TDI × binning × coadds
   - Each saturation point
   - Readout order correctness

Report: files, tests, and a noise budget for a reference config
showing all 14 sources and their fractional contributions.
```

### Prompt 2D.7 — Remaining metrics

```
Task: Implement all remaining metrics.

Read first:
- docs/RADIANT_Metrics.md (all metrics)
- docs/RADIANT_Metric_Dependencies.md (dependency trees)

Produce:
1. src/radiant/metrics/nedt.py, nedl.py, nedr.py
2. src/radiant/metrics/csnr.py
3. src/radiant/metrics/detection.py
   - Point source detection range (iterative solver)
4. src/radiant/metrics/saturation.py
   - Well margin, ADC margin, dynamic range
5. src/radiant/metrics/registry.py
   - can_compute(metric, resolved) using dependency trees
6. Tests for each against docs/RADIANT_Metric_Dependencies.md

Report: files, tests, table of all metrics for a reference config.
```

### Prompt 2D.8 — Backward propagation

```
Task: Implement backward propagation of quantities to any reference frame.

Read first:
- docs/RADIANT_Signal_Chain_Architecture.md (backward propagation section)

Produce:
1. src/radiant/chain/quantity.py
   - ChainQuantity (value + unit + frame)
   - to(target_frame, target_unit) method
   - Frames: at_source, at_aperture, at_fpa, in_electrons, in_dn
2. src/radiant/chain/responsivity.py
   - Spectral R(λ), band-integrated R_band
   - Cumulative transfer functions
3. Update ChainResult to expose ChainQuantity objects
4. Tests:
   - Round-trip: forward to electrons, backward to at-aperture,
     returns the original value
   - Unit consistency at every conversion
   - Known transfer cases

Report: files, tests, example showing read noise in electrons,
electrons/s, and equivalent at-aperture radiance.
```

### Prompt 2D.9 — Sweeps, sensitivity, Monte Carlo

```
Task: Implement analysis capabilities.

Read first:
- docs/RADIANT_Scripting_API.md

Produce:
1. src/radiant/chain/sweep.py
   - sweep (1D), sweep_2d
   - Optional parallelization via multiprocessing
2. src/radiant/chain/tolerance.py
   - monte_carlo with correlated sampling
   - Distribution statistics
3. src/radiant/chain/sensitivity.py
   - One-at-a-time finite difference sensitivity
4. Tests for each
5. Performance test: 1000-point sweep < 60 seconds

Report: files, tests, example sweep plots.
```

### Prompt 2D.10 — Full integration test

```
Task: Comprehensive end-to-end testing.

Produce:
1. tests/integration/test_full_system.py
   - Reference config exercising all implemented features
   - All three regimes
   - Backward propagation
   - Sweeps
   - Tolerance analysis
   - Saturation checks
   - Complete noise budget
2. Update golden tests to cover all new features
3. Full test suite with coverage (target > 85%)

Report: test output, coverage, any gaps.
```

**CHECKPOINT 2D:** The tool is feature-complete for v1. Extended
exploratory testing — unusual configurations, edge cases, numerical
verification against hand calculations for several scenarios.

---

## PHASE 2E — USER EXPERIENCE AND POLISH (6 prompts)

### Prompt 2E.1 — Scripting API and Plottable protocol

```
Task: Implement the Sensor scripting API.

Read first:
- docs/RADIANT_Scripting_API.md (complete document)

Produce:
1. src/radiant/api/sensor.py
   - Sensor class with load, save, set, set_many, reset, get,
     evaluate, sweep, sweep_2d, monte_carlo, sensitivity, clone,
     summary, explain
2. src/radiant/api/plot.py
   - Plottable Protocol
   - .plot() on SpectralArray, MTF1D, MTFBudget, EffectivePSF,
     NoiseBudget, kernels
3. src/radiant/api/inspect.py
   - ChainResult.inspect() tree browser
   - result.plot attribute
4. Tests for the API
5. examples/scripts/:
   - basic_evaluation.py
   - aperture_sweep.py
   - tolerance_analysis.py
   - compare_configs.py
   - custom_loop.py

Report: files, tests, output of running each example script.
```

### Prompt 2E.2 — Full CLI

```
Task: Implement all CLI commands.

Read first:
- docs/RADIANT_Config_Format.md (CLI section)

Produce:
1. Extend src/radiant/cli/main.py:
   - run, validate, new (guided builder), template, sweep, tolerance,
     compare, explain, convert, library, schema
2. src/radiant/cli/guided.py — interactive config wizard
3. src/radiant/cli/templates.py — 12 canonical sensor templates
4. Tests for each command
5. Auto-generated CLI reference docs

Report: full CLI help text, test results.
```

### Prompt 2E.3 — Data library and presets

```
Task: Populate the data library.

Read first:
- docs/RADIANT_Source_Target_System.md (material library section)
- docs/RADIANT_Scope_Decisions.md (what's IN for v1)

Produce:
1. src/radiant/data/spectral_library/
   - ~20 material emissivity/reflectance spectra
   - Sources documented in manifest
2. src/radiant/data/detectors/ — QE curves for 6 materials
3. src/radiant/data/atmosphere/ — 3 standard cases
4. src/radiant/data/solar/ — ASTM G-173 reference
5. examples/templates/ — 12 complete YAML templates
6. src/radiant/data/library.py — SpectralLibrary class
7. Tests verifying every library file loads and is physically plausible

Report: library contents, validation results.
```

### Prompt 2E.4 — Documentation

```
Task: Write comprehensive user documentation.
Category: D

Read first:
- docs/RADIANT_Personas.md — 6 personas (systems engineer, detector engineer,
  mission planner, analyst, optical designer, researcher). Every guide must
  serve at least one named persona. Note the persona at the top of each guide.
- docs/RADIANT_Config_Format.md — canonical YAML structure, import/override
  mechanics, inline comment conventions
- docs/RADIANT_Parameter_System.md — dot-path naming, resolution, defaults,
  consistency groups, tolerance distributions
- docs/RADIANT_Signal_Chain_Architecture.md — 7-stage chain, ChainState flow,
  RadiometricFrame
- docs/RADIANT_Conventions.md — canonical units, coordinate system, spectral
  variable (wavelength in µm)
- docs/RADIANT_Scope_Decisions.md — what is intentionally deferred
- src/radiant/api/sensor.py — Sensor class: from_yaml, from_dict, set, get,
  evaluate, sweep, sweep_2d, monte_carlo, sensitivity, clone, summary, explain
- src/radiant/cli/main.py — 9 CLI commands: run, validate, explain, sweep,
  tolerance, compare, schema, template, convert
- src/radiant/data/library.py — SpectralLibrary: materials(), material(),
  detector_qe(), detectors(), solar()
- examples/scripts/ — 5 example scripts (basic_evaluation, aperture_sweep,
  tolerance_analysis, compare_configs, custom_loop)
- examples/templates/ — 12 YAML templates spanning VNIR/SWIR/MWIR/LWIR,
  LEO/aerial/GEO/ground

Audience hierarchy (from Personas doc):
  Primary:   Sarah (systems engineer) — sweep, trade, quick answers
  Secondary: Raj (mission planner) — load config, run scenario, yes/no
  Tertiary:  Mike (detector), Tom (optics), Dr. Chen (researcher)

Produce the following files. Every code block must be runnable against the
current codebase (tested in the final verification step).

─── User Guides ───────────────────────────────────────────────────────

1. docs/guides/quickstart.md
   Persona: Sarah (systems engineer), Raj (mission planner)
   Content:
   - Install (pip install -e ".[dev]")
   - "Your first evaluation" — load examples/mwir_leo_minimal.yaml via CLI
     (`radiant run`) AND via Python (`Sensor.from_yaml`), show SNR output
   - "Your first sweep" — `radiant sweep` CLI AND `sensor.sweep()` Python
   - "Exploring results" — `result.metrics`, `sensor.explain()`,
     `radiant explain`
   - "Next steps" — links to configuration.md, scripting.md, trade_studies.md
   Constraints:
   - Must be completable in < 5 minutes by someone who has never seen RADIANT
   - Every CLI command shown must also show the Python equivalent
   - Use the mwir_leo_minimal.yaml that ships with the repo (not a made-up example)

2. docs/guides/configuration.md
   Persona: Sarah, Raj, Lisa (analyst)
   Content:
   - YAML structure overview — top-level keys (source, atmosphere, geometry,
     optics, detector, spectral_integration, readout) with one annotated example
   - Parameter dot-path convention (e.g. `optics.f_number`)
   - How defaults work — what you can omit, what you must specify
   - The `--set key=value` override mechanism (CLI) and `sensor.set()` (Python)
   - Consistency groups — f/# = f/D example, what happens on conflict
   - Units — input units vs. canonical units, `radiant convert` utility
   - Using templates as starting points (`radiant template list/show/create`)
   - Loading MODTRAN atmosphere files
   - Common configuration patterns: "I want to change one parameter and re-run",
     "I want to compare two configs", "I want to batch 50 scenarios"
   Constraints:
   - Include a fully annotated YAML showing every section (not all 91 params,
     but the ~25 most commonly used ones with inline # comments)
   - Cross-reference parameter_reference.md for the exhaustive list

3. docs/guides/scripting.md
   Persona: Sarah, Tom (optical designer), Dr. Chen (researcher)
   Content:
   - Sensor class API walkthrough: from_yaml, from_dict, set/get, evaluate
   - Working with ChainResult: metrics dict, stage_outputs, frames, noise_terms
   - Sweeps: sensor.sweep() and sensor.sweep_2d() with plotting
   - Monte Carlo tolerance: sensor.monte_carlo() and sensor.set_tolerance()
   - Sensitivity analysis: sensor.sensitivity()
   - Using SpectralLibrary for material/detector/solar data
   - Cloning sensors for comparison: sensor.clone()
   - Custom analysis loops (reference examples/scripts/custom_loop.py pattern)
   - Exporting results to CSV/JSON
   Constraints:
   - Every code block must be self-contained (imports + setup visible)
   - Reference the 5 example scripts in examples/scripts/ as "see also"
   - Do NOT show matplotlib plotting code in the main guide — mention that
     the plot functions exist and link to the API, but keep focus on the
     data/computation side

4. docs/guides/parameter_reference.md
   Auto-generated from _schema.py files across all stages.
   Content:
   - Table for each stage: parameter name, type, default, unit, bounds, description
   - Organized by stage: source, atmosphere, geometry, optics, detector,
     spectral_integration, readout
   - Consistency groups listed separately
   - Mark which parameters are required (no default) vs. optional
   Generation approach:
   - Write a script `scripts/gen_param_reference.py` that imports
     build_parameter_set() from radiant.api._param_registry, iterates over
     all 91 ParameterDefs, and writes the markdown table
   - Run the script as part of the build; include the output in the guide
   - The script itself is also committed (so the doc can be regenerated)

5. docs/guides/regime_selection.md
   Persona: Sarah, Raj
   Content:
   - What is a radiometric regime? (extended-scene, sub-pixel, point-source)
   - How RADIANT classifies: SourceStage tentative → OpticsStage final
   - When to use each regime:
       extended-scene: target >> pixel IFOV (buildings, terrain)
       sub-pixel: target < pixel IFOV but > diffraction (small vehicles)
       point-source: target << diffraction limit (stars, distant missiles)
   - How fill_fraction and projected_area_m2 interact with regime
   - Where EE_box is applied and where it is not (Rule 9)
   - Common pitfall: "I set the wrong regime and got nonsense SNR"
   - How to override: source.regime_override parameter
   Constraints:
   - Include a decision flowchart (text-based, not image)
   - Show a concrete example for each regime using real templates

6. docs/guides/trade_studies.md
   Persona: Sarah, Tom
   Content:
   - 1D parameter sweep workflow (CLI + Python)
   - 2D parameter sweep workflow (Python only — sweep_2d)
   - Monte Carlo tolerance analysis workflow
   - Sensitivity analysis workflow (which parameter matters most?)
   - Comparing configurations side by side
   - Interpreting results: SNR vs. aperture curves, noise budget waterfall,
     MTF component breakdown
   - Worked example: "What aperture do I need for SNR ≥ 50?" — complete
     walkthrough from config to answer
   Constraints:
   - Every worked example uses templates that ship in examples/templates/
   - Show both CLI and Python paths where both exist

─── Theory Documents ──────────────────────────────────────────────────

7. docs/theory/radiometric_chain.md
   Persona: Dr. Chen (researcher), Mike (detector), Tom (optics)
   Content:
   - The 7-stage signal chain with governing equations:
       source: Planck function, emissivity coupling, regime classification
       atmosphere: Beer-Lambert, τ_atm, L_path, L_downwelling
       optics: throughput (A_pixel × Ω × τ_optics), PSF/MTF, thermal self-emission
       spectral_integration: ∫ over bandpass, QE weighting, EE_box coupling
       detector: noise model (cross-ref noise_model.md)
       readout: TDI, gain, ADC, coadd
       performance: SNR, NEDT, NIIRS (GIQE-5), system MTF
   - Units trace through the chain (dimensional audit table format)
   - What each stage adds to ChainState
   - Assumptions and limitations (list from Scope_Decisions.md)
   Constraints:
   - Equations in LaTeX (MathJax-compatible for mkdocs)
   - Every equation must match the implementation — verify against the actual
     code in each stage.py
   - Cross-reference the implementation file for each equation

8. docs/theory/noise_model.md
   Persona: Mike (detector), Dr. Chen
   Content:
   - Complete noise taxonomy: photon shot, dark current shot, read noise,
     quantization, DSNU, PRNU, 1/f, glow, kTC
   - Equation for each noise term (in electrons)
   - RSS combination: total_noise = sqrt(Σ σ_i²)
   - Dark current vs. temperature (Rule 07 / Arrhenius)
   - CDS noise reduction factor
   - TDI noise scaling
   - When each term dominates (BLIP regime, read-noise-limited, dark-limited)
   - Cross-reference detector parameters from parameter_reference.md
   Constraints:
   - Match equations to the actual implementation in detector/stage.py and
     readout/stage.py
   - Use the same variable names as the code

9. docs/theory/spatial_model.md
   Persona: Tom (optical designer), Sarah
   Content:
   - PSF construction: diffraction (Airy/obscured), wavefront error, defocus
   - MTF decomposition: MTF_optics × MTF_detector × MTF_smear × MTF_jitter ×
     MTF_electronics
   - Polychromatic PSF (photon-flux-weighted average across band)
   - Encircled/ensquared energy: EE_box from PSF (Rule 4 — single PSF for both
     MTF and EE)
   - Smear MTF: velocity/altitude model
   - Jitter MTF: Gaussian jitter model
   - Detector MTF: sinc(f × pitch) × fill factor
   - NIIRS via GIQE-5: equation, input terms, relationship to MTF/SNR/GSD
   - RER (Relative Edge Response) derivation from MTF
   Constraints:
   - Match equations to optics/psf.py, optics/mtf.py, platform/stage.py,
     performance/stage.py
   - Emphasize Rule 4 (single PSF source of truth)

─── Build Configuration ───────────────────────────────────────────────

10. mkdocs.yml
    - Use mkdocs-material theme
    - Navigation:
        Home: index.md (brief intro + link to quickstart)
        User Guides: quickstart, configuration, scripting, parameter_reference,
                     regime_selection, trade_studies
        Theory: radiometric_chain, noise_model, spatial_model
        Developer: link to CLAUDE.md, architecture docs
    - Enable MathJax for LaTeX equations
    - Enable code highlighting (Python, YAML, bash)
    - Enable search
    - Do NOT add mkdocs or mkdocs-material to the project's install_requires —
      they are doc-build-only dependencies. Note them in a comment in mkdocs.yml.

11. docs/index.md
    - One-paragraph description of RADIANT
    - "Get started in 5 minutes" link to quickstart.md
    - Feature list (6 bullets: signal chain, sweep, tolerance, CLI, scripting,
      data library)
    - Link to each guide and theory doc

─── Verification ──────────────────────────────────────────────────────

12. Code-in-docs test
    - Write scripts/test_docs_code.py that:
      a. Finds all ```python blocks in docs/guides/*.md
      b. Extracts each block
      c. Executes it (exec() with a shared namespace per file)
      d. Reports pass/fail per block with file:line reference
    - Run it and fix any broken examples before declaring complete
    - Also run: mkdocs build --strict (if mkdocs is installed) or at minimum
      verify all internal markdown links resolve (no broken [text](path.md) refs)

─── Constraints ───────────────────────────────────────────────────────

- All code examples must use the CURRENT API (Sensor class, CLI commands,
  SpectralLibrary) — not hypothetical future features
- Do not document features listed as deferred in Scope_Decisions.md
- Do not invent parameter names — cross-check against the actual 91 parameters
  from build_parameter_set()
- Keep guides concise: quickstart ≤ 200 lines, configuration ≤ 400 lines,
  scripting ≤ 400 lines, trade_studies ≤ 350 lines, regime ≤ 250 lines
- Theory docs may be longer (up to 500 lines each) but should be scannable
  with clear section headers
- Use relative links between docs (e.g. [configuration](configuration.md))
- No print() in code examples that import from radiant — the library uses
  logging, and code examples should use the returned values directly

Report: Category D task report. Include:
- mkdocs build result (or link-check result if mkdocs not installed)
- Code-in-docs test results (pass/fail per code block)
- List of which persona each guide serves
- Regression: full test suite still passes (1530+ tests)
```

### Prompt 2E.5 — Error message audit

```
Task: Audit and improve error messages.

Review every raise statement. For each:
- What happened?
- Why?
- What to do?

Improve any that fall short. Add tests for error message quality.

Verify:
- Every Parameter has meaningful description
- Every validation error points to offending parameter
- Resolver gives specific "add X to compute Y" messages

Report: before/after examples of improved messages.
```

### Prompt 2E.6 — Release prep

```
Task: Final quality pass.

1. Full test suite with coverage (target 85% overall, 90% core)
2. mypy --strict (zero errors)
3. ruff (zero warnings)
4. Profile: < 1s draft fidelity, < 10s publication fidelity
5. Resolve all TODO/FIXME/XXX comments
6. Verify all docs/RADIANT_*.md files are accurate
7. CHANGELOG.md with v0.1.0 entry
8. RELEASE_NOTES.md listing stubs and deferrals from Scope_Decisions
9. Tag v0.1.0

Report: coverage, type check, lint results, profile, remaining issues.
```

**CHECKPOINT 2E:** Final acceptance testing. Tag v0.1.0. Ship.

---

## Operating principles

Same as the ad-hoc version:

1. **One task per conversation** — never multiple tasks in one prompt
2. **Read first is mandatory** — every prompt loads specific docs
3. **Test before merge** — never accept incomplete tests
4. **No feature creep** — stay in the task's scope
5. **Architectural violations are stop-the-line** — agent must ask
6. **Golden tests are sacred** — never changed silently
7. **Per-phase checkpoints are mandatory** — human review between phases

---

## Why this version is faster than the ad-hoc version

| Aspect | Ad-hoc Phase 2 | Clean-start Phase 2 |
|--------|---------------|---------------------|
| Docs to reference | 33 documents | ~20 documents |
| Ambiguous versions | "Read both versions of X" | Single doc per subsystem |
| Split subsystems | Target types + geometry + materials | Unified source/target system |
| Noise model evolution | Added in pieces across 4 docs | Complete from the start |
| Readout chain | Retrofitted via update doc | Complete from the start |
| Motion sources | Added after initial spatial design | Designed as one unit |
| Supersession table | Needed to resolve conflicts | Not needed — no conflicts |
| Agent confusion | "Which doc is authoritative?" | Zero ambiguity |

The agent spends less time hunting for the right document and less
time reconciling contradictions. Estimated ~15% time savings on
coding tasks, with fewer rework cycles.

---

## Effort comparison

| Phase | Ad-hoc Phase 2 | Clean-start Phase 2 |
|-------|---------------|---------------------|
| 2A Foundation | 8-12 hours | 8-12 hours (same) |
| 2B MVP Chain | 15-20 hours | 14-18 hours |
| 2C Spatial | 12-18 hours | 11-16 hours |
| 2D Full Chain | 25-35 hours | 22-30 hours |
| 2E Polish | 15-20 hours | 14-18 hours |
| **Total** | **75-105 hours** | **69-94 hours** |
| **Wall time** | **7-10 weeks** | **6-9 weeks** |

The savings come from clean document set and reduced ambiguity.
Not dramatic, but meaningful — roughly one week of wall time saved
across the project.

---

## Total project effort (Phase 1 + Phase 2, clean start)

| | Ad-hoc | Clean |
|---|---|---|
| Phase 1 Architecture | 30+ hours | 15-20 hours |
| Phase 2 Implementation | 75-105 hours | 69-94 hours |
| **Total** | **105-135 hours** | **84-114 hours** |
| **Wall time** | **~10-14 weeks** | **~8-11 weeks** |

The clean start saves ~2-3 weeks of wall time and ~20-30 hours of
direct effort. The bigger win is quality: cleaner architecture
produces cleaner code with fewer defects discovered late.
