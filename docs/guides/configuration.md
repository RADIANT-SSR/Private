# Configuration Guide

*Persona: Sarah (systems engineer), Raj (mission planner), Lisa (analyst)*

How to define, customize, and manage RADIANT sensor configurations.

---

## YAML Structure

A RADIANT configuration file has seven top-level sections matching the
signal-chain stages. Here is an annotated example showing the most commonly
used parameters:

```yaml
# --- Source (target and background) ---
source:
  target:
    temperature: 300.0         # K — target kinetic temperature
    emissivity: 0.95           # dimensionless, 0–1
    # fill_fraction: 0.5       # for sub-pixel targets (0–1)
    # projected_area_m2: 4.0   # target cross-section (m^2)
    # range_m: 10000.0         # slant range to target (m)
  background:
    temperature: 290.0         # K — background temperature (default)
    emissivity: 0.95           # background emissivity (default)
  # regime_override: auto      # auto | extended | sub_pixel | point_source

# --- Atmosphere ---
atmosphere:
  standard_atmosphere: midlat_summer   # midlat_summer | midlat_winter | ...
  # model: simple                      # simple | exo | tabulated | modtran
  # visibility_km: 23.0               # meteorological visibility
  # precipitable_water_cm: 1.4        # precipitable water vapor

# --- Geometry ---
geometry:
  sensor_altitude_m: 8000.0   # m — sensor altitude above ground
  # target_altitude_m: 0.0    # m — target elevation
  # path_zenith_rad: 0.0      # rad — off-nadir angle (0 = nadir)

# --- Optics ---
optics:
  aperture_diameter_m: 0.30   # m
  focal_length_m: 1.20        # m → f/4.0 (derived)
  transmission_scalar: 0.70   # end-to-end optical transmission
  # obscuration_ratio: 0.0    # central obscuration ratio
  # wfe_rms_waves: 0.0        # wavefront error in waves
  # optics_temperature_K: 290 # for self-emission calculation

# --- Detector ---
detector:
  pixel_pitch_x_um: 18.0      # um — pixel pitch cross-track
  pixel_pitch_y_um: 18.0      # um — pixel pitch along-track
  qe_value: 0.70              # quantum efficiency (flat)
  dark_rate_e_per_s: 100.0    # e-/s — dark current
  # read_noise handled in readout section
  # fill_factor: 1.0          # pixel fill factor (default)

# --- Spectral Integration ---
spectral_integration:
  filter_min_um: 3.5           # um — bandpass start
  filter_max_um: 5.0           # um — bandpass end
  integration_time_s: 0.005    # s — detector integration time

# --- Readout ---
readout:
  read_noise_e_rms: 5.0       # e- RMS
  gain_e_per_dn: 1.0          # e-/DN — system gain
  adc_bits: 16                 # ADC bit depth
  # n_tdi: 1                  # TDI stages (default = 1 = off)
  # n_coadds: 1               # number of coadded frames
```

See the [Parameter Reference](parameter_reference.md) for the exhaustive list
of all 91 parameters with types, defaults, and bounds.

---

## Parameter Dot-Path Convention

Every parameter has a dot-separated path that maps directly to YAML nesting:

| Dot-path                           | YAML location                      |
|------------------------------------|------------------------------------|
| `optics.aperture_diameter_m`       | `optics: aperture_diameter_m:`     |
| `source.target.temperature`        | `source: target: temperature:`     |
| `spectral_integration.filter_min_um` | `spectral_integration: filter_min_um:` |

This path is used everywhere: CLI overrides, Python API, `explain`, `sweep`.

---

## Defaults and Required Parameters

Most parameters have sensible defaults. The minimum required set for a
working evaluation is:

- `source.target.temperature`
- `source.target.emissivity`
- `optics.aperture_diameter_m`
- `optics.focal_length_m`
- `detector.pixel_pitch_x_um` and `pixel_pitch_y_um`
- `detector.qe_value`
- `spectral_integration.filter_min_um` and `filter_max_um`
- `spectral_integration.integration_time_s`
- `readout.read_noise_e_rms`
- `readout.gain_e_per_dn`
- `readout.adc_bits`
- `geometry.sensor_altitude_m`

Everything else defaults to a physically reasonable value. Run
`radiant validate <config>` to check completeness.

---

## Overriding Parameters

### CLI: `--set`

```bash
radiant run config.yaml --set optics.aperture_diameter_m=0.50
radiant run config.yaml --set optics.aperture_diameter_m=0.50 \
                        --set detector.qe_value=0.80
```

### Python: `sensor.set()`

```python
from radiant.api import Sensor

sensor = Sensor.from_yaml("examples/mwir_leo_minimal.yaml")
sensor.set("optics.aperture_diameter_m", 0.50)
sensor.set("detector.qe_value", 0.80)
result = sensor.evaluate()
```

Or set multiple at once:

```python
from radiant.api import Sensor

sensor = Sensor.from_yaml("examples/mwir_leo_minimal.yaml")
sensor.set_many({
    "optics.aperture_diameter_m": 0.50,
    "detector.qe_value": 0.80,
})
result = sensor.evaluate()
```

---

## Consistency Groups

Some parameters are linked by physical relationships. The f-number
consistency group enforces:

$$f/\# = f / D$$

If you specify `aperture_diameter_m` and `focal_length_m`, then `f_number`
is derived automatically. If you specify all three and they conflict,
RADIANT raises an error.

Check how a derived value was computed:

```bash
radiant explain examples/mwir_leo_minimal.yaml optics.f_number
```

---

## Units

RADIANT uses canonical internal units (meters, radians, seconds, etc.) but
accepts common input units. The `radiant convert` utility helps:

```bash
radiant convert 18 um m          # 18 um = 1.8e-05 m
radiant convert 45 deg rad       # 45 deg = 0.785398 rad
radiant convert 5 ms s           # 5 ms = 0.005 s
```

Parameter values in YAML are in the input units documented in the
[Parameter Reference](parameter_reference.md) --- for example, pixel pitch
is specified in micrometers, altitude in meters.

---

## Using Templates

RADIANT ships 12 templates and 4 CLI-embedded templates spanning VNIR, SWIR,
MWIR, and LWIR bands at various altitudes.

```bash
radiant template list              # see all available templates
radiant template show mwir_leo_pushbroom   # print the YAML
radiant template create mwir_leo_pushbroom # write to mwir_leo_pushbroom.yaml
```

Template YAML files are also in `examples/templates/` for direct use:

```bash
radiant run examples/templates/mwir_aerial_flir.yaml
```

---

## Loading MODTRAN Atmosphere Files

For high-fidelity atmospheric modeling, provide MODTRAN output files:

```yaml
atmosphere:
  model: tabulated
  tabulated_transmittance_file: path/to/transmittance.csv
  tabulated_path_radiance_file: path/to/path_radiance.csv
```

The CSV files must have `wavelength_um` as the first column. See
`data/atmospheres/README.md` for details on why atmosphere data is computed
rather than bundled.

---

## Common Patterns

### Change one parameter and re-run

```bash
radiant run config.yaml --set optics.aperture_diameter_m=0.40
```

### Compare two configurations

```bash
radiant compare config_a.yaml config_b.yaml
```

### Batch many scenarios (Python)

```python
from radiant.api import Sensor

base = Sensor.from_yaml("examples/mwir_leo_minimal.yaml")
altitudes = [5000, 8000, 12000, 20000]

for alt in altitudes:
    s = base.clone()
    s.set("geometry.sensor_altitude_m", alt)
    r = s.evaluate()
    snr = r.metrics["snr"]
    # Process snr for each altitude
```
