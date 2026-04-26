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
from radiant.atmosphere.protocol import (
    AtmosphericGeometry,
    AtmosphericState,
)
from radiant.core.los_geometry import LineOfSightGeometry
from radiant.core.parameters import ParameterSet
from radiant.core.solar import toa_solar_spectral_irradiance
from radiant.core.spectral import SpectralData

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


def _extract_geometry_coord(geometry: AtmosphericGeometry, axis: str) -> float:
    """Extract a named coordinate from an AtmosphericGeometry."""
    if axis not in _GEOMETRY_FIELDS:
        raise ValueError(
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
            raise ValueError(
                f"InterpolatedAtmosphere: at least 2 geometry points required, got {len(points)}."
            )
        if not axes:
            raise ValueError("InterpolatedAtmosphere: at least one interpolation axis required.")
        for ax in axes:
            if ax not in _GEOMETRY_FIELDS:
                raise ValueError(
                    f"InterpolatedAtmosphere: axis '{ax}' is not a valid "
                    f"geometry field. Choose from {sorted(_GEOMETRY_FIELDS)}."
                )
        if method not in ("linear", "nearest"):
            raise ValueError(
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
                    raise ValueError(
                        f"InterpolatedAtmosphere: point {i} is missing "
                        f"coordinate for axis '{ax}'. Available: "
                        f"{sorted(pt.coordinates)}."
                    )

        # Validate: all points share the same wavelength grid.
        ref_wl = points[0].transmittance.wavelength_um
        for i, pt in enumerate(points[1:], start=1):
            if not np.array_equal(ref_wl, pt.transmittance.wavelength_um):
                raise ValueError(
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

        self._coords = coords

        # Detect structured vs scattered grid.
        is_struct, unique_per_axis = _is_structured_grid(coords, len(self._axes))

        if is_struct and len(self._axes) >= 1:
            self._grid_type = "regular"
            self._unique_per_axis = unique_per_axis

            # Reshape values to grid shape + n_wl for RegularGridInterpolator.
            grid_shape = tuple(len(u) for u in unique_per_axis)

            # Build a mapping from coordinate tuple -> point index.
            coord_to_idx: dict[tuple[float, ...], int] = {}
            for i in range(n_pts):
                key = tuple(float(coords[i, j]) for j in range(len(self._axes)))
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
            # LinearNDInterpolator for unstructured data.
            self._interp_log_tau = LinearNDInterpolator(coords, log_tau)
            self._interp_lpath = LinearNDInterpolator(coords, lpath)
            self._interp_ldown = LinearNDInterpolator(coords, ldown)

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
            raise ValueError(
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
            Query wavelength grid.  Must match the grid of the
            pre-computed points (resampling is not supported here —
            resample the source data before constructing the
            interpolator).
        geometry:
            The query geometry.  Coordinates for each interpolation
            axis are extracted automatically.

        Raises
        ------
        ValueError
            If the query geometry is outside the bounds of the
            available data (no extrapolation).
        """
        lam = np.asarray(wavelength_um, dtype=np.float64)

        if not np.array_equal(lam, self._wavelength_um):
            raise ValueError(
                "InterpolatedAtmosphere: query wavelength grid does not "
                "match the grid of the pre-computed points. Resample the "
                "source data before constructing the interpolator, or "
                "query on the same grid."
            )

        # Extract query coordinates.
        query_coords = np.array(
            [_extract_geometry_coord(geometry, ax) for ax in self._axes],
            dtype=np.float64,
        )

        # Bounds check with actionable error.
        bounds = self.coordinate_bounds()
        for j, ax in enumerate(self._axes):
            lo, hi = bounds[ax]
            val = query_coords[j]
            if val < lo - 1e-12 or val > hi + 1e-12:
                raise ValueError(
                    f"InterpolatedAtmosphere: query {ax}={val:.6g} is "
                    f"outside the available range [{lo:.6g}, {hi:.6g}]. "
                    "Interpolation does not extrapolate. Add more "
                    "pre-computed runs covering this geometry, or clamp "
                    "the query to the available range."
                )

        # Interpolate.
        query_point = query_coords.reshape(1, -1)

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
                raise ValueError(
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
                "tau interpolated in log-space (optical depth)",
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

        Same degradation contract as :meth:`TabulatedAtmosphere.evaluate`:
        τ_sun = τ_up = τ_full_up and L_path_up = L_path_full are
        interpolated from the legacy three-field data set, with E_TOA
        drawn from ``radiant.core.solar`` and E_sky_thermal = π · L_atm_down.

        v1 limitation: ``h_tgt > 0`` raises :class:`NotImplementedError`.
        """
        import warnings

        if los.h_tgt > 0.0:
            raise NotImplementedError(
                f"InterpolatedAtmosphere.evaluate: h_tgt = {los.h_tgt} m > 0 "
                "is not supported — the interpolator's sample grid records "
                "only sensor-altitude / zenith-angle axes for the full "
                "(h_tgt = 0) column, and there is no species-resolved "
                "profile to rescale to a partial column.  See Option C "
                "Stage 5 §8.3 open question 'partial-column rescaling for "
                "tabulated/interpolated backends'.  Workaround: use "
                "SimpleAtmosphere or extend the interpolator sample grid "
                "to include h_tgt."
            )

        # Build a legacy AtmosphericGeometry to reuse the interpolator's
        # coordinate-extraction logic.  h_sensor comes from params.
        h_sensor_m = float(params.get("geometry.sensor_altitude_m"))
        theta_s = float(los.theta_s) if los.theta_s is not None else 0.0
        delta_phi = float(los.delta_phi) if los.delta_phi is not None else 0.0
        geometry = AtmosphericGeometry(
            sensor_altitude_m=h_sensor_m,
            target_altitude_m=0.0,
            path_zenith_rad=los.theta_o,
            solar_zenith_rad=theta_s,
            solar_azimuth_rad=delta_phi,
        )
        atm_state = self.build_state(wavelength_um, geometry)
        lam = atm_state.wavelength_um

        warnings.warn(
            (
                "InterpolatedAtmosphere.evaluate: backend does not carry the "
                "Option C two-leg split — collapsing τ_sun=τ_up=τ_full_up and "
                "L_path_up=L_path_full to the single interpolated value."
            ),
            UserWarning,
            stacklevel=2,
        )

        tau = np.asarray(atm_state.transmittance.values, dtype=np.float64)
        lpath = np.asarray(atm_state.path_radiance.values, dtype=np.float64)
        ldown = np.asarray(atm_state.atm_emission_down.values, dtype=np.float64)

        E_TOA = np.asarray(toa_solar_spectral_irradiance(lam), dtype=np.float64)
        E_sky_thermal = np.maximum(np.pi * ldown, 0.0)
        E_sky_scattered = np.zeros_like(lam)

        return AtmosphericQuantities(
            wavelength_um=lam,
            tau_sun=tau,
            tau_up=tau.copy(),
            tau_full_up=tau.copy(),
            E_TOA=E_TOA,
            E_sky_scattered=E_sky_scattered,
            E_sky_thermal=E_sky_thermal,
            L_path_up=lpath,
            L_path_full=lpath.copy(),
        )
