# Scenario 2.4 — GUI Workflow Requirements

How Mike would characterize persistence in the RADIANT GUI. (Per the house
rule; the GUI is not yet built.)

## Workflow

1. **Load persistence config** (`mike_persistence.xlsx`): fraction, τ,
   prior exposure, frame rate, current scene.
2. **Decay panel:** the GUI plots residual signal and persistence noise vs
   frame (log axis) with the 1-LSB floor and marks the frames-to-clear.
3. **SNR recovery:** current-scene SNR vs frame, converging to the clean
   SNR as the ghost decays.
4. **Read the dead time:** frames-to-clear × frame interval — the wait after
   a bright hit before the array is trustworthy.

## MATLAB-like command window

```python
>>> from radiant.detector.persistence_sequence import (
...     persistence_residual_sequence_e, frames_to_clear)
>>> persistence_residual_sequence_e(150000, 0.015, 0.050, 1/60, 20)[:3]
array([2250. , 1612.2, 1155.2])
>>> frames_to_clear(150000, 0.015, 0.050, 1/60, threshold_e=100.0)
11
```

Requirements: the sequence + frames-to-clear callable from the window; a
per-frame overlay of ghost-in-LSB vs the noise floor so the bias-vs-noise
distinction is visible.

## GUI-specific gaps

- A **ghost-in-LSB overlay** (residual / gain) alongside the noise trace so
  users see the persistence *bias* is the operational limiter, not the shot
  noise.
- A **dead-time read-out** (frames-to-clear × frame interval) for duty-cycle
  planning after bright-source events.
