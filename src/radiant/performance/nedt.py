"""Noise-equivalent metrics: NEDT, NEDL, NEDR.

Implements §4.2–§4.4 of ``docs/RADIANT_Metrics.md``.

NEDT — Noise-Equivalent Differential Temperature [K]:
    NEDT = T / SNR  (first-order approximation)
    or exactly: dL/dT inverse evaluated at the noise floor.

    For a thermal source obeying Planck's law observed in a narrow band,
    the first-order result is::

        NEDT ≈ σ_total / (dS/dT)

    where dS/dT is the derivative of the in-band signal with respect to
    target temperature. In the small-ΔT limit this reduces to::

        NEDT = T² / (S · (hc / (λ_eff · k_B · T) - 1)⁻¹)  [approximate]

    We implement the simpler finite-difference approach: the chain
    computes dS/dT externally (e.g., by running at T ± δT), and this
    function takes S, σ, and dS/dT directly.

NEDL — Noise-Equivalent Differential Radiance [W/m²/sr/µm]:
    NEDL = L / SNR

NEDR — Noise-Equivalent Reflectance Difference [dimensionless]:
    NEΔρ = ρ / SNR  (reflective regime)

All three are pure functions of SNR and the relevant signal quantity.
"""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class NEDTResult:
    """Result of an NEDT computation.

    Parameters
    ----------
    value_K:
        NEDT in Kelvin. ``float('nan')`` on failure.
    signal_e:
        Signal electrons per pixel.
    noise_e:
        Total noise [e- RMS].
    ds_dt_e_per_K:
        Signal derivative with respect to temperature [e-/K].
    failure_reason:
        ``None`` on success; human-readable string otherwise.
    """

    value_K: float
    signal_e: float
    noise_e: float
    ds_dt_e_per_K: float
    failure_reason: str | None = None

    @property
    def ok(self) -> bool:
        return self.failure_reason is None and math.isfinite(self.value_K)


def compute_nedt(
    noise_e: float,
    ds_dt_e_per_K: float,
) -> NEDTResult:
    """Compute NEDT from noise and signal temperature derivative.

    Parameters
    ----------
    noise_e:
        Total noise σ_total [e- RMS]. Must be > 0.
    ds_dt_e_per_K:
        Derivative of in-band signal w.r.t. target temperature [e-/K].
        Must be > 0 for a physically meaningful result.

    Returns
    -------
    NEDTResult
        NEDT = σ_total / (dS/dT).
    """
    if noise_e < 0.0:
        return NEDTResult(
            value_K=float("nan"),
            signal_e=0.0,
            noise_e=noise_e,
            ds_dt_e_per_K=ds_dt_e_per_K,
            failure_reason=f"Negative noise ({noise_e:.2f} e-).",
        )
    if ds_dt_e_per_K <= 0.0:
        return NEDTResult(
            value_K=float("nan"),
            signal_e=0.0,
            noise_e=noise_e,
            ds_dt_e_per_K=ds_dt_e_per_K,
            failure_reason=(
                f"dS/dT = {ds_dt_e_per_K:.4g} e-/K must be > 0. "
                "Check that the source temperature produces increasing "
                "signal in the observation band."
            ),
        )
    nedt = noise_e / ds_dt_e_per_K
    return NEDTResult(
        value_K=nedt,
        signal_e=0.0,
        noise_e=noise_e,
        ds_dt_e_per_K=ds_dt_e_per_K,
    )


def compute_nedt_from_snr(
    target_temp_K: float,
    snr: float,
    lambda_eff_um: float,
) -> NEDTResult:
    """Compute NEDT using the Planck-derivative approximation.

    For a narrow-band thermal sensor::

        NEDT ≈ T / (SNR · x · eˣ / (eˣ − 1))

    where x = hc / (λ_eff · k_B · T).

    This is the standard first-order NEDT approximation from
    Dereniak & Boreman, *Infrared Detectors and Systems* (1996).

    Parameters
    ----------
    target_temp_K:
        Target blackbody temperature [K].
    snr:
        Signal-to-noise ratio (must be > 0 and finite).
    lambda_eff_um:
        Effective (band-center) wavelength [µm].
    """
    from radiant.core.constants import c, h, k_B

    if target_temp_K <= 0.0:
        return NEDTResult(
            value_K=float("nan"),
            signal_e=0.0,
            noise_e=0.0,
            ds_dt_e_per_K=0.0,
            failure_reason=f"Target temperature {target_temp_K} K must be > 0.",
        )
    if not math.isfinite(snr) or snr <= 0.0:
        return NEDTResult(
            value_K=float("nan"),
            signal_e=0.0,
            noise_e=0.0,
            ds_dt_e_per_K=0.0,
            failure_reason=f"SNR = {snr} must be positive and finite.",
        )
    if lambda_eff_um <= 0.0:
        return NEDTResult(
            value_K=float("nan"),
            signal_e=0.0,
            noise_e=0.0,
            ds_dt_e_per_K=0.0,
            failure_reason=f"Effective wavelength {lambda_eff_um} µm must be > 0.",
        )

    lam_m = lambda_eff_um * 1.0e-6
    x = h * c / (lam_m * k_B * target_temp_K)

    # Planck derivative factor: x · eˣ / (eˣ − 1)
    # For large x (short λ, low T), exp(x) can overflow.
    try:
        ex = math.exp(x)
    except OverflowError:
        return NEDTResult(
            value_K=float("nan"),
            signal_e=0.0,
            noise_e=0.0,
            ds_dt_e_per_K=0.0,
            failure_reason=(
                f"Planck factor overflow: x = hc/(λkT) = {x:.1f}. "
                "The source temperature is too low for this wavelength."
            ),
        )

    planck_factor = x * ex / (ex - 1.0)
    nedt = target_temp_K / (snr * planck_factor)

    return NEDTResult(
        value_K=nedt,
        signal_e=0.0,
        noise_e=0.0,
        ds_dt_e_per_K=planck_factor * snr / target_temp_K,
    )


@dataclass(frozen=True)
class NEDLResult:
    """Result of an NEDL computation.

    Parameters
    ----------
    value:
        NEDL [W/m²/sr/µm]. ``float('nan')`` on failure.
    radiance:
        Signal radiance [W/m²/sr/µm].
    snr:
        Signal-to-noise ratio.
    failure_reason:
        ``None`` on success.
    """

    value: float
    radiance: float
    snr: float
    failure_reason: str | None = None

    @property
    def ok(self) -> bool:
        return self.failure_reason is None and math.isfinite(self.value)


def compute_nedl(radiance: float, snr: float) -> NEDLResult:
    """Compute NEDL = L / SNR.

    Parameters
    ----------
    radiance:
        In-band radiance [W/m²/sr/µm]. Must be > 0.
    snr:
        Signal-to-noise ratio. Must be > 0 and finite.
    """
    if radiance <= 0.0:
        return NEDLResult(
            value=float("nan"),
            radiance=radiance,
            snr=snr,
            failure_reason=f"Radiance = {radiance} must be > 0.",
        )
    if not math.isfinite(snr) or snr <= 0.0:
        return NEDLResult(
            value=float("nan"),
            radiance=radiance,
            snr=snr,
            failure_reason=f"SNR = {snr} must be positive and finite.",
        )
    return NEDLResult(value=radiance / snr, radiance=radiance, snr=snr)


@dataclass(frozen=True)
class NEDRResult:
    """Result of an NEDR (NEΔρ) computation.

    Parameters
    ----------
    value:
        Noise-equivalent reflectance difference [dimensionless].
    reflectance:
        Target reflectance (fractional).
    snr:
        Signal-to-noise ratio.
    failure_reason:
        ``None`` on success.
    """

    value: float
    reflectance: float
    snr: float
    failure_reason: str | None = None

    @property
    def ok(self) -> bool:
        return self.failure_reason is None and math.isfinite(self.value)


def compute_nedr(reflectance: float, snr: float) -> NEDRResult:
    """Compute NEΔρ = ρ / SNR.

    Parameters
    ----------
    reflectance:
        Target reflectance (0, 1]. Must be > 0.
    snr:
        Signal-to-noise ratio. Must be > 0 and finite.
    """
    if reflectance <= 0.0:
        return NEDRResult(
            value=float("nan"),
            reflectance=reflectance,
            snr=snr,
            failure_reason=f"Reflectance = {reflectance} must be > 0.",
        )
    if not math.isfinite(snr) or snr <= 0.0:
        return NEDRResult(
            value=float("nan"),
            reflectance=reflectance,
            snr=snr,
            failure_reason=f"SNR = {snr} must be positive and finite.",
        )
    return NEDRResult(value=reflectance / snr, reflectance=reflectance, snr=snr)
