# Scenario 1.3 GUI Workflow: Dual-Band MWIR/LWIR Wildfire Trade

How this scenario would be completed in the RADIANT GUI.

## Persona
Sarah, systems engineer. One vendor comparison table, one ASTER spectrum,
one band decision to defend at the design review.

## Step 1: Import the Forest Spectrum
- **File > Import > Material Spectrum (ASTER)** — backed by
  `radiant.io.aster_library.load_aster_spectrum`:
  - Parses the native ASTER text format (metadata header, descending
    wavelength, percent) with the unit taken from the `Y Units:` line
  - Preview: ρ(λ) and ε(λ) = 1 − ρ(λ) curves with both candidate bands
    shaded; band-averaged ε chips per band (0.9530 / 0.9821)
  - Tooltip: "same material, different ε per band — scalars are per-band"

## Step 2: Import the Detector Options
- **File > Import Spreadsheet** on the comparison table: the mapping
  dialog reads BOTH value columns and creates two candidate configs that
  share the platform sheet (unit-aware conversions per Gap 6)
- **Well-fill advisory**: before running, the GUI estimates pixel signal
  for the declared scene and flags integration times that will clip
  (the first execution of this scenario clipped both bands — the GUI
  should catch that pre-run, not post-run)

## Step 3: Configure the Scene
- Hotspot: 5 m² at 600 K, ε 0.85; forest background 300 K with the
  per-band ASTER ε auto-filled
- Sub-pixel panel: GSD/footprint/fill-fraction readout (4 m / 16 m² /
  31%), regime override to sub_pixel with the "keep in-pixel background"
  explanation; clutter σ input (0.03, forest)

## Step 4: Run the Band Comparison
- "Compare Bands" runs both configs; side-by-side cards:
  SNR, contrast SNR, SCNR (incl. clutter — labeled as the detection
  number), NEDT (with the Gap 43 caveat chip), well fill, noise budgets
- Callout: "ΔL nearly equal (374 vs 382 W/m²/sr) — the trade is decided
  by clutter, 350× higher in LWIR"

## Step 5: Fire-Temperature Sweep
- Slider/sweep 400–1200 K; SCNR and P_d curves per band with saturation
  markers (signal ≥ 98% well) and the P_fa threshold line
- Advisory: "LWIR saturates from ≈800 K, MWIR from ≈900 K at these
  integrations — shorten t_int to move the clip point"

## Step 6: Export
- Trade report: comparison table, sweep, spectral-contrast figure,
  recommendation text

## Script Window Commands
```python
from radiant.io.aster_library import load_aster_spectrum
forest = load_aster_spectrum("forest_conifer_aster.txt")
forest.band_averaged_emissivity(3.5, 5.0)   # 0.9530 [--]
forest.band_averaged_emissivity(8.0, 12.0)  # 0.9821 [--]

# per-band sensors from the comparison table, then:
scnr = abs(r.stage_outputs["spectral_integration"]["contrast_e"]) / total_noise
```

## GUI Requirements Summary

| Requirement | Priority | Gap |
|-------------|----------|-----|
| ASTER spectrum import with ε preview | High | **CLOSED** (io/aster_library) |
| Two-column vendor table → two configs | High | — (mapping dialog feature) |
| Pre-run well-fill/clipping advisory | High | — (caught post-run in this execution) |
| Sub-pixel fill/footprint panel with clutter | High | Same pattern as scenario 4.1 |
| Band-comparison card with SCNR as the detection number | High | snr/contrast_snr exclude clutter (4.1 observation) |
| Temperature sweep with saturation markers | Medium | — |
| P_d / ROC panel | Medium | Planned T4 (scenarios 4.2/6.4) |
