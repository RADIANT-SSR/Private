"""Radiometric-calibration analysis — sweep → fit report.

Turns a temperature/radiance calibration sweep (predicted vs measured DN)
into the standard calibration figures a test engineer reports: the
gain/offset decomposition, the temperature and radiance responsivities,
the linearity residuals, and the noise-driven calibration uncertainty in
temperature. These form one coupled report — the temperature uncertainty
uses the responsivity — so they live in one module (Rule 19 bundling
exception).

Gap 46 (Phase T3): scenario 7.2 computed all of these script-side from
``Sensor.sweep(keep_results=True)`` results.

All inputs are plain arrays (one entry per calibration point); this module
does no chain execution, so it composes with any sweep driver.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import numpy.typing as npt

from radiant.core.exceptions import RadiantError

__all__ = [
    "CalibrationAnalysisError",
    "CalibrationReport",
    "analyze_calibration",
    "gain_offset_fit",
    "linearity_residuals_pct_fs",
    "radiance_responsivity_dn_per_radiance",
    "temperature_calibration_uncertainty_k",
    "temperature_responsivity_dn_per_k",
]

FloatArray = npt.NDArray[np.float64]


class CalibrationAnalysisError(RadiantError):
    """Raised for malformed calibration-analysis inputs."""


def _as_1d(name: str, x: npt.ArrayLike) -> FloatArray:
    arr = np.asarray(x, dtype=np.float64)
    if arr.ndim != 1 or arr.size < 2:
        raise CalibrationAnalysisError(f"{name} must be a 1-D array with ≥ 2 points.")
    return arr


def gain_offset_fit(dn_predicted: npt.ArrayLike, dn_measured: npt.ArrayLike) -> tuple[float, float]:
    """Linear fit ``measured = a · predicted + b``.

    Returns ``(a, b)``: ``a`` is the gain-scale error (1.0 = perfect),
    ``b`` the un-modelled instrument offset in DN.
    """
    pred = _as_1d("dn_predicted", dn_predicted)
    meas = _as_1d("dn_measured", dn_measured)
    if pred.size != meas.size:
        raise CalibrationAnalysisError("dn_predicted and dn_measured must be the same length.")
    a, b = np.polyfit(pred, meas, 1)
    return float(a), float(b)


def temperature_responsivity_dn_per_k(
    dn: npt.ArrayLike, temperatures_k: npt.ArrayLike
) -> FloatArray:
    """Per-point responsivity ``dDN/dT`` [DN/K] via a central difference."""
    dn_a = _as_1d("dn", dn)
    t_a = _as_1d("temperatures_k", temperatures_k)
    if dn_a.size != t_a.size:
        raise CalibrationAnalysisError("dn and temperatures_k must be the same length.")
    return np.gradient(dn_a, t_a)


def radiance_responsivity_dn_per_radiance(dn: npt.ArrayLike, band_radiance: npt.ArrayLike) -> float:
    """Radiance responsivity ``dDN/dL`` [DN/(W/m²/sr)] — slope of DN vs L."""
    dn_a = _as_1d("dn", dn)
    l_a = _as_1d("band_radiance", band_radiance)
    if dn_a.size != l_a.size:
        raise CalibrationAnalysisError("dn and band_radiance must be the same length.")
    slope = np.polyfit(l_a, dn_a, 1)[0]
    return float(slope)


def linearity_residuals_pct_fs(
    x: npt.ArrayLike, dn_measured: npt.ArrayLike, full_scale_dn: float
) -> tuple[FloatArray, float]:
    """Linearity residuals as a percent of full scale.

    Fits ``dn_measured = a·x + b`` (x is usually band radiance), then
    returns ``(residuals_pct_fs, max_abs_pct_fs)`` where each residual is
    ``(measured − fit) / full_scale_dn · 100``.
    """
    x_a = _as_1d("x", x)
    meas = _as_1d("dn_measured", dn_measured)
    if x_a.size != meas.size:
        raise CalibrationAnalysisError("x and dn_measured must be the same length.")
    if full_scale_dn <= 0.0:
        raise CalibrationAnalysisError(f"full_scale_dn must be positive, got {full_scale_dn}.")
    a, b = np.polyfit(x_a, meas, 1)
    fit = a * x_a + b
    residuals_pct = (meas - fit) / full_scale_dn * 100.0
    return residuals_pct, float(np.max(np.abs(residuals_pct)))


def temperature_calibration_uncertainty_k(
    sigma_dn: float, dn_per_k: float, n_frames: int = 1
) -> float:
    """Temperature uncertainty [K] from DN noise and responsivity.

    ``σ_T = σ_DN / |dDN/dT| / √N_frames``. Averaging N frames reduces the
    noise-driven temperature uncertainty by √N.
    """
    if sigma_dn < 0.0:
        raise CalibrationAnalysisError(f"sigma_dn must be ≥ 0, got {sigma_dn}.")
    if dn_per_k == 0.0:
        raise CalibrationAnalysisError("dn_per_k must be non-zero (undefined responsivity).")
    if n_frames < 1:
        raise CalibrationAnalysisError(f"n_frames must be ≥ 1, got {n_frames}.")
    return float(sigma_dn / abs(dn_per_k) / np.sqrt(n_frames))


@dataclass(frozen=True)
class CalibrationReport:
    """Full calibration analysis over one sweep.

    Attributes
    ----------
    gain_scale:
        Slope ``a`` of measured-vs-predicted DN (1.0 = perfect gain).
    offset_dn:
        Intercept ``b`` [DN] — un-modelled instrument offset.
    dn_per_k:
        Per-point temperature responsivity [DN/K].
    dn_per_radiance:
        Radiance responsivity [DN/(W/m²/sr)].
    linearity_residuals_pct_fs:
        Per-point linearity residuals [% full scale].
    max_linearity_pct_fs:
        Worst-case linearity residual [% full scale].
    sigma_t_single_frame_k, sigma_t_nframe_k:
        Per-point temperature uncertainty [K], single-frame and N-frame.
    """

    gain_scale: float
    offset_dn: float
    dn_per_k: FloatArray
    dn_per_radiance: float
    linearity_residuals_pct_fs: FloatArray
    max_linearity_pct_fs: float
    sigma_t_single_frame_k: FloatArray
    sigma_t_nframe_k: FloatArray


def analyze_calibration(
    temperatures_k: npt.ArrayLike,
    band_radiance: npt.ArrayLike,
    dn_predicted: npt.ArrayLike,
    dn_measured: npt.ArrayLike,
    sigma_dn: npt.ArrayLike,
    full_scale_dn: float,
    n_frames: int = 100,
) -> CalibrationReport:
    """Assemble a :class:`CalibrationReport` from calibration-sweep arrays."""
    a, b = gain_offset_fit(dn_predicted, dn_measured)
    dn_per_k = temperature_responsivity_dn_per_k(dn_predicted, temperatures_k)
    dn_per_l = radiance_responsivity_dn_per_radiance(dn_predicted, band_radiance)
    resid_pct, max_pct = linearity_residuals_pct_fs(band_radiance, dn_measured, full_scale_dn)

    sig = _as_1d("sigma_dn", sigma_dn)
    if sig.size != dn_per_k.size:
        raise CalibrationAnalysisError("sigma_dn must match the number of sweep points.")
    if n_frames < 1:
        raise CalibrationAnalysisError(f"n_frames must be ≥ 1, got {n_frames}.")
    safe_dn_per_k = np.where(dn_per_k == 0.0, np.nan, dn_per_k)
    sigma_t_single = sig / np.abs(safe_dn_per_k)
    sigma_t_n = sigma_t_single / np.sqrt(n_frames)

    return CalibrationReport(
        gain_scale=a,
        offset_dn=b,
        dn_per_k=dn_per_k,
        dn_per_radiance=dn_per_l,
        linearity_residuals_pct_fs=resid_pct,
        max_linearity_pct_fs=max_pct,
        sigma_t_single_frame_k=sigma_t_single,
        sigma_t_nframe_k=sigma_t_n,
    )
