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
    Gap 110 — this is the default and the zero-drift path.
``"hufnagel_valley"``
    HV parameterized by ``atmosphere.cn2_hv_wind_rms_m_s`` (``w``) and
    ``atmosphere.cn2_hv_ground_strength`` (``A``); the schema defaults are
    HV-5/7.
``"tabulated"``
    A :class:`~radiant.atmosphere.cn2_tabulated.TabulatedCn2Profile` built
    pre-chain from ``atmosphere.cn2_tabulated_file`` and injected at
    ``stage_outputs["atmosphere_config"]["cn2_profile"]`` (Rule 6 — stages do
    not read files).
"""

from __future__ import annotations

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
]

#: The "no profile" selector value — ``atmosphere.r0_m`` is used directly.
CN2_PROFILE_DIRECT: str = "direct"

#: Legal values of ``atmosphere.cn2_profile`` (mirrored by the schema enum).
CN2_PROFILE_NAMES: tuple[str, ...] = ("direct", "hufnagel_valley", "tabulated")


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


def resolve_cn2_profile(
    name: str,
    *,
    hv_wind_rms_m_s: float,
    hv_ground_strength_m23: float,
    tabulated: Cn2Profile | None = None,
) -> Cn2Profile | None:
    """Turn the ``atmosphere.cn2_profile`` selector into a profile object.

    Returns ``None`` for ``"direct"`` (no profile — the caller uses
    ``atmosphere.r0_m``).

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
