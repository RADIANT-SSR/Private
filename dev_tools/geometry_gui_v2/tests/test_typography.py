"""T1 acceptance: glossary + typography helpers behave as advertised."""

from __future__ import annotations

import pytest

from dev_tools.geometry_gui_v2.scene.labels.typography import (
    all_keys,
    description,
    panel_label,
    viewport_label,
)


def test_every_key_has_all_three_forms() -> None:
    for key in all_keys():
        assert viewport_label(key)
        assert panel_label(key)
        assert description(key)


def test_no_underscore_in_panel_labels_outside_subscript() -> None:
    """``panel_label`` may contain ``<sub>`` tags but never a literal ``_``.

    ``_`` in a Qt-rendered HTML label is the visible "built by an engineer"
    tell that this remediation exists to delete.
    """
    for key in all_keys():
        rendered = panel_label(key)
        assert "_" not in rendered, f"{key}: {rendered}"


def test_unknown_key_raises() -> None:
    with pytest.raises(KeyError):
        viewport_label("nonexistent_key")


def test_viewport_label_phase_angle_target() -> None:
    assert viewport_label("phase_angle_target") == r"$\alpha_{t}$"


def test_panel_label_phase_angle_target() -> None:
    assert panel_label("phase_angle_target") == "α<sub>t</sub>"
