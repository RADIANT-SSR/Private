# Scenario 1.2 — Gaps and Friction

Issues encountered building/running the VNIR GSD-trade scenario. Registry
items are mirrored into `docs/tracking/gaps.md` (capability gaps) and
`docs/tracking/Cleanup_Backlog.md` (CUs) per the workflow rules.

---

## RESOLVED during this scenario

### Solar-geometry calculator (was the primary gap)
The catalog flagged "no solar-geometry calculator (LTAN/date/latitude →
solar zenith)". **Built as `radiant.core.solar_geometry`** (committed
00efcc5): `solar_zenith_angle_rad`, `solar_declination_deg` (Spencer's
series), `local_solar_time_from_ltan`. 12 Level-0 tests, 3 hand truth
anchors. Lives in `core/` as pure kinematics alongside
`slant_range_spherical_m`. This scenario is its first consumer.

---

## Framework gaps (mirrored to docs/tracking/gaps.md)

### Gap — no diffraction-limited-resolution metric in `result.metrics`
The Rayleigh ground spot `1.22 λ (f/#) → 1.22 λ altitude / D` is the
optics-only resolution floor and the natural companion to
`gsd_geometric_mean_m`. The script computes it locally
(`diffraction_limited_gsd_m`), but a designer comparing optics-limited vs
detector-limited resolution should get it from the result object. **The
data exists** (aperture, focal, wavelength all in the chain) — this is a
surfacing gap, not a physics gap.

### Gap — no explicit detector-vs-diffraction-limited regime flag
`q_center` is already a metric, and the detector/diffraction-limited call
is a threshold on it (`Q < 1` detector-limited, `Q ≳ 2`
diffraction-limited). A boolean/enum metric (`sampling_regime`) would make
the crossover a first-class output rather than something each script
re-derives. Low effort; pairs with the diffraction-GSD metric above.

### Note (not a gap) — contour plotting is scenario-level
The catalog listed "no contour plot with overlaid constraint lines". This
is correct but by design: RADIANT's `result.plot` namespace covers
single-run diagnostics (MTF, PSF, spectra); multi-run trade contours
(SNR over an aperture × altitude grid) are analysis artifacts the scenario
script owns via matplotlib. No framework change proposed.

---

## Friction / lessons

- **`QeCurve` band-average method is `band_averaged_qe`, not
  `band_average`.** Minor naming friction; the `_qe` suffix disambiguates
  from a future `band_averaged_transmission`. No change needed, noted for
  the next scenario author.
- **MTF-at-Nyquist = 0 UserWarnings** flood the console at small apertures
  (high f/#, oversampled). These are *correct* physics warnings (the
  detector out-samples the optical cutoff), not errors — but a 13×11 grid
  emits ~25 of them. A designer running a sweep wants the aggregate, not
  one warning per cell. Possible enhancement: a sweep-level warning
  dedup/summary. Low priority; the warnings are individually correct.
