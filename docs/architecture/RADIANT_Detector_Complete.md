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

Parameter types, defaults, units, and bounds are the canonical [Parameter Reference](../guides/parameter_reference.md) (auto-generated from the schema — the single source of truth, Rule 27). The pixel-geometry parameters are `detector.pixel_pitch_x_um`, `detector.pixel_pitch_y_um` (defaults to `pitch_x` for a square pixel), `detector.fill_factor`, and `detector.charge_diffusion_length_m`. The **pixel sampling phase** (`detector.pixel_phase_mode` ∈ {average, centered, worst_case, specified} + `detector.pixel_phase_x/y` in fractions of a pitch, Gap 129) is owned here because the grid is the detector's and the box is defined by pitch and fill factor; it is *evaluated* by `PlatformStage` (Rule 9) — see RADIANT_Spatial_Complete.md §6.1.

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
#### Each noise term reports the scaling it received (Gap 133)

`stage_outputs["readout"]["noise_scaling"]` carries, per term, the factor
applied on each axis — TDI, on-chip binning, off-chip binning, co-add — and the
**correlation class that chose it**. Rendered:

```
clutter      spatial            TDI x4  bin x1/x1  coadd x8     [scene-correlated …]
prnu         spatial            TDI x2  bin x1/x1  coadd x8     [different physical pixels …]
signal_shot  shot               TDI x2  bin x1/x1  coadd x2.828
read_noise   read_like          TDI x1  bin x1/x1  coadd x2.828 [injected once after …]
flicker_1f   transfer_function  TDI x2  bin x1/x1  coadd —      [the Dirichlet comb …]
```

Why it exists: CU-381 was invisible for two releases because the co-added 1/f
number was simply *smaller than it should be*, with nothing to say what had
been applied. The scaling rests on a correlation judgement — is this the same
fluctuation in every frame, or an independent draw? — made in code and reported
nowhere, while the person best placed to notice it is wrong is the analyst
reading the budget.

Two properties make the record trustworthy rather than decorative:

**The factors are measured, not described.** Each is obtained by pushing `1.0`
through the *same* helper the stage applies to the real value, so it is the
factor actually applied rather than a second implementation that could drift. A
test pins `reported_factor × raw == scaled` for every multiplicative term,
under both TDI modes and all three co-add modes.

**`None` is not 1.0.** A dash means *no factor was applied on that axis*, which
is different from a factor of one. `flicker_1f` has no co-add factor at all
since CU-381 — its co-add behaviour is the Dirichlet comb, a frequency-dependent
crossover with no single correct exponent — and the record says so in words
instead of inventing a number. The two Gap-117 counting terms likewise report no
TDI or on-chip factor, because `n_counts` already carries both and a factor
there would double-count. That classification was **wrong in this module's
first version**, and the reconciliation test caught it.

#### Derived quantities are echoed with units and provenance (Gap 134)

`stage_outputs["performance"]["derived_quantities"]` is a tuple of
`DerivedQuantity(name, value, unit, source)` — every value RADIANT worked out
for itself, never a bare number. 18 rows on a typical MWIR run: the étendue
cone, pixel solid angle, effective f/# and pupil, collecting area, IFOV in both
axes, band-mean τ_atm and τ_opt, frame rate and duty cycle, the well (**and
which well it is** — counter-derived or analog), the three σ values, and the
per-pixel dark rate **with a note when it was converted from a density**.

The review's reasoning: *"anything RADIANT computed from user input is exactly
what an external model will disagree about."* Its worked case was `Omega_cone`,
where the exact étendue form against the paraxial `π/(4N²)` — 18.4 % apart at
f/1 — accounted for an entire warm-optics discrepancy and was reachable only by
digging in `stage_outputs`. That row now names the convention in its own
`source` string.

Two quantities were genuinely missing rather than merely buried, and each got
its own module (Rule 19): `performance/ifov.py` — which
`performance/johnson_criteria.py` already *consumed* while the chain never
published it — and `performance/band_mean.py`, the unweighted band mean
scenario 3.2 had to compute by hand. The mean is unweighted deliberately: it is
what an external model's "band transmittance" almost always means, it assumes
nothing about the source, and a weighted figure would silently bake in a
spectrum the caller did not choose.

Four rows from the CU-387 scenario triage fold in here, having been one
complaint in four costumes: an effective integration time, a scalar band-mean
τ, a first-class total-noise value, and an MTF budget reachable only by
string-parsing `*_x`/`*_y` suffixes.

#### The background pedestal is reported as a composition (Gap 132)

`stage_outputs["performance"]["background_composition"]` decomposes the
no-target pedestal into `nearfield` / `scene` / `dark` / `stray` / `glow`, each
as an absolute charge **and a share of the total**, with the dominant
contributor named and a `zero_terms()` report.

It computes no physics — it is a pure view over charges the detector stage
already published, deliberately, because anything it derived itself would be a
second opinion on a number the chain owns. `test_background_composition_chain`
pins that it reconciles exactly against those terms.

Why it exists, in the external review's own ranking: it was placed *above* the
review's top defect finding. CU-380 — warm-optics emission evaluating to
identically zero while the term appeared enabled — cost two releases and an
outside reconciliation, and one proportioned line would have shown it. Measured
on the shipped templates after CU-380's warm trains landed:

| template | dominant | nearfield share |
|---|---|---|
| `geo_lwir_staring` | `nearfield` | 100.00 % |
| `sda_space_to_space` | `nearfield` | 73.17 % (dark 26.83 %) |
| `ground_to_air_mwir_detection` | `scene` | 34.43 % |

Three conventions worth knowing: shares are of the **pedestal**, not of signal
(a share of signal would move when the target changes, which is useless for
"where is my background from"); a zero total gives **zero shares, not NaN**,
because a cold-shielded configuration is well-defined rather than undefined;
and `dominant` is `None` at a zero total rather than an arbitrary winner among
five zeros.

#### Noise-equivalent irradiance is reported in photon units (Gap 135)

`stage_outputs["performance"]` now carries `nei_ph_s_cm2` and `nei_w_cm2`, plus
the `photon_energy_j` / `lambda_eff_um` pair that converts between them.

The photon-unit NEI itself is not new — `noise_equivalent_irradiance_ph_s_cm2`
landed with Gap 45 for scenario 2.1 and has been tested ever since. It was
simply **never wired into the chain**, so nothing could reach it from a result.
Wiring it is most of what the review's "offer photon-unit NER/NEI" asked for.

The conversion to watts is the part worth stating. It needs a photon energy and
therefore an effective wavelength, which the review's units table named as the
hidden step in every such conversion. RADIANT computes it rather than assuming
it (`performance/effective_photon_energy.py`):

```
E_eff = ∫ Φ(λ)·QE(λ)·(hc/λ) dλ  /  ∫ Φ(λ)·QE(λ) dλ
```

— the **detected-photon-weighted mean energy**, which is exactly the number that
turns a detected photon rate into the radiant power that produced it. Two
choices in that formula are deliberate:

- **Weighted by the *detected* flux, not the incident flux.** The quantity being
  converted counts photons that produced electrons, so photons that did not are
  not in the average. A QE sloping across the band therefore moves `E_eff`,
  which is why this is not the band centre.
- **An energy average, not a wavelength average.** `⟨hc/λ⟩ ≠ hc/⟨λ⟩`, and by
  Jensen the energy average is the larger, so `lambda_eff_um` — back-solved as
  `hc/E_eff` — is *shorter than the flux-weighted mean wavelength*. On the
  shipped MWIR example: flux-weighted mean 4.4849 µm, `lambda_eff` 4.4500 µm.
  Note both sit above the 4.25 µm band midpoint, because a 300 K source's
  spectrum rises toward 5 µm — `lambda_eff` is not required to be below the
  midpoint, only below the flux-weighted mean.

#### Dark current may be declared as a density (Gap 135)

`detector.dark_rate_e_per_s` is the chain-canonical form — electrons per second
per pixel. But every HgCdTe datasheet, and every external radiometric model
RADIANT gets compared against, publishes a **current density** instead. Both of
Gap 123's predictive laws are published that way too.

So `detector.dark_current_density_a_per_cm2` is a second door onto the *same*
measured quantity, converted once at
`dark_current.dark_rate_e_per_s_from_density` as `rate = J · A_pixel / q`. The
pixel cell area (`pitch_x · pitch_y`) is used, not the optically active area:
dark generation scales with junction area, and fill factor describes optical
collection.

| | |
|---|---|
| canonical unit | `A/cm2` — the datasheet convention, the unit both predictive laws publish, and the unit the conversion helper already took. Same precedent as `r0a_ohm_cm2`. |
| `A/m2` entry | accepted via the unit layer (`set(..., unit="A/m2")`, factor 1e-4). The m²/cm² choice is a silent 10⁴ trap when converted by hand — removing that is the point of the gap. |
| default | `0.0` = unset, so the rate door stays in force and no existing result moves. |
| both set | **rejected as over-specification.** They are two spellings of one quantity, so RADIANT will not silently prefer one — the same posture the predictive branch takes, and Rule 5's. A config that already declares a rate must clear it (`Sensor.reset`) before entering a density. |
| under a predictive `dark_model` | rejected, exactly as an explicit rate is: the law derives the density itself. |
| Arrhenius | the density is a measured value at `dark_reference_temperature_K`, so it scales identically to a rate — it is converted first, then fed the same `DarkCurrent` path. |

The resolved per-pixel rate is published at
`stage_outputs["detector"]["dark_rate_e_per_s"]` on both doors, so a
density-declared run is inspectable (Rule 16) and the converted number is
visible rather than implicit — which is what [[Gap 134]] asks for generally.

| 8 | `flicker_1f` | 1/f flicker in detector + ROIC | `σ_1f² = ∫ S(f)·\|H_box\|²·\|D_K\|²·\|H_ref\|² df` (CU-381) | Long integrations, low signal, co-added stacks | `flicker_K`, `flicker_corner_hz`, `flicker_f_low` / `_f_high` (overrides) |

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

**Gap 120 redefinition (ratified D2, 2026-09-06).** `prnu_pct` / `dsnu_e_rms`
are the **pre-correction** dispersions. Under `calibration.scheme = "none"`
(the default) they enter the budget exactly as above — today's behavior.
Under an active NUC scheme (`one_point` / `two_point`) the detector stage
suppresses terms 12–13 from the raw budget and emits them as
`stage_outputs["detector"]["precal_prnu_pct"]` / `["precal_dsnu_e_rms"]`;
CalibrationStage consumes them and the *post-NUC residual* re-enters
post-readout as the `CALIBRATION_TERMS` family (`nuc_residual`,
`gain_drift`, `offset_drift` — `RADIANT_Calibration.md`). Exactly one of
the two representations is ever live — no double counting, contract-tested
in `calibration/tests/test_detector_handoff.py`.

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
| `flicker_1f` | **Unaffected for now.** The transfer model carries the reference high-pass `\|H_ref(f)\|² = 4sin²(πf·t_sep)` that CDS and `counting_mode: up_down` produce, and it is unit-tested, but it is **not yet wired** from the readout timing — an open CU-381 checklist item. Until it is, `reference_separation_s = 0`, the un-referenced and conservative case: it keeps the low-frequency power a reference would have suppressed. (A `cds_1f_suppression` 0.7 factor was documented but never implemented; removed CU-077.) |
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

**What fills the well (CU-350).** `total_well_e` — the quantity the well check compares against the capacity and `well_fill_fraction` divides by it — is every electron that physically lands in the pixel during the integration:

$$Q_{\text{well}} = \left[S + Q_{\text{dark}} + Q_{\text{glow}} + Q_{\text{nf}} + Q_{\text{stray}} + \left(Q_{\text{bg}}\right)_{\text{point-source only}}\right] \cdot N_{\text{TDI}} \cdot m_{x}m_{y}$$

all terms in e-. TDI stages accumulate independently and each on-chip binned pixel contributes its own charge, so every term carries the same `N_TDI · m_x · m_y` factor. The near-field (warm-optics self-emission, `nearfield_e`) and stray-light (`stray_e`) terms are never folded into `signal_e` by an upstream stage, so they enter in **every** regime; the background pedestal `background_e` is added **only** in the point-source regime, where `signal_e` is the target-only excess (Gap 73) — in the extended and sub-pixel regimes the background is already inside `signal_e` and must not be double-counted. The invariant is that the well check and the noise budget describe the same pixel: any charge whose shot noise is counted in the budget also occupies the well. The counting branch below applies the identical sum against its counting bound.

**Neither clip is silent** (Rule 17, Gap 65): when either check clips, `ReadoutStage` emits a `UserWarning` naming the exceeded ceiling, the clipped value, and the actionable remedies (integration time / gain / ADC bits / FWC), in addition to setting the `well_status` / `adc_status` stage outputs. Silent clipping cost three scenarios (6.1, 6.2, 8.2) real debugging time — two configs that should produce different SNR instead produced bit-identical clipped results that read as "no effect."

**ADC ↔ well matching (`gain_e_per_dn`, `adc_bits`, `full_well_capacity_e` stay independent).** The ADC full-scale in electrons is `(2^bits − 1) · gain_e_per_dn`. A *matched* ADC digitizes exactly the full well, i.e. `gain_e_per_dn = full_well / 2^bits`. This is an **engineering design target, not a physical law** — unlike emissivity (`ε = 1 − R`, Kirchhoff, which Rule 5 forces to derive), a fielded FPA legitimately runs a **non-matched** ADC (a deep well digitized only in part, or a shallow well oversampled by a high-bit-depth converter). RADIANT therefore keeps the three as independent inputs and does **not** derive gain. Instead it publishes read-only diagnostics so the match is visible: `adc_full_scale_e = (2^bits−1)·gain`, `matched_gain_e_per_dn = full_well / 2^bits`, and `adc_well_match_ratio = adc_full_scale_e / full_well` (1.0 = matched; < 1 the ADC cannot reach the full well; > 1 wasted ADC range). An **egregious** mismatch (ratio outside 0.1–10 — e.g. an 8-bit ADC at 1 e-/DN on a 1 Me- well reaching 0.03 % of it) additionally emits a `UserWarning` pointing at the matched gain; a matched or merely-suboptimal ADC stays quiet.

**Readout architecture dispatch (Gap 117, `docs/archive/Digital_Pixel_Readout_Plan.md`).** `readout.architecture` selects between `analog_well` (the canonical chain above, the default — zero behavior change) and `digital_counting` (digital-pixel ROIC: in-pixel comparator + N-bit counter with charge-subtraction reset). `ReadoutStage` validates the architecture-scoped parameter combination before any physics runs (Rule 16): the counting-only parameters (`counter_bits`, `count_packet_e`, `residue_readout`, `max_count_rate_hz`) are rejected if explicitly set under `analog_well` (over-specification, same posture as Rule 5); under `digital_counting`, `count_packet_e` is required (> 0) and an explicitly set `full_well_capacity_e` is rejected — the effective well is `2^counter_bits · count_packet_e`, so an independent analog full well over-specifies the system (the schema default passes silently). **The counting branch is live (plan Phase 2).** Under `digital_counting` the chain runs with these substitutions, everything upstream unchanged: saturation clips at `min(2^N·Q_pkt, f_max·t_int·Q_pkt)` [e-] through the same `check_well_saturation`, with `readout.saturation_mechanism` (`rollover` | `dead_time` | `none`) published alongside `well_status`; the noise budget swaps `quantization` → `counting_quantization` (packet/√12 bare, residue-ADC LSB/√12 with residue readout) and `ktc_reset` → `packet_reset` (√n_counts × σ_kTC, same CDS gate) — still at most 16 terms; DN follows ruling D2 (residue on: combined word at gain Q_pkt/2^M e-/DN; off: bare counter at Q_pkt e-/DN, published as the effective `gain_e_per_dn`); the ADC saturation check and the ADC↔well match diagnostics are suppressed (the counter *is* the ADC); the published `full_well_capacity_e` stage output carries the counting bound so every downstream well consumer (fill fraction, well margin, dynamic range, GUI banner) sees one consistent saturation signal. New stage outputs: `architecture`, `counts` [-], `count_packet_e` [e-], `effective_well_e` [e-], `saturation_mechanism`. Physics modules: `readout/counting_well.py`, `readout/counting_quantization.py`.

**Up/down counting (plan Phase 4, rulings D6/D7).** `readout.counting_mode = "up_down"` turns the counter into a signed modulo accumulator: increment during the scene phase, decrement during a reference phase (`readout/updown_differential.py`). The reference phase is a **real second integration of the same pixel through the same optics, defocused**, repeated many times within an integration period (D6 clarified by owner ruling 2026-09-11, CU-351): defocus spreads the concentrated target while the standing pedestal survives, so Q_down integrates the chain's own background term (sub-pixel/point-source regimes) or a user-specified rate (`reference_rate_e_per_s`, extended-scene fallback) **plus dark, glow, near-field (warm-optics) emission, and stray light under both reference sources** — the differential cancels the full non-signal pedestal, which is what the reference phase exists to do. The down-phase duration is `reference_integration_s` (unset ⇒ equal phases, D7). Counter wrap during the up phase is unwound by the down phase, so the capacity bound moves from rollover to the signed differential `|ΔQ| ≤ 2^(N−1)·Q_pkt` (`saturation_mechanism = "differential_overflow"`); the dead-time ceiling applies per phase. The mean cancels but the noise does not: the budget gains `reference_shot` = √Q_down (17 terms), `packet_reset` accrues over both phases' trips, and the counting-chain read is paid once per phase (×√2). DN is the signed differential at the D2 gain; `signal_e_final` (the SNR numerator) stays the scene-phase target signal. Extra outputs: `counting_mode`, `differential_e` [e-], `reference_charge_e` [e-], `reference_integration_s_used` [s].

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
| `flicker_1f` | √N analog / × N digital | √(MN) | √(PN) | **not a factor — see §9.1** |
| `read_noise` | × 1 | × 1 | × √(PN) | × √K |
| `ktc_reset_noise` | × 1 | × 1 | × √(PN) | × √K |
| `quantization_noise` | × 1 | × 1 | × √(PN) | × √K |
| `prnu` | × N | × MN | × PN | × K (SUM); × 1 (AVG) |
| `dsnu` | × N | × MN | × PN | × K (SUM); × 1 (AVG) |
| `clutter` | × N | × MN | × PN | × K (SUM); × 1 (AVG) |
| `persistence_noise` | √N | √(MN) | √(PN) | grows w/ K |
| `glow_shot` | √N | √(MN) | √(PN) | √K |

#### 9.1 Why `flicker_1f` has no co-add column (CU-381)

The co-add axis is not a scale factor for 1/f noise. It is the **Dirichlet comb**
`|D_K(f)|² = sin²(πfKt_frame)/sin²(πft_frame)` inside the transfer integral
(`radiant.readout.flicker_transfer`), and the correlation it produces is a
*function of frequency*: coherent (`K²` in variance) below `1/T_total`,
incoherent (`K`) far above. No single exponent is correct, so none is applied.
The measured effective exponent on K is ~0.92 for a 1 ms/2 ms/200 Hz case —
between √K and fully correlated, and derived rather than chosen.

The TDI column, by contrast, *is* a factor, and it differs by TDI mode for a
physical reason: analog TDI reads a **different physical pixel** at each stage,
and independent pixels have independent 1/f (√N); digital TDI re-reads the
**same** pixel, so it is one process adding coherently (× N). This is the rule
PRNU/DSNU already follow. Applying the co-add correlation blanket-fashion across
every axis — the tempting shortcut — would over-charge analog TDI by √N.

**Superseded model.** Before CU-381 the term was `σ_1f = √(K·ln(f_high/f_low))`
over a band from two free parameters, scaled × √K on co-add. That was wrong in
three coupled directions: no corner-frequency cut (64–170 % overestimate
measured at 30–120 Hz), a band decoupled from every timing quantity in the model
(a 100 µs and a 100 ms frame got the identical σ), and √K averaging of power
that cannot average (up to a factor √K low at the stack level). The first and
third pull in opposite directions and partially cancelled, which is why the term
looked plausible through v0.2.0 and v0.3.0.

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

### 11.1 `detector.*` — 30 parameters

**QE (4):** `qe_value`, `qe_table_path`, `qe_temperature_coeff_per_K`,
`qe_temperature_ref_K`.

**Pixel geometry (5):** `pixel_pitch_x_um`, `pixel_pitch_y_um`, `fill_factor`,
`charge_diffusion_length_m`, `n_pixels_cross`.

**Pixel sampling phase (3, Gap 129):** `pixel_phase_mode`, `pixel_phase_x`,
`pixel_phase_y`.

**Dark current (4):** `dark_rate_e_per_s`, `dark_activation_energy_eV`,
`dark_reference_temperature_K`, `detector_temperature_K`.
**Dark current (6):** `dark_model`, `dark_cutoff_um`, `dark_rate_e_per_s`,
`dark_activation_energy_eV`, `dark_reference_temperature_K`,
`detector_temperature_K`.

`dark_model` selects the dark-current source (Gap 123). `measured` (default)
uses `dark_rate_e_per_s` at `dark_reference_temperature_K` with optional
Arrhenius scaling via `dark_activation_energy_eV` — the historical behaviour,
bit-identical. `rule07` / `rule22` derive the per-pixel rate from the published
empirical HgCdTe p-on-n laws J(λc, T) — Tennant et al., J. Electron. Mater. 37,
1406 (2008) and M. Zandian, J. Electron. Mater. 52, 7095 (2023) respectively —
using `dark_cutoff_um`, `detector_temperature_K`, and the full pixel cell area
(`pixel_pitch_x_um · pixel_pitch_y_um`; dark generation scales with junction
area, so `fill_factor` is deliberately not applied). The laws live in
`detector/rule07.py` and `detector/rule22.py` (one law, one module); the
published A/cm² output crosses to the canonical e⁻/s/pixel rate exactly once,
in `dark_current.dark_rate_e_per_s_from_density`. Selecting a predictive model
while explicitly setting `dark_rate_e_per_s` or `dark_activation_energy_eV`
is rejected as an over-specified dark budget (`DetectorValidationError`);
evaluations outside a law's published fit range (Rule 07: λe·T ∈ [400, 1700]
µm·K, T ≥ 77 K; Rule 22: λc ∈ [1.6, 17] µm, T ∈ [20, 330] K) surface a
structured `dark_model_note` stage output (CU-081 pattern), and the derived
`dark_rate_e_per_s` and `dark_current_density_a_per_cm2` are stored as
diagnostics in `stage_outputs["detector"]`. Both laws describe HgCdTe only —
they say nothing about InSb, InGaAs, Si, or microbolometers.

**Other detector noise (11):** `gr_factor`, `r0a_ohm_cm2`, `flicker_K`,
`flicker_corner_hz`, `flicker_f_low_hz`, `flicker_f_high_hz`, `persistence_fraction`,
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
