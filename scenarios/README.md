# RADIANT Scenarios

Persona-driven test cases for exercising the RADIANT tool. Each numbered folder
is a persona archetype; each `N.M_*` subfolder is a self-contained scenario with
its own inputs, scripts, and outputs.

Scenario descriptions and execution order: `docs/guides/scenario_catalog.md`.
Rules for building and validating scenarios: `docs/guides/scenario_testing.md`.
File placement and naming rules: `docs/OPERATING_MODEL.md` §5.

Scenario scripts need the `scenarios` extra (`pip install -e ".[scenarios]"`) —
openpyxl for the vendor-format Excel inputs/outputs and matplotlib for figures.

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

## GUI exercise layer

The scenarios above validated the **backend**. To exercise the **GUI** with the
same cases, each chain-based scenario also ships a GUI-openable baseline:

```
N.M_scenario_slug/
  inputs/
    <slug>.gui.yaml            # GUI-openable baseline, derived from the runner
    <slug>.gui.expected.json   # headline-metric snapshot (verify gate re-checks)
  scripts/
    gui_console_<slug>.py       # scripting-window script (metrics, sweep, mutate)
```

These are **generated**, not hand-written — `scenarios/tools/` imports each
runner's validated config factory and serialises `Sensor.to_yaml()`. Regenerate
and verify with:

```bash
python scenarios/tools/emit_gui_yaml.py        # baselines + snapshots
python scenarios/tools/gen_gui_console.py      # console scripts
python scenarios/tools/verify_gui_yaml.py      # API gate: reload + reproduce
QT_QPA_PLATFORM=offscreen python scenarios/tools/verify_gui_open.py  # real-GUI gate
```

The campaign driver — how to walk each scenario through the GUI and what each one
stresses — is `scenarios/GUI_EXERCISE_INDEX.md`. Three scenarios (2.4, 4.2, 6.5)
are analytic sub-module demos with no sensor-chain config, so they have no
`.gui.yaml`; the index notes how to exercise them from the scripting window.

## Status

**All 35 persona scenarios plus both interpolation demonstrations are
implemented and executed** (walkthrough / gaps / gui_workflow trio present in
every folder; executed 2026-07-08/09). The previous table under-reported
maturity by marking 21 executed scenarios "stub" and omitting the 08 series
(CU-075, corrected 2026-07-12).

| Scenario | Status |
|---|---|
| **01 Sarah — systems engineer** | |
| 1.1_mwir_maritime_surveillance | implemented |
| 1.2_vnir_gsd_aperture_altitude | implemented |
| 1.3_dual_band_mwir_lwir | implemented |
| 1.4_tdi_pushbroom_optimization | implemented |
| 1.5_obscured_aperture_spider_vanes | implemented |
| **02 Mike — detector engineer** | |
| 2.1_insb_vs_hgcdte_noise_budget | implemented |
| 2.2_1f_noise_corner_frequency | implemented |
| 2.3_ipc_impact_on_mtf | implemented |
| 2.4_persistence_bright_source | implemented |
| 2.5_well_capacity_optimization | implemented |
| **03 Raj — mission planner** | |
| 3.1_isr_pass_planning | implemented |
| 3.2_weather_sensitivity | implemented |
| 3.3_multi_sensor_comparison | implemented |
| 3.4_off_nadir_agility | implemented |
| 3.5_nighttime_mwir_feasibility | implemented |
| **04 Lisa — analyst** | |
| 4.1_target_detection_matrix | implemented |
| 4.2_maritime_ship_classification | implemented |
| 4.3_camouflage_effectiveness | implemented |
| 4.4_time_of_day_analysis | implemented |
| 4.5_altitude_trade_uav | implemented |
| **05 Tom — optical designer** | |
| 5.1_wfe_budget_allocation | implemented |
| 5.2_pixel_pitch_optimization | implemented |
| 5.3_mono_vs_poly_psf | implemented |
| 5.4_jitter_induced_blur | implemented |
| 5.5_stray_light_veiling_glare | implemented |
| **06 Dr. Chen — researcher** | |
| 6.1_published_snr_benchmark | implemented |
| 6.2_atmospheric_intercomparison | implemented |
| 6.3_noise_model_verification | implemented |
| 6.4_synthetic_scene_generation | implemented |
| 6.5_spectral_emissivity_sensitivity | implemented |
| **07 Karen — test engineer** | |
| 7.1_nedt_reconciliation | implemented |
| 7.2_radiometric_calibration | implemented |
| 7.3_mtf_measurement_vs_prediction | implemented |
| 7.4_cold_stop_sweep | implemented |
| 7.5_environmental_temp_extremes | implemented |
| **08 Interpolation demonstrations** | |
| 8.1_off_nadir_angle_interpolation | implemented |
| 8.2_target_altitude_interpolation | implemented |
| **09 Flagship missions (external validation)** | |
| 9.1_sentinel2_msi_snr | implemented (config-driven; canonical comparison in scripts/run_external_validation.py) |
| 9.2_landsat_tirs_nedt | implemented (config-driven) |
| 9.3_modis_teb_nedt | implemented (config-driven) |
| **10 Direction-general validation (Geometry-Flexibility Phase 5)** | |
| 10.1_ground_to_air_mwir_detection | implemented (executed 2026-07-28; MODTRAN K-ladder anchor) |
| 10.2_air_to_air_level_irst | implemented (executed 2026-07-28; MODTRAN L-grid anchor) |
| 10.3_ground_to_space_sst_visible | implemented (executed 2026-07-28; MODTRAN anchor deferred — owner batch 2) |
| 10.4_leo_to_geo_exo | implemented (executed 2026-07-28; vacuum-identity anchors, exact) |

40 of 40 implemented (35 persona + 2 interpolation + 3 flagship-mission validation). Each folder carries the
`walkthrough.md` / `gaps.md` / `gui_workflow.md` trio and executed
`inputs/scripts/outputs`.

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
| 09_flagship_missions | — | External validation vs published flagship-mission flight data (Sentinel-2, Landsat TIRS, MODIS) |
