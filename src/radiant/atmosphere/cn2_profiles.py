r"""The $C_n^2(h)$ profile family — contract and selector.

This module holds **no physics** (Rule 19): it defines the structural
contract every optical-turbulence profile satisfies and the pure selector that
turns the ``atmosphere.cn2_profile`` enum into a profile object.  The two
implementations live beside it, one computation per module:

* :mod:`radiant.atmosphere.cn2_hufnagel_valley` — the analytic HV preset;
* :mod:`radiant.atmosphere.cn2_tabulated` — a user-supplied table.

The path integral that turns a profile into a Fried parameter lives in
:mod:`radiant.atmosphere.r0_path`.

The selector values
-------------------
``"direct"``
    No profile.  ``atmosphere.r0_m`` is the Fried parameter, exactly as before
    Gap 110 — this is the default and the zero-drift path.  ``geometry.
    site_elevation_m`` is inert here (there is no surface layer), and
    :func:`warn_if_site_elevation_inert` says so rather than ignoring it
    silently (CU-302).
``"hufnagel_valley"``
    HV parameterized by ``atmosphere.cn2_hv_wind_rms_m_s`` (``w``) and
    ``atmosphere.cn2_hv_ground_strength`` (``A``); the schema defaults are
    HV-5/7.  Its surface term is referenced to ``geometry.site_elevation_m``
    (CU-262).
``"tabulated"``
    A :class:`~radiant.atmosphere.cn2_tabulated.TabulatedCn2Profile` built
    pre-chain from ``atmosphere.cn2_tabulated_file`` and injected at
    ``stage_outputs["atmosphere_config"]["cn2_profile"]`` (Rule 6 — stages do
    not read files).  A measured table already carries whatever site the
    measurement was made at, so ``geometry.site_elevation_m`` does **not**
    shift it — the altitudes in the file are used as written, and
    :func:`warn_if_site_elevation_inert` reports the input as inert (CU-302).
"""

from __future__ import annotations

import warnings
from typing import Protocol, runtime_checkable

import numpy as np
import numpy.typing as npt

from radiant.atmosphere.cn2_hufnagel_valley import HufnagelValleyCn2
from radiant.atmosphere.errors import AtmosphereValidationError

__all__ = [
    "CN2_PROFILE_DIRECT",
    "CN2_PROFILE_NAMES",
    "Cn2Profile",
    "resolve_cn2_profile",
    "warn_if_site_elevation_inert",
]

#: The "no profile" selector value — ``atmosphere.r0_m`` is used directly.
CN2_PROFILE_DIRECT: str = "direct"

#: Legal values of ``atmosphere.cn2_profile`` (mirrored by the schema enum).
CN2_PROFILE_NAMES: tuple[str, ...] = ("direct", "hufnagel_valley", "tabulated")

#: Selector values that consume ``geometry.site_elevation_m``.  Hufnagel-Valley
#: is the only one: its surface term is referenced to the terrain (CU-262).
#: Everything else in :data:`CN2_PROFILE_NAMES` ignores the parameter, which is
#: correct but must not be silent (CU-302, Rule 17).
_SITE_ELEVATION_CONSUMERS: frozenset[str] = frozenset({"hufnagel_valley"})


@runtime_checkable
class Cn2Profile(Protocol):
    """Structural contract for an optical-turbulence altitude profile."""

    @property
    def coverage_m(self) -> tuple[float, float] | None:
        """Altitude interval [m MSL] the profile is defined over.

        ``None`` means "everywhere" (an analytic profile).  A finite interval
        means the profile returns zero outside it, and the path integrator
        warns when the line of sight leaves that interval.
        """
        ...

    @property
    def breakpoints_m(self) -> tuple[float, ...]:
        """Altitudes [m MSL] the quadrature should place a node on.

        Interpolant kinks for a tabulated profile; the jet-stream peak for
        Hufnagel-Valley.  May be empty.
        """
        ...

    def cn2(self, altitude_m: npt.NDArray[np.float64]) -> npt.NDArray[np.float64]:
        """Structure constant [m^(-2/3)] at each altitude [m MSL]."""
        ...

    def describe(self) -> str:
        """One-line provenance string."""
        ...


def warn_if_site_elevation_inert(profile_name: str, site_elevation_m: float) -> None:
    """Warn when a declared site elevation cannot reach the selected profile.

    ``geometry.site_elevation_m`` is consumed by exactly one profile — the
    Hufnagel-Valley surface term (CU-262).  With ``"tabulated"`` the measured
    table already carries whatever site it was taken at, and with ``"direct"``
    there is no profile at all, so a non-zero elevation changes nothing.  That
    is the right physics, but Rule 17 forbids doing it silently: an analyst who
    enters a 2635 m site elevation and reads back an unchanged Fried parameter
    has no way to tell the input was ignored.

    No-op for a sea-level (or unset) elevation and for the profiles that use it.

    Parameters
    ----------
    profile_name:
        The ``atmosphere.cn2_profile`` selector value.
    site_elevation_m:
        ``geometry.site_elevation_m`` [m MSL].
    """
    if site_elevation_m == 0.0 or profile_name in _SITE_ELEVATION_CONSUMERS:
        return
    if profile_name == CN2_PROFILE_DIRECT:
        reason = (
            "atmosphere.cn2_profile = 'direct' selects no Cn² profile at all — "
            "atmosphere.r0_m is used exactly as entered, so there is no surface "
            "layer for the terrain to sit on"
        )
    else:
        reason = (
            f"atmosphere.cn2_profile = {profile_name!r} carries its own altitudes: a "
            "measured table already includes whatever site the measurement was made "
            "at, so RADIANT uses its altitudes as written rather than shifting them"
        )
    warnings.warn(
        f"geometry.site_elevation_m = {site_elevation_m:g} m MSL has no effect on this "
        f"run. {reason}. The parameter reaches only the Hufnagel-Valley surface term "
        "(atmosphere.cn2_profile = 'hufnagel_valley', CU-262). Either set "
        "atmosphere.cn2_profile = 'hufnagel_valley' to model an elevated site "
        "analytically, or supply a table whose altitudes already describe the site "
        "and leave geometry.site_elevation_m at 0.",
        UserWarning,
        stacklevel=3,
    )


def resolve_cn2_profile(
    name: str,
    *,
    hv_wind_rms_m_s: float,
    hv_ground_strength_m23: float,
    hv_site_elevation_m: float = 0.0,
    tabulated: Cn2Profile | None = None,
) -> Cn2Profile | None:
    """Turn the ``atmosphere.cn2_profile`` selector into a profile object.

    Returns ``None`` for ``"direct"`` (no profile — the caller uses
    ``atmosphere.r0_m``).

    ``hv_site_elevation_m`` is ``geometry.site_elevation_m`` and reaches the
    Hufnagel-Valley surface term only; the tabulated profile is used as
    written (see the module docstring).

    Raises
    ------
    AtmosphereValidationError
        For an unknown selector value, or for ``"tabulated"`` with no
        pre-built profile injected.
    """
    if name == CN2_PROFILE_DIRECT:
        return None
    if name == "hufnagel_valley":
        return HufnagelValleyCn2(
            wind_rms_m_s=hv_wind_rms_m_s,
            ground_strength_m23=hv_ground_strength_m23,
            site_elevation_m=hv_site_elevation_m,
        )
    if name == "tabulated":
        if tabulated is None:
            raise AtmosphereValidationError(
                "atmosphere.cn2_profile = 'tabulated' but no tabulated profile was "
                "supplied. Rule 6 keeps file I/O out of the stage: set "
                "atmosphere.cn2_tabulated_file and run the chain through "
                "RadiantSession/Sensor (which calls "
                "radiant.atmosphere.loaders.build_cn2_profile and injects the result "
                "at stage_outputs['atmosphere_config']['cn2_profile']), or inject a "
                "TabulatedCn2Profile there yourself."
            )
        return tabulated
    raise AtmosphereValidationError(
        f"atmosphere.cn2_profile = {name!r} is not a known profile. "
        f"Supported: {', '.join(CN2_PROFILE_NAMES)}."
    )
