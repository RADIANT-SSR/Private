"""``ViewerState`` — the production adapter the 3D scene library consumes.

The lifted scene library (``radiant.gui.viewer.scene``) was written against the
prototype's frozen ``SceneState`` slider dataclass. Rather than rebind every scene
module, :class:`ViewerState` reproduces **the same field names** (ADR-0007 §2, the
"same field names to minimise churn" clause) so the lift is mechanical: the scene
modules import ``ViewerState as SceneState`` and read the identical attributes.

Where ``SceneState`` was populated from GUI sliders, :class:`ViewerState` is populated
from a real chain evaluation via :meth:`from_chain_result` — its fields are bound to
``stage_outputs["geometry"]`` (ADR-0006 GeometryStage), the final regime from
``stage_outputs["optics"]`` (Rule 10), and the source/optics/detector parameters that
describe the target shape and sampling. The field-level mapping is the ADR-0007 §2
rebind table:

===========================  ==================================================
``ViewerState`` field        Production source
===========================  ==================================================
``observer_altitude_m``      ``stage_outputs["geometry"]["h_sensor_m"]``
``observer_look_angle_rad``  ``stage_outputs["geometry"]["eta_rad"]`` (off-nadir η)
``target_altitude_m``        ``stage_outputs["geometry"]["h_target_m"]``
``theta_o_rad``              ``stage_outputs["geometry"]["theta_o_rad"]`` (path zenith)
``los_direction``            ``stage_outputs["geometry"]["los_direction"]``
``scene_class``              ``stage_outputs["geometry"]["scene_class"]``
``observer_class``           ``stage_outputs["geometry"]["observer_class"]``
``target_class``             ``stage_outputs["geometry"]["target_class"]``
``solar_zenith_rad``         ``stage_outputs["geometry"]["theta_s_rad"]``
``relative_azimuth_rad``     ``stage_outputs["geometry"]["delta_phi_rad"]``
``regime_override``          ``stage_outputs["optics"]["regime"]`` (final, Rule 10)
``target_shape`` + dims      ``geometry.target.shape`` / ``geometry.target.shape_*``
``target_fill_fraction``     ``source.target.fill_fraction``
``projected_area_m2``        ``stage_outputs["source"]["projected_area_m2"]`` (CU-168)
``angular_extent_rad``       ``stage_outputs["source"]["angular_extent_rad"]`` (CU-168)
``focal_length_m``           ``optics.focal_length_m``
``pixel_pitch_m``            ``detector.pixel_pitch_x_um`` (returned canonical m)
``observer_{yaw,pitch,roll}``  **no stage owner** — defaulted to 0 (CU-122)
``target_{yaw,pitch,roll}``  ``geometry.target.shape_{yaw,pitch,roll}_rad``
===========================  ==================================================

Attitude gap (CU-122): ADR-0006 §4 deferred platform/target *attitude* "until a
consumer exists". The viewer is that consumer, but no stage emits a platform attitude
yet, so ``observer_{yaw,pitch,roll}_rad`` default to zero (identity). The RPY triad that
would render them is Part B; this adapter records the gap rather than inventing a source.

This module holds **no physics** and imports **no physics stage** — it reads a
``ChainResult`` and a parameter getter, both produced upstream by the API layer
(gui → api + core, import-linter contract). All angles are radians, all lengths metres
(RADIANT canonical units); no unit conversion happens here (Rule 2).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal, Protocol

if TYPE_CHECKING:
    from radiant.api import ChainResult

ShapeKind = Literal["none", "sphere", "cylinder", "flat_plate", "box", "cone"]
RegimeOverride = Literal["auto", "extended", "sub_pixel", "point_source"]
BackgroundKind = Literal["none", "cold_space", "ground", "at_aperture"]

#: LOS direction the schematic composes for when the stage publishes none (a partial or
#: pre-ADR-0011 result): the down-looking layout that was the only one before Phase 4.
DEFAULT_LOS_DIRECTION: str = "down"


class ParamGetter(Protocol):
    """The minimal read surface :meth:`ViewerState.from_chain_result` needs.

    Satisfied by :class:`radiant.api.Sensor` (its ``get`` method) — the GUI already
    holds the live sensor, so no new plumbing is required. Kept as a ``Protocol`` so the
    adapter never imports ``Sensor`` and the gui→api boundary stays a runtime call, not a
    structural dependency.
    """

    def get(self, name: str) -> object: ...


@dataclass(frozen=True)
class ViewerState:
    """All inputs the 3D scene library reads, in canonical units.

    Field names and units mirror the prototype ``SceneState`` (ADR-0007 §2) so the
    lifted scene modules consume this object unchanged. Populated from a chain
    evaluation by :meth:`from_chain_result`; a slider never writes it in production.
    """

    observer_altitude_m: float
    observer_look_angle_rad: float
    observer_yaw_rad: float
    observer_pitch_rad: float
    observer_roll_rad: float

    target_altitude_m: float
    target_shape: ShapeKind
    target_radius_m: float
    target_length_m: float
    target_width_m: float
    target_height_m: float
    target_base_radius_m: float
    target_yaw_rad: float
    target_pitch_rad: float
    target_roll_rad: float
    target_fill_fraction: float
    # Target projected area facing the sensor and its angular extent (√A / range),
    # from SourceStage (CU-168). Surfaced on the schematic as a leader-label pill so a
    # target sized only by projected_area_m2 (shape library = "none") is visible, not
    # invisible in the parameter tree. 0.0 when no area is defined (the pill is hidden).
    projected_area_m2: float
    angular_extent_rad: float

    focal_length_m: float
    pixel_pitch_m: float

    solar_zenith_rad: float
    relative_azimuth_rad: float

    regime_override: RegimeOverride
    background_kind: BackgroundKind

    # Night scenes (geometry.solar_illumination = "night") have no sun: the geometry
    # stage publishes theta_s_rad / delta_phi_rad as None, and the schematic hides the
    # sun glyph and every sun-derived vector/arc instead of fabricating angles. The
    # angle fields above then hold inert 0.0 placeholders (never drawn).
    has_sun: bool = True

    # -- Generalized viewing geometry (ADR-0011), bound verbatim from the stage ----
    # These five drive the schematic's *composition* (which endpoint is the lower one,
    # where the ground plane sits) and the θ_o / ζ_low annotations. They default to the
    # down-looking scene the viewer composed before ADR-0011, so a partial result — or a
    # state built without them — renders exactly as it did then.
    #
    # ``theta_o_rad`` is the canonical target-side path zenith on the CLOSED domain
    # [0, π]: acute for a down-looking scene, obtuse for an up-looking one (ADR-0011
    # decision 2). ``los_direction`` is "down" | "up" | "level", DERIVED by the stage from
    # the altitude pair — never a user switch and never re-derived here (decision 1).
    # ``scene_class`` is the observer×target altitude-band label ("ground_to_air", …) and
    # ``observer_class`` / ``target_class`` are its two halves ("ground" | "air" | "space");
    # the schematic uses ``observer_class`` only to decide where the ground plane sits
    # relative to the sensor glyph (decision 8: composition, never physics).
    theta_o_rad: float = 0.0
    los_direction: str = DEFAULT_LOS_DIRECTION
    scene_class: str = ""
    observer_class: str = ""
    target_class: str = ""

    @classmethod
    def default(cls) -> ViewerState:
        """A neutral airborne-ish baseline used only by tests / anchor enumeration.

        Supplies a fully-populated state (all shape dims + RPY) without a chain evaluation,
        for the schematic's ``build_scene`` unit tests. Not used for any bound render (the
        production path always builds from :meth:`from_chain_result`).
        """
        return cls(
            observer_altitude_m=8_000.0,
            observer_look_angle_rad=math.radians(20.0),
            observer_yaw_rad=0.0,
            observer_pitch_rad=0.0,
            observer_roll_rad=0.0,
            target_altitude_m=0.0,
            target_shape="sphere",
            target_radius_m=1.0,
            target_length_m=2.0,
            target_width_m=1.0,
            target_height_m=1.0,
            target_base_radius_m=1.0,
            target_yaw_rad=0.0,
            target_pitch_rad=0.0,
            target_roll_rad=0.0,
            target_fill_fraction=1.0,
            projected_area_m2=0.0,
            angular_extent_rad=0.0,
            focal_length_m=1.0,
            pixel_pitch_m=10e-6,
            solar_zenith_rad=math.radians(35.0),
            relative_azimuth_rad=math.radians(12.0),
            regime_override="auto",
            background_kind="none",
            # A neutral DOWN-looking baseline: an 8 km sensor over a sea-level target, so
            # the path zenith θ_o and the off-nadir η agree to ~0.03° and the composition
            # is the pre-ADR-0011 one. Tests that need another class override these.
            theta_o_rad=math.radians(20.0),
            los_direction="down",
            scene_class="air_to_ground",
            observer_class="air",
            target_class="ground",
        )

    @classmethod
    def from_chain_result(cls, result: ChainResult, params: ParamGetter) -> ViewerState:
        """Build a bound :class:`ViewerState` from an evaluated chain + its parameters.

        *result* supplies the derived geometry (``stage_outputs["geometry"]``) and the
        final regime (``stage_outputs["optics"]["regime"]``, Rule 10). *params* is the
        parameter read surface (the live :class:`~radiant.api.Sensor`) for the target
        shape, focal length, and pixel pitch — quantities the geometry stage does not
        emit. Every value is read verbatim in its canonical unit; no conversion (Rule 2).
        """
        geometry = result.stage_outputs.get("geometry", {})
        optics = result.stage_outputs.get("optics", {})
        source = result.stage_outputs.get("source", {})

        # Night scenes publish theta_s_rad / delta_phi_rad as None (geometry stage,
        # SolarResolution mode="night"): no sun exists, so record that instead of
        # crashing on float(None) — the schematic drops the sun (owner bug 2026-07-18).
        theta_s = geometry.get("theta_s_rad", 0.0)
        delta_phi = geometry.get("delta_phi_rad", 0.0)

        return cls(
            observer_altitude_m=float(geometry.get("h_sensor_m", 0.0)),
            observer_look_angle_rad=float(geometry.get("eta_rad", 0.0)),
            # Platform attitude has no stage owner (ADR-0006 §4 / CU-122): default to
            # identity. The RPY triad that would render it is Part B.
            observer_yaw_rad=0.0,
            observer_pitch_rad=0.0,
            observer_roll_rad=0.0,
            target_altitude_m=float(geometry.get("h_target_m", 0.0)),
            target_shape=_shape_of(params.get("geometry.target.shape")),
            target_radius_m=float(params.get("geometry.target.shape_radius_m")),  # type: ignore[arg-type]
            target_length_m=float(params.get("geometry.target.shape_length_m")),  # type: ignore[arg-type]
            target_width_m=float(params.get("geometry.target.shape_width_m")),  # type: ignore[arg-type]
            target_height_m=float(params.get("geometry.target.shape_height_m")),  # type: ignore[arg-type]
            target_base_radius_m=float(params.get("geometry.target.shape_base_radius_m")),  # type: ignore[arg-type]
            target_yaw_rad=float(params.get("geometry.target.shape_yaw_rad")),  # type: ignore[arg-type]
            target_pitch_rad=float(params.get("geometry.target.shape_pitch_rad")),  # type: ignore[arg-type]
            target_roll_rad=float(params.get("geometry.target.shape_roll_rad")),  # type: ignore[arg-type]
            target_fill_fraction=float(params.get("source.target.fill_fraction")),  # type: ignore[arg-type]
            # SourceStage publishes these as None when no target area is defined
            # (extended scene); coerce to 0.0 so the schematic simply hides the pill.
            projected_area_m2=float(source.get("projected_area_m2") or 0.0),
            angular_extent_rad=float(source.get("angular_extent_rad") or 0.0),
            focal_length_m=float(params.get("optics.focal_length_m")),  # type: ignore[arg-type]
            # get() returns the canonical value (metres) despite the ``_um`` input-unit
            # name (detector schema: canonical_unit="m").
            pixel_pitch_m=float(params.get("detector.pixel_pitch_x_um")),  # type: ignore[arg-type]
            solar_zenith_rad=float(theta_s) if theta_s is not None else 0.0,
            relative_azimuth_rad=float(delta_phi) if delta_phi is not None else 0.0,
            regime_override=_regime_of(optics.get("regime")),
            background_kind="none",
            has_sun=theta_s is not None,
            # Generalized viewing geometry (ADR-0011), read verbatim. A result that
            # predates these keys (or a partial stage output) falls back to the
            # down-looking composition — the viewer's behaviour before Phase 4.
            theta_o_rad=float(geometry.get("theta_o_rad") or 0.0),
            los_direction=str(geometry.get("los_direction") or DEFAULT_LOS_DIRECTION),
            scene_class=str(geometry.get("scene_class") or ""),
            observer_class=str(geometry.get("observer_class") or ""),
            target_class=str(geometry.get("target_class") or ""),
        )


def _shape_of(value: object) -> ShapeKind:
    """Coerce a ``geometry.target.shape`` parameter value to a :data:`ShapeKind`.

    The schema sentinel ``"none"`` (shape not provided) passes through; the production
    builder renders no target *body* for it (an extended/sub-pixel scene has no discrete
    shape). An unrecognised value also collapses to ``"none"`` so the viewer degrades to
    the ground/glyph scene rather than raising.
    """
    known = ("none", "sphere", "cylinder", "flat_plate", "box", "cone")
    text = str(value)
    return text if text in known else "none"  # type: ignore[return-value]


def _regime_of(value: object) -> RegimeOverride:
    """Coerce a final-regime value (``RadiometricRegime`` enum or str) to the literal.

    Reads ``.value`` when handed the enum (its values are exactly
    ``extended``/``sub_pixel``/``point_source``); accepts the bare string too. Anything
    unrecognised becomes ``"auto"`` so the regime overlays simply no-op.
    """
    text = getattr(value, "value", value)
    known = ("extended", "sub_pixel", "point_source", "auto")
    text = str(text)
    return text if text in known else "auto"  # type: ignore[return-value]


__all__ = [
    "ViewerState",
    "ShapeKind",
    "RegimeOverride",
    "BackgroundKind",
    "ParamGetter",
    "DEFAULT_LOS_DIRECTION",
]
