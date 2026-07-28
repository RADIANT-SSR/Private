"""Resolved target reflectance ρ(λ) on a wavelength grid — the single resolver.

Two consumers need the *same* ρ(λ) a target descriptor implies:

* :mod:`radiant.atmosphere.assembly`, which multiplies it against the solar
  and sky irradiance to build the reflected radiance terms of the §6.1
  at-aperture equation, and
* :class:`radiant.source.stage.SourceStage`, which publishes it as a stage
  output so the GUI's reflective view can plot the surface property the
  analyst actually typed (owner walkthrough item 6).

Per Rule 19 there is exactly one resolver, and it lives here (``radiant.core``)
rather than in either stage, because Rule 11 forbids the cross-stage import
that sharing it from a stage would require.

Two pathways carry a reflectance, and both resolve onto the caller's grid:

===================  ===============================================
Descriptor           ρ(λ)
===================  ===============================================
``T2Reflective``     ``rho.reflectance_at(λ, view, illum)`` — the
                     :class:`~radiant.core.reflectance.ReflectanceDescriptor`
                     protocol (scalar-Lambertian adapter, or a BRDF)
``T3Mixed``          ``1 − ε(λ)`` — Kirchhoff (Rule 5); the user supplies
                     ε and never ρ independently
everything else      ``None`` — T1 (ρ ≡ 0 by construction), T5/T6/T7
                     (user-supplied radiance/intensity, no surface
                     property to report)
===================  ===============================================

ρ is dimensionless in ``[0, 1]`` throughout; no unit conversion occurs here
(Rule 2).
"""

from __future__ import annotations

import numpy as np
import numpy.typing as npt

from radiant.core.descriptors import T2Reflective, T3Mixed, TargetDescriptor
from radiant.core.los_geometry import LineOfSightGeometry
from radiant.core.parameters import ParameterBoundsError
from radiant.core.reflectance import ReflectanceDescriptor

# Formal placeholder direction for the callers that have no LOS (a hand-built
# descriptor outside the chain) and for a scenario with no sun at all: the
# Lambertian adapter ignores both vectors, and every arm that would consume an
# illumination direction is already zeroed by cos(θ_s) = 0.
_ZERO_VEC3: npt.NDArray[np.float64] = np.zeros(3, dtype=np.float64)
_NO_ILLUMINATION: npt.NDArray[np.float64] = _ZERO_VEC3


def _view_illum_from_los(
    los: LineOfSightGeometry,
) -> tuple[npt.NDArray[np.float64], npt.NDArray[np.float64]]:
    """Unit vectors (view_dir, illum_dir) at the target surface from LOS.

    Frame convention — local surface tangent plane at the target:
      * +Z = outward surface normal (local vertical)
      * +X = azimuth reference (``φ = 0``); observer azimuth is aligned
        with it so ``phi_o ≡ 0``
      * +Y = right-hand complement (``+Z × +X``)

    With ``phi_o ≡ 0`` and ``phi_s = delta_phi`` (``delta_phi`` is
    ``φ_s − φ_o`` per :class:`LineOfSightGeometry`), the direction from
    the target toward the sensor is::

        view_dir = (sin θ_o, 0, cos θ_o)

    and the direction from the target toward the sun is::

        illum_dir = (sin θ_s cos δφ, sin θ_s sin δφ, cos θ_s)

    Both are unit vectors by construction (``sin²+cos² = 1``).

    When ``theta_s`` is None the scenario has no solar term (pure-thermal
    or dark-cal lab_test); assembly already skips the direct-solar
    branch, so the descriptor receives ``_NO_ILLUMINATION`` (the zero
    vector) as a formal placeholder.
    """
    view_dir = np.asarray(
        [
            np.sin(los.theta_o),
            0.0,
            np.cos(los.theta_o),
        ],
        dtype=np.float64,
    )

    if los.theta_s is None:
        return view_dir, _NO_ILLUMINATION

    delta_phi = 0.0 if los.delta_phi is None else float(los.delta_phi)
    sin_ts = np.sin(los.theta_s)
    illum_dir = np.asarray(
        [
            sin_ts * np.cos(delta_phi),
            sin_ts * np.sin(delta_phi),
            np.cos(los.theta_s),
        ],
        dtype=np.float64,
    )
    return view_dir, illum_dir


def resolve_reflectance_on_grid(
    rho: ReflectanceDescriptor,
    wavelength_um: npt.NDArray[np.float64],
    los: LineOfSightGeometry | None,
) -> npt.NDArray[np.float64]:
    """Resolve a :class:`ReflectanceDescriptor` onto *wavelength_um*.

    Gap H closes the Phase 6 stub framing: ``T2Reflective.rho`` is a
    :class:`ReflectanceDescriptor` after construction, so callers exercise
    the ``reflectance_at(λ, view, illum)`` protocol rather than reaching
    into the adapter's stored :class:`SpectralData`.  ``los`` provides the
    observer / solar zenith and relative azimuth from which the unit
    vectors are built via :func:`_view_illum_from_los`; the Lambertian
    adapter ignores the directions, but anisotropic BRDFs that land on
    this protocol in the future will consume them.

    ``los=None`` is accepted for the case where a caller hand-assembles a
    :class:`T2Reflective` outside the dispatcher; the protocol call falls
    back to zero vectors.

    Raises
    ------
    ParameterBoundsError
        If the implementation returns a shape other than the requested grid.
    """
    if los is None:
        view_dir = _ZERO_VEC3
        illum_dir = _ZERO_VEC3
    else:
        view_dir, illum_dir = _view_illum_from_los(los)
    grid = np.asarray(wavelength_um, dtype=np.float64)
    vals = rho.reflectance_at(grid, view_dir, illum_dir)
    if vals.shape != grid.shape:
        raise ParameterBoundsError(
            what=(f"ReflectanceDescriptor.reflectance_at returned shape {vals.shape}"),
            why="Callers require ρ(λ) sampled on the requested wavelength grid.",
            action=(
                "Ensure the ReflectanceDescriptor implementation resamples to "
                "the input wavelength grid."
            ),
            context={
                "expected_shape": grid.shape,
                "actual_shape": vals.shape,
            },
        )
    return np.asarray(vals, dtype=np.float64)


def target_reflectance_on_grid(
    target: TargetDescriptor,
    wavelength_um: npt.NDArray[np.float64],
    los: LineOfSightGeometry | None,
) -> npt.NDArray[np.float64] | None:
    """ρ(λ) the *target* descriptor implies, or ``None`` if it carries none.

    Dispatches the two reflective pathways of the table in this module's
    docstring: the ``T2Reflective`` protocol call and the ``T3Mixed``
    Kirchhoff derivation ``ρ = 1 − ε`` (Rule 5 — ρ is never an independent
    input for the mixed surface).  Every other variant returns ``None``:
    T1 is pure-thermal (ρ ≡ 0 by construction, not a reported surface
    property), and T5/T6/T7 supply radiance or intensity directly, so no
    surface reflectance exists to report.

    The ε(λ) of a ``T3Mixed`` is already on the chain grid (the inferrer
    resolves it there); it is resampled defensively only when a caller
    passes a different grid.
    """
    if isinstance(target, T2Reflective):
        assert target.rho is not None  # constructor invariant
        return resolve_reflectance_on_grid(target.rho, wavelength_um, los)
    if isinstance(target, T3Mixed):
        assert target.epsilon is not None  # constructor invariant
        grid = np.asarray(wavelength_um, dtype=np.float64)
        eps_grid = np.asarray(target.epsilon.wavelength_um, dtype=np.float64)
        eps_vals = np.asarray(target.epsilon.values, dtype=np.float64)
        if eps_grid.shape != grid.shape or not np.array_equal(eps_grid, grid):
            eps_vals = np.asarray(np.interp(grid, eps_grid, eps_vals), dtype=np.float64)
        return np.asarray(1.0 - eps_vals, dtype=np.float64)
    return None


__all__ = [
    "resolve_reflectance_on_grid",
    "target_reflectance_on_grid",
]
