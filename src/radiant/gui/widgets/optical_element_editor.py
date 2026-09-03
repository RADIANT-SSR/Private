"""The Optics stage's **Elements** tab — the mixed-train element-list editor (ADR-0009 D2).

:class:`OpticalElementEditor` is the structured config-document editor of the GUI
Capability Expansion plan Phase GS-4 (audit O-1: per-element %R/%T/temperature mapping —
the audit's flagship optics gap). It edits the **declarative element document** — the same
entry dicts the ``optical_elements:`` YAML section carries — never physics objects: rows
are (name, transfer mode, kind, R-or-T value, temperature, geometry), *Apply* serializes
the table to entries and commits through the API (validate-and-attach through the io
parser — the single validation authority, Kirchhoff checks included — then persisted by
``Sensor.save``, ADR-0009 D4). The optics stage runs full-prescription on the next
evaluation and the Throughput tab's coating-spectra figure reflects the authored train.

**Emissivity is derived, never an input (Rule 5).** The ε column is **read-only**, filled
from :func:`radiant.api.preview_optical_elements` (band-mean Kirchhoff ε: 1 − R for
mirrors, cavity/zero for refractive). There is no ε input anywhere in this editor.

**R/T value cells** accept a scalar (``0.97``) or a spectral-CSV path (``coatings/au.csv``)
— exactly the document schema; the io parser resolves and validates either form. A
rejected document (missing field, Kirchhoff violation, bad file) surfaces the parser's
actionable error in the shared
:class:`~radiant.gui.widgets.actionable_error_dialog.ActionableErrorDialog`; the live
sensor is never touched by an invalid Apply (fail-fast in ``set_optical_elements``).

Applying emits :attr:`elementsApplied`, which the host relays through the standard
``parameterEdited`` pipeline (stale dots + debounced re-evaluation). The pseudo dot-path
``optics_config.element_list`` identifies the edit; it is not a scalar parameter, so no
undo command is recorded (documented Phase-9 limitation for non-scalar edits).

**Configured element rows (Gap 103 v1.1, owner-ratified 2026-09-02 in live review).** In a
multi-member study a **row configures exactly like a parameter**. The tab always renders
the displayed configuration's effective train
(``ConfigurationSet.effective_optical_elements(active)``), and:

* **Right-click a row** for the two actions the parameter surfaces offer — *Configure
  across configurations…* (:meth:`ConfigurationSet.configure_element`, which seeds every
  configuration with the row's current shared entry, so nothing changes until one is
  edited) and *Un-configure row (keep <first>'s entry)…*
  (:meth:`ConfigurationSet.unconfigure_element`, D-6 keep-first, behind the same
  value-stating confirmation the parameter collapse uses).
* A configured row carries the **red "C"** after its name — the one configured-badge
  glyph, painted by
  :class:`~radiant.gui.widgets.configured_name_delegate.EditableConfiguredNameDelegate`
  so the Name cell stays editable (the name is part of the entry and configures with the
  row — row identity is **positional**).
* **D-8 inline edit:** editing any cell of a configured row and applying writes that
  configuration's entry only (:meth:`ConfigurationSet.set_element_for`); every other
  configuration's entry is untouched. Editing a shared row writes the shared document,
  which every configuration inherits.
* The train's **structure is shared**: the row count and order are the same in every
  configuration, so Add / Remove / reorder change every member. A configured row keeps
  its position, so an edit that would shift one is refused *before* it is made — the
  button is disabled with the reason and the way out (un-configure the row first).

A single-configuration session shows no row menu, no badges, and no study note, and
behaves exactly as it did before this feature.

All colour/typography comes from the QSS theme via object names; one widget class per
file (Rule 19).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Final

from PySide6.QtCore import QPoint, QSignalBlocker, Qt, Signal
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QMenu,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from radiant.api.coating_detail import plot_coating_detail
from radiant.api.config_io import normalize_element_document, preview_optical_elements
from radiant.api.plot import plot_theme
from radiant.core.exceptions import RadiantError
from radiant.gui.dialog_lifetime import exec_dialog
from radiant.gui.widgets.actionable_error_dialog import ActionableErrorDialog
from radiant.gui.widgets.configure_menu import CONFIGURE_TEXT, unconfigure_element_text
from radiant.gui.widgets.configured_name_delegate import (
    CONFIGURED_ROLE,
    EditableConfiguredNameDelegate,
)
from radiant.gui.widgets.matplotlib_canvas import MatplotlibCanvas
from radiant.gui.widgets.spectral_table_dialog import SpectralTableDialog

if TYPE_CHECKING:
    from radiant.api.config_set import ConfigurationSet
    from radiant.api.sensor import Sensor
    from radiant.gui.config_scope import ConfigurationScope

# The pseudo dot-path the host's parameterEdited pipeline sees for an element-document
# commit (not a scalar parameter; undo skips it, dirty/stale/re-evaluate all apply).
ELEMENT_EDIT_PATH: Final[str] = "optics_config.element_list"

# Item-data role carrying a row's inline spectral table (the value cell shows a
# "spectral (N pts)" sentinel; the dict itself rides in this role).
_SPECTRUM_ROLE: Final[int] = int(Qt.ItemDataRole.UserRole) + 1
_SPECTRUM_SENTINEL: Final[str] = "spectral ("

# Item-data role carrying the **document position** a table row was rendered from —
# the row's identity, since row identity is positional (Gap 103 v1.1). A row the
# operator has just added carries :data:`_NEW_ROW` until an Apply puts it in the
# document. Kept on the Name cell, beside CONFIGURED_ROLE.
_ORIGIN_ROLE: Final[int] = int(Qt.ItemDataRole.UserRole) + 3
_NEW_ROW: Final[int] = -1

_TITLE = "Optical element train — per-element R/T, temperature, geometry (ε derived)"
_HINT = (
    "R/T cells take a scalar (0.97), a spectral-CSV path, or an inline λ-table "
    "(Spectrum… button). ε is Kirchhoff-derived "
    "(read-only). Kind is a descriptive label for refractive elements (legend/reporting; "
    "the physics comes from R/T and temperature) — a REFLECTIVE row is always a mirror. "
    "Apply commits the train (one API call); Save persists it in the config."
)

_SPECTRUM_TOOLTIP = "Define the selected row's R/T as an inline λ-table (type or paste)"

_TRANSFER_CHOICES: Final[tuple[str, ...]] = ("REFLECTIVE", "REFRACTIVE")
# Refractive kinds (a REFLECTIVE row is always a mirror; the factory sets it).
_KIND_CHOICES: Final[tuple[str, ...]] = (
    "lens",
    "window",
    "filter",
    "beamsplitter",
    "dewar_window",
)

# -- configured element rows (Gap 103 v1.1) ---------------------------------------
# Shown only in a multi-member study, where "which configuration does this row belong
# to" is a real question. A single-configuration session never sees any of it.
_STUDY_NOTE = (
    "Showing {name}'s train. Right-click a row to configure it across configurations: a "
    "configured row (red C) carries one complete entry per configuration, and editing it "
    "here edits {name}'s entry only. Row count and order are shared by every "
    "configuration."
)
_CONFIGURED_TOOLTIP = "configured — one entry per configuration; editing edits {name} only"
_CONFIGURE_ROW_TOOLTIP = (
    "Give this row one complete entry per configuration, seeded from its current shared "
    "entry — nothing changes until you edit one. The entry's name configures with the row."
)
_NEW_ROW_HINT = (
    "Apply the train first: a row can be configured only once it is part of the element document."
)
_UNCONFIGURE_TITLE = "Un-configure element row"
_UNCONFIGURE_BODY = (
    "Un-configure element row {row}?\n\n"
    "Every configuration will share {kept}'s entry, {entry}. The other configurations' "
    "entries ({summary}) are discarded."
)
_REMOVE_CONFIGURED_TITLE = "Remove a configured element row"
_REMOVE_CONFIGURED_BODY = (
    "Remove element row {row}?\n\n"
    "The row is configured — every configuration carries its own entry ({summary}). "
    "Applying the train removes the row, and all of those entries, from every "
    "configuration."
)
_REMOVE_BLOCKED_TOOLTIP = (
    "Element row {row} below is configured, and a configured row keeps its position in "
    "the train. Un-configure it (right-click it) before removing a row above it."
)
_MOVE_BLOCKED_TOOLTIP = (
    "Element row {row} is configured, and a configured row keeps its position in the "
    "train. Un-configure it (right-click it) before reordering across it."
)
# Separator between per-configuration items in a confirmation's entry list, matching
# the configured-parameter badge tooltips (ConfigurationScope.summary).
_SUMMARY_SEPARATOR = " · "

_EPS_TOOLTIP = "ε is Kirchhoff-derived (1 − R − T) — read-only (Rule 5)."

_DETAIL_TITLE = "Coating detail — R / T / ε on the coating's own grid (Gap 116)"
_DETAIL_PROMPT = (
    "Select an element row to see its coating model — each quantity on an "
    "autoscaled panel, over the curve's full stored wavelength extent."
)
# Tall enough for two stacked autoscaled panels; the figure follows the widget.
_DETAIL_MIN_HEIGHT = 260

_COL_NAME = 0
_COL_TRANSFER = 1
_COL_KIND = 2
_COL_VALUE = 3
_COL_TEMP = 4
_COL_DIAM = 5
_COL_DIST = 6
_COL_EPS = 7
_HEADERS: Final[tuple[str, ...]] = (
    "Name",
    "Transfer",
    "Kind",
    "R or T (scalar | CSV)",
    "T (K)",
    "Diam (m)",
    "→FPA (m)",
    "ε (derived)",
)

# Sensible new-row defaults (ambient mirror / cold filter): plain literals for the
# editor's starting text only — every physical check happens in the io parser on Apply.
_NEW_MIRROR: Final[dict[str, Any]] = {
    "name": "mirror",
    "transfer_mode": "REFLECTIVE",
    "reflectance": 0.97,
    "temperature_K": 293.0,
    "diameter_m": 0.3,
    "distance_to_fpa_m": 1.0,
}
_NEW_REFRACTIVE: Final[dict[str, Any]] = {
    "name": "element",
    "transfer_mode": "REFRACTIVE",
    "kind": "filter",
    "transmittance": 0.9,
    "temperature_K": 240.0,
    "diameter_m": 0.05,
    "distance_to_fpa_m": 0.05,
}


class OpticalElementEditor(QWidget):
    """The element-train table editor: rows ⇌ the declarative element document.

    Signals
    -------
    elementsApplied(str):
        Emitted with :data:`ELEMENT_EDIT_PATH` after a successful Apply, and after a
        row is configured or un-configured — every one of those writes the element
        document, so the host marks state stale and schedules a re-evaluation, the
        same contract as ``parameterEdited``.
    """

    elementsApplied = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("opticalElementEditor")

        self._sensor: Sensor | None = None
        # The session's configuration scope (Gap 103 v1.1): the read side of the study
        # document. Held rather than the set itself, because the scope object is stable
        # across document adoptions while the set it carries is not.
        self._scope: ConfigurationScope | None = None
        # The set the table was last rendered from — the identity that decides whether a
        # scope ``changed`` means "new document" (re-read) or "same document, some
        # parameter got configured" (leave the table alone).
        self._rendered_set: ConfigurationSet | None = None

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

        hint = QLabel(_HINT, card)
        hint.setObjectName("stageCenterNote")
        hint.setWordWrap(True)
        box.addWidget(hint)

        # The study note (Gap 103 v1.1): shown only for a multi-member study, where a row
        # can be configured. A single-configuration session never sees it.
        self._study_note = QLabel("", card)
        self._study_note.setObjectName("stageCenterNote")
        self._study_note.setWordWrap(True)
        self._study_note.setVisible(False)
        box.addWidget(self._study_note)

        self._table = QTableWidget(0, len(_HEADERS), card)
        self._table.setObjectName("elementTable")
        self._table.setHorizontalHeaderLabels(list(_HEADERS))
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.verticalHeader().setVisible(False)
        # The red "C" rides after the name text, painted by the delegate, so the Name
        # cell keeps its inline editor (the name configures with the row).
        self._name_delegate = EditableConfiguredNameDelegate(self._table)
        self._table.setItemDelegateForColumn(_COL_NAME, self._name_delegate)
        self._table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        box.addWidget(self._table)

        buttons = QWidget(card)
        button_row = QHBoxLayout(buttons)
        button_row.setContentsMargins(0, 0, 0, 0)
        button_row.setSpacing(6)
        self._add_mirror = QPushButton("Add mirror", buttons)
        self._add_refractive = QPushButton("Add refractive", buttons)
        self._remove = QPushButton("Remove", buttons)
        self._up = QPushButton("↑", buttons)
        self._down = QPushButton("↓", buttons)
        self._spectrum = QPushButton("Spectrum…", buttons)
        self._spectrum.setToolTip(_SPECTRUM_TOOLTIP)
        self._apply = QPushButton("Apply train", buttons)
        self._apply.setObjectName("elementApplyButton")
        for b in (
            self._add_mirror,
            self._add_refractive,
            self._remove,
            self._up,
            self._down,
            self._spectrum,
        ):
            button_row.addWidget(b)
        button_row.addStretch(1)
        button_row.addWidget(self._apply)
        box.addWidget(buttons)

        self._add_mirror.clicked.connect(lambda: self._add_row(dict(_NEW_MIRROR)))
        self._add_refractive.clicked.connect(lambda: self._add_row(dict(_NEW_REFRACTIVE)))
        self._remove.clicked.connect(self._remove_current)
        self._up.clicked.connect(lambda: self._move_current(-1))
        self._down.clicked.connect(lambda: self._move_current(+1))
        self._spectrum.clicked.connect(self._edit_spectrum)
        self._apply.clicked.connect(self.apply_train)

        # Coating detail (Gap 116): selecting a row draws that element's R/T/ε on its
        # native source grid, one autoscaled panel per quantity — the inspection view
        # the fixed-[0,1] all-element overlay cannot provide. Reads the TABLE's current
        # entries (drafts included, via the `entries=` override), so a row previews
        # before Apply; an unparsable draft shows the io parser's actionable message.
        self._dark = False
        detail_title = QLabel(_DETAIL_TITLE, card)
        detail_title.setObjectName("stagePlotTitle")
        box.addWidget(detail_title)
        self._detail_canvas = MatplotlibCanvas(card)
        self._detail_canvas.setMinimumHeight(_DETAIL_MIN_HEIGHT)
        self._detail_canvas.setVisible(False)
        self._detail_message = QLabel(_DETAIL_PROMPT, card)
        self._detail_message.setObjectName("stagePlotMessage")
        self._detail_message.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._detail_message.setWordWrap(True)
        box.addWidget(self._detail_canvas, 1)
        box.addWidget(self._detail_message)
        self._table.itemSelectionChanged.connect(self.refresh_coating_detail)
        self._table.itemSelectionChanged.connect(self._sync_selection_actions)
        self._table.customContextMenuRequested.connect(self._on_context_menu)
        self.elementsApplied.connect(lambda _path: self.refresh_coating_detail())

        layout.addWidget(card)

    # -- binding --------------------------------------------------------------

    def bind_sensor(self, sensor: Sensor | None, display_units: dict[str, str]) -> None:
        """Bind the live *sensor*; load the displayed configuration's train into the table.

        Loading happens on bind only (never on populate), so an in-progress table edit
        is not clobbered by each re-evaluation. In a multi-member study the host re-binds
        on every configuration switch, which is what re-renders the table for the newly
        active configuration (badges included). *display_units* is accepted for
        signature parity with the other Inputs forms; the table's engineering columns
        are canonical-unit by design (K, m).
        """
        del display_units  # signature parity with the other Inputs forms
        self._sensor = sensor
        self._reload_from_document()

    def set_configuration_scope(self, scope: ConfigurationScope | None) -> None:
        """Give the tab the session's configuration scope (Gap 103 v1.1).

        The scope is the read side of the study document: it answers *is this a
        multi-member study* and *which configuration is displayed*. The tab re-reads the
        train through it, so the row actions appear (and the displayed configuration's
        train renders) as soon as a study is the open document.

        Handed over by the host's one ``bind_configuration_scope`` fan-out, exactly as
        the per-stage form fields get theirs — the scope object is stable for the life
        of the window, so a later document adoption needs no re-wiring. The tab follows
        the scope's ``changed`` signal only far enough to notice that the **document**
        changed: a configure or a configured-value edit fires it too, and re-reading the
        table on those would clobber an in-progress element edit (the same reason
        :meth:`bind_sensor` loads on bind and not on populate).
        """
        if self._scope is not None:
            self._scope.changed.disconnect(self._on_document_changed)
        self._scope = scope
        if scope is not None:
            scope.changed.connect(self._on_document_changed)
        self._reload_from_document()

    def _on_document_changed(self) -> None:
        """Re-read the train when the scope started carrying a different document."""
        scope = self._scope
        if (None if scope is None else scope.configuration_set) is self._rendered_set:
            return
        self._reload_from_document()

    def refresh(self) -> None:
        """No-op on re-evaluation (the table is an editor, not a readout)."""

    # -- the session document --------------------------------------------------

    def _bound_set(self) -> ConfigurationSet | None:
        """The session document, whatever its size (``None`` when none is bound).

        Whose element document the tab reads and an Apply writes. In a plain session the
        set's base **is** the displayed sensor, so reading and writing through it is the
        same object and the same behaviour as before; where the two differ — any set
        whose displayed sensor is a materialization — the document is the one that
        survives, and the throwaway is not it (Rule 17).
        """
        scope = self._scope
        return None if scope is None else scope.configuration_set

    def _study_set(self) -> ConfigurationSet | None:
        """The session's set when it is a **multi-member** study, else ``None``.

        The gate on everything per-configuration: the row menu, the badges, and the
        study note. A one-configuration set is deliberately excluded — it has no second
        member to differ from, so a configured row would say nothing the shared document
        does not already say.
        """
        config_set = self._bound_set()
        if config_set is None or len(config_set.names()) <= 1:
            return None
        return config_set

    def _document_entries(self) -> tuple[list[dict[str, Any]], str]:
        """The entries to render, plus any advisory the API raised reading them.

        With a set bound that is the displayed configuration's **effective** train (the
        shared skeleton with each configured row resolved to that configuration's entry)
        — which for a plain session is simply the displayed sensor's own document, since
        the set's base is that sensor. The one way the read can fail is a configured row
        left without a position — reachable only by replacing the base document behind
        the set's back (a console ``set_optical_elements``). The tab then falls back to
        the shared rows so it stays usable, and returns the API's actionable message so
        it is shown rather than swallowed (Rule 17); the same error also names the
        configuration on the next evaluation.
        """
        config_set = self._bound_set()
        if config_set is None:
            sensor = self._sensor
            document = sensor.optical_elements() if sensor is not None else None
            return list(document or []), ""
        try:
            effective = config_set.effective_optical_elements(config_set.active)
        except RadiantError as exc:
            return list(config_set.base.optical_elements() or []), str(exc)
        return list(effective or []), ""

    def _reload_from_document(self) -> None:
        """Re-render the table from the document (the one render path)."""
        self._rendered_set = self._bound_set()
        entries, advisory = self._document_entries()
        self._reload(entries)
        if entries:
            self._refresh_derived_emissivity(entries)
        self._sync_study_note()
        self._refresh_configured_marks()
        self.refresh_coating_detail()
        if advisory:
            self._show_detail_message(advisory)

    def _sync_study_note(self) -> None:
        """Show the study note (naming the displayed configuration) only in a study."""
        config_set = self._study_set()
        self._study_note.setVisible(config_set is not None)
        self._study_note.setText(
            "" if config_set is None else _STUDY_NOTE.format(name=config_set.active)
        )

    # -- configured rows -------------------------------------------------------

    def _configured_positions(self) -> frozenset[int]:
        """Document positions that carry one entry per configuration.

        Read from the bound set whatever its size — not from :meth:`_study_set` — because
        this is the document's own single store, and a commit that mistook a configured
        row for a shared one would write it into both. (A one-configuration set is never
        *offered* the configure action; a script can still have configured a row in one,
        and the tab must still commit it correctly.)
        """
        config_set = self._bound_set()
        if config_set is None:
            return frozenset()
        return frozenset(config_set.configured_element_indices())

    def _origin(self, row: int) -> int:
        """The document position *row* was rendered from (:data:`_NEW_ROW` if unapplied)."""
        item = self._table.item(row, _COL_NAME)
        if item is None:
            return _NEW_ROW
        stored = item.data(_ORIGIN_ROLE)
        return int(stored) if isinstance(stored, int) else _NEW_ROW

    def _is_configured_row(self, row: int) -> bool:
        """True when table *row* renders a configured document row."""
        return self._origin(row) in self._configured_positions()

    def _refresh_configured_marks(self) -> None:
        """Mark every configured row with the red "C" and its tooltip; sync the buttons.

        The marker is the one configured-badge glyph (``CONFIGURED_ROLE`` + the painting
        delegate), so it is the same red, weight, and placement — immediately right of
        the name — the parameter tree and the per-stage forms use. The Name cell's
        tooltip keeps the full name and gains the one line of *what configured means
        here*, so a truncated column is still readable.
        """
        config_set = self._bound_set()
        active = "" if config_set is None else config_set.active
        configured = self._configured_positions()
        for row in range(self._table.rowCount()):
            item = self._table.item(row, _COL_NAME)
            if item is None:
                continue
            marked = self._origin(row) in configured
            item.setData(CONFIGURED_ROLE, True if marked else None)
            item.setToolTip(
                f"{item.text()}\n\n{_CONFIGURED_TOOLTIP.format(name=active)}"
                if marked
                else item.text()
            )
        self._table.viewport().update()
        self._sync_selection_actions()

    def _sync_selection_actions(self) -> None:
        """Enable the structure buttons only where the edit is expressible.

        Row identity is positional and a configured row keeps its position, so an edit
        that would **shift** a configured row cannot be written: removing a row above one
        would move it, and reordering across one would swap it out of its own slot. Those
        are refused here — before the operator invests any typing — with the reason and
        the way out (un-configure that row first), rather than accepted and rejected at
        Apply. Everything else is enabled: Add appends at the end of the train, which
        shifts nothing, and Remove of a configured row is allowed behind a confirmation.
        """
        row = self._table.currentRow()
        count = self._table.rowCount()
        if not (0 <= row < count):
            self._remove.setEnabled(False)
            self._up.setEnabled(False)
            self._down.setEnabled(False)
            self._spectrum.setEnabled(False)
            return
        self._spectrum.setEnabled(True)
        below = [r for r in range(row + 1, count) if self._is_configured_row(r)]
        self._set_structure_action(
            self._remove, blocked_by=below[0] if below else None, tooltip=_REMOVE_BLOCKED_TOOLTIP
        )
        self._set_structure_action(
            self._up, blocked_by=self._move_blocker(row, -1), tooltip=_MOVE_BLOCKED_TOOLTIP
        )
        self._set_structure_action(
            self._down, blocked_by=self._move_blocker(row, +1), tooltip=_MOVE_BLOCKED_TOOLTIP
        )

    def _move_blocker(self, row: int, delta: int) -> int | None:
        """The configured row a move of *row* by *delta* would shift, if any."""
        target = row + delta
        if not (0 <= target < self._table.rowCount()):
            return None
        for candidate in (row, target):
            if self._is_configured_row(candidate):
                return self._origin(candidate)
        return None

    @staticmethod
    def _set_structure_action(button: QPushButton, *, blocked_by: int | None, tooltip: str) -> None:
        """Enable *button*, or disable it saying which configured row blocks it."""
        button.setEnabled(blocked_by is None)
        button.setToolTip("" if blocked_by is None else tooltip.format(row=blocked_by))

    # -- the row menu (configure / un-configure) --------------------------------

    def _on_context_menu(self, position: QPoint) -> None:
        """Pop the row menu for the row under the cursor (study sessions only)."""
        row = self._table.rowAt(position.y())
        if row < 0:
            return
        menu = self.row_menu(row)
        if menu is None:
            return
        menu.exec(self._table.viewport().mapToGlobal(position))

    def row_menu(self, row: int) -> QMenu | None:
        """The configure / un-configure menu for table *row* (``None`` outside a study).

        The element-row counterpart of
        :func:`~radiant.gui.widgets.configure_menu.add_configuration_actions`, and it
        takes its labels from that module so the two menus keep one vocabulary. A row
        that is not yet in the document (just added, not applied) shows the configure
        action **disabled with the reason** rather than absent — a silently missing
        action leaves the analyst guessing (Rule 17's spirit for UI state).
        """
        config_set = self._study_set()
        if config_set is None or not (0 <= row < self._table.rowCount()):
            return None
        menu = QMenu(self)
        menu.setToolTipsVisible(True)
        origin = self._origin(row)
        if origin == _NEW_ROW:
            action = QAction(CONFIGURE_TEXT, menu)
            action.setEnabled(False)
            action.setToolTip(_NEW_ROW_HINT)
            action.setStatusTip(_NEW_ROW_HINT)
        elif origin in self._configured_positions():
            action = QAction(unconfigure_element_text(config_set.names()[0]), menu)
            action.triggered.connect(lambda: self._unconfigure_row(row))
        else:
            action = QAction(CONFIGURE_TEXT, menu)
            action.setToolTip(_CONFIGURE_ROW_TOOLTIP)
            action.triggered.connect(lambda: self._configure_row(row))
        menu.addAction(action)
        return menu

    def _configure_row(self, row: int) -> None:
        """Configure element row *row* across every configuration — one API call.

        ``configure_element`` seeds **every** configuration with the row's current shared
        entry and moves it out of the shared document (the element analog of ADR-0010
        D-B), so the promotion changes no result. The table then re-reads the document,
        which is what shows the red "C".
        """
        config_set = self._study_set()
        origin = self._origin(row)
        if config_set is None or origin == _NEW_ROW:
            return
        try:
            config_set.configure_element(origin)
        except RadiantError as exc:
            exec_dialog(ActionableErrorDialog(exc, ELEMENT_EDIT_PATH, self))
            return
        self._reload_from_document()
        self.elementsApplied.emit(ELEMENT_EDIT_PATH)

    def _unconfigure_row(self, row: int) -> None:
        """Collapse a configured row back to one shared entry, keeping #1's (D-6).

        The confirmation **names the entry that survives and the ones that are
        discarded** before anything happens: collapsing silently changes the optics of
        every configuration that did not hold that entry, and that is never allowed to
        be a surprise — the same contract the configured-parameter collapse honours.
        """
        config_set = self._study_set()
        origin = self._origin(row)
        if config_set is None or origin not in self._configured_positions():
            return
        kept_name = config_set.names()[0]
        answer = QMessageBox.question(
            self,
            _UNCONFIGURE_TITLE,
            _UNCONFIGURE_BODY.format(
                row=origin,
                kept=kept_name,
                entry=self._entry_name(config_set, origin, kept_name),
                summary=self._entry_summary(config_set, origin),
            ),
            QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if answer != QMessageBox.StandardButton.Ok:
            return
        try:
            config_set.unconfigure_element(origin)
        except RadiantError as exc:
            exec_dialog(ActionableErrorDialog(exc, ELEMENT_EDIT_PATH, self))
            return
        self._reload_from_document()
        self.elementsApplied.emit(ELEMENT_EDIT_PATH)

    @staticmethod
    def _entry_name(config_set: ConfigurationSet, index: int, member: str) -> str:
        """The element name *member* gives configured row *index*."""
        return str(config_set.element_for(index, member).get("name", ""))

    def _entry_summary(self, config_set: ConfigurationSet, index: int) -> str:
        """``"MWIR: band_filter · LWIR: cirrus_filter"`` — every configuration's entry.

        Names only: the entry's ``name`` is what identifies it to the analyst (and it
        configures with the row, so it may legitimately differ per configuration), while
        listing whole entries would bury that in a wall of fields.
        """
        return _SUMMARY_SEPARATOR.join(
            f"{name}: {self._entry_name(config_set, index, name)}" for name in config_set.names()
        )

    # -- coating detail (Gap 116) ----------------------------------------------

    def refresh_coating_detail(self) -> None:
        """Draw the selected row's coating detail, or an actionable message.

        One GUI action ↔ one API call: the selection maps to
        :func:`radiant.api.plot_coating_detail` with the table's current
        entries passed as the document override, so an unapplied draft row is
        inspectable before Apply — and, in a study, the entries are the displayed
        configuration's, so a configured row plots *its* coating. A row the io parser
        rejects (bad path, malformed value) shows the parser's actionable message in
        place of the figure — never a blank pane, never a crash (Rule 15/17).
        """
        row = self._table.currentRow()
        if self._sensor is None or row < 0 or row >= self._table.rowCount():
            self._show_detail_message(_DETAIL_PROMPT)
            return
        entries = self.entries()
        name = str(entries[row].get("name", "")).strip()
        if not name:
            self._show_detail_message("Name this element to plot its coating detail.")
            return
        try:
            with plot_theme(dark=self._dark):
                figure = plot_coating_detail(self._sensor, name, entries=entries)
        except RadiantError as exc:
            self._show_detail_message(str(exc))
            return
        self._detail_message.setVisible(False)
        self._detail_canvas.setVisible(True)
        self._detail_canvas.show_figure(figure)

    def _show_detail_message(self, text: str) -> None:
        self._detail_message.setText(text)
        self._detail_message.setVisible(True)
        self._detail_canvas.setVisible(False)

    def set_dark(self, dark: bool) -> None:
        """Adopt the dark/light plot theme; re-render the detail if one is shown."""
        if dark == self._dark:
            return
        self._dark = dark
        if self._detail_canvas.isVisible():
            self.refresh_coating_detail()

    @property
    def detail_canvas(self) -> MatplotlibCanvas:
        """The coating-detail figure canvas (test seam)."""
        return self._detail_canvas

    @property
    def detail_message(self) -> QLabel:
        """The coating-detail message label (test seam)."""
        return self._detail_message

    # -- table mechanics ------------------------------------------------------

    def _append_row(self, entry: dict[str, Any], origin: int) -> None:
        # Silence the table while the row is half-built: Qt emits selection changes
        # during a structural mutation, and this widget's own listeners read the table
        # back (the coating-detail pane serializes every row), which asserts on a row
        # whose cell widgets are not there yet. Blocking, then refreshing explicitly,
        # is what keeps a listener from ever seeing a half-mutated table.
        blocker = QSignalBlocker(self._table)
        row = self._table.rowCount()
        self._table.insertRow(row)

        transfer = str(entry.get("transfer_mode", "REFLECTIVE")).upper()
        value = entry.get("reflectance" if transfer == "REFLECTIVE" else "transmittance", "")
        spectrum: dict[str, Any] | None = None
        if isinstance(value, dict):
            spectrum = value
            value = f"spectral ({len(value.get('wavelength_um', ()))} pts)"

        name_item = QTableWidgetItem(str(entry.get("name", "")))
        # The full text as a tooltip on every value-bearing cell: a spectral-CSV
        # path is longer than its column, so the hover is the guaranteed way to read
        # what the cell actually holds.
        name_item.setToolTip(name_item.text())
        # Row identity is positional, so every row remembers the document position it
        # came from; a row added here has none until an Apply puts it in the document.
        name_item.setData(_ORIGIN_ROLE, origin)
        self._table.setItem(row, _COL_NAME, name_item)

        transfer_combo = QComboBox(self._table)
        transfer_combo.addItems(list(_TRANSFER_CHOICES))
        transfer_combo.setCurrentText(transfer)
        self._table.setCellWidget(row, _COL_TRANSFER, transfer_combo)

        kind_combo = QComboBox(self._table)
        kind_combo.addItems(list(_KIND_CHOICES))
        kind_combo.setCurrentText(str(entry.get("kind", "lens")).lower())
        self._table.setCellWidget(row, _COL_KIND, kind_combo)
        # Kind applies to refractive rows only (a REFLECTIVE row is always a mirror —
        # the factory forces it and entries() omits kind). Keep the combo honest:
        # locked to "mirror" and disabled while the row is reflective.
        transfer_combo.currentTextChanged.connect(
            lambda text, combo=kind_combo: self._sync_kind_combo(combo, text)
        )
        self._sync_kind_combo(kind_combo, transfer)

        value_item = QTableWidgetItem(str(value))
        value_item.setToolTip(str(value))
        if spectrum is not None:
            value_item.setData(_SPECTRUM_ROLE, spectrum)
        self._table.setItem(row, _COL_VALUE, value_item)
        self._table.setItem(
            row, _COL_TEMP, QTableWidgetItem(str(entry.get("temperature_K", 293.0)))
        )
        self._table.setItem(row, _COL_DIAM, QTableWidgetItem(str(entry.get("diameter_m", 0.1))))
        self._table.setItem(
            row, _COL_DIST, QTableWidgetItem(str(entry.get("distance_to_fpa_m", 1.0)))
        )
        eps_item = QTableWidgetItem("—")
        eps_item.setFlags(eps_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        eps_item.setToolTip(_EPS_TOOLTIP)
        self._table.setItem(row, _COL_EPS, eps_item)
        del blocker  # the row is complete: signals flow again

    @staticmethod
    def _sync_kind_combo(kind_combo: QComboBox, transfer_text: str) -> None:
        """Lock Kind to "mirror" (disabled) on a REFLECTIVE row; free it on REFRACTIVE.

        Kind is a descriptive label for refractive elements; a reflective element is
        a mirror by construction, so showing an editable refractive kind there would
        misstate the document (owner report 2026-07-16).
        """
        reflective = transfer_text.upper() == "REFLECTIVE"
        if reflective:
            if kind_combo.findText("mirror") < 0:
                kind_combo.insertItem(0, "mirror")
            kind_combo.setCurrentText("mirror")
            kind_combo.setEnabled(False)
        else:
            kind_combo.setEnabled(True)
            mirror_idx = kind_combo.findText("mirror")
            if mirror_idx >= 0:
                if kind_combo.currentText() == "mirror":
                    kind_combo.setCurrentText("lens")
                kind_combo.removeItem(mirror_idx)

    def _add_row(self, entry: dict[str, Any]) -> None:
        """Append a new draft row — a **shared** row of the train, in every configuration.

        The train's structure is shared, so a row added here belongs to every
        configuration; it is seeded shared, and configuring it is a separate, explicit
        act (the row menu). Appending at the end shifts no configured row, so it is
        always expressible.
        """
        self._append_row(entry, _NEW_ROW)
        self._refresh_configured_marks()

    def _remove_current(self) -> None:
        """Drop the selected row from the train — for a configured row, behind a confirm.

        Removing a configured row discards **every** configuration's entry for it, which
        is the same irreversible per-configuration loss the un-configure collapse asks
        about, so it asks in the same way and names the entries at stake.
        """
        row = self._table.currentRow()
        if row < 0:
            return
        config_set = self._bound_set()
        origin = self._origin(row)
        if config_set is not None and origin in self._configured_positions():
            answer = QMessageBox.question(
                self,
                _REMOVE_CONFIGURED_TITLE,
                _REMOVE_CONFIGURED_BODY.format(
                    row=origin, summary=self._entry_summary(config_set, origin)
                ),
                QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Cancel,
            )
            if answer != QMessageBox.StandardButton.Ok:
                return
        blocker = QSignalBlocker(self._table)
        self._table.removeRow(row)
        del blocker
        self._refresh_configured_marks()
        self.refresh_coating_detail()

    def _move_current(self, delta: int) -> None:
        row = self._table.currentRow()
        target = row + delta
        if row < 0 or not (0 <= target < self._table.rowCount()):
            return
        rows = self._rows()
        rows[row], rows[target] = rows[target], rows[row]
        self._reload_rows(rows)
        self._refresh_configured_marks()
        self._table.setCurrentCell(target, _COL_NAME)

    def _rows(self) -> list[tuple[dict[str, Any], int]]:
        """The table as (entry, document position) pairs — identity travels with the row."""
        return [(entry, self._origin(row)) for row, entry in enumerate(self.entries())]

    def _reload(self, entries: list[dict[str, Any]]) -> None:
        """Render *entries* as the document's rows 0…n−1 (the document is the identity)."""
        self._reload_rows([(entry, index) for index, entry in enumerate(entries)])

    def _reload_rows(self, rows: list[tuple[dict[str, Any], int]]) -> None:
        blocker = QSignalBlocker(self._table)
        self._table.setRowCount(0)
        for entry, origin in rows:
            self._append_row(entry, origin)
        del blocker

    # -- document assembly ----------------------------------------------------

    def entries(self) -> list[dict[str, Any]]:
        """The table serialized to the declarative element document (verbatim cells).

        Value cells parse as float when numeric, otherwise pass through as a
        spectral-CSV path string — the two forms the document schema accepts. No
        physics validation happens here (the io parser owns it, on Apply).
        """
        result: list[dict[str, Any]] = []
        for row in range(self._table.rowCount()):
            transfer_widget = self._table.cellWidget(row, _COL_TRANSFER)
            kind_widget = self._table.cellWidget(row, _COL_KIND)
            assert isinstance(transfer_widget, QComboBox)  # noqa: S101 — widget invariant
            assert isinstance(kind_widget, QComboBox)  # noqa: S101 — widget invariant
            transfer = transfer_widget.currentText()
            entry: dict[str, Any] = {
                "name": self._cell_text(row, _COL_NAME),
                "transfer_mode": transfer,
                "temperature_K": self._cell_number(row, _COL_TEMP),
                "diameter_m": self._cell_number(row, _COL_DIAM),
                "distance_to_fpa_m": self._cell_number(row, _COL_DIST),
            }
            # A value cell is: an inline λ-table (dict in _SPECTRUM_ROLE, cell shows
            # the "spectral (N pts)" sentinel), a scalar when the text parses, or a
            # spectral-CSV path string — the three forms the document schema accepts.
            # Typing over the sentinel discards the stored table (the text wins).
            value_item = self._table.item(row, _COL_VALUE)
            stored = value_item.data(_SPECTRUM_ROLE) if value_item is not None else None
            text = self._cell_text(row, _COL_VALUE)
            value: Any
            if isinstance(stored, dict) and text.startswith(_SPECTRUM_SENTINEL):
                value = stored
            else:
                try:
                    value = float(text)
                except ValueError:
                    value = text
            if transfer == "REFLECTIVE":
                entry["reflectance"] = value
            else:
                entry["kind"] = kind_widget.currentText()
                entry["transmittance"] = value
            result.append(entry)
        return result

    def _cell_text(self, row: int, col: int) -> str:
        item = self._table.item(row, col)
        return item.text().strip() if item is not None else ""

    def _cell_number(self, row: int, col: int) -> Any:
        text = self._cell_text(row, col)
        try:
            return float(text)
        except ValueError:
            return text  # let the io parser reject it with its actionable message

    def _edit_spectrum(self) -> None:
        """Open the λ-table dialog for the selected row's R/T value (type or paste).

        OK stores the inline table on the cell (shown as "spectral (N pts)"); the
        document form is `{"wavelength_um": [...], "values": [...]}` — the same
        structure the YAML section carries, so it persists with the train.
        """
        row = self._table.currentRow()
        if row < 0:
            return
        value_item = self._table.item(row, _COL_VALUE)
        stored = value_item.data(_SPECTRUM_ROLE) if value_item is not None else None
        name = self._cell_text(row, _COL_NAME) or f"element {row}"
        dialog = SpectralTableDialog(
            self,
            title=f"Spectral R/T — {name}",
            initial=stored if isinstance(stored, dict) else None,
        )
        if exec_dialog(dialog) != int(dialog.DialogCode.Accepted):
            return
        spectrum = dialog.spectrum()
        if value_item is None:
            value_item = QTableWidgetItem()
            self._table.setItem(row, _COL_VALUE, value_item)
        value_item.setData(_SPECTRUM_ROLE, spectrum)
        value_item.setText(f"spectral ({len(spectrum['wavelength_um'])} pts)")

    # -- commit ---------------------------------------------------------------

    def apply_train(self) -> bool:
        """Commit the table — one user action, the document's own write path.

        * **No set bound** (a bare-sensor binding) or a **single-configuration session**:
          one ``Sensor.set_optical_elements`` — today's behaviour, unchanged.
        * **A study**: the shared skeleton goes to one ``set_optical_elements`` on the
          set's base, and each configured row's edited entry goes to one
          ``set_element_for(row, displayed, entry)`` — the displayed configuration only
          (D-8). See :meth:`_apply_study`.

        Success re-reads the table from the document, refills the derived-ε column, and
        emits :attr:`elementsApplied`; a rejection shows the actionable error dialog and
        stores nothing.
        """
        sensor = self._sensor
        if sensor is None:
            return False
        config_set = self._bound_set()
        if config_set is None:
            return self._apply_to_sensor(sensor)
        if self._study_set() is None and not config_set.configured_element_indices():
            # One member and no configured row: the table *is* the document. Same call,
            # same object as before in a plain session (the base is the displayed sensor).
            return self._apply_to_sensor(config_set.base)
        return self._apply_study(config_set)

    def _apply_to_sensor(self, sensor: Sensor) -> bool:
        """The single-document path: attach the table to *sensor* (today's behaviour).

        An empty table detaches the document (back to the scalar/params transmission
        mode).
        """
        entries = self.entries()
        try:
            if entries:
                sensor.set_optical_elements(entries)
                self._refresh_derived_emissivity(sensor.optical_elements() or entries)
            else:
                sensor.set_optical_elements(None)
        except RadiantError as exc:
            exec_dialog(ActionableErrorDialog(exc, ELEMENT_EDIT_PATH, self))
            return False
        self.elementsApplied.emit(ELEMENT_EDIT_PATH)
        return True

    def _apply_study(self, config_set: ConfigurationSet) -> bool:
        """Write a study's train: the shared skeleton, plus the displayed member's entries.

        The table renders the displayed configuration's effective train, so its rows split
        cleanly by the document's own single store (Gap 103 v1.1):

        * a **shared** row belongs to the shared document — all of them go, in table
          order, to one ``set_optical_elements`` on the base, which is what every
          configuration inherits;
        * a **configured** row belongs to the per-configuration table — its edited entry
          goes to ``set_element_for(row, displayed, entry)``, so the other
          configurations' entries stay verbatim (D-8);
        * a configured row the operator **removed** is collapsed first
          (``unconfigure_element``) and then simply left out of the skeleton, which is
          what drops it from every configuration.

        Every entry is validated through the io parser **before** anything is written, so
        a rejected train stores nothing — including the rows that would have been written
        ahead of the offending one. The rejection an invalid configured row shows is the
        API's own, which names the configuration it belongs to.
        """
        active = config_set.active
        rows = self._rows()
        configured = self._configured_positions()
        kept = {origin for _entry, origin in rows if origin in configured}
        skeleton = [entry for entry, origin in rows if origin not in kept]

        invalid = self._first_invalid(rows)
        if invalid is not None:
            index, rejection = invalid
            entry, origin = rows[index]
            if origin in kept:
                rejection = self._member_rejection(config_set, origin, entry) or rejection
            exec_dialog(ActionableErrorDialog(rejection, ELEMENT_EDIT_PATH, self))
            return False

        try:
            for origin in sorted(configured - kept, reverse=True):
                config_set.unconfigure_element(origin)
            config_set.base.set_optical_elements(skeleton or None)
            for entry, origin in rows:
                if origin in kept:
                    config_set.set_element_for(origin, active, entry)
        except RadiantError as exc:
            exec_dialog(ActionableErrorDialog(exc, ELEMENT_EDIT_PATH, self))
            return False
        self._reload_from_document()
        self.elementsApplied.emit(ELEMENT_EDIT_PATH)
        return True

    @staticmethod
    def _first_invalid(
        rows: list[tuple[dict[str, Any], int]],
    ) -> tuple[int, RadiantError] | None:
        """The first row the io parser rejects, with its error (``None`` when all pass).

        The gate that makes a study Apply all-or-nothing: the per-row writes below it
        cannot be rolled back, so nothing is written until every row has been through the
        single validation authority (Kirchhoff included, Rule 5).
        """
        for index, (entry, _origin) in enumerate(rows):
            try:
                normalize_element_document([dict(entry)])
            except RadiantError as exc:
                return index, exc
        return None

    @staticmethod
    def _member_rejection(
        config_set: ConfigurationSet, origin: int, entry: dict[str, Any]
    ) -> RadiantError | None:
        """The API's own rejection of *entry* for a configured row (naming the member).

        The gate above holds the io parser's error, which does not know whose entry it
        is. Routing the offending entry through the call that owns it — ``set_element_for``,
        which validates through the same parser and stores nothing on failure — produces
        the message the analyst needs: the configuration is named. ``None`` only if that
        call unexpectedly accepts the entry, in which case the caller shows the parser's
        own error rather than nothing.
        """
        try:
            config_set.set_element_for(origin, config_set.active, entry)
        except RadiantError as exc:
            return exc
        return None

    def _refresh_derived_emissivity(self, entries: list[dict[str, Any]]) -> None:
        """Fill the read-only ε column from the facade preview (Rule 5 — derived only)."""
        previews = preview_optical_elements(entries)
        for row, preview in enumerate(previews):
            item = self._table.item(row, _COL_EPS)
            if item is not None:
                item.setText(f"{preview.emissivity_mean:.4f}")

    # -- accessors (tests) ------------------------------------------------------

    @property
    def table(self) -> QTableWidget:
        """The element table (tests)."""
        return self._table

    @property
    def apply_button(self) -> QPushButton:
        """The Apply button (tests)."""
        return self._apply

    @property
    def study_note(self) -> QLabel:
        """The study note — hidden outside a multi-member study (tests)."""
        return self._study_note

    @property
    def name_delegate(self) -> EditableConfiguredNameDelegate:
        """The Name column's badge-painting delegate (tests)."""
        return self._name_delegate

    def is_row_configured(self, row: int) -> bool:
        """True when *row* renders a configured document row — the red "C" (tests)."""
        return self._is_configured_row(row)


__all__ = ["OpticalElementEditor", "ELEMENT_EDIT_PATH"]
