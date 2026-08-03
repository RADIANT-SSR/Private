# Scenario 4.5 — Gaps and Friction

Issues encountered building/running the microbolometer UAV altitude trade.
Registry items are mirrored into `docs/tracking/gaps.md`.

---

## RESOLVED during this scenario

### Microbolometer NETD-specified model (was the primary gap)
The catalog flagged "microbolometer noise model (NETD-specified)". Rather
than a bespoke thermal-fluctuation-noise model, this is served by the
shared **D*/NEP/NETD converter set** (`radiant.performance.detectivity`,
`.nep_electrons`, `.nep_netd`, committed ac59315): a vendor NETD is turned
into NEP and D* using the chain's `dP/dT`. This is the owner-approved
design (one shared noise-spec model for 4.5 and 6.1), avoiding a
first-principles bolometer-noise model neither scenario needs. This
scenario is its second consumer (6.1 the first).

---

## Friction / lessons

- **The UAV IR altitude ceiling is resolution-limited, not
  atmosphere-limited.** Over 1–11 km the atmospheric transmission drops
  0.92 → 0.69 (×1.34), while the sub-pixel fill fraction collapses ∝1/alt²
  (×28.6) — dilution outweighs attenuation ~21:1. The apparent-contrast trade
  must model the fill-fraction dilution; attributing lost detection to
  "atmosphere" would mis-diagnose the fix (longer focal length, not a clearer
  sky). *τ figures refreshed 2026-08-02 from the unmodified runner (previous
  vintage 2026-07-08, 0.94 → 0.87); mover CU-161 (`0aebdda`). The conclusion
  holds but the margin is narrower, and the detection ceiling moved 8.5 → 7.5 km.*
- **NETD → NEP needs a dP/dT.** The optical-power temperature derivative
  comes from the chain's exact `dS/dT` (Gap 43) via
  `dP/dT = dS/dT · hc/(QE·λ·t_int)`. Reusing the Gap 43 output kept the
  converter chain exact rather than re-deriving a band-center approximation.

---

## Framework observations (no new gap)

- This scenario computes the sub-pixel fill fraction and apparent contrast
  analytically (script-side) rather than through the chain's sub-pixel
  regime, because the detection floor here is an apparent-ΔT-vs-NETD
  threshold, not a chain `contrast_snr`. A future enhancement could drive
  it through the chain's sub-pixel regime with a NETD-derived noise floor,
  but that couples to the deferred extended-contrast work (Gap 52) and is
  not needed for the altitude ceiling. Not filed as a gap.
