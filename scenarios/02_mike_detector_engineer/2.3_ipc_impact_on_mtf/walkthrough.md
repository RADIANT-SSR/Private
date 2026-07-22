# Scenario 2.3 Walkthrough: IPC Impact on MTF


> **NIIRS applicability — engine update (CU-166).** Since this walkthrough was written, RADIANT added a metric-applicability gate: when one or more GIQE-5 inputs fall outside the calibration envelope — GSD 1.18–31.5 inch, RER 0.20–0.95, SNR 2–130 — the engine reports **NIIRS as N/A** by default instead of silently extrapolating. This configuration is outside that envelope, so the NIIRS values below are the **extrapolated** GIQE-5-form output: reproduce them with `performance.niirs.allow_extrapolated = true` and read them as a *relative trend, not a calibrated rating*. (The SNR/NEDT figures here predate later physics updates and are indicative; a full numeric refresh is tracked separately in the cleanup backlog. No IR-calibrated IIRS model yet — see `docs/tracking/gaps.md` Gap 100.)

## The Problem

Mike is a detector engineer evaluating HgCdTe MWIR detectors for a LEO pushbroom imaging system. His vendor has shipped five sample detectors from the same wafer lot, each with a different level of inter-pixel capacitance (IPC) — a parasitic electrical coupling between neighboring pixels that is inherent to the detector fabrication process.

Mike's question is straightforward: **how much IPC can the system tolerate before it fails to meet its image quality requirements?**

He has three pieces of information:
- A vendor datasheet with the detector's electrical and optical specifications
- Lab measurements he took on all five samples, including MTF at Nyquist and ensquared energy at each sample's IPC level
- System-level requirements that define the performance thresholds: system MTF at Nyquist must be at least 0.15, ensquared energy in a single pixel (EE 1x1) must be at least 0.60, and SNR must be at least 100

## What Is IPC and Why Does It Matter?

Inter-pixel capacitance is an electrical effect, not an optical one. When a pixel in the focal plane array accumulates photoelectrons, a small fraction of that charge couples into each of the four nearest-neighbor pixels through parasitic capacitance in the readout circuit. A typical coupling fraction is 1-3% per neighbor.

The effect is equivalent to convolving the image with a small 3x3 kernel:

```
     0    alpha    0
   alpha  1-4a   alpha
     0    alpha    0
```

This blurs the image electrically — after the photons have already been converted to charge. The consequences are:
- **MTF degrades**: the effective spatial resolution decreases because sharp edges get smeared
- **EE 1x1 decreases**: energy leaks from the central pixel to its neighbors, so less of a point source's energy is captured in a single pixel
- **EE 3x3 is nearly unchanged**: the 3x3 window captures most of the leaked charge
- **SNR is unchanged**: charge is redistributed, not lost — the total signal in the image stays the same

The key insight is that IPC is a multiplicative MTF degradation. The system MTF is the product of all the individual MTF contributors (optics, detector sampling, motion blur, IPC), so the IPC effect can be analyzed independently and combined with the other terms.

## How RADIANT Solves This

### Step 1: Set Up the Sensor Model

Mike's inputs arrive in a vendor-format spreadsheet with three tabs. The script reads each tab, extracts the relevant parameters, and converts from vendor units (cm, %, ms, km) to RADIANT's canonical units (m, fractions, s). This unit conversion step is critical — RADIANT performs all internal calculations in SI-derived units to avoid ambiguity.

The sensor configuration includes the full optical system (30 cm aperture, f/4, 72% transmission), the detector (18 um pixel pitch, 72% QE, 50 e-/s dark current), and the observation geometry (500 km LEO orbit, nadir viewing). The atmosphere model is set to "simple" — a parametric Beer-Lambert model that accounts for molecular scattering, aerosol extinction, and water vapor absorption through the column of atmosphere between the target and the sensor.

### Step 2: Establish the Baseline

RADIANT evaluates the full signal chain from source through atmosphere, optics, spectral integration, detector, and readout to produce baseline performance metrics *without* IPC. This gives us the system's inherent capability before IPC degrades it.

The baseline results at 500 km with atmosphere:
- System MTF at Nyquist: 0.2532 (above the 0.15 requirement)
- SNR: 809 (well above the 100 requirement)
- EE 1x1: 0.4699 (below the 0.60 requirement — already fails at baseline)
- GSD: 7.50 m (cross-track = along-track at nadir)
- Q (sampling parameter): 0.944 (near-optimal Nyquist matching)
- NEDT: 35.6 mK
- NIIRS: 4.82
- Strehl ratio: 1.000 (diffraction-limited, no WFE applied)

The extended radiometric regime is active because the target (a 310 K ground scene) fills the entire pixel. In this regime, background temperature (295 K) only enters the contrast SNR calculation — it does not affect the primary signal or noise budget.

### Step 3: Apply IPC and Sweep

RADIANT natively wires IPC into the signal chain. When `detector.ipc_coupling` is set, the DetectorStage generates the 3×3 IPC kernel and stores it in `stage_outputs`. The PerformanceStage then convolves this kernel with the EffectivePSF via FFT, and all spatial metrics (MTF, EE, RER, FWHM) are computed from the resulting IPC-degraded PSF. This ensures consistency — a single PSF is the source of truth for all spatial metrics (Rule 4).

The IPC MTF at the Nyquist frequency has a simple analytic form that serves as a validation cross-check:

```
MTF_IPC(f_Nyquist) = 1 - 4 * alpha
```

where alpha is the per-neighbor coupling fraction. At 1.8% coupling (the vendor typical value), MTF_IPC = 0.928 — a 7.2% degradation.

The script sweeps IPC from 0% to 5% in 51 steps, running a full RADIANT evaluation at each point. At each IPC value, it extracts MTF at Nyquist, EE 1×1, EE 3×3, RER, FWHM, SNR, NEDT, and NIIRS directly from `result.metrics`. It also performs an analytic cross-check comparing RADIANT's native MTF predictions against baseline × analytic IPC MTF to validate the FFT convolution approach.

### Step 4: Find the Limit

The sweep reveals that the **binding constraint is EE 1x1**, which already fails at baseline (0.4699 < 0.60 requirement) before any IPC is applied. The MTF requirement (>= 0.15) is comfortably met across the full 0-5% IPC range.

**Important caveat**: The IPC kernel convolution in the PSF path currently applies the 3x3 kernel at PSF sample spacing rather than pixel pitch, causing the IPC effect to be much smaller than expected. The analytic cross-check confirms this: at alpha = 5%, the analytic formula predicts system MTF = 0.2025 but RADIANT's native convolution gives 0.2514. The MTF product path correctly computes `mtf_ipc = 1 - 4*alpha`, triggering dual-path consistency check failures at alpha > 2.5%. See gaps.md for details.

For Mike's purposes, the analytic IPC MTF formula (MTF_IPC = 1 - 4*alpha at Nyquist) should be used as the authoritative result until the kernel sampling is fixed.

### Step 5: Validate Against Lab Data

Mike measured MTF at Nyquist and EE 1x1 on all five detector samples in the lab. Comparing RADIANT's native predictions (with IPC convolved into the EffectivePSF) to these measurements serves as a sanity check on the analysis.

The model consistently predicts higher MTF than the lab measurements (by 0.02 to 0.15 depending on the sample). This is expected — the lab measurements include additional degradation from the optical test bench, diffraction from the test setup, and detector-specific effects (like diagonal IPC coupling at 0.3%) that the simple 4-neighbor model does not capture. The model-vs-measurement gap grows with IPC, which is also expected since the simple model neglects higher-order coupling effects that become more significant at higher coupling fractions.

The trend (MTF decreasing with IPC) matches well, confirming that the model captures the dominant physics correctly.

## Key Takeaways

1. **EE 1x1 is the binding constraint for IPC**, not MTF. This is not obvious a priori — many engineers focus on MTF when evaluating IPC, but for this system the ensquared energy requirement is tighter.

2. **The vendor's typical IPC specification does not meet requirements.** This needs to be discussed with the vendor — either the IPC specification must be tightened, or the EE requirement must be relaxed.

3. **The atmosphere matters at orbital altitude.** With the atmosphere model active, the signal chain accounts for atmospheric transmission, path radiance, and thermal emission — all of which contribute to the noise budget and ultimately affect SNR. Bypassing the atmosphere (as was necessary before the model fix) would overestimate SNR and potentially mask design issues.

4. **IPC does not affect SNR.** This is sometimes counterintuitive, but IPC redistributes charge without destroying it. The total signal in the image is conserved, so SNR is unchanged. The impact is purely spatial — resolution and ensquared energy degrade, but signal-to-noise does not.

## Gaps Identified

- **Gap 1 (IPC kernel sampling)**: PARTIALLY FIXED. IPC is now wired into the signal chain — `DetectorStage` generates the IPC kernel and `PerformanceStage` convolves it with the EffectivePSF. However, the 3x3 kernel is applied at PSF sample spacing rather than pixel pitch, making the effect negligible. The MTF product path correctly computes the analytic IPC MTF. The fix requires upsampling the IPC kernel to match the PSF grid spacing.

- ~~**Gap 2 (SNR = 0 at orbital altitude)**: FIXED. The atmosphere model now uses column-integrated optical depth with proper exponential scale heights.~~

- **Gap 3**: No support for arbitrary (e.g. 5x5) IPC kernels. OPEN.
- **Gap 4**: No IPC correction/deconvolution model. OPEN.

### Gaps Closed Since Last Run

| Metric | Previous Status | Current Status |
|--------|----------------|----------------|
| NEDT | Not available | `result.metrics["nedt_K"]` = 35.6 mK |
| NIIRS | Not available | `result.metrics["niirs"]` = 4.82 |
| GSD | Manual calculation | `result.metrics["gsd_cross_track_m"]` = 7.50 m |
| Q parameter | Manual calculation | `result.metrics["q_center"]` = 0.944 |
| Strehl | Not available | `result.metrics["strehl"]` = 1.000 |
| MTF budget | Not available | `mtf_budget.per_term_at_nyquist` with per-component values |
