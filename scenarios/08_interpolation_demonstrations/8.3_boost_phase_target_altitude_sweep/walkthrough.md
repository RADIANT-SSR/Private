# Scenario 8.3 — Boost-Phase Target-Altitude Sweep (skeleton)

**New addition, not part of the original 35-scenario catalog** — see
`scenarios/08_interpolation_demonstrations/README.md`.

**Question:** A missile-defense application — a space-based MWIR sensor in LEO
stares at a booster and tracks it continuously from launch (0 km) through
burnout (> 100 km). As the booster climbs, the atmospheric column between it and
the sensor shortens, so the at-aperture signal and the achievable SNR change
with target altitude. Can a single scenario config sweep
`geometry.target_altitude_m` from 0 to 300 km against the shipped **interpolated**
atmosphere library and produce physically sensible τ_up and SNR?

**Status: SKELETON — the 29–100 km band is data-limited.** This scenario is the
acceptance-criterion #1 driver of `docs/plans/MODTRAN_Boost_Ladder_Expansion_Plan.md`.
It runs end-to-end today, but one of the three altitude regimes it sweeps has no
shipped data yet and is reported as PENDING rather than fabricated (see below).

---

## What runs, and the three regimes

`atmosphere.model = "interpolated"` with `interpolation_axes =
"sensor_altitude_m,target_altitude_m"` selects the shipped `midlat_summer_ladders`
family (loaded by default when `interpolated_data_dir` is unset). Sweeping the
target altitude crosses three regimes:

| Regime | Target altitude | Served by | Status |
|---|---|---|---|
| Interpolated | 0–29 km | `midlat_summer_ladders` (C/G MODTRAN runs) | **works today** |
| Pending | 29–100 km | *(no shipped data — G7–G11 / I-runs)* | **PENDING** |
| Vacuum | ≥ 100 km | Gap 95 exo-altitude vacuum leg (code, not data) | **works today** |

The 29–100 km band is above the ladder's 29 km ceiling but **below** the 100 km
atmosphere top, so the vacuum leg does not yet apply and the interpolator refuses
the query (`AtmosphereValidationError: … outside the available range [0, 29000]`).
The script catches exactly that refusal and marks the rung PENDING — it never
invents a number for a band it has no data for.

---

## Results (MWIR 3–5 µm, LEO sensor 500 km, nadir, sub-pixel 900 K / 4 m² plume)

| Target altitude [km] | Band | τ_up (3–5 µm) [-] | SNR [-] |
|---:|:--:|---:|---:|
| 0 | interpolated | 0.4152 | 325.45 |
| 1 | interpolated | 0.4886 | 352.97 |
| 5 | interpolated | 0.7001 | 423.85 |
| 10 | interpolated | 0.8106 | 460.47 |
| 20 | interpolated | 0.8945 | 494.68 |
| 29 | interpolated | 0.9425 | 518.17 |
| 40 | pending | — | PENDING (G7–G11) |
| 50 | pending | — | PENDING (G7–G11) |
| 60 | pending | — | PENDING (G7–G11) |
| 80 | pending | — | PENDING (G7–G11) |
| 100 | vacuum | 1.0000 | 630.11 |
| 150 | vacuum | 1.0000 | 720.68 |
| 200 | vacuum | 1.0000 | 841.35 |
| 300 | vacuum | 1.0000 | 1263.32 |

*(These absolute numbers are illustrative — the `midlat_summer_ladders` family
ships slit-degraded to 5 cm⁻¹ FWHM and its 0–29 km values are the frozen shipped
library; when the boost-ladder runs land and the library is rebuilt, the 0–29 km
rungs may shift slightly and the 29–100 km rungs fill in.)*

---

## Physics / modeling notes

- **τ_up rises monotonically over 0–29 km** (0.4152 → 0.9425): as the booster
  climbs, less absorbing column sits above it, so more of its MWIR emission
  reaches the sensor. The monotone-in-altitude check passes.
- **τ_up ≡ 1.0000 above 100 km** is the Gap 95 vacuum leg: a target at or above
  the atmosphere top sees no atmosphere, served exactly by code (`exo_target.py`),
  no run required.
- **SNR keeps rising across the vacuum leg** (630 → 1263 over 100 → 300 km) even
  though τ_up is pinned at 1. That is **not** an atmosphere effect — it is the
  **closing slant range**: R = sensor − target altitude (nadir) shrinks from
  400 km to 200 km, the plume's pixel fill fraction grows, and the sub-pixel
  signal rises with it. The scenario separates the two effects explicitly so the
  reader does not misread the vacuum climb as residual absorption.
- **Regime is SUB_PIXEL, not point-source.** A 4 m² (2 m) plume at LEO slant
  range subtends √A_t/R ≈ 4 µrad against a ~16.7 µrad IFOV — 0.22× the PSF FWHM.
  That is too large for the point-source approximation (which the chain enforces
  at ≤ 0.1·PSF_FWHM, raising an actionable error otherwise) and far too small to
  fill a pixel, so the sub-pixel regime is the physically correct one.
  `source.regime_override = "sub_pixel"` locks it (matching the derived regime, so
  no regime-mismatch warning) and keeps the in-pixel background.

---

## Friction / lessons

- **Full-well saturation, twice (Gap 65).** A 900 K MWIR plume is bright; the
  first integration time clipped the well and silently pinned SNR (the recurring
  6.1/6.2/8.2 failure mode). Fixed by shortening the frame. Then a *second* clip
  appeared only at the high-altitude rungs — as the booster closes range the fill
  fraction grows, so the brightest case is the *last* rung, not the first. The
  frame had to be sized for the worst-case (closest) rung, not just the launch
  rung. Lesson: for a sweep, check the saturation envelope at **both** ends.
- **The scenario is warning-free by construction** (the CU-166 owner bar). Two
  backend-inherent notices are filtered as documented expected behavior — the
  ladders' missing downwelling column (no midlat_summer H-run) and the
  interpolated backend's Option-C sun-leg collapse — while saturation warnings
  are deliberately left enabled (Gap 65).

---

## Forward path (do not run yet)

When the MODTRAN boost-ladder run set (G7–G11 nadir + I1–I9 off-nadir) is
delivered and the library is rebuilt (plan §4, gated on delivered tape7s — **not
started here**), the 29–100 km rungs flip from PENDING to interpolated values and
this same script covers the full 0–300 km trajectory with **no code change**. The
off-nadir extension (45°/60° LOS zenith) is the I-run remainder of the same plan.

---

## Gaps Identified

See `gaps.md`.
