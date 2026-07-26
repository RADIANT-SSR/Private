"""Where the red "C" sits, and what the grid-points boxes say (owner UX round, 2026-07-26).

Category D — the two *placement/wording* halves of the 2026-07-26 multi-configuration
refinement (§4.2c/§4.2d). The behavioural halves (per-configuration editing, the
configure affordance) live in ``test_configured_parameters.py``; these are the ones a
reader would otherwise only be able to check by eye:

1. **Badge placement, form rows.** The owner's *"move the red C just to the right of the
   variable name"*: in a :class:`~radiant.gui.widgets.field_row.FieldRow` the badge must
   occupy the grid column **between** the label and the value box, not the far-right
   column it had in Phase 4b. Asserted on the layout, so it holds offscreen and does not
   depend on a rendered geometry.
2. **Badge placement, tree rows.** A ``QTreeWidgetItem`` decoration icon can only paint
   *left* of the text, so the Parameter column now uses
   :class:`~radiant.gui.widgets.configured_name_delegate.ConfiguredNameDelegate`, whose
   :meth:`badge_rect` is the placement decision. Asserted directly (right of the text,
   inside the cell, nothing for a shared row) plus a paint smoke test.
3. **Grid-points wording.** The owner asked, of the configuration manager's grid-points
   fields, *"what are we setting here?"* — every one of them must now answer it.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QPainter, QPixmap, QStandardItem, QStandardItemModel
from PySide6.QtWidgets import QGridLayout, QStyleOptionViewItem

from radiant.api.config_set import ConfigurationSet
from radiant.api.sensor import Sensor
from radiant.gui.main_window import RADIANTMainWindow
from radiant.gui.widgets.configuration_manager_dialog import ConfigurationManagerDialog
from radiant.gui.widgets.configured_name_delegate import (
    BADGE_PX,
    CONFIGURED_ROLE,
    ConfiguredNameDelegate,
)
from radiant.gui.widgets.field_row import ElidingLabel, FieldRow

_EXAMPLE = Path(__file__).resolve().parents[4] / "examples" / "mwir_leo_minimal.yaml"

_FILTER_MIN = "spectral_integration.filter_min_um"
_FILTER_MAX = "spectral_integration.filter_max_um"

_WAIT_MS = 20000

# A cell wide enough that the badge never has to be clamped to the right edge.
_CELL = QRect(0, 0, 400, 20)


def _dual_band_study(tmp_path: Path) -> Path:
    cs = ConfigurationSet(Sensor.load(_EXAMPLE), names=["MWIR", "LWIR"])
    cs.configure(_FILTER_MIN, [3.5, 8.0])
    cs.configure(_FILTER_MAX, [5.0, 12.0])
    path = tmp_path / "dual_band_study.yaml"
    cs.save(path)
    return path


def _open_study(qtbot, tmp_path: Path) -> RADIANTMainWindow:  # type: ignore[no-untyped-def]
    path = _dual_band_study(tmp_path)
    window = RADIANTMainWindow(config_set=ConfigurationSet.load(path), path=str(path))
    qtbot.addWidget(window)
    with qtbot.waitSignal(window.evaluationFinished, timeout=_WAIT_MS):
        pass
    return window


def _grid_column(row: FieldRow, widget: object) -> int:
    """The grid column *widget* occupies inside *row*'s layout."""
    layout = row.layout()
    assert isinstance(layout, QGridLayout)
    index = layout.indexOf(widget)  # type: ignore[arg-type]
    assert index >= 0, "widget is not in the row's layout"
    return layout.getItemPosition(index)[1]


class TestFormRowBadgeSitsBesideTheLabel:
    def test_badge_column_is_between_the_label_and_the_value(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """Label → badge → value, by layout position (owner 2026-07-26)."""
        row = FieldRow("optics.aperture_diameter_m", "aperture_diameter_m", lambda _d: None)
        qtbot.addWidget(row)

        label = row.findChild(ElidingLabel)
        assert label is not None
        label_col = _grid_column(row, label)
        badge_col = _grid_column(row, row.badge)
        value_col = _grid_column(row, row.value_button)

        assert label_col < badge_col < value_col
        assert badge_col == label_col + 1

    def test_showing_the_badge_does_not_move_the_value_box(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """Its slot is reserved when hidden, so a configure never reflows the row."""
        row = FieldRow("optics.aperture_diameter_m", "aperture_diameter_m", lambda _d: None)
        qtbot.addWidget(row)
        row.resize(400, 30)
        row.show()
        qtbot.waitExposed(row)
        before = row.value_button.geometry()

        row.badge.show_for("MWIR: 3.5 um · LWIR: 8 um")
        row.layout().activate()

        assert row.value_button.geometry() == before

    def test_a_real_study_form_row_carries_the_badge_beside_its_label(  # type: ignore[no-untyped-def]
        self, qtbot, tmp_path
    ) -> None:
        """End to end: the shipped per-stage form, not a hand-built row."""
        window = _open_study(qtbot, tmp_path)
        rows = [
            row
            for row in window.central_canvas.stage_center.findChildren(FieldRow)
            if row.dotpath == _FILTER_MIN
        ]
        assert rows
        for row in rows:
            assert row.badge.isVisibleTo(row)
            assert _grid_column(row, row.badge) < _grid_column(row, row.value_button)


class TestTreeBadgeIsPaintedAfterTheName:
    @staticmethod
    def _index(configured: bool, text: str = "filter_min_um"):  # type: ignore[no-untyped-def]
        model = QStandardItemModel()
        item = QStandardItem(text)
        item.setData(True if configured else None, CONFIGURED_ROLE)
        model.appendRow(item)
        # The model is returned alongside the index so the caller keeps it alive.
        return model.index(0, 0), model

    def test_badge_rect_is_to_the_right_of_the_name_and_inside_the_cell(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        delegate = ConfiguredNameDelegate()
        index, _model = self._index(configured=True)
        option = QStyleOptionViewItem()
        option.rect = _CELL
        delegate.initStyleOption(option, index)

        rect = delegate.badge_rect(option, index)

        assert rect is not None
        text_width = option.fontMetrics.horizontalAdvance("filter_min_um")
        assert rect.left() > _CELL.left() + text_width  # strictly after the name
        assert rect.right() <= _CELL.right()
        assert rect.width() == BADGE_PX

    def test_a_shared_row_gets_no_badge(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        delegate = ConfiguredNameDelegate()
        index, _model = self._index(configured=False)
        option = QStyleOptionViewItem()
        option.rect = _CELL

        assert delegate.badge_rect(option, index) is None

    def test_a_long_name_clamps_the_badge_inside_the_cell(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """An elided name must push the badge to the column edge, never out of the row."""
        delegate = ConfiguredNameDelegate()
        index, _model = self._index(configured=True, text="a_very_long_" * 12)
        option = QStyleOptionViewItem()
        option.rect = _CELL
        delegate.initStyleOption(option, index)

        rect = delegate.badge_rect(option, index)

        assert rect is not None
        assert rect.right() <= _CELL.right()

    def test_painting_a_configured_row_marks_the_pixels_a_shared_row_leaves_blank(  # type: ignore[no-untyped-def]
        self, qtbot
    ) -> None:
        """Smoke: the delegate really draws the glyph, and only when configured."""
        delegate = ConfiguredNameDelegate()
        rendered: list[QPixmap] = []
        for configured in (False, True):
            index, _model = self._index(configured=configured)
            pixmap = QPixmap(_CELL.size())
            pixmap.fill(Qt.GlobalColor.white)
            painter = QPainter(pixmap)
            option = QStyleOptionViewItem()
            option.rect = _CELL
            try:
                delegate.paint(painter, option, index)
            finally:
                painter.end()
            rendered.append(pixmap)

        assert rendered[0].toImage() != rendered[1].toImage()


class TestGridPointsFieldsExplainThemselves:
    """Owner question: "what are we setting here?" — every grid-points box answers."""

    def test_shared_and_per_row_tooltips_name_wavelength_samples(self, qtbot, tmp_path) -> None:  # type: ignore[no-untyped-def]
        window = _open_study(qtbot, tmp_path)
        cs = window.configuration_set
        assert cs is not None
        dialog = ConfigurationManagerDialog(cs, window)
        qtbot.addWidget(dialog)

        shared_tip = dialog.shared_points_editor.toolTip()
        assert "wavelength samples" in shared_tip
        assert "500" in shared_tip

        for name in cs.names():
            row_tip = dialog.points_editor(name).toolTip()
            assert "wavelength samples" in row_tip
            assert "filter_min_um" in row_tip
            assert "blank" in row_tip.lower()
