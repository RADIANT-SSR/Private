# ADR-0011: Generalized Viewing Geometry

**Date:** 2026-07-26
**Status:** Accepted

**Supersedes:** the 2026-07-11 owner ruling "v1 has no uplooking geometry"
(recorded in `RADIANT_Geometry.md` §4, enforced in
`core/viewing_triangle.py::_validate_altitudes`).
**Extends, does not replace:** ADR-0006 — `GeometryStage` remains stage 0, the
`geometry.*` namespace keeps its owner, and mode resolution stays
provenance-driven. This ADR widens what that stage is allowed to express.

## Context

RADIANT's viewing geometry is not merely "space-to-ground"; it is
*sensor-strictly-above-target*. `core/viewing_triangle.py` raises for
`h_sensor <= h_target`, and $\theta_o \in [0, \pi/2)$ is enforced three times
independently — in `viewing_triangle`, in `LineOfSightGeometry.__post_init__`,
and in `AtmosphericGeometry` (GF-1, GF-2). Every mission class the owner wants
next is behind that gate, including the pure-vacuum LEO→GEO case where no
atmospheric physics is even consulted.

Below those front doors the backends are already more general than the
contracts admit: `AtmosphericGeometry` documents that the target altitude "may
be greater than `sensor_altitude_m` for uplooking geometries",
`SimpleAtmosphere` integrates optical depth symmetrically between the endpoint
altitudes, and the MODTRAN deck builder already implements the lower-endpoint
zenith convention on Card 3 (`ANGLE = 180° − zenith` when $H_1 > H_2$,
`ANGLE = zenith` unchanged when the sensor is the lower endpoint; CU-065) plus
the ITYPE=1 horizontal path type. The capability is stranded behind the
geometry gate (GF-10).

The organizing frame is the observer × target altitude grid (plan §2), each
axis $\in$ {ground ($\approx$ 0–1 km), air (1–100 km), space (> `h_atm_top`)}:

| | Target: ground | Target: air | Target: space |
|---|---|---|---|
| **Obs: ground** | horizontal short path (today: degenerate collocated carve-out) | **new** — up-looking partial column | **new** — up-looking full column (SST) |
| **Obs: air** | works today numerically (GF-6) | **new** — up / level / down partial paths | **new** — up-looking partial column |
| **Obs: space** | v1 baseline | v1 (Gaps 94/95 delivered) | exo: down-looking today, **new** up-looking |

Reading the grid class-by-class against the audit findings gives the contract
requirements directly — the decisions below are consequences, not preferences:

| New class | What breaks today (evidence) | Contract consequence |
|---|---|---|
| Space→space up-looking (LEO→GEO) | Altitude ordering gate only; backends are vacuum (GF-1, audit §4) | Symmetric triangle solutions + extended $\theta_o$ domain — nothing else |
| Air→air level | Equal altitudes are represented as *geometry-free* scenes, not horizontal paths (GF-1); $\theta_o \approx \pi/2$ illegal (GF-2); no constant-altitude atmospheric arm (GF-11) | Central-angle horizontal solution; a horizontal path segment; a horizon guard, since no refraction model exists |
| Ground→air, ground→space | Sensor endpoint is absent from the Source→Atmosphere contract; backends side-load `geometry.sensor_altitude_m` (GF-3); topology has no up-path radiance and no sky-radiance-along-LOS (GF-7, GF-8); sun hard-bounded above the horizon blocks sunlit-target-over-dark-ground (GF-9) | `h_sensor` on `LineOfSightGeometry`; segment-composed path products; a `SkyBackground`; per-altitude illumination |
| Air→ground | Nothing — it already computes; only `RADIANT_Use_Case_Matrix.md`'s "sensor fixed to space" says otherwise (GF-6) | A doc reconciliation, ratified here |
| All nine | Ground-projection metrics, smear kinematics, and the 2D schematic assume a ground scene (GF-5, GF-13, GF-14, GF-17, GF-18) | Conditioning by scene class as *data*, not per-metric branches |

The common factor is that no class needs a *second* geometry model — each needs
the existing one read from a different vertex, plus radiometry that knows which
way the photons travel. The failure mode to avoid is therefore not "missing
physics" but **per-class branching**: nine classes × existing contracts is how
this upgrade becomes unmaintainable. Plan §3.5 names the four attractors
(G1–G4); this ADR makes them binding.

## Decision

1. **Scene class is the 3×3 observer × target grid above, and LOS direction is
   derived.** Up / down / horizontal follows from ($h_{sensor}$, $h_{target}$,
   $\theta_o$) — never a separate user switch. Provenance-driven mode detection
   (ADR-0006 §3) is retained unchanged.

2. **One canonical representation, extended — not a second one.** The
   target-referenced $\theta_o$ remains canonical with its domain extended to
   $[0, \pi)$: $\theta_o < \pi/2$ means the sensor is above the target's horizon
   plane (all of today's behavior), $\theta_o > \pi/2$ means it is below.
   It is the same Earth-centre / target / sensor spherical triangle read from
   the other vertex, on the same spherical Earth ($R_E = 6371.0$ km,
   `constants.R_EARTH_M`). `core/viewing_triangle.py` **gains the symmetric
   solutions**; no parallel module is created (Rule 27).

3. **Path segments are keyed to their lower endpoint.** Transmittance is
   reciprocal, so a segment carries **one** $\tau$, computed with the zenith
   angle evaluated at the segment's lower endpoint — the convention the MODTRAN
   Card-3 deck builder already implements (GF-10). Path radiance and
   backgrounds are *not* reciprocal: they are direction-specific and get
   explicit per-direction products (up-path radiance, down-path radiance,
   horizontal arm). A scene is therefore a composition of path segments, not a
   fixed eight-field bundle.

4. **The 2026-07-11 down-looking ruling is superseded.** Up-looking, level, and
   below-horizon-sensor geometry are in scope for v1.x.
   **The code restriction remains in force until Phase 1 of
   `docs/plans/Geometry_Flexibility_Plan.md` lands.** As of this ADR,
   `viewing_triangle.py::_validate_altitudes` still raises
   `ParameterBoundsError` for `h_sensor <= h_target`, `_validate_theta_o` and
   `LineOfSightGeometry.__post_init__` still reject $\theta_o \geq \pi/2$, and
   `AtmosphericGeometry` still caps the path zenith at `ZENITH_CEILING_RAD`
   (89.5°). This ADR changes the ruling, not the behavior; every doc statement
   of current behavior stays accurate until the enabling PR updates both
   together (Rule 20).

5. **Ratified exclusions, each with a validity guard, not silence (Rule 17):**
   - *Limb-crossing paths and earthlimb radiance* — **Declined for v1.x**
     (GF-11). An LOS that grazes or crosses the limb raises an actionable error
     naming the tangent altitude; it is never approximated.
   - *Atmospheric refraction* — not modeled; guard-banded (decision 6).
   - *Ellipsoidal Earth* — excluded; the spherical mean radius stays the single
     canonical Earth model (CU-097).

6. **Horizon guard band.** Paths within $\pm 0.5^\circ$ of the geometric
   horizontal ($|\theta_o - \pi/2| < 0.5^\circ$) raise an actionable error —
   hard guard, because refraction dominates there and is not modeled. Between
   $\pm 0.5^\circ$ and $\approx \pm 2^\circ$ the scene **computes** and emits a
   Rule-17 `UserWarning` quantifying the refraction-excluded caveat, so
   long-range air-to-air (which grazes $\approx 1^\circ$ of Earth curvature at
   200 km) is usable at first delivery.

7. **Guardrails G1–G4 (plan §3.5) are binding consequences of this ADR** —
   review-blocking phase-gate criteria on par with Rule 20. A violating PR is
   rejected, not CU'd forward:
   - **G1 — no flat-bundle accretion in `AtmosphericQuantities`.** New path
     products enter as *segment composition*, not as more parallel top-level
     fields. The contract holds eight product fields today; if a design puts it
     past $\approx 12$, or introduces any field whose meaning depends on scene
     class, the design review rejects it and the segment abstraction becomes
     the contract. (Gate: Phase 2 design review.)
   - **G2 — one source of truth for the sensor endpoint.** The PR that puts
     `h_sensor` on `LineOfSightGeometry` **deletes every backend side-load** of
     `geometry.sensor_altitude_m` in the same PR; grep-provable exit criterion
     (no atmosphere backend `evaluate` path reads the parameter directly).
     Two live sources for one quantity is the CU-090/CU-093 disease ADR-0006
     cured. (Gate: Phase 1 exit.)
   - **G3 — scene-class conditioning is data.** One declarative
     scene-class → metric-relevance map feeds the Gap 96 selection machinery
     (the mode-manifest pattern: owned as data, consumed by views). Per-metric
     `if scene_class == ...` branches in `performance/` are review-blocking.
     (Gate: Phase 3.)
   - **G4 — generalizations retire their carve-outs in the same PR** (Rule 27):
     the collocated no-triangle carve-out in `geometry/modes.py` is subsumed by
     the horizontal solution; `atmosphere/exo_target.py::evaluate_with_exo_target`
     becomes a natural case of the segment product and the wrapper is deleted;
     the CU-096 legacy (altitude, angle) fallbacks are re-audited at Phase 3
     close. A carve-out that must outlive its generalization gets an explicit
     deferral record (gating stage + re-audit date). (Gate: every phase close.)

8. **Scene class is derived, never mandatory, with an optional validated
   assertion.** It is computed from $h_{sensor}$, $h_{target}$, and $\theta_o$
   and published with `Provenance.DERIVED`. **Physics never branches on it** —
   it drives defaults, metric relevance, validation, and GUI composition only;
   the radiometry stays continuous in the real inputs. An optional
   `geometry.scene_class` enum lets a user assert intent: if set and it
   disagrees with the derivation, the stage raises `GeometrySpecificationError`
   (the CU-093 redundant-entry pattern), catching wrong-magnitude altitude
   typos that pure derivation would otherwise render as a self-consistent scene
   of the wrong class. In the GUI the same assertion is the mission-type entry
   point (Gap 85 tie-in). A **mandatory** declaration is rejected: it restates
   derivable truth, breaks sweeps that cross class boundaries, burdens every
   existing config, and invites exactly the per-class branching G3 forbids.

9. **Scene definition becomes compositional, not enumerated.**
   `RADIANT_Use_Case_Matrix.md` moves from cell enumeration to composition —
   **observer leg × target leg × LOS-termination background** — with one worked
   example per §2 class replacing exhaustive tables. Adding the observer axis by
   enumeration would roughly triple an already 60-row matrix and pull the code
   toward per-cell match arms. LOS termination selects the background: hits
   Earth → ground; exits the atmosphere → cold space; grazes the limb → raise
   (decision 5).

10. **Also ratified here:**
    - **Air-to-ground** (airborne sensor, down-looking) is supported *now*
      (GF-6) — it already works numerically through the simple model and
      MODTRAN H1/H2; the Use-Case Matrix's "sensor fixed to `space` in v1"
      statement is superseded and reconciled to code behavior in Phase 0.
    - **Per-altitude solar illumination** replaces the global
      $\theta_s < \pi/2$ bound with a shadow-height test — a target is sunlit
      iff its altitude exceeds the terminator shadow height for the given solar
      depression (GF-9). Consequence for Phase 2; the global bound stands until
      then.
    - **Scene-class priority order** (owner): ground-to-air → air-to-air →
      up-looking space-to-space (LEO→GEO) → ground-to-space (SST). Phase 2
      library work targets the first two; the LEO→GEO quick win ships alone;
      the Gap 110 turbulence upgrade (SST-critical) may trail within Phase 3.
    - **Sky-background gating is band-split:** MWIR/LWIR sky backgrounds are
      supported at first delivery; VIS/NIR sky computes but carries a
      "provisional — single-scatter underestimates daytime sky" `UserWarning`
      until MODTRAN-anchored.
    - **Target kinematics (Gap 111) ships both doors,** provenance-resolved:
      direct LOS-rate entry and a target-velocity-vector mode deriving it, with
      the V0–V4 agreement-check pattern on disagreement.
    - **The up-looking/horizontal MODTRAN library families are owner-run**: the
      batch-1 decks (ground-to-air up-looking partial-column ladder, horizontal
      constant-altitude set, CU-065 elevated-endpoint ANGLE convention check)
      are appended to `docs/plans/modtran_run_matrix.csv`; the SST full-column
      ladder is batch 2.

## Rationale

The nine classes differ in *radiometric topology*, not in geometry. One
spherical triangle already solves every altitude pair; the down-looking
restriction is ~10 lines of validation policy, not an assumption baked into the
math (audit §4). Extending the domain of the existing canonical angle therefore
buys eight new classes at the cost of symmetric solutions and a guard band,
while a second representation would double the invariants every downstream
consumer must respect. Keying segments to the lower endpoint exploits
reciprocity to keep exactly one $\tau$ per segment and matches the convention
the MODTRAN deck builder already implements, so the up-looking library families
anchor the same code path the simple model uses.

The guardrails carry equal weight to the physics decisions because the
identified failure mode of this upgrade is structural, not numerical: nine
scene classes multiplied into a flat quantities bundle, a duplicated sensor
altitude, per-metric class branches, and carve-outs left standing beside their
generalizations. Each of G1–G4 names the specific accretion and its
grep-provable or count-provable exit criterion, which is what makes them
reviewable rather than aspirational.

### Alternatives Considered

| Option | Pros | Cons |
|--------|------|------|
| **A. Extend $\theta_o$ to $[0,\pi)$ in `viewing_triangle` (chosen)** | One canonical angle, one module, one set of invariants; existing down-looking goldens byte-identical; symmetric identities are directly testable ($\eta \leftrightarrow \theta_o$ role swap) | Requires careful angle bookkeeping near $\pi/2$; needs an explicit guard band where refraction is absent |
| B. Sensor-referenced canonical angle (swap to $\eta$) | Natural for up-looking; matches how an observer thinks | Inverts today's convention everywhere; breaks the ADR-0002 LOS contract, MODTRAN Card-3 mapping, and every golden baseline for zero new capability |
| C. Parallel `uplooking_triangle.py` module | Fastest to write; no risk to existing paths | Two canonical models (Rule 27 violation); the collocated and near-horizon cases belong to neither; guarantees divergence |
| D. Per-scene-class geometry/atmosphere branches | Each class tuned independently; simple first PR | The spaghetti attractor G1/G3 exist to prevent; nine-way branching in physics modules; class becomes mandatory input |
| E. Enumerate the observer axis in the Use-Case Matrix | Familiar format; explicit cells | ~180-row matrix; pulls code toward per-cell match arms; unmaintainable in lock-step (Rule 20) |
| F. Model refraction now instead of guard-banding | Removes the excluded band entirely | Large, MODTRAN-anchored effort gating all nine classes; the $\pm 2^\circ$ shoulder covers the operational air-to-air need at a fraction of the cost |

## Consequences

- **Positive:** Eight new scene classes become expressible from one triangle;
  LEO→GEO up-looking needs only the altitude gate lifted (Phase 1 quick win);
  air-to-ground becomes documented-and-supported instead of
  works-but-undocumented; `h_sensor` gets a single home (G2) closing the last
  ADR-0006-era duplication; MODTRAN's already-implemented uplooking ANGLE and
  ITYPE=1 horizontal capability becomes reachable; the Use-Case Matrix stops
  growing combinatorially; sunlit-target-over-dark-ground becomes expressible
  (Phase 2).
- **Negative:** `LineOfSightGeometry` gains a field, so the ADR-0002 contract
  and its serialization round-trip change (back-compatibly); `AtmosphericQuantities`
  must grow through a segment abstraction rather than the cheaper flat route;
  a guard band means some near-horizontal scenes raise where a naive model
  would return a number; the MODTRAN up-looking/horizontal library families
  must be *generated* (owner-run batch, decks appended to
  `docs/plans/modtran_run_matrix.csv`), not merely wired.
- **Neutral:** `GeometryStage` remains stage 0 and mode resolution is unchanged
  in form (ADR-0006 intact); the extended $\theta_o$ domain is reachable only
  through newly legal inputs, so every existing down-looking golden baseline is
  byte-identical through Phases 1–2; scene class appears in
  `stage_outputs["geometry"]` as a derived, inspectable label with no physics
  authority. **No code behavior changes with this ADR**: uplooking, horizontal,
  and $\theta_o \geq \pi/2$ inputs are still rejected by
  `core/viewing_triangle.py`, `core/los_geometry.py`, and
  `atmosphere/protocol.py` until Phase 1 lands. Limb radiance, refraction,
  ellipsoidal Earth, clouds (Gap 82), ephemeris geometry (Gap 84), and
  two-point geodetic entry (Gap 83) stay out of scope, the last explicitly not
  precluded by the Phase 1 representation.

## References

- `docs/plans/Geometry_Flexibility_Plan.md` — execution plan; §2 taxonomy,
  §3 design principles, §3.5 guardrails G1–G4, §8.1/§8.2/§8.3 ratification
  record (owner, 2026-07-26).
- `docs/reports/geometry_flexibility_2026-07/` — chartered audit; findings
  GF-1 … GF-18 and the disposition table (immutable record, Rule 24).
- `docs/adr/0006-geometry-stage.md` — GeometryStage as stage 0; extended, not
  replaced, by this ADR.
- `docs/adr/0002-option-c-source-atmosphere-split.md` — the
  `LineOfSightGeometry` Source → Atmosphere contract this ADR extends with the
  sensor endpoint.
- `docs/architecture/RADIANT_Geometry.md` §4 — the formula standard and the
  superseded 2026-07-11 down-looking ruling; updated in Rule-20 lock-step.
- `docs/architecture/RADIANT_Use_Case_Matrix.md` — the enumerated matrix this
  ADR replaces with composition; "sensor fixed to space" scope statement
  superseded (GF-6).
- `docs/architecture/RADIANT_Atmosphere.md` §4 — lower-endpoint zenith
  convention and transmittance reciprocity; `atmosphere/modtran.py` Card-3
  comments (CU-065) for the MODTRAN ANGLE mapping.
- `docs/tracking/gaps.md` — Gaps 107 (LOS direction), 108 (backgrounds),
  109 (path topology), 110 (turbulence), 111 (target kinematics); related
  83, 84, 85, 96, 100.
