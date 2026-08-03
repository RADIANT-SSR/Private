"""Interpolated atmosphere model — geometry-dependent interpolation between runs.

Holds a collection of pre-computed atmospheric states at discrete
geometry points (e.g. from MODTRAN runs or tabulated files) and
interpolates between them for arbitrary query geometries.

Interpolation strategy
----------------------
- **Transmittance**: interpolated in **log-transmittance** (optical
  depth) space.  This is physically motivated: Beer-Lambert gives
  ``tau = exp(-OD)`` where OD is the optical depth, which scales
  linearly with path length and absorber amount.  Interpolating in
  ln(tau) space preserves this linearity.  Values are clamped to
  ``[TAU_FLOOR, 1.0]`` before taking the log to avoid ``-inf``.
  The **wavelength resample** onto a differing chain grid runs in the
  same ln(tau) space (CU-306), so the geometry interpolation and the
  spectral resample are both linear in optical depth and therefore
  commute; resampling linearly in tau instead made the result depend
  on the operation order, to up to ~2% relative tau at off-node query
  wavelengths.

- **Zenith-angle axes interpolate in airmass space** (CU-160):
  ``path_zenith_rad`` / ``solar_zenith_rad`` coordinates are mapped
  θ → sec(θ) before interpolation, completing the same Beer-Lambert
  motivation — the path length along a zenith axis is ∝ sec(θ), so
  log-τ linear in sec(θ) reproduces Beer exactly, where linear-in-angle
  carried a measured ~−4% in-band τ bias at fan midpoints (real
  MODTRAN 6 B-fan holdout, scenario 8.1).  The transform is internal:
  user-facing coordinates, bounds, and errors stay in radians.  Angles
  ≥ ``_MAX_ZENITH_RAD`` (≈ 88.8°) are refused — sec(θ) diverges at the
  horizon.

- **Path radiance** (L_path) and **downwelling emission** (L_atm_down):
  interpolated linearly, and resampled onto the query wavelength grid
  linearly.  These are additive quantities with no multiplicative
  structure — no Beer-Lambert exponential in path length — that would
  benefit from log-space, so CU-306 deliberately left them linear.

- **No extrapolation**: query geometries outside the convex hull of
  available points always raise ``ValueError``.  We never silently
  invent atmospheric data beyond the calibration range.  The single
  query served from outside the node span is not an exception to that
  rule but an application of it: an endpoint above the top of the
  modelled atmosphere is separated from a node there by **vacuum**, so
  the node's column is the exact answer rather than an extrapolated one
  (:data:`_VACUUM_EQUIVALENT_ALTITUDE_M`, one clamp per axis).

Grid detection
--------------
If the available geometry points form a structured rectangular grid
(Cartesian product of unique values per axis), the constructor uses
``scipy.interpolate.RegularGridInterpolator`` for efficiency.
Otherwise it falls back to ``scipy.interpolate.LinearNDInterpolator``
for scattered data.

Family direction (Geometry-Flexibility Phase 2, GF-10)
------------------------------------------------------
Every family shipped before Phase 2 is **down-looking**: its radiance
product is the upwelling path radiance a sensor above the column sees.
The K-block ``midlat_summer_uplooking_ladder`` family was the first
**up-looking** one (the batch-2 delivery added three more — a zenith fan,
a full-column zenith fan, and an elevated-observer ladder), and its
radiance product is the *downward* path
radiance a sensor below the column sees — ``L_toward_lower`` in the
:mod:`radiant.atmosphere.segments` vocabulary.  Those are different
physical quantities, so they are kept apart at every level:

- different NPZ key (:data:`UPLOOKING_RADIANCE_KEY` vs ``path_radiance``),
  so a down-looking reader fails on a missing key rather than silently
  reading the wrong product;
- a ``family_direction`` on the model object, defaulting to ``"down"`` so
  every pre-existing construction is unchanged;
- different query entry points — :meth:`InterpolatedAtmosphere.evaluate`
  (the eight-field down-looking bundle) refuses an up-looking family, and
  :meth:`InterpolatedAtmosphere.uplooking_column_product` (the segment
  product) refuses a down-looking one.

Zero drift: a family constructed without ``family_direction`` behaves
exactly as before — same interpolators, same warnings, same numbers.
"""

from __future__ import annotations

import logging
import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np
from scipy.interpolate import LinearNDInterpolator, RegularGridInterpolator

from radiant.atmosphere._quantities import AtmosphericQuantities
from radiant.atmosphere._sensor_endpoint import require_sensor_altitude_m
from radiant.atmosphere.errors import AtmosphereCapabilityError, AtmosphereValidationError
from radiant.atmosphere.log_tau_resample import TAU_FLOOR
from radiant.atmosphere.protocol import (
    AtmosphericGeometry,
    AtmosphericState,
)
from radiant.core.los_geometry import LineOfSightGeometry
from radiant.core.parameters import ParameterSet
from radiant.core.solar import toa_solar_spectral_irradiance
from radiant.core.spectral import SpectralData, SpectralGrid

logger = logging.getLogger(__name__)

# TAU_FLOOR — the minimum transmittance before taking the log, so log(0) is
# never -inf — is used below and imported above from
# radiant.atmosphere.log_tau_resample, which owns the single definition:
# CU-316 made the log-τ convention universal across the three backends, and
# they must share one floor (Rule 27).  Importers of
# `radiant.atmosphere.interpolated.TAU_FLOOR` are unaffected.

# Geometry fields that can be used as interpolation axes.
_GEOMETRY_FIELDS: frozenset[str] = frozenset(
    {
        "sensor_altitude_m",
        "target_altitude_m",
        "path_zenith_rad",
        "solar_zenith_rad",
        "solar_azimuth_rad",
    }
)

# Zenith-angle axes are interpolated in AIRMASS space, sec(θ), not in the
# angle itself (CU-160). Optical depth scales with path length, and the
# path length along a zenith axis is ∝ sec(θ) — so log-τ linear in sec(θ)
# reproduces Beer-Lambert exactly, while linear-in-angle carries a ~−4%
# in-band τ bias at fan midpoints (measured against the real MODTRAN 6
# B-fan holdout, scenario 8.1). The transform is internal: coordinates,
# bounds, and error messages remain in radians.
_AIRMASS_AXES: frozenset[str] = frozenset({"path_zenith_rad", "solar_zenith_rad"})

# sec(θ) diverges at the horizon; refuse angles this close to π/2 rather
# than interpolate on an exploding coordinate (≈ 88.85°, airmass ≈ 50).
_MAX_ZENITH_RAD: float = 1.55

# CU-167: a query field that is NOT an interpolation axis is served with the
# stored runs' (fixed) value, whatever the query says. When the query differs
# from the stored value beyond these tolerances, warn — silently substituting
# e.g. the nadir column for a 45° slant path is a Rule-17-class reduction.
_NON_AXIS_ANGLE_TOL_RAD: float = 0.0175  # ≈ 1°
_NON_AXIS_LENGTH_TOL_M: float = 1.0

# Geometry fields measured as angles (tolerance in radians); the rest are
# altitudes (tolerance in metres).
_ANGLE_FIELDS: frozenset[str] = frozenset(
    {"path_zenith_rad", "solar_zenith_rad", "solar_azimuth_rad"}
)

# Non-axis fields with no recorded value fall back to these assumed run
# geometries for the mismatch check (the shipped families are rendered
# nadir; record the field in the NPZ 'geometry' dict to override). Fields
# not listed here are skipped when unrecorded — there is no defensible
# assumption for e.g. an unrecorded sensor altitude.
_ASSUMED_UNRECORDED: dict[str, float] = {"path_zenith_rad": 0.0}

# --- Up-looking family contract (GF-10) ------------------------------------

#: NPZ key carrying an up-looking family's DOWNWARD path radiance
#: [W/m²/sr/µm] — the ``L_toward_lower`` product of
#: :mod:`radiant.atmosphere.segments`.  Deliberately not ``path_radiance``:
#: the two are different physical quantities and must not be
#: interchangeable by accident (Rule 17).
UPLOOKING_RADIANCE_KEY: str = "path_radiance_toward_lower"

#: NPZ key carrying a family's self-describing LOS direction marker.
FAMILY_DIRECTION_KEY: str = "los_direction"

#: Directions a shipped family can declare.  ``"down"`` is the historical
#: (and default) value; ``"up"`` is the Phase-2 K-block family.
FAMILY_DIRECTIONS: frozenset[str] = frozenset({"down", "up"})

# An up-looking family WITHOUT a ``path_zenith_rad`` axis is rendered at ONE
# lower-endpoint zenith — the K ladder at vertical, the batch-2 P ladder at the
# 48.2° diffusivity angle. Serving any other zenith from it would need a
# sec-space fan the family does not carry, so the query is refused rather than
# approximated (Rule 17). A family that DOES carry the axis (the batch-2 N fan
# and M column fan) interpolates the zenith in sec(ζ) space like every
# down-looking fan (CU-160) and never reaches this check. The tolerance is pure
# float slack: geometry hands vertical paths theta_o = π exactly.
_UPLOOKING_FIXED_ZENITH_TOL_RAD: float = 1e-6

# MODTRAN's atmosphere ends at 100 km: everything above it is vacuum — zero
# extinction, zero emission — so moving an endpoint from this altitude to any
# higher one adds nothing to the column. Two queries are therefore physically
# EXACT rather than mismatches or extrapolations, one per axis:
#
# * **sensor axis** — a query sensor ABOVE a recorded at-or-above-TOA sensor
#   sees the identical column (:meth:`InterpolatedAtmosphere._warn_ignored_geometry`).
#   This is the identity that justifies the ladders' 40,000 km duplicate node.
# * **target axis** — for an up-looking family whose own runs REACH this
#   altitude, a query target above the family ceiling is served by the ceiling
#   node (:meth:`InterpolatedAtmosphere._vacuum_clamped_target_m`). Same
#   physics, other end of the path: the family measured the entire column, and
#   the extra path to an exo target is vacuum.
#
# A family whose ceiling is BELOW this altitude gets neither clamp — it never
# measured the whole column, so a query past its top rung is extrapolation and
# is refused (Rule 17).
_VACUUM_EQUIVALENT_ALTITUDE_M: float = 100_000.0


def _axis_to_interp_space(axis: str, values: np.ndarray | float) -> np.ndarray | float:
    """Map coordinate values to the axis's interpolation space.

    Zenith-angle axes map θ → sec(θ) (airmass, CU-160); all other axes
    are identity. Raises for angles at/beyond ``_MAX_ZENITH_RAD`` where
    sec(θ) diverges.
    """
    if axis not in _AIRMASS_AXES:
        return values
    arr = np.asarray(values, dtype=np.float64)
    if np.any(arr < 0.0) or np.any(arr >= _MAX_ZENITH_RAD):
        raise AtmosphereValidationError(
            f"InterpolatedAtmosphere: axis '{axis}' value(s) outside "
            f"[0, {_MAX_ZENITH_RAD}) rad — the airmass transform sec(θ) "
            "diverges toward the horizon. Keep zenith angles below "
            f"{np.degrees(_MAX_ZENITH_RAD):.1f}°, or interpolate over a "
            "different axis."
        )
    result = 1.0 / np.cos(arr)
    return float(result) if np.isscalar(values) else result


def _extract_geometry_coord(geometry: AtmosphericGeometry, axis: str) -> float:
    """Extract a named coordinate from an AtmosphericGeometry."""
    if axis not in _GEOMETRY_FIELDS:
        raise AtmosphereValidationError(
            f"InterpolatedAtmosphere: axis '{axis}' is not a valid geometry "
            f"field. Choose from {sorted(_GEOMETRY_FIELDS)}."
        )
    return float(getattr(geometry, axis))


def _is_structured_grid(
    coords: np.ndarray,
    n_axes: int,
) -> tuple[bool, list[np.ndarray]]:
    """Detect whether N-D coordinates form a structured rectangular grid.

    Parameters
    ----------
    coords:
        Shape ``(n_points, n_axes)`` array of coordinate values.
    n_axes:
        Number of interpolation axes.

    Returns
    -------
    is_structured:
        True if the points form a Cartesian product grid.
    unique_per_axis:
        List of sorted unique values for each axis (meaningful only
        if ``is_structured`` is True).
    """
    unique_per_axis: list[np.ndarray] = []
    for j in range(n_axes):
        unique_per_axis.append(np.unique(coords[:, j]))

    expected_count = 1
    for u in unique_per_axis:
        expected_count *= len(u)

    if expected_count != coords.shape[0]:
        return False, unique_per_axis

    # Verify every combination is present.
    coord_set = {tuple(row) for row in coords}
    from itertools import product as cart_product

    for combo in cart_product(*unique_per_axis):
        if combo not in coord_set:
            return False, unique_per_axis

    return True, unique_per_axis


# ---------------------------------------------------------------------------
# GeometryPoint
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class GeometryPoint:
    """A pre-computed atmospheric state at a specific geometry.

    Parameters
    ----------
    coordinates:
        Dict mapping axis names to coordinate values, e.g.
        ``{"path_zenith_rad": 0.3, "sensor_altitude_m": 20000}``.
    transmittance:
        Spectral transmittance at this geometry.
    path_radiance:
        Spectral path radiance at this geometry.
    atm_emission_down:
        Spectral downwelling emission at this geometry.
    """

    coordinates: dict[str, float]
    transmittance: SpectralData
    path_radiance: SpectralData
    atm_emission_down: SpectralData


@dataclass(frozen=True)
class UplookingColumnProduct:
    """One up-looking column segment, interpolated out of an up-looking family.

    Parameters
    ----------
    wavelength_um:
        Query wavelength grid [µm].
    tau:
        Segment transmittance, dimensionless ∈ [0, 1].  One value per
        segment: τ is reciprocal (``RADIANT_Atmosphere.md`` §4.4).
    L_toward_lower:
        Radiance emerging at the segment's **lower** end travelling downward
        [W/m²/sr/µm] — what the ground sensor at the lower endpoint sees.
    provenance:
        Inputs and intermediates (Rule 16 inspectability).  Never consumed by
        physics.

    Notes
    -----
    This deliberately is **not** a
    :class:`~radiant.atmosphere.segments.SegmentQuantities`.  That contract
    carries both directional radiances, and an up-looking MODTRAN family
    measures only one of them: the reverse-direction product for the same
    column is a separate run set (the reciprocal down-looking F/J block
    covers only 3 of the 5 K rungs).  Publishing a ``SegmentQuantities``
    would require inventing an ``L_toward_upper``; a type with no such field
    is the Rule-17-clean way to say "this family carries one direction".
    The topology layer composes it into the eight-field bundle.
    """

    wavelength_um: np.ndarray
    tau: np.ndarray
    L_toward_lower: np.ndarray
    provenance: dict[str, Any]


# ---------------------------------------------------------------------------
# InterpolatedAtmosphere
# ---------------------------------------------------------------------------


class InterpolatedAtmosphere:
    """Atmosphere model that interpolates between pre-computed runs.

    Parameters
    ----------
    points:
        Collection of pre-computed atmospheric states at discrete
        geometry points.
    axes:
        Which geometry fields to interpolate over (e.g.
        ``["path_zenith_rad"]`` or
        ``["path_zenith_rad", "sensor_altitude_m"]``).
    method:
        Interpolation method: ``"linear"`` (default) or ``"nearest"``.
    family_direction:
        Which LOS direction the sample runs were rendered for — ``"down"``
        (default, every pre-Phase-2 family) or ``"up"`` (the K-block
        up-looking ladder).  Keyword-only and defaulted, so every existing
        construction is byte-for-byte unchanged.  It selects which query
        entry point is legal: ``"down"`` families serve :meth:`evaluate`,
        ``"up"`` families serve :meth:`uplooking_column_product`.
    uplooking_companion:
        Backend that serves the legs an up-looking family does **not** carry
        (CU-226): the target's illumination — the solar column and sky
        hemisphere *above* the target — and the sky radiance along the LOS
        continuation out to ``h_atm_top``.  An up-looking run family is one
        column, sensor → target; neither of those legs is any rung of it, and
        neither can be recovered from it.  ``None`` (the default, and the only
        value a down-looking family ever takes) means the model serves the
        observer leg only, which is what
        :func:`radiant.atmosphere.uplooking_quantities.supports_uplooking`
        keys on.  Built pre-chain by
        :func:`radiant.atmosphere.loaders.build_atmosphere_model`, never here.
    """

    def __init__(
        self,
        points: Sequence[GeometryPoint],
        axes: Sequence[str],
        method: str = "linear",
        *,
        family_direction: str = "down",
        uplooking_companion: object | None = None,
    ) -> None:
        if family_direction not in FAMILY_DIRECTIONS:
            raise AtmosphereValidationError(
                f"InterpolatedAtmosphere: family_direction='{family_direction}' "
                f"is not recognised. Choose one of {sorted(FAMILY_DIRECTIONS)} — "
                "'down' for an upwelling (sensor-above-column) run family, 'up' "
                "for a downwelling (sensor-below-column) one."
            )
        self._family_direction = family_direction
        if uplooking_companion is not None and family_direction != "up":
            raise AtmosphereValidationError(
                "InterpolatedAtmosphere: uplooking_companion was supplied for a "
                f"'{family_direction}'-looking family. The companion serves the "
                "illumination and sky-continuation legs of an UP-looking "
                "topology only; a down-looking family's evaluate() already "
                "returns the whole eight-field bundle, and attaching a second "
                "backend to it would silently mix two atmospheres."
            )
        self._uplooking_companion = uplooking_companion
        if len(points) < 2:
            raise AtmosphereValidationError(
                f"InterpolatedAtmosphere: at least 2 geometry points required, got {len(points)}."
            )
        if not axes:
            raise AtmosphereValidationError(
                "InterpolatedAtmosphere: at least one interpolation axis required."
            )
        for ax in axes:
            if ax not in _GEOMETRY_FIELDS:
                raise AtmosphereValidationError(
                    f"InterpolatedAtmosphere: axis '{ax}' is not a valid "
                    f"geometry field. Choose from {sorted(_GEOMETRY_FIELDS)}."
                )
        if method not in ("linear", "nearest"):
            raise AtmosphereValidationError(
                f"InterpolatedAtmosphere: method='{method}' not supported. "
                "Choose 'linear' or 'nearest'."
            )

        self._axes = list(axes)
        self._method = method
        self._name = "interpolated_atmosphere"

        # Validate: all points have coordinates for every axis.
        for i, pt in enumerate(points):
            for ax in self._axes:
                if ax not in pt.coordinates:
                    raise AtmosphereValidationError(
                        f"InterpolatedAtmosphere: point {i} is missing "
                        f"coordinate for axis '{ax}'. Available: "
                        f"{sorted(pt.coordinates)}."
                    )

        # CU-167: record the fixed value of any non-axis geometry field the
        # points carry, so queries can be checked against the stored run
        # geometry. A recorded non-axis field that VARIES across points is
        # ill-posed — the samples differ in a dimension the interpolator
        # would silently ignore — and is refused loud.
        self._non_axis_recorded: dict[str, float] = {}
        for field in sorted(_GEOMETRY_FIELDS - set(self._axes)):
            recorded = [float(pt.coordinates[field]) for pt in points if field in pt.coordinates]
            if not recorded:
                continue
            tol = _NON_AXIS_ANGLE_TOL_RAD if field in _ANGLE_FIELDS else _NON_AXIS_LENGTH_TOL_M
            if max(recorded) - min(recorded) > tol:
                raise AtmosphereValidationError(
                    f"InterpolatedAtmosphere: non-axis geometry field '{field}' "
                    f"varies across the sample points "
                    f"([{min(recorded):.6g}, {max(recorded):.6g}]) but is not an "
                    "interpolation axis — the samples differ in a dimension the "
                    "interpolator would silently ignore (CU-167). Add the field "
                    "to the interpolation axes, or fix the sample set."
                )
            self._non_axis_recorded[field] = recorded[0]

        # Validate: all points share the same wavelength grid.
        ref_wl = points[0].transmittance.wavelength_um
        for i, pt in enumerate(points[1:], start=1):
            if not np.array_equal(ref_wl, pt.transmittance.wavelength_um):
                raise AtmosphereValidationError(
                    f"InterpolatedAtmosphere: point {i} has a different "
                    "wavelength grid than point 0. All points must share "
                    "the same spectral grid. Pre-resample if needed."
                )

        self._wavelength_um = ref_wl.copy()
        n_wl = len(ref_wl)
        n_pts = len(points)

        # Build coordinate and value arrays.
        coords = np.empty((n_pts, len(self._axes)), dtype=np.float64)
        log_tau = np.empty((n_pts, n_wl), dtype=np.float64)
        lpath = np.empty((n_pts, n_wl), dtype=np.float64)
        ldown = np.empty((n_pts, n_wl), dtype=np.float64)

        for i, pt in enumerate(points):
            for j, ax in enumerate(self._axes):
                coords[i, j] = pt.coordinates[ax]
            tau_vals = np.clip(pt.transmittance.values, TAU_FLOOR, 1.0)
            log_tau[i, :] = np.log(tau_vals)
            lpath[i, :] = pt.path_radiance.values
            ldown[i, :] = pt.atm_emission_down.values

        # Original-unit coordinates: bounds reporting and hull checks stay
        # in the user's units (radians for angles). The interpolators run
        # on the transformed coordinates (airmass for zenith axes, CU-160).
        self._coords = coords
        interp_coords = coords.copy()
        for j, ax in enumerate(self._axes):
            interp_coords[:, j] = _axis_to_interp_space(ax, coords[:, j])

        # Detect structured vs scattered grid (transform is monotonic, so
        # grid structure is preserved either way).
        is_struct, unique_per_axis = _is_structured_grid(interp_coords, len(self._axes))

        if is_struct and len(self._axes) >= 1:
            self._grid_type = "regular"
            self._unique_per_axis = unique_per_axis

            # Reshape values to grid shape + n_wl for RegularGridInterpolator.
            grid_shape = tuple(len(u) for u in unique_per_axis)

            # Build a mapping from coordinate tuple -> point index
            # (in interpolation space, matching unique_per_axis).
            coord_to_idx: dict[tuple[float, ...], int] = {}
            for i in range(n_pts):
                key = tuple(float(interp_coords[i, j]) for j in range(len(self._axes)))
                coord_to_idx[key] = i

            # Fill grid arrays.
            log_tau_grid = np.empty(grid_shape + (n_wl,), dtype=np.float64)
            lpath_grid = np.empty(grid_shape + (n_wl,), dtype=np.float64)
            ldown_grid = np.empty(grid_shape + (n_wl,), dtype=np.float64)

            from itertools import product as cart_product

            for multi_idx in cart_product(*(range(len(u)) for u in unique_per_axis)):
                key = tuple(float(unique_per_axis[j][multi_idx[j]]) for j in range(len(self._axes)))
                pt_idx = coord_to_idx[key]
                log_tau_grid[multi_idx] = log_tau[pt_idx]
                lpath_grid[multi_idx] = lpath[pt_idx]
                ldown_grid[multi_idx] = ldown[pt_idx]

            axis_values = tuple(u for u in unique_per_axis)

            self._interp_log_tau = RegularGridInterpolator(
                axis_values,
                log_tau_grid,
                method=method,
                bounds_error=True,
            )
            self._interp_lpath = RegularGridInterpolator(
                axis_values,
                lpath_grid,
                method=method,
                bounds_error=True,
            )
            self._interp_ldown = RegularGridInterpolator(
                axis_values,
                ldown_grid,
                method=method,
                bounds_error=True,
            )
        else:
            self._grid_type = "scattered"
            # LinearNDInterpolator for unstructured data (interp space).
            self._interp_log_tau = LinearNDInterpolator(interp_coords, log_tau)
            self._interp_lpath = LinearNDInterpolator(interp_coords, lpath)
            self._interp_ldown = LinearNDInterpolator(interp_coords, ldown)

        logger.info(
            "InterpolatedAtmosphere: %d points, %d axes (%s), %s grid, %d wavelengths",
            n_pts,
            len(self._axes),
            ", ".join(self._axes),
            self._grid_type,
            n_wl,
        )

    @property
    def name(self) -> str:
        return self._name

    @property
    def axes(self) -> list[str]:
        """The geometry axes being interpolated over."""
        return list(self._axes)

    @property
    def family_direction(self) -> str:
        """``'down'`` (upwelling products) or ``'up'`` (downwelling products)."""
        return self._family_direction

    @property
    def grid_type(self) -> str:
        """'regular' for structured grid, 'scattered' for unstructured."""
        return self._grid_type

    @property
    def n_points(self) -> int:
        """Number of pre-computed geometry points."""
        return self._coords.shape[0]

    @property
    def wavelength_um(self) -> np.ndarray:
        """The shared wavelength grid of all points."""
        return self._wavelength_um.copy()

    def _warn_ignored_geometry(self, geometry: AtmosphericGeometry) -> None:
        """CU-167: warn when a non-axis query field departs from the stored runs.

        The reference is the value recorded in the sample points' coordinate
        dicts when present (constructor-validated as consistent), else the
        assumed run geometry in :data:`_ASSUMED_UNRECORDED` (LOS zenith:
        nadir — every shipped down-looking family is nadir-rendered). Fields
        with neither are skipped: no defensible reference exists.
        """
        import warnings

        for field in sorted(_GEOMETRY_FIELDS - set(self._axes)):
            reference = self._non_axis_recorded.get(field, _ASSUMED_UNRECORDED.get(field))
            if reference is None:
                continue
            query_val = float(getattr(geometry, field))
            if (
                field == "sensor_altitude_m"
                and reference >= _VACUUM_EQUIVALENT_ALTITUDE_M
                and query_val > reference
            ):
                # Query sensor above a recorded at-/above-TOA sensor: the
                # added path is vacuum, the column is identical — exact,
                # not a mismatch.
                continue
            tol = _NON_AXIS_ANGLE_TOL_RAD if field in _ANGLE_FIELDS else _NON_AXIS_LENGTH_TOL_M
            if abs(query_val - reference) > tol:
                origin = "recorded" if field in self._non_axis_recorded else "assumed"
                warnings.warn(
                    (
                        f"InterpolatedAtmosphere: query {field} = {query_val:.6g} "
                        f"is IGNORED — '{field}' is not an interpolation axis "
                        f"(axes={self._axes}), so the result carries the sample "
                        f"runs' {origin} value {reference:.6g} instead (CU-167). "
                        "Add runs covering this dimension and include "
                        f"'{field}' in atmosphere.interpolation_axes, or accept "
                        "the stored geometry's physics."
                    ),
                    UserWarning,
                    stacklevel=3,
                )

    def _require_family_direction(self, wanted: str, where: str) -> None:
        """Refuse a query whose direction the loaded family cannot serve.

        Up-looking and down-looking families carry *different physical
        products* under superficially similar names (upwelling vs downwelling
        path radiance).  Serving one through the other's entry point would be
        a silent, plausible-looking error — exactly what Rule 17 forbids.
        """
        if self._family_direction == wanted:
            return
        if wanted == "down":
            action = (
                "Use InterpolatedAtmosphere.uplooking_column_product() for an "
                "up-looking family, or point atmosphere.interpolated_data_dir "
                "at a down-looking family."
            )
        else:
            action = (
                "Point atmosphere.interpolated_data_dir at an up-looking family "
                "(shipped: midlat_summer_uplooking_ladder), or use "
                "InterpolatedAtmosphere.evaluate() for a down-looking scene."
            )
        raise AtmosphereValidationError(
            f"{where}: this family was built from '{self._family_direction}'-looking "
            f"runs, and this entry point serves '{wanted}'-looking scenes. A "
            "down-looking family's radiance product is the UPWELLING path "
            "radiance; an up-looking family's is the DOWNWELLING one "
            "(L_toward_lower). They are different quantities and are never "
            f"substituted for one another. {action}"
        )

    def _require_uplooking_zenith_is_servable(
        self, zeta_low_rad: float, theta_o_rad: float
    ) -> None:
        """Refuse an up-looking zenith the loaded family cannot represent.

        A family carrying a ``path_zenith_rad`` axis (the batch-2 N zenith fan
        and M column fan) serves any zenith inside its node span, interpolating
        in airmass ``sec(ζ)`` space exactly as the down-looking fans do
        (CU-160); the hull check in :meth:`build_state` is then the only guard
        needed, and this method is a no-op.

        A family *without* that axis is rendered at a single lower-endpoint
        zenith — vertical for the K ladder, 48.2° for the batch-2 P ladder — and
        any other zenith is a different column.  Serving it from the rendered
        one via the sec law would be up to ~2.5 % low in band-mean LWIR τ
        (measured against the K6 45° holdout), so it is refused, not
        approximated (Rule 17).
        """
        if "path_zenith_rad" in self._axes:
            return
        rendered_rad = self._non_axis_recorded.get("path_zenith_rad", 0.0)
        if abs(abs(zeta_low_rad) - rendered_rad) <= _UPLOOKING_FIXED_ZENITH_TOL_RAD:
            return
        if rendered_rad <= _UPLOOKING_FIXED_ZENITH_TOL_RAD:
            rendered = (
                "The loaded up-looking family is a VERTICAL partial-column "
                "ladder — one lower-endpoint zenith only — and it carries no "
                "'path_zenith_rad' axis to interpolate over"
            )
        else:
            rendered = (
                "The loaded up-looking family is rendered at the single "
                f"lower-endpoint zenith {math.degrees(rendered_rad):.4f}° and "
                "carries no 'path_zenith_rad' axis to interpolate over"
            )
        raise AtmosphereValidationError(
            "InterpolatedAtmosphere.uplooking_column_product: the query "
            f"lower-endpoint zenith is {math.degrees(abs(zeta_low_rad)):.4f}° "
            f"(theta_o = {theta_o_rad:.6f} rad; vertical up-looking is "
            f"theta_o = π). {rendered}, so this query cannot be served from it "
            "— mapping it through airmass sec(ζ) space would be up to ~2.5% low "
            "in band-mean LWIR τ (the K6 45° holdout). Point "
            "atmosphere.interpolated_data_dir at an up-looking family that "
            "carries a zenith axis (shipped: midlat_summer_uplooking_zenith_fan "
            "for targets 0-20 km, midlat_summer_sst_column_fan for the full "
            "column to space), or use atmosphere.model='simple', which serves "
            "any up-looking zenith through the segment evaluators."
        )

    @property
    def uplooking_companion(self) -> object | None:
        """Backend serving the illumination and sky legs of an up-looking scene (CU-226)."""
        return self._uplooking_companion

    @property
    def uplooking_target_ceiling_m(self) -> float | None:
        """Highest target altitude this family's own runs measure [m MSL].

        The family's honest answer to "how far up did you integrate?", read off
        the node set rather than off a family name — the two ways a family can
        pin its upper endpoint are both covered:

        * ``target_altitude_m`` **is** an interpolation axis (the K ladder, the
          batch-2 N zenith fan): the ceiling is the top of that axis's hull;
        * it is a recorded **non-axis** field (the batch-2 M column fan and P
          sensor ladder, both rendered at a fixed 100 km upper endpoint): the
          ceiling is that recorded value, which the constructor has already
          validated as constant across the points.

        ``None`` when the family records nothing about its upper endpoint —
        the callers (:meth:`_vacuum_clamped_target_m` and the topology layer's
        exo guard) then take the conservative branch and refuse rather than
        assume a ceiling.

        This is the seam the up-looking topology's exo-target guard keys on:
        a family whose ceiling reaches ``h_atm_top`` measured the entire
        column, so the vacuum identity above it applies (see
        :data:`_VACUUM_EQUIVALENT_ALTITUDE_M`); one whose ceiling is below it
        did not.
        """
        if "target_altitude_m" in self._axes:
            return float(self.coordinate_bounds()["target_altitude_m"][1])
        return self._non_axis_recorded.get("target_altitude_m")

    def _vacuum_clamped_target_m(self, h_tgt_m: float) -> float:
        """Target-altitude coordinate to query for an upper endpoint at *h_tgt_m*.

        The target-axis half of the vacuum-equivalence identity
        (:data:`_VACUUM_EQUIVALENT_ALTITUDE_M`), the mirror of the sensor-axis
        clamp in :meth:`_warn_ignored_geometry`.  For a family whose runs reach
        the top of the modelled atmosphere, a target above that ceiling is
        separated from the ceiling by vacuum — zero extinction, zero emission —
        so the column is *identically* the ceiling node's.  Serving it from the
        ceiling is exact, not an approximation and not an extrapolation.

        The clamp is deliberately gated on the ceiling being at or above
        :data:`_VACUUM_EQUIVALENT_ALTITUDE_M`.  A partial-column family (the
        20 km ladders) gets no clamp: the air between its top rung and the
        query target is real, unmeasured atmosphere, so the query stays out of
        hull and :meth:`build_state` refuses it (Rule 17 — no extrapolation).
        """
        ceiling = self.uplooking_target_ceiling_m
        if ceiling is None or ceiling < _VACUUM_EQUIVALENT_ALTITUDE_M or h_tgt_m <= ceiling:
            return h_tgt_m
        return ceiling

    def coordinate_bounds(self) -> dict[str, tuple[float, float]]:
        """Return the min/max coordinate range for each axis."""
        bounds: dict[str, tuple[float, float]] = {}
        for j, ax in enumerate(self._axes):
            col = self._coords[:, j]
            bounds[ax] = (float(col.min()), float(col.max()))
        return bounds

    # ------------------------------------------------------------------
    # Factory constructors
    # ------------------------------------------------------------------

    @classmethod
    def from_states(
        cls,
        states: Sequence[AtmosphericState],
        geometries: Sequence[dict[str, float]],
        axes: Sequence[str],
        method: str = "linear",
    ) -> InterpolatedAtmosphere:
        """Build from a sequence of AtmosphericState objects.

        Parameters
        ----------
        states:
            Pre-computed atmospheric states.
        geometries:
            Corresponding geometry coordinates as dicts, e.g.
            ``[{"path_zenith_rad": 0.0}, {"path_zenith_rad": 0.5}]``.
        axes:
            Which geometry fields to interpolate over.
        method:
            Interpolation method.
        """
        if len(states) != len(geometries):
            raise AtmosphereValidationError(
                f"InterpolatedAtmosphere.from_states: len(states)={len(states)} "
                f"!= len(geometries)={len(geometries)}."
            )

        points = [
            GeometryPoint(
                coordinates=dict(g),
                transmittance=s.transmittance,
                path_radiance=s.path_radiance,
                atm_emission_down=s.atm_emission_down,
            )
            for s, g in zip(states, geometries, strict=False)
        ]
        return cls(points, axes, method)

    # ------------------------------------------------------------------
    # Atmosphere protocol
    # ------------------------------------------------------------------

    def build_state(
        self,
        wavelength_um: np.ndarray,
        geometry: AtmosphericGeometry,
    ) -> AtmosphericState:
        """Interpolate the atmospheric state at the query geometry.

        Parameters
        ----------
        wavelength_um:
            Query wavelength grid.  May differ from the stored points'
            grid as long as it lies inside their spectral range: the
            geometry-interpolated spectra are then resampled onto the
            query grid (CU-156, the same ``SpectralData.resample``
            pattern ``TabulatedAtmosphere`` uses) — transmittance in
            log-tau, radiances linearly (CU-306).  A query extending
            outside the stored range fails loud — extrapolation is
            never performed.
        geometry:
            The query geometry.  Coordinates for each interpolation
            axis are extracted automatically.

        Raises
        ------
        ValueError
            If the query geometry is outside the bounds of the
            available data (no extrapolation), or the query wavelength
            grid extends outside the stored spectral range.
        """
        lam = np.asarray(wavelength_um, dtype=np.float64)
        resample_needed = not np.array_equal(lam, self._wavelength_um)

        # Extract query coordinates.
        query_coords = np.array(
            [_extract_geometry_coord(geometry, ax) for ax in self._axes],
            dtype=np.float64,
        )

        # CU-167: a query value on a NON-axis field cannot influence the
        # result — it is served with the stored runs' geometry. Warn loud
        # when the query meaningfully departs from the recorded (or, for
        # LOS zenith, assumed-nadir) run value instead of silently
        # substituting e.g. the nadir column for a 45° slant path.
        self._warn_ignored_geometry(geometry)

        # Bounds check with actionable error.
        bounds = self.coordinate_bounds()
        for j, ax in enumerate(self._axes):
            lo, hi = bounds[ax]
            val = query_coords[j]
            if val < lo - 1e-12 or val > hi + 1e-12:
                raise AtmosphereValidationError(
                    f"InterpolatedAtmosphere: query {ax}={val:.6g} is "
                    f"outside the available range [{lo:.6g}, {hi:.6g}]. "
                    "Interpolation does not extrapolate. Add more "
                    "pre-computed runs covering this geometry, or clamp "
                    "the query to the available range."
                )

        # Interpolate — query mapped to interpolation space per axis
        # (airmass sec(θ) for zenith axes, identity otherwise; CU-160).
        query_interp = np.array(
            [
                float(np.asarray(_axis_to_interp_space(ax, query_coords[j])))
                for j, ax in enumerate(self._axes)
            ],
            dtype=np.float64,
        )
        query_point = query_interp.reshape(1, -1)

        if self._grid_type == "regular":
            log_tau_interp = self._interp_log_tau(query_point)[0]
            lpath_interp = self._interp_lpath(query_point)[0]
            ldown_interp = self._interp_ldown(query_point)[0]
        else:
            log_tau_interp = self._interp_log_tau(query_point)[0]
            lpath_interp = self._interp_lpath(query_point)[0]
            ldown_interp = self._interp_ldown(query_point)[0]

            # LinearNDInterpolator returns NaN outside the convex hull.
            if np.any(np.isnan(log_tau_interp)):
                raise AtmosphereValidationError(
                    "InterpolatedAtmosphere: query geometry is outside the "
                    "convex hull of available data points. Interpolation "
                    "does not extrapolate. Available bounds per axis: "
                    + ", ".join(
                        f"{ax}=[{bounds[ax][0]:.6g}, {bounds[ax][1]:.6g}]" for ax in self._axes
                    )
                )

        # Clamp radiance to non-negative.
        lpath_interp = np.maximum(lpath_interp, 0.0)
        ldown_interp = np.maximum(ldown_interp, 0.0)

        if resample_needed:
            # CU-156: geometry interpolation ran on the stored grid; serve any
            # query grid inside the stored spectral range by resampling (the
            # TabulatedAtmosphere pattern). resample() fails loud on a query
            # outside the stored range — no spectral extrapolation.
            #
            # CU-306: τ is resampled in **log-τ**, the same space the geometry
            # interpolation runs in. Both operations are then linear in optical
            # depth, so they commute and the answer no longer depends on their
            # order; resampling linearly in τ instead cost up to ~2% relative
            # τ error at off-node query wavelengths. Radiances stay LINEAR —
            # L_path and L_atm_down are additive emission terms with no
            # Beer-Lambert exponential in path length, so log-resampling them
            # would have no physical basis.
            #
            # τ = 0 / underflow: the constructor already floors stored τ at
            # TAU_FLOOR (1e-30 ≡ OD ≈ 69) before taking the log, so log_tau is
            # finite everywhere by construction — an opaque band resamples as
            # that floor, never as -inf, and exp() can return neither NaN nor
            # inf. Values above the floor are carried through untouched.
            target = SpectralGrid(wavelengths_um=lam)

            def _to_query_grid(name: str, values: np.ndarray, unit: str) -> np.ndarray:
                source = SpectralData(
                    name=name,
                    wavelength_um=self._wavelength_um,
                    values=values,
                    unit=unit,
                    source="InterpolatedAtmosphere (stored-grid intermediate)",
                )
                return np.asarray(source.resample(target).values, dtype=np.float64)

            log_tau_interp = _to_query_grid(
                "atm.log_transmittance.interpolated", log_tau_interp, ""
            )
            lpath_interp = _to_query_grid(
                "atm.path_radiance.interpolated", lpath_interp, "W/m²/sr/µm"
            )
            ldown_interp = _to_query_grid(
                "atm.emission_down.interpolated", ldown_interp, "W/m²/sr/µm"
            )

        # Convert log-tau back to tau, on whichever grid it now lives on.
        tau_interp = np.exp(log_tau_interp)
        tau_interp = np.clip(tau_interp, 0.0, 1.0)

        provenance: dict[str, Any] = {
            "model": "interpolated",
            "grid_type": self._grid_type,
            "n_points": self.n_points,
            "axes": self._axes,
            "query": {ax: float(query_coords[j]) for j, ax in enumerate(self._axes)},
        }

        return AtmosphericState(
            transmittance=SpectralData(
                name="atm.transmittance.interpolated",
                wavelength_um=lam,
                values=tau_interp,
                unit="",
                source="InterpolatedAtmosphere (log-tau interpolation)",
                source_parameters=provenance,
            ),
            path_radiance=SpectralData(
                name="atm.path_radiance.interpolated",
                wavelength_um=lam,
                values=lpath_interp,
                unit="W/m²/sr/µm",
                source="InterpolatedAtmosphere (linear interpolation)",
                source_parameters=provenance,
            ),
            atm_emission_down=SpectralData(
                name="atm.emission_down.interpolated",
                wavelength_um=lam,
                values=ldown_interp,
                unit="W/m²/sr/µm",
                source="InterpolatedAtmosphere (linear interpolation)",
                source_parameters=provenance,
            ),
            geometry=geometry,
            derivation_chain=(
                f"InterpolatedAtmosphere({self._grid_type}, n={self.n_points}, axes={self._axes})",
                "tau interpolated in log-space (optical depth); "
                "zenith axes in airmass sec(θ) space (CU-160)",
                "tau resampled onto the query wavelength grid in log-space too, "
                "so the two operations commute (CU-306)",
                "L_path, L_atm_down interpolated and resampled linearly",
            ),
        )

    def uplooking_column_product(
        self,
        wavelength_um: np.ndarray,
        los: LineOfSightGeometry,
    ) -> UplookingColumnProduct:
        """Interpolate the up-looking observer-leg column segment for *los*.

        The segment is the sensor→target column of an up-looking scene.  Per
        ADR-0011 decision 3 it is keyed to its **lower** endpoint — which for
        an up-looking LOS is the *sensor* — so the family's
        ``target_altitude_m`` axis is the segment's upper endpoint and its
        recorded ``path_zenith_rad`` is the lower-endpoint zenith
        ``ζ_low = π − θ_o``.  (That is the same meaning ``path_zenith_rad``
        already carries in every down-looking family, where the lower endpoint
        is the target and ``θ_o`` is target-referenced — one convention, not
        two.)

        Interpolation conventions are the family-wide ones: τ in log-τ
        (optical-depth) space, radiance linearly, the zenith axis (when the
        family carries one) in airmass ``sec(ζ)`` space (CU-160), no
        extrapolation outside the hull, and a query wavelength grid inside the
        stored spectral range resampled by :meth:`build_state`.

        The one query that reaches past the family's top rung and is still
        served is an **exo target above a full-column family**: see
        :meth:`_vacuum_clamped_target_m`.  That is the vacuum-equivalence
        identity, not an extrapolation, and it is recorded in the returned
        provenance under ``exo_target_vacuum_clamp``.

        Parameters
        ----------
        wavelength_um:
            Query wavelength grid [µm].
        los:
            The line of sight.  ``h_sensor`` supplies the segment's lower
            endpoint and ``h_tgt`` its upper one — read from the LOS contract,
            never from parameters (guardrail G2).

        Raises
        ------
        AtmosphereValidationError
            If the family is not up-looking; if *los* is not up-looking; if the
            query zenith is not one the family can represent (a family with no
            ``path_zenith_rad`` axis serves only its single rendered zenith —
            see :meth:`_require_uplooking_zenith_is_servable`); if the LOS
            carries no ``h_sensor``; or if ``h_sensor`` departs from the
            family's rendered lower endpoint.
        """
        self._require_family_direction("up", "InterpolatedAtmosphere.uplooking_column_product")

        if los.los_direction != "up":
            raise AtmosphereValidationError(
                "InterpolatedAtmosphere.uplooking_column_product: the line of "
                f"sight is '{los.los_direction}'-looking (h_sensor="
                f"{los.h_sensor}, h_tgt={los.h_tgt} m), and this entry point "
                "serves up-looking scenes only. Use evaluate() for a "
                "down-looking scene, or the level-arm segment evaluator for a "
                "constant-altitude path."
            )

        h_sensor_m = require_sensor_altitude_m(
            los, "InterpolatedAtmosphere.uplooking_column_product"
        )

        # ζ_low = π − θ_o: the zenith of the up-going ray at the sensor, which
        # is the segment's lower endpoint.
        zeta_low_rad = math.pi - float(los.theta_o)
        self._require_uplooking_zenith_is_servable(zeta_low_rad, float(los.theta_o))

        # The family is rendered at ONE lower endpoint (the K ladder: ground).
        # Serving a different one would silently swap in a different column —
        # the bottom 100 m alone hold ~8% of the aerosol column (H_aer =
        # 1.2 km) and ~5% of the water column (H_H2O = 2 km), so this is a
        # refusal, not a warning.
        rendered_sensor_m = self._non_axis_recorded.get("sensor_altitude_m")
        if (
            rendered_sensor_m is not None
            and abs(h_sensor_m - rendered_sensor_m) > _NON_AXIS_LENGTH_TOL_M
        ):
            raise AtmosphereValidationError(
                "InterpolatedAtmosphere.uplooking_column_product: query "
                f"h_sensor = {h_sensor_m:.6g} m does not match the family's "
                f"rendered lower endpoint {rendered_sensor_m:.6g} m (tolerance "
                f"{_NON_AXIS_LENGTH_TOL_M:g} m). The runs integrate the column "
                "from THAT altitude upward; starting somewhere else is a "
                "different column, and near the ground the difference is large "
                "(the lowest 100 m carry ~8% of the aerosol column). Add "
                "'sensor_altitude_m' to atmosphere.interpolation_axes with a "
                "run family covering it, or use atmosphere.model='simple'."
            )

        # Target-axis vacuum equivalence (:data:`_VACUUM_EQUIVALENT_ALTITUDE_M`).
        # A full-column family measured up to the top of the atmosphere; the
        # path from there to an exo target is vacuum, so the ceiling node IS
        # the answer. A partial-column family is left alone and the query falls
        # out of hull below.
        target_query_m = self._vacuum_clamped_target_m(float(los.h_tgt))

        query_geometry = AtmosphericGeometry(
            sensor_altitude_m=h_sensor_m,
            target_altitude_m=target_query_m,
            path_zenith_rad=abs(zeta_low_rad),
            solar_zenith_rad=(
                float(los.theta_s)
                if los.theta_s is not None
                else self._non_axis_recorded.get("solar_zenith_rad", 0.0)
            ),
            solar_azimuth_rad=(
                float(los.delta_phi)
                if los.delta_phi is not None
                else self._non_axis_recorded.get("solar_azimuth_rad", 0.0)
            ),
        )
        state = self.build_state(wavelength_um, query_geometry)

        provenance: dict[str, Any] = {
            "model": "interpolated",
            "family_direction": "up",
            "segment_kind": "column",
            "h_low_m": h_sensor_m,
            "h_high_m": float(los.h_tgt),
            "zeta_low_rad": abs(zeta_low_rad),
            "axes": list(self._axes),
            "grid_type": self._grid_type,
            "n_points": self.n_points,
            "radiance_product": "L_toward_lower",
            "target_ceiling_m": self.uplooking_target_ceiling_m,
            "target_altitude_served_m": target_query_m,
        }
        if target_query_m != float(los.h_tgt):
            provenance["exo_target_vacuum_clamp"] = (
                f"target at {float(los.h_tgt):.0f} m is above this family's measured "
                f"column top {target_query_m:.0f} m; the intervening path is vacuum, so "
                "the top-of-column run IS the answer (exact identity, not extrapolation)"
            )
        return UplookingColumnProduct(
            wavelength_um=np.asarray(state.transmittance.wavelength_um, dtype=np.float64),
            tau=np.asarray(state.transmittance.values, dtype=np.float64),
            L_toward_lower=np.asarray(state.path_radiance.values, dtype=np.float64),
            provenance=provenance,
        )

    def evaluate(
        self,
        wavelength_um: np.ndarray,
        los: LineOfSightGeometry,
        params: ParameterSet,
    ) -> AtmosphericQuantities:
        """Thin adapter over the interpolator's 3-field legacy output.

        Same sun-leg degradation contract as
        :meth:`TabulatedAtmosphere.evaluate`: there is no independent
        sun-leg data set, so τ_sun aliases τ_up with a ``UserWarning``,
        with E_TOA drawn from ``radiant.core.solar`` and
        E_sky_thermal = π · L_atm_down.

        Airborne targets (Gap 94): when the sample grid carries a
        ``target_altitude_m`` axis (e.g. the shipped
        ``data/atmospheres/midlat_summer_ladders/`` family), ``h_tgt > 0``
        is served with the real two-leg up/full split from two
        interpolator queries at the same sensor/zenith coordinates:

        - up leg (τ_up, L_path_up): query at ``target_altitude_m = h_tgt``
          — the target→sensor partial column;
        - full column (τ_full_up, L_path_full): query at
          ``target_altitude_m = 0`` — the ground→sensor column the
          background branch needs.

        L_atm_down (→ E_sky_thermal) is taken from the up-leg query — the
        downwelling at the target is what illuminates it.  A query
        outside the grid's target-altitude hull fails with the
        interpolator's no-extrapolation error (e.g. the shipped ladders
        cover 0–29 km; a 90 km target is refused, not extrapolated).

        Without a ``target_altitude_m`` axis, ``h_tgt > 0`` raises
        :class:`NotImplementedError` — a single-column grid cannot
        supply both legs.
        """
        import warnings

        self._require_family_direction("down", "InterpolatedAtmosphere.evaluate")

        has_target_axis = "target_altitude_m" in self._axes
        if los.h_tgt > 0.0 and not has_target_axis:
            raise AtmosphereCapabilityError(
                what=(
                    f"InterpolatedAtmosphere.evaluate: h_tgt = {los.h_tgt} m > 0 "
                    "needs a 'target_altitude_m' interpolation axis, and this "
                    f"grid interpolates only over {self._axes}"
                ),
                why=(
                    "The grid holds the full (h_tgt = 0) column, and one column "
                    "cannot supply both the target→sensor leg (tau_up) and the "
                    "ground→sensor full column (tau_full_up) the background "
                    "branch needs (Gap 94)."
                ),
                action=(
                    "Point atmosphere.interpolated_data_dir at a grid with a "
                    "target-altitude axis (e.g. the shipped "
                    "midlat_summer_ladders/ family, 0–29 km) and add "
                    "'target_altitude_m' to atmosphere.interpolation_axes, or "
                    "use SimpleAtmosphere."
                ),
                context={"h_tgt_m": float(los.h_tgt), "axes": tuple(self._axes)},
            )

        # Build legacy AtmosphericGeometry queries to reuse the
        # interpolator's coordinate-extraction logic.  h_sensor comes from
        # the LOS contract (ADR-0011; guardrail G2 — no params side-load).
        # A pure-thermal scene carries theta_s/delta_phi =
        # None ("no solar geometry declared") — that cannot conflict with
        # the sample runs' recorded sun position, so None adopts the
        # recorded value (no CU-167 mismatch warning) rather than a
        # literal 0.0 that would spuriously differ from it.  An
        # explicitly set solar geometry is still compared and warned.
        h_sensor_m = require_sensor_altitude_m(los, "InterpolatedAtmosphere.evaluate")
        theta_s = (
            float(los.theta_s)
            if los.theta_s is not None
            else self._non_axis_recorded.get("solar_zenith_rad", 0.0)
        )
        delta_phi = (
            float(los.delta_phi)
            if los.delta_phi is not None
            else self._non_axis_recorded.get("solar_azimuth_rad", 0.0)
        )

        def _query_geometry(target_altitude_m: float) -> AtmosphericGeometry:
            return AtmosphericGeometry(
                sensor_altitude_m=h_sensor_m,
                target_altitude_m=target_altitude_m,
                path_zenith_rad=los.theta_o,
                solar_zenith_rad=theta_s,
                solar_azimuth_rad=delta_phi,
            )

        full_state = self.build_state(wavelength_um, _query_geometry(0.0))
        up_state = (
            self.build_state(wavelength_um, _query_geometry(float(los.h_tgt)))
            if los.h_tgt > 0.0
            else full_state
        )
        lam = full_state.wavelength_um

        warnings.warn(
            (
                "InterpolatedAtmosphere.evaluate: backend does not carry the "
                "Option C two-leg split for the sun leg — collapsing τ_sun "
                "onto the up-leg transmittance (τ_sun=τ_up; for a surface "
                "target also τ_up=τ_full_up and L_path_up=L_path_full, the "
                "single interpolated column)."
            ),
            UserWarning,
            stacklevel=2,
        )

        tau_up = np.asarray(up_state.transmittance.values, dtype=np.float64)
        tau_full = np.asarray(full_state.transmittance.values, dtype=np.float64)
        lpath_up = np.asarray(up_state.path_radiance.values, dtype=np.float64)
        lpath_full = np.asarray(full_state.path_radiance.values, dtype=np.float64)
        ldown = np.asarray(up_state.atm_emission_down.values, dtype=np.float64)

        E_TOA = np.asarray(toa_solar_spectral_irradiance(lam), dtype=np.float64)
        E_sky_thermal = np.maximum(np.pi * ldown, 0.0)
        E_sky_scattered = np.zeros_like(lam)

        return AtmosphericQuantities(
            wavelength_um=lam,
            tau_sun=tau_up.copy(),
            tau_up=tau_up.copy(),
            tau_full_up=tau_full.copy(),
            E_TOA=E_TOA,
            E_sky_scattered=E_sky_scattered,
            E_sky_thermal=E_sky_thermal,
            L_path_up=lpath_up.copy(),
            L_path_full=lpath_full.copy(),
        )
