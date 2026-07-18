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

## Results (real MODTRAN 6, 2026-07-17)

| Profile | τ SimpleAtmosphere [-] | τ MODTRAN 6 [-] | τ residual | SNR Simple [-] | SNR MODTRAN [-] | SNR residual |
|---------|------------------------|------------------|------------|----------------|------------------|----------------|
| us_standard | 0.524 | 0.517 | −1.4% | 684.1 | 575.9 | −18.8% |
| tropical | 0.161 | 0.421 | +61.8% | 607.5 | 582.5 | −4.3% |
| midlat_summer | 0.269 | 0.458 | +41.3% | 628.7 | 579.5 | −8.5% |
| midlat_winter | 0.670 | 0.544 | −23.2% | 717.4 | 574.0 | −25.0% |
| subarctic_summer | 0.388 | 0.492 | +21.2% | 654.0 | 570.7 | −14.6% |
| subarctic_winter | 0.814 | 0.571 | −42.5% | 750.4 | 582.3 | −28.9% |

(residual = (MODTRAN − Simple) / MODTRAN, %; τ is the 3.5–5.0 µm
band-mean total transmittance, dimensionless; SNR is the full-chain
extended-scene contrast SNR, dimensionless)

- **SimpleAtmosphere over-responds to profile water vapor — in both
  directions.** Real MODTRAN's profile-to-profile band-mean τ spans a
  narrow 0.42–0.57 (~26% spread): the MWIR band is anchored by the
  saturated, well-mixed CO₂ 4.3 µm core and a continuum floor that no
  climate profile escapes. SimpleAtmosphere spans 0.16–0.81 (5×) —
  too absorbing for wet profiles (tropical +62% residual), too
  transparent for dry ones (subarctic_winter −43%).
- **The band fit is nearly exact at us_standard (−1.4%)** and degrades
  monotonically as PWV departs from it in either direction — the
  signature of a fit calibrated at one reference profile whose
  H₂O-window weighting extrapolates poorly across climates. (Gap 57's
  profile-coupled PWV substitution moves the *input* water column
  correctly; this residual is in the *band-model response* to that
  column.)
- **SNR residuals (−4% to −29%) are smaller than the worst τ residuals
  and don't track them** (tropical: worst τ, best SNR). The
  extended-scene contrast term attenuates target and background by the
  same τ, cancelling much of the transmittance error in the signal
  ratio; what survives is mostly the path-radiance and noise-floor
  difference. Real-MODTRAN SNR is nearly profile-independent (571–582)
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
- **SNR is far less sensitive to atmosphere-model choice than raw
  transmittance is**, for an extended-scene contrast measurement. A
  scenario asking "how much does my *transmittance estimate* change"
  and one asking "how much does my *SNR prediction* change" have
  different answers — worth remembering when scoping which metric
  matters for a given decision.
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
