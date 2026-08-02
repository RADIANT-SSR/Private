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

Which backend serves which leg (CU-226)
---------------------------------------
Until 2026-07-30 every leg came from one ``SimpleAtmosphere``.  The shipped
``midlat_summer_uplooking_ladder`` family changes that for the **observer leg
only**: it is a MODTRAN-rendered ground→target downwelling column, which is
exactly the segment :func:`_evaluate_observer_segment` needs and is the term
that dominates a ground-to-air scene.  It is *one leg of data* — one lower
endpoint (the ground), one zenith (vertical), one direction (downwelling) —
and the topology needs two more legs it does not contain:

* the **illumination** leg is the solar column and sky hemisphere *above the
  target*.  No rung of a sensor→target ladder is that column, and it cannot be
  recovered from one: the ladder integrates upward *to* the target, never past
  it.  Evaluating the backend at the down-looking proxy geometry
  :func:`_illumination_products` uses is refused by construction
  (``InterpolatedAtmosphere._require_family_direction``), and rightly — a
  down-looking query would return the upwelling product under a downwelling
  name.
* the **sky-at-aperture** leg is the whole sensor→``h_atm_top`` column.  The
  shipped ladder stops at 20 km; reading its top rung as "the sky" would be
  extrapolation past the hull, which this backend never does.

So a library-backed up-looking scene is a **declared hybrid**: the observer leg
is MODTRAN-interpolated, the illumination and sky legs come from the
``SimpleAtmosphere`` companion the loader attached to the family
(``InterpolatedAtmosphere.uplooking_companion``).  Two atmospheres in one
answer is a real modelling compromise, so it is never silent — a
``UserWarning`` is raised, an INFO record is logged, and
``provenance["backend_split"]`` names which leg came from which model
(Rule 17: no silent substitution; Rule 16: inspectable).  The alternative,
refusing the scene outright, is what CU-226 was filed to remove; the other
alternative, zeroing the legs the family lacks, would be a silently wrong
answer that inflates SNR.

**Owner-ratified 2026-08-01 (CU-224 checklist, ex-CU-305).**  The hybrid stands
as shipped.  It is a modelling judgement, not a mechanical one, so it was put to
the owner with the divergence measured: on the observer leg at 3–5 µm, ground to
10 km, ``tau`` 0.4725 (family) against 0.5715 (companion), −17.3 %; ``L`` 0.5414
against 0.3995 W/m²/sr/µm, +35.5 %; SNR 1152.72 against 1207.21, −4.5 %.  Where
the two models must agree — ``tau_sun``, ``E_TOA``, ``E_sky_scattered``,
``E_sky_thermal``, all served by the companion alone — they are bit-identical.
The ratification is conditional on the compromise staying **declared**: the
``UserWarning``, the INFO record and the ``backend_split`` provenance marker are
part of what was ratified and must not be softened into silence.

Re-audit condition: this arrangement exists only because an up-looking run
family carries one leg of data.  A future family that is self-contained — one
that carries its own solar column and its own sensor→``h_atm_top`` sky, or a
scene whose target is a blackbody, where the illumination terms vanish — makes
the companion unnecessary for that scene, and the split should be dropped there
rather than declared.  Nothing else re-opens it.

Zero drift
----------
Every entry point here refuses a down-looking LOS.  Nothing in this module is
imported by a pre-existing evaluate path.  ``atmosphere.model='simple'``
resolves to ``column=None`` and takes byte-for-byte the pre-CU-226 route.
"""

from __future__ import annotations

import dataclasses
import logging
import math
import warnings
from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

import numpy as np

from radiant.atmosphere._quantities import AtmosphericQuantities
from radiant.atmosphere.errors import COVERAGE_REFUSAL_SURFACE, COVERAGE_SURFACE_KEY
from radiant.atmosphere.level_arm import evaluate_level_arm
from radiant.atmosphere.level_whole_path import evaluate_level_whole_path
from radiant.atmosphere.observer_leg import ObserverLeg, observer_leg_from_los
from radiant.atmosphere.protocol import SPHERICAL_SWITCH_RAD
from radiant.atmosphere.segment_grazing import evaluate_grazing_segment
from radiant.atmosphere.segment_simple import evaluate_column_segment
from radiant.atmosphere.segments import LevelArmSpec
from radiant.atmosphere.simple import SimpleAtmosphere
from radiant.atmosphere.sky_radiance import (
    sky_radiance_along_los,
    warn_if_scattered_sky_provisional,
)
from radiant.atmosphere.solar_shadow import sunlit
from radiant.atmosphere.solar_transit import twilight_solar_transmittance
from radiant.core.constants import R_EARTH_M
from radiant.core.los_geometry import LineOfSightGeometry
from radiant.core.los_termination import classify_los_termination
from radiant.core.parameters import ParameterBoundsError, ParameterSet
from radiant.core.solar import toa_solar_spectral_irradiance

logger = logging.getLogger(__name__)

#: Floating-point slack for the range checks applied to a library column
#: product — the same slop allowance ``SegmentQuantities`` uses, not a physics
#: parameter.
_LIBRARY_TOLERANCE: float = 1e-12

__all__ = [
    "UplookingColumnBackend",
    "UplookingProducts",
    "evaluate_uplooking_topology",
    "supports_uplooking",
]


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


@runtime_checkable
class UplookingColumnBackend(Protocol):
    """A backend that can supply the up-looking **observer-leg column** (CU-226).

    Structural, not nominal: anything exposing an up-looking column product,
    a ``family_direction`` of ``"up"``, and a companion for the legs it does
    not carry qualifies.  Today that is
    :class:`~radiant.atmosphere.interpolated.InterpolatedAtmosphere` built from
    an up-looking run family; the MODTRAN ITYPE=1 wiring (GF-10, CU-224) is the
    next implementer and needs no change here.
    """

    @property
    def family_direction(self) -> str:
        """``"up"`` for a family whose product is the downwelling column."""

    @property
    def uplooking_companion(self) -> object | None:
        """Backend serving the illumination and sky-continuation legs."""

    @property
    def uplooking_target_ceiling_m(self) -> float | None:
        """Highest target altitude the family's own runs measure [m MSL].

        ``None`` when the family records nothing about its upper endpoint.
        :func:`_refuse_library_backed_exo_target` keys the full-column /
        partial-column split on this value — it is the backend's own answer,
        so no caller has to know family names.
        """

    def uplooking_column_product(self, wavelength_um: np.ndarray, los: Any) -> Any:
        """The sensor→target column segment (τ and ``L_toward_lower``)."""


@dataclass(frozen=True)
class _Backends:
    """Which model serves which leg of one up-looking / level evaluation.

    ``column is None`` is the pre-CU-226 arrangement — one ``SimpleAtmosphere``
    serving every leg — and is the only arrangement a ``simple`` scene ever
    takes.
    """

    simple: SimpleAtmosphere
    column: UplookingColumnBackend | None


def _resolve_backends(model: object) -> _Backends | None:
    """Split *model* into (observer-leg backend, companion), or ``None``.

    ``None`` means the model cannot serve an up-looking / level topology at
    all — the caller turns that into the capability error.
    """
    if isinstance(model, SimpleAtmosphere):
        return _Backends(simple=model, column=None)
    if isinstance(model, UplookingColumnBackend) and model.family_direction == "up":
        companion = model.uplooking_companion
        if isinstance(companion, SimpleAtmosphere):
            return _Backends(simple=companion, column=model)
    return None


def supports_uplooking(model: object) -> bool:
    """Does *model* implement the direction-aware (up/level) segment products?

    Two arrangements qualify (CU-226):

    * :class:`~radiant.atmosphere.simple.SimpleAtmosphere` — the
      CU-161-calibrated species machinery serves every leg of every up-looking
      and level topology, at any zenith;
    * an :class:`UplookingColumnBackend` whose family is up-looking and which
      carries a ``SimpleAtmosphere`` companion — the observer leg comes from
      the run family, the illumination and sky legs from the companion.  See
      the module docstring for why that split is the only one the data
      supports, and why it is declared rather than silent.

    MODTRAN tape7-import still does not qualify: its up-looking / ITYPE=1 deck
    geometry is unwritten (GF-10, CU-224), so it has no column product to
    offer.
    """
    return _resolve_backends(model) is not None


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
        if the target is at or above ``h_atm_top`` while the observer leg comes
        from a run family that stops inside the column
        (:func:`_refuse_library_backed_exo_target`), or if the LOS continuation
        is a limb-crossing column (B4, declined for v1.x — ADR-0011 decision 5).
    """
    backends = _resolve_backends(model)
    if backends is None:
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
                "(b) atmosphere.model='interpolated' pointed at an UP-looking run "
                "family (shipped: midlat_summer_uplooking_ladder, "
                "interpolation_axes='target_altitude_m') — its MODTRAN column serves "
                "the observer leg and its simple companion the illumination and sky "
                "legs (CU-226), and (c) any backend for a wholly-vacuum path with "
                "both endpoints at or above h_atm_top (the LEO→GEO case).  MODTRAN "
                "tape7-import still needs its own up-looking / ITYPE=1 deck geometry, "
                "which is an owner-run batch (plan §4 Phase 2, GF-10)."
            ),
            action=(
                "Set atmosphere.model='simple' for this scene, point "
                "atmosphere.interpolated_data_dir at an up-looking run family, raise "
                "both endpoints above h_atm_top for a vacuum path, or use a "
                "down-looking geometry with the current backend."
            ),
            context={
                # CU-322: a backend that cannot serve this topology is an
                # atmosphere-coverage refusal, not a rejected parameter — the
                # marker routes it to the advisory surface (errors.is_coverage_refusal).
                COVERAGE_SURFACE_KEY: COVERAGE_REFUSAL_SURFACE,
                "model": type(model).__name__,
                "h_sensor": los.h_sensor,
                "h_tgt": los.h_tgt,
                "theta_o": los.theta_o,
                "los_direction": los.los_direction,
            },
        )
    # The companion serves the illumination and sky legs for every arrangement;
    # for a ``simple`` scene it IS the model, so nothing about that path moves.
    atmosphere: SimpleAtmosphere = backends.simple

    lam = np.asarray(wavelength_um, dtype=np.float64)
    h_atm_top = float(los.h_atm_top)
    theta_s = los.theta_s

    # Validate before compute (Rule 16): the exo-target admissibility of a
    # library-backed observer leg is knowable from the LOS and the family's own
    # ceiling, so it is settled BEFORE any leg is evaluated.  Ordering matters
    # — evaluating the observer leg first would let a partial-column family's
    # own out-of-hull error surface instead of this refusal, which is the one
    # that names why the composition is inadmissible and which families serve it.
    _refuse_library_backed_exo_target(backends, los, h_atm_top)

    # ---------------------------------------------------------------
    # 1. Observer leg — the target ↔ sensor segment.
    # ---------------------------------------------------------------
    if backends.column is not None:
        warnings.warn(
            (
                "AtmosphereStage: this up-looking scene is served by TWO atmosphere "
                f"models (CU-226). The observer leg ({los.h_sensor:.0f} m -> "
                f"{los.h_tgt:.0f} m MSL) comes from the interpolated up-looking run "
                "family; the target's illumination (solar column and sky hemisphere "
                "above the target) and the sky radiance along the LOS continuation "
                "come from the SimpleAtmosphere companion, because an up-looking run "
                "family carries neither leg and neither can be recovered from it. "
                "The two models are calibrated independently, so the composed "
                "answer is not a single self-consistent radiative transfer. Use "
                "atmosphere.model='simple' for one consistent model throughout, or "
                "accept the split (result.inspect() -> stage_outputs['atmosphere']"
                "['topology_provenance']['backend_split'] records it)."
            ),
            UserWarning,
            stacklevel=3,
        )
    leg = observer_leg_from_los(los)
    segment = _evaluate_observer_segment(backends, lam, los, leg, theta_s, h_atm_top)
    tau_obs = segment.tau
    L_obs = segment.L_toward_sensor

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
        "backend_split": _backend_split_note(backends),
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


@dataclass(frozen=True)
class _ObserverSegment:
    """The observer leg, reduced to the two products the composition reads.

    Deliberately **not** a
    :class:`~radiant.atmosphere.segments.SegmentQuantities` (CU-226 design
    question (i)).  That contract carries both directional radiances, and an
    up-looking run family measures only one — its reverse-direction product for
    the same column is a separate run set.  The composition never needs the
    other direction:
    :func:`~radiant.atmosphere.observer_leg.observer_leg_from_los` sets
    ``toward_sensor`` from the topology, ``"toward_lower"`` on the up-looking
    branch (the sensor IS the segment's lower endpoint) and ``"toward_upper"``
    on the level branch, and every reader of the observer segment —
    :func:`evaluate_uplooking_topology` and
    :func:`_level_sky_at_aperture` — reads exactly
    ``radiance_toward(leg.toward_sensor)``.  Reducing to that one field at the
    point of evaluation makes the unreachability structural instead of a
    comment: there is no ``L_toward_upper`` slot for a library product to have
    to invent.

    Attributes
    ----------
    tau:
        Segment transmittance, dimensionless ∈ [0, 1].
    L_toward_sensor:
        Radiance emerging at the segment's sensor-side end [W/m²/sr/µm].
    provenance:
        Which evaluator produced it, and its inputs (Rule 16).
    """

    tau: np.ndarray
    L_toward_sensor: np.ndarray
    provenance: dict[str, Any]


def _backend_split_note(backends: _Backends) -> str:
    """One line naming which model served which leg (Rule 16 inspectability)."""
    if backends.column is None:
        return "all legs: SimpleAtmosphere"
    return (
        f"observer leg: {type(backends.column).__name__} up-looking run family; "
        f"illumination and sky-continuation legs: "
        f"{type(backends.simple).__name__} companion (CU-226 hybrid)"
    )


def _evaluate_observer_segment(
    backends: _Backends,
    lam: np.ndarray,
    los: LineOfSightGeometry,
    leg: ObserverLeg,
    theta_s_rad: float | None,
    h_atm_top_m: float,
) -> _ObserverSegment:
    """Dispatch the observer-leg segment to its evaluator (Rule 19 split).

    Three evaluators, selected by (backend, segment shape): the up-looking run
    family's column product when one is attached, otherwise the simple-model
    level-arm or column evaluator.
    """
    if backends.column is not None:
        return _library_observer_segment(backends.column, lam, los, leg)

    spec = leg.spec
    if isinstance(spec, LevelArmSpec):
        segment = evaluate_level_arm(
            backends.simple,
            lam,
            spec,
            theta_s_rad=theta_s_rad,
            delta_phi_rad=leg.delta_phi_seg_rad,
            h_atm_top_m=h_atm_top_m,
        )
    else:
        segment = evaluate_column_segment(
            backends.simple,
            lam,
            spec,
            theta_s_rad=theta_s_rad,
            delta_phi_rad=leg.delta_phi_seg_rad,
            h_atm_top_m=h_atm_top_m,
        )
    return _ObserverSegment(
        tau=np.asarray(segment.tau, dtype=np.float64),
        L_toward_sensor=np.asarray(segment.radiance_toward(leg.toward_sensor), dtype=np.float64),
        provenance=segment.provenance,
    )


def _library_observer_segment(
    column: UplookingColumnBackend,
    lam: np.ndarray,
    los: LineOfSightGeometry,
    leg: ObserverLeg,
) -> _ObserverSegment:
    """The observer leg from an up-looking MODTRAN-derived run family (CU-226).

    The family's product is the sensor→target column, keyed to its lower
    endpoint exactly as :class:`~radiant.atmosphere.segments.ColumnSegmentSpec`
    is, so no re-keying is needed — the backend reads ``h_sensor``, ``h_tgt``
    and ``θ_o`` off the same LOS this leg was derived from, and refuses (loudly,
    with its own actionable message) any query its hull cannot serve: off
    vertical, a lower endpoint other than the rendered one, or a target outside
    the ladder.
    """
    if isinstance(leg.spec, LevelArmSpec):
        raise ParameterBoundsError(
            what=(
                "AtmosphereStage: a LEVEL path cannot be served by an up-looking "
                f"interpolated run family (altitude {leg.spec.altitude_m:.0f} m MSL, "
                f"arm length {leg.spec.length_m:.0f} m)"
            ),
            why=(
                "An up-looking run family is a column ladder: every rung integrates "
                "upward from one lower endpoint.  A level arm has zero vertical "
                "extent and a local zenith of pi/2 everywhere along it, so no rung "
                "of the ladder is that path and no interpolation between rungs "
                "produces it (Rule 17 — this is a refusal, not an approximation)."
            ),
            action=(
                "Set atmosphere.model='simple' for a level path — its level-arm "
                "evaluator uses the true chord length at the arm altitude — or "
                "raise the target above the sensor to make the path up-looking."
            ),
            context={
                # CU-322: routes to the advisory surface (errors.is_coverage_refusal).
                COVERAGE_SURFACE_KEY: COVERAGE_REFUSAL_SURFACE,
                "h_sensor": los.h_sensor,
                "h_tgt": los.h_tgt,
                "altitude_m": leg.spec.altitude_m,
                "length_m": leg.spec.length_m,
            },
        )
    if leg.toward_sensor != "toward_lower":
        raise ParameterBoundsError(  # pragma: no cover - contract invariant
            what=(
                "AtmosphereStage: the up-looking observer leg asked for the "
                f"'{leg.toward_sensor}' radiance, which an up-looking run family "
                "does not carry"
            ),
            why=(
                "An up-looking column's sensor is its LOWER endpoint, so the "
                "radiance reaching it is always L_toward_lower — the one direction "
                "the family measures.  Reaching this branch means observer_leg and "
                "the topology classification disagree."
            ),
            action="File a bug — this is an internal invariant violation.",
            context={"toward_sensor": leg.toward_sensor, "theta_o": los.theta_o},
        )

    product = column.uplooking_column_product(lam, los)
    tau = np.asarray(product.tau, dtype=np.float64)
    L_lower = np.asarray(product.L_toward_lower, dtype=np.float64)
    _validate_library_segment(tau, L_lower, lam)

    provenance = dict(product.provenance)
    provenance["evaluator"] = f"{type(column).__name__}.uplooking_column_product"
    provenance["radiance_read"] = "L_toward_lower (the sensor is the lower endpoint)"
    return _ObserverSegment(tau=tau, L_toward_sensor=L_lower, provenance=provenance)


def _validate_library_segment(tau: np.ndarray, radiance: np.ndarray, lam: np.ndarray) -> None:
    """Range-check a library column product (Rule 17 — no plausible-wrong values).

    ``SegmentQuantities`` applies exactly these checks to a simple-model
    segment; the library branch does not build one (see :class:`_ObserverSegment`),
    so the checks are applied here rather than dropped.
    """
    for name, arr in (("tau", tau), ("L_toward_lower", radiance)):
        if arr.shape != lam.shape:
            raise ParameterBoundsError(
                what=(
                    f"uplooking run family returned {name} of shape {arr.shape}, "
                    f"expected the query grid shape {lam.shape}"
                ),
                why="Every spectral product must ride the chain wavelength grid.",
                action="Regenerate the run family on a grid covering the chain band.",
                context={"field": name, "shape": arr.shape},
            )
        if not np.all(np.isfinite(arr)):
            raise ParameterBoundsError(
                what=f"uplooking run family returned a non-finite {name}",
                why="NaN or inf propagates silently through every downstream product.",
                action="Inspect the run family NPZ and the interpolation query.",
                context={"field": name},
            )
    tau_min = float(tau.min())
    tau_max = float(tau.max())
    if tau_min < -_LIBRARY_TOLERANCE or tau_max > 1.0 + _LIBRARY_TOLERANCE:
        raise ParameterBoundsError(
            what=f"uplooking run family tau outside [0, 1] (min={tau_min:g}, max={tau_max:g})",
            why=(
                "Segment transmittance is a probability of transmission; a value "
                "outside [0, 1] means the interpolation left the physical range."
            ),
            action="Inspect the run family NPZ transmittance arrays.",
            context={"min": tau_min, "max": tau_max},
        )
    rad_min = float(radiance.min())
    if rad_min < -_LIBRARY_TOLERANCE:
        raise ParameterBoundsError(
            what=f"uplooking run family L_toward_lower has negative values (min={rad_min:g})",
            why="Emergent spectral radiance must be >= 0; Rule 17 forbids silent clipping.",
            action="Inspect the run family NPZ path_radiance_toward_lower arrays.",
            context={"min": rad_min},
        )


def _refuse_library_backed_exo_target(
    backends: _Backends,
    los: LineOfSightGeometry,
    h_atm_top_m: float,
) -> None:
    """Admit or refuse a library-backed observer leg whose target is exo.

    CU-224 checklist item (ex-CU-308).  ``_illumination_products``' exo branch
    substitutes the exact vacuum identity (``τ_sun ≡ 1``, ``E_sky ≡ 0``) for
    the proxy down-looking evaluation.  That is correct for the *illumination*
    and says nothing on its own about the composition it lands in, so with a
    library-backed observer leg the join between the two at the top of the
    modelled column needs an anchor.  Whether one exists is a property of the
    **backing family**, and the family answers it itself
    (``uplooking_target_ceiling_m``) — no family names appear here.

    **Full column (ceiling ≥ h_atm_top) — permitted.**  MODTRAN's atmosphere
    ends at ``h_atm_top``.  A family whose measured target-axis ceiling reaches
    it has integrated the *entire* column, and the remaining path up to an exo
    target is vacuum: zero extinction, zero emission.  The composed observer
    leg for any ``h_tgt > h_atm_top`` is therefore **identically** the family's
    own top-of-column run — the anchor the refusal used to demand is the family
    itself, and the composition is exact rather than merely plausible.  The
    query side of this is
    :meth:`~radiant.atmosphere.interpolated.InterpolatedAtmosphere._vacuum_clamped_target_m`,
    the target-axis mirror of the sensor-axis identity the same module already
    ships (the ladders' 40 000 km duplicate node).  Shipped families that
    qualify today: the batch-2 M column fan and P sensor ladder, both rendered
    ground/elevated → 100 km.

    **Partial column (ceiling < h_atm_top, or unknown) — refused.**  Such a
    family stops inside the atmosphere.  Between its top rung and the exo target
    lies real, unmeasured air, and nothing in the family measures it; composing
    its top rung with the vacuum identity would join a measured leg to an
    invented one and report the result as ordinary.  So it is refused, loudly,
    naming the measured ceiling and the full-column families that do serve the
    scene (Rule 17 — a refusal, not an approximation).  This is the arm the
    20 km K ladder and N zenith fan take.

    ``atmosphere.model='simple'`` has ``backends.column is None`` and is
    untouched — its exo path stays exactly as CU-226 left it.
    """
    if backends.column is None or los.h_tgt < h_atm_top_m:
        return
    ceiling_m = backends.column.uplooking_target_ceiling_m
    if ceiling_m is not None and ceiling_m >= h_atm_top_m:
        # The family measured the whole column; the rest of the path is vacuum.
        return
    measured = "unrecorded" if ceiling_m is None else f"{ceiling_m:.0f} m"
    raise ParameterBoundsError(
        what=(
            f"AtmosphereStage: up-looking target at h_tgt = {los.h_tgt:.0f} m is at or "
            f"above h_atm_top = {h_atm_top_m:.0f} m while the observer leg is served "
            "by an interpolated run family"
        ),
        why=(
            "The composition has no anchor. The observer leg would come from the "
            "MODTRAN family while the target's illumination collapses to the exo "
            "vacuum identity (tau_sun = 1, E_sky = 0), and the join between the two "
            "at the top of the modelled column has never been validated against a "
            f"run: this family's own measured target ceiling is {measured}, BELOW "
            "h_atm_top, so it stops inside the atmosphere and real, unmeasured air "
            "lies between its top rung and the target (CU-224, ex-CU-308). A family "
            "that DOES reach h_atm_top is a different case — it measured the entire "
            "column, the rest of the path is vacuum, and the composed answer is "
            "identically its own top-of-column run, so that case is served. "
            "Answering here anyway would compose a measured leg with an unvalidated "
            "one and report it as an ordinary result."
        ),
        action=(
            "Use atmosphere.model='simple' for this scene (one consistent model "
            "throughout, exo illumination included), lower the target below "
            "h_atm_top, or point atmosphere.interpolated_data_dir at a FULL-COLUMN "
            "up-looking family whose runs reach h_atm_top (shipped: "
            "midlat_summer_sst_column_fan for a ground observer at LOS zenith "
            "0-78.5 degrees, midlat_summer_uplooking_sensor_ladder for an observer "
            "at 0-100 km at the 48.2-degree diffusivity angle)."
        ),
        context={
            # CU-322: routes to the advisory surface (errors.is_coverage_refusal).
            COVERAGE_SURFACE_KEY: COVERAGE_REFUSAL_SURFACE,
            "h_tgt": los.h_tgt,
            "h_atm_top": h_atm_top_m,
            "h_sensor": los.h_sensor,
            "column_backend": type(backends.column).__name__,
            "family_target_ceiling_m": ceiling_m,
        },
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
    segment: _ObserverSegment,
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
    *,
    theta_s_rad: float | None,
    delta_phi_seg_rad: float,
    h_atm_top_m: float,
) -> tuple[np.ndarray, str]:
    """One whole-path evaluation for a level LOS (CU-224, ex-CU-276).

    The level branch used to compose ``L_arm→sensor + τ_arm · L_continuation``,
    joined at the target plane.  That join carried the CU-254 non-additivity:
    each segment emits at its own ``T_eff`` with its own species weights, so
    where the target sat changed the background behind it.  It survived CU-254
    only because no evaluator could express "constant-altitude arm then
    ascending arc" as one path; :mod:`radiant.atmosphere.level_whole_path` now
    can, and the sky is evaluated once, about the chord's real perigee.
    """
    assert isinstance(leg.spec, LevelArmSpec)  # caller-enforced branch invariant
    h_arm = leg.spec.altitude_m
    if h_arm >= h_atm_top_m:
        return (
            np.zeros_like(lam),
            "level path above h_atm_top — the whole LOS is vacuum, sky radiance ≡ 0",
        )
    # The band-gating policy applies wherever a sky radiance is produced, not
    # only where ``sky_radiance_along_los`` produces it (CU-260).
    warn_if_scattered_sky_provisional(lam, theta_s_rad)
    whole = evaluate_level_whole_path(
        atmosphere,
        lam,
        altitude_m=h_arm,
        arm_length_m=leg.spec.length_m,
        theta_s_rad=theta_s_rad,
        delta_phi_rad=delta_phi_seg_rad,
        h_atm_top_m=h_atm_top_m,
    )
    perigee_m = float(whole.provenance["perigee_altitude_m"])
    note = (
        f"level whole-path sky at {h_arm:.0f} m MSL: one segment spanning the "
        f"{leg.spec.length_m:.0f} m constant-altitude arm and the ascending "
        f"continuation to cold space, about the chord perigee at {perigee_m:.1f} m MSL"
    )
    return np.asarray(whole.L_toward_lower, dtype=np.float64), note


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
