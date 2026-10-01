# Scenario 2.2 Gaps: 1/f Noise Corner Frequency

## Summary
At 60 Hz: σ_1f = 332.5 e⁻, NEDT_1f = 4.21 mK (2.3% of total noise variance).
Total NEDT at 60 Hz = 27.70 mK, of which 1/f adds 0.3 mK (1.2%).
RADIANT overestimates σ_1f by ~92% because it does not cap the integration at the corner frequency.

*Numbers refreshed 2026-08-02 from the unmodified runner (previous vintage 2026-07-09). No in-window Results-affecting landing covers this `exo`-atmosphere, extended-regime 8–10 µm bench; the corrected values are 2026-07-09 refresh residue, not physics movement.*

## Gap Closure Status

| # | Gap | Severity | Status | Evidence |
|---|-----|----------|--------|----------|
| 1 | No corner frequency model | Medium | FIXED | σ_1f = √(K·ln(f_high/f_low)) integrates over full band; should cap at f_c. Overestimate 64–170% at 30–120 Hz — **CU-387 triage 2026-09-30: FIXED by [[CU-381]]** — `detector.flicker_corner_hz` added, and the corner now enters as the shape of S(f) in the transfer integral rather than as a post-hoc cap. This row's 64-170 % overestimate measurement is cited in CU-381's resolution as one of its three truth anchors. |
| 2 | No frame-rate-aware f_low | Low | FIXED | User must manually set `flicker_f_low_hz`; no `detector.frame_rate_hz` shortcut — **CU-387 triage 2026-09-30: FIXED by [[CU-381]]** — `flicker_f_low_hz` now defaults to 0 = derive from the stack duration (`n_coadds x frame_period_s`), so the band follows the configured timing instead of a hand-set constant. |
| 3 | No noise PSD output | Low | OPEN | Only integrated σ available — no `result.noise_psd(f)` method — **CU-387 triage 2026-09-30: already tracked** as `docs/tracking/gaps.md` GUI-12 (bespoke analysis panels, which enumerates the 1/f PSD panel and names this scenario). No new entry — cross-referenced instead. |
| 4 | Per-term NEDT breakdown missing | Medium | **CLOSED** | `result.metrics["nedt_K"]` exposes total; per-term via `σ_i / (dS/dT)` |
| 5 | **NEW — Nearfield emission = 0 in scalar transmission mode** | **HIGH** (cross-scenario) | FIXED | Scalar mode assumes refractive lump (ε = 1 − T − R = 0). Mirror self-emission from warm optics not captured. Low impact here because extended-scene signal_shot dominates, but high impact for cold-stop (7.4) and point-source scenarios. — **CU-387 triage 2026-09-30: superseded by [[CU-380]]** — the engine now warns when warm-optics emission is structurally zero. This row is one of **five** independent recordings of that defect across scenario gaps.md files; none reached a governed registry, which is what CU-387 is about. The remaining work (a warm train for this scenario) is CU-380's open checklist item. |

## Gap 1 Detail — Corner Frequency Model (Medium)

### Observation
RADIANT's `flicker_1f_noise()`:
```python
σ_1f = √(K · ln(f_high / f_low))
```
integrates 1/f over the full [f_low, f_high] band.

Physically, the 1/f PSD only applies below f_c = 200 Hz. Above f_c the PSD is white — and that contribution is already captured in read noise.

### Comparison at each frame rate
| Frame Rate | σ_1f (RADIANT, full-band) | σ_1f (analytic, capped at f_c) | Overestimate |
|-----------|---------------------------|-------------------------------|--------------|
| 30 Hz | 357.6 e⁻ | 217.8 e⁻ | 64% |
| 60 Hz | 332.5 e⁻ | 173.5 e⁻ | 92% |
| 120 Hz | 305.4 e⁻ | 113.0 e⁻ | 170% |

### Impact
- RADIANT over-predicts flicker noise whenever f_high > f_c (common for short integration times)
- For this BLIP-limited case the 92% overestimate adds only 0.1–0.2 mK to NEDT — negligible
- For read-noise-limited systems, the overestimate could inflate NEDT predictions by several percent

### Recommended Fix
Add a `detector.flicker_corner_hz` parameter. If set, use:
```python
σ_1f = √(K · ln(min(f_high, f_c) / f_low))
```
Default behavior unchanged if corner is None.

## Non-Gap Observations

- 1/f noise is negligible in BLIP-limited LWIR NEDT (~1% penalty: 1.0–1.4% across 30–120 Hz). Mike does not need to worry about 1/f for this spec.
- Logarithmic dependence on frame rate is real physics — a 4× frame rate change only shifts σ_1f by 15%.
- LWIR integration time is FWC-limited (100 µs), not frame-rate-limited.

## Drift Fix 2026-07-07 — Stage-7 h_sensor precondition (registry Gap 42)

The script raised in `validate_no_atmosphere_subcase` after the Stage-7
landing: `atmosphere.model = "exo"` auto-infers the `no_atmosphere / space`
sub-case, which requires a positive user-set `platform.h_sensor` for the
Earth-limb intercept check (the `lab_test` sub-case has no `Sensor.from_dict`
path — registry Gap 42). Fixed in the Phase R sweep pass by adding the
placeholder `platform.h_sensor = 1.0` m (bench height); no radiometric
effect. Remove the placeholder when Gap 42 lands a first-class lab path.
