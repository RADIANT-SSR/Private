# Overnight Blockers Log

Started: 2026-04-07 evening session
Scope: Tasks 2B.2, 2B.3, 2B.4
Rule: If a task blocks on a contradiction with the architecture docs
that I cannot resolve safely, log it here with full context and move
on. Jason will review in the morning.

## How to read an entry

Each entry has:
- **Task / file** — where the issue arose
- **What I hit** — the contradiction or missing information
- **What I did** — skipped / partial / worked around
- **What I need from you** — the decision you need to make
- **Context** — links to the relevant docs or code

---

## 2026-04-07 — 2B.2 SimpleAtmosphere `L_path` (single-scatter) — RESOLVED 2026-04-08

- **Resolution**: Added `radiant.core.solar` with
  `toa_solar_spectral_irradiance` / `toa_solar_equivalent_radiance`
  (option 1 in the original plan). The model is a 5778 K blackbody
  scaled via a cached integral calibration so that ``∫ E_sun dλ = S_0
  = 1361 W/m²`` to 1e-5. Added `R_sun_m`, `au_m`,
  `S_solar_W_per_m2` to `radiant.core.constants`.
- **What's wired now**: `SimpleAtmosphere.build_state` computes the
  §3.1 single-scatter form
  ``L_path(λ) = L_sun(λ) · μ₀ · ω₀(λ) · P(Θ) · (1 − τ_atm(λ))``
  using a weighted two-component phase function: Rayleigh for the
  molecular component and Henyey-Greenstein (``g = 0.7``) for the
  aerosol, weighted by their scattering cross-sections and the
  aerosol single-scattering albedo. ``ω₀`` is the extinction-weighted
  column single-scattering albedo (molecular pure scatter + aerosol
  `ω_aer · σ_aer` over total extinction including H₂O absorption).
- **Geometry change**: `AtmosphericGeometry` gained a
  `cos_scattering_angle()` method. The existing `solar_zenith_rad`
  and `solar_azimuth_rad` fields (unused at 2B.2) are now live;
  `solar_azimuth_rad` is documented as the **relative** azimuth
  ``Δφ = φ_sun − φ_sensor`` (only the difference matters for single
  scatter).
- **Tests added**: TOA irradiance integral recovers 1361 W/m², Wien
  peak at 0.502 µm, visible-band smoke check, spectral-shape Planck
  ratio, radiance/irradiance consistency; L_path zero at τ = 1, ratio
  check for sun-at-horizon vs sun-overhead, non-negative & finite,
  vis ≫ LWIR ordering, cos(θ_sun) monotonicity, order-of-magnitude
  anchor at 0.5 µm, cos Θ truth anchors.

## 2026-04-07 — 2B.2 SimpleAtmosphere `L_atm_down` (graybody) — RESOLVED 2026-04-08

- **Resolution**: Moved `planck_spectral_radiance` (and
  `planck_spectral_radiance_dT`) from `radiant.source.blackbody` to
  `radiant.core.blackbody`. Planck is a pure physical formula with no
  sensor or chain knowledge and fits cleanly in `core/`. All importers
  updated; no compat shim left behind.
- **What's wired now**: `SimpleAtmosphere.build_state` computes
  `L_atm_down(λ) = (1 − τ_atm(λ)) · B(λ, T_atm_eff)` with
  `T_atm_eff` from a closed-form lookup: per-profile sea-level
  temperature (us_standard, tropical, midlat_summer/winter,
  subarctic_summer/winter), 6.5 K/km tropospheric lapse rate, ICAO
  tropopause clamp at 216.65 K, evaluated at `0.5 · sensor_altitude`.
- **Tests added**: zero-τ exo case → zero downwelling; bounded by
  Planck curve; opaque-limit truth anchor (τ → 0 at 6.3 µm H₂O band
  with heavy pwv → L_atm_down → B); profile temperature ordering
  (tropical > subarctic winter at fixed geometry); T_atm_eff lookup
  anchor; standard_atmosphere enum validation.

## 2026-04-08 — 2B.4 `DetectorStage` / `Stage` protocol missing — DEFERRED TO PHASE 2C (confirmed 2026-04-08)

- **Decision (2026-04-08)**: Confirmed with Jason. Option B: keep the
  2B.1–2B.4 detector primitives as standalone tested classes, and ship
  `radiant.core.chain` + all stage wrappers (`SourceStage`,
  `AtmosphereStage`, `OpticsStage`, `DetectorStage`, `ReadoutStage`,
  etc.) together as a single Phase 2C push. Rationale: `core.chain`
  touches every stage's contract (ChainState field layout, regime
  finalisation per Rule 10, spectral integration coupling per Rule 8),
  so designing it against a single consumer would lock in decisions
  without the other seven stages to pressure-test them.
- **Carry-forward for Phase 2C** — the chain scaffold must land before
  any stage wrapper:
  1. `radiant.core.chain`: `Stage` Protocol, frozen `ChainState` with
     `with_frame` / `with_noise` / `with_mtf` / `with_stage_output`
     methods (Rule 7), `ChainRunner`.
  2. `radiant.core.radiometry`: `RadiometricFrame`, `NoiseTerm`.
  3. Then wire stage wrappers on top of the existing primitives:
     - `source/stage.py` over `ThermalSource` etc.
     - `atmosphere/stage.py` over `SimpleAtmosphere` / `ExoAtmosphere`
     - `optics/stage.py` — owns regime finalisation (Rule 10)
     - `detector/stage.py` over `qe` / `pixel` / `shot_noise` /
       `dark_current` (+ mtf_terms registration)
     - `readout/stage.py` over `read_noise` / `adc`
  4. Parameter schemas (`_schema.py`) already exist per stage; wire
     them into `ChainRunner` stage registration.
- **What's shipped today**: `qe.py`, `pixel.py`, `shot_noise.py`,
  `dark_current.py`, `readout/read_noise.py`, `readout/adc.py` — all
  standalone, fully tested. No stage wrapper, no ChainState wiring.
- **Context**:
  - [docs/RADIANT_Signal_Chain_Architecture.md](docs/RADIANT_Signal_Chain_Architecture.md)
    §2 for the Stage protocol signature.
  - [src/radiant/core/](src/radiant/core/) — current core surface (no
    `chain.py` yet).

## 2026-04-08 — 2B.4 QE library tables not yet shipped — RESOLVED 2026-04-08

- **Resolution**: Dropped the notion of a built-in QE library entirely.
  Jason clarified that QE is specified by the user in exactly one of
  two ways: a scalar value or a wavelength-vs-QE table. No canned
  materials, no Fermi-edge warping, no `data/detectors/` directory.
- **What's wired now**: `QuantumEfficiency` keeps two factory
  classmethods:
  - `QuantumEfficiency.constant(value, lam_min_um=0.1, lam_max_um=30.0)`
    — scalar QE, stored internally as a two-point flat `SpectralData`
    table spanning a wide wavelength range so any reasonable
    evaluation grid stays inside the table.
  - `QuantumEfficiency.from_spectral(data)` — wraps a user-supplied
    `SpectralData` QE curve.
- **Removed**: The `parametric(peak, cuton_um, cutoff_um, rolloff_um)`
  Fermi-edge factory and all its tests are gone (CLAUDE.md "no
  speculative abstractions"). Detector schema dropped
  `detector.qe_peak` / `qe_cuton_um` / `qe_cutoff_um`; added
  `detector.qe_value` (scalar) and `detector.qe_table_path` (path to
  a wavelength-vs-QE table, to be loaded by `SpectralDataStore`).
  Exactly one must be set; the XOR will be enforced by a
  `ConsistencyGroup` on the detector stage wrapper when `core.chain`
  lands in Phase 2C.
- **Tests**: 17 tests in `test_qe.py` — constant factory (flat
  evaluation, two-point table layout, bounds validation, value
  validation, peak_qe identity), `from_spectral` wrap, out-of-range
  raise, linear interpolation truth anchor, band-averaged QE flat-top
  anchor, constant and spectral round-trips, photon_energy truth
  anchors.
- **Context**:
  - [docs/RADIANT_Detector_Complete.md](docs/RADIANT_Detector_Complete.md)
    §3.1 (library-curve language is now out of scope for RADIANT;
    users bring their own QE).
