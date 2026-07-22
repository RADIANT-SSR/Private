"""Pre-chain construction of the configured atmosphere model.

Rule 6: stages do not read files — all file I/O happens before chain
execution. This module owns the params → atmosphere-model resolution,
including the file reads needed by the ``tabulated`` and
``interpolated`` models. The API layer (``RadiantSession.run``) calls
:func:`build_atmosphere_model` before the chain starts and injects the
result via ``stage_outputs["atmosphere_config"]["model"]``;
``AtmosphereStage`` consumes the injected model.

The ``modtran`` model has two flavors: with
``atmosphere.modtran.tape7_path`` set, the tape7 file is parsed HERE
(pre-chain, Rule 6) into a ``Tape7Import`` and the model never touches
the binary; without it, the model is constructed with no file I/O and
its ``evaluate()`` invokes the external MODTRAN binary (or its cache)
at chain time, which is inherent to that model, not config-file
reading.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import numpy as np

from radiant.atmosphere.errors import AtmosphereValidationError
from radiant.core.parameters import ParameterSet

logger = logging.getLogger(__name__)

#: Repo-root ``data/atmospheres/`` — the shipped MODTRAN-derived library
#: (same file-relative resolution pattern as ``radiant.data.library``).
_SHIPPED_ATMOSPHERES_DIR = Path(__file__).resolve().parents[3] / "data" / "atmospheres"

#: Shipped library family to use when ``atmosphere.interpolated_data_dir`` is
#: left unset, keyed by the (normalized) ``atmosphere.interpolation_axes``
#: value. Only axes combinations a shipped family actually covers appear here;
#: anything else still requires an explicit data dir.
_SHIPPED_FAMILY_BY_AXES: dict[str, str] = {
    "path_zenith_rad": "us_standard_zenith_fan",
    "sensor_altitude_m,target_altitude_m": "midlat_summer_ladders",
    # Boost expansion families (plan §4.7). The 2-axis key above stays on
    # the 0–29 km ladders (§4.1, no re-baseline); nadir 0–100 km boost
    # coverage is reachable via the off-nadir family (which includes the
    # 0° column) or an explicit interpolated_data_dir.
    "sensor_altitude_m": "midlat_summer_sensor_ladder",
    "sensor_altitude_m,target_altitude_m,path_zenith_rad": "midlat_summer_boost_offnadir",
}

#: Models whose construction ALWAYS requires reading data files. These
#: MUST be built before chain execution (Rule 6); AtmosphereStage refuses
#: to build them inside ``run()``.  ``modtran`` becomes file-backed only
#: when ``atmosphere.modtran.tape7_path`` is set — use
#: :func:`model_requires_prebuild` for the parameter-aware check.
FILE_BACKED_MODELS: frozenset[str] = frozenset({"tabulated", "interpolated"})


def model_requires_prebuild(params: ParameterSet) -> bool:
    """Rule 6: does the selected atmosphere model need file I/O to construct?

    ``tabulated`` and ``interpolated`` always do; ``modtran`` joins them
    only when ``atmosphere.modtran.tape7_path`` is set (the tape7
    file-import flavor).  ``AtmosphereStage`` refuses to build any model
    for which this returns True inside ``run()``.
    """
    model_name: str = params.get("atmosphere.model")
    if model_name in FILE_BACKED_MODELS:
        return True
    if model_name != "modtran":
        return False
    try:
        tape7_path = str(params.get("atmosphere.modtran.tape7_path"))
    except KeyError:
        # Partial-chain fixtures may not register the modtran schema.
        return False
    return bool(tape7_path)


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
        raise AtmosphereValidationError(
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
    """Construct a ModtranAtmosphere from parameters.

    With ``atmosphere.modtran.tape7_path`` set, the tape7 file is parsed
    here — before chain execution (Rule 6) — and the resulting
    ``Tape7Import`` supersedes the binary/cache/fallback path.  Unset,
    no file I/O happens here and the binary flavor is unchanged.
    """
    from radiant.atmosphere.modtran import (
        FluxImport,
        ModtranAtmosphere,
        ModtranConfig,
        Tape7Import,
    )

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

    tape7_path = str(params.get("atmosphere.modtran.tape7_path"))
    tape7_sun_path = str(params.get("atmosphere.modtran.tape7_sun_path"))
    tape7_up_path = str(params.get("atmosphere.modtran.tape7_up_path"))
    flux_path = str(params.get("atmosphere.modtran.flux_path"))
    if tape7_sun_path and not tape7_path:
        raise AtmosphereValidationError(
            "build_atmosphere_model: atmosphere.modtran.tape7_sun_path is set "
            "but atmosphere.modtran.tape7_path is not. The sun-leg file only "
            "supplements a tape7 file import — set tape7_path (the "
            "target→sensor up-leg file) too, or unset tape7_sun_path. The "
            "binary-invocation flavor has no two-leg support yet (CU-011)."
        )
    if tape7_up_path and not tape7_path:
        raise AtmosphereValidationError(
            "build_atmosphere_model: atmosphere.modtran.tape7_up_path is set "
            "but atmosphere.modtran.tape7_path is not. The up-leg file only "
            "supplements a tape7 file import — set tape7_path (the "
            "ground→sensor full-column file the background branch needs) "
            "too, or unset tape7_up_path (Gap 94)."
        )
    if flux_path and not tape7_path:
        raise AtmosphereValidationError(
            "build_atmosphere_model: atmosphere.modtran.flux_path is set "
            "but atmosphere.modtran.tape7_path is not. The flux file only "
            "supplements a tape7 file import — it supplies the downwelling "
            "sky irradiance the tape7 lacks. Set tape7_path too, or unset "
            "flux_path (CU-157; Gap 81)."
        )

    tape7_import = None
    tape7_sun_import = None
    tape7_up_import = None
    flux_import = None
    if tape7_path:
        if not Path(tape7_path).exists():
            raise FileNotFoundError(
                f"atmosphere.modtran.tape7_path: file not found: {tape7_path}. "
                "Check the path, or unset the parameter to use the MODTRAN "
                "binary / cache instead."
            )
        tape7_import = Tape7Import.from_file(tape7_path)
        logger.info(
            "MODTRAN tape7 import: %s (content_key=%s)",
            tape7_path,
            tape7_import.content_key,
        )
        if tape7_sun_path:
            if not Path(tape7_sun_path).exists():
                raise FileNotFoundError(
                    f"atmosphere.modtran.tape7_sun_path: file not found: "
                    f"{tape7_sun_path}. Check the path, or unset the parameter "
                    "to collapse tau_sun onto the up-leg transmittance (with a "
                    "warning) instead."
                )
            tape7_sun_import = Tape7Import.from_file(tape7_sun_path)
            logger.info(
                "MODTRAN tape7 sun-leg import: %s (content_key=%s)",
                tape7_sun_path,
                tape7_sun_import.content_key,
            )
        if tape7_up_path:
            if not Path(tape7_up_path).exists():
                raise FileNotFoundError(
                    f"atmosphere.modtran.tape7_up_path: file not found: "
                    f"{tape7_up_path}. Check the path, or unset the parameter "
                    "(airborne targets are then rejected on the file-import "
                    "path — Gap 94)."
                )
            tape7_up_import = Tape7Import.from_file(tape7_up_path)
            logger.info(
                "MODTRAN tape7 up-leg import: %s (content_key=%s)",
                tape7_up_path,
                tape7_up_import.content_key,
            )
        if flux_path:
            if not Path(flux_path).exists():
                raise FileNotFoundError(
                    f"atmosphere.modtran.flux_path: file not found: "
                    f"{flux_path}. Check the path, or unset the parameter "
                    "(the tape7 import then carries zero downwelling — "
                    "Gap 81)."
                )
            flux_import = FluxImport.from_file(flux_path)
            logger.info(
                "MODTRAN flux import: %s (content_key=%s)",
                flux_path,
                flux_import.content_key,
            )

    return ModtranAtmosphere(
        config,
        tape7_import=tape7_import,
        tape7_sun_import=tape7_sun_import,
        tape7_up_import=tape7_up_import,
        flux_import=flux_import,
    )


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
    axes_str: str = params.get("atmosphere.interpolation_axes")
    axes = [a.strip() for a in axes_str.split(",")]
    method: str = params.get("atmosphere.interpolation_method")

    if not data_dir:
        # Owner request 2026-07-18: selecting the interpolated model with no
        # directory must work out of the box. Default to the shipped library
        # family matching the interpolation axes (mirrors the Gap 57
        # profile→PWV pattern: a loud, logged default; an explicit dir wins).
        family = _SHIPPED_FAMILY_BY_AXES.get(",".join(axes))
        default_dir = _SHIPPED_ATMOSPHERES_DIR / family if family else None
        if family is None or default_dir is None or not default_dir.exists():
            raise AtmosphereValidationError(
                "build_atmosphere_model: model='interpolated' requires "
                "atmosphere.interpolated_data_dir to be set — no shipped "
                f"library family covers interpolation_axes='{axes_str}' "
                f"(shipped: {sorted(_SHIPPED_FAMILY_BY_AXES)} under "
                f"{_SHIPPED_ATMOSPHERES_DIR}). Point interpolated_data_dir "
                "at a directory of NPZ runs with 'geometry' coordinates for "
                "those axes."
            )
        logger.info(
            "atmosphere.interpolated_data_dir left unset; using the shipped "
            "%s family (%s) matching interpolation_axes='%s'. Set "
            "interpolated_data_dir to override.",
            family,
            default_dir,
            axes_str,
        )
        data_dir = str(default_dir)

    data_path = Path(data_dir)
    if not data_path.exists():
        raise FileNotFoundError(
            f"build_atmosphere_model: interpolated data directory not found: {data_path}."
        )

    npz_files = sorted(data_path.glob("*.npz"))
    if len(npz_files) < 2:
        # A library ROOT (e.g. data/atmospheres/) keeps its runs one level down
        # in family folders — the natural directory to pick in a file browser
        # (owner bug 2026-07-18). If the family matching the interpolation axes
        # is a direct child with runs, descend into it; otherwise fail with the
        # family folders that were found so the fix is one click away.
        family = _SHIPPED_FAMILY_BY_AXES.get(",".join(axes))
        family_dir = data_path / family if family else None
        if family_dir is not None and len(sorted(family_dir.glob("*.npz"))) >= 2:
            logger.info(
                "atmosphere.interpolated_data_dir %s holds no NPZ runs itself; "
                "descending into its %s family (matching "
                "interpolation_axes='%s').",
                data_path,
                family,
                axes_str,
            )
            data_path = family_dir
            npz_files = sorted(data_path.glob("*.npz"))
        else:
            subdirs_with_runs = sorted(
                d.name for d in data_path.iterdir() if d.is_dir() and any(d.glob("*.npz"))
            )
            hint = (
                f" Its subdirectories with NPZ runs: {subdirs_with_runs} — pick "
                "the family folder matching atmosphere.interpolation_axes "
                f"('{axes_str}'), or leave interpolated_data_dir empty to use "
                "the shipped default."
                if subdirs_with_runs
                else ""
            )
            raise AtmosphereValidationError(
                f"build_atmosphere_model: interpolated data directory {data_path} "
                f"must contain at least 2 NPZ files, found {len(npz_files)}.{hint}"
            )

    points: list[GeometryPoint] = []
    for npz_file in npz_files:
        data = np.load(npz_file, allow_pickle=True)

        if "geometry" not in data:
            raise AtmosphereValidationError(
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


__all__ = ["FILE_BACKED_MODELS", "build_atmosphere_model", "model_requires_prebuild"]
