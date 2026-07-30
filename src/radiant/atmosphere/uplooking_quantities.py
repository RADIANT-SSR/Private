"""Segment-composed atmospheric quantities for an up-looking / level LOS.

One computation, one module (Rule 19): compose the ADR-0011 path segments of
an up-looking or level scene into the products the §6.1 assembly equation
consumes.

Guardrail G1 in one paragraph
-----------------------------
No new field is added to
:class:`~radiant.atmosphere._quantities.AtmosphericQuantities`.  The eight-field
contract stays exactly as it is; what changes is *which segment* fills the two
observer-leg slots.  For a down-looking scene ``tau_up`` / ``L_path_up`` carry
the column above the target; for an up-looking or level scene they carry the
segment-composed observer leg (target → sensor, evaluated from the sensor side
because the sensor is the lower endpoint).  The one genuinely new product —
the sky radiance along the LOS continuation — is **not** bolted onto the
bundle; it rides alongside on :class:`UplookingProducts` and is consumed only
by the ``SkyBackground`` assembly arm.

The composition
---------------
::

    observer leg  = segment(target ↔ sensor)      → tau_obs, L_obs→sensor
    illumination  = target-side products, reused  → tau_sun, E_TOA, E_sky_*
    sky (up)      = segment(sensor → space)       → L_sky,aperture
    sky (level)   = arm + tau_arm · segment(target → space)

    L_target,aperture = [ ε·B(T_t)
                        + ρ·τ_sun·E_TOA·cos θ_s / π
                        + ρ·(E_sky_scattered + E_sky_thermal) / π ] · tau_obs
                        + L_obs→sensor
    L_bg,aperture     = L_sky,aperture

The **sky** row is the one that changed with CU-254, and it lands at the
aperture rather than at the target plane.  On the up-looking branch it is one
segment: splitting it at the target — ``L_sky(target→top)·tau_obs + L_obs`` —
is exact radiative transfer but is *not* exact for this segment model, whose
per-segment single-effective-temperature graybody is not additive across the
split, and the measured consequence was a background that moved with the
target's position along a fixed ray.  On the level branch it stays a
composition, because a level ray is tangent at the chord midpoint and a
single sensor-rooted arc would drop the constant-altitude arm entirely.  Both
cases, with their measurements, are in :func:`_sky_radiance_at_aperture`.

The target equation is the *unmodified* §6.1 equation with the observer leg
swapped — which is the whole point of ADR-0011 decision 3: the illumination
leg does not care which way the observer is.  Consequently
:func:`radiant.atmosphere.assembly.assemble_target_at_aperture` is reused
verbatim, not forked, and every T-code (T1/T2/T3/T6/T7) works up-looking on
its first day with no new arms.

``tau_full_up``/``L_path_full`` are still set to the observer leg here, but
since CU-254 the ``SkyBackground`` arm no longer reads them: the sky arrives
already at the aperture, so that arm is a pass-through (``τ ≡ 1``,
``L_path ≡ 0``).  The two fields keep the observer leg because
``SpectralIntegrationStage``'s sub-pixel decomposition subtracts
``L_path_full`` from the at-aperture background to recover the pure-background
term, and the observer-leg path radiance is exactly what has to come out
there.  An explicit ``GroundBackground`` on such a scene is refused upstream
(there is no ground behind an up-looking target), so the ground reading of
those two fields is never exercised.

Illumination reuse
------------------
``tau_sun``, ``E_TOA``, ``E_sky_scattered`` and ``E_sky_thermal`` describe the
*target's* radiative environment: the solar column above it and the sky
hemisphere over it.  None of them depends on where the observer is.  They are
therefore obtained by evaluating the backend at a **proxy down-looking
geometry** with the same ``h_tgt`` and the same solar angles, a sensor placed
at ``h_atm_top`` and ``θ_o = 0``.  With the proxy sensor at the top of the
column, ``SimpleAtmosphere``'s ``E_sky_scattered`` slab (``1 − τ_down,vert``
over ``h_tgt → h_sensor``) coincides exactly with the ``E_sky_thermal`` slab
(``h_tgt → h_atm_top``, CU-155) — i.e. the proxy makes both diffuse components
"the sky above the target", which is what an up-looking scene means by them.
The proxy is a *whole-backend* call, so this reuse is model-agnostic in form.

Per-altitude illumination (GF-9 / decision 21)
----------------------------------------------
``θ_s > π/2`` is legal since Phase 2.  Three cases:

* **target in shadow** — ``solar_shadow.sunlit`` is ``False``: there is no
  direct beam, so ``tau_sun`` is set to **0** rather than to some column
  value.  The scattered-sky component is already identically zero there (the
  backend's ``cos θ_s ≤ 0`` guard), and the thermal sky is untouched.
* **target sunlit below the terminator** — ``tau_sun`` is the two-arm tangent
  transit of :mod:`radiant.atmosphere.solar_transit` (provisional; see that
  module for the fragility statement).
* **sun above the horizontal** (``θ_s ≤ π/2``) — the backend's own
  ``tau_sun``, untouched.

Note on the direct-solar *term*: RADIANT models the target as a horizontal
Lambertian facet, so assembly multiplies by ``cos θ_s`` clamped at zero
(``assembly._cos_theta_s``).  For any ``θ_s > π/2`` that factor is zero and
the direct-solar contribution vanishes regardless of ``tau_sun`` — the beam
arrives from below the facet.  ``tau_sun`` is still published correctly
because it is an inspectable physical quantity (Rule 16) and because a
non-horizontal target model would consume it; the facet convention, not this
module, is what zeroes the term.

Zero drift
----------
Every entry point here refuses a down-looking LOS.  Nothing in this module is
imported by a pre-existing evaluate path.
"""

from __future__ import annotations

import dataclasses
import logging
import math
from dataclasses import dataclass
from typing import Any

import numpy as np

from radiant.atmosphere._quantities import AtmosphericQuantities
from radiant.atmosphere.level_arm import evaluate_level_arm
from radiant.atmosphere.observer_leg import ObserverLeg, observer_leg_from_los
from radiant.atmosphere.protocol import SPHERICAL_SWITCH_RAD
from radiant.atmosphere.segment_grazing import evaluate_grazing_segment
from radiant.atmosphere.segment_simple import evaluate_column_segment
from radiant.atmosphere.segments import ColumnSegmentSpec, LevelArmSpec, SegmentQuantities
from radiant.atmosphere.simple import SimpleAtmosphere
from radiant.atmosphere.sky_radiance import (
    sky_radiance_along_los,
    warn_if_scattered_sky_provisional,
)
from radiant.atmosphere.solar_shadow import sunlit
from radiant.atmosphere.solar_transit import twilight_solar_transmittance
from radiant.core.constants import R_EARTH_M
from radiant.core.los_geometry import LineOfSightGeometry
from radiant.core.los_termination import LosTermination, classify_los_termination
from radiant.core.parameters import ParameterBoundsError, ParameterSet
from radiant.core.solar import toa_solar_spectral_irradiance

logger = logging.getLogger(__name__)

__all__ = ["UplookingProducts", "evaluate_uplooking_topology", "supports_uplooking"]


@dataclass(frozen=True)
class UplookingProducts:
    """Segment-composed products for one up-looking / level scene.

    Parameters
    ----------
    quantities:
        The eight-field :class:`AtmosphericQuantities` bundle with the
        observer-leg segment in the ``*_up`` / ``*_full`` slots (see the
        module docstring).  Unchanged contract, different segment.
    sky_radiance_at_aperture:
        Sky radiance along the whole LOS, evaluated **from the sensor** and
        travelling toward it [W/m²/sr/µm] — what the aperture would see if the
        target were not there.  This is the ``SkyBackground`` arm's answer
        directly: it is already at the aperture, so assembly does **not**
        propagate it (CU-254; renamed from ``sky_source_radiance``, which named
        a target-plane quantity).
    provenance:
        Inputs and intermediates (Rule 16 inspectability).  Never consumed
        by physics.
    """

    quantities: AtmosphericQuantities
    sky_radiance_at_aperture: np.ndarray
    provenance: dict[str, Any]


def supports_uplooking(model: object) -> bool:
    """Does *model* implement the direction-aware (up/level) segment products?

    The Phase-2 segment evaluators are built on the CU-161-calibrated
    :class:`~radiant.atmosphere.simple.SimpleAtmosphere` species model, so the
    simple backend is the one that serves up-looking and level paths at first
    delivery.  MODTRAN tape7-import and the interpolated library arrive
    separately (their up-looking / ITYPE=1 families are owner-run batches).
    """
    return isinstance(model, SimpleAtmosphere)


def evaluate_uplooking_topology(
    model: object,
    wavelength_um: np.ndarray,
    los: LineOfSightGeometry,
    params: ParameterSet,
) -> UplookingProducts:
    """Compose the up-looking / level products for *los*.

    Raises
    ------
    ParameterBoundsError
        If *los* is down-looking, if the backend cannot serve the topology,
        or if the LOS continuation is a limb-crossing column (B4, declined
        for v1.x — ADR-0011 decision 5).
    """
    if not supports_uplooking(model):
        raise ParameterBoundsError(
            what=(
                f"AtmosphereStage: atmosphere model {type(model).__name__} cannot serve "
                f"an up-looking/level path (h_sensor = {los.h_sensor} m, h_tgt = "
                f"{los.h_tgt} m, theta_o = {los.theta_o} rad)"
            ),
            why=(
                "The direction-aware path-segment products (up-path column, "
                "constant-altitude arm, sky radiance along the LOS) are built on the "
                "CU-161-calibrated simple-model species machinery.  What IS supported "
                "up-looking today: (a) atmosphere.model='simple' for any endo path, "
                "and (b) any backend for a wholly-vacuum path with both endpoints at "
                "or above h_atm_top (the LEO→GEO case).  MODTRAN tape7-import and the "
                "interpolated library need their own up-looking / ITYPE=1 run "
                "families, which are owner-run batches (plan §4 Phase 2, GF-10)."
            ),
            action=(
                "Set atmosphere.model='simple' for this scene, raise both endpoints "
                "above h_atm_top for a vacuum path, or use a down-looking geometry "
                "with the current backend."
            ),
            context={
                "model": type(model).__name__,
                "h_sensor": los.h_sensor,
                "h_tgt": los.h_tgt,
                "theta_o": los.theta_o,
                "los_direction": los.los_direction,
            },
        )
    atmosphere: SimpleAtmosphere = model  # narrowed by supports_uplooking

    lam = np.asarray(wavelength_um, dtype=np.float64)
    h_atm_top = float(los.h_atm_top)
    theta_s = los.theta_s

    # ---------------------------------------------------------------
    # 1. Observer leg — the target ↔ sensor segment.
    # ---------------------------------------------------------------
    leg = observer_leg_from_los(los)
    segment = _evaluate_observer_segment(
        atmosphere, lam, leg.spec, leg.delta_phi_seg_rad, theta_s, h_atm_top
    )
    tau_obs = np.asarray(segment.tau, dtype=np.float64)
    L_obs = np.asarray(segment.radiance_toward(leg.toward_sensor), dtype=np.float64)

    # ---------------------------------------------------------------
    # 2. Illumination leg — reused target-side products (proxy evaluation).
    # ---------------------------------------------------------------
    illum = _illumination_products(atmosphere, lam, los, params)
    tau_sun, solar_note = _resolve_tau_sun(atmosphere, lam, los, illum.tau_sun, h_atm_top)

    # ---------------------------------------------------------------
    # 3. The sky the sensor sees behind the target — one whole-path
    #    evaluation rooted at the sensor, already at the aperture (CU-254).
    # ---------------------------------------------------------------
    sky, sky_note = _sky_radiance_at_aperture(
        atmosphere, lam, los, leg, segment, theta_s, h_atm_top
    )

    provenance: dict[str, Any] = {
        "topology": los.los_direction,
        "observer_leg": leg.detail,
        "observer_segment_provenance": segment.provenance,
        "illumination_proxy": "backend evaluated at (h_sensor = h_atm_top, theta_o = 0)",
        "solar_leg": solar_note,
        "sky_continuation": sky_note,
        "h_sensor_m": los.h_sensor,
        "h_tgt_m": los.h_tgt,
        "theta_o_rad": los.theta_o,
        "theta_s_rad": theta_s,
        "delta_phi_rad": los.delta_phi,
    }
    logger.info(
        "AtmosphereStage: %s path served by segment composition — %s; %s; %s",
        los.los_direction,
        leg.detail,
        solar_note,
        sky_note,
    )

    quantities = AtmosphericQuantities(
        wavelength_um=lam,
        tau_sun=tau_sun,
        tau_up=tau_obs,
        # The LOS terminates on space, so the background source plane is the
        # target plane: the "full" column IS the observer leg (see module
        # docstring).  Copies keep the arrays independent objects, matching
        # the convention SimpleAtmosphere.evaluate uses for h_tgt == 0.
        tau_full_up=tau_obs.copy(),
        E_TOA=illum.E_TOA,
        E_sky_scattered=illum.E_sky_scattered,
        E_sky_thermal=illum.E_sky_thermal,
        L_path_up=L_obs,
        L_path_full=L_obs.copy(),
    )
    return UplookingProducts(
        quantities=quantities,
        sky_radiance_at_aperture=sky,
        provenance=provenance,
    )


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------


def _evaluate_observer_segment(
    atmosphere: SimpleAtmosphere,
    lam: np.ndarray,
    spec: ColumnSegmentSpec | LevelArmSpec,
    delta_phi_seg_rad: float,
    theta_s_rad: float | None,
    h_atm_top_m: float,
) -> SegmentQuantities:
    """Dispatch the observer-leg segment to its evaluator (Rule 19 split)."""
    if isinstance(spec, LevelArmSpec):
        return evaluate_level_arm(
            atmosphere,
            lam,
            spec,
            theta_s_rad=theta_s_rad,
            delta_phi_rad=delta_phi_seg_rad,
            h_atm_top_m=h_atm_top_m,
        )
    return evaluate_column_segment(
        atmosphere,
        lam,
        spec,
        theta_s_rad=theta_s_rad,
        delta_phi_rad=delta_phi_seg_rad,
        h_atm_top_m=h_atm_top_m,
    )


def _illumination_products(
    atmosphere: SimpleAtmosphere,
    lam: np.ndarray,
    los: LineOfSightGeometry,
    params: ParameterSet,
) -> AtmosphericQuantities:
    """Target-side illumination bundle from a proxy down-looking evaluation.

    Only ``tau_sun``, ``E_TOA``, ``E_sky_scattered`` and ``E_sky_thermal`` of
    the returned bundle are consumed; the observer-leg fields belong to the
    proxy geometry and are discarded by the caller.

    An **exo-altitude target** (``h_tgt ≥ h_atm_top`` — the ground-to-space
    SST and air-to-space classes) has no column above it at all, so the proxy
    would be degenerate.  Its illumination is the exact vacuum identity
    instead: ``τ_sun ≡ 1``, ``E_sky ≡ 0``, ``E_TOA`` the unattenuated core
    solar spectrum — the same identities
    :class:`~radiant.atmosphere.exo.ExoAtmosphere` publishes, and the same
    ones the down-looking exo branch of :mod:`radiant.atmosphere.topology`
    uses.  Earth occultation of the sun is applied afterwards by
    :func:`_resolve_tau_sun`.
    """
    lam64 = np.asarray(lam, dtype=np.float64)
    if los.h_tgt >= los.h_atm_top:
        zeros = np.zeros_like(lam64)
        ones = np.ones_like(lam64)
        return AtmosphericQuantities(
            wavelength_um=lam64,
            tau_sun=ones,
            tau_up=ones.copy(),
            tau_full_up=ones.copy(),
            E_TOA=np.asarray(toa_solar_spectral_irradiance(lam64), dtype=np.float64),
            E_sky_scattered=zeros,
            E_sky_thermal=zeros.copy(),
            L_path_up=zeros.copy(),
            L_path_full=zeros.copy(),
        )
    proxy = dataclasses.replace(los, h_sensor=los.h_atm_top, theta_o=0.0)
    return atmosphere.evaluate(lam64, proxy, params)


def _resolve_tau_sun(
    atmosphere: SimpleAtmosphere,
    lam: np.ndarray,
    los: LineOfSightGeometry,
    tau_sun_backend: np.ndarray,
    h_atm_top_m: float,
) -> tuple[np.ndarray, str]:
    """Apply the GF-9 per-altitude illumination test to the solar leg."""
    theta_s = los.theta_s
    if theta_s is None or theta_s <= math.pi / 2.0:
        return (
            np.asarray(tau_sun_backend, dtype=np.float64),
            "sun above the target's horizontal — backend solar column unchanged",
        )
    h_tgt = float(los.h_tgt)
    if not sunlit(h_tgt, theta_s):
        return (
            np.zeros_like(lam),
            (
                f"target at {h_tgt:.0f} m is inside the Earth's shadow at "
                f"theta_s = {math.degrees(theta_s):.3f}° — no direct beam "
                "(tau_sun set to 0)"
            ),
        )
    if h_tgt >= h_atm_top_m:
        return (
            np.ones_like(lam),
            (
                f"target at {h_tgt:.0f} m is above the modelled column and sunlit at "
                f"theta_s = {math.degrees(theta_s):.3f}° — vacuum solar leg "
                "(tau_sun = 1)"
            ),
        )
    tau = twilight_solar_transmittance(atmosphere, lam, h_tgt, theta_s, h_atm_top_m=h_atm_top_m)
    return (
        tau,
        (
            f"sunlit twilight target at {h_tgt:.0f} m, theta_s = "
            f"{math.degrees(theta_s):.3f}° — two-arm tangent transit "
            "(PROVISIONAL: no MODTRAN twilight anchor in batch 1)"
        ),
    )


def _sky_radiance_at_aperture(
    atmosphere: SimpleAtmosphere,
    lam: np.ndarray,
    los: LineOfSightGeometry,
    leg: ObserverLeg,
    segment: SegmentQuantities,
    theta_s_rad: float | None,
    h_atm_top_m: float,
) -> tuple[np.ndarray, str]:
    """Sky radiance reaching the **aperture** along the pointing direction.

    This is the radiance the sensor would measure if the target were not
    there: everything the LOS runs through from the *sensor* out to
    ``h_atm_top``, with cold space behind it.  It is therefore already an
    at-aperture quantity, and the ``SkyBackground`` assembly arm consumes it
    directly (``τ ≡ 1``, ``L_path ≡ 0`` for that arm) rather than propagating
    it.

    One whole-path evaluation — up-looking (CU-254)
    -----------------------------------------------
    An up-looking LOS leaves the sensor at ``ζ_low = π − η < π/2`` and
    ascends monotonically, so the whole path *is* one column segment keyed to
    the sensor.  Until 2026-07-29 this function returned the sky at the **target** plane
    and assembly re-propagated it as ``L_sky(target→top)·τ(sensor→target) +
    L_path(sensor→target)``.  That composition is exact radiative transfer,
    but the segment model it composes is not additive: each segment emits
    ``(1 − τ_seg)·B(T_eff(h_low,seg))`` with its *own* lower-endpoint
    effective temperature, so splitting one column at the target plane
    replaces part of a warm ground-anchored graybody with a cold
    target-anchored one.  The measured consequence was a background that
    depended on where along a fixed ray the target sat — 1.94207e5 e⁻ at a
    10 km target, 2.14046e5 at 20 km, 2.21479e5 for the whole column — a
    12.3 % under-report that always ran the same way (optimistic SCNR).
    Evaluating the whole path once removes the split, and the surviving value
    is the ground-rooted one, which is also the geometry the MODTRAN H-runs
    anchor.

    A second defect fell out with it (CU-260): the old target-rooted form
    returned **exactly zero** whenever ``h_tgt ≥ h_atm_top``, so every
    ground-to-space and air-to-space scene saw a black sky *and* never
    reached the ADR-0011 decision-10 provisional-VIS warning that lives on
    the way there.  Rooted at the sensor there is no such case: the column
    above a ground site exists whatever the target is doing.

    Why the **level** arm still composes
    ------------------------------------
    A level LOS is tangent at the *chord midpoint*, not at the sensor, so the
    sensor sits on the ray's descending half and a single ascending arc rooted
    at the sensor would omit the entire constant-altitude arm.  Measured, in
    sea-level-equivalent molecular column: a sensor-rooted arc recovers 98.6 %
    of the true traversed path for an 8 km arm at ground level, 83.0 % for
    100 km at 3 km, and 75.1 % for 150 km at 10 km.  Nothing in RADIANT
    evaluates "constant-altitude arm then ascending arc" as one segment
    (:class:`~radiant.atmosphere.segments.LevelArmSpec` and
    :mod:`radiant.atmosphere.segment_grazing` are different computations, Rule
    19), so the level branch keeps the two-segment composition
    ``L_arm→sensor + τ_arm · L_continuation(target→top)`` — which is
    geometrically complete, is numerically what the ``SkyBackground`` arm used
    to assemble, and therefore leaves every level scene unmoved.

    The consequence is that the CU-254 non-additivity survives on the level
    branch: slide the target along a fixed level ray and the split point
    moves, so the background moves with it.  It is bounded by the same
    graybody argument and it is recorded rather than papered over — closing it
    needs a segment evaluator that spans both geometries (CU-276).

    Hand-over at 80°, not 89.5° (CU-225 / CU-274)
    ---------------------------------------------
    Two evaluators still serve the two zenith regimes, but the split moved
    from ``ZENITH_CEILING_RAD`` (89.5°) down to
    :data:`~radiant.atmosphere.protocol.SPHERICAL_SWITCH_RAD` (80°) — the
    angle at which the column form's plane-parallel air mass stops being the
    accurate one.  Below it the column product is used; above it the exact
    spherical slant integral (:mod:`radiant.atmosphere.segment_grazing`).

    The hand-over is still a step, not a blend, but it is now a small one.
    Measured band-mean LWIR (8–13 µm) sky from the ground, grazing/column:

    =======  ================
    ζ [deg]  grazing / column
    =======  ================
    0        1.00000
    30       0.99979
    48.2     0.99929  (the MODTRAN H-run anchor zenith)
    60       0.99852
    80       0.99359  ← the hand-over
    85       1.08665
    89.4     1.07785  ← the old hand-over
    =======  ================

    So the discontinuity went from ≈ 8 % (LWIR from the ground; ≈ 28 % on the
    3 km level arm CU-225 measured) to 0.64 %, and the 80–89.5° band is now
    served by the exact integral instead of by an air mass that was 14–62 %
    low there.  The residual 0.64 % is the plane-parallel model's own error at
    80°; closing it entirely would mean using the grazing form at *every*
    zenith, which is deferred because the two evaluators weight their species
    split at different altitudes and that changes the provisional VIS
    scattered sky by up to 10× — a modelling decision, not a formula swap
    (CU-260).
    """
    termination = classify_los_termination(los)
    if termination.terminus == "earth":
        raise ParameterBoundsError(  # pragma: no cover - unreachable for up/level
            what=(
                "uplooking_quantities: the LOS continuation past the target hits the "
                f"Earth ({termination.detail}) on an up-looking/level path"
            ),
            why=(
                "An ascending continuation cannot intercept the Earth; reaching this "
                "branch means the direction classification and the geometry disagree."
            ),
            action="File a bug — this is an internal invariant violation.",
            context={"theta_o": los.theta_o, "h_tgt": los.h_tgt},
        )
    if termination.terminus == "limb":
        raise ParameterBoundsError(  # pragma: no cover - unreachable for up/level
            what=(
                f"uplooking_quantities: the LOS continuation is a limb-crossing column "
                f"({termination.detail})"
            ),
            why=(
                "Earthlimb backgrounds (matrix B4) are declined for v1.x — ADR-0011 "
                "decision 5 guards them rather than approximating them."
            ),
            action="Tilt the geometry so the continuation does not graze the limb.",
            context={
                "tangent_altitude_m": termination.tangent_altitude_m,
                "tangent_depression_m": termination.tangent_depression_m,
            },
        )

    # The sky column's lower→upper direction is sensor → target → space, the
    # horizontal reverse of φ_o (which is measured target → sensor), so the
    # sun's relative azimuth flips by π; the radiance heading back toward the
    # sensor emerges at the lower end of whichever segment produced it.
    delta_phi = 0.0 if los.delta_phi is None else float(los.delta_phi)
    delta_phi_seg = delta_phi - math.pi

    if isinstance(leg.spec, LevelArmSpec):
        return _level_sky_at_aperture(
            atmosphere,
            lam,
            leg,
            segment,
            termination,
            theta_s_rad=theta_s_rad,
            delta_phi_seg_rad=delta_phi_seg,
            h_atm_top_m=h_atm_top_m,
        )

    # Up-looking: one whole column rooted at the sensor.
    h_sensor = leg.spec.h_low_m
    if h_sensor >= h_atm_top_m:
        return (
            np.zeros_like(lam),
            "sensor above h_atm_top — the whole LOS is vacuum, sky radiance ≡ 0",
        )
    # Zenith of the pointing direction **at the sensor** — the lower endpoint
    # of the sky column, exactly the key an ADR-0011 column segment wants.
    return _ascending_sky(
        atmosphere,
        lam,
        h_low_m=h_sensor,
        zeta_low_rad=leg.zeta_low_rad,
        r_tangent_m=(R_EARTH_M + h_sensor) * math.sin(leg.zeta_low_rad),
        origin="the sensor",
        theta_s_rad=theta_s_rad,
        delta_phi_seg_rad=delta_phi_seg,
        h_atm_top_m=h_atm_top_m,
    )


def _level_sky_at_aperture(
    atmosphere: SimpleAtmosphere,
    lam: np.ndarray,
    leg: ObserverLeg,
    segment: SegmentQuantities,
    termination: LosTermination,
    *,
    theta_s_rad: float | None,
    delta_phi_seg_rad: float,
    h_atm_top_m: float,
) -> tuple[np.ndarray, str]:
    """``L_arm→sensor + τ_arm · L_continuation`` for a level LOS.

    The two-segment composition, kept deliberately — see
    :func:`_sky_radiance_at_aperture` for why a sensor-rooted single arc
    cannot express a level path (it drops the constant-altitude arm, up to
    25 % of the traversed column).  Numerically identical to what the
    ``SkyBackground`` assembly arm used to compute for this topology, so no
    level scene moves.
    """
    assert isinstance(leg.spec, LevelArmSpec)  # caller-enforced branch invariant
    # Level: sensor, target and arm all sit at the one altitude, so the
    # continuation starts there too.
    h_arm = leg.spec.altitude_m
    continuation, cont_note = _ascending_sky(
        atmosphere,
        lam,
        h_low_m=h_arm,
        zeta_low_rad=termination.continuation_zeta_rad,
        r_tangent_m=termination.tangent_radius_m,
        origin="the target",
        theta_s_rad=theta_s_rad,
        delta_phi_seg_rad=delta_phi_seg_rad,
        h_atm_top_m=h_atm_top_m,
    )
    tau_arm = np.asarray(segment.tau, dtype=np.float64)
    L_arm = np.asarray(segment.radiance_toward(leg.toward_sensor), dtype=np.float64)
    sky = L_arm + tau_arm * continuation
    note = (
        f"level composition at {h_arm:.0f} m MSL: constant-altitude arm toward "
        f"the sensor + arm transmittance × [{cont_note}]"
    )
    return np.asarray(sky, dtype=np.float64), note


def _ascending_sky(
    atmosphere: SimpleAtmosphere,
    lam: np.ndarray,
    *,
    h_low_m: float,
    zeta_low_rad: float,
    r_tangent_m: float,
    origin: str,
    theta_s_rad: float | None,
    delta_phi_seg_rad: float,
    h_atm_top_m: float,
) -> tuple[np.ndarray, str]:
    """One monotonically-ascending sky segment, toward its lower end.

    Dispatches on :data:`~radiant.atmosphere.protocol.SPHERICAL_SWITCH_RAD`:
    the anchored column product inside the plane-parallel band, the exact
    spherical slant integral outside it.
    """
    if h_low_m >= h_atm_top_m:
        return (
            np.zeros_like(lam),
            f"{origin} is above h_atm_top — this segment is vacuum, sky radiance ≡ 0",
        )

    if zeta_low_rad <= SPHERICAL_SWITCH_RAD:
        sky = sky_radiance_along_los(
            atmosphere,
            lam,
            h_low_m,
            zeta_low_rad,
            theta_s_rad=theta_s_rad,
            delta_phi_rad=delta_phi_seg_rad,
            h_atm_top_m=h_atm_top_m,
        )
        note = (
            f"sky column from {origin} at {h_low_m:.0f} m, zenith "
            f"{math.degrees(zeta_low_rad):.4f}°, to cold space (column machinery)"
        )
        return np.asarray(sky, dtype=np.float64), note

    # Past the plane-parallel band: the exact spherical slant integral.  The
    # band gating that ``sky_radiance_along_los`` applies on the other branch
    # is applied here explicitly — it is a policy about the product, not about
    # which evaluator produced it (CU-260).
    warn_if_scattered_sky_provisional(lam, theta_s_rad)
    grazing = evaluate_grazing_segment(
        atmosphere,
        lam,
        r_tangent_m=r_tangent_m,
        h_low_m=h_low_m,
        h_high_m=h_atm_top_m,
        zeta_low_rad=zeta_low_rad,
        theta_s_rad=theta_s_rad,
        delta_phi_rad=delta_phi_seg_rad,
        h_atm_top_m=h_atm_top_m,
    )
    note = (
        f"near-horizon sky arc from {origin} at {h_low_m:.0f} m, zenith "
        f"{math.degrees(zeta_low_rad):.4f}° (past the "
        f"{math.degrees(SPHERICAL_SWITCH_RAD):.1f}° plane-parallel band — true "
        f"spherical slant integral, line perigee "
        f"{r_tangent_m - R_EARTH_M:.0f} m MSL)"
    )
    return np.asarray(grazing.L_toward_lower, dtype=np.float64), note
