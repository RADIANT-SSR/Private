# Scenario 1.1 — GUI Workflow Requirements

How Sarah would run this trade study in the GUI, and what the GUI must
provide. (Per the house rule that every scenario documents its GUI
requirements. The GUI is not yet built; this is a requirements capture.)

---

## Sarah's workflow in the GUI

1. **Import her colleague's tape7.** File → Import Atmosphere → MODTRAN
   tape7. The GUI runs `Tape7Reader`, shows the parsed transmittance
   curve, and flags (loudly, non-dismissable on first import) whether the
   file's header was name-matched or fell back to the positional
   assumption (CU-066) — Sarah needs to know which before trusting it.
2. **Digitize the InSb QE graph.** A curve-digitizer widget (click points
   on an imported image of the vendor PDF's graph) producing the same
   two-column CSV this script hand-built. This is a recurring need across
   scenarios (1.2's silicon curve, this one) — a generic "digitize a
   curve from an image" tool, not scenario-specific.
3. **Configure the system.** Aperture range, f/#, band, pixel pitch —
   standard parameter panel. A toggle switches the atmosphere source
   between "Parametric (SimpleAtmosphere)" and "Imported (tape7/tabulated)"
   so the comparison in this walkthrough is a one-click A/B, not two
   separate configs.
4. **Run the sweep.** Aperture sweep, both atmosphere sources, overlaid
   plots (NIIRS vs. aperture, detection range vs. aperture) — the `fig1`
   view.
5. **Regime warning surfaced inline.** When a target/PSF-size check like
   `_validate_psf_regime_consistency` would reject `point_source`, the
   GUI should suggest `sub_pixel` directly (with the numeric ratio shown)
   rather than a raw traceback — this scenario hit exactly that.
6. **Export the PPT summary table.** One-click export of the summary
   table (SNR/NEDT/NIIRS/range, both atmosphere sources) to a slide-ready
   format — the catalog's explicitly desired output, still a gap (see
   `gaps.md`).

---

## MATLAB-like script/command window (standing GUI requirement)

```python
>>> from radiant.atmosphere.modtran import Tape7Reader
>>> wl, tau, lp, gr = Tape7Reader("colleagues_tape7.tp7").to_radiant_units()
>>> s = load("sarah_maritime_mwir"); s.set("atmosphere.model", "tabulated")
>>> s.set("atmosphere.tabulated_transmittance_file", "tau.csv")
>>> r = s.evaluate()
>>> r.metrics["snr"], r.metrics["niirs"]
(1161.4, 4.68)
```

Requirements this implies:
- **`Tape7Reader` callable from the window** with the CU-066
  header-vs-fallback status visible in the echo.
- **A one-call "tape7 → tabulated atmosphere" helper** so Sarah doesn't
  hand-write the CSV round-trip this script does.
- **`detection_range_beer_lambert` callable directly**, with the
  extinction coefficient auto-derived from the current atmosphere state
  rather than hand-computed from `tau_atm`.

---

## GUI-specific gaps

- **Atmosphere-source A/B toggle** (parametric vs. imported) is the core
  ask this scenario surfaces — right now it's two separate config dicts
  in a script.
- **Curve digitizer** for vendor PDF graphs — recurring across scenarios,
  should be a shared GUI tool, not per-scenario tribal knowledge.
- **PPT/slide export** for summary tables — flagged by the original
  catalog entry, still open.
