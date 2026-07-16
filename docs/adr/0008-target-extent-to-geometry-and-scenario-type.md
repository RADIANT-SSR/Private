# ADR-0008: Target Spatial Extent Belongs to Geometry; a Declared Scenario Type Guides Setup

**Date:** 2026-07-15
**Status:** Accepted (owner-ratified 2026-07-15). **Phase A shipped 2026-07-16** (commit
`ecf96c5`). **Decision 4 refined by Amendment 1 (2026-07-16)** — the declared scenario type
already partly exists as `source.scene_type` / `source.regime_override`. **Decision 2 refined by
Amendment 2 (2026-07-16, owner-ratified)** — Phase B moves only the *projected-area* computation
to Geometry; the tentative regime classification **stays in SourceStage** (it is entangled with
descriptor inference). See both amendments at the end of this ADR before executing Phase B/T2.

## Context

ADR-0006 made geometry **Stage 0** and moved the viewing triangle, line of sight, and
slant range (`geometry.target_range_m`) into it — resolving the "range lives in Source but
means a geometry thing" smell (CU-093) and the altitude duplication (CU-090). But it left
one geometry quantity behind in Source: the **target's spatial extent** — its shape,
dimensions, and orientation, from which the **projected area** and hence the target's
angular subtense are computed.

Three facts show that extent is already a geometry computation wearing a Source costume:

1. **Projected area is a function of the viewing direction.**
   `Shape.projected_area(view_direction)` ([source/shape.py:32](../../src/radiant/source/shape.py#L32))
   and `CompositeShape.projected_area` ([source/composite.py:46](../../src/radiant/source/composite.py#L46))
   take a view-direction unit vector in the scene frame.
2. **That view direction comes from the Geometry stage.** The Source inferrer computes
   `view_dir = _view_direction_from_los(...)` then `shape_obj.projected_area(view_dir)`
   ([source/_inferrer.py:662-663](../../src/radiant/source/_inferrer.py#L662-L663)), where
   the LOS is the one **GeometryStage resolved** — Source reaches *back* into
   `stage_outputs["geometry"]["los_geometry"]` and `geometry.target_range_m`
   ([source/stage.py:106,170](../../src/radiant/source/stage.py#L170)) to do it.
3. **Regime classification is rooted in that geometry quantity.**
   `θ_target = √(projected_area) / range` (RADIANT_Source_Target_System §7.1) drives the
   `POINT_SOURCE / SUB_PIXEL / EXTENDED` classification, yet the **tentative** classification
   runs in `SourceStage` (Rule 10 stage-1) because that is where `projected_area` currently
   lives.

So the target's extent parameters (`source.target.shape`, `source.target.shape_*_m`,
`source.target.shape_{yaw,pitch,roll}_rad`, `source.target.projected_area_m2`) sit in Source,
but the computation they feed is geometric and already depends on Geometry's output. Source
does the geometry, then hands itself back a number.

**Why this now matters.** The GUI redesign (ADR D6) makes stage boundaries **user-visible as
tabs**. A Source tab that bundles "how big and how oriented is the target" with "what does it
radiate" does not match the operator mental model. The owner's observation (2026-07-15): the
engagement geometry **and** the target's shape/orientation want to be defined together on the
Geometry tab, leaving the Source tab for the spectral/material properties of target and
background. The stage boundary that was merely an internal smell becomes a UX seam.

**A second, coupled gap.** Operators have no way to declare mission/scenario **intent** up
front so the tool can guide which parameters matter (e.g. an extended scene needs a background
but not a target temperature). RADIANT only ever **derives** the regime bottom-up. A `regime.override`
exists (`auto | force_point | force_subpixel | force_extended`, §7.4) but it is a **hard physics
override**, not a setup guide, and it does not drive parameter relevance or cross-check intent
against the derived result. This is **Gap 85** (DEFERRED post-v1) and the
`project-mission-type-selector` design note.

These two are physically coupled: after the extent moves, Geometry owns `θ_target`, which is
*the* input to the regime — so Geometry is also where a declared-vs-derived regime cross-check
naturally anchors. Settling one without the other would touch the same seam twice.

**Pre-existing doc drift (to reconcile, not caused here).** RADIANT_Source_Target_System §8
inventories these parameters as `source.geometry.*` / `source.orientation.*`, but the shipped
schema names them `source.target.shape_*` / `source.target.shape_{yaw,pitch,roll}_rad`. The
inventory predates the shipped names. Filed as a CU; reconciled by this migration.

## Decision

1. **Move the target's spatial extent from Source to Geometry.** Migrate the shape,
   dimension, orientation, and projected-area parameters from `source.target.*` to a new
   `geometry.target.*` namespace, each with a **deprecated alias** for a full deprecation
   window (precedent: CU-090 `platform.h_sensor` → `geometry.sensor_altitude_m`; CU-093
   range). Relocate the projected-area computation (shape kernels + `projected_area(view_direction)`)
   into `GeometryStage`, which already owns the LOS/view-direction. Source no longer owns or
   computes extent.

2. **Relocate tentative regime classification to Geometry.** Because `GeometryStage` now owns
   `projected_area_m2` and `range` → `θ_target`, it computes the **tentative** regime.
   `OpticsStage` still finalizes with `θ_PSF` (Rule 10 **stage-2 unchanged**). Rule 10's text
   updates: tentative classification is emitted by `GeometryStage`
   (`stage_outputs["geometry"]["regime_tentative"]`), not `SourceStage`.

3. **Source becomes purely spectral / material.** `SourceStage` reads
   `stage_outputs["geometry"]["projected_area_m2"]` and produces target + background spectral
   radiance from temperature / emissivity / reflectance / BRDF (the §3 source-type taxonomy —
   thermal / reflected-solar / combined — is unchanged). No geometry ownership remains in Source.

4. **Introduce a declared scenario type.** A new operator-facing declaration —
   `scenario.type` (enum: `auto | extended | sub_pixel | point_source`, default `auto`) —
   captures mission intent. It:
   - **(a)** drives **parameter relevance** (which knobs matter for the declared type),
     authored as a function of `regime × the existing phenomenology dispatch` (§8.5) — so no
     second declared axis is needed;
   - **(b)** optionally **seeds** the `regime.override` default (a declaration is a soft
     default; forcing remains explicit via `regime.override`);
   - **(c)** is **cross-checked** against the derived *final* regime after evaluate — a
     mismatch (declared `extended`, derived `point_source`) raises a **non-fatal, surfaced
     warning** on the result (Rule 17: named, never silent).

   The declaration **never overrides the physics**: Rule 10 bottom-up derivation stays
   authoritative unless the user explicitly forces via `regime.override`. This is the two-tier
   design (declare-to-guide, derive-to-compute, cross-check-to-warn) the mission-type note called for.

5. **Results-neutral.** The migration relocates computations without changing them; the golden
   suite must be **byte-identical** and is the acceptance gate. The declared-type + cross-check
   layer adds a warning surface only — it changes no computed number.

### Naming (ratified 2026-07-15)
- Extent namespace: **`geometry.target.*`** (ratified; `geometry.object.*` was the alternative).
- Declared type: **`scenario.type`** (ratified; new top-level, operator-facing; `regime.declared`
  beside `regime.override` was the alternative). Both names may still be refined during tier-1
  implementation if a concrete conflict surfaces, per the deprecation-alias mechanics below.

## Rationale

### Alternatives Considered

| Option | Pros | Cons |
|--------|------|------|
| **A — GUI-presentation regroup only** (keep extent in `source.target.*`; Geometry tab merely *renders* the Source controls) | Zero physics risk; ships immediately; precedent exists (§4.4.1 GUI-grouping, CU-137) | Leaves the Source-reaches-into-Geometry smell; the parameter tree + YAML still show `source.*` on the Geometry tab, so the mismatch resurfaces for any power user; does not advance the geometry-first principle ADR-0006 established. The fallback if the migration is declined, not the architecture answer. |
| **B — Physical extent move + declared scenario type** (chosen) | Stage boundaries match the physics; Geometry owns everything determining angular subtense + tentative regime; Source is a clean spectral layer; GUI tabs map to mental model; unblocks Gap 85; a natural home for the (future) attitude owner (CU-122) | Parameter migration with a deprecation window; touches Rule 10 wording; multi-doc lock-step; relevance-metadata authoring is real work (phased) |
| **C — Full named-archetype scenario system now** (curated presets spanning regime × phenomenology × input-path × band) | Richest guided setup | Largest design + maintenance surface; belongs in the deferred preset/library browser (arch §7.2 row 5 / gaps GUI-5), not this boundary ADR |

**On the declared-type axes.** Regime-only *declared* (option 1 of the owner question) is chosen
over a declared regime × phenomenology matrix because phenomenology is already
**parameter-dispatched** (§8.5 decides thermal / reflected / combined from the physics-dispatch
params the user sets anyway). Authoring relevance as `regime × dispatched-phenomenology` gives the
matrix's full expressiveness from a single declared knob. Named archetypes are deferred to the
preset browser.

## Consequences

- **Positive:** Stage boundaries match the physics — Geometry owns extent → projected area →
  θ_target → tentative regime; Source is a pure spectral/material layer; the GUI Geometry and
  Source tabs map to the operator mental model without presentation/namespace mismatch; the
  declared scenario type unblocks Gap 85 guided setup and adds a declared-vs-derived safety
  cross-check; provides the natural stage home to later resolve the platform/target attitude
  owner (CU-122); completes the geometry-first arc ADR-0006 began.
- **Negative:** A parameter-namespace migration with a deprecation window (aliases, provenance,
  round-trip tests); Rule 10 wording changes (tentative → GeometryStage); multi-doc lock-step
  (this ADR + ADR-0006 cross-ref, RADIANT_Geometry, RADIANT_Source, RADIANT_Source_Target_System,
  RADIANT_Signal_Chain_Architecture, RADIANT_Parameter_System, and the regime docs); the
  per-regime relevance metadata (Gap 85 prereq) is genuine authoring work.
- **Neutral:** `regime.override` semantics are unchanged; the five input paths (§6) are
  unchanged — they still describe *how the target is specified*, now split across a
  geometry-extent front and a source-spectral front; the source-type taxonomy (§3) is untouched;
  golden results are byte-identical by construction.

## Scope and Phasing

This ADR ratifies the **boundary + declared-type contract**. Implementation lands in tiers so
GUI Phase II can consume the clean boundary early while the guided-setup metadata trails:

1. **Extent migration** — `source.target.*` → `geometry.target.*` (aliases), computation +
   tentative-regime relocation to GeometryStage. **Results-neutral; golden suite is the gate.**
2. **Declared scenario type** — `scenario.type` parameter + the declared-vs-derived cross-check
   warning. Adds a surface, no results change.
3. **Guided setup (Gap 85)** — per-regime parameter-relevance metadata on the `_schema.py`
   ParameterDefs + the API relevance surface + the GUI selector / badging. Incremental; may
   trail Phase II.

## References

- ADR-0006 (Geometry Is Stage 0) — this ADR completes the extent it left in Source
- CLAUDE.md **Rule 10** (regime tentative → final), **Rule 12** (schema), **Rule 7** (deprecation)
- CU-090, CU-093 (parameter-migration + alias precedents); CU-122 (attitude owner, adjacent)
- **Gap 85** (mission-type-driven parameter relevance) and the `project-mission-type-selector` note
- RADIANT_Source_Target_System.md §3 (source types), §5 (target geometry), §6 (five input paths),
  §7 (auto regime detection), §8 (parameter inventory — names to reconcile)
- `src/radiant/core/regime.py` (`RadiometricRegime`, `TargetInputPath`, thresholds)

---

## Amendment 1 (2026-07-16) — the declared scenario type already partly exists; refine Decision 4

**Discovered during Phase A** (inspecting `source/_schema.py`): the "declared scenario type"
Decision 4 proposed adding as a *new* `scenario.type` param is **already present**, split across
two existing parameters. Decision 4 is refined — **do not add a new `scenario.type`; build T2 on
what exists.** This changes nothing in Phase A/B; it re-scopes T2.

**What already exists:**
- **`source.scene_type`** — enum `("auto", "extended", "sub_pixel", "point_source")`, default
  `"auto"` (a distinct "user did not set this" sentinel). It is the **matrix §3.2 declared
  scene-type axis**: when set explicitly it **wins over inference** and drives which descriptor /
  spec-form is built (`core/descriptors.py` `TargetDescriptor.scene_type`: extended→radiance `L`,
  sub_pixel/point→intensity `I`). This *is* the "declare intent up front" surface (Decision 4a)
  — it exists and is wired.
- **`source.regime_override`** — enum `("auto", "extended", "point_source", "sub_pixel")`, default
  `"auto"`. It **forces** the regime in `SourceStage`'s tentative classification
  (`stage.py`: `if regime_override != "auto": regime = RadiometricRegime(regime_override)`). This
  *is* the "force the physics" surface (Decision 4b) — it exists and is wired.

**What does NOT exist (the genuinely new T2 work):**
- The **declared-vs-derived cross-check**: nothing compares the declared `source.scene_type` (or
  the regime it implies) against the **OpticsStage final** regime after evaluate and warns on a
  mismatch (Decision 4c). This is the real new capability — a surfaced, non-fatal warning.
- The **per-regime parameter-relevance metadata** + relevance surface (Gap 85 / Decision 4a's
  "guides which parameters matter"). Still to author.

**Refined Decision 4 (for T2):**
1. Use the **existing `source.scene_type`** as the declared axis — do **not** mint `scenario.type`.
   Whether to *relocate/rename* it (e.g. to `geometry.target.scenario_type`, alongside the extent
   it now sits near, or leave it in `source`) is a T2 sub-decision; default is **leave it as
   `source.scene_type`** to avoid a second migration, and reconcile naming only if T2 shows cause.
2. Keep **`source.regime_override`** as the force-physics axis (unchanged). Clarify in docs that
   `scene_type` = declared intent (guides + cross-checked, non-binding) while `regime_override` =
   hard force (binding). The two are distinct and both stay.
3. T2's build list shrinks to: (a) the **declared-vs-derived cross-check warning**, and (b) the
   **relevance metadata** (Gap 85) — not a new declaration param.

**Also refine §8-reconcile note:** `RADIANT_Source_Target_System.md` §8.10 (regime control) and §7
should document the `scene_type` vs `regime_override` distinction explicitly when T2 lands.

---

## Amendment 2 (2026-07-16, owner-ratified) — Phase B moves projected-area only; tentative regime stays in Source

**Discovered at Phase B kickoff** (reading `source/stage.py` + `source/_inferrer.py`): the Decision-2
plan to relocate **both** the projected-area computation **and** the tentative regime classification
to GeometryStage collides with real entanglement the ADR did not anticipate:

1. **Shape → projected-area is embedded in Source's descriptor inference.**
   `_inferrer._resolve_projected_area_and_shape` builds the `TargetShape`, computes
   `A_t = shape.projected_area(view_dir)`, applies the Q3 shape-wins-over-`projected_area` rule (with a
   `UserWarning`), enforces the S9/`at_aperture` incompatibility guard, and threads `A_t` **and the
   shape object** into the `TargetDescriptor`. It is not a standalone geometry function.
2. **Tentative regime is genuinely cross-cutting** (`source/stage.py::_classify_regime`): it mixes
   geometry (`√A/range`), detector/optics (IFOV = `pixel_pitch/focal_length`), **and** source concerns
   (`fill_fraction`, `regime_override`, and the **T7 intensity** reference-area case, which depends on
   the *descriptor type* known only inside Source inference). It is called twice (before/after
   inference). Forcing it into Geometry (stage 0) would make Geometry read detector/optics/source
   params and still could not resolve the T7 descriptor-derived-area case cleanly.
3. **Latent finding (CU filed):** the `TargetDescriptor.shape` field is stored but has **no downstream
   reader** — write-only today (the "stages narrow via `isinstance`" comment describes no live
   consumer). Tracked separately; not resolved by Phase B.

**Refined Decision 2 (owner-ratified 2026-07-16):**
- **Phase B moves only the projected-area computation to GeometryStage.** Geometry builds the shape
  from `geometry.target.shape*`, computes `projected_area_m2` (shape-based via its own LOS view
  direction, else the `geometry.target.projected_area_m2` param), and publishes
  `stage_outputs["geometry"]["projected_area_m2"]` (the pure geometric quantity). SourceStage **reads**
  that value instead of recomputing it.
- **The tentative regime classification STAYS in SourceStage.** It is inherently entangled with
  descriptor inference (`fill_fraction`, `regime_override`, T7 reference area). **Rule 10 is
  unchanged** — tentative in SourceStage, final in OpticsStage. This is a more honest stage boundary
  than pushing descriptor-coupled regime logic into stage 0.
- The Source-side concerns that are *not* pure geometry — the shape-wins `UserWarning`, the
  S9/`at_aperture` guard (both `target_location`-dependent), the descriptor `shape` field, and the T7
  reference-area regime case — **stay in Source**. Geometry publishes the number; Source keeps the
  descriptor semantics.

**Consequence for the plan:** `Target_Extent_Geometry_Plan.md` Phase B is rescoped to
"projected-area relocation only" and its Rule-10 doc-update row is dropped (Rule 10 does not change).
Results-neutral still governs: the full golden suite must be byte-identical.
