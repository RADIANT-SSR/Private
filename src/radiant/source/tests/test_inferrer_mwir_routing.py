"""Level-0 routing tests for CU-007: MWIR-overlap targets default to T3Mixed.

Per matrix §3.2 ("MWIR ambient → T3 mandatory"), the legacy ε+T scalar
input surface in
:func:`radiant.source._inferrer._build_target_descriptor` now routes
MWIR-overlap wavelength grids to :class:`T3Mixed` by default.  The
hot-target opt-out lives at the new ``source.target.is_hot_target``
schema parameter.

The tests are anchors A1–A5 from
[docs/CU-007_MWIR_T3Mixed_Routing_Task.md](../../../../docs/CU-007_MWIR_T3Mixed_Routing_Task.md):

* A1 — MWIR + ``is_hot_target`` default false → ``T3Mixed`` (was ``T1Thermal`` pre-fix).
* A2 — MWIR + ``is_hot_target=True``           → ``T1Thermal``.
* A3 — LWIR (8–12 µm)                          → ``T1Thermal`` regardless of flag.
* A4 — Suppression-removal guard:
    - A1 case fires zero MWIR ``UserWarning`` (T3Mixed has no warning).
    - A2 case fires exactly one MWIR ``UserWarning`` (T1Thermal opt-in).
* A5 — LWIR case fires zero ``UserWarning`` (regression guard).

Pre-fix expected behavior (for the discipline note in the commit body):
A1 returns ``T1Thermal`` and the A1/A2 warning checks both come back
silent because the legacy ``warnings.catch_warnings()`` wrapper in
``_build_target_descriptor`` gags every MWIR warning.  Post-fix, A1
returns ``T3Mixed`` (matrix-default) and A2 surfaces the warning that
Rule 17 says the user should see when they opt into T1Thermal against
the matrix.
"""

from __future__ import annotations

import warnings

import numpy as np
import pytest

from radiant.api._param_registry import build_parameter_set
from radiant.core.descriptors import T1Thermal, T3Mixed
from radiant.core.parameters import ParameterSet
from radiant.source._inferrer import _build_target_descriptor

# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------


def _populate_required_groups(params: ParameterSet) -> None:
    """Populate the minimum fields needed to satisfy ParameterSet.resolve().

    Mirrors the pattern in :mod:`test_inferrer_los_routing` — the f-number
    consistency group plus a handful of required None-defaulted fields.
    """
    params.set("optics.aperture_diameter_m", 0.15)
    params.set("optics.focal_length_m", 0.60)
    params.set("atmosphere.model", "simple")
    params.set("geometry.sensor_altitude_m", 500.0)
    params.set("spectral_integration.filter_min_um", 3.0)
    params.set("spectral_integration.filter_max_um", 5.0)
    params.set("spectral_integration.integration_time_s", 1e-3)
    params.set("detector.pixel_pitch_x_um", 5.5)
    params.set("detector.pixel_pitch_y_um", 5.5)
    params.set("detector.qe_value", 0.8)


def _mwir_params(*, is_hot_target: bool | None = None) -> tuple[ParameterSet, np.ndarray]:
    """Build a minimal MWIR ParameterSet + wavelength grid."""
    params = build_parameter_set()
    _populate_required_groups(params)
    params.set("source.target.temperature", 290.0)
    params.set("source.target.emissivity", 0.95)
    if is_hot_target is not None:
        params.set("source.target.is_hot_target", is_hot_target)
    params.resolve()
    wl = np.linspace(3.0, 5.0, 11)
    return params, wl


def _lwir_params(*, is_hot_target: bool | None = None) -> tuple[ParameterSet, np.ndarray]:
    """Build a minimal LWIR ParameterSet + wavelength grid."""
    params = build_parameter_set()
    _populate_required_groups(params)
    params.set("source.target.temperature", 300.0)
    params.set("source.target.emissivity", 0.95)
    if is_hot_target is not None:
        params.set("source.target.is_hot_target", is_hot_target)
    params.resolve()
    wl = np.linspace(8.0, 12.0, 11)
    return params, wl


def _build(params: ParameterSet, wl: np.ndarray) -> object:
    return _build_target_descriptor(
        params=params,
        wavelength_um=wl,
        scene_type="extended",
        target_location="terrestrial",
        no_atmosphere_subcase="",
        h_tgt=0.0,
    )


# ---------------------------------------------------------------------------
# A1 — MWIR-default routes to T3Mixed
# ---------------------------------------------------------------------------


@pytest.mark.level0
class TestA1MwirDefaultRoutesT3Mixed:
    def test_default_isHotTarget_is_false(self) -> None:
        params, _ = _mwir_params()
        assert params.get("source.target.is_hot_target") is False

    def test_mwir_default_returns_T3Mixed(self) -> None:
        params, wl = _mwir_params()
        descriptor = _build(params, wl)
        assert isinstance(descriptor, T3Mixed), (
            f"MWIR default must route to T3Mixed (matrix §3.2); got {type(descriptor).__name__}"
        )

    def test_mwir_default_T3_carries_grey_epsilon(self) -> None:
        params, wl = _mwir_params()
        descriptor = _build(params, wl)
        assert isinstance(descriptor, T3Mixed)
        assert descriptor.epsilon is not None
        assert descriptor.epsilon.values.shape == wl.shape
        assert np.allclose(descriptor.epsilon.values, 0.95)


# ---------------------------------------------------------------------------
# A2 — MWIR + is_hot_target=True routes to T1Thermal
# ---------------------------------------------------------------------------


@pytest.mark.level0
class TestA2MwirHotTargetRoutesT1Thermal:
    def test_mwir_hot_target_returns_T1Thermal(self) -> None:
        params, wl = _mwir_params(is_hot_target=True)
        descriptor = _build(params, wl)
        assert isinstance(descriptor, T1Thermal), (
            f"MWIR + is_hot_target=True must route to T1Thermal "
            f"(legacy hot-target path); got {type(descriptor).__name__}"
        )


# ---------------------------------------------------------------------------
# A3 — LWIR routes to T1Thermal regardless of is_hot_target
# ---------------------------------------------------------------------------


@pytest.mark.level0
class TestA3LwirAlwaysT1Thermal:
    def test_lwir_default_returns_T1Thermal(self) -> None:
        params, wl = _lwir_params()
        descriptor = _build(params, wl)
        assert isinstance(descriptor, T1Thermal), (
            f"LWIR routing is unchanged; expected T1Thermal, got {type(descriptor).__name__}"
        )

    def test_lwir_with_hot_target_flag_still_T1Thermal(self) -> None:
        params, wl = _lwir_params(is_hot_target=True)
        descriptor = _build(params, wl)
        assert isinstance(descriptor, T1Thermal), (
            f"is_hot_target=True must not change LWIR routing; got {type(descriptor).__name__}"
        )


# ---------------------------------------------------------------------------
# A4 — Warning surfaces when (and only when) the user opts into T1Thermal-MWIR
# ---------------------------------------------------------------------------


def _mwir_user_warnings(messages: list[warnings.WarningMessage]) -> list[str]:
    """Return MWIR-routing UserWarning messages emitted during the call."""
    return [
        str(w.message)
        for w in messages
        if issubclass(w.category, UserWarning)
        and "spectral band overlapping the MWIR" in str(w.message)
    ]


@pytest.mark.level0
class TestA4MwirWarningSurfaces:
    def test_mwir_default_emits_zero_mwir_warnings(self) -> None:
        params, wl = _mwir_params()
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            _build(params, wl)
        mwir_msgs = _mwir_user_warnings(caught)
        assert mwir_msgs == [], (
            "T3Mixed routing must not trigger the MWIR-non-mixed warning "
            f"(T3 is the matrix-recommended descriptor); got {mwir_msgs!r}"
        )

    def test_mwir_hot_target_notes_exactly_one_mwir_advisory(self, caplog) -> None:  # type: ignore[no-untyped-def]
        """is_hot_target=True surfaces the matrix-§3.2 advisory as a debug log note,
        not a per-evaluate UserWarning (warning-free-UX campaign)."""
        import logging

        params, wl = _mwir_params(is_hot_target=True)
        with warnings.catch_warnings():
            warnings.simplefilter("error", UserWarning)  # must NOT warn
            with caplog.at_level(logging.DEBUG, logger="radiant.core.descriptors"):
                _build(params, wl)
        mwir_msgs = [
            r.message for r in caplog.records if "spectral band overlapping the MWIR" in r.message
        ]
        assert len(mwir_msgs) == 1, mwir_msgs
        assert "T3Mixed" in mwir_msgs[0]


# ---------------------------------------------------------------------------
# A5 — LWIR fires no MWIR warning (regression guard)
# ---------------------------------------------------------------------------


@pytest.mark.level0
class TestA5LwirNoMwirWarning:
    def test_lwir_emits_zero_mwir_warnings(self) -> None:
        params, wl = _lwir_params()
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            _build(params, wl)
        mwir_msgs = _mwir_user_warnings(caught)
        assert mwir_msgs == [], (
            f"LWIR routing must never trigger the MWIR-non-mixed warning; got {mwir_msgs!r}"
        )


# ---------------------------------------------------------------------------
# Boundary cases (failure-mode coverage from CU-007 task §Failure modes)
# ---------------------------------------------------------------------------


@pytest.mark.level0
class TestBoundaryConditions:
    def test_lambda_min_exactly_3um_routes_T3Mixed(self) -> None:
        # Wavelength grid lower edge sits exactly at the MWIR boundary
        # per _is_mwir_spectral_data's `lam.min() <= 3.0` predicate.
        params = build_parameter_set()
        _populate_required_groups(params)
        params.set("source.target.temperature", 290.0)
        params.set("source.target.emissivity", 0.95)
        params.resolve()
        wl = np.linspace(3.0, 4.0, 5)
        descriptor = _build(params, wl)
        assert isinstance(descriptor, T3Mixed)

    def test_grid_spanning_mwir_and_lwir_routes_T3Mixed(self) -> None:
        # The MWIR-overlap predicate is "any wavelength in 1-3 µm range";
        # mid-MWIR-through-LWIR scans still trigger T3Mixed (matrix wins).
        params = build_parameter_set()
        _populate_required_groups(params)
        params.set("source.target.temperature", 290.0)
        params.set("source.target.emissivity", 0.95)
        params.resolve()
        wl = np.linspace(3.0, 10.0, 11)
        descriptor = _build(params, wl)
        assert isinstance(descriptor, T3Mixed)
