# 9.4 Gaps / Known Issues

- **Provenance verification pass needed (offline compilation)** — the source-data doc
  was compiled without live web access; values classed "published (recalled)" (aperture
  135 mm, focal length 886 mm, pitch 36/18 µm, t_int 3.6 ms, measured SNR column ±15%)
  must be verified against [Knight 2014] / [Morfitt 2015] in an online session before
  the measured-SNR column is treated as authoritative. Mirrored as a Findings_Log line
  (2026-08-29).
- **Gap 103 (per-configuration optical elements) is CLOSED** — closed 2026-09-03 as
  configured element rows; this scenario's `oli2_all_bands_study.yaml` is the deliverable.
  All nine bands, pan included, now live in one study file, each with its own filter entry
  on the configured element row; the composite-filter workaround and the pan band's
  standalone-only status are both retired. The per-band `oli2_b0N_snr_ltyp.yaml` files
  remain as cross-checks (`scripts/check_all_bands_parity.py`, rel < 1e-9, measured
  0.00e+00 [-] on every band).
- **B1/B9 predictions sit below the recalled flight SNR** (0.77× / 0.84×) — assumption
  artifact of conservative narrow-band QE and synthetic filter roll-off, not a chain
  defect; both clear the requirement. A published OLI QE or RSR-integrated throughput
  curve would convert this from hypothesis to closure.
- **Saturation not anchored** — full well is analysis-mode (2 Me-, never clips);
  published per-band saturation radiances exist and would make a natural follow-on
  anchor (owner declined for this task: SNR @ L_typ only).
- **Coating curves are synthetic end to end** — anchored to vendor-typical protected-Ag
  and filter shapes, envelope ±0.06 compound on throughput; a thin-film stack module
  (transfer-matrix) was considered and deliberately not built (owner decision
  2026-08-29: parametric synthesis).
- **`data/filter_butcher_block.csv` is now unused by every config file** — it was the
  shared composite the D-7-era study needed. `scripts/gen_oli2_coatings.py` still emits it
  and this walkthrough documents it as the historical artifact; deleting it (and its
  generator branch) is a candidate cleanup, not a defect.
