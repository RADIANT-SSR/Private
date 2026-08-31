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
| Signal | 20,931 | e⁻ |
| **SNR** | **20.31** | — |
| **Detection range** (SNR = 6) | **1346.5** | km |
| Sampling Q (band center) | 1.42 | — |

*(Refreshed 2026-08-30. One mover: **CU-335** re-fitted the calibrated gas
table's VIS/NIR/SWIR rows against the post-CU-253 Rayleigh. This is a 3–5 µm
scene, so the reach is the λ⁻⁴ tail in the 2.40–5.00 µm floors (≤ 0.001 OD):
signal 20,933 → 20,931 e⁻, range 1,346.6 → 1,346.5 km, SNR unmoved at the
quoted precision. Under one part in ten thousand.)*

*(Prior refresh, 2026-08-29. Two components, and only the smaller one is CU-324's.
**Pre-existing drift — attributed by the CU-334 bisect (2026-08-29) to CU-321,
commit `6cf6eaa9`, landed 2026-08-03:** this table read SNR 17.67 / range
1,254.7 km, but the unmodified runner on the pre-CU-324 tree gave 20.35 /
1,347.8 km. CU-321 made the atmosphere's own thermal emission height- and
wavelength-resolved, so this down-looking MWIR column no longer emits at its
near-surface endpoint temperature: the band-mean path radiance falls
0.4806 → 0.2545 W/m²/sr/µm, and the emission temperature inverted from
`L_path = (1 − τ)·B(λ, T_eff)` goes 292.9 → 277.4 K at 4.0 µm — and stops being
spectrally flat (277.4 K at 4.0 µm vs 276.8 K at 4.5 µm, where before both read
292.9 K). Nothing else in the scene moves: τ is identical to 13 significant
figures, the declared point intensity is untouched, and `background_shot`
(1,171.9 → 1,014.1 e⁻) is the only noise term that changes — so SNR rises
+15.2 % and the detection range +7.4 %. That is the intended direction of the
CU-321 fix; the same mechanism raises scenario 10.1's SNR 130.1 → 144.6, which
CU-321 did record. 1.6 was missed by its refresh sweep because it is the one
moved scenario with no `gui.expected.json` baseline for that sweep to key on.
The signal column was unchanged throughout that bisect. **CU-324:** `E_sky_thermal`'s
flux-diffusivity exponent became the geometric `sec 48.2° = 1.50030` instead of
the CU-155 fitted `D = 1.1`, which raises the sky background this space-to-space
MWIR geometry sees and so lowers SNR a shade — 20.35 → 20.31, range 1,347.8 →
1,346.6 km. The target term is a declared point intensity and does not move at
all; the entire CU-324 effect here is on the background. The signal column read
20,933 e⁻ throughout that refresh.)*

*(Prior refresh, 2026-08-02, superseding the 2026-08-01 CU-263 refresh below. The
dominant mover is **CU-224**: a down-looking column now carries its own thermal
emission, which this MWIR space-to-space geometry sees as extra background —
the target signal is essentially unmoved (21,229 → 20,933 e⁻, the remaining
−1.4 % being **CU-267**'s −0.71 % band-mean τ on 3–5 µm, which landed the same
day as the previous refresh) while the noise floor rises, so SNR falls
25.8 → 17.67 and the detection range shortens 1,522 → 1,254.7 km. CU-263 made
detection ranges longer; CU-224 raises the floor they are measured against, and
here the second effect is the larger.)*

*(Prior refresh, 2026-08-01: the **detection range** moved 1,199 → 1,522 km
because CU-263 made the criterion shot-consistent and routed the down-looking
arm through the path-aware solver, whose receding leg from a 700 km sensor is
exact vacuum. The **signal and SNR** columns had been stale against `main` even
before that — 24,345 e⁻ / 30.5 — and were corrected in the same pass.)*

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
