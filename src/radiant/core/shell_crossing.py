r"""Slant range from a point to a concentric spherical shell, along a given ray.

One computation, one module (Rule 19). Two places in RADIANT need the same
spherical-shell intersection and had derived it independently (CU-237):

* :func:`radiant.core.viewing_triangle.solve_from_lower_zenith` — the slant range
  from the path's lower endpoint up to the upper endpoint's radius;
* :func:`radiant.performance.path_optical_depth.column_exit_range_m` — the range
  at which an up-looking ray leaves the modelled atmospheric column.

They are the same geometric fact with different names for the shell, so they now
share this function rather than two copies of one square root.

The geometry
------------
On a spherical Earth, the radius along a ray at distance :math:`s` from a start
point of radius :math:`r_0`, launched at local zenith angle :math:`\zeta_0`, is

.. math:: r(s)^2 = r_0^2 + s^2 + 2\,r_0 s \cos\zeta_0

(the law of cosines on the triangle Earth-centre / start / point-at-``s``). The
crossing of the shell :math:`r = r_{shell}` is the positive root

.. math:: s = -r_0\cos\zeta_0
              + \sqrt{r_0^2\cos^2\zeta_0 + r_{shell}^2 - r_0^2}.

When :math:`r_{shell} > r_0` the discriminant is strictly positive and the ``+``
root is the unique positive solution, whatever the launch zenith — a ray aimed
below the horizontal still reaches an outer shell, on the far side.

Returns ``0.0`` when the start point is already at or above the shell: there is
no outward crossing to find, and that is a legitimate configuration (a sensor
above the modelled column) rather than an error.
"""

from __future__ import annotations

import math

from radiant.core.constants import R_EARTH_M

__all__ = ["slant_range_to_shell_m"]


def slant_range_to_shell_m(
    h_low_m: float,
    zeta_low_rad: float,
    h_shell_m: float,
) -> float:
    """Range [m] from *h_low_m* to the shell at *h_shell_m*, along a ray at *zeta_low_rad*.

    Parameters
    ----------
    h_low_m:
        Altitude of the start point above mean sea level [m].
    zeta_low_rad:
        Local zenith angle of the ray **at the start point** [rad]. 0 = straight
        up, π/2 = horizontal.
    h_shell_m:
        Altitude of the concentric shell to intersect [m].

    Returns
    -------
    float
        The positive root above, or ``0.0`` when ``h_shell_m <= h_low_m``.
    """
    r_0 = R_EARTH_M + h_low_m
    r_shell = R_EARTH_M + h_shell_m
    if r_0 >= r_shell:
        return 0.0
    cos_zeta = math.cos(zeta_low_rad)
    disc = (r_0 * cos_zeta) ** 2 + (r_shell * r_shell - r_0 * r_0)
    # r_shell > r_0 was established above, so disc > 0 and the '+' root is the
    # unique positive one.
    return float(-r_0 * cos_zeta + math.sqrt(disc))
