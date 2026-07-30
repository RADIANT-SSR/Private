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
from typing import TYPE_CHECKING, Any

import numpy as np

from radiant.atmosphere.errors import AtmosphereValidationError
from radiant.atmosphere.interpolation_coverage import (
    SHIPPED_FAMILIES,
    check_interpolation_coverage,
    shipped_family_catalogue_text,
)
from radiant.core.parameters import ParameterSet

if TYPE_CHECKING:  # type-only: keeps scipy out of this module's import cost
    from radiant.atmosphere.interpolated import GeometryPoint

logger = logging.getLogger(__name__)

#: The shipped MODTRAN-derived atmosphere library, bundled inside the package at
#: ``src/radiant/data/tables/atmospheres/`` so a wheel install carries it
#: (parents[1] == ``radiant`` package root; same relative pattern as
#: ``radiant.data.library``). Rule 30: no repo-root path assumption.
_SHIPPED_ATMOSPHERES_DIR = Path(__file__).resolve().parents[1] / "data" / "tables" / "atmospheres"

#: Shipped library family to use when ``atmosphere.interpolated_data_dir`` is
#: left unset, keyed by ``(los_direction, normalized interpolation_axes)``.
#:
#: The axes string alone stopped being a sufficient key at
#: Geometry-Flexibility Phase 2 (GF-10): an up-looking family and a
#: down-looking family can share an axes signature while carrying different
#: physical products (upwelling vs downwelling path radiance), so the LOS
#: direction is part of the key. Only combinations a shipped family actually
#: covers appear here; anything else still requires an explicit data dir and
#: raises the no-family error naming everything that IS shipped.
#:
#: Data, not branches (guardrail G3 in spirit): adding a family is a row — but
#: since CU-239 that row lives in
#: :data:`radiant.atmosphere.interpolation_coverage.SHIPPED_FAMILIES`, which
#: also carries the operator-facing coverage prose the GUI picker and the
#: config-time coverage check read. This dispatch table is *derived* from it so
#: there is exactly one authority (Rule 27).
_SHIPPED_FAMILY_BY_DIRECTION_AND_AXES: dict[tuple[str, str], str] = {
    (family.los_direction, family.interpolation_axes): family.name for family in SHIPPED_FAMILIES
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

    return _build_simple(params)


def _build_simple(params: ParameterSet) -> Any:
    """Construct the parametric :class:`SimpleAtmosphere` from *params*.

    Extracted from :func:`build_atmosphere_model` unchanged (CU-226) so the
    up-looking interpolated family can carry it as its companion for the legs
    a one-direction MODTRAN column family cannot express — see
    :func:`_build_interpolated`.  Same construction, same Gap-57 PWV default,
    same log line: ``atmosphere.model='simple'`` is byte-for-byte unaffected.
    """
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


def _scene_los_direction(params: ParameterSet) -> str:
    """Pre-chain mirror of :attr:`LineOfSightGeometry.los_direction`.

    The shipped-family default must be picked *before* the chain runs (Rule 6:
    all file I/O happens here), so the LOS object that owns the authoritative
    derivation does not exist yet.  The rule is reproduced from the same two
    altitudes the geometry stage uses, and
    ``test_loaders.py::test_direction_matches_line_of_sight_geometry`` pins the
    two together so this copy cannot drift (guardrail G2's spirit: one rule,
    even where it must be evaluated in two places).

    Falls back to ``"down"`` — the historical behaviour and the only direction
    that existed before Phase 2 — when the geometry schema is not registered
    (partial-chain fixtures), mirroring
    :func:`model_requires_prebuild`'s handling of the same situation.
    """
    try:
        h_sensor = float(params.get("geometry.sensor_altitude_m"))
        h_tgt = float(params.get("geometry.target_altitude_m"))
    except KeyError:
        logger.debug(
            "geometry altitudes are not registered; assuming a down-looking "
            "scene for the shipped-atmosphere-family default."
        )
        return "down"
    if h_sensor > h_tgt:
        return "down"
    if h_sensor < h_tgt:
        return "up"
    return "level"


def _shipped_family_catalogue() -> str:
    """Human-readable list of every shipped ``(direction, axes)`` combination.

    Thin alias kept for the existing call sites; the text is owned by
    :func:`radiant.atmosphere.interpolation_coverage.shipped_family_catalogue_text`
    (CU-239 — one authority for the catalogue).
    """
    return shipped_family_catalogue_text()


def _npz_family_direction(npz_files: list[Path]) -> str:
    """Read the self-describing direction marker off a family's NPZ files.

    Files written before Geometry-Flexibility Phase 2 carry no marker and are
    down-looking by construction, so a missing key reads as ``"down"`` and
    every pre-existing family loads through exactly the path it always did.
    A directory mixing directions is refused: the two carry different
    physical radiance products and cannot share one interpolator.
    """
    from radiant.atmosphere.interpolated import FAMILY_DIRECTION_KEY, FAMILY_DIRECTIONS

    seen: set[str] = set()
    for npz_file in npz_files:
        with np.load(npz_file, allow_pickle=True) as data:
            # A file written before GF-10 carries no marker and is
            # down-looking by construction.
            has_marker = FAMILY_DIRECTION_KEY in data.files
            marker = str(data[FAMILY_DIRECTION_KEY]) if has_marker else "down"
        seen.add(marker)
    if len(seen) > 1:
        raise AtmosphereValidationError(
            "build_atmosphere_model: the interpolated data directory mixes "
            f"run directions {sorted(seen)}. An up-looking family's radiance "
            "product is the DOWNWELLING path radiance and a down-looking "
            "family's is the UPWELLING one — different quantities that cannot "
            "share one interpolation grid. Split the directory by direction."
        )
    direction = seen.pop()
    if direction not in FAMILY_DIRECTIONS:
        raise AtmosphereValidationError(
            f"build_atmosphere_model: NPZ direction marker '{direction}' is not "
            f"recognised. Expected one of {sorted(FAMILY_DIRECTIONS)} under the "
            f"'{FAMILY_DIRECTION_KEY}' key."
        )
    return direction


def _uplooking_geometry_point(npz_file: Path, coords: dict[str, float]) -> GeometryPoint:
    """Build a :class:`GeometryPoint` from an up-looking family NPZ.

    The downwelling product is stored under
    :data:`~radiant.atmosphere.interpolated.UPLOOKING_RADIANCE_KEY`, never
    under ``path_radiance`` — a down-looking reader therefore fails on a
    missing key instead of silently reading the wrong-direction product.
    Inside the interpolator the array rides in the ``path_radiance`` slot;
    it is only ever published through
    :meth:`InterpolatedAtmosphere.uplooking_column_product`, which names it
    ``L_toward_lower``, and :meth:`InterpolatedAtmosphere.evaluate` refuses
    an up-looking family outright.
    """
    from radiant.atmosphere.interpolated import UPLOOKING_RADIANCE_KEY, GeometryPoint
    from radiant.core.spectral import SpectralData

    with np.load(npz_file, allow_pickle=True) as data:
        missing = [
            k for k in ("wavelength_um", "transmittance", UPLOOKING_RADIANCE_KEY) if k not in data
        ]
        if missing:
            raise AtmosphereValidationError(
                f"build_atmosphere_model: up-looking NPZ {npz_file} is missing "
                f"required key(s) {missing}. An up-looking run family stores "
                f"'wavelength_um', 'transmittance' and '{UPLOOKING_RADIANCE_KEY}' "
                "(the downwelling path radiance). Regenerate it with "
                "scripts/build_atmosphere_library.py."
            )
        wl = np.asarray(data["wavelength_um"], dtype=np.float64)
        tau = np.asarray(data["transmittance"], dtype=np.float64)
        l_down = np.asarray(data[UPLOOKING_RADIANCE_KEY], dtype=np.float64)

    source = f"Up-looking library NPZ: {npz_file}"
    provenance = {"model": "interpolated", "npz_file": str(npz_file), "los_direction": "up"}
    return GeometryPoint(
        coordinates=coords,
        transmittance=SpectralData(
            name="atm.transmittance.uplooking",
            wavelength_um=wl.copy(),
            values=tau,
            unit="",
            source=source,
            source_parameters=provenance,
        ),
        path_radiance=SpectralData(
            name="atm.path_radiance_toward_lower.uplooking",
            wavelength_um=wl.copy(),
            values=l_down,
            unit="W/m²/sr/µm",
            source=source,
            source_parameters=provenance,
        ),
        # An up-looking family carries no separate hemispheric downwelling
        # term: its own product IS the downwelling radiance along the LOS.
        # Zeros here are never read — evaluate() refuses up-looking families.
        atm_emission_down=SpectralData(
            name="atm.emission_down.not_carried_by_uplooking_family",
            wavelength_um=wl.copy(),
            values=np.zeros_like(wl),
            unit="W/m²/sr/µm",
            source=source,
            source_parameters=provenance,
        ),
    )


def _build_interpolated(params: ParameterSet) -> object:
    """Construct an InterpolatedAtmosphere from a data directory.

    The data directory must contain NPZ files, each with keys
    ``wavelength_um``, ``transmittance``, ``path_radiance``, and
    optionally ``atm_emission_down``.  Each file must also contain
    a ``geometry`` key with a JSON-encoded dict of coordinate
    values.

    An **up-looking** run family (marked ``los_direction = "up"``) stores its
    downwelling product under ``path_radiance_toward_lower`` instead of
    ``path_radiance`` and carries no ``atm_emission_down``; the loader reads
    it through :func:`_uplooking_geometry_point` and tags the resulting model
    so its down-looking entry point stays closed (GF-10).
    """
    from radiant.atmosphere.interpolated import (
        GeometryPoint,
        InterpolatedAtmosphere,
    )
    from radiant.atmosphere.tabulated import TabulatedAtmosphere

    # CU-239: the scene ↔ axes coverage rules are knowable here, before any
    # NPZ is opened, so the operator meets one actionable config-time refusal
    # instead of an AtmosphereCapabilityError five stages into the chain. The
    # evaluate-time checks stay as defence in depth.
    check_interpolation_coverage(params)

    data_dir = params.get("atmosphere.interpolated_data_dir")
    axes_str: str = params.get("atmosphere.interpolation_axes")
    axes = [a.strip() for a in axes_str.split(",")]
    method: str = params.get("atmosphere.interpolation_method")

    scene_direction = _scene_los_direction(params)
    family_key = (scene_direction, ",".join(axes))

    if not data_dir:
        # Owner request 2026-07-18: selecting the interpolated model with no
        # directory must work out of the box. Default to the shipped library
        # family matching the interpolation axes (mirrors the Gap 57
        # profile→PWV pattern: a loud, logged default; an explicit dir wins).
        # Since GF-10 the key is (LOS direction, axes) — see the dispatch table.
        family = _SHIPPED_FAMILY_BY_DIRECTION_AND_AXES.get(family_key)
        default_dir = _SHIPPED_ATMOSPHERES_DIR / family if family else None
        if family is None or default_dir is None or not default_dir.exists():
            raise AtmosphereValidationError(
                "build_atmosphere_model: model='interpolated' requires "
                "atmosphere.interpolated_data_dir to be set — no shipped "
                f"library family covers a {scene_direction}-looking scene with "
                f"interpolation_axes='{axes_str}' (shipped: "
                f"{_shipped_family_catalogue()}; all under "
                f"{_SHIPPED_ATMOSPHERES_DIR}). Point interpolated_data_dir "
                "at a directory of NPZ runs with 'geometry' coordinates for "
                "those axes, change atmosphere.interpolation_axes to a shipped "
                "combination, or use atmosphere.model='simple'."
            )
        logger.info(
            "atmosphere.interpolated_data_dir left unset; using the shipped "
            "%s family (%s) matching %s-looking interpolation_axes='%s'. Set "
            "interpolated_data_dir to override.",
            family,
            default_dir,
            scene_direction,
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
        family = _SHIPPED_FAMILY_BY_DIRECTION_AND_AXES.get(family_key)
        family_dir = data_path / family if family else None
        if family_dir is not None and len(sorted(family_dir.glob("*.npz"))) >= 2:
            logger.info(
                "atmosphere.interpolated_data_dir %s holds no NPZ runs itself; "
                "descending into its %s family (matching %s-looking "
                "interpolation_axes='%s').",
                data_path,
                family,
                scene_direction,
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
                f"('{axes_str}') for this {scene_direction}-looking scene, or "
                "leave interpolated_data_dir empty to use the shipped default."
                if subdirs_with_runs
                else ""
            )
            raise AtmosphereValidationError(
                f"build_atmosphere_model: interpolated data directory {data_path} "
                f"must contain at least 2 NPZ files, found {len(npz_files)}.{hint}"
            )

    family_direction = _npz_family_direction(npz_files)

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

        if family_direction == "up":
            points.append(_uplooking_geometry_point(npz_file, coords))
            continue

        tab = TabulatedAtmosphere.from_npz(npz_file)
        points.append(
            GeometryPoint(
                coordinates=coords,
                transmittance=tab.transmittance_data,
                path_radiance=tab.path_radiance_data,
                atm_emission_down=tab.atm_emission_down_data,
            )
        )

    # CU-226: an up-looking family is a ONE-LEG data set — the sensor→target
    # column and nothing else.  The up-looking topology also needs the target's
    # illumination (the solar column and sky hemisphere ABOVE the target) and
    # the sky along the LOS continuation out to h_atm_top, neither of which any
    # rung of the ladder contains.  The companion supplies exactly those legs;
    # it is built here rather than in the stage because Rule 6 keeps model
    # construction pre-chain.  Down-looking families get no companion — their
    # ``evaluate`` serves the whole bundle, and nothing changes for them.
    companion = _build_simple(params) if family_direction == "up" else None
    return InterpolatedAtmosphere(
        points,
        axes,
        method,
        family_direction=family_direction,
        uplooking_companion=companion,
    )


def build_cn2_profile(params: ParameterSet) -> object | None:
    """Construct the tabulated Cn² profile named by the parameters, if any.

    Rule 6: the ``atmosphere.cn2_tabulated_file`` CSV is read **here**,
    before chain execution, and the resulting
    :class:`~radiant.atmosphere.cn2_tabulated.TabulatedCn2Profile` is injected
    at ``stage_outputs["atmosphere_config"]["cn2_profile"]`` — the same route
    the atmosphere model itself takes.

    Returns ``None`` for every selector other than ``"tabulated"`` (the
    analytic Hufnagel-Valley profile needs no file, and ``"direct"`` needs no
    profile at all).

    File format
    -----------
    Two comma-separated columns, ``altitude_m,cn2_m^-2/3``, ascending in
    altitude.  Blank lines and ``#`` comments are ignored, and a single
    non-numeric header row is accepted.
    """
    try:
        profile_name: str = str(params.get("atmosphere.cn2_profile"))
    except (KeyError, TypeError):
        # Partial-chain fixtures may not register the turbulence schema.
        return None
    if profile_name != "tabulated":
        return None

    from radiant.atmosphere.cn2_tabulated import TabulatedCn2Profile

    raw_path = str(params.get("atmosphere.cn2_tabulated_file"))
    if not raw_path:
        raise AtmosphereValidationError(
            "build_cn2_profile: atmosphere.cn2_profile = 'tabulated' but "
            "atmosphere.cn2_tabulated_file is empty. Point it at a two-column "
            "'altitude_m,cn2_m^-2/3' CSV, or choose another "
            "atmosphere.cn2_profile ('hufnagel_valley' needs no file, 'direct' "
            "uses atmosphere.r0_m)."
        )
    path = Path(raw_path)
    if not path.exists():
        raise FileNotFoundError(
            f"atmosphere.cn2_tabulated_file: file not found: {path}. Check the "
            "path, or choose another atmosphere.cn2_profile."
        )

    altitudes: list[float] = []
    cn2_values: list[float] = []
    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        text = line.split("#", 1)[0].strip()
        if not text:
            continue
        fields = [f.strip() for f in text.split(",")]
        if len(fields) < 2:
            raise AtmosphereValidationError(
                f"atmosphere.cn2_tabulated_file {path}: line {lineno} has "
                f"{len(fields)} field(s); expected two comma-separated columns "
                "'altitude_m,cn2_m^-2/3'."
            )
        try:
            altitudes.append(float(fields[0]))
            cn2_values.append(float(fields[1]))
        except ValueError:
            if lineno == 1 or not altitudes:
                continue  # a header row
            raise AtmosphereValidationError(
                f"atmosphere.cn2_tabulated_file {path}: line {lineno} "
                f"({text!r}) is not a numeric 'altitude_m,cn2_m^-2/3' pair."
            ) from None

    if not altitudes:
        raise AtmosphereValidationError(
            f"atmosphere.cn2_tabulated_file {path}: no numeric rows found. The "
            "file must hold at least two 'altitude_m,cn2_m^-2/3' rows."
        )

    profile = TabulatedCn2Profile(
        altitude_m=np.asarray(altitudes, dtype=np.float64),
        cn2_m23=np.asarray(cn2_values, dtype=np.float64),
        label=path.name,
    )
    logger.info("Cn² profile loaded: %s", profile.describe())
    return profile


__all__ = [
    "FILE_BACKED_MODELS",
    "build_atmosphere_model",
    "build_cn2_profile",
    "model_requires_prebuild",
]
