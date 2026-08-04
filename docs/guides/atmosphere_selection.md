# Atmosphere Selection Guide

*Persona: Sarah (systems engineer), Raj (mission planner), Marcus (SDA analyst)*

Which atmosphere model to run, which bundled MODTRAN family serves your scene, and what
every warning and refusal you can meet actually means.

This guide is the **operator's** document. The physics is
[`docs/theory/atmosphere_models.md`](../theory/atmosphere_models.md); the measured accuracy
is [`docs/validation/atmosphere_modtran_parity.md`](../validation/atmosphere_modtran_parity.md);
the architecture contract is
[`docs/architecture/RADIANT_Atmosphere.md`](../architecture/RADIANT_Atmosphere.md). Nothing
is re-derived here — every number below cites the section, test, or catalogue entry that
holds it.

---

## 1. The decision in one page

`atmosphere.model` takes five values: `simple`, `interpolated`, `tabulated`, `modtran`,
`exo`. For nearly every scene the choice is between the first two.

| Scene class | Reach for | Why |
|---|---|---|
| Down-looking, ground target, sensor 3–100 km or GEO, nadir | `interpolated` | `midlat_summer_sensor_ladder` covers it; the answer is measured MODTRAN |
| Down-looking, ground target, off-nadir to 60° | `interpolated` | `us_standard_zenith_fan` (sensor 100 km) or `midlat_summer_upwelling_offnadir` (sensor 10 km / 100 km / GEO) |
| Down-looking, elevated target (boost, aircraft, balloon) | `interpolated` | `midlat_summer_ladders` (0–29 km, nadir) or `midlat_summer_boost_offnadir` (0–100 km, ζ 0–60°) |
| Up-looking from the ground at a target 0–20 km | `interpolated` | `midlat_summer_uplooking_zenith_fan` (ζ 0–60°) — but read §5 on the hybrid split |
| Up-looking from the ground through the whole column to space | `interpolated`, explicit dir | `midlat_summer_sst_column_fan`, ζ 0–78.5° |
| Up-looking from a **900 m site** through the whole column to space | `interpolated`, explicit dir | `midlat_summer_sst_column_fan_site900m`, ζ 0–78.5° |
| Up-looking from any **other elevated site** | `simple` | Only 0 m and 900 m lower endpoints are rendered; there is no sensor-altitude axis to interpolate a third site from (§4) |
| Sensor below 3 km looking down (ground test, tower, low UAV) | `simple` | Below every down-looking family's rendered floor (§4) |
| Level / horizontal path (air-to-air, ground-to-ground) | `simple` | No bundled family is rendered for a level line of sight, and one cannot be interpolated from a column ladder (theory §3.7) |
| Grazing, ζ ≥ 88.8° | `simple` only, and read §6 | The interpolation coordinate $\sec\zeta$ diverges and is refused there (parity §3 item 6) |
| Long-range MWIR horizontal (> ~25 km arm) | Neither — see §6 | The analytic arm collapses against a band model; a MODTRAN backend is the remedy (parity §2.6) |
| Both endpoints at or above 100 km MSL | any (`exo` is explicit) | The path is wholly vacuum; no backend is consulted at all |
| A hand-built run matrix of your own | `interpolated` with `atmosphere.interpolated_data_dir` | The bundled catalogue is a convenience, not a constraint |
| A single tape7 or a stored column, geometry fixed | `tabulated` / `modtran` | Geometry-agnostic files; they do not respond to the scene at all |

**`simple` is the always-works baseline.** It is the only backend that can serve an
arbitrary path topology — down-looking, up-looking, level, grazing, twilight — because the
segment evaluators are built on its species model (theory §1). If you are unsure, run
`simple`: it will never refuse a legal geometry.

**`interpolated` is measured MODTRAN data, where a family covers the scene.** It does not
extrapolate. Outside its nodes it refuses, by design (theory §3.2).

### What "measured" actually buys

The stakes are band- and class-dependent. All ratios are model ÷ MODTRAN unless stated.

| Quantity | `simple` accuracy | `interpolated` accuracy |
|---|---|---|
| Transmittance, LWIR 8–12 µm, columns ≥ 10 km | within 2 % (parity §2.6); enforced band 0.95–1.16 | exact on a node (**bit-identical** to the stored column, parity §2.9) |
| Transmittance, MWIR 3–5 µm | enforced band 0.99–1.35; systematically transparent on columns < 5 km (K1 0.755 vs 0.581 measured) | exact on a node |
| Transmittance, between zenith nodes | n/a | −0.10 % band-mean τ on the real B-fan 45° holdout, in $\sec\zeta$ space (parity §2.9) |
| Thermal path radiance, LWIR | 0.52–1.19 across the 14-anchor set; RMS \|ln r\| = 0.2611 (parity §2.1) | exact on a node |
| Thermal path radiance, MWIR | 0.36–1.22 across the same set; the 25–40 % up-looking deficit is the region-flat spectral shape (parity §3 item 1) | exact on a node |
| Daytime VIS/NIR sky radiance | **under-reads by roughly 2×** near the horizon (0.55–0.59 at ζ = 85–89.5°, 0.76 at ζ = 0; parity §2.4) | measured, but see the profile caveat below |
| Long-range MWIR horizontal arm, 3 km altitude | 1.09 at 5 km range falling to **0.01** at 100 km (parity §2.6) | no horizontal family is built |

Read that table as: **in the thermal bands the parametric model is already within tens of
percent, and `interpolated` buys you exactness on a node. In the daytime VIS/NIR, `simple`
is off by a factor of two and `interpolated` is the only quantitative answer.**

Three costs come with `interpolated` and none of them is hidden:

1. **Coverage is a closed set.** Ten families, listed in §3. Off the hull, the run is
   refused (§5).
2. **The profile comes with the family.** Nine of the ten bundled families are rendered on
   `midlat_summer`; one (`us_standard_zenith_fan`) on `us_standard`. Adopting a family
   whose profile differs from an explicitly-set `atmosphere.standard_atmosphere` changes
   the atmosphere of your run — `Sensor.atmosphere_profile_change_warning()` renders that
   caveat and the GUI picker shows it beside the row.
3. **The solar geometry comes with the family too.** Every bundled family is rendered at
   solar zenith 30° and relative azimuth 0°. A scene with a different sun gets the family's
   sun, with a warning (§5, CU-167).

---

## 2. Two ways to choose

### In the GUI

**Atmosphere → Model → `interpolated`** reveals the *Library family* picker
(`AtmosphereFamilyPicker`), which replaces the old free-text `atmosphere.interpolation_axes`
row. It shows:

- one row per bundled family, labelled with name and rendered profile, with the family's
  full coverage line (units always explicit) under the box;
- the row the scene calls for, marked `(recommended for this scene)`;
- when the configured family does not cover the scene, that recommended row **pre-selected
  as a proposal** with an explicit **Use this family** button. A proposal is never applied
  behind your back, because adopting a family can change the profile;
- the profile-mismatch caveat whenever it applies;
- `Custom axes… (advanced)` as the last entry — the free-text escape hatch for a run matrix
  you built yourself.

When no bundled family serves the scene, switching the model produces **exactly one**
Messages-rail advisory naming the single closest miss — not a sequence of refusals, one per
gate. The scene stays on whatever it was.

### In YAML and scripting

```python fragment
from radiant.api import Sensor

sensor = Sensor.load("my_scenario.yaml")
suggestion = sensor.atmosphere_family_suggestion()

if suggestion.serves:
    family = suggestion.family
    sensor.set("atmosphere.model", "interpolated")
    sensor.set("atmosphere.interpolation_axes", family.interpolation_axes)
    if family.explicit_dir_only:                      # §3 — needs the directory too
        sensor.set("atmosphere.interpolated_data_dir", family.bundled_dir)
    result = sensor.evaluate()
else:
    print(suggestion.advisory_text)                  # one sentence, units explicit
    print(suggestion.advisory_error().action)        # what to do instead
```

`atmosphere_family_suggestion()` is **pre-validated end to end**: it reproduces, from each
family's own node geometry, every refusal the chain would raise for this line of sight, so
a family it names is one the chain accepts. It recommends only — it writes nothing.

Related API, all recommendation-only and non-mutating:

| Call | Answers |
|---|---|
| `Sensor.atmosphere_family_suggestion()` | the pre-validated family, or the one closest miss |
| `Sensor.suggested_atmosphere_family()` | the same, family only (`None` when uncovered) |
| `Sensor.atmosphere_family_gap(family)` | why *this named* family cannot serve the scene |
| `Sensor.atmosphere_profile_change_warning(family)` | whether adopting it changes the profile |
| `Sensor.validate_atmosphere_coverage()` | raises the config-time coverage refusal (§5 R1/R2) |
| `radiant.api.shipped_atmosphere_families()` | the whole catalogue, in picker order |
| `radiant.api.is_atmosphere_coverage_refusal(exc)` | routes a caught error to an advisory surface rather than a "bad parameter" modal |

In YAML the same choice is two keys (three for an explicit-dir family):

```yaml
atmosphere:
  model: interpolated
  interpolation_axes: sensor_altitude_m,target_altitude_m,path_zenith_rad
  # interpolated_data_dir: <only for an explicit-dir family, or your own runs>
```

Leaving `interpolated_data_dir` empty dispatches on `(los_direction, interpolation_axes)`
to the bundled family that owns that signature.

---

## 3. The family catalogue

Ten bundled families. **Coverage lines are quoted verbatim** from
`radiant/atmosphere/interpolation_coverage.py`, which is the single authority — the loader's
dispatch table, the GUI picker, and the `atmosphere.interpolated_data_dir` schema
description are all derived from it.

### Down-looking (upwelling path radiance)

| Family | Axes to write | Profile | Nodes | Coverage (verbatim) |
|---|---|---|---:|---|
| `us_standard_zenith_fan` | `path_zenith_rad` | `us_standard` | 4 | ground targets only (target altitude fixed at 0 km), sensor at 100 km, LOS zenith 0-60 degrees |
| `midlat_summer_sensor_ladder` | `sensor_altitude_m` | `midlat_summer` | 6 | ground targets only (target altitude fixed at 0 km), sensor 3-100 km plus 40000 km (GEO), nadir only (LOS zenith 0 degrees) |
| `midlat_summer_ladders` | `sensor_altitude_m,target_altitude_m` | `midlat_summer` | 18 | targets 0-29 km, sensor 35 km / 100 km / 40000 km (GEO), nadir only (LOS zenith 0 degrees) |
| `midlat_summer_upwelling_offnadir` | `sensor_altitude_m,path_zenith_rad` | `midlat_summer` | 9 | ground targets only (target altitude fixed at 0 km), sensor 10 km / 100 km / 40000 km (GEO), LOS zenith 0-60 degrees |
| `midlat_summer_boost_offnadir` | `sensor_altitude_m,target_altitude_m,path_zenith_rad` | `midlat_summer` | 36 | targets 0-100 km, sensor 100 km / 40000 km (GEO), LOS zenith 0-60 degrees |
| `midlat_summer_boost_ladder` **(explicit dir)** | `sensor_altitude_m,target_altitude_m` | `midlat_summer` | 24 | targets 0-100 km (12 rungs through the boost band), sensor 100 km / 40000 km (GEO), nadir only (LOS zenith 0 degrees) |

### Up-looking (downwelling path radiance, `L_toward_lower`)

| Family | Axes to write | Profile | Nodes | Coverage (verbatim) |
|---|---|---|---:|---|
| `midlat_summer_uplooking_ladder` | `target_altitude_m` | `midlat_summer` | 6 | ground sensor (0 km) looking up at targets 0-20 km, vertical only (LOS zenith 0 degrees) |
| `midlat_summer_uplooking_zenith_fan` | `target_altitude_m,path_zenith_rad` | `midlat_summer` | 18 | ground sensor (0 km) looking up at targets 0-20 km, LOS zenith 0-60 degrees (sec 1.0-2.0 at the sensor) |
| `midlat_summer_uplooking_sensor_ladder` | `sensor_altitude_m` | `midlat_summer` | 10 | observer 0-100 km looking up the full column to the 100 km atmosphere top, fixed 48.2 degrees LOS zenith (the diffusivity angle) |
| `midlat_summer_sst_column_fan` **(explicit dir)** | `path_zenith_rad` | `midlat_summer` | 6 | ground sensor (0 km) looking up the full column to the 100 km atmosphere top, LOS zenith 0-78.5 degrees (sec 1.0-5.0) |
| `midlat_summer_sst_column_fan_site900m` **(explicit dir)** | `path_zenith_rad` | `midlat_summer` | 5 | elevated-site sensor (0.9 km, i.e. a 900 m mountaintop) looking up the full column to the 100 km atmosphere top, LOS zenith 0-78.5 degrees (sec 1.0-5.0) |

**Direction is not a preference, it is a different product.** An up-looking family stores
its radiance under a different NPZ key (`path_radiance_toward_lower`) and is served through
a different entry point. The two entry points refuse each other's families rather than
reading the wrong quantity (theory §3.1).

**Nodes** above is the family's actual run count, read from its shipped NPZ `geometry`
dicts. Every family is rendered at solar zenith 30°, relative azimuth 0°.

### Why three families are explicit-dir only

`explicit_dir_only = True` means **no axes string can select this family**. Adopting it
requires writing `atmosphere.interpolated_data_dir` (the family's `bundled_dir`) as well as
the axes. The GUI picker does both for you in one compound edit.

- **`midlat_summer_boost_ladder`** — 24 committed MODTRAN runs whose
  `(down, sensor_altitude_m,target_altitude_m)` signature is already owned by
  `midlat_summer_ladders`. Publishing it as a dispatch row would silently re-baseline every
  existing 2-axis result, so it ships by name instead.
- **`midlat_summer_sst_column_fan`** — its `(up, path_zenith_rad)` signature is free, but
  `path_zenith_rad` is the **schema default** for `atmosphere.interpolation_axes`.
  Publishing it would turn today's actionable refusal, for an up-looking scene that never
  touched the axes parameter, into a silent dispatch onto a family whose target altitude is
  fixed at the 100 km atmosphere top. It is a full-column SST anchor and is adopted
  deliberately, by name, never by default.
- **`midlat_summer_sst_column_fan_site900m`** — the same column from a 900 m site, and
  explicit-dir for both of the above reasons at once: `path_zenith_rad` is the schema
  default *and* the signature is already claimed by the 0 m fan, so the two could not be
  told apart by an axes string even if the default were not in play. Which lower endpoint a
  scene needs is a physical fact about the site — a 900 m column omits the densest 900 m of
  air, worth roughly +0.12 in band-mean 8–12 µm τ at nadir — so the fans are chosen by name,
  never guessed.

All three are offered by the picker; none is reachable from a YAML that sets only the axes.

---

## 4. Scenario availability today

Switch any of the 38 shipped GUI scenarios to `atmosphere.model = interpolated` and one of
two things happens: it works on the first try with the suggested family, or it produces
exactly one advisory naming the specific missing coverage. **27 first-try, 11 advisory.**
Pinned by scenario id — not by count — in
`tests/integration/test_interpolated_switch_sweep.py`, measured 2026-08-03 (10.3 moved into
the first group when the M9–M13 site-elevation decks were ingested).

### The 27 that work first try

| Family the scene lands on | Scenarios |
|---|---|
| `midlat_summer_sensor_ladder` | 1.2, 1.3, 1.4, 1.5, 2.3, 3.2, 3.3, 3.4, 3.5, 4.1, 4.3, 4.4, 5.1, 5.2, 5.3, 5.4, 5.5, 6.2, 6.3, 6.4, 8.2 (21) |
| `us_standard_zenith_fan` | 1.1, 3.1, 8.1 (3) |
| `midlat_summer_uplooking_zenith_fan` | 10.1 (ground → air at ζ = 29.9°) |
| `midlat_summer_sst_column_fan_site900m` | 10.3 (900 m mountaintop SST → 700 km target) |
| `midlat_summer_uplooking_ladder` | 10.4 (LEO → GEO — a wholly-vacuum path; no backend is consulted, the family is only the parameter's carrier) |

### The 11 that get one advisory, and why

| Scenario | Gap kind | The gap, as the operator sees it |
|---|---|---|
| 2.1, 2.2, 2.5 | `sensor_altitude` | `midlat_summer_sensor_ladder` covers sensor_altitude 3 km to 40000 km; this scene asks for **1 m**, below the family's runs |
| 7.1, 7.2, 7.3, 7.4, 7.5 | `sensor_altitude` | same — a lab/test-bench sensor at **1 m** |
| 6.1 | `sensor_altitude` | same — sensor at **1 km** |
| 4.5 | `sensor_altitude` | same — UAV at **2 km** |
| 10.2 | `direction` | no bundled interpolation family is rendered for a **level-looking** line of sight |

### What unblocks each group

- **The 10 low-sensor scenes (1 m – 2 km).** The down-looking sensor ladder's hull starts at
  3 km; neither SST fan carries a sensor axis. Nothing about these is
  a defect — no MODTRAN run below 3 km down-looking (other than the F block's 3 km rung) has
  been ingested into a family. Until one is, `simple` is the answer, and for a
  ground-to-ground or near-ground path it is also the physically honest one.
- **10.3, the 900 m observatory — no longer blocked.** It was, on the SST fan's fixed 0 m
  lower endpoint, and the advisory named rows M9–M13 as the scheduled fix. Those decks were
  delivered and ingested on 2026-08-03 as the sibling family
  `midlat_summer_sst_column_fan_site900m` (a sibling rather than a sensor axis: the 0 m fan
  had to stay byte-identical, and the two blocks do not share a sec ladder — the 900 m block
  has no 48.2° rung, because H5 is a ground run with no elevated sibling). The scene now
  evaluates first-try. **An elevated site other than 0 m or 900 m is still `simple`**: two
  rungs is not a sensor axis, and neither fan will interpolate one.
- **10.2, the level line of sight.** Blocked on there being no level family at all, and one
  cannot be interpolated from a column ladder: a level arm has zero vertical extent and a
  local zenith of $\pi/2$ everywhere, so no rung of a ladder is that path (theory §3.7). The
  L-block horizontal grid (25 delivered runs) exists but no family ingests it — parity §3
  item 9. `simple`'s level whole-path evaluator is the supported route.

---

## 5. Warnings and refusals, cataloged

Everything RADIANT's atmosphere layer says to you falls into two classes. **Informational**
messages let the run finish and tell you what the number does and does not include.
**Refusals** stop the run because no measured answer exists and inventing one would be
silently wrong (Rule 17).

### Informational — the run continues

**I1 — The hybrid two-model split (up-looking on `interpolated`).**
*Fires when:* an up-looking scene is served by an interpolated up-looking family.
*Means:* two independently-calibrated models are in one answer. The observer leg
(sensor → target) comes from the MODTRAN family; the target's illumination (solar column
and the sky hemisphere above the target) and the sky radiance along the LOS continuation
come from a `SimpleAtmosphere` companion, because an up-looking family carries neither leg
and neither can be recovered from it. The composed answer is **not** a single
self-consistent radiative transfer.
*Size of it:* on the observer leg, 3–5 µm, ground to 10 km, the companion runs −17.3 % in τ
and +35.5 % in L against the run family, worth −4.5 % in SNR (parity §2.11).
*What to do:* accept it, or use `atmosphere.model='simple'` for one consistent model
throughout. Where the two models must agree — τ_sun, E_TOA, and both E_sky terms, all
served by the companion alone — they are bit-identical.
*This is never silent, by ratification.* The owner ratified the split on 2026-08-01
**conditionally on it staying declared**: a `UserWarning`, an INFO log record, and
`stage_outputs["atmosphere"]["topology_provenance"]["backend_split"]` each exist and each
has a test. Softening any of the three into silence retracts the ratification (theory §3.7).

**I2 — A query field that is not an interpolation axis (CU-167).**
*Fires when:* a geometry field the family does not interpolate over differs from the value
its runs were rendered at, by more than **1 m** (altitudes) or **≈ 1°** (angles).
*Means:* the result carries the runs' value, not yours. Most commonly this is the sun:
every bundled family is rendered at solar zenith 30°, so any other sun trips it.
*What to do:* accept the stored geometry's physics, or add runs covering that dimension and
name it in `atmosphere.interpolation_axes`.
*One exemption, and it is exact:* a query sensor **above** a recorded at-or-above-100 km
sensor sees an identical column — the added path is vacuum. That is the identity behind the
ladders' 40 000 km duplicate node (theory §3.6).
*Note the asymmetry:* the chain warns here, but `atmosphere_family_suggestion()` will not
*recommend* a family on a non-axis mismatch of sensor altitude, target altitude, or LOS
zenith — warning about a family you deliberately chose is right; proposing one that would
silently serve a different column is not. Solar geometry is deliberately exempt from that
stricter rule, because every shipped family has one sun and treating it as disqualifying
would leave no family for any scene at a different time of day.

**I3 — Provisional scattered sky below 3 µm.**
*Fires when:* a daytime scene ($\cos\theta_s > 0$) produces a sky radiance on a grid
reaching below **3.0 µm**.
*Means:* the simple model's single-scatter source under-predicts the daytime sky, where
multiple scattering dominates. The thermal component (MWIR/LWIR) is MODTRAN-anchored and is
**not** affected.
*Size of it:* roughly a factor of 2 near the horizon (parity §2.4, §3 item 2).
*What to do:* use a MODTRAN or interpolated backend for quantitative VIS/NIR sky-background
work.
*One blind spot to know about:* a pure-thermal target has its solar geometry stripped
upstream, so a `T1Thermal` target on a VIS/NIR grid gets a thermal-only sky at noon and
**no warning**, because the trigger condition is never met (parity §3 item 12).

**I4 — Interpolated down-looking runs collapse the sun leg.**
*Fires when:* every down-looking `interpolated` evaluation.
*Means:* the backend has one stored column per node and does not carry the two-leg split, so
τ_sun is set to τ_up (and, for a surface target, τ_up = τ_full_up, L_path_up = L_path_full).
*What to do:* nothing, for a scene whose signal is thermal or whose solar leg matches the
view leg. For a reflective scene at a solar zenith far from the view zenith, this is a real
approximation and `simple` carries the proper two-leg split.

**I5 — Tabulated backend collapses everything to one value.** Same shape as I4, for
`atmosphere.model='tabulated'`: τ_sun = τ_up = τ_full_up and L_path_up = L_path_full from
the single tabulated column. A tabulated file is geometry-agnostic by design.

**I6 — Near-horizontal path, inside the warn shoulder.**
*Fires when:* an endpoint-minimum path sits between **0.5° and 2.0°** of the geometric
horizontal, or an interior-tangent path's tangent point sinks **100 m to 2000 m** below its
endpoints.
*Means:* atmospheric refraction is not modelled in v1.x and is the dominant geometric error
in this band. The thresholds are provisional pending MODTRAN refraction calibration.
*Size of it:* where the path has a tangent point, the warning quotes the number — under the
standard $k = 4/3$ effective-radius model the ray would bottom out at $\Delta h/k$ rather
than $\Delta h$, so the air the path is sampled through sits on average
$\tfrac{2}{3}\,\Delta h\,(1 - 1/k)$ lower than the true refracted ray's, biasing band
transmittance slightly low. An endpoint-minimum slant has no
tangent point, so the omission is a path-length effect and the warning says it is not sized.

**I7 — Level chord dipping below mean sea level.**
*Fires when:* a level whole path between two points at the same altitude has its midpoint
perigee below 0 m MSL (an 8 km arm at sea level dips 1.3 m).
*Means:* the integration floor is clamped to 0 m; the sub-surface sliver is not counted.
*Size of it:* the warning computes it — the column is under-stated by at most
$\exp(-h_p/H_{\mathrm{H_2O}}) - 1$, water vapour being the shallowest profile (an 8 km
sea-level arm's 1.3 m dip is 0.065 %).
*What to do:* raise the endpoint altitude or shorten the path if the clamp bothers you.

### Refusals — something has to change

**R1 — Down-looking scene with an elevated target and no target axis.**
*Trigger:* `atmosphere.model='interpolated'`, `geometry.target_altitude_m > 0`, and
`target_altitude_m` absent from `atmosphere.interpolation_axes`.
*Physically:* a grid without a target-altitude axis holds only the full (target at 0 m)
column, and **one column cannot supply both** the target→sensor leg (τ_up) and the
ground→sensor full column (τ_full_up) that the background branch needs.
*Remedy, quoted from the error:* set `atmosphere.interpolation_axes` to the exact string the
error names — which also names the shipped family that string selects and its coverage —
or point `atmosphere.interpolated_data_dir` at a grid carrying a target-altitude axis, or
use `atmosphere.model = 'simple'`.
*Raised at config time* by `Sensor.validate_atmosphere_coverage()`, and again inside the
chain as defence in depth.

**R2 — No shipped family for this `(direction, axes)` pair.**
*Trigger:* `interpolated` with an empty `interpolated_data_dir` and an axes string no
shipped family owns for this LOS direction.
*Physically:* the bundled library is a closed set of 8 dispatchable `(direction, axes)`
combinations; an axes string outside it has no directory to fall back to. The error lists
the whole shipped catalogue.
*Remedy:* set the axes string the error suggests for this scene, point
`interpolated_data_dir` at your own NPZ runs whose `geometry` coordinates carry these axes,
or use `simple`.

**R3 — Query outside the node hull.**
*Trigger:* any axis value beyond the family's node range (regular grid), or outside the
convex hull of the nodes (scattered grid).
*Physically:* interpolation does not extrapolate — there is no measured column there
(theory §3.2).
*Remedy:* add pre-computed runs covering the geometry, clamp the query into the available
range, or pick a family whose hull contains the scene. The error prints the per-axis bounds.

**R4 — LOS zenith at or beyond the $\sec\zeta$ ceiling.**
*Trigger:* a zenith-angle axis queried at or beyond **1.55 rad ≈ 88.8°** (air mass ≈ 50).
*Physically:* the interpolation coordinate is $\sec\zeta$, which diverges at the horizon. The
85°/88°/89.5° probes (M6–M8) were run and are usable as *physics anchors*, but are
deliberately excluded from every shipped node set, so the interpolated backend cannot serve
that band at all (parity §3 item 6).
*Remedy:* keep zenith angles below 88.8°, or use `simple`.

**R5 — Up-looking family rendered at one zenith, queried at another.**
*Trigger:* an up-looking family with **no** `path_zenith_rad` axis (the vertical K ladder;
the 48.2° P sensor ladder), queried at any other lower-endpoint zenith than its rendered one
(tolerance 1e-6 rad — pure float slack).
*Physically:* mapping the query through $\sec\zeta$ from the single rendered column would be up to
~2.5 % low in band-mean LWIR τ, measured against the K6 45° holdout.
*Remedy, quoted from the error:* point `interpolated_data_dir` at an up-looking family that
carries a zenith axis — `midlat_summer_uplooking_zenith_fan` for targets 0–20 km,
`midlat_summer_sst_column_fan` for the full column to space from the ground,
`midlat_summer_sst_column_fan_site900m` for the same column from a 900 m site — or use
`atmosphere.model='simple'`, which serves any up-looking zenith through the segment
evaluators.
*This is the mis-suggestion CU-322 fixed:* scenario 10.1 used to be handed the vertical
ladder at ζ = 29.9° and then refused. The pre-validated suggestion now names the fan.

**R6 — Up-looking family's rendered lower endpoint does not match the sensor.**
*Trigger:* an up-looking query whose `h_sensor` differs from the family's rendered
`sensor_altitude_m` by more than **1 m**, on a family with no sensor axis.
*Physically:* the runs integrate the column from *that* altitude upward; starting somewhere
else is a different column, and near the ground the difference is large — the lowest 100 m
carry ~8 % of the aerosol column (H_aer = 1.2 km) and ~5 % of the water column
(H_H2O = 2 km). That is why this is a refusal and not a warning.
*Remedy:* add `sensor_altitude_m` to the axes with a run family covering it, or pick the
fan rendered from the site you have, or use `simple`.
*This was scenario 10.3's gap* — the 900 m site against a 0 m-rendered fan — and it is why
the M9–M13 delivery shipped as a second fan rather than being folded into the first: with no
sensor axis, the only way to serve a different lower endpoint is to have run it.

**R7 — Exo target above a partial-column family (the exo guard).**
The guard has **two arms** and asks the family, never a hard-coded name
(`uplooking_target_ceiling_m` reads the highest target altitude the family's own runs
measure):
- *Permitted arm* — the family's ceiling reaches 100 km (`h_atm_top`). It integrated the
  entire column and the remaining path to an exo target is vacuum, so the composed observer
  leg is **identically** the family's top-of-column run. The query is clamped to the ceiling
  node and the clamp is recorded in provenance under `exo_target_vacuum_clamp`. Measured:
  composed products at 100 km / 400 km / GEO are bit-identical, τ agrees with the stored M1
  full-column run to 5.6e−17 (parity §2.10). The qualifying families are
  `midlat_summer_sst_column_fan`, `midlat_summer_sst_column_fan_site900m`, and
  `midlat_summer_uplooking_sensor_ladder`.
- *Refusing arm* — the ceiling is below 100 km, or unrecorded. Real, unmeasured air lies
  between the family's top rung and the target; composing a measured leg with an invented
  one and reporting it as ordinary is what the refusal prevents. The 20 km ladder and zenith
  fan take this arm.
*Remedy, quoted from the error:* use `simple` (one consistent model, exo illumination
included), lower the target below 100 km, or point at a full-column up-looking family — the
error names both by name and by their coverage.

**R8 — Family direction mismatch.**
*Trigger:* a down-looking scene handed an up-looking family, or the reverse.
*Physically:* a down-looking family's radiance product is the **upwelling** path radiance;
an up-looking family's is the **downwelling** one. They are different quantities and are
never substituted for one another.
*Remedy:* point `interpolated_data_dir` at a family rendered for this direction, or use
`simple`. The pre-validated suggestion never proposes one across directions — direction is
the first gate.

**R9 — Level line of sight on an up-looking family.**
*Trigger:* `uplooking_column_product` reached with a level (or down-looking) LOS.
*Physically:* a level arm has zero vertical extent and a local zenith of $\pi/2$ everywhere, so
no rung of a column ladder is that path and no interpolation between rungs produces it.
*Remedy:* `simple`, whose level whole-path evaluator serves it. This is scenario 10.2.

**R10 — The backend cannot serve an up-looking or level topology at all.**
*Trigger:* an up-looking or level scene on any backend that is neither `simple` nor an
`interpolated` model carrying an **up-looking** family plus its simple companion — i.e.
`tabulated`, `modtran` (tape7 import), `exo` on a path that is not wholly vacuum, or
`interpolated` pointed at a down-looking family.
*Means:* the direction-aware segment products are built on the simple model's species
machinery. What *is* supported up-looking: `simple` for any endo path; `interpolated`
pointed at an up-looking family (the hybrid of I1); and any backend for a wholly-vacuum path
with both endpoints at or above 100 km.
*Remedy:* one of those three, or a down-looking geometry with the current backend.

**R11 — Horizon guard, hard band.** Two topologies, two thresholds:
- *Endpoint-minimum* (closest approach is the lower endpoint): refused inside **±0.5°** of
  the geometric horizontal. Within half a degree, refraction dominates the path geometry and
  v1.x has no refraction model, so any number returned would be quietly wrong. The air-mass
  column also loses meaning there.
- *Interior-tangent* (the ray dips to a tangent point between the endpoints — every level
  and near-level arm): refused when the tangent depression exceeds **2000 m**. That is a
  limb-like transit; it samples air far denser than either endpoint and its bending is
  refraction-dominated. Limb paths are declined for v1.x — guarded rather than approximated.
*Remedy:* move more than 2.0° off the horizontal at the lower endpoint, shorten the path,
raise both endpoints, or change the altitudes so the geometry is no longer grazing.
*Why two topologies:* a pure angular test over-rejects benign short horizontal paths (two
towers 8 km apart sit at θ_o = 90.04° with a 1.3 m tangent depression) and a blanket
equal-altitude exemption under-rejects long transits (500 km at 5 km altitude has
Δh ≈ 4.9 km). The split is what makes the guard continuous between them.

**Routing note.** R1, R7 and R10 carry a structural marker that
`radiant.api.is_atmosphere_coverage_refusal(exc)` reads. A coverage refusal means the scene
is legal, the inputs are legal, and the remedy is a different family or `simple` — it
belongs beside the atmosphere inputs as an advisory, never in a modal headed "Parameter
Rejected".

---

## 6. Limits that shape what you should run

The full register is parity §3, with magnitudes and tracking homes. The subset that changes
an operator's choice:

- **Daytime VIS/NIR sky is provisional on `simple`** — under-reads by roughly 2× near the
  horizon, and the rural VIS aerosol optical depth is itself ~2× high. Quantitative
  VIS/NIR sky-background work needs a measured backend. *(parity §3 items 2 and 14)*
- **MWIR thermal path radiance carries a spectral-shape residual on `simple`** — the model
  is flat within each of 15 calibrated regions, which under-reads up-looking MWIR by 25–40 %
  on columns deeper than 5 km and over-reads down-looking MWIR by ~20 % on tall ones. This
  is now the *named dominant residual* after the height-resolved emission temperature
  landed; it is a recorded model limitation, not scheduled debt. *(parity §3 item 1)*
- **Refraction is unmodelled and guard-banded** — ~0.5° of refractive lift near the horizon,
  comparable to the 0.5° hard band itself. Numbers past ~85° are a better-conditioned model,
  not a validated one, and the on/off calibration decks are unrun. *(parity §3 item 3)*
- **Grazing and limb paths are refused, not approximated** — $\sec\zeta$ is unvalidated past 88.8°
  and the interpolated backend cannot serve that band at all; a tangent depression past
  2000 m is declined for v1.x. *(parity §3 item 6; §5 R4, R11)*
- **Long-range MWIR horizontal is not usable on `simple`** — the analytic arm's
  $\tau(2L) = \tau(L)^2$ collapses against a band model: 1.09 at 5 km range down to 0.01 at 100 km,
  at 3 km altitude. LWIR degrades more gently, to 0.82. No horizontal library family is
  built, so the remedy is a MODTRAN backend. *(parity §3 item 9)*
- **Downwelling above 80 km is modelled, not measured** — every `atm_emission_down` rung
  at or below 80 km is now a MODTRAN run (P7/P8 landed 2026-08-03 and replaced the modelled
  60/80 km values, which had over-stated the measured ones by 10.6× and 8 791× in the MWIR).
  Only an off-node query strictly between 80 km and the 100 km atmosphere top is still
  extrapolated, and it is bracketed by a measured value below and the exact zero identity
  above. No shipped family holds a node in that band. *(parity §3 item 8)*
- **Only two site elevations have a full-column family** — 0 m and 900 m. Neither fan
  carries a `sensor_altitude_m` axis, so a site at any other elevation is `simple`.
  *(parity §3 item 7; §4 above)*
- **Twilight is unanchored** — the tangent-transit decks were delivered but no family or
  parity test consumes them, and the transit carries 30–70 air masses where both the
  exponential τ and the unmodelled refraction are at their worst. Treat as an
  order-of-magnitude bound. *(parity §3 item 11)*

---

## 7. Common pitfalls

**Symptom:** you set `atmosphere.model = interpolated`, changed nothing else, and the run
refused with R2.
**Cause:** `atmosphere.interpolation_axes` still holds its schema default,
`path_zenith_rad`, which owns a `(down, path_zenith_rad)` family whose sensor is fixed at
100 km and whose target is fixed at 0 km. Almost no real scene matches it by accident.
**Fix:** call `Sensor.atmosphere_family_suggestion()` (or open the GUI picker) and write the
axes string it names.

**Symptom:** the run works but the numbers barely move when you change the view angle.
**Cause:** LOS zenith is not an axis of the family you selected, so you are getting the
family's rendered zenith and an I2 warning. Check the warning.
**Fix:** pick a family that carries `path_zenith_rad`.

**Symptom:** an up-looking result you can't reconcile with a `simple` run of the same scene.
**Cause:** the hybrid split (I1) — the observer leg is MODTRAN and the illumination and sky
legs are the parametric companion. On a 3–5 µm ground-to-10 km leg the two differ by −17 %
in τ and +35 % in L.
**Fix:** inspect
`result.stage_outputs["atmosphere"]["topology_provenance"]["backend_split"]` to see which
leg came from which model, or run `simple` throughout for one consistent model.

**Symptom:** you asked for `tropical` and the result looks like a mid-latitude summer.
**Cause:** you adopted a bundled family. Nine of the ten are rendered on `midlat_summer`.
**Fix:** heed `Sensor.atmosphere_profile_change_warning()` — or render your own family with
the profile you want and point `interpolated_data_dir` at it.
