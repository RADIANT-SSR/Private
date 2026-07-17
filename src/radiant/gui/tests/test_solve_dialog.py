"""Tests for the inverse-solve dialog (Tier-2 GT-6 / GUI-8)."""

from __future__ import annotations

import warnings
from pathlib import Path

import pytest

pytest.importorskip("PySide6", reason="GUI tests require the optional 'gui' extra")

from radiant.api.sensor import Sensor  # noqa: E402
from radiant.gui.widgets.solve_dialog import SolveDialog  # noqa: E402

_REPO = Path(__file__).resolve()
while not (_REPO / "pyproject.toml").exists():
    _REPO = _REPO.parent
_EXAMPLE = _REPO / "examples" / "mwir_leo_minimal.yaml"
_WAIT_MS = 240000


class TestSolveDialog:
    def test_solves_aperture_for_snr_and_applies(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        sensor = Sensor.from_yaml(_EXAMPLE)
        dialog = SolveDialog(sensor, ("snr",))
        qtbot.addWidget(dialog)
        dialog._param.setCurrentText("optics.aperture_diameter_m")  # noqa: SLF001
        dialog._target.setText("500")  # noqa: SLF001
        dialog._lo.setText("0.1")  # noqa: SLF001
        dialog._hi.setText("0.6")  # noqa: SLF001
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            with qtbot.waitSignal(dialog.solveSettled, timeout=_WAIT_MS):
                dialog.start_solve()
        result = dialog.solve_result
        assert result is not None
        assert result.achieved == pytest.approx(500.0, rel=1e-4)
        assert "evaluations" in dialog.status_text
        # Apply commits the one sensor.set on the live sensor.
        dialog._on_apply()  # noqa: SLF001
        assert sensor.get_input("optics.aperture_diameter_m") == pytest.approx(
            result.solution, rel=1e-12
        )
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            assert sensor.evaluate().metrics["snr"] == pytest.approx(500.0, rel=1e-4)

    def test_unbracketed_target_reports_actionably(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        sensor = Sensor.from_yaml(_EXAMPLE)
        dialog = SolveDialog(sensor, ("snr",))
        qtbot.addWidget(dialog)
        dialog._param.setCurrentText("optics.aperture_diameter_m")  # noqa: SLF001
        dialog._target.setText("1e9")  # noqa: SLF001 — unreachable
        dialog._lo.setText("0.25")  # noqa: SLF001
        dialog._hi.setText("0.35")  # noqa: SLF001
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            with qtbot.waitSignal(dialog.solveSettled, timeout=_WAIT_MS):
                dialog.start_solve()
        assert dialog.solve_result is None
        assert "failed" in dialog.status_text
