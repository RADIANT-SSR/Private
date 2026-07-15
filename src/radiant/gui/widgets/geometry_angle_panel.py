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
2. **Target shape & orientation** — a combo box populated from the ``source.target.shape``
   schema ``enum_values`` (never a hardcoded list — Gap 70); the per-shape **dimension**
   inputs (radius / length / width / height / base-radius, schema bounds + units, only the
   subset the selected shape uses shown — CU-131); and the yaw / pitch / roll spin boxes
   plus a "show orientation triad" checkbox. Editing any of them requests one ``sensor.set``
   (the owner performs it) and, for shape/RPY/dims, updates the on-canvas wireframe + triad.
   Selecting a shape whose required dimensions are still the ``0.0`` "not set" sentinel seeds
   them to :data:`NOMINAL_SHAPE_DIMENSIONS` (owner performs the sets) so the re-evaluate
   succeeds instead of tripping the shape factory (CU-125).

The **angle-arc reveal toggles** are no longer in this accordion: owner feedback 2026-07-14
moved that selector **onto the plot** as a bottom-left overlay
(:class:`~radiant.gui.viewer.angle_overlay.AngleToggleOverlay`), mirroring the top-left
VECTORS legend. All colour/typography comes from the QSS theme via object names (GUI plan
§4.9); this file holds no colour/font literal.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Final

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QLabel,
    QToolBox,
    QVBoxLayout,
    QWidget,
)

from radiant.gui.widgets.geometry_mode_form import GeometryModeForm

# RPY spin-box dot-paths (the schema owns bounds/units; the grouping is the only literal,
# tracked alongside the geometry mode-form's manifest under CU-120).
_RPY_FIELDS: Final[tuple[tuple[str, str], ...]] = (
    ("Yaw", "source.target.shape_yaw_rad"),
    ("Pitch", "source.target.shape_pitch_rad"),
    ("Roll", "source.target.shape_roll_rad"),
)

_DEFAULT_RPY_BOUNDS: Final[tuple[float, float]] = (-6.283185307179586, 6.283185307179586)

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

_DEFAULT_DIM_BOUNDS: Final[tuple[float, float]] = (0.0, 1e6)

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
    orientationRequested(str, float):
        The user edited an RPY value — ``(dotpath, value_rad)``; owner performs the set.
    dimensionRequested(str, float):
        The user edited a shape-dimension value — ``(dotpath, value_m)``; owner sets it.
    """

    triadToggled = Signal(bool)
    shapeRequested = Signal(str)
    orientationRequested = Signal(str, float)
    dimensionRequested = Signal(str, float)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("geometryAnglePanel")
        # A usable minimum so the accordion labels and value columns are never clipped.
        self.setMinimumWidth(300)
        # Guards so programmatic sync (set_shape / set_orientation) does not echo a signal.
        self._suppress = False
        self._rpy_spins: dict[str, QDoubleSpinBox] = {}
        self._dim_spins: dict[str, QDoubleSpinBox] = {}
        self._dim_labels: dict[str, QLabel] = {}

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
        page = QWidget(self._toolbox)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        shape_header = QLabel("Target shape library", page)
        shape_header.setObjectName("anglePanelGroupHeader")
        layout.addWidget(shape_header)
        self._shape_combo = QComboBox(page)
        self._shape_combo.setObjectName("anglePanelShapeCombo")
        self._shape_combo.currentTextChanged.connect(self._emit_shape)
        layout.addWidget(self._shape_combo)

        # Shape-dimension inputs — every dim field (schema-driven bounds/units); only the
        # subset the selected shape uses is shown (CU-131 + owner request: ALL dims per shape).
        dim_header = QLabel("Dimensions", page)
        dim_header.setObjectName("anglePanelGroupHeader")
        layout.addWidget(dim_header)
        self._dim_form = QFormLayout()
        self._dim_form.setContentsMargins(0, 0, 0, 0)
        for label, dotpath in _DIM_FIELDS:
            spin = QDoubleSpinBox(page)
            spin.setObjectName("anglePanelDimSpin")
            spin.setRange(*_DEFAULT_DIM_BOUNDS)
            spin.setDecimals(3)
            spin.setSingleStep(0.1)
            spin.setSuffix(" m")
            spin.valueChanged.connect(lambda value, path=dotpath: self._emit_dimension(path, value))
            label_widget = QLabel(label, page)
            self._dim_form.addRow(label_widget, spin)
            self._dim_spins[dotpath] = spin
            self._dim_labels[dotpath] = label_widget
        layout.addLayout(self._dim_form)

        rpy_header = QLabel("Body orientation (RPY)", page)
        rpy_header.setObjectName("anglePanelGroupHeader")
        layout.addWidget(rpy_header)
        form = QFormLayout()
        form.setContentsMargins(0, 0, 0, 0)
        for label, dotpath in _RPY_FIELDS:
            spin = QDoubleSpinBox(page)
            spin.setObjectName("anglePanelRpySpin")
            spin.setRange(*_DEFAULT_RPY_BOUNDS)
            spin.setDecimals(4)
            spin.setSingleStep(0.05)
            spin.setSuffix(" rad")
            spin.valueChanged.connect(
                lambda value, path=dotpath: self._emit_orientation(path, value)
            )
            form.addRow(label, spin)
            self._rpy_spins[dotpath] = spin
        layout.addLayout(form)

        self._triad_check = QCheckBox("Show orientation triad", page)
        self._triad_check.setObjectName("anglePanelTriadToggle")
        self._triad_check.toggled.connect(self.triadToggled)
        layout.addWidget(self._triad_check)
        layout.addStretch(1)
        return page

    # -- signal emitters (guarded) -----------------------------------------

    def _emit_shape(self, value: str) -> None:
        # Show the new shape's dimension subset immediately, even before the re-evaluate.
        self._update_visible_dims(value)
        if not self._suppress and value:
            self.shapeRequested.emit(value)

    def _emit_orientation(self, dotpath: str, value: float) -> None:
        if not self._suppress:
            self.orientationRequested.emit(dotpath, value)

    def _emit_dimension(self, dotpath: str, value: float) -> None:
        if not self._suppress:
            self.dimensionRequested.emit(dotpath, value)

    def _update_visible_dims(self, shape: str) -> None:
        """Show only the dimension rows the *shape* uses (schema shape→dims matrix)."""
        visible = set(_SHAPE_DIMENSIONS.get(shape, ()))
        for dotpath, spin in self._dim_spins.items():
            self._dim_form.setRowVisible(spin, dotpath in visible)

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

    def set_orientation_bounds(self, bounds: tuple[float, float]) -> None:
        """Apply the schema RPY bounds to every spin box."""
        for spin in self._rpy_spins.values():
            spin.setRange(*bounds)

    def set_dimension_bounds(self, bounds: Mapping[str, tuple[float, float]]) -> None:
        """Apply schema bounds to each dimension spin (dotpath → (lo, hi))."""
        for dotpath, spin in self._dim_spins.items():
            if dotpath in bounds:
                spin.setRange(*bounds[dotpath])

    def set_dimensions(self, values: Mapping[str, float]) -> None:
        """Reflect the sensor's current shape dimensions (dotpath → m) without emitting."""
        self._suppress = True
        try:
            for dotpath, spin in self._dim_spins.items():
                if dotpath in values:
                    spin.setValue(float(values[dotpath]))
        finally:
            self._suppress = False

    def set_orientation(self, values: Mapping[str, float]) -> None:
        """Reflect the sensor's current RPY (dotpath → rad) without emitting."""
        self._suppress = True
        try:
            for dotpath, spin in self._rpy_spins.items():
                if dotpath in values:
                    spin.setValue(float(values[dotpath]))
        finally:
            self._suppress = False

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

    def rpy_spin(self, dotpath: str) -> QDoubleSpinBox:
        """The RPY spin box for *dotpath* (KeyError if unknown)."""
        return self._rpy_spins[dotpath]

    def dimension_spin(self, dotpath: str) -> QDoubleSpinBox:
        """The shape-dimension spin box for *dotpath* (KeyError if unknown)."""
        return self._dim_spins[dotpath]

    def visible_dimensions(self) -> tuple[str, ...]:
        """The dimension dot-paths whose rows are currently shown (for tests).

        Uses ``not isHidden()`` (the per-row ``setRowVisible`` state) rather than
        ``isVisibleTo`` so it is correct even when the accordion page is not the current one.
        """
        return tuple(dotpath for dotpath, spin in self._dim_spins.items() if not spin.isHidden())

    def set_toolbox_page(self, index: int) -> None:
        """Select an accordion page (0 = Geometry inputs, 1 = Target) — shape/RPY flow."""
        self._toolbox.setCurrentIndex(index)


__all__ = ["NOMINAL_SHAPE_DIMENSIONS", "GeometryAnglePanel"]
