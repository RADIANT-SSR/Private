"""Wavefront error specification — scalar RMS, Zernike, OPD map, field-dependent.

Per RADIANT_Optics.md section 4, the wavefront error is specified in one of
four modes.  The optics module does NOT compute the PSF or Strehl from the WFE
— that is the spatial module's job.  This module stores the WFE data and
provides convenience conversions (RMS OPD in meters, Marechal Strehl estimate).

Wavelength scaling:
    OPD_m = wfe_waves * reference_wavelength_um * 1e-6
    Strehl = exp(-(2*pi*OPD_rms_m / lambda_m)^2)   (Marechal approximation)

Field-dependent WFE:
    Each field point has its own Zernike coefficient set. No interpolation
    between field points — the user selects a field position that must
    exactly match a tabulated point, or uses at_field_nearest() for
    convenience (with a warning for non-exact matches).

    For refractive systems, Zernike coefficients vary with wavelength
    (chromatic aberration). Each field sample can carry a chromatic_zernikes
    mapping: {wavelength_um: {noll_j: coeff_waves}}.
"""

from __future__ import annotations

import enum
import logging
import math
import warnings
from dataclasses import dataclass

import numpy as np

from radiant.optics.element import ElementTransferMode  # same-stage import (OK)

logger = logging.getLogger(__name__)


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
    zernike_coeffs:
        Noll-indexed Zernike coefficients in waves at the reference
        wavelength. Required for every field sample.
    chromatic_zernikes:
        For refractive systems: wavelength-dependent Zernike coefficients.
        Maps wavelength_um → {noll_j: coeff_waves}. If present, overrides
        zernike_coeffs for polychromatic PSF computation (each monochromatic
        PSF uses the nearest tabulated wavelength's Zernike set).
    """

    field_x_deg: float
    field_y_deg: float
    zernike_coeffs: dict[int, float]
    chromatic_zernikes: dict[float, dict[int, float]] | None = None


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
    optical_type:
        REFLECTIVE or REFRACTIVE. Controls whether chromatic Zernike
        coefficients are required for polychromatic PSF computation.
        Default: REFLECTIVE (achromatic WFE).
    """

    mode: WfeMode
    rms_waves: float | None = None
    reference_wavelength_um: float = 0.633
    zernike_coeffs: dict[int, float] | None = None
    opd_map: np.ndarray | None = None
    field_table: tuple[FieldWfeSample, ...] | None = None
    optical_type: ElementTransferMode = ElementTransferMode.REFLECTIVE

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
            # Validate no duplicate field positions.
            positions = [(s.field_x_deg, s.field_y_deg) for s in self.field_table]
            if len(set(positions)) != len(positions):
                raise ValueError(
                    "WavefrontError: field_table contains duplicate field positions. "
                    "Each (field_x_deg, field_y_deg) must be unique."
                )
            # Validate refractive systems have chromatic_zernikes.
            if self.optical_type == ElementTransferMode.REFRACTIVE:
                for sample in self.field_table:
                    if sample.chromatic_zernikes is None:
                        raise ValueError(
                            f"WavefrontError: REFRACTIVE optical_type requires "
                            f"chromatic_zernikes on every field sample, but the "
                            f"sample at ({sample.field_x_deg}, {sample.field_y_deg}) "
                            f"has chromatic_zernikes=None. Provide wavelength-dependent "
                            f"Zernike coefficients for refractive systems."
                        )
                    if len(sample.chromatic_zernikes) == 1:
                        warnings.warn(
                            f"FieldWfeSample at ({sample.field_x_deg}, "
                            f"{sample.field_y_deg}) has chromatic_zernikes with "
                            f"only 1 wavelength — this is equivalent to achromatic "
                            f"(reflective) behavior.",
                            UserWarning,
                            stacklevel=2,
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

        # For field_dependent, return the on-axis (0, 0) field point's RMS
        # if available, otherwise the first field point.
        assert self.field_table is not None
        on_axis = None
        for sample in self.field_table:
            if sample.field_x_deg == 0.0 and sample.field_y_deg == 0.0:
                on_axis = sample
                break
        if on_axis is None:
            on_axis = self.field_table[0]
            logger.info(
                "rms_opd_m: no on-axis field point found; using first sample at (%.3f, %.3f) deg.",
                on_axis.field_x_deg,
                on_axis.field_y_deg,
            )
        rms_waves = math.sqrt(sum(c**2 for c in on_axis.zernike_coeffs.values()))
        return rms_waves * ref_m

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

    def at_field(self, field_x_deg: float, field_y_deg: float) -> FieldWfeSample:
        """Return the FieldWfeSample at the exact field position.

        No interpolation is performed. The requested coordinates must
        exactly match a tabulated point (within floating-point tolerance
        of 1e-12 degrees).

        Parameters
        ----------
        field_x_deg:
            Cross-track field angle [deg].
        field_y_deg:
            Along-track field angle [deg].

        Returns
        -------
        FieldWfeSample
            The sample at the requested position.

        Raises
        ------
        ValueError
            If the mode is not FIELD_DEPENDENT, or if the requested
            position is not in the field table.
        """
        if self.mode != WfeMode.FIELD_DEPENDENT:
            raise ValueError(f"at_field() requires mode=FIELD_DEPENDENT, got {self.mode.value!r}.")
        assert self.field_table is not None

        tol = 1e-12
        for sample in self.field_table:
            if (
                abs(sample.field_x_deg - field_x_deg) < tol
                and abs(sample.field_y_deg - field_y_deg) < tol
            ):
                return sample

        available = [(s.field_x_deg, s.field_y_deg) for s in self.field_table]
        raise ValueError(
            f"No field sample at ({field_x_deg}, {field_y_deg}) deg. "
            f"Available field positions: {available}. "
            f"Use at_field_nearest() for approximate lookup, or provide "
            f"Zernike coefficients at this exact field position."
        )

    def at_field_nearest(self, field_x_deg: float, field_y_deg: float) -> FieldWfeSample:
        """Return the nearest tabulated FieldWfeSample.

        Warns if the nearest point is more than 0.01 degrees away
        from the requested position.

        Parameters
        ----------
        field_x_deg:
            Cross-track field angle [deg].
        field_y_deg:
            Along-track field angle [deg].

        Returns
        -------
        FieldWfeSample
            The nearest tabulated sample.
        """
        if self.mode != WfeMode.FIELD_DEPENDENT:
            raise ValueError(
                f"at_field_nearest() requires mode=FIELD_DEPENDENT, got {self.mode.value!r}."
            )
        assert self.field_table is not None

        best_dist = float("inf")
        best_sample = self.field_table[0]
        for sample in self.field_table:
            dx = sample.field_x_deg - field_x_deg
            dy = sample.field_y_deg - field_y_deg
            dist = math.sqrt(dx * dx + dy * dy)
            if dist < best_dist:
                best_dist = dist
                best_sample = sample

        if best_dist > 0.01:
            warnings.warn(
                f"Nearest field sample at ({best_sample.field_x_deg}, "
                f"{best_sample.field_y_deg}) deg is {best_dist:.4f} deg "
                f"from requested ({field_x_deg}, {field_y_deg}) deg. "
                f"WFE at this position may not be representative.",
                UserWarning,
                stacklevel=2,
            )

        return best_sample
