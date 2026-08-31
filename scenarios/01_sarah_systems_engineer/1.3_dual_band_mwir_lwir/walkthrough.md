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

*Numbers refreshed 2026-08-30 from the unmodified runner. **CU-324 item 2** now
places the 9.6 µm ozone share of the gas floor on the 25 km ozone layer instead
of the 4 km well-mixed profile, so the LWIR column's own thermal emission falls:
pixel signal 2 996 449 → 2 962 748 e⁻ (−1.1 %), clutter 53 377 → 52 366 e⁻ RMS,
SNR 1 363.6 → 1 357.8, NEDT 164.7 → 165.4 mK. The **verdict improves slightly**
in LWIR's favour and for the reason the band trade is about: a smaller background
carries proportionally less 3 % clutter, so LWIR SCNR rises 22.8 → 23.2 at 600 K
and 126.4 → 128.8 at 1200 K while the fire contrast (1 217 206 e⁻) does not move
at all. **Every MWIR figure was bit-identical on the branch** — the split touches
9.4–9.9 µm and nothing else — and the 400 K LWIR miss is unchanged at SCNR 1.1,
P_d 0.000.

*Composed with CU-335 on the merged tree, 2026-08-31: re-run on `main` after both
siblings landed, the MWIR column is no longer bit-identical — it moves in the fifth
significant figure (pixel signal 228 481 → 228 465 e⁻, contrast 220 950 → 220 935 e⁻,
SCNR at 1200 K 2 003.9 → 2 003.8, i.e. ~7 × 10⁻⁵ relative). CU-324 item 2 and CU-335
were each measured against a tree that did not contain the other; CU-335's λ⁻⁴ tail
reaches the 3.5–5.0 µm floors, which is the MWIR path the branch-side measurement
could not see. No SCNR, P_d, saturation temperature or verdict in this document
changes.*

Prior vintage, refreshed 2026-08-29. Two movers, both
small here, both landed 2026-08-29. **CU-330** split the flat 8–10 µm gas region
at the 9.6 µm ozone band, giving the LWIR column real in-band opacity: pixel
signal 3 011 064 → 2 996 449 e⁻ (−0.5 %), clutter 53 631 → 53 377 e⁻ RMS, SNR
1 367.0 → 1 363.6, NEDT 164.5 → 164.7 mK. **Every MWIR figure in this table is
bit-identical**, which is the split's signature — it touches 8–10 µm and nothing
else — and no verdict moves. The earlier mover, from the pre-CU-324 vintage of
2026-08-02: **CU-324** made
`E_sky_thermal`'s flux-diffusivity exponent the geometric `sec 48.2° = 1.50030`
instead of the CU-155 fitted `D = 1.1`, lifting the sky the ε < 1 forest floor
reflects. Everything moves in the fourth significant figure — pixel signal LWIR
3 009 637 → 3 011 064 e⁻, MWIR 228 451 → 228 481 e⁻; clutter LWIR 53 569 →
53 631 e⁻ RMS — and because the background and its 3 % clutter rise together,
the LWIR SCNR is unchanged at 22.8 while the MWIR falls a tick, 408.2 → 408.0.
The fire contrast barely moves (220 943 → 220 950 e⁻ MWIR; 1 223 998 →
1 223 350 e⁻ LWIR): the target is a hotspot, not the sky. **No verdict in this
document changes.**

Prior vintage, for the trend: the 2026-08-02 refresh was dominated by CU-321 —
the down-looking path-thermal term emitted at a height-resolved `T_eff(λ)`
rather than the column's near-surface temperature, which took pixel signal LWIR
3 139 542 → 3 009 637 e⁻ and LWIR SCNR 21.3 → 22.8.*

| Quantity | MWIR | LWIR |
|----------|-----:|-----:|
| Pixel signal [e⁻] | 228,465 | 2,962,748 |
| Contrast (fire − forest) [e⁻] | 220,935 | 1,217,206 |
| Well fill [%] | 5.7 | 24.7 |
| Total noise [e⁻ RMS] | 541.6 | 52,411.7 |
| — of which clutter [e⁻ RMS] | 225.9 | 52,366.3 |
| SNR [--] | 464.2 | 1,357.8 |
| Contrast SNR [--] | 448.9 | 557.8 |
| **SCNR (incl. clutter) [--]** | **408.0** | **23.2** |
| NEDT [mK] (Gap 43 approximation) | 230.0 | 165.4 |

### Spectral contrast (hand Planck, ASTER ε_bg(λ))

Band-integrated ΔL(600 K): 373.6 W/m²/sr (MWIR) vs 382.0 W/m²/sr (LWIR) —
nearly EQUAL in radiance (these are hand-Planck values and did not move).
The trade is decided at the detector, not in ΔL: the 600 K Planck peak sits
at 4.8 µm (inside MWIR), while LWIR sees the 300 K background ~10× brighter,
so LWIR's clutter (3% of a huge background) is ~217× MWIR's. Same ΔL, wildly
different signal-to-clutter.

### Fire-temperature sweep (400–1200 K), P_fa = 1e-6

| T_fire [K] | MWIR SCNR | sat? | LWIR SCNR | sat? | P_d MWIR | P_d LWIR |
|-----------:|----------:|:----:|----------:|:----:|:--------:|:--------:|
| 400 | 42.7 | no | 1.1 | no | 1.000 | **0.000** |
| 500 | 188.0 | no | 10.7 | no | 1.000 | 1.000 |
| 600 | 408.0 | no | 23.2 | no | 1.000 | 1.000 |
| 800 | 924.2 | no | 54.2 | no | 1.000 | 1.000 |
| 1000 | 1,464.3 | no | 90.1 | no | 1.000 | 1.000 |
| 1200 | 2,003.8 | **YES** | 128.8 | no | 1.000 | 1.000 |

MWIR detects the 5 m² fire with P_d ≈ 1 at every temperature; **LWIR
misses the coolest fires** — at 400 K its SCNR is 1.0, far below the
4.75σ threshold, and P_d collapses to 0.000. The band discriminator is
sharper than it was before CU-224: raising the LWIR background raised its
clutter with it, so the coolest-fire LWIR SCNR fell 2.8 → 1.0, and CU-321's
partial give-back only takes it to 1.1 — still far below the 4.75σ threshold,
P_d still 0.000. The verdict is unchanged; the margin is not. MWIR still
saturates first — at ≈1200 K, where the fire signal reaches 98 % of the
4,000,000 e⁻ well even in fire mode; LWIR does not saturate anywhere in the
swept range (25 % well fill at 600 K). Above the
MWIR saturation point the radiometry clips and in-band fire temperature
cannot be retrieved.

## Physics Discussion

1. **Clutter, not noise, is the LWIR penalty.** LWIR total noise is ~102×
   MWIR's, and 99.9% of it is scene clutter — 3% of a background that is
   an order of magnitude brighter in-band. MWIR detection rides on the
   Wien-side contrast steepness with a dim background underneath.
2. **ΔL alone is misleading.** The band-integrated radiance contrasts are
   within 2% of each other at 600 K; a briefing chart that stopped at ΔL
   would call the bands equivalent. The chain comparison (photon
   conversion, per-band QE/dark/read, clutter) is what separates them.
3. **NEDT favors LWIR (161.8 vs 230.0 mK)** — for mapping ambient-
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
   smolder sits *below* threshold (SCNR 1.0 → P_d = 0.000) — LWIR misses
   cool fires from 10 km at this fill. MWIR stays at P_d ≈ 1 everywhere.
   (ROC-grade detection modeling now exists — `performance.roc`, scenario
   6.4 — and could replace the single-threshold model here.)

## Recommendation

**MWIR for detection** — SCNR is ≥17× LWIR's at every fire temperature (up to ~38× at the cool end),
LWIR misses 400 K smolders outright, and MWIR saturates first (from
≈1200 K, where its fire-mode signal reaches ~98% of the 4 Me⁻ well) while
LWIR stays unsaturated across the swept range. Pair MWIR with sub-frame
integrations if fire-temperature retrieval above ~1200 K matters, and keep
LWIR for ambient-scene mapping where its NEDT advantage applies.

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
   must retrieve (not just detect) — the ≈1200 K clip point moves with t_int
2. **Re-run the sweep at night vs day** (solar-reflected MWIR background
   changes the clutter picture for daytime smolder detection)
3. **Feed the vendor QE curves through `load_qe_csv`** (scenario 2.1
   pattern) instead of band-averaged scalars once cutoff shape matters
4. **Push the trade through scenario 4.3's spectral-emissivity path** when
   curve-level background emissivity lands in the chain
