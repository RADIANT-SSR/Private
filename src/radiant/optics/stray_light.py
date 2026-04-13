"""Stray light computation — four input modes per RADIANT_Optics.md section 8.

Stray light contributes electrons (and shot noise) to every pixel uniformly
but is NOT part of the signal.  It appears in the noise budget, not the
signal numerator.

Modes:
    veiling_glare:        E_stray = fraction * E_in_fov
    absolute_irradiance:  E_stray = E_total / bandwidth (flat spectral density)
    spectral_file:        E_stray = preloaded SpectralData
    pst_file:             stubbed (NotImplementedError)
"""

from __future__ import annotations

import enum
import logging
from dataclasses import dataclass

import numpy as np

from radiant.core.spectral import SpectralData

logger = logging.getLogger(__name__)


class StrayLightInputMode(enum.Enum):
    """Stray light input modes."""

    VEILING_GLARE = "veiling_glare"
    ABSOLUTE_IRRADIANCE = "absolute_irradiance"
    SPECTRAL_FILE = "spectral_file"
    PST_FILE = "pst_file"


@dataclass(frozen=True)
class StrayLightConfig:
    """Configuration for stray light computation.

    Parameters
    ----------
    input_mode:
        Which stray light model to use.
    veiling_glare_fraction:
        Fraction of in-FOV irradiance that becomes stray light [0, 1].
    absolute_irradiance_W_m2:
        Total in-band stray irradiance at FPA [W/m^2].
    spectral_file:
        Path to spectral stray light file (for provenance only;
        actual data must be preloaded externally).
    pst_file:
        Path to PST file (stubbed in v1).
    includes_thermal:
        If True, stray light measurement already includes warm-optics
        scatter; nearfield should be suppressed to avoid double-counting.
    """

    input_mode: StrayLightInputMode
    veiling_glare_fraction: float = 0.0
    absolute_irradiance_W_m2: float = 0.0
    spectral_file: str | None = None
    pst_file: str | None = None
    includes_thermal: bool = False

    def __post_init__(self) -> None:
        if self.input_mode == StrayLightInputMode.VEILING_GLARE:
            if not 0.0 <= self.veiling_glare_fraction <= 1.0:
                raise ValueError(
                    f"StrayLightConfig: veiling_glare_fraction must be in "
                    f"[0, 1], got {self.veiling_glare_fraction}."
                )
        elif self.input_mode == StrayLightInputMode.ABSOLUTE_IRRADIANCE:
            if self.absolute_irradiance_W_m2 < 0.0:
                raise ValueError(
                    f"StrayLightConfig: absolute_irradiance_W_m2 must be "
                    f">= 0, got {self.absolute_irradiance_W_m2}."
                )
        elif self.input_mode == StrayLightInputMode.SPECTRAL_FILE:
            if not self.spectral_file:
                raise ValueError(
                    "StrayLightConfig: spectral_file mode requires a non-empty spectral_file path."
                )
        elif self.input_mode == StrayLightInputMode.PST_FILE and not self.pst_file:
            raise ValueError("StrayLightConfig: pst_file mode requires a non-empty pst_file path.")


def compute_stray_light_irradiance(
    config: StrayLightConfig,
    wavelength_um: np.ndarray,
    in_fov_irradiance: SpectralData | None = None,
    preloaded_spectral: SpectralData | None = None,
) -> SpectralData:
    """Compute stray light irradiance at the FPA.

    Parameters
    ----------
    config:
        Stray light configuration.
    wavelength_um:
        Wavelength grid in microns.
    in_fov_irradiance:
        Required for veiling_glare mode — the in-FOV image-plane
        irradiance [W/m^2/um].
    preloaded_spectral:
        Required for spectral_file mode — pre-loaded stray light
        spectral data [W/m^2/um].

    Returns
    -------
    SpectralData
        Stray light irradiance at the FPA in W/m^2/um.
    """
    mode = config.input_mode

    if mode == StrayLightInputMode.VEILING_GLARE:
        if in_fov_irradiance is None:
            raise ValueError(
                "compute_stray_light_irradiance: veiling_glare mode requires "
                "in_fov_irradiance to be provided."
            )
        vals = config.veiling_glare_fraction * in_fov_irradiance.values
        return SpectralData(
            name="optics.stray_light.veiling_glare",
            wavelength_um=wavelength_um.copy(),
            values=vals,
            unit="W/m^2/um",
            source=f"Veiling glare: {config.veiling_glare_fraction} x E_in_fov",
        )

    if mode == StrayLightInputMode.ABSOLUTE_IRRADIANCE:
        bandwidth_um = float(wavelength_um[-1] - wavelength_um[0])
        if bandwidth_um <= 0:
            raise ValueError(
                "compute_stray_light_irradiance: wavelength grid must span a positive bandwidth."
            )
        spectral_density = config.absolute_irradiance_W_m2 / bandwidth_um
        return SpectralData(
            name="optics.stray_light.absolute",
            wavelength_um=wavelength_um.copy(),
            values=np.full_like(wavelength_um, spectral_density),
            unit="W/m^2/um",
            source=(
                f"Absolute irradiance: {config.absolute_irradiance_W_m2} W/m^2 "
                f"/ {bandwidth_um:.3f} um bandwidth"
            ),
        )

    if mode == StrayLightInputMode.SPECTRAL_FILE:
        if preloaded_spectral is None:
            raise ValueError(
                "compute_stray_light_irradiance: spectral_file mode requires "
                "preloaded_spectral to be provided. File I/O must happen "
                "outside the stage run (Rule 6)."
            )
        return SpectralData(
            name="optics.stray_light.spectral_file",
            wavelength_um=wavelength_um.copy(),
            values=preloaded_spectral.values.copy(),
            unit="W/m^2/um",
            source=f"Spectral file: {config.spectral_file}",
        )

    if mode == StrayLightInputMode.PST_FILE:
        raise NotImplementedError(
            "PST-based stray light requires scene radiance distribution "
            "not available in RADIANT v1. Use veiling_glare, "
            "absolute_irradiance, or spectral_file modes instead."
        )

    raise ValueError(f"Unknown stray light mode: {mode}")
