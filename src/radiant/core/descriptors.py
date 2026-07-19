"""Target and Background descriptors for the Source → Atmosphere boundary.

These are the pure data contracts that SourceStage publishes and
AtmosphereStage consumes under Option C (ADR-0002).  Placing them in
``core/`` — not ``source/`` — keeps the contract symmetric across stages and
removes a would-be Rule 11 exception (AtmosphereStage importing from
``radiant.source``).

Three families of classes live here:

- :class:`TargetDescriptor` — base class holding the matrix axes
  (``scene_type``, ``target_location``, ``no_atmosphere_subcase``,
  ``h_tgt``).  Subclasses :class:`T1Thermal`, :class:`T2Reflective`,
  :class:`T3Mixed`, :class:`T5AtAperture`, :class:`T6TabulatedAtSource`,
  :class:`T7IntensityAtSource` carry the discriminated material / geometry
  / user-radiometry payload.

- :class:`BackgroundDescriptor` — base class.  Subclasses
  :class:`AtApertureBackground`, :class:`ColdSpaceBackground`,
  :class:`GroundBackground`, :class:`UserSpectralBackground` cover the
  four v1 background variants.

- Cross-field validation: each ``__post_init__`` enforces the matrix §7
  must-raise combinations it can check from the descriptor alone.
  Checks that require PSF_FWHM (point-source angular-size guard) or
  cross-descriptor state (variant ↔ sub-case pairing) are deferred to
  later stages; see class docstrings for the exact deferrals.

Notes
-----
- All descriptors are frozen dataclasses.  Serialize via
  ``dataclasses.asdict(d)`` but note that nested :class:`SpectralData`
  fields need a custom round-trip (SpectralData already has ``to_dict`` /
  ``from_dict`` methods — use them for I/O).
- Unit conventions match ``RADIANT_Conventions.md``: ε and ρ are
  dimensionless spectral functions on µm; T in K; L in W/m²/sr/µm;
  h in m.
"""

from __future__ import annotations

import logging
import warnings
from dataclasses import dataclass
from typing import ClassVar, Literal

from radiant.core.parameters import ParameterBoundsError
from radiant.core.reflectance import ReflectanceDescriptor, ScalarLambertianReflectance
from radiant.core.spectral import SpectralData

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------

SceneType = Literal["extended", "sub_pixel", "point_source"]
TargetLocation = Literal["at_aperture", "terrestrial", "airborne", "no_atmosphere"]
NoAtmosphereSubcase = Literal["space", "ground_test", "lab_test"]


# ---------------------------------------------------------------------------
# TargetDescriptor — base
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TargetDescriptor:
    """Base target descriptor.

    Carries the three matrix axes plus the target altitude.  Concrete
    subclasses add the discriminated material/geometry payload (ε, ρ, T_t,
    A_t, shape, or user-supplied radiance) per ADR-0002 §"The descriptor
    surface".

    Parameters
    ----------
    scene_type:
        One of ``"extended"``, ``"sub_pixel"``, ``"point_source"``.
    target_location:
        One of ``"at_aperture"``, ``"terrestrial"``, ``"airborne"``,
        ``"no_atmosphere"``.
    no_atmosphere_subcase:
        Required iff ``target_location == "no_atmosphere"``.  One of
        ``"space"``, ``"ground_test"``, ``"lab_test"``.
    h_tgt:
        Target altitude above MSL [m].  Required except when
        ``target_location == "at_aperture"``.

    Deferred validation (NOT checked at construction)
    -------------------------------------------------
    **Point-source angular-size check** (``√A_t / d > 0.1 · PSF_FWHM`` per
    matrix §7): this check requires ``PSF_FWHM`` from OpticsStage and is
    therefore deferred to ``OpticsStage._finalize_regime()`` in Stage 8 of
    the Option C plan.  Constructing a ``point_source`` descriptor with
    a resolved angular size will **not** raise here; the error surfaces
    when OpticsStage finalizes the regime.
    """

    scene_type: SceneType
    target_location: TargetLocation
    no_atmosphere_subcase: NoAtmosphereSubcase | None = None
    h_tgt: float | None = None

    # ------------------------------------------------------------------
    # Shared cross-field validation
    # ------------------------------------------------------------------

    def __post_init__(self) -> None:
        # Enum-ish literals may arrive as raw strings from YAML — validate.
        if self.scene_type not in ("extended", "sub_pixel", "point_source"):
            raise ParameterBoundsError(
                what=f"TargetDescriptor.scene_type = {self.scene_type!r} is invalid",
                why="scene_type must be 'extended', 'sub_pixel', or 'point_source'.",
                action="Set scene_type to one of the three allowed values.",
                context={"scene_type": self.scene_type},
            )
        if self.target_location not in (
            "at_aperture",
            "terrestrial",
            "airborne",
            "no_atmosphere",
        ):
            raise ParameterBoundsError(
                what=(f"TargetDescriptor.target_location = {self.target_location!r} is invalid"),
                why=(
                    "target_location must be one of 'at_aperture', "
                    "'terrestrial', 'airborne', 'no_atmosphere'."
                ),
                action="Set target_location to one of the four allowed values.",
                context={"target_location": self.target_location},
            )

        # Matrix §7: at_aperture is extended-only.
        if self.target_location == "at_aperture" and self.scene_type != "extended":
            raise ParameterBoundsError(
                what=(
                    f"TargetDescriptor: target_location='at_aperture' "
                    f"requires scene_type='extended'; got {self.scene_type!r}"
                ),
                why=(
                    "At-aperture radiance spec is defined only for extended "
                    "scenes (matrix §7, Decision #2).  sub_pixel/point_source "
                    "cells cannot be pre-integrated at the pupil."
                ),
                action=(
                    "Either switch scene_type to 'extended' or pick a target "
                    "location other than 'at_aperture'."
                ),
                context={
                    "target_location": self.target_location,
                    "scene_type": self.scene_type,
                },
            )

        # Matrix §7: no_atmosphere without sub-case → raise.
        if self.target_location == "no_atmosphere" and self.no_atmosphere_subcase is None:
            raise ParameterBoundsError(
                what=(
                    "TargetDescriptor: target_location='no_atmosphere' "
                    "without no_atmosphere_subcase"
                ),
                why=(
                    "The 'no_atmosphere' location covers three distinct "
                    "sub-cases (space / ground_test / lab_test) which share "
                    "A0 atmosphere but differ in default background and "
                    "illumination.  Matrix §7 requires the sub-case."
                ),
                action=("Set no_atmosphere_subcase to 'space', 'ground_test', or 'lab_test'."),
                context={"target_location": self.target_location},
            )
        if self.target_location != "no_atmosphere" and self.no_atmosphere_subcase is not None:
            raise ParameterBoundsError(
                what=(
                    f"TargetDescriptor: no_atmosphere_subcase = "
                    f"{self.no_atmosphere_subcase!r} set but target_location = "
                    f"{self.target_location!r} (not 'no_atmosphere')"
                ),
                why="Sub-case selector is only meaningful for target_location='no_atmosphere'.",
                action="Either clear no_atmosphere_subcase or set target_location='no_atmosphere'.",
                context={
                    "target_location": self.target_location,
                    "no_atmosphere_subcase": self.no_atmosphere_subcase,
                },
            )

        # Validate subcase enum.
        if self.no_atmosphere_subcase is not None and self.no_atmosphere_subcase not in (
            "space",
            "ground_test",
            "lab_test",
        ):
            raise ParameterBoundsError(
                what=(
                    f"TargetDescriptor.no_atmosphere_subcase = "
                    f"{self.no_atmosphere_subcase!r} is invalid"
                ),
                why="Sub-case must be 'space', 'ground_test', or 'lab_test'.",
                action="Set no_atmosphere_subcase to one of the three allowed values.",
                context={"no_atmosphere_subcase": self.no_atmosphere_subcase},
            )

        # h_tgt: required for terrestrial/airborne/no_atmosphere; forbidden for at_aperture.
        if self.target_location == "at_aperture":
            if self.h_tgt is not None:
                raise ParameterBoundsError(
                    what=(
                        f"TargetDescriptor: h_tgt = {self.h_tgt} set but "
                        f"target_location='at_aperture'"
                    ),
                    why="At-aperture descriptors have no atmospheric path; h_tgt is undefined.",
                    action="Leave h_tgt = None for at_aperture targets.",
                    context={"target_location": self.target_location, "h_tgt": self.h_tgt},
                )
        else:
            if self.h_tgt is None:
                raise ParameterBoundsError(
                    what=(
                        f"TargetDescriptor: h_tgt is None but "
                        f"target_location = {self.target_location!r} requires it"
                    ),
                    why=(
                        "Terrestrial / airborne / no_atmosphere descriptors "
                        "drive the atmospheric path and therefore need the "
                        "target altitude."
                    ),
                    action="Set h_tgt to a non-negative altitude [m].",
                    context={"target_location": self.target_location},
                )
            if self.h_tgt < 0.0:
                raise ParameterBoundsError(
                    what=f"TargetDescriptor.h_tgt = {self.h_tgt} m is negative",
                    why="Target altitude must be non-negative (at or above MSL).",
                    action="Set h_tgt ≥ 0.",
                    context={"h_tgt": self.h_tgt},
                )


# ---------------------------------------------------------------------------
# Regime helpers (internal)
# ---------------------------------------------------------------------------


def _is_mwir_spectral_data(sd: SpectralData | None) -> bool:
    """Return True if the wavelength grid overlaps the MWIR band (3–5 µm).

    Used by T1/T2 variant validators to emit Rule-17 warnings when a
    pure-thermal or pure-reflective model is used in the MWIR, where
    matrix §3.2 says T3 mixed is mandatory for ambient scenes.
    """
    if sd is None:
        return False
    lam = sd.wavelength_um
    if lam.size == 0:
        return False
    return bool((lam.min() <= 5.0) and (lam.max() >= 3.0))


def _is_swir_spectral_data(sd: SpectralData | None) -> bool:
    """Return True if the wavelength grid overlaps the SWIR band (1–3 µm).

    Used by T1/T2 variant validators to emit Rule-17 warnings when a hot
    target (T_t > ~700 K) is configured in SWIR with a non-mixed model —
    matrix §3.2 line 318: SWIR is reflective-dominated, but targets above
    ~700 K have measurable thermal emission that pure-reflective or
    pure-thermal treatments drop.
    """
    if sd is None:
        return False
    lam = sd.wavelength_um
    if lam.size == 0:
        return False
    return bool((lam.min() <= 3.0) and (lam.max() >= 1.0))


def _warn_mwir_non_mixed(
    variant: str,
    sd: SpectralData | None,
    extra: str = "",
) -> None:
    """Emit a matrix §3.2 MWIR warning per Rule 17."""
    if _is_mwir_spectral_data(sd):
        msg = (
            f"TargetDescriptor: {variant} applied to a spectral band overlapping "
            f"the MWIR (3–5 µm).  Matrix §3.2 notes that ambient-temperature MWIR "
            f"scenes require the T3 mixed emit+reflect model — a pure "
            f"{variant.lower()} treatment may be inaccurate."
        )
        if extra:
            msg = f"{msg} {extra}"
        # Warning-free-UX campaign: a variant/band routing caveat (matrix §3.2) is a
        # property of the config, not a per-evaluate event, and the descriptor variant
        # is already surfaced on the result — log at debug, not a UserWarning.
        logger.debug(msg)


# SWIR hot-target threshold per matrix §3.2 line 318.
_SWIR_HOT_TARGET_THRESHOLD_K: float = 700.0


def _warn_swir_hot_non_mixed(
    variant: str,
    sd: SpectralData | None,
    T_t: float,
) -> None:
    """Emit a matrix §3.2 SWIR hot-target warning per Rule 17.

    SWIR is reflective-dominated in the ambient-temperature regime, but
    once ``T_t`` exceeds ~700 K the thermal emission becomes measurable
    at 2–3 µm and a pure reflective (T2) or pure thermal (T1) treatment
    drops a non-trivial radiance term.  Matrix §3.2 line 318.
    """
    if _is_swir_spectral_data(sd) and T_t > _SWIR_HOT_TARGET_THRESHOLD_K:
        variant_label = (
            variant.lower().replace("t1thermal", "thermal").replace("t2reflective", "reflective")
        )
        warnings.warn(
            (
                f"TargetDescriptor: {variant} applied to a SWIR spectral band "
                f"(1–3 µm) with T_t = {T_t} K > "
                f"{_SWIR_HOT_TARGET_THRESHOLD_K:g} K.  Matrix §3.2 notes that "
                f"SWIR is reflective-dominated for ambient targets, but hot "
                f"targets (> ~700 K) have measurable thermal emission that "
                f"pure-{variant_label} "
                f"treatment drops.  Use T3Mixed for hot SWIR targets."
            ),
            UserWarning,
            stacklevel=3,
        )


# ---------------------------------------------------------------------------
# TargetDescriptor — concrete variants
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class T1Thermal(TargetDescriptor):
    """Pure-thermal graybody: L_t = ε(λ)·B(λ, T_t).

    Valid for LWIR cells and MWIR cells where ρ ≈ 0 (hot targets).  A
    warning fires if the emissivity spectral band overlaps the MWIR band,
    because matrix §3.2 notes that ambient MWIR scenes need the T3 mixed
    model — the warning gives users a chance to reclassify (Rule 17).
    """

    epsilon: SpectralData | None = None
    T_t: float = 0.0
    A_t: float | None = None

    def __post_init__(self) -> None:
        super().__post_init__()
        if self.epsilon is None:
            raise ParameterBoundsError(
                what="T1Thermal: epsilon is required",
                why="Graybody thermal radiance needs ε(λ) for Kirchhoff self-emission.",
                action="Supply epsilon: SpectralData.",
                context={},
            )
        if self.T_t <= 0.0:
            raise ParameterBoundsError(
                what=f"T1Thermal: T_t = {self.T_t} K is non-positive",
                why="Target temperature must be > 0 K for Planck emission.",
                action="Set T_t to a positive Kelvin temperature.",
                context={"T_t": self.T_t},
            )
        # MWIR warning: pure-thermal without explicit rho-is-zero justification.
        _warn_mwir_non_mixed(
            "T1Thermal",
            self.epsilon,
            "Use T3Mixed unless ρ ≈ 0 (hot target).",
        )
        # SWIR hot-target warning: pure-thermal at SWIR wavelengths with
        # T_t > 700 K drops the reflective solar term (matrix §3.2 line 318).
        _warn_swir_hot_non_mixed("T1Thermal", self.epsilon, self.T_t)


@dataclass(frozen=True)
class T2Reflective(TargetDescriptor):
    """Pure-reflective Lambertian: L_t = ρ(λ)·E/π.

    Valid for VIS/NIR/SWIR reflective cells.  Matrix §3.2 warns that MWIR
    scenes generally need the T3 mixed model; a warning fires if the
    reflectance grid overlaps the MWIR band (Rule 17).
    """

    rho: ReflectanceDescriptor | None = None
    A_t: float | None = None

    def __post_init__(self) -> None:
        super().__post_init__()
        if self.rho is None:
            raise ParameterBoundsError(
                what="T2Reflective: rho is required",
                why=("Lambertian reflection needs ρ(λ) = 1 − ε(λ) (Kirchhoff) or user-supplied ρ."),
                action=(
                    "Supply rho: ReflectanceDescriptor (build via "
                    "radiant.source.converters.reflectance."
                    "reflectance_to_descriptor)."
                ),
                context={},
            )
        if isinstance(self.rho, SpectralData):
            raise ParameterBoundsError(
                what="T2Reflective: rho must be a ReflectanceDescriptor, got SpectralData",
                why=(
                    "Gap H invariant: T2Reflective.rho is narrowed to ReflectanceDescriptor "
                    "so downstream consumers can rely on the .reflectance_at(λ, view, illum) "
                    "protocol interface.  SpectralData is the user-input surface, not the "
                    "descriptor-internal surface."
                ),
                action=(
                    "Build the descriptor via "
                    "radiant.source.converters.reflectance.reflectance_to_descriptor, "
                    "which wraps the SpectralData in a ScalarLambertianReflectance adapter."
                ),
                context={},
            )
        # MWIR §3.2 warning: descriptor-level check is best-effort; for scalar
        # ρ the grid is knowable via the adapter, so the boundary converter
        # emits the authoritative warning at wrap time (Gap H).  Anisotropic
        # BRDF concretions without a stored grid are silent here — their
        # assembly-time consumers are responsible.
        if isinstance(self.rho, ScalarLambertianReflectance):
            _warn_mwir_non_mixed(
                "T2Reflective",
                self.rho.reflectance,
                "Use T3Mixed unless ε ≈ 0 (cold reflector).",
            )


@dataclass(frozen=True)
class T3Mixed(TargetDescriptor):
    """Mixed emit + reflect (Kirchhoff): ρ = 1 − ε.

    Mandatory for MWIR ambient scenes per matrix §3.2.  Takes ε and T_t;
    ρ is derived by AtmosphereStage via Kirchhoff at assembly time.
    """

    epsilon: SpectralData | None = None
    T_t: float = 0.0
    A_t: float | None = None

    def __post_init__(self) -> None:
        super().__post_init__()
        if self.epsilon is None:
            raise ParameterBoundsError(
                what="T3Mixed: epsilon is required",
                why=(
                    "Mixed emit+reflect needs ε(λ); ρ(λ) = 1 − ε(λ) is "
                    "derived via Kirchhoff (Rule 5)."
                ),
                action="Supply epsilon: SpectralData.",
                context={},
            )
        if self.T_t <= 0.0:
            raise ParameterBoundsError(
                what=f"T3Mixed: T_t = {self.T_t} K is non-positive",
                why="Target temperature must be > 0 K for Planck emission.",
                action="Set T_t to a positive Kelvin temperature.",
                context={"T_t": self.T_t},
            )


@dataclass(frozen=True)
class T5AtAperture(TargetDescriptor):
    """User-supplied at-aperture spectrum.

    For extended at-aperture cells (Table A).  Carries either the spectral
    radiance ``L_t_aperture`` (primary) or the spectral intensity
    ``I_t_aperture`` (deferred for at-aperture sub-pixel/point, currently
    invalid per the matrix — accepted here for forward compatibility but
    blocked by the at_aperture⇒extended check in the base ``__post_init__``).
    """

    L_t_aperture: SpectralData | None = None
    I_t_aperture: SpectralData | None = None

    def __post_init__(self) -> None:
        super().__post_init__()
        if self.target_location != "at_aperture":
            raise ParameterBoundsError(
                what=(
                    f"T5AtAperture: target_location must be 'at_aperture'; "
                    f"got {self.target_location!r}"
                ),
                why="T5 carries pre-propagated radiance and cannot run through A2/A3.",
                action="Set target_location='at_aperture' or use T1/T2/T3 instead.",
                context={"target_location": self.target_location},
            )
        if self.L_t_aperture is None and self.I_t_aperture is None:
            raise ParameterBoundsError(
                what="T5AtAperture: must supply L_t_aperture or I_t_aperture",
                why="At-aperture descriptors carry a user-supplied spectrum; neither was provided.",
                action="Supply L_t_aperture (W/m²/sr/µm) for extended cells.",
                context={},
            )
        if self.L_t_aperture is not None and self.I_t_aperture is not None:
            raise ParameterBoundsError(
                what=("T5AtAperture: both L_t_aperture and I_t_aperture supplied"),
                why=(
                    "The at-aperture descriptor holds exactly one of "
                    "{radiance, intensity} — which one is determined by "
                    "scene_type (extended uses L; sub_pixel/point use I)."
                ),
                action="Keep whichever matches your scene_type; remove the other.",
                context={},
            )


@dataclass(frozen=True)
class T6TabulatedAtSource(TargetDescriptor):
    """User-supplied at-source spectral radiance; flows through τ_up + L_path_up.

    ADR-0003 — the S8 / S11(λ-varying) / S12 escape-hatch descriptor.  The
    user provides an absolute spectral radiance ``L_t_source(λ)`` at the
    target plane (h = ``h_tgt``); AtmosphereStage propagates it via the
    normal up-leg arm so downstream stages see ``L_t_source · τ_up +
    L_path_up`` at the aperture.  ρ ≡ 0 by construction (the user is naming
    absolute radiance, not a material property).

    Paired with ``target_location ∈ {terrestrial, airborne, no_atmosphere}``.
    ``at_aperture`` is rejected — that is :class:`T5AtAperture`'s domain.

    Parameters
    ----------
    L_t_source:
        Spectral radiance at the target [W/m²/sr/µm] on the chain
        wavelength grid.  Must be non-negative everywhere.
    A_t:
        Optional projected area [m²] for sub_pixel / point_source regimes.
    """

    L_t_source: SpectralData | None = None
    A_t: float | None = None

    def __post_init__(self) -> None:
        super().__post_init__()
        if self.L_t_source is None:
            raise ParameterBoundsError(
                what="T6TabulatedAtSource: L_t_source is required",
                why=(
                    "T6 wraps a user-supplied spectral radiance at the "
                    "target plane; without L_t_source there is nothing to "
                    "propagate."
                ),
                action="Supply L_t_source: SpectralData in W/m²/sr/µm.",
                context={},
            )
        if self.target_location == "at_aperture":
            raise ParameterBoundsError(
                what=("T6TabulatedAtSource: target_location='at_aperture' is not supported"),
                why=(
                    "T6 carries at-source radiance and flows through the "
                    "atmospheric up-leg.  At-aperture inputs bypass "
                    "atmosphere and belong on T5AtAperture."
                ),
                action=(
                    "Use T5AtAperture for at-aperture inputs; switch "
                    "target_location to terrestrial / airborne / "
                    "no_atmosphere for T6."
                ),
                context={"target_location": self.target_location},
            )
        vals = self.L_t_source.values
        if vals.size == 0 or bool((vals < 0.0).any()):
            raise ParameterBoundsError(
                what=("T6TabulatedAtSource: L_t_source contains negative or empty values"),
                why=(
                    "Spectral radiance is non-negative (Rule 17 — no silent "
                    "failure on unphysical inputs)."
                ),
                action=(
                    "Resample / clean L_t_source so that every value is "
                    "≥ 0 on a non-empty wavelength grid."
                ),
                context={
                    "min_value": float(vals.min()) if vals.size else None,
                    "size": int(vals.size),
                },
            )


@dataclass(frozen=True)
class T7IntensityAtSource(TargetDescriptor):
    """User-supplied at-source spectral intensity I(λ) for point sources.

    ADR-0004.  The user provides spectral intensity ``I_t_source(λ)``
    [W/sr/µm] at the target plane (``h = h_tgt``) for an unresolved
    (point-source) target.  AtmosphereStage's T7 arm performs the
    ``I → L`` conversion at the boundary using
    :attr:`REFERENCE_AREA_M2` and then feeds it through the standard
    up-leg formula ``L · τ_up + L_path_up``.

    The reference area is a *numerical cancellation device*, not a
    physical claim about target size: RADIANT uses a single at-pixel
    camera equation (``L · A_collect · A_t / R²``) for all regimes, and
    choosing ``L ≡ I / A_fict`` with ``A_t ≡ A_fict`` makes ``A_fict``
    cancel exactly, recovering the correct point-source form
    ``I · A_collect / R²``.  See ADR-0004 §Assembly contract.

    No ``shape`` or ``A_t`` fields: a point source is unresolved by
    construction (``scene_type == "point_source"``); projected geometry
    is meaningless at the descriptor surface, and the reference area
    used internally by the assembly arm is an implementation detail
    (ADR-0002 faithfulness).

    Parameters
    ----------
    I_t_source:
        Spectral intensity at the target [W/sr/µm] on the chain
        wavelength grid.  Must be non-negative everywhere with the
        canonical unit string ``"W/sr/um"``.

    Notes
    -----
    Paired with ``scene_type == "point_source"`` and
    ``target_location ∈ {terrestrial, airborne, no_atmosphere}``.
    ``at_aperture`` is rejected — the aperture integrates radiance, not
    intensity; at-aperture scenes belong on :class:`T5AtAperture`.
    ``extended`` and ``sub_pixel`` are rejected — intensity is the
    point-source radiometric quantity (matrix §7 row S10); resolved
    targets belong on T1 / T3 / T6.
    """

    REFERENCE_AREA_M2: ClassVar[float] = 1e-12

    I_t_source: SpectralData | None = None

    def __post_init__(self) -> None:
        super().__post_init__()
        if self.I_t_source is None:
            raise ParameterBoundsError(
                what="T7IntensityAtSource: I_t_source is required",
                why=(
                    "T7 wraps a user-supplied spectral intensity at the "
                    "target plane; without I_t_source there is nothing "
                    "to propagate."
                ),
                action="Supply I_t_source: SpectralData in W/sr/µm.",
                context={},
            )
        if self.scene_type != "point_source":
            raise ParameterBoundsError(
                what=(
                    f"T7IntensityAtSource: scene_type = {self.scene_type!r} is not 'point_source'"
                ),
                why=(
                    "Intensity I(λ) [W/sr/µm] is the point-source "
                    "radiometric quantity (matrix §7 row S10).  "
                    "Resolved (extended / sub_pixel) targets must use "
                    "T1 / T3 / T6 with radiance L(λ) [W/m²/sr/µm]."
                ),
                action=(
                    "Set scene_type='point_source' or switch to a "
                    "radiance-carrying variant (T1, T3, T6)."
                ),
                context={"scene_type": self.scene_type},
            )
        if self.target_location == "at_aperture":
            raise ParameterBoundsError(
                what=("T7IntensityAtSource: target_location='at_aperture' is not supported"),
                why=(
                    "T7 requires atmospheric transport from the target "
                    "plane to the aperture.  The aperture integrates "
                    "radiance, not intensity — at-aperture spectra "
                    "belong on T5AtAperture."
                ),
                action=(
                    "Set target_location to 'terrestrial', 'airborne', "
                    "or 'no_atmosphere', or switch to T5AtAperture."
                ),
                context={"target_location": self.target_location},
            )
        if self.I_t_source.unit != "W/sr/um":
            raise ParameterBoundsError(
                what=(
                    f"T7IntensityAtSource: I_t_source.unit = "
                    f"{self.I_t_source.unit!r} is not the canonical "
                    f"'W/sr/um'"
                ),
                why=(
                    "Rule 2: internal canonical units are fixed; "
                    "conversions happen at boundary readers, so a "
                    "descriptor with a non-canonical unit indicates a "
                    "missed conversion upstream."
                ),
                action=(
                    "Author the SpectralData with unit='W/sr/um' or "
                    "convert at the boundary before constructing T7."
                ),
                context={"unit": self.I_t_source.unit},
            )
        vals = self.I_t_source.values
        if vals.size == 0 or bool((vals < 0.0).any()):
            raise ParameterBoundsError(
                what=("T7IntensityAtSource: I_t_source contains negative or empty values"),
                why=(
                    "Spectral intensity is non-negative (Rule 17 — no "
                    "silent failure on unphysical inputs)."
                ),
                action=(
                    "Resample / clean I_t_source so every value is ≥ 0 "
                    "on a non-empty wavelength grid."
                ),
                context={
                    "min_value": float(vals.min()) if vals.size else None,
                    "size": int(vals.size),
                },
            )


# ---------------------------------------------------------------------------
# Kirchhoff over-specification check (ε and ρ on the same target)
# ---------------------------------------------------------------------------
#
# The Kirchhoff rule (Rule 5 / ADR-0002) says ε + ρ = 1 for an opaque
# Lambertian surface; supplying both is over-specifying.  The dataclass
# subclasses above already split ε-carrying variants (T1, T3) from
# ρ-carrying variants (T2), so a single descriptor cannot carry both.
#
# A helper below raises if a caller hand-assembles a dict with both; this
# is the serialization-layer guard against the over-specification.


def raise_if_epsilon_and_rho_both_set(
    epsilon: SpectralData | None,
    rho: SpectralData | ReflectanceDescriptor | None,
    where: str = "TargetDescriptor",
) -> None:
    """Guard against ε and ρ being supplied together (Rule 5).

    Raises
    ------
    ParameterBoundsError
        If both ``epsilon`` and ``rho`` are non-None.
    """
    if epsilon is not None and rho is not None:
        raise ParameterBoundsError(
            what=f"{where}: both epsilon and rho supplied for the same target",
            why=(
                "Kirchhoff's law ties ρ and ε together for an opaque "
                "Lambertian surface (ρ = 1 − ε).  Supplying both "
                "over-specifies the system (Rule 5)."
            ),
            action="Supply only one of epsilon or rho; the other is derived.",
            context={},
        )


# ---------------------------------------------------------------------------
# Cross-descriptor validators (matrix §7 — require both descriptors in scope)
# ---------------------------------------------------------------------------


def warn_if_reflective_and_sun_below_horizon(
    target: TargetDescriptor,
    theta_s: float | None,
) -> None:
    """Matrix §7 check: T2Reflective with solar zenith below horizon.

    When the target is pure-reflective (T2) and the solar zenith
    ``θ_s > π/2`` (sun below the horizon), the reflected-solar term
    vanishes and the observed radiance collapses to zero in the
    pure-reflective model.  This is a physics concern (not a physics
    error) because the user may intentionally be computing a
    sun-below-horizon scene — we warn per Rule 17 so the user sees the
    zero-signal expectation explicitly.

    Parameters
    ----------
    target:
        The TargetDescriptor published by SourceStage.  Only T2Reflective
        triggers the warning; all other variants are no-ops.
    theta_s:
        Solar zenith at the target [rad] from
        :class:`LineOfSightGeometry.theta_s`; may be ``None`` (pure-
        thermal scene — no warning fires).
    """
    if not isinstance(target, T2Reflective):
        return
    if theta_s is None:
        return
    import math as _math

    if theta_s > _math.pi / 2.0:
        warnings.warn(
            (
                f"T2Reflective: solar zenith theta_s = {theta_s:.4f} rad "
                f"({_math.degrees(theta_s):.2f}°) is below the horizon "
                f"(> π/2).  Matrix §7: a pure-reflective target with the "
                f"sun below the horizon yields zero reflected radiance; "
                f"SNR will vanish.  Consider switching to T3Mixed if the "
                f"target has a thermal emission component."
            ),
            UserWarning,
            stacklevel=2,
        )


# ---------------------------------------------------------------------------
# BackgroundDescriptor — base and variants
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class BackgroundDescriptor:
    """Base class for background descriptors.

    Four variants are defined in v1:

    - :class:`AtApertureBackground` — paired with ``target_location="at_aperture"``.
    - :class:`ColdSpaceBackground` — paired with ``no_atmosphere_subcase="space"``.
    - :class:`GroundBackground` — required for ``target_location ∈ {"terrestrial", "airborne"}``.
    - :class:`UserSpectralBackground` — required for
      ``no_atmosphere_subcase ∈ {"ground_test", "lab_test"}``.

    Variant ↔ target_location pairing is **not** enforced at construction.
    Descriptors are independent data contracts; pairing is checked at
    assembly time (Stage 3 AtmosphereStage) where both descriptors are in
    scope simultaneously.  This keeps construction local, composable, and
    testable.
    """

    # Base class intentionally empty — variant-specific validation lives
    # in each subclass's __post_init__.
    def __post_init__(self) -> None:  # pragma: no cover - no-op
        pass


@dataclass(frozen=True)
class AtApertureBackground(BackgroundDescriptor):
    """At-aperture pre-propagated background radiance.

    Paired with ``target_location == "at_aperture"``.  A ``None`` radiance
    is treated as zero at assembly time (matrix Decision #14).
    """

    L_bg_aperture: SpectralData | None = None


@dataclass(frozen=True)
class ColdSpaceBackground(BackgroundDescriptor):
    """Cold-space background (L ≡ 0 in v1).

    Paired with ``no_atmosphere_subcase == "space"``.  v2 may add
    zodiacal light and diffuse-galactic terms as additive fields without
    breaking this variant's construction signature.
    """

    # No parameters in v1 — L_bg = 0 identically.


@dataclass(frozen=True)
class GroundBackground(BackgroundDescriptor):
    """Ground background (ε_g(λ), T_g).

    Required for ``target_location ∈ {"terrestrial", "airborne"}``.  Emits
    a UserWarning per Rule 17 if ``T_g`` is outside the physically
    plausible Earth-surface range [150, 350] K — it does not raise, because
    the user may legitimately be modeling a non-standard scene.  Extreme
    values should still raise, but the "extreme" threshold is scenario-
    dependent and is deferred to downstream stages (or §8 validators).
    """

    epsilon_g: SpectralData | None = None
    T_g: float = 0.0

    def __post_init__(self) -> None:
        super().__post_init__()
        if self.epsilon_g is None:
            raise ParameterBoundsError(
                what="GroundBackground: epsilon_g is required",
                why="Ground background needs ε_g(λ) for Kirchhoff self-emission.",
                action="Supply epsilon_g: SpectralData.",
                context={},
            )
        if self.T_g <= 0.0:
            raise ParameterBoundsError(
                what=f"GroundBackground: T_g = {self.T_g} K is non-positive",
                why="Ground temperature must be > 0 K for Planck emission.",
                action="Set T_g to a positive Kelvin temperature.",
                context={"T_g": self.T_g},
            )
        if not (150.0 <= self.T_g <= 350.0):
            warnings.warn(
                (
                    f"GroundBackground: T_g = {self.T_g} K is outside the "
                    f"plausible Earth-surface range [150, 350] K (matrix §7). "
                    f"Continuing, but physics may be degraded."
                ),
                UserWarning,
                stacklevel=2,
            )


@dataclass(frozen=True)
class UserSpectralBackground(BackgroundDescriptor):
    """User-supplied spectral background.

    Required for ``no_atmosphere_subcase ∈ {"ground_test", "lab_test"}``
    where no sensible default can be assumed for the test-range or chamber
    radiance.  Distinct from :class:`AtApertureBackground` because source
    physics still runs (the atmosphere is A0 pass-through, not a full
    source-physics bypass).
    """

    L_bg: SpectralData | None = None

    def __post_init__(self) -> None:
        super().__post_init__()
        if self.L_bg is None:
            raise ParameterBoundsError(
                what="UserSpectralBackground: L_bg is required",
                why=(
                    "ground_test / lab_test sub-cases have no sensible "
                    "default background — the user must supply test-range "
                    "or chamber spectral radiance."
                ),
                action="Supply L_bg: SpectralData in W/m²/sr/µm.",
                context={},
            )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

__all__ = [
    "AtApertureBackground",
    "BackgroundDescriptor",
    "ColdSpaceBackground",
    "GroundBackground",
    "T1Thermal",
    "T2Reflective",
    "T3Mixed",
    "T5AtAperture",
    "T6TabulatedAtSource",
    "T7IntensityAtSource",
    "TargetDescriptor",
    "UserSpectralBackground",
    "raise_if_epsilon_and_rho_both_set",
    "warn_if_reflective_and_sun_below_horizon",
]
