# Shipped Atmosphere Library — Manifest

**Generator:** `scripts/build_atmosphere_library.py` reading the real
MODTRAN run set staged (gitignored) under `modtran/real_runs/`
(56-run matrix of `docs/plans/modtran_run_matrix.csv`: the 39-run base
delivered 2026-07-17 + the 17-run boost-ladder expansion — G7–G11, I1–I9,
H5, J1–J2 — delivered 2026-07-20). Regenerate with:

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

## Default families by interpolation axes (loaders `_SHIPPED_FAMILY_BY_AXES`)

When `atmosphere.interpolated_data_dir` is unset, the family is chosen
from `atmosphere.interpolation_axes` (plan §4.7):

| Axes | Family |
|------|--------|
| `path_zenith_rad` | `us_standard_zenith_fan` |
| `sensor_altitude_m,target_altitude_m` | `midlat_summer_ladders` (0–29 km) |
| `sensor_altitude_m` | `midlat_summer_sensor_ladder` |
| `sensor_altitude_m,target_altitude_m,path_zenith_rad` | `midlat_summer_boost_offnadir` |

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
test_loaders.py` — the shipped-default family selection per axes.
