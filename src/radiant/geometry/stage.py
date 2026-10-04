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
    sensor_speed_m_s / sensor_speed_mode
                        the speed the LOS-rate model puts on the SENSOR
                        endpoint, and which door produced it (CU-391).
                        Equal to ground_speed_m_s unless
                        geometry.sensor_speed_m_s stated the platform's
                        inertial speed — the quantity that belongs when the
                        target is not Earth-fixed
    los_angular_rate_rad_s
                        relative LOS angular rate (Gap 111); None only for
                        coincident endpoints.  With no kinematics input set
                        it is the platform-only value sensor_speed / slant
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
from radiant.core.orbit import orbital_velocity_m_s
from radiant.core.parameters import ParameterSet
from radiant.geometry.errors import GeometrySpecificationError
from radiant.geometry.modes import (
    GROUND_TRACK_SENSOR_SPEED_MODE,
    KinematicsResolution,
    LosRateResolution,
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


def _check_site_elevation_consistency(
    params: ParameterSet,
    los_direction: str,
    h_sensor_m: float,
    h_target_m: float,
) -> None:
    """The terrain-bearing endpoint must sit on or above its own terrain (Rule 16).

    ``geometry.site_elevation_m`` is the terrain under the topology-dependent
    site (schema: down-looking = under the TARGET, up-looking = under the
    SENSOR, level = shared). An endpoint below that terrain is underground —
    a mis-entered config that used to pass this stage silently and surface
    only inside ``cn2()`` when an HV profile was selected (October sweep,
    ex-CU-303). The far endpoint is deliberately unconstrained: a valley
    sensor viewing a mountain-top target is physical.
    """
    site_m: float = float(params.get("geometry.site_elevation_m"))
    if site_m <= 0.0:
        return
    checks: list[tuple[str, float]] = []
    if los_direction == "down":
        checks.append(("target", h_target_m))
    elif los_direction == "up":
        checks.append(("sensor", h_sensor_m))
    else:  # level — the terrain is shared by both endpoints
        checks.append(("sensor", h_sensor_m))
        checks.append(("target", h_target_m))
    for endpoint, altitude_m in checks:
        if altitude_m < site_m:
            raise GeometrySpecificationError(
                what=(
                    f"the {endpoint} altitude ({altitude_m:.1f} m MSL) is below its "
                    f"own terrain (geometry.site_elevation_m = {site_m:.1f} m)"
                ),
                why=(
                    "site_elevation_m is the terrain under the "
                    f"{endpoint} for a {los_direction}-looking scene — an endpoint "
                    "below it is underground, not a physical viewing geometry"
                ),
                action=(
                    f"raise geometry.{endpoint}_altitude_m to at least the site "
                    "elevation, or correct geometry.site_elevation_m"
                ),
                context={
                    "los_direction": los_direction,
                    "endpoint": endpoint,
                    "altitude_m": altitude_m,
                    "site_elevation_m": site_m,
                },
            )


def _refuse_ground_track_speed_against_a_space_target(
    kinematics: KinematicsResolution,
    los_rate: LosRateResolution,
    target_class: str,
    h_sensor_m: float,
) -> None:
    """Refuse a LOS rate built on the ground-track speed for a space target (CU-391).

    The sensor endpoint's velocity in ``omega = |v_rel,perp| / R`` defaults to
    the sub-satellite **ground-track** speed ``v*R_E/a``, which is the right
    quantity only for an **Earth-fixed** target seen from a nadir-stabilised
    platform (``d_eta/dt = v_g/h``).  Against a target that is not Earth-fixed
    the platform's **inertial** speed belongs, and the target's own orbital
    motion subtracts from it.  Neither correction is derivable from
    ``sensor_altitude_m``: the target's velocity would require assuming a
    co-planar, co-rotating circular orbit the analyst never stated.

    The difference is not small, and not conservative in either direction. On a
    500 km LEO staring at the geostationary belt the ground-track default
    publishes 200.1 urad/s against a correct 128.7 (+55.5 %), and supplying
    only the sensor's inertial speed gives 215.85 — *further* from correct,
    because 62 % of the discrepancy is the target's own co-rotating motion.
    That rate feeds ``smear_width_m``, the smear MTF, EE_box, SNR and detection
    range, so the error reaches every spatial and radiometric result.

    This was a ``UserWarning`` when the sensor-speed door landed (2026-10-01).
    Owner ruling 2026-10-03: **refuse instead**. A warning is scrollable, and
    the published number is wrong by tens of percent in a quantity the analyst
    is likely reading downstream; an unstated velocity frame is an
    under-specified scene, which is what this error class is for (Rule 16 —
    validate before compute).  Scene class gates only the *validation*, never
    the physics (ADR-0011 decision 8) — exactly as the warning did.
    """
    if target_class != "space":
        return
    if los_rate.los_angular_rate_rad_s is None:
        return
    if "geometry.los_angular_rate_rad_s" in los_rate.mode:
        return  # K1 entered the rate directly — the velocity model is unused.
    if kinematics.sensor_speed_mode != GROUND_TRACK_SENSOR_SPEED_MODE:
        return  # the door is open; the analyst stated the sensor's speed.
    if kinematics.sensor_speed_m_s <= 0.0:
        return  # a static platform has nothing to mis-attribute.
    v_inertial = orbital_velocity_m_s(h_sensor_m) if h_sensor_m > 0.0 else None
    inertial_clause = (
        f"geometry.sensor_speed_m_s = {v_inertial:.1f} (the circular-orbit "
        f"inertial speed at {h_sensor_m:.0f} m)"
        if v_inertial is not None
        else "geometry.sensor_speed_m_s = the platform's inertial speed"
    )
    raise GeometrySpecificationError(
        what=(
            "the line-of-sight angular rate would be built on the sub-satellite "
            f"ground-track speed ({kinematics.sensor_speed_m_s:.1f} m/s), but this "
            "scene's target is in space and therefore not Earth-fixed"
        ),
        why=(
            "the ground-track speed v*R_E/a is the correct LOS-rate scaling only "
            "for an Earth-fixed target seen from a nadir-stabilised platform. For "
            "a space target the platform's INERTIAL speed belongs, and the "
            "target's own orbital motion subtracts from it. RADIANT cannot supply "
            "either from the altitude alone — the target's velocity would require "
            "assuming a co-planar, co-rotating circular orbit you have not stated "
            "— and the resulting rate drives smear, EE_box, SNR and detection "
            "range, so it cannot be published on a guess"
        ),
        action=(
            f"state the velocities: set {inertial_clause}, together with "
            "geometry.target_speed_m_s / target_heading_rad / target_climb_rad "
            "for the target's own motion; or enter the rate directly with "
            "geometry.los_angular_rate_rad_s. Note that supplying only the "
            "sensor's inertial speed moves the answer FURTHER from correct when "
            "the target co-rotates, so enter both endpoints"
        ),
        context={
            "target_class": target_class,
            "sensor_speed_m_s": kinematics.sensor_speed_m_s,
            "sensor_speed_mode": kinematics.sensor_speed_mode,
            "sensor_inertial_speed_m_s": v_inertial,
            "h_sensor_m": h_sensor_m,
            "los_rate_mode": los_rate.mode,
        },
    )


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

        _check_site_elevation_consistency(
            params, los.los_direction, viewing.h_sensor_m, viewing.h_target_m
        )

        los_rate = resolve_los_rate(params, viewing, kinematics)
        # CU-391: the ground-track default is right for an Earth-fixed target
        # and wrong for a space one — refuse rather than publish it (owner
        # ruling 2026-10-03; it was a UserWarning until then).
        _refuse_ground_track_speed_against_a_space_target(
            kinematics, los_rate, scene.target_class, viewing.h_sensor_m
        )

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
            # CU-391: the speed the LOS-rate model puts on the SENSOR endpoint
            # — the ground-track speed above unless geometry.sensor_speed_m_s
            # stated the platform's inertial speed instead.
            ("sensor_speed_m_s", kinematics.sensor_speed_m_s),
            ("sensor_speed_mode", kinematics.sensor_speed_mode),
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
