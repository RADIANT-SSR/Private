# Script-Window Dependency Spike

**Status:** Complete (2026-07-12)
**Question:** Is the MATLAB-like script/command window — an embedded interactive
console sharing the live `Sensor` namespace, the standing owner requirement in
every `gui_workflow.md` — technically feasible, and what does it depend on?
**Verdict:** **Low risk — feasible today.** The shipped scripting API is already
the exact namespace such a window needs; the console-embedding pattern is
standard. Two dependency options, one recommendation.

---

## 1. What the window must do

Persona `gui_workflow.md` files converge on: a command window where the user
types Python against a live `sensor` object — query parameters, `evaluate()`,
`sweep()`, read metrics, and plot — with output (including inline plots) echoed
in place, history, and unit-labelled results. It is the highest-integration-risk
GUI element because it couples a REPL, the Qt event loop, matplotlib, and the
RADIANT session in one widget.

## 2. Dependency landscape (measured 2026-07-12)

| Package | Status | Role |
|---|---|---|
| `PySide6` | **present, 6.11.0** | Qt6 GUI toolkit (the chosen stack, `RADIANT_GUI_Architecture.md` §1) |
| `IPython` | missing | rich REPL kernel |
| `qtconsole` | missing | `RichJupyterWidget` — the embeddable console widget |
| `ipykernel` | missing | in-process kernel |
| `jupyter_client` | missing | kernel management |
| `matplotlib` | present | plotting (Agg headless verified; Qt backend for inline) |

Only PySide6 is installed. The rich console path needs four Jupyter packages
added to the (future) GUI extra in `pyproject.toml`; none conflict with the
core library, which stays Jupyter-free.

## 3. Core pattern is proven (headless)

The load-bearing question is not "can we embed a console" (routine) but "does
the shipped API expose a clean, mutable, live namespace a console can drive."
It does. A stdlib `code.InteractiveConsole` over `{"sensor": Sensor(...), "np":
np, "plt": plt}` was driven headlessly through a realistic session:

```python
result = sensor.evaluate()                 # SNR = 615.96
records = result.metric_records()          # 32 metrics, every one unit-labelled (Gap 71)
sweep = sensor.sweep("optics.aperture_diameter_m", [0.2, 0.3, 0.4], metric="snr")
# sweep.metric_values -> [410.6, 616.0, 821.3]
plt.plot(sweep.values, sweep.metric_values); plt.savefig(...)   # 17.5 kB PNG
```

Every command saw the same live `sensor` (namespace persists across pushes),
mutations took effect on re-`evaluate()`, and plotting worked. The Pre-GUI
Phase-1 surfaces are exactly what the window binds to: `Sensor.parameter_defs()`
(Gap 70) for tooltips/completion, `metric_records()` (Gap 71) for unit-labelled
echo, `progress=/cancel=` (Gap 72) for long sweeps, `save()/load()` (Gap 67) for
File-menu parity. **The API layer is ready; no backend gap blocks the window.**

## 4. Two architecture options

### Option A — qtconsole in-process kernel (recommended)

`qtconsole.RichJupyterWidget` backed by an `ipykernel` **in-process**
(`InProcessKernelManager`), whose `kernel.shell.push({"sensor": sensor, ...})`
shares the exact same Python objects with the GUI. Gives syntax highlighting,
tab-completion (drives naturally off `Sensor.parameter_defs()`), command
history, and **inline matplotlib** via the `inline`/`qt` backend. This is the
canonical "embed a Jupyter console in a Qt app" recipe.

- **Deps:** qtconsole, ipykernel, jupyter_client, ipython (GUI extra only).
- **Sharing:** in-process kernel → the widget and the app hold the *same*
  `sensor`; edits in the GUI param tree are visible in the console and vice
  versa (both call `sensor.set(...)`).
- **Compat note:** qtconsole selects the Qt binding via `qtpy`; confirm
  qtconsole ≥ the version that supports PySide6 6.11 at install time (qtpy
  abstracts PyQt5/6/PySide2/6 — low risk, but pin-test).

### Option B — stdlib `code.InteractiveConsole` in a `QPlainTextEdit`

Zero new heavy deps (the proof above used exactly this). A `QPlainTextEdit`
captures input; `console.push()` runs it over the shared namespace; stdout is
redirected into the widget. Simpler and dependency-light, but no
highlighting/completion/rich-inline output — a plainer window. Good fallback if
the Jupyter stack is undesirable.

## 5. Risks and mitigations

| Risk | Mitigation |
|---|---|
| A long `evaluate()`/`sweep()` blocks the Qt event loop (in-process kernel runs on the GUI thread) | Use the **Gap 72 `progress=/cancel=` hooks** and run sweeps on a worker thread, or use an **out-of-process** kernel (loses live object sharing → would need to re-send params). In-process + worker-thread is the pragmatic path; single `evaluate()` is 0.22 s so only sweeps/MC need it. |
| Inline matplotlib needs backend wiring | qtconsole's `inline` backend is standard; select it in the kernel startup. Option B renders to a separate Qt canvas or saves to file. |
| PySide6 6.11 vs qtconsole binding | qtpy indirection; pin and smoke-test at install. Low. |
| Namespace pollution / user `del sensor` | Re-inject on reset; treat the console namespace as recreatable, `sensor` as owned by the app. |

## 6. Recommendation

Adopt **Option A** (qtconsole + in-process ipykernel) for the production
script window; keep **Option B** as the zero-dep fallback for a minimal build.
Add the four Jupyter packages to a `gui` extra in `pyproject.toml` when GUI work
starts (not before — the core library must stay Jupyter-free). Seed the kernel
namespace with `{sensor, result, np, plt}` and wire tab-completion to
`Sensor.parameter_defs()`. No RADIANT-side work is required to make the window
possible — the Pre-GUI Phase-1 hardening already shipped every surface it binds
to. The spike **de-risks GUI kickoff**: the highest-integration-risk element has
a proven pattern and a bounded dependency list.
