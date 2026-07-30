# ADR-0004: T7IntensityAtSource — user-supplied at-source spectral intensity

**Date:** 2026-04-21
**Status:** Accepted

## Context

The Target Definition Matrix ([`RADIANT_Target_Definition_Matrix.md`](../architecture/RADIANT_Target_Definition_Matrix.md))
defines **S10** as a user-supplied spectral intensity `I(λ)` [W/sr/µm] for
unresolved / point-source targets.  Phase 5 of the
[implementation plan](../archive/Target_Definition_Implementation_Plan.md) is
scoped to wire this YAML surface through the inferrer.

The pre-Option-C code path uses
[`DirectIntensitySource`](../../src/radiant/source/point_source_direct.py) +
[`resolve_direct_intensity`](../../src/radiant/source/resolvers/intensity.py),
which return a `ResolvedTarget` — the legacy container that Stage 2 of
Option C replaced with `TargetDescriptor` subclasses (T1/T2/T3/T5/T6).
The Step 5.1 plan prompt still reads *"route to `resolve_direct_intensity`"* —
written before Option C landed.  The current inferrer returns `TargetDescriptor`
only, so that routing target no longer exists in the descriptor surface.

Today the descriptor family cannot express "user-supplied intensity at the
target plane that still needs atmospheric transport":

- **T1Thermal / T3Mixed** carry (ε, T_t) and compute `ε · B(λ, T_t)` —
  cannot reproduce an arbitrary `I(λ)` unless the source is a blackbody.
- **T2Reflective** is for reflected solar — not a pass-through.
- **T5AtAperture** is at-aperture only; S10 still needs up-leg transport.
- **T6TabulatedAtSource** carries radiance `L_t_source(λ)` in W/m²/sr/µm,
  not intensity.  Forcing I into T6 requires the fictitious-area trick
  (`L = I / A_fict`, `A_t = A_fict`) already used inside
  `DirectIntensitySource.spectral_radiance`.  That works numerically but
  **hides the user's raw `I(λ)`**: the descriptor payload becomes a
  computed scaled quantity, round-trip serialization reports a
  multiplied/divided radiance, and assembly-arm debugging shows
  `L_t_source = 1e12 · I` instead of the number the user typed.

Ignoring the contradiction and jamming S10 into T6 silently couples the
descriptor surface to an assembly-time convention (the specific
`A_fict = 1e-12 m²`), violating the ADR-0002 principle that descriptors
are a faithful user-payload surface.  Leaving S10 routed through
`ResolvedTarget` forks Option C into a two-track source stage — the same
failure mode ADR-0003 explicitly rejected for S8.

## Decision

Introduce a new `TargetDescriptor` variant, **`T7IntensityAtSource`**,
that wraps a user-supplied spectral intensity at the target plane
(h = h_tgt) and flows through the same atmospheric up-leg arm as T6 —
with the `I → L` conversion happening at the assembly boundary, not
inside the descriptor.

### Descriptor contract

```python
@dataclass(frozen=True)
class T7IntensityAtSource(TargetDescriptor):
    I_t_source: SpectralData | None = None   # required, W/sr/µm
    # No shape field — a point source is unresolved by construction
    # (scene_type == "point_source"); shape geometry is meaningless.
    # No A_t field — S10 point sources carry no finite projected area.
    # The fictitious reference area used internally by the assembly arm
    # is an implementation detail, not a user-facing descriptor field.
```

`__post_init__` enforces:

- `I_t_source is not None`.
- `I_t_source.values >= 0` everywhere (Rule 17: no silent failure).
- `I_t_source.size >= 2` (SpectralData grid requirement).
- `scene_type == "point_source"` (matrix §7 row S10 — intensity is the
  point-source radiometric quantity; `extended` / `sub_pixel` must use
  T1 / T6 instead).
- `target_location != "at_aperture"` (T7 requires atmospheric transport;
  at-aperture intensity is meaningless — the aperture integrates
  radiance, not intensity).
- `I_t_source.unit == "W/sr/µm"` (canonical per Rule 2).

Note: T7 has no `shape` field and no `A_t` field.  A point source is
unresolved by definition, so projected geometry is meaningless at the
descriptor surface.  The reference area used internally by the
assembly arm (see below) is an assembly implementation detail — per
ADR-0002, it does not belong on the descriptor.

### Assembly contract (`atmosphere.assembly._assemble_t7`)

The assembly arm performs the `I → L` conversion at the boundary and
then follows the T6 up-leg formula:

```
L_t_source(λ) = I_t_source(λ) / A_fict          # boundary conversion
L_t,aperture(λ) = L_t_source(λ) · τ_up(λ) + L_path_up(λ)
```

It also publishes `A_t = A_fict` into `stage_outputs["source"]["projected_area_m2"]`
so that SpectralIntegrationStage picks it up as the scene-solid-angle
denominator.  `A_fict = 1e-12 m²` is the canonical reference area.

**Why this works — the single-camera-equation identity.**  RADIANT uses
one at-pixel radiometric equation across all regimes, living in
[`spectral_integration.stage`](../../src/radiant/spectral_integration/stage.py):

```
photon_rate(λ) = L_target(λ) · A_collect · (A_target / R²) · (λ / hc)
```

There is *no* separate point-source branch that uses `I · (A_ap / d²)`.
For a genuine point source that extended-scene formula is ill-posed
(L → ∞ as the target area → 0).  The fictitious-area construction
resolves this algebraically: choosing `L ≡ I / A_fict` and
`A_target ≡ A_fict` makes `A_fict` cancel exactly through the
`(A_target / R²)` factor, leaving

```
photon_rate(λ) = I(λ) · A_collect · (1 / R²) · (λ / hc)
```

which is the correct point-source camera equation.  The specific
numerical value of `A_fict` is irrelevant at the focal plane — it
cancels — but the `L_path_up · A_fict` additive term at the aperture
does retain a residual proportional to `A_fict`.  At `1e-12 m²` that
residual is ≈ 1e-12 × typical `L_path`, numerically negligible against
`I · τ_up` for any realistic source.

OpticsStage's point-source angular-size guard
(`√A_t / d ≤ 0.1 · PSF_FWHM`, matrix §7) sees `A_t = A_fict`, which is
far below any realistic PSF and always passes — the guard is satisfied
by construction for T7 because the user opted into the point-source
approximation by supplying intensity in the first place.

**Amendment (CU-256, owner ruling 2026-07-29).** "Satisfied by
construction" is exactly why the door must refuse a *declared* extent.
A user who supplies both an intensity and
`geometry.target.projected_area_m2` / `geometry.target.shape` has stated
the target's size twice, inconsistently; T7 honoured only the sentinel,
so a 500 m² target at 25 km (≈20 pixels across) passed the §7 guard as a
point source. The pair is now refused at the door
(`source.target_spec.check_intensity_door_extent_conflicts`), *before*
the sentinels are published. This ADR's `A_fict` algebra is unchanged —
T7 still publishes `A_fict` as the projected area; the guard simply never
sees a conflicting user value, because the conflict is refused
upstream.

`_components_t7` populates `AssemblyComponents` with `self_emission =
I_t_source / A_fict`, all ρ-driven terms zero, and the standard τ_up /
L_path audit fields — consistent with T1 / T6 reporting.

### Migration of legacy DirectIntensitySource

`DirectIntensitySource` becomes an **internal helper** used by
`atmosphere.assembly._assemble_t7` to perform the `I → L` conversion.
It stops being a user-facing source object.  `resolve_direct_intensity`
is deprecated (marked with a `DeprecationWarning` pointing at T7) and
removed once every in-tree caller has migrated.

### Scope of this ADR

- **In scope**: T7 class in `radiant.core.descriptors`, assembly arm in
  `radiant.atmosphere.assembly`, component decomposition, round-trip
  tests, deprecation of `resolve_direct_intensity`.  No user-facing
  parameter surface — Phase 5.1 wires `source.target.user_intensity_path`
  onto T7.
- **Out of scope**: Alternative reference areas (A_fict is fixed at
  1e-12 m²; plumbing an override through the descriptor surface is a
  separate change with its own ADR if ever needed).

## Rationale

### Alternatives Considered

| Option | Pros | Cons |
|--------|------|------|
| **T7 as proposed** (new descriptor) | User's raw I(λ) preserved on the descriptor; clean assembly arm; symmetric with T6; round-trip preserves user payload | Descriptor family grows 5→6 variants; new assembly arm + ADR |
| Reuse T6 with fictitious-area trick (`L = I / A_fict`, `A_t = A_fict`) | No new class | Hides user's raw I; couples descriptor surface to A_fict convention; serialization reports scaled radiance; debugging shows `1e12 · I`; ADR-0002 faithfulness violated |
| Extend T6 with optional `I_t_source` field (dual payload) | No new class | Splits T6's single-payload contract; every consumer must branch; `L or I` mutual-exclusion logic pollutes the assembly arm |
| Keep S10 on legacy `ResolvedTarget` path | No architectural change | Forks Option C into descriptor + ResolvedTarget tracks; same two-path failure ADR-0003 rejected for S8; Stage 7 matrix coverage can't complete S10 |
| Add a non-descriptor "intensity override" stage output | No descriptor change | Breaks the ADR-0002 contract that Stage 3 consumes only `TargetDescriptor`; every downstream stage must learn a second code path |

### Why now

Phase 5.1 is the next implementation plan step.  Trying to proceed
without an ADR was blocked in conversation because:

1. The plan's "route to `resolve_direct_intensity`" language is
   obsolete post-Option-C (same obsolescence that ADR-0003 resolved for
   S8).
2. Reuse-T6 would quietly violate the descriptor-faithfulness principle
   codified in ADR-0002.
3. Inventing a new variant without an ADR is explicitly forbidden by
   CLAUDE.md's Step 4.1 precedent: *"If the existing descriptor family
   cannot express S8 cleanly, STOP and report; do not invent a new
   variant without an ADR."*

Adding T7 now keeps Phase 5.1 minimal (schema + inferrer branch → T7
construction) and unblocks Phase 7's matrix coverage for S10.

## Consequences

- **Positive**:
  - User's raw `I(λ)` survives round-trip through the descriptor
    surface without scaling artifacts.
  - Phase 5.1 reduces to: add `USER_INTENSITY_PATH` schema param, load
    CSV, construct `T7IntensityAtSource(...)`, mirror Step 4.1's
    structure.
  - `DirectIntensitySource` becomes an internal assembly-layer helper,
    removing a legacy-vs-Option-C fork in the source stage.
  - Stage 7 matrix coverage gains a clean S10 row.

- **Negative**:
  - One more descriptor variant (5 → 6) plus a new assembly arm.  Adds
    an entry to `__all__`, the assembly dispatch ladder, and the
    `descriptors_to_params` round-trip helper.
  - Deprecation cycle for `resolve_direct_intensity` — one release of
    `DeprecationWarning` before removal.

- **Neutral**:
  - Descriptor numbering stays contiguous on allocation (1, 2, 3, 5, 6,
    7).  T4 remains reserved from ADR-0002 for "T4 Mixed with
    user-supplied ρ" and is still unused.
  - `A_fict = 1e-12 m²` is a named assembly constant; future ADRs that
    want a configurable reference area override it there, not on the
    descriptor.

## Resolved questions (were open during drafting)

1. **Should `shape` remain on T7?**  **Resolved: no.**  A point source
   is unresolved by construction; `shape` would be a field that must
   always be `None`, which is noise on the descriptor surface rather
   than a contract.  The perceived symmetry with T1 / T6 is false —
   T1 / T6 carry radiance `[W/m²/sr/µm]` whose per-pixel radiometry
   needs a projected area; T7 carries intensity `[W/sr/µm]` which
   already has the area folded in.  Dropped from the dataclass.
2. **Should `A_fict` be an atmosphere-parameter instead of a constant?**
   **Resolved: no.**  `A_fict` is not a physical quantity — it is the
   cancellation device that makes the single extended-scene camera
   equation reduce to the correct point-source form (see Assembly
   contract above).  Its numerical value is irrelevant at the focal
   plane.  Exposing it as a parameter would invite users to choose
   values that make the `L_path_up · A_fict` residual visually
   significant and mis-interpret it.  Locked at `1e-12 m²` as a named
   module constant in `atmosphere.assembly` (e.g. `_T7_REFERENCE_AREA`).
   A future ADR may lift this if a concrete need arises.

## References

- [ADR-0002](0002-option-c-source-atmosphere-split.md) — descriptor
  surface contract (faithfulness principle).
- [ADR-0003](0003-t6-tabulated-at-source.md) — T6TabulatedAtSource
  precedent for user-supplied at-source quantities.
- [`RADIANT_Target_Definition_Matrix.md`](../architecture/RADIANT_Target_Definition_Matrix.md)
  §1 row S10; §7 point-source angular-size constraint.
- [`Target_Definition_Implementation_Plan.md`](../archive/Target_Definition_Implementation_Plan.md)
  Phase 5 (blocked on this ADR).
- [`src/radiant/source/point_source_direct.py`](../../src/radiant/source/point_source_direct.py) —
  legacy `DirectIntensitySource` migrating to internal helper.
- [`src/radiant/source/resolvers/intensity.py`](../../src/radiant/source/resolvers/intensity.py) —
  legacy `resolve_direct_intensity` being deprecated.
- `CLAUDE.md` Rules 2 (unit boundaries), 11 (no cross-stage imports),
  17 (no silent failure).
