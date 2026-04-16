# Scenario 2.2 Walkthrough: 1/f Noise Corner Frequency Impact on LWIR Staring Array

## The Problem

Mike has a 640x512 LWIR HgCdTe staring array with known 1/f noise characteristics: flicker coefficient K = 2.5×10⁴ e⁻² and corner frequency f_c = 200 Hz. He operates the sensor at three frame rates (30, 60, 120 Hz) and wants to understand how 1/f noise impacts NEDT at each rate.

Mike's questions:
1. **How much does 1/f noise degrade NEDT at each frame rate?**
2. **How should RADIANT's flicker parameters (f_low, f_high) be set for each frame rate?**
3. **Is 1/f noise significant compared to the photon noise budget?**

## The Physics

### 1/f Noise Power Spectral Density

The 1/f (flicker) noise power spectral density has the form:

```
S(f) = K / f    [e⁻² / Hz]
```

where K is the flicker coefficient. This applies below the **corner frequency** f_c, where the 1/f spectrum meets the white noise floor (read noise). Above f_c, the PSD is flat.

### Integrating Over the Frequency Band

The total 1/f noise is the integral of the PSD over the relevant frequency band:

```
σ²_1f = ∫(f_low to f_high) K/f df = K · ln(f_high / f_low)
σ_1f  = √(K · ln(f_high / f_low))    [e⁻ RMS]
```

For a staring array:
- **f_low = frame rate** — the lowest temporal frequency in the frame stream
- **f_high = 1/(2·t_int)** — the Nyquist frequency within one integration period

### Frame Rate Controls f_low

At lower frame rates, f_low decreases, which increases ln(f_high/f_low) and therefore σ_1f:

| Frame Rate [Hz] | f_low [Hz] | f_high [Hz] | ln(f_high/f_low) | σ_1f [e⁻] |
|-----------------|-----------|-------------|-------------------|-----------|
| 30 | 30 | 5,000 | 5.12 | 357.6 |
| 60 | 60 | 5,000 | 4.42 | 332.5 |
| 120 | 120 | 5,000 | 3.73 | 305.4 |

The dependence is **logarithmic** — a 4× change in frame rate (30→120 Hz) only reduces σ_1f by 15%.

### Corner Frequency Subtlety

RADIANT integrates 1/f over the full [f_low, f_high] band, but physically the 1/f PSD only applies below f_c = 200 Hz. Above f_c, the noise is white and already captured as read noise. The physically correct integral would cap f_high at f_c:

```
σ_1f (capped) = √(K · ln(min(f_high, f_c) / f_low))
```

| Frame Rate | σ_1f (RADIANT) | σ_1f (capped at f_c) | Overestimate |
|-----------|---------------|---------------------|--------------|
| 30 Hz | 357.6 e⁻ | 217.8 e⁻ | 64% |
| 60 Hz | 332.5 e⁻ | 173.5 e⁻ | 92% |
| 120 Hz | 305.4 e⁻ | 113.0 e⁻ | 170% |

RADIANT overestimates σ_1f because it does not model the corner frequency transition. This is a gap.

## How RADIANT Solves This

### Step 1: System Configuration

This is an LWIR ground-based surveillance system:
- **Optics**: 15 cm Ge objective, f/2, 85% transmission, 20°C ambient
- **Spectral**: 8.0–10.0 µm (LWIR atmospheric window)
- **Detector**: 24 µm HgCdTe, QE = 55%, dark = 500,000 e⁻/s, read = 350 e⁻ RMS
- **FWC**: 20M e⁻ (large LWIR format)
- **Integration time**: 100 µs (FWC-limited — LWIR background fills the well quickly)

The atmosphere model is `"exo"` (short-range, negligible atmospheric path).

### Step 2: LWIR Background Dominance

LWIR systems are fundamentally different from MWIR. At 293 K (ambient), the Planck function peaks near 10 µm, so the thermal background is enormous:

- Signal (300 K target): 4,431,044 e⁻ (22.2% well)
- Background (295 K): 4,132,439 e⁻
- Nearfield (optics at 293 K): 726,467 e⁻
- **Total well charge: 9,289,950 e⁻ (46.4% of 20M FWC)**

Even at 100 µs integration, the well is nearly half full. This is why LWIR staring arrays need large FWC (20M+ e⁻) and short integrations.

### Step 3: NEDT With and Without 1/f

Running RADIANT at each frame rate with `flicker_K = 25000` and without:

| Frame Rate | NEDT (no 1/f) [mK] | NEDT (with 1/f) [mK] | Δ NEDT [mK] | Δ [%] |
|-----------|--------------------|--------------------|------------|-------|
| 30 Hz | 39.1 | 39.4 | 0.3 | 0.7% |
| 60 Hz | 39.1 | 39.3 | 0.2 | 0.6% |
| 120 Hz | 39.1 | 39.3 | 0.2 | 0.4% |

**1/f noise adds only 0.2–0.3 mK to NEDT** — less than 1% degradation. The reason: photon shot noise (signal + background + nearfield) completely dominates the noise budget in this BLIP-limited LWIR system.

### Step 4: Noise Breakdown at 60 Hz

| Noise Term | σ [e⁻ RMS] | NEDT_i [mK] | Fraction [%] |
|------------|-----------|-------------|-------------|
| signal_shot | 2,105.0 | 26.65 | 45.9 |
| background_shot | 2,032.8 | 25.74 | 42.8 |
| nearfield_shot | 852.3 | 10.79 | 7.5 |
| quantization | 352.2 | 4.46 | 1.3 |
| read_noise | 350.0 | 4.43 | 1.3 |
| **flicker_1f** | **332.5** | **4.21** | **1.1** |
| dark_shot | 7.1 | 0.09 | <0.1 |
| **RSS TOTAL** | **3,106.0** | **39.3** | **100.0** |

1/f noise (332.5 e⁻) is comparable to read noise (350.0 e⁻) and quantization noise (352.2 e⁻), but all three combined are dwarfed by the photon noise terms (signal_shot + background_shot + nearfield_shot = 3,087 e⁻ RSS). This is the definition of BLIP performance.

### Step 5: f_low Sweep

The analytic sweep of f_low from 1 Hz to 500 Hz shows the full sensitivity curve. NEDT ranges from 39.5 mK (at 1 Hz) to 39.2 mK (at 500 Hz) — a total variation of only 0.3 mK across the entire range. This confirms that 1/f noise is irrelevant for NEDT in this BLIP-limited system.

### Step 6: When 1/f WOULD Matter

1/f noise becomes significant when:
- **Read-noise-limited systems** (low signal, short integration) — where σ_1f is comparable to the dominant noise
- **Very low frame rates** (< 10 Hz) — where ln(f_high/f_low) grows significantly
- **Detectors with large K** (>10⁶ e⁻²) — some older InSb or microbolometer arrays
- **Long-wave systems with very cold backgrounds** — where photon noise is reduced

For Mike's LWIR system, none of these apply. The photon noise from the warm background is so large that 1/f noise is buried under it.

## Key Takeaways

1. **1/f noise is negligible for NEDT in BLIP-limited LWIR systems.** The 0.2 mK penalty (0.6%) at 60 Hz is well within measurement uncertainty. Mike does not need to worry about 1/f noise for NEDT specification.

2. **The logarithmic dependence is weak.** Going from 30 Hz to 120 Hz (4× frame rate) only reduces σ_1f by 15%. Frame rate has minimal impact on 1/f noise contribution.

3. **RADIANT overestimates 1/f by 64–170%** because it does not model the corner frequency cutoff. The flicker model integrates K/f over the full [f_low, f_high] band, even though physically the 1/f PSD transitions to white noise above f_c = 200 Hz.

4. **LWIR integration times are FWC-limited, not frame-rate-limited.** At f/2 with a 300 K scene in 8–10 µm, the well fills to 46% in just 100 µs. All three frame rates use the same 100 µs integration time because the well capacity — not the frame period — limits exposure.

5. **Background shot noise dominates.** Signal_shot and background_shot together account for 89% of the noise variance. The warm background (295 K) produces almost as much photon flux as the target (300 K) in the LWIR band.

## Gaps Identified

- **Gap 1 (No corner frequency model)**: RADIANT's `flicker_1f_noise()` computes `σ = √(K · ln(f_high / f_low))` over the full band. Physically, the 1/f PSD only applies below the corner frequency f_c. For f > f_c, noise is white and already captured as read noise. A corner-frequency-aware model would integrate K/f only up to min(f_high, f_c). This overestimates σ_1f by 64–170% for this system.

- **Gap 2 (No frame-rate-aware f_low calculator)**: Users must manually set `flicker_f_low_hz = frame_rate`. A `detector.frame_rate_hz` parameter that automatically sets f_low would reduce confusion. Mike's spreadsheet notes show he was confused about how f_low and f_high map to frame rate.

- **Gap 3 (No noise PSD output)**: Mike wants to plot the noise power spectral density S(f) showing the 1/f, white, and total contributions. RADIANT computes only the integrated σ, not the frequency-domain PSD. A `result.noise_psd(f_array)` method would enable this visualization.

- **Gap 4 (No NEDT breakdown by noise term)**: Same gap identified in scenario 7.1 — RADIANT provides total NEDT but not per-term NEDT_i = σ_i / (dS/dT). The script must compute this manually.
