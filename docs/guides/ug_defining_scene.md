# Defining the Scene

Three stages describe the world the sensor looks at: **Geometry** (where everything is),
**Source** (what the target and its background radiate), and **Atmosphere** (what the air in
between does to it). They run first, in that order, and everything downstream is a
consequence of them. This chapter walks each workspace.

The sensor side — optics, platform, detector, readout, calibration — is chapter 7.

## 1. Geometry

RADIANT is geometry-first: the chain settles ranges, angles, and ground sampling before any
radiometry runs. That is why the Geometry workspace is the first stage in the strip and why
it is where target size and shape live too.

![The Geometry workspace, Inputs tab, on the Landsat 9 TIRS band-10 baseline — the scene-class
card, one card per geometry family, and (in the rail) the metrics that follow from
them.](figures/gui/ug_geometry_inputs.png)

### 1.1 The scene-class card

The pane leads with the scene class, because it is the fact that makes every other input mean
something. The chip is **derived** and read verbatim from the stage's outputs:

```text
Scene: space → ground (space_to_ground) — derived
```

Observer class and target class combine into the class — `air_to_ground` for an aircraft over
terrain, `space_to_ground` for the figure's 705 km orbit, and likewise the ground-to-air,
space-to-space and level variants. Below it sits an optional **Assert scene class** field.
Asserting one steers which defaults apply and is checked against the derivation at the next
evaluation; leave it `auto` and the derivation simply stands.

The card also previews **relevance**: which metrics this scene class turns off by default —
here the three target-plane sample distances, which mean nothing for a ground target. The
note under the list is the rule that governs it: *defaults only* — a metric group you select
yourself is always computed, whatever the scene class.

### 1.2 One mode per family

Beneath the scene card, geometry is entered through **families**, and you pick exactly one
**mode** in each. This is the flexibility different disciplines need: a mission planner has a ground
range, an optical designer has an off-boresight angle, a test engineer has a slant range, and
none of them should have to convert.

| Family | Modes |
|---|---|
| **Viewing geometry** | Path zenith at the lower endpoint (V1) · Off-boresight angle (V2) · Ground range (V3) · Elevation angle, signed (V4) · Direct slant range (V0) |
| **Solar geometry** | Solar zenith $\theta_s$ (S1) · Solar elevation (S2) · Site + time (S3: latitude, day of year, local solar time, LTAN) |
| **Platform kinematics** | Direct ground speed · Circular orbit (V6) |
| **Line-of-sight rate** | Platform motion only (derived, K0) · Direct LOS rate (K1) · Target velocity (K2) |

Each family card carries a mode selector, and only the active mode's fields are editable. The
others stay visible and grayed — they are not missing features, they are the doors you did
not take, and they display the value **derived** from the one you did. In the figure the
viewing family is on V1, so `path_zenith_rad` is enterable while `sensor_off_boresight_rad`,
`ground_range_m`, `elevation_angle_rad` and `target_range_m` show what that zenith implies.
A blank configuration opens every family on its documented default door — V1, S1, direct
ground speed, platform-motion-only — with the schema defaults showing.

**The selector is the switch.** Picking another mode does three things as one action: it
withdraws the old door's value, it seeds the new door with the derived value you were just
looking at, and it makes that field editable. The scene does not move — a 10° path zenith
becomes the same 10° expressed as a ground range — so you then type the number you actually
have. One Edit → Undo reverses the whole switch. A door that cannot be derived (site and
time, target velocity) opens empty and waits for your values. Choosing *Circular orbit*
sets the flag; choosing *Direct ground speed* again seeds the orbital speed the flag implied.

Every viewing angle is read at the path's **lower endpoint**, and the reference axis is
resolved from the altitudes rather than declared — the same door works looking down from
orbit and up from the ground.

The active mode is detected from provenance, never guessed: the mode is whichever one you
actually supplied a value for. There is one door per family, and the application holds you
to it at the door: a second door entered anywhere else — the Parameters dock, a YAML apply —
is rejected inline (*Two viewing doors are set …*) with the selector named as the way to
switch. A configuration file that already carries two agreeing doors still loads and
evaluates (the engine tolerates a consistent pair); disagreeing doors raise an
over-specification error at evaluation, the application tints the offending family's card,
and jumps you to the Geometry screen. The *what / why / action* text is in the error dialog
and the Messages panel; the tint is just the locator.

Inside the **Site + time** door the hour angle is one quantity with two spellings, so the
card carries a toggle: *Local solar time*, or *LTAN* for a sun-synchronous orbit. Flipping it
withdraws the other entry; the two are never both live.

**Bench and lab geometry.** A bench has no viewing angle. Set both altitudes to the same
value (0 m will do), pick *Direct slant range (V0)* and enter the separation — the level path
is then fixed by the range alone, and the horizon guard, which exists for refraction over
kilometres of air, has nothing to say about two metres of it. Do not also enter an angle: on a
level path a zero zenith or elevation contradicts the range, and the selector withdraws one
for you if you pick V0 after the fact. The selector's V0 entry carries this hint as a tooltip.

A standalone **site elevation** card carries `geometry.site_elevation_m`. It is not a mode —
it is a scene fact (the ground under the observer), and it is results-affecting: the
turbulence surface term is evaluated relative to it.

### 1.3 Target size and shape

Target extent lives here, not on the Source stage, because it is geometry. The **Target
shape** panel on the *Schematic* tab offers a shape library — plate, box, sphere, cylinder,
cone, circle, ellipsoid, point source, extended scene — with the dimension fields for the
chosen shape, *or* a scalar **projected area** (`geometry.target.projected_area_m2`) when the
shape is `none`. Never both: they are two mutually exclusive ways to say the same thing, and
the size you give here is what the regime classifier compares against the pixel.

### 1.4 The derived-angle readout

Below the inputs, the stage's outputs are grouped by **reference frame**, because an angle
without its frame is a trap:

- **Target frame** — path zenith $\theta_o$, incidence $\theta_i$, solar zenith $\theta_s$,
  relative azimuth $\Delta\varphi$.
- **Ground / platform frame** — off-nadir $\eta$, slant range, ground range, both altitudes,
  ground speed, orbital period.
- **Resolution** — the illumination state (`day` / `night`) and the mode actually used in each
  family, written out: `viewing_mode = path_zenith (default)`, `kinematics_mode = direct`,
  `los_rate_mode = platform-only (derived)`.

That last group is the one to check when a result surprises you: it states, in words, which
door the chain actually walked through.

### 1.5 The schematic

![The Geometry workspace, Schematic tab — a 705 km space-to-ground view, drawn not to
scale.](figures/gui/ug_geometry_schematic.png)

The *Schematic* tab is a 2D engineering drawing of the scene: sun, sensor and target glyphs,
the sun→target and sensor→target vectors, the local zenith, and a faint reference ground grid.
It exists to answer "is this the geometry I meant?", which the numbers alone answer poorly.

**It is deliberately not to scale, and that is a design rule rather than a limitation.** A
705 km altitude drawn to scale against a 6371 km Earth radius would be a hairline; drawn
against a 2 m target it would be nothing at all. So the *angles* are true and the *magnitudes*
are carried by leader labels — the `h_s 705 km` pill in the figure. Nothing is rescaled or
translated to fake proportionality. A target sized only by projected area gets its own pill
(`A_t <area> m² · <n> px`, the pixel multiple being the sub-pixel-versus-resolved cue), and a
level path gets a tangent-sag pill, because a 49 m dip is invisible in a drawing like this one
and matters to the atmosphere.

Bottom left, the **ANGLES** overlay is a set of toggles that reveal the angle arcs and their
degree labels on the canvas, split by frame exactly as the readout is: target-frame ($\theta_s$,
$\Delta\varphi$, phase angle, $\theta_o$, $\zeta_\text{low}$) and ground/platform-frame ($\eta$).
Top left, the **VECTORS** legend names what is drawn — and only what is drawn: a night scene
has no sun, so the sun glyph, both sun vectors and every sun-derived annotation disappear
rather than being drawn from fabricated angles, and the legend shrinks with them.

The angles in the schematic are read from the stage's outputs. The drawing computes projection
and picking, never physics, so the picture and the readout cannot disagree.

The tab also carries an editable copy of the geometry mode forms, so you can adjust the scene
while watching the drawing change.

## 2. Target and background

The Source workspace has five tabs because a "target" is up to four different declarations
depending on what kind of thing it is.

### 2.1 Scene & regime

The first tab is where you state what kind of scene this is — `source.scene_type` — and,
if you must, force the classification with `source.regime_override`. It also carries the
sub-pixel fill fraction, and beneath them the stage's outputs: the tentative regime, the
projected area, the range, the fill fraction, the angular extent. Chapter 4, §5 covers the
classification itself.

### 2.2 Target — thermal

![The Source workspace, Target — thermal tab, on the minimal MWIR example: temperature and
emissivity above the pre-atmosphere emission spectrum.](figures/gui/ug_source_thermal.png)

Temperature and emissivity, plus a *hot target* switch that forces a pure-emissive treatment.
Below them, the emitted spectral radiance **leaving the target**, before the atmosphere — the
figure's smooth rise from about 0.35 to 2.6 W/m²/sr/µm across the 3.5–5.0 µm band is a 300 K
Planck curve times $\varepsilon = 0.95$, and it is drawn here rather than at the aperture
because this stage's job ends at the target's surface. The background arm is drawn alongside
when one is defined.

Emissivity is an independent input here, and only here: for a *scene* material it is a
physical property you are entitled to state. (For an *optical element* it is not — the
Optics stage derives emissivity from reflectance and transmittance, and refuses to accept
both. Chapter 7.)

### 2.3 Target — reflective

![The Source workspace, Target — reflective tab, on the bundled aerial VNIR template:
reflectance beside the reflected radiance it produces.](figures/gui/ug_source_reflective.png)

A sunlit target is described by its reflectance: either the scalar
`source.target.reflectance` or a spectral $\rho(\lambda)$ from a CSV file. They are mutually
exclusive, and an over-specified pair is rejected at the moment you commit it, with the same
message the evaluation would have produced.

The thermal, reflective and point-intensity tabs are **doors** onto one target, and entering
a value through one of them is how you switch. Commit a reflectance on a target that has a
temperature and emissivity and both are withdrawn in the same action — the editor lists
them on a *Withdraws* line before you apply, and one Undo brings them back. Going the other
way is the mirror: a temperature withdraws the reflectance.

The tab pairs cause with effect: $\rho(\lambda)$ on the left — here a flat 0.30 across
0.4–0.9 µm — and the reflected radiance leaving the target on the right, peaking near
95 W/m²/sr/µm at about 0.55 µm under this scene's 40° sun. Change one and watch the other.

The three solar rows on this tab (`illumination`, solar zenith, solar azimuth) are **read-only
mirrors**. The sun is geometry, it is owned by the Geometry stage, and showing it here without
a second editor is the compromise: you can see why the reflected term is what it is without
there being two places to change it.

For a target that both emits and reflects, set emissivity and temperature and let Kirchhoff
supply $\rho = 1 - \varepsilon$; for a purely reflective target, set reflectance alone. The
tab says so in a note, and the engine enforces it.

### 2.4 Target — point source

A point source is defined by **intensity**, not by radiance times area, so it gets its own
tab and its own inputs (in-band radiant intensity, or an equivalent temperature, area and
emissivity). The surface-radiance rows are disabled there, and the point-source rows are
disabled elsewhere — the tab set follows the declared scene type rather than offering every
input at once. Entering an intensity on a target that still carries a temperature and
emissivity withdraws them as part of the same commit (the editor's *Withdraws* line names
them); the blackbody triple and the band-integrated intensity are two forms of one door and
withdraw each other the same way.

### 2.5 Background & contrast

Background temperature and emissivity, the contrast reference pair, and a named background
material from the shipped library. The background matters more than it looks: it sets the
contrast SNR, it is what a sub-pixel target is mixed with, and it is the term the ensquared
energy is deliberately *not* applied to.

## 3. Atmosphere

![The Atmosphere workspace: the model selector with only the active backend's knobs shown,
above the per-leg transmittance and path-radiance spectra.](figures/gui/ug_atmosphere_workspace.png)

### 3.1 Choosing a model

`atmosphere.model` takes five values, and the form shows **only the selected backend's
inputs** — so a `simple` run does not present you with tape7 paths, and a `modtran` run does
not present you with a visibility slider that would do nothing.

| Model | What it is | When to reach for it |
|---|---|---|
| `simple` | a parametric species model — profile, aerosol type, visibility, precipitable water | the always-works baseline; the only backend that serves *any* path topology, including up-looking, level, and grazing geometries |
| `interpolated` | measured MODTRAN runs, interpolated between nodes | whenever a bundled family covers your scene; on a node it is bit-identical to the stored column |
| `tabulated` | a stored column from files | a fixed geometry you have data for; geometry-agnostic by design |
| `modtran` | a MODTRAN tape7 you supply | as above, from MODTRAN output directly |
| `exo` | vacuum | both endpoints at or above 100 km, where no backend is consulted at all |

The figure shows the `simple` group: `midlat_summer` profile, `rural` aerosol, 23 km
visibility, 1.4 cm precipitable water, with the turbulence Fried parameter $r_0$ beneath under
its own heading (`0 m` meaning turbulence off).

### 3.2 The guidance, in one page

The full decision table, the ten bundled MODTRAN families with their verbatim coverage lines,
and the catalog of every warning and refusal are in the repository's atmosphere-selection
guide. The operator's summary:

- **`simple` never refuses a legal geometry.** In the thermal bands it is within tens of
  percent of MODTRAN; in the daytime visible and near-infrared it under-reads sky radiance by
  roughly a factor of two, so quantitative VIS/NIR background work needs a measured backend.
- **`interpolated` is exact on a node and refuses off the hull.** It does not extrapolate.
  Coverage is a closed set of ten families, most of them rendered on a mid-latitude summer
  profile at a 30° sun — so adopting one can change your atmosphere *profile* and your *sun*,
  and both caveats are surfaced rather than assumed away.
- **Direction is not a preference.** Down-looking families store upwelling path radiance;
  up-looking families store downwelling. They are different physical quantities and are never
  substituted for one another.
- **Some geometries have no measured family at all** — level (air-to-air, ground-to-ground)
  paths, grazing lines of sight past about 88.8° zenith, and sensors below the down-looking
  families' 3 km floor. For those, `simple` is not a fallback, it is the supported answer.

### 3.3 The family picker

Selecting `interpolated` reveals the **library family** picker instead of a free-text axes
field. It lists one row per bundled family with its name, its rendered profile and a
plain-language coverage line with explicit units; marks the row your scene calls for as
*(recommended for this scene)*; and, where the configured family cannot serve the scene,
**pre-selects the recommendation as a proposal** with an explicit *Use this family* button —
never applying it behind your back, because adopting a family can change the profile. Where
the profile would change, the caveat is printed beside the row. *Custom axes… (advanced)* is
the last entry, for a run matrix you built yourself.

The recommendation is validated end to end before it is offered — direction, axes, line-of-sight
zenith, target ceiling, lower endpoint — so a family the picker names is one the chain will
accept.

When **no** bundled family serves the scene you get exactly **one** advisory in the Messages
panel, naming the single closest miss, and the configuration stays as it was. Coverage
refusals appear as advisories rather than as a "Parameter Rejected" dialog, and the
distinction is deliberate: your scene is legal and your inputs are legal — the bundled library
simply has no measured column for it, and the remedy is a different family or `simple`.

### 3.4 What the stage produces

The workspace's outputs and figures are per-leg, because the atmosphere is not one number:

- **Target path** — $\tau_\text{up}$ and $L_{\text{path,up}}$, target to sensor.
- **Background path** — $\tau_\text{full,up}$ and $L_{\text{path,full}}$, ground to sensor.
  These differ whenever the target is elevated, which is exactly why an interpolated family
  without a target-altitude axis has to refuse that scene rather than reuse one column for
  both.
- **Sky terms** — the scattered and thermal downwelling irradiances that illuminate the
  target.

The transmittance and path-radiance curves are drawn on a twin axis so that loss and the
path's own emission are visible separately: in the figure's 3.5–5.0 µm band $\tau_\text{atm}$
sits high and flat across the window and falls away at the long-wavelength edge, exactly
where $L_\text{path}$ turns up — an absorbing path is an emitting path, which is the same
physics seen twice.

The workspace also draws the spectra **before** and **after** the atmosphere on one screen, so
propagation reads as a before-and-after rather than as a single mysterious multiplication. The
at-aperture radiance is shown here and nowhere else, because this is the stage that produced
it.
