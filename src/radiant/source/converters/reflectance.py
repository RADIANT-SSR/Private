"""S4 / S5 / S6 reflectance → TargetDescriptor converter.

Spec forms S4 (scalar ρ), S5 (tabulated ρ(λ)), and S6 (user-supplied
``albedo`` alias) all describe a purely reflective Lambertian target and
collapse onto :class:`~radiant.core.descriptors.T2Reflective` (ADR-0002).

This converter lifts a user-supplied reflectance — either a scalar in
``[0, 1]`` or a pre-built :class:`SpectralData` in the same range — into
the canonical T2Reflective descriptor on the chain wavelength grid.
The illumination path (solar / ambient) is handled downstream by the
existing :class:`~radiant.source.reflected.ReflectedSolarSource`
pipeline; this module is a pure boundary converter and does no radiance
evaluation.

Rule 19 — this module owns exactly the reflective boundary conversion.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from radiant.core.descriptors import (
    NoAtmosphereSubcase,
    SceneType,
    T2Reflective,
    TargetDescriptor,
    TargetLocation,
)
from radiant.core.parameters import ParameterBoundsError
from radiant.core.reflectance import ScalarLambertianReflectance
from radiant.core.spectral import SpectralData
from radiant.source.converters._csv import load_two_column_csv

_RHO_MIN: float = 0.0
_RHO_MAX: float = 1.0


def load_reflectance_csv(path: Path | str, *, is_albedo: bool) -> SpectralData:
    """Load a two-column ``(wavelength_um, rho)`` CSV into SpectralData.

    Delegates to the shared :func:`load_two_column_csv` reader with
    dimensionless unit.  Caller owns validation (``ρ ∈ [0, 1]``) and
    resampling onto the chain grid — this function is a pure transport.

    Parameters
    ----------
    path:
        Filesystem path to the CSV.  Columns are
        ``(wavelength_um, reflectance)`` — the second column is a
        dimensionless fraction in ``[0, 1]``.  Header row auto-detected.
    is_albedo:
        Cosmetic flag controlling the ``column_label`` embedded in
        error messages.  S5 (``reflectance_path``) and S6
        (``albedo_path``) are aliases for the same quantity; this lets
        errors point back to whichever parameter surface the user set.

    Returns
    -------
    SpectralData
        ρ(λ) on the CSV's native wavelength grid, unit ``"dimensionless"``.
    """
    column_label = "albedo" if is_albedo else "reflectance"
    return load_two_column_csv(
        path,
        value_unit="dimensionless",
        column_label=column_label,
        sd_name="source.target.reflectance",
        sd_source_prefix="source.converters.reflectance",
    )


def _lift_scalar_rho(
    rho_scalar: float,
    wavelength_um: np.ndarray,
) -> SpectralData:
    """Lift a scalar ρ to a constant SpectralData on the chain grid."""
    lam = np.asarray(wavelength_um, dtype=np.float64)
    return SpectralData(
        name="source.target.reflectance",
        wavelength_um=lam,
        values=np.full_like(lam, float(rho_scalar), dtype=np.float64),
        unit="",
        source=("source.converters.reflectance (scalar lift; S4)"),
    )


def _validate_rho(rho_values: np.ndarray) -> None:
    """Raise :class:`ParameterBoundsError` on empty or out-of-range ρ."""
    if rho_values.size == 0:
        raise ParameterBoundsError(
            what=("reflectance: rho SpectralData has zero samples"),
            why=("The converter needs at least one (λ, ρ) pair to emit a descriptor."),
            action=(
                "Supply rho on the chain wavelength grid (at least two "
                "points for the SpectralData constructor)."
            ),
            context={},
        )
    if np.any(rho_values < _RHO_MIN):
        bad = float(rho_values.min())
        raise ParameterBoundsError(
            what=(f"reflectance: rho = {bad} is negative"),
            why=(
                "Reflectance is a dimensionless fraction in [0, 1]; "
                "negative values have no physical interpretation."
            ),
            action=f"Set every rho value ≥ {_RHO_MIN}.",
            context={"min_rho": bad, "floor": _RHO_MIN},
        )
    if np.any(rho_values > _RHO_MAX):
        bad = float(rho_values.max())
        raise ParameterBoundsError(
            what=(f"reflectance: rho = {bad} exceeds 1.0 ceiling"),
            why=(
                "Reflectance > 1 violates energy conservation (reflected "
                "power cannot exceed incident power for a passive surface)."
            ),
            action="Clamp rho ≤ 1 or check for unit / scale errors.",
            context={"max_rho": bad, "ceiling": _RHO_MAX},
        )


def reflectance_to_descriptor(
    rho: SpectralData | float,
    wavelength_um: np.ndarray,
    *,
    scene_type: SceneType,
    target_location: TargetLocation,
    no_atmosphere_subcase: NoAtmosphereSubcase | None = None,
    h_tgt: float | None = None,
    A_t: float | None = None,
) -> TargetDescriptor:
    """Convert a user-supplied ρ (scalar or SpectralData) into a T2Reflective.

    Parameters
    ----------
    rho:
        Scalar in ``[0, 1]`` (lifted to a constant spectrum on
        ``wavelength_um``) or a pre-built :class:`SpectralData` whose
        values are all in ``[0, 1]``.
    wavelength_um:
        Chain wavelength grid (canonical µm).  Used both for scalar
        lifts and to re-index a SpectralData whose native grid differs
        (no resampling here — the inferrer is responsible for supplying
        ρ on the chain grid; this argument documents the invariant).
    scene_type, target_location, no_atmosphere_subcase, h_tgt:
        Matrix-axes metadata, passed through to T2Reflective.
        ``at_aperture`` is rejected — that cell is the S9 domain and has
        no incident irradiance for ρ to modulate.
    A_t:
        Projected-area surface; passed through to the descriptor.

    Returns
    -------
    TargetDescriptor
        :class:`T2Reflective` with ``rho`` populated and ``A_t``
        from the matrix-Q3 resolution.

    Raises
    ------
    ParameterBoundsError
        * ``target_location == 'at_aperture'``.
        * ρ outside ``[0, 1]``.
        * Empty ρ SpectralData.
    """
    if target_location == "at_aperture":
        raise ParameterBoundsError(
            what=("reflectance: target_location='at_aperture' is not supported"),
            why=(
                "At-aperture (S9) specifies radiance already at the "
                "sensor aperture; there is no up-leg illumination for "
                "ρ to modulate.  Use T5AtAperture directly for S9."
            ),
            action=(
                "Set target_location to 'terrestrial', 'airborne', or "
                "'no_atmosphere', or remove reflectance and supply "
                "L_t_aperture via T5."
            ),
            context={"target_location": target_location},
        )

    rho_sd = rho if isinstance(rho, SpectralData) else _lift_scalar_rho(float(rho), wavelength_um)

    _validate_rho(np.asarray(rho_sd.values, dtype=np.float64))

    # Gap H: wrap the SpectralData into a ReflectanceDescriptor adapter so
    # T2Reflective.rho is always protocol-typed.  Scalar-Lambertian adapter
    # is an identity on the chain grid — no physics drift.  MWIR §3.2 warn
    # fires at the descriptor level on the adapter's stored grid.
    rho_descriptor = ScalarLambertianReflectance(reflectance=rho_sd)

    return T2Reflective(
        scene_type=scene_type,
        target_location=target_location,
        no_atmosphere_subcase=no_atmosphere_subcase,
        h_tgt=h_tgt,
        rho=rho_descriptor,
        A_t=A_t,
    )


__all__ = ["load_reflectance_csv", "reflectance_to_descriptor"]
