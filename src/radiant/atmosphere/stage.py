"""AtmosphereStage — chain wrapper for atmospheric transmission and path radiance.

Stage 4 Option C — **descriptor-driven assembly path is authoritative**.

This stage drives the new ``evaluate`` + ``assemble_*`` path: it builds the
:class:`AtmosphericQuantities` bundle from the configured atmosphere model,
then calls :func:`assemble_target_at_aperture` /
:func:`assemble_background_at_aperture` to produce the at-aperture radiance
arrays.

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
    - ``r0_m``: Fried parameter (only when ``atmosphere.r0_m > 0``).
"""

from __future__ import annotations

import logging

import numpy as np

from radiant.atmosphere._quantities import AtmosphericQuantities
from radiant.atmosphere.assembly import (
    assemble_background_at_aperture,
    assemble_target_at_aperture,
    validate_no_atmosphere_subcase,
)
from radiant.atmosphere.errors import AtmosphereValidationError
from radiant.atmosphere.loaders import build_atmosphere_model, model_requires_prebuild
from radiant.core.chain import ChainState
from radiant.core.parameters import ParameterSet, Provenance
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
        # Matrix §7: space sub-case requires a positive user-set
        # platform.h_sensor and the LOS must clear the Earth limb; the
        # ground_test / lab_test sub-cases require a UserSpectralBackground
        # on the background arm.  Fails loud per Rule 17 before any
        # physics runs.
        # ------------------------------------------------------------------
        if getattr(target_desc, "target_location", None) == "no_atmosphere":
            try:
                h_sensor_rv = params.get_resolved("platform.h_sensor")
                h_sensor: float | None = float(h_sensor_rv.value)
                h_sensor_user_set: bool = h_sensor_rv.provenance is not Provenance.DEFAULT
            except KeyError:
                # Platform schema not registered in this ParameterSet (source-
                # only unit-test fixture).  Treat as "not supplied".
                h_sensor = None
                h_sensor_user_set = False
            validate_no_atmosphere_subcase(
                target=target_desc,
                background=background_desc,
                los=los,
                h_sensor=h_sensor,
                h_sensor_user_set=h_sensor_user_set,
            )

        # ------------------------------------------------------------------
        # 3. Evaluate the atmospheric quantities bundle and assemble the
        #    at-aperture radiance arrays for the target and background arms.
        # ------------------------------------------------------------------
        atm_quantities: AtmosphericQuantities = model.evaluate(  # type: ignore[attr-defined]
            state.wavelength_um,
            los,
            params,
        )
        L_aperture_target: np.ndarray = assemble_target_at_aperture(
            target_desc,
            atm_quantities,
            los,
        )
        L_aperture_background: np.ndarray | None = assemble_background_at_aperture(
            background_desc,
            atm_quantities,
            los,
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
        state = (
            state.with_frame(target_frame)
            .with_frame(at_aperture_frame)
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

        # Turbulence: store Fried parameter for downstream stages.
        try:
            r0_m: float = params.get("atmosphere.r0_m")
        except (KeyError, TypeError):
            r0_m = 0.0
        if r0_m > 0.0:
            state = state.with_stage_output("atmosphere", "r0_m", r0_m)

        return state


__all__ = ["AtmosphereStage"]
