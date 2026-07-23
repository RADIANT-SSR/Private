# Scenario 7.4 Walkthrough: Cold Stop Leakage Sweep

Refreshed 2026-07-07 (Scenario_Execution_Plan Phase R): the script now uses
`Sensor.solve_for` (Gap 10), `optics.scalar_emissivity` (Gap 37), the
`optics.nearfield_fraction` name (Gap 12), and the Stage-7
`geometry.sensor_altitude_m` precondition. Numbers re-verified 2026-07-22 (CU-176)
against the current engine: this is a vacuum (exo) lab test, so signal, nearfield,
SNR, and the η_nf inversions are unchanged; only NEDT shifted slightly (band-effective
Planck-factor update, ~+0.5 mK).

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

In RADIANT this is the `optics.nearfield_fraction` parameter (η_nf, formerly `cold_stop_efficiency` — renamed under Gap 12), the fraction of the FPA hemisphere filled by warm-emitting elements:

```
E_nearfield ∝ η_nf × ε_optics × B(λ, T_optics)
```

- η_nf = 0.0 → perfect cold stop (blocks all warm radiation)
- η_nf = 1.0 → no cold stop (all warm radiation reaches FPA)
- η_nf = 1 − vendor "cold stop efficiency" (the vendor convention counts blocking, not leakage)

**Warm-optics emissivity is derived, not free (Rule 5 / Gap 37).** In scalar transmission mode the train is one lumped element. Treating the non-transmitted power as absorbed gives ε = 1 − τ = 1 − 0.68 = 0.32, set via `optics.scalar_emissivity`. Without it the lump defaults to the refractive assumption ε = 0 and the nearfield term is identically zero — the failure that made the first execution of this scenario non-functional (old Gap 4, now closed).

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
- 80 fA/pixel → 499,376 e-/s (dark current: fA × 1e-15 ÷ q_e)
- 3700–4800 nm → 3.70–4.80 µm (bandpass)
- 8 ms → 0.008 s (integration time)
- 68% → 0.68 (transmission), and derived ε = 1 − τ = 0.32 (Kirchhoff)
- vendor cold-stop efficiency % → η_nf = 1 − efficiency (leakage fraction)

### Step 2: Configure the Vacuum Chamber

The atmosphere model is "exo" (vacuum) since Karen is testing in TVAC with no atmospheric path. Two consequences of the current architecture (registry Gap 42):

- The exo backend auto-infers the `no_atmosphere` **space** sub-case (the `lab_test` sub-case has no `Sensor.from_dict` path), so the run carries a placeholder `geometry.sensor_altitude_m = 1.0` m (≈ bench height) to satisfy the Stage-7 Earth-limb intercept check. The value has no radiometric effect here.
- The blackbody fills the FOV → **extended regime**, and in this regime RADIANT skips the separate scene-background photon term entirely (matrix Decision #13): `background_e = 0` by design. The chamber-shroud parameters stay in the config but contribute no photons; the only background terms are warm-optics nearfield and dark current.

### Step 3: Establish the Reference Point

**Illuminated mode** (blackbody at 308 K), at η_nf = 1.0 (no cold stop — maximum leakage):
- Signal: 2,994,945 e-
- Nearfield: 812,493 e-
- Scene background: 0 e- (extended regime, see above)
- SNR: 1,534

**Shuttered mode** (cold plate at 77 K blocking aperture) models what Karen actually measures. At 77 K, the cold plate's MWIR emission is negligible; the only signal is warm optics leaking past the cold stop:
- At η_nf = 0: nearfield = 0 e- (perfect cold stop)
- At η_nf = 1.0: nearfield = 812,493 e- (no cold stop)

Nearfield scales linearly with η_nf, so 1% of leakage ≈ 8,125 e- of shuttered background.

### Step 4: Invert Each Measurement with Sensor.solve_for

The former sweep + linear-interpolation workaround (old Gap 1) is replaced by `Sensor.solve_for` (Gap 10) — Brent root-finding on the forward model with a callable metric (`nearfield_e + background_e`). Each measurement inverts in 6–7 forward-chain evaluations:

| Test Point | Position [mm] | Measured [e-] | Matched η_nf [—] | Evals |
|------------|---------------|---------------|------------------|-------|
| CS-NOM     | 0.0           | 35,500        | 0.0437           | 6     |
| CS-OFF-05  | 0.5           | 39,500        | 0.0486           | 6     |
| CS-OFF-10  | 1.0           | 44,000        | 0.0542           | 7     |
| CS-OFF-15  | 1.5           | 47,750        | 0.0588           | 6     |
| CS-OFF-20  | 2.0           | 52,000        | 0.0640           | 7     |
| CS-OFF-25  | 2.5           | 55,750        | 0.0686           | 6     |

Even at the nominal position, the cold stop has about 4.4% leakage — expected from manufacturing tolerances (no cold stop is truly perfect). The leakage increases linearly with offset, gaining about 1% per mm of misalignment. (The full 51-point sweep is retained only for the plots and the output workbook.)

### Step 5: Assess Requirements

Solving for the 40,000 e- limit gives η_nf ≤ 0.0492, i.e. vendor cold stop efficiency ≥ 95.08%.

- **CS-NOM (0.0 mm)**: 35,500 e- → PASS (η_nf = 0.0437, within limit)
- **CS-OFF-05 (0.5 mm)**: 39,500 e- → PASS (η_nf = 0.0486, marginal)
- **CS-OFF-10 (1.0 mm)**: 44,000 e- → FAIL (η_nf = 0.0542, 10% above limit)

Karen now knows that a 1.0 mm cold stop misalignment pushes the background above the requirement. The alignment tolerance is approximately ±0.5 mm.

### Step 6: SNR Impact

The script evaluates SNR at both the nominal and anomalous cold stop positions with the blackbody illuminated (operational conditions):

| Metric | Nominal (η_nf = 0.0437) | Anomaly (η_nf = 0.0542) |
|--------|-------------------------|-------------------------|
| SNR [—] | 1,719.1 | 1,716.7 |
| NEDT [mK] | 16.81 | 16.83 |
| Nearfield shot noise [e- RMS] | 188.4 | 209.8 |
| Nearfield noise fraction | 1.2% | 1.4% |

**The SNR impact is negligible.** At 1.2–1.4% of total noise variance, nearfield shot noise is completely dominated by signal shot noise (1,731 e- RMS). The cold stop leakage is a calibration concern, not a performance-limiting defect.

## Key Takeaways

1. **The nominal cold stop has 4.4% leakage (η_nf = 0.0437)**, which is normal for a real cryogenic baffle. No cold stop achieves exactly 0% leakage.

2. **The alignment tolerance is ~0.5 mm.** Beyond that, the shuttered background exceeds the 40,000 e- requirement (η_nf > 0.0492). Karen can provide this number to the mechanical team for alignment budgeting.

3. **Cold stop leakage does not significantly affect operational SNR.** Even at the worst tested position (2.5 mm offset, 55,750 e-), nearfield shot noise contributes only ~1.4% of total noise variance. The requirement on shuttered background is driven by calibration accuracy, not image quality.

4. **The parameter name now matches the physics.** `optics.nearfield_fraction` states what the value is; the script converts once, explicitly, from the vendor convention (η_nf = 1 − vendor efficiency) at the input boundary.

5. **The scalar-mode emissivity must be declared, and it is derived, not free.** ε = 1 − τ by Kirchhoff for a reflective train. Forgetting `optics.scalar_emissivity` silently reverts to ε = 0 and a zero nearfield — exactly the failure mode of this scenario's first execution.

6. **The atmosphere model matters — and so does the sub-case.** "exo" (vacuum) sets transmission to unity and path radiance to zero, but routes through the `space` sub-case, requiring the placeholder `geometry.sensor_altitude_m` (registry Gap 42). Using the wrong atmosphere model (e.g., "simple" with an orbital altitude) would introduce spurious atmospheric absorption into a lab measurement comparison.

## Gaps Identified

- ~~**Gap 1 (Inverse solver)**~~: **CLOSED** — `Sensor.solve_for` (registry Gap 10). Each lab measurement inverts in 6–7 forward-model evaluations instead of a 51-point sweep plus interpolation.

- **Gap 2 (Thermal background breakdown)**: OPEN. RADIANT outputs `nearfield_e` (warm optics) and `background_e` (scene) separately, which is good. But there is no per-element breakdown — Karen cannot see how much each optical element (primary mirror, secondary, fold mirror, etc.) contributes to the nearfield. This would help identify which element is the largest contributor and whether the cold stop leakage is coming from one element's direction.

- ~~**Gap 3 (NEDT)**~~: **CLOSED**. `result.metrics["nedt_K"]`, displayed in baseline, sweep, and SNR impact sections.

- ~~**Gap 4 (Nearfield = 0 in scalar mode)**~~: **CLOSED** — `optics.scalar_emissivity` (registry Gap 37) with the Kirchhoff-derived ε = 1 − τ. The sweep is now physically meaningful end-to-end.

- **Gap 6 (lab_test sub-case unreachable from the config surface)**: OPEN — registry Gap 42. This TVAC scenario must masquerade as the `space` sub-case with a placeholder `geometry.sensor_altitude_m`. Acceptable here (extended target fills the FOV; chamber background negligible), but a lit-lab scenario with a non-negligible chamber background cannot be modeled from `Sensor.from_dict` at all.

See `gaps.md` for the full per-gap records.
