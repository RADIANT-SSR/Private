# 9.3 MODIS (Aqua) Thermal Emissive Bands

**Mission**: MODIS, 705 km SSO whiskbroom (1.4771 s scan, 1354 frames), 17.78 cm
aperture, 83 K HgCdTe FPAs — 20+ years of on-orbit TEB calibration record.
**Claims validated**: (1) RADIANT's band-averaged Planck radiance matches NASA's
published typical radiances exactly; (2) the photon floor sits below the measured NEdT
in the physically required ordering for a detector-noise-limited instrument.

## Design

300 K blackbody through vacuum; published EFLs (380.9 / 282.1 mm), detector sizes
(540 / 400 µm), and frame-derived integration times (323.3 µs; B29: 4×73.3 µs
on-board-averaged). Optics transmission (0.40) and QE (0.7) are assumptions with
envelopes; detector noise is the published-data-anchored unknown (see Findings §3).

## Run

`radiant run modis_b20_nedt_300k.yaml` (the clean band). B29/31/32 evaluate but
well-clip — see gaps.md.

## Expected results

Part 1 — spectral anchors (any band, compare Source-stage band radiance):
L_typ published 0.45 / 9.58 / 9.55 / 8.94 W/m²/sr/µm (B20/29/31/32) vs RADIANT
band-averaged Planck — agreement ≤0.1%.

Part 2 — NEdT: B20 chain value ~10 mK (photon+read+ADC floor) vs 50 mK spec /
20 mK measured — floor < measured < spec as required for a detector-limited
instrument. B29/31/32 floors (2–2.7 mK, computed pre-readout by
`scripts/run_external_validation.py`) carry the same verdict.
