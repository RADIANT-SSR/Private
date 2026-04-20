# ADR-0002: Option C — Source/Atmosphere Split via Descriptors

**Date:** 2026-04-19
**Status:** Accepted

## Context

The [RADIANT Use-Case Matrix](../RADIANT_Use_Case_Matrix.md) v1 catalogs 90 imaging-scenario cells across three axes (`scene_type` × `target_location` × `wavelength_regime`). The matrix's centerpiece is the radiance assembly equation (matrix §6.1):

```
L_t,aperture(λ) = [ε·B(T_t) + ρ·τ_sun·E_TOA·cos(θ_s)/π + ρ·E_sky/π] · τ_up + L_path,up
L_bg,aperture(λ) = [ε_g·B(T_g) + ρ_g·E_g/π] · τ_full,up + L_path,full
```

The equation interleaves *target* properties (ε, ρ, T_t), *atmospheric* quantities (τ_sun, τ_up, τ_full,up, E_sky, L_path), and *illumination* (E_TOA, θ_s). Someone has to own the assembly. The current codebase (pre-Option-C) places it implicitly inside the source modules: `SourceStage` produces a fully-assembled `L_target` radiance frame and `AtmosphereStage` only applies a single `L·τ + L_path` on top.

This implicit split is the root cause of the gaps documented in [Use_Case_gaps.md](../Use_Case_gaps.md): only ~2 of 90 cells run end-to-end with correct physics. Specifically, the implicit split:

- Cannot separate the down-leg (τ_sun) from the up-leg (τ_up) of the two-way path (kills all reflective terrestrial cells).
- Cannot propagate the background term `L_bg,aperture` through the atmosphere as a separate, geometry-aware quantity (kills all sub-pixel and point-source cells with non-zero background).
- Cannot dispatch on `target_location` because SourceStage doesn't know about the matrix's axis enums.
- Forces SourceStage to import atmospheric internals (E_TOA, E_sky) when computing reflective terms — a Rule 11 cross-stage import violation in the making.
- Has no place for the matrix §7 cross-field validators (at_aperture⇒extended, MWIR⇒T3, no_atmosphere⇒sub_case, etc.) to live cleanly.

A decision is required on **where** the assembly equation runs and **what** flows across the SourceStage → AtmosphereStage boundary, before the matrix can become a description of what RADIANT does rather than what it should do.

## Decision

**RADIANT adopts Option C**: SourceStage publishes *descriptors only* (no radiance); AtmosphereStage owns the full radiance-assembly equation and produces both `L_t,aperture(λ)` and `L_bg,aperture(λ)` as separate `RadiometricFrame` objects.

### The descriptor surface

Three descriptor classes constitute the SourceStage → AtmosphereStage contract:

#### 1. `TargetDescriptor` (frozen dataclass) — [src/radiant/core/descriptors.py](../../src/radiant/core/descriptors.py)

**Location rationale**: the three descriptor classes (`TargetDescriptor`, `BackgroundDescriptor`, `LineOfSightGeometry`) are pure frozen dataclasses with no physics. They are the cross-stage data contract between SourceStage and AtmosphereStage, analogous to `ChainState` and `ObserverGeometry` which already live in `core/`. Placing them in `core/` removes a would-be Rule 11 exception (AtmosphereStage importing from `radiant.source._descriptors`) and makes the descriptor surface available to any stage, plugin, or I/O layer that needs to construct or consume them.

Common fields:
- `scene_type`: enum `{"extended", "sub_pixel", "point_source"}`
- `target_location`: enum `{"at_aperture", "terrestrial", "airborne", "no_atmosphere"}`
- `no_atmosphere_subcase`: enum `{"space", "ground_test", "lab_test"} | None` — required iff `target_location == "no_atmosphere"`
- `h_tgt`: float [m] — required except for `at_aperture`

Discriminated material/geometry payload by `(target_location, scene_type)`:

| Variant | Carries | Used for |
|---|---|---|
| `T1Thermal` | `epsilon: SpectralData`, `T_t: float [K]`, optional `(A_t, shape)` for sub_pixel/point | LWIR cells; MWIR with ρ ≈ 0 |
| `T2Reflective` | `rho: SpectralData` (or `epsilon` + Kirchhoff), optional `(A_t, shape)` | VIS / NIR / SWIR reflective cells |
| `T3Mixed` | `epsilon: SpectralData`, `T_t: float [K]`, `rho` derived via Kirchhoff (`ρ = 1 − ε`), optional `(A_t, shape)` | All MWIR cells; SWIR hot targets |
| `T5AtAperture` | `L_t_aperture: SpectralData` (extended) or `I_t_aperture: SpectralData` (deferred for at_aperture sub-pixel/point — currently invalid per matrix) | Table A cells |

#### 2. `BackgroundDescriptor` (frozen dataclass, discriminated) — same module ([src/radiant/core/descriptors.py](../../src/radiant/core/descriptors.py))

| Variant | Carries | Required for |
|---|---|---|
| `AtApertureBackground` | `L_bg_aperture: SpectralData \| None = None` (None ⇒ 0) | `target_location == "at_aperture"` |
| `ColdSpaceBackground` | (no params; L_bg ≡ 0 in v1) | `no_atmosphere_subcase == "space"` |
| `GroundBackground` | `epsilon_g: SpectralData`, `T_g: float [K]` | `target_location ∈ {"terrestrial", "airborne"}` (required, no default) |
| `UserSpectralBackground` | `L_bg: SpectralData` | `no_atmosphere_subcase ∈ {"ground_test", "lab_test"}` (required, no default) |

`BackgroundDescriptor` is `None` for computed-extended cells (matrix Decision §13: spectral-integration skips the background photon term entirely).

#### 3. `LineOfSightGeometry` (frozen dataclass) — [src/radiant/core/los_geometry.py](../../src/radiant/core/los_geometry.py)

Per matrix §4.3 and Decision #10 (its own file, Rule 19):

```python
@dataclass(frozen=True)
class LineOfSightGeometry:
    h_tgt: float              # m, target altitude above MSL
    h_atm_top: float = 1e5    # m, top of atmospheric integration (Kármán line)
    theta_o: float            # rad, observer zenith at target
    theta_s: float | None     # rad, solar zenith at target
    delta_phi: float | None   # rad, relative azimuth φ_s − φ_o ∈ [−π, π]

    @property
    def slant_range_atm(self) -> float: ...     # m, LOS h_tgt → h_atm_top, spherical Earth
    @property
    def path_airmass_up(self) -> float: ...     # dimensionless airmass for up-leg
```

Plus boundary converter (Rule 2 — conversion at boundary only):

```python
def theta_o_from_eta(eta: float, h_sensor: float, h_tgt: float) -> float:
    """Corrected sine rule: sin(θ_o) = (R_E + h_sensor)/(R_E + h_tgt) · sin(η)."""
```

`SensorDescriptor` (h_sensor for OpticsStage / platform) is **deferred** to a follow-on ADR per matrix §4.4 — not on the critical path for Option C.

### Stage boundary contract

```python
# SourceStage (after Option C):
def run(state, params) -> ChainState:
    target = build_target_descriptor(params)        # scene_type, location, material
    bg     = build_background_descriptor(params)    # variant per location/subcase, or None
    los    = build_los_geometry(params)             # h_tgt, h_atm_top, θ_o, θ_s, Δφ
    return (state
            .with_stage_output("source", "target",       target)
            .with_stage_output("source", "background",   bg)
            .with_stage_output("source", "los_geometry", los)
            .with_stage_output("source", "regime_tentative", target.scene_type))
    # NO RadiometricFrame published. SourceStage emits zero radiance under Option C.

# AtmosphereStage (after Option C):
def run(state, params) -> ChainState:
    tgt = state.stage_outputs["source"]["target"]
    bg  = state.stage_outputs["source"]["background"]
    los = state.stage_outputs["source"]["los_geometry"]

    atm = self.backend.evaluate(los, params)        # τ_sun, τ_up, τ_full,up, E_TOA,
                                                    # E_sky_scattered, E_sky_thermal,
                                                    # L_path_up, L_path_full
    L_t_ap  = assemble_target_at_aperture(tgt, atm, los)
    L_bg_ap = assemble_background_at_aperture(bg,  atm, los)  # may be 0 / None for computed-extended

    return (state
            .with_frame("at_aperture_target",     L_t_ap)
            .with_frame("at_aperture_background", L_bg_ap))
```

### Cell ↔ assembly-arm mapping

Each matrix cell maps to one branch of `assemble_target_at_aperture` × one variant of `BackgroundDescriptor`:

| Matrix cell class | Target arm | Background variant | Atm path |
|---|---|---|---|
| Table A (at_aperture extended, all regimes) | `T5` pass-through | `AtApertureBackground` | A0 (with warn-if-atm-supplied) |
| Table B extended VIS/NIR/SWIR (Cells 16,19,22) | `T2` reflective with full A2 assembly | None (computed extended) | A2 |
| Table B extended MWIR (Cell 25) | `T3` mixed with E_sky_thermal dominant | None | A2 (full) |
| Table B extended LWIR (Cell 28) | `T1` thermal, ρ ≈ 0 reduces solar terms to 0 | None | A4 (degenerate from A2) |
| Table B sub_pixel/point (Cells 17–18, 20–21, 23–24, 26–27, 29–30) | T2/T3/T1 + A_t | `GroundBackground` | A2 + bg branch with τ_full,up, L_path,full |
| Table C airborne (all 15) | Same arms as B with h_tgt > 0 | `GroundBackground` | A3 (partial column) |
| Table D space LWIR (Cell 58) | `T1` | None or `ColdSpaceBackground` (extended ⇒ None) | A0 |
| Table D space other (Cells 46–57, 59–60) | T1/T2/T3 | `ColdSpaceBackground` (sub-pixel/point only) | A0 |
| Table D-ground (G1–G15) | T1/T2/T3 from material+T+illumination | `UserSpectralBackground` (required) | A0 |
| Table D-lab (L1–L15) | Same as D-ground; illumination optional | `UserSpectralBackground` (required) | A0 |

### Validation surface

Matrix §7 cross-field validators land in descriptor `__post_init__` blocks, not in stages. This makes them reachable without running a chain and ensures the same checks run for every entry path (YAML, programmatic, plugin):

- `TargetDescriptor.__post_init__`: at_aperture⇒extended; no_atmosphere⇒subcase; T3 required for MWIR (warn unless ρ≈0); point_source angular size ≤ 0.1·PSF_FWHM (deferred — needs OpticsStage handshake)
- `BackgroundDescriptor` factories: variant↔target_location compatibility; UserSpectralBackground required for ground_test/lab_test; T_g ∈ [150, 350] K with warn-if-outside
- `LineOfSightGeometry.__post_init__`: θ_o ∈ [0, π/2); θ_s ∈ [0, π] if provided; Δφ ∈ [−π, π]; h_tgt ∈ [0, h_atm_top]; Earth-LOS-intercept check for `space` sub-case

## Rationale

### Alternatives Considered

| Option | Description | Pros | Cons |
|---|---|---|---|
| **A** — Source owns assembly | SourceStage publishes `L_t,aperture` directly; AtmosphereStage absorbed into source | Single stage, simpler chain | Forces SourceStage to import atmospheric internals (Rule 11 violation); no clean place to swap atmosphere backends; cannot reuse atmosphere quantities across target and background terms |
| **B** — Source publishes pre-atm radiance | SourceStage publishes `L_t,surface` (the term in `[…]` brackets, pre-τ_up); AtmosphereStage applies τ_up + L_path | Familiar separation; preserves frame-based interface | The `[…]` term *itself* contains τ_sun and E_sky (atmospheric quantities), so SourceStage still imports atmosphere; double-bookkeeping for the background term; cannot reduce to A0 cleanly |
| **C** — Source publishes descriptors; atmosphere assembles | SourceStage publishes TargetDescriptor + BackgroundDescriptor + LineOfSightGeometry; AtmosphereStage owns the full assembly | Single point of assembly; clean atmosphere-backend swap; both target and background propagate through the same atmospheric quantities; matrix cells map 1:1 to match arms; validators centralize on descriptors | Larger refactor (SourceStage stops emitting frames); changes the public stage_outputs surface; existing scenarios need a back-compat inferrer |

**Why C wins**:

1. **The equation cannot be cleanly factored.** The reflective term `ρ·τ_sun·E_TOA·cos(θ_s)/π` mixes a target property (ρ), an atmospheric property (τ_sun), and an illumination property (E_TOA, θ_s). Options A and B both force one stage to compute quantities that conceptually belong to the other. C avoids this by deferring assembly until both target and atmospheric quantities are available in one place.

2. **Two-leg attenuation is geometry-dependent, not source-dependent.** The down-leg (TOA → h_tgt along θ_s) and up-leg (h_tgt → sensor along θ_o) are different paths. Only AtmosphereStage owns the geometry machinery to compute them. Putting assembly there places the right computation next to the right inputs.

3. **The background term needs the same atmosphere as the target term.** In a sub-pixel cell, `L_bg,aperture` propagates through `τ_full,up` (full column from surface) while `L_t,aperture` propagates through `τ_up` (partial column from h_tgt). These are the same atmosphere evaluated at two different geometries. Computing them in two different stages would duplicate the atmosphere call and risk inconsistency.

4. **Matrix axes become enum dispatch.** Once the descriptors carry `target_location` and `no_atmosphere_subcase`, the assembly is a `match` statement with one arm per matrix table. The 90-cell matrix becomes a finite enumeration in code rather than implicit conditional behavior scattered across modules.

5. **Validation has a natural home.** The §7 invalid combinations are cross-field constraints on the descriptor objects themselves. Running them in `__post_init__` makes them reachable from every code path that constructs a descriptor, including tests, plugins, and YAML loaders.

### Counterarguments addressed

- *"Stages becoming heavier"*: AtmosphereStage grows; SourceStage shrinks by an equal amount (it loses radiance assembly). Net code mass is roughly unchanged; what moves is the boundary.
- *"Breaking change for existing scenarios"*: managed by the Stage 2 back-compat inferrer that maps current flat parameters to descriptors with sensible defaults. Existing scenarios continue to run unchanged.
- *"Frame consumers depend on `at_target`"*: the only legitimate downstream consumer is SpectralIntegrationStage, which will consume `at_aperture_target` and `at_aperture_background` after Stage 4. The legacy `at_target` frame is removed at that point.

### Decision #15 — `source.background.*` is adjacent-scene only

**Problem**: the matrix/code uses "background" in a way that collides with the common EO engineer's usage. In Option C there are three distinct non-target photon sources:

1. **Adjacent-scene radiance** — what fills a sub-pixel footprint beside a point/sub-pixel target, or what lies geometrically behind the target (cold space behind an Earth target, etc.). Option C names this via `BackgroundDescriptor` (`GroundBackground`, `ColdSpaceBackground`, `AtApertureBackground`, `UserSpectralBackground`). **Absent for extended scenes** (the target *is* the adjacent scene) — this is matrix Decision #13.
2. **Atmospheric path radiance in front of the target** — photons scattered/emitted into the LOS by the column between target and sensor. Always present in a non-vacuum path, independent of scene regime. Named `L_path_up` / `L_path_full` in `AtmosphericQuantities`; owned by AtmosphereStage.
3. **Downwelling sky that reflects off the target** — illumination of the target via `E_sky_thermal` + `E_sky_scattered`. Not "background" in any traditional sense; contributes to target leaving radiance via `ρ·E_sky/π`.

**The legacy trap**: pre-Option-C, the scalar parameters `source.background.temperature` and `source.background.emissivity` fed a single `L_background = ε_bg · B(T_bg)` path through SourceStage and into SpectralIntegrationStage's background-photon-shot term. Extended-scene YAMLs (Cells 28 and 58 among them) set these parameters because the chain required *something* non-zero — most plausibly as a proxy for **atmospheric path thermal emission** (intent = (2) above), not as an adjacent-scene term that Decision #13 correctly says does not exist. The Stage 0 anchor values bake this double-count in.

**Decision**: `source.background.*` parameters describe (1) only. They populate `BackgroundDescriptor` and are meaningful only when a background is meaningful — i.e., for `sub_pixel`, `point_source`, and the explicit `no_atmosphere` sub-cases. For `scene_type == "extended"`:

- Stage 2's `_infer_background_descriptor` returns `None` (Decision #13).
- If the user *also* set `source.background.temperature > 0` and/or `source.background.emissivity > 0`, Stage 2 emits a `UserWarning` naming the likely intent-mismatch and pointing at the atmosphere parameter surface. **No silent bypass; no silent honour.** (Rule 17.)
- SpectralIntegrationStage skips the background photon term when no background frame is published (already Rule 9 behavior).
- Atmospheric thermal path emission is computed from atmosphere-stage physics — `SimpleAtmosphere` derives `L_path_up` from `T_atm_eff` and the column integral; `ExoAtmosphere` returns zero; `TabulatedAtmosphere` lifts a precomputed table.

**Consequence for Stage 0 anchors**: Cells 28 and 58 (both extended LWIR) re-baseline at Stage 4. The legacy `SpectralIntegrationStage` computed a `background_e` term from `L_background` for EXTENDED scenes (feeding the `background_shot` noise RSS), which numerically dominated the noise budget and drove SNR down (5.52 for Cell 28, 6.47 for Cell 58). Under Decision #13 + #15, `BackgroundDescriptor = None` for extended scenes → `background_e = 0` → `background_shot = 0`, and SNR rises to ~315.5 and ~316.0 respectively. The target-arm radiance transport is unchanged, so `L_aperture(λ)` stays bit-identical across the Stage 4 cut. The three `lwir_*` scenarios in `option_c_baseline.yaml` (all cell_ref `Cell 28`) are reclassified from `invariant` to `expected_to_change_at_stage_4`; their new post-Stage-4 SNR/NEDT values are pinned in `docs/option_c_baseline.md`.

**Why this is not a parameter migration**: the user's intent-under-the-hood was almost always atmospheric path radiance, which is already computed by the atmosphere backend without the user touching any knob. For the terrestrial case the SimpleAtmosphere path-integral produces it; for the exo case it is genuinely zero. There is nothing to automatically migrate — the legacy parameter was over-specifying the system. The `UserWarning` explains this to legacy users.

## Consequences

### Positive

- **Matrix coverage becomes incremental and measurable**: each new cell is a new arm or a new descriptor variant. The "N of 90 cells passing" number becomes a test assertion.
- **AtmosphereStage backend is swappable cleanly**: Simple, MODTRAN, Tabulated, and Exo backends all conform to one protocol that returns `(τ_sun, τ_up, τ_full,up, E_TOA, E_sky_scattered, E_sky_thermal, L_path_up, L_path_full)`. Switching backends does not change the assembly.
- **Rule 11 (no cross-stage imports) is preserved**: SourceStage no longer needs E_TOA or E_sky.
- **Rule 9 (EE_box) is structurally enforced**: target and background arrive at SpectralIntegrationStage as separate frames, so it is impossible to accidentally apply EE_box to background.
- **Validation centralizes**: all matrix §7 checks run at descriptor construction, before any physics fires.
- **At-aperture pass-through becomes trivial**: one `match` arm in `assemble_target_at_aperture` returns the user's spectrum unchanged; the warn-if-atm-supplied check (matrix Decision #6) lives in AtmosphereStage's pre-assembly validation.

### Negative

- **8-PR refactor** spanning ~16.5 engineering days before all matrix cells are reachable (per the staged plan in the conversation that produced this ADR). Stage 4 is the earliest point at which the full Option C surface is in.
- **Stage 3 will move some golden values**: cells that today benefit from the missing atmospheric propagation of the background term (sub-pixel terrestrial scenarios) will produce different — *correct* — numbers. Each changed golden requires a review per [RADIANT_Testing_Validation.md §5.3](../RADIANT_Testing_Validation.md).
- **A new public surface** (`state.stage_outputs["source"]["target" | "background" | "los_geometry"]`) becomes part of the contract that downstream stages and plugins consume. Once published it is hard to change.
- **Sensor altitude (`h_sensor`) is deferred** to a follow-on ADR; it does not bite today (OpticsStage uses focal length + aperture only) but will when airborne sensors land in v2.

### Neutral

- `RadiometricFrame` named `at_target` is removed; replaced by `at_aperture_target` and `at_aperture_background` published from AtmosphereStage. Anything that names "at_target" must be updated.
- The `L_background` stage_output published by SourceStage today is removed; SpectralIntegrationStage reads the `at_aperture_background` frame instead.
- `AtmosphericGeometry` ([src/radiant/atmosphere/protocol.py](../../src/radiant/atmosphere/protocol.py)) is superseded by `LineOfSightGeometry` ([src/radiant/core/los_geometry.py](../../src/radiant/core/los_geometry.py)). Field name and semantics differ (`solar_azimuth_rad` absolute compass → `delta_phi` relative ∈ [−π, π]); a converter is provided during the deprecation window.
- The `regime_tentative` published by SourceStage continues to exist; OpticsStage continues to finalize regime per Rule 10.

## Implementation contract

This ADR is implemented by the 8-stage plan recorded in the conversation transcript dated 2026-04-19:

| Stage | Output | Days | Cells unlocked (cumulative) |
|---|---|---|---|
| 0 | This ADR + baseline tag + golden snapshots | 0.5 | — |
| 1 | Descriptor + LineOfSightGeometry classes (no wiring) | 2 | — |
| 2 | SourceStage publishes descriptors alongside legacy frame | 2 | — |
| 3 | AtmosphereStage consumes descriptors, owns assembly | 3 | ~15 |
| 4 | SpectralIntegrationStage consumes two frames; legacy frame removed | 1 | ~20 |
| 5 | A3 partial-column atmosphere | 3 | +15 (Table C) |
| 6 | E_sky decomposition | 2 | quality fix on MWIR cells |
| 7 | no_atmosphere sub-case presets and dispatch | 1 | +30 (D-ground + D-lab) |
| 8 | §7 cross-field validators + 90-cell parametric coverage test | 2 | quality fix on all |

Stage 4 is the "Option C landed" milestone (full Option C surface in place; SourceStage publishes zero radiance). Stages 5/6 and 7 are independent expansions on top of Stage 4 and may run in parallel.

## References

- [RADIANT_Use_Case_Matrix.md](../RADIANT_Use_Case_Matrix.md) — 90-cell matrix and the Locked Decision §4 that this ADR implements
- [Use_Case_gaps.md](../Use_Case_gaps.md) — adversarial coverage audit that motivated this work
- [RADIANT_Master_Architecture.md](../RADIANT_Master_Architecture.md) — Rules 2 (units at boundaries), 9 (EE_box), 10 (regime finalization), 11 (no cross-stage imports), 19 (one computation, one module)
- [RADIANT_Signal_Chain_Architecture.md](../RADIANT_Signal_Chain_Architecture.md) — Stage protocol, ChainState contract
- [ADR-0001](0001-scope-and-constraints.md) — RADIANT scope and top-level constraints (parent ADR)
