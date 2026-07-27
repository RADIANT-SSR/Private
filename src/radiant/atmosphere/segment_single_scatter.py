"""Single-scatter solar source term for one path segment.

One computation, one module (Rule 19): the scattered-solar radiance emerging
from a path segment of known transmittance, in one of the segment's two
travel directions.  Both the column-segment evaluator and the level-arm
evaluator consume this; the formula lives here once rather than being
re-derived in each.

Physics
-------
The standard single-scatter approximation (Schott, *Remote Sensing of the
Environment*; Liou, *An Introduction to Atmospheric Radiation*)::

    L_scat(λ) = [E_sun(λ) / 4π] · cos(θ_s) · ω₀(λ) · P(Θ) · (1 − τ(λ))

with ``E_sun / π`` supplied by
:func:`radiant.core.solar.toa_solar_equivalent_radiance`, hence the extra
factor of 4 in the denominator.  ``(1 − τ)`` is the path-integrated
single-scatter source, ``ω₀`` the single-scattering albedo, and ``P(Θ)`` the
extinction-weighted phase function normalised so an isotropic scatterer has
``P ≡ 1``.  This is exactly the form ``SimpleAtmosphere.evaluate`` already
uses for ``L_path_up``; the only new thing here is that the scattering angle
is resolved per travel direction.

Directional scattering angle
----------------------------
Let ``ζ`` be the segment zenith at its lower endpoint, ``θ_s`` the solar
zenith and ``Δφ = φ_s − φ_o`` the sun-to-path relative azimuth.  The incoming
photon direction is ``ŝ_in = −(sin θ_s cos φ_s, sin θ_s sin φ_s, cos θ_s)``
(photons travel *away* from where the sun is).  For light emerging at the
segment's **upper** end the outgoing direction is ``ŝ_up = (sin ζ cos φ_o,
sin ζ sin φ_o, cos ζ)``, so::

    cos Θ_toward_upper = ŝ_in · ŝ_up = −[sin θ_s sin ζ cos Δφ + cos θ_s cos ζ]

which is exactly
:meth:`radiant.atmosphere.protocol.AtmosphericGeometry.cos_scattering_angle`
— the existing convention, reproduced here as a free function because that
method cannot be constructed for ``ζ = π/2`` (the level arm) or for a sun at
or below the horizon.  Light emerging at the **lower** end travels along
``−ŝ_up``, so::

    cos Θ_toward_lower = −cos Θ_toward_upper

Forward scatter for one direction is back scatter for the other: this sign
flip is the mechanism that makes the two directional radiance products
genuinely different, and with a strongly forward-peaked aerosol phase
function (Henyey-Greenstein ``g = 0.7``) the difference is large.

Sun below the horizon
---------------------
``cos θ_s ≤ 0`` gives an exactly-zero scattered term.  The comparison uses
the same ``1e-12`` cosine tolerance the existing backend uses, because
``cos(π/2)`` evaluates to ~6e-17 rather than 0 in IEEE-754 and a "sun exactly
on the horizon" case must yield a hard zero.

The horizon test is the **target-local** one (the sun's zenith at the
segment's lower endpoint).  The per-altitude shadow-height test that lets a
high-altitude segment stay sunlit while the ground below it is dark is GF-9,
a separate Phase 2 item; until it lands, a segment whose lower endpoint is in
darkness contributes no scattered solar, which under-states rather than
over-states the signal.
"""

from __future__ import annotations

import math

import numpy as np

from radiant.atmosphere.segments import SegmentDirection
from radiant.core.parameters import ParameterBoundsError
from radiant.core.solar import toa_solar_equivalent_radiance

__all__ = [
    "COS_HORIZON_TOLERANCE",
    "cos_scattering_angle",
    "segment_single_scatter_radiance",
]

# Sun-below-horizon guard.  cos(π/2) ≈ 6.1e-17 in IEEE-754; treat any cosine
# below this as exactly zero so the scattered term is a hard zero for
# θ_s ≥ π/2.  Mirrors ``_COS_HORIZON_TOL`` in ``simple.py`` — same convention,
# not a new physics parameter.
COS_HORIZON_TOLERANCE: float = 1.0e-12


def cos_scattering_angle(
    zeta_low_rad: float,
    theta_s_rad: float,
    delta_phi_rad: float,
    direction: SegmentDirection,
) -> float:
    """Cosine of the single-scatter angle for one segment travel direction.

    Parameters
    ----------
    zeta_low_rad:
        Segment zenith at the lower endpoint [rad].  ``π/2`` for a level arm.
    theta_s_rad:
        Solar zenith angle at the segment's lower endpoint [rad].
    delta_phi_rad:
        Relative azimuth ``φ_s − φ_o`` [rad].  Only its cosine is used.
    direction:
        ``"toward_upper"`` or ``"toward_lower"``.

    Returns
    -------
    float
        ``cos Θ`` ∈ [−1, 1].
    """
    cos_up = -(
        math.sin(theta_s_rad) * math.sin(zeta_low_rad) * math.cos(delta_phi_rad)
        + math.cos(theta_s_rad) * math.cos(zeta_low_rad)
    )
    if direction == "toward_upper":
        return cos_up
    if direction == "toward_lower":
        return -cos_up
    raise ParameterBoundsError(
        what=f"cos_scattering_angle: unknown direction {direction!r}",
        why="A segment has exactly two travel directions.",
        action="Pass 'toward_upper' or 'toward_lower'.",
        context={"direction": direction},
    )


def segment_single_scatter_radiance(
    wavelength_um: np.ndarray,
    tau: np.ndarray,
    omega0: np.ndarray,
    phase: np.ndarray,
    cos_theta_sun: float,
) -> np.ndarray:
    """Single-scatter solar radiance emerging from a segment [W/m²/sr/µm].

    Parameters
    ----------
    wavelength_um:
        Wavelength grid [µm].
    tau:
        Segment transmittance [dimensionless] ∈ [0, 1], same shape.
    omega0:
        Single-scattering albedo ``ω₀(λ)`` [dimensionless] ∈ [0, 1].
    phase:
        Extinction-weighted phase function ``P(Θ, λ)`` [dimensionless],
        normalised so an isotropic scatterer gives 1.
    cos_theta_sun:
        ``cos θ_s`` at the segment's lower endpoint [dimensionless].  Values
        at or below :data:`COS_HORIZON_TOLERANCE` give an exactly-zero result.

    Returns
    -------
    np.ndarray
        Non-negative scattered radiance [W/m²/sr/µm]; exactly zero when the
        sun is at or below the local horizon, and exactly zero when
        ``τ == 1`` (no material to scatter from).
    """
    lam = np.asarray(wavelength_um, dtype=np.float64)
    t = np.asarray(tau, dtype=np.float64)
    w = np.asarray(omega0, dtype=np.float64)
    p = np.asarray(phase, dtype=np.float64)
    for name, arr in (("tau", t), ("omega0", w), ("phase", p)):
        if arr.shape != lam.shape:
            raise ParameterBoundsError(
                what=(
                    f"segment_single_scatter_radiance: {name} shape {arr.shape} "
                    f"does not match wavelength_um shape {lam.shape}"
                ),
                why="All single-scatter inputs are one spectral vector.",
                action="Evaluate every input on the chain wavelength grid.",
                context={"field": name, "shape": arr.shape},
            )
    if not math.isfinite(cos_theta_sun):
        raise ParameterBoundsError(
            what=f"segment_single_scatter_radiance: cos_theta_sun = {cos_theta_sun} is not finite",
            why="A non-finite solar cosine propagates NaN through the radiance.",
            action="Supply cos(θ_s) as a finite number in [−1, 1].",
            context={"cos_theta_sun": cos_theta_sun},
        )

    if cos_theta_sun <= COS_HORIZON_TOLERANCE:
        return np.zeros_like(lam)

    l_sun = np.asarray(toa_solar_equivalent_radiance(lam), dtype=np.float64)
    values = l_sun * cos_theta_sun * w * p * (1.0 - t) / 4.0
    # P(Θ) and ω₀ are non-negative and (1 − τ) ≥ 0, so this is non-negative by
    # construction; the clamp removes signed-zero dust only.
    return np.asarray(np.maximum(values, 0.0), dtype=np.float64)
