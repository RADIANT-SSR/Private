# Sweeps and Trade Studies in the Application

A single evaluation answers "what does this design do". A trade study answers "what should this
design be". The application carries four surfaces for the second question, and they answer
four different shapes of it.

| Surface | Where | The question it answers |
|---|---|---|
| **Sweep** | Run ▸ Run Sweep… | how does one metric move as one or two parameters vary continuously |
| **Solve** | Tools ▸ Solve for Parameter… | what value of X gives metric Y |
| **Compare Config Files** | Tools ▸ Compare Config Files… | how do these N designs, each in its own file, stack up |
| **Configuration set** | the configuration bar (chapter 8) | how do these N named variants of *one* design stack up |

Two more menu items — **Monte Carlo…** and **Batch Run…** — do not run anything themselves;
they hand you a prefilled script (§4).

## 1. Run ▸ Run Sweep…

A real dialog, not a scaffold. It runs 1-D and 2-D sweeps on a worker thread and plots the
result in place.

### 1.1 Setting one up

**Parameter** is a dropdown of every float parameter in the schema. Choosing one does two
things you should notice:

- the **Start** and **Stop** boxes seed to ×0.5 and ×1.5 of the session's current value,
  clamped to the parameter's bounds — so a sweep starts life bracketing where you actually are,
  not at an alphabetical parameter's 0 → 1;
- the unit chip beside the boxes reads `[m] · now 0.3`, naming both the unit you are typing in
  and the value you are sweeping around, so you never have to remember it from the main window.

Then **Points**, and optionally **Log spacing**.

**You type in the parameter's input unit**, the conversion happens once at the dialog boundary,
and — this is the part that matters when you read the plot — the axis is drawn in the same unit
you typed. Entry and display are symmetric here as everywhere else; no mental arithmetic stands
between what you entered and what the figure shows.

Ticking **Second parameter (2-D grid)** reveals an identical second block. A 2-D sweep needs two
*different* parameters; naming the same one twice is refused before anything runs.

**Metric** chooses what is plotted. The list is the live metric set from the last result, so
it reflects the metric groups you actually have switched on (chapter 9, §2).

### 1.2 Running it

**Run sweep** validates the whole specification against the schema bounds **before** launching,
so a bad endpoint fails at 0/N with the offending value named, rather than at point 1 of 121.

While it runs, the status line counts:

```text
Running… 37/121
```

**Cancel run** stops it, and the dialog is honest about what that means:

```text
Cancelled at 37/121. No partial results (sweep API contract).
```

There are no partial results on cancel — that is the sweep API's contract, and the dialog says
so rather than presenting a truncated curve as data. Closing the dialog mid-run does not orphan
the worker either: it requests the cancel, stays open with an honest status line, and closes
itself when the worker settles.

**The sweep runs against a clone of the live sensor.** Your session configuration is never
mutated by a trade study.

### 1.3 Reading and keeping the result

A 1-D sweep draws a marked line; a 2-D sweep draws a color mesh with a labeled colourbar —
drawn on the real coordinate arrays, so a log-spaced axis places its cells correctly rather
than smearing them across a linear extent. Both axes and the colourbar carry their units.

```text
Done — 121 points.
Done — 11×11 grid.
```

**Copy as script** puts a complete, runnable reproduction block on the clipboard:

```python
values1 = np.linspace(0.15, 0.45, 13)  # optics.aperture_diameter_m in m (input unit, as entered)
sweep = sensor.sweep("optics.aperture_diameter_m", values1, metric="snr", keep_results=True)
```

The emitted endpoints are the canonical values the sweep actually ran, in the unit you typed,
so pasting the block into the scripting window (`Ctrl+Shift+P`) reproduces the plotted numbers
exactly. This is the intended graduation path: configure the trade where it is easy to
configure, then take it to a script when it needs to be repeatable, parameterized, or part of
something larger.

The last-run specification persists across dialog openings, so a loop you run several times a
week reopens already configured.

The completed sweep is retained on the window: **File ▸ Export Sweep CSV…** enables, and the
XLSX workbook export picks the sweep up as a sheet. Every column of that CSV carries its unit in
the header — `optics.aperture_diameter_m [m]`, `nedt_K [K]`, `snr` bare when dimensionless — and
a code or flag metric says so (`niirs_extrapolated [0/1 flag]`, `sampling_regime_code [code]`)
so it cannot be read as a value; cells are plain numbers, and the axis column reads the values
you typed.

## 2. Tools ▸ Solve for Parameter…

The inverse of a sweep. Pick the free parameter, the target metric and the value you want, and
a bracket in the parameter's input unit; a Brent iteration runs on a worker thread against a
clone. Success reports the solution with its unit, the metric value actually achieved, and how
many evaluations it took, and offers **Apply solution** — one edit to the live sensor, only if
you ask for it.

A target that is not bracketed by your endpoints fails with both endpoint metric values shown,
so you can widen the bracket knowingly. A metric that is flat over the bracket cannot be
bracketed at all, and the message says that rather than returning an arbitrary root.

## 3. Tools ▸ Compare Config Files…

This compares the current configuration against N **config files on disk**. The wording is
deliberate: since configuration sets landed, a bare "configuration" means a member of one
study, and *those* are compared by the Performance columns (chapter 8, §5) and by the scripting
`ConfigurationSet.compare`. This dialog is the file-level comparison, and the two are unrelated
mechanisms.

Add files; each column evaluates once, sequentially, on a worker thread with progress. The
result is an aligned matrix: union-of-metrics rows with their registry units, per-metric deltas
against the baseline column you choose, and conservative best-per-metric marks rendered bold
with a ✓. A metric absent from one config shows an em dash — never a zero.

Every column evaluates on a **clone**; the session sensor is never mutated.

This is also the atmosphere A/B surface, and it falls out for free: save the current config,
flip one parameter, add the saved file, and read the two columns side by side.

## 4. Monte Carlo and Batch Run — script scaffolds

**Run ▸ Monte Carlo…** and **Run ▸ Batch Run…** do not open a dialog. Each opens the scripting
window with a prefilled, runnable script in a fresh editor tab, and the status bar says so:

```text
Monte Carlo scaffold opened in the script editor — edit and Run
```

That is a deliberate design choice rather than an unfinished feature: both of these are
*programs*, not forms. A Monte-Carlo run is a distribution over tolerances plus whatever
post-processing you want; a batch is a cartesian product of labeled axes plus a per-cell
function that returns whatever you care about. Wrapping either in a dialog would fix choices
that need to stay open, so the GUI teaches the API instead and hands you a working starting
point bound to the sensor already on screen.

The Monte-Carlo scaffold is **seeded from your session's tolerances**. If you have annotated
parameters, they are listed as comments at the top of the block:

```python
# Monte Carlo scaffold (Run → Monte Carlo…)
# toleranced: detector.qe_value ~ gaussian{'std': 0.02}
mc = sensor.monte_carlo(n_trials=500, seed=42)
for name in mc.metric_names:
    p5 = mc.percentile(name, 5)
    p50 = mc.percentile(name, 50)
    p95 = mc.percentile(name, 95)
    print(f"{name}: p5={p5:.4g}  median={p50:.4g}  p95={p95:.4g}")
# mc.to_csv("mc_trials.csv")  # per-trial export
```

If you have set none, it says that and shows you how — both the scripting call and the
Tolerance section in any parameter editor dialog.

The Batch scaffold is a `BatchRunner` skeleton with two labeled axes, an `evaluate` function,
and a pivot at the end; edit the axes to yours and run it.

## 5. Which surface for which trade

The choice is usually obvious once the question is phrased properly.

| If the answer is… | use |
|---|---|
| a curve or a surface, and no single point deserves a name | **Sweep** |
| a single number you want the model to find | **Solve** |
| a table of a handful of named designs that share almost everything | a **configuration set** (chapter 8) |
| a table of designs that live in separate files | **Compare Config Files** |
| a distribution — "what does manufacturing scatter do to my NEDT" | the **Monte Carlo** scaffold |
| a matrix over several discrete axes with custom per-cell outputs | the **Batch** scaffold |

Two rules of thumb worth keeping. **If you find yourself naming sweep points, you want a
configuration set.** **If you find yourself adding a thirteenth configuration to trace out a
trend, you want a sweep.**

## 6. Taking it further

Everything above has a scripting equivalent, and the scripted forms are where a trade study
becomes repeatable: sweeps and 2-D grids, Monte-Carlo tolerance analysis, sensitivity ranking,
config-file comparison, and building a configuration set programmatically. The recipes — with
the interpretation notes for SNR-versus-aperture, the noise budget, and MTF terms — are in
the repository's trade-studies guide, and worked end to end in Volume IV's trade-study
cookbook.

The **Copy as script** button in the sweep dialog is the bridge between the two: the GUI is
where a trade is *shaped*, and a script is where it is *kept*.
