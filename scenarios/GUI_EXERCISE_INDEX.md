# GUI Exercise Campaign — Index

Status: Active

The 37 scenarios were built to validate the **backend engine** (they run as
`scripts/run_*.py` against the API). This campaign re-runs the same scenarios
**through the GUI** to shake out the desktop app. It adds three artifacts per
scenario and three headless gates, and it points at each scenario's
`gui_workflow.md` for the bespoke widgets a human still has to click.

The GUI opens **YAML only** (`File → Open YAML`) and reproduces analysis in its
**scripting window** (Ctrl+Shift+P), which binds a live `sensor` / `result` /
`plot` / `Sensor` namespace. The scenario runners store config as `.xlsx` plus
hard-coded Python — none of it GUI-loadable — so each scenario now also ships a
GUI-openable baseline derived from its validated runner.

---

## Artifacts added per scenario

| File | What it is |
|---|---|
| `inputs/<slug>.gui.yaml` | GUI-openable baseline, **derived** from the validated runner (`Sensor.to_yaml`), not hand-written. This is what `File → Open YAML` consumes. |
| `inputs/<slug>.gui.expected.json` | Headline-metric snapshot taken at emit time; the reload gate re-checks it. |
| `scripts/gui_console_<slug>.py` | Scripting-window script: echoes metrics **with units**, runs a trade micro-sweep binding `plot`, and mutates a parameter to trip the stale-banner. Runs pasted into the GUI console *and* standalone. |

The generator/registry that produces them lives in `scenarios/tools/`.

---

## Automated gates (run from repo root)

```bash
# 1. (Re)generate baselines + expected snapshots + console scripts
python scenarios/tools/emit_gui_yaml.py          # writes *.gui.yaml + *.expected.json
python scenarios/tools/gen_gui_console.py        # writes gui_console_*.py

# 2. API-level gate: every YAML reloads and reproduces its snapshot
python scenarios/tools/verify_gui_yaml.py        # -> "N/37 scenarios PASS"

# 3. Widget-level gate: every YAML opens in the REAL RADIANTMainWindow and its
#    console script runs inside the REAL ScriptingConsole — no display needed
QT_QPA_PLATFORM=offscreen python scenarios/tools/verify_gui_open.py
```

All three accept a scenario-id subset, e.g. `... verify_gui_open.py 1.1 2.3`.

Gate 3 is the headless proxy for "exercise the GUI through the GUI": it drives
the same widget code path a user does (open a config, run the chain, use the
scripting console). What it **cannot** drive — file-importers, sliders, matrix
builders, radar charts, error-budget panels — is exactly what the manual loop
below covers, per scenario, against each `gui_workflow.md`.

---

## Manual GUI exercise loop (per scenario)

1. **Open** `File → Open YAML → inputs/<slug>.gui.yaml`. The main view should
   populate and evaluate without error.
2. **Confirm the headline metrics** match `inputs/<slug>.gui.expected.json`
   (SNR / NEDT / NIIRS). A mismatch is a GUI display or wiring bug.
3. **Run the console script**: open the scripting window (Ctrl+Shift+P), paste
   `scripts/gui_console_<slug>.py`, run it. The figure should pop out; the
   parameter change should mark the main view stale.
4. **Walk the scenario's `gui_workflow.md`** — it lists the bespoke widgets and
   imports this scenario is meant to stress (see the focus column below).
   Anything it demands that the GUI does not yet provide is a **finding**.
5. **Log findings**: GUI defects → `docs/tracking/Cleanup_Backlog.md` (CU, Rule
   21); missing capabilities → `docs/tracking/gaps.md` (Rule 25).

---

## Scenario master table — what each one stresses in the GUI

Paths follow the uniform pattern above; the focus column is distilled from each
`gui_workflow.md` (the manual-check anchor).

| Scenario | GUI surface it exercises (see its `gui_workflow.md`) |
|---|---|
| **01 Sarah — systems engineer** | |
| 1.1 mwir_maritime_surveillance | tape7 import; QE-curve digitizer; atmosphere A/B toggle; aperture sweep plots |
| 1.2 vnir_gsd_aperture_altitude | orbit/LTAN + seasonal solar-zenith; GSD-hold aperture×altitude contour |
| 1.3 dual_band_mwir_lwir | ASTER material import; spreadsheet import; dual-band side-by-side; well-fill advisory |
| 1.4 tdi_pushbroom_optimization | live sliders (FWC, read noise, reflectance, TDI misalignment) |
| 1.5 obscured_aperture_spider_vanes | obscuration/strut sweep; Strehl-caveat surfacing |
| **02 Mike — detector engineer** | |
| 2.1 insb_vs_hgcdte_noise_budget | detector QE + dark-current curve import; range guard; detector-only bench preset |
| 2.2 1f_noise_corner_frequency | 1/f corner + frame-rate; Hz unit conversions |
| 2.3 ipc_impact_on_mtf | IPC → MTF-path coupling; MTF budget view |
| 2.4 persistence_bright_source | persistence decay panel; SNR recovery; dead-time readout |
| 2.5 well_capacity_optimization | well-capacity; integration-time vs dynamic-range trade |
| **03 Raj — mission planner** | |
| 3.1 isr_pass_planning | orbit dashboard; off-nadir trade; access corridor |
| 3.2 weather_sensitivity | visibility + PWV sweep |
| 3.3 multi_sensor_comparison | multi-proposal comparison table; compliance matrix; radar chart |
| 3.4 off_nadir_agility | SNR-vs-angle and GSD-vs-angle tabs |
| 3.5 nighttime_mwir_feasibility | night scene; LST-map load; dual-band panel |
| **04 Lisa — analyst** | |
| 4.1 target_detection_matrix | target-library import; deprecation banner; matrix builder + progress grid |
| 4.2 maritime_ship_classification | DRI matrix; range bars; cycles-vs-range |
| 4.3 camouflage_effectiveness | ASTER + emissivity-CSV import; spectral-emissivity note (Gap 47); signature-reduction % |
| 4.4 time_of_day_analysis | diurnal profile load; temporal sweep; washout detection |
| 4.5 altitude_trade_uav | UAV vendor-spec load; altitude trade; ceiling diagnosis |
| **05 Tom — optical designer** | |
| 5.1 wfe_budget_allocation | Zemax import; error-budget panel; target NIIRS/Strehl inputs |
| 5.2 pixel_pitch_optimization | pixel-pitch / Q-parameter trade |
| 5.3 mono_vs_poly_psf | monochromatic vs polychromatic PSF (n-wavelength) |
| 5.4 jitter_induced_blur | jitter tolerance; LOS-stability requirement |
| 5.5 stray_light_veiling_glare | stray-light panel; tolerance slider; noise budget |
| **06 Dr. Chen — researcher** | |
| 6.1 published_snr_benchmark | datasheet benchmark panel; residual diagnosis |
| 6.2 atmospheric_intercomparison | atmosphere-model swap toggle; six-profile grid; per-band residual panel |
| 6.3 noise_model_verification | spreadsheet import + column-mapping dialog; noise-model check |
| 6.4 synthetic_scene_generation | per-target radiometry panel; scene-strip view; detection-range sweep |
| 6.5 spectral_emissivity_sensitivity | emissivity Jacobian panel; retrieval sweep; tolerance readout |
| **07 Karen — test engineer** | |
| 7.1 nedt_reconciliation | nominal-vs-as-built table; atmosphere auto-detect |
| 7.2 radiometric_calibration | spreadsheet + measured-curve import; self-emission panel; predicted-vs-measured plot |
| 7.3 mtf_measurement_vs_prediction | MTF measured-vs-predicted overlay; warning surfacing (CU-058) |
| 7.4 cold_stop_sweep | cold-stop leakage sweep; derived-parameter highlights |
| 7.5 environmental_temp_extremes | measured-curve import; compliance panel; co-varying dark current |
| **08 Interpolation demonstrations** | |
| 8.1 off_nadir_angle_interpolation | query-geometry entry; coverage indicator; A/B vs nearest-neighbor; family registry browser |
| 8.2 target_altitude_interpolation | query-altitude entry; interpolation coverage + A/B |
| **10 Direction-general validation (ADR-0011 / Geometry-Flexibility Phase 5)** | |
| 10.1 ground_to_air_mwir_detection | scene-class chip (ground_to_air derived) + assertion; up-looking schematic composition (sensor on the ground plane, LOS ascending); θ_o / ζ_low arcs (obtuse θ_o); relevance preview — GSD family off, target-plane metrics on |
| 10.2 air_to_air_level_irst | level schematic composition (both endpoints elevated); Δh sag pill; horizon-guard warning surfaced in Messages; kinematics doors (K1/K2) in the LOS-rate family selector |
| 10.3 ground_to_space_sst_visible | scene-class chip (ground_to_space); up-looking full-column composition; turbulence inputs (Cn² profile / r₀); solar-depression entry past 90° (terminator) |
| 10.4 leo_to_geo_exo | space-observer both-elevated composition; θ_o = π exactly on the arc pill; vacuum-path atmosphere view (τ = 1); assertion agreeing with the derivation |

---

## Cross-cutting GUI surface coverage

The campaign touches these GUI subsystems (a defect in one shows up across all
the scenarios listed):

- **File importers** — tape7 (1.1), ASTER/material spectrum (1.3, 4.3),
  QE/dark-current curve (2.1), spreadsheet + column-mapping (1.3, 6.3, 7.2),
  measured curve (7.2, 7.5), Zemax WFE (5.1), target library (4.1).
- **Live parameter sliders** — 1.4, 5.5 (and any form field, all scenarios).
- **Sweep + overlay plotting** — every scenario via the console micro-sweep;
  bespoke contour/matrix views in 1.2, 4.1, 4.2.
- **Bespoke analysis panels** — error budget (5.1), stray light (5.5),
  persistence decay (2.4), Jacobian (6.5), DRI matrix (4.2), radar/compliance
  (3.3), benchmark residual (6.1, 7.2).
- **Regime / warning surfacing** — 1.1, 1.5, 7.3 (CU-058); the scripting
  console's stale-banner (every console script trips it).
- **Interpolation family browser** — 8.1, 8.2.

---

## Known caveats

- The `.gui.yaml` baselines pick a **portable** point of each scenario's trade
  (mid-range aperture, `simple` atmosphere where the runner used a staged
  MODTRAN tape7). The console script shows how to switch to the heavier source.
  The full sweep still lives in the original `scripts/run_*.py`.
- The console micro-sweep uses a generic aperture axis unless a scenario
  overrides it — it exercises the console/plot path, it is not the scenario's
  headline trade (that is the runner's job).
- Gate 3 (offscreen widget gate) covers open + evaluate + console-run. Bespoke
  importer/slider/panel widgets are **manual-only** — that is what step 4 of the
  loop is for.
- Scenario **6.4** takes **~123 s per chain evaluate** (measured, real GUI): its
  runner's own config is a small f/20 aperture that heavily oversamples the optics
  (Q ≈ 8), which blows up the PSF/MTF grid over the 500-point wavelength axis.
  The baseline is faithful to the validated runner — the cost is a RADIANT
  PSF-grid performance characteristic at high Q, not a defect in the baseline.
  Opening 6.4 and hitting Run in the GUI freezes for ~2 minutes; its console
  sweep would take ~15 minutes. Tracked for investigation as **CU-165**.

## Coverage and verification status

**34 of 37 scenarios** ship a GUI baseline + console script. The three
exclusions are not chain scenarios — their runners call a physics **sub-module
directly** and never assemble a full `Sensor` config, so there is nothing for
`File → Open YAML` to load. Exercise them from the scripting window instead:

| Scenario | Why no `.gui.yaml` | Exercise via console |
|---|---|---|
| 2.4 persistence_bright_source | analytic persistence decay | `from radiant.detector.persistence_sequence import persistence_residual_sequence_e` |
| 4.2 maritime_ship_classification | Johnson-criteria DRI ranges | `from radiant.performance.johnson_criteria import johnson_range_m` |
| 6.5 spectral_emissivity_sensitivity | emissivity/temperature Jacobians | `from radiant.performance.temperature_retrieval import emissivity_jacobian` |

**Automated gate results** (2026-07-18, run from repo root):

- `verify_gui_yaml.py` (API reload gate): **34 / 34 PASS** — every `.gui.yaml`
  reloads via `Sensor.from_yaml` and reproduces its metric snapshot.
- `verify_gui_open.py` (offscreen real-GUI gate): **33 / 34 run clean, 0
  failures** — each baseline opens in `RADIANTMainWindow` and its console script
  runs inside the real `ScriptingConsole` with no traceback. The one exception is
  **6.4**, which opens and evaluates correctly in the real GUI (SNR = 874.4) but
  each chain `evaluate()` takes **~123 s** (see the caveat below and CU-165), so
  its 8-evaluation console sweep is impractical to run headless; it is excluded
  from the automated widget gate and checked open-only.

Re-run both after any change to a scenario runner or the emitter; the two gates
are the definition of done for the GUI artifacts.

> Import note (see CU-164): every scenario runner keeps only imports, constants,
> input loading and its config factories at module scope, with the analysis behind
> `if __name__ == "__main__": main()`. Importing one to reach its factory therefore
> runs no analysis, prints nothing and writes nothing — the `_StopModuleExec` halt
> that used to stop an unguarded sweep mid-import is retired. The emitter still
> imports inside the hermetic guard (`scenarios/tools/_runner_import.py`, which
> no-ops figure/workbook writes and silences stdout) as a belt-and-braces backstop,
> so regenerating baselines never clobbers committed figures.
>
> One consequence for 4.3: its derived radiance CSVs live in the gitignored
> `outputs/derived/` tree and are written by `main()`, so its baseline factory
> reads them on demand. Run `python run_camouflage_analysis.py` once before
> re-emitting the 4.3 baseline in a cold checkout; the factory says so if you
> don't. (The shipped `.gui.yaml` points at the committed `inputs/` copy — CU-180
> / CU-273 — so *verifying* the baselines needs no such run.)
