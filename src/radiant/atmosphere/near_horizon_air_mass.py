"""Per-species effective air mass for a near-horizon slant path.

One computation, one module (Rule 19): given a straight ray of known perigee
radius and the two altitudes it runs between, produce the **per-species**
factors that turn a vertical optical depth into a slant one, and apply them.

Why per species, and why not ``sec ζ``
-------------------------------------
:meth:`radiant.atmosphere.protocol.AtmosphericGeometry.air_mass` is the honest
plane-parallel primitive: one scalar, ``sec ζ`` with a small spherical
correction, valid while the atmosphere can be treated as flat.  Near the
horizon it cannot.  Measured against the exact spherical slant integral
(:func:`radiant.atmosphere.grazing_column.grazing_slant_column_km`, molecular
scale height, ground → 100 km), ``sec ζ`` overstates the air mass by

=======  =========
ζ [deg]  ``sec ζ`` high by
=======  =========
30       0.042 %
60       0.373 %
75       1.687 %
80       3.752 %
85       13.15 %
89.4     236.5 %
=======  =========

and — the reason a single scalar cannot be patched — the error is *species
dependent*: at 89.4° the 2 km water-vapour profile is overstated by 104.4 %
against molecular's 236.5 %, a 2.3× divergence, because a shallow profile hugs
the tangent point far more tightly than a deep one.  Each species therefore
carries its own

.. math::  m_i \\;=\\; S_i(r_0;\\, h_{lo} \\to h_{hi};\\, H_i) \\;/\\; \\mathrm{col}_i

with ``S_i`` the exact spherical slant column and ``col_i`` the vertical one.
For a non-grazing geometry every ``m_i`` converges on the plane-parallel air
mass, so this reduces to the column model outside the near-horizon band.

Where the hand-over happens
---------------------------
:data:`~radiant.atmosphere.protocol.SPHERICAL_SWITCH_RAD` (80°) — the angle at
which the plane-parallel air mass stops being the accurate one, and the same
angle the up-looking sky already hands over at (CU-225 / CU-274).  Below it the
plane-parallel form is used unchanged, so nothing outside the band moves.  The
hand-over is a step, not a blend; at 80° it is the plane-parallel model's own
2.8 % optical-depth error, and the resulting transmittance/radiance step is
smaller still because the products saturate as ``1 − τ``.

Bundling note (Rule 19)
-----------------------
:func:`near_horizon_species_air_mass` and
:func:`apply_species_air_mass` are one model, not two: the second states the
convention the first is only meaningful under — that the well-mixed-gas floor
follows the *molecular* curvature (it shares the molecular scale height), and
that the CU-161 water curve of growth is evaluated on the **vertical** column
and then scaled, because that is the convention it was calibrated in.  Splitting
them would leave that convention undocumented at both halves.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from radiant.atmosphere.grazing_column import grazing_slant_column_km
from radiant.atmosphere.protocol import SPHERICAL_SWITCH_RAD
from radiant.core.constants import R_EARTH_M
from radiant.core.parameters import ParameterBoundsError

__all__ = [
    "SpeciesAirMass",
    "apply_species_air_mass",
    "is_near_horizon",
    "near_horizon_species_air_mass",
    "tangent_radius_m",
]


@dataclass(frozen=True)
class SpeciesAirMass:
    """Effective air masses of one slant path, one per species [dimensionless].

    Parameters
    ----------
    m_mol, m_aer, m_h2o:
        ``S_i / col_i`` for the molecular, aerosol and water-vapour profiles.
        The well-mixed-gas floor has no entry of its own: it follows the
        molecular scale height by construction (CU-161), so it uses ``m_mol``.
    r_tangent_m:
        Perigee radius of the ray the masses were computed for [m].
    slant_column_mol_km, slant_column_aer_km, slant_column_h2o_km:
        The exact spherical slant columns [km] the masses came from
        (provenance).
    """

    m_mol: float
    m_aer: float
    m_h2o: float
    r_tangent_m: float
    slant_column_mol_km: float
    slant_column_aer_km: float
    slant_column_h2o_km: float

    def as_provenance(self) -> dict[str, float]:
        """Flat provenance mapping, matching ``segment_grazing``'s key names."""
        return {
            "r_tangent_m": self.r_tangent_m,
            "tangent_altitude_m": self.r_tangent_m - R_EARTH_M,
            "slant_column_mol_km": self.slant_column_mol_km,
            "slant_column_aer_km": self.slant_column_aer_km,
            "slant_column_h2o_km": self.slant_column_h2o_km,
            "air_mass_mol": self.m_mol,
            "air_mass_aer": self.m_aer,
            "air_mass_h2o": self.m_h2o,
        }


def is_near_horizon(zenith_rad: float) -> bool:
    """``True`` when *zenith_rad* is past the plane-parallel band (80°).

    The single predicate for the hand-over, so the threshold cannot drift
    between the sky column, the observer column and the solar column.
    """
    return bool(zenith_rad > SPHERICAL_SWITCH_RAD)


def tangent_radius_m(h_low_m: float, zenith_rad: float) -> float:
    """Perigee radius of the ray leaving *h_low_m* at *zenith_rad* [m].

    ``r · sin ζ`` is invariant along a straight ray, so this is the closest
    approach of the **infinite line** to the Earth centre — exactly the ``r₀``
    :func:`radiant.atmosphere.grazing_column.grazing_slant_column_km` consumes.
    """
    return float((R_EARTH_M + h_low_m) * math.sin(zenith_rad))


def near_horizon_species_air_mass(
    r_tangent_m: float,
    h_low_m: float,
    h_high_m: float,
    *,
    col_mol_km: float,
    col_aer_km: float,
    col_h2o_km: float,
    scale_height_mol_m: float,
    scale_height_aer_m: float,
    scale_height_h2o_m: float,
) -> SpeciesAirMass:
    """Effective air masses of the arc ``h_low_m → h_high_m`` about *r_tangent_m*.

    Parameters
    ----------
    r_tangent_m:
        Perigee radius of the ray [m]; see :func:`tangent_radius_m`.
    h_low_m, h_high_m:
        Near and far ends of the traversed arc [m], ordered.
    col_mol_km, col_aer_km, col_h2o_km:
        The **vertical** column lengths over the same altitude interval [km],
        as produced by ``SimpleAtmosphere._column_length_km``.  Passed in
        rather than recomputed so there is exactly one implementation of that
        integral (Rule 27) and so this module stays free of any backend import.
    scale_height_mol_m, scale_height_aer_m, scale_height_h2o_m:
        The species scale heights [m].

    Returns
    -------
    SpeciesAirMass
        A zero-length vertical column (``col_i == 0``) yields ``m_i = 1``, the
        same degenerate convention ``segment_grazing`` uses: the species
        contributes no optical depth either way, so the factor is arbitrary and
        1 keeps it finite.

    Raises
    ------
    ParameterBoundsError
        Propagated from :func:`grazing_slant_column_km` for a non-physical
        geometry (perigee above the near end, inverted altitudes, negative
        altitude).  Rule 16 — validate before compute.
    """
    if not math.isfinite(r_tangent_m):
        raise ParameterBoundsError(
            what=f"near_horizon_species_air_mass: r_tangent_m = {r_tangent_m} m is not finite",
            why="A non-finite perigee radius propagates NaN into every optical depth.",
            action="Compute it with tangent_radius_m(h_low_m, zenith_rad).",
            context={"r_tangent_m": r_tangent_m},
        )
    s_mol = grazing_slant_column_km(r_tangent_m, h_low_m, h_high_m, scale_height_mol_m)
    s_aer = grazing_slant_column_km(r_tangent_m, h_low_m, h_high_m, scale_height_aer_m)
    s_h2o = grazing_slant_column_km(r_tangent_m, h_low_m, h_high_m, scale_height_h2o_m)
    return SpeciesAirMass(
        m_mol=s_mol / col_mol_km if col_mol_km > 0.0 else 1.0,
        m_aer=s_aer / col_aer_km if col_aer_km > 0.0 else 1.0,
        m_h2o=s_h2o / col_h2o_km if col_h2o_km > 0.0 else 1.0,
        r_tangent_m=float(r_tangent_m),
        slant_column_mol_km=s_mol,
        slant_column_aer_km=s_aer,
        slant_column_h2o_km=s_h2o,
    )


def apply_species_air_mass(
    masses: SpeciesAirMass,
    *,
    od_vert_mol: np.ndarray,
    od_vert_aer: np.ndarray,
    od_vert_h2o: np.ndarray,
    od_vert_gas: np.ndarray,
) -> np.ndarray:
    """Slant optical depth from the four vertical species terms [dimensionless].

    ::

        od = od_mol·m_mol + od_aer·m_aer + od_h2o·m_h2o + od_gas·m_mol

    The well-mixed-gas floor rides on ``m_mol`` because CU-161 defines it as a
    fraction of the molecular column and it shares the molecular scale height.
    The water term is the curve-of-growth optical depth of the **vertical**
    column, scaled — evaluating the curve at the slant amount would be a
    different model from the calibrated one and would make the 80° hand-over
    discontinuous.  The residual (a linear-in-air-mass curve of growth
    under-states band saturation on very long paths) is a known limitation
    shared with :mod:`radiant.atmosphere.level_arm`.
    """
    return np.asarray(
        od_vert_mol * masses.m_mol
        + od_vert_aer * masses.m_aer
        + od_vert_h2o * masses.m_h2o
        + od_vert_gas * masses.m_mol,
        dtype=np.float64,
    )
