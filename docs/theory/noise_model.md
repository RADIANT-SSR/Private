# Noise Model

*Persona: Mike (detector engineer), Dr. Chen (researcher)*

Complete noise taxonomy, equations, and scaling rules as implemented in
RADIANT.

---

## Overview

RADIANT models 16 independent noise sources, each computed in electrons
RMS. The total noise is the RSS (root sum of squares) combination:

$$\sigma_{\text{total}} = \sqrt{\sum_{i=1}^{16} \sigma_i^2}$$

Noise terms are categorized as **temporal** (independent between frames,
reducible by averaging) or **spatial** (fixed-pattern, not reducible by
temporal averaging).

---

## Noise Taxonomy

### Photon Shot Noise (4 terms)

These arise from Poisson statistics of photon arrival.

**Signal shot noise** --- from target photocurrent:

$$\sigma_{\text{signal\_shot}} = \sqrt{S}$$

where $S$ is signal electrons.

**Background shot noise** --- from scene background:

$$\sigma_{\text{background\_shot}} = \sqrt{S_{\text{bg}}}$$

**Nearfield shot noise** --- from warm optics thermal emission:

$$\sigma_{\text{nearfield\_shot}} = \sqrt{S_{\text{nf}}}$$

**Straylight shot noise** --- from scattered light:

$$\sigma_{\text{straylight\_shot}} = \sqrt{S_{\text{stray}}}$$

*Implementation: `src/radiant/detector/noise.py`*

### Detector Noise (4 terms)

**Dark current shot noise** --- from detector leakage current:

$$\sigma_{\text{dark\_shot}} = \sqrt{J_{\text{dark}} \cdot t_{\text{int}}}$$

where $J_{\text{dark}}$ is dark current rate (e-/s) and $t_{\text{int}}$ is
integration time.

**Generation-recombination (G-R) noise**:

$$\sigma_{\text{gr}} = \sqrt{2 \cdot g_{\text{gr}} \cdot J_{\text{dark}} \cdot t_{\text{int}}}$$

where $g_{\text{gr}}$ is the G-R factor (typically 0 for photovoltaic
detectors, ~1 for photoconductive).

**Johnson noise** --- from detector resistance:

$$\sigma_{\text{johnson}} = \sqrt{\frac{4 k_B T \cdot A_{\text{det}}}{R_0 A} \cdot \frac{t_{\text{int}}}{q^2}}$$

where $R_0 A$ is the detector resistance-area product, $A_{\text{det}}$ is
pixel area, and $q$ is electron charge.

**1/f (flicker) noise**:

$$\sigma_{\text{1/f}} = \sqrt{K \cdot \ln\!\left(\frac{f_{\text{high}}}{f_{\text{low}}}\right)}$$

where $K$ is the flicker noise coefficient and $f_{\text{high}}$,
$f_{\text{low}}$ define the frequency band.

*Implementation: `src/radiant/detector/noise.py`*

### ROIC Noise (3 terms)

**Read noise** --- amplifier noise floor:

$$\sigma_{\text{read}} = \text{read\_noise\_e\_rms}$$

A fixed value in electrons. If `readout.read_noise_is_post_cds = True`
(default), this already includes CDS benefit.

**kTC (reset) noise** --- from capacitor reset:

$$\sigma_{\text{kTC}} = \frac{\sqrt{k_B T \cdot C_{\text{node}}}}{q}$$

where $C_{\text{node}}$ is node capacitance. **Suppressed to zero when CDS
is enabled** (`readout.cds_enabled = True`, the default).

**Quantization noise** --- from ADC digitization:

$$\sigma_{\text{quant}} = \frac{\text{gain\_e\_per\_dn}}{\sqrt{12}}$$

where gain converts between electrons and digital numbers.

*Implementation: `src/radiant/readout/stage.py`*

### Spatial (Fixed-Pattern) Noise (3 terms)

**PRNU** (Photo-Response Non-Uniformity) --- pixel-to-pixel gain variation:

$$\sigma_{\text{PRNU}} = \frac{\text{prnu\_pct}}{100} \cdot S$$

Proportional to signal level. Spatial noise --- does not average with frames.

**DSNU** (Dark Signal Non-Uniformity) --- pixel-to-pixel dark current
variation:

$$\sigma_{\text{DSNU}} = \text{dsnu\_e\_rms}$$

A fixed spatial noise floor.

**Clutter noise** --- scene-induced spatial variation:

$$\sigma_{\text{clutter}} = \sigma_c \cdot S_{\text{bg}}$$

where $\sigma_c$ is the clutter contrast coefficient. Scales with
background signal.

### Other (2 terms)

**Persistence noise** --- residual charge from prior exposure:

$$\sigma_{\text{persist}} = f_p \cdot S_{\text{prior}} \cdot \sqrt{1 - \exp\!\left(-\frac{\Delta t}{\tau}\right)}$$

where $f_p$ is persistence fraction, $S_{\text{prior}}$ is prior frame
signal, $\Delta t$ is time between frames, and $\tau$ is decay time constant.

**Glow shot noise** --- from ROIC thermal glow:

$$\sigma_{\text{glow}} = \sqrt{R_{\text{glow}} \cdot t_{\text{int}}}$$

---

## Dark Current vs. Temperature

RADIANT models dark current temperature dependence via the Arrhenius
relation:

$$J(T) = J_{\text{ref}} \cdot \exp\!\left[\frac{E_a}{k_B}\left(\frac{1}{T_{\text{ref}}} - \frac{1}{T}\right)\right]$$

where $E_a$ is activation energy (eV), $T_{\text{ref}}$ is the reference
temperature, and $J_{\text{ref}}$ is dark current at reference temperature.

Parameters: `detector.dark_rate_e_per_s`, `detector.dark_reference_temperature_K`,
`detector.dark_activation_energy_eV`, `detector.detector_temperature_K`.

---

## CDS Noise Reduction

Correlated Double Sampling (CDS) eliminates kTC reset noise by differencing
the reset and signal reads. When `readout.cds_enabled = True` (default):

- kTC noise → 0
- Read noise is assumed to already include CDS benefit if
  `readout.read_noise_is_post_cds = True`

---

## TDI Noise Scaling

Time Delay Integration sums $N_{\text{TDI}}$ rows. Each noise term scales
differently:

| Noise category | Analog TDI | Digital TDI |
|---------------|-----------|------------|
| Signal        | × $N$     | × $N$      |
| Shot-like temporal | × $\sqrt{N}$ | × $\sqrt{N}$ |
| Read / kTC / quant | × 1 | × $\sqrt{N}$ |
| PRNU / DSNU (spatial) | × $\sqrt{N}$ | × $\sqrt{N}$ |
| Clutter (spatial, scene-correlated) | × $N$ | × $N$ |

Analog TDI sums charge before readout (one read per TDI group). Digital TDI
reads each row independently and sums digitally (read noise per row).

---

## Noise Regime

The `detector.noise_regime` parameter controls which noise terms enter
$\sigma_{\text{total}}$:

- `"imaging"` (default): temporal noise only (shot, dark, read, quant, 1/f,
  G-R, Johnson, kTC, glow, persistence)
- `"detection"`: temporal + spatial noise (adds PRNU, DSNU, clutter)

---

## When Each Term Dominates

| Regime | Dominant noise | Typical scenario |
|--------|---------------|-----------------|
| BLIP (Background-Limited) | Signal/background shot | Cold targets, long integration, low read noise |
| Read-noise limited | Read noise | Short integration, low signal |
| Dark-current limited | Dark shot | Long integration, warm detector |
| FPN-limited | PRNU/clutter | High signal, no frame averaging |

---

## Parameter Cross-Reference

See [Parameter Reference](../guides/parameter_reference.md) for the full
list of detector and readout parameters with types, defaults, and bounds.
