# Figures — GUI usability audit (Rule 26b provenance)

Generator: the audit's scratch offscreen driver (Audit_Plan.md §2.1; `QT_QPA_PLATFORM=offscreen`, window 1400×900, production 200 ms debounce, modals intercepted and logged), not committed. Every figure is a `QWidget.grab()` of the real `RADIANTMainWindow` at the numbered step of the track named below, on commit `d5905846` of `main`. Regenerate by replaying the numbered steps in the referencing findings document.

| Figure | Track / step | Referenced by |
|---|---|---|
| `geometry_door_conflict.png` | T-B b3, step 16 (evaluate after a second viewing door) | `Findings_Bootstrap_Recovery.md` F-05, F-11, F-14 |
| `bootstrap_dock_blank.png` | T-A dialog path, geometry-first order, step 5 (after the fourth accepted edit) | `Findings_Bootstrap_Recovery.md` F-01, F-13 |
| `bootstrap_form_vs_dock.png` | T-A forms probe, step 3 (Geometry form after one accepted edit on a blank config) | `Findings_Bootstrap_Recovery.md` F-01, F-15 |
| `study_columns.png` | J-4.1, step 16 (Performance workspace after configuring aperture across three configurations) | `Findings_Journeys_P1_P4.md` J-4.1, F-22 |
| `small_window_performance.png` | T-H, 1024×640 window, Performance workspace | `Findings_Tracks.md` F-38 |

**Regeneration record (2026-09-19, phase 4).** The first four figures were regenerated at the same steps after the driver was found to be grabbing an unthemed window: `launch_gui` applies the light theme and the driver did not, so the phase-1/2 grabs showed Fusion chrome. The driver now applies `themes.LIGHT` exactly as `launch_gui` does. No finding depended on the chrome; the states shown are unchanged.
