# Conventions

Every RADIANT module obeys one set of conventions. No module defines its own local ones,
and a violation is a bug rather than a style preference. This chapter is the working
summary; the repository's conventions document carries the binding statement, with the
justification for each choice and the comparison against other tools.

---

## 1. Canonical Internal Units

These are the units every quantity is stored and computed in, everywhere inside the
framework.

| Quantity | Canonical unit | Notes |
|----------|----------------|-------|
| Wavelength | µm | Ascending order, always |
| Angle | rad | No exceptions, in any module |
| Time | s | `integration_time_s`, `frame_period_s` |
| Length | m | Altitudes, ranges, aperture, focal length |
| Spectral radiance $L(\lambda)$ | W/m²/sr/µm | Not W/cm² — see the MODTRAN note below |
| In-band radiance $L$ | W/m²/sr | $\int L(\lambda)\,d\lambda$ over the bandpass |
| Spectral irradiance $E(\lambda)$ | W/m²/µm | |
| Spectral intensity $I(\lambda)$ | W/sr/µm | Point sources |
| Spectral photon radiance $L_q(\lambda)$ | photons/s/m²/sr/µm | Derived: $L_q = L\lambda/(hc)$ |
| Signal | e⁻ | After QE and integration time |
| Noise | e⁻ RMS | Every noise term, at its origin frame |
| Temperature | K | Entry in K, °C, or °F; converted once at `set()` |
| SNR | dimensionless | $S/\sigma_\text{total}$ |
| NEDT | K | |
| NIIRS | dimensionless | |
| MTF | dimensionless | $0 \le \text{MTF}(\nu) \le 1$ |
| Spatial frequency | cycles/mm (focal plane) or cycles/mrad (angular) | Always labeled; never "cycles/pixel" as a primary unit |

### Conversion happens exactly once

| Boundary | Conversion | Owner |
|----------|-----------|-------|
| User input | deg → rad, µrad → rad, ms → s, °C/°F → K | `ParameterSet.set(..., unit=...)` |
| MODTRAN tape7 import | cm⁻¹ → µm, W/cm² → W/m² ($\times 10^4$), descending → ascending $\lambda$ | `radiant.atmosphere.modtran` reader |
| Vendor QE CSV | nm → µm, percent → fraction | `radiant.io.qe_csv` |
| Vendor dark-current CSV | A/cm² → e⁻/s/pixel | `radiant.io.dark_current_csv` |
| Detector QE stage | W/m²/sr/µm → photons/s/m²/sr/µm | `SpectralIntegrationStage` |
| Output formatting | rad → deg or µrad, s → ms | Output formatter / GUI |

If a conversion appears in two modules, one of them is wrong. A factor of `1e4`,
`math.pi/180`, or `1e-6` inside a physics module is a red flag: verify it is physics, not
unit plumbing.

The $\times 10^4$ on MODTRAN radiance is the single most consequential conversion in the
tool. MODTRAN reports W/cm²/sr/µm; RADIANT stores W/m²/sr/µm. It is implemented in the
MODTRAN reader and nowhere else.

### Angles: two user-facing units, one internal unit

Internally: radians only. At the user boundary, two units are supported and the threshold
between them is roughly $0.1° = 1745$ µrad:

- **Large angles in degrees** — FOV, look angle, solar zenith, elevation, azimuth.
- **Small angles in µrad** — jitter, pointing knowledge, IFOV, angular blur.

`mrad` is deliberately not supported: it sits in an awkward middle zone and a third
angular unit triples the bug surface.

A parameter's name suffix names its *canonical stored* unit, which is not always the
user-facing entry unit. Two patterns coexist:

```python
# Small angles: stored and named in the user-facing unit.
sensor.set("platform.jitter_rms_urad", 5.0)            # µrad → rad at the boundary

# Large geometry angles: stored and named in radians, entered in degrees.
sensor.set("geometry.solar_zenith_rad", 30.0, unit="deg")   # → 0.5236 rad stored
```

The invariant that actually holds across the whole schema is narrower than "every angle
is named in its entry unit": **every angular parameter is unit-suffixed and is converted
to radians exactly once, at the `set()` boundary.**

---

## 2. Spatial Coordinate System

| Property | Convention |
|----------|-----------|
| Handedness | Right-handed |
| $+Z$ | Toward target — along boresight / optical axis |
| $+X$ | Cross-track (cross-scan; perpendicular to flight direction) |
| $+Y$ | Along-track (along-scan; flight direction projected to the image plane) |
| Euler sequence | 3-2-1 (ZYX): yaw → pitch → roll |
| Pixel indexing | `[row, col] = [y, x] = [along-track, cross-track]`, 0-indexed |

$+Z$ toward target matches the optics convention (Zemax, Code V), where the optical axis
is $+Z$ and the focal plane lies in the $XY$ plane. For a nadir-pointing spacecraft,
$+Z$ is nadir; for a ground observer, $+Z$ is toward the target in the sky. The same
assignment holds for every viewing geometry, with no redefinition.

For a pushbroom sensor the linear array lies cross-track ($+X$) and the image builds
along-track ($+Y$), which puts the TDI direction along $+Y$ and completes a right-handed
frame. A staring sensor maps its two focal-plane axes the same way.

`[row, col]` is the opposite of Cartesian $(x, y)$ ordering, deliberately: it matches
NumPy row-major storage, OpenCV, and standard image processing. Every function that takes
pixel coordinates takes `(row, col)`, never `(x, y)`.

Conversions at boundaries: FITS stores `[col, row]` (NAXIS1 = column = cross-track), so
FITS I/O transposes. MATLAB is 1-indexed, so a MATLAB bridge adds or subtracts 1. STK and
other orbital frames transform to the sensor body frame with the ZYX angles in the
transform module — never inside a physics module.

---

## 3. Spectral Conventions

| Property | Convention |
|----------|-----------|
| Primary spectral variable | Wavelength |
| Primary unit | µm |
| Array ordering | Ascending: $\lambda_0 < \lambda_1 < \dots < \lambda_{N-1}$ |
| Secondary variable | Wavenumber $\nu$ [cm⁻¹] — derived, never stored as primary |
| Conversion | $\nu\,[\text{cm}^{-1}] = 10000 / \lambda\,[\text{µm}]$ |

Wavelength in µm keeps every band in single digits: UV 0.2–0.4 µm, VIS 0.4–0.7 µm,
SWIR 0.7–2.5 µm, MWIR 3–5 µm, LWIR 8–14 µm. Nanometres make MWIR/LWIR unwieldy
(3000–14000 nm); wavenumber inverts the intuition.

MODTRAN's native tape7 output is ascending wavenumber, which is *descending* wavelength.
On import RADIANT reverses the array and applies the Jacobian of the transformation:

$$L(\lambda) = L(\nu)\,\nu^2$$

The $\nu^2$ is two factors whose powers of ten cancel: the spectral-axis Jacobian
$|d\nu/d\lambda| = 10^4/\lambda^2 = \nu^2/10^4$, times the $10^4$ that carries the
cm⁻² → m⁻² area conversion. Written either factor alone, the relation is off by $10^4$.

**Every spectral array must be monotonically increasing in $\lambda$.** Non-monotonic
input is an error, not something silently reordered.

All stages evaluate on one common wavelength grid, spanning
`spectral_integration.filter_min_um` to `filter_max_um` with
`Sensor.wavelength_points` samples (default 500 points). There is no resampling inside
the chain.

---

## 4. Time Conventions

| Property | Convention |
|----------|-----------|
| Integration time | s — `spectral_integration.integration_time_s` |
| Frame period | s — `readout.frame_period_s` (0.0 s = unset) |
| Frame rate | Hz — derived, `stage_outputs["readout"]["frame_rate_hz"]` |
| Duty cycle | dimensionless, $0 < \text{duty} \le 1$ — derived, `stage_outputs["readout"]["duty_cycle"]` |

Integration time and frame period are **independent** parameters: the first is how long
charge accumulates, the second is the time between frame starts, and
$\text{duty cycle} = t_\text{int} / T_\text{frame}$. Neither is derived from the other
without explicit user intent. When `readout.frame_period_s` is left at 0.0 s, the frame
period defaults to $t_\text{int}$ (frame rate $= 1/t_\text{int}$, duty cycle 1.0) and the
chain records `frame_period_defaulted` in the readout stage outputs. A duty cycle above
1.0 — integration longer than the frame period — is rejected with an actionable error.

Display may use SI prefixes (10.0 ms, 250 µs); internal storage is always seconds.

---

## 5. Radiometric Modelling Conventions

**Energy units upstream, photons at the detector.** The chain computes in W through
source, atmosphere, and optics. The conversion to photons happens once, where QE is
applied:

$$S\,[\text{e}^-] = t_\text{int} \int L(\lambda)\, A\, \Omega\, \tau_\text{opt}(\lambda)\, \tau_\text{atm}(\lambda)\, \text{QE}(\lambda)\, \frac{\lambda}{hc}\, d\lambda$$

Carrying photon quantities upstream would force a $\lambda/(hc)$ spectral weighting
through stages that should be spectrally agnostic, such as geometric throughput.

**Noise lives in electrons at its origin frame.** Every noise term carries a value in
e⁻ RMS and the reference frame where it was generated. Conversion to another frame — DN,
aperture-referred irradiance — happens at query time from the stored forward factors,
never at generation time.

**Emissivity of an optical element is always derived, never an input.** Kirchhoff's law
gives $\varepsilon = 1 - R$ for a mirror and $\varepsilon = 1 - T - R$ for a transmissive
element. Supplying both reflectance and emissivity for an optical surface over-specifies
the energy balance and is rejected with a `KirchhoffViolationError`. This does **not**
apply to scene targets and backgrounds, where emissivity is a legitimate independent
material property.

---

## 6. Physical Constants

All constants are CODATA 2018 exact values, defined once in `radiant.core.constants` and
imported everywhere else.

| Constant | Symbol | Value | Unit |
|----------|--------|-------|------|
| Speed of light | $c$ | $2.99792458 \times 10^{8}$ | m/s |
| Planck constant | $h$ | $6.62607015 \times 10^{-34}$ | J·s |
| Boltzmann constant | $k_B$ | $1.380649 \times 10^{-23}$ | J/K |
| Stefan–Boltzmann constant | $\sigma_\text{SB}$ | $5.670374419 \times 10^{-8}$ | W/m²/K⁴ |
| Elementary charge | $q$ | $1.602176634 \times 10^{-19}$ | C |

No module hardcodes a constant, and no "close enough" approximation is acceptable —
$c \approx 3 \times 10^{8}$ m/s is forbidden.

---

## 7. Parameter Naming

Parameters are dot-paths of the form `namespace.parameter_name`, lowercase with
underscores, mapping directly onto YAML nesting:

| Dot-path | YAML location |
|----------|---------------|
| `optics.aperture_diameter_m` | `optics:` → `aperture_diameter_m:` |
| `source.target.temperature` | `source:` → `target:` → `temperature:` |
| `spectral_integration.filter_min_um` | `spectral_integration:` → `filter_min_um:` |

The ten namespaces are the ten stage names. A unit suffix on the name (`_m`, `_um`,
`_rad`, `_s`, `_e_rms`) names the canonical stored unit; a parameter with no natural
unit carries none. Every parameter has exactly one `ParameterDef` in its owning stage's
`_schema.py`, and nothing tuneable is hardcoded in a physics module.
