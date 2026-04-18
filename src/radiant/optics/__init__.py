"""Stage 3: PSF, MTF, optical throughput, encircled energy, and regime finalization."""

from radiant.optics.element import (
    ElementKind,
    KirchhoffViolationError,
    OpticalElement,
)
from radiant.optics.element_factories import make_lumped_element
from radiant.optics.nearfield_irradiance import (
    NearfieldResult,
    compute_downstream_transmission,
    compute_nearfield_irradiance,
)
from radiant.optics.system_transmission import compute_system_transmission
from radiant.optics.filters import (
    FilterSpec,
    FilterType,
    filter_to_element,
    make_filter_transmission,
)
from radiant.optics.stray_light import (
    StrayLightConfig,
    StrayLightInputMode,
    compute_stray_light_irradiance,
)
from radiant.optics.transmission_modes import (
    TransmissionInputMode,
    TransmissionResult,
    resolve_transmission,
)
from radiant.optics.wavefront import (
    FieldWfeSample,
    WavefrontError,
    WfeMode,
)

__all__ = [
    "ElementKind",
    "FieldWfeSample",
    "NearfieldResult",
    "FilterSpec",
    "FilterType",
    "KirchhoffViolationError",
    "OpticalElement",
    "StrayLightConfig",
    "StrayLightInputMode",
    "TransmissionInputMode",
    "TransmissionResult",
    "WavefrontError",
    "WfeMode",
    "compute_downstream_transmission",
    "compute_nearfield_irradiance",
    "compute_stray_light_irradiance",
    "compute_system_transmission",
    "filter_to_element",
    "make_filter_transmission",
    "make_lumped_element",
    "resolve_transmission",
]
