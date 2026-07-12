# ADR-0006: Geometry Is Stage 0 of the Chain

**Date:** 2026-07-12
**Status:** Accepted

## Context

Scene geometry — where the sensor, target, and sun are — is consumed by nearly every
stage but owned by none:

- The `geometry.*` parameter namespace (7 ParameterDefs) is defined in
  `atmosphere/_schema.py` by historical accident and consumed by atmosphere, platform,
  performance, the source inferrer, and MODTRAN deck rendering.
- `source.target.range_m` (slant range) lives in source's schema; the range it names
  can silently disagree with the range implied by `geometry.sensor_altitude_m` +
  `geometry.path_zenith_rad` — regime classification and detection range use one,
  GSD/GIQE use the other (CU-093).
- `platform.h_sensor` duplicates `geometry.sensor_altitude_m` with no consistency
  link (CU-090).
- `core/geometry.py`'s `ObserverGeometry`/`TargetGeometry`/`SceneGeometry` dataclasses
  have zero consumers — a parallel flat-Earth model beside the spherical-Earth
  functions the runtime actually uses (CU-094).
- Three geometry input paths are half-built with no front door: `theta_o_from_eta`
  (deliberately parked by CU-005 "behind the SensorDescriptor ADR"),
  `core/solar_geometry.py` (tested, zero runtime consumers), `core/orbit.py`
  (reachable only via an opt-in API helper).

The 2026-07-12 GUI mockup review made the user-facing cost concrete: a screen-per-stage
GUI that opens at Source asks the user to define a target's radiance before saying
where anything is, and has no screen where "where is everything?" lives.
`RADIANT_Use_Case_Matrix.md` §4.4 had already stubbed a `SensorDescriptor` ("exact
structure deferred to its own design review") for part of this problem. This ADR is
that design review.

## Decision

1. **A new `GeometryStage` becomes stage 0** of the signal chain
   (`geometry → source → atmosphere → optics → platform → spectral_integration →
   detector → readout → performance`). It is a pure Stage (Rule 6) that emits no
   radiometric frames — it validates scene geometry, resolves one **input mode**
   into the canonical internal representation, derives all geometric quantities
   exactly once (slant range, ground range, incidence angle, `LineOfSightGeometry`),
   and publishes them via `stage_outputs["geometry"]`. Downstream stages consume
   published values and never re-derive.

2. **The `geometry.*` namespace moves to `src/radiant/geometry/_schema.py`** (names
   unchanged). Geometry-owned parameters in other namespaces are renamed into it
   using the existing `deprecated_aliases` machinery (warn + redirect):
   `source.target.range_m` → `geometry.target_range_m`; `platform.h_sensor` folds
   into `geometry.sensor_altitude_m` after the CU-090 call-site audit.

3. **Input modes are the specification model** (full taxonomy:
   `docs/plans/Geometry_Stage_Plan.md` §3, normative home after execution:
   `docs/architecture/RADIANT_Geometry.md`). v1 ships: direct range (V0),
   altitude+path-zenith (V1, reference mode), altitude+off-nadir η (V2 — wires the
   reserved `theta_o_from_eta`, the CU-005 follow-on), altitude+ground-range (V3),
   altitude+elevation (V4), circular orbit (V6 — wires `core/orbit.py`), and solar
   modes off/direct/elevation/site+time (S0–S3, S3 wiring `core/solar_geometry.py`).
   Deferred with gap entries: two-point geodetic (V5 → Gap 83), TLE/elements,
   trajectory series, solar ephemeris (V7/V8/S4 → Gap 84). Mode resolution is
   provenance-driven: exactly one complete mode per family; redundant values must
   agree within 1 % or the stage raises an actionable over-specification error;
   derived values carry `Provenance.DERIVED`.

4. **The flat-Earth dataclasses are deleted** (`ObserverGeometry`, `TargetGeometry`,
   `SceneGeometry`). The spherical-Earth module functions are the one canonical
   model (Rule 27). Platform/target attitude returns only when a consumer exists.

5. **`SensorDescriptor` (Use_Case_Matrix §4.4) is superseded.** Physical sensor
   altitude lives in `geometry.*`; no separate descriptor object is created.

6. **Zero-drift requirement**: the restructure is re-homing and wiring, not physics.
   Same formulas, same defaults; golden baselines must be byte-identical through
   Phases 1–2. The only new user-visible behavior is the over-specification error
   (Phase 3, CHANGELOG'd).

## Rationale

Geometry is upstream of everything that consumes it — regime classification,
atmospheric path length, smear, GSD, detection range. Making it a stage puts the
dependency graph, the documentation, and the GUI workflow in the same order, which is
RADIANT's primary goal (a model anyone can follow). The stage protocol already
accommodates non-radiometric stages (SourceStage publishes descriptors and LOS
today), so no protocol change is needed.

### Alternatives Considered

| Option | Pros | Cons |
|--------|------|------|
| **A. GeometryStage (chosen)** | One owner, one derivation, one validation point; chain order = mental model = GUI order; fits the existing Stage protocol; gives the three orphaned input paths a front door | New package; ~13 docs touched; parameter renames (mitigated by aliases) |
| B. Status quo + consistency groups only | Minimal churn; fixes CU-090/CU-093 point-wise | Namespace stays owned by atmosphere; no home for input modes; GUI still has no geometry screen backed by the architecture; derivations stay scattered |
| C. Pre-chain resolution in the API layer (like atmosphere-model injection) | No new stage; keeps chain at 8 stages | Geometry is *parameters + derivation*, not file I/O — hiding it in the API layer makes it invisible to `result.inspect()`, stage docs, and the consistency machinery; contradicts "every tuneable quantity is a parameter with a stage owner" (Rule 12) |
| D. `SensorDescriptor` object per Use_Case_Matrix §4.4 | Already sketched | Solves only the h_sensor slice; adds a second specification mechanism beside `ParameterSet` instead of using the parameter system's own consistency/provenance machinery |

## Consequences

- **Positive:** CU-090, CU-093, CU-094, and CU-005's residual all close structurally;
  regime classification, detection range, and GSD are guaranteed range-consistent;
  the GUI's first screen has a 1:1 architectural counterpart; sun-synchronous and
  orbital trade studies become one-line inputs (S3/V6 wired).
- **Negative:** 9-stage chain (docs, tests, and muscle memory updated); two
  deprecation cycles to manage (`source.target.range_m`, `platform.h_sensor`);
  ~48 test/scenario files migrate to canonical names in Phase 3.
- **Neutral:** `LineOfSightGeometry` is unchanged as the Source→Atmosphere data
  contract (ADR-0002); it is now built by GeometryStage instead of the source
  inferrer. Execution plan and phase gates: `docs/plans/Geometry_Stage_Plan.md`.
