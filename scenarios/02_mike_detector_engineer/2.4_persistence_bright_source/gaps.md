# Scenario 2.4 — Gaps and Friction

## RESOLVED during this scenario

### Multi-frame persistence model (was the primary gap)
The catalog flagged "no multi-frame temporal model (only single-frame
persistence noise)", "no residual signal calculation", and "no frames-to-
clear metric". **Built as `radiant.detector.persistence_sequence`**
(committed c4a3a28): `persistence_residual_sequence_e` (residual ghost
signal over frames), `persistence_residual_e`, and `frames_to_clear`. 9
Level-0 tests. Extends the existing single-frame `persistence_noise` term.

## Friction / lessons

- **Persistence is a bias, not (mainly) a noise.** The residual shot noise
  is small next to read noise (SNR barely moves), but the residual *signal*
  is a many-LSB ghost image that a detection algorithm treats as real — and
  it does not average away. The scenario reports the ghost in LSB to make
  the operational point.
- **Frames-to-clear is the actionable metric** (11 frames / ~183 ms here) —
  the dead time after a bright hit before the array is trustworthy.

## Framework observations (no new gap)

- A full frame-sequence *chain* simulation (running the chain per frame with
  the residual injected as a prior-frame signal) would let the ghost
  interact with the live scene radiometry. The analytic residual+noise
  sequence here is sufficient for the characterization outputs; a
  chain-integrated frame loop is a larger capability not needed for 2.4.
  Not filed.
