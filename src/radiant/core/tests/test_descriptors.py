"""Tests for radiant.core.descriptors.

Covers:
- Valid-cell smoke tests per matrix §3.2 (one per T-code × sub-case).
- Invalid-combination raise tests per matrix §7.
- Warn-not-raise tests for T_g out of range and MWIR-with-non-mixed.
- Serialization round-trip via dataclasses.asdict + a SpectralData helper.
"""

from __future__ import annotations

import dataclasses
from typing import Any

import numpy as np
import pytest

from radiant.core.descriptors import (
    AtApertureBackground,
    ColdSpaceBackground,
    GroundBackground,
    T1Thermal,
    T2Reflective,
    T3Mixed,
    T5AtAperture,
    T6TabulatedAtSource,
    UserSpectralBackground,
    raise_if_epsilon_and_rho_both_set,
    warn_if_reflective_and_sun_below_horizon,
)
from radiant.core.parameters import ParameterBoundsError
from radiant.core.reflectance import ScalarLambertianReflectance
from radiant.core.spectral import SpectralData

# ---------------------------------------------------------------------------
# SpectralData factories for each band
# ---------------------------------------------------------------------------


def _sd(
    name: str,
    lam_min: float,
    lam_max: float,
    value: float = 0.9,
    unit: str = "",
) -> SpectralData:
    """Construct a flat SpectralData on [lam_min, lam_max] µm (2 points)."""
    return SpectralData(
        name=name,
        wavelength_um=np.array([lam_min, lam_max], dtype=np.float64),
        values=np.array([value, value], dtype=np.float64),
        unit=unit,
        source="test_descriptors",
    )


def eps_lwir() -> SpectralData:
    return _sd("eps_lwir", 8.0, 14.0, 0.95)


def eps_mwir() -> SpectralData:
    return _sd("eps_mwir", 3.0, 5.0, 0.90)


def rho_vis() -> ScalarLambertianReflectance:
    return ScalarLambertianReflectance(reflectance=_sd("rho_vis", 0.4, 0.7, 0.3))


def rho_nir() -> ScalarLambertianReflectance:
    return ScalarLambertianReflectance(reflectance=_sd("rho_nir", 0.7, 1.0, 0.4))


def rho_swir() -> ScalarLambertianReflectance:
    return ScalarLambertianReflectance(reflectance=_sd("rho_swir", 1.0, 2.5, 0.5))


def rho_mwir() -> ScalarLambertianReflectance:
    return ScalarLambertianReflectance(reflectance=_sd("rho_mwir", 3.0, 5.0, 0.1))


def L_flat(name: str = "L_aperture") -> SpectralData:
    return _sd(name, 0.4, 14.0, 1.0, unit="W/m^2/sr/um")


def L_source_lwir(name: str = "L_t_source") -> SpectralData:
    """Positive flat L_source on the LWIR grid for T6 tests."""
    return _sd(name, 8.0, 14.0, 1.0, unit="W/m^2/sr/um")


# ---------------------------------------------------------------------------
# Valid-cell smoke tests (matrix §3.2 representatives)
# ---------------------------------------------------------------------------


@pytest.mark.level0
def test_cell_16_terrestrial_vis_extended_t2() -> None:
    """Cell 16 — terrestrial VIS extended reflective."""
    t = T2Reflective(
        scene_type="extended",
        target_location="terrestrial",
        h_tgt=0.0,
        rho=rho_vis(),
    )
    assert t.scene_type == "extended"
    assert t.target_location == "terrestrial"


@pytest.mark.level0
def test_cell_17_terrestrial_vis_sub_pixel_t2() -> None:
    """Cell 17 — terrestrial VIS sub-pixel reflective + area."""
    t = T2Reflective(
        scene_type="sub_pixel",
        target_location="terrestrial",
        h_tgt=0.0,
        rho=rho_vis(),
        A_t=1.0,
        shape="sphere",
    )
    assert t.A_t == 1.0


@pytest.mark.level0
def test_cell_20_terrestrial_nir_sub_pixel_t2() -> None:
    t = T2Reflective(
        scene_type="sub_pixel",
        target_location="terrestrial",
        h_tgt=0.0,
        rho=rho_nir(),
        A_t=2.5,
    )
    assert t.target_location == "terrestrial"


@pytest.mark.level0
def test_cell_23_terrestrial_swir_sub_pixel_t2() -> None:
    t = T2Reflective(
        scene_type="sub_pixel",
        target_location="terrestrial",
        h_tgt=0.0,
        rho=rho_swir(),
        A_t=1.0,
    )
    assert t.scene_type == "sub_pixel"


@pytest.mark.level0
def test_cell_25_terrestrial_mwir_extended_t3_mandatory() -> None:
    """Cell 25 — terrestrial MWIR extended mixed emit+reflect (mandatory)."""
    t = T3Mixed(
        scene_type="extended",
        target_location="terrestrial",
        h_tgt=0.0,
        epsilon=eps_mwir(),
        T_t=300.0,
    )
    assert t.T_t == 300.0


@pytest.mark.level0
def test_cell_28_terrestrial_lwir_extended_t1() -> None:
    """Cell 28 — terrestrial LWIR extended graybody (anchor cell)."""
    t = T1Thermal(
        scene_type="extended",
        target_location="terrestrial",
        h_tgt=0.0,
        epsilon=eps_lwir(),
        T_t=300.0,
    )
    assert t.T_t == 300.0


@pytest.mark.level0
def test_cell_29_terrestrial_lwir_sub_pixel_t1() -> None:
    t = T1Thermal(
        scene_type="sub_pixel",
        target_location="terrestrial",
        h_tgt=0.0,
        epsilon=eps_lwir(),
        T_t=350.0,
        A_t=0.5,
    )
    assert t.scene_type == "sub_pixel"


@pytest.mark.level0
def test_cell_43_airborne_lwir_extended_t1() -> None:
    """Cell 43 — airborne LWIR extended; h_tgt > 0."""
    t = T1Thermal(
        scene_type="extended",
        target_location="airborne",
        h_tgt=10_000.0,
        epsilon=eps_lwir(),
        T_t=250.0,
    )
    assert t.h_tgt == 10_000.0


@pytest.mark.level0
def test_cell_58_space_lwir_extended_t1_anchor() -> None:
    """Cell 58 — no_atmosphere space LWIR extended (anchor cell)."""
    t = T1Thermal(
        scene_type="extended",
        target_location="no_atmosphere",
        no_atmosphere_subcase="space",
        h_tgt=400_000.0,
        epsilon=eps_lwir(),
        T_t=285.0,
    )
    bg = ColdSpaceBackground()
    assert t.no_atmosphere_subcase == "space"
    assert isinstance(bg, ColdSpaceBackground)


@pytest.mark.level0
def test_cell_46_space_vis_extended_t2() -> None:
    t = T2Reflective(
        scene_type="extended",
        target_location="no_atmosphere",
        no_atmosphere_subcase="space",
        h_tgt=400_000.0,
        rho=rho_vis(),
    )
    assert t.target_location == "no_atmosphere"


@pytest.mark.level0
def test_cell_55_space_mwir_extended_t3() -> None:
    t = T3Mixed(
        scene_type="extended",
        target_location="no_atmosphere",
        no_atmosphere_subcase="space",
        h_tgt=400_000.0,
        epsilon=eps_mwir(),
        T_t=320.0,
    )
    assert t.T_t == 320.0


@pytest.mark.level0
def test_cell_1_at_aperture_vis_extended_t5_L() -> None:
    """Cell 1 — at_aperture VIS extended user radiance."""
    t = T5AtAperture(
        scene_type="extended",
        target_location="at_aperture",
        L_t_aperture=L_flat("L_t_aperture"),
    )
    bg = AtApertureBackground(L_bg_aperture=L_flat("L_bg_aperture"))
    assert t.L_t_aperture is not None
    assert bg.L_bg_aperture is not None


@pytest.mark.level0
def test_cell_G13_ground_test_lwir_extended_user_bg() -> None:
    t = T1Thermal(
        scene_type="extended",
        target_location="no_atmosphere",
        no_atmosphere_subcase="ground_test",
        h_tgt=0.0,
        epsilon=eps_lwir(),
        T_t=310.0,
    )
    bg = UserSpectralBackground(L_bg=L_flat("L_bg_test"))
    assert t.no_atmosphere_subcase == "ground_test"
    assert bg.L_bg is not None


@pytest.mark.level0
def test_cell_L13_lab_test_lwir_extended_user_bg() -> None:
    t = T1Thermal(
        scene_type="extended",
        target_location="no_atmosphere",
        no_atmosphere_subcase="lab_test",
        h_tgt=0.0,
        epsilon=eps_lwir(),
        T_t=373.0,
    )
    bg = UserSpectralBackground(L_bg=L_flat("L_bg_chamber"))
    assert t.no_atmosphere_subcase == "lab_test"
    assert bg.L_bg is not None


@pytest.mark.level0
def test_ground_background_valid_construction() -> None:
    bg = GroundBackground(epsilon_g=eps_lwir(), T_g=290.0)
    assert bg.T_g == 290.0


# ---------------------------------------------------------------------------
# Matrix §7 must-raise tests
# ---------------------------------------------------------------------------


@pytest.mark.level0
def test_raise_at_aperture_sub_pixel() -> None:
    """at_aperture + sub_pixel must raise (matrix §7)."""
    with pytest.raises(ParameterBoundsError, match="at_aperture"):
        T5AtAperture(
            scene_type="sub_pixel",
            target_location="at_aperture",
            L_t_aperture=L_flat(),
        )


@pytest.mark.level0
def test_raise_at_aperture_point_source() -> None:
    """at_aperture + point_source must raise (matrix §7)."""
    with pytest.raises(ParameterBoundsError, match="at_aperture"):
        T5AtAperture(
            scene_type="point_source",
            target_location="at_aperture",
            L_t_aperture=L_flat(),
        )


@pytest.mark.level0
def test_raise_no_atmosphere_without_subcase() -> None:
    with pytest.raises(ParameterBoundsError, match="sub.?case"):
        T1Thermal(
            scene_type="extended",
            target_location="no_atmosphere",
            h_tgt=400_000.0,
            epsilon=eps_lwir(),
            T_t=285.0,
        )


@pytest.mark.level0
def test_raise_subcase_without_no_atmosphere() -> None:
    with pytest.raises(ParameterBoundsError, match="no_atmosphere"):
        T1Thermal(
            scene_type="extended",
            target_location="terrestrial",
            no_atmosphere_subcase="space",
            h_tgt=0.0,
            epsilon=eps_lwir(),
            T_t=300.0,
        )


@pytest.mark.level0
def test_raise_invalid_subcase_value() -> None:
    with pytest.raises(ParameterBoundsError, match="sub.?case"):
        T1Thermal(
            scene_type="extended",
            target_location="no_atmosphere",
            no_atmosphere_subcase="outer_space",  # type: ignore[arg-type]
            h_tgt=400_000.0,
            epsilon=eps_lwir(),
            T_t=285.0,
        )


@pytest.mark.level0
def test_raise_h_tgt_negative() -> None:
    with pytest.raises(ParameterBoundsError, match="h_tgt"):
        T1Thermal(
            scene_type="extended",
            target_location="terrestrial",
            h_tgt=-10.0,
            epsilon=eps_lwir(),
            T_t=300.0,
        )


@pytest.mark.level0
def test_raise_terrestrial_without_h_tgt() -> None:
    with pytest.raises(ParameterBoundsError, match="h_tgt"):
        T1Thermal(
            scene_type="extended",
            target_location="terrestrial",
            epsilon=eps_lwir(),
            T_t=300.0,
        )


@pytest.mark.level0
def test_raise_at_aperture_with_h_tgt_set() -> None:
    with pytest.raises(ParameterBoundsError, match="h_tgt"):
        T5AtAperture(
            scene_type="extended",
            target_location="at_aperture",
            h_tgt=0.0,
            L_t_aperture=L_flat(),
        )


@pytest.mark.level0
def test_raise_t1_missing_epsilon() -> None:
    with pytest.raises(ParameterBoundsError, match="epsilon"):
        T1Thermal(
            scene_type="extended",
            target_location="terrestrial",
            h_tgt=0.0,
            T_t=300.0,
        )


@pytest.mark.level0
def test_raise_t1_zero_temperature() -> None:
    with pytest.raises(ParameterBoundsError, match="T_t"):
        T1Thermal(
            scene_type="extended",
            target_location="terrestrial",
            h_tgt=0.0,
            epsilon=eps_lwir(),
            T_t=0.0,
        )


@pytest.mark.level0
def test_raise_t2_missing_rho() -> None:
    with pytest.raises(ParameterBoundsError, match="rho"):
        T2Reflective(
            scene_type="extended",
            target_location="terrestrial",
            h_tgt=0.0,
        )


@pytest.mark.level0
def test_raise_t5_missing_both_spectra() -> None:
    with pytest.raises(ParameterBoundsError, match="L_t_aperture"):
        T5AtAperture(
            scene_type="extended",
            target_location="at_aperture",
        )


@pytest.mark.level0
def test_raise_t5_both_L_and_I() -> None:
    with pytest.raises(ParameterBoundsError, match="both"):
        T5AtAperture(
            scene_type="extended",
            target_location="at_aperture",
            L_t_aperture=L_flat("L_t"),
            I_t_aperture=L_flat("I_t"),
        )


@pytest.mark.level0
def test_raise_t5_with_non_at_aperture_location() -> None:
    with pytest.raises(ParameterBoundsError, match="at_aperture"):
        T5AtAperture(
            scene_type="extended",
            target_location="terrestrial",
            h_tgt=0.0,
            L_t_aperture=L_flat(),
        )


@pytest.mark.level0
def test_raise_ground_background_missing_epsilon() -> None:
    with pytest.raises(ParameterBoundsError, match="epsilon_g"):
        GroundBackground(T_g=290.0)


@pytest.mark.level0
def test_raise_ground_background_non_positive_T_g() -> None:
    with pytest.raises(ParameterBoundsError, match="T_g"):
        GroundBackground(epsilon_g=eps_lwir(), T_g=0.0)


@pytest.mark.level0
def test_raise_user_spectral_bg_missing_L_bg() -> None:
    with pytest.raises(ParameterBoundsError, match="L_bg"):
        UserSpectralBackground()


@pytest.mark.level0
def test_raise_epsilon_and_rho_both_helper() -> None:
    """The over-specification helper raises when both are set (Rule 5)."""
    with pytest.raises(ParameterBoundsError, match="both"):
        raise_if_epsilon_and_rho_both_set(eps_lwir(), rho_vis())


@pytest.mark.level0
def test_helper_accepts_one_or_neither() -> None:
    raise_if_epsilon_and_rho_both_set(eps_lwir(), None)
    raise_if_epsilon_and_rho_both_set(None, rho_vis())
    raise_if_epsilon_and_rho_both_set(None, None)


# ---------------------------------------------------------------------------
# Warn (not raise) tests
# ---------------------------------------------------------------------------


@pytest.mark.level0
def test_warn_ground_background_T_g_above_range() -> None:
    with pytest.warns(UserWarning, match=r"150.*350"):
        GroundBackground(epsilon_g=eps_lwir(), T_g=400.0)


@pytest.mark.level0
def test_warn_ground_background_T_g_below_range() -> None:
    with pytest.warns(UserWarning, match=r"150.*350"):
        GroundBackground(epsilon_g=eps_lwir(), T_g=100.0)


@pytest.mark.level0
def test_no_warn_ground_background_T_g_in_range() -> None:
    import warnings as _w

    with _w.catch_warnings():
        _w.simplefilter("error")
        # Should not raise a warning-as-error
        GroundBackground(epsilon_g=eps_lwir(), T_g=290.0)


@pytest.mark.level0
def test_warn_mwir_t1_pure_thermal() -> None:
    """T1 applied to an MWIR band emits a matrix §3.2 reclassification warning."""
    with pytest.warns(UserWarning, match="MWIR"):
        T1Thermal(
            scene_type="extended",
            target_location="terrestrial",
            h_tgt=0.0,
            epsilon=eps_mwir(),
            T_t=300.0,
        )


@pytest.mark.level0
def test_warn_mwir_t2_pure_reflective() -> None:
    with pytest.warns(UserWarning, match="MWIR"):
        T2Reflective(
            scene_type="extended",
            target_location="terrestrial",
            h_tgt=0.0,
            rho=rho_mwir(),
        )


@pytest.mark.level0
def test_no_warn_lwir_t1() -> None:
    import warnings as _w

    with _w.catch_warnings():
        _w.simplefilter("error")
        T1Thermal(
            scene_type="extended",
            target_location="terrestrial",
            h_tgt=0.0,
            epsilon=eps_lwir(),
            T_t=300.0,
        )


@pytest.mark.level0
def test_no_warn_t3_mwir_is_mandatory_model() -> None:
    """T3Mixed in MWIR is the *correct* choice — no warning should fire."""
    import warnings as _w

    with _w.catch_warnings():
        _w.simplefilter("error")
        T3Mixed(
            scene_type="extended",
            target_location="terrestrial",
            h_tgt=0.0,
            epsilon=eps_mwir(),
            T_t=300.0,
        )


# ---------------------------------------------------------------------------
# Serialization round-trip
# ---------------------------------------------------------------------------
#
# `dataclasses.asdict` recurses into nested dataclasses but does NOT know how
# to round-trip a `SpectralData` (whose fields include numpy arrays).  The
# helper below flattens SpectralData into its own `to_dict()` payload and
# rebuilds via `SpectralData.from_dict()` — this is the documented
# serialization contract for descriptor payloads.


def _descriptor_to_plain_dict(d: Any) -> dict[str, Any]:
    """Recurse through a frozen-dataclass descriptor, using SpectralData.to_dict()
    for any nested SpectralData fields.  Produces a JSON-friendly nested dict.
    """
    if isinstance(d, SpectralData):
        return d.to_dict()
    if dataclasses.is_dataclass(d) and not isinstance(d, type):
        out: dict[str, Any] = {"__class__": type(d).__name__}
        for f in dataclasses.fields(d):
            val = getattr(d, f.name)
            out[f.name] = _descriptor_to_plain_dict(val)
        return out
    if isinstance(d, list):
        return {"__list__": [_descriptor_to_plain_dict(x) for x in d]}
    # Scalar leaf (None, str, float, int, bool) — wrap so signature returns dict.
    return {"__scalar__": d}


def _rebuild_from_plain_dict(d: Any, cls: type) -> Any:
    """Inverse of _descriptor_to_plain_dict for a specific descriptor class."""
    if isinstance(d, dict) and "__class__" in d:
        kwargs: dict[str, Any] = {}
        for f in dataclasses.fields(cls):
            raw = d[f.name]
            # SpectralData fields: flat dict with wavelength + values keys.
            if isinstance(raw, dict) and "name" in raw and "wavelength_um" in raw:
                kwargs[f.name] = SpectralData.from_dict(raw)
            elif isinstance(raw, dict) and "__scalar__" in raw:
                kwargs[f.name] = raw["__scalar__"]
            elif isinstance(raw, dict) and raw.get("__class__") == "ScalarLambertianReflectance":
                kwargs[f.name] = _rebuild_from_plain_dict(raw, ScalarLambertianReflectance)
            else:
                kwargs[f.name] = raw
        return cls(**kwargs)
    raise ValueError("Unexpected payload for rebuild")


def _spectral_data_equal(a: SpectralData, b: SpectralData) -> bool:
    return (
        a.name == b.name
        and a.unit == b.unit
        and a.source == b.source
        and np.array_equal(a.wavelength_um, b.wavelength_um)
        and np.array_equal(a.values, b.values)
    )


def _descriptors_equal(a: Any, b: Any) -> bool:
    if isinstance(a, SpectralData) and isinstance(b, SpectralData):
        return _spectral_data_equal(a, b)
    if dataclasses.is_dataclass(a) and dataclasses.is_dataclass(b):
        if type(a) is not type(b):
            return False
        return all(
            _descriptors_equal(getattr(a, f.name), getattr(b, f.name))
            for f in dataclasses.fields(a)
        )
    return bool(a == b)


@pytest.mark.level0
def test_roundtrip_t1_thermal() -> None:
    orig = T1Thermal(
        scene_type="extended",
        target_location="terrestrial",
        h_tgt=0.0,
        epsilon=eps_lwir(),
        T_t=300.0,
    )
    d = _descriptor_to_plain_dict(orig)
    rebuilt = _rebuild_from_plain_dict(d, T1Thermal)
    assert _descriptors_equal(orig, rebuilt)


@pytest.mark.level0
def test_roundtrip_t2_reflective() -> None:
    orig = T2Reflective(
        scene_type="sub_pixel",
        target_location="terrestrial",
        h_tgt=0.0,
        rho=rho_vis(),
        A_t=1.5,
        shape="sphere",
    )
    d = _descriptor_to_plain_dict(orig)
    rebuilt = _rebuild_from_plain_dict(d, T2Reflective)
    assert _descriptors_equal(orig, rebuilt)


@pytest.mark.level0
def test_roundtrip_t3_mixed() -> None:
    orig = T3Mixed(
        scene_type="extended",
        target_location="terrestrial",
        h_tgt=0.0,
        epsilon=eps_mwir(),
        T_t=300.0,
    )
    d = _descriptor_to_plain_dict(orig)
    rebuilt = _rebuild_from_plain_dict(d, T3Mixed)
    assert _descriptors_equal(orig, rebuilt)


@pytest.mark.level0
def test_roundtrip_t5_at_aperture() -> None:
    orig = T5AtAperture(
        scene_type="extended",
        target_location="at_aperture",
        L_t_aperture=L_flat("L_t_aperture"),
    )
    d = _descriptor_to_plain_dict(orig)
    rebuilt = _rebuild_from_plain_dict(d, T5AtAperture)
    assert _descriptors_equal(orig, rebuilt)


@pytest.mark.level0
def test_roundtrip_at_aperture_background() -> None:
    orig = AtApertureBackground(L_bg_aperture=L_flat("L_bg"))
    d = _descriptor_to_plain_dict(orig)
    rebuilt = _rebuild_from_plain_dict(d, AtApertureBackground)
    assert _descriptors_equal(orig, rebuilt)


@pytest.mark.level0
def test_roundtrip_at_aperture_background_none() -> None:
    orig = AtApertureBackground()
    d = _descriptor_to_plain_dict(orig)
    rebuilt = _rebuild_from_plain_dict(d, AtApertureBackground)
    assert _descriptors_equal(orig, rebuilt)


@pytest.mark.level0
def test_roundtrip_cold_space_background() -> None:
    orig = ColdSpaceBackground()
    d = _descriptor_to_plain_dict(orig)
    rebuilt = _rebuild_from_plain_dict(d, ColdSpaceBackground)
    assert _descriptors_equal(orig, rebuilt)


@pytest.mark.level0
def test_roundtrip_ground_background() -> None:
    orig = GroundBackground(epsilon_g=eps_lwir(), T_g=290.0)
    d = _descriptor_to_plain_dict(orig)
    rebuilt = _rebuild_from_plain_dict(d, GroundBackground)
    assert _descriptors_equal(orig, rebuilt)


@pytest.mark.level0
def test_roundtrip_user_spectral_background() -> None:
    orig = UserSpectralBackground(L_bg=L_flat("L_bg"))
    d = _descriptor_to_plain_dict(orig)
    rebuilt = _rebuild_from_plain_dict(d, UserSpectralBackground)
    assert _descriptors_equal(orig, rebuilt)


# ---------------------------------------------------------------------------
# Matrix §7 SWIR hot-target warn (T1Thermal alone in SWIR at T_t > 700 K)
# ---------------------------------------------------------------------------


def eps_swir() -> SpectralData:
    return _sd("eps_swir", 1.0, 2.5, 0.9)


@pytest.mark.level0
def test_warn_t1_thermal_swir_hot_target() -> None:
    """Matrix §3.2 line 318: T1Thermal at SWIR with T_t > 700 K must warn."""
    with pytest.warns(UserWarning, match=r"SWIR.*700"):
        T1Thermal(
            scene_type="extended",
            target_location="terrestrial",
            h_tgt=0.0,
            epsilon=eps_swir(),
            T_t=1200.0,
        )


@pytest.mark.level0
def test_no_warn_t1_thermal_swir_cold_target() -> None:
    """T1Thermal at SWIR with T_t <= 700 K must not fire the SWIR warning."""
    import warnings as _w

    with _w.catch_warnings():
        _w.simplefilter("error", UserWarning)
        # 600 K target: below threshold; should not fire SWIR warning.
        T1Thermal(
            scene_type="extended",
            target_location="terrestrial",
            h_tgt=0.0,
            epsilon=eps_swir(),
            T_t=600.0,
        )


@pytest.mark.level0
def test_no_warn_t1_thermal_lwir_hot_target() -> None:
    """LWIR band: even with T_t > 700 K, the SWIR check must not fire."""
    import warnings as _w

    with _w.catch_warnings():
        _w.simplefilter("error", UserWarning)
        T1Thermal(
            scene_type="extended",
            target_location="terrestrial",
            h_tgt=0.0,
            epsilon=eps_lwir(),
            T_t=1200.0,
        )


# ---------------------------------------------------------------------------
# Matrix §7 θ_s > π/2 with T2Reflective (sun below horizon → zero signal)
# ---------------------------------------------------------------------------


@pytest.mark.level0
def test_warn_t2_reflective_sun_below_horizon() -> None:
    """θ_s > π/2 (sun below horizon) with T2Reflective must warn."""
    import math

    target = T2Reflective(
        scene_type="extended",
        target_location="terrestrial",
        h_tgt=0.0,
        rho=rho_vis(),
    )
    with pytest.warns(UserWarning, match=r"below the horizon"):
        warn_if_reflective_and_sun_below_horizon(target, theta_s=math.pi * 0.6)


@pytest.mark.level0
def test_no_warn_t2_reflective_sun_above_horizon() -> None:
    """θ_s = π/4 is well above horizon — no warning for T2Reflective."""
    import math
    import warnings as _w

    target = T2Reflective(
        scene_type="extended",
        target_location="terrestrial",
        h_tgt=0.0,
        rho=rho_vis(),
    )
    with _w.catch_warnings():
        _w.simplefilter("error", UserWarning)
        warn_if_reflective_and_sun_below_horizon(target, theta_s=math.pi / 4.0)


@pytest.mark.level0
def test_no_warn_t1_thermal_sun_below_horizon() -> None:
    """T1Thermal with sun below horizon: warning is T2-only, no-op for T1."""
    import math
    import warnings as _w

    target = T1Thermal(
        scene_type="extended",
        target_location="terrestrial",
        h_tgt=0.0,
        epsilon=eps_lwir(),
        T_t=300.0,
    )
    with _w.catch_warnings():
        _w.simplefilter("error", UserWarning)
        warn_if_reflective_and_sun_below_horizon(target, theta_s=math.pi * 0.6)


@pytest.mark.level0
def test_no_warn_t2_reflective_theta_s_none() -> None:
    """θ_s = None (pure-thermal scene) — helper is a no-op."""
    import warnings as _w

    target = T2Reflective(
        scene_type="extended",
        target_location="terrestrial",
        h_tgt=0.0,
        rho=rho_vis(),
    )
    with _w.catch_warnings():
        _w.simplefilter("error", UserWarning)
        warn_if_reflective_and_sun_below_horizon(target, theta_s=None)


# ---------------------------------------------------------------------------
# T6TabulatedAtSource (ADR-0003) — construction, validation, round-trip
# ---------------------------------------------------------------------------


@pytest.mark.level0
def test_t6_terrestrial_valid_construction() -> None:
    """Happy path: T6 on terrestrial LWIR with a flat L_source(λ)."""
    t = T6TabulatedAtSource(
        scene_type="extended",
        target_location="terrestrial",
        h_tgt=0.0,
        L_t_source=L_source_lwir(),
    )
    assert isinstance(t, T6TabulatedAtSource)
    assert t.L_t_source is not None
    assert t.L_t_source.values.min() >= 0.0


@pytest.mark.level0
def test_t6_no_atmosphere_space_valid_construction() -> None:
    """T6 is allowed on no_atmosphere (τ_up ≡ 1, L_path ≡ 0 → pass-through)."""
    t = T6TabulatedAtSource(
        scene_type="extended",
        target_location="no_atmosphere",
        no_atmosphere_subcase="space",
        h_tgt=0.0,
        L_t_source=L_source_lwir(),
    )
    assert t.no_atmosphere_subcase == "space"


@pytest.mark.level0
def test_t6_raise_missing_L_t_source() -> None:
    """L_t_source is required — constructor raises (Rule 15)."""
    with pytest.raises(ParameterBoundsError, match=r"L_t_source is required"):
        T6TabulatedAtSource(
            scene_type="extended",
            target_location="terrestrial",
            h_tgt=0.0,
            L_t_source=None,
        )


@pytest.mark.level0
def test_t6_raise_at_aperture_rejected() -> None:
    """T6 rejects at_aperture — that is T5's domain."""
    with pytest.raises(ParameterBoundsError, match=r"at_aperture.*not supported"):
        T6TabulatedAtSource(
            scene_type="extended",
            target_location="at_aperture",
            L_t_source=L_source_lwir(),
        )


@pytest.mark.level0
def test_t6_raise_negative_radiance() -> None:
    """Negative L_source values are unphysical and must raise (Rule 17)."""
    bad = SpectralData(
        name="L_bad",
        wavelength_um=np.array([8.0, 14.0], dtype=np.float64),
        values=np.array([1.0, -0.5], dtype=np.float64),
        unit="W/m^2/sr/um",
        source="test_t6",
    )
    with pytest.raises(ParameterBoundsError, match=r"negative or empty"):
        T6TabulatedAtSource(
            scene_type="extended",
            target_location="terrestrial",
            h_tgt=0.0,
            L_t_source=bad,
        )


@pytest.mark.level0
def test_roundtrip_t6_tabulated_at_source() -> None:
    orig = T6TabulatedAtSource(
        scene_type="sub_pixel",
        target_location="airborne",
        h_tgt=1000.0,
        L_t_source=L_source_lwir("L_t_source_rt"),
        A_t=12.0,
    )
    d = _descriptor_to_plain_dict(orig)
    rebuilt = _rebuild_from_plain_dict(d, T6TabulatedAtSource)
    assert _descriptors_equal(orig, rebuilt)
