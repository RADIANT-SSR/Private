# Scenario 6.2 — GUI Workflow Requirements

How Dr. Chen would run a model intercomparison in the GUI, and what
the GUI must provide. (Per the house rule that every scenario documents
its GUI requirements. The GUI is not yet built; this is a requirements
capture.)

---

## Dr. Chen's workflow in the GUI

1. **Import reference datasets.** File → Import Atmosphere, once per
   external tool (MODTRAN tape7, libRadtran output when that parser
   exists). Each import is tagged with its source so figures/tables
   can label series correctly.
2. **"Swap atmosphere model, keep everything else" toggle.** The
   catalog's own named gap — a dropdown (Parametric / Imported A / Imported
   B / ...) that re-runs the identical sensor config under each
   atmosphere source, exactly what this script does by hand with two
   config dicts.
3. **Six-profile grid view.** A small-multiples spectral overlay
   (the `fig1` view) plus a bar-chart summary (`fig2`) generated
   automatically once all profiles are imported/configured.
4. **Residual and per-band error panel.** Spectral residual
   (model A − model B) as its own overlay, with a numeric band-by-band
   breakdown table — the catalog's explicitly desired output, not yet
   built (see gaps.md).
5. **SNR-vs-transmittance decoupling callout.** Given this scenario's
   own finding (transmittance residuals don't track SNR residuals), the
   GUI should show both side by side by default, not just transmittance
   — otherwise a user could reasonably (and wrongly) assume a large τ
   mismatch means an equally large SNR mismatch.

---

## MATLAB-like script/command window (standing GUI requirement)

```python
>>> from radiant.atmosphere.modtran import Tape7Reader
>>> results = {}
>>> for profile, run_id in {"tropical": "A2", "us_standard": "A1"}.items():
...     wl, tau, lp, gr = Tape7Reader(f"{run_id}.tp7")  # real runs; .synthetic.tp7 fallback.to_radiant_units()
...     results[profile] = tau.mean()
>>> results
{'tropical': 0.6148, 'us_standard': 0.6775}
```

Requirements this implies:
- **Batch tape7 import** across a named set of profiles/runs, not
  one-file-at-a-time.
- **A residual/comparison object** (per-profile, per-band) callable and
  exportable, not just plotted.

---

## GUI-specific gaps

- **libRadtran parser** does not exist at all (see `gaps.md`) — the GUI
  requirement is the same "Import Atmosphere" flow as MODTRAN, once a
  parser exists.
- **Per-band error analysis** ("where does the simple model break
  down?", catalog's own phrasing) is not built — would need a spectral
  residual view with configurable band edges.
