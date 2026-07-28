"""The Source stage's radiometric **Inputs** section — editable schema-driven fields.

:class:`SourceInputsForm` is the *Inputs* section of the Source stage's contextual center
(arch doc §4.4 section 1, GUI plan Phase PS-1): the key source radiometric parameters —
target (ε, T), background (ε, T), and the extended contrast-reference (ε, T) — as editable
schema-driven rows. Together with the emission spectra and the Outputs readout it makes the
Source stage an *instrument*, matching the Geometry-screen standard. Target
extent/shape/orientation is **not** Source content: it is geometry (``geometry.target.*``,
post-TEG) and is edited on Geometry → Schematic only (GT-0 / Windows finding 14 — the
Source-tab duplicate of the shape editor was removed).

**Schema-driven, one API call per edit (Gap 70 / R-API).** Every field is built from and
formatted through the public :class:`~radiant.api.sensor.Sensor` surface
(:meth:`Sensor.parameter_def` for the label/unit, :meth:`Sensor.get_input` for the value).
Editing a field opens the shared
:class:`~radiant.gui.widgets.parameter_editor_dialog.ParameterEditorDialog`, so a commit is
exactly one ``sensor.set`` validated on a throwaway clone first (a rejected value never
touches the live sensor; the actionable what/why/action shows inline) — the identical
edit+reject discipline as the parameter tree (Phase 2) and the Geometry Inputs form
(Phase 5). The value shows in the row's **display unit**, sharing the parameter panel's
session display-unit store so a unit chosen on any surface agrees. Each accepted edit
re-emits :attr:`parameterEdited`, so the host debounces a full re-evaluation and the
emission spectra + Outputs readout refresh (edit-and-watch).

Every field is the shared :class:`~radiant.gui.widgets.field_row.FieldRow` — the same
building block the Geometry mode form and the target-shape panel use — so the Source inputs
render **identically by construction** to every other schema-driven field (owner hard rule:
"the target/source boxes should be just like the geometry boxes"). All colour/typography
comes from the QSS theme via object names (GUI plan §4.9); this file holds no colour/font
literal. One widget class per file (Rule 19).
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

# The source radiometric + scene-declaration parameters (label, dot-path), grouped (GUI
# Capability Expansion plan GS-1 — audit S-1…S-6: the pre-GS-1 card could only express a
# graybody thermal emitter; the reflective/solar pathway, the scene-type declaration, and
# the sub-pixel knobs were invisible). Bounds/units/choices/description all come from the
# live schema (never transcribed) — only the labels + grouping are literals here (CU-120).
#
# Reflective note: `source.target.albedo`/`albedo_path` are user-facing *aliases* of
# reflectance (mutually exclusive) — the form exposes only the `reflectance` surfaces so
# the GUI never invites an over-specified pair; the aliases stay reachable in the
# All-Parameters tree. Both reflectance surfaces are mounted (owner walkthrough item 6:
# "should be able to input R(lambda) as well"): the scalar ρ and the ρ(λ) CSV. They are
# themselves mutually exclusive, and the engine says so — setting the second opens the
# shared editor's reject path with the actionable what/why/action, exactly as any other
# over-specified pair does.
_THERMAL_FIELDS: Final[tuple[tuple[str, str], ...]] = (
    ("Target temperature", "source.target.temperature"),
    ("Target emissivity", "source.target.emissivity"),
    ("Hot target (force pure-emit)", "source.target.is_hot_target"),
)

_REFLECTIVE_FIELDS: Final[tuple[tuple[str, str], ...]] = (
    ("Target reflectance ρ (VIS/solar)", "source.target.reflectance"),
    ("Target ρ(λ) file (spectral)", "source.target.reflectance_path"),
    ("Solar illumination (Geometry)", "geometry.solar_illumination"),
    ("Solar zenith angle (Geometry)", "geometry.solar_zenith_rad"),
    ("Solar azimuth angle (Geometry)", "geometry.solar_azimuth_rad"),
)

# Sun geometry has exactly one owner — the Geometry stage — but the reflective
# pathway is where its consequence is visible, so the rows show here read-only
# (owner walkthrough item 6: keep them, they answer "why is my reflected term
# dark?", but do not offer a second editor for a Geometry-owned parameter).
_GEOMETRY_OWNED: Final[frozenset[str]] = frozenset(
    {
        "geometry.solar_illumination",
        "geometry.solar_zenith_rad",
        "geometry.solar_azimuth_rad",
    }
)
_GEOMETRY_OWNED_REASON: Final[str] = (
    "Owned by the Geometry stage — read-only here. Edit it on Geometry → Inputs "
    "(solar illumination / zenith / azimuth). It is shown on this tab because it "
    "drives the reflected-solar term: no sun, no reflected radiance."
)
_SOLAR_NOTE_TEXT: Final[str] = (
    "Sun geometry is defined on the Geometry stage; the three rows above are "
    "read-only mirrors. ρ is the surface property — the plots pair it with the "
    "reflected radiance it produces under this scene's illumination."
)

_BACKGROUND_FIELDS: Final[tuple[tuple[str, str], ...]] = (
    ("Background temperature", "source.background.temperature"),
    ("Background emissivity", "source.background.emissivity"),
    ("Background material (library)", "source.background.material"),
    ("Contrast ref. temperature", "source.contrast_reference.temperature"),
    ("Contrast ref. emissivity", "source.contrast_reference.emissivity"),
)

_SCENE_FIELDS: Final[tuple[tuple[str, str], ...]] = (
    ("Scene type (declared)", "source.scene_type"),
    ("Regime override (force)", "source.regime_override"),
    ("Fill fraction (sub-pixel)", "source.target.fill_fraction"),
)

# Point-source radiant intensity I(λ) [W/sr] — the point-source-regime input (Gap 98 D).
# A true point source is defined by intensity, not surface radiance × area; these rows
# carry the ``regime:point_source`` schema tag so they gate ON only for a point-source
# scene (and the thermal surface-radiance rows gate OFF — see _THERMAL_FIELDS tags).
_POINT_INTENSITY_FIELDS: Final[tuple[tuple[str, str], ...]] = (
    ("Emitter temperature (blackbody I)", "source.target.point_intensity_temperature_K"),
    ("Emitting area (blackbody I)", "source.target.point_intensity_area_m2"),
    ("Emitter emissivity (blackbody I)", "source.target.point_intensity_emissivity"),
    ("Band-integrated intensity [W/sr]", "source.target.point_intensity_band_W_per_sr"),
)

# The flat union, in display order — the single manifest tests and hosts iterate.
_RADIOMETRY_FIELDS: Final[tuple[tuple[str, str], ...]] = (
    _THERMAL_FIELDS
    + _REFLECTIVE_FIELDS
    + _POINT_INTENSITY_FIELDS
    + _BACKGROUND_FIELDS
    + _SCENE_FIELDS
)

# (heading, fields) in reading order: what the target emits, what it reflects, what
# surrounds it, and what the operator declares the scene to be.
# (key, heading, fields): the key is the GT-0 tab filter handle (stage_views
# names the groups each Source tab mounts).
_GROUPS: Final[tuple[tuple[str, str, tuple[tuple[str, str], ...]], ...]] = (
    ("scene", "Scene type & regime", _SCENE_FIELDS),
    ("thermal", "Thermal (emissive)", _THERMAL_FIELDS),
    ("reflective", "Reflective (solar)", _REFLECTIVE_FIELDS),
    ("point_source", "Point-source intensity", _POINT_INTENSITY_FIELDS),
    ("background", "Background & contrast reference", _BACKGROUND_FIELDS),
)

_SCENE_TYPE_PATH = "source.scene_type"

_TITLE = "Source — thermal & reflective radiometry, scene declaration"


class SourceInputsForm(QWidget):
    """The Source radiometric inputs card: schema-driven :class:`FieldRow` per parameter.

    Parameters
    ----------
    parent:
        The owning widget, if any.

    Signals
    -------
    parameterEdited(str):
        Emitted with the dot-path after an accepted edit, so the host window can refresh
        the parameter tree, this form, and schedule a re-evaluation — the same contract as
        :attr:`GeometryModeForm.parameterEdited`.
    """

    parameterEdited = Signal(str)

    def __init__(
        self,
        parent: QWidget | None = None,
        groups: tuple[str, ...] | None = None,
    ) -> None:
        """*groups* filters which keyed groups render (None = all — the flat card).

        The GT-0 Source tabs each mount one group ("scene" / "thermal" /
        "reflective" / "background"); the tab label then provides the context,
        so a filtered card suppresses the big title.
        """
        super().__init__(parent)
        self.setObjectName("sourceInputsForm")
        self._groups_filter = groups

        self._sensor: Sensor | None = None
        self._display_units: dict[str, str] = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        # One ``geoModeFamily`` card (same object name → same QSS as every geometry card), so
        # the Source inputs sit in an identically-styled card to the geometry/target fields.
        card = QWidget(self)
        card.setObjectName("geoModeFamily")
        card.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        card.setProperty("state", "normal")
        box = QVBoxLayout(card)
        box.setContentsMargins(12, 10, 12, 10)
        box.setSpacing(6)

        if groups is None:
            title = QLabel(_TITLE, card)
            title.setObjectName("geoModeFamilyTitle")
            title.setWordWrap(True)
            box.addWidget(title)

        self._rows: dict[str, FieldRow] = {}
        self._albedo_note: QLabel | None = None
        for key, heading, fields in _GROUPS:
            if groups is not None and key not in groups:
                continue
            group_label = QLabel(heading, card)
            group_label.setObjectName("geoModeGroupHeading")
            box.addWidget(group_label)
            for label, dotpath in fields:
                row = FieldRow(dotpath, label, self._open_editor)
                if dotpath in _GEOMETRY_OWNED:
                    row.set_read_only(_GEOMETRY_OWNED_REASON)
                box.addWidget(row)
                self._rows[dotpath] = row
            if key == "reflective":
                # Name the owner in the pane itself, not only in a tooltip: the
                # operator must know where to go to change the sun.
                solar_note = QLabel(_SOLAR_NOTE_TEXT, card)
                solar_note.setObjectName("stageCenterNote")
                solar_note.setWordWrap(True)
                box.addWidget(solar_note)
            if key == "background":
                # GT-0 derived-albedo readout (owner, 2026-07-16): the assembly's
                # daytime reflected-ground term uses exactly ρ_g = 1 − ε_g
                # (Kirchhoff); in VIS this is the number intuition checks, so it
                # shows derived and read-only — never an input (Rule 5 spirit).
                self._albedo_note = QLabel("", card)
                self._albedo_note.setObjectName("stageCenterNote")
                self._albedo_note.setWordWrap(True)
                box.addWidget(self._albedo_note)

        layout.addWidget(card)

    # -- binding / refresh --------------------------------------------------

    def bind_sensor(self, sensor: Sensor | None, display_units: dict[str, str]) -> None:
        """Bind the live *sensor* and the shared *display_units* store, then refresh.

        *display_units* is the parameter panel's session display-unit dict (shared by
        reference), so a unit chosen on any surface reflects here. A ``None`` sensor blanks
        every field (the pre-config state).
        """
        self._sensor = sensor
        self._display_units = display_units
        self.refresh()

    def refresh(self) -> None:
        """Re-read every field and gate rows on the declared scene type (Gap 85).

        A parameter carrying ``regime:<type>`` schema tags matters only for those
        declared scene types: when ``source.scene_type`` is declared (not ``auto``)
        and excludes a row's regimes, the row disables with an explanatory tooltip
        (badged, never hidden — the field stays discoverable). ``auto`` (or an
        unresolvable in-progress config) gates nothing. The tags live on the
        ``ParameterDef``s (never transcribed here).
        """
        declared = self._declared_scene_type()
        self._refresh_albedo_note()
        for dotpath, row in self._rows.items():
            row.set_value_text(self._value_text(dotpath))
            if row.is_read_only:
                # A Geometry-owned mirror: its value refreshes, but neither the
                # relevance gating nor its tooltip is this form's to rewrite.
                continue
            regimes = self._regime_tags(dotpath)
            relevant = (
                declared in (None, "auto")
                or not regimes
                or dotpath == _SCENE_TYPE_PATH
                or declared in regimes
            )
            if relevant:
                row.set_editable(True)
                row.setToolTip("")
            else:
                row.set_editable(False)
                row.setToolTip(
                    f"Not used for declared scene type '{declared}' "
                    f"(relevant for: {', '.join(sorted(regimes))}). "
                    "Set Scene type to 'auto' to edit freely."
                )

    def _refresh_albedo_note(self) -> None:
        """Fill the derived ground-albedo line (ρ_g = 1 − ε_g, the Kirchhoff term).

        Scalar ε → a number; a library material or ε(λ) CSV → a spectral note
        (the band-dependent ρ(λ) = 1 − ε(λ) is what the physics uses).
        """
        if self._albedo_note is None:
            return
        sensor = self._sensor
        if sensor is None:
            self._albedo_note.setText("")
            return
        try:
            material = str(sensor.get_input("source.background.material") or "")
            eps_path = str(sensor.get_input("source.background.emissivity_path") or "")
            eps = sensor.get_input("source.background.emissivity")
        except RadiantError:
            self._albedo_note.setText("")
            return
        if eps_path or (material and material not in ("", "grey", "gray")):
            self._albedo_note.setText(
                "Implied ground albedo: ρ(λ) = 1 − ε(λ) from the spectral background "
                "(daytime reflected-ground term uses it directly)."
            )
        elif eps is not None:
            rho = 1.0 - float(eps)
            self._albedo_note.setText(
                f"Implied ground albedo ρ = 1 − ε = {rho:.3f} (derived — the daytime "
                f"reflected-ground radiance uses this; in VIS pick ε so ρ matches "
                f"your ground)."
            )
        else:
            self._albedo_note.setText("")

    def _declared_scene_type(self) -> str | None:
        """The declared source.scene_type, or None with no / unresolvable sensor."""
        if self._sensor is None:
            return None
        try:
            return str(self._sensor.get_input(_SCENE_TYPE_PATH))
        except RadiantError:
            return None

    def _regime_tags(self, dotpath: str) -> set[str]:
        """The regime:<type> tag values on *dotpath* (empty = regime-independent)."""
        if self._sensor is None:
            return set()
        pdef = self._sensor.parameter_def(dotpath)
        return {tag.split(":", 1)[1] for tag in pdef.tags if tag.startswith("regime:")}

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
        """Record the chosen display unit, refresh, and signal the edit upstream."""
        if unit is not None:
            self._display_units[dotpath] = unit
        self.refresh()
        self.parameterEdited.emit(dotpath)

    # -- accessors (tests) --------------------------------------------------

    def field_dotpaths(self) -> tuple[str, ...]:
        """The parameter dot-paths this form edits, in order."""
        return tuple(self._rows)

    def field_value_text(self, dotpath: str) -> str:
        """The displayed value+unit text of the field for *dotpath*."""
        return self._rows[dotpath].value_text()

    def row(self, dotpath: str) -> FieldRow:
        """The :class:`FieldRow` for *dotpath* (KeyError if unknown)."""
        return self._rows[dotpath]


__all__ = ["SourceInputsForm"]
