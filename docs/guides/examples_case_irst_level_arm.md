# Case Study — Air-to-Air IRST on a Level Arm

**Scenario 10.2** · persona: Sarah, systems engineer sizing an airborne MWIR IRST ·
modality: GUI-led · scenario folder:
`scenarios/10_direction_general/10.2_air_to_air_level_irst/`

---

## The question

Own-ship cruises at 10 km. The target cruises at 10 km. The line of sight between them
is horizontal, the target is a 500 K hot-parts source of 0.36 m² at ε = 0.90, and the
sensor is a 150 mm f/3 refractive MWIR head on a 20 µm focal plane. Sarah needs four
answers:

1. How far can this IRST see the target, and how does SNR fall with range?
2. **Does RADIANT even accept a horizontal line of sight**, and what does it warn about
   when it does?
3. The target is manoeuvring. What does the relative line-of-sight rate do to the
   integration-time budget?
4. How much can she trust the atmosphere model on a 100 km horizontal path at cruise
   altitude?

Question 2 used to have an embarrassing answer. Equal altitudes were a geometry-free
carve-out, and a path zenith at or past $\pi/2$ was rejected in three independent
places. This scenario is the validation that the level arm now works end to end, and
the GUI surfaces it exercises — the derived scene-class chip, the level composition of
the schematic, the tangent-depression pill — are the ones built for it.

This chapter walks the nominal 50 km point in the GUI on the scenario's committed
baseline, `inputs/10.2_air_to_air_level_irst.gui.yaml`. The 25–100 km range sweep, the
kinematics doors and the MODTRAN cross-check are the scripted half.

## The system, and why it is what it is

Vendor units on the left, canonical on the right — the vendor data arrives in mm, %,
ke-, ms, km, kt and °C, and the import maps every one of them once.

| Quantity | Vendor | Canonical |
|---|---|---|
| Entrance pupil diameter | 150 mm | 0.150 m |
| Effective focal length | 450 mm | 0.450 m |
| f-number | 3.0 | 3.0 (derived) |
| Optical transmission | 75 % | 0.750 |
| Central obscuration | 0 % | 0 — a filled refractive pupil |
| WFE RMS | 0.05 waves | 0.05 waves at 0.633 µm |
| Spectral band | 3.50 – 5.00 µm | same |
| Pixel pitch | 20 µm | 20 µm |
| Fill factor | 100 % | 1.00 |
| Quantum efficiency | 80 % | 0.80 |
| Dark current | 50 000 e-/s | 50 000 e-/s |
| FPA temperature | 80 K | 80 K |
| Read noise | 40 e- RMS | 40 e- RMS |
| Full well | 1000 ke- | 1.000 × 10⁶ e- |
| System gain | 61 e-/DN | 61 e-/DN |
| ADC | 14 bits | 14 bits |
| Frame integration | 0.10 ms | 1.00 × 10⁻⁴ s |
| Own-ship / target altitude | 10 km / 10 km | 10 000 m / 10 000 m |
| Slant range | 50 km | 50 000 m |
| Target hot parts | 226.85 °C, 0.36 m², 90 % | 500.00 K, 0.36 m², 0.90 |
| Own-ship TAS | 480 kt | 246.93 m/s |
| Illumination | — | `night` |
| Atmosphere | midlat_summer, PWV 2.92 cm, vis 23 km, rural | same |

The derived instrument scales follow immediately: IFOV = $p/f$ = 44.44 µrad, band
centre 4.250 µm, $Q = \lambda F/\# / p = 0.6375$ — undersampled, which is normal for a
search IRST that is trading resolution for field of view.

The atmosphere is deliberately set to the same profile, water content, visibility and
aerosol as the delivered MODTRAN horizontal grid, so the scenario's cross-check is
apples-to-apples rather than approximately so.

## The GUI walk

### Step 1 — Check that the tool understood the scene

Select stage **1 Geometry**, tab **Inputs**. This is the check Sarah makes before
trusting a single downstream number: has the GUI read this as an air-to-air level arm,
or as a space-to-ground look with a typo in it?

![Geometry workspace, Inputs tab — the derived air_to_air scene class, its off-by-default
metric list, and the V0 direct-slant-range mode.](figures/gui/case_irst_scene_class.png)

The card at the top reads `Scene: air → air (air_to_air) — derived`, with the two
component classes spelled out. The label is read verbatim from the geometry stage's
output; the card never re-derives a class from an altitude. `Assert scene class` sits at
`auto`, which is the point — the assertion is available but never required.

Underneath, **off by default for this scene class**, is a list of eleven metrics:
NIIRS, NIIRS (extrapolated), the three GSD axes, ground range, swath width, access
rate, two diffraction-limit-at-target entries, and max integration time. Every one of
them projects something onto a ground plane, and there is no ground plane at an
airborne target. The note beneath is explicit that these are *defaults only* — an
explicitly set `performance.metrics.*` group flag always wins — so a missing metric is
never ambiguous between "irrelevant" and "failed".

The viewing family is in mode **V0**, `Direct slant range`. `sensor_altitude_m` and
`target_altitude_m` both read 10 000 m and `target_range_m` reads 50 000 m; the four
angular fields are greyed. For equal altitudes the chord fixes the Earth-centre central
angle directly, which is the solution that subsumed the old geometry-free carve-out.

> **Proving the guard works.** The scenario's workflow has Sarah set
> `Assert scene class = air_to_air` (nothing changes — the assertion agrees with the
> derivation), then change `target_altitude_m` from 10 000 m to 10 m, the classic
> wrong-magnitude typo. The scene now derives `air_to_ground`, contradicting the
> assertion, and the geometry stage raises. The GUI answers in three places at once: the
> actionable-error dialog carrying the what/why/action verbatim, a row in the right-rail
> Messages panel, and a conflict tint on the scene-class card itself with the error's
> *what* line beside the chip — the contradiction shown where the assertion was made.

### Step 2 — Look at the arm

Switch to the **Schematic** tab.

![Geometry workspace, Schematic tab — the level composition, both endpoints at altitude,
with the tangent-depression leader pill.](figures/gui/case_irst_schematic.png)

This is the figure the Phase-4 geometry work exists for. Three things to check:

- **Both endpoints are drawn apart at the same abstract height**, with the ground plane
  pushed below both. The composition is chosen from the derived `los_direction`, never
  from a user switch. If this still drew the down-looking layout — sensor above, target
  on the ground plane — the composition split would be broken, and that would be a
  regression rather than a cosmetic complaint.
- **The altitude leader pills** read `h_t 10.0 km` at the target and `h_s 10.0` at the
  sensor, whose unit is clipped by the right edge of the viewport; the mode form beside
  the picture confirms both at 10 000 m. Altitude is *told*, not drawn to scale — the
  not-to-scale idiom that governs every RADIANT schematic.
- **The `Δh 49 m` pill** on the arm itself. It has no toggle; it is drawn whenever the
  scene is a level arm and hidden otherwise, exactly like the altitude pills.

There is no sun vector, because `solar_illumination` is `night`.

**What Δh is, and why it is a text label.** Both endpoints sit on the same shell of
radius $r = R_E + h$, so the straight chord between them sags *below* that shell and
each endpoint looks very slightly **down** at the other. The depression is

$$\Delta h = (R_E + h)\,(1 - \sin\zeta_{low}) \approx \frac{L^2}{8(R_E+h)},$$

which at $L = 50$ km is 48.97 m. Forty-nine metres over a fifty-kilometre arm is
invisible at any honest drawing scale, so it is annotated rather than drawn. And it
matters: Δh is the variable the horizon guard classifies a level path on, so this pill
is the analyst's early warning that a longer arm will trip it. The schematic calls
`radiant.core.viewing_triangle.classify_horizon_topology` and formats the result rather
than restating the formula, so the pill and the guard cannot disagree.

The same sag is why the path zenith at the target is *greater* than 90 degrees. The
derived readout below the mode form — scroll the centre pane — reports
$\theta_o = 1.574714$ rad = **90.2245°** at the target and $\eta = 89.7755°$ at the
sensor, with ground range 49 922 m. Those two sum to exactly 180.0000° and differ by the
Earth-centre central angle $\varphi = 0.44896°$, with $\theta_o = \pi/2 + \varphi/2$.
That identity is checkable on screen by revealing the $\theta_o$ and $\eta$ arcs from
the ANGLES panel; on a level arm the $\zeta_{low}$ arc coincides with $\theta_o$
exactly, and seeing the two overlap is the visual proof that the down/level and
up-looking branches meet continuously at equal altitudes.

### Step 3 — Read the spatial budget of an undersampled search sensor

Select stage **4 Optics**, tab **MTF**.

![Optics workspace, MTF tab — the IRST's MTF budget, with the pixel aperture ringing past
its first zero above Nyquist.](figures/gui/case_irst_mtf.png)

Nyquist is marked at **11.3 cycles/mrad**, which is $1/(2 \times 44.44\ \mu\mathrm{rad})$.
Two contributors bite; the caption lists charge diffusion, electronics, IPC, jitter and
TDI as "≈ 1.0 across band (not drawn)", and the table confirms them at exactly 1 at every
sampled fraction of Nyquist.

| Contributor | 0.25 × Nyq | 0.5 × Nyq | 0.75 × Nyq | 1 × Nyq |
|---|---:|---:|---:|---:|
| `mtf_optics` | 0.8981 | 0.7968 | 0.6970 | 0.5996 |
| `mtf_charge_diffusion` | 1 | 1 | 1 | 1 |
| `mtf_electronics` | 1 | 1 | 1 | 1 |
| `mtf_ipc` | 1 | 1 | 1 | 1 |
| `mtf_jitter` | 1 | 1 | 1 | 1 |

The optics term comes from the autocorrelation of the complex pupil — diffraction and
the 0.05-wave wavefront error together, never as two factors multiplied — and the pixel
aperture is the sinc of the 20 µm footprint. The shape worth noticing is the teal pixel
curve: it crosses zero near 22 cycles/mrad and then *rings*, and every one of those
sidelobes lies above Nyquist. In an undersampled sensor that energy is not resolution;
it is aliasing. That is the price the $Q = 0.6375$ design pays for its field of view,
and the Performance page reports an alias fraction of 0.503 at Nyquist to match.

### Step 4 — Read the noise budget

Select stage **7 Detector**, tab **Noise**.

![Detector workspace, Noise tab — the 50 km budget, dominated by the target's own shot
noise.](figures/gui/case_irst_noise.png)

| Term | σ [e- RMS] |
|---|---:|
| `signal_shot` | 305.4 |
| `background_shot` | 51.89 |
| `read_noise` | 40 |
| `quantization` | 17.61 |
| `dark_shot` | 2.236 |
| **Total (RSS)** | **313** |

This budget carries the most counter-intuitive result in the scenario. The target's own
shot noise is 305.4 e- RMS of a 313 e- RMS total — **95 % of the noise power comes from
the thing being detected.** Everything that is *not* the target — sky background shot,
read, quantization and dark — combines to 67.9 e- RMS.

That matters because a detection-range solver has to scale the noise as well as the
signal. Push the target out and its own shot noise goes with it, leaving the 67.9 e-
floor; freeze the total noise at its reference value instead, as a frozen-noise solver
does, and the near-field answer comes out strongly pessimistic. The shipped solver
uses $\sigma^2(R) = S(R) + N_0^2$ with $N_0$ the target-free floor, and the consequence
is visible in the next figure.

### Step 5 — Read the result, and notice what is missing

Select stage **10 Performance**.

![Performance workspace on the level arm — the ground-projection family absent by scene
class, target-plane sample distance in its place.](figures/gui/case_irst_performance.png)

**Sampling / geometry** opens with three rows that do not appear on any ground scene:
target-plane sample distance 2.222 m in x, y and geometric mean. That is $p\,d/f =
20\ \mu\mathrm{m} \times 50\ \mathrm{km} / 0.45\ \mathrm{m}$, and it is the right
substitute for GSD when there is no ground plane to project a footprint onto. $Q$ reads
0.6375 at band centre (0.525 at the short edge, 0.75 at the long one), classified
`detector-limited`, with a diffraction limit of 34.57 µrad. **There is no GSD row, no
ground range, no swath width, no access rate** — the eleven metrics the scene-class card
listed are genuinely absent from the result, not blank.

The pinned cards say the same thing in a second place: GSD and NIIRS both read
`n/a — not computed for this run`, and the Interpretability group carries only MRT at
Nyquist, 0.5364 K. Nothing in the configuration asked for this; it follows from the
derived scene class through one declarative relevance map.

**Spatial / MTF.** FWHM 20.65 µm cross-track and 20.6 µm along-track — 45.9 µrad, just
over the 44.44 µrad IFOV, which is the undersampling again. RER 0.7031, ensquared energy
0.5387 in the central pixel and 0.9185 over 3 × 3, MTF at Nyquist 0.3806, folded MTF
0.7659, alias fraction 0.503. Strehl ratio 0.9983 against a Maréchal value of 0.9978 —
the 0.05-wave wavefront error costs essentially nothing, and the two independent Strehl
routes agree to 5 × 10⁻⁴.

**Radiometric.**

| Metric | Value |
|---|---|
| SNR | 298.1 |
| Contrast SNR | 298.1 |
| SCNR | 298.1 |
| Detection range | 2.025 × 10⁵ m |
| NEDT | 90.74 mK |

**Saturation.** Well margin 20.61 dB, ADC margin 20.60 dB, dynamic range 70.09 dB. The
margin is $20\log_{10}$ of the ratio of capacity to filled charge, so 20.61 dB is a
factor of 10.7: the 100 µs frame fills about 9 % of the 1 Me- well at 50 km. Nothing in
the whole 25–100 km sweep saturates — the near end of the sweep still holds 4.6 dB.

The regime here is **`POINT_SOURCE`**, tentative in the source stage and final in
optics. An IRST target is specified as in-band radiant intensity in W/sr rather than as
a radiance, so the point-intensity door (emitter temperature 500 K, emitting area
0.36 m², emitter emissivity 0.90) is the native descriptor, and the ensquared-energy
fraction is applied once, in spectral integration, to the target term only. The
background is `SkyBackground`, selected by the line-of-sight termination classifier: the
ray continues *past* the target, and a level arm at 10 km leaves the atmosphere rather
than striking the ground. The same configuration aimed at a ground target would have
selected a ground background. Nothing in the scenario asks for either behaviour.

## What the study concludes

**The range sweep.** Over 25 → 100 km the runner reports:

| Range [km] | θ_o [deg] | Δh [m] | Guard | τ (MWIR) | Signal [e-] | Noise [e- RMS] | SNR | Det. range [km] |
|---:|---:|---:|---|---:|---:|---:|---:|---:|
| 25 | 90.11224 | 12.2 | clean | 0.6337 | 5.8803 × 10⁵ | 769.8 | 763.9 | 202.4 |
| 50 | 90.22448 | 49.0 | clean | 0.4023 | 9.3262 × 10⁴ | 312.8 | 298.1 | 202.5 |
| 75 | 90.33672 | 110.2 | **warn** | 0.2556 | 2.6329 × 10⁴ | 176.1 | 149.5 | 202.5 |
| 100 | 90.44896 | 195.9 | **warn** | 0.1625 | 9.4131 × 10³ | 119.1 | 79.0 | 202.2 |

The 50 km row is the baseline this chapter evaluated, and the GUI's SNR 298.1,
detection range 2.025 × 10⁵ m and 20.61 dB well margin are that row. SNR falls 9.9× over
a 4× range increase — steeper than inverse square, because the band transmittance falls
from 0.634 to 0.163 across the same span.

**The detection range is reference-range invariant**: 202.4 km solved from the 25 km
point against 202.2 km solved from the 100 km point, a spread of 1.001×. That is the
payoff of scaling the target's own shot noise along the path. Before that fix the same
design returned 123.4 km from 25 km and 182.5 km from 100 km — a 1.48× spread on one
unchanged sensor, and the nominal 50 km answer moved from 150.9 km to about 199 km when
it was corrected. The residual 0.3 km of spread is the band-mean transmittance model's
own reference dependence, not the noise treatment.

**The horizon guard warns, and quantifies what it is warning about.** Ten of the
sixteen sweep arms are clean (25–70 km, Δh 12.2–96.0 m) and six sit in the warning
shoulder (75–100 km, Δh 110.2–195.9 m); the analytic crossover
$L = \sqrt{8 r \Delta h_{clean}} = 71.45$ km falls between the 70 km and 75 km rungs.
The warning text names the excluded physics — RADIANT models no atmospheric refraction —
and sizes it: under the standard $k = 4/3$ effective-radius model the 100 km path would
bottom out 146.9 m below its lower endpoint rather than 195.9 m, so the modelled ray
samples air about 32.6 m lower on average than the real one, worth roughly **0.91 %** in
band transmittance. That is the right verdict for operational work: the scene computes,
the caveat is named and quantified, and the analyst decides.

**Target kinematics cost more than they look like they cost.** Platform motion alone
gives $\omega_{LOS}$ = 4.939 mrad/s; the crossing target (580 kt, heading 270 deg,
2 deg climb) raises it to **10.905 mrad/s**, a factor of 2.21. The two do *not* combine
in quadrature — they are two contributions to one focal-plane translation, so they
compose in the velocity domain and only then become a smear, and an RSS of two smears
would have returned 7.745 mrad/s and understated the blur by 29 %. At the 100 µs search
frame the smear is 0.0111 pixel platform-only against 0.0245 pixel with the target, so
it is negligible either way. The consequence is in the *budget*: the integration time
that produces one pixel of smear falls from 8.999 ms to 4.076 ms, a 54.7 % cut. Target
motion is free in search mode and binding in track mode.

**The atmosphere is the weakest link, and it is pessimistic.** Against the delivered
MODTRAN horizontal decks at the same profile and altitude, the parametric model's MWIR
band transmittance runs +19.7 % at 5 km, −3.1 % at 25 km, −30.8 % at 50 km and −66.8 %
at 100 km. The mechanism is named: a band-averaged transmittance is not multiplicative
in path length, because strong lines saturate first and flux leaks through the windows
between them. The effective band extinction must therefore *fall* with path length by
as much as $k(\lambda)$ varies inside the band, and the measurement is stark — MODTRAN's
$\alpha(5\,\mathrm{km})/\alpha(100\,\mathrm{km})$ is 7.60× in the MWIR against the
model's 1.01×. The model's $k(\lambda)$ is essentially flat across 3.5–5.0 µm, so it
cannot reproduce saturation at all. **Usable band on that evidence: within about 5 % out
to 25 km; beyond 50 km treat the MWIR numbers as a lower bound.**

Finally, the dual-path spatial consistency check runs silent on this scene: the maximum
disagreement between the FFT of the convolved PSF and the MTF product is 1.0 × 10⁻³
against a 2 × 10⁻² tolerance, twenty times inside it, with no warning records emitted.
A level arm changes the radiometry and the geometry, not the spatial degradations, so
there was no mechanism for the two paths to diverge — and the check confirms none did.

## The same study from a script

```bash
cd scenarios/10_direction_general/10.2_air_to_air_level_irst
python inputs/create_spreadsheet.py
python scripts/run_air_to_air_level_irst.py
```

The runner takes about seven seconds and does 39 chain evaluations: the 16-point range
sweep with both kinematics doors at each point, the horizon-guard classification, the
five independent hand cross-checks, and — when the horizontal MODTRAN decks are staged —
the transmittance comparison of the last section. Without those decks it prints a skipped
banner naming the missing runs and every other section is unaffected.
`scripts/gui_console_10.2_air_to_air_level_irst.py` is the same work as a paste-in for
the GUI's scripting console, where the schematic's own pill value is one call:

```python
from radiant.core.viewing_triangle import classify_horizon_topology
g = result.stage_outputs["geometry"]
res = classify_horizon_topology(g["theta_o_rad"], g["h_sensor_m"], g["h_target_m"])
print(res.topology, f"{res.dh_m:.2f} m", res.action)   # interior_tangent 48.97 m clean
```

The full geometry derivation, the verbatim guard and over-specification errors, the
kinematics-door matrix and the gap list are in the scenario's own `walkthrough.md`.
