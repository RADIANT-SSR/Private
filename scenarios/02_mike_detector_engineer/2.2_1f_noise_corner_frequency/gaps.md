# Scenario 2.2 Gaps: 1/f Noise Corner Frequency

## Summary
At 60 Hz: σ_1f = 332.5 e⁻, NEDT_1f = 4.21 mK (1.2% of total noise variance).
Total NEDT at 60 Hz = 37.81 mK, of which 1/f adds 0.2 mK (0.6%).
RADIANT overestimates σ_1f by ~92% because it does not cap the integration at the corner frequency.

## Gap Closure Status

| # | Gap | Severity | Status | Evidence |
|---|-----|----------|--------|----------|
| 1 | No corner frequency model | Medium | Open | σ_1f = √(K·ln(f_high/f_low)) integrates over full band; should cap at f_c. Overestimate 64–170% at 30–120 Hz |
| 2 | No frame-rate-aware f_low | Low | Open | User must manually set `flicker_f_low_hz`; no `detector.frame_rate_hz` shortcut |
| 3 | No noise PSD output | Low | Open | Only integrated σ available — no `result.noise_psd(f)` method |
| 4 | Per-term NEDT breakdown missing | Medium | **CLOSED** | `result.metrics["nedt_K"]` exposes total; per-term via `σ_i / (dS/dT)` |
| 5 | **NEW — Nearfield emission = 0 in scalar transmission mode** | **HIGH** (cross-scenario) | Open | Scalar mode assumes refractive lump (ε = 1 − T − R = 0). Mirror self-emission from warm optics not captured. Low impact here because extended-scene signal_shot dominates, but high impact for cold-stop (7.4) and point-source scenarios. |

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

- 1/f noise is negligible in BLIP-limited LWIR NEDT (<1% penalty). Mike does not need to worry about 1/f for this spec.
- Logarithmic dependence on frame rate is real physics — a 4× frame rate change only shifts σ_1f by 15%.
- LWIR integration time is FWC-limited (100 µs), not frame-rate-limited.
