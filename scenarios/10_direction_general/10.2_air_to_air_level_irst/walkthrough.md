# Scenario 10.2 — Air-to-Air Level-Arm MWIR IRST

**Series:** 10 — direction-general validation (Geometry-Flexibility Phase 5)
**Scene class:** `air_to_air` — observer × target grid cell E5, ADR-0011 §Context
**Persona:** Sarah (systems engineer) sizing an airborne MWIR IRST
**Runner:** `scripts/run_air_to_air_level_irst.py` (~7 s, 39 chain evaluations)
**Inputs:** `inputs/irst_air_to_air_vendor_data.xlsx` (vendor units: mm, %, ke-, ms, km, kt, °C)

---

## 1. The problem

Own-ship cruises at 10 km. The target cruises **co-altitude** at 10 km. Sarah
needs to know:

1. How far can this IRST see the target, and how does SNR fall with range?
2. The line of sight is horizontal. Does RADIANT even accept that geometry, and
   what does it warn about when it does?
3. The target is manoeuvring. What does the relative line-of-sight rate do to
   the integration-time budget?
4. How much can she trust the atmosphere model on a 100 km horizontal path at
   cruise altitude?

Before Geometry-Flexibility Phases 1–4 the answer to (2) was "RADIANT refuses
the scene": equal altitudes were a *geometry-free* collocated carve-out and
$\theta_o \ge \pi/2$ was rejected three times independently (ADR-0011 §Context,
findings GF-1/GF-2/GF-11). This scenario is the validation that the level arm
now works end to end.

## 2. The system

| Quantity | Vendor value | Vendor unit | Canonical value | Canonical unit |
|---|---|---|---|---|
| Entrance pupil diameter | 150 | mm | 0.1500 | m |
| Effective focal length | 450 | mm | 0.4500 | m |
| f-number | 3.0 | — | 3.0 | — |
| Optical transmission | 75 | % | 0.7500 | fraction |
| Optics temperature | −23.15 | °C | 250.00 | K |
| Central obscuration | 0 | % | 0 | fraction |
| WFE RMS | 0.05 | waves | 0.05 | waves |
| Spectral band | 3.50 – 5.00 | µm | 3.50 – 5.00 | µm |
| Pixel pitch | 20 | µm | 20 | µm |
| Fill factor | 100 | % | 1.00 | fraction |
| Quantum efficiency | 80 | % | 0.80 | fraction |
| Dark current | 50 000 | e⁻/s | 50 000 | e⁻/s |
| FPA temperature | 80 | K | 80 | K |
| Read noise | 40 | e⁻ RMS | 40 | e⁻ RMS |
| Full well | 1000 | ke⁻ | 1.000 × 10⁶ | e⁻ |
| System gain | 61 | e⁻/DN | 61 | e⁻/DN |
| ADC | 14 | bits | 14 | bits |
| Frame integration | 0.10 | ms | 1.00 × 10⁻⁴ | s |
| Own-ship altitude | 10 | km | 10 000 | m |
| Target altitude | 10 | km | 10 000 | m |
| Target hot-parts temperature | 226.85 | °C | 500.00 | K |
| Target hot-parts area | 0.36 | m² | 0.36 | m² |
| Target emissivity | 90 | % | 0.90 | fraction |
| Own-ship TAS | 480 | kt | 246.93 | m/s |
| Target TAS | 580 | kt | 298.38 | m/s |
| Target heading | 270 | deg | 4.712389 | rad |
| Target climb | 2 | deg | 0.034907 | rad |
| Atmosphere | midlat_summer, PWV 2.92 cm, vis 23 km, rural | — | same | — |

Derived instrument scales: **IFOV = 44.44 µrad**, band centre **4.250 µm**,
**Q = λF/p = 0.637** (undersampled — normal for a search IRST), system PSF FWHM
**45.88 µrad**.

The atmosphere is deliberately set to the *same* profile / PWV / visibility /
aerosol as the delivered MODTRAN horizontal grid, so §7's anchor is
apples-to-apples rather than approximately-so.

## 3. Approach

The runner sweeps the level-arm slant range 25 → 100 km in 5 km steps
(16 points, both kinematics doors at each point) with `atmosphere.model = "simple"`.
The viewing geometry is entered through mode **V0** (`geometry.target_range_m`):
for equal altitudes the chord fixes the central angle directly, which is the
solution that subsumed the pre-ADR-0011 collocated no-triangle carve-out
(guardrail G4).

Everything else in the chain is held fixed; the only swept variable is range.

## 4. Results

### 4.1 Scene class, level-arm geometry, and the Δh sag

| Stage output | Value |
|---|---|
| `scene_class` | `air_to_air` (derived, `Provenance.DERIVED`) |
| `observer_class` / `target_class` | `air` / `air` |
| `los_direction` | `level` (derived from the altitude pair — never a user switch) |
| `viewing_mode` | `geometry.target_range_m (level path — chord ⇒ central angle)` |
| θ_o at 50 km | 1.574714218 rad = **90.22448°** |
| η at 50 km | 1.566878436 rad = 89.77552° |
| ground range at 50 km | 49.922 km (surface arc) |

θ_o is *greater* than 90° on a level arm and this is not a rounding artefact:
both endpoints sit on the same shell of radius $r = R_E + h$, so the straight
chord sags below that shell and each endpoint looks slightly **down** at the
other,

$$\varphi = 2\arcsin\!\left(\frac{d}{2r}\right), \qquad
  \theta_o = \frac{\pi}{2} + \frac{\varphi}{2}\;\text{at both endpoints.}$$

The horizon classifier reports topology `interior_tangent` — the perpendicular
from the Earth's centre falls *on* the segment, so the ray dips to a tangent
point between the endpoints. The depression is

$$\Delta h = (R_E + h)\,(1 - \sin\zeta_{low}) \approx \frac{L^2}{8(R_E+h)}.$$

At 50 km, **Δh = 48.97 m** (tangent altitude 9951.0 m MSL). This is the same
number the GUI schematic prints in its **Δh leader pill** — the schematic calls
`core.viewing_triangle.classify_horizon_topology` rather than restating the
formula, so the pill and the guard cannot disagree. At the nominal point the
pill reads `Δh  49 m`.

### 4.2 The range sweep

`outputs/10.2_snr_and_detection_range_vs_range.png`

| Range [km] | θ_o [deg] | Δh [m] | guard | τ MWIR [–] | signal [e⁻] | noise [e⁻ rms] | SNR [–] | det. range [km] | well margin [dB] |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 25 | 90.11224 | 12.2 | clean | 0.6337 | 5.3390e5 | 733.8 | 727.6 | 199.0 | 5.5 |
| 40 | 90.17958 | 31.3 | clean | 0.4824 | 1.5869e5 | 404.1 | 392.7 | 199.1 | 16.0 |
| 50 | 90.22448 | 49.0 | clean | 0.4023 | 8.4677e4 | 298.8 | 283.4 | 199.1 | 21.4 |
| 70 | 90.31427 | 96.0 | clean | 0.2799 | 3.0047e4 | 186.3 | 161.3 | 199.1 | 30.4 |
| 75 | 90.33672 | 110.2 | **warn** | 0.2556 | 2.3905e4 | 169.1 | 141.4 | 199.0 | 32.4 |
| 100 | 90.44896 | 195.9 | **warn** | 0.1625 | 8.5466e3 | 115.5 | 74.0 | 198.8 | 41.4 |

*Numbers refreshed 2026-09-01. One mover since the previous vintage: **CU-336**
corrected the gas fit's grid convention, so the floors CU-335 had over-fitted
come down. This is a 3–5 µm level path, so the reach is again the λ⁻⁴ tail
(3.50–5.00 µm floor 0.4498 -> 0.4494 OD), running the other way: τ rises in the
fourth decimal at every range rung (0.4020 -> 0.4023 at 50 km), the nominal
detection range 198.9 -> 199.1 km (+0.1 %), and α_eff falls in the fifth digit
(0.01823 -> 0.01821 km⁻¹ at 50 km). No verdict moves.*

*Prior vintage, 2026-08-30. **CU-335** re-fitted the calibrated gas table's
VIS/NIR/SWIR rows against the post-CU-253 Rayleigh; the same λ⁻⁴ tail took τ
0.4021 → 0.4020 at 50 km and the nominal detection range 199.0 → 198.9 km.*

*Composed with CU-335 on the merged tree, 2026-08-31: CU-335 and CU-324 item 2 were
each measured on a tree that did not contain the other, and re-running on `main` with
both present moves the fourth significant figure back — τ at 25 km 0.6334 → 0.6335,
every signal rung by ≈ 4 × 10⁻⁵ relative (50 km: 8.4631e4 → 8.4616e4 e⁻), and the
detection range at the 40/50/70 km rungs 198.9 → 199.0 km, i.e. the −0.05 % step the
CU-335 branch measured is cancelled on the composed tree. τ, noise, SNR and well
margin at every other rung, and every verdict in this document, are unchanged.*

*Prior vintage, 2026-08-02, pre-CU-321. Dominant mover: **CU-321** — the height-resolved
emission temperature. This is a **level** path, and a level arm is isothermal,
so the arm's own `T_eff` collapses to the exact profile temperature at 10 km
and its thermal emission is untouched by the layering; what moves is the
**sky background** behind the target, which comes from the whole traversed
level path (`level_whole_path`, CU-224) and does span altitudes. Its emission
falls slightly, taking ~0.3 % off the noise column, so SNR and detection range
edge **up** (nominal 50 km: SNR 282.8 → 283.4, range 197.9 → 199.1 km). The
signal and τ columns are bit-identical. One second-order consequence worth
noting: the arm's `T_eff` also lost the CU-155 200 m emission-height offset
(it was fit for the hemispheric sky flux, not for a directional arm), which is
a 1.3 K change in the arm's graybody temperature — visible only in the fifth
digit here.*

(The full 16-row table is in `outputs/10.2_air_to_air_results.xlsx`, regenerated
by running the script.)

SNR falls 9.9× over a 4× range increase — steeper than inverse-square because
the band transmittance falls from 0.634 to 0.163 over the same span. No pixel
saturates anywhere in the sweep (well margin 5.5 dB at the near end).

**One warning other than the horizon guard is raised, at every sweep point.**
The runner classifies it as UNEXPECTED and prints it in full:

> `optics.optics_temperature_K = 250 K is set, but in scalar transmission mode
> the optics' self-emission is ε·B(λ, T_optics) with ε = optics.scalar_emissivity,
> which is 0 (the default 'refractive lump' assumption). The temperature
> therefore contributes nothing: this scene evaluates identically at any optics
> temperature.`

This is CU-261/265's inert-optics-temperature warning, and it is telling the
truth about *this* configuration: the vendor table's −23.15 °C optics
temperature (§2) is carried through the config but is radiometrically inert,
because the scenario models the refractive head as a scalar transmission lump
with `scalar_emissivity = 0` rather than as a Kirchhoff-derived element list.
Every number in this walkthrough is therefore independent of the optics
temperature. The scenario config is left unmodified rather than silenced — the
warning is the correct Rule-17 report of an over-specified input, not a defect
to suppress.

**Non-obvious result — `detection_range_m` is reference-range invariant**
(199.0 km referenced at 25 km, 198.8 km referenced at 100 km, a factor 1.00).
The path-aware solver scales the *signal* along the path,
$S(R) = S_{ref}(R_{ref}/R)^2\,\tau(R)/\tau(R_{ref})$, **and the target's own
shot noise with it**: $\sigma^2(R) = S(R) + N_0^2$, with $N_0$ the target-free
floor. Until CU-263 (2026-08-01) the **total** noise was frozen at its reference
value, which is exact only in a background-limited system. This one is not, at
short range:

| range [km] | total noise [e⁻ rms] | of which target shot [e⁻ rms] | target-free floor [e⁻ rms] |
|---:|---:|---:|---:|
| 25 | 733.8 | 730.7 | 67.5 |
| 100 | 115.5 | 92.5 | 69.2 |

At 25 km the noise is almost entirely the *target's own* shot noise, which
vanishes as the target recedes. Freezing it used to make the near-field answer
strongly pessimistic — **123.4 km referenced at 25 km against 182.5 km
referenced at 100 km, a 1.48× spread on one unchanged design**, which is what
CU-263 was filed against. The nominal 50 km answer moved **150.9 km → 199.1 km
(+31.9 %)** with the fix. The residual 0.3 km spread across the sweep is the
band-mean τ model's own reference dependence ($\alpha_{eff}$ moves in the fifth
digit, 0.01826 → 0.01818 km⁻¹), not the noise treatment.

Cross-check: re-solving against the target-free floor **alone** (sky background
shot + read + quantisation + dark = **69.2 e⁻ rms**, dropping the target's own
residual shot noise entirely) gives **200.0 km at SNR = 5** — the fully
floor-limited bound, which must sit just *above* the chain's 198.7 km. They
agree to 0.7 %. That is the number an IRST engineer would quote for this design
against this target on the simple model, and the shipped metric now reproduces
it.

### 4.3 The horizon guard across the sweep

`outputs/10.2_horizon_guard_tangent_depression.png`

10 of 16 arms are **clean** (25–70 km, Δh 12.2–96.0 m); 6 are in the
**warning shoulder** (75–100 km, Δh 110.2–195.9 m). The analytic crossover
$L = \sqrt{8 r \Delta h_{clean}} = \sqrt{8 \times 6381\,\text{km} \times 100\,\text{m}}
= 71.45\,\text{km}$ falls exactly between the 70 km (clean) and 75 km (warn)
sweep points.

The verbatim `UserWarning` on the 100 km arm:

> `LineOfSightGeometry: horizon guard: near-horizontal path — interior tangent
> point 195.9 m below the lower endpoint (10000.0 m MSL); tangent altitude
> 9804.1 m. Computing anyway, but atmospheric refraction is NOT modelled in
> v1.x and is the dominant geometric error in this band (hard guard at ±0.5° /
> 2000 m tangent depression; thresholds provisional pending Phase 2 MODTRAN
> calibration). Size of the omission: under the standard k = 1.33
> effective-radius model this path would bottom out at 146.9 m rather than
> 195.9 m below its lower endpoint, i.e. the air this path is sampled through
> sits on average ~32.6 m lower than the true refracted ray's — so the band
> transmittance is biased slightly low.`

**What it caveats, quantified.** RADIANT models no refraction at all
(ADR-0011 decision 5). Refraction bends the ray downward, conventionally
absorbed into an effective Earth radius $kR_E$; with the standard $k = 4/3$ the
sag becomes $\Delta h/k = 146.9$ m instead of 195.9 m, so the modelled ray
samples air an average of **32.6 m lower** than the real one (2/3 of the
difference — the mean of a parabolic sag). With a density scale height of
6.5 km and a band optical depth of 1.818 on that arm, that altitude error is
worth

$$\frac{\delta\tau}{\tau} \approx \tau_{od}\,\frac{\delta z}{H} = \mathbf{0.91\ \%}$$

in band transmittance. The guard is therefore flagging a **sub-percent** effect
— correctly, because Rule 17 forbids silent unmodelled physics, but it is *not*
the dominant error on this arm. §4.5 shows the simple model's own band-model
error on the same path is 67 %, two orders of magnitude larger. The $k = 4/3$
factor is a standard-atmosphere convention used here only to size the excluded
effect; it is not a RADIANT result.

The `warn` shoulder is the right verdict for operational air-to-air work: the
scene computes, the caveat is named and quantified, and the analyst decides.

### 4.4 Target kinematics — both Gap 111 doors

`outputs/10.2_los_rate_and_smear_budget.png`

At the nominal 50 km point:

| Door | `los_rate_mode` | ω_LOS [mrad/s] | smear [µm] |
|---|---|---:|---:|
| K0 (no kinematics input) | `platform-only (derived)` | 4.93866 | 0.2222 |
| K2 (speed + heading + climb) | `target velocity (K2)` | 10.90457 | 0.4907 |
| K1 (rate entered directly) | `geometry.los_angular_rate_rad_s` | 10.90457 | — |
| K1 + K2 together | `geometry.los_angular_rate_rad_s + target velocity (K2) (consistent)` | 10.90457 | — |

K1 vs K2 relative difference: **0.000e+00** (agreement bound 1 %). Feeding K1 a
deliberately wrong rate raises, as the V0–V4 pattern requires:

> `GeometrySpecificationError: Over-specified LOS-rate geometry: 2 inputs imply
> disagreeing values — geometry.los_angular_rate_rad_s ⇒ 0.0218091 rad/s;
> target velocity (K2) ⇒ 0.0109 rad/s`

**Why the rates add rather than RSS.** Platform motion and target motion are not
two independent blurs; they are two contributions to one focal-plane
translation, so they compose in the **velocity** domain and only then become a
smear. The beam-aspect crosser (heading 270°, i.e. against the platform's
cross-track motion) gives
$v_\perp = v_T\cos\gamma\sin\psi - v_S = -545.13$ m/s, so 4.939 mrad/s
platform-only becomes **10.905 mrad/s** relative — a factor 2.21. An RSS of two
smears would have returned 7.745 mrad/s, understating the blur by 29 %.

**Smear consequence.** At the 100 µs search frame the smear is 0.0111 pixel
(K0) and 0.0245 pixel (K2) — negligible either way. The design consequence is
in the *budget*: the integration time that produces one pixel of smear falls
from **8.999 ms** (platform only) to **4.076 ms** (crossing target), a **54.7 %**
cut. Target motion costs nothing in search mode and becomes the binding
constraint only for track-mode integration.

### 4.5 Cross-model anchor — level arm vs the MODTRAN horizontal grid

`outputs/10.2_transmittance_vs_modtran_lgrid.png`

Model side: `evaluate_level_arm(SimpleAtmosphere(midlat_summer, PWV 2.92 cm,
vis 23 km, rural), LevelArmSpec(h = 10 km, L))`. MODTRAN side: the delivered
ITYPE=1 horizontal decks **L16–L20** (`docs/plans/modtran_run_matrix.csv`),
H1 = H2 = 10 km, Card-3 RANGE = L, identical profile / aerosol / visibility.
Both sides are band-mean transmittance (dimensionless).

*Numbers refreshed 2026-08-02 from the unmodified runner with
`modtran/real_runs/L16–L20` staged (previous vintage 2026-08-01, when the
model-τ column had gone stale for want of the run set). Dominant mover: CU-267 —
the gas-region C1 smoothstep blend raises the model's band extinction ≈ 0.7 % in
both bands. The MODTRAN columns are delivered measurements and do not move.*

**MWIR 3.5–5.0 µm — this sensor's own band:**

| run | range [km] | MODTRAN τ | model τ | ratio | difference [%] | α MODTRAN [1/km] | α model [1/km] |
|---|---:|---:|---:|---:|---:|---:|---:|
| L16 | 5 | 0.7621 | 0.9124 | 1.197 | +19.7 | 0.05434 | 0.01833 |
| L17 | 10 | 0.7230 | 0.8327 | 1.152 | +15.2 | 0.03243 | 0.01831 |
| L18 | 25 | 0.6535 | 0.6334 | 0.969 | −3.1 | 0.01701 | 0.01827 |
| L19 | 50 | 0.5810 | 0.4020 | 0.692 | −30.8 | 0.01086 | 0.01823 |
| L20 | 100 | 0.4894 | 0.1623 | 0.332 | −66.8 | 0.00715 | 0.01819 |

**LWIR 8–12 µm — reference band:**

| run | range [km] | MODTRAN τ | model τ | ratio | difference [%] | α MODTRAN [1/km] | α model [1/km] |
|---|---:|---:|---:|---:|---:|---:|---:|
| L16 | 5 | 0.9725 | 0.9634 | 0.991 | −0.9 | 0.00557 | 0.00745 |
| L17 | 10 | 0.9521 | 0.9324 | 0.979 | −2.1 | 0.00491 | 0.00700 |
| L18 | 25 | 0.9064 | 0.8539 | 0.942 | −5.8 | 0.00393 | 0.00632 |
| L19 | 50 | 0.8567 | 0.7566 | 0.883 | −11.7 | 0.00309 | 0.00558 |
| L20 | 100 | 0.7950 | 0.6257 | 0.787 | −21.3 | 0.00229 | 0.00469 |

*LWIR table refreshed 2026-08-29 from the unmodified runner — **CU-330**, the
9.6 µm ozone region split. The model gains real in-band opacity, so its α model
column rises 9–16 % and every model τ falls; the MODTRAN columns are delivered
measurements and are untouched, as is the entire MWIR table above (the split
touches only 8–10 µm). Net effect on the disagreement: it shrinks at long range
(L20 ratio 0.753 → 0.787) and grows slightly at short range (L16 0.996 → 0.991),
which is the expected sign — the model was short of band opacity, and adding it
helps most where the path is long enough for that shortfall to compound.*

The MWIR α model column is now the same quantity the sweep table in §4.2 reports
as `α_eff` (0.01826 km⁻¹ at 25 km, 0.01818 km⁻¹ at 100 km) — the two agree to
0.06 %, which is the check that §4.5 and §4.2 are evaluating one atmosphere and
not two. (They no longer agree to the last *printed* digit, as they did before the
2026-08-31 composition: §4.2 band-averages τ on the chain's own wavelength grid and
§4.5 on the MODTRAN deck's wavenumber grid, so a band mean over a spectrum that has
just gained structure need not land on the same fifth digit twice.)

The LWIR ratios reproduce the values pinned in
`tests/integration/test_uplooking_horizontal_anchors.py::
test_level_arm_vs_the_full_horizontal_grid` for the 10 km row
(0.991 / 0.979 / 0.942 / 0.883 / 0.787) to within 0.001 — the scenario and the
golden test are measuring the same thing on the same runs. Both were refreshed
together by CU-330 on 2026-08-29; before that the pins were a pre-CU-267 vintage
sitting ≈ 0.002 high at the long end, and that gap is now closed.

**Expected residual, and why it is one-sided at long range.** A band-averaged
transmittance is not multiplicative in path length. Within a band the strong
lines saturate first and flux leaks through the windows between them, so by
Jensen's inequality $\langle e^{-2kL}\rangle \ge \langle e^{-kL}\rangle^2$, with
equality **only if $k(\lambda)$ is flat across the band**. Equivalently the
effective band extinction $\alpha = -\ln\tau / L$ must fall with path length by
exactly as much as $k(\lambda)$ varies inside the band. The last two columns
measure that on both sides:

| band | α(5 km)/α(100 km), MODTRAN | α(5 km)/α(100 km), model |
|---|---:|---:|
| MWIR 3.5–5.0 µm | **7.60×** | 1.01× |
| LWIR 8–12 µm | **2.43×** | 1.59× |

In the MWIR the simple model's $k(\lambda)$ is essentially **flat** across
3.5–5.0 µm — the documented CU-161 region-flat spectral-shape limitation — so
its band mean stays very nearly exponential (α drifts 1 % over a 20× path) and
it cannot reproduce MODTRAN's saturation at all. In the LWIR the model carries
some spectral structure and recovers part of the effect, but still far too
little. Real MWIR line structure (the CO₂ 4.3 µm band and dense H₂O lines
cutting the window) is what MODTRAN has and the model does not. *The LWIR figure
moved 1.25× → 1.59× on 2026-08-29 (CU-330): splitting the 8–10 µm region at the
ozone band gave the model real in-band structure where it had a flat average, and
it recovers correspondingly more of MODTRAN's saturation. That is the same
mechanism this paragraph names, applied once — a direct measurement of what a
finer partition buys.*

**Direction of the consequence for this scenario:** the model is progressively
*too opaque* as the arm lengthens, so RADIANT's SNR and detection range at the
long end of the sweep are **pessimistic**. Usable band on this evidence: within
~5 % out to 25 km; beyond ~50 km treat the MWIR numbers as a lower bound.

### 4.6 Regime, background, and the metric-relevance flip

- **Regime:** `POINT_SOURCE`, final in `OpticsStage`, tentative already in
  `SourceStage`. An IRST target is specified as in-band radiant intensity
  $I$ [W/sr], not radiance, so the **T7** point-intensity door
  (`point_intensity_temperature_K` + `_area_m2` + `_emissivity`) is the native
  descriptor. EE_box is applied once, in `SpectralIntegrationStage`, to the
  target term only (Rule 9).
- **Background:** `SkyBackground`, selected by the LOS-termination classifier —
  it follows the ray *past* the target, and a level arm at 10 km leaves the
  atmosphere rather than striking the ground. The same configuration with a
  ground target would have selected `GroundBackground`. This is the
  direction-general behaviour; nothing in the scenario asks for it.
- **Metric relevance (guardrail G3):** for an **air** target the whole
  ground-projection family defaults off — eleven metrics: `gsd_cross_track_m`,
  `gsd_along_track_m`, `gsd_geometric_mean_m`, `ground_range_m`,
  `swath_width_m`, `access_rate_m2_s`, `diffraction_limit_ground_m`,
  `diffraction_limit_target_plane_m`, `max_integration_time_s`, `niirs`,
  `niirs_extrapolated` — all verified absent
  from `result.metrics`. In their place
  `target_plane_sample_distance_{x,y,geometric_mean}_m` default **on**, all
  = 2.2222 m at 50 km. There is no ground plane at an airborne target to
  project a footprint onto; $p\,d/f$ is the right sample distance instead.

**Parameters that do not affect this result, and why**

| Parameter | Why inert here |
|---|---|
| `geometry.solar_zenith_rad`, `geometry.solar_azimuth_rad` | `solar_illumination = "night"` — no reflected-solar term in either the source or the sky background |
| `source.background.temperature`, `source.background.emissivity` | The background is `SkyBackground`; its radiance comes from the atmosphere stage, not from a user-set surface |
| `optics.obscuration_ratio` | 0 for the refractive head — the pupil is a filled circle, so no obscuration term enters the autocorrelation |
| `geometry.circular_orbit` | An aircraft is not in orbit; platform speed comes from the direct ground-speed door |

## 5. Independent cross-checks

Five, all computed inside the runner so they cannot drift from the results:

| # | Check | Hand value | RADIANT | Relative difference |
|---|---|---|---|---|
| 1 | Level-arm θ_o closed form, $\pi/2 + \varphi/2$ with $\varphi = 2\arcsin(d/2r)$ | 1.574714218 rad | 1.574714218 rad | 0.00e+00 |
| 2 | Tangent depression $L^2/8r$ at 25 / 50 / 100 km | 12.24 / 48.97 / 195.89 m | 12.24 / 48.97 / 195.90 m | ≤ 1.5e−05 |
| 3 | Point-source signal scaling $S \propto I\tau(R)/R^2$: $S(50)/S(25)$ | 0.158658 | 0.158544 | 7.2e−04 |
| 4 | Relative LOS rate $\lvert \mathbf v_{rel}\times\hat u\rvert / R$ | 0.010904566 rad/s | 0.010904566 rad/s | 1.5e−14 |
| 5 | Target-plane sample distance $p\,d/f$ | 2.222222 m | 2.222222 m | 1.5e−14 |
| 6 | MODTRAN L16–L20 band-mean τ (§4.5) | see tables | see tables | LWIR ratios match the pinned golden test to 3 figures |

Check 2 is the small-angle form of an exact spherical result, so its residual
grows as $L^2$ — 9.6e−07 at 25 km, 1.5e−05 at 100 km, exactly the fourth-order
term. Check 3 is the load-bearing one for an air target: it proves the
point-source term is genuinely inverse-square in the *slant* range and
Beer-Lambert in the band τ, with no ground-projection factor sneaking in.

## 6. Rule-4 dual-path consistency

Run at the nominal point with warnings visible and a logging handler attached to
the root logger:

```
passed_x / passed_y:          True / True
max |FFT(PSF) - prod(MTF)| x: 0.001041 (dimensionless)
max |FFT(PSF) - prod(MTF)| y: 0.001025 (dimensionless)
tolerance:                    0.020000
consistency WARNING log records emitted: 0
non-horizon Python warnings at the nominal point: 1
  - optics.optics_temperature_K = 250 K is set, but in scalar transmission
    mode the optics' self-emission is ε·B(λ, T_optics) with
    ε = optics.scalar_emissivity, which is 0 …
```

The single non-horizon warning is the inert-optics-temperature report discussed
in §4.2; it is a configuration caveat, not a consistency failure, and no
`consistency_check` log record was emitted.

**Verdict: SILENT for the `air_to_air` level arm.** The residual (1.0e−03) is
20× inside the 2e−02 tolerance and is the ordinary discretisation floor. Both
paths root in the same complex pupil; the level arm changes the radiometry and
the geometry, not the spatial degradations, so there was no mechanism for the
paths to diverge — and the check confirms none did.

## 7. Gaps

Four, all in `gaps.md` and mirrored in the structured report. **Gap 2 was closed
on 2026-08-01 by CU-263** — it is retained below with its resolution so the
scenario's own record of the finding survives:

1. The **T7 point-intensity door bypasses the matrix-§7 point-source
   angular-size guard** (it publishes a sentinel angular extent), so a target
   0.52× the PSF FWHM was accepted silently where the T1 radiance door would
   have raised.
2. ~~`detection_range_m` **holds total noise constant**, including the target's
   own shot noise, so the metric depends on the range it is evaluated at (1.48×
   across this sweep).~~ **RESOLVED 2026-08-01 (CU-263):** the solvers now use
   $\sigma^2(R) = S(R) + N_0^2$; the spread across this sweep is 1.00× and the
   nominal answer moved 150.9 km → 199.0 km.
3. **No refraction model** — guard-banded by design (ADR-0011 decision 5), but
   the scenario has to estimate the excluded effect itself to know whether the
   warning matters.
4. The **simple level arm cannot reproduce band saturation in the MWIR**
   (CU-161 region-flat spectral shape), so long-arm MWIR results are
   systematically pessimistic; the scenario needs the MODTRAN grid to bound the
   error.

## 8. What Sarah does next

- Re-run the sweep against a **MODTRAN horizontal library** for the MWIR rather
  than the simple model, now that §4.5 has bounded the error at −67 % at 100 km.
  The L-grid decks already exist; what is missing is an interpolated horizontal
  family (`InterpolatedAtmosphere` with a range axis at constant altitude).
- Sweep **altitude** as well as range — the L-grid's 3/5/10/15 km rows say the
  model/MODTRAN agreement improves sharply with altitude, so a 15 km CAP would
  be both physically better and better modelled.
- Trade **aperture vs frame time** against the 4.076 ms crossing-target smear
  budget from §4.4: the design has 40× headroom at the search frame, which is
  where a larger aperture or a longer track-mode dwell should be spent.
- Repeat with an **up-looking** geometry (target above own-ship) to close out
  the third direction, which shares the same segment machinery.

## 9. Reproducing

```bash
pip install -e ".[dev,scenarios]"
python scenarios/10_direction_general/10.2_air_to_air_level_irst/inputs/create_spreadsheet.py
python scenarios/10_direction_general/10.2_air_to_air_level_irst/scripts/run_air_to_air_level_irst.py
```

§4.5 additionally needs `modtran/real_runs/L16–L20.tp7` staged (gitignored — see
`modtran/real_runs/README.md`). Without them the runner prints a SKIPPED banner
naming the missing runs and every other section is unaffected.
