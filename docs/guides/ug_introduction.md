# Introduction

RADIANT predicts how well an electro-optical sensor will see a scene, from the physics
up. You describe the geometry, the scene, the air in between, and the instrument; it
returns signal-to-noise ratio, noise-equivalent temperature difference, ground sample
distance, the system modulation transfer function, image-quality ratings, saturation
margins, and the detection ranges that follow from them — each with its units, each
traceable to the stage that produced it.

This volume is the operator's manual. It assumes you want to *use* RADIANT rather than
extend it: install it, drive the desktop application, describe a sensor, run it, and read
the answer. The physics behind each number is Volume I (*Theory Manual*); the scripting
API, YAML format, and parameter reference are Volume III (*Technical Reference*); worked
examples and validation evidence are Volume IV.

## 1. What RADIANT computes

RADIANT is a **signal-chain model**. A single evaluation walks ten stages in order,
each handing its outputs to the next:

| # | Stage | What it settles |
|---|---|---|
| 1 | Geometry | where the sensor and target are; ranges, angles, ground sampling, motion |
| 2 | Source | the spectral radiance leaving the target and its background |
| 3 | Atmosphere | transmittance and path radiance along each leg |
| 4 | Optics | the pupil, the point-spread function, throughput — and the final regime |
| 5 | Platform | jitter and smear, as blur on that PSF |
| 6 | Spectral Integration | the collapse from spectra to electrons in a pixel |
| 7 | Detector | quantum efficiency, dark current, and most of the noise-term budget |
| 8 | Readout | TDI, co-adds, gain, full well, analog-to-digital conversion |
| 9 | Calibration | post-correction residuals, drift, and the bias budget |
| 10 | Performance | SNR, NEDT, NIIRS, MTF budgets, margins, detection range |

Two properties of that chain matter to you as an operator:

**Nothing is fitted.** Every quantity is computed from a governing equation with named
inputs. When a number surprises you, there is a stage whose outputs explain it, and the
application will show you those outputs rather than asking you to trust the headline.

**Nothing is hidden.** Every tunable quantity is a *parameter* with a schema entry — a
canonical unit, bounds, a description, and a recorded provenance saying whether the value
came from your configuration, from a schema default, from a part preset, or from a
derivation. A run you cannot reproduce is a defect, not a fact of life.

RADIANT deliberately does **not** do some things. It is not an optical design code: it
takes a wavefront-error budget, a Strehl ratio, or a pupil description, not a lens
prescription, and it does not ray-trace. It is not a scene generator: it models radiance,
not rendered imagery. It does not require MODTRAN — reference atmospheres ship with the
tool — though it will ingest MODTRAN output when you have it.

## 2. Who it is for

RADIANT is built around seven working archetypes. You will recognize yourself in one or
two of them; the application is arranged so that each can reach their own question without
first learning everybody else's.

| Archetype | The question they arrive with | What they mostly touch |
|---|---|---|
| Systems engineer | "What aperture buys me SNR ≥ 50 on this target, and where is the knee?" | Optics, sweeps, the performance cards |
| Detector engineer | "Which noise term dominates, and at what integration time does that change?" | Detector, Readout, the noise budget |
| Mission planner | "Can this existing sensor see that target, on this pass, in this weather?" | Geometry, Atmosphere, pass/fail margins |
| Detection analyst | "Give me a detection-range matrix over targets, atmospheres, and sensors." | Configuration sets, batch runs, exported tables |
| Optical designer | "How does my WFE budget compose with detector, jitter and smear at Nyquist?" | Optics MTF and PSF, MTF budget, RER |
| Researcher | "Show me every intermediate value so I can benchmark it against my own model." | The Inspector, scripting, provenance records |
| Test engineer | "The bench measured 22 mK and the model says 18 mK — which term is the gap?" | Lab-style scenes, calibration terms, per-term noise |

Three consequences of that spread are visible throughout the interface. Inputs are
**flexible** — you may specify a viewing geometry by path zenith, by off-boresight angle,
by ground range, by elevation angle, or by slant range, because different disciplines
carry different numbers in their heads. Outputs are **granular** — every intermediate is
readable, not just the headline metric. And **defaults are sensible but never silent**:
the parameter you did not set is marked `default` wherever it appears, so nothing you did
not choose can quietly masquerade as something you did.

## 3. Three radiometric regimes

The single most consequential thing RADIANT decides about your scene is its **radiometric
regime** — how the target's energy couples into a pixel. There are three, and almost every
mission is one of them:

| Regime | The scene | What follows |
|---|---|---|
| **Extended** | the target fills the pixel footprint and then some | signal is radiance integrated over the pixel solid angle; the ensquared-energy fraction is reported as a spatial metric, not applied to the signal |
| **Sub-pixel** | the target is smaller than a pixel but larger than the blur spot | the pixel sees a weighted mix of target and background; ensquared energy is applied to the target term only, never to the background |
| **Point-source** | the target is smaller than the diffraction limit | the target is an intensity, not a radiance; ensquared energy sets how much of the PSF lands in the central pixel |

Terrain, water, cloud tops and canopy are extended. A vehicle or a small vessel viewed from
orbit is sub-pixel. A star, a distant plume, or a glint is a point source.

**The regime is classified for you.** You do not select a mission type; the chain works it
out from the scene you described. It happens in two steps:

1. The **Source** stage forms a *tentative* classification from the target's angular extent
   against the pixel instantaneous field of view — with a declared fill fraction below 1
   forcing sub-pixel, and an explicit `source.regime_override` winning over the comparison.
   It publishes the result as `regime_tentative`.
2. The **Optics** stage makes the *final* call, once the actual PSF is known, and publishes
   it as the `regime` output of that stage. Every later stage reads that one value.
   Nothing re-classifies afterwards.

Both are on screen. The Source workspace's *Scene & regime* tab shows the tentative
classification beside the angular extent and range it was formed from; the Optics
workspace's *Inputs* tab shows the final `Regime:` line among the derived optics outputs.
When the two differ, the optics stage is telling you that the blur spot changed the answer.

Two doors let you steer the classification rather than fight it. `source.scene_type`
*declares* what kind of scene you believe you have — the application uses the declaration
to decide which inputs are relevant, and warns if the derivation disagrees.
`source.regime_override` *forces* a regime outright, for the case where you know the
classifier's inputs are the thing that is wrong. Both are ordinary parameters, both carry a
provenance badge, and both are visible on the *Scene & regime* tab.

Regime matters because it changes the answer, not just the vocabulary. An extended target
evaluated as a point source loses signal to an ensquared-energy fraction it should never
have paid; a point source evaluated as extended gains signal it never collected. A
surprising SNR is worth one glance at the regime line before it is worth anything else.

## 4. How this volume is arranged

Chapters 1–6 take you from an empty machine to a described scene:

- **Chapter 2, Installation & Launch** — Python, the install, the extras, and starting the
  application on Windows and macOS.
- **Chapter 3, Quickstart Tour** — one evaluation end to end in the graphical application,
  then the same run from YAML and the command line.
- **Chapter 4, Core Concepts** — the vocabulary the rest of the manual assumes: stages,
  parameters, units and display symmetry, provenance, regimes, configurations.
- **Chapter 5, The Main Window** — every part of the application window, what it is for,
  and how the evaluate loop behaves.
- **Chapter 6, Defining the Scene** — geometry, target and background, atmosphere.

Later chapters describe the sensor side (optics, platform, detector, readout,
calibration), configuration sets, running and reading results, sweeps and trade studies,
the YAML round-trip, and troubleshooting.

Throughout, values are quoted exactly as the application shows them, in the display unit it
shows them in. Figures are captures of the real application, generated by driving it with a
committed configuration file; regenerating the whole figure set is one command, so a
screenshot in this manual is a statement about the shipped build rather than a memory of an
older one.
