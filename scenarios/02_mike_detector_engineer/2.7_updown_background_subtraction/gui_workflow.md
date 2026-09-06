# Scenario 2.7 GUI Workflow: Up/Down Counting Trade

How Mike runs the up-vs-up_down comparison in the GUI, and what the Phase 4
GUI increment must provide.

## Intended workflow

1. **Configure the point-source scene** — Source panel: 500 K target,
   swept background temperature; Geometry: 10 km range, 0.001 m² projected
   area; regime shows `point_source`.
2. **Readout panel**: Architecture `digital_counting` (Phase 3 group), then
   the **Counting mode** selector → `up_down`. The **reference group**
   appears: Reference source (`background_term` | `user_level`), Reference
   rate [e-/s] (shown only under `user_level`), Reference integration [s]
   ("equal to scene" when unset — ruling D7 default).
3. **Two configurations** — one per mode — in the configuration set;
   evaluate all; compare SNR / well fill / mechanism side by side.
4. **Read the saturation banner**: `up` shows `rollover` at hot backgrounds;
   `up_down` shows `differential_overflow` only when |ΔQ| exceeds the
   signed capacity.

## GUI requirements (Phase 4 increment)

- **Counting mode selector** in the Digital counting group, shown only
  under `digital_counting` (contextual-relevance, one level down from the
  Phase 3 pattern).
- **Reference group** shown only under `up_down`: reference source enum,
  rate (0.0 sentinel renders as "unset — required" under `user_level`),
  reference integration (0.0 sentinel renders as "equal to scene phase").
- **Advisory routing carries over**: a `user_level` reference without a
  rate is a mid-switch incompleteness (Messages rail, readout chip red,
  no modal), and `background_term` on an extended scene is an
  architecture-conflict advisory naming the `user_level` remedy.
- **Outputs readout additions**: `differential_e` [e-],
  `reference_charge_e` [e-], `reference_integration_s_used` [s], signed
  `counts` [-].

## Status

- Scripting API: fully supported (this scenario's runner).
- GUI: the Phase 4 increment implements the above; this file is the
  acceptance script for its live review.
