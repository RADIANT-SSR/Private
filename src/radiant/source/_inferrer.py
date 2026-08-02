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
``geometry.target.projected_area_m2``, ``source.target.fill_fraction``).

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

import logging
import math
import warnings
from typing import Any

import numpy as np

from radiant.core.blackbody import planck_spectral_radiance
from radiant.core.descriptors import (
    AtApertureBackground,
    BackgroundDescriptor,
    ColdSpaceBackground,
    GroundBackground,
    SkyBackground,
    T1Thermal,
    T2Reflective,
    T3Mixed,
    T5AtAperture,
    T7IntensityAtSource,
    TargetDescriptor,
    UserSpectralBackground,
    _is_mwir_spectral_data,
)
from radiant.core.los_geometry import LineOfSightGeometry
from radiant.core.los_termination import classify_los_termination
from radiant.core.parameters import ParameterBoundsError, ParameterSet, Provenance
from radiant.core.regime import (
    REGIME_EXTENDED_IFOV_MULTIPLE,
    REGIME_POINT_SOURCE_IFOV_MULTIPLE,
)
from radiant.core.spectral import SpectralData
from radiant.source.converters._csv import load_two_column_csv
from radiant.source.converters.brightness_temperature import (
    brightness_temperature_to_descriptor,
    load_brightness_temperature_csv,
)
from radiant.source.converters.point_intensity import (
    blackbody_point_intensity,
    scalar_band_intensity,
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
from radiant.source.target_spec import (
    check_brightness_temperature_conflicts,
    check_emissivity_path_conflicts,
    check_intensity_door_extent_conflicts,
    check_point_intensity_conflicts,
    check_radiance_temperature_conflicts,
    check_reflectance_conflicts,
    check_user_intensity_conflicts,
    check_user_radiance_conflicts,
)

logger = logging.getLogger(__name__)

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
    raw_area: float = params.get("geometry.target.projected_area_m2")
    # Canonical name geometry.target_range_m (ADR-0006); the old
    # source.target.range_m survives as a deprecated alias for users.
    raw_range: float = params.get("geometry.target_range_m")
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
    # as _classify_regime (shared via core.regime, CU-044).
    angular_extent = math.sqrt(projected_area_m2) / range_m
    ifov = pixel_pitch_m / focal_length_m
    if angular_extent <= REGIME_POINT_SOURCE_IFOV_MULTIPLE * ifov:
        return "point_source"
    if angular_extent >= REGIME_EXTENDED_IFOV_MULTIPLE * ifov:
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
    # Gap 59: day/night toggle. 'night' removes the solar terms entirely
    # (theta_s = None → assembly skips direct-solar reflection and the
    # single-scatter solar sky) while thermal self-emission and reflected
    # thermal downwelling remain. 'day' (default) preserves the historical
    # behavior, where the solar_zenith_rad schema default gave every
    # T2/T3 target a daytime sun.
    try:
        solar_illumination: str = str(params.get("geometry.solar_illumination"))
    except KeyError:
        solar_illumination = "day"
    if solar_illumination == "day" and isinstance(target_descriptor, (T2Reflective, T3Mixed)):
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


def _no_atmosphere_h_tgt(scene_los: LineOfSightGeometry) -> float:
    """Target altitude the ``no_atmosphere`` arm carries on the adjusted LOS.

    Historically this was unconditionally ``0.0``: the no-atmosphere path
    never integrates a column, so the only consumer of ``h_tgt`` is the
    Earth-limb intercept check, which was written against a surface-anchored
    target.  That override is kept **verbatim for every down-looking scene**
    (``h_sensor > h_tgt``) — which is every pre-ADR-0011 scene — so no
    existing result moves by a bit.

    Since ADR-0011 the LOS also carries ``h_sensor``, and
    :class:`~radiant.core.los_geometry.LineOfSightGeometry` enforces the
    altitude/hemisphere invariant (``h_sensor > h_tgt ⟺ θ_o < π/2``).  On an
    up-looking or level path, rewriting ``h_tgt`` to 0 while keeping
    ``h_sensor`` and ``θ_o`` fabricates a triple that violates that invariant
    (e.g. LEO→GEO: ``h_sensor`` = 500 km, ``θ_o`` = π, ``h_tgt`` → 0), so the
    contract object rightly refuses to be built.  The real target altitude is
    kept there: it is self-consistent, and the intercept check reads the true
    segment instead of a surface-anchored stand-in.
    """
    if scene_los.h_sensor is None or scene_los.h_sensor > scene_los.h_tgt:
        return 0.0
    return scene_los.h_tgt


def _adjust_scene_los(
    scene_los: LineOfSightGeometry,
    target_location: str,
    *,
    target_descriptor: TargetDescriptor | None,
) -> LineOfSightGeometry | None:
    """Descriptor-adjust the GeometryStage-published scene LOS (ADR-0006).

    GeometryStage publishes *scene* geometry: theta_s is set whenever the
    scene is lit (day mode), independent of target type.  Whether a target
    consumes the solar terms is a radiometric decision that stays here:

      * ``at_aperture``     → ``None`` (the pass-through arm never
        evaluates an atmospheric path — matrix §4.3), matching
        :func:`_infer_los`.
      * ``no_atmosphere``   → ``h_tgt`` forced to 0.0 **on a down-looking
        path**, matching :func:`_infer_los` ("the space LOS is above
        everything"; the no-atm path ignores it, and the Earth-limb
        intercept check keeps its legacy geometry).  See
        :func:`_no_atmosphere_h_tgt` for why the override stops at the
        down-looking case since ADR-0011.
      * T1 (pure-thermal) and the user-supplied-radiance doors → solar
        fields stripped (CU-009 predicate: a pure-thermal radiance has no
        solar leg).  Night mode arrives already stripped from GeometryStage.
      * ``T7IntensityAtSource`` **keeps** the solar fields (CU-258).  The
        intensity door says what the *target* emits; it says nothing about
        the **sky**.  Stripping θ_s there made the atmosphere build a purely
        thermal sky and path radiance (~1e-18 W/m²/sr/µm in the VIS), so
        every daytime intensity-door scene lost the sky pedestal — which for
        a visible measurement is the dominant noise term, not a correction.
    """
    if target_location == "at_aperture":
        return None
    h_tgt = (
        _no_atmosphere_h_tgt(scene_los) if target_location == "no_atmosphere" else scene_los.h_tgt
    )
    # CU-258: T7 joins the solar-keeping set. The predicate asks "does this
    # scene have a sun the atmosphere should know about?", not "does the target
    # reflect?" — an intensity door still sits under a lit sky.
    if isinstance(target_descriptor, (T2Reflective, T3Mixed, T7IntensityAtSource)):
        theta_s, delta_phi = scene_los.theta_s, scene_los.delta_phi
    else:
        theta_s, delta_phi = None, None
    return LineOfSightGeometry(
        h_tgt=h_tgt,
        # ADR-0011 / GF-3: the sensor endpoint published by GeometryStage is
        # carried through unchanged — this function adjusts the *radiometric*
        # fields (h_tgt for no_atmosphere, the solar pair per target type),
        # never the sensor endpoint.  Dropping it here would leave the
        # atmosphere backends without the single source of truth they now
        # read (guardrail G2).
        h_sensor=scene_los.h_sensor,
        h_atm_top=scene_los.h_atm_top,
        theta_o=scene_los.theta_o,
        theta_s=theta_s,
        delta_phi=delta_phi,
    )


def _view_direction_from_los(
    params: ParameterSet,
    target_location: str,
    scene_theta_o: float | None = None,
) -> np.ndarray:
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
    # ADR-0006: prefer the theta_o GeometryStage resolved (covers the
    # off-nadir / ground-range / elevation input modes); the param read
    # is the legacy fallback for direct infer_descriptors callers.
    if scene_theta_o is not None:
        theta_o = float(scene_theta_o)
    else:
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


def _resolve_projected_area(
    params: ParameterSet,
    target_location: str,
    scene_theta_o: float | None = None,
) -> float | None:
    """Return ``A_t`` per the Q3 shape-wins rule.

    Shared between the legacy ε/T path in ``_build_target_descriptor``
    and the S11 brightness-temperature branch; both paths apply the
    shape-over-projected_area precedence identically.
    """
    projected_area: float = params.get("geometry.target.projected_area_m2")
    user_area_set: bool = projected_area > 0.0

    shape_obj: TargetShape | None = build_shape(params)
    if shape_obj is not None and target_location == "at_aperture":
        shape_name_tmp: str = params.get("geometry.target.shape")
        raise ParameterBoundsError(
            what=(
                f"geometry.target.shape = {shape_name_tmp!r} is incompatible "
                f"with target_location='at_aperture' (S9)"
            ),
            why=(
                "The at-aperture target spec form (S9) provides a "
                "spectral radiance already at the aperture plane — there "
                "is no scene-frame geometry for shape.projected_area "
                "to operate on."
            ),
            action=(
                "Either remove geometry.target.shape to use the at-aperture "
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
        shape_name: str = params.get("geometry.target.shape")
        view_dir = _view_direction_from_los(params, target_location, scene_theta_o)
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
    return A_t


def _maybe_build_from_brightness_temperature(
    params: ParameterSet,
    wavelength_um: np.ndarray,
    scene_type: str,
    target_location: str,
    no_atmosphere_subcase: str,
    h_tgt: float | None,
    scene_theta_o: float | None = None,
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

    # CU-244: the exclusivity guards for this door live in
    # radiant.source.target_spec (shared with the resolve-time seam
    # Sensor.validate_target_spec) — same order, same what/why/action.
    check_brightness_temperature_conflicts(params)

    A_t = _resolve_projected_area(params, target_location, scene_theta_o)

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
    )


def _maybe_build_from_radiance_temperature(
    params: ParameterSet,
    wavelength_um: np.ndarray,
    scene_type: str,
    target_location: str,
    no_atmosphere_subcase: str,
    h_tgt: float | None,
    scene_theta_o: float | None = None,
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

    # CU-244: exclusivity guards extracted to radiant.source.target_spec
    # (shared with the resolve-time seam). The band completeness check above
    # stays here — it is not an exclusivity rule.
    check_radiance_temperature_conflicts(params)

    T_R_K = float(t_r_rv.value)
    band = (float(lo_rv.value), float(hi_rv.value))

    A_t = _resolve_projected_area(params, target_location, scene_theta_o)
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
    )


def _maybe_build_from_reflectance(
    params: ParameterSet,
    wavelength_um: np.ndarray,
    scene_type: str,
    target_location: str,
    no_atmosphere_subcase: str,
    h_tgt: float | None,
    scene_theta_o: float | None = None,
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

    # CU-244: the exclusivity guards for this door live in
    # radiant.source.target_spec (shared with the resolve-time seam
    # Sensor.validate_target_spec) — same order, same what/why/action.
    check_reflectance_conflicts(params)

    A_t = _resolve_projected_area(params, target_location, scene_theta_o)

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
    )


def _maybe_build_from_user_radiance(
    params: ParameterSet,
    wavelength_um: np.ndarray,
    scene_type: str,
    target_location: str,
    no_atmosphere_subcase: str,
    h_tgt: float | None,
    scene_theta_o: float | None = None,
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
    (each rejects S8 symmetrically); the guards this door owns — the
    legacy (ε, T) surface, and S10 — live in
    :func:`radiant.source.target_spec.check_user_radiance_conflicts`
    (CU-293), shared with the resolve-time seam.
    """
    path_rv = params.get_resolved("source.target.user_radiance_path")
    path_user = path_rv.provenance is not Provenance.DEFAULT and bool(path_rv.value)
    if not path_user:
        return None

    # CU-293 (folded CU-294): the exclusivity guards for this door live in
    # radiant.source.target_spec (shared with the resolve-time seam
    # Sensor.validate_target_spec) — same order, same what/why/action.
    check_user_radiance_conflicts(params)

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

    A_t = _resolve_projected_area(params, target_location, scene_theta_o)
    return user_radiance_to_descriptor(
        L_t_source=L_sd,
        scene_type=scene_type,  # type: ignore[arg-type]
        target_location=target_location,  # type: ignore[arg-type]
        no_atmosphere_subcase=(  # type: ignore[arg-type]
            no_atmosphere_subcase or None
        ),
        h_tgt=h_tgt,
        A_t=A_t,
    )


def _maybe_build_from_point_intensity(
    params: ParameterSet,
    wavelength_um: np.ndarray,
    scene_type: str,
    target_location: str,
    no_atmosphere_subcase: str,
    h_tgt: float | None,
) -> TargetDescriptor | None:
    """Return an S10 T7IntensityAtSource from the point-intensity convenience inputs (Gap B).

    Two opt-in ways to give a point-source intensity without a CSV
    (:mod:`radiant.source.converters.point_intensity`):

    * **Blackbody** — ``point_intensity_temperature_K`` (+ ``_area_m2``, ``_emissivity``)
      → ``I(λ) = ε·A·B(λ,T)``.
    * **Scalar** — ``point_intensity_band_W_per_sr`` → a spectrally flat ``I(λ)`` whose
      band integral equals the given value.

    Both build ``I(λ)`` on the chain grid and route through
    :func:`user_intensity_to_descriptor` (so CSV / blackbody / scalar converge on one
    T7 path). ``scene_type='point_source'`` is enforced there. Set-detection is
    provenance-based; the two modes and the (ε, T)/CSV paths are mutually exclusive —
    those guards live in
    :func:`radiant.source.target_spec.check_point_intensity_conflicts` (CU-293),
    shared with the resolve-time seam.
    """
    bb_set = _is_user_set(params, "source.target.point_intensity_temperature_K")
    scalar_set = _is_user_set(params, "source.target.point_intensity_band_W_per_sr")
    if not bb_set and not scalar_set:
        return None

    # CU-256: refuse a declared target extent at the door, BEFORE T7 publishes
    # its fictitious reference area (which would silently discard the extent).
    check_intensity_door_extent_conflicts(params)

    # CU-293 (folded CU-294): the remaining exclusivity guards for this door
    # live in radiant.source.target_spec (shared with the resolve-time seam
    # Sensor.validate_target_spec) — same order, same what/why/action.
    check_point_intensity_conflicts(params)

    lam = np.asarray(wavelength_um, dtype=np.float64)
    if bb_set:
        temperature_K = float(params.get("source.target.point_intensity_temperature_K"))
        area_m2 = float(params.get("source.target.point_intensity_area_m2"))
        emissivity = float(params.get("source.target.point_intensity_emissivity"))
        if area_m2 <= 0.0:
            raise ParameterBoundsError(
                what=(
                    f"source.target.point_intensity_area_m2 = {area_m2} m² must be > 0 for a "
                    "blackbody point source"
                ),
                why=(
                    "The emitting area scales the intensity I(λ) = ε·A·B(λ,T); "
                    "zero area emits nothing."
                ),
                action=(
                    "Set source.target.point_intensity_area_m2 to the emitter's projected area "
                    "[m²]."
                ),
                context={"point_intensity_area_m2": area_m2},
            )
        i_values = blackbody_point_intensity(lam, temperature_K, area_m2, emissivity)
        source_str = (
            f"source.converters.point_intensity blackbody "
            f"(ε={emissivity}, A={area_m2} m², T={temperature_K} K)"
        )
    else:
        band_W_per_sr = float(params.get("source.target.point_intensity_band_W_per_sr"))
        filter_min_um = float(params.get("spectral_integration.filter_min_um"))
        filter_max_um = float(params.get("spectral_integration.filter_max_um"))
        i_values = scalar_band_intensity(lam, band_W_per_sr, filter_min_um, filter_max_um)
        source_str = (
            f"source.converters.point_intensity scalar "
            f"({band_W_per_sr} W/sr over [{filter_min_um}, {filter_max_um}] µm, band-flat)"
        )

    i_sd = SpectralData(
        name="source.target.point_intensity",
        wavelength_um=lam,
        values=np.asarray(i_values, dtype=np.float64),
        unit="W/sr/um",
        source=source_str,
    )
    return user_intensity_to_descriptor(
        I_t_source=i_sd,
        scene_type=scene_type,  # type: ignore[arg-type]
        target_location=target_location,  # type: ignore[arg-type]
        no_atmosphere_subcase=(no_atmosphere_subcase or None),  # type: ignore[arg-type]
        h_tgt=h_tgt,
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
    rejects S10 symmetrically); the guard this door owns — the legacy
    (ε, T) surface — lives in
    :func:`radiant.source.target_spec.check_user_intensity_conflicts`
    (CU-293), shared with the resolve-time seam.
    """
    path_rv = params.get_resolved("source.target.user_intensity_path")
    path_user = path_rv.provenance is not Provenance.DEFAULT and bool(path_rv.value)
    if not path_user:
        return None

    # CU-256: refuse a declared target extent at the door, BEFORE T7 publishes
    # its fictitious reference area (which would silently discard the extent).
    check_intensity_door_extent_conflicts(params)

    # CU-293 (folded CU-294): the remaining exclusivity guard for this door
    # lives in radiant.source.target_spec (shared with the resolve-time seam
    # Sensor.validate_target_spec) — same what/why/action.
    check_user_intensity_conflicts(params)

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


def _validate_emissivity_csv(eps_values: np.ndarray, *, csv_path: str) -> None:
    """Raise on ε outside ``[0, 1]`` at the CSV boundary (Rule 15, Gap 47)."""
    if eps_values.size == 0:
        raise ParameterBoundsError(
            what="emissivity_path: CSV produced zero-sample SpectralData",
            why="The converter needs at least one (λ, ε) pair to emit a descriptor.",
            action="Populate the CSV with at least two (wavelength_um, emissivity) rows.",
            context={"path": csv_path},
        )
    if np.any(eps_values < 0.0) or np.any(eps_values > 1.0):
        bad = float(eps_values.min()) if np.any(eps_values < 0.0) else float(eps_values.max())
        raise ParameterBoundsError(
            what=f"emissivity_path: ε = {bad} is outside [0, 1] in CSV {csv_path}",
            why="Emissivity is a dimensionless fraction in [0, 1] (Kirchhoff: ε ≤ 1).",
            action="Correct the CSV rows so every emissivity value is in [0, 1].",
            context={"path": csv_path, "bad_value": bad},
        )


def _load_emissivity_on_grid(
    params: ParameterSet, wavelength_um: np.ndarray
) -> SpectralData | None:
    """Spectral ε(λ) from ``source.target.emissivity_path``, or None (Gap 47).

    Raises if emissivity_path is combined with any conflicting surface — the
    thermal spectral-emissivity target is a single spec form (S1 with ε(λ)),
    so scalar ε, reflective, radiance, and brightness/radiance-temperature
    surfaces would over-specify it.  CU-318 moved that exclusivity guard into
    :func:`radiant.source.target_spec.check_emissivity_path_conflicts`, so it
    also runs at the resolve-time seam; the call below keeps the evaluate-time
    refusal (defence in depth) at the exact point the inline block occupied.
    """
    if not _is_user_set(params, "source.target.emissivity_path"):
        return None
    csv_path = str(params.get("source.target.emissivity_path"))
    if not csv_path:
        return None
    check_emissivity_path_conflicts(params)
    eps_native = load_two_column_csv(
        csv_path,
        value_unit="",
        column_label="emissivity",
        sd_name="source.target.emissivity",
        sd_source_prefix="source.converters.emissivity",
    )
    _validate_emissivity_csv(np.asarray(eps_native.values, dtype=np.float64), csv_path=csv_path)
    eps_on_grid = _resample_dimensionless_on_grid(
        eps_native, wavelength_um, quantity_label="emissivity"
    )
    return SpectralData(
        name="source.target.emissivity",
        wavelength_um=np.asarray(wavelength_um, dtype=np.float64),
        values=eps_on_grid,
        unit="",
        source=f"source.converters.emissivity (CSV → chain grid: {csv_path})",
    )


def _build_target_descriptor(
    params: ParameterSet,
    wavelength_um: np.ndarray,
    scene_type: str,
    target_location: str,
    no_atmosphere_subcase: str,
    h_tgt: float | None,
    scene_theta_o: float | None = None,
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
        scene_theta_o=scene_theta_o,
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
        scene_theta_o=scene_theta_o,
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
        scene_theta_o=scene_theta_o,
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
        scene_theta_o=scene_theta_o,
    )
    if s8 is not None:
        return s8

    # S10 convenience — point-source intensity from a blackbody emitter (ε, A, T)
    # or a scalar band-integrated flux (Gap B). Checked before the CSV S10 (both
    # build T7IntensityAtSource; they are mutually exclusive).
    s10b = _maybe_build_from_point_intensity(
        params=params,
        wavelength_um=wavelength_um,
        scene_type=scene_type,
        target_location=target_location,
        no_atmosphere_subcase=no_atmosphere_subcase,
        h_tgt=h_tgt,
    )
    if s10b is not None:
        return s10b

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

    # Spectral ε(λ) via source.target.emissivity_path (Gap 47) supersedes the
    # grey scalar; otherwise build the grey ε(λ) SpectralData. Either way the
    # descriptor consumes a SpectralData emissivity, so T1Thermal / T3Mixed
    # get ε(λ)·B(λ,T) with no further change.
    epsilon = _load_emissivity_on_grid(params, wavelength_um)
    if epsilon is None:
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
    # inside ``_resolve_projected_area`` — shared with the S11
    # brightness-temperature branch.
    A_t = _resolve_projected_area(params, target_location, scene_theta_o)

    # Matrix §3.2 routing (CU-007): MWIR-overlap targets default to
    # T3Mixed (Kirchhoff emit+reflect); the hot-target opt-out at
    # `source.target.is_hot_target` lets ρ ≈ 0 scenes (engine plumes,
    # missile signatures, calibration sources) keep T1Thermal where
    # the reflected terms are physically negligible.  The opt-out is
    # ignored on non-MWIR grids — LWIR routing is unconditional T1.
    is_hot_target = bool(params.get("source.target.is_hot_target"))
    is_mwir = _is_mwir_spectral_data(epsilon)
    if is_mwir and not is_hot_target:
        return T3Mixed(
            scene_type=scene_type,  # type: ignore[arg-type]
            target_location=target_location,  # type: ignore[arg-type]
            no_atmosphere_subcase=(
                no_atmosphere_subcase or None  # type: ignore[arg-type]
            ),
            h_tgt=h_tgt,
            epsilon=epsilon,
            T_t=T_t,
            A_t=A_t,
        )
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
    )


# ---------------------------------------------------------------------------
# Background descriptor construction
# ---------------------------------------------------------------------------


def _select_los_termination_background(
    los: LineOfSightGeometry | None,
) -> BackgroundDescriptor | None:
    """Rule-B background default for a non-down-looking LOS, or ``None``.

    Use-Case Matrix §3.2.5 (Rule B) selects the background by following the
    line of sight **past** the target and asking where it ends.  Before
    Geometry-Flexibility Phase 2 every expressible scene was down-looking, so
    the continuation always ran into the Earth and the ground default was the
    only reachable answer.  Phase 1 made up-looking and level scenes legal;
    their continuation ascends and terminates on space, which is matrix
    ``B2`` — :class:`~radiant.core.descriptors.SkyBackground`.

    Returns ``None`` for a missing LOS and for every **down-looking** path:
    the down-looking default is deliberately untouched so that no existing
    scene can change background (plan §3 principle 3, zero drift).  An
    explicit ``GroundBackground`` is still required for a down-looking
    sub-pixel / point-source scene exactly as before.

    Raises
    ------
    ParameterBoundsError
        If the continuation is a limb-crossing column (matrix ``B4``),
        declined for v1.x by ADR-0011 decision 5 — guarded, never
        approximated.
    """
    if los is None or los.los_direction == "down":
        return None

    termination = classify_los_termination(los)
    if termination.terminus == "space":
        return SkyBackground()
    if termination.terminus == "limb":
        raise ParameterBoundsError(
            what=(
                "source._inferrer: the line of sight continues past the target into a "
                f"limb-crossing column ({termination.detail})"
            ),
            why=(
                "Earthlimb backgrounds (Use-Case Matrix B4) are declined for v1.x — "
                "ADR-0011 decision 5 guards a limb termination with an actionable "
                "error naming the tangent altitude rather than approximating a "
                "radiance RADIANT cannot model."
            ),
            action=(
                "Tilt the geometry away from the limb, or supply an explicit "
                "BackgroundDescriptor via stage_outputs['source']['background'] if "
                "you have the background radiance from another source."
            ),
            context={
                "theta_o": los.theta_o,
                "h_tgt": los.h_tgt,
                "tangent_altitude_m": termination.tangent_altitude_m,
                "tangent_depression_m": termination.tangent_depression_m,
            },
        )
    # "earth" — an ascending continuation cannot reach it, so this is
    # unreachable for a non-down-looking LOS; fall back to the existing
    # defaults rather than inventing a new one.
    return None  # pragma: no cover


def _build_background_descriptor(
    params: ParameterSet,
    wavelength_um: np.ndarray,
    target_location: str,
    no_atmosphere_subcase: str,
    scene_type: str,
    background_emissivity: SpectralData | None = None,
    los: LineOfSightGeometry | None = None,
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
            # Gap 40: positive dark/lit assertion.  In the use-case matrix
            # "dark" means NO EXTERNAL ILLUMINATION (no lamp / no solar) —
            # thermal self-emission of a blackbody standard is the canonical
            # D-lab dark-cal scene.  'dark' is therefore validated against
            # user-configured illumination inputs (a reflectance-driven
            # target has nothing to reflect in a dark chamber, Rule 16);
            # 'lit' and '' change nothing radiometrically.
            lab_mode: str = params.get("source.lab_test_mode")
            if lab_mode == "dark" and _is_user_set(params, "source.target.reflectance"):
                refl: float = params.get("source.target.reflectance")
                raise ParameterBoundsError(
                    what=(
                        f"source.lab_test_mode='dark' but "
                        f"source.target.reflectance = {refl} was set"
                    ),
                    why=(
                        "'dark' asserts no external illumination (no lamp, "
                        "no solar) — a reflectance-driven target has nothing "
                        "to reflect in a dark chamber, so the configuration "
                        "is contradictory."
                    ),
                    action=(
                        "Remove source.target.reflectance (use a thermal "
                        "target for dark-chamber measurements), or drop "
                        "lab_test_mode='dark' for an illuminated scene."
                    ),
                    context={
                        "lab_test_mode": lab_mode,
                        "target_reflectance": refl,
                    },
                )
            # Gap 42: build the chamber / test-range background from the
            # config surface.  Decision #15 (ADR-0002) makes
            # source.background.* the *valid* adjacent-scene surface for the
            # no_atmosphere sub-cases (unlike extended, where it is
            # deprecated), so a grey-body chamber wall
            # L_bg(λ) = ε_bg · B(λ, T_bg) is the natural config-driven
            # UserSpectralBackground.  A user who has a measured L_bg(λ)
            # still injects a UserSpectralBackground directly into
            # stage_outputs['source']['background'].
            #
            # Rule 17: the chamber temperature has no universal default, so
            # if the user left source.background.temperature at its schema
            # default we warn that the ambient default was assumed rather
            # than silently baking it in.
            bg_T: float = params.get("source.background.temperature")
            bg_eps: float = params.get("source.background.emissivity")
            if not _is_user_set(params, "source.background.temperature"):
                warnings.warn(
                    f"source._inferrer: no_atmosphere_subcase="
                    f"{no_atmosphere_subcase!r} built a grey-body chamber "
                    f"background from the default source.background.temperature "
                    f"= {bg_T} K (ε = {bg_eps}). Set source.background.temperature "
                    "explicitly to the chamber / test-range wall temperature, or "
                    "inject a measured UserSpectralBackground(L_bg) via "
                    "stage_outputs['source']['background'].",
                    UserWarning,
                    stacklevel=3,
                )
            L_bg_vals = bg_eps * planck_spectral_radiance(wavelength_um, bg_T)
            L_bg = SpectralData(
                name="source.background.chamber",
                wavelength_um=np.asarray(wavelength_um, dtype=np.float64),
                values=np.asarray(L_bg_vals, dtype=np.float64),
                unit="W/m^2/sr/um",
                source=(
                    f"source._inferrer grey-body chamber background "
                    f"(ε={bg_eps}·B(T={bg_T} K); Gap 42)"
                ),
            )
            return UserSpectralBackground(L_bg=L_bg)
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
            # Warning-free-UX campaign: "these background.* params are ignored for
            # an extended scene" is a property of the config (Decision #15), not a
            # per-evaluate event — and the operative regime is already surfaced as
            # stage_outputs["source"]["regime_tentative"]. Log at debug rather than a
            # UserWarning on every evaluate.
            logger.debug(
                "source._inferrer: extended terrestrial/airborne scene was configured "
                "with user-set %s. Per ADR-0002 Decision #15, source.background.* are "
                "adjacent-scene only (sub_pixel / point_source); for extended scenes the "
                "background photon term is computed from the atmospheric downwelling / "
                "ground reflectance physics and these values are ignored. Remove them "
                "from the scenario to silence this note.",
                ", ".join(fields),
            )
        return None

    # sub_pixel / point_source with an up-looking or level LOS: Rule B says
    # the background is what the LOS runs into *past* the target, and for
    # those topologies that is the sky, not the ground (matrix B2).  Checked
    # before the ground branch so the ground default stays the answer for
    # every down-looking scene, byte-for-byte (zero drift).
    sky = _select_los_termination_background(los)
    if sky is not None:
        return sky

    # sub_pixel / point_source (down-looking): need a GroundBackground (CU-008).
    # Spectral ε_g(λ) comes from the API-layer injection
    # (source.background.material library entry or .emissivity_path CSV,
    # resolved pre-chain per Rule 6) when present; otherwise the scalar
    # source.background.emissivity is an explicit grey choice
    # (material="grey", the default) — no longer a warned placeholder.
    bg_T: float = params.get("source.background.temperature")
    if background_emissivity is not None:
        eps_vals = np.interp(
            np.asarray(wavelength_um, dtype=np.float64),
            np.asarray(background_emissivity.wavelength_um, dtype=np.float64),
            np.asarray(background_emissivity.values, dtype=np.float64),
        )
        bad = (eps_vals < 0.0) | (eps_vals > 1.0)
        if np.any(bad):
            raise ParameterBoundsError(
                what=(
                    "source background ε_g(λ) is outside [0, 1] after "
                    "resampling onto the chain grid"
                ),
                why="Emissivity is a dimensionless fraction of blackbody emission.",
                action=(
                    "Check the spectral-library entry / CSV covers the "
                    "chain wavelength range with values in [0, 1]."
                ),
                context={
                    "source": background_emissivity.source,
                    "min": float(eps_vals.min()),
                    "max": float(eps_vals.max()),
                },
            )
        epsilon_g = SpectralData(
            name="source.background.emissivity",
            wavelength_um=np.asarray(wavelength_um, dtype=np.float64),
            values=eps_vals,
            unit="",
            source=f"CU-008 spectral ε_g ({background_emissivity.source})",
        )
        return GroundBackground(epsilon_g=epsilon_g, T_g=bg_T)

    bg_eps_scalar: float = params.get("source.background.emissivity")
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
    background_emissivity: SpectralData | None = None,
    scene_los: LineOfSightGeometry | None = None,
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
    # ADR-0006: when SourceStage passes the GeometryStage-published scene
    # LOS, its theta_o feeds the shape view direction and the published
    # LOS becomes the atmosphere contract (descriptor-adjusted below).
    # scene_los=None is the legacy bridge for direct callers (unit
    # fixtures) — geometry is then rebuilt from params exactly as before.
    scene_theta_o: float | None = scene_los.theta_o if scene_los is not None else None
    # Target first so CU-009's T1/T2/T3 routing predicate in _infer_los
    # can dispatch on the runtime descriptor type.
    target = _build_target_descriptor(
        params=params,
        wavelength_um=wavelength_um,
        scene_type=scene_type,
        target_location=target_location,
        no_atmosphere_subcase=no_atmosphere_subcase,
        h_tgt=h_tgt,
        scene_theta_o=scene_theta_o,
    )

    # --- LOS geometry ---
    if scene_los is not None:
        los = _adjust_scene_los(scene_los, target_location, target_descriptor=target)
    else:
        los = _infer_los(target_location, params, target_descriptor=target)
    background = _build_background_descriptor(
        params=params,
        wavelength_um=wavelength_um,
        target_location=target_location,
        no_atmosphere_subcase=no_atmosphere_subcase,
        scene_type=scene_type,
        background_emissivity=background_emissivity,
        los=los,
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
        d["geometry.target.projected_area_m2"] = (
            float(target.A_t) if target.A_t is not None else 0.0
        )
    elif isinstance(target, T2Reflective):
        d["geometry.target.projected_area_m2"] = (
            float(target.A_t) if target.A_t is not None else 0.0
        )
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
