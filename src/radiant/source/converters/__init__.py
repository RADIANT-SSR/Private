"""Boundary converters: physical equivalents → canonical TargetDescriptor.

Per CLAUDE.md Rule 2 (unit conversions happen at boundaries only), users
may specify a target in equivalents such as brightness temperature
(``T_B(λ)``, S11) or band-averaged radiance temperature (``T_R``, S12).
These converters run at the SourceStage boundary and produce a canonical
TargetDescriptor so every downstream stage sees a single surface.

Each converter lives in its own module per Rule 19 (one computation per
module).
"""

from __future__ import annotations

from radiant.source.converters.brightness_temperature import (
    brightness_temperature_to_descriptor,
    load_brightness_temperature_csv,
)
from radiant.source.converters.invert_band_radiance import (
    integrate_planck_over_band,
    invert_band_radiance_to_temperature,
)
from radiant.source.converters.radiance_temperature import (
    radiance_temperature_to_descriptor,
)
from radiant.source.converters.reflectance import (
    load_reflectance_csv,
    reflectance_to_descriptor,
)
from radiant.source.converters.user_intensity import (
    load_user_intensity_csv,
    user_intensity_to_descriptor,
)
from radiant.source.converters.user_radiance import (
    load_user_radiance_csv,
    user_radiance_to_descriptor,
)

__all__ = [
    "brightness_temperature_to_descriptor",
    "integrate_planck_over_band",
    "invert_band_radiance_to_temperature",
    "load_brightness_temperature_csv",
    "load_reflectance_csv",
    "load_user_intensity_csv",
    "load_user_radiance_csv",
    "radiance_temperature_to_descriptor",
    "reflectance_to_descriptor",
    "user_intensity_to_descriptor",
    "user_radiance_to_descriptor",
]
