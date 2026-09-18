# Trade-Study Cookbook

A trade study is a question of the form *"how does this number move when I change that
one?"* — and RADIANT answers six distinct shapes of that question with six distinct
tools. Choosing the wrong one is the most common way to spend an afternoon producing a
plot nobody can act on.

This chapter is the recipe card for all six. Each entry says **when to reach for it**,
gives a short scripted recipe with its **real output**, names the **GUI route** where
one exists, and points at the case study earlier in this volume that uses it in anger.
It is deliberately not the reference: the project's Trade Studies Guide
holds the full API surface, the configuration-set
model, and the result-interpretation notes, and this chapter does not repeat them.

## The worked configuration, and three habits

Every recipe below runs against `examples/mwir_leo_minimal.yaml` — a 0.30 m f/4
telescope at 8 km altitude looking straight down at a 300 K, $\varepsilon = 0.95$
extended scene through a mid-latitude-summer atmosphere, on an 18 µm-pitch focal plane
with a 2 Me- well. Every output block is what the recipe actually printed, run from the
repository root as `PYTHONPATH=src python <script>.py`.

Three habits apply to all six, and each of them has cost someone a re-run:

- **Declare the envelope before you run.** A tolerance, a threshold, or a pass band
  chosen *after* the numbers are on screen is not an analysis result. Put
  `TOLERANCE_PCT`, the SNR floor, or the acceptable NEdT in the script as a named
  constant at the top.
- **Read the warnings.** Every trade tool in RADIANT evaluates the full chain, and the
  chain warns rather than silently clipping. A sweep whose curve flattens may be
  showing you diminishing returns — or a saturated well, which is a different
  conclusion entirely. Recipe 1 walks straight into that case on purpose.
- **Nothing mutates your session.** `sweep`, `sweep_2d`, `solve_for`, `monte_carlo`
  and `sensitivity` all evaluate against copies of the parameter set, and the GUI runs
  its dialogs against a `Sensor` clone. You can trade freely from a configured session
  without disturbing it.

---

## Recipe 1 — The 1-D sweep

### When to reach for it

One continuous axis, one metric, and you want the **shape** of the relationship: where
the knee is, where the requirement is crossed, whether the curve is linear or square-
root. If you find yourself naming individual sweep points, you want a configuration
set instead (see the Trade Studies Guide); if you want the crossing point rather than
the curve, skip to Recipe 3.

### The recipe

```python
import numpy as np
from radiant.api import Sensor

sensor = Sensor.from_yaml("examples/mwir_leo_minimal.yaml")

sweep = sensor.sweep(
    "optics.aperture_diameter_m",          # dot-path, canonical unit (m)
    np.linspace(0.10, 0.60, 6),            # the axis values [m]
    metric="snr",                          # a metrics key, or a callable
)

for diameter_m, snr in zip(sweep.values, sweep.metric_values, strict=True):
    print(f"  D = {diameter_m:.2f} m   SNR = {snr:8.2f} [-]")

hit = sweep.at_metric_threshold(1000.0)    # first point at or above the threshold
print(f"first point with SNR >= 1000: {hit}")
sweep.to_csv("aperture_sweep.csv")         # tidy per-point export
```

```
  D = 0.10 m   SNR =   374.54 [-]
  D = 0.20 m   SNR =   749.31 [-]
  D = 0.30 m   SNR =  1124.03 [-]
  D = 0.40 m   SNR =  1414.17 [-]
  D = 0.50 m   SNR =  1414.17 [-]
  D = 0.60 m   SNR =  1414.17 [-]
first point with SNR >= 1000: (0.30000000000000004, 1124.0273378815184)
```

**Read the curve before believing it.** The first three points scale exactly linearly
with diameter — which is the shot-noise limit's signature, since signal grows as $D^2$
and shot noise as $D$. The last three are identical to the digit, and *that* is not
physics: the run warns

```
pixel saturated: signal 5.054e+06 e- clipped to 2.000e+06 e- — the well
capacity remaining after the non-signal pedestal
```

The flat top is the 2 Me- well filling, not an aperture knee. A sweep that crosses a
saturation boundary is answering a different question on either side of it; either
shorten the integration time along with the aperture, or stop the axis before the
clip.

Useful extras on `SweepResult`: `param_name` and `metric_name` (what was swept, what
was measured), `results` (the full `ChainResult` per point, unless you passed
`keep_results=False`), `sweep[metric_key]` to pull a *second* metric out of the
retained results without re-running, and `n_workers=N` on the call for parallel
evaluation.

### From the GUI

**Run → Run Sweep…** is the same call behind a dialog. Pick the parameter from the
schema-driven list (every float `ParameterDef`), type Start / Stop / Points **in the
parameter's own input unit** — the chip beside the field shows that unit and the
session's current value — optionally tick *Log spacing*, pick the metric, and Run. The
range seeds itself at ×0.5 / ×1.5 of the current value, clamped to the schema bounds,
so an opened dialog is already bracketing where you are. The curve plots in the units
you typed; a progress bar tracks done/total and Cancel aborts cleanly (there are no
partial results on cancel, by API contract, and the dialog says so). **Copy as script**
puts a runnable reproduction of the sweep on the clipboard — the canonical values that
actually ran — which is the intended graduation path from dialog to script.
**File → Export Sweep CSV…** writes the retained result.

### Seen in anger

The **MWIR maritime surveillance** case study sweeps aperture from 0.15 m to 0.45 m at
fixed f/2.5 and reports the result that matters: SNR does not move at all while NIIRS
climbs from 3.53 to 5.13. Aperture bought resolution, not signal — the kind of finding
that only a swept curve makes obvious. The **wavefront-error budget** case study sweeps
$0 \to 0.25$ waves RMS over thirteen points and reads the first grid point past each
degradation threshold, with a note on the difference between sweep resolution and
interpolated crossing.

---

## Recipe 2 — The 2-D sweep

### When to reach for it

Two continuous axes whose **interaction** is the question. Use it when you suspect the
optimum in one parameter depends on the other — aperture against integration time,
pitch against focal length — and a pair of 1-D sweeps would mislead by holding the
wrong thing fixed. Two coarse axes beat one fine axis: an $8 \times 4$ grid is 32
evaluations and shows you the whole surface.

### The recipe

```python
from radiant.api import Sensor

sensor = Sensor.from_yaml("examples/mwir_leo_minimal.yaml")

grid = sensor.sweep_2d(
    "optics.aperture_diameter_m", [0.20, 0.30, 0.40],              # [m]
    "spectral_integration.integration_time_s", [0.001, 0.005],     # [s]
    metric="snr",
)

print(grid.grid.shape)     # (3, 2) — axis 1 varies down the rows
print(grid.grid.round(1))
grid.to_csv("aperture_dwell_grid.csv")
```

```
(3, 2)
[[ 335.   749.3]
 [ 502.6 1124. ]
 [ 670.2 1414.2]]
```

The grid is indexed `[i1, i2]` — first parameter down the rows, second across the
columns — and `to_csv` writes it in long form with both axis values per cell, which is
the shape a plotting library or a spreadsheet wants. Note the bottom-right cell: 0.40 m
at 5 ms is the saturated corner from Recipe 1, so the surface's apparent plateau is a
well limit rather than an optimum. On a real 2-D study, plot the saturation mask
alongside the metric.

### From the GUI

The same **Run → Run Sweep…** dialog. Tick **Second parameter (2-D grid)** and a second
parameter/Start/Stop/Points block appears, each with its own unit chip and log-spacing
option. The result renders as a heatmap with both axes and the colour bar unit-suffixed
in the units you typed. Progress, cancel, **Copy as script** and CSV export behave
exactly as in the 1-D case.

### Seen in anger

No tier-1 case study runs a `sweep_2d` — which is itself informative. When the two axes
are *discrete and labelled* (three atmospheres × six targets) the right tool is Recipe
6's batch matrix, and that is what the **target detection matrix** case study uses. The
2-D sweep earns its place when both axes are continuous and the answer is a surface,
not a table of named cells.

---

## Recipe 3 — Solve for a parameter

### When to reach for it

You already know the answer you need — SNR = 50, NEdT = 30 mK, NIIRS = 4.5 — and want
the parameter value that produces it. A sweep can only tell you which of its grid
points crossed; a solve gives you the crossing itself, usually in fewer evaluations
than a coarse sweep would take.

### The recipe

```python
from radiant.api import Sensor
from radiant.api.solve import SolveBracketError

sensor = Sensor.from_yaml("examples/mwir_leo_minimal.yaml")

try:
    solution = sensor.solve_for(
        "optics.aperture_diameter_m",   # the free parameter
        250.0,                          # the target metric value [-]
        bounds=(0.05, 1.0),             # bracket, in the parameter's input unit [m]
        metric="snr",
    )
except SolveBracketError as exc:
    print(f"target not bracketed: {exc}")
else:
    print(f"{solution.param_name} = {solution.solution:.5f} m")
    print(f"achieved {solution.metric_name} = {solution.achieved:.3f} [-] "
          f"in {solution.n_evaluations} evaluations")
```

```
optics.aperture_diameter_m = 0.06678 m
achieved snr = 250.000 [-] in 9 evaluations
```

Three things to know. The solve is **Brent root-finding on the forward model**, so the
metric must be monotone-ish and *actually vary* over the bracket: a plateaued metric
cannot be bracketed, and the error says so. `SolveBracketError` reports **both endpoint
metric values**, which is usually enough to see whether you bracketed the wrong side or
the wrong parameter. And `solution.result` carries the full `ChainResult` at the
solution, so you can check the rest of the chain — saturation, MTF, noise split — at the
point the solver landed on, rather than trusting one metric in isolation.

### From the GUI

**Tools → Solve for Parameter…**. Pick the free parameter, the target metric and its
value, and the bracket in the parameter's input unit. The Brent iteration runs on a
worker thread against a **clone**, so the session is untouched until you decide
otherwise; success reports the solution with its unit, the achieved metric, and the
evaluation count, and offers **Apply solution** — one `sensor.set` on the live sensor.
A non-bracketing target surfaces the API's actionable error, both endpoint values
included, inline in the dialog.

### Seen in anger

No tier-1 case study drives the solver — the closest is scenario 7.4's cold-stop study,
whose walkthrough records that the inverse-solver gap it was written against was closed
by `Sensor.solve_for`, and whose own inversion parameter has since been removed. The
live demonstrations are scenario 7.2 (radiometric calibration verification) and the
solver's own unit tests. In practice the solver's most valuable use is exactly the one
this recipe shows: converting a requirement into a design value without building a
sweep around it first.

---

## Recipe 4 — Monte Carlo tolerance analysis

### When to reach for it

Your inputs are not single values but distributions — a coating transmission with a
±5 % spread, a QE that varies across a lot, an aperture with a manufacturing tolerance
— and the question is not "what is the SNR" but **"what fraction of built units meet
the requirement"**. Reach for this when a specification has to survive manufacturing,
not just design.

### The recipe

```python
from radiant.api import Sensor

REQUIRED_SNR = 1050.0          # declare the bar BEFORE the run

sensor = Sensor.from_yaml("examples/mwir_leo_minimal.yaml")
sensor.set_tolerance("optics.aperture_diameter_m", "gaussian", std_fraction=0.02)
sensor.set_tolerance("detector.qe_value", "gaussian", std=0.03)

mc = sensor.monte_carlo(n_trials=64, seed=42)

print(f"mean  {mc.mean('snr'):.2f} [-]")
print(f"std   {mc.std('snr'):.2f} [-]")
print(f"5th percentile  {mc.percentile('snr', 5):.2f} [-]")
print(f"P(SNR >= {REQUIRED_SNR:.0f}) = {mc.probability_of_exceeding('snr', REQUIRED_SNR):.2f}")
print("correlation with inputs:", {k: round(v, 2) for k, v in mc.correlation("snr").items()})
mc.to_csv("mc_trials.csv")     # one row per trial
```

```
mean  1122.04 [-]
std   27.99 [-]
5th percentile  1071.41 [-]
P(SNR >= 1050) = 0.98
correlation with inputs: {'detector.qe_value': 0.75, 'optics.aperture_diameter_m': 0.76}
```

Four distributions are available — `gaussian`, `uniform`, `truncated_gaussian`,
`log_normal` — and the keyword arguments are the distribution's own (`std`,
`std_fraction`, `mean`, and so on). **The seed is part of the result**: the same seed
and trial count reproduce the run exactly, which is what makes an MC number quotable in
a review. Sixty-four trials is a demonstration size; a percentile you intend to defend
wants several hundred, and the cost is linear.

The correlation column is the part people under-use. Here the two toleranced inputs
land at 0.75 and 0.76 — i.e. neither dominates, and tightening only one of them will
not move the distribution much. When one input correlates at 0.9 and the rest at 0.2,
you have found the tolerance worth paying to tighten.

### From the GUI

There is no Monte Carlo dialog. **Run → Monte Carlo…** opens the scripting window with
a **prefilled scaffold**: the tolerances already set on the session appear as comments
at the top (or, if none are set, a one-line example of how to set one), followed by the
`monte_carlo` call, the summary statistics, and a commented `to_csv` export. That is a
deliberate design choice — a tolerance study has too many defensible shapes to put
behind a form, so the GUI hands you the script and gets out of the way. Tolerances set
through the GUI's ± badges persist into the config file's `_radiant.tolerances` block,
so a scaffolded script picks up the session's declared spreads.

### Seen in anger

`examples/scripts/tolerance_analysis.py`, walked in the **Scripting Examples** chapter
of this volume: three toleranced parameters, 50 trials, and the statistics printed with
units. No tier-1 case study runs a Monte Carlo — the eight were chosen for breadth of
persona, and tolerancing is a specialist's tool that a systems engineer reaches for
once a programme rather than weekly.

---

## Recipe 5 — Sensitivity ranking

### When to reach for it

Before any of the above. You have twenty parameters and no idea which three matter, and
you want a defensible ordering to spend the rest of the study on. A one-at-a-time
sensitivity is cheap — two evaluations per parameter — and it produces exactly that
ordering.

### The recipe

```python
from radiant.api import Sensor

sensor = Sensor.from_yaml("examples/mwir_leo_minimal.yaml")

ranking = sensor.sensitivity(
    metric="snr",
    param_names=[
        "optics.aperture_diameter_m",
        "detector.qe_value",
        "spectral_integration.integration_time_s",
        "optics.transmission_scalar",
    ],
    delta_fraction=0.01,      # ±1 % perturbation
)

for entry in sorted(ranking.entries, key=lambda e: abs(e.sensitivity), reverse=True):
    print(f"  {entry.param_name:45s} {entry.sensitivity:+.3f}")
print(f"nominal {ranking.metric_name} = {ranking.entries[0].metric_nominal:.2f} [-]")
```

```
  optics.aperture_diameter_m                    +1.000
  detector.qe_value                             +0.500
  optics.transmission_scalar                    +0.500
  spectral_integration.integration_time_s       +0.500
nominal snr = 1124.03 [-]
```

**The sensitivity is normalised**: a value of 2.0 means a 1 % change in the parameter
produces a 2 % change in the metric, and a negative value means the metric falls as the
parameter rises. It is therefore directly comparable across parameters with wildly
different units, which is the whole point.

This particular ranking is also a validation of the chain in miniature. In the
shot-noise limit $\mathrm{SNR} \propto D\sqrt{\eta\,\tau\,t_{int}}$ — aperture with
exponent 1, and quantum efficiency, transmission and integration time each with
exponent $\tfrac{1}{2}$. The numerical ranking recovers 1.000, 0.500, 0.500, 0.500
exactly. When a sensitivity comes back at an exponent you cannot explain from the
physics, that is worth a second look before it is worth a design decision.

Each `SensitivityEntry` also carries `nominal_value`, `metric_nominal`, `metric_plus`
and `metric_minus`, so the two-sided behaviour is inspectable — useful where a
parameter is near a boundary and the response is asymmetric. Omit `param_names`
entirely and the analysis runs over the toleranced parameters, or over all float
parameters if none are toleranced.

### From the GUI

None. Sensitivity is a scripting-only surface; run it from the scripting window
(**Tools → Scripting Window**, Ctrl+Shift+P, or Command+Shift+P on macOS), where `sensor` is already bound to
the loaded session.

### Seen in anger

Scenario 6.3 (noise-model verification) closes by ranking parametric sensitivities
against hand calculations. Among the tier-1 case studies, the **InSb versus HgCdTe**
shootout does the same job structurally — it establishes which noise term dominates
before arguing about detector choice, which is the sensitivity question asked in the
noise budget's own language.

---

## Recipe 6 — The batch matrix

### When to reach for it

Two or more **discrete, labelled** axes whose cells you want in a table with the labels
attached: three sensors × four targets × two atmospheres. Unlike a sweep, each cell can
change several parameters at once, the axis labels survive into the output, and a cell
that fails is *recorded* rather than aborting the run — which matters when a corner of
the matrix is physically invalid.

### The recipe

```python
from radiant.api import Sensor
from radiant.api.batch import BatchRunner

CFG = "examples/mwir_leo_minimal.yaml"

axes = [
    ("aperture", {"25 cm": {"optics.aperture_diameter_m": 0.25},
                  "35 cm": {"optics.aperture_diameter_m": 0.35}}),
    ("dwell",    {"2 ms": {"spectral_integration.integration_time_s": 0.002},
                  "5 ms": {"spectral_integration.integration_time_s": 0.005}}),
]

def evaluate(sensor, labels):
    """One cell: the sensor arrives with this cell's overrides applied."""
    result = sensor.evaluate()
    return {"snr": result.metrics["snr"], "nedt_mK": 1e3 * result.metrics["nedt_K"]}

runner = BatchRunner(
    base_config={},                                   # unused here — the factory loads the YAML
    axes=axes,
    sensor_factory=lambda cfg: Sensor.from_yaml(CFG),
)
batch = runner.run(evaluate)

print("failed cells:", batch.n_failed)
for row in batch.rows:
    print(f"  {row['aperture']:>6} x {row['dwell']:>5}: "
          f"SNR {row['snr']:8.1f} [-]   NEdT {row['nedt_mK']:6.1f} [mK]")
```

```
failed cells: 0
   25 cm x  2 ms: SNR    592.3 [-]   NEdT   47.4 [mK]
   25 cm x  5 ms: SNR    936.7 [-]   NEdT   30.0 [mK]
   35 cm x  2 ms: SNR    829.3 [-]   NEdT   33.8 [mK]
   35 cm x  5 ms: SNR   1311.4 [-]   NEdT   21.4 [mK]
```

`batch.pivot("snr", rows="aperture", cols="dwell")` turns the same rows into a
briefing table — `{row_label: {col_label: value}}`, with failed cells as `None` — which
is one call away from a rendered matrix. The last axis varies fastest; axis names
become result columns, so `"error"` is reserved.

The two structural properties worth designing around: the `evaluate` callback returns
**whatever columns you want** (a derived metric, a detection range, a pass/fail flag —
not just chain metrics), and a `RadiantError` inside a cell is captured into that row's
`error` column so the batch completes. A matrix that silently dropped its invalid cells
would misreport coverage; this one reports `n_failed` and keeps the row.

### From the GUI

**Run → Batch Run…**, like Monte Carlo, opens the scripting window with a prefilled
`BatchRunner` skeleton — two labelled axes, an `evaluate` function, the run, a `pivot`
and the failed-cell count — for the same reason: the shape of a batch is the analysis,
and it belongs in a script.

### Seen in anger

The **target detection matrix** case study is this recipe at full scale: twelve targets ×
four atmospheres × three sensors — 144 cells — with a bisection search for detection range inside
each cell's `evaluate`, early exits at nadir and at the swath edge, and `pivot` used to
build the briefing tables directly. Read it for how much analysis can live inside the
cell callback.

---

## Choosing between them

| Your question | Reach for | Chapter |
|---|---|---|
| "What does the curve look like?" | 1-D sweep | Recipe 1 |
| "Do these two parameters interact?" | 2-D sweep | Recipe 2 |
| "What value hits my requirement?" | `solve_for` | Recipe 3 |
| "What fraction of units will pass?" | Monte Carlo | Recipe 4 |
| "Which parameters matter at all?" | Sensitivity ranking | Recipe 5 |
| "Fill in this table of named cases." | `BatchRunner` | Recipe 6 |
| "Compare a handful of named designs." | Configuration set | Trade Studies Guide |

Two boundaries are worth restating because they are the ones people cross by accident.
A **configuration set** is for up to twelve *named* designs that differ in several
parameters each, save as one document, and appear side by side in the GUI's comparison
view — if you are naming sweep points, that is what you want. A **batch matrix** is for
the Cartesian product of labelled axes evaluated into a tidy table — if you are adding a
thirteenth configuration to trace a trend, you want a sweep instead.

And whichever you reach for: the numbers it prints are only as good as the
configuration underneath. The flagship-validation chapter says exactly how far that
underneath has been checked.
