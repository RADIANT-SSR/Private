# Scenario 5.5 — Stray-Light / Veiling-Glare Impact on Contrast & NIIRS

**Persona:** Tom, optical designer.
**Question:** His FRED stray-light analysis gives a 3 % veiling-glare index
and 2.5 W/m² out-of-field stray irradiance (plus a 2-D stray PSF RADIANT
can't ingest). What is the contrast, SNR, and NIIRS impact, and how much
veiling glare can the design tolerate?

Scene: daytime VNIR pan (0.5–0.8 µm), rooftop target (ρ = 0.30) vs
vegetation (ρ = 0.15), airborne 7 km, solar zenith 30°, D 15 cm f/6.

---

## Inputs (non-RADIANT)

| File | Format | Represents |
|------|--------|-----------|
| `inputs/tom_straylight.xlsx` | Excel workbook | Two-reflectance scene, the FRED stray-light numbers (VGI 3 %, out-of-field 2.5 W/m², 2-D PSF), and the VNIR sensor config |

`inputs/create_spreadsheet.py` regenerates it; values are transcribed into
the run script.

---

## Method + an important caveat

RADIANT has two usable scalar stray-light modes (a 2-D PSF / PST importer
does not exist — gaps.md). **One of them is currently broken:**

- **`absolute_irradiance` (correct).** Tom's 2.5 W/m² injects a flat stray
  spectral density → a real electron pedestal → shot noise → SNR/NIIRS loss.
- **`veiling_glare` (BROKEN — CU-062).** It scales the in-FOV irradiance by
  the *pixel IFOV solid angle* instead of the *f-cone solid angle*, so it
  under-reports stray by ~(D/pitch)²·π/4 ≈ 10⁷–10⁸. At VGI = 10 % it produces
  stray_e = 1.3×10⁻³ e- (should be ~9×10⁴) and leaves SNR unchanged — the
  mode does nothing.

So the scenario **demonstrates the bug**, then routes Tom's 3 % VGI through
the correct physics using the identity `stray_e = VGI · S_scene` (a uniform
scene scatters VGI of its own per-pixel flux onto each pixel), expressed as
an equivalent absolute irradiance so the chain — including its GIQE/NIIRS —
sees the right pedestal.

**Stray light is a noise pedestal, not a signal.** It is common to target
and background, so it cancels in the target−background contrast *signal*;
contrast SNR degrades purely through the added shot noise. RADIANT does not
model the veiling-glare MTF / contrast-modulation reduction (gaps.md).

---

## Results

| Case | Stray e- | SNR | Contrast SNR | NIIRS | ΔNIIRS |
|------|----------|-----|--------------|-------|--------|
| Clean | 0 | 546.7 | 126.3 | 11.070 | — |
| Native `veiling_glare` 10 % | 1.3×10⁻³ | 546.7 | — | 11.070 | 0.000 (**inert, bug**) |
| Veiling glare 3 % (corrected) | 2.68×10⁴ | 523.9 | 121.1 | 11.042 | −0.029 |
| Out-of-field 2.5 W/m² | 5.52×10⁶ | 124.3 | 28.7 | 10.068 | **−1.003** |

- **3 % veiling glare is a mild penalty** — ~3 % of the scene added as a
  stray pedestal, costing ~4 % of the contrast SNR and 0.03 NIIRS.
- **The 2.5 W/m² out-of-field stray is the real threat** — 5.5×10⁶ stray e-,
  several × the signal, cutting SNR 4.4× and costing a **full NIIRS level**.
- **Tolerance:** VGI can rise to ~10 % before ΔNIIRS exceeds 0.2 or the
  contrast SNR drops below 50 — Tom's 3 % sits comfortably inside budget.
  The out-of-field stray, not the veiling glare, is what he must control.

Figures: `fig1_vgi_tolerance.png` (contrast SNR and ΔNIIRS vs VGI, with the
tolerance band and Tom's 3 % marked); `fig2_noise_budget.png` (noise terms
clean vs +2.5 W/m² — stray shot noise dwarfs read+dark).

---

## Physics / modeling notes (house rule)

- **Every number carries units**; the noise model (shot + dark + read +
  stray shot) and the pedestal-cancels-in-contrast behaviour are stated
  inline.
- **The VGI→absolute-irradiance identity is exact** for a uniform extended
  scene: veiling glare re-images a fraction VGI of the total scene flux
  uniformly, which per pixel equals VGI × the mean per-pixel signal.
- **What RADIANT does NOT model** (both filed): the veiling-glare MTF /
  low-frequency contrast-modulation reduction, and 2-D stray-light PSF / PST
  ingestion. The scalar-pedestal model captures the radiometric (noise) hit
  but not the spatial (MTF) hit.

---

## Truth anchors

- **`absolute_irradiance` linearity**: stray_e scales linearly with the
  injected irradiance (calibration 2.209×10⁶ e- per W/m²); 2.5 W/m² → 5.52×10⁶
  e-, matching 2.5 × the unit-irradiance run.
- **VGI-mode inertness reproduces the solid-angle ratio**: native stray_e at
  VGI 10 % is ~(pitch/D)²·(4/π) below 10 % of the signal — the exact factor
  in CU-062.
- **Contrast unchanged by a common pedestal**: the target−background signal
  difference is identical with and without stray light; only the combined
  noise grows — the defining property of a uniform veiling-glare pedestal.
