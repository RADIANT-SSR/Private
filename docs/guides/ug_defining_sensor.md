# Defining the Sensor

Five stages describe the instrument: **Optics** (what collects the light and how well),
**Platform** (how steady the line of sight is), **Detector** (what converts photons to
electrons, and what noise comes with them), **Readout** (what turns electrons into counts),
and **Calibration** (how much of the residual error survives correction). They run after the
scene stages of chapter 6, and each one takes the frame it was handed and degrades it in a
specific, named way.

This chapter walks the five workspaces in chain order. Spectral Integration sits between
Platform and Detector in the strip and is covered in chapter 4, §1 — it owns the band edges
and the integration time, and collapses the spectrum exactly once.

## 1. Optics

Four tabs: **Inputs · Transmission · MTF · PSF + Pupil**. Two of them are where you type, and
two are diagnostics — pictures of what you typed.

### 1.1 Inputs

![Optics workspace, Inputs tab, on the Landsat 9 TIRS band-10 baseline — aperture and
wavefront-error fields above the stage's derived outputs.](figures/gui/ug_optics_inputs.png)

The card's title says what is here and, more usefully, what is not:
*Optics — aperture and wavefront error (transmission: Transmission tab)*.

**Aperture geometry.** Aperture diameter, focal length and f-number form a consistency group:
give any two and the third is derived, and the derived one shows the ⚡ marker and the
`derived` badge. In the figure, `aperture_diameter_m = 0.1085 m` and `focal_length_m = 0.178 m`
come from the config and `f_number = 1.64055` is derived from them. Give all three and the
evaluation rejects the set unless they agree to within the group's tolerance — chapter 12, §3
shows the message.

**Obscuration and spiders.** `obscuration_ratio` is the linear ratio of the central
obstruction, and `n_spiders` / `spider_width_m` / `spider_angle_deg` describe the support
vanes. These are not cosmetic: they enter the **complex pupil function**, which is what both
spatial paths are built from, so a spider changes the PSF wings and the mid-frequency MTF
together.

**Wavefront error.** Two ways to say it, and they are not additive alternatives — the richer
one wins:

| Input | What it means |
|---|---|
| `wfe_rms_waves` + `wfe_reference_wavelength_um` | a scalar RMS wavefront error at a stated reference wavelength |
| `zernike_file` | a Zemax *Zernike Standard Coefficients* export, term by term |

**Import Zemax Zernike…** under the fields is the confirm-before-apply path: pick the export,
read a summary of what was parsed — the term count, the non-piston RSS in waves, and whether
the report carried its own reference wavelength — and only on *Yes* is `optics.zernike_file`
set. A Zernike wavefront **supersedes** the scalar WFE; the dialog says so before it commits.
`defocus_um` is a separate, always-available term folded into the same wavefront.

**Optics temperature is not here, and that is deliberate.** There is no single
`optics.optics_temperature_K` any more. Temperature is a property of an *element*, and it
lives on the rows of the element train, one value per surface — a warm filter and a cold
mirror are different sources of in-band emission, and one scalar could not say that.

Below the inputs, the stage's outputs include the one classification the whole downstream
chain reads: **`Regime`** (`extended` in the figure). The Optics stage is where the
radiometric regime is finalized; nothing downstream re-decides it.

### 1.2 Transmission — one home for optical throughput

![Optics workspace, Transmission tab, in Scalar throughput mode — the mode selector, the
banner stating which definition is in force, the single τ_opt field, and the flat τ_opt(λ)
it produces.](figures/gui/ug_optics_transmission_scalar.png)

Optical transmission has exactly two definitions and they are mutually exclusive, so the tab
leads with a segmented control — **TRANSMISSION DEFINED BY: Scalar throughput | Element
train** — and a banner in plain words underneath:

```text
Scalar throughput defines transmission — τ_opt is flat across the band and no element
train is attached.
```

In element mode the banner instead reads *Element train defines transmission (N elements) —
scalar τ ignored*. That sentence is the whole reason these used to be two tabs and are now
one: with the scalar field on one tab and the element table on another, you could edit τ_opt,
watch SNR not move, and have no way to find out that an attached train was overriding it.

**The mode is read from the document, never invented.** A config with an `optical_elements:`
list opens in *Element train*; anything else opens in *Scalar throughput*.

**Switching modes is non-destructive within a session.** Leaving element mode detaches the
document but leaves the rows in the table, inactive, so you can A/B the two definitions
without retyping a train; switching back re-commits them. **Saving writes only the active
mode** — in scalar mode the file carries no `optical_elements:` section at all. While rows are
held inactive the banner says so, and the save confirmation adds a note naming how many rows
were not written. A file with an element list means element mode, full stop; there is no
hidden inactive state in any config RADIANT writes.

### 1.3 The element train

In *Element train* mode the tab shows a table, one row per surface from source to focal plane:

| Column | What it is |
|---|---|
| Name | your label for the surface; also part of the saved entry |
| Transfer mode | `REFLECTIVE` or `REFRACTIVE` — which side of the surface the signal leaves on |
| Kind | `MIRROR`, `LENS`, `WINDOW`, `FILTER`, `BEAMSPLITTER`, `DEWAR_WINDOW`, `COLD_STOP`, `LUMPED` |
| R or T | the defining value: reflectance for a reflective surface, transmittance for a refractive one |
| ε | **read-only** — the band-mean emissivity Kirchhoff gives you |
| Temperature | that surface's physical temperature, in kelvin |

**There is no emissivity input anywhere in this editor, and there never will be.** For an
optical surface, emissivity is a consequence of energy conservation — $\varepsilon = 1 - R$
for a mirror, $\varepsilon = 1 - T - R$ for a transmissive element — so it is derived and
shown, not accepted. (A *scene* material is the opposite case: there, emissivity is a real
material property you are entitled to state, which is why the Source stage takes it as an
input. Chapter 6, §2.2.)

The R/T cell accepts either a scalar (`0.97`) or a path to a spectral CSV
(`data/mirror_protected_ag.csv`) — the same two forms the YAML takes, resolved and validated
by the same parser.

**Edits commit as you make them.** A finished cell edit, a combo change, a *CSV file…* pick,
Add, Remove and reorder each write the document immediately, and the debounced re-evaluation
follows. There is no *Apply train* button and that is not an omission: the batched version
held drafts that looked committed, so an edit could be made, produce no visible change, and
be lost on navigation.

A row that is **transiently invalid** — a `REFLECTIVE` → `REFRACTIVE` flip before you retype
the value cell, a CSV path that does not resolve — is neither stored nor thrown away. It stays
in the table as a visible pending draft with the parser's actionable message inline beneath
the table (never a modal per keystroke), and it commits with the rest of the train on the next
edit that validates. Leaving the tab can discard a *pending* draft, and the inline message
says so. An edit that validated can never be lost, because it committed the moment you made it.

**Undo works on the train.** Every committed write records a whole-train before/after pair, so
`Ctrl+Z` steps back through element edits exactly as it does through parameter edits.

**In a study, a row configures like a parameter.** Right-clicking a row offers *Configure
across configurations…* and *Un-configure row…*; a configured row carries the red **C** after
its name and editing any of its cells writes only the displayed configuration's entry. The
train's *structure* — how many rows, in what order — stays shared across the whole study.
Chapter 8 covers the mechanics.

Under the table sits the **coating detail** drill-down (per-element R, T and ε against
wavelength) and, below the τ(λ) figures, the **cold-stop / effective-pupil** strip: the two
editable `optics.cold_stop_*` fields beside the $D_\text{eff}$, $f/\#_\text{eff}$,
$A_\text{collect}$ and $\Omega_\text{cone}$ they produce.

Two figures live on this tab, and which one is drawn follows the mode. In scalar mode it is
**System optical throughput τ_opt(λ)** — the flat line at 0.7 in the figure, which is the whole
model. In element mode it is **Per-element net τ and the SYSTEM product**: one curve per
element with the assembled τ_opt(λ) drawn bold over them, so a band edge you did not expect is
attributable to the surface that caused it.

### 1.4 MTF and PSF + Pupil — the diagnostics

Neither tab has an input on it. They exist so that what you typed on the first two tabs has a
picture.

**MTF** shows the system MTF overlay with Nyquist marked, and below the figure a per-term
budget table reading at four fractions of Nyquist in x and y. Each row is one contributor —
optics, detector aperture, jitter, smear, diffusion, IPC, turbulence, TDI mis-registration —
and the system curve is their product.

**PSF + Pupil** shows three 2-D maps on one row: pupil apodization (amplitude), pupil
wavefront error in waves, and the effective PSF. They are side by side because they are read
together — the pupil pair is the cause and the PSF is the effect. Raise the WFE on the Inputs
tab and the middle map gains structure while the right one spreads.

One thing to hold onto about these two tabs: the optical MTF is computed from the
**autocorrelation of that same complex pupil**, not by multiplying a diffraction term by an
aberration term. Aberrations and diffraction interact in the pupil and do not factor. What the
PSF map shows and what the MTF budget's optics row says are two views of one object.

## 2. Platform

![Platform workspace, Inputs tab, with an 8 µrad isotropic jitter entered — the jitter and
motion/smear knobs above the jitter σ, smear width and EE_box the stage derives from
them.](figures/gui/ug_platform_workspace.png)

Two tabs, and a deliberately small first one. Platform is deliberately small: there is no
dedicated MTF view here, because the jitter and smear MTF terms already appear in the Optics
MTF budget and the Performance surface, and a third place to read them would be a third place
to disagree.

**Jitter.** Either one isotropic RMS (`jitter_rms_urad`) or the anisotropic pair
(`jitter_rms_x_urad` cross-track, `jitter_rms_y_urad` along-track). In the figure an 8 µrad
isotropic jitter produces `Jitter sigma x = Jitter sigma y = 1.424e-06 m` at the focal plane —
the angular value times the focal length — and pulls MTF @ Nyquist from 0.3533 down to 0.3478.

**Motion & smear.** `ground_velocity_m_s` with the integration time gives the image-plane
smear, or you can state the focal-plane smear length directly (`smear_length_um`) when that is
the number you have.

The outputs block is the payoff: `Jitter sigma x`, `Jitter sigma y`, `Smear width`, and
**`Ee box`** — the ensquared-energy fraction computed here, from the *fully degraded* PSF, and
applied once downstream in Spectral Integration. `Ee box centered`, `Straddle factor` and the
three `Pixel phase` outputs beside it say where on the pixel grid the image was assumed to
land; section 3.3 of this chapter covers the sampling-phase modes.

The second tab, **PSF degradation**, draws the convolution kernels this stage applied beside
the PSF that came out of them. Its note is worth reading once: the PSF carries an accumulated
stack, so kernels contributed by Optics (optical, pixel aperture, charge diffusion) and by
Performance (IPC) appear here too, and each card names the stage that applied it. **Kernels
appear only for degradations you configured non-zero.** A scene with no jitter, no smear and
no turbulence contributes none, and the tab shows only what it inherited — that is the model
agreeing with your configuration, not missing data.

## 3. Detector

Three tabs: **Inputs · Noise · Detector + PSF**. The Inputs tab is the largest single form in
the application, because the detector is where the noise model lives.

![Detector workspace, Inputs tab — the FPA part-library row above the detector schema in
labeled groups, with no preset applied; the form continues past the foot of the
pane.](figures/gui/ug_detector_inputs.png)

### 3.1 The FPA part library

The strip across the top is the shortcut past the form beneath it:

```text
FPA part library   no part applied   [ Choose part & apply… ]  [ Open datasheet/paper ]
```

**Choose part & apply…** opens a sortable browser of the shipped parts — class, band, and a
census of what each value in the preset is *based on* (measured, datasheet, inferred) —
with a details pane. Accepting it makes exactly one call, and the strip is replaced by the
report:

```text
geosnap-18: 5 applied, 7 kept (explicit wins)
```

That is the real line from applying the 21-part library's `geosnap-18` to the minimal MWIR
example, and it tells you two things. **Applied** is how many parameters the preset supplied.
**Kept (explicit wins)** is how many it declined to overwrite because you or your config had
already set them — here the pitch, QE, ADC bits, full well, gain and read noise the example
states for itself. A preset never silently replaces a value you stated. On a blank
configuration the same part reports `12 applied` and nothing kept. A preset that carries a QE
curve adds a third clause naming the material it bound.

**Details…** opens the per-parameter provenance: which dot-paths were applied, which were kept
and why, the census of value bases in the preset document, and the citation titles. In the
Parameters dock the applied rows carry a `preset` source badge, so their origin is legible
from the tree as well.

**Open datasheet/paper** opens the part's reference document — the committed PDF when you are
working in a repository checkout, otherwise the citation's URL or DOI.

**Remove** clears the preset's values and returns you to a custom design. It keeps your
explicit edits, including ones you made *after* applying the preset. If the preset had been
supplying a parameter with no schema default — a pixel pitch, say — removing it leaves the
configuration legitimately incomplete, and the card says so in place of the status line:

```text
preset removed — set required parameter(s) for a custom design: detector.pixel_pitch_x_um
```

That is an advisory, not an error dialog: you are mid-way through building something, and the
application does not interrupt you with a modal for each parameter you have not typed yet.

### 3.2 The detector form

Below the strip, the full detector schema in labeled groups. The groups reflow into one or
two columns with the pane width; they never scroll sideways.

| Group | What it holds |
|---|---|
| Pixel geometry & temperature | pitch x and y, fill factor, cross-track pixel count, detector temperature |
| Pixel sampling phase | the straddle mode and the x/y image offsets it uses (section 3.3) |
| Quantum efficiency | scalar QE, a QE curve CSV, a library material, and the temperature coefficient/reference pair |
| Dark current & glow | dark rate with its reference temperature and activation energy, plus ROIC glow |
| 1/f noise | the coefficient $K$ and the band edges it is integrated over |
| G-R & Johnson noise | the HgCdTe G-R factor and the $R_0A$ product |
| Fixed-pattern noise & regime | PRNU, DSNU, clutter σ, and the noise regime selector |
| Persistence | fraction, time constant, and the prior-frame signal it acts on |
| IPC & diffusion | the inter-pixel coupling α and the charge-diffusion length |

Two buttons sit under the QE group. **Define QE(λ) table…** lets you type or paste a
wavelength-versus-QE table; the points are written to a CSV of your choosing and bound as
`detector.qe_table_path`. **Import QE curve (preview)…** takes a vendor CSV, shows you what
was parsed — including which units the header was auto-detected as — and binds it only on
Apply. Both end at the same parameter, and both produce an ordinary file you can re-import
anywhere.

The **Noise** tab shows the noise budget as a log-scale bar beside the per-term table, with
click-to-explain on each term. The **Detector + PSF** tab draws the pixel itself — a
not-to-scale schematic labeled with its pitch and fill factor — beside the convolution kernel
that pixel imposes, with the PSF and the pixel grid overlaid below.

### 3.3 Pixel sampling phase

A point source does not land politely on a pixel center. Where it lands changes how much of
its energy one pixel collects, and therefore the ensquared-energy fraction the chain applies
— by tens of percent between the best and worst placement. The **Pixel sampling phase** group
is where you say which placement the run should assume. It affects the point-source and
sub-pixel regimes only; an extended scene has no single image point to place.

`detector.pixel_phase_mode` takes four values:

| Mode | What it assumes | When to use it |
|---|---|---|
| `average` | the phase is unknown, so the result is the expectation over one pitch | the default, and the right answer for a source you cannot place — a survey, a detection study, a link budget |
| `centered` | the image sits on a pixel center | the best case; use it to bound the optimistic end, or when a tracker really does keep the target centered |
| `worst_case` | the image sits on a four-pixel corner, straddling all four | the pessimistic bound; the number to quote when the requirement must hold for any placement |
| `specified` | the image sits where you say | a measured or simulated placement; `detector.pixel_phase_x` and `pixel_phase_y` carry the offset from the pixel center as a fraction of the pitch, each in the range −0.5 to +0.5 |

The Platform workspace reports what the choice cost you: `Ee box` is the fraction under the
mode you picked, `Ee box centered` the fraction the same PSF would give on a pixel center, and
`Straddle factor` is their ratio. A straddle factor of 1.00 means you asked for the centered
case; the further below 1.00 it sits, the more energy the assumed placement spills into
neighbouring pixels.

Two cautions. The default `average` is the *expectation*, not the middle of the range, and it
is what earlier versions of RADIANT computed — so it is the mode that keeps old numbers
comparable. And the offsets are measured from the geometric image point, the chief ray, not
from the centroid of the blurred spot; on an asymmetric PSF those are not the same place.

## 4. Readout

![Readout workspace on the Landsat 9 OLI-2 band-4 config — architecture, read noise, ADC, full
well, TDI, co-adds, binning and acquisition groups above the DN and noise
outputs.](figures/gui/ug_readout_workspace.png)

One pane, grouped in reading order, and **the first group decides what the rest of the screen
means**.

### 4.1 Architecture

`readout.architecture` takes two values:

| Architecture | What it models |
|---|---|
| `analog_well` | the conventional charge well: electrons accumulate, an ADC digitizes the result |
| `digital_counting` | a digital-pixel ROIC: charge packets are counted in-pixel, with an optional residue ADC |

The form follows the choice rather than showing you everything at once. Under
`analog_well` — the figure's case — the **Full well** and **ADC → Conversion gain** rows are
live and the *Digital counting* group is absent. Switch to `digital_counting` and that group
appears (counter depth, charge packet, residue readout, max count rate, counting mode), while
full-well capacity and conversion gain **disappear**, because under counting they are not
inputs: the effective well is $2^N \times$ packet and the DN gain derives from the packet.
`adc_bits` stays visible in both, meaning the residue-ADC depth under counting.

The form hides those rows rather than greying them because the stage *rejects* them there —
an explicit full well under counting is an over-specification error. Showing an input that can
only be refused would be an invitation to a rejected edit.

Selecting `counting_mode = up_down` reveals one further contextual group, **Reference
(up/down)**: the reference source, and — only when that source is `user_level` — the reference
rate and integration time.

### 4.2 The rest

| Group | Fields |
|---|---|
| Read noise | per-frame read noise, e- RMS |
| ADC | conversion gain (e-/DN), bit depth |
| Full well | saturation capacity, e- |
| TDI | stage count, mode, cross-scan misalignment in pixels |
| Co-adds | frame count, combination mode |
| Binning | on-chip and off-chip factors, x and y |
| Acquisition | integration time, frame period |

**On-chip versus off-chip binning is a real distinction, not a labeling one.** On-chip binning
sums charge before the read, so the read noise is paid once for the binned pixel; off-chip
binning sums after, so each contributing pixel brings its own read noise. The two give
different SNR for the same binning factor.

**TDI misalignment** is the one MTF term in the model with no spatial kernel behind it. It is a
readout-timing effect — line-to-line registration error across the TDI stages — so it enters
the MTF product and nothing else.

**Integration time appears on this screen and on Spectral Integration, and it is one
parameter.** The schema owns it at `spectral_integration.integration_time_s`, because that is
the stage that consumes it; it is mirrored here because this is where operators look for it.
Both surfaces edit the same dot-path and refresh together. **Frame period** is readout's own:
leave it at `0 s` and it defaults to the integration time, giving a duty cycle of 1.0; the
derived frame rate and duty cycle appear in the outputs.

## 5. Calibration

![Calibration workspace with a one-point scheme active — the scheme selector and the groups it
reveals, beside the residual, drift and bias
outputs.](figures/gui/ug_calibration_workspace.png)

The last stage before Performance, and the one most likely to be the reason your NEDT stops
improving when you integrate longer.

### 5.1 The scheme selector

`calibration.scheme` steers everything else on the screen.

| Scheme | What it models | What the form shows |
|---|---|---|
| `none` (default) | the model is off; PRNU and DSNU act as static dispersions, exactly as before this stage existed | the selector alone |
| `one_point` | offset correction at a single known cal source | cal points (low), drift, cal source, spectral, internal cal, absolute gain |
| `two_point` | gain and offset correction at two cal sources | the above plus the high cal point and the nonlinearity dispersion |
| `three_point` | adds a mid cal point | the above plus the mid point |

Leaving the selector at `none` reproduces today's results exactly — that is the point of the
default, and the note at the bottom of the screen says so rather than making you infer it from
a screenful of inert rows.

### 5.2 Cal points

`cal_point_mode` chooses how a cal point is stated, and the rows follow:

- **`temperature`** — the figure's case: cal sources given as blackbody temperatures
  (`cal_temp_low_K`, and `_mid_K` / `_high_K` as the scheme allows). The flux rows are hidden.
- **`flux_fraction`** — cal sources given as a fraction of full-scale flux, for a system whose
  cal source is not a blackbody. The temperature rows are hidden.

Flipping the mode is one action: the other mode's inputs — the cal temperatures and every
temperature-anchored bias term under `flux_fraction`, the flux points on the way back — are
withdrawn with the commit, the editor's *Withdraws* line names them first, and one Undo
restores them. A file that carries both is refused in either direction: a flux point under
the temperature mode is as much a conflict as a cal temperature under the flux mode. A flux-mode scheme without its flux point is then the same *expected*
incomplete state as a scheme without its cal temperature, and routes as an advisory.

An unset cal temperature renders as **words** — `unset — required` — never as a plausible-looking
`0 K`. A scheme switched on without its cal point is an *expected* incomplete state, so the
evaluation routes it as an advisory rather than a modal: only the Calibration chip goes red, the
status bar names what is missing, and the Messages panel carries the full text. Chapter 12, §4
shows exactly that state.

### 5.3 The three error families

The remaining groups split along a line worth keeping straight: **precision** (how repeatable a
measurement is — noise) and **accuracy** (how close it is to truth — bias). RADIANT reports them
beside each other and never RSSes one into the other.

| Group | Feeds | What it says |
|---|---|---|
| NUC residual (`nonlinearity_pct`) | noise | the per-pixel quadratic residual two-point correction cannot remove |
| Drift since cal (time since cal, gain-drift rate, offset-drift rate) | noise | how far the correction has aged since it was applied |
| Cal source (emissivity, uniformity, ΔT, Δε) | bias | how well you know the source you calibrated against |
| Spectral cal (band-center Δλ) | bias | how well you know where your band actually sits |
| Internal cal (cal path, elements before shutter, narcissus FPN) | bias | what an internal shutter sees that the scene path does not |
| Absolute gain (gain uncertainty) | bias | the residual scale error on the whole measurement |

Time since cal is edited in **hours** by default — entry and display in the same unit, as
everywhere else — and stored in seconds.

The outputs beside the form carry the cal signals, the per-term residuals, the σ totals, the
NEDT-equivalent **calibration floor**, and the RSS of the bias budget. The noise-budget figure
below them gains the residual terms the moment a scheme goes active.

**Why this matters to a number you already care about.** Calibration residuals are
*correlated* errors: they do not average down with integration. Co-add or TDI your way to more
electrons and the random terms fall as expected while the residual terms do not, so NEDT
plateaus at the calibration floor instead of continuing to improve. If a sensitivity trade
stops responding to integration time, this screen is where the answer is. The accuracy side of
the budget surfaces as the radiometric-accuracy metrics on the Performance screen — chapter 9.
