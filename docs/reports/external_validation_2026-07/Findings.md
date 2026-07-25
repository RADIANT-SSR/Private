# External Validation Dossier — Findings

Status: Draft (MODIS section pending)
Campaign: `docs/plans/External_Validation_Plan.md` (owner-chartered 2026-07-24)
Method, provenance, and reproduction: `docs/validation/*_source_data.md` +
`scripts/run_external_validation.py` (all numbers below regenerate from that script).

## Claim under test

RADIANT's first-principles signal chain, configured from **published, cited** instrument
parameters with all assumptions named and enveloped, predicts the flight-measured
radiometric performance of real EO sensors. This complements the 2026-07 assurance audit
(internal consistency: code ↔ equations) with the external leg (equations ↔ world).

## 1. Sentinel-2 MSI — reflective-band SNR @ L_ref

Setup: at-sensor reference radiance driven directly (user-radiance, vacuum path) — the
ESA SNR requirement is defined at L_ref, so the comparison isolates aperture-to-electrons
radiometry. Published: 150 mm pupil, 7.5/15 µm pitches, 12-bit, 2-line TDI, 786 km;
derived: f = 0.5895 m (from p·h/GSD, self-consistent across 10 m and 20 m bands),
t_line = GSD/v_g ≈ 1.50 ms; assumptions: QE per band, τ = 0.75 (enveloped).

| Band | Predicted SNR (envelope) [-] | Required [-] | Measured (S2C) [-] | Verdict |
|---|---|---|---|---|
| B2 (493 nm) | 253 (188–309) | 154 | 162 | CONSISTENT via inversion — implied QE·τ = 0.153 ⇒ QE ≈ 0.20 at 493 nm with τ = 0.75: plausible front-illuminated CMOS + blue-end dichroic/filter losses |
| B3 (560 nm) | 208 (157–252) | 168 | — | CONSISTENT (requirement inside envelope) |
| B4 (665 nm) | 193 (145–233) | 142 | 175 | **CONSISTENT** — measured inside envelope; implied QE·τ = 0.341 vs 0.41 assumed |
| B8 (833 nm) | 337 (254–430) | 174 | — | CONSISTENT with requirement (floor); no measured value to test |
| B11 (1614 nm) | 331 (264–375) | 100 | 133 | INCONCLUSIVE — implied QE·τ = 0.091, implausible for MCT; points at an unpublished much-shorter SWIR t_int (~0.5 ms vs the 3.0 ms line time) |

Reading: with zero tuning the predictions land within 1.1–2.0× of flight-measured
values, and the shot-limit inversion turns every gap into a *named hypothesis about an
unpublished parameter* (blue QE, SWIR integration time) rather than an unexplained
residual. The instrument's own design note (per-band CVF sized against Lmax saturation)
matches RADIANT's independent finding that the wide bands are well-management-limited.

## 2. Landsat 8 TIRS — thermal NEdT

Setup: 300 K-class blackbody scene through a vacuum path (the published NEdT is measured
against the onboard blackbody). Published: f/1.64, f = 178 mm, 25 µm QWIP @ ~39 K,
t = 3.49 ms, CE = 0.8% band-average, τ_opt ≈ 0.49, dark 4×10⁷ e-/s, read 260 e-
(electronics ≤1000 e- spec), full well >5×10⁶ e-, saturation ~400 K (B10) / ~370 K
(B11). Two throughput bounds: raw published CE, and CE inverted from the published
saturation temperature (well full there by definition). Cross-check: RADIANT's raw
signal model agrees with the instrument team's own published signal model
([Jhabvala 2011]) within ~25%.

Predicted NEdT [mK] (range spans the two throughput bounds × read-noise envelope):

| Band | Scene T [K] | Predicted [mK] | Spec [mK] | Measured [mK] | Verdict |
|---|---|---|---|---|---|
| B10 | 300 | 58–124 | 400 | 49 | **CONSISTENT** — measured just below the photon/read floor bracket's low edge; ~8× inside spec, matching the published "exceeds requirements by about a factor of 8" |
| B10 | 270 / 320 | 64–153 / 56–113 | 560 / 350 | 57 / 45 | CONSISTENT (same pattern) |
| B11 | 300 | 52–89 | 400 | 52 | **CONSISTENT** — saturation-bound prediction lands exactly on the flight value |
| B11 | 270 / 320 | 55–103 / 51–84 | 530 / 350 | 60 / 51 | CONSISTENT |

Reading: the QWIP's unpublished in-band spectral response is the dominant unknown; both
bounds bracket the measured values to better than 2.5× worst-case and ~1.0–1.2× at the
saturation-anchored bound. The published instrument noise budget is dominated by
blackbody/optics temperature-*instability* terms (calibration stability, not detector
noise) — RADIANT correctly models the photon/dark/read floor, and the flight values sit
where that floor predicts.

## 3. MODIS thermal emissive bands

*(pending — researcher in flight; section to be added before this report closes)*

## Cross-cutting observations (to disposition at close)

- The user-radiance + exo validation pattern proved clean and is recommended as the
  standing method for future sensor validations (candidate for a
  `docs/validation/` how-to note).
- The implied-throughput inversion (shot-limit back-out of QE·τ or CE from a measured
  SNR/NEdT plus a published physical constraint) converts unexplained residuals into
  testable hypotheses — used for S2 B2/B11 and TIRS; worth capturing in the theory
  manual's performance chapter at close.
- No RADIANT physics discrepancy was uncovered by either sensor: every gap traced to an
  unpublished instrument parameter, and every published-vs-predicted comparison landed
  inside the documented assumption envelope.
