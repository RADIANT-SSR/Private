# Calibration Error Model

*Persona: Mike (detector engineer), Karen (test engineer)*

What a radiometric calibration leaves behind. A non-uniformity correction removes the
pixel-to-pixel gain and offset dispersion exactly at the signal levels where it was
derived; everywhere else a residual survives, and that residual — not the temporal noise
floor — frequently sets the achieved NEDT of a cooled infrared system. This chapter states
the residual model, the drift terms, the accuracy (bias) budget, and how each enters the
noise composition of Chapter 6.

Two facts drive the whole design. **Correlated errors do not average down:** TDI stages,
co-added frames, and binned pixels reduce temporal noise as $\sqrt{N}$, but a calibration
residual is the same error in every frame, so it is exempt. **Precision is not accuracy:**
a cal-source temperature uncertainty moves the entire array's radiometric scale and must
never be root-sum-squared into $\sigma_{tot}$, where it would masquerade as noise that
integration could beat down.

---

## Overview — a terms-only stage after readout

The calibration stage sits between readout and the metric layer, and it transforms
nothing: it collapses no spectrum, moves no frame, and — this matters — contributes no
MTF term. Residual fixed-pattern noise is spatial *noise*, not a spatial *degradation*: it
has no point spread function kernel, so neither spatial path of Chapter 5 gains a
contributor and the dual-path consistency check is untouched.

What the stage contributes is three kinds of term:

- **Residual noise terms** [e- RMS], all classed spatial and all calibration-correlated:
  post-NUC residual, cal-source non-uniformity, gain drift, offset drift, and — on the
  internal-shutter cal path only — narcissus fixed-pattern noise.
- **Bias terms** [dimensionless fractions of radiance], the accuracy budget: cal-source
  temperature and emissivity, spectral calibration, internal-cal offset, and absolute gain.
- **Published totals**: the calibration RSS $\sigma_{cal}$, the post-calibration total
  $\sigma_{tot}$, the bias total, and the calibration-limited NEDT.

**The ordering is the physics.** Readout applies the $\sqrt{N}$ scaling first; calibration
appends afterwards. No term needs to be tagged "do not average me" for the exemption to
hold — the chain position enforces it. Equivalently: the residual's size *relative to the
signal* is invariant in $N$, because both the residual and the full-scale reference it is
computed against live in the same summed domain.

**The type separation is the guarantee.** A noise term and a bias term are different
types. SNR and NEDT read noise terms only; the radiometric-accuracy metric reads bias terms
only. Nothing in the model can quietly RSS one into the other.

**Noise-regime interplay.** The imaging noise regime excludes the raw PRNU, DSNU, and
clutter terms on the grounds that they are "calibrated out". The calibration residuals are
precisely what survives that calibration, so they enter the total in *both* the imaging and
the detection regimes. With an active scheme the detector's PRNU and DSNU are re-read as
**pre-correction** dispersions feeding the residual model rather than as noise terms of
their own, so nothing is counted twice.

**In RADIANT.** `calibration/stage.py`, with the residual and bias models in the sibling
modules named per section below. **References.** [Schulz & Caldwell 1995], [Holst 2008].

---

## 1. Cal points — where the correction is anchored

A correction scheme is defined by the signal levels at which it is exact. RADIANT supports
one-, two-, and three-point schemes, and two ways of declaring the points.

### 1.1 Temperature-declared points

The physical form: the cal source is a blackbody at a stated temperature. Because the stage
runs after the single spectral collapse, only scalars are available, so the mapping from
temperature to signal is a band photon-radiance ratio anchored at the scene:

$$S(T_{cal}) = S_{scene}\,\frac{B_q(T_{cal})}{B_q(T_{scene})},\qquad B_q(T) = \int_{\lambda_1}^{\lambda_2} \frac{B(\lambda, T)}{E_{ph}(\lambda)}\,d\lambda$$

with $B_q$ in photon/s/m²/sr and $E_{ph} = hc/\lambda_m$ [J]. Photon weighting, not energy
weighting, is what the band integral uses, because the collected signal counts photons.
Cal-point *fluxes* are never independent inputs in this mode — declaring both a cal
temperature and its flux would over-specify the source.

**Assumption.** The spectral response $\mathrm{QE}(\lambda)\tau(\lambda)$ varies slowly
enough across the band that a flat-weighted photon-radiance ratio stands in for the
response-weighted signal ratio. Only the *ratio* enters, and numerator and denominator are
anchored at nearby temperatures, so the first-order response slope largely cancels; the
approximation degrades for a strongly sloped response curve.

**Numeric anchor.** MWIR band 3.0–5.0 µm, scene at 300.0 K: $S(280\ \mathrm{K}) =
0.46475\,S_{scene}$ and $S(320\ \mathrm{K}) = 1.96525\,S_{scene}$. For a scene signal of
$5.000 \times 10^4$ e- this places the cal points at $S_1 = 2.3238 \times 10^4$ e- and
$S_2 = 9.8262 \times 10^4$ e-.

**In RADIANT.** `calibration/cal_points.py::cal_point_signal_e`.

### 1.2 Flux-declared points

The laboratory form: an integrating sphere or flat-field source produces a known level
relative to the scene, with no thermal anchor at all. The cal points are then declared
directly as fractions of the scene signal,

$$S_i = f_i\,S_{scene},\qquad f_i \ \text{dimensionless},$$

with $f_1 < f_2 < f_3$ required. In this mode every temperature-anchored input — the cal
temperatures, the source temperature uncertainty, the source non-uniformity in K, the
band-center uncertainty, and the source emissivity uncertainty — is **rejected** as
over-specification rather than silently ignored. A set parameter that does nothing is
exactly the failure class the model exists to prevent. Drift, the direct gain-uncertainty
bias, and the internal-shutter path carry no temperature anchor and behave identically in
both modes.

### 1.3 When the thermal anchor does not describe the scene

The temperature mapping anchors at the declared scene temperature. On a reflective scene
that temperature describes none of the collected signal: a visible/near-infrared band
looking at a 300 K surface collects Kirchhoff-reflected sunlight, while a 300 K blackbody
puts essentially nothing into that band. The diagnostic quantity is the in-band share of
the scene-temperature blackbody's photon exitance,

$$\Phi_{band}(T) = \frac{\int_{\lambda_1}^{\lambda_2} B_q(\lambda,T)\,d\lambda}{\int_{0.05\ \mu m}^{1000\ \mu m} B_q(\lambda,T)\,d\lambda}\quad[\text{dimensionless}]$$

**Numeric anchor.** $\Phi_{band}(300\ \mathrm{K})$ is $4.30 \times 10^{-22}$ for a
0.50–0.85 µm band, $3.20 \times 10^{-3}$ for a 3.0–5.0 µm band; a 77 K laboratory scene in
an 8–12 µm band gives $1.99 \times 10^{-5}$. The discrimination spans nearly twenty orders
of magnitude, so the $10^{-9}$ floor the model warns below is a diagnostic bound, not tuned
physics.

Below that floor — or for a target declared purely reflective — the cal points are
deterministic stand-ins: the residual *structure* (the shape of the parabola, the
$\sqrt{N}$ exemption, the plateau between cal points) survives, but the absolute level
rides the stand-in. The run proceeds under a loud advisory rather than silently, and the
correct remedy is to declare the cal points as flux fractions.

### 1.4 The full-scale reference

The nonlinearity coefficient of *Post-NUC residual* below is referenced to full scale, so
the reference $S_{ref}$
must live in the same summed domain as the signal it is compared against: the counting
detector's effective well when that branch ran, otherwise the per-pixel full-well capacity
scaled by the accumulation gain the signal actually received through TDI, binning, and
co-adding. One domain for numerator and denominator is what makes the residual's
signal-relative size invariant in $N$.

---

## 2. Post-NUC residual — the correctability parabola

### 2.1 Two-point correction

Model each pixel's response as linear plus a small quadratic term,
$y = g\,(S + \beta S^2 / S_{ref}) + o$, with the curvature coefficient $\beta$ dispersed
across the array with 1σ magnitude $\sigma_\beta$. A two-point correction solves for each
pixel's gain and offset so that the corrected output is exact at $S_1$ and $S_2$. Carrying
the exact linear-correction algebra through in the small-$\beta$ limit leaves the per-pixel
error

$$\Delta S = \beta\,\frac{(S - S_1)(S - S_2)}{S_{ref}},$$

so the array RMS residual is

$$\sigma_{NUC}(S) = \beta\,\frac{\lvert (S - S_1)(S - S_2)\rvert}{S_{ref}}\quad[\mathrm{e}\text{-}\ \mathrm{RMS}]$$

— a parabola that vanishes at both cal points, peaks between them, and grows
quadratically outside them. The peak sits at the midpoint of the cal span and has the
value $\beta\,(S_2-S_1)^2/(4 S_{ref})$, which is the one number worth memorizing: the
residual is quadratic in the *span*, so halving the separation between cal points quarters
the worst-case residual inside it. Gain and offset dispersion (PRNU and DSNU) are removed
exactly by the correction itself and re-enter only through the drift terms of *Drift
between calibration events*.

**Symbols.** $S$ scene signal [e-]; $S_1, S_2$ cal-point signals [e-]; $\beta$ 1σ
nonlinearity fraction at full scale [dimensionless]; $S_{ref}$ full-scale reference [e-].

**Pitfalls.** Quoting the residual at a cal point (it is zero there by construction, which
is why *Cal-source spatial non-uniformity* exists); referencing $\beta$ to the signal
instead of to full scale, which makes
the residual cubic; taking $S_{ref}$ in the per-pixel domain while $S$ is in the summed
TDI domain, which makes the residual appear to shrink with $N_{TDI}$.

**Numeric anchor.** $\beta = 0.5\%$, $S_1 = 2.000 \times 10^4$ e-,
$S_2 = 8.000 \times 10^4$ e-, $S_{ref} = 1.000 \times 10^5$ e-: at the midpoint
$S = 5.000 \times 10^4$ e- the residual is 45.00 e- RMS, and it is 0.00 e- RMS at either
cal point.

### 2.2 One-point correction

An offset-only correction leaves the gain dispersion intact, acting on the departure from
the single cal point:

$$\sigma_{1pt}(S) = k\,\lvert S - S_1\rvert\quad[\mathrm{e}\text{-}\ \mathrm{RMS}]$$

with $k$ the pre-correction PRNU fraction. The contrast with the two-point correction
above is the point of running
two points at all: the one-point residual is *linear* in the departure and carries the
full PRNU coefficient, so it is typically an order of magnitude larger.

**Numeric anchor.** $k = 0.5\%$, $S_1 = 2.000 \times 10^4$ e-, $S = 5.000 \times 10^4$ e-:
150.0 e- RMS — 3.3× the two-point residual at the same signal in the anchor above.

### 2.3 Three-point correction

With a third point between the extremes, the correction is piecewise: inside each
bracketing segment it is exactly that pair's two-point solve, so the residual is that
segment's own parabola, vanishing at all three cal points and peaking at a quarter of the
corresponding two-point value when the mid point bisects the span. Outside the calibrated
range the nearest segment extrapolates, exactly as the two-point model extrapolates past
its own span. The model stops at three points by design; beyond that a real instrument
uses a response curve, not more anchors.

**Numeric anchor.** Same $\beta$ and $S_{ref}$ as the two-point correction, with a mid
point at
$5.000 \times 10^4$ e-: the residual at $3.500 \times 10^4$ e- (the midpoint of the lower
segment) is 11.25 e- RMS, a quarter of the 45.00 e- RMS two-point peak.

**In RADIANT.** `calibration/nuc_residual.py`.

---

## 3. Cal-source spatial non-uniformity

A real calibration blackbody holds only ±0.01–0.05 K (1σ) across its aperture. At cal time
each pixel therefore views a slightly different source temperature and the correction
imprints that pattern into its own coefficients. With $\delta T$ the pixel's local
departure and $D_j = dS/dT$ evaluated at cal point $j$ [e-/K], the imprinted error at cal
view $j$ is $\delta S_j = \delta T\,D_j$, and propagating it through the correction solve
gives

$$\sigma_{unif}(S) = \Delta T_{unif}\,D_1 \quad \text{(one-point)},\qquad
\sigma_{unif}(S) = \Delta T_{unif}\,\frac{\lvert D_1 (S_2 - S) + D_2 (S - S_1)\rvert}{S_2 - S_1} \quad \text{(two-point)}$$

with the three-point form interpolating piecewise between the bracketing pair's constants.

**The combination is linear, not RSS.** The same plate is viewed at both cal points and a
cavity gradient is temperature-independent in kelvin to first order, so the two imprints
are fully correlated. Treating them as independent and root-sum-squaring the weights would
under-predict the residual inside the cal span.

**Why this term matters out of proportion to its size.** Unlike the nonlinearity parabola,
it does **not** vanish at the cal points: $\sigma_{unif}(S_1) = \Delta T_{unif} D_1$
exactly. It is what retires the comfortable but false picture of a calibration that is
perfect where it was taken. When it dominates, it sets a calibration-limited NEDT floor of
approximately $\Delta T_{unif}$ itself, because the term and the scene derivative it is
divided by are both proportional to $dS/dT$.

**Numeric anchor.** MWIR 3.0–5.0 µm, scene 300.0 K, scene signal $5.000 \times 10^4$ e-,
cal points 280.0 K and 320.0 K: $D_1 = 950.3$ e-/K and $D_2 = 3123.9$ e-/K. With
$\Delta T_{unif} = 0.020$ K the residual at the scene signal is 34.51 e- RMS. Against the
scene's own derivative $dS/dT = 1795$ e-/K that is 0.0192 K — within 4 % of
$\Delta T_{unif}$, as the floor argument predicts.

**In RADIANT.** `calibration/source_uniformity.py`, with the cal-point derivatives from
`calibration/cal_points.py::cal_point_ds_dt_e_per_K`.

---

## 4. Drift between calibration events

Between the cal event and the observation, the corrected gain and offset both walk. The v1
model is time-linear in both, with 1σ rates:

$$\sigma_{gain}(S) = r_g\,t_{cal}\,S \quad [\mathrm{e}\text{-}\ \mathrm{RMS}],\qquad
\sigma_{offset} = r_o\,t_{cal} \quad [\mathrm{e}\text{-}\ \mathrm{RMS}]$$

with $r_g$ in s⁻¹ (entered as %/hour), $r_o$ in e-/s (entered as e-/hour), and $t_{cal}$
the elapsed time since calibration [s]. Gain drift is proportional to signal and therefore
scales with scene brightness; offset drift is signal-independent and dominates at low flux.
Both are spatial and calibration-correlated, so both are exempt from $\sqrt{N}$ averaging.

The practical use of these two terms is cadence: they are what turns "how often must we
calibrate" into a number, since they are the only residual terms that grow without bound
between events.

**Numeric anchor.** $r_g = 0.20\%$/hour and $r_o = 10.0$ e-/hour, 1800 s (30 min) since
the cal event, scene signal $5.000 \times 10^4$ e-: $\sigma_{gain} = 50.00$ e- RMS and
$\sigma_{offset} = 5.000$ e- RMS.

**Deferred.** Drift driven by focal-plane temperature change is not modeled; the v1 rates
are time-linear only.

**In RADIANT.** `calibration/gain_drift.py`, `calibration/offset_drift.py`.

---

## 5. The internal-shutter cal path

A calibration flag inside the optical train sees only itself and the elements *behind* it.
The correction derived from that view absorbs the aft-element emission but never the
emission of the elements in *front* of the flag, which returns in operation as an
uncorrected offset. The split is the photon-weighted in-band fraction of the near-field
focal-plane irradiance contributed by the fore elements:

$$f_{fore} = \frac{\int_{\lambda_1}^{\lambda_2} \sum_{i \in \text{fore}} E_i(\lambda)\,\lambda \; d\lambda}{\int_{\lambda_1}^{\lambda_2} \sum_{i \in \text{all}} E_i(\lambda)\,\lambda \; d\lambda}\quad[\text{dimensionless}]$$

with $E_i(\lambda)$ the per-element near-field irradiance at the focal plane [W/m²/µm].
Each watt of in-band power carries $\lambda/hc$ photons, so $hc$ cancels in the ratio and
only the factor $\lambda$ survives as the weighting. The electron magnitude then rides the
detector's own near-field conversion, $S_{fore} = S_{nf}\,f_{fore}$ [e-]: no radiometry is
re-derived here, which is what keeps this term consistent with the warm-optics treatment
of Chapter 3 and the appendix.

That uncorrected offset produces two distinct effects. Its mean is an **offset bias**,
$S_{fore}/S$ as a fraction of the scene signal, which belongs in the accuracy budget of
*The bias budget* below. The part of it that varies across the array — cold-stop reflections, vignetting of the
warm fore-optics — is **narcissus fixed-pattern noise**, a spatial noise term equal to a
declared fraction of $S_{fore}$.

**Assumption.** The split weights per-element irradiance by photon count rather than by the
QE spectrum. It is exact for flat QE across the band and first-order otherwise, because the
per-element spectra are same-family graybody curves and the QE weighting largely cancels in
the ratio.

**In RADIANT.** `calibration/internal_cal.py`.

---

## 6. Composition — how calibration enters the budget

The five residual terms are mutually independent mechanisms, so they combine in quadrature,
and the calibration RSS combines the same way with the post-readout total:

$$\sigma_{cal} = \sqrt{\sigma_{NUC}^2 + \sigma_{unif}^2 + \sigma_{gain}^2 + \sigma_{offset}^2 + \sigma_{narc}^2},\qquad
\sigma_{tot} = \sigma_{readout} \oplus \sigma_{cal}$$

Every term is appended in the electron domain, input-referred at the sense node, exactly as
Chapter 6 requires of any noise term. All five are classed **spatial**, so a single-frame
spatial budget contains them; none is temporal, so none averages down over frames. The
downstream metrics prefer this post-calibration total wherever it is published: SNR and
contrast SNR use $\sigma_{tot}$ above, and the signal-to-clutter-plus-noise ratio adds
$\sigma_{cal}$ into its spatial RSS.

**Worked example (MWIR staring, two-point cal).** Band 3.0–5.0 µm, scene 300.0 K, scene
signal $5.000 \times 10^4$ e-, full-scale reference $1.000 \times 10^5$ e-, cal points
280.0 K and 320.0 K (so $S_1 = 2.3238 \times 10^4$ e-, $S_2 = 9.8262 \times 10^4$ e-),
nonlinearity $\beta = 0.5\%$, source uniformity $\Delta T_{unif} = 0.020$ K, drift rates
$r_g = 0.20\%$/hour and $r_o = 10.0$ e-/hour at $t_{cal} = 1800$ s, full-aperture cal path:

| Term | Value | Class |
|---|---|---|
| Post-NUC residual | 64.58 e- RMS | spatial, cal-correlated |
| Cal-source uniformity | 34.51 e- RMS | spatial, cal-correlated |
| Gain drift | 50.00 e- RMS | spatial, cal-correlated |
| Offset drift | 5.000 e- RMS | spatial, cal-correlated |
| **Calibration RSS** $\sigma_{cal}$ | **88.81 e- RMS** | — |

Against a temporal (post-readout) total of 300.0 e- RMS this gives
$\sigma_{tot} = 312.9$ e- RMS: the SNR falls from 166.7 to 159.8, a 4.1 % loss that no
amount of integration time recovers.

**Rule-4 non-interaction.** None of these terms has a PSF kernel or an MTF factor. Adding
an "FPN MTF" would double-count a spatial *noise* as a spatial *degradation*.

---

## 7. Calibration-limited NEDT

The reason the stage exists. Dividing the calibration RSS by the scene's own thermal
derivative gives the temperature resolution the calibration alone permits:

$$\mathrm{NEDT}_{cal} = \frac{\sigma_{cal}}{dS/dT}\quad[\mathrm{K}]$$

with $dS/dT$ [e-/K] the band-integrated derivative the chain already computes for NEDT.
This is a *floor*, not a contribution to be traded: because $\sigma_{cal}$ is exempt from
$\sqrt{N}$ averaging, lengthening the integration or adding TDI stages raises the signal
and the residual together, leaving $\mathrm{NEDT}_{cal}$ where it was. A system whose
temporal NEDT has been pushed below its calibration floor has bought nothing.

**Numeric anchor.** Continuing the *Composition* example, $dS/dT = 1795$ e-/K at the
300.0 K scene:

| Quantity | Value |
|---|---|
| Temporal NEDT (readout total alone) | 167.1 mK |
| Calibration-limited NEDT | 49.5 mK |
| Achieved NEDT (post-calibration total) | 174.3 mK |

The calibration floor costs only 7.2 mK on this 167.1 mK system. Halve the temporal noise
and the *same* floor costs 13.5 mK on an 83.6 mK system; halve it again and it costs
23.0 mK on a 41.8 mK system, which now achieves 64.8 mK. The floor does not move, so every
improvement bought with integration time, cooling, or TDI stages is worth progressively
less until the calibration — not the detector — is the thing to fix. That crossover, not
the absolute numbers, is the design content of this chapter.

---

## 8. The bias budget — accuracy, not precision

A calibration-source error does not disperse pixel to pixel; it moves the whole array's
radiometric scale. Such an error is reported as a fractional radiance bias and never
appears in $\sigma_{tot}$.

**Cal-source temperature.** A 1σ uncertainty $\Delta T_{src}$ in the cal source's own
temperature propagates through the photon-weighted band Planck log-derivative at the cal
temperature:

$$b_{src} = \frac{\int_{\lambda_1}^{\lambda_2} (\partial B_q/\partial T)\,d\lambda}{\int_{\lambda_1}^{\lambda_2} B_q\,d\lambda}\,\Delta T_{src}\quad[\text{dimensionless}]$$

**Cal-source emissivity.** A pure scale error, $b_\varepsilon = \Delta\varepsilon /
\varepsilon_{src}$.

**Spectral calibration.** A band-center error $\delta\lambda$ [µm] rigidly shifts the band
the radiometry is computed over. The calibration absorbs the resulting scale error *at its
own source temperature*, because the gain is derived there, so what survives on a scene is
the difference of the band-shift log-derivatives:

$$g(T) = \frac{B_q(\lambda_2, T) - B_q(\lambda_1, T)}{\int_{\lambda_1}^{\lambda_2} B_q(\lambda, T)\,d\lambda}\ [\mu\mathrm{m}^{-1}],
\qquad b_{spec} = \lvert g(T_{scene}) - g(T_{cal})\rvert\;\delta\lambda$$

The expression follows from the Leibniz rule with both band edges moving together. It is
exactly zero when the scene sits at the cal temperature and grows with the scene-versus-cal
separation; short-wave (Wien-side) bands are the sensitive ones. Band-*width* drift is a
distinct and typically smaller mechanism and is not modeled.

**Internal-cal offset.** The uncorrected fore-optics emission of *The internal-shutter cal
path* as a fraction of the
scene signal, $S_{fore}/S$.

**Absolute gain.** A directly declared fractional uncertainty in the radiometric gain.

**Composition.** Independent sources RSS *within* the budget, and the total converts to a
temperature at the scene through the chain's own derivative:

$$b_{tot} = \sqrt{\sum_i b_i^2},\qquad \Delta T = \frac{b_{tot}\,S}{dS/dT}\quad[\mathrm{K}]$$

A scene with no thermal derivative reports the fractional value with a named failure for
the kelvin conversion rather than a silent NaN.

**Numeric anchors.** $\Delta T_{src} = 0.10$ K on a 300.0 K cal source gives
$b_{src} = 3.590 \times 10^{-3}$ (0.359 %) in a 3.0–5.0 µm band and
$1.615 \times 10^{-3}$ (0.161 %) in an 8.0–12.0 µm band — the MWIR band's steeper Planck
slope makes it 2.2× as unforgiving of source-temperature error. An emissivity uncertainty of
0.002 on an $\varepsilon_{src} = 0.99$ cavity gives $b_\varepsilon = 2.020 \times 10^{-3}$.
A band-center uncertainty $\delta\lambda = 0.005$ µm with the scene at 300.0 K and the cal
at 320.0 K in the 3.0–5.0 µm band gives $b_{spec} = 6.121 \times 10^{-4}$ (0.061 %), from
$g(300\ \mathrm{K}) = 1.5459$ µm⁻¹ and $g(320\ \mathrm{K}) = 1.4235$ µm⁻¹.

**Pitfalls.** RSS-ing a bias into the noise total, which makes an accuracy error look like
something $\sqrt{N}$ can fix; quoting the spectral-calibration bias at the cal temperature
(it is zero there); reporting a bias in kelvin without stating the scene temperature it was
converted at.

**In RADIANT.** `calibration/cal_source_bias.py`, `calibration/spectral_cal.py`, with the
budget assembled by `performance/radiometric_accuracy.py`.

---

## 9. Assumptions, validity, and what is deferred

| Assumption | Why it holds | What breaks it |
|---|---|---|
| Quadratic response over the cal span | The departure from linearity of a well-behaved photodiode is smooth and small over the calibrated range | Approach to saturation, where the response is not polynomial and the residual is a lower bound |
| Band photon-radiance ratio for cal points | Only the ratio enters, anchored at nearby temperatures, so the response slope largely cancels | Strongly sloped $\mathrm{QE}\tau$ across the band; a scene whose signal is not thermal at the declared temperature (see *When the thermal anchor does not describe the scene*) |
| Fully correlated source-uniformity imprints | The same plate is viewed at every cal point and a cavity gradient is temperature-independent in K to first order | A source whose gradient changes shape with temperature |
| Time-linear drift | Adequate over a cal interval short compared with the thermal time constants driving it | Long intervals, or drift driven by focal-plane temperature excursions (not modeled) |
| Full PRNU correlation along a TDI column | Takes the correlated limit, an upper bound on the residual floor | Long TDI columns with partially decorrelated pixel gains — the true residual is then lower than modeled |
| Photon-weighted fore-optics split | Exact for flat QE; the per-element spectra are same-family graybody curves | Sharply structured QE across the band |

**Deferred by ruling.** Focal-plane-temperature-driven drift; operations-level calibration
(cal cadence trades, scene-based non-uniformity correction); partial along-column
decorrelation of PRNU under long TDI. Each has a home in this stage when it arrives.

**Boundary conditions.** With the scheme off, the stage emits nothing and results are
bit-identical to a chain without it — enabling the model is a deliberate act, never a
default that quietly moves numbers. Cal points that coincide, are unordered, or are left
unset with a scheme active are rejected with an actionable error rather than
ill-conditioned arithmetic: as $S_2 \to S_1$ the two-point solve degenerates, and the model
refuses instead of dividing by a vanishing span.

---

## Parameter cross-reference

Volume III's Parameter Reference lists the `calibration.*` namespace with types,
defaults, bounds, and entry units. Every cal-related default is the
model-off limit.
