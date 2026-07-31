r"""Resolve the scene's Fried parameter: direct input vs $C_n^2$-profile path.

One computation, one module (Rule 19): the *policy* that decides which
$r_0$ the chain uses.  The profiles live in
:mod:`radiant.atmosphere.cn2_hufnagel_valley` /
:mod:`radiant.atmosphere.cn2_tabulated`, the path integral in
:mod:`radiant.atmosphere.r0_path`, and the Kolmogorov MTF in
:mod:`radiant.atmosphere.turbulence`.

The resolution rules (the ADR-0006 provenance pattern, CU-093 agreement check)
-----------------------------------------------------------------------------
1. ``atmosphere.cn2_profile = "direct"`` (the schema default) — ``r0_m`` is
   used exactly as supplied, including ``0.0`` meaning "turbulence off".  This
   is the **pre-Gap-110 path, bit-identical**; no geometry is consulted and no
   integral is computed.
2. A profile is selected and ``atmosphere.r0_m`` is left at its default —
   $r_0$ comes from the path integral.
3. A profile is selected **and** ``r0_m`` is explicitly user-set — the
   explicit input **wins** (an entered number is never silently replaced), and
   the profile becomes a cross-check: a disagreement of more than 1 % raises
   :class:`~radiant.atmosphere.errors.TurbulenceSpecificationError`.  This is
   the CU-093 redundant-entry pattern: two live inputs for one canonical
   quantity must describe one scene.
4. A profile is selected and ``r0_m`` is explicitly set to ``0`` — a
   contradiction ("compute the turbulence" and "there is no turbulence"), so
   it raises rather than silently picking one (Rule 17).

Site elevation (CU-262)
-----------------------
On the profile path the resolver also reads ``geometry.site_elevation_m`` — the
terrain elevation beneath the line of sight — and hands it to the
Hufnagel-Valley profile, whose **surface term only** is then referenced to the
ground rather than to mean sea level.  The default 0 leaves every profile
evaluation bit-identical to the pre-CU-262 one.  HV is the *only* consumer, so
a non-zero elevation set against ``"direct"`` or ``"tabulated"`` changes
nothing — correct, but reported rather than silent (CU-302, Rule 17): the
elevation is read before the ``"direct"`` short-circuit purely so
``cn2_profiles.warn_if_site_elevation_inert`` covers that branch too.

Reference wavelength
--------------------
$r_0 \propto \lambda^{6/5}$, so a Fried parameter is meaningless without the
wavelength it is quoted at.  The profile-driven value is computed at the
**band-centre wavelength of the scene's spectral grid**,
``wavelength_um[len // 2]`` — exactly the wavelength ``OpticsStage`` uses for
its monochromatic PSF reference, so the number that reaches
``platform/turbulence_kernel.py`` and ``performance/turbulence_mtf_term.py``
is quoted at the wavelength those consumers apply it at.  The chosen value is
published on the result for inspectability.  A user who needs $r_0$ at some
other wavelength uses the ``"direct"`` path.
"""

from __future__ import annotations

import math
import warnings
from dataclasses import dataclass

import numpy as np
import numpy.typing as npt

from radiant.atmosphere.cn2_profiles import (
    CN2_PROFILE_DIRECT,
    Cn2Profile,
    resolve_cn2_profile,
    warn_if_site_elevation_inert,
)
from radiant.atmosphere.errors import TurbulenceSpecificationError
from radiant.atmosphere.r0_path import PathFriedParameter, path_fried_parameter_from_los
from radiant.core.los_geometry import LineOfSightGeometry
from radiant.core.parameters import ParameterSet, Provenance

__all__ = ["FriedParameterResolution", "resolve_fried_parameter"]

#: Relative agreement tolerance for the redundant-entry check (CU-093 uses the
#: same 1 % as ADR-0006 rule 2).
_AGREEMENT_REL_TOL: float = 0.01


@dataclass(frozen=True)
class FriedParameterResolution:
    """The scene's resolved Fried parameter and how it was obtained.

    Parameters
    ----------
    r0_m:
        Fried coherence diameter [m].  ``0.0`` means "turbulence off" — the
        MTF term is then omitted entirely rather than set to unity
        (RADIANT_Atmosphere.md §8 item 5).
    mode:
        ``"off"``, ``"direct"`` (user ``r0_m``) or ``"profile"``
        (path-integrated).
    profile_name:
        The ``atmosphere.cn2_profile`` selector value.
    reference_wavelength_um:
        Wavelength ``r0_m`` is quoted at [µm].  ``0.0`` when turbulence is off.
    path:
        The full :class:`~radiant.atmosphere.r0_path.PathFriedParameter` when
        a profile was evaluated (even if rule 3 gave the direct value the last
        word), else ``None``.
    detail:
        Human-readable one-liner for provenance and log messages.
    """

    r0_m: float
    mode: str
    profile_name: str
    reference_wavelength_um: float
    path: PathFriedParameter | None
    detail: str


def resolve_fried_parameter(
    params: ParameterSet,
    los: LineOfSightGeometry | None,
    wavelength_um: npt.NDArray[np.float64],
    tabulated_profile: Cn2Profile | None = None,
) -> FriedParameterResolution:
    """Resolve the scene's Fried parameter per the rules in the module docstring.

    Parameters
    ----------
    params:
        Resolved parameter set.  A partial-chain fixture that never
        registered the atmosphere turbulence schema is treated as
        "turbulence off", the pre-Gap-110 behaviour.
    los:
        Scene line of sight; required only on the profile path.
    wavelength_um:
        The chain's spectral grid [µm]; its band centre is the reference
        wavelength.
    tabulated_profile:
        Pre-built profile injected at
        ``stage_outputs["atmosphere_config"]["cn2_profile"]`` (Rule 6).
    """
    try:
        r0_direct: float = float(params.get("atmosphere.r0_m"))
        r0_is_user_set = params.get_resolved("atmosphere.r0_m").provenance is not Provenance.DEFAULT
    except (KeyError, TypeError):
        r0_direct, r0_is_user_set = 0.0, False

    try:
        profile_name: str = str(params.get("atmosphere.cn2_profile"))
    except (KeyError, TypeError):
        profile_name = CN2_PROFILE_DIRECT

    # CU-228: the wavelength the user's r₀ is quoted at. Only the direct path uses
    # it — a Cn² profile derives r₀ at the band centre already, so there is nothing
    # to rescale.
    try:
        r0_reference_um: float = float(params.get("atmosphere.r0_reference_wavelength_um"))
    except (KeyError, TypeError):
        r0_reference_um = 0.0

    # CU-262: the terrain the surface boundary layer sits on. A partial-chain
    # fixture that never registered the geometry schema falls back to sea
    # level — the pre-CU-262 behaviour, bit-identical.  Read before the
    # "direct" short-circuit so CU-302's inert-input warning covers that branch
    # too: only 'hufnagel_valley' consumes the elevation, and a user who set it
    # against any other profile must be told it changed nothing (Rule 17).
    try:
        site_elevation_m: float = float(params.get("geometry.site_elevation_m"))
    except (KeyError, TypeError):
        site_elevation_m = 0.0
    warn_if_site_elevation_inert(profile_name, site_elevation_m)

    if profile_name == CN2_PROFILE_DIRECT:
        return _direct_resolution(r0_direct, profile_name, wavelength_um, r0_reference_um)

    if r0_is_user_set and r0_direct == 0.0:
        raise TurbulenceSpecificationError(
            what=(
                f"atmosphere.cn2_profile = {profile_name!r} selects a Cn²-profile-driven "
                "Fried parameter, but atmosphere.r0_m is explicitly set to 0 "
                "(turbulence off)"
            ),
            why=(
                "The two inputs contradict each other: one asks RADIANT to integrate a "
                "turbulence profile along the path, the other asserts there is no "
                "turbulence. RADIANT cannot know which describes the intended scene."
            ),
            action=(
                "Leave atmosphere.r0_m unset to use the profile, or set "
                "atmosphere.cn2_profile = 'direct' to turn turbulence off."
            ),
            context={"cn2_profile": profile_name, "r0_m": r0_direct},
        )

    if los is None:
        raise TurbulenceSpecificationError(
            what=(
                f"atmosphere.cn2_profile = {profile_name!r} needs the scene line of "
                "sight, but no LineOfSightGeometry was published upstream"
            ),
            why=(
                "The profile-driven Fried parameter is a path integral: it needs the "
                "two endpoint altitudes and the lower-endpoint zenith. Without a LOS "
                "there is no path."
            ),
            action=(
                "Run GeometryStage and SourceStage before AtmosphereStage, or set "
                "atmosphere.cn2_profile = 'direct' and supply atmosphere.r0_m."
            ),
            context={"cn2_profile": profile_name},
        )

    profile = resolve_cn2_profile(
        profile_name,
        hv_wind_rms_m_s=float(params.get("atmosphere.cn2_hv_wind_rms_m_s")),
        hv_ground_strength_m23=float(params.get("atmosphere.cn2_hv_ground_strength")),
        hv_site_elevation_m=site_elevation_m,
        tabulated=tabulated_profile,
    )
    if profile is None:  # pragma: no cover — only "direct" returns None
        return _direct_resolution(r0_direct, profile_name, wavelength_um, r0_reference_um)

    wave_type: str = str(params.get("atmosphere.turbulence_wave_type"))
    lam_um = _band_centre_um(wavelength_um)
    path = path_fried_parameter_from_los(los, profile, lam_um * 1e-6, wave_type)

    if r0_is_user_set:
        if not _agree(path.r0_m, r0_direct):
            raise TurbulenceSpecificationError(
                what=(
                    "Over-specified turbulence: atmosphere.r0_m = "
                    f"{r0_direct:.6g} m but atmosphere.cn2_profile = "
                    f"{profile_name!r} integrates to r₀ = {path.r0_m:.6g} m at "
                    f"{lam_um:.4g} µm — a "
                    f"{100.0 * abs(path.r0_m - r0_direct) / max(path.r0_m, r0_direct):.1f} % "
                    "disagreement"
                ),
                why=(
                    "Two inputs were set for one canonical quantity and they disagree "
                    "by more than 1 % (the CU-093 redundant-entry pattern). RADIANT "
                    "cannot know which describes the intended scene: the MTF product "
                    "and the PSF kernel would both use one of them, silently."
                ),
                action=(
                    "Set exactly one — leave atmosphere.r0_m unset to use the profile, "
                    "or set atmosphere.cn2_profile = 'direct' to use the entered r₀ — "
                    "or reconcile the profile parameters (Cn² strength, wave type, "
                    "geometry) with the entered value."
                ),
                context={
                    "r0_m_user": r0_direct,
                    "r0_m_profile": path.r0_m,
                    "cn2_profile": profile_name,
                    "wave_type": wave_type,
                    "reference_wavelength_um": lam_um,
                    "cn2_path_integral_m13": path.cn2_path_integral_m13,
                },
            )
        # Agreeing: the explicitly entered number wins, bit-identical to the
        # pre-Gap-110 result; the profile stays attached as a cross-check.
        return FriedParameterResolution(
            r0_m=r0_direct,
            mode="direct",
            profile_name=profile_name,
            reference_wavelength_um=lam_um,
            path=path,
            detail=(
                f"r₀ = {r0_direct:.6g} m from atmosphere.r0_m (explicit input wins); "
                f"cross-checked against {path.detail}"
            ),
        )

    if path.negligible:
        return FriedParameterResolution(
            r0_m=0.0,
            mode="off",
            profile_name=profile_name,
            reference_wavelength_um=lam_um,
            path=path,
            detail=(
                "turbulence omitted: the path carries negligible Cn² "
                f"(r₀ saturated at {path.r0_m:g} m) — {path.detail}"
            ),
        )

    return FriedParameterResolution(
        r0_m=path.r0_m,
        mode="profile",
        profile_name=profile_name,
        reference_wavelength_um=lam_um,
        path=path,
        detail=path.detail,
    )


#: Kolmogorov wavelength scaling exponent: r₀ ∝ λ^(6/5).
_R0_WAVELENGTH_EXPONENT: float = 6.0 / 5.0

#: The wavelength seeing is habitually quoted at [µm]. Used only to decide whether
#: an un-referenced r₀ looks like a mis-entered visible seeing value (CU-228).
_HABITUAL_SEEING_WAVELENGTH_UM: float = 0.5

#: How far the band centre must sit from 0.5 µm before an un-referenced r₀ is
#: suspicious. A factor of two is well clear of any VIS/NIR band, so the warning
#: cannot fire for a scene that really is working near the habitual wavelength.
_REFERENCE_SUSPICION_FACTOR: float = 2.0


def _rescale_r0_to_band(
    r0_direct: float,
    reference_wavelength_um: float,
    band_centre_um: float,
) -> tuple[float, str]:
    """Scale an r₀ quoted at *reference_wavelength_um* to the band centre (CU-228).

    Kolmogorov turbulence gives ``r₀ ∝ λ^(6/5)``, so a value measured at one
    wavelength is simply wrong at another — the astronomer's habitual 0.5 µm
    seeing of 10 cm corresponds to 1.2 m at 4 µm, a factor of twelve in the
    turbulence MTF. Returns ``(r0_at_band, provenance_detail)``.

    With *reference_wavelength_um* = 0 the user has declared nothing, and the
    value passes through untouched — the pre-CU-228 behaviour, bit-identical.
    """
    if reference_wavelength_um <= 0.0:
        return r0_direct, ""
    scaled = r0_direct * (band_centre_um / reference_wavelength_um) ** _R0_WAVELENGTH_EXPONENT
    return scaled, (
        f"; rescaled from {r0_direct:.6g} m at {reference_wavelength_um:.4g} µm "
        f"to {scaled:.6g} m at the {band_centre_um:.4g} µm band centre "
        f"(r₀ ∝ λ^{_R0_WAVELENGTH_EXPONENT:.1f})"
    )


def _warn_if_reference_wavelength_is_missing(
    reference_wavelength_um: float,
    band_centre_um: float,
) -> None:
    """Flag an un-referenced r₀ used far from the habitual seeing wavelength (CU-228)."""
    if reference_wavelength_um > 0.0:
        return
    ratio = band_centre_um / _HABITUAL_SEEING_WAVELENGTH_UM
    if 1.0 / _REFERENCE_SUSPICION_FACTOR <= ratio <= _REFERENCE_SUSPICION_FACTOR:
        return
    implied = (
        _HABITUAL_SEEING_WAVELENGTH_UM,
        ratio**_R0_WAVELENGTH_EXPONENT,
    )
    warnings.warn(
        f"atmosphere.r0_m is being applied at the {band_centre_um:.4g} µm band centre, "
        f"but atmosphere.r0_reference_wavelength_um is unset so the entered value is "
        f"taken as already being at that wavelength. Seeing is habitually quoted at "
        f"{implied[0]:.1f} µm; if that is what you entered, the correct r₀ here is "
        f"{implied[1]:.3g}x larger (r₀ ∝ λ^{_R0_WAVELENGTH_EXPONENT:.1f}) and the "
        f"turbulence MTF is currently that much too aggressive. Set "
        f"atmosphere.r0_reference_wavelength_um to the wavelength your r₀ is quoted "
        f"at, or leave it unset if the value is already at the operating wavelength.",
        UserWarning,
        stacklevel=3,
    )


def _direct_resolution(
    r0_direct: float,
    profile_name: str,
    wavelength_um: npt.NDArray[np.float64],
    reference_wavelength_um: float = 0.0,
) -> FriedParameterResolution:
    """The pre-Gap-110 path: ``atmosphere.r0_m``, rescaled to the band if referenced."""
    on = r0_direct > 0.0
    if not on:
        return FriedParameterResolution(
            r0_m=r0_direct,
            mode="off",
            profile_name=profile_name,
            reference_wavelength_um=0.0,
            path=None,
            detail="turbulence off (atmosphere.r0_m = 0)",
        )
    band_centre = _band_centre_um(wavelength_um)
    _warn_if_reference_wavelength_is_missing(reference_wavelength_um, band_centre)
    r0_at_band, rescale_note = _rescale_r0_to_band(r0_direct, reference_wavelength_um, band_centre)
    return FriedParameterResolution(
        r0_m=r0_at_band,
        mode="direct",
        profile_name=profile_name,
        reference_wavelength_um=band_centre,
        path=None,
        detail=f"r₀ = {r0_at_band:.6g} m from atmosphere.r0_m (direct input){rescale_note}",
    )


def _band_centre_um(wavelength_um: npt.NDArray[np.float64]) -> float:
    """Band-centre wavelength [µm] — the OpticsStage monochromatic reference."""
    grid = np.asarray(wavelength_um, dtype=np.float64)
    if grid.size == 0:
        raise TurbulenceSpecificationError(
            what="resolve_fried_parameter: the spectral wavelength grid is empty",
            why="The Fried parameter is wavelength-dependent (r₀ ∝ λ^(6/5)); with no "
            "grid there is no wavelength to quote it at.",
            action="Run the chain with a non-empty spectral grid.",
            context={"n_wavelengths": 0},
        )
    return float(grid[grid.size // 2])


def _agree(a: float, b: float) -> bool:
    """1 % relative agreement (ADR-0006 rule 2 / CU-093)."""
    return math.isclose(a, b, rel_tol=_AGREEMENT_REL_TOL, abs_tol=0.0)
