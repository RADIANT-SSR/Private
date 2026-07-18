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
  interpolated linearly.  These are additive quantities with no
  multiplicative structure that would benefit from log-space.

- **No extrapolation**: query geometries outside the convex hull of
  available points always raise ``ValueError``.  We never silently
  invent atmospheric data beyond the calibration range.

Grid detection
--------------
If the available geometry points form a structured rectangular grid
(Cartesian product of unique values per axis), the constructor uses
``scipy.interpolate.RegularGridInterpolator`` for efficiency.
Otherwise it falls back to ``scipy.interpolate.LinearNDInterpolator``
for scattered data.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np
from scipy.interpolate import LinearNDInterpolator, RegularGridInterpolator

from radiant.atmosphere._quantities import AtmosphericQuantities
from radiant.atmosphere.errors import AtmosphereValidationError
from radiant.atmosphere.protocol import (
    AtmosphericGeometry,
    AtmosphericState,
)
from radiant.core.los_geometry import LineOfSightGeometry
from radiant.core.parameters import ParameterSet
from radiant.core.solar import toa_solar_spectral_irradiance
from radiant.core.spectral import SpectralData, SpectralGrid

logger = logging.getLogger(__name__)

# Minimum transmittance value before taking log, to avoid log(0) = -inf.
# 1e-30 corresponds to OD ~ 69, well beyond any realistic atmosphere.
TAU_FLOOR: float = 1e-30

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

# CU-164: a query field that is NOT an interpolation axis is served with the
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
    """

    def __init__(
        self,
        points: Sequence[GeometryPoint],
        axes: Sequence[str],
        method: str = "linear",
    ) -> None:
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

        # CU-164: record the fixed value of any non-axis geometry field the
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
                    "interpolator would silently ignore (CU-164). Add the field "
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
        """CU-164: warn when a non-axis query field departs from the stored runs.

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
            tol = _NON_AXIS_ANGLE_TOL_RAD if field in _ANGLE_FIELDS else _NON_AXIS_LENGTH_TOL_M
            if abs(query_val - reference) > tol:
                origin = "recorded" if field in self._non_axis_recorded else "assumed"
                warnings.warn(
                    (
                        f"InterpolatedAtmosphere: query {field} = {query_val:.6g} "
                        f"is IGNORED — '{field}' is not an interpolation axis "
                        f"(axes={self._axes}), so the result carries the sample "
                        f"runs' {origin} value {reference:.6g} instead (CU-164). "
                        "Add runs covering this dimension and include "
                        f"'{field}' in atmosphere.interpolation_axes, or accept "
                        "the stored geometry's physics."
                    ),
                    UserWarning,
                    stacklevel=3,
                )

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
            geometry-interpolated spectra are then linearly resampled
            onto the query grid (CU-156, the same
            ``SpectralData.resample`` pattern ``TabulatedAtmosphere``
            uses).  A query extending outside the stored range fails
            loud — extrapolation is never performed.
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

        # CU-164: a query value on a NON-axis field cannot influence the
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

        # Convert log-tau back to tau.
        tau_interp = np.exp(log_tau_interp)
        tau_interp = np.clip(tau_interp, 0.0, 1.0)

        # Clamp radiance to non-negative.
        lpath_interp = np.maximum(lpath_interp, 0.0)
        ldown_interp = np.maximum(ldown_interp, 0.0)

        if resample_needed:
            # CU-156: geometry interpolation ran on the stored grid; serve any
            # query grid inside the stored spectral range by linear resampling
            # (the TabulatedAtmosphere pattern). resample() fails loud on a
            # query outside the stored range — no spectral extrapolation.
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

            tau_interp = _to_query_grid("atm.transmittance.interpolated", tau_interp, "")
            lpath_interp = _to_query_grid(
                "atm.path_radiance.interpolated", lpath_interp, "W/m²/sr/µm"
            )
            ldown_interp = _to_query_grid(
                "atm.emission_down.interpolated", ldown_interp, "W/m²/sr/µm"
            )

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
                "L_path, L_atm_down interpolated linearly",
            ),
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

        has_target_axis = "target_altitude_m" in self._axes
        if los.h_tgt > 0.0 and not has_target_axis:
            raise NotImplementedError(
                f"InterpolatedAtmosphere.evaluate: h_tgt = {los.h_tgt} m > 0 "
                "needs a 'target_altitude_m' interpolation axis, and this "
                f"grid interpolates only over {self._axes} for the full "
                "(h_tgt = 0) column — one column cannot supply both the "
                "target→sensor leg (tau_up) and the ground→sensor full "
                "column (tau_full_up) the background branch needs (Gap 94). "
                "Workaround: point atmosphere.interpolated_data_dir at a "
                "grid with a target-altitude axis (e.g. the shipped "
                "data/atmospheres/midlat_summer_ladders/ family, 0–29 km) "
                "and add 'target_altitude_m' to "
                "atmosphere.interpolation_axes, or use SimpleAtmosphere."
            )

        # Build legacy AtmosphericGeometry queries to reuse the
        # interpolator's coordinate-extraction logic.  h_sensor comes
        # from params.
        h_sensor_m = float(params.get("geometry.sensor_altitude_m"))
        theta_s = float(los.theta_s) if los.theta_s is not None else 0.0
        delta_phi = float(los.delta_phi) if los.delta_phi is not None else 0.0

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
