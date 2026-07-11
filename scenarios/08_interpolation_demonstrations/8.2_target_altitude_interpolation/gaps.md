# Scenario 8.2 — Gaps and Friction

---

## OPEN

Same registry-scope gaps as scenario 8.1 (hand-curated family registry,
no chain-ready helper) — not repeated here.

### Full-well saturation is a recurring, silent failure mode (escalated)
**Severity:** Medium (cross-scenario, not scenario-specific)
**Description:** this is the **third** scenario (after 6.1 and 6.2) to
lose time to full-well saturation silently producing a misleading
"no effect" result — the chain runs without error, `well_status` just
quietly says `clipped`, and two configs that should differ produce
identical SNR. Mirrored to `docs/tracking/gaps.md` as Gap 65 since this
is now a pattern, not scenario-local friction.
**Workaround:** always check `well_status` before trusting any
comparison where a metric looks suspiciously unchanged.
**Suggested fix:** `PerformanceStage` (or `ChainResult`) could emit a
`UserWarning` when `well_status != "unclipped"` and the run wasn't
explicitly configured to test saturation — visible by default, not
buried in `stage_outputs`.

---

## Friction / lessons

See walkthrough.md's "Friction / lessons" section — the saturation
story is the whole lesson here.
