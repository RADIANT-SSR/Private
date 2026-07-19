"""CU-099 — the committed parameter_reference.md must match the live registry.

Enforces doc/registry lock-step: if a `ParameterDef` is added, renamed, or its
metadata changes, `docs/guides/parameter_reference.md` must be regenerated
(`python scripts/gen_param_reference.py`) and committed. This test runs the
generator's `--check` mode and fails on any drift.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent


def test_parameter_reference_matches_registry() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/gen_param_reference.py", "--check"],
        cwd=_REPO,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        "parameter_reference.md is stale — run "
        "`python scripts/gen_param_reference.py` and commit.\n"
        f"{result.stdout}\n{result.stderr}"
    )
