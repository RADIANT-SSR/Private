"""Level-0 pin: the solar pair on the adopted LOS is descriptor-independent (CU-388).

CU-388 reported that ``source/_inferrer._adjust_scene_los`` kept ``theta_s`` /
``delta_phi`` only for ``T2Reflective`` and ``T3Mixed`` — the CU-009
"a pure-thermal radiance has no solar leg" predicate — so a
``T7IntensityAtSource`` target fell into the else-branch, the atmosphere lost
the solar geometry, and the sky background pedestal disappeared from every
VIS/NIR point-source-by-intensity scene.

That predicate is gone: CU-258 (2026-07-28) first punched through it for the
T7 intensity door and CU-356 (2026-09-12) removed it entirely.  What was
missing was a **pinned contract** — nothing asserted the T7 case, so the
behavior CU-388 asks for was correct but unprotected, which is how the same
defect came back as a registry entry twice.  This module is that pin.

The contract has two halves, and the distinction is the whole point of
CU-388:

1. **The atmosphere keeps the sun.**  ``theta_s`` / ``delta_phi`` describe
   *where the sun is in the scene*, which is a property of the scene and not
   of the target's material.  The sky background and the path radiance are
   second consumers whose solar dependence has nothing to do with how the
   analyst chose to declare the target, so the adopted LOS carries the solar
   pair for **every** target descriptor.
2. **The target is not re-illuminated.**  An intensity-declared target
   (S10 → ``T7IntensityAtSource``) is pre-integrated: ``I(λ)`` [W/sr/µm]
   already contains whatever illumination the analyst accounted for.  The
   target-side gate against double-counting is **structural**, not
   predicate-based: the T7 assembly arm carries no ρ term for the sun to
   enter through.  Pinned here by asserting the descriptor exposes no
   reflectance surface, and end-to-end in
   ``tests/integration/test_direction_aware_atmosphere.py``
   (``TestIntensityDoorKeepsTheDaytimeSky``), where the at-aperture target
   radiance is invariant under ``theta_s`` while the background is not.

``'night'`` remains the one switch on the solar pair, and it is applied
upstream in ``GeometryStage`` — the LOS reaching ``_adjust_scene_los``
already carries ``theta_s = None``, so the pass-through is what is asserted
here.

Level 0: these are direct calls on the routing functions with hand-built
inputs.  No chain, no golden.
"""

from __future__ import annotations

from collections.abc import Callable

import numpy as np
import pytest

from radiant.core.descriptors import (
    T1Thermal,
    T2Reflective,
    T7IntensityAtSource,
    TargetDescriptor,
)
from radiant.core.los_geometry import LineOfSightGeometry
from radiant.core.spectral import SpectralData
from radiant.source._inferrer import _adjust_scene_los
from radiant.source.converters.reflectance import reflectance_to_descriptor

#: VIS grid — the band where the omission CU-388 describes is leading-order
#: (a daylight sky pedestal is the dominant noise term of a visible
#: measurement, not a correction).
_WL_VIS = np.linspace(0.4, 0.9, 11)

#: Distinctive solar pair.  Deliberately not the schema defaults, so a
#: pass-through cannot be confused with a re-derivation from parameters.
_THETA_S_RAD = 1.0471975511965976  # 60°
_DELTA_PHI_RAD = 0.7853981633974483  # 45°


def _flat(value: float, *, name: str, unit: str) -> SpectralData:
    """Spectrally flat ``SpectralData`` on the VIS grid."""
    return SpectralData(
        name=name,
        wavelength_um=_WL_VIS,
        values=np.full(_WL_VIS.shape, float(value), dtype=np.float64),
        unit=unit,
        source="test_scene_los_solar_retention",
    )


def _intensity_target(
    *,
    target_location: str = "terrestrial",
    no_atmosphere_subcase: str | None = None,
) -> T7IntensityAtSource:
    """The S10 intensity door — the descriptor CU-388 is about."""
    return T7IntensityAtSource(
        scene_type="point_source",
        target_location=target_location,  # type: ignore[arg-type]
        no_atmosphere_subcase=no_atmosphere_subcase,  # type: ignore[arg-type]
        h_tgt=0.0,
        I_t_source=_flat(10.0, name="test.I_t_source", unit="W/sr/um"),
    )


def _thermal_target() -> T1Thermal:
    """A pure-thermal target — the byte-identity side of the contract."""
    return T1Thermal(
        scene_type="extended",
        target_location="terrestrial",
        h_tgt=0.0,
        epsilon=_flat(0.95, name="test.epsilon", unit=""),
        T_t=300.0,
    )


def _reflective_target() -> T2Reflective:
    """A reflective target — the descriptor that always kept the sun."""
    target = reflectance_to_descriptor(
        rho=0.3,
        wavelength_um=_WL_VIS,
        scene_type="extended",
        target_location="terrestrial",
        h_tgt=0.0,
    )
    assert isinstance(target, T2Reflective)
    return target


def _lit_scene_los() -> LineOfSightGeometry:
    """A lit, down-looking scene LOS as ``GeometryStage`` publishes it."""
    return LineOfSightGeometry(
        h_tgt=0.0,
        h_sensor=500_000.0,
        h_atm_top=100_000.0,
        theta_o=0.3490658503988659,  # 20°
        theta_s=_THETA_S_RAD,
        delta_phi=_DELTA_PHI_RAD,
    )


def _dark_scene_los() -> LineOfSightGeometry:
    """The same scene at night — ``GeometryStage`` already stripped the pair."""
    return LineOfSightGeometry(
        h_tgt=0.0,
        h_sensor=500_000.0,
        h_atm_top=100_000.0,
        theta_o=0.3490658503988659,
        theta_s=None,
        delta_phi=None,
    )


#: One factory per descriptor door that can reach an atmospheric path.  T7 is
#: the CU-388 subject; T1 is the byte-identity side; T2 is the door that
#: always kept the sun and therefore fixes the reference payload.
_DESCRIPTOR_FACTORIES: dict[str, Callable[[], TargetDescriptor]] = {
    "T7IntensityAtSource": _intensity_target,
    "T1Thermal": _thermal_target,
    "T2Reflective": _reflective_target,
}


class TestTheAtmosphereKeepsTheSun:
    """Half 1: the adopted LOS carries the solar pair for every descriptor."""

    @pytest.mark.parametrize("label", sorted(_DESCRIPTOR_FACTORIES))
    def test_lit_scene_keeps_theta_s_and_delta_phi(self, label: str) -> None:
        adjusted = _adjust_scene_los(
            _lit_scene_los(), "terrestrial", target_descriptor=_DESCRIPTOR_FACTORIES[label]()
        )
        assert adjusted is not None
        assert adjusted.theta_s == pytest.approx(_THETA_S_RAD, rel=0.0, abs=0.0), (
            f"{label} lost theta_s — the atmosphere cannot build a scattered sky "
            "without it (CU-388)"
        )
        assert adjusted.delta_phi == pytest.approx(_DELTA_PHI_RAD, rel=0.0, abs=0.0)

    def test_the_intensity_door_is_not_a_special_case(self) -> None:
        """T7 gets the *same* solar pair a reflective target gets.

        The discriminating assertion: CU-388's defect was an asymmetry
        between the intensity door and the reflective door, so the pin is
        that the two adopted LOS payloads are equal field-for-field.
        """
        scene = _lit_scene_los()
        by_intensity = _adjust_scene_los(
            scene, "terrestrial", target_descriptor=_intensity_target()
        )
        by_reflectance = _adjust_scene_los(
            scene, "terrestrial", target_descriptor=_reflective_target()
        )
        assert by_intensity is not None
        assert by_reflectance is not None
        assert by_intensity == by_reflectance

    @pytest.mark.parametrize("label", sorted(_DESCRIPTOR_FACTORIES))
    def test_night_scene_arrives_and_stays_stripped(self, label: str) -> None:
        """``'night'`` is applied in ``GeometryStage``; this is a pass-through."""
        adjusted = _adjust_scene_los(
            _dark_scene_los(), "terrestrial", target_descriptor=_DESCRIPTOR_FACTORIES[label]()
        )
        assert adjusted is not None
        assert adjusted.theta_s is None, f"{label} fabricated a sun on a night scene"
        assert adjusted.delta_phi is None

    def test_no_atmosphere_intensity_door_keeps_the_sun(self) -> None:
        """The ``no_atmosphere`` arm adjusts ``h_tgt``, never the solar pair."""
        adjusted = _adjust_scene_los(
            _lit_scene_los(),
            "no_atmosphere",
            target_descriptor=_intensity_target(
                target_location="no_atmosphere", no_atmosphere_subcase="space"
            ),
        )
        assert adjusted is not None
        assert adjusted.theta_s == pytest.approx(_THETA_S_RAD, rel=0.0, abs=0.0)
        assert adjusted.delta_phi == pytest.approx(_DELTA_PHI_RAD, rel=0.0, abs=0.0)
        assert adjusted.h_tgt == pytest.approx(0.0, rel=0.0, abs=0.0)

    def test_at_aperture_still_has_no_los_at_all(self) -> None:
        """The pass-through arm never evaluates an atmospheric path.

        S10 cannot *be* at-aperture (matrix §7: ``at_aperture`` requires
        ``scene_type='extended'``, and an intensity is point-source only), so
        the arm is pinned on the descriptor that can reach it.  Keeping the
        solar pair must not turn the pass-through arm into an atmospheric one.
        """
        assert (
            _adjust_scene_los(
                _lit_scene_los(),
                "at_aperture",
                target_descriptor=_thermal_target(),
            )
            is None
        )


class TestTheTargetIsNotReIlluminated:
    """Half 2: keeping ``theta_s`` must not put sunlight on an S10 target.

    The gate is structural rather than predicate-based, so what is asserted
    is the structure: a ``T7IntensityAtSource`` exposes an intensity and no
    reflectance, so there is no term for a solar irradiance to multiply.  The
    radiometric consequence — at-aperture target radiance invariant under
    ``theta_s`` — is pinned end to end in
    ``tests/integration/test_direction_aware_atmosphere.py``.
    """

    def test_t7_carries_no_reflectance_term(self) -> None:
        target = _intensity_target()
        assert target.I_t_source is not None
        assert getattr(target, "rho", None) is None
        assert getattr(target, "epsilon", None) is None
        assert getattr(target, "T_t", None) is None

    def test_t7_scene_los_adjustment_does_not_touch_the_intensity(self) -> None:
        """Routing the LOS leaves ``I(λ)`` byte-identical.

        ``_adjust_scene_los`` is a pure function of the LOS; this asserts it
        has no side effect on the descriptor it dispatches on, which is what
        would silently re-scale a pre-integrated intensity.
        """
        target = _intensity_target()
        assert target.I_t_source is not None
        before = np.array(target.I_t_source.values, copy=True)
        _adjust_scene_los(_lit_scene_los(), "terrestrial", target_descriptor=target)
        assert target.I_t_source is not None
        np.testing.assert_array_equal(target.I_t_source.values, before)
