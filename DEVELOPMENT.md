# RADIANT Developer Guide

This document covers: environment setup, running tests, adding parameters, adding stages, and contributing. Read `CLAUDE.md` first for architectural rules.

---

## Prerequisites

- Python 3.11 or 3.12 (3.12 recommended)
- Git
- MODTRAN (optional — only needed to generate new atmosphere tape7 files; existing fixtures are bundled)

---

## Environment Setup

```bash
# Clone and enter the repo
git clone <repo-url> SSR_Tool
cd SSR_Tool

# Create a virtual environment (recommended)
python -m venv .venv
source .venv/bin/activate        # macOS/Linux
# .venv\Scripts\activate.bat     # Windows

# Install in editable mode with dev dependencies
pip install -e ".[dev]"

# Verify installation
radiant --help
python -c "from radiant import Sensor; print('OK')"
```

### Optional Dependencies

```bash
# HDF5 batch output support
pip install h5py

# Plotting in examples
pip install matplotlib

# Jupyter notebook support
pip install jupyter ipywidgets
```

---

## Running Tests

```bash
# All fast tests (< 2 minutes):
pytest src/ -v

# With coverage:
pytest src/ --cov=radiant --cov-report=term-missing

# A specific module:
pytest src/radiant/core/tests/ -v

# A specific test function:
pytest src/radiant/core/tests/test_parameters.py::test_fno_consistency_group -v

# Physics correctness only (Level 0):
pytest -m "level0" -v

# Skip golden regression tests (faster CI):
pytest -m "not golden" -v

# Only golden regression tests (run on main branch):
pytest -m golden -v
```

### Test Marks

| Mark | Usage |
|------|-------|
| `@pytest.mark.level0` | Physics correctness (analytic result checks) |
| `@pytest.mark.level1` | Module-level tests |
| `@pytest.mark.level2` | End-to-end reference scenario tests |
| `@pytest.mark.golden` | Golden regression tests |

---

## Code Quality Checks

Run all of these before submitting a PR. CI runs them automatically.

```bash
# Type checking (must pass --strict on core and api):
mypy --strict src/radiant/core src/radiant/api

# Linting (zero warnings):
ruff check src/

# Formatting (auto-fix):
ruff format src/

# Import rule enforcement:
import-linter --config pyproject.toml

# Organization rules (placement + naming per docs/OPERATING_MODEL.md):
python scripts/check_org_rules.py

# Coverage gate (≥ 85%):
pytest --cov=radiant --cov-fail-under=85
```

---

## Project Structure Quick Reference

```
SSR_Tool/
├── CLAUDE.md                # Coding agent instructions (read first)
├── DEVELOPMENT.md           # This file
├── pyproject.toml           # Build config, entry points, dependencies
├── src/
│   └── radiant/             # Package root
│       ├── core/            # Foundational abstractions
│       ├── source/          # Stage 1: source radiance
│       ├── atmosphere/      # Stage 2: atmosphere
│       ├── optics/          # Stage 3: optics + PSF + EE_box
│       ├── platform/        # Stage 4: smear + jitter
│       ├── spectral_integration/  # Stage 5: spectral → electrons
│       ├── detector/        # Stage 6: noise + detector MTF
│       ├── readout/         # Stage 7: readout + ADC
│       ├── performance/     # Stage 8: SNR, NEDT, NIIRS
│       ├── io/              # YAML, MODTRAN reader, results serialization
│       ├── api/             # Public API (Sensor class)
│       ├── cli/             # radiant CLI
│       └── plugins/         # Extension points
├── tests/
│   └── integration/         # Full-chain integration tests + golden files
├── data/                    # Reference data (solar spectra, atmospheres)
├── docs/                    # Architecture documents
└── examples/                # Usage examples (Python scripts)
```

---

## Adding a New Parameter

1. **Find the owning stage** for the parameter. The namespace (`sensor.optics.*`, `sensor.detector.*`, etc.) determines which stage owns it.

2. **Open the stage's `_schema.py`** and add a `ParameterDef`:

```python
# src/radiant/optics/_schema.py
from radiant.core.parameters import ParameterDef

OPTICS_PARAMS: list[ParameterDef] = [
    # ... existing params ...
    ParameterDef(
        name="sensor.optics.your_new_param",
        description="One-sentence description of what this parameter represents",
        dtype=float,
        canonical_unit="m",      # internal canonical unit
        input_unit="mm",         # user-facing unit (add conversion to core/units.py if needed)
        default=None,            # None = required; otherwise, the default value in input_unit
        bounds=(0.0, 1.0),       # in input_unit; None if no bounds
        enum_values=None,        # for str parameters: list of allowed values
        group=None,              # consistency group name, if any
        tags=frozenset({"optics"}),
    ),
]
```

3. **Add the unit conversion** if the input unit differs from the canonical unit and is not already in `core/units.py`.

4. **Update the YAML example** in `docs/architecture/RADIANT_Config_Format.md` to show the new parameter.

5. **Write a Level 0 test** if the new parameter affects any equation.

6. **Add the parameter** to the naming table in `docs/architecture/RADIANT_Parameter_System.md`.

---

## Adding a New Stage

1. **Create the directory:**

```bash
mkdir -p src/radiant/mystage/tests
touch src/radiant/mystage/__init__.py
touch src/radiant/mystage/_schema.py
touch src/radiant/mystage/stage.py
touch src/radiant/mystage/tests/__init__.py
touch src/radiant/mystage/tests/test_mystage.py
```

2. **Write `_schema.py`** with all `ParameterDef` objects for this stage's parameters.

3. **Write Level 0 tests** for the key equations before implementing the stage.

4. **Write `stage.py`** implementing the `Stage` protocol:

```python
# src/radiant/mystage/stage.py
from radiant.core.chain import ChainState
from radiant.core.parameters import ParameterSet

class MyStage:
    name = "mystage"

    def run(self, state: ChainState, params: ParameterSet) -> ChainState:
        # Read from state (never mutate it)
        prior_data = state.stage_outputs.get("prior_stage", {})

        # Do physics
        result = compute_something(params.get("some.param"))

        # Write to new state (never mutate the input state)
        state = state.with_stage_output("mystage", "my_result", result)

        # If the stage generates a noise term:
        from radiant.core.radiometry import NoiseTerm
        noise = NoiseTerm(
            name="my_noise",
            value_e=sigma,
            origin_frame="electrons",
            physical_basis="My physical basis",
        )
        state = state.with_noise(noise)

        return state
```

5. **Register the stage** in the chain runner. Open `src/radiant/api/session.py` and add `MyStage()` to the `_default_stages()` list in the correct position.

6. **Add the module** to the import rules in `pyproject.toml` under `[tool.importlinter]`.

7. **Add the stage** to the document map in `docs/architecture/RADIANT_Master_Architecture.md`.

---

## Updating Golden Results

Golden results are frozen JSON files in `tests/golden/`. Update them only when a legitimate physics change produces different (but correct) results.

```bash
# Freeze golden result for one scenario:
radiant freeze-golden tests/fixtures/mwir_leo_baseline.yaml \
    --output tests/golden/mwir_leo_baseline.json \
    --message "Describe why the result changed"

# Re-freeze all golden files:
radiant freeze-all-golden --message "Reason for update"

# Compare current output against a golden file:
radiant compare-golden tests/golden/mwir_leo_baseline.json

# Verify golden files are all passing:
pytest -m golden -v
```

Always include the `--message` flag. The message is stored in the golden JSON and serves as the change log for physics changes. Golden file updates require review from a domain expert.

---

## Working With MODTRAN Files

RADIANT reads MODTRAN tape7 output files. The fixture file at `tests/fixtures/sample_tape7.txt` is a small (50-line) MWIR mid-latitude summer example sufficient for unit tests.

**To generate new tape7 files:**
- Run MODTRAN with the desired atmospheric and geometry settings
- Point `atmosphere.modtran_file` in the config to the output tape7 file
- Verify the reader loads it correctly: `radiant validate your_config.yaml`

**tape7 format requirements:**
- Column format: wavenumber (cm⁻¹), transmittance, path radiance (W/cm²/sr/cm⁻¹), thermal emission (W/cm²/sr/cm⁻¹)
- Wavenumber must be ascending (RADIANT reverses it to ascending wavelength on load)
- Radiance units must be W/cm²/sr/cm⁻¹ (RADIANT converts to W/m²/sr/µm)

---

## Example Workflows

### Quick sanity check after a change

```python
# scripts/sanity_check.py
from radiant import Sensor

s = Sensor.load("tests/fixtures/mwir_leo_baseline.yaml")
result = s.evaluate()
print(f"SNR:   {result.snr():.1f}  (expect ~47)")
print(f"NEDT:  {result.nedt()*1000:.1f} mK  (expect ~23)")
print(f"NIIRS: {result.niirs():.2f}  (expect ~5.4)")
```

### Run a parameter sweep to see the effect of a change

```python
import numpy as np
from radiant import Sensor

s = Sensor.load("tests/fixtures/mwir_leo_baseline.yaml")
sweep = s.sweep("sensor.optics.aperture_diameter", np.linspace(0.15, 0.60, 10))
for d, snr in zip(sweep.values, sweep["snr"]):
    print(f"D={d:.2f} m  SNR={snr:.1f}")
```

### Check all noise terms

```python
from radiant import Sensor

s = Sensor.load("tests/fixtures/mwir_leo_baseline.yaml")
result = s.evaluate()
result.noise_budget().table()
```

---

## Contributing

1. **Branch naming:** `feature/<short-description>` or `fix/<issue-number>-short-description`
2. **PR title:** present tense, imperative mood: "Add charge-diffusion MTF to DetectorStage"
3. **PR description:** Include: what changed, why, before/after golden comparison (if golden files changed), any physics references.
4. **Review requirement:** At least one reviewer. Golden file changes require a domain expert.
5. **CI must pass:** All tests, type check, lint, import rules, coverage gate.
6. **No force-push to main.**
