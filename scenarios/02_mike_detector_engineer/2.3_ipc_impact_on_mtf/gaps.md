# Scenario 2.3 — Gaps

## Gap 1: IPC kernel applied at PSF sample spacing instead of pixel pitch
**Severity**: Medium
**Status**: OPEN (partially fixed — IPC is wired in but kernel sampling is incorrect)
**Description**: RADIANT now wires IPC into the signal chain: `DetectorStage` generates
the 3x3 IPC kernel and `PerformanceStage` convolves it with the EffectivePSF via
`with_kernel()`. However, the 3x3 IPC kernel is defined on the **pixel grid** (one
sample per pixel), while the EffectivePSF is on a **finer sub-pixel grid** (many samples
per pixel). The `with_kernel()` method pads the 3x3 kernel into the PSF grid and
convolves at the PSF sample spacing, making the IPC effect orders of magnitude smaller
than it should be.

Evidence: At IPC alpha = 5%, the analytic MTF_IPC at Nyquist should be 0.80 (= 1 - 4*0.05),
reducing system MTF from 0.2532 to ~0.2025. But the native convolution produces 0.2514
(less than 1% reduction). The MTF product path correctly computes `mtf_ipc_x = 0.80` via
the analytic formula, causing the dual-path consistency check to fail at alpha > 2.5%.

**Fix**: The IPC kernel must be upsampled to the PSF sample grid before convolution.
Each pixel-width step in the IPC kernel maps to `pixel_pitch / sample_spacing` samples
in the PSF. Alternatively, apply IPC as a pixel-domain operation after resampling the
PSF to pixel pitch, then resample back.

**Workaround**: Multiply RADIANT's baseline system MTF by the analytic IPC MTF formula:
`MTF_system_with_IPC = MTF_system_no_IPC * (1 - 4*alpha)` at Nyquist. This is exact
for the nearest-neighbor 4-connected kernel. The script uses this approach for the
requirements analysis.

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
