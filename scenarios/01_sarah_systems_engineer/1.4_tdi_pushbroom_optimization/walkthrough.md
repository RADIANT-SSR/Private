# Scenario 1.4 Walkthrough: TDI Pushbroom Optimization — Line Rate vs. SNR

## Persona
Sarah, systems engineer. She is designing a VNIR panchromatic pushbroom imager (25 cm aperture, f/10, 7 um Si CCD) for a 500 km SSO. Ground velocity constrains the per-line integration time to ~0.2 ms. She needs TDI to build sufficient SNR and must find the optimal N_tdi.

## Why VNIR, Not MWIR
The original concept specified MWIR. However, MWIR thermal scenes (300+ K) generate so many photons per pixel per line (~250,000 e- for a 30 cm aperture at 1 ms integration) that the well saturates at N_tdi=1. Adding TDI stages only grows noise while signal is clipped at FWC — NIIRS degrades monotonically. TDI is primarily a VNIR technology where reflected solar provides orders of magnitude less signal per pixel, making TDI essential for pushbroom operation.

## System Configuration
| Parameter | Value | Unit |
|---|---|---|
| Aperture diameter | 25 | cm |
| Focal length | 250 | cm |
| f-number | 10.0 | -- |
| Optical transmission | 70 | % |
| Optics temperature | 20 | C |
| WFE RMS | 0.05 | waves |
| Central obscuration | 30 | % |
| Pixel pitch | 7.0 | um |
| QE | 80 | % |
| Dark current | 5.0 | e-/s |
| Read noise | 15.0 | e- RMS |
| FWC | 60,000 | e- |
| Band | 500--850 | nm |
| Orbit altitude | 500 | km |
| Target reflectance | 0.15 | -- |
| Background reflectance | 0.10 | -- |
| Solar zenith angle | 30 | deg |
| GSD | 1.40 | m |
| Q (sampling) | 0.964 | -- (undersampled) |
| IFOV | 2.8 | urad |
| TDI mode | analog | -- |
| TDI misalignment | 0.1 | pixels/stage |

## Derived Orbital Parameters
| Parameter | Value | Unit | Derivation |
|---|---|---|---|
| Ground velocity | 6954.2 | m/s | v_orb x R_E/(R_E+h) |
| Line period | 0.2013 | ms | GSD / v_ground |
| Smear MTF@Nyquist | 0.6366 | -- | sinc(pi/2) = 2/pi (constant) |
| Airy disk | 16.5 | um (2.35 pixels) | 2.44 x lambda x f/# |

## Approach
The script runs the full RADIANT signal chain at each N_tdi value using the built-in readout stage TDI handling. The `readout.n_tdi` parameter drives signal scaling (xN), noise scaling (shot x sqrt(N), read x1 for analog TDI), and well saturation checking. Integration time per line is derived from orbital mechanics.

Smear MTF (1 pixel/line motion during each TDI stage) and TDI misalignment MTF are computed analytically and applied as corrections to the RADIANT system MTF. These are not yet wired into the chain (see gaps).

## Trade Study Design
- **N_tdi sweep**: 1, 2, 4, 8, 16, 32, 64, 96, 128
- **Total evaluations**: 9 full RADIANT chain evaluations
- **Key trade**: SNR improvement vs. well saturation
- **Secondary trade**: TDI misalignment MTF degradation

## Key Results

### TDI Sweep
| N_tdi | Signal [e-] | Well Fill [%] | SNR [--] | MTF@Nyq [--] | RER [--] | NIIRS [--] | Status |
|---|---|---|---|---|---|---|---|
| 1 | 3,118 | 5.2 | 38.8 | 0.3115 | 0.5656 | 5.10 | OK |
| 2 | 6,236 | 10.4 | 55.3 | 0.3115 | 0.5656 | 5.34 | OK |
| 4 | 12,473 | 20.8 | 78.6 | 0.3115 | 0.5656 | 5.58 | OK |
| 8 | 24,945 | 41.6 | 111.4 | 0.3115 | 0.5656 | 5.81 | OK |
| 16 | 49,891 | 83.2 | 157.8 | 0.3115 | 0.5656 | 6.05 | NEAR-SAT |
| 32 | 60,000 | 100.0 | 150.0 | 0.3115 | 0.5656 | 6.02 | SATURATED |
| 64 | 60,000 | 100.0 | 117.7 | 0.3115 | 0.5656 | 5.85 | SATURATED |
| 96 | 60,000 | 100.0 | 100.1 | 0.3115 | 0.5656 | 5.74 | SATURATED |
| 128 | 60,000 | 100.0 | 88.5 | 0.3115 | 0.5656 | 5.66 | SATURATED |

### Optimal N_tdi
- **Peak NIIRS**: 6.05 at N_tdi = 16 (83% well fill, just below saturation)
- **Conservative choice**: N_tdi = 8 (NIIRS = 5.81, 42% well fill, 80% margin)
- **Saturation onset**: N_tdi = 32 (signal clipped at FWC = 60,000 e-)

### SNR Scaling
| N_tdi | SNR [--] | SNR/SNR_1 | sqrt(N) | Regime |
|---|---|---|---|---|
| 1 | 38.8 | 1.00 | 1.00 | baseline |
| 2 | 55.3 | 1.43 | 1.41 | shot-limited |
| 4 | 78.6 | 2.03 | 2.00 | shot-limited |
| 8 | 111.4 | 2.87 | 2.83 | shot-limited |
| 16 | 157.8 | 4.07 | 4.00 | shot-limited |
| 32 | 150.0 | 3.87 | 5.66 | saturated |

Below saturation, SNR scales as exactly sqrt(N_tdi). This confirms the system is photon-shot-noise-limited (read noise = 15 e- is negligible compared to signal shot = 55-223 e-). Past saturation, signal is capped at FWC while background noise continues to grow, so SNR DECREASES.

### Noise Budget
| Noise Term | N=1 [e-] | N=8 [e-] | N=16 [e-] | N=32 [e-] | N=128 [e-] |
|---|---|---|---|---|---|
| signal_shot | 55.8 | 157.9 | 223.4 | 244.9 | 244.9 |
| background_shot | 55.8 | 157.9 | 223.4 | 315.9 | 631.8 |
| read_noise | 15.0 | 15.0 | 15.0 | 15.0 | 15.0 |
| TOTAL (RSS) | 80.4 | 223.9 | 316.2 | 400.0 | 677.8 |

Signal and background shot noise dominate equally, both scaling as sqrt(N). Read noise is constant at 15 e- (analog TDI advantage). Past saturation, signal_shot is capped (sqrt of clipped signal) but background_shot continues growing — this is why SNR degrades.

### MTF Budget
| N_tdi | MTF_opt [--] | MTF_smear [--] | MTF_misalign [--] | MTF_sys [--] | Misalign [pix] |
|---|---|---|---|---|---|
| 1 | 0.3115 | 0.6366 | 0.9959 | 0.1975 | 0.10 |
| 8 | 0.3115 | 0.6366 | 0.9674 | 0.1918 | 0.28 |
| 16 | 0.3115 | 0.6366 | 0.9355 | 0.1855 | 0.40 |
| 32 | 0.3115 | 0.6366 | 0.8735 | 0.1732 | 0.57 |
| 64 | 0.3115 | 0.6366 | 0.7568 | 0.1501 | 0.80 |
| 128 | 0.3115 | 0.6366 | 0.5508 | 0.1092 | 1.13 |

- **MTF_opt** (optics + detector + aberrations) is constant — does not depend on N_tdi
- **MTF_smear** = 2/pi = 0.6366 (1 pixel/line motion, constant for all N_tdi)
- **MTF_misalign** degrades as sqrt(N_tdi) accumulated registration error
- At N_tdi=128, misalignment is 1.13 pixels, dropping MTF_misalign to 0.55

## Physics Discussion

### Why TDI Works
In pushbroom imaging, the detector array scans across the ground as the satellite moves. Each detector row sees the same ground patch for one line period. TDI shifts the charge synchronously with the image motion, accumulating signal from N consecutive rows:

- Signal: S_total = N x S_per_line (linear accumulation)
- Shot noise: sigma_total = sqrt(N) x sigma_per_line (independent Poisson)
- Read noise (analog TDI): sigma_read = constant (single readout after all stages)
- **SNR improvement**: sqrt(N) for shot-limited systems

The analog TDI advantage is that read noise is injected only once, at the end of the charge accumulation. Digital TDI reads each stage independently, so read noise grows as sqrt(N) — less favorable but allows individual stage correction.

### The Saturation Cliff
When accumulated signal exceeds FWC, the charge is clipped. No additional TDI stages can add signal, but noise continues to grow:
- Background shot: always grows as sqrt(N) because background photons keep arriving
- Signal shot: capped at sqrt(FWC) since signal is clipped
- Net effect: SNR = FWC / sqrt(FWC + N x bg_per_line + ...) → SNR decreases

This creates a sharp NIIRS peak just below the saturation threshold. For this system:
- Signal per line: 3,118 e-
- FWC: 60,000 e-
- Theoretical max N_tdi: 60,000 / 3,118 = 19.2
- Optimal N_tdi: 16 (just below saturation)

### Smear MTF: Why It's Constant
During each line period, the ground image moves by exactly 1 pixel (by design — the line rate is matched to the ground velocity). This produces a rect function blur of width = 1 pixel, giving:

MTF_smear(f_Nyq) = |sinc(pi/2)| = 2/pi = 0.6366

This smear is INHERENT to pushbroom operation and is the SAME for all N_tdi values. The charge follows the image motion across TDI stages, so TDI does not add smear. The only variable spatial degradation with N_tdi is misalignment.

### TDI Misalignment
Cross-track registration error between TDI stages produces a sinc MTF degradation. For random per-stage misalignment delta:
- Total misalignment: delta_total = delta x sqrt(N_tdi)
- MTF: |sinc(pi x f x delta_total)|

At delta = 0.1 pixel/stage:
- N_tdi=16: 0.4 pixel total → MTF_misalign = 0.94 (minor)
- N_tdi=64: 0.8 pixel total → MTF_misalign = 0.76 (significant)
- N_tdi=128: 1.13 pixel total → MTF_misalign = 0.55 (severe)

### Why NIIRS Doesn't Benefit from MTF Corrections
In this scenario, NIIRS changes come entirely from the SNR term in GIQE-5 (1.559 x log10(SNR)). The RER term (3.32 x log10(RER)) is constant because RADIANT's ePSF does not include smear or TDI misalignment. Including these corrections would shift the absolute NIIRS values but would not change the location of the optimal N_tdi (which is determined by the saturation cliff).

## Gap Findings

### Gap 1: Smear MTF Not in Chain
Platform motion smear functions exist (`platform/smear.py`) but are not wired into PlatformStage. The smear MTF and kernel are computed analytically in the script instead of through the chain. This means RADIANT's system MTF, RER, and NIIRS do not include motion smear.

### Gap 2: No Orbital Velocity to Line Period Calculator
The script manually computes ground velocity from orbital velocity and derives line period from GSD. RADIANT should have a built-in velocity/timing module that computes these from orbital elements.

### Gap 3: No Automatic Saturation Warning in Sweep
When sweeping N_tdi, RADIANT clips the signal at FWC but does not emit a warning. A built-in well-fill diagnostic would help users identify the saturation threshold without manual inspection.

### Gap 4: TDI Misalignment Not in Chain
TDI misalignment MTF functions exist (`readout/tdi.py`) but are not applied in the chain. The misalignment kernel should be convolved into the ePSF by ReadoutStage or a dedicated step.

### Gap 5: No Effective Integration Time Output
For TDI pushbroom, the effective integration time is N_tdi x line_period. RADIANT outputs signal but does not report the effective integration time, making it harder for users to cross-check timing constraints.
