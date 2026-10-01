"""1/f noise through the measurement's own transfer function (CU-381).

RADIANT previously evaluated flicker noise as a closed form over a bandwidth
taken from two free parameters::

    sigma = sqrt(K * ln(f_high / f_low))          # superseded

which has three independent defects, documented in CU-381 and found from two
directions (scenario 2.2's ``gaps.md`` Gaps 1-2; external review 2026-09-30 F2):

(a) the band was not capped at the corner frequency, above which the PSD is
    white and already counted as read noise -- a 64-170 % overestimate measured
    at 30-120 Hz;
(b) the band was decoupled from every timing quantity in the model, so a 100 us
    frame and a 100 ms frame got the identical sigma; and
(c) co-adding scaled it by sqrt(K), averaging down power that is common to
    every frame in the stack and cannot average.

(a) and (c) pull in opposite directions and partially cancel, which is why the
term looked plausible through two releases.

This module replaces the closed form with the integral the measurement actually
performs::

    sigma^2 = INT S(f) |H_box(f)|^2 |D_K(f)|^2 |H_ref(f)|^2 df

Every one of the three defects becomes a limit of this integral rather than a
patch:

===========================  ==================================================
Limit                        Result
===========================  ==================================================
``f -> 0``                   ``|H|^2 -> (K)^2``: correlated, x K in amplitude.
                             Defect (c), with no exponent chosen by hand.
White ``S(f)``               ``INT -> K x`` per-frame: x sqrt(K). The sqrt(K)
                             is recovered exactly where it is correct.
``K = 1``                    collapses to one boxcar.
Corner frequency             enters as the SHAPE of ``S(f)``, not as a cap.
                             Defect (a).
``t_int``                    enters through the boxcar sinc. Defect (b).
===========================  ==================================================

The terms
---------
``S(f) = K_f / f`` for ``f < f_corner``, and 0 above it. The cutoff is not an
approximation of the PSD -- the physical PSD really is ``K_f/f + white`` -- it
is the avoidance of a **double count**: above the corner the 1/f contribution
lies under the white floor, and RADIANT already charges that floor as read
noise. Integrating past the corner would bill it twice.

``H_box(f) = sinc(pi f t_int)``, the per-frame charge integration, normalised to
1 at DC. Note what this makes of the old ``flicker_f_high_hz``: the boxcar's own
roll-off at ``f ~ 1/t_int`` **is** the high-frequency limit, so no separate
upper bandwidth parameter is physically required. The old 1 MHz default was a
fiction the sinc would have handled, and at ``t_int = 5 ms`` it was integrating
3.5 decades of band the detector cannot respond to.

``D_K(f)``, the Dirichlet kernel of the K-frame comb at spacing
``frame_period_s``, normalised to ``D_K(0) = K`` to match ``coadd_mode: sum``::

    |D_K(f)| = |sin(pi f K t_frame) / sin(pi f t_frame)|

This is the whole of the co-add correlation physics. Below ``1/T_total`` the
frames see one common fluctuation and it adds coherently (``K^2`` in variance);
far above, successive frames are uncorrelated and it adds incoherently (``K``).
The crossover is not asserted, it is where the kernel puts it.

``H_ref(f) = 1 - exp(-2 pi i f t_sep)``, so ``|H_ref|^2 = 4 sin^2(pi f t_sep)``,
for a measurement differenced against a reference ``t_sep`` later (CDS, or
``counting_mode: up_down``). This is the high-pass that a chopped or modulated
sensor buys: it suppresses exactly the low-frequency power an un-referenced
staring stack accumulates. With no reference it is unity -- and then the DC
divergence below is real.

Why ``f_low`` survives
----------------------
As ``f -> 0`` the kernel gives ``|D_K|^2 -> K^2`` while ``S ~ 1/f``, so the
integral **diverges logarithmically at DC** for an un-referenced sum. That is
not a modelling artefact: for a bare sum with no reference, arbitrarily slow
drift couples in with full weight, and a single integration cannot distinguish
1/f drift from signal at all. What makes 1/f *noise* rather than *offset* is the
comparison -- across the frames of a stack, or against a reference.

So ``f_low`` is the reciprocal of the longest timescale over which the
measurement is compared. It defaults to ``1 / T_total`` with
``T_total = K * frame_period_s``, and remains settable for an analyst who knows
their calibration interval. The model states this rather than hiding it behind
the old 0.01 Hz default, which corresponded to no timing anywhere in RADIANT.
"""

from __future__ import annotations

import math

import numpy as np

from radiant.readout.errors import ReadoutValidationError

__all__ = [
    "DIRICHLET_EXACT_SPAN",
    "flicker_noise_e",
]

#: How far above ``1/T_total`` the Dirichlet kernel is evaluated exactly before
#: its period-average is substituted. ``|D_K|^2`` oscillates with period
#: ``1/(K t_frame)``; at K = 500 over a 200 Hz band that is ~1e5 oscillations,
#: which no affordable quadrature grid resolves. Its average over one period is
#: exactly K, so above the crossover the average is used. The coherent-to-
#: incoherent transition lives below the crossover and is resolved exactly, which
#: is the part that carries the physics.
DIRICHLET_EXACT_SPAN: float = 20.0

#: Quadrature points per decade of frequency (log-spaced trapezoid).
_POINTS_PER_DECADE: int = 400


def _dirichlet_power(f_hz: np.ndarray, n_coadds: int, frame_period_s: float) -> np.ndarray:
    """``|D_K(f)|^2`` for the K-frame comb, exact at low f and averaged above.

    Returns ``K**2`` at DC and oscillates about ``K`` once
    ``f >> 1 / (K * frame_period_s)``.
    """
    if n_coadds == 1:
        return np.ones_like(f_hz)

    total_s = n_coadds * frame_period_s
    crossover_hz = DIRICHLET_EXACT_SPAN / total_s

    power = np.full_like(f_hz, float(n_coadds))
    low = f_hz <= crossover_hz
    if not np.any(low):
        return power

    f_low_band = f_hz[low]
    numerator = np.sin(math.pi * f_low_band * n_coadds * frame_period_s)
    denominator = np.sin(math.pi * f_low_band * frame_period_s)
    # The kernel's removable singularities sit at f = m / frame_period_s, where
    # every frame is in phase and the sum is fully coherent.
    tiny = np.abs(denominator) < 1e-12
    exact = np.empty_like(f_low_band)
    exact[tiny] = float(n_coadds) ** 2
    exact[~tiny] = (numerator[~tiny] / denominator[~tiny]) ** 2
    power[low] = exact
    return power


def flicker_noise_e(
    *,
    flicker_K_e2: float,
    t_int_s: float,
    frame_period_s: float,
    n_coadds: int,
    corner_hz: float,
    f_low_hz: float,
    reference_separation_s: float = 0.0,
) -> float:
    """1/f noise of a K-frame summed measurement [e- RMS].

    The value is for ``coadd_mode: sum``. ``AVERAGE`` is this divided by
    ``n_coadds`` exactly -- which reproduces ``/sqrt(K)`` for white noise and
    *no reduction at all* for perfectly correlated noise, both correct.

    Parameters
    ----------
    flicker_K_e2:
        ``detector.flicker_K`` [e-^2] -- the 1/f PSD coefficient, ``S = K_f/f``.
        Zero disables the term.
    t_int_s:
        Per-frame integration time [s]. Sets the boxcar roll-off.
    frame_period_s:
        Frame-to-frame spacing [s]. Must be >= ``t_int_s``.
    n_coadds:
        Number of co-added frames, K >= 1.
    corner_hz:
        Frequency where the 1/f PSD meets the white floor [Hz]. Above it the
        power is charged as read noise, so it is excluded here.
    f_low_hz:
        Low-frequency limit [Hz] -- the reciprocal of the longest timescale the
        measurement is compared over. See the module docstring on why this
        cannot be derived away for an un-referenced stack.
    reference_separation_s:
        Separation between a measurement and its reference [s] (CDS, up/down).
        0 means un-referenced, giving ``|H_ref|^2 = 1``.

    Returns
    -------
    float
        Flicker noise in electrons RMS at the summed measurement.
    """
    if flicker_K_e2 <= 0.0:
        return 0.0
    if n_coadds < 1:
        raise ReadoutValidationError(f"flicker_noise_e: n_coadds = {n_coadds} must be >= 1.")
    if t_int_s <= 0.0:
        raise ReadoutValidationError(f"flicker_noise_e: t_int_s = {t_int_s} must be > 0.")
    if frame_period_s < t_int_s:
        raise ReadoutValidationError(
            f"flicker_noise_e: frame_period_s = {frame_period_s} s is shorter than "
            f"t_int_s = {t_int_s} s — a frame cannot integrate for longer than the "
            f"period it repeats on. Set readout.frame_period_s >= the integration time."
        )
    if f_low_hz <= 0.0:
        raise ReadoutValidationError(
            f"flicker_noise_e: f_low_hz = {f_low_hz} must be > 0. The 1/f integral "
            f"diverges at DC for an un-referenced measurement; f_low is the "
            f"reciprocal of the longest timescale the measurement is compared over."
        )
    if corner_hz <= f_low_hz:
        # The whole 1/f band lies under the white floor, which read noise owns.
        return 0.0

    # Bound the upper limit: past a few decades beyond the boxcar roll-off the
    # sinc^2 contributes nothing, so integrating further only costs grid.
    f_high_hz = min(corner_hz, 100.0 / t_int_s)
    if f_high_hz <= f_low_hz:
        f_high_hz = corner_hz

    decades = math.log10(f_high_hz / f_low_hz)
    n_points = max(int(_POINTS_PER_DECADE * decades), 2000)
    f_hz = np.logspace(math.log10(f_low_hz), math.log10(f_high_hz), n_points)

    psd = flicker_K_e2 / f_hz
    box = np.sinc(f_hz * t_int_s) ** 2  # np.sinc(x) = sin(pi x)/(pi x)
    comb = _dirichlet_power(f_hz, n_coadds, frame_period_s)
    if reference_separation_s > 0.0:
        ref = 4.0 * np.sin(math.pi * f_hz * reference_separation_s) ** 2
    else:
        ref = np.ones_like(f_hz)

    variance_e2 = float(np.trapezoid(psd * box * comb * ref, f_hz))
    if variance_e2 < 0.0 or not math.isfinite(variance_e2):
        raise ReadoutValidationError(
            f"flicker_noise_e: integration produced a non-physical variance "
            f"({variance_e2} e-^2) for flicker_K = {flicker_K_e2} e-^2, "
            f"t_int = {t_int_s} s, frame_period = {frame_period_s} s, K = {n_coadds}, "
            f"corner = {corner_hz} Hz, f_low = {f_low_hz} Hz."
        )
    return math.sqrt(variance_e2)
