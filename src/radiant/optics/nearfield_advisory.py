"""Advisory for a nearfield calculation that can only return zero (CU-380).

``optics.nearfield_enabled`` defaults to 1, but transmission modes 1-4
synthesize lumped elements at 0 K with zero emissivity (see
``transmission_modes._SYNTHESIZED_TEMPERATURE_K``), and
:func:`~radiant.optics.nearfield_irradiance.compute_nearfield_irradiance`
skips any element at 0 K. A config that selects ``transmission_scalar`` in a
thermal band therefore computes warm-optics irradiance as **identically zero**
while believing the term is switched on.

That ``eps = 0`` model is right: a synthesized lump is bookkeeping, not a
surface, and Kirchhoff gives it no emissivity. The defect was the silence. On
the shipped ``examples/mwir_leo_minimal.yaml`` (3.5-5.0 um,
``transmission_scalar: 0.70``) the omitted term is 37 % of signal and the
reported SNR is 17 % optimistic; in a background-dominated point-source case
the same mechanism measured 19x.

Scope of the advisory
---------------------
Fires only in a **thermal** band. Warm-optics self-emission is negligible below
~2.5 um, where a zero near-field term is the physically correct answer, and a
warning that fires on cases it does not apply to is a warning operators learn
to skip -- the same pathology as a ``validate`` that misses real errors.

The predicate is deliberately **mode-agnostic**: it asks whether any declared
element can emit, not which transmission mode is selected. That also catches a
Mode 4/5 element train whose rows were given no temperature, which is the same
defect arriving by a different route.

The band edge is read from the **chain wavelength grid**, not from
``spectral_integration.filter_max_um``. The grid is the band the chain actually
integrates (they coincide: 3.5-5.0 um filter gives a 3.5-5.0 um grid), it is
already in ``OpticsStage``'s hand, and taking it from there keeps this check
working for the stage-level unit tests that build a ParameterSet with no
spectral_integration section at all.
"""

from __future__ import annotations

from radiant.optics.element import OpticalElement

__all__ = ["THERMAL_BAND_FLOOR_UM", "nearfield_is_silently_zero", "nearfield_zero_message"]

#: Long-wave edge below which warm-optics emission is negligible [um]. A 300 K
#: surface radiates ~5 orders of magnitude less at 2.5 um than at 10 um, so a
#: zero near-field term is correct there and needs no advisory.
THERMAL_BAND_FLOOR_UM: float = 2.5


def nearfield_is_silently_zero(
    *,
    nearfield_enabled: bool,
    stray_includes_thermal: bool,
    elements: tuple[OpticalElement, ...],
    band_max_um: float,
) -> bool:
    """True when the near-field term is switched on, thermal, and structurally zero.

    Parameters
    ----------
    nearfield_enabled:
        ``optics.nearfield_enabled`` as a bool. False means the analyst turned
        the term off deliberately -- nothing to report.
    stray_includes_thermal:
        ``optics.stray.includes_thermal``. When set, warm-optics emission is
        accounted for in the stray-light term instead, so a zero near-field is
        correct by construction.
    elements:
        The element train the transmission mode produced.
    band_max_um:
        The long-wave edge of the chain wavelength grid [um].
    """
    if not nearfield_enabled or stray_includes_thermal:
        return False
    if band_max_um <= THERMAL_BAND_FLOOR_UM:
        return False
    return not any(element.temperature_K > 0.0 for element in elements)


def nearfield_zero_message(*, band_max_um: float, n_elements: int) -> str:
    """The advisory text. Names the cause, the consequence, and both remedies."""
    return (
        f"OpticsStage: optics.nearfield_enabled = 1 in a thermal band "
        f"(grid long-wave edge {band_max_um:g} um), but none of the "
        f"{n_elements} element(s) in the optical train can emit — every one is at 0 K, "
        f"which is how transmission modes 1–4 stamp a synthesized lump (a lump is "
        f"bookkeeping, not a surface, so Kirchhoff gives it no emissivity). "
        f"Warm-optics irradiance is therefore identically zero, and for a thermal "
        f"system it is usually the dominant background: omitting it makes SNR "
        f"optimistic — 17 % on RADIANT's own MWIR example, 19× in a "
        f"background-dominated point-source case. Either declare an "
        f"'optical_elements:' train carrying each surface's temperature_K (modes "
        f"'key_elements' or 'full_prescription'), or set optics.nearfield_enabled = 0 "
        f"to state that a zero warm-optics term is intended."
    )
