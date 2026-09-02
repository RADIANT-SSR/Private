# Scenario 1.5 — Obscured Aperture & Spider Vanes

**Persona:** Sarah, systems engineer trading a Cassegrain telescope design.
**Question:** How much do the central obscuration (secondary mirror) and
the spider arms that support it degrade image quality versus an ideal
unobstructed aperture, and how does the cost grow with strut width?

This scenario is the first consumer of the new spider-vane pupil masking
(`optics.n_spiders`, `optics.spider_width_m`, `optics.spider_angle_deg`),
which implements RADIANT_Optics.md §3.3.

---

## Inputs (vendor / design format — non-RADIANT)

| File | Format | Represents |
|------|--------|-----------|
| `inputs/sarah_cassegrain.xlsx` | Excel workbook (`Telescope` sheet) | Cassegrain pupil geometry (primary, obscuration, spider arms) and the VNIR detector/readout configuration |

`inputs/create_spreadsheet.py` regenerates it; values are transcribed into
the run script as constants for a self-contained, reproducible run.

---

## The physics: one pupil, two paths, two effects

RADIANT builds **both** the PSF (Fourier transform of the complex pupil)
and the optical MTF (pupil autocorrelation) from the *same* amplitude mask.
So adding opaque spider struts to that mask degrades **both** spatial paths
at once (the Rule 4 dual-path consistency invariant). The struts produce
two coupled effects:

1. **Spatial** — energy scatters out of the PSF core into the familiar
   four-point diffraction spikes, lowering encircled energy (EE_box), the
   edge response (RER), and the peak.
2. **Radiometric** — the struts subtract from the clear collecting area
   (`A_clear`), so fewer photons are collected and SNR falls.

Crucially, the **Strehl ratio does not move** — it is a wavefront-error
metric (degraded-PSF peak over a diffraction-limited *reference* peak), and
the reference PSF carries the same aperture geometry (obscuration and
vanes). The aperture effects are common-mode and cancel. The vane cost is
correctly attributed to EE/RER/SNR, not Strehl.

---

## Results (50 cm f/12 Cassegrain, VNIR pan, 500 km)

### Aperture comparison

*Numbers refreshed 2026-09-01 from the unmodified runner (previous vintage
2026-08-30). Sole mover: **CU-336**, the grid-convention correction to the same
gas-band fit: the CU-335 floors were fitted by subtracting a non-water reference
measured on a uniform-λ grid from a ladder optical depth measured on MODTRAN's
wavenumber grid, so they came out high. Corrected, 0.45–0.70 µm reads 0.1375 and
0.70–1.30 µm reads 0.0402, and this VNIR scene becomes slightly more transmissive
again: **SNR rises +1.5 % on every row** (unobstructed 74.0 → 75.1). Every
spatial metric — EE_3×3, RER, MTF@Nyquist, Strehl — is bit-identical, because the
change is purely radiometric, and the comparison this scenario exists to make is
unchanged because every row moved together.*

*Prior vintage, 2026-08-30. **CU-335** put those two floors on the table for the
first time (0.1597 / 0.0517, against a pre-CU-253 Rayleigh ~8× too large that had
clamped them to zero): SNR fell −14.8 % on every row, unobstructed 86.7 → 74.0.
The 2026-08-02 refresh before it moved SNR −1.5 % per row under CU-253/CU-267.*

| Configuration | SNR | EE_3×3 | RER | MTF@Nyq | Strehl |
|---------------|-----|--------|-----|---------|--------|

| Configuration | SNR | EE_3×3 | RER | MTF@Nyq | Strehl |
|---------------|-----|--------|-----|---------|--------|
| Unobstructed | 75.1 | 0.864 | 0.582 | 0.228 | 1.000 |
| Obscured only (ε=0.30) | 71.5 | 0.763 | 0.517 | 0.207 | 1.000 |
| Obscured + 4× 3 cm spiders | 66.8 | 0.657 | 0.485 | 0.221 | 1.000 |

- Going from an ideal unobstructed aperture to the full Cassegrain costs
  **11.1 % of SNR and 24 % of the 3×3 encircled energy.** The obscuration
  alone accounts for most of the SNR loss (less area); the spiders add the
  diffraction-spike EE/RER penalty on top.
- **Strehl is 1.000 throughout** — confirming it isolates WFE and is blind
  to aperture geometry, exactly as designed. A designer who judged this
  telescope by Strehl alone would miss the entire obscuration/vane cost.

### Spider-width sweep (ε=0.30, 4 arms)

| Width | SNR | EE_3×3 | RER |
|-------|-----|--------|-----|
| 0 cm | 71.5 | 0.763 | 0.517 |
| 1 cm | 69.9 | 0.736 | 0.509 |
| 2 cm | 68.4 | 0.683 | 0.493 |
| 3 cm | 66.8 | 0.657 | 0.485 |
| 4 cm | 65.2 | 0.632 | 0.477 |
| 5 cm | 63.5 | 0.607 | 0.469 |

EE_3×3 and RER fall monotonically with strut width — each centimetre of
strut scatters more core energy into the spikes and shaves more collecting
area. Sarah's **3 cm baseline costs ~14 % of the encircled energy** versus
strut-free supports, quantifying the price of a robust secondary mount.

---

## Figures

- `fig1_psf_diffraction_spikes.png` — the effective PSF core (log scale)
  for the three apertures. The unobstructed Airy pattern, the obscured
  pattern (brighter first ring), and the four-point spider spikes are
  directly visible.
- `fig2_degradation_vs_width.png` — EE_3×3, RER, and SNR (each normalised
  to the strut-free value) vs spider width.

---

## Physics / modeling notes (house rule: explain the non-obvious)

- **Regime = EXTENDED.** The sunlit surface fills the pixel; the spatial
  metrics (EE, RER, MTF) are the point of interest here, not the regime.
- **MTF@Nyquist is non-monotonic** across the three apertures (0.228 →
  0.207 → 0.221). Obscuration and thin struts redistribute the MTF: the
  obscuration lowers mid frequencies but the thin high-contrast strut
  slice can nudge the on-axis Nyquist value back up. The robust,
  monotonic degradation signals are EE and RER, which is why the sweep
  tracks those.
- **The strut width is converted m → pupil-fraction** at the stage
  boundary (Rule 2); internally the mask works in normalised pupil
  coordinates.

---

## Truth anchors for the spider-vane model

Verified in `src/radiant/optics/tests/test_spider_vanes.py` (10 Level-0
tests) before this scenario consumed the model:

1. **No-vane byte-identical guard:** `vanes=None` reproduces the historical
   pupil exactly (confirmed against 496 optics + 10 golden tests, all
   unchanged).
2. **Clear-area anchor:** D=1 m, 4 arms × 0.01 m → A = π/4 − 4·0.01·0.5 =
   0.7654 m² (hand calc of the §3.3 formula).
3. **Geometry:** a 4-strut spider at 0° blanks the ±x/±y axes; struts
   lower the normalised PSF peak.
