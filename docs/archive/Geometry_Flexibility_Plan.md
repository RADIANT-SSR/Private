> **HISTORICAL — archived 2026-07-28 (completed by the coding agent; all five phases delivered).** Phase 0 ADR-0011 + matrix composition (`f6b747a`); Phase 1 direction-general core (`c869d06`); Phase 2 direction-aware atmosphere (`0748dff`); Phase 3 degradations/metrics (`0b08ee7`); Phase 4 direction-aware GUI (`6365dfa`); Phase 5 validation scenarios + G4 close-out (this merge). Outstanding items live in the registries: owner-run MODTRAN batch 2, CU-236, CU-253…CU-269, Gaps 113–115.

# Geometry Flexibility — Generalized Viewing Geometry Development Plan

**Status:** Complete — §8.1 ratified in full and §8.2 answered by the owner 2026-07-26 (record: §8.3). Phases 0–2 complete 2026-07-26, Phase 3 complete 2026-07-27, Phases 4–5 complete 2026-07-28. **All five phases delivered.** Outstanding beyond this plan: the owner-run MODTRAN batch 2 (SST full-column ladder + twilight/refraction calibration pair — anchors the ground-to-space class and calibrates the horizon-guard thresholds), the owner-gated CU-236 down-looking detection-range swap, and the validation-wave findings CU-253…CU-269 / Gaps 113–115 (headline: CU-253, results-affecting VIS Rayleigh coefficient).
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

### Phase 0 — ADR-0011 + scope ratification (Category A; docs only) — COMPLETE 2026-07-26

- ✅ ADR-0011 "Generalized Viewing Geometry" accepted
  (`docs/adr/0011-generalized-viewing-geometry.md`): taxonomy (§2), canonical
  representation (§3.1), lower-endpoint path convention (§3.2), the
  supersession of the 2026-07-11 ruling (code restriction stays in force
  until Phase 1), the v1.x exclusions with validity guards, the two-tier
  horizon guard, guardrails G1–G4 as binding consequences, and the
  derived-scene-class decision.
- ✅ `RADIANT_Use_Case_Matrix.md` reconciled and converted to compositional
  scene definition (observer leg × illumination leg × LOS-termination
  background; one worked example per §2 class; semantic-preservation ledger
  §3.5): air-to-ground ratified supported, A1 up-path and A5 horizontal-arm
  codes enter the catalog, B2 `SkyBackground` ratified band-gated.
- ✅ Batch-1 MODTRAN decks appended to `docs/plans/modtran_run_matrix.csv`
  (K1–K7 ground-to-air up-looking ladder incl. the CU-065 elevated-endpoint
  ANGLE check at K7; L1–L4 constant-altitude horizontal set — owner runs).
- ✅ Rule-20 lock-step: `RADIANT_Geometry.md` §4 cites ADR-0011 and states
  the restriction remains until Phase 1; ADR index updated; Gap 107 status
  refreshed.
- **Gate:** owner ratification of §8 — satisfied (§8.3, 2026-07-26).

### Phase 1 — Direction-general geometry core (Category B) — COMPLETE 2026-07-26

Exit criteria met: (a) LEO→GEO up-looking runs end-to-end through the exo
backend (`tests/integration/test_uplooking_phase1.py` — vertical θ_o = π
exact and slant cases, vacuum identities exact); (b) **G2** grep-provable —
zero `geometry.sensor_altitude_m` parameter reads under
`src/radiant/atmosphere/`; (c) **G4** — the collocated no-triangle
carve-out is subsumed by the level central-angle solution (only the
zero-separation coincident-endpoints limit keeps None ranges, documented).
Down-looking golden baselines byte-identical (differential proof over
9 256 configurations + full golden suite). Up-looking/level paths through
real atmosphere refuse actionably pending Phase 2. θ_o domain implemented
**closed** `[0, π]` — ADR-0011's `[0, π)` was a notation slip,
owner-confirmed 2026-07-26 (§8.3 addendum). CU-222 filed
(guard-threshold units).

- `core/viewing_triangle.py`: symmetric solutions valid for any
  `h_sensor ≠ h_target` ordering + the equal-altitude horizontal case
  (central-angle form); extended $\theta_o$ domain; horizon guard band
  per the §8.3 addendum (tangent-point topology: angular bands for
  endpoint-minimum paths, tangent-height-depression thresholds —
  provisional 100 m / 2 km — for interior-tangent paths).
  Level-0 tests first: up/down symmetry identities
  (η↔θ_o role swap), nadir/zenith limits, horizon behavior, and the
  guard-topology boundary cases (short A5 arm clean; 200 km air-to-air
  warns; deep transit raises).
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

### Phase 2 — Direction-aware atmosphere (Category C; the dominant cost) — DELIVERED 2026-07-26 (simple backend); MODTRAN library families outstanding

Exit state: `AtmosphereStage` dispatches on the derived `los.los_direction`
(`atmosphere/topology.py`) — `down` takes the backend's own `evaluate`
unchanged and byte-identical, `up`/`level` take the segment composition
(`observer_leg.py` → `segment_simple.py` / `level_arm.py`, assembled by
`uplooking_quantities.py`). Matrix classes E2 (ground→air), E3 (ground→space
SST), E5 (air→air level) and E6 (air→space) run end-to-end on
`atmosphere.model = "simple"`; other backends raise an actionable **capability**
error naming what is supported. `SkyBackground` (matrix B2) and the Rule-B
LOS-termination selector (`core/los_termination.py`) land with it, band-gated as
ratified. GF-9 per-altitude illumination lands (`solar_shadow.py`,
`solar_transit.py`; `geometry.solar_zenith_rad` bound widened to π). **G1** held:
`AtmosphericQuantities` still has exactly eight product fields. **G4**
discharged: `evaluate_with_exo_target` and `_uplooking_guard` are deleted, the
exo carve-out folded into the segment composition with a 3 124-configuration
bit-identity differential proof. Zero drift: all 78 golden baselines unchanged.
**Outstanding:** MODTRAN / interpolated up-looking + ITYPE=1 **library
families** (owner-run batch 2 — the deck builder is wired, the runs are not),
the twilight and refraction calibration decks, and CU-224 (down-looking
`L_path_up` carries no thermal term, so the two topologies use different
path-radiance physics).


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

### Phase 3 — Direction-aware degradations and metrics (Category C) — COMPLETE 2026-07-27

Exit state: Gap 110 delivered (Cn² profile family + path-weighted r₀,
HV-5/7 anchored to 0.8 % of the Andrews & Phillips value; space-observer
`ScopeError` retired per G4); Gap 111 delivered (both kinematics doors +
relative-motion smear arm feeding both Rule-4 paths); scene class derived
+ optional validated assertion (ADR-0011 decision 8); **G3** held — one
declarative scene-class → relevance map (`performance/scene_relevance.py`),
zero per-metric class branches; target-plane sample distance metric
registered; detection range path-aware for up/level (down-looking swap is
owner-gated: CU-236). CU-096 residue re-audited per G4 → refreshed
deferral, gating stage Phase 5 (`RADIANT_Geometry.md` §4.3). Discovered
and fixed in-phase: CU-234, a pre-existing 1e6 unit slip that had zeroed
turbulence out of the MTF-product path since 2026-04-18 (Rule-4 violation
up to 0.88 absolute; caught by the new phase's dual-path tripwire).
Zero golden drift; full suite green.

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

### Phase 4 — GUI (Category D) — COMPLETE 2026-07-28

Exit state: the schematic composes by the stage-derived `los_direction` —
up-looking (sensor = lower endpoint, on the ground plane for a ground
observer, LOS ascending) and level (both endpoints at one abstract height)
join the unchanged down-looking layout (byte-identical render parity proven
against pre-Phase-4 `main`). Angle catalog extended with θ_o (obtuse-capable)
and ζ_low — each stage-backed arc swept to its **own** ray, since η/θ_o/ζ_low
are read at different triangle vertices; ζ_low's stage truth is θ_o for
down/level and **π − η** for up (the plan's earlier π − θ_o shorthand was a
flat-Earth slip, ~2° off at LEO altitudes) — plus the level-arm Δh sag pill
from the core horizon-guard classifier. Angle-truth consistency tests
parametrize over the new scene classes (ground→air, ground→space, LEO→GEO,
air→air level + down-looking) at the existing 1e-9 rad tolerance. Mode labels
re-worded direction-general (V1 lower-endpoint zenith, V2 off-boresight, V4
signed elevation). Scene-class steering shipped: the derived-class chip + the
`geometry.scene_class` assertion as the mission-type entry (mismatch tints
in-context) + the per-class default-off metric preview over the new
`radiant.api.scene_relevance` bridge (G3 held — a re-export, no GUI-side
copy). CU-246…CU-251 filed from in-phase findings. The per-scene-class
`gui_workflow.md` rider ships with each validation scenario in Phase 5, where
the scenarios themselves are built.

- Mode-form labels + new mode wording (manifest auto-delivers structure). ✅
- Schematic viewer: up-looking and horizontal compositions (ground plane
  placed by scene class; LOS ascending; both-elevated layout), angle-catalog
  extension, angle-truth tests extended per class. ✅
- Scene-class steering: surfaces the Gap 85 mission-type concept for
  geometry (class chip driving defaults/relevance); full Gap 85 remains its
  own effort. ✅
- Per the GUI workflow rule: each new scene class ships with a
  `gui_workflow.md` in its validation scenario (→ Phase 5, with the
  scenarios).

### Phase 5 — Validation and scenario close-out (Category D) — COMPLETE 2026-07-28

Exit state: scenario series `scenarios/10_direction_general/` delivers one
validation scenario per priority cell — 10.1 ground-to-air MWIR detection
(E2), 10.2 air-to-air level IRST (E5), 10.3 ground-to-space SST visible
(E3), 10.4 LEO→GEO exo — each with the full walkthrough / gaps /
gui_workflow trio, units on every output, regime discussion, committed
figures + manifests, a module-level factory, and a registered GUI baseline
(38/38 scenarios pass the reload gate; 4/4 open in the real GUI headless).
**Rule-4 consistency stayed silent on every new class** (10.1 measured the
residual at 26× margin across its sweep; 10.3 at 5× with turbulence).
**Cross-model anchors:** 10.1 vs the K-ladder (τ +4.3 % at K6 45°, +17.3 %
vertical — the known simple-model MWIR excess), 10.2 vs the L-grid 10 km row
(band-saturation shortfall quantified), 10.4 vs exact vacuum/geometry
identities (bitwise); **the ground-to-space MODTRAN comparison is deferred
pending the owner-run batch 2** (SST ladder + twilight/refraction pair) —
10.3 substitutes a vacuum identity and a published-extinction anchor, and
that anchor **root-caused CU-253**, a results-affecting VIS Rayleigh
coefficient defect (~8× OD inflation) now owner-visible in the backlog.
**G4 carried duty discharged:** the CU-096 partial-fixture fallbacks are
retired (Performance consumes only GeometryStage-published geometry;
Platform keeps the drift-proof nadir slant = altitude proxy;
`test_geometry_required_contract.py` pins it; §4.3 records it). The
validation wave minted CU-253…CU-269 and Gaps 113–115 — the direction-general
machinery is sound (geometry, guards, relevance, kinematics doors, GUI all
verified), while the findings concentrate in the simple model's VIS fidelity
and the intensity-door solar coupling, exactly what a validation phase
exists to surface. All existing golden baselines unchanged.

- **Carried duty (G4, from Phase 3 close):** retire or re-defer the CU-096
  fallbacks. ✅ Retired.
- One golden scenario per newly-opened cell (minimum: ground-to-air MWIR
  detection, ground-to-space SST visible, air-to-air level IRST, LEO→GEO
  exo), each with walkthrough / units / regime discussion / gui_workflow. ✅
- Full regression: existing golden baselines unchanged ✅; Rule-4 green on
  the new classes ✅; cross-model simple-vs-MODTRAN per class ✅ where batch-1
  anchors exist (K/L); SST deferred to batch 2 (recorded above).

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

### 8.3 Ratification record (owner, 2026-07-26)

**§8.1:** all eight items ratified as written.

**§8.2 answers:**

1. **Near-horizontal shoulder** — compute with a Rule-17 `UserWarning` in
   the band between the hard ±0.5° guard and ≈±2° of horizontal
   (warning quantifies the refraction-excluded caveat); long-range
   air-to-air stays usable at first delivery.
2. **MODTRAN batch** — the owner runs MODTRAN. The needed decks are
   **appended to `docs/plans/modtran_run_matrix.csv`** (first batch scope:
   ground-to-air up-looking partial-column ladder + constant-altitude
   horizontal set, with the CU-065 uplooking Card-3 ANGLE convention check
   folded in; SST full-column ladder is batch 2). All atmospheric
   documentation (`RADIANT_Atmosphere.md` and companions) is updated in
   Rule-20 lock-step at every phase — owner-emphasized.
3. **Sky-background gating** — band-split: MWIR/LWIR sky backgrounds
   supported at first delivery; VIS/NIR sky computes but carries a
   "provisional — single-scatter underestimates daytime sky" `UserWarning`
   until MODTRAN-anchored.
4. **Gap 111 input shape** — both doors, provenance-resolved: direct
   LOS-rate entry and a target-velocity-vector mode deriving it, with the
   V0–V4 agreement-check pattern on disagreement.

**Scene-class priority (owner-ordered):** ground-to-air → air-to-air →
up-looking space-to-space (LEO→GEO) → ground-to-space (SST). Consequences:
Phase 2 library work targets the first two; the Phase 1 LEO→GEO quick win
ships on its own; the Gap 110 turbulence upgrade (SST-critical) may trail
within Phase 3.

**Kickoff:** deferred to a dedicated session (owner, 2026-07-26). Phase 0
is the first action there; nothing beyond this ratification record was
executed in the auditing session.

**Addendum (owner, 2026-07-26, Phase 0 close) — horizon-guard
discriminator (Use-Case Matrix open questions 8 and 10):** the
near-horizontal guard keys on the ray's **tangent-point topology**, not on
$|\theta_o - \pi/2|$ alone. Endpoint-minimum paths (up/down slants grazing
the horizon at their lower endpoint) keep the ratified angular bands at the
lower endpoint (±0.5° raise, ≈±2° warn shoulder). Interior-tangent paths
(level / near-level, incl. every constant-altitude arm) guard instead on
the tangent-height depression $\Delta h = (R_E + h_{low})(1 -
\sin\theta_{low}) \approx L^2/8R_E$: below ~100 m compute clean; ~100 m–2 km
compute with the quantified refraction `UserWarning`; above ~2 km raise
(limb-like transit). Thresholds provisional; calibrated in Phase 2 by a
MODTRAN refraction on/off deck pair (batch 2, alongside the SST ladder).
The same interior-tangent test is the B2/B4 background discriminator
(continuation tangent deeper than the raise threshold → B4 raise). This
refines ADR-0011 decision 6 (the angular bands there apply to the
endpoint-minimum topology); it lands in `core/viewing_triangle.py` with the
extended domain in Phase 1, with Rule-20 doc lock-step in that PR.
Rationale: a pure angular test over-rejects benign short horizontal paths
(8 km towers, $\Delta h$ = 1.3 m, θ_o = 90.04°) and a blanket equal-altitude
exemption both under-rejects long transits (500 km at 5 km altitude,
$\Delta h$ ≈ 4.9 km) and makes behavior discontinuous between equal and
almost-equal altitudes.

**Addendum (owner, 2026-07-26, Phase 1 close) — θ_o domain closed at π.**
ADR-0011 decision 2 writes the extended domain as "$[0, \pi)$"; the owner
confirms this was a notation slip. The canonical domain is the **closed**
interval $[0, \pi]$: $\theta_o = \pi$ is the vertical up-looking case
(ground sensor with the target at zenith; LEO sensor directly beneath a
GEO target — the K-ladder and SST geometries) and is attained exactly.
Implemented as closed in Phase 1 (`core/viewing_triangle.py`,
`core/los_geometry.py`, `geometry.path_zenith_rad` bounds).

**Addendum (owner, 2026-07-26) — batch 1 delivered; horizontal set
re-scoped to a 5×5 grid.** The K-block (K1–K7) and the horizontal set were
run and staged to `modtran/real_runs/` (manifest regenerated). The original
L1–L4 decks were run with Card-3 RANGE = 0.000 (the builder's hardcoded
value) and came back without path length — confirming the
`phase2_range_wiring` caveat. The owner re-scoped the horizontal family to
a **5×5 grid** — altitude {0, 3, 5, 10, 15} km × range {5, 10, 25, 50,
100} km, rows L1–L25, new `hrange_km` column in the run matrix — ran all
25 with HRANGE set correctly, and delivered the tape7s. Owner snapshot
archived at `docs/archive/modtran_run_matrix_update_2026-07.csv`; the
master matrix carries the merged content. Phase 2's horizontal-arm truth
anchors are therefore already in hand.
