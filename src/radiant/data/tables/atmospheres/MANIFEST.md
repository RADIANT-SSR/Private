# Shipped Atmosphere Library — Manifest

**Generator:** `scripts/build_atmosphere_library.py` reading the real
MODTRAN run set tracked under `modtran/real_runs/`
(`docs/plans/modtran_run_matrix.csv`: the 39-run base delivered
2026-07-17 + the 17-run boost-ladder expansion — G7–G11, I1–I9, H5,
J1–J2 — delivered 2026-07-20 + the Geometry-Flexibility batch-1 K block
K1–K7, delivered 2026-07-26, of which K1–K5 build the up-looking family
+ **batch 2** — M1–M8, N1–N10, O1–O5, P1–P6, Q1–Q4, Q7–Q8, delivered
2026-08-02, which add three up-looking families, one down-looking
upwelling grid, and the altitude-resolved downwelling of CU-181).
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

**Up-looking NPZ format (GF-10):** every up-looking family replaces
`path_radiance` with `path_radiance_toward_lower` [W/m²/sr/µm] (the
*downward* product), omits `atm_emission_down`, and adds a
`los_direction = "up"` marker. `TabulatedAtmosphere.from_npz` cannot read
these files by design — see `midlat_summer_uplooking_ladder/` below.
Four up-looking families ship: the vertical K ladder, the batch-2 zenith
fan, the batch-2 SST full-column fan, and the batch-2 elevated-observer
ladder.

**Downwelling is altitude-resolved (CU-181, batch 2):** a down-looking
node's `atm_emission_down` is the up-looking 48.2° diffusivity-angle sky
radiance **at that node's target altitude** — `E_sky_thermal = π·L` is
the sky irradiance falling on the target, so the target altitude is the
physically meaningful key. It is interpolated from the measured rung
ladder H5 (0 km) + P1–P6 (1/5/10/20/29/50 km) by
`scripts/downwelling_altitude.py`: `ln L` piecewise linear in altitude
inside the measured span, the top-two-rung slope (clamped non-increasing)
above it, and exactly zero at the 100 km atmosphere top, where an
observer has no sky above it. Before batch 2 the single ground-level H5
value was attached to every node; ground-target nodes are therefore
byte-identical and only elevated-target nodes moved. Measured decay of
the shipped `atm_emission_down` across 0 → 50 km: **142×** (3–5 µm band
mean) and **442×** (8–12 µm) — see "Known limitations" for why that is
one-to-two orders less than CU-181's analytic table predicted.

## Families

### `profiles/` — six standard atmospheres (tabulated, nadir full column)

| File | Run | Sensor→target | Downwelling source |
|------|-----|---------------|--------------------|
| `us_standard.npz` | A1 | 100 km → 0, nadir | H2 (up-looking, 48.2° diffusivity angle) |
| `tropical.npz` | A2 | 100 km → 0, nadir | H4 (48.2°) |
| `midlat_summer.npz` | A3 | 100 km → 0, nadir | H5 (48.2°) |
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

### `midlat_summer_uplooking_zenith_fan/` — 2-D grid over `(target_altitude_m, path_zenith_rad)`, **up-looking**

18 nodes = 6 target altitudes (0/1/3/5/10/20 km) × 3 lower-endpoint
zeniths. Ground observer (0 km) throughout, `midlat_summer`.

| Zenith | sec ζ | Runs (targets 1/3/5/10/20 km) |
|--------|-------|-------------------------------|
| 0° | 1.0000 | K1–K5 (batch 1, not re-run — Rule 27) |
| 48.2° | 1.4999 | N1–N5 |
| 60° | 2.0000 | N6–N10 |

The `target = 0` row at every zenith is the **synthesized zero-length
identity** (τ ≡ 1, `L_toward_lower` ≡ 0): a target at the observer's own
altitude has no air between the endpoints, at any zenith. It closes the
grid's bottom row exactly, the same way the boost ladder's 100 km vacuum
rung closes its top.

**This is the family that closes the GF-10 deferral.** Before batch 2 an
off-vertical up-looking interpolated query was *refused* (see "Known
limitations"); this family carries a `path_zenith_rad` axis, so the query
is served, interpolating in airmass sec(ζ) space like every down-looking
fan (CU-160). Three sec rungs is the minimum that can *test* linearity in
sec rather than assume it. The refusal survives, narrowed, for up-looking
families that carry no zenith axis — the K ladder and the P ladder below.

**Hull ends at 20 km and at sec 2.0.** A target above 20 km or a zenith
past 60° is refused, not extrapolated. K6 (10 km at 45°) still sits off
this grid and stays a holdout spot check.

### `midlat_summer_sst_column_fan/` — 1-D grid over `path_zenith_rad`, **up-looking**, full column

A ground observer's whole column to the 100 km atmosphere top — the SST
(space surveillance) anchor family, `midlat_summer`.

| File | Run | Zenith | sec ζ |
|------|-----|--------|-------|
| `z00.000.npz` | M1 | 0° | 1.0 |
| `z48.200.npz` | H5 | 48.2° | 1.5 |
| `z60.000.npz` | M2 | 60° | 2.0 |
| `z70.529.npz` | M3 | 70.529° | 3.0 |
| `z75.522.npz` | M4 | 75.522° | 4.0 |
| `z78.463.npz` | M5 | 78.463° | 5.0 |

A uniform sec ladder 1…5, which is what makes the CU-160 interpolation
coordinate evenly sampled rather than crowded near nadir.

**M6–M8 (85°/88°/89.5°, sec 11.5/28.7/114.6) are `dev_only` and do not
ship.** They sit outside the uniform ladder and, for M7/M8, at or past
`InterpolatedAtmosphere`'s 88.8° airmass ceiling, where the sec-space
mapping is unvalidated; shipping them would put an unvalidated coordinate
inside a hull the interpolator is allowed to traverse. They remain
staged run data for the near-horizon air-mass work (CU-320).

**Reachable only through an explicit `atmosphere.interpolated_data_dir`.**
Its `(up, path_zenith_rad)` signature is free, but `path_zenith_rad` is
the *schema default* for `atmosphere.interpolation_axes`, so publishing it
as a default-dispatch row would turn today's actionable refusal for an
up-looking scene that never touched the axes parameter into a silent
dispatch onto a family whose target altitude is fixed at 100 km. It is
listed in `EXPLICIT_DIR_FAMILIES` instead, so the GUI picker still offers
it by name and writes the directory (the ex-CU-296 pattern).

### `midlat_summer_uplooking_sensor_ladder/` — 1-D grid over `sensor_altitude_m`, **up-looking**

An *elevated* observer's full column to the 100 km top at the fixed 48.2°
diffusivity angle: the batch-2 P block plus H5.

| File | Run | Observer altitude |
|------|-----|-------------------|
| `s000.npz` | H5 | 0 km (ground) |
| `s001.npz` | P1 | 1 km |
| `s005.npz` | P2 | 5 km |
| `s010.npz` | P3 | 10 km |
| `s020.npz` | P4 | 20 km |
| `s029.npz` | P5 | 29 km |
| `s050.npz` | P6 | 50 km |
| `s100.npz` | — | 100 km, synthesized zero-length identity |

These are the same runs the CU-181 downwelling ladder is built from; here
they are library nodes in their own right (the run matrix's P-row note
asked for `tau_total` precisely so they could be).

**One zenith only.** The family carries no `path_zenith_rad` axis, so a
query at any other zenith is refused with a message naming the 48.2° it
*is* rendered at and pointing at `midlat_summer_sst_column_fan` (which
carries the axis) or `atmosphere.model = "simple"`.

### `midlat_summer_upwelling_offnadir/` — 2-D grid over `(sensor_altitude_m, path_zenith_rad)`

9 nodes = 3 sensor altitudes × 3 LOS zeniths, **ground target**,
down-looking, `midlat_summer`. The upwelling reciprocals of the
up-looking columns, and the emission-height anchors CU-224's down-looking
thermal term needs.

| Sensor | 0° | 48.2° | 60° |
|--------|----|-------|-----|
| 10 km | J1 | O3 | O4 |
| 100 km | A3 | O5 | I5 |
| 40 000 km (GEO) | A3 | O5 | I5 (orbital duplicates) |

The recorded `path_zenith_rad` is the run matrix's
`path_zenith_deg_radiant` — the **lower-endpoint (ground) zenith**, the
same convention every other family records. MODTRAN's Card-3 ANGLE on
these decks is `180° −` that (180 / 131.8 / 120), which is exactly the
ex-CU-223 conversion; a builder that fed `los.theta_o` straight through
would have written the wrong number, and
`tests/integration/test_batch2_atmosphere_families.py` asserts it did not.

O1 (1 km) and O2 (5 km) are nadir-only — they have no zenith column, so
they cannot join this rectangular grid and ship under `validation/`.

### `validation/` — off-grid points (NOT interpolation nodes)

| File | Run | Geometry |
|------|-----|----------|
| `C7.npz` | C7 | 35 km → 10 km at 45° LOS zenith |
| `G6.npz` | G6 | 100 km → 10 km at 45° |
| `H1.npz` | H1 | ground → 100 km up-looking, nadir |
| `O1.npz` | O1 | 1 km → ground, nadir (down-looking partner of K1) |
| `O2.npz` | O2 | 5 km → ground, nadir (down-looking partner of K3) |

C7/G6 would add a third, two-point axis to the ladder grid — too sparse
to interpolate honestly, so they ship as point data for validating the
θ×h_tgt coupling of any future partial-column model. H1 is the nadir
up-looking downwelling anchor (H2's 48.2° sibling). O1/O2 are the matched
down-looking partners of the K1/K3 up-looking columns: τ must match
(reciprocity) while path radiance must not (CU-224's asymmetry).

## Interpolation-space note (CU-160, 2026-07-17)

`InterpolatedAtmosphere` interpolates zenith-angle axes in **airmass
sec(θ) space** (internally; coordinates stay in radians). For the
`us_standard_zenith_fan/` this reproduces Beer-Lambert exactly between
nodes — validated by a 45° holdout against the real node (−0.1%
band-mean τ, vs −4% under the earlier linear-in-angle axis).

## Known limitations (recorded per plan §7.2)

- **Grid-match requirement (CU-156) — lifted 2026-07-18:**
  `InterpolatedAtmosphere.build_state` now serves any query wavelength
  grid inside the stored spectral range by resampling the
  geometry-interpolated spectra (the `TabulatedAtmosphere` pattern);
  queries extending outside the stored range still fail loud. The
  historical restriction (query grid must equal the stored grid) no
  longer applies. Since CU-306 (2026-08-01) that resample runs in
  **log-τ** for transmittance — the same optical-depth space the
  geometry interpolation uses, so the two commute — and linearly for
  the radiances, which carry no Beer-Lambert path-length exponential.
- **Chain consumption of `h_tgt > 0` — lifted 2026-07-18 (Gap 94):**
  `InterpolatedAtmosphere.evaluate` serves airborne targets from a
  `target_altitude_m` grid axis with a real two-leg up/full split, so
  the ladders are reachable from a chain run (targets 0–29 km; the
  boost families extend this to 0–100 km; beyond the hull still refuses
  — no extrapolation). CU-011's binary flavor remains open.
- **Elevated-target downwelling (CU-181) — resolved into data 2026-08-02,
  with one modelled band left.** The constant-per-family H-run value is
  gone: every down-looking node now carries the measured downwelling at
  its own target altitude (see the NPZ-format note above). What remains
  modelled rather than measured is the band **above 50 km** — the 60/80 km
  boost rungs, extrapolated on the 29→50 km log slope as the run matrix
  directs, with the slope clamped non-increasing because no residual
  column can gain emitters with altitude. Those nodes are an upper bound,
  in the same conservative direction as the constant they replace and
  ~150× smaller. Below 50 km every node is measured.
  **The entry's ≳10⁴ acceptance criterion is NOT met, and should not be.**
  MODTRAN says the real midlat_summer downwelling falls 142× (3–5 µm) and
  442× (8–12 µm) across 0 → 50 km. CU-181's 16 579× figure came from
  `SimpleAtmosphere.evaluate`'s own `E_sky_thermal` — RADIANT predicting
  itself — whose water-dominated column collapses far faster than the real
  stratospheric CO₂/O₃ emission does. The MWIR profile is also **not
  monotonic**: the 29 km rung is brighter than the 20 km one, which is why
  the interpolation assumes no monotonicity.
- **Aerosol/visibility variants (Blocks D/E) deliberately do not ship** —
  condition-specific studies, regenerate-on-demand (plan §7.2).
- **Up-looking zenith fan (GF-10) — landed 2026-08-02.**
  `midlat_summer_uplooking_zenith_fan` (targets 0–20 km × sec ζ 1.0–2.0)
  and `midlat_summer_sst_column_fan` (full column × sec ζ 1–5) carry a
  `path_zenith_rad` axis and serve off-vertical up-looking queries in
  airmass sec(ζ) space, as the down-looking off-nadir family does. The
  refusal survives, **narrowed**: an up-looking family with no zenith axis
  (`midlat_summer_uplooking_ladder` at vertical,
  `midlat_summer_uplooking_sensor_ladder` at 48.2°) still raises for any
  other zenith rather than applying the sec law from its one rendered
  column — measured against the K6 45° holdout, that prediction is
  0.1–2.5 % low in band-mean τ, so applying it silently would be a quiet
  ~2 % LWIR error. The message now names the fans as the remedy.
- **Up-looking sensor-altitude axis — partial (2026-08-02).**
  `midlat_summer_uplooking_sensor_ladder` gives the *full column to the
  100 km top* an observer-altitude axis (0–50 km, at 48.2° only). The
  partial-column families (K ladder, zenith fan) are still rendered from
  ground level, and an elevated lower endpoint on them is refused with a
  1 m tolerance rather than warned: the lowest 100 m alone carry ≈8 % of
  the aerosol column (H_aer = 1.2 km) and ≈5 % of the water column
  (H_H2O = 2 km). K7 (5 km → 15 km at 45°) is the delivered anchor for an
  elevated-endpoint *partial*-column family when it is run.
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
| down | `sensor_altitude_m,path_zenith_rad` | `midlat_summer_upwelling_offnadir` |
| up | `target_altitude_m` | `midlat_summer_uplooking_ladder` |
| up | `target_altitude_m,path_zenith_rad` | `midlat_summer_uplooking_zenith_fan` |
| up | `sensor_altitude_m` | `midlat_summer_uplooking_sensor_ladder` |

Two bundled families are reachable **only** through an explicit
`atmosphere.interpolated_data_dir` (`EXPLICIT_DIR_FAMILIES`):
`midlat_summer_boost_ladder`, whose 2-axis signature is owned by
`midlat_summer_ladders`, and `midlat_summer_sst_column_fan`, whose
signature is free but is the *schema default* axes string, so publishing
it would silently widen an existing refusal. The GUI family picker offers
both by name and writes the directory.

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
`tests/integration/test_batch2_atmosphere_families.py` — the batch-2
ingestion contract: every delivered Card-3 echo against the run matrix on
the ex-CU-223 lower-endpoint convention, every new family's grid shape and
sec ladder, node-exact and sec-space off-node queries, the dev-only M6–M8
exclusion, and the CU-181 per-rung downwelling table (including the
byte-identity of every ground-target node with the old H5 constant).
`tests/integration/test_batch2_fixture_anchors.py` — full-resolution
parse-level anchors for the five promoted fixtures (M1, N4, N9, O1, P1);
see `tests/integration/fixtures/modtran/MANIFEST.md`.
`scripts/test_downwelling_altitude.py` — Level-0 tests of the CU-181
altitude interpolation itself, against hand-computed values.
