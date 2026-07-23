# Scenario 4.3 Walkthrough: Camouflage Effectiveness Analysis

Executed 2026-07-08 (Scenario_Execution_Plan Phase T3, priority 20); uses the
ASTER importer (commit f50253a) and the S8 tabulated-source spec form for
spectral emissivity. Refreshed 2026-07-22 against the current engine (nadir
numbers, CU-176) and re-run after the CU-182 geometry-convention fix, which
restored the off-nadir detection-range sweep (edge-limited at 17.1 km).

## The Problem

Lisa evaluates thermal camouflage against an airborne LWIR FLIR (8–12 µm,
3 km). A hot vehicle (engine deck ~380 K) sits in scrub (305 K, ε 0.96).
Three candidate nets drape the vehicle and re-emit at their own
near-ambient temperature (310 K); their emissivity spectra arrive in
three different vendor forms:

- **Bare vehicle**: oxidized steel, ε from an **ASTER-library text file**
  (`load_aster_spectrum`, ε = 1 − ρ ≈ 0.80).
- **Net A**: broadband low-ε metalized weave (mean ~0.60), a dense
  measured ε(λ) CSV.
- **Net B**: spectrally shaped — low in 8–10 µm, high in 10–12 µm.
- **Net C**: emissivity at only THREE wavelengths (a vendor quote sheet)
  — sparse, needs interpolation.

## How Spectral Emissivity Enters the Chain

RADIANT's target surface takes only a **scalar** emissivity (the catalog's
"spectral emissivity input" gap — filed as registry **Gap 47**). The S8
spec form accepts a tabulated spectral *radiance* instead
(`source.target.user_radiance_path` → `T6TabulatedAtSource`, "the user owns
the physics"). The script therefore composes each option at the file
boundary:

    L_t(λ) = ε(λ) · B(λ, T_surface)      [W/m²/sr/µm]

writes the derived radiance CSV, and hands the chain the S8 path — exactly
the physics Lisa has (measured ε(λ) plus an assumed surface temperature).

**Detection geometry.** A draped net at 3 km fills the pixel → extended
regime (clean L → signal, no sub-pixel EE_box penalty). Detection is the
option-covered pixel MINUS a **scrub-background pixel** (adjacent-pixel
contrast — the resolved-target construction from scenario 4.1). Because the
extended regime carries no separate scene-background photon term
(Decision #13), the differential is formed explicitly from two extended
runs: `SCNR = |S_option − S_scrub| / noise_scrub`.

## Key Results (nadir, full 8–12 µm)

| Option | Contrast [e⁻] | SCNR | Well fill [%] | Signature reduction |
|--------|--------------:|-----:|--------------:|--------------------:|
| Bare vehicle | +1,860,247 | 1,450.4 | 28.8 | — |
| Camo net A (ε≈0.60) | −512,481 | 399.6 | 9.0 | 72.5% |
| Camo net B (shaped) | −274,894 | 214.3 | 11.0 | 85.2% |
| **Camo net C (ε≈0.93)** | **+83,183** | **64.9** | 14.0 | **95.5%** |

### Sub-band (which half detects each option best?)

| Option | 8–10 µm SCNR | 10–12 µm SCNR | Best |
|--------|-------------:|--------------:|------|
| Bare vehicle | 1,136.3 | 898.5 | 8–10 µm |
| Net A | 264.7 | 291.0 | 10–12 µm |
| Net B | 264.3 | 46.2 | 8–10 µm |
| Net C | 48.1 | 42.6 | 8–10 µm |

Net B's shaping is visible: its high 10–12 µm emissivity matches the
background well there (SCNR 46), but its low 8–10 µm reads cold (SCNR 264).
A sensor confined to one half-band would rank the nets differently than
the full FLIR — the reason spectral, not scalar, emissivity matters.

### Detection range

Edge-limited at 17.1 km for **every** option (the 80° zenith sweep cap,
not SCNR): a sensitive FLIR at 3 km detects all options across the
practical swath. **Emissivity camo buys signature reduction, not
invisibility** at this range. (The zenith bisection sweeps
`geometry.path_zenith_rad` — the target-side path zenith θ_o — and reads the
slant range back through the chain's own `slant_range_from_theta_o_m`;
CU-182 fixed the earlier over-spec that set a second, sensor-off-nadir slant
via `geometry.target_range_m`, so the km figure is now internally consistent
with the chain geometry, 17.1 km vs the pre-fix 17.4 km.)

## Physics Discussion

**Camouflage is radiance MATCHING, not lowering emission.** The effective
net drives `ε_net·B(T_net)` toward `ε_bg·B(T_bg)`, i.e. contrast → 0. Net C
(ε ≈ 0.93, near the 0.96 scrub, at near-ambient 310 K) does exactly that:
+83k e⁻ residual, a 95.5% signature cut. The intuitive "low-ε to reduce
emission" choice (net A) **over-corrects** — 0.60 emissivity at ambient
reads distinctly *cold* (−512k e⁻), a large *negative* contrast that a
`|contrast|` detector sees just as well as a hot one. This is the central,
counter-intuitive result: against a warm ground background, a poorly
chosen low-ε net can be *worse than nothing at all* in the wrong direction.

**Why the S8 radiance path, and why extended.** The chain has no spectral
target-emissivity input (Gap 47), so the emissivity physics is done at the
file boundary and injected as radiance. The extended regime is used because
a draped net genuinely fills the FLIR pixel; the sub-pixel path's EE_box
penalty (correct for isolated point targets) understates a pixel-filling
target and, composed with the in-pixel background term, inverted the
electron contrast in early runs — the extended differential-vs-scrub
construction is both cleaner and the physically right model here.

**Net C's three-point limitation.** The quote sheet gives ε at 8.0/10.5/
14.0 µm only; the script linearly interpolates between them, and any
spectral structure between the points is invisible to the analysis
(flagged in `gaps.md`). Net C *happens* to be smooth, so this is benign —
but a resonant net could hide a detection window between the spot values.

## Recommendation

**Camo net C** — 95.5% signature reduction, the closest background match.
Its high, flat emissivity near the scrub value is what a warm-background
thermal net should have; low-ε "reduce emission" nets (net A) over-correct
into a cold signature. Note that none of the nets defeats detection at
3 km — they reduce the thermal *signature*, which is the operational metric
(harder to track/classify, shorter effective ID range), not detectability
against a sensitive short-range FLIR.

## Gaps Identified

See `gaps.md`. Highlights: ASTER importer **closed** (f50253a); **spectral
target emissivity has no chain input** (new registry **Gap 47** — worked
around via S8 radiance composition); ΔL(λ), optimal-band, and
range-reduction are script-side analyses (ΔL is a hand-Planck plot, no new
gap); sparse-spectral interpolation is a documented assumption, not a
framework gap.

## Outputs

- `outputs/camouflage_results.xlsx` — per-option trade table
- `outputs/derived/` — the four L_t(λ) CSVs + the scrub reference (S8 inputs)
- `outputs/fig1_spectral_contrast.png` — ΔL(λ) for all options
- `outputs/fig2_signature_by_option.png` — nadir SCNR bar chart
- `outputs/fig3_emissivity_inputs.png` — the four input ε(λ) spectra + scrub line

## What Lisa Would Do Next

1. **Model the net's actual temperature** (solar loading, vehicle
   conduction through the standoff) rather than the assumed 310 K — the
   contrast is first-order in T_net
2. **Feed real ASTER/measured net spectra** through the same S8 path once
   spectral target emissivity lands in the chain (Gap 47)
3. **Test against the multi-band sensor set** (scenario 1.3): net B's
   shaping that fails here would pay against an 8–10 µm-only seeker
4. **Add a recognition/ID range criterion** (NIIRS/DRI), not just
   detection — camo's operational value is denying classification
