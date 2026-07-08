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

## Key Results (600 K fire)

| Quantity | MWIR | LWIR |
|----------|-----:|-----:|
| Pixel signal [e⁻] | 752,423 | 7,806,779 |
| Contrast (fire − forest) [e⁻] | 747,615 | 6,140,911 |
| Well fill [%] | 18.8 | 65.1 |
| Total noise [e⁻ RMS] | 885.6 | 50,071.3 |
| — of which clutter [e⁻ RMS] | 144.2 | 49,976.1 |
| SNR [--] | 861.1 | 2,529.5 |
| Contrast SNR [--] | 855.6 | 1,989.7 |
| **SCNR (incl. clutter) [--]** | **844.2** | **122.6** |
| NEDT [mK] (Gap 43 approximation) | 123.1 | 89.9 |

### Spectral contrast (hand Planck, ASTER ε_bg(λ))

Band-integrated ΔL(600 K): 373.6 W/m²/sr (MWIR) vs 382.0 W/m²/sr (LWIR) —
nearly EQUAL in radiance. The trade is decided at the detector, not in
ΔL: the 600 K Planck peak sits at 4.8 µm (inside MWIR), while LWIR sees
the 300 K background ~10× brighter, so LWIR's clutter (3% of a huge
background) is 350× MWIR's. Same ΔL, wildly different signal-to-clutter.

### Fire-temperature sweep (400–1200 K), P_fa = 1e-6

| T_fire [K] | MWIR SCNR | sat? | LWIR SCNR | sat? | P_d (both) |
|-----------:|----------:|:----:|----------:|:----:|:----------:|
| 400 | 149.3 | no | 10.1 | no | 1.000 |
| 600 | 844.2 | no | 122.6 | no | 1.000 |
| 800 | 1,763.3 | no | 279.2 | **YES** | 1.000 |
| 900 | 2,549.9 | **YES** | 367.4 | YES | 1.000 |
| 1200 | 6,924.3 | YES | 655.0 | YES | 1.000 |

Both bands detect a 5 m² fire with P_d ≈ 1 at every temperature — from
10 km, detection is not the discriminator. **Dynamic range is**: with
these fire-mode integrations the LWIR saturates from ≈800 K and the MWIR
from ≈900 K; above saturation the radiometry clips and in-band fire
temperature cannot be retrieved. LWIR is closer to its well everywhere
(65% at 600 K) because the 300 K background alone nearly fills it.

## Physics Discussion

1. **Clutter, not noise, is the LWIR penalty.** LWIR total noise is 56×
   MWIR's, and 99.8% of it is scene clutter — 3% of a background that is
   an order of magnitude brighter in-band. MWIR detection rides on the
   Wien-side contrast steepness with a dim background underneath.
2. **ΔL alone is misleading.** The band-integrated radiance contrasts are
   within 2% of each other at 600 K; a briefing chart that stopped at ΔL
   would call the bands equivalent. The chain comparison (photon
   conversion, per-band QE/dark/read, clutter) is what separates them.
3. **NEDT favors LWIR (89.9 vs 123.1 mK)** — for mapping ambient-
   temperature scenes LWIR remains the right band; NEDT is the wrong
   figure of merit for fire *detection* (both values carry the Gap 43
   single-λ caveat; the reflected-solar component of that caveat is
   absent here because the simple terrestrial path has no TOA solar
   injection into a 600 K thermal target).
4. **Per-band background emissivity matters at the percent level.** The
   ASTER curve gives ε 0.9530/0.9821 (MWIR/LWIR); treating the forest as
   a flat ε = 0.97 would misstate each band's background radiance by
   ~2%, which flows straight into the clutter estimate.
5. **Detection probability is a threshold formality here.** P_d =
   Q(4.75 − SCNR) saturates to 1 for SCNR ≳ 10; the LWIR at a 400 K
   smolder (SCNR 10.1) is the only cell anywhere near the transition.
   ROC-grade detection modeling is planned T4 work (scenarios 4.2/6.4).

## Recommendation

**MWIR for detection** — SCNR is 7–15× LWIR's at every fire temperature,
with 3× more headroom before saturation. Pair it with LWIR (or sub-frame
MWIR integrations) if fire-temperature retrieval above ~900 K matters,
and keep LWIR for ambient-scene mapping where its NEDT advantage applies.

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
