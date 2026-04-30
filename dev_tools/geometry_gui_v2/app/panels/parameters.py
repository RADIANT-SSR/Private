"""Left-dock parameter panel — every slider, spinbox, and mode toggle.

PLAN_v2.md §6 (salvage list): "the slider inventory in PLAN v1 §6 — lift
verbatim. Same ranges, units, RADIANT field bindings."

PLAN_v2_remediation_round2.md §9 (R8) — the work order this module
delivers:

  * Width 200 px.
  * Collapsible sections: Observer / Target / Sun / Sensor / Mode.
  * Each parameter row: label + slider + spinbox + units.
  * Emits ``state_changed(SceneState)`` on any change, debounced to
    16 ms during drag.
  * Placed in a ``QDockWidget`` on the left side.

Architecture notes:

  * **Slider integer mapping.** ``QSlider`` is integer-valued. Each slider
    runs 0..1000; a row's display range maps linearly across that span.
    The companion ``QDoubleSpinBox`` holds the canonical floating-point
    display value with row-appropriate decimals. The two are kept
    bidirectionally in sync (slider → spinbox commits immediately;
    spinbox → slider commits immediately) using ``blockSignals`` to
    break the would-be feedback loop.

  * **Drag debounce.** While the user is dragging the slider, raw
    ``valueChanged`` ticks fire every pixel of mouse motion. Emitting
    ``state_changed`` on every tick would saturate the rebuild path.
    A 16 ms ``QTimer`` (single-shot, restartable) coalesces the tail
    of any slider drag into one terminal emit. The spinbox commits
    immediately — slow keyboard input doesn't need debouncing.

  * **Display ↔ canonical units.** Every slider renders a display value
    in the unit the user expects (km, deg, µm). The conversion to the
    canonical SceneState unit (m, rad, m) lives in the row's
    ``to_canonical``/``from_canonical`` lambdas, mirroring the v1
    callback layer so canonical units stay locked to the dataclass
    (CLAUDE.md §"Units").

  * **Rule 19.** Mode toggles (regime override, background kind, target
    shape) are categorical, not numeric — they live in this same module
    because they are part of the same "parameter input" surface that
    the user reaches for. Splitting them off into a third file would
    fragment the panel without making any single piece more reusable.
"""

from __future__ import annotations

import dataclasses
import math
from dataclasses import dataclass
from typing import Callable, Final

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QRadioButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from dev_tools.geometry_gui_v2.app.state import (
    BackgroundKind,
    RegimeOverride,
    SceneState,
    ShapeKind,
)


# ---------------------------------------------------------------------------
# Numeric-row inventory — lifted verbatim from v1 (PLAN_v2.md §6 salvage).
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _NumericRow:
    """One slider/spinbox row.

    ``field`` is the canonical SceneState field name (in canonical units).
    ``to_canonical`` converts the display value the user sees into the
    canonical unit before being applied to SceneState; ``from_canonical``
    is the inverse and is used to populate the row from a SceneState.
    """

    section: str
    component_id: str
    label: str
    display_units: str
    field: str
    display_min: float
    display_max: float
    display_step: float
    decimals: int
    to_canonical: Callable[[float], float]
    from_canonical: Callable[[float], float]


def _km_to_m(v: float) -> float:
    return v * 1_000.0


def _m_to_km(v: float) -> float:
    return v / 1_000.0


def _deg_to_rad(v: float) -> float:
    return math.radians(v)


def _rad_to_deg(v: float) -> float:
    return math.degrees(v)


def _um_to_m(v: float) -> float:
    return v * 1e-6


def _m_to_um(v: float) -> float:
    return v * 1e6


def _identity(v: float) -> float:
    return v


# Display-unit row inventory. Every range, step, and default mirrors the
# v1 slider files so the round-2 panel preserves the calibrated UX.
_NUMERIC_ROWS: Final[list[_NumericRow]] = [
    # ---- Observer ----
    _NumericRow("Observer", "obs-altitude", "Altitude", "km",
                "observer_altitude_m",
                100.0, 36_000.0, 50.0, 1, _km_to_m, _m_to_km),
    _NumericRow("Observer", "obs-look-angle", "Look angle (off-nadir)", "deg",
                "observer_look_angle_rad",
                0.0, 60.0, 0.5, 2, _deg_to_rad, _rad_to_deg),
    _NumericRow("Observer", "obs-yaw", "Yaw", "deg",
                "observer_yaw_rad",
                -30.0, 30.0, 0.5, 2, _deg_to_rad, _rad_to_deg),
    _NumericRow("Observer", "obs-pitch", "Pitch", "deg",
                "observer_pitch_rad",
                -30.0, 30.0, 0.5, 2, _deg_to_rad, _rad_to_deg),
    _NumericRow("Observer", "obs-roll", "Roll", "deg",
                "observer_roll_rad",
                -30.0, 30.0, 0.5, 2, _deg_to_rad, _rad_to_deg),
    # ---- Target (numeric — shape selector handled separately) ----
    _NumericRow("Target", "tgt-altitude", "Altitude", "km",
                "target_altitude_m",
                0.0, 2_000.0, 1.0, 1, _km_to_m, _m_to_km),
    _NumericRow("Target", "tgt-radius", "Radius", "m",
                "target_radius_m",
                0.01, 100.0, 0.1, 2, _identity, _identity),
    _NumericRow("Target", "tgt-length", "Length", "m",
                "target_length_m",
                0.01, 100.0, 0.1, 2, _identity, _identity),
    _NumericRow("Target", "tgt-width", "Width", "m",
                "target_width_m",
                0.01, 100.0, 0.1, 2, _identity, _identity),
    _NumericRow("Target", "tgt-height", "Height", "m",
                "target_height_m",
                0.01, 100.0, 0.1, 2, _identity, _identity),
    _NumericRow("Target", "tgt-base-radius", "Base radius (cone)", "m",
                "target_base_radius_m",
                0.01, 100.0, 0.1, 2, _identity, _identity),
    _NumericRow("Target", "tgt-yaw", "Yaw", "deg",
                "target_yaw_rad",
                -180.0, 180.0, 1.0, 1, _deg_to_rad, _rad_to_deg),
    _NumericRow("Target", "tgt-pitch", "Pitch", "deg",
                "target_pitch_rad",
                -180.0, 180.0, 1.0, 1, _deg_to_rad, _rad_to_deg),
    _NumericRow("Target", "tgt-roll", "Roll", "deg",
                "target_roll_rad",
                -180.0, 180.0, 1.0, 1, _deg_to_rad, _rad_to_deg),
    _NumericRow("Target", "tgt-fill-fraction", "Fill fraction", "—",
                "target_fill_fraction",
                0.001, 1.0, 0.001, 3, _identity, _identity),
    # ---- Sun ----
    _NumericRow("Sun", "sun-zenith", "Solar zenith θ_s", "deg",
                "solar_zenith_rad",
                0.0, 180.0, 1.0, 1, _deg_to_rad, _rad_to_deg),
    _NumericRow("Sun", "sun-azimuth", "Relative azimuth Δφ", "deg",
                "relative_azimuth_rad",
                -180.0, 180.0, 1.0, 1, _deg_to_rad, _rad_to_deg),
    # ---- Sensor ----
    _NumericRow("Sensor", "sen-focal", "Focal length", "m",
                "focal_length_m",
                0.1, 10.0, 0.1, 2, _identity, _identity),
    _NumericRow("Sensor", "sen-pixel-pitch", "Pixel pitch", "µm",
                "pixel_pitch_m",
                1.0, 50.0, 0.5, 2, _um_to_m, _m_to_um),
]


_SHAPE_OPTIONS: Final[list[tuple[str, ShapeKind]]] = [
    ("Sphere", "sphere"),
    ("Cylinder", "cylinder"),
    ("Flat plate", "flat_plate"),
    ("Box", "box"),
    ("Cone", "cone"),
]


_REGIME_OPTIONS: Final[list[tuple[str, RegimeOverride]]] = [
    ("Auto", "auto"),
    ("Extended", "extended"),
    ("Sub-pixel", "sub_pixel"),
    ("Point source", "point_source"),
]


_BACKGROUND_OPTIONS: Final[list[tuple[str, BackgroundKind]]] = [
    ("None", "none"),
    ("Cold space", "cold_space"),
    ("Ground", "ground"),
    ("At-aperture", "at_aperture"),
]


# ---------------------------------------------------------------------------
# Slider scaling helpers.
# ---------------------------------------------------------------------------

# Each slider has 1001 integer positions (0..1000); mapping to display range
# preserves three decimals over a 0..1 slider (good enough for fill_fraction)
# and produces ~0.001 deg over the look-angle range — well below the row's
# native step.
_SLIDER_RESOLUTION: Final[int] = 1000


def _display_to_slider_int(row: _NumericRow, display_value: float) -> int:
    span = row.display_max - row.display_min
    if span <= 0:
        return 0
    fraction = (display_value - row.display_min) / span
    fraction = min(max(fraction, 0.0), 1.0)
    return int(round(fraction * _SLIDER_RESOLUTION))


def _slider_int_to_display(row: _NumericRow, slider_value: int) -> float:
    span = row.display_max - row.display_min
    fraction = slider_value / _SLIDER_RESOLUTION
    return row.display_min + fraction * span


# ---------------------------------------------------------------------------
# Panel.
# ---------------------------------------------------------------------------


# 16 ms = ~60 Hz. Sliders' ``valueChanged`` fires on every pixel of mouse
# motion; without debounce the rebuild path saturates. The terminal value
# always lands because ``QTimer.start()`` restarts a pending interval, so
# the last user-input position triggers the final emit ~16 ms after the
# user stops dragging.
_DRAG_DEBOUNCE_MS: Final[int] = 16


class ParametersPanel(QWidget):
    """Left-dock widget: collapsible parameter input groups.

    Holds a numeric row per slider in PLAN_v2 §6's verbatim inventory,
    plus mode toggles (target shape, regime override, background kind).
    Emits ``state_changed(SceneState)`` whenever any control commits a
    change; the slider rows debounce drag input to ~16 ms.

    The host window (``app.main``) listens to ``state_changed`` and runs
    the full scene rebuild + readouts refresh. The panel itself keeps no
    plotter or scene reference — it is pure Qt.
    """

    state_changed = Signal(SceneState)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        # PLAN_v2_remediation_round2.md §9: width 200 px.
        self.setMinimumWidth(200)

        self._state: SceneState = SceneState.default()
        self._sliders: dict[str, QSlider] = {}
        self._spinboxes: dict[str, QDoubleSpinBox] = {}
        self._rows_by_id: dict[str, _NumericRow] = {
            row.component_id: row for row in _NUMERIC_ROWS
        }

        # Pending-drag debounce timer. Emits the *last* slider value when
        # the user stops moving for ``_DRAG_DEBOUNCE_MS`` ms.
        self._drag_timer = QTimer(self)
        self._drag_timer.setSingleShot(True)
        self._drag_timer.setInterval(_DRAG_DEBOUNCE_MS)
        self._drag_timer.timeout.connect(self._emit_state_changed)
        # Set when a slider is mid-drag. Pending state lives on the
        # spinbox (it always carries the canonical display value), so we
        # only need a flag, not a value queue.
        self._drag_pending: bool = False

        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 8, 8, 8)
        outer.setSpacing(8)

        # Bucket numeric rows by section, preserving inventory order.
        sections: dict[str, list[_NumericRow]] = {}
        for row in _NUMERIC_ROWS:
            sections.setdefault(row.section, []).append(row)

        # ---- Observer / Target / Sun / Sensor: numeric sections ----
        # The Target section gets a leading shape dropdown built into
        # the same QGroupBox so the user reads it as one panel.
        for section_title, rows in sections.items():
            group = QGroupBox(section_title)
            group.setCheckable(True)
            group.setChecked(True)
            group_layout = QVBoxLayout(group)
            group_layout.setContentsMargins(8, 8, 8, 8)
            group_layout.setSpacing(4)

            if section_title == "Target":
                shape_row = self._build_shape_row()
                group_layout.addLayout(shape_row)

            form = QFormLayout()
            form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
            form.setHorizontalSpacing(6)
            form.setVerticalSpacing(2)
            for row in rows:
                form.addRow(QLabel(row.label), self._build_numeric_row(row))
            group_layout.addLayout(form)
            outer.addWidget(group)

        # ---- Mode section: regime override + background ----
        mode_group = QGroupBox("Mode")
        mode_group.setCheckable(True)
        mode_group.setChecked(True)
        mode_layout = QVBoxLayout(mode_group)
        mode_layout.setContentsMargins(8, 8, 8, 8)
        mode_layout.setSpacing(4)
        mode_layout.addWidget(QLabel("Regime override"))
        self._regime_buttons = QButtonGroup(self)
        for label_text, value in _REGIME_OPTIONS:
            btn = QRadioButton(label_text)
            btn.setProperty("regime_value", value)
            if value == self._state.regime_override:
                btn.setChecked(True)
            self._regime_buttons.addButton(btn)
            mode_layout.addWidget(btn)
        self._regime_buttons.buttonClicked.connect(self._on_regime_clicked)

        mode_layout.addSpacing(6)
        mode_layout.addWidget(QLabel("Background"))
        self._background_buttons = QButtonGroup(self)
        for label_text, value in _BACKGROUND_OPTIONS:
            btn = QRadioButton(label_text)
            btn.setProperty("background_value", value)
            if value == self._state.background_kind:
                btn.setChecked(True)
            self._background_buttons.addButton(btn)
            mode_layout.addWidget(btn)
        self._background_buttons.buttonClicked.connect(self._on_background_clicked)
        outer.addWidget(mode_group)

        outer.addStretch(1)

        # Populate every row from the default state.
        self.set_state(self._state)

    # ---- Row builders ----------------------------------------------------

    def _build_shape_row(self) -> QHBoxLayout:
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 4)
        layout.addWidget(QLabel("Shape"))
        self._shape_combo = QComboBox()
        for label_text, value in _SHAPE_OPTIONS:
            self._shape_combo.addItem(label_text, value)
        self._shape_combo.setCurrentIndex(
            next(
                (i for i, (_, v) in enumerate(_SHAPE_OPTIONS)
                 if v == self._state.target_shape),
                0,
            )
        )
        self._shape_combo.currentIndexChanged.connect(self._on_shape_changed)
        layout.addWidget(self._shape_combo, 1)
        return layout

    def _build_numeric_row(self, row: _NumericRow) -> QWidget:
        container = QWidget()
        h = QHBoxLayout(container)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(4)

        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setObjectName(row.component_id + "-slider")
        slider.setMinimum(0)
        slider.setMaximum(_SLIDER_RESOLUTION)
        slider.valueChanged.connect(
            lambda v, r=row: self._on_slider_changed(r, v)
        )

        spinbox = QDoubleSpinBox()
        spinbox.setObjectName(row.component_id + "-spinbox")
        spinbox.setMinimum(row.display_min)
        spinbox.setMaximum(row.display_max)
        spinbox.setSingleStep(row.display_step)
        spinbox.setDecimals(row.decimals)
        # ``keyboardTracking`` defaults to True, which fires
        # ``valueChanged`` on every keystroke. That makes multi-digit
        # typing (e.g. "800" altitude) impossible: after the first "8"
        # the host rebuilds the entire scene with altitude=8 km, the
        # spinbox is repainted, and the user cannot complete the
        # number. Turning it off makes the spinbox commit only on
        # Enter / focus-out / arrow-step / programmatic ``setValue`` —
        # which is what every typed-input control should do here.
        # The existing tests use ``setValue`` (programmatic) so they
        # still emit immediately regardless of this setting.
        spinbox.setKeyboardTracking(False)
        spinbox.valueChanged.connect(
            lambda v, r=row: self._on_spinbox_changed(r, v)
        )
        spinbox.setMinimumWidth(70)

        units_label = QLabel(row.display_units)
        units_label.setMinimumWidth(28)

        h.addWidget(slider, 1)
        h.addWidget(spinbox)
        h.addWidget(units_label)

        self._sliders[row.component_id] = slider
        self._spinboxes[row.component_id] = spinbox
        return container

    # ---- External API ----------------------------------------------------

    def set_state(self, state: SceneState) -> None:
        """Push a SceneState into the panel without re-emitting.

        Used at startup, on "New scene", and any time the host window
        wants to sync the panel from another source (e.g. a scenario
        file). All control updates block signals so the round-trip
        cannot fire ``state_changed`` and create a feedback loop.
        """
        self._state = state
        for row in _NUMERIC_ROWS:
            canonical_value = float(getattr(state, row.field))
            display_value = row.from_canonical(canonical_value)
            slider = self._sliders[row.component_id]
            spinbox = self._spinboxes[row.component_id]

            slider.blockSignals(True)
            slider.setValue(_display_to_slider_int(row, display_value))
            slider.blockSignals(False)

            spinbox.blockSignals(True)
            spinbox.setValue(display_value)
            spinbox.blockSignals(False)

        # Mode + shape combos.
        self._shape_combo.blockSignals(True)
        self._shape_combo.setCurrentIndex(
            next(
                (i for i, (_, v) in enumerate(_SHAPE_OPTIONS)
                 if v == state.target_shape),
                0,
            )
        )
        self._shape_combo.blockSignals(False)

        for btn in self._regime_buttons.buttons():
            btn.blockSignals(True)
            btn.setChecked(btn.property("regime_value") == state.regime_override)
            btn.blockSignals(False)

        for btn in self._background_buttons.buttons():
            btn.blockSignals(True)
            btn.setChecked(btn.property("background_value") == state.background_kind)
            btn.blockSignals(False)

    def current_state(self) -> SceneState:
        """The most recent SceneState the panel has produced or been pushed."""
        return self._state

    # ---- Slider / spinbox handlers ---------------------------------------

    def _on_slider_changed(self, row: _NumericRow, slider_value: int) -> None:
        display_value = _slider_int_to_display(row, slider_value)
        # Mirror to spinbox without firing its signal.
        spinbox = self._spinboxes[row.component_id]
        spinbox.blockSignals(True)
        spinbox.setValue(display_value)
        spinbox.blockSignals(False)
        # Apply to state and queue a debounced emit.
        self._apply_numeric_change(row, display_value)
        self._drag_pending = True
        self._drag_timer.start()

    def _on_spinbox_changed(self, row: _NumericRow, display_value: float) -> None:
        # Mirror to slider without firing its signal.
        slider = self._sliders[row.component_id]
        slider.blockSignals(True)
        slider.setValue(_display_to_slider_int(row, display_value))
        slider.blockSignals(False)
        # Apply to state and emit immediately — keyboard input is slow
        # enough that no debounce is needed.
        self._apply_numeric_change(row, display_value)
        self._emit_state_changed()

    def _apply_numeric_change(self, row: _NumericRow, display_value: float) -> None:
        canonical = row.to_canonical(display_value)
        self._state = dataclasses.replace(
            self._state, **{row.field: canonical}
        )

    # ---- Shape / mode handlers -------------------------------------------

    def _on_shape_changed(self, index: int) -> None:
        shape_value: ShapeKind = self._shape_combo.itemData(index)
        self._state = dataclasses.replace(self._state, target_shape=shape_value)
        self._emit_state_changed()

    def _on_regime_clicked(self) -> None:
        btn = self._regime_buttons.checkedButton()
        if btn is None:
            return
        regime_value: RegimeOverride = btn.property("regime_value")
        self._state = dataclasses.replace(self._state, regime_override=regime_value)
        self._emit_state_changed()

    def _on_background_clicked(self) -> None:
        btn = self._background_buttons.checkedButton()
        if btn is None:
            return
        bg_value: BackgroundKind = btn.property("background_value")
        self._state = dataclasses.replace(self._state, background_kind=bg_value)
        self._emit_state_changed()

    # ---- Emit ------------------------------------------------------------

    def _emit_state_changed(self) -> None:
        self._drag_pending = False
        self.state_changed.emit(self._state)
