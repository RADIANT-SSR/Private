# 9.1 GUI Workflow

1. **File → Open** any `s2_msi_*_snr_lref.yaml` (start with B4).
2. **Source stage**: confirm the user-radiance table loaded (spectral table shows the
   flat L_ref in W/m²/sr/µm); scene type extended; regime banner should read extended.
3. **Atmosphere stage**: model `exo` — τ ≡ 1, no path radiance (validation is at-sensor).
4. **Readout stage**: TDI stages = 2 (Gap 102 acquisition section); integration time
   1.5045 ms shared with Spectral Integration.
5. **Run**, then read **SNR** in the Performance outputs (Pinned card recommended:
   SNR + signal_e_final + well_fill_fraction).
6. Compare against the walkthrough table; the well fill should be ~8–23% (no
   saturation banner).
7. Optional: sweep `detector.qe_value` over the data-doc envelope and watch SNR scale
   as √QE — the envelope in Findings §1.
