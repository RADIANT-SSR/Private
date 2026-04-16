# Scenario 2.3 — Gaps

## Gap 1: IPC not wired into signal chain
**Severity**: Medium
**Description**: RADIANT has the IPC parameter (`detector.ipc_coupling`) and the IPC MTF math (`radiant.detector.ipc`), but no stage currently applies IPC to the system MTF or EffectivePSF. The IPC kernel exists but is never convolved with the PSF or multiplied into the MTF cascade.
**Workaround**: Script computes IPC MTF analytically using `ipc_mtf_1d()` and multiplies it with RADIANT's baseline system MTF post-hoc.
**Recommendation**: Wire IPC into the detector stage so that `ipc_coupling` automatically applies the IPC kernel to the EffectivePSF before MTF and EE are computed.

## Gap 2: SNR = 0 at orbital altitude (FIXED)
**Severity**: High (was blocking)
**Description**: The atmosphere model previously returned zero transmission at 500 km due to a bug in how water vapor extinction was scaled with altitude. This caused SNR = 0 for any LEO scenario.
**Status**: FIXED — the model now uses column-integrated optical depth with proper exponential scale heights.
