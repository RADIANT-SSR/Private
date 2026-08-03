# Scenario 2.4 — Persistence Characterization (Bright-Source Recovery)

**Persona:** Mike, detector engineer.
**Question:** After imaging a hot 800 K calibration source, how long does
the Type-II superlattice detector's persistence ghost linger, and how does
it affect the current scene?

First consumer of the new multi-frame model
`radiant.detector.persistence_sequence`.

---

## Inputs (non-RADIANT)

| File | Format | Represents |
|------|--------|-----------|
| `inputs/mike_persistence.xlsx` | Excel workbook | Measured persistence (fraction, τ), the bright prior exposure, and the current-scene / detector config |

`inputs/create_spreadsheet.py` regenerates it.

---

## The model

Residual (ghost) signal in frame *n* after the bright exposure decays with
the trap time constant:

```
residual_e(n) = prior · f · exp(−(n−1)·Δt_frame / τ)
```

with per-frame shot noise `√residual_e`. `f` = 1.5 % (residual in frame 1),
τ = 50 ms, Δt = 16.67 ms (60 Hz). The ghost is "cleared" once it drops
below one LSB (`gain_e_per_dn` = 100 e⁻).

---

## Results (prior 150,000 e⁻, current scene 20,000 e⁻)

| Frame | Residual [e⁻] | Ghost [LSB] | Persistence noise [e⁻] | Scene SNR |
|-------|---------------|-------------|------------------------|-----------|
| 1 | 2250 | 22.5 | 47.4 | 58.4 |
| 4 | 828 | 8.3 | 28.8 | 58.8 |
| 8 | 218 | 2.2 | 14.8 | 58.9 |
| 11 | ~80 | ~0.8 | ~9.0 | 59.0 |
| 17 | 11 | 0.1 | 3.3 | 59.0 |

*Numbers refreshed 2026-08-02 from the unmodified runner (previous vintage 2026-07-08). Only the frame-11 row moved: it is interpolated by hand (the runner prints frames 1–9, 13 and 17), and its previous values were an arithmetic slip, not physics movement — no in-window Results-affecting landing touches this scenario, which is a closed-form `radiant.detector.persistence_sequence` calculation with no atmosphere, optics, or chain radiometry in the loop. Frames-to-clear is unchanged at 11, since residual(10) = 112.0 e⁻ > 1 LSB > residual(11) = 80.3 e⁻.*

- **Frames to clear below 1 LSB: 11** (~183 ms of dead time after a bright
  hit before the ghost is sub-LSB).
- **The bias, not the noise, is the problem.** The persistence *shot noise*
  is small (47 e⁻ in frame 1 vs the 300 e⁻ read noise), so the current
  scene's SNR barely moves (59.0 → 58.4, −1 %). But the residual *signal* is
  a **22-LSB false structure** — a ghost image of the calibration source —
  that a detection algorithm would flag as real.
- **The ghost does not average away.** Unlike random noise (which
  frame-averaging beats down), the persistence bias is a systematic,
  decaying image; the only remedy is to wait out the ~11 frames or subtract
  a modeled ghost.

---

## Physics / modeling notes (house rule)

- **Two distinct effects:** the residual is (a) a bias (ghost image, in
  LSB) and (b) a shot-noise contribution (√residual). The scenario reports
  both; the bias dominates the operational impact.
- **Extends the single-frame term:** RADIANT already had a single-frame
  `persistence_noise`; this adds the temporal sequence + the residual
  *signal* + the frames-to-clear metric the single-frame form could not
  give.
- **τ vs frame rate** sets the clearing time: a longer τ or faster frame
  rate means more frames (but similar wall-clock) to clear.

---

## Truth anchors

Verified in `src/radiant/detector/tests/test_persistence_sequence.py`
(9 Level-0 tests): residual(1) = prior·f = 2250 e⁻; residual(n) =
residual(1)·exp(−(n−1)Δt/τ); frames-to-clear straddles the threshold
(residual(n) < threshold ≤ residual(n−1)).
