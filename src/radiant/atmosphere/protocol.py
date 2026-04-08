"""Atmosphere protocol, geometry, and state contract.

Defines the structural interface every atmosphere model in RADIANT must
satisfy and the immutable result it produces. Per
``docs/RADIANT_Atmosphere.md`` §2 the chain consumes a single
``AtmosphericState`` regardless of which model produced it (simple,
tabulated, MODTRAN, exo).

This 2B.2 cut implements the *minimum* contract: the three spectral
arrays (``transmittance``, ``path_radiance``, ``atm_emission_down``),
the geometry the state was evaluated for, and the derived ``air_mass``
and ``slant_path_length_m``. Fields that only matter for MODTRAN
(``derivation_chain``, ``cache_key``, ``native_output``) and
turbulence are deferred to later phases — see
``notes/blocked.md``.

The protocol is structural (``typing.Protocol``), so concrete models
do not need to subclass it. Duck typing is sufficient.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

import numpy as np

from radiant.core.spectral import SpectralData

# ---------------------------------------------------------------------------
# Constants used by geometry math
# ---------------------------------------------------------------------------

# Mean Earth radius [m] used for the spherical-Earth slant-path correction.
# Value from RADIANT_Atmosphere.md §4.2 (consistent with US Standard 1976).
EARTH_RADIUS_M: float = 6_371_000.0

# Zenith angle (rad) above which the flat-Earth approximation breaks down
# and the spherical correction kicks in. Per RADIANT_Atmosphere.md §4.2.
SPHERICAL_SWITCH_RAD: float = math.radians(80.0)

# Hard ceiling on the zenith angle. The horizon (π/2) is excluded — the
# slant path is finite under spherical correction but the simple model is
# not trustworthy in that regime, so the ceiling sits a hair below.
ZENITH_CEILING_RAD: float = math.radians(89.5)


# ---------------------------------------------------------------------------
# AtmosphericGeometry
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AtmosphericGeometry:
    """Geometry inputs to the atmosphere module.

    Per ``docs/RADIANT_Conventions.md`` §5 all angles are stored
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
        Must satisfy ``0 ≤ θ ≤ ZENITH_CEILING_RAD``. Past
        ``SPHERICAL_SWITCH_RAD`` the spherical-Earth correction is used
        for ``slant_path_length_m`` and ``air_mass``.
    solar_zenith_rad:
        Solar zenith angle [rad], for the single-scatter ``L_path``
        and reflected-solar paths. ``0 ≤ θ_sun < π/2``. Defaults to
        zero (sun overhead) which is enough for transmittance-only use.
    solar_azimuth_rad:
        Solar azimuth [rad]. Drives the scattering phase angle in
        ``L_path``. Defaults to zero. Not validated for sign — only
        the difference from the line-of-sight azimuth matters and
        future code can compute it from this raw value.
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
            raise ValueError(
                f"AtmosphericGeometry: sensor_altitude_m = {self.sensor_altitude_m} m "
                "is negative. Altitudes are measured above mean sea level; set "
                "sensor_altitude_m ≥ 0."
            )
        if self.target_altitude_m < 0.0:
            raise ValueError(
                f"AtmosphericGeometry: target_altitude_m = {self.target_altitude_m} m "
                "is negative. Set target_altitude_m ≥ 0."
            )
        if not (0.0 <= self.path_zenith_rad <= ZENITH_CEILING_RAD):
            raise ValueError(
                f"AtmosphericGeometry: path_zenith_rad = {self.path_zenith_rad:.4f} rad "
                f"({math.degrees(self.path_zenith_rad):.2f}°) is out of the supported "
                f"range [0, {math.degrees(ZENITH_CEILING_RAD):.1f}°]. The simple "
                "model is unreliable past the horizon; reduce path_zenith_rad or use "
                "a higher-fidelity atmosphere model."
            )
        if not (0.0 <= self.solar_zenith_rad < math.pi / 2):
            raise ValueError(
                f"AtmosphericGeometry: solar_zenith_rad = {self.solar_zenith_rad:.4f} rad "
                f"({math.degrees(self.solar_zenith_rad):.2f}°) is out of [0, 90°). "
                "Set solar_zenith_rad < π/2; for night-side conditions disable the "
                "reflected-solar source rather than supplying a sub-horizon sun."
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
        """Slant-path length through the atmosphere [m].

        Flat-Earth: ``L = Δh / cos(θ)`` for ``θ ≤ 80°``.

        Spherical-Earth correction past ``80°``::

            L = R_E · [√(cos²θ + 2(Δh/R_E) + (Δh/R_E)²) − cos θ]

        Per ``docs/RADIANT_Atmosphere.md`` §4.2.

        For exo-atmospheric paths (``Δh = 0``) the slant path is zero.
        Callers needing a positive path length must use a model whose
        contract guarantees ``slant_path_length_m > 0`` (i.e. not
        ``ExoAtmosphere``).
        """
        dh = self.altitude_difference_m
        cos_theta = math.cos(self.path_zenith_rad)
        if self.path_zenith_rad <= SPHERICAL_SWITCH_RAD:
            return dh / cos_theta
        # Spherical-Earth correction. The formulation is the standard
        # plane-parallel-atmosphere root-form Air Mass approximation
        # specialised to a finite-thickness slab.
        x = dh / EARTH_RADIUS_M
        radicand = cos_theta * cos_theta + 2.0 * x + x * x
        return EARTH_RADIUS_M * (math.sqrt(radicand) - cos_theta)

    def air_mass(self) -> float:
        """Dimensionless air mass ``L_slant / Δh``.

        For ``Δh = 0`` (no atmosphere along the line of sight) the air
        mass is conventionally ``1`` — this matches the
        ``ExoAtmosphere`` contract that ``air_mass ≥ 1`` always.
        """
        dh = self.altitude_difference_m
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

    Per ``docs/RADIANT_Atmosphere.md`` §2:

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
    phases of the implementation; see ``notes/blocked.md`` for the open
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
            raise ValueError(
                "AtmosphericState: transmittance and path_radiance must share "
                "the same wavelength grid."
            )
        if not np.array_equal(wl, self.atm_emission_down.wavelength_um):
            raise ValueError(
                "AtmosphericState: transmittance and atm_emission_down must "
                "share the same wavelength grid."
            )

        # Sanity bounds — RADIANT_Atmosphere.md §9.
        tau = self.transmittance.values
        if np.any(tau < 0.0) or np.any(tau > 1.0):
            raise ValueError(
                f"AtmosphericState: transmittance values out of [0, 1] "
                f"(min={float(tau.min()):g}, max={float(tau.max()):g}). "
                "Transmittance is a probability and must be bounded."
            )
        if np.any(self.path_radiance.values < 0.0):
            raise ValueError(
                "AtmosphericState: path_radiance has negative values. "
                "Path radiance is energy added to the line of sight and "
                "must be non-negative."
            )
        if np.any(self.atm_emission_down.values < 0.0):
            raise ValueError("AtmosphericState: atm_emission_down has negative values.")

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

    A model is a pure producer of an :class:`AtmosphericState` for a
    given wavelength grid and geometry. Implementations must be
    deterministic: calling ``build_state`` twice with the same inputs
    must return numerically identical results.

    Implementations must NOT perform file I/O at evaluation time
    (loading happens earlier, in the model constructor) and must NOT
    import from any other physics stage. They may only depend on
    ``radiant.core``.
    """

    def build_state(
        self,
        wavelength_um: np.ndarray,
        geometry: AtmosphericGeometry,
    ) -> AtmosphericState:
        """Compute the atmospheric state on the given grid.

        Parameters
        ----------
        wavelength_um:
            1-D ascending wavelength grid in µm, strictly positive.
        geometry:
            The :class:`AtmosphericGeometry` to evaluate at.

        Returns
        -------
        AtmosphericState
            The frozen state object the chain consumes.
        """
        ...
