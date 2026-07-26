# Geometry Flexibility — Generalized Viewing Geometry Development Plan

**Status:** Draft — awaiting owner ratification of §8.1 proposed decisions and answers to §8.2 open questions.
**Source audit:** `docs/reports/geometry_flexibility_2026-07/` (chartered 2026-07-26).
**Gaps served:** 107 (down-looking-only LOS), 108 (direction-blind backgrounds), 109 (path topology), 110 (turbulence stub), 111 (target kinematics). Related: 82 (clouds — untouched), 83 (two-point geodetic), 84 (ephemeris), 85 (mission-type relevance), 100 (IIRS).
**Supersedes on ratification:** the 2026-07-11 "v1 has no uplooking geometry" ruling (`RADIANT_Geometry.md` §4); requires a new ADR (ADR-0011, Phase 0 deliverable).

---

## 1. Objective

Make RADIANT express and correctly model **any observer/target altitude pair
and LOS direction**: air-to-air, air-to-ground, ground-to-air,
ground-to-space, space-to-ground (today's case), space-to-space in either
direction, and level/near-horizontal paths — with the atmosphere, background,
metrics, and GUI all direction-aware. Full flexibility is the end state;
the phases below sequence it so that each merge leaves `main` shippable and
each new scene class arrives with its radiometry *correct*, not merely
non-crashing.

## 2. Scene-Class Taxonomy (organizing frame for every phase)

Observer location × target location, each ∈ {ground (≈0–1 km), air
(1–100 km), space (> `h_atm_top`)}, with the LOS direction (up / down /
horizontal) derived from the altitude pair and zenith — never a separate
user switch (provenance-driven mode detection is retained unchanged).

| | Target: ground | Target: air | Target: space |
|---|---|---|---|
| **Obs: ground** | horizontal short-path (today: degenerate collocated carve-out) | **NEW** up-looking partial column | **NEW** up-looking full column (SST) |
| **Obs: air** | works today (ratify: GF-6) | **NEW** up/level/down partial paths | **NEW** up-looking partial column |
| **Obs: space** | v1 baseline | v1 (Gap 94/95 delivered) | exo (down-looking today; **NEW**: up-looking is Phase 1 quick win) |

## 3. Design Principles

1. **One canonical representation, extended — not a second one.** The
   target-referenced $\theta_o$ stays canonical, with its domain extended to
   $[0, \pi)$: $\theta_o < \pi/2$ = sensor above the target's horizon plane
   (all of today), $\theta_o > \pi/2$ = sensor below it (up-looking scenes,
   from the target's viewpoint). The spherical triangle is the same triangle
   read from the other vertex; `viewing_triangle` gains the symmetric
   solutions rather than a parallel module (Rule 27).
2. **The path is endpoint-symmetric; the radiometry is not.** Transmittance
   is reciprocal (arch doc §4.4) — one $\tau$ per segment, computed with the
   zenith at the segment's **lower endpoint** (matches the MODTRAN Card-3
   convention already implemented). Path radiance and backgrounds are
   direction-specific and get explicit per-direction products.
3. **Zero drift for existing scenes.** Every down-looking golden baseline is
   byte-identical through Phases 1–2 (the ADR-0006 precedent). New behavior
   is reachable only through newly legal inputs.
4. **No silent physics degradation at the edges.** Near-horizon
   ($|\theta_o - \pi/2| <$ guard) and limb-crossing paths raise actionable
   errors until a refraction/limb model exists — never a quietly wrong
   answer (Rule 17).

### 3.5 Upgradeability guardrails (review-blocking; owner-directed 2026-07-26)

These four are the identified spaghetti attractors of this upgrade. Each is
a **phase-gate criterion** — a PR that violates one is rejected in review,
exactly like a Rule 20 doc-drift violation, not deferred to a CU.

- **G1 — No flat-bundle accretion in `AtmosphericQuantities`.** New path
  products enter as *path-segment composition* (a segment product assembled
  per topology), not as ever-more parallel top-level fields. Alarm
  threshold: if the Phase 2 design has the flat contract exceeding ~12
  fields, or any field whose meaning depends on scene class, the design
  review rejects it and the segment abstraction becomes the contract.
  (Gate: Phase 2 design review.)
- **G2 — One source of truth for the sensor endpoint.** The same PR that
  puts `h_sensor` on `LineOfSightGeometry` **deletes every backend
  side-load** of `geometry.sensor_altitude_m` from params. Grep-provable
  exit criterion: no atmosphere backend `evaluate` path reads the parameter
  directly. Two live sources for one quantity is the CU-090/CU-093 disease
  ADR-0006 just cured; it does not come back. (Gate: Phase 1 exit.)
- **G3 — Scene-class conditioning is data, not scattered branches.** Metric
  applicability lives in **one declarative scene-class → relevance map**
  feeding the Gap 96 selection machinery (the mode-manifest pattern: owned
  as data, consumed by views). Per-metric `if scene_class == ...` branches
  in `performance/` modules are review-blocking. (Gate: Phase 3.)
- **G4 — Generalizations retire their carve-outs in the same PR (Rule 27).**
  The collocated no-triangle carve-out (`modes.py`) is subsumed by the
  horizontal-path solution in Phase 1; `evaluate_with_exo_target`'s override
  branch becomes a natural case of the Phase 2 path-segment product and the
  wrapper is deleted; the CU-096 legacy (altitude, angle) fallbacks are
  re-audited at Phase 3 close. A carve-out that must outlive its
  generalization gets an explicit deferral record (gating stage + re-audit
  date), never silence. (Gate: every phase close.)

## 4. Phases

### Phase 0 — ADR-0011 + scope ratification (Category A; docs only)

- Write ADR-0011 "Generalized viewing geometry": taxonomy (§2), canonical
  representation (§3.1), lower-endpoint path convention (§3.2), the
  supersession of the 2026-07-11 ruling, and the v1.x exclusions (limb
  radiance, refraction, ellipsoidal Earth — each with its validity guard).
- Reconcile `RADIANT_Use_Case_Matrix.md` "sensor fixed to space" with actual
  code behavior (GF-6): ratify air-to-ground as supported, define the new
  cells' target/atmosphere/background codes (A1 up-path enters the matrix).
- **Gate:** owner ratification of §8.

### Phase 1 — Direction-general geometry core (Category B)

- `core/viewing_triangle.py`: symmetric solutions valid for any
  `h_sensor ≠ h_target` ordering + the equal-altitude horizontal case
  (central-angle form); extended $\theta_o$ domain; horizon guard band.
  Level-0 tests first: up/down symmetry identities
  (η↔θ_o role swap), nadir/zenith limits, horizon behavior.
- `core/los_geometry.py`: `LineOfSightGeometry` carries **both endpoints**
  (`h_sensor` joins the contract; GF-3) and exposes signed direction;
  serialization round-trip extended back-compatibly.
- `geometry/modes.py` + `_schema.py` + `mode_manifest.py`: existing V1–V4
  entries generalized (elevation angle may go negative = target below
  sensor horizon; off-nadir becomes off-boresight with direction resolved
  from altitudes); agreement checks unchanged in form.
- **Exit criteria:** (a) quick win — up-looking space-to-space (LEO→GEO)
  runs end-to-end through the exo backend, the only blocker being this
  phase; (b) **G2** — zero backend side-loads of
  `geometry.sensor_altitude_m` remain (grep-provable); (c) **G4** — the
  collocated no-triangle carve-out in `modes.py` is subsumed by the
  general horizontal solution, not retained beside it.
- Golden down-looking baselines byte-identical.

### Phase 2 — Direction-aware atmosphere (Category C; the dominant cost)

- **Path-segment product** (Gap 109): backend contract evaluates a column
  between two altitudes with zenith at the lower endpoint; adds an
  up-path radiance product (sensor→target leg viewed from below) and a
  horizontal constant-altitude arm (analytic Beer-Lambert at local density
  in the simple model; MODTRAN ITYPE=1 wiring). Contract shape is governed
  by **G1**: segment composition, not flat-field accretion — the existing
  eight fields are unchanged for back-compat, but new products enter
  through the segment abstraction, and the Phase 2 design review rejects a
  flat contract past ~12 fields. **G4**: `evaluate_with_exo_target` folds
  into the general segment product and the wrapper is deleted in the same
  PR.
- **Sky-radiance-along-LOS + `SkyBackground`** (Gap 108): simple model
  single-scatter solar + graybody thermal along the view ray (reusing the
  CU-155/CU-161 machinery); MODTRAN via up-looking radiance runs.
  LOS-termination logic selects background defaults: hits Earth → ground;
  exits atmosphere → cold space; grazes limb → raise (excluded, §3.4).
- **Per-altitude solar illumination** (GF-9): replace the global
  $\theta_s < \pi/2$ bound with a shadow-height test — target sunlit iff
  its altitude exceeds the terminator shadow height for the given solar
  depression; enables sunlit-target-over-dark-ground.
- **MODTRAN library families** (GF-10): define the up-looking/horizontal run
  matrix (owner-run MODTRAN batch, the 17-deck pattern); interpolated-model
  axes extended; sec-space mapping revisited for the near-horizontal band.
- Truth anchors: MODTRAN up-looking runs (the existing H-runs are
  ground-up-looking — direct anchors for the up-path products), reciprocity
  checks ($\tau$ equal both directions), vacuum limits, horizontal-path
  analytic values.

### Phase 3 — Direction-aware degradations and metrics (Category C)

- **Turbulence** (Gap 110): $C_n^2$ profile family (HV-5/7 preset +
  tabulated), path-weighted $r_0$ with plane/spherical-wave options and
  zenith scaling; direct `r0_m` kept as override; the space-observer
  `ScopeError` replaced by profile-driven negligibility.
- **Metric conditioning** (GF-5/GF-13): scene-class → metric relevance map
  over the Gap 96 selection machinery (GSD/ground-range/NIIRS/access off by
  default for non-ground targets; angular resolution/target-plane sample
  distance on). Shape governed by **G3**: one declarative map, no
  per-metric scene-class branches. **G4**: the CU-096 legacy
  (altitude, angle) fallbacks are re-audited at this phase's close.
- **Detection-range solver** (GF-15): piecewise path-aware extinction.
- **Target kinematics** (Gap 111): target velocity params → LOS angular
  rate in GeometryStage → smear moving-target arm.

### Phase 4 — GUI (Category D)

- Mode-form labels + new mode wording (manifest auto-delivers structure).
- Schematic viewer: up-looking and horizontal compositions (ground plane
  placed by scene class; LOS ascending; both-elevated layout), angle-catalog
  extension, angle-truth tests extended per class.
- Scene-class steering: surfaces the Gap 85 mission-type concept for
  geometry (class chip driving defaults/relevance); full Gap 85 remains its
  own effort.
- Per the GUI workflow rule: each new scene class ships with a
  `gui_workflow.md` in its validation scenario.

### Phase 5 — Validation and scenario close-out (Category D)

- One golden scenario per newly-opened cell of §2's matrix (minimum:
  ground-to-air MWIR detection, ground-to-space SST visible, air-to-air
  level IRST, LEO→GEO exo). Each: walkthrough .md, units-on-all-outputs,
  regime discussion, gui_workflow.md.
- Full regression: all existing golden baselines unchanged; consistency
  check (Rule 4) green on the new classes; cross-model simple-vs-MODTRAN
  comparison per class.

## 5. Explicitly Out of Scope (this plan)

Limb-crossing radiance/earthlimb backgrounds (declined for v1.x — findings
GF-11), atmospheric refraction (guard-banded, not modeled), ellipsoidal
Earth, clouds (Gap 82), ephemeris/time-series geometry (Gap 84), two-point
geodetic entry (Gap 83 — the representation from Phase 1 is designed not to
preclude it).

## 6. Sequencing and effort

Phase 0: S. Phase 1: M. Phase 2: L (dominant; MODTRAN batch is owner-gated).
Phase 3: M. Phase 4: M. Phase 5: M. Phases 1 and 3a (turbulence) are
parallelizable after Phase 0; Phase 2 gates Phases 3b–5 for the new classes.

## 7. Registry and doc lock-step

Every phase updates in the same PR: `RADIANT_Geometry.md`,
`RADIANT_Atmosphere.md`, `RADIANT_Use_Case_Matrix.md`, parameter reference
(generated), CHANGELOG (results-affecting entries expected in Phases 2–3),
and gap statuses (107–111) per Rules 20–22/29.

## 8. Owner Decisions

### 8.1 Proposed for ratification

1. **Supersede the 2026-07-11 down-looking ruling** via ADR-0011 (the whole
   plan hangs on this).
2. **Canonical representation:** keep target-referenced $\theta_o$, extend
   domain to $[0, \pi)$; path segments keyed to the lower endpoint (§3).
3. **Ratify air-to-ground (airborne sensor, down-looking) as supported now**
   and update the Use-Case Matrix accordingly (GF-6).
4. **Limb/refraction exclusions** with hard validity guards (§3.4, §5).
5. **Horizon guard band**: paths within ±0.5° of the geometric horizon
   raise until refraction exists (value tunable at ratification).
6. **Use-Case Matrix moves to composition, not enumeration.** Adding the
   observer axis by enumerating cells would roughly triple an already
   60-row matrix and pull the code toward per-cell match arms. ADR-0011
   instead defines scenes compositionally — observer leg × target leg ×
   LOS-termination background — and the matrix is reduced to one worked
   example per §2 class. This is the highest-leverage anti-spaghetti
   decision in the plan (companion to guardrails §3.5).
7. **Guardrails §3.5 (G1–G4) are review-blocking phase-gate criteria**, on
   par with Rule 20 — a violating PR is rejected, not CU'd forward.
8. **Scene class is derived, never mandatory — with an optional validated
   assertion.** The class (§2) is computed from `h_sensor`, `h_target`, and
   θ_o and published with DERIVED provenance; physics never branches on it
   (it drives defaults, metric relevance, validation, and GUI composition
   only — the radiometry stays continuous in the real inputs). An optional
   `geometry.scene_class` enum lets the user assert intent: if set and it
   disagrees with the derivation, the stage raises
   `GeometrySpecificationError` (the CU-093 / redundant-mode-entry
   pattern) — catching wrong-magnitude altitude typos that pure derivation
   renders as a self-consistent scene of the wrong class. In the GUI the
   same assertion is the mission-type entry point (Gap 85 tie-in): picking
   a class steers defaults/relevance up front and is validated against the
   numbers entered afterward. A mandatory declaration is rejected: it
   re-states derivable truth, breaks sweeps that cross class boundaries,
   burdens every existing config, and invites the per-class physics
   branching G3 forbids.

### 8.2 Open questions

1. How far below the horizontal must the near-horizontal band be trusted?
   (Air-to-air at 200 km range grazes ~1° of Earth curvature — inside or
   outside the guard band?)
2. Up-looking MODTRAN library: which families does the owner want in the
   first batch (ground-to-space zenith ladder? slant set at fixed site?),
   and when can the batch run (ties to the MODTRAN boost-batch workflow)?
3. Does the sky background need polarization or aerosol-model selection at
   first delivery, or is the simple-model fidelity acceptable pending
   library data?
4. Target kinematics (Gap 111): first delivery as direct LOS-rate entry, or
   full target velocity vector?
