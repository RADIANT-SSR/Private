# 9.2 GUI Workflow

1. **File → Open** `tirs_b10_nedt_300k.yaml`.
2. **Source stage**: 300 K blackbody, emissivity 1.0 (onboard-calibrator view).
3. **Detector stage**: note qe_value is the *effective CE* (1.64e-2) — see the file
   header comment for the inversion provenance; dark rate 4×10⁷ e-/s.
4. **Run**; read **NEDT** from Performance outputs (pin NEDT + sigma_total_e +
   well_fill_fraction). Expect ~58 mK (B10) / ~52 mK (B11), well fill ~35–49%.
5. Compare the noise budget panel: shot (signal+dark) should dominate read noise —
   the photon-floor regime the walkthrough describes.
6. Optional: set `readout.read_noise_e_rms` to 1033 (electronics spec ceiling RSS'd)
   to reproduce the upper bound of the Findings bracket.
