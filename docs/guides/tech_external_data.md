# External Data Interfaces

RADIANT reads several external file formats: MODTRAN output, vendor detector datasheet
exports, Zemax wavefront reports, spectral-library files, and Excel workbooks. Every one
of them follows the same two rules.

**Conversion happens at the reader, once.** A tape7 is in wavenumber and W/cm²; a vendor
QE curve may be in nanometres and percent; a dark-current plot is in A/cm². Each reader
converts to canonical units at the file boundary and hands the rest of the framework a
clean object. No physics module ever sees a foreign unit.

**Stages never read files.** Every importer here is called *before* chain execution, by
the API layer or by your own script, and its product is injected as a pre-chain stage
output. This is what keeps stages pure functions.

This chapter documents what actually ships. Where a format is designed but not
implemented, that is said plainly.

---

## 1. MODTRAN

Two ways in, and they are not equal.

### Tape7 file import — the primary path

Set `atmosphere.modtran.tape7_path` to a tape7 produced anywhere — a colleague's
workstation, an archived run, a contractor deliverable. The loader parses it before the
chain; the MODTRAN binary, the cache, and the fallback are never consulted.

```yaml
atmosphere:
  model: modtran
  modtran:
    tape7_path: runs/midlat_summer_nadir/tape7
    tape7_sun_path: runs/midlat_summer_nadir/tape7_sun   # optional solar leg
    tape7_up_path:  runs/midlat_summer_nadir/tape7_up    # optional up-looking leg
    flux_path:      runs/midlat_summer_nadir/flux        # optional flux output
```

Conversions applied exactly once, in `Tape7Reader.to_radiant_units`:

| From | To | Relation |
|------|----|----------|
| Wavenumber $\nu$ [cm⁻¹] | Wavelength $\lambda$ [µm] | $\lambda = 10000/\nu$ |
| Radiance [W/cm²/sr/cm⁻¹] | [W/m²/sr/µm] | $L(\lambda) = L(\nu)\,\nu^2$ |
| Transmittance [--] | [--] | unchanged |
| Descending $\lambda$ | Ascending $\lambda$ | array reversed |

The $\nu^2$ factor is two conversions whose powers of ten cancel: the spectral-axis
Jacobian $|d\nu/d\lambda| = 10^4/\lambda^2 = \nu^2/10^4$, times the $10^4$ that carries
cm⁻² → m⁻² on the area. A tape7 that yields fewer than two spectral rows, or whose
columns cannot be located, raises `Tape7ParseError` naming the file.

A tape7 is **geometry-agnostic**: it is one path, already computed. The model does not
respond to a change in altitude or look angle, and the chain says so in an advisory note
rather than silently reusing the wrong path.

### Binary invocation — the secondary path

With a MODTRAN executable installed, RADIANT can render a tape5 card deck, run the
binary, parse the tape7, and cache the result keyed by an SHA-256 of the rendered deck.
The relevant parameters are `atmosphere.modtran.binary_path`, `cache_dir`,
`atmosphere_profile`, `aerosol_model`, `h2o_scale`, `o3_scale`,
`spectral_resolution_cm1`, and `allow_fallback`.

When the binary is unavailable the behavior is explicit, never silent:

| Condition | Behavior |
|-----------|----------|
| Cache hit | Use the cached result |
| `allow_fallback: true` | Translate the parameters to the simple analytic model and warn |
| `allow_fallback: false` | Raise `ModtranUnavailableError` naming the binary path tried |

This path has never been exercised against a licensed installation in the shipped test
matrix; the tape7-import path is the supported one.

### The shipped alternative

Most users need neither: the bundled atmosphere library is MODTRAN-derived data,
available through `atmosphere.model: interpolated`. See the
[Data Libraries](tech_data_libraries.md) chapter.

---

## 2. Measured Curves

`radiant.io.measurement.load_measured_curve` reads a two-column $(x, y)$ curve from any
delimited text file — measured MTF against spatial frequency, measured transmission
against wavelength — for comparison against a RADIANT prediction.

```python
from radiant.io.measurement import load_measured_curve

curve = load_measured_curve(
    "lab/mtf_measured.csv",
    x_column=0, y_column=1,
    delimiter=",",
    skip_header="auto",
    x_unit="cycles/mm",
)
curve.x, curve.y, curve.n_points, curve.x_unit, curve.source_file
```

Parsing rules, chosen so nothing is dropped quietly:

- `#` comment lines and blank lines are skipped.
- `skip_header="auto"` treats a first row that does not parse numerically as a header. An
  integer skips exactly that many data rows unconditionally.
- Any non-numeric value after the header is a hard `MeasurementParseError` — no silent
  row dropping.
- $x$ must be strictly ascending. Out-of-order rows are sorted with a `UserWarning`;
  duplicated $x$ values raise, because the intended ordering is then ambiguous.

Excel workbooks are out of scope for this reader — export the sheet to CSV first.

---

## 3. Vendor Detector Data

### QE curves

`radiant.io.qe_csv.load_qe_csv` reads a vendor QE export into canonical units — µm and
fraction — resolving the mixed conventions vendors ship (`wavelength_nm, QE_pct` and
`lambda_um, quantum_efficiency` are both common):

```python
import numpy as np
from radiant.io.qe_csv import load_qe_csv

qe = load_qe_csv("vendor/imx455_qe.csv")           # units inferred from the header
qe = load_qe_csv("vendor/qe.csv", wavelength_unit="nm", qe_unit="percent")

qe.evaluate(np.array([4.0, 4.2, 4.4]))   # QE at those wavelengths [µm], as fractions
qe.band_averaged_qe(3.5, 5.0)            # band mean over 3.5-5.0 µm
```

Unit resolution in `"auto"` mode is header-driven, never magnitude-driven: a header token
containing `nm` means nanometres, one containing `um` / `µm` / `micron` means
micrometres, and a token containing `pct` / `percent` / `%` means percent. A header with
no hint raises `QeCsvParseError` asking for an explicit `wavelength_unit` rather than
guessing. A fraction-mode curve carrying values above 1.0 raises with a pointer at
`qe_unit="percent"` instead of producing unphysical QE.

The same file can be reached from a config through `detector.qe_table_path`, in which
case the API layer loads it before the chain and injects the curve onto the evaluation
grid; past-cutoff QE is zero.

### Dark current

`radiant.io.dark_current_csv.load_dark_current_csv` reads a temperature-vs-current-density
export (`T_K, Jdark_A_cm2`) and converts to RADIANT's canonical dark rate for a given
pixel pitch:

$$\text{rate}\,[\text{e}^-/\text{s}] = \frac{J\,[\text{A/cm}^2] \cdot (\text{pitch} \cdot 100)^2\,[\text{cm}^2]}{q}$$

```python
from radiant.io.dark_current_csv import load_dark_current_csv

dc = load_dark_current_csv("vendor/jdark.csv")
dc.j_dark_at(95.0)                                    # A/cm² at 95 K
dc.dark_rate_e_per_s(95.0, pixel_pitch_m=18e-6)       # e-/s/pixel
dc.temperature_at_rate(100.0, pixel_pitch_m=18e-6)    # K giving 100 e-/s/pixel
```

Interpolation is Arrhenius-faithful: $\ln J$ is interpolated linearly in $1/T$, which is
exact for $J \propto \exp(-E_a/k_B T)$ between nodes and a far better model of diode dark
current than linear-in-$T$. A query outside the measured temperature range **raises** —
silently extrapolating an exponential is how dark-current budgets go wrong.

---

## 4. Zemax Wavefront Reports

`radiant.io.zemax_zernike.load_zemax_zernike` parses the text report Zemax (OpticStudio)
writes from *Analyze → Wavefront → Zernike Standard Coefficients → Save As Text*. It does
**not** read a `.ZMX` lens prescription.

```python
from radiant.io.zemax_zernike import load_zemax_zernike

z = load_zemax_zernike("optics/lens_field0.txt")
z.zernike_coeffs          # {Noll index: coefficient [waves]}
z.reference_wavelength_um # µm, or None if the header line is absent
z.n_terms
wfe = z.to_wavefront_error()   # feeds the ZERNIKE wavefront pipeline directly
```

Zemax "Standard" Zernikes are Noll-numbered and quoted in waves at the stated wavelength —
exactly RADIANT's own convention, so the parsed set feeds the wavefront pipeline with no
renumbering. The parser tolerates both `Z   1` and `Z1` index styles, an optional trailing
polynomial formula, header wording differences, and UTF-16 (LE/BE, with or without BOM),
UTF-8, or latin-1 encodings — Zemax on Windows usually writes UTF-16-LE.

The report is single-field. A multi-field export concatenated into one file repeats Noll
indices and is rejected with an actionable error telling you to export each field
separately.

From a config, `optics.zernike_file` names the same report and the API layer loads it
pre-chain, superseding the scalar `optics.wfe_rms_waves` path.

---

## 5. Spectral Libraries

`radiant.io.aster_library.load_aster_spectrum` reads one file of the JPL/NASA ASTER
spectral library — the `Name:` / `Type:` metadata header followed by two
whitespace-separated columns:

```python
from radiant.io.aster_library import load_aster_spectrum

spec = load_aster_spectrum("aster/conifer.txt")
spec.name, spec.wavelength_um, spec.reflectance
spec.emissivity()                       # 1 - rho(lambda), Kirchhoff for an opaque material
spec.band_averaged_emissivity(8.0, 12.0)
```

ASTER files usually list wavelength in *descending* order; the reader sorts ascending and
returns fractional reflectance. The $Y$ unit is taken from the `Y Units:` header line
(`percent` vs. `fraction`); a file with no recognizable unit line raises rather than
guessing.

Emissivity for an opaque scene material is $\varepsilon(\lambda) = 1 - \rho(\lambda)$.
This is the legitimate independent-emissivity case — Kirchhoff's derived-only constraint
binds optical elements, not scene targets.

RADIANT's own bundled material and QE curves are covered in
[Data Libraries](tech_data_libraries.md). A measured background emissivity can also be
attached from a config through `source.background.emissivity_path` (a two-column
`wavelength_um, emissivity` CSV), and a target reflectance or brightness temperature the
same way.

---

## 6. Spreadsheets

Two Excel interfaces ship, and both depend on `openpyxl` from an optional extra. A third
is designed but not implemented — see below.

### Target-library import — `[scenarios]` extra

`radiant.io.target_library.load_target_library` reads a program-office target list from a
workbook:

```python
from radiant.io.target_library import load_target_library

targets = load_target_library("program/targets.xlsx", sheet="Targets")
for t in targets:
    t.target_name, t.length_m, t.width_m, t.height_m
    t.temperature_K, t.emissivity, t.material
    t.projected_area_m2      # length_m x width_m, the sub-pixel / point-source area term
```

Expected header columns, in any order: `target_name`, `length_m`, `width_m`, `height_m`,
`temperature_K`, `emissivity`, `material`. `openpyxl` is imported lazily, so a missing
extra raises an actionable `TargetLibraryError` naming the install rather than breaking
`import radiant.io`:

```bash
pip install "radiant[scenarios]"
```

### Workbook export — `[gui]` extra

`radiant.gui.xlsx_export.export_workbook` writes one workbook with up to three sheets,
built purely from public API surfaces:

| Sheet | Columns | Source |
|-------|---------|--------|
| `Config` | parameter, value, unit | `Sensor.parameter_defs()` + `get_input()` |
| `Metrics` | name, value, unit, description | `ChainResult.to_records()` |
| `Sweep` | param + metric columns (1-D) or long form (2-D) | the last sweep, when one exists |

```python
from radiant.gui.xlsx_export import export_workbook

export_workbook("study.xlsx", sensor, result, sweep)
```

Numeric cells keep full precision — numbers, not formatted strings — and units get their
own column, so the workbook is usable as data rather than only as a report.

### Not implemented: `radiant export` / `radiant import`

`RADIANT_Config_Format.md` §2 describes an XLSX *convenience view* of a config file —
one sheet per namespace, editable value column, round-trippable back to YAML for
reviewers who do not write YAML. **This is a design target.** There is no `radiant export`
or `radiant import` command and no XLSX config code in `radiant.io`. (The existing
`radiant convert` CLI is an unrelated scalar unit converter.) Use `Sensor.to_yaml()` or
the GUI workbook export above.

---

## 7. Other File-Valued Parameters

Beyond the importers above, several schema parameters take a file path directly. The API
layer loads each one before the chain and injects the product:

| Parameter | File | Injected as |
|-----------|------|-------------|
| `atmosphere.modtran.tape7_path` | MODTRAN tape7 | the atmosphere model |
| `atmosphere.tabulated_transmittance_file` / `..._path_radiance_file` / `..._downwelling_file` | CSV or NPZ, first column `wavelength_um` | the atmosphere model |
| `atmosphere.interpolated_data_dir` | directory of NPZ runs | the atmosphere model |
| `atmosphere.cn2_tabulated_file` | altitude-vs-$C_n^2$ CSV | `atmosphere_config.cn2_profile` |
| `detector.qe_table_path` | wavelength-vs-QE CSV | `spectral_integration.qe_curve` |
| `optics.zernike_file` | Zemax Zernike report | `optics_config.wavefront_error` |
| `source.background.emissivity_path` | wavelength-vs-emissivity CSV | `source_config.background_emissivity` |
| `source.target.emissivity_path` / `reflectance_path` / `brightness_temperature_path` | two-column CSV | the source descriptor |
| element-train R/T references | spectral CSV, or an inline table in the YAML | `optics_config.element_list` |

Every one of these paths is resolved **relative to the config file's own directory**, and
`Sensor.save()` writes them back out relative to the destination directory — so a config
and its data files move together as a portable unit.
