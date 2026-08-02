# Scenario 6.1 — GUI Workflow Requirements

How Dr. Chen would benchmark RADIANT against a datasheet in the GUI, and
what the GUI must provide. (Per the house rule that every scenario
documents its GUI requirements. The GUI is not yet built; this is a
requirements capture.)

---

## Dr. Chen's workflow in the GUI

1. **Load the datasheet.** Import `chen_lwir_datasheet.xlsx`. The GUI shows
   the published D*/NETD and the reference conditions, and auto-configures
   a sensor to those conditions.
2. **Run and convert.** The GUI runs the chain and shows the computed
   noise, then applies the D*/NEP/NETD converters to express the chain
   result as D* and NETD in the datasheet's units.
3. **Benchmark panel.** A side-by-side datasheet-vs-chain comparison for
   D* and NETD, with the tolerance band shaded and a PASS/FAIL verdict —
   the `fig1` view.
4. **Diagnose residuals.** When a residual exceeds tolerance, the GUI
   surfaces the noise-budget breakdown (shot/dark/read) so Dr. Chen can see
   whether a background-flux or QE mismatch drives it.

---

## MATLAB-like script/command window (standing GUI requirement)

Dr. Chen's core ask is an interactive command window (per the GUI vision
memo) where she can convert between figures of merit and benchmark:

```python
>>> from radiant.performance.detectivity import dstar_from_nep
>>> from radiant.performance.nep_electrons import nep_from_noise_electrons, integrating_bandwidth_hz
>>> s = load("chen_lwir_datasheet"); r = s.evaluate()
>>> noise = r.stage_outputs["spectral_integration"]["signal_e"] / r.metrics["snr"]
>>> nep = nep_from_noise_electrons(noise, 0.75, 10.0, 30e-6)
>>> dstar_from_nep(nep, (30e-4)**2, integrating_bandwidth_hz(30e-6))
1.795e11
```

Requirements this implies:
- **The converter functions callable from the window** with unit-labeled
  echo.
- **A one-call "chain → D*/NETD" helper** so Dr. Chen doesn't re-derive the
  noise → NEP → D* chain each time.
- **A benchmark-report object** (datasheet vs chain, residuals, verdict)
  she can tabulate or export.

---

## GUI-specific gaps

- The GUI should offer a **datasheet-benchmark mode**: load a datasheet,
  auto-configure, run, and produce the residual report — the researcher's
  core validation loop, packaging what this scenario does by hand.
- The **noise-budget breakdown** must be exposed per contributor so a
  failing benchmark is diagnosable (which noise term drives the residual).

## Interpolated-atmosphere availability

No bundled interpolated-atmosphere family serves this scene: 'midlat_summer_sensor_ladder' covers sensor_altitude 3 km to 40000 km; this scene asks for 1 km, below the family's runs. Switching **Atmosphere → Model** to `interpolated` therefore produces exactly one Messages-rail advisory saying so — not a sequence of refusals — and the scene stays on `atmosphere.model = 'simple'`, which serves any geometry.
