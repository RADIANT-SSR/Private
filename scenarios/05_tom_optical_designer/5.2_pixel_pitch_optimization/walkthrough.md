# Scenario 5.2 Walkthrough: Pixel Pitch / Q-Parameter Trade Study

## The Problem

Tom is an optical designer selecting a detector for a MWIR pushbroom imager. His optics are fixed — a Ritchey-Chrétien telescope with a 30 cm aperture, f/4, operating in the 3.5–5.0 µm band from a 500 km LEO orbit. What he needs to decide is the pixel pitch.

Six candidate detectors are available from different vendors, with pixel pitches from 8 to 30 µm. Each pitch comes with its own detector characteristics — smaller pixels tend to have lower full well capacity, lower dark current, and lower read noise, while larger pixels have higher well capacity and higher noise floors.

Tom's question: **which pixel pitch gives the best balance of spatial resolution and sensitivity, while meeting all system requirements?**

The requirements are:
- GSD < 10 m (ground sample distance at nadir)
- MTF at Nyquist ≥ 0.10
- EE 1×1 ≥ 0.30
- SNR ≥ 100

## The Sampling Parameter Q

The central concept in this trade study is the **sampling parameter Q**, defined as:

```
Q = λ · f/# / p
```

where λ is the wavelength, f/# is the focal ratio, and p is the pixel pitch. Q describes how well the detector samples the optical point spread function (PSF):

- **Q > 1.5**: Oversampled. The Airy disk spans many pixels. Smooth, well-resolved PSF, but smaller pixels collect fewer photons. At Q = 2.12 (8 µm), the Airy disk spans over 5 pixels — each pixel sees only a small fraction of the PSF energy.

- **Q ≈ 1.0**: Critically sampled. The Airy disk spans about 2 pixels. This is the theoretical optimum for information capture per Nyquist-Shannon sampling theory, but in practice Q ≈ 1.0–1.4 provides the best balance.

- **Q < 0.7**: Undersampled / aliased. The Airy disk fits within a single pixel. High-frequency spatial information folds back below Nyquist (aliasing). MTF at Nyquist appears high because the detector can't resolve the PSF structure — it just averages everything into one pixel.

For Tom's system at λ = 4.25 µm and f/4, the Airy disk diameter is 2.44 × λ × f/# = 41.6 µm. The Q values range from 2.12 (8 µm, oversampled) to 0.57 (30 µm, aliased).

## How RADIANT Solves This

### Step 1: Read and Convert Tom's Design Data

Tom's data arrives in optical designer units:
- **Zemax convention**: entrance pupil diameter and focal length in mm (not cm or m)
- **Spectral**: filter edges in nm (not µm)
- **Detector vendors**: pixel pitch in µm, dark current in e⁻/s, QE in %
- **Mission**: orbit altitude in km, GSD in m

The script converts at the boundary: mm → m (÷ 1000), nm → µm (÷ 1000), % → fraction (÷ 100), km → m (× 1000).

Each candidate pitch has matched detector specs from the vendor table — this isn't just a single parameter sweep. The 8 µm detector has different QE (70%), dark current (15 e⁻/s), FWC (40,000 e⁻), and read noise (8 e⁻) than the 30 µm detector (68% QE, 120 e⁻/s dark, 2.5M FWC, 28 e⁻ read noise).

### Step 2: Compute Q and GSD

Before running RADIANT, the script calculates the sampling parameter and ground sample distance for each pitch:

| Pitch [µm] | Q [—] | GSD [m] | Sampling Regime |
|-------------|-------|---------|-----------------|
| 8           | 2.12  | 3.3     | Oversampled     |
| 12          | 1.42  | 5.0     | Well-sampled    |
| 15          | 1.13  | 6.2     | Well-sampled    |
| 18          | 0.94  | 7.5     | Undersampled    |
| 24          | 0.71  | 10.0    | Undersampled    |
| 30          | 0.57  | 12.5    | Aliased         |

The GSD requirement (< 10 m) immediately eliminates the 24 and 30 µm options. But Tom still needs to understand the full trade space.

### Step 3: Run RADIANT for Each Candidate

RADIANT evaluates the complete signal chain for each pixel pitch with matched detector specs. The atmosphere model is "simple" (LEO through atmosphere at 500 km). All configurations use extended radiometric regime — the 310 K ground target fills every pixel.

Results:

| Pitch [µm] | Q    | SNR    | MTF@Nyq | EE 1×1 | NIIRS | NEDT [mK] | Signal [e⁻] |
|-------------|------|--------|---------|--------|-------|-----------|-------------|
| 8           | 2.12 | 199.8  | 0.000   | 0.164  | 4.3   | 149.4     | 40,000      |
| 12          | 1.42 | 346.2  | 0.115   | 0.309  | 4.5   | 86.2      | 120,000     |
| 15          | 1.13 | 499.7  | 0.203   | 0.389  | 4.7   | 59.7      | 250,000     |
| 18          | 0.94 | 706.9  | 0.267   | 0.483  | 4.8   | 42.2      | 500,000     |
| 24          | 0.71 | 950.7  | 0.355   | 0.565  | 4.7   | 31.4      | 904,280     |
| 30          | 0.57 | 1171.2 | 0.409   | 0.623  | 4.6   | 25.5      | 1,372,568   |

The trends are clear:
- **Signal scales roughly as p²** — the 30 µm pixel collects ~34× more photons than the 8 µm pixel (whose well saturates and clips at 40,000 e⁻, so the ratio understates the raw p²·QE collection). This is the dominant driver of SNR.
- **SNR increases with pitch** — larger pixels win on sensitivity.
- **MTF at Nyquist decreases with smaller pitch** — counterintuitively, the 8 µm pixel has MTF = 0 at Nyquist. This is because at Q = 2.12, the Nyquist frequency (62.5 cy/mm) is well beyond the optical cutoff, so there is no modulation at that frequency. The MTF is zero because the optics can't produce contrast at such a high spatial frequency.
- **EE 1×1 decreases with smaller pitch** — the Airy disk spreads across many pixels at small pitch, so each pixel captures less of the total PSF energy.

### Step 4: Requirements Compliance

| Pitch | GSD < 10 m | MTF ≥ 0.10 | EE ≥ 0.30 | SNR ≥ 100 | Verdict |
|-------|------------|------------|-----------|-----------|---------|
| 8 µm  | PASS       | FAIL       | FAIL      | PASS      | FAIL (MTF, EE) |
| 12 µm | PASS       | PASS       | PASS      | PASS      | **ALL PASS** |
| 15 µm | PASS       | PASS       | PASS      | PASS      | **ALL PASS** |
| 18 µm | PASS       | PASS       | PASS      | PASS      | **ALL PASS** |
| 24 µm | FAIL       | PASS       | PASS      | PASS      | FAIL (GSD) |
| 30 µm | FAIL       | PASS       | PASS      | PASS      | FAIL (GSD) |

Three candidates pass: 12, 15, and 18 µm. The 8 µm pixel fails on three metrics — it's too small for this f/4 system. The 24 and 30 µm pixels exceed the GSD requirement.

### Step 5: Optimal Selection

Among the three compliant candidates, a simple figure of merit (SNR / GSD — higher is better, favoring both high sensitivity and fine resolution) selects **18 µm** as the optimal pixel pitch:

| Pitch [µm] | Q    | GSD [m] | SNR   | NIIRS | NEDT [mK] | FoM (SNR/GSD) |
|-------------|------|---------|-------|-------|-----------|----------------|
| 12          | 1.42 | 5.0     | 346.2 | 4.5   | 86.2      | 69.2           |
| 15          | 1.13 | 6.2     | 499.7 | 4.7   | 59.7      | 80.6           |
| 18          | 0.94 | 7.5     | 706.9 | 4.8   | 42.2      | **94.3**       |

The 18 µm pixel has Q = 0.94 — slightly undersampled but with excellent SNR margin (707 vs. 100 requirement) and GSD margin (7.5 m vs. 10 m limit). It's the classic engineering trade-off: slightly sacrificing sampling adequacy for a large gain in sensitivity.

## Key Takeaways

1. **Q = 0.94 (18 µm) is the sweet spot for this f/4 MWIR system.** Slightly undersampled, but the SNR gain from larger pixels far outweighs the modest aliasing risk. The MTF at Nyquist (0.267) and EE 1×1 (0.483) are both well above requirements.

2. **Oversampling is expensive in SNR.** The 8 µm pixel (Q = 2.12) is severely oversampled — it has 3.3 m GSD but can barely meet the SNR requirement. Signal scales as p², so halving the pixel pitch quarters the signal. Going from 18 to 8 µm reduces signal by 5×.

3. **GSD drives the upper bound on pitch, not spatial metrics.** The 24 and 30 µm options have excellent MTF and SNR but fail on GSD. If the GSD requirement were relaxed to 12 m, the 24 µm pixel (Q = 0.71) would be a strong contender.

4. **Each pitch needs matched detector specs.** This isn't a single-parameter sweep — smaller pixels have different noise characteristics, well capacity, and QE than larger ones. Running the trade with identical detector specs (just changing pitch) would give misleading results.

5. **MTF at Nyquist = 0 for the 8 µm pixel is physical, not a bug.** At Q = 2.12, the Nyquist frequency (62.5 cy/mm) exceeds the optical diffraction cutoff (~59 cy/mm at 4.25 µm, f/4). There is genuinely no modulation at that frequency — the optics cannot produce contrast faster than the diffraction limit, and the 8 µm pixel's Nyquist is beyond it.

## Gaps Identified

- ~~**Gap 1 (No Q parameter in RADIANT output)**: FIXED. Q (center, min, max) is now computed natively by PerformanceStage and available in `result.metrics["q_center"]`, `["q_min"]`, `["q_max"]`.~~

- ~~**Gap 2 (No GSD in RADIANT output)**: FIXED. GSD (cross-track and along-track) is now computed natively and available in `result.metrics["gsd_cross_track_m"]`, `["gsd_along_track_m"]` when orbital geometry is specified.~~

- **Gap 3 (No aliased/folded MTF model)**: RADIANT computes the system MTF at Nyquist but does not model aliasing (spatial frequency folding). For undersampled systems (Q < 1), the apparent MTF at Nyquist can be misleadingly high because energy from above-Nyquist frequencies folds back. A proper aliased MTF would show this effect.

- ~~**Gap 4 (No full MTF curve export)**: FIXED. Full MTF curves (frequency array + MTF values) for both axes are now stored in `result.stage_outputs["performance"]` as `mtf_freq_x`, `mtf_x`, `mtf_freq_y`, `mtf_y`.~~

- ~~**Gap 5 (MTF = 0 at 8 µm pitch)**: CLOSED — physically correct, not a bug. At Q = 2.12, the Nyquist frequency (62.5 cy/mm) exceeds the diffraction cutoff (~59 cy/mm at 4.25 µm, f/4). RADIANT now emits a diagnostic warning when this condition is detected.~~

### New Metrics Available Since Initial Run

The script now also extracts these natively computed metrics at each pitch:
- **RER** (relative edge response) — from `result.metrics["rer"]`
- **FWHM** (PSF full-width at half-max) — from `result.metrics["fwhm_x_m"]`
- **NEDT** (noise-equivalent temperature difference) — from `result.metrics["nedt_K"]`
- **NIIRS** (national imagery interpretability rating scale) — from `result.metrics["niirs"]`
- **Strehl ratio** — from `result.metrics["strehl"]`
