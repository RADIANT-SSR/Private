# Scenario 1.1 — MWIR Maritime Surveillance Trade Study

**Persona:** Sarah, systems engineer on a proposal team.
**Question:** For a 500 km SSO MWIR ship-detection sensor (15–45 cm
aperture, f/2.5, InSb 640×512, 15 µm pixel), how do SNR, NEDT, NIIRS, and
detection range vary with aperture — and how much does using a real
atmospheric-transmittance dataset (vs. RADIANT's own parametric model)
change the answer?

**Status: pipeline demonstration, not a validated trade study.** The
atmosphere data is *synthetic* (HITRAN-line-by-line-based, not a real
MODTRAN run — see below). Treat the numbers as illustrating the pipeline
and the *shape* of the MODTRAN-vs-parametric comparison, not as design
guidance, until real MODTRAN data replaces run `D2`.

---

## Inputs (vendor-style — non-RADIANT)

| File | Represents |
|------|-----------|
| `inputs/insb_qe_representative.csv` | Representative InSb QE curve (cutoff ~5.4 µm, peak ~0.84 near 3.5 µm) — Sarah's vendor PDF has a QE *graph*, not data points; this is a typical-InSb digitization, not a specific vendor's curve (the catalog's stated gap — no PDF exists to digitize from). Band-averaged to a scalar QE for the chain (`detector.qe_value`), matching scenario 1.2's approach. |
| `modtran/synthetic/D2.synthetic.tp7` | The MODTRAN tape7 Sarah's colleague gave her — **synthetic**, not real MODTRAN (see next section). `midlat_summer` profile, maritime aerosol (IHAZE=3). |
| `data/emissivity/steel.csv` | Ship-hull emissivity (RADIANT's library "steel" curve; catalog says "0.7–0.85 depending on paint, partially rusted" — no rust-specific curve exists, see gaps.md). |
| `data/emissivity/water_calm.csv` | Ocean background emissivity (catalog wants wind-state/sea-state dependence — not modeled, see gaps.md). |

---

## Atmosphere data: what's real, what isn't

`D2` comes from `scripts/generate_synthetic_tape7.py` — **not** a real
MODTRAN run. Per `modtran/synthetic/README.md`:
- `TOT TRANS` (what this scenario consumes) is genuine independent
  physics: real HITRAN line-by-line molecular transmittance on an
  independently-built layered atmosphere.
- The path-radiance/scattering columns are a simplified approximation,
  not multiple-scattering DISORT — not relevant here since the ship is a
  reflective/thermal point-like target, not a diffuse-sky calculation.
- **Do not** use this scenario's numbers to validate RADIANT's atmosphere
  physics — that is explicitly what `modtran/synthetic/README.md`
  forbids. This scenario exists to prove the pipeline (`Tape7Reader` →
  `atmosphere.model="tabulated"` → chain) works end-to-end.

---

## How RADIANT solves this

1. **Convert the tape7.** `Tape7Reader(D2_path).to_radiant_units()` gives
   ascending-wavelength transmittance and path radiance; written to
   temporary CSVs for `atmosphere.model="tabulated"`.
2. **Two atmosphere configs, same geometry/target/detector**:
   `SimpleAtmosphere` (maritime aerosol, `midlat_summer`) vs. the
   `D2`-tabulated data, so the comparison isolates the atmosphere term.
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

## Results (aperture = 30 cm, mid-sweep)

| Metric | SimpleAtmosphere | MODTRAN-D2 (synthetic) |
|--------|-------------------|--------------------------|
| SNR [-] | 1135.6 | 1158.6 |
| NEDT [K] | 0.0208 | 0.0205 |
| NIIRS [-] | 4.67 | 4.68 |
| Detection range @ SNR=5 [km] | 1689.8 | 2841.2 |
| In-band transmittance [-] | 0.239 | 0.617 |

- **The atmosphere source matters a lot for absolute transmittance**
  (0.24 vs. 0.62 — 2.6×) but only mildly for SNR at this operating point,
  because the system is already comfortably above the SNR=5 threshold at
  532 km; the detection-range extrapolation amplifies the transmittance
  difference into a much larger range delta (1690 → 2843 km).
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
  aperture benefit shows up entirely as resolution: NIIRS rises from 3.67
  to 5.26 as the diffraction-limited PSF shrinks. A genuine "SNR from a
  bigger telescope" trade needs a fixed-focal-length (varying f/#) sweep,
  not a fixed-f/# aperture sweep — worth remembering for the next
  aperture trade study.
- **Detection range is a Beer-Lambert point-source extrapolation**, not a
  full-chain re-evaluation at each range — it assumes the extinction
  coefficient measured at 532 km holds out to ~1700–2800 km, which is
  unrealistic (curvature, refraction, and the actual atmosphere profile
  all change over that distance). Treat the range numbers as illustrating
  the *relative* SimpleAtmosphere-vs-MODTRAN sensitivity, not an
  operational range.
- **Regime = SUB_PIXEL, not POINT_SOURCE.** Matrix §7's own consistency
  check caught this — a useful sanity check that the target-vs-PSF size
  assumption isn't silently wrong.

---

## Gaps Identified

See `gaps.md` for the full list; summary: wind-state ocean emissivity,
rust-specific hull emissivity, and a real (non-synthetic) MODTRAN dataset
are the three open items. The MODTRAN tape7 *parsing* gap the original
catalog entry flagged is closed (CU-066 + this scenario).
