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

## Method + a bug this scenario found and fixed

RADIANT has two usable scalar stray-light modes (a 2-D PSF / PST importer
does not exist — gaps.md):

- **`absolute_irradiance`.** Tom's 2.5 W/m² injects a flat stray spectral
  density → a real electron pedestal → shot noise → SNR/NIIRS loss.
- **`veiling_glare`.** Tom's 3 % VGI. This scenario originally found the mode
  **inert (CU-062):** it scaled the in-FOV irradiance by the *pixel IFOV
  solid angle* instead of the *f-cone solid angle*, under-reporting stray by
  ~(D/pitch)²·π/4 ≈ 10⁷–10⁸ so any VGI produced ~zero stray. **The bug is now
  fixed** (commit 8cb0448): the mode uses `Ω_cone = A_collect/focal²`, so
  `stray_e = vgf·signal_e` for a uniform extended scene. Section 2 of the
  script verifies this against the identity before using the mode directly.

**Stray light is a noise pedestal, not a signal.** It is common to target
and background, so it cancels in the target−background contrast *signal*;
contrast SNR degrades purely through the added shot noise. RADIANT does not
model the veiling-glare MTF / contrast-modulation reduction (gaps.md, Gap 60).

---

## Results

| Case | Stray e- | SNR | Contrast SNR | NIIRS | ΔNIIRS |
|------|----------|-----|--------------|-------|--------|
| Clean | 0 | 546.7 | 217.7 | 11.052 | — |
| Veiling glare 3 % (native mode) | 2.86×10⁴ | 522.5 | 209.0 | 11.022 | −0.031 |
| Out-of-field 2.5 W/m² | 5.52×10⁶ | 124.3 | 49.5 | 10.049 | **−1.003** |

*Numbers refreshed 2026-08-30 from the unmodified runner (previous vintage
2026-08-02). Sole mover: **CU-335** — the calibrated gas table's 0.45–0.70 and
0.70–1.30 µm well-mixed floors were re-fitted against the post-CU-253 Rayleigh
(0.0000 → 0.1597 / 0.0517). This VNIR scene loses ~14 % of both its target and
its background signal (9.530e+05 / 5.207e+05 e⁻ where it read 1.108e+06 /
6.126e+05), and the 3 % veiling-glare pedestal shrinks with the signal it is
defined against (3.32×10⁴ → 2.86×10⁴ stray e⁻). **Extended-scene SNR and NIIRS
are bit-identical**, because the target pixel is well-saturated (FWC
3.0×10⁵ e⁻) and SNR is pinned at √FWC; **contrast SNR rises 213.9 → 217.7
(+1.8 %)**, because the target and background pedestals fall together and the
difference signal loses proportionally less than the shot noise does. Tom's
verdict is unchanged: 3 % veiling glare stays inside the ΔNIIRS ≤ 0.2 /
contrast-SNR ≥ 50 budget, and the 2.5 W/m² out-of-field case still costs a full
NIIRS level.*

*Prior vintage, for the trend: the 2026-08-02 refresh was dominated by CU-253 —
the Rayleigh optical depth was 8× too
large, and correcting it shrank the sky-scattered/path pedestal that is common
to the rooftop (ρ = 0.30) and vegetation (ρ = 0.15) pixels. The
background/target signal ratio therefore fell from 0.73 toward the pure-albedo
0.55, lifting contrast SNR 131.6 → 213.9 (+63 %). Extended-scene SNR and NIIRS
are unchanged because the target pixel is well-saturated (FWC 3.0×10⁵ e⁻), so
SNR is pinned at the well-limited √FWC value regardless of collected signal.*

Section 2 verifies the fixed `veiling_glare` mode: at VGI 10 % it yields
`stray_e = 1.108×10⁵ e- = 0.10 × signal` — exactly the identity.

- **3 % veiling glare is a mild penalty** — ~3 % of the signal added as a
  stray pedestal, costing ~5 % of the contrast SNR and 0.035 NIIRS.
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
- **The `stray_e = vgf·signal_e` identity is exact** for a uniform extended
  scene: veiling glare re-images a fraction VGI of the in-FOV scene flux
  uniformly onto each pixel, collected through the same etendue as the
  signal. The fixed `veiling_glare` mode reproduces this to the digit.
- **What RADIANT does NOT model** (both filed): the veiling-glare MTF /
  low-frequency contrast-modulation reduction, and 2-D stray-light PSF / PST
  ingestion. The scalar-pedestal model captures the radiometric (noise) hit
  but not the spatial (MTF) hit.

---

## Truth anchors

- **`absolute_irradiance` linearity**: stray_e scales linearly with the
  injected irradiance (calibration 2.209×10⁶ e- per W/m²); 2.5 W/m² → 5.52×10⁶
  e-, matching 2.5 × the unit-irradiance run.
- **Fixed `veiling_glare` mode reproduces the identity**: native stray_e at
  VGI 10 % equals 0.10 × signal to the digit (1.108×10⁵ e-). The pre-fix bug
  under-counted by (pitch/D)²·(4/π) — the exact solid-angle ratio (CU-062,
  resolved 8cb0448).
- **Contrast unchanged by a common pedestal**: the target−background signal
  difference is identical with and without stray light; only the combined
  noise grows — the defining property of a uniform veiling-glare pedestal.
