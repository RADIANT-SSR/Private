"""Tests for the S4 / S5 / S6 reflectance → T2Reflective inferrer wiring.

Step 3.2 of the Target Definition Matrix Implementation Plan: the
inferrer routes a user-supplied scalar reflectance (S4) or albedo alias
(S6) through :func:`radiant.source.converters.reflectance_to_descriptor`
and emits a :class:`~radiant.core.descriptors.T2Reflective` descriptor.
The S5/S6 tabulated paths (``reflectance_path`` / ``albedo_path``) ship
too: the inferrer loads the CSV and routes it through the same converter
(``_inferrer.py``, "Tabulated ρ(λ) via CSV").  That routing is exercised
end-to-end through ``SourceStage`` in ``test_reflectance_published.py``.

Truth anchors
-------------
1. **Pure Lambertian identity** — scalar ρ routed through the inferrer
   gives a T2Reflective whose ρ exactly recovers
   ``L_refl(λ) = ρ · E_sun(λ) / π`` when evaluated through the existing
   :class:`~radiant.source.brdf_lambertian.LambertianBRDF`.
2. **Heaviside ρ(λ) propagation** — a tabulated ρ with a sharp step at
   0.5 µm is passed straight through (no smoothing, no grid
   interpolation), asserted on **both** entry points: the boundary
   converter directly (the Rule-19 scope of the converter module) and
   the ``reflectance_path`` CSV route the inferrer actually takes.
3. **Kirchhoff cross-model consistency** — a T2Reflective built from
   ρ=0.3 and a T3Mixed built from ε=0.7 on the same grid satisfy
   ``T2.rho + T3.epsilon ≡ 1`` pointwise (Rule 5 sanity check at the
   descriptor layer).

Also covered: mutual-exclusion guards (ρ + (ε, T), ρ + S11/S12), the
MWIR non-mixed warning (Rule 17 handoff), and isinstance assertions.
"""

from __future__ import annotations

import math
import warnings
from pathlib import Path

import numpy as np
import pytest

from radiant.api._param_registry import build_parameter_set
from radiant.core.descriptors import T1Thermal, T2Reflective, T3Mixed
from radiant.core.parameters import ParameterBoundsError, ParameterSet
from radiant.core.solar import toa_solar_spectral_irradiance
from radiant.core.spectral import SpectralData
from radiant.source._inferrer import infer_descriptors
from radiant.source.brdf_lambertian import LambertianBRDF
from radiant.source.converters.reflectance import (
    load_reflectance_csv,
    reflectance_to_descriptor,
)

_WL_VIS = np.linspace(0.4, 0.8, 21)
_WL_MWIR = np.linspace(3.0, 5.0, 11)
_ZERO3 = np.zeros(3, dtype=np.float64)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _reflective_params() -> ParameterSet:
    """Return a ParameterSet configured for the reflective fast-path.

    Sets the minimum fields required for ``params.resolve()`` to succeed
    and for ``infer_descriptors`` to run (optics consistency group,
    atmosphere backend, explicit scene_type so the IFOV discriminator
    stays inert).  Legacy ε / T are left at their Provenance.DEFAULT
    schema values so the inferrer's ``_is_user_set`` guard returns False
    on them and the reflective branch is reachable.
    """
    params = build_parameter_set()
    # Optics f-number consistency group — supply two of three.
    params.set("optics.aperture_diameter_m", 0.15)
    params.set("optics.focal_length_m", 0.60)
    params.set("atmosphere.model", "simple")
    # Other required (default=None) fields — values are placeholders; the
    # inferrer reads only pixel_pitch / focal_length / atmosphere.model /
    # source.* for the reflective branch.
    params.set("geometry.sensor_altitude_m", 500.0)
    params.set("spectral_integration.filter_min_um", 0.4)
    params.set("spectral_integration.filter_max_um", 0.9)
    params.set("spectral_integration.integration_time_s", 1e-3)
    params.set("detector.pixel_pitch_x_um", 5.5)
    params.set("detector.pixel_pitch_y_um", 5.5)
    params.set("detector.qe_value", 0.8)
    # Skip the IFOV discriminator — explicit scene wins.
    params.set("source.scene_type", "extended")
    params.set("source.target_location", "terrestrial")
    return params


# ---------------------------------------------------------------------------
# Truth Anchor 1 — pure Lambertian identity at the descriptor layer
# ---------------------------------------------------------------------------


class TestTruthAnchorLambertianIdentity:
    """Scalar ρ routed through the inferrer recovers L = ρ·E_sun/π.

    The inferrer's contract is: "given a scalar ρ on the schema, emit a
    T2Reflective whose ρ(λ) is the same value on the chain grid."  The
    downstream Lambertian identity L_refl = ρ·E_sun/π is intrinsic to
    :class:`LambertianBRDF` and :class:`ReflectedSolarSource`; this
    anchor confirms that the descriptor's ρ feeds the existing solar
    path unchanged.
    """

    @pytest.mark.level1
    def test_scalar_rho_flat_on_chain_grid(self) -> None:
        params = _reflective_params()
        params.set("source.target.reflectance", 0.5)
        # Reflective pathway must not inherit legacy (ε, T) from template.
        params.resolve()

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            target, _bg, _los = infer_descriptors(params, _WL_VIS)

        assert isinstance(target, T2Reflective)
        assert target.rho is not None
        # Constant-ρ lift: every grid point equals 0.5 exactly (probed via
        # the ReflectanceDescriptor protocol surface — Gap H).
        rho_on_grid = target.rho.reflectance_at(_WL_VIS, _ZERO3, _ZERO3)
        np.testing.assert_array_equal(rho_on_grid, np.full_like(_WL_VIS, 0.5))

    @pytest.mark.level1
    def test_lambertian_identity_recovers_rho_times_E_over_pi(self) -> None:
        """L_refl(λ) = ρ·E_sun(λ)/π reconstructed from the descriptor's ρ."""
        params = _reflective_params()
        params.set("source.target.reflectance", 0.5)
        params.resolve()

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            target, _bg, _los = infer_descriptors(params, _WL_VIS)
        assert isinstance(target, T2Reflective)
        assert target.rho is not None

        E_sun = toa_solar_spectral_irradiance(_WL_VIS)

        # Path A: direct analytic identity from descriptor's ρ (Gap H: via
        # the ReflectanceDescriptor protocol).
        rho_on_grid = target.rho.reflectance_at(_WL_VIS, _ZERO3, _ZERO3)
        L_direct = rho_on_grid * E_sun / math.pi

        # Path B: Lambertian BRDF evaluated at θ_sun = 0 ⇒ L = BRDF·E·cos0.
        brdf = LambertianBRDF(reflectance=rho_on_grid)
        L_brdf = brdf.evaluate(_WL_VIS) * E_sun * math.cos(0.0)

        np.testing.assert_allclose(L_brdf, L_direct, rtol=1e-12, atol=0.0)

        # Sanity: descriptor ρ = 0.5 ⇒ L = 0.5·E_sun/π (no hidden factor).
        expected = 0.5 * E_sun / math.pi
        np.testing.assert_allclose(L_direct, expected, rtol=1e-12, atol=0.0)


# ---------------------------------------------------------------------------
# Truth Anchor 2 — Heaviside ρ(λ) through the boundary converter
# ---------------------------------------------------------------------------


class TestTruthAnchorHeavisideSpectrum:
    """Tabulated ρ with a step at 0.5 µm propagates unaltered.

    The invariant is identical on both entry points — the converter never
    resamples or smooths ρ — so both are asserted: the converter called
    directly, and the ``reflectance_path`` CSV the inferrer loads (S5).
    The CU-245 correction: this class used to state that the inferrer
    "only scalar-lifts today", which stopped being true once the S5
    loader landed, and that stale claim is why the ρ(λ) GUI input stayed
    unmounted until the walkthrough item-6 pass.
    """

    @pytest.mark.level1
    def test_heaviside_step_preserved_in_descriptor(self) -> None:
        step_edge_um = 0.5
        wl = np.linspace(0.3, 0.9, 25)
        rho_vals = np.where(wl < step_edge_um, 0.0, 1.0).astype(np.float64)
        rho_sd = SpectralData(
            name="test.heaviside_rho",
            wavelength_um=wl,
            values=rho_vals,
            unit="",
            source="test_inferrer_reflective::heaviside",
        )

        target = reflectance_to_descriptor(
            rho=rho_sd,
            wavelength_um=wl,
            scene_type="extended",
            target_location="terrestrial",
            h_tgt=0.0,
        )

        assert isinstance(target, T2Reflective)
        assert target.rho is not None
        # Converter must be pass-through: no interpolation, no clipping
        # (Gap H: probed through the ReflectanceDescriptor protocol).
        rho_on_grid = target.rho.reflectance_at(wl, _ZERO3, _ZERO3)
        np.testing.assert_array_equal(rho_on_grid, rho_vals)
        # Step semantics preserved: below 0.5 µm all zero, above all one.
        below = wl < step_edge_um
        above = wl >= step_edge_um
        assert np.all(rho_on_grid[below] == 0.0)
        assert np.all(rho_on_grid[above] == 1.0)

    @pytest.mark.level1
    def test_heaviside_step_survives_the_reflectance_path_csv_route(
        self,
        tmp_path: Path,
    ) -> None:
        """The same step, entered the way a user actually enters one (S5 CSV).

        The inferrer route adds a CSV load and a resample onto the chain
        grid; neither may round the edge off.  Sampling the CSV knots on
        the chain grid itself keeps the step exact, so any interpolation
        across the edge would show immediately.
        """
        step_edge_um = 0.5
        wl = np.linspace(0.3, 0.9, 25)
        rho_vals = np.where(wl < step_edge_um, 0.0, 1.0).astype(np.float64)

        csv = tmp_path / "rho_step.csv"
        rows = "".join(f"{w},{r}\n" for w, r in zip(wl, rho_vals, strict=True))
        csv.write_text("wavelength_um,rho\n" + rows, encoding="utf-8")

        params = _reflective_params()
        params.set("source.target.reflectance_path", str(csv))
        params.resolve()

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            target, _bg, _los = infer_descriptors(params, wl)

        assert isinstance(target, T2Reflective)
        assert target.rho is not None
        rho_on_grid = target.rho.reflectance_at(wl, _ZERO3, _ZERO3)
        np.testing.assert_allclose(rho_on_grid, rho_vals, rtol=0.0, atol=1e-12)
        assert np.all(rho_on_grid[wl < step_edge_um] == 0.0)
        assert np.all(rho_on_grid[wl >= step_edge_um] == 1.0)


# ---------------------------------------------------------------------------
# Truth Anchor 3 — Kirchhoff ρ = 1 − ε cross-model consistency
# ---------------------------------------------------------------------------


class TestTruthAnchorKirchhoffConsistency:
    """T2Reflective(ρ) and T3Mixed(ε=1−ρ) satisfy ρ + ε ≡ 1 pointwise.

    Rule 5: for opaque Lambertian surfaces ρ + ε = 1 exactly.  Building
    T2 and T3 from complementary spectra on the same grid must give
    descriptors whose ρ and ε are algebraic complements — verifying the
    boundary converter and the descriptor dataclasses agree on the
    Kirchhoff identity at construction time.  (The downstream
    ``L = ε·B(T) + ρ·E_down·τ/π`` assembly lives in AtmosphereStage and
    is tested there.)
    """

    @pytest.mark.level1
    def test_rho_plus_epsilon_is_one_pointwise(self) -> None:
        rho_scalar = 0.3
        eps_scalar = 1.0 - rho_scalar  # 0.7
        wl = np.linspace(0.5, 2.5, 41)

        # Build T2Reflective from scalar ρ via the converter.
        t2 = reflectance_to_descriptor(
            rho=rho_scalar,
            wavelength_um=wl,
            scene_type="extended",
            target_location="terrestrial",
            h_tgt=0.0,
        )
        assert isinstance(t2, T2Reflective)

        # Build T3Mixed from complementary scalar ε on the same grid.
        epsilon_sd = SpectralData(
            name="test.complement_epsilon",
            wavelength_um=wl,
            values=np.full_like(wl, eps_scalar),
            unit="",
            source="test_inferrer_reflective::kirchhoff",
        )
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            t3 = T3Mixed(
                scene_type="extended",
                target_location="terrestrial",
                h_tgt=0.0,
                epsilon=epsilon_sd,
                T_t=300.0,
            )

        assert t2.rho is not None
        assert t3.epsilon is not None
        # Kirchhoff identity at the descriptor layer (Gap H: T2 ρ read via
        # the protocol).
        rho_on_grid = t2.rho.reflectance_at(wl, _ZERO3, _ZERO3)
        np.testing.assert_allclose(
            rho_on_grid + t3.epsilon.values,
            np.ones_like(wl),
            rtol=1e-12,
            atol=0.0,
        )


# ---------------------------------------------------------------------------
# Inferrer happy-path — isinstance + mutual-exclusion rejection
# ---------------------------------------------------------------------------


class TestInferrerReflectiveDispatch:
    """The inferrer dispatches scalar ρ / albedo to T2Reflective."""

    @pytest.mark.level1
    def test_scalar_reflectance_produces_T2Reflective(self) -> None:
        params = _reflective_params()
        params.set("source.target.reflectance", 0.3)
        params.resolve()

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            target, _bg, _los = infer_descriptors(params, _WL_VIS)

        assert isinstance(target, T2Reflective)
        assert not isinstance(target, (T1Thermal, T3Mixed))

    @pytest.mark.level1
    def test_albedo_alias_produces_T2Reflective(self) -> None:
        """S6 albedo alias collapses onto the same T2Reflective surface."""
        params = _reflective_params()
        params.set("source.target.albedo", 0.4)
        params.resolve()

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            target, _bg, _los = infer_descriptors(params, _WL_VIS)

        assert isinstance(target, T2Reflective)
        assert target.rho is not None
        rho_on_grid = target.rho.reflectance_at(_WL_VIS, _ZERO3, _ZERO3)
        np.testing.assert_array_equal(rho_on_grid, np.full_like(_WL_VIS, 0.4))


# ---------------------------------------------------------------------------
# Negative cases (Rule 16 / 17 — over-specified, ambiguous, deferred)
# ---------------------------------------------------------------------------


class TestInferrerReflectiveRejections:
    @pytest.mark.level1
    def test_reflectance_plus_temperature_raises(self) -> None:
        """ρ + (ε, T) over-specifies the target; must raise."""
        params = _reflective_params()
        params.set("source.target.reflectance", 0.3)
        params.set("source.target.temperature", 300.0)
        params.set("source.target.emissivity", 0.7)
        params.resolve()

        with pytest.raises(ParameterBoundsError, match="mutually exclusive"):
            infer_descriptors(params, _WL_VIS)

    @pytest.mark.level1
    def test_reflectance_plus_brightness_temperature_raises(self) -> None:
        """Reflective S4/S5/S6 and thermal S11 are mutually exclusive."""
        params = _reflective_params()
        params.set("source.target.reflectance", 0.3)
        params.set("source.target.brightness_temperature_K", 290.0)
        params.resolve()

        with pytest.raises(ParameterBoundsError, match="mutually exclusive"):
            infer_descriptors(params, _WL_VIS)

    @pytest.mark.level1
    def test_reflectance_plus_radiance_temperature_raises(self) -> None:
        """Reflective S4/S5/S6 and thermal S12 are mutually exclusive."""
        params = _reflective_params()
        params.set("source.target.reflectance", 0.3)
        params.set("source.target.radiance_temperature_K", 290.0)
        params.set("source.target.radiance_temperature_band_lo_um", 8.0)
        params.set("source.target.radiance_temperature_band_hi_um", 12.0)
        params.resolve()

        with pytest.raises(ParameterBoundsError, match="mutually exclusive"):
            infer_descriptors(params, _WL_VIS)

    @pytest.mark.level1
    def test_reflectance_plus_albedo_raises(self) -> None:
        """Reflectance + albedo (both scalar surfaces) over-specifies ρ."""
        params = _reflective_params()
        params.set("source.target.reflectance", 0.3)
        params.set("source.target.albedo", 0.3)
        params.resolve()

        with pytest.raises(ParameterBoundsError, match="over-specified"):
            infer_descriptors(params, _WL_VIS)

    @pytest.mark.level1
    def test_reflectance_at_aperture_raises(self) -> None:
        """ρ is meaningless at S9 (at-aperture) — converter must reject."""
        with pytest.raises(ParameterBoundsError, match="at_aperture"):
            reflectance_to_descriptor(
                rho=0.3,
                wavelength_um=_WL_VIS,
                scene_type="extended",
                target_location="at_aperture",
            )

    @pytest.mark.level1
    def test_reflectance_mwir_emits_advisory(self, caplog) -> None:  # type: ignore[no-untyped-def]
        """S4 with MWIR grid triggers the T2 non-mixed advisory.

        Matrix §3.2: ambient-temperature MWIR scenes should use T3Mixed.
        The T2Reflective ``__post_init__`` logs the advisory; this test
        asserts the inferrer does not suppress it (pass-through).  Warning-Free
        UX: the advisory is a quiet ``logger.debug`` note, not a ``UserWarning``.
        """
        import logging

        params = _reflective_params()
        params.set("source.target.reflectance", 0.5)
        params.resolve()

        with caplog.at_level(logging.DEBUG, logger="radiant.core.descriptors"):
            target, _bg, _los = infer_descriptors(params, _WL_MWIR)

        assert isinstance(target, T2Reflective)
        mwir_msgs = [
            r for r in caplog.records if "MWIR" in r.message and "T2Reflective" in r.message
        ]
        assert mwir_msgs, (
            "Expected T2Reflective MWIR non-mixed advisory to propagate; "
            f"got debug records: {[r.message for r in caplog.records]}"
        )


# ---------------------------------------------------------------------------
# Gap G Step G.2 — reflectance_path / albedo_path CSV wiring
# ---------------------------------------------------------------------------


def _write_flat_rho_csv(
    path: Path,
    *,
    wl_um: np.ndarray,
    rho_value: float,
    header: bool = True,
) -> Path:
    lines: list[str] = []
    if header:
        lines.append("wavelength_um,reflectance")
    lines.extend(f"{w:.6f},{rho_value:.6f}" for w in wl_um)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def _write_two_row_rho_csv(
    path: Path,
    *,
    wl_low: float,
    wl_high: float,
    rho_low: float,
    rho_high: float,
) -> Path:
    path.write_text(
        f"wavelength_um,reflectance\n{wl_low:.6f},{rho_low:.6f}\n{wl_high:.6f},{rho_high:.6f}\n",
        encoding="utf-8",
    )
    return path


class TestReflectancePathCSV:
    """S5 (reflectance_path) and S6 (albedo_path) CSV wiring.

    Each test uses the file-native grid that BRACKETS ``_WL_VIS`` so
    the resampler stays inside the CSV span (Rule 17: out-of-grid
    raises).
    """

    # ----- Truth Anchor 1 — constant ρ=0.3 round-trip (Lambertian) -----

    @pytest.mark.level1
    def test_constant_reflectance_path_recovers_rho(self, tmp_path: Path) -> None:
        csv = _write_flat_rho_csv(
            tmp_path / "rho.csv",
            wl_um=np.array([0.3, 0.4, 0.8, 0.9]),
            rho_value=0.3,
        )
        params = _reflective_params()
        params.set("source.target.reflectance_path", str(csv))
        params.resolve()

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            target, _bg, _los = infer_descriptors(params, _WL_VIS)

        assert isinstance(target, T2Reflective)
        assert target.rho is not None
        rho_on_grid = target.rho.reflectance_at(_WL_VIS, _ZERO3, _ZERO3)
        np.testing.assert_allclose(
            rho_on_grid,
            np.full_like(_WL_VIS, 0.3),
            rtol=1e-12,
            atol=1e-12,
        )

    # ----- Truth Anchor 2 — step ρ(λ) carries the step -----

    @pytest.mark.level1
    def test_step_reflectance_path_carries_the_step(self, tmp_path: Path) -> None:
        # Step at 0.6 µm: ρ=0.1 below, ρ=0.6 above.  File grid encodes
        # the step as two rows on either side of the edge to avoid
        # linear-interpolation smoothing around the cut.
        csv = tmp_path / "step_rho.csv"
        csv.write_text(
            "wavelength_um,reflectance\n0.30,0.1\n0.59999,0.1\n0.60001,0.6\n0.90,0.6\n",
            encoding="utf-8",
        )
        params = _reflective_params()
        params.set("source.target.reflectance_path", str(csv))
        params.resolve()

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            target, _bg, _los = infer_descriptors(params, _WL_VIS)

        assert isinstance(target, T2Reflective)
        assert target.rho is not None
        rho_on_grid = target.rho.reflectance_at(_WL_VIS, _ZERO3, _ZERO3)
        # Chain grid samples below 0.6 µm should be ≈ 0.1; samples
        # above should be ≈ 0.6.  Points inside [0.59999, 0.60001]
        # are excluded from both tails.
        below = _WL_VIS < 0.59999
        above = _WL_VIS > 0.60001
        np.testing.assert_allclose(rho_on_grid[below], 0.1, rtol=1e-9, atol=1e-9)
        np.testing.assert_allclose(rho_on_grid[above], 0.6, rtol=1e-9, atol=1e-9)

    # ----- Truth Anchor 3 — albedo_path alias identity -----

    @pytest.mark.level1
    def test_albedo_path_and_reflectance_path_are_aliases(self, tmp_path: Path) -> None:
        csv_a = _write_flat_rho_csv(
            tmp_path / "alb.csv",
            wl_um=np.array([0.3, 0.4, 0.8, 0.9]),
            rho_value=0.42,
        )
        csv_r = _write_flat_rho_csv(
            tmp_path / "rho.csv",
            wl_um=np.array([0.3, 0.4, 0.8, 0.9]),
            rho_value=0.42,
        )

        params_a = _reflective_params()
        params_a.set("source.target.albedo_path", str(csv_a))
        params_a.resolve()

        params_r = _reflective_params()
        params_r.set("source.target.reflectance_path", str(csv_r))
        params_r.resolve()

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            t_a, _, _ = infer_descriptors(params_a, _WL_VIS)
            t_r, _, _ = infer_descriptors(params_r, _WL_VIS)

        assert isinstance(t_a, T2Reflective)
        assert isinstance(t_r, T2Reflective)
        assert t_a.rho is not None and t_r.rho is not None
        rho_a = t_a.rho.reflectance_at(_WL_VIS, _ZERO3, _ZERO3)
        rho_r = t_r.rho.reflectance_at(_WL_VIS, _ZERO3, _ZERO3)
        np.testing.assert_array_equal(rho_a, rho_r)

    # ----- Cross-model consistency — CSV ρ vs scalar ρ -----

    @pytest.mark.level1
    def test_csv_flat_rho_matches_scalar_rho(self, tmp_path: Path) -> None:
        """Flat-ρ CSV path and scalar-ρ schema path produce identical ρ(λ)."""
        csv = _write_flat_rho_csv(
            tmp_path / "rho.csv",
            wl_um=np.array([0.3, 0.4, 0.8, 0.9]),
            rho_value=0.55,
        )
        params_csv = _reflective_params()
        params_csv.set("source.target.reflectance_path", str(csv))
        params_csv.resolve()

        params_scalar = _reflective_params()
        params_scalar.set("source.target.reflectance", 0.55)
        params_scalar.resolve()

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            t_csv, _, _ = infer_descriptors(params_csv, _WL_VIS)
            t_sca, _, _ = infer_descriptors(params_scalar, _WL_VIS)

        assert t_csv.rho is not None and t_sca.rho is not None
        rho_csv = t_csv.rho.reflectance_at(_WL_VIS, _ZERO3, _ZERO3)
        rho_sca = t_sca.rho.reflectance_at(_WL_VIS, _ZERO3, _ZERO3)
        np.testing.assert_allclose(rho_csv, rho_sca, rtol=1e-12, atol=1e-12)

    # ----- Failure mode — reflectance_path + albedo_path both set -----

    @pytest.mark.level1
    def test_reflectance_path_plus_albedo_path_raises(self, tmp_path: Path) -> None:
        csv = _write_flat_rho_csv(
            tmp_path / "r.csv",
            wl_um=np.array([0.3, 0.9]),
            rho_value=0.3,
        )
        params = _reflective_params()
        params.set("source.target.reflectance_path", str(csv))
        params.set("source.target.albedo_path", str(csv))
        params.resolve()

        with pytest.raises(ParameterBoundsError, match="over-specified"):
            infer_descriptors(params, _WL_VIS)

    # ----- Failure mode — ρ > 1 boundary rejection -----

    @pytest.mark.level1
    def test_reflectance_path_with_rho_gt_1_raises(self, tmp_path: Path) -> None:
        csv = tmp_path / "bad.csv"
        csv.write_text("wavelength_um,reflectance\n0.3,0.3\n0.5,1.5\n0.9,0.3\n", encoding="utf-8")
        params = _reflective_params()
        params.set("source.target.reflectance_path", str(csv))
        params.resolve()

        with pytest.raises(ParameterBoundsError, match="exceeds 1.0") as exc:
            infer_descriptors(params, _WL_VIS)
        # Boundary-guard context carries the source file path so the user
        # can trace the bad row.
        assert exc.value.context["path"] == str(csv)
        assert exc.value.context["max_rho"] == pytest.approx(1.5, rel=1e-9)

    # ----- Failure mode — ρ < 0 boundary rejection -----

    @pytest.mark.level1
    def test_reflectance_path_with_negative_rho_raises(self, tmp_path: Path) -> None:
        csv = tmp_path / "neg.csv"
        csv.write_text("wavelength_um,reflectance\n0.3,0.3\n0.5,-0.1\n0.9,0.3\n", encoding="utf-8")
        params = _reflective_params()
        params.set("source.target.reflectance_path", str(csv))
        params.resolve()

        with pytest.raises(ParameterBoundsError, match="negative") as exc:
            infer_descriptors(params, _WL_VIS)
        assert exc.value.context["path"] == str(csv)

    # ----- Failure mode — chain grid wider than file grid -----

    @pytest.mark.level1
    def test_reflectance_path_out_of_grid_raises(self, tmp_path: Path) -> None:
        # File grid [0.5, 0.7] does NOT cover chain grid [0.4, 0.8] —
        # resampler must raise rather than silently extrapolate.
        csv = _write_two_row_rho_csv(
            tmp_path / "narrow.csv",
            wl_low=0.5,
            wl_high=0.7,
            rho_low=0.3,
            rho_high=0.3,
        )
        params = _reflective_params()
        params.set("source.target.reflectance_path", str(csv))
        params.resolve()

        with pytest.raises(ParameterBoundsError, match="extends outside") as exc:
            infer_descriptors(params, _WL_VIS)
        ctx = exc.value.context
        assert ctx["chain_grid_um"] == pytest.approx([0.4, 0.8], rel=1e-9)
        assert ctx["file_grid_um"] == pytest.approx([0.5, 0.7], rel=1e-9)

    # ----- Failure mode — non-monotonic CSV grid -----

    @pytest.mark.level1
    def test_reflectance_path_non_monotonic_grid_raises(self, tmp_path: Path) -> None:
        csv = tmp_path / "unsorted.csv"
        csv.write_text(
            "wavelength_um,reflectance\n"
            "0.3,0.1\n"
            "0.9,0.2\n"
            "0.5,0.3\n",  # out-of-order ⇒ diffs not all > 0
            encoding="utf-8",
        )
        params = _reflective_params()
        params.set("source.target.reflectance_path", str(csv))
        params.resolve()

        with pytest.raises(ParameterBoundsError, match="strictly ascending"):
            infer_descriptors(params, _WL_VIS)

    # ----- Failure mode — duplicate wavelengths -----

    @pytest.mark.level1
    def test_reflectance_path_duplicate_wavelengths_raises(self, tmp_path: Path) -> None:
        csv = tmp_path / "dup.csv"
        csv.write_text(
            "wavelength_um,reflectance\n0.3,0.1\n0.5,0.2\n0.5,0.3\n0.9,0.4\n", encoding="utf-8"
        )
        params = _reflective_params()
        params.set("source.target.reflectance_path", str(csv))
        params.resolve()

        with pytest.raises(ParameterBoundsError, match="duplicate wavelength"):
            infer_descriptors(params, _WL_VIS)

    # ----- Failure mode — reflectance_path + temperature -----

    @pytest.mark.level1
    def test_reflectance_path_plus_temperature_raises(self, tmp_path: Path) -> None:
        csv = _write_flat_rho_csv(
            tmp_path / "r.csv",
            wl_um=np.array([0.3, 0.9]),
            rho_value=0.3,
        )
        params = _reflective_params()
        params.set("source.target.reflectance_path", str(csv))
        params.set("source.target.temperature", 300.0)
        params.set("source.target.emissivity", 0.7)
        params.resolve()

        with pytest.raises(ParameterBoundsError, match="mutually exclusive"):
            infer_descriptors(params, _WL_VIS)

    # ----- load_reflectance_csv helper direct test -----

    @pytest.mark.level1
    def test_load_reflectance_csv_dimensionless_unit(self, tmp_path: Path) -> None:
        csv = _write_flat_rho_csv(
            tmp_path / "r.csv",
            wl_um=np.array([0.3, 0.9]),
            rho_value=0.4,
        )
        sd = load_reflectance_csv(csv, is_albedo=False)
        assert sd.unit == "dimensionless"
        assert sd.name == "source.target.reflectance"
        np.testing.assert_array_equal(sd.wavelength_um, [0.3, 0.9])
        np.testing.assert_array_equal(sd.values, [0.4, 0.4])

    @pytest.mark.level1
    def test_load_reflectance_csv_albedo_label_in_errors(self, tmp_path: Path) -> None:
        missing = tmp_path / "missing.csv"
        with pytest.raises(ParameterBoundsError, match="albedo"):
            load_reflectance_csv(missing, is_albedo=True)
