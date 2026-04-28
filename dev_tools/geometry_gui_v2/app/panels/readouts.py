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

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
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


# Section title → list of (display label, component-id) pairs. Component
# ids are the keys returned by ``format_readout`` so updates are wired by
# id without the panel knowing the format.
_SECTIONS: Final[list[tuple[str, list[tuple[str, str]]]]] = [
    (
        "Scene objects",
        [
            ("Slant range", "ro-slant-range"),
            ("Ground range", "ro-ground-range"),
            ("Pixel area", "ro-pixel-area"),
            ("Projected area A_t", "ro-projected-area"),
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
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._value_labels: dict[str, QLabel] = {}
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

        outer.addStretch(1)

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
