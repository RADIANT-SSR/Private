# Atmosphere Data

RADIANT does **not** ship pre-tabulated atmospheric transmission or path
radiance spectra. Atmospheric profiles are computed at runtime by the
`AtmosphereStage` using analytic models (e.g., Beer–Lambert with
standard-atmosphere molecular absorption coefficients).

For high-fidelity work, users can supply MODTRAN `.tp5`/`.tp6` output
files via the configuration's `atmosphere.modtran_file` parameter. The
RADIANT I/O layer (`radiant.io.modtran`) parses MODTRAN tape output
and converts to the internal spectral format.

## Why no CSV files here?

Unlike material emissivity or detector QE, atmospheric transmission is a
strong function of:

- Observer altitude and slant path geometry
- Target altitude
- Atmospheric profile (temperature, humidity, aerosol loading)
- Wavelength (molecular absorption lines are narrow and numerous)

Pre-tabulating a useful set of atmospheric spectra would require thousands
of files for different geometries and atmospheric conditions. The analytic
model or MODTRAN interface is the correct approach.
