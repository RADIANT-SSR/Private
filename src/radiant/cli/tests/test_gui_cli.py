"""Tests for the ``radiant gui`` CLI subcommand.

The missing-extra path is unit-tested by monkeypatching the lazy import to fail,
so it runs even where PySide6 *is* installed. The wiring path monkeypatches
``launch_gui`` so no real window opens.

Since CU-342 the CLI loads every file through ``ConfigurationSet.load`` — the
API decides the document kind (the same one-reader dispatch as the GUI's
File → Open) — and hands ``launch_gui`` a ``config_set``, so a study file
(``configurations:`` section) launches as the full set instead of dying on the
``Sensor.from_yaml`` refusal.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from click.testing import CliRunner

from radiant.cli.gui import GuiUnavailableError
from radiant.cli.main import cli

_EXAMPLE = Path(__file__).resolve().parents[4] / "examples" / "mwir_leo_minimal.yaml"


@pytest.fixture()
def runner() -> CliRunner:
    return CliRunner()


class TestGuiSubcommand:
    def test_registered(self, runner: CliRunner) -> None:
        """`radiant gui` is a known subcommand with help text."""
        result = runner.invoke(cli, ["gui", "--help"])
        assert result.exit_code == 0
        assert "desktop GUI" in result.output

    def test_missing_pyside6_raises_actionable_error(
        self, runner: CliRunner, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """If the gui extra is absent, an actionable RADIANT error names the remedy."""
        # Force `from radiant.gui import launch_gui` to raise ImportError, as it
        # would on a core-only install missing PySide6.
        monkeypatch.setitem(sys.modules, "radiant.gui", None)

        result = runner.invoke(cli, ["gui"], standalone_mode=False)
        assert result.exception is not None
        assert isinstance(result.exception, GuiUnavailableError)
        exc = result.exception
        assert isinstance(exc, GuiUnavailableError)
        assert 'pip install "radiant[gui]"' in exc.action
        assert "not available" in exc.what

    def test_launches_with_no_config(
        self, runner: CliRunner, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """With the extra present, `radiant gui` hands launch_gui a **blank
        editable** degenerate configuration set for the no-config case — the
        from-scratch flow (owner report 2026-07-17); a dead ``None`` window was
        the bug (CU-158; set-shaped since CU-342)."""
        from radiant.api.config_set import ConfigurationSet

        calls: list[object] = []

        def fake_launch(
            sensor: object = None, path: object = None, *, config_set: object = None
        ) -> int:
            calls.append(config_set)
            return 0

        monkeypatch.setattr("radiant.gui.launch_gui", fake_launch)
        result = runner.invoke(cli, ["gui"], standalone_mode=False)
        assert result.exit_code == 0
        assert len(calls) == 1
        cs = calls[0]
        assert isinstance(cs, ConfigurationSet)
        assert len(cs) == 1  # degenerate — observably the single-model session
        assert dict(cs.base._params.inputs()) == {}  # noqa: SLF001 — truly blank

    def test_loader_returns_blank_set_for_no_config(self) -> None:
        """`_load_config_set(None)` builds the blank editable degenerate set
        directly (moved here from the gui tests — gui may not import cli;
        CU-158/CU-342)."""
        from radiant.api.config_set import ConfigurationSet
        from radiant.cli.gui import _load_config_set

        cs = _load_config_set(None)
        assert isinstance(cs, ConfigurationSet)
        assert len(cs) == 1
        assert dict(cs.base._params.inputs()) == {}  # noqa: SLF001 — truly blank

    def test_plain_config_launches_as_degenerate_set(
        self, runner: CliRunner, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A single-configuration file arrives as the one-member set with its path."""
        from radiant.api.config_set import ConfigurationSet

        calls: list[tuple[object, object]] = []

        def fake_launch(
            sensor: object = None, path: object = None, *, config_set: object = None
        ) -> int:
            calls.append((config_set, path))
            return 0

        monkeypatch.setattr("radiant.gui.launch_gui", fake_launch)
        result = runner.invoke(cli, ["gui", str(_EXAMPLE)], standalone_mode=False)
        assert result.exit_code == 0
        cs, path = calls[0]
        assert isinstance(cs, ConfigurationSet)
        assert len(cs) == 1
        assert path == str(_EXAMPLE)

    def test_study_file_launches_as_full_set(
        self, runner: CliRunner, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """A ``configurations:``-bearing file launches as the full set (CU-342).

        This is the exact file kind `Sensor.from_yaml` refuses with the
        "load it with ConfigurationSet.load" error — the pre-fix CLI died here.
        """
        from radiant.api.config_set import ConfigurationSet
        from radiant.api.sensor import Sensor

        study = tmp_path / "study.yaml"
        ConfigurationSet(Sensor.load(_EXAMPLE), names=["MWIR_A", "MWIR_B"]).save(study)

        calls: list[object] = []

        def fake_launch(
            sensor: object = None, path: object = None, *, config_set: object = None
        ) -> int:
            calls.append(config_set)
            return 0

        monkeypatch.setattr("radiant.gui.launch_gui", fake_launch)
        result = runner.invoke(cli, ["gui", str(study)], standalone_mode=False)
        assert result.exit_code == 0
        cs = calls[0]
        assert isinstance(cs, ConfigurationSet)
        assert cs.names() == ("MWIR_A", "MWIR_B")

    def test_missing_config_file_errors(
        self, runner: CliRunner, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A named config that does not exist is reported before launching."""
        monkeypatch.setattr(
            "radiant.gui.launch_gui",
            lambda sensor=None, path=None, *, config_set=None: 0,
        )
        result = runner.invoke(cli, ["gui", "does_not_exist.yaml"], standalone_mode=False)
        assert result.exit_code == 1
        assert "file not found" in result.output
