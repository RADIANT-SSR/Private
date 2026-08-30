# RADIANT Atmosphere

**Status**: Authoritative — the architecture contract for Stage 2
**Scope**: All atmospheric propagation between the target and the entrance pupil. Anything that produces a transmittance, a path radiance, a sky irradiance, or an atmospheric MTF term for the chain to consume.
**Sister documents**: RADIANT_Conventions.md, RADIANT_Parameter_System.md, RADIANT_Signal_Chain_Architecture.md, RADIANT_Source_Target_System.md

## Role of this document

The atmosphere subsystem is documented as **four** documents, one per reader class. This
one is the contract; it deliberately holds no derivation, no measured parity number, and no
operator recommendation.

| Document | Answers |
|---|---|
| **this document** (`docs/architecture/RADIANT_Atmosphere.md`) | the **contract** — product shapes, backend seams and dispatch, topology composition, guard architecture, invariants, parameter surface, stage responsibilities |
| [`docs/theory/atmosphere_models.md`](../theory/atmosphere_models.md) | the **physics** — what each model family computes, from what first principles, with the derivations |
| [`docs/validation/atmosphere_modtran_parity.md`](../validation/atmosphere_modtran_parity.md) | the **measured accuracy** — parity tables against the MODTRAN 6 run set, the anchor inventory, and the known-limitations register |
| [`docs/guides/atmosphere_selection.md`](../guides/atmosphere_selection.md) | the **operator's choice** — which model and which bundled family for which scene, and every warning and refusal with its remedy |

Reading rule, in both directions: a quantity's *definition and invariants* are here; its
*derivation* is in the theory document; its *measured value* is in the parity document; its
*selection consequence* is in the guide. Each section below names its depth documents.

---

## 1. Design Philosophy

The atmosphere module has one job: **deliver an atmospheric product bundle to the chain**.
Everything in the subsystem — Beer-Lambert exponentials, standard profiles, MODTRAN tape7
parsing, slant-path geometry, Kolmogorov turbulence — exists to populate that contract.

Five guiding rules:

1. **One contract, many input paths.** A user may specify the atmosphere by simple
   parametric model, by tabulated file, by interpolation over pre-computed runs, by MODTRAN
   run, or by declaring the path exo-atmospheric. All paths produce the **same** contract.
   The chain has no idea which path was used.
2. **Three spectral outputs, always.** Every model, including exo-atmospheric, returns
   `τ_atm(λ)`, `L_path(λ)` (upwelling path radiance) and `L_atm_down(λ)` (hemispheric
   downwelling **irradiance**, consumed by the reflected-diffuse terms of the target and
   ground-background arms). The `SkyBackground` descriptor consumes a *different* product —
   a directional radiance along the LOS continuation, §4.2g. Numerical zero is preferable
   to a model-dependent `None`.
3. **Geometry is an input, not a model property.** Endpoint altitudes, path zenith and
   solar geometry are inputs to *every* atmosphere model. The model decides how each input
   affects its outputs; the user does not pre-bake geometry into a tabulated file.
4. **Turbulence is profile-driven, and off by default.** The Kolmogorov long-exposure MTF
   takes a Fried parameter $r_0$, entered directly or derived from a $C_n^2(h)$ profile
   integrated along the line of sight (§7). There is **no observer-type gate**: a space
   observer's path simply carries no atmospheric column, so the integral is negligible and
   the term is omitted — a computed answer, not a refusal (ADR-0011 guardrail G4).
5. **MODTRAN is a wrapped tool, not an embedded library.** RADIANT imports a tape7, or
   writes a card deck and calls a `modtran` binary and caches the result. RADIANT itself
   never tries to *be* MODTRAN.

---

## 2. The `AtmosphericState` Contract

> **Implementation reality (reconciled 2026-07-12).** The shipped
> `AtmosphericState` (`atmosphere/protocol.py`) is a frozen dataclass with **five
> fields**: `transmittance`, `path_radiance`, `atm_emission_down` (all
> `SpectralData`), `geometry` (`AtmosphericGeometry`), and `derivation_chain`.
> The additional fields in the block below — `model`, `cache_key`, `air_mass`,
> `slant_path_length_m`, `native_output` — are **design-target, deferred to a
> later phase** (the class docstring says so explicitly). Consequently invariant 3
> (`air_mass`/`slant_path_length_m` stored on the state) describes intended, not
> shipped, behavior. `AtmosphereModel` is not a shipped enum type; the model is
> selected by the `atmosphere.model` **string** parameter, whose five legal values
> are `simple`, `exo`, `tabulated`, `modtran`, `interpolated` (§3).

```python
# The `model`/`cache_key`/`air_mass`/`slant_path_length_m`/`native_output`
# fields below are DESIGN-TARGET — see the banner above.
@dataclass(frozen=True)
class AtmosphericState:
    """Everything the chain needs to know about the atmospheric path.

    Produced by exactly one input path. Immutable.
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

    # ---- Turbulence: not carried on this bundle.  The resolved Fried
    #      parameter travels as stage_outputs['atmosphere']['r0_m'] (§7.1).

    # ---- Optional: native model output for debugging ---------------------
    native_output: ModtranNativeOutput | None  # tape7 parsed dataclass
```

**Invariants:**

1. `transmittance`, `path_radiance`, and `atm_emission_down` are **all** populated, even
   when one is "not physical" for the model. For `EXO_ATMOSPHERIC`, transmittance is unity
   at every wavelength and the two radiance fields are zero.
2. All three spectral arrays live on the global wavelength grid in `SpectralDataStore`
   before `AtmosphericState` is constructed. Wavelength alignment is enforced at
   construction, not at consumption.
3. `air_mass` and `slant_path_length_m` are derived from `geometry` at construction and
   stored for downstream use (NEDT and detection-range calculations want them).
4. The turbulence MTF term exists only when the resolved Fried parameter is positive (§7).
   There is no observer-type restriction: `atmosphere.r0_path` integrates whatever
   atmospheric column the line of sight actually crosses, so a space observer's residual
   column yields a huge $r_0$ and the term is omitted entirely. The pre-Gap-110 "the
   parameter resolver rejects turbulence for a space observer with a `ScopeError`" rule is
   **retired** (ADR-0011 guardrail G4 / Rule 27).

### The `AtmosphericQuantities` bundle — the backend output contract

`AtmosphericState` is the chain-level state; the **backend output contract** is
`AtmosphericQuantities` (`atmosphere/_quantities.py`), returned by every
`Atmosphere.evaluate` implementation. It is a frozen dataclass carrying a wavelength grid
plus **eight** spectral arrays, all on that grid, all in canonical units (Rule 2):

| Field | Unit | Meaning |
|---|---|---|
| `tau_sun` | – | sun → target column (down-leg) |
| `tau_up` | – | target → sensor column (up-leg) |
| `tau_full_up` | – | ground → sensor full column (background branch) |
| `E_TOA` | W/m²/µm | top-of-atmosphere solar spectral irradiance at 1 AU |
| `E_sky_scattered` | W/m²/µm | scattered-solar diffuse sky irradiance at the target |
| `E_sky_thermal` | W/m²/µm | thermal-emission diffuse sky irradiance at the target |
| `L_path_up` | W/m²/sr/µm | path radiance over the target → sensor leg |
| `L_path_full` | W/m²/sr/µm | path radiance over the ground → sensor full column |

The **two-leg split** (`tau_sun` distinct from `tau_up`, `tau_full_up` distinct from both)
is the Option C contract (ADR-0002): it is what lets the assembly equation run without the
source stage knowing any atmosphere physics —

```
L_t,aperture(λ) = [ ε·B(T_t) + ρ·τ_sun·E_TOA·cos θ_s/π
                    + ρ·(E_sky_scattered + E_sky_thermal)/π ] · τ_up  +  L_path_up
```

— with the background branch substituting `tau_full_up` / `L_path_full`. For a surface
target (`h_tgt = 0`) `tau_up == tau_full_up` identically. `__post_init__` validates shape
consistency, τ ∈ [0, 1], and non-negative energy terms, and **raises** rather than clipping
(Rule 17). Callers consume `E_sky_scattered + E_sky_thermal`, never one component alone.

**Guardrail G1 (ADR-0011): the eight fields are a closed set.** A new path topology is
never served by adding a ninth flat field. New topologies are served by *composing path
segments* into these same eight slots (§4.2c–§4.2d); products that are genuinely not
members of this bundle ride alongside it on `TopologyProducts` (§4.2g).

*Depth*: physics of what fills each slot → theory §2; the products' measured accuracy →
parity §2.

---

## 3. The Unified Input Paths

Five models satisfy one contract. The chain sees only `AtmosphericQuantities`; which
backend produced it is invisible downstream.

| `atmosphere.model` | Built by | Pre-chain file I/O | Geometry response | Topologies served |
|---|---|---|---|---|
| `simple` | inline or `loaders` | none | recomputed for every geometry | all (down, up, level, grazing, twilight) |
| `interpolated` | `loaders` (**file-backed**) | NPZ directory scan | interpolates over declared axes; refuses off-hull | the direction its runs measured; up-looking via the declared hybrid (§4.2b) |
| `tabulated` | `loaders` (**file-backed**) | CSV / `.npz` / `.sli` | **none** — served as-is | down-looking only |
| `modtran` | `loaders` when `tape7_path` set (§5.1); else binary at first use | tape7 / flux CSV parse | **none** for the file flavor; deck-driven for the binary flavor | down-looking only |
| `exo` | inline | none | none (exact identities) | any wholly-vacuum path |

`FILE_BACKED_MODELS` and the parameter-aware `model_requires_prebuild()` decide which of
these `AtmosphereStage` may build inline and which it must be handed pre-built (Rule 6,
§8.1).

*Depth*: the two model families' physics → theory §1 and §3; which one to pick → guide §1.

### 3.1 Simple parametric

A closed-form Beer-Lambert model over four species (molecular, aerosol, water vapour,
well-mixed gases), with three user knobs that map to what a working radiometrist has on
hand: visibility, humidity, and aerosol type. It is the **only** backend that can serve an
arbitrary path topology, because the segment evaluators of §4.2c are built on its species
model.

Contract properties this document owns:

- **Products.** `τ_atm` from a slant optical depth; `L_path` as the sum of a single-scatter
  solar term and a Kirchhoff thermal-emission term, on one and the same column; the
  hemispheric `E_sky_scattered` / `E_sky_thermal` pair on the target's own vertical slab.
- **Emissivity is derived, never independent** (Rule 5): the thermal term's emissivity is
  the column's own `1 − τ`. `atmosphere/segment_thermal.py` is one module called from both
  directions (Rule 19) — a night down-looking scene has scattered ≡ 0 and thermal > 0.
- **Two `ω₀` definitions coexist deliberately** (Rule 27 does not apply — they are
  different products): the internal extinction-weighted column albedo inside the
  phase-weighted `L_path` integral, and the MODTRAN-derived `omega0_eff` band table inside
  the hemispheric `E_sky_scattered` closed form.
- **Two emission-temperature models coexist deliberately**, for the same reason: the
  height-resolved `atmosphere/emission_temperature.py` serves the directional
  `L_path,therm`, while the fitted `z_em` offset serves the hemispheric `E_sky_thermal`
  flux and cannot be inherited by a directional product. Its companion exponent `D` is
  **not** fitted — since CU-324 (2026-08-29) it is the geometric `sec 48.2°`, the secant of
  the diffusivity angle the up-looking reference decks were run at.
- **No `ParameterDef` for the emission quadrature** (Rule 12): its sub-layer count is a
  convergence-tested numerical parameter, not a tuneable physical quantity.

**Known fragilities**, named here and sized in the parity document: region-flat spectral
shape inside each calibrated region; linear air-mass scaling on saturated bands; edge-region
clamping outside 0.30–14.29 µm; VIS aerosol absolute optical depth. Cross-validated against
the five non-calibration profile anchors (A2–A6) to ≤ ±0.012 band-mean τ in the
water-relevant windows.

**Inputs** (§6.2): `atmosphere.visibility_km`, `atmosphere.aerosol_type`,
`atmosphere.precipitable_water_cm`, `atmosphere.standard_atmosphere`.

*Depth*: derivations, calibrated tables and constants → theory §2.1–§2.13; measured parity
and the fragility magnitudes → parity §2.1–§2.7 and §3.

### 3.2 Tabulated

The user provides spectra as files (CSV, ENVI `.sli`, or NumPy `.npz`). RADIANT loads them,
validates monotonic ascending wavelength, carries them to the chain grid, and uses them
as-is. **No physics is applied; the user owns the physics.** This is the escape hatch for
libRadtran / 6S / DIRSIG output, measured FTIR transmittance, and regression fixtures.

Contract properties:

- **Geometry-agnostic.** RADIANT does *not* re-scale a tabulated column for a different
  slant path. Changing geometry after load raises a `GeometryDrift` warning.
- `L_atm_down(λ)` is optional; if not supplied it is zero with a logged warning.
- **One resample convention, universal across the three file-backed backends**:
  transmittance is carried onto the chain grid in **log-τ**, the radiances and irradiances
  **linearly**, through the single implementation in `atmosphere/log_tau_resample.py`. A
  query on the file's own grid short-circuits the round trip and is bit-identical to the
  stored array. `TAU_FLOOR` is a *lower* clamp only — an over-unity array is not capped, so
  a mis-scaled file fails loud in `AtmosphericQuantities.__post_init__` instead of being
  snapped to a plausible value (Rule 17).

**Inputs** (§6.3): `atmosphere.tabulated_transmittance_file`,
`atmosphere.tabulated_path_radiance_file`, `atmosphere.tabulated_downwelling_file`.

**Shipped nominal library.** RADIANT ships a committed NPZ library derived from the real
MODTRAN 6 run matrix (`src/radiant/data/tables/atmospheres/`, slit-degraded to 5 cm⁻¹
FWHM), so `tabulated` / `interpolated` users get real-radiative-transfer atmospheres
without a MODTRAN license. Its architecture rules:

- Each family declares its **interpolation axes**, its **direction** (`los_direction` on
  every NPZ), the **profile** it was rendered on, and the full five-field run geometry per
  node — so non-axis mismatch checks compare against recorded values, not assumptions.
- **Dispatch is by `(los_direction, interpolation_axes)`** when
  `atmosphere.interpolated_data_dir` is unset; an explicit directory always wins, and a
  pair no shipped family covers is refused, never approximated. `EXPLICIT_DIR_FAMILIES`
  names families that no axes string may select (§8.1).
- Vacuum-equivalence nodes (a TOA state duplicated at a 40 000 km sensor node; a
  synthesized exact `τ ≡ 1`, `L ≡ 0` target rung at the column top) are **physical
  identities**, not interpolation conveniences — they close the hull to the Gap 95 exo
  handoff (§4.2a).
- **Three interpolation guards, all refusals rather than approximations** (Rule 17): a query
  outside the node hull raises (no extrapolation, ever); a zenith axis is interpolated in
  `sec ζ` and is refused at or past `_MAX_ZENITH_RAD` ≈ 88.8°, where the coordinate diverges;
  and a query field that is *not* an axis is served with the runs' recorded value under a
  `UserWarning` naming the field and the value actually served (CU-167). The one exemption is
  exact, not tolerant: a query sensor above a recorded at-or-above-`h_atm_top` sensor sees an
  identical column.

The family catalogue with coverage lines is guide §3; per-file provenance and packaging
decisions are that tree's `MANIFEST.md`; the dispatch table is derived from
`SHIPPED_FAMILIES` so there is one authority.

*Depth*: what a library family is, the log-τ and sec-ζ interpolation identities, and the
vacuum-equivalence proofs → theory §3; cross-backend agreement measurements → parity §2.9.

### 3.3 Exo-atmospheric

For sensors above the atmosphere observing targets above the atmosphere (space
surveillance, satellite-to-satellite imaging, deep space). All three spectral outputs are
constants:

```
τ_atm(λ) ≡ 1.0
L_path(λ) ≡ 0.0
L_atm_down(λ) ≡ 0.0
```

This is not "no atmosphere"; it is "the atmosphere is the cosmic vacuum, and the cosmic
vacuum has unity transmittance and zero path radiance to within a part in 10²⁰." The CMB
contribution is delivered through `SourceStage` as a `BlackbodyBackground(T=2.7)`, not
through `AtmosphereStage` (RADIANT_Source_Target_System.md §3.7).

**Inputs**: none. Selection is implicit from `geometry.observer_type = "space"` and
`geometry.target_type = "space"`. An explicit `atmosphere.model = "exo"` for a ground
observer is a logged warning.

### 3.4 MODTRAN

The high-fidelity option, with two flavors and a fixed precedence (§5). **Tape7 file
import** (primary): `atmosphere.modtran.tape7_path` names a tape7 produced elsewhere;
RADIANT parses it pre-chain, converts units, and carries it to the chain grid — no binary
required. **Binary invocation** (secondary, never yet exercised): RADIANT renders a card
deck, invokes the binary, parses the tape7, and caches the converted arrays.

**Inputs** (§6.4): `atmosphere.modtran.tape7_path` for the file flavor, or
`atmosphere.modtran.atmosphere_profile`, `.aerosol_model`, `.h2o_scale`, `.o3_scale`,
`.cloud_model`, `.binary_path`, `.cache_dir` for the binary flavor, plus all `geometry.*`.

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

Per RADIANT_Conventions.md §5, all angles are stored in radians internally; `_deg` suffixes
mark the user-facing API contract.

### 4.2 Slant path length

Computed once at `AtmosphericGeometry` construction and stored for every model to use:

```
L_slant = Δh_absorbing / cos(ζ)          for the whole legal domain 0 ≤ ζ ≤ 89.5°
```

with `Δh_absorbing = min(|h_sensor − h_target|, h_atm_top − min(h_sensor, h_target))` — the
vertical extent of *atmosphere* on the segment, not the endpoint separation (CU-255: a
ground site viewing a 700 km target traverses 100 km of air, not 700 km). Air mass
`m = L_slant / Δh_absorbing` is stored alongside and is therefore exactly `sec(ζ)`;
`Δh = 0` (a wholly exo path) returns `m = 1` by the `ExoAtmosphere` convention.

**One formula, no branch (CU-274).** A second "spherical-Earth correction" branch that took
over past 80° was deleted: it was the *geometric chord* of a slab, not a density-weighted
path, and it made the air mass drop discontinuously across its own switch.
`AtmosphericGeometry.air_mass()` is now the honest plane-parallel primitive, continuous and
monotone in ζ.

**Accuracy past 80° is bought by routing elsewhere, not by patching this formula.** The
exact spherical slant integral lives in `atmosphere/grazing_column.py`, and **every** column
hands over to it — per species — at the single shared threshold `SPHERICAL_SWITCH_RAD` = 80°,
through `atmosphere/near_horizon_air_mass.py`:

| Call site | Inside the band (ζ ≤ 80°) | Past it |
|---|---|---|
| `segment_simple.column_segment_optical_depth` | `od_vert × air_mass()` | per-species spherical |
| `SimpleAtmosphere.evaluate` — `tau_up`, `tau_full_up` | `od_vert × air_mass()` | per-species spherical |
| `SimpleAtmosphere.evaluate` — `tau_sun` | `od_vert × air_mass()` | per-species spherical |

The hand-over is a **step, not a blend**: the residual discontinuity is the plane-parallel
model's own error at the point where it is retired, and it moves transmittance *up*, never
down. Removing it entirely would mean using the spherical integral at every zenith, which
re-baselines every existing down-looking result and is a separate, owner-gated decision.
*The solar column's 89.5° clamp retires with it* — the spherical route has no ceiling, so a
twilight scene at θ_s = 89.9° gets its own column; `ZENITH_CEILING_RAD` still bounds
`path_zenith_rad`, so the *observer* domain is unchanged.

**Anchoring status.** The spherical integral is anchored analytically (Chapman's grazing
limit); refraction is unmodelled and is the dominant geometric error inside the horizon
guard's warn band, so numbers past ~85° are a better-conditioned model, not a validated one.

*Depth*: the air-mass derivation and the per-species spherical column → theory §2.7;
the measured `sec ζ` error, the hand-over step size, and the first anchors past 60° →
parity §2.4; the operator consequence → guide §6.

### 4.2a Exo-altitude targets — the vacuum target leg (Gap 95)

A target at or above the top of the atmospheric column (`los.h_tgt ≥ los.h_atm_top`,
default 100 km — a satellite, a post-burnout booster, a 100+ km hypersonic) is legal
geometry and is served **model-agnostically** by the down-looking exo arm of
`atmosphere/topology.py::evaluate_path_topology`, which `AtmosphereStage` calls in place of
a bare `model.evaluate`. It is expressed as the ADR-0011 **path-segment composition** it
always was: the path partitions at `h_atm_top` into a ground→target column `G` (the
backend's own full column, from a surface-target evaluation) and a vacuum target→sensor
segment `V` (`τ_V ≡ 1`, `L_V ≡ 0`, no model consulted). The composition rules
`τ(G ∪ V) = τ_G·τ_V`, `L(G ∪ V) = L_G·τ_V + L_V` collapse by those identities to exactly the
published fields — **with no arithmetic performed at all**:

- `τ_up ≡ 1`, `L_path_up ≡ 0`, `τ_sun ≡ 1` — exact identities (no absorber above the column
  top), not approximations; no warning is emitted.
- `τ_full_up`, `L_path_full`, `E_TOA` and the `E_sky` terms come from the same backend
  evaluated at the surface-target geometry (`h_tgt = 0`, same angles). This is a
  **down-looking** construction, kept because a down-looking LOS continues past an exo
  target to the ground.
- **Up-looking / level exo path.** When the sensor sits at or below the target, the LOS
  continues into space. Such a path takes this arm only when its **lower** endpoint is
  itself at or above `h_atm_top` — both endpoints outside the column, so the whole path
  *and its continuation* are vacuum and the full-column terms are the vacuum identities too
  (`τ_full_up ≡ 1`, `L_path_full ≡ 0`, `E_sky ≡ 0`; `E_TOA` still from `radiant.core.solar`).
  This is the space-to-space case (LEO→GEO). An up-looking path whose lower endpoint is
  still inside the column is routed to the §4.2b up-looking composition instead, where the
  illumination collapses to the same vacuum identity while the observer leg is evaluated
  properly.
- Works for **every** backend, including single-column file imports that refuse
  endo-atmospheric elevated targets — in this regime one column is all the physics needs.
- **Documented conflation:** the single `E_sky` pair still carries ground-level downwelling,
  so an exo target's reflected-diffuse term uses Earthshine-magnitude but ground-spectrum
  illumination (negligible against plume/self emission in the driving scenarios).

> **Retirement note (guardrail G4 / Rule 27, 2026-07-26).** This case used to be served by an
> `evaluate_with_exo_target` *wrapper* that called the backend at a substituted geometry and
> overrode fields of the result. G4 requires a carve-out to become a natural case of its
> generalization and the wrapper to be deleted in the same PR, so `atmosphere/exo_target.py`
> is gone and the composition above is the only description. The fold was provably
> bit-identical — a differential run over 3 124 exo configurations compared old and new with
> exact `==`.

`LineOfSightGeometry.slant_range_atm` returns 0 m and `path_airmass_up` the vacuum limit
1.0 for these targets.

### 4.2b Path direction — one source of truth, three topology arms

Since ADR-0011 `LineOfSightGeometry` carries **both** endpoints, and `los.h_sensor` is the
**only** source of the sensor altitude inside `radiant.atmosphere`: no backend `evaluate`
reads `geometry.sensor_altitude_m` from the `ParameterSet` (guardrail G2 — `GeometryStage`
is the one place that reads the parameter and puts it on the LOS). A LOS that does not carry
`h_sensor` raises an actionable error rather than falling back to the parameter
(`atmosphere/_sensor_endpoint.py`).

Direction is **derived from the altitude pair, never declared**, and it *dispatches* rather
than refuses (`atmosphere/topology.py::evaluate_path_topology`):

| `los.los_direction` | Product |
|---|---|
| `down` | The backend's own `evaluate`, **unchanged and not rerouted** — every existing scene is byte-identical. The exo-altitude target is the segment composition of §4.2a over that same call |
| `up` | Segment composition: an observer-leg column keyed to the **sensor** (the lower endpoint), plus reused target-side illumination, plus a sky continuation — §4.2d |
| `level` | Same, with a constant-altitude arm as the observer leg |

The refusal that remains is a **capability** refusal, not a pending-implementation one: the
segment evaluators are built on the simple model's species machinery, so
`atmosphere.model = "simple"` serves up-looking and level paths, `interpolated` serves them
through an up-looking family plus its companion (below), and every other backend raises an
actionable error naming exactly what *is* supported.

**Direction is a first-class property of a run family (GF-10).** A family is tagged `down`
(default, upwelling products) or `up` (downwelling products) at construction, from the
`los_direction` marker on its NPZ files. Three structural properties keep the two from being
confused: the NPZ radiance key differs (`path_radiance_toward_lower` vs `path_radiance`);
every file carries the marker; and the two query entry points — `evaluate()` (the eight-field
down-looking bundle) and `uplooking_column_product()` (the up-looking observer leg) — refuse
each other's families. An up-looking query takes its lower endpoint from `los.h_sensor`
(guardrail G2). A family that carries a `path_zenith_rad` axis serves any zenith inside its
hull; one rendered at a single zenith refuses any other, as it refuses an elevated endpoint
on a ground-rendered family, rather than approximating it.

**The declared hybrid (CU-226; owner-ratified 2026-08-01).** An up-looking run family is
**one leg of data**, so an up-looking chain run on `interpolated` composes two models.
`uplooking_quantities.supports_uplooking` admits two arrangements: a bare `SimpleAtmosphere`,
and an `UplookingColumnBackend` — a structural protocol satisfied by an
`InterpolatedAtmosphere` whose `family_direction` is `"up"` and which carries an
`uplooking_companion`:

| Leg | Served by | Why |
|-----|-----------|-----|
| observer (sensor → target) | the up-looking run family | this *is* the rendered column; it dominates a ground-to-air scene |
| illumination (solar column + sky hemisphere above the target) | the `SimpleAtmosphere` companion | no rung of a sensor→target ladder is the column *above* the target, and the down-looking proxy query an up-looking family would need is refused by construction |
| sky at aperture (sensor → `h_atm_top`) | the `SimpleAtmosphere` companion | reading a partial ladder's top rung as "the sky" would be extrapolation past the hull |

The companion is built pre-chain by `atmosphere.loaders.build_atmosphere_model` (Rule 6)
from the same `atmosphere.*` parameters a `model = "simple"` run would use, and attached
only when the family's direction is `"up"`. Two independently-calibrated models in one
answer is a real modelling compromise, so **it is never silent**: a `UserWarning` is raised,
an INFO record is logged, and
`stage_outputs["atmosphere"]["topology_provenance"]["backend_split"]` names which leg came
from which model. **The owner's ratification is conditional on the compromise staying
declared** — the warning, the INFO record and the `backend_split` marker are part of what
was ratified and must not be softened into silence.

Re-audit condition, and only this one: the split exists because an up-looking run family is
one leg of data. A family that is self-contained — carrying its own solar column and its own
sensor → `h_atm_top` sky — or a scene whose target is a blackbody, where the illumination
terms vanish, makes the companion unnecessary *for that scene*, and the split should be
dropped there rather than declared.

**The exo-target guard — the family is asked, never a hard-coded name.** When the target sits
at or above `h_atm_top`, `_illumination_products` substitutes the exact vacuum identity
(`τ_sun ≡ 1`, `E_sky ≡ 0`). That identity is right for the illumination and says nothing about
the composition it lands in, so with a library-backed observer leg the join at the top of the
modelled column needs an anchor. Whether one exists is a property of the **backing family**,
and `uplooking_quantities._refuse_library_backed_exo_target` reads
`InterpolatedAtmosphere.uplooking_target_ceiling_m` — the highest target altitude the family's
own runs measure:

- **Full column (ceiling ≥ `h_atm_top`) — permitted.** The family integrated the *entire*
  column and the remaining path is vacuum, so the composed observer leg is **identically** the
  family's own top-of-column run. The query side is
  `InterpolatedAtmosphere._vacuum_clamped_target_m`, the **target-axis mirror** of the
  sensor-axis vacuum equivalence the same module already ships, both gated on the shared
  `_VACUUM_EQUIVALENT_ALTITUDE_M`; the clamp is recorded in provenance under
  `exo_target_vacuum_clamp` (Rule 16).
- **Partial column (ceiling < `h_atm_top`, or unrecorded) — refused** with an actionable
  `ParameterBoundsError`: real, unmeasured air lies between the top rung and the target, and
  composing a measured leg with an invented one is what the refusal prevents (Rule 17).

The clamp is gated at `h_atm_top` and nowhere else: a 50 km target through a 20 km ladder is
40 km of real atmosphere and still fails the family's own hull check.
`test_uplooking_backend_dispatch.py` asserts the invariant against the committed node sets —
every bundled up-looking family either stays below `h_atm_top` *and* refuses an exo target, or
reaches it *and* satisfies the identity. `atmosphere.model = "simple"` has no column backend
and keeps the vacuum identity unchanged.

Two further structural refusals. `SegmentQuantities` is deliberately **not** the observer-leg
type on this path: that contract carries both directional radiances and an up-looking family
measures only `L_toward_lower`, so the internal `_ObserverSegment` carries exactly `tau` and
`L_toward_sensor` and the unreachability is structural rather than a comment
(`observer_leg_from_los` sets `toward_sensor = "toward_lower"` on every up-looking column).
And a **level** path on an up-looking family is refused, not approximated: a level arm has
zero vertical extent and a local zenith of π/2 everywhere, so no rung of a column ladder is
that path. MODTRAN tape7-import does not qualify for up-looking at all — its ITYPE=1 deck
geometry is unwritten.

*Depth*: the hybrid's physics rationale → theory §3.7; the measured divergence between the
two legs → parity §2.11; the family catalogue and every refusal's remedy → guide §3 and §5.

### 4.2c The path-segment contract (guardrail G1)

Guardrail G1 forbids serving new path topologies by giving `AtmosphericQuantities` new flat
fields. The unit of composition is instead a **path segment**: one piece of path between two
points, evaluated once, read from either end. `atmosphere/segments.py` owns the contract; the
evaluators (`segment_simple.py`, `segment_thermal.py`, `segment_single_scatter.py`,
`segment_grazing.py`, `level_arm.py`, `level_whole_path.py`) implement it, one computation
per module (Rule 19).

Two spec types, because there are two path topologies and they are not variations of one
form:

| Spec | Fields | Topology |
|---|---|---|
| `ColumnSegmentSpec` | `h_low_m`, `h_high_m` [m], `zeta_low_rad` [rad] | **endpoint-minimum** — the path's lowest point is an endpoint. Column air mass (§4.2) |
| `LevelArmSpec` | `altitude_m` [m], `length_m` [m] | **interior-tangent** — the lowest point is in the middle. True spherical chord at constant density; **no air mass at all** (§4.2f) |

One evaluated product, `SegmentQuantities`, carrying:

- `wavelength_um` [µm] — the chain grid, ascending and strictly positive.
- `tau` — **one** array, dimensionless ∈ [0, 1]. Transmittance is reciprocal (§4.4), so a
  segment has one τ no matter which way it is read. A second direction-tagged τ would be a
  second source of truth for one quantity.
- `L_toward_upper`, `L_toward_lower` [W/m²/sr/µm] — path radiance **is** direction-specific,
  so it is two fields. They differ because the emitting and scattering layers are weighted by
  the transmittance of the material *between* them and the receiver, and that weighting
  reverses with direction.

**The lower-endpoint convention** (ADR-0011 decision 3). Every column segment's zenith is
keyed to its **lower** endpoint. Two structural reasons: it is the one endpoint the two
travel directions share, so a single scalar describes the segment rather than the reading of
it; and it is the angle MODTRAN's Card 3 wants when `H1 ≤ H2` (§5.2), so no convention
translation sits between RADIANT and its truth source. A level arm has no column zenith at
all — its 90° is an interior-tangent quantity, not an air-mass argument — which is why
`LevelArmSpec` carries a length instead.

**The validity ceiling and the refused sliver.** `zeta_low_rad` is bounded at
`ZENITH_CEILING_RAD` = 89.5°, the column air-mass validity ceiling. A zenith in the sliver
**(89.5°, 90°)** is *geometrically* admissible, and the horizon guard only **warns** there
for an endpoint-minimum path; but there is no trustworthy column air mass in that band, so
`ColumnSegmentSpec` **refuses** it with an actionable error rather than returning a
plausible-looking wrong number (Rule 17). The two layers disagreeing is deliberate: geometry
judges whether the *path* is modellable, the segment spec judges whether the *column air
mass* is. A near-horizontal path in that sliver is an interior-tangent path and belongs in a
`LevelArmSpec`, which carries no air mass and is therefore unaffected by the ceiling.

### 4.2d Direction-aware composition — up-looking and level paths

Gaps 108/109. An up-looking or level scene is a **composition of path segments** — guardrail
G1: the eight-field `AtmosphericQuantities` contract is unchanged; what changes is which
segment fills the observer-leg slots — built by `atmosphere/uplooking_quantities.py`:

```
observer leg = segment(target ↔ sensor)       → tau_obs, L_obs→sensor
illumination = target-side products, reused   → tau_sun, E_TOA, E_sky_*
continuation = segment(target → space)        → L_sky

L_t,aperture  = [ε·B(T_t) + ρ·τ_sun·E_TOA·cos θ_s/π + ρ·E_sky/π] · tau_obs + L_obs→sensor
L_bg,aperture = L_sky · tau_obs + L_obs→sensor
```

The target equation is the **unmodified §2 assembly equation with the observer leg swapped**,
so `assembly.assemble_target_at_aperture` is reused verbatim and every T-code works
up-looking with no new arms.

- **Observer leg** (`atmosphere/observer_leg.py`). Up-looking: a `ColumnSegmentSpec` from
  `h_sensor` to `h_tgt` keyed to the sensor's zenith `ζ_low = π − η` (ADR-0011 decision 3),
  read in the `toward_lower` direction. Level: a `LevelArmSpec` whose length is the true
  spherical chord, read `toward_upper`. The sun's relative azimuth is re-expressed in the
  segment's frame (`Δφ_seg = Δφ − π` up-looking). **Transmittance is reciprocal**: the same
  physical line expressed down-looking and up-looking gives the same `τ` to within an ULP,
  and exactly for the vertical case.
- **Illumination leg.** `τ_sun`, `E_TOA` and the two `E_sky` terms describe the *target's*
  environment and are direction-agnostic, so they are reused from a proxy down-looking
  evaluation at the same `h_tgt` and solar angles with the sensor at `h_atm_top` and
  `θ_o = 0`. With the proxy sensor at the column top the `E_sky_scattered` slab coincides
  with the `E_sky_thermal` slab, so both diffuse components mean "the sky above the target",
  which is what an up-looking scene means by them. An exo-altitude target takes the vacuum
  identities instead (§4.2a).
- **Continuation / `SkyBackground`.** The LOS continuation leaves the target at
  `ζ_c = π − θ_o`; `core/los_termination.py` classifies where it ends. Inside the 89.5°
  column ceiling it is `sky_radiance.sky_radiance_along_los`; past it — every level arm
  shorter than ≈ 111 km — it is the true spherical slant integral
  (`atmosphere/segment_grazing.py` over `atmosphere/grazing_column.py`). For an exo target
  the continuation is vacuum and `L_sky ≡ 0`, so the background reduces to the observer
  leg's own emission.
- **`tau_full_up` / `L_path_full` carry the observer leg** for these topologies: the LOS
  terminates on space, so the background source plane *is* the target plane. An explicit
  `GroundBackground` on an up-looking or level path is refused (there is no ground behind
  the target — `AtmosphereStage`).

### 4.2e Per-altitude solar illumination (GF-9, ratified decision 21)

The global `θ_s < π/2` bound is replaced by a per-altitude shadow-height test.
`geometry.solar_zenith_rad` and `AtmosphericGeometry.solar_zenith_rad` span the closed
`[0, π]`; whether a given point is lit is decided by `atmosphere/solar_shadow.py`, and a
sunlit target past π/2 takes its direct beam from the two-arm tangent transit of
`atmosphere/solar_transit.py` rather than a descending column. A **shadowed** target has
`τ_sun` exactly 0 (no beam at all) and an already-identically-zero scattered-sky solar
component; the thermal sky is untouched. The modelling assumption is a **sharp terminator**
— opaque sphere, point Sun, no refraction.

> **PROVISIONAL.** The twilight transit carries the largest optical depths anywhere in
> RADIANT and its transmittance is **unanchored** — the delivered twilight decks are
> `dev_only`, consumed by no family and no parity test. Treat it as an order-of-magnitude
> bound (parity §3 item 11).
>
> Note also that RADIANT models the target as a horizontal Lambertian facet, so assembly
> multiplies the direct-solar term by `cos θ_s` clamped at zero. For any `θ_s > π/2` that
> factor is zero and the direct term vanishes regardless of `τ_sun` — the beam arrives from
> below the facet. `τ_sun` is still published correctly because it is an inspectable
> physical quantity (Rule 16) and a non-horizontal target model would consume it.

**Zero drift**: every scene with `θ_s ≤ π/2` keeps the backend's own solar column, untouched.

*Depth*: the shadow-height and tangent-transit derivations → theory §2.13.

### 4.2f The constant-altitude arm — the level path (A5)

A level or near-level path (`los_direction == "level"`) cannot be served by the column
machinery at all, and the reason is structural rather than a matter of accuracy: a column
segment's optical depth between two *equal* altitudes is **exactly zero**, and its air mass
is a plane-parallel `sec ζ` that is undefined at ζ = π/2. The level arm is an
**interior-tangent** topology — its lowest point is in the middle, not at an endpoint — so
it gets its own spec type (`LevelArmSpec`) and its own evaluator (`atmosphere/level_arm.py`),
per Rule 19. Its τ is a pure exponential in the **true spherical chord** between the
endpoints, using the *local* extinction at the arm's altitude; no new calibration is
introduced.

**Constant-density assumption, and where the guard stops it.** The arm is a straight chord of
uniform density. On a spherical Earth the chord dips below its endpoints by the tangent-height
depression `Δh ≈ L²/8R_E` (mean sag `≈ (2/3)Δh`), so the real path samples slightly *denser*
air and the model **under-states** optical depth. The horizon guard is what bounds the error —
it admits `Δh < 100 m` clean, warns to 2 km, and raises beyond. Worked against the 2 km water
scale height (the record for these thresholds):

| Guard band | Δh | Mean sag | Water-density error |
|---|---|---|---|
| clean edge | 100 m (L ≈ 71 km) | 67 m | 3.4 % |
| L-grid longest arm | 196 m (L = 100 km) | 131 m | 6.8 % |
| raise threshold | 2 km | 1.33 km | ≈ 1.9× (90 %) |

The last row is *why* 2 km raises rather than warns — a two-fold understatement of water
optical depth is not a caveat, it is a wrong answer (Rule 17).

The arm's exponential `τ(2L) = τ(L)²` is the model's own claim, and it is exactly where a
correlated-k band model disagrees; long-range MWIR horizontal work therefore needs a MODTRAN
or interpolated backend. MODTRAN's own horizontal path type is `ITYPE=1`, wired through
`ModtranConfig.hrange_km` (§5.2).

*Depth*: the arm and whole-path formulations → theory §2.12; the measured arm-vs-MODTRAN
divergence → parity §2.6; the operator consequence → guide §6.

### 4.2g Sky radiance along the LOS — the `SkyBackground` product (Gap 108)

The one genuinely **new** product of the direction-aware topologies. It is the radiance a
receiver at `h_start` sees looking **up** along a ray of zenith ζ with nothing behind the
atmosphere but cold space, and it is what a sensor sees *behind* an airborne target. The
2.7 K cosmic background contributes < 1e-9 W/m²/sr/µm anywhere in the 0.3–14 µm working
range and is deliberately not modelled, so the "compose with what lies beyond" step is a
no-op and `atmosphere/sky_radiance.py` is a thin, well-named wrapper over `segment_simple.py`
rather than a second physics implementation.

**Where the ray starts: the sensor, not the target (CU-254, 2026-07-29).** The quantity
handed to assembly is `TopologyProducts.sky_radiance_at_aperture` [W/m²/sr/µm] — the whole
LOS from the *sensor* out to `h_atm_top`, i.e. what the aperture would measure if the target
were not there. The retired form held the sky at the **target** plane and re-propagated it as
`L_sky·τ_full_up + L_path_full`. That composition is exact radiative transfer, but the segment
model being composed is *not* additive: each segment emits at its own effective temperature,
so splitting one column at the target plane swaps part of a warm ground-anchored graybody for
a cold target-anchored one. Measured on the shipped 10.1 config, varying only
`geometry.target_altitude_m` at fixed pointing:

| target altitude | `background_e` before | after |
|---|---|---|
| 10 km | 1.94207e5 e⁻ | 2.21479e5 e⁻ |
| 20 km | 2.14046e5 e⁻ | 2.21479e5 e⁻ |
| 99 km (whole column) | 2.21479e5 e⁻ | 2.21479e5 e⁻ |

A background behind a target cannot depend on where along the ray the target sits; the
surviving value is the ground-rooted one, which is also the geometry the MODTRAN up-looking
runs anchor. The `SkyBackground` arm is consequently a **pass-through** — `τ ≡ 1`,
`L_path ≡ 0` — and must not consult `τ_full_up` / `L_path_full` at all.

**The level topology is one whole path too.** `atmosphere/level_whole_path.py` evaluates
"constant-altitude arm then ascending arc" as a single segment, called once by
`uplooking_quantities._level_sky_at_aperture`, so the sky has one τ and one effective
temperature and carries no constant-density approximation. A zero-length arm reduces the
whole-path evaluator **exactly** to `segment_grazing.evaluate_grazing_segment` at ζ = π/2, so
the level and ascending sky topologies join without a step. `level_arm.py` is **not**
superseded by it (Rule 27): the arm still computes the observer leg, a different path between
different endpoints.

Two things this product is **not**:

- It is not `AtmosphericQuantities.E_sky_thermal`. That is a hemispheric downwelling
  **irradiance** [W/m²/µm] used for surface reflection; this is a directional **radiance**
  [W/m²/sr/µm] along one ray. Different quantity, different unit, different geometry.
- It is not a field on `AtmosphericQuantities` (guardrail G1). It rides alongside the
  eight-field bundle on `TopologyProducts.sky_radiance_at_aperture`.

A missing or off-grid `sky_radiance_at_aperture` **raises** rather than defaulting to zero: a
silently-zero sky background would delete the background photon term and therefore *inflate*
SNR, which is the exact failure mode Rule 17 forbids.

**Band gating (locked decision 20).** The thermal component is first-class at first delivery
— it is anchored directly against the real MODTRAN up-looking runs. The scattered-solar
component rests on a single-scatter approximation known to under-predict the daytime VIS/NIR
sky. A `UserWarning` is emitted when **both** conditions hold: the evaluation grid extends
below `sky_radiance.SCATTERED_SKY_PROVISIONAL_MAX_UM` (3 µm) **and** a solar geometry with
the sun above the local horizon is supplied. A pure-thermal MWIR/LWIR call warns about
nothing, and neither does a night scene on a VIS grid.

> **Coupling caveat (found 2026-07-26, not yet repaired).** Whether the sky carries a
> scattered-solar component at all is gated by `los.theta_s`, and
> `source/_inferrer._adjust_scene_los` strips `theta_s` for a **T1Thermal** target (the
> CU-009 predicate: "a pure-thermal radiance has no solar leg"). That predicate was complete
> when the target was the only consumer of `theta_s`; the sky background is now a second
> consumer whose solar dependence has nothing to do with the target's material. Consequence:
> a pure-thermal target on a VIS/NIR grid gets a **thermal-only sky at noon**, and no
> provisional warning, because the trigger condition is never met. Pinned as a
> characterization by
> `tests/integration/test_direction_aware_atmosphere.py::TestProvisionalScatteredSkyWarning`.

**Near-horizon: hand over at 80°, not 89.5°.** Past `SPHERICAL_SWITCH_RAD` the sky is
evaluated as a true spherical slant integral instead of by the plane-parallel column form.
The hand-over sits at 80° because that is where the column form's air mass genuinely expires
(§4.2), not at the 89.5° ceiling. The species proportions that set ω₀ and the phase function
are weighted at the segment's **lower endpoint** in every evaluator, and all three evaluators
linearise the calibrated column terms against the **slant** column — one convention, so the
hand-over step is uniform across bands rather than a spectral artefact of two evaluators
disagreeing.

*Depth*: the sky-radiance and whole-level-path formulations, and the lower-endpoint
species split → theory §2.9 and §2.12; the hand-over step, the species-split adoption
measurement, and the level whole-path comparison → parity §2.3, §2.4 and §2.13.

### 4.3 How geometry feeds each model

| Model | Slant path effect | Solar zenith effect |
|-------|-------------------|---------------------|
| Simple | Recomputed per geometry: species columns and air masses re-evaluated for `(h_sensor, h_target, ζ)` | Drives the single-scatter `L_path` and `τ_sun`; the downwelling is target-anchored (sensor altitude does not enter) |
| Interpolated | Interpolated over the family's declared axes; **refused** outside the node hull. A non-axis field is served with the runs' geometry, with a `UserWarning` | Same rule: an axis if declared, otherwise the runs' sun with the mismatch warning |
| Tabulated | **None.** Files are taken at face value. `GeometryDrift` warning if geometry changes after load | None |
| Exo | None | None |
| MODTRAN | File flavor: none. Binary flavor: set into the card deck (Card 3 `H1`, `H2`, `ANGLE`); MODTRAN computes the slant path internally | Binary flavor: Card 3A1 (`IPARM`, `PARM1`, `PARM2`); MODTRAN computes single + multiple scatter |

The simple model and the MODTRAN binary interface both *recompute* their outputs whenever
geometry changes; the interpolated backend re-queries; tabulated and tape7-import do not.
This is the user-visible price of choosing a file-backed geometry-agnostic input.

### 4.4 Reciprocity and the upwelling/downwelling distinction

For unpolarized broadband radiation, transmittance is **reciprocal**:
`τ(sensor → target) = τ(target → sensor)`. RADIANT exploits this — only one transmittance is
computed per slant path, and `SegmentQuantities` carries one `tau` for both readings (§4.2c).
Path radiance is *not* reciprocal: the sensor-bound (`L_path`, "upwelling") and source-bound
(`L_atm_down`, "downwelling") radiances differ because of where the scattering and emission
happen relative to the receiver. Both are computed independently and are never interchanged.

Non-reciprocal does not mean *different physics*. Both directions carry the same two terms —
single-scatter solar plus Kirchhoff emission `(1 − τ)·B(λ, T_eff)` (§3.1) — and differ only
in the scattering angle and the escape endpoint the emission temperature is resolved from.
The model still under-states the true directional spread, because a one-slab graybody makes
emission direction-symmetric by construction and only the scattering term breaks the
symmetry.

`L_atm_down` (surfaced in `AtmosphericQuantities` as the `E_sky_thermal` / `E_sky_scattered`
**irradiance** pair) is consumed by the reflected-diffuse term of the target and
ground-background arms, and by any `ReflectedSolarSource` whose downwelling spectrum is tied
to the atmospheric model rather than a top-of-atmosphere standard. The atmosphere module
*produces* it; it does not consume it.

**Not to be confused with the `SkyBackground` product.** The `SkyBackground` descriptor
consumes a *directional radiance along the LOS continuation* (§4.2g,
`TopologyProducts.sky_radiance_at_aperture`, W/m²/sr/µm), never the hemispheric irradiance,
and the irradiance's real consumers are the reflective terms. The two are separate products
computed by separate modules; conflating them would put a hemispheric integral where a single
ray belongs.

*Depth*: the measured reciprocity residual and the up/down asymmetry → parity §2.8.

---

## 5. MODTRAN Interface

This section defines the file and binary boundary between RADIANT and MODTRAN. Everything
that depends on MODTRAN file formats lives in `radiant.atmosphere.modtran` — the tape7 import
(`Tape7Import`), the deck builder (`render_tape5`), the parser (`Tape7Reader`), the flux
reader (`ModtranFluxReader`), and the cache. **No other module may know what a tape5, tape7,
or `.tp7` file looks like.**

There are **two ways in**, with a fixed precedence:

1. **Tape7 file import (§5.1) — the primary workflow.** `atmosphere.modtran.tape7_path`
   names a tape7 produced elsewhere. When set, the file wins unconditionally: the binary, the
   cache, and the fallback are never consulted.
2. **Binary invocation (§5.2–§5.5) — secondary, never yet exercised.** With `tape7_path`
   unset, RADIANT renders a tape5 deck and drives a locally-installed `modtran` executable,
   with caching and an opt-in fallback.

**Verification status.** Both the **parse** side and the **deck** side are validated against
the owner-run MODTRAN 6 run set: tape7 output round-trips through the reader, and the
field-position conventions RADIANT *writes* are confirmed by three-way agreement
(`render_tape5` output = the run matrix's hand-worked column = the delivered tape7's card
echoes) over every delivered slant row, including the elevated-lower-endpoint case that pins
the Card-3 ANGLE convention and the ITYPE=1 rows whose Card-3 `RANGE` is compared as well.
Still external: RADIANT has not itself *invoked* a MODTRAN binary — the runs were delivered
as files. The row-by-row evidence is parity §1.1 and §1.2.

### 5.1 Tape7 file import (primary workflow)

Setting `atmosphere.modtran.tape7_path` (with `atmosphere.model = "modtran"`) builds the
atmospheric state from an existing tape7 file:

- **Rule 6 boundary**: the file is parsed **before chain execution**, in
  `radiant.atmosphere.loaders._build_modtran`, via `Tape7Reader.to_radiant_units()`. The
  parsed arrays travel as a `Tape7Import` (frozen dataclass: four ascending-wavelength arrays
  + `source_path` + `content_key` = sha256(file bytes)[:16]) into `ModtranAtmosphere`, which
  carries them to the chain grid exactly the way the binary path's cache-hit branch does —
  every τ-like column in **log-τ** per the universal convention (§3.2), the radiances
  linearly. `AtmosphereStage` never reads the file; with `tape7_path` set, `modtran` counts
  as file-backed for the stage's Rule 6 refusal check (`loaders.model_requires_prebuild`).
- **Precedence**: file set → file wins; binary, cache and `allow_fallback` are irrelevant.
  File unset → §5.2–§5.5 behavior, bit-identical to before the import path existed.
- **Geometry-agnostic**, like tabulated input: the imported arrays are served as-is for any
  query geometry. Consequently an airborne target (`h_tgt > 0`) raises `NotImplementedError`
  **unless** a second target→sensor run is imported via `atmosphere.modtran.tape7_up_path` —
  a single file cannot supply both the target-leg and the full-column transmittance the
  background branch needs.
- **Airborne-target two-leg split (Gap 94, file flavor)**: `tape7_up_path` names a run along
  the target→sensor partial column. When set, `τ_up` / `L_path_up` come from that file,
  `tape7_path` keeps supplying the ground→sensor full column, and airborne targets are
  accepted. RADIANT cannot verify the file's H2 against the scenario's `h_tgt` (a tape7 does
  not record its deck geometry) — the user owns that consistency, as with every file import.
- **Sun-leg two-leg split (CU-011, file flavor)**: `tape7_sun_path` names a run along the
  sun→target slant path. When set, `τ_sun` comes from that file and the single-τ collapse
  `UserWarning` is not emitted; with only `tape7_path`, `τ_sun` aliases `τ_up` with the
  warning.
- **Downwelling**: a standard IEMSCT=2 tape7 carries no downwelling column, so on a bare
  import `L_atm_down ≡ 0` and both `E_sky` terms are zero, with a loud Gap 81 `UserWarning`.
- **Flux-file downwelling (CU-157, file flavor)**: `flux_path` names the run's spectral flux
  CSV. When set, the ground-level **DOWN** column supplies the real hemispheric downwelling
  (`L_atm_down = DOWN / π`), split at the reflective-solar / thermal boundary (4 µm,
  `_FLUX_REFLECTIVE_SOLAR_MAX_UM`) into `E_sky_scattered` and `E_sky_thermal`, superseding the
  Gap 81 zeros. The boundary is a **labelling** choice only: assembly consumes the sum, which
  equals the full DOWN column regardless of the split (owner-ratified band-split, Gap 38).
- Each of `tape7_sun_path`, `tape7_up_path` and `flux_path` **requires** `tape7_path`; any of
  them alone is a configuration error.
- **Equivalence guarantee**: importing a tape7 directly produces chain outputs identical to
  the historical side-door (`Tape7Reader` → full-precision CSVs → `model = "tabulated"`);
  `tests/integration/test_modtran_tape7_import.py` asserts exact equality.
- **Provenance**: `derivation_chain` records the source path and `content_key`;
  `SpectralData.source_parameters` carries `cache_key="tape7-file:<content_key>"`.

### 5.2 Card deck builder

`ModtranConfig` is a dataclass holding the MODTRAN knobs RADIANT exposes; the free function
`render_tape5(config, geometry)` emits the fixed-format tape5 string. RADIANT does not expose
every MODTRAN knob — only the ones that matter for the in-scope use cases:
`atmosphere_profile` (MODEL 1–6), `aerosol_model` (IHAZE), `h2o_scale` / `o3_scale` (Card 2C
column scaling), `visibility_km` (Card 2 VIS; `None` = IHAZE default), `itype` (Card 1 path
geometry; default 2 = slant path H1→H2), `iemsct` (Card 1 mode; default 2 = thermal+solar path
radiance, 3 = solar irradiance), `hrange_km` (Card 3 RANGE — the horizontal path length in km;
meaningful only for `itype=1`), `spectral_resolution_cm1`, `v1_cm1` / `v2_cm1` (Card 4), plus
`binary_path`, `cache_dir` and `allow_fallback`.

**Cards RADIANT writes** (1, 1A, 2, 2C, 3, 3A1, 4, 5). Geometry comes from
`AtmosphericGeometry`: H1/H2 from sensor/target altitude; **Card 3 ANGLE** is converted from
`path_zenith_rad` (measured at the path's lower endpoint, §4.1) to MODTRAN's zenith-at-H1
convention — down-looking (H1 above H2) renders `180° − zenith` (nadir-from-space → 180°),
up-looking renders the zenith unchanged. **ITYPE=1 (horizontal, constant-altitude) is the one
path type where ANGLE is not derived from `path_zenith_rad`**: MODTRAN builds the path from H1
plus Card 3 RANGE and ignores H2/ANGLE, so `render_tape5` writes the literal 90° a level path
has by definition and takes the path length from `ModtranConfig.hrange_km`. A level path's 90°
is an interior-tangent quantity, not a column zenith, so `AtmosphericGeometry` correctly
refuses to carry it and the horizontal branch does not consult it. `ModtranConfig` refuses
`itype=1` without `hrange_km` (a zero-length path) and `hrange_km` outside `itype=1`
(over-specification). Because `hrange_km` is 0.0 for every non-horizontal deck and
`f"{0.0:10.3f}"` is exactly the ten-character literal the RANGE field previously held, every
ITYPE ∈ {2, 3} deck renders byte-identically to the pre-wiring builder. Solar zenith/azimuth
go on Card 3A1 (IPARM=2). IMULT=1 (multiple scattering) is fixed. Anything not exposed is left
at the literal values in `render_tape5`; `ModtranConfig.extra_cards: dict[str, str]` lets
advanced users override a whole card line, and the override is part of the rendered deck and
therefore of the cache key.

The deck is rendered to a tape5 in a per-run temp directory. RADIANT does *not* edit a
user-supplied tape5 — the deck is built from scratch every run, so reproducibility is owned
entirely by the parameter set, not by a hand-tuned input file.

### 5.3 Tape7 parser

`Tape7Reader` parses the fixed-column tape7 file into a `ModtranNativeOutput` dataclass:

```python
@dataclass(frozen=True)
class ModtranNativeOutput:
    wavenumber_cm1: np.ndarray           # cm⁻¹, MODTRAN-native descending order
    total_transmittance: np.ndarray      # dimensionless
    path_thermal_radiance: np.ndarray    # W/cm²/sr/cm⁻¹ (PTH THRML / THRML_EM)
    path_scattered_radiance: np.ndarray  # W/cm²/sr/cm⁻¹ (SOL SCAT, or MULT_SCAT+SING_SCAT)
    ground_reflected_radiance: np.ndarray  # W/cm²/sr/cm⁻¹ (GRND RFLT / GRND_RFLT)
    header: dict[str, Any]               # raw header lines (card echo etc.)
```

The other real tape7 columns (`THRML SCT`, `SURF EMIS`, `SNGL SCAT`/`SING_SCAT`, `DRCT RFLT`,
`TOTAL RAD`) are located by the parser but not yet consumed.

**Column identification.** Columns are located by their tape7 header LABEL, matched by
left-to-right order of appearance in the header line — **not** by a fixed token/character
position, which varies by MODTRAN version and does not survive multi-word labels. Two label
vocabularies are recognised, so one reader serves either binary: the **classic**
space-delimited names (`TOT TRANS`, `PTH THRML`, `SOL SCAT`, `GRND RFLT`, …) and **MODTRAN
6**'s underscore names (`TOT_TRANS`, `THRML_EM`, `GRND_RFLT`, …), which split the classic
combined `SOL SCAT` column into `MULT_SCAT` + `SING_SCAT` (summed; the classic `SOL_SCAT`
column, when present, takes priority and is not double-counted). MODTRAN's `-9999.`
end-of-block sentinel is detected by its column-count mismatch and excluded. A header lacking
a required column raises `Tape7ParseError`. Files with no recognisable header (hand-authored
fixtures) fall back to the pre-fix positional assumption with a `UserWarning`; that fallback
must not be relied on for MODTRAN-derived results.

**Unit conversion** happens in `to_radiant_units()`, which returns four ascending-wavelength
arrays — `(wavelength_um, transmittance, path_radiance, ground_reflected)`:

1. Spectral axis: `λ [µm] = 10⁴ / ν [cm⁻¹]`, sorted ascending.
2. Radiance: `L(λ) [W/m²/sr/µm] = L(ν) [W/cm²/sr/cm⁻¹] · ν²` — the single factor `ν²`
   combines the cm⁻²→m⁻² area conversion (10⁴) with the spectral Jacobian
   `|dν/dλ| = ν²/10⁴`.
3. Transmittance is dimensionless and unchanged.

The conversion is implemented exactly *once*, in this method (Rule 2). No other module
performs cm⁻¹↔µm or W/cm²↔W/m² arithmetic.

**Flux table reader (`ModtranFluxReader`).** MODTRAN 6's irradiance runs write spectral
irradiance to a separate `*_flux.csv` sidecar, not the tape7 — a `case index … { … }` block
with, per atmospheric level, three columns: upward-diffuse (`UP`), downward-diffuse (`DOWN` =
thermal emission + scattered solar), and direct solar beam (`SOLAR`). `parse()` returns a
`ModtranFluxOutput` (`wavenumber_cm1`, `altitude_km`, and `flux_up`/`flux_down`/
`flux_direct_solar` shaped `(N_freq, M_levels)`) in native W/cm²/cm⁻¹; `to_radiant_units()`
returns the ground-level `(wavelength_um, e_direct, e_diffuse_down)` in W/m²/µm using the
**same** `ν²` Jacobian (spectral flux has no per-steradian factor to alter it). The DOWN
column is wired into the chain via `atmosphere.modtran.flux_path` (§5.1); the `SOLAR` column
is parsed and retained on `FluxImport` for provenance but is not yet consumed — the
direct-solar branch of the assembly still uses `E_TOA · τ_sun`.

### 5.4 Cache

MODTRAN runs are slow (seconds to minutes). The cache is keyed by a deterministic hash of the
rendered tape5, and stores the **parsed, unit-converted arrays** (not the raw tape7):

```
cache_key  = sha256(rendered_tape5 + "\0" + binary_fingerprint).hexdigest()[:16]
cache_path = cache_dir / f"{cache_key}.npz"    # wavelength_um, transmittance,
                                               # path_radiance, ground_reflected
```

On a run: render tape5 → compute key → on hit, load the `.npz` and skip MODTRAN; on miss,
invoke the binary in a temp directory, parse the tape7, save the arrays, proceed. The
`binary_fingerprint` is a hash of the MODTRAN executable's bytes (`exe:<sha256[:16]>`, falling
back to the path when unreadable), so **an upgraded binary invalidates stale entries** rather
than silently reusing the old version's results. It is computed by reading the executable's
bytes, never by invoking it; a `modtran -version` form can supersede the byte hash once the
binary-invocation path is first exercised.

Cache eviction is **manual** — RADIANT never deletes cache entries on its own; remove files
from `cache_dir` (default `~/.radiant/modtran_cache`) by hand. Entries are small, so
accumulated cache is megabytes, not gigabytes.

### 5.5 Error handling when MODTRAN is unavailable

(Applies to the binary path only — the tape7 import never consults the binary.)

The MODTRAN binary may be missing for legitimate reasons: CI runners, students, contractors
without licenses. RADIANT degrades in this order:

1. **Cache hit**: if the rendered tape5 hashes to a key already in the cache, return it. The
   user never knows MODTRAN was missing.
2. **Cache miss with `allow_fallback = True`** (default `False`): log a warning and build the
   state from `SimpleAtmosphere` at the equivalent profile/aerosol settings.
3. **Cache miss with `allow_fallback = False`**: raise `ModtranUnavailableError` naming the
   missing binary path and the two remedies (install MODTRAN / enable the fallback).

Fallback is opt-in because a user running a sensitivity study almost always wants to know that
MODTRAN silently disappeared from under them.

---

## 6. Parameter Inventory

All parameters live under the `atmosphere.*` namespace. Names follow
RADIANT_Parameter_System.md §"Naming rules" (lowercase, no unit suffix on the canonical name,
two-deep namespace). Where the user-facing input has a unit different from the internal
storage unit, the user-facing parameter carries a `_<unit>` suffix per RADIANT_Conventions.md
§5.

Types, defaults, units, and bounds are the canonical
[Parameter Reference](../guides/parameter_reference.md), auto-generated from the schema — the
single source of truth (Rule 27). The subsections below carry only *design context*.

### 6.1 Selection

- `atmosphere.model` — five legal values (§3); `interpolated` interpolates between
  pre-computed runs.
- `atmosphere.interpolation_axes` — the axes string that, with the scene's LOS direction,
  selects a shipped family when `interpolated_data_dir` is unset (§8.1).
- `atmosphere.interpolated_data_dir` — an explicit run-set directory; always wins over
  dispatch.

### 6.2 Simple parametric

- `atmosphere.visibility_km` — "clear" per Koschmieder; rejected if ≤ 0.
- `atmosphere.aerosol_type` — sets Ångström α and single-scattering albedo.
- `atmosphere.precipitable_water_cm` — **profile-coupled**: if left at its schema default
  while a non-default `standard_atmosphere` is selected, the loader substitutes the profile's
  standard column (`simple.PROFILE_PWV_CM`). An explicitly set value always wins
  (provenance-based, Gap 57).
- `atmosphere.standard_atmosphere` — used for the temperature-profile lookup, aerosol/H₂O
  scale heights, and the default water column (above).
- `atmosphere.cloud_fraction`, `atmosphere.cloud_optical_depth` — stubbed in v1; non-zero
  raises `NotImplementedError`.

### 6.3 Tabulated

- `atmosphere.tabulated_transmittance_file` — CSV / `.npz` / `.sli`; ascending λ in µm.
- `atmosphere.tabulated_path_radiance_file` — same format; W/m²/sr/µm.
- `atmosphere.tabulated_downwelling_file` — same format; optional, defaults to zero with a
  warning.

### 6.4 MODTRAN

- `atmosphere.modtran.tape7_path` — tape7 file import (§5.1). Set → the file wins;
  binary/cache/fallback never consulted. Geometry-agnostic; `h_tgt > 0` rejected unless
  `tape7_up_path` supplies the target leg.
- `atmosphere.modtran.tape7_sun_path` — optional sun-leg tape7. Requires `tape7_path`. Set →
  `τ_sun` from this file, no collapse warning; unset → `τ_sun` aliases `τ_up` with a warning.
- `atmosphere.modtran.tape7_up_path` — optional target→sensor up-leg tape7 (Gap 94). Requires
  `tape7_path`. Set → `τ_up`/`L_path_up` from this file and airborne targets accepted.
- `atmosphere.modtran.flux_path` — optional spectral flux CSV supplying downwelling (CU-157).
  Requires `tape7_path`. Set → the DOWN column feeds the two `E_sky` terms, superseding the
  Gap 81 zeros.
- `atmosphere.modtran.binary_path` — cross-platform default (CU-151): `modtran` on `PATH`,
  else the per-platform install location (POSIX `/usr/local/bin/modtran`; Windows
  `C:\Program Files\MODTRAN\modtran.exe`). Existence is checked at first use (not config
  load) and a missing binary raises `ModtranUnavailableError`.
- `atmosphere.modtran.cache_dir` — created if missing.
- `atmosphere.modtran.allow_fallback` — if `True`, falls back to simple parametric on a
  missing binary.
- `atmosphere.modtran.atmosphere_profile` — maps to `MODEL` 1–6.
- `atmosphere.modtran.aerosol_model` — maps to `IHAZE`.
- `atmosphere.modtran.h2o_scale` — `H2OSTR = "1.0g"` syntax handled by the deck builder.
- `atmosphere.modtran.o3_scale` — same (dimensionless multiplier).
- `atmosphere.modtran.cloud_model` — cloud fraction is 0/1 in v1.
- `atmosphere.modtran.disort_streams` — 4 for fast mode; 8 for production; 16 reserved.
- `atmosphere.modtran.spectral_resolution_cm1` — drives `DV` and `FWHM`.
- `atmosphere.modtran.extra_cards` — override hatch; recorded in the cache key.

### 6.5 Geometry (consumed, not owned)

These parameters live in `geometry.*`, owned by GeometryStage since ADR-0006 (definitions in
`geometry/_schema.py`, not this stage's schema); the atmosphere module reads them through the
parameter resolver:

`geometry.sensor_altitude_m`, `geometry.target_altitude_m`, `geometry.path_zenith_deg`,
`geometry.solar_zenith_deg`, `geometry.solar_azimuth_deg`, `geometry.observer_type`,
`geometry.target_type`, `geometry.day_of_year`.

**Producer-side note (CU-009; amended by ADR-0006 Phase 2):** SourceStage adopts the scene
`LineOfSightGeometry` that GeometryStage publishes
(`stage_outputs["geometry"]["los_geometry"]`) and descriptor-adjusts it
(`source/_inferrer._adjust_scene_los`); the legacy param-built `_infer_los` path survives only
for direct `infer_descriptors` callers. The solar-zenith and solar-azimuth values propagate
only when the target descriptor is solar-interacting (`T2Reflective`, `T3Mixed`); pure-thermal
`T1Thermal` targets receive `theta_s = delta_phi = None` regardless of the registered solar
params, honoring the `LineOfSightGeometry` "None for pure-thermal" docstring contract. (The
sky-background coupling consequence of that rule is the caveat in §4.2g.)

### 6.6 Turbulence

- `atmosphere.r0_m` — Fried parameter [m] entered directly. Default 0 = turbulence off.
- `atmosphere.r0_reference_wavelength_um` — the wavelength a directly-entered `r0_m` is quoted
  at (CU-228). Unset (default) = already at the operating wavelength.
- `atmosphere.cn2_profile` — `direct` (default, use `r0_m` verbatim), `hufnagel_valley`, or
  `tabulated`. Selecting a profile makes $r_0$ a derived quantity (§7.1).
- `atmosphere.cn2_hv_wind_rms_m_s`, `atmosphere.cn2_hv_ground_strength` — the two HV
  coefficients $w$ and $A$; the defaults are HV-5/7.
- `geometry.site_elevation_m` — the terrain elevation the HV **surface term** is referenced to
  (CU-262, §7.1). Default 0 = sea level. Owned by the geometry schema because it is a
  scene-geometry fact, not a turbulence coefficient; consumed today only by the
  `hufnagel_valley` profile. A non-zero value set against any other `cn2_profile` is
  **inert, and says so** — `cn2_profiles.warn_if_site_elevation_inert` raises a `UserWarning`
  naming why the input cannot reach that profile and what to do instead (CU-302, Rule 17).
- `atmosphere.cn2_tabulated_file` — two-column `altitude_m,cn2_m^-2/3` CSV, read pre-chain
  (Rule 6) by `loaders.build_cn2_profile` and injected at
  `stage_outputs["atmosphere_config"]["cn2_profile"]`.
- `atmosphere.turbulence_wave_type` — `plane` (default) or `spherical` path weighting (§7.1).

There is no `turbulence_enabled` flag and no observer-type gate: `r0_m = 0` with
`cn2_profile = 'direct'` *is* "off", and a path that crosses no atmosphere resolves to "off"
by itself.

---

## 7. Atmospheric Turbulence

Turbulence is the one atmosphere product that is **not** part of the four-document split: the
MTF equation, its assumptions and its numeric anchors live with the rest of the MTF cascade in
[`docs/theory/spatial_model.md`](../theory/spatial_model.md) §7, and everything below —
$r_0$ resolution, the path integral, the profiles, and the site-elevation reference — is
owned here.

### 7.1 What RADIANT implements

**The MTF.** A Kolmogorov long-exposure MTF, applied as a term in the spatial model, not in
`AtmosphereStage`'s radiometric output:

$$\mathrm{MTF}_{turb}(f) = \exp\!\left[-3.44\,\left(\frac{\lambda f}{r_0}\right)^{5/3}\right]$$

with $f$ the angular spatial frequency [cycles/rad]. `atmosphere/turbulence.py` holds the
formula; the PSF-path kernel is built in `platform/turbulence_kernel.py` and the MTF-product
term in `performance/turbulence_mtf_term.py` (Rule 4 — both paths, one physics).

**The Fried parameter.** $r_0$ reaches those consumers through
`stage_outputs["atmosphere"]["r0_m"]`, resolved by `atmosphere/r0_resolution.py`:

| `atmosphere.cn2_profile` | `atmosphere.r0_m` | Result |
|---|---|---|
| `direct` (default) | any | used verbatim; `0` = turbulence off. No geometry consulted. |
| a profile | unset | derived from the path integral below. |
| a profile | user-set, agrees within 1 % | the **entered** value wins; the profile is a recorded cross-check. |
| a profile | user-set, disagrees > 1 % | `TurbulenceSpecificationError` (the CU-093 redundant-entry pattern). |
| a profile | user-set to `0` | `TurbulenceSpecificationError` — contradictory intent. |

**The path integral** (`atmosphere/r0_path.py`, Gap 110):

$$r_0 = \left[\,0.423\,k^2 \sec\zeta \int_{h_{low}}^{h_{high}} C_n^2(h)\,W(h)\,\mathrm{d}h\right]^{-3/5},\qquad k = 2\pi/\lambda$$

- $\zeta$ is the zenith angle at the segment's **lower endpoint** — the same ADR-0011
  decision-3 convention `ColumnSegmentSpec` and the MODTRAN Card-3 deck builder use. It comes
  from `observer_leg.py` for up-looking paths and is $\theta_o$ for down-looking ones.
  $\sec\zeta$ is refused past `ZENITH_CEILING_RAD` (89.5°).
- **Integration limits are direction-aware**: the endpoint altitudes clipped into
  `[0, h_atm_top]`. A ground sensor gets the full column above it; an airborne sensor a
  partial one; a space sensor's residual column is empty, giving a finite huge $r_0$ saturated
  at `R0_NEGLIGIBLE_M` (1 km) with `negligible = True`, whereupon the term is **omitted
  entirely** rather than multiplied in as unity (§8 item 5). This replaces the retired
  space-observer `ScopeError` (guardrail G4 / Rule 27).
- **Weighting** $W$, parameterized by $u(h) = (h - h_{tgt})/(h_{sen} - h_{tgt}) \in [0,1]$ —
  the fraction of the way from the target to the aperture: `plane` (default) is $W = 1$, the
  source-at-infinity imaging case that published $r_0$ values assume; `spherical` is
  $W = u^{5/3}$, **maximum at the aperture and zero at the target**, the finite-range
  point-source case. Turbulence near the sensor therefore dominates.
- **Level (constant-altitude) paths** are not columns — $\sec(\pi/2)$ diverges. They integrate
  along the true chord at constant altitude: $C_n^2(h)\,L$ (plane) or $C_n^2(h)\,L\cdot 3/8$
  (spherical, since $\int_0^1 u^{5/3}du = 3/8$).
- Quadrature is a graded-grid trapezoid refined by doubling until it converges to $10^{-6}$
  relative; failure to converge raises (Rule 17).

**Profiles** (`atmosphere/cn2_profiles.py` is the contract; one implementation per module,
Rule 19):

- `hufnagel_valley` (`cn2_hufnagel_valley.py`) — the three-term HV form parameterized by the
  RMS upper-atmosphere wind $w$ and ground strength $A$; the schema defaults are HV-5/7
  ($w = 21$ m/s, $A = 1.7\times10^{-14}$ m$^{-2/3}$), which reproduce the published
  $r_0 = 5$ cm and $\theta_0 = 7$ µrad at 0.5 µm for a vertical path.
- `tabulated` (`cn2_tabulated.py`) — a measured (altitude, $C_n^2$) table, log-linearly
  interpolated (linearly across a zero endpoint), **zero outside its range** with a
  `UserWarning` quantifying the uncovered extent. A measured table already carries the site it
  was taken at, so `geometry.site_elevation_m` does **not** shift it.

**Site elevation — which altitude reference each HV term uses (CU-262).** RADIANT altitudes
are metres above mean sea level; the HV literature writes the profile against height above the
*site*. The two disagree by exactly the terrain elevation, and that disagreement is only
harmless for two of the three terms:

$$C_n^2(h) = \underbrace{0.00594\left(\tfrac{w}{27}\right)^2 (10^{-5}h)^{10}e^{-h/1000}}_{\text{jet stream — MSL}} + \underbrace{2.7\times10^{-16}e^{-h/1500}}_{\text{free atmosphere — MSL}} + \underbrace{A\,e^{-(h - h_{site})/100}}_{\text{surface layer — site-referenced}}$$

The jet stream is at 10 km MSL wherever the ground below it is, and the 1500 m-scale-height
background is a free-atmosphere property, so both stay on MSL. The surface term is different:
its 100 m scale height means a 900 m observatory evaluated against MSL sits
$e^{-9} \approx 1.2\times10^{-4}$ into its own boundary layer — it loses the layer entirely and
reports $r_0 = 15.0$ cm (0.67″ seeing) at 0.5 µm where HV-5/7 is *defined* to give 5 cm
(2.0″). Referencing the surface term to $h_{site}$ restores the anchor to 5.22 cm (1.94″); the
residual +4 % is the genuine altitude benefit of starting 900 m up the free-atmosphere column,
not a lost boundary layer.

**Choosing $A$ for your site.** The HV-5/7 default $A = 1.7\times10^{-14}$ m$^{-2/3}$ is a
near-sea-level *daytime* ground strength. Now that the surface term follows the terrain,
carrying that default unchanged to an elevated site gives that site a full sea-level-strength
boundary layer — ~1.94″ seeing at a 900 m site, correct for the model but far too pessimistic
for any decent observatory, whose site was chosen precisely for a weak surface layer. $A$ is a
*site quality* parameter and should be set from measured seeing: solve the path integral above
for the $A$ that reproduces the site's median seeing. Worked anchor:
$A = 2.70\times10^{-15}$ m$^{-2/3}$ reproduces the 0.80″ median at Paranal's 2635 m elevation.
**Migration warning:** before CU-262 the only way to make elevation matter was to *absorb it
into an inflated (or deflated) $A$*; that workaround is obsolete and now double-counts.
Re-derive $A$ from measured seeing with the elevation set honestly. (No shipped scenario used
the workaround.)

*Whose site is it?* — per topology, with the physics reason:

| LOS topology | Site is the terrain under… | Why |
|---|---|---|
| down-looking (`h_sensor > h_tgt`) | the **target** | The path descends toward the target; the only boundary layer it can enter is the one over the target's ground. |
| up-looking (`h_sensor < h_tgt`) | the **sensor** | The path rises from the sensor; the boundary layer it looks up through is the one the sensor stands in. The observatory / SST case. |
| level (`h_sensor == h_tgt`) | **both, jointly** — the arm's own terrain | Both endpoints are at the same altitude, so there is one terrain beneath the whole arm. |

In every row it is the same single number: the elevation of the terrain beneath the line of
sight. It is deliberately **not** derived from the lowest point of the line of sight — that
proxy would put a 100 m-scale-height boundary layer at 10 km for a level air-to-air leg,
inventing turbulence that is not there. No topology needs a special case for an endpoint that
is airborne over the site: the 100 m scale height suppresses the surface term on its own, so
**a level air-to-air path carries no surface term**, while a genuinely near-surface horizontal
link keeps the layer it physically sits in.

An altitude below $h_{site}$ is inside the terrain and is refused with a
`ParameterBoundsError` (Rule 16/17). At the default $h_{site} = 0$ that check is exactly the
pre-CU-262 "altitude must be ≥ 0" check, so **every existing result is bit-identical**.

**Reference wavelength.** $r_0 \propto \lambda^{6/5}$ exactly. The derived value is computed at
the **band-centre wavelength of the scene's spectral grid** — the same wavelength `OpticsStage`
uses for its monochromatic PSF reference, so the number is quoted at the wavelength its
consumers apply it at. It is published on `stage_outputs["atmosphere"]["r0_resolution"]`
(present only when a profile was evaluated). A directly-entered `r0_m` is rescaled **only if
you say what wavelength it is quoted at**, via `atmosphere.r0_reference_wavelength_um`
(CU-228): when set, the value is scaled to the band centre by
$(\lambda_{band}/\lambda_{ref})^{6/5}$ and both numbers are recorded in the resolution detail.
Left unset, the entered value is taken as already being at the operating wavelength.

This matters more than it looks: seeing is habitually quoted at 0.5 µm, and
$r_0 \propto \lambda^{6/5}$ means the astronomer's 10 cm becomes **1.3 m** at a 4.25 µm band
centre. RADIANT cannot detect that from the number alone, so it warns whenever `r0_m` is set,
the reference is unset, **and** the band centre is more than a factor of two from 0.5 µm. A
scene genuinely working near 0.5 µm stays quiet.

### 7.2 What RADIANT does *not* implement

- **Anisoplanatism** (off-axis turbulence degradation) and the isoplanatic angle $\theta_0$ as
  a published metric.
- **Scintillation** (irradiance fluctuations).
- **Tilt vs. higher-order decomposition** (adaptive optics).
- **Short-exposure MTF** (the tilt-removed correction term).
- **von Kármán outer scale** — Kolmogorov ($L_0 = \infty$) only.
- **Dome and platform-induced seeing.**
- **Turbulence-induced beam wander / refraction of the path itself** — the geometry is
  unrefracted (ADR-0011 decision 5).

These are absent, not stubbed: no parameter, no dataclass field, no `NotImplementedError`
placeholder.

### 7.3 Why turbulence is in the atmosphere module but applied as MTF

Turbulence is physically an atmospheric phenomenon (refractive index fluctuations along the
path) but it acts on the chain *spatially*, not radiometrically — total energy is conserved and
only the PSF is modified. Putting the turbulence MTF generation in the atmosphere module keeps
all atmosphere-related physics in one place (parameter inventory, documentation, plugin entry
point), while the *application* of that MTF lives in the spatial model where the rest of the
MTF cascade is computed. This is the same pattern the optics module uses for
`MTF_diffraction`: generated in `optics/diffraction.py`, applied in the system MTF cascade.

---

## 8. The `AtmosphereStage`

Per RADIANT_Signal_Chain_Architecture.md §2, `AtmosphereStage` is the second stage in the
chain. Its responsibilities:

1. **Resolve the atmosphere model** — preferentially the pre-built model injected at
   `stage_outputs["atmosphere_config"]["model"]` (§8.1); only non-file-backed models may be
   built inline as a partial-chain fallback — and **build the atmospheric products** from it,
   through `topology.evaluate_path_topology` rather than a bare `model.evaluate` (§4.2b).
2. **Apply transmittance and add path radiance** to produce the `at_aperture` reference frame:
   ```
   L_at_aperture(λ) = L_at_target(λ) · τ_atm(λ) + L_path(λ)
   ```
3. **Register the `at_aperture` frame** on the `ChainState` per the architecture document.
4. **Register `L_atm_down(λ)`** in `state.stage_outputs["atmosphere"]["downwelling"]` so the
   source stage's reflected-solar paths can consume it on their next pass (the `SkyBackground`
   arm does *not* read it — its radiance arrives on `TopologyProducts.sky_radiance_at_aperture`,
   §4.2g) — this is the only chain-level back-coupling and is handled by re-running
   `SourceStage` once if the source has a downwelling-dependent component (per
   RADIANT_Signal_Chain_Architecture.md §6.3).
5. **Resolve and publish the Fried parameter** (§7.1) as `stage_outputs["atmosphere"]["r0_m"]`,
   and — only when a Cn² profile was evaluated — the `FriedParameterResolution` record as
   `["r0_resolution"]`. When turbulence is off (or the path carries none), `r0_m` is absent and
   the downstream turbulence terms are omitted entirely rather than set to unity; the
   system-MTF cascade simply has one fewer term. The MTF term itself is built downstream
   (`platform/` for the PSF kernel, `performance/` for the MTF product), not here.
6. **Store the full `AtmosphericState`** in `state.stage_outputs["atmosphere"]["state"]` for
   downstream inspection, alongside the `topology_provenance` record (§4.2b).

`AtmosphereStage` is a pure function of `(state_in, params)`. It does not mutate state,
performs **no file I/O** (Rule 6 — see §8.1), and is safely re-runnable.

### 8.1 The Rule 6 loader boundary (`atmosphere/loaders.py`)

Rule 6 forbids stages from reading files, so all file-backed model construction lives in
`radiant/atmosphere/loaders.py`, which runs **before** chain execution:

- `build_atmosphere_model(params)` dispatches on `atmosphere.model` and performs any file I/O
  the model needs (NPZ/CSV tables for `tabulated`, an NPZ directory scan for `interpolated`,
  tape7 parsing for `modtran` with `tape7_path` set); `exo` and `simple` need no I/O. For an
  up-looking `interpolated` family it also builds and attaches the `SimpleAtmosphere` companion
  of the declared hybrid (§4.2b).
- For `interpolated` with no explicit directory, the shipped family is selected from
  `(LOS direction, interpolation_axes)`. Direction must be resolved **pre-chain**, before the
  `LineOfSightGeometry` exists, so `_scene_los_direction(params)` reproduces
  `LineOfSightGeometry.los_direction`'s rule from `geometry.sensor_altitude_m` vs
  `geometry.target_altitude_m`; a test pins the two together so the copies cannot drift. An
  unregistered geometry schema (partial-chain fixtures) falls back to `down`.
- **Config-time coverage check (CU-239).** `build_atmosphere_model` runs
  `interpolation_coverage.check_interpolation_coverage(params)` before it opens a single NPZ,
  so a scene the selected axes cannot serve is refused **pre-chain** with the remedy in hand
  rather than five stages later inside `InterpolatedAtmosphere.evaluate` (which keeps its own
  check as defence in depth). Two rules: (1) a down-looking scene with
  `geometry.target_altitude_m > 0 m` needs a `target_altitude_m` axis — one column cannot serve
  both the target→sensor leg and the ground→sensor full column (Gap 94); (2) an empty
  `interpolated_data_dir` needs the `(los_direction, axes)` pair to name a shipped family. The
  error names the **exact axes string to set**, the family it selects with coverage in
  km/degrees, and — when that family's rendered profile differs from an explicitly-set
  `atmosphere.standard_atmosphere` — a sentence saying so, because adopting a family must never
  silently change the profile the operator asked for.
- **`Sensor.validate_atmosphere_coverage()`** is the same check as a resolve-time API seam (the
  GUI runs it on every parameter edit), and `radiant.api.atmosphere_families` publishes the
  catalogue rows — the loader's dispatch table is derived from `SHIPPED_FAMILIES`, so there is
  one authority. `interpolation_coverage.py` owns the coverage lines; `BUNDLED_ATMOSPHERES_DIR`
  is the single definition of the packaged library's location.
- **`EXPLICIT_DIR_FAMILIES`** carries the bundled families that no `(direction, axes)` key may
  select: they are published for a picker with `explicit_dir_only = True` and a `bundled_dir`
  to write, and are deliberately excluded from the dispatch table, from `family_for()`, and
  from every coverage-refusal listing. The architectural reason a family lands here is that its
  signature is either already owned by another family (publishing it would re-baseline existing
  results) or is the *schema default* (publishing it would turn an actionable refusal into a
  silent dispatch). Which families, and their coverage → guide §3.
- `FILE_BACKED_MODELS = frozenset({"tabulated", "interpolated"})` names the models that
  **always** need files; `model_requires_prebuild(params)` is the parameter-aware check the
  stage uses — it additionally returns True for `modtran` when `atmosphere.modtran.tape7_path`
  is set (§5.1).
- The API layer (`RadiantSession`, and therefore `Sensor`) calls the loader and injects the
  constructed model into the chain via
  `ChainRunner.run(..., initial_stage_outputs={"atmosphere_config": {"model": model}})`.
- If no injected model is present, the stage builds only non-file-backed models inline. For a
  file-backed model it **refuses to build inline** and raises a `ValueError` directing the
  caller to `RadiantSession`/`Sensor` or to `build_atmosphere_model()` + manual injection.

---

## 9. Validation & Sanity Bounds

The atmosphere module enforces a small set of physical sanity checks at construction.
Violations raise `AtmosphericPhysicsError` with the offending wavelength(s).

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

The "soft" warning bounds are RADIANT-specific tripwires for the most common form of user
error (units), not physics constraints.

---

## 10. Plugin Hook **[DESIGN-TARGET]**

> **Not implemented.** The `plugins/` package was removed 2026-07-06 (see
> `RADIANT_Plugins.md`, DEFERRED banner). There is no `AtmospherePlugin` ABC and no
> `radiant.plugins.atmosphere` entry point. The five built-in models are dispatched directly by
> `atmosphere/loaders.py` (`build_atmosphere_model`) and `assembly.py`, **not** through a plugin
> registry — so the claim below that "the plugin interface is the only interface" is design
> intent, not current behavior. The extension-point design returns when `RADIANT_Plugins.md` is
> implemented.

Per the (deferred) plugin design, atmosphere would be a plugin extension point: users could
register a custom `AtmospherePlugin` that returns an `AtmosphericState` from a parameter set.
This is how a future libRadtran or 6S wrapper would integrate without touching core code.

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

Plugins would be registered via the `radiant.plugins.atmosphere` entry point (see
RADIANT_File_Tree.md §"Plugin entry points"), with the built-in models registered by the core
distribution so there is no special-cased "core vs. plugin" path.

---

## 11. Out of Scope for v1

Recorded explicitly so future RADIANT_Scope_Decisions.md updates can lift them deliberately:

- **Polarized atmospheric radiative transfer.** Stokes vectors are not propagated; everything
  is treated as unpolarized intensity.
- **3D / heterogeneous atmospheres.** Plane-parallel (with the spherical hand-over of §4.2)
  only. No broken-cloud handling, no horizontal gradients.
- **Time-dependent atmospheres.** A scenario specifies one atmospheric state; time-series
  scenarios re-build the state per frame.
- **Adjacency effects.** The reflected-solar contribution from neighboring ground pixels is not
  modeled (a 6S/MODTRAN-style "background reflectance" term).
- **Auroral and airglow emission.**
- **Refraction-induced apparent altitude shifts.** A target at zenith angle 89.5° is treated
  geometrically; the apparent vs. true altitude correction is deferred (ADR-0011 decision 5).
- **Cloud microphysics.** Clouds in v1 are either "off" or "MODTRAN's canned cloud model"; no
  LWC/effective-radius parameterization.

The *measured* consequences of these boundaries, where any exist, are the known-limitations
register in parity §3.

---

## 12. Open Questions

1. **MODTRAN version compatibility.** RADIANT targets MODTRAN 5 and 6 tape7 formats. Earlier
   versions are not supported. Confirm with the program office before locking the parser.
2. **Wavelength grid for `simple` aerosol fits.** The Ångström-α model is good in VIS/SWIR,
   already weak in MWIR, and *wrong* in LWIR. **Implemented (CU-088, 2026-07-12):** aerosol
   extinction is clamped at the MWIR–LWIR boundary (`AEROSOL_CLAMP_WAVELENGTH_UM` = 5.0 µm) —
   the "weak but usable" MWIR power law is preserved, and beyond 5 µm the extinction is frozen
   at its 5 µm value instead of decaying unphysically toward zero. `SimpleAtmosphere` warns once
   per run when the clamp engages. The boundary was placed at MWIR–LWIR rather than the
   originally-planned SWIR–MWIR so the flagship MWIR baseline is unchanged and only the
   genuinely-wrong long-wave extrapolation is corrected. A tabulated aerosol cross-section per
   type remains the higher-fidelity alternative for quantitative IR aerosol work.
3. **Where does `day_of_year` live?** It is a geometry concept (drives sun position) but only
   the atmosphere/MODTRAN path consumes it directly. Currently filed under
   `geometry.day_of_year`; revisit if a non-atmospheric consumer appears.
4. **Should the simple model expose its `L_path` decomposition?** MODTRAN does (thermal,
   scattered, single-scatter solar). The simple model could too, at the cost of more code.
   Probably yes.

---
