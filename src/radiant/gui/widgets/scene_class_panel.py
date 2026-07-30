"""Scene-class steering for the Geometry screen — derived chip + assertion + relevance.

:class:`SceneClassPanel` is the top card of the Geometry stage's **Inputs** tab
(arch doc §4.4), and it is the GUI's *mission-type* entry point (ADR-0011
decision 8 / Geometry-Flexibility plan Phase 4). It shows three things about the
scene class, in the order the analyst needs them:

1. **Derived** — after each evaluation, the class the altitudes actually produced,
   read verbatim from ``stage_outputs["geometry"]`` (``scene_class`` plus its two
   pieces ``observer_class`` / ``target_class``). The stage is the single source
   of truth; this panel never re-derives a band from an altitude. Before the first
   evaluation the chip shows a neutral placeholder — never a guess.
2. **Asserted** — the optional ``geometry.scene_class`` enum parameter (``auto`` =
   not asserted, plus the nine class keys). Asserting a class steers the defaults
   up front *and* is validated against the derivation at the next evaluate: a
   disagreement raises the stage's ``GeometrySpecificationError`` (the CU-093
   redundant-entry pattern that catches a wrong-magnitude altitude — 600 m where
   600 km was meant). It is **never required**.
3. **Relevance** — the metrics whose *default* selection the displayed class turns
   off, read through the :mod:`radiant.api.scene_relevance` bridge (guardrail G3:
   one declarative map, re-exported, never transcribed GUI-side) and rendered with
   the human labels of :mod:`radiant.gui.metric_format`. A ground target drops the
   target-plane sample distances (GSD is the right answer there); an air or space
   target drops the whole ground-projection family, which has no ground plane at
   the target to project onto. These are **defaults**: an explicitly set
   ``performance.metrics.*`` group flag always wins (the Gap 96 override
   semantics), which the card says on its face. With no class known — no
   evaluation yet and no assertion — the relevance block shows nothing rather than
   guessing a class.

Full per-input mission-type gating (which *inputs* a scene class dims) is Gap 85
and is **not** implemented here.

**Schema-driven, one API call per edit (Gap 70 / R-API).** The assertion field is
the shared :class:`~radiant.gui.widgets.field_row.FieldRow`; editing it opens the
shared :class:`~radiant.gui.widgets.parameter_editor_dialog.ParameterEditorDialog`,
so a commit is exactly one ``sensor.set`` validated on a throwaway clone first (a
rejected value never touches the live sensor) and each accepted edit re-emits
:attr:`parameterEdited` so results go stale and the host re-evaluates — the
identical discipline as every other Inputs form. The enum choices come from the
live schema through the dialog, never from a transcribed list here.

**Mismatch in context.** :meth:`highlight_error` tints the card
(``[state="conflict"]``, the same property-based QSS pattern as
``geoModeFamily``) and shows the error's *what* line beside the chip, so the
operator sees the contradiction where the assertion was made — the actionable
what/why/action still surfaces in the window dialog and the Messages panel; this
card adds only the in-place locator and invents no GUI-side validation.

One widget class per file (Rule 19). All colour/typography comes from the QSS
theme via object names (GUI plan §4.9); this file holds no colour/font literal.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, Final

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from radiant.api.scene_relevance import SCENE_CLASS_KEYS, default_off_metrics
from radiant.core.exceptions import RadiantError
from radiant.gui.dialog_lifetime import exec_dialog
from radiant.gui.metric_format import METRIC_DISPLAY_LABELS, metric_display_label
from radiant.gui.param_format import field_display_text, safe_provenance
from radiant.gui.widgets.field_row import UNSET as _UNSET
from radiant.gui.widgets.field_row import FieldRow
from radiant.gui.widgets.parameter_editor_dialog import ParameterEditorDialog

if TYPE_CHECKING:
    from radiant.api.sensor import Sensor

#: The optional scene-class assertion parameter (ADR-0011 decision 8).
SCENE_CLASS_PARAM: Final[str] = "geometry.scene_class"

#: The ``stage_outputs["geometry"]`` keys this panel reads — the derived label and
#: its two pieces. Read verbatim; the panel never re-derives a band (arch doc §6.3:
#: the stage is the single source of truth).
DERIVED_KEYS: Final[tuple[str, str, str]] = ("scene_class", "observer_class", "target_class")

_TITLE: Final[str] = "Scene class — derived label & optional assertion"
_PLACEHOLDER: Final[str] = "Scene: evaluate to derive"
_ASSERTION_LABEL: Final[str] = "Assert scene class"
_RELEVANCE_HEADING: Final[str] = "Off by default for this scene class"
_OVERRIDE_NOTE: Final[str] = (
    "Defaults only — an explicitly set performance.metrics.* group flag always wins, "
    "so selecting a group yourself computes it whatever the scene class."
)

# The context keys ``geometry.scene_class.check_scene_class_assertion`` puts on its
# GeometrySpecificationError (asserted vs. derived). Matching on the structured
# context — not on prose — is what routes the mismatch to this card.
_ASSERTION_CONTEXT_KEYS: Final[frozenset[str]] = frozenset({"asserted", "derived"})


def names_scene_class_assertion(what: str, context: Mapping[str, Any] | None) -> bool:
    """Whether a geometry error names the ``geometry.scene_class`` assertion.

    True for the two errors ``check_scene_class_assertion`` raises: the
    asserted-vs-derived mismatch (whose ``context`` carries both keys) and the
    defence-in-depth "not a scene class" bounds error (whose ``what`` names the
    parameter). Anything else is not this card's conflict — the window then leaves
    the tint alone, so an unrelated failure never hijacks the panel.
    """
    if context is not None and set(context) >= _ASSERTION_CONTEXT_KEYS:
        return True
    return SCENE_CLASS_PARAM in what


def off_metric_labels(scene_class: str | None) -> tuple[str, ...]:
    """Human display labels of the metrics *scene_class* turns off by default.

    The set itself comes from the :mod:`radiant.api.scene_relevance` bridge (the one
    declarative map, guardrail G3); only the wording is view-layer
    (:func:`radiant.gui.metric_format.metric_display_label`, so no raw registry key
    ever reaches the screen). ``None`` — no class known — returns an empty tuple:
    the panel shows nothing rather than guessing the ground rule the metric layer
    falls back to. Order follows ``METRIC_DISPLAY_LABELS`` (the registry's physics
    reading order), with any unlabelled key trailing alphabetically.
    """
    if scene_class is None:
        return ()
    rank = {key: index for index, key in enumerate(METRIC_DISPLAY_LABELS)}
    unranked = len(rank)
    ordered = sorted(
        default_off_metrics(scene_class), key=lambda key: (rank.get(key, unranked), key)
    )
    return tuple(metric_display_label(key) for key in ordered)


class SceneClassPanel(QWidget):
    """The Geometry Inputs tab's scene-class card: derived chip, assertion, relevance.

    Parameters
    ----------
    parent:
        The owning widget, if any.

    Signals
    -------
    parameterEdited(str):
        Emitted with the dot-path after an accepted assertion edit, so the host
        window refreshes the parameter tree, marks results stale and schedules a
        re-evaluation — the same contract as every other Inputs form.
    """

    parameterEdited = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("sceneClassPanel")

        self._sensor: Sensor | None = None
        self._display_units: dict[str, str] = {}
        self._derived: str | None = None
        self._derived_observer: str | None = None
        self._derived_target: str | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        # The card. A bare QWidget paints no QSS background/border unless
        # styled-background is on; the panel fill and the conflict tint need it.
        self._card = QWidget(self)
        self._card.setObjectName("sceneClassCard")
        self._card.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._card.setProperty("state", "normal")
        box = QVBoxLayout(self._card)
        box.setContentsMargins(12, 10, 12, 10)
        box.setSpacing(6)

        title = QLabel(_TITLE, self._card)
        title.setObjectName("sceneClassTitle")
        title.setWordWrap(True)
        box.addWidget(title)

        self._chip = QLabel(_PLACEHOLDER, self._card)
        self._chip.setObjectName("sceneClassChip")
        self._chip.setWordWrap(True)
        box.addWidget(self._chip)

        # The mismatch's what-line, shown beside the chip only while a conflict is on.
        self._conflict = QLabel("", self._card)
        self._conflict.setObjectName("sceneClassConflict")
        self._conflict.setWordWrap(True)
        self._conflict.setVisible(False)
        box.addWidget(self._conflict)

        self._assertion_row = FieldRow(SCENE_CLASS_PARAM, _ASSERTION_LABEL, self._open_editor)
        box.addWidget(self._assertion_row)

        # The relevance block: heading + one label per off-by-default metric + the
        # override note. Hidden as a whole while no class is known.
        self._relevance = QWidget(self._card)
        relevance_box = QVBoxLayout(self._relevance)
        relevance_box.setContentsMargins(0, 0, 0, 0)
        relevance_box.setSpacing(3)
        relevance_heading = QLabel(_RELEVANCE_HEADING, self._relevance)
        relevance_heading.setObjectName("sceneClassRelevanceHeading")
        relevance_box.addWidget(relevance_heading)
        self._relevance_layout = relevance_box
        self._relevance_items: list[QLabel] = []
        self._note = QLabel(_OVERRIDE_NOTE, self._relevance)
        self._note.setObjectName("sceneClassNote")
        self._note.setWordWrap(True)
        relevance_box.addWidget(self._note)
        self._relevance.setVisible(False)
        box.addWidget(self._relevance)

        layout.addWidget(self._card)

    # -- binding / refresh --------------------------------------------------

    def bind_sensor(self, sensor: Sensor | None, display_units: dict[str, str]) -> None:
        """Bind the live *sensor* and the shared *display_units* store, then refresh.

        The derived label is dropped on **every** bind, not only on a ``None``
        sensor: a derivation belongs to the result of the sensor that produced it, so
        a config swap (File → New, a configuration switch) must not leave the previous
        scene's class on screen until the next evaluation lands. The chip returns to
        its placeholder and the relevance preview follows whatever assertion the new
        sensor carries.
        """
        self._sensor = sensor
        self._display_units = display_units
        self._derived = None
        self._derived_observer = None
        self._derived_target = None
        self.refresh()

    def refresh(self) -> None:
        """Re-read the assertion field and re-render the chip + relevance list.

        Does **not** touch the conflict tint — the window owns that lifecycle (set on
        a failed evaluate, cleared on a clean run), so a value re-sync during a
        conflict does not wipe the highlight the user needs to see.
        """
        self._assertion_row.set_value_text(self._value_text(SCENE_CLASS_PARAM))
        self._render_chip()
        self._render_relevance()

    def populate(self, geometry_outputs: Mapping[str, Any]) -> None:
        """Adopt the derived class from ``stage_outputs["geometry"]`` (one evaluation).

        Values are taken verbatim — the panel displays what the stage published and
        derives nothing of its own (arch doc §6.3). Outputs without a
        ``scene_class`` key (a partial fixture) leave the placeholder in place.
        """
        derived, observer, target = (geometry_outputs.get(key) for key in DERIVED_KEYS)
        self._derived = str(derived) if derived is not None else None
        self._derived_observer = str(observer) if observer is not None else None
        self._derived_target = str(target) if target is not None else None
        self._render_chip()
        self._render_relevance()

    # -- rendering ----------------------------------------------------------

    def _render_chip(self) -> None:
        """Write the chip text — what the stage derived, and what (if anything) was asserted.

        The derived label always leads when one exists: it is the class the chain
        actually ran with. An assertion is reported alongside it, agreeing or not —
        never *instead* of it, so an asserted class can never masquerade as a
        derivation. With no result yet, an assertion shows on its own, flagged as
        still-unvalidated.
        """
        asserted = self.asserted_class()
        if self._derived is None:
            self._chip.setText(
                _PLACEHOLDER
                if asserted is None
                else f"Scene: {asserted} — asserted (validated at the next evaluate)"
            )
            return
        derived = f"Scene: {self._describe(self._derived)} — derived"
        if asserted is None:
            self._chip.setText(derived)
        elif asserted == self._derived:
            self._chip.setText(f"{derived}; assertion agrees")
        else:
            self._chip.setText(f"{derived}; asserted {asserted}")

    def _describe(self, scene_class: str) -> str:
        """``"ground → air (ground_to_air)"`` when both pieces are published."""
        if self._derived_observer and self._derived_target:
            return f"{self._derived_observer} → {self._derived_target} ({scene_class})"
        return scene_class

    def _render_relevance(self) -> None:
        """Rebuild the off-by-default metric list for the displayed class."""
        labels = off_metric_labels(self.displayed_class())
        for item in self._relevance_items:
            self._relevance_layout.removeWidget(item)
            item.setParent(None)
            item.deleteLater()
        self._relevance_items = []
        if not labels:
            self._relevance.setVisible(False)
            return
        # Insert above the trailing override note (index 0 is the heading).
        for offset, text in enumerate(labels):
            item = QLabel(f"• {text}", self._relevance)
            item.setObjectName("sceneClassRelevanceItem")
            item.setWordWrap(True)
            self._relevance_layout.insertWidget(1 + offset, item)
            self._relevance_items.append(item)
        self._relevance.setVisible(True)

    # -- value reads (public Sensor surface only) ---------------------------

    def _value_text(self, dotpath: str) -> str:
        """The value text for *dotpath* in its display unit (— with no sensor)."""
        sensor = self._sensor
        if sensor is None:
            return _UNSET
        return field_display_text(sensor, dotpath, self._display_units)

    def asserted_class(self) -> str | None:
        """The user's ``geometry.scene_class`` assertion, or ``None`` when unset.

        "Unset" is read from **provenance**, not from a transcribed sentinel: the
        parameter still at its schema default asserts nothing (the ``auto``
        sentinel is the schema's, and stays the schema's). A value that is not one
        of the nine class keys also reads as no assertion — the schema enum rejects
        it at set time, and the stage's own bounds error reports it.
        """
        sensor = self._sensor
        if sensor is None:
            return None
        provenance = safe_provenance(sensor, SCENE_CLASS_PARAM)
        if provenance is None or provenance == "default":
            return None
        try:
            value = str(sensor.get(SCENE_CLASS_PARAM))
        except (KeyError, RadiantError):
            return None
        return value if value in SCENE_CLASS_KEYS else None

    def displayed_class(self) -> str | None:
        """The class the relevance preview describes: asserted if set, else derived."""
        return self.asserted_class() or self._derived

    @property
    def derived_class(self) -> str | None:
        """The class the last evaluation derived (``None`` before the first result)."""
        return self._derived

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

    # -- conflict highlight -------------------------------------------------

    def set_conflict(self, on: bool) -> None:
        """Tint the card as conflicting (the ``geoModeFamily`` pattern) or clear it.

        Clearing also drops the what-line, so a stale mismatch message can never
        outlive the tint that explains it.
        """
        self._card.setProperty("state", "conflict" if on else "normal")
        if not on:
            self._conflict.setText("")
            self._conflict.setVisible(False)
        # Re-polish so the property-based QSS rule repaints.
        style = self._card.style()
        style.unpolish(self._card)
        style.polish(self._card)

    def set_conflict_message(self, what: str) -> None:
        """Show the error's *what* line beside the chip (empty hides the label)."""
        self._conflict.setText(what)
        self._conflict.setVisible(bool(what))

    def highlight_error(self, what: str, context: Mapping[str, Any] | None) -> bool:
        """Tint + explain when the error names the scene-class assertion.

        Returns whether the error was this card's (so the host can decide to
        navigate). An error that is not the assertion's leaves the tint untouched —
        clearing is the window's separate, explicit action.
        """
        if not names_scene_class_assertion(what, context):
            return False
        self.set_conflict(True)
        self.set_conflict_message(what)
        return True

    def clear_highlight(self) -> None:
        """Clear the conflict tint and its what-line (a clean run / an edit)."""
        self.set_conflict(False)

    # -- accessors (tests) --------------------------------------------------

    def chip_text(self) -> str:
        """The derived/asserted chip's current text."""
        return self._chip.text()

    def conflict_text(self) -> str:
        """The mismatch what-line currently shown (empty when there is none)."""
        return self._conflict.text()

    def is_conflicting(self) -> bool:
        """True while the card carries the conflict tint."""
        return bool(self._card.property("state") == "conflict")

    def relevance_labels(self) -> tuple[str, ...]:
        """The off-by-default metric labels currently listed, in display order."""
        return tuple(item.text().removeprefix("• ") for item in self._relevance_items)

    def relevance_visible(self) -> bool:
        """Whether the relevance block is shown (hidden while no class is known).

        Asks ``isHidden`` rather than ``isVisible`` so the answer is the panel's own
        show/hide decision, not whether an ancestor happens to be on screen (an
        offscreen test never shows the window).
        """
        return not self._relevance.isHidden()

    @property
    def assertion_row(self) -> FieldRow:
        """The ``geometry.scene_class`` field row (the assertion control)."""
        return self._assertion_row


__all__ = [
    "DERIVED_KEYS",
    "SCENE_CLASS_PARAM",
    "SceneClassPanel",
    "names_scene_class_assertion",
    "off_metric_labels",
]
