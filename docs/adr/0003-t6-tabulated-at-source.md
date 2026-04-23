# ADR-0003: T6TabulatedAtSource — user-supplied at-source spectral radiance

**Date:** 2026-04-21
**Status:** Proposed

## Context

The Target Definition Matrix ([`RADIANT_Target_Definition_Matrix.md`](../RADIANT_Target_Definition_Matrix.md))
calls out three spec forms that need to hand the SourceStage a pre-computed
spectral radiance L_source(λ) at the target (h = h_tgt), letting the normal
atmospheric up-leg (τ_up, L_path_up) propagate it to the aperture:

- **S8** — user-tabulated at-source radiance (Phase 4 of the
  [implementation plan](../Target_Definition_Implementation_Plan.md)).
- **S11** — brightness temperature T_B(λ); when T_B is λ-dependent, the only
  exact representation is L(λ) = B(λ, T_B(λ)) (Phase 2.1).
- **S12** — band-averaged radiance temperature T_R; the inversion harness
  produces a per-λ L(λ) in the general case (Phase 2.2).

Today the descriptor family (T1/T2/T3/T5) cannot express "pre-computed
L_source that still needs atmospheric transport":

- **T1Thermal** carries (ε, T_t) and re-computes B(λ, T_t) via Planck.  It
  cannot reproduce an arbitrary L(λ) unless T_B is constant.
- **T2Reflective** carries ρ and drives a reflected-solar / diffuse-sky
  computation — not a pass-through.
- **T3Mixed** carries (ε, T_t) with Kirchhoff ρ = 1 − ε — same constraint
  as T1.
- **T5AtAperture** carries L_t_aperture and bypasses atmosphere
  entirely; it is at-aperture by definition and the dispatcher rejects
  any non-at_aperture target_location paired with T5.

Phase 2.1 of the plan explicitly names the contradiction: "if T_B varies
with λ, the single-temperature T1Thermal cannot exactly reproduce L(λ).
The correct implementation stores L_source = B(λ, T_B(λ)) and routes to
TabulatedRadianceSource (S8 path)" — but **TabulatedRadianceSource is
not a TargetDescriptor**; it is a pre-Option-C source object that does
not flow through the Stage 3 assembly pipeline.  Wiring it to user input
today would either bypass the descriptor surface (violating ADR-0002) or
require atmosphere physics inside the source stage (violating Rule 11).

Ignoring the contradiction and shipping scalar-only S11 / S12 / S8 would
cap matrix coverage at partial delivery of three spec forms and force a
rewrite once the full spectrum is needed.

## Decision

Introduce a new `TargetDescriptor` variant, **`T6TabulatedAtSource`**,
that wraps a user-supplied spectral radiance at the target plane (h = h_tgt)
and flows through the normal atmospheric up-leg arm.

### Descriptor contract

```python
@dataclass(frozen=True)
class T6TabulatedAtSource(TargetDescriptor):
    L_t_source: SpectralData | None = None   # required, W/m²/sr/µm
    A_t: float | None = None                 # projected area, m² (optional)
    shape: object | None = None              # TargetShape | None (optional)
```

`__post_init__` enforces:

- `L_t_source` is not None.
- `L_t_source.values >= 0` everywhere.
- `target_location != "at_aperture"` (T6 requires atmospheric transport;
  at-aperture is T5's domain).
- `L_t_source.unit == "W/m²/sr/µm"`.

### Assembly contract (`atmosphere.assembly._assemble_t6`)

```
L_t,aperture(λ) = L_t_source(λ) · τ_up(λ) + L_path_up(λ)
```

Mathematically identical to T1 with the substitution
`ε(λ) · B(λ, T_t) → L_t_source(λ)` — the self-emission source function is
supplied by the user rather than computed from (ε, T_t).  ρ ≡ 0 by
construction (the user is naming absolute emitted/emitted-plus-reflected
radiance, not a material property).

`_components_t6` populates `AssemblyComponents` with `self_emission =
L_t_source`, all ρ-driven terms zero, and the standard τ_up / L_path
audit fields — consistent with how T1 reports.

### Scope of this ADR

- **In scope**: T6 class, assembly arm, component decomposition, round-trip
  tests.  No user-facing parameter surface (Phases 2.1 / 2.2 / 4 will wire
  schema fields onto T6).  No I/O (existing `SpectralData.from_dict` covers
  serialization).
- **Out of scope**: MWIR non-mixed warning — T6 names the absolute radiance;
  the mixed-vs-thermal distinction is a material-property question, not a
  radiance-value question.  No analog of `_warn_mwir_non_mixed` applies.

## Rationale

### Alternatives Considered

| Option | Pros | Cons |
|--------|------|------|
| **T6 as proposed** (new descriptor) | Clean flow through existing Stage-3 dispatcher; one new arm; single source of truth for S8/S11/S12; no Rule-11 or Rule-5 violations | Descriptor family grows from 4→5 variants; ADR + minor test surface |
| Overload `T5AtAperture` to accept an "at-source" flag | No new class | Violates T5's invariant (at-aperture pass-through); dispatcher forked on flag; leaks atmosphere knowledge into T5 |
| Route through `TabulatedRadianceSource` (legacy) | Reuses existing class | That class is not a descriptor; bypasses Stage-3 assembly; would re-introduce the pre-Option-C two-path problem |
| Compute B(λ, T_B(λ)) inside `_inferrer` and emit T1Thermal with an effective T_t | No descriptor change | Silently lossy — `T_t` is a scalar; λ-varying T_B cannot round-trip through ε·B(T_t) |
| Keep S11/S12/S8 scalar-only | No architectural change | Partial matrix delivery; Phase 7 can't complete; forces rewrite later |

### Why now

Phase 1 is green and regressions are stable.  Three downstream phases
(2.1, 2.2, 4.1) all funnel into the same L_source(λ) → aperture problem;
solving it once keeps each of those phases minimal ("schema + inferrer
branch") rather than each re-inventing a path.  Waiting until Phase 4
would mean rewriting Step 2.1's output in place.

## Consequences

- **Positive**:
  - Phases 2.1, 2.2, and 4.1 all reduce to: add a schema param, read it,
    build a `SpectralData`, construct `T6TabulatedAtSource(...)`.
  - Matrix §6.1 equation stays a single master formula with four
    specialisations (T1/T2/T3/T6) plus the T5 pass-through.
  - Stage 7 coverage harness can include S8/S11/S12 cells end-to-end.

- **Negative**:
  - One more descriptor variant to maintain.  Adds 4–5 lines in `__all__`,
    imports, and the assembly dispatch ladder.
  - Existing `_build_target_descriptor` still only emits T1Thermal today;
    Phases 2.1+ will be responsible for emitting T6 correctly.

- **Neutral**:
  - The descriptor numbering stays sparse (1, 2, 3, 5, 6) — T4 was reserved
    in ADR-0002 for a future "T4 Mixed with user-supplied ρ" and remains
    unused.
  - `descriptors_to_params` round-trip in `_inferrer` grows a branch for
    T6, but the lossy-boundary policy is unchanged (nested SpectralData
    round-trips via `SpectralData.to_dict` / `from_dict`, not the flat
    parameter dict).

## References

- [ADR-0002](0002-option-c-source-atmosphere-split.md) — the descriptor
  surface contract this ADR extends.
- [`RADIANT_Target_Definition_Matrix.md`](../RADIANT_Target_Definition_Matrix.md)
  §1 rows S8, S11, S12; §6.1 master equation.
- [`Target_Definition_Implementation_Plan.md`](../Target_Definition_Implementation_Plan.md)
  Phases 2 and 4.
- `CLAUDE.md` Rules 5 (Kirchhoff — informs ρ ≡ 0 choice for T6), 11
  (no cross-stage imports), 17 (no silent failure).
