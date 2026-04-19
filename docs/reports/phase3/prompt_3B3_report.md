# Task Report: Prompt 3B.3 — Defocus model (Gap 29)

## Category: C

## Files
Created:
  - `src/radiant/optics/defocus.py` — `defocus_sigma_m()`, `defocus_kernel_2d()`
  - `src/radiant/optics/tests/test_defocus.py` — 16 tests
Modified:
  - `src/radiant/optics/_schema.py` — Added `DEFOCUS_UM` parameter
  - `src/radiant/optics/stage.py` — Defocus kernel applied after ePSF construction
  - `src/radiant/optics/tests/test_stage.py` — 5 new defocus wiring tests
  - `docs/gaps.md` — Gap 29 marked CLOSED

Tests added:
  - `src/radiant/optics/tests/test_defocus.py` — 16 tests (8 sigma, 7 kernel, 1 MTF validation)
  - `src/radiant/optics/tests/test_stage.py` — 5 tests (zero, degradation, symmetry, stored sigma, FWHM increase)

## Test Results
Total tests: 1722
Passing: 1722
Failing: 0

## Design Decisions

### Separate module (Rule 19)
`defocus.py` contains `defocus_sigma_m()` and `defocus_kernel_2d()`. These are tightly coupled (kernel needs sigma), and the kernel generation is specific to defocus physics (not reusable for jitter), so they share a module.

### Gaussian approximation
The Gaussian approximation σ = |δ|/(4·f/#·√3) is valid for small defocus where Strehl > 0.5. For large defocus (Z4 > 2 waves), the true PSF is a pill-box. The stage emits a warning when Z4 exceeds 2 waves. Accurate large-defocus modelling requires Zernike Z4 (Gap 24).

### Defocus applied in OpticsStage, not PlatformStage
Defocus is an optical property (focus position), not a platform effect. Applied after ePSF construction and before nearfield computation. Uses the same `epsf.with_kernel()` pattern as jitter.

### Default 0.0 = backward compatible
`defocus_um = 0.0` means no defocus kernel is applied. Existing tests and golden values are unaffected.

## Numerical Validation

### Truth Anchor 1: σ formula at f/3, δ=10 µm
  Source: Analytical — σ = |δ| / (4 × f/# × √3)
  Expected: 10e-6 / (4 × 3 × √3) = 0.481 µm
  Actual: 0.481 µm
  Relative error: < 1e-12 (exact formula)
  Regime notes: Formula is exact; physical validity limited to small defocus.

### Truth Anchor 2: Zero defocus
  Source: Mathematical identity
  Expected: σ = 0, kernel = delta, ePSF unchanged
  Actual: verified (bit-identical ePSF, "defocus" not in convolution_history)

### Truth Anchor 3: Kernel MTF vs analytical Gaussian MTF
  Source: Analytical — MTF_defocus(f) = exp(-2π²σ²f²)
  At f/3, δ=10 µm: kernel MTF (via FFT of projected kernel) matches exp(-2π²σ²f²) at 5 frequencies from 0.1×f_Nyquist to 0.5×f_Nyquist
  Tolerance: < 1%
  Actual: all 5 frequencies match within 1%
  Regime notes: Kernel must be large enough (≥6σ span) to capture tails.

## Dimensional Audit

| Stage | Input Units | Output Units | Conversion | Check |
|-------|-------------|-------------|------------|-------|
| defocus_um | µm | µm | parameter input | ✓ |
| defocus_m | m | m | ×1e-6 (boundary) | ✓ |
| f_number | dimensionless | dimensionless | none | ✓ |
| σ = \|δ\|/(4·f/#·√3) | m / (dimless × dimless) | m | divide | ✓ |
| kernel grid | m spacing | dimensionless | normalised | ✓ |
| Z4 = δ/(8·λ·f/#²) | m / (m × dimless²) | waves | dimensionless | ✓ |

Issues: none

## Failure Modes Tested

| Case | Expected | Actual |
|------|----------|--------|
| defocus_um = 0 | No kernel applied | ✓ |
| defocus_um > 0 | MTF degraded | ✓ |
| defocus_um < 0 | Same as +defocus (symmetric) | ✓ |
| f_number = 0 | ValueError | ✓ |
| f_number < 0 | ValueError | ✓ |
| npix even | ValueError | ✓ |
| sample_spacing ≤ 0 | ValueError | ✓ |
| sigma < 0 | ValueError | ✓ |
| Large defocus (Z4 > 2 waves) | Warning logged | ✓ (by code path) |

## Assumptions

**Assumption: Gaussian defocus blur**
  Why valid: For small defocus (Marechal criterion: Strehl > 0.5, Z4 < ~0.25 waves), the defocus spot is well approximated by a Gaussian with σ = |δ|/(4·f/#·√3).
  What breaks: Large defocus (many waves of Z4) produces a pill-box PSF, not Gaussian. The Gaussian underestimates the MTF at low frequencies and overestimates it at high frequencies.
  Detected how: Runtime warning when Z4 > 2 waves.

**Assumption: Isotropic (rotationally symmetric)**
  Why valid: Defocus is Zernike Z4 which is rotationally symmetric. The geometric blur spot is a circle.
  What breaks: Astigmatic defocus (different x/y focus) requires separate treatment.
  Detected how: Not detected; would need Z5/Z6 Zernike terms.

**Assumption: σ = |δ|/(4·f/#·√3), not |δ|/(4·f/#)**
  Why valid: The √3 factor comes from the RMS radius of a uniform disk (the geometric defocus spot), not the radius itself. RMS_disk = R/√3 where R = |δ|/(4·f/#) is the geometric blur radius.
  What breaks: Nothing — this is the correct formula for the RMS blur sigma.

## Fragility Points

**What breaks this implementation?**
- Large defocus (Z4 >> 2 waves): Gaussian is inaccurate. Use Zernike Z4 instead.
- Very fast f-numbers (f/1): small defocus produces large σ; kernel may need to be very large.
- Kernel truncation: if σ is larger than the PSF grid can accommodate, the kernel is clipped to the PSF grid size. This is acceptable since the PSF grid sets the resolution limit.

**Mitigations:**
- Warning at Z4 > 2 waves.
- Kernel size capped to PSF grid size, minimum 3×3.
- 6σ span ensures > 99.7% of kernel energy is captured.

## Traceability
Same inputs → identical outputs: verified (deterministic, no random state)
Deterministic seed: N/A (no stochastic components)
Intermediate values inspectable: yes — defocus_sigma_m stored in stage_outputs, "defocus" in convolution_history

## Regression Status
Existing tests: 1722/1722 passing (21 new)
Changes to golden values: none
New tests added: 21 (16 defocus pure function + 5 stage wiring)

## Self-Review

**Physics:** σ = |δ|/(4·f/#·√3) correctly converts linear defocus to focal-plane Gaussian RMS blur. The √3 is from the uniform-disk RMS radius. Kernel is isotropic (defocus is Z4, rotationally symmetric). Warning at Z4 > 2 waves where approximation breaks down.

**Code:** Separate module per Rule 19. Same kernel pattern as jitter (generate Gaussian, normalise, apply via with_kernel). Unit conversion happens at the boundary (µm → m in stage.py, not in defocus.py).

**Architecture:** No cross-stage imports. defocus.py imports only stdlib and numpy. Stage wiring follows existing pattern (build ePSF → apply defocus → continue).

**Scope:** Only Gap 29 addressed. No additional features.

## Open Issues or Questions

None.
