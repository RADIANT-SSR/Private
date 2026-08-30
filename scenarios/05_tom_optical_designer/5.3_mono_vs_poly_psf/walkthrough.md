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
| 3.50    | 0.328   | 0.478  | 0.899  | 0.660 | 19.5       | 88  |
| 4.00    | 0.290   | 0.442  | 0.885  | 0.628 | 20.5       | 151 |
| 4.25    | 0.267   | 0.414  | 0.878  | 0.610 | 21.3       | 188 |
| 4.50    | 0.248   | 0.396  | 0.871  | 0.599 | 22.0       | 227 |
| 5.00    | 0.210   | 0.358  | 0.858  | 0.568 | 23.6       | 244 |

*Numbers refreshed 2026-08-29 from the unmodified runner (previous vintage
2026-08-02, pre-CU-324). One mover: **CU-324** — `E_sky_thermal`'s
flux-diffusivity exponent is now the geometric `sec 48.2° = 1.50030` rather than
the CU-155 fitted `D = 1.1`, which lifts the reflected-sky term by well under
1 % per band. Only two rows cross a rounding boundary in this integer SNR
column (4.25 µm 187 → 188, 4.50 µm 226 → 227); the other three are unchanged as
printed. MTF@Nyquist, EE 1×1, RER and FWHM are spatial and bit-identical at
every wavelength.*

*Prior vintage, for the trend: the 2026-08-02 refresh was CU-321's
height-resolved path-emission temperature, which lowered the per-band SNR by
6–18 %, most at 5.0 µm.*

The trends are monotonic: shorter wavelengths give better MTF and EE (tighter PSF concentrates more energy), but worse SNR (fewer photons in a narrow band at shorter wavelengths for a thermal source — a 300 K target emits far more MWIR photons at 5 µm than at 3.5 µm). RER (relative edge response) is now also extracted at each wavelength. The SNR column stays monotonic in λ across the whole band under CU-321 as it did under CU-224; the pre-CU-224 vintage showed a spurious dip at 5.0 µm (208 at 4.50 µm vs 202 at 5.00 µm), and that remains gone.

### Step 2: Full-Band Comparison — Mono vs. Poly

RADIANT's `optics.psf_n_wavelengths` parameter controls the PSF model:
- **N=1** (default): monochromatic PSF at band-center
- **N=5, 11, 21**: polychromatic PSF using N wavelengths, photon-flux-weighted

| PSF Model | MTF@Nyq | EE 1×1 | EE 3×3 | RER   | FWHM [µm] | SNR | NEDT [mK] | NIIRS |
|-----------|---------|--------|--------|-------|------------|-----|-----------|-------|
| Mono (N=1)  | 0.267 | 0.414 | 0.878 | 0.610 | 21.3 | 707 | 42.3 | 4.8 |
| Poly (N=5)  | 0.247 | 0.395 | 0.871 | 0.596 | 21.3 | 707 | 42.3 | 4.7 |
| Poly (N=11) | 0.248 | 0.396 | 0.871 | 0.596 | 21.1 | 707 | 42.3 | 4.7 |
| Poly (N=21) | 0.248 | 0.396 | 0.871 | 0.596 | 21.2 | 707 | 42.3 | 4.7 |

*Numbers refreshed 2026-08-02 from the unmodified runner (previous vintage
2026-08-02, pre-CU-321). The polychromatic rows moved again, for the same
reason they moved on CU-224: the poly PSF is weighted by the in-band photon
flux, and CU-321's height-resolved emission temperature re-weights that
spectrum — this time back toward the short-wavelength end, so the poly metrics
move a little closer to the mono ones. The mono (N=1) row is bit-identical
(its spatial metrics are weighting-independent). SNR is well-clipped at
500,000 e⁻ and unchanged.*

### Step 3: Quantify the Error

The chromaticism error from monochromatic analysis (relative to poly N=11):

| Metric | Mono vs. Poly Error |
|--------|---------------------|
| MTF at Nyquist | +7.6% (mono overstates) |
| EE 1×1 | +4.7% (mono overstates) |
| EE 3×3 | +0.8% (negligible) |
| RER | +2.3% (small) |
| FWHM | +0.8% (negligible) |
| SNR | +0.0% (no effect — SNR is radiometric, not spatial) |

The largest error is in MTF at Nyquist (+7.6%), with EE 1×1 second at +4.7%. Monochromatic analysis tells Tom that 41.4% of a point source's energy falls in a single pixel, when the true value is 39.6%. That is still a meaningful difference for point-source detection sensitivity. The MTF-leads-EE ranking, which first appeared when CU-224 re-weighted the photon-flux spectrum, survives CU-321's re-weighting in the opposite direction — both errors shrank by about a tenth and neither overtook the other.

### Step 4: Convergence Check

N=11 vs N=21 agrees well within 1% on all metrics (MTF 0.32%, EE 1×1 0.22%, FWHM 0.08%). N=11 is sufficient for this band.

## Key Takeaways

1. **Monochromatic PSF overstates spatial performance by up to ~8%.** For this 3.5–5.0 µm band, MTF at Nyquist is overstated by 7.6% and EE 1×1 by 4.7%. The error is systematic — monochromatic always overstates because band-center is sharper than the flux-weighted average.

2. **SNR is unaffected.** The PSF model choice does not change SNR because SNR in extended-scene regime depends on total signal and noise, not the PSF shape. The signal is the same regardless of how the PSF is computed.

3. **EE 3×3 is robust to chromaticism.** Only 0.9% error in EE 3×3 because the 3×3 box is large enough to capture the PSF regardless of wavelength-dependent broadening. EE 1×1 is much more sensitive because a single pixel is comparable in size to the PSF.

4. **N=11 wavelengths is sufficient** for this band. Convergence is achieved within ~0.3% of the N=21 result. N=5 also gives similar results (within ~1–2% of N=11).

5. **The FWHM result.** Polychromatic FWHM (21.1 µm) is marginally smaller than monochromatic (21.3 µm), a 0.8% difference — small enough to be a wash at this band ratio. The polychromatic PSF has a tighter core from the short-wavelength contributions but broader wings from the long-wavelength contributions. FWHM measures only the core width, so the sharper short-wavelength PSFs hold the FWHM roughly level while the broader wings reduce EE 1×1. (Pre-CU-224 this difference read 2.0%; CU-224's flux re-weighting all but cancelled it, and CU-321's re-weighting brings a little of it back.)

6. **For Tom's design review**: the 18 µm pixel still passes all requirements under polychromatic analysis. MTF at Nyquist drops from 0.267 to 0.246 (requirement: ≥ 0.10) and EE 1×1 drops from 0.414 to 0.394 (requirement: ≥ 0.30). Both are still above thresholds, though EE 1×1 now clears its floor by 31% rather than the 47% of the previous vintage.

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
