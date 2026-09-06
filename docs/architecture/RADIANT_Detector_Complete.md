# RADIANT Detector Complete

**Status**: Authoritative for the noise model and readout order; **partially design-target** for the QE-input model and the parameter inventory (see banner below).
**Scope**: The detector and the readout chain in one document. QE, pixel geometry, the complete noise budget, TDI, on-chip and off-chip binning, coadds, two-stage saturation, and the readout-order rules that make all of this consistent. Splitting detector and readout into separate documents would break the noise-and-timing interactions, which is exactly the point of this combined design.
**Sister documents**: RADIANT_Conventions.md, RADIANT_Optics.md, RADIANT_Spatial_Complete.md, RADIANT_Atmosphere.md, RADIANT_Signal_Chain_Architecture.md, RADIANT_Scan_Timing.md

> **Implementation-reality banner (reconciled 2026-07-12).** This document was a
> unified first design pass; parts of it describe abstractions that were never
> built as written. What is **shipped and verified**: the 16-source noise model
> (§4), the temporal/spatial split (§5), the canonical readout order and both
> saturation checks (§6), TDI / binning / coadds scaling (§7–§10). What is
> **design-target, not implemented**: the single `DetectorState` frozen dataclass
> (§2 — the stages instead write signal, the noise-term tuple, and MTF arrays into
> the immutable `ChainState`); the `QeInput` LIBRARY/CUSTOM enum with
> material-name selection and cutoff-warping (§3.1 — only scalar `qe_value` and a
> `qe_table_path` CSV are implemented); and sub-band / two-color weighting (§3.2).
> The §11 parameter inventory has been rewritten to the real schema. Sections that
> remain design-target are flagged inline with **[DESIGN-TARGET]**.

---

## 1. Design Philosophy

1. **One contract: `DetectorState`.** Everything the readout, performance, and metric stages need is delivered as a single immutable object: per-pixel signal in electrons, the per-pixel noise budget split into temporal and spatial components, the realized saturation status, and the digital output in DN.
2. **Noise sources are enumerated, not implicit.** RADIANT computes 16 noise sources (see §4) independently and stores each one. Quadrature combination is the *last* step. No noise term is rolled into another at the source.
3. **Two saturation points, in two domains.** Analog well capacity (after TDI accumulation, before readout) is one saturation. ADC dynamic range (after gain conversion) is the other. Both are checked. A frame can saturate at one without saturating the other.
4. **The readout order is canonical.** TDI accumulates before binning before well check before nonlinearity before read-noise injection before gain before A/D before off-chip binning before coadds. Each step is in a specific domain (analog or digital) and the noise math depends on that. Re-ordering is not a configuration option.
5. **Temporal vs. spatial noise is the user's regime choice, not a guess.** Imaging applications (where the user calibrates fixed-pattern out) report temporal noise only. Detection applications (where every pixel is interrogated independently and FPN looks like clutter) report temporal + spatial. The user picks; the framework reports both.

---

## 2. The `DetectorState` Contract **[DESIGN-TARGET]**

> **Not implemented as a single object.** There is no `DetectorState` frozen
> dataclass in the codebase. The `DetectorStage` and `ReadoutStage` write their
> outputs into the immutable `ChainState` instead: per-pixel signal and the
> realized scaling/saturation status go into `stage_outputs["detector"]` /
> `stage_outputs["readout"]`, each noise source is appended to the
> `ChainState.noise_terms` tuple as a `NoiseTerm` (§4), and the pixel-aperture,
> charge-diffusion, and IPC MTFs go into `ChainState.mtf_terms`. The fields below
> are the *conceptual* contract those outputs collectively satisfy — read them as
> a checklist of what the two stages produce, not as a literal type.

```python
@dataclass(frozen=True)
class DetectorState:
    # ---- Identification ---------------------------------------------------
    detector_material: DetectorMaterial          # SI_CCD | SI_CMOS | INGAAS | HGCDTE_MWIR
                                                 # | HGCDTE_LWIR | INSB | T2SL | CUSTOM
    pixel_pitch_m: tuple[float, float]           # (x, y)
    fill_factor: float
    derivation_chain: tuple[str, ...]

    # ---- Signal -----------------------------------------------------------
    signal_e_per_pixel: float                    # post-TDI, post-binning, post-FWC clip
    signal_dn: float                             # post-gain, post-ADC clip
    saturation_well: SaturationStatus            # OK | CLIPPED | SEVERELY_CLIPPED
    saturation_adc:  SaturationStatus

    # ---- Noise ------------------------------------------------------------
    noise_terms: dict[str, float]                # 16 entries, each in e- RMS
    sigma_temporal_e: float                      # RSS of temporal terms
    sigma_spatial_e: float                       # RSS of spatial terms
    sigma_total_e: float                         # RSS of (temporal, spatial) per regime

    # ---- Spatial coupling -------------------------------------------------
    mtf_pixel_aperture: np.ndarray | None
    mtf_charge_diffusion: np.ndarray | None
    mtf_ipc: np.ndarray | None

    # ---- Realized scaling factors -----------------------------------------
    n_tdi_realized: int
    binning_onchip: tuple[int, int]
    binning_offchip: tuple[int, int]
    n_coadds: int
    cds_enabled: bool
```

---

## 3. QE Library and Pixel Geometry

### 3.1 QE inputs

**Implemented (two paths only):** QE is supplied either as a flat scalar
`detector.qe_value` **or** as a wavelength-vs-QE CSV `detector.qe_table_path`
(the two are mutually exclusive — `qe_value` is `required_unless` `qe_table_path`
is set). An optional linear temperature correction is applied via
`detector.qe_temperature_coeff_per_K` about `detector.qe_temperature_ref_K`.
Material QE curves ship in `data/detectors/` (`hgcdte_mwir.csv`,
`hgcdte_lwir.csv`, `ingaas.csv`, `inp_ingaasp.csv`, `silicon.csv`,
`type2_sls.csv`) and are loadable through `radiant.data.SpectralLibrary`; a user
selects one by pointing `qe_table_path` at it.

> **[DESIGN-TARGET]** The `QeInput` LIBRARY/FILE/CUSTOM enum, material-name
> selection with `detector.qe_cutoff_um` cutoff-warping, and the `CUSTOM`
> parametric Fermi-edge curve (`qe_peak`, `qe_cuton_um`, `qe_rolloff_sharpness`)
> below are **not implemented**. Only the scalar and CSV paths above exist. The
> material table is a reference for the shipped CSVs, not a selectable enum.

```python
# DESIGN-TARGET — not in the codebase
class QeInput(StrEnum):
    LIBRARY = "library"          # one of the built-in materials
    FILE    = "file"             # user-supplied QE(λ) table
    CUSTOM  = "custom"           # parametric model with cutoff
```

Reference cutoffs for the shipped material CSVs:

| Material | Cutoff (µm) | Typical peak QE | Notes |
|----------|-------------|-----------------|-------|
| Si CCD | 1.1 | 0.85 | Backside-illuminated; UV-enhanced variant available |
| Si CMOS | 1.1 | 0.75 | Frontside; rolling-shutter implied unless overridden |
| InGaAs | 1.7 (or 2.5 ext.) | 0.80 | SWIR; both standard and extended cutoffs |
| HgCdTe MWIR | 5.3 | 0.85 | Cutoff tunable per program |
| HgCdTe LWIR | 10.5 | 0.75 | Tunable; 9.5 / 10.5 / 12 µm common |
| InSb | 5.5 | 0.80 | Classic MWIR |
| T2SL | 9.5 | 0.55 | Two-color superlattice |

### 3.2 Sub-band weighting **[DESIGN-TARGET]**

> **Not implemented.** There is no `detector.qe_subbands` parameter and no
> multi-layer / two-color per-band signal path. A single QE curve is applied per
> run. The design below is retained as the intended future model.

For multi-layer / two-color detectors, the user supplies a list of sub-bands, each with its own QE curve and the relative *electron* weight (not photon weight) per band. The framework computes the in-band signal for each layer separately and reports them per-band.

### 3.3 Pixel geometry

Parameter types, defaults, units, and bounds are the canonical [Parameter Reference](../guides/parameter_reference.md) (auto-generated from the schema — the single source of truth, Rule 27). The pixel-geometry parameters are `detector.pixel_pitch_x_um`, `detector.pixel_pitch_y_um` (defaults to `pitch_x` for a square pixel), `detector.fill_factor`, and `detector.charge_diffusion_length_m`.

The canonical charge-diffusion parameter is `detector.charge_diffusion_length_m`
(canonical unit metres, per the naming convention), **not** `_um`. There is no
`detector.pixel_shape` parameter — the pixel-aperture model is rectangular fill
only; the circular (`jinc`) variant is design-target.

The pixel-aperture MTF is `sinc(π·f_x·p_x·√FF) · sinc(π·f_y·p_y·√FF)` for rectangular fill (FF is the *areal* photosensitive fraction, so a square photosite has linear width `p·√FF`; CU-074). The same `p·√FF` width drives the PSF-path pixel-aperture kernel (both Rule-4 paths agree), and the radiometric collecting area `p²·FF` scales the collected signal. Charge diffusion is a Gaussian convolution with `σ = L_d / √2`. Both feed the spatial PSF cascade per `RADIANT_Spatial_Complete.md` §6.

---

## 4. The Complete Noise Model — 16 Sources

The 13 sources from the original prompt, plus three more I have included after thinking about it (persistence, glow, IPC fixed pattern). Each is computed separately, stored under a stable key, and combined only at the end.

### Photon-shot family
| # | Term | Origin | Equation | When it matters | Parameters |
|---|------|--------|----------|-----------------|------------|
| 1 | `signal_shot` | Poisson statistics on signal electrons | `√S_signal` | Always | none beyond signal |
| 2 | `background_shot` | Same, on background electrons | `√S_bg` | Always; dominant in LWIR | from source/atm |
| 3 | `nearfield_shot` | Same, on warm-optics electrons | `√S_nf` | Dominant in LWIR/MWIR with warm optics | from optics |
| 4 | `straylight_shot` | Same, on stray-light electrons | `√S_stray` | Always present, often small | from optics |

Photon-shot terms have **no free parameters** beyond the upstream electron rates. They are not configurable; they are computed from physics.

### Detector-material family
| # | Term | Origin | Equation | When | Parameters |
|---|------|--------|----------|------|------------|
| 5 | `dark_shot` | Poisson on thermally generated carriers | `√(J_dark · t_int)` | Always; dominant cooled IR | `J_dark`, `T_det` |
| 6 | `gr_noise` | Generation-recombination through trap states | `√(2 · J_gen · t_int)` Burstein form | HgCdTe / T2SL | `gr_factor` (scales above shot) |
| 7 | `johnson_noise` | Thermal noise across detector R₀A | `√(4kT/(R₀A) · A · t_int) · e/q` | Photovoltaic IR | `R0A_ohm_cm2`, `T_det` |
| 8 | `flicker_1f` | 1/f flicker in detector + ROIC | `σ_1f² = K · ln(f_high/f_low)` | Long integrations, low signal | `flicker_K`, `flicker_f_low`, `flicker_f_high` |

`gr_noise`, `johnson_noise`, `flicker_1f` are zero by default and only kick in when their parameters are set. Users running a Si visible system see all three at zero.

### ROIC family
| # | Term | Origin | Equation | When | Parameters |
|---|------|--------|----------|------|------------|
| 9 | `read_noise` | ROIC sense node + amplifier | `read_noise_e_rms` (parameter) | Always | `read_noise_e_rms` |
| 10 | `ktc_reset_noise` | kT/C on the sense node | `√(kTC)/q`, suppressed by CDS | Snapshot pixels w/o CDS | `node_capacitance_F`, `T_det`, `cds_enabled` |
| 11 | `quantization_noise` | ADC LSB | `LSB / √12` (e-) | Always (small unless under-bitted) | `gain_e_per_dn`, `adc_bits` |

When `cds_enabled = True`, the kTC term is set to zero and the suppression is recorded.

> **Actual `NoiseTerm` keys.** The shipped keys for terms 10 and 11 are
> `ktc_reset` and `quantization` (not `ktc_reset_noise` / `quantization_noise` as
> written in the tables above). All 16 terms are produced; the ROIC/well/gain
> controls they depend on live in `readout.*` (see §11.2), and `node_capacitance_F`
> is read from `readout.node_capacitance_F`.

### Fixed-pattern (spatial) family
| # | Term | Origin | Equation | When | Parameters |
|---|------|--------|----------|------|------------|
| 12 | `prnu` | Pixel-to-pixel responsivity variation | `prnu_pct · S_signal / 100` | Imaging w/o flat-field; detection always | `prnu_pct` |
| 13 | `dsnu` | Pixel-to-pixel dark variation | `dsnu_e_rms` | Long integrations | `dsnu_e_rms` |
| 14 | `clutter` | Scene background spatial variation | `clutter_sigma · S_bg` | Detection only | `background.clutter_sigma` |

### Other (added after re-thinking)
| # | Term | Origin | Equation | When | Parameters |
|---|------|--------|----------|------|------------|
| 15 | `persistence_noise` | Trap relaxation from prior frame | `f_persist · S_prev · √(1 − exp(−Δt/τ_p))` | HgCdTe long-stare; coadds | `persistence_fraction`, `persistence_tau_s`, `prior_signal_e` |
| 16 | `glow_shot` | Detector + mux glow | `√(R_glow · t_int)` | LWIR cooled w/ ROIC glow | `glow_e_per_s` |

### Sources I considered but did NOT include as separate terms
- **Cosmic rays**: returned as a separate `event_rate_per_s_per_cm2` statistic, not a noise term. They are an outlier-rejection problem, not a Gaussian noise.
- **ADC nonlinearity (INL/DNL)**: deferred per RADIANT_Scope_Decisions.md (electronics-tool concern).
- **Crosstalk**: optical crosstalk is deferred (D17). Electrical crosstalk is folded into IPC, which appears as an MTF term, not a noise term.
- **Bias drift**: handled as a constant DN offset (R10 in scope), not a noise term — it doesn't add variance per frame.
- **Image lag** in CCDs: rolled into persistence with `persistence_tau_s ~ frame period`.
- **Anti-blooming drain**: a saturation effect (reduces effective FWC) not a noise term. Folded into the well check.

That gives 16 noise terms in v1, with 4 categories deferred or folded. **Recommendation: include all 16 above**; persistence and glow especially are LWIR-relevant and the cost of carrying them is one extra parameter each.

### 4.1 CDS effect on noise terms

Correlated double sampling subtracts a reset frame from a signal frame, suppressing noise terms that are correlated between the two reads. The framework applies CDS as follows:

| Term | Effect of CDS |
|------|---------------|
| `ktc_reset_noise` | Set to 0 |
| `flicker_1f` | **Unaffected** — RADIANT does not currently model CDS 1/f suppression. (A `cds_1f_suppression` 0.7 factor was documented but never implemented; removed CU-077.) |
| `read_noise` | **Unaffected** — `read_noise_e_rms` is the *effective per-frame (post-CDS)* value delivered to the signal path; RADIANT does not apply a pre/post-CDS √2 scaling. (The unread `read_noise_is_post_cds` toggle was removed CU-077.) |
| All others | Unaffected |

The default convention is: when `read_noise_e_rms` comes from a datasheet, it is already the post-CDS number, so no further scaling is applied.

---

## 5. Temporal vs. Spatial Separation

```
σ_temporal² = signal_shot² + background_shot² + nearfield_shot² + straylight_shot²
            + dark_shot² + gr² + johnson² + flicker_1f² + read² + ktc² + quant²
            + persistence² + glow_shot²

σ_spatial²  = prnu² + dsnu² + clutter²

σ_total² = σ_temporal² + σ_spatial²       (detection regime)
σ_total² = σ_temporal²                    (imaging regime, FPN calibrated out)
```

The user picks `detector.noise_regime ∈ {imaging, detection}`. Both `σ_temporal_e` and `σ_spatial_e` are *always* computed and reported; `σ_total_e` is the one that matches the user's regime. This way the user can re-frame the result without re-running.

---

## 6. The Readout Chain (Canonical Order)

Each step happens in a *domain* (analog or digital), and the noise math depends on the domain. **No re-ordering.**

```
Step  Operation                          Domain    Signal           Noise (per-frame)
────  ─────────────────────────────────  ────────  ───────────────  ───────────────────────
0     Photon flux → electrons            analog    S_e_raw           √S (already, photon shot)
1     TDI accumulation (×N_tdi stages)   analog    × N_tdi           dark × N_tdi (sum of shot)
2     On-chip binning (×M_x × M_y)       analog    × M_x M_y         shot adds; read still 1
3     Well capacity check (FWC)          analog    clip at FWC       saturation_well = CLIPPED
4     Nonlinearity                       analog    polynomial(S)     unchanged
5     Read noise injection               analog    +0                ⊕ read_noise (ONCE)
6     Gain conversion (e- → DN)          boundary  ÷ gain_e_per_dn   ⊕ quantization
7     A/D quantization                   digital   round / clip      already quantized
8     ADC saturation check (2^bits−1)    digital   clip at full      saturation_adc = CLIPPED
9     Off-chip binning (×P_x × P_y)      digital   × P_x P_y         read × √(P_x P_y)
10    Coadds (×K)                        digital   per coadd mode    per coadd mode
11    Final DN                           digital   DN_final          σ_DN
```

Two saturation points: **well** (step 3) and **ADC** (step 8). They are checked independently. A user can have a 100,000 e- well with a 14-bit ADC and 1 e-/DN gain — the well saturates first. Or they can have a 1,000,000 e- well and 8-bit ADC with 100 e-/DN — the ADC saturates first. RADIANT reports both.

**Neither clip is silent** (Rule 17, Gap 65): when either check clips, `ReadoutStage` emits a `UserWarning` naming the exceeded ceiling, the clipped value, and the actionable remedies (integration time / gain / ADC bits / FWC), in addition to setting the `well_status` / `adc_status` stage outputs. Silent clipping cost three scenarios (6.1, 6.2, 8.2) real debugging time — two configs that should produce different SNR instead produced bit-identical clipped results that read as "no effect."

**ADC ↔ well matching (`gain_e_per_dn`, `adc_bits`, `full_well_capacity_e` stay independent).** The ADC full-scale in electrons is `(2^bits − 1) · gain_e_per_dn`. A *matched* ADC digitizes exactly the full well, i.e. `gain_e_per_dn = full_well / 2^bits`. This is an **engineering design target, not a physical law** — unlike emissivity (`ε = 1 − R`, Kirchhoff, which Rule 5 forces to derive), a fielded FPA legitimately runs a **non-matched** ADC (a deep well digitized only in part, or a shallow well oversampled by a high-bit-depth converter). RADIANT therefore keeps the three as independent inputs and does **not** derive gain. Instead it publishes read-only diagnostics so the match is visible: `adc_full_scale_e = (2^bits−1)·gain`, `matched_gain_e_per_dn = full_well / 2^bits`, and `adc_well_match_ratio = adc_full_scale_e / full_well` (1.0 = matched; < 1 the ADC cannot reach the full well; > 1 wasted ADC range). An **egregious** mismatch (ratio outside 0.1–10 — e.g. an 8-bit ADC at 1 e-/DN on a 1 Me- well reaching 0.03 % of it) additionally emits a `UserWarning` pointing at the matched gain; a matched or merely-suboptimal ADC stays quiet.

**Readout architecture dispatch (Gap 117, `docs/archive/Digital_Pixel_Readout_Plan.md`).** `readout.architecture` selects between `analog_well` (the canonical chain above, the default — zero behavior change) and `digital_counting` (digital-pixel ROIC: in-pixel comparator + N-bit counter with charge-subtraction reset). `ReadoutStage` validates the architecture-scoped parameter combination before any physics runs (Rule 16): the counting-only parameters (`counter_bits`, `count_packet_e`, `residue_readout`, `max_count_rate_hz`) are rejected if explicitly set under `analog_well` (over-specification, same posture as Rule 5); under `digital_counting`, `count_packet_e` is required (> 0) and an explicitly set `full_well_capacity_e` is rejected — the effective well is `2^counter_bits · count_packet_e`, so an independent analog full well over-specifies the system (the schema default passes silently). **The counting branch is live (plan Phase 2).** Under `digital_counting` the chain runs with these substitutions, everything upstream unchanged: saturation clips at `min(2^N·Q_pkt, f_max·t_int·Q_pkt)` [e-] through the same `check_well_saturation`, with `readout.saturation_mechanism` (`rollover` | `dead_time` | `none`) published alongside `well_status`; the noise budget swaps `quantization` → `counting_quantization` (packet/√12 bare, residue-ADC LSB/√12 with residue readout) and `ktc_reset` → `packet_reset` (√n_counts × σ_kTC, same CDS gate) — still at most 16 terms; DN follows ruling D2 (residue on: combined word at gain Q_pkt/2^M e-/DN; off: bare counter at Q_pkt e-/DN, published as the effective `gain_e_per_dn`); the ADC saturation check and the ADC↔well match diagnostics are suppressed (the counter *is* the ADC); the published `full_well_capacity_e` stage output carries the counting bound so every downstream well consumer (fill fraction, well margin, dynamic range, GUI banner) sees one consistent saturation signal. New stage outputs: `architecture`, `counts` [-], `count_packet_e` [e-], `effective_well_e` [e-], `saturation_mechanism`. Physics modules: `readout/counting_well.py`, `readout/counting_quantization.py`.

**Up/down counting (plan Phase 4, rulings D6/D7).** `readout.counting_mode = "up_down"` turns the counter into a signed modulo accumulator: increment during the scene phase, decrement during a reference phase (`readout/updown_differential.py`). The reference integrates the chain's own background term (sub-pixel/point-source regimes, D6) or a user-specified rate (`reference_rate_e_per_s`, extended-scene fallback); the down-phase duration is `reference_integration_s` (unset ⇒ equal phases, D7). Counter wrap during the up phase is unwound by the down phase, so the capacity bound moves from rollover to the signed differential `|ΔQ| ≤ 2^(N−1)·Q_pkt` (`saturation_mechanism = "differential_overflow"`); the dead-time ceiling applies per phase. The mean cancels but the noise does not: the budget gains `reference_shot` = √Q_down (17 terms), `packet_reset` accrues over both phases' trips, and the counting-chain read is paid once per phase (×√2). DN is the signed differential at the D2 gain; `signal_e_final` (the SNR numerator) stays the scene-phase target signal. Extra outputs: `counting_mode`, `differential_e` [e-], `reference_charge_e` [e-], `reference_integration_s_used` [s].

The "read noise injection happens ONCE" rule is the reason TDI gets a √N_tdi SNR improvement: the signal accumulates as N_tdi (analog) but the read noise is added once at the end. If anyone tries to add read noise before TDI accumulation, the chain has a sign of degradation and the test suite catches it.

---

## 7. TDI

```
S_tdi   = N_tdi · S_per_stage
σ_dark² = N_tdi · σ_dark_per_stage²       (independent dark events sum)
σ_read  = σ_read                          (single readout)
```

**Well check** runs after TDI accumulation. A user with a 50,000 e- well, a 10,000 e- per-stage signal, and N_tdi = 8 will saturate at stage 5; the framework returns `saturation_well = CLIPPED` and clamps signal to FWC.

**CTE loss**: charge transfer efficiency `cte_per_transfer` (default 0.99999). Signal scales by `cte^(N_tdi · n_transfers_per_stage)`, where `n_transfers_per_stage = 1` for area arrays in TDI mode. Reported in `noise_terms["cte_loss"]` as a *signal* loss, not a noise term.

**TDI misalignment** (yaw error, velocity mismatch) is handled in the spatial PSF cascade as `mtf_tdi_misalign` per RADIANT_Spatial_Complete.md §9. The detector module records the misalign value but does not apply it.

---

## 8. Binning

### 8.1 On-chip (analog, before readout)

```
S_binned       = M_x · M_y · S_pixel
σ_dark_binned  = √(M_x · M_y) · σ_dark
σ_read_binned  = σ_read                   (single readout, like TDI)
σ_quant        = LSB / √12                (still LSB-bound)
```

The combined charge is *one* charge packet read out by the ROIC; saturation happens against the **summing well capacity**, which may differ from per-pixel FWC. If `summing_well_capacity_e` is not specified, it defaults to `M_x · M_y · pixel_FWC` with a logged warning.

### 8.2 Off-chip (digital, after readout)

```
S_binned       = P_x · P_y · S_pixel
σ_read_binned  = √(P_x · P_y) · σ_read    (each pixel read independently)
```

Each pixel saturates *independently*; binning happens after the per-pixel ADC clip. Off-chip binning never improves saturation headroom.

### 8.3 Spatial effect

Both binning modes change the *effective pixel pitch* on the FPA. The framework constructs an "effective detector" with `pitch_eff = (M_x · P_x · pitch_x, M_y · P_y · pitch_y)` and the detector MTF is recomputed against the effective pitch. This effective pitch is what the spatial cascade uses for the pixel-aperture sinc.

---

## 9. Coadds

```python
class CoaddMode(StrEnum):
    SUM = "sum"
    AVERAGE = "average"
    MEDIAN = "median"
```

| Mode | Signal | Read noise | Other temporal | FPN |
|------|--------|------------|----------------|-----|
| SUM | × K | × √K | × √K | × K |
| AVERAGE | unchanged | / √K | / √K | unchanged |
| MEDIAN | unchanged | × √(π/(2K)) | × √(π/(2K)) | unchanged |

Each coadded frame **saturates independently** at well and ADC — coadds offer no saturation relief. The framework tracks per-frame saturation and warns if any frame saturated even when the average looks unsaturated.

Persistence (term 15) accumulates across coadds: `prior_signal_e` for coadd `k` is the signal of coadd `k−1`. The framework propagates this internally.

---

## 10. Interaction Matrix

TDI × on-chip binning × off-chip binning × coadds can all be active simultaneously. The total signal scaling is:

```
S_final = N_tdi · M_x · M_y · P_x · P_y · K_signal · S_per_pixel_per_stage
```

where `K_signal = K` for SUM mode and `K_signal = 1` for AVERAGE/MEDIAN.

Noise term scalings (multiply each term in §4 by the factor in the matrix):

| Term | × N_tdi | × M_x M_y on-chip | × P_x P_y off-chip | × K coadds (SUM) |
|------|---------|-------------------|--------------------|------------------|
| `signal_shot` | √N | √(MN) | √(PN) | √K |
| `background_shot` | √N | √(MN) | √(PN) | √K |
| `dark_shot` | √N | √(MN) | √(PN) | √K |
| `gr_noise` | √N | √(MN) | √(PN) | √K |
| `johnson_noise` | √N | √(MN) | √(PN) | √K |
| `flicker_1f` | depends (correlated within readout) | √(MN) | √(PN) | √K |
| `read_noise` | × 1 | × 1 | × √(PN) | × √K |
| `ktc_reset_noise` | × 1 | × 1 | × √(PN) | × √K |
| `quantization_noise` | × 1 | × 1 | × √(PN) | × √K |
| `prnu` | × N | × MN | × PN | × K (SUM); × 1 (AVG) |
| `dsnu` | × N | × MN | × PN | × K (SUM); × 1 (AVG) |
| `clutter` | × N | × MN | × PN | × K (SUM); × 1 (AVG) |
| `persistence_noise` | √N | √(MN) | √(PN) | grows w/ K |
| `glow_shot` | √N | √(MN) | √(PN) | √K |

The `flicker_1f` row deliberately uses words because the right scaling depends on whether the integration time is increased (`× N`) or the rate is increased (`× 1`); the framework picks based on which knob the user used and records the choice.

For AVERAGE coadd mode, divide every column "× K coadds" entry by K (since signal stays unchanged but noise reduces).

---

## 11. Parameter Inventory

**44 parameters as shipped** — 27 in the `detector.*` namespace (owned by
`DetectorStage`) and 17 in `readout.*` (owned by `ReadoutStage`). The original
design pass listed ~54 parameters all under `detector.*`, but the built system
splits gain/ADC/well/TDI/binning/coadd controls into `readout.*` (they act in
the readout chain, §6) and never implemented ~20 of the designed names. This
section is the authoritative, reconciled inventory (verified against
`detector/_schema.py` and `readout/_schema.py`, 2026-07-12).

### 11.1 `detector.*` — 27 parameters

**QE (4):** `qe_value`, `qe_table_path`, `qe_temperature_coeff_per_K`,
`qe_temperature_ref_K`.

**Pixel geometry (5):** `pixel_pitch_x_um`, `pixel_pitch_y_um`, `fill_factor`,
`charge_diffusion_length_m`, `n_pixels_cross`.

**Dark current (4):** `dark_rate_e_per_s`, `dark_activation_energy_eV`,
`dark_reference_temperature_K`, `detector_temperature_K`.

**Other detector noise (9):** `gr_factor`, `r0a_ohm_cm2`, `flicker_K`,
`flicker_f_low_hz`, `flicker_f_high_hz`, `persistence_fraction`,
`persistence_tau_s`, `prior_signal_e`, `glow_e_per_s`.

**Fixed-pattern / regime (4):** `prnu_pct`, `dsnu_e_rms`, `clutter_sigma`,
`noise_regime`.

**IPC (1):** `ipc_coupling`.

### 11.2 `readout.*` — 26 parameters

**Read / CDS (4):** `read_noise_e_rms`, `cds_enabled`,
`node_capacitance_F`, `electronics_sigma_um`.

**ADC and gain (2):** `gain_e_per_dn`, `adc_bits`.

**Well (1):** `full_well_capacity_e` (analog_well only — rejected if
explicitly set under `digital_counting`).

**Architecture / digital-pixel counting (9, Gap 117 — see §6 dispatch):**
`architecture`, `counter_bits`, `count_packet_e`, `residue_readout`,
`max_count_rate_hz`, plus the Phase 4 up/down group `counting_mode`,
`reference_source`, `reference_rate_e_per_s`, `reference_integration_s`.
The counting-only parameters are rejected if explicitly set under
`analog_well`; the reference trio likewise under `counting_mode = "up"`.

**TDI (3):** `n_tdi`, `tdi_misalign_pixels`, `tdi_mode`.

**Binning (4):** `binning_x_onchip`, `binning_y_onchip`, `binning_x_offchip`,
`binning_y_offchip`.

**Coadds (2):** `n_coadds`, `coadd_mode`.

**Timing (1):** `frame_period_s` (previously omitted from this inventory —
the pre-Gap-117 heading said 16 while the schema held 17).

### 11.3 Designed but not implemented

The following design-pass names have **no ParameterDef** in either schema and no
consuming code: `qe_input`, `qe_material`, `qe_file`, `qe_cutoff_um`,
`qe_subbands`, `pixel_shape`, `summing_well_capacity_e`, `nonlinearity_coeffs`,
`adc_full_scale_dn`, `bias_offset_dn`, `cte_per_transfer`,
`n_transfers_per_stage`, `tdi_velocity_match_pct`, `cds_1f_suppression`,
`bad_pixel_fraction`, `cosmic_ray_flux`, `detector_material`, `rolling_shutter`,
`ipc_kernel_file`. Their corresponding models (CTE loss §7, summing-well
capacity §8.1, ADC full-scale/bias §6, cosmic-ray statistic §4) are therefore
design-target: the sections describing them stand as intent, not shipped
behavior. `dark_current_e_per_s` in the design pass is the shipped
`dark_rate_e_per_s`.

---

## 12. The `DetectorStage` and `ReadoutStage`

Per RADIANT_Signal_Chain_Architecture.md, these are stages 6 and 7. RADIANT keeps them as separate stage objects (so the architecture document's stage list is preserved) but the documentation is unified.

- `DetectorStage`: applies QE, computes per-pixel signal/dark/glow electrons, builds the photon-shot family, assembles the spatial MTF terms (pixel aperture, charge diffusion, IPC), and registers them on the chain state.
- `ReadoutStage`: runs the canonical readout chain (§6) starting from the per-pixel electron rate, builds the read-noise / ktc / quantization / FPN terms, applies TDI, binning, coadds, and the two saturation checks, and emits the final `DetectorState`.

The split exists so that a user studying spatial behavior alone (e.g., "what does the detector MTF look like?") can stop after `DetectorStage` without paying for the readout chain.

---

## 13. Validation

| Check | Bound |
|-------|-------|
| QE(λ) ∈ [0, 1] | hard |
| `pixel_pitch_x_um > 0`, `pitch_y > 0` | hard |
| `0 ≤ fill_factor ≤ 1` | hard |
| `n_tdi ≥ 1` | hard |
| `summing_well_capacity_e ≥ pixel_FWC` | soft warn if not |
| Each noise term ≥ 0 | hard |
| `gain_e_per_dn > 0`, `adc_bits ≥ 8` | hard |
| If `noise_regime = imaging`, FPN terms still computed but not in σ_total | soft (informational) |

---

## 14. Out of Scope for v1

- Optical crosstalk modeling (D17, deferred).
- ADC INL/DNL (R9, deferred).
- Live multi-frame state (the chain is stateless; persistence uses user-supplied prior signal).
- True rolling-shutter readout simulation (snapshot assumed; flag reserved).
- Power supply noise, clock feedthrough (deferred to electronics tools).

---
