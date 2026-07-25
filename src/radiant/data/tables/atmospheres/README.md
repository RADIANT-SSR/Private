# Atmosphere Data

This directory ships RADIANT's **nominal atmosphere library**: NPZ
spectra derived from a real MODTRAN 6 run matrix (2026-07-17), packaged
for the `tabulated` and `interpolated` atmosphere models so users
without a MODTRAN license get real-radiative-transfer atmospheres out
of the box.

See [`MANIFEST.md`](MANIFEST.md) for the full design record: family
tables, run provenance, spectral degradation, packaging decisions, and
known limitations. Generator: `scripts/build_atmosphere_library.py`
(requires the gitignored `modtran/real_runs/` staging set).

## What ships

| Family | Model | Contents |
|--------|-------|----------|
| `profiles/` | `tabulated` | Six standard atmospheres, nadir full column (us_standard, tropical, midlat_summer include real downwelling sky radiance) |
| `us_standard_zenith_fan/` | `interpolated` | LOS zenith 0–60° fan |
| `midlat_summer_ladders/` | `interpolated` | Sensor (35 km–GEO) × target altitude (0–29 km) grid |
| `midlat_summer_boost_ladder/` | `interpolated` | Space sensor × target altitude 0–100 km (missile boost; synthesized vacuum rung at 100 km) |
| `midlat_summer_boost_offnadir/` | `interpolated` | Space sensor × target 0–100 km × LOS zenith 0/45/60° (off-nadir boost tracking) |
| `midlat_summer_sensor_ladder/` | `interpolated` | Airborne→space sensor (3 km–GEO), ground target |
| `validation/` | point data | Off-grid 45° and up-looking anchors |

Example (shipped profile through the chain):

```yaml
atmosphere:
  model: tabulated
  tabulated_transmittance_file: data/atmospheres/profiles/us_standard.npz
  tabulated_path_radiance_file: data/atmospheres/profiles/us_standard.npz
```

## What deliberately does not ship

- **Aerosol/visibility variants** (run-matrix Blocks D/E) — condition-
  specific studies, regenerate-on-demand.
- **Full-resolution (1 cm⁻¹) spectra** — the library is slit-degraded to
  5 cm⁻¹ FWHM (band-integrating metrics are insensitive; keeps the
  library ~4 MB). Full-resolution data lives in the committed test
  fixtures (`tests/integration/fixtures/`, plan §7.1) and the local
  staging set.
- **Every-geometry pre-tabulation** — arbitrary geometries remain the
  job of the analytic `simple` model or a user's own MODTRAN runs via
  `atmosphere.modtran.tape7_path`.

*(Historical note: this README previously said pre-tabulation "would
require thousands of files". That predated `InterpolatedAtmosphere`'s
log-τ structured-grid interpolation, which is what makes the small
node set above useful — see `RADIANT_Atmosphere.md` §3.)*
