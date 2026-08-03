# Scenario 6.3 Gaps: Noise Model Verification — Analytic vs. RADIANT

Refreshed 2026-07-07 (Scenario_Execution_Plan Phase R). Registry mirror:
`docs/tracking/gaps.md` (Gaps 6, 42, 43).

## Summary
System: 30 cm f/4 MWIR (3.5–5.0 µm), 18 µm HgCdTe at 77 K, 293 K optics, 8 km airborne, exo atmosphere; GSD = 0.12 m, Q = 0.944.
All six hand-verifiable noise terms now PASS at **0.00%**: the refreshed hand model integrates photons spectrally and includes the Kirchhoff reflected-solar term (ρ = 1 − ε under the space sub-case's TOA solar illumination), matching RADIANT's signal to < 0.01% (1,640,135 vs 1,640,136 e⁻). background_shot = 0 on both sides (extended regime skips the scene-background photon stream by design, matrix Decision #13). Total RSS: 1280.83 vs 1280.83 e⁻ RMS. SNR 1280.52 vs 1280.52 (0.00%). NEDT 21.79 (RADIANT) vs 23.92 mK (exact hand) — 8.91%, root-caused and filed as **registry Gap 43**.
Parameters entered RADIANT in vendor units via `Sensor.set(..., unit=)` (Gap 6), cross-checked against script conversions to 1e-12.

## Gap Closure Status

| # | Gap | Severity | Status | Evidence |
|---|-----|----------|--------|----------|
| 1 | No noise sensitivity matrix d(σᵢ)/d(pⱼ) | Medium | Open | `radiant.api.sensitivity` provides one-at-a-time sensitivities for scalar metrics (default: SNR) but no per-noise-term Jacobian; Dr. Chen must run manual parameter sweeps to get ∂σᵢ/∂pⱼ for her paper |
| 2 | Scalar transmission mode forces nearfield_shot = 0 | Medium | Open | Lumped element is treated as refractive, so ε = 1 − T − R = 0 by Kirchhoff. With 293 K optics in a 3.5–5.0 µm band, mirror self-emission is physically significant but unrepresentable in scalar mode. Cross-ref: scenario 7.1 Gap 6 (rated HIGH there). Workaround: `key_elements` or `full_prescription` mode |
| 3 | No first-class total-noise metric | Low | Open | `sigma_total_e` exists only in the readout stage output; script re-RSS's a hardcoded 13-name set of temporal terms (`run_verification.py:347-352`), which will silently drift if a noise term is ever added or renamed |
| 4 | dS/dT (responsivity derivative) not exposed | Low | Open | NEDT verification must rebuild dL/dT via finite-difference Planck integration; only end-to-end NEDT is cross-checkable, not RADIANT's internal spectral derivative. Same as scenario 7.1 Gap 4 |
| 5 | MTF budget only reachable via stage_outputs | Low | Open | Script reaches into `result.stage_outputs["performance"]["mtf_budget"]` and reconstructs x/y pairs by string-parsing `*_x`/`*_y` key suffixes; no first-class per-axis budget accessor |
| 6 | Spreadsheet parameters with no config pass-through | Low | Open | "Number of optical elements" (informational only in scalar mode), "Number of TDI stages" (`readout.n_tdi` exists in the schema but the script never passes it; value = 1 so benign), "Look angle" (0° nadir; not wired into the config). All are read and printed but silently ignored — a non-default spreadsheet value would not change the result |
| 7 | NEDT stage uses the single-λ Planck-factor approximation | Medium | Open — **registry Gap 43** (filed this refresh) | `nedt.compute_nedt_from_snr` reads 8.91% low here (21.79 vs 23.92 mK exact): its SNR includes the temperature-independent reflected-solar signal, inflating apparent thermal sensitivity. Exact path `nedt.compute_nedt` exists but unwired |
| — | Unit-aware input (registry Gap 6) | Medium | **CLOSED** (exercised this refresh) | `Sensor.set(value, unit="cm"/"%"/"ms"/"km")`; Step 3a cross-check vs script conversions matches to 1e-12 |
| — | NEDT / NIIRS / GSD / Strehl / Q / MTF-budget metric exposure | Medium | **CLOSED** | All exposed: `result.metrics["nedt_K"]` = 21.79 mK, `["niirs"]` = 11.12, `["gsd_geometric_mean_m"]` = 0.12 m, `["strehl"]` = 1.0, `["q_center"]` = 0.9444; `mtf_budget.per_term_at_nyquist` with 8 terms |

*Figures refreshed 2026-08-02 from the unmodified runner. The NEDT and
NIIRS values above (20.76 mK / 13.2% / 11.10) were stale against this
scenario's **own** walkthrough, which the 2026-07-22 CU-176 refresh
updated without touching this file — the movement predates the doc window
and is not attributable to any recent Results-affecting landing. The only
in-window change to this vacuum-path scenario is EE (1×1), via CU-188.*

## Non-Gap Observations

- The former ~3% shot-noise discrepancy was the **hand calc's** band-center photon-energy approximation; the refreshed hand model uses the photon-weighted spectral integral and matches RADIANT to < 0.01%.
- The former "background_shot" hand term modeled a scene construct that does not exist in the extended regime — RADIANT skips the separate scene-background photon stream by design (matrix Decision #13); the background inputs feed the contrast scene only. Both sides now report 0.
- The reflected-solar term (ρ·E_TOA·cosθ/π, ρ = 1 − ε = 0.05, θ = 0.5 rad default) is **correct daytime physics** of the space sub-case, ~9% of the in-band signal. A thermal-only comparison is a nighttime verification; the scenario now verifies the scene RADIANT actually models.
- Deterministic terms (dark_shot 0.71 e⁻, read_noise 20.00 e⁻, quantization = gain/√12 = 0.29 e⁻) match to 0.00% — they involve no spectral integration.
- nearfield_shot = 0 is **correct physics** under the scalar-mode refractive-lump assumption (T + R = 1 → ε = 0) with `optics.scalar_emissivity` unset; the hand calc also predicts 0, so the row passes legitimately. Gap 37's `scalar_emissivity` now offers a declared-ε alternative for warm reflective trains.
- Vendor-unit entry now flows through `Sensor.set(..., unit=)` (Gap 6) — RADIANT performs the cm/%/ms/km conversions at the boundary, and the script cross-checks them against its own conversions before running (a second, independent verification layer this scenario gains for free).
- The script contains **no re-implemented RADIANT physics used as a workaround** — the Planck integration in Steps 5 and 7 is the independent analytic reference the scenario exists to compare against. It imports `radiant.core.constants` (h, c, k_B) and the `radiant.core.solar` TOA irradiance table so both sides share input data; the physics under test is not imported.
