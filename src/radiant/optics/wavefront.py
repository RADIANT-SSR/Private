"""Wavefront error specification — scalar RMS, Zernike, OPD map, field-dependent.

Per RADIANT_Optics.md section 4, the wavefront error is specified in one of
four modes.  The optics module does NOT compute the PSF or Strehl from the WFE
— that is the spatial module's job.  This module stores the WFE data and
provides convenience conversions (RMS OPD in meters, Marechal Strehl estimate).

Wavelength scaling:
    OPD_m = wfe_waves * reference_wavelength_um * 1e-6
    Strehl = exp(-(2*pi*OPD_rms_m / lambda_m)^2)   (Marechal approximation)
"""

from __future__ import annotations

import enum
import math
from dataclasses import dataclass

import numpy as np


class WfeMode(enum.Enum):
    """Wavefront error input modes."""

    SCALAR_RMS = "scalar_rms"
    ZERNIKE = "zernike"
    OPD_MAP = "opd_map"
    FIELD_DEPENDENT = "field_dependent"


@dataclass(frozen=True)
class FieldWfeSample:
    """A single WFE measurement at a specific field position.

    Parameters
    ----------
    field_x_deg:
        Field angle in cross-track direction [deg].
    field_y_deg:
        Field angle in along-track direction [deg].
    source_mode:
        How the WFE at this point is specified (scalar_rms or zernike).
    rms_waves:
        RMS WFE in waves (for scalar_rms mode).
    zernike_coeffs:
        Noll-indexed Zernike coefficients in waves (for zernike mode).
    """

    field_x_deg: float
    field_y_deg: float
    source_mode: WfeMode
    rms_waves: float | None = None
    zernike_coeffs: dict[int, float] | None = None


@dataclass(frozen=True)
class WavefrontError:
    """Wavefront error specification.

    Parameters
    ----------
    mode:
        Input mode.
    rms_waves:
        RMS WFE in waves at ``reference_wavelength_um`` (scalar_rms mode).
    reference_wavelength_um:
        Reference wavelength in microns (default: HeNe 0.633 um).
    zernike_coeffs:
        Noll-indexed Zernike coefficients in waves (zernike mode).
    opd_map:
        2-D array of OPD in waves at ``reference_wavelength_um`` (opd_map mode).
    field_table:
        Field-dependent WFE samples (field_dependent mode).
    """

    mode: WfeMode
    rms_waves: float | None = None
    reference_wavelength_um: float = 0.633
    zernike_coeffs: dict[int, float] | None = None
    opd_map: np.ndarray | None = None
    field_table: tuple[FieldWfeSample, ...] | None = None

    def __post_init__(self) -> None:
        if self.reference_wavelength_um <= 0:
            raise ValueError(
                f"WavefrontError: reference_wavelength_um must be > 0, "
                f"got {self.reference_wavelength_um}."
            )

        if self.mode == WfeMode.SCALAR_RMS:
            if self.rms_waves is None:
                raise ValueError("WavefrontError: scalar_rms mode requires rms_waves.")
            if self.rms_waves < 0:
                raise ValueError(f"WavefrontError: rms_waves must be >= 0, got {self.rms_waves}.")
        elif self.mode == WfeMode.ZERNIKE:
            if not self.zernike_coeffs:
                raise ValueError(
                    "WavefrontError: zernike mode requires non-empty zernike_coeffs dict."
                )
        elif self.mode == WfeMode.OPD_MAP:
            if self.opd_map is None:
                raise ValueError("WavefrontError: opd_map mode requires opd_map array.")
            if self.opd_map.ndim != 2:
                raise ValueError(
                    f"WavefrontError: opd_map must be 2-D, got shape {self.opd_map.shape}."
                )
        elif self.mode == WfeMode.FIELD_DEPENDENT:
            if not self.field_table:
                raise ValueError(
                    "WavefrontError: field_dependent mode requires non-empty field_table."
                )

    def rms_opd_m(self) -> float:
        """Return the RMS optical path difference in meters.

        For scalar_rms:  ``rms_waves * lambda_ref * 1e-6``
        For zernike:     ``sqrt(sum(c_i^2)) * lambda_ref * 1e-6``
        For opd_map:     ``std(opd_map) * lambda_ref * 1e-6``
        For field_dependent: raises NotImplementedError.
        """
        ref_m = self.reference_wavelength_um * 1e-6

        if self.mode == WfeMode.SCALAR_RMS:
            assert self.rms_waves is not None
            return self.rms_waves * ref_m

        if self.mode == WfeMode.ZERNIKE:
            assert self.zernike_coeffs is not None
            rms_waves = math.sqrt(sum(c**2 for c in self.zernike_coeffs.values()))
            return rms_waves * ref_m

        if self.mode == WfeMode.OPD_MAP:
            assert self.opd_map is not None
            return float(np.std(self.opd_map)) * ref_m

        raise NotImplementedError(
            "rms_opd_m is not available for field_dependent mode without "
            "specifying a field position."
        )

    def strehl_marechal(self, wavelength_um: float) -> float:
        """Marechal approximation for Strehl ratio.

        ``S = exp(-(2*pi*sigma_OPD / lambda)^2)``

        Valid for WFE < ~lambda/5 (Strehl > ~0.8).

        Parameters
        ----------
        wavelength_um:
            Operating wavelength in microns.

        Returns
        -------
        float
            Estimated Strehl ratio in [0, 1].
        """
        if wavelength_um <= 0:
            raise ValueError(f"strehl_marechal: wavelength_um must be > 0, got {wavelength_um}.")
        sigma_m = self.rms_opd_m()
        lam_m = wavelength_um * 1e-6
        phase_var = (2.0 * math.pi * sigma_m / lam_m) ** 2
        return math.exp(-phase_var)
