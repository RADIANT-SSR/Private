> **HISTORICAL (archived 2026-07-06).** Historical LLM prompt-sequence playbook. Was misfiled in docs/adr/ — it is not a decision record. Archived unmodified.

# RADIANT — Optimized Prompt Sequence for Architecture from Scratch

## How to use this document

Run these prompts sequentially in a single long conversation with a
capable LLM (Claude Opus, GPT-5 class). Each prompt produces one or
more architecture documents. Do NOT skip prompts — later prompts
depend on decisions made in earlier ones.

**Estimated time:** 12–18 hours of focused conversation (vs the ~30+
hours it took us the first time).

**Why this is faster:** Front-loaded scoping, physics inventory before
design, explicit "what are we missing" checkpoints, unified subsystems
built together instead of separately.

---

## PHASE 0 — FRAMING (1 prompt)

### Prompt 0.1 — Project framing

```
I am designing a radiometric, spectral, and spatial performance
modeling framework for space-based and airborne electro-optical
sensors. I will call it RADIANT.

The goal is to predict metrics like SNR, NEDT, NIIRS, detection
range, and MTF from first-principles physics: source emission,
atmospheric propagation, optical throughput, detector response,
and spatial resolution.

Before we design anything, I want you to act as a technical fellow systems
architect with deep domain expertise in IR sensor physics, radiometry,
and software architecture. Throughout this conversation:

1. Push back when I'm wrong about physics or about software design.
2. Proactively identify gaps — don't wait for me to ask.
3. Prefer explicit over implicit. Prefer one right way over many.
4. Ask clarifying questions before making assumptions.
5. When you generate documents, make them dense and specific, not
   verbose marketing copy.

Acknowledge this and ask me any framing questions you have before
we start scoping. Do not begin designing anything yet.
```

---

## PHASE 1 — SCOPE AND PHYSICS INVENTORY (3 prompts)

**Critical insight from our first attempt:** We discovered noise sources,
motion sources, stray light, and other physics reactively. This phase
forces us to enumerate ALL physics up front so nothing is missed.

### Prompt 1.1 — Complete physics inventory

```
Before we design architecture, I need a complete inventory of the
physics that must be modeled. Be exhaustive — I would rather explicitly
defer a source than discover it mid-implementation.

Produce a single document that enumerates EVERY physical effect that
could influence sensor performance, organized by signal chain stage:

1. Source/target radiation (thermal, reflected, self-luminous, Doppler, ...)
2. Atmospheric propagation (absorption, scattering, emission, turbulence,
   refraction, polarization, ...)
3. Optical train (transmission, reflection, emission, stray light,
   ghost images, scatter, polarization, diffraction, WFE, ...)
4. Detector (QE, dark current, ALL noise sources — give me at least 12,
   saturation, nonlinearity, crosstalk, persistence, cosmic rays, ...)
5. Readout electronics (TDI, binning, coadds, CDS, gain, ADC,
   quantization, bias drift, ...)
6. Spatial effects (PSF, MTF, smear sources, jitter sources, pointing,
   registration, ...)
7. Scene/background (clutter, co-registration, spatial structure, ...)

For each physical effect, note:
  - Whether it's fundamental or engineering
  - Which wavelength regimes it matters in (VIS, SWIR, MWIR, LWIR)
  - Typical magnitude (order of magnitude)
  - Whether it's usually modeled or usually ignored
  - Input parameters needed to model it

Then produce a "Scope Triage" table with three columns:
  IN v1 | STUBBED v1 | DEFERRED

Your recommendation for each effect. Be conservative with IN — aim
for ~80% coverage with ~50% effort. We will make final scope decisions
together based on your triage.

Document name: RADIANT_Physics_Inventory.md
```

### Prompt 1.2 — Scope decisions

```
Review your physics inventory. I want to discuss the borderline cases
before we lock in scope.

For each item you marked "STUBBED" or "DEFERRED", tell me:
  1. What capability we lose by deferring it
  2. What kinds of users or scenarios need it
  3. How much implementation effort to add later vs now
  4. Whether deferring it affects any architectural decisions

I will then make the final IN/STUBBED/DEFERRED call for each. Produce
the final scope document after we agree.

Constraints:
  - OUT: plume model, multi-band/hyperspectral sensors, custom mesh import
  - STUBBED acceptable: atmospheric turbulence, exotic BRDFs, stray light
    from first principles, stellar catalogs
  - IN: everything else that has a reasonable implementation path

Document name: RADIANT_Scope_Decisions.md
```

### Prompt 1.3 — Use cases and user personas

```
Who uses RADIANT, and what do they do with it? I want 5–7 concrete
user personas with representative workflows.

Examples of personas to consider:
  - Systems engineer doing early trade studies (SNR vs aperture)
  - Detector engineer evaluating noise budgets
  - Mission planner checking a specific observation scenario
  - Analyst computing detection probability for a target set
  - Researcher generating data for a paper

For each persona, give me:
  1. Their background (expertise level in radiometry)
  2. Their typical task (concrete example)
  3. Their inputs (what they know about their system)
  4. Their outputs (what they need to deliver)
  5. How often they use the tool

Then derive a set of design implications. Examples:
  - "If X persona uses it weekly, the main API must be MATLAB-simple"
  - "If Y persona needs Z output, we must track provenance"

Document name: RADIANT_Personas.md
```

---

## PHASE 2 — CORE ABSTRACTIONS (4 prompts)

Build the foundational data structures before any physics. These are
the decisions that shape everything else.

### Prompt 2.1 — Coordinate and spectral conventions

```
Define the core conventions. These must be locked before any physics
document is written. Be specific — no "we could do it either way".

Decide and justify:

1. Spatial coordinate system
   - Handedness (right or left)
   - +Z direction (toward target, away from target, up)
   - +X and +Y axis assignments (cross-scan, along-scan)
   - Euler angle convention (which rotation order)
   - Pixel indexing ([row,col]=[y,x] or [x,y])

2. Spectral conventions
   - Primary variable: wavelength or wavenumber
   - Units (µm, nm, cm⁻¹)
   - Ordering (ascending, descending)
   - How the other one is derived/accessed

3. Radiometric quantity conventions
   - Spectral radiance units (W/m²/sr/µm or photon rate)
   - Spectral irradiance units
   - Spectral intensity units
   - How to convert between them

4. Time conventions
   - Integration time units (s, ms, µs)
   - Frame rate vs integration time distinction

5. Angular units
   - Radians or degrees for what
   - urad vs mrad

For each, give me:
  - The choice
  - The justification (physics and code-ergonomics)
  - What other tools use (MODTRAN, Zemax, Code V, etc.)
  - Conversion rules at interface boundaries

Document name: RADIANT_Conventions.md
```

### Prompt 2.2 — Parameter system

```
Design the parameter system. This is the foundation for EVERYTHING.

Requirements:
  1. Every parameter is named, described, typed, unit-tagged.
  2. Parameters can be specified by user OR computed from other parameters.
  3. When a parameter changes, downstream parameters are recomputed.
  4. Consistency groups: some parameters are linked (e.g., focal
     length, aperture diameter, f/number — specify any 2 of 3).
  5. Tolerances: any parameter can have a statistical distribution
     for Monte Carlo or tolerance analysis.
  6. Validation: ranges, types, enum options.
  7. Provenance: track whether a value is user-set, default, or derived.
  8. Explainability: any parameter can answer "why does this have
     this value?"

Design the Parameter class and the resolver that processes a set
of parameters into resolved values.

Critical decision: how do we handle spectral arrays (wavelength-dependent
quantities) in the parameter system? Options:
  a. Treat as parameters like any other
  b. Keep parameters scalar, put arrays in module computation layer
  c. Hybrid

Choose and justify. The decision affects the entire architecture.

Also decide:
  - Parameter naming convention (dot paths, namespaces)
  - How defaults are specified
  - How units are represented (strings, astropy.units, custom enum)
  - How tolerances are specified
  - How dependencies are tracked (topological sort)

Produce both the design document AND a skeleton Python implementation
of the Parameter class and resolver.

Document name: RADIANT_Parameter_System.md
```

### Prompt 2.3 — Signal chain skeleton

```
Now design the signal chain architecture. Before any specific physics,
define:

1. What is a "chain"? Is it a pipeline of modules? A function
   composition? A DAG?

2. What are the module interfaces? Every module (source, atmosphere,
   optics, detector) must produce what and consume what?

3. How does data flow between modules?
   - SpectralArrays for wavelength-dependent quantities
   - Scalars for integrated quantities
   - Propagation of both through the chain

4. Critical insight I learned the hard way: there are THREE distinct
   radiometric regimes that need different chains:
   - Extended scene (target fills pixel): radiance × Ω × A_pix
   - Point source (target << PSF): intensity / R² × A_aperture × EE
   - Sub-pixel (target between): fill fraction × radiance contrast

   How does the framework dispatch between these? Auto-detect from
   target angular extent vs PSF/IFOV? User-specified?

5. Backward propagation: a user should be able to express or query ANY quantity (noise, signal) at ANY reference frame (at aperture,
   at FPA, in electrons, in DN). How?

6. How do modules communicate non-radiometric info (geometry, timing)?

Produce the architecture document with:
  - Module protocol definitions (what every source must implement, etc.)
  - ChainResult data structure
  - Regime auto-detection logic
  - Forward and backward propagation equations
  - Concrete interface signatures in Python

Document name: RADIANT_Signal_Chain_Architecture.md
```

### Prompt 2.4 — File tree and module layout

```
Given the parameter system and signal chain architecture, propose the
complete directory structure for the codebase.

Constraints:
  - Python package, single namespace (radiant/)
  - Every physics module gets its own subpackage
  - Clear separation of: core abstractions, physics modules, I/O,
    CLI, scripting API, tests, data, documentation
  - Tests alongside implementation (radiant/xxx/tests/ or parallel tests/)

For each directory, list the files that go in it with a one-line
description. Aim for ~100-150 source files (not fewer — overly small
files are fine, overly large ones are not).

Also specify:
  - Import rules (what can import what)
  - Public vs private API
  - Where plugins/extensions go
  - How users add their own sources/metrics/atmosphere models

Document name: RADIANT_File_Tree.md
```

---

## PHASE 3 — PHYSICS DESIGN (6 prompts)

With foundations locked, design each physics domain. Each prompt
produces a complete subsystem in one pass — no circling back.

### Prompt 3.1 — Sources and targets (UNIFIED)

```
Design the complete source/target system in one pass. I want:

1. Source types
   - Thermal (Planck × emissivity)
   - Reflected solar (BRDF × E_sun)
   - Combined (Kirchhoff-consistent)
   - Sub-pixel (target + background with fill fraction)
   - Point source (intensity directly or from physics)
   - Tabulated (user-provided spectral data)
   - Background model (for noise, not signal)

2. Target geometry
   - Parameterized shapes: sphere, cylinder, box, flat_plate, cone
   - Composite (multi-primitive assembly)
   - Per-facet materials
   - Orientation (Euler angles)
   - Projected area computation
   - Visible facet determination

3. Materials (SurfaceMaterial class)
   - Temperature
   - Emissivity (scalar, spectral file, library)
   - Reflectance (scalar, spectral file, library)
   - BRDF model (Lambertian, Phong for v1)
   - Kirchhoff consistency enforcement

4. Unified input paths
   Users can specify a target as:
   - Direct radiance properties (skip geometry)
   - 3D geometry with materials → regime auto-detected
   - Sub-pixel parameters (skip geometry)
   - Direct intensity (point source)
   - Physical object (computed intensity)

   All five paths must produce the SAME ResolvedTarget that the chain
   consumes. The chain should not know which path was used.

5. Auto regime detection
   Given a target's projected area, range, PSF, and IFOV, determine:
   - Point source regime (angular extent < 0.3 × PSF FWHM)
   - Sub-pixel regime (between)
   - Extended regime (> 3 × IFOV)

   Formalize the thresholds and the dispatch logic.

6. Parameter inventory
   Give me the COMPLETE parameter list for this subsystem. Every
   user-facing parameter with name, description, unit, type, default,
   valid range, and tolerance defaults. Expect 50-100 parameters.

THIS IS ONE DOCUMENT, NOT FIVE. In my first attempt I built target
shapes and source models separately and then had to unify them.
Unified from the start saves time.

Document name: RADIANT_Source_Target_System.md
```

### Prompt 3.2 — Atmosphere

```
Design the atmospheric propagation module.

1. Atmosphere models
   - Simple parametric (visibility, humidity, aerosol type)
   - Exo-atmospheric (tau=1)
   - Tabulated (user provides transmittance and path radiance)
   - MODTRAN interface (builds card deck, parses tape7, caches results)

2. Outputs
   - Spectral transmittance τ_atm(λ)
   - Path radiance L_path(λ)
   - Both must be computed for any model

3. Geometry dependence
   - Slant path length from sensor altitude, target altitude, zenith angle
   - Solar zenith angle for downwelling irradiance
   - How path length affects each model

4. Atmospheric turbulence (STUBBED)
   - Kolmogorov MTF formula only, enabled as flag
   - r_0 as input parameter
   - Applied as MTF component in spatial model, not here

5. Parameter inventory
   - All user-facing parameters for each atmosphere model

6. MODTRAN interface details
   - Card deck builder (which cards, which parameters)
   - Tape7 parser
   - Cache keying (config hash → results)
   - Error handling when MODTRAN is unavailable

Document name: RADIANT_Atmosphere.md
```

### Prompt 3.3 — Optics (COMPLETE)

```
Design the complete optics module. This is one of the most complex
subsystems — do it all in one pass.

1. Aperture
   - Circular, rectangular, custom shape
   - Central obscuration
   - Spider arms
   - Apodization (uniform, Gaussian, tabulated)
   - Pupil function generation

2. Wavefront error
   - Scalar RMS (simplest)
   - Zernike coefficients (standard)
   - Measured OPD map (from interferometer)
   - Field-dependent WFE

3. Transmission — FIVE input modes (critical design)
   - Mode 1: scalar transmission (simplest)
   - Mode 2: spectral transmission file
   - Mode 3: telescope transmission + filter stack
   - Mode 4: key elements (user lists important ones)
   - Mode 5: full element-by-element prescription
   All five must produce the same internal representation.

4. Element list (for modes 4–5)
   - Each element: type, temperature, reflectance/transmittance,
     surfaces, geometry
   - Filters (bandpass, longpass, shortpass, notch, tabulated)
   - Kirchhoff-derived emissivity: ε = 1 - R for mirrors,
     ε = 1 - T - R for transmissive
   - User specifies reflectance and transmittance; emissivity is ALWAYS
     derived. Never specified independently.

5. Nearfield emission
   - Each element's thermal emission
   - Downstream attenuation: element i's emission is attenuated by
     all elements between i and the detector
   - Per-element solid angle (not the signal Ω)
   - Cold stop efficiency
   - Total nearfield irradiance at FPA

6. Stray light (FOUR input modes)
   - Mode 1: veiling glare fraction (% of in-FOV)
   - Mode 2: absolute irradiance at FPA (W/m²)
   - Mode 3: spectral stray file (from FRED/TracePro export)
   - Mode 4: PST file (STUBBED in v1, interface reserved)
   Stray light adds electrons + shot noise, NOT signal.
   Include `includes_thermal` flag to prevent double-counting with nearfield.

7. Etendue vs nearfield solid angle (subtle point)
   - Signal path uses single AΩ (invariant through optics)
   - Nearfield uses per-element Ω (depends on each element's size/location)
   - Do NOT conflate these

8. Parameter inventory
   - Complete list for aperture, WFE, all five transmission modes,
     all four stray light modes, nearfield

Document name: RADIANT_Optics.md
```

### Prompt 3.4 — Spatial/diffraction/PSF (UNIFIED)

```
Design the complete spatial model in one pass. This must tie together
diffraction, PSF, MTF, EE, LSF, ERF, smear, jitter, and TDI effects
WITHOUT any inconsistency.

CRITICAL INSIGHT (learned the hard way): the PSF is the SINGLE SOURCE
OF TRUTH. MTF, EE, LSF, ERF, and fill-fraction coupling must all be
derived from the same PSF. Never compute them independently.

1. Diffraction engine
   - Pupil function → PSF via FFT
   - Pupil grid sampling
   - Focal plane grid sampling
   - Zero-padding for spatial oversampling
   - Polychromatic PSF (wavelength quadrature)

2. Sampling configuration
   Three mutually-constrained parameters:
   - psf_oversample (samples per pixel in PSF)
   - psf_sample_spacing_um (physical sample spacing)
   - min_samples_per_pixel
   User specifies one, others derived via consistency group.
   NOTE: do NOT call this parameter 'Q' or 'padding_ratio' — collides
   with QE notation and is ambiguous.

3. Fidelity presets
   - Draft, standard, high, publication
   Each sets grid sizes, oversample factors, wavelength sample count.

4. PSF pipeline
   Starting from optical PSF, convolve in order:
     a. Detector pixel aperture (rect)
     b. Charge diffusion (Gaussian)
     c. Platform smear along-track (rect)
     d. Scan smear cross-track (rect, if any)
     e. Target motion smear (rect, if untracked)
     f. Jitter (Gaussian, possibly anisotropic)
     g. TDI misalignment (small rect)
     h. Atmospheric turbulence (Kolmogorov, if enabled)
   
   Result is the EffectivePSF.

5. EffectivePSF class (THE critical class)
   Methods:
     - mtf_2d(), mtf_1d(axis) → MTF derived from PSF via FFT
     - ensquared_energy(box) → EE from integration of PSF
     - ensquared_energy_nxn(n, pitch) → EE in n×n pixel box
     - ee_vs_offset(pitch) → EE as function of sub-pixel position
     - lsf(angle) → projected PSF
     - erf(angle) → cumulative LSF
     - edge_slope(angle) → sharpness metric
     - rer() → relative edge response for NIIRS
     - fwhm(axis) → spot size
     - strehl() → peak ratio
   ALL methods derived from the same PSF data. No inconsistency possible.

6. Smear sources (FIVE distinct)
   - Platform motion (along-track, deterministic)
   - Scan mechanism (cross-track, deterministic)
   - Target motion (either axis, if target moving)
   - Platform jitter (random, Gaussian or PSD)
   - Atmospheric turbulence (random, stubbed)

7. Tracking mode
   - Untracked: platform motion blurs target and background
   - Tracked: target image stabilized, background smears instead
   - Different MTF budgets for target vs background in tracked mode
   - Important for point source detection while tracking

8. MTF budget (12 components)
   List every MTF contribution and how they combine (product).
   Verify: product of individual MTFs equals FFT of convolved PSF.
   This is the consistency check.

9. Parameter inventory
   Complete list for all sampling, motion, jitter sources.

Document name: RADIANT_Spatial_Complete.md
```

### Prompt 3.5 — Detector (COMPLETE: QE, noise, TDI, binning, readout)

```
Design the complete detector and readout chain in ONE pass.
Do not split this into multiple documents — the interactions matter.

1. QE library
   - Pre-built for: Si CCD, InGaAs, HgCdTe MWIR, HgCdTe LWIR, InSb, T2SL
   - Custom QE curve from file
   - QE as function of wavelength
   - Cutoff wavelength parameter
   - Sub-band weighting (if multi-layer detector)

2. Pixel geometry
   - Pitch x, pitch y
   - Fill factor (active area fraction)
   - Shape (rect, circle)
   - Charge diffusion (Gaussian kernel)

3. Complete noise model — enumerate ALL sources
   Fundamental photon noise:
   - Signal shot
   - Background shot
   - Nearfield shot
   - Stray light shot
   Detector material noise:
   - Dark current shot (Arrhenius T-scaling)
   - Generation-recombination (G-R)
   - Johnson (thermal from R_0 × A)
   - 1/f (flicker)
   ROIC noise:
   - Read noise
   - kTC reset noise (suppressed by CDS)
   - Quantization
   Fixed pattern (spatial):
   - PRNU (signal-dependent)
   - DSNU (dark-dependent)
   - Scene clutter

   That's 13 sources. Did I miss any? Think carefully — persistence,
   image lag, cosmic rays, ADC nonlinearity, crosstalk, bias drift?
   Tell me which to include.

   For each noise source:
   - Physical origin
   - Equation
   - When it matters (wavelength, temperature, detector type)
   - Parameters needed
   - How CDS affects it (for kTC and 1/f)

4. Temporal vs spatial separation
   - σ_temporal = RSS of random noises (per frame)
   - σ_spatial = RSS of fixed patterns (calibrated out for imaging)
   - User selects which regime: imaging (temporal only) or
     detection (temporal + spatial)

5. Readout chain order (CRITICAL)
   Signal electrons →
     TDI accumulation (analog, before readout) →
     On-chip binning (analog, before readout) →
     Well capacity check (analog saturation) →
     Nonlinearity →
     Read noise injection (ONCE for analog accumulation) →
     Gain conversion (e⁻ → DN) →
     A/D quantization →
     ADC saturation check (digital) →
     Off-chip binning (digital, after readout) →
     Coadds (digital, frame accumulation) →
     DN_final

   Two saturation points: well (analog) and ADC (digital).
   Document which operations happen in which domain and why.

6. TDI
   - Analog charge accumulation across N stages
   - Signal × N, dark × N, read noise unchanged (single readout)
   - Well capacity check happens AFTER TDI accumulation
   - CTE loss model
   - TDI misalignment → MTF degradation (passes to spatial model)

7. Binning
   - On-chip (analog): signal × MN, read noise unchanged,
     but combined charge can saturate well
   - Off-chip (digital): signal × MN, read noise × √(MN),
     each pixel saturates independently
   - Spatial effect: effective pixel pitch × M,N → recompute MTF_det

8. Coadds
   - Digital accumulation after readout
   - Sum mode: signal × K, read noise × √K
   - Average mode: signal unchanged, read noise / √K
   - Median mode: outlier rejection, noise ≈ √(π/(2K))
   - Each frame saturates independently (no additional saturation risk)

9. Interaction matrix
   TDI × on-chip binning × off-chip binning × coadds can all be active
   simultaneously. Multiplicative scaling for signal and noise. Give me
   the complete interaction table.

10. Parameter inventory
    Expect ~60 parameters for this subsystem.

Document name: RADIANT_Detector_Complete.md
```

### Prompt 3.6 — Scan modes and timing

```
Design scan modes and timing.

1. Scan types
   - Stare (framing sensor)
   - Pushbroom (TDI or non-TDI)
   - Whiskbroom (cross-track scanning)
   - Step-stare (mosaic)

2. Timing computation for each
   - Line rate (pushbroom)
   - Frame rate (stare)
   - Dwell time per pixel (whiskbroom)
   - Settle time (step-stare)

3. Integration time derivation
   - User specifies directly, OR
   - Derived from scan type + geometry + platform velocity
   - Consistency group with related parameters

4. Ground velocity
   - From platform orbit (LEO ~6800 m/s)
   - From aircraft speed
   - From user override

5. Motion parameters feeding the spatial model
   - Platform smear (from scan type + t_int)
   - Target motion smear (from target velocity + t_int × N_TDI)
   - Jitter (from separate jitter subsystem)

6. Parameter inventory

Document name: RADIANT_Scan_Timing.md
```

---

## PHASE 4 — METRICS AND DEPENDENCIES (2 prompts)

### Prompt 4.1 — Metrics

```
Define every output metric RADIANT produces, with the complete
computation path from inputs.

Metrics to include:
  - SNR (all three regimes)
  - NEΔT (thermal targets)
  - NEΔL (spectral and band-integrated)
  - NEΔρ (reflected targets)
  - CSNR (sub-pixel contrast)
  - NIIRS (GIQE-5)
  - RER (relative edge response)
  - Edge slope
  - MTF 
  - EE (1×1, 3×3, 5×5, vs offset)
  - Strehl ratio
  - Point source detection range
  - Saturation margins (well, ADC)
  - Dynamic range

For each metric:
  - Formula
  - Required inputs (which parameters MUST be set)
  - Applicable regimes
  - Units
  - Typical values
  - Failure modes (when it's meaningless or ill-defined)

Also design a metric plugin system: users should be able to register
custom metrics without modifying core code.

Document name: RADIANT_Metrics.md
```

### Prompt 4.2 — Metric dependency trees

```
For every metric from the previous prompt, produce the COMPLETE
dependency tree back to input parameters.

Format: indented tree showing every intermediate quantity and every
required parameter. Mark required (★) vs has-default (●).

Example:

CSNR
├── |ΔS| (contrast electrons)
│   ├── ff (fill fraction)
│   │   ├── ★ target angular extent
│   │   ├── IFOV (derived from pixel pitch + focal length)
│   │   └── PSF coupling (if enabled)
│   ├── ΔL(λ) (spectral contrast)
│   │   ├── ★ target temperature
│   │   ├── ★ background temperature
│   │   ...
│   ...
└── σ_total
    ...

This will be used by the parameter resolver to:
  1. Validate required inputs before running
  2. Give specific error messages ("CSNR requires X")
  3. Determine which metrics are computable from current config
  4. Show the user exactly what to add for a desired analysis

Document name: RADIANT_Metric_Dependencies.md
```

---

## PHASE 5 — USER INTERFACE (3 prompts)

### Prompt 5.1 — Configuration format

```
Design the configuration format and I/O.

1. YAML as canonical format
   - Structure and naming conventions
   - Inheritance (parent → child overrides)
   - Variable substitution
   - Include/import
   - Comments for documentation

2. XLSX as convenience view
   - Generated from YAML
   - Round-trippable (edit in Excel, back to YAML)
   - Not the source of truth

3. Python API (creation from code)

4. CLI overrides (dot-path parameter overrides)

5. Validation
   - Pydantic schema
   - Physics-informed validation (consistency groups)
   - Rich error messages

6. Examples
   Give me 5 complete YAML configs for common scenarios:
   - MWIR LEO pushbroom (baseline)
   - LWIR geostationary stare
   - Visible aerial pushbroom
   - Point source tracking
   - Sub-pixel target detection

Document name: RADIANT_Config_Format.md
```

### Prompt 5.2 — Scripting API

```
Design the Python scripting API. The goal is MATLAB-like simplicity
for trade studies.

Requirements:
  1. Load/save configs
  2. Evaluate chains
  3. Sweep any parameter, collect any metric
  4. 2D sweeps (contour plots)
  5. Monte Carlo tolerance analysis
  6. Sensitivity analysis
  7. Plot ANY intermediate quantity (spectral, 2D, MTF, kernel)
  8. Variable explorer: browse every intermediate
  9. Tab completion in IPython/Jupyter

Concrete API design:
  - Sensor class (primary interface)
  - sensor.load(), sensor.set(), sensor.evaluate()
  - sensor.sweep(param, values, metric="snr")
  - sensor.sweep_2d(...)
  - sensor.monte_carlo(n_trials=1000)
  - Plottable protocol for every object that can display itself
  - result.plot.* for quick plots
  - result.inspect() for variable browsing
  - Every SpectralArray, EffectivePSF, MTF, kernel has .plot()

Give me complete interface definitions and 20+ usage examples covering
common workflows.

Document name: RADIANT_Scripting_API.md
```

### Prompt 5.3 — GUI architecture

```
Design the GUI architecture. Not implementing yet — just architecture
so the scripting API and GUI share the same backend.

1. Technology choice
   - Web (React + FastAPI backend)?
   - Native (PyQt, PySide)?
   - Notebook (Jupyter widgets)?
   Choose and justify based on the personas from Phase 1.

2. Layout
   - Title bar with file/edit/tools menu
   - Signal chain strip (source → atmosphere → optics → detector → scan)
   - Parameter panel (left)
   - Visualization area (center)
   - Tabbed detail panel (bottom): spectral, MTF, sweep, variable
     explorer, YAML, console

3. GUI-backend interface
   - GUI builds a Sensor object via the scripting API
   - parameter changes trigger .set() and .evaluate()
   - Live feedback (<100ms for most parameter changes)
   - Heavy computations shown in progress indicator

4. Interoperability
   - Config built in GUI saves to YAML
   - YAML loaded by scripting can be opened in GUI
   - Both views of the same model

5. Deferred to Phase 2
   - Actual implementation

Produce the architecture document and a mockup sketch (ASCII or text
description of layout).

Document name: RADIANT_GUI_Architecture.md
```

---

## PHASE 6 — NON-FUNCTIONAL (2 prompts)

### Prompt 6.1 — Testing, validation, provenance

```
Design the testing strategy and validation framework.

1. Test hierarchy
   - Level 0: physics correctness (Planck, diffraction, noise stats)
   - Level 1: module-level (each module against known cases)
   - Level 2: end-to-end (full chain against reference scenarios)
   - Level 3: regression (frozen golden results)

2. Reference cases
   List 10+ validation scenarios with known-good results from
   literature or from trusted tools (MODTRAN, Zemax).

3. Numerical tolerances
   - What's "close enough" for each test?
   - When can tests fail due to legitimate physics changes?
   - How do we update golden results intentionally?

4. Provenance tracking
   - Run ID
   - Config hash
   - Data hashes (input files)
   - Software version
   - Dependency versions
   - Timestamp
   - Should enable reproducibility from any result

5. Error handling philosophy
   - Every error explains: what, why, what to do
   - No silent failures
   - Progressive disclosure (summary → details)
   - Validation happens early (before expensive computation)

Document name: RADIANT_Testing_Validation.md
```

### Prompt 6.2 — Plugin system and extensibility

```
Design the plugin/extension system. Users should be able to:
  1. Add custom source models
  2. Add custom atmosphere models
  3. Add custom metrics
  4. Add custom detector models
  5. Add custom file formats

For each:
  - Base class or Protocol to implement
  - Registration mechanism (decorator? manifest file?)
  - Discovery (how does the framework find plugins?)
  - Namespace conflicts (what if two plugins define the same name?)
  - Testing (how do plugin authors validate their plugins?)

Also:
  - Expression-based custom metrics (user can write a metric as a
    Python expression with parameter references)
  - User-provided spectral libraries
  - User-provided sensor templates

Document name: RADIANT_Plugins.md
```

---

## PHASE 7 — MASTER DOCUMENT AND IMPLEMENTATION PLAN (2 prompts)

### Prompt 7.1 — Master architecture document

```
Synthesize everything into a single master architecture document that
serves as the entry point for anyone coming to this project.

Include:
  1. What is RADIANT (1 paragraph)
  2. Document map (table of all architecture docs with when to read each)
  3. Key architectural decisions (12-15 non-negotiable constraints)
  4. Scope summary (in/out/stubbed)
  5. How documents relate (supersession table for conflicts)
  6. Implementation order (dependency-correct phasing)
  7. Rules for implementers (coding standards, testing, error handling)

This document should be 5-10 pages. It's the thing someone reads
FIRST. Every other document is a reference they consult as needed.

Document name: RADIANT_Master_Architecture.md
```

### Prompt 7.2 — Phase 1 implementation plan

```
Produce the Phase 1 implementation plan.

For each phase (1a through 1e), specify:
  1. Deliverables (specific files and features)
  2. "Done" criteria (concrete, testable)
  3. Dependencies (what must be complete first)
  4. Estimated effort (hours or weeks)
  5. Risks and mitigations
  6. Which developer or agent does what (if multi-agent)

Also produce:
  1. A CLAUDE.md for coding agents with all architectural rules
  2. A developer quickstart (how to set up, run tests, contribute)
  3. A sequencing diagram showing which modules can be built in
     parallel vs must be serial

Document name: RADIANT_Phase1_Plan.md
Document name: CLAUDE.md
Document name: DEVELOPMENT.md
```

---

## META: What Makes This Sequence Better

### Key improvements over the ad-hoc approach

1. **Physics inventory BEFORE design.** Prompt 1.1 forces enumeration
   of all physics up front. In our first attempt we discovered noise
   sources, motion sources, and stray light reactively — each one
   triggered architecture updates. Front-loading prevents this.

2. **Unified subsystems instead of split ones.** Prompt 3.1 designs
   sources AND targets AND materials together. Prompt 3.3 designs all
   of optics (including stray light) together. Prompt 3.5 designs
   all of the detector (including TDI, binning, coadds, readout)
   together. In our first attempt we built these separately and then
   had to unify — multiple rounds of "oh wait, we also need...".

3. **Each prompt has ONE deliverable.** No prompt produces three
   documents. Each prompt focuses on one subsystem or decision.

4. **Explicit "what are we missing" checkpoints.** Prompt 3.5 asks
   "did I miss any noise sources? Think carefully — persistence,
   image lag, cosmic rays..." This prompts the LLM to enumerate
   rather than take the user's list at face value.

5. **Scope decisions FIRST.** Phase 1 locks scope before any physics
   is designed. Prevents "we should also model X" during design.

6. **Personas drive decisions.** Phase 1 includes use cases so design
   decisions have concrete justification. Avoids abstract debates.

7. **Physics before UI.** UI/scripting/GUI are Phase 5. Tempting to
   design UI early (it's fun) but it depends on the data model being
   locked. In our first attempt we did GUI mockups before the final
   noise model.

8. **Master document LAST.** Written after everything else. In our
   first attempt we kept trying to write master documents while
   architecture was still churning.

9. **Phase 1 implementation plan LAST.** Only after all architecture
   is complete. This plan can then confidently sequence the work
   because nothing is undefined.

### What's still hard

Even with this sequence, the LLM will need the human to:

- Make judgment calls on borderline scope items
- Catch errors (LLMs will hallucinate physics occasionally)
- Push back when the LLM is being too verbose or too abstract
- Stop the LLM when it's over-engineering (ask "is this needed for v1?")
- Validate references to external tools (MODTRAN, Zemax, HITRAN) are real

The human is the scope-keeper. The LLM is the scribe and the physics
reviewer. This division of labor is what makes the sequence work.

### Estimated effort comparison

| Phase | First attempt | Optimized |
|-------|-------------|-----------|
| Framing and scope | scattered throughout | 2-3 hours |
| Core abstractions | 4-5 hours | 3-4 hours |
| Physics design | 12-15 hours | 6-8 hours |
| Metrics | 2-3 hours | 1-2 hours |
| UI/API | 4-5 hours | 2-3 hours |
| Non-functional | scattered | 1-2 hours |
| Master doc and plan | scattered | 1-2 hours |
| **Total** | **~30+ hours** | **~15-20 hours** |

The optimized sequence is roughly 40-50% faster because it doesn't
circle back. Every decision is made once, in the right order, with
full context.

### Recommended tools

- Run this in Claude Opus (the most capable reasoning model)
- Use a project with ALL physics references uploaded (IR handbooks,
  EMVA 1288, GIQE-5 paper, etc.) so the LLM can cite them
- Save every output to files as you go
- Stop and review after every 2-3 prompts — catch errors early
- Don't let the LLM produce 5000-line documents. Cap each at ~1000
  lines. If it wants more, split into sub-documents.
