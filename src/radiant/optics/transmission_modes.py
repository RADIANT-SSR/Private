"""Transmission mode dispatch — five input modes per RADIANT_Optics.md section 5.

All five modes produce the same internal representation:
    - ``transmission: SpectralData``  (net system throughput)
    - ``elements: tuple[OpticalElement, ...]``  (for nearfield calculation)

Modes 1-4 synthesize lumped elements where needed.  Mode 5 uses the
user-supplied element list directly.
"""

from __future__ import annotations

import enum
import logging
from dataclasses import dataclass

import numpy as np

from radiant.core.spectral import SpectralData
from radiant.optics.element import OpticalElement, make_lumped_element
from radiant.optics.element_list import compute_system_transmission
from radiant.optics.filters import FilterSpec, filter_to_element, make_filter_transmission

logger = logging.getLogger(__name__)


class TransmissionInputMode(enum.Enum):
    """Transmission specification modes per RADIANT_Optics.md section 5."""

    SCALAR = "scalar"
    SPECTRAL_FILE = "spectral_file"
    TELESCOPE_PLUS_FILTERS = "telescope_plus_filters"
    KEY_ELEMENTS = "key_elements"
    FULL_PRESCRIPTION = "full_prescription"


@dataclass(frozen=True)
class TransmissionResult:
    """Uniform output from any transmission mode.

    Parameters
    ----------
    mode:
        Which input mode produced this result.
    transmission:
        Net system transmission ``tau_opt(lambda)`` on the wavelength grid.
    elements:
        Tuple of optical elements for nearfield computation.
    """

    mode: TransmissionInputMode
    transmission: SpectralData
    elements: tuple[OpticalElement, ...]


def resolve_transmission(
    mode: TransmissionInputMode,
    wavelength_um: np.ndarray,
    *,
    # Mode 1: scalar
    transmission_scalar: float | None = None,
    # Mode 2: spectral file (preloaded)
    transmission_spectral: SpectralData | None = None,
    # Mode 3: telescope + filters
    telescope_transmission: SpectralData | float | None = None,
    filter_specs: tuple[FilterSpec, ...] = (),
    # Mode 4: key elements
    key_elements: tuple[OpticalElement, ...] = (),
    residual_transmission: SpectralData | float | None = None,
    # Mode 5: full prescription
    full_elements: tuple[OpticalElement, ...] = (),
    # Common defaults for synthesized elements
    optics_temperature_K: float = 290.0,
    optics_distance_to_fpa_m: float | None = None,
    aperture_diameter_m: float = 0.3,
) -> TransmissionResult:
    """Resolve transmission from the specified input mode.

    All modes produce the same output type: a net transmission SpectralData
    and a tuple of OpticalElement for nearfield calculation.

    Parameters
    ----------
    mode:
        Which input mode to use.
    wavelength_um:
        Wavelength grid in microns.
    transmission_scalar:
        Flat throughput [0, 1] for Mode 1.
    transmission_spectral:
        Pre-loaded spectral transmission for Mode 2.
    telescope_transmission:
        Broadband telescope throughput for Mode 3 (scalar or SpectralData).
    filter_specs:
        Filter specifications for Mode 3.
    key_elements:
        User-supplied key elements for Mode 4.
    residual_transmission:
        Residual lumped transmission for Mode 4 (scalar or SpectralData).
    full_elements:
        Complete ordered element list for Mode 5.
    optics_temperature_K:
        Default temperature for synthesized elements.
    optics_distance_to_fpa_m:
        Default distance to FPA for synthesized elements.
    aperture_diameter_m:
        Aperture diameter for synthesized element geometry.
    """
    dist = optics_distance_to_fpa_m if optics_distance_to_fpa_m else 1.0

    if mode == TransmissionInputMode.SCALAR:
        return _resolve_scalar(
            wavelength_um,
            transmission_scalar,
            optics_temperature_K,
            aperture_diameter_m,
            dist,
        )

    if mode == TransmissionInputMode.SPECTRAL_FILE:
        return _resolve_spectral_file(
            wavelength_um,
            transmission_spectral,
            optics_temperature_K,
            aperture_diameter_m,
            dist,
        )

    if mode == TransmissionInputMode.TELESCOPE_PLUS_FILTERS:
        return _resolve_telescope_filters(
            wavelength_um,
            telescope_transmission,
            filter_specs,
            optics_temperature_K,
            aperture_diameter_m,
            dist,
        )

    if mode == TransmissionInputMode.KEY_ELEMENTS:
        return _resolve_key_elements(
            wavelength_um,
            key_elements,
            residual_transmission,
            optics_temperature_K,
            aperture_diameter_m,
            dist,
        )

    if mode == TransmissionInputMode.FULL_PRESCRIPTION:
        return _resolve_full_prescription(wavelength_um, full_elements)

    raise ValueError(f"Unknown transmission mode: {mode}")


# ---------------------------------------------------------------------------
# Mode implementations
# ---------------------------------------------------------------------------


def _resolve_scalar(
    wavelength_um: np.ndarray,
    transmission_scalar: float | None,
    temperature_K: float,
    diameter_m: float,
    distance_m: float,
) -> TransmissionResult:
    """Mode 1: scalar throughput broadcast to flat spectrum."""
    if transmission_scalar is None:
        raise ValueError("resolve_transmission: SCALAR mode requires transmission_scalar.")
    tau_sd = SpectralData(
        name="optics.transmission.scalar",
        wavelength_um=wavelength_um.copy(),
        values=np.full_like(wavelength_um, transmission_scalar),
        unit="",
        source=f"Scalar Mode 1: tau={transmission_scalar}",
    )
    lumped = make_lumped_element(tau_sd, temperature_K, diameter_m, distance_m)
    return TransmissionResult(
        mode=TransmissionInputMode.SCALAR,
        transmission=tau_sd,
        elements=(lumped,),
    )


def _resolve_spectral_file(
    wavelength_um: np.ndarray,
    transmission_spectral: SpectralData | None,
    temperature_K: float,
    diameter_m: float,
    distance_m: float,
) -> TransmissionResult:
    """Mode 2: spectral transmission from file (pre-loaded)."""
    if transmission_spectral is None:
        raise ValueError("resolve_transmission: SPECTRAL_FILE mode requires transmission_spectral.")
    lumped = make_lumped_element(
        transmission_spectral,
        temperature_K,
        diameter_m,
        distance_m,
        name="lumped_spectral",
    )
    return TransmissionResult(
        mode=TransmissionInputMode.SPECTRAL_FILE,
        transmission=transmission_spectral,
        elements=(lumped,),
    )


def _resolve_telescope_filters(
    wavelength_um: np.ndarray,
    telescope_transmission: SpectralData | float | None,
    filter_specs: tuple[FilterSpec, ...],
    temperature_K: float,
    diameter_m: float,
    distance_m: float,
) -> TransmissionResult:
    """Mode 3: telescope broadband throughput * filter stack."""
    if telescope_transmission is None:
        raise ValueError(
            "resolve_transmission: TELESCOPE_PLUS_FILTERS mode requires telescope_transmission."
        )

    # Resolve telescope transmission to SpectralData.
    if isinstance(telescope_transmission, int | float):
        tele_sd = SpectralData(
            name="optics.telescope_transmission",
            wavelength_um=wavelength_um.copy(),
            values=np.full_like(wavelength_um, float(telescope_transmission)),
            unit="",
            source=f"Telescope scalar: {telescope_transmission}",
        )
    else:
        tele_sd = telescope_transmission

    # Compute net transmission: telescope * product of filters.
    net_vals = tele_sd.values.copy()
    filter_elements: list[OpticalElement] = []

    for spec in filter_specs:
        f_sd = make_filter_transmission(spec, wavelength_um)
        net_vals = net_vals * f_sd.values
        filter_elements.append(
            filter_to_element(spec, wavelength_um, temperature_K, diameter_m, distance_m)
        )

    net_sd = SpectralData(
        name="optics.transmission.telescope_plus_filters",
        wavelength_um=wavelength_um.copy(),
        values=net_vals,
        unit="",
        source=f"Telescope + {len(filter_specs)} filter(s)",
    )

    # Synthesize telescope element as lumped.
    tele_elem = make_lumped_element(
        tele_sd,
        temperature_K,
        diameter_m,
        distance_m,
        name="telescope_lumped",
    )

    return TransmissionResult(
        mode=TransmissionInputMode.TELESCOPE_PLUS_FILTERS,
        transmission=net_sd,
        elements=(tele_elem, *filter_elements),
    )


def _resolve_key_elements(
    wavelength_um: np.ndarray,
    key_elements: tuple[OpticalElement, ...],
    residual_transmission: SpectralData | float | None,
    temperature_K: float,
    diameter_m: float,
    distance_m: float,
) -> TransmissionResult:
    """Mode 4: key elements plus a residual lumped transmission."""
    if not key_elements:
        raise ValueError(
            "resolve_transmission: KEY_ELEMENTS mode requires at least one element in key_elements."
        )

    # Resolve residual.
    if residual_transmission is None:
        residual_transmission = 1.0  # no residual loss

    if isinstance(residual_transmission, int | float):
        res_sd = SpectralData(
            name="optics.residual_transmission",
            wavelength_um=wavelength_um.copy(),
            values=np.full_like(wavelength_um, float(residual_transmission)),
            unit="",
            source=f"Residual scalar: {residual_transmission}",
        )
    else:
        res_sd = residual_transmission

    # System transmission = residual * product of key element net transmittances.
    net_vals = res_sd.values.copy()
    for elem in key_elements:
        net_vals = net_vals * elem.net_transmittance.values

    net_sd = SpectralData(
        name="optics.transmission.key_elements",
        wavelength_um=wavelength_um.copy(),
        values=net_vals,
        unit="",
        source=f"{len(key_elements)} key element(s) + residual",
    )

    # Residual as lumped element.
    res_elem = make_lumped_element(
        res_sd,
        temperature_K,
        diameter_m,
        distance_m,
        name="residual_lumped",
    )

    return TransmissionResult(
        mode=TransmissionInputMode.KEY_ELEMENTS,
        transmission=net_sd,
        elements=(*key_elements, res_elem),
    )


def _resolve_full_prescription(
    wavelength_um: np.ndarray,
    full_elements: tuple[OpticalElement, ...],
) -> TransmissionResult:
    """Mode 5: full element-by-element prescription."""
    if not full_elements:
        raise ValueError(
            "resolve_transmission: FULL_PRESCRIPTION mode requires at "
            "least one element in full_elements."
        )
    tau_sd = compute_system_transmission(full_elements, wavelength_um)
    return TransmissionResult(
        mode=TransmissionInputMode.FULL_PRESCRIPTION,
        transmission=tau_sd,
        elements=full_elements,
    )
