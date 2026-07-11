# Scenario 8.2 — Gaps and Friction

---

## OPEN

Same registry-scope gaps as scenario 8.1 (hand-curated family registry,
no chain-ready helper) — not repeated here.

### Full-well saturation is a recurring, silent failure mode (escalated) — FIXED
**Severity:** Medium (cross-scenario, not scenario-specific)
**Status:** FIXED 2026-07-11 (Gap 65 in `docs/tracking/gaps.md`)
**Description:** this was the **third** scenario (after 6.1 and 6.2) to
lose time to full-well saturation silently producing a misleading
"no effect" result — the chain ran without error, `well_status` just
quietly said `clipped`, and two configs that should differ produced
identical SNR.
**Resolution:** `ReadoutStage` now warns on both well and ADC clips
(also a latent Rule 17 violation). The fix immediately caught a second
live instance in this very scenario: the config was still
**ADC**-saturating (gain 16 e-/DN × 14-bit caps at ~2.6e5 e-); gain
corrected to 200 e-/DN (~FWC/2^14). Root-cause note: this scenario's
own blanket `warnings.simplefilter("ignore")` had been suppressing the
pre-existing CU-061 saturation warning too — the script now re-enables
saturation warnings through the blanket filter.

---

## Friction / lessons

See walkthrough.md's "Friction / lessons" section — the saturation
story is the whole lesson here.
