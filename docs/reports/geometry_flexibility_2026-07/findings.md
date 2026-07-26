# Geometry Flexibility Audit — Findings

**Status:** Complete (2026-07-26). Immutable point-in-time record (Rule 24).
**Charter:** `charter.md`. **Remediation:** `docs/plans/Geometry_Flexibility_Plan.md` (Draft).
**Code state audited:** `main` @ d956fef (2026-07-26).

---

## 1. Executive Summary

The owner's suspicion is confirmed, and is sharper than "down-looking
sensors only": **every viewing-geometry entry point in RADIANT requires the
sensor to be strictly above the target** (`h_sensor > h_target`) **with the
LOS zenith at the target below the horizon** ($\theta_o \in [0, \pi/2)$).
This is a deliberate v1 policy (owner ruling 2026-07-11, recorded in
`RADIANT_Geometry.md` §4 and enforced in `core/viewing_triangle.py`), not an
accident — but it now gates every mission class the owner wants: ground-to-air,
air-to-air, ground-to-space, and even **up-looking space-to-space** (a LEO
sensor viewing a GEO target is rejected despite the path being pure vacuum).

Three structural facts shape the remediation:

1. **The atmosphere backends are already more general than the geometry
   front door.** `AtmosphericGeometry` documents uplooking support, the
   MODTRAN deck builder implements the uplooking Card-3 ANGLE convention and
   the ITYPE=1 horizontal-path type, and `SimpleAtmosphere` integrates its
   optical-depth column symmetrically between the two endpoint altitudes.
   The hard blockage is concentrated in `core/viewing_triangle.py`,
   `core/los_geometry.py` (`LineOfSightGeometry`), and `geometry/modes.py`.

2. **The radiometric *topology* is down-looking even where the *transmittance*
   is not.** The eight-field `AtmosphericQuantities` contract, the §6.1
   assembly equation, and the four background descriptors all encode
   "ground behind the target, sky above it": there is no sky-radiance-along-LOS
   product, no up-path radiance slot, no horizontal path, no earthlimb, and
   the sun is hard-bounded above the horizon. Fixing the LOS math without
   fixing the path/background topology would produce geometrically valid but
   radiometrically wrong up-looking scenes — the background/contrast term is
   the whole game for up-looking detection.

3. **Downstream metrics and the GUI assume a ground scene** — GSD/NIIRS/ground
   range/access rate are ground-projection concepts, smear kinematics is
   platform-ground-speed-only, and the 2D schematic viewer composes a
   sensor-above-ground-grid scene. These need conditioning by scene class,
   not wholesale replacement (the Gap 96 metric-selection machinery is the
   right hook).

Findings GF-1 through GF-18 below; dispositions in §5. Five new gaps filed
(107–111). No code was changed by this audit.

---

## 2. Method

Inline single-agent read of the geometry core, geometry stage, all six
atmosphere backends + assembly + protocol, platform/performance consumers,
and the GUI geometry surfaces; cross-checked against ADR-0006,
`RADIANT_Geometry.md`, `RADIANT_Use_Case_Matrix.md`, `RADIANT_Atmosphere.md`,
and the gap registry. Every claim below carries a file anchor.

---

## 3. Findings — Codebase

### 3.1 Geometry core and stage

**GF-1 — Hard down-looking gate (root finding).**
`core/viewing_triangle.py::_validate_altitudes` raises `ParameterBoundsError`
for `h_sensor <= h_target` ("v1 has no uplooking geometry"); every V1–V4 mode
conversion in `geometry/modes.py::resolve_viewing` routes through it. The
collocated case `h_sensor == h_target` survives only as a degenerate
"no viewing triangle" carve-out (triangle-derived fields `None`), which means
**equal-altitude horizontal paths are not merely unsupported — they are
represented as geometry-free scenes**. Even the pure-vacuum up-looking
space-to-space case is rejected here, before the atmosphere is ever consulted.
→ Gap 107.

**GF-2 — Zenith domain excludes horizontal and above-horizon LOS.**
$\theta_o \in [0, \pi/2)$ is enforced independently in
`viewing_triangle._validate_theta_o`, `LineOfSightGeometry.__post_init__`
(`core/los_geometry.py`), and `AtmosphericGeometry` (ceiling 89.5°,
`atmosphere/protocol.py::ZENITH_CEILING_RAD`). An up-looking scene needs
$\theta_o > \pi/2$ (LOS *descending* at the target toward a lower sensor);
a level air-to-air scene needs $\theta_o \approx \pi/2$. No refraction model
exists to make near-horizon/limb paths trustworthy (self-documented in the
`LineOfSightGeometry.theta_o` validator). → Gap 107 / Gap 109.

**GF-3 — `LineOfSightGeometry` does not carry the sensor endpoint.**
The Source→Atmosphere contract carries only `h_tgt`, `h_atm_top`, and angles;
`slant_range_atm` and `path_airmass_up` integrate **target → top-of-atmosphere**
regardless of where the sensor is, and backends side-load
`geometry.sensor_altitude_m` from params (documented v1 shortcut,
`simple.py` evaluate: "the LineOfSightGeometry does not carry h_sensor in
v1"). A direction-general path needs both endpoints and a signed direction on
the contract object itself. → Gap 107 (Phase 1 of the plan).

**GF-4 — Azimuth exists only as sun-relative $\Delta\phi$.**
No absolute sensor/target azimuth, no 3D LOS vector. Adequate for the current
axially-symmetric path model; insufficient for two-point geodetic entry
(Gap 83) and for coupling target aspect to LOS direction in air-to-air
scenes. → folded into Gap 107 planning (representation choice), no separate gap.

**GF-5 — `incidence_angle_rad` ≡ $\theta_o$ presumes a ground-plane target.**
Published by GeometryStage and consumed by GSD ($\cos$-projection). For an
airborne/space target "incidence on the local vertical" is not the quantity
of interest (the target-plane projection depends on target body orientation,
which lives in `geometry.target.shape_*`). Down-stream conditioning issue,
not a blocker. → Planned (plan Phase 3).

### 3.2 Atmosphere

**GF-6 — Aspirational/actual mismatch on sensor location.**
`RADIANT_Use_Case_Matrix.md` fixes the sensor to `space` in v1, yet nothing
validates `h_sensor ≥ h_atm_top`, and `SimpleAtmosphere` integrates
$OD$ between the endpoint altitudes — an **airborne down-looking sensor
already works numerically** through the simple model (and through MODTRAN
via H1/H2). The matrix's scope statement and the code's behavior disagree;
Rule 20 wants them reconciled whichever way the owner rules. → Planned
(plan Phase 0 scope decision; doc update in lock-step).

**GF-7 — Two-leg topology is down-looking by construction.**
`AtmosphericQuantities` fixes the product set: $\tau_{up}$ (target→sensor),
$\tau_{full,up}$ (ground→sensor, feeds `GroundBackground` assembly),
$\tau_{sun}$ (TOA→target), upward $L_{path}$ terms only. Missing for
generality: sensor→target *up-path* radiance (dominant clutter for a low
sensor viewing a high target through sunlit air), a horizontal
constant-altitude arm, and any background-continuation column other than
"ground below". → Gap 109.

**GF-8 — $E_{sky}$ is target-side and dome-integrated only.**
The downwelling sky the *target* sees (correct for reflective loading) is the
only sky product; "the sensor altitude does not enter" (`simple.py`
docstring, deliberate CU-155 design). There is no sky *radiance along a
specific LOS* — which is what an up-looking background needs — and the
exo-target branch already documents the Earthshine conflation
(`exo_target.py`, "right order of magnitude, wrong spectrum"). → Gap 108.

**GF-9 — Sun hard-bounded above the horizon.**
`AtmosphericGeometry.__post_init__` raises for $\theta_s \geq \pi/2$; the
schema bounds `geometry.solar_zenith_rad` at 1.5707. The day/night toggle
(Gap 59) is scene-global. The operationally central SDA/boost case —
**sunlit high-altitude target over a dark ground** — and all twilight scenes
are unexpressible. Illumination needs a per-altitude shadow-height test, not
a global bound. → Gap 109.

**GF-10 — MODTRAN capability stranded behind the front door.**
The deck builder already implements: uplooking ANGLE convention (H1 below H2
→ ANGLE = zenith, `modtran.py` Card-3 comments), ITYPE=1 horizontal path,
ITYPE=3 slant-to-space. None is reachable: geometry rejects the scenes
upstream. The interpolated library refuses zenith ≥ 88.8° (sec-space
mapping), and every shipped ladder family is down-looking. Up-looking
library families must be *generated* (the 17-deck batch pattern exists),
not just wired. → Gap 109.

**GF-11 — Simple-model calibrations are validated down/vertical only.**
The CU-161 water/gas fits and CU-155 $E_{sky}$ fits anchor against vertical
and up-looking-from-ground H-runs; the plane-parallel airmass with spherical
correction is a *column-traversal* model. A horizontal path at altitude
(constant density, no column traversal) is a different integral — analytic
and easy (Beer-Lambert at local density) but currently absent, and the
single-scatter $L_{path}$/graybody $L_{atm,down}$ fits do not transfer to
limb-like geometry. → Gap 109.

**GF-12 — Turbulence is a direction/path-blind stub.**
`atmosphere/turbulence.py` self-documents: $r_0$ is a direct user input; no
$C_n^2$ profile, no path-weighted integration, no zenith scaling; and
`RADIANT_Scope_Decisions.md` rejects turbulence for space observers
entirely. For ground-based up-looking (SST — the canonical Gap 107 payoff
scene) turbulence is the dominant spatial degradation. → Gap 110.

### 3.3 Downstream consumers

**GF-13 — Ground-projection metrics need scene-class conditioning.**
GSD (`performance/gsd.py`, incidence $< \pi/2$ enforced), ground range,
swath/access rate, and NIIRS/GIQE (ground-imaging by definition; see also
Gap 100) are meaningless or differently-defined for air/space targets. The
Gap 96 metric-selection machinery is the natural gate; what is missing is a
scene-class-driven default relevance map (relates to deferred Gap 85
mission-type selector). → Planned (plan Phase 3).

**GF-14 — Kinematics is ground-track-only.**
One scalar `geometry.ground_speed_m_s` (or V6 orbit derivation); smear =
platform velocity over range (`platform/smear.py::smear_width_m`). No target
velocity, no relative LOS angular rate — the driver for air-to-air and SDA
integration-time trades. → Gap 111.

**GF-15 — Detection-range solver assumes constant extinction along range.**
`performance/stage.py::_compute_detection_range_metric` derives
$\alpha = -\ln(\bar\tau)/R$ from the band-mean in-band $\tau$ and bisects on
inverse-square × Beer-Lambert. Self-documented as first-order; error grows
for strongly slanted/vertical paths where $\alpha$ varies orders of
magnitude along the LOS (exactly the ground-to-space case). → Planned
(plan Phase 3; no separate gap — the code already flags the deferral).

### 3.4 GUI

**GF-16 — Mode form auto-follows the manifest (good bones).**
The Geometry screen is a view over `geometry/mode_manifest.py` via the
`radiant.api.geometry_modes` bridge (CU-120): new modes/parameters propagate
without GUI transcription. Only the human labels (`gui/geometry_modes.py::
MODE_LABELS`, import-checked complete) and mode wording ("off-nadir",
"ground range") need extension when direction-general modes land. → Planned
(plan Phase 4, small).

**GF-17 — Schematic viewer composes a down-looking scene.**
`gui/viewer/schematic_view.py` draws a ground grid/axes with the sensor
glyph above and sensor→ground drop vectors; the angle catalog (η, $\theta_s$,
$\Delta\phi$, phase) carries down-looking semantics. Up-looking and
horizontal compositions (sensor at/near the ground plane, LOS ascending;
both glyphs elevated) are new layout work, though the not-to-scale
architecture (fixed abstract display distances, owner-endorsed) transfers
directly. The angle-truth consistency test harness also transfers. → Planned
(plan Phase 4).

**GF-18 — No scenario-class steering.**
With one scene class, "which parameters matter" was tractable; with nine
observer×target classes it is not. The deferred Gap 85 mission-type selector
becomes load-bearing: scene class should drive mode availability, background
defaults, metric relevance, and viewer composition. → Planned (plan Phases
0/4 tie-in to Gap 85; Gap 85 status unchanged by this audit).

---

## 4. What already works (assets the plan builds on)

- **Spherical-Earth triangle machinery** is clean, tested, and symmetric in
  structure — the down-looking restriction is validation policy, ~10 lines,
  not baked into the math (the law-of-cosines/sines forms work for either
  endpoint ordering with careful angle bookkeeping).
- **Mode-manifest architecture** (provenance-driven detection, agreement
  checks, GUI bridge) extends to new modes without structural change.
- **MODTRAN deck builder** already speaks uplooking/horizontal (GF-10);
  `Tape7Reader` and the interpolated-library machinery are
  geometry-agnostic given new run families.
- **Exo/exo-target backends** mean the space-to-space up-looking case needs
  *only* the geometry gate lifted (quick win — plan Phase 1 exit criterion).
- **Gap 96 metric selection + Gap 91 frames + descriptor system** give the
  conditioning hooks Phase 3 needs.
- **Airborne down-looking sensors** largely work today modulo the scope
  statement (GF-6) — air-to-ground is the cheapest class to ratify.

---

## 5. Disposition Table (Rule 28)

| Finding | Disposition |
|---------|-------------|
| GF-1 | **Planned** — Gap 107; plan Phase 1 |
| GF-2 | **Planned** — Gap 107 (domain), Gap 109 (near-horizon physics); refraction explicitly deferred with a validity guard (plan Phase 2) |
| GF-3 | **Planned** — Gap 107; plan Phase 1 (LOS contract change, ADR required) |
| GF-4 | **Planned** — folded into plan Phase 0 representation decision (with Gap 83) |
| GF-5 | **Planned** — plan Phase 3 (metric conditioning) |
| GF-6 | **Planned** — plan Phase 0 scope ratification + Rule 20 doc reconciliation |
| GF-7 | **Planned** — Gap 109; plan Phase 2 |
| GF-8 | **Planned** — Gap 108; plan Phase 2 |
| GF-9 | **Planned** — Gap 109; plan Phase 2 (shadow-height illumination) |
| GF-10 | **Planned** — Gap 109; plan Phases 2/5 (library generation is owner-run MODTRAN work) |
| GF-11 | **Planned** — Gap 109; plan Phase 2 (horizontal arm analytic; limb radiance **Declined for v1.x** — earthlimb stays a v2 exclusion per Use-Case Matrix, re-scoped only if a limb-viewing mission materializes) |
| GF-12 | **Planned** — Gap 110; plan Phase 3 |
| GF-13 | **Planned** — plan Phase 3 (scene-class relevance map over Gap 96 machinery) |
| GF-14 | **Planned** — Gap 111 (OPEN; scheduled behind Phase 1–2 landings) |
| GF-15 | **Planned** — plan Phase 3 (path-aware extinction in the solver) |
| GF-16 | **Planned** — plan Phase 4 |
| GF-17 | **Planned** — plan Phase 4 |
| GF-18 | **Planned** — plan Phases 0/4; Gap 85 remains DEFERRED but is named a dependency of full GUI delivery |

No findings were CU'd: none is a latent *defect* in shipped behavior — every
item is a scoped v1 exclusion or a capability gap, and the capability
registry (gaps.md) is their single home per Rule 25. One sub-item Declined
(limb radiance, GF-11) with rationale above.
