# Core Concepts

Five ideas carry the rest of this manual: the **chain** of ten stages, the **parameters**
that feed it, the **units** those parameters are entered and displayed in, the
**provenance** that says where each value came from, and the **regime** the chain classifies
your scene into. A sixth — **configurations** — matters as soon as you model more than one
version of an instrument. This chapter defines each from the operator's seat.

## 1. The chain, stage by stage

Every evaluation runs the same ten stages in the same order, each consuming what the ones
before it produced. The application's stage strip *is* that order, so moving left to right
through the strip is moving forward through the physics.

| # | Stage | What its workspace lets you say | What it hands on |
|---|---|---|---|
| 1 | **Geometry** | where the sensor and target are, how the line of sight is specified, the sun, platform motion, target size and shape | slant and ground range, path zenith, off-nadir, solar angles, GSD, ground speed, the scene class |
| 2 | **Source** | target and background temperature and emissivity, reflectance, point-source intensity, declared scene type | the spectral radiance leaving target and background, and a tentative regime |
| 3 | **Atmosphere** | which atmosphere model, its knobs, the turbulence parameter $r_0$ | transmittance and path radiance per leg |
| 4 | **Optics** | aperture, focal length, obscuration, spiders, wavefront error, optics temperature, how throughput is defined | the complex pupil, the PSF, optical MTF, collecting area, **the final regime** |
| 5 | **Platform** | jitter RMS, ground velocity, smear length | jitter and smear kernels on the PSF, the ensquared-energy fraction |
| 6 | **Spectral Integration** | the filter band edges and the integration time | electrons per pixel: signal, background, contrast |
| 7 | **Detector** | pixel geometry, QE, dark current and glow, 1/f, fixed-pattern terms, IPC and diffusion — or a part from the FPA preset library | the per-term noise budget and the detector MTF terms |
| 8 | **Readout** | read noise, gain, ADC depth, full well, TDI, co-adds, binning, frame timing, readout architecture | the digitised signal, well fill, quantisation |
| 9 | **Calibration** | the calibration scheme and its cal points, drift, source and gain uncertainty | post-correction residual noise and the bias budget |
| 10 | **Performance** | which metric groups to compute | SNR, NEDT, NIIRS, MTF budgets, margins, detection range |

Some stages are one pane; some are tabbed because their content genuinely separates:

| Stage | Tabs |
|---|---|
| Geometry | *Inputs* · *Schematic* |
| Source | *Scene & regime* · *Target — thermal* · *Target — point source* · *Target — reflective* · *Background & contrast* |
| Optics | *Inputs* · *Transmission* · *MTF* · *PSF + Pupil* |
| Platform | *Inputs* · *PSF degradation* |
| Detector | *Inputs* · *Noise* · *Detector + PSF* |
| Atmosphere, Spectral Integration, Readout, Calibration, Performance | single pane |

Whatever the shape, every workspace is built the same way: **Inputs** (the stage's editable
parameters), **Outputs** (what the stage computed, read-only, each with its unit), and
**Plots** (that stage's figures). If you want to know what a stage did, its Outputs section
is the answer — not the headline metric three stages downstream.

Two ordering rules are worth carrying:

- **The regime is settled in Optics** and never revisited (§5).
- **Spectral integration happens exactly once.** Before stage 6 every quantity is a spectrum;
  after it, electrons. That is why the band edges and the integration time live together on
  one screen, and why a per-wavelength noise spectrum does not exist to be shown: noise is
  computed per term after the collapse.

## 2. Parameters

Everything tunable is a **parameter** with a dotted name — `optics.aperture_diameter_m`,
`geometry.sensor_altitude_m`, `detector.pixel_pitch_x_um`. Nothing in the physics is a
hardcoded number that you cannot see and set.

Each parameter carries a schema entry: a data type, a **canonical unit**, the unit it is
normally entered in, bounds, a description, and a default (or a statement that it is
required). The application reads every field, label, editor and unit suffix from that
schema, which is why a parameter added to the model appears in the tree without anybody
updating the interface — and why this manual does not reproduce the list. The full
enumeration is generated from the code: Volume III's parameter reference.

Three behaviours follow from the schema and are visible everywhere:

**Validation happens before computation.** An edit is checked — type, bounds, enumeration
membership, consistency-group sanity, cross-parameter over-specification — before it reaches
the live model. A rejected value never sticks: the row keeps its old value and the rejection
is shown as *what / why / action*.

**Derived parameters are computed, not typed.** `optics.f_number` belongs to a consistency
group with aperture diameter and focal length: supply any two and the third is derived. A
derived row is marked with a lightning bolt, badged `derived`, and is read-only. Trying to
edit it is not the way to change it; change one of its inputs.

**One action is one change.** Each committed edit is exactly one parameter assignment, the
same call a script would make. There is no hidden batch, no Apply button to forget, and
nothing that changes two things because it seemed convenient.

## 3. Units, and the display-symmetry rule

RADIANT's internals are canonical: wavelength in µm, angles in radians, time in seconds,
length in metres, radiance in W/m²/sr/µm, noise in e- RMS, temperature in K. Conversions
happen exactly once, at the boundary where you type a value or a file is read. No physics
module converts units.

That is the internal story. The rule that matters to you is the opposite one:

> **The application shows values in the unit you chose.** If you enter an altitude as
> 500 km, the row reads `500 km` — not `500000 m`. Entry and display are symmetric, and the
> unit is always part of the displayed string.

The mechanism is a per-row display unit, remembered for the session. Open the full parameter
editor on a dimensional parameter and it offers a unit selector built from the conversions
the framework actually supports (never a hand-written list), with a live preview of the
canonical result — type `8`, choose `km`, and the preview confirms `= 8000 m`. Commit, and
from then on that row displays in kilometres, including when you type into it inline: typing
`550` into a km-displaying row stores 550 000 m.

Angles get their own switch, because radians are canonical and nobody thinks in them:
**View ▸ Angles in Degrees** is on by default and persists across launches. It is display
only — the stored value is unchanged — which is why the figures in this manual show
`path_zenith_rad` reading `0 deg` and `solar_zenith_rad` reading `28.6479 deg`.

Metric cards scale for legibility on the same principle: NEDT renders in mK, a 2.13 × 10⁻⁵ m
FWHM renders as 21.3 µm, and a dimensionless ratio renders as a bare number. One metric shows
one unit everywhere on screen.

## 4. Provenance: where a value came from

Every resolved parameter knows its origin, and the *Source* column in the Parameters dock
shows it.

| Badge | Meaning |
|---|---|
| `config` | the configuration file set it |
| `user-set` | you set it in this session |
| `default` | nobody set it; this is the schema's value |
| `derived` | computed from other parameters (⚡, read-only) |
| `preset` | supplied by an applied part preset, such as an FPA from the part library |
| `sampled` | drawn by a Monte-Carlo tolerance run |

![The Parameters dock, widened so the full dot-paths are legible: filter box and
*Changed only* switch above a Parameter / Value / Source tree.](figures/gui/ug_parameter_dock.png)

Provenance is not decoration. It is the answer to "did I actually specify that, or is the
model carrying a default I never looked at?" — the question behind most surprising results.
It is also what keeps saved files small and honest: **Save** writes the values you chose, not
the two hundred the model resolved, so the schema stays free to improve underneath your
configuration.

Two aids sit with it in the dock: the **filter box**, which narrows the tree by substring
across dot-paths, and the **Changed only** switch, which hides everything still at its
default — the fastest way to see your configuration as a short list.

## 5. Radiometric regimes, as classified

Chapter 1 introduced the three regimes. Here is what the application does with them.

**Classification is automatic and happens in two steps.** The Source stage forms a tentative
regime; the Optics stage makes the final call once the PSF is known; every downstream stage
reads the final one. You do not declare a mission type to get this — the chain derives it
from the scene you described.

The tentative step compares the target's angular extent $\theta = \sqrt{A_t}/R_s$ (slant range, not Earth radius) against the
pixel's instantaneous field of view $\mathrm{IFOV} = p/f$, in this order:

1. a declared `source.target.fill_fraction` below 1 means **sub-pixel**;
2. otherwise an explicit `source.regime_override` wins outright;
3. otherwise $\theta \ge 2\,\mathrm{IFOV}$ is **extended**, $\theta \le 0.25\,\mathrm{IFOV}$
   is **point-source**, and anything between is **sub-pixel**.

![The Source workspace's Scene & regime tab: the declared scene type and regime override
above the stage's outputs, including the tentative classification.](figures/gui/ug_source_scene_regime.png)

The figure is the minimal MWIR example. No target area was given, so the angular extent
reads `∞`, the fill fraction is 1, and the tentative regime is `extended` — a scene that
fills the pixel by construction. The final regime appears as the `Regime:` line among the
Optics workspace's outputs; when it differs from the tentative one, the optics stage is
telling you the blur spot changed the answer.

**Why it matters.** The regime decides where the ensquared-energy fraction is applied:
nowhere in an extended scene, to the target term only in sub-pixel and point-source scenes,
and never to the background. Evaluate an extended target as a point source and it pays an
aperture loss it never suffered; evaluate a point source as extended and it collects signal
it never had. Before investigating an implausible SNR, look at the regime.

**Steering it.** `source.scene_type` *declares* the kind of scene you believe you have, which
the application uses to decide which inputs are relevant — and which the chain checks against
its own derivation, warning if the two disagree. `source.regime_override` *forces* the
classification. Both are on the *Scene & regime* tab, both are ordinary parameters, and both
carry a provenance badge, so a forced regime can never be mistaken for a derived one.

## 6. Configurations

Most studies are not one instrument — they are one instrument with variations: nine spectral
bands of the same telescope, two detector choices, three integration times.

RADIANT models that the way an optical design code models zoom positions. A session is a
**configuration set**. A parameter is **shared** — one value for every configuration — until
you explicitly *configure* it, at which point it carries one value per configuration. A
study therefore records what differs, not what is repeated, and a shared edit moves every
configuration at once.

![The configuration selector on a nine-band study: one accent-chipped tab per configuration,
with the manager beside it.](figures/gui/ug_configuration_bar.png)

Four consequences:

- A plain configuration file loads as the **degenerate one-configuration set**. The selector
  band is not merely empty, it is absent, and the session behaves exactly like a
  single-model session. You pay nothing for a capability you are not using.
- A file carrying a `configurations:` section loads as a full study through the same
  **File ▸ Open** — there is no separate "open study" action.
- A set holds at most **12** configurations. Beyond that the refusal states the cap.
- Switching the selected configuration re-renders every surface — workspaces, forms,
  readouts, the parameter tree, the pinned cards — from the retained results. It evaluates
  nothing, because a study evaluates all its configurations in one pass.

Chapter 8 covers the configuration manager, promoting and demoting parameters, and the
side-by-side comparison view.

## 7. Metrics, groups, and honest failures

The Performance stage computes metrics in five groups — *Sampling / geometry*, *Spatial /
MTF*, *Radiometric*, *Interpretability*, *Saturation* — and the `Compute:` row selects which
of them the chain produces. Deselecting a group stops its computation, which is how you buy
back time on an expensive configuration; it is not a display filter.

Two behaviours are worth expecting in advance:

**A metric that cannot be computed says so.** RADIANT's metric layer is allowed to return a
named failure instead of a number, and the interface never fills the gap with a blank, a
zero, or a stale value. A card reads `n/a — not computed for this run` whenever the run
produced no value for that metric at all: because its group is switched off, because the
scene class does not populate it, or because the metric declined to answer. It reads
`n/a (<reason>)` in the narrower case where a value *was* produced but is not a usable
number, and the failure carries a name.

NIIRS on a 0.12 m thermal scene is the common case of the first form. The GIQE-5 regression
is out of its calibration range, so the tool declines rather than extrapolating, and emits
no NIIRS value — which is why the card says *not computed* rather than naming the range.
The full explanation is on the run itself, in `stage_outputs["performance"]["niirs_result"]`
(`failure_reason`), and `performance.niirs.allow_extrapolated = true` opts back into the
extrapolated number, still flagged.

**A warning is never swallowed.** Chain warnings — saturation clipping, an extrapolated
rating, an atmosphere model used outside its comfortable band — are captured with the result
and listed in the Messages panel, verbatim, one row each. Errors land in the same place with
their *what / why / action* text. The rule behind this, throughout RADIANT, is that
undefined physics stops or speaks; it never quietly returns a plausible number.

## 8. One action, one call

A last principle that will save you time: **every action in the application is exactly one
call of the public scripting API**. Editing a field is a parameter set. Opening a file is a
load. Running a sweep is a sweep call. Applying an FPA preset is one apply.

This is why anything you can do in the window you can also do in a script and in a YAML file,
with identical results, and why this manual can hand you off to Volume III without a
translation table. The application is a view over the same model, not a second
implementation of it.
