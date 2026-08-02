"""Pre-validated bundled-family selection for the interpolated backend (CU-322).

One computation, one module (Rule 19): **given a line of sight, which bundled
interpolation family will the chain actually serve it with — and if none will,
what is the first real gap?**

Why it exists.  :func:`radiant.atmosphere.interpolation_coverage.recommended_axes`
reasons about *axes strings* alone: it answers "which axes does a scene of this
shape need", not "will the family behind those axes accept this query".  Those
are different questions, and the gap between them is what CU-322 measured on the
38 shipped GUI scenarios: the recommendation named a family whose own evaluation
then refused (an up-looking scene at ζ = 29.9° recommended the *vertical-only*
ladder), and it could not name an ``EXPLICIT_DIR_FAMILIES`` row at all, because
no axes string reaches one.  The operator met a sequence of
honest Rule-17 refusals — one per gate — instead of either a working family or
one sentence naming the one thing that is missing.

What this module adds is the **complete query check, before anything is
recommended**.  For each candidate family it reproduces, from the family's own
node geometry, every refusal the chain would raise for this LOS:

* **direction** — an up-looking family's radiance product is the downwelling
  column and can never serve a down-looking scene
  (:meth:`InterpolatedAtmosphere._require_family_direction`);
* **target axis** — a down-looking scene above the surface needs a
  ``target_altitude_m`` axis (Gap 94, :meth:`InterpolatedAtmosphere.evaluate`);
* **exo ceiling** — an up-looking target at or above ``h_atm_top`` needs a
  family whose own runs reach ``h_atm_top``
  (:func:`radiant.atmosphere.uplooking_quantities._refuse_library_backed_exo_target`);
* **LOS zenith** — an axis-carrying family must hold the query in its hull; a
  family rendered at one fixed zenith serves only that zenith
  (:meth:`InterpolatedAtmosphere._require_uplooking_zenith_is_servable`);
* **target altitude** — inside the axis hull, after the vacuum-equivalence clamp
  (:meth:`InterpolatedAtmosphere._vacuum_clamped_target_m`);
* **lower endpoint / sensor altitude** — inside the axis hull, or within the
  1 m tolerance of the family's single rendered lower endpoint
  (:meth:`InterpolatedAtmosphere.uplooking_column_product`).

A **non-axis mismatch beyond the CU-167 tolerances also disqualifies a family
here**, even though the chain only *warns* about it.  A warning is the right
answer for an operator who deliberately pointed at that family; it is the wrong
thing to *recommend*, because the family would silently serve a different
column (the 100 km-rendered zenith fan answering for a 1 m sensor).  The
disqualification is limited to the three path-geometry fields the family key is
about — sensor altitude, target altitude, LOS zenith.  Solar geometry keeps the
CU-167 warning and never blocks a recommendation: every shipped family is
rendered at one solar zenith, so treating it as disqualifying would leave no
family for any scene with a different sun.

Every gap sentence carries its units (m, km, degrees) — the same operator-facing
contract the coverage lines and the GUI display-unit rule enforce.

Thresholds are **imported** from :mod:`radiant.atmosphere.interpolated`, never
restated: this module must refuse exactly what that one refuses, and a second
copy of a tolerance is a divergence waiting to happen (Rule 27).  The bundled
families' node geometry is read from their NPZ ``geometry`` dicts and cached, so
the answer is derived from the shipped data rather than from prose (~16 ms for
the whole library, once per process).
"""

from __future__ import annotations

import json
import logging
import math
from dataclasses import dataclass, field
from functools import cache
from pathlib import Path

import numpy as np

from radiant.atmosphere.errors import (
    COVERAGE_REFUSAL_SURFACE,
    COVERAGE_SURFACE_KEY,
    AtmosphereCapabilityError,
)
from radiant.atmosphere.interpolated import (
    _MAX_ZENITH_RAD,
    _NON_AXIS_ANGLE_TOL_RAD,
    _NON_AXIS_LENGTH_TOL_M,
    _UPLOOKING_FIXED_ZENITH_TOL_RAD,
    _VACUUM_EQUIVALENT_ALTITUDE_M,
)
from radiant.atmosphere.interpolation_coverage import (
    BUNDLED_ATMOSPHERES_DIR,
    BUNDLED_FAMILIES,
    ShippedFamily,
    normalize_axes,
    recommended_axes,
)
from radiant.core.los_geometry import LineOfSightGeometry

logger = logging.getLogger(__name__)

__all__ = [
    "AtmosphereFamilySuggestion",
    "FamilyGap",
    "FamilyNodeGeometry",
    "FamilySuitability",
    "family_node_geometry",
    "family_suitability",
    "select_atmosphere_family",
]

#: Gate order, earliest first.  When no family serves a scene, the reported gap
#: is the one from the candidate that got **furthest** through this sequence —
#: the family that was closest to serving names the one thing that is missing,
#: which is what "the first real gap" means to an operator (CU-322 checklist
#: item 4).  Ties are broken by candidate precedence.
_GATE_DIRECTION: int = 0
_GATE_CAPABILITY: int = 1
_GATE_ZENITH: int = 2
_GATE_TARGET: int = 3
_GATE_SENSOR: int = 4


@dataclass(frozen=True)
class FamilyNodeGeometry:
    """What a bundled family's own NPZ nodes say about the runs it holds.

    Attributes
    ----------
    axes:
        The interpolation axes, in key order.
    bounds:
        ``{axis: (min, max)}`` over the node set, in the coordinates' own units
        (m for altitudes, rad for angles) — the same original-unit hull
        :meth:`InterpolatedAtmosphere.coordinate_bounds` reports and the same one
        its no-extrapolation check tests against.
    fixed:
        ``{field: value}`` for every **non-axis** geometry field the nodes record
        with one constant value — the family's rendered geometry for that
        dimension.  A field that varies across nodes without being an axis (which
        the interpolator's constructor rejects) is omitted rather than guessed.
    n_nodes:
        How many runs the family holds.
    """

    axes: tuple[str, ...]
    bounds: dict[str, tuple[float, float]]
    fixed: dict[str, float]
    n_nodes: int

    @property
    def target_ceiling_m(self) -> float | None:
        """Highest target altitude the family's own runs measure [m MSL].

        The pre-chain mirror of
        :attr:`InterpolatedAtmosphere.uplooking_target_ceiling_m`: the top of the
        target axis's hull when it is an axis, the recorded constant when it is
        not, ``None`` when the family records nothing about its upper endpoint.
        """
        if "target_altitude_m" in self.axes:
            return self.bounds["target_altitude_m"][1]
        return self.fixed.get("target_altitude_m")


@dataclass(frozen=True)
class FamilyGap:
    """The one thing that stops a family serving a scene.

    Attributes
    ----------
    kind:
        Machine-readable gate name — ``"direction"``, ``"target_axis"``,
        ``"exo_ceiling"``, ``"path_zenith"``, ``"target_altitude"``,
        ``"sensor_altitude"``, or ``"library_missing"``.
    gate:
        Position in the gate sequence (see the module constants).  Higher means
        the family got further before it stopped.
    text:
        The operator-facing sentence, units always explicit.
    context:
        The numbers behind the sentence, for a caller that wants to render them
        differently.
    """

    kind: str
    gate: int
    text: str
    context: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class FamilySuitability:
    """Whether one bundled family can serve one line of sight."""

    family: ShippedFamily
    gap: FamilyGap | None

    @property
    def serves(self) -> bool:
        """True when the chain would accept every part of this query."""
        return self.gap is None


@dataclass(frozen=True)
class AtmosphereFamilySuggestion:
    """The pre-validated bundled-family recommendation for one scene (CU-322).

    ``family`` is a family the chain will actually serve — never one it would
    then refuse.  When it is ``None``, ``gap`` names the single closest miss and
    :attr:`advisory_text` renders it as one sentence, so a caller can say what is
    missing instead of replaying every gate's refusal in turn.

    Attributes
    ----------
    family:
        The family to adopt, or ``None`` when the bundled library cannot serve
        this scene.  An ``explicit_dir_only`` row is a legitimate answer: adopting
        it means writing :attr:`ShippedFamily.bundled_dir` into
        ``atmosphere.interpolated_data_dir`` as well as the axes.
    gap:
        The blocking gap when ``family`` is ``None``; ``None`` otherwise.
    considered:
        Every family name evaluated, in the precedence order they were tried.
    los_direction:
        The direction the scene was classified as (``"down"``, ``"up"``, or
        ``"level"``).
    vacuum_path:
        ``True`` for an up-looking or level scene whose sensor already sits at or
        above ``h_atm_top``: there is no medium anywhere along the path, the
        products are identities, and **no backend is consulted at all**
        (:func:`radiant.atmosphere.topology.evaluate_path_topology`).  The scene
        evaluates on the interpolated model, so a family is still named for the
        parameter to carry — but that family's coverage says nothing about this
        scene, and a caller quoting the coverage line must say so.
    """

    family: ShippedFamily | None
    gap: FamilyGap | None
    considered: tuple[str, ...]
    los_direction: str
    vacuum_path: bool = False

    @property
    def serves(self) -> bool:
        """True when a bundled family covers this scene."""
        return self.family is not None

    @property
    def advisory_text(self) -> str | None:
        """The one sentence naming the first real gap, or ``None`` when served."""
        if self.gap is None:
            return None
        return f"No bundled interpolation family serves this scene: {self.gap.text}."

    def advisory_error(self) -> AtmosphereCapabilityError | None:
        """The gap as an actionable, **unraised** error for a message surface.

        The GUI's Messages rail and every other actionable-error surface render
        ``what`` / ``why`` / ``action``, so the advisory is handed over in that
        shape rather than as a bare string.  It is constructed, never raised:
        nothing here refuses a run — the scene may still be evaluated with
        ``atmosphere.model='simple'``, and this is the sentence that says so.
        """
        if self.gap is None:
            return None
        return AtmosphereCapabilityError(
            what=self.advisory_text or "",
            why=(
                "The bundled interpolation library is a closed set of MODTRAN runs. "
                "Every family is rendered at a fixed lower endpoint, over a fixed "
                "span of target altitudes and LOS zenith angles, and the backend "
                "never extrapolates outside the runs it holds (Rule 17) — so a scene "
                "outside every family's span has no measured column to interpolate."
            ),
            action=(
                "Use atmosphere.model='simple' for this scene — it serves any "
                "geometry — or point atmosphere.interpolated_data_dir at a run "
                "family rendered for this geometry."
            ),
            context={
                COVERAGE_SURFACE_KEY: COVERAGE_REFUSAL_SURFACE,
                "gap_kind": self.gap.kind,
                "los_direction": self.los_direction,
                "families_considered": list(self.considered),
                **self.gap.context,
            },
        )


# ---------------------------------------------------------------------------
# Node geometry (read once per family, from the shipped NPZs)
# ---------------------------------------------------------------------------


@cache
def family_node_geometry(name: str) -> FamilyNodeGeometry | None:
    """Node hull and rendered geometry of the bundled family called *name*.

    Reads only each run's ``geometry`` coordinate dict — an NPZ is a zip, so no
    spectrum is decompressed and the whole bundled library costs a few
    milliseconds.  Cached for the process: the packaged library is read-only.

    ``None`` when the family's directory holds no NPZ runs (a stripped install)
    or when a run carries no ``geometry`` key — the caller then declines to
    recommend the family rather than assuming a coverage it cannot verify.
    """
    family = next((f for f in BUNDLED_FAMILIES if f.name == name), None)
    if family is None:
        return None
    directory = Path(family.bundled_dir)
    npz_files = sorted(directory.glob("*.npz"))
    if not npz_files:
        logger.debug("family_node_geometry: %s holds no NPZ runs at %s", name, directory)
        return None

    coords: list[dict[str, float]] = []
    for npz_file in npz_files:
        with np.load(npz_file, allow_pickle=True) as data:
            if "geometry" not in data:
                logger.debug("family_node_geometry: %s has no 'geometry' key", npz_file)
                return None
            raw = data["geometry"]
        parsed = raw.item() if hasattr(raw, "item") else json.loads(str(raw))
        coords.append({str(k): float(v) for k, v in dict(parsed).items()})

    axes = tuple(normalize_axes(family.interpolation_axes).split(","))
    bounds: dict[str, tuple[float, float]] = {}
    for axis in axes:
        if any(axis not in c for c in coords):
            logger.debug("family_node_geometry: %s nodes do not all carry axis %s", name, axis)
            return None
        values = [c[axis] for c in coords]
        bounds[axis] = (min(values), max(values))

    fixed: dict[str, float] = {}
    for name_ in sorted({k for c in coords for k in c}):
        if name_ in axes or any(name_ not in c for c in coords):
            continue
        values = [c[name_] for c in coords]
        if max(values) - min(values) <= 0.0:
            fixed[name_] = values[0]
    return FamilyNodeGeometry(axes=axes, bounds=bounds, fixed=fixed, n_nodes=len(coords))


# ---------------------------------------------------------------------------
# Per-family suitability
# ---------------------------------------------------------------------------


def _km(value_m: float) -> str:
    """Altitude as a unit-bearing string, in whichever unit reads naturally."""
    if abs(value_m) < 1000.0:
        return f"{value_m:.0f} m"
    return f"{value_m / 1000.0:g} km"


def _deg(value_rad: float) -> str:
    """Angle as a unit-bearing string in degrees (the operator-facing unit)."""
    return f"{math.degrees(value_rad):.1f} degrees"


def _hull_gap(
    family: ShippedFamily,
    axis: str,
    query: float,
    bounds: tuple[float, float],
    gate: int,
) -> FamilyGap | None:
    """Gap when *query* falls outside an interpolation axis's node hull."""
    low, high = bounds
    if low - 1e-12 <= query <= high + 1e-12:
        return None
    is_angle = axis.endswith("_rad")
    fmt = _deg if is_angle else _km
    kind = "path_zenith" if is_angle else axis.replace("_m", "")
    side = "below" if query < low else "above"
    return FamilyGap(
        kind=kind,
        gate=gate,
        text=(
            f"'{family.name}' covers {axis.replace('_m', '').replace('_rad', '')} "
            f"{fmt(low)} to {fmt(high)}; this scene asks for {fmt(query)}, "
            f"{side} the family's runs"
        ),
        context={
            "family": family.name,
            "axis": axis,
            "query": query,
            "hull_low": low,
            "hull_high": high,
        },
    )


def _fixed_gap(
    family: ShippedFamily,
    field_name: str,
    query: float,
    rendered: float,
    tol: float,
    gate: int,
) -> FamilyGap | None:
    """Gap when a **non-axis** field departs from the family's rendered value.

    The chain would only warn here (CU-167) and serve the rendered column, so
    this is a *recommendation* gate rather than a refusal mirror — see the module
    docstring.  Two exceptions match the vacuum-equivalence identities the
    backend already applies, and are therefore exact rather than mismatches:
    a sensor above an at-or-above-TOA rendered sensor, and a target above a
    full-column family's ceiling (clamped by the caller before this is reached).
    """
    if abs(query - rendered) <= tol:
        return None
    if (
        field_name == "sensor_altitude_m"
        and rendered >= _VACUUM_EQUIVALENT_ALTITUDE_M
        and query > rendered
    ):
        return None
    is_angle = field_name.endswith("_rad")
    fmt = _deg if is_angle else _km
    kind = "path_zenith" if is_angle else field_name.replace("_m", "")
    what = {
        "sensor_altitude_m": "is rendered from a fixed lower endpoint at",
        "target_altitude_m": "is rendered to a fixed upper endpoint at",
        "path_zenith_rad": "is rendered at a single LOS zenith of",
    }[field_name]
    return FamilyGap(
        kind=kind,
        gate=gate,
        text=(
            f"'{family.name}' {what} {fmt(rendered)} and carries no "
            f"'{field_name}' axis; this scene asks for {fmt(query)}"
        ),
        context={
            "family": family.name,
            "field": field_name,
            "query": query,
            "rendered": rendered,
            "tolerance": tol,
        },
    )


def _tolerance_for(field_name: str, family: ShippedFamily) -> float:
    """The tolerance the chain applies to a non-axis mismatch on *field_name*.

    Altitudes use the CU-167 1 m slack — which is also the hard tolerance
    :meth:`InterpolatedAtmosphere.uplooking_column_product` refuses a mismatched
    lower endpoint at.  LOS zenith uses the CU-167 ~1 degree slack for a
    down-looking family (where the mismatch is a warning) and the up-looking
    families' float-slack 1e-6 rad (where it is a hard refusal).
    """
    if field_name != "path_zenith_rad":
        return _NON_AXIS_LENGTH_TOL_M
    return (
        _UPLOOKING_FIXED_ZENITH_TOL_RAD if family.los_direction == "up" else _NON_AXIS_ANGLE_TOL_RAD
    )


def _check_field(
    family: ShippedFamily,
    nodes: FamilyNodeGeometry,
    field_name: str,
    query: float,
    gate: int,
) -> FamilyGap | None:
    """Hull check when *field_name* is an axis, rendered-value check when it is not."""
    if field_name in nodes.axes:
        return _hull_gap(family, field_name, query, nodes.bounds[field_name], gate)
    rendered = nodes.fixed.get(field_name)
    if rendered is None:
        return None
    return _fixed_gap(family, field_name, query, rendered, _tolerance_for(field_name, family), gate)


def _zenith_beyond_transform(family: ShippedFamily, query_rad: float) -> FamilyGap | None:
    """Gap when the query zenith is where the airmass transform sec(ζ) diverges."""
    if query_rad < _MAX_ZENITH_RAD:
        return None
    return FamilyGap(
        kind="path_zenith",
        gate=_GATE_ZENITH,
        text=(
            f"this scene's LOS zenith is {_deg(query_rad)}, at or beyond the "
            f"{_deg(_MAX_ZENITH_RAD)} horizon limit where the airmass transform "
            "sec(zeta) diverges; no interpolated family can serve it"
        ),
        context={"family": family.name, "query": query_rad, "limit": _MAX_ZENITH_RAD},
    )


def _down_looking_gap(
    family: ShippedFamily,
    nodes: FamilyNodeGeometry,
    los: LineOfSightGeometry,
) -> FamilyGap | None:
    """First gap on the down-looking path (:meth:`InterpolatedAtmosphere.evaluate`)."""
    # A down-looking exo target composes as [ground->target column G] union
    # [vacuum segment V] and the backend is called at the SURFACE target
    # (topology._down_looking_exo), so that is the altitude to check.
    h_tgt_m = 0.0 if los.h_tgt >= los.h_atm_top else float(los.h_tgt)
    theta_o_rad = float(los.theta_o)

    if h_tgt_m > 0.0 and "target_altitude_m" not in nodes.axes:
        return FamilyGap(
            kind="target_axis",
            gate=_GATE_CAPABILITY,
            text=(
                f"'{family.name}' holds only the full ground-to-sensor column and "
                f"carries no 'target_altitude_m' axis; this scene's target is at "
                f"{_km(h_tgt_m)}, which needs both the target-to-sensor leg and the "
                "ground-to-sensor column"
            ),
            context={"family": family.name, "target_altitude_m": h_tgt_m},
        )

    gap = _zenith_beyond_transform(family, theta_o_rad)
    if gap is not None:
        return gap
    gap = _check_field(family, nodes, "path_zenith_rad", theta_o_rad, _GATE_ZENITH)
    if gap is not None:
        return gap
    # evaluate() queries the full column at 0 m as well as the up leg at h_tgt.
    for target_query_m in (0.0, h_tgt_m):
        gap = _check_field(family, nodes, "target_altitude_m", target_query_m, _GATE_TARGET)
        if gap is not None:
            return gap
    if los.h_sensor is None:
        return None
    return _check_field(family, nodes, "sensor_altitude_m", float(los.h_sensor), _GATE_SENSOR)


def _up_looking_gap(
    family: ShippedFamily,
    nodes: FamilyNodeGeometry,
    los: LineOfSightGeometry,
) -> FamilyGap | None:
    """First gap on the up-looking path (``uplooking_column_product`` + exo guard)."""
    h_sensor_m = float(los.h_sensor) if los.h_sensor is not None else 0.0
    h_tgt_m = float(los.h_tgt)
    # zeta_low = pi - theta_o: the zenith of the up-going ray at the sensor,
    # which is the segment's lower endpoint and the coordinate the family is
    # keyed on (uplooking_column_product).
    zeta_low_rad = abs(math.pi - float(los.theta_o))
    ceiling_m = nodes.target_ceiling_m

    if h_tgt_m >= los.h_atm_top and (ceiling_m is None or ceiling_m < los.h_atm_top):
        measured = "nothing" if ceiling_m is None else _km(ceiling_m)
        return FamilyGap(
            kind="exo_ceiling",
            gate=_GATE_CAPABILITY,
            text=(
                f"this scene's target at {_km(h_tgt_m)} is at or above the "
                f"{_km(los.h_atm_top)} top of the modelled atmosphere, and "
                f"'{family.name}' measures the column only up to {measured} — real, "
                "unmeasured air lies between its top rung and the target"
            ),
            context={
                "family": family.name,
                "h_tgt_m": h_tgt_m,
                "h_atm_top_m": float(los.h_atm_top),
                "family_target_ceiling_m": ceiling_m,
            },
        )

    gap = _zenith_beyond_transform(family, zeta_low_rad)
    if gap is not None:
        return gap
    gap = _check_field(family, nodes, "path_zenith_rad", zeta_low_rad, _GATE_ZENITH)
    if gap is not None:
        return gap

    # Target-axis vacuum equivalence: a family whose runs reach the top of the
    # modelled atmosphere serves a higher target from its ceiling node exactly
    # (_vacuum_clamped_target_m), so that is the coordinate actually queried.
    target_query_m = h_tgt_m
    if ceiling_m is not None and ceiling_m >= _VACUUM_EQUIVALENT_ALTITUDE_M and h_tgt_m > ceiling_m:
        target_query_m = ceiling_m
    gap = _check_field(family, nodes, "target_altitude_m", target_query_m, _GATE_TARGET)
    if gap is not None:
        return gap
    return _check_field(family, nodes, "sensor_altitude_m", h_sensor_m, _GATE_SENSOR)


def family_suitability(family: ShippedFamily, los: LineOfSightGeometry) -> FamilySuitability:
    """Whether *family* can serve *los*, and the first gap when it cannot.

    Reproduces, from the family's own node geometry, every refusal the chain
    would raise for this query — see the module docstring for the list and for
    the one place this is deliberately stricter than the chain (a non-axis
    path-geometry mismatch, which the chain warns about and this declines to
    recommend).
    """
    direction = los.los_direction
    if family.los_direction != direction:
        return FamilySuitability(
            family=family,
            gap=FamilyGap(
                kind="direction",
                gate=_GATE_DIRECTION,
                text=(
                    f"'{family.name}' was rendered from {family.los_direction}-looking "
                    f"runs and this line of sight is {direction}-looking"
                ),
                context={"family": family.name, "los_direction": direction},
            ),
        )

    nodes = family_node_geometry(family.name)
    if nodes is None:
        return FamilySuitability(
            family=family,
            gap=FamilyGap(
                kind="library_missing",
                gate=_GATE_DIRECTION,
                text=(
                    f"the bundled runs for '{family.name}' are not present in this "
                    f"installation (expected under {BUNDLED_ATMOSPHERES_DIR})"
                ),
                context={"family": family.name, "directory": family.bundled_dir},
            ),
        )

    gap = (
        _down_looking_gap(family, nodes, los)
        if direction == "down"
        else _up_looking_gap(family, nodes, los)
    )
    return FamilySuitability(family=family, gap=gap)


# ---------------------------------------------------------------------------
# Selection
# ---------------------------------------------------------------------------


def _candidates(los: LineOfSightGeometry) -> tuple[ShippedFamily, ...]:
    """Bundled families that could serve *los*, most specific first.

    Precedence, deliberately unchanged where the old answer worked: the family
    :func:`recommended_axes` names for this scene shape comes first, so every
    scene the axes-string reasoning already served keeps the family it had.
    The rest of the direction's catalogue follows, more axes first (a family
    that interpolates a dimension is more specific than one rendered at a fixed
    value for it), then catalogue order — which puts the default-dispatch
    :data:`SHIPPED_FAMILIES` ahead of the ``explicit_dir_only`` rows at equal
    specificity, because those need a directory written as well.
    """
    direction = los.los_direction
    matching = [f for f in BUNDLED_FAMILIES if f.los_direction == direction]
    if not matching:
        return ()
    order = {f.name: i for i, f in enumerate(BUNDLED_FAMILIES)}
    matching.sort(key=lambda f: (-len(f.interpolation_axes.split(",")), order[f.name]))

    axes = recommended_axes(direction, float(los.h_tgt), float(los.theta_o))
    if axes is not None:
        normalized = normalize_axes(axes)
        preferred = [f for f in matching if f.interpolation_axes == normalized]
        matching = preferred + [f for f in matching if f not in preferred]
    return tuple(matching)


def select_atmosphere_family(los: LineOfSightGeometry) -> AtmosphereFamilySuggestion:
    """The bundled family to recommend for *los*, pre-validated end to end.

    Walks the candidates in precedence order and returns the first the chain
    would accept in full.  When none is accepted, the result carries the gap of
    the candidate that got **furthest** through the gate sequence — the closest
    miss, which is the one gap worth naming — instead of the first refusal an
    operator would happen to trip over (CU-322).

    A wholly-vacuum path (an up-looking or level scene whose sensor is already at
    or above ``h_atm_top``) is served by identity, with no backend consulted
    (:func:`radiant.atmosphere.topology.evaluate_path_topology`), so the leading
    candidate is returned without gate checks — nothing about the family can
    make that scene fail.
    """
    direction = los.los_direction
    candidates = _candidates(los)
    considered = tuple(f.name for f in candidates)

    if not candidates:
        return AtmosphereFamilySuggestion(
            family=None,
            gap=FamilyGap(
                kind="direction",
                gate=_GATE_DIRECTION,
                text=(
                    f"no bundled interpolation family is rendered for a "
                    f"{direction}-looking line of sight"
                ),
                context={"los_direction": direction},
            ),
            considered=considered,
            los_direction=direction,
        )

    if direction in ("up", "level") and los.h_sensor is not None and los.h_sensor >= los.h_atm_top:
        return AtmosphereFamilySuggestion(
            family=candidates[0],
            gap=None,
            considered=considered,
            los_direction=direction,
            vacuum_path=True,
        )

    worst: FamilyGap | None = None
    for candidate in candidates:
        suitability = family_suitability(candidate, los)
        if suitability.serves:
            return AtmosphereFamilySuggestion(
                family=candidate,
                gap=None,
                considered=considered,
                los_direction=direction,
            )
        gap = suitability.gap
        if gap is None:  # pragma: no cover - not-serving implies a gap
            continue
        if worst is None or gap.gate > worst.gate:
            worst = gap
    return AtmosphereFamilySuggestion(
        family=None,
        gap=_with_pending_runs(worst),
        considered=considered,
        los_direction=direction,
    )


def _with_pending_runs(gap: FamilyGap | None) -> FamilyGap | None:
    """Append the blocking family's authored-but-unrun MODTRAN rows to *gap*.

    A gap whose fix is already scheduled reads very differently from one that is
    not, and the run matrix is where that is recorded — so when the family that
    came closest has rows authored for exactly this geometry, the advisory says
    so rather than leaving the operator to conclude the capability is absent.
    """
    if gap is None:
        return None
    name = gap.context.get("family")
    family = next((f for f in BUNDLED_FAMILIES if f.name == name), None)
    if family is None or family.pending_runs is None:
        return gap
    return FamilyGap(
        kind=gap.kind,
        gate=gap.gate,
        text=f"{gap.text} ({family.pending_runs})",
        context={**gap.context, "pending_runs": family.pending_runs},
    )
