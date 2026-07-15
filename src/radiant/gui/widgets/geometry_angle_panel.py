"""The Schematic-tab accordion side panel — geometry inputs, shape + RPY editor.

This is the right-hand accordion of the Geometry "Schematic" tab (arch doc §6.2/§6.4, GUI
plan Phase 7 Part B). For the shape/RPY controls it is a **view + control surface only**: it
emits intent signals and never touches the ``Sensor`` itself — the owning ``StagePane``
(:mod:`radiant.gui.widgets.stage_center`) performs the one ``sensor.set`` per edit (one GUI
action ↔ one API call, GUI plan §4.1). The embedded **Geometry inputs** form is the one
exception: it is the Phase-5 :class:`GeometryModeForm`, which owns its own schema-driven
edit/reject path (one ``sensor.set`` on commit) — mounted here so the user can edit geometry
and watch the schematic + arcs update live (owner request 2026-07-14). The owning
``StagePane`` binds it to the same live sensor as the Inputs-tab form and re-emits its
``parameterEdited`` so an edit here re-evaluates and re-renders the schematic.

Two accordion pages (``QToolBox``):

1. **Geometry inputs** — the Phase-5 :class:`GeometryModeForm` (mode selectors + schema-driven
   fields), letting the user set viewing/solar/kinematics geometry from the Schematic tab and
   watch the scene move. The derived-angles table is deliberately **not** here (it lives on
   the Inputs tab; the key derived values surface on the schematic itself as arc degree labels
   + leader labels — owner request 2026-07-14).
2. **Target shape & orientation** — the same building blocks as the Inputs-tab
   :class:`GeometryModeForm`, so the two pages are visually indistinguishable (owner feedback
   2026-07-14): ``geoModeFamily`` cards holding a shape combo styled like a geometry mode
   selector (``geoModeSelector``, populated from the ``source.target.shape`` schema
   ``enum_values`` — never a hardcoded list, Gap 70), the per-shape **dimension** fields
   (radius / length / width / height / base-radius — only the subset the selected shape uses
   is shown, CU-131), and the yaw / pitch / roll fields, each rendered as the shared
   :class:`~radiant.gui.widgets.field_row.FieldRow` (label + value button). Clicking a
   dimension or RPY value emits :attr:`GeometryAnglePanel.editRequested`; the owner opens the
   shared :class:`ParameterEditorDialog` on that dot-path (one ``sensor.set`` on commit, the
   same value/unit/reject discipline as the parameter tree). Selecting a shape emits
   ``shapeRequested``; a shape whose required dimensions are still the ``0.0`` "not set"
   sentinel is seeded to :data:`NOMINAL_SHAPE_DIMENSIONS` (owner performs the sets) so the
   re-evaluate succeeds instead of tripping the shape factory (CU-125).

The **angle-arc reveal toggles** are no longer in this accordion: owner feedback 2026-07-14
moved that selector **onto the plot** as a bottom-left overlay
(:class:`~radiant.gui.viewer.angle_overlay.AngleToggleOverlay`), mirroring the top-left
VECTORS legend. All colour/typography comes from the QSS theme via object names (GUI plan
§4.9); this file holds no colour/font literal.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Final

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QLabel,
    QSizePolicy,
    QToolBox,
    QVBoxLayout,
    QWidget,
)

from radiant.gui.widgets.field_row import FieldRow
from radiant.gui.widgets.geometry_mode_form import GeometryModeForm

# RPY spin-box dot-paths (the schema owns bounds/units; the grouping is the only literal,
# tracked alongside the geometry mode-form's manifest under CU-120).
_RPY_FIELDS: Final[tuple[tuple[str, str], ...]] = (
    ("Yaw", "source.target.shape_yaw_rad"),
    ("Pitch", "source.target.shape_pitch_rad"),
    ("Roll", "source.target.shape_roll_rad"),
)

# Every shape-dimension dot-path (the schema owns bounds/units; the label + the
# shape→subset matrix below are the grouping literals, tracked under CU-120/CU-131).
_DIM_FIELDS: Final[tuple[tuple[str, str], ...]] = (
    ("Radius", "source.target.shape_radius_m"),
    ("Length", "source.target.shape_length_m"),
    ("Width", "source.target.shape_width_m"),
    ("Height", "source.target.shape_height_m"),
    ("Base radius", "source.target.shape_base_radius_m"),
)

# Which dimension dot-paths each shape uses (from the source._schema.py descriptions — each
# shape reads a subset). Switching the shape shows exactly this subset (owner request: ALL
# dimension inputs, per shape). ``none`` (extended/sub-pixel scene) exposes no body dims.
_SHAPE_DIMENSIONS: Final[Mapping[str, tuple[str, ...]]] = {
    "none": (),
    "sphere": ("source.target.shape_radius_m",),
    "cylinder": ("source.target.shape_radius_m", "source.target.shape_length_m"),
    "flat_plate": ("source.target.shape_length_m", "source.target.shape_width_m"),
    "box": (
        "source.target.shape_length_m",
        "source.target.shape_width_m",
        "source.target.shape_height_m",
    ),
    "cone": ("source.target.shape_base_radius_m", "source.target.shape_height_m"),
}

# Nominal (sensible non-zero) body dimensions seeded when a shape is first selected while
# its required dims are still the ``0.0`` "not set" sentinel (CU-125). Keyed shape → dotpath
# → metres; each shape's keys are exactly its ``_SHAPE_DIMENSIONS`` required subset (a test
# asserts that invariant). These are display/UX defaults only — the schema keeps the ``0.0``
# Rule-12 sentinel (0.0 still means "shape not provided"); the owner applies a nominal value
# only to a dim currently at 0.0, never overwriting a user-set non-zero value. Magnitudes are
# not-to-scale (§6.1): they only need to be positive and give a recognisable aspect ratio.
NOMINAL_SHAPE_DIMENSIONS: Final[Mapping[str, Mapping[str, float]]] = {
    "sphere": {"source.target.shape_radius_m": 1.0},
    "cylinder": {
        "source.target.shape_radius_m": 0.5,
        "source.target.shape_length_m": 2.0,
    },
    "flat_plate": {
        "source.target.shape_length_m": 1.0,
        "source.target.shape_width_m": 1.0,
    },
    "box": {
        "source.target.shape_length_m": 1.0,
        "source.target.shape_width_m": 1.0,
        "source.target.shape_height_m": 1.0,
    },
    "cone": {
        "source.target.shape_base_radius_m": 0.5,
        "source.target.shape_height_m": 1.0,
    },
}


class GeometryAnglePanel(QWidget):
    """Accordion side controls for the 3D geometry viewer (Part B).

    Signals
    -------
    triadToggled(bool):
        The RPY-triad checkbox changed.
    shapeRequested(str):
        The user picked a target shape — the owner performs ``sensor.set``.
    editRequested(str):
        The user clicked a dimension or RPY value field — ``(dotpath,)``; the owner opens
        the shared :class:`ParameterEditorDialog` on that dot-path (one ``sensor.set`` on
        commit). One edit-intent signal for every schema-driven field, matching the
        Inputs-tab :class:`GeometryModeForm` (both open the same dialog on click).
    """

    triadToggled = Signal(bool)
    shapeRequested = Signal(str)
    editRequested = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("geometryAnglePanel")
        # A usable minimum so the accordion labels and value columns are never clipped.
        self.setMinimumWidth(300)
        # Guards so programmatic sync (set_shape) does not echo a signal.
        self._suppress = False
        self._rpy_rows: dict[str, FieldRow] = {}
        self._dim_rows: dict[str, FieldRow] = {}

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self._toolbox = QToolBox(self)
        self._toolbox.setObjectName("geometryAngleAccordion")
        outer.addWidget(self._toolbox)

        # The Phase-5 GeometryModeForm, mounted here so geometry is editable from the
        # Schematic tab (owner request 2026-07-14). It owns its own schema-driven edit path;
        # the owning StagePane binds it to the live sensor and re-emits its parameterEdited.
        self._geometry_form = GeometryModeForm(self)
        self._toolbox.addItem(self._build_inputs_page(), "Geometry inputs")
        self._toolbox.addItem(self._build_target_page(), "Target shape & orientation")

    # -- page construction --------------------------------------------------

    def _build_inputs_page(self) -> QWidget:
        """The **Geometry inputs** accordion page — the editable Phase-5 mode form.

        Hosts the :class:`GeometryModeForm` so geometry is settable from the Schematic tab
        (edit-and-watch, owner request 2026-07-14). The form is scrollable so the three
        family cards stay usable in the short accordion page.
        """
        page = QWidget(self._toolbox)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(6)
        self._geometry_form.setParent(page)
        layout.addWidget(self._geometry_form, 1)
        return page

    def _build_target_page(self) -> QWidget:
        """The **Target shape & orientation** page — built from the same parts as the form.

        The shape combo, the per-shape dimension fields, and the RPY fields are rendered as
        the identical card + field-row building blocks the Inputs-tab :class:`GeometryModeForm`
        uses (``geoModeFamily`` cards, ``geoModeSelector`` combo, shared :class:`FieldRow`),
        so the two pages read as one design (owner feedback 2026-07-14). Editing a dimension
        or RPY field emits :attr:`editRequested`; the owner opens the shared editor dialog and
        performs the one ``sensor.set`` (view + control surface only — R-API §4.1).
        """
        page = QWidget(self._toolbox)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        # Shape-library card — a titled family card + the schema-driven shape combo, styled
        # exactly like a geometry mode selector (same object name + sizing so it elides and
        # shrinks to the accordion column rather than tripping a horizontal scrollbar).
        shape_card, shape_box = self._card("Target shape library", page)
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
        dim_card, dim_box = self._card("Dimensions", page)
        for label, dotpath in _DIM_FIELDS:
            row = FieldRow(dotpath, label, self._request_edit)
            dim_box.addWidget(row)
            self._dim_rows[dotpath] = row
        layout.addWidget(dim_card)

        # Body-orientation (RPY) card — the same shared FieldRow for each yaw/pitch/roll.
        rpy_card, rpy_box = self._card("Body orientation (RPY)", page)
        for label, dotpath in _RPY_FIELDS:
            row = FieldRow(dotpath, label, self._request_edit)
            rpy_box.addWidget(row)
            self._rpy_rows[dotpath] = row
        layout.addWidget(rpy_card)

        self._triad_check = QCheckBox("Show orientation triad", page)
        self._triad_check.setObjectName("anglePanelTriadToggle")
        self._triad_check.toggled.connect(self.triadToggled)
        layout.addWidget(self._triad_check)
        layout.addStretch(1)
        return page

    @staticmethod
    def _card(title: str, parent: QWidget) -> tuple[QWidget, QVBoxLayout]:
        """A ``geoModeFamily`` card (title + content column) — the geometry form's card shell.

        Returns the card widget and its content layout so the caller adds the combo / field
        rows into the same bordered, titled card the Inputs-tab family blocks use, keeping
        the two pages visually identical (same object names → same QSS).
        """
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
        """Show only the dimension rows the *shape* uses (schema shape→dims matrix)."""
        visible = set(_SHAPE_DIMENSIONS.get(shape, ()))
        for dotpath, row in self._dim_rows.items():
            row.setVisible(dotpath in visible)

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
        is identical to the Inputs-tab form's fields.
        """
        for dotpath, row in self._dim_rows.items():
            if dotpath in texts:
                row.set_value_text(texts[dotpath])

    def set_orientation(self, texts: Mapping[str, str]) -> None:
        """Reflect the sensor's current RPY as display text (dotpath → text) — pure view."""
        for dotpath, row in self._rpy_rows.items():
            if dotpath in texts:
                row.set_value_text(texts[dotpath])

    # -- accessors (tests) --------------------------------------------------

    @property
    def geometry_form(self) -> GeometryModeForm:
        """The embedded editable :class:`GeometryModeForm` (Schematic-tab geometry inputs)."""
        return self._geometry_form

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

    def visible_dimensions(self) -> tuple[str, ...]:
        """The dimension dot-paths whose rows are currently shown (for tests).

        Uses ``not isHidden()`` (the per-row visibility state) rather than ``isVisibleTo``
        so it is correct even when the accordion page is not the current one.
        """
        return tuple(dotpath for dotpath, row in self._dim_rows.items() if not row.isHidden())

    def set_toolbox_page(self, index: int) -> None:
        """Select an accordion page (0 = Geometry inputs, 1 = Target) — shape/RPY flow."""
        self._toolbox.setCurrentIndex(index)


__all__ = ["NOMINAL_SHAPE_DIMENSIONS", "GeometryAnglePanel"]
