# Installation and Launch

RADIANT is a Python package with a desktop application bundled in. Installing it means
installing Python, fetching the repository, making a virtual environment, and running one
`pip` command. Everything in this chapter works the same way on Windows and on macOS; where
the shell syntax differs, both forms are given.

Chapter 3 is the five-minute version — install, open the example, read the answer. This
chapter is the fuller treatment: what each step is for, which extras exist and what they
actually add, how to prove the install is sound, and what the common failures look like.

## 1. Prerequisites

| Requirement | Notes |
|---|---|
| Python **3.11 or 3.12** | 3.12 is the version the project is developed and tested on. The package metadata's floor is 3.11; check yours with `python --version`. |
| Git | to fetch the repository (RADIANT is distributed from a private repository, not from PyPI). |
| A graphical desktop session | only for the application. The library, the command line, and batch runs are fully headless. |
| MODTRAN | **not required.** Reference atmosphere data ships inside the package. MODTRAN is needed only to *generate new* atmosphere files. |

RADIANT needs no compiler, no CUDA, and no system Qt: every dependency, including the Qt
bindings, installs as a wheel from PyPI.

## 2. Get the code

```bash
git clone https://github.com/RADIANT-SSR/Private.git SSR_Tool
cd SSR_Tool
```

## 3. Create a virtual environment

A virtual environment keeps RADIANT's dependencies — a specific Qt, matplotlib, NumPy and
SciPy — out of your system Python.

**macOS (and Linux):**

```bash
python -m venv .venv
source .venv/bin/activate
```

**Windows (PowerShell):**

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

Your prompt now carries `(.venv)`. Every new terminal needs the activate command again;
forgetting it is the most common cause of "`radiant` is not recognized".

If PowerShell refuses to run the activation script, Windows' execution policy is blocking
it. Allow signed local scripts for your own account once:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

## 4. Install

```bash
pip install -e ".[dev]"
```

`-e` (editable) means the installed package points at your checkout, so pulling a newer
revision updates the tool without reinstalling. The quotes matter on macOS and on Windows
PowerShell alike — both shells would otherwise try to interpret the brackets.

**The desktop application is part of the base install.** The Qt stack (PySide6),
matplotlib, the console backend, and the workbook writer are ordinary dependencies, so a
plain `pip install -e .` already gives you a runnable `radiant gui`. The optional extras
add tooling around that core:

| Extra | Command | What it adds |
|---|---|---|
| *(none)* | `pip install -e .` | the library, the command line, and the desktop application |
| `dev` | `pip install -e ".[dev]"` | the developer toolchain — pytest, pytest-qt, mypy, ruff, import-linter, hypothesis, h5py |
| `scenarios` | `pip install -e ".[scenarios]"` | Excel-workbook and plotting support used by the shipped scenario run scripts |
| `gui` | `pip install -e ".[gui]"` | **a back-compatibility alias.** The GUI stack moved into the base dependencies; `radiant[gui]` remains a valid, no-op superset so older install instructions keep working |

Extras combine in one command — `pip install -e ".[dev,scenarios]"`. If you only intend to
*use* RADIANT rather than develop it, the bare `pip install -e .` is enough; the rest of
this manual assumes nothing from `dev`.

## 5. Verify the install

Four checks, in increasing depth. Run them in the activated environment from the repository
root.

**The executable is on PATH and reports its build:**

```bash
radiant --version
```

```text
radiant 0.2.0
  loaded from: /path/to/SSR_Tool/src/radiant
  git commit:  f1ae9933 (clean)
```

The `loaded from` line is worth reading rather than skipping: it tells you *which* checkout
this `radiant` resolves to, which is exactly the question when two clones or two
environments are in play. The commit line marks a modified working tree as `dirty`.

**The library imports:**

```bash
python -c "from radiant import Sensor; print('RADIANT import OK')"
```

**A shipped configuration resolves:**

```bash
radiant validate examples/mwir_leo_minimal.yaml
```

```text
Config OK: examples/mwir_leo_minimal.yaml
  218 parameters resolved.
```

`validate` performs every schema check, unit conversion, consistency-group resolution and
bounds test — but runs no physics. It is the cheapest possible proof that the installation
and the data files are intact.

**The chain runs:**

```bash
radiant run examples/mwir_leo_minimal.yaml
```

The output is the electron signal, all sixteen noise terms in e- RMS, the root-sum-square
total, and SNR. Chapter 3 walks through that output line by line; for now, a printed
`SNR:     1124.03` means a complete, working install.

## 6. Launch the application

```bash
radiant gui
```

Started with no argument, the application opens on its **welcome screen**: a grid of
mission-template cards, an always-present **Blank config** card, an **Open recent** list,
and a group of bundled worked examples. Nothing is evaluated yet, because nothing is loaded
yet.

Started with a path, it opens *on* that configuration and evaluates it immediately:

```bash
radiant gui examples/mwir_leo_minimal.yaml
```

Either form accepts a plain configuration file or a study file carrying a
`configurations:` section; the same reader handles both (chapter 8).

The mission templates are also reachable from the command line, which is a quick way to see
what ships:

```bash
radiant template list
```

```text
Name                          Description
------------------------------------------------------------------------------
aerial_vnir_imaging           Small-aircraft visible/NIR imager over a sunlit extended scene from 3 km.  [VNIR 0.4–0.9 µm · 3 km nadir · extended reflective scene]
airborne_lwir_surveillance    Wide-area thermal imaging of extended terrain from an 8 km platform.  [LWIR 8–12 µm · 8 km airborne · extended scene]
...
```

## 7. When something goes wrong

**`radiant: command not found` / `not recognised as a cmdlet`.** The virtual environment is
not active in this terminal. Re-run the activate command from §3. If it persists, the
install did not complete — re-run `pip install -e .` and read its output.

**An `ImportError` naming PySide6.** The Qt stack is missing, which normally means the
environment was built before the GUI moved into the base dependencies. `pip install -e .`
again; the error message names the same remedy.

**The application refuses to start over SSH or in a container.** Qt needs a display. Either
run it on the desktop machine, or work headlessly through the command line and the
scripting API, which need no display at all.

**A configuration is rejected on load.** RADIANT's errors are written to be acted on: each
one states *what* was rejected, *why* it is not acceptable, and *what to do*. Read the
action line before changing anything — the parameter named there is almost always the one
to change. Chapter 12 catalogues the common rejections.

**The numbers moved after an upgrade.** Check `radiant --version` for the new build, then the
release's change log, which records every change that moves a computed result and states the
direction and rough size.

## 8. Keeping it current

```bash
git pull
pip install -e ".[dev]"
```

The second command is needed only when dependencies changed; it is harmless otherwise. An
editable install picks up source changes without reinstalling, which is why the workflow is
`pull` first and `pip` only if something complains.
