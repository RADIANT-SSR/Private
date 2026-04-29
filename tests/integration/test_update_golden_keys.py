"""Regression guard for ``scripts/update_golden.py`` noise-key lookups.

CU-047: ``scripts/update_golden.py`` indexes the chain's noise dict with
fixed string keys (``"signal_shot"``, ``"dark_shot"``, ``"read_noise"``,
``"quantization"``). When a stage renames a NoiseTerm without updating
this script, the golden-refresh tooling silently breaks with KeyError.

This test asserts the invariant: every key the script reads must be
present in the chain output for the baseline scenario it runs against
(``examples/mwir_leo_minimal.yaml``).
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from radiant.api.session import RadiantSession
from radiant.io.config import load_config

CONFIG_PATH = Path(__file__).parents[2] / "examples" / "mwir_leo_minimal.yaml"

# Keys read by scripts/update_golden.py (see noise[...] indexing in main()).
SCRIPT_REQUIRED_NOISE_KEYS = (
    "signal_shot",
    "dark_shot",
    "read_noise",
    "quantization",
)


def test_update_golden_noise_keys_present_in_baseline_chain() -> None:
    """Every key indexed by update_golden.py must exist in the chain output."""
    wl = np.linspace(3.5, 5.0, 500)
    session = RadiantSession(wavelength_um=wl)
    params = session.default_params()
    load_config(CONFIG_PATH, params)
    params.resolve()
    r = session.run(params)

    chain_noise_names = {n.name for n in r.noise_terms}
    missing = [k for k in SCRIPT_REQUIRED_NOISE_KEYS if k not in chain_noise_names]
    assert not missing, (
        f"scripts/update_golden.py expects noise term(s) {missing} but the "
        f"chain produced {sorted(chain_noise_names)}. If a noise term was "
        "renamed, update both the script and this test."
    )
