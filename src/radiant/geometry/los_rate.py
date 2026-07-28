r"""Relative line-of-sight angular rate — the moving-target/moving-platform ω (Gap 111).

One computation (Rule 19): the angular rate at which the sensor↔target line of
sight rotates, given the relative velocity of the two endpoints and their
separation.  The rate itself is elementary rigid-kinematics —

.. math::

    \omega = \frac{\lvert \mathbf{v}_{rel,\perp} \rvert}{R},
    \qquad
    \mathbf{v}_{rel} = \mathbf{v}_{target} - \mathbf{v}_{sensor},

where :math:`\mathbf{v}_{rel,\perp}` is the component of the relative velocity
perpendicular to the LOS (the parallel component changes the *range*, not the
*direction*) and :math:`R` is the slant range.  The component along the LOS is
removed exactly, so a purely receding or approaching target gives ω = 0 and a
purely crossing target at range R gives ω = v/R.

Frame (target-local, and deliberately the frame RADIANT already uses)
---------------------------------------------------------------------
Angles are expressed in the target's local horizontal frame, with the
**observer's ground azimuth as the zero** — exactly the convention behind
``delta_phi`` (:math:`\Delta\varphi = \varphi_s - \varphi_o`, i.e.
:math:`\varphi_o \equiv 0`).  The right-handed triad is

* :math:`\hat{e}_\parallel` — horizontal, in the LOS vertical plane, pointing
  from the target's ground point toward the **sensor's** ground point
  (azimuth 0, the same zero ``delta_phi`` measures the sun from);
* :math:`\hat{e}_\perp = \hat{e}_{up} \times \hat{e}_\parallel` — horizontal,
  perpendicular to that plane (azimuth +90°, i.e. the same rotational sense in
  which :math:`\Delta\varphi` increases: counter-clockwise seen from above);
* :math:`\hat{e}_{up}` — the target's local vertical.

In this frame the unit LOS from target to sensor is

.. math::  \hat{u} = \sin\theta_o \, \hat{e}_\parallel + \cos\theta_o \, \hat{e}_{up}

for the canonical target-side path zenith :math:`\theta_o \in [0, \pi]` — valid
for down-looking (:math:`\cos\theta_o > 0`), level, and up-looking
(:math:`\cos\theta_o < 0`) scenes alike, since :math:`\sin\theta_o \ge 0` on the
whole closed domain (ADR-0011).

**Target velocity** is entered as speed + heading + climb:

.. math::

    \mathbf{v}_T = v_T \left(
        \cos\gamma \cos\psi \, \hat{e}_\parallel
      + \cos\gamma \sin\psi \, \hat{e}_\perp
      + \sin\gamma \, \hat{e}_{up} \right)

with heading :math:`\psi` (``geometry.target_heading_rad``) measured in the
target's horizontal plane from :math:`\hat{e}_\parallel` — so ψ = 0 is a target
moving horizontally *toward the sensor's ground point*, ψ = π away from it —
and climb :math:`\gamma` (``geometry.target_climb_rad``) measured from that
horizontal plane, positive upward.

**Sensor velocity** is taken as :math:`\mathbf{v}_S = v_g \hat{e}_\perp`: the
platform's ground-track velocity, **cross-track** with respect to the LOS
azimuth plane.  Two simplifications are being made here, and both are
deliberate:

1. *Direction.*  RADIANT has no ground-track-azimuth parameter — the platform
   is described by a scalar ``geometry.ground_speed_m_s`` (or the circular-orbit
   derivation).  The cross-track choice is the standard push-broom geometry
   that ``platform/smear.py`` already assumes (it uses ω = v/R with no
   projection factor, which is the exact rate only when the velocity is
   perpendicular to the LOS), so adopting it here makes the platform-only limit
   of this module reduce **exactly** to the rate the smear arm already derives,
   for every down-looking geometry rather than only at nadir.  An *along-track*
   off-boresight look has the smaller rate :math:`v_g \cos^2\eta / h`; expressing
   it needs a track-azimuth input this stage does not yet have.
2. *Magnitude.*  ``ground_speed_m_s`` is the **ground-track** speed
   (:math:`v R_E / a` for a circular orbit — ``core.orbit``), not the inertial
   orbital speed.  That is the correct scaling for the LOS rate seen by a
   nadir-stabilised platform: with the sensor at central-angle rate
   :math:`\omega_o = v/a`, a fixed ground target's off-boresight angle changes at
   :math:`\mathrm{d}\eta/\mathrm{d}t = R_E \omega_o / h = v_g / h`.  It is the
   same quantity ``platform.ground_velocity_m_s`` carries (Gap 75 collapse), so
   the two arms of the model cannot disagree.

Degenerate case
---------------
A zero (or absent) slant range means the endpoints are coincident: there is no
line of sight, so there is no direction for it to rotate in and ω is undefined
rather than large.  This raises an actionable error (Rule 17) instead of
returning ``inf`` or silently substituting zero; the caller
(:func:`radiant.geometry.modes.resolve_los_rate`) decides when that is reachable.
"""

from __future__ import annotations

import math

from radiant.geometry.errors import GeometrySpecificationError

__all__ = [
    "relative_los_angular_rate_rad_s",
    "relative_velocity_m_s",
]


def _require_finite(name: str, value: float) -> None:
    if not math.isfinite(value):
        raise GeometrySpecificationError(
            what=f"relative LOS rate: {name} = {value} is not finite",
            why="A non-finite kinematic input cannot produce a meaningful angular rate.",
            action=f"Set {name} to a finite value.",
            context={name: value},
        )


def relative_velocity_m_s(
    *,
    sensor_ground_speed_m_s: float = 0.0,
    target_speed_m_s: float = 0.0,
    target_heading_rad: float = 0.0,
    target_climb_rad: float = 0.0,
) -> tuple[float, float, float]:
    """Relative velocity ``v_target − v_sensor`` in the target-local triad [m/s].

    Returns the components along ``(ê_∥, ê_⊥, ê_up)`` as defined in the module
    docstring: ``ê_∥`` horizontal toward the sensor's ground point, ``ê_⊥``
    horizontal at +90° (the sensor's ground-track direction), ``ê_up`` the
    target's local vertical.

    Parameters
    ----------
    sensor_ground_speed_m_s:
        Platform ground-track speed [m/s], along ``+ê_⊥`` (cross-track).
        Must be non-negative.
    target_speed_m_s:
        Target speed [m/s].  Must be non-negative.
    target_heading_rad:
        Target heading [rad] from ``ê_∥`` toward ``ê_⊥``.
    target_climb_rad:
        Target climb angle [rad] above the local horizontal, positive up.
        Must lie in ``[−π/2, π/2]``.

    Raises
    ------
    GeometrySpecificationError
        On a non-finite input, a negative speed, or a climb angle outside
        ``[−π/2, π/2]``.
    """
    for name, value in (
        ("sensor_ground_speed_m_s", sensor_ground_speed_m_s),
        ("target_speed_m_s", target_speed_m_s),
        ("target_heading_rad", target_heading_rad),
        ("target_climb_rad", target_climb_rad),
    ):
        _require_finite(name, value)
    for name, value in (
        ("sensor_ground_speed_m_s", sensor_ground_speed_m_s),
        ("target_speed_m_s", target_speed_m_s),
    ):
        if value < 0.0:
            raise GeometrySpecificationError(
                what=f"relative LOS rate: {name} = {value} m/s is negative",
                why=(
                    "Speeds are magnitudes; a reversed direction is expressed by "
                    "the heading (and climb) angle, not by a negative speed."
                ),
                action=f"Set {name} >= 0 and rotate the heading by π to reverse it.",
                context={name: value},
            )
    if not (-math.pi / 2.0 <= target_climb_rad <= math.pi / 2.0):
        raise GeometrySpecificationError(
            what=(
                f"relative LOS rate: target_climb_rad = {target_climb_rad} rad "
                f"({math.degrees(target_climb_rad):.3f}°) is outside [−π/2, π/2]"
            ),
            why=(
                "The climb angle is the velocity's elevation above the local "
                "horizontal; ±π/2 is straight up / straight down and nothing "
                "outside that is an elevation."
            ),
            action="Set target_climb_rad in [−π/2, π/2] rad (−90°…+90°).",
            context={"target_climb_rad": target_climb_rad},
        )

    cos_climb = math.cos(target_climb_rad)
    v_par = target_speed_m_s * cos_climb * math.cos(target_heading_rad)
    v_perp = target_speed_m_s * cos_climb * math.sin(target_heading_rad) - sensor_ground_speed_m_s
    v_up = target_speed_m_s * math.sin(target_climb_rad)
    return (v_par, v_perp, v_up)


def relative_los_angular_rate_rad_s(
    *,
    slant_range_m: float,
    theta_o_rad: float,
    sensor_ground_speed_m_s: float = 0.0,
    target_speed_m_s: float = 0.0,
    target_heading_rad: float = 0.0,
    target_climb_rad: float = 0.0,
) -> float:
    """Angular rate of the sensor↔target line of sight [rad/s].

    ``ω = |v_rel × û| / R`` with ``û`` the unit LOS from target to sensor and
    ``v_rel = v_target − v_sensor`` (see the module docstring for the frame).
    The cross-product form is used rather than
    ``sqrt(|v_rel|² − (v_rel·û)²)`` because the latter cancels catastrophically
    for a near-radial relative velocity, where the answer is near zero.

    Parameters
    ----------
    slant_range_m:
        Target↔sensor slant range [m].  Must be strictly positive.
    theta_o_rad:
        Canonical target-side path zenith [rad] on the closed domain ``[0, π]``
        (ADR-0011): acute = down-looking, ``π/2`` = level, obtuse = up-looking.
    sensor_ground_speed_m_s, target_speed_m_s, target_heading_rad, target_climb_rad:
        See :func:`relative_velocity_m_s`.

    Returns
    -------
    float
        The LOS angular rate [rad/s], always non-negative.  Exactly ``0.0``
        when neither endpoint moves, and ``v/R`` when the relative velocity is
        exactly perpendicular to the LOS.

    Raises
    ------
    GeometrySpecificationError
        If the slant range is not strictly positive (coincident endpoints —
        no line of sight exists to rotate), if ``theta_o_rad`` is outside
        ``[0, π]``, or on any invalid velocity input.
    """
    _require_finite("slant_range_m", slant_range_m)
    _require_finite("theta_o_rad", theta_o_rad)
    if slant_range_m <= 0.0:
        raise GeometrySpecificationError(
            what=(
                f"relative LOS rate: slant_range_m = {slant_range_m} m is not "
                "strictly positive — the endpoints are coincident"
            ),
            why=(
                "The angular rate is |v_rel,perp| / R. With the sensor and the "
                "target at the same point there is no line of sight, so its "
                "direction — and any rate of change of that direction — is "
                "undefined, not merely large."
            ),
            action=(
                "Give the scene a separation (a viewing angle, a ground range, "
                "or geometry.target_range_m), or enter the rate directly via "
                "geometry.los_angular_rate_rad_s, which needs no range."
            ),
            context={"slant_range_m": slant_range_m},
        )
    if not (0.0 <= theta_o_rad <= math.pi):
        raise GeometrySpecificationError(
            what=(
                f"relative LOS rate: theta_o_rad = {theta_o_rad} rad "
                f"({math.degrees(theta_o_rad):.3f}°) is outside [0, π]"
            ),
            why=(
                "theta_o is the canonical target-side path zenith; its closed "
                "domain is [0, π] (ADR-0011). Outside it the LOS unit vector "
                "sin(theta_o) e_par + cos(theta_o) e_up is not a direction the "
                "viewing triangle produced."
            ),
            action="Pass the theta_o published by GeometryStage (0…π rad).",
            context={"theta_o_rad": theta_o_rad},
        )

    v_par, v_perp, v_up = relative_velocity_m_s(
        sensor_ground_speed_m_s=sensor_ground_speed_m_s,
        target_speed_m_s=target_speed_m_s,
        target_heading_rad=target_heading_rad,
        target_climb_rad=target_climb_rad,
    )

    sin_t = math.sin(theta_o_rad)
    cos_t = math.cos(theta_o_rad)
    # v_rel × û with û = (sin θ_o, 0, cos θ_o):
    #   (v_perp·cos θ_o,  v_up·sin θ_o − v_par·cos θ_o,  −v_perp·sin θ_o)
    # whose magnitude simplifies to hypot(v_perp, v_up·sin θ_o − v_par·cos θ_o)
    # because cos² + sin² = 1 on the first and third components.
    cross_mag = math.hypot(v_perp, v_up * sin_t - v_par * cos_t)
    return float(cross_mag / slant_range_m)
