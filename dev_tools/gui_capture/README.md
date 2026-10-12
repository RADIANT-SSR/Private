# GUI capture harness

Deterministic offscreen screenshots of the RADIANT GUI and headless renders of
every `result.plot.*` figure. This is the **generator** (Rule 26) of every
before/after contact sheet under `docs/reports/gui_visual_finish_2026-10/`
and of the blind pairs the aesthetic auditors score in the GUI Visual Finish
program (`docs/plans/GUI_Visual_Finish_Plan.md`, Gap 143).

```bash
python dev_tools/gui_capture/capture.py \
    --config examples/mwir_leo_minimal.yaml \
    --config src/radiant/data/examples/landsat_oli2_all_bands.yaml \
    --config src/radiant/data/examples/air_to_air_irst.yaml \
    --out .impeccable/captures/baseline --theme both --welcome
```

- Runs under `QT_QPA_PLATFORM=offscreen`; needs the `gui` extra. macOS and
  Windows (no POSIX-only calls; paths via `pathlib`).
- Walks every stage in the strip and every visible tab; one PNG per view, per
  theme, at the requested window size (default 1600×1000).
- Renders every public figure of `ResultPlotNamespace` at 7.5×4.6 in, 130 dpi,
  under the matching `plot_theme`.
- Writes `capture.json` beside the images: RADIANT version and commit, Qt
  version, platform plugin, resolved font families, window size, the file
  list, and any figure that failed to render (a finding, not a silent skip).
- Uses an isolated `QSettings` INI per run so the operator's persisted theme
  and panel preferences are never read or written.

Two runs on the same commit, config, size and theme produce identical files;
that is the property the blind comparison depends on. Captures live in the
gitignored `.impeccable/captures/` tree; only downscaled contact sheets that a
committed report references are checked in.

Known limits: offscreen rendering uses Qt's software rasteriser, so native
macOS widget chrome (menus, scrollbars, focus rings) differs from an on-screen
run — the owner's live review covers what offscreen cannot.
