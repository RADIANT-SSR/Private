"""Config-time coverage check for the interpolated atmosphere backend (CU-239).

One computation, one module (Rule 19): this module owns the **shipped-family
catalogue** and the **scene ↔ family coverage rule** for
``atmosphere.model = "interpolated"``.

Why it exists.  The interpolated backend is keyed by
``atmosphere.interpolation_axes`` — a free-text, comma-separated axis list whose
schema default is ``"path_zenith_rad"``.  A scene with ``target_altitude_m > 0``
(the whole reason the MODTRAN target-altitude ladders were built) needs a
``target_altitude_m`` axis, and until CU-239 the mismatch was discovered only
inside :meth:`InterpolatedAtmosphere.evaluate` — five stages into the chain,
which the GUI renders as a crash dialog rather than a config-time message.
The mismatch is knowable the moment the geometry and the axes are both set
(Rule 16: validate before compute), so :func:`check_interpolation_coverage`
runs it at resolve time and the API exposes it as
:meth:`radiant.api.sensor.Sensor.validate_atmosphere_coverage`.

The catalogue is the single authority for which ``(los_direction, axes)``
combinations a shipped family covers: :mod:`radiant.atmosphere.loaders` derives
its default-family dispatch table from :data:`SHIPPED_FAMILIES` (Rule 27 — one
canonical version), and the GUI reaches the same rows through
:func:`radiant.api.shipped_atmosphere_families` so a family picker never has to
re-type them.

Every coverage line names its units explicitly (km, degrees) — the same
operator-facing contract the GUI's display-unit rule enforces.

Profile safety.  Each shipped family bakes in one MODTRAN atmosphere profile
(:attr:`ShippedFamily.profile`, an ``atmosphere.standard_atmosphere`` enum
value).  Recommending a family whose profile differs from the one the operator
explicitly asked for would silently change the atmosphere — so the coverage
error says so in its own sentence, and :func:`profile_change_warning` gives the
GUI the same sentence to show beside a picker entry.  Nothing in this module
mutates a :class:`~radiant.core.parameters.ParameterSet`.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from radiant.atmosphere.errors import AtmosphereCapabilityError, AtmosphereValidationError
from radiant.core.parameters import ParameterSet, Provenance

__all__ = [
    "BUNDLED_ATMOSPHERES_DIR",
    "BUNDLED_FAMILIES",
    "EXPLICIT_DIR_FAMILIES",
    "SHIPPED_FAMILIES",
    "ShippedFamily",
    "check_interpolation_coverage",
    "family_for",
    "normalize_axes",
    "profile_change_warning",
    "recommended_axes",
    "shipped_family_catalogue_text",
]

#: The shipped MODTRAN-derived atmosphere library, bundled inside the package at
#: ``src/radiant/data/tables/atmospheres/`` so a wheel install carries it
#: (parents[1] == the ``radiant`` package root; same relative pattern as
#: ``radiant.data.library``). Rule 30: no repo-root path assumption, no string
#: path concatenation. :mod:`radiant.atmosphere.loaders` imports this rather
#: than re-deriving it (Rule 27 — one canonical version).
BUNDLED_ATMOSPHERES_DIR: Path = (
    Path(__file__).resolve().parents[1] / "data" / "tables" / "atmospheres"
)


@dataclass(frozen=True)
class ShippedFamily:
    """One row of the bundled atmosphere-library catalogue.

    Attributes
    ----------
    name:
        Directory name under ``radiant/data/tables/atmospheres/``.
    los_direction:
        ``"down"`` or ``"up"`` — the direction of the rendered path. An
        up-looking family's radiance product is the *downwelling* column and
        cannot substitute for a down-looking one.
    interpolation_axes:
        The exact string ``atmosphere.interpolation_axes`` must carry to select
        this family. Free-text no longer has to be guessed: this is the value.
    profile:
        The MODTRAN atmosphere profile the runs were rendered with, as an
        ``atmosphere.standard_atmosphere`` enum value.
    coverage:
        Plain-language coverage line, units always explicit.
    explicit_dir_only:
        ``True`` for a bundled family whose ``(direction, axes)`` signature is
        already owned by another family, so no axes string can select it and it
        is reachable **only** through an explicit
        ``atmosphere.interpolated_data_dir`` (ex-CU-296). Such a row is absent
        from the loader's default-dispatch table by construction: it lives in
        :data:`EXPLICIT_DIR_FAMILIES`, never in :data:`SHIPPED_FAMILIES`. A
        caller adopting one MUST write :attr:`bundled_dir` as well as the axes.
    """

    name: str
    los_direction: str
    interpolation_axes: str
    profile: str
    coverage: str
    explicit_dir_only: bool = False

    @property
    def summary(self) -> str:
        """One-line picker label: profile, direction, coverage, and the axes string."""
        return (
            f"{self.name} — {self.coverage} "
            f"[{self.los_direction}-looking, profile '{self.profile}', "
            f"axes '{self.interpolation_axes}']"
        )

    @property
    def bundled_dir(self) -> str:
        """This family's directory inside the packaged library, as a path string.

        The value to write into ``atmosphere.interpolated_data_dir``. Required
        for an :attr:`explicit_dir_only` family and optional for every other one
        (leaving the parameter empty lets the loader's ``(direction, axes)``
        dispatch find the same directory).
        """
        return str(BUNDLED_ATMOSPHERES_DIR / self.name)


#: The bundled MODTRAN-derived interpolation families, one row per
#: ``(los_direction, interpolation_axes)`` combination the loader can default to.
#: Coverage numbers are the node values recorded in the NPZ ``geometry`` dicts
#: (pinned by ``test_interpolation_coverage.py``); prose matches
#: ``radiant/data/tables/atmospheres/MANIFEST.md``.
#:
#: Data, not branches: adding a family is a row here and nowhere else.
#:
#: One shipped directory is deliberately absent — ``midlat_summer_boost_ladder``
#: (nadir, targets 0–100 km, boost expansion plan §4.7). The 2-axis
#: ``sensor_altitude_m,target_altitude_m`` key stays on the 0–29 km
#: ``midlat_summer_ladders`` (§4.1, no re-baseline), so nadir 0–100 km coverage is
#: reached either through the 3-axis off-nadir family (which carries the 0-degree
#: column) or through an explicit ``atmosphere.interpolated_data_dir``. Adding a
#: row *here* would silently re-baseline every existing 2-axis result; it is
#: instead listed in :data:`EXPLICIT_DIR_FAMILIES` so a picker can still offer it
#: by name (ex-CU-296).
SHIPPED_FAMILIES: tuple[ShippedFamily, ...] = (
    ShippedFamily(
        name="us_standard_zenith_fan",
        los_direction="down",
        interpolation_axes="path_zenith_rad",
        profile="us_standard",
        coverage=(
            "ground targets only (target altitude fixed at 0 km), sensor at 100 km, "
            "LOS zenith 0-60 degrees"
        ),
    ),
    ShippedFamily(
        name="midlat_summer_ladders",
        los_direction="down",
        interpolation_axes="sensor_altitude_m,target_altitude_m",
        profile="midlat_summer",
        coverage=(
            "targets 0-29 km, sensor 35 km / 100 km / 40000 km (GEO), nadir only "
            "(LOS zenith 0 degrees)"
        ),
    ),
    ShippedFamily(
        name="midlat_summer_sensor_ladder",
        los_direction="down",
        interpolation_axes="sensor_altitude_m",
        profile="midlat_summer",
        coverage=(
            "ground targets only (target altitude fixed at 0 km), sensor 3-100 km "
            "plus 40000 km (GEO), nadir only (LOS zenith 0 degrees)"
        ),
    ),
    ShippedFamily(
        name="midlat_summer_boost_offnadir",
        los_direction="down",
        interpolation_axes="sensor_altitude_m,target_altitude_m,path_zenith_rad",
        profile="midlat_summer",
        coverage=("targets 0-100 km, sensor 100 km / 40000 km (GEO), LOS zenith 0-60 degrees"),
    ),
    ShippedFamily(
        name="midlat_summer_uplooking_ladder",
        los_direction="up",
        interpolation_axes="target_altitude_m",
        profile="midlat_summer",
        coverage=(
            "ground sensor (0 km) looking up at targets 0-20 km, vertical only "
            "(LOS zenith 0 degrees)"
        ),
    ),
)


#: Bundled families that **no** ``(direction, axes)`` key can select, because
#: another family already owns their signature. They are reachable only through an
#: explicit ``atmosphere.interpolated_data_dir`` (:attr:`ShippedFamily.bundled_dir`),
#: and they are deliberately kept out of :data:`SHIPPED_FAMILIES` so the loader's
#: derived default-dispatch table, the coverage refusals, and every existing
#: 2-axis result stay exactly as they are.
#:
#: ``midlat_summer_boost_ladder`` is the whole list today: 24 committed MODTRAN
#: runs (nadir, targets 0–100 km) that shipped in 2026-07 with no discoverable
#: route (ex-CU-296). Publishing the row here is what lets the GUI family picker
#: offer it *by name* and write the directory for the operator.
EXPLICIT_DIR_FAMILIES: tuple[ShippedFamily, ...] = (
    ShippedFamily(
        name="midlat_summer_boost_ladder",
        los_direction="down",
        interpolation_axes="sensor_altitude_m,target_altitude_m",
        profile="midlat_summer",
        coverage=(
            "targets 0-100 km (12 rungs through the boost band), sensor 100 km / "
            "40000 km (GEO), nadir only (LOS zenith 0 degrees)"
        ),
        explicit_dir_only=True,
    ),
)

#: Every bundled family, default-dispatch rows first — the catalogue a picker
#: enumerates. :func:`family_for` and the loader's dispatch table deliberately
#: read :data:`SHIPPED_FAMILIES` instead, because only those rows are selectable
#: by axes alone.
BUNDLED_FAMILIES: tuple[ShippedFamily, ...] = SHIPPED_FAMILIES + EXPLICIT_DIR_FAMILIES


def normalize_axes(axes_str: str) -> str:
    """Canonical form of an ``atmosphere.interpolation_axes`` value.

    Strips whitespace around each comma-separated axis name and preserves
    order (the axis order is part of the family key, not incidental).
    """
    return ",".join(a.strip() for a in axes_str.split(","))


def family_for(los_direction: str, axes_str: str) -> ShippedFamily | None:
    """The shipped family covering ``(los_direction, axes)``, or ``None``."""
    normalized = normalize_axes(axes_str)
    for family in SHIPPED_FAMILIES:
        if family.los_direction == los_direction and family.interpolation_axes == normalized:
            return family
    return None


def shipped_family_catalogue_text() -> str:
    """Human-readable list of every shipped ``(direction, axes)`` combination."""
    return ", ".join(
        f"{family.los_direction}-looking axes='{family.interpolation_axes}' → {family.name}"
        for family in sorted(
            SHIPPED_FAMILIES, key=lambda f: (f.los_direction, f.interpolation_axes)
        )
    )


def recommended_axes(los_direction: str, h_tgt_m: float, theta_o_rad: float) -> str | None:
    """The ``interpolation_axes`` string a shipped family covers for this scene.

    Scene-aware family selection (CU-239 layer 2), derived rather than guessed:

    * up-looking ⇒ ``target_altitude_m`` (the only up-looking family shipped);
    * down-looking with an above-ground target ⇒ needs a ``target_altitude_m``
      axis; off-nadir (LOS zenith > 0) additionally needs ``path_zenith_rad``,
      so the 3-axis boost family is the recommendation there and the 2-axis
      nadir ladders otherwise;
    * down-looking at a ground target ⇒ ``path_zenith_rad`` off-nadir (the
      zenith fan), ``sensor_altitude_m`` at nadir (the sensor ladder).

    Returns ``None`` for a level LOS, which no shipped family covers. This is a
    *recommendation*: nothing here writes a parameter, because adopting a
    family can change the atmosphere profile (see
    :func:`profile_change_warning`).
    """
    if los_direction == "up":
        return "target_altitude_m"
    if los_direction != "down":
        return None
    off_nadir = theta_o_rad > 0.0
    if h_tgt_m > 0.0:
        return (
            "sensor_altitude_m,target_altitude_m,path_zenith_rad"
            if off_nadir
            else "sensor_altitude_m,target_altitude_m"
        )
    return "path_zenith_rad" if off_nadir else "sensor_altitude_m"


def profile_change_warning(params: ParameterSet, family: ShippedFamily) -> str | None:
    """Warn text if adopting ``family`` would change the operator's profile.

    ``None`` when the operator never set ``atmosphere.standard_atmosphere`` (so
    there is no explicit request to contradict) or when it already matches the
    family's rendered profile. Non-``None`` is a caller-surfaced message — this
    function never mutates and never suppresses.
    """
    if not _is_user_set(params, "atmosphere.standard_atmosphere"):
        return None
    requested = _value_of(params, "atmosphere.standard_atmosphere")
    if requested is None or str(requested) == family.profile:
        return None
    return (
        f"The shipped '{family.name}' family was rendered with the "
        f"'{family.profile}' atmosphere profile, but "
        f"atmosphere.standard_atmosphere = '{requested}' was requested. "
        "Adopting this family changes the atmosphere profile of the run. Use an "
        "explicit atmosphere.interpolated_data_dir rendered with "
        f"'{requested}' to keep the requested profile."
    )


def _is_user_set(params: ParameterSet, name: str) -> bool:
    """True iff the user chose a value for ``name`` (non-DEFAULT provenance).

    Same dual-view read as :func:`radiant.source.target_spec._is_user_set`
    (CU-244): a resolved set answers from provenance, an unresolved set from the
    explicit-inputs snapshot, so the seam runs on a half-entered config.
    """
    try:
        if params.is_resolved:
            return params.get_resolved(name).provenance is not Provenance.DEFAULT
    except KeyError:
        return False
    return name in params.inputs()


def _value_of(params: ParameterSet, name: str) -> object | None:
    """The parameter's value on either view (``None`` if unset or unregistered)."""
    try:
        if params.is_resolved:
            return params.get_resolved(name).value
    except KeyError:
        return None
    return params.inputs().get(name)


def _scene(params: ParameterSet) -> tuple[float, float, float] | None:
    """``(h_sensor_m, h_tgt_m, theta_o_rad)`` for the configured scene.

    ``None`` when the geometry schema is not registered (partial-chain
    fixtures) or the altitudes are not yet resolvable — the coverage check is
    then a no-op, mirroring :func:`radiant.atmosphere.loaders._scene_los_direction`'s
    handling of the same situation. A missing ``path_zenith_rad`` reads as
    nadir (0 rad), its schema default.
    """
    try:
        h_sensor = float(params.get("geometry.sensor_altitude_m"))
        h_tgt = float(params.get("geometry.target_altitude_m"))
    except (KeyError, TypeError, ValueError):
        return None
    try:
        theta_o = float(params.get("geometry.path_zenith_rad"))
    except (KeyError, TypeError, ValueError):
        theta_o = 0.0
    return h_sensor, h_tgt, theta_o


def _los_direction(h_sensor_m: float, h_tgt_m: float) -> str:
    """Pre-chain mirror of ``LineOfSightGeometry.los_direction`` (see loaders)."""
    if h_sensor_m > h_tgt_m:
        return "down"
    if h_sensor_m < h_tgt_m:
        return "up"
    return "level"


def check_interpolation_coverage(params: ParameterSet) -> None:
    """Raise if the configured scene is outside the selected family's axes.

    The resolve-time seam for the interpolated backend (CU-239). Two rules,
    both knowable before any physics runs:

    1. **Target-altitude axis** — a down-looking scene with
       ``geometry.target_altitude_m > 0`` needs ``target_altitude_m`` among
       ``atmosphere.interpolation_axes``. One column cannot supply both the
       target→sensor leg and the ground→sensor full column the background
       branch needs (Gap 94). This is the same refusal
       :meth:`InterpolatedAtmosphere.evaluate` raises, moved to the door and
       extended with the exact axes string to use plus any profile-change
       caveat.
    2. **Default-family reachability** — when
       ``atmosphere.interpolated_data_dir`` is left empty, the
       ``(los_direction, axes)`` pair must name a shipped family. Otherwise
       the loader has no directory to fall back to.

    No-op for every ``atmosphere.model`` other than ``"interpolated"``, and for
    a config whose geometry altitudes are not registered.

    Raises
    ------
    radiant.atmosphere.errors.AtmosphereCapabilityError
        Rule 1 — the axes cannot serve the scene's target altitude.
    radiant.atmosphere.errors.AtmosphereValidationError
        Rule 2 — no shipped family covers the pair and no directory was given.
    """
    try:
        model = str(params.get("atmosphere.model"))
    except KeyError:
        return
    if model != "interpolated":
        return

    scene = _scene(params)
    if scene is None:
        return
    h_sensor_m, h_tgt_m, theta_o_rad = scene
    direction = _los_direction(h_sensor_m, h_tgt_m)

    axes_str = normalize_axes(str(params.get("atmosphere.interpolation_axes")))
    axes = axes_str.split(",")
    data_dir = str(params.get("atmosphere.interpolated_data_dir") or "")

    if direction == "down" and h_tgt_m > 0.0 and "target_altitude_m" not in axes:
        suggested = recommended_axes(direction, h_tgt_m, theta_o_rad)
        family = family_for(direction, suggested) if suggested else None
        remedy = (
            f"Set atmosphere.interpolation_axes = '{suggested}'"
            if suggested
            else "Add 'target_altitude_m' to atmosphere.interpolation_axes"
        )
        if family is not None and not data_dir:
            remedy += f", which selects the shipped '{family.name}' family ({family.coverage})"
            caveat = profile_change_warning(params, family)
            if caveat:
                remedy += f". {caveat}"
        remedy += (
            ". Or point atmosphere.interpolated_data_dir at a grid carrying a "
            "target-altitude axis, or use atmosphere.model = 'simple'."
        )
        raise AtmosphereCapabilityError(
            what=(
                f"atmosphere.model='interpolated' with "
                f"geometry.target_altitude_m = {h_tgt_m} m > 0 needs a "
                "'target_altitude_m' interpolation axis, but "
                f"atmosphere.interpolation_axes = '{axes_str}'"
            ),
            why=(
                "A grid without a target-altitude axis holds only the full "
                "(target at 0 m) column, and one column cannot supply both the "
                "target→sensor leg (tau_up) and the ground→sensor full column "
                "(tau_full_up) the background branch needs (Gap 94)."
            ),
            action=remedy,
            context={
                "target_altitude_m": h_tgt_m,
                "axes": tuple(axes),
                "suggested_axes": suggested,
                "suggested_family": None if family is None else family.name,
            },
        )

    if not data_dir and family_for(direction, axes_str) is None:
        suggested = recommended_axes(direction, h_tgt_m, theta_o_rad)
        remedy = (
            f"Set atmosphere.interpolation_axes = '{suggested}' for this scene, or "
            if suggested
            else ""
        )
        # AtmosphereValidationError is the plain RadiantError/ValueError form
        # (no what/why/action constructor), so the three parts are formatted
        # here in the same "… | Why: … | Action: …" shape the structured errors
        # render, keeping one error grammar across the module.
        raise AtmosphereValidationError(
            "atmosphere.model='interpolated' with an empty "
            "atmosphere.interpolated_data_dir needs a shipped library family, "
            f"and none covers a {direction}-looking scene with "
            f"atmosphere.interpolation_axes = '{axes_str}'"
            " | Why: The bundled library is a closed set of "
            f"{len(SHIPPED_FAMILIES)} (direction, axes) combinations; an axes "
            "string outside it has no directory to fall back to. Shipped: "
            f"{shipped_family_catalogue_text()}."
            f" | Action: {remedy}point atmosphere.interpolated_data_dir at a "
            "directory of NPZ runs whose 'geometry' coordinates carry these "
            "axes, or use atmosphere.model = 'simple'."
        )
