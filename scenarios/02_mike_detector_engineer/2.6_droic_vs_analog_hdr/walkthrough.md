# Scenario 2.6 Walkthrough: DROIC vs Analog ROIC — Single-Frame HDR

## Persona
Mike, detector engineer. Scenario 2.5 ended at a physical wall: his 200–1500 K
scene (cold sky to jet exhaust) cannot fit through a 2 Me- analog charge well
at *any* integration time — 1000 K and 1500 K saturated even at 1 µs. A vendor
has offered a Senseeker-class digital-pixel ROIC (DROIC) for the same MWIR
HgCdTe FPA: in-pixel 16-bit counters with 4.5 ke- charge-subtraction packets
and analog residue readout. Mike wants to know what that buys him at his 1 ms
cold-target working point, before committing to the part.

## System Configuration (identical FPA + optics; only the ROIC differs)
| Parameter | Value | Unit |
|---|---|---|
| Aperture diameter | 20 | cm |
| Focal length (f/2) | 40 | cm |
| Spectral band | 3.5–5.0 | µm |
| Optical transmission | 80 | % |
| Quantum efficiency | 72 | % |
| Pixel pitch | 15 | µm |
| Dark current | 100 | e-/s |
| Integration time | 1.0 | ms |

| ROIC parameter | Analog | DROIC | Unit |
|---|---|---|---|
| Well / effective well | 2.0 M | 2¹⁶ × 4500 = 294.9 M | e- |
| Dead-time ceiling (5 MHz × 1 ms × 4500 e-) | — | 22.5 M | e- |
| Governing bound at 1 ms | charge well (2.0 Me-) | dead time (22.5 Me-) | — |
| ADC | 14 bit at 130 e-/DN | 14-bit residue ADC (0.275 e-/DN, full scale = 1 packet) | — |
| Read noise / counting-chain noise | 20 | 20 | e- RMS |

## Key Results (from `scripts/run_droic_vs_analog.py`)

| T_scene [K] | Analog fill [%] | Analog SNR [-] | Analog NEDT [mK] | DROIC fill [%] | DROIC SNR [-] | DROIC NEDT [mK] |
|---|---|---|---|---|---|---|
| 200 | 4.6 | 301.5 | 37.96 | 0.4 | 303.8 | 37.68 |
| 300 | 53.6 | 1034.1 | 26.98 | 4.8 | 1034.8 | 26.96 |
| 400 | **SAT** (733.0) | 1413.6 (clipped) | 34.56* | 65.2 | 3828.9 | 12.76 |
| 500 | **SAT** | 1413.6 (clipped) | 53.13* | **SAT** (dead_time) | 4743.4 (clipped) | 15.83* |
| 1500 | **SAT** | 1413.6 (clipped) | 412.57* | **SAT** (dead_time) | 4743.4 (clipped) | 122.95* |

\* NEDT on a saturated (clipped) signal is not a usable sensitivity number —
the chain warns and `readout.well_status = "clipped"` flags these rows.

Dynamic range at the matched 200 K point: **76.3 dB analog → 97.4 dB DROIC**
(+21.1 dB), with the DROIC bound set by the dead-time ceiling (22.5 Me-), not
the counter (294.9 Me-).

## Key Observations

1. **Where the analog well saturates (400 K), the DROIC keeps measuring.**
   Same photocurrent, same FPA — at 400 K the analog chain reports a clipped
   SNR of 1413.6 [-] while the DROIC delivers 3828.9 [-] at 65.2 % fill and a
   2.7× better NEDT (12.76 mK vs 34.56 mK on a clipped signal).
2. **In the unsaturated overlap (200–300 K) the two ROICs are equivalent.**
   SNR agrees within 0.8 % and NEDT within 0.3 mK: with residue readout the
   DROIC quantization floor (0.079 e- RMS) is even slightly below the analog
   130 e-/DN ADC's (37.5 e- RMS), and both are dominated by shot + read noise.
   This is the plan §7 cross-model consistency check, visible in a workflow.
3. **The dead-time ceiling is the DROIC's real limit, not the counter.**
   At 1 ms, 5 MHz × 4500 e- caps the pixel at 22.5 Me- — 7.6 % of the
   294.9 Me- counter capacity. Above ~450 K the DROIC also clips
   (`saturation_mechanism = "dead_time"`). Shortening t_int raises the flux
   ceiling proportionally less than it helps the analog well, because the
   ceiling scales with t_int while the well does not.
4. **The 2.5 requirement is still not met end-to-end — but the wall moved.**
   200→400 K now fits in one frame (analog: 200→300 K). Covering 1500 K needs
   a faster comparator (f_max ≳ 90 MHz), a larger packet, or the Phase 4
   up/down mode operating point discussion.

## Reproduce

```bash
cd scenarios/02_mike_detector_engineer/2.6_droic_vs_analog_hdr/scripts
python run_droic_vs_analog.py
```

Regenerates `outputs/droic_vs_analog_results.csv` and the table above.
