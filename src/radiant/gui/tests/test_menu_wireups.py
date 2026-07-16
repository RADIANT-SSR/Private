"""Tests for the GX-1 existing-API menu wire-ups (GUI Capability Expansion plan).

Export YAML → ``Sensor.save``; Export JSON Result → ``ChainResult.to_provenance_record``;
Tools → Parameter Schema Browser (the Gap-70 introspection tree); Tools → Explain
Parameter… → ``Sensor.explain``. Each handler is one API call; the Run-menu
sweep/MC/Batch placeholders stay disabled (deferred tier by owner ruling 2026-07-16).
"""

from __future__ import annotations

import json
import warnings
from pathlib import Path

import pytest

pytest.importorskip("PySide6", reason="GUI tests require the optional 'gui' extra")

from radiant.api.sensor import Sensor  # noqa: E402
from radiant.gui.main_window import RADIANTMainWindow  # noqa: E402
from radiant.gui.widgets.schema_browser_dialog import SchemaBrowserDialog  # noqa: E402

_EXAMPLE = Path(__file__).resolve().parents[4] / "examples" / "mwir_leo_minimal.yaml"
_WAIT_MS = 20000


def _window(qtbot) -> RADIANTMainWindow:  # type: ignore[no-untyped-def]
    """A loaded window, settled past its auto-evaluation (teardown-safe)."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        window = RADIANTMainWindow(Sensor.load(_EXAMPLE))
    qtbot.addWidget(window)
    with qtbot.waitSignal(window.evaluationFinished, timeout=_WAIT_MS):
        pass
    return window


class TestActionStates:
    def test_wired_actions_enabled_after_load_and_first_result(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        window = _window(qtbot)  # settled past the auto-evaluation
        for key in ("file.export_yaml", "tools.schema", "tools.explain", "file.export_json"):
            assert window.action(key).isEnabled(), key

    def test_run_menu_trade_studies_stay_disabled(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """Owner ruling 2026-07-16: sweep/MC/Batch surfaces are a deferred tier."""
        window = _window(qtbot)
        for key in ("run.sweep", "run.monte_carlo", "run.batch"):
            assert not window.action(key).isEnabled(), key


class TestExports:
    def test_export_yaml_writes_reloadable_config(self, qtbot, tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        window = _window(qtbot)
        dest = tmp_path / "exported.yaml"
        from radiant.gui import main_window as mw

        monkeypatch.setattr(
            mw.QFileDialog, "getSaveFileName", staticmethod(lambda *a, **k: (str(dest), ""))
        )
        window.action("file.export_yaml").trigger()
        assert dest.exists()
        reloaded = Sensor.load(dest)
        assert reloaded.get_input("optics.aperture_diameter_m") == pytest.approx(
            window.sensor.get_input("optics.aperture_diameter_m"), rel=1e-12
        )
        # Export is a snapshot: the current file did not rebind to the export path.
        assert window._current_path != dest  # noqa: SLF001 — snapshot, not a rebind

    def test_export_json_writes_provenance_record(self, qtbot, tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        window = _window(qtbot)  # auto-evaluation already produced a result
        dest = tmp_path / "result.json"
        from radiant.gui import main_window as mw

        monkeypatch.setattr(
            mw.QFileDialog, "getSaveFileName", staticmethod(lambda *a, **k: (str(dest), ""))
        )
        window.action("file.export_json").trigger()
        record = json.loads(dest.read_text())
        assert isinstance(record, dict) and record  # a real provenance record landed


class TestSchemaBrowser:
    def test_browser_lists_full_schema_and_filters(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        sensor = Sensor.from_yaml(_EXAMPLE)
        dialog = SchemaBrowserDialog(sensor)
        qtbot.addWidget(dialog)
        total_rows = sum(
            dialog.tree.topLevelItem(g).childCount() for g in range(dialog.tree.topLevelItemCount())
        )
        assert total_rows == len(sensor.parameter_defs())
        # Filtering narrows to matching rows.
        dialog.filter_edit.setText("aperture_diameter")
        visible = [
            dialog.tree.topLevelItem(g).child(i).text(0)
            for g in range(dialog.tree.topLevelItemCount())
            for i in range(dialog.tree.topLevelItem(g).childCount())
            if not dialog.tree.topLevelItem(g).child(i).isHidden()
        ]
        # The exact name matches; consistency-group descriptions may legitimately
        # mention the aperture too (f_number derives from it) — assert containment
        # plus that every visible row matches on name or description.
        assert "optics.aperture_diameter_m" in visible
        for name in visible:
            pdef = sensor.parameter_def(name)
            assert "aperture_diameter" in name or "aperture_diameter" in pdef.description
