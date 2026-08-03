# Scenario 6.4 — Synthetic Scene Generation for Algorithm Testing

**Persona:** Dr. Chen, developing an LWIR target-detection algorithm.
**Question:** Give me pixel-level signal and noise for a multi-target scene,
a simulated noisy 1-D strip, an SNR map, and a ROC curve per target — the
raw material to test a detector against.

First consumer of the new `radiant.performance.roc` model
(`roc_curve`, `detection_probability`, `roc_auc`).

---

## Inputs (non-RADIANT)

| File | Format | Represents |
|------|--------|-----------|
| `inputs/chen_scene.xlsx` | Excel workbook | 5 targets (range/T/ε/size), the uniform 290 K background, and the LWIR sensor config |

`inputs/create_spreadsheet.py` regenerates it; the values are transcribed
into the run script.

---

## Method — chain radiometry, analytic scene assembly

RADIANT supplies the radiometry; the script assembles the scene from it.

1. **Background run** (extended, 290 K) → per-pixel background signal
   `S_bg` and total noise `σ` (shot + dark + read).
2. **One run per target temperature** (extended, full pixel) → the target's
   filled-pixel signal `S_tgt`.
3. **Fill-fraction contrast.** Each target subtends
   `ff = (size / GSD)²`, `GSD = IFOV · range`, capped at 1 when the target
   over-fills the pixel. The per-pixel contrast is
   `contrast_e = ff · (S_tgt − S_bg)`, and the contrast SNR is
   `contrast_e / σ`.
4. **ROC.** The equal-variance Gaussian detection model
   (`radiant.performance.roc`) turns each contrast SNR into
   `P_d = Q(Q⁻¹(P_fa) − SNR)`, `AUC = Φ(SNR/√2)`.

**Key regime fact used throughout:** in the extended regime the per-pixel
background and *filled-pixel* target signals are **range-independent** (they
are radiance × a fixed pixel solid angle). Only `ff` depends on range. That
is what makes the detection-range sweep below a pure analytic dilution of an
already-computed signal — no re-running the chain.

---

## Results

### The five nominal targets (all trivially detected)

Sensor: 5 cm aperture, f/20, 25 µm pitch (25 µrad IFOV), LWIR 8–12 µm,
0.5 ms integration. Sub-pixel onset (GSD = 3 m target size) is at **120 km**.

| Target | Range | GSD | Fill frac | Contrast (e-) | Contrast SNR | P_d @ P_fa 1e-4 |
|---|---|---|---|---|---|---|
| T1 | 10 km | 0.25 m | 1.00 (resolved) | 351 031 | 475.5 | 1.000 |
| T2 | 20 km | 0.50 m | 1.00 (resolved) | 248 037 | 336.0 | 1.000 |
| T3 | 50 km | 1.25 m | 1.00 (resolved) | 185 400 | 251.2 | 1.000 |
| T4 | 100 km | 2.50 m | 1.00 (resolved) | 152 975 | 207.2 | 1.000 |
| T5 | 200 km | 5.00 m | 0.36 (sub-pixel) | 36 379 | 49.3 | 1.000 |

*Numbers refreshed 2026-08-02 from the unmodified runner (previous vintage
2026-07-09). Dominant mover: CU-224 — down-looking path radiance now carries
`(1−τ)·B(λ,T_eff)`, which lifts the background pixel by +18.7 % and its
shot-noise floor by +8.7 %. CU-267's gas-region blend contributes a further
−0.27 % on τ over 8–12 µm. **Note the sign:** CU-224 is documented as
*raising* SNR, and it does raise the chain's own `snr` metric — but this
scenario's figure of merit is a script-derived **contrast** SNR,
`ff·(S_tgt − S_bg)/σ`. The added path emission is common to target and
background so it cancels out of the numerator, while it still inflates σ.
Contrast SNR therefore falls where chain SNR rises; the two are not in
conflict.*

Background pixel: 5.343×10⁵ e-, σ = 738 e- — **shot-noise-limited**. Every
nominal target is 15–40 K hotter than the background, so contrast SNR runs
49–476. **All five are trivially detected** — the correct answer for a hot,
resolved (or barely-diluted) target with this sensor. A ROC of just these
five is uninformative: every curve is pinned in the top-left corner.

### Detection-range sweep — where the ROC is informative

The detection science lives at the sensitivity floor. Push the reference
target (305 K, 3 m, ε 0.93) outward; `ff ∝ 1/range²` walks the contrast SNR
down through the informative band:

| Range | GSD | Fill frac | Contrast (e-) | Contrast SNR | ROC AUC | P_d @ P_fa 1e-4 |
|---|---|---|---|---|---|---|
| 200 km | 5.0 m | 0.360 | 36 379 | 49.3 | 1.0000 | 1.000 |
| 500 km | 12.5 m | 0.0576 | 5 821 | 7.9 | 1.0000 | 1.000 |
| 800 km | 20.0 m | 0.0225 | 2 274 | 3.1 | 0.9853 | **0.262** |
| 1100 km | 27.5 m | 0.0119 | 1 203 | 1.6 | 0.8753 | 0.018 |
| 1300 km | 32.5 m | 0.0085 | 861 | 1.2 | 0.7953 | 0.005 |
| 1500 km | 37.5 m | 0.0064 | 647 | 0.88 | 0.7322 | 0.002 |
| 2000 km | 50.0 m | 0.0036 | 364 | 0.49 | 0.6363 | 0.001 |

*Same refresh and same dominant mover as the table above (CU-224). The
deeper noise floor pulls both headline ranges in by roughly 3–14 %.*

- **Reliable detection (P_d ≥ 0.9 @ P_fa 1e-4) holds out to ≈ 533 km**;
  the **50/50 range is ≈ 687 km**. Between them is the operating band where
  a detection algorithm actually earns its keep.
- Note the gap between AUC and the strict-P_fa `P_d`: at 800 km the AUC is
  still 0.985 (good *separation*) but `P_d` at P_fa = 1e-4 is only 0.26.
  Choosing a strict false-alarm budget costs detections — exactly the
  trade Dr. Chen tunes. (This point used to read 0.996 / 0.49, i.e. "about
  a coin flip"; post-CU-224 it is closer to one detection in four.)

### Simulated scene strip (fig 1)

A 1-D pixel strip with 12 background pixels between each target pixel; the
clean signal is corrupted with **Poisson shot noise on the signal plus a
Gaussian read-noise term** (fixed RNG seed → reproducible). The lower panel
is the contrast-SNR map at each target pixel.

### ROC family (fig 2)

ROC curves for the swept ranges, spanning the corner (200–500 km, near-
certain) through the informative band (800–1300 km) down toward chance
(2000 km). The P_fa = 1e-4 operating line is marked.

---

## Physics / modeling notes (house rule)

- **Every printed value carries units**; the noise model (shot + dark + read)
  and the regime (extended, range-independent per-pixel signal) are stated
  inline.
- **`is_hot_target = True`** on every run — LWIR self-emission of a warm
  surface, no solar/reflective term.
- **Why fill-fraction dilution and not a chain sub-pixel run:** the chain's
  point-source/sub-pixel path needs a projected area + range from the source
  stage; for a uniform-radiance patch the analytic `ff` dilution of the
  extended signal is equivalent and lets the range sweep stay analytic.
- **The near targets being "too easy" is not a modeling artifact** — it is
  the physical result. The scenario reports it honestly and moves the
  interesting analysis to the range sweep.

---

## Truth anchors

Verified in `src/radiant/performance/tests/test_roc.py` (11 Level-0 tests):
SNR = 0 → ROC is the chance diagonal, AUC = 0.5; AUC = Φ(SNR/√2)
(SNR = 1 → 0.760); `P_d(P_fa=0.5) = Φ(SNR)`; `P_d ≥ P_fa` and monotone in
SNR; negative SNR and out-of-range P_fa raise `RocError`.
