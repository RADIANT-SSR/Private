"""Level 0 — SourceStage publishes the resolved target reflectance ρ(λ).

Owner walkthrough item 6: the GUI's reflective view must plot the *surface
property* the analyst set, not the at-aperture radiance it eventually
produces.  Nothing published ρ(λ) as an array before; it lived only inside the
descriptors (``T2Reflective.rho``, and Kirchhoff ρ = 1 − ε for ``T3Mixed``).
``stage_outputs["source"]["reflectance"]`` closes that, resolved through the
single :mod:`radiant.core.target_reflectance` resolver the radiance path also
uses (Rule 19), so the plotted curve cannot drift from the ρ the chain
integrates.

Key equations under test (hand values, not RADIANT-computed — Rule 18):

* **T2Reflective** — a scalar ρ lifts to a flat spectrum: ρ(λ) ≡ ρ on every
  grid point.  A ρ(λ) CSV resamples onto the chain grid with no smoothing.
* **T3Mixed** — Kirchhoff (Rule 5): ρ(λ) = 1 − ε(λ) elementwise.  ε = 0.95 ⇒
  ρ = 0.05 exactly; ε = 0.7 ⇒ ρ = 0.3 exactly.
* **Everything else** — the output is *absent*, never a fabricated zero: T1 is
  pure-thermal, and T5/T6/T7 supply radiance or intensity with no surface
  property at all.

ρ is dimensionless on both pathways (no unit conversion anywhere — Rule 2).
"""

from __future__ import annotations

import warnings

import numpy as np
import pytest

from radiant.core.chain import ChainState
from radiant.core.parameters import ParameterSet
from radiant.core.spectral import SpectralData
from radiant.detector._schema import ALL_PARAMETERS as DET_PARAMS
from radiant.geometry._schema import ALL_PARAMETERS as GEO_PARAMS
from radiant.optics._schema import ALL_PARAMETERS as OPT_PARAMS
from radiant.source._schema import ALL_PARAMETERS as SRC_PARAMS
from radiant.source.stage import SourceStage

_WL_VIS = np.linspace(0.4, 0.9, 26)
_WL_MWIR = np.linspace(3.0, 5.0, 21)


def _base_params() -> ParameterSet:
    """A ParameterSet with everything SourceStage needs but no target spec."""
    from radiant.api._param_registry import _FNUMBER_GROUP

    schema = list(GEO_PARAMS) + list(SRC_PARAMS) + list(OPT_PARAMS) + list(DET_PARAMS)
    ps = ParameterSet(schema, [_FNUMBER_GROUP])
    ps.set("geometry.sensor_altitude_m", 500_000.0)
    ps.set("geometry.target_altitude_m", 0.0)
    ps.set("detector.pixel_pitch_x_um", 18.0)
    ps.set("detector.pixel_pitch_y_um", 18.0)
    ps.set("detector.qe_value", 0.7)
    ps.set("optics.focal_length_m", 1.2)
    ps.set("optics.aperture_diameter_m", 0.3)
    ps.set("optics.transmission_scalar", 0.7)
    return ps


def _run(params: ParameterSet, wl: np.ndarray) -> ChainState:
    params.resolve()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        return SourceStage().run(ChainState(wavelength_um=wl), params)


def _published(state: ChainState) -> SpectralData | None:
    return state.stage_outputs["source"].get("reflectance")


# ---------------------------------------------------------------------------
# Pathway 1 — T2Reflective (the ReflectanceDescriptor protocol)
# ---------------------------------------------------------------------------


class TestReflectivePathway:
    @pytest.mark.level0
    def test_scalar_rho_publishes_flat_spectrum_on_the_chain_grid(self) -> None:
        """ρ = 0.42 ⇒ ρ(λ) ≡ 0.42 on every chain grid point, exactly."""
        params = _base_params()
        params.set("source.target.reflectance", 0.42)
        state = _run(params, _WL_VIS)

        rho = _published(state)
        assert rho is not None, "a pure-reflective target must publish ρ(λ)"
        np.testing.assert_array_equal(rho.values, np.full_like(_WL_VIS, 0.42))
        np.testing.assert_array_equal(rho.wavelength_um, _WL_VIS)

    @pytest.mark.level0
    def test_published_rho_is_dimensionless(self) -> None:
        """Dimensional audit: ρ carries no unit on either pathway (Rule 2)."""
        params = _base_params()
        params.set("source.target.reflectance", 0.42)
        rho = _published(_run(params, _WL_VIS))
        assert rho is not None
        assert rho.unit == "dimensionless"

    @pytest.mark.level0
    def test_spectral_rho_csv_lands_on_the_chain_grid(self, tmp_path) -> None:  # type: ignore[no-untyped-def]
        """A ρ(λ) CSV (owner item 6: "input R(lambda) as well") resolves to the grid.

        The CSV is linear in λ from 0.2 at 0.4 µm to 0.7 at 0.9 µm, so the
        published curve is checkable at both ends and in the middle against
        hand values: ρ(0.4) = 0.2, ρ(0.65) = 0.45, ρ(0.9) = 0.7.
        """
        csv = tmp_path / "rho.csv"
        csv.write_text(
            "wavelength_um,rho\n0.4,0.2\n0.65,0.45\n0.9,0.7\n",
            encoding="utf-8",
        )
        params = _base_params()
        params.set("source.target.reflectance_path", str(csv))
        rho = _published(_run(params, _WL_VIS))

        assert rho is not None
        np.testing.assert_array_equal(rho.wavelength_um, _WL_VIS)
        assert rho.values[0] == pytest.approx(0.2, abs=1e-12)
        assert rho.values[-1] == pytest.approx(0.7, abs=1e-12)
        # Linear ramp: ρ(λ) = 0.2 + (λ − 0.4) · (0.5 / 0.5).
        np.testing.assert_allclose(
            rho.values,
            0.2 + (_WL_VIS - 0.4),
            rtol=0.0,
            atol=1e-12,
        )


# ---------------------------------------------------------------------------
# Pathway 2 — T3Mixed (Kirchhoff ρ = 1 − ε, Rule 5)
# ---------------------------------------------------------------------------


class TestKirchhoffPathway:
    @pytest.mark.level0
    @pytest.mark.parametrize(
        ("epsilon", "expected_rho"),
        [(0.95, 0.05), (0.7, 0.3), (1.0, 0.0), (0.0, 1.0)],
    )
    def test_rho_is_one_minus_epsilon_elementwise(
        self, epsilon: float, expected_rho: float
    ) -> None:
        """Hand value: ρ = 1 − ε on every grid point (Rule 5, no ρ input exists)."""
        params = _base_params()
        params.set("source.target.temperature", 300.0)
        params.set("source.target.emissivity", epsilon)
        rho = _published(_run(params, _WL_MWIR))

        assert rho is not None, "a mixed emit+reflect target must publish ρ(λ)"
        np.testing.assert_allclose(
            rho.values,
            np.full_like(_WL_MWIR, expected_rho),
            rtol=0.0,
            atol=1e-15,
        )

    @pytest.mark.level0
    def test_spectral_epsilon_gives_pointwise_complement(self, tmp_path) -> None:  # type: ignore[no-untyped-def]
        """ε(λ) from CSV ⇒ ρ(λ) = 1 − ε(λ) pointwise, not a band average."""
        csv = tmp_path / "eps.csv"
        csv.write_text(
            "wavelength_um,emissivity\n3.0,0.9\n4.0,0.6\n5.0,0.2\n",
            encoding="utf-8",
        )
        params = _base_params()
        params.set("source.target.temperature", 300.0)
        params.set("source.target.emissivity_path", str(csv))
        state = _run(params, _WL_MWIR)

        rho = _published(state)
        target = state.stage_outputs["source"]["target"]
        assert rho is not None
        # The complement of the descriptor's own ε — the Kirchhoff invariant.
        np.testing.assert_allclose(
            rho.values + np.asarray(target.epsilon.values, dtype=np.float64),
            np.ones_like(_WL_MWIR),
            rtol=0.0,
            atol=1e-15,
        )
        # And against the hand values at the CSV's own knots.
        assert rho.values[0] == pytest.approx(1.0 - 0.9, abs=1e-12)
        assert rho.values[-1] == pytest.approx(1.0 - 0.2, abs=1e-12)


# ---------------------------------------------------------------------------
# Absence — descriptors that carry no reflectance publish nothing
# ---------------------------------------------------------------------------


class TestAbsentForNonReflectiveTargets:
    @pytest.mark.level0
    def test_pure_thermal_hot_target_publishes_no_reflectance(self) -> None:
        """T1 (is_hot_target ⇒ ρ ≡ 0 by construction) reports no surface ρ.

        Rule 17: an absent output is honest — the accessor that reads it says
        "this scene's target carries none" rather than plotting a zero curve
        the analyst could mistake for a measured black surface.
        """
        params = _base_params()
        params.set("source.target.temperature", 800.0)
        params.set("source.target.emissivity", 0.9)
        params.set("source.target.is_hot_target", True)
        state = _run(params, _WL_MWIR)

        from radiant.core.descriptors import T1Thermal

        assert isinstance(state.stage_outputs["source"]["target"], T1Thermal)
        assert _published(state) is None

    @pytest.mark.level0
    def test_user_supplied_at_source_radiance_publishes_no_reflectance(
        self,
        tmp_path,  # type: ignore[no-untyped-def]
    ) -> None:
        """T6 carries L(λ) directly — there is no surface property to report."""
        csv = tmp_path / "L_source.csv"
        csv.write_text(
            "wavelength_um,radiance\n3.0,5.0\n5.0,5.0\n",
            encoding="utf-8",
        )
        params = _base_params()
        params.set("source.target.user_radiance_path", str(csv))
        state = _run(params, _WL_MWIR)

        from radiant.core.descriptors import T6TabulatedAtSource

        assert isinstance(state.stage_outputs["source"]["target"], T6TabulatedAtSource)
        assert _published(state) is None


# ---------------------------------------------------------------------------
# One resolver — the published ρ is the ρ the radiance path consumes
# ---------------------------------------------------------------------------


class TestSingleResolver:
    @pytest.mark.level0
    def test_published_rho_matches_the_descriptor_protocol_call(self) -> None:
        """Rule 19: publication and assembly resolve ρ through the same function.

        Probed at the descriptor's own protocol surface — if SourceStage ever
        grew a second resolver, this comparison is what would catch it.
        """
        params = _base_params()
        params.set("source.target.reflectance", 0.37)
        state = _run(params, _WL_VIS)

        from radiant.core.target_reflectance import resolve_reflectance_on_grid

        target = state.stage_outputs["source"]["target"]
        los = state.stage_outputs["source"]["los_geometry"]
        rho = _published(state)
        assert rho is not None
        np.testing.assert_array_equal(
            rho.values,
            resolve_reflectance_on_grid(target.rho, _WL_VIS, los),
        )
