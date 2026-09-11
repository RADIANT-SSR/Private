"""The Optics stage's **Transmission** tab — one home for how τ_opt is defined.

:class:`TransmissionPanel` is the consolidation the owner ratified on 2026-09-09/10: the
Optics stage's old *Elements* and *Throughput* tabs were two halves of one question —
**how is optical transmission defined?** — split across the tab strip, so an analyst
editing the scalar τ_opt on *Inputs* could not see that an attached element train was
overriding it. The tab strip is now **Inputs · Transmission · MTF · PSF + Pupil**, and this
panel is the Transmission tab's content:

1. a :class:`~radiant.gui.widgets.transmission_mode_selector.TransmissionModeSelector`
   segmented control — *Scalar throughput* | *Element train*;
2. a **mode banner** stating which definition is in force and what that makes irrelevant;
3. the active mode's editor — the ``optics.transmission_scalar`` field (moved off the
   *Inputs* form, so transmission is defined in exactly one place) or the
   :class:`~radiant.gui.widgets.optical_element_editor.OpticalElementEditor` train table
   with its Gap-116 coating-detail drill-down.

The τ(λ) figures and the cold-stop / effective-pupil strip are sections of the same tab,
declared in :mod:`radiant.gui.stage_views` and assembled by
:class:`~radiant.gui.widgets.stage_center.StagePane` — the panel only tells the host which
mode is active so the per-element overlay is shown in element mode and hidden in scalar
mode (there are no elements to draw).

**Mode semantics (owner-ratified).** The mode is not a parameter — it is the *shape of the
document*, so it is read from the document and never invented:

* **Loading** picks the mode from the config: an ``optical_elements`` list opens in
  *Element train*, anything else in *Scalar throughput*.
* **Switching is non-destructive in-session**: leaving element mode detaches the document
  (one API call) but the rows stay in the table, inactive, so the operator can A/B the two
  definitions without retyping a train. Switching back re-commits them.
* **Saving writes only the active mode.** In scalar mode the sensor carries no element
  document, so the written YAML carries no ``optical_elements`` section — a file with an
  element list means element mode, period, and no hidden inactive state ever reaches a
  config. While rows are held, the banner says so in the warn register, and the window adds
  a non-modal note to the save confirmation (:meth:`held_element_rows`).

**One action ↔ one API call.** Detaching is one ``set_optical_elements(None)`` through the
element editor's own write path (which knows the study document); re-attaching is the same
commit-on-edit path every cell edit uses; the scalar field is one ``sensor.set`` through the
shared :class:`~radiant.gui.widgets.parameter_editor_dialog.ParameterEditorDialog`. No
physics and no unit maths happen here.

All colour/typography comes from the QSS theme via object names (GUI plan §4.9); this file
holds no colour or font literal. One widget class per file (Rule 19).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from radiant.gui.dialog_lifetime import exec_dialog
from radiant.gui.param_format import field_display_text
from radiant.gui.widgets.field_row import UNSET as _UNSET
from radiant.gui.widgets.field_row import FieldRow
from radiant.gui.widgets.optical_element_editor import OpticalElementEditor
from radiant.gui.widgets.parameter_editor_dialog import ParameterEditorDialog
from radiant.gui.widgets.transmission_mode_selector import (
    MODE_ELEMENT,
    MODE_SCALAR,
    TransmissionModeSelector,
)

if TYPE_CHECKING:
    from radiant.api.sensor import Sensor
    from radiant.gui.config_scope import ConfigurationScope

#: The scalar transmission parameter — defined on this tab and nowhere else.
SCALAR_DOTPATH: Final[str] = "optics.transmission_scalar"

_SCALAR_LABEL: Final[str] = "Scalar throughput τ_opt"
_SCALAR_TITLE: Final[str] = "Scalar transmission — one flat τ_opt across the band"

_BANNER_SCALAR: Final[str] = (
    "Scalar throughput defines transmission — τ_opt is flat across the band and no "
    "element train is attached."
)
_BANNER_ELEMENT: Final[str] = (
    "Element train defines transmission ({n} elements) — scalar τ ignored."
)
_BANNER_HELD: Final[str] = (
    "Scalar throughput is active — the {n} element row(s) below are inactive and held in "
    "this session only. Saving writes no optical_elements section; switch back to Element "
    "train to keep them."
)


class TransmissionPanel(QWidget):
    """The Transmission tab: mode selector + the active definition's editor.

    Signals
    -------
    parameterEdited(str):
        Emitted with the dot-path (or the element document's pseudo-path) after any
        committed edit — the scalar field, an element-table edit, or a mode switch — so
        the host marks the run stale and schedules a re-evaluation.
    modeChanged(str):
        Emitted with the active mode (``"scalar"`` / ``"element"``) whenever it changes,
        including when a freshly bound document selects it. The host uses it to show the
        per-element τ overlay only where there are elements.
    """

    parameterEdited = Signal(str)
    modeChanged = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("transmissionPanel")

        self._sensor: Sensor | None = None
        self._display_units: dict[str, str] = {}
        self._mode = MODE_SCALAR

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self._selector = TransmissionModeSelector(self)
        self._selector.modeSelected.connect(self._on_mode_selected)
        layout.addWidget(self._selector)

        self._banner = QLabel(_BANNER_SCALAR, self)
        self._banner.setObjectName("transmissionModeBanner")
        self._banner.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._banner.setProperty("state", "normal")
        self._banner.setWordWrap(True)
        layout.addWidget(self._banner)

        # The scalar card: one FieldRow, in the same card chrome as every other
        # schema-driven inputs group (owner hard rule — fields render identically).
        self._scalar_card = QWidget(self)
        self._scalar_card.setObjectName("geoModeFamily")
        self._scalar_card.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._scalar_card.setProperty("state", "normal")
        scalar_box = QVBoxLayout(self._scalar_card)
        scalar_box.setContentsMargins(12, 10, 12, 10)
        scalar_box.setSpacing(6)
        scalar_title = QLabel(_SCALAR_TITLE, self._scalar_card)
        scalar_title.setObjectName("geoModeFamilyTitle")
        scalar_title.setWordWrap(True)
        scalar_box.addWidget(scalar_title)
        self._scalar_row = FieldRow(SCALAR_DOTPATH, _SCALAR_LABEL, self._open_scalar_editor)
        scalar_box.addWidget(self._scalar_row)
        layout.addWidget(self._scalar_card)

        self._editor = OpticalElementEditor(self)
        self._editor.elementsApplied.connect(self.parameterEdited)
        layout.addWidget(self._editor)

        self._sync_mode_widgets()

    # -- accessors ------------------------------------------------------------

    @property
    def mode(self) -> str:
        """The active transmission mode (``"scalar"`` / ``"element"``)."""
        return self._mode

    @property
    def selector(self) -> TransmissionModeSelector:
        """The segmented mode control (tests)."""
        return self._selector

    @property
    def element_editor(self) -> OpticalElementEditor:
        """The embedded element-train editor (the Elements tab's widget, unchanged)."""
        return self._editor

    @property
    def banner(self) -> QLabel:
        """The mode banner label (tests)."""
        return self._banner

    def scalar_row(self) -> FieldRow:
        """The ``optics.transmission_scalar`` field row — this tab's only home for it."""
        return self._scalar_row

    def scalar_value_text(self) -> str:
        """The displayed value+unit text of the scalar τ_opt field."""
        return self._scalar_row.value_text()

    def held_element_rows(self) -> int:
        """How many element rows are held inactive while scalar mode is active.

        ``0`` in element mode and in any scalar session that never authored a train. The
        window reads it after a save to add the non-modal "these were not written" note.
        """
        if self._mode != MODE_SCALAR:
            return 0
        return int(self._editor.table.rowCount())

    # -- binding --------------------------------------------------------------

    def bind_sensor(self, sensor: Sensor | None, display_units: dict[str, str]) -> None:
        """Bind the live *sensor*; adopt the **document's own** transmission mode.

        Loading never invents state: the mode is whatever the configuration says. The
        element editor is activated first so it re-reads the document as it always has,
        then deactivated when the document turns out to be scalar — which leaves an empty,
        inactive table rather than a stale one.
        """
        self._sensor = sensor
        self._display_units = display_units
        self._editor.set_active(True)
        self._editor.bind_sensor(sensor, display_units)
        mode = MODE_ELEMENT if self._document_rows(sensor) else MODE_SCALAR
        if mode == MODE_SCALAR:
            self._editor.set_active(False)
        self._set_mode(mode)
        self.refresh()

    def set_configuration_scope(self, scope: ConfigurationScope | None) -> None:
        """Hand the session's configuration scope to the element editor (Gap 103 v1.1)."""
        self._editor.set_configuration_scope(scope)

    def set_dark(self, dark: bool) -> None:
        """Adopt the dark/light plot theme (the editor's coating-detail figure)."""
        self._editor.set_dark(dark)

    def refresh(self) -> None:
        """Re-read the scalar field and re-state the banner (post-evaluation beat)."""
        self._scalar_row.set_value_text(self._scalar_text())
        self._sync_banner()

    # -- mode ------------------------------------------------------------------

    def _document_rows(self, sensor: Sensor | None) -> int:
        """How many elements the bound document carries (``0`` when it carries none)."""
        if sensor is None:
            return 0
        document = sensor.optical_elements()
        return 0 if not document else len(document)

    def _on_mode_selected(self, mode: str) -> None:
        """An operator mode switch: detach or re-attach the document, then re-state."""
        if mode == self._mode:
            return
        if mode == MODE_SCALAR:
            # Detach through the editor's own write path (it knows the study document),
            # keeping the rows in the table so the operator can switch back.
            self._editor.detach_document()
            self._editor.set_active(False)
        else:
            self._editor.set_active(True)
            self._editor.reattach_document()
        self._set_mode(mode)

    def _set_mode(self, mode: str) -> None:
        """Adopt *mode*: sync the selector, the visible editors, and the banner."""
        changed = mode != self._mode
        self._mode = mode
        self._selector.set_mode(mode)
        self._sync_mode_widgets()
        if changed:
            self.modeChanged.emit(mode)

    def _sync_mode_widgets(self) -> None:
        """Show the active mode's editor; keep held element rows visible but inactive."""
        scalar = self._mode == MODE_SCALAR
        self._scalar_card.setVisible(scalar)
        # In element mode the table is the tab's subject. In scalar mode it stays on
        # screen only while it holds rows — an empty disabled table would be noise.
        self._editor.setVisible(not scalar or self._editor.table.rowCount() > 0)
        self._sync_banner()

    def _sync_banner(self) -> None:
        """State which definition is in force — and, when rows are held, that they are not saved."""
        rows = int(self._editor.table.rowCount())
        if self._mode == MODE_ELEMENT:
            text, state = _BANNER_ELEMENT.format(n=rows), "normal"
        elif rows:
            text, state = _BANNER_HELD.format(n=rows), "held"
        else:
            text, state = _BANNER_SCALAR, "normal"
        self._banner.setText(text)
        if self._banner.property("state") != state:
            self._banner.setProperty("state", state)
            style = self._banner.style()
            style.unpolish(self._banner)
            style.polish(self._banner)

    # -- the scalar field ------------------------------------------------------

    def _scalar_text(self) -> str:
        sensor = self._sensor
        if sensor is None:
            return _UNSET
        return field_display_text(sensor, SCALAR_DOTPATH, self._display_units)

    def _open_scalar_editor(self, dotpath: str) -> None:
        """Open the shared Parameter Editor on τ_opt (one ``sensor.set`` on commit)."""
        if self._sensor is None:
            return
        dialog = ParameterEditorDialog(
            self._sensor,
            dotpath,
            self._after_scalar_commit,
            self,
            display_unit=self._display_units.get(dotpath),
        )
        exec_dialog(dialog)

    def _after_scalar_commit(self, dotpath: str, unit: str | None) -> None:
        """Record the chosen display unit, re-read the field, and signal the edit upstream."""
        if unit is not None:
            self._display_units[dotpath] = unit
        self.refresh()
        self.parameterEdited.emit(dotpath)


__all__ = ["TransmissionPanel", "SCALAR_DOTPATH"]
