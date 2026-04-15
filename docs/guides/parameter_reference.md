# Parameter Reference

*Auto-generated from the parameter registry. Do not edit by hand --- re-run `python scripts/gen_param_reference.py` to update.*

**Total parameters: 91**

## source

| Parameter | Type | Default | Input Unit | Bounds | Description |
|-----------|------|---------|------------|--------|-------------|
| `source.background.emissivity` | float | 0.95 | --- | (0.0, 1.0) | Background surface emissivity for sub-pixel regime. |
| `source.background.temperature` | float | 290.0 | K | (0.0, 5000.0) | Background surface temperature [K] for sub-pixel regime. |
| `source.regime_override` | str | auto | --- | --- | Force regime classification. 'auto' = use detection rule. 'extended', 'point_source', 'sub_pixel' = force that regime. |
| `source.target.emissivity` | float | 0.95 | --- | (0.0, 1.0) | Scalar target emissivity used when no spectral emissivity table is supplied. Graybody approximation: ε(λ) = const. |
| `source.target.fill_fraction` | float | 1.0 | --- | (0.0, 1.0) | Target fill fraction within the pixel. 1.0 = extended scene (default). Values in (0, 1) activate the sub-pixel regime. |
| `source.target.projected_area_m2` | float | 0.0 | m2 | (0.0, 1000000000000.0) | Projected area of target facing the observer [m²]. 0.0 = not specified (extended-scene default). |
| `source.target.range_m` | float | 0.0 | m | (0.0, 1000000000000.0) | Observer-to-target slant range [m]. 0.0 = not specified (extended-scene default). |
| `source.target.temperature` | float | 300.0 | K | (0.0, 5000.0) | Target surface kinetic temperature (blackbody / graybody). |

## atmosphere

| Parameter | Type | Default | Input Unit | Bounds | Description |
|-----------|------|---------|------------|--------|-------------|
| `atmosphere.aerosol_type` | str | rural | --- | --- | Aerosol type label. Selects an Ångström exponent and single-scatter albedo: rural (α=1.3), urban (α=1.5), maritime (α=0.7). |
| `atmosphere.interpolated_data_dir` | str |  | --- | --- | Directory containing pre-computed atmosphere runs (NPZ files) at discrete geometry points for the interpolated model. Required when atmosphere.model='interpolated'. |
| `atmosphere.interpolation_axes` | str | path_zenith_rad | --- | --- | Comma-separated list of geometry fields to interpolate over, e.g. 'path_zenith_rad' or 'path_zenith_rad,sensor_altitude_m'. |
| `atmosphere.interpolation_method` | str | linear | --- | --- | Interpolation method: 'linear' or 'nearest'. |
| `atmosphere.model` | str | simple | --- | --- | Atmosphere model selector. 'simple' uses a closed-form Beer-Lambert; 'exo' uses a vacuum; 'tabulated' loads from files; 'modtran' wraps the MODTRAN binary; 'interpolated' interpolates between pre-computed runs at discrete geometry points. |
| `atmosphere.modtran.aerosol_model` | str | rural | --- | --- | Aerosol model for MODTRAN (maps to IHAZE card). |
| `atmosphere.modtran.allow_fallback` | bool | False | --- | --- | If True and MODTRAN binary is unavailable, fall back to SimpleAtmosphere with translated parameters. |
| `atmosphere.modtran.atmosphere_profile` | str | us_standard | --- | --- | Standard atmosphere profile for MODTRAN (maps to MODEL card). Same enum as atmosphere.standard_atmosphere. |
| `atmosphere.modtran.binary_path` | str | /usr/local/bin/modtran | --- | --- | Path to the MODTRAN executable. |
| `atmosphere.modtran.cache_dir` | str | ~/.radiant/modtran_cache | --- | --- | Directory for caching MODTRAN tape7 results. Keyed by SHA-256 hash of the rendered tape5 deck. |
| `atmosphere.modtran.h2o_scale` | float | 1.0 | --- | (0.01, 10.0) | Water vapor column scaling factor for MODTRAN. |
| `atmosphere.modtran.o3_scale` | float | 1.0 | --- | (0.01, 10.0) | Ozone column scaling factor for MODTRAN. |
| `atmosphere.modtran.spectral_resolution_cm1` | float | 1.0 | cm-1 | (0.1, 100.0) | Spectral resolution [cm-1] for the MODTRAN computation. |
| `atmosphere.precipitable_water_cm` | float | 1.4 | cm | (0.0, 10.0) | Total column precipitable water in centimetres of liquid-equivalent water vapour. Drives the 5-band water-vapor extinction fit. |
| `atmosphere.standard_atmosphere` | str | us_standard | --- | --- | Standard atmosphere profile selector. Used by the simple model for the path-mean temperature lookup and aerosol/H2O scale heights. |
| `atmosphere.tabulated_downwelling_file` | str |  | --- | --- | Path to CSV file containing tabulated downwelling atmospheric emission [W/m^2/sr/um]. Optional; defaults to zeros if not provided. |
| `atmosphere.tabulated_path_radiance_file` | str |  | --- | --- | Path to CSV or NPZ file containing tabulated path radiance [W/m^2/sr/um]. Required when atmosphere.model='tabulated'. |
| `atmosphere.tabulated_transmittance_file` | str |  | --- | --- | Path to CSV or NPZ file containing tabulated atmospheric transmittance. CSV: two columns (wavelength_um, value). NPZ: key 'transmittance' with matching 'wavelength_um'. Required when atmosphere.model='tabulated'. |
| `atmosphere.visibility_km` | float | 23.0 | km | (0.1, 500.0) | Meteorological visibility at 550 nm in kilometres. Drives the Koschmieder aerosol extinction σ_aer(550 nm) = 3.912 / V_km. |

## geometry

| Parameter | Type | Default | Input Unit | Bounds | Description |
|-----------|------|---------|------------|--------|-------------|
| `geometry.path_zenith_rad` | float | 0.0 | rad | (0.0, 1.562) | Line-of-sight zenith angle [rad]. |
| `geometry.sensor_altitude_m` | float | **required** | m | (0.0, 100000000.0) | Sensor altitude above mean sea level [m]. |
| `geometry.solar_azimuth_rad` | float | 0.0 | rad | (-6.2832, 6.2832) | Sun-to-sensor relative azimuth [rad]. |
| `geometry.solar_zenith_rad` | float | 0.5 | rad | (0.0, 1.5707) | Solar zenith angle [rad]. |
| `geometry.target_altitude_m` | float | 0.0 | m | (0.0, 100000000.0) | Target altitude above mean sea level [m]. |

## optics

| Parameter | Type | Default | Input Unit | Bounds | Description |
|-----------|------|---------|------------|--------|-------------|
| `optics.aperture_diameter_m` | float | **required** | m | (0.0001, 20.0) | Clear entrance-pupil diameter of the primary [m]. |
| `optics.cold_stop_efficiency` | float | 1.0 | --- | (0.0, 1.0) | Cold-stop efficiency: fraction of the FPA hemisphere filled by warm (nearfield-emitting) elements. Unity for uncooled instruments. |
| `optics.f_number` | float | **required** | --- | (0.3, 200.0) | Dimensionless f/# = focal_length_m / aperture_diameter_m. Part of the {D, f, f/#} consistency group; supply any two and the third is derived. |
| `optics.focal_length_m` | float | **required** | m | (0.0001, 100.0) | Effective focal length of the telescope [m]. |
| `optics.nearfield_enabled` | int | 1 | --- | (0, 1) | Enable nearfield (warm-optics) emission calculation. Set to 0 to disable (int: 1=True, 0=False). |
| `optics.obscuration_ratio` | float | 0.0 | --- | (0.0, 0.99) | Central obscuration ratio ``D_secondary / D_primary``. Defaults to 0 (unobscured). Must satisfy 0 ≤ ε < 1. |
| `optics.optics_distance_to_fpa_m` | float | 0.0 | m | (0.0, 100.0) | Default distance from the optical train to the FPA [m]. Used as the distance_to_fpa_m for synthesized lumped elements. A value of 0.0 means 'use focal_length_m'. |
| `optics.optics_temperature_K` | float | 290.0 | K | (1.0, 1000.0) | Default physical temperature of the optical train [K]. Used for synthesized lumped elements in Modes 1-4. |
| `optics.psf_n_wavelengths` | int | 1 | --- | (1, 101) | Number of wavelengths for polychromatic PSF computation. 1 = monochromatic at band center (default). Values > 1 compute a photon-flux-weighted average of monochromatic PSFs across the spectral band. |
| `optics.stray.absolute_irradiance_W_m2` | float | 0.0 | W/m^2 | (0.0, 1000000.0) | Absolute in-band stray irradiance at the FPA [W/m^2]. Distributed flat across the wavelength grid. |
| `optics.stray.includes_thermal` | int | 0 | --- | (0, 1) | If 1, the stray light measurement already includes warm-optics scatter; nearfield is suppressed to avoid double-counting. (int: 1=True, 0=False). |
| `optics.stray.input_mode` | str | veiling_glare | --- | --- | Stray light input mode: veiling_glare, absolute_irradiance, spectral_file, or pst_file. |
| `optics.stray.veiling_glare_fraction` | float | 0.0 | --- | (0.0, 1.0) | Veiling glare fraction: fraction of in-FOV scene irradiance that becomes stray light [0, 1]. |
| `optics.transmission_input_mode` | str | scalar | --- | --- | Which of the five transmission input modes to use: scalar, spectral_file, telescope_plus_filters, key_elements, full_prescription. |
| `optics.transmission_scalar` | float | 0.7 | --- | (0.0, 1.0) | Flat broadband optical throughput ``τ_opt`` (Mode 1 of RADIANT_Optics.md §5.1). Dimensionless in [0, 1]. |
| `optics.wfe_mode` | str | scalar_rms | --- | --- | Wavefront error input mode: scalar_rms, zernike, opd_map, or field_dependent. |
| `optics.wfe_reference_wavelength_um` | float | 0.633 | um | (0.1, 30.0) | Reference wavelength at which the WFE is specified [um]. HeNe 0.633 um is the standard interferometry wavelength. |
| `optics.wfe_rms_waves` | float | 0.0 | waves | (0.0, 2.0) | RMS wavefront error in waves at the reference wavelength (scalar_rms mode). |

## detector

| Parameter | Type | Default | Input Unit | Bounds | Description |
|-----------|------|---------|------------|--------|-------------|
| `detector.clutter_sigma` | float | 0.0 | --- | (0.0, 1.0) | Scene clutter coefficient (fractional). Zero disables. |
| `detector.dark_activation_energy_eV` | float | 0.0 | eV | (0.0, 5.0) | Arrhenius activation energy for dark-rate temperature scaling. Zero disables scaling. |
| `detector.dark_rate_e_per_s` | float | 100.0 | 1/s | (0.0, 1000000000.0) | Dark current generation rate per pixel [e-/s]. |
| `detector.dark_reference_temperature_K` | float | 300.0 | K | (1.0, 500.0) | Temperature at which dark_rate_e_per_s is specified [K]. |
| `detector.detector_temperature_K` | float | 77.0 | K | (1.0, 500.0) | Detector operating temperature [K]. |
| `detector.dsnu_e_rms` | float | 0.0 | --- | (0.0, 1000000.0) | Dark-signal non-uniformity [e- RMS]. Zero disables. |
| `detector.fill_factor` | float | 1.0 | --- | (0.0, 1.0) | Photosensitive fraction of the pixel cell. |
| `detector.flicker_K` | float | 0.0 | --- | (0.0, 1000000000000.0) | 1/f flicker noise coefficient [e-²]. Zero disables. |
| `detector.flicker_f_high_hz` | float | 1000000.0 | Hz | (0.001, 1000000000.0) | Upper frequency bound for 1/f integration [Hz]. |
| `detector.flicker_f_low_hz` | float | 0.01 | Hz | (1e-06, 1000000.0) | Lower frequency bound for 1/f integration [Hz]. |
| `detector.glow_e_per_s` | float | 0.0 | 1/s | (0.0, 1000000.0) | Detector/ROIC glow rate [e-/s/pixel]. Zero disables. |
| `detector.gr_factor` | float | 0.0 | --- | (0.0, 10.0) | G-R noise factor (0 = disabled, 1 = classic HgCdTe). |
| `detector.ipc_coupling` | float | 0.0 | --- | (0.0, 0.25) | Inter-pixel capacitance coupling fraction α [0, 0.25). |
| `detector.noise_regime` | str | imaging | --- | --- | Noise regime: 'imaging' (temporal only, FPN calibrated out) or 'detection' (temporal + spatial). |
| `detector.persistence_fraction` | float | 0.0 | --- | (0.0, 1.0) | Fraction of prior-frame signal that persists. Zero disables. |
| `detector.persistence_tau_s` | float | 1.0 | s | (1e-06, 1000.0) | Persistence time constant [s]. |
| `detector.pixel_pitch_x_um` | float | **required** | um | (0.1, 1000.0) | Pixel pitch along the cross-track (x) axis. |
| `detector.pixel_pitch_y_um` | float | **required** | um | (0.1, 1000.0) | Pixel pitch along the along-track (y) axis. Defaults to x pitch. |
| `detector.prior_signal_e` | float | 0.0 | --- | (0.0, 1000000000.0) | Signal electrons from prior frame (for persistence). Zero disables. |
| `detector.prnu_pct` | float | 0.0 | --- | (0.0, 100.0) | Photo-response non-uniformity [%]. Zero disables. |
| `detector.qe_table_path` | str |  | --- | --- | Path to a wavelength-vs-QE table (loaded by SpectralDataStore). |
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
| `readout.full_well_capacity_e` | float | 100000.0 | --- | (100.0, 100000000.0) | Full well capacity per pixel [e-]. |
| `readout.gain_e_per_dn` | float | 1.0 | --- | (0.001, 1000000.0) | System conversion gain: electrons per digital number (LSB). |
| `readout.n_coadds` | int | 1 | --- | (1, 10000) | Number of coadded frames. 1 = no coadd. |
| `readout.n_tdi` | int | 1 | --- | (1, 1000) | Number of TDI stages. 1 = no TDI. |
| `readout.node_capacitance_F` | float | 0.0 | F | (0.0, 1e-09) | Sense-node capacitance [F]. Zero disables kTC noise. |
| `readout.read_noise_e_rms` | float | 5.0 | --- | (0.0, 10000.0) | Per-frame read noise delivered to the signal path [e- RMS]. |
| `readout.read_noise_is_post_cds` | int | 1 | --- | --- | If 1, the read_noise_e_rms value is already the post-CDS number (no √2 scaling needed). If 0, the value is pre-CDS and CDS adds √2. |
| `readout.tdi_mode` | str | analog | --- | --- | TDI readout mode: 'analog' (single readout after charge accumulation) or 'digital' (each stage read independently, summed digitally). |

## Consistency Groups

See `optics.f_number` = `optics.focal_length_m / optics.aperture_diameter_m`.
