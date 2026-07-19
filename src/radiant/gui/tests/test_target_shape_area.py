"""The Target-shape panel's projected-area field and shape/area mutual exclusivity.

Shape and ``geometry.target.projected_area_m2`` are two ways to size the same target, so
the panel shows exactly one at a time: the scalar **Projected area** field when
``shape="none"``, the selected shape's dimension subset otherwise — never both (the GUI
half of "define one or the other"; the engine's shape-wins precedence is the backstop).
"""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6", reason="GUI tests require the optional 'gui' extra")

from radiant.gui.widgets.target_shape_panel import (  # noqa: E402
    _PROJECTED_AREA_PATH,
    TargetShapePanel,
)


def _panel(qtbot) -> TargetShapePanel:  # type: ignore[no-untyped-def]
    panel = TargetShapePanel(show_triad_toggle=False)
    qtbot.addWidget(panel)
    panel.set_shape_choices(("none", "sphere", "box"))
    return panel


class TestProjectedAreaExclusivity:
    def test_area_field_shown_only_for_none(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        panel = _panel(qtbot)
        panel.set_shape("none")
        assert not panel.projected_area_row.isHidden()
        assert panel.visible_dimensions() == ()  # no body dims for a shapeless target

    def test_shape_hides_area_shows_dims(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        panel = _panel(qtbot)
        panel.set_shape("box")
        assert panel.projected_area_row.isHidden()  # area field gone when a shape is picked
        assert set(panel.visible_dimensions()) == {
            "geometry.target.shape_length_m",
            "geometry.target.shape_width_m",
            "geometry.target.shape_height_m",
        }

    def test_never_both_at_once(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """For every shape choice, the area field and any dim rows are mutually exclusive."""
        panel = _panel(qtbot)
        for shape in ("none", "sphere", "box"):
            panel.set_shape(shape)
            area_shown = not panel.projected_area_row.isHidden()
            dims_shown = len(panel.visible_dimensions()) > 0
            assert not (area_shown and dims_shown), shape

    def test_area_row_binds_the_projected_area_dotpath(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        """Clicking the field edits geometry.target.projected_area_m2 (one API call)."""
        panel = _panel(qtbot)
        panel.set_shape("none")
        edits: list[str] = []
        panel.editRequested.connect(edits.append)
        panel.projected_area_row.value_button.click()
        assert edits == [_PROJECTED_AREA_PATH]

    def test_set_projected_area_updates_text(self, qtbot) -> None:  # type: ignore[no-untyped-def]
        panel = _panel(qtbot)
        panel.set_projected_area("240 m²")
        assert panel.projected_area_row.value_text() == "240 m²"
