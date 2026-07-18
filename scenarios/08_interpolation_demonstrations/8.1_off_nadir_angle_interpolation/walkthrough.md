# Scenario 8.1 — Off-Nadir Angle Interpolation

**New addition, not part of the original 35-scenario catalog** — see
`scenarios/08_interpolation_demonstrations/README.md` for why this
folder exists outside the persona-catalog numbering.

**Question:** A customer requirement lands at 37.5° off-nadir — not one
of the MODTRAN run matrix's zenith-fan points (0°, 30°, 45°, 60°, all
`us_standard`/100 km sensor/nadir target). Does interpolating between
the two bracketing runs actually beat just grabbing the nearest one?

**Status: validated method demonstration (upgraded 2026-07-17).**
Atmosphere data is the **real MODTRAN 6 zenith fan** (A1/B1/B2/B3 of
the 2026-07-17 run set; `family_interpolate` auto-detects the staged
`modtran/real_runs/` and falls back to synthetic with a loud banner).
The upgrade adds something the synthetic era could not: a **holdout
validation** — predict the 45° run from its 30°/60° neighbors and
compare against the real 45° run, a ground-truth test of the
interpolation method itself.

---

## How RADIANT (well, this scenario's tooling) solves this

1. `interpolate_family("zenith_fan_us_standard", 37.5)` locates the
   bracketing runs (B1=30°, B2=45°), interpolates
   `log(transmittance)` linearly in **airmass sec θ** (Beer-Lambert-
   exact — CU-160; matches `InterpolatedAtmosphere`'s convention),
   and linearly interpolates path radiance on the same axis.
2. For comparison, "naive nearest-neighbor" — an operator who just
   grabs the closer matrix point (45°, since 37.5° is nominally
   equidistant... **note**: 37.5 is exactly the midpoint of 30/45; the
   tie-break in this script's comparison logic picks 45° — see
   gaps.md) — reuses that run's atmosphere data unmodified.
3. Both atmosphere sources are fed through the identical chain
   config, evaluated at the *actual* query geometry (37.5°
   `path_zenith_rad`), isolating the atmosphere-data-source effect.

---

## Holdout validation (real data): predict 45° from 30° + 60°

| Predictor of the real 45° run | In-band τ (3.5–5.0 µm) [-] | Error |
|---|---|---|
| Real B2 (truth) | 0.4988 | — |
| Log-τ, linear **in angle** (pre-CU-160) | 0.4785 | −4.07% |
| Log-τ, linear **in airmass sec θ** (**the method — CU-160 landed**) | 0.4983 | **−0.10%** |
| Nearest-neighbor (30°) | 0.5329 | +6.84% |

- **The method beats nearest-neighbor ~1.7×** against ground truth —
  the scenario's original claim, now validated on real MODTRAN.
- **The −4% angle-axis residual had a knowable cause and a 40× fix,
  which has now landed (CU-160)**: optical depth scales with *airmass*
  (sec θ), not angle. Both `family_interpolate` and
  `InterpolatedAtmosphere` (and therefore the shipped
  `data/atmospheres/us_standard_zenith_fan/`) now interpolate zenith
  axes in sec θ space — the holdout row above is the acceptance
  evidence, and `test_shipped_atmosphere_library.py` pins it on the
  committed library.

---

## Results (real MODTRAN 6, 2026-07-17)

| Geometry | In-band transmittance [-] | Chain SNR [-] |
|----------|---------------------------|---------------|
| 30° (B1, exact) | 0.5329 | — |
| 45° (B2, exact) | 0.4988 | — |
| 37.5°, interpolated (airmass axis, CU-160) | 0.5185 | 556.2 |
| 37.5°, naive nearest-neighbor (45°) | 0.4988 | 545.7 |

- **The interpolated point sits correctly between the two bracketing
  values and on the expected monotonic curve** (`fig1`).
- **Nearest-neighbor error at this query point**: −3.8% transmittance,
  −1.9% SNR — roughly 3× larger than the synthetic-era numbers
  suggested (real MODTRAN's angle dependence in this band is stronger
  than the synthetic generator's). At 37.5° (near the family's
  midpoint) this is close to the worst case for a 15°-spaced grid.

---

## Physics / modeling notes

- **Why log-transmittance, not linear transmittance?** Beer-Lambert
  gives τ = exp(−σ·path), so σ·path (optical depth) is what varies
  linearly with the physical quantity changing (here, airmass via
  1/cos θ) — interpolating in log-τ space respects that; interpolating
  raw τ linearly would not.
- **And why the axis is airmass, not angle (CU-160, landed):** the
  holdout table above is the empirical demonstration — same log-τ
  machinery, correct physical axis, 40× smaller error. The change was
  a coordinate transform, not new data.
- **This is a 1-D interpolation problem by design** — the family holds
  every other geometry axis fixed. A genuinely multi-axis query (e.g.
  a new profile *and* a new angle simultaneously) is out of scope for
  this lightweight tool; that's what `InterpolatedAtmosphere`
  (general N-D) exists for, and why this repo has both.

---

## Gaps Identified

See `gaps.md` — the angle-vs-airmass axis finding (CU-160, since
landed) is the headline addition from the real-data upgrade.
