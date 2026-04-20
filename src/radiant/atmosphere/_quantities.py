"""AtmosphericQuantities — the spectral-arrays bundle produced by Stage 3 backends.

Option C (ADR-0002) splits the atmosphere contract into a *two-leg*
radiometric product so the §6.1 assembly equation can run on its own::

    L_t,aperture(λ) = [ ε·B(T_t)                           (self-emission)
                        + ρ·τ_sun · E_TOA · cos(θ_s) / π   (direct solar)
                        + ρ · (E_sky_scattered + E_sky_thermal) / π  (diffuse)
                      ] · τ_up
                      + L_path_up                          (upwelling path)

and the background branch uses ``τ_full_up`` and ``L_path_full`` — the
ground-to-sensor attenuation and path radiance — instead of the target-to-
sensor ones.

This dataclass is the **backend output contract** (see
:class:`radiant.atmosphere.protocol.Atmosphere.evaluate`).  Every backend
— simple, exo, tabulated, interpolated, and in later stages MODTRAN —
produces an ``AtmosphericQuantities`` evaluated on the chain wavelength
grid and a single :class:`radiant.core.los_geometry.LineOfSightGeometry`.

Notes
-----
- All eight fields are 1-D ``np.ndarray`` on the same wavelength grid.
- All are in canonical units: dimensionless for τ, W/m²/µm for E_TOA and
  the two E_sky components, W/m²/sr/µm for the two L_path components.
  Conversion at boundaries only (Rule 2).
- ``__post_init__`` validates: shape consistency, τ ∈ [0, 1], energy
  terms non-negative.  Per Rule 17, a failure here raises with a
  pointing message — no silent clipping.
- Stage 3 populates ``E_sky_scattered`` and ``E_sky_thermal`` separately
  but both may be zero depending on backend capability.  Stage 6
  replaces the single-graybody ``E_sky`` with a proper split (see
  :ref:`Option_C_Implementation_Plan.md` Stage 6).  Callers should
  consume the sum ``E_sky_scattered + E_sky_thermal`` rather than either
  component alone.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from radiant.core.parameters import ParameterBoundsError

# Hard absolute tolerances used by __post_init__ — not physics parameters,
# just floating-point slop allowances for clamping and validation.
# τ ∈ [0, 1] with one ULP of slack either side.
_TAU_TOLERANCE: float = 1e-12
# Energy terms are clamped at zero; a slightly negative value from
# numerical cancellation is accepted (snapped to 0), but anything
# beyond this tolerance raises.
_ENERGY_NEGATIVE_TOLERANCE: float = 1e-12


@dataclass(frozen=True)
class AtmosphericQuantities:
    """Frozen bundle of atmospheric spectral quantities on a fixed λ grid.

    Produced by :meth:`radiant.atmosphere.protocol.Atmosphere.evaluate`
    and consumed by the assembly functions in
    :mod:`radiant.atmosphere.assembly`.

    Parameters
    ----------
    wavelength_um:
        1-D ascending wavelength grid [µm]. All eight spectral arrays
        must share this grid exactly (element-wise equality, not merely
        the same length).
    tau_sun:
        Transmittance along the sun → target column (down-leg),
        dimensionless ∈ [0, 1].
    tau_up:
        Transmittance along the target → sensor column (up-leg),
        dimensionless ∈ [0, 1].  The distinction between ``tau_sun`` and
        ``tau_up`` is the **two-leg split** that Option C introduces:
        legacy single-τ models collapse both legs into one factor and
        lose the solar-zenith dependence.
    tau_full_up:
        Transmittance along the ground → sensor full column (used for
        the background branch when the target is airborne / above the
        surface).  For a surface-level target (``h_tgt = 0``),
        ``tau_full_up == tau_up`` identically.
    E_TOA:
        Top-of-atmosphere solar spectral irradiance at 1 AU [W/m²/µm].
        Non-negative.  Supplied directly from
        :func:`radiant.core.solar.toa_solar_spectral_irradiance`.
    E_sky_scattered:
        Scattered-solar diffuse sky spectral irradiance at the target
        [W/m²/µm]. Non-negative. Stage 3 may leave this ≈ 0 (a Stage 6
        deliverable); Stage 6 populates it properly.
    E_sky_thermal:
        Atmospheric-thermal diffuse sky spectral irradiance at the
        target [W/m²/µm]. Non-negative. Derived from
        ``(1 − τ_down) · π · B(T_atm_eff)`` in the simple backend.
    L_path_up:
        Upwelling path radiance from the target to the sensor
        [W/m²/sr/µm]. Non-negative.
    L_path_full:
        Upwelling path radiance from the ground (h = 0) to the sensor
        [W/m²/sr/µm], used by the background branch. For a surface-level
        target, ``L_path_full == L_path_up`` identically.

    Notes
    -----
    Internal callers should not import private fields or add new fields
    without first updating ADR-0002 and the Stage 3/6 plan sections.
    """

    wavelength_um: np.ndarray
    tau_sun: np.ndarray
    tau_up: np.ndarray
    tau_full_up: np.ndarray
    E_TOA: np.ndarray
    E_sky_scattered: np.ndarray
    E_sky_thermal: np.ndarray
    L_path_up: np.ndarray
    L_path_full: np.ndarray

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def __post_init__(self) -> None:
        self._validate_grid()
        self._validate_tau("tau_sun", self.tau_sun)
        self._validate_tau("tau_up", self.tau_up)
        self._validate_tau("tau_full_up", self.tau_full_up)
        self._validate_nonneg("E_TOA", self.E_TOA)
        self._validate_nonneg("E_sky_scattered", self.E_sky_scattered)
        self._validate_nonneg("E_sky_thermal", self.E_sky_thermal)
        self._validate_nonneg("L_path_up", self.L_path_up)
        self._validate_nonneg("L_path_full", self.L_path_full)

    def _validate_grid(self) -> None:
        lam = np.asarray(self.wavelength_um)
        if lam.ndim != 1:
            raise ParameterBoundsError(
                what=f"AtmosphericQuantities.wavelength_um must be 1-D, got shape {lam.shape}",
                why="The quantity bundle is a spectral vector keyed by wavelength.",
                action="Pass a 1-D wavelength array from ChainState.wavelength_um.",
                context={"shape": lam.shape},
            )
        if lam.size < 2:
            raise ParameterBoundsError(
                what=(
                    f"AtmosphericQuantities.wavelength_um needs ≥2 samples, got {lam.size}"
                ),
                why="Spectral quantities require a non-trivial wavelength grid.",
                action="Provide at least two wavelength samples.",
                context={"n_samples": int(lam.size)},
            )
        if not np.all(np.diff(lam) > 0.0):
            raise ParameterBoundsError(
                what="AtmosphericQuantities.wavelength_um must be strictly ascending",
                why="Downstream interpolation and phase functions assume monotone λ.",
                action="Sort the wavelength grid ascending before constructing.",
                context={},
            )

        # Every array shares the grid exactly — this is the shape-validating
        # contract called out in Stage 3 of the Option C plan.
        shape = lam.shape
        for field_name in (
            "tau_sun",
            "tau_up",
            "tau_full_up",
            "E_TOA",
            "E_sky_scattered",
            "E_sky_thermal",
            "L_path_up",
            "L_path_full",
        ):
            arr = np.asarray(getattr(self, field_name))
            if arr.shape != shape:
                raise ParameterBoundsError(
                    what=(
                        f"AtmosphericQuantities.{field_name} shape {arr.shape} "
                        f"does not match wavelength_um shape {shape}"
                    ),
                    why=(
                        "All spectral fields on an AtmosphericQuantities share "
                        "the wavelength grid; per-field grids are not supported."
                    ),
                    action=(
                        "Resample or regenerate the field on the chain "
                        "wavelength_um grid before constructing the bundle."
                    ),
                    context={"field": field_name, "shape": arr.shape},
                )

    @staticmethod
    def _validate_tau(name: str, arr: np.ndarray) -> None:
        a = np.asarray(arr)
        lo = float(a.min()) if a.size else 0.0
        hi = float(a.max()) if a.size else 0.0
        if lo < -_TAU_TOLERANCE or hi > 1.0 + _TAU_TOLERANCE:
            raise ParameterBoundsError(
                what=(
                    f"AtmosphericQuantities.{name} out of [0, 1] "
                    f"(min={lo:g}, max={hi:g})"
                ),
                why=(
                    "Transmittance is a probability-of-transmission bounded "
                    "to [0, 1]. Values outside this range point to a bug in "
                    "the backend (e.g. Beer-Lambert OD < 0)."
                ),
                action=(
                    "Inspect the backend that produced this array; fix the "
                    "sign of the optical depth or the table load."
                ),
                context={"field": name, "min": lo, "max": hi},
            )

    @staticmethod
    def _validate_nonneg(name: str, arr: np.ndarray) -> None:
        a = np.asarray(arr)
        if a.size == 0:
            return
        lo = float(a.min())
        if lo < -_ENERGY_NEGATIVE_TOLERANCE:
            raise ParameterBoundsError(
                what=f"AtmosphericQuantities.{name} has negative values (min={lo:g})",
                why=(
                    "Spectral irradiance / radiance must be ≥ 0.  Negative "
                    "values from a backend are a physics bug, not a clamp "
                    "target — Rule 17 forbids silent clipping."
                ),
                action=(
                    "Fix the backend that produced this field; if the "
                    "negativity is tiny numerical noise, snap the array to 0 "
                    "before construction."
                ),
                context={"field": name, "min": lo},
            )


__all__ = ["AtmosphericQuantities"]
