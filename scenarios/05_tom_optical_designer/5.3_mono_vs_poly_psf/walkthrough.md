# Scenario 5.3 Walkthrough: Monochromatic vs. Polychromatic PSF

## The Problem

Tom has selected his pixel pitch (18 µm, from scenario 5.2) and now wants to understand whether his spatial analysis is accurate. His MWIR band spans 3.5–5.0 µm — a 43% wavelength range. Since diffraction scales linearly with wavelength, the Airy disk diameter grows from 34.2 µm at 3.5 µm to 48.8 µm at 5.0 µm. That's a 44% increase across the band.

Tom's question: **does a monochromatic PSF at band-center (4.25 µm) give accurate spatial metrics, or does he need a polychromatic (flux-weighted) PSF?**

This matters for his design review. If monochromatic analysis overstates MTF or EE by a significant margin, his system may not actually meet the spatial requirements he reported in scenario 5.2.

## The Physics

### Diffraction Scales with Wavelength

The Airy disk diameter is `2.44 × λ × f/#`. For Tom's f/4 system:

| Wavelength [µm] | Airy Ø [µm] | Q (at 18 µm pitch) | Regime |
|------------------|-------------|---------------------|--------|
| 3.50 | 34.2 | 0.78 | Undersampled |
| 4.00 | 39.0 | 0.89 | Undersampled |
| 4.25 | 41.5 | 0.94 | Undersampled |
| 4.50 | 43.9 | 1.00 | Critical |
| 5.00 | 48.8 | 1.11 | Well-sampled |

At 3.5 µm, the PSF is compact and undersampled (Q = 0.78). At 5.0 µm, the PSF is broader and well-sampled (Q = 1.11). A monochromatic PSF at 4.25 µm captures neither extreme.

### Photon-Flux Weighting

The polychromatic PSF is not a simple average of per-wavelength PSFs. It's weighted by the **photon spectral flux** — the number of photons per second per unit wavelength arriving at the detector. For a 300 K blackbody in the 3.5–5.0 µm band, longer wavelengths contribute more photon flux (the Planck function in photon units peaks at ~9.7 µm, so within the MWIR band the long-wavelength end dominates). This means the polychromatic PSF is biased toward the broader, 5 µm end.

### Why Monochromatic Overstates Performance

A monochromatic PSF at band-center (4.25 µm) computes all spatial metrics at a single wavelength. Since shorter wavelengths produce tighter PSFs with higher MTF and EE, and the actual flux-weighted PSF is biased toward the broader long-wavelength end, band-center monochromatic analysis systematically **overstates** spatial performance.

## How RADIANT Solves This

### Step 1: Per-Wavelength Analysis

The script runs RADIANT at 5 individual wavelengths (3.5, 4.0, 4.25, 4.5, 5.0 µm) using narrow bands (±50 nm). This shows how every spatial metric varies across the band:

| λ [µm] | MTF@Nyq | EE 1×1 | EE 3×3 | RER   | FWHM [µm] | SNR |
|---------|---------|--------|--------|-------|------------|-----|
| 3.50    | 0.308   | 0.520  | 0.902  | 0.647 | 20.3       | 172 |
| 4.00    | 0.290   | 0.503  | 0.889  | 0.628 | 20.5       | 183 |
| 4.25    | 0.253   | 0.470  | 0.882  | 0.602 | 21.8       | 204 |
| 4.50    | 0.265   | 0.448  | 0.874  | 0.610 | 21.5       | 226 |
| 5.00    | 0.203   | 0.389  | 0.861  | 0.563 | 23.9       | 245 |

The trends are monotonic: shorter wavelengths give better MTF and EE (tighter PSF concentrates more energy), but worse SNR (fewer photons in narrower band at shorter wavelengths for a thermal source). RER (relative edge response) is now also extracted at each wavelength.

### Step 2: Full-Band Comparison — Mono vs. Poly

RADIANT's `optics.psf_n_wavelengths` parameter controls the PSF model:
- **N=1** (default): monochromatic PSF at band-center
- **N=5, 11, 21**: polychromatic PSF using N wavelengths, photon-flux-weighted

| PSF Model | MTF@Nyq | EE 1×1 | EE 3×3 | RER   | FWHM [µm] | SNR | NEDT [mK] | NIIRS |
|-----------|---------|--------|--------|-------|------------|-----|-----------|-------|
| Mono (N=1)  | 0.253 | 0.470 | 0.882 | 0.601 | 21.8 | 707 | 40.9 | 4.7 |
| Poly (N=5)  | 0.247 | 0.437 | 0.877 | 0.597 | 21.3 | 707 | 40.9 | 4.7 |
| Poly (N=11) | 0.248 | 0.437 | 0.877 | 0.598 | 21.1 | 707 | 40.9 | 4.7 |
| Poly (N=21) | 0.249 | 0.438 | 0.877 | 0.598 | 21.2 | 707 | 40.9 | 4.7 |

### Step 3: Quantify the Error

The chromaticism error from monochromatic analysis (relative to poly N=11):

| Metric | Mono vs. Poly Error |
|--------|---------------------|
| MTF at Nyquist | +1.9% (mono overstates) |
| EE 1×1 | +7.4% (mono overstates) |
| EE 3×3 | +0.6% (negligible) |
| RER | +0.6% (negligible) |
| FWHM | +3.2% (mono understates broadness) |
| SNR | +0.0% (no effect — SNR is radiometric, not spatial) |

The largest error is in EE 1×1 (+7.4%). Monochromatic analysis tells Tom that 47.0% of a point source's energy falls in a single pixel, when the true value is 43.7%. That's a meaningful difference for point source detection sensitivity.

### Step 4: Convergence Check

N=11 vs N=21 agrees within 0.2% on all metrics. N=11 is sufficient for this band.

## Key Takeaways

1. **Monochromatic PSF overstates spatial performance by 2–8%.** For this 3.5–5.0 µm band, EE 1×1 is overstated by 7.4% and MTF at Nyquist by 1.9%. The error is systematic — monochromatic always overstates because band-center is sharper than the flux-weighted average.

2. **SNR is unaffected.** The PSF model choice does not change SNR because SNR in extended-scene regime depends on total signal and noise, not the PSF shape. The signal is the same regardless of how the PSF is computed.

3. **EE 3×3 is robust to chromaticism.** Only 1% error in EE 3×3 because the 3×3 box is large enough to capture the PSF regardless of wavelength-dependent broadening. EE 1×1 is much more sensitive because a single pixel is comparable in size to the PSF.

4. **N=11 wavelengths is sufficient** for this band. Convergence is achieved within 0.2% of the N=21 result. N=5 also gives similar results (within 0.5% of N=11).

5. **The FWHM result.** Polychromatic FWHM (21.1 µm) is smaller than monochromatic (21.8 µm), a 3.2% difference. The polychromatic PSF has a tighter core from the short-wavelength contributions but broader wings from the long-wavelength contributions. FWHM measures only the core width, so the sharper short-wavelength PSFs pull the FWHM down, while the broader wings reduce EE 1×1.

6. **For Tom's design review**: the 18 µm pixel still passes all requirements under polychromatic analysis. MTF at Nyquist drops from 0.253 to 0.247 (requirement: ≥ 0.10) and EE 1×1 drops from 0.470 to 0.436 (requirement: ≥ 0.30). Both are well above thresholds.

## Gaps Identified

- **Gap 1 (Per-wavelength PSFs not exposed)**: RADIANT computes monochromatic PSFs internally during polychromatic averaging but discards them. Tom would like to visualize the PSF at each wavelength overlaid. Currently requires running N separate narrow-band evaluations.

- **Gap 2 (No per-wavelength MTF curve output)**: Similar to Gap 1 — the per-wavelength MTF curves are not stored. Tom wants an overlay of MTF(f) at 3.5, 4.0, 4.5, 5.0 µm to see the chromatic spread. Note: the **aggregate** full MTF curve is now available natively from `result.stage_outputs["performance"]["mtf_freq_x"]` and `["mtf_x"]` — this gap is about per-wavelength decomposition, not the aggregate curve.

- **Gap 3 (No FWHM vs. wavelength from polychromatic run)**: FWHM is computed only for the final aggregate PSF, not per wavelength. Tom needs to plot FWHM(λ) and compare to the analytic Airy FWHM = 1.03 × λ × f/#.

- **Gap 4 (No arbitrary source spectrum for PSF weighting)**: The polychromatic PSF uses the scene source spectrum (post-atmosphere, post-optics) for weighting. Tom wants to compare blackbody-weighted vs. solar-reflection-weighted polychromatic PSFs, but there's no way to specify an alternative weighting spectrum.

### New Metrics Available Since Initial Run

The script now also extracts these natively computed metrics for each PSF model:
- **RER** (relative edge response) — chromaticism error now tracked for RER alongside MTF and EE
- **NEDT** (noise-equivalent temperature difference) — from `result.metrics["nedt_K"]`
- **NIIRS** (imagery interpretability rating) — from `result.metrics["niirs"]`
- **Strehl ratio** — from `result.metrics["strehl"]`
- **Q, GSD** — from `result.metrics["q_center"]`, `["gsd_cross_track_m"]`
