# Scenario 8.3 — Gaps and Friction

---

## OPEN

### 29–100 km target-altitude band has no shipped atmosphere data
**Severity:** High for this scenario (it is the whole reason 8.3 is a *skeleton*)
**Status:** Tracked — `docs/tracking/gaps.md` **Gap 95** (data remainder) and
`docs/plans/MODTRAN_Boost_Ladder_Expansion_Plan.md` (the delivery plan). Gated on
**MODTRAN access** (the run set is not yet delivered).
**Description:** the shipped `midlat_summer_ladders` interpolation family covers
target altitudes 0–29 km (C/G runs). A booster mid-boost sits in the 29–100 km
band, which is above the ladder ceiling but below the 100 km atmosphere top, so
neither the interpolator nor the Gap 95 vacuum leg serves it — the interpolator
raises `AtmosphereValidationError: … outside the available range [0, 29000]`.
**Workaround used:** the runner catches that specific refusal and reports the
rung as **PENDING** (it does not fabricate or vacuum-extrapolate a value). The
0–29 km and ≥ 100 km bands run and validate today.
**Resolution path:** the boost-ladder run set (G7–G11 nadir + I1–I9 off-nadir)
closes the band; when it lands and the library is rebuilt (plan §4), the PENDING
rungs fill in with no change to this script. **Not started here** — library
rebuild is gated on delivered tape7s.

### Nadir only — off-nadir boost tracking not yet exercised
**Severity:** Low (skeleton scope)
**Status:** Tracked — the off-nadir grid (45°/60° LOS zenith) is the I-run
remainder of the boost-ladder plan.
**Description:** boost-phase tracking from LEO is rarely nadir, but the shipped
ladders are nadir-only, and CU-167 correctly warns (and this scenario would trip)
if a non-nadir LOS were queried against a nadir-only family. This skeleton stays
at `path_zenith_rad = 0` so it runs clean; the off-nadir sweep waits on the
I-runs.

---

## Known / expected (not faults)

- **The `midlat_summer_ladders` ship without a downwelling column** (no matching
  MODTRAN H-run for midlat_summer — documented in
  `data/atmospheres/MANIFEST.md`), so the chain notes `no 'atm_emission_down'
  key … defaulting to zeros`. Immaterial here: a 900 K plume's reflected-sky
  term is negligible against its own emission. The runner filters this expected
  notice.
- **The interpolated backend collapses the Option-C sun-leg split**
  (`τ_sun = τ_up`) on every evaluate (CU-011-class) — a documented backend
  limitation that does not affect this self-luminous target's SNR. Also filtered.

---

## Friction / lessons

See `walkthrough.md`'s "Friction / lessons" — the full-well saturation envelope
(clipping appears at the *closest* rung, not the launch rung) is the reusable
lesson for altitude/range sweeps of a bright target.
