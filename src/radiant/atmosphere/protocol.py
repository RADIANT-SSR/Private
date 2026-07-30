"""Atmosphere protocol, geometry, and state contract.

Defines the structural interface every atmosphere model in RADIANT must
satisfy and the immutable result it produces. Per
``docs/architecture/RADIANT_Atmosphere.md`` §2 the chain consumes a single
``AtmosphericState`` regardless of which model produced it (simple,
tabulated, MODTRAN, exo).

This 2B.2 cut implements the *minimum* contract: the three spectral
arrays (``transmittance``, ``path_radiance``, ``atm_emission_down``),
the geometry the state was evaluated for, and the derived ``air_mass``
and ``slant_path_length_m``. Fields that only matter for MODTRAN
(``derivation_chain``, ``cache_key``, ``native_output``) and
turbulence are deferred to later phases — see
``docs/archive/blocked_overnight_log.md``.

The protocol is structural (``typing.Protocol``), so concrete models
do not need to subclass it. Duck typing is sufficient.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

import numpy as np

from radiant.atmosphere._quantities import AtmosphericQuantities
from radiant.atmosphere.errors import AtmosphereValidationError
from radiant.core.los_geometry import LineOfSightGeometry
from radiant.core.parameters import ParameterSet
from radiant.core.spectral import SpectralData

# ---------------------------------------------------------------------------
# Constants used by geometry math
# ---------------------------------------------------------------------------

# Zenith angle (rad) beyond which the plane-parallel column model stops being
# the accurate description of the path and callers that have an alternative
# must hand over to the exact spherical slant integral
# (``atmosphere/segment_grazing.py`` over ``grazing_column.py``).  Measured
# against that integral, ``sec ζ`` is high by 0.04 % at 30°, 0.4 % at 60° and
# 3.8 % at 80°, and the error then runs away (13 % at 85°, 237 % at 89.4°).
#
# CU-274: this constant used to *also* switch ``slant_path_length_m`` onto a
# root-form "spherical correction" that was not an air mass at all (see that
# method), producing an 18 % discontinuity in transmittance at 80° for every
# geometry.  The root form is gone; the constant now marks a hand-over point
# for callers, not a formula switch inside this class.
SPHERICAL_SWITCH_RAD: float = math.radians(80.0)

# Hard ceiling on the zenith angle. The horizon (π/2) is excluded — the
# plane-parallel column model is not trustworthy in that regime, so the
# ceiling sits a hair below.
ZENITH_CEILING_RAD: float = math.radians(89.5)


#: Top of the modelled atmospheric column [m]. Above it there is no medium, so it
#: bounds the *absorbing* thickness of any segment (CU-255). Defined here, in the
#: lowest layer, and re-exported by ``segment_simple`` as ``DEFAULT_H_ATM_TOP_M``
#: so the column top has one value framework-wide.
H_ATM_TOP_M: float = 1.0e5


# ---------------------------------------------------------------------------
# AtmosphericGeometry
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AtmosphericGeometry:
    """Geometry inputs to the atmosphere module.

    Per ``docs/architecture/RADIANT_Conventions.md`` §5 all angles are stored
    internally in **radians**. The ``from_degrees`` factory accepts the
    user-facing degrees-typed inputs documented in
    ``RADIANT_Atmosphere.md`` §4.1.

    Parameters
    ----------
    sensor_altitude_m:
        Sensor altitude above mean sea level [m]. ``≥ 0``.
    target_altitude_m:
        Target altitude above mean sea level [m]. ``≥ 0``. May be
        greater than ``sensor_altitude_m`` for uplooking geometries.
    path_zenith_rad:
        Zenith angle of the line of sight at the lower endpoint [rad].
        Must satisfy ``0 ≤ θ ≤ ZENITH_CEILING_RAD``. ``slant_path_length_m``
        and ``air_mass`` are plane-parallel (``sec θ``) over the whole
        domain; past ``SPHERICAL_SWITCH_RAD`` callers that can should hand
        over to :mod:`radiant.atmosphere.segment_grazing` (CU-274).
    solar_zenith_rad:
        Solar zenith angle [rad], for the single-scatter ``L_path``
        and reflected-solar paths. ``0 ≤ θ_sun ≤ π`` (widened from the
        pre-Phase-2 ``< π/2`` by ADR-0011 decision 10; a sun below the local
        horizontal is legal, and whether a point is lit is a per-altitude
        shadow-height question — see
        :mod:`radiant.atmosphere.solar_shadow`). Defaults to
        zero (sun overhead) which is enough for transmittance-only use.
    solar_azimuth_rad:
        Solar azimuth *relative to the sensor look direction* [rad].
        That is, ``Δφ = φ_sun − φ_sensor``. Only this difference
        matters for the single-scatter phase angle; there is no need
        to track absolute compass azimuths. Defaults to ``0`` (sun
        behind / in front of the sensor — same meridional plane).
        Range is unrestricted; only ``cos(Δφ)`` is consumed.
    observer_type:
        One of ``"space"``, ``"airborne"``, ``"ground"``. Free-form
        string here; the parameter resolver enforces the enum.
    target_type:
        One of ``"space"``, ``"airborne"``, ``"ground"``.
    """

    sensor_altitude_m: float
    target_altitude_m: float
    path_zenith_rad: float
    solar_zenith_rad: float = 0.0
    solar_azimuth_rad: float = 0.0
    observer_type: str = "airborne"
    target_type: str = "ground"

    def __post_init__(self) -> None:
        if self.sensor_altitude_m < 0.0:
            raise AtmosphereValidationError(
                f"AtmosphericGeometry: sensor_altitude_m = {self.sensor_altitude_m} m "
                "is negative. Altitudes are measured above mean sea level; set "
                "sensor_altitude_m ≥ 0."
            )
        if self.target_altitude_m < 0.0:
            raise AtmosphereValidationError(
                f"AtmosphericGeometry: target_altitude_m = {self.target_altitude_m} m "
                "is negative. Set target_altitude_m ≥ 0."
            )
        if not (0.0 <= self.path_zenith_rad <= ZENITH_CEILING_RAD):
            raise AtmosphereValidationError(
                f"AtmosphericGeometry: path_zenith_rad = {self.path_zenith_rad:.4f} rad "
                f"({math.degrees(self.path_zenith_rad):.2f}°) is out of the supported "
                f"range [0, {math.degrees(ZENITH_CEILING_RAD):.1f}°]. The simple "
                "model is unreliable past the horizon; reduce path_zenith_rad or use "
                "a higher-fidelity atmosphere model."
            )
        if not (0.0 <= self.solar_zenith_rad <= math.pi):
            raise AtmosphereValidationError(
                f"AtmosphericGeometry: solar_zenith_rad = {self.solar_zenith_rad:.4f} rad "
                f"({math.degrees(self.solar_zenith_rad):.2f}°) is out of [0, 180°]. "
                "Solar zenith is a zenith angle: 0 is overhead, π/2 the local "
                "horizontal, π directly underfoot. The domain is the full closed "
                "interval since Geometry-Flexibility Phase 2 (ADR-0011 decision 10) so "
                "that twilight and sunlit-above-the-terminator geometry is "
                "expressible; whether a given altitude is actually lit is decided by "
                "radiant.atmosphere.solar_shadow, not by this bound."
            )

    # ------------------------------------------------------------------
    # Constructors
    # ------------------------------------------------------------------

    @classmethod
    def from_degrees(
        cls,
        sensor_altitude_m: float,
        target_altitude_m: float,
        path_zenith_deg: float,
        solar_zenith_deg: float = 0.0,
        solar_azimuth_deg: float = 0.0,
        observer_type: str = "airborne",
        target_type: str = "ground",
    ) -> AtmosphericGeometry:
        """User-facing constructor: angles in degrees.

        Per RADIANT_Conventions.md §5, the API exposes degrees with an
        explicit ``_deg`` suffix. The conversion to canonical radians
        happens here, **once**, at the boundary.
        """
        return cls(
            sensor_altitude_m=float(sensor_altitude_m),
            target_altitude_m=float(target_altitude_m),
            path_zenith_rad=math.radians(float(path_zenith_deg)),
            solar_zenith_rad=math.radians(float(solar_zenith_deg)),
            solar_azimuth_rad=math.radians(float(solar_azimuth_deg)),
            observer_type=observer_type,
            target_type=target_type,
        )

    # ------------------------------------------------------------------
    # Derived geometry
    # ------------------------------------------------------------------

    @property
    def altitude_difference_m(self) -> float:
        """Absolute height between sensor and target [m]."""
        return abs(self.sensor_altitude_m - self.target_altitude_m)

    def slant_path_length_m(self) -> float:
        """Plane-parallel slant-path length through the atmosphere [m].

        ``L = Δh / cos(ζ)`` over the whole legal zenith domain
        ``[0, ZENITH_CEILING_RAD]``, with ``Δh`` the *absorbing* thickness of
        the segment (:meth:`_absorbing_thickness_m`, CU-255).

        Per ``docs/architecture/RADIANT_Atmosphere.md`` §4.2.

        One formula, no branch (CU-274)
        -------------------------------
        Until 2026-07-29 a second, "spherical-Earth corrected" branch took over
        past :data:`SPHERICAL_SWITCH_RAD`::

            L = R_E · [√(cos²ζ + 2(Δh/R_E) + (Δh/R_E)²) − cos ζ]

        That root form is not an air mass: it is the *geometric chord* of a
        slab of thickness ``Δh`` on a spherical Earth, and an air mass is a
        density-weighted path.  With an 8 km molecular scale height the
        absorbing mass hugs the ground where curvature is negligible, so the
        two are different quantities and the switch was a step, not a
        refinement.  Measured against the exact spherical slant integral
        (:func:`radiant.atmosphere.grazing_column.grazing_slant_column_km`,
        molecular scale height, ground → 100 km):

        =======  ==========  ===========  ==========
        ζ [deg]  ``sec ζ``   root form    exact
        =======  ==========  ===========  ==========
        30       1.15470     1.15470       1.15422
        60       2.00000     2.00000       1.99258
        79.9     5.70234     (unused)      5.49989
        80.1     5.81635     4.80715       5.60209
        85       11.47371    7.06683      10.14005
        89.4     95.49471   10.68472      28.37722
        =======  ==========  ===========  ==========

        The root form was 14 % low at 80.1°, 30 % at 85° and 62 % at 89.4°,
        and it produced an 18 % *drop* in air mass across its own switch —
        transmittance discontinuous in look angle for every scene class.
        Removing it makes the model continuous, monotone in ζ, and internally
        consistent: :class:`~radiant.atmosphere.simple.SimpleAtmosphere` is
        plane-parallel everywhere else too (vertical columns × one air mass,
        mean-altitude species weights, target-anchored emission height).

        Accuracy past 80° is bought by *routing elsewhere*, not by patching
        this formula: the exact spherical slant integral lives in
        :mod:`radiant.atmosphere.segment_grazing`, and every caller that has
        that route takes it at :data:`SPHERICAL_SWITCH_RAD` (the up-looking
        sky background does — §4.2g).  Callers that do not (the down-looking
        column, the solar column) now overestimate the air mass near the
        horizon rather than underestimating it — a pessimistic SNR rather than
        an optimistic one — and that residual is tracked as CU-275.

        For exo-atmospheric paths (``Δh = 0``) the slant path is zero.
        Callers needing a positive path length must use a model whose
        contract guarantees ``slant_path_length_m > 0`` (i.e. not
        ``ExoAtmosphere``).
        """
        return self._absorbing_thickness_m() / math.cos(self.path_zenith_rad)

    def _absorbing_thickness_m(self) -> float:
        """Vertical extent of *atmosphere* on this segment [m] (CU-255).

        :meth:`slant_path_length_m` is a slab formula: it answers "how much air
        does this ray traverse", not "how far apart are the endpoints". Where
        the path ends inside the atmosphere the two coincide, which is why the
        distinction went unnoticed.

        For an up-looking segment ending **above** the column they do not. A
        ground site viewing a 700 km target gives Δh = 700 km — a slab a hundred
        times thicker than the real atmosphere — so the reported length would be
        700 km/cos ζ of which 600 km is vacuum. Under the pre-CU-274 root form
        the same input also made optical depth *fall* as the ray tilted further
        from vertical (scenario 10.3: τ(0.55 µm) 0.0137 at 79.9° → 0.0980 at
        80.1°); that branch is gone, but the thickness clamp is still what makes
        the reported length and the air mass describe the absorbing path.

        Clamping at the column top does that: vacuum above the column
        contributes no extinction, so excluding it loses nothing.
        """
        h_low = min(self.sensor_altitude_m, self.target_altitude_m)
        return min(self.altitude_difference_m, max(H_ATM_TOP_M - h_low, 0.0))

    def cos_scattering_angle(self) -> float:
        """Cosine of the single-scatter angle ``Θ`` between sun and sensor.

        For a photon that leaves the sun, scatters once in the
        atmosphere, and heads toward the sensor, the scattering angle
        is the angle between the incoming (downward from sun) and
        outgoing (upward toward sensor) directions. In the local
        plane-parallel frame::

            cos Θ = −[sin θ_s sin θ_v cos(Δφ) + cos θ_s cos θ_v]

        where ``θ_s`` is the solar zenith, ``θ_v`` is the sensor look
        zenith, and ``Δφ = solar_azimuth_rad`` is the sun-to-sensor
        relative azimuth. The leading minus captures the reversal
        between the incoming and outgoing photon directions.

        Sanity: sun at zenith + sensor at nadir → cos Θ = −1
        (exact backscatter). Sun at the horizon facing the sensor
        (θ_s = 90°, θ_v = 0, any Δφ) → cos Θ = 0 (side scatter).
        """
        th_s = self.solar_zenith_rad
        th_v = self.path_zenith_rad
        d_phi = self.solar_azimuth_rad
        return -(
            math.sin(th_s) * math.sin(th_v) * math.cos(d_phi) + math.cos(th_s) * math.cos(th_v)
        )

    def air_mass(self) -> float:
        """Dimensionless air mass ``L_slant / Δh`` — ``sec(ζ)`` (CU-274).

        Since the root-form branch was removed the ratio is exactly
        ``sec(path_zenith_rad)`` for every non-degenerate geometry: the
        absorbing thickness cancels between numerator and denominator. It is
        still written as the ratio rather than as ``1/cos ζ`` because that is
        the *definition* of an air mass, and because ``Δh = 0`` needs the
        conventional answer below.

        For ``Δh = 0`` (no atmosphere along the line of sight) the air
        mass is conventionally ``1`` — this matches the
        ``ExoAtmosphere`` contract that ``air_mass ≥ 1`` always.
        """
        # CU-255: normalise by the same absorbing thickness the slant path uses.
        # Dividing the clamped path by the raw endpoint separation would report an
        # air mass below 1 for a target above the column, contradicting the
        # ``air_mass ≥ 1`` contract stated above.
        dh = self._absorbing_thickness_m()
        if dh == 0.0:
            return 1.0
        return self.slant_path_length_m() / dh

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-compatible dict (radians preserved)."""
        return {
            "sensor_altitude_m": float(self.sensor_altitude_m),
            "target_altitude_m": float(self.target_altitude_m),
            "path_zenith_rad": float(self.path_zenith_rad),
            "solar_zenith_rad": float(self.solar_zenith_rad),
            "solar_azimuth_rad": float(self.solar_azimuth_rad),
            "observer_type": str(self.observer_type),
            "target_type": str(self.target_type),
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> AtmosphericGeometry:
        """Deserialize from a dict produced by :meth:`to_dict`."""
        return cls(
            sensor_altitude_m=float(d["sensor_altitude_m"]),
            target_altitude_m=float(d["target_altitude_m"]),
            path_zenith_rad=float(d["path_zenith_rad"]),
            solar_zenith_rad=float(d.get("solar_zenith_rad", 0.0)),
            solar_azimuth_rad=float(d.get("solar_azimuth_rad", 0.0)),
            observer_type=str(d.get("observer_type", "airborne")),
            target_type=str(d.get("target_type", "ground")),
        )


# ---------------------------------------------------------------------------
# AtmosphericState
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AtmosphericState:
    """The frozen contract every atmosphere model returns.

    Per ``docs/architecture/RADIANT_Atmosphere.md`` §2:

    - ``transmittance``, ``path_radiance``, and ``atm_emission_down`` are
      **always** populated. ``ExoAtmosphere`` returns numerical zero
      rather than ``None`` for the radiance fields.
    - All three spectral arrays share the same wavelength grid (the
      grid the model was evaluated on). Wavelength alignment is enforced
      at construction time, not at consumption time.
    - ``air_mass`` and ``slant_path_length_m`` are derived from
      ``geometry`` at construction and stored for downstream use.

    The full doc-spec ``AtmosphericState`` carries additional fields for
    MODTRAN provenance (``model``, ``derivation_chain``, ``cache_key``,
    ``native_output``) and turbulence. Those are deferred to later
    phases of the implementation; see ``docs/archive/blocked_overnight_log.md`` for the open
    items.

    Parameters
    ----------
    transmittance:
        ``τ_atm(λ)`` — dimensionless ``[0, 1]``. ``unit`` should be the
        empty string.
    path_radiance:
        ``L_path(λ)`` — upwelling path radiance, ``W/m²/sr/µm``,
        non-negative.
    atm_emission_down:
        ``L_atm_down(λ)`` — downwelling atmospheric emission,
        ``W/m²/sr/µm``, non-negative.
    geometry:
        The :class:`AtmosphericGeometry` the model was evaluated for.
    derivation_chain:
        Optional human-readable build steps; ``()`` by default.
    """

    transmittance: SpectralData
    path_radiance: SpectralData
    atm_emission_down: SpectralData
    geometry: AtmosphericGeometry
    derivation_chain: tuple[str, ...] = field(default=())

    def __post_init__(self) -> None:
        # All three arrays must share the same wavelength grid. We
        # check element-wise rather than by `is` so a model that
        # constructs three separate arrays still passes.
        wl = self.transmittance.wavelength_um
        if not np.array_equal(wl, self.path_radiance.wavelength_um):
            raise AtmosphereValidationError(
                "AtmosphericState: transmittance and path_radiance must share "
                "the same wavelength grid."
            )
        if not np.array_equal(wl, self.atm_emission_down.wavelength_um):
            raise AtmosphereValidationError(
                "AtmosphericState: transmittance and atm_emission_down must "
                "share the same wavelength grid."
            )

        # Sanity bounds — RADIANT_Atmosphere.md §9.
        tau = self.transmittance.values
        if np.any(tau < 0.0) or np.any(tau > 1.0):
            raise AtmosphereValidationError(
                f"AtmosphericState: transmittance values out of [0, 1] "
                f"(min={float(tau.min()):g}, max={float(tau.max()):g}). "
                "Transmittance is a probability and must be bounded."
            )
        if np.any(self.path_radiance.values < 0.0):
            raise AtmosphereValidationError(
                "AtmosphericState: path_radiance has negative values. "
                "Path radiance is energy added to the line of sight and "
                "must be non-negative."
            )
        if np.any(self.atm_emission_down.values < 0.0):
            raise AtmosphereValidationError(
                "AtmosphericState: atm_emission_down has negative values."
            )

    # ------------------------------------------------------------------
    # Derived geometry passthroughs
    # ------------------------------------------------------------------

    @property
    def air_mass(self) -> float:
        """Dimensionless air mass ``L_slant / Δh``, ``≥ 1``."""
        return self.geometry.air_mass()

    @property
    def slant_path_length_m(self) -> float:
        """Slant-path length through the atmosphere [m]."""
        return self.geometry.slant_path_length_m()

    @property
    def wavelength_um(self) -> np.ndarray:
        """The shared wavelength grid (µm) — convenience accessor."""
        return self.transmittance.wavelength_um


# ---------------------------------------------------------------------------
# Atmosphere protocol
# ---------------------------------------------------------------------------


@runtime_checkable
class Atmosphere(Protocol):
    """Structural protocol for atmosphere models.

    A model is a pure producer of an :class:`AtmosphericQuantities`
    bundle for a given wavelength grid and line-of-sight geometry.
    Implementations must be deterministic: calling :meth:`evaluate`
    twice with the same inputs must return numerically identical
    results.

    Implementations must NOT perform file I/O at evaluation time
    (loading happens earlier, in the model constructor) and must NOT
    import from any other physics stage. They may only depend on
    ``radiant.core``.
    """

    def evaluate(
        self,
        wavelength_um: np.ndarray,
        los: LineOfSightGeometry,
        params: ParameterSet,
    ) -> AtmosphericQuantities:
        """Compute the Option C two-leg atmospheric quantities bundle.

        Produces the eight spectral arrays that the assembly equation
        needs: ``τ_sun``, ``τ_up``, ``τ_full_up``, ``E_TOA``,
        ``E_sky_scattered``, ``E_sky_thermal``, ``L_path_up``,
        ``L_path_full`` — all on the supplied wavelength grid and for the
        given :class:`LineOfSightGeometry`.

        Parameters
        ----------
        wavelength_um:
            1-D ascending wavelength grid in µm, strictly positive.
        los:
            The :class:`LineOfSightGeometry` published by SourceStage.
        params:
            The resolved :class:`ParameterSet` for the run.  Backends may
            consult it for atmospheric-model-specific settings; the
            authoritative geometry comes from ``los``.

        Returns
        -------
        AtmosphericQuantities
            The frozen Stage 3 output contract consumed by
            ``radiant.atmosphere.assembly``.
        """
        ...
