# Quickstart Tour

One scene, evaluated twice: first in the desktop application, then from a YAML file on the
command line. The point of the tour is orientation rather than completeness — where things
are, what the application does on its own, and how the two ways of driving RADIANT are the
same run. Chapters 4–6 return to each surface properly.

The scene is the one RADIANT ships as its reference case,
`examples/mwir_leo_minimal.yaml`: a 300 K, emissivity-0.95 extended scene viewed straight
down from 8 km through a 0.30 m f/4 telescope, integrating 5 ms over a 3.5–5.0 µm band onto
an 18 µm pixel.

## 1. Open it

```bash
radiant gui examples/mwir_leo_minimal.yaml
```

The window opens already populated. RADIANT evaluates a configuration as soon as it loads —
there is no "run" step to remember before the first look — and the status bar in the bottom
left reports the outcome:

```text
Evaluated — 500 wavelength points
```

![The main window on the minimal MWIR example: stage strip across the top, Parameters dock
at the left, the Geometry workspace in the centre, and the persistent right rail with the
pinned metric cards.](figures/gui/ug_window_anatomy.png)

Four things are worth naming before anything else:

- **The strip along the top is the signal chain** — ten stages in the order the physics runs,
  each a button, each carrying a health dot. All ten are green here: the run finished with
  no warnings.
- **The left dock is every parameter in the model**, as a tree, with a *Source* column
  saying where each value came from. `sensor_altitude_m` reads `8000 m` with a `config`
  badge because the file set it; the rows around it read `default`.
- **The centre is one stage at a time.** Clicking a stage in the strip swaps the centre to
  that stage's workspace — its editable inputs, its computed outputs, its plots. The window
  opened on Geometry.
- **The right rail is always there.** Five metric cards are pinned by default (SNR, NEDT,
  NIIRS, GSD, MTF at Nyquist), below them the `Edit Config (YAML)` button and the Messages
  panel, and pinned at the bottom the accent **Evaluate** button with its `F5` label.

## 2. Read the answer

The rail already carries the headline: **SNR 1124**, **NEDT 24.96 mK**, **GSD 0.12 m**,
**MTF @ Nyq 0.2668**. NIIRS reads `n/a — not computed for this run`, which is the tool
declining to extrapolate the GIQE-5 regression outside its range rather than printing a
number it does not stand behind.

For the full metric surface, select stage **10 Performance**.

![The Performance workspace after evaluation — the Compute: group toggles above the grouped
metric cards.](figures/gui/performance_workspace.png)

Metrics arrive in five groups — *Sampling / geometry*, *Spatial / MTF*, *Radiometric*,
*Interpretability*, *Saturation* — and the `Compute:` checkbox row above the cards is a
computation switch, not a display filter: unticking a group stops the chain producing its
inputs. Every row carries its unit.

## 3. Change one number and watch

Select stage **4 Optics**, and in the *Inputs* tab set `aperture_diameter_m` to 0.35 m.

You do not need to press anything. RADIANT re-evaluates on a short debounce after every
committed edit, so the whole chain re-runs and every open view refreshes. Within a moment
the rail reads **SNR 1311**, **NEDT 21.39 mK**, and **MTF @ Nyq 0.3152**; the *Saturation*
group's well margin has dropped to **1.311 dB**.

That last number is the interesting one. Signal grows as $D^2$ while shot noise grows as
$\sqrt{S} \propto D$, so SNR climbs linearly with diameter — and the well fills quadratically.
At 0.30 m the well margin was 3.989 dB; at 0.35 m it is 1.311 dB. Push much further on this
configuration and the pixel clips, at which point RADIANT says so loudly in the Messages
panel rather than quietly reporting the clipped number as if it were a prediction.

Press `Ctrl+Z` (Edit ▸ Undo) to put the aperture back. Undo covers parameter edits, so the
tour leaves the shipped example as it found it.

## 4. The same run, from the file

Close the application. Everything above is also a two-line file and one command.

The configuration is short because RADIANT writes down only what you *chose* — the rest is
schema defaults, and they stay visible as defaults rather than being frozen into your file:

```yaml
source:
  target:
    temperature: 300.0        # K
    emissivity: 0.95

geometry:
  sensor_altitude_m: 8000.0   # m

optics:
  aperture_diameter_m: 0.30   # m
  focal_length_m: 1.20        # m  (f/4.0)
  transmission_scalar: 0.70

spectral_integration:
  filter_min_um: 3.5           # um
  filter_max_um: 5.0           # um
  integration_time_s: 0.005    # s  (5 ms)
```

(The file also sets the atmosphere profile, the detector and the readout; the full listing
is `examples/mwir_leo_minimal.yaml`.)

Run it:

```bash
radiant run examples/mwir_leo_minimal.yaml
```

```text
Signal:  1263548.28 e-
  signal_shot      1124.0766 e- RMS
  background_shot  0.0000 e- RMS
  nearfield_shot   0.0000 e- RMS
  straylight_shot  0.0000 e- RMS
  dark_shot        0.7071 e- RMS
  gr_noise         0.0000 e- RMS
  johnson_noise    0.0000 e- RMS
  flicker_1f       0.0000 e- RMS
  read_noise       5.0000 e- RMS
  ktc_reset        0.0000 e- RMS
  quantization     9.2376 e- RMS
  prnu             0.0000 e- RMS
  dsnu             0.0000 e- RMS
  clutter          0.0000 e- RMS
  persistence_noise  0.0000 e- RMS
  glow_shot        0.0000 e- RMS
Noise (RSS): 1124.1259 e- RMS
SNR:     1124.03
```

Read that as a budget. The pixel collected 1.264 × 10⁶ e-; sixteen noise terms were computed
and all sixteen are listed, including the twelve that are exactly zero for this
configuration — a term that does not apply is reported as 0.0000 e- RMS rather than being
omitted, so a missing mechanism can never hide in a gap. The terms combine in quadrature to
1124.1259 e- RMS, of which signal shot noise is 1124.0766. This is a shot-noise-limited
measurement: the 5 e- RMS read noise and the 9.2376 e- RMS quantization noise together move
the total by less than 0.05 e- RMS.

The same SNR — 1124.03 — that the application showed as **1124**.

## 5. The rest of the metric surface, and one override

The text output is the radiometric summary. The whole metric surface, with the keys the
scripting API and the sweep dialog use, comes out as CSV:

```bash
radiant run examples/mwir_leo_minimal.yaml --format csv
```

```text
metric,value
adc_margin_dB,4.40062882420454
alias_fraction_at_nyquist,0.5000073062882227
contrast_snr,1124.0273378815184
diffraction_limit_angular_urad,17.28333333333333
...
gsd_geometric_mean_m,0.12000000000000002
mtf_at_nyquist,0.2667707827793829
nedt_K,0.024957967557736216
snr,1124.0273378815184
```

Note the units the raw surface carries: `nedt_K` is in kelvin (0.024958 K), which the
application displays as 24.96 mK. The value is the same; the display scale is chosen for
legibility, and the unit is always shown.

The same single-parameter change made in the application in §3 is an override here, with no
edit to the file:

```bash
radiant run examples/mwir_leo_minimal.yaml --set optics.aperture_diameter_m=0.35
```

```text
Signal:  1719829.60 e-
  signal_shot      1311.4227 e- RMS
  ...
Noise (RSS): 1311.4650 e- RMS
SNR:     1311.38
```

SNR 1311.38 — the number the rail showed as **1311**.

## 6. Two more commands worth knowing early

**Ask why a value is what it is.** The example file never sets an f-number, yet the model
has one:

```bash
radiant explain examples/mwir_leo_minimal.yaml optics.f_number
```

```text
optics.f_number = 4.0  (canonical: 4.0 )
  Description: Dimensionless f/# = focal_length_m / aperture_diameter_m. Part of the {D, f, f/#} consistency group; supply any two and the third is derived.
  Provenance: derived
  Source: derived: f_number = focal_length_m / aperture_diameter_m
  Derived from:
    optics.aperture_diameter_m = 0.3
    optics.focal_length_m = 1.2
```

That is the same provenance the application paints as a `derived` badge, and the same reason
the f-number field in the Optics workspace is read-only: it is computed, so it is not typed.

**Check a file without running it.**

```bash
radiant validate examples/mwir_leo_minimal.yaml
```

```text
Config OK: examples/mwir_leo_minimal.yaml
  218 parameters resolved.
```

Two hundred and eighteen parameters were resolved from the dozen the file names. That ratio
is the thing to carry out of this tour: RADIANT is a complete model of a sensor at all
times, and your configuration is the set of statements you have made about it. Which values
are yours, and which are the model's, is the subject of the next chapter.

## Where to go next

- **Chapter 4** — what a parameter, a unit, a provenance badge, a regime, and a
  configuration actually are.
- **Chapter 5** — the window part by part, and how the evaluate loop behaves.
- **Volume IV, chapter 2** — six task-shaped walkthroughs that pick up where this tour
  stops: build a sensor from nothing, read a validated flagship baseline, adopt a focal
  plane from the part library, edit an optical train, run a sweep, compare configurations.
