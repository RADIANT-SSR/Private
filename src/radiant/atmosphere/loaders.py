"""Pre-chain construction of the configured atmosphere model.

Rule 6: stages do not read files — all file I/O happens before chain
execution. This module owns the params → atmosphere-model resolution,
including the file reads needed by the ``tabulated`` and
``interpolated`` models. The API layer (``RadiantSession.run``) calls
:func:`build_atmosphere_model` before the chain starts and injects the
result via ``stage_outputs["atmosphere_config"]["model"]``;
``AtmosphereStage`` consumes the injected model.

The ``modtran`` model is constructed here without file I/O; its
``evaluate()`` invokes the external MODTRAN binary (or its cache) at
chain time, which is inherent to that model, not config-file reading.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import numpy as np

from radiant.core.parameters import ParameterSet

logger = logging.getLogger(__name__)

#: Models whose construction requires reading data files. These MUST be
#: built before chain execution (Rule 6); AtmosphereStage refuses to
#: build them inside ``run()``.
FILE_BACKED_MODELS: frozenset[str] = frozenset({"tabulated", "interpolated"})


def build_atmosphere_model(params: ParameterSet) -> object:
    """Construct the atmosphere model selected by ``atmosphere.model``.

    Performs any file I/O the model needs (NPZ/CSV tables for
    ``tabulated``, an NPZ directory scan for ``interpolated``). Call
    this before chain execution.
    """
    model_name: str = params.get("atmosphere.model")

    if model_name == "exo":
        from radiant.atmosphere.exo import ExoAtmosphere

        return ExoAtmosphere()
    if model_name == "tabulated":
        return _build_tabulated(params)
    if model_name == "modtran":
        return _build_modtran(params)
    if model_name == "interpolated":
        return _build_interpolated(params)

    # Default: simple parametric model.
    from radiant.atmosphere.simple import PROFILE_PWV_CM, SimpleAtmosphere
    from radiant.core.parameters import Provenance

    profile: str = params.get("atmosphere.standard_atmosphere")
    pwv_cm: float = params.get("atmosphere.precipitable_water_cm")

    # Gap 57: the climate preset implies its water column. If the user
    # selected a profile but left precipitable_water_cm at its schema
    # default, use the profile's standard column (McClatchey/MODTRAN) so
    # e.g. "tropical" carries tropical humidity rather than the
    # US-standard 1.4 cm. An explicitly set PWV always wins.
    pwv_rv = params.get_resolved("atmosphere.precipitable_water_cm")
    if pwv_rv.provenance is Provenance.DEFAULT and profile in PROFILE_PWV_CM:
        profile_pwv = PROFILE_PWV_CM[profile]
        if profile_pwv != pwv_cm:
            logger.info(
                "atmosphere.precipitable_water_cm left at default; using the "
                "%s profile's standard water column %.2f cm (Gap 57). Set "
                "precipitable_water_cm explicitly to override.",
                profile,
                profile_pwv,
            )
        pwv_cm = profile_pwv

    return SimpleAtmosphere(
        visibility_km=params.get("atmosphere.visibility_km"),
        aerosol_type=params.get("atmosphere.aerosol_type"),
        precipitable_water_cm=pwv_cm,
        standard_atmosphere=profile,
    )


def _build_tabulated(params: ParameterSet) -> object:
    """Construct a TabulatedAtmosphere from parameters (reads NPZ/CSV)."""
    from radiant.atmosphere.tabulated import TabulatedAtmosphere

    tau_file = params.get("atmosphere.tabulated_transmittance_file")
    lpath_file = params.get("atmosphere.tabulated_path_radiance_file")
    ldown_file = params.get("atmosphere.tabulated_downwelling_file")

    if not tau_file or not lpath_file:
        raise ValueError(
            "build_atmosphere_model: model='tabulated' requires "
            "atmosphere.tabulated_transmittance_file and "
            "atmosphere.tabulated_path_radiance_file to be set."
        )

    # Detect format by extension.
    if str(tau_file).endswith(".npz"):
        return TabulatedAtmosphere.from_npz(tau_file)
    return TabulatedAtmosphere.from_csv(
        tau_file,
        lpath_file,
        ldown_file if ldown_file else None,
    )


def _build_modtran(params: ParameterSet) -> object:
    """Construct a ModtranAtmosphere from parameters (no file I/O here)."""
    from radiant.atmosphere.modtran import ModtranAtmosphere, ModtranConfig

    config = ModtranConfig(
        binary_path=Path(params.get("atmosphere.modtran.binary_path")),
        cache_dir=Path(
            str(params.get("atmosphere.modtran.cache_dir")).replace(
                "~",
                str(Path.home()),
            )
        ),
        allow_fallback=params.get("atmosphere.modtran.allow_fallback"),
        atmosphere_profile=params.get("atmosphere.modtran.atmosphere_profile"),
        aerosol_model=params.get("atmosphere.modtran.aerosol_model"),
        h2o_scale=params.get("atmosphere.modtran.h2o_scale"),
        o3_scale=params.get("atmosphere.modtran.o3_scale"),
        spectral_resolution_cm1=params.get("atmosphere.modtran.spectral_resolution_cm1"),
    )
    return ModtranAtmosphere(config)


def _build_interpolated(params: ParameterSet) -> object:
    """Construct an InterpolatedAtmosphere from a data directory.

    The data directory must contain NPZ files, each with keys
    ``wavelength_um``, ``transmittance``, ``path_radiance``, and
    optionally ``atm_emission_down``.  Each file must also contain
    a ``geometry`` key with a JSON-encoded dict of coordinate
    values.
    """
    from radiant.atmosphere.interpolated import (
        GeometryPoint,
        InterpolatedAtmosphere,
    )
    from radiant.atmosphere.tabulated import TabulatedAtmosphere

    data_dir = params.get("atmosphere.interpolated_data_dir")
    if not data_dir:
        raise ValueError(
            "build_atmosphere_model: model='interpolated' requires "
            "atmosphere.interpolated_data_dir to be set."
        )

    axes_str: str = params.get("atmosphere.interpolation_axes")
    axes = [a.strip() for a in axes_str.split(",")]
    method: str = params.get("atmosphere.interpolation_method")

    data_path = Path(data_dir)
    if not data_path.exists():
        raise FileNotFoundError(
            f"build_atmosphere_model: interpolated data directory not found: {data_path}."
        )

    npz_files = sorted(data_path.glob("*.npz"))
    if len(npz_files) < 2:
        raise ValueError(
            f"build_atmosphere_model: interpolated data directory {data_path} "
            f"must contain at least 2 NPZ files, found {len(npz_files)}."
        )

    points: list[GeometryPoint] = []
    for npz_file in npz_files:
        data = np.load(npz_file, allow_pickle=True)

        if "geometry" not in data:
            raise ValueError(
                f"build_atmosphere_model: NPZ file {npz_file} is missing a "
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


__all__ = ["FILE_BACKED_MODELS", "build_atmosphere_model"]
