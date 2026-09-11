"""The étendue acceptance cone of the focal plane (Gap 128).

The Lagrange invariant fixes how much solid angle a detector pixel can accept:
whatever the internal layout, every in-beam element is seen through the
reimaging optics and can fill at most the cone set by the working f/#. That
cone is the *only* geometry the near-field model uses (owner-ratified
2026-09-09, `docs/plans/Nearfield_Etendue_Model.md` §2 rule 1):

.. math::

    \\Omega_\\mathrm{cone} = 2\\pi\\,(1 - \\cos\\theta), \\qquad
    \\theta = \\arctan\\!\\left(\\frac{1}{2 N_\\mathrm{eff}}\\right)

with ``N_eff`` the **effective** (post-cold-stop) f-number — see
``effective_pupil.py``. The exact form is used, not the paraxial
``π / (4 N²)``: the two agree to 0.5 % at f/6 and to 5 % at f/2, and the
paraxial form over-states the cone (it exceeds 2π as N → 0, which no solid
angle may do).

Superseded model: each element formerly carried its own
``Ω_i = π (D_i/2)² / d_i²``, which is not bounded by the invariant — a 0.3 m
mirror 1.0 m from the FPA claimed 0.0707 sr against an f/6 cone of 0.0217 sr,
3.2× more than physics permits (Gap 128).
"""

from __future__ import annotations

import math

from radiant.optics.errors import OpticsValidationError


def etendue_cone_solid_angle_sr(f_number: float) -> float:
    """Solid angle [sr] of the acceptance cone at working f-number *f_number*.

    Parameters
    ----------
    f_number:
        Effective (working) f-number ``N_eff = f / D_eff`` [-]. Must be a
        positive finite number.

    Returns
    -------
    float
        ``Ω_cone = 2π (1 − cos θ)`` [sr] with ``θ = arctan(1 / (2 N_eff))``
        [rad]. Strictly between 0 and 2π for every finite positive f/#.
    """
    if not math.isfinite(f_number) or f_number <= 0.0:
        raise OpticsValidationError(
            f"etendue_cone_solid_angle_sr: f_number = {f_number} is invalid. "
            "The working f/# must be a positive finite number; it is derived "
            "from the effective pupil as f_number_eff = focal_length_m / D_eff."
        )
    # Half-angle of the marginal ray: tan θ = (D_eff/2) / f = 1 / (2 N_eff) [rad].
    theta_rad = math.atan(1.0 / (2.0 * f_number))
    return 2.0 * math.pi * (1.0 - math.cos(theta_rad))
