"""GeometryStage — stage 0: resolve, validate, and publish scene geometry.

Runs before SourceStage (ADR-0006).  Emits no radiometric frames: its
entire product is ``stage_outputs["geometry"]`` — the validated,
mode-resolved scene geometry that every downstream stage consumes
instead of re-deriving:

    los_geometry        LineOfSightGeometry (h_tgt, h_sensor, θ_o, θ_s, Δφ)
                        — the Source → Atmosphere contract object
                        (ADR-0002), now built here.  Both endpoints are
                        always carried (ADR-0011 / GF-3), so the contract
                        object owns the horizon guard and the direction.
    theta_o_rad         canonical target-side path zenith, closed domain
                        [0, π] — obtuse for an up-looking scene
    los_direction       "down" | "up" | "level", read off the LOS object
                        (derived from the altitudes, never a user switch —
                        ADR-0011 decision 1)
    eta_rad             sensor-side off-nadir angle (spherical sine rule)
    slant_range_m       target ↔ sensor slant range (spherical triangle)
    ground_range_m      surface arc, nadir point → target
    incidence_angle_rad angle between LOS and the target's local vertical
                        (identically θ_o on a spherical Earth)
    target_range_m      user-declared slant range (V0), or None
    h_sensor_m / h_target_m
    scene_class         derived observer×target altitude-band label, e.g.
                        "ground_to_air" (ADR-0011 decision 8) — drives
                        defaults, metric relevance, validation and GUI
                        composition; physics NEVER branches on it
    observer_class / target_class
                        the two pieces of scene_class ("ground"/"air"/"space")
    theta_s_rad / delta_phi_rad / solar_illumination
    ground_speed_m_s / orbital_period_s (circular-orbit mode only)
    los_angular_rate_rad_s
                        relative LOS angular rate (Gap 111); None only for
                        coincident endpoints.  With no kinematics input set
                        it is the platform-only value ground_speed / slant
    viewing_mode / solar_mode / kinematics_mode / los_rate_mode
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
    check_range_consistency,
    resolve_kinematics,
    resolve_los_rate,
    resolve_solar,
    resolve_viewing,
)
from radiant.geometry.scene_class import (
    check_scene_class_assertion,
    derive_scene_class,
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
        # CU-093: user range vs angle-implied slant — raise on explicit
        # contradiction, warn on range-vs-defaulted-geometry mismatch.
        check_range_consistency(params, viewing)

        raw_range: float = float(params.get("geometry.target_range_m"))
        target_range_m: float | None = raw_range if raw_range > 0.0 else None

        # Both endpoints, always (ADR-0011 / GF-3): h_sensor is what lets the
        # contract object enforce the altitude/hemisphere invariant and run
        # the full two-topology horizon guard instead of the conservative
        # angular band a pre-ADR-0011 payload was limited to.
        los = LineOfSightGeometry(
            h_tgt=viewing.h_target_m,
            h_sensor=viewing.h_sensor_m,
            theta_o=viewing.theta_o_rad,
            theta_s=solar.theta_s_rad,
            delta_phi=solar.delta_phi_rad,
        )

        # Derived scene class (ADR-0011 decision 8) — a label, never an input.
        # The direction comes off the LOS object so there is one definition of
        # it; the optional user assertion is validated against the derivation
        # (CU-093 redundant-entry pattern) and is never required.
        scene = derive_scene_class(viewing.h_sensor_m, viewing.h_target_m, los.los_direction)
        check_scene_class_assertion(
            str(params.get("geometry.scene_class")),
            scene,
            viewing.h_sensor_m,
            viewing.h_target_m,
        )

        los_rate = resolve_los_rate(params, viewing, kinematics)

        logger.debug(
            "GeometryStage: viewing=%s (%s) solar=%s kinematics=%s theta_o=%.6f rad slant=%s m",
            viewing.mode,
            viewing.direction,
            solar.mode,
            kinematics.mode,
            viewing.theta_o_rad,
            viewing.slant_range_m,
        )

        for key, value in (
            ("los_geometry", los),
            # Derived, never declared (ADR-0011 decision 1).  Read straight
            # off the contract object so there is exactly one definition of
            # the direction; the scene class below carries this same value.
            ("los_direction", los.los_direction),
            ("theta_o_rad", viewing.theta_o_rad),
            ("eta_rad", viewing.eta_rad),
            ("slant_range_m", viewing.slant_range_m),
            ("ground_range_m", viewing.ground_range_m),
            # On a spherical Earth the incidence angle at the target
            # (LOS vs local vertical) IS the target-side zenith; None in
            # the collocated (no-triangle) case, like the ranges.
            (
                "incidence_angle_rad",
                viewing.theta_o_rad if viewing.slant_range_m is not None else None,
            ),
            ("target_range_m", target_range_m),
            ("h_sensor_m", viewing.h_sensor_m),
            ("h_target_m", viewing.h_target_m),
            ("theta_s_rad", solar.theta_s_rad),
            ("delta_phi_rad", solar.delta_phi_rad),
            ("solar_illumination", params.get("geometry.solar_illumination")),
            ("ground_speed_m_s", kinematics.ground_speed_m_s),
            ("orbital_period_s", kinematics.orbital_period_s),
            # Derived scene class (ADR-0011 decision 8): a label consumed by
            # metric relevance, defaults, validation, and the GUI — never by
            # physics.  Published alongside its two pieces.
            ("scene_class", scene.key),
            ("observer_class", scene.observer_class),
            ("target_class", scene.target_class),
            # LOS angular rate (Gap 111).  With no kinematics input this is
            # the platform-only value ground_speed / slant that the smear arm
            # already derives; None only for coincident endpoints.
            ("los_angular_rate_rad_s", los_rate.los_angular_rate_rad_s),
            ("viewing_mode", viewing.mode),
            ("solar_mode", solar.mode),
            ("kinematics_mode", kinematics.mode),
            ("los_rate_mode", los_rate.mode),
        ):
            state = state.with_stage_output("geometry", key, value)
        return state
