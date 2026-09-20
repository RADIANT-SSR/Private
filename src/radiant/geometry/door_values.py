"""Every geometry door's value as implied by the resolved scene (CU-377).

One computation, one module (Rule 19): given a resolved
:class:`~radiant.core.parameters.ParameterSet`, the value each input-mode
*door* of the ADR-0006 manifest (:mod:`radiant.geometry.mode_manifest`) would
carry to produce the geometry the active door produced. The GUI's mode
selector reads it to (a) display derived values in the inactive doors instead
of their inert schema defaults (usability-audit F-48) and (b) seed a newly
selected door with the value that keeps the scene where it is (F-05), so a
switch is a re-expression of the same geometry, never a silent change of it.

The mapping is the inverse of what :mod:`radiant.geometry.modes` applies at
each door (ADR-0011 decision 3 — every viewing angle is read at the path's
**lower** endpoint):

* **V1** ``path_zenith_rad`` = ζ_low, the lower-endpoint zenith: θ_o itself on
  a down-looking or level path, ``π − η`` on an up-looking one;
* **V2** ``sensor_off_boresight_rad`` = η (the historical off-nadir look angle)
  when the sensor is the upper endpoint, else ζ_low (the entered angle *is* the
  sensor's zenith);
* **V3** ``ground_range_m`` = the surface arc, direction-free;
* **V4** ``elevation_angle_rad`` = ``π/2 − ζ_low`` (signed);
* **V0** ``target_range_m`` = the slant range;
* **S1** ``solar_zenith_rad`` = θ_s; **S2** ``solar_elevation_rad`` = ``π/2 − θ_s``;
  the **S3** site-and-time inputs have no inverse (many sites and times share
  one θ_s) and read ``None``;
* **direct** ``ground_speed_m_s`` = the resolved ground-track speed;
  ``circular_orbit`` = whether the kinematics resolved through the orbit door;
* **K1** ``los_angular_rate_rad_s`` = the resolved LOS rate; the **K2**
  target-velocity triple has no inverse and reads ``None``.

``None`` also stands for "no path" (coincident endpoints), a night scene's
solar doors, and — for every door — a parameter set that cannot resolve at all.
"""

from __future__ import annotations

import math

from radiant.core.exceptions import RadiantError
from radiant.core.parameters import ParameterSet
from radiant.geometry.mode_manifest import all_mode_params
from radiant.geometry.modes import (
    resolve_kinematics,
    resolve_los_rate,
    resolve_solar,
    resolve_viewing,
)

__all__ = ["door_values"]

_S3_DOORS = (
    "geometry.site_latitude_rad",
    "geometry.day_of_year",
    "geometry.local_solar_time_h",
    "geometry.ltan_h",
)
_K2_DOORS = (
    "geometry.target_speed_m_s",
    "geometry.target_heading_rad",
    "geometry.target_climb_rad",
)


def door_values(params: ParameterSet) -> dict[str, float | bool | None]:
    """The value each manifest door carries under the currently resolved geometry.

    Keys are exactly :func:`~radiant.geometry.mode_manifest.all_mode_params`
    (numeric anchors included — they read their resolved value; the enum anchor
    ``solar_illumination`` reads ``None``). A door with no inverse,
    no path, or an unresolvable parameter set reads ``None``. Never raises on a
    geometry the resolvers refuse: that refusal is Evaluate's to report; this
    read-only view answers "what would each door say" or "nothing yet".
    """
    values: dict[str, float | bool | None] = dict.fromkeys(all_mode_params(), None)
    try:
        if not params.is_resolved:
            params.resolve()
        viewing = resolve_viewing(params)
        solar = resolve_solar(params)
        kinematics = resolve_kinematics(params)
        los_rate = resolve_los_rate(params, viewing, kinematics)
    except (RadiantError, KeyError, TypeError, ValueError):
        return values

    values["geometry.sensor_altitude_m"] = viewing.h_sensor_m
    values["geometry.target_altitude_m"] = viewing.h_target_m

    if viewing.slant_range_m is not None and viewing.eta_rad is not None:
        theta_o = viewing.theta_o_rad
        eta = viewing.eta_rad
        zeta_low = math.pi - eta if viewing.direction == "up" else theta_o
        values["geometry.path_zenith_rad"] = zeta_low
        values["geometry.sensor_off_boresight_rad"] = (
            eta if viewing.direction == "down" else zeta_low
        )
        values["geometry.ground_range_m"] = viewing.ground_range_m
        values["geometry.elevation_angle_rad"] = math.pi / 2.0 - zeta_low
        values["geometry.target_range_m"] = viewing.slant_range_m

    values["geometry.solar_illumination"] = None
    values["geometry.solar_azimuth_rad"] = solar.delta_phi_rad
    if solar.theta_s_rad is not None:
        values["geometry.solar_zenith_rad"] = solar.theta_s_rad
        values["geometry.solar_elevation_rad"] = math.pi / 2.0 - solar.theta_s_rad
    for name in _S3_DOORS:
        values[name] = None

    values["geometry.ground_speed_m_s"] = kinematics.ground_speed_m_s
    values["geometry.circular_orbit"] = kinematics.mode == "circular_orbit"

    values["geometry.los_angular_rate_rad_s"] = los_rate.los_angular_rate_rad_s
    for name in _K2_DOORS:
        values[name] = None
    return values
