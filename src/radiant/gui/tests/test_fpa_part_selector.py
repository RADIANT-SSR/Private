"""Tests for the Detector stage's FPA part-library row + picker dialog (Gap 119 Phase 3).

Live-review iteration (2026-09-06): the card is one compact row; browsing
lives in :class:`FPAPartPickerDialog` (table with Kind/Class/Band/census
columns). Contract: one ``sensor.apply_fpa`` per accepted pick; presets seed
and explicit values win (the status row says so); Open datasheet resolves the
committed PDF in a repo checkout and falls back to the citation URL.
"""

from __future__ import annotations

import warnings
from pathlib import Path

import pytest

pytest.importorskip("PySide6", reason="GUI tests require the optional 'gui' extra")

from PySide6.QtCore import QUrl  # noqa: E402

from radiant.api.fpa_preset import available_fpa_parts  # noqa: E402
from radiant.api.sensor import Sensor  # noqa: E402
from radiant.gui.stage_views import STAGE_COMPOSITIONS  # noqa: E402
from radiant.gui.widgets.fpa_part_picker_dialog import FPAPartPickerDialog  # noqa: E402
from radiant.gui.widgets.fpa_part_selector import FPAPartSelector  # noqa: E402
from radiant.gui.widgets.stage_center import StagePane  # noqa: E402

_EXAMPLE = Path(__file__).resolve().parents[4] / "examples" / "mwir_leo_minimal.yaml"


@pytest.fixture()
def sensor() -> Sensor:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return Sensor.from_yaml(_EXAMPLE)


class TestPickerDialog:
    def test_every_library_part_is_listed(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        parts = available_fpa_parts()
        dialog = FPAPartPickerDialog(parts)
        qtbot.addWidget(dialog)
        assert dialog._table.rowCount() == len(parts) >= 21

    def test_roic_parts_are_marked(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        dialog = FPAPartPickerDialog(available_fpa_parts())
        qtbot.addWidget(dialog)
        dialog.select_part("senseeker-calcium-rp0033")
        row = dialog._table.currentRow()
        assert "ROIC" in dialog._table.item(row, 1).text()
        assert "Gap 121" in dialog._details.text()
        dialog.select_part("geosnap-18")
        row = dialog._table.currentRow()
        assert dialog._table.item(row, 1).text() == "FPA"

    def test_selection_enables_apply_and_details(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        dialog = FPAPartPickerDialog(available_fpa_parts())
        qtbot.addWidget(dialog)
        assert dialog.selected_part() is None
        assert not dialog._ok.isEnabled()
        dialog.select_part("teledyne-h2rg-2p5")
        assert dialog.selected_part() == "teledyne-h2rg-2p5"
        assert dialog._ok.isEnabled()
        assert "datasheet" in dialog._details.text() or "Sources" in dialog._details.text()


class TestApply:
    def test_apply_sets_values_and_reports(self, qtbot, sensor: Sensor) -> None:  # type: ignore[no-untyped-def]
        widget = FPAPartSelector()
        qtbot.addWidget(widget)
        widget.bind_sensor(sensor)
        assert widget._choose.isEnabled()
        with qtbot.waitSignal(widget.presetApplied, timeout=2000) as blocker:
            widget.apply_part("geosnap-18")
        assert blocker.args == ["geosnap-18"]
        # The example pins read noise etc. — explicit wins, and the row says so.
        text = widget._status.text()
        assert "applied" in text and "kept" in text
        assert widget._details.isVisibleTo(widget)
        assert widget.current_part() == "geosnap-18"
        # A value the example does not pin arrived with the preset.
        sensor._params.resolve()
        assert sensor._params.get("detector.detector_temperature_K") == pytest.approx(
            110.0, rel=1e-12
        )

    def test_apply_report_matches_sensor_record(self, qtbot, sensor: Sensor) -> None:  # type: ignore[no-untyped-def]
        widget = FPAPartSelector()
        qtbot.addWidget(widget)
        widget.bind_sensor(sensor)
        widget.apply_part("teledyne-h2rg-2p5")
        assert sensor.fpa_applications[-1] is widget._last_report

    def test_unbound_disables_choose(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        widget = FPAPartSelector()
        qtbot.addWidget(widget)
        widget.bind_sensor(None)
        assert not widget._choose.isEnabled()


class TestOpenDocument:
    def test_repo_checkout_resolves_committed_pdf(self, qtbot, sensor: Sensor) -> None:  # type: ignore[no-untyped-def]
        widget = FPAPartSelector()
        qtbot.addWidget(widget)
        widget.bind_sensor(sensor)
        widget.apply_part("geosnap-18")
        target = widget._document_target()
        assert target is not None and target.isLocalFile()
        assert target.toLocalFile().endswith("geosnap18_datasheet_2022.pdf")

    def test_web_page_part_falls_back_to_url(self, qtbot, sensor: Sensor) -> None:  # type: ignore[no-untyped-def]
        # Senseeker parts cite a web page only (no committed file).
        widget = FPAPartSelector()
        qtbot.addWidget(widget)
        widget.bind_sensor(sensor)
        widget.apply_part("senseeker-magnesium-rp0092")
        target = widget._document_target()
        assert target is not None and not target.isLocalFile()
        assert target == QUrl("https://www.senseeker.com/products/RP0092-D120.htm")

    def test_open_uses_desktop_services(self, qtbot, sensor: Sensor, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        opened: list[QUrl] = []
        monkeypatch.setattr(
            "radiant.gui.widgets.fpa_part_selector.QDesktopServices.openUrl",
            lambda url: opened.append(url) or True,
        )
        widget = FPAPartSelector()
        qtbot.addWidget(widget)
        widget.bind_sensor(sensor)
        widget.apply_part("geosnap-18")
        widget._open_doc.click()
        assert len(opened) == 1


class TestStageIntegration:
    def test_detector_pane_hosts_selector_and_reevaluates(self, qtbot, sensor: Sensor) -> None:  # type: ignore[no-untyped-def]
        pane = StagePane("detector", STAGE_COMPOSITIONS["detector"])
        qtbot.addWidget(pane)
        pane.bind_sensor(sensor, {})
        selector = pane.fpa_part_selector
        assert selector is not None
        # A successful apply re-enters the host's parameterEdited pipeline.
        with qtbot.waitSignal(pane.parameterEdited, timeout=2000):
            selector.apply_part("geosnap-18")
