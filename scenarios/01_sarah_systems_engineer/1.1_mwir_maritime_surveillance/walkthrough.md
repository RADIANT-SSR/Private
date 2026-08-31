# Scenario 1.1 — MWIR Maritime Surveillance Trade Study

**Persona:** Sarah, systems engineer on a proposal team.
**Question:** For a 500 km SSO MWIR ship-detection sensor (15–45 cm
aperture, f/2.5, InSb 640×512, 15 µm pixel), how do SNR, NEDT, NIIRS, and
detection range vary with aperture — and how much does using a real
atmospheric-transmittance dataset (vs. RADIANT's own parametric model)
change the answer?

**Status: validated trade study (upgraded 2026-07-17).** The atmosphere
data is the **real MODTRAN 6 `D2` run** (maritime aerosol, midlat_summer,
2026-07-17 run set, `modtran/real_runs/D2.tp7`) — the numbers below are
a real MODTRAN-vs-parametric comparison. The script auto-detects the
gitignored real-run staging set and falls back to the synthetic D2
(with a loud banner) where it isn't staged, so the scenario stays
runnable from a bare clone.

---

## Inputs (vendor-style — non-RADIANT)

| File | Represents |
|------|-----------|
| `inputs/insb_qe_representative.csv` | Representative InSb QE curve (cutoff ~5.4 µm, peak ~0.84 near 3.5 µm) — Sarah's vendor PDF has a QE *graph*, not data points; this is a typical-InSb digitization, not a specific vendor's curve (the catalog's stated gap — no PDF exists to digitize from). Band-averaged to a scalar QE for the chain (`detector.qe_value`), matching scenario 1.2's approach. |
| `modtran/real_runs/D2.tp7` | The MODTRAN tape7 Sarah's colleague gave her — real MODTRAN 6 (2026-07-17 run set; gitignored staging, see `modtran/real_runs/README.md`). `midlat_summer` profile, maritime aerosol (IHAZE=3), 23 km visibility, nadir 100 km→0. |
| `modtran/synthetic/D2.synthetic.tp7` | Fallback when the real set isn't staged (loud banner; pipeline-demo mode only). |
| `data/emissivity/steel.csv` | Ship-hull emissivity (RADIANT's library "steel" curve; catalog says "0.7–0.85 depending on paint, partially rusted" — no rust-specific curve exists, see gaps.md). |
| `data/emissivity/water_calm.csv` | Ocean background emissivity (catalog wants wind-state/sea-state dependence — not modeled, see gaps.md). |

---

## Atmosphere data: what's real, what isn't

`D2` is a **real MODTRAN 6 run** (2026-07-17 set): full DISORT
multiple-scattering radiance and band-model transmittance, with the
deck conventions verified against this very run set (CU-065/CU-067).
Two residual caveats:
- The exact MODTRAN build/band-model version string is pending from the
  run operator (recorded in `data/atmospheres/MANIFEST.md` when known).
- In synthetic-fallback mode (real set not staged) the old rules apply
  unchanged: `TOT TRANS` is genuine HITRAN line-by-line physics, the
  scattering columns are simplified, and nothing from that mode
  validates RADIANT's atmosphere physics (`modtran/synthetic/README.md`).

---

## How RADIANT solves this

1. **Import the tape7 directly.** `atmosphere.model="modtran"` +
   `atmosphere.modtran.tape7_path` points the chain at D2's tape7;
   RADIANT parses and unit-converts it pre-chain (no temp-CSV side
   door — `RADIANT_Atmosphere.md` §5.1, no MODTRAN binary involved).
2. **Two atmosphere configs, same geometry/target/detector**:
   `SimpleAtmosphere` (maritime aerosol, `midlat_summer`) vs. the
   imported `D2` data, so the comparison isolates the atmosphere term.
3. **Regime**: the 30×8 m ship at 532 km slant range is angularly
   *comparable to* the diffraction PSF at these apertures (not ≤ 10 % of
   it) — the point-source approximation's own validity check
   (`_validate_psf_regime_consistency`, Matrix §7) rejects it. Configured
   as `sub_pixel` instead, which is the physically correct call: at 15 cm
   aperture the ship is genuinely on the edge of being resolved.
4. **Detection range** via `detection_range_beer_lambert` — extrapolates
   the reference-range SNR outward using an extinction coefficient
   derived from the in-band mean transmittance (`α = −ln(τ̄)/R_ref`).

---

## Results (aperture = 30 cm, mid-sweep; real MODTRAN 6, D2 run set)

*Numbers refreshed 2026-08-30 from the unmodified runner (previous vintage
2026-08-29). One mover, and only in the SimpleAtmosphere column. **CU-335**
re-fitted the calibrated gas table's VIS/NIR/SWIR rows against the post-CU-253
Rayleigh. This is a 3–5 µm scene, so the only reach is the λ⁻⁴ tail in the
2.40–5.00 µm floors (+0.0010 / +0.0005 / +0.0001 OD): τ̄ 0.4593 → 0.4592,
SNR 1001.47 → 1001.45, range 2356.7 → 2356.5 km, NEDT and NIIRS unmoved at the
quoted precision. Two parts in 100 000 — recorded because the table moved, not
because the scenario did. The **MODTRAN 6** column is bit-identical: it carries
its own measured τ.*

*Prior vintage, 2026-08-29 (pre-CU-324). **CU-324:** `E_sky_thermal`'s
flux-diffusivity exponent became the geometric
`sec 48.2° = 1.50030` — the secant of the angle every up-looking MODTRAN deck in
the downwelling reference set was run at — instead of the CU-155 fitted
`D = 1.1`. The sky's effective emissivity rises, so the ε = 0.95 hull's
Kirchhoff-reflected sky term rises with it: SNR 980.55 → 1001.47 (+2.1 %),
NEDT 0.0256 → 0.0251 K, NIIRS 4.59 → 4.61, range 2344.6 → 2356.7 km. τ was
untouched (0.4593, bit-identical — the swap changes the downwelling emissivity,
not any optical depth). The **MODTRAN 6** column did not move at all: it
carries its own measured downwelling, so no fitted or derived sky constant
reaches it.*

*Prior vintage, for the trend: the 2026-08-02 refresh moved the Simple column
under CU-321 (SNR 1152.37 → 980.55) and the MODTRAN column under CU-316
(τ 0.4319 → 0.4277, SNR 917.36 → 916.18, range 2239.7 → 2227.3 km).*

| Metric | SimpleAtmosphere | MODTRAN 6 (real D2) |
|--------|-------------------|----------------------|
| SNR [-] | 1001.45 | 916.18 |
| NEDT [K] | 0.0251 | 0.0266 |
| NIIRS [-] | 4.61 | 4.55 |
| Detection range @ SNR=5 [km] | 2356.5 | 2227.3 |
| In-band transmittance [-] | 0.4592 | 0.4277 |

- **SimpleAtmosphere agrees with MODTRAN to ~7% on transmittance for this
  maritime MWIR column** (τ̄ 0.4592 vs 0.4277 real, the parametric model
  slightly *more* transparent). The earlier ~45% over-absorption was removed by
  the CU-155/161 water-ladder recalibration — scenario 6.2 is the dedicated
  validation, which collapsed the τ residuals across all six profiles ~6× to a
  uniform −5…−11% band. Detection range now differs by +5.8% (2356.5 vs
  2227.3 km), where the pre-recalibration model understated it by ~25%.
- **SNR: the parametric model reads ~9% high** (1001 vs 916). Its history in
  four steps: it read ~17% *low* before CU-224 (no down-looking path emission
  at all), swung to ~26% high when CU-224 added that emission at the column's
  near-surface temperature, settled at ~7% high once CU-321 resolved the
  emission temperature in altitude — a 100 km MWIR column emits mostly from
  cold air aloft, not from the boundary layer — and rose to ~9% high when
  CU-324 made the downwelling exponent geometric, which lifts the reflected-sky
  term of this ρ = 0.05 hull. The remaining gap is the parametric model being
  marginally the more transparent of the two, and its noise floor is
  correspondingly lower (NEDT 0.0251 vs 0.0266 K). τ, SNR, and range still do
  not move together — quote the metric the decision needs.
- **This is the entire point of scenario 1.1's original gap**: before
  `Tape7Reader`/CU-066, RADIANT had no way to *consume* a colleague's
  MODTRAN tape7 at all — Sarah was stuck re-deriving atmosphere from the
  parametric model regardless of what data she actually had on hand.

---

## Physics / modeling notes (house rule: explain the non-obvious)

- **SNR is flat across the aperture sweep (15→45 cm).** The sweep holds
  f/# fixed at 2.5, so focal length scales with aperture. At fixed f/#,
  per-pixel étendue — and thus photon flux for both the sub-pixel target
  and the extended ocean background — is invariant with aperture. The
  aperture benefit shows up entirely as resolution: NIIRS rises from 3.53
  to 5.13 (real D2) as the diffraction-limited PSF shrinks. A genuine "SNR from a
  bigger telescope" trade needs a fixed-focal-length (varying f/#) sweep,
  not a fixed-f/# aperture sweep — worth remembering for the next
  aperture trade study.
- **Detection range is a Beer-Lambert point-source extrapolation**, not a
  full-chain re-evaluation at each range — it assumes the extinction
  coefficient measured at 532 km holds out to ~2240–2420 km, which is
  unrealistic (curvature, refraction, and the actual atmosphere profile
  all change over that distance). Treat the range numbers as illustrating
  the *relative* SimpleAtmosphere-vs-MODTRAN sensitivity, not an
  operational range.
- **Regime = SUB_PIXEL, not POINT_SOURCE.** Matrix §7's own consistency
  check caught this — a useful sanity check that the target-vs-PSF size
  assumption isn't silently wrong.

---

## Gaps Identified

See `gaps.md` for the full list; summary: wind-state ocean emissivity
and rust-specific hull emissivity remain open. The "real MODTRAN
dataset" item closed 2026-07-17 (this upgrade), and the MODTRAN tape7
*parsing* gap the original catalog entry flagged closed earlier
(CU-066 + this scenario).

**Postscript (2026-08-02):** the SimpleAtmosphere maritime over-absorption
documented above was substantially corrected by CU-161 (commit `0aebdda`), and
the comparison table has since been re-run against current `main` — it is no
longer the pre-fix vintage. The prior "detection range nearly coincides"
reading and the "parametric model reads 17% low" reading both belonged to that
vintage and are superseded above.
