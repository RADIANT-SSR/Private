# Scenario 2.6 GUI Workflow: DROIC vs Analog ROIC

How Mike would run this comparison in the RADIANT GUI, and what the GUI must
provide to support it.

## Intended workflow

1. **Load the analog baseline** — open the 2.5-style config (or set the
   system parameters in the Optics / Detector / Readout stage panels).
2. **Duplicate into a configuration set** — one configuration per ROIC
   (the multi-configuration selector; cap 12 is ample). Configuration A:
   `analog_well` (default). Configuration B: switch the Readout panel's
   **architecture selector** to `digital_counting` and fill in the counting
   group: counter depth 16 [bits], charge packet 4500 [e-], residue readout
   on, max count rate 5 [MHz] (entered in the user's chosen unit — GUI
   display-units rule).
3. **Sweep scene temperature** — 200–1500 [K] on the source panel, per
   configuration.
4. **Read the comparison** — SNR [-], NEDT [mK], dynamic range [dB], well
   fill [%] side by side in the performance columns; the saturation banner
   must show *which* mechanism clipped (`charge well` vs `dead_time` vs
   `rollover`), not just "saturated".

## GUI requirements this scenario imposes (Phase 3 of the plan)

- **Readout panel: architecture selector** (`analog_well` | `digital_counting`)
  with the counting parameter group shown **only** under `digital_counting`
  (contextual-relevance convention), and the analog well/ADC group hidden or
  disabled under counting — the validation rejects mixed specification, so
  the GUI must not invite it.
- **Saturation banner: mechanism-aware.** `readout.saturation_mechanism`
  (`rollover` | `dead_time` | `none`) joins `well_status` in the banner text.
- **Outputs readout additions:** `counts` [-], `effective_well_e` [e-],
  published well bound [e-] (the counting Q_sat), effective gain [e-/DN].
- **Unit-symmetric entry** for the counting group: packet in e- or ke-,
  max count rate in Hz/kHz/MHz per the display-units rule.

## Status

- Scripting API: fully supported today (this scenario's runner).
- GUI: **blocked on plan Phase 3** (readout panel counting group). The
  workflow above is the acceptance script for that phase's live review.
