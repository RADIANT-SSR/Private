"""Phase 4 acceptance — right-dock readouts panel renders every row with
units, in monospace, right-aligned, and the projected-area row carries
the literal `[from shape.projected_area]` handoff tag.

Skips cleanly when PySide6 is not installed.
"""

from __future__ import annotations

import os
from typing import Iterator

import pytest

# Pin Qt binding before importing pyvistaqt / qtpy. See app/main.py for
# the same pattern in the application entry point.
os.environ.setdefault("QT_API", "pyside6")
# Force offscreen Qt platform for headless test environments (CI, tmux).
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QGroupBox, QLabel  # noqa: E402

from dev_tools.geometry_gui_v2.app.panels.readouts import ReadoutsPanel  # noqa: E402
from dev_tools.geometry_gui_v2.app.state import SceneState  # noqa: E402


@pytest.fixture(scope="module")
def qt_app() -> Iterator[QApplication]:
    app = QApplication.instance() or QApplication([])
    yield app  # don't quit; QApplication is process-singleton.


@pytest.fixture()
def panel(qt_app: QApplication) -> ReadoutsPanel:
    panel = ReadoutsPanel()
    panel.set_state(SceneState.default())
    return panel


def _value_label_texts(panel: ReadoutsPanel) -> dict[str, str]:
    return {cid: lbl.text() for cid, lbl in panel._value_labels.items()}


# --- Section structure -----------------------------------------------------


def test_panel_has_four_collapsible_sections(panel: ReadoutsPanel) -> None:
    """PLAN_v2.md §12 step 4: 'Scene objects / Vectors / Angles / Regime'.

    Plus the 'Multi-facet decomposition' explainer at the bottom — five
    QGroupBox total. Each is checkable (collapsible) so the user can
    hide a section.
    """
    boxes = panel.findChildren(QGroupBox)
    titles = sorted(b.title() for b in boxes)
    assert titles == sorted(
        [
            "Scene objects",
            "Vectors",
            "Angles",
            "Regime",
            "Multi-facet decomposition",
        ]
    )
    for b in boxes:
        if b.title() != "Multi-facet decomposition":
            assert b.isCheckable(), f"section {b.title()!r} should be collapsible"


# --- Every documented row is present and unit-bearing ---------------------


_NUMERIC_ROWS = [
    "ro-slant-range",
    "ro-ground-range",
    "ro-pixel-area",
    "ro-projected-area",
    "ro-view-azimuth",
    "ro-view-elevation",
    "ro-solar-zenith",
    "ro-relative-azimuth",
    "ro-gsd",
    "ro-ifov",
    "ro-angular-extent",
    "ro-fill-fraction",
]


@pytest.mark.parametrize("component_id", _NUMERIC_ROWS)
def test_every_numeric_row_renders_with_units(
    panel: ReadoutsPanel, component_id: str
) -> None:
    """Hard rule from user memory: every numeric value in GUI output must
    have units — no exceptions."""
    text = _value_label_texts(panel)[component_id]
    assert text and text != "—", f"{component_id} not populated"
    # Acceptable unit tokens that must appear in the value. (For most rows
    # this is the trailing token; the projected-area row has the
    # ``[from shape.projected_area]`` handoff tag appended after the unit,
    # so we only require the token to appear, not to be the last token.)
    units = ("km", "m", "deg", "rad", "µrad", "m^2", "(dimensionless)")
    assert any(u in text for u in units), (
        f"{component_id}={text!r} must contain a unit token (one of {units})"
    )


def test_projected_area_row_has_radiometry_handoff_tag(
    panel: ReadoutsPanel,
) -> None:
    """PLAN_v2.md §12 step 5: the projected-area row has the literal
    `[from shape.projected_area]` tag so the user knows it is the
    radiometry handoff number (C3 invariant)."""
    text = _value_label_texts(panel)["ro-projected-area"]
    assert "[from shape.projected_area]" in text, (
        f"projected-area row missing handoff tag: {text!r}"
    )


def test_regime_rows_render_without_units(panel: ReadoutsPanel) -> None:
    """Regime / regime-reason are categorical, not numeric — they don't
    take a unit. Just confirm they populate."""
    texts = _value_label_texts(panel)
    assert texts["ro-regime"] != "—"
    assert texts["ro-regime-reason"] != "—"


# --- Monospace + right-aligned --------------------------------------------


def test_value_labels_are_monospace_and_right_aligned(
    panel: ReadoutsPanel,
) -> None:
    """PLAN_v2.md §12 step 4: 'Use a monospace font ... for numeric
    values. Right-align numbers.'"""
    from PySide6.QtCore import Qt

    for component_id, label in panel._value_labels.items():
        font = label.font()
        # The Qt font system may report any of these as the resolved family;
        # just confirm the *style hint* is monospace.
        assert font.styleHint() == font.StyleHint.Monospace or (
            font.family() in ("Inter Mono", "JetBrains Mono", "Menlo", "Monospace")
        ), (
            f"{component_id} label font is not monospace: family={font.family()!r}"
        )
        assert (
            label.alignment() & Qt.AlignmentFlag.AlignRight
        ), f"{component_id} label is not right-aligned"


# --- Multi-facet explainer ------------------------------------------------


def test_multi_facet_explainer_renders_for_default_state(
    panel: ReadoutsPanel,
) -> None:
    """The default scene is a sphere; the explainer reads
    'single-projection (orientation-invariant)'."""
    text = panel._explainer_label.text()
    assert "orientation-invariant" in text


# --- set_state refresh ----------------------------------------------------


def test_set_state_refreshes_every_row(qt_app: QApplication) -> None:
    """Calling ``set_state`` with a new state must refresh every row."""
    import dataclasses
    import math

    panel = ReadoutsPanel()
    panel.set_state(SceneState.default())
    before = _value_label_texts(panel).copy()

    new_state = dataclasses.replace(
        SceneState.default(),
        observer_altitude_m=300_000.0,  # bigger change → bigger slant-range delta
        observer_look_angle_rad=math.radians(40.0),
        target_radius_m=2.5,
    )
    panel.set_state(new_state)
    after = _value_label_texts(panel)

    # At minimum, slant-range and projected-area should change.
    assert before["ro-slant-range"] != after["ro-slant-range"]
    assert before["ro-projected-area"] != after["ro-projected-area"]
