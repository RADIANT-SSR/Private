"""Site-elevation entry for the Geometry screen — the one non-mode scene fact (CU-301).

:class:`SiteElevationPanel` is a small bespoke card on the Geometry stage's **Inputs**
tab carrying a single parameter, ``geometry.site_elevation_m``: the terrain elevation
of the scene's ground site above mean sea level.

**Why it needs a bespoke card at all.** The rest of the Geometry Inputs tab is rendered
from the *mode manifest* (:mod:`radiant.gui.geometry_modes`), which enumerates the
input-mode doors — the mutually exclusive ways of specifying the viewing, solar,
kinematics and LOS-rate families. Site elevation is not a door onto any canonical
viewing quantity; it is a standalone scene fact, and the schema tags it ``non_mode`` to
say so (the tag the manifest-coverage drift tests subtract, CU-309). Being outside the
manifest left it reachable only from YAML or the scripting API — exactly where
``geometry.scene_class`` sat before it got its own
:mod:`~radiant.gui.widgets.scene_class_panel`, and the precedent this card follows.

**Results-affecting, so it edits like every other geometry input.** The parameter feeds
the Hufnagel-Valley Cn² surface term (CU-262: the surface layer is evaluated at
``h − site_elevation_m``, so an elevated observatory keeps its own boundary layer), which
moves the turbulence MTF and every metric downstream of it. The row is therefore the
shared :class:`~radiant.gui.widgets.field_row.FieldRow` and editing it opens the shared
:class:`~radiant.gui.widgets.parameter_editor_dialog.ParameterEditorDialog` — one
``sensor.set`` validated on a throwaway clone first, so a rejected value never touches
the live sensor and its actionable what/why/action reaches the Messages rail — and each
accepted edit re-emits :attr:`parameterEdited` so results go stale and the host
re-evaluates. Identical discipline to the mode forms and the scene-class card.

**Units (display-units rule).** The value is shown through
:func:`radiant.gui.param_format.field_display_text` in the row's session display unit,
and the editor dialog offers the same unit for entry — so an analyst working in feet
enters feet and reads feet back, and never converts by hand. The unit store is the
shared session dict, so a unit chosen here or anywhere else agrees everywhere.

One widget class per file (Rule 19). All colour/typography comes from the QSS theme via
object names (GUI plan §4.9); this file holds no colour/font literal.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from radiant.gui.dialog_lifetime import exec_dialog
from radiant.gui.param_format import field_display_text
from radiant.gui.widgets.field_row import UNSET as _UNSET
from radiant.gui.widgets.field_row import FieldRow
from radiant.gui.widgets.parameter_editor_dialog import ParameterEditorDialog

if TYPE_CHECKING:
    from radiant.api.sensor import Sensor

#: The one parameter this card carries (CU-262; schema-tagged ``non_mode``).
SITE_ELEVATION_PARAM: Final[str] = "geometry.site_elevation_m"

_TITLE: Final[str] = "Site elevation — terrain under the line of sight"
_LABEL: Final[str] = "Site elevation"
_NOTE: Final[str] = (
    "Elevation of the ground SITE the boundary layer sits on — not the lowest point of "
    "the line of sight. Whose site it is follows the topology: down-looking, the terrain "
    "under the target; up-looking, the terrain under the sensor; level, the shared terrain "
    "under the arm. Consumed by the Hufnagel-Valley Cn² profile only "
    "(Atmosphere → cn2_profile); against a tabulated or direct profile it is inert and the "
    "run says so. The default 0 m is mean sea level."
)


class SiteElevationPanel(QWidget):
    """The Geometry Inputs tab's site-elevation card: one unit-bearing field + a note.

    Parameters
    ----------
    parent:
        The owning widget, if any.

    Signals
    -------
    parameterEdited(str):
        Emitted with the dot-path after an accepted edit, so the host window refreshes
        the parameter tree, marks results stale and schedules a re-evaluation — the same
        contract as every other Geometry Inputs surface.
    """

    parameterEdited = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("siteElevationPanel")

        self._sensor: Sensor | None = None
        self._display_units: dict[str, str] = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        # A bare QWidget paints no QSS background/border unless styled-background is on;
        # the card fill needs it (the same Qt gotcha the scene-class card documents).
        self._card = QWidget(self)
        self._card.setObjectName("siteElevationCard")
        self._card.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        box = QVBoxLayout(self._card)
        box.setContentsMargins(12, 10, 12, 10)
        box.setSpacing(6)

        title = QLabel(_TITLE, self._card)
        title.setObjectName("siteElevationTitle")
        title.setWordWrap(True)
        box.addWidget(title)

        self._row = FieldRow(SITE_ELEVATION_PARAM, _LABEL, self._open_editor)
        box.addWidget(self._row)

        note = QLabel(_NOTE, self._card)
        note.setObjectName("siteElevationNote")
        note.setWordWrap(True)
        box.addWidget(note)

        layout.addWidget(self._card)

    # -- binding / refresh --------------------------------------------------

    def bind_sensor(self, sensor: Sensor | None, display_units: dict[str, str]) -> None:
        """Bind the live *sensor* and the shared *display_units* store, then refresh.

        *display_units* is the session's display-unit dict (shared by reference), so a
        unit chosen in this card, the parameter tree, or any other form agrees in all of
        them. A ``None`` sensor blanks the field (the pre-config state).
        """
        self._sensor = sensor
        self._display_units = display_units
        self.refresh()

    def refresh(self) -> None:
        """Re-read the field's value in its display unit from the bound sensor."""
        self._row.set_value_text(self._value_text())

    def _value_text(self) -> str:
        """The value+unit text in the chosen display unit (— with no sensor)."""
        sensor = self._sensor
        if sensor is None:
            return _UNSET
        return field_display_text(sensor, SITE_ELEVATION_PARAM, self._display_units)

    # -- editing (reuses the Parameter Editor dialog + reject discipline) ----

    def _open_editor(self, dotpath: str) -> None:
        """Open the full Parameter Editor for *dotpath* (one API call on commit)."""
        if self._sensor is None:
            return
        dialog = ParameterEditorDialog(
            self._sensor,
            dotpath,
            self._after_commit,
            self,
            display_unit=self._display_units.get(dotpath),
        )
        exec_dialog(dialog)

    def _after_commit(self, dotpath: str, unit: str | None) -> None:
        """Record the chosen display unit, refresh, and signal the edit upstream."""
        if unit is not None:
            self._display_units[dotpath] = unit
        self.refresh()
        self.parameterEdited.emit(dotpath)

    # -- accessors (tests) --------------------------------------------------

    @property
    def field_row(self) -> FieldRow:
        """The ``geometry.site_elevation_m`` field row."""
        return self._row

    def value_text(self) -> str:
        """The displayed value+unit text (for tests)."""
        return self._row.value_text()


__all__ = ["SITE_ELEVATION_PARAM", "SiteElevationPanel"]
