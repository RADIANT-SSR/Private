# Scenario 8.2 — GUI Workflow Requirements

Same requirements as scenario 8.1's `gui_workflow.md` (identical tool,
different axis) — not repeated here. One addition specific to this
scenario:

---

## Additional requirement: well-fill warning

This scenario (and 6.1, 6.2 before it) hit full-well saturation
silently — the chain ran without error, just clipped, and produced a
misleadingly "atmosphere has zero effect" result until caught by
comparing two configs and noticing identical output. The GUI's run
panel should show `well_status` prominently (not just in
`stage_outputs`) whenever it isn't `unclipped`, ideally as a persistent
banner, not a dismissible toast — three scenarios in a row have lost
time to this exact failure mode.
