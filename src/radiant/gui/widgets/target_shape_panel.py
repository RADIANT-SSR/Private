"""The shared **Target shape & orientation** control — shape combo + dims + RPY.

This is the reusable target-shape editor factored out of the Geometry "Schematic" tab so
it can be mounted **verbatim** on two surfaces (Rule 19 — one implementation, two homes):

* the Geometry Schematic-tab accordion
  (:class:`~radiant.gui.widgets.geometry_angle_panel.GeometryAnglePanel`, Part B), where a
  shape edit tilts the 3D-schematic glyph, and
* the **Source** stage instrument (arch-doc §4.4.1 Source "size / shape / orientation"),
  where the same controls set the target's projected-area shape (GUI plan Phase PS-1).

Both edit the **same** ``geometry.target.shape`` / ``geometry.target.shape_*`` schema
parameters — there is only one target in the model, so the two surfaces are two views of
one parameter set (a shape set from the Source stage shows on the Geometry schematic and
vice-versa after the next evaluation). This panel is a **view + control surface only**: it
emits intent signals and never touches a ``Sensor`` — the owning ``StagePane``
(:mod:`radiant.gui.widgets.stage_center`) performs the one ``sensor.set`` per edit (one GUI
action ↔ one API call, GUI plan §4.1).

The controls are the identical building blocks the Inputs-tab
:class:`~radiant.gui.widgets.geometry_mode_form.GeometryModeForm` uses — ``geoModeFamily``
cards holding a shape combo styled like a geometry mode selector (``geoModeSelector``,
populated from the ``geometry.target.shape`` schema ``enum_values`` — never a hardcoded list,
Gap 70), the per-shape **dimension** fields (radius / length / width / height / base-radius
— only the subset the selected shape uses is shown, CU-131) **or**, when ``shape="none"``,
the scalar **Projected area** field (``geometry.target.projected_area_m2``) that sizes a
shapeless target — the two are mutually exclusive by construction (the panel never shows a
shape's dims and the projected-area field together), the GUI half of "size the target one way
or the other" (CU-168 follow-up; the engine's shape-wins precedence is the backstop for raw
configs). Plus the yaw / pitch / roll fields, each rendered as the shared
:class:`~radiant.gui.widgets.field_row.FieldRow` (label + value button). Clicking a dimension,
the projected area, or an RPY value emits :attr:`TargetShapePanel.editRequested`; selecting a
shape emits :attr:`shapeRequested`.

All colour/typography comes from the QSS theme via object names (GUI plan §4.9); this file
holds no colour/font literal. One widget class per file (Rule 19).
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Final

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from radiant.gui.widgets.field_row import FieldRow

# RPY field dot-paths (the schema owns bounds/units; the grouping is the only literal,
# tracked alongside the geometry mode-form's manifest under CU-120).
_RPY_FIELDS: Final[tuple[tuple[str, str], ...]] = (
    ("Yaw", "geometry.target.shape_yaw_rad"),
    ("Pitch", "geometry.target.shape_pitch_rad"),
    ("Roll", "geometry.target.shape_roll_rad"),
)

# The scalar projected-area dot-path — the size input for a target with NO shape
# (extended/sub-pixel scene). Shape and projected area are two ways to specify the same
# quantity (the projected area); the panel shows exactly one — this field when shape="none",
# the shape's dimension subset otherwise — so they are mutually exclusive by construction
# (CU-168 follow-up; the engine's shape-wins precedence is the backstop for raw configs).
_PROJECTED_AREA_PATH: Final[str] = "geometry.target.projected_area_m2"

# Every shape-dimension dot-path (the schema owns bounds/units; the label + the
# shape→subset matrix below are the grouping literals, tracked under CU-120/CU-131).
_DIM_FIELDS: Final[tuple[tuple[str, str], ...]] = (
    ("Radius", "geometry.target.shape_radius_m"),
    ("Length", "geometry.target.shape_length_m"),
    ("Width", "geometry.target.shape_width_m"),
    ("Height", "geometry.target.shape_height_m"),
    ("Base radius", "geometry.target.shape_base_radius_m"),
)

# Which dimension dot-paths each shape uses (from the source._schema.py descriptions — each
# shape reads a subset). Switching the shape shows exactly this subset (owner request: ALL
# dimension inputs, per shape). ``none`` (extended/sub-pixel scene) exposes no body dims.
_SHAPE_DIMENSIONS: Final[Mapping[str, tuple[str, ...]]] = {
    "none": (),
    "sphere": ("geometry.target.shape_radius_m",),
    "cylinder": ("geometry.target.shape_radius_m", "geometry.target.shape_length_m"),
    "flat_plate": ("geometry.target.shape_length_m", "geometry.target.shape_width_m"),
    "box": (
        "geometry.target.shape_length_m",
        "geometry.target.shape_width_m",
        "geometry.target.shape_height_m",
    ),
    "cone": ("geometry.target.shape_base_radius_m", "geometry.target.shape_height_m"),
}

# Nominal (sensible non-zero) body dimensions seeded when a shape is first selected while
# its required dims are still the ``0.0`` "not set" sentinel (CU-125). Keyed shape → dotpath
# → metres; each shape's keys are exactly its ``_SHAPE_DIMENSIONS`` required subset (a test
# asserts that invariant). These are display/UX defaults only — the schema keeps the ``0.0``
# Rule-12 sentinel (0.0 still means "shape not provided"); the owner applies a nominal value
# only to a dim currently at 0.0, never overwriting a user-set non-zero value. Magnitudes are
# not-to-scale (§6.1): they only need to be positive and give a recognisable aspect ratio.
NOMINAL_SHAPE_DIMENSIONS: Final[Mapping[str, Mapping[str, float]]] = {
    "sphere": {"geometry.target.shape_radius_m": 1.0},
    "cylinder": {
        "geometry.target.shape_radius_m": 0.5,
        "geometry.target.shape_length_m": 2.0,
    },
    "flat_plate": {
        "geometry.target.shape_length_m": 1.0,
        "geometry.target.shape_width_m": 1.0,
    },
    "box": {
        "geometry.target.shape_length_m": 1.0,
        "geometry.target.shape_width_m": 1.0,
        "geometry.target.shape_height_m": 1.0,
    },
    "cone": {
        "geometry.target.shape_base_radius_m": 0.5,
        "geometry.target.shape_height_m": 1.0,
    },
}


class TargetShapePanel(QWidget):
    """Shape combo + per-shape dimension fields + RPY fields (view + control surface).

    Parameters
    ----------
    parent:
        The owning widget, if any.
    show_triad_toggle:
        Include the "show orientation triad" checkbox (a 3D-viewer control). The Geometry
        Schematic tab wants it (there is a 3D scene to overlay a triad on); the Source
        instrument has no 3D scene, so it constructs the panel with the toggle hidden.

    Signals
    -------
    shapeRequested(str):
        The user picked a target shape — the owner performs ``sensor.set``.
    editRequested(str):
        The user clicked a dimension or RPY value field — ``(dotpath,)``; the owner opens
        the shared :class:`ParameterEditorDialog` on that dot-path (one ``sensor.set`` on
        commit). One edit-intent signal for every schema-driven field, matching the
        Inputs-tab :class:`GeometryModeForm` (both open the same dialog on click).
    triadToggled(bool):
        The RPY-triad checkbox changed (only ever emitted when ``show_triad_toggle``).
    """

    shapeRequested = Signal(str)
    editRequested = Signal(str)
    triadToggled = Signal(bool)

    def __init__(self, parent: QWidget | None = None, *, show_triad_toggle: bool = True) -> None:
        super().__init__(parent)
        self.setObjectName("targetShapePanel")
        # Guards so programmatic sync (set_shape) does not echo a signal.
        self._suppress = False
        self._rpy_rows: dict[str, FieldRow] = {}
        self._dim_rows: dict[str, FieldRow] = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        # Shape-library card — a titled family card + the schema-driven shape combo, styled
        # exactly like a geometry mode selector (same object name + sizing so it elides and
        # shrinks to the column rather than tripping a horizontal scrollbar).
        shape_card, shape_box = self._card("Target shape library", self)
        self._shape_combo = QComboBox(shape_card)
        self._shape_combo.setObjectName("geoModeSelector")
        self._shape_combo.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
        )
        self._shape_combo.setMinimumContentsLength(6)
        self._shape_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._shape_combo.currentTextChanged.connect(self._emit_shape)
        shape_box.addWidget(self._shape_combo)
        layout.addWidget(shape_card)

        # Dimensions card — every dim field as a shared FieldRow (schema-driven bounds/units,
        # opened in the shared editor dialog); only the subset the selected shape uses shows
        # (CU-131 + owner request: ALL dims per shape).
        dim_card, dim_box = self._card("Dimensions", self)
        # Projected-area field (shape="none" only) — the size input for a shapeless target.
        # Shown/hidden opposite the shape dims so the panel never offers both at once.
        self._area_row = FieldRow(_PROJECTED_AREA_PATH, "Projected area", self._request_edit)
        dim_box.addWidget(self._area_row)
        for label, dotpath in _DIM_FIELDS:
            row = FieldRow(dotpath, label, self._request_edit)
            dim_box.addWidget(row)
            self._dim_rows[dotpath] = row
        layout.addWidget(dim_card)

        # Body-orientation (RPY) card — the same shared FieldRow for each yaw/pitch/roll.
        rpy_card, rpy_box = self._card("Body orientation (RPY)", self)
        for label, dotpath in _RPY_FIELDS:
            row = FieldRow(dotpath, label, self._request_edit)
            rpy_box.addWidget(row)
            self._rpy_rows[dotpath] = row
        layout.addWidget(rpy_card)

        self._triad_check = QCheckBox("Show orientation triad", self)
        self._triad_check.setObjectName("anglePanelTriadToggle")
        self._triad_check.toggled.connect(self.triadToggled)
        self._triad_check.setVisible(show_triad_toggle)
        layout.addWidget(self._triad_check)
        layout.addStretch(1)

    @staticmethod
    def _card(title: str, parent: QWidget) -> tuple[QWidget, QVBoxLayout]:
        """A ``geoModeFamily`` card (title + content column) — the geometry form's card shell.

        Returns the card widget and its content layout so the caller adds the combo / field
        rows into the same bordered, titled card the Inputs-tab family blocks use, keeping
        every shape/geometry surface visually identical (same object names → same QSS).
        """
        from PySide6.QtWidgets import QLabel

        card = QWidget(parent)
        card.setObjectName("geoModeFamily")
        # A bare QWidget paints no QSS background/border unless styled-background is on
        # (the same Qt gotcha the geometry family cards handle).
        card.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        card.setProperty("state", "normal")
        box = QVBoxLayout(card)
        box.setContentsMargins(12, 10, 12, 10)
        box.setSpacing(6)
        heading = QLabel(title, card)
        heading.setObjectName("geoModeFamilyTitle")
        box.addWidget(heading)
        return card, box

    # -- signal emitters (guarded) -----------------------------------------

    def _emit_shape(self, value: str) -> None:
        # Show the new shape's dimension subset immediately, even before the re-evaluate.
        self._update_visible_dims(value)
        if not self._suppress and value:
            self.shapeRequested.emit(value)

    def _request_edit(self, dotpath: str) -> None:
        """A dimension/RPY value field was clicked — ask the owner to open the editor."""
        if not self._suppress:
            self.editRequested.emit(dotpath)

    def _update_visible_dims(self, shape: str) -> None:
        """Show only the dimension rows the *shape* uses (schema shape→dims matrix).

        With ``shape="none"`` no body dims apply; the scalar **Projected area** field takes
        their place instead. Shape dims and the projected-area field are never shown together
        — they are the two mutually-exclusive ways to size the target (CU-168 follow-up).
        """
        visible = set(_SHAPE_DIMENSIONS.get(shape, ()))
        for dotpath, row in self._dim_rows.items():
            row.setVisible(dotpath in visible)
        self._area_row.setVisible(shape == "none")

    # -- programmatic sync (from the owner, does not echo signals) ----------

    def set_shape_choices(self, choices: tuple[str, ...]) -> None:
        """Populate the shape combo from the schema ``enum_values`` (Gap 70)."""
        self._suppress = True
        try:
            current = self._shape_combo.currentText()
            self._shape_combo.clear()
            self._shape_combo.addItems(list(choices))
            if current in choices:
                self._shape_combo.setCurrentText(current)
        finally:
            self._suppress = False

    def set_shape(self, value: str) -> None:
        """Reflect the sensor's current shape (updates the visible dim rows) without emitting."""
        self._suppress = True
        try:
            self._shape_combo.setCurrentText(value)
        finally:
            self._suppress = False
        self._update_visible_dims(value)

    def set_dimensions(self, texts: Mapping[str, str]) -> None:
        """Reflect the sensor's current shape dimensions as display text (dotpath → text).

        The owner formats each value in its display unit (the shared
        :func:`radiant.gui.param_format.field_display_text`) and passes the ready string,
        so the panel stays a pure view (no ``Sensor`` access) — the value+unit presentation
        is identical to every other schema-driven field.
        """
        for dotpath, row in self._dim_rows.items():
            if dotpath in texts:
                row.set_value_text(texts[dotpath])

    def set_orientation(self, texts: Mapping[str, str]) -> None:
        """Reflect the sensor's current RPY as display text (dotpath → text) — pure view."""
        for dotpath, row in self._rpy_rows.items():
            if dotpath in texts:
                row.set_value_text(texts[dotpath])

    def set_projected_area(self, text: str) -> None:
        """Reflect the sensor's current ``projected_area_m2`` as display text — pure view.

        Only meaningful when ``shape="none"`` (the field is hidden otherwise); the owner
        formats the value in its display unit via the shared formatter and passes the string.
        """
        self._area_row.set_value_text(text)

    # -- accessors (tests) --------------------------------------------------

    @property
    def shape_combo(self) -> QComboBox:
        """The target-shape combo box."""
        return self._shape_combo

    @property
    def triad_checkbox(self) -> QCheckBox:
        """The 'show orientation triad' checkbox."""
        return self._triad_check

    def rpy_row(self, dotpath: str) -> FieldRow:
        """The RPY field row for *dotpath* (KeyError if unknown)."""
        return self._rpy_rows[dotpath]

    def dimension_row(self, dotpath: str) -> FieldRow:
        """The shape-dimension field row for *dotpath* (KeyError if unknown)."""
        return self._dim_rows[dotpath]

    @property
    def projected_area_row(self) -> FieldRow:
        """The scalar projected-area field row (shown only when shape='none')."""
        return self._area_row

    def visible_dimensions(self) -> tuple[str, ...]:
        """The dimension dot-paths whose rows are currently shown (for tests).

        Uses ``not isHidden()`` (the per-row visibility state) rather than ``isVisibleTo``
        so it is correct even when the panel is not on the current tab/page.
        """
        return tuple(dotpath for dotpath, row in self._dim_rows.items() if not row.isHidden())


__all__ = [
    "NOMINAL_SHAPE_DIMENSIONS",
    "TargetShapePanel",
]
