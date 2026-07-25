# Landsat 8/9 TIRS — Source Data for External Validation

Retrieved 2026-07-24 by cited web research (solo researcher; MDPI/USGS 403'd — full texts
read via Wayback captures and NASA NTRS as noted). Confidence classes as in
`sentinel2_msi_source_data.md`.

Primary sources:
- [Reuter 2015] Reuter et al., "The Thermal Infrared Sensor (TIRS) on Landsat 8: Design
  Overview and Pre-Launch Characterization," Remote Sensing 7(1):1135–1153,
  doi:10.3390/rs70101135 — https://www.mdpi.com/2072-4292/7/1/1135
- [Montanaro 2014b] Montanaro, Levy, Markham, "On-Orbit Radiometric Performance of the
  Landsat 8 Thermal Infrared Sensor," Remote Sensing 6(12):11753–11769,
  doi:10.3390/rs61211753
- [Montanaro 2014a] Montanaro et al., "Radiometric Calibration Methodology of the Landsat
  8 Thermal Infrared Sensor," Remote Sensing 6(9):8803–8821, doi:10.3390/rs6098803
- [Jhabvala 2011] Jhabvala et al., "The QWIP Focal Plane Assembly for NASA's Landsat Data
  Continuity Mission," Proc. SPIE, NASA NTRS 20110015428
- [Barsi 2022] Barsi et al., "Early Radiometric Performance of Landsat-9 Thermal Infrared
  Sensor," NASA NTRS 20220016849
- [eoPortal-L8] https://www.eoportal.org/satellite-missions/landsat-8-ldcm

## NEDT (the validation target) — Landsat 8, [Montanaro 2014b] Table 2

| Band | λ range (50% pts) | Scene T [K] | NEdT spec [K] | NEdT measured [K] |
|---|---|---|---|---|
| 10 | 10.6–11.2 µm | 270 | 0.56 | 0.057 |
| 10 | 10.6–11.2 µm | **300** | **0.40** | **0.049** |
| 10 | 10.6–11.2 µm | 320 | 0.35 | 0.045 |
| 11 | 11.5–12.5 µm | 270 | 0.53 | 0.060 |
| 11 | 11.5–12.5 µm | **300** | **0.40** | **0.052** |
| 11 | 11.5–12.5 µm | 320 | 0.35 | 0.051 |

On-orbit method: per-detector σ over 1750 onboard-blackbody frames → brightness
temperature. "Approximately 0.05 K @ 300 K in both bands, exceeding requirements by about
a factor of 8." Landsat-9 TIRS-2: ≤0.05 K (B10) / ≤0.07 K (B11) @ 300 K [Barsi 2022].
Companion NEdL @300 K: 0.0070 / 0.0064 W/m²/sr/µm measured vs ≤0.059 / ≤0.049 required.

## Instrument

| Parameter | Value | Units | Source | Confidence |
|---|---|---|---|---|
| Telescope | 4-element refractive (3 Ge + 1 ZnSe), f/1.64, ~diffraction-limited | — | [Reuter 2015] | published |
| Focal length | 178 | mm | [Reuter 2015] | published |
| Entrance pupil diameter | 108.5 | mm | derived: 178/1.64 | derived |
| Optics temperature | 185 (180–190, ±0.1 K stabilized) | K | [Reuter 2015], [eoPortal-L8] | published |
| Scene-select mirror temperature | 293 | K | [Jhabvala 2011] Table 1 | published |
| Total optical transmission | ≈0.49 | — | [Jhabvala 2011] ("Topt≈0.49") | published (model value) |
| Detector | GaAs QWIP, 3× 640×512 SCAs, Indigo ISC9803 ROIC | — | [Jhabvala 2011], [Reuter 2015] | published |
| Pixel pitch | 25 | µm | [Reuter 2015], [Jhabvala 2011] | published |
| FPA temperature | ~39 flight (43 design) | K | [Reuter 2015] / [Jhabvala 2011] | published (discrepancy flagged) |
| Integration time (as flown) | 3.49 | ms | [Reuter 2015] | published |
| Frame rate / averaging | 70 fps = one frame per 100 m line; published NEdT is single-frame (no co-adding found) | — | [Reuter 2015]; readout scheme [Montanaro 2014a] | published / assumption (no co-adding) |
| Conversion efficiency CE = g·η (band-avg, operating bias) | 0.8 | % | [Jhabvala 2011] | published |
| Photoconductive gain g | 0.3 | — | [Jhabvala 2011] | published |
| Dark current | 4×10⁷ | e-/s | [Jhabvala 2011] | published |
| Read noise (ROIC, typical) | 260 | e- RMS | [Jhabvala 2011] | published |
| Electronics noise (spec ceiling) | <1000 | e- RMS | [Jhabvala 2011] Table 1 | published (bound) |
| Full well | >5×10⁶ | e- | [Jhabvala 2011] | published |
| ADC | 12 | bit | [Reuter 2015] | published |
| Saturation temperature | ~400 K (B10) / ~370 K (B11); calibrated 240–360 K | K | [Reuter 2015] | published |

## Geometry

705 km sun-synchronous, 98.2°, 16-day repeat, 10:00 LTDN; native GSD 100 m; IFOV
141 µrad (= 25 µm / 178 mm); 185 km swath / 15° FOV; pushbroom, ground speed ~7 km/s
[Reuter 2015], [eoPortal-L8].

## Published noise budget ([Jhabvala 2011] Table 2 — 12 µm band, 300 K, t=5.5 ms model)

Variances [e-²]: dark shot 1.32e5; signal shot 1.67e6; ΔT-instability dark 1.25e6,
telescope background 9.41e6, mirror 1.58e6, optics 1.14e4; read 3.03e5; electronics 1e6;
A/D 4.87e5. Total 3.98e3 e- RMS; S_ΔT = 2.52e4 e-/K → modeled NEΔT 0.16 K (conservative
vs 0.049 K achieved; dominated by temperature-*instability* terms, not photon noise).

## Modeling notes

- **Throughput treatment:** RADIANT's raw published-parameter model (CE 0.8%,
  τ 0.49, 3.49 ms) collects 7.9×10⁵ e- at 300 K (B10) — within ~25% of
  [Jhabvala 2011]'s own signal model and only 19% well fill: the published
  parameter set is internally consistent. Because the QWIP in-band spectral
  response shape is unpublished, the effective CE is additionally **inverted from
  the published per-band saturation temperatures** (400 K B10 / 370 K B11 — well
  full there by definition), giving a second, physically-anchored bound
  (CE_eff ≈ 1.6–2.1× the band-average published CE). Predictions are reported as
  the raw-CE and saturation-CE bracket.
- ΔT-instability terms (blackbody/optics/mirror temperature knowledge) are calibration
  stability, not detector noise — RADIANT models the photon/read/dark floor; the measured
  0.049 K sits between the shot floor and the 0.16 K conservative model, and the
  well-constrained inversion is expected to land near it.
- Use t = 3.49 ms (as flown), not the 5.5 ms model value; FPA 39 K flight.
