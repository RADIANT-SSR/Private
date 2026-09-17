# Running the Examples

RADIANT ships its worked examples in two forms, and this volume uses both. Some
examples are **configurations you open** — a YAML file that the desktop GUI loads,
evaluates, and lets you drive by hand. Others are **programs you run** — a Python
script that builds a sensor, sweeps it, and prints its results to the terminal. The
two modalities describe the same physics through the same public API; they differ
only in who is holding the controls.

This chapter is the setup instruction for every chapter that follows: what to
install, where the files live, and the two commands that open an example.

---

## 1. What ships

| Kind | Where | Opened with |
|---|---|---|
| Reference configs | `examples/*.yaml` | GUI, CLI, or `Sensor.from_yaml` |
| Example programs | `examples/scripts/*.py` | `python examples/scripts/<name>.py` |
| Scenario exercise baselines | `scenarios/NN_persona/N.M_slug/inputs/<slug>.gui.yaml` | GUI (`File → Open YAML`) |
| Scenario run scripts | `scenarios/NN_persona/N.M_slug/scripts/run_<slug>.py` | `python run_<slug>.py` |
| Flagship-mission configs | `scenarios/09_flagship_missions/9.N_*/**.yaml` | GUI, CLI, or the API |

Two of those rows deserve a note.

**The exercise baselines are generated, not hand-written.** Each scenario was built
as a *backend* test case: a run script that assembles a `Sensor` in Python, sweeps
it, and writes a workbook. A Python script is not something `File → Open` can
consume, so `scenarios/tools/emit_gui_yaml.py` imports each runner's validated
config factory and serialises `Sensor.to_yaml()` into `inputs/<slug>.gui.yaml`,
alongside a headline-metric snapshot in `inputs/<slug>.gui.expected.json`. Opening a
baseline in the GUI therefore reproduces the same numbers the backend scenario
validated — that equality is a gate (`scenarios/tools/verify_gui_yaml.py`), not a
hope.

**The baselines pick one portable point of each trade.** A scenario's run script may
sweep aperture from 0.15 m to 0.60 m against a staged MODTRAN tape7; its baseline
freezes a mid-range aperture and, where the tape7 is not committed, the `simple`
parametric atmosphere. The baseline is for *driving the GUI*; the full sweep still
lives in the run script.

---

## 2. Installing what the examples need

RADIANT needs **Python 3.11 or 3.12**. From a clone:

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\Activate.ps1
pip install -e ".[dev]"
```

The optional extras each unlock a different part of this volume:

| Extra | Installs | Needed for |
|---|---|---|
| `gui` | PySide6, matplotlib, qtconsole, openpyxl | the GUI chapters (chapter 2) |
| `scenarios` | openpyxl, matplotlib | scenario run scripts (vendor-format workbooks, figures) |
| `dev` | pytest, mypy, ruff, import-linter, hypothesis, h5py | running the test suite |

```bash
pip install -e ".[gui,scenarios]"
```

`gui` is a back-compatibility alias: the Qt stack moved into the base dependencies,
so a plain `pip install radiant` already ships the desktop application. Installing
the extra explicitly still works and costs nothing.

The six programs in `examples/scripts/` need **no extra at all** except
`aperture_sweep.py`, which saves a figure and therefore needs matplotlib (present in
both `gui` and `scenarios`).

Verify the install, and check *which* RADIANT you just got — a stale editable install
pointing at another checkout is the single most common source of "my edit did
nothing":

```bash
radiant --version
```

---

## 3. Where inputs and outputs live

Inputs are committed; results generally are not.

- **Committed:** every `.yaml` config, every `.csv`/`.xlsx` vendor-format input,
  every figure a `walkthrough.md` actually references (each with a provenance line
  in the folder's `outputs/MANIFEST.md`).
- **Not committed:** `*_results.xlsx` workbooks, ad-hoc plots, and the built PDF
  manuals. These are regenerate-on-demand and gitignored.

A scenario folder has a fixed shape:

```
NN_persona/
  N.M_scenario_slug/
    inputs/      # vendor-format data, the .gui.yaml baseline, the metric snapshot
    scripts/     # run_<slug>.py (the trade study), gui_console_<slug>.py
    outputs/     # committed figures + MANIFEST.md; workbooks are regenerated
    walkthrough.md    # what was run and what the numbers mean
    gaps.md           # every RADIANT limitation the scenario hit
    gui_workflow.md   # what the GUI must provide to support this workflow
```

`examples/` is flatter and deliberately so: its scripts carry their explanation in
the module docstring and in their own printed output, not in a companion
walkthrough. When chapter 3 quotes a script's commentary, it is quoting text the
script itself prints.

---

## 4. Modality one — open a baseline in the GUI

```bash
radiant gui                                     # empty, pick a file from inside
radiant gui examples/mwir_leo_minimal.yaml      # straight onto a config
```

or, once the window is up, `File → Open YAML…`.

The GUI reads **every** document through one reader. A plain config opens as a
single session; a file carrying a `configurations:` section opens as the whole
study, with a configuration selector across the top and one metric column per
configuration. You do not choose between two open commands — the file's content
decides, and the status bar says which happened
(`Opened oli2_all_bands_study.yaml — 9 configurations (B1_CA, B2_Blue, …);
displaying B1_CA`).

Loading evaluates immediately. Editing any parameter marks the view stale and
re-evaluates after a short debounce; `Evaluate` (F5) forces it. Everything the
window shows — metric cards, MTF curves, noise tables — comes from the last
completed run, so a figure in this manual always shows an *evaluated* window.

To confirm a baseline landed correctly, compare the headline cards against the
scenario's `inputs/<slug>.gui.expected.json`. A mismatch is a GUI wiring bug, not a
physics result.

## 5. Modality two — run a script

From the repository root:

```bash
python examples/scripts/basic_evaluation.py
```

If you are working in a git worktree, or in any checkout that is not the one
`pip install -e .` registered, put the checkout's sources first so you exercise
*those* edits:

```bash
PYTHONPATH=src python examples/scripts/basic_evaluation.py
```

The same config runs from the command line, which is the fastest way to get one
number without writing anything:

```bash
radiant run examples/mwir_leo_minimal.yaml
radiant run examples/mwir_leo_minimal.yaml --set optics.aperture_diameter_m=0.50
radiant run scenarios/09_flagship_missions/9.4_landsat_oli2_snr/oli2_all_bands_study.yaml \
    --configuration B4_Red
```

Scenario run scripts are launched from inside their own folder, because they resolve
their vendor inputs relative to themselves:

```bash
cd scenarios/01_sarah_systems_engineer/1.1_mwir_maritime_surveillance/scripts
python run_mwir_maritime_surveillance.py
```

---

## 6. Three things that will otherwise surprise you

**Warnings are results.** RADIANT raises a `UserWarning` when the physics stops
meaning what you think it means — most often full-well saturation. Several examples
in this volume print such warnings on purpose, and the saturated points are part of
the lesson. A clipped pixel's SNR no longer responds to the scene, so a saturated
configuration reads as *insensitive*, not as high-performing. Read the warning before
reading the number it decorates.

**The spectral grid is an input.** Chain results depend on how finely the band is
sampled. `Sensor.from_yaml(path, wavelength_points=300)` and
`radiant run --wavelength-points 300` set it; the GUI's status bar reports what was
used (`Evaluated — 500 wavelength points`). Two runs that disagree in the fourth
digit usually disagree about this, not about physics.

**The regime is decided for you, once.** Whether a target is treated as extended,
sub-pixel, or a point source is classified in the optics stage and read unchanged by
every stage after it. You influence it through the scene you describe — target extent,
range, aperture — never by asserting it downstream. Each worked example names the
regime it lands in, because almost every surprising number in this volume traces back
to that one classification.

---

## 7. What the next two chapters do

Chapter 2 drives the GUI: six short task-oriented walkthroughs, each with numbered
steps and screenshots of the real application, from building a sensor out of nothing
to comparing nine configurations side by side.

Chapter 3 drives the API: the six programs in `examples/scripts/`, each with the
listing excerpt that matters, the output it actually produced, and the physics that
output is showing you.
