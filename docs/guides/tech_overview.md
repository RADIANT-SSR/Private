# System Overview

RADIANT is a first-principles electro-optical sensor performance model. Given a sensor
specification, an observation geometry, an atmosphere, and a target/background
description, it propagates spectral radiance from the source to the digitized output and
reports SNR, NEDT, NIIRS, system MTF, and detection range — accumulating every noise term
and every MTF contributor at the stage where it physically originates.

This chapter orients a script author or developer in that machine: what the stages are,
how data moves between them, why there are two parallel spatial paths, and why geometry
runs first. The authoritative statement of each constraint lives in
`docs/architecture/RADIANT_Master_Architecture.md`; Part 3 of this volume binds the stage
protocol, the parameter system, and the test framework verbatim.

---

## 1. The Signal Chain

A RADIANT evaluation is one pass through ten stages, in a fixed order. The order is a
physics statement, not a convenience: each stage consumes quantities the previous stages
published, and no stage reaches backwards.

| # | Stage | Package | Consumes | Publishes |
|---|-------|---------|----------|-----------|
| 0 | `geometry` | `radiant.geometry` | Altitudes [m], look angles [rad], platform kinematics | Slant range [m], ground range [m], GSD [m], incidence [rad], ground speed [m/s] |
| 1 | `source` | `radiant.source` | Target/background temperature [K], emissivity [--], reflectance [--] | Target and background spectral radiance [W/m²/sr/µm], tentative regime |
| 2 | `atmosphere` | `radiant.atmosphere` | Path geometry, atmosphere model selection | $\tau_\text{atm}(\lambda)$ [--], path radiance $L_\text{path}(\lambda)$ [W/m²/sr/µm] |
| 3 | `optics` | `radiant.optics` | Aperture [m], focal length [m], wavefront error [waves], element train | Complex pupil, `EffectivePSF`, `MTF_optics`, throughput [--], **final regime** |
| 4 | `platform` | `radiant.platform` | Jitter [µrad RMS], smear rate [rad/s], turbulence $C_n^2$ [m^(-2/3)] | Degraded `EffectivePSF`, jitter/smear/turbulence MTF, `EE_box` [--] |
| 5 | `spectral_integration` | `radiant.spectral_integration` | All spectral arrays, QE($\lambda$) [--], $t_\text{int}$ [s] | Per-pixel signal [e⁻] — the spectral-to-scalar boundary |
| 6 | `detector` | `radiant.detector` | Dark rate [e⁻/s], pixel pitch [µm], operating temperature [K] | Detector noise terms [e⁻ RMS], detector-aperture / diffusion / IPC MTF |
| 7 | `readout` | `radiant.readout` | Read noise [e⁻ RMS], gain [e⁻/DN], ADC bits [--], TDI stages [--] | Digitized signal [DN], read/quantization noise [e⁻ RMS], TDI MTF |
| 8 | `calibration` | `radiant.calibration` | Calibration scheme, NUC residual terms | Post-NUC residual noise [e⁻ RMS], bias budget [--] (fractional $\Delta L/L$) |
| 9 | `performance` | `radiant.performance` | Everything above | SNR [--], NEDT [K], NIIRS [--], system MTF [--], detection range [m] |

The stage names in the first column are the literal keys of
`ChainResult.stage_outputs` and the entries of `ChainResult.history`, verified against
`radiant.api.session.RadiantSession.stage_names`.

Two ordering decisions in that table are load-bearing and are **not** free to change:

- **`spectral_integration` sits between `platform` and `detector`.** Everything above it
  carries spectral arrays of length $N_\lambda$; everything below it carries per-pixel
  scalars in e⁻ and DN. The collapse happens exactly once.
- **`calibration` runs after `readout`, not before.** Post-NUC residual fixed-pattern
  terms are appended after TDI and coadd scaling, which is precisely what makes them
  structurally exempt from $\sqrt{N}$ averaging. Moving the stage earlier would silently
  average away the error the stage exists to model (ADR-0012).

### Stages are pure functions

Every stage implements one method:

```python
def run(self, state: ChainState, params: ParameterSet) -> ChainState: ...
```

A stage does not mutate its inputs, does not read or write files, does not call another
stage, and holds no state between runs. All inter-stage communication flows through
`ChainState`, a frozen dataclass that stages extend with `with_frame(...)`,
`with_noise(...)`, `with_mtf(...)`, and `with_stage_output(...)`. Fields added by an
earlier stage are never removed or overwritten by a later one, so the final state is a
complete audit record of the run.

File I/O happens *before* the chain: the atmosphere model, the optical-element list, a
tabulated QE curve, a Zernike wavefront, and a $C_n^2$ profile are all built by the
API layer and injected as pre-chain stage outputs. The full mechanism is in Part 3,
"Signal-Chain Internals".

---

## 2. Radiometric Regimes

RADIANT classifies every scene into one of three radiometric regimes, because the signal
equation is genuinely different in each:

| Regime | Condition | Signal model |
|--------|-----------|--------------|
| `extended` | Target fills the pixel footprint | Radiance-based; no `EE_box` term |
| `sub_pixel` | Target fills part of the pixel | Target term weighted by fill fraction and `EE_box`; background pedestal fills the remainder and is **not** `EE_box`-weighted |
| `point_source` | Angular extent much smaller than the IFOV | Intensity-based [W/sr]; `EE_box` applied once |

Classification is **tentative** in `SourceStage`
(`stage_outputs["source"]["regime_tentative"]`) and **final** in `OpticsStage`
(`stage_outputs["optics"]["regime"]`), because the decision needs the diffraction PSF
diameter, which does not exist until the pupil has been built. Every downstream stage
reads the optics value. No stage re-classifies.

`source.regime_override` forces a regime when the analyst knows better than the detection
rule.

---

## 3. The Dual Spatial Path

RADIANT maintains **two** parallel spatial descriptions, both rooted in the *same*
complex pupil function. This is the single most frequently misunderstood part of the
architecture, and it exists because spatial-domain metrics and frequency-domain budgets
have genuinely different natural homes.

### Path A — the PSF path (spatial domain)

Every spatial degradation enters as a convolution kernel on one `EffectivePSF` object:
the diffraction-and-aberration PSF from the pupil, then the detector aperture kernel,
then jitter, smear, turbulence, diffusion, and IPC. Ensquared energy (`EE_box`), RER,
FWHM, Strehl ratio, LSF, and ERF are computed **only** from that one object.

Strehl ratio is the degraded-PSF peak divided by the diffraction-limited
`reference_psf` peak, with the same detector kernels applied to both so detector effects
cancel. The analytic Maréchal approximation survives only as a separate `strehl_marechal`
diagnostic — it is not the reported Strehl.

`EE_box` is computed in `PlatformStage` from the fully degraded PSF (jitter, smear, and
turbulence already folded in) and applied once, in `SpectralIntegrationStage`.

### Path B — the MTF product path (frequency domain)

Optical MTF comes from the **autocorrelation of the complex pupil function**. By the
Wiener–Khinchin theorem this equals $|\mathcal{F}\{\text{PSF}\}|$, but computing it
directly from the pupil is what makes it correct: aberrations interact with diffraction
*inside* the pupil and cannot be factored. Writing

$$\text{MTF}_\text{optics}(\nu) = \text{MTF}_\text{diffraction}(\nu) \times \text{MTF}_\text{aberration}(\nu)$$

is wrong, and RADIANT never does it. There is one `MTF_optics` term.

Each downstream contributor — detector aperture, jitter, smear, diffusion, IPC,
turbulence — supplies an analytic or kernel-derived MTF, and the system MTF is their
product:

$$\text{MTF}_\text{sys}(\nu) = \prod_i \text{MTF}_i(\nu)$$

MTF budgets, MTF-at-Nyquist, folded MTF, and GIQE/NIIRS all consume this path.

One term is deliberately MTF-only: **TDI mis-registration**. It is a readout-timing
effect with no spatial kernel, so it enters the product and is excluded from the
cross-path comparison below.

### The consistency invariant

Both paths start from the same pupil, so the FFT of the convolved `EffectivePSF` must
agree with the MTF product. `radiant.performance.consistency_check` verifies this on
every chain execution in which the spatial path is computed:

| Property | Value |
|----------|-------|
| Default absolute tolerance | $2 \times 10^{-2}$ (dimensionless MTF units) |
| Worst measured full-chain residual | $\sim 1 \times 10^{-2}$ (dimensionless) — about 2× margin |
| Comparison band | At and below detector Nyquist only |
| Excluded terms | TDI mis-registration (MTF-only by construction) |
| Failure behavior | Logged warning |

A failure means a degradation was added to one path and not the other. The check is
skipped only when the analyst deselects the entire Spatial-MTF metric group *and* no
enabled metric needs a spatial input — there is then no spatial computation to check.

---

## 4. Geometry-First Design

Geometry is Stage 0, not a helper called from inside the radiometry. Every downstream
stage that needs a range, an angle, a GSD, or a ground speed reads it from
`stage_outputs["geometry"]`; nothing recomputes it locally.

The analyst does not have to supply the geometry in one canonical form. Geometry accepts
**input modes**, grouped into four independent families. Exactly one mode per family is
active, and the stage solves the spherical viewing triangle from whichever door was used
(`radiant.api.geometry_modes.MODE_FAMILIES`):

| Family | Mode | Driving parameter(s) |
|--------|------|----------------------|
| viewing | `V0` | `geometry.target_range_m` [m] |
| viewing | `V1` | `geometry.path_zenith_rad` [rad] |
| viewing | `V2` | `geometry.sensor_off_boresight_rad` [rad] |
| viewing | `V3` | `geometry.ground_range_m` [m] |
| viewing | `V4` | `geometry.elevation_angle_rad` [rad] |
| solar | `S1` | `geometry.solar_zenith_rad` [rad] |
| solar | `S2` | `geometry.solar_elevation_rad` [rad] |
| solar | `S3` | `geometry.site_latitude_rad` [rad], `geometry.day_of_year` [--], `geometry.local_solar_time_h` [h], `geometry.ltan_h` [h] |
| kinematics | `direct` | `geometry.ground_speed_m_s` [m/s] |
| kinematics | `circular` | `geometry.circular_orbit` [--] (derives speed from altitude) |
| LOS rate | `K0` | none — static line of sight |
| LOS rate | `K1` | `geometry.los_angular_rate_rad_s` [rad/s] |
| LOS rate | `K2` | `geometry.target_speed_m_s` [m/s], `geometry.target_heading_rad` [rad], `geometry.target_climb_rad` [rad] |

Because the families are independent, a ground-to-air scenario (up-looking `V4`
elevation, `K2` target kinematics) and a nadir mapping pass (`V1` path zenith, `circular`
orbit) use the same solver with no special cases. The full contract is ADR-0006 and
ADR-0011.

---

## 5. Units, Provenance, and the Stable Surface

**Units convert exactly once**, at a boundary: `params.set()` for user input, or a file
reader for external data (the MODTRAN reader's $\times 10^4$ for W/cm² → W/m² is the
canonical example). Inside a physics module, a `* math.pi / 180` or a `* 1e4` is a bug
unless it is computing physics. Canonical internal units: wavelength in µm, angles in
rad, time in s, length in m, radiance in W/m²/sr/µm, noise in e⁻ RMS. The next chapter
gives the full table.

**Provenance is mandatory and cannot be disabled.** Every `ChainResult` carries
`to_provenance_record()`: run ID, RADIANT version, git commit, Python version, dependency
versions, the fully resolved parameter set with per-parameter provenance, SHA-256 hashes
of every consumed input file, and the ordered list of stages that ran. Given that record,
the run reproduces.

**The stable surface is small.** The top-level `__all__` of `radiant` is
`{Sensor, RadiantError, __version__}`; `Sensor` and `RadiantError` carry stability
guarantees.
`ChainResult` is importable from `radiant.io.results` (and re-exported from
`radiant.api`) but is not top-level. `BatchRunner` is a semi-public
`radiant.api.batch` class. There are no `SensorConfig` or `ScenarioConfig` builder
classes — ADR-C dropped them because `Sensor.from_yaml()` and `Sensor.from_dict()`
already accept the same data. Anything under `radiant.core.*` or an individual stage
package is internal.

---

## 6. Where to Go Next

| You want to | Read |
|-------------|------|
| Drive RADIANT from Python | "Scripting Guide", this volume |
| Drive it from a terminal | "Command-Line Interface", this volume |
| Write or read a config file | "Configuration Guide", this volume |
| Look up a parameter | "Parameter Reference", this volume (generated from the schema) |
| Catch and interpret an error | "Error Taxonomy", this volume |
| Understand the physics | *RADIANT Theory Manual* (Volume I) |
| Implement a stage or parameter | Part 3 of this volume, and "Extending RADIANT" |
