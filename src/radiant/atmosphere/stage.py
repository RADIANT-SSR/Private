"""AtmosphereStage — chain wrapper for atmospheric transmission and path radiance.

Wraps all atmosphere models (simple, exo, tabulated, modtran,
interpolated) into the :class:`~radiant.core.chain.Stage` protocol.

Produces
--------
Frame ``"at_aperture"`` with spectral radiance:
    ``L_at_aperture(λ) = L_target(λ) · τ_atm(λ) + L_path(λ)``

Stage outputs under ``stage_outputs["atmosphere"]``:
    - ``tau_atm``: transmittance values (ndarray)
    - ``L_path``: path radiance values (ndarray)
    - ``L_atm_down``: downwelling emission values (ndarray)
"""

from __future__ import annotations

import logging
from pathlib import Path

from radiant.atmosphere.exo import ExoAtmosphere
from radiant.atmosphere.protocol import AtmosphericGeometry
from radiant.atmosphere.simple import SimpleAtmosphere
from radiant.core.chain import ChainState
from radiant.core.parameters import ParameterSet
from radiant.core.radiometry import RadiometricFrame

logger = logging.getLogger(__name__)


class AtmosphereStage:
    """Chain stage for atmospheric transmission and path radiance."""

    @property
    def name(self) -> str:
        return "atmosphere"

    def run(self, state: ChainState, params: ParameterSet) -> ChainState:
        model_name: str = params.get("atmosphere.model")

        geometry = AtmosphericGeometry(
            sensor_altitude_m=params.get("geometry.sensor_altitude_m"),
            target_altitude_m=params.get("geometry.target_altitude_m"),
            path_zenith_rad=params.get("geometry.path_zenith_rad"),
            solar_zenith_rad=params.get("geometry.solar_zenith_rad"),
            solar_azimuth_rad=params.get("geometry.solar_azimuth_rad"),
        )

        if model_name == "exo":
            model = ExoAtmosphere()
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

        atm_state = model.build_state(state.wavelength_um, geometry)

        # Read the source radiance from the at_target frame.
        at_target = state.frames["at_target"]
        L_target = at_target.spectral_radiance
        if L_target is None:
            raise ValueError(
                "AtmosphereStage: 'at_target' frame has no spectral_radiance. "
                "SourceStage must run first and produce spectral radiance."
            )

        tau = atm_state.transmittance.values
        L_path = atm_state.path_radiance.values
        L_at_aperture = L_target * tau + L_path

        frame = RadiometricFrame(
            name="at_aperture",
            wavelength_um=state.wavelength_um,
            spectral_radiance=L_at_aperture,
            notes=(
                f"L_target × τ_atm + L_path ({model_name})"
            ),
        )

        return (
            state.with_frame(frame)
            .with_stage_output("atmosphere", "tau_atm", tau)
            .with_stage_output("atmosphere", "L_path", L_path)
            .with_stage_output("atmosphere", "L_atm_down", atm_state.atm_emission_down.values)
        )

    # ------------------------------------------------------------------
    # Model builders (file I/O happens here, before build_state)
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

        import numpy as np

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
