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

- Signal (300 K target + background + nearfield, integrated in extended regime): 4,431,044 e⁻ (22.2% well fill)
- Integration time: 100 µs (FWC-limited)

Even at 100 µs integration, the well is ~22% full from a 300 K scene alone. This is why LWIR staring arrays need large FWC (2–20M e⁻) and short integrations. Note: `nearfield_shot = 0` in scalar transmission mode — mirror self-emission is not modeled (see Gap 5).

### Step 3: NEDT With and Without 1/f

Running RADIANT at each frame rate with `flicker_K = 25000` and without:

| Frame Rate | NEDT (no 1/f) [mK] | NEDT (with 1/f) [mK] | Δ NEDT [mK] | Δ [%] |
|-----------|--------------------|--------------------|------------|-------|
| 30 Hz | 37.6 | 37.9 | 0.3 | 0.8% |
| 60 Hz | 37.6 | 37.8 | 0.2 | 0.6% |
| 120 Hz | 37.6 | 37.8 | 0.2 | 0.5% |

**1/f noise adds only 0.2–0.3 mK to NEDT** — less than 1% degradation. The reason: photon shot noise (signal + background + nearfield) completely dominates the noise budget in this BLIP-limited LWIR system.

### Step 4: Noise Breakdown at 60 Hz

| Noise Term | σ [e⁻ RMS] | NEDT_i [mK] | Fraction [%] |
|------------|-----------|-------------|-------------|
| signal_shot | 2,105.0 | 26.65 | 49.7 |
| background_shot | 2,032.8 | 25.74 | 46.3 |
| quantization | 352.2 | 4.46 | 1.4 |
| read_noise | 350.0 | 4.43 | 1.4 |
| **flicker_1f** | **332.5** | **4.21** | **1.2** |
| dark_shot | 7.1 | 0.09 | <0.1 |
| nearfield_shot | 0.0 | 0.00 | 0.0 |
| **RSS TOTAL** | **2,986.7** | **37.81** | **100.0** |

1/f noise (332.5 e⁻) is comparable to read noise (350.0 e⁻) and quantization noise (352.2 e⁻), but all three combined are dwarfed by the photon noise terms (signal_shot + background_shot = 2,927 e⁻ RSS). This is the definition of BLIP performance. Note: `nearfield_shot = 0` due to scalar-mode refractive-lump assumption (see Gap 5 — the full background is already captured in the extended regime's signal_shot since the scene fills the FOV).

### Step 5: f_low Sweep

The analytic sweep of f_low from 1 Hz to 500 Hz shows the full sensitivity curve. NEDT ranges from 38.03 mK (at 1 Hz) to 37.70 mK (at 500 Hz) — a total variation of only 0.33 mK across the entire range. This confirms that 1/f noise is irrelevant for NEDT in this BLIP-limited system.

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

5. **Background shot noise dominates.** Signal_shot and background_shot together account for 96% of the noise variance. The warm background (295 K) produces almost as much photon flux as the target (300 K) in the LWIR band.

## Gaps Identified

See [gaps.md](gaps.md) for full detail.

### Gap Closure Since Last Run
| Gap | Status | Notes |
|-----|--------|-------|
| Gap 4 (per-term NEDT breakdown) | **CLOSED** | `result.metrics["nedt_K"]` and per-term `σ_i / (dS/dT)` both computed |

### Open Gaps
- **Gap 1 (No corner frequency model)**: still open. RADIANT overestimates σ_1f by 64–170% for this system.
- **Gap 2 (No frame-rate-aware f_low calculator)**: still open. User must manually set `flicker_f_low_hz = frame_rate`.
- **Gap 3 (No noise PSD output)**: still open. Only integrated σ available.
- **Gap 5 (NEW — Nearfield = 0 in scalar mode)**: HIGH severity. Mirror self-emission from warm LWIR optics not modeled — but since signal_shot already includes the full scene in extended regime here, real-world impact on NEDT is small for this particular scenario.
