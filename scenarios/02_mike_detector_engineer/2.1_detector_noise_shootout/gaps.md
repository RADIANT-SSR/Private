# Scenario 2.1 Gaps: InSb vs. HgCdTe Noise Budget Shootout

Executed 2026-07-08 (Phase T3). Registry mirror: `docs/tracking/gaps.md`
(Gaps 42, 44, 45; importer gaps closed by commit 1de9cf4).

## Summary
Bench: 300 K blackbody filling the aperture, 3.5–5.0 µm, f/2.3, 15 µm
pixels, shared ROIC (33 fF, CDS, 5 e⁻/s glow), t_int = 1 ms, T_FPA = 77 K.
Both FPAs photon-noise-dominated at 77 K (σ_total 1037.7 vs 989.3 e⁻ RMS;
SNR 1029.7 vs 981.3). Trade numbers from exact Arrhenius inversion of the
vendor J_dark(T) data: crossover 77.3 K (InSb) vs 84.1 K (HgCdTe); BLIP
101.7 K vs 115.4 K; NEI 5.36e11 vs 5.62e11 photons/s/cm².

## Gap Closure Status (catalog "Gaps revealed" list)

| # | Catalog gap | Status | Evidence |
|---|-------------|--------|----------|
| 1 | No J_dark(T) CSV importer (A/cm² → e⁻/s) | **CLOSED** (commit 1de9cf4) | `radiant.io.dark_current_csv.load_dark_current_csv`; conversion `J·A_pix/q` in the loader (Rule 2); Arrhenius-faithful ln(J)-vs-1/T interpolation; refuses to extrapolate |
| 2 | No QE import from nm/percent format | **CLOSED** (commit 1de9cf4) | `radiant.io.qe_csv.load_qe_csv`; header-token unit resolution handles both vendor conventions in this scenario with the same call |
| 3 | No BLIP temperature calculation | Open — **registry Gap 45** | One-liner script-side via `temperature_at_rate(signal_e/t_int)`; not a native metric |
| 4 | No NEI metric | Open — **registry Gap 45** | Script-side: σ_total/(QE·A_pix·t_int); not in `result.metrics` |
| 5 | No dark-current crossover finder | Open — **registry Gap 45** | One-liner via `temperature_at_rate(RN²/t_int)` |
| 6 | No "detector-only mode" (lab blackbody source) | Open — **registry Gap 42** | Same bench masquerade as the 7.x scenarios: exo → 'space' sub-case + `platform.h_sensor = 1.0` m placeholder |

## New Gaps Found by This Execution

### Registry Gap 44 — `detector.qe_table_path` is schema-only (unwired)
The parameter exists in `detector/_schema.py` (with a comment promising a
"Phase 2C stage wrapper" XOR against `qe_value`) but nothing in the chain or
API reads it. Spectral QE reaches the chain only via the
`stage_outputs["spectral_integration"]["qe_curve"]` injection
(`RadiantSession.run(extra_stage_outputs=...)`) — an API-level route with no
config/YAML surface. Schema-drift + capability gap; this scenario used the
injection route with `QeCurve.evaluate(wl_grid)`.

### Registry Gap 45 — detector-comparison metrics are script-side
BLIP temperature, dark-current crossover temperature, and NEI are computed
in the scenario script. With the new loaders each is 1–3 lines, so severity
is low; a native home would be a `radiant.api` detector-trade helper (or
`result.metrics["nei_photons_s_cm2"]` for NEI, which needs only quantities
the chain already has).

## Non-Gap Observations

- **The no-extrapolation guard earned its keep on the first run**: the BLIP
  temperatures (101.7 / 115.4 K) lie above the initially generated 110 K
  table edge, and `temperature_at_rate` raised instead of silently
  extrapolating the exponential. The vendor tables were extended to 130 K —
  the correct fix, and exactly the failure mode the guard exists for.
- **Quantization (88 e⁻ at 305 e⁻/DN) is the #2 noise term** for both FPAs
  — larger than either read noise. Harmless on this photon-dominated bench;
  decisive for low-background scenes. Configuration finding, not a RADIANT
  gap (gain is a user input).
- **Spectral-vs-scalar QE differs by only ~1.2%** here because both QE
  curves are flat across 3.5–5.0 µm; the spectral injection route matters
  more for steep curves near cutoff (scenario 1.3 dual-band will stress it).
- **kTC hand cross-check**: √(k_B·T·C)/q = 37.0 e⁻ at 33 fF/77 K if CDS
  were off; RADIANT reports 0 with `cds_enabled = 1` — consistent.
- **background_shot = nearfield_shot = 0 are by design** (extended-regime
  Decision #13; scalar-mode ε = 0), same as documented in scenarios 6.3/7.4.
