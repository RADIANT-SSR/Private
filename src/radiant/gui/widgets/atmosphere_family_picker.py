"""The interpolated-atmosphere **family picker** — the closed catalogue as a list (CU-239).

:class:`AtmosphereFamilyPicker` replaces the free-text ``atmosphere.interpolation_axes``
row inside the Atmosphere stage's *Interpolated run matrix* group. The contract it fixes
was inverted: the bundled library is a **closed, known set** keyed by
``(los_direction, interpolation_axes)``, yet the GUI asked the operator to reconstruct a
dictionary key by hand — and the only feedback for a wrong key was a mid-evaluation
refusal (owner session, 2026-07-27: a LEO nadir → 20 km sub-pixel target, the textbook
interpolated scenario, failed because the default axes string still read
``path_zenith_rad``).

What it shows, all of it read from :func:`radiant.api.shipped_atmosphere_families`
(the GUI imports :mod:`radiant.api` only — no physics package, no re-typed catalogue):

* **One row per bundled family**, labelled with its name and rendered profile, with the
  full plain-language coverage line — **units always explicit** (km, degrees) — under
  the box for the selected row.
* **The scene's recommendation.** ``Sensor.suggested_atmosphere_family()`` derives, from
  the resolved geometry, which family the scene actually calls for; that row is marked
  ``(recommended for this scene)`` and named in the note beneath. When the configured
  family does not cover the scene, the recommended row is *pre-selected* as a proposal
  and an explicit **Use this family** button writes it — a proposal is never applied
  behind the operator's back, because adopting a family can change the atmosphere
  profile.
* **The profile-mismatch caveat.** Whenever the highlighted family's rendered profile
  differs from an explicitly-set ``atmosphere.standard_atmosphere``, the picker shows
  the API's own warning sentence. Choosing a family must never silently change the
  atmosphere the operator asked for (the CU's non-negotiable).
* **The boost ladder, by name.** ``midlat_summer_boost_ladder`` ships 24 MODTRAN runs
  whose ``(down, sensor_altitude_m,target_altitude_m)`` signature is already owned by
  ``midlat_summer_ladders``, so **no** axes string could ever select it (ex-CU-296). The
  picker enumerates the catalogue directly, so it offers the family by name and writes
  its ``bundled_dir`` into ``atmosphere.interpolated_data_dir`` for the operator.
* **An escape hatch.** The last entry, *Custom axes… (advanced)*, restores the free-text
  row: it opens the shared
  :class:`~radiant.gui.widgets.parameter_editor_dialog.ParameterEditorDialog` on
  ``atmosphere.interpolation_axes`` exactly as before, for a hand-built run matrix that
  is not in the catalogue. The picker is the default path; free text is the exception,
  and an unrecognized configured value selects this entry rather than being hidden.

**One action ↔ one API call.** Choosing a catalogue row is one user action, so its
parameter writes are emitted as a single compound edit
(:attr:`parametersEdited`) which the window records as one undo step — the same
``compoundParameterEdited`` contract the geometry shape picker uses (CU-141). The picker
never resolves, never evaluates, and never mutates anything but the two parameters it
owns.

One widget class per file (Rule 19); every colour/font comes from the QSS theme via
object names (GUI plan §4.9).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from radiant.api.atmosphere_families import ShippedFamily, shipped_atmosphere_families
from radiant.core.exceptions import RadiantError
from radiant.gui.dialog_lifetime import exec_dialog
from radiant.gui.widgets.field_row import LABEL_COLUMN_WIDTH, VALUE_BOX_MAX
from radiant.gui.widgets.parameter_editor_dialog import ParameterEditorDialog

if TYPE_CHECKING:
    from radiant.api.sensor import Sensor

#: The two parameters this picker owns.
AXES_PARAM: Final[str] = "atmosphere.interpolation_axes"
DATA_DIR_PARAM: Final[str] = "atmosphere.interpolated_data_dir"

#: Label of the free-text escape hatch, always the last entry.
CUSTOM_LABEL: Final[str] = "Custom axes… (advanced)"

#: Suffix marking the family the resolved scene calls for.
RECOMMENDED_SUFFIX: Final[str] = "  (recommended for this scene)"

_HEADING: Final[str] = "Library family"
_APPLY_TEXT: Final[str] = "Use this family"
_NO_SENSOR: Final[str] = "—"
_CUSTOM_NOTE: Final[str] = (
    "Free-text axes — no bundled family matches. Click the axes row to edit it, or pick "
    "a family above."
)


class AtmosphereFamilyPicker(QWidget):
    """Pick a bundled interpolation family instead of typing its axes key.

    Signals
    -------
    parametersEdited(list):
        Emitted with the dot-paths written by one user action (one or two), so the
        host records a single undo step and schedules one re-evaluation.
    """

    parametersEdited = Signal(list)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("atmosphereFamilyPicker")

        self._sensor: Sensor | None = None
        self._display_units: dict[str, str] = {}
        self._families: tuple[ShippedFamily, ...] = shipped_atmosphere_families()
        self._recommended: ShippedFamily | None = None
        self._configured: ShippedFamily | None = None
        self._pending: bool = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        top.setSpacing(6)
        heading = QLabel(_HEADING, self)
        heading.setObjectName("geoModeFieldLabel")
        heading.setFixedWidth(LABEL_COLUMN_WIDTH)
        top.addWidget(heading)

        self._combo = QComboBox(self)
        self._combo.setObjectName("atmosphereFamilyCombo")
        self._combo.setMaximumWidth(VALUE_BOX_MAX * 2)
        self._combo.activated.connect(self._on_activated)
        top.addWidget(self._combo)
        top.addStretch(1)
        layout.addLayout(top)

        self._coverage = QLabel("", self)
        self._coverage.setObjectName("stageCenterNote")
        self._coverage.setWordWrap(True)
        layout.addWidget(self._coverage)

        self._warning = QLabel("", self)
        self._warning.setObjectName("stageCenterNote")
        self._warning.setWordWrap(True)
        self._warning.hide()
        layout.addWidget(self._warning)

        self._apply = QPushButton(_APPLY_TEXT, self)
        self._apply.setObjectName("atmosphereFamilyApplyButton")
        self._apply.setMaximumWidth(LABEL_COLUMN_WIDTH + VALUE_BOX_MAX + 10)
        self._apply.clicked.connect(self._apply_selected)
        self._apply.hide()
        layout.addWidget(self._apply)

        self._populate_combo()

    # -- binding / refresh --------------------------------------------------

    def bind_sensor(self, sensor: Sensor | None, display_units: dict[str, str]) -> None:
        """Bind the live *sensor* and the shared display-unit store, then refresh."""
        self._sensor = sensor
        self._display_units = display_units
        self.refresh()

    def refresh(self) -> None:
        """Re-read the configured family, the scene's recommendation, and the caveat.

        Purely a read: nothing here writes a parameter, so binding a sensor can never
        change the atmosphere the operator asked for.
        """
        self._recommended = self._read_recommendation()
        self._populate_combo()

        if self._sensor is None:
            self._combo.setCurrentIndex(self._combo.count() - 1)
            self._combo.setEnabled(False)
            self._pending = False
            self._configured = None
            self._coverage.setText(_NO_SENSOR)
            self._warning.hide()
            self._apply.hide()
            return

        self._combo.setEnabled(True)
        self._configured = self._configured_family()
        if self._recommended is not None and not self._configured_serves_scene():
            # What is configured cannot serve this scene — the CU-239 reproduction
            # (default ``path_zenith_rad`` axes under a 20 km target). Pre-select the
            # family the scene calls for as a *proposal*: shown, named, and costed, but
            # not written, because adopting it can change the atmosphere profile. Rule
            # 17 — the mismatch is stated, never silently patched over.
            #
            # Since CU-322 the recommendation is pre-validated end to end, so what is
            # pre-selected is a family the chain will actually serve — including an
            # ``explicit_dir_only`` row, which no axes string can reach and which the
            # old axes-string recommendation could therefore never name.
            self._pending = True
            self._select(self._recommended)
        elif self._configured is not None:
            self._pending = False
            self._select(self._configured)
        else:
            self._pending = False
            self._combo.setCurrentIndex(self._combo.count() - 1)
        self._refresh_detail()

    # -- accessors (tests + host) -------------------------------------------

    @property
    def families(self) -> tuple[ShippedFamily, ...]:
        """The catalogue rows this picker enumerates, in catalogue order."""
        return self._families

    @property
    def combo(self) -> QComboBox:
        """The family selector (the escape hatch is its last entry)."""
        return self._combo

    @property
    def apply_button(self) -> QPushButton:
        """The *Use this family* button — shown only while a proposal is unapplied."""
        return self._apply

    @property
    def recommended_family(self) -> ShippedFamily | None:
        """The family the resolved scene calls for, or ``None``."""
        return self._recommended

    @property
    def is_proposal_pending(self) -> bool:
        """True while the selected family is a recommendation not yet written."""
        return self._pending

    @property
    def configured_family(self) -> ShippedFamily | None:
        """The family the live parameters select, or ``None`` for free-text axes."""
        return self._configured

    def selected_family(self) -> ShippedFamily | None:
        """The highlighted catalogue row, or ``None`` for the custom-axes entry."""
        index = self._combo.currentIndex()
        if 0 <= index < len(self._families):
            return self._families[index]
        return None

    def coverage_text(self) -> str:
        """The coverage / status line currently shown (units explicit)."""
        return self._coverage.text()

    def warning_text(self) -> str:
        """The profile-mismatch caveat currently shown ("" when there is none)."""
        return self._warning.text() if self._warning.isVisibleTo(self) else ""

    def select_family_by_name(self, name: str) -> None:
        """Choose the catalogue row called *name* as a user action would (tests).

        Drives the identical slot the combo's ``activated`` signal drives, so a test
        cannot accidentally exercise a path the operator never takes.
        """
        for index, family in enumerate(self._families):
            if family.name == name:
                self._combo.setCurrentIndex(index)
                self._on_activated(index)
                return
        raise KeyError(name)

    # -- internals ----------------------------------------------------------

    def _populate_combo(self) -> None:
        """Rebuild the entries: every catalogue row, then the custom-axes escape hatch."""
        blocked = self._combo.blockSignals(True)
        current = self._combo.currentIndex()
        self._combo.clear()
        for family in self._families:
            label = f"{family.name} — profile '{family.profile}', {family.los_direction}-looking"
            if self._recommended is not None and family.name == self._recommended.name:
                label += RECOMMENDED_SUFFIX
            self._combo.addItem(label)
        self._combo.addItem(CUSTOM_LABEL)
        if 0 <= current < self._combo.count():
            self._combo.setCurrentIndex(current)
        self._combo.blockSignals(blocked)

    def _select(self, family: ShippedFamily) -> None:
        """Highlight *family* without emitting anything (a read, not an edit)."""
        for index, row in enumerate(self._families):
            if row.name == family.name:
                self._combo.setCurrentIndex(index)
                return

    def _read_recommendation(self) -> ShippedFamily | None:
        """The scene's recommended family through the one API seam (never re-derived)."""
        if self._sensor is None:
            return None
        try:
            return self._sensor.suggested_atmosphere_family()
        except RadiantError:
            # A mid-edit config that cannot resolve has no scene to recommend for; the
            # resolution error itself surfaces through the Messages rail, not here.
            return None

    def _configured_family(self) -> ShippedFamily | None:
        """The catalogue row the live parameters actually select, if any.

        Two families can share an axes string (the boost ladder and the 0–29 km
        ladders), so the explicit directory is part of the match: an
        ``explicit_dir_only`` row matches only when the directory names it, and every
        other row matches an empty directory or its own.
        """
        sensor = self._sensor
        if sensor is None:
            return None
        try:
            axes = str(sensor.get_input(AXES_PARAM) or "")
            data_dir = str(sensor.get_input(DATA_DIR_PARAM) or "")
        except (KeyError, RadiantError):
            return None
        normalized = ",".join(part.strip() for part in axes.split(","))
        for family in self._families:
            if family.interpolation_axes != normalized:
                continue
            if family.explicit_dir_only:
                if data_dir == family.bundled_dir:
                    return family
            elif data_dir in ("", family.bundled_dir):
                return family
        return None

    def _scene_is_covered(self) -> bool:
        """Whether the configured axes can serve this scene — the one config-time seam.

        Only ever called once :meth:`_read_recommendation` has already resolved the
        sensor, so a raise here is a coverage refusal rather than an incomplete config.
        """
        sensor = self._sensor
        if sensor is None:
            return True
        try:
            sensor.validate_atmosphere_coverage()
        except RadiantError:
            return False
        return True

    def _configured_serves_scene(self) -> bool:
        """Whether what is configured *today* would actually evaluate for this scene.

        Two questions, both needed (CU-322). ``validate_atmosphere_coverage`` decides
        whether the axes string reaches a family at all; ``atmosphere_family_gap``
        decides whether the family it reaches can serve this particular query. The
        second was the missing half: an up-looking scene at ζ = 29.9° with
        ``interpolation_axes = 'target_altitude_m'`` passes the first check — the axes
        do name a shipped family — and is then refused at evaluate, because that family
        is the *vertical-only* ladder. Either failure pre-selects the recommendation
        as a proposal.
        """
        if not self._scene_is_covered():
            return False
        sensor = self._sensor
        configured = self._configured
        if sensor is None or configured is None:
            return True
        try:
            return sensor.atmosphere_family_gap(configured) is None
        except RadiantError:
            return True

    def _refresh_detail(self) -> None:
        """Re-render the coverage line, the profile caveat, and the apply affordance."""
        family = self.selected_family()
        if family is None:
            self._coverage.setText(_CUSTOM_NOTE)
            self._warning.hide()
            self._apply.hide()
            return

        prefix = "Proposed — " if self._pending else "Covers "
        text = f"{prefix}{family.coverage}. Axes: '{family.interpolation_axes}'."
        if family.explicit_dir_only:
            text += " Selected by directory (no axes key reaches this family)."
        if self._pending:
            current = (
                f"'{self._configured.name}'"
                if self._configured is not None
                else "the configured axes"
            )
            text += (
                f" Not applied yet — {current} does not cover this scene; "
                "click “Use this family” to write it."
            )
        gap = self._family_gap(family)
        if gap:
            # The highlighted row cannot serve this scene: say so here rather than
            # letting the operator discover it at Evaluate (CU-322). Units are the
            # API's — km / degrees — never re-derived here.
            text += f" Does not serve this scene: {gap}."
        self._coverage.setText(text)

        caveat = self._profile_caveat(family)
        if caveat:
            self._warning.setText(caveat)
            self._warning.show()
        else:
            self._warning.setText("")
            self._warning.hide()

        self._apply.setVisible(self._pending)

    def _family_gap(self, family: ShippedFamily) -> str | None:
        """The API's one-sentence reason *family* cannot serve this scene, or ``None``."""
        sensor = self._sensor
        if sensor is None:
            return None
        try:
            return sensor.atmosphere_family_gap(family)
        except RadiantError:
            return None

    def _profile_caveat(self, family: ShippedFamily) -> str | None:
        """The API's profile-change sentence for *family*, or ``None``."""
        sensor = self._sensor
        if sensor is None:
            return None
        try:
            return sensor.atmosphere_profile_change_warning(family)
        except RadiantError:
            return None

    def _on_activated(self, index: int) -> None:
        """A user picked an entry: write a catalogue row, or open the free-text editor."""
        if index >= len(self._families):
            self._pending = False
            self._refresh_detail()
            self._open_axes_editor()
            return
        self._pending = False
        self._write(self._families[index])

    def _apply_selected(self) -> None:
        """Apply the pre-selected recommendation (the explicit proposal step)."""
        family = self.selected_family()
        if family is None:
            return
        self._pending = False
        self._write(family)

    def _write(self, family: ShippedFamily) -> None:
        """Write the family's derived parameter values, then announce one compound edit.

        The directory is written only for a family no axes key can reach, and cleared
        otherwise so a stale explicit directory cannot quietly outlive the choice that
        set it.
        """
        sensor = self._sensor
        if sensor is None:
            return
        written: list[str] = []
        try:
            current_axes = str(sensor.get_input(AXES_PARAM) or "")
        except (KeyError, RadiantError):
            current_axes = ""
        if current_axes != family.interpolation_axes:
            sensor.set(AXES_PARAM, family.interpolation_axes)
            written.append(AXES_PARAM)

        target_dir = family.bundled_dir if family.explicit_dir_only else ""
        try:
            current_dir = str(sensor.get_input(DATA_DIR_PARAM) or "")
        except (KeyError, RadiantError):
            current_dir = ""
        if current_dir != target_dir:
            sensor.set(DATA_DIR_PARAM, target_dir)
            written.append(DATA_DIR_PARAM)

        self.refresh()
        if written:
            self.parametersEdited.emit(written)

    def _open_axes_editor(self) -> None:
        """The escape hatch: the shared editor on the free-text axes parameter."""
        sensor = self._sensor
        if sensor is None:
            return
        dialog = ParameterEditorDialog(
            sensor,
            AXES_PARAM,
            self._after_axes_commit,
            self,
            display_unit=self._display_units.get(AXES_PARAM),
        )
        exec_dialog(dialog)

    def _after_axes_commit(self, dotpath: str, unit: str | None) -> None:
        """A hand-typed axes string committed: record the unit, re-read, announce."""
        if unit is not None:
            self._display_units[dotpath] = unit
        self.refresh()
        self.parametersEdited.emit([dotpath])


__all__ = ["AXES_PARAM", "CUSTOM_LABEL", "DATA_DIR_PARAM", "AtmosphereFamilyPicker"]
