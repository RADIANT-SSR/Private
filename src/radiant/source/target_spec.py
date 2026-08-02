"""Target-spec over-specification guards — the resolve-time seam (CU-244).

One computation, one module (Rule 19): this module owns the **cross-parameter
mutual-exclusivity rules** for the ``source.target.*`` user-entry surfaces
(Target Definition Matrix §1 spec forms).  The guards were historically inlined
in the :mod:`radiant.source._inferrer` door builders, which made them reachable
only at ``evaluate()`` time; CU-244 extracted them here so the same checks — and
the exact same what/why/action text — can also run at *resolve* time, before any
physics, via :meth:`radiant.api.sensor.Sensor.validate_target_spec` (which the
GUI's clone-validate edit discipline calls to reject an over-specified pair at
the door).

Two entry points:

* The inferrer's door builders call the per-door ``check_*_conflicts``
  functions at the same points the inline blocks used to occupy, so the
  evaluate-time behaviour is unchanged — defence in depth.  CU-244 kept the
  message text byte-identical through the extraction, which left every
  ``what=`` opening ``"source._inferrer: …"`` — a module that no longer holds
  the check.  CU-295 retargeted that prefix to ``"source.target_spec: "``
  here; the identity that matters (seam error == evaluate error) is unaffected
  because both callers read these same functions.
* :func:`validate_target_spec` runs the doors in the inferrer's dispatch order
  (S11 → S12 → S4/S5/S6 → S8 → S10b → S10 → S1-with-ε(λ)) and is the single
  seam the API exposes.  CU-256 added
  :func:`check_intensity_door_extent_conflicts` here as the intended extension
  point predicted by the CU-244 docstring; CU-293 (with the folded CU-294)
  moved three more inlined door blocks — S8
  :func:`check_user_radiance_conflicts`, S10b
  :func:`check_point_intensity_conflicts`, S10
  :func:`check_user_intensity_conflicts` — and added the S11-vs-S12 guard the
  S11 door had always been missing; CU-318 moved the last one, the ε(λ) door's
  :func:`check_emissivity_path_conflicts`.  Future door guards slot in the same
  way.

Every door is now registered here: whichever door dispatches first, the same
pair is refused with the same message at both entry points.  Before CU-293 the
S11 door alone had no S12 guard, so a ``brightness_temperature_* +
radiance_temperature_K`` pair raised at this seam but *evaluated silently* —
the S11 builder dispatched first and discarded the radiance-temperature
surface (Rule 17).  Before CU-318 the ε(λ) door's guard was still inlined, so
its one unique pair (``emissivity_path`` + scalar ``source.target.emissivity``)
refused only at ``evaluate()``.

Scope: **over-specification only.**  Completeness checks (e.g. "S12 requires
the band edges") stay in the inferrer — a half-entered spec is a legitimate
intermediate state while the user types, and ``evaluate()`` remains the surface
that reports what is still missing.

Every guard is a pure read of :class:`~radiant.core.parameters.ParameterSet`
provenance — no file I/O, no physics, no mutation — so the seam is safe to run
on every GUI edit.
"""

from __future__ import annotations

from typing import Any

from radiant.core.parameters import ParameterBoundsError, ParameterSet, Provenance
from radiant.source._schema import validate_reflectance_albedo_exclusive

__all__ = [
    "check_brightness_temperature_conflicts",
    "check_emissivity_path_conflicts",
    "check_intensity_door_extent_conflicts",
    "check_point_intensity_conflicts",
    "check_radiance_temperature_conflicts",
    "check_reflectance_conflicts",
    "check_user_intensity_conflicts",
    "check_user_radiance_conflicts",
    "validate_target_spec",
]

# Surfaces that over-specify the S1-with-ε(λ) thermal target opened by
# ``source.target.emissivity_path`` (Gap 47).  Order is the pre-extraction
# inline order in ``_inferrer._load_emissivity_on_grid`` (CU-318).
_EMISSIVITY_PATH_CONFLICTS: tuple[str, ...] = (
    "source.target.emissivity",
    "source.target.reflectance",
    "source.target.albedo",
    "source.target.reflectance_path",
    "source.target.albedo_path",
    "source.target.brightness_temperature_K",
    "source.target.brightness_temperature_path",
    "source.target.radiance_temperature_K",
    "source.target.user_radiance_path",
    "source.target.user_intensity_path",
)

# The three user-entry surfaces that open the S10/S10b intensity door
# (:class:`~radiant.core.descriptors.T7IntensityAtSource`).
_INTENSITY_DOOR_SURFACES: tuple[str, ...] = (
    "source.target.user_intensity_path",
    "source.target.point_intensity_temperature_K",
    "source.target.point_intensity_band_W_per_sr",
)

# Declared-extent surfaces: the ways a user states how big the target is on
# the sky.  ``geometry.target.shape`` uses ``'none'`` as its Rule-12 sentinel
# for "not provided"; ``projected_area_m2`` uses ``0.0``.
_DECLARED_EXTENT_SURFACES: tuple[str, ...] = (
    "geometry.target.projected_area_m2",
    "geometry.target.shape",
)
_EXTENT_UNSET_SENTINELS: frozenset[object] = frozenset({None, "", "none", 0.0})


#: Provenances that do **not** mean "the user chose this value".
#: ``DEFAULT`` is the schema fallback; ``DERIVED`` is a value RADIANT itself
#: computed (a consistency-group free variable, or an API-side derivation such
#: as ``platform.ground_velocity_m_s`` from the orbit).  Over-specification is a
#: statement about *user input*, so refusing a config over a value the framework
#: supplied would blame the user for something they never set (CU-300).
#: ``SAMPLED`` deliberately counts as user-set: a sweep axis is user intent.
_NOT_USER_SET: frozenset[Provenance] = frozenset({Provenance.DEFAULT, Provenance.DERIVED})


def _is_user_set(params: ParameterSet, name: str) -> bool:
    """True iff the user chose a value for ``name`` (see :data:`_NOT_USER_SET`).

    Works on both resolved and unresolved sets, and both views apply the same
    provenance rule: a resolved set reads :meth:`ParameterSet.get_resolved`
    provenance, an unresolved set reads the explicit-inputs snapshot's
    :meth:`ParameterSet.input_provenances`.  The unresolved branch is what lets
    :meth:`Sensor.validate_target_spec` run on a still-incomplete config
    without forcing (or failing) a full resolve.

    CU-300: ``DERIVED`` used to count as user-set on the resolved view.  That
    is inert for every surface the current guards inspect — none of the
    ``source.target.*`` / ``geometry.target.*`` spec surfaces participates in a
    consistency group, and the one API-side ``DERIVED`` write
    (``platform.ground_velocity_m_s``) is not among them — but the CU-244 seam
    is designed to grow, and the first guard added over a derived surface would
    have raised an over-specification error against a value RADIANT computed.
    """
    if params.is_resolved:
        return params.get_resolved(name).provenance not in _NOT_USER_SET
    return params.input_provenances().get(name, Provenance.DEFAULT) not in _NOT_USER_SET


def _value_of(params: ParameterSet, name: str) -> Any:
    """The parameter's value on either view (``None`` if unset and unresolved)."""
    if params.is_resolved:
        return params.get_resolved(name).value
    return params.inputs().get(name)


def _is_user_set_nonempty(params: ParameterSet, name: str) -> bool:
    """User-set AND truthy — the activation test for path-valued surfaces."""
    return _is_user_set(params, name) and bool(_value_of(params, name))


def _rho_family_user_set(params: ParameterSet) -> bool:
    """True iff any S4/S5/S6 reflectance surface is user-set (paths must be non-empty)."""
    return (
        _is_user_set(params, "source.target.reflectance")
        or _is_user_set(params, "source.target.albedo")
        or _is_user_set_nonempty(params, "source.target.reflectance_path")
        or _is_user_set_nonempty(params, "source.target.albedo_path")
    )


def check_brightness_temperature_conflicts(params: ParameterSet) -> None:
    """S11 door: raise if brightness_temperature_* is paired with a rival surface.

    No-op when neither S11 surface is user-set.  Guard order (and text) is
    exactly the pre-CU-244 inline order in
    ``_inferrer._maybe_build_from_brightness_temperature``: K+path both set,
    then (ε, T), then S8, then S10, then ρ-family — with the S12 guard CU-293
    appended last, mirroring the position the S11 guard already occupies in
    :func:`check_radiance_temperature_conflicts`.
    """
    t_b_k_user = _is_user_set(params, "source.target.brightness_temperature_K")
    t_b_path_user = _is_user_set_nonempty(params, "source.target.brightness_temperature_path")

    if not t_b_k_user and not t_b_path_user:
        return

    if t_b_k_user and t_b_path_user:
        raise ParameterBoundsError(
            what=(
                "source.target_spec: both "
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
                "brightness_temperature_K": _value_of(
                    params, "source.target.brightness_temperature_K"
                ),
                "brightness_temperature_path": _value_of(
                    params, "source.target.brightness_temperature_path"
                ),
            },
        )

    if _is_user_set(params, "source.target.temperature") or _is_user_set(
        params, "source.target.emissivity"
    ):
        raise ParameterBoundsError(
            what=(
                "source.target_spec: brightness_temperature is mutually "
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
                "source.target_spec: brightness_temperature is mutually "
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
                "user_radiance_path": _value_of(params, "source.target.user_radiance_path"),
            },
        )

    if _is_user_set(params, "source.target.user_intensity_path"):
        raise ParameterBoundsError(
            what=(
                "source.target_spec: brightness_temperature is mutually "
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
                "user_intensity_path": _value_of(params, "source.target.user_intensity_path"),
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
                "source.target_spec: brightness_temperature is mutually "
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

    # CU-293 (owner ruling 2026-08-01): the S11 door was the one door with no
    # guard against its S12 twin.  Because the inferrer dispatches S11 first,
    # its absence meant a user-supplied radiance temperature was silently
    # discarded at evaluate() while this same seam already refused the pair —
    # the two entry points disagreed.  Exclusivity is over
    # ``radiance_temperature_K`` alone: the S12 band edges are a completeness
    # requirement, which stays with the inferrer (module scope, above).
    if _is_user_set(params, "source.target.radiance_temperature_K"):
        raise ParameterBoundsError(
            what=(
                "source.target_spec: brightness_temperature is mutually "
                "exclusive with radiance_temperature_K (S11 vs S12)"
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
                "radiance_temperature_K_set": True,
                "radiance_temperature_K": _value_of(params, "source.target.radiance_temperature_K"),
            },
        )


def check_radiance_temperature_conflicts(params: ParameterSet) -> None:
    """S12 door: raise if radiance_temperature_K is paired with a rival surface.

    No-op when ``radiance_temperature_K`` is not user-set.  Guard order (and
    text) is exactly the pre-CU-244 inline order in
    ``_inferrer._maybe_build_from_radiance_temperature``: (ε, T), then S8,
    then S10, then ρ-family, then S11.  The S12 *completeness* check (band
    edges required) is not an exclusivity rule and stays in the inferrer.
    """
    if not _is_user_set(params, "source.target.radiance_temperature_K"):
        return

    if _is_user_set(params, "source.target.temperature") or _is_user_set(
        params, "source.target.emissivity"
    ):
        raise ParameterBoundsError(
            what=(
                "source.target_spec: radiance_temperature is mutually "
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
                "source.target_spec: radiance_temperature is mutually "
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
                "user_radiance_path": _value_of(params, "source.target.user_radiance_path"),
            },
        )

    if _is_user_set(params, "source.target.user_intensity_path"):
        raise ParameterBoundsError(
            what=(
                "source.target_spec: radiance_temperature is mutually "
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
                "user_intensity_path": _value_of(params, "source.target.user_intensity_path"),
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
                "source.target_spec: radiance_temperature is mutually "
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
                "source.target_spec: radiance_temperature is mutually "
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


def check_intensity_door_extent_conflicts(params: ParameterSet) -> None:
    """S10/S10b door: raise if the intensity door is paired with a declared extent.

    CU-256 (owner ruling 2026-07-29).  The intensity door describes the target
    as a zero-dimensional emitter of ``I(λ)`` [W/sr/µm]; a declared extent
    (``geometry.target.projected_area_m2`` or ``geometry.target.shape``)
    describes it as a finite object on the sky.  They are two mutually
    exclusive descriptions of the same target, so supplying both is an
    over-specification and is refused here — at the door, before
    :class:`~radiant.core.descriptors.T7IntensityAtSource` publishes its
    fictitious reference area.

    Why refusing beats reconciling: the T7 path deliberately publishes
    ``A_fict`` as ``stage_outputs["source"]["projected_area_m2"]`` so the
    ADR-0004 algebra cancels (``L·A_t = (I/A_fict)·A_fict = I``).  The
    consequence is that the derived ``angular_extent_rad`` is a sentinel
    (``√A_fict/d``, ~1e-11 rad), which silently disarms the matrix §7
    point-source validity guard in
    ``radiant.optics.stage._validate_psf_regime_consistency`` — a 500 m²
    target at 25 km (≈20 pixels across) evaluated as a point source.
    Publishing the *real* area would break the radiometry; publishing the
    real angular extent would re-classify the regime (Rule 10).  The
    over-specification is refused instead, so neither trade-off arises.

    ``source.target.point_intensity_area_m2`` is **not** an extent surface —
    it is the emitting area inside the S10b blackbody intensity itself
    (``I(λ) = ε·A·B(λ,T)``) and belongs to the door.

    No-op when no intensity-door surface is user-set.
    """
    door_set = [s for s in _INTENSITY_DOOR_SURFACES if _is_user_set_nonempty(params, s)]
    if not door_set:
        return

    extent_set = [
        s
        for s in _DECLARED_EXTENT_SURFACES
        if _is_user_set(params, s) and _value_of(params, s) not in _EXTENT_UNSET_SENTINELS
    ]
    if not extent_set:
        return

    raise ParameterBoundsError(
        what=(
            "source.target_spec: the point-source intensity door "
            f"({', '.join(door_set)}) is mutually exclusive with the declared "
            f"target extent ({', '.join(extent_set)})"
        ),
        why=(
            "An intensity I(λ) [W/sr/µm] describes the target as a "
            "zero-dimensional emitter — the area has already been integrated "
            "out.  A declared projected area or shape describes it as a "
            "resolved object on the sky.  Supplying both over-specifies the "
            "target: RADIANT would have two inconsistent statements of how "
            "big it is, and the intensity path can only honour one of them "
            "(it publishes a fictitious reference area so the ADR-0004 "
            "algebra cancels, which would silently discard the declared "
            "extent and disarm the matrix §7 point-source validity check)."
        ),
        action=(
            "Pick one description of the target.  For an unresolved point "
            "source, remove "
            f"{' and '.join(extent_set)}.  For a resolved target, remove "
            f"{' and '.join(door_set)} and specify the target's radiance "
            "instead (source.target.temperature + .emissivity, "
            "source.target.user_radiance_path, or a brightness/radiance "
            "temperature) alongside the extent."
        ),
        context={s: _value_of(params, s) for s in door_set + extent_set},
    )


def check_user_radiance_conflicts(params: ParameterSet) -> None:
    """S8 door: raise if ``user_radiance_path`` is paired with a rival surface.

    CU-293 (folded CU-294).  No-op when ``user_radiance_path`` is not user-set
    or is empty.  Guard order (and text, modulo the CU-295 module prefix) is
    exactly the pre-extraction inline order in
    ``_inferrer._maybe_build_from_user_radiance``: (ε, T), then S10.

    The S8-vs-ρ and S8-vs-S11/S12 pairs are not repeated here — the ρ-family,
    S11 and S12 doors each already reject S8 symmetrically, and
    :func:`validate_target_spec` runs those first (inferrer dispatch order), so
    the seam and ``evaluate()`` raise the same error for those pairs.
    """
    if not _is_user_set_nonempty(params, "source.target.user_radiance_path"):
        return

    if _is_user_set(params, "source.target.temperature") or _is_user_set(
        params, "source.target.emissivity"
    ):
        raise ParameterBoundsError(
            what=(
                "source.target_spec: user_radiance_path is mutually "
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
                "source.target_spec: user_radiance_path is mutually "
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
                "user_intensity_path": _value_of(params, "source.target.user_intensity_path"),
            },
        )


def check_point_intensity_conflicts(params: ParameterSet) -> None:
    """S10b door: raise if a point-intensity surface is paired with a rival.

    CU-293 (folded CU-294).  No-op when neither point-intensity mode is
    user-set.  Guard order (and text, modulo the CU-295 module prefix) is
    exactly the pre-extraction inline order in
    ``_inferrer._maybe_build_from_point_intensity``: the two modes both set
    (blackbody ``point_intensity_temperature_K`` vs scalar
    ``point_intensity_band_W_per_sr``), then (ε, T), then the S10 CSV.

    The declared-extent conflict is a separate rule with its own owner ruling
    and lives in :func:`check_intensity_door_extent_conflicts`; the inferrer
    calls that one first, and so does :func:`validate_target_spec`.
    """
    bb_set = _is_user_set(params, "source.target.point_intensity_temperature_K")
    scalar_set = _is_user_set(params, "source.target.point_intensity_band_W_per_sr")
    if not bb_set and not scalar_set:
        return

    if bb_set and scalar_set:
        raise ParameterBoundsError(
            what=(
                "source.target_spec: point_intensity_temperature_K (blackbody) and "
                "point_intensity_band_W_per_sr (scalar) are both set"
            ),
            why="They are two mutually-exclusive ways to define the same point-source intensity.",
            action=(
                "Set exactly one: point_intensity_temperature_K (+area, emissivity) for a "
                "blackbody emitter, or point_intensity_band_W_per_sr for a band flux."
            ),
            context={},
        )

    for other, label in (
        ("source.target.temperature", "temperature"),
        ("source.target.emissivity", "emissivity"),
        ("source.target.user_intensity_path", "user_intensity_path"),
    ):
        if _is_user_set(params, other):
            raise ParameterBoundsError(
                what=(
                    "source.target_spec: point-intensity inputs are mutually exclusive with "
                    f"source.target.{label}"
                ),
                why=(
                    "The point-intensity path supplies an absolute I(λ) at the target plane; "
                    "combining it with a surface-radiance (ε, T) or the CSV intensity path "
                    "over-specifies the target."
                ),
                action=(
                    f"Remove source.target.{label}, or drop the point_intensity_* params to "
                    "use that form instead."
                ),
                context={"conflicting_param": f"source.target.{label}"},
            )


def check_user_intensity_conflicts(params: ParameterSet) -> None:
    """S10 door: raise if ``user_intensity_path`` is paired with (ε, T).

    CU-293 (folded CU-294).  No-op when ``user_intensity_path`` is not user-set
    or is empty.  Text is the pre-extraction inline text in
    ``_inferrer._maybe_build_from_user_intensity`` modulo the CU-295 module
    prefix.  Every other S10 pairing (ρ-family, S11, S12, S8, S10b) is rejected
    symmetrically by the door that owns it, which dispatches first.
    """
    if not _is_user_set_nonempty(params, "source.target.user_intensity_path"):
        return

    if _is_user_set(params, "source.target.temperature") or _is_user_set(
        params, "source.target.emissivity"
    ):
        raise ParameterBoundsError(
            what=(
                "source.target_spec: user_intensity_path is mutually "
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


def check_reflectance_conflicts(params: ParameterSet) -> None:
    """S4/S5/S6 door: raise if a reflectance surface is paired with a rival surface.

    No-op when no ρ-family surface is user-set.  Guard order (and text) is
    exactly the pre-CU-244 inline order in
    ``_inferrer._maybe_build_from_reflectance``: the reflectance/albedo alias
    exclusivity (schema-layer validator), then (ε, T), then S8, then S10, then
    S11/S12.
    """
    if not _rho_family_user_set(params):
        return

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
                "source.target_spec: reflectance/albedo is mutually "
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
                "source.target_spec: reflectance/albedo is mutually "
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
                "user_radiance_path": _value_of(params, "source.target.user_radiance_path"),
            },
        )

    if _is_user_set(params, "source.target.user_intensity_path"):
        raise ParameterBoundsError(
            what=(
                "source.target_spec: reflectance/albedo is mutually "
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
                "user_intensity_path": _value_of(params, "source.target.user_intensity_path"),
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
                "source.target_spec: reflectance/albedo is mutually "
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


def check_emissivity_path_conflicts(params: ParameterSet) -> None:
    """S1-with-ε(λ) door: raise if ``emissivity_path`` is paired with a rival surface.

    CU-318.  No-op when ``emissivity_path`` is not user-set or is empty.  Guard
    order (and text, modulo the CU-295 module prefix) is exactly the
    pre-extraction inline order in ``_inferrer._load_emissivity_on_grid``: the
    single :data:`_EMISSIVITY_PATH_CONFLICTS` sweep, first hit wins.

    Most of those pairs are already refused by the rival door's own symmetric
    guard, which :func:`validate_target_spec` runs first (inferrer dispatch
    order — the ε(λ) door dispatches last, after S10).  The pair unique to this
    door is ``emissivity_path`` + scalar ``source.target.emissivity``: before
    CU-318 it reached only ``evaluate()``.
    """
    if not _is_user_set_nonempty(params, "source.target.emissivity_path"):
        return
    csv_path = str(_value_of(params, "source.target.emissivity_path"))

    for other in _EMISSIVITY_PATH_CONFLICTS:
        if _is_user_set(params, other):
            raise ParameterBoundsError(
                what=(
                    "source.target_spec: source.target.emissivity_path is "
                    f"mutually exclusive with {other}"
                ),
                why=(
                    "emissivity_path defines a thermal target via ε(λ)·B(T); "
                    "combining it with a scalar-ε, reflective, radiance, or "
                    "brightness/radiance-temperature surface over-specifies the target."
                ),
                action=f"Set either source.target.emissivity_path or {other}, not both.",
                context={"emissivity_path": csv_path, "conflict": other},
            )


def validate_target_spec(params: ParameterSet) -> None:
    """Raise :class:`ParameterBoundsError` if the target spec is over-specified.

    Runs the per-door exclusivity guards in the inferrer's dispatch order
    (S11 → S12 → S4/S5/S6 → S8 → S10b → S10 → S1-with-ε(λ)), so whenever ``evaluate()`` would
    raise an exclusivity error via ``_inferrer._build_target_descriptor``, the
    first error raised here is that same error — same what/why/action.  A no-op
    on a cleanly specified (or not-yet-complete) target: completeness is
    deliberately out of scope.

    CU-293 closed the last gap in that equivalence.  This seam used to be
    *stricter* than ``evaluate()`` for an S11 + S12 pair, because the inferrer's
    S11 builder dispatched first and had no S12 guard; that guard now exists
    (:func:`check_brightness_temperature_conflicts`), so the two entry points
    agree on every pair the doors know about.  CU-318 closed the mirror-image
    gap: the ε(λ) door's guard was still inlined in the inferrer, so
    ``emissivity_path`` + scalar ``source.target.emissivity`` — the one pair no
    other door refuses symmetrically — reached only ``evaluate()``.  It is now
    :func:`check_emissivity_path_conflicts`, last in dispatch order.
    """
    check_brightness_temperature_conflicts(params)
    check_radiance_temperature_conflicts(params)
    check_reflectance_conflicts(params)
    check_user_radiance_conflicts(params)
    check_intensity_door_extent_conflicts(params)
    check_point_intensity_conflicts(params)
    check_user_intensity_conflicts(params)
    check_emissivity_path_conflicts(params)
