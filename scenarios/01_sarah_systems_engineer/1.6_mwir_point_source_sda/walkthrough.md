# 1.6 — MWIR Point-Source SDA (Space Domain Awareness)

**Status:** Active · **Persona:** Sarah (systems engineer) · **Regime:** point_source

## The problem

A space-based MWIR sensor (700 km LEO) must detect an **unresolved** satellite —
a *point source*. At a 729 km slant range with a 0.30 m aperture, the target's
angular extent is far below one pixel IFOV, so it lands within a single PSF: there
is no "surface" filling a pixel. The right radiometric quantity is the target's
**radiant intensity** `I(λ)` [W/sr/µm], not a surface radiance × area.

This is the space-domain-awareness / star-tracker case: you know (or model) the
object's intensity, and you ask *"what SNR do I get, and out to what range can I
detect it?"*

## Why intensity, not radiance

Radiance `L` [W/m²/sr/µm] is a property of a *resolved surface*. A true point
source subtends ≈ zero solid angle, so its radiance is undefined (it would be
`I / (A·Ω)` with `A → 0`). What is well-defined and measurable is:

- **radiant intensity** `I(λ)` [W/sr/µm], and
- the **irradiance at the aperture** `E(λ) = I(λ) / R²` [W/m²/µm].

The at-pixel signal is `S ∝ I/R² · A_collect · τ_atm · QE · t_int` — linear in
`I`, inverse-square in range. Defining this target with a blackbody *radiance* and
zeroing the area does **not** describe a point source (it raises an error — see
gaps.md / Gap 98).

## How this scenario defines the target (the workflow)

The satellite's MWIR self-emission is modeled as a graybody point source:

```
I(λ) = ε · A_emit · B(λ, T),   ε = 0.85,  A_emit = 8 m²,  T = 290 K
```

supplied through the **blackbody point-intensity** inputs (no hand-authored CSV):

```yaml
source:
  scene_type: point_source
  regime_override: point_source
  target:
    point_intensity_temperature_K: 290.0
    point_intensity_area_m2: 8.0        # emitting area — scales I, does NOT size a pixel
    point_intensity_emissivity: 0.85
geometry:
  target_range_m: 729287.0              # explicit — point_source reads range from here
```

Three interchangeable ways exist to give `I(λ)` (all → `T7IntensityAtSource`):
| Input | When |
|---|---|
| `point_intensity_temperature_K` + `_area_m2` (+ `_emissivity`) | thermal object, you know T and size (**this scenario**) |
| `point_intensity_band_W_per_sr` | you know only the in-band flux `∫I dλ` [W/sr] (modeled flat over the band) |
| `user_intensity_path` (CSV) | you own the full spectrum |

## Results

Run `scripts/run_point_source_sda.py` (or `Sensor.from_yaml(...).evaluate()`):

| Metric | Value | Units |
|---|---|---|
| Regime | point_source | — |
| Signal | 21,229 | e⁻ |
| **SNR** | **25.8** | — |
| **Detection range** (SNR = 6) | **1522** | km |
| Sampling Q (band center) | 1.42 | — |

*(Refreshed 2026-08-01. The **detection range** moved 1,199 → 1,522 km in this
refresh: CU-263 made the criterion shot-consistent and routed the down-looking
arm through the path-aware solver, whose receding leg from a 700 km sensor is
exact vacuum. The **signal and SNR** columns were already stale against `main`
before that change — 24,345 e⁻ / 30.5 against the 21,229 e⁻ / 25.8 the runner
produces today — and are corrected here rather than left mixed; that drift comes
from earlier landed work, not from CU-263.)*

Sanity: signal scales **linearly** with `point_intensity_area_m2`, `_emissivity`,
and `I` (2× intensity → 2× signal), and inverse-square with range — the
point-source camera equation. The blackbody input reproduces an equivalent
hand-built intensity CSV **exactly**.

## Gotchas (see gaps.md → Gap 98)

- The `point_source` signal reads the range from `geometry.target_range_m`
  **explicitly** — it does not fall back to the range derived from
  altitude + zenith, so this scenario sets it.
- Leaving surface-radiance params (`temperature`/`emissivity`) set in
  `point_source` regime with zero area does **not** define a point source — it
  raises `point_source regime requires projected_area_m2` (an error that steers
  toward area, not intensity). Use the intensity inputs above.
- The GUI does not yet expose the point-intensity inputs.
