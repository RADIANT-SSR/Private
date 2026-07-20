# Solar Irradiance Library — Manifest

**Status:** approximate reference — a smooth continuum fit, **not** a
spectrally-resolved measured standard.

## `solar_irradiance_am0.csv`

Top-of-atmosphere (AM0) spectral solar irradiance, `E(λ)` in W/m²/µm, on a
0.2–~5 µm wavelength grid (140 points). Used as the default extraterrestrial
solar spectrum for the reflective-solar source path.

**Provenance (CU-080):** this curve is a **Planck-continuum approximation** of the
AM0 solar spectrum, characterised in the 2026-07 data-provenance audit as validated
**only against total solar irradiance** (the integrated value agrees with the solar
constant to ±5%). It is a smooth continuum — it carries **no Fraunhofer absorption
lines** and is not the spectrally-resolved AM0 standard (e.g. ASTM E490 / Gueymard).

## Known limitations

- **Band-integrated use only.** Because it is validated on integrated irradiance,
  it is suitable for band-averaged reflective-solar signal estimates, not for
  narrow-band work that depends on solar line structure.
- **Do not compare line-by-line** against measured AM0 data — the deviations are
  expected (the continuum has no absorption features).
- **Replace-or-cite.** To make this traceable, replace it with a cited
  spectrally-resolved standard (ASTM E490, Gueymard 2004) and record the source +
  generator here.
