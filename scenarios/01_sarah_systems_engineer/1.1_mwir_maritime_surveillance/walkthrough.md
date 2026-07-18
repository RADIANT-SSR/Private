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

## Results (aperture = 30 cm, mid-sweep; real MODTRAN 6, 2026-07-17)

| Metric | SimpleAtmosphere | MODTRAN 6 (real D2) |
|--------|-------------------|----------------------|
| SNR [-] | 1135.6 | 957.3 |
| NEDT [K] | 0.0208 | 0.0253 |
| NIIRS [-] | 4.69 | 4.58 |
| Detection range @ SNR=5 [km] | 1689.8 | 2113.8 |
| In-band transmittance [-] | 0.239 | 0.432 |

- **SimpleAtmosphere is ~45% too absorbing for this maritime MWIR
  column** (τ̄ 0.239 vs 0.432 real) — the same PWV over-response that
  scenario 6.2 quantified across all six profiles (midlat_summer:
  +41% τ residual there, consistent with this run). The detection-range
  extrapolation turns that into a +25% range difference (1690 →
  2114 km): a proposal quoting the parametric model would understate
  achievable maritime detection range by a quarter.
- **SNR moves the other way** (1136 → 957, −16%): the real atmosphere
  is more transparent but carries real DISORT path radiance that raises
  the background/noise floor — the parametric model's lower τ was
  partially compensating for its simpler path-radiance term. τ, SNR,
  and range do not move together; quote the metric the decision needs.
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
  aperture benefit shows up entirely as resolution: NIIRS rises from 3.58
  to 5.16 (real D2) as the diffraction-limited PSF shrinks. A genuine "SNR from a
  bigger telescope" trade needs a fixed-focal-length (varying f/#) sweep,
  not a fixed-f/# aperture sweep — worth remembering for the next
  aperture trade study.
- **Detection range is a Beer-Lambert point-source extrapolation**, not a
  full-chain re-evaluation at each range — it assumes the extinction
  coefficient measured at 532 km holds out to ~1700–2100 km, which is
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
