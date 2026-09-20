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


class TestF23CompareReadsStudies:
    """F-23: Tools ▸ Compare Config Files… refused a study file the operator had just
    saved, with "load it with ConfigurationSet.load(path)"."""

    def test_a_saved_study_compares_one_column_per_configuration(self, qtbot, tmp_path) -> None:  # type: ignore[no-untyped-def]
        """J-4.2: File ▸ Save As on a study, then add that file to the comparison."""
        from radiant.api.config_set import ConfigurationSet
        from radiant.gui.widgets.comparison_dialog import ComparisonDialog

        sensor = Sensor.load(_EXAMPLE)
        study = ConfigurationSet(sensor.clone(), names=("MWIR", "Wide"))
        study.configure("optics.aperture_diameter_m", [0.3, 0.5])
        study_path = tmp_path / "j42_study.yaml"
        study.save(study_path)

        dialog = ComparisonDialog(sensor)
        qtbot.addWidget(dialog)
        dialog.add_config(study_path)
        assert "2 configurations" in dialog._config_list.item(1).text()  # noqa: SLF001
        baselines = [dialog._baseline.itemText(i) for i in range(dialog._baseline.count())]  # noqa: SLF001
        assert baselines == ["current", "j42_study:MWIR", "j42_study:Wide"]
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            with qtbot.waitSignal(dialog.comparisonSettled, timeout=_WAIT_MS):
                dialog.start_comparison()
        assert "load failed" not in dialog.status_text
        cmp_ = dialog.comparison
        assert cmp_ is not None
        assert cmp_.labels == ("current", "j42_study:MWIR", "j42_study:Wide")
        snr = cmp_.row("snr")
        assert snr.best_index == 2  # the wide aperture wins SNR

    def test_a_bad_file_still_reports_plainly(self, qtbot, tmp_path) -> None:  # type: ignore[no-untyped-def]
        from radiant.gui.widgets.comparison_dialog import ComparisonDialog

        dialog = ComparisonDialog(Sensor.load(_EXAMPLE))
        qtbot.addWidget(dialog)
        bad = tmp_path / "junk.yaml"
        bad.write_text("nonsense: {here: true}\n", encoding="utf-8")
        dialog.add_config(bad)
        dialog.start_comparison()
        assert dialog.status_text.startswith("Config load failed")
        assert "ConfigurationSet.load" not in dialog.status_text


class TestF27DeclinedMetricsKeepTheirRow:
    """F-27: below the detection threshold `detection_range_m` simply disappeared —
    no pass/fail reading, the threshold not echoed anywhere near the result."""

    def test_below_threshold_detection_shows_the_reason_and_threshold(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """J-3.2 step 25: a point-source scene whose SNR at the reference range misses
        the threshold. The shipped air-to-air IRST example delivers SNR ~298; the
        schema's ceiling threshold (100) with a 10x shorter integration (SNR ~87)
        puts the target below it, exactly Raj's 5 km-visibility case."""
        import radiant

        irst = (
            Path(radiant.__file__).resolve().parent / "data" / "examples" / "air_to_air_irst.yaml"
        )
        sensor = (
            Sensor.load(irst)
            .set("performance.detection_snr_threshold", 100.0)
            .set("spectral_integration.integration_time_s", 1e-5)
        )
        window = RADIANTMainWindow(sensor, path=str(irst))
        qtbot.addWidget(window)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            with qtbot.waitSignal(window.evaluationFinished, timeout=_WAIT_MS):
                pass
        assert "detection_range_m" not in window.last_result.metrics  # the run declined it
        window.central_canvas.stage_center.select_stage("performance")
        cards = window.central_canvas.stage_center.pane("performance").metric_cards
        assert cards is not None
        assert "detection_range_m" in cards.declined_keys()
        assert "detection_range_m" not in cards.rendered_keys()  # not a computed value
        text = cards.value_text("detection_range_m")
        assert text.startswith("n/a (")
        assert "not detectable" in text and "100" in text  # the pass/fail and the threshold

    def test_niirs_declined_names_its_reason_on_the_pinned_card(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """F-19's other half: NIIRS refused (outside GIQE-5) says why, not 'not computed'."""
        from radiant.gui.metric_format import badge_display

        window = _window(qtbot)
        result = window.last_result
        assert "niirs" not in result.metrics
        value, reason = badge_display(result, "niirs")
        assert value == "n/a"
        assert reason is not None and reason != "not computed for this run"
        assert "GIQE" in reason or "extrapolat" in reason
