# RADIANT Scenarios

Persona-driven test cases for exercising the RADIANT tool. Each numbered folder
is a persona archetype; each `N.M_*` subfolder is a self-contained scenario with
its own inputs, scripts, and outputs.

Scenario descriptions and execution order: `docs/guides/scenario_catalog.md`.
Rules for building and validating scenarios: `docs/guides/scenario_testing.md`.
File placement and naming rules: `docs/OPERATING_MODEL.md` §5.

## Layout of an implemented scenario

```
NN_persona/
  N.M_scenario_slug/
    inputs/
      create_spreadsheet.py        # generator for the input workbook
      <persona>_<topic>_data.xlsx  # scenario input data (committed)
    scripts/
      run_<scenario_slug>.py       # the scenario driver
    outputs/
      MANIFEST.md                  # provenance: generator + input + commit per artifact
      <slug>_<what_it_shows>.png   # committed figures (referenced by walkthrough.md)
      <slug>_results.xlsx          # NOT committed — regenerate by running the script
    walkthrough.md                 # narrative: what was run, what the numbers mean
    gaps.md                        # every RADIANT limitation hit, with workaround used
    gui_workflow.md                # how a GUI would need to support this workflow
```

**Definition of done** for a scenario: the run script executes cleanly from the
committed inputs; `walkthrough.md`, `gaps.md`, and `gui_workflow.md` all exist
(the trio is mandatory — an empty gaps.md that says "no gaps found" is valid,
a missing one is not); every numerical value in script output carries units;
the script's output explains the radiometric regime in effect and any
non-obvious physics; `outputs/MANIFEST.md` names the generator, input file,
and commit for each committed artifact. Open items in `gaps.md` must also be
mirrored to `docs/tracking/gaps.md` (the tracking registry) to be actionable.

**Output policy** (OPERATING_MODEL Rule 26): figures referenced by
`walkthrough.md` are committed with a manifest line; `*_results.xlsx`
workbooks are regenerate-on-demand and gitignored.

## Status

| Scenario | Status |
|---|---|
| **01 Sarah — systems engineer** | |
| 1.1_mwir_maritime_surveillance | stub |
| 1.2_vnir_gsd_aperture_altitude | stub |
| 1.3_dual_band_mwir_lwir | stub |
| 1.4_tdi_pushbroom_optimization | **implemented** |
| 1.5_obscured_aperture_spider_vanes | stub |
| **02 Mike — detector engineer** | |
| 2.1_insb_vs_hgcdte_noise_budget | stub |
| 2.2_1f_noise_corner_frequency | **implemented** |
| 2.3_ipc_impact_on_mtf | **implemented** |
| 2.4_persistence_bright_source | stub |
| 2.5_well_capacity_optimization | **implemented** |
| **03 Raj — mission planner** | |
| 3.1_isr_pass_planning | stub |
| 3.2_weather_sensitivity | **implemented** |
| 3.3_multi_sensor_comparison | stub |
| 3.4_off_nadir_agility | **implemented** |
| 3.5_nighttime_mwir_feasibility | stub |
| **04 Lisa — analyst** | |
| 4.1_target_detection_matrix | stub |
| 4.2_maritime_ship_classification | stub |
| 4.3_camouflage_effectiveness | stub |
| 4.4_time_of_day_analysis | stub |
| 4.5_altitude_trade_uav | stub |
| **05 Tom — optical designer** | |
| 5.1_wfe_budget_allocation | **implemented** |
| 5.2_pixel_pitch_optimization | **implemented** |
| 5.3_mono_vs_poly_psf | **implemented** |
| 5.4_jitter_induced_blur | **implemented** |
| 5.5_stray_light_veiling_glare | stub |
| **06 Dr. Chen — researcher** | |
| 6.1_published_snr_benchmark | stub |
| 6.2_atmospheric_intercomparison | stub |
| 6.3_noise_model_verification | **implemented** |
| 6.4_synthetic_scene_generation | stub |
| 6.5_spectral_emissivity_sensitivity | stub |
| **07 Karen — test engineer** | |
| 7.1_nedt_reconciliation | **implemented** |
| 7.2_radiometric_calibration | stub |
| 7.3_mtf_measurement_vs_prediction | **implemented** |
| 7.4_cold_stop_sweep | **implemented** |
| 7.5_environmental_temp_extremes | stub |

14 of 35 implemented. Stubs contain only the `inputs/scripts/outputs` skeleton
(`.gitkeep` markers) and are intentional placeholders for the persona test plan.

## Personas

| Folder | Persona | Role |
|--------|---------|------|
| 01_sarah_systems_engineer | Sarah | Systems engineer running trade studies |
| 02_mike_detector_engineer | Mike | Detector engineer evaluating FPA options |
| 03_raj_mission_planner | Raj | Mission planner optimizing orbits and coverage |
| 04_lisa_analyst | Lisa | Intelligence analyst assessing detection capability |
| 05_tom_optical_designer | Tom | Optical designer optimizing PSF and MTF |
| 06_dr_chen_researcher | Dr. Chen | Researcher validating models against theory |
| 07_karen_test_engineer | Karen | Test engineer reconciling predictions with measurements |
