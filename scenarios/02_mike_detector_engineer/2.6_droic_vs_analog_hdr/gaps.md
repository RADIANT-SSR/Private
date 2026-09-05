# Scenario 2.6 Gaps: DROIC vs Analog ROIC — Single-Frame HDR

## Summary
Same FPA, same optics, same 1 ms integration: the DROIC moves the single-frame
saturation wall from 300 K (analog 2 Me- well) to 400 K, delivers +21.1 dB
dynamic range at the matched 200 K point (76.3 → 97.4 dB), and matches the
analog chain within 0.8 % SNR / 0.3 mK NEDT in the unsaturated overlap — the
plan §7 cross-model consistency, visible in a workflow. The DROIC's governing
bound at this working point is the comparator dead-time ceiling
(5 MHz × 1 ms × 4500 e- = 22.5 Me-), 7.6 % of its 294.9 Me- counter capacity;
1500 K coverage remains out of reach without a faster comparator (≳ 90 MHz),
a larger packet, or the Phase 4 up/down operating mode.

## Gap Closure Status
- Gap 117 (digital-pixel readout): exercised end-to-end by this scenario —
  counting saturation with mechanism attribution, D2 DN semantics, D3
  read-noise reuse, counting noise budget entries, HDR dynamic range at the
  metric level. Delivered with plan Phase 2.
- GUI surface (architecture selector, counting group, mechanism-aware
  saturation banner): tracked as plan Phase 3; `gui_workflow.md` here is the
  acceptance script for its live review.

## Issues found while building the scenario
- None blocking. NEDT rows on clipped signals are printed with a footnote —
  the chain already warns and flags `well_status = "clipped"`, and the GUI
  banner requirement in `gui_workflow.md` carries the mechanism forward.
