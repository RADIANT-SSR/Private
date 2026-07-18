# MODTRAN Boost-Ladder Expansion Plan — targets to 100 km + off-nadir grid

Status: Active
Owner trigger: 2026-07-18 — missile-defense boost-phase application (detect from
launch through burnout from a space sensor); follows the Gap 95 owner review.
Scope ratified in-conversation 2026-07-18 ("append the new runs to the existing
run_matrix … capture both the additional runs and the followup processing and
integration").

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

## 2. New runs (appended to `docs/plans/modtran_run_matrix.csv`, 2026-07-18)

All midlat_summer, rural/23 km vis (irrelevant above ~30 km), IEMSCT=2,
700–25000 cm⁻¹ @ 1 cm⁻¹, H1 = 100 km (space column), destination
`shipped_library`. Decks are rendered (53 total now) — regenerate anytime with
`python scripts/render_modtran_decks.py`.

| Runs | Geometry | Purpose |
|------|----------|---------|
| G7–G11 | H2 = 35/40/50/60/80 km, nadir | Boost ladder: closes 29–100 km. Node spacing ≈ 1–1.5 pressure scale heights so log-τ interpolation between rungs is well-conditioned |
| I1–I4 | H2 = 0/29/50/80 km at 45° LOS zenith | Off-nadir boost grid (45° column; G6 already supplies 10 km @ 45°) |
| I5–I9 | H2 = 0/10/29/50/80 km at 60° LOS zenith | Off-nadir boost grid (60° column, airmass = 2 anchor) |

Total: 14 new MODTRAN runs. The MODTRAN ANGLE convention caveat (CU-065:
`ANGLE` at H1 = 180° − LOS zenith for down-looking paths) applies — verify on
the first I-block run before trusting the batch, exactly as the B-fan was
verified.

**Deliberately not run**: any H2 ≥ 100 km (vacuum identity); limb/grazing
geometries θ_o > 60° (different MODTRAN path type, ITYPE 3 — out of scope until
a scenario needs it); other profiles (the >30 km residual column is
profile-insensitive except O₃; revisit only if a validation miss shows it).

## 3. Execution (owner, MODTRAN license)

1. `python scripts/render_modtran_decks.py` (already done — decks staged in
   `modtran/decks/G7…G11.tp5`, `I1…I9.tp5`).
2. Run the 14 decks through MODTRAN 6; name outputs `<run_id>.tp7`.
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
2. **Synthesize the exact 100 km vacuum node** — target = 100 km rung with
   τ ≡ 1, L_path ≡ 0. This is a physical identity (zero column above the top),
   not fabricated data; label it as synthesized in the MANIFEST provenance
   table. It closes the interpolation hull to the Gap 95 handoff altitude so
   τ_up is continuous from 0 km to space.
3. **Build the off-nadir family** — `midlat_summer_boost_offnadir/`: regular
   3-D grid target {0,10,29,50,80 km} × zenith {0°,45°,60°} at sensor 100 km
   (nadir column from A3/G1-derived nodes; 45° from I1/G6/I2–I4; 60° from
   I5–I9), duplicated at 40 000 km for the orbital hull. Zenith axis
   interpolates in airmass sec(θ) space automatically (CU-160).
4. **Record full run geometry per NPZ** (CU-167 follow-through) — write all
   five geometry fields into each NPZ `geometry` dict (including the fields
   that are constant per family), so the CU-167 mismatch check compares against
   recorded values instead of the assumed-nadir fallback.
5. Update `data/atmospheres/MANIFEST.md` (family tables, provenance, the
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
- **Registry closeout** — Gap 95's 29–100 km data remainder closes against the
  library-build commit; the run matrix rows flip from plan to delivered in
  `modtran/decks/MANIFEST.md` automatically on re-render.

## 6. Acceptance criteria

1. A single scenario config can sweep `geometry.target_altitude_m` from 0 m to
   300 km with `atmosphere.model = "interpolated"` and produce physically
   monotone τ_up (decreasing path absorption with altitude, τ_up = 1.000 above
   100 km) with no errors and no CU-167 warnings at any swept zenith ≤ 60°.
2. All Category C/D validation sections for the new families (truth anchors
   from the delivered tape7s; dimensional audit unchanged — same units as
   existing families) reported in the landing PR.
3. CHANGELOG entry (capability addition) + Gap 95 data-remainder closure with
   commit SHA (Rule 22 protocol applied to the gap registry).
