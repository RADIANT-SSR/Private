# Scenario 8.2 — Target-Altitude Interpolation

**New addition, not part of the original 35-scenario catalog** — see
`scenarios/08_interpolation_demonstrations/README.md`.

**Question:** A stratospheric-sensor mission needs atmosphere data for a
target at 15 km — not one of the run matrix's altitude-ladder points
(`altitude_ladder_stratospheric`: 0, 1, 5, 10, 20, 29 km, all
`midlat_summer`/35 km-sensor/nadir). Same interpolation method as 8.1
(`family_interpolate.py`), a different axis type (altitude, not angle),
to show the tool generalizes.

**Status: pipeline/method demonstration.** Atmosphere data is
*synthetic* (see `modtran/synthetic/README.md`).

---

## Results (8–12 µm LWIR)

| Target altitude | In-band transmittance |
|---|---|
| 0 km | 0.5774 |
| 1 km | 0.7039 |
| 5 km | 0.8822 |
| 10 km | 0.9151 |
| 15 km, **interpolated** | **0.9291** |
| 20 km | 0.9447 |
| 29 km | 0.9790 |

- **Naive nearest-neighbor (20 km) transmittance error vs. interpolated:
  +1.7%** — the ladder's spacing is uneven and coarse right where the
  query falls (10→20 km is a 10 km gap, the widest in the ladder), so the
  nearest matrix point (20 km) still misses the true 15 km transmittance —
  exactly the situation where nearest-neighbor selection is weakest and
  interpolation earns its keep.
- **Full-chain SNR error: +0.7%.** Smaller than the transmittance error
  for the same reason as scenario 6.2 found — SNR depends on the
  extended-scene target/background contrast, which partially cancels
  atmosphere effects that are common to both terms.

*τ ladder re-verified 2026-08-02 against the unmodified runner under the CU-321
sweep: every value above is bit-identical (CU-321 changes emission altitude, not
optical depth). This scenario's GUI baseline **did** move — SNR 1730.9 → 1658.8,
NEDT 0.02500 → 0.02624 — because the `.gui.yaml` payload runs the `simple`
model, where the height-resolved path-thermal emission applies. The +0.7 % SNR
error above is a ratio between two interpolated-atmosphere runs and could not be
re-verified in this sweep: the runner's chain half needs the generated synthetic
MODTRAN set, which is absent on a clean tree (the fresh-clone dependency logged
at CU-317 closure). It is carried forward unchanged, not re-measured.*

---

## Physics / modeling notes

- **The ladder is non-uniformly spaced** (1, 4, 5, 10, 9 km gaps) — a
  deliberate matrix design choice (denser sampling near the ground
  where transmittance changes fastest with altitude, sparser aloft
  where it's flattening out — visible in `fig1`'s concave shape). This
  scenario's 15 km query happens to fall in the widest gap, which is
  the most informative place to demonstrate interpolation's value.
- **Same log-transmittance-linear method as 8.1** — see that
  scenario's walkthrough for the Beer-Lambert justification. The
  method doesn't care whether the free axis is an angle or an
  altitude; it only needs monotonic-in-optical-depth behavior along
  that axis, which both zenith angle (via airmass) and target altitude
  (via column length) satisfy.

---

## Friction / lessons (mirrors 6.2's exactly)

- **Full-well saturation again silently zeroed the atmosphere effect
  on SNR on the first attempt** (`well_status: clipped`,
  `signal_e_final` pinned at the full-well ceiling for both 15 km and
  20 km, giving bit-identical SNR). Fixed by reducing integration time
  20×. This is now the *third* scenario (6.1, 6.2, 8.2) to hit this
  exact failure mode — see gaps.md for a proposed standing fix.

---

## Gaps Identified

See `gaps.md`.
