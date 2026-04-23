"""S12 band-averaged radiance-temperature → TargetDescriptor converter.

Radiance temperature ``T_R`` is the scalar equivalent-blackbody temperature
whose in-band integrated radiance matches the target's in-band integrated
radiance over ``[λ_lo, λ_hi]``:

``∫_{band} B(λ, T_R) dλ = ∫_{band} L_target(λ) dλ``

In the simple user-entry case — T_R is supplied along with the band and
no spectral emissivity — the target is treated as a blackbody at T_R and
the converter emits :class:`T1Thermal` with ``T_t = T_R`` and ``ε ≡ 1``.
The inversion harness (:mod:`source.converters.invert_band_radiance`) is
provided for future use cases where a user supplies an in-band integrated
radiance and needs T_equiv recovered.

Rule 19 — this module owns exactly the S12 boundary conversion.
"""

from __future__ import annotations

import numpy as np

from radiant.core.descriptors import (
    NoAtmosphereSubcase,
    SceneType,
    T1Thermal,
    TargetDescriptor,
    TargetLocation,
)
from radiant.core.parameters import ParameterBoundsError
from radiant.core.spectral import SpectralData

_T_R_MIN_K: float = 0.0
_T_R_MAX_K: float = 10_000.0


def _grey_epsilon(wavelength_um: np.ndarray) -> SpectralData:
    """Build ε(λ) ≡ 1 on the chain wavelength grid.

    Same rationale as the S11 helper: T_R is defined against a blackbody,
    so emitting T1Thermal with ε ≡ 1 makes the in-band radiance identity
    hold exactly at the boundary (downstream transport is handled by the
    atmosphere / optics stages).
    """
    lam = np.asarray(wavelength_um, dtype=np.float64)
    return SpectralData(
        name="source.target.epsilon_from_T_R",
        wavelength_um=lam,
        values=np.ones_like(lam),
        unit="",
        source=(
            "source.converters.radiance_temperature (ε≡1; T_R supplied)"
        ),
    )


def _validate_inputs(
    T_R_K: float,
    band_um: tuple[float, float],
) -> None:
    """Raise :class:`ParameterBoundsError` on invalid T_R or band."""
    if not np.isfinite(T_R_K):
        raise ParameterBoundsError(
            what=f"radiance_temperature: T_R = {T_R_K} K is not finite",
            why="T_R must be a real temperature in K.",
            action="Supply T_R as a finite positive number.",
            context={"T_R_K": T_R_K},
        )
    if T_R_K <= _T_R_MIN_K:
        raise ParameterBoundsError(
            what=(
                f"radiance_temperature: T_R = {T_R_K} K is non-positive"
            ),
            why=(
                "T1Thermal requires T_t > 0 K for Planck emission; T_R "
                "represents an absolute temperature."
            ),
            action=f"Supply T_R > {_T_R_MIN_K} K.",
            context={"T_R_K": T_R_K},
        )
    if T_R_K > _T_R_MAX_K:
        raise ParameterBoundsError(
            what=(
                f"radiance_temperature: T_R = {T_R_K} K exceeds "
                f"{_T_R_MAX_K} K ceiling"
            ),
            why=(
                "T_R > 10 000 K is non-physical for RADIANT targets and "
                "typically indicates a unit error (°C vs K)."
            ),
            action="Verify units (canonical K, not °C).",
            context={"T_R_K": T_R_K, "ceiling_K": _T_R_MAX_K},
        )

    lo, hi = float(band_um[0]), float(band_um[1])
    if lo <= 0.0 or hi <= 0.0:
        raise ParameterBoundsError(
            what=(
                f"radiance_temperature: band = ({lo}, {hi}) µm has "
                "non-positive edges"
            ),
            why="Wavelengths must be strictly positive for Planck's law.",
            action="Supply band edges in µm with 0 < λ_lo < λ_hi.",
            context={"band_um": (lo, hi)},
        )
    if lo >= hi:
        raise ParameterBoundsError(
            what=(
                f"radiance_temperature: band = ({lo}, {hi}) µm is inverted "
                "or degenerate (λ_lo ≥ λ_hi)"
            ),
            why="Band integration requires λ_lo < λ_hi (strict).",
            action="Swap band edges so λ_lo is the smaller wavelength.",
            context={"band_um": (lo, hi)},
        )


def radiance_temperature_to_descriptor(
    T_R_K: float,
    band_um: tuple[float, float],
    wavelength_um: np.ndarray,
    *,
    scene_type: SceneType,
    target_location: TargetLocation,
    no_atmosphere_subcase: NoAtmosphereSubcase | None = None,
    h_tgt: float | None = None,
    A_t: float | None = None,
    shape: object | None = None,
) -> TargetDescriptor:
    """Convert a scalar T_R + band into a canonical TargetDescriptor.

    Parameters
    ----------
    T_R_K:
        Scalar band-averaged radiance temperature [K]; ``0 < T_R ≤ 10 000``.
    band_um:
        ``(λ_lo, λ_hi)`` tuple in µm; ``0 < λ_lo < λ_hi``.
    wavelength_um:
        Chain wavelength grid on which to build ε(λ) ≡ 1.  Typically the
        full simulation grid, not the (narrower) T_R band.
    scene_type, target_location, no_atmosphere_subcase, h_tgt:
        Matrix-axes metadata, passed through to the constructed
        descriptor.  ``at_aperture`` is rejected — that cell is the S9
        domain (T5AtAperture) and has no atmospheric transport for T_R
        to inform.
    A_t, shape:
        Optional projected-area surface; passed through to the descriptor.

    Returns
    -------
    TargetDescriptor
        :class:`T1Thermal` with ``T_t = T_R`` and ``ε(λ) ≡ 1``.

    Raises
    ------
    ParameterBoundsError
        * ``target_location == 'at_aperture'``.
        * ``T_R ≤ 0`` or ``T_R > 10 000`` K.
        * Inverted or non-positive ``band_um``.

    Notes
    -----
    The band argument is informational for the boundary hand-off: since
    the target is a blackbody at T_R, ``L(λ) = B(λ, T_R)`` at every
    wavelength — in-band integration is not needed at the boundary, and
    the downstream stages see a canonical T1Thermal.  The band is
    validated here so misconfigured inputs fail at the boundary rather
    than propagate silently.
    """
    if target_location == "at_aperture":
        raise ParameterBoundsError(
            what=(
                "radiance_temperature: target_location='at_aperture' is "
                "not supported"
            ),
            why=(
                "At-aperture (S9) specifies radiance already at the "
                "sensor aperture; there is no up-leg transport for T_R "
                "to inform.  Use T5AtAperture directly for S9."
            ),
            action=(
                "Set target_location to 'terrestrial', 'airborne', or "
                "'no_atmosphere', or remove T_R and supply L_t_aperture."
            ),
            context={"target_location": target_location},
        )

    _validate_inputs(T_R_K, band_um)

    lam = np.asarray(wavelength_um, dtype=np.float64)
    return T1Thermal(
        scene_type=scene_type,
        target_location=target_location,
        no_atmosphere_subcase=no_atmosphere_subcase,
        h_tgt=h_tgt,
        epsilon=_grey_epsilon(lam),
        T_t=float(T_R_K),
        A_t=A_t,
        shape=shape,
    )


__all__ = ["radiance_temperature_to_descriptor"]
