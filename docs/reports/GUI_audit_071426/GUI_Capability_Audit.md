# RADIANT GUI Capability Audit — Screen-by-Screen Missing-Feature Findings

**Status:** Complete (point-in-time audit — immutable per Rule 24/28; corrections are new documents)
**Date:** 2026-07-15
**Auditor:** Coding agent, owner-requested
**Scope:** Every GUI surface after Phase I ("v1 shipped"): the 9 signal-chain stage screens
(Geometry, Source, Atmosphere, Optics, Platform, Spectral Integration, Detector, Readout,
Performance) plus the cross-cutting surfaces (scripting console, sweep/comparison, plotting,
export, right rail, menu bar).
**Authority / method:** The ~40 scenario `gui_workflow.md` docs (8 personas) are the requirement
spine; first-principles physics/UX judgment is layered on. Requirements were cross-referenced
against (a) what each per-stage GUI form actually exposes today, (b) what the engine `_schema.py`
files and loaders actually support, and (c) the existing Gap Registry (`docs/tracking/gaps.md`,
Gaps 69, 80–92). No code was modified.

> **Concurrent work note.** A separate agent is implementing `Target_Extent_Geometry_Plan.md`
> against the **base code** (not the GUI). Geometry findings here are GUI-surface findings; where
> one depends on that plan's parameter/geometry changes it is flagged **[coord: TEG]** so the two
> efforts don't double-implement.

---

## 1. Executive Summary

**The single most important finding:** RADIANT's GUI is a *thin scalar skin over a rich engine*.
The Phase-I forms expose a small set of scalar `ParameterDef`s per stage, but the engine already
supports — via YAML / `params.set()` / file loaders — almost every capability the scenario docs
demand. The dominant work is therefore **surfacing existing engine capability**, not building new
physics. This is good news: most P0/P1 items are GUI-only or GUI-plus-a-config-plumbing task, not
physics tasks.

Concretely, the forms expose today:

| Screen | Fields exposed today | Engine actually supports |
|--------|---------------------|--------------------------|
| Geometry | mode selectors + derived readout (rich) | + solar geometry (zenith/az, day/night, site+date+LTAN), orbital derivation |
| **Source** | 6 fields: target/background/contrast-ref **T + ε only** | reflectance/albedo (scalar+spectral), brightness/radiance temp, user radiance/intensity, materials, shapes, `scene_type` |
| **Atmosphere** | **NO input form at all** (2 plots only) | **5 models** (`simple`/`exo`/`tabulated`/`modtran`/`interpolated`), MODTRAN tape7 import, profile/aerosol/PWV, turbulence r₀ |
| **Optics** | 8 scalars (aperture, f, f/#, obsc, spiders, τ scalar, WFE RMS, T) | 5 transmission modes, per-element R/T/ε train, Zernike/Zemax WFE, defocus, scatter, stray-light, poly-PSF |
| Platform | jitter (iso + x/y), ground vel, smear length | (essentially complete) |
| Spectral Integration | filter min/max, integration time | (complete — top-hat band is the whole model) |
| **Detector** | 6 scalars (QE, dark rate, pitch x/y, fill, T) | spectral QE(λ), QE(T), Arrhenius dark, 1/f, G-R, persistence, IPC, diffusion, FPN |
| **Readout** | 4 scalars (read noise, gain, ADC bits, well) | **TDI (analog/digital, misalign)**, binning, coadds, kTC, electronics MTF |
| Performance | metric readout + system MTF + MTF budget | + GSD/RER/Strehl/Q/EE/NEDT/NIIRS all in `result.metrics` |

**Cross-cutting, the biggest structural gaps:**

- **The entire Run menu is disabled scaffolding** — *Evaluate*, *Run Sweep…*, *Monte Carlo…*,
  *Batch Run…* are all `enabled=False` placeholders. Sweeps and comparison — the dominant workflow
  shape for Mike, Raj, Lisa, Tom, and both interpolation demos — have **no GUI surface**; the
  scripting console is the only path.
- **The entire export surface is disabled** — *Export YAML*, *Export JSON Result* are placeholders.
  No CSV/Excel/PDF/PPT/PNG export exists, yet nearly every doc asks for one.
- **No data-import surface** — unit-aware spreadsheet/CSV import (QE curves, dark-current curves,
  ASTER emissivity, target libraries, tape7, Zemax Zernike) is required by ~20 docs; the engine has
  every loader (`io/qe_csv.py`, `io/dark_current_csv.py`, `io/aster_library.py`,
  `io/target_library.py`, `io/zemax_zernike.py`, `io/element_config.py`) but the GUI exposes none.
- **A structural reach-ability blocker:** the non-scalar optics/atmosphere capabilities (element
  lists, filter stacks, Zernike screens, stray-light spectra, tabulated atmospheres) are injected
  as pre-chain **config objects** under `stage_outputs['optics_config']` etc., *not* as flat
  `ParameterDef`s. A form driven only by `ParameterDef`s **cannot reach them** — surfacing them
  needs a config-object editing surface, not just more `FieldRow`s. See §12.

### Severity tally (distinct findings)

| Severity | Count | Meaning |
|----------|-------|---------|
| **P0 — Blocking** | 8 | A whole class of scenarios is impossible in the GUI today |
| **P1 — Major** | 27 | Engine-supported capability required by multiple scenarios, GUI-absent |
| **P2 — Moderate** | 24 | Single-scenario or refinement; or a partial surface exists |
| **P3 — Deferred/engine-gap** | 12 | Capability absent in the *engine* too — a tracked gap, not a GUI-only fix |

### The 8 P0 (blocking) findings

1. **Source: no reflective/solar input path** — VIS scenarios cannot set target reflectivity/albedo;
   MWIR mixed emit+reflect cannot be configured. Engine has `source.target.reflectance`/`albedo`
   (+spectral) fully. (§3)
2. **Atmosphere: no input form whatsoever** — cannot choose a model, select a profile, or import a
   MODTRAN/tape7 run. Engine has 5 models behind `atmosphere.model`. (§4)
3. **Optics: no element / coating definition** — cannot map per-element %R/%T/temperature/emissivity;
   only the lumped scalar throughput is editable. Engine has the full element-list mechanism. (§5)
4. **No GUI sweep surface** — *Run Sweep…* disabled; the dominant persona workflow has no home. (§11.2)
5. **No GUI comparison surface** — side-by-side config/band/vendor comparison required by ≥10 docs;
   nothing exists. (§11.4)
6. **No import surface** — unit-aware spreadsheet/CSV import required by ~20 docs; loaders exist,
   GUI absent. (§11.6)
7. **No export surface** — CSV/Excel/PDF/PPT/PNG/YAML all required; menu items disabled. (§11.5)
8. **No scene-type / mission-type selector** — declared `scene_type` axis exists in the engine
   (`source.scene_type`, `source.regime_override`) but is unexposed; owner-requested (Gap 85 /
   CU-…). (§3, §13)

---

## 2. Classification legend

Every missing-capability row is tagged with a **class** (where the fix lives) and a **severity**.

**Class — where does the capability already live?**

| Class | Meaning | Implication |
|-------|---------|-------------|
| **[E]** | Exists in the engine as a flat `ParameterDef` | Pure GUI work: add a field/control bound to the existing dot-path |
| **[C]** | Exists in the engine only as an **injected config object** (`stage_outputs['*_config']`) or file loader, not a `ParameterDef` | GUI **plus** a config-editing/plumbing surface (see §12) |
| **[A]** | A public **API accessor** exists (`result.plot.*`, `ErrorBudget`, sweep helper) but the GUI doesn't consume it | GUI wiring to an existing one-call surface |
| **[X]** | Absent in the engine/API too | A true capability gap — tracked in `gaps.md`; **not** a GUI-only fix |

**Severity**

- **P0** — a whole class of scenarios cannot be performed in the GUI at all.
- **P1** — a capability required by multiple scenarios; engine-supported; GUI-absent.
- **P2** — single-scenario, refinement, or a partial surface already exists.
- **P3** — deferred / engine-gap (class [X]); listed for completeness, owner-triaged separately.

---

## 3. Source screen

**Exposed today** (`source_inputs_form.py`): exactly six fields — target T, target ε, background T,
background ε, contrast-reference T, contrast-reference ε — plus the shared target shape/orientation
editor and the tentative-regime readout. The stage note explicitly says "all source inputs are shown
ungated; per-scenario-type input relevance is deferred (Gap 85)."

**The gap in one line:** the Source screen can only express a *graybody thermal emitter*. Every other
target-specification pathway the engine supports is invisible.

| # | Missing capability | Class | Engine surface (exists today) | Docs | Sev |
|---|--------------------|-------|-------------------------------|------|-----|
| S-1 | **Target reflectivity / albedo for VIS solar** (scalar) | **[E]** | `source.target.reflectance`, `source.target.albedo` | 1.2 | **P0** |
| S-2 | **Spectral reflectance ρ(λ)** import | [E]/[C] | `source.target.reflectance_path` (CSV) | 1.2, 4.3 | P1 |
| S-3 | **Day/night solar toggle** — reflected-solar term appears/vanishes; thermal-vs-solar ratio per band; flag MWIR daytime solar contamination | **[E]** | `geometry.solar_illumination` (`day`/`night`), reflected-solar physics | 3.5, 1.2 | **P0** |
| S-4 | Solar-geometry helpers (zenith vs season/LTAN/latitude) with live echo | [E] | `geometry.solar_zenith_rad`, site+date+`ltan_h` modes (S3) | 1.2, 3.1 | P1 |
| S-5 | **Scene-type / regime declaration selector** (extended / sub-pixel / point) with relevance gating | [E] | `source.scene_type`, `source.regime_override`, `source.target_location`, `source.no_atmosphere_subcase`, `source.lab_test_mode` | 1.3, 4.1, 4.5, 2.3, 7.x | **P0** |
| S-6 | Fill-fraction + sub-pixel apparent-contrast helper (fill × ΔT × τ) | [E] | `source.target.fill_fraction` | 4.5, 4.3 | P1 |
| S-7 | Brightness / radiance-temperature input (IR remote sensing) | [E] | `source.target.brightness_temperature_K`(+`_path`), `radiance_temperature_K` + band edges | 6.5 | P2 |
| S-8 | User-radiance-path input — compose L_t(λ)=ε(λ)·B(λ,T), feed radiance path | [E]/[C] | `source.target.user_radiance_path`, `user_intensity_path` | 4.3, 3.5 | P1 |
| S-9 | Named-material picker for target & background ε(λ) | [C] | `source.background.material` + `SpectralLibrary` (`data/library.py`), `emissivity_path` | 1.3, 4.3 | P1 |
| S-10 | Target-library / ship-class import (dims, T, ε, material → projected area, √(L·H)) | [C] | `io/target_library.py` (Excel) | 4.1, 4.2 | P1 |
| S-11 | Clutter σ input for SCNR | [E] | `detector.clutter_sigma` (note: lives in detector schema) | 1.3, 4.1, 4.3 | P1 |
| S-12 | Diurnal/thermal-profile import + ΔT-vs-time plot with crossings | [X] | no profile-timeseries source | 4.4 | P3 |
| S-13 | Hot-target opt-out (force pure-emit) | [E] | `source.target.is_hot_target` | 1.3, 3.5 | P2 |
| S-14 | 2-D scene canvas: place targets, PSF-convolve, mixed-radiance image | [X] | not in engine | 6.4 | P3 |
| S-15 | Noisy 1-D scene-strip generator (seed + re-roll) + contrast-SNR map | [X] | not in engine (synthetic-scene, Gap) | 6.4 | P3 |
| S-16 | LST/GeoTIFF raster ingestion → background envelope | [X] | not in engine | 3.5 | P3 |
| S-17 | Solar model / distance selector (non-Earth-orbit reflective) | [X] | `ReflectedSolarSource.solar_model`/`distance_au` are **hardcoded**, not `ParameterDef`s; `astm_e490` stubbed | (dual-use) | P3 |

**Physics/UX judgment notes.**
- The reflective pathway (S-1/S-2) is the flagship gap the owner named. It is *pure* [E] work for the
  scalar case — the engine routes to `T2Reflective` the moment `source.target.reflectance` is set.
- S-3 (day/night) is physically load-bearing for MWIR: the reflected-solar term competes with thermal
  emission in-band, and the current GUI silently omits it. The regime note under the Source view should
  state which terms are active.
- S-5 (scene-type selector) is the inverse-workflow the owner has asked for repeatedly (Gap 85, plus the
  mission-type memory). The engine axes already exist; the missing piece is (a) per-regime relevance
  metadata on the `ParameterDef`s and (b) the selector + badging. This is the one P0 that is *not* pure
  GUI — it needs the schema-metadata prerequisite first.

---

## 4. Atmosphere screen

**Exposed today:** *nothing editable.* `STAGE_COMPOSITIONS["atmosphere"]` carries only two plots
(τ_atm & L_path; radiance at aperture). There is no atmosphere input form, no model selector, no
profile picker, no import button anywhere in the GUI.

**The gap in one line:** the most configurable stage in the engine (five backends behind one enum,
a live MODTRAN wrapper, a tape7 importer, a run-matrix interpolator) is entirely un-configurable in
the GUI.

| # | Missing capability | Class | Engine surface | Docs | Sev |
|---|--------------------|-------|----------------|------|-----|
| A-1 | **Atmosphere model selector** (`simple`/`exo`/`tabulated`/`modtran`/`interpolated`) | **[E]** | `atmosphere.model` enum; `build_atmosphere_model()` dispatch | 1.1, 6.2, 2.3, 7.1 | **P0** |
| A-2 | Standard-atmosphere profile selector (tropical / midlat_summer / … / us_standard) | [E] | `atmosphere.standard_atmosphere` enum | 3.2, 3.5, 4.1 | P1 |
| A-3 | Aerosol-type selector (rural/urban/maritime) + visibility + PWV inputs | [E] | `atmosphere.aerosol_type`, `visibility_km`, `precipitable_water_cm` | 3.2, 4.1, 3.5 | P1 |
| A-4 | **MODTRAN tape7 import** (single + two-leg sun path); show τ curve; CU-066 header/fallback status | [E]/[C] | `atmosphere.modtran.tape7_path`, `..._sun_path`, binary/cache/fallback, profile/aerosol/H2O/O3/resolution | 1.1, 6.2 | **P0** |
| A-5 | **Radiance/transmittance before-vs-after atmosphere** side-by-side; band-mean τ range | [A] | `result.plot.spectral_source` (at-aperture) + `spectral_atmosphere` (τ, L_path) already exist; need the paired "before" (Gap 91 emission frame, now `spectral_source_emission`) | 2.3, 3.2, 3.4 | **P1** |
| A-6 | **Plots vs altitude / range / angle** (τ-vs-off-nadir; radiance-vs-altitude; LEO-through-atmosphere) | [A]/[X] | no native sweep surface (§11.2); values computable per-point | 3.4, 2.3, 3.2 | **P1** |
| A-7 | "Swap atmosphere, keep everything else" A/B toggle re-running identical config | [E]/[A] | model enum + re-eval; needs comparison surface (§11.4) | 6.2, 1.1 | P1 |
| A-8 | Tabulated-atmosphere file import (τ/path-radiance/downwelling CSV/NPZ) | [C] | `atmosphere.tabulated_*_file` | 1.1, 6.2 | P1 |
| A-9 | Interpolated run-matrix selector + family registry browser (`FAMILIES`) | [C] | `atmosphere.interpolated_data_dir`, `interpolation_axes`, `interpolation_method` | 8.1, 8.2, 6.2 | P1 |
| A-10 | Turbulence r₀ (Fried parameter) input | [E] | `atmosphere.r0_m` | 5.x, ground | P2 |
| A-11 | Visibility sweep (log) + PWV sweep (linear) + stacked signal-vs-PWV | [E]+sweep | params exist; needs sweep surface | 3.2 | P1 |
| A-12 | Named weather presets (clear/haze/tropical) + preset↔PWV coupling warning | [X]/[E] | preset bundling not in engine; components ([E]) exist | 3.2, 4.1, 3.5 | P2 |
| A-13 | Six-profile small-multiples spectral overlay + spectral residual (A−B) + per-band error table | [A]/[X] | plot accessors exist; residual/multi-atmosphere compare surface absent | 6.2 | P2 |
| A-14 | Cloud / rain / fog condition | **[X]** | **not in engine (Gap 82)** | 3.2 | P3 |
| A-15 | libRadtran atmosphere parser | [X] | not in engine | 6.2 | P3 |

**Physics/UX judgment notes.**
- A-5 is exactly the owner's "show radiances after atmospheric propagation separately from the
  atmospheric radiation" request. The plumbing is nearly complete: `spectral_source_emission`
  (pre-atmosphere, Gap 91 closed), `spectral_atmosphere` (τ & L_path), and `spectral_source`
  (at-aperture) accessors all exist. The Atmosphere screen just needs to lay them out as a
  before/after pair with the path-radiance (self-emission) term broken out.
- A-6 ("plots vs altitude or range") is the owner's other explicit ask. It is blocked on the missing
  sweep surface (§11.2), not on physics — every point is a normal evaluate.
- A-1/A-4 are P0 because with no model selector the GUI is silently pinned to whatever `atmosphere.model`
  the loaded YAML carried; a user cannot switch `simple`↔`modtran` or load a tape7 at all.

---

## 5. Optics screen

**Exposed today** (`optics_inputs_form.py`, 4 tabs): 8 scalar fields (aperture, focal length, f/#,
obscuration, spider arms, scalar τ_opt, WFE RMS waves, optics temperature) + MTF/PSF/pupil/throughput
plots. The **"Coating spectra — R/T/ε per element"** plot exists in the Throughput tab, but there is
**no editor to define those elements** — it can only render a train that was injected via YAML.

**The gap in one line:** optics is editable only in its single lumped-scalar mode (Mode 1 of 5); the
per-element R/T/ε/temperature train, Zernike/Zemax WFE, defocus, scatter, and stray-light — all
engine-supported — are unreachable.

| # | Missing capability | Class | Engine surface | Docs | Sev |
|---|--------------------|-------|----------------|------|-----|
| O-1 | **Per-element definition: map %R / %T / temperature / emissivity per surface** | **[C]** | `io/element_config.py::load_element_list()`, `OpticalElement` (kind, transfer_mode, T_K, R/T scalar-or-CSV, cavity); `optics.transmission_input_mode` = `key_elements`/`full_prescription` | 1.1, 7.2, 7.4, 2.5 | **P0** |
| O-2 | Transmission input-mode selector (scalar / spectral_file / telescope+filters / key_elements / full_prescription) | [E]+[C] | `optics.transmission_input_mode` enum | 1.1, 6.2 | P1 |
| O-3 | Self-emission via Kirchhoff ε=1−τ → `optics.scalar_emissivity`, with modeled DN offset shown pre-run | [E] | `optics.scalar_emissivity`, `optics.nearfield_enabled` | 7.2, 7.4 | P1 |
| O-4 | Cold-stop `nearfield_fraction` slider (0–1) + vendor-efficiency tooltip + guardrail | [E] | `optics.nearfield_fraction` (alias `cold_stop_efficiency`, Gap 12) | 7.4 | P1 |
| O-5 | **WFE input-mode selector (Scalar RMS / Zernike / OPD map) + reference wavelength** | [E]+[C] | `optics.wfe_mode` (`scalar_rms`/`zernike`/`field_dependent`), `wfe_reference_wavelength_um` | 5.1 | P1 |
| O-6 | **Zemax Zernike import** → Z4–Z15 table (coeff, variance %), RSS total | [C] | `io/zemax_zernike.py::load_zemax_zernike` (Gap 26) | 5.1 | P1 |
| O-7 | Zernike per-coefficient sliders (Z4–Z15) with real-time PSF; Zernike-vs-scalar-screen compare | [C] | `zernike.py`, `zernike_opd.py` | 5.1 | P2 |
| O-8 | ErrorBudget WFE allocation panel (allocation λ/14, live RSS, over/under, headroom) | **[A]** | `radiant.api.error_budget.ErrorBudget` (Gap 23/28, shipped) | 5.1 | P1 |
| O-9 | Pupil-preview widget (amplitude mask: obscuration + spider arms) before run | **[A]** | `result.plot.pupil_amplitude` / `pupil_phase` exist (Gap 89) — but pre-run preview needs a mask renderer | 1.5 | P1 |
| O-10 | Spider/strut width + angle inputs with live PSF-spike/EE/RER | [E] | `optics.spider_width_m`, `optics.spider_angle_deg` (not in current 8-field form) | 1.5 | P1 |
| O-11 | Direct PSF access + log-scale image (`imshow(log(psf))`) | [A] | `result.plot.psf` / `psf_pixel_grid` | 1.5, 5.3 | P2 |
| O-12 | **Mono vs poly PSF toggle + N selector (5/11/21)** + difference map + convergence-vs-N | [E] | `optics.psf_n_wavelengths` | 5.3 | P1 |
| O-13 | Per-wavelength PSF viewer (λ slider, Airy overlay); chromatic MTF overlay; chromaticism table | [C]/[X] | poly-PSF computed; per-λ PSF export is Gap 16 (partial) | 5.3 | P2 |
| O-14 | Defocus / focus-position sweep (MTF@Nyquist vs defocus) | [E] | `optics.defocus_um` (Gap 29) | 7.3 | P2 |
| O-15 | Surface-roughness / scatter (TIS) parameters | [E] | `optics.surface_roughness_nm`, `optics.scatter_halo_sigma_um` | 7.3 | P2 |
| O-16 | **Stray-light panel** (mode selector veiling-glare / absolute-irradiance / spectral_file; stray_e, SNR, NIIRS vs clean) + tolerance slider | [E]+[C] | `optics.stray.*` (input_mode, veiling_glare_fraction, absolute_irradiance_W_m2, mtf, halo, includes_thermal) | 5.5 | P1 |
| O-17 | Sensitivity sliders (f/#, pitch, obscuration, λ → Q/MTF/EE/Strehl) | [E]+sweep | params exist; needs sweep/slider surface | 5.1, 5.2 | P1 |
| O-18 | Sampling-regime annotation (detector- vs diffraction-limited) color band | [A] | derivable from Q in `result.metrics` | 1.2, 5.2 | P2 |
| O-19 | Optics distance-to-FPA input | [E] | `optics.optics_distance_to_fpa_m` | 7.x | P3 |
| O-20 | Arbitrary/measured pupil-mask image import; 2-D stray-light PSF (FRED/Zemax) ingestion + MTF | **[X]** | measured-pupil override / 2-D stray PSF not in engine (Gap 60) | 1.5, 5.5 | P3 |

**Physics/UX judgment notes.**
- O-1 is the owner's named optics gap. It is **[C]**, not [E]: the element train is an injected config
  object, so the GUI needs a small *element-list editor* (add element → kind, T_K, R/T scalar-or-CSV)
  that assembles the `optical_elements:` YAML block `load_element_list()` already consumes. This is the
  clearest example of the §12 config-object blocker.
- Rule 5 must be honored in that editor: **emissivity is derived, never an independent input** for a
  physical surface — the UI should show ε=1−R (mirror) / cavity-derived (refractive) as a *computed,
  read-only* field, and only allow a declared ε on a `LUMPED` pseudo-element (the one sanctioned
  exception, Gap 37).
- O-8/O-9/O-11 are class **[A]**: the API/plot surface already exists (ErrorBudget shipped; pupil
  accessors shipped under Gap 89) — the Optics view simply doesn't mount them yet.

---

## 6. Platform screen

**Exposed today:** jitter (isotropic + cross/along-track) and smear (ground velocity + focal-plane
length). Owner-ratified v1-minimal.

| # | Missing capability | Class | Engine surface | Docs | Sev |
|---|--------------------|-------|----------------|------|-----|
| PL-1 | Jitter-axes selector (isotropic/anisotropic) explicit control | [E] | `platform.jitter_axes` | 5.4 | P2 |
| PL-2 | **Jitter tolerance study**: jitter-RMS sweep with dual-unit (urad/pixels/IFOV-fraction), NIIRS-vs-jitter & MTF-vs-jitter with threshold drag-handles | [E]+sweep | params exist; needs sweep+dual-unit surface | 5.4 | P1 |
| PL-3 | Isolated jitter MTF vs system MTF; family-of-curves collapse | [A] | MTF-budget decomposition | 5.4 | P2 |
| PL-4 | RSS jitter budget calculator (per-source sliders, green/yellow/red) + jitter-source reference bars | **[A]** | `ErrorBudget` (Gap 23) | 5.4 | P1 |
| PL-5 | Auto-range detection (coarse sweep to find interesting range) | [X]/[A] | needs sweep surface | 5.4 | P2 |
| PL-6 | Orbit dashboard: period, orbital velocity, ground-track speed, orbits/day; auto ground-velocity + line period from orbital params | [E]/[A] | `geometry.circular_orbit`, `core.orbit`; smear MTF@Nyquist derived | 1.4, 1.2, 3.1 | P1 |
| PL-7 | Physics-note banner ("jitter affects MTF/RER not SNR") | [A] | text/UX | 5.4 | P3 |

**Note.** Platform attitude/pointing has no stage owner yet (ADR-0006 §4 / CU-122); the target RPY triad
ships from `source.target.*`. The v1-minimal framing is owner-ratified, so PL findings are mostly P1/P2
enhancements, not blocking — *except* that the sweep-dependent ones (PL-2, PL-5) inherit the §11.2 P0.

---

## 7. Spectral Integration screen

**Exposed today:** filter min/max edges + integration time. This *is* the whole engine model for this
stage (a top-hat bandpass) — so the stage-level surface is complete. The gaps here are analysis/plot
overlays, not inputs.

| # | Missing capability | Class | Engine surface | Docs | Sev |
|---|--------------------|-------|----------------|------|-----|
| SI-1 | Spectral-QE / emissivity import + overlay with cold-filter band shaded; band-averaged chips | [C] | `detector.qe_table_path`, `source.*.emissivity_path`, `io/qe_csv.py`, `io/aster_library.py` | 2.1, 1.3, 4.3 | P1 |
| SI-2 | ΔL(λ) spectral-contrast plot + sub-band (8–10 vs 10–12) table | [A]/[X] | in-band radiance frame exists; sub-band split absent | 4.3, 1.3 | P2 |
| SI-3 | Jacobian panel (∂L/∂ε, ∂L/∂T, dT/dε) + emissivity-retrieval sweep with ±NEDT band | [X]/sweep | not a native accessor | 6.5 | P2 |
| SI-4 | Band summary (Δλ/λ chromaticism, per-λ Q range) | [A] | derivable | 5.3 | P3 |
| SI-5 | Per-wavelength noise decomposition | **[X]** | **not in engine (Gap 92)** — noise is post-integration scalar (Rule 8) | (owner) | P3 |
| SI-6 | Curve-digitizer widget (vendor-PDF graph → CSV) | [X] | not in engine | 1.1 | P3 |

---

## 8. Detector screen

**Exposed today** (`detector_inputs_form.py`, 3 tabs): 6 scalars — QE, dark rate, pixel pitch x/y, fill
factor, temperature — + noise pie + pixel illustration + PSF grid.

**The gap in one line:** the detector is the engine's richest noise model (Arrhenius dark, 1/f, G-R,
Johnson, persistence, IPC, diffusion, FPN, QE(λ)/QE(T)) — the GUI exposes six of ~25 knobs.

| # | Missing capability | Class | Engine surface | Docs | Sev |
|---|--------------------|-------|----------------|------|-----|
| D-1 | **Spectral QE(λ) import** (CSV, header-unit auto-detect) + overlay + A/B vs scalar | [E]/[C] | `detector.qe_table_path`, `io/qe_csv.py` | 2.1, 1.1, 1.2 | P1 |
| D-2 | QE(T) temperature dependence inputs + co-varying temp sweep | [E] | `detector.qe_temperature_coeff_per_K`, `qe_temperature_ref_K` | 7.5 | P1 |
| D-3 | **Dark-current curve import** J_dark(T) (semilog, no-extrapolation guard) + Arrhenius fit + knee flag | [E]/[C] | `dark_rate_e_per_s`, `dark_reference_temperature_K`, `dark_activation_energy_eV`, `io/dark_current_csv.py` | 2.1, 7.5 | P1 |
| D-4 | **1/f noise configurator** (K, f_low/f_high band, frame-rate mapping, PSD log-log, full-band vs corner toggle, overestimate warning) | [E] | `detector.flicker_K`, `flicker_f_low_hz`, `flicker_f_high_hz` | 2.2 | P1 |
| D-5 | **IPC coupling** input + IPC→MTF toggle + gap-awareness banner | [E] | `detector.ipc_coupling` (Gap 1 wired) | 2.3 | P1 |
| D-6 | **Persistence panel** (residual & persistence-noise vs frame, frames-to-clear, ghost-in-LSB) | [E] | `detector.persistence_fraction`, `persistence_tau_s`, `prior_signal_e`; `persistence_sequence.py` | 2.4 | P1 |
| D-7 | Charge-diffusion length input (diffusion MTF) | [E] | `detector.charge_diffusion_length_m` | 2.3, 5.2 | P2 |
| D-8 | G-R & Johnson noise inputs | [E] | `detector.gr_factor`, `detector.r0a_ohm_cm2` | 2.1 | P2 |
| D-9 | FPN inputs (PRNU, DSNU) + noise-regime selector (imaging/detection) | [E] | `detector.prnu_pct`, `dsnu_e_rms`, `detector.noise_regime` | 2.3 | P2 |
| D-10 | ROIC glow input | [E] | `detector.glow_e_per_s` | 2.4 | P3 |
| D-11 | Cross-track pixel count (swath) | [E] | `detector.n_pixels_cross` | 3.1 | P3 |
| D-12 | **Sampling-config view** (per-pitch Q, oversampled/well/undersampled/ALIASED badges, Airy overlay, GSD calc) | [A] | Q in `result.metrics` | 5.2 | P1 |
| D-13 | Cooler-budget trade panel (crossover T, BLIP T, NEI, T_FPA slider live re-query) | [E]+sweep | dark/temp params + sweep | 2.1 | P1 |
| D-14 | Well-fill / integration-time trade heatmap + saturation contours + pre-run advisory | [E]+sweep | `readout.full_well_capacity_e` + sweep | 2.5, 1.4 | P1 |
| D-15 | Multi-detector import (tabular candidates → matched pitch sweep) | [C] | vendor-table import + sweep | 5.2 | P1 |
| D-16 | Detectivity converters (D*/NEP/NETD from chain noise) callable | [A]/[X] | verify accessor exists (`nep_from_netd`/`dstar_from_nep` referenced) | 6.1, 4.5 | P2 |
| D-17 | Datasheet-benchmark mode (auto-configure to reference conditions, residual PASS/FAIL) | [X] | not a native flow | 6.1 | P3 |
| D-18 | Non-standard dark-current unit import (fA/pixel, A/cm² → e⁻/s) | [C] | unit-aware import | 7.4, 7.5 | P2 |

**Physics/UX judgment note.** D-1 through D-6 are all class [E] scalars already in the schema — the
Detector *Inputs* tab shows 6 of them and hides the rest. The fastest, highest-value move on this screen
is simply *expanding the Inputs form to the full detector schema* (grouped: QE, dark, 1/f, G-R/Johnson,
FPN, persistence, IPC/diffusion), which unblocks Mike's entire persona (2.1–2.5) at near-zero physics
risk.

---

## 9. Readout screen

**Exposed today:** read noise, conversion gain, ADC bits, full-well. Owner-ratified v1-minimal.

| # | Missing capability | Class | Engine surface | Docs | Sev |
|---|--------------------|-------|----------------|------|-----|
| R-1 | **TDI configuration** (analog/digital selector, misalignment slider, N_tdi sweep, analog-vs-digital overlay) | [E] | `readout.n_tdi`, `readout.tdi_mode`, `readout.tdi_misalign_pixels`; `tdi_mtf.py` | 1.4 | P1 |
| R-2 | Read-noise slider (shot- vs read-limited regime transition) | [E] | `readout.read_noise_e_rms` (+sweep) | 1.4 | P2 |
| R-3 | Binning inputs (on/off-chip x/y) | [E] | `readout.binning_x/y_on/off-chip` | 1.4 | P2 |
| R-4 | Coadd inputs (N, mode sum/average/median) | [E] | `readout.n_coadds`, `readout.coadd_mode` | 2.2 | P2 |
| R-5 | kTC / CDS controls + suppression indicator | [E] | `readout.cds_enabled`, `read_noise_is_post_cds`, `node_capacitance_F` | 2.1 | P2 |
| R-6 | Electronics-blur (electronics MTF) input | [E] | `readout.electronics_sigma_um` (Gap 32) | 7.3 | P2 |
| R-7 | `well_status` / well-fill prominent saturation banner when not `unclipped` | [A] | stage output | 8.2, 7.1 | P1 |
| R-8 | Frame-rate selector/sweep (→ 1/f band, persistence) | [E]/[X] | frame-rate as input surface | 2.2, 2.4 | P2 |
| R-9 | Radiometric-calibration report (predicted-vs-measured DN, gain a·predicted+b fit, "Apply calibration" provenance) | [X] | not a native flow | 7.2 | P3 |
| R-10 | Gain-switching / HDR / dual-integration "Simulate this" cards | [X] | not in engine | 2.5 | P3 |

**Note.** R-1 (TDI) is the highest-value Readout item — the engine has a full analog/digital TDI model
with misalignment MTF, and Sarah's 1.4 pushbroom scenario is entirely about it, yet no control exists.
The v1-minimal framing (owner-ratified) explains the gap but 1.4 cannot be run in the GUI without it.

---

## 10. Performance screen

**Exposed today:** metric readout + system MTF + MTF budget plots. The `result.metrics` surface already
carries SNR, NEDT, NIIRS, GSD, RER, Strehl, Q, MTF@Nyquist, EE, FWHM (Gaps 3/4/5/8/13 all FIXED).

**The gap in one line:** the metrics *exist*; the Performance screen shows a flat readout but lacks the
decomposition, comparison, sensitivity, and detection-range views the analyst personas need.

| # | Missing capability | Class | Engine surface | Docs | Sev |
|---|--------------------|-------|----------------|------|-----|
| P-1 | Full metrics dashboard with contrast-SNR/SCNR, well-margin dB, dynamic-range dB, N/A handling for lab geometry | [A] | `result.metrics` (+ units/metadata, Gap 71) | many | P1 |
| P-2 | **MTF-budget decomposition** bar (optics, pixel, jitter, smear, IPC, diffusion, TDI) with toggleable components | [A] | `result.plot.mtf_budget` (Gap 19) | 6.3, 5.2, 7.3, 3.4 | P1 |
| P-3 | Folded/aliased MTF view (Q<1) | [A]/[X] | folded-MTF (Gap 14) — verify accessor | 5.2 | P2 |
| P-4 | Measured-vs-predicted MTF overlay (`compare_mtf`, unit-switchable axis, residual subplot) | [A]/[X] | measurement import (Gap 30 shipped?) | 7.3 | P1 |
| P-5 | **Detection-range** computation (bisection) + range bars + not-detectable/swath-edge states | [A]/[X] | `johnson_range`/`detection_range` helpers referenced | 4.1, 4.2, 4.3 | P1 |
| P-6 | SCNR (clutter-inclusive) as labeled detection metric distinct from SNR | [A] | `contrast_e`/SCNR from spectral_integration | 1.3, 4.1 | P1 |
| P-7 | GIQE-5 / NIIRS term decomposition bar + "what limits NIIRS" + what-if sliders | [A]/[X] | `giqe5_sensitivity` (Gap 20) | 3.2, 5.4 | P1 |
| P-8 | Johnson-criteria DRI ranges + cycles-vs-range plot | [X] | verify `johnson`/`N50` helpers | 4.2 | P2 |
| P-9 | NEDT reconciliation (predicted-vs-measured overlay, gap analysis, tornado sensitivity) | [X]/sweep | needs measurement import + sweep | 7.1 | P2 |
| P-10 | Dual-path (PSF-FFT vs MTF-product) consistency indicator / CU-058 banner | [A] | `consistency_check` runs every chain | 5.1, 7.3 | P1 |
| P-11 | Regime badge (extended/point/sub-pixel) + inline regime-warning suggestion (not traceback) | [A] | `stage_outputs['optics']['regime']` | 2.3, 4.1, 1.1 | P1 |
| P-12 | Feasibility / always-saturated / physically-impossible indicator | [A] | well_status + result-typed failures (ADR-B) | 2.5 | P2 |
| P-13 | ROC / P_d / P_fa / AUC panel | [X] | synthetic-scene/ROC not in engine | 6.4, 1.3 | P3 |
| P-14 | MRT/MRC-at-Nyquist detectability margin | [X] | not in engine | 3.5 | P3 |
| P-15 | Figure-of-merit optimizer (custom weighting + compliance filter) | [X] | not a native flow | 5.2 | P3 |

**Physics/UX judgment note.** Most P-row items are class **[A]** — the metric/plot/consistency surface
exists; the Performance screen just presents a flat readout. The high-value additions are the MTF-budget
decomposition (P-2), regime badge + non-traceback warning (P-11), and the dual-path consistency indicator
(P-10, Rule 4 is a first-class RADIANT invariant and users should see when it trips).

---

## 11. Cross-cutting surfaces

### 11.1 Scripting console — **present and strong**
The scripting window (`scripting_window.py`) ships a MATLAB-like console + workspace + script editor with
`sensor`/`result`/`plot`/`inspect_result` bound, history, figure pop-out, and a shared namespace with the
main GUI. This is the one cross-cutting surface that largely meets its requirement (every doc leans on it).
**Judgment:** because every disabled menu action below has a console equivalent, the console is currently
load-bearing as the *only* path to sweeps/comparison/export — which is exactly why the GUI-native surfaces
are P0: a persona GUI cannot require every user to script.

### 11.2 Sweeps — **P0, no GUI surface**
*Run Sweep…*, *Monte Carlo…*, *Batch Run…* are all disabled menu placeholders. Required (as a GUI surface,
not just a console call) by 1.2, 1.4, 1.5, 2.2, 2.5, 3.2, 5.1, 5.2, 5.4, 7.2, 7.4, 8.1, 8.2 — the single
most-requested cross-cutting capability. Needs: single-axis sweep, two-axis trade (contour + constraint
line), progress bar + ETA + abort-keeps-results, threshold/zero-crossing finder, live curve/heatmap.
Backend primitives partially exist (`Sensor.sweep`/`keep_results`, `BatchRunner`; verify) — the surface is
the gap. **[A]/[X]**, **P0**.

### 11.3 Plotting — **partial**
`result.plot.*` accessors exist and the console can plot inline. Missing as first-class GUI: contour+overlay
with named constraint lines, dual-axis, color-by-third-variable, draggable threshold lines, hover
tooltips/click-drill, reference-data (measured) overlay, plot-vs-altitude/range. Mostly [A] wiring + a chart
interaction layer. **P1.**

### 11.4 Comparison — **P0, no GUI surface**
Side-by-side multi-config comparison (evaluate N, tabulate metrics, best-per-metric highlight), band cards
(MWIR vs LWIR), compliance/PASS-FAIL matrix, traffic-light go/no-go, detection matrix/heatmap, with/without
single-source toggle. Required by 1.3, 1.5, 2.1, 2.3, 3.2, 3.3, 3.5, 4.1, 6.2, 6.3, 7.4. Backend primitive
absent for N-run orchestration/merge (gaps.md notes "GUI comparison table has no backend primitive").
**[X]+GUI**, **P0**.

### 11.5 Export — **P0, disabled**
*Export YAML*, *Export JSON Result* are disabled placeholders; CSV/Excel/PDF/PPT/PNG-SVG absent entirely.
Required by nearly every doc (Excel multi-sheet, PDF report, PPT briefing slides, CSV sweep data, per-chart
PNG/SVG, YAML snapshot, per-λ PSF FITS/NumPy). YAML-in-memory serialize is Gap 88 (OPEN). **[X]+GUI**, **P0.**

### 11.6 Data import / right rail — **P0, no surface**
Unit-aware spreadsheet/CSV import with column→dot-path mapping, unit auto-detect/conversion preview,
green/red validation, provenance (imported/default/derived) is required by ~20 docs (all of Mike/Lisa/Raj/
Karen batch work). The engine has *every loader* (`io/qe_csv.py`, `dark_current_csv.py`, `aster_library.py`,
`target_library.py`, `zemax_zernike.py`, `element_config.py`, tape7) and unit-aware `Sensor.set(...,unit=)`
(Gap 6) — but no GUI import surface exists. Right rail today = Pinned / Messages / Workspace only. **[C]+GUI**,
**P0.**

### 11.7 Menu scaffolding — disabled placeholders
For completeness, the following menu actions are present-but-`enabled=False`: File(New, Save, Save As,
Export YAML, Export JSON), Edit(Reset to Defaults), View(Theme, Font ±), Run(Evaluate, Sweep, Monte Carlo,
Batch), Tools(Schema Browser, Explain Parameter, Preferences), Help(Docs, Examples, About). Several back
capabilities that already exist in the engine/API (Schema Browser ← Gap 70 introspection API FIXED; Explain
Parameter ← `Sensor.parameter_def`; Reset to Defaults; Evaluate). These are low-risk [E]/[A] wire-ups.

### 11.8 Global UX conventions required across screens
- **Dual-unit / unit-labeled display everywhere** (ms/µs, m/ft, e⁻/ke⁻, urad/pixels/IFOV, waves/nm, km/mi/nm).
  The GUI display-unit store exists (per the memory that GUI shows values in the user's chosen unit); the docs
  additionally want *simultaneous* dual-unit echo in trade contexts. **P1.**
- **Gap-awareness banners / status chips** surfacing known limitations + workaround (e.g. IPC-not-wired,
  CU-066 tape7 fallback, CU-058 consistency warning). **P1.**
- **Derived-parameter confirmation panel** (GSD, IFOV, Q, Airy) — partly in geometry readout. **P2.**
- **Auto-recommendation / design-summary panel.** **P3** (verges on new analysis logic).

---

## 12. Structural finding — the config-object reach-ability blocker

Several P0/P1 items (O-1 element train, O-5/O-6 Zernike WFE, O-16 stray-light spectra, A-4 tape7, A-8
tabulated atmosphere, D-1/D-3 spectral curves, S-9/S-10 materials & libraries) share one root cause:

> These capabilities are **not** flat `ParameterDef`s. They are injected into the chain as pre-built
> **config objects** (`stage_outputs['optics_config']`, `['atmosphere_config']['model']`, element lists,
> filter specs, Zernike screens) or loaded from files by the IO layer *before* chain execution (Rule 6).

The current GUI forms are **`ParameterDef`-driven** — one `FieldRow` per dot-path — so they *structurally
cannot* reach any of this. Surfacing these needs a different widget class: a small **config-object editor**
(element-list table, curve-import card, model-config panel) that assembles the YAML section / config object
the existing loader consumes, then feeds it via the same `initial_stage_outputs=` path the API already uses.
This is the highest-leverage architectural decision for GUI v2 — it converts a dozen [C] items from
"impossible in the GUI" to "one shared editor pattern." **Recommend an ADR before implementing.**

---

## 13. Cross-references to the existing Gap Registry

The GUI-era gaps already filed corroborate this audit — several are the exact items above:

| Gap | Title | Status | This audit |
|-----|-------|--------|-----------|
| 6 | Unit-aware parameter input | FIXED | enables §11.6 import |
| 69 | Bundled libraries not selectable from config | **OPEN** | S-9 material dropdowns |
| 70 | Public parameter-schema introspection API | FIXED | enables Tools→Schema Browser (§11.7) |
| 80 | No multi-band / dual-band run concept | (see reg.) | §11.4 band comparison |
| 81 | MODTRAN sky terms not ingestable | (see reg.) | A-4 fidelity |
| 82 | No cloud/rain/fog | (see reg.) | A-14 **[X]** |
| 83 | No two-point geodetic geometry input | (see reg.) | Geometry map-pick |
| 84 | No time/orbital-ephemeris geometry | (see reg.) | PL-6 orbit dashboard |
| **85** | **No mission-type-driven parameter relevance** | (see reg.) | **S-5 scene-type selector (owner-requested)** |
| 86 | Spectral-radiance figure accessors | FIXED | A-5 before/after plots |
| 87 | `result.inspect()`/`explain()` accessors | OPEN | Variables/Noise tabs |
| 88 | In-memory config serialize | OPEN | §11.5 YAML export |
| 89 | Optics pupil diagnostics | OPEN→partial | O-9 pupil preview |
| 90 | Optics coating/element spectral figure | OPEN→partial | O-1 element editor |
| 91 | Pre-atmosphere source-emission frame | FIXED (`spectral_source_emission`) | A-5, Source view |
| 92 | Per-wavelength noise decomposition | OPEN | SI-5 **[X]** |

**Note on process (Rule 21/25).** This audit does **not** itself modify `gaps.md` or `Cleanup_Backlog.md`
(scope: produce the audit md only). Per Rule 28 the owner should disposition each finding as **CU'd**,
**Planned** (a GUI v2 plan under `docs/plans/`), or **Declined**. Findings S-14/15/16, A-14/15, O-20,
SI-5/6, P-13/14/15, R-9/10, D-17 are class **[X]** (engine gaps) and should be reconciled against existing
`gaps.md` entries rather than double-filed.

---

## 14. Recommended priority tiers (for owner triage)

**Tier 1 — unblock whole personas (do first).** All are engine-supported today.
1. Atmosphere input form: model selector + profile/aerosol/PWV + tape7 import (A-1..A-4). *Unblocks 1.1, 3.2, 6.2, 7.x.*
2. Source reflective/solar path + day/night (S-1, S-3) and scene-type selector (S-5). *Unblocks all VIS + owner ask.*
3. Expand Detector Inputs to full schema — spectral QE, dark curve, 1/f, IPC, persistence (D-1..D-6). *Unblocks Mike 2.1–2.5.*
4. GUI sweep surface (§11.2) + comparison surface (§11.4). *Unblocks Raj, Lisa, Tom, both interpolation demos.*
5. Import surface + export surface (§11.5, §11.6).

**Tier 2 — high-value, engine-supported.**
Optics element/coating editor (O-1, needs §12 ADR); WFE modes + Zemax import + ErrorBudget panel
(O-5/O-6/O-8); TDI config (R-1); before/after-atmosphere plots (A-5); plots-vs-altitude/range (A-6);
MTF-budget + regime badge + consistency indicator on Performance (P-2/P-10/P-11); menu wire-ups (§11.7).

**Tier 3 — refinements & deferred [X] gaps.**
2-D scene canvas, synthetic-scene/ROC, cloud/fog, libRadtran, measured-pupil/2-D stray PSF, calibration
report, HDR cards, MRT/MRC — reconcile against `gaps.md`; most warrant their own plan or a Declined line.

---

## 15. Method & limitations

- **Sources cross-referenced:** all 42 `gui_workflow.md` docs (personas 01–08); every per-stage
  `*_inputs_form.py` and `stage_views.py`; every stage `_schema.py` + atmosphere/optics loaders;
  `main_window.py` menu registry; `gaps.md` Gaps 1–92.
- **Class tags ([E]/[C]/[A]/[X])** were assigned from the engine survey; a handful marked "[A]/[X] —
  verify" (P-3 folded MTF, P-5/P-8 detection-range/Johnson helpers, D-16 detectivity converters, §11.2
  sweep primitives) need a quick confirmation of the exact public accessor name before a plan commits —
  flagged inline rather than asserted.
- **Not covered:** visual/aesthetic polish, theme correctness, accessibility, performance/latency of
  re-evaluation, and test coverage of existing widgets — this audit is scoped to *missing capabilities*,
  not quality of shipped ones.
- No code, schema, or tracking file was modified.
