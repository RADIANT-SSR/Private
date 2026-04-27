"""SceneState — the frozen view-model input.

One field per slider on the GUI. All angles in radians, all lengths in meters,
matching RADIANT's canonical units (CLAUDE.md §"Units"). Conversion from
slider-display units (deg, km, µm) happens in the Dash callback layer in
Phase 3 — never inside this file or `view_model.py`.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal

ShapeKind = Literal["sphere", "cylinder", "flat_plate", "box", "cone"]
RegimeOverride = Literal["auto", "extended", "sub_pixel", "point_source"]
BackgroundKind = Literal["none", "cold_space", "ground", "at_aperture"]


@dataclass(frozen=True)
class SceneState:
    """All slider inputs, in canonical units.

    Phases 2+ derive every plotly trace, every readout value, and every
    classification decision from this dataclass. There is no hidden state
    elsewhere.
    """

    observer_altitude_m: float
    observer_look_angle_rad: float
    observer_yaw_rad: float
    observer_pitch_rad: float
    observer_roll_rad: float

    target_altitude_m: float
    target_shape: ShapeKind
    target_radius_m: float
    target_length_m: float
    target_width_m: float
    target_height_m: float
    target_base_radius_m: float
    target_yaw_rad: float
    target_pitch_rad: float
    target_roll_rad: float
    target_fill_fraction: float

    focal_length_m: float
    pixel_pitch_m: float

    solar_zenith_rad: float
    relative_azimuth_rad: float

    regime_override: RegimeOverride
    background_kind: BackgroundKind

    @classmethod
    def default(cls) -> SceneState:
        """LEO-ish baseline: 600 km altitude, 20° look, 1 m sphere on the ground."""
        return cls(
            observer_altitude_m=600_000.0,
            observer_look_angle_rad=math.radians(20.0),
            observer_yaw_rad=0.0,
            observer_pitch_rad=0.0,
            observer_roll_rad=0.0,
            target_altitude_m=0.0,
            target_shape="sphere",
            target_radius_m=1.0,
            target_length_m=2.0,
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
            relative_azimuth_rad=math.radians(12.0),
            regime_override="auto",
            background_kind="none",
        )
