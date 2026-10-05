"""Per-element detail editor — the whole of one optical element, in one place (Gap 142).

Why this exists
---------------
A reflective element is two numbers (R and a temperature). A refractive **cavity**
element is up to seven: R1/T1, R2/T2, a substrate *or* an explicit alpha, a
thickness, a temperature. The train table has one value column, so it can show the
first and structurally cannot show the second — a cavity row's value cell is blank, the
thickness has no home anywhere, and a refusal that names ``alpha`` reads as nonsense
because ``alpha`` appears nowhere on screen. All of that is one defect: the table shows
a *projection* of the element, and the hidden part is where the physics lives (owner
report, 2026-10-04 live review).

So the table keeps the **train** — order, names, the derived summary — and this widget
owns the **element**, grouped by physical role rather than by table column.

Two decisions worth stating
---------------------------
**The model is chosen, not inferred.** A refractive entry carrying surface coatings runs
the cavity model; one carrying a single transmittance does not. That is a storage
detail, and it must not be the only place the answer lives — otherwise the only way to
read an element's model is to notice which keys are missing, and the only way to change
it is to know which keys to add. The :class:`ElementModel` selector states it and
switches it, and a switch says what it will cost before it applies.

**Over-specification is made unconstructible, not refused.** The bulk comes from a
named substrate *or* from an explicit alpha — one radio group, never two fields an
operator can both fill. The io parser still refuses the illegal combination (it is the
validation authority and a config can be hand-edited), but through this widget the state
that produces that refusal cannot be reached. A refusal you cannot trigger beats a
refusal worded better.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass
from enum import Enum
from typing import Any, Final

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QRadioButton,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from radiant.api.substrate import REMOVED_ENTRY_KEYS, SubstrateInfo, available_substrates

__all__ = ["ElementDetailEditor", "ElementModel", "model_of_entry"]

#: Keys that make a REFRACTIVE entry a cavity entry. Mirrors the io parser's own
#: predicate; the parser remains the authority, and this is only used to *read* an
#: entry's current model for display.
_CAVITY_KEYS: Final[tuple[str, ...]] = ("R1", "T1", "R2", "T2")

#: Combo entry for "no named substrate" — the custom-material path, not a blank.
#: Names what the operator supplies instead, so an empty picker is not read as an
#: unfilled field.
NO_SUBSTRATE: Final[str] = "— none (α given directly) —"

#: Disabled separator above the tier-B materials in the substrate combo.
FLAGGED_SEPARATOR: Final[str] = "— flagged: class-typical α —"

#: Seeds used when converting a simple element into a cavity one. They are a *guess at
#: the coatings*, not a conversion of them — nothing in a single net transmittance
#: determines two surface coatings plus a bulk — so the UI says so rather than
#: presenting a seeded number as preserved physics.
SEED_THICKNESS_M: Final[float] = 0.005
SEED_SURFACE_R: Final[float] = 0.01

#: Width of a single value field [px] — a scalar, a short path, or a sentinel.
_VALUE_WIDTH: Final[int] = 170


class ElementModel(Enum):
    """The three element models, as the operator chooses between them."""

    REFLECTIVE = "reflective"
    SIMPLE = "simple"
    CAVITY = "cavity"


def model_of_entry(entry: dict[str, Any]) -> ElementModel:
    """Read an entry's current model from the keys it carries."""
    if str(entry.get("transfer_mode", "")).strip().upper() != "REFRACTIVE":
        return ElementModel.REFLECTIVE
    return ElementModel.CAVITY if any(k in entry for k in _CAVITY_KEYS) else ElementModel.SIMPLE


@dataclass(frozen=True)
class _Conversion:
    """What switching to a model will do, stated before it applies."""

    entry: dict[str, Any]
    note: str


def _as_text(value: Any) -> str:
    """Render a stored value for a line edit, without inventing one."""
    if value is None:
        return ""
    if isinstance(value, dict):
        n = len(value.get("wavelength_um", ()))
        return f"spectral ({n} pts)"
    return str(value)


def _parse_cell(text: str) -> Any:
    """Parse an edited cell to float when numeric, else pass the string through.

    The three forms the element schema accepts per quantity are a scalar, a spectral
    CSV path, and an inline table; a path must survive untouched, so anything that is
    not a number is returned as typed rather than rejected here. The io parser owns
    validation.
    """
    stripped = text.strip()
    if not stripped:
        return None
    try:
        return float(stripped)
    except ValueError:
        return stripped


class _Surface(QWidget):
    """One face of a cavity: give R or T, with the other derived (R + T = 1).

    The radio pair is the point. Surfaces are lossless by model rule, so exactly one of
    the two is an input and the other follows; a form with both as fields would invite
    an operator to enter a pair that does not sum to one and then be refused for it.
    """

    edited = Signal()

    def __init__(self, title: str, r_key: str, t_key: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._r_key, self._t_key = r_key, t_key
        self._entry: dict[str, Any] = {}

        self.setObjectName("elementSurfaceCard")
        # A bare QWidget does not paint a stylesheet background or border without this;
        # the card rule applied silently to nothing until it was set.
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        box = QVBoxLayout(self)
        box.setContentsMargins(10, 8, 10, 8)
        box.setSpacing(5)

        head = QHBoxLayout()
        caption = QLabel(title)
        caption.setObjectName("elementSurfaceTitle")
        head.addWidget(caption)
        self._r_radio = QRadioButton(f"specify {r_key}")
        self._t_radio = QRadioButton(f"specify {t_key}")
        self._which = QButtonGroup(self)
        self._which.addButton(self._r_radio, 0)
        self._which.addButton(self._t_radio, 1)
        head.addWidget(self._r_radio)
        head.addWidget(self._t_radio)
        head.addStretch(1)
        box.addLayout(head)

        row = QHBoxLayout()
        self._label = QLabel(r_key)
        self._value = QLineEdit()
        self._value.setPlaceholderText("scalar, CSV path, or table")
        self._value.setMaximumWidth(_VALUE_WIDTH)
        self._browse = QPushButton("CSV…")
        row.addWidget(self._label)
        row.addWidget(self._value)
        row.addWidget(self._browse)
        row.addStretch(1)
        box.addLayout(row)

        self._derived = QLabel()
        self._derived.setObjectName("stagePlotMessage")
        self._derived.setWordWrap(True)
        box.addWidget(self._derived)

        self._value.editingFinished.connect(self.edited)
        self._which.idClicked.connect(self._on_side_changed)

    def bind(self, entry: dict[str, Any]) -> None:
        self._entry = entry
        gives_t = self._t_key in entry and self._r_key not in entry
        (self._t_radio if gives_t else self._r_radio).setChecked(True)
        key = self._t_key if gives_t else self._r_key
        self._label.setText(key)
        self._value.setText(_as_text(entry.get(key)))
        other = self._r_key if gives_t else self._t_key
        self._derived.setText(
            f"→ {other} derived — the coating is lossless by model rule, R + T = 1"
        )

    def apply_to(self, entry: dict[str, Any]) -> None:
        """Write this surface's chosen key, removing the one it is not giving."""
        gives_t = self._t_radio.isChecked()
        key, drop = (self._t_key, self._r_key) if gives_t else (self._r_key, self._t_key)
        entry.pop(drop, None)
        parsed = _parse_cell(self._value.text())
        if parsed is None:
            entry.pop(key, None)
        else:
            entry[key] = parsed

    def _on_side_changed(self, _id: int) -> None:
        # Switching which quantity is given converts the value so the surface does not
        # silently change: 1% reflectance becomes 99% transmittance, not 1%.
        current = _parse_cell(self._value.text())
        if isinstance(current, float):
            self._value.setText(f"{1.0 - current:g}")
        gives_t = self._t_radio.isChecked()
        self._label.setText(self._t_key if gives_t else self._r_key)
        self.edited.emit()

    @property
    def browse_button(self) -> QPushButton:
        return self._browse


class ElementDetailEditor(QWidget):
    """The selected element, whole: model, surfaces, bulk, thermal, derived.

    Emits :attr:`entryEdited` with a complete replacement entry. The host writes it back
    through the train editor's own commit path, so io-parser validation, undo and the
    entry-faithfulness contract (CU-344) all apply unchanged — this widget never writes
    to a sensor itself.
    """

    entryEdited = Signal(object)
    showAbsorption = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._entry: dict[str, Any] = {}
        self._model = ElementModel.REFLECTIVE
        self._pending: _Conversion | None = None
        self._loading = False
        self._substrates: tuple[SubstrateInfo, ...] = available_substrates()

        # No width bounds here: the host's inspection splitter owns the geometry, and a
        # fixed width on this form is what made the figure beside it unreadable. Field
        # widths are bounded individually instead, which is where the real constraint
        # is — a four-character reflectance gains nothing from a wider box.

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(8)

        self._title = QLabel()
        self._title.setObjectName("stagePlotTitle")
        outer.addWidget(self._title)

        outer.addWidget(self._build_model_row())
        self._note = QLabel()
        self._note.setWordWrap(True)
        self._note.setObjectName("transmissionModeBanner")
        self._note.setProperty("state", "held")
        self._note.setVisible(False)
        outer.addWidget(self._note)

        outer.addWidget(self._build_tab_row())
        self._stack = QStackedWidget(self)
        self._stack.addWidget(self._build_definition_page())
        self._stack.addWidget(self._build_bulk_page())
        self._stack.addWidget(self._build_thermal_page())
        self._stack.addWidget(self._build_derived_page())
        outer.addWidget(self._stack, 1)

    # ------------------------------------------------------------------
    # construction
    # ------------------------------------------------------------------

    def _build_model_row(self) -> QWidget:
        box = QWidget(self)
        row = QHBoxLayout(box)
        row.setContentsMargins(0, 0, 0, 0)
        model_label = QLabel("Model")
        model_label.setObjectName("sceneClassTitle")
        row.addWidget(model_label)
        self._model_buttons: dict[ElementModel, QPushButton] = {}
        self._model_group = QButtonGroup(self)
        for model, label in (
            (ElementModel.REFLECTIVE, "Reflective"),
            (ElementModel.SIMPLE, "Simple τ"),
            (ElementModel.CAVITY, "Substrate + coatings"),
        ):
            button = QPushButton(label, box)
            button.setObjectName("transmissionModeButton")
            button.setCheckable(True)
            button.clicked.connect(lambda _c, m=model: self._choose_model(m))
            self._model_group.addButton(button)
            self._model_buttons[model] = button
            row.addWidget(button)
        row.addStretch(1)
        return box

    def _build_tab_row(self) -> QWidget:
        box = QWidget(self)
        row = QHBoxLayout(box)
        row.setContentsMargins(0, 0, 0, 0)
        self._tabs: list[QPushButton] = []
        group = QButtonGroup(self)
        for index, label in enumerate(("Definition", "Bulk", "Thermal", "Derived")):
            button = QPushButton(label, box)
            button.setObjectName("transmissionModeButton")
            button.setCheckable(True)
            button.clicked.connect(lambda _c, i=index: self._stack.setCurrentIndex(i))
            group.addButton(button)
            self._tabs.append(button)
            row.addWidget(button)
        self._tabs[0].setChecked(True)
        row.addStretch(1)
        return box

    def _build_definition_page(self) -> QWidget:
        page = QWidget(self)
        box = QVBoxLayout(page)
        box.setContentsMargins(0, 0, 0, 0)

        self._surface1 = _Surface("Surface 1 — entry face", "R1", "T1", page)
        self._surface2 = _Surface("Surface 2 — exit face", "R2", "T2", page)
        for surface in (self._surface1, self._surface2):
            surface.edited.connect(self._commit)
            box.addWidget(surface)
        self._surface_note = QLabel(
            "Each surface is independent: the two may differ in value and in form — "
            "a scalar on one face and a measured CSV on the other is a normal train."
        )
        self._surface_note.setObjectName("stagePlotMessage")
        self._surface_note.setWordWrap(True)
        box.addWidget(self._surface_note)

        self._single = QWidget(page)
        single_form = QFormLayout(self._single)
        single_form.setContentsMargins(0, 0, 0, 0)
        self._single_value = QLineEdit(self._single)
        self._single_value.setMaximumWidth(_VALUE_WIDTH)
        self._single_value.editingFinished.connect(self._commit)
        self._single_label = QLabel("R")
        single_form.addRow(self._single_label, self._single_value)
        self._single_note = QLabel()
        self._single_note.setObjectName("stagePlotMessage")
        self._single_note.setWordWrap(True)
        single_form.addRow(self._single_note)
        box.addWidget(self._single)

        box.addStretch(1)
        return page

    def _build_bulk_page(self) -> QWidget:
        page = QWidget(self)
        box = QVBoxLayout(page)
        box.setContentsMargins(0, 0, 0, 0)

        self._bulk_absent = QLabel()
        self._bulk_absent.setObjectName("stagePlotMessage")
        self._bulk_absent.setWordWrap(True)
        box.addWidget(self._bulk_absent)

        self._bulk = QWidget(page)
        inner = QVBoxLayout(self._bulk)
        inner.setContentsMargins(0, 0, 0, 0)
        bulk_caption = QLabel("Bulk absorption from — one or the other, never both")
        bulk_caption.setWordWrap(True)
        inner.addWidget(bulk_caption)

        self._named_radio = QRadioButton("Named substrate", self._bulk)
        self._explicit_radio = QRadioButton("Explicit α", self._bulk)
        source = QButtonGroup(self)
        source.addButton(self._named_radio)
        source.addButton(self._explicit_radio)
        self._named_radio.toggled.connect(self._on_bulk_source_changed)

        inner.addWidget(self._named_radio)
        self._substrate_combo = QComboBox(self._bulk)
        self._populate_substrates()
        self._substrate_combo.currentIndexChanged.connect(self._commit)
        picker_row = QHBoxLayout()
        # The combo yields width; the button does not. Given equal footing the combo
        # takes its content width and pushes the button past the panel edge, where it
        # is unreachable rather than merely tight.
        self._substrate_combo.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToContentsOnFirstShow
        )
        self._substrate_combo.setMinimumContentsLength(10)
        self._substrate_combo.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        picker_row.addWidget(self._substrate_combo, 1)
        # "If I want to see what the absorption is, I should be able to navigate there"
        # (owner, 2026-10-04). alpha IS the property being chosen and the one the name
        # does not tell you, so it gets a one-click route from the point of choosing.
        self._view_alpha = QPushButton("View α(λ)…", self._bulk)
        self._view_alpha.setToolTip(
            "Plot this material's absorption coefficient and refractive index across "
            "its whole published window, with the evaluation band shaded."
        )
        self._view_alpha.clicked.connect(self._emit_show_absorption)
        picker_row.addWidget(self._view_alpha)
        inner.addLayout(picker_row)
        self._substrate_facts = QLabel(self._bulk)
        self._substrate_facts.setObjectName("stagePlotMessage")
        self._substrate_facts.setWordWrap(True)
        inner.addWidget(self._substrate_facts)

        inner.addWidget(self._explicit_radio)
        self._explicit = QWidget(self._bulk)
        explicit_box = QVBoxLayout(self._explicit)
        explicit_box.setContentsMargins(16, 0, 0, 0)
        explicit_box.setSpacing(5)
        alpha_row = QHBoxLayout()
        alpha_row.addWidget(QLabel("α"))
        self._alpha = QLineEdit(self._explicit)
        self._alpha.setPlaceholderText("scalar, CSV path, or table")
        self._alpha.setMaximumWidth(_VALUE_WIDTH)
        self._alpha.editingFinished.connect(self._commit)
        alpha_row.addWidget(self._alpha)
        # alpha(lambda) is the usual case, not the exception: a measured coupon comes
        # off an FTIR as a spectrum, and the library's own materials are spectra. The
        # field has always accepted a CSV path or an inline table — the config layer
        # resolves all three forms — but with no button the only way to discover it was
        # to read the parser (owner, 2026-10-04).
        self._alpha_csv = QPushButton("CSV…", self._explicit)
        self._alpha_csv.setToolTip(
            "Load α(λ) from a two-column CSV: wavelength_um, alpha. A column-header "
            "row is accepted; comment lines start with '#'."
        )
        self._alpha_csv.clicked.connect(self._pick_alpha_csv)
        alpha_row.addWidget(self._alpha_csv)
        alpha_row.addWidget(QLabel("1/m"))
        alpha_row.addStretch(1)
        explicit_box.addLayout(alpha_row)
        explicit_note = QLabel(
            "A scalar, or α(λ) from a CSV — the custom-material path for a measured "
            "coupon or a substrate the library does not carry.",
            self._explicit,
        )
        explicit_note.setObjectName("stagePlotMessage")
        explicit_note.setWordWrap(True)
        explicit_box.addWidget(explicit_note)
        inner.addWidget(self._explicit)

        thickness_row = QHBoxLayout()
        thickness_row.addWidget(QLabel("Thickness"))
        self._thickness = QLineEdit(self._bulk)
        self._thickness.editingFinished.connect(self._commit)
        self._thickness.setMaximumWidth(110)
        thickness_row.addWidget(self._thickness)
        thickness_row.addWidget(QLabel("mm"))
        thickness_row.addStretch(1)
        inner.addLayout(thickness_row)
        # Its own wrapped line, not a tail on the field's row: trailing prose in a
        # fixed-height row cannot wrap, so in a narrow column it is simply cut — this
        # one read "belongs to the lens, never" with the sentence lost off the edge.
        thickness_note = QLabel("Belongs to the lens, never to the material.", self._bulk)
        thickness_note.setObjectName("stagePlotMessage")
        thickness_note.setWordWrap(True)
        inner.addWidget(thickness_note)

        box.addWidget(self._bulk)
        box.addStretch(1)
        return page

    def _build_thermal_page(self) -> QWidget:
        page = QWidget(self)
        form = QFormLayout(page)
        form.setContentsMargins(0, 0, 0, 0)
        self._temperature = QLineEdit(page)
        self._temperature.setMaximumWidth(110)
        self._temperature.editingFinished.connect(self._commit)
        form.addRow("Temperature [K]", self._temperature)
        explain = QLabel(
            "Feeds this element's near-field self-emission, L(λ) = ε(λ)·B(λ, T). "
            "ε is derived from the bulk and the coatings and is never entered."
        )
        explain.setWordWrap(True)
        form.addRow(explain)
        self._validity = QLabel(page)
        self._validity.setObjectName("stagePlotMessage")
        self._validity.setWordWrap(True)
        form.addRow(self._validity)
        return page

    def _build_derived_page(self) -> QWidget:
        page = QWidget(self)
        box = QVBoxLayout(page)
        box.setContentsMargins(0, 0, 0, 0)
        self._derived_text = QLabel(page)
        self._derived_text.setObjectName("stagePlotMessage")
        self._derived_text.setWordWrap(True)
        self._derived_text.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        box.addWidget(self._derived_text)
        box.addStretch(1)
        return page

    def _populate_substrates(self) -> None:
        self._substrate_combo.addItem(NO_SUBSTRATE, "")
        separated = False
        for info in self._substrates:
            if info.is_flagged and not separated:
                self._substrate_combo.addItem(FLAGGED_SEPARATOR, None)
                index = self._substrate_combo.count() - 1
                self._substrate_combo.model().item(index).setEnabled(False)
                separated = True
            self._substrate_combo.addItem(info.label, info.name)
            tip = (
                f"tier {info.tier} · window {info.window_um[0]:g}–{info.window_um[1]:g} µm · "
                f"α published at {info.reference_temperature_K:g} K"
            )
            if info.grade_sensitivity:
                tip += f" · grade spread {info.grade_sensitivity}"
            self._substrate_combo.setItemData(
                self._substrate_combo.count() - 1, tip, Qt.ItemDataRole.ToolTipRole
            )

    # ------------------------------------------------------------------
    # binding
    # ------------------------------------------------------------------

    def bind_entry(self, entry: dict[str, Any] | None, derived: str = "") -> None:
        """Show *entry*. ``None`` clears the panel (no row selected)."""
        self._loading = True
        try:
            self._pending = None
            self._note.setVisible(False)
            self._entry = copy.deepcopy(entry) if entry else {}
            self.setEnabled(bool(entry))
            if not entry:
                self._title.setText("No element selected")
                return
            self._model = model_of_entry(self._entry)
            name = str(self._entry.get("name", "(unnamed)"))
            kind = str(self._entry.get("kind", "")).lower()
            self._title.setText(f"<b>{name}</b>  {kind}")
            self._model_buttons[self._model].setChecked(True)
            self._render(self._model, self._entry)
            self._derived_text.setText(derived or "Evaluate to populate the derived values.")
        finally:
            self._loading = False

    def _render(self, model: ElementModel, entry: dict[str, Any]) -> None:
        cavity = model is ElementModel.CAVITY
        self._surface1.setVisible(cavity)
        self._surface2.setVisible(cavity)
        self._surface_note.setVisible(cavity)
        self._single.setVisible(not cavity)
        if cavity:
            self._surface1.bind(entry)
            self._surface2.bind(entry)
        else:
            reflective = model is ElementModel.REFLECTIVE
            key = "reflectance" if reflective else "transmittance"
            self._single_label.setText("R" if reflective else "τ")
            self._single_value.setText(_as_text(entry.get(key)))
            self._single_note.setText(
                "→ ε = 1 − R, derived. A mirror has no bulk and no second surface."
                if reflective
                else "This form takes the remaining 1 − τ to be <b>reflection, not "
                "absorption</b>, so ε = 0 by construction and this element emits "
                "nothing. Switch to <i>Substrate + coatings</i> to model its emission."
            )

        self._bulk.setVisible(cavity)
        self._bulk_absent.setVisible(not cavity)
        if not cavity:
            self._bulk_absent.setText(
                "<b>No bulk on this element.</b> A substrate supplies the bulk absorption "
                "coefficient α and the refractive index n, and those reach the answer only "
                "through the cavity emission model, which this element does not run. "
                "Naming a material here would change nothing — which is why the "
                "configuration refuses it rather than accepting it quietly."
            )
        else:
            named = entry.get("substrate")
            self._named_radio.setChecked(named is not None)
            self._explicit_radio.setChecked(named is None)
            index = self._substrate_combo.findData(str(named or ""))
            self._substrate_combo.setCurrentIndex(max(0, index))
            self._alpha.setText(_as_text(entry.get("alpha")))
            thickness = entry.get("thickness_m")
            self._thickness.setText("" if thickness is None else f"{float(thickness) * 1000.0:g}")
            self._on_bulk_source_changed(self._named_radio.isChecked())
            self._update_substrate_facts()

        self._temperature.setText(_as_text(entry.get("temperature_K")))
        self._update_validity()

    def _update_substrate_facts(self) -> None:
        info = self._selected_substrate()
        self._view_alpha.setEnabled(info is not None)
        if info is None:
            self._substrate_facts.setText(
                "The custom-material path: state α yourself. Unchanged and fully "
                "supported — it is how you model a lot-specific coupon or a material the "
                "library does not carry."
            )
            return
        flag = " · class-typical α, not measured" if info.is_flagged else ""
        text = (
            f"tier {info.tier}{flag} · window {info.window_um[0]:g}–{info.window_um[1]:g} µm · "
            f"α published at {info.reference_temperature_K:g} K"
        )
        if info.grade_sensitivity:
            text += f" · grade spread {info.grade_sensitivity}"
        self._substrate_facts.setText(text)

    def _update_validity(self) -> None:
        info = self._selected_substrate()
        if info is None or info.valid_temperature_K is None:
            self._validity.setText("")
            return
        low, high = info.valid_temperature_K
        temperature = _parse_cell(self._temperature.text())
        if not isinstance(temperature, float):
            self._validity.setText(f"{info.label} is valid over {low:g}–{high:g} K.")
            return
        inside = low <= temperature <= high
        verdict = "in range" if inside else "OUTSIDE the published validity window"
        self._validity.setText(
            f"{info.label} α is published at {info.reference_temperature_K:g} K and is "
            f"valid over {low:g}–{high:g} K. This element is at {temperature:g} K — {verdict}."
        )

    def _selected_substrate(self) -> SubstrateInfo | None:
        name = str(self._substrate_combo.currentData() or "")
        if not name:
            return None
        return next((i for i in self._substrates if i.name == name), None)

    # ------------------------------------------------------------------
    # editing
    # ------------------------------------------------------------------

    def _on_bulk_source_changed(self, named: bool) -> None:
        self._substrate_combo.setEnabled(named)
        self._explicit.setEnabled(not named)
        if not self._loading:
            self._commit()

    def _choose_model(self, model: ElementModel) -> None:
        if self._loading or model is self._model:
            self._pending = None
            self._note.setVisible(False)
            return
        conversion = self._convert(model)
        self._pending = conversion
        self._note.setText(f"<b>Not applied yet.</b> {conversion.note}")
        self._note.setVisible(True)
        self._loading = True
        try:
            self._render(model, conversion.entry)
        finally:
            self._loading = False
        self._model = model
        self._entry = conversion.entry
        self.entryEdited.emit(copy.deepcopy(conversion.entry))

    def _convert(self, model: ElementModel) -> _Conversion:
        """Build the converted entry and the sentence that says what it cost."""
        entry = copy.deepcopy(self._entry)
        for key in ("R1", "T1", "R2", "T2", "alpha", "thickness_m", "substrate"):
            entry.pop(key, None)
        if model is ElementModel.REFLECTIVE:
            entry["transfer_mode"] = "REFLECTIVE"
            entry.setdefault("reflectance", entry.pop("transmittance", 0.97))
            entry.pop("kind", None)
            note = (
                "A mirror has one surface and no bulk, so the thickness, the second "
                "surface and the substrate are discarded. ε becomes 1 − R."
            )
        elif model is ElementModel.SIMPLE:
            entry["transfer_mode"] = "REFRACTIVE"
            entry.setdefault("transmittance", entry.pop("reflectance", 0.95))
            note = (
                "The simple form keeps one net transmittance and sets ε to exactly 0 — "
                "this element stops emitting. Both surface coatings, the thickness and "
                "the substrate are discarded, and nothing remembers them."
            )
        else:
            entry["transfer_mode"] = "REFRACTIVE"
            entry.pop("reflectance", None)
            entry.pop("transmittance", None)
            entry["R1"] = SEED_SURFACE_R
            entry["R2"] = SEED_SURFACE_R
            entry["thickness_m"] = SEED_THICKNESS_M
            entry.setdefault("kind", "lens")
            note = (
                f"The cavity model needs two things the simple form does not carry: a "
                f"thickness and a coating value per surface. Seeded at "
                f"{SEED_THICKNESS_M * 1000:g} mm and R₁ = R₂ = {SEED_SURFACE_R:g} — that is "
                "a guess at the coatings, not a conversion of them, because one net "
                "transmittance cannot determine two coatings plus a bulk. ε stays 0 until "
                "you give it a substrate or an explicit α."
            )
        return _Conversion(entry=entry, note=note)

    def _commit(self) -> None:
        if self._loading or not self._entry:
            return
        entry = copy.deepcopy(self._entry)
        # The one place entry-faithfulness (CU-344) must yield. A document written
        # before a key was removed still carries it, and the parser refuses it — so a
        # row riding it through would be un-committable for ever: every edit re-emits
        # the key and every commit is rejected for a field the operator never set and
        # cannot see. Dropped against the parser's own roster, never a guess at it.
        for removed in REMOVED_ENTRY_KEYS:
            entry.pop(removed, None)
        if self._model is ElementModel.CAVITY:
            self._surface1.apply_to(entry)
            self._surface2.apply_to(entry)
            if self._named_radio.isChecked():
                entry.pop("alpha", None)
                name = str(self._substrate_combo.currentData() or "")
                if name:
                    entry["substrate"] = name
                else:
                    entry.pop("substrate", None)
            else:
                entry.pop("substrate", None)
                _assign(entry, "alpha", self._alpha.text())
            thickness = _parse_cell(self._thickness.text())
            if isinstance(thickness, float):
                entry["thickness_m"] = thickness / 1000.0
            elif thickness is None:
                entry.pop("thickness_m", None)
        else:
            reflective = self._model is ElementModel.REFLECTIVE
            _assign(
                entry, "reflectance" if reflective else "transmittance", self._single_value.text()
            )
        _assign(entry, "temperature_K", self._temperature.text())

        self._update_substrate_facts()
        self._update_validity()
        if entry == self._entry:
            return
        self._entry = entry
        self.entryEdited.emit(copy.deepcopy(entry))

    def _pick_alpha_csv(self) -> None:
        """Choose a two-column α(λ) CSV and put its path in the field."""
        path, _ = QFileDialog.getOpenFileName(
            self, "Select α(λ) CSV", "", "CSV files (*.csv);;All files (*)"
        )
        if path:
            self._alpha.setText(path)
            self._commit()

    def _emit_show_absorption(self) -> None:
        """Ask the host to show the selected material's absorption figure."""
        info = self._selected_substrate()
        if info is not None:
            self.showAbsorption.emit(info.name)

    @property
    def model(self) -> ElementModel:
        """The model currently shown."""
        return self._model

    @property
    def entry(self) -> dict[str, Any]:
        """A copy of the entry as currently edited."""
        return copy.deepcopy(self._entry)


def _assign(entry: dict[str, Any], key: str, text: str) -> None:
    """Write *text* to *key*, or remove the key when the field is cleared.

    Clearing a field removes the key rather than writing a zero, so the io parser's own
    default keeps applying — the same contract the train table's empty cells carry
    (CU-344). A field showing a spectral sentinel ("spectral (N pts)") is left alone:
    it is a rendering, not a value, and must not be written back as a string.
    """
    if text.strip().startswith("spectral ("):
        return
    parsed = _parse_cell(text)
    if parsed is None:
        entry.pop(key, None)
    else:
        entry[key] = parsed
