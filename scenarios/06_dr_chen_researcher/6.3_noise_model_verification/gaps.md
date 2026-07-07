# Scenario 6.3 Gaps: Noise Model Verification — Analytic vs. RADIANT

## Summary
System: 30 cm f/4 MWIR (3.5–5.0 µm), 18 µm HgCdTe at 77 K, 293 K optics, 8 km airborne, exo atmosphere; GSD = 0.12 m, Q = 0.944.
All six hand-verifiable noise terms PASS (< 5% tolerance): shot terms agree to ~3% (band-center photon-energy approximation in the hand calc), deterministic terms match exactly. Total RSS: 1551.52 (hand) vs. 1596.82 (RADIANT) e⁻ RMS = 2.92%. SNR 917.50 vs. 943.25 (2.81%); NEDT 30.43 vs. 28.18 mK (7.37%, expected from finite-difference dS/dT).

## Gap Closure Status

| # | Gap | Severity | Status | Evidence |
|---|-----|----------|--------|----------|
| 1 | No noise sensitivity matrix d(σᵢ)/d(pⱼ) | Medium | Open | `radiant.api.sensitivity` provides one-at-a-time sensitivities for scalar metrics (default: SNR) but no per-noise-term Jacobian; Dr. Chen must run manual parameter sweeps to get ∂σᵢ/∂pⱼ for her paper |
| 2 | Scalar transmission mode forces nearfield_shot = 0 | Medium | Open | Lumped element is treated as refractive, so ε = 1 − T − R = 0 by Kirchhoff. With 293 K optics in a 3.5–5.0 µm band, mirror self-emission is physically significant but unrepresentable in scalar mode. Cross-ref: scenario 7.1 Gap 6 (rated HIGH there). Workaround: `key_elements` or `full_prescription` mode |
| 3 | No first-class total-noise metric | Low | Open | `sigma_total_e` exists only in the readout stage output; script re-RSS's a hardcoded 13-name set of temporal terms (`run_verification.py:347-352`), which will silently drift if a noise term is ever added or renamed |
| 4 | dS/dT (responsivity derivative) not exposed | Low | Open | NEDT verification must rebuild dL/dT via finite-difference Planck integration; only end-to-end NEDT is cross-checkable, not RADIANT's internal spectral derivative. Same as scenario 7.1 Gap 4 |
| 5 | MTF budget only reachable via stage_outputs | Low | Open | Script reaches into `result.stage_outputs["performance"]["mtf_budget"]` and reconstructs x/y pairs by string-parsing `*_x`/`*_y` key suffixes; no first-class per-axis budget accessor |
| 6 | Spreadsheet parameters with no config pass-through | Low | Open | "Number of optical elements" (informational only in scalar mode), "Number of TDI stages" (`readout.n_tdi` exists in the schema but the script never passes it; value = 1 so benign), "Look angle" (0° nadir; not wired into the config). All are read and printed but silently ignored — a non-default spreadsheet value would not change the result |
| — | NEDT / NIIRS / GSD / Strehl / Q / MTF-budget metric exposure | Medium | **CLOSED** | All exposed: `result.metrics["nedt_K"]` = 28.18 mK, `["niirs"]` = 10.89, `["gsd_geometric_mean_m"]` = 0.12 m, `["strehl"]` = 1.0, `["q_center"]` = 0.9444; `mtf_budget.per_term_at_nyquist` with 7 terms |

## Non-Gap Observations

- The ~3% signal/background shot-noise discrepancy is the **hand calc's** approximation, not a RADIANT error: the hand calc converts photons to electrons using a single band-center photon energy (λ = 4.25 µm), while RADIANT integrates spectral radiance × QE(λ) × filter(λ) per wavelength. RADIANT is the more physically accurate side of the comparison.
- Deterministic terms (dark_shot 0.71 e⁻, read_noise 20.00 e⁻, quantization = gain/√12 = 0.29 e⁻) match to 0.00% — they involve no spectral integration.
- nearfield_shot = 0 is **correct physics** under the scalar-mode refractive-lump assumption (T + R = 1 → ε = 0); Gap 2 is a modeling-scope limitation, not a bug. The hand calc also predicts 0 for this configuration, so the verification row passes legitimately.
- The 7.37% NEDT difference is expected: the hand calc uses a finite-difference dS/dT (±0.1 K) with a band-center photon energy, while RADIANT computes dL/dT spectrally. This compounds the same ~3% approximation that appears in the shot terms.
- No unit-conversion gap: manual cm→m, %→fraction, ms→s, km→m conversions at the spreadsheet boundary are the intended workflow (canonical-units Rule 2). RADIANT accepted every converted parameter directly through `Sensor.from_dict`; no parameter required a manual correction or post-hoc scaling after the run.
- The script contains **no re-implemented RADIANT physics used as a workaround** — the Planck integration in Steps 5 and 7 is the independent analytic reference the scenario exists to compare against, and it deliberately imports only `radiant.core.constants` (h, c, k_B) so both sides share CODATA values.
