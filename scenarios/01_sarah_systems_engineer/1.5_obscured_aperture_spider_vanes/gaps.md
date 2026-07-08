# Scenario 1.5 — Gaps and Friction

Issues encountered building/running the obscured-aperture / spider-vane
scenario. Registry items are mirrored into `docs/tracking/gaps.md`.

---

## RESOLVED during this scenario

### Spider-vane pupil masking (was the primary gap, and an aspirational-doc drift)
The catalog flagged "no arbitrary pupil mask (spider vanes)". RADIANT_Optics.md
§3.3 *described* spider arms (parameters `n_spiders`, `spider_width_m`,
`spider_angle_deg` and an `A_clear` subtraction) but the code never
implemented them — an aspirational-doc drift. **Implemented as
`optics.n_spiders` / `optics.spider_width_m` / `optics.spider_angle_deg`**
(committed 36286e7), matching the doc's parameter names and formula.
Struts enter the shared pupil amplitude mask, so they degrade both the PSF
and the MTF (Rule 4) from one edit, and subtract from the radiometric
clear area. The doc §3.3 was updated from "deferred/aspirational" to the
implemented behavior. 10 Level-0 tests including a byte-identical no-vane
regression guard (all 496 optics + 10 golden tests unchanged).

The central obscuration (`optics.obscuration_ratio`) and Strehl
(`ee`/`strehl` metrics) already existed — so 1.5 needed only the spider
struts, not new PSF/MTF/Strehl machinery.

---

## Framework gaps (mirrored to docs/tracking/gaps.md)

### Gap 54 — no arbitrary/measured pupil mask (only parametric shapes)
The pupil supports circular aperture + central obscuration + radial spider
arms, all parametric. There is no path to load an arbitrary measured pupil
mask (e.g. a segmented aperture, a non-circular primary, a wavefront-sensor
pupil image) as a 2-D array. The `make_pupil_amplitude` grid could accept
an injected mask. Filed as Gap 54. Low-medium effort; not blocking (the
parametric shapes cover the common Cassegrain/refractor cases).

---

## Friction / lessons

- **RADIANT_Optics.md §3.3 was aspirational.** The doc fully specified
  spider arms (names, formula) but the code had them "deferred". This is
  exactly the aspirational-doc failure mode the architecture rules warn
  about. The fix aligned code to the existing doc spec (rather than
  inventing new names), then updated the doc's status from deferred to
  implemented — a doc-and-code lock-step correction (Rule 20).
- **Strehl is blind to aperture geometry — by design.** A designer
  trading obscuration/vane geometry must look at EE_box, RER, and SNR, not
  Strehl (which isolates WFE; the reference PSF shares the aperture
  geometry, so obscuration/vanes cancel). The scenario surfaces all four
  metrics to make this explicit.
- **MTF@Nyquist is non-monotonic** with obscuration/thin struts (they
  redistribute rather than uniformly lower the MTF). EE and RER are the
  robust degradation indicators for a pupil-geometry trade.
