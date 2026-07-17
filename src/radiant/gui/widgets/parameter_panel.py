"""The parameter dock's contents: filter box + schema-driven parameter tree (§4.3).

:class:`ParameterPanel` is the body of the left "Parameters" dock. It builds a
three-column tree — Parameter / Value / Source — **entirely** from
``Sensor.parameter_defs()`` (never a transcribed list, Gap 70), grouped by dot-path
namespace in chain order (geometry first). Each row shows the resolved value with its
schema unit suffix (R-UNITS); derived parameters carry the ⚡ marker; the Source column
shows the provenance (user-set / config / default / derived) sourced from the resolved
set via the public :meth:`Sensor.explain` surface (see
:mod:`radiant.gui.param_format`). A live filter box narrows rows by substring across
full dot-paths.

GUI plan Phase 2 **Task B** (this module) adds editing on top of the Task-A read-only
tree:

* Double-click (or the edit key) on an editable row opens the editor the parameter's
  schema calls for (:class:`~radiant.gui.widgets.parameter_delegate.ParameterEditDelegate`)
  — combo for enums, checkbox for bools, spin box for ints, line edit for floats/strings.
  Derived (⚡) rows stay read-only.
* Commit runs **one** ``sensor.set(dotpath, value)`` (§4.1). To keep the live sensor
  untouched when a value is rejected, the edit is first validated on a throwaway
  ``sensor.clone()`` (the API's own resolve does the validating — no reimplemented
  physics); only a clean value is applied to the live sensor. A rejected value never
  reaches the display and never mutates the sensor.
* Rejections (``ParameterBoundsError`` / ``UnknownParameterError`` / consistency-group
  violations — all surfaced by the resolver) render inline on the row (themed error
  tint + tooltip + a themed banner) **and** in a modal
  (:class:`~radiant.gui.widgets.actionable_error_dialog.ActionableErrorDialog`); an
  unexpected exception raises
  :class:`~radiant.gui.widgets.unexpected_error_dialog.UnexpectedErrorDialog` with a
  traceback fold (Rules 15/17 — nothing swallowed).
* Right-click: Copy dot-path, Explain (``sensor.explain`` in
  :class:`~radiant.gui.widgets.explain_dialog.ExplainDialog`), Reset to Default
  (``sensor.reset``).

Styling comes entirely from the design-system QSS theme; this module sets structure,
object names, and text only (GUI plan §4.9).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMenu,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from radiant.core.exceptions import RadiantError
from radiant.gui.param_format import (
    DERIVED_BADGE,
    display_in_unit,
    format_value,
    group_by_namespace,
    is_derived,
    ordered_namespaces,
    provenance_label,
    safe_provenance,
)
from radiant.gui.widgets.actionable_error_dialog import ActionableErrorDialog
from radiant.gui.widgets.explain_dialog import ExplainDialog
from radiant.gui.widgets.parameter_delegate import (
    DOTPATH_ROLE,
    ERROR_ROLE,
    ParameterEditDelegate,
    ReadOnlyCellDelegate,
)
from radiant.gui.widgets.parameter_editor_dialog import ParameterEditorDialog
from radiant.gui.widgets.unexpected_error_dialog import UnexpectedErrorDialog

if TYPE_CHECKING:
    from radiant.api.sensor import Sensor
    from radiant.core.parameters import ParameterDef

# The three columns of the parameter tree (§4.3): the leaf parameter name, its
# value + unit suffix, and its provenance ("Source").
_COLUMNS: tuple[str, ...] = ("Parameter", "Value", "Source")

# Qt item-data role carrying each leaf row's full dot-path (for filtering, editing,
# and the both-directions schema-match test). Shared with the edit delegate.
_DOTPATH_ROLE = DOTPATH_ROLE

_EMPTY_MESSAGE = "No configuration loaded — open a YAML to inspect parameters"

# Compact fixed widths (px, layout geometry — not design tokens) for the Value and
# Source columns, so the stretchy Parameter column keeps the most room in the dock.
_VALUE_COL_WIDTH = 104
_SOURCE_COL_WIDTH = 72


class ParameterPanel(QWidget):
    """Filter box + schema-driven Parameter/Value/Source tree, editable (Task B).

    Parameters
    ----------
    parent:
        The owning widget, if any.

    Signals
    -------
    parameterEdited(str):
        Emitted with the dot-path after an accepted edit or a reset, so the host
        window can mark downstream state stale (a re-evaluation is due).
    """

    parameterEdited = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("parameterPanel")

        # The sensor currently displayed (None → empty state), and the dot-path ->
        # leaf QTreeWidgetItem map for filtering, editing, and test introspection.
        self._sensor: Sensor | None = None
        self._items: dict[str, QTreeWidgetItem] = {}
        # The dot-path of the row whose last edit was rejected (themed error tint),
        # or None when no row is in the error state.
        self._error_dotpath: str | None = None
        # Per-dot-path display-unit preference (owner feedback 2026-07-13: show the
        # value in the unit the user chose, not always the canonical/input unit). A
        # row absent here displays in its schema input_unit (unchanged behaviour); a
        # row gains an entry when the user commits an edit through the Parameter Editor
        # with an explicit unit choice. Session-scoped only — persistence across
        # launches arrives with QSettings in Phase 9. Cleared when a new sensor loads.
        self._display_units: dict[str, str] = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        self._filter = QLineEdit(self)
        self._filter.setObjectName("parameterSearch")
        self._filter.setPlaceholderText("Filter parameters…")
        self._filter.setClearButtonEnabled(True)
        self._filter.textChanged.connect(self._apply_filter)

        self._tree = QTreeWidget(self)
        self._tree.setObjectName("parameterTree")
        self._tree.setColumnCount(len(_COLUMNS))
        self._tree.setHeaderLabels(list(_COLUMNS))
        self._tree.setRootIsDecorated(True)
        self._tree.setAlternatingRowColors(True)
        # Open the editor on double-click or the platform edit key (§4.3). Only
        # rows carrying ItemIsEditable (non-derived leaves) actually open one.
        self._tree.setEditTriggers(
            QAbstractItemView.EditTrigger.DoubleClicked
            | QAbstractItemView.EditTrigger.EditKeyPressed
        )
        # Right-click context menu (Copy dot-path / Explain / Reset to Default).
        self._tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._tree.customContextMenuRequested.connect(self._show_context_menu)

        # Value-column editor delegate: providers read the *live* sensor at edit
        # time, and commits route through _commit_edit (one sensor.set per edit).
        self._delegate = ParameterEditDelegate(
            self._pdef_for,
            self._input_value_for,
            self._commit_edit,
            self._tree,
        )
        self._tree.setItemDelegateForColumn(1, self._delegate)
        # Parameter (name) + Source columns never open an in-place editor: a
        # double-click there opens the full ParameterEditorDialog instead (§4.3).
        self._readonly_delegate = ReadOnlyCellDelegate(self._tree)
        self._tree.setItemDelegateForColumn(0, self._readonly_delegate)
        self._tree.setItemDelegateForColumn(2, self._readonly_delegate)
        # Double-click on any column other than Value opens the detail editor dialog.
        self._tree.doubleClicked.connect(self._on_double_click)

        # Give the (often long) parameter names the stretch space; keep the Value
        # and Source columns compact so, in the narrow dock, names truncate last.
        header = self._tree.header()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Interactive)
        self._tree.setColumnWidth(1, _VALUE_COL_WIDTH)
        self._tree.setColumnWidth(2, _SOURCE_COL_WIDTH)

        self._empty_msg = QLabel(_EMPTY_MESSAGE, self)
        self._empty_msg.setObjectName("parameterEmptyMsg")
        self._empty_msg.setWordWrap(True)
        self._empty_msg.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Themed inline error banner (hidden until a rejected edit); QSS owns colour.
        self._error_banner = QLabel("", self)
        self._error_banner.setObjectName("parameterErrorBanner")
        self._error_banner.setWordWrap(True)
        self._error_banner.setVisible(False)

        layout.addWidget(self._filter)
        layout.addWidget(self._tree, 1)
        layout.addWidget(self._empty_msg, 1)
        layout.addWidget(self._error_banner)

        # A freshly constructed panel carries no sensor: show the empty state.
        self._show_empty_state()

    # -- public accessors ---------------------------------------------------

    @property
    def filter_box(self) -> QLineEdit:
        """The live parameter filter box (substring match across dot-paths)."""
        return self._filter

    @property
    def tree(self) -> QTreeWidget:
        """The Parameter/Value/Source tree built from the schema."""
        return self._tree

    @property
    def error_banner(self) -> QLabel:
        """The themed inline error banner (visible only after a rejected edit)."""
        return self._error_banner

    @property
    def display_units(self) -> dict[str, str]:
        """The session display-unit store (dot-path → chosen unit), shared by reference.

        The Geometry screen's input form (GUI plan Phase 5) binds this same dict so a
        unit chosen in either the tree's Parameter Editor or the form's editor agrees.
        Cleared in place on a new-sensor load, so a shared reference stays valid.
        """
        return self._display_units

    def row_dotpaths(self) -> set[str]:
        """Every parameter dot-path currently rendered as a tree row."""
        return set(self._items)

    def value_text(self, dotpath: str) -> str:
        """The Value-column text (value + unit, ⚡ prefix if derived) for a row."""
        return self._items[dotpath].text(1)

    def source_text(self, dotpath: str) -> str:
        """The Source-column (provenance label) text for a row."""
        return self._items[dotpath].text(2)

    def is_editable(self, dotpath: str) -> bool:
        """True when the row for *dotpath* accepts edits (non-derived leaf)."""
        return bool(self._items[dotpath].flags() & Qt.ItemFlag.ItemIsEditable)

    def has_error(self, dotpath: str) -> bool:
        """True when the row for *dotpath* is showing the rejected-edit state."""
        return bool(self._items[dotpath].data(1, ERROR_ROLE))

    def visible_dotpaths(self) -> set[str]:
        """Dot-paths of the rows currently visible (not filtered out)."""
        return {dotpath for dotpath, item in self._items.items() if not item.isHidden()}

    def scroll_to_namespace(self, namespace: str) -> bool:
        """Scroll to, expand, and select the *namespace* group header (stage-strip click).

        Returns ``True`` if the group exists (and was scrolled to), ``False`` if no
        such namespace is present — the caller (the stage strip navigation, GUI plan
        Phase 4) then knows the parameter tree has no group for that stage. Navigation
        only: no sensor mutation, no evaluation.
        """
        for i in range(self._tree.topLevelItemCount()):
            group = self._tree.topLevelItem(i)
            if group.text(0) == namespace:
                group.setExpanded(True)
                self._tree.scrollToItem(group, QAbstractItemView.ScrollHint.PositionAtTop)
                self._tree.setCurrentItem(group)
                return True
        return False

    # -- population ---------------------------------------------------------

    def populate(self, sensor: Sensor | None) -> None:
        """(Re)build the tree from *sensor*'s schema, or show the empty state.

        With a resolvable ``Sensor`` (the ``radiant gui CONFIG.yaml`` path) the
        tree fills from ``sensor.parameter_defs()``; ``None`` (a bare launch — a
        default ``Sensor()`` is not resolvable) leaves the themed "no configuration
        loaded" state. Rebuilding clears any transient rejected-edit state.

        A genuinely *new* sensor (a different object — the ``radiant gui CONFIG`` or an
        Open action) resets the session's display-unit preferences; a refresh with the
        *same* sensor object (the post-edit re-populate) preserves them so a row the
        user re-unitted keeps that unit across edits.
        """
        if sensor is not self._sensor:
            self._display_units.clear()
        self._sensor = sensor
        self._clear_error_state()
        self._tree.clear()
        self._items.clear()

        if sensor is None:
            self._show_empty_state()
            return

        defs = sensor.parameter_defs()
        grouped = group_by_namespace(defs)
        for namespace in ordered_namespaces(defs.keys()):
            group_item = QTreeWidgetItem([namespace, "", ""])
            self._tree.addTopLevelItem(group_item)
            for dotpath, pdef in grouped[namespace]:
                child = self._build_row(sensor, dotpath, pdef)
                group_item.addChild(child)
                self._items[dotpath] = child
            group_item.setExpanded(True)

        self._show_tree()
        self._apply_filter(self._filter.text())

    def _build_row(
        self,
        sensor: Sensor,
        dotpath: str,
        pdef: ParameterDef,
    ) -> QTreeWidgetItem:
        """One leaf row: value + display unit, ⚡-marked, provenance-labelled, editable.

        A sensor that cannot resolve yet (a blank File → New: required parameters
        unset) still gets a full tree — every row falls back to an unset display
        (no provenance label, — value) instead of crashing populate (found
        2026-07-16: `explain`/`get_input` resolve internally and raised
        `CoreValidationError` through the File → New path).
        """
        provenance = safe_provenance(sensor, dotpath)
        derived = is_derived(provenance)
        try:
            value, unit = self._display_value_and_unit(sensor, dotpath, pdef)
        except RadiantError:
            value, unit = None, (pdef.input_unit or "")
        value_text = format_value(value, unit)
        if derived:
            value_text = f"{DERIVED_BADGE} {value_text}"

        # Leaf label is the dot-path remainder after the namespace prefix.
        leaf = dotpath.split(".", 1)[1] if "." in dotpath else dotpath
        item = QTreeWidgetItem([leaf, value_text, provenance_label(provenance)])
        item.setData(0, _DOTPATH_ROLE, dotpath)
        item.setToolTip(0, f"{dotpath}\n{pdef.description}" if pdef.description else dotpath)
        # Editable unless derived (Rule 4 / §4.3: ⚡ rows are read-only). The
        # ItemIsEditable flag on column 1 is what lets the delegate open an editor.
        if not derived:
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEditable)
        return item

    @staticmethod
    def _resolved_value(sensor: Sensor, dotpath: str) -> object | None:
        """Resolved value in input units, or ``None`` if the parameter is unset.

        A required-unless parameter superseded by an alternative resolves to no
        value; ``Sensor.get_input`` raises ``KeyError`` for it. Rendering that as
        an explicit em-dash (``None`` here) is a visible state, not a swallowed
        error (Rule 17) — the row still appears, marked unresolved.
        """
        try:
            return sensor.get_input(dotpath)
        except KeyError:
            return None

    # -- display units ------------------------------------------------------

    def display_unit(self, dotpath: str) -> str:
        """The unit a row's value is currently displayed in (owner feedback 2026-07-13).

        Defaults to the parameter's schema ``input_unit`` (unchanged behaviour for a
        never-edited row); overridden to the unit the user picked when they last
        committed an edit through the Parameter Editor. Session-scoped (Phase 9 adds
        QSettings persistence).
        """
        assert self._sensor is not None
        override = self._display_units.get(dotpath)
        if override is not None:
            return override
        return self._sensor.parameter_def(dotpath).input_unit

    def _display_value_and_unit(
        self,
        sensor: Sensor,
        dotpath: str,
        pdef: ParameterDef,
    ) -> tuple[Any, str]:
        """The (value, unit) pair to show for a row, honouring its display-unit choice.

        With no override (or an override equal to the schema input_unit) this is the
        resolved input-unit value and the input_unit — the original behaviour. With an
        override it re-expresses the value in that unit through the public registry
        seam (:func:`~radiant.gui.param_format.display_in_unit`); if that unit is not
        soundly convertible (unregistered / offset unit) it **falls back** to the
        canonical/input unit for that row rather than inventing a conversion (Rule 2).
        """
        input_value = self._resolved_value(sensor, dotpath)
        target = self._display_units.get(dotpath)
        if target is None or target == pdef.input_unit:
            return input_value, pdef.input_unit
        try:
            value = display_in_unit(input_value, pdef.input_unit, target, pdef.canonical_unit)
        except KeyError:
            return input_value, pdef.input_unit
        return value, target

    # -- editing ------------------------------------------------------------

    def _pdef_for(self, dotpath: str) -> ParameterDef:
        """The schema entry for *dotpath* (delegate uses it to choose the editor)."""
        assert self._sensor is not None  # editing is disabled without a sensor
        return self._sensor.parameter_def(dotpath)

    def _input_value_for(self, dotpath: str) -> Any:
        """The row's current value **in its display unit** (seeds the inline editor).

        Entry and display are kept symmetric (owner feedback 2026-07-13): the editor
        opens showing the same number the row shows, and :meth:`_commit_edit` writes it
        back through the same unit — so what you type is what you read. With no
        display-unit override this is the plain input-unit value (unchanged).
        """
        assert self._sensor is not None
        pdef = self._sensor.parameter_def(dotpath)
        value, _unit = self._display_value_and_unit(self._sensor, dotpath, pdef)
        return value

    def _commit_edit(self, dotpath: str, value: Any) -> None:
        """Apply one edit: validate on a clone, then ``sensor.set`` if accepted.

        The live sensor is mutated by exactly one ``set`` call, and only for a value
        the API accepts. Validation runs first on a throwaway clone so a rejected
        value leaves the live sensor — and therefore the displayed tree — untouched
        (verified by the edit-reject test via the public API). Rejections surface
        inline and in a modal; unexpected errors get a traceback dialog (Rules 15/17).

        The typed number is interpreted in the row's **display unit** (owner feedback
        2026-07-13): when the row carries a display-unit override the value is written
        with ``unit=<display_unit>`` so the API performs the single Rule-2 conversion
        (type 550 into a km-displaying row → 550000 m canonical). With no override the
        value is written unit-less, exactly as before.
        """
        sensor = self._sensor
        if sensor is None:
            return

        unit = self._display_units.get(dotpath)
        pdef = sensor.parameter_def(dotpath)
        write_unit = unit if (unit is not None and unit != pdef.input_unit) else None

        trial = sensor.clone()
        try:
            self._set_on(trial, dotpath, value, write_unit)
            # Force a full resolve on the clone: bounds/enum/type checks and
            # consistency-group validation all fire here (not at set() time).
            trial.get_input(dotpath)
        except RadiantError as exc:
            self._reject_edit(dotpath, exc)
            return
        except Exception as exc:  # genuine bug, not a rejected input — never swallow
            UnexpectedErrorDialog(exc, f"Editing “{dotpath}”", self).exec()
            return

        # Accepted: the single mandated API call on the live sensor.
        self._set_on(sensor, dotpath, value, write_unit)
        self._clear_error_state()
        self.populate(sensor)  # refresh value + provenance + any derived rows
        self.parameterEdited.emit(dotpath)

    @staticmethod
    def _set_on(sensor: Sensor, dotpath: str, value: Any, unit: str | None) -> None:
        """One ``sensor.set`` — with ``unit=`` only when a display-unit override is active."""
        if unit is not None:
            sensor.set(dotpath, value, unit=unit)
        else:
            sensor.set(dotpath, value)

    def _reject_edit(self, dotpath: str, exc: RadiantError) -> None:
        """Show the rejected-edit state inline + modal; the value never sticks."""
        self._set_error_state(dotpath, exc)
        ActionableErrorDialog(exc, dotpath, self).exec()

    def _set_error_state(self, dotpath: str, exc: RadiantError) -> None:
        """Mark *dotpath*'s row rejected (tint + tooltip) and show the banner."""
        self._clear_error_state()
        self._error_dotpath = dotpath
        item = self._items.get(dotpath)
        if item is not None:
            item.setData(1, ERROR_ROLE, True)
            item.setToolTip(1, str(exc))
            self._tree.scrollToItem(item)
            self._tree.setCurrentItem(item)
        what = str(getattr(exc, "what", "") or exc)
        action = str(getattr(exc, "action", "") or "")
        leaf = dotpath.split(".", 1)[1] if "." in dotpath else dotpath
        summary = f"{leaf}: {what}"
        if action:
            summary = f"{summary} — {action}"
        self._error_banner.setText(summary)
        self._error_banner.setVisible(True)

    def _clear_error_state(self) -> None:
        """Drop any rejected-edit tint/tooltip and hide the banner."""
        if self._error_dotpath is not None:
            item = self._items.get(self._error_dotpath)
            if item is not None:
                item.setData(1, ERROR_ROLE, None)
                item.setToolTip(1, "")
            self._error_dotpath = None
        self._error_banner.clear()
        self._error_banner.setVisible(False)

    # -- context menu -------------------------------------------------------

    def _show_context_menu(self, pos: QPoint) -> None:
        """Right-click menu on a leaf row: Copy dot-path / Explain / Reset (§4.3)."""
        item = self._tree.itemAt(pos)
        if item is None:
            return
        dotpath = item.data(0, _DOTPATH_ROLE)
        if not dotpath:  # a namespace group header, not a parameter
            return
        dotpath = str(dotpath)

        menu = QMenu(self._tree)
        edit_action = menu.addAction("Edit…")
        menu.addSeparator()
        copy_action = menu.addAction("Copy dot-path")
        explain_action = menu.addAction("Explain")
        reset_action = menu.addAction("Reset to Default")
        chosen = menu.exec(self._tree.viewport().mapToGlobal(pos))
        if chosen is None:
            return
        if chosen is edit_action:
            self._open_editor_dialog(dotpath)
        elif chosen is copy_action:
            self._copy_dotpath(dotpath)
        elif chosen is explain_action:
            self._explain(dotpath)
        elif chosen is reset_action:
            self._reset_to_default(dotpath)

    def _on_double_click(self, index: Any) -> None:
        """Open the detail editor when a non-Value column is double-clicked (§4.3).

        The Value column (1) keeps its fast in-place delegate editor; double-clicking
        the Parameter (0) or Source (2) column — for any row, derived or not — opens the
        full :class:`ParameterEditorDialog`. A namespace group header (no dot-path) is
        ignored.
        """
        if index.column() == 1:
            return
        item = self._tree.itemFromIndex(index)
        if item is None:
            return
        dotpath = item.data(0, _DOTPATH_ROLE)
        if not dotpath:  # a namespace group header, not a parameter
            return
        self._open_editor_dialog(str(dotpath))

    def _open_editor_dialog(self, dotpath: str) -> None:
        """Open the full-detail Parameter Editor for *dotpath* (both entry points).

        The dialog owns the value + unit entry, the canonical preview, and the inline
        actionable-error surface; an accepted edit calls back into
        :meth:`_after_dialog_commit`, which refreshes the tree and marks results stale
        exactly as an in-place edit does.
        """
        if self._sensor is None:
            return
        dialog = ParameterEditorDialog(
            self._sensor,
            dotpath,
            self._after_dialog_commit,
            self,
            display_unit=self.display_unit(dotpath),
        )
        dialog.exec()

    def _after_dialog_commit(self, dotpath: str, unit: str | None) -> None:
        """Record the chosen display unit, refresh the tree, and mark results stale.

        The unit the user picked in the Parameter Editor becomes the row's display
        unit (owner feedback 2026-07-13), so the tree afterwards shows the value in
        that unit. ``None`` (a non-numeric parameter carries no unit) leaves the row's
        display unit untouched.
        """
        if self._sensor is None:
            return
        if unit is not None:
            self._display_units[dotpath] = unit
        self._clear_error_state()
        self.populate(self._sensor)
        self.parameterEdited.emit(dotpath)

    def _copy_dotpath(self, dotpath: str) -> None:
        """Put the full dot-path on the clipboard."""
        QApplication.clipboard().setText(dotpath)

    def _explain(self, dotpath: str) -> None:
        """Render ``sensor.explain(dotpath)`` in a themed modal dialog."""
        if self._sensor is None:
            return
        try:
            text = self._sensor.explain(dotpath)
        except Exception as exc:  # never swallow — surface it (Rules 15/17)
            UnexpectedErrorDialog(exc, f"Explaining “{dotpath}”", self).exec()
            return
        ExplainDialog(dotpath, text, self).exec()

    def _reset_to_default(self, dotpath: str) -> None:
        """Reset *dotpath* to its schema default via ``Sensor.reset`` (§4.3).

        ``Sensor.reset`` clears the user/config input so the parameter reverts to
        its default (or is re-derived from a consistency group) on the next resolve.
        Resetting a parameter that had no explicit input is a harmless no-op.
        """
        if self._sensor is None:
            return
        try:
            self._sensor.reset(dotpath)
            self._sensor.get_input(dotpath)  # force resolve; surfaces any error now
        except RadiantError as exc:
            self._reject_edit(dotpath, exc)
            return
        except Exception as exc:
            UnexpectedErrorDialog(exc, f"Resetting “{dotpath}”", self).exec()
            return
        self._clear_error_state()
        self.populate(self._sensor)
        self.parameterEdited.emit(dotpath)

    # -- filtering ----------------------------------------------------------

    def _apply_filter(self, text: str) -> None:
        """Show only rows whose full dot-path contains *text* (case-insensitive).

        A namespace group hides when the query excludes all its children and shows
        (expanded) otherwise; an empty query restores the full tree.
        """
        query = text.strip().lower()
        for i in range(self._tree.topLevelItemCount()):
            group = self._tree.topLevelItem(i)
            visible_children = 0
            for j in range(group.childCount()):
                child = group.child(j)
                dotpath = str(child.data(0, _DOTPATH_ROLE))
                matches = query in dotpath.lower() if query else True
                child.setHidden(not matches)
                visible_children += int(matches)
            group.setHidden(bool(query) and visible_children == 0)
            if query:
                group.setExpanded(True)

    # -- empty / populated state -------------------------------------------

    def _show_empty_state(self) -> None:
        """Show the "no configuration loaded" message; hide + disable the tree."""
        self._tree.setVisible(False)
        self._empty_msg.setVisible(True)
        self._filter.setEnabled(False)

    def _show_tree(self) -> None:
        """Show the populated tree and enable the live filter box."""
        self._empty_msg.setVisible(False)
        self._tree.setVisible(True)
        self._filter.setEnabled(True)
