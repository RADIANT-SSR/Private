"""The 3D-viewer accordion side panel — annotation toggles, readout, shape + RPY editor.

This is the right-hand accordion of the Geometry "3D View" tab (arch doc §6.2/§6.4, GUI
plan Phase 7 Part B). It is a **view + control surface only**: it emits intent signals and
never touches the ``Sensor`` itself — the owning ``StagePane``
(:mod:`radiant.gui.widgets.stage_center`) performs the one ``sensor.set`` per edit (one
GUI action ↔ one API call, GUI plan §4.1).

Three accordion pages (``QToolBox``):

1. **Angles** — one checkbox per annotatable angle, grouped by reference frame
   (target-frame vs ground/platform-frame, matching the Phase-5
   :class:`~radiant.gui.widgets.geometry_readout.GeometryReadout` split), plus the **shared**
   ``GeometryReadout`` widget showing the live numeric readout (not duplicated — the same
   widget class Phase 5 ships). Toggling a checkbox reveals/hides that arc in the 3D scene.
2. **Target shape** — a combo box populated from the ``source.target.shape`` schema
   ``enum_values`` (never a hardcoded list — Gap 70). Selecting a shape requests a
   ``sensor.set``.
3. **Orientation (RPY)** — yaw / pitch / roll spin boxes (bounds from the schema) plus a
   "show orientation triad" checkbox; editing a value requests a ``sensor.set`` and the
   triad checkbox toggles the on-target gizmo.

The annotation list is read from the ``angle_annotations`` catalog (the single source), so
a new annotatable angle appears here without transcription. All colour/typography comes
from the QSS theme via object names (GUI plan §4.9); this file holds no colour/font literal.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, Final

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

from radiant.gui.viewer.scene import angle_annotations
from radiant.gui.widgets.geometry_readout import GeometryReadout

if TYPE_CHECKING:
    from radiant.gui.viewer.scene.angle_annotations import AngleAnnotation

# Frame tag → the accordion sub-header (aligned with GeometryReadout's group titles).
_FRAME_TITLES: Final[Mapping[str, str]] = {
    angle_annotations.FRAME_TARGET: "Target-frame angles",
    angle_annotations.FRAME_GROUND: "Ground / platform frame",
}

# RPY spin-box dot-paths (the schema owns bounds/units; the grouping is the only literal,
# tracked alongside the geometry mode-form's manifest under CU-120).
_RPY_FIELDS: Final[tuple[tuple[str, str], ...]] = (
    ("Yaw", "source.target.shape_yaw_rad"),
    ("Pitch", "source.target.shape_pitch_rad"),
    ("Roll", "source.target.shape_roll_rad"),
)

_DEFAULT_RPY_BOUNDS: Final[tuple[float, float]] = (-6.283185307179586, 6.283185307179586)


class GeometryAnglePanel(QWidget):
    """Accordion side controls for the 3D geometry viewer (Part B).

    Signals
    -------
    angleToggled(str, bool):
        An annotation checkbox changed — ``(annotation_name, revealed)``.
    triadToggled(bool):
        The RPY-triad checkbox changed.
    shapeRequested(str):
        The user picked a target shape — the owner performs ``sensor.set``.
    orientationRequested(str, float):
        The user edited an RPY value — ``(dotpath, value_rad)``; owner performs the set.
    """

    angleToggled = Signal(str, bool)
    triadToggled = Signal(bool)
    shapeRequested = Signal(str)
    orientationRequested = Signal(str, float)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("geometryAnglePanel")
        # A usable minimum so the accordion labels and value columns are never clipped.
        self.setMinimumWidth(300)
        # Guards so programmatic sync (set_shape / set_orientation) does not echo a signal.
        self._suppress = False
        self._angle_checks: dict[str, QCheckBox] = {}
        self._rpy_spins: dict[str, QDoubleSpinBox] = {}

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self._toolbox = QToolBox(self)
        self._toolbox.setObjectName("geometryAngleAccordion")
        outer.addWidget(self._toolbox)

        self._toolbox.addItem(self._build_angles_page(), "Angles")
        self._toolbox.addItem(self._build_target_page(), "Target shape & orientation")

    # -- page construction --------------------------------------------------

    def _build_angles_page(self) -> QWidget:
        page = QWidget(self._toolbox)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(6)

        # Annotation toggles, grouped by reference frame (target vs ground).
        by_frame: dict[str, list[AngleAnnotation]] = {}
        for ann in angle_annotations.annotations():
            by_frame.setdefault(ann.frame, []).append(ann)
        for frame, title in _FRAME_TITLES.items():
            group = by_frame.get(frame)
            if not group:
                continue
            header = QLabel(title, page)
            header.setObjectName("anglePanelGroupHeader")
            layout.addWidget(header)
            for ann in group:
                check = QCheckBox(f"{ann.symbol}  ·  {ann.name.replace('_', ' ')}", page)
                check.setObjectName("anglePanelToggle")
                check.toggled.connect(lambda on, name=ann.name: self._emit_angle(name, on))
                layout.addWidget(check)
                self._angle_checks[ann.name] = check

        readout_header = QLabel("Live readout", page)
        readout_header.setObjectName("anglePanelGroupHeader")
        layout.addWidget(readout_header)
        # SHARED with Phase 5 — the same GeometryReadout widget class, frame-grouped.
        self._readout = GeometryReadout(page)
        layout.addWidget(self._readout, 1)
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

    def _emit_angle(self, name: str, revealed: bool) -> None:
        if not self._suppress:
            self.angleToggled.emit(name, revealed)

    def _emit_shape(self, value: str) -> None:
        if not self._suppress and value:
            self.shapeRequested.emit(value)

    def _emit_orientation(self, dotpath: str, value: float) -> None:
        if not self._suppress:
            self.orientationRequested.emit(dotpath, value)

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
        """Reflect the sensor's current shape without emitting ``shapeRequested``."""
        self._suppress = True
        try:
            self._shape_combo.setCurrentText(value)
        finally:
            self._suppress = False

    def set_orientation_bounds(self, bounds: tuple[float, float]) -> None:
        """Apply the schema RPY bounds to every spin box."""
        for spin in self._rpy_spins.values():
            spin.setRange(*bounds)

    def set_orientation(self, values: Mapping[str, float]) -> None:
        """Reflect the sensor's current RPY (dotpath → rad) without emitting."""
        self._suppress = True
        try:
            for dotpath, spin in self._rpy_spins.items():
                if dotpath in values:
                    spin.setValue(float(values[dotpath]))
        finally:
            self._suppress = False

    def populate_readout(self, geometry_outputs: Mapping[str, Any]) -> None:
        """Refresh the shared frame-grouped numeric readout from stage outputs."""
        self._readout.populate(geometry_outputs)

    # -- accessors (tests) --------------------------------------------------

    @property
    def readout(self) -> GeometryReadout:
        """The shared frame-grouped :class:`GeometryReadout` instance."""
        return self._readout

    def angle_checkbox(self, name: str) -> QCheckBox:
        """The annotation checkbox for *name* (KeyError if unknown)."""
        return self._angle_checks[name]

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

    def set_toolbox_page(self, index: int) -> None:
        """Select an accordion page (0 = Angles, 1 = Target) — used by the shape/RPY flow."""
        self._toolbox.setCurrentIndex(index)


__all__ = ["GeometryAnglePanel"]
