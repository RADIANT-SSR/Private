# Case Study — MWIR Maritime Surveillance

**Scenario 1.1** · persona: Sarah, systems engineer on a proposal team · modality:
GUI-led · scenario folder:
`scenarios/01_sarah_systems_engineer/1.1_mwir_maritime_surveillance/`

---

## The question

Sarah's team is bidding a sun-synchronous MWIR ship-detection payload. The
procurement asks for detection of a small surface vessel from a 500 km orbit, and
the proposal has to defend an aperture: somewhere between 15 cm and 45 cm at a
fixed f/2.5, on a 640 × 512 InSb focal plane with 15 µm pixels. Two questions have
to be answered before the aperture can be argued:

1. How do SNR, NEDT, NIIRS and detection range move as the aperture grows?
2. A colleague has handed her a MODTRAN 6 tape7 for a maritime column. How much
   does using that real transmittance instead of RADIANT's own parametric model
   change the answer?

The second question is the one that used to have no answer. Before RADIANT could
read a tape7, an analyst holding a colleague's MODTRAN run still had to re-derive
the atmosphere from a parametric model — which is to say, ignore the data she had.

This chapter walks the GUI half of that study on the scenario's committed baseline,
`inputs/1.1_mwir_maritime_surveillance.gui.yaml`, which is the 30 cm mid-sweep point
with the parametric atmosphere. The MODTRAN comparison and the full aperture sweep
are the scripted half; the closing section points at them.

## The inputs, and why they are what they are

| Quantity | Value | Why |
|---|---|---|
| Sensor altitude | 500,000 m | The procurement's sun-synchronous reference orbit. |
| Path zenith angle | 20° | A representative off-nadir look, not a nadir best case. |
| Slant range to target | 532,089 m | Carried in the config file; the altitude and look angle above imply it to within 0.5 %. |
| Target projected area | 240 m² | A 30 m × 8 m hull, presented broadside. |
| Target temperature | 288 K | Sea-surface temperature; the hull is in thermal equilibrium with it. |
| Target emissivity | `steel` curve, band-average ε = 0.266 | RADIANT's library curve over 3.5–5.0 µm; the catalog wants a rust-specific curve, which does not exist. |
| Background | `water_calm`, 288 K, ε = 0.985 | Calm-ocean emissivity from the same library. |
| Aperture diameter | 0.30 m | Mid-point of the 0.15–0.45 m trade. |
| Focal length | 0.75 m | Holds f/2.5 at the mid-point. |
| Optical transmission | 0.85 | Scalar lump — this study does not model a coated train. |
| Spectral band | 3.5–5.0 µm | MWIR cold-filter passband. |
| Integration time | 0.005 s | 5 ms, a long dwell for a pushbroom but plausible for a staring frame. |
| Pixel pitch | 15 µm × 15 µm | The vendor's InSb array. |
| Quantum efficiency | 0.773476 | Band-average of the vendor's InSb QE curve over 3.5–5.0 µm. |
| Dark rate | 50,000 e-/s at 77 K | Vendor figure at the cryogenic set point. |
| Read noise | 30 e- RMS | Vendor ROIC. |
| Full well / gain / ADC | 8 × 10⁶ e- / 500 e-/DN / 14 bit | Vendor ROIC. |
| Atmosphere | parametric, `midlat_summer`, maritime aerosol, 23 km visibility | Matched to the profile the MODTRAN column was run against. |

Two of those deserve a second look. The **target and the background are at the same
temperature**: a steel hull floating in 288 K water is not a hot target. Everything
this sensor detects comes from the *material* difference between painted steel and
calm water — the library's steel curve band-averages to ε = 0.266 over 3.5–5.0 µm
against the sea's 0.985, and by Kirchhoff the hull's complementary reflectance
ρ = 0.734 bounces sky and (in daylight) sun back into the aperture. RADIANT models the
hull as a mixed emit-plus-reflect target for exactly that reason. The two effects run
opposite ways, and how nearly they cancel is the whole detection problem.

And the **quantum efficiency is a scalar**, band-averaged from the vendor's curve
rather than carried spectrally — the same simplification scenario 1.2 makes, and the
reason this baseline and the scenario's spectral-QE runs agree only to about a percent.

## The GUI walk

### Step 1 — The atmosphere the colleague supplied

The scenario's own GUI workflow opens with `File → Import Atmosphere → MODTRAN
tape7`. That is a modal file dialog, and the figures in this manual are captured
offscreen where modal dialogs cannot be photographed cleanly, so the figure below
shows the state that matters instead: the Atmosphere workspace as the baseline
config leaves it, on the **parametric** side of the comparison.

![Atmosphere workspace on the scenario 1.1 baseline — the parametric
model's four inputs above, the target-path transmittance and path radiance they
produce below.](figures/gui/case_maritime_atmosphere.png)

The model selector reads `simple`, and the four parametric inputs beneath it are the
whole specification: standard atmosphere `midlat_summer`, aerosol type `maritime`,
visibility 23 km, precipitable water 1.4 cm. The Fried parameter is 0 m, which is
how this workspace says *turbulence off* — appropriate for a down-looking space
sensor where the turbulent layer is at the far end of a 532 km path.

The plots underneath are the stage's output, drawn on the chain's 500-point
wavelength grid. The **target path** panel carries two curves: $\tau_{up}$, flat at
a little under half scale from 3.5 µm to about 4.9 µm and then falling off the
5.0 µm filter edge, and $L_{path}$, the up-welling path radiance, climbing steadily
across the band. The scenario's runner reports the in-band mean as
$\bar\tau = 0.4594$ — a maritime MWIR column at 20° off nadir passes under half
the target's emission. The **background path** panel below repeats the exercise for
the ground-to-sensor leg.

> **Where the tape7 goes.** Switching the model selector to `modtran` exposes
> `atmosphere.modtran.tape7_path`; RADIANT parses and unit-converts the deck before
> the chain runs, with no temporary-CSV side door. The scenario's script runs both
> ways on one otherwise-identical config, which is what makes the comparison a clean
> A/B on the atmosphere term alone.

### Step 2 — Place the sensor and the target

Select stage **1 Geometry**, tab **Inputs**.

![Geometry workspace, Inputs tab — the derived scene class, the off-by-default metric
list, and the V1 path-zenith viewing mode.](figures/gui/case_maritime_geometry.png)

The card at the top reads `Scene: space → ground (space_to_ground) — derived`. Nobody
typed that; it follows from a 500 km sensor looking at a 0 m target, and it is what
decides which metrics are relevant. For this scene class only three metrics default
off — the three target-plane sample distances — because a ground scene *has* a ground
plane and every ground-projection metric applies.

The viewing family sits in mode **V1**, `Path zenith at lower endpoint`. The three
entered fields are `sensor_altitude_m` = 500,000 m, `target_altitude_m` = 0 m and
`path_zenith_rad` = 20 deg; `sensor_off_boresight_rad`, `ground_range_m`,
`elevation_angle_rad` and `target_range_m` are grayed because they belong to *other*
doors of the same family, not because they are unavailable. The slant range reads
532,089 m — 6 % longer than the 500 km altitude, which is the cost of a 20° look.

In the Parameters dock on the left, five rows carry a `config` badge —
`sensor_altitude_m`, `path_zenith_rad`, `target_range_m`, `target.projected_area_m2`
at 240 m², and the solar setting — and everything else reads `default`. That column
is how you tell what the analyst specified from what the schema supplied.

`target_range_m` appearing in both lists is not a contradiction, and it is worth
understanding once. The *mode form* greys it because mode V1 does not read it — the
slant range is solved from the altitude and the zenith angle. The *dock* badges it
`config` because the baseline file carries a value for it anyway: this file was written
by `Sensor.to_yaml()`, which records the range it resolved. The form is telling you what
this mode takes as input; the dock is telling you where a value came from. They answer
different questions about the same row.

### Step 3 — Declare the scene type, and let the tool argue with you

Select stage **2 Source**, tab **Scene & regime**.

![Source workspace, Scene & regime tab — the declared sub-pixel scene and
the angular extent that justifies it.](figures/gui/case_maritime_scene_regime.png)

`Scene type (declared)` and `Regime override (force)` both read `sub_pixel`, and the
Outputs list beneath reports `Regime tentative` = `sub_pixel`, projected area 240 m²,
range 532,089 m, fill fraction 1, and — the number the declaration rests on — an
**angular extent of 2.91153 × 10⁻⁵ rad**, i.e. 29.1 µrad.

That is the number to reason from. The diffraction-limited angular blur at this
aperture is 17.28 µrad (the Performance workspace reports it in a moment), so the ship
subtends about 1.7 times the diffraction spot. A point-source treatment requires the
target to be *small compared with* the PSF — conventionally under about a tenth of it
— and 1.7× is not that. RADIANT's own point-source consistency check rejects the
point-source classification here, and the scenario declares `sub_pixel` instead. That
is not a workaround: at 30 cm of aperture this ship is genuinely on the edge of being
resolved, and `sub_pixel` is the physically correct description of a target that fills
part of a pixel against a background that fills the rest.

The scenario's GUI workflow asks for this refusal to be surfaced inline, with the
numeric ratio shown, rather than as a raw traceback. That advisory is still a gap; the
numbers it would quote are the two on this page.

### Step 4 — Give it a telescope, and watch the regime be finalized

Select stage **4 Optics**, tab **Inputs**.

![Optics workspace, Inputs tab — the 30 cm f/2.5 head and the stage outputs, ending in
the final radiometric regime.](figures/gui/case_maritime_optics.png)

Aperture diameter 0.3 m, focal length 0.75 m, and the f-number field immediately reads
2.5 with a lightning bolt and a `derived` badge. WFE RMS is 0 waves against a 0.633 µm
reference wavelength — this study treats the optics as diffraction-limited, which is
why the Strehl ratio will come out at exactly 1.

The Outputs block underneath is what the stage handed downstream: collecting area
0.0706858 m², pixel solid angle 4 × 10⁻¹⁰ sr, effective diameter 0.3 m, effective
f-number 2.5, cone solid angle 0.122015 sr, pupil evaluated at 4.2515 µm — and
`Regime: sub_pixel`.

That last line is the architectural point. The source stage made a *tentative*
classification; the optics stage, which is the first stage that knows the PSF, makes
the **final** one. Every downstream stage reads this value and none re-decides it. The
practical consequence here is that the ensquared-energy fraction will be applied to
the target term and not to the background term, because in a sub-pixel scene the
background genuinely fills the pixel while the target does not.

### Step 5 — Read the noise budget

Select stage **7 Detector**, tab **Noise**.

![Detector workspace, Noise tab — the maritime noise budget, where background shot
nearly matches signal shot.](figures/gui/case_maritime_noise.png)

Sixteen noise terms are computed; five are non-zero. In order:

| Term | σ [e- RMS] | Note |
|---|---:|---|
| `signal_shot` | 1416 | The hull's own emission. |
| `background_shot` | 1408 | The sea filling the rest of the pixel. |
| `quantization` | 144.3 | $g/\sqrt{12}$ at 500 e-/DN. |
| `read_noise` | 30 | Vendor ROIC. |
| `dark_shot` | 15.81 | 50,000 e-/s over 5 ms. |
| **Total (RSS)** | **2003** | |

**Signal shot and background shot are the same size, and the figure lets you read why.**
Shot noise is $\sqrt{S}$, so the two terms square straight back to collected charge:
$1416^2 = 2.005 \times 10^6$ e- from the target arm against
$1408^2 = 1.982 \times 10^6$ e- from the background arm. The difference is
$2.3 \times 10^4$ e-, about **1.1 % of either one**. The sea is not a dark backdrop —
it is a 288 K surface at ε = 0.985 filling the pixel, and the hull is a 288 K surface
at ε = 0.266 that makes up most of the shortfall by reflecting sky and sun. Nothing
about this scene is signal-versus-dark.

Quantization at 144.3 e- RMS is nearly five times the read noise, which is what a
500 e-/DN gain buys: the ADC, not the detector, sets the electronic floor. On this
bright scene it costs nothing — 144 e- against 2003 e- total is 0.5 % in quadrature —
but it is worth remembering before this ROIC is flown against a fainter one.

### Step 6 — Read the result, and pick the right SNR

Select stage **10 Performance**.

![Performance workspace on the scenario 1.1 baseline — all five metric groups after
evaluation.](figures/gui/case_maritime_performance.png)

**Sampling / geometry.** GSD 10.59 m cross-track and 11.27 m along-track, geometric
mean 10.93 m; ground range 1.68 × 10⁵ m; $Q$ = 0.7083 at band center (0.5833 at the
short edge, 0.8333 at the long one), classified `detector-limited`; diffraction limit
17.28 µrad, projecting to 9.152 m at the target. The two GSD axes are not equal, and
the ratio is exactly the obliquity: $11.27 / 10.59 = 1.064 = 1/\cos 20^\circ$. A 20°
look stretches the ground footprint in the plane of the tilt and leaves the
perpendicular axis alone.

**Spatial / MTF.** FWHM 15.74 µm in both axes, RER 0.681, ensquared energy 0.5097 in
the central pixel and 0.909 over 3 × 3, straddle factor 0.6901, MTF at Nyquist 0.3553,
folded MTF 0.7106, alias fraction 0.5. Strehl is exactly 1 in both the degraded-PSF
and the Maréchal form, because the config carries no wavefront error.

**Radiometric — read this group carefully.**

| Metric | Value |
|---|---|
| SNR | 1002 |
| Contrast SNR | 11.45 |
| SCNR | 11.45 |
| NEDT | 25.11 mK |

SNR and contrast SNR differ by a factor of 87. SNR is the collected signal over the
total noise — it says the pixel is well exposed. **Contrast SNR is the
target-minus-background difference over that same noise, and it is the number that
decides whether the ship is detectable.** The 1.1 % radiance difference read off the
noise budget a moment ago, divided by 2003 e- RMS, *is* 11.45. That is comfortably
above a detection threshold of 5, so the answer is still *yes, detectable* — but an
aperture trade argued on SNR = 1002 is arguing about the wrong number. The margin here
is 11.45, and it is set by how nearly the hull's reflected sky makes up for its missing
emission.

**Interpretability.** MRT at Nyquist 0.159 K, NIIRS 4.606, flagged
`yes — outside GIQE-5`. The flag is not a footnote to ignore: a 10.93 m GSD thermal
scene sits outside the GIQE-5 regression's calibration range, and the config opts into
the extrapolated value explicitly via `performance.niirs.allow_extrapolated`. Read
NIIRS here as a relative trend across the aperture sweep, not as an absolute rating.

**Saturation.** Well margin 12.02 dB, ADC margin 12.22 dB, dynamic range 72.03 dB. The
margin is $20\log_{10}$ of capacity over filled charge, so 12.02 dB is a factor of 4:
the 5 ms dwell fills about a quarter of the 8 Me- well. There is room to integrate
longer if the frame rate allows it, though not a great deal.

## What the study concludes

At the 30 cm mid-point, with the parametric maritime atmosphere, the GUI reports
SNR 1002, contrast SNR 11.45, NEDT 25.11 mK, NIIRS 4.606 and GSD 10.93 m. The
scenario's runner, which evaluates the same configuration headless, reports SNR
1001.55, NEDT 0.0251 K and NIIRS 4.61 — the same numbers to the precision the cards
display.

Three findings survive out of the aperture sweep the script runs:

- **SNR is flat across 15 → 45 cm of aperture.** The sweep holds f/2.5 fixed, so focal
  length scales with diameter and the per-pixel étendue — and therefore the photon
  flux, for both the sub-pixel hull and the extended sea — is invariant. The aperture
  buys *resolution*, not signal: NIIRS climbs from 3.53 to 5.13 across the sweep while
  SNR does not move. An aperture trade that wants an SNR benefit has to sweep aperture
  at **fixed focal length**, letting f/# vary.
- **The parametric atmosphere and the real MODTRAN column agree to about 7 % on band
  transmittance** here — $\bar\tau$ 0.4594 parametric against 0.4277 measured, with the
  parametric model marginally the more transparent. SNR follows at about 9 % high
  (1001.55 against 916.18) and detection range at 5.8 % (2357.2 km against 2227.3 km).
  Note that $\tau$, SNR and range do not move together; quote the one the decision
  needs.
- **The regime is `sub_pixel`, and the metric that matters is contrast SNR.** Both
  follow from the same fact: this is a modest target against a bright, isothermal
  background at the edge of being resolved.

One note for anyone reading the scenario's own walkthrough alongside this chapter.
Its physics discussion describes the hull as "the ε = 0.95 hull" and "this ρ = 0.05
hull". The config — the scenario's runner and this GUI baseline alike — points
`source.target.emissivity_path` at the library's `steel` curve, which band-averages to
**ε = 0.266** over 3.5–5.0 µm, so the hull is ρ = 0.734 and strongly reflective in this
band. The prose predates the emissivity-path wiring; ε = 0.95 is the schema's scalar
default, not the value the run resolves. The numbers in the walkthrough's result table
are from the real run and are unaffected; only that sentence's characterization is.

One caveat carries into the proposal. The detection ranges above come from
`detection_range_beer_lambert`, which extrapolates the reference-range SNR outward on
an extinction coefficient measured at 532 km. It is not a full chain re-evaluation at
each range, and it assumes that coefficient holds out past 2000 km, which curvature,
refraction and the real atmospheric profile all say it does not. The GUI baseline does
not publish a `detection_range_m` metric for this scene at all — the scenario's runner
composes it. Treat those kilometers as a *relative* parametric-versus-MODTRAN
sensitivity, not as an operational range.

## The same study from a script

Everything above is one evaluation of one config; the study is a sweep of both. The
scenario's runner does the whole thing:

```bash
cd scenarios/01_sarah_systems_engineer/1.1_mwir_maritime_surveillance
python scripts/run_mwir_maritime_surveillance.py
```

It builds the two atmosphere configurations — `SimpleAtmosphere` and the imported
tape7 — on one otherwise-identical sensor, sweeps the aperture from 0.15 m to 0.45 m
at fixed f/2.5, composes detection range through
`radiant.performance.detection_range_beer_lambert`, and writes
`outputs/fig1_snr_and_range_vs_aperture.png` plus the comparison table this chapter
quotes. The MODTRAN column needs the real-run tape7 staged; without it the script
falls back to the synthetic deck behind a loud banner and says so.
`scripts/gui_console_1.1_mwir_maritime_surveillance.py` is the same work as a paste-in
for the GUI's scripting console, if you would rather stay in the window.

The full narrative, the atmosphere-provenance caveats, and the gap list are in the
scenario's own `walkthrough.md`.
