# 1.6 MWIR Point-Source SDA — Gaps

Framework gaps surfaced authoring this scenario — all now **resolved**
(`docs/tracking/gaps.md` Gap 98):

- **B (inputs) — DONE.** Point sources can be defined by radiant intensity without
  a hand-authored CSV: blackbody (`point_intensity_temperature_K`/`_area_m2`/
  `_emissivity`) and scalar band-flux (`point_intensity_band_W_per_sr`).
- **A (steering) — DONE.** A `point_source` target with no intensity now raises an
  actionable error naming the intensity inputs (not `projected_area_m2`); in the
  GUI the surface-radiance (ε, T) rows disable for a point-source scene.
- **C (range) — DONE.** `source.range_m` falls back to the GeometryStage-derived
  slant range, so `geometry.target_range_m` need not be set explicitly (this config
  still sets it, for a reproducible fixed range).
- **D (GUI) — DONE.** The Source instrument has a "Target — point source" tab with
  the intensity inputs, regate-gated to the point-source regime.

No scenario-specific data gaps: the target intensity is modeled analytically
(`I = ε·A·B(λ,T)`); no external MODTRAN/measurement input is required.
