# Shipped Atmosphere Library — Manifest

**Generator:** `scripts/build_atmosphere_library.py` reading the real
MODTRAN run set staged (gitignored) under `modtran/real_runs/`
(delivered 2026-07-17; 39-run matrix of
`docs/plans/modtran_run_matrix.csv`). Regenerate with:

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
dict of interpolation coordinates on the interpolated families.

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

No downwelling data for midlat_summer (no H-run) — the ladders load
with the zero-downwelling default.

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

- **Grid-match requirement (CU-156):** `InterpolatedAtmosphere.build_state`
  requires the query wavelength grid to equal the stored grid — the
  interpolated families (fan, ladders) therefore serve sessions running
  on the library grid, until resampling support lands. The tabulated
  `profiles/` have no such restriction.
- **Chain consumption of `h_tgt > 0`:** `InterpolatedAtmosphere.evaluate`
  (the Option-C chain path) raises `NotImplementedError` for airborne
  targets, so the ladders are not yet reachable from a chain run — they
  ship as the reference data that unblocks that extension (Gap 39
  closed against them; CU-011 binary flavor still open).
- **Aerosol/visibility variants (Blocks D/E) deliberately do not ship** —
  condition-specific studies, regenerate-on-demand (plan §7.2).

## Tests asserting this library

`tests/integration/test_shipped_atmosphere_library.py` — loads every
family through its intended runtime path, pins band-mean goldens
(us_standard window τ, H2 downwelling energy, G3 LEO query), asserts
the orbital hull, no-extrapolation refusal, altitude monotonicity, and
a full chain run on the shipped us_standard profile.
