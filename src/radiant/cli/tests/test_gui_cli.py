"""Tests for the ``radiant gui`` CLI subcommand.

The missing-extra path is unit-tested by monkeypatching the lazy import to fail,
so it runs even where PySide6 *is* installed. The wiring path monkeypatches
``launch_gui`` so no real window opens.
"""

from __future__ import annotations

import sys

import pytest
from click.testing import CliRunner

from radiant.cli.gui import GuiUnavailableError
from radiant.cli.main import cli


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
        editable Sensor** for the no-config case — the from-scratch flow
        (owner report 2026-07-17); a dead ``None`` window was the bug
        (assertion updated with that change; CU-158)."""
        from radiant.api.sensor import Sensor

        calls: list[object] = []

        def fake_launch(sensor: object = None, path: object = None) -> int:
            calls.append(sensor)
            return 0

        monkeypatch.setattr("radiant.gui.launch_gui", fake_launch)
        result = runner.invoke(cli, ["gui"], standalone_mode=False)
        assert result.exit_code == 0
        assert len(calls) == 1
        assert isinstance(calls[0], Sensor)
        assert dict(calls[0]._params.inputs()) == {}  # noqa: SLF001 — truly blank

    def test_loader_returns_blank_sensor_for_no_config(self) -> None:
        """`_load_sensor(None)` builds the blank editable Sensor directly
        (moved here from the gui tests — gui may not import cli; CU-158)."""
        from radiant.api.sensor import Sensor
        from radiant.cli.gui import _load_sensor

        sensor = _load_sensor(None)
        assert isinstance(sensor, Sensor)
        assert dict(sensor._params.inputs()) == {}  # noqa: SLF001 — truly blank

    def test_missing_config_file_errors(
        self, runner: CliRunner, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A named config that does not exist is reported before launching."""
        monkeypatch.setattr("radiant.gui.launch_gui", lambda sensor=None, path=None: 0)
        result = runner.invoke(cli, ["gui", "does_not_exist.yaml"], standalone_mode=False)
        assert result.exit_code == 1
        assert "file not found" in result.output
