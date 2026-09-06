# Scenario 2.7 Walkthrough: Up/Down Counting — In-Pixel Background Subtraction

## Persona
Mike, detector engineer. His DROIC vendor's part supports an up/down mode:
the in-pixel counter increments during the scene phase and decrements during
a reference phase, subtracting the background pedestal before readout. The
driving use case (plan §2.4): a **dim point-source target over a bright
common background**, where plain up-counting spends the counter range on the
pedestal. Mike wants the trade quantified: what does up/down buy, and what
does it cost?

## System Configuration
| Parameter | Value | Unit |
|---|---|---|
| Aperture / focal length (f/2) | 15 / 30 | cm |
| Spectral band | 3.5–5.0 | µm |
| Target | 500 K, ε 0.9, 0.001 m² at 10 km | — |
| Background (swept) | 250–330 K, ε 0.95 | K |
| Sensor altitude / atmosphere | 8 km, mid-lat summer | — |
| Integration (up = down phase, ruling D7) | 50 | ms |
| DROIC counter | 14 bit × 2000 e-/count | — |
| `up` bound: 2¹⁴ × 2000 e- | 32.77 M | e- |
| `up_down` bound (signed): 2¹³ × 2000 e- | 16.38 M | e- |
| Counting-chain noise (per phase) | 5 | e- RMS |

Target charge over the up phase ≈ 4.86 Me- (29.6 % of the signed capacity);
the background pedestal grows from ~15.9 Me- (250 K) to ~88.9 Me- (330 K).

## Key Results (from `scripts/run_updown_trade.py`)

| T_bg [K] | `up` fill [%] | `up` SNR [-] | `up_down` fill [%] | `up_down` SNR [-] |
|---|---|---|---|---|
| 250 | 63.2 | 1066.0 | 29.6 | 802.2 |
| 270 | 79.7 | 949.6 | 29.6 | 705.1 |
| 290 | **SAT** (113.6) | 67.6* | 29.6 | 581.6 |
| 310 | **SAT** (177.0) | 0.0* | 29.6 | 460.3 |
| 330 | **SAT** (286.0) | 0.0* | 29.6 | 359.2 |

\* clipped-signal SNR — the chain warns and flags `well_status = "clipped"`.

## Key Observations

1. **The wall moves from the pedestal to the differential.** `up` counting
   saturates at ~290 K background (pedestal + target > 32.77 Me-) and the
   target SNR collapses. `up_down` fill is background-independent — 29.6 %
   at every swept temperature, because only |Q_up − Q_down| ≈ the 4.86 Me-
   target counts against the signed 16.38 Me- capacity.
2. **The price is the √2 reference penalty, and it is visible.** At 250 K,
   where both modes are clean, `up_down` SNR is 802.2 vs 1066.0 — ratio
   0.75, between 1 (no penalty) and 1/√2 = 0.707 because the target's own
   shot noise (2203 e- RMS) doesn't double, only the background terms do
   (`reference_shot` = √Q_down = 3984 e- RMS at 250 K enters in quadrature).
3. **Above the crossover the comparison inverts decisively:** at 290 K,
   581.6 (`up_down`, clean) vs 67.6 (`up`, clipped) — an 8.6× usable-SNR
   advantage that grows unbounded as `up` saturates harder.
4. **Noise budget is honest about both phases:** `reference_shot` is the top
   term for `up_down` at every temperature, the counting-chain read is paid
   ×√2, and `packet_reset` accrues over the trips of both phases. Any model
   that cancels the mean without paying the reference noise would overstate
   the mode by up to √2 — forbidden by plan §2.4.

## Reproduce

```bash
cd scenarios/02_mike_detector_engineer/2.7_updown_background_subtraction/scripts
python run_updown_trade.py
```

Regenerates `outputs/updown_trade_results.csv` and the table above.
