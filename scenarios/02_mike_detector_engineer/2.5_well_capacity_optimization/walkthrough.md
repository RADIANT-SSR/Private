# Scenario 2.5 Walkthrough: Well Capacity Optimization — Integration Time vs. Dynamic Range

## Persona
Mike, detector engineer. He has a MWIR HgCdTe FPA (640x512, 15 µm pitch, 2M e- FWC) in an f/2 ground-based surveillance system. The scene contains both cold sky (200 K) and hot jet exhaust plumes (1500 K). He needs to find the integration time that gives adequate SNR on cold targets without saturating on hot targets.

## System Configuration
| Parameter | Value | Unit |
|---|---|---|
| Detector format | 640x512 | pixels |
| Pixel pitch | 15 | µm |
| Spectral band | 3.5–5.0 | µm |
| Aperture diameter | 20 | cm |
| Focal length | 40 | cm |
| f-number | 2.0 | — |
| Optical transmission | 80 | % |
| Optics temperature | 20 | °C |
| Quantum efficiency | 72 | % |
| Dark current | 100 | e-/s |
| Read noise | 20 | e- RMS |
| Full well capacity | 2.0 M | e- |
| ADC resolution | 14 | bits |
| System gain | 130 | e-/DN |

## Trade Study Design
- **Sweep**: 50 integration times, log-spaced from 1 µs to 50 ms
- **Scene temperatures**: 200, 250, 280, 300, 350, 400, 500, 700, 1000, 1500 K
- **Requirements**: SNR ≥ 10 on 200 K cold target, max 70% well fill on hot targets, absolute saturation limit 90%
- **Total evaluations**: 500 (10 temperatures × 50 integration times)
- **Atmosphere**: `exo` (short-range ground-based, no atmospheric path)

## Key Results

### Well Fill vs. Integration Time (selected temperatures)
| t_int | 200 K | 300 K | 400 K | 500 K | 1000 K | 1500 K |
|---|---|---|---|---|---|---|
| 1 µs | 0.0% | 0.1% | 0.8% | 4.0% | SAT | SAT |
| 14.2 µs | 0.0% | 0.7% | 10.9% | 56.5% | SAT | SAT |
| 82.8 µs | 0.0% | 4.3% | 63.5% | SAT | SAT | SAT |
| 484.3 µs | 0.1% | 25.1% | SAT | SAT | SAT | SAT |
| 2.83 ms | 0.8% | SAT | SAT | SAT | SAT | SAT |
| 40.09 ms | 11.0% | SAT | SAT | SAT | SAT | SAT |

**Key observation**: 1000 K and 1500 K saturate even at the shortest integration time (1 µs). These temperatures produce so much MWIR flux that no practical integration time avoids saturation with a 2M e- well.

### SNR vs. Integration Time for Cold Target (200 K)
| t_int | Signal [e-] | Well Fill [%] | SNR [—] | Status |
|---|---|---|---|---|
| 1 µs | 5 | 0.0% | 0.1 | FAIL |
| 82.8 µs | 453 | 0.0% | 9.5 | FAIL |
| **103.2 µs** | **565** | **0.0%** | **11.6** | **PASS** ← |
| 200.2 µs | 1,096 | 0.1% | 20.3 | PASS |
| 1.17 ms | 6,415 | 0.3% | 70.7 | PASS |
| 2.83 ms | 15,516 | 0.8% | 117.9 | PASS |
| 40.09 ms | 219,550 | 11.0% | 466.6 | PASS |

**Result**: SNR ≥ 10 on the cold target requires t_int ≥ 103.2 µs.

*Numbers refreshed 2026-08-02 from the unmodified runner (previous vintage 2026-04-19). Dominant mover: the extended-regime consolidation of the separate `background_shot` photon term into `signal_shot` (ADR-0002 Decision #13) — the 696 e⁻ RMS background term the old noise budget carried no longer exists as a distinct contributor, which drops total noise at 200 K / 1 ms from ~700 e⁻ to 85.3 e⁻ and raises every cold-target SNR by roughly the same factor. This landing **predates the CU-317 attribution window** (the dated Results-affecting table begins 2026-07-16, the doc vintage is 2026-04-19), so it is named from the runner's own regime output rather than from that table. No in-window landing applies: the bench is `atmosphere.model = "exo"`, so CU-224 (down-looking `simple` path radiance), CU-267 (`simple` gas-region blend) and CU-253 (VIS/NIR Rayleigh) all exclude it by their own scope statements.*

### Dynamic Range Trade-Off
At 103.2 µs (the minimum t_int for cold-target detection), the maximum scene temperature that stays below 90% well fill is 400 K. At 1 ms it has fallen to 300 K — barely above ambient. The 200–1500 K dynamic range is **physically impossible** in a single integration.

### Integration Time for 70% Well Fill
| Scene Temp [K] | t_int for 70% fill | SNR at that t_int [—] |
|---|---|---|
| 200 | ~256 ms (extrapolated) | — |
| 280 | 3.53 ms | 1307.6 |
| 400 | 103 µs | 1257.7 |
| 700 | 3.0 µs | 1284.4 |
| 1000 | 1.0 µs | 1413.6 (saturated) |
| 1500 | 1.0 µs | 1413.6 (saturated) |

The 200 K target never reaches 70% well fill within the sweep range — it would need ~256 ms. Meanwhile 1000 K and 1500 K are already saturated at 1 µs.

### Noise Budget Comparison at 1 ms
| Noise Term | 200 K [e- RMS] | 200 K Fraction | 400 K [e- RMS] | 400 K Fraction |
|---|---|---|---|---|
| signal_shot | 74.0 | 75.2% | 1414.2 | 99.9% |
| quantization | 37.5 | 19.3% | 37.5 | 0.1% |
| read_noise | 20.0 | 5.5% | 20.0 | 0.0% |
| dark_shot | 0.3 | 0.0% | 0.3 | 0.0% |
| nearfield_shot | 0.0 | 0.0% | 0.0 | 0.0% |
| **RSS TOTAL** | **85.3** | **100.0%** | **1414.9** | **100.0%** |

Signal at 1 ms is 5,476 e⁻ (0.3% well, SNR 64.2) for the 200 K target and 2,000,000 e⁻ (100.0% well — clipped, SNR 1413.6) for the 400 K target.

**Regime transition**: There is **no separate `background_shot` term** — in the extended regime the scene is one radiance field, so the whole-FOV photon shot noise is carried by `signal_shot` alone (ADR-0002 Decision #13). Both targets are therefore nominally signal-shot-limited, but the *degree* differs sharply: at 200 K, `signal_shot` is 75.2% of the noise variance and the ROIC floor is still material — quantization (19.3%) plus read noise (5.5%) make up a quarter of the budget. At 400 K, `signal_shot` is 99.9% and the electronics are irrelevant. The cold end is where ROIC choices show up.

**Note**: `nearfield_shot = 0` is a known scalar-mode limitation (Gap 7 below). Mirror self-emission from warm optics (293 K, 4 elements) should be a real contributor but is not modeled in scalar transmission mode. This means RADIANT under-predicts noise for cold targets in warm-optics MWIR systems.

This is physically correct: at 200 K in MWIR, the target emits very little compared to the 280 K background and 293 K warm optics. At 400 K, the target outshines the background.

## Physics Discussion

### Why the Dynamic Range is Impossible
A 1500 K blackbody radiates ~389× more MWIR power than a 200 K target. With a 2M e- well, there is no single integration time where the cold target generates ≥10 SNR while the hot target stays below saturation. This is a fundamental radiometric constraint, not a RADIANT limitation.

### Why Background Dominates for Cold Targets
In the MWIR band (3.5–5.0 µm), room-temperature objects (280–293 K) emit substantially. The background (280 K) and warm optics (293 K, 4 optical elements) together produce far more photons than a 200 K target. This is why MWIR systems need cold shields (to block off-axis warm radiation). Note that RADIANT does not surface that warm flux as a separate noise line here: in the extended regime the whole-FOV radiance is carried by `signal_shot` (Decision #13), and the warm-optics contribution is missing entirely because scalar transmission mode sets `nearfield_shot = 0` (Gap 7). At 200 K / 1 ms the reported floor is therefore `signal_shot` 74.0 e⁻ plus a non-trivial ROIC contribution — quantization 37.5 e⁻ and read noise 20.0 e⁻ — for 85.3 e⁻ RMS total.

### Well Fill Physics
RADIANT tracks signal electrons and clips at FWC. In reality, the detector well accumulates signal + background + nearfield + dark current photons together. For hot targets (≥400 K), signal dominates the well. For cold targets, background and nearfield photons dominate, but the signal is still distinguishable because the noise is √(total electrons) while the target signal adds coherently.

### Unused Parameters
- **Dark current** (100 e-/s): negligible at all integration times in this sweep (max 5 e- at 50 ms). At 77 K operating temperature, dark current is irrelevant compared to photon noise.
- **Read noise** (20 e- RMS): irrelevant on hot targets (0.0% of the 400 K noise variance at 1 ms) but *not* negligible on cold ones — 5.5% of the 200 K variance at 1 ms, where the 85.3 e⁻ RMS total is only ~4× the read noise. It dominates further down the sweep, at the shortest integrations.
- **IPC coupling** (1%): slightly broadens the PSF, but this is an extended-scene scenario where IPC does not affect photometry.

## Gap Findings

See [gaps.md](gaps.md) for full detail with severity and status.

### Gap Closure Since Last Run
| Gap | Status | Notes |
|-----|--------|-------|
| Well margin / saturation flags | **CLOSED** | `result.metrics["well_margin_dB"]` and `result.metrics["dynamic_range_dB"]` now exposed |

### Open Gaps

- **Gap 1 (No HDR / dual-integration mode)**: still open.
- **Gap 2 (Well fill excludes background/nearfield)**: still open. RADIANT clips only signal_e at FWC; for cold targets at long t_int, background alone could saturate.
- **Gap 3 (No saturation map)**: partially closed by `well_margin_dB`; no per-pixel map yet.
- **Gap 4 (No automatic trade study support)**: still open. 500 evaluations done manually.
- **Gap 5 (No NEDT-at-saturation warning)**: still open. NEDT goes to ∞ at FWC silently.
- **Gap 6 (No spectral narrowing analysis)**: still open.
- **Gap 7 (NEW — Nearfield = 0 in scalar transmission mode)**: HIGH severity. Mirror self-emission from warm optics (293 K, 4 elements) not modeled. Under-predicts noise for cold targets by ~30–40% in MWIR with warm optics.
