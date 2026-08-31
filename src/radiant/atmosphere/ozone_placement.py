"""Where the 9.6 µm ozone opacity is, and how much of the gas floor it is (CU-324).

One computation, one module (Rule 19): the two numbers an emission-placement
model needs about ozone — **what fraction** of the calibrated well-mixed-gas
floor is O₃ rather than continuum, and **what altitude profile** that fraction
rides.  Neither is fitted.

The share is arithmetic on the τ table
--------------------------------------
The CU-161 region table calibrates one water-independent ``floor_od`` per
spectral region.  Before CU-330 its 8.00–10.00 µm row was a single flat slab
spanning both the clean window and the O₃ ν₂ fundamental, so the table could not
say how much of that floor was ozone; the share was a free parameter and the
split was declined on exactly that ground.  CU-330 partitioned the row at the
measured band edges, and the share became readable:

* 8.00–9.40 µm — clean window, ``floor_od = 0.1494``.  Same CO₂/N₂O/CH₄
  continuum, no ozone in it.
* 9.40–9.90 µm — O₃ ν₂ core, ``floor_od = 0.8877``.  The same continuum *plus*
  the band.

An ozone band sits **on top of** the continuum its neighbours carry, so the
ozone is the excess, not the total:

    share_O3 = (0.8877 − 0.1494) / 0.8877 = 0.832

This module never writes that number down.  It computes the excess from the
shipped table by re-evaluating the table's own blended floor twice — once as
shipped, once with the core region's floor replaced by its clean-window
neighbour's (:func:`ozone_continuum_regions`) — and taking the ratio
(:func:`ozone_share_of_gas_floor`).  Two consequences follow for free:

* **the CU-267 blend ramps are handled by construction.**  Both floors pass
  through the same C¹ smoothstep, so the share inherits its continuity at
  9.40 and 9.90 µm rather than needing a second, parallel ramp implementation
  that could drift from the first (Rule 27).  In the 9.40 µm ramp the continuum
  is flat — the window and the substituted core carry the same floor — while the
  shipped floor rises, so the share rises smoothly from 0 to 0.832 across
  exactly the interval the measured band edge occupies.
* **it tracks the table.**  Re-fit the two rows and the share follows; there is
  no decimal here to go stale.

The 9.90–10.00 µm long-wave tail (``floor_od = 0.3013``, 3.3× the continuum)
keeps the well-mixed placement.  Its excess is ozone too, but the CU-324 item-2
ruling scoped the split to the band core the parity is measured in; placing the
tail is a separate results-affecting movement.

The altitude profile is physical, not fitted
--------------------------------------------
Ozone is not well mixed: photochemical production peaks in the mid
stratosphere, and the US Standard Atmosphere ozone number density peaks near
25 km with a half-width of order 5 km.  The placement profile is therefore a
Gaussian layer,

    ρ_O3(z) ∝ exp( −½ ((z − z₀) / w)² ),   z₀ = 25 km,  w = 5 km,

against the 4 km pressure-broadened scale height the rest of the gas floor
rides.  That is the whole physical content of the item: emission in the 9.6 µm
band leaves from the stratosphere, not from the first few kilometres of air.

The geometry is **weakly observable** and deliberately not tuned to the parity.
The fixed-lapse ICAO profile RADIANT integrates over is isothermal above the
11 km tropopause, so every candidate layer above it sits in air at 222.65 K and
only the *quantity* of opacity moved above the tropopause is measurable.
Measured at the τ-derived share over centres 20/25/30 km × widths 3/5/8 km, the
9.4–9.9 µm parity spans 0.1329–0.1925 with no interior optimum worth reading —
the numbers are in ``docs/validation/atmosphere_modtran_parity.md`` §2.14(b).
Taking the geometry from the standard ozone profile rather than from that grid
is what keeps this module's construction zero-fit: one number (the share) comes
from the τ table, the other two from a published profile.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Sequence
from typing import Protocol, TypeVar

import numpy as np

from radiant.core.parameters import ParameterBoundsError

__all__ = [
    "OZONE_BAND_UM",
    "OZONE_LAYER_CENTRE_M",
    "OZONE_LAYER_WIDTH_M",
    "ozone_continuum_regions",
    "ozone_share_of_gas_floor",
]

#: The CU-330 partition's O₃ ν₂ core region [µm] — the region whose floor stands
#: above its clean-window neighbour's by the ozone band.  Matched against the
#: table by its edges rather than by index so a re-partition cannot silently
#: point this module at the wrong row.
OZONE_BAND_UM: tuple[float, float] = (9.40, 9.90)

#: Centre of the ozone layer the in-band excess opacity is placed on [m].
#: US Standard Atmosphere ozone number density peaks at 22–25 km; 25 km is the
#: value the CU-324 measurement used and the owner's 2026-08-30 go named.
OZONE_LAYER_CENTRE_M: float = 25_000.0

#: Gaussian standard deviation of that layer [m].  5 km reproduces the standard
#: profile's 1/e half-width of ~7 km.  Not fitted — see the module docstring on
#: why the parity cannot constrain it.
OZONE_LAYER_WIDTH_M: float = 5_000.0


class GasRegionLike(Protocol):
    """Structural view of the calibrated gas-region rows this module reads.

    Declared structurally so the module never imports
    :mod:`radiant.atmosphere.simple` — the table's owner already imports this
    module, and a concrete import would close the cycle.
    """

    @property
    def lo_um(self) -> float: ...

    @property
    def hi_um(self) -> float: ...

    @property
    def floor_od(self) -> float: ...


_Region = TypeVar("_Region", bound=GasRegionLike)


def ozone_continuum_regions(regions: Sequence[_Region]) -> tuple[_Region, ...]:
    """The gas-region table with the ozone band's floor read as pure continuum.

    Returns a copy of ``regions`` in which the O₃ ν₂ core region
    (:data:`OZONE_BAND_UM`) carries the ``floor_od`` of the clean window
    immediately below it.  Evaluating the table's own blended floor against this
    copy gives the continuum a wavelength inside the band *would* have carried
    had there been no ozone in it; the difference against the shipped floor is
    the ozone.

    Only ``floor_od`` is substituted: the water coefficients are untouched
    because the water term is not what this module apportions.

    A table whose band row carries *exactly* its window's floor is not an
    error: there is then no excess, so no ozone to place, and the share this
    function feeds comes out zero — the correct answer, not a degraded one.
    That case is reached deliberately by
    ``scripts/fit_simple_atmosphere_gas_bands.py``, which zeroes every floor
    for its non-water reference evaluation; with no calibrated gas floor at
    all there is by construction no ozone opacity to apportion.

    Raises
    ------
    ParameterBoundsError
        If the table has no region at :data:`OZONE_BAND_UM`, if that region is
        the first in the table (no window below it to read the continuum
        from), or if the band's floor sits *below* that window's — a band that
        absorbs less than its own continuum is not a band, and the share would
        be negative rather than merely small.
    """
    lo_um, hi_um = OZONE_BAND_UM
    index = next(
        (i for i, region in enumerate(regions) if region.lo_um == lo_um and region.hi_um == hi_um),
        None,
    )
    if index is None:
        raise ParameterBoundsError(
            what=(f"ozone_continuum_regions: no calibrated gas region spans {lo_um}–{hi_um} µm"),
            why=(
                "The ozone share is read as the excess of the O₃ ν₂ core region's "
                "floor over its clean-window neighbour's, so both rows must exist."
            ),
            action=(
                "Restore the CU-330 partition at 9.40/9.90 µm, or update "
                "OZONE_BAND_UM to the region a re-partition actually created."
            ),
            context={"band_um": OZONE_BAND_UM, "n_regions": len(regions)},
        )
    if index == 0:
        raise ParameterBoundsError(
            what="ozone_continuum_regions: the ozone band is the table's first region",
            why="The continuum is read from the clean window immediately below the band.",
            action="Keep a calibrated region below 9.40 µm in the gas-region table.",
            context={"band_um": OZONE_BAND_UM},
        )
    window = regions[index - 1]
    band = regions[index]
    if band.floor_od < window.floor_od:
        raise ParameterBoundsError(
            what=(
                f"ozone_continuum_regions: the {lo_um}–{hi_um} µm floor "
                f"{band.floor_od} sits below the window floor {window.floor_od}"
            ),
            why=(
                "An absorption band stands above the continuum its neighbours carry; "
                "a band below its own window would give a negative ozone share."
            ),
            action=(
                "Re-run the gas-band fit, or retire the ozone placement split if the "
                "re-fit no longer resolves the band."
            ),
            context={"band_floor_od": band.floor_od, "window_floor_od": window.floor_od},
        )
    replaced = dataclasses.replace(band, floor_od=window.floor_od)
    return tuple(regions[:index]) + (replaced,) + tuple(regions[index + 1 :])


def ozone_share_of_gas_floor(
    floor_od: np.ndarray,
    continuum_floor_od: np.ndarray,
) -> np.ndarray:
    """Ozone fraction of the well-mixed-gas floor, per wavelength [-].

    ``share(λ) = 1 − floor_continuum(λ) / floor(λ)`` where ``floor`` is the
    blended table floor as shipped and ``floor_continuum`` is the same
    evaluation against :func:`ozone_continuum_regions`.  Outside the ozone band
    the two are the identical array and the share is exactly ``0.0``; inside it
    the share is the band's excess over the continuum; across the CU-267 blend
    ramps it inherits the smoothstep both floors already carry, so placement is
    continuous in λ.

    Wavelengths where the floor is zero (the VIS/UV regions, whose Rayleigh and
    aerosol terms already meet the measured floor) carry no gas opacity to
    apportion and return ``0.0``.

    Raises
    ------
    ParameterBoundsError
        On a shape mismatch, a non-finite or negative floor, or a continuum
        floor that exceeds the shipped floor (which would make the share
        negative — an ozone band that absorbs less than its own continuum).
    """
    floor = np.asarray(floor_od, dtype=np.float64)
    continuum = np.asarray(continuum_floor_od, dtype=np.float64)
    if floor.shape != continuum.shape:
        raise ParameterBoundsError(
            what=(
                f"ozone_share_of_gas_floor: floor shape {floor.shape} does not match "
                f"continuum shape {continuum.shape}"
            ),
            why="Both floors are the same table evaluated on the same wavelength grid.",
            action="Evaluate both on the chain wavelength grid before calling.",
            context={"floor_shape": floor.shape, "continuum_shape": continuum.shape},
        )
    if not np.all(np.isfinite(floor)) or not np.all(np.isfinite(continuum)):
        raise ParameterBoundsError(
            what="ozone_share_of_gas_floor: a gas floor is not finite",
            why="The share is a ratio of two optical depths; neither may be NaN or inf.",
            action="Fix the region-table evaluation that produced it.",
            context={"floor_finite": bool(np.all(np.isfinite(floor)))},
        )
    if float(np.min(floor)) < 0.0 or float(np.min(continuum)) < 0.0:
        raise ParameterBoundsError(
            what="ozone_share_of_gas_floor: a gas floor is negative",
            why="A negative optical depth is an amplifying medium, not an atmosphere.",
            action="Fix the region-table calibration that produced it.",
            context={"floor_min": float(np.min(floor)), "continuum_min": float(np.min(continuum))},
        )
    excess = floor - continuum
    if float(np.min(excess)) < 0.0:
        raise ParameterBoundsError(
            what=(
                "ozone_share_of_gas_floor: the continuum floor exceeds the shipped floor "
                f"by up to {-float(np.min(excess))}"
            ),
            why=(
                "The ozone band stands above the continuum, so the shipped floor is the "
                "larger of the two everywhere — including inside the blend ramps."
            ),
            action="Check that the continuum table came from ozone_continuum_regions.",
            context={"worst_deficit": -float(np.min(excess))},
        )
    positive = floor > 0.0
    share = np.zeros_like(floor)
    share[positive] = excess[positive] / floor[positive]
    return share
