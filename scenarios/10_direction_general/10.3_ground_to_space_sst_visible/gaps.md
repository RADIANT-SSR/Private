# Gaps — scenario 10.3 (ground-to-space SST, visible)

Twelve findings. Every one is reproducible by running
`scripts/run_ground_to_space_sst_visible.py`; the section that surfaces it is named.
Local IDs (G1…G12) are scenario-local labels only — the orchestrator mirrors them
into `docs/tracking/gaps.md` / `docs/tracking/Cleanup_Backlog.md` with real registry
numbers. **No RADIANT source file was modified by this scenario.**

---

## G1 — No reflective point-source door; `cos θ_s` clamp contradicts the GF-9 sunlit verdict

| Field | Value |
|---|---|
| **Found in** | Scenario 10.3, runner section 8 (GEO reflective door, twilight) |
| **Status** | WORKAROUND |
| **Severity** | High — blocks the headline use case of the scene class |
| **Description** | RADIANT's reflective target path (`T2Reflective`/`T3Mixed`) computes the direct-solar term as `ρ · τ_sun · E_TOA · max(cos θ_s, 0) / π` (`atmosphere/assembly.py::_cos_theta_s`). For θ_s > π/2 the clamp gives exactly zero. But ADR-0011 decision 10's shadow-height test (`atmosphere/solar_shadow.sunlit`) declares a 700 km / GEO object **sunlit** at θ_s = 102°, and the chain publishes `tau_sun = 1.0` (vacuum solar leg). The two subsystems disagree: GF-9 says lit, assembly says dark. Verified: the GEO reflective run at θ_s = 102° returns band-mean target radiance 1.36e-18 W/m²/sr/µm and SNR = 0.000, while `sunlit(3.5786e7, 102°) is True` and `tau_sun = 1.0000`. The clamp is right for a *horizontal ground facet*; it is wrong for a satellite, whose illuminated face is not the local horizontal. The physically meaningful variable is the **solar phase angle**, for which RADIANT has no input door. Consequently there is no reflective *point-source* door at all: shape + albedo cannot express a sunlit object over a dark site. |
| **Workaround** | Enter the object through `source.target.user_intensity_path` (T7IntensityAtSource) with a pre-computed signature I(λ) = ρ·A·E_sun(λ)·p(α)/π; `inputs/create_spreadsheet.py` does the reflective physics outside RADIANT. |
| **Impact** | Every reflective ground_to_space and air_to_space scene in the terminator window (i.e. the operational SST window). Also blocks any phase-angle photometry. |
| **Fix location** | `src/radiant/atmosphere/assembly.py::_cos_theta_s` + `_direct_solar_term`; a new `source.target.solar_phase_angle_rad` door and a reflective point-source resolver. |
| **Effort** | Medium (new parameter + resolver + descriptor branch); the clamp itself must stay for ground facets, so this is a new path, not an edit. |
| **Rerun after fix** | 10.3 (drop the pre-computed signature, enter ρ + A + α). |

## G2 — The GF-9 illumination verdict never reaches the signal through the intensity door

| Field | Value |
|---|---|
| **Found in** | Scenario 10.3, runner section 7 |
| **Status** | OPEN (documentation/UX) |
| **Severity** | Medium — silent wrong answer for an eclipsed object |
| **Description** | `T7IntensityAtSource` consumes I(λ) verbatim, so `tau_sun` (which carries the GF-9 shadow verdict, including the hard 0 for an eclipsed target) never multiplies the target term. Re-running the nominal at 30° solar depression — where `sunlit(7e5, 120°) is False` and the chain sets `tau_sun = 0` — returns the *same* signal, 34 961 e-. Nothing warns. |
| **Workaround** | The scenario gates the signature on the shadow test in the runner narrative and states the ownership explicitly. |
| **Impact** | Any point-source-by-intensity scene where the target can enter eclipse. |
| **Fix location** | Either apply `tau_sun` to the intensity path when the descriptor is flagged reflective, or (minimum) emit a `UserWarning` from `SourceStage`/`AtmosphereStage` when `tau_sun == 0` and the target is an intensity descriptor. |
| **Effort** | Small (warning) / Medium (semantics). |
| **Rerun after fix** | 10.3 section 7. |

## G3 — `_adjust_scene_los` strips the solar geometry for *reflective* intensity targets

| Field | Value |
|---|---|
| **Found in** | Scenario 10.3, runner section 8 (nominal background radiance) |
| **Status** | OPEN |
| **Severity** | High — deletes the dominant noise source of a visible measurement |
| **Description** | `source/_inferrer.py::_adjust_scene_los` keeps `theta_s`/`delta_phi` only for `T2Reflective` and `T3Mixed` (the CU-009 "a pure-thermal radiance has no solar leg" predicate). `T7IntensityAtSource` falls into the else-branch, so the atmosphere receives `theta_s = None` and builds a **pure-thermal** sky and path radiance — ~1e-18 W/m²/sr/µm at 0.4–0.9 µm. But an intensity descriptor is agnostic about what the intensity represents; a sunlit satellite signature is reflective. Measured: nominal at-aperture background = 1.2719e-18 W/m²/sr/µm at θ_s = 102°, and *identical* at θ_s = 80°. The daytime sky is therefore absent from every intensity-door scene. |
| **Workaround** | None available from the config surface. The scenario reports the missing pedestal and states that its SNR is target-shot-noise-plus-detector only. |
| **Impact** | Every VIS/NIR point-source-by-intensity scene; SNR is optimistic by whatever the sky pedestal would have contributed. |
| **Fix location** | `src/radiant/source/_inferrer.py::_adjust_scene_los` — the predicate needs to distinguish "no solar leg because the target self-emits" from "no solar leg modelled because the user pre-integrated it", and keep θ_s for the atmosphere's own background/path terms in the latter case. |
| **Effort** | Small–Medium (predicate change + goldens for T1 scenes must stay byte-identical). |
| **Rerun after fix** | 10.3 section 8; 1.6 (MWIR point-source SDA) as a zero-drift check. |

## G4 — VIS/NIR provisional sky warning is structurally unreachable in `ground_to_space`, and the observer-leg scatter underflows

| Field | Value |
|---|---|
| **Found in** | Scenario 10.3, runner section 8 (GEO reflective door, daylight) |
| **Status** | **PARTIALLY RESOLVED 2026-07-29** (commit `5c0f3dd`, CU-254/CU-260) — half (a) is closed, half (b) is open. The sky is now rooted at the **sensor** and spans the whole LOS, so the `h_tgt ≥ h_atm_top` early return is gone and the provisional VIS/NIR `UserWarning` fires for this scene class; `sky_radiance.warn_if_scattered_sky_provisional` is public so the near-horizon branch applies the same gate. The `_sky_source_radiance` symbol named below is now `_sky_radiance_at_aperture`. Half (b), the species split at the arithmetic mean altitude, is unchanged and stays open as CU-260 — note also that the sky pedestal was **not** in fact absent: the `SkyBackground` arm added `L_path_full`, so the assembled background moved by only −2.6e-7 relative on this config (the **Impact** row below overstates it). |
| **Severity** | High |
| **Description** | Two coupled defects. **(a)** The `SkyBackground` source term is the LOS *continuation past the target*. When the target is above `h_atm_top` — i.e. for the whole ground_to_space class — `uplooking_quantities::_sky_source_radiance` returns zeros early and never calls `sky_radiance_along_los`, which is the only place the ADR-0011 decision-10 VIS/NIR provisional `UserWarning` is raised. The warning can therefore never fire for an SST scene, even though the analyst is looking through the daytime atmosphere. **(b)** The sky the telescope actually looks *through* is the observer leg, whose single-scatter source (`segment_simple::_single_scatter_terms`) takes its species split at the segment's **arithmetic mean altitude**. For a site→object segment that is h_tgt/2: 350 km for the LEO case (densities ~1e-20, ratio still resolves) and 17 893 km for the GEO case, where every `exp(-h/H)` underflows to exactly 0, the single-scattering albedo evaluates to 0, and the scattered term vanishes. Measured: GEO daylight run at θ_s = 60° gives observer-leg L_path = 1.3637e-18 W/m²/sr/µm. The comparison probe at a 20 km target gives 21.572 W/m²/sr/µm. |
| **Workaround** | The scenario demonstrates the warning on a `ground_to_air` probe (20 km target, extended scene) and prints it verbatim; the ground_to_space sky pedestal is reported as missing. |
| **Impact** | Sky background and its shot noise are absent from every ground_to_space / air_to_space scene. SNR is optimistic, and the user is never told. |
| **Fix location** | `src/radiant/atmosphere/segment_simple.py::_single_scatter_terms` (evaluate the species split at a density-weighted altitude, or clip the segment to `h_atm_top` before taking the mean); `src/radiant/atmosphere/uplooking_quantities.py::_sky_source_radiance` (raise the provisional caveat on the observer leg, not only on the continuation). |
| **Effort** | Medium. |
| **Rerun after fix** | 10.3 section 8. |

## G5 — The >80° air-mass correction is keyed to the segment's geometric Δh, not the atmospheric thickness

| Field | Value |
|---|---|
| **Found in** | Scenario 10.3, runner section 10b (air-mass handover probe) |
| **Status** | OPEN |
| **Severity** | Medium — non-monotonic transmittance; the scenario avoids the band |
| **Description** | `atmosphere/protocol.py::AtmosphericGeometry.slant_path_length_m` switches at `SPHERICAL_SWITCH_RAD` (80°) from `Δh/cos ζ` to `R_E·[√(cos²ζ + 2x + x²) − cos ζ]` with `x = Δh/R_E`. That root form is the standard spherical air-mass approximation for a *thin atmospheric slab*. For an up-looking observer segment the spec runs site → target, so Δh = 699 km (x = 0.110) rather than the ~10 km of atmosphere, and the correction is applied to a thickness three orders of magnitude too large. Measured: τ(0.55 µm) at ζ_low = 79.9° is 0.01373 (optical depth 4.288) and at 80.1° is 0.09796 (optical depth 2.323) — the optical depth **drops** as the path lengthens. Transmittance is non-monotonic in zenith angle above 80°, and the spherical branch under-estimates the column. |
| **Workaround** | Every reported number in scenario 10.3 is at ζ_low ≤ 75°, inside the flat-Earth branch where sec ζ is correct to < 0.5 %. |
| **Impact** | Any up-looking or down-looking path with an exo-atmospheric endpoint evaluated above 80° zenith. |
| **Fix location** | `src/radiant/atmosphere/protocol.py::AtmosphericGeometry.slant_path_length_m` (use the atmospheric column thickness, or clip the segment at `h_atm_top` before computing the air mass), or `segment_simple::column_segment_optical_depth` (clip the spec). |
| **Effort** | Small–Medium; touches a widely used helper, so goldens must be checked. |
| **Rerun after fix** | 10.3 section 10b; the down-looking goldens as a zero-drift check. |

## G6 — Point-source angular-extent guard compares against the optics-only PSF

| Field | Value |
|---|---|
| **Found in** | Scenario 10.3, target-selection dead end (reproduced by setting `geometry.target.projected_area_m2 = 1.0` with `source.target.albedo` at 700 km) |
| **Status** | WORKAROUND |
| **Severity** | Medium |
| **Description** | `optics/stage.py::_validate_psf_regime_consistency` raises when `√A_t/d > 0.1 · PSF_FWHM`, with `PSF_FWHM` taken from the **`OpticsStage`** `EffectivePSF` — i.e. before turbulence, which enters at `PlatformStage`. For a ground-based seeing-limited system the operative PSF is 4–15× wider than the optics-only one, so a physically unresolved object is rejected. Reproduced: a 1 m² object at 739 km gives √A/d = 1.351e-6 rad and the stage raises at 1.305× PSF_FWHM (1.035e-6 rad) — while the actual seeing disc is 3.2e-6 rad, making the object unresolved by 2.4×. |
| **Workaround** | The scenario uses the intensity door, whose fictitious reference area skips the guard entirely; the reflective-door comparison uses a GEO object where the guard passes. |
| **Impact** | Ground-based reflective/point-source scenes of realistic LEO objects cannot use the shape door. |
| **Fix location** | `src/radiant/optics/stage.py::_validate_psf_regime_consistency` — the guard needs the degraded PSF, which means either deferring the check to `PlatformStage` or admitting an r₀-derived widening term. |
| **Effort** | Medium (stage-ordering question). |
| **Rerun after fix** | 10.3 with a shape+albedo LEO target. |

## G7 — Wholly-vacuum up-looking path + `SkyBackground` raises

| Field | Value |
|---|---|
| **Found in** | Scenario 10.3, cross-check (a), true-vacuum run |
| **Status** | OPEN |
| **Severity** | Medium — blocks a documented capability (the LEO→GEO quick win) for non-extended scenes |
| **Description** | `topology.evaluate_path_topology` returns `TopologyProducts(quantities=_vacuum_quantities(...))` with `sky_radiance_at_aperture = None` when both endpoints are at or above `h_atm_top`. But `source/_inferrer.py::_select_los_termination_background` still selects `SkyBackground()` for the space termination, and `assembly._validated_sky_radiance` refuses to default the missing radiance to zero (correctly, under Rule 17). The result is `ParameterBoundsError: assembly: SkyBackground requires the whole-LOS sky radiance, but sky_radiance_at_aperture is None`. Reproduced by raising `geometry.sensor_altitude_m` to 100 000 m in the nominal config. |
| **Workaround** | The vacuum limiting-case identity is evaluated analytically (τ → 1 in the closed-form integral) rather than by a second chain run. |
| **Impact** | Any up-looking scene with both endpoints above `h_atm_top` and a scene type that needs a background (point_source / sub_pixel) — including the ADR-0011 "LEO→GEO quick win". |
| **Fix location** | `src/radiant/atmosphere/topology.py` — the vacuum branch should publish a zero sky-radiance array (the exact vacuum identity) rather than `None`. |
| **Effort** | Small. |
| **Rerun after fix** | 10.3 cross-check (a); add a LEO→GEO point-source integration test. |

## G8 — HV-5/7 Cn² profile is evaluated against MSL altitude, not above-ground-level

| Field | Value |
|---|---|
| **Found in** | Scenario 10.3, runner section 9 |
| **Status** | OPEN |
| **Severity** | Medium — r₀ optimistic by ~2× for any non-sea-level site |
| **Description** | `atmosphere/cn2_hufnagel_valley.py` evaluates the HV-5/7 profile — whose ground term has a 100 m scale height — against MSL altitude, and `r0_path` integrates from `h_low = h_sensor` in MSL. A site at 900 m MSL therefore starts the integral above its own boundary layer and loses it entirely. Measured: chain r₀ = 19.820 cm at 0.650 µm, i.e. 14.5 cm at 0.5 µm (0.70″ seeing) where a real 0.9 km high-desert site runs 1.0–1.5″. The sea-level integral of the same profile gives 4.961 cm at 0.5 µm, matching the HV-5/7 "≈ 5 cm" definition. |
| **Workaround** | The scenario states the caveat and quotes the sea-level anchor beside the chain value. A user wanting realistic seeing can enter `atmosphere.r0_m` directly (the direct door wins, with the CU-093 agreement check). |
| **Impact** | Every turbulence result for a sensor above ~200 m MSL. |
| **Fix location** | `src/radiant/atmosphere/cn2_hufnagel_valley.py` — the ground term should be referenced to the site altitude (an AGL offset parameter), or the docstring must state the MSL convention and the schema must expose the offset. |
| **Effort** | Small (parameter + offset) plus a doc update (Rule 20). |
| **Rerun after fix** | 10.3 section 9; `tests/integration/test_phase3_conditioning.py` uses a sea-level site and is unaffected. |

## G9 — Rayleigh coefficient: a dimensionless vertical optical depth used as a km⁻¹ extinction

| Field | Value |
|---|---|
| **Found in** | Scenario 10.3, cross-check (b) |
| **Status** | OPEN |
| **Severity** | **High — results-affecting for every VIS/NIR scene through the simple model** |
| **Description** | `atmosphere/simple.py` defines `RAYLEIGH_COEFF_KM = 0.0088`, `RAYLEIGH_EXPONENT = 4.09` and computes `σ_mol(λ, h) = 0.0088 · λ_µm^(−4.09) · exp(−h/8 km)` documented as `[1/km at sea level]` (citing Bucholtz 1995); the column optical depth is then `σ_mol × col_length_km`. But `0.0088 λ^(−4.09)` is the standard fit to the **total vertical Rayleigh optical depth** (dimensionless — Hansen & Travis 1974; Bucholtz 1995 tabulates both quantities). The true sea-level Rayleigh *volume extinction* at 550 nm is 0.0116 km⁻¹, ≈ 8.7× smaller than the 0.10148 the expression yields. Multiplying by the ~8 km molecular column therefore inflates the Rayleigh optical depth by ≈ H_mol/1 km ≈ 8×. Measured at the 900 m site, zenith: RADIANT τ(0.55 µm) = 0.4714 → **0.816 mag/airmass**, against a published 0.12–0.20 mag/airmass for good sites. Substituting the correct reading (0.0907 optical depths instead of 0.7255) gives τ = 0.8894 → **0.127 mag/airmass, inside the published band** — which is what confirms the diagnosis. |
| **Workaround** | None. The scenario reports RADIANT's numbers as-is, states that τ (and hence SNR) is pessimistic by ≈ 1.8× at the nominal geometry, and notes that trends are unaffected. |
| **Impact** | Every VIS/NIR (roughly λ < 1.5 µm) scene using `atmosphere.model = "simple"`, up-looking or down-looking — reciprocity check (c) shows both directions share it. MWIR/LWIR is unaffected in practice (Rayleigh OD at 4 µm is ~2.5e-4 either way), which is why the CU-161 MODTRAN calibration, anchored over 3–14 µm, never saw it. |
| **Fix location** | `src/radiant/atmosphere/simple.py` (`RAYLEIGH_COEFF_KM`, `_rayleigh_extinction_km`, and the `column_segment_optical_depth` / `build_state` callers) + `docs/architecture/RADIANT_Atmosphere.md` §3.1 line 162 in Rule-20 lock-step + a `CHANGELOG.md` **Results-affecting:** entry. |
| **Effort** | Small code change, **large** golden-baseline impact: every VIS/NIR golden moves. Needs the §5.3 golden-review protocol. |
| **Rerun after fix** | 10.3 cross-check (b); scenarios 1.2, 5.2, 9.1 (Sentinel-2 MSI) and every VIS golden. |

## G10 — Piecewise-constant gas-region table produces τ discontinuities at region edges

| Field | Value |
|---|---|
| **Found in** | Scenario 10.3, `outputs/signature_and_column_transmittance.png` |
| **Status** | OPEN (low) |
| **Severity** | Low — cosmetic in this scenario, real for narrow-band work |
| **Description** | `simple.py::_CALIBRATED_GAS_REGIONS` is a step table; `k_h2o` jumps 0.0025 → 0.1245 at the 0.70 µm boundary, producing a visible step in τ(λ) from 0.728 to 0.617 across one grid point. Any band edge placed near a region boundary, or any narrow band straddling one, inherits the step. |
| **Workaround** | None needed here (the band is broad and the step is ~11 % of τ at one wavelength). |
| **Impact** | Narrow-band VIS/SWIR work near 0.45, 0.70, 1.30, 1.50, 1.75, 2.05, 2.40, 3.10, 3.50, 5.00, 7.50, 8.00, 10.00, 12.00 µm. |
| **Fix location** | `src/radiant/atmosphere/simple.py::_region_params` — interpolate the region coefficients rather than step them, or document the convention. |
| **Effort** | Small code, medium golden impact. |
| **Rerun after fix** | Any scenario with a band edge near a region boundary. |

## G11 — MODTRAN anchor for the ground-to-space class is deferred (owner-run batch 2)

| Field | Value |
|---|---|
| **Found in** | Scenario 10.3, cross-check (e) |
| **Status** | BLOCKED — awaiting owner |
| **Severity** | Medium — the class ships without its trusted-tool anchor |
| **Description** | ADR-0011 decision 10 assigns the SST full-column up-looking MODTRAN ladder to **batch 2**, which has not been run. There is therefore no MODTRAN comparison for τ(λ), L_path, or the sky background in this scene class. **This scenario reports no MODTRAN comparison and fabricates none.** The substitutes used instead are a closed-form vacuum-limit identity, a published-extinction anchor, an apparent-magnitude anchor, and the HV-5/7 literature r₀ — all recorded in `walkthrough.md` §10. |
| **Workaround** | The four anchors above. Note that the published-extinction anchor already *failed* and root-caused G9; a MODTRAN run would have found the same thing. |
| **Impact** | The `ground_to_space` transmittance and sky-radiance products remain provisional. |
| **Fix location** | `docs/plans/modtran_run_matrix.csv` batch 2; then `atmosphere/loaders.py` family wiring for an up-looking full-column K-block. |
| **Effort** | Owner-run batch + medium wiring. |
| **Rerun after fix** | 10.3 cross-check (e) becomes a real anchor. |

## G12 — Up-looking topology provenance is dropped before it reaches `ChainResult`

| Field | Value |
|---|---|
| **Found in** | Scenario 10.3, while looking for the GF-9 verdict in `result.stage_outputs` |
| **Status** | OPEN (low) |
| **Severity** | Low — inspectability (Rule 16), not a wrong number |
| **Description** | `uplooking_quantities.UplookingProducts` carries a `provenance` dict with the GF-9 illumination note (`"target at … is inside the Earth's shadow …"` / `"… above the modelled column and sunlit … (tau_sun = 1)"`), the observer-leg description, and the sky-continuation note. `topology.TopologyProducts` has no provenance field, so `evaluate_path_topology` discards it and `AtmosphereStage` never publishes it. The information exists only in an `INFO` log record. A user cannot inspect *why* `tau_sun` took its value. |
| **Workaround** | The scenario calls `atmosphere.solar_shadow.sunlit` / `shadow_height_m` directly to reproduce the verdict. |
| **Impact** | Inspectability of the direction-aware atmosphere; `result.inspect()` cannot explain the solar leg. |
| **Fix location** | `src/radiant/atmosphere/topology.py` (`TopologyProducts` gains `provenance`) + `atmosphere/stage.py` (publish it as `stage_outputs["atmosphere"]["path_topology_provenance"]`) + `RADIANT_Atmosphere.md` in Rule-20 lock-step. |
| **Effort** | Small. |
| **Rerun after fix** | 10.3 section 7 can read the note from the chain instead of recomputing it. |
