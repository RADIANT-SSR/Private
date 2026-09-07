"""Tests for the Detector stage's FPA part-library card (Gap 119, plan Phase 3).

Real widgets, real `Sensor`, offscreen. The card's contract: one
``sensor.apply_fpa`` per Apply click; presets seed and explicit values win
(the report row says so); Open datasheet resolves the committed PDF in a repo
checkout and falls back to the citation URL otherwise.
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
from radiant.gui.widgets.fpa_part_selector import FPAPartSelector  # noqa: E402
from radiant.gui.widgets.stage_center import StagePane  # noqa: E402

_EXAMPLE = Path(__file__).resolve().parents[4] / "examples" / "mwir_leo_minimal.yaml"


def _select(widget: FPAPartSelector, part: str) -> None:
    combo = widget._combo
    for i in range(combo.count()):
        if combo.itemData(i) == part:
            combo.setCurrentIndex(i)
            return
    raise AssertionError(f"part {part!r} not in combo")


@pytest.fixture()
def sensor() -> Sensor:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return Sensor.from_yaml(_EXAMPLE)


class TestPartList:
    def test_every_library_part_is_listed(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        widget = FPAPartSelector()
        qtbot.addWidget(widget)
        listed = {
            widget._combo.itemData(i)
            for i in range(widget._combo.count())
            if widget._combo.itemData(i)
        }
        assert listed == {info.name for info in available_fpa_parts()}
        assert len(listed) >= 21

    def test_placeholder_disables_apply(self, qtbot, sensor: Sensor) -> None:  # type: ignore[no-untyped-def]
        widget = FPAPartSelector()
        qtbot.addWidget(widget)
        widget.bind_sensor(sensor)
        assert widget.selected_part() is None
        assert not widget._apply.isEnabled()

    def test_selection_shows_blurb_and_enables(self, qtbot, sensor: Sensor) -> None:  # type: ignore[no-untyped-def]
        widget = FPAPartSelector()
        qtbot.addWidget(widget)
        widget.bind_sensor(sensor)
        _select(widget, "teledyne-h2rg-2p5")
        assert widget._apply.isEnabled()
        assert widget._open_doc.isEnabled()
        assert "datasheet" in widget._blurb.text()


class TestApply:
    def test_apply_sets_values_and_reports(self, qtbot, sensor: Sensor) -> None:  # type: ignore[no-untyped-def]
        widget = FPAPartSelector()
        qtbot.addWidget(widget)
        widget.bind_sensor(sensor)
        _select(widget, "geosnap-18")
        with qtbot.waitSignal(widget.presetApplied, timeout=2000) as blocker:
            widget._apply.click()
        assert blocker.args == ["geosnap-18"]
        # The example pins read noise etc. — explicit wins, and the row says so.
        text = widget._report_label.text()
        assert "applied" in text and "kept" in text
        assert widget._report_row.isVisibleTo(widget)
        # A value the example does not pin arrived with the preset.
        sensor._params.resolve()
        assert sensor._params.get("detector.detector_temperature_K") == pytest.approx(
            110.0, rel=1e-12
        )

    def test_apply_report_matches_sensor_record(self, qtbot, sensor: Sensor) -> None:  # type: ignore[no-untyped-def]
        widget = FPAPartSelector()
        qtbot.addWidget(widget)
        widget.bind_sensor(sensor)
        _select(widget, "teledyne-h2rg-2p5")
        widget._apply.click()
        assert sensor.fpa_applications[-1] is widget._last_report


class TestOpenDocument:
    def test_repo_checkout_resolves_committed_pdf(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        widget = FPAPartSelector()
        qtbot.addWidget(widget)
        _select(widget, "geosnap-18")
        target = widget._document_target()
        assert target is not None and target.isLocalFile()
        assert target.toLocalFile().endswith("geosnap18_datasheet_2022.pdf")

    def test_web_page_part_falls_back_to_url(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        # senseeker parts cite a web page only (no committed file).
        widget = FPAPartSelector()
        qtbot.addWidget(widget)
        _select(widget, "senseeker-magnesium-rp0092")
        target = widget._document_target()
        assert target is not None and not target.isLocalFile()
        assert target == QUrl("https://www.senseeker.com/products/RP0092-D120.htm")

    def test_open_uses_desktop_services(self, qtbot, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        opened: list[QUrl] = []
        monkeypatch.setattr(
            "radiant.gui.widgets.fpa_part_selector.QDesktopServices.openUrl",
            lambda url: opened.append(url) or True,
        )
        widget = FPAPartSelector()
        qtbot.addWidget(widget)
        _select(widget, "geosnap-18")
        widget._open_doc.click()
        assert len(opened) == 1


class TestStageIntegration:
    def test_detector_pane_hosts_selector_and_reevaluates(self, qtbot, sensor: Sensor) -> None:  # type: ignore[no-untyped-def]
        pane = StagePane("detector", STAGE_COMPOSITIONS["detector"])
        qtbot.addWidget(pane)
        pane.bind_sensor(sensor, {})
        selector = pane.fpa_part_selector
        assert selector is not None
        _select(selector, "geosnap-18")
        # A successful apply re-enters the host's parameterEdited pipeline.
        with qtbot.waitSignal(pane.parameterEdited, timeout=2000):
            selector._apply.click()
