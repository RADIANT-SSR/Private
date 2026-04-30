"""Right-dock readouts panel — four collapsible sections of live values.

PLAN_v2.md §12 step 4-5:
  * Four collapsible ``QGroupBox`` sections: Scene objects / Vectors /
    Angles / Regime.
  * Every numeric row pulls from ``view_model.derived_readout(state)`` so
    the displayed number is the same number radiometry would consume
    (C3 invariant).
  * Monospace font, right-aligned numerics, padded tabular grid.
  * Projected-area row carries the literal ``[from shape.projected_area]``
    tag so the user knows it is the radiometry handoff (step 5).

Hard rule (Jason's "units on every output" memory): every numeric value
on this panel carries explicit units. The view-model formatter
(``format_readout``) is the single source of truth for the unit-bearing
display strings — this widget never builds its own format strings.

Rule 19: own file. The other panels (left-dock parameters, status bar)
land in their own modules in Phase 5/6.
"""

from __future__ import annotations

from typing import Final

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QCheckBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from dev_tools.geometry_gui_v2.app.state import SceneState
from dev_tools.geometry_gui_v2.app.view_model import (
    classify_regime,
    format_readout,
    multi_facet_explainer,
)
from dev_tools.geometry_gui_v2.scene.labels.typography import panel_label


# Section title → list of (display label, component-id) pairs. Component
# ids are the keys returned by ``format_readout`` so updates are wired by
# id without the panel knowing the format.
#
# T10 of the visual remediation: every symbol that appears in a row
# label flows through ``panel_label()`` so the glossary YAML is the
# single source of truth (HTML form for Qt panels, math-text for the
# 3D viewport).
_SECTIONS: Final[list[tuple[str, list[tuple[str, str]]]]] = [
    (
        "Scene objects",
        [
            ("Slant range", "ro-slant-range"),
            ("Ground range", "ro-ground-range"),
            ("Pixel area", "ro-pixel-area"),
            (f"Projected area {panel_label('projected_area')}", "ro-projected-area"),
        ],
    ),
    (
        "Vectors",
        [
            ("View azimuth", "ro-view-azimuth"),
            ("View elevation", "ro-view-elevation"),
            ("Solar zenith", "ro-solar-zenith"),
            ("Relative azimuth", "ro-relative-azimuth"),
        ],
    ),
    (
        "Angles",
        [
            ("GSD", "ro-gsd"),
            ("IFOV", "ro-ifov"),
            ("Angular extent", "ro-angular-extent"),
            ("Effective fill fraction", "ro-fill-fraction"),
        ],
    ),
    (
        "Regime",
        [
            ("Regime", "ro-regime"),
            ("Reason", "ro-regime-reason"),
        ],
    ),
]

# Component id of the projected-area row gets the literal handoff tag.
_PROJECTED_AREA_TAG: Final[str] = "  [from shape.projected_area]"


def _monospace_font() -> QFont:
    """System monospace at the readout-grid weight.

    Tries Inter Mono → JetBrains Mono → Menlo → system monospace
    fallback (Qt's StyleHint.Monospace). The tag the user sees is the
    first one available on their system; identical font on
    every platform is a Phase-7 polish concern.
    """
    for family in ("Inter Mono", "JetBrains Mono", "Menlo"):
        f = QFont(family, 11)
        f.setStyleHint(QFont.Monospace)
        return f
    f = QFont()
    f.setStyleHint(QFont.Monospace)
    f.setFamily("Monospace")
    f.setPointSize(11)
    return f


class ReadoutsPanel(QWidget):
    """Right-dock widget: four collapsible sections of live numeric rows.

    Wire changes in scene state by calling ``set_state(state)``; the
    panel re-pulls every component-id from ``format_readout`` and
    updates each value label in place.

    Round-2 R7 (PLAN_v2_remediation_round2.md §8): a fifth "Visibility"
    section carries an eye-icon toggle per scene primitive. Toggles
    emit ``visibility_changed(primitive_name, is_visible)``. The host
    window (``app.main``) wires the signal to per-actor visibility on
    the plotter; the panel itself stays Qt-only and never imports the
    plotter or the scene namespace.
    """

    # PLAN_v2_remediation_round2.md §8: eye-icon visibility toggles emit
    # ``visibility_changed(primitive, is_visible)``. The signal is the
    # contract; the main window listens and applies the toggle to the
    # PyVista plotter via ``scene.highlight.actors_for_primitive``.
    visibility_changed = Signal(str, bool)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._value_labels: dict[str, QLabel] = {}
        self._visibility_checkboxes: dict[str, QCheckBox] = {}
        self._mono_font = _monospace_font()

        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 8, 8, 8)
        outer.setSpacing(8)

        for section_title, rows in _SECTIONS:
            group = self._build_section(section_title, rows)
            outer.addWidget(group)

        explainer_group = QGroupBox("Multi-facet decomposition")
        ex_layout = QVBoxLayout(explainer_group)
        self._explainer_label = QLabel("(awaiting first state update)")
        self._explainer_label.setWordWrap(True)
        ex_layout.addWidget(self._explainer_label)
        outer.addWidget(explainer_group)

        # The visibility section is built by ``populate_visibility_toggles``
        # so the host window owns the (primitive → display-label) mapping.
        # Keeping the panel decoupled from ``scene.highlight`` honors C7
        # at the panel layer (Qt-only widget; no scene imports).
        self._visibility_group = QGroupBox("Visibility")
        self._visibility_group.setCheckable(True)
        self._visibility_group.setChecked(True)
        self._visibility_form = QFormLayout(self._visibility_group)
        self._visibility_form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        self._visibility_form.setHorizontalSpacing(16)
        self._visibility_form.setVerticalSpacing(4)
        outer.addWidget(self._visibility_group)

        outer.addStretch(1)

    def populate_visibility_toggles(
        self, primitives: list[tuple[str, str]]
    ) -> None:
        """Populate the Visibility section with one row per primitive.

        ``primitives`` is a list of ``(primitive_name, display_label)``
        tuples — the host window owns the display labels (the panel
        cannot import ``scene.highlight``'s primitive-name vocabulary
        without coupling). Idempotent: a second call rebuilds the section.
        """
        # Tear down any prior rows so a re-populate works cleanly.
        for cb in self._visibility_checkboxes.values():
            cb.deleteLater()
        self._visibility_checkboxes.clear()
        while self._visibility_form.rowCount():
            self._visibility_form.removeRow(0)

        for primitive_name, display_label in primitives:
            # Eye-icon affordance: a checkbox with a leading "eye"
            # character that flips with the toggle state. The Qt-material
            # dark theme styles the checkbox indicator natively; the
            # leading glyph is the secondary-redundant signal.
            cb = QCheckBox("\u25c9 visible")
            cb.setChecked(True)
            cb.setToolTip(f"Toggle visibility of {display_label}")
            cb.toggled.connect(
                lambda checked, p=primitive_name, c=cb: self._on_visibility_toggled(
                    p, checked, c
                )
            )
            self._visibility_checkboxes[primitive_name] = cb
            self._visibility_form.addRow(QLabel(display_label), cb)

    def set_primitive_visibility(self, primitive_name: str, visible: bool) -> None:
        """External API — host window calls this when the Scene menu (or
        a keyboard shortcut) toggles a primitive elsewhere, so the panel
        checkbox stays in sync. Blocks signal emission so the host
        doesn't get a feedback loop."""
        cb = self._visibility_checkboxes.get(primitive_name)
        if cb is None:
            return
        cb.blockSignals(True)
        cb.setChecked(bool(visible))
        cb.setText("\u25c9 visible" if visible else "\u25cb hidden")
        cb.blockSignals(False)

    def _on_visibility_toggled(
        self, primitive_name: str, checked: bool, checkbox: QCheckBox
    ) -> None:
        checkbox.setText("\u25c9 visible" if checked else "\u25cb hidden")
        self.visibility_changed.emit(primitive_name, bool(checked))

    def _build_section(
        self, title: str, rows: list[tuple[str, str]]
    ) -> QGroupBox:
        group = QGroupBox(title)
        group.setCheckable(True)
        group.setChecked(True)
        form = QFormLayout(group)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        form.setFormAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        form.setHorizontalSpacing(16)
        form.setVerticalSpacing(4)

        for display_text, component_id in rows:
            value = QLabel("—")
            value.setFont(self._mono_font)
            value.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            value.setMinimumWidth(180)
            self._value_labels[component_id] = value
            form.addRow(QLabel(display_text), value)

        return group

    def set_state(self, state: SceneState) -> None:
        """Refresh every readout row from the view-model."""
        regime, reason = classify_regime(state)
        formatted = format_readout(state, regime, reason)
        for component_id, text in formatted.items():
            label = self._value_labels.get(component_id)
            if label is None:
                continue
            display = text
            if component_id == "ro-projected-area":
                display = f"{text}{_PROJECTED_AREA_TAG}"
            label.setText(display)

        self._explainer_label.setText(multi_facet_explainer(state.target_shape))
