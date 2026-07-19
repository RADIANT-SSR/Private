# Warning-Free Launch & Evaluate — UX Cleanup Campaign

> **HISTORICAL** — Archived 2026-07-19. Completed by commit `ef8ed24` (merged
> fast-forward to `main`). Acceptance met: the 36-config sweep emits zero
> non-deprecation warnings except saturation; full suite green (4413 passed).
> Follow-up CU-170 tracks the 12 saturating scenario baselines.

**Status:** Complete — kicked off and completed 2026-07-19.

## Goal (owner bar)

*A valid, nominally-operating scenario should launch and evaluate with **zero**
warnings.* A warning must mean the configuration is wrong or the results are
untrustworthy (full-well saturation, an unphysical input) — **never** that a
model applied a documented, legitimate behavior (a clamp, a routing choice, a
temperature-inert dark rate). Informational conditions are carried as **structured
status** on the result and rendered **once** by a consumer, not re-emitted as a
`warnings.warn` / `logger.warning` on every evaluate.

This generalizes the CU-166 principle to the whole chain + the GUI launch.

## Empirical work-list (2026-07-19)

Evaluating the 36 shipped configs (`examples/` + `scenarios/*/*/inputs/*.gui.yaml`)
surfaced the warnings that actually fire on **valid** scenarios. These are the
targets — reclassify each as (a) genuinely-actionable warning (keep) or (b)
informational status (carry on the result, stop warning):

| # | Warning | Fires | Verdict | Fix |
|---|---|---|---|---|
| L | GUI launch: `qt.qpa.fonts … missing font family "IBM Plex …"` | every launch | (b) informational | CU-169/CU-103 — register bundled fonts + drop the unavailable lead family so Qt never resolves a missing family. **← first** |
| A | `SimpleAtmosphere: aerosol extinction is clamped to its 5.0 µm …` | 12 | (b) informational | Ångström clamp is a config property (band outside the fit) — carry as `stage_outputs["atmosphere"]` status, drop the per-evaluate `warnings.warn`. |
| B | `source._inferrer: extended terrestrial/airborne scene was configured with …` | 11 | (b) informational | routing/config notice — structured status on the source descriptor. |
| C | `DetectorStage: detector_temperature_K = … differs from dark_reference_temperature_K …, activation_energy = 0 …` | ~20 | (b) informational | CU-081 "temperature knob inert" is a config property — carry as `stage_outputs["detector"]` status; keep the actionable guidance in the field, not a per-evaluate warning. |
| D | `TargetDescriptor: T1Thermal applied to a spectral band overlapping the …` | 2 | (b) informational | routing notice — structured status. |
| — | `ReadoutStage: full well / ADC saturated`, `pixel saturated` | several | **(a) KEEP** | saturation clips the signal → results untrustworthy; genuinely actionable (owner-affirmed). Verify shipped scenarios that saturate intend to. |

The full 46-site inventory (`grep warnings.warn|logger.warning` across the stages)
is audited opportunistically as each area is touched; a site that never fires on a
valid config stays as-is.

## Pattern

For each (b): add a typed status field to the owning stage's `stage_outputs`
(a bool + a one-line message, or a small dataclass), remove the `warnings.warn` /
`logger.warning`, and update the GUI Messages/readout to render it once as a dimmed
note. Update the affected tests (they assert the warning today) and refresh any
scenario `expected.json` baseline that captured the warning. CHANGELOG under
`[Unreleased]`; the retired warning is a public-surface change (Rule 20/29).

## Acceptance

- Re-running the 36-config sweep emits **zero** non-deprecation warnings except
  genuinely-actionable ones (saturation on scenarios that intend it).
- GUI launches without the `qt.qpa.fonts` warning.
- Each converted condition is still discoverable (structured field + GUI note).
- No golden physics result changes (status is metadata, not a computed value).

## Progress

- [x] L — launch font warning (CU-169 done; CU-103 registration hook landed, .ttf bundling remains)
- [x] C — detector dark-reference-temp (CU-081) → structured status note on `stage_outputs["detector"]`
- [x] A — SimpleAtmosphere aerosol clamp → `logger.debug` (model-method; clamp is documented CU-088 behavior)
- [x] B — inferrer extended-scene notice → `logger.debug` (regime already surfaced as `regime_tentative`)
- [x] D — MWIR non-mixed advisory → `logger.debug` (descriptor variant already surfaced)
- [x] Saturation audit — the only warnings left on the 36-config sweep are saturation (full-well/ADC/pixel), the genuinely-actionable kind (owner-affirmed KEEP). Audit found **12 scenario baselines** clip at their shipped operating point → filed **CU-170** to re-center the accidental ones (kept-by-design ones stay + get documented).

**Acceptance met (2026-07-19):** the 36-config sweep emits **zero** non-deprecation
warnings except saturation (which is genuinely actionable). The reclassified
conditions stay discoverable — C as a stage-output status note (Outputs readout /
inspect), A/B/D as debug logs. No golden physics result changed.

> **Note on A/B/D representation:** these three are model-/inferrer-level notices
> whose operative fact is already surfaced on the result (the atmosphere model
> name, the source `regime_tentative`, the descriptor variant), so they became
> quiet-by-default `logger.debug` messages rather than new stage-output fields —
> a proportionate reading of "structured status" (not a per-evaluate warning;
> discoverable). C, the one that changes physics interpretation ("your temperature
> knob is inert"), got a first-class stage-output status note.
