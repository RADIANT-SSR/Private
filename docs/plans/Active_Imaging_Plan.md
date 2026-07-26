# Active Imaging (Flash LADAR) Capability — Development and Test Plan

**Status:** Draft — awaiting owner ratification of §9.1 proposed decisions and answers to §9.2 open questions.

**Date:** 2026-07-26
**Category:** D overall (integration + UX); physics phases are Category C, core-model phases Category B.
**Owner scope decisions already made (conversation, 2026-07-26):**
1. Modality: **active imaging is in scope** as a major capability.
2. Architecture: **flash LADAR** (staring detector array, whole-scene pulsed illumination) — not scanning — is the v1 architecture.
3. Detection: **direct detection only** in v1. Coherent/heterodyne detection is a future upgrade; v1 makes the three structural allowances in §4.9 so that upgrade stays additive.

**Read first:**
`docs/architecture/RADIANT_Master_Architecture.md`,
`docs/architecture/RADIANT_Signal_Chain_Architecture.md`,
`docs/architecture/RADIANT_Parameter_System.md`,
`docs/architecture/RADIANT_Metrics.md`,
`docs/architecture/RADIANT_GUI_Architecture.md`,
`docs/adr/0008-target-extent-to-geometry-and-scenario-type.md` (declared-scenario axis),
`docs/adr/0010-multi-configuration-model.md` (configuration interplay, §4.8 here).

---

## 1. Objective

Add a first-principles **direct-detection flash LADAR** modality to RADIANT: a pulsed laser
transmitter illuminates the full sensor footprint, the existing receiver chain (optics →
focal-plane array) detects the range-gated echo, and the performance stage reports
active-imaging metrics — signal photons per pulse, single-pulse and accumulated SNR,
probability of detection at a specified false-alarm rate, ranging precision, and maximum
detection range — alongside the passive metrics that still apply (GSD, MTF budget, Q,
swath).

The governing architectural insight: **the existing passive chain becomes the
background-noise path of the active system.** Solar/thermal scene radiance through the
receiver's narrow spectral filter — the dominant daytime noise for lidar — is exactly what
the passive source → atmosphere → optics → spectral-integration → detector chain already
computes. The genuinely new physics is confined to: a transmitter model, two-way
atmospheric transmittance at the laser line, speckle, APD gain statistics, range gating,
and the active metric set.

**In scope (v1):**
- Monostatic, direct-detection, hard-target flash LADAR (space-based or airborne).
- Linear-mode APD detection (McIntyre gain/excess-noise model). Unity-gain photodiode is
  the $M{=}1$ degenerate case.
- Single-pulse SNR plus incoherent $N$-pulse accumulation ($\sqrt{N}$).
- Fully developed speckle as a signal-proportional noise term.
- Gaussian threshold detection statistics ($P_d$/$P_{fa}$) via the existing `roc.py` model.
- Range precision (leading-edge/matched-filter estimate) and max-range solver.
- Full GUI integration (modality selector, transmitter/timing panels, active metrics and
  plots, 2-D geometry-viewer beam and gate annotations).

**Out of scope (v1) — each becomes a Gap entry at Phase 0 (§8):**
coherent/heterodyne detection (Doppler, vibrometry); Geiger-mode APD / photon counting;
scanning-lidar architectures and scan-pattern/point-density metrics; atmospheric
backscatter inside the range gate; bistatic geometry; illumination-nonuniformity spatial
effects (transmit beam is radiometrically uniform top-hat in v1); line-by-line molecular
absorption at the laser wavelength (v1 interpolates the band-model grid, §4.3 fragility);
transmit-path turbulence (beam wander/scintillation — second-order for mrad-class flash
divergence, §4.3); multiple returns / foliage penetration / full-waveform simulation;
non-Gaussian detection statistics (speckle-Rician, log-normal); laser eye-safety (ANSI
Z136 MPE) bookkeeping.

---

## 2. What Already Exists (code survey, 2026-07-26)

Reuse inventory — none of these need modification beyond what the phases below state:

| Existing asset | Location | Role in active imaging |
|---|---|---|
| Slant range, incidence, viewing triangle (ADR-0006) | `radiant.geometry`, `core/viewing_triangle.py` | Range $R$ to target and per-pixel geometry — unchanged |
| Passive radiance chain (target + background) | `radiant.source` → `radiant.spectral_integration` | **Background path**: scene radiance through the narrow filter band → background electrons per gate |
| BRDF models (Lambertian $\rho/\pi$, Phong) | `source/brdf_lambertian.py`, `source/brdf_phong.py` | Target reflectance model for the laser return |
| MODTRAN atmosphere, 17-deck boost library | `radiant.atmosphere` | One-way $\tau_{atm}(\lambda)$; active path squares it (§4.3) |
| Receiver PSF/MTF dual path (Rule 4) | `radiant.optics`, `radiant.platform` | Unchanged — flash LADAR receiver is a staring imager |
| Regime machinery (extended / sub-pixel / point) | `optics` final classification (Rule 10), `source/fill_fraction.py` | Governs $R^{-2}$ vs $R^{-4}$ signal scaling (§3.4) and EE_box coupling — unchanged |
| Gaussian ROC: $P_d(P_{fa}) = Q(Q^{-1}(P_{fa}) - \mathrm{SNR})$ | `performance/roc.py` | v1 detection statistics — reused directly |
| Bisection SNR-vs-range solver | `performance/detection_generic.py` | Max-detection-range solver backbone |
| Metric groups + dependency closure (Gap 96) | `performance/metric_selection.py` | New `active` group slots in; taxonomy-partition test forces correct wiring |
| Multi-configuration model (ADR-0010) | `api/config_set.py` | Studies over pulse energy / PRF / gate width work with zero new code |
| Noise budget (`NoiseTerm`, e⁻ RMS at origin frame) | `core/radiometry.py`, `detector/noise/` | Speckle and APD excess noise enter as new terms in the existing budget |
| Turbulence MTF (receive path) | `performance/turbulence_mtf_term.py` | Unchanged (receive-path blur) |
| GUI contextual stage views + plots | `gui/stage_views.py` (`StageComposition`, `PlotSpec`) | New transmitter/timing compositions and $P_d$-vs-$R$ / ROC plots follow the existing pattern |

**What does not exist** (the genuinely new work): any transmitter representation; two-way
transmittance application; pulse/gate timing; APD gain and excess noise; speckle; active
metrics; the modality switch.

---

## 3. Physics Model (v1, normative for Phases 1–4)

All symbols in canonical units (Rule 2): wavelength µm, angles rad, time s, length m,
energy J, electrons e⁻.

### 3.1 Transmit path — irradiance on target

Beam footprint diameter at range $R$ (m), for full-angle divergence $\theta_{div}$ (rad)
and transmit aperture diameter $d_{tx}$ (m):

$$ d_{spot} = d_{tx} + 2R\tan(\theta_{div}/2) \;\approx\; R\,\theta_{div} \quad (R\theta_{div} \gg d_{tx}) $$

Top-hat energy density on target per pulse (J/m²), with pulse energy $E_p$ (J), transmit
optics transmission $T_{tx}$, one-way atmospheric transmittance at the laser line
$\tau_1 = \tau_{atm}(\lambda_L)$, and pointing loss $\eta_{point}$ (§3.5):

$$ F_t = \frac{E_p\, T_{tx}\, \tau_1\, \eta_{point}}{(\pi/4)\, d_{spot}^2} $$

Flash sizing check (validation, not physics): the footprint must cover the sensor scene
footprint; a `UserWarning` (Rule 17-compliant, surfaced) fires when
$\theta_{div} <$ full FOV.

### 3.2 Target return — radiance toward the receiver

Lambertian hard target with reflectance $\rho$ at the laser wavelength (existing BRDF
module):

$$ L_r = \frac{F_t\, \rho}{\pi} \qquad [\mathrm{J\,m^{-2}\,sr^{-1}}\ \text{per pulse}] $$

### 3.3 Receive path — photons and electrons per pixel per pulse

For the **extended-scene regime** (flash lidar imaging a resolved surface), a pixel with
ground-projected area $A_{GIFOV}$ (m², from existing GSD machinery), receiver aperture
area $A_{rx}$ (m²), return-path transmittance $\tau_1$, receiver optics transmission
$T_{rx}$ (existing optics throughput):

$$ E_{rx} = L_r\, A_{GIFOV}\, \frac{A_{rx}}{R^2}\, \tau_1\, T_{rx} \qquad [\mathrm{J/pixel/pulse}] $$

$$ N_{ph} = E_{rx}\, \frac{\lambda_L}{h c}, \qquad N_{pe} = \eta(\lambda_L)\, N_{ph} \quad [\mathrm{e^-/pixel/pulse}] $$

with $\eta(\lambda_L)$ the existing detector QE evaluated at the laser wavelength. The
two-way transmittance $\tau_1^2$ appears as one factor in §3.1 and one here — monostatic
path symmetry (assumption, §9.1-D7).

**Laser-line transmittance:** $\tau_{atm}(\lambda_L)$ is interpolated from the band-model
spectral grid the atmosphere stage already provides. *Fragility (must appear in the
Phase-2 report):* near-IR molecular absorption varies faster than the band-model grid;
a laser line sitting on an absorption feature can be mispredicted. v1 documents this and
files the line-by-line gap; mitigation is choosing $\lambda_L$ in a documented window
(1064 nm, 1550 nm defaults are in windows).

**Transmit-path turbulence:** beam wander (µrad-class) is second-order against mrad-class
flash divergence — excluded in v1 with a gap entry and a documented validity bound
(wander $\ll \theta_{div}$, checked and warned at runtime).

### 3.4 Regime scaling (consistency check with existing regime machinery)

- Extended scene: $A_{GIFOV} \propto R^2$ cancels one $R^2$ → signal $\propto \tau_1^2/R^2$.
- Sub-pixel / point target: target area fixed → signal $\propto \tau_1^2/R^4$ (classic
  point-target lidar scaling).

The existing OpticsStage-final regime (Rule 10) selects the branch; EE_box coupling
follows Rule 9 exactly as in the passive chain (applied to the laser return in
point-source and sub-pixel regimes, never to background, never in extended regime).

### 3.5 Pointing loss

Transmit pointing bias $\beta$ and jitter $\sigma_{point}$ (rad) reduce on-target energy.
v1 top-hat model: $\eta_{point} = 1$ while $\beta + 2\sigma_{point} \le (\theta_{div} - \mathrm{FOV})/2$
(beam oversize margin covers pointing), else the geometric overlap fraction of the
scene footprint that remains illuminated. Level 0 test: closed-form overlap of two
circles. (Gaussian-profile refinement is a listed v2 item, §9.2-Q5.)

### 3.6 Background and dark counts per range gate

The receiver's narrow bandpass filter **is** the existing spectral band definition: the
analyst sets the band limits to the filter passband ($\lambda_L$ must lie inside; validated).
No new spectral machinery. The passive chain then yields background electron rate
$\dot{N}_b$ (e⁻/s/pixel) from scene + path radiance integrated over the band — existing
computation, unchanged.

Range gating replaces the integration time for pulsed detection:

$$ N_b = \dot{N}_b\, t_{gate}, \qquad N_d = \dot{N}_{dark}\, t_{gate} $$

with $t_{gate}$ (s) the gate width. Gate ↔ range-slab conversion $\Delta R = c\,t_{gate}/2$
is a geometry helper (own module, Rule 19).

### 3.7 APD gain and excess noise (McIntyre)

Linear-mode APD with mean gain $M$ and effective ionization ratio $k_{eff}$:

$$ F(M) = k_{eff} M + \left(2 - \tfrac{1}{M}\right)(1 - k_{eff}) $$

Post-gain signal $S = M N_{pe}$; shot-type variances multiply by $M^2 F$. $M{=}1,
F{=}1$ recovers the existing photodiode chain exactly (regression requirement, Phase 3).

### 3.8 Speckle

Coherent illumination of a rough surface produces fully developed speckle: a
signal-proportional fluctuation $\sigma_{speckle} = S/\sqrt{M_s}$, entering the noise
budget as a `NoiseTerm` on the signal frame. $M_s$ is the speckle diversity (independent
cells averaged per pixel per pulse): aperture diversity
$M_{ap} \approx \max\!\big(1, (\pi d_{spot,pix} D_{rx} / (4\lambda_L R))^2\big)$ per
Goodman, times pulse accumulation $N$ (independent realizations for moving
platform/target). The exact $M_s$ expression is a Phase-2 truth-anchor item (Goodman
§4; Richmond & Cain Ch. 7) — the plan fixes the *structure* (signal-proportional term,
$\sqrt{M_s}$ law), the phase fixes the anchored formula. Speckle is what caps single-pulse
SNR on diffuse targets; omitting it would make RADIANT systematically optimistic, which
is why it is v1-mandatory.

### 3.9 Single-pulse SNR and accumulation

$$ \mathrm{SNR}_1 = \frac{M N_{pe}}{\sqrt{\,M^2 F\,(N_{pe} + N_b + N_d) \;+\; \sigma_{read}^2 \;+\; (M N_{pe}/\sqrt{M_s})^2\,}} $$

$\sigma_{read}$ is the existing readout noise chain. Incoherent accumulation of $N$
pulses: $\mathrm{SNR}_N = \sqrt{N}\,\mathrm{SNR}_1$ (speckle term also averages when
realizations decorrelate — assumption documented per §9.1-D8).

### 3.10 Detection statistics, range precision, max range

- $P_d$ at analyst-specified $P_{fa}$: existing `roc.py` Gaussian model with
  $d' = \mathrm{SNR}_N$. Non-Gaussian statistics → gap.
- Range precision (leading-edge / matched-filter estimate, Richmond & Cain):
  $$ \sigma_R \approx \frac{c\, t_{pulse}}{2\, \mathrm{SNR}_N} \;\oplus\; \frac{c\,\sigma_{TDC}}{2} $$
  (RSS with timing-electronics jitter $\sigma_{TDC}$).
- Max detection range: bisection on $\mathrm{SNR}_N(R) \ge \mathrm{SNR}_{req}$ using
  `detection_generic.py`'s solver pattern with the closed-form $R$-scaling of §3.4 and
  range-dependent $\tau_1(R)$ from the atmosphere model.

---

## 4. Core Design

### 4.1 Modality switch

New boolean parameter **`transmitter.enabled`** (default `False`). This is a *third*
axis, deliberately distinct from the two ADR-0008 axes (`source.scene_type` = declared
intent; `source.regime_override` = forced physics). Default-off guarantees every
existing config, golden result, and test is byte-identical — the entire capability is
additive (regression requirement, every phase).

### 4.2 New package: `src/radiant/transmitter/` — a real chain stage

`TransmitterStage` is registered in `api/session.py` between `GeometryStage()` and
`SourceStage()` (it needs range; source/atmosphere need nothing from it until spectral
integration). When `transmitter.enabled` is `False` it writes nothing and returns the
state unchanged (documented no-op, not a silent failure — `history` still records it).

Package layout (Rule 19 — one computation, one module):

```
src/radiant/transmitter/
├── _schema.py          # all transmitter.* ParameterDefs (§4.5)
├── stage.py            # TransmitterStage (protocol-conforming, pure)
├── beam_footprint.py   # d_spot(R) — §3.1 geometry
├── target_irradiance.py# F_t — §3.1 radiometry (τ₁ applied downstream, see note)
├── pointing_loss.py    # η_point — §3.5
├── gate.py             # gate width ↔ range-slab conversion, gate placement
├── errors.py           # TransmitterConfigError(RadiantError)
└── tests/
```

Stage outputs (`state.stage_outputs["transmitter"]`): `enabled`, `wavelength_um`,
`pulse_energy_J`, `pulse_width_s`, `prf_hz`, `footprint_diameter_m`,
`fluence_pre_atmosphere_J_m2` ($F_t$ **without** $\tau_1$ — the atmosphere factor is
applied in spectral integration where $\tau(\lambda)$ lives, keeping Rule 6 data flow
one-directional and the transmitter stage atmosphere-ignorant), `pointing_efficiency`,
`gate_width_s`, `gate_center_range_m`, `n_pulses`.

**No new `ChainState` fields.** The existing `stage_outputs` mapping carries everything;
`NoiseTerm`/`metrics` mechanisms absorb the rest. (Architecture win worth stating in the
ADR.)

### 4.3 Import compliance

`transmitter/` is a physics stage: imports `radiant.core` only (Rule 11). New
`import-linter` contract line mirrors the other eight stages. `api/` gains the
`TransmitterStage` import (allowed). Reflectance at $\lambda_L$ is read from the
source-stage outputs via `ChainState`, **not** by importing `radiant.source`.

### 4.4 Active return radiometry — `spectral_integration/active_return.py`

Rule 8 says spectral collapse happens exactly once, in `SpectralIntegrationStage` — and
the laser return is born quasi-monochromatic, so that is where it joins the chain. New
module `active_return.py` (plus `speckle.py` for the $M_s$/noise-term computation)
computes §3.2–§3.4 from `stage_outputs` (transmitter, geometry, optics regime, atmosphere
$\tau(\lambda_L)$ interpolation) and:

- writes `laser_signal_e_per_pulse` into the spectral-integration stage outputs, joining
  the standard electron-domain frames;
- **redefines the signal/background split in active mode**: the laser return is the
  signal; the passive radiance of the target *and* background within the filter band all
  become background counts (they are scene glow the gate integrates). This redefinition
  is explicit in the stage outputs (`signal_source: "laser"`) and in the docs;
- adds the speckle `NoiseTerm` (§3.8) at the spectral-integration frame;
- applies EE_box per Rule 9 to the laser return only, per regime.

### 4.5 Parameter schema (all new `ParameterDef`s; input→canonical per Rule 2)

`transmitter/_schema.py`:

| Name | dtype | canonical | input | default | bounds / enum | Notes |
|---|---|---|---|---|---|---|
| `transmitter.enabled` | bool | — | — | `False` | — | Modality switch |
| `transmitter.wavelength_um` | float | µm | µm | `None` (required if enabled) | (0.2, 20) | Must lie inside spectral band (validated) |
| `transmitter.pulse_energy_mJ` | float | J | mJ | `None` (required) | (0, 1e4) | |
| `transmitter.pulse_width_ns` | float | s | ns | `None` (required) | (0.01, 1e6) | Drives $\sigma_R$ |
| `transmitter.prf_kHz` | float | Hz | kHz | `None` (required) | (1e-6, 1e5) | Frame rate = PRF for flash |
| `transmitter.divergence_full_angle_mrad` | float | rad | mrad | `None` (required) | (1e-4, 1e3) | Flash-coverage warning vs FOV |
| `transmitter.aperture_diameter_mm` | float | m | mm | 0.0 | [0, 2e3) | 0 → pure-divergence far field |
| `transmitter.beam_profile` | str | — | — | `"tophat"` | {tophat} | Enum grows in v2 (gaussian) |
| `transmitter.optics_transmission` | float | frac | frac | 1.0 | (0, 1] | |
| `transmitter.pointing_bias_urad` | float | rad | µrad | 0.0 | [0, 1e6) | |
| `transmitter.pointing_jitter_rms_urad` | float | rad | µrad | 0.0 | [0, 1e6) | Transmit-side; distinct from `platform.jitter_rms_urad` (receive) |
| `transmitter.gate_width_ns` | float | s | ns | `None` (required) | (0.1, 1e9) | Background/dark integrate over this |
| `transmitter.gate_center_mode` | str | — | — | `"auto_target_range"` | {auto_target_range, manual} | auto = geometry slant range |
| `transmitter.gate_center_range_m` | float | m | m | `None` | (0, ∞) | Required iff manual |
| `transmitter.n_pulses_accumulated` | int | — | — | 1 | [1, 1e9) | $\sqrt{N}$ accumulation |
| `transmitter.target_reflectance_at_laser` | float | frac | frac | `None` | (0, 1] | `None` → evaluate existing source material $\rho(\lambda_L)$; scalar overrides |

`detector/_schema.py` additions:

| Name | dtype | canonical | input | default | bounds | Notes |
|---|---|---|---|---|---|---|
| `detector.apd_gain` | float | — | — | 1.0 | [1, 1e4) | $M{=}1$ ⇒ existing chain exactly |
| `detector.apd_k_eff` | float | — | — | 0.02 | [0, 1] | McIntyre; default = owner decision §9.2-Q3 |

`readout/_schema.py` addition:

| Name | dtype | canonical | input | default | bounds | Notes |
|---|---|---|---|---|---|---|
| `readout.tdc_jitter_ps` | float | s | ps | 0.0 | [0, 1e6) | Timing-electronics term in $\sigma_R$ |

`performance/_schema.py` addition:

| Name | dtype | canonical | input | default | bounds | Notes |
|---|---|---|---|---|---|---|
| `performance.active_pfa` | float | frac | frac | 1e-6 | (0, 0.5) | $P_{fa}$ operating point for `active_pd` |
| `performance.active_snr_required` | float | — | — | 6.0 | (0, ∞) | Threshold for max-range solver |

~20 new parameters total. `scripts/gen_param_reference.py --check` regenerates the
reference doc in each schema-touching phase (gate battery item).

### 4.6 Detector and readout additions

- `detector/apd.py` — McIntyre $F(M)$, gain application (own module, Rule 19).
- `detector/noise/` — existing shot-type terms gain the $M^2F$ factor **only when**
  `apd_gain > 1` and modality active; gate width replaces integration time for
  background/dark when active. Implementation constraint: the $M{=}1$/passive path must
  be bit-identical to today (golden regression, Phase 3).
- `readout/tdc.py` — TDC jitter contribution (feeds `range_precision_m` only; no MTF
  term, analogous to the TDI mis-registration precedent as a non-spatial readout effect —
  but unlike TDI it touches neither MTF path, so no Rule 4 exclusion entry is needed).

### 4.7 Performance metrics — new `active` metric group

New modules (Rule 19, one metric one module): `active_snr.py`, `active_detection.py`
(wraps `roc.py`), `range_precision.py`, `active_max_range.py`, plus `MetricSpec`
registrations and a new `METRIC_GROUPS["active"]` entry. The Gap 96 taxonomy-partition
test forces every new metric into the group — wiring cannot be forgotten.

| Metric key | Unit | Meaning |
|---|---|---|
| `laser_photons_per_pulse` | photons | $N_{ph}$ at detector, per pixel per pulse |
| `laser_signal_e_per_pulse` | e⁻ | $N_{pe}$ (pre-gain) |
| `background_e_per_gate` | e⁻ | $N_b$ |
| `speckle_diversity_cells` | dimensionless | $M_s$ |
| `active_snr_single_pulse` | dimensionless | §3.9 |
| `active_snr_accumulated` | dimensionless | $\sqrt{N}$-accumulated |
| `active_pd` | fraction | $P_d$ at `performance.active_pfa` |
| `range_precision_m` | m | $\sigma_R$ |
| `active_max_range_m` | m | SNR-threshold bisection solve |
| `laser_footprint_diameter_m` | m | $d_{spot}$ at target range |
| `gate_range_depth_m` | m | $c\,t_{gate}/2$ |

Distinct from the existing passive `detection_range_m` (point-source passive solver) —
both can coexist in one report. Passive-only metrics (NEDT, NIIRS/GIQE, MRT) are simply
not in the `active` group; the analyst's group toggles govern as today (no forced
disabling — see GUI defaults, §5.2). **Rule 4 status:** the PSF/MTF dual path is
untouched; the consistency check runs exactly as today when spatial metrics are enabled.

### 4.8 Config file, API, CLI, multi-configuration

- YAML: a flat `transmitter:` parameter namespace — no new structured section needed
  (unlike ADR-0009 element lists); `ConfigError` if `transmitter.enabled` with missing
  required params (Rule 15 actionable message listing them).
- `Sensor`/`ChainResult`: no new public methods; metrics arrive through the existing
  metric surface. `result.inspect()` shows transmitter stage outputs automatically.
- CLI: `radiant run`/`validate`/`explain` work unchanged; `explain` gains transmitter
  stage text (same mechanism as other stages).
- Multi-configuration (ADR-0010): `transmitter.*` parameters are configurable per
  configuration like any other — a pulse-energy or gate-width study needs zero new code.
  Explicit test in Phase 5.

### 4.9 Coherent-future allowances (the only three, per owner decision)

1. Namespace is `transmitter.*` (not `pulse.*`/`laser.*`) so linewidth/coherence
   parameters land beside existing ones additively.
2. "Signal+noise at detector" and "statistics → $P_d$/$P_{fa}$" stay in separate modules
   with a documented interface (`active_snr.py` vs `active_detection.py`) so a coherent
   receiver swaps the statistics module, not the radiometry.
3. Atmosphere turbulence outputs remain exposed as named quantities ($r_0$, $C_n^2$
   already surfaced) rather than pre-baked intensity effects.

Zero coherent physics is implemented. The exclusion gap records these three seams.

---

## 5. GUI Design (Phase 6; binding once §9 ratified)

Per `RADIANT_GUI_Architecture.md`: the GUI is a view over the scripting API — one action
↔ one API call; no physics in `gui/`. All new displays obey the hard display-unit rule
(entry/display symmetric in the user's chosen unit — mJ, ns, kHz, mrad, µrad, photons,
e⁻) and the messages panel explains regime and unused-parameter consequences.

### 5.1 Modality selector

An **Active illumination** toggle (backing `transmitter.enabled`) in the sensor-level
header area, adjacent to — but visually distinct from — the declared-scenario control
(`source.scene_type`, ADR-0008). Toggling re-skins stage panels (5.2), seeds metric-group
defaults (5.3), and adds the viewer annotations (5.4). Relation to the pending two-tier
mission-type-selector proposal: this toggle is that proposal's first concrete tier-1 axis;
the plan neither blocks on nor supersedes it (owner note §9.2-Q6).

### 5.2 New stage panels (`StageComposition` entries in `stage_views.py`)

- **Transmitter panel** (namespace `transmitter`): laser parameters with live derived
  read-outs — footprint diameter (m) vs scene footprint (m) with the coverage warning
  inline, fluence on target (J/m²), photons per pulse (photons). Sub-views follow the
  existing `StageSubView` pattern.
- **Timing & gating sub-panel**: gate width (ns) with live range-depth (m), gate-center
  mode, pulse accumulation count; TDC jitter lives here visually though the parameter is
  `readout.*` (panels are namespace-primary, not namespace-exclusive — existing precedent).
- **Detector panel addition**: APD group (gain, $k_{eff}$, live $F(M)$ read-out),
  visible only when active modality is on.
- Passive-only parameter groups grey out with a messages-panel explanation (never
  hidden-and-silent) when active mode changes their meaning (e.g. integration time vs
  gate width).

### 5.3 Results: metric matrix and plots

- `active` metric group column/rows appear in the existing metric matrix (multi-config
  side-by-side columns work unchanged).
- Two new `PlotSpec` plots: **$P_d$ vs range** (at the configured $P_{fa}$) and **ROC
  curve** at scene range. Both honor unit settings and export via the existing xlsx path.
- Modality toggle seeds *default* group selections (active on: `radiometric`,
  `sampling`, `saturation`, `spatial_mtf`, `active`; `interpretability` off) — seeds
  only; the analyst's explicit toggles are never overridden.

### 5.4 2-D geometry viewer (QPainter schematic — stays 2-D, ratified 2026-07-14)

Two annotation layers: transmit-beam cone (boresight-aligned, divergence to scale in
angle-space, not-to-scale altitude per the leader-label convention) and the range-gate
slab (two chords bracketing the target at $c\,t_{gate}/2$ depth, labeled in m). Layer
visibility follows the modality toggle.

### 5.5 Scenario deliverable

Phase 7 adds one worked scenario under `scenarios/` (persona TBD §9.2-Q7) with the
mandatory trio `walkthrough.md`, `gaps.md`, `gui_workflow.md` — the GUI workflow doc is
the acceptance script for Phase 6.

---

## 6. Development Plan (phases = branches = merges, per Multi-Agent Git Hygiene)

Every phase: one branch, gate battery green (`pytest -q`, touched goldens,
`mypy --strict` core+api, `ruff check src/ tests/`, `lint-imports`,
`check_org_rules.py`, `gen_param_reference.py --check`), merge, push, branch deleted.
Registry edits (gaps/CUs/CHANGELOG) are separate immediate commits. Level 0 tests are
written **before** the physics they verify (Rule 18).

### Phase 0 — ADR + gap filings (Category A; branch `adr/active-phase0`)
- ADR-0011 "Active imaging model — direct-detection flash LADAR": records §3 model
  choices, §4 placement decisions, §9 ratifications, the three coherent-future seams.
- File the §1 exclusion gaps (numbered at filing time; one commit).
- CHANGELOG: no entry (doc-only).
- Effort: 1 session.

### Phase 1 — Transmitter stage package (Category C; branch `transmitter/active-phase1`)
- `src/radiant/transmitter/` per §4.2; schema per §4.5 (transmitter namespace only);
  stage registration in `api/session.py` (no-op when disabled); import-linter contract.
- Docs lock-step: new `docs/architecture/RADIANT_Active_Imaging.md` (§1–§3 of the spec),
  Master Architecture stage list + document map, Parameter System, Signal Chain doc.
- CHANGELOG: public-surface entry (new stage + parameters, default-off).
- Effort: 2 sessions.

### Phase 2 — Active return radiometry + speckle (Category C; branch `si/active-phase2`)
- `spectral_integration/active_return.py`, `speckle.py`; τ interpolation at $\lambda_L$;
  signal/background redefinition; EE_box regime coupling; speckle `NoiseTerm`.
- Effort: 2–3 sessions (the physics heart; three truth anchors mandatory, §7).

### Phase 3 — APD + timing (Category C; branch `detector/active-phase3`)
- `detector/apd.py`, noise-term $M^2F$ wiring, gate-width integration substitution,
  `readout/tdc.py`; schema additions.
- Hard regression requirement: $M{=}1$/passive bit-identical goldens.
- Effort: 2 sessions.

### Phase 4 — Performance metrics (Category C; branch `perf/active-phase4`)
- Four metric modules (§4.7), `MetricSpec` registrations, `METRIC_GROUPS["active"]`,
  metric-selection wiring, `performance` schema additions.
- Docs: Metrics doc §§ for each metric (formula, units, regime notes).
- Effort: 2 sessions.

### Phase 5 — API/config/CLI integration + goldens (Category D; branch `api/active-phase5`)
- YAML validation (`ConfigError` messages), example template
  (`examples/templates/swir_leo_flash_ladar.yaml` — name per §5.2 conventions), CLI
  `explain` text, multi-config study test (pulse-energy sweep), **new golden**: one
  full-chain active config with committed baseline (generator named per Rule 26).
- Regression: full passive golden suite unchanged.
- Effort: 2 sessions.

### Phase 6 — GUI (Category D; sub-phases, each its own branch `gui/active-phase6a…e`)
- 6a modality toggle + session model; 6b transmitter/timing/APD panels; 6c metric
  matrix + $P_d$/ROC plots; 6d geometry-viewer annotations; 6e polish + display-unit
  audit. pytest-qt throughout (existing patterns).
- Effort: 4–5 sessions total.

### Phase 7 — Close-out (Category A/D; branch `docs/active-phase7`)
- Worked scenario (trio incl. `gui_workflow.md`), docs final pass, re-audit any
  stage-deferred CUs touched, archive this plan with HISTORICAL banner + merge-record
  table (Rule 24), final CHANGELOG consolidation check.
- Effort: 1–2 sessions.

Total: ~16–19 sessions. Phases 1–4 are strictly ordered (each consumes the previous
stage's outputs); 5 follows 4; 6 follows 5; no useful parallelism except 6d (viewer)
which depends only on 6a.

---

## 7. Test Plan

### Level 0 anchors (written first, per phase)

Phase 1: beam-spread geometry ($d_{spot}$ hand calc); top-hat fluence energy
conservation ($\int F_t\,dA = E_p T_{tx}\eta_{point}$, τ excluded at this stage);
circle-overlap pointing loss closed form.

Phase 2 (three independent truth anchors, Category C):
1. Full link budget hand calculation (energy → photons at detector) for a published-style
   1550 nm airborne flash case — Richmond & Cain, *Direct-Detection LADAR Systems* (SPIE
   TT85, 2010), worked-example chapter.
2. Range-equation cross-check against McManamon, *LiDAR Technologies and Systems* (SPIE,
   2019) link-budget example.
3. Speckle: $\sigma/S = 1/\sqrt{M_s}$ against Goodman, *Speckle Phenomena in Optics*
   (§ fully-developed speckle; $M_s{=}1$ ⇒ contrast 1 limit; aperture-diversity formula).
   Regime notes must cover the $R^{-2}$ vs $R^{-4}$ transition (§3.4) matching the
   regime machinery's classification.

Phase 3: McIntyre $F(M)$ against the 1966 paper's tabulated values ($k{=}0$: $F \to 2 - 1/M$;
$k{=}1$: $F = M$); $M{=}1 \Rightarrow F{=}1$ identity; gate-width substitution
dimensional audit (e⁻/s × s = e⁻).

Phase 4: `roc.py` identities reused (already anchored); $\sigma_R$ against Richmond &
Cain's leading-edge expression; max-range solver against a hand-solved crossing with
constant-τ toy atmosphere ($R^{-2}$ ⇒ analytic solution).

### Unit and integration
- Per-module unit tests in each package's `tests/` (explicit `rel=`/`abs=` tolerances).
- Failure modes per Category C spec: zero pulse energy, gate width → 0/∞, divergence
  smaller than FOV (warning), $\lambda_L$ outside band (error), $k_{eff}$ at 0 and 1,
  required-param-missing errors, SNR → 0 limits of $P_d$ and $\sigma_R$.
- Integration (Phase 5): active golden config; **passive regression** — full existing
  golden suite byte-identical with `transmitter.enabled=False` (the default).
- GUI (Phase 6): pytest-qt — toggle round-trip to YAML, unit-symmetry on every new
  field, panel visibility, plot creation smoke tests.
- Consistency check (Rule 4): assert the check still runs and passes on an active config
  with spatial metrics enabled (no new MTF terms ⇒ no new exclusions).

---

## 8. Registry & Doc Lock-Step Summary (Rules 20/21/29)

| Artifact | When |
|---|---|
| Gap: active-imaging capability (parent, status PLANNED → this plan) | Filed with this plan (own commit) |
| Gaps: v1 exclusions (§1 list) | Phase 0, one commit |
| ADR-0011 | Phase 0 |
| `docs/architecture/RADIANT_Active_Imaging.md` (new spec) | Phase 1, grows through Phase 6 |
| Master Architecture (stage list, doc map), Signal Chain, Parameter System | Phase 1 (+ touched phases) |
| Metrics doc | Phase 4 |
| Config Format, Scripting API | Phase 5 |
| GUI Architecture | Phase 6 |
| CHANGELOG `[Unreleased]` | Every phase adding public surface (1, 3, 4, 5, 6); none results-affecting for passive users (default-off) |
| CUs | Any latent issue found in passing, before that phase's merge (Rule 21) |
| This plan → `docs/archive/` with merge-record table | Phase 7 (Rule 24) |

---

## 9. Decisions

### 9.1 Proposed for ratification (owner sign-off turns Draft → Active)

- **D1** Modality switch is `transmitter.enabled` (default `False`); passive results
  guaranteed unchanged.
- **D2** New physics package/stage `radiant.transmitter`, registered between geometry
  and source; no-op when disabled.
- **D3** The receiver spectral filter **is** the existing band definition (no separate
  filter machinery); $\lambda_L$ validated to lie in-band.
- **D4** In active mode the laser return is the signal; all passive in-band radiance
  (target + background) becomes background counts.
- **D5** v1 detection statistics are the existing Gaussian ROC model; refinements are
  gaps, not blockers.
- **D6** Speckle is v1-mandatory as a signal-proportional `NoiseTerm` with $\sqrt{M_s}$
  diversity averaging.
- **D7** Monostatic path symmetry: one $\tau_1$ each way, i.e. $\tau_{2way} = \tau_1^2$.
- **D8** $N$-pulse accumulation is incoherent $\sqrt{N}$, assuming decorrelated speckle
  realizations between pulses (documented assumption + runtime note when $N > 1$).
- **D9** No new `ChainState` fields; everything flows through `stage_outputs`,
  `NoiseTerm`s, and `metrics`.
- **D10** GUI modality toggle seeds metric-group defaults but never overrides explicit
  analyst selections.

### 9.2 Open questions (answers folded into ADR-0011 at Phase 0)

- **Q1** Default example wavelength/template: 1550 nm SWIR LEO flash (proposed) or
  1064 nm airborne? (Affects only the Phase-5 template and scenario.)
- **Q2** `performance.active_pfa` default 1e-6 — acceptable operating point?
- **Q3** `detector.apd_k_eff` default: 0.02 (HgCdTe e-APD-like, near-noiseless) vs 0.2
  (InGaAs-like). Proposal: 0.02 with the InGaAs value called out in the parameter
  description; no silent surprises either way since $F(M)$ is displayed in the GUI.
- **Q4** Gate-center auto mode uses the geometry slant range — sufficient for v1, or is
  analyst-specified gate *depth margin* (m) wanted as a third parameter?
- **Q5** Pointing-loss model: is the §3.5 top-hat overlap adequate for v1, or is a
  Gaussian-beam refinement wanted immediately? (Proposal: top-hat; Gaussian is v2 with
  `beam_profile` enum growth.)
- **Q6** Sequencing vs the pending two-tier mission-type-selector proposal: land this
  toggle first and fold it in later (proposal), or block Phase 6a on that design?
- **Q7** Scenario persona for the Phase-7 walkthrough (suggest a new persona — active
  imaging isn't covered by the existing 35-scenario catalog; catalog gains a Tier for
  it, or the scenario lives standalone).
- **Q8** Eye-safety (ANSI Z136 MPE) bookkeeping: confirmed out of scope v1 (gap), or
  wanted as a simple reported quantity? (Proposal: gap.)
