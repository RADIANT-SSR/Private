# Scenario 1.2 — VNIR Pan Imager: GSD vs Aperture vs Altitude

**Persona:** Sarah, systems engineer sizing a sun-synchronous panchromatic
imager.
**Question:** For a fixed 0.5 m panchromatic GSD, what combination of
aperture and orbit altitude meets the SNR spec, where does the design
cross from detector-limited to diffraction-limited, and how much does the
SNR move across the seasons for a 10:30 LTAN orbit?

This scenario is the first consumer of the new
`radiant.core.solar_geometry` model, which turns the orbit's LTAN plus the
target latitude and calendar date into the solar zenith angle the chain
consumes as `geometry.solar_zenith_rad`.

---

## Inputs (vendor / mission formats — non-RADIANT)

| File | Format | Represents |
|------|--------|-----------|
| `inputs/silicon_ccd_qe.csv` | 2-column CSV (`wavelength_nm,QE_pct`) | Front-illuminated Si CCD QE, **digitized from a datasheet plot** (a JPEG can't be read directly — digitization is a manual pre-step, noted in the file header) |
| `inputs/sarah_vnir_design.xlsx` | Excel workbook (`Design`, `Seasons` sheets) | Fixed design parameters, the sun-sync orbit (LTAN, latitude), and the aperture/altitude sweep ranges |

`inputs/create_spreadsheet.py` regenerates both. The QE CSV is read by
`radiant.io.qe_csv.load_qe_csv` and band-averaged over the 450–700 nm pan
band; the workbook values are transcribed into the run script as constants
so the script is self-contained and reproducible.

---

## The trade, precisely

The nadir GSD relation is `GSD = pitch · altitude / focal_length`. To
**hold** GSD at 0.5 m at every altitude, the focal length is derived:

```
focal_length(alt) = pitch · alt / 0.5 m       (pitch fixed at 6.5 µm)
f/#(alt, D)       = focal_length(alt) / D
```

So higher altitude ⇒ longer focal ⇒ **higher f/#** ⇒ less irradiance per
pixel (an extended source scales as `1/(f/#)²`) ⇒ lower SNR. A larger
aperture pulls the f/# back down. **That coupling — trading aperture
against altitude at constant GSD — is the whole scenario.** It is why the
SNR contour tilts: the SNR-spec line runs diagonally, requiring bigger
optics as the orbit rises.

---

## What the run produces

`scripts/run_gsd_trade.py` (run from the repo root):

1. **Solar illumination table** — declination and solar zenith for the
   four seasons at LTAN 10:30, latitude 35°N. Winter (θ_z = 62°) is the
   worst-case illumination; the sizing contour uses it as an SNR floor.
2. **Aperture × altitude SNR contour** (`fig1_snr_aperture_altitude.png`)
   — filled SNR with two overlaid constraint lines: the white SNR-spec
   contour (SNR = 50) and the red dashed diffraction-limit line (where the
   Rayleigh ground spot equals 0.5 m). Left of the red line the optics
   blur past the sample (diffraction-limited); right of the white line the
   design meets spec.
3. **Seasonal SNR bars** (`fig2_seasonal_snr.png`) — SNR at the reference
   design (50 cm, 500 km) across the four seasons, with the spec line.
4. **Minimum aperture per altitude** — the smallest aperture in the swept
   range that meets the SNR spec at each altitude.

---

## Results (worst-case winter unless noted)

| Aperture | 400 km | 500 km | 600 km |
|----------|--------|--------|--------|
| 20 cm | SNR 20.7, Q 2.30, diff-GSD 1.40 m | SNR 15.1, Q 2.88 | SNR 11.4, Q 3.45 |
| 50 cm | SNR 62.5, Q 0.92, diff-GSD 0.56 m | SNR 48.9, Q 1.15, diff-GSD 0.70 m | SNR 39.6, Q 1.38 |
| 80 cm | SNR 102.8, Q 0.57, diff-GSD 0.35 m | SNR 81.4, Q 0.72 | SNR 67.1, Q 0.86 |

- **The 20 cm aperture is diffraction-limited** everywhere (Q > 2.3,
  diffraction ground spot 1.4–2.1 m ≫ the 0.5 m pixel): the pixel is far
  finer than the optics can resolve. Buying that GSD with a small aperture
  is wasted — the optics, not the detector, set the resolution.
- **The 80 cm aperture is detector-limited** (Q < 0.9, diffraction spot
  below 0.5 m): the optics out-resolve the pixel, so the pixel sets the
  GSD. This is the efficient regime for a 0.5 m sample.
- **The 50 cm aperture straddles the crossover** (Q ≈ 0.9–1.4) — near
  critical sampling, the usual sweet spot for a pan imager.
- **Seasonal swing is 43%**: at the 50 cm / 500 km reference design SNR
  runs 86 in summer (θ_z = 23°) down to **48.9 in winter (θ_z = 62°),
  which FAILS the SNR = 50 spec.** Sizing to the annual mean would ship a
  sensor that misses spec every winter — the worst-case-season floor is
  the correct sizing basis.
- **Minimum aperture climbs with altitude**: 45 cm at 400 km → 65 cm at
  600 km to hold the SNR spec at fixed GSD.

---

## Physics notes (house rule: explain the non-obvious)

- **Regime = EXTENDED.** The sunlit surface fills the pixel, so the scene
  radiance *is* the background; EE_box is not applied (Rule 9), and the
  contrast is the surface reflectance against the atmosphere. Point-source
  and sub-pixel machinery is unused here.
- **`Q = λ·(f/#)/pitch`** is the sampling parameter. `Q < 1` undersampled
  (aliasing risk, detector-limited); `Q ≈ 2` critically/oversampled
  (diffraction-limited). It is the frequency-domain twin of the
  diffraction-GSD-vs-sample comparison, and the two agree cell-for-cell.
- **MTF-at-Nyquist = 0 warnings** at the 20 cm end are expected and
  correct: when the detector Nyquist frequency exceeds the optical
  diffraction cutoff, there is genuinely no optical modulation left at
  Nyquist. The framework warns rather than silently returning zero.
- **`local_solar_time_from_ltan` is an identity with a documented
  approximation** — a sun-sync orbit holds ~constant local solar time
  along the daylit track, so LTAN ≈ target LST (target longitude and
  intra-pass nodal drift neglected, both < a few minutes for LEO).

---

## Truth anchors for the solar-geometry model

Verified in `src/radiant/core/tests/test_solar_geometry.py` (12 Level-0
tests) before this scenario consumed the model:

1. Equinox, equator, solar noon → θ_z = 0 (sun overhead).
2. June solstice, Tropic of Cancer (23.44°N), noon → θ_z = 0.
3. Equinox, equator, LST 10:30 → θ_z = |hour angle| = 22.5°.

Declination hits +23.44° at June solstice, −23.44° at December solstice,
≈0 at the equinoxes (Spencer's series, ~0.01°).
