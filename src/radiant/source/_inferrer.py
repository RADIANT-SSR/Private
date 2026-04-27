"""Back-compat descriptor inferrer for SourceStage (Option C, Stage 2).

This module maps the legacy (pre-Option-C) parameter surface onto the new
Option C descriptor surface defined in :mod:`radiant.core.descriptors` and
:mod:`radiant.core.los_geometry`.  It is the Stage-2 **additive bridge**
step in the [Option C plan](../../../docs/archive/Option_C_Implementation_Plan.md):
SourceStage now publishes TargetDescriptor + BackgroundDescriptor +
LineOfSightGeometry alongside the legacy ``at_target`` frame and
``L_background`` stage_output, so downstream stages are unchanged while
AtmosphereStage (Stage 3) and SpectralIntegrationStage (Stage 4) prepare
to consume the descriptors.

Principles
----------
- **Explicit overrides win**.  If the user sets ``source.scene_type`` or
  ``source.target_location`` to anything other than the sentinel ``"auto"``,
  that choice is honored.  If ``source.no_atmosphere_subcase`` is non-empty,
  it is used directly.
- **Inference is deterministic and conservative**.  Every rule has a code
  comment citing the matrix §3.2 line that justifies it.
- **Rule 2 (units at boundaries only)**.  This module performs zero unit
  conversions: inputs come from ``ParameterSet.get(...)`` in canonical
  units, and outputs (descriptors) carry canonical units directly.
- **Rule 11 (no cross-stage imports)**.  This module imports only from
  ``radiant.core`` (descriptors, los_geometry, parameters, spectral) and
  from ``radiant.source`` (local helpers like ``_classify_regime``).  It
  never imports ``radiant.atmosphere`` — it consults ``atmosphere.model``
  as a parameter string only.
- **Rule 19 (one computation, one module)**.  Inference lives here, not
  inside ``stage.py``.

Lossy boundary
--------------
The inferrer's output does **not** round-trip back to every legacy
parameter.  The descriptors carry the surface-radiometric surface
(ε, T_t, ρ, A_t, h_tgt, θ_o, θ_s) but do NOT carry atmosphere.* fields
(model selector, visibility, standard_atmosphere, etc.) because those
belong to the atmosphere subsystem, not the source.  The test
``test_inferrer.py::test_round_trip`` documents the lossy subset
(``source.target.temperature``, ``source.target.emissivity``,
``source.scene_type``, ``source.target_location``, ``source.target.range_m``,
``source.target.projected_area_m2``, ``source.target.fill_fraction``).

Stage 2 placeholder — GroundBackground
--------------------------------------
Matrix §3.2 says terrestrial / airborne targets carry a
:class:`GroundBackground`.  Stage 2 does not yet load full background
emissivity spectra; it builds a placeholder GroundBackground from
``source.background.temperature`` and a grey emissivity built from the
wavelength grid, and emits a ``UserWarning`` flagging that Stage 3 will
replace the placeholder with proper inference.  This keeps the current
pipeline running while we wire up the real background path.
"""

from __future__ import annotations

import math
import warnings
from typing import Any

import numpy as np

from radiant.core.descriptors import (
    AtApertureBackground,
    BackgroundDescriptor,
    ColdSpaceBackground,
    GroundBackground,
    T1Thermal,
    T2Reflective,
    T3Mixed,
    T5AtAperture,
    TargetDescriptor,
    UserSpectralBackground,
)
from radiant.core.los_geometry import LineOfSightGeometry
from radiant.core.parameters import ParameterBoundsError, ParameterSet, Provenance
from radiant.core.spectral import SpectralData
from radiant.source._schema import validate_reflectance_albedo_exclusive
from radiant.source.converters.brightness_temperature import (
    brightness_temperature_to_descriptor,
    load_brightness_temperature_csv,
)
from radiant.source.converters.radiance_temperature import (
    radiance_temperature_to_descriptor,
)
from radiant.source.converters.reflectance import (
    load_reflectance_csv,
    reflectance_to_descriptor,
)
from radiant.source.converters.user_intensity import (
    _validate_I_t_source,
    load_user_intensity_csv,
    user_intensity_to_descriptor,
)
from radiant.source.converters.user_radiance import (
    _validate_L_t_source,
    load_user_radiance_csv,
    user_radiance_to_descriptor,
)
from radiant.source.resolvers.shape_factory import build_shape
from radiant.source.shape import TargetShape
from radiant.source.tabulated import TabulatedRadianceSource

# ---------------------------------------------------------------------------
# Constants / helpers
# ---------------------------------------------------------------------------

# Atmosphere models that place the target on an atmospheric column.
# Matrix §3.2 lines 200–215: terrestrial / airborne defaults.
_TERRESTRIAL_ATM_MODELS: frozenset[str] = frozenset(
    {"simple", "modtran", "tabulated", "interpolated"}
)
# Atmosphere model that implies target_location="no_atmosphere" (space).
# Matrix §3.2 line 286: `exo` backend is the v1 vacuum model.
_EXO_ATM_MODELS: frozenset[str] = frozenset({"exo"})


def _is_user_set(params: ParameterSet, name: str) -> bool:
    """Return True iff parameter ``name`` was set by the user (not defaulted).

    Uses the ParameterSet's provenance mechanism: a parameter with
    :class:`Provenance.DEFAULT` provenance is the schema default; anything
    else (USER_SET, CONFIG_FILE, DERIVED, SAMPLED) is treated as "the
    user chose this value".  Stage 2 inference only activates when the
    provenance is DEFAULT.
    """
    rv = params.get_resolved(name)
    return rv.provenance is not Provenance.DEFAULT


def _grey_spectraldata(
    wavelength_um: np.ndarray,
    value: float,
    name: str,
    unit: str,
) -> SpectralData:
    """Build a constant-across-λ :class:`SpectralData` array.

    Used for the scalar-to-spectral lift in Stage 2: the legacy surface
    only exposes scalar ε and T_t, so we build a grey ε(λ) = value array
    on the chain's wavelength grid.  Stage 3+ will accept spectral
    emissivity/reflectance directly when the backgrounds subsystem
    matures.
    """
    vals = np.full(wavelength_um.shape, float(value), dtype=np.float64)
    return SpectralData(
        name=name,
        wavelength_um=np.asarray(wavelength_um, dtype=np.float64),
        values=vals,
        unit=unit,
        source="source._inferrer (grey lift from scalar parameter)",
    )


# ---------------------------------------------------------------------------
# Scene-type inference (matrix §3.2, §1.1)
# ---------------------------------------------------------------------------


def _infer_scene_type(
    params: ParameterSet,
    pixel_pitch_m: float,
    focal_length_m: float,
) -> str:
    """Deterministic scene_type from legacy parameters.

    Rules (matrix §3.2 lines 156–177):
      * ``fill_fraction == 1.0`` and no sub-pixel geometry → ``extended``.
      * ``0 < fill_fraction < 1`` → ``sub_pixel``.
      * Geometry implies point source (√A / R < 0.25 × IFOV) → ``point_source``.
      * Otherwise → ``extended`` when no geometry, ``sub_pixel`` when
        angular extent is intermediate.

    The point-source discriminator uses the SAME 0.25 × IFOV and 2 × IFOV
    thresholds as ``_classify_regime`` in ``stage.py``; see matrix §1.1.
    The descriptor point-source angular-size check
    (``√A / d > 0.1 · PSF_FWHM``, matrix §7) is **deferred** to
    OpticsStage per ADR-0002.
    """
    fill_fraction: float = params.get("source.target.fill_fraction")
    raw_area: float = params.get("source.target.projected_area_m2")
    raw_range: float = params.get("source.target.range_m")
    projected_area_m2: float | None = raw_area if raw_area > 0.0 else None
    range_m: float | None = raw_range if raw_range > 0.0 else None

    # Matrix §3.2 line 164: fill_fraction < 1 forces sub_pixel.
    if fill_fraction < 1.0:
        return "sub_pixel"

    # Matrix §3.2 line 168: no geometry → default extended (safest; matches
    # the legacy pipeline where every scenario without area/range ran as
    # extended thermal).
    if projected_area_m2 is None or range_m is None or range_m <= 0.0:
        return "extended"

    # Matrix §3.2 line 172 / §1.1: IFOV-based discriminator, same constants
    # as _classify_regime.
    angular_extent = math.sqrt(projected_area_m2) / range_m
    ifov = pixel_pitch_m / focal_length_m
    if angular_extent <= 0.25 * ifov:
        return "point_source"
    if angular_extent >= 2.0 * ifov:
        return "extended"
    return "sub_pixel"


# ---------------------------------------------------------------------------
# Target-location inference (matrix §3.2, §3.3)
# ---------------------------------------------------------------------------


def _infer_target_location_and_subcase(
    params: ParameterSet,
) -> tuple[str, str]:
    """Return ``(target_location, no_atmosphere_subcase)`` per matrix §3.2.

    Rules (matrix §3.2 lines 200–215, 280–300):
      * ``atmosphere.model`` ∈ {'simple','modtran','tabulated','interpolated'}
        → ``terrestrial``, subcase = "" (N/A).
      * ``atmosphere.model == 'exo'`` → ``no_atmosphere`` with subcase
        ``space`` (matrix §3.3 line 304: exo is the v1 vacuum backend and
        the Earth-intercept check is deferred to Stage 7).
      * Any other backend string → terrestrial (safest default; future
        backends would register themselves in ``_TERRESTRIAL_ATM_MODELS``).

    Airborne (h_tgt > 0) is NOT inferred here because the legacy parameter
    surface has no ``h_tgt`` field — Stage 5 of the Option C plan introduces
    the partial-column atmosphere and will add an ``airborne`` branch.
    Users who need airborne today set ``source.target_location`` explicitly.

    Graceful fallback: when ``atmosphere.model`` is not registered in the
    supplied ParameterSet (unit-test fixtures that only load the source
    schema), we default to ``terrestrial`` — the most common case and the
    one that the legacy SourceStage unit tests implicitly assume.
    """
    try:
        atm_model: str = params.get("atmosphere.model")
    except KeyError:
        # Source-only ParameterSet (unit test fixture).  Fall back to
        # terrestrial — the default used by the legacy pipeline before
        # Option C introduced the location axis.
        return "terrestrial", ""
    if atm_model in _EXO_ATM_MODELS:
        return "no_atmosphere", "space"
    if atm_model in _TERRESTRIAL_ATM_MODELS:
        return "terrestrial", ""
    # Unknown backends default to terrestrial (conservative — the user can
    # always override via `source.target_location`).
    return "terrestrial", ""


# ---------------------------------------------------------------------------
# LineOfSightGeometry inference
# ---------------------------------------------------------------------------


def _infer_los(
    target_location: str,
    params: ParameterSet,
    *,
    target_descriptor: TargetDescriptor | None = None,
) -> LineOfSightGeometry | None:
    """Build a LineOfSightGeometry from already-registered ``geometry.*`` params.

    Matrix §4.3 requires (h_tgt, θ_o, θ_s, Δφ).  All four canonical
    quantities map onto AtmosphereStage-registered ``geometry.*`` params
    that downstream stages already consume; this helper wires the
    SourceStage producer side to read from the same canonical names
    (CU-009).

      * ``h_tgt``        ← ``geometry.target_altitude_m`` (default 0.0 m).
      * ``theta_o``      ← ``geometry.path_zenith_rad`` (default 0.0 rad
        — nadir).
      * ``theta_s``      ← ``geometry.solar_zenith_rad`` for T2/T3
        targets, ``None`` for T1Thermal.
      * ``delta_phi``    ← ``geometry.solar_azimuth_rad`` for T2/T3
        targets, ``None`` for T1Thermal.
      * ``h_atm_top``    stays at the dataclass default (1e5 m, Kármán
        line; user-overridable surface is Stage-7+ / SensorDescriptor
        territory).

    The "T2/T3 ⇒ populated, T1 ⇒ None" predicate honors
    :class:`LineOfSightGeometry`'s "``None`` for pure-thermal scenarios
    where the sun is not used" docstring contract: T1Thermal radiance
    has no solar leg, so the solar fields are inert metadata at best
    and misleading at worst.  When ``target_descriptor`` is ``None``
    (legacy callers, source-only fixtures), the predicate also yields
    ``theta_s=None, delta_phi=None`` — back-compat with the pre-CU-009
    behavior.

    Returns ``None`` when ``target_location == "at_aperture"`` because
    the at-aperture pass-through arm never evaluates an atmospheric
    path; matrix §4.3 line 356.

    Each ``params.get`` is wrapped in ``try/except KeyError → default``
    so source-only unit-test fixtures (which do not register the
    AtmosphereStage schema) continue to work.
    """
    if target_location == "at_aperture":
        return None
    try:
        h_tgt_m = float(params.get("geometry.target_altitude_m"))
    except KeyError:
        h_tgt_m = 0.0
    if h_tgt_m < 0.0:
        h_tgt_m = 0.0
    try:
        theta_o = float(params.get("geometry.path_zenith_rad"))
    except KeyError:
        theta_o = 0.0
    if isinstance(target_descriptor, (T2Reflective, T3Mixed)):
        try:
            theta_s: float | None = float(params.get("geometry.solar_zenith_rad"))
        except KeyError:
            theta_s = None
        try:
            delta_phi: float | None = float(params.get("geometry.solar_azimuth_rad"))
        except KeyError:
            delta_phi = None
    else:
        theta_s = None
        delta_phi = None
    return LineOfSightGeometry(
        h_tgt=h_tgt_m,
        theta_o=theta_o,
        theta_s=theta_s,
        delta_phi=delta_phi,
    )


def _view_direction_from_los(params: ParameterSet, target_location: str) -> np.ndarray:
    """Return the target→observer unit 3-vector in the target scene frame.

    The shape protocol (``TargetShape.projected_area``) expects a unit
    view vector in the target's local scene frame with +Z = local up
    (per Rule 3).  The observer zenith angle ``theta_o`` is read from
    the canonical ``geometry.path_zenith_rad`` parameter (the same
    name that the AtmosphereStage / PlatformStage / PerformanceStage
    consumers use); we set the absolute observer azimuth to 0
    (observer along local +X horizon when tilted off-nadir) so that
    ``theta_o = 0`` gives the canonical nadir view ``(0, 0, 1)`` = +Z.

    Parameters
    ----------
    params:
        Resolved source ParameterSet.
    target_location:
        Matrix §3.2 target-location axis.  When ``at_aperture`` the
        LOS is skipped and we fall back to the nadir view because the
        at-aperture arm never evaluates atmospheric geometry.

    Returns
    -------
    numpy.ndarray
        Unit 3-vector in the target scene frame, target → observer.
    """
    if target_location == "at_aperture":
        return np.array([0.0, 0.0, 1.0], dtype=np.float64)
    try:
        theta_o = float(params.get("geometry.path_zenith_rad"))
    except KeyError:
        theta_o = 0.0
    if theta_o < 0.0:
        theta_o = 0.0
    if theta_o >= math.pi / 2.0:
        theta_o = math.pi / 2.0 - 1e-9
    return np.array([math.sin(theta_o), 0.0, math.cos(theta_o)], dtype=np.float64)


# ---------------------------------------------------------------------------
# CSV resample / validation helpers (Gap G, Step G.2 / G.3)
# ---------------------------------------------------------------------------


def _resample_dimensionless_on_grid(
    native: SpectralData,
    wavelength_um: np.ndarray,
    *,
    quantity_label: str,
) -> np.ndarray:
    """Resample a native-grid SpectralData onto the chain grid.

    Rule 17 — no silent extrapolation.  If the chain grid extends
    beyond the file's native grid on either end, raise
    :class:`ParameterBoundsError` with both ranges in context.  Also
    reject non-monotonic and duplicated native wavelengths; ``np.interp``
    otherwise silently produces ambiguous values.

    Parameters
    ----------
    native:
        SpectralData on its native grid (from the CSV loader).
    wavelength_um:
        Chain wavelength grid (canonical µm).
    quantity_label:
        Human-readable quantity name used in error messages
        (e.g. ``"reflectance"``, ``"brightness_temperature"``).

    Returns
    -------
    ndarray
        Values interpolated onto ``wavelength_um``.
    """
    lam = np.asarray(wavelength_um, dtype=np.float64)
    src_wl = np.asarray(native.wavelength_um, dtype=np.float64)
    src_vals = np.asarray(native.values, dtype=np.float64)

    # Monotonicity / duplicate checks are enforced by the shared CSV
    # loader (and ultimately by SpectralData.__post_init__), so by the
    # time we get here src_wl is strictly ascending.

    if lam[0] < src_wl[0] or lam[-1] > src_wl[-1]:
        raise ParameterBoundsError(
            what=(
                f"{quantity_label}: chain grid "
                f"[{lam[0]:.4f}, {lam[-1]:.4f}] µm extends outside "
                f"the CSV native grid "
                f"[{src_wl[0]:.4f}, {src_wl[-1]:.4f}] µm"
            ),
            why=(
                "RADIANT never silently extrapolates user-supplied "
                "tabulated data; extrapolation past the file bounds is "
                "unphysical and hides authoring errors."
            ),
            action=(
                "Extend the CSV to cover the full sensor band, or "
                "narrow the chain grid (source.grid.*) to the file "
                "extent."
            ),
            context={
                "source": native.source,
                "chain_grid_um": [float(lam[0]), float(lam[-1])],
                "file_grid_um": [float(src_wl[0]), float(src_wl[-1])],
                "quantity": quantity_label,
            },
        )

    return np.asarray(np.interp(lam, src_wl, src_vals), dtype=np.float64)


def _validate_rho_csv(rho_values: np.ndarray, *, csv_path: str) -> None:
    """Raise on ρ outside ``[0, 1]`` at the CSV boundary (Rule 15).

    Mirrors :func:`reflectance._validate_rho` but reports the source
    CSV path in context so the user can trace a bad row to its file.
    """
    if rho_values.size == 0:
        raise ParameterBoundsError(
            what=("reflectance_path: CSV produced zero-sample SpectralData"),
            why=("The converter needs at least one (λ, ρ) pair to emit a descriptor."),
            action=("Populate the CSV with at least two (wavelength_um, reflectance) rows."),
            context={"path": csv_path},
        )
    if np.any(rho_values < 0.0):
        bad = float(rho_values.min())
        raise ParameterBoundsError(
            what=(f"reflectance_path: rho = {bad} is negative in CSV {csv_path}"),
            why=(
                "Reflectance is a dimensionless fraction in [0, 1]; "
                "negative values have no physical interpretation."
            ),
            action=("Correct the CSV rows so every rho value is ≥ 0."),
            context={
                "path": csv_path,
                "min_rho": bad,
                "floor": 0.0,
            },
        )
    if np.any(rho_values > 1.0):
        bad = float(rho_values.max())
        raise ParameterBoundsError(
            what=(f"reflectance_path: rho = {bad} exceeds 1.0 in CSV {csv_path}"),
            why=(
                "Reflectance > 1 violates energy conservation "
                "(reflected power cannot exceed incident power for a "
                "passive surface)."
            ),
            action=(
                "Clamp rho ≤ 1 in the CSV or check for unit / scale "
                "errors (e.g. percent vs fraction)."
            ),
            context={
                "path": csv_path,
                "max_rho": bad,
                "ceiling": 1.0,
            },
        )


_T_B_CSV_MIN_K: float = 0.0
_T_B_CSV_MAX_K: float = 10_000.0


def _validate_T_B_csv(T_B_values: np.ndarray, *, csv_path: str) -> None:
    """Raise on T_B outside ``(0, 10000]`` K at the CSV boundary (Rule 15).

    Mirrors the converter's private ``_validate_T_B`` but reports the
    source CSV path in context so the user can trace a bad row to its
    file.  Runs on the native grid (pre-resample) — Rule 16: validate
    before compute.
    """
    if T_B_values.size == 0:
        raise ParameterBoundsError(
            what=("brightness_temperature_path: CSV produced zero-sample SpectralData"),
            why=("The converter needs at least one (λ, T_B) pair to emit a descriptor."),
            action=(
                "Populate the CSV with at least two (wavelength_um, brightness_temperature) rows."
            ),
            context={"path": csv_path},
        )
    if np.any(T_B_values < _T_B_CSV_MIN_K):
        bad = float(T_B_values.min())
        raise ParameterBoundsError(
            what=(f"brightness_temperature_path: T_B = {bad} K is negative in CSV {csv_path}"),
            why=(
                "Brightness temperature is an equivalent absolute "
                "temperature; negative values have no Planck "
                "interpretation."
            ),
            action=(f"Set every T_B value ≥ {_T_B_CSV_MIN_K} K in the CSV."),
            context={
                "path": csv_path,
                "min_T_B_K": bad,
                "floor_K": _T_B_CSV_MIN_K,
            },
        )
    if np.any(T_B_values > _T_B_CSV_MAX_K):
        bad = float(T_B_values.max())
        raise ParameterBoundsError(
            what=(
                f"brightness_temperature_path: T_B = {bad} K exceeds "
                f"{_T_B_CSV_MAX_K} K ceiling in CSV {csv_path}"
            ),
            why=(
                "T_B > 10 000 K is non-physical for RADIANT targets "
                "(solar effective T ≈ 5778 K).  Values this large are "
                "typically a unit error (°C vs K) or input scale bug."
            ),
            action=("Verify units (canonical K, not °C) and the T_B CSV column values."),
            context={
                "path": csv_path,
                "max_T_B_K": bad,
                "ceiling_K": _T_B_CSV_MAX_K,
            },
        )


# ---------------------------------------------------------------------------
# Target descriptor construction
# ---------------------------------------------------------------------------


def _resolve_projected_area_and_shape(
    params: ParameterSet,
    target_location: str,
) -> tuple[float | None, TargetShape | None]:
    """Return ``(A_t, shape)`` per the Q3 shape-wins rule.

    Shared between the legacy ε/T path in ``_build_target_descriptor``
    and the S11 brightness-temperature branch; both paths apply the
    shape-over-projected_area precedence identically.
    """
    projected_area: float = params.get("source.target.projected_area_m2")
    user_area_set: bool = projected_area > 0.0

    shape_obj: TargetShape | None = build_shape(params)
    if shape_obj is not None and target_location == "at_aperture":
        shape_name_tmp: str = params.get("source.target.shape")
        raise ParameterBoundsError(
            what=(
                f"source.target.shape = {shape_name_tmp!r} is incompatible "
                f"with target_location='at_aperture' (S9)"
            ),
            why=(
                "The at-aperture target spec form (S9) provides a "
                "spectral radiance already at the aperture plane — there "
                "is no scene-frame geometry for shape.projected_area "
                "to operate on."
            ),
            action=(
                "Either remove source.target.shape to use the at-aperture "
                "radiance directly, or switch target_location away from "
                "'at_aperture' so the shape is evaluated against a "
                "physical line of sight."
            ),
            context={
                "shape": shape_name_tmp,
                "target_location": target_location,
            },
        )
    if shape_obj is not None:
        shape_name: str = params.get("source.target.shape")
        view_dir = _view_direction_from_los(params, target_location)
        a_shape = float(shape_obj.projected_area(view_dir))
        if user_area_set:
            warnings.warn(
                (
                    f"Both shape={shape_name!r} and "
                    f"projected_area_m2={projected_area} supplied; "
                    f"shape wins (A_projected={a_shape} m²)."
                ),
                UserWarning,
                stacklevel=2,
            )
        A_t: float | None = a_shape if a_shape > 0.0 else None
    else:
        A_t = projected_area if user_area_set else None
    return A_t, shape_obj


def _maybe_build_from_brightness_temperature(
    params: ParameterSet,
    wavelength_um: np.ndarray,
    scene_type: str,
    target_location: str,
    no_atmosphere_subcase: str,
    h_tgt: float | None,
) -> TargetDescriptor | None:
    """Return an S11-routed descriptor or None if T_B is not user-set.

    S11 spec form (Target Definition Matrix §1): the user supplies a
    brightness temperature ``T_B`` (scalar or λ-tabulated) and the
    boundary converter routes to either :class:`T1Thermal` (near-constant
    T_B, ε ≡ 1) or :class:`T6TabulatedAtSource` (λ-varying T_B, per
    ADR-0003).

    Both user-entry surfaces are fully wired:
      * ``source.target.brightness_temperature_K`` (scalar) lifts to a
        flat SpectralData on the chain grid.
      * ``source.target.brightness_temperature_path`` (CSV) loads a
        native-grid SpectralData via the shared two-column reader,
        validates T_B ∈ (0, 10000] K at the boundary, then resamples
        onto the chain grid with hard out-of-grid guards (Rule 17:
        no silent extrapolation).
    """
    t_b_k_rv = params.get_resolved("source.target.brightness_temperature_K")
    t_b_path_rv = params.get_resolved("source.target.brightness_temperature_path")
    t_b_k_user = t_b_k_rv.provenance is not Provenance.DEFAULT
    t_b_path_user = t_b_path_rv.provenance is not Provenance.DEFAULT and bool(t_b_path_rv.value)

    if not t_b_k_user and not t_b_path_user:
        return None

    if t_b_k_user and t_b_path_user:
        raise ParameterBoundsError(
            what=(
                "source._inferrer: both "
                "source.target.brightness_temperature_K and "
                "source.target.brightness_temperature_path are user-set"
            ),
            why=(
                "S11 is a single spec form — either a scalar T_B or a "
                "tabulated T_B(λ), not both (would over-specify the "
                "source surface)."
            ),
            action=(
                "Pick one: leave the scalar for a flat T_B, or the path "
                "for a λ-dependent T_B (routes to T6TabulatedAtSource)."
            ),
            context={
                "brightness_temperature_K": t_b_k_rv.value,
                "brightness_temperature_path": t_b_path_rv.value,
            },
        )

    if _is_user_set(params, "source.target.temperature") or _is_user_set(
        params, "source.target.emissivity"
    ):
        raise ParameterBoundsError(
            what=(
                "source._inferrer: brightness_temperature is mutually "
                "exclusive with source.target.temperature / "
                "source.target.emissivity"
            ),
            why=(
                "S11 replaces the (ε, T_t) surface with an equivalent-"
                "blackbody radiance description; supplying both forms "
                "over-specifies the target."
            ),
            action=(
                "Remove source.target.temperature and .emissivity when "
                "using source.target.brightness_temperature_*; or remove "
                "brightness_temperature_* to use the legacy (ε, T) form."
            ),
            context={
                "temperature_set": _is_user_set(params, "source.target.temperature"),
                "emissivity_set": _is_user_set(params, "source.target.emissivity"),
            },
        )

    if _is_user_set(params, "source.target.user_radiance_path"):
        raise ParameterBoundsError(
            what=(
                "source._inferrer: brightness_temperature is mutually "
                "exclusive with user_radiance_path (S11 vs S8)"
            ),
            why=(
                "S8 supplies an absolute radiance already at the target "
                "plane; S11 supplies an equivalent brightness "
                "temperature that the converter turns into radiance.  "
                "Combining them over-specifies the target radiance."
            ),
            action=(
                "Pick one user-entry surface: brightness_temperature_* "
                "for S11, or user_radiance_path for S8 (direct radiance)."
            ),
            context={
                "user_radiance_path": params.get_resolved("source.target.user_radiance_path").value,
            },
        )

    if _is_user_set(params, "source.target.user_intensity_path"):
        raise ParameterBoundsError(
            what=(
                "source._inferrer: brightness_temperature is mutually "
                "exclusive with user_intensity_path (S11 vs S10)"
            ),
            why=(
                "S10 supplies an absolute intensity at the target plane "
                "for point sources; S11 supplies an equivalent "
                "brightness temperature that the converter turns into "
                "radiance.  Combining them over-specifies the target."
            ),
            action=(
                "Pick one user-entry surface: brightness_temperature_* "
                "for S11, or user_intensity_path for S10 (direct "
                "intensity)."
            ),
            context={
                "user_intensity_path": params.get_resolved(
                    "source.target.user_intensity_path"
                ).value,
            },
        )

    if (
        _is_user_set(params, "source.target.reflectance")
        or _is_user_set(params, "source.target.albedo")
        or _is_user_set(params, "source.target.reflectance_path")
        or _is_user_set(params, "source.target.albedo_path")
    ):
        raise ParameterBoundsError(
            what=(
                "source._inferrer: brightness_temperature is mutually "
                "exclusive with reflectance/albedo (thermal S11 vs "
                "reflective S4/S5/S6)"
            ),
            why=(
                "A single target cannot be both purely thermal and "
                "purely reflective.  Mixed emit+reflect must go through "
                "the legacy (ε, T) → T3Mixed path."
            ),
            action=(
                "Pick one user-entry surface: brightness_temperature_* "
                "for pure thermal (T1), reflectance/albedo for pure "
                "reflection (T2), or temperature+emissivity for mixed (T3)."
            ),
            context={
                "reflectance_set": _is_user_set(params, "source.target.reflectance"),
                "albedo_set": _is_user_set(params, "source.target.albedo"),
            },
        )

    A_t, shape_obj = _resolve_projected_area_and_shape(params, target_location)

    # Tabulated T_B(λ) via CSV (S11 brightness_temperature_path).
    # Gap G Step G.3: load native grid, validate T_B ∈ (0, 10000] K at the
    # boundary, resample onto the chain grid with hard out-of-grid guards
    # (Rule 17: no silent extrapolation), then dispatch to the converter
    # which routes constant vs λ-varying to T1Thermal vs T6TabulatedAtSource.
    if t_b_path_user:
        csv_path = str(t_b_path_rv.value)
        T_B_native = load_brightness_temperature_csv(csv_path)
        # Boundary guard (Rule 16): validate native T_B BEFORE resampling —
        # interpolation could otherwise mask out-of-range samples between
        # good neighbours.
        _validate_T_B_csv(
            np.asarray(T_B_native.values, dtype=np.float64),
            csv_path=csv_path,
        )
        T_B_on_grid = _resample_dimensionless_on_grid(
            T_B_native,
            wavelength_um,
            quantity_label="brightness_temperature",
        )
        T_B = SpectralData(
            name="source.target.brightness_temperature",
            wavelength_um=np.asarray(wavelength_um, dtype=np.float64),
            values=T_B_on_grid,
            unit="K",
            source=(f"source.converters.brightness_temperature (CSV → chain grid: {csv_path})"),
        )
        return brightness_temperature_to_descriptor(
            T_B=T_B,
            scene_type=scene_type,  # type: ignore[arg-type]
            target_location=target_location,  # type: ignore[arg-type]
            no_atmosphere_subcase=(  # type: ignore[arg-type]
                no_atmosphere_subcase or None
            ),
            h_tgt=h_tgt,
            A_t=A_t,
            shape=shape_obj,
        )

    # Scalar T_B: lift to a flat SpectralData on the chain grid and run
    # the converter.  Constant ⇒ T1Thermal with ε ≡ 1 (exact blackbody).
    T_B_scalar = float(t_b_k_rv.value)
    T_B = SpectralData(
        name="source.target.brightness_temperature",
        wavelength_um=np.asarray(wavelength_um, dtype=np.float64),
        values=np.full(
            np.asarray(wavelength_um).shape,
            T_B_scalar,
            dtype=np.float64,
        ),
        unit="K",
        source=("source.target.brightness_temperature_K (scalar lift; S11)"),
    )

    return brightness_temperature_to_descriptor(
        T_B=T_B,
        scene_type=scene_type,  # type: ignore[arg-type]
        target_location=target_location,  # type: ignore[arg-type]
        no_atmosphere_subcase=(  # type: ignore[arg-type]
            no_atmosphere_subcase or None
        ),
        h_tgt=h_tgt,
        A_t=A_t,
        shape=shape_obj,
    )


def _maybe_build_from_radiance_temperature(
    params: ParameterSet,
    wavelength_um: np.ndarray,
    scene_type: str,
    target_location: str,
    no_atmosphere_subcase: str,
    h_tgt: float | None,
) -> TargetDescriptor | None:
    """Return an S12-routed descriptor or None if T_R is not user-set.

    S12 spec form (Target Definition Matrix §1): the user supplies a
    scalar radiance temperature ``T_R`` together with a band
    ``[λ_lo, λ_hi]``.  The boundary converter treats the target as a
    blackbody at ``T_R`` and emits :class:`T1Thermal` with ``T_t = T_R``
    and ``ε ≡ 1``.  Implementation plan Step 2.2.
    """
    t_r_rv = params.get_resolved("source.target.radiance_temperature_K")
    lo_rv = params.get_resolved("source.target.radiance_temperature_band_lo_um")
    hi_rv = params.get_resolved("source.target.radiance_temperature_band_hi_um")
    t_r_user = t_r_rv.provenance is not Provenance.DEFAULT

    if not t_r_user:
        return None

    lo_user = lo_rv.provenance is not Provenance.DEFAULT
    hi_user = hi_rv.provenance is not Provenance.DEFAULT
    if not (lo_user and hi_user):
        raise ParameterBoundsError(
            what=(
                "source._inferrer: radiance_temperature_K is set but "
                "radiance_temperature_band_lo_um / _hi_um is not"
            ),
            why=(
                "S12 requires both the scalar T_R and the band edges "
                "(λ_lo, λ_hi); T_R is defined against an integration "
                "window and cannot be interpreted without one."
            ),
            action=(
                "Set both source.target.radiance_temperature_band_lo_um "
                "and source.target.radiance_temperature_band_hi_um in µm."
            ),
            context={
                "radiance_temperature_K": t_r_rv.value,
                "band_lo_set": lo_user,
                "band_hi_set": hi_user,
            },
        )

    if _is_user_set(params, "source.target.temperature") or _is_user_set(
        params, "source.target.emissivity"
    ):
        raise ParameterBoundsError(
            what=(
                "source._inferrer: radiance_temperature is mutually "
                "exclusive with source.target.temperature / "
                "source.target.emissivity"
            ),
            why=(
                "S12 replaces the (ε, T_t) surface with an equivalent-"
                "blackbody band-radiance description; supplying both "
                "forms over-specifies the target."
            ),
            action=(
                "Remove source.target.temperature and .emissivity when "
                "using source.target.radiance_temperature_K; or remove "
                "T_R to use the legacy (ε, T) form."
            ),
            context={
                "temperature_set": _is_user_set(params, "source.target.temperature"),
                "emissivity_set": _is_user_set(params, "source.target.emissivity"),
            },
        )

    if _is_user_set(params, "source.target.user_radiance_path"):
        raise ParameterBoundsError(
            what=(
                "source._inferrer: radiance_temperature is mutually "
                "exclusive with user_radiance_path (S12 vs S8)"
            ),
            why=(
                "S8 supplies an absolute radiance already at the target "
                "plane; S12 supplies a band-averaged radiance "
                "temperature the converter inverts into radiance.  "
                "Combining them over-specifies the target radiance."
            ),
            action=(
                "Pick one user-entry surface: radiance_temperature_K + "
                "band for S12, or user_radiance_path for S8 (direct "
                "radiance)."
            ),
            context={
                "user_radiance_path": params.get_resolved("source.target.user_radiance_path").value,
            },
        )

    if _is_user_set(params, "source.target.user_intensity_path"):
        raise ParameterBoundsError(
            what=(
                "source._inferrer: radiance_temperature is mutually "
                "exclusive with user_intensity_path (S12 vs S10)"
            ),
            why=(
                "S10 supplies an absolute intensity at the target plane "
                "for point sources; S12 supplies a band-averaged "
                "radiance temperature the converter inverts into "
                "radiance.  Combining them over-specifies the target."
            ),
            action=(
                "Pick one user-entry surface: radiance_temperature_K + "
                "band for S12, or user_intensity_path for S10 (direct "
                "intensity)."
            ),
            context={
                "user_intensity_path": params.get_resolved(
                    "source.target.user_intensity_path"
                ).value,
            },
        )

    if (
        _is_user_set(params, "source.target.reflectance")
        or _is_user_set(params, "source.target.albedo")
        or _is_user_set(params, "source.target.reflectance_path")
        or _is_user_set(params, "source.target.albedo_path")
    ):
        raise ParameterBoundsError(
            what=(
                "source._inferrer: radiance_temperature is mutually "
                "exclusive with reflectance/albedo (thermal S12 vs "
                "reflective S4/S5/S6)"
            ),
            why=(
                "A single target cannot be both purely thermal and "
                "purely reflective.  Mixed emit+reflect must go through "
                "the legacy (ε, T) → T3Mixed path."
            ),
            action=(
                "Pick one user-entry surface: radiance_temperature_K + "
                "band for pure thermal (T1), reflectance/albedo for pure "
                "reflection (T2), or temperature+emissivity for mixed (T3)."
            ),
            context={
                "reflectance_set": _is_user_set(params, "source.target.reflectance"),
                "albedo_set": _is_user_set(params, "source.target.albedo"),
            },
        )

    if _is_user_set(params, "source.target.brightness_temperature_K") or _is_user_set(
        params, "source.target.brightness_temperature_path"
    ):
        raise ParameterBoundsError(
            what=(
                "source._inferrer: radiance_temperature is mutually "
                "exclusive with brightness_temperature_* (S11 vs S12)"
            ),
            why=(
                "S11 and S12 are parallel user-entry forms for the same "
                "thermal target; combining them over-specifies the "
                "source surface."
            ),
            action=(
                "Pick one: brightness_temperature_* for a λ-resolved "
                "T_B(λ), or radiance_temperature_K + band for a scalar "
                "band-averaged T_R."
            ),
            context={
                "T_B_K_set": _is_user_set(params, "source.target.brightness_temperature_K"),
                "T_B_path_set": _is_user_set(params, "source.target.brightness_temperature_path"),
            },
        )

    T_R_K = float(t_r_rv.value)
    band = (float(lo_rv.value), float(hi_rv.value))

    A_t, shape_obj = _resolve_projected_area_and_shape(params, target_location)
    return radiance_temperature_to_descriptor(
        T_R_K=T_R_K,
        band_um=band,
        wavelength_um=wavelength_um,
        scene_type=scene_type,  # type: ignore[arg-type]
        target_location=target_location,  # type: ignore[arg-type]
        no_atmosphere_subcase=(  # type: ignore[arg-type]
            no_atmosphere_subcase or None
        ),
        h_tgt=h_tgt,
        A_t=A_t,
        shape=shape_obj,
    )


def _maybe_build_from_reflectance(
    params: ParameterSet,
    wavelength_um: np.ndarray,
    scene_type: str,
    target_location: str,
    no_atmosphere_subcase: str,
    h_tgt: float | None,
) -> TargetDescriptor | None:
    """Return an S4/S5/S6-routed T2Reflective or None if ρ is not user-set.

    Matrix spec forms S4 (scalar ρ), S5 (tabulated ρ(λ) via CSV path),
    S6 (albedo alias) all collapse onto :class:`T2Reflective`.  Step 3.2
    fully wires the scalar paths (``reflectance`` / ``albedo``); the
    tabulated ``_path`` surfaces raise a clear deferral error until the
    same CSV-loader work that lands with S11's T_B path.
    """
    rho_rv = params.get_resolved("source.target.reflectance")
    alb_rv = params.get_resolved("source.target.albedo")
    rho_path_rv = params.get_resolved("source.target.reflectance_path")
    alb_path_rv = params.get_resolved("source.target.albedo_path")

    rho_user = rho_rv.provenance is not Provenance.DEFAULT
    alb_user = alb_rv.provenance is not Provenance.DEFAULT
    rho_path_user = rho_path_rv.provenance is not Provenance.DEFAULT and bool(rho_path_rv.value)
    alb_path_user = alb_path_rv.provenance is not Provenance.DEFAULT and bool(alb_path_rv.value)

    any_user = rho_user or alb_user or rho_path_user or alb_path_user
    if not any_user:
        return None

    # Reject over-specified reflectance surfaces (reflectance + albedo,
    # scalar + path, etc.).  The schema-layer validator owns this check.
    validate_reflectance_albedo_exclusive(params)

    # Reject pairing with legacy thermal surface (T3Mixed is the path for
    # combined ε + T; supplying both ρ and T over-specifies the target).
    if _is_user_set(params, "source.target.temperature") or _is_user_set(
        params, "source.target.emissivity"
    ):
        raise ParameterBoundsError(
            what=(
                "source._inferrer: reflectance/albedo is mutually "
                "exclusive with source.target.temperature / "
                "source.target.emissivity"
            ),
            why=(
                "Pure-reflective targets (T2Reflective) are specified "
                "by ρ(λ) alone.  Combining ρ with (ε, T) drops into the "
                "T3Mixed regime — for that surface, omit ρ and let "
                "Kirchhoff derive ρ = 1 − ε downstream."
            ),
            action=(
                "Remove source.target.temperature and .emissivity when "
                "using reflectance/albedo; or remove reflectance to use "
                "the legacy (ε, T) → T3Mixed path."
            ),
            context={
                "temperature_set": _is_user_set(params, "source.target.temperature"),
                "emissivity_set": _is_user_set(params, "source.target.emissivity"),
            },
        )

    if _is_user_set(params, "source.target.user_radiance_path"):
        raise ParameterBoundsError(
            what=(
                "source._inferrer: reflectance/albedo is mutually "
                "exclusive with user_radiance_path (S4/S5/S6 vs S8)"
            ),
            why=(
                "S8 supplies an absolute radiance already at the target "
                "plane; S4/S5/S6 supplies a material ρ(λ) that RADIANT "
                "turns into radiance via the solar path.  Combining "
                "them over-specifies the target radiance."
            ),
            action=(
                "Pick one user-entry surface: reflectance/albedo for "
                "a material description (S4/S5/S6), or "
                "user_radiance_path for direct radiance (S8)."
            ),
            context={
                "user_radiance_path": params.get_resolved("source.target.user_radiance_path").value,
            },
        )

    if _is_user_set(params, "source.target.user_intensity_path"):
        raise ParameterBoundsError(
            what=(
                "source._inferrer: reflectance/albedo is mutually "
                "exclusive with user_intensity_path (S4/S5/S6 vs S10)"
            ),
            why=(
                "S10 supplies an absolute intensity at the target plane "
                "for point sources; S4/S5/S6 supplies a material ρ(λ) "
                "that RADIANT turns into radiance via the solar path.  "
                "Combining them over-specifies the target."
            ),
            action=(
                "Pick one user-entry surface: reflectance/albedo for "
                "a material description (S4/S5/S6), or "
                "user_intensity_path for direct intensity (S10)."
            ),
            context={
                "user_intensity_path": params.get_resolved(
                    "source.target.user_intensity_path"
                ).value,
            },
        )

    # Reject pairing with S11 / S12 thermal user-entry forms.
    if (
        _is_user_set(params, "source.target.brightness_temperature_K")
        or _is_user_set(params, "source.target.brightness_temperature_path")
        or _is_user_set(params, "source.target.radiance_temperature_K")
    ):
        raise ParameterBoundsError(
            what=(
                "source._inferrer: reflectance/albedo is mutually "
                "exclusive with brightness_temperature / "
                "radiance_temperature (thermal S11/S12 vs reflective "
                "S4/S5/S6)"
            ),
            why=(
                "A single target cannot be both purely reflective and "
                "purely thermal.  Mixed emit+reflect must go through "
                "the legacy (ε, T) → T3Mixed path."
            ),
            action=(
                "Pick one user-entry surface: reflectance/albedo for "
                "pure reflection (T2), brightness_temperature or "
                "radiance_temperature for pure thermal (T1), or "
                "temperature+emissivity for mixed (T3)."
            ),
            context={
                "brightness_temperature_K_set": _is_user_set(
                    params, "source.target.brightness_temperature_K"
                ),
                "brightness_temperature_path_set": _is_user_set(
                    params, "source.target.brightness_temperature_path"
                ),
                "radiance_temperature_K_set": _is_user_set(
                    params, "source.target.radiance_temperature_K"
                ),
            },
        )

    A_t, shape_obj = _resolve_projected_area_and_shape(params, target_location)

    # Tabulated ρ(λ) via CSV (S5 reflectance_path / S6 albedo_path).
    # Gap G Step G.2: load native grid, validate bounds at the boundary,
    # resample onto the chain grid with hard out-of-grid / monotonicity
    # guards (Rule 17: no silent extrapolation), then dispatch.
    if rho_path_user or alb_path_user:
        csv_path = str(rho_path_rv.value if rho_path_user else alb_path_rv.value)
        rho_native = load_reflectance_csv(csv_path, is_albedo=alb_path_user)
        # Boundary guard (Rule 16): validate native ρ ∈ [0, 1] BEFORE
        # resampling — catches bad rows at the CSV boundary with the
        # source path in context.
        _validate_rho_csv(
            np.asarray(rho_native.values, dtype=np.float64),
            csv_path=csv_path,
        )
        rho_on_grid = _resample_dimensionless_on_grid(
            rho_native, wavelength_um, quantity_label="reflectance"
        )
        rho_sd = SpectralData(
            name="source.target.reflectance",
            wavelength_um=np.asarray(wavelength_um, dtype=np.float64),
            values=rho_on_grid,
            unit="dimensionless",
            source=(f"source.converters.reflectance (CSV → chain grid: {csv_path})"),
        )
        return reflectance_to_descriptor(
            rho=rho_sd,
            wavelength_um=wavelength_um,
            scene_type=scene_type,  # type: ignore[arg-type]
            target_location=target_location,  # type: ignore[arg-type]
            no_atmosphere_subcase=(  # type: ignore[arg-type]
                no_atmosphere_subcase or None
            ),
            h_tgt=h_tgt,
            A_t=A_t,
            shape=shape_obj,
        )

    # Scalar ρ — take whichever surface is user-set (validator already
    # enforced that only one is).
    rho_scalar = float(rho_rv.value if rho_user else alb_rv.value)

    return reflectance_to_descriptor(
        rho=rho_scalar,
        wavelength_um=wavelength_um,
        scene_type=scene_type,  # type: ignore[arg-type]
        target_location=target_location,  # type: ignore[arg-type]
        no_atmosphere_subcase=(  # type: ignore[arg-type]
            no_atmosphere_subcase or None
        ),
        h_tgt=h_tgt,
        A_t=A_t,
        shape=shape_obj,
    )


def _maybe_build_from_user_radiance(
    params: ParameterSet,
    wavelength_um: np.ndarray,
    scene_type: str,
    target_location: str,
    no_atmosphere_subcase: str,
    h_tgt: float | None,
) -> TargetDescriptor | None:
    """Return an S8-routed T6TabulatedAtSource, or None if not user-set.

    S8 spec form (Target Definition Matrix §1): the user supplies an
    absolute spectral radiance ``L_t_source(λ)`` at the target plane
    via ``source.target.user_radiance_path`` (a two-column CSV).  The
    boundary converter loads the CSV, resamples onto the chain grid
    through :class:`~radiant.source.tabulated.TabulatedRadianceSource`,
    and routes to :class:`T6TabulatedAtSource` (ADR-0003).

    ``target_location == 'at_aperture'`` is rejected — that cell is the
    S9 (T5AtAperture) domain and bypasses atmospheric transport.  The
    mutual-exclusion guards against every other spec form ((ε, T),
    ρ/albedo, S11 T_B, S12 T_R) are owned by the respective helpers
    (each rejects S8 symmetrically); this helper only needs to guard
    the legacy (ε, T) surface for the case where S8 is the only
    fast-path candidate.
    """
    path_rv = params.get_resolved("source.target.user_radiance_path")
    path_user = path_rv.provenance is not Provenance.DEFAULT and bool(path_rv.value)
    if not path_user:
        return None

    if _is_user_set(params, "source.target.temperature") or _is_user_set(
        params, "source.target.emissivity"
    ):
        raise ParameterBoundsError(
            what=(
                "source._inferrer: user_radiance_path is mutually "
                "exclusive with source.target.temperature / "
                "source.target.emissivity"
            ),
            why=(
                "S8 supplies an absolute radiance already at the target "
                "plane; combining it with (ε, T) over-specifies the "
                "target radiance (RADIANT would have two inconsistent "
                "ways to compute L_t_source)."
            ),
            action=(
                "Remove source.target.temperature and .emissivity when "
                "using source.target.user_radiance_path; or remove "
                "user_radiance_path to use the legacy (ε, T) form."
            ),
            context={
                "temperature_set": _is_user_set(params, "source.target.temperature"),
                "emissivity_set": _is_user_set(params, "source.target.emissivity"),
            },
        )

    if _is_user_set(params, "source.target.user_intensity_path"):
        raise ParameterBoundsError(
            what=(
                "source._inferrer: user_radiance_path is mutually "
                "exclusive with user_intensity_path (S8 vs S10)"
            ),
            why=(
                "S8 supplies radiance L_t_source [W/m²/sr/µm] at the "
                "target plane for resolved targets; S10 supplies "
                "intensity I_t_source [W/sr/µm] for point-source targets. "
                "They are different radiometric quantities for different "
                "regimes — combining them over-specifies the target."
            ),
            action=(
                "Pick one user-entry surface: user_radiance_path for "
                "resolved targets (S8), or user_intensity_path for "
                "point-source targets (S10)."
            ),
            context={
                "user_intensity_path": params.get_resolved(
                    "source.target.user_intensity_path"
                ).value,
            },
        )

    csv_path = str(path_rv.value)

    # Load CSV → SpectralData on the file's native grid.  Rule 15:
    # load_user_radiance_csv raises ParameterBoundsError on missing /
    # malformed / empty files with actionable context.
    L_native = load_user_radiance_csv(csv_path)

    # Boundary guard (Rule 15): validate native values here so a negative
    # CSV entry surfaces as a ParameterBoundsError with actionable
    # context, not as the ValueError that TabulatedRadianceSource
    # raises for the same condition.
    _validate_L_t_source(np.asarray(L_native.values, dtype=np.float64))

    # Resample onto the chain grid via TabulatedRadianceSource (owns
    # the interpolation contract; extrapolation outside the native
    # grid raises).
    tabulated = TabulatedRadianceSource(radiance_data=L_native, name="source.target.user_radiance")
    lam = np.asarray(wavelength_um, dtype=np.float64)
    L_on_grid = tabulated.spectral_radiance(lam)

    L_sd = SpectralData(
        name="source.target.user_radiance",
        wavelength_um=lam,
        values=L_on_grid,
        unit="W/m^2/sr/um",
        source=(f"source.converters.user_radiance (CSV → chain grid: {csv_path})"),
    )

    A_t, shape_obj = _resolve_projected_area_and_shape(params, target_location)
    return user_radiance_to_descriptor(
        L_t_source=L_sd,
        scene_type=scene_type,  # type: ignore[arg-type]
        target_location=target_location,  # type: ignore[arg-type]
        no_atmosphere_subcase=(  # type: ignore[arg-type]
            no_atmosphere_subcase or None
        ),
        h_tgt=h_tgt,
        A_t=A_t,
        shape=shape_obj,
    )


def _maybe_build_from_user_intensity(
    params: ParameterSet,
    wavelength_um: np.ndarray,
    scene_type: str,
    target_location: str,
    no_atmosphere_subcase: str,
    h_tgt: float | None,
) -> TargetDescriptor | None:
    """Return an S10-routed T7IntensityAtSource, or None if not user-set.

    S10 spec form (Target Definition Matrix §1; ADR-0004): the user
    supplies an absolute spectral intensity ``I_t_source(λ)`` at the
    target plane via ``source.target.user_intensity_path`` (a two-
    column CSV).  The boundary converter loads the CSV, resamples onto
    the chain grid via linear interpolation, and routes to
    :class:`T7IntensityAtSource`.

    ``target_location == 'at_aperture'`` and ``scene_type != 'point_source'``
    are rejected by the converter.  Mutual-exclusion guards against
    every other spec form are owned by the respective helpers (each
    rejects S10 symmetrically); this helper only needs to guard the
    legacy (ε, T) surface for the case where S10 is the only fast-path
    candidate.
    """
    path_rv = params.get_resolved("source.target.user_intensity_path")
    path_user = path_rv.provenance is not Provenance.DEFAULT and bool(path_rv.value)
    if not path_user:
        return None

    if _is_user_set(params, "source.target.temperature") or _is_user_set(
        params, "source.target.emissivity"
    ):
        raise ParameterBoundsError(
            what=(
                "source._inferrer: user_intensity_path is mutually "
                "exclusive with source.target.temperature / "
                "source.target.emissivity"
            ),
            why=(
                "S10 supplies an absolute intensity already at the "
                "target plane; combining it with (ε, T) over-specifies "
                "the target (RADIANT would have two inconsistent ways "
                "to compute the at-aperture signal)."
            ),
            action=(
                "Remove source.target.temperature and .emissivity when "
                "using source.target.user_intensity_path; or remove "
                "user_intensity_path to use the legacy (ε, T) form."
            ),
            context={
                "temperature_set": _is_user_set(params, "source.target.temperature"),
                "emissivity_set": _is_user_set(params, "source.target.emissivity"),
            },
        )

    csv_path = str(path_rv.value)

    # Load CSV → SpectralData on the file's native grid.  Rule 15:
    # load_user_intensity_csv raises ParameterBoundsError on missing /
    # malformed / empty files with actionable context.
    I_native = load_user_intensity_csv(csv_path)

    # Boundary guard (Rule 15): validate native values here so a negative
    # CSV entry surfaces as a ParameterBoundsError before the grid
    # resample or descriptor construction.
    _validate_I_t_source(np.asarray(I_native.values, dtype=np.float64))

    # Resample onto the chain grid via linear interpolation.  Extrapolation
    # outside the native grid raises below by checking the bounds up
    # front — matches TabulatedRadianceSource's contract for S8.
    lam = np.asarray(wavelength_um, dtype=np.float64)
    src_wl = np.asarray(I_native.wavelength_um, dtype=np.float64)
    if lam[0] < src_wl[0] or lam[-1] > src_wl[-1]:
        raise ParameterBoundsError(
            what=(
                "source._inferrer: user_intensity CSV grid "
                f"[{src_wl[0]:.4f}, {src_wl[-1]:.4f}] µm does not cover "
                f"the chain wavelength grid "
                f"[{lam[0]:.4f}, {lam[-1]:.4f}] µm"
            ),
            why=(
                "Extrapolating user-supplied intensity outside the "
                "tabulated grid would silently invent physics.  Rule 17 "
                "— the loader refuses rather than falling back to "
                "zero-fill or constant extrapolation."
            ),
            action=(
                "Extend the CSV wavelength coverage to span the chain "
                "grid, or tighten source.wavelength_min/max so the "
                "chain grid fits inside the CSV grid."
            ),
            context={
                "csv_range_um": (float(src_wl[0]), float(src_wl[-1])),
                "chain_range_um": (float(lam[0]), float(lam[-1])),
            },
        )
    I_on_grid = np.interp(lam, src_wl, I_native.values)

    I_sd = SpectralData(
        name="source.target.user_intensity",
        wavelength_um=lam,
        values=np.asarray(I_on_grid, dtype=np.float64),
        unit="W/sr/um",
        source=(f"source.converters.user_intensity (CSV → chain grid: {csv_path})"),
    )

    return user_intensity_to_descriptor(
        I_t_source=I_sd,
        scene_type=scene_type,  # type: ignore[arg-type]
        target_location=target_location,  # type: ignore[arg-type]
        no_atmosphere_subcase=(  # type: ignore[arg-type]
            no_atmosphere_subcase or None
        ),
        h_tgt=h_tgt,
    )


def _build_target_descriptor(
    params: ParameterSet,
    wavelength_um: np.ndarray,
    scene_type: str,
    target_location: str,
    no_atmosphere_subcase: str,
    h_tgt: float | None,
) -> TargetDescriptor:
    """Dispatch on (target_location, scene_type) → TargetDescriptor variant.

    Stage-2 scope: only ``T1Thermal`` is materialised from the legacy
    parameter surface (``source.target.emissivity`` + ``source.target.temperature``).
    The other variants (T2/T3/T5) require material/atmosphere data not yet
    on the legacy surface; they will be populated in Stages 3, 5, and 7
    when the corresponding surfaces arrive.  Today, every scenario in
    [tests/integration/snapshots/option_c_baseline.yaml](../../../tests/integration/snapshots/option_c_baseline.yaml)
    carries a scalar ε+T; T1 is the correct v1 variant for them.

    Parameters
    ----------
    wavelength_um:
        Chain wavelength grid (canonical µm array from ChainState).
    scene_type, target_location, no_atmosphere_subcase, h_tgt:
        Resolved axes from the other inferrer helpers.
    """
    # S11 fast path — user-supplied brightness temperature.
    s11 = _maybe_build_from_brightness_temperature(
        params=params,
        wavelength_um=wavelength_um,
        scene_type=scene_type,
        target_location=target_location,
        no_atmosphere_subcase=no_atmosphere_subcase,
        h_tgt=h_tgt,
    )
    if s11 is not None:
        return s11

    # S12 fast path — user-supplied band-averaged radiance temperature.
    s12 = _maybe_build_from_radiance_temperature(
        params=params,
        wavelength_um=wavelength_um,
        scene_type=scene_type,
        target_location=target_location,
        no_atmosphere_subcase=no_atmosphere_subcase,
        h_tgt=h_tgt,
    )
    if s12 is not None:
        return s12

    # S4/S5/S6 fast path — user-supplied reflectance (pure-reflective target).
    s4 = _maybe_build_from_reflectance(
        params=params,
        wavelength_um=wavelength_um,
        scene_type=scene_type,
        target_location=target_location,
        no_atmosphere_subcase=no_atmosphere_subcase,
        h_tgt=h_tgt,
    )
    if s4 is not None:
        return s4

    # S8 fast path — user-supplied absolute radiance at the target plane.
    s8 = _maybe_build_from_user_radiance(
        params=params,
        wavelength_um=wavelength_um,
        scene_type=scene_type,
        target_location=target_location,
        no_atmosphere_subcase=no_atmosphere_subcase,
        h_tgt=h_tgt,
    )
    if s8 is not None:
        return s8

    # S10 fast path — user-supplied absolute intensity at the target
    # plane (point-source; ADR-0004).
    s10 = _maybe_build_from_user_intensity(
        params=params,
        wavelength_um=wavelength_um,
        scene_type=scene_type,
        target_location=target_location,
        no_atmosphere_subcase=no_atmosphere_subcase,
        h_tgt=h_tgt,
    )
    if s10 is not None:
        return s10

    T_t: float = params.get("source.target.temperature")
    epsilon_scalar: float = params.get("source.target.emissivity")

    # Build the grey ε(λ) SpectralData once — reused for both the target
    # emissivity and the background fallback below.
    epsilon = _grey_spectraldata(
        wavelength_um=wavelength_um,
        value=epsilon_scalar,
        name="source.target.emissivity",
        unit="",
    )

    # Matrix §3.2 line 156: T1Thermal is the correct v1 variant for the
    # legacy ε+T parameter surface.  T2/T3/T5 enter the pipeline in later
    # stages when reflectance, mixed, or at-aperture data are surfaced.
    #
    # Q3 shape-wins precedence (matrix §4, resolved 2026-04-21) is applied
    # inside ``_resolve_projected_area_and_shape`` — shared with the S11
    # brightness-temperature branch.
    A_t, shape_obj = _resolve_projected_area_and_shape(params, target_location)

    # Silence the MWIR non-mixed warning emitted by T1Thermal.__post_init__
    # during Stage-2 back-compat inference.  The scalar-ε legacy surface
    # cannot distinguish "MWIR with ρ ≈ 0 (hot target)" from "MWIR that
    # should really use T3 mixed", so firing the warning here produces
    # noise on every MWIR scenario in the snapshot.  Stage 3/6 addresses
    # MWIR mixed explicitly; until then the warning suppression is
    # scoped narrowly to this back-compat construction only.
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        return T1Thermal(
            scene_type=scene_type,  # type: ignore[arg-type]
            target_location=target_location,  # type: ignore[arg-type]
            no_atmosphere_subcase=(
                no_atmosphere_subcase or None  # type: ignore[arg-type]
            ),
            h_tgt=h_tgt,
            epsilon=epsilon,
            T_t=T_t,
            A_t=A_t,
            shape=shape_obj,
        )


# ---------------------------------------------------------------------------
# Background descriptor construction
# ---------------------------------------------------------------------------


def _build_background_descriptor(
    params: ParameterSet,
    wavelength_um: np.ndarray,
    target_location: str,
    no_atmosphere_subcase: str,
    scene_type: str,
) -> BackgroundDescriptor | None:
    """Build the background descriptor matching ``target_location`` / subcase.

    Stage-2 policy (matrix §3.2 / Decision #13):

      * ``at_aperture`` → :class:`AtApertureBackground` (L_bg = None until
        users supply it).
      * ``no_atmosphere`` + ``space`` → :class:`ColdSpaceBackground`.
      * ``no_atmosphere`` + ``ground_test`` / ``lab_test`` → requires
        :class:`UserSpectralBackground`; the legacy parameter surface has
        no L_bg path, so Stage 2 raises a clear error pointing at Stage 7.
      * ``terrestrial`` / ``airborne`` + sub_pixel or point_source →
        :class:`GroundBackground` placeholder built from
        ``source.background.temperature`` and a grey ε_g from
        ``source.background.emissivity`` (warns — Stage 3 replaces).
      * ``terrestrial`` / ``airborne`` + extended → ``None`` (matrix
        Decision #13: computed-extended cells skip the background
        photon term in SpectralIntegrationStage).

    Returns None when no background variant applies (extended computed
    cells).
    """
    if target_location == "at_aperture":
        # Matrix §3.2 line 365: at_aperture paired with
        # AtApertureBackground; L_bg = None treated as zero at assembly.
        return AtApertureBackground(L_bg_aperture=None)

    if target_location == "no_atmosphere":
        if no_atmosphere_subcase == "space":
            # Matrix §3.3 line 300: space sub-case → ColdSpaceBackground
            # (default, no user input required).  Default illumination is
            # solar TOA unattenuated; the assembly arm reads E_TOA directly
            # from ExoAtmosphere.evaluate() which populates it from the
            # built-in solar spectrum (radiant.core.solar).  Stage 7 adds
            # an Earth-intercept precondition on the LOS — see
            # atmosphere.assembly.validate_no_atmosphere_subcase.
            return ColdSpaceBackground()
        if no_atmosphere_subcase in ("ground_test", "lab_test"):
            # Matrix §7: ground_test / lab_test require a
            # UserSpectralBackground (L_bg(λ) on the chain grid).  The
            # legacy parameter surface has no user-L_bg path — a user
            # driving the chain through the legacy YAML must construct a
            # UserSpectralBackground manually and inject it into
            # stage_outputs['source']['background'] before AtmosphereStage
            # runs (this is the integration test pattern in Stage 7 of
            # the Option C plan; a richer YAML-driven path is the
            # SensorDescriptor / illumination follow-on).
            #
            # Raising here is Rule 17 (no silent failure): the inferrer
            # has no default to give and the Stage-7 AtmosphereStage
            # validator will likewise raise.  We raise early so the user
            # sees a clear, actionable error at descriptor construction
            # rather than deep in assembly.
            raise ParameterBoundsError(
                what=(
                    f"source._inferrer: no_atmosphere_subcase="
                    f"{no_atmosphere_subcase!r} requires a user-supplied "
                    f"UserSpectralBackground; the legacy parameter "
                    f"surface does not carry L_bg(λ)."
                ),
                why=(
                    "Matrix §7: ground_test and lab_test sub-cases have no "
                    "sensible default for test-range or chamber radiance. "
                    "The user must supply UserSpectralBackground(L_bg: "
                    "SpectralData in W/m²/sr/µm).  The Option C "
                    "SourceStage legacy inferrer cannot construct L_bg "
                    "from scalar parameters; this is a Stage-7 preset "
                    "that runs through a direct-descriptor pathway "
                    "(tests inject a UserSpectralBackground into "
                    "stage_outputs['source']['background']).  The "
                    "illumination follow-on ADR will add a YAML-driven "
                    "path."
                ),
                action=(
                    "Either (a) construct a UserSpectralBackground "
                    "manually and publish it as "
                    "stage_outputs['source']['background'] (see "
                    "tests/integration/test_no_atm_subcases.py for the "
                    "canonical pattern), or (b) leave "
                    "source.target_location at 'auto' for a space / "
                    "terrestrial / airborne scenario."
                ),
                context={
                    "target_location": target_location,
                    "no_atmosphere_subcase": no_atmosphere_subcase,
                },
            )
        # Unknown sub-case — the descriptor constructor already rejects
        # these; this arm is defensive.
        raise ParameterBoundsError(  # pragma: no cover
            what=(f"source._inferrer: unknown no_atmosphere_subcase={no_atmosphere_subcase!r}"),
            why="Valid sub-cases are 'space', 'ground_test', 'lab_test'.",
            action="Set no_atmosphere_subcase to one of the three values.",
            context={"no_atmosphere_subcase": no_atmosphere_subcase},
        )

    # terrestrial / airborne: background depends on scene_type.
    # Matrix Decision #13: extended terrestrial/airborne = no bg term.
    if scene_type == "extended":
        # Decision #15: source.background.* is adjacent-scene only; if the
        # user explicitly set these parameters for an extended scene they
        # will be silently ignored by downstream assembly.  Warn loudly
        # (Rule 17) so the user sees the contract mismatch.
        try:
            bg_t_rv = params.get_resolved("source.background.temperature")
            bg_e_rv = params.get_resolved("source.background.emissivity")
            t_user_set = bg_t_rv.provenance is not Provenance.DEFAULT
            e_user_set = bg_e_rv.provenance is not Provenance.DEFAULT
        except KeyError:
            t_user_set = False
            e_user_set = False
        if t_user_set or e_user_set:
            fields = []
            if t_user_set:
                fields.append(f"source.background.temperature = {bg_t_rv.value} K")
            if e_user_set:
                fields.append(f"source.background.emissivity = {bg_e_rv.value}")
            warnings.warn(
                (
                    "source._inferrer: extended terrestrial/airborne scene "
                    "was configured with user-set "
                    f"{', '.join(fields)}.  Per ADR-0002 Decision #15, "
                    "source.background.* parameters are adjacent-scene only "
                    "(sub_pixel / point_source).  For extended scenes the "
                    "background photon term is computed from the atmospheric "
                    "downwelling / ground reflectance physics and these "
                    "values are ignored.  Remove them from the scenario to "
                    "silence this warning."
                ),
                UserWarning,
                stacklevel=3,
            )
        return None

    # sub_pixel / point_source: need a GroundBackground.  Stage 2 has no
    # spectral-ε_g surface yet (the backgrounds subsystem loads that),
    # so we build a placeholder from the legacy scalar background params
    # and emit a UserWarning per Rule 17.
    bg_T: float = params.get("source.background.temperature")
    bg_eps_scalar: float = params.get("source.background.emissivity")
    warnings.warn(
        (
            "source._inferrer: terrestrial/airborne sub-pixel scenario is "
            "using a Stage-2 GroundBackground placeholder built from "
            "scalar source.background.temperature / .emissivity.  Stage 3 "
            "of the Option C plan will replace this with spectral "
            "emissivity inference.  Until then, spectral ε_g(λ) is grey."
        ),
        UserWarning,
        stacklevel=3,
    )
    epsilon_g = _grey_spectraldata(
        wavelength_um=wavelength_um,
        value=bg_eps_scalar,
        name="source.background.emissivity",
        unit="",
    )
    return GroundBackground(epsilon_g=epsilon_g, T_g=bg_T)


# ---------------------------------------------------------------------------
# Public entrypoint
# ---------------------------------------------------------------------------


def infer_descriptors(
    params: ParameterSet,
    wavelength_um: np.ndarray,
) -> tuple[TargetDescriptor, BackgroundDescriptor | None, LineOfSightGeometry | None]:
    """Build the three Option-C descriptors from a legacy ParameterSet.

    This is the Stage-2 bridge: every YAML in
    ``examples/`` and ``tests/integration/snapshots/option_c_baseline.yaml``
    passes through this function with zero physics change downstream
    (the legacy ``at_target`` frame and ``L_background`` stage_output are
    still published in parallel).  Stage 3 starts consuming the
    descriptors in AtmosphereStage; Stage 4 removes the legacy path.

    Parameters
    ----------
    params:
        Resolved :class:`ParameterSet` carrying the full schema from every
        stage (SourceStage accesses both its own parameters and
        ``atmosphere.model`` / ``detector.pixel_pitch_x_um`` /
        ``optics.focal_length_m`` to mirror the legacy
        ``_classify_regime`` logic).
    wavelength_um:
        Chain wavelength grid (canonical µm array).  Used for the
        scalar-to-spectral lift of ε / ε_g.

    Returns
    -------
    target:
        :class:`TargetDescriptor` (currently always :class:`T1Thermal`
        from the scalar ε+T legacy surface; see ``_build_target_descriptor``).
    background:
        :class:`BackgroundDescriptor` or ``None`` for extended
        terrestrial/airborne (Decision #13).
    los:
        :class:`LineOfSightGeometry` or ``None`` for at_aperture.
    """
    # --- Scene type ---
    # Explicit user value wins; sentinel 'auto' triggers inference.
    scene_type_user: str = params.get("source.scene_type")
    if scene_type_user != "auto":
        scene_type = scene_type_user
    else:
        pixel_pitch_m: float = params.get("detector.pixel_pitch_x_um")
        focal_length_m: float = params.get("optics.focal_length_m")
        scene_type = _infer_scene_type(params, pixel_pitch_m, focal_length_m)

    # --- Target location & sub-case ---
    target_location_user: str = params.get("source.target_location")
    subcase_user: str = params.get("source.no_atmosphere_subcase")
    if target_location_user != "auto":
        target_location = target_location_user
        no_atmosphere_subcase = subcase_user
        # Matrix §7: no_atmosphere requires a subcase.  If the user set
        # target_location='no_atmosphere' but left subcase = "" (default),
        # the TargetDescriptor constructor will raise with the canonical
        # message; we let that happen rather than inferring a subcase
        # silently (Rule 17).
    else:
        target_location, no_atmosphere_subcase = _infer_target_location_and_subcase(params)
        # If the user explicitly set a subcase while target_location was
        # auto, honor it so explicit subcase still wins when paired with
        # inferred location.  The descriptor constructor checks the
        # matrix §7 pairing rule.
        if subcase_user:
            no_atmosphere_subcase = subcase_user

    # --- h_tgt (target altitude) ---
    # Matrix §3.2: h_tgt = geometry.target_altitude_m for terrestrial
    # (Stage 5 A3 — airborne partial-column support); None for
    # at_aperture; still 0 for no_atmosphere=space (the space LOS is
    # "above everything", and h_tgt is irrelevant for the no_atm path).
    # Computed before LOS so the target descriptor can be constructed
    # first; the LOS's T1/T2/T3 routing predicate (CU-009) reads the
    # descriptor's runtime type to decide whether to populate
    # ``theta_s`` / ``delta_phi``.
    if target_location == "at_aperture":
        h_tgt: float | None = None
    elif target_location == "no_atmosphere":
        h_tgt = 0.0
    else:
        try:
            h_tgt_raw = float(params.get("geometry.target_altitude_m"))
        except KeyError:
            h_tgt_raw = 0.0
        h_tgt = h_tgt_raw if h_tgt_raw >= 0.0 else 0.0

    # --- Construct descriptors ---
    # Target first so CU-009's T1/T2/T3 routing predicate in _infer_los
    # can dispatch on the runtime descriptor type.
    target = _build_target_descriptor(
        params=params,
        wavelength_um=wavelength_um,
        scene_type=scene_type,
        target_location=target_location,
        no_atmosphere_subcase=no_atmosphere_subcase,
        h_tgt=h_tgt,
    )

    # --- LOS geometry ---
    los = _infer_los(target_location, params, target_descriptor=target)
    background = _build_background_descriptor(
        params=params,
        wavelength_um=wavelength_um,
        target_location=target_location,
        no_atmosphere_subcase=no_atmosphere_subcase,
        scene_type=scene_type,
    )

    return target, background, los


# ---------------------------------------------------------------------------
# Round-trip helper (Category B serialization requirement)
# ---------------------------------------------------------------------------


def descriptors_to_params(
    target: TargetDescriptor,
    background: BackgroundDescriptor | None,
    los: LineOfSightGeometry | None,
) -> dict[str, Any]:
    """Extract the legacy parameter subset carried by a descriptor trio.

    Returns a flat dot-path dict of **only** the source-owned parameters
    that the descriptors round-trip.  Atmosphere.*, detector.*, optics.*,
    and other stage parameters are NOT included — those cross the stage
    boundary and never ride on descriptors.  This is the lossy boundary
    documented in the module docstring.

    Used by ``test_inferrer.py::test_round_trip`` to confirm the Stage-2
    bridge is a pure identity on the subset it claims to cover.
    """
    d: dict[str, Any] = {}

    # Target-location axes.
    d["source.scene_type"] = target.scene_type
    d["source.target_location"] = target.target_location
    d["source.no_atmosphere_subcase"] = target.no_atmosphere_subcase or ""

    # Thermal / reflective payload.  Only T1Thermal is synthesised in
    # Stage 2; other variants are surfaced in later stages.
    if isinstance(target, (T1Thermal, T3Mixed)):
        d["source.target.temperature"] = float(target.T_t)
        # Grey emissivity is a constant array; pull the first sample.
        if target.epsilon is not None and target.epsilon.values.size > 0:
            d["source.target.emissivity"] = float(target.epsilon.values[0])
        d["source.target.projected_area_m2"] = float(target.A_t) if target.A_t is not None else 0.0
    elif isinstance(target, T2Reflective):
        d["source.target.projected_area_m2"] = float(target.A_t) if target.A_t is not None else 0.0
    elif isinstance(target, T5AtAperture):
        # At-aperture: no target params round-trip.
        pass

    # fill_fraction is carried implicitly by scene_type in Stage 2; the
    # round-trip on fill_fraction is tested separately.

    # Background round-trip (scalar GroundBackground only).
    if isinstance(background, GroundBackground):
        d["source.background.temperature"] = float(background.T_g)
        if background.epsilon_g is not None and background.epsilon_g.values.size > 0:
            d["source.background.emissivity"] = float(background.epsilon_g.values[0])

    # UserSpectralBackground carries an L_bg spectrum that does not
    # round-trip to the legacy scalar surface; silence is the honest answer.
    _ = (background, los, UserSpectralBackground)  # mark used for lint

    return d


__all__ = [
    "descriptors_to_params",
    "infer_descriptors",
]
