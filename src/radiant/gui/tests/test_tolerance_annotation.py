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

    def test_declared_extended_dims_subpixel_rows(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """Excluded rows dim (muted foreground + value tooltip), not a value-cell suffix.

        The old ``(n/a: <type>)`` text lived inside the Value column and blew a
        content-sized column wide open, starving the names (2026-08-03 critique;
        owner-hit on scenario 10.1). The affordance is now the dimmed row; the
        sentence lives in the tooltip.
        """
        from radiant.gui.themes.stylesheet import active_theme

        window = self._window_for_badging(qtbot)
        window.sensor.set("source.scene_type", "extended")
        window._parameter_panel.populate(window.sensor)  # noqa: SLF001
        items = window._parameter_panel._items  # noqa: SLF001
        dim = active_theme().muted_2
        # Sub-pixel-only knobs dim + explain; regime-independent rows do not.
        excluded = items["source.target.fill_fraction"]
        assert "(n/a" not in excluded.text(1)  # the suffix is gone for good
        assert excluded.foreground(0).color().name() == dim
        assert "extended" in excluded.toolTip(1)
        assert items["geometry.target.shape"].foreground(0).color().name() == dim
        included = items["source.contrast_reference.temperature"]
        assert included.toolTip(1) == ""
        assert included.foreground(0).color().name() != dim
        # The selector itself never dims (the way back out).
        assert items["source.scene_type"].foreground(0).color().name() != dim

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


class TestRejectedApplyChangesNothing:
    """CU-219 — the single-value path must keep the contract every reject surface keeps."""

    def test_out_of_bounds_value_is_rejected_before_the_tolerance_step(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """Documents why the entry's reproduction does not reproduce.

        Kept as a guard: if clone validation ever stops catching this, the orphan
        window widens back to the case the CU described.
        """
        sensor = Sensor.from_yaml(_EXAMPLE)
        alt = "geometry.sensor_altitude_m"  # bounds (0, 1e8)
        before_value = sensor.get(alt)
        assert alt not in sensor.tolerances()

        dialog = ParameterEditorDialog(sensor, alt, lambda d, u: None)
        qtbot.addWidget(dialog)
        assert dialog._tol_distribution is not None  # noqa: SLF001
        dialog._tol_distribution.setCurrentText("gaussian")  # noqa: SLF001
        dialog._tol_params["std"].setText("100.0")  # noqa: SLF001
        dialog.value_editor.setText("999999999999")  # far above the 1e8 m bound
        dialog.apply(close=False)

        assert dialog.error_frame.isVisibleTo(dialog)  # the rejection is shown
        assert sensor.get(alt) == pytest.approx(before_value, abs=0)
        assert alt not in sensor.tolerances(), (
            "a rejected Apply wrote a tolerance for a value that never landed"
        )

    def test_rejected_tolerance_leaves_no_value_behind(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """The mirror case: a good value with a malformed tolerance commits neither."""
        sensor = Sensor.from_yaml(_EXAMPLE)
        alt = "geometry.sensor_altitude_m"
        before_value = sensor.get(alt)

        dialog = ParameterEditorDialog(sensor, alt, lambda d, u: None)
        qtbot.addWidget(dialog)
        assert dialog._tol_distribution is not None  # noqa: SLF001
        dialog._tol_distribution.setCurrentText("gaussian")  # noqa: SLF001
        dialog._tol_params["std"].setText("")  # required field left empty
        dialog.value_editor.setText("600000")
        dialog.apply(close=False)

        assert dialog.error_frame.isVisibleTo(dialog)
        assert sensor.get(alt) == pytest.approx(before_value, abs=0)
        assert alt not in sensor.tolerances()

    def test_both_valid_commits_both(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """The guard must not have made the happy path a no-op."""
        sensor = Sensor.from_yaml(_EXAMPLE)
        alt = "geometry.sensor_altitude_m"

        dialog = ParameterEditorDialog(sensor, alt, lambda d, u: None)
        qtbot.addWidget(dialog)
        assert dialog._tol_distribution is not None  # noqa: SLF001
        dialog._tol_distribution.setCurrentText("gaussian")  # noqa: SLF001
        dialog._tol_params["std"].setText("1000.0")  # noqa: SLF001
        dialog.value_editor.setText("600000")
        dialog.apply(close=False)

        assert not dialog.error_frame.isVisibleTo(dialog)
        assert sensor.get(alt) == pytest.approx(600000.0, abs=0)
        assert sensor.tolerances()[alt].distribution == "gaussian"
