# ADR-0005: Extended Target-vs-Background Contrast

**Date:** 2026-07-08
**Status:** Proposed

## Context

The metric `contrast_snr` is meant to report how well a target is
distinguished from its background. In the **sub-pixel** and **point-source**
regimes it is a genuine differential: `SpectralIntegrationStage` builds an
`at_aperture_background` reference frame and computes
`contrast_e = signal_e − background_e`, so the metric correctly falls to
zero when the target and background radiate equally (thermal crossover,
camouflage match, etc.).

In the **extended** regime it is not. Per **Decision #13** (ADR-0002), an
extended scene has no `BackgroundDescriptor` — the target *is* the adjacent
scene — so no `at_aperture_background` frame is built, and
`SpectralIntegrationStage` falls through to `contrast_e = signal_e`. The
`contrast_snr` metric therefore reports the **whole-scene SNR**, not a
target-vs-background contrast, and never nulls at crossover. This surfaced
as **Gap 52** while building scenarios 4.4 (diurnal thermal washout) and
4.3 (camouflage), both of which need an extended target-vs-background
differential and both of which work around it by running two extended
pixels (a target-filled and a background-filled scene) and differencing
them manually:

```
contrast_snr = (S_target − S_background) / √(N_target² + N_background²)
```

The obvious "just build the background frame in extended too" fix is blocked
by two landed decisions:

- **Decision #13** deliberately makes `BackgroundDescriptor = None` for
  extended scenes. The `background_e` it would produce feeds
  `compute_noise_budget(background_e=…)` — the background-shot noise term.
  Zeroing it is exactly what lifts the pinned Option-C anchor SNRs from
  ~5.5/6.5 to ~315.5/316.0. Re-introducing `background_e` for the contrast
  would revert that SNR architecture.
- **Decision #15** deprecates `source.background.*` for extended scenes: it
  describes *adjacent-scene* radiance only, and a user who sets it for an
  extended scene gets a `UserWarning` because the parameter was a
  "nomenclature-trap proxy for atmospheric path radiance," not a real
  adjacent background.

So the extended contrast is fundamentally a comparison of **two adjacent
extended scenes** (two neighbouring uniform pixels), which is a different
object from the "adjacent-scene-behind-a-sub-pixel-target"
`BackgroundDescriptor`. It needs its own representation, and that
representation must not resurrect the noise term Decision #13 removed nor
re-legitimise the parameters Decision #15 deprecated.

## Decision

Adopt **Option A**: add a **dedicated, explicitly-named contrast-reference
scene** for the extended regime, **decoupled from the noise budget**, and
define the extended `contrast_snr` as a two-pixel spatial differential.

Concretely:

1. **New input surface**, distinct from the deprecated `source.background.*`
   (avoiding the Decision-#15 trap): `source.contrast_reference.temperature`
   and `source.contrast_reference.emissivity` (thermal), extensible later to
   a reflectance/spectral path. It is optional; **absent ⇒ the extended
   `contrast_snr` is not emitted** (no behaviour change, goldens intact).
2. **Decoupled from noise (preserves Decision #13).** The contrast reference
   is used *only* to compute a reference-pixel in-band signal `S_b` (and its
   own pixel noise `N_b`) for the differential. It is **never** added to the
   target pixel's `background_e` / `compute_noise_budget`. The target
   pixel's SNR, NEDT, and all pinned anchors are therefore unchanged —
   `background_e` stays `0` for extended per Decision #13.
3. **Contrast-noise model = combined (√-sum).** The differential is between
   two independently-noisy adjacent pixels, so the noise is
   `√(N_target² + N_reference²)`, and

   ```
   contrast_e   = S_target − S_reference
   contrast_snr = |S_target − S_reference| / √(N_target² + N_reference²)
   ```

   This nulls exactly at the radiance crossover `ε_t·B(λ,T_t) = ε_r·B(λ,T_r)`,
   matching the manual two-pixel construction scenarios 4.3/4.4 already use.
4. **Scope:** thermal extended contrast first (the diurnal/camouflage use
   cases). Reflective extended contrast reuses the same input surface with a
   reflectance path when a scenario needs it.

`source.contrast_reference.*` is a new adjacent-scene *concept* that is
explicitly **not** the Decision-#15 `source.background.*` and explicitly
**not** the Decision-#13 `BackgroundDescriptor`; it is the "reference scene
in the neighbouring pixel" used solely for the extended contrast metric.

## Rationale

The extended contrast is a *spatial* differential between two uniform
scenes, not a *within-pixel* target-on-background composite. The three
photon-source concepts ADR-0002 carefully separated (adjacent-scene,
atmospheric path, downwelling sky) do not include "the uniform scene in the
next pixel over" — that is a fourth, metric-only concept, so it earns its
own explicitly-named surface rather than overloading an existing one.

Decoupling it from the noise budget is what makes the whole thing safe:
Decision #13's SNR lift is a *noise* decision (`background_e = 0`), while
Gap 52 is a *signal-differential* need. Keeping the reference out of
`compute_noise_budget` honours the former while delivering the latter.

The combined-noise model is the physically correct noise of a difference of
two independent measurements and is what the shipping workarounds already
assume, so accepting it makes the native metric agree with the validated
scenario results rather than introducing a third convention.

### Alternatives Considered

| Option | Pros | Cons |
|--------|------|------|
| **A. New decoupled contrast-reference input** (chosen) | Honours Decisions #13 and #15; goldens untouched (opt-in); matches the validated two-pixel workaround; clear intent | New public surface + a `ContrastReferenceDescriptor`-style concept; modest `SpectralIntegrationStage` work |
| **B. Re-purpose `source.background.*` for extended** | No new parameter | **Directly contradicts Decision #15** (which deprecated exactly this) and risks reviving the path-radiance double-count; the `UserWarning` would have to be removed |
| **C. Keep the two-pixel-differencing workaround** | Zero framework change; already ships (4.3/4.4) | `contrast_snr` stays misleading in the extended regime (reports whole-scene SNR); every scenario re-implements the differential; the metric name lies |
| D. Build `at_aperture_background` in extended and let it feed noise | Smallest code change | **Reverts Decision #13** — re-introduces background-shot noise, breaks the pinned Option-C anchor SNRs (315→5.5) |

## Consequences

- **Positive:** `contrast_snr` becomes a true target-vs-background
  differential in the extended regime, nulling at crossover; scenarios 4.3
  and 4.4 can drop their manual two-pixel differencing; the metric name
  finally matches its meaning across all regimes.
- **Positive:** Decision #13's SNR architecture and all pinned anchors are
  preserved (the reference is noise-decoupled; `background_e` stays 0 for
  extended).
- **Negative:** a new public parameter surface (`source.contrast_reference.*`)
  and a small `SpectralIntegrationStage` addition (a second in-band
  integration for the reference pixel) to build and test.
- **Neutral:** default behaviour is unchanged — the reference is opt-in, so
  no golden result moves unless a user sets it. Reflective extended contrast
  is deferred to a follow-on (same surface, reflectance path).

## References

- ADR-0002 — Option C source/atmosphere split (Decisions #13 and #15).
- `docs/tracking/gaps.md` — Gap 52.
- Scenarios `04_lisa_analyst/4.4_time_of_day_analysis` and
  `.../4.3_camouflage_effectiveness` — the two-pixel-differencing workaround
  this ADR makes native.
- `src/radiant/spectral_integration/stage.py` — the `contrast_e` /
  `background_e` construction this ADR extends.
