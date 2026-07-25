# Sentinel-2 MSI — Source Data for External Validation

Retrieved 2026-07-24 by cited web research (assurance-campaign researchers). Confidence
classes: **published** (verbatim from the cited source), **derived** (computed here from
published values — formula shown), **assumption** (engineering estimate, marked, with the
sensitivity range used in the validation envelope).

Primary sources:
- [S2-SW] SentiWiki "S2 Mission", https://sentiwiki.copernicus.eu/web/s2-mission
  (ESA; spectral/SNR Table 3, orbit Table 1)
- [S2-EO] eoPortal "Copernicus: Sentinel-2",
  https://www.eoportal.org/satellite-missions/copernicus-sentinel-2 (page rev. 2025-12-07)

## Instrument

| Parameter | Value | Units | Source | Confidence |
|---|---|---|---|---|
| Telescope | TMA, SiC, 3 aspheric mirrors | — | [S2-EO], [S2-SW] | published |
| Pupil (aperture) diameter | 150 | mm | [S2-EO] "pupil diameter of 150 mm"; [S2-SW] "pupil diameter equivalent to 150 mm" | published |
| Effective focal length | 0.5895 | m | derived: $f = p\,h/\mathrm{GSD}$ = 7.5 µm × 786 km / 10 m; cross-checked 15 µm × 786 km / 20 m = same | derived |
| f-number | 3.93 | — | derived: $f/D$ = 0.5895/0.150 | derived |
| Optical transmission (telescope+filters) | 0.75 | — | **ASSUMPTION** (silvered TMA + dichroic + filter; envelope 0.60–0.85) | assumption |
| VNIR detector | monolithic CMOS, 12 modules/FPA, staggered | — | [S2-EO], [S2-SW] | published |
| VNIR pixel pitch (10 m bands) | 7.5 | µm | [S2-EO] Table 6 "7.5-15 µm pitch" (7.5 for 10 m bands, 15 for 20/60 m) | published (interpretation) |
| SWIR detector | MCT/CTIA hybrid, 195 K | — | [S2-EO], [S2-SW] | published |
| SWIR pixel pitch | 15 | µm | [S2-EO] Table 6 | published |
| TDI | 1 TDI stage for 2 lines (VNIR 10 m; SWIR B11/B12) | — | [S2-EO] Table 6; [S2-SW] | published (modeled as $N_{TDI}=2$ charge sum — see notes) |
| Quantization | 12 | bit | [S2-EO], [S2-SW] | published |
| VNIR read noise | 15 | e- RMS | **ASSUMPTION** from [S2-EO] "readout noise of the order of 130 µV rms" with an assumed CVF ~10 µV/e- (envelope 5–30 e-) | assumption |
| QE at band (see per-band) | — | — | **ASSUMPTION** (no published curves found) | assumption |
| Full well (analysis mode) | 500 000 | e- | sized above signal(Lmax) so the comparison never clips; the real MSI sizes per-band CTIA capacity/CVF to avoid Lmax saturation ([S2-EO]) — collected charge at L_ref is unaffected | analysis choice |

## Geometry

| Parameter | Value | Units | Source | Confidence |
|---|---|---|---|---|
| Orbit altitude | 786 | km | [S2-SW] Table 1; [S2-EO] | published |
| Inclination / LTDN | 98.62° / 10:30 | — | [S2-SW] Table 1 | published |
| Swath / FOV | 290 km / 20.6° | — | [S2-SW]; [S2-EO] Table 5 | published |
| GSD | 10 (B2,B3,B4,B8); 20 (B11) | m | [S2-SW]; [S2-EO] Table 5 | published |
| Line time (10 m bands) | ≈1.50 | ms | derived: GSD / v_g, v_g from two-body ground-track speed at 786 km (computed by `radiant.core.orbit.ground_track_speed_m_s`) | derived |

## Bands and radiometric requirement (S2A values, [S2-SW] Table 3; BW = FWHM)

| Band | λ center [nm] | BW [nm] | L_ref [W/m²/sr/µm] | SNR required @ L_ref | SNR measured (S2C, [S2-SW] Table 4) | QE assumption (envelope) |
|---|---|---|---|---|---|---|
| B2 | 492.7 | 64 | 128.00 | 154 | 162 | 0.50 (0.35–0.65) |
| B3 | 559.8 | 35 | 128.00 | 168 | — | 0.55 (0.40–0.70) |
| B4 | 664.6 | 30 | 108.00 | 142 | 175 | 0.55 (0.40–0.70) |
| B8 | 832.8 | 118 | 103.00 | 174 | — | 0.35 (0.25–0.50) |
| B11 | 1613.7 | 88 | 4.00 | 100 | 133 | 0.75 (0.60–0.85) |

(Lmin/Lmax also published in [S2-SW] Table 3; not used at the L_ref operating point.)

## Modeling notes

- **Why exo/user-radiance:** ESA's SNR requirement is defined *at* an at-sensor reference
  radiance L_ref, so the validation drives RADIANT with L_ref directly
  (`source.target.user_radiance_path`, `atmosphere.model = exo`) — atmosphere and scene
  models are deliberately out of the loop; this validates aperture-to-DN radiometry.
- **TDI interpretation:** "1 TDI stage for 2 lines" is modeled as a charge-domain sum of
  2 line periods (`readout.n_tdi = 2`): signal ×2, shot ×√2, read noise once. If ESA's
  phrase instead means one stage spanning a 2-line aperture, predicted SNR drops by up to
  √2 — carried in the envelope.
- **Dominant unknowns:** QE × τ product (the prediction scales as
  $\sqrt{QE\,\tau\,t_{int}\,N_{TDI}}$ in the shot limit) — the envelope columns propagate
  these; read noise is non-binding at L_ref (shot-dominated by >10×).
- **B11 caveat:** SWIR MCT with unpublished t_int for the 20 m focal plane; line time
  derived as 20 m / v_g ≈ 3.0 ms; weakest-confidence row.

## First-run inversion notes (2026-07-24)

Shot-limited inversion of the measured SNRs (implied QE·τ = assumed × (meas/pred)²):
B4 → 0.341 (vs 0.4125 assumed — **plausible**, inside the envelope);
B2 → 0.153 (QE ≈ 0.20 at 493 nm with τ = 0.75 — **plausible** for front-illuminated CMOS
plus blue-end dichroic/filter losses; resolves the first-run "tension" as a QE-assumption
artifact, not a physics discrepancy);
B11 → 0.091 (implausibly low for MCT SWIR QE ~0.75 — points instead at a much shorter
SWIR integration time than the derived 3.0 ms 20 m line time, e.g. effective
t ≈ 0.5 ms under the published pixel-deselection/TDI scheme, or CTIA well-limited
integration — **INCONCLUSIVE pending a sourced SWIR t_int**).
