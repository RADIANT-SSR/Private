# Scenario 8.3 — GUI Workflow Requirements

This scenario is a **target-altitude sweep** that deliberately crosses a band
with no shipped data. It exercises three GUI capabilities beyond the shared
interpolation requirements (8.1/8.2).

---

## 1. Sweeping a geometry parameter with graceful per-point failure

The user sweeps `geometry.target_altitude_m` from 0 to 300 km. Some points
succeed (0–29 km interpolated, ≥ 100 km vacuum) and some **fail by design**
(29–100 km: `AtmosphereValidationError`, "outside the available range"). The
GUI's sweep/plot surface must:

- **not abort the whole sweep** when one point raises — mark that point as
  N/A / PENDING and continue (the scripting console does this via `try/except`
  on `AtmosphereValidationError`; the GUI needs the same resilience);
- **distinguish "failed to compute" from "computed a zero"** on the plot — a
  gap in the curve with a labelled shaded band ("no shipped data — boost-ladder
  runs pending"), never an interpolated line drawn *through* the missing band;
- surface the actual refusal message on demand (hover / detail pane) so the user
  learns *why* the band is empty, pointing at
  `docs/plans/MODTRAN_Boost_Ladder_Expansion_Plan.md`.

This is the same "unavailable is not one-way / not silent" principle behind
CU-163 — a degraded point must not poison the rest of the run.

## 2. Regime badge for a sub-pixel target

The plume is sub-pixel (0.22× PSF FWHM). The run panel should show the **derived
radiometric regime** (SUB_PIXEL) prominently, and — because this scenario sets
`source.regime_override` to lock it — indicate that the regime is user-locked vs
auto-derived. If a user picks a target size/range that would trip the
point-source angular-extent guard (√A_t/R > 0.1·PSF_FWHM), the GUI should offer
the actionable remedy the chain already raises (switch to sub_pixel) rather than
surfacing a raw traceback.

## 3. Well-fill (saturation) banner — inherited from 8.2, sharper here

Full-well saturation is the recurring silent failure (6.1/6.2/8.2, and twice in
this scenario). 8.3 adds a twist: **the clip appears at the closest / highest-
altitude rung, not the launch rung**, because the fill fraction grows as the
booster closes range. So a GUI that only checks saturation on the first evaluated
point would miss it. The GUI must show `well_status`/`adc_status` per swept point
(a persistent banner whenever any point is not `unclipped`), not just for the
initial configuration.

---

Shared interpolation requirements (family selection, axis interpolation vs
nearest-neighbor) are as in 8.1/8.2 and not repeated here.
