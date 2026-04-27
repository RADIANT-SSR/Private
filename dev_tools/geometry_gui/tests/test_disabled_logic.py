"""Phase 4 disabled-slider logic tests.

Pin the per-shape and per-regime grey-out behavior published by
`main.slider_disabled` and `main.shape_dropdown_disabled`. Together these
realize the Phase-4 §"Per-shape relevant size sliders" table and the
EXTENDED-mode shape-dropdown rule.
"""

from __future__ import annotations

import pytest

from radiant.core.regime import RadiometricRegime

from dev_tools.geometry_gui.app.main import (
    SHAPE_RELEVANT_SIZES,
    SIZE_SLIDERS,
    TARGET_DISABLE_IDS,
    shape_dropdown_disabled,
    slider_disabled,
)


# ---------------------------------------------------------------------------
# Per-shape size-slider table (Phase-4 §"Per-shape relevant size sliders")
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "shape, relevant",
    [
        ("sphere", {"tgt-radius"}),
        ("cylinder", {"tgt-radius", "tgt-length"}),
        ("flat_plate", {"tgt-length", "tgt-width"}),
        ("box", {"tgt-length", "tgt-width", "tgt-height"}),
        ("cone", {"tgt-base-radius", "tgt-height"}),
    ],
)
def test_size_slider_relevance(shape: str, relevant: set[str]) -> None:
    for sid in SIZE_SLIDERS:
        expected_disabled = sid not in relevant
        assert slider_disabled(sid, RadiometricRegime.SUB_PIXEL, shape) is expected_disabled  # type: ignore[arg-type]


def test_relevant_table_publishes_each_shape() -> None:
    """Sanity: every dropdown shape has an entry in the relevance table."""
    assert set(SHAPE_RELEVANT_SIZES.keys()) == {
        "sphere",
        "cylinder",
        "flat_plate",
        "box",
        "cone",
    }


# ---------------------------------------------------------------------------
# Orientation sliders are inert for sphere only
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("axis", ["tgt-yaw", "tgt-pitch", "tgt-roll"])
def test_orientation_disabled_for_sphere(axis: str) -> None:
    assert slider_disabled(axis, RadiometricRegime.SUB_PIXEL, "sphere") is True  # type: ignore[arg-type]


@pytest.mark.parametrize("shape", ["cylinder", "flat_plate", "box", "cone"])
def test_orientation_enabled_for_non_sphere(shape: str) -> None:
    for axis in ("tgt-yaw", "tgt-pitch", "tgt-roll"):
        assert slider_disabled(axis, RadiometricRegime.SUB_PIXEL, shape) is False  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# EXTENDED & POINT_SOURCE disable every size + orientation slider
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "regime", [RadiometricRegime.EXTENDED, RadiometricRegime.POINT_SOURCE]
)
def test_extended_or_point_source_disables_all_shape_sliders(
    regime: RadiometricRegime,
) -> None:
    for sid in TARGET_DISABLE_IDS:
        assert slider_disabled(sid, regime, "box") is True


# ---------------------------------------------------------------------------
# Shape-dropdown grey-out rule
# ---------------------------------------------------------------------------


def test_shape_dropdown_disabled_only_in_extended() -> None:
    assert shape_dropdown_disabled(RadiometricRegime.EXTENDED) is True
    assert shape_dropdown_disabled(RadiometricRegime.POINT_SOURCE) is False
    assert shape_dropdown_disabled(RadiometricRegime.SUB_PIXEL) is False
