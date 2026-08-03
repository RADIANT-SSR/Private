# Scenario 2.3 — Gaps

## Gap 1: IPC kernel applied at PSF sample spacing instead of pixel pitch
**Severity**: Medium
**Status**: CLOSED (kernel sampling corrected; native convolution now matches the analytic form)
**Description**: RADIANT wires IPC into the signal chain: `DetectorStage` generates
the 3x3 IPC kernel and `PerformanceStage` convolves it with the EffectivePSF via
`with_kernel()`. An earlier build convolved the pixel-grid kernel at the *PSF* sample
spacing rather than at pixel pitch, making the IPC effect orders of magnitude smaller
than it should be (at alpha = 5%: analytic 0.2025 vs native 0.2514 on that build's
0.2532 baseline).

Evidence of closure: at the current baseline system MTF of 0.2668, the native
convolution tracks `MTF_system_no_IPC * (1 - 4*alpha)` to within rounding across the
full 0–5% sweep — Δ = 0.0000 at alpha = 0%, 0.0002 at 2%, and a worst case of 0.0005 at
alpha = 5% (native 0.2139 vs analytic 0.2134). The dual-path consistency check no longer
fails at high alpha.

**Cross-check retained**: `MTF_system_with_IPC = MTF_system_no_IPC * (1 - 4*alpha)` at
Nyquist is exact for the nearest-neighbor 4-connected kernel and remains a useful hand
validation. The script now quotes RADIANT's native values for the requirements analysis
and reports the analytic form alongside them as a cross-check.

*Numbers refreshed 2026-08-02 from the unmodified runner (previous vintage 2026-07-22 for the walkthrough; this file was not refreshed in that pass). The values corrected here are pre-2026-07-22 kernel-sampling residue, not movement from any in-window Results-affecting landing.*

## Gap 2: SNR = 0 at orbital altitude (FIXED)
**Severity**: High (was blocking)
**Status**: FIXED
**Description**: The atmosphere model previously returned zero transmission at 500 km due
to a bug in how water vapor extinction was scaled with altitude. This caused SNR = 0 for
any LEO scenario. Fixed — the model now uses column-integrated optical depth with proper
exponential scale heights.

## Gap 3: No support for arbitrary IPC kernel
**Severity**: Low
**Status**: OPEN
**Description**: RADIANT only accepts a scalar nearest-neighbor coupling fraction (alpha).
Mike has a full 5x5 IPC kernel from knife-edge measurements that includes diagonal
coupling. The current implementation cannot accept this.
**Workaround**: Use the scalar alpha as an approximation of the dominant coupling mode.

## Gap 4: No IPC correction/deconvolution model
**Severity**: Low
**Status**: OPEN
**Description**: Mike wants to see MTF "with and without IPC correction applied" — i.e.,
what happens if post-processing deconvolves the IPC kernel. RADIANT does not model
post-processing corrections.
**Workaround**: Not available; would require a separate analysis.
