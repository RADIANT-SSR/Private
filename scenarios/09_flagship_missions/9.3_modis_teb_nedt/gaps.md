# 9.3 Gaps / Known Issues

- **Well-clip artifact (B29/31/32)** — PC/PV HgCdTe integrates photocurrent with no
  discrete charge well; collected charge exceeds RADIANT's well-schema max (1×10⁸ e-),
  so the chain reports an inapplicable saturation and clipped SNR/NEdT. Second instance
  of **Gap 101** (recorded on that entry). The valid photon floor is computed from the
  pre-readout signal by `scripts/run_external_validation.py`.
- Per-band optics transmission and QE are calibration-LUT-internal at NASA —
  assumptions 0.30–0.50 / 0.6–0.8 carried with envelopes.
- Measured NEdT is detector/system-noise-limited (PC G-R/1/f, PV crosstalk families) —
  a photon model bounds it, and the implied detector noise (7×10³–6×10⁵ e- per band,
  Findings §3) is the target for any future HgCdTe detector-noise model.
- Along-scan smear is 0.97 IFOV during integration — required for any future MODIS MTF
  validation (not modeled in these NEdT configs).
