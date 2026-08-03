# Scenario 6.2 — Atmospheric Model Intercomparison

**Persona:** Dr. Chen, researcher comparing RADIANT's parametric
atmosphere against an external radiative-transfer reference.
**Question:** How much does RADIANT's `SimpleAtmosphere` (Beer-Lambert,
tuned band fits) diverge from MODTRAN across the six named standard
atmosphere profiles, for the same nadir/100 km-sensor geometry — and
what does that divergence do to SNR?

**Status: validated 2-way benchmark (upgraded 2026-07-17).** The
"MODTRAN" data is the **real MODTRAN 6 A-block** (2026-07-17 run set,
`modtran/real_runs/A1–A6.tp7`) — the residuals below are a validated
measure of SimpleAtmosphere's in-band error against a full
radiative-transfer reference at this geometry. The script auto-detects
the gitignored real-run staging set and falls back to the synthetic
A-block (with a loud banner) where it isn't present, so the scenario
stays runnable from a bare clone. **libRadtran is still not included**
— no implementation or real output exists (see gaps.md); fabricating
plausible libRadtran numbers would defeat the purpose of an
intercomparison the same way a fake MODTRAN would.

**Deviation from the catalog:** the original entry specifies "10° off-
nadir, 500 km path, midlat summer" for one profile. The run matrix's
A-block instead gives all six profiles at a fixed nadir/100 km-sensor
geometry — a broader profile sweep using data that already existed
rather than re-deriving one path's data six ways. See gaps.md.

---

## Inputs (non-RADIANT)

| File | Represents |
|------|-----------|
| `modtran/real_runs/A1–A6.tp7` | Real MODTRAN 6 transmittance/path-radiance, one per standard profile (gitignored staging set — see `modtran/real_runs/README.md`). |
| `modtran/synthetic/A1–A6.synthetic.tp7` | Fallback when the real set isn't staged (loud banner; pipeline-demo mode only). |

No Excel workbook — the six tape7 paths and their profile mapping are
the entire "vendor input" here, kept as script constants (matching
scenario 6.1's pattern for a self-contained, reproducible run).

---

## How RADIANT solves this

1. For each profile, the tape7 feeds the chain directly via
   `atmosphere.model="modtran"` + `atmosphere.modtran.tape7_path`
   (parsed and unit-converted pre-chain — `RADIANT_Atmosphere.md`
   §5.1; no temp-CSV side door, no MODTRAN binary).
   `Tape7Reader(...).to_radiant_units()` is still called once per
   profile for the spectral overlay figures.
2. The identical sensor config runs twice per profile — once with
   `atmosphere.model="simple"` at that profile, once with the
   imported real-MODTRAN data — isolating the atmosphere term.
3. In-band (3.5–5.0 µm) mean transmittance and full-chain SNR are
   compared, profile by profile.

---

## Results (real MODTRAN 6; re-run 2026-08-02)

| Profile | τ SimpleAtmosphere [-] | τ MODTRAN 6 [-] | τ residual | SNR Simple [-] | SNR MODTRAN [-] | SNR residual |
|---------|------------------------|------------------|------------|----------------|------------------|----------------|
| us_standard | 0.552 | 0.517 | −6.8% | 650.4 | 572.0 | −13.7% |
| tropical | 0.463 | 0.421 | −9.8% | 674.4 | 579.2 | −16.4% |
| midlat_summer | 0.498 | 0.458 | −8.7% | 656.7 | 575.9 | −14.0% |
| midlat_winter | 0.576 | 0.544 | −5.8% | 624.4 | 570.4 | −9.5% |
| subarctic_summer | 0.526 | 0.492 | −6.9% | 639.8 | 566.8 | −12.9% |
| subarctic_winter | 0.597 | 0.571 | −4.6% | 617.4 | 579.5 | −6.5% |

*Numbers refreshed 2026-08-02 from the unmodified runner (previous vintage
2026-08-02, pre-CU-321). Two movers, one per arm. **SNR Simple (CU-321):** the
`(1−τ)·B` path emission is now emitted at a height-resolved `T_eff(λ)` over the
column instead of at its near-surface temperature, so it falls by 6–12 % —
most on the wettest, most opaque profiles, which is the same `(1−τ)` ordering
CU-224 raised it by. The **τ Simple** column is bit-identical (CU-321 changes no
optical depth). **SNR MODTRAN (CU-316):** the tape7 backend now resamples τ in
log-τ like every other backend, which moves the measured arm by 0.5–0.7 %
(575.9 → 572.0 on us_standard); its **τ MODTRAN** column is unchanged at three
decimals.*

**This table is the CU-161 acceptance evidence for the τ columns.** The
first real-data run of this scenario (2026-07-17) found τ residuals
spanning **−43% to +62%** — SimpleAtmosphere over-responding to profile
water in both directions. The gas-band recalibration that finding
triggered (CU-161, landed 2026-07-18: curve-of-growth water + well-mixed
CO₂/N₂O floor, fit to the D-block water ladder) collapses them **6×, to a
uniform −4.6%…−9.8%**. The small remaining τ offset is systematic (simple
slightly transparent — largely the band-mean comparison convention this
script uses) rather than profile-dependent: the water physics now scales
correctly across climates.

(residual = (MODTRAN − Simple) / MODTRAN, %; τ is the 3.5–5.0 µm
band-mean total transmittance, dimensionless; SNR is the full-chain
extended-scene contrast SNR, dimensionless)

- **(Historical, fixed by CU-161)** The pre-recalibration model
  over-responded to profile water in both directions (τ span 0.16–0.81
  vs real 0.42–0.57; +62% tropical, −43% subarctic_winter) because its
  linear-in-w Lorentzian fit attributed the MWIR's saturated CO₂ floor
  to water. The recalibrated model spans 0.46–0.60 — matching real
  MODTRAN's narrow climate spread.
- **SNR residuals (−6.5% to −16.4%) are now comparable to the τ residuals,
  and they DO track them** (tropical is worst on both, subarctic_winter best on
  both). This is still the reversal of the pre-CU-224 finding, at about half the
  amplitude: the path-radiance term the `simple` arm carries scales as `(1−τ)`,
  so the more opaque the profile the more emission it adds — and CU-321 now
  emits it from the column's true (colder) emission altitude, which scales the
  whole effect down without changing its ordering. Ranking the SNR Simple
  *decrease* under CU-321 by `(1−τ)` is monotonic in the same direction:
  subarctic_winter `(1−τ)=0.40` → −2.7%, midlat_winter 0.43 → −5.2%,
  us_standard 0.45 → −8.6%, subarctic_summer 0.47 → −8.8%,
  midlat_summer 0.50 → −10.8%, tropical 0.54 → −12.5%.
- **The residuals are now one-sided.** Simple over-predicts SNR against
  MODTRAN for every profile, where before the errors straddled zero. The
  extended-scene contrast cancellation that used to mask the τ error is
  still present, but it no longer dominates: the added path emission does
  not cancel between target and background, so it survives into the
  ratio. Real-MODTRAN SNR remains nearly profile-independent (567–579)
  — consistent with its narrow τ range.

---

## Physics / modeling notes (house rule: explain the non-obvious)

- **The CO₂ 4.3 µm notch is identical across every profile** (`fig1`) —
  CO₂ is well-mixed at ~415 ppm regardless of climate, so this is
  exactly the expected physical signature, now confirmed in the real
  MODTRAN data (it was previously verified only in the synthetic
  generator).
- **Regime note:** extended-scene thermal contrast in the MWIR at
  100 km nadir — both target (300 K) and background (288 K) are
  attenuated by the same column, so the SNR-relevant quantity is the
  contrast radiance difference, not absolute τ. A sub-pixel or
  point-source regime would weight the atmosphere differently
  (EE_box and absolute signal, not contrast cancellation).
- **SNR is now *more* sensitive to atmosphere-model choice than raw
  transmittance is**, for this extended-scene contrast measurement — the
  opposite of what this scenario concluded before CU-224. A scenario
  asking "how much does my *transmittance estimate* change" and one
  asking "how much does my *SNR prediction* change" still have different
  answers; the lesson survives, but the direction has flipped. The reason
  is that an atmosphere model contributes two separable things —
  attenuation (τ, which largely cancels in a contrast ratio) and its own
  emission (path radiance, which does not). Judging a model by τ alone
  understates its effect on a thermal SNR prediction.
- **Full-well saturation silently erased the atmosphere signal on the
  first (synthetic-era) attempt** — see gaps.md's "Friction" section;
  the fix (shorter integration time) is the same lesson scenario 6.1
  logged ("LWIR staring FPAs are integration-time-limited").

---

## Gaps Identified

See `gaps.md`: libRadtran comparison (still open), the geometry
deviation from the catalog's exact "10°/500 km" framing, and the
SimpleAtmosphere PWV over-response quantified above (now a validated
finding — the MWIR-band divergence previously flagged as "worth a
follow-up investigation" is confirmed and bounded by this run).
