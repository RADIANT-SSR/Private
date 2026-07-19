"""Gap H — reflectance boundary converter wrap assertions.

Complements the existing scalar-lift / CSV coverage in the inferrer test
suite.  Gap H (2026-04-23) narrows ``T2Reflective.rho`` to
``ReflectanceDescriptor | None``; the boundary converter is the single
wrap site.  These tests protect the three Category-B-level invariants
spelled out in the Gap H plan:

1. A ``SpectralData`` ρ(λ) input yields a ``T2Reflective`` whose ``rho``
   is a ``ScalarLambertianReflectance`` (and thus satisfies the
   ``ReflectanceDescriptor`` protocol).
2. ``ScalarLambertianReflectance.reflectance_at`` returns the stored
   ``SpectralData.values`` bit-identically on the native grid — the
   proof that the adapter does not drift physics.
3. The MWIR §3.2 "use T3Mixed unless ε ≈ 0" warning fires at the wrap
   site when the stored grid overlaps 3–5 µm (the warning relocated
   from ``T2Reflective.__post_init__``'s SpectralData branch, which
   Gap H removed).
"""

from __future__ import annotations

import warnings

import numpy as np
import pytest

from radiant.core.descriptors import T2Reflective
from radiant.core.reflectance import (
    ReflectanceDescriptor,
    ScalarLambertianReflectance,
)
from radiant.core.spectral import SpectralData
from radiant.source.converters.reflectance import reflectance_to_descriptor

_ZERO3 = np.zeros(3, dtype=np.float64)


def _sd(wl: np.ndarray, value: float) -> SpectralData:
    return SpectralData(
        name="test.reflectance",
        wavelength_um=wl,
        values=np.full_like(wl, value, dtype=np.float64),
        unit="dimensionless",
        source="test_reflectance_converter",
    )


@pytest.mark.level0
def test_spectraldata_input_yields_scalar_lambertian_wrap() -> None:
    """Invariant (1): converter wraps SpectralData into the adapter."""
    wl = np.linspace(0.4, 0.7, 8, dtype=np.float64)
    rho_sd = _sd(wl, 0.3)

    target = reflectance_to_descriptor(
        rho=rho_sd,
        wavelength_um=wl,
        scene_type="extended",
        target_location="terrestrial",
        h_tgt=0.0,
    )

    assert isinstance(target, T2Reflective)
    assert isinstance(target.rho, ScalarLambertianReflectance)
    assert isinstance(target.rho, ReflectanceDescriptor)


@pytest.mark.level0
def test_reflectance_at_round_trips_bit_identical_on_native_grid() -> None:
    """Invariant (2): protocol returns stored values bit-identical on native grid."""
    wl = np.linspace(0.4, 0.7, 8, dtype=np.float64)
    rho_sd = _sd(wl, 0.42)

    target = reflectance_to_descriptor(
        rho=rho_sd,
        wavelength_um=wl,
        scene_type="extended",
        target_location="terrestrial",
        h_tgt=0.0,
    )
    assert target.rho is not None

    r = target.rho.reflectance_at(wl, _ZERO3, _ZERO3)
    np.testing.assert_array_equal(r, rho_sd.values)


@pytest.mark.level0
def test_mwir_warn_fires_at_wrap_site(caplog) -> None:  # type: ignore[no-untyped-def]
    """Invariant (3): MWIR §3.2 warning fires at T2Reflective construction.

    Gap H relocates the warning from the ``SpectralData`` branch of
    ``__post_init__`` (removed) to the adapter branch.  Functionally
    identical — the converter builds the adapter, hands it to
    ``T2Reflective``, ``__post_init__`` sees a ``ScalarLambertianReflectance``
    and runs ``_warn_mwir_non_mixed`` on its stored grid.
    """
    wl_mwir = np.linspace(3.5, 4.5, 8, dtype=np.float64)
    rho_sd = _sd(wl_mwir, 0.2)

    import logging

    with caplog.at_level(logging.DEBUG, logger="radiant.core.descriptors"):
        reflectance_to_descriptor(
            rho=rho_sd,
            wavelength_um=wl_mwir,
            scene_type="extended",
            target_location="terrestrial",
            h_tgt=0.0,
        )
    assert any("MWIR" in r.message for r in caplog.records)


@pytest.mark.level0
def test_no_mwir_warn_on_vis_grid() -> None:
    """Regression: no MWIR warning on a pure-VIS grid."""
    wl_vis = np.linspace(0.4, 0.7, 8, dtype=np.float64)
    rho_sd = _sd(wl_vis, 0.3)

    with warnings.catch_warnings():
        warnings.simplefilter("error", UserWarning)
        reflectance_to_descriptor(
            rho=rho_sd,
            wavelength_um=wl_vis,
            scene_type="extended",
            target_location="terrestrial",
            h_tgt=0.0,
        )
