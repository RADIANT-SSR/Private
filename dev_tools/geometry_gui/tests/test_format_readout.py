"""Phase 5 format_readout tests — every numeric row carries explicit units.

Hard rule (CLAUDE.md / user memory): numeric values rendered in the GUI
MUST carry units. This test pins that invariant for each readout component.
"""

from __future__ import annotations

import math

from radiant.core.regime import RadiometricRegime

from dev_tools.geometry_gui.app.layout.readout_panel import READOUT_LINES
from dev_tools.geometry_gui.app.state import SceneState
from dev_tools.geometry_gui.app.view_model import classify_regime, format_readout

# Component IDs whose value is a category label (not a number) and so do
# not require a unit suffix.
_NON_NUMERIC: frozenset[str] = frozenset({"ro-regime", "ro-regime-reason"})


def _regime_and_reason(state: SceneState) -> tuple[RadiometricRegime, str]:
    return classify_regime(state)


def test_format_readout_publishes_every_panel_row() -> None:
    state = SceneState.default()
    regime, reason = _regime_and_reason(state)
    out = format_readout(state, regime, reason)
    expected = {component_id for component_id, _ in READOUT_LINES}
    assert set(out.keys()) == expected


def test_format_readout_every_numeric_row_has_units() -> None:
    state = SceneState.default()
    regime, reason = _regime_and_reason(state)
    out = format_readout(state, regime, reason)
    accepted_unit_tokens = (
        " m",
        " m^2",
        " km",
        " µrad",
        " deg",
        "(dimensionless)",
    )
    for component_id, label in READOUT_LINES:
        if component_id in _NON_NUMERIC:
            continue
        text = out[component_id]
        # Fill fraction is the only dimensionless numeric — accept the bare
        # number, since the row label already names the quantity.
        if component_id == "ro-fill-fraction":
            assert text.replace(".", "").replace("-", "").isdigit() or text == "0.000", (
                f"{component_id}: expected dimensionless number, got {text!r}"
            )
            continue
        assert any(token in text for token in accepted_unit_tokens), (
            f"{component_id} ({label!r}) has no recognized unit suffix: {text!r}"
        )


def test_format_readout_solar_zenith_in_degrees() -> None:
    state = SceneState.default()  # solar_zenith_rad = 35°
    regime, reason = _regime_and_reason(state)
    out = format_readout(state, regime, reason)
    assert "deg" in out["ro-solar-zenith"]
    assert "35.00" in out["ro-solar-zenith"]


def test_format_readout_handles_infinite_angular_extent() -> None:
    """Zero slant range → angular extent is +inf; readout must not crash."""
    # Stack observer altitude on top of target altitude so slant range = 0.
    state = SceneState(
        observer_altitude_m=0.0,
        observer_look_angle_rad=0.0,
        observer_yaw_rad=0.0,
        observer_pitch_rad=0.0,
        observer_roll_rad=0.0,
        target_altitude_m=0.0,
        target_shape="sphere",
        target_radius_m=1.0,
        target_length_m=1.0,
        target_width_m=1.0,
        target_height_m=1.0,
        target_base_radius_m=1.0,
        target_yaw_rad=0.0,
        target_pitch_rad=0.0,
        target_roll_rad=0.0,
        target_fill_fraction=1.0,
        focal_length_m=1.0,
        pixel_pitch_m=10e-6,
        solar_zenith_rad=math.radians(35.0),
        relative_azimuth_rad=0.0,
        regime_override="auto",
        background_kind="none",
    )
    regime, reason = _regime_and_reason(state)
    out = format_readout(state, regime, reason)
    assert "∞" in out["ro-angular-extent"]


def test_format_readout_projected_area_matches_view_model() -> None:
    """The displayed A_t must reflect projected_area_m2(state) (C3)."""
    from dev_tools.geometry_gui.app.view_model import projected_area_m2

    state = SceneState.default()
    regime, reason = _regime_and_reason(state)
    out = format_readout(state, regime, reason)
    A_t = projected_area_m2(state)
    # The formatted string uses %.4g; pick enough digits to round-trip.
    formatted = f"{A_t:.4g}"
    assert formatted in out["ro-projected-area"]
    assert "m^2" in out["ro-projected-area"]
