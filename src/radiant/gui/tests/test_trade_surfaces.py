"""Pinning tests for CU-375 — trade surfaces (GUI usability audit 2026-09).

Each test drives the real surface — the sweep, solve and compare dialogs, the batch
scaffold, the Performance metric cards — on the shipped example (or the audit's
from-scratch configuration) and asserts the fixed behaviour. Every test here failed on
the pre-fix code; the finding numbers refer to ``docs/reports/gui_usability_audit_2026-09/``.
"""

from __future__ import annotations

import warnings
from pathlib import Path

import pytest

pytest.importorskip("PySide6", reason="GUI tests require the optional 'gui' extra")

from radiant.api.sensor import Sensor  # noqa: E402
from radiant.gui.main_window import RADIANTMainWindow  # noqa: E402

_EXAMPLE = Path(__file__).resolve().parents[4] / "examples" / "mwir_leo_minimal.yaml"
_WAIT_MS = 15000


def _window(qtbot) -> RADIANTMainWindow:  # type: ignore[no-untyped-def]
    window = RADIANTMainWindow(Sensor.load(_EXAMPLE), path=str(_EXAMPLE))
    qtbot.addWidget(window)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        with qtbot.waitSignal(window.evaluationFinished, timeout=_WAIT_MS):
            pass
    return window


class TestF24BatchScaffoldStartsFromTheScreen:
    """F-24: Run ▸ Batch Run… scaffolded `base = {}` instead of the displayed sensor."""

    def test_scaffold_runs_from_the_displayed_sensor(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """J-4.3: the scaffold's base is the sensor the console binds, and it runs."""
        window = _window(qtbot)
        window.action("run.batch").trigger()
        text = window._scripting_window.editor.current_tab().toPlainText()  # noqa: SLF001
        assert "base = {}" not in text
        assert "base = sensor.to_dict()" in text
        namespace: dict[str, object] = {"sensor": window.sensor}
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            exec(compile(text, "<batch scaffold>", "exec"), namespace)  # noqa: S102
        batch = namespace["batch"]
        assert batch.n_failed == 0  # type: ignore[attr-defined]
        assert len(batch.rows) == 4  # type: ignore[attr-defined] — two axes of two labels
        pivot = batch.pivot("snr", rows="aperture", cols="t_int")  # type: ignore[attr-defined]
        base_snr = window.last_result.metrics["snr"]
        values = [v for row in pivot.values() for v in row.values()]
        assert len(values) == 4
        # Every cell is the on-screen configuration with one aperture and one t_int
        # changed — the same order of magnitude as the on-screen SNR, never a blank
        # configuration's.
        assert all(0.1 * base_snr < v < 10 * base_snr for v in values), values
