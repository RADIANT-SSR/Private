# Scenario 5.2 — Gaps

## Gap 1: No Q parameter in RADIANT output
**Severity**: Low
**Description**: The sampling parameter Q = λ·f/#/p is not computed or reported by RADIANT. It must be calculated manually from optical parameters. Q is fundamental to spatial analysis — it determines whether a system is oversampled, critically sampled, or aliased.
**Workaround**: Script computes Q manually as `lambda_center_um * f_number / pitch_um`.
**Recommendation**: Add Q to `result.metrics` (compute at band-center wavelength). Also consider reporting Q at band edges to show the sampling variation across the spectral band.

## Gap 2: No GSD in RADIANT output
**Severity**: Low
**Description**: Ground sample distance (GSD = p × h / f) is not computed by RADIANT. This is a basic mission parameter that should be reported automatically when orbital geometry is specified.
**Workaround**: Script computes GSD manually.
**Recommendation**: Add `gsd_cross_track_m` and `gsd_along_track_m` to `result.metrics` when `geometry.sensor_altitude_m > 0`.

## Gap 3: No aliased/folded MTF model
**Severity**: Medium
**Description**: RADIANT computes the system MTF but does not model aliasing (spatial frequency folding at Nyquist). For undersampled systems (Q < 1), high-frequency scene content folds back below Nyquist, producing spurious apparent contrast. The current MTF represents the pre-sampling (optical) transfer function, not the sampled (aliased) system response.
**Workaround**: None — aliasing analysis requires a folded-MTF computation not currently available.
**Recommendation**: Add an aliased MTF calculation that folds the optical MTF at multiples of the Nyquist frequency.

## Gap 4: No full MTF curve export
**Severity**: Medium
**Description**: Only MTF at Nyquist is reported in `result.metrics`. The full MTF curve (modulation vs. spatial frequency) is computed internally by the EffectivePSF but not exposed to the user. Optical designers need the full curve to evaluate frequency response across the band.
**Workaround**: None through the standard API. Would require accessing `result.stage_outputs` internals.
**Recommendation**: Add `mtf_curve_x` and `mtf_curve_y` (frequency array + MTF array) to `result.metrics` or a dedicated accessor.

## Gap 5: MTF = 0.000 at 8 µm pixel pitch (Q = 2.12)
**Severity**: Medium (needs investigation)
**Description**: The 8 µm pixel returns MTF at Nyquist = 0.0000. The Nyquist frequency at 8 µm pitch is 62.5 cy/mm, while the optical diffraction cutoff at 4.25 µm, f/4 is approximately 1/(λ·f/#) ≈ 59 cy/mm. Since Nyquist exceeds the diffraction cutoff, MTF = 0 may be physically correct. However, it could also indicate insufficient PSF grid resolution for very small pixels.
**Workaround**: For the trade study, this result is correctly flagged as FAIL — the 8 µm pixel is unsuitable for this f/4 system regardless.
**Recommendation**: Verify whether the EffectivePSF computation uses sufficient grid points for high-Q (small-pixel) configurations. Consider issuing a warning when Nyquist frequency exceeds the optical cutoff.
