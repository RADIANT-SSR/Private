"""Round-2 R8 acceptance — left-dock parameter panel.

PLAN_v2_remediation_round2.md §9: width 200 px, collapsible
Observer/Target/Sun/Sensor/Mode sections, each parameter row =
label + slider + spinbox + units, ``state_changed(SceneState)``
emitted on any change with slider drag debounced to ~16 ms.

Skips cleanly when PySide6 is not installed.
"""

from __future__ import annotations

import math
import os
from typing import Iterator

import pytest

# Pin Qt binding before importing pyvistaqt / qtpy. See app/main.py for
# the same pattern in the application entry point.
os.environ.setdefault("QT_API", "pyside6")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtTest import QSignalSpy  # noqa: E402
from PySide6.QtWidgets import (  # noqa: E402
    QApplication,
    QComboBox,
    QDoubleSpinBox,
    QGroupBox,
    QRadioButton,
    QSlider,
)

from dev_tools.geometry_gui_v2.app.panels.parameters import (  # noqa: E402
    ParametersPanel,
    _NUMERIC_ROWS,
)
from dev_tools.geometry_gui_v2.app.state import SceneState  # noqa: E402


@pytest.fixture(scope="module")
def qt_app() -> Iterator[QApplication]:
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture()
def panel(qt_app: QApplication) -> ParametersPanel:
    return ParametersPanel()


# --- Section structure -----------------------------------------------------


def test_panel_has_five_collapsible_sections(panel: ParametersPanel) -> None:
    """PLAN_v2_remediation_round2.md §9: Observer / Target / Sun / Sensor / Mode."""
    boxes = panel.findChildren(QGroupBox)
    titles = sorted(b.title() for b in boxes)
    assert titles == sorted(["Observer", "Target", "Sun", "Sensor", "Mode"])
    for b in boxes:
        assert b.isCheckable(), f"section {b.title()!r} should be collapsible"


def test_panel_has_minimum_width_200(panel: ParametersPanel) -> None:
    """PLAN_v2_remediation_round2.md §9: width 200 px."""
    assert panel.minimumWidth() >= 200


# --- Row inventory ---------------------------------------------------------


def test_panel_has_all_19_numeric_rows(panel: ParametersPanel) -> None:
    """5 observer + 10 target + 2 sun + 2 sensor = 19 numeric rows.

    Each row pairs a QSlider with a QDoubleSpinBox; both must exist."""
    assert len(_NUMERIC_ROWS) == 19
    sliders = panel.findChildren(QSlider)
    spinboxes = panel.findChildren(QDoubleSpinBox)
    assert len(sliders) == 19
    assert len(spinboxes) == 19


def test_target_section_has_shape_dropdown(panel: ParametersPanel) -> None:
    combos = panel.findChildren(QComboBox)
    assert len(combos) == 1
    options = [combos[0].itemData(i) for i in range(combos[0].count())]
    assert options == ["sphere", "cylinder", "flat_plate", "box", "cone"]


def test_mode_section_has_eight_radio_buttons(panel: ParametersPanel) -> None:
    """4 regime-override radios + 4 background radios = 8 total."""
    radios = panel.findChildren(QRadioButton)
    assert len(radios) == 8


# --- Default population ----------------------------------------------------


def test_default_state_populates_every_slider(panel: ParametersPanel) -> None:
    """The panel must boot with SceneState.default() values reflected in
    every slider's display value (within one slider step)."""
    state = SceneState.default()
    for row in _NUMERIC_ROWS:
        canonical = float(getattr(state, row.field))
        display_expected = row.from_canonical(canonical)
        spinbox = panel._spinboxes[row.component_id]
        # Spinbox always carries the exact display value.
        assert math.isclose(
            spinbox.value(), display_expected, rel_tol=1e-9, abs_tol=1e-9
        ), f"{row.component_id}: spinbox={spinbox.value()} expected={display_expected}"


# --- Signal emission --------------------------------------------------------


def test_spinbox_change_emits_state_changed_immediately(
    panel: ParametersPanel,
) -> None:
    spy = QSignalSpy(panel.state_changed)
    spinbox = panel._spinboxes["obs-altitude"]
    spinbox.setValue(800.0)  # km
    assert spy.count() == 1
    state = spy.at(0)[0]
    assert isinstance(state, SceneState)
    assert math.isclose(state.observer_altitude_m, 800_000.0)


def test_shape_dropdown_change_emits_state_changed(panel: ParametersPanel) -> None:
    spy = QSignalSpy(panel.state_changed)
    panel._shape_combo.setCurrentIndex(1)  # cylinder
    assert spy.count() == 1
    assert spy.at(0)[0].target_shape == "cylinder"


def test_regime_radio_change_emits_state_changed(panel: ParametersPanel) -> None:
    spy = QSignalSpy(panel.state_changed)
    for btn in panel._regime_buttons.buttons():
        if btn.property("regime_value") == "extended":
            btn.setChecked(True)
            btn.click()
            break
    assert spy.count() >= 1
    assert spy.at(spy.count() - 1)[0].regime_override == "extended"


def test_background_radio_change_emits_state_changed(panel: ParametersPanel) -> None:
    spy = QSignalSpy(panel.state_changed)
    for btn in panel._background_buttons.buttons():
        if btn.property("background_value") == "ground":
            btn.setChecked(True)
            btn.click()
            break
    assert spy.count() >= 1
    assert spy.at(spy.count() - 1)[0].background_kind == "ground"


# --- Slider drag debounce --------------------------------------------------


def test_slider_drag_debounces_to_one_emit(
    panel: ParametersPanel, qt_app: QApplication
) -> None:
    """A burst of slider valueChanged signals (mid-drag) coalesces into a
    single ``state_changed`` emission once the drag pauses long enough
    for the 16 ms timer to expire.

    The timer is restarted on every tick, so 100 rapid ticks → 0
    immediate emissions, then exactly 1 emission after the wait."""
    spy = QSignalSpy(panel.state_changed)
    slider = panel._sliders["obs-altitude"]
    for v in range(100, 200):
        slider.setValue(v)
    # Mid-burst: nothing emitted yet (timer hasn't fired).
    assert spy.count() == 0
    # Wait for the 16 ms timer.
    qt_app.processEvents()
    import time
    time.sleep(0.05)
    qt_app.processEvents()
    assert spy.count() == 1
    # The terminal value (slider position 199) lands in the SceneState.
    state = spy.at(0)[0]
    expected_display = panel._spinboxes["obs-altitude"].value()
    expected_canonical = expected_display * 1000.0
    assert math.isclose(state.observer_altitude_m, expected_canonical, rel_tol=1e-3)


# --- Slider/spinbox synchronization ----------------------------------------


def test_slider_change_mirrors_to_spinbox(panel: ParametersPanel) -> None:
    slider = panel._sliders["sun-zenith"]
    spinbox = panel._spinboxes["sun-zenith"]
    slider.setValue(500)  # 50% of 0..180 = 90 deg
    assert math.isclose(spinbox.value(), 90.0, abs_tol=0.5)


def test_spinbox_change_mirrors_to_slider(panel: ParametersPanel) -> None:
    slider = panel._sliders["sun-zenith"]
    spinbox = panel._spinboxes["sun-zenith"]
    spinbox.setValue(45.0)
    # 45/180 * 1000 = 250
    assert abs(slider.value() - 250) <= 1


# --- set_state round-trip --------------------------------------------------


def test_set_state_does_not_re_emit_signal(panel: ParametersPanel) -> None:
    """External sync (host window pushing SceneState into panel) must not
    fire ``state_changed`` — that would create a feedback loop with the
    rebuild path that called set_state in the first place."""
    import dataclasses

    spy = QSignalSpy(panel.state_changed)
    new_state = dataclasses.replace(
        SceneState.default(),
        observer_altitude_m=1_200_000.0,
        target_shape="box",
        regime_override="extended",
        background_kind="ground",
    )
    panel.set_state(new_state)
    assert spy.count() == 0
    # And the panel reflects the pushed state.
    assert panel._spinboxes["obs-altitude"].value() == pytest.approx(1200.0)
    assert panel._shape_combo.currentData() == "box"


def test_unit_conversions_round_trip(panel: ParametersPanel) -> None:
    """The display ↔ canonical round-trip must be exact for the
    representative non-identity rows: km↔m, deg↔rad, µm↔m."""
    spinbox_alt = panel._spinboxes["obs-altitude"]
    spinbox_alt.setValue(600.0)
    assert math.isclose(panel.current_state().observer_altitude_m, 600_000.0)

    spinbox_look = panel._spinboxes["obs-look-angle"]
    spinbox_look.setValue(30.0)
    assert math.isclose(
        panel.current_state().observer_look_angle_rad, math.radians(30.0)
    )

    spinbox_pitch = panel._spinboxes["sen-pixel-pitch"]
    spinbox_pitch.setValue(15.0)
    assert math.isclose(panel.current_state().pixel_pitch_m, 15e-6)
