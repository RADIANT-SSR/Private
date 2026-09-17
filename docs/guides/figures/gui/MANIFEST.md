# GUI Figure Manifest

Status: Generated — do not hand-edit.

Every figure in this folder is produced by `scripts/gen_gui_screenshots.py`,
which drives the real `RADIANTMainWindow` under `QT_QPA_PLATFORM=offscreen` on a
committed input config and grabs the window (or a named panel) after the window's
auto-evaluation completes. Offscreen rendering uses platform-neutral Fusion chrome
(Support_Documentation_Plan §10, ruling Q7), so the figures do not depend on who
regenerated them.

Regenerate the whole set with:

```
python scripts/gen_gui_screenshots.py --all
```

- Generator: `scripts/gen_gui_screenshots.py`
- Commit: `0b50efd1`
- Generated: 2026-09-16
- Figures: 34

| Figure | Capture | Input config | Workspace | Target | Window |
|---|---|---|---|---|---|
| `performance_workspace.png` | `performance_workspace` | `examples/mwir_leo_minimal.yaml` | `performance` | full window | 1440×900 |
| `geometry_workspace.png` | `geometry_workspace` | `examples/mwir_leo_minimal.yaml` | `geometry` | full window | 1440×900 |
| `optics_workspace.png` | `optics_workspace` | `examples/mwir_leo_minimal.yaml` | `optics` | full window | 1440×900 |
| `detector_workspace.png` | `detector_workspace` | `examples/mwir_leo_minimal.yaml` | `detector` | full window | 1440×900 |
| `build_geometry_inputs.png` | `build_geometry_inputs` | `examples/mwir_leo_minimal.yaml` | `geometry` → Inputs | full window | 1440×900 |
| `build_geometry_schematic.png` | `build_geometry_schematic` | `examples/mwir_leo_minimal.yaml` | `geometry` → Schematic | full window | 1440×900 |
| `build_optics_inputs.png` | `build_optics_inputs` | `examples/mwir_leo_minimal.yaml` | `optics` → Inputs | full window | 1440×900 |
| `flagship_performance.png` | `flagship_performance` | `scenarios/09_flagship_missions/9.2_landsat_tirs_nedt/tirs_b10_nedt_300k.yaml` | `performance` | full window | 1440×900 |
| `flagship_mtf_budget.png` | `flagship_mtf_budget` | `scenarios/09_flagship_missions/9.2_landsat_tirs_nedt/tirs_b10_nedt_300k.yaml` | `optics` → MTF | full window | 1440×900 |
| `flagship_noise_budget.png` | `flagship_noise_budget` | `scenarios/09_flagship_missions/9.2_landsat_tirs_nedt/tirs_b10_nedt_300k.yaml` | `detector` → Noise | full window | 1440×900 |
| `fpa_preset_detector.png` | `fpa_preset_detector` | `scenarios/02_mike_detector_engineer/2.8_fpa_part_library/inputs/geosnap18_mwir_leo.yaml` | `detector` → Inputs | full window | 1440×900 |
| `element_train_transmission.png` | `element_train_transmission` | `scenarios/09_flagship_missions/9.4_landsat_oli2_snr/oli2_b04_snr_ltyp.yaml` | `optics` → Transmission | full window | 1440×900 |
| `sweep_parameter_panel.png` | `sweep_parameter_panel` | `examples/mwir_leo_minimal.yaml` | `optics` → Inputs | `parameter_panel` | 1440×900 |
| `compare_configurations.png` | `compare_configurations` | `scenarios/09_flagship_missions/9.4_landsat_oli2_snr/oli2_all_bands_study.yaml` | `performance` | full window | 1440×900 |
| `ug_window_anatomy.png` | `ug_window_anatomy` | `examples/mwir_leo_minimal.yaml` | `geometry` → Inputs | full window | 1440×900 |
| `ug_stage_strip.png` | `ug_stage_strip` | `examples/mwir_leo_minimal.yaml` | `performance` | `stage_strip` | 1440×900 |
| `ug_parameter_dock.png` | `ug_parameter_dock` | `examples/mwir_leo_minimal.yaml` | `geometry` | `parameter_panel` | 1440×900 |
| `ug_right_rail.png` | `ug_right_rail` | `examples/mwir_leo_minimal.yaml` | `performance` | `right_rail` | 1440×900 |
| `ug_configuration_bar.png` | `ug_configuration_bar` | `scenarios/09_flagship_missions/9.4_landsat_oli2_snr/oli2_all_bands_study.yaml` | `performance` | `configuration_bar` | 1440×900 |
| `ug_geometry_inputs.png` | `ug_geometry_inputs` | `scenarios/09_flagship_missions/9.2_landsat_tirs_nedt/tirs_b10_nedt_300k.yaml` | `geometry` → Inputs | full window | 1440×900 |
| `ug_geometry_schematic.png` | `ug_geometry_schematic` | `scenarios/09_flagship_missions/9.2_landsat_tirs_nedt/tirs_b10_nedt_300k.yaml` | `geometry` → Schematic | full window | 1440×900 |
| `ug_source_scene_regime.png` | `ug_source_scene_regime` | `examples/mwir_leo_minimal.yaml` | `source` → Scene & regime | full window | 1440×900 |
| `ug_source_thermal.png` | `ug_source_thermal` | `examples/mwir_leo_minimal.yaml` | `source` → Target — thermal | full window | 1440×900 |
| `ug_source_reflective.png` | `ug_source_reflective` | `src/radiant/data/templates/aerial_vnir_imaging.yaml` | `source` → Target — reflective | full window | 1440×900 |
| `ug_atmosphere_workspace.png` | `ug_atmosphere_workspace` | `examples/mwir_leo_minimal.yaml` | `atmosphere` | full window | 1440×900 |
| `ug_optics_inputs.png` | `ug_optics_inputs` | `scenarios/09_flagship_missions/9.2_landsat_tirs_nedt/tirs_b10_nedt_300k.yaml` | `optics` → Inputs | full window | 1440×900 |
| `ug_optics_transmission_scalar.png` | `ug_optics_transmission_scalar` | `examples/mwir_leo_minimal.yaml` | `optics` → Transmission | full window | 1440×900 |
| `ug_platform_workspace.png` | `ug_platform_workspace` | `scenarios/09_flagship_missions/9.2_landsat_tirs_nedt/tirs_b10_nedt_300k.yaml` | `platform` → Inputs | full window | 1440×900 |
| `ug_detector_inputs.png` | `ug_detector_inputs` | `scenarios/09_flagship_missions/9.2_landsat_tirs_nedt/tirs_b10_nedt_300k.yaml` | `detector` → Inputs | full window | 1440×900 |
| `ug_readout_workspace.png` | `ug_readout_workspace` | `scenarios/09_flagship_missions/9.4_landsat_oli2_snr/oli2_b04_snr_ltyp.yaml` | `readout` | full window | 1440×900 |
| `ug_calibration_workspace.png` | `ug_calibration_workspace` | `scenarios/09_flagship_missions/9.2_landsat_tirs_nedt/tirs_b10_nedt_300k.yaml` | `calibration` | full window | 1440×900 |
| `ug_configured_parameters.png` | `ug_configured_parameters` | `scenarios/09_flagship_missions/9.4_landsat_oli2_snr/oli2_all_bands_study.yaml` | `spectral_integration` | `parameter_panel` | 1440×900 |
| `ug_performance_selection.png` | `ug_performance_selection` | `examples/mwir_leo_minimal.yaml` | `performance` | full window | 1440×900 |
| `ug_messages_error.png` | `ug_messages_error` | `scenarios/09_flagship_missions/9.2_landsat_tirs_nedt/tirs_b10_nedt_300k.yaml` | `calibration` | `right_rail` | 1440×900 |

## Pre-capture parameter edits

These figures show a state an operator reaches by editing a field, so the generator applies the edits below to the loaded config's shared base (one `Sensor.set` each, values in the schema's input unit) before building the window.

- `ug_platform_workspace.png` — `platform.jitter_rms_urad` = `8.0`
- `ug_calibration_workspace.png` — `calibration.scheme` = `'one_point'`; `calibration.cal_temp_low_K` = `290.0`
- `ug_performance_selection.png` — `performance.metrics.spatial_mtf` = `False`; `performance.metrics.interpretability` = `False`
- `ug_messages_error.png` — `calibration.scheme` = `'two_point'`

## Captions

- `performance_workspace.png` — Performance workspace on the minimal MWIR LEO example, after evaluation.
- `geometry_workspace.png` — Geometry workspace as it opens — the Inputs tab, mode cards and ranges.
- `optics_workspace.png` — Optics workspace as it opens — the Inputs tab and the derived optics outputs.
- `detector_workspace.png` — Detector workspace — QE and noise-term breakdown.
- `build_geometry_inputs.png` — Geometry workspace, Inputs tab, with the Parameters dock widened so the full dot-paths are readable.
- `build_geometry_schematic.png` — Geometry workspace, Schematic tab — the 2D viewing-triangle schematic.
- `build_optics_inputs.png` — Optics workspace, Inputs tab — aperture, focal length, and derived outputs.
- `flagship_performance.png` — Performance workspace on the Landsat 9 TIRS band-10 baseline — every metric group card populated after evaluation.
- `flagship_mtf_budget.png` — Optics workspace, MTF tab — system MTF curve and the per-term budget table.
- `flagship_noise_budget.png` — Detector workspace, Noise tab — the noise-budget table beside its chart.
- `fpa_preset_detector.png` — Detector workspace, Inputs tab, on a config built from the GeoSNAP-18 FPA preset — the preset-supplied fields carry the part's provenance.
- `element_train_transmission.png` — Optics workspace, Transmission tab, on the Landsat 9 OLI-2 band-4 config — the element train and the transmission it produces.
- `sweep_parameter_panel.png` — Parameters dock (panel-level grab) — the optics branch holding optics.aperture_diameter_m, the axis the sweep walkthrough varies.
- `compare_configurations.png` — Performance workspace on the nine-configuration OLI-2 study — one metric column per configuration, in set order, plain values only (ADR-0010 D-9).
- `ug_window_anatomy.png` — The main window at default proportions — configuration-free minimal MWIR example, Geometry workspace, after the load-time evaluation.
- `ug_stage_strip.png` — The signal-chain strip (panel-level grab) — ten stage chips in chain order, each with its health dot; Performance is the selected chip.
- `ug_parameter_dock.png` — The Parameters dock (panel-level grab) — filter box above the Parameter / Value / Source tree, scrolled to the geometry namespace.
- `ug_right_rail.png` — The right rail (panel-level grab) — pinned metric cards, the Edit Config (YAML) button, the Messages panel, and the Evaluate footer.
- `ug_configuration_bar.png` — The configuration selector (panel-level grab) on the nine-band OLI-2 study — one accent-chipped tab per configuration plus the manager gear.
- `ug_geometry_inputs.png` — Geometry workspace, Inputs tab, on the Landsat 9 TIRS band-10 baseline — scene-class card, one mode card per geometry family, derived-angle readout.
- `ug_geometry_schematic.png` — Geometry workspace, Schematic tab, on the TIRS band-10 baseline — a 705 km space-to-ground view drawn not to scale, altitudes carried by leader labels.
- `ug_source_scene_regime.png` — Source workspace, Scene & regime tab — the declared scene type, the regime override, and the tentative classification the source stage publishes.
- `ug_source_thermal.png` — Source workspace, Target — thermal tab — target and background temperature and emissivity beside the pre-atmosphere emitted-radiance spectra.
- `ug_source_reflective.png` — Source workspace, Target — reflective tab, on the bundled aerial VNIR template — target reflectance beside the reflected radiance it produces.
- `ug_atmosphere_workspace.png` — Atmosphere workspace — the model selector with only the active backend's knobs shown, above the transmittance and path-radiance spectra.
- `ug_optics_inputs.png` — Optics workspace, Inputs tab, on the Landsat 9 TIRS band-10 baseline — aperture and wavefront-error fields above the stage's derived outputs, including the final regime classification.
- `ug_optics_transmission_scalar.png` — Optics workspace, Transmission tab, in Scalar throughput mode — the mode selector, the banner stating which definition is in force, the single τ_opt field, and the flat τ_opt(λ) it produces.
- `ug_platform_workspace.png` — Platform workspace, Inputs tab, with an 8 µrad isotropic jitter entered — the jitter and motion/smear knobs beside the jitter σ, smear width and EE_box the stage derives from them.
- `ug_detector_inputs.png` — Detector workspace, Inputs tab — the FPA part-library row above the full detector schema in labelled groups, with no preset applied.
- `ug_readout_workspace.png` — Readout workspace on the Landsat 9 OLI-2 band-4 config — architecture, read noise, ADC, full well, TDI, co-adds, binning and acquisition groups beside the DN and noise outputs.
- `ug_calibration_workspace.png` — Calibration workspace with a one-point scheme active — the scheme selector and the groups it reveals, beside the residual, drift and bias outputs.
- `ug_configured_parameters.png` — The Parameters dock (panel-level grab) on the nine-band OLI-2 study — the configured parameters carry the red C badge; everything unmarked is shared.
- `ug_performance_selection.png` — Performance workspace with the Spatial / MTF and Interpretability groups deselected — the Compute row's state and the card sections that survive it.
- `ug_messages_error.png` — The right rail (panel-level grab) after a failed evaluation — pinned cards flipped to their stale marker and the Messages panel carrying the error.
