"""CU-179: gate the GUI-loadable scenario baselines in CI.

Each validated scenario ships a portable ``inputs/<slug>.gui.yaml`` (what the GUI's
``File -> Open YAML`` consumes) plus an ``inputs/<slug>.gui.expected.json`` snapshot
of its headline metrics. ``scenarios/tools/verify_gui_yaml.py`` reloads each YAML,
re-evaluates the chain, and checks the metrics still match the snapshot — the
acceptance test for these artifacts.

That script was only ever run by hand, so nothing in pytest/CI exercised it: when
the engine legitimately moved (the CU-166 NIIRS gate, Gap 38, CU-155/157/161, …)
the snapshots silently went stale — CU-175 found 31 of 34 red, undetected until the
script was run manually. This test runs the same reload-and-compare check under
pytest (``golden`` marker), one case per scenario, so drift fails CI instead of
accumulating invisibly. When a baseline change is intentional, regenerate the
snapshots with ``python scenarios/tools/emit_gui_yaml.py`` (Rule 26 /
``RADIANT_Testing_Validation.md`` §5.3), exactly as for any golden update.

Runs from any checkout because the baselines reference their data files by a
YAML-relative path (CU-177), not an absolute machine path.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# The registry + verify harness live under scenarios/tools (outside the package).
_TOOLS = Path(__file__).resolve().parents[2] / "scenarios" / "tools"
if str(_TOOLS) not in sys.path:
    sys.path.insert(0, str(_TOOLS))

from gui_baselines import REGISTRY  # noqa: E402
from verify_gui_yaml import consistency_one, verify_one  # noqa: E402

# Baselines that reference a *generated* (gitignored) input file and so cannot be
# reloaded in a cold checkout without first running the scenario. Empty since
# CU-180 committed 4.3's derived radiance CSV as a scenario input (its generator
# is named in the scenario MANIFEST). Every shipped baseline is now portable and
# gated; add an id here only if a future baseline reintroduces a non-committed input.
_NON_PORTABLE: set[str] = set()


@pytest.mark.golden
@pytest.mark.parametrize("scen", REGISTRY, ids=[s.id for s in REGISTRY])
def test_gui_baseline_reproduces_snapshot(scen: object) -> None:
    """Each shipped .gui.yaml reloads and reproduces its .gui.expected.json."""
    if scen.id in _NON_PORTABLE:
        pytest.skip(
            f"{scen.id}: baseline references a generated (gitignored) input file; "
            "not reloadable in a cold checkout — see CU-180"
        )
    ok, message = verify_one(scen)
    assert ok, f"{scen.id} {scen.slug}: {message}"


@pytest.mark.golden
@pytest.mark.parametrize("scen", REGISTRY, ids=[s.id for s in REGISTRY])
def test_gui_baseline_dual_path_consistency(scen: object) -> None:
    """R2.1: the Rule-4 dual-path (PSF vs MTF-product) invariant holds for every
    shipped baseline that computes the spatial path.

    ``PerformanceStage`` only *logs a warning* when the FFT of the convolved
    EffectivePSF disagrees with the MTF product — the audit's #1 unenforced
    risk. This turns that warn-only invariant into a hard gate: a spatial
    degradation added to one path but not the other fails CI here. Scenarios
    that deselect the spatial-MTF metric group (Gap 96) compute no consistency
    check and pass trivially.
    """
    if scen.id in _NON_PORTABLE:
        pytest.skip(f"{scen.id}: non-portable baseline (see CU-180)")
    ok, message = consistency_one(scen)
    assert ok, f"{scen.id} {scen.slug}: dual-path consistency FAILED — {message}"
