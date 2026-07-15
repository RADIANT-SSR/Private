"""The Schematic-tab accordion side panel — geometry inputs + target shape/RPY editor.

This is the right-hand accordion of the Geometry "Schematic" tab (arch doc §6.2/§6.4, GUI
plan Phase 7 Part B). It composes two accordion pages (``QToolBox``):

1. **Geometry inputs** — the Phase-5 :class:`GeometryModeForm` (mode selectors + schema-driven
   fields), letting the user set viewing/solar/kinematics geometry from the Schematic tab and
   watch the scene move (edit-and-watch, owner request 2026-07-14). The form owns its own
   schema-driven edit/reject path (one ``sensor.set`` on commit); the owning ``StagePane``
   binds it to the live sensor and re-emits its ``parameterEdited``. The derived-angles table
   is deliberately **not** here (it lives on the Inputs tab; the key derived values surface on
   the schematic itself as arc degree labels + leader labels — owner request 2026-07-14).
2. **Target shape & orientation** — the shared
   :class:`~radiant.gui.widgets.target_shape_panel.TargetShapePanel` (shape combo + per-shape
   dimension fields + RPY fields). This is the **same** widget the Source stage instrument
   mounts (GUI plan Phase PS-1) — one target-shape editor, two homes (Rule 19) — editing the
   same ``source.target.shape*`` parameters. For the shape/RPY controls this panel is a **view
   + control surface only**: it re-emits the :class:`TargetShapePanel` intent signals and never
   touches a ``Sensor`` — the owning ``StagePane`` performs the one ``sensor.set`` per edit (one
   GUI action ↔ one API call, GUI plan §4.1).

The **angle-arc reveal toggles** are no longer in this accordion: owner feedback 2026-07-14
moved that selector **onto the plot** as a bottom-left overlay
(:class:`~radiant.gui.viewer.angle_overlay.AngleToggleOverlay`), mirroring the top-left
VECTORS legend. All colour/typography comes from the QSS theme via object names (GUI plan
§4.9); this file holds no colour/font literal.
"""

from __future__ import annotations

from collections.abc import Mapping

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QToolBox,
    QVBoxLayout,
    QWidget,
)

from radiant.gui.widgets.field_row import FieldRow
from radiant.gui.widgets.geometry_mode_form import GeometryModeForm

# Re-exported from the shared target-shape panel so existing importers (and tests) that read
# these off ``geometry_angle_panel`` keep working after the shape controls were factored out.
from radiant.gui.widgets.target_shape_panel import (
    _SHAPE_DIMENSIONS,
    NOMINAL_SHAPE_DIMENSIONS,
    TargetShapePanel,
)

__all__ = ["_SHAPE_DIMENSIONS", "NOMINAL_SHAPE_DIMENSIONS", "GeometryAnglePanel"]


class GeometryAnglePanel(QWidget):
    """Accordion side controls for the 3D geometry viewer (Part B).

    Signals
    -------
    triadToggled(bool):
        The RPY-triad checkbox changed (re-emitted from the embedded target panel).
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
        # The shared target-shape editor — the SAME widget the Source instrument mounts.
        self._target_panel = TargetShapePanel(self)
        # Re-emit the target panel's intent signals so the StagePane's existing wiring (which
        # connects to this panel) is unchanged by the shape-controls extraction.
        self._target_panel.shapeRequested.connect(self.shapeRequested)
        self._target_panel.editRequested.connect(self.editRequested)
        self._target_panel.triadToggled.connect(self.triadToggled)

        self._toolbox.addItem(self._build_inputs_page(), "Geometry inputs")
        self._toolbox.addItem(self._build_target_page(), "Target shape & orientation")

    # -- page construction --------------------------------------------------

    def _build_inputs_page(self) -> QWidget:
        """The **Geometry inputs** accordion page — the editable Phase-5 mode form."""
        page = QWidget(self._toolbox)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(6)
        self._geometry_form.setParent(page)
        layout.addWidget(self._geometry_form, 1)
        return page

    def _build_target_page(self) -> QWidget:
        """The **Target shape & orientation** page — hosts the shared target-shape panel."""
        page = QWidget(self._toolbox)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)
        self._target_panel.setParent(page)
        layout.addWidget(self._target_panel, 1)
        return page

    # -- programmatic sync (delegated to the shared target panel) -----------

    def set_shape_choices(self, choices: tuple[str, ...]) -> None:
        """Populate the shape combo from the schema ``enum_values`` (Gap 70)."""
        self._target_panel.set_shape_choices(choices)

    def set_shape(self, value: str) -> None:
        """Reflect the sensor's current shape (updates the visible dim rows) without emitting."""
        self._target_panel.set_shape(value)

    def set_dimensions(self, texts: Mapping[str, str]) -> None:
        """Reflect the sensor's current shape dimensions as display text (dotpath → text)."""
        self._target_panel.set_dimensions(texts)

    def set_orientation(self, texts: Mapping[str, str]) -> None:
        """Reflect the sensor's current RPY as display text (dotpath → text) — pure view."""
        self._target_panel.set_orientation(texts)

    # -- accessors (tests) --------------------------------------------------

    @property
    def geometry_form(self) -> GeometryModeForm:
        """The embedded editable :class:`GeometryModeForm` (Schematic-tab geometry inputs)."""
        return self._geometry_form

    @property
    def target_panel(self) -> TargetShapePanel:
        """The embedded shared :class:`TargetShapePanel` (shape combo + dims + RPY)."""
        return self._target_panel

    @property
    def shape_combo(self) -> QComboBox:
        """The target-shape combo box."""
        return self._target_panel.shape_combo

    @property
    def triad_checkbox(self) -> QCheckBox:
        """The 'show orientation triad' checkbox."""
        return self._target_panel.triad_checkbox

    def rpy_row(self, dotpath: str) -> FieldRow:
        """The RPY field row for *dotpath* (KeyError if unknown)."""
        return self._target_panel.rpy_row(dotpath)

    def dimension_row(self, dotpath: str) -> FieldRow:
        """The shape-dimension field row for *dotpath* (KeyError if unknown)."""
        return self._target_panel.dimension_row(dotpath)

    def visible_dimensions(self) -> tuple[str, ...]:
        """The dimension dot-paths whose rows are currently shown (for tests)."""
        return self._target_panel.visible_dimensions()

    def set_toolbox_page(self, index: int) -> None:
        """Select an accordion page (0 = Geometry inputs, 1 = Target) — shape/RPY flow."""
        self._toolbox.setCurrentIndex(index)
