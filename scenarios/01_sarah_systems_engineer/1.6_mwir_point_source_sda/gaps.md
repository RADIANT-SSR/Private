# 1.6 MWIR Point-Source SDA — Gaps

Framework gaps surfaced authoring this scenario. The **capability** to define a
point source by intensity now exists (blackbody + scalar band-flux convenience
inputs — `docs/tracking/gaps.md` Gap 98, "inputs done"); the residual items are
UX/workflow, tracked as **Gap 98 (A/C/D)**:

- **A — no steering to intensity.** The Source stage keeps the surface-radiance
  params (`temperature`/`emissivity`) settable in `point_source` regime. With the
  area at zero the chain raises `SpectralIntegrationStage: point_source regime
  requires projected_area_m2 and range_m` — an error pointing back to *area*,
  never naming the intensity inputs. A point-source config should be steered to
  `point_intensity_*` / `user_intensity_path`.

- **C — range must be re-specified.** The `point_source` signal reads
  `source.range_m` from the explicit `geometry.target_range_m` param and does not
  fall back to the GeometryStage-derived slant range, so a config that derives
  range from altitude + zenith fails with "requires … range_m". This scenario
  sets `target_range_m` explicitly as the workaround.

- **D — no GUI surface.** The Source instrument exposes none of the intensity
  inputs and shows the (point-source-irrelevant) blackbody surface-radiance params
  regardless of regime.

No scenario-specific data gaps: the target intensity is modeled analytically
(`I = ε·A·B(λ,T)`); no external MODTRAN/measurement input is required.
