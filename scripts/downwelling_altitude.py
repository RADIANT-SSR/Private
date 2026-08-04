"""Altitude-dependent downwelling sky radiance for the shipped library (CU-181).

One computation, one module (Rule 19).  The shipped MODTRAN families attach a
downwelling sky radiance ``atm_emission_down`` [W/m²/sr/µm] to every node; the
physically meaningful key is the **target** altitude, because ``E_sky_thermal =
π · L`` is the sky irradiance falling on the target.  Before the batch-2 P-block
the library had exactly one measured rung (the ground-level H5 run) and attached
it to every node regardless of target altitude — [[CU-181]].

This module turns the measured rung ladder into a value at an arbitrary target
altitude.  It is pure array arithmetic with no MODTRAN or RADIANT dependency, so
it is testable at Level 0 against hand-computed values.

Model
-----
Per wavelength, ``ln L`` is piecewise linear in altitude:

* **inside the measured span** (ground rung → top rung) — linear interpolation
  of ``ln L`` between the two bracketing rungs.  Log space because the residual
  emitting column above an observer falls quasi-exponentially with altitude;
  the interpolation makes no monotonicity assumption, which matters because the
  real MWIR profile is **not** monotonic (the stratospheric CO₂/O₃ layers make
  the 29 km rung brighter than the 20 km one).
* **above the top measured rung** — linear extrapolation of ``ln L`` using the
  slope of the top **two** rungs, clamped to be non-increasing per wavelength.
  It is the weakest link in the model: see the caveat below.  The clamp exists
  because a *rising* measured slope is real inside the span (stratospheric
  CO₂/O₃) but cannot continue above the top rung — there is strictly less air
  above it than below it.
* **at or above the atmosphere top** — exactly ``0``.  An observer at the top of
  the modelled atmosphere has no sky above it, so the downwelling vanishes
  identically.  This is a physical identity of the same class as the library's
  synthesized vacuum rung (``τ ≡ 1``, ``L_path ≡ 0``), not an extrapolation.

Caveat on the extrapolated band
-------------------------------
Only the band **above the top measured rung** is modelled.  With the P7/P8
follow-on (2026-08-03) the measured ladder reaches 80 km, so that band is
80 → 100 km, and no node any shipped family holds falls inside it: the boost
families' rungs are 60 km and 80 km (both measured now) and 100 km (the exact
zero identity), so the extrapolation is reached only by an off-node query
between 80 and 100 km.  Such a query is bracketed by two things that are not
modelled — a measured value at 80 km and exactly zero at the atmosphere top —
so its error is bounded by the measured 80 km value itself.

Historical note, because it sizes what the follow-on bought: before P7/P8 the
top measured rung was 50 km and the 60/80 km library nodes were extrapolated on
the 29 → 50 km slope.  That slope is shallow in the MWIR — the measured 3–5 µm
downwelling falls only ~1.4× across 29 → 50 km, held up by stratospheric CO₂/O₃
emission — and continuing it upward under-predicted the collapse that actually
happens above 50 km.  Measured against P7/P8, the extrapolation over-stated the
3–5 µm value by **10.6×** at 60 km and **8 791×** at 80 km (8–12 µm: 4.9× and
349×): conservative in direction, as this docstring claimed, but the MWIR band
whose slope made the model look benign is the one it got most wrong.  The
non-increasing clamp, by contrast, was confirmed — the measured profile really
does fall monotonically through 50 → 60 → 80 km.  Full table in
``docs/validation/atmosphere_modtran_parity.md`` §2.5.

Units: altitudes in **km** (the run matrix's unit, and the unit the caller's
node names carry); radiance in **W/m²/sr/µm**.
"""

from __future__ import annotations

import numpy as np

__all__ = ["ATMOSPHERE_TOP_KM", "RADIANCE_FLOOR", "downwelling_at_altitude"]

#: Radiance floor used before taking the log, so an identically-zero spectral
#: bin cannot produce ``-inf``.  Six orders below the smallest physically
#: meaningful downwelling in this library.
RADIANCE_FLOOR: float = 1.0e-30

#: Top of MODTRAN's modelled atmosphere [km].  At and above it the downwelling
#: is exactly zero — the vacuum identity.
ATMOSPHERE_TOP_KM: float = 100.0


def downwelling_at_altitude(
    rung_altitude_km: np.ndarray,
    rung_radiance: np.ndarray,
    query_altitude_km: float,
    *,
    atmosphere_top_km: float = ATMOSPHERE_TOP_KM,
) -> np.ndarray:
    """Downwelling sky radiance at ``query_altitude_km``, per wavelength.

    Parameters
    ----------
    rung_altitude_km:
        Measured rung altitudes [km], strictly ascending, at least two, the
        first at or below every query altitude (the ground rung).
    rung_radiance:
        Shape ``(n_rungs, n_wavelengths)`` downwelling radiance
        [W/m²/sr/µm] at those rungs.  Negative values are refused — the
        caller clips MODTRAN output before it gets here.
    query_altitude_km:
        Target altitude to evaluate at [km].
    atmosphere_top_km:
        Altitude at and above which the downwelling is identically zero [km].

    Returns
    -------
    numpy.ndarray
        Shape ``(n_wavelengths,)`` radiance [W/m²/sr/µm], never negative and
        never ``NaN``/``inf``.

    Raises
    ------
    ValueError
        If the rung ladder is malformed or the query is below the bottom rung
        (this module never extrapolates *downward* — there is no defensible
        below-ground sky).
    """
    alt = np.asarray(rung_altitude_km, dtype=np.float64)
    values = np.asarray(rung_radiance, dtype=np.float64)

    if alt.ndim != 1 or alt.size < 2:
        raise ValueError(
            f"downwelling_at_altitude: need at least 2 rung altitudes, got shape {alt.shape}. "
            "The ladder is built from the H5 ground run plus the P-block elevated runs."
        )
    if values.ndim != 2 or values.shape[0] != alt.size:
        raise ValueError(
            f"downwelling_at_altitude: rung_radiance shape {values.shape} does not match "
            f"{alt.size} rung altitudes — expected (n_rungs, n_wavelengths)."
        )
    if not np.all(np.diff(alt) > 0.0):
        raise ValueError(
            f"downwelling_at_altitude: rung altitudes must strictly ascend, got {alt.tolist()} km."
        )
    if np.any(values < 0.0):
        raise ValueError(
            "downwelling_at_altitude: negative downwelling radiance in the rung ladder. "
            "Clip MODTRAN path radiance at zero before building the ladder."
        )
    if query_altitude_km < alt[0]:
        raise ValueError(
            f"downwelling_at_altitude: query altitude {query_altitude_km} km is below the "
            f"bottom rung {alt[0]} km. There is no defensible sub-surface sky; add a lower "
            "rung or key the node to the bottom rung explicitly."
        )

    if query_altitude_km >= atmosphere_top_km:
        # Vacuum identity: no sky above the top of the modelled atmosphere.
        return np.zeros(values.shape[1], dtype=np.float64)

    log_values = np.log(np.maximum(values, RADIANCE_FLOOR))

    if query_altitude_km <= alt[-1]:
        # np.interp is per-wavelength linear-in-altitude on the log values.
        log_query = np.array(
            [np.interp(query_altitude_km, alt, log_values[:, j]) for j in range(values.shape[1])],
            dtype=np.float64,
        )
    else:
        # Log-linear extrapolation on the slope of the top two rungs, clamped
        # to be non-positive per wavelength. A positive measured slope between
        # the top two rungs is real (the stratospheric CO2/O3 layers), but
        # continuing it upward would grow the downwelling without bound above
        # the measured span, which no residual column can do — there is strictly
        # less air above 50 km than above 29 km. The clamp holds such a bin flat
        # instead, which is the conservative (over-stating) direction.
        span_km = alt[-1] - alt[-2]
        slope = np.minimum((log_values[-1, :] - log_values[-2, :]) / span_km, 0.0)
        log_query = log_values[-1, :] + slope * (query_altitude_km - alt[-1])

    out = np.exp(log_query)
    # An at-floor bin means "no measured emission here": report exact zero
    # rather than the floor, so downstream sums are unpolluted. The 2× margin
    # absorbs the round-trip round-off of exp(log(RADIANCE_FLOOR)), which lands
    # a few ulps above the floor itself.
    return np.where(out <= 2.0 * RADIANCE_FLOOR, 0.0, out)
