"""AtmosphereStage — chain wrapper for atmospheric transmission and path radiance.

Stage 4 Option C — **descriptor-driven assembly path is authoritative**.

This stage drives the new ``evaluate`` + ``assemble_*`` path: it builds the
:class:`AtmosphericQuantities` bundle from the configured atmosphere model,
then calls :func:`assemble_target_at_aperture` /
:func:`assemble_background_at_aperture` to produce the at-aperture radiance
arrays.

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
from pathlib import Path

import numpy as np

from radiant.atmosphere._quantities import AtmosphericQuantities
from radiant.atmosphere.assembly import (
    assemble_background_at_aperture,
    assemble_target_at_aperture,
    validate_no_atmosphere_subcase,
)
from radiant.atmosphere.exo import ExoAtmosphere
from radiant.atmosphere.simple import SimpleAtmosphere
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
        # 1. Build the atmospheric model (pure — no chain coupling).
        # ------------------------------------------------------------------
        if model_name == "exo":
            model: object = ExoAtmosphere()
        elif model_name == "tabulated":
            model = self._build_tabulated(params)
        elif model_name == "modtran":
            model = self._build_modtran(params)
        elif model_name == "interpolated":
            model = self._build_interpolated(params)
        else:
            # Default: simple parametric model.
            model = SimpleAtmosphere(
                visibility_km=params.get("atmosphere.visibility_km"),
                aerosol_type=params.get("atmosphere.aerosol_type"),
                precipitable_water_cm=params.get("atmosphere.precipitable_water_cm"),
                standard_atmosphere=params.get("atmosphere.standard_atmosphere"),
            )

        # ------------------------------------------------------------------
        # 2. Read descriptor inputs from SourceStage.
        # ------------------------------------------------------------------
        source_out = state.stage_outputs.get("source", {})
        target_desc = source_out.get("target")
        background_desc = source_out.get("background")
        los = source_out.get("los_geometry")

        if target_desc is None:
            raise ValueError(
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
                h_sensor_user_set: bool = (
                    h_sensor_rv.provenance is not Provenance.DEFAULT
                )
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
            state.wavelength_um, los, params,
        )
        L_aperture_target: np.ndarray = assemble_target_at_aperture(
            target_desc, atm_quantities, los,
        )
        L_aperture_background: np.ndarray | None = assemble_background_at_aperture(
            background_desc, atm_quantities, los,
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
                "atmosphere", "E_sky_scattered", atm_quantities.E_sky_scattered,
            )
            .with_stage_output(
                "atmosphere", "E_sky_thermal", atm_quantities.E_sky_thermal,
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

    # ------------------------------------------------------------------
    # Model builders (file I/O happens here, before evaluate)
    # ------------------------------------------------------------------

    @staticmethod
    def _build_tabulated(params: ParameterSet) -> object:
        """Construct a TabulatedAtmosphere from parameters."""
        from radiant.atmosphere.tabulated import TabulatedAtmosphere

        tau_file = params.get("atmosphere.tabulated_transmittance_file")
        lpath_file = params.get("atmosphere.tabulated_path_radiance_file")
        ldown_file = params.get("atmosphere.tabulated_downwelling_file")

        if not tau_file or not lpath_file:
            raise ValueError(
                "AtmosphereStage: model='tabulated' requires "
                "atmosphere.tabulated_transmittance_file and "
                "atmosphere.tabulated_path_radiance_file to be set."
            )

        # Detect format by extension.
        if str(tau_file).endswith(".npz"):
            return TabulatedAtmosphere.from_npz(tau_file)
        return TabulatedAtmosphere.from_csv(
            tau_file, lpath_file, ldown_file if ldown_file else None,
        )

    @staticmethod
    def _build_modtran(params: ParameterSet) -> object:
        """Construct a ModtranAtmosphere from parameters."""
        from radiant.atmosphere.modtran import ModtranAtmosphere, ModtranConfig

        config = ModtranConfig(
            binary_path=Path(params.get("atmosphere.modtran.binary_path")),
            cache_dir=Path(
                str(params.get("atmosphere.modtran.cache_dir")).replace(
                    "~", str(Path.home()),
                )
            ),
            allow_fallback=params.get("atmosphere.modtran.allow_fallback"),
            atmosphere_profile=params.get("atmosphere.modtran.atmosphere_profile"),
            aerosol_model=params.get("atmosphere.modtran.aerosol_model"),
            h2o_scale=params.get("atmosphere.modtran.h2o_scale"),
            o3_scale=params.get("atmosphere.modtran.o3_scale"),
            spectral_resolution_cm1=params.get(
                "atmosphere.modtran.spectral_resolution_cm1"
            ),
        )
        return ModtranAtmosphere(config)

    @staticmethod
    def _build_interpolated(params: ParameterSet) -> object:
        """Construct an InterpolatedAtmosphere from a data directory.

        The data directory must contain NPZ files, each with keys
        ``wavelength_um``, ``transmittance``, ``path_radiance``, and
        optionally ``atm_emission_down``.  Each file must also contain
        a ``geometry`` key with a JSON-encoded dict of coordinate
        values.
        """
        import json

        from radiant.atmosphere.interpolated import (
            GeometryPoint,
            InterpolatedAtmosphere,
        )
        from radiant.atmosphere.tabulated import TabulatedAtmosphere

        data_dir = params.get("atmosphere.interpolated_data_dir")
        if not data_dir:
            raise ValueError(
                "AtmosphereStage: model='interpolated' requires "
                "atmosphere.interpolated_data_dir to be set."
            )

        axes_str: str = params.get("atmosphere.interpolation_axes")
        axes = [a.strip() for a in axes_str.split(",")]
        method: str = params.get("atmosphere.interpolation_method")

        data_path = Path(data_dir)
        if not data_path.exists():
            raise FileNotFoundError(
                f"AtmosphereStage: interpolated data directory not found: "
                f"{data_path}."
            )

        npz_files = sorted(data_path.glob("*.npz"))
        if len(npz_files) < 2:
            raise ValueError(
                f"AtmosphereStage: interpolated data directory {data_path} "
                f"must contain at least 2 NPZ files, found {len(npz_files)}."
            )

        points: list[GeometryPoint] = []
        for npz_file in npz_files:
            data = np.load(npz_file, allow_pickle=True)

            if "geometry" not in data:
                raise ValueError(
                    f"AtmosphereStage: NPZ file {npz_file} is missing a "
                    "'geometry' key with coordinate values."
                )

            geom_raw = data["geometry"]
            coords = geom_raw.item() if hasattr(geom_raw, "item") else json.loads(str(geom_raw))

            tab = TabulatedAtmosphere.from_npz(npz_file)
            points.append(
                GeometryPoint(
                    coordinates=coords,
                    transmittance=tab.transmittance_data,
                    path_radiance=tab.path_radiance_data,
                    atm_emission_down=tab.atm_emission_down_data,
                )
            )

        return InterpolatedAtmosphere(points, axes, method)


__all__ = ["AtmosphereStage"]
