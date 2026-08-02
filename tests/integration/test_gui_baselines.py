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

import emit_gui_yaml  # noqa: E402
import gui_baselines  # noqa: E402
from gui_baselines import REGISTRY, GuiScenario  # noqa: E402
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


@pytest.mark.parametrize("scen", REGISTRY, ids=[s.id for s in REGISTRY])
def test_gui_baseline_references_only_committed_files(scen: object) -> None:
    """CU-273: no baseline may point at a generated (gitignored) input file.

    ``test_gui_baseline_reproduces_snapshot`` above cannot catch this. It runs
    in a tree where the scenario's ``outputs/`` directory usually exists — the
    same tree that regenerated the baseline — so an unreloadable path resolves
    fine there and the failure surfaces only for the next cold checkout or CI.
    That is precisely how a live regression reached ``main`` in the CU-253
    baseline refresh under a green 6023-test suite (``d169feb``, repaired by
    ``962bc8e``).

    This is the static half, and it holds regardless of what happens to be on
    disk: every file-path value in every shipped ``.gui.yaml`` must resolve to
    a file that is committed and *outside* any ``outputs/`` tree. It is cheap,
    unmarked (so it runs in the fast suite, unlike the golden reload above),
    and it fails in the tree that introduces the problem rather than the one
    that inherits it.
    """
    text = scen.yaml_path.read_text(encoding="utf-8")
    offenders = [
        line.strip() for line in text.splitlines() if "_path:" in line and "outputs/" in line
    ]
    assert not offenders, (
        f"{scen.id} {scen.slug}: baseline references the gitignored outputs/ tree, so it "
        f"will not reload in a cold checkout (CU-273): {offenders}. Commit the derived "
        "file under the scenario's inputs/ directory — scenarios/tools/emit_gui_yaml.py "
        "repoints it automatically once a committed counterpart exists."
    )

    # And the paths it does reference must actually be there.
    base = scen.yaml_path.parent
    for line in text.splitlines():
        key, _, value = line.partition(":")
        if not key.strip().endswith("_path"):
            continue
        target = value.strip().strip("'\"")
        if not target:
            continue
        resolved = (base / target).resolve()
        assert resolved.exists(), (
            f"{scen.id} {scen.slug}: {key.strip()} -> {target} does not resolve to a file "
            f"({resolved}). A shipped baseline must be reloadable from a clean checkout."
        )


@pytest.mark.parametrize("scen", REGISTRY, ids=[s.id for s in REGISTRY])
def test_gui_baseline_is_rebuildable_from_its_runner(scen: object) -> None:
    """CU-319: every registry entry can still build its Sensor from the runner.

    The reload tests above read the *committed* ``.gui.yaml``, so they stay green
    while the path that produces it is broken. That is what happened after the
    CU-164 guard pass moved runner constants and config dicts inside ``main()``:
    13 of the 38 entries reached for module attributes that no longer existed
    (``AttributeError: module 'scenrunner_<slug>' has no attribute
    'base_config'`` / ``T_nominal`` / ``baseline_vis_km`` / ``pitches_um`` /
    ``band_min_um`` / ``sensor`` / ``config``), and 4.3's lazy accessor refused
    at import on a clean tree. ``emit_gui_yaml.py`` printed ``[FAIL]`` and
    exited 0, so a batch regeneration looked successful while leaving those
    baselines stale.

    This asserts only the *build* half (no ``evaluate``), which is what broke:
    import the runner, call the registry's factory, get a Sensor.
    """
    sensor = scen.build()
    assert sensor is not None
    # A built baseline must carry real inputs, not an empty default Sensor.
    assert sensor.inputs(), f"{scen.id}: runner factory produced a Sensor with no inputs"


class TestEmitterExitCode:
    """CU-319: a batch emit that fails any scenario must exit non-zero.

    ``emit_gui_yaml.main`` used to ``return 0`` unconditionally, printing
    ``[FAIL]`` per broken scenario — so the documented §5.3 baseline-refresh
    path reported success while leaving baselines stale, and no script or CI
    step could tell the difference.
    """

    @staticmethod
    def _fake_scenario(tmp_path: Path, scen_id: str, build: object) -> GuiScenario:
        """A registry entry rooted in ``tmp_path`` so nothing committed is touched."""
        return GuiScenario(
            id=scen_id,
            persona="99_test_persona",
            slug=f"{scen_id}_fake",
            title="fake",
            build=build,  # type: ignore[arg-type]
            metrics=("snr",),
        )

    def test_failing_scenario_exits_non_zero(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def _explode() -> object:
            raise AttributeError("module 'scenrunner_fake' has no attribute 'base_config'")

        monkeypatch.setattr(gui_baselines, "SCENARIOS", tmp_path)
        scen = self._fake_scenario(tmp_path, "99.1", _explode)
        monkeypatch.setattr(emit_gui_yaml, "REGISTRY", [scen])

        assert emit_gui_yaml.main(["emit_gui_yaml.py"]) != 0

    def test_passing_scenario_exits_zero(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from radiant.api import Sensor

        example = Path(__file__).resolve().parents[2] / "examples" / "mwir_leo_minimal.yaml"

        monkeypatch.setattr(gui_baselines, "SCENARIOS", tmp_path)
        scen = self._fake_scenario(tmp_path, "99.2", lambda: Sensor.from_yaml(example))
        monkeypatch.setattr(emit_gui_yaml, "REGISTRY", [scen])

        assert emit_gui_yaml.main(["emit_gui_yaml.py"]) == 0
        assert scen.yaml_path.is_file()
        assert scen.expected_path.is_file()

    def test_unknown_scenario_id_still_exits_two(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """The pre-existing "nothing matched" exit code is unchanged."""
        assert emit_gui_yaml.main(["emit_gui_yaml.py", "no.such.id"]) == 2


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
