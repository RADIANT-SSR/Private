"""Assembly functions — the §6.1 at-aperture equation for Option C Stage 3.

This module implements the two pure functions that consume descriptor
outputs from Stage 1/2 and ``AtmosphericQuantities`` from Stage 3 backends
and produce the at-aperture spectral radiance arrays that Stage 4 will
make authoritative:

- :func:`assemble_target_at_aperture` — one match arm per
  ``TargetDescriptor.target_location`` and variant, per the ADR-0002 cell
  mapping table.
- :func:`assemble_background_at_aperture` — one match arm per
  ``BackgroundDescriptor`` variant.

The assembly equation (matrix §6.1, reproduced here in math form)::

    L_t,aperture(λ) = [ ε·B(T_t)                                  # self-emission
                        + ρ · τ_sun · E_TOA · cos(θ_s) / π        # direct solar
                        + ρ · (E_sky_scattered + E_sky_thermal)/π # diffuse sky
                      ] · τ_up
                      + L_path_up

Kirchhoff (Rule 5) ties ρ = 1 − ε for opaque Lambertian surfaces, so
``T1Thermal`` (ρ ≡ 0 except for the implied-hot-target case), ``T3Mixed``
(ρ derived), and ``T2Reflective`` (ε ≡ 0) are specialisations of the
master equation rather than independent formulas.

Rule 11 (import discipline)
---------------------------
This module imports only from ``radiant.core`` and ``radiant.atmosphere``.
No cross-stage physics imports.  ``radiant.core.descriptors`` holds the
discriminated payload types.

Rule 9 (EE_box)
---------------
Assembly does **not** apply EE_box.  The regime-dependent point-spread
factor enters exclusively in ``SpectralIntegrationStage`` (Stage 5 of the
legacy chain).  Assembly produces the *full* at-aperture radiance arrays.

Decision #6 (at-aperture pass-through warn)
-------------------------------------------
When a :class:`T5AtAperture` descriptor is used, the user has already
propagated the scene through to the pupil.  Running such a scenario with a
non-trivial atmosphere (``τ_up ≠ 1`` anywhere) is almost certainly a user
error — we emit a :class:`UserWarning` and pass the user spectrum through
unchanged.  Rule 17 — no silent failure.
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass
from typing import Literal, overload

import numpy as np

from radiant.atmosphere._quantities import AtmosphericQuantities
from radiant.core.blackbody import planck_spectral_radiance
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
from radiant.core.parameters import ParameterBoundsError
from radiant.core.spectral import SpectralData

# Floor for "non-trivial atmosphere" detection in the T5 warn-if-atm arm.
# τ ≥ 1 − _T5_TAU_TRIVIAL_TOL everywhere → trivial; otherwise warn.
_T5_TAU_TRIVIAL_TOL: float = 1e-9
# Floor for "non-zero L_path" detection in the T5 warn-if-atm arm.
_T5_LPATH_TRIVIAL_TOL: float = 1e-12


# ---------------------------------------------------------------------------
# no_atmosphere sub-case preconditions (Stage 7, Option C)
# ---------------------------------------------------------------------------


def validate_no_atmosphere_subcase(
    target: TargetDescriptor,
    background: BackgroundDescriptor | None,
    los: LineOfSightGeometry | None,
    h_sensor: float | None,
    h_sensor_user_set: bool,
) -> None:
    """Enforce matrix §7 preconditions for the three no_atmosphere sub-cases.

    Only called by :class:`AtmosphereStage` when
    ``target.target_location == "no_atmosphere"``.  Pure validation —
    raises :class:`ParameterBoundsError` on violation; returns ``None``
    on success.  Does not mutate inputs.

    Matrix §7 rules enforced here:

    * ``space`` requires a positive ``platform.h_sensor`` set by the
      user (Rule 17 — no silent default).
    * ``space`` with an Earth-intercepting LOS raises (v1 has no
      earthlimb model, §7 "no_atmosphere (space) + LOS intercepts
      Earth").
    * ``ground_test`` / ``lab_test`` require a
      :class:`UserSpectralBackground` background; §7 "no_atmosphere
      (ground_test / lab_test) without UserSpectralBackground".

    The ``lab_test`` dark-cal regime (no illumination) is permitted;
    illumination is a T2/T3 concern and is orthogonal to the sub-case
    validation handled here.

    Parameters
    ----------
    target:
        TargetDescriptor published by SourceStage.  The
        ``target_location`` must be ``"no_atmosphere"``.
    background:
        BackgroundDescriptor (may be ``None``).  Matrix §7 requires
        UserSpectralBackground for ground_test/lab_test.
    los:
        LineOfSightGeometry.  Required for the space sub-case
        Earth-intercept check; optional otherwise.
    h_sensor:
        Sensor altitude above MSL [m], from ``params["platform.h_sensor"]``.
        Only consulted for the space sub-case; ignored otherwise.
    h_sensor_user_set:
        ``True`` iff the user explicitly set ``platform.h_sensor``.  The
        space sub-case rejects the default value loudly rather than
        silently using 0.0 (Rule 17).
    """
    if target.target_location != "no_atmosphere":
        return  # Not a no_atmosphere cell — nothing to validate here.

    subcase = target.no_atmosphere_subcase

    if subcase == "space":
        if not h_sensor_user_set or h_sensor is None or h_sensor <= 0.0:
            raise ParameterBoundsError(
                what=(
                    f"assembly.validate_no_atmosphere_subcase: "
                    f"no_atmosphere_subcase='space' requires a positive "
                    f"user-supplied platform.h_sensor (got h_sensor="
                    f"{h_sensor!r}, user_set={h_sensor_user_set})"
                ),
                why=(
                    "The space sub-case runs an Earth-intercept check on "
                    "the sensor → target LOS (matrix §7; v1 has no "
                    "earthlimb model).  The check requires the sensor "
                    "altitude; silently defaulting it to 0 (ground) would "
                    "produce a non-physical result (Rule 17)."
                ),
                action=(
                    "Set platform.h_sensor to the sensor altitude above "
                    "MSL in meters (e.g. 800_000 for 800 km LEO).  This "
                    "parameter is a Stage-7 stop-gap that the "
                    "SensorDescriptor follow-on ADR will subsume."
                ),
                context={
                    "h_sensor": h_sensor,
                    "h_sensor_user_set": h_sensor_user_set,
                    "no_atmosphere_subcase": subcase,
                },
            )
        if los is None:
            raise ParameterBoundsError(
                what=(
                    "assembly.validate_no_atmosphere_subcase: "
                    "no_atmosphere_subcase='space' requires a "
                    "LineOfSightGeometry; got None"
                ),
                why=(
                    "The Earth-intercept check needs the observer zenith "
                    "and target altitude to project the LOS onto the "
                    "Earth sphere."
                ),
                action=(
                    "Check that SourceStage published a LineOfSightGeometry "
                    "for the no_atmosphere target (it should — see "
                    "_inferrer._infer_los)."
                ),
                context={"no_atmosphere_subcase": subcase},
            )
        if los.intercepts_earth(h_sensor):
            raise ParameterBoundsError(
                what=(
                    f"assembly.validate_no_atmosphere_subcase: "
                    f"no_atmosphere_subcase='space' LOS from h_sensor="
                    f"{h_sensor} m to h_tgt={los.h_tgt} m at theta_o="
                    f"{los.theta_o} rad intersects the Earth"
                ),
                why=(
                    "Matrix §7: no_atmosphere (space) + LOS intercepts "
                    "Earth is rejected because v1 has no earthlimb "
                    "background model.  A space-to-space scenario with "
                    "an Earth-intersecting LOS is physically a ground / "
                    "earthlimb scenario and must be routed through a "
                    "terrestrial / airborne target_location instead."
                ),
                action=(
                    "Either (a) increase h_tgt so the target is above the "
                    "Earth limb at this zenith, (b) reduce theta_o so the "
                    "LOS points further from the limb, or (c) switch "
                    "target_location to terrestrial / airborne."
                ),
                context={
                    "h_sensor": h_sensor,
                    "h_tgt": los.h_tgt,
                    "theta_o": los.theta_o,
                    "no_atmosphere_subcase": subcase,
                },
            )
        return

    if subcase in ("ground_test", "lab_test"):
        if not isinstance(background, UserSpectralBackground):
            variant = type(background).__name__ if background is not None else "None"
            raise ParameterBoundsError(
                what=(
                    f"assembly.validate_no_atmosphere_subcase: "
                    f"no_atmosphere_subcase={subcase!r} requires a "
                    f"UserSpectralBackground; got {variant}"
                ),
                why=(
                    "Matrix §7: no_atmosphere (ground_test / lab_test) "
                    "has no sensible default for test-range or chamber "
                    "radiance.  The user must supply a "
                    "UserSpectralBackground carrying the measured or "
                    "modelled L_bg(λ) on the chain wavelength grid."
                ),
                action=(
                    "Construct a UserSpectralBackground with "
                    "L_bg: SpectralData in W/m²/sr/µm and publish it "
                    "as the background descriptor (via SourceStage's "
                    "stage_outputs['source']['background'])."
                ),
                context={
                    "no_atmosphere_subcase": subcase,
                    "background_variant": variant,
                },
            )
        return

    # no_atmosphere_subcase is None or an unknown value — the descriptor
    # constructor already rejected these, so this arm is unreachable.
    # Defensive: raise if we somehow land here.
    raise ParameterBoundsError(  # pragma: no cover
        what=(
            f"assembly.validate_no_atmosphere_subcase: unknown "
            f"no_atmosphere_subcase={subcase!r}"
        ),
        why="Valid sub-cases are 'space', 'ground_test', 'lab_test'.",
        action="Set no_atmosphere_subcase on the TargetDescriptor.",
        context={"no_atmosphere_subcase": subcase},
    )


# ---------------------------------------------------------------------------
# Per-term decomposition (Stage 6, Option C — report_components introspection)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AssemblyComponents:
    """Per-term decomposition of a §6.1 assembly call.

    Produced by :func:`assemble_target_at_aperture` when
    ``report_components=True``.  Every field is a 1-D ndarray on the
    atmosphere wavelength grid (W/m²/sr/µm).  The assembly equation is
    exactly::

        total = (self_emission
                 + direct_solar
                 + diffuse_sky_scattered
                 + diffuse_sky_thermal) * tau_up
              + path_up

    so all fields sum (with the shared τ_up factor on the non-path terms)
    to the returned ``total``.

    Fields
    ------
    total:
        The same at-aperture radiance ``assemble_target_at_aperture``
        returns in its scalar mode (``report_components=False``).
    self_emission:
        ``ε · B(T_t)`` — zero for T2, non-zero for T1/T3.  Pre-τ_up.
    direct_solar:
        ``ρ · τ_sun · E_TOA · cos(θ_s) / π`` — zero for T1 (ρ=0) or sun
        below horizon.  Pre-τ_up.
    diffuse_sky_scattered:
        ``ρ · E_sky_scattered / π`` — the single-scatter diffuse solar
        contribution.  Pre-τ_up.  Stage 6 deliverable.
    diffuse_sky_thermal:
        ``ρ · E_sky_thermal / π`` — the atmospheric-thermal diffuse
        contribution.  Pre-τ_up.  Stage 6 deliverable.
    tau_up_factor:
        The common ``τ_up(λ)`` multiplier applied to the four pre-τ
        terms (exposed for audit-time arithmetic verification).
    path_up:
        The additive ``L_path_up(λ)`` — not multiplied by τ_up.
    """

    total: np.ndarray
    self_emission: np.ndarray
    direct_solar: np.ndarray
    diffuse_sky_scattered: np.ndarray
    diffuse_sky_thermal: np.ndarray
    tau_up_factor: np.ndarray
    path_up: np.ndarray


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _grid_match(lam: np.ndarray, atm: AtmosphericQuantities) -> None:
    """Raise if a descriptor's spectral grid does not match the atm grid."""
    if lam.shape != atm.wavelength_um.shape or not np.array_equal(
        lam, atm.wavelength_um
    ):
        raise ParameterBoundsError(
            what=(
                "assembly: descriptor spectral grid does not match "
                "AtmosphericQuantities.wavelength_um"
            ),
            why=(
                "Assembly is grid-aligned arithmetic; resampling is the "
                "caller's responsibility (Rule 2 — conversions at "
                "boundaries only)."
            ),
            action=(
                "Resample ε(λ) / ρ(λ) onto the chain wavelength_um grid "
                "before calling assembly, or run evaluate() on the "
                "descriptor grid."
            ),
            context={"descriptor_shape": lam.shape, "atm_shape": atm.wavelength_um.shape},
        )


def _extract_sd_values(sd: SpectralData, atm: AtmosphericQuantities) -> np.ndarray:
    """Validate and extract grid-aligned values from a SpectralData field."""
    _grid_match(sd.wavelength_um, atm)
    return np.asarray(sd.values, dtype=np.float64)


def _cos_theta_s(los: LineOfSightGeometry) -> float:
    """Cosine of the solar zenith at the target — 0 if no sun is specified.

    Matrix §6.1: for no-sun (pure thermal) scenarios, the direct-solar
    term must vanish exactly.  Returning 0 produces that, and avoids
    contaminating the thermal-only anchor cells with a spurious cos·τ·E
    term when ``theta_s`` is None.
    """
    if los.theta_s is None:
        return 0.0
    # Matrix §7: sun below horizon (θ_s > π/2) — direct beam contributes
    # zero.  cos(θ_s) is returned clamped at 0 rather than raising; the
    # descriptor constructor already constrained θ_s ∈ [0, π].
    c = float(np.cos(los.theta_s))
    return c if c > 0.0 else 0.0


def _direct_solar_term(
    rho: np.ndarray,
    atm: AtmosphericQuantities,
    cos_theta_s: float,
) -> np.ndarray:
    """ρ · τ_sun · E_TOA · cos(θ_s) / π  — the direct-beam reflected term.

    Returns a zero array when cos(θ_s) = 0 (pure-thermal scenarios).
    """
    if cos_theta_s <= 0.0:
        return np.zeros_like(atm.E_TOA, dtype=np.float64)
    return np.asarray(
        rho * atm.tau_sun * atm.E_TOA * cos_theta_s / np.pi, dtype=np.float64
    )


def _diffuse_sky_term(rho: np.ndarray, atm: AtmosphericQuantities) -> np.ndarray:
    """ρ · (E_sky_scattered + E_sky_thermal) / π  — the diffuse-sky term.

    Stage 6 (Option C) — the *consumed* sum is unchanged so the §6.1
    assembly math is bit-invariant with the Stage 4 baseline (modulo
    the new non-zero ``E_sky_scattered``).  Per-component introspection
    is available via :func:`_diffuse_sky_scattered_term` and
    :func:`_diffuse_sky_thermal_term` (called from the ``report_components``
    branch of :func:`assemble_target_at_aperture`).
    """
    e_sky = atm.E_sky_scattered + atm.E_sky_thermal
    return np.asarray(rho * e_sky / np.pi, dtype=np.float64)


def _diffuse_sky_scattered_term(
    rho: np.ndarray, atm: AtmosphericQuantities,
) -> np.ndarray:
    """ρ · E_sky_scattered / π — the single-scatter diffuse-solar term.

    Stage 6 (Option C) per-term introspection.  Returned alone only when
    the caller has asked for ``report_components``; the assembly math
    still consumes the sum via :func:`_diffuse_sky_term`.
    """
    return np.asarray(rho * atm.E_sky_scattered / np.pi, dtype=np.float64)


def _diffuse_sky_thermal_term(
    rho: np.ndarray, atm: AtmosphericQuantities,
) -> np.ndarray:
    """ρ · E_sky_thermal / π — the atmospheric-thermal diffuse term.

    Stage 6 (Option C) per-term introspection.  Returned alone only when
    the caller has asked for ``report_components``; the assembly math
    still consumes the sum via :func:`_diffuse_sky_term`.
    """
    return np.asarray(rho * atm.E_sky_thermal / np.pi, dtype=np.float64)


def _is_trivial_atmosphere(atm: AtmosphericQuantities) -> bool:
    """True iff every τ_up ≈ 1 and every L_path_up ≈ 0.

    Used by the T5 at-aperture arm to distinguish a vacuum / exo
    atmosphere from any real atmospheric path.
    """
    return bool(
        np.all(atm.tau_up >= 1.0 - _T5_TAU_TRIVIAL_TOL)
        and np.all(np.abs(atm.L_path_up) <= _T5_LPATH_TRIVIAL_TOL)
    )


# ---------------------------------------------------------------------------
# Target assembly
# ---------------------------------------------------------------------------


@overload
def assemble_target_at_aperture(
    target: TargetDescriptor,
    atm: AtmosphericQuantities,
    los: LineOfSightGeometry | None,
) -> np.ndarray: ...


@overload
def assemble_target_at_aperture(
    target: TargetDescriptor,
    atm: AtmosphericQuantities,
    los: LineOfSightGeometry | None,
    *,
    report_components: Literal[True],
) -> AssemblyComponents: ...


@overload
def assemble_target_at_aperture(
    target: TargetDescriptor,
    atm: AtmosphericQuantities,
    los: LineOfSightGeometry | None,
    *,
    report_components: Literal[False],
) -> np.ndarray: ...


def assemble_target_at_aperture(
    target: TargetDescriptor,
    atm: AtmosphericQuantities,
    los: LineOfSightGeometry | None,
    *,
    report_components: bool = False,
) -> np.ndarray | AssemblyComponents:
    """Compute the target at-aperture spectral radiance [W/m²/sr/µm].

    Dispatches on ``target.target_location`` first, then on the
    descriptor variant, per the ADR-0002 cell-mapping table:

    ================  =========  ====================================
    target_location   variant    Arm
    ================  =========  ====================================
    at_aperture       T5         pass-through (warn-if-atm; Decision #6)
    terrestrial       T1         ε·B(T_t)·τ_up + L_path_up
    terrestrial       T2         ρ·[τ_sun·E_TOA·cosθ_s/π + E_sky/π]·τ_up + L_path_up
    terrestrial       T3         T1 + T2 with ρ = 1 − ε (Kirchhoff)
    airborne          T1/T2/T3   same as terrestrial; backends compute
                                  τ/L_path from h_tgt > 0 (Stage 5)
    no_atmosphere     T1         ε·B(T_t)·τ_up + L_path_up  (τ_up ≡ 1,
                                  L_path_up ≡ 0 for ExoAtmosphere)
    no_atmosphere     T5         pass-through (Table A vacuum / lab)
    ================  =========  ====================================

    Parameters
    ----------
    target:
        The :class:`TargetDescriptor` published by SourceStage.
    atm:
        The :class:`AtmosphericQuantities` produced by the backend on the
        chain wavelength grid.
    los:
        The :class:`LineOfSightGeometry` published by SourceStage, or
        ``None`` if the target is at_aperture.  Used only for θ_s.
    report_components:
        When True, return an :class:`AssemblyComponents` dataclass with
        the per-term decomposition alongside the summed total.  The
        default (``False``) returns the total only, preserving the
        Stage-4 ``np.ndarray`` contract.  Stage 6 (Option C) — enables
        the MWIR crossover audit (Cells 25/26/40/41) without forking the
        assembly math.

    Returns
    -------
    numpy.ndarray
        1-D spectral radiance array in W/m²/sr/µm on the atm wavelength
        grid (default), OR
    AssemblyComponents
        Per-term decomposition with the same ``total`` field when
        ``report_components=True``.

    Raises
    ------
    ParameterBoundsError
        If the descriptor's spectral grid disagrees with the atm grid,
        or the descriptor variant is unsupported.
    """
    lam = atm.wavelength_um

    # --- at_aperture (T5 pass-through; Decision #6) ---
    if target.target_location == "at_aperture":
        if not isinstance(target, T5AtAperture):
            raise ParameterBoundsError(
                what=(
                    f"assembly: target_location='at_aperture' requires "
                    f"T5AtAperture variant; got {type(target).__name__}"
                ),
                why=(
                    "At-aperture targets carry a user-supplied spectrum by "
                    "definition.  Other variants (T1/T2/T3) model the "
                    "reflected / emitted physics and require an atmosphere."
                ),
                action="Use T5AtAperture for at_aperture target_location.",
                context={"target_location": target.target_location, "variant": type(target).__name__},
            )
        # Decision #6: pass through L_t_aperture unmodified; warn if the
        # caller paired the pass-through with a non-trivial atmosphere.
        total = _assemble_t5(target, atm)
        if report_components:
            zeros = np.zeros_like(atm.wavelength_um, dtype=np.float64)
            # T5 pass-through has no decomposable physics — every branch
            # except ``total`` is identically zero and τ_up is 1 by
            # construction (or should be; if not, the pass-through warned).
            return AssemblyComponents(
                total=total,
                self_emission=zeros,
                direct_solar=zeros,
                diffuse_sky_scattered=zeros,
                diffuse_sky_thermal=zeros,
                tau_up_factor=np.ones_like(atm.wavelength_um, dtype=np.float64),
                path_up=zeros,
            )
        return total

    # --- Every non-at_aperture arm requires a LineOfSightGeometry ---
    if los is None:
        raise ParameterBoundsError(
            what=(
                f"assembly: target_location={target.target_location!r} "
                "requires a LineOfSightGeometry; got None"
            ),
            why=(
                "Non-at-aperture assembly uses θ_o / θ_s / δφ from the LOS "
                "geometry; SourceStage must publish it alongside the "
                "descriptor."
            ),
            action=(
                "Check that SourceStage constructed the LOS and published "
                "it to stage_outputs['source']['los_geometry']."
            ),
            context={"target_location": target.target_location},
        )

    cos_ts = _cos_theta_s(los)

    # --- T1Thermal — pure-thermal graybody ---
    if isinstance(target, T1Thermal):
        if report_components:
            return _components_t1(target, atm, cos_ts)
        return _assemble_t1(target, atm, cos_ts)

    # --- T2Reflective — pure-reflective Lambertian ---
    if isinstance(target, T2Reflective):
        if report_components:
            return _components_t2(target, atm, cos_ts)
        return _assemble_t2(target, atm, cos_ts)

    # --- T3Mixed — Kirchhoff ρ = 1 − ε ---
    if isinstance(target, T3Mixed):
        if report_components:
            return _components_t3(target, atm, cos_ts)
        return _assemble_t3(target, atm, cos_ts)

    # --- T5 but target_location != at_aperture — already blocked by
    #     T5AtAperture.__post_init__, but guard anyway. ---
    if isinstance(target, T5AtAperture):
        raise ParameterBoundsError(
            what=(
                "assembly: T5AtAperture descriptor must have "
                "target_location='at_aperture'; this should have been "
                "caught at construction"
            ),
            why="T5 has no atmospheric-path arm; it carries pre-propagated radiance.",
            action="Switch to T1/T2/T3 for terrestrial/airborne/no_atmosphere targets.",
            context={"target_location": target.target_location},
        )

    raise ParameterBoundsError(
        what=f"assembly: unsupported TargetDescriptor variant {type(target).__name__}",
        why="Stage 3 of Option C only knows T1/T2/T3/T5.",
        action="Extend assembly with the new variant (update ADR-0002 first).",
        context={"variant": type(target).__name__},
    )


def _assemble_t1(
    target: T1Thermal,
    atm: AtmosphericQuantities,
    cos_theta_s: float,
) -> np.ndarray:
    """T1 thermal graybody assembly: ε·B(T_t)·τ_up + L_path_up.

    T1 implies ρ = 0 (pure-thermal — the "hot target" / LWIR case).  The
    solar and sky terms vanish identically, so the assembly reduces to
    self-emission attenuated by the up-leg plus the up-leg path radiance.
    """
    assert target.epsilon is not None  # mypy: constructor invariant
    epsilon = _extract_sd_values(target.epsilon, atm)
    L_self = epsilon * planck_spectral_radiance(atm.wavelength_um, target.T_t)
    # ρ ≡ 0 for T1; the direct-solar and sky branches vanish without a
    # separate code path (saves a branch and matches the math exactly).
    _ = cos_theta_s  # kept for symmetry with T2/T3 signatures
    return np.asarray(L_self * atm.tau_up + atm.L_path_up, dtype=np.float64)


def _assemble_t2(
    target: T2Reflective,
    atm: AtmosphericQuantities,
    cos_theta_s: float,
) -> np.ndarray:
    """T2 reflective Lambertian assembly: ρ·(τ_sun·E·cosθ_s + E_sky)·τ_up/π + L_path_up."""
    assert target.rho is not None  # mypy: constructor invariant
    rho = _extract_sd_values(target.rho, atm)
    direct = _direct_solar_term(rho, atm, cos_theta_s)
    diffuse = _diffuse_sky_term(rho, atm)
    # No self-emission for pure reflective (ε ≡ 0 → B·ε ≡ 0).
    return np.asarray((direct + diffuse) * atm.tau_up + atm.L_path_up, dtype=np.float64)


def _assemble_t3(
    target: T3Mixed,
    atm: AtmosphericQuantities,
    cos_theta_s: float,
) -> np.ndarray:
    """T3 mixed emit+reflect (Kirchhoff ρ = 1 − ε) assembly.

    The full §6.1 equation: self-emission plus direct-solar plus diffuse
    sky, all attenuated by τ_up, plus L_path_up.  Per Rule 5 the ρ(λ) is
    derived from ε(λ); the user does not supply ρ independently.
    """
    assert target.epsilon is not None  # mypy: constructor invariant
    epsilon = _extract_sd_values(target.epsilon, atm)
    rho = 1.0 - epsilon
    L_self = epsilon * planck_spectral_radiance(atm.wavelength_um, target.T_t)
    direct = _direct_solar_term(rho, atm, cos_theta_s)
    diffuse = _diffuse_sky_term(rho, atm)
    return np.asarray(
        (L_self + direct + diffuse) * atm.tau_up + atm.L_path_up,
        dtype=np.float64,
    )


def _components_t1(
    target: T1Thermal,
    atm: AtmosphericQuantities,
    cos_theta_s: float,
) -> AssemblyComponents:
    """Per-term T1 decomposition (Stage 6 introspection)."""
    assert target.epsilon is not None
    epsilon = _extract_sd_values(target.epsilon, atm)
    zeros = np.zeros_like(atm.wavelength_um, dtype=np.float64)
    L_self = np.asarray(
        epsilon * planck_spectral_radiance(atm.wavelength_um, target.T_t),
        dtype=np.float64,
    )
    _ = cos_theta_s  # T1 has ρ = 0
    total = np.asarray(L_self * atm.tau_up + atm.L_path_up, dtype=np.float64)
    return AssemblyComponents(
        total=total,
        self_emission=L_self,
        direct_solar=zeros,
        diffuse_sky_scattered=zeros,
        diffuse_sky_thermal=zeros,
        tau_up_factor=np.asarray(atm.tau_up, dtype=np.float64),
        path_up=np.asarray(atm.L_path_up, dtype=np.float64),
    )


def _components_t2(
    target: T2Reflective,
    atm: AtmosphericQuantities,
    cos_theta_s: float,
) -> AssemblyComponents:
    """Per-term T2 decomposition (Stage 6 introspection)."""
    assert target.rho is not None
    rho = _extract_sd_values(target.rho, atm)
    zeros = np.zeros_like(atm.wavelength_um, dtype=np.float64)
    direct = _direct_solar_term(rho, atm, cos_theta_s)
    diffuse_scat = _diffuse_sky_scattered_term(rho, atm)
    diffuse_therm = _diffuse_sky_thermal_term(rho, atm)
    diffuse_sum = diffuse_scat + diffuse_therm
    total = np.asarray(
        (direct + diffuse_sum) * atm.tau_up + atm.L_path_up, dtype=np.float64,
    )
    return AssemblyComponents(
        total=total,
        self_emission=zeros,
        direct_solar=direct,
        diffuse_sky_scattered=diffuse_scat,
        diffuse_sky_thermal=diffuse_therm,
        tau_up_factor=np.asarray(atm.tau_up, dtype=np.float64),
        path_up=np.asarray(atm.L_path_up, dtype=np.float64),
    )


def _components_t3(
    target: T3Mixed,
    atm: AtmosphericQuantities,
    cos_theta_s: float,
) -> AssemblyComponents:
    """Per-term T3 decomposition (Stage 6 introspection)."""
    assert target.epsilon is not None
    epsilon = _extract_sd_values(target.epsilon, atm)
    rho = 1.0 - epsilon
    L_self = np.asarray(
        epsilon * planck_spectral_radiance(atm.wavelength_um, target.T_t),
        dtype=np.float64,
    )
    direct = _direct_solar_term(rho, atm, cos_theta_s)
    diffuse_scat = _diffuse_sky_scattered_term(rho, atm)
    diffuse_therm = _diffuse_sky_thermal_term(rho, atm)
    diffuse_sum = diffuse_scat + diffuse_therm
    total = np.asarray(
        (L_self + direct + diffuse_sum) * atm.tau_up + atm.L_path_up,
        dtype=np.float64,
    )
    return AssemblyComponents(
        total=total,
        self_emission=L_self,
        direct_solar=direct,
        diffuse_sky_scattered=diffuse_scat,
        diffuse_sky_thermal=diffuse_therm,
        tau_up_factor=np.asarray(atm.tau_up, dtype=np.float64),
        path_up=np.asarray(atm.L_path_up, dtype=np.float64),
    )


def _assemble_t5(target: T5AtAperture, atm: AtmosphericQuantities) -> np.ndarray:
    """T5 at-aperture pass-through (Decision #6).

    Returns the user-supplied spectrum unmodified.  If the atmosphere
    bundle is non-trivial (τ_up < 1 or L_path_up > 0 anywhere), emit a
    UserWarning so the user sees that the atmosphere inputs are being
    ignored — silent bypass would hide a likely scenario bug (Rule 17).
    """
    if target.L_t_aperture is None:
        raise ParameterBoundsError(
            what=(
                "assembly: T5AtAperture without L_t_aperture cannot be "
                "assembled (sub_pixel/point_source at_aperture is deferred)"
            ),
            why=(
                "Only the extended at-aperture path is supported in v1.  "
                "A T5 descriptor with I_t_aperture instead of L_t_aperture "
                "corresponds to a sub_pixel/point_source at-aperture cell, "
                "which is currently blocked by the "
                "at_aperture⇒extended check in T5AtAperture.__post_init__."
            ),
            action=(
                "Use L_t_aperture (W/m²/sr/µm) for the extended at_aperture "
                "scene, or switch target_location away from at_aperture."
            ),
            context={},
        )
    L = _extract_sd_values(target.L_t_aperture, atm)
    if not _is_trivial_atmosphere(atm):
        warnings.warn(
            (
                "assembly.assemble_target_at_aperture: T5AtAperture paired "
                "with a non-trivial atmosphere (τ_up < 1 or L_path_up > 0 "
                "somewhere on the grid).  The pass-through arm ignores the "
                "atmosphere entirely — if you need atmospheric transport, "
                "switch to T1/T2/T3.  (Option C Decision #6)"
            ),
            UserWarning,
            stacklevel=3,
        )
    return L


# ---------------------------------------------------------------------------
# Background assembly
# ---------------------------------------------------------------------------


def assemble_background_at_aperture(
    background: BackgroundDescriptor | None,
    atm: AtmosphericQuantities,
    los: LineOfSightGeometry | None,
) -> np.ndarray | None:
    """Compute the background at-aperture spectral radiance [W/m²/sr/µm] or None.

    Dispatches on the :class:`BackgroundDescriptor` variant:

    ==========================  =========================================
    Variant                     Arm
    ==========================  =========================================
    None                        Return None (matrix Decision #13 — skip
                                bg photon term for computed-extended cells)
    AtApertureBackground        Pass through L_bg_aperture (or zeros)
    ColdSpaceBackground         Zeros (CMB is a SourceStage concern)
    GroundBackground            ε_g·B(T_g)·τ_full_up + L_path_full + diffuse
    UserSpectralBackground      Pass through L_bg (no atmospheric transport;
                                the subcase is ground_test/lab_test and
                                atmosphere is A0 pass-through)
    ==========================  =========================================

    Returns ``None`` when the background is ``None`` (Decision #13);
    SpectralIntegrationStage uses that to skip the background photon term
    in computed-extended cells.
    """
    if background is None:
        return None

    # Pass-through arms (no atmospheric transport).
    if isinstance(background, AtApertureBackground):
        if background.L_bg_aperture is None:
            # Matrix Decision #14: missing L_bg_aperture → treat as zero.
            return np.zeros_like(atm.wavelength_um, dtype=np.float64)
        return _extract_sd_values(background.L_bg_aperture, atm)

    if isinstance(background, ColdSpaceBackground):
        # Matrix §3.3: cold-space background is identically zero in v1.
        # CMB is a SourceStage option (not wired in v1); zodiacal light
        # deferred to v2.  Returning zeros is the honest answer.
        return np.zeros_like(atm.wavelength_um, dtype=np.float64)

    if isinstance(background, UserSpectralBackground):
        # ground_test / lab_test: chamber / test-range background.
        # Atmosphere is A0 pass-through, so no atmospheric transport.
        assert background.L_bg is not None  # constructor invariant
        return _extract_sd_values(background.L_bg, atm)

    # GroundBackground is the only arm that actually propagates through
    # the atmosphere; everything else is handled above.
    if isinstance(background, GroundBackground):
        if los is None:
            raise ParameterBoundsError(
                what=(
                    "assembly: GroundBackground requires a LineOfSightGeometry; "
                    "got None"
                ),
                why=(
                    "Ground background propagates from h = 0 to the sensor "
                    "through τ_full_up and L_path_full, both of which are "
                    "derived from the LOS."
                ),
                action=(
                    "Make sure SourceStage publishes LOS geometry for "
                    "terrestrial / airborne scenarios."
                ),
                context={},
            )
        return _assemble_ground_background(background, atm, los)

    raise ParameterBoundsError(
        what=(
            f"assembly: unsupported BackgroundDescriptor variant "
            f"{type(background).__name__}"
        ),
        why="Stage 3 of Option C only knows AtAperture/ColdSpace/Ground/UserSpectral.",
        action="Extend assembly with the new variant (update ADR-0002 first).",
        context={"variant": type(background).__name__},
    )


def _assemble_ground_background(
    bg: GroundBackground,
    atm: AtmosphericQuantities,
    los: LineOfSightGeometry,
) -> np.ndarray:
    """ε_g·B(T_g)·τ_full_up + L_path_full + (1 − ε_g) · diffuse terms · τ_full_up.

    Ground behaves like a T3 Kirchhoff surface at h = 0: self-emission
    plus reflected-diffuse (solar and sky), attenuated by the full
    ground-to-sensor column.  The direct-solar reflected component is
    omitted in v1 because the user's sub-pixel / point-source geometry
    mixes with this radiance without a distinct sun-glint term — matrix
    §3.2 notes that a single Kirchhoff graybody approximation is the v1
    scope.  Stage 6+ may add the direct-solar reflected term to the
    ground branch if MWIR mixed cells require it.
    """
    assert bg.epsilon_g is not None  # constructor invariant
    epsilon_g = _extract_sd_values(bg.epsilon_g, atm)
    rho_g = 1.0 - epsilon_g
    cos_ts = _cos_theta_s(los)

    # Self-emission at ground temperature.
    L_self = epsilon_g * planck_spectral_radiance(atm.wavelength_um, bg.T_g)

    # Ground reflects diffuse sky terms; direct-solar reflected term on
    # the background is deferred per the docstring above.
    diffuse = _diffuse_sky_term(rho_g, atm)
    # Keep the direct-solar reflected component for coherence with T3 —
    # the ground *is* a Kirchhoff surface and matrix §6.1 includes direct
    # beam on the target arm.  Including it on the background matches the
    # "ground treated as a T3 at h=0" view.
    direct = _direct_solar_term(rho_g, atm, cos_ts)

    return np.asarray(
        (L_self + direct + diffuse) * atm.tau_full_up + atm.L_path_full,
        dtype=np.float64,
    )


__all__ = [
    "AssemblyComponents",
    "assemble_background_at_aperture",
    "assemble_target_at_aperture",
    "validate_no_atmosphere_subcase",
]
