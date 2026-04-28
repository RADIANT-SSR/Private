"""Phase 4 regime-classifier branch tests.

Five parameterized states, each forcing one Rule-10 branch in
`view_model.classify_regime`. The test pins the exact reason string so
GUI display copy stays stable.
"""

from __future__ import annotations

import dataclasses
import math

import pytest

from radiant.core.regime import RadiometricRegime

from dev_tools.geometry_gui_v2.app.state import SceneState
from dev_tools.geometry_gui_v2.app.view_model import (
    _angular_extent_rad,
    classify_regime,
)


def _state(**overrides: object) -> SceneState:
    return dataclasses.replace(SceneState.default(), **overrides)


# ---------------------------------------------------------------------------
# Manual override branch — radio set to anything other than "auto"
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "override, expected_regime",
    [
        ("extended", RadiometricRegime.EXTENDED),
        ("sub_pixel", RadiometricRegime.SUB_PIXEL),
        ("point_source", RadiometricRegime.POINT_SOURCE),
    ],
)
def test_manual_override_branch(
    override: str, expected_regime: RadiometricRegime
) -> None:
    """`regime_override != 'auto'` → return that regime, reason names the override."""
    state = _state(regime_override=override)  # type: ignore[arg-type]
    regime, reason = classify_regime(state)
    assert regime is expected_regime
    assert reason == f"user override: {override}"


# ---------------------------------------------------------------------------
# fill_fraction < 1 forces sub-pixel
# ---------------------------------------------------------------------------


def test_fill_fraction_lt_one_forces_sub_pixel() -> None:
    state = _state(target_fill_fraction=0.42)
    regime, reason = classify_regime(state)
    assert regime is RadiometricRegime.SUB_PIXEL
    assert reason == "fill_fraction = 0.420 < 1.0"


# ---------------------------------------------------------------------------
# Geometry-driven branches (regime_override="auto", fill_fraction=1.0)
# ---------------------------------------------------------------------------


def test_angular_extent_extended_branch() -> None:
    """Large flat plate viewed normal → ang_ext ≥ 2*ifov → EXTENDED."""
    state = _state(
        target_shape="flat_plate",
        target_length_m=15.0,
        target_width_m=15.0,
    )
    regime, reason = classify_regime(state)
    assert regime is RadiometricRegime.EXTENDED
    assert reason == "ang_ext >= 2*ifov"


def test_angular_extent_point_source_branch() -> None:
    """Tiny flat plate viewed normal → ang_ext ≤ 0.25*ifov → POINT_SOURCE."""
    state = _state(
        target_shape="flat_plate",
        target_length_m=1.0,
        target_width_m=1.0,
    )
    regime, reason = classify_regime(state)
    assert regime is RadiometricRegime.POINT_SOURCE
    assert reason == "ang_ext <= 0.25*ifov"


def test_angular_extent_sub_pixel_branch() -> None:
    """In-between regime → 0.25*ifov < ang_ext < 2*ifov → SUB_PIXEL."""
    state = _state(target_shape="sphere", target_radius_m=2.0)
    regime, reason = classify_regime(state)
    assert regime is RadiometricRegime.SUB_PIXEL
    assert reason == "0.25*ifov < ang_ext < 2*ifov"


# ---------------------------------------------------------------------------
# Numerical truth anchors — Phase 4 prompt §"Report"
# ---------------------------------------------------------------------------


def test_truth_anchor_extended() -> None:
    """Hand-compute angular_extent and ifov for the extended-state case.

    State: 600 km altitude, 20° look, 15 m × 15 m flat plate, normal incidence.
      slant   = 600_000 / cos(20°)            ≈ 638_507.27 m
      A       = 15 * 15                        = 225.0 m²
      ang_ext = sqrt(225) / 638_507.27         ≈ 2.349e-5 rad
      ifov    = 10e-6 / 1.0                    = 1.000e-5 rad
      ratio   = ang_ext / ifov                 ≈ 2.349    >= 2.0 → EXTENDED
    """
    state = _state(
        target_shape="flat_plate",
        target_length_m=15.0,
        target_width_m=15.0,
    )

    slant_expected = 600_000.0 / math.cos(math.radians(20.0))
    A_expected = 15.0 * 15.0
    ang_ext_expected = math.sqrt(A_expected) / slant_expected
    ifov_expected = 10e-6 / 1.0

    assert _angular_extent_rad(state) == pytest.approx(ang_ext_expected, rel=1e-9)
    assert ang_ext_expected / ifov_expected >= 2.0  # branch sanity
    regime, _ = classify_regime(state)
    assert regime is RadiometricRegime.EXTENDED


def test_truth_anchor_sub_pixel() -> None:
    """Hand-compute angular_extent and ifov for the sub-pixel state.

    State: defaults, sphere R = 2 m.
      slant   = 600_000 / cos(20°)            ≈ 638_507.27 m
      A       = π * 2² = 4π                    ≈ 12.566 m²
      ang_ext = sqrt(4π) / slant               ≈ 5.553e-6 rad
      ifov    = 10e-6                           = 1.000e-5 rad
      ratio   = ang_ext / ifov                 ≈ 0.5553   ∈ (0.25, 2.0) → SUB_PIXEL
    """
    state = _state(target_shape="sphere", target_radius_m=2.0)

    slant_expected = 600_000.0 / math.cos(math.radians(20.0))
    A_expected = math.pi * 4.0
    ang_ext_expected = math.sqrt(A_expected) / slant_expected
    ifov_expected = 10e-6

    assert _angular_extent_rad(state) == pytest.approx(ang_ext_expected, rel=1e-9)
    ratio = ang_ext_expected / ifov_expected
    assert 0.25 < ratio < 2.0  # branch sanity
    regime, _ = classify_regime(state)
    assert regime is RadiometricRegime.SUB_PIXEL
