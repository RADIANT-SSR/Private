"""GUI findings sweep, 2026-09-22 — two log lines from the September sweep.

Both pin fixed behaviour and both fail on the pre-fix code:

* the parameters dock rendered a file-valued row as its absolute path, so a
  dock capture carried the operator's home directory into a shipped figure;
* the plot column's 420 px *preference* was set as a *minimum*, which reached
  the enclosing page's minimum size hint and raised a horizontal scrollbar on
  a page whose content fitted — the "2 px wider than its viewport, nothing
  clipped" the Detector ▸ Noise tab showed.
"""

from __future__ import annotations

import warnings
from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QScrollArea, QTabWidget  # noqa: E402

from radiant.api.sensor import Sensor  # noqa: E402
from radiant.gui.main_window import RADIANTMainWindow  # noqa: E402
from radiant.gui.param_format import compact_path  # noqa: E402

_REPO = Path(__file__).resolve().parents[4]
_EXAMPLE = _REPO / "examples" / "mwir_leo_minimal.yaml"
#: Scenario 1.1 points ``source.target.emissivity_path`` at the bundled steel
#: curve, so its dock carries a file-valued row — the case this fix is about.
_WITH_A_FILE_ROW = (
    _REPO
    / "scenarios/01_sarah_systems_engineer/1.1_mwir_maritime_surveillance/inputs"
    / "1.1_mwir_maritime_surveillance.gui.yaml"
)
_WAIT_MS = 15000


def _load_window(qtbot, path: Path = _EXAMPLE) -> RADIANTMainWindow:  # type: ignore[no-untyped-def]
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        window = RADIANTMainWindow(Sensor.load(path))
    qtbot.addWidget(window)
    window.resize(1440, 900)
    with qtbot.waitSignal(window.evaluationFinished, timeout=_WAIT_MS):
        pass
    return window


class TestAFileRowShowsTheFileNotTheMachine:
    @pytest.mark.level0
    def test_an_absolute_path_is_shortened_to_its_last_two_components(self) -> None:
        assert (
            compact_path("/Users/someone/SSR_Tool/src/radiant/data/tables/emissivity/steel.csv")
            == ".../emissivity/steel.csv"
        )

    @pytest.mark.level0
    def test_a_windows_path_keeps_its_own_separator(self) -> None:
        """Rule 30: the rendered text must not look foreign on the host it ran on."""
        assert compact_path(r"C:\Users\someone\radiant\decks\A1.tp7") == r"...\decks\A1.tp7"

    @pytest.mark.level0
    @pytest.mark.parametrize(
        "text",
        ["simple", "23 km", "0.3", "rural", "steel.csv", "emissivity/steel.csv", "1177.9"],
    )
    def test_a_value_that_is_not_a_path_is_untouched(self, text: str) -> None:
        """Safe to apply to every row: it takes a separator *and* a suffixed tail."""
        assert compact_path(text) == text

    @pytest.mark.level0
    def test_a_path_without_a_suffixed_tail_is_untouched(self) -> None:
        assert compact_path("/a/b/c/d") == "/a/b/c/d"

    def test_the_dock_renders_the_short_form_and_hovers_the_full_one(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """The row shows the file; the absolute path is one hover away."""
        window = _load_window(qtbot, _WITH_A_FILE_ROW)
        from PySide6.QtWidgets import QTreeWidget

        trees = window.findChildren(QTreeWidget)
        tree = next(t for t in trees if t.objectName() == "parameterTree")
        rows: list[tuple[str, str]] = []
        stack = [tree.topLevelItem(i) for i in range(tree.topLevelItemCount())]
        while stack:
            item = stack.pop()
            if item is None:
                continue
            rows.append((item.text(1), item.toolTip(1)))
            stack.extend(item.child(i) for i in range(item.childCount()))
        shortened = [(value, tip) for value, tip in rows if value.startswith("...")]
        assert shortened, "scenario 1.1 pins a file-valued emissivity curve"
        assert any("steel.csv" in value for value, _tip in shortened)
        for value, tip in shortened:
            assert "/Users/" not in value and "\\Users\\" not in value
            assert tip.endswith(value.removeprefix("...")) or value.removeprefix("...") in tip


class TestThePlotColumnPreferenceIsNotAMinimum:
    def test_the_noise_tab_does_not_scroll_at_a_width_its_content_fits(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """At 1152 px the Noise and Detector + PSF pages fit and must not scroll.

        They used to. The plot column carried a 420 px *preference* as a
        ``setMinimumWidth``, which propagated into the page's own minimum size
        hint, so at a 400 px viewport the page declared 420 and Qt raised a
        horizontal scrollbar over content whose figures need 320. Measured on
        the pre-fix code: Noise scrolled 20 px and Detector + PSF 38 px, both
        with nothing clipped.
        """
        window = _load_window(qtbot)
        window.show()
        window.central_canvas.select_stage("detector")
        qtbot.wait(60)
        pane = window.central_canvas.stage_center.pane("detector")
        tab_widget = pane.findChildren(QTabWidget)[0]
        window.resize(1152, 900)
        qtbot.wait(150)
        offenders: list[str] = []
        for index in range(tab_widget.count()):
            if tab_widget.tabText(index) == "Inputs":
                continue  # the form's own floor is CU-363's, measured separately
            tab_widget.setCurrentIndex(index)
            qtbot.wait(100)
            page = tab_widget.widget(index)
            if not isinstance(page, QScrollArea):
                continue
            overflow = page.horizontalScrollBar().maximum()
            if overflow > 0:
                offenders.append(f"'{tab_widget.tabText(index)}' scrolls {overflow} px")
        assert not offenders, "; ".join(offenders)

    def test_the_plot_column_floor_is_one_readable_figure(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """The preference steers the opening split; the floor is the section floor."""
        from radiant.gui.widgets import stage_center as sc

        assert sc._PLOT_MIN_SECTION_WIDTH_PX < sc._PLOT_PREFERRED_WIDTH_PX
        window = _load_window(qtbot)
        window.show()
        window.central_canvas.select_stage("detector")
        qtbot.wait(60)
        pane = window.central_canvas.stage_center.pane("detector")
        tab_widget = pane.findChildren(QTabWidget)[0]
        tab_widget.setCurrentIndex(1)  # Noise
        qtbot.wait(100)
        page = tab_widget.widget(1)
        assert isinstance(page, QScrollArea)
        inner = page.widget()
        assert inner is not None
        # The page's minimum is the panel plus one readable figure, never the
        # 420 px preference: pre-fix this read 514 at the same layout.
        assert inner.minimumSizeHint().width() < 514

    def test_a_genuinely_narrow_pane_still_scrolls(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """The floor is lower, not gone: below one readable figure it still scrolls."""
        window = _load_window(qtbot)
        window.show()
        window.central_canvas.select_stage("detector")
        window.resize(1024, 900)
        qtbot.wait(150)
        pane = window.central_canvas.stage_center.pane("detector")
        tab_widget = pane.findChildren(QTabWidget)[0]
        tab_widget.setCurrentIndex(1)  # Noise
        qtbot.wait(100)
        page = tab_widget.widget(1)
        assert isinstance(page, QScrollArea)
        assert page.horizontalScrollBar().maximum() > 0
