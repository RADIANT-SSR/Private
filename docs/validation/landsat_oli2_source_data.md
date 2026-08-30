# Landsat 9 OLI-2 — Source Data for External Validation

Compiled 2026-08-29. Unlike `sentinel2_msi_source_data.md` and `landsat_tirs_source_data.md`
(cited live web research), this document was compiled **from the modeling agent's training
corpus without live source access** (offline session). Citations are given for every value,
but numeric values carry an explicit recall-confidence class:

- **published** — requirement-table or design values reproduced consistently across many
  sources; recall risk negligible (band edges, L_typ, SNR requirements, aperture, ADC bits).
- **published (recalled)** — appears in the cited source but the specific number was
  reproduced from memory; verify against the source before treating as authoritative.
  Estimated recall uncertainty is noted per value.
- **derived** — computed here from other tabulated values (formula given).
- **assumption** — not published at the needed granularity; value chosen inside a stated
  envelope. The scenario's conclusions are tested against the envelope, not the point value.

A follow-up web-verification pass (any online session) should promote or correct every
"published (recalled)" entry; the scenario `gaps.md` carries this as an open item.

Primary sources:
- [Irons 2012] Irons, Dwyer, Barsi, "The next Landsat satellite: The Landsat Data
  Continuity Mission," Remote Sens. Environ. 122:11–21, doi:10.1016/j.rse.2011.08.026 —
  OLI requirements table (L_typ, SNR@L_typ, band edges, GSD).
- [Knight 2014] Knight & Kvaran, "Landsat-8 Operational Land Imager Design,
  Characterization, and Performance," Remote Sensing 6(11):10286–10305,
  doi:10.3390/rs61110286 — instrument design: four-mirror telescope, FPA, detectors,
  integration time, prelaunch SNR.
- [Morfitt 2015] Morfitt et al., "Landsat-8 Operational Land Imager (OLI) Radiometric
  Performance On-Orbit," Remote Sensing 7(2):2208–2237, doi:10.3390/rs70202208 — on-orbit
  SNR at L_typ (the validation target's L8 baseline).
- [Barsi 2024] Barsi et al., Landsat 9 OLI-2 on-orbit radiometric performance
  (IGARSS/Rem. Sens. papers, 2022–2023) — OLI-2 SNR relative to OLI, 14-bit quantization.
- [eoPortal-L9] https://www.eoportal.org/satellite-missions/landsat-9 — mission summary.

## SNR @ L_typical (the validation target)

Band edges and L_typ / SNR requirement per [Irons 2012] (class: published). Measured
on-orbit SNR per [Morfitt 2015] (L8 OLI) — class: **published (recalled, ±15%)**; the
qualitative anchor (measured ≈ 2–3× requirement in every band) is high-confidence even
where the third digit is not. [Barsi 2024]: OLI-2 SNR is equal or slightly better than
OLI in all bands (14-bit quantization removes quantization-noise share at low signal);
no separate OLI-2 point values are relied on here.

| Band | Name | λ 50% edges [µm] | L_typ [W/m²/sr/µm] | SNR req @ L_typ | L8 measured (recalled ±15%) |
|---|---|---|---|---|---|
| 1 | Coastal aerosol | 0.435–0.451 | 40 | 130 | ~230 |
| 2 | Blue | 0.452–0.512 | 40 | 130 | ~360 |
| 3 | Green | 0.533–0.590 | 30 | 100 | ~300 |
| 4 | Red | 0.636–0.673 | 22 | 90 | ~225 |
| 5 | NIR | 0.851–0.879 | 14 | 90 | ~200 |
| 6 | SWIR 1 | 1.566–1.651 | 4.0 | 100 | ~265 |
| 7 | SWIR 2 | 2.107–2.294 | 1.7 | 100 | ~180 |
| 8 | Panchromatic | 0.503–0.676 | 23 | 80 | ~145 |
| 9 | Cirrus | 1.363–1.384 | 6.0 | 50 | ~165 |

Success criterion (mirrors scenario 9.1): the RADIANT prediction with assumption-class
parameters at their point values must land **above the requirement and within a factor
of ~2 of the measured value**, with the assumption envelope bracketing the measured
value. RADIANT models no PRNU, striping, or calibration-transfer noise, so the physics
prediction is expected to sit above (better than) the flight measurement.

## Instrument

| Parameter | Value | Units | Source | Confidence |
|---|---|---|---|---|
| Telescope | four-mirror off-axis anastigmat, front aperture stop | — | [Knight 2014] | published |
| Aperture stop diameter | 135 | mm | [Knight 2014] | published (recalled, ±5 mm) |
| Focal length | 886 | mm | [Knight 2014] | published (recalled, ±10 mm); self-consistent: 36 µm/886 mm × 705 km = 28.6 m ≈ 30 m GSD ✓ |
| f-number | 6.6 | — | derived: 886/135 | derived |
| Mirror coating | protected/enhanced silver | — | [Knight 2014] | published (recalled — coating type; curve is synthesized, see below) |
| Detectors (VNIR: B1–5, B8) | Si PIN photodiode, hybridized ROIC | — | [Knight 2014] | published |
| Detectors (SWIR: B6, B7, B9) | HgCdTe (~2.5 µm cutoff), same FPA | — | [Knight 2014] | published |
| Pixel pitch, 30 m bands | 36 | µm | [Knight 2014] | published (recalled; consistent with GSD, see focal length row) |
| Pixel pitch, pan band | 18 | µm | [Knight 2014] | published (recalled; 15 m GSD self-consistency) |
| FPA temperature | 210 | K | [Knight 2014] | published |
| Band filters | butcher-block interference-filter assembly over the FPA (one strip per band) | — | [Knight 2014] | published |
| Integration time, 30 m bands | 3.6 | ms | [Knight 2014] | published (recalled, ±0.4 ms); envelope 3.2–4.4 ms; line time is the 4.44 ms ceiling (derived below) |
| Integration time, pan | 1.8 | ms | derived: half the 30 m value (2× line rate) | derived |
| ADC quantization (OLI-2) | 14 (OLI was 12) | bit | [Barsi 2024], [eoPortal-L9] | published |
| Full well | 2×10⁶ (analysis mode) | e- | sized ≥4× the largest L_typ signal — never clips in this scenario; the real well is not anchored (saturation is out of scope) | assumption |
| Read noise | 200 (envelope 100–400) | e- RMS | not published at this granularity | assumption (non-binding: shot-dominated at L_typ in every band, see walkthrough) |
| QE, VNIR Si PIN | band-avg 0.70 (B1), 0.80 (B2), 0.85 (B3), 0.87 (B4), 0.78 (B5), 0.83 (B8); envelope ±0.15 | — | typical Si PIN response shape | assumption |
| QE, SWIR HgCdTe | band-avg 0.80 (B6), 0.75 (B7), 0.80 (B9); envelope ±0.15 | — | typical MCT response | assumption |
| Dark rate, VNIR @ 210 K | 100 | e-/s | Si PIN at 210 K is dark-negligible | assumption (non-binding: <1 e- per 3.6 ms frame) |
| Dark rate, SWIR @ 210 K | 5×10⁴ (envelope 10³–10⁶) | e-/s | 2.5 µm-cutoff MCT at 210 K | assumption (≤180 e-/frame at point value — shot-negligible vs ≥10⁵ e- signals) |

## Geometry

705 km sun-synchronous circular orbit, 98.2°, 10:00–10:15 LTDN, 185 km swath / 15° FOV,
pushbroom (7 000 / 14 000 detectors per 30 m / pan band across 14 FPA modules)
[Irons 2012], [Knight 2014] — class published. Derived: v_ground = v_orb·R_E/(R_E+h)
= 7 504·(6 371/7 076) = 6 756 m/s (spherical, Earth rotation neglected, ±2%);
line time = 30 m / 6 756 m/s = 4.44 ms (30 m bands), 2.22 ms (pan).

## Synthetic optical prescription (this scenario's differentiator)

No per-surface reflectance/transmittance curves are published for OLI. The scenario
therefore builds a **synthetic prescription** — every curve is generated by
`scripts/gen_oli2_coatings.py` (Rule 26 manifest: that script + the anchor tables in its
docstring are the generator; the CSVs under the scenario `data/` folder are its output):

| Element | Model | Anchor | Class |
|---|---|---|---|
| M1–M4 mirrors | one protected-silver R(λ) curve, monotone-spline through vendor-typical anchor points (0.945 @ 0.42 µm → 0.975 @ 0.60 µm → 0.985 @ 1.6 µm) | vendor-typical protected-Ag curves (Quantum Coating / ECI class) | assumption (synthetic; envelope ±0.01 per surface) |
| FPA window | fused silica, broadband AR both faces, T = 0.985 flat | typical two-surface AR residual | assumption (synthetic) |
| Band filters (9) | super-Gaussian T(λ) = T_pk·exp(−((λ−λc)/σ)^{2m}), m = 5, 50% points matched to the [Irons 2012] band edges; T_pk = 0.90 VNIR / 0.85 SWIR / 0.80 cirrus; 10⁻⁴ blocking floor | 50% edges published; peak transmission vendor-typical | edges: published; shape/peak: assumption (synthetic) |
| Butcher-block composite (study files) | sum of the eight non-overlapping 30 m-band strips over the blocking floor — one shared spectral element, per-configuration band edges select the strip (physically faithful to the actual filter assembly; ADR-0010 D-7 workaround, see Gap 103) | — | assumption (synthetic) |

End-to-end sanity: τ(B4) = 0.975⁴ × 0.985 × 0.90 ≈ 0.80 band-average — plausible for a
four-mirror silver telescope with a single filter substrate; treated as assumption-class
with the per-surface envelopes above (compound envelope ≈ ±0.06).

## Modeling notes

- **Scenario design mirrors 9.1**: flat user-radiance = L_typ through a vacuum
  (`atmosphere: exo`) — the requirement is defined at-aperture, so the model validates
  aperture-to-electrons radiometry, not an atmosphere.
- **Thermal self-emission of the train is modeled but non-binding**: elements carry
  Kirchhoff-derived ε = 1−R (mirrors) / 1−T (filters, window) at 290 K optics
  temperature; at λ ≤ 2.3 µm and 290 K the emitted term is many orders below L_typ.
- **Why the prediction should exceed flight SNR**: RADIANT's chain has no PRNU,
  no striping/banding, no calibration-transfer noise, and assumption-class QE is
  band-average optimistic. The 9.1 precedent landed 1.1–2.0× flight; the same envelope
  logic applies here (documented per band in the scenario walkthrough).
