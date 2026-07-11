# Scenario 8.1 — Off-Nadir Angle Interpolation

**New addition, not part of the original 35-scenario catalog** — see
`scenarios/08_interpolation_demonstrations/README.md` for why this
folder exists outside the persona-catalog numbering.

**Question:** A customer requirement lands at 37.5° off-nadir — not one
of the MODTRAN run matrix's zenith-fan points (0°, 30°, 45°, 60°, all
`us_standard`/100 km sensor/nadir target). Does interpolating between
the two bracketing runs actually beat just grabbing the nearest one?

**Status: pipeline/method demonstration.** Atmosphere data is
*synthetic* (see `modtran/synthetic/README.md`). This scenario
demonstrates the *interpolation method* — log-transmittance-linear
between bracketing runs, `scripts/synth_modtran/family_interpolate.py`
— which is independent of whether the underlying data is real or
synthetic; the absolute numbers are illustrative only.

---

## How RADIANT (well, this scenario's tooling) solves this

1. `interpolate_family("zenith_fan_us_standard", 37.5)` locates the
   bracketing runs (B1=30°, B2=45°), interpolates
   `log(transmittance)` linearly in zenith angle (Beer-Lambert-
   consistent — matches `InterpolatedAtmosphere`'s own convention),
   and linearly interpolates path radiance.
2. For comparison, "naive nearest-neighbor" — an operator who just
   grabs the closer matrix point (45°, since 37.5° is nominally
   equidistant... **note**: 37.5 is exactly the midpoint of 30/45; the
   tie-break in this script's comparison logic picks 45° — see
   gaps.md) — reuses that run's atmosphere data unmodified.
3. Both atmosphere sources are fed through the identical chain
   config, evaluated at the *actual* query geometry (37.5°
   `path_zenith_rad`), isolating the atmosphere-data-source effect.

---

## Results

| Geometry | In-band transmittance | Chain SNR |
|----------|------------------------|-----------|
| 30° (B1, exact) | 0.7037 | — |
| 45° (B2, exact) | 0.6873 | — |
| 37.5°, interpolated | 0.6952 | 641.4 |
| 37.5°, naive nearest-neighbor (45°) | 0.6873 | 636.2 |

- **The interpolated point sits correctly between the two bracketing
  values and on the expected monotonic curve** (`fig1`) — a good
  visual sanity check that the log-space interpolation is behaving.
- **Nearest-neighbor error at this query point is modest but real**:
  −1.1% transmittance, −0.8% SNR. At 37.5° (near the family's
  midpoint), the error is close to the family's worst case for this
  10–15°-spaced grid; a query closer to one bracketing point would
  show a *smaller* nearest-neighbor error, and a coarser family
  (larger angle spacing) would show a larger one.

---

## Physics / modeling notes

- **Why log-transmittance, not linear transmittance?** Beer-Lambert
  gives τ = exp(−σ·path), so σ·path (optical depth) is what varies
  linearly with the physical quantity changing (here, airmass via
  1/cos θ) — interpolating in log-τ space respects that; interpolating
  raw τ linearly would not (and would be wrong in the same way linear-
  interpolating a decaying exponential is always wrong).
- **This is a 1-D interpolation problem by design** — the family holds
  every other geometry axis fixed. A genuinely multi-axis query (e.g.
  a new profile *and* a new angle simultaneously) is out of scope for
  this lightweight tool; that's what `InterpolatedAtmosphere`
  (general N-D) exists for, and why this repo has both.

---

## Gaps Identified

See `gaps.md`.
