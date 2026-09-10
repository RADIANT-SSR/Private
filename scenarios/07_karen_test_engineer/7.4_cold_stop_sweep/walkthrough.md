# Scenario 7.4 Walkthrough: Cold-Stop Undersizing Sweep

Rebuilt 2026-09-09 under Gap 128 (étendue-conserving near-field; the cold stop
as an undersized aperture stop, owner-ratified). The scenario previously swept
`optics.nearfield_fraction`, a "leakage fraction" that let a cold stop attenuate
warm-optics emission. That knob was unphysical and has been deleted: in-cone
emission arrives through the imaging path itself and cannot be blocked, while
out-of-cone warm structure is taken to be blocked completely. The question the
scenario answers is now the real cold-stop trade — **how much undersizing margin
can the camera afford?**

## The Problem

Karen is a test engineer running a thermal-vacuum (TVAC) characterization
campaign on an MWIR imager. The cold stop in that camera *is* the aperture stop:
a cryogenic aperture at ~77 K that defines the beam. It is deliberately built a
little smaller than the primary, so that alignment and thermal tolerances can
never let the focal plane see past it to warm structure.

Undersizing buys that certainty and pays for it in photons. Karen needs:

1. **What does undersizing cost?** Signal, SNR, NEDT, and resolution, as a
   function of the undersizing fraction *u*.
2. **Does it help the background?** The spec says the shuttered background must
   be below 40,000 e⁻.
3. **What do her lab measurements now mean?** Six shuttered-background readings
   at different cold-stop offsets, from 35,500 to 55,750 e⁻.

## The Model Rules (Gap 128, owner-ratified 2026-09-09)

The cold stop is the aperture stop, slightly undersized for tolerancing:

```
D_eff  = (1 − u) · aperture_diameter_m          [m]
N_eff  = focal_length_m / D_eff                  [-]
Ω_cone = 2π (1 − cos θ),  θ = arctan(1/(2·N_eff)) [sr]
```

That single effective pupil feeds **everything** the pupil sets:

- `A_collect` [m²] — so signal scales as (1 − u)²;
- `N_eff` [-] — the working f-number;
- the complex pupil function — the diffraction PSF *and* the MTF product, from
  one pupil (Rule 4, both spatial paths);
- `Ω_cone` [sr] — the étendue acceptance cone, the **only** near-field geometry.

Warm-optics emission is
`E_nf(λ) = Ω_cone · Σ_i ε_i(λ) · B(λ, T_i) · τ_down,i(λ)` [W/m²/µm]. Every
in-beam element is seen through the same cone: the Lagrange invariant fixes what
the focal plane can accept, so an element cannot subtend more solid angle by
sitting close to it. Per-element `diameter_m` / `distance_to_fpa_m` are gone.

**Consequence that matters here: signal and near-field fall together.**
Undersizing is not a way to buy a darker background for free.

## The Warm Train (Kirchhoff, Rule 5; Gap 127/128)

The workbook quotes one end-to-end transmission, τ = 0.68 [-]. Reading the whole
1 − τ loss as absorption — the ε = 1 − τ fallacy — would put ε = 0.32 [-] on the
train and over-state warm-optics emission several-fold. A real MWIR camera loses
most of that τ at coatings and at the cold filter, not to absorption.

The train is therefore modelled as what it is:

| Element | Type | Value | Kirchhoff ε |
|---------|------|-------|-------------|
| fold_mirror_1..3 | MIRROR | R = 0.98 [-] each | ε = 1 − R = 0.02 [-] each |
| cold_window | WINDOW (AR-coated) | T = 0.7225 [-] | ε = 0 [-] (Gap 127) |

Net throughput 0.98³ × 0.7225 = 0.68 [-] — the workbook value, exactly — with an
emitting emissivity of 0.06 [-] instead of 0.32 [-].

## Step 1: Read and Convert Karen's Lab Data

Three-sheet Excel workbook, vendor and lab units, converted at the boundary:

- 25 cm → 0.25 m (aperture)
- 1000 mm → 1.0 m (focal length) ⇒ f/4.0
- 20 °C → 293.15 K (optics temperature)
- 80 fA/pixel → 499,376 e⁻/s (dark current: fA × 1e-15 ÷ q_e)
- 3700–4800 nm → 3.70–4.80 µm (bandpass)
- 8 ms → 0.008 s (integration time)
- 68 % → 0.68 [-] (net transmission), decomposed into the train above

One vendor number now has **no model home**: "cold stop design efficiency"
(a blocked fraction). The script says so explicitly rather than mapping it onto
something that does not mean the same thing.

## Step 2: Configure the Vacuum Chamber

Atmosphere model "exo" (vacuum). Two consequences of the current architecture
(registry Gap 42), unchanged by this rebuild:

- The exo backend auto-infers the `no_atmosphere` **space** sub-case, so the run
  carries a placeholder `geometry.sensor_altitude_m = 1.0` m (≈ bench height) to
  satisfy the Earth-limb intercept check. No radiometric effect here.
- The blackbody fills the FOV → **extended regime**, in which RADIANT skips the
  separate scene-background photon term (matrix Decision #13): `background_e = 0`
  by design. The only background terms are warm-optics near-field and dark.

## Step 3: The Baseline — Cold Stop Matched to the Primary (u = 0)

| Quantity | Value | Unit |
|----------|-------|------|
| D_eff | 0.25000 | m |
| f/#_eff | 4.0000 | [-] |
| A_collect | 0.049087 | m² |
| Ω_cone | 0.048520 | sr |
| Signal | 2,994,945 | e⁻ |
| Near-field | 106,631 | e⁻ |
| SNR | 1699.3 | [-] |
| NEDT | 17.00 | mK |
| MTF at Nyquist | 0.3017 | [-] |

Noise budget: signal shot 1730.6, near-field shot 326.5, dark shot 63.2, read
25.0, quantization 0.7 e⁻ RMS.

Note the exact-form cone. At f/4 the paraxial π/(4N²) would give 0.049087 sr —
1.2 % high — and it diverges past 2π sr for fast systems, which no solid angle
may do.

## Step 4: Sweep the Undersizing, 0 → 10 %

| u [%] | D_eff [m] | f/#_eff | Ω_cone [sr] | Near-field [e⁻] | Signal [e⁻] | SNR [-] | NEDT [mK] | MTF_nyq |
|------:|----------:|--------:|------------:|----------------:|------------:|--------:|----------:|--------:|
| 0 | 0.25000 | 4.0000 | 0.048520 | 106,631 | 2,994,945 | 1699.32 | 17.00 | 0.3017 |
| 2 | 0.24500 | 4.0816 | 0.046637 | 102,491 | 2,876,247 | 1665.28 | 17.35 | 0.2933 |
| 4 | 0.24000 | 4.1667 | 0.044765 | 98,368 | 2,758,802 | 1631.25 | 17.71 | 0.2849 |
| 6 | 0.23500 | 4.2553 | 0.042930 | 94,346 | 2,646,334 | 1597.16 | 18.09 | 0.2835 |
| 8 | 0.23000 | 4.3478 | 0.041140 | 90,413 | 2,534,922 | 1563.11 | 18.48 | 0.2752 |
| 10 | 0.22500 | 4.4444 | 0.039387 | 86,561 | 2,425,906 | 1529.06 | 18.89 | 0.2668 |

Over 0 → 10 % undersizing:

- A_collect −19.0 % (exactly (1 − 0.1)² − 1)
- Ω_cone −18.8 %
- Near-field −18.8 % (it tracks Ω_cone, as it must)
- Signal −19.0 %
- SNR −10.0 % (shot-limited: √signal)
- MTF at Nyquist −11.6 %

**Signal and near-field fall together**, because both come from the same
effective pupil. That is the physics the old leakage knob concealed.

## Step 5: Requirements

The requirement is a shuttered background below 40,000 e⁻. The model predicts
106,631 e⁻ at u = 0 and 86,561 e⁻ at u = 10 % — a FAIL either way, and
undersizing moves it only as fast as Ω_cone falls (−18.8 % across the sweep).

**Undersizing is not a background-control knob.** The levers that actually scale
the near-field are the optics temperature and the coating emissivity.

## Step 6: What the Lab Measurements Now Mean

Near-field scales linearly with the emitting emissivity Σ(1 − R) at fixed Ω_cone
and T_optics, so each measurement inverts to an implied per-mirror reflectance:

| Test Point | Position [mm] | Measured [e⁻] | Model [e⁻] | Δ [%] | implied ε [-] | implied R [-] | Status |
|------------|--------------:|--------------:|-----------:|------:|--------------:|--------------:|--------|
| CS-NOM | 0.0 | 35,500 | 106,631 | −66.7 | 0.0200 | 0.9933 | PASS |
| CS-OFF-05 | 0.5 | 39,500 | 106,631 | −63.0 | 0.0222 | 0.9926 | PASS |
| CS-OFF-10 | 1.0 | 44,000 | 106,631 | −58.7 | 0.0248 | 0.9917 | FAIL |
| CS-OFF-15 | 1.5 | 47,750 | 106,631 | −55.2 | 0.0269 | 0.9910 | FAIL |
| CS-OFF-20 | 2.0 | 52,000 | 106,631 | −51.2 | 0.0293 | 0.9902 | FAIL |
| CS-OFF-25 | 2.5 | 55,750 | 106,631 | −47.7 | 0.0314 | 0.9895 | FAIL |

Two readings:

1. **Every measurement sits below the model.** The assumed R = 0.98 [-] per
   mirror is pessimistic for this camera; the lab data bracket the real train at
   R ≈ 0.990–0.993 [-], or equivalently a barrel colder than the assumed 20 °C.
   That is a testable statement about coatings and thermal design — where the old
   model offered only a fitted leakage fraction that hid the same disagreement.

2. **The 57 % spread across cold-stop positions is what the new rules cannot
   explain.** With a cold stop present, position should not move the background
   at all. A monotone rise with offset therefore says warm structure is entering
   the acceptance cone as the stop shifts — i.e. the stop stops being the
   aperture stop at those offsets. That is outside this model's scope (an
   accepted Gap 128 limitation) and is itself the finding Karen should carry to
   the mechanical team.

## Key Takeaways

1. **A cold stop cannot attenuate in-cone emission.** The old
   `optics.nearfield_fraction` knob implied it could. It is deleted; setting it
   now raises an actionable error naming Gap 128.

2. **The cold stop is the aperture stop.** Its one real degree of freedom is
   size: `optics.cold_stop_undersize_frac` [-]. That number moves A_collect,
   f/#, the PSF, the MTF, and Ω_cone together, because they all come from one
   pupil (Rule 4).

3. **Undersizing costs about 1 % of SNR per 1 % of pupil diameter** for a
   shot-limited camera, plus about 1.2 % of MTF at Nyquist. Ten percent of
   tolerancing margin costs 10 % of SNR and 12 % of resolution.

4. **Emissivity is derived, never free.** ε = 1 − R per mirror; an AR-coated
   window with only T known emits nothing (Gap 127). Reading one end-to-end τ as
   absorption over-states warm-optics emission several-fold.

5. **The measurement–model disagreement is now physically interpretable.** It
   bounds the coating reflectance and the barrel temperature instead of being
   absorbed by a fitted leakage number.

## Figures

- `outputs/fig1_signal_and_nearfield_vs_undersize.png` — signal and near-field
  vs *u*, on one plot: the load-bearing display, because they fall together.
- `outputs/fig2_snr_and_mtf_vs_undersize.png` — SNR and MTF at Nyquist vs *u*:
  the cost of tolerancing margin.
- `outputs/fig3_shuttered_background_vs_undersize.png` — shuttered background vs
  *u*, with the 40,000 e⁻ requirement and Karen's six measurements.
- `outputs/fig4_pupil_vs_undersize.png` — A_collect [cm²] and Ω_cone [msr] vs
  *u*: one effective pupil, two consequences.

## Gaps Identified

- ~~**Gap 1 (Inverse solver)**~~: **CLOSED** — `Sensor.solve_for` (registry
  Gap 10). The parameter it used to invert onto no longer exists, so this
  scenario no longer exercises it; scenario 7.2 and the solver's own tests do.

- **Gap 2 (Thermal background breakdown)**: OPEN, and now partly served —
  `stage_outputs["optics"]["nearfield_per_element"]` gives the per-element
  contribution. What remains missing is a GUI surface for it.

- ~~**Gap 3 (NEDT)**~~: **CLOSED**. `result.metrics["nedt_K"]`, in the baseline
  and every sweep row.

- ~~**Gap 4 (Nearfield = 0 in scalar mode)**~~: **CLOSED** — the train is a
  defined element list with Kirchhoff-derived ε (registry Gap 37, element form
  under Gap 127, realistic coating split under Gap 128).

- **Gap 6 (lab_test sub-case unreachable from the config surface)**: OPEN —
  registry Gap 42. This TVAC scenario must masquerade as the `space` sub-case
  with a placeholder `geometry.sensor_altitude_m`.

- **New (Gap 128 accepted limitation)**: a cold stop that has shifted far enough
  to stop being the aperture stop — so that warm structure enters the acceptance
  cone — is outside the model. The scenario names it rather than fitting it.

See `gaps.md` for the full per-gap records.
