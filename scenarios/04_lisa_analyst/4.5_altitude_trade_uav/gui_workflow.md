# Scenario 4.5 — GUI Workflow Requirements

How Lisa would run the microbolometer UAV altitude trade in the GUI, and
what the GUI must provide. (Per the house rule that every scenario
documents its GUI requirements. The GUI is not yet built; this is a
requirements capture.)

---

## Lisa's workflow in the GUI

1. **Load the vendor spec.** Import `lisa_microbolometer_uav.xlsx`. The GUI
   shows the microbolometer NETD and, via the converters, its NEP and D* —
   so Lisa can compare an uncooled (≈10⁹ Jones) unit to a cooled one.
2. **Set the target.** Enter the target size, ΔT, and background
   temperature.
3. **Run the altitude trade.** A slider or full sweep drives altitude; the
   GUI live-plots the apparent contrast `ff·ΔT·τ_atm` against the
   `threshold·NETD` floor, marking the sub-pixel altitude and the detection
   ceiling.
4. **Diagnose the ceiling.** The GUI shows fill fraction and τ_atm
   separately so Lisa sees the ceiling is resolution- (sub-pixel-) driven,
   not atmosphere-driven.

---

## MATLAB-like script/command window (standing GUI requirement)

Lisa's core ask is an interactive command window (per the GUI vision memo):

```python
>>> from radiant.performance.nep_netd import nep_from_netd
>>> from radiant.performance.detectivity import dstar_from_nep
>>> from radiant.performance.nep_electrons import integrating_bandwidth_hz
>>> # vendor NETD → D*
>>> nep = nep_from_netd(50e-3, dp_dt)          # dp_dt from the chain dS/dT
>>> dstar_from_nep(nep, (17e-4)**2, integrating_bandwidth_hz(16e-3))
1.34e9
>>> # altitude ceiling
>>> ceiling(target=1.0, dT=4.0, netd=50e-3, ifov=486e-6)
8.5   # km
```

Requirements this implies:
- **NETD ⇄ NEP ⇄ D\* converters callable from the window**, with the chain
  supplying `dP/dT`.
- **A sub-pixel apparent-contrast helper** (fill fraction × ΔT × τ_atm) and
  a **threshold-crossing finder** that returns the detection ceiling.
- **Per-effect breakdown** (fill fraction vs τ_atm) so the ceiling's cause
  is visible.

---

## GUI-specific gaps

- The GUI should let a detector be specified **by NETD** (vendor mode), not
  only by dark/read/QE — and auto-convert to NEP/D* for display. This is
  the uncooled-detector workflow this scenario exercises.
- A **detection-ceiling readout** (apparent ΔT vs threshold·NETD across an
  altitude sweep) should be a first-class panel for UAV ISR planning.

## Interpolated-atmosphere availability

No bundled interpolated-atmosphere family serves this scene: 'midlat_summer_sensor_ladder' covers sensor_altitude 3 km to 40000 km; this scene asks for 2 km, below the family's runs. Switching **Atmosphere → Model** to `interpolated` therefore produces exactly one Messages-rail advisory saying so — not a sequence of refusals — and the scene stays on `atmosphere.model = 'simple'`, which serves any geometry.
