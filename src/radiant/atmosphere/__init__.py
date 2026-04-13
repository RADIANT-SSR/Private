"""Stage 2: atmospheric transmittance, path radiance, and downwelling radiance.

Models
------
- :class:`SimpleAtmosphere` — closed-form Beer-Lambert (Rayleigh + aerosol + H2O)
- :class:`ExoAtmosphere` — vacuum (tau=1, L_path=0)
- :class:`TabulatedAtmosphere` — user-provided spectral data from files
- :class:`ModtranAtmosphere` — MODTRAN binary wrapper with caching
- :class:`InterpolatedAtmosphere` — geometry-dependent interpolation between runs
"""

from radiant.atmosphere.exo import ExoAtmosphere
from radiant.atmosphere.interpolated import GeometryPoint, InterpolatedAtmosphere
from radiant.atmosphere.modtran import (
    ModtranAtmosphere,
    ModtranConfig,
    ModtranNativeOutput,
    ModtranUnavailableError,
    Tape7Reader,
)
from radiant.atmosphere.protocol import (
    Atmosphere,
    AtmosphericGeometry,
    AtmosphericState,
)
from radiant.atmosphere.simple import SimpleAtmosphere
from radiant.atmosphere.stage import AtmosphereStage
from radiant.atmosphere.tabulated import TabulatedAtmosphere

__all__ = [
    "Atmosphere",
    "AtmosphereStage",
    "AtmosphericGeometry",
    "AtmosphericState",
    "ExoAtmosphere",
    "GeometryPoint",
    "InterpolatedAtmosphere",
    "ModtranAtmosphere",
    "ModtranConfig",
    "ModtranNativeOutput",
    "ModtranUnavailableError",
    "SimpleAtmosphere",
    "TabulatedAtmosphere",
    "Tape7Reader",
]
