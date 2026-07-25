# External-Validation Scenario Configs

Loadable RADIANT configs (GUI: File → Open, or `radiant run <file>`) for the eleven
external-validation scenarios of `docs/reports/external_validation_2026-07/Findings.md`.
One file per instrument band; every parameter carries an inline provenance comment
(published / derived / assumption) keyed to the cited data sheets in
`docs/validation/*_source_data.md`. The **canonical** comparison (assumption envelopes,
implied-throughput inversions, MODIS pre-readout floor) is
`scripts/run_external_validation.py`; these configs reproduce its central-value runs.

| Config | Scenario | Chain-evaluated result | Published (spec / measured) |
|---|---|---|---|
| `s2_msi_b02_snr_lref.yaml` | S2 MSI B2 SNR @ 128 W/m²/sr/µm | SNR 253 [-] | ≥154 / 162 (see B2 inversion note in Findings §1) |
| `s2_msi_b03_snr_lref.yaml` | S2 MSI B3 SNR @ 128 W/m²/sr/µm | SNR 208 [-] | ≥168 / — |
| `s2_msi_b04_snr_lref.yaml` | S2 MSI B4 SNR @ 108 W/m²/sr/µm | SNR 193 [-] | ≥142 / 175 |
| `s2_msi_b08_snr_lref.yaml` | S2 MSI B8 SNR @ 103 W/m²/sr/µm | SNR 337 [-] | ≥174 / — |
| `s2_msi_b11_snr_lref.yaml` | S2 MSI B11 SNR @ 4 W/m²/sr/µm | SNR 331 [-] | ≥100 / 133 (INCONCLUSIVE — SWIR t_int unpublished) |
| `tirs_b10_nedt_300k.yaml` | TIRS B10 NEdT @ 300 K | 58 mK | ≤400 / 49 mK |
| `tirs_b11_nedt_300k.yaml` | TIRS B11 NEdT @ 300 K | 52 mK | ≤400 / 52 mK |
| `modis_b20_nedt_300k.yaml` | MODIS B20 @ 300 K (photon floor) | 10 mK | ≤50 / 20 mK (detector-limited) |
| `modis_b29_nedt_300k.yaml` | MODIS B29 @ 300 K | well-clipped (see file NOTE / Gap 101) | ≤50 / 20 mK |
| `modis_b31_nedt_300k.yaml` | MODIS B31 @ 300 K | well-clipped (see file NOTE / Gap 101) | ≤50 / 20 mK |
| `modis_b32_nedt_300k.yaml` | MODIS B32 @ 300 K | well-clipped (see file NOTE / Gap 101) | ≤50 / 30 mK |

Notes:
- S2 SNR values reproduce the dossier's central predictions exactly; the envelopes and
  verdicts live in Findings §1. TIRS configs carry the saturation-inverted CE (the raw
  published CE 8.0e-3 is the other bracket bound — Findings §2).
- MODIS B29/31/32: PC/PV HgCdTe has no discrete charge well; the chain's well clip is a
  representational artifact (Gap 101 second instance) — each file's NOTE explains; the
  valid photon floor comes from the script's pre-readout computation.
- `data/` holds the five flat L_ref spectra (2-point CSVs, generated from the published
  L_ref values by the config generator — trivially regenerable; committed as config
  inputs per Rule 26).
- The "PSF undersampled" log line on the thermal configs is a true statement about these
  instruments (Q ≪ 1 fast-optics designs), not a config error; radiometric metrics are
  unaffected.
