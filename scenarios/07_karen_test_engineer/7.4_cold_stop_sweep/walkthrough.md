# Scenario 7.4 Walkthrough: Cold Stop Efficiency Sweep

## The Problem

Karen is a test engineer running a thermal-vacuum (TVAC) characterization campaign on an MWIR imager. During a background characterization test — with the calibration blackbody shuttered and a 77 K cold plate blocking the aperture — she measures 44,000 e- of background signal at one detector position. The design predicts about 35,000 e- with the cold stop properly aligned.

Karen suspects the cold shield has shifted during vibration testing, allowing warm optics thermal emission to leak past the baffle and reach the FPA. She needs to answer three questions:

1. **What cold stop leakage matches the measured background?** If she can map each measurement to an effective leakage parameter, she can quantify the misalignment.
2. **Does the nominal alignment still meet requirements?** The spec says the shuttered background must be below 40,000 e-.
3. **How much does the leakage affect operational SNR?** Is this a cosmetic issue (higher background but acceptable images) or a performance-limiting defect?

## What Is a Cold Stop and Why Does It Matter?

In a cooled infrared sensor, the detector operates at cryogenic temperature (77 K for Karen's HgCdTe FPA). But the optics — mirrors, lenses, and the barrel housing — are warm, typically near ambient temperature (293 K for Karen's TVAC shroud at 20°C).

Every warm optical element radiates thermally according to the Planck function. At 293 K, this radiation peaks in the LWIR but has significant emission in the 3.7–4.8 µm MWIR band that Karen's sensor uses. Without any shielding, the warm optics would flood the FPA with thermal photons, creating a large background signal that degrades noise performance.

The cold stop (also called a cold shield or cold baffle) is a cryogenic enclosure around the FPA, typically cooled to the same 77 K as the detector. It blocks the warm optics from directly illuminating the FPA, allowing only light through the designed optical path (the aperture) to reach the detector.

In RADIANT, this is modeled by the `cold_stop_efficiency` parameter, which controls how much of the warm-optics nearfield irradiance reaches the FPA:

```
E_nearfield = η_cold × Σ [ε_i × B(λ, T_optics) × Ω_i × τ_downstream]
```

**Important convention**: RADIANT's `cold_stop_efficiency` is the fraction of the FPA hemisphere filled by warm-emitting elements — essentially the *leakage* fraction. This is the opposite of the vendor convention where "100% cold stop efficiency" means complete blocking:
- η_cold = 0.0 → perfect cold stop (blocks all warm radiation)
- η_cold = 1.0 → no cold stop (all warm radiation reaches FPA)

## How RADIANT Solves This

### Step 1: Read and Convert Karen's Lab Data

Karen's data arrives in a three-sheet Excel workbook with vendor and lab units:
- **Instrument Spec Sheet**: aperture in cm, focal length in mm, optics temperature in °C, dark current in fA/pixel, spectral band edges in nm, integration time in ms
- **Background Measurements**: six test points at different cold stop positions (0.0 to 2.5 mm offset), with background signal in both DN and e-
- **Performance Requirements**: max shuttered background of 40,000 e-

The script converts every parameter to RADIANT canonical units at the boundary:
- 25 cm → 0.25 m (aperture)
- 1000 mm → 1.0 m (focal length)
- 20°C → 293.15 K (optics temperature)
- 80 fA/pixel → 499.4 e-/s (dark current: fA × 1e-15 ÷ q_e)
- 3700–4800 nm → 3.70–4.80 µm (bandpass)
- 8 ms → 0.008 s (integration time)
- 68% → 0.68 (transmission)
- 75% → 0.75 (quantum efficiency)

### Step 2: Establish the Baseline

RADIANT evaluates the full signal chain in two modes:

**Illuminated mode** (blackbody at 308 K, shroud at 293 K): This gives the operational performance baseline. With η_cold = 1.0 (no cold stop — maximum nearfield):
- Signal: 2,916,027 e-
- Nearfield: 812,493 e-
- Scene background: 1,640,220 e-
- SNR: 1,258

**Shuttered mode** (cold plate at 77 K blocking aperture): This models what Karen actually measures during the background test. At 77 K, the cold plate's MWIR emission is negligible. The only signal is from warm optics leaking through the cold stop:
- At η_cold = 0: nearfield = 0 e- (perfect cold stop)
- At η_cold = 1.0: nearfield = 812,493 e- (no cold stop)

The atmosphere model is set to "exo" (vacuum) since Karen is testing in a TVAC chamber with no atmospheric path.

### Step 3: Sweep and Match

The script sweeps cold_stop_efficiency from 0.00 to 1.00 in the shuttered configuration. Because nearfield scales linearly with η_cold, the sweep produces a straight line from 0 to 812,493 e-.

For each of Karen's lab measurements, the script finds the η_cold that produces the same background signal by linear interpolation:

| Test Point | Position [mm] | Measured [e-] | Matched η_cold |
|------------|---------------|---------------|----------------|
| CS-NOM     | 0.0           | 35,500        | 0.044          |
| CS-OFF-05  | 0.5           | 39,500        | 0.049          |
| CS-OFF-10  | 1.0           | 44,000        | 0.054          |
| CS-OFF-15  | 1.5           | 47,750        | 0.059          |
| CS-OFF-20  | 2.0           | 52,000        | 0.064          |
| CS-OFF-25  | 2.5           | 55,750        | 0.069          |

Even at the nominal position, the cold stop has about 4.4% leakage — this is expected from manufacturing tolerances (no cold stop is truly perfect). The leakage increases linearly with offset, gaining about 1% per mm of misalignment.

### Step 4: Assess Requirements

The 40,000 e- background requirement corresponds to η_cold ≤ 0.049.

- **CS-NOM (0.0 mm)**: 35,500 e- → PASS (η = 0.044, well within limit)
- **CS-OFF-05 (0.5 mm)**: 39,500 e- → PASS (η = 0.049, marginal)
- **CS-OFF-10 (1.0 mm)**: 44,000 e- → FAIL (η = 0.054, 10% above limit)

Karen now knows that a 1.0 mm cold stop misalignment pushes the background above the requirement. The alignment tolerance is approximately ±0.5 mm.

### Step 5: SNR Impact

The script evaluates SNR at both the nominal and anomalous cold stop positions with the blackbody illuminated (operational conditions):

| Metric | Nominal (η = 0.044) | Anomaly (η = 0.054) |
|--------|---------------------|---------------------|
| SNR | 1,360 | 1,359 |
| Nearfield shot noise | 188 e- RMS | 210 e- RMS |
| Nearfield noise fraction | 0.8% | 1.0% |

**The SNR impact is negligible.** At 0.8–1.0% of total noise variance, nearfield shot noise is completely dominated by signal shot noise (1,708 e-) and scene background shot noise (1,281 e-). The cold stop leakage is a calibration concern, not a performance-limiting defect.

## Key Takeaways

1. **The nominal cold stop has 4.4% leakage (η = 0.044)**, which is normal for a real cryogenic baffle. No cold stop achieves exactly 0% leakage.

2. **The alignment tolerance is ~0.5 mm.** Beyond that, the shuttered background exceeds the 40,000 e- requirement. Karen can provide this number to the mechanical team for alignment budgeting.

3. **Cold stop leakage does not significantly affect operational SNR.** Even at the worst tested position (2.5 mm offset, 55,750 e-), nearfield shot noise contributes only ~1% of total noise. The requirement on shuttered background is driven by calibration accuracy, not image quality.

4. **RADIANT's cold_stop_efficiency convention is inverted from vendor convention.** The vendor says "100% efficient cold stop" meaning complete blocking; RADIANT's η_cold = 0 means complete blocking, η_cold = 1 means no blocking. This is a common source of confusion that a GUI should flag clearly.

5. **The atmosphere model matters.** Karen's TVAC test uses "exo" (vacuum) mode, which sets atmospheric transmission to unity and path radiance to zero. Using the wrong atmosphere model (e.g., "simple" with an orbital altitude) would introduce spurious atmospheric absorption into a lab measurement comparison.

## Gaps Identified

- **Gap 1 (Inverse solver)**: OPEN. RADIANT has no built-in "find the parameter value that matches a measurement" solver. The script does this by sweeping and interpolating. A dedicated solver (e.g., root-finding on a scalar objective) would be more efficient and could handle multiple parameters simultaneously.

- **Gap 2 (Thermal background breakdown)**: OPEN. RADIANT outputs `nearfield_e` (warm optics) and `background_e` (scene) separately, which is good. But there is no per-element breakdown — Karen cannot see how much each optical element (primary mirror, secondary, fold mirror, etc.) contributes to the nearfield. This would help identify which element is the largest contributor and whether the cold stop leakage is coming from one element's direction.

- ~~**Gap 3 (NEDT)**~~: **CLOSED**. RADIANT now computes NEDT in the performance stage: `result.metrics["nedt_K"]`. The script now displays NEDT in baseline, sweep, and SNR impact sections.

- **Gap 4 (Nearfield = 0 in scalar mode)**: OPEN. In scalar transmission mode, the lumped refractive element has ε = 0 by Kirchhoff's law (T + R = 1, so ε = 1 − T − R = 0). This means `nearfield_e = 0` regardless of cold_stop_efficiency, making the cold stop sweep non-functional. The fix requires using `key_elements` or `full_prescription` mode with individual mirrors (ε = 1 − R). See `gaps.md` for details.

### Gaps Closed Since Last Run

| Metric | Previous Status | Current Status |
|--------|----------------|----------------|
| NEDT | Not available | `result.metrics["nedt_K"]` — CLOSED |
| NIIRS | Not available | `result.metrics["niirs"]` — CLOSED |
| GSD | Not available | `result.metrics["gsd_geometric_mean_m"]` — CLOSED |
| Strehl | Not available | `result.metrics["strehl"]` — CLOSED |
| Q parameter | Not available | `result.metrics["q_center"]` — CLOSED |
| MTF budget | Not available | `mtf_budget.per_term_at_nyquist` — CLOSED |
| Well margin | Not available | `result.metrics["well_margin_dB"]` — CLOSED |
