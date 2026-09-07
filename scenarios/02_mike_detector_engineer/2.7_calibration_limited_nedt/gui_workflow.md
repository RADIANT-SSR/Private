# GUI Workflow — Scenario 2.7 (Calibration-Limited NEDT)

Status note: the Calibration screen shipped with Gap 120 plan Phase 3 and is
merge-gated on the owner live review; this workflow describes the built screen.

## Steps
1. **Load the config.** File → Open on a saved YAML of this scenario's system
   (or build it: Optics/Detector/Spectral/Readout screens per the tables in
   `walkthrough.md`). Every value entered in its native unit via the shared
   field editor (cm for aperture, µs for integration time).
2. **Calibration screen** (chain strip → "Calibration", chip "NUC · bias";
   Ctrl+9). The scheme selector reads `none` — the screen is quiet and the
   note explains today's-behavior default.
3. **Turn the model on.** Edit *Scheme* → `two_point`. The contextual groups
   appear: set *Cal point (low)* = 290 K, *Cal point (high)* = 310 K,
   *Nonlinearity dispersion* = 1 %. (Until both cal points are set the
   evaluate reports an **advisory** beside the inputs — the calibration chip
   paints as the error site, no modal.) Set the pre-cal PRNU (2 %) on the
   Detector screen.
4. **Watch the floor.** The Outputs readout shows `nuc_residual_e` [e- RMS],
   `sigma_calibration_e`, the post-calibration `sigma_total_e`, and
   `calibration_nedt_K` — the floor's NEDT-equivalent. The noise-budget plot
   below gains the three residual bars. Edit the scene temperature on the
   Source screen (280 → 340 K) and watch the residual vanish at 290/310 K
   and dominate at 340 K (edit-and-watch).
5. **Drift.** Set *Time since cal* = 24 hours (entered and displayed in
   hours), *Gain drift rate* = 0.005 %/hour, *Offset drift rate* =
   720 e-/hour; the drift terms appear in the readout and the budget.
6. **Accuracy beside precision.** Set the cal-source group (ε = 0.98,
   ΔT = 0.5 K, Δε = 0.005). On the **Performance** screen the radiometric
   group now carries *Radiometric accuracy (radiance)* [%] and *(temperature)*
   [K] cards beside NEDT — precision and accuracy side by side, never one
   number. Pin both to the right rail to keep them visible while sweeping.

## GUI requirements exercised
- Calibration screen: scheme selector, contextual groups, sentinel words for
  unset cal points, hours display units, outputs readout, noise-budget plot.
- Advisory (not modal) routing for the mid-switch scheme state.
- Performance metric cards for the two accuracy metrics; right-rail pinning.
- Detector screen: pre-cal PRNU/DSNU entry (re-documented as pre-correction).
