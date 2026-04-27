"""Level-0 tests for CU-009 — `_infer_los` routing through `geometry.*` params.

CU-009 wires SourceStage's `_infer_los` to read three already-registered
`geometry.*` parameters (canonically owned by AtmosphereStage's schema)
instead of hardcoding nadir / no-solar geometry:

    * ``geometry.path_zenith_rad``  → ``LineOfSightGeometry.theta_o``
    * ``geometry.solar_zenith_rad`` → ``LineOfSightGeometry.theta_s``  (T2/T3 only)
    * ``geometry.solar_azimuth_rad``→ ``LineOfSightGeometry.delta_phi`` (T2/T3 only)

The "T2/T3 only" predicate honors :class:`LineOfSightGeometry`'s docstring
intent (``theta_s`` / ``delta_phi`` are ``None`` for pure-thermal scenarios
where the sun is not used).  T1Thermal targets retain ``None`` regardless
of the registered solar params, so all 14 baseline scenarios + Cells 28/58
remain bit-invariant under defaults.

The latent-finding fix (`_view_direction_from_los` now reads from the
canonical `geometry.path_zenith_rad` instead of the unregistered
`geometry.observer_zenith_rad`) is covered by A9.

See: docs/CU-009_Observer_Geometry_Schema_Task.md, anchors A1–A9.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from radiant.api._param_registry import build_parameter_set
from radiant.core.descriptors import T1Thermal, T2Reflective, T3Mixed
from radiant.core.los_geometry import LineOfSightGeometry
from radiant.core.parameters import ParameterBoundsError, ParameterSet
from radiant.core.spectral import SpectralData
from radiant.source._inferrer import _infer_los, _view_direction_from_los
from radiant.source.converters.reflectance import reflectance_to_descriptor

_WL_GREY = np.linspace(8.0, 12.0, 11)  # LWIR band — keeps T1Thermal silent.
_WL_MWIR = np.linspace(3.0, 5.0, 11)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _los_params(*, resolve: bool = True) -> ParameterSet:
    """Return a ParameterSet carrying the AtmosphereStage `geometry.*` schema.

    `_infer_los` reads three `geometry.*` params via ``params.get(...)``,
    which requires a resolved ParameterSet.  We populate the minimum
    fields needed to satisfy ``resolve()`` (the f-number consistency
    group plus a handful of None-defaulted required fields) and
    optionally resolve before returning.

    Set ``resolve=False`` to defer resolution — useful for A7 cases
    that need to inject an out-of-range value before resolving.
    """
    params = build_parameter_set()
    # f-number consistency group — supply two of three.
    params.set("optics.aperture_diameter_m", 0.15)
    params.set("optics.focal_length_m", 0.60)
    # None-defaulted fields required for resolve() to succeed.
    params.set("atmosphere.model", "simple")
    params.set("geometry.sensor_altitude_m", 500.0)
    params.set("spectral_integration.filter_min_um", 0.4)
    params.set("spectral_integration.filter_max_um", 0.9)
    params.set("spectral_integration.integration_time_s", 1e-3)
    params.set("detector.pixel_pitch_x_um", 5.5)
    params.set("detector.pixel_pitch_y_um", 5.5)
    params.set("detector.qe_value", 0.8)
    if resolve:
        params.resolve()
    return params


def _grey_epsilon(wavelength_um: np.ndarray, value: float = 0.95) -> SpectralData:
    """Build a grey ε(λ) SpectralData on the given grid."""
    return SpectralData(
        name="test.epsilon",
        wavelength_um=wavelength_um,
        values=np.full(wavelength_um.shape, float(value), dtype=np.float64),
        unit="",
        source="test_inferrer_los_routing",
    )


def _set_geometry(
    params: ParameterSet,
    *,
    path_zenith_rad: float | None = None,
    solar_zenith_rad: float | None = None,
    solar_azimuth_rad: float | None = None,
) -> None:
    """Set geometry params on an already-resolved ParameterSet, then re-resolve.

    ``params.set`` clears the resolved flag; tests that set values after
    initial resolution must re-resolve before calling helpers that read
    via ``params.get``.
    """
    if path_zenith_rad is not None:
        params.set("geometry.path_zenith_rad", path_zenith_rad)
    if solar_zenith_rad is not None:
        params.set("geometry.solar_zenith_rad", solar_zenith_rad)
    if solar_azimuth_rad is not None:
        params.set("geometry.solar_azimuth_rad", solar_azimuth_rad)
    params.resolve()


def _t1_thermal() -> T1Thermal:
    """Build a minimal LWIR T1Thermal target (silent — no MWIR/SWIR warnings)."""
    return T1Thermal(
        scene_type="extended",
        target_location="terrestrial",
        h_tgt=0.0,
        epsilon=_grey_epsilon(_WL_GREY),
        T_t=300.0,
    )


def _t3_mixed_mwir() -> T3Mixed:
    """Build an MWIR T3Mixed target (matrix §3.2: T3 is mandatory in MWIR)."""
    return T3Mixed(
        scene_type="extended",
        target_location="terrestrial",
        h_tgt=0.0,
        epsilon=_grey_epsilon(_WL_MWIR, value=0.95),
        T_t=290.0,
    )


def _t2_reflective_vis() -> T2Reflective:
    """Build a VIS T2Reflective target via the boundary converter."""
    wl = np.linspace(0.4, 0.8, 21)
    target = reflectance_to_descriptor(
        rho=0.3,
        wavelength_um=wl,
        scene_type="extended",
        target_location="terrestrial",
        h_tgt=0.0,
    )
    assert isinstance(target, T2Reflective)
    return target


# ---------------------------------------------------------------------------
# A1 — default params, T1Thermal: no solar geometry, nadir baseline.
# ---------------------------------------------------------------------------


class TestA1DefaultParamsT1Baseline:
    """A1 — default params + T1Thermal returns the nadir / None-solar baseline.

    Documents the back-compat invariant that protects Cells 28/58 and all
    14 LWIR / MWIR-as-T1 baseline rows: under schema defaults
    (``path_zenith_rad=0.0``, ``solar_zenith_rad=0.5``, ``solar_azimuth_rad=0.0``)
    a T1Thermal target produces ``theta_o=0``, ``theta_s=None``,
    ``delta_phi=None`` — bit-identical to the pre-fix hardcode.
    """

    def test_default_params_t1_returns_baseline_los(self) -> None:
        params = _los_params()
        target = _t1_thermal()

        los = _infer_los("terrestrial", params, target_descriptor=target)

        assert los is not None
        assert los.h_tgt == 0.0
        assert los.theta_o == 0.0
        assert los.theta_s is None
        assert los.delta_phi is None
        assert los.h_atm_top == 1.0e5  # Kármán default — not overridden in CU-009.


# ---------------------------------------------------------------------------
# A2 — non-default path zenith, T1Thermal: theta_o reads, theta_s stays None.
# ---------------------------------------------------------------------------


class TestA2NonDefaultPathZenithT1:
    """A2 — T1Thermal honors ``theta_o`` but ignores solar geometry.

    Even when ``geometry.solar_zenith_rad`` is non-default, a T1Thermal
    target's LOS leaves ``theta_s = None``.  This is the predicate that
    keeps MWIR-as-T1 baseline rows bit-invariant: solar params *exist* in
    schema but do not propagate to the T1 LOS.
    """

    def test_path_zenith_propagates_theta_s_stays_none_for_t1(self) -> None:
        params = _los_params()
        # Set solar params to non-default — A2 asserts they DO NOT propagate
        # for a T1Thermal target.
        _set_geometry(
            params,
            path_zenith_rad=0.4,
            solar_zenith_rad=0.7,
            solar_azimuth_rad=0.5,
        )
        target = _t1_thermal()

        los = _infer_los("terrestrial", params, target_descriptor=target)

        assert los is not None
        assert los.theta_o == pytest.approx(0.4, rel=0.0, abs=0.0)
        assert los.theta_s is None
        assert los.delta_phi is None


# ---------------------------------------------------------------------------
# A3 — T3Mixed target: full geometry plumbed (theta_o, theta_s, delta_phi).
# ---------------------------------------------------------------------------


class TestA3T3MixedFullGeometry:
    """A3 — T3Mixed routes all three geometry params into the LOS.

    The MWIR mixed path consumes ``theta_s`` for its solar leg
    (``_assemble_t3``).  Once CU-007 lands and routes MWIR scenarios to
    T3Mixed, this is the path that delivers the correct solar zenith.
    """

    def test_t3_mixed_propagates_path_solar_zenith_and_azimuth(self) -> None:
        params = _los_params()
        _set_geometry(
            params,
            path_zenith_rad=0.3,
            solar_zenith_rad=0.6,
            solar_azimuth_rad=0.5,
        )
        target = _t3_mixed_mwir()

        los = _infer_los("terrestrial", params, target_descriptor=target)

        assert los is not None
        assert los.theta_o == pytest.approx(0.3, rel=0.0, abs=0.0)
        assert los.theta_s == pytest.approx(0.6, rel=0.0, abs=0.0)
        assert los.delta_phi == pytest.approx(0.5, rel=0.0, abs=0.0)


# ---------------------------------------------------------------------------
# A4 — T2Reflective target: same predicate as T3Mixed (solar fields propagate).
# ---------------------------------------------------------------------------


class TestA4T2ReflectiveFullGeometry:
    """A4 — T2Reflective routes all three geometry params into the LOS.

    Pure-reflective targets need the sun's geometry just as mixed targets
    do — the Lambertian / BRDF evaluation is solar-geometry-dependent.
    Same routing predicate as A3.
    """

    def test_t2_reflective_propagates_path_solar_zenith_and_azimuth(self) -> None:
        params = _los_params()
        _set_geometry(
            params,
            path_zenith_rad=0.3,
            solar_zenith_rad=0.6,
            solar_azimuth_rad=0.5,
        )
        target = _t2_reflective_vis()

        los = _infer_los("terrestrial", params, target_descriptor=target)

        assert los is not None
        assert los.theta_o == pytest.approx(0.3, rel=0.0, abs=0.0)
        assert los.theta_s == pytest.approx(0.6, rel=0.0, abs=0.0)
        assert los.delta_phi == pytest.approx(0.5, rel=0.0, abs=0.0)


# ---------------------------------------------------------------------------
# A5 — at_aperture pass-through: returns None regardless of geometry params.
# ---------------------------------------------------------------------------


class TestA5AtAperturePassThrough:
    """A5 — ``target_location='at_aperture'`` returns None unconditionally.

    The at-aperture arm never evaluates an atmospheric path (matrix §4.3
    line 356); ``_infer_los`` returns ``None`` even when the schema
    carries non-default geometry values.
    """

    def test_at_aperture_returns_none_with_non_default_params(self) -> None:
        params = _los_params()
        _set_geometry(
            params,
            path_zenith_rad=0.4,
            solar_zenith_rad=0.7,
            solar_azimuth_rad=0.5,
        )
        # at_aperture skips the descriptor build; pass None to mimic the
        # pre-descriptor call site.
        los = _infer_los("at_aperture", params, target_descriptor=None)

        assert los is None


# ---------------------------------------------------------------------------
# A6 — no_atmosphere: routing predicate is the same as terrestrial.
# ---------------------------------------------------------------------------


class TestA6NoAtmosphereRouting:
    """A6 — ``target_location='no_atmosphere'`` follows the same T1/T2/T3 rule.

    The no_atmosphere matrix arm (§7) does not zero out the LOS; the
    routing predicate operates on the descriptor type, not the location.
    h_tgt stays at 0 per matrix §7 (the "above everything" convention).
    """

    def test_no_atmosphere_t1_returns_los_with_none_solar(self) -> None:
        params = _los_params()
        _set_geometry(
            params,
            path_zenith_rad=0.3,
            solar_zenith_rad=0.6,
            solar_azimuth_rad=0.5,
        )
        target = _t1_thermal()

        los = _infer_los("no_atmosphere", params, target_descriptor=target)

        assert los is not None
        assert los.theta_o == pytest.approx(0.3, rel=0.0, abs=0.0)
        assert los.theta_s is None
        assert los.delta_phi is None


# ---------------------------------------------------------------------------
# A7 — out-of-range geometry params surface loudly (no silent clamp).
# ---------------------------------------------------------------------------


class TestA7OutOfRangeRaises:
    """A7 — out-of-range geometry params raise rather than being clamped.

    Two safety nets:
      * ParameterSet bounds (input layer) reject negative or
        > π/2 path zenith.
      * ``LineOfSightGeometry.__post_init__`` (dataclass invariant)
        catches anything that bypasses the schema.

    Both are tested so that the "out-of-range surfaces loudly" intent is
    enforced no matter which path a future caller takes.
    """

    def test_negative_path_zenith_rejected_at_resolve(self) -> None:
        params = _los_params(resolve=False)
        params.set("geometry.path_zenith_rad", -0.1)
        with pytest.raises(ValueError, match=r"out of bounds"):
            params.resolve()

    def test_path_zenith_above_schema_upper_bound_rejected(self) -> None:
        params = _los_params(resolve=False)
        # Schema upper bound is 1.562 rad (~89.5°); π/2 ≈ 1.5708 exceeds it.
        params.set("geometry.path_zenith_rad", math.pi / 2.0)
        with pytest.raises(ValueError, match=r"out of bounds"):
            params.resolve()

    def test_los_dataclass_rejects_negative_theta_o(self) -> None:
        # Defence in depth: even if the schema is bypassed, the dataclass
        # invariant must reject negative theta_o.
        with pytest.raises(ParameterBoundsError, match=r"theta_o"):
            LineOfSightGeometry(h_tgt=0.0, theta_o=-0.1)


# ---------------------------------------------------------------------------
# A8 — limit case: theta_o = π/2 - ε constructs (dataclass half-open guard).
# ---------------------------------------------------------------------------


class TestA8HalfOpenIntervalLimit:
    """A8 — the LOS half-open interval ``[0, π/2)`` works at the limit.

    Bypasses the (tighter) schema bound to exercise the dataclass
    invariant directly.  Verifies that at θ_o just below π/2 the
    dataclass constructs and ``path_airmass_up`` is finite.
    """

    def test_theta_o_just_below_horizon_is_finite(self) -> None:
        theta_o = math.pi / 2.0 - 1e-12
        los = LineOfSightGeometry(h_tgt=0.0, theta_o=theta_o)
        airmass = los.path_airmass_up
        assert math.isfinite(airmass)
        assert airmass > 1.0  # secant grows large but not infinite.


# ---------------------------------------------------------------------------
# A9 — _view_direction_from_los reads `geometry.path_zenith_rad` (latent fix).
# ---------------------------------------------------------------------------


class TestA9ViewDirectionFromCanonicalParam:
    """A9 — ``_view_direction_from_los`` reads the canonical param.

    Pre-fix: the function read the unregistered ``geometry.observer_zenith_rad``
    with a silent ``KeyError → 0.0`` fallback (Rule-12 + Rule-17 violation).
    Post-fix: it reads ``geometry.path_zenith_rad``, the canonical name
    that the rest of the chain already consumes.  At ``theta_o = θ`` the
    target→observer unit vector is ``(sin θ, 0, cos θ)`` exactly.
    """

    def test_view_direction_uses_path_zenith_rad(self) -> None:
        params = _los_params()
        _set_geometry(params, path_zenith_rad=0.5)

        view_dir = _view_direction_from_los(params, "terrestrial")

        expected = np.array([math.sin(0.5), 0.0, math.cos(0.5)], dtype=np.float64)
        np.testing.assert_allclose(view_dir, expected, rtol=0.0, atol=1e-15)

    def test_view_direction_default_is_nadir(self) -> None:
        # With no override, default geometry.path_zenith_rad = 0 → +Z view.
        params = _los_params()
        view_dir = _view_direction_from_los(params, "terrestrial")
        np.testing.assert_array_equal(view_dir, np.array([0.0, 0.0, 1.0]))
