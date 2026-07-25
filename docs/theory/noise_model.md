# Noise Model

*Persona: Mike (detector engineer), Dr. Chen (researcher)*

Complete noise taxonomy, equations, scaling rules, and acquisition timing as implemented
in RADIANT. All noise in electrons RMS (Rule 2 canonical unit). Numeric anchors are
blind-derived values from the 2026-07 assurance audit
(`docs/reports/assurance_audit_2026-07/track_a3_noise_metrics_derivation.md`).

---

## Overview — RSS composition

RADIANT models 16 independent noise sources, each in e- RMS. With statistical
independence, variances add:

$$\sigma_{\text{total}} = \sqrt{\sum_{i=1}^{16} \sigma_i^2}$$

**The load-bearing assumption is independence** — each mechanism arises in a physically
distinct process, so cross-covariances vanish. It is deliberately violated by
fixed-pattern terms across frames of the same pixel (they are a static spatial pattern:
they belong in a single-frame spatial budget but do not average down over frames — see
TDI/co-add scaling below). All terms are input-referred to electrons at the sense node
before combining; mixing DN-domain and e--domain terms in one RSS is the classic error.

Terms are classed **temporal** (frame-independent, average down as $\sqrt{N}$) or
**spatial** (fixed-pattern).

**Numeric anchor.** $N_{target}=10000$, $N_{bg}=5000$, $N_{dark}=1000$ e-,
$\sigma_{read}=50$ e-, PRNU 0.1% ($\sigma_{PRNU}=10$ e-):
$\sigma_{tot} = \sqrt{16000 + 2500 + 100} = 136.381817$ e- RMS.

**In RADIANT.** `detector/noise/budget.py` (assembly), `core/noise_budget.py`
(NoiseTerm/temporal-spatial classing) · anchored by `detector/tests/test_noise.py` and
the audit-pinned RSS case therein. **References.** [Dereniak & Boreman 1996],
[Holst 2008].

---

## Noise Taxonomy

### Photon shot noise (4 terms)

Poisson statistics of photon arrival: for $N_e$ photoelectrons,
$\sigma = \sqrt{N_e}$. QE < 1 preserves Poisson statistics (binomial thinning), so the
square root is taken of **electrons**, never photons or DN
($\sigma_{DN} = \sqrt{S_{DN}/g}$, not $\sqrt{S_{DN}}$).

- Signal shot: $\sigma = \sqrt{S}$ (target electrons)
- Background shot: $\sigma = \sqrt{S_{bg}}$
- Nearfield shot: $\sqrt{S_{nf}}$ (warm-optics self-emission)
- Straylight shot: $\sqrt{S_{stray}}$

**Pitfalls.** Adding σ's instead of variances; dark-frame subtraction removes the dark
*mean*, never its shot noise (single-shot subtraction doubles the dark shot variance).

**In RADIANT.** `detector/noise/photon.py`, `detector/shot_noise.py` · anchored by
`detector/tests/test_shot_noise.py`, `test_noise.py`.

### Detector-material noise (4 terms)

**Dark shot:** $\sigma = \sqrt{J_{dark}\,t_{int}}$ with $J_{dark}$ in e-/s.
Temperature scaling is Arrhenius:

$$J(T) = J_{\text{ref}}\exp\!\left[\frac{E_a}{k_B}\left(\frac{1}{T_{\text{ref}}} - \frac{1}{T}\right)\right]$$

(`detector.dark_activation_energy_eV`, `dark_reference_temperature_K`). Physics note:
diffusion-limited material has $E_a \approx E_g$, generation–recombination-limited
$E_a \approx E_g/2$ — conflating them mis-predicts the cooling benefit by squaring the
true ratio (audit anchor: $E_g = 0.1$ eV diffusion, 77→84 K: dark current ×4.56).

**G-R noise:** $\sigma_{gr} = \sqrt{2 g_{gr} J_{dark} t_{int}}$ ($g_{gr}\approx0$ PV,
~1 PC — the same generation-AND-recombination doubling that costs photoconductors
$\sqrt2$ in D*).

**Johnson noise** (from $R_0A$) and **1/f noise** (flicker coefficient over a frequency
band) per the forms in `detector/noise/detector_material.py`.

**In RADIANT.** `detector/dark_current.py`, `detector/noise/detector_material.py` ·
anchored by `detector/tests/test_dark_current.py`, `test_noise.py`.
**References.** [Vincent 1990], [Dereniak & Boreman 1996].

### ROIC noise (3 terms)

**Read noise:** fixed floor `readout.read_noise_e_rms`; includes CDS benefit when
`read_noise_is_post_cds = True` (default).

**kTC reset noise:** $\sigma_{kTC} = \sqrt{k_B T C_{node}}/q$ — suppressed to zero when
CDS is enabled (`readout.cds_enabled = 1`, default).

**ADC quantization:**

$$\sigma_{ADC} = \frac{g}{\sqrt{12}},\qquad g = \frac{N_{fullwell}}{2^n}\ \text{[e-/DN]}.$$

Valid when input noise ≳ 1 LSB (dithered); the error is uniform on ±LSB/2 and its
variance is LSB²/12.

**Pitfalls.** Dividing by 12 instead of $\sqrt{12}$ (3.46× understatement); counting
quantization twice when a vendor's measured "read noise in e-" already includes the ADC;
leaving σ_ADC in DN when the RSS is in e-.

**Numeric anchor.** 14-bit, 100 ke- full well: $g = 6.10352$ e-/DN,
$\sigma_{ADC} = 1.76193$ e- RMS.

**In RADIANT.** `readout/read_noise.py`, `detector/noise/roic.py` (kTC),
`readout/adc.py::AnalogToDigital.quantization_noise_e` · anchored by
`readout/tests/test_read_noise.py`, `test_adc.py`.

### Spatial (fixed-pattern) noise (3 terms)

**PRNU** — multiplicative gain dispersion, **linear in signal** (not $\sqrt{N}$):
$\sigma_{PRNU} = k\,S$ with $k$ the residual non-uniformity after NUC. Shot/PRNU
crossover at $N = 1/k^2$ (0.1% → $10^6$ e-): above it, more integration cannot improve
single-frame spatial SNR — only better flat-fielding can.

**DSNU** — dark-signal non-uniformity, a fixed spatial floor (`dsnu_e_rms`).

**Clutter** — scene-induced spatial variance, $\sigma_c \cdot S_{bg}$
(`detector.clutter_sigma`).

**Pitfalls.** Applying $\sqrt{\cdot}$ to PRNU; claiming temporal co-adding reduces FPN
(perfectly frame-correlated for a staring pixel); applying $k$ to signal+dark (dark
dispersion is DSNU's job).

**In RADIANT.** `detector/noise/fixed_pattern.py` · anchored by
`detector/tests/test_noise.py`.

### Other (2 terms)

**Persistence** (residual charge from prior exposure, exponential decay model —
`detector/persistence_sequence.py`) and **ROIC glow shot** ($\sqrt{R_{glow} t_{int}}$)
per `detector/noise/other.py`.

---

## Acquisition scaling

### TDI and co-adding

Summing $N$ stages/frames: signal ×$N$; uncorrelated temporal noise ×$\sqrt{N}$; SNR
×$\sqrt{N}$. The architecture determines the read-noise and FPN behavior:

| Noise category | Charge-domain (analog) TDI | Digital co-add |
|---|---|---|
| Signal | × $N$ | × $N$ |
| Shot-like temporal | × $\sqrt{N}$ | × $\sqrt{N}$ |
| Read / kTC / quantization | × 1 (one read) | × $\sqrt{N}$ (read per frame) |
| PRNU/DSNU across **distinct** pixels (cross-scan TDI) | effective $k/\sqrt{N}$ | — |
| FPN, **same** pixels (staring co-add) | — | × $N$ (coherent; no SNR gain) |
| Clutter (scene-correlated) | × $N$ | × $N$ |

**Well-fill cap:** charge-domain TDI accumulates into one well —
$N(S_1 + N_{d,1}) \le N_{fullwell}$ bounds the useful $N$
(audit anchor: 10 ke- per stage against a 100 ke- well caps $N$ at 10, SNR gain at
$\sqrt{10}$).

**In RADIANT.** `readout/tdi_scaling.py`, `readout/coadds.py`
(`readout.n_tdi`/`tdi_mode`, `n_coadds`/`coadd_mode`), well check in
`readout/saturation.py` · anchored by `readout/tests/test_tdi.py`, `test_coadds.py`,
`test_saturation.py`.

### Binning

On-chip binning merges charge before read (read noise once per binned super-pixel);
off-chip binning averages after read (read noise per contributing pixel, ×$\sqrt{n}$ in
the sum). Signal scales with the binned area in both.

**In RADIANT.** `readout/binning_onchip.py`, `readout/binning_offchip.py` · anchored by
`readout/tests/test_binning.py`.

### Frame timing (Conventions §4)

Frame period is stored independently of integration time:

$$f_{frame} = \frac{1}{T_{frame}},\qquad \text{duty} = \frac{t_{int}}{T_{frame}} \le 1.$$

Unset `readout.frame_period_s` (0.0) defaults to $t_{int}$ (duty 1.0, continuous
readout); duty > 1 is rejected with an actionable error. Outputs
`frame_period_s`/`frame_rate_hz`/`duty_cycle`/`frame_period_defaulted` in
`stage_outputs["readout"]`.

**In RADIANT.** `readout/frame_timing.py::compute_frame_timing` · anchored by
`readout/tests/test_frame_timing.py`.

---

## Noise regime selection

`detector.noise_regime` controls the budget composition: `"imaging"` (temporal terms
only, default) vs `"detection"` (adds PRNU, DSNU, clutter). The regime distinction exists
because single-frame detection against a scene sees the spatial pattern as noise, while a
calibrated imaging chain removes the static component.

---

## When each term dominates

| Regime | Dominant noise | Typical scenario |
|--------|---------------|-----------------|
| BLIP (background-limited) | Background shot | IR, long $t_{int}$, low read noise — see `theory/performance_metrics.md` for the BLIP criterion and $f_{BLIP}$ |
| Read-noise limited | Read | Short $t_{int}$, low flux |
| Dark-current limited | Dark shot | Long $t_{int}$, warm detector |
| FPN-limited | PRNU/clutter | $S > 1/k^2$, no scan averaging |

A system can exit BLIP *from above* as flux grows: $\sigma_{PRNU} = kN_{bg}$ outpaces
$\sqrt{N_{bg}}$ past the crossover.

---

## Parameter cross-reference

See [Parameter Reference](../guides/parameter_reference.md) for all detector/readout
parameters with types, defaults, and bounds.
