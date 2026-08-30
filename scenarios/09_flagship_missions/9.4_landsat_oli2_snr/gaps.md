# 9.4 Gaps / Known Issues

- **Provenance verification pass needed (offline compilation)** — the source-data doc
  was compiled without live web access; values classed "published (recalled)" (aperture
  135 mm, focal length 886 mm, pitch 36/18 µm, t_int 3.6 ms, measured SNR column ±15%)
  must be verified against [Knight 2014] / [Morfitt 2015] in an online session before
  the measured-SNR column is treated as authoritative. Mirrored as a Findings_Log line
  (2026-08-29).
- **Pan band cannot join the study file** — its filter overlaps green/red, so the
  shared-composite workaround fails for it (and 9 bands would exceed the
  8-configuration cap regardless). Tracked as the recorded re-audit instance on
  **Gap 103** (per-configuration element documents, deferred to v1.1).
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
