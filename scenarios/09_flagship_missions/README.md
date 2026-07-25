# 09 — Flagship Missions

External-validation scenarios: RADIANT configured to three flight-proven flagship
instruments from **published, cited** parameters, predicting the performance figures
those missions actually measured on orbit. These are the loadable-scenario form of the
external-validation dossier (`docs/reports/external_validation_2026-07/Findings.md`);
the canonical comparison with assumption envelopes is
`scripts/run_external_validation.py`, and every parameter's provenance is in
`docs/validation/*_source_data.md`.

| Sub-scenario | Mission | Validates | Result |
|---|---|---|---|
| 9.1_sentinel2_msi_snr | Sentinel-2 MSI | Reflective-band SNR @ ESA L_ref | Predictions within 1.1–2.0× of flight-measured, envelopes bracket |
| 9.2_landsat_tirs_nedt | Landsat 8 TIRS | LWIR NEdT @ 300 K | 52–58 mK predicted vs 49–52 mK measured (spec 400 mK) |
| 9.3_modis_teb_nedt | MODIS (Aqua) TEB | Band-averaged Planck anchors + NEdT floor | L_typ matched ≤0.1%; floor < measured < spec |

Every config is self-documenting: each parameter carries its units and provenance class
(published / derived / assumption) inline. Run any config from its folder or the repo
root: `radiant run <file>` or GUI File → Open.
