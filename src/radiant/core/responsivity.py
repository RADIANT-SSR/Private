"""Spectral and band-integrated responsivity.

Implements the responsivity computation per
``docs/RADIANT_Signal_Chain_Architecture.md`` §5.

The spectral responsivity ``R(λ)`` converts spectral radiance at the
aperture [W/m²/sr/µm] to electron rate [e-/s/pixel/µm]:

    R(λ) = A_collect · Ω_pixel · τ_opt(λ) · QE(λ) · λ / hc

The band-integrated responsivity ``R_band`` converts band-averaged
radiance [W/m²/sr] to electron rate [e-/s/pixel]:

    R_band = ∫ R(λ) dλ   over the filter bandpass

These are used for backward propagation: to express electrons at the
aperture, divide by R_band.

    L_aperture [W/m²/sr/µm] = signal_e / (R_band · t_int)

QE is read from ``stage_outputs["spectral_integration"]["qe_curve"]``
if available (spectral array on the wavelength grid), otherwise from
``stage_outputs["spectral_integration"]["qe_scalar"]`` as a uniform
value. If neither is present, QE is omitted and the returned
responsivity is in photons, not electrons.
"""

from __future__ import annotations

import numpy as np
import numpy.typing as npt

from radiant.core.chain import ChainState
from radiant.core.constants import hc


def spectral_responsivity(
    state: ChainState,
) -> npt.NDArray[np.float64] | None:
    """Compute spectral responsivity R(λ) [e-/s/pixel per W/m²/sr/µm].

    Requires optics stage outputs (A_collect, Omega_pixel, tau_opt).
    Includes QE if available from spectral_integration stage_outputs.

    Returns
    -------
    ndarray or None
        R(λ) array on the state wavelength grid. None if required
        optics data is missing.
    """
    optics_out = state.stage_outputs.get("optics", {})
    A_collect = optics_out.get("A_collect")
    Omega_pixel = optics_out.get("Omega_pixel")
    tau_opt = optics_out.get("tau_opt")

    if A_collect is None or Omega_pixel is None or tau_opt is None:
        return None

    tau_arr = np.asarray(tau_opt, dtype=np.float64)
    wl = state.wavelength_um
    lam_m = wl * 1.0e-6  # µm → m

    # QE: read from spectral_integration stage_outputs where the
    # forward chain stored it. Prefer spectral curve, fall back to
    # scalar, then to 1.0 (photon responsivity only).
    si_out = state.stage_outputs.get("spectral_integration", {})
    qe_curve = si_out.get("qe_curve")
    if qe_curve is not None:
        qe_arr = np.asarray(qe_curve, dtype=np.float64)
    else:
        qe_scalar = si_out.get("qe_scalar")
        qe_arr = np.full_like(wl, float(qe_scalar)) if qe_scalar is not None else np.ones_like(wl)

    # R(λ) = A_collect · Ω_pixel · τ_opt(λ) · QE(λ) · (λ/hc)
    return A_collect * Omega_pixel * tau_arr * qe_arr * (lam_m / hc)


def band_integrated_responsivity(
    state: ChainState,
    filter_min_um: float | None = None,
    filter_max_um: float | None = None,
) -> float | None:
    """Compute band-integrated responsivity R_band.

    R_band = ∫ R(λ) dλ over the filter bandpass.

    Returns
    -------
    float or None
        Band-integrated responsivity [photon/s/pixel per W/m²/sr].
        None if spectral responsivity cannot be computed.
    """
    r_lambda = spectral_responsivity(state)
    if r_lambda is None:
        return None

    wl = state.wavelength_um

    if filter_min_um is not None and filter_max_um is not None:
        mask = (wl >= filter_min_um) & (wl <= filter_max_um)
        wl_band = wl[mask]
        r_band = r_lambda[mask]
    else:
        wl_band = wl
        r_band = r_lambda

    if wl_band.size < 2:
        return None

    return float(np.trapezoid(r_band, wl_band))


def electrons_to_radiance(
    signal_e: float,
    state: ChainState,
    t_int: float | None = None,
) -> float | None:
    """Convert electron count to equivalent at-aperture radiance.

    L [W/m²/sr] ≈ signal_e / (R_band · t_int)

    where R_band already includes QE (if available in stage_outputs).

    Parameters
    ----------
    signal_e:
        Signal in electrons.
    state:
        ChainState with optics and spectral_integration parameters.
    t_int:
        Integration time [s]. If None, inferred from stage_outputs.
    """
    r_band = band_integrated_responsivity(state)
    if r_band is None or r_band <= 0.0:
        return None

    if t_int is None:
        si_out = state.stage_outputs.get("spectral_integration", {})
        e_rate = si_out.get("e_rate_per_s")
        signal = si_out.get("signal_e")
        if e_rate is not None and e_rate > 0.0 and signal is not None and signal > 0.0:
            t_int = signal / e_rate
        else:
            return None

    if t_int <= 0.0:
        return None

    return signal_e / (r_band * t_int)
