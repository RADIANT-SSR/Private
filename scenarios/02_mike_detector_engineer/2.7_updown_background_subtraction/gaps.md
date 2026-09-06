# Scenario 2.7 Gaps: Up/Down Counting — Background Subtraction Trade

## Summary
The up/down mode moves the saturation wall from the pedestal to the
differential: `up` counting saturates at ~290 K background (pedestal >
2¹⁴ × 2000 e- = 32.77 Me-) while `up_down` holds a background-independent
29.6 % fill of the signed 2¹³ × 2000 e- = 16.38 Me- capacity across the
whole 250–330 K sweep. The cost is the reference phase's own noise —
SNR ratio 0.75 at 250 K (between 1 and 1/√2, since only the background
terms double) — and above the crossover the usable-SNR advantage is 8.6×
and growing. Plan §7 anchors 4–5 (wrap arithmetic, two-phase Monte Carlo
with the √2 control) are covered by the Level-0 suite.

## Gap Closure Status
- Gap 117 Phase 4 (up/down counting, v1.1): exercised end-to-end by this
  scenario — signed differential, `differential_overflow` mechanism,
  `reference_shot` / doubled `packet_reset` / ×√2 counting-chain budget
  entries, D6 background-term reference, D7 parameterized phases.
- GUI increment (counting-mode selector + reference group): plan Phase 4;
  `gui_workflow.md` here is its live-review acceptance script.

## Issues found while building the scenario
- None blocking. Initial spec had a 0.05 m² "dim" target that at 50 ms was
  2.4×10⁸ e- and overflowed even the signed capacity — corrected to
  0.001 m² (4.86 Me-); a reminder that "dim point source" is a statement
  about electrons, not about area.
