"""S11 brightness-temperature → TargetDescriptor converter.

Brightness temperature ``T_B(λ)`` is the equivalent-blackbody temperature
that produces the same spectral radiance as the source at wavelength ``λ``:
``L(λ) = B(λ, T_B(λ))``.  When ``T_B`` is λ-independent, ``T_B`` equals the
physical blackbody temperature and the source is a perfect blackbody; when
``T_B`` varies with ``λ``, the source is either a graybody (constant ε < 1)
or a selective emitter.

This converter maps the user-supplied ``T_B`` to a canonical
:class:`~radiant.core.descriptors.TargetDescriptor`:

- **(Near-)constant T_B** (peak-to-peak ≤ ``constant_threshold_K``, default
  1 K): :class:`~radiant.core.descriptors.T1Thermal` with ``T_t`` = mean
  ``T_B`` and ``ε ≡ 1``.  Exact at every λ because the source *is* a
  blackbody at that temperature.
- **λ-varying T_B**: :class:`~radiant.core.descriptors.T6TabulatedAtSource`
  carrying ``L_source = B(λ, T_B(λ))`` per ADR-0003.  Exact at every λ
  because ``L_source`` is precomputed on the chain grid before atmospheric
  transport.

Rule 19 — this module holds exactly the S11 boundary conversion.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from radiant.core.blackbody import planck_spectral_radiance
from radiant.core.descriptors import (
    NoAtmosphereSubcase,
    SceneType,
    T1Thermal,
    T6TabulatedAtSource,
    TargetDescriptor,
    TargetLocation,
)
from radiant.core.parameters import ParameterBoundsError
from radiant.core.spectral import SpectralData
from radiant.source.converters._csv import load_two_column_csv

# ---------------------------------------------------------------------------
# Bounds — same semantics as ``source.target.temperature`` schema, widened
# to 10_000 K per implementation plan Step 2.1 (solar effective T ≈ 5778 K
# is the physical ceiling we care about; 10_000 K rejects unit errors).
# ---------------------------------------------------------------------------

_T_B_MIN_K: float = 0.0
_T_B_MAX_K: float = 10_000.0

# Peak-to-peak window inside which T_B is treated as "near-constant" and
# collapsed to T1Thermal.  1 K is ≈ 0.3% of 300 K, well below the noise
# floor of any reasonable S11 measurement.
_CONSTANT_THRESHOLD_K: float = 1.0


def _grey_epsilon(wavelength_um: np.ndarray) -> SpectralData:
    """Build ε(λ) ≡ 1 on the chain wavelength grid.

    T_B is defined against a blackbody reference; emitting T1Thermal with
    ε ≡ 1 makes the radiance identity ``L = ε·B(λ, T_t) = B(λ, T_B)``
    hold exactly.
    """
    lam = np.asarray(wavelength_um, dtype=np.float64)
    return SpectralData(
        name="source.target.epsilon_from_T_B",
        wavelength_um=lam,
        values=np.ones_like(lam),
        unit="",
        source="source.converters.brightness_temperature (ε≡1; T_B supplied)",
    )


def _planck_at_per_point_temperature(
    wavelength_um: np.ndarray,
    T_B_K: np.ndarray,
) -> np.ndarray:
    """Return ``B(λ_i, T_B_i)`` pointwise in W/m²/sr/µm.

    ``planck_spectral_radiance`` is scalar-T only; we call it per sample so
    every array element sees its own ``T_B`` without re-deriving the Planck
    formula here (Rule 13: one source of truth for ``B``).
    """
    lam = np.asarray(wavelength_um, dtype=np.float64)
    T = np.asarray(T_B_K, dtype=np.float64)
    out = np.empty_like(lam)
    for i in range(lam.size):
        # planck_spectral_radiance wraps scalars to 1-D arrays; read [0].
        out[i] = float(
            planck_spectral_radiance(np.asarray([lam[i]], dtype=np.float64), float(T[i]))[0]
        )
    return out


def _validate_T_B(T_B_K: np.ndarray) -> None:
    """Raise :class:`ParameterBoundsError` if any T_B value is out of range.

    Rule 15: actionable error with why / action.  Rule 17: no silent
    clipping — out-of-band inputs fail fast.
    """
    if T_B_K.size == 0:
        raise ParameterBoundsError(
            what=("brightness_temperature: T_B SpectralData has zero samples"),
            why=("The converter needs at least one (λ, T_B) pair to emit a descriptor."),
            action=(
                "Supply T_B on the chain wavelength grid (at least two "
                "points for the SpectralData constructor)."
            ),
            context={},
        )
    if np.any(T_B_K < _T_B_MIN_K):
        bad = float(T_B_K.min())
        raise ParameterBoundsError(
            what=(f"brightness_temperature: T_B = {bad} K is negative"),
            why=(
                "Brightness temperature is an equivalent absolute "
                "temperature; negative values have no Planck interpretation."
            ),
            action=(f"Set every T_B value ≥ {_T_B_MIN_K} K (use 0 K only for zero radiance)."),
            context={"min_T_B_K": bad, "floor_K": _T_B_MIN_K},
        )
    if np.any(T_B_K > _T_B_MAX_K):
        bad = float(T_B_K.max())
        raise ParameterBoundsError(
            what=(f"brightness_temperature: T_B = {bad} K exceeds {_T_B_MAX_K} K ceiling"),
            why=(
                "T_B > 10 000 K is non-physical for RADIANT targets "
                "(solar effective T ≈ 5778 K is already in the "
                "reflective-dominated regime).  Values this large are "
                "typically a unit error (°C vs K) or an input scale bug."
            ),
            action=("Verify units (canonical K, not °C) and the T_B array values."),
            context={"max_T_B_K": bad, "ceiling_K": _T_B_MAX_K},
        )


def brightness_temperature_to_descriptor(
    T_B: SpectralData,
    *,
    scene_type: SceneType,
    target_location: TargetLocation,
    no_atmosphere_subcase: NoAtmosphereSubcase | None = None,
    h_tgt: float | None = None,
    A_t: float | None = None,
    shape: object | None = None,
    constant_threshold_K: float = _CONSTANT_THRESHOLD_K,
) -> TargetDescriptor:
    """Convert a user-supplied T_B(λ) into a canonical TargetDescriptor.

    Parameters
    ----------
    T_B:
        :class:`SpectralData` in K on the chain wavelength grid.  May be
        flat (constant across λ — collapses to T1Thermal) or λ-dependent
        (routed to T6TabulatedAtSource with precomputed ``L_source``).
    scene_type, target_location, no_atmosphere_subcase, h_tgt:
        Matrix-axes metadata, passed through to the constructed
        descriptor.  ``at_aperture`` is rejected — that cell is the S9
        domain (T5AtAperture) and has no atmospheric transport for T_B
        to inform.
    A_t, shape:
        Optional projected-area surface; passed through to the descriptor.
    constant_threshold_K:
        Peak-to-peak T_B window inside which the spectrum is treated as
        scalar and collapsed to T1Thermal.  Default 1 K; exposed for
        tests that want to force one branch or the other.

    Returns
    -------
    TargetDescriptor
        :class:`T1Thermal` (near-constant T_B, ε ≡ 1) or
        :class:`T6TabulatedAtSource` (λ-varying T_B, L_source = B(λ, T_B(λ))).

    Raises
    ------
    ParameterBoundsError
        * ``target_location == 'at_aperture'``.
        * Any ``T_B < 0`` or ``T_B > 10 000`` K.
        * Empty ``T_B.values`` array.
        * Mean ``T_B`` ≤ 0 on the constant branch (rejected for Planck
          emission in :class:`T1Thermal`).
    """
    if target_location == "at_aperture":
        raise ParameterBoundsError(
            what=("brightness_temperature: target_location='at_aperture' is not supported"),
            why=(
                "At-aperture (S9) specifies radiance already at the "
                "sensor aperture; there is no up-leg transport for T_B "
                "to inform.  Use T5AtAperture directly for S9."
            ),
            action=(
                "Set target_location to 'terrestrial', 'airborne', or "
                "'no_atmosphere' so atmospheric transport applies; or "
                "remove T_B and supply L_t_aperture via T5."
            ),
            context={"target_location": target_location},
        )

    lam = np.asarray(T_B.wavelength_um, dtype=np.float64)
    T_vals = np.asarray(T_B.values, dtype=np.float64)
    _validate_T_B(T_vals)

    peak_to_peak_K = float(T_vals.max() - T_vals.min())
    if peak_to_peak_K <= constant_threshold_K:
        T_t = float(T_vals.mean())
        if T_t <= 0.0:
            raise ParameterBoundsError(
                what=(f"brightness_temperature: mean T_B = {T_t} K is non-positive"),
                why=("T1Thermal requires T_t > 0 K for Planck emission."),
                action="Supply T_B > 0 K.",
                context={"mean_T_B_K": T_t},
            )
        return T1Thermal(
            scene_type=scene_type,
            target_location=target_location,
            no_atmosphere_subcase=no_atmosphere_subcase,
            h_tgt=h_tgt,
            epsilon=_grey_epsilon(lam),
            T_t=T_t,
            A_t=A_t,
            shape=shape,
        )

    # λ-varying T_B → T6 with L_source precomputed on the chain grid.
    L_vals = _planck_at_per_point_temperature(lam, T_vals)
    L_source = SpectralData(
        name="source.target.L_from_T_B",
        wavelength_um=lam,
        values=L_vals,
        unit="W/m^2/sr/um",
        source=("source.converters.brightness_temperature (L = B(λ, T_B(λ)); ADR-0003)"),
    )
    return T6TabulatedAtSource(
        scene_type=scene_type,
        target_location=target_location,
        no_atmosphere_subcase=no_atmosphere_subcase,
        h_tgt=h_tgt,
        L_t_source=L_source,
        A_t=A_t,
        shape=shape,
    )


def load_brightness_temperature_csv(path: Path | str) -> SpectralData:
    """Load an S11 brightness-temperature CSV into a :class:`SpectralData`.

    Thin wrapper around :func:`load_two_column_csv` that fixes the S11
    metadata (unit = K, column label = ``brightness_temperature``) so
    callers can't accidentally mislabel the file at the boundary.

    The returned :class:`SpectralData` is on the CSV's native wavelength
    grid; the caller is responsible for resampling onto the chain grid.
    """
    return load_two_column_csv(
        path,
        value_unit="K",
        column_label="brightness_temperature",
        sd_name="source.target.brightness_temperature",
        sd_source_prefix="source.converters.brightness_temperature",
    )


__all__ = [
    "brightness_temperature_to_descriptor",
    "load_brightness_temperature_csv",
]
