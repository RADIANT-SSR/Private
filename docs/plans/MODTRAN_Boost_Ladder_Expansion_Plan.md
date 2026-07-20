# MODTRAN Boost-Ladder Expansion Plan — targets to 100 km + off-nadir grid

Status: Active
Owner trigger: 2026-07-18 — missile-defense boost-phase application (detect from
launch through burnout from a space sensor); follows the Gap 95 owner review.
Scope ratified in-conversation 2026-07-18 ("append the new runs to the existing
run_matrix … capture both the additional runs and the followup processing and
integration").
Amended: 2026-07-19 — atmospheric-paradigm audit (owner-ratified same day).
Four audit findings folded in: (1) the off-nadir family needs the synthesized
100 km vacuum rung too, or the §6 acceptance sweep fails for 80–100 km targets
at 45°/60°; (2) airborne sensors (0–35 km) had no shipped family — J-block +
promoted F2 close it for ground targets; (3) H5 supplies the missing
midlat_summer downwelling (E_sky_thermal loads as 0 W/m²/sr/µm on every
ladder/boost node today); (4) §4 gains the `loaders._SHIPPED_FAMILY_BY_AXES`
wiring and an explicit all-families scope for the geometry-recording rebuild.
VLWIR (> 14.29 µm) stays out of scope — tracked as Gap 99.

## 1. Objective

Extend RADIANT's real-MODTRAN atmosphere library so a space sensor can model a
boosting target continuously from launch (0 km) through burnout (>100 km):

- **0–29 km** — already covered (C/G ladders, shipped 2026-07-17).
- **29–100 km** — NOT covered; the band a booster climbs through mid-boost.
  Broadband residual τ error is small (band-mean 0.95–0.98 floors, Gap 39),
  but the residual column is O₃/CO₂ — the constituents that shape the CO₂
  4.3 µm plume-detection band and the 9.6 µm O₃ band. Real runs required;
  a vacuum-node interpolation from 29 km would misrepresent the band cores.
- **≥ 100 km** — permanently covered by code, not data: the Gap 95 vacuum
  target leg (τ_up ≡ 1, L_path_up ≡ 0, full ground→sensor column retained for
  the background) landed 2026-07-18 (`atmosphere/exo_target.py`, wired in
  `AtmosphereStage`). No MODTRAN run can improve on an identity.
- **Off-nadir** — boost-phase tracking from LEO is rarely nadir. The shipped
  ladders are nadir-only, and CU-167 (fixed 2026-07-18) now *warns* rather than
  silently serving the nadir column for a slant query; the warning goes away
  only when the data actually covers the zenith dimension.
- **Airborne sensors (0–35 km)** *(2026-07-19 amendment)* — no shipped family
  covers a sensor below the 35 km ladder floor: an aircraft scenario on
  `interpolated` is either refused (ladders hull) or, on the zenith fan,
  silently served the 100 km space column (the fan NPZs record no
  `sensor_altitude_m` for the CU-167 check to compare). The J-block + the
  already-delivered F2 run close this for ground targets.
- **midlat_summer downwelling** *(2026-07-19 amendment)* — no H-run exists for
  the profile every altitude family uses, so every ladder/boost node loads
  with `atm_emission_down ≡ 0 W/m²/sr/µm` → `E_sky_thermal = 0 W/m²` (sky-reflected
  term lost for LWIR/MWIR low-emissivity targets and sea backgrounds). H5 is
  the H2/H4 sibling that fixes it.

## 2. New runs (appended to `docs/plans/modtran_run_matrix.csv`, 2026-07-18; H5/J-block appended 2026-07-19)

All midlat_summer, rural/23 km vis (irrelevant above ~30 km), IEMSCT=2,
700–25000 cm⁻¹ @ 1 cm⁻¹; G/I blocks H1 = 100 km (space column). All
destination `shipped_library`. Decks are rendered (56 total now) — regenerate
anytime with `python scripts/render_modtran_decks.py`.

| Runs | Geometry | Purpose |
|------|----------|---------|
| G7–G11 | H2 = 35/40/50/60/80 km, nadir | Boost ladder: closes 29–100 km. Node spacing ≈ 1–1.5 pressure scale heights so log-τ interpolation between rungs is well-conditioned |
| I1–I4 | H2 = 0/29/50/80 km at 45° LOS zenith | Off-nadir boost grid (45° column; G6 already supplies 10 km @ 45°) |
| I5–I9 | H2 = 0/10/29/50/80 km at 60° LOS zenith | Off-nadir boost grid (60° column, airmass = 2 anchor) |
| H5 *(2026-07-19)* | H1 = 0 → H2 = 100 km, up-looking at 48.2° (diffusivity angle) | midlat_summer thermal downwelling — the H2/H4 sibling; π·L(48.2°) [W/m²/µm] attaches to every midlat_summer family node at build |
| J1–J2 *(2026-07-19)* | H1 = 10/20 km → ground, nadir | Airborne sensor ladder rungs; with the promoted F2 (3 km, already delivered) plus C1 (35 km) and A3 (100 km) forms a 5-node 1-D `sensor_altitude_m` family for ground targets |

Total: 17 new MODTRAN runs to execute (14 from 2026-07-18 + H5/J1/J2; F2 is
promoted, not re-run — its tape7 is already in `modtran/real_runs/`). The
MODTRAN ANGLE convention caveat (CU-065: `ANGLE` at H1 = 180° − LOS zenith for
down-looking paths) applies — verify on the first I-block run before trusting
the batch, exactly as the B-fan was verified. H5 is up-looking: ANGLE at H1 =
LOS zenith directly (48.2°, no 180° conversion), same as H1–H4.

**Deliberately not run**: any H2 ≥ 100 km (vacuum identity); limb/grazing
geometries θ_o > 60° (different MODTRAN path type, ITYPE 3 — out of scope until
a scenario needs it); other profiles (the >30 km residual column is
profile-insensitive except O₃; revisit only if a validation miss shows it);
**VLWIR extension** (v1 < 700 cm⁻¹, i.e. λ > 14.29 µm — Gap 99): all points of
an interpolation family must share one spectral grid, so a wider range is a
whole-library re-run decision, not an incremental append; elevated targets
from airborne sensors (the h_tgt > 0, h_sensor < 35 km quadrant — a scattered,
non-rectangular grid; deferred until a scenario needs it).

## 3. Execution (owner, MODTRAN license)

1. `python scripts/render_modtran_decks.py` (already done — decks staged in
   `modtran/decks/G7…G11.tp5`, `I1…I9.tp5`, `H5.tp5`, `J1…J2.tp5`).
2. Run the 17 decks through MODTRAN 6; name outputs `<run_id>.tp7`.
3. Drop them in `modtran/real_runs/` alongside the existing 39.

## 4. Follow-up processing (agent, next session after delivery)

All in `scripts/build_atmosphere_library.py` (regenerates `data/atmospheres/`):

1. **Extend the nadir ladder family** — add G7–G11 to the `LADDER` dict
   (sensor 100 km × target 35/40/50/60/80 km). Keep the C-runs (35 km sensor)
   at their existing 0–29 km rungs: the 35 km sensor cannot see higher targets,
   so the family becomes two regular grids or one scattered set — decide at
   build time; prefer splitting a `midlat_summer_boost_ladder/` family
   (sensor {100 km, 40 000 km-duplicate} × target {0,1,5,10,20,29,35,40,50,60,80,100 km})
   and leaving `midlat_summer_ladders/` untouched (no re-baseline of its tests).
2. **Synthesize the exact 100 km vacuum node — in BOTH altitude families**
   *(scope widened 2026-07-19)* — target = 100 km rung with τ ≡ 1,
   L_path ≡ 0 W/m²/sr/µm. This is a physical identity (zero column above the
   top), not fabricated data — and it holds at **every** zenith angle, so the
   off-nadir family gets the rung once per zenith column (0°/45°/60°), not
   just the nadir ladder. Without it the off-nadir hull tops out at 80 km
   while the Gap 95 exo handoff starts at 100 km, and the §6 acceptance sweep
   fails for 80–100 km targets at 45°/60° (2026-07-19 audit finding 1). Label
   as synthesized in the MANIFEST provenance table.
3. **Build the off-nadir family** — `midlat_summer_boost_offnadir/`: regular
   3-D grid target {0,10,29,50,80,**100 (synthesized)** km} × zenith
   {0°,45°,60°} at sensor 100 km (nadir column from A3/G1-derived nodes; 45°
   from I1/G6/I2–I4; 60° from I5–I9), duplicated at 40 000 km for the orbital
   hull. Zenith axis interpolates in airmass sec(θ) space automatically
   (CU-160).
4. **Attach the H5 downwelling to every midlat_summer family** *(added
   2026-07-19)* — `atm_emission_down` = the H5 up-looking 48.2° sky radiance
   [W/m²/sr/µm] on `profiles/midlat_summer.npz`, every `midlat_summer_ladders/`
   node, and every boost/off-nadir node (a target-site hemispheric property,
   independent of viewing geometry for endo targets — same treatment as H2 on
   the us_standard zenith fan). Removes the zero-downwelling load warning from
   the workhorse families.
5. **Build the airborne sensor-ladder family** *(added 2026-07-19)* —
   `midlat_summer_sensor_ladder/`: 1-D `sensor_altitude_m` grid, nodes
   3 (F2) / 10 (J1) / 20 (J2) / 35 (C1) / 100 (A3) km, duplicated at
   40 000 km (vacuum above TOA — same data-only duplication as the ladders),
   ground target, nadir. Closes the airborne-sensor hull for ground-target
   scenarios (audit finding 2). Elevated targets from airborne sensors stay
   out of scope (§2 "deliberately not run").
6. **Record full run geometry per NPZ — all families, existing ones included**
   (CU-167 follow-through; scope made explicit 2026-07-19) — write all five
   geometry fields into each NPZ `geometry` dict (including fields constant
   per family, and including the **regenerated existing families**: profiles,
   zenith fan, ladders, validation points), so the CU-167 mismatch check
   compares against recorded values instead of the assumed-nadir fallback.
   Today the gaps are silent: the fan records no `sensor_altitude_m` (an
   airborne query is served the 100 km column without warning) and no shipped
   NPZ records `solar_zenith_rad` (every down-looking run used θ_s = 30°; a
   VIS/NIR query at any other sun angle silently gets 30°-sun path radiance —
   audit finding 3).
7. **Wire the new families into the out-of-the-box default** *(added
   2026-07-19)* — extend `atmosphere/loaders.py::_SHIPPED_FAMILY_BY_AXES` with
   `"sensor_altitude_m"` → `midlat_summer_sensor_ladder` and
   `"sensor_altitude_m,target_altitude_m,path_zenith_rad"` →
   `midlat_summer_boost_offnadir`, with tests; otherwise the §6 "single
   scenario config" criterion needs an explicit `interpolated_data_dir` and
   fails as written. Doc lock-step: `RADIANT_Atmosphere.md` §3.2 default-family
   list (Rule 20).
8. Update `data/atmospheres/MANIFEST.md` (family tables, provenance, the
   synthesized-node note) and `data/atmospheres/README.md` in the same PR
   (Rule 26 manifest discipline; Rule 20 lock-step).

## 5. Integration & validation (same PR as §4)

- **Golden extension** — `tests/integration/test_shipped_atmosphere_library.py`:
  a `TestBoostLadder` class pinning band-mean τ(8–13 µm) and τ(3.5–5 µm) at
  the new rungs (values extracted at build time from the slit-degraded NPZs,
  same protocol as the existing G3 anchor), plus monotonicity τ(h₁) < τ(h₂)
  for h₁ < h₂ across 0–100 km, plus continuity at the Gap 95 handoff:
  interpolated τ_up(→100 km) → 1 meets the vacuum branch's exact 1.0.
- **Band-core check (the reason these runs exist)** — a Level-2 test asserting
  the 4.20–4.45 µm CO₂ band-mean τ at H2 = 50 km is materially below 1
  (threshold from the delivered run; expected ≈ 0.5–0.8) — guards against a
  future "optimization" replacing the rungs with vacuum interpolation.
- **Off-nadir consistency** — I-block 45° column vs CU-160 airmass prediction
  from the 0°/60° nodes (the B-fan holdout methodology, now at altitude).
- **Chain smoke** — the Gap 95 integration test
  (`tests/integration/test_exo_target_chain.py`) gains a mid-boost case
  (h_tgt = 50 km) once the boost family ships; expected: runs with real τ_up
  between the 29 km and vacuum values.
- **H5 downwelling parity** *(added 2026-07-19)* — π·L_sky(48.2°) reproduces
  the hemispheric downwelling flux to the same ~15% envelope the H2/us_standard
  anchor holds (`test_modtran_real_runs.py` pattern); band-mean
  `atm_emission_down` golden pinned on the regenerated
  `profiles/midlat_summer.npz`.
- **Sensor-ladder physics** *(added 2026-07-19)* — monotonicity
  τ(h_sensor = 3 km) < τ(10 km) < τ(20 km) < τ(35 km) < τ(100 km) for a ground
  target (band-mean, 8–13 µm and 3.5–5 µm), plus a hull check that a 500 km
  LEO query lands on the duplicated node exactly.
- **CU-096 re-audit at landing** *(added 2026-07-19)* — the off-nadir family
  makes θ_o ≠ 0 a first-class shipped geometry, which is exactly where the
  open CU-096 residue (atmosphere reads `path_zenith_rad` as target-side θ_o;
  platform/performance legacy fallbacks read it as sensor-side η, up to ~8°
  apart at LEO) starts to matter. The landing PR re-audits CU-096 per its
  deferral record rather than silently carrying it across this stage landing
  (Rule 22).
- **Registry closeout** — Gap 95's 29–100 km data remainder closes against the
  library-build commit; the run matrix rows flip from plan to delivered in
  `modtran/decks/MANIFEST.md` automatically on re-render.

## 6. Acceptance criteria

1. A single scenario config can sweep `geometry.target_altitude_m` from 0 m to
   300 km with `atmosphere.model = "interpolated"` and produce physically
   monotone τ_up (decreasing path absorption with altitude, τ_up = 1.000 above
   100 km) with no errors and no CU-167 warnings at any swept zenith ≤ 60° —
   including the 80–100 km band at 45°/60°, served by the per-zenith
   synthesized vacuum rung (§4.2, 2026-07-19 amendment), with continuity into
   the exo branch's exact 1.000 at the handoff.
2. *(added 2026-07-19)* A ground-target scenario can sweep
   `geometry.sensor_altitude_m` from 3 km to 500 km on
   `atmosphere.model = "interpolated"` with `interpolation_axes =
   "sensor_altitude_m"` and **no** `interpolated_data_dir` set (shipped-default
   wiring, §4.7), producing monotone increasing band-mean τ with sensor
   altitude and no CU-167 warnings.
3. *(added 2026-07-19)* Every midlat_summer family node loads with non-zero
   `atm_emission_down` (H5-derived, W/m²/sr/µm); the zero-downwelling warning
   no longer fires on the ladders, boost, off-nadir, or profile loads.
4. All Category C/D validation sections for the new families (truth anchors
   from the delivered tape7s; dimensional audit unchanged — same units as
   existing families) reported in the landing PR.
5. CHANGELOG entry (capability addition) + Gap 95 data-remainder closure with
   commit SHA (Rule 22 protocol applied to the gap registry).
