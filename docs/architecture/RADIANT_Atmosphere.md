# RADIANT Atmosphere

**Status**: Authoritative — first design pass, unified
**Scope**: All atmospheric propagation between the target and the entrance pupil. Anything that produces a `SpectralTransmittance`, a `SpectralPathRadiance`, or an atmospheric MTF term for the chain to consume.
**Sister documents**: RADIANT_Conventions.md, RADIANT_Parameter_System.md, RADIANT_Signal_Chain_Architecture.md, RADIANT_Source_Target_System.md

---

## 1. Design Philosophy

The atmosphere module has one job: **deliver an `AtmosphericState` to the chain**. Everything in this document — Beer-Lambert exponentials, US Standard profiles, MODTRAN tape7 parsing, slant-path geometry, Kolmogorov turbulence — exists to populate that single contract.

Five guiding rules:

1. **One contract, four input paths.** A user may specify the atmosphere by simple parametric model, by tabulated transmittance/path-radiance, by MODTRAN run, or by declaring the path exo-atmospheric (τ ≡ 1, L_path ≡ 0). All four paths produce the **same** `AtmosphericState`. The chain has no idea which path was used.
2. **Three spectral outputs, always.** Every model, including exo-atmospheric, returns `τ_atm(λ)`, `L_path(λ)` (upwelling path radiance — what the sensor sees added to the target on its way through the atmosphere), and `L_atm_down(λ)` (hemispheric downwelling **irradiance**, used by the reflected-diffuse terms of the target and ground-background arms). The `SkyBackground` descriptor consumes a different product — a directional radiance along the LOS continuation, §4.2g — not this one. Numerical zero is preferable to a model-dependent `None`.
3. **Geometry is an input, not a model property.** Slant range, sensor altitude, target altitude, path zenith angle, and solar zenith are all geometry inputs to *every* atmosphere model. The model decides how each input affects its outputs; the user does not pre-bake geometry into a tabulated file.
4. **Turbulence is profile-driven, and off by default.** The Kolmogorov long-exposure MTF takes a Fried parameter $r_0$, which the user may enter directly (`atmosphere.r0_m`, the default path) or have RADIANT derive from a $C_n^2(h)$ profile integrated along the line of sight (`atmosphere.cn2_profile`; Gap 110, §7). Anisoplanatism, scintillation, short-exposure MTF, and the von Kármán outer scale remain out of scope. There is **no observer-type gate**: a space observer's path simply carries no atmospheric column, so the integral is negligible and the term is omitted — a computed answer, not a refusal (ADR-0011 guardrail G4).
5. **MODTRAN is a wrapped tool, not an embedded library.** RADIANT writes a card deck, calls a `modtran` binary, parses tape7, and caches the result keyed by a hash of the deck. If the binary is missing, the cache is consulted; if the cache misses, a clear error is raised. RADIANT itself never tries to *be* MODTRAN.

---

## 2. The `AtmosphericState` Contract

> **Implementation reality (reconciled 2026-07-12).** The shipped
> `AtmosphericState` (`atmosphere/protocol.py`) is a frozen dataclass with **five
> fields**: `transmittance`, `path_radiance`, `atm_emission_down` (all
> `SpectralData`), `geometry` (`AtmosphericGeometry`), and `derivation_chain`.
> The additional fields in the block below — `model`, `cache_key`, `air_mass`,
> `slant_path_length_m`, `turbulence`, `native_output` — are **design-target,
> deferred to a later phase** (the class docstring says so explicitly).
> Consequently invariant 3 (`air_mass`/`slant_path_length_m` stored on the state)
> and invariant 4 (`turbulence` field) below describe intended, not shipped,
> behavior. `AtmosphereModel` is not a shipped enum type; the model is selected by
> the `atmosphere.model` **string** parameter, whose five legal values are
> `simple`, `exo`, `tabulated`, `modtran`, `interpolated` (§3).

```python
# The `model`/`cache_key`/`air_mass`/`slant_path_length_m`/`turbulence`/
# `native_output` fields below are DESIGN-TARGET — see the banner above.
@dataclass(frozen=True)
class AtmosphericState:
    """Everything the chain needs to know about the atmospheric path.

    Produced by exactly one of the four input paths. Immutable.
    The chain consumes this and never inspects how it was built.
    """

    # ---- Identification & provenance --------------------------------------
    model: AtmosphereModel               # SIMPLE | TABULATED | MODTRAN | EXO_ATMOSPHERIC
    derivation_chain: tuple[str, ...]    # human-readable build steps
    cache_key: str | None                # populated for MODTRAN; None otherwise

    # ---- Spectral outputs (always present, always on the global grid) -----
    transmittance: SpectralTransmittance     # τ_atm(λ), dimensionless [0,1]
    path_radiance: SpectralPathRadiance      # L_path(λ), upwelling, W/m²/sr/µm
    atm_emission_down: SpectralPathRadiance  # L_atm_down(λ), downwelling, W/m²/sr/µm

    # ---- Geometry the model was evaluated for ----------------------------
    geometry: AtmosphericGeometry        # slant path, zenith, altitudes, solar geometry
    air_mass: float                      # computed from zenith angle (≥ 1, ∞ at horizon)
    slant_path_length_m: float

    # ---- Turbulence: not carried on this bundle.  The resolved Fried
    #      parameter travels as stage_outputs['atmosphere']['r0_m'] (§7.1).

    # ---- Optional: native model output for debugging ---------------------
    native_output: ModtranNativeOutput | None  # tape7 parsed dataclass
```

**Invariants:**

1. `transmittance`, `path_radiance`, and `atm_emission_down` are **all** populated, even when one is "not physical" for the model. For `EXO_ATMOSPHERIC`, transmittance is unity at every wavelength and the two radiance fields are zero.
2. All three spectral arrays live on the global wavelength grid in `SpectralDataStore` before `AtmosphericState` is constructed. Wavelength alignment is enforced at construction, not at consumption.
3. `air_mass` and `slant_path_length_m` are derived from `geometry` at construction and stored for downstream use (NEDT and detection-range calculations want them).
4. The turbulence MTF term exists only when the resolved Fried parameter is positive (§7). There is no observer-type restriction: `radiant.atmosphere.r0_path` integrates whatever atmospheric column the line of sight actually crosses, so a space observer's residual column yields a huge $r_0$ and the term is omitted entirely. The pre-Gap-110 "the parameter resolver rejects turbulence for a space observer with a `ScopeError`" rule is **retired** (ADR-0011 guardrail G4 / Rule 27).

---

## 3. The Unified Input Paths

> **Five models, not four.** In addition to the four paths below, a fifth model —
> `interpolated` (`atmosphere/interpolated.py`, `InterpolatedAtmosphere`) — serves
> `AtmosphericState` by interpolating between pre-computed MODTRAN runs at discrete
> geometry points. It is file-backed (`FILE_BACKED_MODELS`, §8.1) like `tabulated`.
> Transmittance interpolates in log-τ (optical-depth) space; **zenith-angle axes
> additionally interpolate in airmass sec(θ) space** (CU-160) — Beer-Lambert-exact
> between nodes, validated by a 45° holdout against the real MODTRAN B-fan (−0.1%
> band-mean τ vs −4% under the earlier linear-in-angle axis). Zenith nodes ≥ ~88.8°
> are refused (sec diverges at the horizon).
> **Query wavelength grid (CU-156, lifted 2026-07-18):** `build_state` serves any
> query grid inside the stored spectral range by resampling the
> geometry-interpolated spectra (the `TabulatedAtmosphere` pattern); a query
> extending outside the stored range fails loud — no spectral extrapolation.
> **That resample runs in log-τ for transmittance (CU-306, 2026-08-01)** — the
> same optical-depth space the geometry interpolation uses — so the two
> operations are both linear in ln(τ), commute, and the answer no longer depends
> on their order. Resampling linearly in τ instead cost up to ~2.8% relative τ
> at off-node query wavelengths, i.e. on every chain grid that differs from the
> stored one. `L_path` and `L_atm_down` resample **linearly**: they are additive
> emission terms with no Beer-Lambert exponential in path length. τ = 0 bands are
> safe in log space by construction — the constructor floors stored τ at
> `TAU_FLOOR` (1e-30 ≡ OD ≈ 69) before taking the log, so ln(τ) is finite
> everywhere and an opaque band resamples to that floor, never to −inf or NaN.
> Note the scope: `tabulated` and `modtran` still resample τ linearly (one
> resample, no operation order to get wrong).
> **Airborne targets (Gap 94):** when the grid carries a `target_altitude_m` axis
> (the shipped `midlat_summer_ladders/` family), `evaluate()` serves `h_tgt > 0`
> with a real two-leg split from two queries at the same sensor/zenith coordinates —
> up leg (`τ_up`, `L_path_up`) at `target_altitude_m = h_tgt`, full column
> (`τ_full_up`, `L_path_full`) at `target_altitude_m = 0`; `L_atm_down` comes from
> the target-local (up-leg) query. No extrapolation: an `h_tgt` beyond the grid's
> target hull (ladders: 0–29 km) is refused. Without a target axis, `h_tgt > 0`
> raises `NotImplementedError` — one column cannot supply both legs.
> **Non-axis query geometry is never silently substituted (CU-167):** a query
> field that is not an interpolation axis is served with the sample runs'
> geometry; when the query departs from the recorded per-point value (or, for
> LOS zenith on data that records none, the assumed-nadir run geometry) beyond
> ~1° / 1 m, a `UserWarning` names the ignored field and the value actually
> served. A *recorded* non-axis field that varies across sample points is
> refused at construction — the set differs in a dimension the interpolator
> would ignore. Two physics-aware refinements (2026-07-20, boost plan §4.6):
> a query **sensor above a recorded at-/above-TOA (100 km) sensor** is exempt
> from the mismatch warning — the added path is vacuum and the column exactly
> identical (the same identity behind the ladders' 40,000 km duplicate node);
> and a **pure-thermal scene** (`theta_s = None` — no solar geometry declared)
> adopts the recorded run sun in `evaluate()` rather than a literal 0.0, so it
> cannot spuriously mismatch — an explicitly set solar geometry is still
> compared and warned. The shipped `data/atmospheres/` NPZs record the full
> five-field run geometry on every file (see the library MANIFEST), so these
> checks compare against recorded values, not assumptions.
> **Family direction (GF-10, 2026-07-26):** a family is tagged `down` (default,
> upwelling products) or `up` (downwelling products) at construction, from the
> `los_direction` marker on its NPZ files. `evaluate()` — the eight-field
> down-looking bundle — refuses an up-looking family, and
> `uplooking_column_product()` — the segment product for an up-looking observer
> leg — refuses a down-looking one. The up-looking query takes its lower endpoint
> from `los.h_sensor` (guardrail G2), interpolates 1-D over target altitude in
> the same log-τ space — and, since CU-306, resamples onto the chain grid in
> that space too — and refuses an off-vertical or elevated-endpoint query
> rather than approximating it (§4.2b).
> The diagram and subsections below predate it; treat `interpolated` as a sixth box
> feeding the same single `AtmosphericState` contract.

```
              ┌──────────────────────────────────┐
              │     User configuration           │
              └──────────────────────────────────┘
                              │
       ┌──────────┬───────────┼──────────┬──────────────────┐
       ▼          ▼           ▼          ▼                  ▼
  ┌────────┐ ┌─────────┐ ┌─────────┐ ┌──────────┐
  │ Simple │ │Tabulated│ │ MODTRAN │ │   Exo-   │
  │paramet.│ │ τ, L    │ │ tape7   │ │atmosphr. │
  └────┬───┘ └────┬────┘ └────┬────┘ └─────┬────┘
       └──────────┴──────┬────┴────────────┘
                         ▼
              ┌───────────────────────┐
              │   AtmosphericState    │
              │  (single contract)    │
              └───────────────────────┘
                         ▼
                  AtmosphereStage
```

### 3.1 Simple parametric

A closed-form Beer-Lambert model with three knobs that map to the things a working radiometrist actually has on hand: visibility, humidity, and aerosol type. Suitable for trade studies, scoping, regression tests, and any case where the user does not have a MODTRAN license or cares more about gradient than absolute accuracy.

```
τ_atm(λ) = exp[ −OD_total(λ) · air_mass ]
OD_total(λ) = OD_mol + OD_aer + OD_h2o(λ; w) + OD_gas(λ)
```

- **Molecular (Rayleigh)**: the published constant is a **total vertical optical depth**, not a per-km coefficient — τ_R,vert(λ) = 0.0088 · λ_µm⁻⁴·⁰⁹ (dimensionless; 0.1015 at 550 nm, matching the published whole-atmosphere value of 0.0973–0.10, Hansen & Travis 1974 / Bucholtz 1995). The sea-level volume extinction the slant-path integral needs is *derived* from it through the exponential profile's own identity τ_vert = σ₀·H_mol, i.e. σ_mol(λ) = τ_R,vert(λ) / H_mol ≈ 0.0127 km⁻¹ at 550 nm (published ≈ 0.0116 km⁻¹); it is then scaled along the path by `exp(−h/H_mol)` with H_mol = 8 km. **CU-253**: this line previously read the published OD as though it were the km⁻¹ coefficient, which inflated every VIS/NIR molecular optical depth by exactly the column depth (≈ 8×). Deriving σ₀ rather than storing it separately is what keeps the two from drifting apart again.
- **Aerosol (Mie)**: σ_aer is fit from the Koschmieder visibility relation `σ_aer(550 nm) = 3.912 / V_km`, with a wavelength dependence drawn from one of three canonical Ångström exponents: `rural` (α = 1.3), `urban` (α = 1.5), `maritime` (α = 0.7). Aerosol scale height is 1.2 km.
- **Water vapor (CU-161, recalibrated 2026-07-17)**: a 15-region curve-of-growth model, `OD_h2o = k(λ) · w_eff^b(λ)`, where `w_eff` is the path water amount (total precipitable water × the traversed fraction of the H_h2o = 2 km exponential column). Fit region-by-region against the real MODTRAN 6 water ladder (D4/A1/D5, H₂O ×0.5/×1/×2): sub-linear `b ≈ 0.2–0.8` in the saturated absorption bands, super-linear `b ≈ 1.3–1.75` in the LWIR where the e-type continuum dominates. Replaces the original five-Lorentzian fit whose far wings made the MWIR water response ~5× too steep (the defect scenarios 6.2/1.1/3.2 quantified). Generator: `scripts/fit_simple_atmosphere_gas_bands.py`; anchors pinned in `test_simple.py::test_cu161_water_ladder_anchor`.
- **Well-mixed gases (CU-161, new)**: a water-independent absorption floor per region (CO₂ 4.3/15 µm, N₂O, O₃ 9.6 µm, O₂/CH₄ overtones) on the molecular scale height — e.g. band-mean OD 0.45 in the MWIR, 1.35 at 5–7.5 µm. The term whose absence made the pre-CU-161 model attribute the MWIR CO₂ floor to water (effective ω₀ ≈ 1 for space columns, Gap 38; the gas term now also enters the ω₀ denominator as a pure absorber). Spectral shape within a region is flat — the model's contract is band-integrated fidelity, not line structure.
- **Region-edge blend (CU-267, 2026-08-01)**: the fitted table is piecewise-constant, but it is **not read as a step function**. Across each of the fourteen interior region edges the three coefficients `(floor_od, k_h2o, b_h2o)` are joined by a C¹ smoothstep ramp of half-width `GAS_REGION_BLEND_HALF_WIDTH_UM = 0.02 µm` (full width 0.04 µm):

$$u(\lambda) = \mathrm{clip}\!\left(\tfrac{1}{2} + \frac{\lambda - \lambda_{\text{edge}}}{2\,h_w},\,0,\,1\right), \qquad S(u) = u^2\,(3 - 2u), \qquad c(\lambda) = c_{\text{lo}} + (c_{\text{hi}} - c_{\text{lo}})\,S(u)$$

  with $S(0)=0$, $S(1)=1$, $S'(0)=S'(1)=0$ (the ramp meets the flat calibrated regions with matching value *and* slope) and $S(0.5)=\tfrac12$ (the edge itself carries the two regions' mean). Outside the ramps nothing changes: a λ at or beyond $h_w$ from every edge keeps the bit-identical calibrated coefficient, so a band crossing no edge is unaffected. Every region is wider than $2 h_w$ (narrowest 0.20 µm at 1.30–1.50 µm), so no two ramps overlap — the invariant is pinned by `test_gas_region_blend.py::test_blend_ramps_never_overlap`, which is what stops a future refit from silently invalidating the blend. Read literally the step table made τ(λ) jump at every edge (−90 % at 2.40 µm, +821 % relative at 8.00 µm) and made a band-mean τ that straddled an edge **sampling-grid-dependent** (1.83 % between N = 31 and N = 1001 on 3.0–5.0 µm; exactly 0 on bands crossing no edge). Adopting the blend moved band-mean τ_up by −0.20 % (0.5–0.8 µm), −0.12 % (0.4–0.9), −0.71 % (3.0–5.0), −0.27 % (8–12), −0.21 % (8–14), −0.19 % (11.5–12.5), and by exactly 0 on 3.7–4.8 and 10.6–11.2 µm.

Cross-validated against the five non-calibration profile anchors (A2–A6) to ≤ ±0.012 band-mean τ in the water-relevant windows. **Known fragilities** (documented, unfixed): region-flat spectral shape (no 4.3 µm notch structure) away from the 0.04 µm edge ramps; the airmass factor stays linear while real saturated bands grow sub-linearly off-nadir (measured: MWIR OD ×1.18 at 45° vs Beer's ×1.41); λ outside 0.30–14.29 µm clamps to the edge regions' calibration; VIS aerosol absolute OD remains ~2× high at rural-23 (scenario 3.4's finding — aerosol was deliberately not recalibrated here). The edge ramp removes the *discontinuity*, not the underlying region-flat approximation: a spectral feature narrower than 0.04 µm sitting on a region edge is still not resolved, and a band-mean sampled more coarsely than the 0.04 µm ramp width still under-resolves the ramp itself.

**Path radiance** for the simple model uses a single-scatter approximation:
```
L_path(λ) = [E_sun(λ) / (4π)] · cos(θ_sun) · ω₀(λ) · P(θ_scatter) · [1 − τ_atm(λ)]
```
where `E_sun(λ)` is the TOA solar spectral irradiance and the `4π` is the full-sphere phase function normalization. With `ω₀ = 0.95` (rural), `0.85` (urban), `0.99` (maritime), and a Henyey-Greenstein phase function with `g = 0.7` (`simple.HG_ASYMMETRY`). This is good to ±30% in VIS/SWIR and is intentionally crude; users who need better path radiance use MODTRAN.

**Atmospheric thermal emission** for the simple model uses a target-anchored graybody (CU-155, recalibrated 2026-07-18):
```
E_sky_thermal(λ) = [1 − τ_sky,vert(λ)^D] · π · B(λ, T(h_tgt + z_em))
L_atm_down(λ)    = E_sky_thermal(λ) / π        (hemispheric-mean radiance)
```
where `τ_sky,vert` is the **vertical** transmittance of the **target→h_atm_top** column (the sky the target actually sees — the sensor's altitude and viewing zenith deliberately do not enter a hemispheric flux at the target), `T(·)` is the fixed-lapse ICAO standard-atmosphere lookup (floored at the 216.65 K tropopause), and the two constants are fit jointly to the real MODTRAN 6 up-looking H-runs (H2 us_standard + H4 tropical, LWIR + MWIR band integrals): emission-height offset `z_em = 200 m` (downwelling is dominated by near-surface air; the E1 flux DOWN at 14.4 µm ≈ π·B(283 K)) and flux-diffusivity exponent `D = 1.1` (below the textbook Elsasser 1.66 because the CU-161 τ calibration to slant paths already absorbs part of the hemispheric weighting).

> **Measured accuracy (CU-155, resolved 2026-07-18):** band-integrated model/MODTRAN ratios at the fit — H2 LWIR 1.24, H2 MWIR 0.70, H4 LWIR 1.41, H4 MWIR 1.34, versus 0.21 / 0.02 / 0.21 / 0.03 for the pre-fix model (which evaluated `T_atm_eff` at 0.5·h_sensor and clamped every space column to the tropopause). The residual ±40% tracks the CU-161 region-flat spectral-shape fragility, not temperature structure. Parity envelope pinned in `tests/integration/test_modtran_real_runs.py`; for higher fidelity use MODTRAN-derived data (Gap 81/CU-157 for the import path's own sky terms).

**Diffuse scattered-solar sky irradiance** for the simple model (Stage 6 / ADR-0002; ω₀ recalibrated 2026-07-20, Gap 38):
```
E_sky_scattered(λ) = E_TOA(λ) · cos(θ_s) · ω₀_eff(λ, aerosol) · [1 − τ_down,vert(λ)]
```
on the same target→sensor vertical slab as `E_sky_thermal`. `ω₀_eff` is the **MODTRAN-derived effective single-scattering albedo** (`atmosphere/omega0_eff.py`): band-median values per aerosol regime (VIS 0.4–0.7 / NIR 0.7–1.4 / SWIR 1.4–2.5 µm, edge-extended outside; e.g. rural 0.791/0.698/0.187, urban 0.423/0.430/0.263), obtained by inverting this closed form against the real MODTRAN 6 ground-level diffuse-flux tables (E1/E3/E4), so it absorbs MODTRAN's multiple-scatter contribution as an effective parameter of this formula. It replaces the internal extinction-weighted column ω₀, which evaluated ≈ 1.000 for space columns and over-predicted diffuse sky irradiance ~1.3× (VIS rural) to ~5× (SWIR/urban). The internal ω₀ survives only in the phase-weighted `L_path` single-scatter integral above, where the flux-fit table is not a valid substitute. Reference table independently pinned with a re-derivation guard in `tests/integration/test_modtran_real_runs.py`. Known fragility: piecewise-constant spectral shape (steps at 0.7/1.4 µm); the fit is at θ_s = 30°, and the E2 comparison shows the cos θ_s scaling under-predicts diffuse at low sun (θ_s = 60°) — the residual sun-angle dependence is documented in gaps.md Gap 38.

**Inputs** (all parameters are user-facing; see §6):
`atmosphere.visibility_km`, `atmosphere.aerosol_type`, `atmosphere.precipitable_water_cm`, `atmosphere.standard_atmosphere`.

### 3.2 Tabulated

The user provides `τ_atm(λ)` and `L_path(λ)` as files (CSV, ENVI .sli, or NumPy .npz). RADIANT loads them, validates monotonic ascending wavelength, interpolates onto the global grid, and uses them as-is. No physics is applied. The user owns the physics.

This is the escape hatch for:
- Output from a higher-fidelity tool that is not MODTRAN (libRadtran, 6S, DIRSIG).
- Measured transmittance from an FTIR campaign.
- Unit-test fixtures and regression baselines.
- "I have a tape7 from a colleague but no MODTRAN binary." (The better answer: import it directly via `atmosphere.modtran.tape7_path`, §5.1 — no manual CSV conversion.)

`L_atm_down(λ)` is optional for tabulated input; if not supplied, it is set to zero with a logged warning. Tabulated input is geometry-agnostic — RADIANT does *not* re-scale tabulated transmittance for a different slant path. If the user changes geometry after specifying a tabulated file, the parameter resolver flags a `GeometryDrift` warning.

**Inputs**: `atmosphere.tabulated_transmittance_file`, `atmosphere.tabulated_path_radiance_file`, `atmosphere.tabulated_downwelling_file` (optional).

**Shipped nominal library (`data/atmospheres/`; base 2026-07-17, boost expansion 2026-07-20, up-looking K block 2026-07-26):** RADIANT ships a committed NPZ library derived from the real MODTRAN 6 run matrix, so `tabulated`/`interpolated` users get real-radiative-transfer atmospheres without a MODTRAN license: six standard-profile nadir columns (`profiles/`, tabulated; us_standard, tropical, and midlat_summer carry real H-run downwelling sky radiance), a us_standard LOS-zenith fan 0–60° (`us_standard_zenith_fan/`, interpolated), a midlat_summer sensor×target-altitude grid spanning 35 km–GEO × 0–29 km (`midlat_summer_ladders/`, interpolated), and the boost-expansion families for missile-defense boost-phase tracking: `midlat_summer_boost_ladder/` (space sensor × target 0–100 km, nadir), `midlat_summer_boost_offnadir/` (× LOS zenith 0/45/60°), and `midlat_summer_sensor_ladder/` (airborne→space sensor 3 km–GEO, ground target). The 100 km TOA states are duplicated at a 40,000 km node so orbital sensors fall inside the interpolation hull (vacuum above TOA makes the duplication exact), and each boost family's 100 km target rung is a **synthesized exact vacuum node** (τ ≡ 1, L_path ≡ 0 — a physical identity, present at every zenith column) closing the hull to the Gap 95 exo handoff. All midlat_summer families carry the H5 48.2° downwelling. Slit-degraded to 5 cm⁻¹ FWHM; full per-file provenance, the CO₂-band-core rationale, packaging decisions, the elevated-target downwelling simplification (CU-181), and known limitations in `data/atmospheres/MANIFEST.md`. Asserted by `tests/integration/test_shipped_atmosphere_library.py` and `tests/integration/test_exo_target_chain.py`. **Up-looking family (GF-10, 2026-07-26):** `midlat_summer_uplooking_ladder/` (K1–K5 + a synthesized zero-length node) is the first up-looking family — ground sensor, vertical, targets 0–20 km, carrying the *downward* path radiance under `path_radiance_toward_lower` with a `los_direction` marker; see §4.2b. **Out-of-the-box default:** `atmosphere.model = "interpolated"` with `interpolated_data_dir` unset loads the shipped family matching the scene's LOS direction and `interpolation_axes` — down-looking `path_zenith_rad` → `us_standard_zenith_fan`, down `sensor_altitude_m,target_altitude_m` → `midlat_summer_ladders`, down `sensor_altitude_m` → `midlat_summer_sensor_ladder`, down `sensor_altitude_m,target_altitude_m,path_zenith_rad` → `midlat_summer_boost_offnadir`, up `target_altitude_m` → `midlat_summer_uplooking_ladder` — with a logged notice; an explicit directory always wins, and a (direction, axes) pair no shipped family covers still requires one.

### 3.3 Exo-atmospheric

For sensors above the atmosphere observing targets above the atmosphere (typical space surveillance, satellite-to-satellite imaging, deep-space). All three spectral outputs are constants:

```
τ_atm(λ) ≡ 1.0
L_path(λ) ≡ 0.0
L_atm_down(λ) ≡ 0.0
```

This is not "no atmosphere"; it is "the atmosphere is the cosmic vacuum, and the cosmic vacuum has unity transmittance and zero path radiance to within a part in 10²⁰." The CMB contribution is delivered through `SourceStage` as a `BlackbodyBackground(T=2.7)`, not through `AtmosphereStage` (per RADIANT_Source_Target_System.md §3.7).

**Inputs**: none. Selection is implicit from `geometry.observer_type = "space"` and `geometry.target_type = "space"`. The user may explicitly request `atmosphere.model = "exo"` for any geometry, but doing so for a ground observer is a logged warning.

### 3.4 MODTRAN

The high-fidelity option, with two flavors (precedence and detail in §5). **Tape7 file import** (primary): `atmosphere.modtran.tape7_path` names a tape7 produced elsewhere; RADIANT parses it pre-chain, converts units (cm⁻¹ → µm, W/cm² → W/m², descending → ascending), and resamples onto the global wavelength grid — no binary required. **Binary invocation** (secondary, never yet exercised): RADIANT builds a MODTRAN card deck from the user's parameters and geometry, invokes the MODTRAN binary, parses the resulting tape7, and caches the converted arrays.

**Inputs**: `atmosphere.modtran.tape7_path` (file import), or for the binary flavor `atmosphere.modtran.atmosphere_profile`, `atmosphere.modtran.aerosol_model`, `atmosphere.modtran.h2o_scale`, `atmosphere.modtran.o3_scale`, `atmosphere.modtran.cloud_model`, `atmosphere.modtran.binary_path`, `atmosphere.modtran.cache_dir`, plus all `geometry.*` parameters.

---

## 4. Geometry Dependence

### 4.1 The geometry inputs

```python
@dataclass(frozen=True)
class AtmosphericGeometry:
    sensor_altitude_m: float      # height above mean sea level
    target_altitude_m: float      # height above mean sea level
    path_zenith_deg: float        # angle from local vertical at the lower endpoint
    solar_zenith_deg: float       # for downwelling and reflected-solar paths
    solar_azimuth_deg: float      # for path-radiance phase angle
    observer_type: ObserverType   # SPACE | AIRBORNE | GROUND
    target_type: TargetType       # SPACE | AIRBORNE | GROUND
```

Per RADIANT_Conventions.md §5, all angles are stored in radians internally; `_deg` suffixes mark the user-facing API contract.

### 4.2 Slant path length

Computed once at `AtmosphericGeometry` construction and stored for every model to use:

```
L_slant = Δh_absorbing / cos(ζ)          for the whole legal domain 0 ≤ ζ ≤ 89.5°
```

with `Δh_absorbing = min(|h_sensor − h_target|, h_atm_top − min(h_sensor, h_target))` — the vertical extent of *atmosphere* on the segment, not the endpoint separation (CU-255: a ground site viewing a 700 km target traverses 100 km of air, not 700 km). Air mass `m = L_slant / Δh_absorbing` is stored alongside and is therefore exactly `sec(ζ)`; `Δh = 0` (a wholly exo path) returns `m = 1` by the `ExoAtmosphere` convention.

**One formula, no branch (CU-274, 2026-07-29).** A second "spherical-Earth correction" branch used to take over past 80°:

```
L_slant = R_E · [√(cos²ζ + 2(Δh/R_E) + (Δh/R_E)²) − cos ζ]     # REMOVED
```

It was not an air mass. It is the *geometric chord* of a slab of thickness Δh on a spherical Earth, while an air mass is a density-weighted path, and with an 8 km molecular scale height the absorbing mass hugs the ground where curvature is negligible. Measured against the exact spherical slant integral (`grazing_column.grazing_slant_column_km`, molecular scale height, ground → 100 km):

| ζ | `sec ζ` | root form | exact |
|---|---|---|---|
| 30° | 1.15470 | 1.15470 | 1.15422 |
| 60° | 2.00000 | 2.00000 | 1.99258 |
| 79.9° | 5.70234 | (unused) | 5.49989 |
| 80.1° | 5.81635 | 4.80715 | 5.60209 |
| 85° | 11.47371 | 7.06683 | 10.14005 |
| 89.4° | 95.49471 | 10.68472 | 28.37722 |

The root form was 14 % low at 80.1°, 30 % at 85° and 62 % at 89.4°, and it made the air mass **drop 18 % across its own switch** — transmittance discontinuous in look angle for every scene class, on an ordinary down-looking column. Removing it makes the model continuous, monotone in ζ, and consistent with the rest of `SimpleAtmosphere`, which was plane-parallel throughout at that date (vertical columns × one air mass, mean-altitude species weights, target-anchored emission height). No shipped scenario exceeds 37.5° LOS zenith or 40° solar zenith, so nothing moved.

Accuracy past 80° is bought by **routing elsewhere**, not by patching this formula: the exact spherical slant integral is `grazing_column.py`, and callers take it at `SPHERICAL_SWITCH_RAD` = 80°. `AtmosphericGeometry.air_mass()` stays the honest plane-parallel primitive it now is; nothing calls it past 80° any more.

**Every column now takes that route (CU-224 / ex-CU-275, 2026-08-01).** The up-looking sky background hand-over landed with CU-225/CU-274; the down-looking observer column and the solar column kept `sec ζ` over their whole legal domain and therefore *overestimated* the near-horizon air mass — by +3.8 % at 80°, +13 % at 85° and +237 % at 89.4°. Both now hand over at the same 80°, through the shared `near_horizon_air_mass.py`:

| site | inside the band (ζ ≤ 80°) | past it |
|---|---|---|
| `segment_simple.column_segment_optical_depth` | `od_vert × air_mass()`, unchanged | per-species spherical |
| `SimpleAtmosphere.evaluate` — `tau_up`, `tau_full_up` | `od_vert × air_mass()`, unchanged | per-species spherical |
| `SimpleAtmosphere.evaluate` — `tau_sun` | `od_vert × air_mass()`, unchanged | per-species spherical |

Three consequences worth stating plainly.

*It is per species, not one corrected scalar.* Water vapour's 2 km profile hugs the tangent point far harder than the 8 km molecular one: at 89.4° `sec ζ` overstates molecular air by 237 % but water by only 104 %, a 2.3× divergence. Each species carries `m_i = S_i(r₀; h_lo→h_hi; H_i) / col_i`; the well-mixed-gas floor rides on `m_mol`, because CU-161 defines it as a fraction of the molecular column.

*The direction is toward more signal.* The plane-parallel form was pessimistic near the horizon, so transmittance and SNR move **up** past 80° and never down.

*It is a step, not a blend.* Straddling 80° by a thousandth of a degree on a ground → 100 km column, optical depth drops **2.0 %** (median over 0.4–14 µm; 2.9 % worst wavelength) and transmittance rises **10.6 %** median (up to 49 % where the column is nearly opaque, because τ is exponential in a large OD). That is the plane-parallel model's own error at the point where it is retired — the same shape the sky's 0.64 % radiance step has carried since CU-225, and about five times smaller *in the exponent* than the 18 % air-mass drop that got the root form deleted. Removing it entirely would mean using the spherical integral at every zenith, which moves every existing down-looking baseline and is a separate, owner-gated decision.

*The solar column's 89.5° clamp is retired with it.* The plane-parallel construction had to clamp θ_s at `ZENITH_CEILING_RAD` because `AtmosphericGeometry` refuses past it — which is the worst possible place to clamp, being exactly where `sec ζ` is most wrong. The spherical route has no ceiling, so a twilight scene at θ_s = 89.9° now gets its own column instead of the 89.5° one. `ZENITH_CEILING_RAD` still bounds `path_zenith_rad`, so the *observer* domain is unchanged.

**Anchoring status.** The spherical integral is anchored analytically (Chapman's grazing limit, `grazing_column.py`) but the near-horizon **transmittance** is not yet anchored against a MODTRAN run at those angles — the twilight/refraction calibration pair is a batch-2 deck. Refraction is also unmodelled and is the dominant geometric error inside the horizon guard's warn band, so numbers past ~85° are a better-conditioned model, not a validated one.

### 4.2a Exo-altitude targets — the vacuum target leg (Gap 95)

A target at or above the top of the atmospheric column (`los.h_tgt ≥
los.h_atm_top`, default 100 km — a satellite, a post-burnout booster, a 100+ km
hypersonic) is legal geometry (`LineOfSightGeometry` accepts any `h_tgt ≥ 0`)
and is served **model-agnostically** by the down-looking exo arm of
`atmosphere/topology.py::evaluate_path_topology`, which `AtmosphereStage` calls
in place of a bare `model.evaluate`. Since Geometry-Flexibility Phase 2 it is
expressed as the ADR-0011 **path-segment composition** it always was. The path
partitions at `h_atm_top` into a ground→target column `G` (the backend's own full
column, from a surface-target evaluation) and a vacuum target→sensor segment `V`
(`τ_V ≡ 1`, `L_V ≡ 0`, no model consulted), and the composition rules
`τ(G ∪ V) = τ_G·τ_V`, `L(G ∪ V) = L_G·τ_V + L_V` collapse by those identities to
exactly the published fields — with no arithmetic performed at all:

- `τ_up ≡ 1`, `L_path_up ≡ 0 W/m²/sr/µm`, `τ_sun ≡ 1` — exact identities (no
  absorber above the column top), not approximations; no warning is emitted.
- `τ_full_up`, `L_path_full`, `E_TOA`, and the E_sky terms come from the same
  backend evaluated at the surface-target geometry (`h_tgt = 0`, same angles) —
  the ground→sensor full column survives to the background/noise branch
  unchanged. This is a **down-looking** construction: it is the column behind
  the target, kept because a down-looking LOS continues past an exo target to
  the ground.
- **Up-looking / level exo path (ADR-0011, Geometry-Flexibility Phase 1):** when
  the sensor sits at or below the target, the LOS continues into space rather
  than to the ground. Such a path is served only when its **lower** endpoint is
  itself at or above `h_atm_top` — both endpoints outside the column, so the
  whole path *and its continuation* are vacuum and the full-column terms are the
  vacuum identities too (`τ_full_up ≡ 1`, `L_path_full ≡ 0`, `E_sky ≡ 0`,
  `E_TOA` still from `radiant.core.solar`). This is the up-looking
  space-to-space case (LEO→GEO). An up-looking path whose lower endpoint is
  still inside the column (ground/air → satellite) is **refused** — see §4.2b.
- Works for every backend, including single-column file imports (tape7,
  tabulated) that refuse endo-atmospheric elevated targets — in this regime one
  column is all the physics needs.
- Documented conflation: the single E_sky pair in `AtmosphericQuantities` still
  carries ground-level downwelling, so an exo target's reflected-diffuse term
  uses Earthshine-magnitude but ground-spectrum illumination (see the module
  docstring; negligible against plume/self emission in the driving scenarios).

> **Retirement note (guardrail G4 / Rule 27, 2026-07-26).** Before Phase 2 this
> case was served by an `evaluate_with_exo_target` *wrapper* — a function that
> called the backend at a substituted geometry and then overrode fields of the
> result. G4 requires a carve-out to become a natural case of its generalization
> and the wrapper to be deleted in the same PR, so `atmosphere/exo_target.py` is
> gone and the composition above is the only description. Because the
> composition performs no arithmetic, the fold was provably bit-identical: a
> differential run over 3 124 exo configurations compared old and new with exact
> `==`. The name survives only in retirement notes — this paragraph, the
> `atmosphere/topology.py` module docstring, and the `h_tgt` note on
> `LineOfSightGeometry` — and nothing in the live design depends on it.

`LineOfSightGeometry.slant_range_atm` returns 0 m and `path_airmass_up` the
vacuum limit 1.0 for these targets. Targets in the 29–100 km band are now
covered by real MODTRAN data — the boost-ladder run set (G7–G11, I1–I9) landed
2026-07-20 in the `midlat_summer_boost_ladder/` (nadir) and
`midlat_summer_boost_offnadir/` (0/45/60°) families, so the interpolated
backend serves a continuous τ_up from 0 km through the synthesized 100 km
vacuum rung into this exo branch (see the shipped-library note in §3.2 and the
archived `docs/archive/MODTRAN_Boost_Ladder_Expansion_Plan.md`).

### 4.2b Path direction — one source of truth, three topology arms

Since ADR-0011 (Geometry-Flexibility Phase 1) `LineOfSightGeometry` carries
**both** endpoints, and `los.h_sensor` is the **only** source of the sensor
altitude inside `radiant.atmosphere`: no backend `evaluate` reads
`geometry.sensor_altitude_m` from the `ParameterSet` (plan §3.5 guardrail G2 —
`GeometryStage` is the one place that reads the parameter and puts it on the
LOS). A LOS that does not carry `h_sensor` raises an actionable error rather
than falling back to the parameter (`atmosphere/_sensor_endpoint.py`).

Direction is derived from the altitude pair, never declared, and since
Geometry-Flexibility **Phase 2** it *dispatches* rather than refuses
(`atmosphere/topology.py::evaluate_path_topology`; the Phase-1
`_uplooking_guard.py` blanket refusal is deleted):

| `los.los_direction` | Product |
|---|---|
| `down` | The backend's own `evaluate`, **unchanged and not rerouted** — every existing scene is byte-identical. The exo-altitude target is the segment composition of §4.2a over that same call |
| `up` | Segment composition: an observer-leg column keyed to the **sensor** (the lower endpoint), plus reused target-side illumination, plus a sky continuation — §4.2d |
| `level` | Same, with a constant-altitude arm as the observer leg |

The refusal that remains is a **capability** refusal, not a
pending-implementation one: the segment evaluators are built on the
CU-161-calibrated `SimpleAtmosphere` species model, so `atmosphere.model =
"simple"` serves up-looking and level paths and every other backend raises an
actionable error naming exactly what *is* supported (simple for any endo path;
any backend for a wholly-vacuum path with both endpoints above `h_atm_top`).
MODTRAN tape7-import and the interpolated library arrive with their own
up-looking / ITYPE=1 run families (owner-run batches, GF-10).

**Up-looking interpolated library (GF-10, shipped 2026-07-26).** The first
up-looking run family ships as `midlat_summer_uplooking_ladder/` — the K-block
vertical partial-column ladder (ground sensor → targets 1/3/5/10/20 km, plus a
synthesized exact zero-length node at 0 km). It is queried through
`InterpolatedAtmosphere.uplooking_column_product(wavelength_um, los)`, which
returns an `UplookingColumnProduct` carrying the segment's reciprocal `tau` and
its `L_toward_lower` — the *downward* path radiance the ground sensor sees. It
is deliberately **not** a `SegmentQuantities`: an up-looking run measures one
travel direction, and a type with no `L_toward_upper` field is how that is said
without inventing one (Rule 17). Three properties keep the two directions from
being confused: the NPZ radiance key differs (`path_radiance_toward_lower` vs
`path_radiance`), every file carries a `los_direction` marker, and the two query
entry points refuse each other's families. The shipped-family default is keyed
on `(los_direction, interpolation_axes)`. The family is vertical-only and
ground-endpoint-only; off-vertical and elevated-endpoint queries raise and name
`atmosphere.model = "simple"` rather than being approximated (see
`data/atmospheres/MANIFEST.md` for the K6 45° measurement that justifies the
refusal).

> **Deferred — the sec-space zenith axis (GF-10, batch 2).** Down-looking
> families interpolate a zenith axis in **sec θ** (airmass) space, which is
> what makes a zenith fan interpolate linearly (CU-160). An up-looking zenith
> fan would need the same treatment, and the transform diverges as θ → 90°, so
> the near-horizontal band an up-looking family most wants to cover is exactly
> where sec-space is worst behaved. Rather than ship a fan on an untested
> mapping, the first up-looking family is rendered at a single zenith and
> off-vertical queries **raise**. Revisiting the mapping for the near-horizontal
> band is batch-2 work, alongside the refraction on/off calibration pair; until
> then `atmosphere.model = "simple"` is the answer for a slant up-look.
>
**Chain wiring — landed 2026-07-30 (CU-226).** An up-looking chain run on
`atmosphere.model = "interpolated"` now consumes the shipped family.
`uplooking_quantities.supports_uplooking` admits two arrangements: a bare
`SimpleAtmosphere` (every leg, any zenith, unchanged), and an
`UplookingColumnBackend` — a structural protocol satisfied by an
`InterpolatedAtmosphere` whose `family_direction` is `"up"` and which carries an
`uplooking_companion`.

The second arrangement is a **declared hybrid**, because an up-looking run
family is one leg of data:

| Leg | Served by | Why |
|-----|-----------|-----|
| observer (sensor → target) | the up-looking run family | this *is* the rendered column; it is the term that dominates a ground-to-air scene |
| illumination (solar column + sky hemisphere above the target) | the `SimpleAtmosphere` companion | no rung of a sensor→target ladder is the column *above* the target, and the down-looking proxy query an up-looking family would need is refused by construction |
| sky at aperture (sensor → `h_atm_top`) | the `SimpleAtmosphere` companion | the shipped ladder stops at 20 km; reading its top rung as "the sky" would be extrapolation past the hull |

The companion is built pre-chain by `atmosphere.loaders.build_atmosphere_model`
(Rule 6) from the same `atmosphere.*` parameters a `model = "simple"` run would
use, and attached to the family only when its direction is `"up"`. Two
independently-calibrated models in one answer is a real modelling compromise, so
it is never silent: a `UserWarning` is raised, an INFO record is logged, and
`stage_outputs["atmosphere"]["topology_provenance"]["backend_split"]` names which
leg came from which model.

`SegmentQuantities` is deliberately **not** the observer-leg type on this path.
That contract carries both directional radiances and an up-looking family
measures only `L_toward_lower`; the composition never needs the other direction,
because `observer_leg_from_los` sets `toward_sensor = "toward_lower"` on every
up-looking column (the sensor *is* the segment's lower endpoint). The internal
`_ObserverSegment` carries exactly `tau` and `L_toward_sensor`, so the
unreachability is structural rather than a comment — there is no
`L_toward_upper` slot for a one-direction family to have to invent.

A **level** path on an up-looking family is refused, not approximated: a level
arm has zero vertical extent and a local zenith of π/2 everywhere, so no rung of
a column ladder is that path and no interpolation between rungs produces it.
MODTRAN tape7-import still does not qualify — its up-looking / ITYPE=1 deck
geometry is unwritten (GF-10, CU-224).

### 4.2c The path-segment contract (guardrail G1)

Guardrail G1 forbids serving new path topologies by giving
`AtmosphericQuantities` new flat fields. The unit of composition is instead a
**path segment**: one piece of path between two points, evaluated once, read
from either end. `atmosphere/segments.py` owns the contract; the evaluators
(`segment_simple.py`, `segment_thermal.py`, `segment_single_scatter.py`,
`segment_grazing.py`, `level_arm.py`) implement it, one computation per module
(Rule 19).

Two spec types, because there are two path topologies and they are not
variations of one form:

| Spec | Fields | Topology |
|---|---|---|
| `ColumnSegmentSpec` | `h_low_m`, `h_high_m` [m], `zeta_low_rad` [rad] | **endpoint-minimum** — the path's lowest point is an endpoint. Plane-parallel-with-spherical-correction air mass |
| `LevelArmSpec` | `altitude_m` [m], `length_m` [m] | **interior-tangent** — the lowest point is in the middle. True spherical chord at constant density; **no air mass at all** (§4.2f) |

One evaluated product, `SegmentQuantities`, carrying:

- `wavelength_um` [µm] — the chain grid, ascending and strictly positive.
- `tau` — **one** array, dimensionless ∈ [0, 1]. Transmittance is reciprocal
  (§4.4), so a segment has one τ no matter which way it is read. A second
  direction-tagged τ would be a second source of truth for one quantity.
- `L_toward_upper`, `L_toward_lower` [W/m²/sr/µm] — path radiance **is**
  direction-specific, so it is two fields. `L_toward_upper` is what a sensor
  above the segment sees; `L_toward_lower` is what a sensor below it sees. They
  differ because the emitting and scattering layers are weighted by the
  transmittance of the material *between* them and the receiver, and that
  weighting reverses with direction.

**The lower-endpoint convention** (ADR-0011 decision 3). Every column segment's
zenith is keyed to its **lower** endpoint. Two reasons, both structural: it is
the one endpoint the two travel directions share, so a single scalar describes
the segment rather than the reading of it; and it is the angle MODTRAN's Card 3
wants when `H1 ≤ H2` (§5.2), so no convention translation sits between RADIANT
and its truth source. A level arm has no column zenith at all — its 90° is an
interior-tangent quantity, not an air-mass argument — which is why `LevelArmSpec`
carries a length instead.

**The validity ceiling and the refused sliver.** `zeta_low_rad` is bounded at
`ZENITH_CEILING_RAD` = 89.5° — the existing
plane-parallel-with-spherical-correction air-mass ceiling, unchanged from the
down-looking path. A zenith in the sliver **(89.5°, 90°)** is *geometrically*
admissible, and the Phase-1
horizon guard only **warns** there for an endpoint-minimum path; but there is no
trustworthy column air mass in that band, so `ColumnSegmentSpec` **refuses** it
with an actionable error rather than returning a plausible-looking wrong number
(Rule 17). The two layers disagreeing is deliberate, not an oversight: geometry
judges whether the *path* is modellable, the segment spec judges whether the
*column air mass* is. A near-horizontal path in that sliver is an
interior-tangent path and belongs in a `LevelArmSpec`, which carries no air mass
and is therefore unaffected by the ceiling. This is also why the near-tangent
sky continuation past 89.5° switches to the true spherical slant integral of
`segment_grazing.py` (§4.2g) instead of extrapolating the column form.

### 4.2d Direction-aware composition — up-looking and level paths (Phase 2)

Gaps 108/109. An up-looking or level scene is a **composition of path
segments** (guardrail G1: the eight-field `AtmosphericQuantities` contract is
unchanged; what changes is which segment fills the observer-leg slots), built by
`atmosphere/uplooking_quantities.py`:

```
observer leg = segment(target ↔ sensor)       → tau_obs, L_obs→sensor
illumination = target-side products, reused   → tau_sun, E_TOA, E_sky_*
continuation = segment(target → space)        → L_sky

L_t,aperture  = [ε·B(T_t) + ρ·τ_sun·E_TOA·cos θ_s/π + ρ·E_sky/π] · tau_obs + L_obs→sensor
L_bg,aperture = L_sky · tau_obs + L_obs→sensor
```

The target equation is the **unmodified §6.1 equation with the observer leg
swapped**, so `assembly.assemble_target_at_aperture` is reused verbatim and
every T-code works up-looking with no new arms.

- **Observer leg** (`atmosphere/observer_leg.py`). Up-looking: a
  `ColumnSegmentSpec` from `h_sensor` to `h_tgt` keyed to the sensor's zenith
  `ζ_low = π − η` (ADR-0011 decision 3), read in the `toward_lower` direction.
  Level: a `LevelArmSpec` whose length is the true spherical chord, read
  `toward_upper`. The sun's relative azimuth is re-expressed in the segment's
  frame (`Δφ_seg = Δφ − π` up-looking, where lower→upper is sensor→target).
  **Transmittance is reciprocal**: the same physical line expressed down-looking
  and up-looking gives the same `τ` to within an ULP, and exactly for the
  vertical case.
- **Illumination leg.** `τ_sun`, `E_TOA` and the two `E_sky` terms describe the
  *target's* environment and are direction-agnostic, so they are reused from a
  proxy down-looking evaluation at the same `h_tgt` and solar angles with the
  sensor at `h_atm_top` and `θ_o = 0`. With the proxy sensor at the column top
  the `E_sky_scattered` slab coincides with the CU-155 `E_sky_thermal` slab, so
  both diffuse components mean "the sky above the target", which is what an
  up-looking scene means by them. An exo-altitude target takes the vacuum
  identities instead.
- **Continuation / `SkyBackground`.** The LOS continuation leaves the target at
  `ζ_c = π − θ_o`; `core/los_termination.py` classifies where it ends
  (Rule B). Inside the 89.5° column ceiling it is
  `sky_radiance.sky_radiance_along_los`; past it — every level arm shorter than
  ≈ 111 km — it is the true spherical slant integral
  (`atmosphere/segment_grazing.py`, over `atmosphere/grazing_column.py`),
  because the plane-parallel air mass understates the real column by ~3× there.
  For an exo target the continuation is vacuum and `L_sky ≡ 0`, so the
  background reduces to the observer leg's own emission.
- **`tau_full_up` / `L_path_full` carry the observer leg** for these topologies:
  the LOS terminates on space, so the background source plane *is* the target
  plane. An explicit `GroundBackground` on an up-looking or level path is
  refused (there is no ground behind the target — `AtmosphereStage`).

### 4.2e Per-altitude solar illumination (GF-9, ratified decision 21)

The global `θ_s < π/2` bound is replaced by a per-altitude shadow-height test.
`geometry.solar_zenith_rad` and `AtmosphericGeometry.solar_zenith_rad` now span
the closed `[0, π]`; whether a given point is lit is decided by
`atmosphere/solar_shadow.py`:

```
sunlit(h, θ_s)  ⟺  θ_s ≤ π/2  or  (R_E + h)·sin θ_s ≥ R_E
                ⟺  h ≥ R_E·(sec δ − 1),   δ = θ_s − π/2
```

so a 60 km booster is sunlit at 5° solar depression while the ground beneath it
(shadow height ≈ 24 km) is not. Assumption: a **sharp terminator** — opaque
sphere, point Sun, no refraction; the ≈ 200 m penumbral blur and the ≈ 0.5° of
unmodelled refractive lift are documented, not smoothed.

For a **sunlit** target with `θ_s > π/2` the direct beam is a tangent transit,
not a descending column, so `τ_sun` is the two-arm decomposition
`τ(tangent → target)·τ(tangent → TOA)` of `atmosphere/solar_transit.py`. For a
**shadowed** target `τ_sun` is exactly 0 (no beam at all) and the scattered-sky
solar component is already identically zero; the thermal sky is untouched.

> **PROVISIONAL.** The twilight transit carries the largest optical depths
> anywhere in RADIANT (30–70 air masses), where the exponential-in-column
> transmittance and the unmodelled refraction are both at their worst, and
> MODTRAN batch 1 contains no twilight deck. Treat it as an order-of-magnitude
> bound; a twilight pair belongs in batch 2 alongside the refraction on/off
> calibration.
>
> Note also that RADIANT models the target as a horizontal Lambertian facet, so
> assembly multiplies the direct-solar term by `cos θ_s` clamped at zero. For
> any `θ_s > π/2` that factor is zero and the direct term vanishes regardless of
> `τ_sun` — the beam arrives from below the facet. `τ_sun` is still published
> correctly because it is an inspectable physical quantity (Rule 16) and a
> non-horizontal target model would consume it.

**Zero drift**: every scene with `θ_s ≤ π/2` — everything expressible before
Phase 2 — keeps the backend's own solar column, untouched.

### 4.2f The constant-altitude arm — the level path (A5)

A level or near-level path (`los_direction == "level"`) cannot be served by the
column machinery at all, and the reason is structural rather than a matter of
accuracy: a column segment's optical depth is `∫ exp(−h/H) dh` between its two
endpoint altitudes, which for equal altitudes is **exactly zero**, and its air
mass is a plane-parallel `sec ζ` that is undefined at ζ = π/2. The level arm is
an **interior-tangent** topology — its lowest point is in the middle, not at an
endpoint — so it gets its own spec type (`LevelArmSpec`) and its own evaluator
(`atmosphere/level_arm.py`), per Rule 19.

```
τ(λ)      = exp[ −α(λ, h) · L ]                    (Beer-Lambert, exact)
L_path(λ) = (1 − τ(λ))·B(λ, T_eff)  +  single-scatter solar source
```

with `α(λ, h)` the **local** extinction coefficient at the arm's altitude
[1/km] and `L` the **true spherical chord** between the endpoints [km] — not a
flat-Earth range. No new calibration is introduced: Rayleigh and aerosol have
closed-form local values already, and the CU-161 water and well-mixed-gas terms
(which are calibrated as *column* optical depths, the water one as a curve of
growth `OD = k·w_eff^b` that is the integral of no local coefficient) are
linearised the same way `simple.py` already linearises them for its
single-scattering-albedo weights — the species' column-mean sea-level extinction
over the column *above* the arm, brought down to the arm's local density. That
reference column is independent of the arm's own length, which is what makes `α`
a property of altitude alone and `τ` a pure exponential in `L`.

**Constant-density assumption, and where it stops being valid.** The arm is a
straight chord of uniform density at `altitude_m`. On a spherical Earth the
chord dips below its endpoints by the tangent-height depression
`Δh ≈ L²/8R_E` (mean sag over the chord `≈ (2/3)Δh`), so the real path samples
slightly *denser* air and the model **under-states** optical depth. The Phase-1
horizon guard is what bounds the error: it admits `Δh < 100 m` clean, warns to
2 km, and raises beyond. Working the numbers on the 2 km water scale height:

| Guard band | Δh | Mean sag | Water-density error |
|---|---|---|---|
| clean edge | 100 m (L ≈ 71 km) | 67 m | 3.4 % |
| L-grid longest arm | 196 m (L = 100 km) | 131 m | 6.8 % |
| raise threshold | 2 km | 1.33 km | ≈ 1.9× (90 %) |

The last row is *why* 2 km raises rather than warns — a two-fold understatement
of water optical depth is not a caveat, it is a wrong answer (Rule 17).

**The exponential is the model's own claim, and it is measured.** `τ(2L) = τ(L)²`
holds exactly for this arm and is precisely where a correlated-k band model
disagrees: strong lines saturate first and flux keeps leaking through the
windows between them. Against the real MODTRAN horizontal 5×5 grid (rows
L1–L25, midlat_summer, rural, 23 km visibility) the band-mean model/MODTRAN
ratio at 3 km altitude runs **1.03, 1.01, 0.95, 0.87, 0.82** over 5/10/25/50/100
km at 8–12 µm, and **1.09, 0.88, 0.43, 0.11, 0.01** at 3–5 µm — the exponential
arm collapses while MODTRAN keeps leaking. Long-range MWIR horizontal work needs
a MODTRAN or interpolated backend; the A5 library family is batch 2. MODTRAN's
own horizontal path type is `ITYPE=1`, wired through `ModtranConfig.hrange_km`
(§5.2).

### 4.2g Sky radiance along the LOS — the `SkyBackground` product (Gap 108)

The one genuinely **new** product of Phase 2. It is the radiance a receiver at
`h_start` sees looking **up** along a ray of zenith ζ with nothing behind the
atmosphere but cold space, and it is what a sensor sees *behind* an airborne
target:

```
L_sky(h_start, ζ) = SegmentQuantities(ColumnSegmentSpec(h_start, h_atm_top, ζ)).L_toward_lower
                    + τ_segment · L_beyond ,      L_beyond ≡ 0
```

`L_beyond ≡ 0` because the 2.7 K cosmic background contributes
< 1e-9 W/m²/sr/µm anywhere in the 0.3–14 µm working range and is deliberately
not modelled. The composition is therefore a no-op and
`atmosphere/sky_radiance.py` is a thin, well-named wrapper over
`segment_simple.py` rather than a second physics implementation.

**Where the ray starts: the sensor, not the target (CU-254, 2026-07-29).** The
quantity handed to assembly is `TopologyProducts.sky_radiance_at_aperture`
[W/m²/sr/µm] — the whole LOS from the *sensor* out to `h_atm_top`, i.e. what the
aperture would measure if the target were not there. Until 2026-07-29 the field
was named `sky_source_radiance` and held the sky at the **target** plane, which
assembly re-propagated as `L_sky·τ_full_up + L_path_full`. That composition is
exact radiative transfer, but the segment model being composed is *not* additive:
each segment emits `(1 − τ_seg)·B(T_eff(h_low,seg))` at its own lower-endpoint
effective temperature, so splitting one column at the target plane swaps part of
a warm ground-anchored graybody for a cold target-anchored one. Measured on the
shipped 10.1 config, varying only `geometry.target_altitude_m` at fixed pointing:

| target altitude | `background_e` before | after |
|---|---|---|
| 10 km | 1.94207e5 e⁻ | 2.21479e5 e⁻ |
| 20 km | 2.14046e5 e⁻ | 2.21479e5 e⁻ |
| 99 km (whole column) | 2.21479e5 e⁻ | 2.21479e5 e⁻ |

A background behind a target cannot depend on where along the ray the target
sits; the surviving value is the ground-rooted one, which is also the geometry
the MODTRAN H-runs anchor. The `SkyBackground` arm is consequently a
**pass-through** — `τ ≡ 1`, `L_path ≡ 0` — and must not consult `τ_full_up` /
`L_path_full` at all.

**The level topology still composes.** A level ray is tangent at the chord
*midpoint*, so the sensor sits on its descending half and a single sensor-rooted
ascending arc would omit the constant-altitude arm entirely: measured in
sea-level-equivalent molecular column, such an arc recovers 98.6 % of the true
traversed path for an 8 km arm at ground level, 83.0 % for 100 km at 3 km, and
75.1 % for 150 km at 10 km. Nothing evaluates "constant-altitude arm then
ascending arc" as one segment (`LevelArmSpec` and `segment_grazing.py` are
different computations, Rule 19), so the level branch keeps
`L_arm→sensor + τ_arm · L_continuation(target→top)`, computed at the production
site in `uplooking_quantities._level_sky_at_aperture`. It is geometrically
complete, it is numerically what assembly used to build, and no level scene
moved. It also keeps the CU-254 target-position dependence, tracked as CU-276.

Two things it is **not**:

- It is not `AtmosphericQuantities.E_sky_thermal`. That is a hemispheric
  downwelling **irradiance** [W/m²/µm] used for surface reflection; this is a
  directional **radiance** [W/m²/sr/µm] along one ray. Different quantity,
  different unit, different geometry — nothing here modifies or replaces it, so
  no existing scene moves.
- It is not a field on `AtmosphericQuantities` (guardrail G1). It rides
  alongside the eight-field bundle on
  `TopologyProducts.sky_radiance_at_aperture`.

A missing or off-grid `sky_radiance_at_aperture` **raises** rather than defaulting
to zero: a silently-zero sky background would delete the background photon term
and therefore *inflate* SNR, which is the exact failure mode Rule 17 forbids.

**Band gating (plan §8.3 answer 3, locked decision 20).** The thermal component
is first-class at first delivery — it is anchored directly against the real
MODTRAN up-looking H-runs. The scattered-solar component rests on a
single-scatter approximation known to under-predict the daytime VIS/NIR sky,
where multiple scattering dominates. A `UserWarning` is emitted when **both**
conditions hold: the evaluation grid extends below
`sky_radiance.SCATTERED_SKY_PROVISIONAL_MAX_UM` (3 µm) **and** a solar geometry
with the sun above the local horizon is supplied. A pure-thermal MWIR/LWIR call
warns about nothing, and neither does a night scene on a VIS grid.

> **Coupling caveat (found 2026-07-26, not yet repaired).** Whether the sky
> carries a scattered-solar component at all is gated by `los.theta_s`, and
> `source/_inferrer._adjust_scene_los` strips `theta_s` for a **T1Thermal**
> target (the CU-009 predicate: "a pure-thermal radiance has no solar leg").
> That predicate was complete when the target was the only consumer of
> `theta_s`; the sky background is now a second consumer whose solar dependence
> has nothing to do with the target's material. Consequence: a pure-thermal
> target on a VIS/NIR grid gets a **thermal-only sky at noon**, and no
> provisional warning, because the trigger condition is never met. Pinned as a
> characterization by
> `tests/integration/test_direction_aware_atmosphere.py::TestProvisionalScatteredSkyWarning`.

**Near-horizon: hand over at 80°, not 89.5° (CU-225 / CU-274, 2026-07-29).**
Past `SPHERICAL_SWITCH_RAD` the sky is evaluated as a true spherical slant
integral (`atmosphere/segment_grazing.py` over `grazing_column.py`) instead of
by the plane-parallel column form. The hand-over moved down from the 89.5°
ceiling to 80° because 80° is where the column form's air mass stops being
`sec ζ` and starts being the root form §4.2 has now deleted — i.e. 80° is where
the plane-parallel description genuinely expires, and there is no reason to keep
using it for another 9.5°.

The hand-over is still a **step, not a blend**, but a small one. Band-mean LWIR
(8–13 µm) sky from the ground, grazing/column:

| ζ | 0° | 30° | 48.2° | 60° | **80°** | 85° | 89.4° |
|---|---|---|---|---|---|---|---|
| ratio | 1.00000 | 0.99979 | 0.99929 | 0.99852 | **0.99359** | 1.08665 | 1.07785 |

(48.2° is the zenith the MODTRAN H-runs anchor.) So the discontinuity went from
≈ 8 % at the old ceiling — ≈ 28 % on the 3 km level arm CU-225 originally
measured — to **0.64 %**, and the whole 80–89.5° band is now served by the exact
integral rather than by an air mass that was 14–62 % low there. The residual
0.64 % is the plane-parallel model's own error where it is retired; the
underlying optical depths differ by 2.8 % at 80° and by a factor of two at 89°.

**The species split is weighted at the lower endpoint (CU-260, adopted
2026-08-01).** Both evaluators now take the *relative* species proportions that
set ω₀ and P(Θ) at the segment's **lower endpoint** — the densest air in the
path, the end the `L_toward_lower` product emerges from, and what
`segment_grazing.py` and `level_arm.py` already did. `segment_simple.py` used
the segment's *arithmetic-mean* altitude until this date, which for any column
taller than ≈ 40 km put the weights above the altitude where the aerosol and
water coefficients underflow: ω₀ evaluated to exactly 1 (no absorption at all)
and the Henyey-Greenstein forward peak collapsed onto the isotropic-Rayleigh
1.5, so a tall column scattered as if the atmosphere held no aerosol whatever
`visibility_km` said.

Anchored against the shipped `midlat_summer_uplooking_ladder` MODTRAN family
(ground sensor, ζ = 0°, θ_s = 30°, five non-degenerate rungs), band-mean
MODTRAN/model at the worst rung:

| band | arithmetic mean (retired) | lower endpoint (shipped) |
|---|---|---|
| VIS 0.45–0.85 µm | 3.085× | **1.360×** |
| NIR 0.85–1.40 µm | 3.024× | **1.262×** |
| SWIR 1.4–2.5 µm | 8.712× | **1.666×** |
| MWIR 3–5 µm | 2.404× | **2.334×** |
| LWIR 8–12 µm | 1.885× | 1.885× (identical to 4e-4 — thermal control) |

Lower-endpoint weighting is closer on 18 of the 25 rung × band cells and its
overall RMS |ln ratio| is half the retired form's (0.351 against 0.717); the off-band
thermal region is inert to the choice, which is the condition the adoption
criterion required. The anchors are frozen in
`tests/integration/test_species_split_anchors.py`. Note what this does *not*
claim: the single-scatter source still under-predicts the daytime VIS/NIR sky by
tens of percent, which is what the sub-3 µm provisional warning above says.

The alignment also removes the *species-split* half of the 80° hand-over step —
VIS band-mean grazing/column was 2.12× at ζ = 0° and 9.91× at 30° and is now
1.000 and 1.007 — but not all of it. The residual step at the hand-over is
**1.063× VIS**, **0.996× MWIR**, **0.994× LWIR** (measured 2026-08-01, ground to
`h_atm_top`, θ_s = 30°). What remains is not the weight altitude: the two
evaluators linearise the CU-161 water curve of growth and gas floor against
*different reference columns* — `segment_simple` against the vertical column,
`segment_grazing` against the slant one — and because the curve of growth is
sub-linear that changes the effective water weight by `(m_h2o)^(b−1)` and
therefore ω₀ wherever water absorbs (the step is < 0.5 % below 0.68 µm and ≈ 30 %
above it). Recorded as a finding, not closed here.

### 4.3 How geometry feeds each model

| Model | Slant path effect | Solar zenith effect |
|-------|-------------------|---------------------|
| Simple | `τ = exp(−σ · L_slant)`; aerosol & H₂O scale heights re-evaluated for `(h_sensor, h_target)` | Drives `cos(θ_sun)` in single-scatter `L_path`; the downwelling `T_eff` is target-anchored (CU-155 — sensor altitude does not enter) |
| Tabulated | **None.** Tabulated files are taken at face value. `GeometryDrift` warning if geometry changes after load | None |
| Exo | None | None |
| MODTRAN | Set into card deck (CARD 3: `H1`, `H2`, `ANGLE`); MODTRAN computes the slant path internally | Set into card deck (CARD 3A1: `IPARM`, `PARM1`, `PARM2`); MODTRAN computes single + multiple scatter |

The simple model and the MODTRAN interface both *recompute* their outputs whenever geometry changes. Tabulated does not. This is the user-visible price of choosing tabulated input.

### 4.4 Reciprocity and the upwelling/downwelling distinction

For unpolarized broadband radiation in a plane-parallel atmosphere, transmittance is reciprocal: `τ(sensor → target) = τ(target → sensor)`. RADIANT exploits this — only one transmittance is computed per slant path. Path radiance is *not* reciprocal: the sensor-bound (`L_path`, "upwelling") and source-bound (`L_atm_down`, "downwelling") radiances differ because of the geometry of where the scattering and emission happen. Both are computed independently, and they are not interchanged.

`L_atm_down` (surfaced in `AtmosphericQuantities` as the `E_sky_thermal` / `E_sky_scattered` **irradiance** pair) is consumed by the reflected-diffuse term of the target and ground-background arms, and by any `ReflectedSolarSource` whose downwelling spectrum is tied to the atmospheric model rather than to a top-of-atmosphere standard. The atmosphere module *produces* it; it does not consume it.

**Not to be confused with the `SkyBackground` product.** Before Phase 2 this paragraph named `SkyBackground` as `L_atm_down`'s consumer, which the Phase-2 implementation makes wrong in both directions: the `SkyBackground` descriptor consumes a *directional radiance along the LOS continuation* (§4.2g, `TopologyProducts.sky_radiance_at_aperture`, W/m²/sr/µm), never the hemispheric irradiance, and the irradiance's real consumers are the reflective terms. The two are separate products computed by separate modules; conflating them would put a hemispheric integral where a single ray belongs.

---

## 5. MODTRAN Interface

This section defines the file and binary boundary between RADIANT and MODTRAN. Everything that depends on MODTRAN file formats lives in `radiant.atmosphere.modtran` — the tape7 file import (`Tape7Import`), the deck builder (`render_tape5`), the parser (`Tape7Reader`), and the cache. No other module may know what a tape5, tape7, or `.tp7` file looks like.

There are **two ways in**, with a fixed precedence:

1. **Tape7 file import (§5.1) — the primary workflow.** `atmosphere.modtran.tape7_path` names a tape7 produced elsewhere (a colleague's licensed MODTRAN run, a donated fixture). When set, the file wins unconditionally: the binary, the cache, and the fallback are never consulted.
2. **Binary invocation (§5.2–§5.5) — secondary, never yet exercised.** With `tape7_path` unset, RADIANT renders a tape5 deck and drives a locally-installed `modtran` executable, with caching and an opt-in fallback. This path is retained unchanged for when MODTRAN access arrives.

**Verification status caveat**: as of 2026-07-17 a real MODTRAN 6 run set (the 39-run matrix) has been produced externally, and both the **parse side** and the **deck side** are now validated against it. Parse: tape7 output round-trips through the reader (CU-154; §5.3 "Real-data validation"). Deck: the field-position conventions RADIANT *writes* are confirmed by three-way agreement (`render_tape5` == the CSV's hand-worked column == the delivered tape7's card echoes) across all 35 non-E rows plus correct airmass physics — **CU-065** (Card 3 ANGLE-at-H1 convention: nadir renders 180°) and **CU-067** (Card 1 token positions MODEL/ITYPE/IEMSCT/IMULT) are verified this way, a stronger authority than the manual alone, and pinned by Level-0 tests. Still external: RADIANT has not itself *invoked* a MODTRAN binary (the runs were delivered as files); the binary-invocation cache key now fingerprints the executable's bytes so an upgrade invalidates stale entries (**CU-070** resolved via the byte-hash fallback; a `modtran -version` form can supersede it once the binary path is exercised). The committed test fixtures remain synthetic/hand-authored until the real fixture subset is committed (plan §7.1). **Extended 2026-07-26** (Geometry-Flexibility Phase 2, batch-1 delivery): the same three-way agreement now covers every delivered row of the 88-row matrix, including the K-block up-looking ladder (K7 closing the elevated-lower-endpoint ANGLE convention) and the 25-row ITYPE=1 horizontal grid, whose Card-3 **RANGE** field is compared as well (`tests/integration/test_uplooking_horizontal_anchors.py`). See `docs/archive/MODTRAN_Run_Matrix_Plan.md`.

### 5.1 Tape7 file import (primary workflow)

Setting `atmosphere.modtran.tape7_path` (with `atmosphere.model = "modtran"`) builds the atmospheric state from an existing tape7 file:

- **Rule 6 boundary**: the file is parsed **before chain execution**, in `radiant.atmosphere.loaders._build_modtran`, via `Tape7Reader.to_radiant_units()`. The parsed arrays travel as a `Tape7Import` (frozen dataclass: four ascending-wavelength arrays + `source_path` + `content_key` = sha256(file bytes)[:16]) into `ModtranAtmosphere`, which resamples them to the chain grid exactly the way the binary path's cache-hit branch does. `AtmosphereStage` never reads the file; with `tape7_path` set, `modtran` counts as file-backed for the stage's Rule 6 refusal check (`loaders.model_requires_prebuild`).
- **Precedence**: file set → file wins; binary, cache, and `allow_fallback` are irrelevant. File unset → §5.2–§5.5 behavior, bit-identical to before the import path existed.
- **Geometry-agnostic**, like tabulated input (§3.2): the imported arrays are served as-is for any query geometry. The file encodes whatever geometry its MODTRAN run used; RADIANT does not re-scale it. Consequently an airborne target (`h_tgt > 0`) raises `NotImplementedError` **unless** a second target→sensor run is imported via `atmosphere.modtran.tape7_up_path` (Gap 94, below) — a single file cannot supply both the target-leg and the full-column transmittance the background branch needs (same restriction as `TabulatedAtmosphere`).
- **Airborne-target two-leg split (Gap 94, file flavor)**: optionally, `atmosphere.modtran.tape7_up_path` names a second tape7 run along the target→sensor partial column (a deck with H2 = the target altitude, like the run matrix's C/G blocks). When set, `τ_up` and `L_path_up` come from that file's columns resampled to the chain grid, `tape7_path` keeps supplying the ground→sensor full column (`τ_full_up`, `L_path_full`), and airborne targets are accepted. Without a sun-leg file, `τ_sun` then aliases the up-leg `τ_up` under the collapse warning. RADIANT cannot verify the file's H2 against the scenario's `h_tgt` (a tape7 does not record its deck geometry) — the user owns that consistency, as with every file import. `tape7_up_path` without `tape7_path` is a configuration error.
- **Downwelling**: a standard IEMSCT=2 tape7 carries no downwelling column, so on a bare import `L_atm_down ≡ 0` (identical to the tabulated side-door without a downwelling file); `E_sky_thermal = 0` and `E_sky_scattered = 0` follow, with a loud Gap 81 `UserWarning`.
- **Flux-file downwelling (CU-157, file flavor)**: optionally, `atmosphere.modtran.flux_path` names the run's spectral flux CSV (a Block E irradiance run's `*_flux.csv` sidecar, parsed by `ModtranFluxReader`, §5.3). When set, the ground-level **DOWN** column (thermal emission + scattered solar, in W/m²/µm) supplies the real hemispheric downwelling: `L_atm_down = DOWN / π`, and the two sky-reflection terms are split at the reflective-solar / thermal boundary (4 µm, `_FLUX_REFLECTIVE_SOLAR_MAX_UM`) — `E_sky_scattered` from λ below it, `E_sky_thermal` from λ above — superseding the Gap 81 zeros (no warning). The boundary is a **labelling** choice only: the assembly consumes `E_sky_scattered + E_sky_thermal`, which equals the full DOWN column regardless of the split, so a modest thermal-overlap overcount in `E_sky_scattered` near the boundary is accepted (owner-ratified band-split, gaps.md Gap 38). Requires `tape7_path`; `flux_path` without it is a configuration error.
- **Two-leg split (CU-011, file flavor)**: optionally, `atmosphere.modtran.tape7_sun_path` names a second tape7 run along the sun→target slant path (the run matrix's B-block was designed as sun-leg data). When set, `τ_sun` comes from that file's transmittance column resampled to the chain grid, and the single-τ collapse `UserWarning` is not emitted; `τ_up == τ_full_up` still alias (exact for the surface targets this path permits). With only `tape7_path`, `τ_sun` aliases `τ_up` with the warning, as before. `tape7_sun_path` without `tape7_path` is a configuration error — the binary flavor has no two-leg support yet (CU-011's remaining deferral).
- **Equivalence guarantee**: importing a tape7 directly produces chain outputs identical to the historical side-door (Tape7Reader → full-precision CSVs → `atmosphere.model="tabulated"`); `tests/integration/test_modtran_tape7_import.py` asserts exact equality.
- **Provenance**: `derivation_chain` records the source path and `content_key`; `SpectralData.source_parameters` carries `cache_key="tape7-file:<content_key>"`.

### 5.2 Card deck builder

`ModtranConfig` is a dataclass holding the MODTRAN knobs RADIANT exposes; the free function `render_tape5(config, geometry)` emits the fixed-format tape5 string. RADIANT does not expose every MODTRAN knob — only the ones that matter for the in-scope use cases: `atmosphere_profile` (MODEL 1–6), `aerosol_model` (IHAZE), `h2o_scale` / `o3_scale` (Card 2C column scaling), `visibility_km` (Card 2 VIS; `None` = IHAZE default, CU-063), `itype` (Card 1 path geometry; default 2 = slant path H1→H2, CU-069), `iemsct` (Card 1 mode; default 2 = thermal+solar path radiance, 3 = solar irradiance, CU-064), `hrange_km` (Card 3 RANGE — the horizontal path length in km; meaningful only for `itype=1`), `spectral_resolution_cm1`, `v1_cm1` / `v2_cm1` (Card 4), plus `binary_path`, `cache_dir`, and `allow_fallback`.

**Cards RADIANT writes** (1, 1A, 2, 2C, 3, 3A1, 4, 5): geometry comes from `AtmosphericGeometry` — H1/H2 from sensor/target altitude; Card 3 ANGLE is converted from `path_zenith_rad` (measured at the path's lower endpoint, §4.1) to MODTRAN's zenith-at-H1 convention: downlooking (H1 above H2) renders `180° − zenith` (nadir-from-space → 180°), uplooking renders the zenith unchanged. The conversion reproduces the hand-worked `modtran_angle_at_h1_deg` column of `docs/plans/modtran_run_matrix.csv` for every ITYPE=2 row; the CU-065 residue is confirming that convention against the MODTRAN manual itself, and the delivered K7 run (5 → 15 km at 45°) closes the elevated-lower-endpoint half of it empirically: its Card-3 echo reads `ANGLE 45.000` with `PHI 135.083` at H2, which is only consistent with ANGLE belonging to H1. **ITYPE=1 (horizontal, constant-altitude) is the one path type where ANGLE is not derived from `path_zenith_rad`**: MODTRAN builds the path from H1 plus Card 3 RANGE and ignores H2/ANGLE, so `render_tape5` writes the literal 90° a level path has by definition and takes the path length from `ModtranConfig.hrange_km`. A level path's 90° is an interior-tangent quantity, not a column zenith, so `AtmosphericGeometry` correctly refuses to carry it (`ZENITH_CEILING_RAD` = 89.5° is the column air-mass validity ceiling) and the horizontal branch does not consult it. `ModtranConfig` refuses `itype=1` without `hrange_km` (a zero-length path) and `hrange_km` outside `itype=1` (over-specification — MODTRAN derives RANGE from H1/H2/ANGLE for a slant path). Because `hrange_km` is 0.0 for every non-horizontal deck and `f"{0.0:10.3f}"` is exactly the ten-character literal the RANGE field previously held, every ITYPE ∈ {2, 3} deck renders byte-identically to the pre-wiring builder. Solar zenith/azimuth go on Card 3A1 (IPARM=2). IMULT=1 (multiple scattering) is fixed. Anything not exposed is left at the literal values in `render_tape5`; the `ModtranConfig.extra_cards: dict[str, str]` field lets advanced users override a whole card line, and the override is part of the rendered deck and therefore of the cache key.

The deck is rendered to a tape5 in a per-run temp directory. RADIANT does *not* edit a user-supplied tape5 — the deck is built from scratch every run, so reproducibility is owned entirely by the parameter set, not by a hand-tuned input file.

### 5.3 Tape7 parser

`Tape7Reader` parses the fixed-column tape7 file into a `ModtranNativeOutput` dataclass:

```python
@dataclass(frozen=True)
class ModtranNativeOutput:
    wavenumber_cm1: np.ndarray           # cm⁻¹, MODTRAN-native descending order
    total_transmittance: np.ndarray      # dimensionless
    path_thermal_radiance: np.ndarray    # W/cm²/sr/cm⁻¹ (PTH THRML / THRML_EM)
    path_scattered_radiance: np.ndarray  # W/cm²/sr/cm⁻¹ (SOL SCAT, or MULT_SCAT+SING_SCAT)
    ground_reflected_radiance: np.ndarray  # W/cm²/sr/cm⁻¹ (GRND RFLT / GRND_RFLT)
    header: dict[str, Any]               # raw header lines (card echo etc.)
```

The other real tape7 columns (`THRML SCT`, `SURF EMIS`, `SNGL SCAT`/`SING_SCAT`, `DRCT RFLT`, `TOTAL RAD`) are located by the parser but not yet consumed — a richer decomposition (e.g. exposing single-scatter solar separately) is future work, not a shipped surface.

**Column identification (CU-066, CU-154):** columns are located by their tape7 header LABEL, matched by left-to-right order of appearance in the header line — not by a fixed token/character position, which varies by MODTRAN version and does not survive multi-word labels. Two label vocabularies are recognised, so one reader serves either binary: the **classic** space-delimited names (`TOT TRANS`, `PTH THRML`, `SOL SCAT`, `GRND RFLT`, …) and **MODTRAN 6**'s underscore names (`TOT_TRANS`, `THRML_EM`, `GRND_RFLT`, …), which split the classic combined `SOL SCAT` column into `MULT_SCAT` + `SING_SCAT` (summed to form `path_scattered_radiance`; the classic `SOL_SCAT` column, when present, takes priority and is not double-counted with `SNGL SCAT`). MODTRAN's `-9999.` end-of-block sentinel is detected by its column-count mismatch and excluded from the spectral data. A header lacking a required column (`FREQ`, `TOT_TRANS`, `THRML_EM`, `GRND_RFLT`, or a solar-scatter term) raises `Tape7ParseError`. Tape7 files with no recognisable header (e.g. hand-authored fixtures) fall back to the pre-fix positional assumption with a `UserWarning`; that fallback should not be relied on for MODTRAN-derived results.

**Real-data validation (CU-154):** the first real MODTRAN run set (2026-07-17, MODTRAN 6, the 39-run matrix of `docs/plans/modtran_run_matrix.csv`) now round-trips through `Tape7Reader` — `tests/…/test_modtran.py::TestRealModtranA1` checks the A1 tape7's unit conversion against hand-computed values in the LWIR, MWIR, and VIS. That real run set is staged gitignored under `modtran/real_runs/` until the committed fixture subset lands (plan §7.1), so the acceptance test is `skipif`-guarded on the file's presence; the committed suite otherwise still runs on synthetic/hand-authored fixtures. The Card-3 ANGLE (CU-065) and Card-1 (CU-067) *deck-side* conventions remain unverified against the MODTRAN manual — real-data validation so far covers the tape7 *parse*, not the deck geometry.

Conversion to RADIANT internal units happens in `to_radiant_units()`, which returns four ascending-wavelength `np.ndarray`s — `(wavelength_um, transmittance, path_radiance, ground_reflected)`, where `path_radiance` is the sum of the thermal and scattered components in W/m²/sr/µm:
1. Spectral axis: `λ [µm] = 10⁴ / ν [cm⁻¹]`, sorted ascending.
2. Radiance: `L(λ) [W/m²/sr/µm] = L(ν) [W/cm²/sr/cm⁻¹] · ν²` — the single factor `ν²` combines the cm⁻²→m⁻² area conversion (10⁴) with the spectral Jacobian `|dν/dλ| = ν²/10⁴`.
3. Transmittance is dimensionless and unchanged.

The conversion is implemented exactly *once*, in this method. No other module performs cm⁻¹↔µm or W/cm²↔W/m² arithmetic.

**Flux table reader (`ModtranFluxReader`, CU-154).** MODTRAN 6's Block E irradiance runs write their spectral irradiance to a separate `*_flux.csv` sidecar, not the tape7 — a `case index … { … }` block with, per atmospheric level, three columns: upward-diffuse (`UP`), downward-diffuse (`DOWN` = thermal emission + scattered solar), and direct solar beam (`SOLAR`). `ModtranFluxReader.parse()` returns a `ModtranFluxOutput` (frozen dataclass: `wavenumber_cm1`, `altitude_km`, and `flux_up`/`flux_down`/`flux_direct_solar` shaped `(N_freq, M_levels)`) in native W/cm²/cm⁻¹; `to_radiant_units()` returns the ground-level `(wavelength_um, e_direct, e_diffuse_down)` in W/m²/µm using the **same** `ν²` Jacobian as the radiance case (spectral flux has no per-steradian factor to alter it). This is the reference data for `E_sky_scattered` / direct-solar irradiance (Gap 38). The reader is validated on the real E1 run — the LWIR direct beam is zero and the downwelling diffuse flux ≈ π·B(T_near-surface), the VIS direct beam ≈ TOA solar × τ × cos θ_s. As of CU-157 the **DOWN** column is wired into the chain via `atmosphere.modtran.flux_path` (§5.1, "Flux-file downwelling"): the ground-level DOWN irradiance feeds `E_sky_thermal` (thermal band) and `E_sky_scattered` (reflective-solar band), split at the 4 µm boundary; the owner-ratified band-limit (gaps.md Gap 38) resolves how the thermal and scattered-solar components of DOWN are separated. The `SOLAR`/`e_direct` column is parsed and retained on `FluxImport` for provenance but is not yet consumed — the direct-solar branch of the assembly still uses `E_TOA · τ_sun`.

### 5.4 Cache

MODTRAN runs are slow (seconds to minutes). The cache is keyed by a deterministic hash of the rendered tape5, and stores the **parsed, unit-converted arrays** (not the raw tape7):

```
cache_key  = sha256(rendered_tape5 + "\0" + binary_fingerprint).hexdigest()[:16]
cache_path = cache_dir / f"{cache_key}.npz"    # wavelength_um, transmittance,
                                               # path_radiance, ground_reflected
```

On a run: render tape5 → compute key → on hit, load the `.npz` and skip MODTRAN; on miss, invoke the binary in a temp directory, parse the tape7, save the arrays, proceed. The `binary_fingerprint` is a hash of the MODTRAN executable's bytes (`exe:<sha256[:16]>`, falling back to the path when unreadable), so **an upgraded binary invalidates stale entries** rather than silently reusing the old version's results (CU-070). It is computed by reading the executable's bytes, never by invoking it; a `modtran -version` form can supersede the byte-hash once the binary-invocation path is first exercised.

Cache eviction is **manual** — RADIANT never deletes cache entries on its own; remove files from `cache_dir` (default `~/.radiant/modtran_cache`) by hand. Entries are small (four float arrays per run), so accumulated cache is megabytes, not gigabytes.

### 5.5 Error handling when MODTRAN is unavailable

(Applies to the binary path only — the tape7 import (§5.1) never consults the binary.)

The MODTRAN binary may be missing for legitimate reasons: CI runners, students, contractors without licenses. RADIANT degrades in this order:

1. **Cache hit**: if the rendered tape5 hashes to a key already in the cache, return it. The user never knows MODTRAN was missing.
2. **Cache miss with `allow_fallback = True`** (default `False`): log a warning ("MODTRAN binary not available … falling back to SimpleAtmosphere with translated parameters") and build the state from `SimpleAtmosphere` at the equivalent profile/aerosol settings.
3. **Cache miss with `allow_fallback = False`**: raise `ModtranUnavailableError` naming the missing binary path and the two remedies (install MODTRAN / enable the fallback).

Fallback is opt-in because a user running a sensitivity study almost always wants to know that MODTRAN silently disappeared from under them. CI and student users opt in explicitly in their config.

---

## 6. Parameter Inventory

All parameters live under the `atmosphere.*` namespace. Names follow RADIANT_Parameter_System.md §"Naming rules" (lowercase, no unit suffix on the canonical name, two-deep namespace). Where the user-facing input has a unit different from the internal storage unit, the user-facing parameter carries a `_<unit>` suffix per RADIANT_Conventions.md §5 / §"interface boundaries."

### 6.1 Selection

Parameter types, defaults, units, and bounds are the canonical [Parameter Reference](../guides/parameter_reference.md) (auto-generated from the schema — the single source of truth, Rule 27). Design context:

- `atmosphere.model` — five legal values; `interpolated` interpolates between pre-computed runs.

### 6.2 Simple parametric

Parameter types, defaults, units, and bounds are the canonical [Parameter Reference](../guides/parameter_reference.md) (auto-generated from the schema — the single source of truth, Rule 27). Design context:

- `atmosphere.visibility_km` — "clear" per Koschmieder; rejected if ≤ 0.
- `atmosphere.aerosol_type` — sets Ångström α and SSA.
- `atmosphere.precipitable_water_cm` — **profile-coupled**: if left at its schema default while a non-default `standard_atmosphere` is selected, the loader substitutes the profile's McClatchey/MODTRAN standard column (`simple.PROFILE_PWV_CM`: tropical 4.11, midlat_summer 2.92, midlat_winter 0.85, subarctic_summer 2.08, subarctic_winter 0.42, us_standard 1.4). An explicitly set value always wins (provenance-based, Gap 57).
- `atmosphere.standard_atmosphere` — used for `T_atm_eff` lookup, aerosol/H₂O scale heights, and the default water column (above).
- `atmosphere.cloud_fraction` — stubbed in v1; non-zero raises `NotImplementedError`.
- `atmosphere.cloud_optical_depth` — same (stubbed in v1).

### 6.3 Tabulated

Parameter types, defaults, units, and bounds are the canonical [Parameter Reference](../guides/parameter_reference.md) (auto-generated from the schema — the single source of truth, Rule 27). Design context:

- `atmosphere.tabulated_transmittance_file` — CSV / .npz / .sli; ascending λ in µm.
- `atmosphere.tabulated_path_radiance_file` — same format; W/m²/sr/µm.
- `atmosphere.tabulated_downwelling_file` — same format; optional, defaults to zero with a warning.

### 6.4 MODTRAN

Parameter types, defaults, units, and bounds are the canonical [Parameter Reference](../guides/parameter_reference.md) (auto-generated from the schema — the single source of truth, Rule 27). Design context:

- `atmosphere.modtran.tape7_path` — Tape7 file import (§5.1). Set → the file wins; binary/cache/fallback never consulted. Geometry-agnostic; `h_tgt > 0` rejected unless `tape7_up_path` supplies the target leg.
- `atmosphere.modtran.tape7_sun_path` — optional sun-leg tape7 (§5.1, CU-011 file flavor). Requires `tape7_path`. Set → `τ_sun` from this file, no collapse warning; unset → `τ_sun` aliases `τ_up` with a warning.
- `atmosphere.modtran.tape7_up_path` — optional target→sensor up-leg tape7 (§5.1, Gap 94). Requires `tape7_path` (the full column). Set → `τ_up`/`L_path_up` from this file and airborne targets (`h_tgt > 0`) accepted; unset → airborne targets rejected on the file-import path.
- `atmosphere.modtran.flux_path` — optional spectral flux CSV supplying downwelling (§5.1, CU-157). Requires `tape7_path`. Set → the DOWN column feeds `E_sky_thermal` (thermal band) and `E_sky_scattered` (reflective-solar band), superseding the Gap 81 zeros; unset → both sky terms stay zero with the Gap 81 warning.
- `atmosphere.modtran.binary_path` — cross-platform default (CU-151): `modtran` on `PATH`, else the per-platform install location (POSIX `/usr/local/bin/modtran`; Windows `C:\Program Files\MODTRAN\modtran.exe`). Existence is checked at first use (not config load) and a missing binary raises `ModtranUnavailableError`.
- `atmosphere.modtran.cache_dir` — created if missing.
- `atmosphere.modtran.allow_fallback` — if `True`, falls back to simple parametric on missing binary.
- `atmosphere.modtran.atmosphere_profile` — maps to `MODEL` 1–6.
- `atmosphere.modtran.aerosol_model` — maps to `IHAZE`.
- `atmosphere.modtran.h2o_scale` — `H2OSTR = "1.0g"` syntax handled by deck builder.
- `atmosphere.modtran.o3_scale` — same (dimensionless multiplier).
- `atmosphere.modtran.cloud_model` — cloud fraction is 0/1 in v1 (stubbed for fractional).
- `atmosphere.modtran.disort_streams` — 4 for fast mode; 8 for production; 16 reserved.
- `atmosphere.modtran.spectral_resolution_cm1` — drives `DV` and `FWHM`.
- `atmosphere.modtran.extra_cards` — override hatch; recorded in cache key.

### 6.5 Geometry (consumed, not owned)

These parameters live in `geometry.*`, owned by GeometryStage since ADR-0006 (definitions in `geometry/_schema.py`, not this stage's schema); the atmosphere module reads them through the parameter resolver:

`geometry.sensor_altitude_m`, `geometry.target_altitude_m`, `geometry.path_zenith_deg`, `geometry.solar_zenith_deg`, `geometry.solar_azimuth_deg`, `geometry.observer_type`, `geometry.target_type`, `geometry.day_of_year`.

**Producer-side note (CU-009; amended by ADR-0006 Phase 2):** SourceStage adopts the scene `LineOfSightGeometry` that GeometryStage publishes (`stage_outputs["geometry"]["los_geometry"]` — built once from the resolved viewing/solar input mode) and descriptor-adjusts it (`source/_inferrer._adjust_scene_los`); the legacy param-built `_infer_los` path survives only for direct `infer_descriptors` callers (source-only unit fixtures). The solar-zenith and solar-azimuth values propagate only when the target descriptor is solar-interacting (`T2Reflective`, `T3Mixed`); pure-thermal `T1Thermal` targets receive `theta_s = delta_phi = None` regardless of the registered solar params, honoring the `LineOfSightGeometry` "None for pure-thermal" docstring contract.

### 6.6 Turbulence

Parameter types, defaults, units, and bounds are the canonical [Parameter Reference](../guides/parameter_reference.md) (auto-generated from the schema — the single source of truth, Rule 27). Design context:

- `atmosphere.r0_m` — Fried parameter [m] entered directly. Default 0 = turbulence off. Quoted at the scene's band-centre wavelength.
- `atmosphere.cn2_profile` — `direct` (default, use `r0_m` verbatim), `hufnagel_valley`, or `tabulated`. Selecting a profile makes $r_0$ a derived quantity (§7.1).
- `atmosphere.cn2_hv_wind_rms_m_s`, `atmosphere.cn2_hv_ground_strength` — the two HV coefficients $w$ and $A$; the defaults are HV-5/7.
- `geometry.site_elevation_m` — the terrain elevation the HV **surface term** is referenced to (CU-262, §7.1 "Site elevation"). Default 0 = sea level. Owned by the geometry schema because it is a scene-geometry fact, not a turbulence coefficient; consumed today only by the `hufnagel_valley` profile. A non-zero value set against any other `cn2_profile` is **inert, and says so** — `cn2_profiles.warn_if_site_elevation_inert` raises a `UserWarning` naming why the input cannot reach that profile and what to do instead (CU-302, Rule 17).
- `atmosphere.cn2_tabulated_file` — two-column `altitude_m,cn2_m^-2/3` CSV, read pre-chain (Rule 6) by `loaders.build_cn2_profile` and injected at `stage_outputs["atmosphere_config"]["cn2_profile"]`.
- `atmosphere.turbulence_wave_type` — `plane` (default) or `spherical` path weighting (§7.1).

There is no `turbulence_enabled` flag and no observer-type gate: `r0_m = 0` with `cn2_profile = 'direct'` *is* "off", and a path that crosses no atmosphere resolves to "off" by itself.

---

## 7. Atmospheric Turbulence

### 7.1 What RADIANT implements

**The MTF.** A Kolmogorov long-exposure MTF, applied as a term in the spatial model, not in `AtmosphereStage`'s radiometric output:

$$\mathrm{MTF}_{turb}(f) = \exp\!\left[-3.44\,\left(\frac{\lambda f}{r_0}\right)^{5/3}\right]$$

with $f$ the angular spatial frequency [cycles/rad] and $r_0$ the Fried parameter at the wavelength of interest. `atmosphere/turbulence.py` holds the formula; the PSF-path kernel is built in `platform/turbulence_kernel.py` and the MTF-product term in `performance/turbulence_mtf_term.py` (Rule 4 — both paths, one physics).

**The Fried parameter.** $r_0$ reaches those consumers through `stage_outputs["atmosphere"]["r0_m"]`, resolved by `atmosphere/r0_resolution.py`:

| `atmosphere.cn2_profile` | `atmosphere.r0_m` | Result |
|---|---|---|
| `direct` (default) | any | used verbatim; `0` = turbulence off. No geometry consulted. |
| a profile | unset | derived from the path integral below. |
| a profile | user-set, agrees within 1 % | the **entered** value wins; the profile is a recorded cross-check. |
| a profile | user-set, disagrees > 1 % | `TurbulenceSpecificationError` (the CU-093 redundant-entry pattern). |
| a profile | user-set to `0` | `TurbulenceSpecificationError` — contradictory intent. |

**The path integral** (`atmosphere/r0_path.py`, Gap 110):

$$r_0 = \left[\,0.423\,k^2 \sec\zeta \int_{h_{low}}^{h_{high}} C_n^2(h)\,W(h)\,\mathrm{d}h\right]^{-3/5},\qquad k = 2\pi/\lambda$$

- $\zeta$ is the zenith angle at the segment's **lower endpoint** — the same ADR-0011 decision-3 convention `ColumnSegmentSpec` and the MODTRAN Card-3 deck builder use. It comes from `observer_leg.py` for up-looking paths and is $\theta_o$ for down-looking ones. $\sec\zeta$ is refused past `ZENITH_CEILING_RAD` (89.5°), which the Phase-1 horizon guard already forbids.
- **Integration limits are direction-aware**: the endpoint altitudes clipped into `[0, h_atm_top]`. A ground sensor gets the full column above it; an airborne sensor a partial one; a space sensor's residual column is empty, giving a finite huge $r_0$ saturated at `R0_NEGLIGIBLE_M` (1 km) with `negligible = True`, whereupon the term is **omitted entirely** rather than multiplied in as unity (§8 item 5). This replaces the retired space-observer `ScopeError` (ADR-0011 guardrail G4 / Rule 27).
- **Weighting** $W$, parameterized by $u(h) = (h - h_{tgt})/(h_{sen} - h_{tgt}) \in [0,1]$ — the fraction of the way from the target to the aperture: `plane` (default) is $W = 1$, the source-at-infinity imaging case that published $r_0$ values assume; `spherical` is $W = u^{5/3}$, **maximum at the aperture and zero at the target**, the finite-range point-source case. Turbulence near the sensor therefore dominates.
- **Level (constant-altitude) paths** are not columns — $\sec(\pi/2)$ diverges. They integrate along the true chord at constant altitude: $C_n^2(h)\,L$ (plane) or $C_n^2(h)\,L\cdot 3/8$ (spherical, since $\int_0^1 u^{5/3}du = 3/8$).
- Quadrature is a graded-grid trapezoid refined by doubling until it converges to $10^{-6}$ relative; failure to converge raises (Rule 17).

**Profiles** (`atmosphere/cn2_profiles.py` is the contract; one implementation per module, Rule 19):

- `hufnagel_valley` (`cn2_hufnagel_valley.py`) — the three-term HV form parameterized by the RMS upper-atmosphere wind $w$ and ground strength $A$; the schema defaults are HV-5/7 ($w = 21$ m/s, $A = 1.7\times10^{-14}$ m$^{-2/3}$), which reproduce the published $r_0 = 5$ cm and $\theta_0 = 7$ µrad at 0.5 µm for a vertical path.
- `tabulated` (`cn2_tabulated.py`) — a measured (altitude, $C_n^2$) table, log-linearly interpolated (linearly across a zero endpoint), **zero outside its range** with a `UserWarning` quantifying the uncovered extent. A measured table already carries the site it was taken at, so `geometry.site_elevation_m` does **not** shift it — the altitudes in the file are used as written, and a non-zero elevation emits the CU-302 inert-input `UserWarning` rather than being dropped silently.

**Site elevation — which altitude reference each HV term uses (CU-262).** RADIANT altitudes are metres above mean sea level; the HV literature writes the profile against height above the *site*. The two disagree by exactly the terrain elevation, and that disagreement is only harmless for two of the three terms:

$$C_n^2(h) = \underbrace{0.00594\left(\tfrac{w}{27}\right)^2 (10^{-5}h)^{10}e^{-h/1000}}_{\text{jet stream — MSL}} + \underbrace{2.7\times10^{-16}e^{-h/1500}}_{\text{free atmosphere — MSL}} + \underbrace{A\,e^{-(h - h_{site})/100}}_{\text{surface layer — site-referenced}}$$

The jet stream is at 10 km MSL wherever the ground below it is, and the 1500 m-scale-height background is a free-atmosphere property, so both stay on MSL. The surface term is different: its 100 m scale height means a 900 m observatory evaluated against MSL sits $e^{-9} \approx 1.2\times10^{-4}$ into its own boundary layer — it loses the layer entirely and reports $r_0 = 15.0$ cm (0.67″ seeing) at 0.5 µm where HV-5/7 is *defined* to give 5 cm (2.0″). Referencing the surface term to $h_{site}$ restores the anchor to 5.22 cm (1.94″); the residual +4 % is the genuine altitude benefit of starting 900 m up the free-atmosphere column, not a lost boundary layer.

**Choosing $A$ for your site.** The HV-5/7 default $A = 1.7\times10^{-14}$ m$^{-2/3}$ is a near-sea-level *daytime* ground strength. Now that the surface term follows the terrain (CU-262), carrying that default unchanged to an elevated site gives that site a full sea-level-strength boundary layer — ~1.94″ seeing at a 900 m site, correct for the model but far too pessimistic for any decent observatory, whose site was chosen precisely for a weak surface layer. $A$ is a *site quality* parameter and should be set from measured seeing: solve the §7.1 path integral for the $A$ that reproduces the site's median seeing. Worked anchor (CU-262's Paranal case): $A = 2.70\times10^{-15}$ m$^{-2/3}$ reproduces the 0.80″ median at the 2635 m elevation. **Migration warning:** before CU-262 the only way to make elevation matter was to *absorb it into an inflated (or deflated) $A$*; that workaround is obsolete and now double-counts — a config carrying a compensated $A$ together with a non-zero `geometry.site_elevation_m` applies the site correction twice. Re-derive $A$ from measured seeing with the elevation set honestly. (No shipped scenario used the workaround — checked during CU-262.)

*Whose site is it?* — per topology, with the physics reason:

| LOS topology | Site is the terrain under… | Why |
|---|---|---|
| down-looking (`h_sensor > h_tgt`) | the **target** | The path descends toward the target; the only boundary layer it can enter is the one over the target's ground. |
| up-looking (`h_sensor < h_tgt`) | the **sensor** | The path rises from the sensor; the boundary layer it looks up through is the one the sensor stands in. The observatory / SST case. |
| level (`h_sensor == h_tgt`) | **both, jointly** — the arm's own terrain | Both endpoints are at the same altitude, so there is one terrain beneath the whole arm. |

In every row it is the same single number: the elevation of the terrain beneath the line of sight. It is deliberately **not** derived from the lowest point of the line of sight — that proxy would put a 100 m-scale-height boundary layer at 10 km for a level air-to-air leg, inventing turbulence that is not there. No topology needs a special case for an endpoint that is airborne over the site: the 100 m scale height suppresses the surface term on its own ($e^{-91}$ for a 10 km leg over a 900 m site), so **a level air-to-air path carries no surface term**, while a genuinely near-surface horizontal link keeps the layer it physically sits in.

An altitude below $h_{site}$ is inside the terrain and is refused with a `ParameterBoundsError` (Rule 16/17) — most often it means the declared site elevation and the path's lower endpoint describe different scenes. At the default $h_{site} = 0$ that check is exactly the pre-CU-262 "altitude must be ≥ 0" check, and $e^{-(h-0)/100} \equiv e^{-h/100}$, so **every existing result is bit-identical**.

**Reference wavelength.** $r_0 \propto \lambda^{6/5}$ exactly. The derived value is computed at the **band-centre wavelength of the scene's spectral grid** — the same wavelength `OpticsStage` uses for its monochromatic PSF reference, so the number is quoted at the wavelength its consumers apply it at. The value is published on `stage_outputs["atmosphere"]["r0_resolution"]` (present only when a profile was evaluated, so a scene using the direct input sees exactly the outputs it saw before Gap 110). A directly-entered `r0_m` is rescaled **only if you say what wavelength it is quoted at**, via `atmosphere.r0_reference_wavelength_um` (CU-228): when set, the value is scaled to the band centre by $(\lambda_{band}/\lambda_{ref})^{6/5}$ and both numbers are recorded in the resolution detail. Left unset (the default), the entered value is taken as already being at the operating wavelength — the pre-CU-228 behaviour, preserved bit-identically so no existing config moves.

This matters more than it looks: seeing is habitually quoted at 0.5 µm, and $r_0 \propto \lambda^{6/5}$ means the astronomer's 10 cm becomes **1.3 m** at a 4.25 µm band centre. Entering the habitual number and running an MWIR scene therefore makes the turbulence MTF about an order of magnitude too aggressive. RADIANT cannot detect that from the number alone, so it warns whenever `r0_m` is set, the reference is unset, **and** the band centre is more than a factor of two from 0.5 µm — the case where a mis-entered visible value is the likely explanation. A scene genuinely working near 0.5 µm stays quiet.

### 7.2 What RADIANT does *not* implement

- **Anisoplanatism** (off-axis turbulence degradation) and the isoplanatic angle $\theta_0$ as a published metric.
- **Scintillation** (irradiance fluctuations).
- **Tilt vs. higher-order decomposition** (adaptive optics).
- **Short-exposure MTF** (the tilt-removed correction term).
- **von Kármán outer scale** — Kolmogorov ($L_0 = \infty$) only.
- **Dome and platform-induced seeing.**
- **Turbulence-induced beam wander / refraction of the path itself** — the geometry is unrefracted (ADR-0011 decision 5).

These are absent, not stubbed: no parameter, no dataclass field, no `NotImplementedError` placeholder.

### 7.3 Why turbulence is in the atmosphere module but applied as MTF

Turbulence is physically an atmospheric phenomenon (refractive index fluctuations along the path) but it acts on the chain *spatially*, not radiometrically — total energy is conserved and only the PSF is modified. Putting the turbulence MTF generation in the atmosphere module keeps all atmosphere-related physics in one place (parameter inventory, documentation, plugin entry point), while the *application* of that MTF lives in the spatial model where the rest of the MTF cascade is computed. This is the same pattern the optics module uses for `MTF_diffraction`: generated in `optics/diffraction.py`, applied in the system MTF cascade.

---

## 8. The `AtmosphereStage`

Per RADIANT_Signal_Chain_Architecture.md §2, `AtmosphereStage` is the second stage in the chain. Its responsibilities:

1. **Resolve the atmosphere model** — preferentially the pre-built model injected at `stage_outputs["atmosphere_config"]["model"]` (see §8.1); only non-file-backed models may be built inline as a partial-chain fallback — and **build the `AtmosphericState`** from it.
2. **Apply transmittance and add path radiance** to produce the `at_aperture` reference frame:
   ```
   L_at_aperture(λ) = L_at_target(λ) · τ_atm(λ) + L_path(λ)
   ```
3. **Register the `at_aperture` frame** on the `ChainState` per the architecture document.
4. **Register `L_atm_down(λ)`** in `state.stage_outputs["atmosphere"]["downwelling"]` so the source stage's reflected-solar paths can consume it on their next pass (the `SkyBackground` arm does *not* read it — its radiance arrives on `TopologyProducts.sky_radiance_at_aperture`, §4.2g) — this is the only chain-level back-coupling and is handled by re-running `SourceStage` once if the source has a downwelling-dependent component (per RADIANT_Signal_Chain_Architecture.md §6.3).
5. **Resolve and publish the Fried parameter** (§7.1) as `stage_outputs["atmosphere"]["r0_m"]`, and — only when a Cn² profile was evaluated — the `FriedParameterResolution` record as `["r0_resolution"]`. When turbulence is off (or the path carries none), `r0_m` is absent and the downstream turbulence terms are omitted entirely rather than set to unity; the system-MTF cascade simply has one fewer term, which is faster and avoids the temptation to "see" turbulence in a debug plot when it is off. The MTF term itself is built downstream (`platform/` for the PSF kernel, `performance/` for the MTF product), not here.
6. **Store the full `AtmosphericState`** in `state.stage_outputs["atmosphere"]["state"]` for downstream inspection.

`AtmosphereStage` is a pure function of `(state_in, params)` per the architecture document. It does not mutate state, performs **no file I/O** (Rule 6 — see §8.1), and is safely re-runnable.

### 8.1 The Rule 6 loader boundary (`atmosphere/loaders.py`)

Rule 6 forbids stages from reading files, so all file-backed model construction lives in `radiant/atmosphere/loaders.py`, which runs **before** chain execution:

- `build_atmosphere_model(params)` dispatches on `atmosphere.model` and performs any file I/O the model needs (NPZ/CSV tables for `tabulated`, an NPZ directory scan for `interpolated`, tape7 parsing for `modtran` with `tape7_path` set); `exo` and `simple` need no I/O.
- For `interpolated` with no explicit directory, the shipped family is selected from `(LOS direction, interpolation_axes)` (GF-10). Direction must be resolved **pre-chain**, before the `LineOfSightGeometry` exists, so `_scene_los_direction(params)` reproduces `LineOfSightGeometry.los_direction`'s rule from `geometry.sensor_altitude_m` vs `geometry.target_altitude_m`; a test pins the two together so the copies cannot drift. An unregistered geometry schema (partial-chain fixtures) falls back to `down` — the only direction that existed before Phase 2.
- **Config-time coverage check (CU-239).** `build_atmosphere_model` runs `interpolation_coverage.check_interpolation_coverage(params)` before it opens a single NPZ, so a scene the selected axes cannot serve is refused **pre-chain** with the remedy in hand rather than five stages later inside `InterpolatedAtmosphere.evaluate` (which keeps its own check as defence in depth). Two rules: (1) a down-looking scene with `geometry.target_altitude_m > 0 m` needs a `target_altitude_m` axis — one column cannot serve both the target→sensor leg and the ground→sensor full column (Gap 94); (2) an empty `interpolated_data_dir` needs the `(los_direction, axes)` pair to name a shipped family. The error names the **exact axes string to set**, the family it selects with coverage in km/degrees, and — when that family's rendered profile differs from an explicitly-set `atmosphere.standard_atmosphere` — a sentence saying so, because adopting a family must never silently change the profile the operator asked for. `Sensor.validate_atmosphere_coverage()` is the same check as a resolve-time API seam, and `radiant.api.atmosphere_families` publishes the catalogue rows (the loader's dispatch table is derived from them, so there is one authority).
- `FILE_BACKED_MODELS = frozenset({"tabulated", "interpolated"})` names the models that **always** need files; `model_requires_prebuild(params)` is the parameter-aware check the stage uses — it additionally returns True for `modtran` when `atmosphere.modtran.tape7_path` is set (§5.1).
- The API layer (`RadiantSession`, and therefore `Sensor`) calls the loader and injects the constructed model into the chain via `ChainRunner.run(..., initial_stage_outputs={"atmosphere_config": {"model": model}})`; `AtmosphereStage` reads it from `stage_outputs["atmosphere_config"]["model"]`.
- If no injected model is present, the stage builds only non-file-backed models inline (partial-chain convenience). For a file-backed model it **refuses to build inline** and raises a `ValueError` directing the caller to `RadiantSession`/`Sensor` or to `build_atmosphere_model()` + manual injection.

---

## 9. Validation & Sanity Bounds

The atmosphere module enforces a small set of physical sanity checks at `AtmosphericState` construction. Violations raise `AtmosphericPhysicsError` with the offending wavelength(s).

| Check | Bound | Reason |
|-------|-------|--------|
| `0 ≤ τ_atm(λ) ≤ 1` ∀λ | hard | Transmittance is a probability; out-of-bound means corrupt input |
| `L_path(λ) ≥ 0` ∀λ | hard | Path radiance is energy emitted/scattered into the line of sight |
| `L_atm_down(λ) ≥ 0` ∀λ | hard | Same |
| `L_atm_down(λ) ≤ B(λ, T_max)` ∀λ where T_max = 350 K | soft (warn) | Downwelling thermal cannot exceed a hot graybody; failure suggests unit confusion |
| `air_mass ≥ 1` | hard | Geometry sanity |
| `slant_path_length_m > 0` for non-exo | hard | Same |
| For MODTRAN: tape7 spectral range covers the global wavelength grid | hard | Otherwise interpolation would extrapolate; user must widen the MODTRAN run |
| For tabulated: ascending λ, no duplicates | hard | Per RADIANT_Conventions.md §2 |

The "soft" warning bounds are RADIANT-specific tripwires for the most common form of user error (units), not physics constraints. They are easy to silence if a user really does want to model a 1000 K atmosphere.

---

## 10. Plugin Hook **[DESIGN-TARGET]**

> **Not implemented.** The `plugins/` package was removed 2026-07-06 (see
> `RADIANT_Plugins.md`, DEFERRED banner). There is no `AtmospherePlugin` ABC and
> no `radiant.plugins.atmosphere` entry point. The five built-in models are
> dispatched directly by `atmosphere/loaders.py` (`build_atmosphere_model`) and
> `assembly.py`, **not** through a plugin registry — so the claim below that "the
> plugin interface is the only interface" is design intent, not current behavior.
> The extension-point design returns when `RADIANT_Plugins.md` is implemented.

Per the (deferred) plugin design, atmosphere would be a plugin extension point: users could register a custom `AtmospherePlugin` that returns an `AtmosphericState` from a parameter set. This is how a future libRadtran or 6S wrapper would integrate without touching core code.

```python
class AtmospherePlugin(ABC):
    name: str
    @abstractmethod
    def build_state(
        self,
        params: ParameterSet,
        geometry: AtmosphericGeometry,
        wavelength_um: np.ndarray,
    ) -> AtmosphericState: ...
```

Plugins are registered via the `radiant.plugins.atmosphere` entry point (see RADIANT_File_Tree.md §"Plugin entry points"). The four built-in models (`simple`, `tabulated`, `modtran`, `exo`) are themselves plugins registered by the core distribution, so there is no special-cased "core vs. plugin" path — the plugin interface is the only interface.

---

## 11. Out of Scope for v1

Recorded explicitly so future RADIANT_Scope_Decisions.md updates can lift them deliberately:

- **Polarized atmospheric radiative transfer.** Stokes vectors are not propagated; everything is treated as unpolarized intensity.
- **3D / heterogeneous atmospheres.** Plane-parallel only. No broken-cloud handling, no horizontal gradients.
- **Time-dependent atmospheres.** A scenario specifies one atmospheric state; time-series scenarios re-build the state per frame.
- **Adjacency effects.** The reflected-solar contribution from neighboring ground pixels is not modeled (a 6S/MODTRAN-style "background reflectance" term).
- **Auroral and airglow emission.**
- **Refraction-induced apparent altitude shifts.** A target at zenith angle 89.5° is treated geometrically; the apparent vs. true altitude correction is deferred.
- **Cloud microphysics.** Clouds in v1 are either "off" or "MODTRAN's canned cloud model"; no LWC/effective-radius parameterization.

---

## 12. Open Questions

1. **MODTRAN version compatibility.** RADIANT targets MODTRAN 5 and 6 tape7 formats. Earlier versions are not supported. Confirm with the program office before locking the parser.
2. **Wavelength grid for `simple` aerosol fits.** The Ångström-α model is good in VIS/SWIR and is already weak in MWIR; it is *wrong* in LWIR. **Implemented (CU-088, 2026-07-12):** aerosol extinction is clamped at the **MWIR–LWIR boundary** (`AEROSOL_CLAMP_WAVELENGTH_UM = 5.0 µm`) — the "weak but usable" MWIR power law is preserved, and beyond 5 µm the extinction is frozen at its 5 µm value instead of decaying unphysically toward zero (real IR aerosol extinction is absorption-dominated and roughly flat). `SimpleAtmosphere` warns once per run when the clamp engages. The boundary was placed at MWIR–LWIR rather than the originally-planned SWIR–MWIR so the flagship MWIR baseline is unchanged and only the genuinely-wrong long-wave extrapolation is corrected. A tabulated aerosol cross-section per type remains the higher-fidelity alternative for quantitative IR aerosol work.
3. **Where does `day_of_year` live?** It is a geometry concept (drives sun position) but only the atmosphere/MODTRAN path consumes it directly. Currently filed under `geometry.day_of_year`; revisit if a non-atmospheric consumer appears.
4. **Should the simple model expose its single-scatter `L_path` decomposition?** MODTRAN does (thermal, scattered, single-scatter solar). The simple model could too, at the cost of more code. Probably yes.

---
