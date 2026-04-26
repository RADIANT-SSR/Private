"""Gap H — every ``T2Reflective`` built through the inferrer has a protocol ``rho``.

The four user-facing reflective surfaces — ``source.target.reflectance``
(S4 scalar), ``source.target.albedo`` (S6 scalar alias),
``source.target.reflectance_path`` (S5 CSV), and
``source.target.albedo_path`` (S6 CSV alias) — all collapse onto
:class:`~radiant.core.descriptors.T2Reflective`.  Gap H narrows
``T2Reflective.rho`` to ``ReflectanceDescriptor | None``; this suite is
the single-place guard that every path through the inferrer (scalar +
CSV, for both aliases) produces a descriptor that satisfies the
``ReflectanceDescriptor`` protocol.

One parametrised test enforces the invariant across all four surfaces.
Mypy catches it structurally; this test catches it at runtime on real
inferrer call paths — including the CSV resample leg, which the scalar
path does not exercise.
"""

from __future__ import annotations

import warnings
from pathlib import Path

import numpy as np
import pytest

from radiant.api._param_registry import build_parameter_set
from radiant.core.descriptors import T2Reflective
from radiant.core.parameters import ParameterSet
from radiant.core.reflectance import ReflectanceDescriptor
from radiant.source._inferrer import infer_descriptors

_WL_VIS = np.linspace(0.4, 0.8, 21, dtype=np.float64)
_ZERO3 = np.zeros(3, dtype=np.float64)


def _reflective_params() -> ParameterSet:
    """Minimum ParameterSet for the reflective fast-path through the inferrer."""
    params = build_parameter_set()
    params.set("optics.aperture_diameter_m", 0.15)
    params.set("optics.focal_length_m", 0.60)
    params.set("atmosphere.model", "simple")
    params.set("geometry.sensor_altitude_m", 500.0)
    params.set("spectral_integration.filter_min_um", 0.4)
    params.set("spectral_integration.filter_max_um", 0.9)
    params.set("spectral_integration.integration_time_s", 1e-3)
    params.set("detector.pixel_pitch_x_um", 5.5)
    params.set("detector.pixel_pitch_y_um", 5.5)
    params.set("detector.qe_value", 0.8)
    params.set("source.scene_type", "extended")
    params.set("source.target_location", "terrestrial")
    return params


def _write_flat_rho_csv(path: Path, *, rho_value: float) -> Path:
    """Write a 4-row CSV bracketing _WL_VIS with constant ρ."""
    path.write_text(
        "wavelength_um,reflectance\n"
        f"0.300000,{rho_value:.6f}\n"
        f"0.400000,{rho_value:.6f}\n"
        f"0.800000,{rho_value:.6f}\n"
        f"0.900000,{rho_value:.6f}\n"
    )
    return path


@pytest.mark.level0
@pytest.mark.parametrize(
    "surface",
    ["reflectance", "albedo", "reflectance_path", "albedo_path"],
)
def test_every_t2_rho_is_reflectance_descriptor(surface: str, tmp_path: Path) -> None:
    """Gap H invariant: T2.rho is a ReflectanceDescriptor for every user surface.

    For each of the four reflective user surfaces, drive the inferrer,
    then assert:
      - ``target`` is a ``T2Reflective``;
      - ``target.rho`` satisfies the ``ReflectanceDescriptor`` protocol;
      - ``target.rho.reflectance_at(WL, zero, zero)`` returns an array
        with the chain-grid shape and values in [0, 1].
    """
    params = _reflective_params()
    rho_value = 0.3

    if surface == "reflectance":
        params.set("source.target.reflectance", rho_value)
    elif surface == "albedo":
        params.set("source.target.albedo", rho_value)
    elif surface == "reflectance_path":
        csv = _write_flat_rho_csv(tmp_path / "rho.csv", rho_value=rho_value)
        params.set("source.target.reflectance_path", str(csv))
    elif surface == "albedo_path":
        csv = _write_flat_rho_csv(tmp_path / "alb.csv", rho_value=rho_value)
        params.set("source.target.albedo_path", str(csv))
    params.resolve()

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        target, _bg, _los = infer_descriptors(params, _WL_VIS)

    assert isinstance(target, T2Reflective)
    assert target.rho is not None
    assert isinstance(target.rho, ReflectanceDescriptor)

    rho_on_grid = target.rho.reflectance_at(_WL_VIS, _ZERO3, _ZERO3)
    assert rho_on_grid.shape == _WL_VIS.shape
    assert float(rho_on_grid.min()) >= 0.0
    assert float(rho_on_grid.max()) <= 1.0
    np.testing.assert_allclose(
        rho_on_grid,
        np.full_like(_WL_VIS, rho_value),
        rtol=1e-12,
        atol=1e-12,
    )
