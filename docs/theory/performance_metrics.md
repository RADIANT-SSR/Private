# Performance Metrics

*Persona: Lisa (analyst), Sarah (systems engineer)*

The metric layer: how RADIANT turns the signal/noise/spatial chain state into SNR, NEDT,
NIIRS, detection range, and their relatives. Numeric anchors are blind-derived values
from the 2026-07 assurance audit (`track_a3_noise_metrics_derivation.md`). Metric-layer
functions may return result-typed failures with a structured `failure_reason` instead of
raising (CLAUDE.md Rule 17 carve-out / ADR-B) — silent NaN propagation remains forbidden.

**Symbols:** $S$ target signal [e-]; $S_{bg}$ background signal [e-];
$\sigma_{tot}$ total noise [e- RMS] (see `theory/noise_model.md`); $t_{int}$ [s];
$p$ pixel pitch [m]; GSD [m].

---

## 1. SNR family

**Equations.**

$$\mathrm{SNR} = \frac{S}{\sigma_{tot}},\qquad \mathrm{CSNR} = \frac{S - S_{bg}}{\sigma_{tot}},\qquad \mathrm{SCNR} = \frac{S - S_{bg}}{\sigma_{tot} \oplus \sigma_{clutter}}$$

($\oplus$ = RSS). **The denominator always contains the background and dark shot noise**:
subtracting the background estimate in the numerator does not remove its Poisson
fluctuations. In the thermal IR, where $\Delta S \ll S_{bg}$, using
$\sqrt{S - S_{bg}}$ in the denominator overstates contrast SNR by large factors (1.9× at
the audit anchor).

**Numeric anchor.** $S = 10000$, $S_{bg} = 5000$, $N_{dark} = 1000$ e-,
$\sigma_{read} = 50$ e-, PRNU 0.1%: $\sigma_{tot} = 136.38$ e-, SNR $= 73.32$,
CSNR $= 36.66$.

**In RADIANT.** `performance/snr.py::compute_snr`,
`contrast_snr.py::compute_contrast_snr`, `scnr.py::compute_scnr` (clutter via
`detector.clutter_sigma`) · anchored by `performance/tests/test_snr.py`, `test_scnr.py`.
**References.** [Holst 2008].

---

## 2. NEDT

**Equation.**

$$\mathrm{NEDT} = \frac{\sigma_{tot}}{dS/dT}\quad[\mathrm{K}],$$

with the thermal responsivity band-integrated in the photon domain:

$$\frac{dS}{dT} = t_{int}\,G \int \frac{\lambda_m}{hc}\,QE(\lambda)\,\tau(\lambda)\,\frac{\partial L_\lambda}{\partial T}\,d\lambda\quad[\mathrm{e^-/K}],$$

$\partial L_\lambda/\partial T$ the analytic Planck derivative
(`theory/radiometric_chain.md`), $G$ the étendue. RADIANT computes $dS/dT$ in
`SpectralIntegrationStage` (`ds_dt_e_per_K` stage output) and divides in the metric layer;
a fallback `compute_nedt_from_snr` uses the SNR route when the derivative output is
absent.

**Pitfalls.** Paraxial étendue $A_d\pi/(4F_\#^2)$ vs exact $A_d\pi/(4F_\#^2+1)$ — 6.25%
at $f/2$, 25% at $f/1$ (understates NEDT); finite-difference $\Delta T = 1$ K instead of
the analytic derivative; energy-domain radiance without the $\lambda_m/hc$ photon factor;
quoting mK NEDT that implies an impossible well fill (the audit's LWIR example: an $f/2$,
1 ms configuration implies 800× a 100 ke- well — always sanity-check
$S_{bg}$ against `total_well_e`).

**Numeric anchors.** $dS/dT = 5000$ e-/K, $\sigma = 60$ e- → NEDT $= 12.0$ mK;
$\int_8^{12}(\partial L_\lambda/\partial T)\,d\lambda = 0.6297$ W/m²/sr/K at 300 K.

**In RADIANT.** `performance/nedt.py::compute_nedt` (+ `compute_nedt_from_snr`),
`spectral_integration/stage.py` (`ds_dt_e_per_K`) · anchored by
`performance/tests/test_nedt.py`, `tests/integration/test_nedt_exact.py`.
**References.** [Holst 2008], [Dereniak & Boreman 1996].

---

## 3. NEI, NEP, and D*

**Equations.** Noise-equivalent irradiance at the aperture (photon domain):

$$\mathrm{NEI} = \frac{\sigma_{tot}}{\eta_{sys}\,EE\,A_{ap}\,t_{int}}\quad[\mathrm{ph/s/cm^2\ or\ /m^2}],$$

power form via $hc/\lambda_m$. Specific detectivity:

$$D^* = \frac{\sqrt{A_d\,\Delta f}}{\mathrm{NEP}}\quad[\mathrm{cm\sqrt{Hz}/W}],\qquad \Delta f = \frac{1}{2\,t_{int}},$$

with $A_d$ in **cm²** (Jones convention). BLIP-limit PV detectivity
$(\lambda_m/hc)\sqrt{\eta/(2Q_b)}$; photoconductors are $\sqrt2$ lower
(generation *and* recombination noise).

**Pitfalls.** $\Delta f = 1/t_{int}$ vs $1/(2t_{int})$ — a $\sqrt2$ error of exactly the
PV/PC magnitude, easily conflated; $A_d$ in m² (inflates $D^*$ ×100); omitting the
ensquared-energy factor in NEI (optimistic by $1/EE$); photon/energy domain mixing (the
$\lambda_m/hc$ lost or doubled — the NEP↔electrons converter carries an absolute anchor
for exactly this).

**Numeric anchors.** NEP $= 10^{-14}$ W, $A_d = (20\ \mathrm{µm})^2$,
$\Delta f = 1000$ Hz → $D^* = 6.3246\times10^{12}$ cm√Hz/W; NEP anchor
$\sigma = 100$ e-, $\eta = 0.7$, $\lambda = 10$ µm, $t = 10$ ms →
$2.8378\times10^{-16}$ W.

**In RADIANT.** `performance/noise_equivalent_irradiance.py::noise_equivalent_irradiance_ph_s_cm2`,
`detectivity.py::dstar_from_nep`/`nep_from_dstar`, `nep_electrons.py`, `nep_netd.py` ·
anchored by `performance/tests/test_detector_figures_of_merit.py`,
`test_noise_spec_converters.py::test_nep_absolute_anchor`.
**References.** [Vincent 1990], [Dereniak & Boreman 1996].

---

## 4. NIIRS via GIQE-5 (and the IIRS placeholder)

**Equation.**

$$\mathrm{NIIRS} = c_0 + c_1\log_{10}\mathrm{GSD_{in}} + c_2\log_{10}\mathrm{RER} + c_3\log_{10}\mathrm{SNR} + c_4 H + c_5 G$$

with the literature coefficients $(9.57,\ -3.32,\ 3.32,\ 1.559,\ -0.334,\ -0.01)$
pinned exactly by test; GSD in **inches** (geometric mean of the §4-geometry directions),
RER the geometric mean from the PSF path, $H$ edge overshoot, $G$ noise gain.

**Fit-envelope gating (CU-166):** GIQE-5 was fit over GSD 1.18–31.5 in, RER 0.2–0.95,
SNR 2–130. Outside the envelope RADIANT refuses by default (result-typed failure with
`failure_reason`), computes only when `performance.niirs.allow_extrapolated = true`, and
flags `niirs_extrapolated = 1`.

**IIRS status (Gap 100):** the MWIR/LWIR interpretability metric currently **reuses
GIQE-5 verbatim** — same formula, envelope, and coefficients. Treat IR "IIRS" outputs as
GIQE-5-on-IR until a real IIRS lands.

**Numeric anchor.** GSD = 1 m, RER = 0.9, SNR = 50 → NIIRS $= 6.4268$ (pure-literal test
value).

**In RADIANT.** `performance/giqe.py::compute_giqe5`, `iirs.py::compute_iirs`,
`giqe_sensitivity.py` (term-by-term sensitivities) · anchored by
`performance/tests/test_giqe.py::test_coefficients_pinned_to_literature`,
`test_hand_calculation_numeric_literal`, `test_giqe_sensitivity.py` (FD cross-check).
**References.** [Harrington 2015].

---

## 5. Johnson criteria and minimum resolvable

**Equations.** Cycles resolved across a target's critical dimension $d_c$ at range $R_s$:

$$N_{cyc} = \frac{d_c}{2\,\mathrm{IFOV}\,R_s}$$

(the factor 2 converting pixels to cycles), compared against the Johnson thresholds
(detect ≈ 1, recognize ≈ 4, identify ≈ 8 cycles, 50% probability). `johnson_range_m`
inverts for range at a given task. Minimum-resolvable temperature/contrast couple the MTF
budget to NEDT/SNR thresholds (`minimum_resolvable.py`).

**Pitfalls.** Cycles vs pixels (factor 2); using nadir IFOV footprint at slant geometry;
50%-probability thresholds quoted as certainties.

**In RADIANT.** `performance/johnson_criteria.py::resolved_cycles`, `johnson_range_m`;
`minimum_resolvable.py::minimum_resolvable_temperature_K` /
`minimum_resolvable_contrast` · anchored by
`performance/tests/test_johnson_criteria.py`, `test_minimum_resolvable.py`.
**References.** [Johnson 1958], [Holst 2008].

---

## 6. Detection range

**Equation.** For a point source with atmospheric extinction, the SNR-vs-range equation
mixes $1/R_s^2$ geometric falloff with Beer–Lambert transmission
$e^{-\alpha R_s}$; RADIANT solves

$$\mathrm{SNR}(R_s) = \mathrm{SNR}_{threshold}$$

by bisection (constant extinction coefficient $\alpha$, point-source regime only;
threshold parameter default 5.0). A generic solver variant handles the no-atmosphere
case.

**Pitfalls.** Applying extended-scene SNR to the point-source range equation; forgetting
that EE_box and jitter enter through the signal chain, not as post-hoc factors; α from a
band-average τ over a very different path length.

**In RADIANT.** `performance/detection_beer_lambert.py::detection_range_beer_lambert`,
`detection_generic.py`, `detection.py` (dispatch) · anchored by
`performance/tests/test_detection.py`, `tests/integration/test_detection_range_chain.py`.
**References.** [Holst 2008].

---

## 7. Saturation, dynamic range, BLIP

**Equations.** Well margin $20\log_{10}(\mathrm{FWC}/S_{tot})$ dB and ADC margin
$20\log_{10}(DN_{max}/S_{DN})$ dB; dynamic range

$$\mathrm{DR} = 20\log_{10}\!\frac{\mathrm{FWC}}{\sigma_{floor}}\ \mathrm{dB}$$

with $\sigma_{floor}$ the **dark-scene** floor (read + dark shot + ADC), not the
shot-inflated full-well noise. BLIP: background shot exceeds all other noise RSS'd;
$f_{BLIP} = \sigma_{bg,shot}/\sigma_{tot}$ (→1 fully BLIP; threshold $1/\sqrt2$);
`blip_rate_e_per_s` reports the photon rate scale.

**Pitfalls.** $10\log$ vs $20\log$ (halves the dB); ADC full scale vs true full well
(take the min); counting target shot as "background" in the BLIP test; quoting BLIP at
one $t_{int}$ as if general.

**Numeric anchors.** 100 ke-/50 e- → 66.02 dB; the audit's marginal-BLIP case:
$\sigma_{bg} = 70.7$ vs other-RSS 60.0 e-, $f_{BLIP} = 0.762$.

**In RADIANT.** `performance/well_margin.py`, `adc_margin.py`,
`dynamic_range.py::compute_dynamic_range`, `blip_rate.py::blip_rate_e_per_s`,
`saturation_metrics.py`, `dark_crossover_rate.py` · anchored by
`performance/tests/test_saturation_metrics.py`, `test_detector_figures_of_merit.py`.
**References.** [Dereniak & Boreman 1996].

---

## 8. Radiometric inversions and sensitivity relatives

**NEΔL / NEΔρ** — noise-equivalent radiance/reflectance differences, currently computed
as `radiance/SNR` and `reflectance/SNR` helpers (`nedl.py`, `nedr.py`; **not wired into
`PerformanceStage`** — Gap 78, disclosed in `RADIANT_Metrics.md` §6). **Temperature
retrieval** — band-radiance inversion with emissivity and temperature Jacobians
(`temperature_retrieval.py::retrieve_temperature_K`; the forward
`band_planck_radiance` is anchored to the audit's 38.5 W/m²/sr at 300 K, 8–12 µm).

**In RADIANT.** modules above · anchored by
`performance/tests/test_temperature_retrieval.py` (absolute anchor added by the audit
remediation), `test_noise_spec_converters.py`.

---

## Metric selection and the registry

Which metrics compute is governed by the five Gap-96 group flags
(`performance/_schema.py`, all default true) resolved through
`performance/metric_selection.py` with dependency closure; every computed key is
registered in `performance/registry.py` and reconciled one-for-one against
`RADIANT_Metrics.md` §6 by `tests/integration/test_metric_registry_reconciliation.py`.
When the whole Spatial-MTF group is deselected and nothing needs a spatial input, the
spatial path — including the Rule-4 consistency check — is skipped entirely
(owner-ratified, 2026-07-18).
