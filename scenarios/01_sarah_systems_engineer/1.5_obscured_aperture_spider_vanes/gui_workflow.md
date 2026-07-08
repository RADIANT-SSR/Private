# Scenario 1.5 — GUI Workflow Requirements

How Sarah would trade a Cassegrain pupil in the RADIANT GUI, and what the
GUI must provide. (Per the house rule that every scenario documents its
GUI requirements. The GUI is not yet built; this is a requirements
capture.)

---

## Sarah's workflow in the GUI

1. **Load the telescope.** Import `sarah_cassegrain.xlsx`. The GUI draws
   the pupil (circle + central obscuration + spider arms) so Sarah sees
   the geometry she is trading.
2. **Compare apertures.** The GUI shows the metric table (SNR, EE_box,
   RER, MTF@Nyquist, Strehl) for unobstructed / obscured / obscured+spider,
   side by side, with the PSF core rendered for each (the diffraction-spike
   view).
3. **Sweep strut width.** A slider drives `spider_width_m`; the PSF spikes
   grow and the EE/RER/SNR curves update live.
4. **See the Strehl caveat.** The GUI flags that Strehl is unchanged and
   directs Sarah to EE/RER/SNR for the aperture-geometry cost — so she does
   not mis-judge the design by Strehl alone.

---

## MATLAB-like script/command window (standing GUI requirement)

Sarah's core ask is an interactive command window (per the GUI vision memo)
where she can trade pupil geometry and view the PSF:

```python
>>> s = load("sarah_cassegrain")
>>> s.set("optics.spider_width_m", 0.03)
>>> r = s.evaluate()
>>> r.metrics["ee_3x3"], r.metrics["rer"], r.metrics["snr"]
(0.6636, 0.4861, 80.7)
>>> imshow(log(r.optics.effective_psf))     # the diffraction spikes
>>> sweep = s.sweep("optics.spider_width_m", linspace(0, 0.05, 6))
>>> plot(sweep, x="optics.spider_width_m", y="ee_3x3")
```

Requirements this implies:
- **Direct PSF access + log-scale image display** from the command window
  (the effective PSF array is the deliverable Sarah wants to see).
- **A pupil-preview widget** that renders the amplitude mask from the
  obscuration + spider parameters before running the chain.
- **A metric-comparison table** across several configurations (not just a
  single-config read-out), since the trade is comparative.

---

## GUI-specific gaps

- The GUI should render the **pupil mask** (not just the PSF) so the
  geometry being traded is visible — this needs the amplitude mask exposed
  as an array (it exists internally in `make_pupil_amplitude`).
- Once an **arbitrary-pupil-mask** import lands (see `gaps.md` Gap 54), the
  GUI should let Sarah load a measured pupil image instead of only the
  parametric obscuration+spider shapes.
