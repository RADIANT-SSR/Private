"""The Optics stage's **Elements** tab — the mixed-train element-list editor (ADR-0009 D2).

:class:`OpticalElementEditor` is the structured config-document editor of the GUI
Capability Expansion plan Phase GS-4 (audit O-1: per-element %R/%T/temperature mapping —
the audit's flagship optics gap). It edits the **declarative element document** — the same
entry dicts the ``optical_elements:`` YAML section carries — never physics objects: rows
are (name, transfer mode, kind, R-or-T value, temperature, geometry), *Apply* serializes
the table to entries and commits through exactly **one API call**,
:meth:`Sensor.set_optical_elements` (validate-and-attach through the io parser — the single
validation authority, Kirchhoff checks included — then persisted by ``Sensor.save``,
ADR-0009 D4). The optics stage runs full-prescription on the next evaluation and the
Throughput tab's coating-spectra figure reflects the authored train.

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

**Per-configuration elements (Gap 103 v1.1, owner-ratified 2026-09-02).** In a
multi-member study the tab renders the **active configuration's effective train** —
``ConfigurationSet.effective_optical_elements(active)``, i.e. the shared document with
that configuration's replace-by-name overrides swapped in — and a **scope control**
chooses what *Apply* writes:

* *Shared document* — the shared ``optical_elements`` document, exactly as a
  single-configuration session behaves. Rows an override swapped in are shown (badged)
  but **locked**, and Apply writes their **shared** entry back, so a shared edit can
  neither absorb an override's values nor disturb the override itself.
* *This configuration* — Apply **diffs** the edited train against the shared document
  and stores exactly the changed entries through one
  ``ConfigurationSet.set_element_override(active, changed)`` call; an entry edited back
  to equality with its shared counterpart drops out, and an empty diff calls
  ``clear_element_override(active)`` so the configuration inherits again. Element
  addition, removal, and reordering are structural properties of the shared train, so
  those affordances are disabled in this scope (an override replaces a shared element by
  name — it never adds or removes one).

A single-configuration session shows no scope control and behaves exactly as before.

All colour/typography comes from the QSS theme via object names; one widget class per
file (Rule 19).
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, Final

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
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

# -- per-configuration scope (Gap 103 v1.1) ---------------------------------------
# The two scopes an Apply can target in a multi-member study, in combo order. The
# labels are the owner-ratified wording (plan §4a, 2026-09-02).
_SCOPE_LABEL: Final[str] = "Edit scope:"
_SCOPE_SHARED: Final[str] = "Shared document"
_SCOPE_CONFIGURATION: Final[str] = "This configuration"
_SCOPE_INDEX_SHARED: Final[int] = 0
_SCOPE_INDEX_CONFIGURATION: Final[int] = 1
_SCOPE_COMBO_TOOLTIP = (
    "Which document Apply writes: the shared optical_elements train every configuration "
    "inherits, or this configuration's replace-by-name overrides."
)
_SCOPE_NOTE_SHARED = (
    "Apply edits the shared train every configuration inherits. Rows {name} overrides are "
    "shown for context and locked here. Switching scope re-reads the train from the "
    "document, so Apply before you switch."
)
_SCOPE_NOTE_CONFIGURATION = (
    "Apply stores only the entries that differ from the shared train as {name}'s overrides; "
    "an entry edited back to the shared values drops its override. Switching scope re-reads "
    "the train from the document, so Apply before you switch."
)
# The per-row marker for an entry an override swapped in, in the configured-badge
# family (same QSS rule, so it matches the red "C" in both themes).
_OVERRIDE_BADGE = "overridden — {name}"
_OVERRIDE_TOOLTIP_SHARED = (
    "{element} is overridden in {name}. Shared-document Apply keeps the shared entry and "
    "leaves the override untouched — pick the This configuration scope to edit it."
)
_OVERRIDE_TOOLTIP_CONFIGURATION = (
    "{element} is overridden in {name} — this row replaces the shared entry of that name."
)
_STRUCTURE_TOOLTIP = (
    "Adding, removing, or reordering elements changes the shared train: an override "
    "replaces a shared element by name and never adds or removes one. Pick the Shared "
    "document scope."
)
_REMOVE_OVERRIDDEN_TOOLTIP = (
    "{element} is overridden in {name}; removing it from the shared train would leave that "
    "override with nothing to replace. Edit it back to the shared values in the This "
    "configuration scope first."
)

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


def _canonical(value: Any) -> Any:
    """A comparable, order-independent form of an element-document value.

    Dicts compare by sorted key (so key order never decides equality), sequences
    elementwise, and every number as a ``float`` (so a shared ``293`` and an edited
    ``293.0`` are the same temperature). Everything else compares as-is.

    Numbers compare **exactly** — no tolerance. Both sides of the diff are the same
    entries rendered to text and parsed back (``repr`` round-trips a Python float
    exactly), so an untouched row is bit-identical, and a tolerance would silently
    swallow a small deliberate edit rather than store it (Rule 17).
    """
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, Mapping):
        return tuple(sorted(((str(k), _canonical(v)) for k, v in value.items()), key=_first))
    if isinstance(value, (list, tuple)):
        return tuple(_canonical(item) for item in value)
    return value


def _first(pair: tuple[str, Any]) -> str:
    """Sort key for :func:`_canonical`'s mapping items (the key, never the value)."""
    return pair[0]


def _entries_equal(entry: Mapping[str, Any], shared: Mapping[str, Any] | None) -> bool:
    """True when *entry* says exactly what the shared document's *shared* entry says.

    ``None`` (no shared entry of that name) is never equal: such an entry is a
    structural change the override mechanism refuses, and the API names it.
    """
    return shared is not None and _canonical(entry) == _canonical(shared)


class OpticalElementEditor(QWidget):
    """The element-train table editor: rows ⇌ the declarative element document.

    Signals
    -------
    elementsApplied(str):
        Emitted with :data:`ELEMENT_EDIT_PATH` after a successful Apply (the one
        ``sensor.set_optical_elements`` call), so the host marks state stale and
        schedules a re-evaluation — the same contract as ``parameterEdited``.
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

        # The scope control (Gap 103 v1.1): shown only for a multi-member study, where
        # "which document does Apply write" is a real question. A single-configuration
        # session never sees it and keeps today's one-document behaviour.
        self._scope_row = QWidget(card)
        scope_layout = QHBoxLayout(self._scope_row)
        scope_layout.setContentsMargins(0, 0, 0, 0)
        scope_layout.setSpacing(6)
        scope_caption = QLabel(_SCOPE_LABEL, self._scope_row)
        scope_caption.setObjectName("stageCenterNote")
        self._scope_combo = QComboBox(self._scope_row)
        self._scope_combo.setObjectName("elementScopeCombo")
        self._scope_combo.addItems([_SCOPE_SHARED, _SCOPE_CONFIGURATION])
        self._scope_combo.setToolTip(_SCOPE_COMBO_TOOLTIP)
        self._scope_note = QLabel("", self._scope_row)
        self._scope_note.setObjectName("stageCenterNote")
        self._scope_note.setWordWrap(True)
        scope_layout.addWidget(scope_caption)
        scope_layout.addWidget(self._scope_combo)
        scope_layout.addWidget(self._scope_note, 1)
        self._scope_row.setVisible(False)
        box.addWidget(self._scope_row)

        self._table = QTableWidget(0, len(_HEADERS), card)
        self._table.setObjectName("elementTable")
        self._table.setHorizontalHeaderLabels(list(_HEADERS))
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.verticalHeader().setVisible(False)
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
        self._scope_combo.currentIndexChanged.connect(self._on_scope_changed)
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
        multi-member study*, *which configuration is active*, and *what does it
        override*. The tab re-reads the train through it, so the scope control appears
        (and the effective train renders) as soon as a study is the open document.

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

    # -- per-configuration scope (Gap 103 v1.1) --------------------------------

    def _bound_set(self) -> ConfigurationSet | None:
        """The session document, whatever its size (``None`` when none is bound).

        Whose element document the tab reads and a shared Apply writes. In a plain
        session the set's base **is** the displayed sensor, so reading and writing
        through it is the same object and the same behaviour as before; where the two
        differ — any set whose displayed sensor is a materialization — the document is
        the one that survives, and the throwaway is not it (Rule 17).
        """
        scope = self._scope
        return None if scope is None else scope.configuration_set

    def _study_set(self) -> ConfigurationSet | None:
        """The session's set when it is a **multi-member** study, else ``None``.

        The gate on everything per-configuration: the scope control, the badges, and
        the override routing. A one-configuration set is deliberately excluded — it has
        no second member to differ from, so a per-configuration override would say
        nothing the shared document does not already say.
        """
        config_set = self._bound_set()
        if config_set is None or len(config_set.names()) <= 1:
            return None
        return config_set

    def _override_target(self) -> str | None:
        """The configuration an Apply would override, or ``None`` for a shared Apply."""
        config_set = self._study_set()
        if config_set is None:
            return None
        if self._scope_combo.currentIndex() != _SCOPE_INDEX_CONFIGURATION:
            return None
        return config_set.active

    def _overridden_names(self) -> set[str]:
        """Element names the active configuration overrides (empty outside a study)."""
        config_set = self._study_set()
        if config_set is None:
            return set()
        entries = config_set.element_overrides(config_set.active)
        return {str(entry.get("name")) for entry in entries or ()}

    def _document_entries(self) -> tuple[list[dict[str, Any]], str]:
        """The entries to render, plus any advisory the API raised reading them.

        With a set bound that is the active configuration's **effective** train (shared
        document, overrides swapped in, shared order) — which for a plain session is
        simply the displayed sensor's own document, since the set's base is that sensor.
        The one way the read can fail is an override whose shared counterpart has gone —
        reachable only by replacing the base document behind the set's back (a console
        ``set_optical_elements``). The tab then falls back to the shared train so it
        stays usable, and returns the API's actionable message so it is shown rather
        than swallowed (Rule 17); the same error also names the configuration on the
        next evaluation.
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
        self._sync_scope_control()
        self._apply_scope_state()
        self.refresh_coating_detail()
        if advisory:
            self._show_detail_message(advisory)

    def _sync_scope_control(self) -> None:
        """Show/hide the scope control and word its note for the active configuration."""
        config_set = self._study_set()
        self._scope_row.setVisible(config_set is not None)
        if config_set is None:
            self._scope_combo.setCurrentIndex(_SCOPE_INDEX_SHARED)
            self._scope_note.setText("")
            return
        note = (
            _SCOPE_NOTE_CONFIGURATION
            if self._scope_combo.currentIndex() == _SCOPE_INDEX_CONFIGURATION
            else _SCOPE_NOTE_SHARED
        )
        self._scope_note.setText(note.format(name=config_set.active))

    def _on_scope_changed(self, index: int) -> None:
        """Re-read the train for the newly chosen scope (the note says this happens)."""
        del index  # the scope is read back from the combo
        self._reload_from_document()

    def _apply_scope_state(self) -> None:
        """Badge overridden rows and lock what the current scope may not edit.

        Two locks, both structural rather than cosmetic:

        * **Shared scope, overridden row** — the row shows the *override's* values, which
          do not belong to the shared document. It is read-only, and a shared Apply
          writes its shared entry back (:meth:`_shared_document_from_table`), so a shared
          edit can neither absorb an override's values nor silently drop the operator's
          typing into a document that will not keep it.
        * **This-configuration scope** — add / remove / reorder and the Name cells are
          disabled: an override replaces a shared element **by name**, so a new name, a
          missing row, or a different order has nowhere to land and would be a silent
          no-op (or an API refusal) at Apply.
        """
        config_set = self._study_set()
        target = self._override_target()
        per_configuration = target is not None
        active = config_set.active if config_set is not None else ""
        overridden = self._overridden_names()
        for button in (self._add_mirror, self._add_refractive, self._up, self._down):
            button.setEnabled(not per_configuration)
            button.setToolTip("" if not per_configuration else _STRUCTURE_TOOLTIP)
        for row in range(self._table.rowCount()):
            name = self._cell_text(row, _COL_NAME)
            marked = name in overridden
            locked = marked and not per_configuration
            self._set_row_locked(row, locked=locked, name_locked=per_configuration)
            tooltip = (
                _OVERRIDE_TOOLTIP_CONFIGURATION if per_configuration else _OVERRIDE_TOOLTIP_SHARED
            ).format(element=name, name=active)
            self._set_row_badge(row, name, active if marked else None, tooltip)
        self._sync_selection_actions()

    def _set_row_locked(self, row: int, *, locked: bool, name_locked: bool) -> None:
        """Make *row*'s cells read-only (or editable again) for the current scope."""
        for col in (_COL_VALUE, _COL_TEMP, _COL_DIAM, _COL_DIST):
            item = self._table.item(row, col)
            if item is not None:
                self._set_editable(item, not locked)
        name_item = self._table.item(row, _COL_NAME)
        if name_item is not None:
            self._set_editable(name_item, not (locked or name_locked))
        transfer = self._table.cellWidget(row, _COL_TRANSFER)
        kind = self._table.cellWidget(row, _COL_KIND)
        if isinstance(transfer, QComboBox):
            transfer.setEnabled(not locked)
        if isinstance(kind, QComboBox):
            if locked:
                kind.setEnabled(False)
            elif isinstance(transfer, QComboBox):
                # Never a blanket re-enable: Kind stays locked to "mirror" on a
                # REFLECTIVE row whatever the scope is.
                self._sync_kind_combo(kind, transfer.currentText())

    @staticmethod
    def _set_editable(item: QTableWidgetItem, editable: bool) -> None:
        """Flip *item*'s editable flag (the ε cell is read-only by construction)."""
        if editable:
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEditable)
        else:
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)

    def _set_row_badge(self, row: int, name: str, config: str | None, tooltip: str) -> None:
        """Mark *row* as overridden by *config* (or clear the mark when ``None``).

        The marker is the configured-badge family — a ``QLabel`` carrying the
        ``configuredBadge`` object name, so it is the same red, weight, and font the
        red "C" uses in both themes (GUI plan §4.9: no colour literal here). It rides
        as a cell widget over the Name cell, whose item still holds the plain element
        name, so :meth:`entries` keeps reading the document's name and not the badge.
        """
        if config is None:
            self._table.removeCellWidget(row, _COL_NAME)
            return
        host = QWidget(self._table)
        host.setToolTip(tooltip)
        row_layout = QHBoxLayout(host)
        row_layout.setContentsMargins(4, 0, 4, 0)
        row_layout.setSpacing(6)
        name_label = QLabel(name, host)
        badge = QLabel(_OVERRIDE_BADGE.format(name=config), host)
        badge.setObjectName("configuredBadge")
        row_layout.addWidget(name_label)
        row_layout.addWidget(badge)
        row_layout.addStretch(1)
        self._table.setCellWidget(row, _COL_NAME, host)

    def _sync_selection_actions(self) -> None:
        """Enable the selection-driven buttons only where they are a legal edit.

        *Remove* is refused in the This-configuration scope (structure is shared) and,
        in the Shared scope, on a row some configuration overrides — removing that
        shared element would leave the override with nothing to replace. *Spectrum…*
        writes into a value cell, so it follows the row's lock: on a locked row the
        edit would be substituted away at Apply, and a button that discards what it
        collects is worse than one that is disabled.
        """
        config_set = self._study_set()
        row = self._table.currentRow()
        name = self._cell_text(row, _COL_NAME) if 0 <= row < self._table.rowCount() else ""
        per_configuration = self._override_target() is not None
        overridden = config_set is not None and name in self._overridden_names()
        locked = overridden and not per_configuration
        self._spectrum.setEnabled(not locked)
        self._spectrum.setToolTip(
            _OVERRIDE_TOOLTIP_SHARED.format(
                element=name, name="" if config_set is None else config_set.active
            )
            if locked
            else _SPECTRUM_TOOLTIP
        )
        if per_configuration:
            self._remove.setEnabled(False)
            self._remove.setToolTip(_STRUCTURE_TOOLTIP)
            return
        if overridden and config_set is not None:
            self._remove.setEnabled(False)
            self._remove.setToolTip(
                _REMOVE_OVERRIDDEN_TOOLTIP.format(element=name, name=config_set.active)
            )
            return
        self._remove.setEnabled(True)
        self._remove.setToolTip("")

    # -- coating detail (Gap 116) ----------------------------------------------

    def refresh_coating_detail(self) -> None:
        """Draw the selected row's coating detail, or an actionable message.

        One GUI action ↔ one API call: the selection maps to
        :func:`radiant.api.plot_coating_detail` with the table's current
        entries passed as the document override, so an unapplied draft row is
        inspectable before Apply. A row the io parser rejects (bad path,
        malformed value) shows the parser's actionable message in place of the
        figure — never a blank pane, never a crash (Rule 15/17).
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

    def _append_row(self, entry: dict[str, Any]) -> None:
        row = self._table.rowCount()
        self._table.insertRow(row)

        transfer = str(entry.get("transfer_mode", "REFLECTIVE")).upper()
        value = entry.get("reflectance" if transfer == "REFLECTIVE" else "transmittance", "")
        spectrum: dict[str, Any] | None = None
        if isinstance(value, dict):
            spectrum = value
            value = f"spectral ({len(value.get('wavelength_um', ()))} pts)"

        self._table.setItem(row, _COL_NAME, QTableWidgetItem(str(entry.get("name", ""))))

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
        self._table.setItem(row, _COL_EPS, eps_item)

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
        """Append a new draft row and re-apply the scope's locks/badges to the table."""
        self._append_row(entry)
        self._apply_scope_state()

    def _remove_current(self) -> None:
        row = self._table.currentRow()
        if row >= 0:
            self._table.removeRow(row)
            self._apply_scope_state()

    def _move_current(self, delta: int) -> None:
        row = self._table.currentRow()
        target = row + delta
        if row < 0 or not (0 <= target < self._table.rowCount()):
            return
        entries = self.entries()
        entries[row], entries[target] = entries[target], entries[row]
        self._reload(entries)
        self._apply_scope_state()
        self._table.setCurrentCell(target, _COL_NAME)

    def _reload(self, entries: list[dict[str, Any]]) -> None:
        self._table.setRowCount(0)
        for entry in entries:
            self._append_row(entry)

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

    # -- commit (one API call) -------------------------------------------------

    def apply_train(self) -> bool:
        """Commit the table — one API call, chosen by the current scope.

        * *This configuration* scope (multi-member study only): one
          ``set_element_override`` — or ``clear_element_override`` when nothing differs
          — see :meth:`_apply_configuration_override`.
        * Otherwise the **shared** document: one ``set_optical_elements`` on the set's
          base, with any overridden row's shared entry written back in place of the
          locked display values, so existing overrides survive verbatim. In a plain
          session the base **is** the displayed sensor, so this is today's call on
          today's object; where they differ (any set whose displayed sensor is a
          materialization) the document is what survives the next switch, and the
          throwaway is not.
        * With no set bound at all (a bare-sensor binding): one
          ``Sensor.set_optical_elements`` on the live sensor.

        Success re-reads the table from the document (so a new override's badge appears
        immediately), refills the derived-ε column, and emits :attr:`elementsApplied`;
        a rejection shows the actionable error dialog and stores nothing (fail-fast in
        the API).
        """
        sensor = self._sensor
        if sensor is None:
            return False
        config_set = self._bound_set()
        if config_set is None:
            return self._apply_to_sensor(sensor)
        if self._override_target() is not None:
            return self._apply_configuration_override(config_set)
        if self._study_set() is None:
            # One member: no override can exist, so there is nothing to substitute and
            # nothing to re-derive — the table *is* the document. Same call, same
            # object as before in a plain session (the base is the displayed sensor).
            return self._apply_to_sensor(config_set.base)
        return self._apply_shared_document(config_set)

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

    def _apply_shared_document(self, config_set: ConfigurationSet) -> bool:
        """Write the shared train of a study — overrides untouched."""
        entries = self._shared_document_from_table(config_set)
        try:
            config_set.base.set_optical_elements(entries if entries else None)
        except RadiantError as exc:
            exec_dialog(ActionableErrorDialog(exc, ELEMENT_EDIT_PATH, self))
            return False
        self._reload_from_document()
        self.elementsApplied.emit(ELEMENT_EDIT_PATH)
        return True

    def _shared_document_from_table(self, config_set: ConfigurationSet) -> list[dict[str, Any]]:
        """The table as a **shared** document: overridden rows keep their shared entry.

        The table renders the effective train, so an overridden row displays the
        override's values. Those values belong to one configuration, not to the shared
        document, and writing them into it would silently promote a band-specific entry
        to every configuration. The row is locked in this scope for exactly that reason;
        here its shared counterpart is substituted back so the write is a true
        shared-only edit.
        """
        shared = {
            str(entry.get("name")): entry for entry in config_set.base.optical_elements() or []
        }
        overridden = self._overridden_names()
        return [
            shared[str(entry.get("name"))]
            if str(entry.get("name")) in overridden and str(entry.get("name")) in shared
            else entry
            for entry in self.entries()
        ]

    def _apply_configuration_override(self, config_set: ConfigurationSet) -> bool:
        """Store the table's *difference* from the shared train as the active override.

        The diff is per entry, by name, against the shared document, on the entries the
        API itself would store: the table is normalized through the same
        ``normalize_element_document`` the API applies, so a relative spectral-file path
        and its absolutized shared counterpart compare equal instead of reading as an
        edit. Entries that match their shared counterpart drop out; an empty diff clears
        the override so the configuration inherits again (there is no such thing as an
        override that changes nothing).

        A table the io parser rejects has no meaningful diff, so the **whole** table
        goes to the API, which refuses it with the io parser's message and the
        configuration named — and stores nothing.
        """
        name = config_set.active
        edited = self.entries()
        shared = {
            str(entry.get("name")): entry for entry in config_set.base.optical_elements() or []
        }
        try:
            normalized = normalize_element_document([dict(entry) for entry in edited])
        except RadiantError:
            changed = edited
        else:
            changed = [
                raw
                for raw, entry in zip(edited, normalized, strict=True)
                if not _entries_equal(entry, shared.get(str(entry.get("name"))))
            ]
        try:
            if changed:
                config_set.set_element_override(name, changed)
            else:
                config_set.clear_element_override(name)
        except RadiantError as exc:
            exec_dialog(ActionableErrorDialog(exc, ELEMENT_EDIT_PATH, self))
            return False
        self._reload_from_document()
        self.elementsApplied.emit(ELEMENT_EDIT_PATH)
        return True

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
    def scope_selector(self) -> QComboBox:
        """The Shared-document / This-configuration scope combo (tests)."""
        return self._scope_combo

    @property
    def scope_row(self) -> QWidget:
        """The scope control's row — hidden outside a multi-member study (tests)."""
        return self._scope_row

    def override_badge_text(self, row: int) -> str | None:
        """*row*'s override badge text, or ``None`` when the row is inherited (tests)."""
        host = self._table.cellWidget(row, _COL_NAME)
        if host is None:
            return None
        badge = host.findChild(QLabel, "configuredBadge")
        return None if badge is None else badge.text()


__all__ = ["OpticalElementEditor", "ELEMENT_EDIT_PATH"]
