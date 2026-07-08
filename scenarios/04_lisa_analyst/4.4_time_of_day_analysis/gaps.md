# Scenario 4.4 — Gaps and Friction

Issues encountered building/running the diurnal time-of-day analysis.
Registry items are mirrored into `docs/tracking/gaps.md`.

---

## No new framework model required

The catalog listed 4.4 under "new physics models (time-varying scenario)",
but no new model was needed: the diurnal temperature profile is INPUT DATA
(a field-campaign product), and the chain already computes the in-band
signal for any surface temperature/emissivity. The "time axis" is a
scenario-level sweep over the input profile, run once per time step. This
is a Category D integration scenario, not a Category C new-model scenario.

---

## Framework gaps (mirrored to docs/tracking/gaps.md)

### Gap 52 — no first-class extended target-vs-background differential
The chain populates `contrast_e = signal_e − background_e` only in the
sub-pixel regime (and point-source). In the EXTENDED regime with a target
and a background temperature set, the `at_aperture_background` frame is not
built, so `contrast_e` collapses to the whole-scene `signal_e` and the
`contrast_snr` metric never nulls at thermal crossover — it reports the
absolute-scene SNR, not the target-vs-background contrast. A scenario that
needs the extended two-surface differential (diurnal washout, camouflage,
any "target patch on terrain") must construct it by running the two pixels
separately and differencing (this scenario, and 4.3). A first-class
extended differential — build the background reference frame whenever
`source.background.temperature` is set, not only in sub-pixel — would make
`contrast_snr` meaningful in the extended regime. Filed as Gap 52.

---

## Friction / lessons

- **`contrast_snr` in the EXTENDED regime is the whole-scene SNR, not a
  target-vs-background contrast** (see Gap 52). This is a genuine trap:
  the metric name suggests a differential, but in extended mode it does
  not null at crossover. Verified by inspecting `background_e` (= 0 in the
  extended path, `spectral_integration/stage.py:283`). The scenario builds
  the differential explicitly and documents why.
- **LWIR staring sensors saturate fast on warm scenes.** At the sensor's
  nominal 8 ms integration the well hit >99 % on a ~300 K scene, clipping
  the signal and killing the contrast. Dropped to 0.1 ms (~40 % well).
  This is the same well-saturation tuning seen in the T3 thermal scenarios
  (7.2/7.5/1.3/4.3) — LWIR extended scenes are integration-time-limited,
  and any diurnal/thermal scenario must size t_int to the *hottest* point
  of the sweep, not the mean.
- **The interesting physics is the emissivity offset**, not the crossover
  itself: because ε_target < ε_background, the radiance crossover (where
  detectability actually vanishes) is offset ~1 h from the temperature
  crossover. A scenario that only tracked ΔT = 0 would mis-time the
  washout.
