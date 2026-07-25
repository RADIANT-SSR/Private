# Parameter Reference

*Auto-generated from the parameter registry. Do not edit by hand --- re-run `python scripts/gen_param_reference.py` to update.*

**Total parameters: 173**

## source

| Parameter | Type | Default | Input Unit | Bounds | Description |
|-----------|------|---------|------------|--------|-------------|
| `source.background.emissivity` | float | 0.95 | --- | (0.0, 1.0) | Background surface emissivity for sub-pixel regime. |
| `source.background.emissivity_path` | str |  | --- | --- | Two-column CSV (wavelength_um, emissivity) giving a measured background emissivity spectrum ε_g(λ) for the sub-pixel/point-source GroundBackground (CU-008). Loaded by the API layer before chain execution (Rule 6) and resampled onto the chain grid. Takes precedence over source.background.material. |
| `source.background.material` | str | grey | --- | --- | Named spectral-library material for the sub-pixel/point-source GroundBackground emissivity ε_g(λ) (CU-008). 'grey' (default) uses the scalar source.background.emissivity as a flat spectrum — the back-compat path. Any other name is resolved against radiant.data.SpectralLibrary (vegetation_green, snow, soil_dry, asphalt, ...) by the API layer before chain execution (Rule 6); unknown names are rejected with the legal vocabulary. source.background.emissivity_path overrides this when set. |
| `source.background.temperature` | float | 290.0 | K | (0.0, 5000.0) | Background surface temperature [K] for sub-pixel regime. |
| `source.contrast_reference.emissivity` | float | 0.95 | --- | (0.0, 1.0) | Emissivity of the extended contrast-reference scene (ADR-0005). Only used when source.contrast_reference.temperature > 0. |
| `source.contrast_reference.temperature` | float | 0.0 | K | (0.0, 5000.0) | Temperature [K] of the reference (background) scene in the neighbouring extended pixel, used only for the extended contrast_snr differential (ADR-0005). 0 = no contrast reference (default). Never enters the noise budget. |
| `source.lab_test_mode` | str |  | --- | --- | Positive dark/lit assertion for the ground_test / lab_test sub-cases (Gap 40). 'dark' declares a no-external-illumination configuration (no lamp, no solar — thermal self-emission only, the D-lab dark-cal sub-mode) and is VALIDATED: a user-set source.target.reflectance contradicts it and is rejected. 'lit' positively asserts an externally illuminated lab scene (recorded for readability; unvalidated until a lamp surface exists). Empty string = unasserted (back-compat). |
| `source.no_atmosphere_subcase` | str |  | --- | --- | Matrix §3.3 sub-case selector for target_location='no_atmosphere'. Empty string = not set (paired with target_location != 'no_atmosphere'). Allowed explicit values: 'space', 'ground_test', 'lab_test'. |
| `source.regime_override` | str | auto | --- | --- | Force regime classification. 'auto' = use detection rule. 'extended', 'point_source', 'sub_pixel' = force that regime. |
| `source.scene_type` | str | auto | --- | --- | Matrix §3.2 scene-type axis. 'auto' = infer from fill_fraction / geometry (default). 'extended' = fills the pixel; 'sub_pixel' = partial fill; 'point_source' = angular size ≪ IFOV. |
| `source.target.albedo` | float | 0.0 | --- | (0.0, 1.0) | User-facing alias for source.target.reflectance with identical semantics (Lambertian ρ, 0–1).  Accepted for scenarios where 'albedo' is the natural label; the inferrer rejects pairing with source.target.reflectance (pick one). |
| `source.target.albedo_path` | str |  | --- | --- | Alias of source.target.reflectance_path with identical CSV format.  Rejected when paired with the reflectance_path surface. |
| `source.target.brightness_temperature_K` | float | 0.0 | K | (0.0, 10000.0) | Scalar brightness temperature T_B [K] — the equivalent-blackbody temperature that produces the same spectral radiance as the source. When user-set (provenance != DEFAULT), routes through the S11 converter to a T1Thermal descriptor with ε≡1.  Mutually exclusive with source.target.brightness_temperature_path. |
| `source.target.brightness_temperature_path` | str |  | --- | --- | Path to a 2-column CSV (wavelength_um, T_B_K) carrying a wavelength-dependent brightness temperature.  When set, routes through the S11 converter; λ-varying T_B emits T6TabulatedAtSource with L_source = B(λ, T_B(λ)) per ADR-0003. Mutually exclusive with source.target.brightness_temperature_K. |
| `source.target.emissivity` | float | 0.95 | --- | (0.0, 1.0) | Scalar target emissivity used when no spectral emissivity table is supplied. Graybody approximation: ε(λ) = const. |
| `source.target.emissivity_path` | str |  | --- | --- | Path to a 2-column CSV (wavelength_um, emissivity) carrying a λ-dependent emissivity ε(λ) for a thermal target (Gap 47). When set, the inferrer builds the thermal descriptor with L_t(λ) = ε(λ)·B(λ, source.target.temperature) instead of a grey ε. Mutually exclusive with the scalar source.target.emissivity and with every reflective / radiance / brightness-temperature surface. |
| `source.target.fill_fraction` | float | 1.0 | --- | (0.0, 1.0) | Target fill fraction within the pixel. 1.0 = extended scene (default). Values in (0, 1) activate the sub-pixel regime. |
| `source.target.is_hot_target` | bool | False | --- | --- | Hot-target opt-out for MWIR routing.  Per matrix §3.2 the legacy scalar-ε surface defaults MWIR scenes to T3Mixed (Kirchhoff emit+reflect) because ambient MWIR scenes are reflective-relevant.  Set true for ρ ≈ 0 hot-target scenes (engine plumes, missile signatures, calibration sources) where self-emission dominates and the legacy T1Thermal pure-emit treatment is the correct physics.  Ignored for non-MWIR wavelength grids. |
| `source.target.point_intensity_area_m2` | float | 0.0 | m^2 | (0.0, 1000000000000.0) | Projected emitting area [m²] of a blackbody point source — the A in I(λ) = ε·A·B(λ,T). Distinct from geometry.target.projected_area_m2 (which sizes a resolved/sub-pixel target); this one only scales the point-source intensity. |
| `source.target.point_intensity_band_W_per_sr` | float | 0.0 | W/sr | (0.0, 1000000000000.0) | Scalar band-integrated radiant intensity [W/sr] of a point source — the in-band integral ∫ I(λ) dλ over the filter band [spectral_integration.filter_min_um, filter_max_um]. Modeled as a spectrally flat intensity I(λ) = value/(filter_max−filter_min) inside the band, zero outside, so the band integral recovers the specified value. The simplest point-source input (star-tracker / SDA when only a band flux is known); requires scene_type='point_source'. Mutually exclusive with the blackbody point-intensity params and the CSV intensity path. |
| `source.target.point_intensity_emissivity` | float | 1.0 | --- | (0.0, 1.0) | Scalar emissivity ε ∈ [0, 1] of a blackbody point source (the ε in I(λ) = ε·A·B(λ,T)). Independent material property (Rule 5 applies to optical elements, not scene targets). |
| `source.target.point_intensity_temperature_K` | float | 0.0 | K | (0.0, 5000.0) | Point-source emitter temperature [K]. With point_intensity_area_m2 (and point_intensity_emissivity) defines a blackbody radiant intensity I(λ) = ε·A·B(λ,T) [W/sr/µm] for an unresolved target (SDA thermal object, S10 convenience — no surface radiance × area needed). Requires scene_type='point_source'. |
| `source.target.radiance_temperature_K` | float | 0.0 | K | (0.0, 10000.0) | Band-averaged radiance temperature T_R [K] — the scalar equivalent-blackbody temperature that matches the in-band integrated radiance of the target over [λ_lo, λ_hi].  Must be paired with source.target.radiance_temperature_band_lo_um and source.target.radiance_temperature_band_hi_um when user-set.  Mutually exclusive with S11 brightness_temperature parameters. |
| `source.target.radiance_temperature_band_hi_um` | float | 0.0 | um | (0.0, 1000.0) | Upper band edge [µm] for the S12 radiance-temperature specification. Required when source.target.radiance_temperature_K is user-set; must satisfy λ_lo < λ_hi. |
| `source.target.radiance_temperature_band_lo_um` | float | 0.0 | um | (0.0, 1000.0) | Lower band edge [µm] for the S12 radiance-temperature specification. Required when source.target.radiance_temperature_K is user-set; must satisfy λ_lo < λ_hi. |
| `source.target.reflectance` | float | 0.0 | --- | (0.0, 1.0) | Scalar target reflectance ρ [dimensionless, 0–1] — the fraction of incident radiance that is reflected from the target.  When user-set (provenance != DEFAULT), routes through the Step 3.2 inferrer to a T2Reflective descriptor with ρ(λ) ≡ this scalar. Mutually exclusive with source.target.albedo, source.target.reflectance_path, and the legacy (ε, T) surface. |
| `source.target.reflectance_path` | str |  | --- | --- | Path to a 2-column CSV (wavelength_um, rho) carrying a λ-dependent reflectance ρ(λ).  When set, routes through the Step 3.2 inferrer to a T2Reflective descriptor (S5/S6).  Mutually exclusive with the scalar reflectance / albedo surfaces. |
| `source.target.temperature` | float | 300.0 | K | (0.0, 5000.0) | Target surface kinetic temperature (blackbody / graybody). |
| `source.target.user_intensity_path` | str |  | --- | --- | Path to a 2-column CSV (wavelength_um, I_t_source [W/sr/µm]) carrying a user-supplied spectral intensity at the target plane, for unresolved (point-source) targets.  When set, routes through the Phase 5 inferrer to a T7IntensityAtSource descriptor (S10 — ADR-0004; no physical model applied, the user owns the physics).  Mutually exclusive with every other target spec form ((ε, T), reflectance/albedo, brightness_temperature, radiance_temperature, user_radiance).  Requires scene_type='point_source'. |
| `source.target.user_radiance_path` | str |  | --- | --- | Path to a 2-column CSV (wavelength_um, L_t_source [W/m²/sr/µm]) carrying a user-supplied spectral radiance at the target plane.  When set, routes through the Phase 4 inferrer to a T6TabulatedAtSource descriptor (S8 — no physical model applied; the user owns the physics).  Mutually exclusive with every other target spec form ((ε, T), reflectance/albedo, brightness_temperature, radiance_temperature). |
| `source.target_location` | str | auto | --- | --- | Matrix §3.2 target-location axis. 'auto' = infer from atmosphere.model (default). Allowed explicit values: 'at_aperture', 'terrestrial', 'airborne', 'no_atmosphere'. |

## atmosphere

| Parameter | Type | Default | Input Unit | Bounds | Description |
|-----------|------|---------|------------|--------|-------------|
| `atmosphere.aerosol_type` | str | rural | --- | --- | Aerosol type label. Selects an Ångström exponent and single-scatter albedo: rural (α=1.3), urban (α=1.5), maritime (α=0.7). |
| `atmosphere.interpolated_data_dir` | str |  | --- | --- | Directory containing pre-computed atmosphere runs (NPZ files) at discrete geometry points for the interpolated model. Empty (the default) uses the bundled atmosphere library family matching atmosphere.interpolation_axes: 'path_zenith_rad' → us_standard_zenith_fan (LOS zenith 0–60°), 'sensor_altitude_m,target_altitude_m' → midlat_summer_ladders (35 km–GEO × 0–29 km). Other axes combinations require an explicit directory. |
| `atmosphere.interpolation_axes` | str | path_zenith_rad | --- | --- | Comma-separated list of geometry fields to interpolate over, e.g. 'path_zenith_rad' or 'path_zenith_rad,sensor_altitude_m'. |
| `atmosphere.interpolation_method` | str | linear | --- | --- | Interpolation method: 'linear' or 'nearest'. |
| `atmosphere.model` | str | simple | --- | --- | Atmosphere model selector. 'simple' uses a closed-form Beer-Lambert; 'exo' uses a vacuum; 'tabulated' loads from files; 'modtran' wraps the MODTRAN binary; 'interpolated' interpolates between pre-computed runs at discrete geometry points. |
| `atmosphere.modtran.aerosol_model` | str | rural | --- | --- | Aerosol model for MODTRAN (maps to IHAZE card). |
| `atmosphere.modtran.allow_fallback` | bool | False | --- | --- | If True and MODTRAN binary is unavailable, fall back to SimpleAtmosphere with translated parameters. |
| `atmosphere.modtran.atmosphere_profile` | str | us_standard | --- | --- | Standard atmosphere profile for MODTRAN (maps to MODEL card). Same enum as atmosphere.standard_atmosphere. |
| `atmosphere.modtran.binary_path` | str | /usr/local/bin/modtran | --- | --- | Path to the MODTRAN executable. |
| `atmosphere.modtran.cache_dir` | str | ~/.radiant/modtran_cache | --- | --- | Directory for caching MODTRAN tape7 results. Keyed by SHA-256 hash of the rendered tape5 deck. |
| `atmosphere.modtran.flux_path` | str |  | --- | --- | Optional MODTRAN spectral flux CSV (a Block E irradiance run's *_flux.csv sidecar) supplying the downwelling sky irradiance for the tape7-import path (CU-157, Gap 38). Requires atmosphere.modtran.tape7_path. When set, the ground-level DOWN column (thermal emission + scattered solar) feeds the sky-reflection terms: E_sky_scattered from the reflective-solar band and E_sky_thermal from the thermal band — superseding the Gap 81 zero for flux-equipped imports. Unset, a standard IEMSCT=2 tape7 carries no downwelling column, so both terms stay zero (Gap 81). |
| `atmosphere.modtran.h2o_scale` | float | 1.0 | --- | (0.01, 10.0) | Water vapor column scaling factor for MODTRAN. |
| `atmosphere.modtran.o3_scale` | float | 1.0 | --- | (0.01, 10.0) | Ozone column scaling factor for MODTRAN. |
| `atmosphere.modtran.spectral_resolution_cm1` | float | 1.0 | cm-1 | (0.1, 100.0) | Spectral resolution [cm-1] for the MODTRAN computation. |
| `atmosphere.modtran.tape7_path` | str |  | --- | --- | Path to a MODTRAN tape7 output file produced elsewhere. When set (with atmosphere.model='modtran'), the atmospheric state is built from this file — parsed before chain execution (Rule 6) — and the MODTRAN binary, cache, and fallback are never consulted. Unset (empty) leaves the binary/cache/fallback behavior unchanged. Like tabulated files, an imported tape7 is geometry-agnostic: the arrays are served as-is for any query geometry. Airborne targets (h_tgt > 0) additionally require the target→sensor leg via atmosphere.modtran.tape7_up_path; with only this single (ground→sensor) file they are rejected. |
| `atmosphere.modtran.tape7_sun_path` | str |  | --- | --- | Optional sun-leg tape7 file for the two-leg split (CU-011, file flavor). Requires atmosphere.modtran.tape7_path. When set, tau_sun (the sun→target down-leg transmittance) comes from this file's TOT TRANS column — a MODTRAN run along the solar-zenith slant path — instead of aliasing the up-leg transmittance, and the single-tau collapse warning is not emitted. Unset, tau_sun aliases tau_up with a UserWarning, as before. |
| `atmosphere.modtran.tape7_up_path` | str |  | --- | --- | Optional target→sensor up-leg tape7 file for airborne targets (Gap 94, file flavor). Requires atmosphere.modtran.tape7_path (which then supplies the ground→sensor full column the background branch needs). When set, tau_up and L_path_up (the target→sensor partial column) come from this file — a MODTRAN run with H2 = the target altitude — enabling h_tgt > 0 on the file-import path. The user owns geometry consistency: nothing in the file records H2, so this file must actually be the run matching the scenario's target altitude and LOS zenith. Unset, airborne targets are rejected on the file-import path. |
| `atmosphere.precipitable_water_cm` | float | 1.4 | cm | (0.0, 10.0) | Total column precipitable water in centimetres of liquid-equivalent water vapour. Drives the 5-band water-vapor extinction fit. |
| `atmosphere.r0_m` | float | 0.0 | m | (0.0, 10.0) | Fried coherence diameter r₀ [m] at the operating wavelength. Controls long-exposure Kolmogorov turbulence MTF. Set to 0 to disable turbulence effects. |
| `atmosphere.standard_atmosphere` | str | us_standard | --- | --- | Standard atmosphere profile selector. Used by the simple model for the path-mean temperature lookup and aerosol/H2O scale heights. |
| `atmosphere.tabulated_downwelling_file` | str |  | --- | --- | Path to CSV file containing tabulated downwelling atmospheric emission [W/m^2/sr/um]. Optional; defaults to zeros if not provided. |
| `atmosphere.tabulated_path_radiance_file` | str |  | --- | --- | Path to CSV or NPZ file containing tabulated path radiance [W/m^2/sr/um]. Required when atmosphere.model='tabulated'. |
| `atmosphere.tabulated_transmittance_file` | str |  | --- | --- | Path to CSV or NPZ file containing tabulated atmospheric transmittance. CSV: two columns (wavelength_um, value). NPZ: key 'transmittance' with matching 'wavelength_um'. Required when atmosphere.model='tabulated'. |
| `atmosphere.visibility_km` | float | 23.0 | km | (0.1, 500.0) | Meteorological visibility at 550 nm in kilometres. Drives the Koschmieder aerosol extinction σ_aer(550 nm) = 3.912 / V_km. |

## geometry

| Parameter | Type | Default | Input Unit | Bounds | Description |
|-----------|------|---------|------------|--------|-------------|
| `geometry.circular_orbit` | bool | False | --- | --- | Declare the platform a circular orbit at geometry.sensor_altitude_m — mode V6 entry. When true, the ground-track speed (and orbital period) are derived from the altitude via core.orbit; do not also set geometry.ground_speed_m_s unless it agrees. False = generic platform (airborne or static); ground speed is taken from geometry.ground_speed_m_s as before. |
| `geometry.day_of_year` | int | 80 | --- | (1, 366) | Day of year, 1–366 — mode S3 entry (site + time solar geometry). |
| `geometry.elevation_angle_rad` | float | 1.5707963 | rad | (0.0088, 1.5708) | Sensor elevation above the target's local horizon [rad] — mode V4 entry (grazing-angle framing). path zenith = pi/2 − elevation. Unused unless explicitly set. |
| `geometry.ground_range_m` | float | 0.0 | m | (0.0, 20000000.0) | Surface arc distance from the sensor nadir point to the target [m] — mode V3 entry. The target-side path zenith is derived via the spherical viewing triangle. Unused unless explicitly set. |
| `geometry.ground_speed_m_s` | float | 0.0 | m/s | (0.0, 50000.0) | Ground-track speed [m/s]. For LEO at 600 km: ~6900 m/s. |
| `geometry.local_solar_time_h` | float | 12.0 | h | (0.0, 24.0) | Local solar time at the target [hours, 0–24; 12.0 = solar noon] — mode S3 entry. Mutually exclusive with geometry.ltan_h. |
| `geometry.ltan_h` | float | 12.0 | h | (0.0, 24.0) | Local time of ascending node [hours] for a sun-synchronous orbit — mode S3 entry; the local solar time is derived via core.solar_geometry.local_solar_time_from_ltan. Mutually exclusive with geometry.local_solar_time_h. |
| `geometry.path_zenith_rad` | float | 0.0 | rad | (0.0, 1.562) | Line-of-sight zenith angle at the TARGET (theta_o) [rad]. 0 = sensor at the target's zenith (nadir view). This is the target-side angle consumed by the atmospheric path; the sensor-side off-nadir angle is geometry.sensor_off_nadir_rad. |
| `geometry.sensor_altitude_m` | float | **required** | m | (0.0, 100000000.0) | Sensor altitude above mean sea level [m]. Also the altitude the no_atmosphere 'space' sub-case uses for the Earth-limb intercept check (formerly the separate platform.h_sensor stop-gap — folded as a deprecated alias per CU-090/ADR-0006). |
| `geometry.sensor_off_nadir_rad` | float | 0.0 | rad | (0.0, 1.5707) | Sensor off-nadir look angle eta [rad] — mode V2 entry. The target-side path zenith is derived via the spherical-Earth sine rule (core.los_geometry.theta_o_from_eta). Unused unless explicitly set; do not also set geometry.path_zenith_rad unless the two agree. |
| `geometry.site_latitude_rad` | float | 0.0 | rad | (-1.5708, 1.5708) | Target geodetic latitude [rad], north positive — mode S3 entry (site + time solar geometry). Combined with geometry.day_of_year and geometry.local_solar_time_h (or geometry.ltan_h) to derive the solar zenith angle. Unused unless an S3 parameter is explicitly set. |
| `geometry.solar_azimuth_rad` | float | 0.0 | rad | (-6.2832, 6.2832) | Sun-to-sensor relative azimuth [rad]. |
| `geometry.solar_elevation_rad` | float | 1.0707963 | rad | (0.0, 1.5708) | Sun elevation above the target's local horizon [rad] — mode S2 entry. solar zenith = pi/2 − elevation. Unused unless explicitly set. |
| `geometry.solar_illumination` | str | day | --- | --- | Day/night solar toggle (Gap 59). 'day' (default) illuminates reflective and mixed (T2/T3) targets with the sun at geometry.solar_zenith_rad — the historical behavior, in which the 0.5 rad zenith default meant every T2/T3 scene carried a daytime sun. 'night' removes the solar terms entirely (theta_s = None: no direct-solar reflection, no single-scatter solar sky) while thermal self-emission and reflected THERMAL downwelling remain — the physically correct nighttime mixed scene. Pure-thermal targets (T1) never carry a solar term either way. |
| `geometry.solar_zenith_rad` | float | 0.5 | rad | (0.0, 1.5707) | Solar zenith angle [rad]. |
| `geometry.target.projected_area_m2` | float | 0.0 | m2 | (0.0, 1000000000000.0) | Projected area of target facing the observer [m²]. 0.0 = not specified (extended-scene default). |
| `geometry.target.shape` | str | none | --- | --- | Geometric primitive for sub-pixel / point-source projected-area computation. 'none' = not specified (back-compat: use geometry.target.projected_area_m2).  Explicit values select a concrete shape; dimensional parameters are read from the geometry.target.shape_* scalars per the matrix §3 catalog. |
| `geometry.target.shape_base_radius_m` | float | 0.0 | m | (0.0, 1000000.0) | Base-circle radius [m] for the cone shape.  Separate from geometry.target.shape_radius_m because the cone class names the parameter base_radius_m (see shapes/cone.py).  Ignored for non-cone shapes. |
| `geometry.target.shape_height_m` | float | 0.0 | m | (0.0, 1000000.0) | Height [m] for shapes with a body-Z extent (box height, cone apex-to-base height).  Ignored for sphere, cylinder, flat_plate. |
| `geometry.target.shape_length_m` | float | 0.0 | m | (0.0, 1000000.0) | Length [m] for shapes with a length axis (cylinder axial extent, flat_plate body-X extent, box body-X extent).  Ignored for sphere and cone. |
| `geometry.target.shape_pitch_rad` | float | 0.0 | rad | (-6.283185307179586, 6.283185307179586) | Target body pitch [rad] about scene +Y (ZYX Euler, Rule 3). |
| `geometry.target.shape_radius_m` | float | 0.0 | m | (0.0, 1000000.0) | Radius [m] for shapes with a single radius parameter (sphere, cylinder).  Must be > 0 when the selected shape requires it; validation is enforced by the Step 1.2 shape factory, not here.  Ignored for shapes that do not take a radius (flat_plate, box). |
| `geometry.target.shape_roll_rad` | float | 0.0 | rad | (-6.283185307179586, 6.283185307179586) | Target body roll [rad] about scene +X (ZYX Euler, Rule 3). |
| `geometry.target.shape_width_m` | float | 0.0 | m | (0.0, 1000000.0) | Width [m] for rectangular shapes (flat_plate body-Y extent, box body-Y extent).  Ignored for sphere, cylinder, cone. |
| `geometry.target.shape_yaw_rad` | float | 0.0 | rad | (-6.283185307179586, 6.283185307179586) | Target body yaw [rad] about scene +Z (ZYX Euler, Rule 3).  Applied to the selected TargetShape's ``orientation_rad`` tuple in Step 1.2. |
| `geometry.target_altitude_m` | float | 0.0 | m | (0.0, 100000000.0) | Target altitude above mean sea level [m]. |
| `geometry.target_range_m` | float | 0.0 | m | (0.0, 1000000000000.0) | Observer-to-target slant range [m]. 0.0 = not specified (extended-scene default). |

## optics

| Parameter | Type | Default | Input Unit | Bounds | Description |
|-----------|------|---------|------------|--------|-------------|
| `optics.aperture_diameter_m` | float | **required** | m | (0.0001, 20.0) | Clear entrance-pupil diameter of the primary [m]. |
| `optics.defocus_um` | float | 0.0 | um | (-500.0, 500.0) | Linear defocus: displacement of the detector plane from best focus [µm]. Positive = behind focus, negative = in front. Both produce identical blur (absolute value used). Zero = no defocus. |
| `optics.f_number` | float | **required** | --- | (0.3, 200.0) | Dimensionless f/# = focal_length_m / aperture_diameter_m. Part of the {D, f, f/#} consistency group; supply any two and the third is derived. |
| `optics.field_position_x` | float | 0.0 | deg | (-10.0, 10.0) | Normalized cross-track field coordinate for field-dependent WFE evaluation. 0.0 = on-axis. Maps to field_x_deg via the field table. |
| `optics.field_position_y` | float | 0.0 | deg | (-10.0, 10.0) | Normalized along-track field coordinate for field-dependent WFE evaluation. 0.0 = on-axis. Maps to field_y_deg via the field table. |
| `optics.focal_length_m` | float | **required** | m | (0.0001, 100.0) | Effective focal length of the telescope [m]. |
| `optics.n_spiders` | int | 0 | --- | (0, 12) | Number of secondary-support spider arms (radial struts). Default 0 (no struts). A 4-arm spider produces the familiar four-point diffraction spike. See RADIANT_Optics.md §3.3. |
| `optics.nearfield_enabled` | int | 1 | --- | (0, 1) | Enable nearfield (warm-optics) emission calculation. Set to 0 to disable (int: 1=True, 0=False). |
| `optics.nearfield_fraction` | float | 1.0 | --- | (0.0, 1.0) | Nearfield fraction: fraction of the FPA hemisphere filled by warm (nearfield-emitting) elements. 0 = perfect cold stop (no warm-optics emission reaches the FPA); 1 = no cold stop (uncooled instrument). NOTE this is INVERTED from the vendor 'cold stop efficiency' convention, where 100% efficient means complete blocking: nearfield_fraction = 1 - vendor_efficiency. Formerly named optics.cold_stop_efficiency (deprecated alias still accepted, Gap 12). |
| `optics.obscuration_ratio` | float | 0.0 | --- | (0.0, 0.99) | Central obscuration ratio ``D_secondary / D_primary``. Defaults to 0 (unobscured). Must satisfy 0 ≤ ε < 1. |
| `optics.optics_distance_to_fpa_m` | float | 0.0 | m | (0.0, 100.0) | Default distance from the optical train to the FPA [m]. Used as the distance_to_fpa_m for synthesized lumped elements. A value of 0.0 means 'use focal_length_m'. |
| `optics.optics_temperature_K` | float | 290.0 | K | (1.0, 1000.0) | Default physical temperature of the optical train [K]. Used for synthesized lumped elements in Modes 1-4. |
| `optics.psf_n_wavelengths` | int | 1 | --- | (1, 101) | Number of wavelengths for polychromatic PSF computation. 1 = monochromatic at band center (default). Values > 1 compute a photon-flux-weighted average of monochromatic PSFs across the spectral band. |
| `optics.scalar_emissivity` | float | 0.0 | --- | (0.0, 1.0) | Declared effective emissivity of the lumped optical train in scalar transmission mode [0, 1]. Zero (default) keeps the refractive-lump assumption (no warm-optics nearfield emission). Set nonzero for warm reflective trains — e.g. eps ≈ 1 - tau for an all-mirror train. Permitted only because the scalar lump is not a physical surface; Rule 5 (Kirchhoff-derived emissivity) still binds real elements. Requires eps + tau <= 1. Ignored in non-scalar transmission modes. |
| `optics.scatter_halo_sigma_um` | float | 100.0 | um | (0.1, 10000.0) | Focal-plane sigma of the Gaussian scatter halo [µm] used by the TIS model. Sets where the scattered fraction lands; tune to a measured halo when available. Only meaningful when optics.surface_roughness_nm > 0. |
| `optics.spider_angle_deg` | float | 0.0 | deg | (0.0, 360.0) | Orientation of the first spider arm about the optical axis [deg]; remaining arms equally spaced. Default 0 (first arm along +x). |
| `optics.spider_width_m` | float | 0.0 | m | (0.0, 1.0) | Width of each spider arm [m]. Converted to a fraction of the pupil diameter for the mask; also subtracted from the radiometric clear area (RADIANT_Optics.md §3.3). Default 0. Active only when n_spiders > 0. |
| `optics.stray.absolute_irradiance_W_m2` | float | 0.0 | W/m^2 | (0.0, 1000000.0) | Absolute in-band stray irradiance at the FPA [W/m^2]. Distributed flat across the wavelength grid. |
| `optics.stray.halo_sigma_um` | float | 50.0 | um | (0.1, 1000.0) | Gaussian half-width of the veiling-glare halo on the focal plane [µm] (Gap 60). Must be small enough to fit the PSF grid for the kernel and analytic MTF term to stay exact Fourier pairs (the kernel is truncated at the grid edge). |
| `optics.stray.includes_thermal` | int | 0 | --- | (0, 1) | If 1, the stray light measurement already includes warm-optics scatter; nearfield is suppressed to avoid double-counting. (int: 1=True, 0=False). |
| `optics.stray.input_mode` | str | veiling_glare | --- | --- | Stray light input mode: veiling_glare, absolute_irradiance, or spectral_file (curve injected via stage_outputs['optics_config']['stray_light_spectral']). pst_file is not offered: PST-based stray light needs a scene radiance distribution RADIANT v1 does not model (Gap 68 un-advertised the always-raising mode). |
| `optics.stray.veiling_glare_fraction` | float | 0.0 | --- | (0.0, 1.0) | Veiling glare fraction: fraction of in-FOV scene irradiance that becomes stray light [0, 1]. |
| `optics.stray.veiling_glare_mtf` | int | 0 | --- | (0, 1) | Enable the SPATIAL veiling-glare model (Gap 60): the veiling-glare fraction is re-imaged as a Gaussian halo, entering the PSF path as a kernel (1−vgf)·δ + vgf·G(σ_halo) and the MTF product path as its exact Fourier pair (1−vgf) + vgf·exp(−2π²σ²f²) — the low-frequency contrast-modulation loss the radiometric pedestal cannot express. 0 (default) = pedestal-only (historical behavior); 1 = halo model active when veiling_glare_fraction > 0. (int: 1=True, 0=False). |
| `optics.surface_roughness_nm` | float | 0.0 | nm | (0.0, 10000.0) | Effective RMS surface micro-roughness of the optical train [nm] for the TIS scatter model: TIS = 1 - exp(-(4πσ/λ)²) at band center. Zero (default) = no scatter. Smooth-surface limit — a warning fires when TIS > 0.3. Scattered energy lands in a Gaussian halo of width optics.scatter_halo_sigma_um (Rule 4: kernel on the PSF path + analytic MTF term, exact Fourier pair). |
| `optics.transmission_input_mode` | str | scalar | --- | --- | Which of the five transmission input modes to use: scalar, spectral_file, telescope_plus_filters, key_elements, full_prescription. Non-scalar modes read their curves/elements from pre-chain injections under stage_outputs['optics_config'] (transmission_spectral; telescope_transmission + filter_specs; key_elements + residual_transmission; element_list) — e.g. via Sensor.evaluate(extra_stage_outputs=...). |
| `optics.transmission_scalar` | float | 0.7 | --- | (0.0, 1.0) | Flat broadband optical throughput ``τ_opt`` (Mode 1 of RADIANT_Optics.md §5.1). Dimensionless in [0, 1]. |
| `optics.wfe_mode` | str | scalar_rms | --- | --- | Wavefront error input mode: scalar_rms (parameter-driven), or zernike / field_dependent (WavefrontError object injected via stage_outputs['optics_config']['wavefront_error']). opd_map is not offered: OPD maps have no pupil-phase representation in v1 (Gap 68 un-advertised the always-raising mode). |
| `optics.wfe_reference_wavelength_um` | float | 0.633 | um | (0.1, 30.0) | Reference wavelength at which the WFE is specified [um]. HeNe 0.633 um is the standard interferometry wavelength. |
| `optics.wfe_rms_waves` | float | 0.0 | waves | (0.0, 2.0) | RMS wavefront error in waves at the reference wavelength (scalar_rms mode). |
| `optics.zernike_file` | str |  | --- | --- | Path to a Zemax 'Zernike Standard Coefficients' text export. When set, the API layer loads it pre-chain (Rule 6) and injects the resulting ZERNIKE-mode WavefrontError via stage_outputs['optics_config']['wavefront_error'], which supersedes wfe_mode/wfe_rms_waves. The report's own reference wavelength is honored; optics.wfe_reference_wavelength_um is the fallback when the export has no Wavelength header. Empty = disabled (scalar/parameter-driven WFE). |

## detector

| Parameter | Type | Default | Input Unit | Bounds | Description |
|-----------|------|---------|------------|--------|-------------|
| `detector.charge_diffusion_length_m` | float | 0.0 | m | (0.0, 0.001) | RMS charge diffusion length [m]. Zero disables diffusion MTF. |
| `detector.clutter_sigma` | float | 0.0 | --- | (0.0, 1.0) | Scene clutter coefficient (fractional). Zero disables. |
| `detector.dark_activation_energy_eV` | float | 0.0 | eV | (0.0, 5.0) | Arrhenius activation energy for dark-rate temperature scaling. Zero disables scaling. |
| `detector.dark_rate_e_per_s` | float | 100.0 | 1/s | (0.0, 1000000000.0) | Dark current generation rate per pixel [e-/s]. |
| `detector.dark_reference_temperature_K` | float | 77.0 | K | (1.0, 500.0) | Temperature at which dark_rate_e_per_s is specified [K]. |
| `detector.detector_temperature_K` | float | 77.0 | K | (1.0, 500.0) | Detector operating temperature [K]. |
| `detector.dsnu_e_rms` | float | 0.0 | --- | (0.0, 1000000.0) | Dark-signal non-uniformity [e- RMS]. Zero disables. |
| `detector.fill_factor` | float | 1.0 | --- | (0.0, 1.0) | Photosensitive fraction of the pixel cell. |
| `detector.flicker_K` | float | 0.0 | --- | (0.0, 1000000000000.0) | 1/f flicker noise coefficient [e-²]. Zero disables. |
| `detector.flicker_f_high_hz` | float | 1000000.0 | Hz | (0.001, 1000000000.0) | Upper frequency bound for 1/f integration [Hz]. |
| `detector.flicker_f_low_hz` | float | 0.01 | Hz | (1e-06, 1000000.0) | Lower frequency bound for 1/f integration [Hz]. |
| `detector.glow_e_per_s` | float | 0.0 | 1/s | (0.0, 1000000.0) | Detector/ROIC glow rate [e-/s/pixel]. Zero disables. |
| `detector.gr_factor` | float | 0.0 | --- | (0.0, 10.0) | G-R noise factor (0 = disabled, 1 = classic HgCdTe). |
| `detector.ipc_coupling` | float | 0.0 | --- | (0.0, 0.25) | Inter-pixel capacitance coupling fraction α [0, 0.25). |
| `detector.n_pixels_cross` | int | 0 | --- | (0, 1000000) | Number of detector pixels in the cross-track direction. |
| `detector.noise_regime` | str | imaging | --- | --- | Noise regime: 'imaging' (temporal only, FPN calibrated out) or 'detection' (temporal + spatial). |
| `detector.persistence_fraction` | float | 0.0 | --- | (0.0, 1.0) | Fraction of prior-frame signal that persists. Zero disables. |
| `detector.persistence_tau_s` | float | 1.0 | s | (1e-06, 1000.0) | Persistence time constant [s]. |
| `detector.pixel_pitch_x_um` | float | **required** | um | (0.1, 1000.0) | Pixel pitch along the cross-track (x) axis. |
| `detector.pixel_pitch_y_um` | float | **required** | um | (0.1, 1000.0) | Pixel pitch along the along-track (y) axis. Required — there is no 'defaults to x pitch' fallback; set it explicitly (equal to pixel_pitch_x_um for square pixels). |
| `detector.prior_signal_e` | float | 0.0 | --- | (0.0, 1000000000.0) | Signal electrons from prior frame (for persistence). Zero disables. |
| `detector.prnu_pct` | float | 0.0 | --- | (0.0, 100.0) | Photo-response non-uniformity [%]. Zero disables. |
| `detector.qe_material` | str |  | --- | --- | Named bundled detector QE curve (Gap 69): a material in the bundled detector library (e.g. 'insb', 'hgcdte_mwir', 'silicon' — the API rejects unknown names with the legal vocabulary). Resolved pre-chain by the API layer (Rule 6) onto the wavelength grid, QE = 0 past the data span. Precedence: qe_table_path (explicit file) > qe_material (library) > qe_value (scalar). Empty = disabled. |
| `detector.qe_table_path` | str |  | --- | --- | Path to a wavelength-vs-QE CSV. When set, RadiantSession loads it (io.qe_csv) onto the wavelength grid and applies it spectrally, superseding the scalar qe_value; past-cutoff QE is zero (Gap 44). |
| `detector.qe_temperature_coeff_per_K` | float | 0.0 | 1/K | (-0.1, 0.1) | Linear QE temperature coefficient [1/K]. QE(T) = QE_base · (1 + coeff·(detector_temperature_K − qe_temperature_ref_K)), applied to the scalar qe_value or the qe_table_path curve. Default 0 (temperature-independent QE). Gap 48. |
| `detector.qe_temperature_ref_K` | float | 300.0 | K | (1.0, 1000.0) | Reference temperature [K] at which the QE (qe_value / qe_table_path) was characterised. Only used when qe_temperature_coeff_per_K ≠ 0. |
| `detector.qe_value` | float | **required** | --- | (0.0, 1.0) | Wavelength-independent scalar quantum efficiency. |
| `detector.r0a_ohm_cm2` | float | 0.0 | ohm_cm2 | (0.0, 1000000000000.0) | Detector R₀A product [Ω·cm²]. Zero disables Johnson noise. |

## spectral_integration

| Parameter | Type | Default | Input Unit | Bounds | Description |
|-----------|------|---------|------------|--------|-------------|
| `spectral_integration.filter_max_um` | float | **required** | um | (0.1, 30.0) | Long-wavelength edge of the filter bandpass [µm]. |
| `spectral_integration.filter_min_um` | float | **required** | um | (0.1, 30.0) | Short-wavelength edge of the filter bandpass [µm]. |
| `spectral_integration.integration_time_s` | float | **required** | s | (1e-09, 100.0) | Detector integration time [s]. |

## readout

| Parameter | Type | Default | Input Unit | Bounds | Description |
|-----------|------|---------|------------|--------|-------------|
| `readout.adc_bits` | int | 16 | --- | (4, 32) | ADC bit depth. |
| `readout.binning_x_offchip` | int | 1 | --- | (1, 64) | Off-chip binning factor along x. 1 = no binning. |
| `readout.binning_x_onchip` | int | 1 | --- | (1, 64) | On-chip binning factor along x. 1 = no binning. |
| `readout.binning_y_offchip` | int | 1 | --- | (1, 64) | Off-chip binning factor along y. 1 = no binning. |
| `readout.binning_y_onchip` | int | 1 | --- | (1, 64) | On-chip binning factor along y. 1 = no binning. |
| `readout.cds_enabled` | int | 1 | --- | --- | Correlated double sampling enabled (1=yes, 0=no). |
| `readout.coadd_mode` | str | sum | --- | --- | Coadd combination mode: 'sum', 'average', or 'median'. |
| `readout.electronics_sigma_um` | float | 0.0 | um | (0.0, 100.0) | Electronics MTF: equivalent Gaussian blur sigma on the focal plane [µm] from finite amplifier bandwidth at the pixel clock rate. Blurs the readout (cross-scan, x) axis only. Zero (default) = ideal electronics, no blur. Enters both the EffectivePSF (kernel) and the MTF product (analytic term) per Rule 4. |
| `readout.frame_period_s` | float | 0.0 | s | (0.0, 1000000.0) | Frame period [s]: the time between frame starts, stored independently of the integration time (spectral_integration.integration_time_s) per RADIANT_Conventions.md §4. Frame rate = 1/frame_period and duty cycle = t_int/frame_period are derived by radiant.readout.frame_timing and published in stage_outputs['readout']. Default 0.0 means 'unset': the frame period defaults to the integration time (frame rate = 1/t_int, duty cycle = 1.0) with a logged warning. A duty cycle > 1 (integration longer than the frame period) is rejected. |
| `readout.full_well_capacity_e` | float | 100000.0 | --- | (100.0, 100000000.0) | Full well capacity per pixel [e-]. |
| `readout.gain_e_per_dn` | float | 1.0 | --- | (0.001, 1000000.0) | System conversion gain: electrons per digital number (LSB). |
| `readout.n_coadds` | int | 1 | --- | (1, 10000) | Number of coadded frames. 1 = no coadd. |
| `readout.n_tdi` | int | 1 | --- | (1, 1000) | Number of TDI stages. 1 = no TDI. |
| `readout.node_capacitance_F` | float | 0.0 | F | (0.0, 1e-09) | Sense-node capacitance [F]. Zero disables kTC noise. |
| `readout.read_noise_e_rms` | float | 5.0 | --- | (0.0, 10000.0) | Per-frame read noise delivered to the signal path [e- RMS]. |
| `readout.tdi_misalign_pixels` | float | 0.0 | --- | (0.0, 10.0) | Cross-scan TDI misalignment in pixel units. Zero = perfect alignment. |
| `readout.tdi_mode` | str | analog | --- | --- | TDI readout mode: 'analog' (single readout after charge accumulation) or 'digital' (each stage read independently, summed digitally). |

## Consistency Groups

See `optics.f_number` = `optics.focal_length_m / optics.aperture_diameter_m`.
