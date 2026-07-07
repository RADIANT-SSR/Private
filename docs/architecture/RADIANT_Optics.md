# RADIANT Optics

**Status**: Authoritative — first design pass, unified
**Scope**: All optical-train physics between the entrance pupil and the focal plane. Aperture, wavefront, transmission, nearfield (warm-optics) emission, stray light, and the étendue bookkeeping that ties them together.
**Sister documents**: RADIANT_Conventions.md, RADIANT_Parameter_System.md, RADIANT_Signal_Chain_Architecture.md, RADIANT_Source_Target_System.md, RADIANT_Atmosphere.md, RADIANT_Spatial_Complete.md

---

## 1. Design Philosophy

The optics module has one job: **deliver an `OpticsState` to the chain**. Five guiding rules:

1. **One contract, many input depths.** A user may specify the optics by a scalar transmission and a Strehl ratio, or by a full element-by-element prescription with measured OPD maps and per-element temperatures. All inputs flow into the same `OpticsState`. The downstream chain is identical.
2. **Kirchhoff is enforced for elements.** A user supplies reflectance and (for transmissive elements) transmittance. Emissivity is **derived**: ε = 1 − R for mirrors, ε = 1 − T − R for transmissive elements (with R defaulting to a small number when unspecified). Emissivity is never specified independently for a physical surface. The one sanctioned exception is the LUMPED pseudo-element (`optics.scalar_emissivity`, §5.1): a lump stands in for an entire train whose energy balance is not derivable from net transmission, so the user may declare it there — still bounded by ε + τ ≤ 1.
3. **Signal etendue and nearfield solid angle are different things.** The signal path uses the single invariant AΩ. Nearfield emission uses a *per-element* Ω that depends on each element's size and distance from the FPA. They are computed separately, named separately, and never conflated.
4. **Stray light adds noise, not signal.** Stray light contributes electrons (and therefore shot noise) to every pixel uniformly, but is not part of the signal that NIIRS or detection metrics measure. It is reported in the noise budget.
5. **Pupil → PSF lives elsewhere.** The optics module produces the pupil function (or hands the diffraction module enough to build one). The PSF, MTF, and EE all live in `RADIANT_Spatial_Complete.md`. Optics owns the pupil; spatial owns the focal plane.

---

## 2. The `OpticsState` Contract

```python
@dataclass(frozen=True)
class OpticsState:
    """Everything the chain needs to know about the optical train."""

    # ---- Identification & provenance --------------------------------------
    transmission_input_mode: TransmissionInputMode  # SCALAR | SPECTRAL | TELESCOPE_PLUS_FILTER
                                                    # | KEY_ELEMENTS | FULL_PRESCRIPTION
    stray_light_input_mode: StrayLightInputMode     # VEILING_GLARE | ABSOLUTE_IRRADIANCE
                                                    # | SPECTRAL_FILE | PST_FILE
    derivation_chain: tuple[str, ...]

    # ---- Pupil --------------------------------------------------------------
    pupil: PupilDescription                  # geometry + apodization + WFE
    aperture_area_m2: float                  # A_collect (clear area, not D²·π/4)
    f_number: float
    focal_length_m: float

    # ---- Throughput ---------------------------------------------------------
    transmission: SpectralData               # τ_opt(λ), dimensionless [0,1]
    elements: tuple[OpticalElement, ...]     # populated for KEY_ELEMENTS / FULL_PRESCRIPTION
                                             # synthesized otherwise (single virtual element)

    # ---- Nearfield (warm optics) emission ---------------------------------
    nearfield_irradiance_at_fpa: SpectralData  # E_nf(λ), W/m²/µm at FPA
    nearfield_fraction: float                  # η_nf ∈ [0,1] (0 = perfect cold stop)

    # ---- Stray light --------------------------------------------------------
    stray_light_irradiance_at_fpa: SpectralData  # E_stray(λ), W/m²/µm at FPA
    stray_includes_thermal: bool                 # see §6.5

    # ---- Étendue bookkeeping ----------------------------------------------
    signal_etendue_AΩ_m2_sr: float            # invariant; for trace/debug only
```

**Invariants:**

1. `transmission` is on the global wavelength grid. Its value is the *net* throughput from the entrance pupil to the FPA, regardless of how the user specified it.
2. `elements` is always populated. For input modes that do not name elements explicitly, it contains a single synthesized "lumped" element with the supplied transmission and an effective temperature.
3. `nearfield_irradiance_at_fpa` and `stray_light_irradiance_at_fpa` are *irradiance at the FPA*, not radiance and not "irradiance at the entrance pupil." This is the form the detector stage consumes directly.
4. `nearfield_fraction` is unity for uncooled instruments.
5. `signal_etendue_AΩ_m2_sr` is `aperture_area_m2 × Ω_pixel` and is stored only for sanity checks. Downstream stages do not multiply by this — they apply A and Ω independently per regime (per RADIANT_Signal_Chain_Architecture.md §4).

---

## 3. Aperture and Pupil

### 3.1 Aperture shapes

| Shape | Parameters | Notes |
|-------|------------|-------|
| `circular` | `aperture_diameter_m` | Default; covers >95% of EO sensors |
| `rectangular` | `aperture_width_m`, `aperture_height_m` | Slit and prism spectrometer fronts |
| `custom` | `aperture_mask_file` (CSV / FITS bitmask) | User-supplied transmission map on a normalized [0,1]² grid |

### 3.2 Central obscuration

```
obscuration_ratio ε = D_secondary / D_primary  ∈ [0, 1)
A_clear = (π/4) · D² · (1 − ε²)
```

`obscuration_ratio` defaults to 0 (unobscured). The clear area `A_clear` — not the geometric `π D²/4` — is `aperture_area_m2`.

### 3.3 Spider arms

Optional. Parameters: `n_spiders` (int, default 0), `spider_width_m`, `spider_angle_deg` (orientation of the first arm; remaining arms equally spaced). Spiders subtract from `A_clear`:
```
A_spiders ≈ n_spiders · spider_width_m · (D/2 − D_secondary/2)
A_clear -= A_spiders
```
The pupil mask carries the full geometry; the area subtraction is only for the radiometric `A_collect`. The PSF (in spatial) sees the actual masked pupil.

### 3.4 Apodization

| Mode | Parameters | Notes |
|------|------------|-------|
| `uniform` | (none) | Default; mask is binary 0/1 |
| `gaussian` | `apodization_sigma_norm` ∈ (0, 1] | Gaussian taper, σ in units of pupil radius |
| `tabulated` | `apodization_file` | Same format as `aperture_mask_file`; values in [0,1] |

Apodization multiplies the pupil mask. The radiometric `A_collect` becomes `∫∫ A(x,y)² dx dy / max(A)²` for accurate energy throughput (so a perfectly Gaussian-apodized pupil has `A_collect ≈ 0.5 × A_geometric`).

### 3.5 `PupilDescription`

```python
@dataclass(frozen=True)
class PupilDescription:
    shape: ApertureShape
    diameter_m: float | None
    width_m: float | None
    height_m: float | None
    obscuration_ratio: float
    spiders: SpiderConfig | None
    apodization: ApodizationConfig
    wavefront_error: WavefrontError              # §4
    pupil_mask_grid: np.ndarray | None           # cached on first request
    pupil_phase_grid: np.ndarray | None          # cached on first request
    pupil_grid_size_px: int                      # set by spatial fidelity preset
```

The mask and phase grids are not constructed at `OpticsState` build time — they are constructed lazily by the spatial module the first time it asks for them. This avoids paying the FFT-grid cost when the user only wants a noise budget.

---

## 4. Wavefront Error

Four input modes, in order of fidelity:

| Mode | Parameter | Use case |
|------|-----------|----------|
| `scalar_rms` | `wfe_rms_waves` (scalar; ref wavelength `wfe_reference_wavelength_um`) | Trade studies; "I have a Strehl budget" |
| `zernike` | `wfe_zernike_coeffs` (dict {index: waves}) | Standard interferometric output |
| `opd_map` | `wfe_opd_file` (FITS, 2D array, units of waves at `wfe_reference_wavelength_um`) | Measured OPD from a real instrument |
| `field_dependent` | `wfe_field_table` (table of {field_x_deg, field_y_deg, source_mode, value}) | Off-axis aberration mapping |

```python
@dataclass(frozen=True)
class WavefrontError:
    mode: WfeMode
    rms_waves: float | None
    reference_wavelength_um: float
    zernike_coeffs: dict[int, float] | None    # Noll-indexed
    opd_map: np.ndarray | None
    field_table: tuple[FieldWfeSample, ...] | None

    def opd_at_field(self, field_x_deg, field_y_deg, wavelength_um) -> np.ndarray:
        """Return OPD in *meters* on the pupil grid at a given field/wavelength."""
```

**Wavelength scaling**: WFE specified in waves at λ_ref converts to OPD in meters at any wavelength: `opd_m = wfe_waves × λ_ref_m`. The OPD is then converted to phase at the operating wavelength: `phase_rad = 2π × opd_m / λ_op_m`. Strehl follows from the standard `S ≈ exp(−(2πσ_OPD/λ)²)` Maréchal approximation when the WFE is small; for larger WFE, the spatial module integrates the actual OPD.

**Marechal vs. full OTF**: The optics module does not compute the reported Strehl. The WFE always enters the complex pupil, which is FFT'd (there is no fidelity preset — ADR-A). The reported `strehl` metric is PSF-derived in `PerformanceStage`: degraded `effective_psf` peak over the diffraction-limited `reference_psf` peak (both published by `OpticsStage`, same detector kernels — Rule 4). The Maréchal formula survives as the separate `strehl_marechal` diagnostic (`performance/strehl.py`), computed from `stage_outputs["optics"]["wavefront_error"]`.

---

## 5. Transmission — Five Input Modes

All five modes produce the same internal representation: a single `transmission: SpectralData` and an `elements: tuple[OpticalElement, ...]` list. The `transmission_input_mode` field on `OpticsState` records which path was used so the parameter resolver and provenance log can report it.

### 5.1 Mode 1: scalar transmission

Inputs: `optics.transmission_scalar` (e.g., 0.7).

The scalar is broadcast to a flat spectrum on the global wavelength grid. The elements list is synthesized as a single virtual element:

```python
OpticalElement(
    name="lumped",
    kind=ElementKind.LUMPED,
    temperature_K=optics.optics_temperature_K,
    transmittance=flat_at(transmission_scalar),
    reflectance=flat_at(0.0),                     # not used
    declared_emissivity=flat_at(optics.scalar_emissivity),  # default 0.0 — see below
    distance_to_fpa_m=optics.optics_distance_to_fpa_m,
    diameter_m=aperture_diameter_m,
)
```

**Lumped-train emissivity (Gap 37).** By default the lump follows the simple-refractive rule `ε = 0` — the remaining `1 − τ` cannot be attributed to absorption vs. reflection from net transmission alone, so scalar mode produces **no nearfield emission** unless told otherwise. For warm reflective trains (where mirrors follow `ε = 1 − R` and do emit), set `optics.scalar_emissivity` to the train's effective emissivity — `ε ≈ 1 − τ` is the appropriate declaration for an all-mirror train. Construction enforces `ε + τ ≤ 1` (energy conservation) and raises `KirchhoffViolationError` otherwise.

This is the **one sanctioned exception** to the never-independent-emissivity rule (Rule 5): a LUMPED pseudo-element is not a physical surface — it stands in for an entire train whose energy balance the user, not Kirchhoff's law, must supply. `declared_emissivity` on any non-LUMPED element raises `KirchhoffViolationError`.

### 5.2 Mode 2: spectral transmission file

Inputs: `optics.transmission_file` (CSV or .npz, ascending λ in µm).

The file is loaded, validated, interpolated onto the global grid, and stored as `transmission`. The elements list is again a single lumped element, with the same `ε = 0` default as Mode 1. `optics.scalar_emissivity` applies to Mode 1 only; for spectral emissivity control use `key_elements` (Mode 4) or `full_prescription` (Mode 5).

### 5.3 Mode 3: telescope transmission + filter stack

Inputs:
- `optics.telescope_transmission` (scalar or spectral file) — broadband throughput of mirrors, windows, and any non-filter elements.
- `optics.filters` (list of filter specs; see §6.2) — bandpass, longpass, shortpass, notch, or tabulated.

Internally:
```
transmission(λ) = telescope(λ) × Π filter_i(λ)
```

The elements list contains the telescope as one synthesized lumped element plus one synthesized element per filter.

### 5.4 Mode 4: key elements

The user supplies a partial element list — the elements they consider radiometrically important — and a *residual* lumped transmission for everything else.

Inputs:
- `optics.key_elements` (list of `OpticalElement` specs; see §6).
- `optics.residual_transmission` (scalar or file) — accounts for everything not in the key list.

Internally:
```
transmission(λ) = residual(λ) × Π element_i(λ).net_transmittance
```

The residual is treated as a synthesized lumped element with `temperature = optics.optics_temperature_K` (the per-instrument default ambient/cooled temperature). The final elements list is `key_elements + (residual_lumped,)`.

### 5.5 Mode 5: full element-by-element prescription

The user supplies a complete ordered list of elements from entrance pupil to FPA. No residual is permitted.

```
transmission(λ) = Π element_i(λ).net_transmittance
```

This is the only mode in which the order of elements matters for nearfield: emission from element *i* is attenuated by all elements between *i* and the FPA (§7).

---

## 6. Element Catalog and Filters

### 6.1 `OpticalElement`

```python
@dataclass(frozen=True)
class OpticalElement:
    name: str
    kind: ElementKind                      # MIRROR | LENS | WINDOW | FILTER | BEAMSPLITTER
                                           # | DEWAR_WINDOW | COLD_STOP | LUMPED
    temperature_K: float

    transmittance: SpectralData            # τ(λ); 0 for mirrors
    reflectance: SpectralData              # ρ(λ); 0 for ideal lenses

    # Geometry — used by nearfield, not by signal path
    diameter_m: float
    distance_to_fpa_m: float               # along the optical path
    n_surfaces: int = 1                    # for derivation provenance only

    @property
    def net_transmittance(self) -> SpectralData:
        if self.kind == ElementKind.MIRROR:
            return self.reflectance               # mirrors "transmit" by reflecting
        return self.transmittance

    @property
    def emissivity(self) -> SpectralData:
        if self.kind == ElementKind.MIRROR:
            return 1 - self.reflectance
        return 1 - self.transmittance - self.reflectance
```

**Kirchhoff enforcement** at construction:
- For mirrors: `emissivity = 1 − reflectance`. If the user accidentally sets `transmittance` on a mirror, raise `KirchhoffViolationError`.
- For transmissive elements: `emissivity = 1 − transmittance − reflectance`. The default `reflectance` is the per-surface Fresnel scalar (default 0.005 per coated surface) times `n_surfaces`. If the user sets all three independently, the total must satisfy ε + T + R = 1 within tolerance.
- Emissivity is never a user-facing parameter on `OpticalElement` for physical surfaces. The schema rejects any `emissivity` field. Exception: `declared_emissivity` is accepted on `kind=LUMPED` pseudo-elements only (§5.1, Gap 37) and raises `KirchhoffViolationError` on any other kind.

### 6.2 Filter specifications

`Filter` is a kind of `OpticalElement` with five sub-modes:

| Filter type | Parameters | Net transmission |
|-------------|------------|------------------|
| `bandpass` | `center_um`, `fwhm_um`, `peak_transmission`, `oob_rejection` | Top-hat with raised-cosine edges; peak inside the band, OOB level outside |
| `longpass` | `cuton_um`, `peak_transmission`, `oob_rejection` | Step at cuton |
| `shortpass` | `cutoff_um`, `peak_transmission`, `oob_rejection` | Step at cutoff |
| `notch` | `center_um`, `fwhm_um`, `min_transmission`, `peak_transmission` | Inverse top-hat |
| `tabulated` | `transmission_file` | User-supplied τ(λ) |

OOB rejection is a single-number floor, not a spectral curve. Users with measured OOB profiles use `tabulated`.

### 6.3 Built-in element library

Materials shipped under `data/optics/` keyed by name: `gold_protected`, `silver_protected`, `aluminum_uv`, `zns`, `zinc_selenide`, `germanium`, `silicon`, `caf2`, `bk7`, `fused_silica`, `bbar_vis`, `bbar_swir`, `bbar_mwir`, `bbar_lwir`. Each entry has reflectance and/or transmittance vs. wavelength on a 0.2–25 µm grid. The user references them by name on an `OpticalElement`:

```yaml
elements:
  - name: primary
    kind: mirror
    material: gold_protected
    diameter_m: 0.30
    temperature_K: 290
```

---

## 7. Nearfield (Warm-Optics) Emission

This is the warm-optics self-emission term that dominates MWIR and especially LWIR systems. It is *not* the same as path radiance from the atmosphere — it originates inside the instrument.

### 7.1 Per-element thermal emission

Each element radiates as a graybody at its temperature:
```
L_element_i(λ) = ε_i(λ) · B(λ, T_i)        [W/m²/sr/µm]
```

### 7.2 Downstream attenuation

Element *i*'s emission is attenuated by every element between *i* and the FPA. For an ordered element list `[e_1, e_2, ..., e_N]` from entrance pupil (1) to last element before FPA (N):
```
τ_downstream(i)(λ) = Π_{j=i+1}^{N} τ_j(λ)
```

For mode 5 (`FULL_PRESCRIPTION`), the order is the user's. For modes 1–4, the synthesized lumped element is treated as immediately before the FPA (`τ_downstream = 1`), which is conservative.

### 7.3 Per-element solid angle

The signal path's Ω is `pixel_area / focal_length²`. The nearfield Ω is *element-specific*: how big does element *i* look from the FPA?

```
Ω_element_i = π · (D_i / 2)² / d_i²        [sr]
```
where `D_i` is the element diameter and `d_i` is its distance to the FPA. For elements bigger than they are far away (a typical field lens close to the FPA), this is clipped at 2π and a logged warning is issued ("element fills the half-space; nearfield estimate is approximate").

This per-element Ω is what makes the difference between "I have a 10 cm secondary 30 cm from the FPA" and "I have a 10 cm window 1 cm from the FPA": the latter contributes ~900× more nearfield even though the element transmittance is identical.

### 7.4 Nearfield fraction (cold stop)

Cooled IR instruments have a cold stop that limits the solid angle the FPA can see "outside" the optical path. `optics.nearfield_fraction` (η_nf) is the fraction of the FPA's hemisphere that is filled by **warm** (nearfield-emitting) elements:
```
E_nf_total(λ) = η_nf · Σ_i ε_i(λ) · B(λ, T_i) · Ω_element_i · τ_downstream(i)(λ)
```

For uncooled instruments, `η_nf = 1` (everything the FPA sees is warm). For a well-baffled cooled IR camera, `η_nf ≈ 0.05–0.2`.

**Naming (Gap 12).** This parameter was formerly `optics.cold_stop_efficiency`, which inverted the vendor convention (a vendor's "100% efficient cold stop" blocks everything, i.e. η_nf = 0). The relationship is `nearfield_fraction = 1 − vendor_cold_stop_efficiency`. The old name remains accepted as a deprecated alias (DeprecationWarning) and will be removed in a future release. GUI tooltips must state the vendor-convention relationship explicitly.

### 7.5 Output

The total `nearfield_irradiance_at_fpa(λ)` is summed over all elements and stored on `OpticsState`. The detector stage adds it to the photon-flux integrand at the FPA — it does not pass through the signal etendue (it is already an irradiance on the FPA).

---

## 8. Stray Light — Four Input Modes

Stray light is everything that reaches the FPA via a non-image-forming path: scattering off baffles, ghosting, secondary reflections, out-of-FOV sources scattering into the FOV. RADIANT v1 does not model any of this from first principles; it accepts user-supplied magnitudes in four forms.

| Mode | Parameter | Conversion to `E_stray(λ)` |
|------|-----------|----------------------------|
| `veiling_glare` | `optics.stray.veiling_glare_fraction` (0–1) | `E_stray(λ) = vgf × E_in_fov(λ)` where `E_in_fov` is the image-plane irradiance from the in-FOV scene |
| `absolute_irradiance` | `optics.stray.absolute_irradiance_W_m2` (in-band scalar) | Distributed flat across the wavelength grid (multiplied by inverse filter shape if a bandpass is present) |
| `spectral_file` | `optics.stray.spectral_file` (FRED / TracePro export, W/m²/µm at FPA) | Loaded directly, interpolated onto global grid |
| `pst_file` | `optics.stray.pst_file` (PST vs. off-axis angle table) | **Stubbed in v1.** Interface is reserved; raises `NotImplementedError`. Requires a scene radiance distribution to apply, which v1 does not have |

### 8.1 Stray light is noise, not signal

The detector stage adds stray-light electrons to the per-pixel charge **and** to the shot-noise calculation, but stray-light electrons do not appear in `S_signal` and therefore do not influence SNR-as-signal, NIIRS, RER, or detection contrast in the numerator. They appear in the denominator (noise) only.

This is why the parameter is on `OpticsState` rather than added to a radiance frame upstream: putting it into a frame would imply it propagates as signal, which is wrong.

### 8.2 The `includes_thermal` flag

Stray light measurements taken with a cold instrument (e.g., a TracePro export at the design temperature) include scattered nearfield emission as well as scattered out-of-FOV scene radiance. If the user has *also* enabled the nearfield calculation in §7, those photons would be double-counted.

`optics.stray.includes_thermal` (default `False`) prevents the double-count:
- `False`: stray light is purely scattered scene; nearfield is added separately. (Standard for trade studies.)
- `True`: stray light already contains the warm-optics scatter; the nearfield calculation is *suppressed* (set to zero) and a `derivation_chain` entry records the suppression. The user is told.

The flag is recorded on `OpticsState.stray_includes_thermal` so downstream consumers can verify which convention is in force.

---

## 9. Étendue vs. Nearfield Ω — The Subtle Point

This is the most common confusion in EO performance modeling, and the architecture is designed to make it impossible to get wrong:

| Quantity | Symbol | Where it lives | What it is |
|----------|--------|----------------|------------|
| Signal etendue | `A · Ω_pixel` | `signal_etendue_AΩ_m2_sr` (debug only) | Invariant area × pixel solid angle; appears in the extended-source signal equation |
| Per-element nearfield Ω | `Ω_element_i` | Inside `nearfield_irradiance_at_fpa` calculation | How big each warm element looks from the FPA |

**Rules:**
1. The signal path multiplies `L(λ) × A_collect × Ω_pixel × τ_opt(λ) × QE(λ)`. The Ω here is `Ω_pixel = pixel_area / focal_length²`.
2. The nearfield path multiplies `ε_i(λ) × B(λ, T_i) × Ω_element_i × τ_downstream`. The Ω here is the per-element solid angle from the FPA's perspective.
3. **No code anywhere uses both Ωs in the same expression.** They live in different functions, with different parameter names (`omega_pixel_sr` vs. `omega_element_sr`), and the type system flags any cross-use.

The reason this is subtle: in many old performance tools, "warm optics" is computed by treating the entire instrument as one element with one effective solid angle, often the entrance pupil seen from the FPA. That is wrong for any instrument with a relay or a field lens, where elements close to the FPA dominate. Per-element Ω is the right answer; the parameter inventory makes it explicit.

---

## 10. Parameter Inventory

All parameters live under the `optics.*` namespace per RADIANT_Parameter_System.md.

### 10.1 Aperture & geometry
| Parameter | Unit | Default | Notes |
|-----------|------|---------|-------|
| `optics.aperture_shape` | enum: `circular`, `rectangular`, `custom` | `circular` | |
| `optics.aperture_diameter_m` | m | None (required for circular) | |
| `optics.aperture_width_m` | m | None | rectangular only |
| `optics.aperture_height_m` | m | None | rectangular only |
| `optics.aperture_mask_file` | path | None | custom only |
| `optics.obscuration_ratio` | dimensionless | 0.0 | |
| `optics.n_spiders` | int | 0 | |
| `optics.spider_width_m` | m | 0.0 | |
| `optics.spider_angle_deg` | deg | 0.0 | |
| `optics.apodization_mode` | enum | `uniform` | |
| `optics.apodization_sigma_norm` | dimensionless | 1.0 | gaussian only |
| `optics.apodization_file` | path | None | tabulated only |
| `optics.focal_length_m` | m | None (required) | |
| `optics.f_number` | dimensionless | derived from D and f | consistency-grouped |

### 10.2 Wavefront error
| Parameter | Unit | Default |
|-----------|------|---------|
| `optics.wfe_mode` | enum: `scalar_rms`, `zernike`, `opd_map`, `field_dependent` | `scalar_rms` |
| `optics.wfe_rms_waves` | waves | 0.0 |
| `optics.wfe_reference_wavelength_um` | µm | 0.633 |
| `optics.wfe_zernike_coeffs` | dict | `{}` |
| `optics.wfe_opd_file` | path | None |
| `optics.wfe_field_table` | path | None |

### 10.3 Transmission
| Parameter | Unit | Default | Mode |
|-----------|------|---------|------|
| `optics.transmission_input_mode` | enum | inferred | |
| `optics.transmission_scalar` | dimensionless | None | mode 1 |
| `optics.scalar_emissivity` | dimensionless (0–1) | 0.0 | mode 1 — declared lumped-train emissivity (Gap 37); requires ε + τ ≤ 1 |
| `optics.transmission_file` | path | None | mode 2 |
| `optics.telescope_transmission` | scalar or path | None | mode 3 |
| `optics.filters` | list[FilterSpec] | `[]` | mode 3 |
| `optics.key_elements` | list[ElementSpec] | `[]` | mode 4 |
| `optics.residual_transmission` | scalar or path | None | mode 4 |
| `optics.elements` | list[ElementSpec] | `[]` | mode 5 |
| `optics.optics_temperature_K` | K | 290 | default for synthesized elements |
| `optics.optics_distance_to_fpa_m` | m | `focal_length_m` | default for synthesized elements |

### 10.4 Nearfield
| Parameter | Unit | Default |
|-----------|------|---------|
| `optics.nearfield_fraction` (deprecated alias: `optics.cold_stop_efficiency`) | dimensionless | 1.0 |
| `optics.nearfield_enabled` | bool | True |

### 10.5 Stray light
| Parameter | Unit | Default |
|-----------|------|---------|
| `optics.stray.input_mode` | enum: `veiling_glare`, `absolute_irradiance`, `spectral_file`, `pst_file` | `veiling_glare` |
| `optics.stray.veiling_glare_fraction` | dimensionless | 0.0 |
| `optics.stray.absolute_irradiance_W_m2` | W/m² | 0.0 |
| `optics.stray.spectral_file` | path | None |
| `optics.stray.pst_file` | path | None (stubbed) |
| `optics.stray.includes_thermal` | bool | False |

---

## 11. The `OpticsStage`

Per RADIANT_Signal_Chain_Architecture.md, `OpticsStage` is the third stage. Responsibilities:

1. Build the `OpticsState` from parameters (one of five transmission modes × one of four stray-light modes).
2. Apply transmission to produce the `at_fpa_signal` reference frame (still spectral radiance, but multiplied by `τ_opt(λ)`).
3. Compute `A_collect` and `Ω_pixel`, and publish the `effective_psf` and diffraction-limited `reference_psf` (same detector kernels; used for the PSF-derived Strehl) in `state.stage_outputs["optics"]`. **EE_box is *not* computed here** — it is computed downstream in `PlatformStage` from the fully degraded PSF (jitter, smear, turbulence included), stored at `stage_outputs["platform"]["EE_box"]`, and applied exactly once in `SpectralIntegrationStage` (Rule 9 unchanged).
4. Finalize the radiometric regime (per the architecture document, Source's tentative regime can be upgraded once the real PSF FWHM is known).
5. Register `nearfield_irradiance_at_fpa` and `stray_light_irradiance_at_fpa` in `state.stage_outputs["optics"]` for the detector stage to consume.
6. Register the single optical MTF term `mtf_optics_x` / `mtf_optics_y` in `state.mtf_terms`, computed from the pupil autocorrelation (Rule 4 — diffraction, WFE, and defocus enter via the pupil and are not separate MTF factors).

---

## 12. Validation

| Check | Bound |
|-------|-------|
| `0 ≤ τ_opt(λ) ≤ 1` ∀λ | hard |
| `0 ≤ ε_i(λ) ≤ 1` for every element | hard |
| `ε_i + T_i + R_i = 1 ± 1e-4` for transmissive | hard (Kirchhoff) |
| `ε_i + R_i = 1 ± 1e-4` for mirrors | hard (Kirchhoff) |
| `obscuration_ratio < 1` | hard |
| `nearfield_fraction ∈ [0, 1]` | hard |
| `aperture_diameter_m > 0` | hard |
| Mode 4/5 element list non-empty | hard |
| Mode 5 elements ordered (entrance → FPA) | hard; user must order |
| `f_number = focal_length / aperture_diameter` consistency | hard, in consistency group |

---

## 13. Out of Scope for v1

- Polarization in optics (Mueller matrices, retarders).
- Chromatic aberration (refractive system design problem).
- Ghost-image computation from first principles (stray-light tool).
- Surface BSDF (first-principles stray light).
- Non-rotationally-symmetric apodization beyond the supplied 2D mask.
- Tilted/decentered element trees (this is a design tool concern, not performance).
- Field-dependent transmission / vignetting beyond a polynomial table.
