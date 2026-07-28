"""AtmosphereStage — chain wrapper for atmospheric transmission and path radiance.

Stage 4 Option C — **descriptor-driven assembly path is authoritative**.

This stage drives the new ``evaluate`` + ``assemble_*`` path: it builds the
:class:`AtmosphericQuantities` bundle from the configured atmosphere model,
then calls :func:`assemble_target_at_aperture` /
:func:`assemble_background_at_aperture` to produce the at-aperture radiance
arrays.

Path topology (ADR-0011, Geometry-Flexibility Phase 2)
------------------------------------------------------
The bundle is not built by calling ``model.evaluate`` directly; it comes from
:func:`radiant.atmosphere.topology.evaluate_path_topology`, which dispatches on
the **derived** ``los.los_direction``: ``down`` is the backend's own evaluate
path, unchanged and byte-identical (including the Gap-95 exo-altitude target,
now expressed as a segment composition over that same call); ``up`` and
``level`` are served by path-segment composition. An up/level topology also
yields a sky-continuation radiance, which is handed to the ``SkyBackground``
assembly arm — the one new product, carried alongside the eight-field bundle
rather than bolted onto it (guardrail G1).

Rule 6 — the atmosphere model is resolved before chain execution:
``RadiantSession.run`` calls
:func:`radiant.atmosphere.loaders.build_atmosphere_model` (which owns any
file I/O) and injects the model via
``stage_outputs["atmosphere_config"]["model"]``. This stage only falls
back to building I/O-free models (simple, exo, modtran without a
``tape7_path``) inline for partial-chain use, and refuses to build
file-backed models itself (``loaders.model_requires_prebuild``).

Produces
--------
Frame ``"at_aperture"`` with spectral radiance = ``at_aperture_target`` —
    kept as the canonical name consumed by OpticsStage (``× τ_opt``).

Frame ``"at_aperture_target"`` with spectral radiance
    ``L_aperture_target(λ)`` — the §6.1 assembly result for the target arm.

Frame ``"at_aperture_background"`` with spectral radiance, **only when**
    the background descriptor is non-``None`` (Decision #13: extended
    terrestrial / airborne cells skip this term entirely).

Frame ``"at_source_target"`` with spectral radiance = the pre-atmosphere
    source emission (emitted+reflected radiance LEAVING the target, before
    the up-leg τ/L_path) — Gap 91.  This is the ``L_source`` the at-aperture
    assembly consumes; ``at_aperture_target ≈ τ_up · at_source_target +
    L_path_up`` by construction.  Purely additive (feeds no metric).

Frame ``"at_source_background"`` with the background pre-atmosphere source
    emission, **only when** the background descriptor is non-``None``
    (Gap 91; same Decision #13 gate as ``at_aperture_background``).

Stage outputs under ``stage_outputs["atmosphere"]``:
    - ``atm_quantities``: the :class:`AtmosphericQuantities` bundle
      (the eight spectral fields used by §6.1 assembly).
    - ``tau_atm``: ``atm_quantities.tau_up`` exposed as ndarray for
      downstream stages that still key off the legacy name.
    - ``L_path``: ``atm_quantities.L_path_up`` exposed as ndarray for
      downstream stages that still key off the legacy name.
    - ``E_sky_scattered``: ``atm_quantities.E_sky_scattered`` exposed
      for Rule 16 inspectability (Stage 6 — Option C decomposition).
    - ``E_sky_thermal``: ``atm_quantities.E_sky_thermal`` exposed for
      Rule 16 inspectability (Stage 6 — Option C decomposition).
    - ``r0_m``: Fried parameter [m], present only when turbulence is on.
      Resolved by :func:`radiant.atmosphere.r0_resolution.resolve_fried_parameter`
      — the direct ``atmosphere.r0_m`` input (default) or, when
      ``atmosphere.cn2_profile`` selects a profile, the path-weighted integral
      over the line of sight (Gap 110).
    - ``r0_resolution``: the
      :class:`~radiant.atmosphere.r0_resolution.FriedParameterResolution`
      record, published only when a Cn² profile was actually evaluated, so a
      scene using the direct input keeps exactly the stage outputs it had
      before.
"""

from __future__ import annotations

import logging

import numpy as np

from radiant.atmosphere._quantities import AtmosphericQuantities
from radiant.atmosphere.assembly import (
    assemble_background_at_aperture,
    assemble_background_source_emission,
    assemble_target_at_aperture,
    assemble_target_source_emission,
    validate_no_atmosphere_subcase,
)
from radiant.atmosphere.errors import AtmosphereValidationError
from radiant.atmosphere.loaders import build_atmosphere_model, model_requires_prebuild
from radiant.atmosphere.r0_resolution import resolve_fried_parameter
from radiant.atmosphere.topology import TopologyProducts, evaluate_path_topology
from radiant.core.chain import ChainState
from radiant.core.descriptors import GroundBackground
from radiant.core.los_geometry import LineOfSightGeometry
from radiant.core.parameters import ParameterBoundsError, ParameterSet
from radiant.core.radiometry import RadiometricFrame

logger = logging.getLogger(__name__)


class AtmosphereStage:
    """Chain stage for atmospheric transmission and path radiance.

    Stage 4 of Option C: drives the descriptor-driven assembly path
    exclusively.  Publishes the target / background at-aperture radiance
    frames and the :class:`AtmosphericQuantities` bundle.
    """

    @property
    def name(self) -> str:
        return "atmosphere"

    def run(self, state: ChainState, params: ParameterSet) -> ChainState:
        model_name: str = params.get("atmosphere.model")

        # ------------------------------------------------------------------
        # 1. Resolve the atmospheric model. Rule 6: stages do not read
        #    files, so file-backed models (tabulated, interpolated, modtran
        #    with a tape7_path) must be
        #    built before chain execution and injected via
        #    stage_outputs["atmosphere_config"]["model"] — RadiantSession
        #    does this automatically. Models that need no file I/O are
        #    built inline as a fallback for partial-chain use.
        # ------------------------------------------------------------------
        atm_config = state.stage_outputs.get("atmosphere_config", {})
        model: object | None = atm_config.get("model")
        if model is None:
            if model_requires_prebuild(params):
                raise AtmosphereValidationError(
                    f"AtmosphereStage: model='{model_name}' (with the current "
                    "parameters) requires file I/O and must be constructed "
                    "before chain execution (Rule 6). "
                    "Run the chain via RadiantSession/Sensor (which injects "
                    "stage_outputs['atmosphere_config']['model']), or build "
                    "the model with "
                    "radiant.atmosphere.loaders.build_atmosphere_model() and "
                    "inject it into the initial ChainState."
                )
            model = build_atmosphere_model(params)

        # ------------------------------------------------------------------
        # 2. Read descriptor inputs from SourceStage.
        # ------------------------------------------------------------------
        source_out = state.stage_outputs.get("source", {})
        target_desc = source_out.get("target")
        background_desc = source_out.get("background")
        los = source_out.get("los_geometry")

        if target_desc is None:
            raise AtmosphereValidationError(
                "AtmosphereStage: SourceStage did not publish a TargetDescriptor "
                "under stage_outputs['source']['target']. Stage 4 requires the "
                "descriptor-driven path; run SourceStage before AtmosphereStage."
            )

        # ------------------------------------------------------------------
        # 2a. Stage 7 (Option C) — no_atmosphere sub-case preconditions.
        # Matrix §7: space sub-case requires a positive sensor altitude and
        # the LOS must clear the Earth limb; the ground_test / lab_test
        # sub-cases require a UserSpectralBackground on the background arm.
        # Fails loud per Rule 17 before any physics runs.
        # ADR-0011 / guardrail G2: the sensor endpoint is read from the LOS
        # contract (GeometryStage populates it from the required geometry
        # parameter), never side-loaded from the ParameterSet here — one
        # source of truth.  A LOS without it counts as "not supplied", the
        # same verdict the old un-set-parameter branch produced.
        # ------------------------------------------------------------------
        if getattr(target_desc, "target_location", None) == "no_atmosphere":
            h_sensor: float | None = los.h_sensor if los is not None else None
            validate_no_atmosphere_subcase(
                target=target_desc,
                background=background_desc,
                los=los,
                h_sensor=h_sensor,
                h_sensor_user_set=h_sensor is not None,
            )

        # ------------------------------------------------------------------
        # 2b. Background/topology admissibility (ADR-0011 Phase 2).  An
        # up-looking or level LOS terminates on space, so there is no ground
        # behind the target and a GroundBackground cannot be served — refuse
        # it here rather than propagating a ground term through a column that
        # does not exist (Rule 17).
        # ------------------------------------------------------------------
        _reject_ground_background_without_ground(background_desc, los)

        # ------------------------------------------------------------------
        # 3. Evaluate the atmospheric quantities bundle and assemble the
        #    at-aperture radiance arrays for the target and background arms.
        # ------------------------------------------------------------------
        # Topology dispatch (ADR-0011): down-looking scenes take the backend's
        # own evaluate path unchanged; up-looking and level scenes are served
        # by segment composition; the Gap-95 exo-altitude target is a segment
        # composition over the same down-looking call.  See
        # atmosphere/topology.py.
        topology: TopologyProducts = evaluate_path_topology(
            model,
            state.wavelength_um,
            los,
            params,
        )
        atm_quantities: AtmosphericQuantities = topology.quantities
        L_aperture_target: np.ndarray = assemble_target_at_aperture(
            target_desc,
            atm_quantities,
            los,
        )
        L_aperture_background: np.ndarray | None = assemble_background_at_aperture(
            background_desc,
            atm_quantities,
            los,
            sky_source_radiance=topology.sky_source_radiance,
        )
        # Gap 91: pre-atmosphere source emission (emitted+reflected radiance
        # LEAVING the target/background, before the up-leg τ/L_path).  This is
        # the L_source that the at-aperture assembly above consumes — published
        # here (the stage that assembles it, Rule 6) as a persisted frame.
        # Purely additive: it does not feed any existing frame or metric.
        L_source_target: np.ndarray = assemble_target_source_emission(
            target_desc,
            atm_quantities,
            los,
        )
        L_source_background: np.ndarray | None = assemble_background_source_emission(
            background_desc,
            atm_quantities,
            los,
            sky_source_radiance=topology.sky_source_radiance,
        )

        # ------------------------------------------------------------------
        # 4. Emit frames + stage outputs.
        # ------------------------------------------------------------------
        target_frame = RadiometricFrame(
            name="at_aperture_target",
            wavelength_um=state.wavelength_um,
            spectral_radiance=L_aperture_target,
            notes=(
                f"§6.1 assembly (target arm); model={model_name}; "
                f"variant={type(target_desc).__name__}"
            ),
        )
        # Canonical ``at_aperture`` frame consumed by OpticsStage.  It is
        # the target-arm at-aperture radiance — identical content to
        # ``at_aperture_target``, retained under the legacy name so the
        # OpticsStage contract is stable across the Stage 4 cut.
        at_aperture_frame = RadiometricFrame(
            name="at_aperture",
            wavelength_um=state.wavelength_um,
            spectral_radiance=L_aperture_target,
            notes=(
                f"§6.1 assembly (target arm, canonical); model={model_name}; "
                f"variant={type(target_desc).__name__}"
            ),
        )
        # Gap 91: pre-atmosphere source-emission frame (target arm).
        at_source_target_frame = RadiometricFrame(
            name="at_source_target",
            wavelength_um=state.wavelength_um,
            spectral_radiance=L_source_target,
            notes=(
                "pre-atmosphere source emission (emitted+reflected radiance "
                f"leaving the target, before τ_up/L_path); model={model_name}; "
                f"variant={type(target_desc).__name__}"
            ),
        )
        state = (
            state.with_frame(target_frame)
            .with_frame(at_aperture_frame)
            .with_frame(at_source_target_frame)
            .with_stage_output("atmosphere", "atm_quantities", atm_quantities)
            .with_stage_output("atmosphere", "tau_atm", atm_quantities.tau_up)
            .with_stage_output("atmosphere", "L_path", atm_quantities.L_path_up)
            # Stage 6 (Option C) — per-component diffuse-sky inspectability.
            # Per Rule 16: the two constituents of the consumed E_sky sum
            # must be individually inspectable so users / tests can audit
            # the physical regime (VIS = scattered-dominated; LWIR =
            # thermal-dominated; MWIR = mixed).
            .with_stage_output(
                "atmosphere",
                "E_sky_scattered",
                atm_quantities.E_sky_scattered,
            )
            .with_stage_output(
                "atmosphere",
                "E_sky_thermal",
                atm_quantities.E_sky_thermal,
            )
        )

        if L_aperture_background is not None:
            background_frame = RadiometricFrame(
                name="at_aperture_background",
                wavelength_um=state.wavelength_um,
                spectral_radiance=L_aperture_background,
                notes=(
                    f"§6.1 assembly (background arm); model={model_name}; "
                    f"variant={type(background_desc).__name__}"
                ),
            )
            state = state.with_frame(background_frame)

        # Gap 91: pre-atmosphere source-emission frame (background arm), when a
        # background is present (Decision #13: computed-extended cells skip it).
        if L_source_background is not None:
            at_source_background_frame = RadiometricFrame(
                name="at_source_background",
                wavelength_um=state.wavelength_um,
                spectral_radiance=L_source_background,
                notes=(
                    "pre-atmosphere source emission (background arm), before "
                    f"τ_up/L_path; model={model_name}; "
                    f"variant={type(background_desc).__name__}"
                ),
            )
            state = state.with_frame(at_source_background_frame)

        # Turbulence: resolve the Fried parameter (direct input or Cn²-profile
        # path integral — Gap 110) and store it for downstream stages.
        # atmosphere.cn2_profile = 'direct' (the default) reproduces the
        # pre-Gap-110 behaviour exactly.
        r0_resolution = resolve_fried_parameter(
            params,
            los,
            state.wavelength_um,
            tabulated_profile=atm_config.get("cn2_profile"),
        )
        if r0_resolution.r0_m > 0.0:
            state = state.with_stage_output("atmosphere", "r0_m", r0_resolution.r0_m)
        if r0_resolution.path is not None:
            # Only the derived path publishes diagnostics: a scene that simply
            # entered r0_m sees exactly the stage outputs it saw before.
            state = state.with_stage_output("atmosphere", "r0_resolution", r0_resolution)
            logger.info("Turbulence r₀ resolved: %s", r0_resolution.detail)

        return state


def _reject_ground_background_without_ground(
    background: object,
    los: LineOfSightGeometry | None,
) -> None:
    """Refuse a ``GroundBackground`` on a path whose LOS never reaches the ground.

    Rule B (matrix §3.2.5) selects the background by where the LOS
    *continuation* terminates.  For an up-looking or level path it terminates
    on space, so the ground is not behind the target at all; the up/level
    quantities bundle consequently carries the observer leg in
    ``tau_full_up`` / ``L_path_full`` rather than a ground→sensor column
    (``atmosphere/uplooking_quantities.py``).  Assembling a ground term
    against those fields would produce a number for a surface the sensor
    cannot see, so it raises (Rule 17).

    No-op for every down-looking scene, which is where every existing
    ``GroundBackground`` lives.
    """
    if los is None or not isinstance(background, GroundBackground):
        return
    if los.los_direction == "down":
        return
    raise ParameterBoundsError(
        what=(
            f"AtmosphereStage: a GroundBackground was supplied for an "
            f"{los.los_direction}-looking path (h_sensor = {los.h_sensor} m, "
            f"h_tgt = {los.h_tgt} m, theta_o = {los.theta_o} rad)"
        ),
        why=(
            "The background is what lies behind the target along the line of sight "
            "(Use-Case Matrix Rule B).  An up-looking or level LOS continues upward "
            "past the target and leaves the atmosphere — the Earth's surface is "
            "behind the *sensor*, not behind the target — so there is no ground "
            "column to propagate a ground radiance through."
        ),
        action=(
            "Use SkyBackground (the Rule-B default for up-looking and level scenes, "
            "computed from the scene with no user parameters), a "
            "UserSpectralBackground if you have a measured background spectrum, or a "
            "down-looking geometry if you meant to view the ground."
        ),
        context={
            "h_sensor": los.h_sensor,
            "h_tgt": los.h_tgt,
            "theta_o": los.theta_o,
            "los_direction": los.los_direction,
        },
    )


__all__ = ["AtmosphereStage"]
