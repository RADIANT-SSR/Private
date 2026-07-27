# Shipped Atmosphere Library — Manifest

**Generator:** `scripts/build_atmosphere_library.py` reading the real
MODTRAN run set staged (gitignored) under `modtran/real_runs/`
(`docs/plans/modtran_run_matrix.csv`: the 39-run base delivered
2026-07-17 + the 17-run boost-ladder expansion — G7–G11, I1–I9, H5,
J1–J2 — delivered 2026-07-20 + the Geometry-Flexibility batch-1 K block
K1–K7, delivered 2026-07-26, of which K1–K5 build the up-looking family).
Regenerate with:

```
python scripts/build_atmosphere_library.py
```

**MODTRAN provenance:** MODTRAN 6-family build (Card-1 echo `M F 6…`,
underscore tape7 header). Exact build/band-model string: pending
confirmation from the run operator; recorded here when known. Deck
conventions (Card 3 ANGLE, Card 1 fields) verified against this run set
— CU-065/CU-067, resolved commit `e69d0a6`.

**Spectral treatment:** every array is slit-degraded with a triangular
FWHM = 5 cm⁻¹ kernel on the native uniform 1 cm⁻¹ wavenumber grid, then
decimated to 2 cm⁻¹ sampling and stored float32 (12,984 points,
0.375–14.29 µm). Band-mean τ shifts ≲ 0.003 vs the full-resolution
tape7s. Full-resolution data remains the domain of the committed test
fixtures (plan §7.1), not this library.

**NPZ format:** `TabulatedAtmosphere.from_npz` keys — `wavelength_um`
[µm, ascending], `transmittance` [–], `path_radiance` [W/m²/sr/µm],
optional `atm_emission_down` [W/m²/sr/µm], plus a pickled `geometry`
dict. Since 2026-07-20 (boost plan §4.6, CU-167 follow-through) the
`geometry` dict on **every** file — profiles included — records the full
five-field run geometry (`sensor_altitude_m`, `target_altitude_m`,
`path_zenith_rad`, `solar_zenith_rad`, `solar_azimuth_rad`), not just
the interpolation coordinates. All shipped down-looking runs used solar
zenith 30° / azimuth 0°; `InterpolatedAtmosphere` warns when a query
departs from a recorded non-axis value (a pure-thermal scene with no
declared solar geometry adopts the recorded sun — no warning), and a
query sensor above a recorded at-/above-TOA (100 km) sensor is exempt —
the added path is vacuum, the column identical.

**Up-looking NPZ format (GF-10):** the one up-looking family replaces
`path_radiance` with `path_radiance_toward_lower` [W/m²/sr/µm] (the
*downward* product), omits `atm_emission_down`, and adds a
`los_direction = "up"` marker. `TabulatedAtmosphere.from_npz` cannot read
these files by design — see `midlat_summer_uplooking_ladder/` below.

## Families

### `profiles/` — six standard atmospheres (tabulated, nadir full column)

| File | Run | Sensor→target | Downwelling source |
|------|-----|---------------|--------------------|
| `us_standard.npz` | A1 | 100 km → 0, nadir | H2 (up-looking, 48.2° diffusivity angle) |
| `tropical.npz` | A2 | 100 km → 0, nadir | H4 (48.2°) |
| `midlat_summer.npz` | A3 | 100 km → 0, nadir | — (no H-run; loads as zeros) |
| `midlat_winter.npz` | A4 | 100 km → 0, nadir | — |
| `subarctic_summer.npz` | A5 | 100 km → 0, nadir | — |
| `subarctic_winter.npz` | A6 | 100 km → 0, nadir | — |

Load via `atmosphere.model = "tabulated"` +
`atmosphere.tabulated_transmittance_file` (NPZ path; set the
path-radiance param to the same file). `TabulatedAtmosphere` resamples
to any chain grid.

`atm_emission_down` is the up-looking sky radiance at the 48.2°
diffusivity angle: `E_sky_thermal = π·L` reproduces the hemispheric
downwelling flux to ~15% (validated against the E1 flux table in
`tests/integration/test_modtran_real_runs.py`). Only profiles with a
matching H-run carry it — the four without load with a zero-downwelling
warning, which is the documented `from_npz` default.

### `us_standard_zenith_fan/` — 1-D interpolation over `path_zenith_rad`

| File | Run | RADIANT LOS zenith |
|------|-----|--------------------|
| `zen00.npz` | A1 | 0 (nadir) |
| `zen30.npz` | B1 | 30° |
| `zen45.npz` | B2 | 45° |
| `zen60.npz` | B3 | 60° |

All four carry the H2 downwelling (a target-site hemispheric property,
independent of the viewing zenith for a ground target). Regular 1-D
grid; `InterpolatedAtmosphere` refuses queries beyond 60° (no
extrapolation).

### `midlat_summer_ladders/` — 2-D grid over `(sensor_altitude_m, target_altitude_m)`

18 nodes = 3 sensor altitudes × 6 target altitudes (0/1/5/10/20/29 km):

- 35 km sensor: runs C1–C6.
- 100 km sensor (= TOA): runs A3, G1–G5.
- **40,000 km sensor: duplicates of the 100 km states.** Design decision
  per plan §7.2 (data-only node duplication): MODTRAN's atmosphere ends
  at 100 km, so any sensor above TOA sees the identical column — the
  added path is vacuum. Duplicating the states at a 40,000 km node puts
  every LEO/GEO sensor altitude inside the interpolation hull, and
  interpolating between identical values is exact. The alternative
  (clamping queries to TOA in the loader) would touch code; this is
  data-only.

Since the boost expansion (2026-07-20) every midlat_summer_ladders node
carries the **H5** up-looking 48.2° downwelling as `atm_emission_down`
(plan §4.4) — the zero-downwelling default no longer applies to this
family. The grid structure (18 nodes) is unchanged.

### `midlat_summer_boost_ladder/` — 2-D grid over `(sensor_altitude_m, target_altitude_m)`, boost band

24 nodes = 2 sensor altitudes × 12 target altitudes
(0/1/5/10/20/29/35/40/50/60/80/100 km):

- 100 km sensor (= TOA): runs A3, G1–G5 (0–29 km) + **G7–G11**
  (35/40/50/60/80 km, the boost expansion) + the **synthesized 100 km
  vacuum rung** (τ ≡ 1, L_path ≡ 0 — a physical identity, zero absorbing
  column above the atmosphere top; NOT a MODTRAN run). The vacuum rung
  closes the interpolation hull to the Gap 95 exo handoff so τ_up is
  continuous from 0 km to space.
- 40,000 km sensor: orbital-hull duplicate of the 100 km states, as for
  the ladders (vacuum above TOA → exact).
- The 4.20–4.45 µm **CO₂ band core** is the reason these rungs exist: it
  climbs 0.0001 (ground) → 0.58 (29 km) → 0.75 (35 km) → 0.92 (50 km) →
  1.0 (vacuum) — real stratospheric structure a two-node vacuum
  interpolation cannot reproduce.

### `midlat_summer_boost_offnadir/` — 3-D grid over `(sensor_altitude_m, target_altitude_m, path_zenith_rad)`

36 nodes = 2 sensor × 6 target (0/10/29/50/80/100 km) × 3 zenith
(0°/45°/60°):

- nadir (0°): A3/G3/G5/G9/G11; 45°: I1/G6/I2/I3/I4; 60°: I5–I9.
- The synthesized 100 km vacuum rung is present at **every** zenith
  column (the identity holds at all angles), so the 80–100 km target
  band is inside the hull off-nadir as well as at nadir (plan §4.2,
  widened 2026-07-19).
- Zenith interpolates in airmass sec(θ) space (CU-160): a 45° holdout
  from the 0°/60° columns reproduces the real 45° node to 0.02%
  band-mean τ at altitude.

### `midlat_summer_sensor_ladder/` — 1-D grid over `sensor_altitude_m`

6 nodes = F2 (3 km) + J1 (10 km) + J2 (20 km) + C1 (35 km) + A3 (100 km)
+ 40,000 km orbital duplicate; ground target, nadir. Closes the
airborne-sensor hull for ground-target scenarios. Band-mean τ(8–13 µm)
**decreases** with sensor altitude (0.640 at 3 km → 0.557 at 100 km):
a higher sensor sees more of the ground→sensor column.

All four midlat_summer families (ladders, boost, off-nadir, sensor
ladder) carry the H5 downwelling.

> **Elevated-target downwelling simplification (CU-181).** We have one
> midlat_summer up-looking run (H5, ground level), so the same
> `atm_emission_down` is attached to every target-altitude node,
> including elevated and vacuum rungs. Physically the downwelling a
> target sees thins with altitude (a 80 km target sees almost no sky
> above it); the constant-per-family value therefore OVER-states
> downwelling at elevated targets. This is a secondary (reflected-sky)
> term, negligible against the self-emission of the hot boost bodies
> these families model, and is tracked for future refinement in
> `docs/tracking/Cleanup_Backlog.md` (CU-181).

### `midlat_summer_uplooking_ladder/` — 1-D grid over `target_altitude_m`, **up-looking**

Generator: `scripts/build_atmosphere_library.py` (dict `UPLOOKING_LADDER`).
Inputs: `modtran/real_runs/{K1,K2,K3,K4,K5}.tp7` — run-matrix rows K1–K5,
the Geometry-Flexibility batch-1 up-looking block (plan §8.3). Ground
sensor (H1 = 0 km), vertical (Card-3 ANGLE = 0), midlat_summer, rural
23 km, ITYPE = 2, IEMSCT = 2, SURREF = 0, solar zenith 30°.

6 nodes = K1 (1 km) + K2 (3 km) + K3 (5 km) + K4 (10 km) + K5 (20 km)
+ a **synthesized exact zero-length node** at 0 km.

| File | Run | Target altitude | Band-mean τ (8–12 µm) |
|------|-----|-----------------|------------------------|
| `t000.npz` | *synthesized* | 0 km | 1.000000 (identity) |
| `t001.npz` | K1 | 1 km | 0.77825 |
| `t003.npz` | K2 | 3 km | 0.66663 |
| `t005.npz` | K3 | 5 km | 0.64414 |
| `t010.npz` | K4 | 10 km | 0.62569 |
| `t020.npz` | K5 | 20 km | 0.59517 |

**This is the first up-looking family, and it is not interchangeable with
the down-looking ones.** Three things differ:

1. **Product.** The radiance key is `path_radiance_toward_lower`, the
   *downward* path radiance emerging at the segment's lower end — the
   `L_toward_lower` product of `radiant.atmosphere.segments`. Every other
   family stores the upwelling `path_radiance` under that name. Different
   physical quantity, different key: a down-looking reader hits a missing
   key rather than a plausible-looking wrong number. τ keeps its usual
   name because τ is reciprocal (`RADIANT_Atmosphere.md` §4.4) — one value
   per segment, direction-free.
2. **Marker.** Every file carries `los_direction = "up"`. The loader reads
   it, tags the model, and `InterpolatedAtmosphere.evaluate()` (the
   eight-field down-looking bundle) then refuses the family outright. The
   query entry point is `InterpolatedAtmosphere.uplooking_column_product()`.
3. **Zenith convention.** The recorded `path_zenith_rad = 0` is the
   **lower-endpoint** zenith ζ_low, which for an up-looking path is at the
   *sensor* (ADR-0011 decision 3; ζ_low = π − θ_o). This is the same
   meaning the down-looking families already carry, where the lower
   endpoint is the target and θ_o is target-referenced — one convention,
   read from whichever end is lower.

**Synthesized 0 km node.** A target at the sensor's own altitude has no
air between the endpoints: τ ≡ 1, L ≡ 0 exactly. Same principle as the
boost ladder's synthesized 100 km vacuum rung (a physical identity, never
a MODTRAN run) but at the *other* end of the axis — an up-looking ladder's
path **grows** with target altitude, so τ → 1 is the h_tgt → h_sensor
limit, not the h_tgt → TOA limit.

**Hull ends at 20 km.** There is no vertical midlat_summer up-looking
full-column run (H5 is 48.2°, not 0°), so a target above 20 km is refused,
not extrapolated. Closing the hull to 100 km needs one more owner-run deck.

**τ reciprocity (truth anchor).** K2/K4/K5 span the same 0–3/0–10/0–20 km
columns as the down-looking F2/J1/J2 runs in `midlat_summer_sensor_ladder/`.
Band-mean τ agrees to ≤ 1.2 × 10⁻⁷ relative in VIS/MWIR/LWIR — MODTRAN's
transmittance is reciprocal to round-off, exactly as §4.4 claims.

**K6 holdout (45°).** The one off-vertical K deck is deliberately **not**
shipped: it is the coupling anchor for a future up-looking zenith fan, and
is consumed only by the `skipif`-guarded characterization test. Predicting
it from the vertical 10 km node by the airmass law τ(ζ) = τ(0)^sec ζ
under-predicts band-mean τ by 0.1 % (VIS) to 2.5 % (LWIR) — band-model
non-exponentiality, the same effect measured on the L grid. That is why an
off-vertical up-looking interpolated query **raises** instead of applying
the sec-law: see "Known limitations" below.

### `validation/` — off-grid points (NOT interpolation nodes)

| File | Run | Geometry |
|------|-----|----------|
| `C7.npz` | C7 | 35 km → 10 km at 45° LOS zenith |
| `G6.npz` | G6 | 100 km → 10 km at 45° |
| `H1.npz` | H1 | ground → 100 km up-looking, nadir |

C7/G6 would add a third, two-point axis to the ladder grid — too sparse
to interpolate honestly, so they ship as point data for validating the
θ×h_tgt coupling of any future partial-column model. H1 is the nadir
up-looking downwelling anchor (H2's 48.2° sibling).

## Interpolation-space note (CU-160, 2026-07-17)

`InterpolatedAtmosphere` interpolates zenith-angle axes in **airmass
sec(θ) space** (internally; coordinates stay in radians). For the
`us_standard_zenith_fan/` this reproduces Beer-Lambert exactly between
nodes — validated by a 45° holdout against the real node (−0.1%
band-mean τ, vs −4% under the earlier linear-in-angle axis).

## Known limitations (recorded per plan §7.2)

- **Grid-match requirement (CU-156) — lifted 2026-07-18:**
  `InterpolatedAtmosphere.build_state` now serves any query wavelength
  grid inside the stored spectral range by linear resampling of the
  geometry-interpolated spectra (the `TabulatedAtmosphere` pattern);
  queries extending outside the stored range still fail loud. The
  historical restriction (query grid must equal the stored grid) no
  longer applies.
- **Chain consumption of `h_tgt > 0` — lifted 2026-07-18 (Gap 94):**
  `InterpolatedAtmosphere.evaluate` serves airborne targets from a
  `target_altitude_m` grid axis with a real two-leg up/full split, so
  the ladders are reachable from a chain run (targets 0–29 km; the
  boost families extend this to 0–100 km; beyond the hull still refuses
  — no extrapolation). CU-011's binary flavor remains open.
- **Elevated-target downwelling (CU-181)** — constant-per-family H-run
  value over-states downwelling at elevated targets; see the boost
  families' simplification note above.
- **Aerosol/visibility variants (Blocks D/E) deliberately do not ship** —
  condition-specific studies, regenerate-on-demand (plan §7.2).
- **No up-looking zenith fan (GF-10)** — `midlat_summer_uplooking_ladder`
  is vertical-only, so an off-vertical up-looking *interpolated* query
  raises and names `atmosphere.model = "simple"` (which serves any
  up-looking zenith through the segment evaluators). Mapping off-vertical
  up-looking queries into airmass sec(ζ) space, as the down-looking
  off-nadir family does, is **deferred** until an up-looking zenith fan is
  run: measured against the K6 45° holdout, the sec-law prediction from
  the vertical node is 0.1–2.5 % low in band-mean τ, so applying it
  silently would be a quiet ~2 % LWIR error on every slant up-looking
  scene.
- **No up-looking sensor-altitude axis** — the K family is rendered from
  ground level. An elevated lower endpoint (air-to-air up-looking) is
  refused with a 1 m tolerance rather than warned: the lowest 100 m alone
  carry ≈8 % of the aerosol column (H_aer = 1.2 km) and ≈5 % of the water
  column (H_H2O = 2 km). K7 (5 km → 15 km at 45°) is the delivered anchor
  for that family when it is run.
- **Up-looking families carry one direction only** — the K runs measure the
  downwelling radiance at the ground observer; the reverse-direction
  product for the same column is a separate run set (the reciprocal F/J
  block covers 3 of the 5 rungs). `uplooking_column_product()` therefore
  returns an `UplookingColumnProduct` (τ + `L_toward_lower`) rather than a
  `SegmentQuantities`, which would require inventing an `L_toward_upper`.

## Default families by direction and axes (loaders `_SHIPPED_FAMILY_BY_DIRECTION_AND_AXES`)

When `atmosphere.interpolated_data_dir` is unset, the family is chosen
from the scene's **LOS direction** and `atmosphere.interpolation_axes`
(plan §4.7; direction added by GF-10). Direction is derived pre-chain
from `geometry.sensor_altitude_m` vs `geometry.target_altitude_m` — the
same rule `LineOfSightGeometry.los_direction` applies, pinned to it by a
test. A `(direction, axes)` pair with no shipped family raises the
actionable no-family error listing every row of this table.

| Direction | Axes | Family |
|-----------|------|--------|
| down | `path_zenith_rad` | `us_standard_zenith_fan` |
| down | `sensor_altitude_m,target_altitude_m` | `midlat_summer_ladders` (0–29 km) |
| down | `sensor_altitude_m` | `midlat_summer_sensor_ladder` |
| down | `sensor_altitude_m,target_altitude_m,path_zenith_rad` | `midlat_summer_boost_offnadir` |
| up | `target_altitude_m` | `midlat_summer_uplooking_ladder` |

No `level` family ships: a constant-altitude path is served by the
level-arm segment evaluator on `atmosphere.model = "simple"`, and the
L-block 5×5 horizontal grid is dev-only holdout data (plan §8.3).

The 2-axis key stays on the 0–29 km ladders (no re-baseline, plan §4.1);
nadir 0–100 km boost coverage is reached via the off-nadir family (which
includes the 0° column) or an explicit `interpolated_data_dir` pointed
at `midlat_summer_boost_ladder`.

## Tests asserting this library

`tests/integration/test_shipped_atmosphere_library.py` — loads every
family through its intended runtime path, pins band-mean goldens
(us_standard window τ, H2/H5 downwelling energy, G3 LEO query, boost-rung
τ and CO₂ band-core anchors, sensor-ladder τ), asserts the orbital hull,
no-extrapolation refusal, altitude monotonicity, per-zenith vacuum-rung
exactness, the 45° airmass holdout at altitude, and a full chain run on
the shipped us_standard profile.
`tests/integration/test_exo_target_chain.py` — mid-boost (50 km) chain
smoke and the §6 acceptance sweep (target 0→300 km, monotone τ_up, no
CU-167 warnings, at 45° zenith). `src/radiant/atmosphere/tests/
test_loaders.py` — the shipped-default family selection per direction and
axes, and the pin between the loader's pre-chain direction rule and
`LineOfSightGeometry.los_direction`.
`tests/integration/test_uplooking_horizontal_anchors.py` — the
`skipif`-guarded K6 45° coupling characterization against the delivered
tape7 (needs `modtran/real_runs/`).
