# Scenario 5.3 — Gaps

## Gap 1: Per-wavelength PSFs not exposed
**Severity**: Medium
**Description**: RADIANT computes monochromatic PSFs at each wavelength internally during polychromatic averaging (in `compute_polychromatic_psf()`) but discards them after accumulation. The per-wavelength PSF arrays are never stored in `stage_outputs`. To visualize individual-wavelength PSFs, the user must run N separate evaluations with narrow spectral bands — an expensive workaround.
**Workaround**: Run RADIANT N times with narrow bands (±50 nm) centered at each wavelength of interest.
**Recommendation**: Store per-wavelength PSF arrays in `stage_outputs["optics"]["psf_per_wavelength"]` as a dict keyed by wavelength. This requires minimal memory (N × grid × grid) and enables chromatic PSF visualization without re-running.

## Gap 2: No per-wavelength MTF curve output
**Severity**: Medium
**Description**: Related to Gap 1 — the MTF curve at each wavelength is not available. Tom wants to overlay MTF(f) at 3.5, 4.0, 4.5, 5.0 µm to see how frequency response varies across the band. Currently only the aggregate polychromatic MTF at Nyquist is reported.
**Workaround**: Same as Gap 1 — run narrow-band evaluations and extract MTF from each.
**Recommendation**: If per-wavelength PSFs are stored (Gap 1), per-wavelength MTF curves follow trivially via FFT of each stored PSF.

## Gap 3: No FWHM vs. wavelength from polychromatic run
**Severity**: Low
**Description**: FWHM is computed only for the final aggregate PSF. For chromatic analysis, FWHM(λ) is needed to compare against the analytic Airy FWHM = 1.03 × λ × f/# and assess diffraction-limited performance across the band.
**Workaround**: Compute from narrow-band runs (same as Gaps 1–2).
**Recommendation**: Derive from per-wavelength PSFs if stored.

## Gap 4: No arbitrary source spectrum for PSF weighting
**Severity**: Low
**Description**: The polychromatic PSF weighting uses the scene source spectrum (post-atmosphere, post-optics photon flux). Tom wants to compare blackbody-weighted vs. solar-reflection-weighted polychromatic PSFs (e.g., for VNIR bands where solar illumination dominates). There is no mechanism to override the weighting spectrum.
**Workaround**: Change the source temperature/spectrum and re-run, but this also changes the radiometric results (SNR, signal). No way to change PSF weighting independently.
**Recommendation**: Add an optional `optics.psf_weighting_spectrum` parameter that, if set, overrides the automatic photon-flux weighting.
