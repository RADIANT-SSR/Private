# RADIANT User Personas

**Date:** 2026-04-06  
**Status:** Draft — Pending Review  
**Purpose:** Define who uses RADIANT, how they use it, and what that implies for design.

---

## Persona 1: Systems Engineer — Early Trade Studies

**Name archetype:** "Sarah, EO Systems Engineer"

1. **Background:** MS in optical or aerospace engineering, 5–15 years experience. Solid radiometry intuition — knows the governing equations but doesn't memorize spectral absorption coefficients. Uses tools daily; builds spreadsheets when tools don't exist. Has probably built her own Excel-based SNR calculator at least twice.

2. **Typical task:** "What aperture do I need to achieve SNR ≥ 50 on a 300 K target at 500 km slant range in MWIR, with a 10 cm GSD?" She sweeps aperture from 15–60 cm, plots SNR vs. aperture, and identifies the knee. She then adds jitter and smear to see how MTF degrades NIIRS, and iterates on integration time.

3. **Inputs she knows:**
   - Target: temperature, emissivity (approximate), size
   - Geometry: altitude, look angle, slant range
   - Atmosphere: "standard mid-latitude summer" or a MODTRAN run she got from someone
   - Sensor: aperture range, f/#, pixel pitch, detector material, approximate dark current and read noise
   - She does NOT know: exact WFE, Zernike coefficients, ROIC glow, IPC values. She wants sensible defaults.

4. **Outputs she needs:**
   - SNR vs. aperture (parametric sweep plot)
   - NIIRS vs. aperture
   - NEDT at each operating point
   - System MTF curve
   - A one-page summary she can put in a PowerPoint for a design review

5. **Frequency:** 3–5 times per week during concept phase; daily during proposal surges.

---

## Persona 2: Detector Engineer — Noise Budget Analysis

**Name archetype:** "Mike, Detector Physics Engineer"

1. **Background:** PhD in solid-state physics or electrical engineering. Deep expertise in detector noise mechanisms — he *wrote* the noise models. Knows HgCdTe, InSb, and InGaAs material properties from memory. Skeptical of tools that hide assumptions.

2. **Typical task:** "What is the noise budget breakdown for our 5.0 µm cutoff HgCdTe detector at 80 K operating temperature with 10 ms integration time?" He wants every noise term individually: shot noise, dark current shot noise, read noise, 1/f, kTC, quantization, DSNU residual, PRNU residual, glow. He then asks: "Which noise term dominates? At what integration time does dark current overtake read noise? What operating temperature do I need to keep dark current below X?"

3. **Inputs he knows:**
   - Detector: material, cutoff wavelength, QE(λ), dark current vs. temperature (Rule 07 or measured data), read noise, IPC, pixel pitch, fill factor, diffusion length — all with precision
   - ROIC: CDS mode, gain, FWC, glow level, 1/f corner frequency
   - He does NOT typically care about: atmosphere, scene, or optics. He wants to model the detector in isolation, then plug it into the full system.

4. **Outputs he needs:**
   - Noise budget table: each noise source in electrons, its percentage of total
   - Dark current vs. temperature curve
   - NEDT vs. operating temperature
   - SNR vs. integration time (with each noise component visible)
   - Exportable data (CSV/JSON) for his own plotting tools

5. **Frequency:** Weekly during detector selection; daily during detector characterization campaigns.

---

## Persona 3: Mission Planner — Observation Scenario Evaluation

**Name archetype:** "Raj, Mission Planning Analyst"

1. **Background:** MS in aerospace engineering or physics. Moderate radiometry knowledge — understands SNR and NIIRS conceptually but doesn't derive the equations. Expert in orbital mechanics, geometry, and scheduling. Comfortable with Python scripts but not a software engineer.

2. **Typical task:** "Can our sensor detect a 2 m² vehicle at 40 km/h on a highway from a 600 km sun-synchronous orbit at 10:30 AM LTAN, on June 15, at 35°N latitude, with 23 km visibility?" He has a specific scenario with date, time, location, atmosphere, and target — and needs a yes/no answer with margin.

3. **Inputs he knows:**
   - Sensor: a fixed configuration (the sensor exists or is baselined); he has a sensor spec sheet
   - Geometry: exact orbit parameters, ground target coordinates, date/time → solar zenith, slant range, look angle
   - Atmosphere: visibility, standard atmosphere type, or a MODTRAN tape7 file from the weather team
   - Target: size, temperature or reflectance, speed (for smear)
   - He does NOT want to specify: individual noise terms, Zernike coefficients, BRDF models. He wants to load a sensor config file and go.

4. **Outputs he needs:**
   - SNR for this specific scenario
   - NIIRS for this specific scenario
   - Detection probability (if threshold model available)
   - "Traffic light" pass/fail against requirements
   - Sensitivity to weather (what if visibility drops to 10 km?)

5. **Frequency:** Daily during mission planning; burst usage during exercises or real-world tasking.

---

## Persona 4: Detection/Targeting Analyst — Target Set Evaluation

**Name archetype:** "Lisa, MASINT/GEOINT Analyst"

1. **Background:** BS in physics or engineering; 5–10 years as an analyst. Knows what SNR and NIIRS mean operationally but does not build radiometric models. Uses tools as a consumer, not a developer. Expects a GUI or at minimum a well-documented CLI with config files.

2. **Typical task:** "For 15 target types (vehicles, buildings, ships) across 4 atmospheric conditions and 3 sensor configurations, generate a detection range matrix." She runs a batch of scenarios and produces a table showing detection range (km) for each target/atmosphere/sensor combination.

3. **Inputs she knows:**
   - Target library: predefined target types with T, ε, size, reflectance
   - Sensor library: predefined sensor configurations (loaded from files)
   - Atmosphere library: standard conditions (clear, haze, tropical, arctic)
   - Geometry: range sweep (10–200 km), or fixed altitude with variable look angle
   - She does NOT know (and should not need to): detector physics parameters individually

4. **Outputs she needs:**
   - Detection range matrix (target × atmosphere × sensor)
   - NIIRS vs. range for each combination
   - Exportable tables for briefing slides
   - Batch execution — she should not click through 180 individual runs

5. **Frequency:** Weekly; large batch runs monthly for program reviews.

---

## Persona 5: Optical Designer — MTF and Spatial Performance

**Name archetype:** "Tom, Optical Systems Engineer"

1. **Background:** PhD in optical engineering. Expert in diffraction, aberrations, and MTF. Fluent in Zemax/Code V. He cares about the spatial chain and needs RADIANT to correctly compose his optical MTF with detector, smear, jitter, and electronics MTF to get system-level performance.

2. **Typical task:** "I have a Korsch three-mirror anastigmat with 0.08 waves RMS WFE on-axis and 0.15 waves at full field. What is the system MTF at Nyquist for my baseline detector? How much jitter can I tolerate before NIIRS drops below 5?" He imports his optical PSF or WFE and wants RADIANT to handle everything downstream.

3. **Inputs he knows:**
   - Optics: full prescription (but wants to input via Strehl or Zernike, not lens prescription)
   - WFE map or Zernike coefficients (Z4–Z36)
   - Obscuration, vignetting map, f/#
   - He does NOT want to specify: atmosphere or target details. He wants to fix those at representative values and focus on the spatial chain.

4. **Outputs he needs:**
   - System MTF curve with individual MTF components plotted separately
   - MTF at Nyquist frequency
   - NIIRS vs. WFE (parametric sweep)
   - RER (Relative Edge Response) — required for GIQE
   - PSF plot (2D)
   - Ensquared/encircled energy vs. box/radius size

5. **Frequency:** 2–3 times per week during optical design phase; intermittently during integration and test.

---

## Persona 6: Researcher — Publication and Validation

**Name archetype:** "Dr. Chen, University Researcher"

1. **Background:** PhD in remote sensing, atmospheric science, or EO systems. Deep theoretical knowledge but may not have access to classified sensor parameters. Uses RADIANT to validate models, generate synthetic data for papers, or compare algorithms. Expects code-level access, not just a GUI.

2. **Typical task:** "I'm developing a new background clutter model for LWIR urban scenes. I need RADIANT to generate ground-truth SNR and NEDT predictions for a set of reference sensor configurations so I can benchmark my model against an independent tool."

3. **Inputs he knows:**
   - Everything — he specifies all parameters explicitly because he's controlling the experiment
   - He wants to override defaults, disable specific effects, and isolate individual model components
   - He may want to swap in his own atmospheric model or detector model

4. **Outputs he needs:**
   - Full intermediate results at every stage of the signal chain (not just final SNR)
   - Spectral radiance at each stage (source, at-sensor, after optics, at detector)
   - Every noise term individually
   - Every MTF term individually
   - Provenance: what version of the code, what parameters, what models were active
   - Reproducibility: given the same inputs, identical outputs

5. **Frequency:** Intensive bursts during paper writing (daily for weeks); otherwise occasional.

---

## Persona 7: Test Engineer — Hardware Verification

**Name archetype:** "Karen, Integration & Test Engineer"

1. **Background:** MS in optical or electrical engineering. Practical, measurement-oriented. She has lab data from radiometric calibration and wants to compare measured performance against predicted performance. "Does our sensor match the model?"

2. **Typical task:** "We measured NEDT = 22 mK at 25°C blackbody temperature with 8 ms integration. The model predicts 18 mK. Which noise term explains the 4 mK gap?" She runs RADIANT with the exact as-built sensor parameters and compares each noise component against measured values to isolate discrepancies.

3. **Inputs she knows:**
   - Exact as-built parameters: measured QE, measured dark current at operating temperature, measured read noise, measured FWC, actual integration time, actual f/#
   - Lab conditions: blackbody temperature, background temperature, calibration source spectral output
   - She does NOT need: atmosphere, orbit, scene. She needs a "lab mode" where the source is a calibration blackbody filling the aperture.

4. **Outputs she needs:**
   - Predicted NEDT with full noise breakdown
   - Predicted vs. measured comparison table
   - Sensitivity analysis: which parameter, if adjusted by X%, would close the gap?
   - Parameter audit trail: exact inputs used for this prediction

5. **Frequency:** Daily during I&T campaigns (weeks to months); occasional during anomaly investigation.

---

## Design Implications

The personas above drive the following architectural and interface requirements:

### Input Flexibility

| Implication | Driving Persona | Consequence |
|-------------|----------------|-------------|
| **Sensible defaults for all parameters** | Sarah (P1), Raj (P3), Lisa (P4) | Every parameter must have a documented default value. Users who don't know IPC coupling coefficient should get a reasonable value without being forced to look it up. |
| **Sensor configuration files** | Raj (P3), Lisa (P4), Karen (P7) | Sensors must be definable as reusable config files (YAML/JSON/TOML). Load a sensor, specify a scenario, get a result. |
| **Target and atmosphere libraries** | Lisa (P4), Raj (P3) | Predefined target types (vehicle, building, ship) and standard atmospheres must ship with the tool. |
| **Parameter override at any level** | Dr. Chen (P6), Mike (P2) | Any default or library value must be overridable. Expert users need full control. |
| **Lab mode (no atmosphere, no scene)** | Karen (P7), Mike (P2) | The tool must support a mode where the source is a calibration blackbody and there is no atmosphere — just source → optics → detector → readout. |

### Output Requirements

| Implication | Driving Persona | Consequence |
|-------------|----------------|-------------|
| **Full noise budget breakdown** | Mike (P2), Karen (P7) | Every noise term must be reported individually, not just total noise. Output must include a noise budget table. |
| **Full MTF budget breakdown** | Tom (P5) | Every MTF contributor must be reported individually. System MTF is a product, but the factors must be visible. |
| **Intermediate radiance at every stage** | Dr. Chen (P6), Karen (P7) | Signal chain must expose spectral radiance after each stage: source, at-sensor (after atmosphere), after optics, at detector. Not just final electrons. |
| **Exportable data formats** | All | CSV and JSON export at minimum. Analysts paste into PowerPoint; researchers load into MATLAB/Python; engineers load into Excel. |
| **Provenance and reproducibility** | Dr. Chen (P6), Karen (P7) | Every output must record: RADIANT version, date, full input parameter set, which models were active/stubbed/disabled. Given the same inputs, outputs must be bitwise identical. |

### Execution Model

| Implication | Driving Persona | Consequence |
|-------------|----------------|-------------|
| **Parametric sweeps are first-class** | Sarah (P1), Tom (P5) | The API must natively support "sweep parameter X from A to B in N steps, hold everything else constant." This is the most common use pattern. |
| **Batch execution** | Lisa (P4) | Must support batch runs from a list of scenario definitions. No interactive clicks for 180 runs. |
| **Single-scenario quick evaluation** | Raj (P3) | Must support "one call, one answer" for a fully specified scenario. Latency < 1 second for a single-band, single-scenario evaluation. |
| **Component isolation** | Mike (P2), Tom (P5), Dr. Chen (P6) | Users must be able to run subsets of the signal chain in isolation: detector-only, optics-only, atmosphere-only. |

### API and Interface

| Implication | Driving Persona | Consequence |
|-------------|----------------|-------------|
| **Python API must be the primary interface** | All | Python is the lingua franca for this user community. The core API must be Pythonic, well-documented, and importable. MATLAB bridge is a nice-to-have, not v1. |
| **CLI for batch and scripting** | Raj (P3), Lisa (P4) | Command-line interface for headless/batch execution. Config file in → results file out. |
| **No GUI required in v1** | All except Lisa (P4) | GUI is a future enhancement. The primary interface is Python API + CLI. Lisa's batch workflow is served by config files + CLI. |
| **Notebook-friendly** | Sarah (P1), Dr. Chen (P6) | Must work cleanly in Jupyter notebooks. Plotting helpers are valuable but not core. |

### Trust and Validation

| Implication | Driving Persona | Consequence |
|-------------|----------------|-------------|
| **Transparent assumptions** | All | Every model assumption must be documented and queryable at runtime ("what BRDF model is active for this run?"). No hidden magic. |
| **Units are explicit everywhere** | All | Every input and output must carry explicit units. No implicit conventions. SI preferred; spectral radiance in W/m²/sr/µm. |
| **Validation test suite ships with the tool** | Karen (P7), Dr. Chen (P6) | Reference cases with known-good answers (e.g., blackbody SNR in a simple scenario) must be part of the distribution. Users need to verify their installation produces correct results. |

---

## Priority Matrix

Which personas drive v1 requirements most strongly?

| Persona | v1 Priority | Rationale |
|---------|-------------|-----------|
| P1 — Systems Engineer (Sarah) | **Critical** | Most common user; defines core workflow (parametric trade studies) |
| P2 — Detector Engineer (Mike) | **Critical** | Noise budget is a core output; validates detector model fidelity |
| P3 — Mission Planner (Raj) | **High** | Single-scenario evaluation is a degenerate case of parametric sweep; served by sensor config files |
| P4 — Detection Analyst (Lisa) | **High** | Batch execution + target/atmosphere libraries; important but layered on top of core API |
| P5 — Optical Designer (Tom) | **High** | MTF chain is core; PSF/MTF decomposition is a required output |
| P6 — Researcher (Dr. Chen) | **Medium** | Intermediate outputs and provenance are architectural requirements that serve everyone; his exotic override needs are secondary |
| P7 — Test Engineer (Karen) | **Medium** | Lab mode is a valuable degenerate case; predicted-vs-measured is a post-processing workflow |
