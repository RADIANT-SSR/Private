"""The Atmosphere stage's **Inputs** section — model selector + per-model parameters.

:class:`AtmosphereInputsForm` is the *Inputs* section of the Atmosphere stage's contextual
center (arch doc §4.4 section 1, GUI Capability Expansion plan Phase GS-2). It closes the
audit's A-1…A-4 gap: before GS-2 the Atmosphere stage had **no editable inputs at all**,
while the engine carries five backends behind one enum. The card shows:

- **Model** — the ``atmosphere.model`` selector (``simple`` / ``exo`` / ``tabulated`` /
  ``modtran`` / ``interpolated``); editing it swaps which per-model group below is shown.
- **Per-model group** — only the active model's parameters are visible (the others hide,
  the same only-the-active-door discipline as the Geometry mode forms): the parametric
  (simple) knobs, the MODTRAN tape7 + profile/aerosol/scaling knobs, the tabulated file
  paths, or the interpolated run-matrix knobs. ``exo`` (vacuum) shows a themed note — it
  has no knobs by design.
- **Turbulence** — the Fried parameter ``atmosphere.r0_m`` (model-independent).

File-path parameters (tape7, tabulated CSVs, run-matrix dir) are ordinary string schema
fields: editing one opens the shared editor (type or paste the path); the loaders resolve
and validate the file pre-chain (Rule 6) and a bad path raises the loader's actionable
error into the Messages panel. The richer ADR-0009 D5 preview-import dialog is the
follow-on; this form is the plan's sanctioned file-picker fallback.

**Schema-driven, one API call per edit (Gap 70 / R-API).** Every field is built from and
formatted through the public :class:`~radiant.api.sensor.Sensor` surface; editing a field
opens the shared
:class:`~radiant.gui.widgets.parameter_editor_dialog.ParameterEditorDialog`, so a commit is
exactly one ``sensor.set`` validated on a throwaway clone first — the identical edit+reject
discipline as every other Inputs form. The value shows in the row's **display unit**,
sharing the session display-unit store. Each accepted edit re-emits
:attr:`parameterEdited`, so the host debounces a full re-evaluation and the τ/L_path and
before/after-aperture plots refresh (edit-and-watch); an accepted **model** edit also
re-runs :meth:`refresh`, swapping the visible group.

Every field is the shared :class:`~radiant.gui.widgets.field_row.FieldRow`. All
colour/typography comes from the QSS theme via object names (GUI plan §4.9); this file
holds no colour/font literal. One widget class per file (Rule 19).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from radiant.core.exceptions import RadiantError
from radiant.gui.param_format import field_display_text
from radiant.gui.widgets.field_row import UNSET as _UNSET
from radiant.gui.widgets.field_row import FieldRow
from radiant.gui.widgets.parameter_editor_dialog import ParameterEditorDialog

if TYPE_CHECKING:
    from radiant.api.sensor import Sensor

# The model selector (label, dot-path). Bounds/choices/description come from the live
# schema (never transcribed) — only the human label + grouping is a literal here (CU-120).
_MODEL_FIELDS: Final[tuple[tuple[str, str], ...]] = (("Atmosphere model", "atmosphere.model"),)

# Parametric (simple) knobs — shown when model == "simple".
_SIMPLE_FIELDS: Final[tuple[tuple[str, str], ...]] = (
    ("Standard atmosphere", "atmosphere.standard_atmosphere"),
    ("Aerosol type", "atmosphere.aerosol_type"),
    ("Visibility", "atmosphere.visibility_km"),
    ("Precipitable water", "atmosphere.precipitable_water_cm"),
)

# MODTRAN knobs — shown when model == "modtran". The tape7 import paths lead; the
# binary/cache/fallback plumbing stays in the All-Parameters tree (advanced, rarely edited).
_MODTRAN_FIELDS: Final[tuple[tuple[str, str], ...]] = (
    ("Tape7 file (import)", "atmosphere.modtran.tape7_path"),
    ("Tape7 sun-path file", "atmosphere.modtran.tape7_sun_path"),
    ("Atmosphere profile", "atmosphere.modtran.atmosphere_profile"),
    ("Aerosol model", "atmosphere.modtran.aerosol_model"),
    ("H₂O column scale", "atmosphere.modtran.h2o_scale"),
    ("O₃ column scale", "atmosphere.modtran.o3_scale"),
)

# Tabulated-file knobs — shown when model == "tabulated".
_TABULATED_FIELDS: Final[tuple[tuple[str, str], ...]] = (
    ("Transmittance file", "atmosphere.tabulated_transmittance_file"),
    ("Path-radiance file", "atmosphere.tabulated_path_radiance_file"),
    ("Downwelling file (optional)", "atmosphere.tabulated_downwelling_file"),
)

# Interpolated run-matrix knobs — shown when model == "interpolated".
_INTERPOLATED_FIELDS: Final[tuple[tuple[str, str], ...]] = (
    ("Run-matrix directory", "atmosphere.interpolated_data_dir"),
    ("Interpolation axes", "atmosphere.interpolation_axes"),
    ("Interpolation method", "atmosphere.interpolation_method"),
)

# Turbulence — model-independent (Kolmogorov long-exposure MTF; 0 disables).
_TURBULENCE_FIELDS: Final[tuple[tuple[str, str], ...]] = (
    ("Fried parameter r₀ (0 = off)", "atmosphere.r0_m"),
)

_TITLE = "Atmosphere — model & propagation inputs"
_EXO_NOTE = (
    "Exo (vacuum) model: τ = 1, no path radiance — no atmosphere parameters apply. "
    "Used for space-to-space and lab/TVAC scenarios."
)

# model value -> its group key (the group shown for that model; None → note only).
_MODEL_GROUPS: Final[dict[str, str | None]] = {
    "simple": "simple",
    "modtran": "modtran",
    "tabulated": "tabulated",
    "interpolated": "interpolated",
    "exo": None,
}


class AtmosphereInputsForm(QWidget):
    """The Atmosphere inputs card: model selector + the active model's schema fields.

    Signals
    -------
    parameterEdited(str):
        Emitted with the dot-path after an accepted edit, so the host window can refresh
        the parameter tree, this form, and schedule a re-evaluation — the same contract
        as every other Inputs form.
    """

    parameterEdited = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("atmosphereInputsForm")

        self._sensor: Sensor | None = None
        self._display_units: dict[str, str] = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        card = QWidget(self)
        card.setObjectName("geoModeFamily")
        card.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        card.setProperty("state", "normal")
        box = QVBoxLayout(card)
        box.setContentsMargins(12, 10, 12, 10)
        box.setSpacing(6)

        title = QLabel(_TITLE, card)
        title.setObjectName("geoModeFamilyTitle")
        title.setWordWrap(True)
        box.addWidget(title)

        self._rows: dict[str, FieldRow] = {}
        # Model-specific groups are wrapped in per-group containers so refresh() can
        # show exactly the active model's group (the others hide — same discipline as
        # the geometry mode forms showing only the active door).
        self._groups: dict[str, QWidget] = {}
        self._add_group(box, card, "Model", _MODEL_FIELDS)
        self._groups["simple"] = self._add_group(box, card, "Parametric (simple)", _SIMPLE_FIELDS)
        self._groups["modtran"] = self._add_group(box, card, "MODTRAN", _MODTRAN_FIELDS)
        self._groups["tabulated"] = self._add_group(box, card, "Tabulated files", _TABULATED_FIELDS)
        self._groups["interpolated"] = self._add_group(
            box, card, "Interpolated run matrix", _INTERPOLATED_FIELDS
        )
        # The exo note (shown only for the vacuum model).
        self._exo_note = QLabel(_EXO_NOTE, card)
        self._exo_note.setObjectName("stageCenterNote")
        self._exo_note.setWordWrap(True)
        self._exo_note.hide()
        box.addWidget(self._exo_note)
        self._add_group(box, card, "Turbulence", _TURBULENCE_FIELDS)

        layout.addWidget(card)

    def _add_group(
        self,
        box: QVBoxLayout,
        card: QWidget,
        heading: str,
        fields: tuple[tuple[str, str], ...],
    ) -> QWidget:
        """Add a titled sub-group in its own container (so it can show/hide as one)."""
        group = QWidget(card)
        group_box = QVBoxLayout(group)
        group_box.setContentsMargins(0, 0, 0, 0)
        group_box.setSpacing(6)
        label = QLabel(heading, group)
        label.setObjectName("geoModeGroupHeading")
        group_box.addWidget(label)
        for text, dotpath in fields:
            row = FieldRow(dotpath, text, self._open_editor)
            group_box.addWidget(row)
            self._rows[dotpath] = row
        box.addWidget(group)
        return group

    # -- binding / refresh --------------------------------------------------

    def bind_sensor(self, sensor: Sensor | None, display_units: dict[str, str]) -> None:
        """Bind the live *sensor* and the shared *display_units* store, then refresh."""
        self._sensor = sensor
        self._display_units = display_units
        self.refresh()

    def refresh(self) -> None:
        """Re-read every field and show only the active model's group.

        The model value is read from the live sensor input (``get_input`` — the resolved
        enum string). With no sensor every group shows blank fields under the selector.
        """
        for dotpath, row in self._rows.items():
            row.set_value_text(self._value_text(dotpath))

        model = self._current_model()
        active = _MODEL_GROUPS.get(model, "simple") if model is not None else None
        for key, group in self._groups.items():
            group.setVisible(model is None or key == active)
        self._exo_note.setVisible(model == "exo")

    def _current_model(self) -> str | None:
        """The current ``atmosphere.model`` value, or None with no sensor.

        A sensor that cannot resolve (an invalid in-progress config) also returns None —
        every group then shows, never a wrongly-hidden field. The resolution error itself
        surfaces on evaluate through the Messages panel; it is not this row's to report.
        """
        if self._sensor is None:
            return None
        try:
            return str(self._sensor.get_input("atmosphere.model"))
        except RadiantError:
            return None

    def _value_text(self, dotpath: str) -> str:
        """The value+unit text for *dotpath* in its display unit (— if unset)."""
        sensor = self._sensor
        if sensor is None:
            return _UNSET
        return field_display_text(sensor, dotpath, self._display_units)

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
        dialog.exec()

    def _after_commit(self, dotpath: str, unit: str | None) -> None:
        """Record the display unit, refresh (a model edit swaps groups), notify the host."""
        if unit is not None:
            self._display_units[dotpath] = unit
        self.refresh()
        self.parameterEdited.emit(dotpath)

    # -- accessors (tests) ----------------------------------------------------

    def field_dotpaths(self) -> tuple[str, ...]:
        """The parameter dot-paths this form edits, in order."""
        return tuple(self._rows)

    def row(self, dotpath: str) -> FieldRow:
        """The :class:`FieldRow` for *dotpath* (KeyError if unknown)."""
        return self._rows[dotpath]

    def group_visible(self, key: str) -> bool:
        """Whether the model group *key* is currently shown (tests)."""
        return self._groups[key].isVisible()


__all__ = ["AtmosphereInputsForm"]
