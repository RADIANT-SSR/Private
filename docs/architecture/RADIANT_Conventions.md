# RADIANT Core Conventions

**Date:** 2026-04-06  
**Status:** Accepted  
**Scope:** These conventions are binding on all RADIANT code, documentation, and data formats. No module may define its own local conventions. Violations are bugs.

---

## 1. Spatial Coordinate System

### Choice

| Property | Convention |
|----------|-----------|
| Handedness | **Right-handed** |
| +Z direction | **Toward target** (along boresight / optical axis) |
| +X direction | **Cross-track** (cross-scan; perpendicular to flight direction) |
| +Y direction | **Along-track** (along-scan; flight direction projected to image plane) |
| Euler convention | **3-2-1 (ZYX): Yaw → Pitch → Roll** |
| Pixel indexing | **[row, col] = [y, x] = [along-track, cross-track]** (0-indexed) |

### Justification

**+Z toward target:** Matches the optics convention (Zemax, Code V) where the optical axis is +Z and the focal plane lies in the XY plane. For a nadir-pointing space sensor, +Z = nadir = toward Earth. For a ground-based observer, +Z = zenith = toward target in space. The convention holds for all 9 geometry combinations without redefinition.

**+X cross-track, +Y along-track:** For a pushbroom sensor, the linear array is oriented cross-track (+X), and the image builds up along-track (+Y) as the platform moves. This places the TDI direction along +Y, the array direction along +X, and completes a right-handed system with +Z toward target. For a staring sensor, +X and +Y map to the two focal plane axes with the same assignment.

**3-2-1 Euler (ZYX):** Standard in aerospace (aircraft, spacecraft). Yaw = rotation about +Z (sensor boresight), Pitch = rotation about the once-rotated +Y axis, Roll = rotation about the twice-rotated +X axis. This is the convention used in most attitude control systems and avoids gimbal lock for small off-nadir angles.

**[row, col] = [y, x]:** Matches NumPy array indexing (row-major), OpenCV, FITS, and standard image processing. Row 0 is the first along-track line acquired. Column 0 is the leftmost cross-track pixel (port side / minimum +X). This is the opposite of Cartesian (x, y) ordering — and that is deliberate: array storage and image display are row-major. Every function that takes pixel coordinates uses (row, col), never (x, y), to prevent ambiguity.

### What other tools use

| Tool | Convention | Interface note |
|------|-----------|----------------|
| Zemax | +Z along optical axis, right-handed | Direct alignment — no transform needed |
| Code V | +Z along optical axis, right-handed | Direct alignment |
| MODTRAN | No spatial frame (1D path) | N/A |
| STK | Various body/ECI/ECEF frames | Transform at geometry interface |
| NumPy | [row, col], 0-indexed | Direct alignment |
| MATLAB | [row, col], 1-indexed | Subtract 1 on import |
| FITS | [col, row] (NAXIS1 = X, NAXIS2 = Y) | Transpose axes on FITS I/O |

### Conversion rules at interface boundaries

- **FITS import/export:** Transpose array axes. FITS NAXIS1 = column = cross-track, NAXIS2 = row = along-track. RADIANT stores [row, col]; FITS stores [col, row] in header semantics.
- **STK/orbital geometry:** Transform from ECI/ECEF to sensor body frame using the 3-2-1 Euler angles. The transform module owns this conversion; no physics module should contain coordinate transforms.
- **MATLAB interop:** Add 1 to all indices on export, subtract 1 on import.

---

## 2. Spectral Conventions

### Choice

| Property | Convention |
|----------|-----------|
| Primary spectral variable | **Wavelength** |
| Primary unit | **µm (micrometers)** |
| Array ordering | **Ascending wavelength**: λ[0] < λ[1] < ... < λ[N-1] |
| Secondary variable | **Wavenumber ν (cm⁻¹)**, derived, never stored as primary |
| Conversion | ν [cm⁻¹] = 10,000 / λ [µm] |

### Justification

**Wavelength in µm:** The EO sensor community thinks in wavelength, not wavenumber. "MWIR is 3–5 µm" is universal; "MWIR is 2000–3333 cm⁻¹" is atmospheric-physicist speak. Using µm avoids the non-intuitive inverse relationship of wavenumber, where larger numbers mean shorter wavelengths.

Nanometers (nm) are rejected because MWIR/LWIR wavelengths become unwieldy (3000–14000 nm). Micrometers keep all bands in single-digit numbers: UV = 0.2–0.4 µm, VIS = 0.4–0.7 µm, SWIR = 0.7–2.5 µm, MWIR = 3–5 µm, LWIR = 8–14 µm.

**Ascending wavelength:** Natural ordering for the EO community. Plot axes go left to right with increasing wavelength. Array index increases with wavelength.

**Wavenumber as derived:** MODTRAN's native output is in wavenumber (cm⁻¹, ascending), which means descending wavelength. On MODTRAN import, RADIANT reverses the array to ascending wavelength and converts cm⁻¹ → µm. Wavenumber is accessible via a utility function or property but is never stored as the primary spectral axis.

### What other tools use

| Tool | Primary variable | Unit | Ordering |
|------|-----------------|------|----------|
| MODTRAN (tape7) | Wavenumber | cm⁻¹ | Ascending wavenumber (= descending λ) |
| MODTRAN (.plt) | Wavelength | µm | Ascending wavelength |
| Zemax | Wavelength | µm | Ascending |
| ENVI | Wavelength | µm or nm | Ascending |
| Spectral libraries (USGS, ASTER) | Wavelength | µm | Ascending |

### Conversion rules at interface boundaries

- **MODTRAN tape7 import:** Read ascending wavenumber array ν[]. Convert: λ[i] = 10000 / ν[i]. Reverse array to ascending wavelength. Convert spectral quantities: L(λ) = L(ν) × ν² / 10000 (Jacobian of the cm⁻¹ → µm transformation).
- **MODTRAN .plt import:** Already in µm ascending. No conversion needed.
- **ENVI spectral libraries in nm:** Divide by 1000 to convert to µm.
- **All spectral arrays must be monotonically increasing in λ.** Non-monotonic input is an error, not silently reordered.

---

## 3. Radiometric Quantity Conventions

### Choice

| Quantity | Symbol | Unit | Notes |
|----------|--------|------|-------|
| Spectral radiance | L(λ) | **W / m² / sr / µm** | Energy rate per area per solid angle per wavelength |
| In-band radiance | L | **W / m² / sr** | Integral of L(λ) over bandpass |
| Spectral irradiance | E(λ) | **W / m² / µm** | Energy rate per area per wavelength |
| In-band irradiance | E | **W / m²** | Integral of E(λ) over bandpass |
| Spectral intensity | I(λ) | **W / sr / µm** | Energy rate per solid angle per wavelength (point sources) |
| Spectral photon radiance | L_q(λ) | **photons / s / m² / sr / µm** | Derived: L_q = L × λ / (hc) |
| Signal electrons | S | **e⁻** | After QE and integration time |
| Noise | σ | **e⁻ RMS** | All noise terms in electrons |
| SNR | SNR | **dimensionless** | S / σ_total |
| NEDT | NEDT | **K (kelvin)** | Noise-equivalent differential temperature |
| NIIRS | NIIRS | **dimensionless** | National Imagery Interpretability Rating Scale |
| MTF | MTF(f) | **dimensionless** | 0–1, as a function of spatial frequency f |
| Spatial frequency | f | **cycles / mm** (focal plane) or **cycles / mrad** (angular) | Context-dependent; always labeled |

### Justification

**W/m²/sr/µm for spectral radiance:** This is the SI-adjacent standard used by MODTRAN, most radiometry textbooks (Dereniak & Boreman, Schott), and the remote sensing community. The alternative W/cm²/sr/µm (used in some older military specs like MIL-STD-2500) introduces a factor of 10⁴ that causes unit conversion bugs. We use m², not cm².

**Photon radiance as derived, not primary:** The signal chain computes in energy units (W) through source, atmosphere, and optics. Conversion to photons happens once, at the detector interface, where QE is applied:

```
S_electrons = ∫ [L(λ) × A × Ω × τ_opt(λ) × τ_atm(λ) × QE(λ) × λ/(hc)] dλ × t_int
```

Storing photon quantities upstream would require carrying λ/(hc) through every stage, creating a spectral-weighting dependency in stages that should be spectrally agnostic (e.g., geometric throughput).

**Noise in electrons:** All noise terms are computed and reported in electrons (e⁻ RMS). This is the natural unit at the detector. Conversion to other units happens at the output stage:
- To DN: divide by gain G (e⁻/DN)
- To NEDT: σ_total / (dS/dT) where dS/dT is signal derivative with respect to target temperature
- To NEI: σ_total / (dS/dE) for irradiance-referred noise

### What other tools use

| Tool | Radiance unit | Notes |
|------|--------------|-------|
| MODTRAN | W / cm² / sr / µm (or W / cm² / sr / cm⁻¹) | **Factor of 10⁴ conversion required on import** |
| Zemax | W / cm² (radiometric analysis) | Varies by analysis type |
| DIRSIG | W / m² / sr / µm | Direct alignment |
| NVThermIP | W / cm² / sr | Integrated, not spectral |

### Conversion rules at interface boundaries

- **MODTRAN import:** Multiply spectral radiance by 10⁴ to convert from W/cm²/sr/µm → W/m²/sr/µm. This is the single most important unit conversion in the tool and must be implemented once in the MODTRAN reader, nowhere else.
- **Energy → photon conversion:** Applied once at the detector QE stage. L_q(λ) = L(λ) × λ / (hc), where h = 6.62607015 × 10⁻³⁴ J·s, c = 2.99792458 × 10⁸ m/s, and λ is in meters (convert from µm by × 10⁻⁶). Use exact CODATA 2018 values for h and c.
- **Spatial frequency:** Always labeled with units. Focal-plane spatial frequency in cycles/mm; angular spatial frequency in cycles/mrad. Conversion: f_angular = f_focal × focal_length. Never use "cycles/pixel" as a primary unit — it hides the physical scale.

---

## 4. Time Conventions

### Choice

| Property | Convention |
|----------|-----------|
| Integration time | **Seconds (float64)** |
| Frame period | **Seconds (float64)** |
| Frame rate | **Hz (float64)** = 1 / frame_period |
| Duty cycle | **Dimensionless (0–1)** = t_int / frame_period |
| Display convention | **SI prefixes allowed in display** (ms, µs) but internal is always seconds |

### Justification

**Seconds, always:** SI unit. Eliminates the "is 10 milliseconds or microseconds?" ambiguity. Detector datasheets often quote integration time in ms or µs, but those are display conventions. Internally, `t_int = 0.010` means 10 ms. `t_int = 1e-5` means 10 µs. No unit suffix on the variable — the convention document defines it.

**Frame rate vs. integration time:** These are independent parameters. Integration time is how long charge accumulates. Frame period is the time between frame starts. Duty cycle = t_int / frame_period ≤ 1.0. A duty cycle < 1 means dead time between frames. These are always stored separately; never derive one from the other without explicit user intent.

### What other tools use

| Tool | Time unit | Notes |
|------|----------|-------|
| MODTRAN | N/A | Atmospheric model; no time dependence |
| Detector datasheets | ms or µs typically | Convert on input |
| NVThermIP | ms | Convert on input |

### Conversion rules at interface boundaries

- **Input:** Accept time values with optional unit specification. If no unit specified, assume seconds. Config file example: `integration_time: 0.010  # seconds`. Display helpers may show "10.0 ms" but internal storage is always seconds.
- **No implicit frame rate ↔ integration time conversion.** Both must be specified independently. If only integration time is given, frame rate defaults to 1/t_int (duty cycle = 1.0) with a logged warning.

---

## 5. Angular Units

### Choice

| Context | Unit | Rationale |
|---------|------|-----------|
| **Internal computation** | **Radians** | All trig functions, all physics equations, all stored values |
| **User-facing input: large angles** | **Degrees** | FOV, look angle, solar zenith, elevation, azimuth |
| **User-facing input: small angles** | **µrad** | Jitter, pointing knowledge, IFOV, angular blur |
| **User-facing output** | **Same as input context** | Large angles in degrees, small angles in µrad |
| **Threshold between "large" and "small"** | **~0.1° = 1745 µrad** | Below this, µrad is more readable; above, degrees is more readable |

### Justification

**Radians internally:** NumPy trig functions use radians. All physics equations (diffraction: θ = 1.22λ/D in radians, MTF: exp(−2π²σ²f²) with σ in radians, etc.) use radians. Storing angles in degrees internally would require conversion at every computation — a guaranteed source of bugs.

**Degrees for large angles:** "Solar zenith = 30°" is immediately understandable. "Solar zenith = 0.5236 rad" is not. Large angles (FOV, pointing, geometry) are always communicated in degrees in the EO community.

**µrad for small angles:** "Jitter = 5 µrad RMS" is standard in the pointing/controls community. "Jitter = 2.86 × 10⁻⁴ degrees" or "Jitter = 5 × 10⁻⁶ rad" are both unreadable. IFOV of a typical sensor is 10–100 µrad — µrad is the natural unit.

**mrad is not used.** It falls in an awkward middle zone. Quantities that are naturally mrad-scale (IFOV of wide-angle cameras, some FOVs) can be expressed as either µrad × 10³ or degrees × 10⁻³. Allowing three angular units (degrees, mrad, µrad) triples the bug surface. Two units (degrees for large, µrad for small) is sufficient.

### What other tools use

| Tool | Angular unit |
|------|-------------|
| MODTRAN | Degrees (geometry inputs) |
| Zemax | Degrees (field angles, surface tilts) |
| Code V | Degrees |
| STK | Degrees (large angles), arcseconds (pointing) |
| Pointing/controls community | µrad, arcseconds |

### Conversion rules at interface boundaries

- **Input API contract:** All angular parameters are named with a suffix indicating their user-facing unit: `solar_zenith_deg`, `jitter_urad`, `fov_deg`, `ifov_urad`. On ingestion, the API converts to radians immediately:
  ```
  solar_zenith_rad = solar_zenith_deg * (π / 180)
  jitter_rad = jitter_urad * 1e-6
  ```
- **Internal storage:** Radians only. No exceptions. No module may store angles in degrees or µrad internally.
- **Output API contract:** Convert back to the user-facing unit on output. The output struct labels all angular quantities with their unit suffix.
- **Never pass bare floats as angles.** If a function takes an angle, the parameter name or type must indicate the unit. `compute_mtf(sigma)` is forbidden; `compute_mtf(sigma_rad)` is required.

---

## 6. Physical Constants

All physical constants use **CODATA 2018 exact values** (SI redefinition):

| Constant | Symbol | Value | Unit |
|----------|--------|-------|------|
| Speed of light | c | 2.99792458 × 10⁸ | m/s |
| Planck constant | h | 6.62607015 × 10⁻³⁴ | J·s |
| Boltzmann constant | k_B | 1.380649 × 10⁻²³ | J/K |
| Stefan-Boltzmann constant | σ_SB | 5.670374419 × 10⁻⁸ | W/m²/K⁴ |
| Elementary charge | q | 1.602176634 × 10⁻¹⁹ | C |

These are defined once in a constants module. No module may hardcode physical constants. No "close enough" approximations (e.g., c ≈ 3 × 10⁸ is forbidden).

---

## 7. Summary of Interface Conversion Responsibilities

| Boundary | What gets converted | Who owns the conversion |
|----------|-------------------|------------------------|
| MODTRAN import | cm⁻¹ → µm, W/cm² → W/m², descending λ → ascending λ | MODTRAN reader module |
| Config file import | deg → rad, µrad → rad, ms → s | Input parser |
| Detector interface | W/m²/sr/µm → photons/s/m²/sr/µm | Detector model (QE stage) |
| Output formatting | rad → deg or µrad, s → ms | Output formatter |
| FITS I/O | [row, col] ↔ [NAXIS1, NAXIS2] axis transpose | FITS I/O module |
| MATLAB interop | 0-indexed ↔ 1-indexed | MATLAB bridge |

**Rule:** Each conversion happens in exactly one place. If a conversion appears in two modules, one of them is wrong.
