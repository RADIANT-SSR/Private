"""The configuration manager (arch doc §4.2d, multi-configuration Phase 4c).

The owner's first GUI requirement for studies: *"the user can define the number of
configurations and then name them"* (plan §4 item 1). This dialog is that surface —
create, duplicate, rename, remove, reorder, and pick the baseline — and it is also the
door a plain single-model session walks through to **become** a study: `Add` on a
one-configuration session is what makes the master selector appear.

Above the rows sits the study's **shared grid points** field (CU-213, Phase 4e): the
spectral point count every configuration uses unless its own row overrides it. It is
the number the blank per-row placeholders name, and until Phase 4e no GUI surface could
change it.

**One row per configuration**, in set order, each carrying

* the configuration's stable accent chip (the selector's hue for that slot, §8.1
  ``config_accents``) and its name, with the **baseline** marked;
* its spectral **wavelength-points** override — an integer, or blank to inherit the
  shared default, whose value and meaning the blank row states in grey placeholder
  text (``shared: 500 pts``) so "blank" is never an unexplained empty box;
* a live **status** from ``ConfigurationSet.validate_all()`` — ``OK``, or the failing
  configuration's error *what*-line, with the full what/why/action as its tooltip.
  ``validate_all`` is resolve-only: opening this dialog never runs physics.

**A private working copy.** The dialog edits ``config_set.clone()`` and hands the
window a :class:`~radiant.gui.widgets.configuration_shape_command.ConfigurationShape`
only when the user accepts. Two things follow. First, Cancel is exactly "throw the
clone away" — nothing partially applied, no undo entry. Second, every guard the
analyst meets is the **API's own** — a ninth configuration, a duplicate or empty name,
removing the last one — raised by the real ``ConfigurationSet`` call on the clone and
rendered here as its what/why/action (Rules 15/17). This file duplicates none of that
validation.

**Removing the displayed configuration** is allowed, and the policy is stated in the
dialog: the display moves to the first surviving configuration. That is the model's
own ``remove()`` behaviour, so the dialog states it rather than inventing a second
rule — and it is why the removal is confirmed, never silent.

One widget class per file (Rule 19). All colour/typography comes from the QSS theme
via the object names below (GUI plan §4.9); the only colour named here is the accent
token tuple read from the active theme.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QIntValidator, QPixmap
from PySide6.QtWidgets import (
    QButtonGroup,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from radiant.api.config_set import ConfigurationSet
from radiant.core.exceptions import RadiantError
from radiant.gui.themes import active_theme
from radiant.gui.widgets.configuration_shape_command import ConfigurationShape

if TYPE_CHECKING:
    from collections.abc import Callable

# Accent-chip side in device-independent px — layout geometry, matching the master
# selector's and the value table's chip so all three read as one identity system.
_CHIP_PX = 10

# Row status text for a configuration that resolves cleanly.
_OK_TEXT = "OK"

# The removal policy this dialog implements, stated in the dialog itself so the
# analyst reads it before removing the configuration they are looking at.
REMOVE_DISPLAYED_POLICY = (
    "Removing the displayed configuration moves the display to the first remaining one."
)


class ConfigurationManagerDialog(QDialog):
    """Create, name, order, and validate the configurations of one study.

    Parameters
    ----------
    config_set:
        The session's live set. It is **not** mutated: the dialog clones it and the
        caller applies :meth:`shape` after an accepted dialog.
    parent:
        The owning widget, if any.
    """

    def __init__(self, config_set: ConfigurationSet, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._working: ConfigurationSet = config_set.clone()
        self._selected: str = self._working.active
        self._rebuilding: bool = False
        self._rows: list[str] = []
        self._points_editors: dict[str, QLineEdit] = {}
        self._status_labels: dict[str, QLabel] = {}
        self._name_buttons: dict[str, QPushButton] = {}

        self.setObjectName("configurationManagerDialog")
        self.setWindowTitle("Configurations")
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 14)
        layout.setSpacing(10)

        self._build_header(layout)
        self._build_shared_points(layout)
        self._build_table(layout)
        self._build_actions(layout)
        self._build_error_area(layout)
        self._build_note(layout)
        self._build_buttons(layout)
        self._rebuild()

    # -- construction -------------------------------------------------------

    def _build_header(self, layout: QVBoxLayout) -> None:
        """What the dialog is, and the cap it enforces."""
        title = QLabel(
            f"A study holds up to {ConfigurationSet.MAX_CONFIGS} configurations of the "
            "same model. Shared parameters have one value for all of them; configured "
            "parameters have one value each.",
            self,
        )
        title.setObjectName("configManagerIntro")
        title.setWordWrap(True)
        layout.addWidget(title)

    def _build_shared_points(self, layout: QVBoxLayout) -> None:
        """The study-wide spectral grid point count, above the per-row overrides (CU-213).

        Every blank per-row box states this number in its placeholder, so the dialog was
        showing a value it could not edit — the shared default was reachable only through
        the YAML editor or the console. This is that one missing control; the per-row
        boxes below still override it configuration by configuration.
        """
        row = QHBoxLayout()
        row.setSpacing(8)
        label = QLabel("Shared grid points", self)
        label.setObjectName("configManagerHeading")
        editor = QLineEdit(self)
        editor.setObjectName("configManagerSharedPoints")
        editor.setValidator(QIntValidator(1, 1_000_000, editor))
        editor.setToolTip(
            "Spectral grid points every configuration uses unless its own row overrides "
            "it. Trading evaluation cost against spectral resolution for the whole study."
        )
        editor.editingFinished.connect(self._commit_shared_points)
        row.addWidget(label, 0)
        row.addWidget(editor, 0)
        row.addStretch(1)
        layout.addLayout(row)
        self._shared_points_editor = editor

    def _build_table(self, layout: QVBoxLayout) -> None:
        """The column headings plus the (rebuilt-on-change) row grid."""
        headings = QGridLayout()
        headings.setHorizontalSpacing(10)
        headings.setColumnStretch(1, 1)
        headings.setColumnStretch(4, 2)
        columns = ((1, "Configuration"), (2, "Baseline"), (3, "Grid points"), (4, "Status"))
        for column, text in columns:
            label = QLabel(text, self)
            label.setObjectName("configManagerHeading")
            headings.addWidget(label, 0, column)
        layout.addLayout(headings)

        self._grid = QGridLayout()
        self._grid.setHorizontalSpacing(10)
        self._grid.setVerticalSpacing(6)
        self._grid.setColumnStretch(1, 1)
        self._grid.setColumnStretch(4, 2)
        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        layout.addLayout(self._grid)

    def _build_actions(self, layout: QVBoxLayout) -> None:
        """The CRUD / order / baseline button row (all act on the selected row)."""
        row = QHBoxLayout()
        row.setSpacing(6)
        self._action_buttons: dict[str, QPushButton] = {}
        for key, text, handler in (
            ("add", "Add", self._on_add),
            ("duplicate", "Duplicate", self._on_duplicate),
            ("rename", "Rename", self._on_rename),
            ("remove", "Remove", self._on_remove),
            ("up", "Move Up", self._on_move_up),
            ("down", "Move Down", self._on_move_down),
            ("baseline", "Set as Baseline", self._on_set_baseline),
        ):
            button = QPushButton(text, self)
            button.setObjectName("configManagerAction")
            button.clicked.connect(handler)
            row.addWidget(button)
            self._action_buttons[key] = button
        row.addStretch(1)
        layout.addLayout(row)

    def _build_error_area(self, layout: QVBoxLayout) -> None:
        """The inline, themed what/why/action area (hidden until an action is refused)."""
        frame = QFrame(self)
        frame.setObjectName("paramEditorError")
        frame_layout = QVBoxLayout(frame)
        frame_layout.setContentsMargins(12, 10, 12, 10)
        frame_layout.setSpacing(6)

        header = QLabel("Refused", frame)
        header.setObjectName("errorDialogHeader")
        header.setWordWrap(True)
        frame_layout.addWidget(header)

        self._error_form = QFormLayout()
        self._error_form.setSpacing(4)
        frame_layout.addLayout(self._error_form)

        frame.setVisible(False)
        layout.addWidget(frame)
        self._error_frame = frame

    def _build_note(self, layout: QVBoxLayout) -> None:
        """The standing policy note plus the running status line."""
        note = QLabel(REMOVE_DISPLAYED_POLICY, self)
        note.setObjectName("configManagerNote")
        note.setWordWrap(True)
        layout.addWidget(note)

        status = QLabel("", self)
        status.setObjectName("configManagerStatus")
        status.setWordWrap(True)
        layout.addWidget(status)
        self._status_line = status

    def _build_buttons(self, layout: QVBoxLayout) -> None:
        """OK (hand the shape to the window) / Cancel (discard the working copy)."""
        buttons = QDialogButtonBox(self)
        cancel = buttons.addButton("Cancel", QDialogButtonBox.ButtonRole.RejectRole)
        cancel.clicked.connect(self.reject)
        ok = buttons.addButton("OK", QDialogButtonBox.ButtonRole.AcceptRole)
        ok.clicked.connect(self.accept)
        layout.addWidget(buttons)
        self._buttons = buttons

    # -- rendering ----------------------------------------------------------

    def _rebuild(self) -> None:
        """Redraw every row from the working set, then re-run ``validate_all``."""
        self._rebuilding = True
        while self._grid.count():
            item = self._grid.takeAt(0)
            widget = item.widget()
            if widget is None:
                continue
            if isinstance(widget, QPushButton):
                self._group.removeButton(widget)
            widget.setParent(None)
            widget.deleteLater()
        self._points_editors.clear()
        self._status_labels.clear()
        self._name_buttons.clear()

        names = self._working.names()
        self._rows = list(names)
        if self._selected not in names:
            self._selected = self._working.active
        accents = active_theme().config_accents
        shared_points = self._working.wavelength_points()
        # ``wavelength_points()`` always reports the count *in force* (never None), so
        # the shared field is never blank and "blank" carries no meaning here — unlike a
        # per-row box, where blank means "inherit".
        self._shared_points_editor.setText("" if shared_points is None else str(shared_points))

        for row, name in enumerate(names):
            chip = QLabel(self)
            chip.setObjectName("configManagerChip")
            chip.setPixmap(self._accent_chip(accents[row % len(accents)]))

            selector = QPushButton(name, self)
            selector.setObjectName("configurationTab")
            selector.setCheckable(True)
            selector.setChecked(name == self._selected)
            selector.setCursor(Qt.CursorShape.PointingHandCursor)
            selector.setToolTip(f"Select {name!r} for the actions below")
            selector.clicked.connect(lambda _checked=False, n=name: self._select(n))
            self._group.addButton(selector, row)
            self._name_buttons[name] = selector

            baseline = QLabel("baseline" if name == self._working.baseline else "", self)
            baseline.setObjectName("configManagerBaseline")

            points = QLineEdit(self)
            points.setObjectName("configManagerPoints")
            points.setValidator(QIntValidator(0, 1_000_000, points))
            override = self._working.wavelength_points(name)
            points.setText("" if override is None else str(override))
            points.setPlaceholderText(f"shared: {shared_points} pts")
            points.setToolTip(
                "Spectral grid points for this configuration. Leave blank to use the "
                f"study's shared default of {shared_points} points."
            )
            points.editingFinished.connect(lambda n=name: self._commit_points(n))
            self._points_editors[name] = points

            status = QLabel("", self)
            status.setObjectName("configManagerRowStatus")
            status.setWordWrap(True)
            self._status_labels[name] = status

            self._grid.addWidget(chip, row, 0)
            self._grid.addWidget(selector, row, 1)
            self._grid.addWidget(baseline, row, 2)
            self._grid.addWidget(points, row, 3)
            self._grid.addWidget(status, row, 4)

        self._rebuilding = False
        self._refresh_status()

    def _refresh_status(self) -> None:
        """Re-run the resolve-only ``validate_all`` and paint each row's status.

        No physics: ``validate_all`` materializes each configuration and resolves it,
        which is exactly what a per-row "will this configuration run?" light needs and
        nothing more. A failing row shows the error's *what* line — the sentence that
        names the offending parameter — with the whole what/why/action on hover.
        """
        for name, error in self._working.validate_all().items():
            label = self._status_labels.get(name)
            if label is None:  # pragma: no cover - names come from the same set
                continue
            if error is None:
                label.setText(_OK_TEXT)
                label.setProperty("state", "ok")
                label.setToolTip("")
            else:
                label.setText(_what(error))
                label.setProperty("state", "error")
                label.setToolTip(_full_text(error))
            label.style().unpolish(label)
            label.style().polish(label)

    @staticmethod
    def _accent_chip(colour: str) -> QPixmap:
        """A small solid square of *colour* — the configuration's identity chip."""
        pixmap = QPixmap(_CHIP_PX, _CHIP_PX)
        pixmap.fill(QColor(colour))
        return pixmap

    def _select(self, name: str) -> None:
        """Make *name* the row the action buttons act on."""
        self._selected = name
        for row_name, button in self._name_buttons.items():
            button.setChecked(row_name == name)

    # -- actions ------------------------------------------------------------

    def _guarded(self, call: Callable[[], None], announce: str, select: str | None = None) -> bool:
        """Run one ``ConfigurationSet`` call, rendering its refusal inline.

        Returns True when the call succeeded, in which case the rows are redrawn from
        the working set, *select* (when given) becomes the selected row, and *announce*
        becomes the status line. The API is the only validator: this method never
        decides *whether* an action is legal, only how a refusal reads.
        """
        try:
            call()
        except RadiantError as exc:
            self._show_error(exc)
            return False
        self._clear_error()
        if select is not None:
            self._selected = select
        self._rebuild()
        self._status_line.setText(announce)
        return True

    def _on_add(self) -> None:
        """Add a configuration — the action that turns a plain session into a study."""
        name = self._ask_name("Add configuration", "Name for the new configuration:", "")
        if name is None:
            return
        self._guarded(lambda: self._working.add(name), f"Added {name!r}", select=name)

    def _on_duplicate(self) -> None:
        """Copy the selected configuration, including its configured values and grid."""
        source = self._selected
        name = self._ask_name(
            "Duplicate configuration",
            f"Name for the copy of {source!r}:",
            f"{source} copy",
        )
        if name is None:
            return
        self._guarded(
            lambda: self._working.add(name, copy_from=source),
            f"Duplicated {source!r} as {name!r}",
            select=name,
        )

    def _on_rename(self) -> None:
        """Rename the selected configuration, keeping its position and values."""
        old = self._selected
        name = self._ask_name("Rename configuration", f"New name for {old!r}:", old)
        if name is None or name == old:
            return
        self._guarded(
            lambda: self._working.rename(old, name),
            f"Renamed {old!r} to {name!r}",
            select=name,
        )

    def _on_remove(self) -> None:
        """Remove the selected configuration, after stating what it costs.

        The confirmation names the configured values that go with it and, when the
        removed configuration is the displayed one, the survivor the display moves
        to (:data:`REMOVE_DISPLAYED_POLICY`).
        """
        name = self._selected
        n_configured = len(self._working.configured())
        detail = f"Its values for {n_configured} configured parameter(s) are discarded."
        if name == self._working.active:
            detail = f"{detail} {REMOVE_DISPLAYED_POLICY}"
        answer = QMessageBox.question(
            self,
            "Remove configuration",
            f"Remove configuration {name!r}?\n\n{detail}",
            QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if answer != QMessageBox.StandardButton.Ok:
            return
        if self._guarded(lambda: self._working.remove(name), f"Removed {name!r}"):
            self._selected = self._working.active
            self._rebuild()
            self._status_line.setText(f"Removed {name!r} — displaying {self._working.active!r}")

    def _on_move_up(self) -> None:
        self._move(-1)

    def _on_move_down(self) -> None:
        self._move(+1)

    def _move(self, delta: int) -> None:
        """Move the selected configuration *delta* places, values moving with it."""
        order = list(self._working.names())
        index = order.index(self._selected)
        target = index + delta
        if not 0 <= target < len(order):
            self._status_line.setText(f"{self._selected!r} is already at the end of the order")
            return
        order[index], order[target] = order[target], order[index]
        self._guarded(lambda: self._working.reorder(order), f"Moved {self._selected!r}")

    def _on_set_baseline(self) -> None:
        """Make the selected configuration the comparison baseline."""
        name = self._selected

        def _assign() -> None:
            self._working.baseline = name

        self._guarded(_assign, f"{name!r} is now the baseline")

    def _commit_points(self, name: str) -> None:
        """Write one row's wavelength-point override (blank clears it back to shared)."""
        if self._rebuilding:
            # Redrawing the rows moves focus off the editor being destroyed, which
            # re-emits editingFinished; that echo must not re-enter the write path.
            return
        editor = self._points_editors.get(name)
        if editor is None:  # pragma: no cover - rows and editors are built together
            return
        text = editor.text().strip()
        points = int(text) if text else None
        if points == self._working.wavelength_points(name):
            return
        self._guarded(
            lambda: self._working.set_wavelength_points(name, points),
            f"{name!r} spectral grid: {'shared default' if points is None else f'{points} points'}",
        )

    def _commit_shared_points(self) -> None:
        """Write the study-wide grid point count (CU-213), then redraw the placeholders.

        Blank is *not* a clear here: unlike a per-row override there is no "inherit"
        state above the shared default, and ``wavelength_points()`` always reports a
        concrete count. A cleared box therefore restores the current value rather than
        writing ``None`` — the field states a number, so it always shows one.

        The write goes through the same :meth:`_guarded` path as every other action, so
        the API's own refusal (a non-positive count) renders as its what/why/action, and
        the rebuild refreshes every blank per-row placeholder to the new number.
        """
        if self._rebuilding:
            return
        current = self._working.wavelength_points()
        text = self._shared_points_editor.text().strip()
        if not text:
            self._shared_points_editor.setText("" if current is None else str(current))
            return
        points = int(text)
        if points == current:
            return
        self._guarded(
            lambda: self._working.set_wavelength_points(None, points),
            f"Shared spectral grid: {points} points",
        )

    def _ask_name(self, title: str, prompt: str, seed: str) -> str | None:
        """Ask for a configuration name; ``None`` when the user cancels.

        An empty or blank answer is *not* filtered here — it goes to the API, which
        refuses it with the reason a name matters (Rule 15), so the analyst reads one
        vocabulary of refusals rather than two.
        """
        text, ok = QInputDialog.getText(self, title, prompt, QLineEdit.EchoMode.Normal, seed)
        if not ok:
            return None
        return text

    # -- error rendering ----------------------------------------------------

    def _show_error(self, exc: RadiantError) -> None:
        """Render a refusal's what/why/action inline; the dialog stays open."""
        while self._error_form.rowCount():
            self._error_form.removeRow(0)
        self._add_row("What", _what(exc))
        why = str(getattr(exc, "why", "") or "")
        action = str(getattr(exc, "action", "") or "")
        if why:
            self._add_row("Why", why)
        if action:
            self._add_row("Action", action)
        self._error_frame.setVisible(True)

    def _add_row(self, label: str, text: str) -> None:
        """One what/why/action line in the inline refusal area."""
        caption = QLabel(label, self._error_frame)
        caption.setObjectName("errorDialogLabel")
        value = QLabel(text, self._error_frame)
        value.setObjectName("errorDialogValue")
        value.setWordWrap(True)
        value.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self._error_form.addRow(caption, value)

    def _clear_error(self) -> None:
        """Hide the inline refusal area and drop its fields."""
        while self._error_form.rowCount():
            self._error_form.removeRow(0)
        self._error_frame.setVisible(False)

    # -- accessors (tests / host) ------------------------------------------

    def shape(self) -> ConfigurationShape:
        """The study shape the working copy now describes (what ``OK`` hands back)."""
        return ConfigurationShape.of(self._working)

    @property
    def names(self) -> tuple[str, ...]:
        """The configuration names the dialog currently shows, in order."""
        return tuple(self._rows)

    @property
    def selected(self) -> str:
        """The configuration the action buttons act on."""
        return self._selected

    def select(self, name: str) -> None:
        """Select *name*'s row (the programmatic form of clicking it)."""
        self._select(name)

    def points_editor(self, name: str) -> QLineEdit:
        """*name*'s wavelength-points editor (tests drive these)."""
        return self._points_editors[name]

    @property
    def shared_points_editor(self) -> QLineEdit:
        """The study-wide grid-point editor above the rows (CU-213)."""
        return self._shared_points_editor

    def status_text(self, name: str) -> str:
        """*name*'s rendered validate_all status (``OK`` or the error's what-line)."""
        return self._status_labels[name].text()

    def action_button(self, key: str) -> QPushButton:
        """One of the CRUD buttons by key (``add``/``duplicate``/…)."""
        return self._action_buttons[key]

    @property
    def error_frame(self) -> QFrame:
        """The inline refusal area (visible only after a refused action)."""
        return self._error_frame

    @property
    def status_line(self) -> QLabel:
        """The running "what just happened" line under the buttons."""
        return self._status_line

    @property
    def buttons(self) -> QDialogButtonBox:
        """The OK / Cancel box."""
        return self._buttons


def _what(exc: RadiantError) -> str:
    """A RADIANT error's *what* line, or its whole text when it carries none."""
    return str(getattr(exc, "what", "") or exc)


def _full_text(exc: RadiantError) -> str:
    """The whole what/why/action text of an error, for a tooltip."""
    return str(exc)


__all__ = ["REMOVE_DISPLAYED_POLICY", "ConfigurationManagerDialog"]
