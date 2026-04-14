# RADIANT Atmosphere

**Status**: Authoritative — first design pass, unified
**Scope**: All atmospheric propagation between the target and the entrance pupil. Anything that produces a `SpectralTransmittance`, a `SpectralPathRadiance`, or an atmospheric MTF term for the chain to consume.
**Sister documents**: RADIANT_Conventions.md, RADIANT_Parameter_System.md, RADIANT_Signal_Chain_Architecture.md, RADIANT_Source_Target_System.md

---

## 1. Design Philosophy

The atmosphere module has one job: **deliver an `AtmosphericState` to the chain**. Everything in this document — Beer-Lambert exponentials, US Standard profiles, MODTRAN tape7 parsing, slant-path geometry, Kolmogorov turbulence — exists to populate that single contract.

Five guiding rules:

1. **One contract, four input paths.** A user may specify the atmosphere by simple parametric model, by tabulated transmittance/path-radiance, by MODTRAN run, or by declaring the path exo-atmospheric (τ ≡ 1, L_path ≡ 0). All four paths produce the **same** `AtmosphericState`. The chain has no idea which path was used.
2. **Three spectral outputs, always.** Every model, including exo-atmospheric, returns `τ_atm(λ)`, `L_path(λ)` (upwelling path radiance — what the sensor sees added to the target on its way through the atmosphere), and `L_atm_down(λ)` (downwelling, used by `SkyBackground` and reflected-solar paths). Numerical zero is preferable to a model-dependent `None`.
3. **Geometry is an input, not a model property.** Slant range, sensor altitude, target altitude, path zenith angle, and solar zenith are all geometry inputs to *every* atmosphere model. The model decides how each input affects its outputs; the user does not pre-bake geometry into a tabulated file.
4. **Turbulence is a stub with a real interface.** The Kolmogorov MTF formula is implemented because it is one line. Everything else (Cn² profiles, anisoplanatism, scintillation) is reserved interface. Turbulence is a flag, off by default, and never enabled for space-based observers.
5. **MODTRAN is a wrapped tool, not an embedded library.** RADIANT writes a card deck, calls a `modtran` binary, parses tape7, and caches the result keyed by a hash of the deck. If the binary is missing, the cache is consulted; if the cache misses, a clear error is raised. RADIANT itself never tries to *be* MODTRAN.

---

## 2. The `AtmosphericState` Contract

```python
@dataclass(frozen=True)
class AtmosphericState:
    """Everything the chain needs to know about the atmospheric path.

    Produced by exactly one of the four input paths. Immutable.
    The chain consumes this and never inspects how it was built.
    """

    # ---- Identification & provenance --------------------------------------
    model: AtmosphereModel               # SIMPLE | TABULATED | MODTRAN | EXO_ATMOSPHERIC
    derivation_chain: tuple[str, ...]    # human-readable build steps
    cache_key: str | None                # populated for MODTRAN; None otherwise

    # ---- Spectral outputs (always present, always on the global grid) -----
    transmittance: SpectralTransmittance     # τ_atm(λ), dimensionless [0,1]
    path_radiance: SpectralPathRadiance      # L_path(λ), upwelling, W/m²/sr/µm
    atm_emission_down: SpectralPathRadiance  # L_atm_down(λ), downwelling, W/m²/sr/µm

    # ---- Geometry the model was evaluated for ----------------------------
    geometry: AtmosphericGeometry        # slant path, zenith, altitudes, solar geometry
    air_mass: float                      # computed from zenith angle (≥ 1, ∞ at horizon)
    slant_path_length_m: float

    # ---- Turbulence (stubbed; populated only if turbulence_enabled) ------
    turbulence: TurbulenceState | None   # None for space, optional for ground

    # ---- Optional: native model output for debugging ---------------------
    native_output: ModtranNativeOutput | None  # tape7 parsed dataclass
```

**Invariants:**

1. `transmittance`, `path_radiance`, and `atm_emission_down` are **all** populated, even when one is "not physical" for the model. For `EXO_ATMOSPHERIC`, transmittance is unity at every wavelength and the two radiance fields are zero.
2. All three spectral arrays live on the global wavelength grid in `SpectralDataStore` before `AtmosphericState` is constructed. Wavelength alignment is enforced at construction, not at consumption.
3. `air_mass` and `slant_path_length_m` are derived from `geometry` at construction and stored for downstream use (NEDT and detection-range calculations want them).
4. `turbulence` is `None` unless the user explicitly enabled the turbulence flag *and* the observer is ground-based. Space-based observers cannot enable turbulence; the parameter resolver rejects the combination with a `ScopeError` (per RADIANT_Scope_Decisions.md).

---

## 3. The Four Unified Input Paths

```
              ┌──────────────────────────────────┐
              │     User configuration           │
              └──────────────────────────────────┘
                              │
       ┌──────────┬───────────┼──────────┬──────────────────┐
       ▼          ▼           ▼          ▼                  ▼
  ┌────────┐ ┌─────────┐ ┌─────────┐ ┌──────────┐
  │ Simple │ │Tabulated│ │ MODTRAN │ │   Exo-   │
  │paramet.│ │ τ, L    │ │ tape7   │ │atmosphr. │
  └────┬───┘ └────┬────┘ └────┬────┘ └─────┬────┘
       └──────────┴──────┬────┴────────────┘
                         ▼
              ┌───────────────────────┐
              │   AtmosphericState    │
              │  (single contract)    │
              └───────────────────────┘
                         ▼
                  AtmosphereStage
```

### 3.1 Simple parametric

A closed-form Beer-Lambert model with three knobs that map to the things a working radiometrist actually has on hand: visibility, humidity, and aerosol type. Suitable for trade studies, scoping, regression tests, and any case where the user does not have a MODTRAN license or cares more about gradient than absolute accuracy.

```
τ_atm(λ) = exp[ −σ_total(λ) · L_slant ]
σ_total(λ) = σ_mol(λ) + σ_aer(λ; visibility, type) + σ_h2o(λ; rh, T)
```

- **Molecular (Rayleigh)**: σ_mol(λ) = 0.0088 · λ_µm⁻⁴·⁰⁹ km⁻¹ at sea level (Bucholtz 1995); scaled to slant path by an exponential atmosphere `exp(−h/H_mol)` with H_mol = 8 km.
- **Aerosol (Mie)**: σ_aer is fit from the Koschmieder visibility relation `σ_aer(550 nm) = 3.912 / V_km`, with a wavelength dependence drawn from one of three canonical Ångström exponents: `rural` (α = 1.3), `urban` (α = 1.5), `maritime` (α = 0.7). Aerosol scale height is 1.2 km.
- **Water vapor**: a five-band continuum + absorption fit (1.4, 1.9, 2.7, 3.2, 6.3 µm) parameterized by precipitable water w_pw [cm]. The fit is calibrated against MODTRAN US Standard at the band centers and is *not* claimed to be accurate elsewhere; outside the bands, water vapor contributes only the continuum.

**Path radiance** for the simple model uses a single-scatter approximation:
```
L_path(λ) = [E_sun(λ) / (4π)] · cos(θ_sun) · ω₀(λ) · P(θ_scatter) · [1 − τ_atm(λ)]
```
where `E_sun(λ)` is the TOA solar spectral irradiance and the `4π` is the full-sphere phase function normalization. With `ω₀ = 0.95` (rural), `0.85` (urban), `0.99` (maritime), and a Henyey-Greenstein phase function with `g = 0.75`. This is good to ±30% in VIS/SWIR and is intentionally crude; users who need better path radiance use MODTRAN.

**Atmospheric thermal emission** for the simple model uses a graybody approximation at the path-mean temperature:
```
L_atm_down(λ) = [1 − τ_atm(λ)] · B(λ, T_atm_eff)
```
with `T_atm_eff` from the standard-atmosphere lookup at 0.5 × sensor altitude. Adequate for MWIR/LWIR scoping.

**Inputs** (all parameters are user-facing; see §6):
`atmosphere.visibility_km`, `atmosphere.aerosol_type`, `atmosphere.precipitable_water_cm`, `atmosphere.standard_atmosphere`.

### 3.2 Tabulated

The user provides `τ_atm(λ)` and `L_path(λ)` as files (CSV, ENVI .sli, or NumPy .npz). RADIANT loads them, validates monotonic ascending wavelength, interpolates onto the global grid, and uses them as-is. No physics is applied. The user owns the physics.

This is the escape hatch for:
- Output from a higher-fidelity tool that is not MODTRAN (libRadtran, 6S, DIRSIG).
- Measured transmittance from an FTIR campaign.
- Unit-test fixtures and regression baselines.
- "I have a tape7 from a colleague but no MODTRAN binary." (See §5 for a better answer to this.)

`L_atm_down(λ)` is optional for tabulated input; if not supplied, it is set to zero with a logged warning. Tabulated input is geometry-agnostic — RADIANT does *not* re-scale tabulated transmittance for a different slant path. If the user changes geometry after specifying a tabulated file, the parameter resolver flags a `GeometryDrift` warning.

**Inputs**: `atmosphere.tabulated_transmittance_file`, `atmosphere.tabulated_path_radiance_file`, `atmosphere.tabulated_downwelling_file` (optional).

### 3.3 Exo-atmospheric

For sensors above the atmosphere observing targets above the atmosphere (typical space surveillance, satellite-to-satellite imaging, deep-space). All three spectral outputs are constants:

```
τ_atm(λ) ≡ 1.0
L_path(λ) ≡ 0.0
L_atm_down(λ) ≡ 0.0
```

This is not "no atmosphere"; it is "the atmosphere is the cosmic vacuum, and the cosmic vacuum has unity transmittance and zero path radiance to within a part in 10²⁰." The CMB contribution is delivered through `SourceStage` as a `BlackbodyBackground(T=2.7)`, not through `AtmosphereStage` (per RADIANT_Source_Target_System.md §3.7).

**Inputs**: none. Selection is implicit from `geometry.observer_type = "space"` and `geometry.target_type = "space"`. The user may explicitly request `atmosphere.model = "exo"` for any geometry, but doing so for a ground observer is a logged warning.

### 3.4 MODTRAN

The high-fidelity option. RADIANT builds a MODTRAN card deck from the user's parameters and geometry, invokes the MODTRAN binary, parses the resulting tape7 file, converts units (cm⁻¹ → µm, W/cm² → W/m², descending → ascending), interpolates onto the global wavelength grid, and stores everything. The full native parsed output is preserved on the `AtmosphericState` for debugging. Detailed in §5.

**Inputs**: `atmosphere.modtran.atmosphere_profile`, `atmosphere.modtran.aerosol_model`, `atmosphere.modtran.h2o_scale`, `atmosphere.modtran.o3_scale`, `atmosphere.modtran.cloud_model`, `atmosphere.modtran.binary_path`, `atmosphere.modtran.cache_dir`, plus all `geometry.*` parameters.

---

## 4. Geometry Dependence

### 4.1 The geometry inputs

```python
@dataclass(frozen=True)
class AtmosphericGeometry:
    sensor_altitude_m: float      # height above mean sea level
    target_altitude_m: float      # height above mean sea level
    path_zenith_deg: float        # angle from local vertical at the lower endpoint
    solar_zenith_deg: float       # for downwelling and reflected-solar paths
    solar_azimuth_deg: float      # for path-radiance phase angle
    observer_type: ObserverType   # SPACE | AIRBORNE | GROUND
    target_type: TargetType       # SPACE | AIRBORNE | GROUND
```

Per RADIANT_Conventions.md §5, all angles are stored in radians internally; `_deg` suffixes mark the user-facing API contract.

### 4.2 Slant path length

Computed once at `AtmosphericGeometry` construction and stored for every model to use:

```
For target above sensor (uplooking):
    L_slant = (h_target − h_sensor) / cos(θ_zenith)            # flat-Earth small zenith
For sensor above target (downlooking):
    L_slant = (h_sensor − h_target) / cos(θ_zenith)
For zenith > 80°: switch to spherical-Earth correction
    L_slant = R_E · [√(cos²θ + 2(Δh/R_E) + (Δh/R_E)²) − cos θ]
```

Air mass `m = L_slant / Δh` is stored alongside; for zenith ≤ 80° it equals `sec(θ)`, and the spherical correction kicks in past 80° to keep the horizon finite (`m ≈ 38` at the horizon for sea level).

### 4.3 How geometry feeds each model

| Model | Slant path effect | Solar zenith effect |
|-------|-------------------|---------------------|
| Simple | `τ = exp(−σ · L_slant)`; aerosol & H₂O scale heights re-evaluated for `(h_sensor, h_target)` | Drives `cos(θ_sun)` in single-scatter `L_path`; drives `T_atm_eff` weakly |
| Tabulated | **None.** Tabulated files are taken at face value. `GeometryDrift` warning if geometry changes after load | None |
| Exo | None | None |
| MODTRAN | Set into card deck (CARD 3: `H1`, `H2`, `ANGLE`); MODTRAN computes the slant path internally | Set into card deck (CARD 3A1: `IPARM`, `PARM1`, `PARM2`); MODTRAN computes single + multiple scatter |

The simple model and the MODTRAN interface both *recompute* their outputs whenever geometry changes. Tabulated does not. This is the user-visible price of choosing tabulated input.

### 4.4 Reciprocity and the upwelling/downwelling distinction

For unpolarized broadband radiation in a plane-parallel atmosphere, transmittance is reciprocal: `τ(sensor → target) = τ(target → sensor)`. RADIANT exploits this — only one transmittance is computed per slant path. Path radiance is *not* reciprocal: the sensor-bound (`L_path`, "upwelling") and source-bound (`L_atm_down`, "downwelling") radiances differ because of the geometry of where the scattering and emission happen. Both are computed independently, and they are not interchanged.

`L_atm_down` is consumed by `SkyBackground` (RADIANT_Source_Target_System.md §3.7) and by any `ReflectedSolarSource` whose downwelling spectrum is tied to the atmospheric model rather than to a top-of-atmosphere standard. The atmosphere module *produces* `L_atm_down`; it does not consume it.

---

## 5. MODTRAN Interface

This section defines the binary boundary between RADIANT and MODTRAN. Everything that depends on MODTRAN file formats lives in `radiant.atmosphere.modtran` and `radiant.io.modtran_reader`. No other module may know what a tape5, tape7, or `.tp7` file looks like.

### 5.1 Card deck builder

`ModtranCardDeck` is a dataclass with one field per MODTRAN card that RADIANT cares about, plus a `render()` method that emits a fixed-format tape5. RADIANT does not expose every MODTRAN knob — only the ones that matter for the in-scope use cases.

**Cards RADIANT writes:**

| Card | Purpose | RADIANT-controlled fields |
|------|---------|---------------------------|
| 1 | Mode + atmosphere selection | `MODTRN=T`, `IEMSCT` (1=transmission, 2=radiance+thermal, 4=radiance+thermal+solar), `IMULT` (multiple scatter on/off), `MODEL` (1–6 for atmosphere profile), `M1–M6` profile selectors |
| 1A | Spectral DOS / aerosol controls | `DIS=T` (DISORT solver), `NSTR=8` (8 streams; 4 for fast mode), `LSUN=T` (use Kurucz solar) |
| 2 | Aerosol & cloud | `IHAZE` (1=rural, 4=urban, 3=maritime, 5=tropospheric, 0=none), `CTHIK`, `CALT`, `VIS`, `H2OSTR`, `O3STR` |
| 3 | Geometry | `H1` (sensor altitude km), `H2` (target altitude km), `ANGLE` (zenith deg), `RANGE` (slant range km — used only when `H1`/`H2` are ambiguous), `IDAY` (day of year for solar geometry) |
| 3A1 | Solar / lunar | `IPARM=12`, `PARM1=solar_az_deg`, `PARM2=solar_zen_deg` |
| 4 | Spectral range | `V1`, `V2` (cm⁻¹ start/stop), `DV` (resolution cm⁻¹), `FWHM` |
| 5 | Repeat | `IRPT=0` (no repeat run) |

The deck is rendered to a tape5 file in a per-run temp directory. RADIANT does *not* edit a user-supplied tape5 — the deck is built from scratch every run, so reproducibility is owned entirely by the parameter set, not by a hand-tuned input file.

**RADIANT-controlled vs. MODTRAN defaults**: anything not in the table above is left at MODTRAN's default. The `ModtranCardDeck.extra_cards: dict[str, str]` field lets advanced users inject overrides, and the override is recorded in the cache key.

### 5.2 Tape7 parser

`Tape7Reader` parses the fixed-column tape7 file into a `ModtranNativeOutput` dataclass:

```python
@dataclass(frozen=True)
class ModtranNativeOutput:
    wavenumber_cm1: np.ndarray            # ascending cm⁻¹ as MODTRAN writes it
    total_transmittance: np.ndarray
    path_thermal_radiance_W_cm2_sr_cm1: np.ndarray
    path_scattered_radiance_W_cm2_sr_cm1: np.ndarray
    surface_reflected_radiance_W_cm2_sr_cm1: np.ndarray
    single_scatter_solar_radiance_W_cm2_sr_cm1: np.ndarray
    ground_reflected_radiance_W_cm2_sr_cm1: np.ndarray
    direct_solar_irradiance_W_cm2_cm1: np.ndarray
    header: dict[str, str]                # parsed cards 1-5 echo
```

Conversion to RADIANT internal units happens in a separate `to_radiant_units()` method, which:
1. Multiplies radiances by 10⁴ (W/cm² → W/m²) — *the* conversion from RADIANT_Conventions.md §3.
2. Converts the spectral axis: `λ[i] = 10000 / ν[i]`.
3. Reverses the arrays so wavelength is ascending.
4. Applies the Jacobian: `L(λ) = L(ν) · ν² / 10000` for spectral radiance, `T(λ) = T(ν)` for transmittance (dimensionless).
5. Returns three `SpectralData` objects on MODTRAN's native grid; the global-grid interpolation happens later in `SpectralDataStore`.

The conversion is implemented exactly *once*, in this method. No other module performs cm⁻¹↔µm or W/cm²↔W/m² arithmetic.

**Path radiance composition**: RADIANT's `L_path(λ)` is the sum of MODTRAN's `path_thermal`, `path_scattered`, and `single_scatter_solar` components. The decomposition is preserved on `ModtranNativeOutput` so a user can ask "how much of my path radiance is solar scatter vs. thermal" without re-running.

### 5.3 Cache

MODTRAN runs are slow (seconds to minutes). The cache is keyed by a deterministic hash of the rendered tape5 plus the MODTRAN binary version string:

```
cache_key = sha256(rendered_tape5 + "\n" + modtran_version).hexdigest()[:16]
cache_path = cache_dir / f"{cache_key}.tape7"
```

On a run:
1. Build the deck → render tape5 → compute `cache_key`.
2. If `cache_path` exists, parse it and skip MODTRAN.
3. Otherwise, invoke MODTRAN, write tape7 to `cache_path`, parse it.
4. Always store `cache_key` on the resulting `AtmosphericState` so a downstream user can re-run identical scenarios deterministically.

Cache eviction is **manual**. RADIANT never deletes cache entries on its own; the user runs `radiant atm clear-cache --older-than 30d` if they want to. Atmosphere runs are tiny (~100 KB tape7 each), so even a year of accumulated cache is megabytes. The pain of an over-zealous cache eviction is much greater than the pain of disk usage.

### 5.4 Error handling when MODTRAN is unavailable

The MODTRAN binary may be missing for legitimate reasons: CI runners, students, contractors without licenses. RADIANT degrades in this order:

1. **Cache hit**: if the rendered tape5 hashes to a key already in the cache, return it. The user never knows MODTRAN was missing.
2. **Cache miss with `atmosphere.modtran.allow_fallback = True`** (default `False`): log a `ModtranUnavailableWarning`, build a `simple` atmosphere from the closest equivalent parameters (visibility from `VIS`, aerosol type from `IHAZE`, profile from `MODEL`), and proceed. The `derivation_chain` records "MODTRAN unavailable; fell back to simple parametric model with translated parameters."
3. **Cache miss with `allow_fallback = False`**: raise `ModtranUnavailableError` with the rendered tape5 path, the cache key that would have been used, and a one-line instruction for installing MODTRAN or pre-populating the cache.

Fallback is opt-in because a user running a sensitivity study almost always wants to know that MODTRAN silently disappeared from under them. CI and student users opt in explicitly in their config.

---

## 6. Parameter Inventory

All parameters live under the `atmosphere.*` namespace. Names follow RADIANT_Parameter_System.md §"Naming rules" (lowercase, no unit suffix on the canonical name, two-deep namespace). Where the user-facing input has a unit different from the internal storage unit, the user-facing parameter carries a `_<unit>` suffix per RADIANT_Conventions.md §5 / §"interface boundaries."

### 6.1 Selection

| Parameter | Unit / type | Default | Required for | Notes |
|-----------|-------------|---------|--------------|-------|
| `atmosphere.model` | enum: `simple`, `tabulated`, `modtran`, `exo` | auto from observer/target type | all | Auto: `exo` if both endpoints space; `simple` otherwise |
| `atmosphere.turbulence_enabled` | bool | `False` | ground only | Rejected if observer is space |

### 6.2 Simple parametric

| Parameter | Unit / type | Default | Notes |
|-----------|-------------|---------|-------|
| `atmosphere.visibility_km` | km | 23.0 | "Clear" per Koschmieder; rejected if ≤ 0 |
| `atmosphere.aerosol_type` | enum: `rural`, `urban`, `maritime` | `rural` | Sets Ångström α and SSA |
| `atmosphere.precipitable_water_cm` | cm | 1.4 | US Standard mid-latitude annual mean |
| `atmosphere.standard_atmosphere` | enum: `tropical`, `midlat_summer`, `midlat_winter`, `subarctic_summer`, `subarctic_winter`, `us_standard` | `us_standard` | Used for `T_atm_eff` lookup and aerosol/H₂O scale heights |
| `atmosphere.cloud_fraction` | dimensionless 0–1 | 0.0 | Stubbed in v1; non-zero raises `NotImplementedError` |
| `atmosphere.cloud_optical_depth` | dimensionless | 0.0 | Same |

### 6.3 Tabulated

| Parameter | Unit / type | Default | Notes |
|-----------|-------------|---------|-------|
| `atmosphere.tabulated_transmittance_file` | path | None (required) | CSV / .npz / .sli; ascending λ in µm |
| `atmosphere.tabulated_path_radiance_file` | path | None (required) | Same format; W/m²/sr/µm |
| `atmosphere.tabulated_downwelling_file` | path | None (optional) | Same format; defaults to zero with warning |

### 6.4 MODTRAN

| Parameter | Unit / type | Default | Notes |
|-----------|-------------|---------|-------|
| `atmosphere.modtran.binary_path` | path | env var `RADIANT_MODTRAN_BIN`, then `/usr/local/bin/modtran` | Resolved at first use, not at config load |
| `atmosphere.modtran.cache_dir` | path | `~/.radiant/modtran_cache/` | Created if missing |
| `atmosphere.modtran.allow_fallback` | bool | `False` | If `True`, falls back to simple parametric on missing binary |
| `atmosphere.modtran.atmosphere_profile` | enum: `tropical`, `midlat_summer`, `midlat_winter`, `subarctic_summer`, `subarctic_winter`, `us_standard` | `us_standard` | Maps to `MODEL` 1–6 |
| `atmosphere.modtran.aerosol_model` | enum: `rural`, `urban`, `maritime`, `tropospheric`, `none` | `rural` | Maps to `IHAZE` |
| `atmosphere.modtran.h2o_scale` | dimensionless multiplier | 1.0 | `H2OSTR = "1.0g"` syntax handled by deck builder |
| `atmosphere.modtran.o3_scale` | dimensionless multiplier | 1.0 | Same |
| `atmosphere.modtran.cloud_model` | enum: `none`, `cumulus`, `altostratus`, `stratus`, `stratocumulus`, `nimbostratus` | `none` | Cloud fraction is 0/1 in v1 (stubbed for fractional) |
| `atmosphere.modtran.disort_streams` | int | 8 | 4 for fast mode; 8 for production; 16 reserved |
| `atmosphere.modtran.spectral_resolution_cm1` | cm⁻¹ | 1.0 | Drives `DV` and `FWHM` |
| `atmosphere.modtran.extra_cards` | dict[str,str] | `{}` | Override hatch; recorded in cache key |

### 6.5 Geometry (consumed, not owned)

These parameters live in `geometry.*` per RADIANT_Parameter_System.md, and the atmosphere module reads them through the parameter resolver:

`geometry.sensor_altitude_m`, `geometry.target_altitude_m`, `geometry.path_zenith_deg`, `geometry.solar_zenith_deg`, `geometry.solar_azimuth_deg`, `geometry.observer_type`, `geometry.target_type`, `geometry.day_of_year`.

### 6.6 Turbulence (stubbed)

| Parameter | Unit / type | Default | Notes |
|-----------|-------------|---------|-------|
| `atmosphere.turbulence_enabled` | bool | `False` | Rejected if observer is space |
| `atmosphere.r0_cm` | cm at 500 nm | 10.0 | Fried parameter; user provides directly in v1 |
| `atmosphere.turbulence_outer_scale_m` | m | 25.0 | von Kármán outer scale; reserved (Kolmogorov uses ∞) |
| `atmosphere.cn2_profile` | enum: `none`, `hufnagel_valley`, `slc_day`, `slc_night` | `none` | Reserved interface; `none` means "use r₀ directly" |

---

## 7. Atmospheric Turbulence (Stubbed)

### 7.1 What v1 implements

Exactly one thing: a Kolmogorov long-exposure MTF, applied as an MTF term in the spatial model (not in `AtmosphereStage`'s radiometric output).

```
MTF_turb(f) = exp[ −3.44 · (λ · f / r₀)^(5/3) ]
```

where `f` is the spatial frequency at the entrance pupil in cycles/m, `λ` is wavelength in m, and `r₀` is the Fried parameter at the wavelength of interest. The wavelength scaling `r₀(λ) = r₀(500 nm) · (λ / 500 nm)^(6/5)` is applied automatically.

The MTF is registered into `state.mtf_terms["turbulence"]` by `AtmosphereStage`. From the perspective of the spatial model (RADIANT_Signal_Chain_Architecture.md §6 and the upcoming `RADIANT_Spatial.md`), it is just another term in the system MTF cascade — no special handling.

### 7.2 What v1 does *not* implement (interface reserved)

- **Cn² profile integration** to derive r₀ from atmospheric structure. The v1 user provides r₀ directly.
- **Anisoplanatism** (off-axis turbulence degradation).
- **Scintillation** (irradiance fluctuations from refractive index variations).
- **Tilt vs. higher-order decomposition** (relevant for adaptive optics).
- **Short-exposure MTF** (the `exp((λf/r₀)^(5/3) · 1)` correction term).
- **Dome and platform-induced seeing**.

These are interface-reserved: parameters exist in `_schema.py` and on the `TurbulenceState` dataclass, but raise `NotImplementedError` in v1. They are deferred per RADIANT_Scope_Decisions.md ("turbulence is dominated by r₀ for the use cases we care about, and r₀ is something a working observer can measure or estimate; everything else is a refinement that does not change the conclusions of a trade study").

### 7.3 Why turbulence is in the atmosphere module but applied as MTF

Turbulence is physically an atmospheric phenomenon (refractive index fluctuations along the path) but it acts on the chain *spatially*, not radiometrically — total energy is conserved and only the PSF is modified. Putting the turbulence MTF generation in the atmosphere module keeps all atmosphere-related physics in one place (parameter inventory, documentation, plugin entry point), while the *application* of that MTF lives in the spatial model where the rest of the MTF cascade is computed. This is the same pattern the optics module uses for `MTF_diffraction`: generated in `optics/diffraction.py`, applied in the system MTF cascade.

---

## 8. The `AtmosphereStage`

Per RADIANT_Signal_Chain_Architecture.md §2, `AtmosphereStage` is the second stage in the chain. Its responsibilities:

1. **Build the `AtmosphericState`** by dispatching to the model selected in `atmosphere.model`.
2. **Apply transmittance and add path radiance** to produce the `at_aperture` reference frame:
   ```
   L_at_aperture(λ) = L_at_target(λ) · τ_atm(λ) + L_path(λ)
   ```
3. **Register the `at_aperture` frame** on the `ChainState` per the architecture document.
4. **Register `L_atm_down(λ)`** in `state.stage_outputs["atmosphere"]["downwelling"]` so the source stage's reflected-solar and sky-background paths can consume it on their next pass — this is the only chain-level back-coupling and is handled by re-running `SourceStage` once if the source has a downwelling-dependent component (per RADIANT_Signal_Chain_Architecture.md §6.3).
5. **Register the turbulence MTF** in `state.mtf_terms["turbulence"]` if turbulence is enabled. Otherwise this term is omitted entirely (not set to unity); the system-MTF cascade simply has one fewer term, which is faster and avoids the temptation to "see" turbulence in a debug plot when it is off.
6. **Store the full `AtmosphericState`** in `state.stage_outputs["atmosphere"]["state"]` for downstream inspection.

`AtmosphereStage` is a pure function of `(state_in, params)` per the architecture document. It does not mutate state, does not perform I/O outside of the cached MODTRAN invocation, and is safely re-runnable.

---

## 9. Validation & Sanity Bounds

The atmosphere module enforces a small set of physical sanity checks at `AtmosphericState` construction. Violations raise `AtmosphericPhysicsError` with the offending wavelength(s).

| Check | Bound | Reason |
|-------|-------|--------|
| `0 ≤ τ_atm(λ) ≤ 1` ∀λ | hard | Transmittance is a probability; out-of-bound means corrupt input |
| `L_path(λ) ≥ 0` ∀λ | hard | Path radiance is energy emitted/scattered into the line of sight |
| `L_atm_down(λ) ≥ 0` ∀λ | hard | Same |
| `L_atm_down(λ) ≤ B(λ, T_max)` ∀λ where T_max = 350 K | soft (warn) | Downwelling thermal cannot exceed a hot graybody; failure suggests unit confusion |
| `air_mass ≥ 1` | hard | Geometry sanity |
| `slant_path_length_m > 0` for non-exo | hard | Same |
| For MODTRAN: tape7 spectral range covers the global wavelength grid | hard | Otherwise interpolation would extrapolate; user must widen the MODTRAN run |
| For tabulated: ascending λ, no duplicates | hard | Per RADIANT_Conventions.md §2 |

The "soft" warning bounds are RADIANT-specific tripwires for the most common form of user error (units), not physics constraints. They are easy to silence if a user really does want to model a 1000 K atmosphere.

---

## 10. Plugin Hook

Per RADIANT_File_Tree.md, atmosphere is a plugin extension point: users can register a custom `AtmospherePlugin` that returns an `AtmosphericState` from a parameter set. This is how a future libRadtran or 6S wrapper would integrate without touching core code.

```python
class AtmospherePlugin(ABC):
    name: str
    @abstractmethod
    def build_state(
        self,
        params: ParameterSet,
        geometry: AtmosphericGeometry,
        wavelength_um: np.ndarray,
    ) -> AtmosphericState: ...
```

Plugins are registered via the `radiant.plugins.atmosphere` entry point (see RADIANT_File_Tree.md §"Plugin entry points"). The four built-in models (`simple`, `tabulated`, `modtran`, `exo`) are themselves plugins registered by the core distribution, so there is no special-cased "core vs. plugin" path — the plugin interface is the only interface.

---

## 11. Out of Scope for v1

Recorded explicitly so future RADIANT_Scope_Decisions.md updates can lift them deliberately:

- **Polarized atmospheric radiative transfer.** Stokes vectors are not propagated; everything is treated as unpolarized intensity.
- **3D / heterogeneous atmospheres.** Plane-parallel only. No broken-cloud handling, no horizontal gradients.
- **Time-dependent atmospheres.** A scenario specifies one atmospheric state; time-series scenarios re-build the state per frame.
- **Adjacency effects.** The reflected-solar contribution from neighboring ground pixels is not modeled (a 6S/MODTRAN-style "background reflectance" term).
- **Auroral and airglow emission.**
- **Refraction-induced apparent altitude shifts.** A target at zenith angle 89.5° is treated geometrically; the apparent vs. true altitude correction is deferred.
- **Cn² profile integration** (turbulence stub above).
- **Cloud microphysics.** Clouds in v1 are either "off" or "MODTRAN's canned cloud model"; no LWC/effective-radius parameterization.

---

## 12. Open Questions

1. **MODTRAN version compatibility.** RADIANT targets MODTRAN 5 and 6 tape7 formats. Earlier versions are not supported. Confirm with the program office before locking the parser.
2. **Wavelength grid for `simple` aerosol fits.** The Ångström-α model is good in VIS/SWIR and is already weak in MWIR; it is *wrong* in LWIR. The current plan is to clamp aerosol extinction at the SWIR-MWIR boundary and document the limitation. Alternative: switch to a tabulated aerosol cross-section per type.
3. **Where does `day_of_year` live?** It is a geometry concept (drives sun position) but only the atmosphere/MODTRAN path consumes it directly. Currently filed under `geometry.day_of_year`; revisit if a non-atmospheric consumer appears.
4. **Should the simple model expose its single-scatter `L_path` decomposition?** MODTRAN does (thermal, scattered, single-scatter solar). The simple model could too, at the cost of more code. Probably yes.

---
