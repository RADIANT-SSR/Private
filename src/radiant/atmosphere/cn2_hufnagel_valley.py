r"""Hufnagel-Valley refractive-index structure constant profile $C_n^2(h)$.

One computation, one module (Rule 19): the analytic HV altitude profile and
nothing else.  It is consumed through the
:class:`~radiant.atmosphere.cn2_profiles.Cn2Profile` contract by
:mod:`radiant.atmosphere.r0_path`, which owns the path integral.

The model
--------
The Hufnagel-Valley profile is the standard three-term night-time-to-daytime
parameterization of optical turbulence strength versus altitude:

.. math::

    C_n^2(h) = 0.00594\,\left(\frac{w}{27}\right)^2
               \left(10^{-5} h\right)^{10} e^{-h/1000}
             + 2.7\times10^{-16}\, e^{-h/1500}
             + A\, e^{-h/100}

with ``h`` the altitude above ground in **metres** and $C_n^2$ in
**m^(-2/3)**.  The three terms are, in order:

1. the **tropopause / jet-stream** term, whose strength is set by ``w``, the
   RMS upper-atmosphere wind speed [m/s] (the 5–20 km slab average).  The
   $h^{10}e^{-h/1000}$ shape peaks at exactly $h = 10$ km;
2. a fixed **middle-atmosphere** background term;
3. the **surface-layer** term, whose strength is set by ``A``, the
   ground-level $C_n^2$ [m^(-2/3)], with a 100 m scale height.

``HV-5/7`` — the canonical preset, named for the $r_0 = 5$ cm and
$\theta_0 = 7$ µrad it produces at 0.5 µm for a vertical path — is
``w = 21`` m/s, ``A = 1.7 \times 10^{-14}`` m^(-2/3).

References
----------
- L. C. Andrews and R. L. Phillips, *Laser Beam Propagation through Random
  Media*, 2nd ed., SPIE Press (2005), §12.2.2 Eq. (12.30) — the HV-5/7
  parameters and the $r_0 = 5$ cm / $\theta_0 = 7$ µrad values.
- R. R. Beland, "Propagation through Atmospheric Optical Turbulence", in
  *The Infrared and Electro-Optical Systems Handbook*, Vol. 2, SPIE (1993),
  §2.3 — the same three-term form with the wind/ground parameterization.
- G. C. Valley, "Isoplanatic degradation of tilt correction and short-term
  imaging systems", *Appl. Opt.* **19**, 574 (1980) — the original two-term
  Hufnagel fit that the surface term extends.

Altitude reference
------------------
``h`` is altitude **above mean sea level** in RADIANT, matching every other
altitude in the framework (``geometry.sensor_altitude_m``,
``ColumnSegmentSpec.h_low_m``).  The literature writes the HV profile against
height above the *site*; for a sea-level site the two coincide, and for an
elevated site the difference is absorbed into ``A`` (which is a site
measurement anyway).  This is documented rather than corrected: introducing a
site-elevation offset would make the profile depend on a quantity RADIANT does
not carry.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
import numpy.typing as npt

from radiant.core.parameters import ParameterBoundsError

__all__ = [
    "HV_5_7_GROUND_STRENGTH_M23",
    "HV_5_7_WIND_RMS_M_S",
    "HufnagelValleyCn2",
]

#: HV-5/7 preset: RMS upper-atmosphere (5–20 km) wind speed [m/s].
HV_5_7_WIND_RMS_M_S: float = 21.0

#: HV-5/7 preset: ground-level structure constant [m^(-2/3)].
HV_5_7_GROUND_STRENGTH_M23: float = 1.7e-14

# --- Fixed model coefficients (Andrews & Phillips Eq. 12.30) ---------------
_TROPO_COEFF: float = 0.00594  # [m^(-2/3)] scale of the jet-stream term
_TROPO_WIND_REF_M_S: float = 27.0  # reference wind in the (w/27)^2 factor
_TROPO_HEIGHT_SCALE_INV_M: float = 1.0e-5  # the (1e-5 h) argument
_TROPO_DECAY_M: float = 1000.0
_MIDDLE_COEFF_M23: float = 2.7e-16
_MIDDLE_DECAY_M: float = 1500.0
_SURFACE_DECAY_M: float = 100.0


@dataclass(frozen=True)
class HufnagelValleyCn2:
    """Hufnagel-Valley $C_n^2(h)$ profile.

    Parameters
    ----------
    wind_rms_m_s:
        RMS upper-atmosphere wind speed ``w`` [m/s].  Must be finite and
        ``>= 0``.  HV-5/7 uses 21 m/s.
    ground_strength_m23:
        Ground-level structure constant ``A`` [m^(-2/3)].  Must be finite
        and ``>= 0``.  HV-5/7 uses 1.7e-14 m^(-2/3).
    """

    wind_rms_m_s: float = HV_5_7_WIND_RMS_M_S
    ground_strength_m23: float = HV_5_7_GROUND_STRENGTH_M23

    def __post_init__(self) -> None:
        for name, value in (
            ("wind_rms_m_s", self.wind_rms_m_s),
            ("ground_strength_m23", self.ground_strength_m23),
        ):
            if not math.isfinite(value):
                raise ParameterBoundsError(
                    what=f"HufnagelValleyCn2.{name} = {value} is not finite",
                    why="Both HV coefficients scale a physical turbulence term.",
                    action=f"Set {name} to a finite non-negative number.",
                    context={name: value},
                )
            if value < 0.0:
                raise ParameterBoundsError(
                    what=f"HufnagelValleyCn2.{name} = {value} is negative",
                    why=(
                        "A negative wind speed or a negative ground-level "
                        "structure constant would make Cn² negative, which has "
                        "no physical meaning (Cn² is a variance)."
                    ),
                    action=f"Set {name} >= 0.",
                    context={name: value},
                )

    # -- Cn2Profile contract ------------------------------------------------

    @property
    def coverage_m(self) -> tuple[float, float] | None:
        """``None`` — the analytic form is valid at every altitude."""
        return None

    @property
    def breakpoints_m(self) -> tuple[float, ...]:
        """Quadrature nodes worth forcing: the 10 km jet-stream peak.

        The $h^{10}e^{-h/1000}$ term has its maximum at exactly 10 km
        (``d/dh[10 ln h - h/1000] = 0``); the two exponential terms are
        monotone and need no forced node.
        """
        return (10.0e3,)

    def cn2(self, altitude_m: npt.NDArray[np.float64]) -> npt.NDArray[np.float64]:
        """Evaluate $C_n^2$ [m^(-2/3)] at each altitude [m above MSL].

        Negative altitudes are refused (Rule 16/17: a sub-sea-level altitude
        is an input error, not something to silently clamp).
        """
        h = np.asarray(altitude_m, dtype=np.float64)
        if not np.all(np.isfinite(h)):
            raise ParameterBoundsError(
                what="HufnagelValleyCn2.cn2: altitude_m contains non-finite values",
                why="Cn² is evaluated pointwise; a NaN/inf altitude has no profile value.",
                action="Pass finite altitudes in metres above mean sea level.",
                context={"n_bad": int(np.count_nonzero(~np.isfinite(h)))},
            )
        if np.any(h < 0.0):
            raise ParameterBoundsError(
                what=f"HufnagelValleyCn2.cn2: minimum altitude {float(h.min())} m is negative",
                why="RADIANT altitudes are metres above mean sea level; the HV profile "
                "is defined for h >= 0.",
                action="Pass altitudes >= 0 m.",
                context={"h_min_m": float(h.min())},
            )

        # Jet-stream term evaluated in log space: (1e-5 h)^10 overflows for
        # absurd altitudes while exp(-h/1000) underflows, producing inf*0 = NaN
        # in the direct form.  exp(10 ln(1e-5 h) - h/1000) is the same number
        # to within float rounding and is unconditionally finite.
        safe_h = np.where(h > 0.0, h, 1.0)
        log_arg = 10.0 * np.log(_TROPO_HEIGHT_SCALE_INV_M * safe_h) - safe_h / _TROPO_DECAY_M
        tropo = np.where(h > 0.0, np.exp(log_arg), 0.0)
        tropo = tropo * (_TROPO_COEFF * (self.wind_rms_m_s / _TROPO_WIND_REF_M_S) ** 2)

        middle = _MIDDLE_COEFF_M23 * np.exp(-h / _MIDDLE_DECAY_M)
        surface = self.ground_strength_m23 * np.exp(-h / _SURFACE_DECAY_M)

        result: npt.NDArray[np.float64] = tropo + middle + surface
        return result

    def describe(self) -> str:
        """One-line provenance string."""
        preset = (
            " (HV-5/7)"
            if self.wind_rms_m_s == HV_5_7_WIND_RMS_M_S
            and self.ground_strength_m23 == HV_5_7_GROUND_STRENGTH_M23
            else ""
        )
        return (
            f"Hufnagel-Valley{preset}: w = {self.wind_rms_m_s:g} m/s, "
            f"A = {self.ground_strength_m23:g} m^(-2/3)"
        )
