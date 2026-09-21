"""Findings Log 2026-09-20 (engine-consistency batch B): a withdrawn configured input.

In a study a configured parameter carries one value per configuration; a column
has no empty cell. The dock refuses a required parameter's reset at the door, so
the reachable withdrawal is a companion switch (CU-377): entering a reflectance
withdraws the thermal pair, and a configured temperature has nowhere to be
withdrawn to. The window used to drop that silently, leaving the displayed
sensor and the document apart; it now refuses with a reason and puts the display
back in step with the document. Failed on the pre-fix code (no dialog).
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("PySide6", reason="GUI tests require the optional 'gui' extra")

from radiant.api.config_set import ConfigurationSet  # noqa: E402
from radiant.api.sensor import Sensor  # noqa: E402
from radiant.gui.main_window import RADIANTMainWindow  # noqa: E402
from radiant.gui.widgets.parameter_editor_dialog import ParameterEditorDialog  # noqa: E402

_EXAMPLE = Path(__file__).resolve().parents[4] / "examples" / "mwir_leo_minimal.yaml"
_TEMPERATURE = "source.target.temperature"
_WAIT_MS = 20000


def _open_study(qtbot, tmp_path: Path) -> RADIANTMainWindow:  # type: ignore[no-untyped-def]
    cs = ConfigurationSet(Sensor.load(_EXAMPLE), names=["A", "B"])
    cs.configure(_TEMPERATURE, [310.0, 320.0])  # differs from the 300 K default
    path = tmp_path / "study.yaml"
    cs.save(path)
    window = RADIANTMainWindow(config_set=ConfigurationSet.load(path), path=str(path))
    qtbot.addWidget(window)
    with qtbot.waitSignal(window.evaluationFinished, timeout=_WAIT_MS):
        pass
    return window


def test_withdrawing_a_configured_value_is_refused_and_the_display_resynced(
    qtbot, tmp_path: Path, monkeypatch
) -> None:  # type: ignore[no-untyped-def]
    window = _open_study(qtbot, tmp_path)
    opened: list[object] = []
    for module in ("radiant.gui.main_window", "radiant.gui.widgets.parameter_panel"):
        monkeypatch.setattr(f"{module}.exec_dialog", lambda dlg, *a, **k: opened.append(dlg) or 0)
    assert window.sensor.inputs()[_TEMPERATURE] == 310.0
    # A reflectance on the thermal target withdraws the thermal pair (CU-377 F-07);
    # the configured temperature has no empty cell to be withdrawn to.
    panel = window.parameter_panel
    dialog = ParameterEditorDialog(
        window.sensor,
        "source.target.reflectance",
        panel._after_dialog_commit,
        panel,  # noqa: SLF001
    )
    qtbot.addWidget(dialog)
    dialog.value_editor.setText("0.5")
    dialog.apply(close=True)
    assert opened, "the withdrawal is refused with a reason, not dropped silently"
    header = getattr(opened[-1], "header_text", "")
    assert "reset" in header.lower()
    # The document still holds the configured column, and the display agrees with it.
    cs = window._config_set  # noqa: SLF001
    assert cs is not None and cs.configured()[_TEMPERATURE][0] == 310.0
    assert window.sensor.inputs()[_TEMPERATURE] == 310.0
