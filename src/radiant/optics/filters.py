"""Optical filter shape functions — bandpass, longpass, shortpass, notch, tabulated.

Per RADIANT_Optics.md section 6.2, filters are modeled with idealized
spectral shapes.  Real measured profiles use the ``tabulated`` type.

All filter shapes use raised-cosine edge transitions for smooth
differentiability.  Edge width defaults to 10% of the characteristic
wavelength (FWHM for bandpass/notch, cut wavelength for pass filters).
"""

from __future__ import annotations

import enum
import logging
from dataclasses import dataclass

import numpy as np

from radiant.core.spectral import SpectralData
from radiant.optics.element import ElementKind, OpticalElement
from radiant.optics.errors import OpticsValidationError

logger = logging.getLogger(__name__)


class FilterType(enum.Enum):
    """Filter shape types."""

    BANDPASS = "bandpass"
    LONGPASS = "longpass"
    SHORTPASS = "shortpass"
    NOTCH = "notch"
    TABULATED = "tabulated"


@dataclass(frozen=True)
class FilterSpec:
    """Specification for a single optical filter.

    Only the fields relevant to the chosen ``filter_type`` are used.
    Construction validates that the required fields are set.

    Parameters
    ----------
    filter_type:
        Shape type.
    center_um:
        Center wavelength for bandpass/notch [um].
    fwhm_um:
        Full-width at half-max for bandpass/notch [um].
    cuton_um:
        Cut-on wavelength for longpass [um].
    cutoff_um:
        Cut-off wavelength for shortpass [um].
    peak_transmission:
        In-band peak transmission [0, 1].
    oob_rejection:
        Out-of-band floor transmission [0, 1].
    min_transmission:
        Minimum (in-notch) transmission for notch filter [0, 1].
    transmission_file:
        Path to tabulated transmission file (CSV or NPZ).
    name:
        Human-readable label.
    """

    filter_type: FilterType
    center_um: float | None = None
    fwhm_um: float | None = None
    cuton_um: float | None = None
    cutoff_um: float | None = None
    peak_transmission: float = 0.95
    oob_rejection: float = 1e-4
    min_transmission: float | None = None
    transmission_file: str | None = None
    name: str = "filter"

    def __post_init__(self) -> None:
        ft = self.filter_type
        if ft == FilterType.BANDPASS:
            if self.center_um is None or self.fwhm_um is None:
                raise OpticsValidationError(
                    f"FilterSpec '{self.name}': bandpass requires center_um and fwhm_um."
                )
            if self.fwhm_um <= 0:
                raise OpticsValidationError(f"FilterSpec '{self.name}': fwhm_um must be > 0.")
        elif ft == FilterType.LONGPASS:
            if self.cuton_um is None:
                raise OpticsValidationError(
                    f"FilterSpec '{self.name}': longpass requires cuton_um."
                )
        elif ft == FilterType.SHORTPASS:
            if self.cutoff_um is None:
                raise OpticsValidationError(
                    f"FilterSpec '{self.name}': shortpass requires cutoff_um."
                )
        elif ft == FilterType.NOTCH:
            if self.center_um is None or self.fwhm_um is None:
                raise OpticsValidationError(
                    f"FilterSpec '{self.name}': notch requires center_um and fwhm_um."
                )
            if self.min_transmission is None:
                raise OpticsValidationError(
                    f"FilterSpec '{self.name}': notch requires min_transmission."
                )
        elif ft == FilterType.TABULATED:
            if self.transmission_file is None:
                raise OpticsValidationError(
                    f"FilterSpec '{self.name}': tabulated requires transmission_file."
                )

        if not 0.0 <= self.peak_transmission <= 1.0:
            raise OpticsValidationError(
                f"FilterSpec '{self.name}': peak_transmission must be in "
                f"[0, 1], got {self.peak_transmission}."
            )
        if not 0.0 <= self.oob_rejection <= 1.0:
            raise OpticsValidationError(
                f"FilterSpec '{self.name}': oob_rejection must be in "
                f"[0, 1], got {self.oob_rejection}."
            )


# ---------------------------------------------------------------------------
# Edge shape: raised cosine transition
# ---------------------------------------------------------------------------


def _raised_cosine_transition(
    wavelength_um: np.ndarray,
    center: float,
    width: float,
    low: float,
    high: float,
    rising: bool = True,
) -> np.ndarray:
    """Smooth transition from *low* to *high* over a cosine bell.

    The transition is centered at *center* with total width *width*.
    ``rising=True``: low on the left, high on the right.
    ``rising=False``: high on the left, low on the right.
    """
    half = width / 2.0
    left = center - half
    right = center + half

    mask = (wavelength_um >= left) & (wavelength_um <= right)
    t = (wavelength_um[mask] - left) / width  # 0..1
    # Smooth blend 0→1 via raised cosine
    blend = 0.5 * (1.0 - np.cos(np.pi * t))

    if rising:
        result = np.full_like(wavelength_um, low)
        result[mask] = low + (high - low) * blend
        result[wavelength_um > right] = high
    else:
        result = np.full_like(wavelength_um, high)
        result[mask] = high + (low - high) * blend
        result[wavelength_um > right] = low

    return result


# ---------------------------------------------------------------------------
# Filter shape functions
# ---------------------------------------------------------------------------


def _bandpass_transmission(
    wavelength_um: np.ndarray,
    center_um: float,
    fwhm_um: float,
    peak: float,
    oob: float,
) -> np.ndarray:
    """Top-hat bandpass with raised-cosine edges."""
    edge_width = 0.1 * fwhm_um
    half_band = fwhm_um / 2.0

    # Rising edge at center - half_band
    rising = _raised_cosine_transition(
        wavelength_um,
        center=center_um - half_band,
        width=edge_width,
        low=oob,
        high=peak,
        rising=True,
    )
    # Falling edge at center + half_band
    falling = _raised_cosine_transition(
        wavelength_um,
        center=center_um + half_band,
        width=edge_width,
        low=oob,
        high=peak,
        rising=False,
    )
    # In-band: both are high. Out-of-band: at least one is low.
    return np.minimum(rising, falling)


def _longpass_transmission(
    wavelength_um: np.ndarray,
    cuton_um: float,
    peak: float,
    oob: float,
) -> np.ndarray:
    """Step-up at cuton with raised-cosine transition."""
    edge_width = 0.1 * cuton_um
    return _raised_cosine_transition(
        wavelength_um,
        center=cuton_um,
        width=edge_width,
        low=oob,
        high=peak,
        rising=True,
    )


def _shortpass_transmission(
    wavelength_um: np.ndarray,
    cutoff_um: float,
    peak: float,
    oob: float,
) -> np.ndarray:
    """Step-down at cutoff with raised-cosine transition."""
    edge_width = 0.1 * cutoff_um
    return _raised_cosine_transition(
        wavelength_um,
        center=cutoff_um,
        width=edge_width,
        low=oob,
        high=peak,
        rising=False,
    )


def _notch_transmission(
    wavelength_um: np.ndarray,
    center_um: float,
    fwhm_um: float,
    peak: float,
    min_trans: float,
) -> np.ndarray:
    """Inverse top-hat: peak outside, min inside the notch."""
    edge_width = 0.1 * fwhm_um
    half_band = fwhm_um / 2.0

    # Falling edge into notch at center - half_band
    falling = _raised_cosine_transition(
        wavelength_um,
        center=center_um - half_band,
        width=edge_width,
        low=min_trans,
        high=peak,
        rising=False,
    )
    # Rising edge out of notch at center + half_band
    rising = _raised_cosine_transition(
        wavelength_um,
        center=center_um + half_band,
        width=edge_width,
        low=min_trans,
        high=peak,
        rising=True,
    )
    return np.maximum(falling, rising)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def make_filter_transmission(
    spec: FilterSpec,
    wavelength_um: np.ndarray,
) -> SpectralData:
    """Evaluate a filter specification on a wavelength grid.

    Parameters
    ----------
    spec:
        Filter specification.
    wavelength_um:
        Wavelength grid in microns (ascending).

    Returns
    -------
    SpectralData
        Filter transmission on the given grid, dimensionless [0, 1].
    """
    ft = spec.filter_type

    if ft == FilterType.BANDPASS:
        assert spec.center_um is not None and spec.fwhm_um is not None
        vals = _bandpass_transmission(
            wavelength_um,
            spec.center_um,
            spec.fwhm_um,
            spec.peak_transmission,
            spec.oob_rejection,
        )
    elif ft == FilterType.LONGPASS:
        assert spec.cuton_um is not None
        vals = _longpass_transmission(
            wavelength_um,
            spec.cuton_um,
            spec.peak_transmission,
            spec.oob_rejection,
        )
    elif ft == FilterType.SHORTPASS:
        assert spec.cutoff_um is not None
        vals = _shortpass_transmission(
            wavelength_um,
            spec.cutoff_um,
            spec.peak_transmission,
            spec.oob_rejection,
        )
    elif ft == FilterType.NOTCH:
        assert spec.center_um is not None and spec.fwhm_um is not None
        assert spec.min_transmission is not None
        vals = _notch_transmission(
            wavelength_um,
            spec.center_um,
            spec.fwhm_um,
            spec.peak_transmission,
            spec.min_transmission,
        )
    elif ft == FilterType.TABULATED:
        raise OpticsValidationError(
            f"FilterSpec '{spec.name}': tabulated filters must be loaded "
            "externally and passed as preloaded SpectralData. Use "
            "make_filter_transmission only for analytic filter shapes."
        )
    else:
        raise OpticsValidationError(f"Unknown filter type: {ft}")

    return SpectralData(
        name=f"filter.{spec.name}",
        wavelength_um=wavelength_um.copy(),
        values=vals,
        unit="",
        source=f"Analytic {ft.value} filter ({spec.name})",
    )


def filter_to_element(
    spec: FilterSpec,
    wavelength_um: np.ndarray,
    temperature_K: float,
    diameter_m: float,
    distance_to_fpa_m: float,
    default_reflectance_per_surface: float = 0.005,
) -> OpticalElement:
    """Create an OpticalElement of kind FILTER from a FilterSpec.

    Parameters
    ----------
    spec:
        Filter specification.
    wavelength_um:
        Wavelength grid.
    temperature_K:
        Filter temperature in Kelvin.
    diameter_m:
        Clear aperture of the filter.
    distance_to_fpa_m:
        Distance from filter to FPA.
    default_reflectance_per_surface:
        Per-surface Fresnel reflectance for coated substrates (default 0.5%).
    """
    tau = make_filter_transmission(spec, wavelength_um)

    n_surfaces = 2  # standard filter has two surfaces
    total_reflectance = default_reflectance_per_surface * n_surfaces

    rho = SpectralData(
        name=f"filter.{spec.name}.reflectance",
        wavelength_um=wavelength_um.copy(),
        values=np.full_like(wavelength_um, total_reflectance),
        unit="",
        source=f"Default Fresnel ({n_surfaces} surfaces × {default_reflectance_per_surface})",
    )

    # Ensure T + R <= 1: clip transmittance if needed.
    max_tau = 1.0 - total_reflectance
    clipped_vals = np.minimum(tau.values, max_tau)
    tau_clipped = SpectralData(
        name=tau.name,
        wavelength_um=tau.wavelength_um,
        values=clipped_vals,
        unit=tau.unit,
        source=tau.source,
    )

    return OpticalElement(
        name=spec.name,
        kind=ElementKind.FILTER,
        temperature_K=temperature_K,
        transmittance=tau_clipped,
        reflectance=rho,
        diameter_m=diameter_m,
        distance_to_fpa_m=distance_to_fpa_m,
        n_surfaces=n_surfaces,
    )
