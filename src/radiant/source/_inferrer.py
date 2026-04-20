"""Back-compat descriptor inferrer for SourceStage (Option C, Stage 2).

This module maps the legacy (pre-Option-C) parameter surface onto the new
Option C descriptor surface defined in :mod:`radiant.core.descriptors` and
:mod:`radiant.core.los_geometry`.  It is the Stage-2 **additive bridge**
step in the [Option C plan](../../../docs/Option_C_Implementation_Plan.md):
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


def _infer_los(target_location: str) -> LineOfSightGeometry | None:
    """Build a LineOfSightGeometry for the Stage-2 bridge.

    Matrix §4.3 requires (h_tgt, θ_o, θ_s, Δφ).  The legacy parameter
    surface does not yet expose viewing / solar geometry through the
    SourceStage; Stage 3 will consume them through the AtmosphereStage
    parameters.  For Stage 2 we build a minimal LOS:

      * h_tgt = 0 m (surface target) for terrestrial / no_atmosphere.
      * θ_o = 0 rad (nadir).
      * θ_s = None (no solar geometry — LWIR-friendly default).
      * Δφ = None.
      * h_atm_top = 1e5 m (Kármán line, v1 default).

    Returns ``None`` when ``target_location == "at_aperture"`` because
    the at-aperture pass-through arm never evaluates an atmospheric
    path; matrix §4.3 line 356.
    """
    if target_location == "at_aperture":
        return None
    return LineOfSightGeometry(h_tgt=0.0, theta_o=0.0)


# ---------------------------------------------------------------------------
# Target descriptor construction
# ---------------------------------------------------------------------------


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
    projected_area = params.get("source.target.projected_area_m2")
    A_t: float | None = projected_area if projected_area > 0.0 else None

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
            shape=None,
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
            # Matrix §3.3 line 300: space sub-case → ColdSpaceBackground.
            return ColdSpaceBackground()
        # ground_test / lab_test: user must supply spectral background;
        # Stage 7 introduces the preset.  Raising here is Rule 17:
        # fail loud rather than silently.
        raise ParameterBoundsError(
            what=(
                f"source._inferrer: no_atmosphere_subcase = "
                f"{no_atmosphere_subcase!r} requires a user-supplied "
                f"UserSpectralBackground, which is not yet wired into "
                f"the legacy parameter surface."
            ),
            why=(
                "Stage 2 of the Option C plan is the additive bridge; "
                "ground_test / lab_test presets land in Stage 7 of the "
                "plan.  Setting the sub-case today requires the user to "
                "supply their own background spectrum through a future "
                "API surface."
            ),
            action=(
                "Either leave source.target_location at 'auto' / "
                "'terrestrial' / 'no_atmosphere'=space for now, or wait "
                "for Stage 7 to land the ground_test / lab_test preset."
            ),
            context={
                "target_location": target_location,
                "no_atmosphere_subcase": no_atmosphere_subcase,
            },
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
                fields.append(
                    f"source.background.temperature = {bg_t_rv.value} K"
                )
            if e_user_set:
                fields.append(
                    f"source.background.emissivity = {bg_e_rv.value}"
                )
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

    # --- LOS geometry ---
    los = _infer_los(target_location)

    # --- h_tgt (target altitude) ---
    # Matrix §3.2: h_tgt = 0 for terrestrial; None for at_aperture;
    # 0 for no_atmosphere=space (the space LOS is "above everything",
    # and the LOS object is currently still built with h_tgt=0 — a
    # Stage 7 enhancement will make h_tgt irrelevant for the no_atm path).
    if target_location == "at_aperture":
        h_tgt: float | None = None
    else:
        h_tgt = 0.0

    # --- Construct descriptors ---
    target = _build_target_descriptor(
        params=params,
        wavelength_um=wavelength_um,
        scene_type=scene_type,
        target_location=target_location,
        no_atmosphere_subcase=no_atmosphere_subcase,
        h_tgt=h_tgt,
    )
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
        d["source.target.projected_area_m2"] = (
            float(target.A_t) if target.A_t is not None else 0.0
        )
    elif isinstance(target, T2Reflective):
        d["source.target.projected_area_m2"] = (
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
