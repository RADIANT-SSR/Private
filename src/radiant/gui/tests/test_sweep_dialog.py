"""Tests for the Run → Run Sweep… dialog (Tier-2 GT-1)."""

from __future__ import annotations

import warnings
from pathlib import Path

import pytest

pytest.importorskip("PySide6", reason="GUI tests require the optional 'gui' extra")

from radiant.api.sensor import Sensor  # noqa: E402
from radiant.api.sweep import SweepResult  # noqa: E402
from radiant.gui.widgets.sweep_dialog import SweepDialog  # noqa: E402

_REPO = Path(__file__).resolve()
while not (_REPO / "pyproject.toml").exists():
    _REPO = _REPO.parent
_EXAMPLE = _REPO / "examples" / "mwir_leo_minimal.yaml"
_WAIT_MS = 120000


def _dialog(qtbot, metric_names=("snr",)) -> SweepDialog:  # type: ignore[no-untyped-def]
    sensor = Sensor.from_yaml(_EXAMPLE)
    dialog = SweepDialog(sensor, metric_names)
    qtbot.addWidget(dialog)
    return dialog


class TestSpec:
    def test_unit_labels_follow_schema(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        dialog = _dialog(qtbot)
        dialog._param1.setCurrentText("detector.pixel_pitch_x_um")  # noqa: SLF001
        assert "µm" in dialog._unit1.text() or "um" in dialog._unit1.text()  # noqa: SLF001

    def test_axis_values_stay_in_the_input_unit(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """Sensor.sweep interprets values like sensor.set: in the INPUT unit (CU-325).

        The dialog used to convert to canonical here, so a µm-pitch sweep ran
        values 10⁶ off (or died on the input-unit bounds check). The typed
        numbers now pass through untouched; the API converts once, inside.
        """
        dialog = _dialog(qtbot)
        values = dialog._axis_values(  # noqa: SLF001
            "detector.pixel_pitch_x_um", "10", "30", "3", log=False
        )
        assert values[0] == pytest.approx(10.0, rel=1e-12)
        assert values[-1] == pytest.approx(30.0, rel=1e-12)

    def test_invalid_spec_reports_not_runs(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        dialog = _dialog(qtbot)
        dialog._n1.setText("1")  # noqa: SLF001 — fewer than 2 points
        dialog.start_sweep()
        assert "Invalid sweep spec" in dialog.status_text

    def test_2d_requires_two_distinct_params(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        dialog = _dialog(qtbot)
        dialog._enable_2d.setChecked(True)  # noqa: SLF001
        dialog._param2.setCurrentText(dialog._param1.currentText())  # noqa: SLF001
        dialog.start_sweep()
        assert "two different parameters" in dialog.status_text


class TestRun:
    def test_1d_sweep_runs_and_plots(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        dialog = _dialog(qtbot)
        dialog._param1.setCurrentText("optics.aperture_diameter_m")  # noqa: SLF001
        dialog._start1.setText("0.25")  # noqa: SLF001
        dialog._stop1.setText("0.35")  # noqa: SLF001
        dialog._n1.setText("3")  # noqa: SLF001
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            with qtbot.waitSignal(dialog._worker_done_signal(), timeout=_WAIT_MS):
                dialog.start_sweep()
        assert isinstance(dialog.sweep_result, SweepResult)
        assert len(dialog.sweep_result.values) == 3
        assert "Done" in dialog.status_text
        # SNR grows with aperture — the physics sanity of the run.
        mv = dialog.sweep_result.metric_values
        assert mv[-1] > mv[0]

    def test_copy_as_script_reproduces_run(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        dialog = _dialog(qtbot)
        dialog._param1.setCurrentText("optics.aperture_diameter_m")  # noqa: SLF001
        dialog._start1.setText("0.25")  # noqa: SLF001
        dialog._stop1.setText("0.35")  # noqa: SLF001
        dialog._n1.setText("3")  # noqa: SLF001
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            with qtbot.waitSignal(dialog._worker_done_signal(), timeout=_WAIT_MS):
                dialog.start_sweep()
        script = dialog.script_text()
        assert 'sensor.sweep("optics.aperture_diameter_m"' in script
        assert "np.linspace(0.25, 0.35, 3)" in script

    def test_cancel_reports_honestly(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        dialog = _dialog(qtbot)
        dialog._param1.setCurrentText("optics.aperture_diameter_m")  # noqa: SLF001
        dialog._start1.setText("0.25")  # noqa: SLF001
        dialog._stop1.setText("0.45")  # noqa: SLF001
        dialog._n1.setText("30")  # noqa: SLF001
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            with qtbot.waitSignal(dialog._worker_done_signal(), timeout=_WAIT_MS):
                dialog.start_sweep()
                dialog._on_cancel_clicked()  # noqa: SLF001 — cancel immediately
        assert dialog.sweep_result is None
        assert "Cancelled" in dialog.status_text
        assert "No partial results" in dialog.status_text


class TestScriptReproduces:
    """CU-325: the emitted script must run and reproduce the plotted numbers."""

    def _run_dialog(self, qtbot):  # type: ignore[no-untyped-def]
        dialog = _dialog(qtbot)
        dialog._param1.setCurrentText("detector.pixel_pitch_x_um")  # noqa: SLF001
        dialog._start1.setText("10")  # noqa: SLF001 — µm entry
        dialog._stop1.setText("30")  # noqa: SLF001
        dialog._n1.setText("3")  # noqa: SLF001
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            with qtbot.waitSignal(dialog._worker_done_signal(), timeout=_WAIT_MS):
                dialog.start_sweep()
        return dialog

    def test_script_is_runnable_and_reproduces_canonical_values(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """exec() the emitted block against a capturing sensor: values match the run."""
        import numpy as np

        dialog = self._run_dialog(qtbot)
        script = dialog.script_text()

        captured: dict = {}

        class _FakeSensor:
            def sweep(self, param, values, **kwargs):  # type: ignore[no-untyped-def]
                captured["param"] = param
                captured["values"] = values
                return "ok"

        namespace = {"np": np, "sensor": _FakeSensor()}
        exec(script, namespace)  # noqa: S102 — the contract under test IS executability
        assert captured["param"] == "detector.pixel_pitch_x_um"
        # The script's values are exactly what the sweep consumed: the typed
        # input-unit numbers (the API converts once, inside sensor.set).
        assert captured["values"][0] == pytest.approx(10.0, rel=1e-9)
        assert captured["values"][-1] == pytest.approx(30.0, rel=1e-9)
        assert len(captured["values"]) == 3
        assert np.allclose(captured["values"], dialog.sweep_result.values)

    def test_2d_script_is_runnable(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """The 2-D emission defines BOTH axes (the old one referenced undefined values2)."""
        import numpy as np

        dialog = _dialog(qtbot)
        dialog._param1.setCurrentText("optics.aperture_diameter_m")  # noqa: SLF001
        dialog._start1.setText("0.25")  # noqa: SLF001
        dialog._stop1.setText("0.3")  # noqa: SLF001
        dialog._n1.setText("2")  # noqa: SLF001
        dialog._enable_2d.setChecked(True)  # noqa: SLF001
        dialog._param2.setCurrentText("detector.pixel_pitch_x_um")  # noqa: SLF001
        dialog._start2.setText("15")  # noqa: SLF001
        dialog._stop2.setText("25")  # noqa: SLF001
        dialog._n2.setText("2")  # noqa: SLF001
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            with qtbot.waitSignal(dialog._worker_done_signal(), timeout=_WAIT_MS):
                dialog.start_sweep()
        script = dialog.script_text()

        captured: dict = {}

        class _FakeSensor:
            def sweep_2d(self, p1, v1, p2, v2, **kwargs):  # type: ignore[no-untyped-def]
                captured.update(p1=p1, v1=v1, p2=p2, v2=v2)
                return "ok"

        exec(script, {"np": np, "sensor": _FakeSensor()})  # noqa: S102
        assert captured["p2"] == "detector.pixel_pitch_x_um"
        assert captured["v2"][0] == pytest.approx(15.0, rel=1e-9)  # µm, as entered


class TestGuards:
    def test_bounds_are_prevalidated_before_launch(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """A range escaping the schema bounds fails at 0/N with the bounds named."""
        dialog = _dialog(qtbot)
        dialog._param1.setCurrentText("optics.aperture_diameter_m")  # noqa: SLF001
        dialog._start1.setText("0.1")  # noqa: SLF001
        dialog._stop1.setText("50")  # noqa: SLF001 — schema max is 20 m
        dialog._n1.setText("5")  # noqa: SLF001
        dialog.start_sweep()
        assert "escapes the schema bounds" in dialog.status_text
        assert dialog._worker is None  # noqa: SLF001 — never launched

    def test_close_during_run_cancels_then_closes(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """Esc/Close mid-run never orphans the worker (CU-325)."""
        dialog = _dialog(qtbot)
        dialog._param1.setCurrentText("optics.aperture_diameter_m")  # noqa: SLF001
        dialog._start1.setText("0.25")  # noqa: SLF001
        dialog._stop1.setText("0.45")  # noqa: SLF001
        dialog._n1.setText("30")  # noqa: SLF001
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            with qtbot.waitSignal(dialog._worker_done_signal(), timeout=_WAIT_MS):
                dialog.start_sweep()
                dialog.reject()  # Esc during the run
                # The dialog is still open, cancelling — not closed with a live thread.
                assert "Cancelling" in dialog.status_text
        # After the worker settles the pending close completes and no thread runs.
        assert dialog._worker is None  # noqa: SLF001

    def test_progress_bar_hidden_until_a_run(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        dialog = _dialog(qtbot)
        assert not dialog._progress.isVisibleTo(dialog)  # noqa: SLF001
        assert "plots here" in dialog.status_text  # idle hint, not an empty label


class TestDefaultsAndPersistence:
    def test_range_seeds_around_the_current_value(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        dialog = _dialog(qtbot)
        dialog._param1.setCurrentText("optics.aperture_diameter_m")  # noqa: SLF001
        current = float(dialog._sensor.get_input("optics.aperture_diameter_m"))  # noqa: SLF001
        assert float(dialog._start1.text()) == pytest.approx(current * 0.5)  # noqa: SLF001
        assert float(dialog._stop1.text()) == pytest.approx(current * 1.5)  # noqa: SLF001

    def test_param2_never_defaults_equal_to_param1(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        dialog = _dialog(qtbot)
        target = dialog._param2.currentText()  # noqa: SLF001
        if dialog._param1.currentText() == target:  # noqa: SLF001 — ensure a real change
            dialog._param1.setCurrentText("optics.aperture_diameter_m")  # noqa: SLF001
            target = dialog._param2.currentText()  # noqa: SLF001
        dialog._param1.setCurrentText(target)  # noqa: SLF001 — collide via a real change
        assert dialog._param1.currentText() != dialog._param2.currentText()  # noqa: SLF001

    def test_last_spec_persists_across_openings(self, qtbot, tmp_path) -> None:  # type: ignore[no-untyped-def]
        from PySide6.QtCore import QSettings

        from radiant.gui.settings_store import SettingsStore

        store = SettingsStore(QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat))
        sensor = Sensor.from_yaml(_EXAMPLE)
        dialog = SweepDialog(sensor, ("snr",), settings=store)
        qtbot.addWidget(dialog)
        dialog._param1.setCurrentText("optics.aperture_diameter_m")  # noqa: SLF001
        dialog._start1.setText("0.25")  # noqa: SLF001
        dialog._stop1.setText("0.35")  # noqa: SLF001
        dialog._n1.setText("3")  # noqa: SLF001
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            with qtbot.waitSignal(dialog._worker_done_signal(), timeout=_WAIT_MS):
                dialog.start_sweep()

        reopened = SweepDialog(Sensor.from_yaml(_EXAMPLE), ("snr",), settings=store)
        qtbot.addWidget(reopened)
        assert reopened._param1.currentText() == "optics.aperture_diameter_m"  # noqa: SLF001
        assert reopened._start1.text() == "0.25"  # noqa: SLF001
        assert reopened._n1.text() == "3"  # noqa: SLF001


class TestPlotUnits:
    def test_1d_axis_is_labelled_in_the_entry_unit(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """CU-326 item 4: enter µm, read the plot in µm — with the unit on the axis."""
        dialog = _dialog(qtbot)
        dialog._param1.setCurrentText("detector.pixel_pitch_x_um")  # noqa: SLF001
        dialog._start1.setText("10")  # noqa: SLF001
        dialog._stop1.setText("30")  # noqa: SLF001
        dialog._n1.setText("3")  # noqa: SLF001
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            with qtbot.waitSignal(dialog._worker_done_signal(), timeout=_WAIT_MS):
                dialog.start_sweep()
        figure = dialog._canvas._figure  # noqa: SLF001
        axis = figure.axes[0]
        assert "µm" in axis.get_xlabel()
        line = axis.get_lines()[0]
        # Plotted x-values are the µm the analyst typed, not canonical metres.
        assert float(line.get_xdata()[0]) == pytest.approx(10.0, rel=1e-9)
        assert float(line.get_xdata()[-1]) == pytest.approx(30.0, rel=1e-9)
