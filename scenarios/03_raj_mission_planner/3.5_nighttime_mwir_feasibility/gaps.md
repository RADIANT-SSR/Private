# Scenario 3.5 — Gaps and Friction

## RESOLVED / already-available

The catalog flagged five gaps for 3.5. Three were closed by earlier T4 work
and are simply consumed here:

- **NEDT output** — `nedt_K` in `result.metrics` (Gap 3; exact dS/dT from
  Gap 43). Used as the detectability floor.
- **Minimum resolvable ΔT (MRT)** — `mrt_at_nyquist_K` in `result.metrics`
  (Gap 53 / `performance.minimum_resolvable`). Used for the resolvable-detail
  check.
- **Extended target-vs-background differential** — the first-class contrast
  reference (Gap 52 / ADR-0005). Used for `contrast_snr`; validated here to
  match two-run differencing to the digit.

## Gaps filed to the registry (`docs/tracking/gaps.md`)

### Gap 57 — `standard_atmosphere` preset is radiometrically thin
Selecting `standard_atmosphere = "tropical"` (or any of the six presets)
only changes the downwelling **emission temperature** via the sea-level
temperature table (`simple.py:_T_SEA_LEVEL_K`, tropical 299.65 vs
us_standard 288.15 K). It does **not** set the profile-appropriate humidity,
ozone, or transmission. Water vapour is a *separate* independent parameter
(`precipitable_water_cm`, default 1.4 cm = US-standard); so a user who picks
"tropical" but leaves PWV at the default gets tropical emission temperature
with **US-standard transmission** — silently wrong for MWIR/LWIR window
work, where tropical humidity is the dominant effect. This scenario sets
PWV = 4.1 cm explicitly as the workaround.

### Gap 58 — No GeoTIFF / raster reader
RADIANT has no importer for GeoTIFF (or any raster) surface-temperature or
land-cover maps. Raj's NOAA LST map is transcribed to a 1-D CSV strip as the
workaround; a real reader would ingest the 2-D field and (with Gap 56's
scene model) drive a per-pixel background.

### Gap 59 — No solar-dependence analysis mode
There is no built-in toggle to add/remove a reflected-solar term from an
emissive scene and report the day/night delta. This scenario computes the
thermal-vs-reflected-solar comparison analytically (`core.blackbody`)
script-side; a first-class "day vs night" mode would package it and fold the
reflected term into the chain radiometry rather than a side calculation.

## CU filed (`docs/tracking/Cleanup_Backlog.md`)

### Contrast-reference `contrast_snr` drifts when the pixel saturates
The ADR-0005 combined-noise formula
(`contrast_snr.py`, `n_ref² = N_t² − S_t + S_ref`) uses the pre-full-well
`signal_e`. When the target pixel saturates (signal_e > full well), the
reported `contrast_snr` diverges from the true two-run differential and can
even **exceed the absolute `snr`** (observed: LWIR contrast_snr 6250 vs snr
2447 at FWC 2×10⁷ with signal_e 2.6×10⁷). Physically impossible for a
differential; a saturation-aware clamp (or an explicit saturation warning on
the contrast metric) is needed. This scenario sidesteps it by sizing the
integration below full well. Filed as a Category-B CU.

## Friction / lessons

- **Two parameters make an atmosphere.** The preset name and the humidity
  are independent; picking a climate zone does not set its water column.
  Easy to get a physically inconsistent atmosphere without noticing.
- **MWIR is only modestly emission-dominated at 295 K (×5).** The nighttime
  argument is not "solar is always negligible in MWIR" — it is "at night the
  reflected term is exactly zero." Stating it as orders-of-magnitude would
  be wrong for MWIR.

## Catalog status

Priority 34 (Scenario 3.5) — **DONE**. The three metric gaps (NEDT, MRT,
extended differential) were closed by prior work and are consumed; the two
genuinely-missing capabilities (tropical humidity coupling, GeoTIFF reader)
plus the solar-mode gap are filed (Gaps 57–59), and the saturation
interaction is CU'd.
