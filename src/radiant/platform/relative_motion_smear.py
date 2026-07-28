r"""Focal-plane smear extent from the relative line-of-sight angular rate (Gap 111).

One computation (Rule 19): given the rate at which the sensor↔target line of
sight rotates, how far does the target's image translate across the focal
plane during one integration?

.. math::

    s = \omega_{LOS} \, f \, t_{int}

with :math:`\omega_{LOS}` in rad/s, the effective focal length :math:`f` in m
and the integration time :math:`t_{int}` in s, giving :math:`s` in m on the
focal plane.  The intermediate *angular* smear is :math:`\omega t_{int}` [rad];
multiplying by :math:`f` is the paraxial focal-plane scale (m per rad), the same
scale ``platform/jitter.py`` uses to turn an angular jitter into a focal-plane
sigma.

Why ONE rate and not a combination of two smears
------------------------------------------------
Platform motion and target motion do **not** produce two independent blurs to
be combined.  They produce one blur, because they are two contributions to a
single physical quantity: the linear translation of the target's image across
the focal plane during the integration.  The composition therefore happens in
the **velocity** domain, upstream of this module —

.. math::

    \mathbf{v}_{rel} = \mathbf{v}_{target} - \mathbf{v}_{sensor},
    \qquad
    \omega_{LOS} = \frac{\lvert \mathbf{v}_{rel} \times \hat{u} \rvert}{R}

(:func:`radiant.geometry.los_rate.relative_los_angular_rate_rad_s`, published by
GeometryStage as ``stage_outputs["geometry"]["los_angular_rate_rad_s"]``) — and
this module receives the single resulting rate.

An RSS combination :math:`\sqrt{s_{platform}^2 + s_{target}^2}` would be wrong
in both limits, not merely imprecise:

* **Co-moving target** (a target flying with the platform's ground track at the
  matching angular rate): the true relative rate is **zero** — the image does
  not move, and a long integration is legitimate.  RSS returns
  :math:`\sqrt{2}\,s_{platform}`, inventing a blur that does not exist.
* **Counter-moving target** (equal and opposite rates): the true smear is
  :math:`2 s_{platform}`.  RSS returns :math:`\sqrt{2}\,s_{platform}`,
  understating the blur by 30 %.

RSS is the correct combination only for statistically independent, zero-mean
random displacements (jitter axes, charge diffusion) — deterministic linear
translations add as vectors, and cancellation is a real, physical outcome.

Direction convention (v1 limitation, documented not hidden)
-----------------------------------------------------------
The rect smear kernel and the ``mtf_smear_y`` term are applied along the
focal-plane **y** (along-track) axis, which is exactly where the platform-only
smear has always gone.  RADIANT carries no focal-plane azimuth for the relative
velocity (``geometry.target_heading_rad`` is a *scene* azimuth, and the platform
track azimuth is not a parameter at all — see
:mod:`radiant.geometry.los_rate`), so a crossing target whose image moves along
x is modelled with its true smear *magnitude* placed on the y axis.  The
magnitude — hence the smear MTF at a given frequency, RER along the smear axis,
and the resulting NIIRS — is correct; the *orientation* of the anisotropy is
not.  Making it azimuth-resolved needs a track-azimuth input and a 2-D rect
kernel, which is the unbuilt part of Gap 74.
"""

from __future__ import annotations

import math

from radiant.platform.errors import PlatformValidationError

__all__ = ["smear_width_from_los_rate_m"]


def smear_width_from_los_rate_m(
    los_rate_rad_s: float,
    t_int_s: float,
    focal_length_m: float,
) -> float:
    """Focal-plane smear extent [m] from a line-of-sight angular rate.

    Parameters
    ----------
    los_rate_rad_s:
        Relative line-of-sight angular rate [rad/s] — the rate at which the
        sensor↔target LOS *direction* rotates, including both endpoints'
        motion.  Must be finite and non-negative (it is a magnitude; the
        smear extent does not depend on the sign of the motion).
    t_int_s:
        Integration time [s].  Must be finite and non-negative.
    focal_length_m:
        Effective focal length [m].  Must be finite and strictly positive.

    Returns
    -------
    float
        Smear extent on the focal plane [m]: ``los_rate × focal_length ×
        t_int``.  Exactly ``0.0`` when the rate or the integration time is
        zero.

    Raises
    ------
    PlatformValidationError
        On a non-finite input, a negative rate or integration time, or a
        non-positive focal length.
    """
    for name, value in (
        ("los_rate_rad_s", los_rate_rad_s),
        ("t_int_s", t_int_s),
        ("focal_length_m", focal_length_m),
    ):
        if not math.isfinite(value):
            raise PlatformValidationError(
                f"smear from LOS rate: {name} = {value} is not finite. "
                "A non-finite input cannot produce a meaningful smear extent. "
                f"Set {name} to a finite value."
            )
    if los_rate_rad_s < 0.0:
        raise PlatformValidationError(
            f"smear from LOS rate: los_rate_rad_s must be non-negative, got {los_rate_rad_s}. "
            "The LOS rate is a magnitude — |v_rel,perp| / R — and the smear extent is "
            "direction-independent. Pass the rate GeometryStage publishes "
            "(stage_outputs['geometry']['los_angular_rate_rad_s']), which is never negative."
        )
    if t_int_s < 0.0:
        raise PlatformValidationError(f"t_int_s must be non-negative, got {t_int_s}")
    if focal_length_m <= 0.0:
        raise PlatformValidationError(f"focal_length_m must be positive, got {focal_length_m}")

    return los_rate_rad_s * focal_length_m * t_int_s
