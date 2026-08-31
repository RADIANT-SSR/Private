# Scenario 1.4 Walkthrough: TDI Pushbroom Optimization — Line Rate vs. SNR


> **NIIRS applicability — engine update (CU-166).** Since this walkthrough was written, RADIANT added a metric-applicability gate: when one or more GIQE-5 inputs fall outside the calibration envelope — GSD 1.18–31.5 inch, RER 0.20–0.95, SNR 2–130 — the engine reports **NIIRS as N/A** by default instead of silently extrapolating. This configuration is outside that envelope, so the NIIRS values below are the **extrapolated** GIQE-5-form output: reproduce them with `performance.niirs.allow_extrapolated = true` and read them as a *relative trend, not a calibrated rating*. (The SNR/NEDT figures here predate later physics updates and are indicative; a full numeric refresh is tracked separately in the cleanup backlog. No IR-calibrated IIRS model yet — see `docs/tracking/gaps.md` Gap 100.)

## Persona
Sarah, systems engineer. She is designing a VNIR panchromatic pushbroom imager (25 cm aperture, f/10, 7 um Si CCD) for a 500 km SSO. Ground velocity constrains the per-line integration time to ~0.2 ms. She needs TDI to build sufficient SNR and must find the optimal N_tdi.

## Why VNIR, Not MWIR
The original concept specified MWIR. However, MWIR thermal scenes (300+ K) generate so many photons per pixel per line (~250,000 e- for a 30 cm aperture at 1 ms integration) that the well saturates at N_tdi=1. Adding TDI stages then buys nothing — the signal is already clipped at FWC, so NIIRS cannot improve. TDI is primarily a VNIR technology where reflected solar provides orders of magnitude less signal per pixel, making TDI essential for pushbroom operation.

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

*Numbers refreshed 2026-08-30 from the unmodified runner (previous vintage
2026-08-02). Sole mover: **CU-335**, the VIS/NIR re-fit of the calibrated
gas-band table. CU-161 had fitted the 0.45–0.70 and 0.70–1.30 µm well-mixed
floors against a Rayleigh optical depth ~8× too large, so both clamped to zero;
CU-253 corrected Rayleigh in 2026-07 and the fit was never re-run. Putting
`floor_od` = 0.1597 / 0.0517 back on those two rows takes band-mean τ on this
500–850 nm scene down ~11 %, and the per-line signal falls with it,
1,584 → 671 e⁻ (−58 %) — much more than τ alone, because the scattered-sky
irradiance illuminating the scene is attenuated on the solar leg as well as the
view leg. **SNR falls ~40 % at every unsaturated sweep point** (N_tdi = 1:
37.2 → 22.4) and the saturation knee moves out one further sweep point, from
N_tdi = 64 to 96. The MTF and RER columns are optics-and-motion only and are
bit-identical. The design recommendation moves with the knee (see below); the
scenario's physics conclusion — analog TDI is √N shot-limited until the well
clips, then plateaus — is unchanged.*

*Prior vintage, for the trend: the 2026-08-02 refresh was dominated by CU-253
itself (N_tdi = 1 SNR 52.3 → 37.2, knee 32 → 64).*

| N_tdi | Signal [e-] | Well Fill [%] | SNR [--] | MTF@Nyq [--] | RER [--] | NIIRS [--] | Status |
|---|---|---|---|---|---|---|---|
| 1 | 671 | 1.1 | 22.4 | 0.1962 | 0.4884 | 4.52 | OK |
| 2 | 1,341 | 2.2 | 33.9 | 0.1962 | 0.4884 | 4.80 | OK |
| 4 | 2,683 | 4.5 | 49.7 | 0.1962 | 0.4884 | 5.06 | OK |
| 8 | 5,366 | 8.9 | 71.8 | 0.1962 | 0.4884 | 5.30 | OK |
| 16 | 10,731 | 17.9 | 102.5 | 0.1962 | 0.4884 | 5.55 | OK |
| 32 | 21,462 | 35.8 | 145.7 | 0.1962 | 0.4884 | 5.78 | OK |
| 64 | 42,924 | 71.5 | 206.6 | 0.1962 | 0.4884 | 6.02 | OK |
| 96 | 60,000 | 100.0 | 244.5 | 0.1962 | 0.4884 | 6.13 | NEAR-SAT |
| 128 | 60,000 | 100.0 | 244.5 | 0.1962 | 0.4884 | 6.13 | NEAR-SAT |

### Optimal N_tdi
- **Peak NIIRS**: 6.13, reached at N_tdi = 96 and held (plateau) for all higher stages.
- **Conservative choice**: N_tdi = 16 (NIIRS = 5.55, 18% well fill, comfortable margin).
- **Sweet spot**: N_tdi = 32 (NIIRS = 5.78, 36% well fill) — within 0.35 NIIRS of the
  plateau with substantial saturation margin.
- **Saturation onset**: N_tdi = 96 (signal first clips at FWC = 60,000 e-); N_tdi = 64
  runs at 71.5% well fill.

Because this is an extended reflective scene, the background photon term is not a
separate noise source (ADR-0002 Decision #13): the pixel sees one radiance field, so
its shot noise is `signal_shot` alone. Once the signal clips at full well, the noise
stops growing too, so **SNR and NIIRS plateau at saturation rather than degrading** —
there is no sharp peak to sit below.

### SNR Scaling
| N_tdi | SNR [--] | SNR/SNR_1 | sqrt(N) | Regime |
|---|---|---|---|---|
| 1 | 22.4 | 1.00 | 1.00 | baseline |
| 2 | 33.9 | 1.51 | 1.41 | mixed |
| 4 | 49.7 | 2.22 | 2.00 | mixed |
| 8 | 71.8 | 3.20 | 2.83 | mixed |
| 16 | 102.5 | 4.58 | 4.00 | shot-limited |
| 32 | 145.7 | 6.50 | 5.66 | shot-limited |
| 64 | 206.6 | 9.22 | 8.00 | shot-limited |
| 96–128 | 244.5 | 10.91 | — | saturated (plateau) |

Below saturation, SNR scales as sqrt(N_tdi) once the signal is well clear of the
read floor — the system is photon-shot-noise-limited there (read noise = 15 e- is
negligible against signal shot = 104–207 e-). CU-335's lower signal pushes the
first three rungs into the mixed regime the runner now labels them with: at
N_tdi = 1 the shot term is 25.9 e- against 15 e- of read noise, so the ratio runs
*above* √N until read noise stops mattering. At saturation the signal caps at FWC
and, with no background term to keep growing, the total noise caps at
√FWC ≈ 245 e-, so **SNR plateaus at 244.5 rather than decreasing**.

### Noise Budget
| Noise Term | N=1 [e-] | N=8 [e-] | N=16 [e-] | N=32 [e-] | N=128 [e-] |
|---|---|---|---|---|---|
| signal_shot | 25.9 | 73.2 | 103.6 | 146.5 | 244.9 |
| dark_shot | 0.0 | 0.1 | 0.1 | 0.2 | 0.4 |
| read_noise | 15.0 | 15.0 | 15.0 | 15.0 | 15.0 |
| quantization | 0.4 | 0.4 | 0.4 | 0.4 | 0.4 |
| TOTAL (RSS) | 29.9 | 74.8 | 104.7 | 147.3 | 245.4 |

Signal shot noise dominates throughout, scaling as √N below saturation. Read noise is
constant at 15 e- (the analog-TDI advantage), and dark/quantization are negligible.
There is **no background_shot term** — the extended scene contributes one radiance
field, not a separable background (Decision #13). Past saturation, signal_shot caps at
√FWC and the total plateaus at 245 e-, so SNR holds flat instead of degrading.

### MTF Budget
| N_tdi | MTF_opt [--] | MTF_smear [--] | MTF_misalign [--] | MTF_sys [--] | Misalign [pix] |
|---|---|---|---|---|---|
| 1 | 0.1962 | 0.6366 | 0.9959 | 0.1244 | 0.10 |
| 8 | 0.1962 | 0.6366 | 0.9674 | 0.1209 | 0.28 |
| 16 | 0.1962 | 0.6366 | 0.9355 | 0.1169 | 0.40 |
| 32 | 0.1962 | 0.6366 | 0.8735 | 0.1091 | 0.57 |
| 64 | 0.1962 | 0.6366 | 0.7568 | 0.0945 | 0.80 |
| 128 | 0.1962 | 0.6366 | 0.5508 | 0.0688 | 1.13 |

*(The MTF_opt column was a stale 0.1821 — an older vintage than the sweep table
above it, which already carried 0.1962. Refreshed here so the two tables agree
with each other and with the runner; MTF is geometry/optics-only and does not
depend on the radiometric landings above.)*

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

### The Saturation Plateau
When accumulated signal exceeds FWC, the charge is clipped. No additional TDI stages
can add signal, and — because this extended scene has no separable background photon
term (Decision #13) — the noise stops growing too:
- Signal shot: capped at sqrt(FWC) once the signal clips
- No background_shot term to keep growing past saturation
- Net effect: SNR = FWC / sqrt(FWC + small terms) → **SNR plateaus** at ≈ 245

So the NIIRS curve rises with √N up to saturation and then holds flat (no sharp peak,
no degradation). For this system:
- Signal per line: 671 e-
- FWC: 60,000 e-
- Theoretical max N_tdi (100% fill): 60,000 / 671 = 89.5
- Saturation first reached at N_tdi = 96; NIIRS plateaus at 6.13 from there on
- Practical choice: N_tdi = 64 (NIIRS 6.02, 72% fill) for peak quality with saturation
  margin, or N_tdi = 32 (NIIRS 5.78, 36% fill) for a conservative margin

(If the readout added digital-TDI read noise growth, or if a genuinely separable
background dominated — e.g. a bright adjacent-scene sub-pixel case — the plateau would
instead become a cliff. This extended reflective scene shows the plateau.)

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
In this scenario, NIIRS changes come entirely from the SNR term in GIQE-5 (1.559 x log10(SNR)). The RER term (3.32 x log10(RER)) is constant because RADIANT's ePSF does not include smear or TDI misalignment. Including these corrections would shift the absolute NIIRS values but would not change where the NIIRS plateau begins (which is set by the saturation onset at N_tdi = 64).

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
