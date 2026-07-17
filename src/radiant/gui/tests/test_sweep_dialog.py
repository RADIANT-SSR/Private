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

    def test_axis_values_convert_input_to_canonical(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        dialog = _dialog(qtbot)
        values = dialog._axis_values(  # noqa: SLF001
            "detector.pixel_pitch_x_um", "10", "30", "3", log=False
        )
        # Entered in µm; sweep consumes canonical metres.
        assert values[0] == pytest.approx(10e-6, rel=1e-12)
        assert values[-1] == pytest.approx(30e-6, rel=1e-12)

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
