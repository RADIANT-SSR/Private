# MODIS (Terra/Aqua) TEB — Source Data for External Validation

Retrieved 2026-07-24 (solo researcher; NASA sources fetched directly). Confidence classes
as in `sentinel2_msi_source_data.md`. Focus bands 20/29/31/32.

Primary sources:
- [SPEC] NASA MODIS Web "Specifications" — https://modis.gsfc.nasa.gov/about/specifications.php
- [L1B-ATBD] MODIS Level 1B ATBD Collection 7 v7 (MCST) — https://mcst.gsfc.nasa.gov/sites/default/files/file_attachments/MODIS_L1B_ATBD_C7_v7.pdf
- [GEO-ATBD] Nishihama et al., MODIS Level 1A Earth Location ATBD v3.0, SDST-092 (1997) — https://modis.gsfc.nasa.gov/data/atbd/atbd_mod28_v3.pdf
- [XIONG-2023] Xiong et al., "Aqua MODIS: 20 Years of On-orbit Calibration and Performance," JARS 17(3) 037501 (2023) — https://ntrs.nasa.gov/citations/20240001404
- [XIONG-2008] Xiong et al., Terra MODIS TEB multiyear calibration — https://ntrs.nasa.gov/citations/20080040164

## Validation targets ([SPEC] spec + [XIONG-2023] Table 5 Aqua measured, band-average)

| Band | λ range [µm] | T_typ [K] | L_typ [W/m²/sr/µm] | NEdT spec [K] | NEdT measured (2002/2012/2022) [K] |
|---|---|---|---|---|---|
| 20 | 3.660–3.840 | 300 | 0.45 | 0.05 | 0.02 / 0.02 / 0.02 |
| 29 | 8.400–8.700 | 300 | 9.58 | 0.05 | 0.02 / 0.02 / 0.02 |
| 31 | 10.780–11.280 | 300 | 9.55 | 0.05 | 0.02 / 0.02 / 0.02 |
| 32 | 11.770–12.270 | 300 | 8.94 | 0.05 | 0.03 / 0.03 / 0.02 |

Spec NEdL equivalents ([XIONG-2008] Table 1, W/m²/sr/µm): B20 0.0010, B29 0.0090,
B31 0.0070, B32 0.0061. The L_typ column is itself the 300 K band-averaged Planck
radiance — an independent published anchor set for RADIANT's spectral chain.

## Instrument (verbatim-sourced; full tables in the researcher deliverable)

| Parameter | Value | Units | Source | Confidence |
|---|---|---|---|---|
| Aperture | 17.78 cm off-axis afocal + 4 objectives, double-sided scan mirror | — | [SPEC], [DESIGN] | published |
| EFL SMIR (B20) / LWIR (B29/31/32) | 380.859 / 282.118 | mm | [GEO-ATBD] Table 3-1 | published |
| Effective f/# | ≈2.14 (SMIR) / ≈1.59 (LWIR) | — | derived (EFL/17.78 cm) | derived |
| Detector size | 540 (SMIR) / ≈400 (LWIR) square | µm | [GEO-ATBD] (LWIR derived from IFOV × EFL) | published/derived |
| IFOV | 1.4178 | mrad | derived (540 µm / 380.859 mm) | derived |
| Detector type | PV HgCdTe (20–30) / PC HgCdTe (31–36) | — | [L1B-ATBD] §3.3.2 | published |
| FPA temperature | 83 (radiative cooler) | K | [L1B-ATBD] | published |
| Integration time | 323.333 µs (B20, B31/32); 4×73.333 µs on-board-averaged (B29) | µs | [GEO-ATBD] Table 3-4 | published |
| Scan | whiskbroom 20.3092 rpm double-sided; 1.47716 s scan; 1354 frames @3 kHz; ±55°; 30.6% efficiency; along-scan smear 0.97 IFOV during integration | — | [GEO-ATBD], [L1B-ATBD] | published/derived |
| Quantization | 12 | bit | [SPEC] | published |
| Optics transmission per band | UNKNOWN (calibration-LUT internal) | — | — | ASSUMPTION 0.3–0.5 |
| QE (PV) / detector noise (PC) | UNKNOWN | — | — | ASSUMPTION η 0.6–0.8 (PV); PC detector noise is the dominant free parameter |

## Modeling notes

- **NEdT regime:** with published étendue and t_int, the photon-shot floor at 300 K is
  ~0.5–3 mK — the measured 20–30 mK is 10–40× above it: MODIS TEBs are
  **detector/system-noise-limited** (PC HgCdTe G-R/1/f, PV crosstalk), not photon-limited.
  The dossier therefore (a) validates the spectral chain against the four published L_typ
  Planck anchors, (b) reports RADIANT's photon floor as a bound and **inverts the implied
  detector noise** (σ_det = dS/dT × NEdT_meas) as the named unknown, rather than
  pretending a photon model reproduces 20 mK.
- Use Aqua early-mission values (Terra PV-LWIR bands carry post-2010 crosstalk drift);
  band-averaged over 10 detectors; NEdT defined at the onboard blackbody's single
  scan-mirror AOI (RVS unpublished).
- Along-scan smear of 0.97 IFOV during integration is the dominant along-scan MTF term
  (RADIANT smear kernel = 0.97 pixel) — noted for any future MODIS MTF validation.
