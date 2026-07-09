# Scenario 6.5 — GUI Workflow Requirements

How Dr. Chen would run the emissivity-sensitivity study in the RADIANT GUI.
(Per the house rule; the GUI is not yet built.)

## Workflow

1. **Load the retrieval config** (`chen_retrieval_config.xlsx`): true T/ε,
   assumed-ε sweep, band, NEDT.
2. **Jacobian panel:** the GUI shows ∂L/∂ε and ∂L/∂T at the operating point
   and the derived dT/dε.
3. **Retrieval sweep:** a slider on assumed ε updates the retrieved T live
   against the true-T line and a shaded ±NEDT band; the T-error-vs-ε-error
   plot overlays the first-order Jacobian law.
4. **Read the tolerance:** the GUI reports the NEDT-equivalent ε uncertainty
   (how well ε must be known) — the design-driving number.

## MATLAB-like command window

```python
>>> from radiant.performance.temperature_retrieval import (
...     band_planck_radiance, retrieve_temperature_K, temperature_jacobian, emissivity_jacobian)
>>> band = linspace(8, 12, 400)
>>> L = 0.95 * band_planck_radiance(300.0, band)
>>> retrieve_temperature_K(L, 0.90, band)     # assume wrong ε
303.34
>>> -emissivity_jacobian(300, band) / temperature_jacobian(300, 0.95, band)  # dT/dε
-64.4
```

Requirements: retrieval + Jacobian callable from the window; a sweep
primitive over assumed ε; a "known-to" tolerance read-out (ε uncertainty
for a target T accuracy).

## GUI-specific gaps

- A **retrieval-tolerance panel** (invert a target T-accuracy into the
  required ε knowledge) would package the design-driving output.
- Bias-vs-noise should be visually distinguished (systematic ε bias vs
  random NEDT) so users don't expect frame-averaging to fix the bias.
