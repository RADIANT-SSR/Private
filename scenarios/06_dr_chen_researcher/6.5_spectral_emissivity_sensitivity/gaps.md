# Scenario 6.5 — Gaps and Friction

## RESOLVED during this scenario

### Temperature retrieval + Jacobian (was the primary gap)
The catalog flagged "no temperature retrieval model (inverse problem)" and
"no Jacobian output." **Built as `radiant.performance.temperature_retrieval`**
(committed 6623d0d): `retrieve_temperature_K` (Brent inversion of
`ε_assumed·B̄(T)=L`), `band_planck_radiance`, and the operating-point
Jacobians `emissivity_jacobian` (∂L/∂ε) and `temperature_jacobian` (∂L/∂T).
8 Level-0 tests with forward/inverse truth anchors.

The catalog's "no NEDT output" is resolved separately (Gap 3, and the exact
`dS/dT` NEDT from Gap 43); this scenario uses NEDT as the reference floor.

## Friction / lessons

- **Retrieval error is a systematic bias, not noise.** Averaging frames
  beats down NEDT but not the ε-assumption bias — the scenario reports the
  bias in NEDT-multiples to make the point (67× at ±0.05 ε).
- **The ε→T sensitivity is steep** (−0.64 K per 0.01 ε at 300 K LWIR):
  emissivity must be known to ~0.08 % for the bias to stay under a 50 mK
  NEDT. This is the researcher takeaway — absolute LWIR thermometry is
  emissivity-limited.

## Framework observations (no new gap)

- The retrieval model operates on band-averaged Planck radiance directly;
  a chain-integrated variant (using the full throughput/QE spectrum rather
  than a pure Planck band) would tie the retrieved T to the actual measured
  electrons. Not needed for the sensitivity study (the ε→T bias is a
  radiance-domain effect independent of the throughput scale). Not filed.
