# Scenario 2.1 GUI Workflow: InSb vs. HgCdTe Noise Budget Shootout

How this scenario would be completed in the RADIANT GUI.

## Persona
Mike, detector engineer. Two vendor datasheets in different CSV
conventions, one shared ROIC spec, one question: which FPA, and how warm
can the cooler run?

## Step 1: Import Vendor Detector Data
- **File > Import > Detector QE Curve** — backed by
  `radiant.io.qe_csv.load_qe_csv`:
  - User picks `insb_qe.csv`; GUI shows the detected units from the header
    tokens ("wavelength_nm → nm", "QE_pct → percent") with a confirmation
    chip; parse errors (QE > 1 in fraction mode, unknown units) surface as
    actionable dialogs naming the override (`qe_unit="percent"`)
  - Repeat for `hgcdte_qe.csv` — different convention, same dialog; both
    land in canonical µm/fraction
  - Preview: both curves overlaid with the cold-filter band shaded
- **File > Import > Dark Current Curve** — backed by
  `radiant.io.dark_current_csv.load_dark_current_csv`:
  - Semilog preview of J_dark(T); tooltip states the interpolation model
    (ln J linear in 1/T) and the no-extrapolation policy
  - **Range guard surfaced**: if a later query (e.g. BLIP T) falls outside
    the table, the GUI shows the loader's error and asks for extended
    vendor data — never extrapolates silently

## Step 2: Bench Configuration
- Load `mike_roic_specs.xlsx` through the mapping dialog (unit-aware
  import per scenario 6.3's workflow: fF → F, cm → m, % → fraction,
  ms → s)
- **Detector-only bench preset** (registry Gap 42): GUI sets exo
  atmosphere + the `platform.h_sensor` bench placeholder behind a single
  "Lab bench / flat-field source" checkbox with an explanatory tooltip
- **Spectral QE toggle**: "Use imported QE curve" — the GUI evaluates the
  curve on the chain grid and performs the `qe_curve` injection (registry
  Gap 44: no config path exists; the GUI owns the injection until then).
  A/B switch against the band-averaged scalar for comparison

## Step 3: Run the Comparison
- "Compare Detectors" runs the chain once per FPA (same bench, per-FPA
  QE curve, dark rate at the set point, read noise)
- Results view: side-by-side noise budget table (every chain term, e⁻
  RMS), log-scale grouped bar chart, SNR/signal/total-noise summary cards
- Callouts the GUI must make:
  - "background_shot = 0 by design (extended regime)" — not a bug
  - "quantization = 88 e⁻ (gain/√12) is your #2 term — consider a
    low-gain mode" when quantization exceeds read noise
  - kTC suppressed indicator when CDS is on, with the √(kTC)/q hand value

## Step 4: Cooler-Budget Trade Panel
- **Crossover T**: GUI calls `temperature_at_rate(RN²/t_int)` per FPA
- **BLIP T**: `temperature_at_rate(signal_e/t_int)`
- **NEI**: σ_total/(QE·A_pix·t_int) [photons/s/cm²] (+ W/cm² with the
  band-center caveat)
- Display: the J_dark(T) semilog plot with crossover/BLIP markers per FPA
  and a "cooler margin" delta chip (e.g. "HgCdTe: +6.8 K vs InSb")
- Set-point slider: drag T_FPA from 60–130 K, noise budget updates live
  (dark rate re-queried from the vendor curve)

## Step 5: Export
- Excel workbook (noise budget + cooler-trade sheets), PNG figures,
  parameter snapshot per FPA

## Script Window Commands
```python
from radiant.io.qe_csv import load_qe_csv
from radiant.io.dark_current_csv import load_dark_current_csv

qe = load_qe_csv("insb_qe.csv")                    # nm/% auto-resolved
jd = load_dark_current_csv("insb_jdark.csv")

qe.band_averaged_qe(3.5, 5.0)                      # [fraction]
jd.dark_rate_e_per_s(77.0, pixel_pitch_m=15e-6)    # [e-/s]

# Cooler-trade one-liners (registry Gap 45 until native):
t_cross = jd.temperature_at_rate(18.0**2 / 1e-3, pixel_pitch_m=15e-6)  # [K]
t_blip = jd.temperature_at_rate(signal_e / 1e-3, pixel_pitch_m=15e-6)  # [K]

# Spectral QE injection (registry Gap 44 until a config path exists):
result = session.run(params, extra_stage_outputs={
    "spectral_integration": {"qe_curve": qe.evaluate(wl_grid)}})
```

## GUI Requirements Summary

| Requirement | Priority | Gap |
|-------------|----------|-----|
| QE CSV import with header-unit confirmation | High | **CLOSED** (io/qe_csv) |
| J_dark(T) import with no-extrapolation guard surfaced | High | **CLOSED** (io/dark_current_csv) |
| Spectral-QE injection behind a toggle | High | Registry Gap 44 (GUI owns injection until config path) |
| Detector-only bench preset | Medium | Registry Gap 42 |
| Cooler-trade panel (crossover/BLIP/NEI + set-point slider) | High | Registry Gap 45 (GUI computes via loaders) |
| Side-by-side multi-config comparison view | High | — |
| Quantization-vs-read-noise advisory callout | Low | — |
