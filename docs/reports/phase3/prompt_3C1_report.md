# Task Report: Prompt 3C.1 — Wire smear into MTF chain

## Category: C

## Files
Modified:
  - src/radiant/platform/_schema.py (added GROUND_VELOCITY_M_S, SMEAR_LENGTH_UM)
  - src/radiant/platform/stage.py (added smear computation after jitter, _compute_smear_width)
  - src/radiant/platform/tests/test_stage.py (added 12 smear tests)

## Test Results
Total tests (platform): 92
Passing: 92
Failing: 0
Total tests (full suite): 1734
Passing: 1734
Failing: 0

## Numerical Validation

### Truth Anchor 1: Smear MTF sinc formula
  Source: Analytic sinc MTF: |sinc(pi * f * smear_width)|
  Expected: sinc values at frequencies below 0.5 * f_Nyquist
  Actual: Kernel-derived MTF ratio (smeared/original) matches within atol=0.05
  Absolute error: < 0.05 at low-mid frequencies
  Relative error: < 5%
  Regime notes: Discrete rect kernel diverges from continuous sinc at high frequencies due to finite grid sampling

### Truth Anchor 2: Smear width at nadir (velocity-based)
  Source: Hand calculation: v/H * f * t_int = 7000/600000 * 5.0 * 0.0001 = 5.833e-6 m
  Expected: 5.833e-6 m
  Actual: 5.833e-6 m (via test_velocity_based_smear_width)
  Absolute error: < 1% (spherical model vs flat Earth)
  Relative error: < 0.01
  Regime notes: At nadir, slant_range = altitude, so flat-Earth and spherical agree

### Truth Anchor 3: Direct override (smear_length_um)
  Source: Direct input: 10 µm → 10e-6 m canonical
  Expected: smear_width_m = 10e-6 m
  Actual: 10e-6 m
  Absolute error: 0
  Relative error: 0
  Regime notes: Direct override bypasses velocity computation entirely

### Truth Anchor 4: Zero smear identity
  Source: Mathematical identity: convolution with zero-width rect = identity
  Expected: ePSF unchanged (object identity)
  Actual: ePSF is epsf_orig (identity check passes)
  Absolute error: 0
  Relative error: 0
  Regime notes: N/A

## Dimensional Audit

| Stage              | Input Units       | Output Units   | Conversion         | Check |
|--------------------|-------------------|----------------|--------------------|-------|
| smear_length_um    | µm (input)        | m (canonical)  | ParameterSet ×1e-6 | pass  |
| ground_velocity    | m/s               | m/s            | none               | pass  |
| sensor_altitude    | m                 | m              | none               | pass  |
| path_zenith_rad    | rad               | rad            | none               | pass  |
| integration_time   | s                 | s              | none               | pass  |
| slant_range        | m                 | m              | spherical model    | pass  |
| angular_rate       | m/s / m = rad/s   | rad/s          | divide             | pass  |
| smear_width        | rad/s * m * s = m | m              | multiply           | pass  |
| kernel spacing     | m                 | m              | from ePSF          | pass  |
| kernel_2d          | dimensionless     | dimensionless  | normalized sum=1   | pass  |

Issues: none

## Failure Modes Tested
- Zero velocity + zero smear_length_um: no smear applied (test_zero_smear_preserves_epsf)
- velocity > 0 but no altitude param: graceful skip via try/except (stage._compute_smear_width)
- velocity > 0 but no integration_time param: graceful skip via try/except
- Smear larger than half PSF grid: logger.warning issued, kernel clamped to grid size
- smear_length_um overrides ground_velocity when both set (test_direct_overrides_velocity)
- No ePSF from optics: skip all spatial operations, still store smear_width_m

## Assumptions

Assumption: Along-track smear only (y-axis)
  Why valid: Platform motion is primarily along-track; cross-track smear from scan mechanisms is deferred
  What breaks: If cross-track smear is significant, FWHM_x will be under-estimated
  Detected how: Documentation; future prompt (scan smear)

Assumption: Rect kernel approximation for uniform motion
  Why valid: Constant velocity during integration produces uniform blur
  What breaks: Non-uniform motion (acceleration, vibration harmonics) produces non-rect kernels
  Detected how: Documentation; user must verify motion is approximately uniform

Assumption: Slant range approximation for angular rate
  Why valid: omega = v_ground / slant_range is geometrically correct for along-track motion
  What breaks: Very high off-nadir angles (>80 deg) where Earth curvature significantly changes the projection
  Detected how: slant_range_spherical_m handles curvature; tested at 45 deg off-nadir in smear.py tests

## Fragility Points
- Discrete rect kernel: finite grid means the rect width is quantized to integer samples. For very small smear (<< 1 sample), the kernel reduces to a delta. This is physically correct (sub-sample smear has negligible effect on the sampled PSF).
- 2-D kernel construction: outer product delta_x * rect_y introduces small cross-coupling in FWHM_x (~4%) due to discrete convolution on a finite grid. This is a numerical artifact, not a physics error.
- Large smear (>50% of PSF grid): kernel is clamped to grid size, warning issued. Results become unreliable at this point — increase PSF grid size.

## Traceability
Same inputs -> identical outputs: verified (deterministic convolution, no random state)
Deterministic seed: N/A (no stochastic components)
Intermediate values inspectable: yes (smear_width_m, convolution_history via stage_outputs)

## Cross-Model Consistency
- smear_mtf_1d() analytic sinc vs. kernel-derived MTF ratio: agree within atol=0.05 at frequencies < 0.5 * f_Nyquist
- 2-D kernel verified: y-axis broadened (FWHM_y increases), x-axis approximately unchanged (within 5%)

## Regression Status
Existing tests: 1734 / 1734 pass
Changes to golden values: none
New tests added: 12 (in test_stage.py)

## Self-Review
Physics: Smear width = (v/slant_range) * focal_length * t_int is dimensionally consistent [m]. Rect kernel produces sinc MTF, verified analytically. Slant range used instead of altitude for off-nadir consistency.
Code: Pure function stage, no mutation of inputs. All outputs via with_stage_output. No cross-stage imports (slant_range from core.geometry is allowed per Rule 11).
Architecture: Two new ParameterDefs in _schema.py with proper naming, bounds, and units. Stage follows existing jitter pattern. Rule 19 satisfied — smear.py already exists as its own module.
Scope: Only platform along-track smear (source 1). Scan and target smear deferred per prompt spec.

## Open Issues or Questions
- None. Implementation matches prompt spec exactly.
