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
- "I have a tape7 from a colleague but no MODTRAN binary." (The better answer: import it directly via `atmosphere.modtran.tape7_path`, §5.1 — no manual CSV conversion.)

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

The high-fidelity option, with two flavors (precedence and detail in §5). **Tape7 file import** (primary): `atmosphere.modtran.tape7_path` names a tape7 produced elsewhere; RADIANT parses it pre-chain, converts units (cm⁻¹ → µm, W/cm² → W/m², descending → ascending), and resamples onto the global wavelength grid — no binary required. **Binary invocation** (secondary, never yet exercised): RADIANT builds a MODTRAN card deck from the user's parameters and geometry, invokes the MODTRAN binary, parses the resulting tape7, and caches the converted arrays.

**Inputs**: `atmosphere.modtran.tape7_path` (file import), or for the binary flavor `atmosphere.modtran.atmosphere_profile`, `atmosphere.modtran.aerosol_model`, `atmosphere.modtran.h2o_scale`, `atmosphere.modtran.o3_scale`, `atmosphere.modtran.cloud_model`, `atmosphere.modtran.binary_path`, `atmosphere.modtran.cache_dir`, plus all `geometry.*` parameters.

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

This section defines the file and binary boundary between RADIANT and MODTRAN. Everything that depends on MODTRAN file formats lives in `radiant.atmosphere.modtran` — the tape7 file import (`Tape7Import`), the deck builder (`render_tape5`), the parser (`Tape7Reader`), and the cache. No other module may know what a tape5, tape7, or `.tp7` file looks like.

There are **two ways in**, with a fixed precedence:

1. **Tape7 file import (§5.1) — the primary workflow.** `atmosphere.modtran.tape7_path` names a tape7 produced elsewhere (a colleague's licensed MODTRAN run, a donated fixture). When set, the file wins unconditionally: the binary, the cache, and the fallback are never consulted.
2. **Binary invocation (§5.2–§5.5) — secondary, never yet exercised.** With `tape7_path` unset, RADIANT renders a tape5 deck and drives a locally-installed `modtran` executable, with caching and an opt-in fallback. This path is retained unchanged for when MODTRAN access arrives.

**Verification status caveat**: no real MODTRAN binary has ever executed a RADIANT-rendered deck, and no real tape7 has ever passed through the parser — every `.tp7` in the test suite is a synthetic or hand-authored fixture. Field-position details below carry open verification CUs (CU-065: Card 3 ANGLE convention; CU-067: Card 1 token positions) that must be checked against the MODTRAN manual when access arrives. See `docs/plans/MODTRAN_Run_Matrix_Plan.md`.

### 5.1 Tape7 file import (primary workflow)

Setting `atmosphere.modtran.tape7_path` (with `atmosphere.model = "modtran"`) builds the atmospheric state from an existing tape7 file:

- **Rule 6 boundary**: the file is parsed **before chain execution**, in `radiant.atmosphere.loaders._build_modtran`, via `Tape7Reader.to_radiant_units()`. The parsed arrays travel as a `Tape7Import` (frozen dataclass: four ascending-wavelength arrays + `source_path` + `content_key` = sha256(file bytes)[:16]) into `ModtranAtmosphere`, which resamples them to the chain grid exactly the way the binary path's cache-hit branch does. `AtmosphereStage` never reads the file; with `tape7_path` set, `modtran` counts as file-backed for the stage's Rule 6 refusal check (`loaders.model_requires_prebuild`).
- **Precedence**: file set → file wins; binary, cache, and `allow_fallback` are irrelevant. File unset → §5.2–§5.5 behavior, bit-identical to before the import path existed.
- **Geometry-agnostic**, like tabulated input (§3.2): the imported arrays are served as-is for any query geometry. The file encodes whatever geometry its MODTRAN run used; RADIANT does not re-scale it. Consequently an airborne target (`h_tgt > 0`) raises `NotImplementedError` — a single file cannot supply both the target-leg and the full-column transmittance the background branch needs (same restriction as `TabulatedAtmosphere`).
- **Downwelling**: a standard IEMSCT=2 tape7 carries no downwelling column, so `L_atm_down ≡ 0` (identical to the tabulated side-door without a downwelling file); `E_sky_thermal = 0` follows.
- **Equivalence guarantee**: importing a tape7 directly produces chain outputs identical to the historical side-door (Tape7Reader → full-precision CSVs → `atmosphere.model="tabulated"`); `tests/integration/test_modtran_tape7_import.py` asserts exact equality.
- **Provenance**: `derivation_chain` records the source path and `content_key`; `SpectralData.source_parameters` carries `cache_key="tape7-file:<content_key>"`.

### 5.2 Card deck builder

`ModtranConfig` is a dataclass holding the MODTRAN knobs RADIANT exposes; the free function `render_tape5(config, geometry)` emits the fixed-format tape5 string. RADIANT does not expose every MODTRAN knob — only the ones that matter for the in-scope use cases: `atmosphere_profile` (MODEL 1–6), `aerosol_model` (IHAZE), `h2o_scale` / `o3_scale` (Card 2C column scaling), `visibility_km` (Card 2 VIS; `None` = IHAZE default, CU-063), `itype` (Card 1 path geometry; default 2 = slant path H1→H2, CU-069), `iemsct` (Card 1 mode; default 2 = thermal+solar path radiance, 3 = solar irradiance, CU-064), `spectral_resolution_cm1`, `v1_cm1` / `v2_cm1` (Card 4), plus `binary_path`, `cache_dir`, and `allow_fallback`.

**Cards RADIANT writes** (1, 1A, 2, 2C, 3, 3A1, 4, 5): geometry comes from `AtmosphericGeometry` — H1/H2 from sensor/target altitude, ANGLE from `path_zenith_rad` (written in RADIANT's own convention pending CU-065 verification), solar zenith/azimuth on Card 3A1 (IPARM=2). IMULT=1 (multiple scattering) is fixed. Anything not exposed is left at the literal values in `render_tape5`; the `ModtranConfig.extra_cards: dict[str, str]` field lets advanced users override a whole card line, and the override is part of the rendered deck and therefore of the cache key.

The deck is rendered to a tape5 in a per-run temp directory. RADIANT does *not* edit a user-supplied tape5 — the deck is built from scratch every run, so reproducibility is owned entirely by the parameter set, not by a hand-tuned input file.

### 5.3 Tape7 parser

`Tape7Reader` parses the fixed-column tape7 file into a `ModtranNativeOutput` dataclass:

```python
@dataclass(frozen=True)
class ModtranNativeOutput:
    wavenumber_cm1: np.ndarray           # cm⁻¹, MODTRAN-native descending order
    total_transmittance: np.ndarray      # dimensionless
    path_thermal_radiance: np.ndarray    # W/cm²/sr/cm⁻¹ (PTH THRML column)
    path_scattered_radiance: np.ndarray  # W/cm²/sr/cm⁻¹ (SOL SCAT column)
    ground_reflected_radiance: np.ndarray  # W/cm²/sr/cm⁻¹ (GRND RFLT column)
    header: dict[str, Any]               # raw header lines (card echo etc.)
```

The other real tape7 columns (`THRML SCT`, `SURF EMIS`, `SNGL SCAT`, `DRCT RFLT`, `TOTAL RAD`) are located by the parser but not yet consumed — a richer decomposition (e.g. exposing single-scatter solar separately) is future work, not a shipped surface.

**Column identification (CU-066):** columns are located by their tape7 header LABEL (`FREQ`, `TOT TRANS`, `PTH THRML`, `SOL SCAT`, `GRND RFLT`, ...), matched by left-to-right order of appearance in the header line — not by a fixed token/character position, which varies by MODTRAN version and does not survive multi-word labels. A header lacking a required label raises `Tape7ParseError`. Tape7 files with no recognisable header (e.g. hand-authored fixtures) fall back to the pre-fix positional assumption with a `UserWarning`; that fallback has not been validated against a real tape7 and should not be relied on for MODTRAN-derived results.

Conversion to RADIANT internal units happens in `to_radiant_units()`, which returns four ascending-wavelength `np.ndarray`s — `(wavelength_um, transmittance, path_radiance, ground_reflected)`, where `path_radiance` is the sum of the thermal and scattered components in W/m²/sr/µm:
1. Spectral axis: `λ [µm] = 10⁴ / ν [cm⁻¹]`, sorted ascending.
2. Radiance: `L(λ) [W/m²/sr/µm] = L(ν) [W/cm²/sr/cm⁻¹] · ν²` — the single factor `ν²` combines the cm⁻²→m⁻² area conversion (10⁴) with the spectral Jacobian `|dν/dλ| = ν²/10⁴`.
3. Transmittance is dimensionless and unchanged.

The conversion is implemented exactly *once*, in this method. No other module performs cm⁻¹↔µm or W/cm²↔W/m² arithmetic.

### 5.4 Cache

MODTRAN runs are slow (seconds to minutes). The cache is keyed by a deterministic hash of the rendered tape5, and stores the **parsed, unit-converted arrays** (not the raw tape7):

```
cache_key  = sha256(rendered_tape5).hexdigest()[:16]
cache_path = cache_dir / f"{cache_key}.npz"    # wavelength_um, transmittance,
                                               # path_radiance, ground_reflected
```

On a run: render tape5 → compute key → on hit, load the `.npz` and skip MODTRAN; on miss, invoke the binary in a temp directory, parse the tape7, save the arrays, proceed. The MODTRAN binary version is **not** part of the key (CU-070): upgrading the binary silently reuses results cached from the old version — delete the cache directory after a MODTRAN upgrade until that CU closes.

Cache eviction is **manual** — RADIANT never deletes cache entries on its own; remove files from `cache_dir` (default `~/.radiant/modtran_cache`) by hand. Entries are small (four float arrays per run), so accumulated cache is megabytes, not gigabytes.

### 5.5 Error handling when MODTRAN is unavailable

(Applies to the binary path only — the tape7 import (§5.1) never consults the binary.)

The MODTRAN binary may be missing for legitimate reasons: CI runners, students, contractors without licenses. RADIANT degrades in this order:

1. **Cache hit**: if the rendered tape5 hashes to a key already in the cache, return it. The user never knows MODTRAN was missing.
2. **Cache miss with `allow_fallback = True`** (default `False`): log a warning ("MODTRAN binary not available … falling back to SimpleAtmosphere with translated parameters") and build the state from `SimpleAtmosphere` at the equivalent profile/aerosol settings.
3. **Cache miss with `allow_fallback = False`**: raise `ModtranUnavailableError` naming the missing binary path and the two remedies (install MODTRAN / enable the fallback).

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
| `atmosphere.precipitable_water_cm` | cm | 1.4 (US Standard) — **profile-coupled** | If left at its schema default while a non-default `standard_atmosphere` is selected, the loader substitutes the profile's McClatchey/MODTRAN standard column (`simple.PROFILE_PWV_CM`: tropical 4.11, midlat_summer 2.92, midlat_winter 0.85, subarctic_summer 2.08, subarctic_winter 0.42, us_standard 1.4). An explicitly set value always wins (provenance-based, Gap 57). |
| `atmosphere.standard_atmosphere` | enum: `tropical`, `midlat_summer`, `midlat_winter`, `subarctic_summer`, `subarctic_winter`, `us_standard` | `us_standard` | Used for `T_atm_eff` lookup, aerosol/H₂O scale heights, and the default water column (above) |
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
| `atmosphere.modtran.tape7_path` | path | `""` (unset) | Tape7 file import (§5.1). Set → the file wins; binary/cache/fallback never consulted. Geometry-agnostic; `h_tgt > 0` rejected |
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

**Producer-side note (CU-009):** SourceStage's `_infer_los` reads `geometry.path_zenith_rad`, `geometry.solar_zenith_rad`, and `geometry.solar_azimuth_rad` to construct the `LineOfSightGeometry` it publishes for AtmosphereStage. The solar-zenith and solar-azimuth values propagate only when the target descriptor is solar-interacting (`T2Reflective`, `T3Mixed`); pure-thermal `T1Thermal` targets receive `theta_s = delta_phi = None` regardless of the registered solar params, honoring the `LineOfSightGeometry` "None for pure-thermal" docstring contract.

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

1. **Resolve the atmosphere model** — preferentially the pre-built model injected at `stage_outputs["atmosphere_config"]["model"]` (see §8.1); only non-file-backed models may be built inline as a partial-chain fallback — and **build the `AtmosphericState`** from it.
2. **Apply transmittance and add path radiance** to produce the `at_aperture` reference frame:
   ```
   L_at_aperture(λ) = L_at_target(λ) · τ_atm(λ) + L_path(λ)
   ```
3. **Register the `at_aperture` frame** on the `ChainState` per the architecture document.
4. **Register `L_atm_down(λ)`** in `state.stage_outputs["atmosphere"]["downwelling"]` so the source stage's reflected-solar and sky-background paths can consume it on their next pass — this is the only chain-level back-coupling and is handled by re-running `SourceStage` once if the source has a downwelling-dependent component (per RADIANT_Signal_Chain_Architecture.md §6.3).
5. **Register the turbulence MTF** in `state.mtf_terms["turbulence"]` if turbulence is enabled. Otherwise this term is omitted entirely (not set to unity); the system-MTF cascade simply has one fewer term, which is faster and avoids the temptation to "see" turbulence in a debug plot when it is off.
6. **Store the full `AtmosphericState`** in `state.stage_outputs["atmosphere"]["state"]` for downstream inspection.

`AtmosphereStage` is a pure function of `(state_in, params)` per the architecture document. It does not mutate state, performs **no file I/O** (Rule 6 — see §8.1), and is safely re-runnable.

### 8.1 The Rule 6 loader boundary (`atmosphere/loaders.py`)

Rule 6 forbids stages from reading files, so all file-backed model construction lives in `radiant/atmosphere/loaders.py`, which runs **before** chain execution:

- `build_atmosphere_model(params)` dispatches on `atmosphere.model` and performs any file I/O the model needs (NPZ/CSV tables for `tabulated`, an NPZ directory scan for `interpolated`, tape7 parsing for `modtran` with `tape7_path` set); `exo` and `simple` need no I/O.
- `FILE_BACKED_MODELS = frozenset({"tabulated", "interpolated"})` names the models that **always** need files; `model_requires_prebuild(params)` is the parameter-aware check the stage uses — it additionally returns True for `modtran` when `atmosphere.modtran.tape7_path` is set (§5.1).
- The API layer (`RadiantSession`, and therefore `Sensor`) calls the loader and injects the constructed model into the chain via `ChainRunner.run(..., initial_stage_outputs={"atmosphere_config": {"model": model}})`; `AtmosphereStage` reads it from `stage_outputs["atmosphere_config"]["model"]`.
- If no injected model is present, the stage builds only non-file-backed models inline (partial-chain convenience). For a file-backed model it **refuses to build inline** and raises a `ValueError` directing the caller to `RadiantSession`/`Sensor` or to `build_atmosphere_model()` + manual injection.

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
