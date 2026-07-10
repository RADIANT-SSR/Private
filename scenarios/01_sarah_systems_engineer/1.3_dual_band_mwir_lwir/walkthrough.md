# Scenario 1.3 Walkthrough: Dual-Band MWIR/LWIR Wildfire Detection Trade

Executed 2026-07-08 (Scenario_Execution_Plan Phase T3, priority 19). First
execution; prerequisite ASTER importer landed in commit f50253a
(`radiant.io.aster_library`).

## The Problem

Sarah must pick a band for a wildfire mission: a 5 m² hotspot at ~600 K
against a 300 K conifer forest, seen from a 10 km airborne platform. The
vendor sent two HgCdTe options — MWIR (3.5–5.0 µm, 80 K) and LWIR
(8–12 µm, 60 K) — as an Excel comparison table, and the forest emissivity
arrives as a JPL/NASA ASTER-library text file.

## Inputs

- **`forest_conifer_aster.txt`** — ASTER library format (metadata header,
  descending-wavelength two-column data, reflectance in percent), read by
  `radiant.io.aster_library.load_aster_spectrum`. ε(λ) = 1 − ρ(λ) for the
  opaque canopy; band averages: **ε = 0.9530 (MWIR) vs 0.9821 (LWIR)** —
  the same canopy differs by ~3% between the bands, which a shared scalar
  emissivity would miss.
- **`sarah_detector_options.xlsx`** — the two detector columns (QE, dark
  current, operating temperature, read noise, well, gain, fire-mode
  integration time) + a shared platform sheet (2.5 cm f/2 optics, 20 µm
  pixels, 10 km altitude, clutter σ = 0.03).

Geometry: GSD = 4.0 m → 16 m² pixel footprint; the 5 m² hotspot fills 31%
of a pixel → **sub-pixel regime** (regime override keeps the in-pixel
background photons and scene clutter in the budget, as in scenario 4.1).

Fire-mode integration times are deliberately short (MWIR 5 µs, LWIR 25 µs):
the first execution at ms-class integrations clipped BOTH bands at 100%
well on the 600 K fire — which is itself the well-known reason fire
products run dedicated short-integration channels.

## Key Results (600 K fire, fill fraction 0.31 — CU-060 corrected)

The 5 m² hotspot fills 31% of the 16 m² pixel footprint; the sub-pixel
regime weights the target by `source.target.fill_fraction` (CU-060 — the
original execution left it at the default 1.0, overstating the fire signal
~3× and pulling the saturation temperatures down).

| Quantity | MWIR | LWIR |
|----------|-----:|-----:|
| Pixel signal [e⁻] | 238,438 | 3,584,903 |
| Contrast (fire − forest) [e⁻] | 233,630 | 1,919,035 |
| Well fill [%] | 6.0 | 29.9 |
| Total noise [e⁻ RMS] | 519.9 | 50,029.1 |
| — of which clutter [e⁻ RMS] | 144.2 | 49,976.1 |
| SNR [--] | 477.3 | 1,556.7 |
| Contrast SNR [--] | 467.7 | 833.3 |
| **SCNR (incl. clutter) [--]** | **449.4** | **38.4** |
| NEDT [mK] (Gap 43 approximation) | 221.8 | 145.1 |

### Spectral contrast (hand Planck, ASTER ε_bg(λ))

Band-integrated ΔL(600 K): 373.6 W/m²/sr (MWIR) vs 382.0 W/m²/sr (LWIR) —
nearly EQUAL in radiance. The trade is decided at the detector, not in
ΔL: the 600 K Planck peak sits at 4.8 µm (inside MWIR), while LWIR sees
the 300 K background ~10× brighter, so LWIR's clutter (3% of a huge
background) is 350× MWIR's. Same ΔL, wildly different signal-to-clutter.

### Fire-temperature sweep (400–1200 K), P_fa = 1e-6

| T_fire [K] | MWIR SCNR | sat? | LWIR SCNR | sat? | P_d MWIR | P_d LWIR |
|-----------:|----------:|:----:|----------:|:----:|:--------:|:--------:|
| 400 | 58.6 | no | 3.2 | no | 1.000 | **0.057** |
| 500 | 224.1 | no | 18.5 | no | 1.000 | 1.000 |
| 600 | 449.4 | no | 38.4 | no | 1.000 | 1.000 |
| 800 | 973.5 | no | 87.3 | no | 1.000 | 1.000 |
| 1000 | 1,529.1 | no | 143.9 | no | 1.000 | 1.000 |
| 1200 | 2,163.8 | **YES** | 204.7 | **YES** | 1.000 | 1.000 |

MWIR detects the 5 m² fire with P_d ≈ 1 at every temperature; **LWIR
misses the coolest fires** — at 400 K its SCNR (3.2) falls below the
4.75σ threshold and P_d collapses to 0.057. That is a real band
discriminator the pixel-filling error had hidden (LWIR SCNR was
overstated ~3×). With the correct 31% fill, saturation moves out to
≈1200 K in **both** bands (from ≈800/900 K before the fix); above it the
radiometry clips and in-band fire temperature cannot be retrieved.

## Physics Discussion

1. **Clutter, not noise, is the LWIR penalty.** LWIR total noise is 96×
   MWIR's, and 99.9% of it is scene clutter — 3% of a background that is
   an order of magnitude brighter in-band. MWIR detection rides on the
   Wien-side contrast steepness with a dim background underneath.
2. **ΔL alone is misleading.** The band-integrated radiance contrasts are
   within 2% of each other at 600 K; a briefing chart that stopped at ΔL
   would call the bands equivalent. The chain comparison (photon
   conversion, per-band QE/dark/read, clutter) is what separates them.
3. **NEDT favors LWIR (145.1 vs 221.8 mK)** — for mapping ambient-
   temperature scenes LWIR remains the right band; NEDT is the wrong
   figure of merit for fire *detection* (both values carry the Gap 43
   single-λ caveat; the reflected-solar component of that caveat is
   absent here because the simple terrestrial path has no TOA solar
   injection into a 600 K thermal target).
4. **Per-band background emissivity matters at the percent level.** The
   ASTER curve gives ε 0.9530/0.9821 (MWIR/LWIR); treating the forest as
   a flat ε = 0.97 would misstate each band's background radiance by
   ~2%, which flows straight into the clutter estimate.
5. **Detection probability now discriminates at the cool end.** P_d =
   Q(4.75 − SCNR) saturates to 1 for SCNR ≳ 10, but the LWIR at a 400 K
   smolder sits *below* threshold (SCNR 3.2 → P_d = 0.057) — LWIR misses
   cool fires from 10 km at this fill. MWIR stays at P_d ≈ 1 everywhere.
   (ROC-grade detection modeling now exists — `performance.roc`, scenario
   6.4 — and could replace the single-threshold model here.)

## Recommendation

**MWIR for detection** — SCNR is 10–12× LWIR's at every fire temperature,
LWIR misses 400 K smolders outright, and both bands now saturate together
at ≈1200 K (the fill-corrected radiometry removed MWIR's earlier
saturation penalty). Pair MWIR with sub-frame integrations if
fire-temperature retrieval above ~1200 K matters, and keep LWIR for
ambient-scene mapping where its NEDT advantage applies.

## Gaps Identified

See `gaps.md`. Highlights: the ASTER importer gap is **closed**
(f50253a); "multi-band comparison workflow" is two Sensor configs + a
table (no new machinery needed — noted, not filed); ΔL and P_d are
script-side (ΔL is a hand-Planck plot; detection probability belongs to
the planned T4 ROC work, so no new registry gap); the Excel-to-YAML
converter gap is mooted by reading the comparison table directly.

## Outputs

- `outputs/dual_band_results.xlsx` — trade table + temperature sweep
- `outputs/fig1_spectral_contrast.png` — ΔL(λ) with both bands shaded
- `outputs/fig2_detection_vs_temperature.png` — SCNR and P_d vs T_fire, saturation marked
- `outputs/fig3_noise_budgets.png` — side-by-side noise budgets (log)

## What Sarah Would Do Next

1. **Size the MWIR fire-mode integration** against the hottest fire she
   must retrieve (not just detect) — the 900 K clip point moves with t_int
2. **Re-run the sweep at night vs day** (solar-reflected MWIR background
   changes the clutter picture for daytime smolder detection)
3. **Feed the vendor QE curves through `load_qe_csv`** (scenario 2.1
   pattern) instead of band-averaged scalars once cutoff shape matters
4. **Push the trade through scenario 4.3's spectral-emissivity path** when
   curve-level background emissivity lands in the chain
