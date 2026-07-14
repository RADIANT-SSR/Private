"""Themed key-value readout of the derived geometry stage outputs (§4.4, §6).

:class:`GeometryReadout` is the Geometry stage's default central visualization until
the 3D viewer lands (GUI plan Phases 6–7). It renders the derived angle/range values
from ``stage_outputs["geometry"]`` as a titled key-value table — each row a symbol, a
human label, and the value **with its unit** (R-UNITS, an owner hard rule).

The rows are grouped by **reference frame** (GUI plan Phase 5 task 2): a *target-frame*
set (angles referenced at the target's local vertical — θ_o, θ_i, θ_s, Δφ — the angles
the source/atmosphere consume) and a *ground/platform-frame* set (the sensor-side
off-nadir angle η and the ranges, altitudes, and kinematics that describe the
platform-to-ground geometry), plus a small *resolution* group naming the illumination
and which input mode resolved each family. Any output key not classified falls into an
"Other" group so a future stage output is never silently dropped.

This is *data display, not physics*: the values are read **verbatim** from the stage
output in their canonical units (angles in ``rad``, lengths in ``m``, speeds in
``m/s``, times in ``s`` — per ``RADIANT_Conventions.md``). No conversion happens here
(Rule 2 — the GUI does no unit maths); the unit suffix is inferred from the output
key's canonical suffix, and known angle keys get their conventional symbol. Values
that are structured objects (e.g. ``los_geometry``) rather than scalars are not part
of the angle summary and are skipped.

All colour/typography comes from the QSS theme via object names (GUI plan §4.9); this
file sets structure and text only.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Final

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QGridLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from radiant.gui.param_format import format_value

_TITLE: Final[str] = "Geometry — derived angles & ranges"

# Known geometry output keys → (human label, conventional symbol). Keys not listed
# fall back to a humanized key and an empty symbol. Symbols follow the geometry doc /
# §6.2 (θ_o target zenith, θ_s solar zenith, η nadir angle, Δφ relative azimuth).
_LABELS: Final[Mapping[str, tuple[str, str]]] = {
    "theta_o_rad": ("Target-path zenith", "θ_o"),
    "theta_s_rad": ("Solar zenith", "θ_s"),
    "eta_rad": ("Nadir (off-nadir) angle", "η"),
    "delta_phi_rad": ("Relative azimuth", "Δφ"),
    "incidence_angle_rad": ("Incidence angle", "θ_i"),
    "slant_range_m": ("Slant range", "R"),
    "ground_range_m": ("Ground range", ""),
    "target_range_m": ("Target range", ""),
    "h_sensor_m": ("Sensor altitude", "h_sen"),
    "h_target_m": ("Target altitude", "h_tgt"),
    "ground_speed_m_s": ("Ground speed", "v_g"),
    "orbital_period_s": ("Orbital period", "T"),
    "solar_illumination": ("Solar illumination", ""),
    "solar_mode": ("Solar mode", ""),
    "viewing_mode": ("Viewing mode", ""),
    "kinematics_mode": ("Kinematics mode", ""),
}

# Reference-frame grouping (Phase 5 task 2). Ordered (group title, output keys). A key
# not listed here lands in the appended "Other" group so nothing is silently dropped.
_TARGET_FRAME = "Target-frame angles"
_GROUND_FRAME = "Ground / platform frame"
_RESOLUTION = "Resolution"
_OTHER = "Other"

_GROUPS: Final[tuple[tuple[str, tuple[str, ...]], ...]] = (
    (_TARGET_FRAME, ("theta_o_rad", "incidence_angle_rad", "theta_s_rad", "delta_phi_rad")),
    (
        _GROUND_FRAME,
        (
            "eta_rad",
            "slant_range_m",
            "ground_range_m",
            "target_range_m",
            "h_sensor_m",
            "h_target_m",
            "ground_speed_m_s",
            "orbital_period_s",
        ),
    ),
    (_RESOLUTION, ("solar_illumination", "viewing_mode", "solar_mode", "kinematics_mode")),
)

# Canonical unit suffix → unit string (RADIANT_Conventions.md). Longest suffix first
# so ``_m_s`` (speed) matches before ``_m`` / ``_s``.
_UNIT_SUFFIXES: Final[tuple[tuple[str, str], ...]] = (
    ("_m_s", "m/s"),
    ("_rad", "rad"),
    ("_m", "m"),
    ("_s", "s"),
)


def _unit_for(key: str) -> str:
    """Infer the canonical unit of a geometry output *key* from its suffix (``""`` if none)."""
    for suffix, unit in _UNIT_SUFFIXES:
        if key.endswith(suffix):
            return unit
    return ""


def _label_and_symbol(key: str) -> tuple[str, str]:
    """The (label, symbol) for *key* — known mapping, else a humanized fallback."""
    if key in _LABELS:
        return _LABELS[key]
    label = key
    for suffix, _unit in _UNIT_SUFFIXES:
        if label.endswith(suffix):
            label = label[: -len(suffix)]
            break
    return label.replace("_", " ").capitalize(), ""


def _is_scalar(value: Any) -> bool:
    """True for the primitive scalars the readout renders (numbers, strings, None)."""
    return value is None or isinstance(value, (bool, int, float, str))


def _grouped_keys(geometry_outputs: Mapping[str, Any]) -> list[tuple[str, list[str]]]:
    """Bucket the present scalar output keys into frame groups, in group order.

    Empty groups are dropped; any scalar key not classified is collected into a
    trailing "Other" group so a new stage output is never silently omitted.
    """
    scalar_keys = [key for key, value in geometry_outputs.items() if _is_scalar(value)]
    classified: set[str] = set()
    groups: list[tuple[str, list[str]]] = []
    for title, keys in _GROUPS:
        present = [key for key in keys if key in scalar_keys]
        classified.update(present)
        if present:
            groups.append((title, present))
    extras = [key for key in scalar_keys if key not in classified]
    if extras:
        groups.append((_OTHER, extras))
    return groups


class GeometryReadout(QWidget):
    """Titled key-value readout of ``stage_outputs["geometry"]`` (Geometry default view).

    Parameters
    ----------
    parent:
        The owning widget, if any.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("geometryReadout")

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self._title = QLabel(_TITLE, self)
        self._title.setObjectName("geoReadoutTitle")

        # A scroll area keeps a long angle set usable in a short canvas.
        self._scroll = QScrollArea(self)
        self._scroll.setObjectName("geoReadoutScroll")
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QScrollArea.Shape.NoFrame)

        self._grid_host = QWidget(self._scroll)
        self._grid_host.setObjectName("geoReadoutBody")
        self._grid = QGridLayout(self._grid_host)
        self._grid.setContentsMargins(14, 12, 14, 12)
        self._grid.setHorizontalSpacing(14)
        self._grid.setVerticalSpacing(6)
        self._grid.setColumnStretch(1, 1)  # let the label column take the slack
        self._scroll.setWidget(self._grid_host)

        outer.addWidget(self._title)
        outer.addWidget(self._scroll, 1)

        # dotpath-free: keyed by output key so tests can read a rendered value back.
        self._value_labels: dict[str, QLabel] = {}
        # group title -> the output keys rendered under it (for tests / grouping checks).
        self._groups: dict[str, list[str]] = {}

    def populate(self, geometry_outputs: Mapping[str, Any]) -> None:
        """Render the geometry stage outputs as frame-grouped symbol/label/value rows.

        Only scalar outputs (the derived angles, ranges, modes) are shown; structured
        objects such as ``los_geometry`` are skipped. Rows are grouped by reference
        frame (target-frame vs ground/platform frame vs resolution), each group under a
        sub-header; re-populating is stable.
        """
        self._clear()
        row = 0
        for title, keys in _grouped_keys(geometry_outputs):
            header = QLabel(title, self._grid_host)
            header.setObjectName("geoReadoutGroupHeader")
            self._grid.addWidget(header, row, 0, 1, 3)
            row += 1
            self._groups[title] = list(keys)
            for key in keys:
                label, symbol = _label_and_symbol(key)
                unit = _unit_for(key)
                value_text = format_value(geometry_outputs[key], unit)

                symbol_label = QLabel(symbol, self._grid_host)
                symbol_label.setObjectName("geoReadoutSymbol")
                name_label = QLabel(label, self._grid_host)
                name_label.setObjectName("geoReadoutLabel")
                value_label = QLabel(value_text, self._grid_host)
                value_label.setObjectName("geoReadoutValue")
                value_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
                value_label.setAlignment(
                    Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
                )

                self._grid.addWidget(symbol_label, row, 0)
                self._grid.addWidget(name_label, row, 1)
                self._grid.addWidget(value_label, row, 2)
                self._value_labels[key] = value_label
                row += 1
        self._grid.setRowStretch(row, 1)

    def value_text(self, key: str) -> str:
        """The rendered 'value + unit' text for a geometry output *key* (for tests)."""
        return self._value_labels[key].text()

    def rendered_keys(self) -> set[str]:
        """The geometry output keys currently rendered as rows."""
        return set(self._value_labels)

    def group_keys(self, group_title: str) -> list[str]:
        """The output keys rendered under *group_title* (empty if the group is absent)."""
        return list(self._groups.get(group_title, []))

    def group_titles(self) -> list[str]:
        """The frame-group titles currently rendered, in order."""
        return list(self._groups)

    def _clear(self) -> None:
        """Remove all existing rows before a re-populate."""
        self._value_labels.clear()
        self._groups.clear()
        while self._grid.count():
            item = self._grid.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()
