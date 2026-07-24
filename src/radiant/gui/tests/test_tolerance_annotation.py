"""Tests for the GT-2 tolerance annotation + MC/Batch scaffolds (owner D3)."""

from __future__ import annotations

import warnings
from pathlib import Path

import pytest

pytest.importorskip("PySide6", reason="GUI tests require the optional 'gui' extra")

from radiant.api.sensor import Sensor  # noqa: E402
from radiant.gui.main_window import RADIANTMainWindow  # noqa: E402
from radiant.gui.widgets.parameter_editor_dialog import ParameterEditorDialog  # noqa: E402

_REPO = Path(__file__).resolve()
while not (_REPO / "pyproject.toml").exists():
    _REPO = _REPO.parent
_EXAMPLE = _REPO / "examples" / "mwir_leo_minimal.yaml"
_WAIT_MS = 20000


class TestToleranceSection:
    def test_dialog_sets_and_clears_tolerance(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        sensor = Sensor.from_yaml(_EXAMPLE)
        committed: list[tuple[str, str | None]] = []
        dialog = ParameterEditorDialog(
            sensor, "detector.qe_value", lambda d, u: committed.append((d, u))
        )
        qtbot.addWidget(dialog)
        assert dialog._tol_distribution is not None  # noqa: SLF001 — float param gets the section
        dialog._tol_distribution.setCurrentText("gaussian")  # noqa: SLF001
        dialog._tol_params["std"].setText("0.02")  # noqa: SLF001
        dialog.apply(close=False)
        tol = sensor.tolerances()["detector.qe_value"]
        assert tol.distribution == "gaussian"
        assert tol.params["std"] == pytest.approx(0.02, rel=1e-9)
        # Clearing: back to none.
        dialog._tol_distribution.setCurrentText("none")  # noqa: SLF001
        dialog.apply(close=False)
        assert "detector.qe_value" not in sensor.tolerances()

    def test_missing_tolerance_param_rejected_inline(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        sensor = Sensor.from_yaml(_EXAMPLE)
        dialog = ParameterEditorDialog(sensor, "detector.qe_value", lambda d, u: None)
        qtbot.addWidget(dialog)
        dialog._tol_distribution.setCurrentText("gaussian")  # noqa: SLF001
        dialog._tol_params["std"].setText("")  # noqa: SLF001
        dialog.apply(close=False)
        assert "detector.qe_value" not in sensor.tolerances()

    def test_enum_parameter_has_no_tolerance_section(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        sensor = Sensor.from_yaml(_EXAMPLE)
        dialog = ParameterEditorDialog(sensor, "atmosphere.model", lambda d, u: None)
        qtbot.addWidget(dialog)
        assert dialog._tol_distribution is None  # noqa: SLF001

    def test_tolerance_round_trips_through_save(self, qtbot, tmp_path) -> None:  # type: ignore[no-untyped-def]
        sensor = Sensor.from_yaml(_EXAMPLE)
        sensor.set_tolerance("detector.qe_value", "gaussian", std=0.02)
        path = tmp_path / "tol.yaml"
        sensor.save(path)
        reloaded = Sensor.load(path)
        assert reloaded.tolerances()["detector.qe_value"].params["std"] == pytest.approx(
            0.02, rel=1e-9
        )


class TestScaffolds:
    def _window(self, qtbot) -> RADIANTMainWindow:  # type: ignore[no-untyped-def]
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            window = RADIANTMainWindow(Sensor.load(_EXAMPLE))
        qtbot.addWidget(window)
        with qtbot.waitSignal(window.evaluationFinished, timeout=_WAIT_MS):
            pass
        return window

    def test_mc_scaffold_opens_editor_tab_with_runnable_snippet(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        window = self._window(qtbot)
        window.sensor.set_tolerance("detector.qe_value", "gaussian", std=0.02)
        assert window.action("run.monte_carlo").isEnabled()
        window.action("run.monte_carlo").trigger()
        tab = window._scripting_window.editor.current_tab()  # noqa: SLF001
        text = tab.toPlainText()
        assert "sensor.monte_carlo(n_trials=500" in text
        assert "detector.qe_value" in text  # the annotated tolerance is listed
        assert "percentile(" in text

    def test_batch_scaffold_matches_real_api(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        window = self._window(qtbot)
        window.action("run.batch").trigger()
        tab = window._scripting_window.editor.current_tab()  # noqa: SLF001
        text = tab.toPlainText()
        assert "BatchRunner(base, axes).run(evaluate)" in text
        assert 'pivot("snr", rows="aperture", cols="t_int")' in text

    def test_tree_shows_tolerance_badge(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        window = self._window(qtbot)
        window.sensor.set_tolerance("detector.qe_value", "gaussian", std=0.02)
        window._parameter_panel.populate(window.sensor)  # noqa: SLF001
        item = window._parameter_panel._items["detector.qe_value"]  # noqa: SLF001
        assert "±" in item.text(1)


class TestRelevanceBadging:
    """GT-7 (Gap 85 close-out): the All-Parameters tree badges excluded rows."""

    def test_declared_extended_badges_subpixel_rows(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        window = self._window_for_badging(qtbot)
        window.sensor.set("source.scene_type", "extended")
        window._parameter_panel.populate(window.sensor)  # noqa: SLF001
        items = window._parameter_panel._items  # noqa: SLF001
        # Sub-pixel-only knobs badge; regime-independent + matching rows do not.
        assert "(n/a: extended)" in items["source.target.fill_fraction"].text(1)
        assert "(n/a: extended)" in items["geometry.target.shape"].text(1)
        assert "(n/a" not in items["source.contrast_reference.temperature"].text(1)
        assert "(n/a" not in items["source.target.temperature"].text(1)
        # The selector itself never badges (the way back out).
        assert "(n/a" not in items["source.scene_type"].text(1)

    def test_auto_badges_nothing(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        window = self._window_for_badging(qtbot)
        window._parameter_panel.populate(window.sensor)  # noqa: SLF001
        items = window._parameter_panel._items  # noqa: SLF001
        assert "(n/a" not in items["source.target.fill_fraction"].text(1)

    def _window_for_badging(self, qtbot) -> RADIANTMainWindow:  # type: ignore[no-untyped-def]
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            window = RADIANTMainWindow(Sensor.load(_EXAMPLE))
        qtbot.addWidget(window)
        with qtbot.waitSignal(window.evaluationFinished, timeout=_WAIT_MS):
            pass
        return window
