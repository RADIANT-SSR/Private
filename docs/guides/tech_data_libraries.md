# Data Libraries

RADIANT ships three reference-data libraries inside the package, so a useful evaluation
needs no external downloads and no MODTRAN license:

| Library | Accessor | Contents |
|---------|----------|----------|
| Spectral library | `radiant.data.SpectralLibrary` | 19 material emissivity spectra, 6 detector QE curves, AM0 solar irradiance |
| FPA preset library | `radiant.data.FPALibrary` | 21 focal-plane / ROIC presets with per-value datasheet attribution |
| Atmosphere library | selected through `atmosphere.model` | MODTRAN-derived transmittance and path radiance, as profiles and interpolable families |

All three live under `src/radiant/data/tables/` in a source checkout and ship inside the
wheel at `radiant/data/tables/`. Each directory carries a `MANIFEST.md` naming its
generator, its inputs, and its provenance, per the regenerable-artifact rule.

---

## 1. SpectralLibrary

```python
from radiant.data import SpectralLibrary

lib = SpectralLibrary()

lib.materials()                     # 19 names, sorted
emissivity = lib.material("vegetation_green")
lib.material_info("vegetation_green")
# {'default_temperature_K': 300,
#  'description': 'Healthy green vegetation (deciduous canopy)',
#  'filename': 'vegetation_green.csv',
#  'source_citation': "Salisbury & D'Aria, JGR, 1992; ASTER Spectral Library"}

lib.detectors()                     # 6 names, sorted
qe = lib.detector_qe("hgcdte_mwir")

solar = lib.solar()                 # AM0 exo-atmospheric spectral irradiance
```

Every accessor returns a `SpectralData` object carrying `.wavelength_um` and `.values`
arrays plus `.unit`, `.source`, and `.name` metadata — so a curve never travels without
its units or its citation.

### Materials — 19 emissivity spectra

`aluminum`, `asphalt`, `blackbody`, `concrete`, `copper`, `glass`, `gold`, `ice`,
`paint_black`, `paint_grey`, `paint_white`, `sand`, `snow`, `soil_dry`, `soil_wet`,
`steel`, `vegetation_dry`, `vegetation_green`, `water_calm`.

Values are dimensionless emissivity, $0 \le \varepsilon(\lambda) \le 1$. Per-material
description, default temperature [K], and source citation live in
`tables/emissivity/manifest.yaml` and come back from `material_info()`.

This is scene-material emissivity — a legitimate independent property. It is *not* the
route for optical-element emissivity, which is always Kirchhoff-derived from R and T.

These curves are reachable from a config without any Python:

```yaml
source:
  background:
    material: vegetation_green   # resolved against SpectralLibrary before the chain
```

### Detector QE — 6 curves

`hgcdte_lwir`, `hgcdte_mwir`, `ingaas`, `inp_ingaasp`, `silicon`, `type2_sls`.

Values are QE as a fraction. A curve selected through `detector.qe_material` supersedes
the scalar `detector.qe_value`; a user-supplied CSV via `detector.qe_table_path`
supersedes both. All three are resolved by the API layer *before* the chain, because
stages do not read files.

### Solar

`lib.solar()` returns AM0 exo-atmospheric spectral irradiance in W/m²/µm, from the
RADIANT solar data library (a Planck fit to the Kopp & Lean 2011 total solar irradiance).
It is the illumination source for every reflective-regime scene.

---

## 2. FPALibrary — 21 presets

An FPA preset is a curated set of `detector.*` and `readout.*` values taken from one
vendor datasheet or paper, with **per-value attribution**: every number records the unit
it was quoted in, the document it came from, and the exact location in that document.

```python
from radiant.data import FPALibrary

lib = FPALibrary()
lib.names()                        # 21 part slugs, sorted
preset = lib.part("teledyne-h2rg-2p5")

preset.vendor                      # 'Teledyne Imaging Sensors'
preset.part_class, preset.part_kind
preset.material
preset.band.label, preset.band.cut_on_um, preset.band.cut_off_um
preset.parameters["detector.pixel_pitch_x_um"]
# FPAParameterEntry(value=18.0, unit='um', basis='datasheet', source='ds2022',
#                   location="'Array Format 2048 x 2048 pixel, 18 um pitch'", note=None)
preset.sources                     # source keys -> FPASource records (title, URL, file)
preset.qe_table                    # a bundled QE curve name, or None
```

Applying one is a single call (or a single config key):

```python
from radiant.api import Sensor

sensor = Sensor.from_yaml("examples/mwir_leo_minimal.yaml")
report = sensor.apply_fpa("scd-blackbird-1920")
```

Values are stored in **the cited document's native unit** and converted to canonical units
at apply time through the unit-aware parameter boundary — the one conversion point.
An entry whose `basis` is `assumed` rather than `datasheet` carries a justification note
instead of a document location, so an inferred value is never mistaken for a quoted one.

### The roster

| Part | Vendor | Class | Detector material | Band [µm] |
|------|--------|-------|-------------------|-----------|
| `dfpa-generic` | MIT Lincoln Laboratory (research lineage) | cooled IR DROIC | detector-agnostic | 1.0–14.0 |
| `e2v-ccd42-40` | Teledyne e2v | scientific visible | back-illuminated Si CCD (AIMO) | 0.35–1.06 |
| `flir-boson-plus-640` | Teledyne FLIR | uncooled bolometer | microbolometer (VOx family) | 8.0–14.0 |
| `flir-lepton-35` | Teledyne FLIR | uncooled bolometer | VOx microbolometer | 8.0–14.0 |
| `flir-neutrino-lc` | Teledyne FLIR | cooled IR | HOT MWIR MCT-class | 3.4–4.9 |
| `geosnap-10` | Teledyne Space Imaging | cooled IR | HgCdTe, customer cutoff | 0.4–14.0 |
| `geosnap-18` | Teledyne Space Imaging | cooled IR | HgCdTe, customer cutoff | 0.4–15.0 |
| `gpixel-gsense400bsi` | Gpixel | scientific visible | BSI Si sCMOS | 0.35–1.0 |
| `lynred-atto640` | Lynred | uncooled bolometer | microbolometer (a-Si family) | 8.0–14.0 |
| `lynred-daphnis-hd-mw` | Lynred | cooled IR | HgCdTe MWIR, HOT to 110 K | 3.7–4.8 |
| `rvs-miri-si-as` | Raytheon Vision Systems | cooled IR | Si:As IBC | 5.0–28.0 |
| `rvs-virgo-2k` | Raytheon Vision Systems | cooled IR | HgCdTe on CdZnTe | 0.75–2.45 |
| `scd-blackbird-1920` | SCD | cooled IR | InSb | 1.0–5.4 |
| `senseeker-calcium-rp0033` | Senseeker | cooled IR DROIC | bare DPROIC | 1.0–14.0 |
| `senseeker-magnesium-rp0092` | Senseeker | cooled IR DROIC | bare DPROIC | 2.0–14.0 |
| `sony-imx250` | Sony Semiconductor Solutions | scientific visible | FSI Si CMOS (Pregius) | 0.32–1.1 |
| `sony-imx455` | Sony Semiconductor Solutions | scientific visible | BSI Si CMOS | 0.35–1.0 |
| `sony-imx990-senswir` | Sony Semiconductor Solutions | SWIR | InGaAs on Si (SenSWIR) | 0.4–1.7 |
| `teledyne-e2v-ccd273` | Teledyne e2v | scientific visible | back-illuminated full-frame Si CCD | 0.3–1.0 |
| `teledyne-h2rg-2p5` | Teledyne Imaging Sensors | scientific visible | substrate-removed HgCdTe hybrid | 0.4–2.5 |
| `teledyne-h4rg-10` | Teledyne Imaging Sensors | scientific visible | HgCdTe hybrid, 2.5 µm cutoff | 0.5–2.5 |

The roster deliberately spans five part classes — cooled IR, DROIC / digital counting,
uncooled bolometer, scientific visible, and SWIR — so a trade study can move between
detector technologies without hand-transcribing a datasheet.

### Provenance chain

Each preset's `sources` block names the documents it cites. The documents themselves are
committed at `docs/validation/fpa_datasheets/` (22 PDFs — vendor datasheets, product
leaflets, and peer-reviewed papers) with a `MANIFEST.md` giving, per file, the title, the
acquisition URL (a Wayback URL where the live document is delisted), the retrieval date,
and a SHA-256. A test asserts that every file a preset cites exists there and matches its
hash.

Those PDFs are **repo-only** and excluded from the wheel — an installed RADIANT gives you
each preset's citation URL or DOI instead of a redistributed copy. A vendor revision is
handled as a new file plus a preset update, never an in-place replacement of a hashed
document.

`src/radiant/data/tables/fpa/configs/` holds one generated, loadable RADIANT config per
preset, rendered by `scripts/gen_fpa_configs.py` and freshness-gated by a test.

---

## 3. Atmosphere library

The atmosphere tables are the largest shipped data product: NPZ spectra derived from a
real MODTRAN 6 run matrix, packaged for the `tabulated` and `interpolated` models so a
user without a MODTRAN license still gets real radiative-transfer atmospheres.

| Family | Model | Coverage |
|--------|-------|----------|
| `profiles/` | `tabulated` | Six standard atmospheres, nadir full column (`us_standard`, `tropical`, `midlat_summer` also carry real downwelling sky radiance) |
| `us_standard_zenith_fan/` | `interpolated` | Line-of-sight zenith fan, 0–60° |
| `midlat_summer_ladders/` | `interpolated` | Sensor altitude (35 km – GEO) × target altitude (0–29 km) |
| `midlat_summer_boost_ladder/` | `interpolated` | Space sensor × target altitude 0–100 km (missile boost) |
| `midlat_summer_boost_offnadir/` | `interpolated` | Space sensor × target 0–100 km × LOS zenith 0/45/60° |
| `midlat_summer_sensor_ladder/` | `interpolated` | Airborne → space sensor (3 km – GEO), ground target |
| `midlat_summer_uplooking_*` | `interpolated` | Up-looking families (ladders, sensor ladder, zenith fan) |
| `midlat_summer_sst_column_fan*` | `interpolated` | Up-looking whole-column to space, zenith 0–78.5°, sea level and 900 m site |
| `midlat_summer_upwelling_offnadir/` | `interpolated` | Down-looking upwelling grid, off-nadir |
| `validation/` | point data | Off-grid 45° and up-looking anchors |

### Provenance and treatment

The generator is `scripts/build_atmosphere_library.py`, reading a tracked MODTRAN 6 run
set: a 39-run base, a 17-run boost-ladder expansion, and two geometry-flexibility batches.
Every array is slit-degraded with a triangular FWHM = 5 cm⁻¹ kernel on the native uniform
1 cm⁻¹ wavenumber grid, then decimated to 2 cm⁻¹ sampling and stored as float32 — 12,984
points spanning 0.375–14.29 µm. Band-mean $\tau$ shifts by $\lesssim 0.003$ (dimensionless)
against the full-resolution tape7s.

Each NPZ carries `wavelength_um` [µm, ascending], `transmittance` [dimensionless],
`path_radiance` [W/m²/sr/µm], an optional `atm_emission_down` [W/m²/sr/µm], and a
`geometry` dict recording the full five-field run geometry: `sensor_altitude_m` [m],
`target_altitude_m` [m], `path_zenith_rad` [rad], `solar_zenith_rad` [rad], and
`solar_azimuth_rad` [rad]. All shipped down-looking runs used a solar zenith of 30° and
an azimuth of 0°; the interpolated model warns when a query departs from a recorded
non-axis value.

### Selection

With `atmosphere.model: interpolated` and no `atmosphere.interpolated_data_dir`, the
loader picks the bundled family matching the scene's line-of-sight direction and the
configured `atmosphere.interpolation_axes`. The model **does not extrapolate**: a query
outside a family's node coverage is refused with an actionable error naming the coverage
it does have, rather than silently producing an invented atmosphere.

Point `atmosphere.interpolated_data_dir` at your own directory of NPZ runs to use a
private run matrix — the bundled catalog is a convenience, not a constraint.

Full detail, including the family tables, the run provenance, and the known limitations,
is in the shipped library's own manifest and README. Choosing between the five atmosphere
backends for a given scene is the subject of the repository's atmosphere-selection guide.

---

## 4. Mission templates

Not a data library in the same sense, but shipped in the same tree: nine complete,
runnable mission configs at `radiant/data/templates/`, listed in the Command-Line
Interface chapter under `radiant template`. They are the
GUI welcome-screen set and the fastest way to a working config in a new band or regime.
