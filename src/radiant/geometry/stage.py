"""GeometryStage — stage 0: resolve, validate, and publish scene geometry.

Runs before SourceStage (ADR-0006).  Emits no radiometric frames: its
entire product is ``stage_outputs["geometry"]`` — the validated,
mode-resolved scene geometry that every downstream stage consumes
instead of re-deriving:

    los_geometry        LineOfSightGeometry (h_tgt, θ_o, θ_s, Δφ) — the
                        Source → Atmosphere contract object (ADR-0002),
                        now built here
    theta_o_rad         canonical target-side path zenith
    eta_rad             sensor-side off-nadir angle (spherical sine rule)
    slant_range_m       target ↔ sensor slant range (spherical triangle)
    ground_range_m      surface arc, nadir point → target
    incidence_angle_rad angle between LOS and the target's local vertical
                        (identically θ_o on a spherical Earth)
    target_range_m      user-declared slant range (V0), or None
    h_sensor_m / h_target_m
    theta_s_rad / delta_phi_rad / solar_illumination
    ground_speed_m_s / orbital_period_s (circular-orbit mode only)
    viewing_mode / solar_mode / kinematics_mode
                        which input mode produced each family — surfaced
                        by result.inspect() and the GUI

Derivations happen exactly once, here.  Consistency between redundant
user inputs is enforced in :mod:`radiant.geometry.modes` (ADR-0006
rule 2); physical bounds live on the schema and in
:class:`~radiant.core.los_geometry.LineOfSightGeometry`.

Solar note: θ_s is published as *scene* geometry whenever the scene is
lit (day mode).  Whether a given target type consumes the solar terms
(T1 thermal targets do not) remains SourceStage's descriptor-level
decision — scene geometry describes where the sun is, not whether a
material reflects it.
"""

from __future__ import annotations

import logging

from radiant.core.chain import ChainState
from radiant.core.los_geometry import LineOfSightGeometry
from radiant.core.parameters import ParameterSet
from radiant.geometry.modes import (
    resolve_kinematics,
    resolve_solar,
    resolve_viewing,
)

logger = logging.getLogger(__name__)


class GeometryStage:
    """Stage 0 — canonical scene geometry (pure function, Rule 6)."""

    @property
    def name(self) -> str:
        return "geometry"

    def run(self, state: ChainState, params: ParameterSet) -> ChainState:
        viewing = resolve_viewing(params)
        solar = resolve_solar(params)
        kinematics = resolve_kinematics(params)

        raw_range: float = float(params.get("geometry.target_range_m"))
        target_range_m: float | None = raw_range if raw_range > 0.0 else None

        los = LineOfSightGeometry(
            h_tgt=viewing.h_target_m,
            theta_o=viewing.theta_o_rad,
            theta_s=solar.theta_s_rad,
            delta_phi=solar.delta_phi_rad,
        )

        logger.debug(
            "GeometryStage: viewing=%s solar=%s kinematics=%s theta_o=%.6f rad slant=%.1f m",
            viewing.mode,
            solar.mode,
            kinematics.mode,
            viewing.theta_o_rad,
            viewing.slant_range_m,
        )

        for key, value in (
            ("los_geometry", los),
            ("theta_o_rad", viewing.theta_o_rad),
            ("eta_rad", viewing.eta_rad),
            ("slant_range_m", viewing.slant_range_m),
            ("ground_range_m", viewing.ground_range_m),
            # On a spherical Earth the incidence angle at the target
            # (LOS vs local vertical) IS the target-side zenith.
            ("incidence_angle_rad", viewing.theta_o_rad),
            ("target_range_m", target_range_m),
            ("h_sensor_m", viewing.h_sensor_m),
            ("h_target_m", viewing.h_target_m),
            ("theta_s_rad", solar.theta_s_rad),
            ("delta_phi_rad", solar.delta_phi_rad),
            ("solar_illumination", params.get("geometry.solar_illumination")),
            ("ground_speed_m_s", kinematics.ground_speed_m_s),
            ("orbital_period_s", kinematics.orbital_period_s),
            ("viewing_mode", viewing.mode),
            ("solar_mode", solar.mode),
            ("kinematics_mode", kinematics.mode),
        ):
            state = state.with_stage_output("geometry", key, value)
        return state
