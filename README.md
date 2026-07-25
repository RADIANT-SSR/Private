# RADIANT

First-principles electro-optical (EO) sensor performance modeling framework.

Predicts SNR, NEDT, NIIRS, MTF, and detection range for space-based and airborne EO
sensors from a physics-based signal chain:

```
geometry → source → atmosphere → optics → platform → spectral integration → detector → readout → performance
```

---

## Quick Start

### 1. Prerequisites

- **Python 3.11 or 3.12** (3.12 recommended) — check with `python --version`
- **Git**
- MODTRAN is **not** required to run — reference atmosphere fixtures ship with the repo.
  It is only needed to generate *new* atmosphere files.

### 2. Get the code

```bash
git clone https://github.com/RADIANT-SSR/Private.git SSR_Tool
cd SSR_Tool
```

(Requires access to the private `RADIANT-SSR` repository.)

### 3. Create and activate a virtual environment

A virtual environment keeps RADIANT's dependencies isolated from your system Python.

**macOS / Linux:**

```bash
python -m venv .venv
source .venv/bin/activate
```

**Windows (PowerShell):**

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

Your shell prompt now shows `(.venv)`. Re-run the activate command in any new terminal.

### 4. Install

```bash
pip install -e ".[dev]"
```

This installs RADIANT in editable mode (your source edits take effect immediately) with
the developer toolchain (pytest, mypy, ruff, import-linter).

The **desktop GUI is included in the base install** — `pip install radiant` ships a
runnable `radiant gui` (the PySide6/matplotlib/console stack is a base dependency as of
2026-07-24). Optional extras:

| Extra          | Install                        | Adds                                              |
|----------------|--------------------------------|---------------------------------------------------|
| `gui`          | `pip install -e ".[gui]"`      | Back-compat alias — the GUI stack is already in the base install |
| `scenarios`    | `pip install -e ".[scenarios]"`| Excel workbook + plotting support for scenario runs |

Combine them: `pip install -e ".[dev]"`.

### 5. Verify

```bash
radiant --version
radiant --help
python -c "from radiant import Sensor; print('RADIANT import OK')"
```

### 6. Run your first evaluation

RADIANT ships a reference MWIR config — a 300 K target viewed from 8 km through a
0.30 m aperture:

```bash
radiant run examples/mwir_leo_minimal.yaml
```

You'll see the signal, the full noise budget (per term, in e⁻ RMS), and SNR.

The same thing from Python:

```python
from radiant import Sensor

sensor = Sensor.from_yaml("examples/mwir_leo_minimal.yaml")
result = sensor.evaluate()
print(result.summary())
```

Override a parameter without editing the file:

```bash
radiant run examples/mwir_leo_minimal.yaml --set optics.aperture_diameter_m=0.50
```

### 7. Run the tests

```bash
pytest src/ -v -m "not golden"     # fast suite (< 2 min)
pytest -v                          # full suite, including golden regression
```

---

## Common Commands

| Command | What it does |
|---------|--------------|
| `radiant run <config.yaml>` | Run the full signal chain and print metrics |
| `radiant sweep <config.yaml> <param> --min A --max B --steps N --metric snr` | 1-D parameter sweep |
| `radiant validate <config.yaml>` | Check a config for missing/invalid parameters (no chain run) |
| `radiant explain <config.yaml> <param>` | Show how a parameter got its value (provenance) |
| `radiant gui` | Launch the desktop GUI (requires the `gui` extra) |

Run `radiant <command> --help` for full options.

---

## Documentation

- **[Quickstart guide](docs/guides/quickstart.md)** — worked usage: first evaluation, sweeps, exploring results
- **[Developer guide](DEVELOPMENT.md)** — environment setup, running tests, adding parameters/stages, contributing
- **[Configuration guide](docs/guides/configuration.md)** — YAML structure, defaults, overrides
- **[Parameter reference](docs/guides/parameter_reference.md)** — every parameter with types and defaults
- **[CLAUDE.md](CLAUDE.md)** — architectural rules (read first before changing code)
- **[Architecture docs](docs/architecture/)** — subsystem design and conventions

---

## Project Layout

```
SSR_Tool/
├── src/radiant/        # Package: core + physics stages (source … performance) + api/cli/gui
│   └── data/tables/    # Bundled reference data (solar, emissivity, QE, atmospheres) — ships in the wheel
├── tests/              # Integration + golden tests (unit tests live beside each stage)
├── examples/           # Reference configs and Python usage scripts
├── docs/               # Architecture, guides, ADRs, tracking
├── CLAUDE.md           # Coding-agent rules (authoritative)
└── DEVELOPMENT.md      # Developer setup and workflows
```
