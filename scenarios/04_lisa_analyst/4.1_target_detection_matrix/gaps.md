# Scenario 4.1 Gaps: Target Detection Matrix

Executed 2026-07-08 (Phase T3). Registry mirror: `docs/tracking/gaps.md`.
Prereqs: `radiant.api.batch.BatchRunner` + `radiant.io.target_library`
(commit 6492028).

## Gap Closure Status (catalog "Gaps revealed" list)

| # | Catalog gap | Status | Evidence |
|---|-------------|--------|----------|
| 1 | No Excel input parser for target libraries | **CLOSED** (6492028) | `radiant.io.target_library.load_target_library` reads the 12-row workbook into validated `TargetEntry` objects |
| 2 | No projected area calculator from dimensions | **CLOSED** (6492028) | `TargetEntry.projected_area_m2 = length × width` (derived, not an input column) |
| 3 | No detection range calculator | Not filed — bisection helper | Range-vs-zenith bisection at SCNR ≥ threshold (spherical Earth); a native `detection_range()` would wrap this loop, no new physics |
| 4 | No batch execution from scenario matrix definition | **CLOSED** (6492028) | `radiant.api.batch.BatchRunner` — cartesian grid, per-cell overrides, Rule 17 failure capture, `pivot()`; 144 cells, 0 failures |
| 5 | No Excel output with conditional formatting | Not filed — openpyxl at the scenario layer | Green/yellow/red fills written directly |
| 6 | No NIIRS output | **Already closed** | `result.metrics["niirs"]` (GIQE extrapolation caveat at these GSDs) |

## Detection Metric: SCNR, not SNR (design finding, shared with 1.3/4.3)

Pure noise-limited SNR ≥ 5 saturates for every cell (these sensors hold
SNR ≫ 5 across the whole swath), so it does not discriminate. Real
sub-pixel detection at 500 km is **clutter-limited**. The matrix therefore
uses SCNR = |contrast_e| / RSS(all noise incl. scene clutter), assembled
script-side because `result.metrics["snr"]` / `["contrast_snr"]` carry only
temporal noise — spatial scene clutter (`detector.clutter_sigma`) is a
noise TERM but is excluded from those metrics. A first-class
clutter-inclusive detection SNR would remove the script-side assembly
(same observation filed against scenarios 1.3/4.3; candidate registry gap
if a fourth scenario needs it).

## Sub-Pixel Contrast Sign (EE_box occlusion — physics, not a bug)

The chain forms sub-pixel contrast as
`contrast_e = ff·(L_target·EE_box − L_bg)`: the target's compact energy is
EE_box-weighted (its PSF spills to neighbouring pixels) while the uniform
in-pixel background it OCCLUDES is not. A deeply sub-pixel target (tiny
EE_box) is detected largely by the background DIP it punches, so
`contrast_e` can be NEGATIVE for a hot-but-dim target and its |·| ordering
runs opposite to a naïve ε·B(T)·A estimate (which omits EE_box). This is
correct radiometry; the `|contrast|` detection criterion is robust to the
sign. Absolute detection ranges carry the caveat (documented in the script
docstring and walkthrough). A multi-pixel matched filter would additionally
sum the target energy in the neighbours — a performance-model refinement
beyond this single-pixel SCNR.

## Execution-Time Bug Caught and Fixed (script-side)

**Unit double-conversion in the footprint calculation.** `Sensor.get(
"detector.pixel_pitch_x_um")` returns the CANONICAL value (metres), not µm,
despite the `..._um` parameter name. The first correct-looking run applied
an extra `× 1e-6`, making the IFOV 10⁶× too small and the pixel footprint
10¹²× too small — which silently capped every target's effective area to
~0. Caught by cross-checking the printed GSD (which read 0.0 m). Fixed to
use the canonical metres value directly. **Lesson for scenario authors:
`Sensor.get` is canonical units; read vendor values from the input
workbook (or use `Sensor.get_input`) when you need the display unit.**

## Non-Gap Observations

- **The deprecated-alias mechanism works end-to-end**: sensor C's YAML
  still carries the pre-Gap-12 `optics.cold_stop_efficiency`; RADIANT
  accepted it with one `DeprecationWarning` and mapped it to
  `optics.nearfield_fraction` — the config ran, loudly.
- **Off-nadir range uses the chain's own spherical-Earth slant range**
  (`radiant.core.geometry.slant_range_spherical_m`), the same function GSD
  uses — a flat-earth sec(θ) would disagree with the chain's geometry at
  the horizon (68° at 500 km).
- **BatchRunner's failure capture was exercised**: 0 cells failed, but the
  `error`-column path is unit-tested (`RadiantError` → recorded row).

---

## Real-data validation (2026-07-17)

A-block anchors rerank the condition axis: real MWIR τ spread across
the four climate cells is 1.3× where SimpleAtmosphere claimed 5×
(tropical_haze ~2.9× understated, arctic_clear ~1.35× overstated —
CU-161 water over-response). LWIR condition-insensitivity claim
weakens (real tropical LWIR carries ~22% continuum penalty). Target-
axis conclusions unaffected. See the walkthrough's validation note.
