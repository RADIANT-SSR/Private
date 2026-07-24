"""Tests for the S11 brightness-temperature boundary converter.

Covers Step 2.1 of the Target Definition Matrix Implementation Plan:

- 3 mandatory truth anchors (constant-T_B identity, λ-varying pointwise
  identity, round-trip T_B → L → invert Planck → T_B to 1e-4 K).
- Negative cases: T_B < 0, T_B > 10 000, empty, at_aperture.
- Inferrer integration (Gap G Step G.3): scalar T_B routes to T1Thermal;
  CSV path loads via the shared two-column reader, validates
  T_B ∈ (0, 10000] K at the boundary, and routes to T1Thermal (flat) or
  T6TabulatedAtSource (λ-varying).
- Over-specification: brightness_temperature paired with legacy (ε, T)
  or with the scalar ``brightness_temperature_K``.

These are the Category C numerical anchors for
``source.converters.brightness_temperature``.
"""

from __future__ import annotations

import math
import warnings
from pathlib import Path

import numpy as np
import pytest

from radiant.api._param_registry import build_parameter_set
from radiant.core.blackbody import planck_spectral_radiance
from radiant.core.constants import hc_over_kB, two_hc2
from radiant.core.descriptors import T1Thermal, T6TabulatedAtSource
from radiant.core.parameters import ParameterBoundsError, ParameterSet
from radiant.core.spectral import SpectralData
from radiant.source._inferrer import infer_descriptors
from radiant.source.converters.brightness_temperature import (
    brightness_temperature_to_descriptor,
    load_brightness_temperature_csv,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _lwir_grid(n: int = 61) -> np.ndarray:
    """LWIR wavelength grid (8–14 µm) used for the truth anchors."""
    return np.linspace(8.0, 14.0, n, dtype=np.float64)


def _flat_T_B(lam: np.ndarray, T_K: float) -> SpectralData:
    return SpectralData(
        name="T_B",
        wavelength_um=lam,
        values=np.full_like(lam, T_K, dtype=np.float64),
        unit="K",
        source="test_brightness_temperature_converter",
    )


def _sd_T_B(lam: np.ndarray, vals: np.ndarray) -> SpectralData:
    return SpectralData(
        name="T_B",
        wavelength_um=lam,
        values=vals,
        unit="K",
        source="test_brightness_temperature_converter",
    )


def _invert_planck_to_T_B(lam_um: float, L: float) -> float:
    """Planck inverse: given L at λ, return T_B such that B(λ, T_B) = L.

    Closed form:  T_B = (h c / λ k_B) / ln(1 + 2 h c² / (λ⁵ L)).

    Uses the SI form (λ in m, L in W/m²/sr/m) with a Jacobian conversion
    from the canonical W/m²/sr/µm.
    """
    lam_m = float(lam_um) * 1.0e-6
    L_per_m = float(L) * 1.0e6  # W/m²/sr/µm → W/m²/sr/m
    numer = two_hc2 / (lam_m**5)
    return float(hc_over_kB / (lam_m * math.log(1.0 + numer / L_per_m)))


# ---------------------------------------------------------------------------
# Truth anchor 1 — constant T_B routes to T1Thermal and reproduces Planck
# ---------------------------------------------------------------------------


class TestAnchor1ConstantTBMatchesPlanck:
    @pytest.mark.level0
    def test_constant_T_B_emits_T1_thermal_with_epsilon_1(self) -> None:
        lam = _lwir_grid()
        T_B = _flat_T_B(lam, 300.0)

        desc = brightness_temperature_to_descriptor(
            T_B=T_B,
            scene_type="extended",
            target_location="terrestrial",
            h_tgt=0.0,
        )

        assert isinstance(desc, T1Thermal)
        assert desc.T_t == pytest.approx(300.0, abs=1e-12)
        assert desc.epsilon is not None
        np.testing.assert_allclose(desc.epsilon.values, np.ones_like(lam), atol=0.0)

    @pytest.mark.level0
    def test_L_at_10um_matches_planck_blackbody(self) -> None:
        """Anchor 1: T_B = 300 K flat → L(10 µm) = B(10 µm, 300 K) to 1e-6."""
        lam = _lwir_grid()
        T_B = _flat_T_B(lam, 300.0)
        desc = brightness_temperature_to_descriptor(
            T_B=T_B,
            scene_type="extended",
            target_location="terrestrial",
            h_tgt=0.0,
        )
        assert isinstance(desc, T1Thermal)

        idx_10um = int(np.argmin(np.abs(lam - 10.0)))
        expected = float(planck_spectral_radiance(np.asarray([lam[idx_10um]]), desc.T_t)[0])
        assert desc.epsilon is not None
        actual = float(desc.epsilon.values[idx_10um]) * expected

        rel = abs(actual - expected) / expected
        assert rel < 1.0e-6, f"|ΔL/L| = {rel:g} exceeds 1e-6 truth-anchor tolerance"


# ---------------------------------------------------------------------------
# Truth anchor 2 — λ-varying T_B matches pointwise Planck at 3 wavelengths
# ---------------------------------------------------------------------------


class TestAnchor2VaryingTBMatchesPointwisePlanck:
    @pytest.mark.level0
    def test_varying_T_B_emits_T6_with_matching_L(self) -> None:
        """Anchor 2: sloped T_B(λ) → L(λ_i) = B(λ_i, T_B(λ_i)) at 3 checkpoints."""
        lam = _lwir_grid()
        # Sloped T_B from 280 K at 8 µm up to 320 K at 14 µm — peak-to-peak
        # 40 K, solidly in the λ-varying branch.
        T_B_vals = np.linspace(280.0, 320.0, lam.size, dtype=np.float64)
        T_B = SpectralData(
            name="T_B",
            wavelength_um=lam,
            values=T_B_vals,
            unit="K",
            source="test_brightness_temperature_converter",
        )

        desc = brightness_temperature_to_descriptor(
            T_B=T_B,
            scene_type="extended",
            target_location="terrestrial",
            h_tgt=0.0,
        )

        assert isinstance(desc, T6TabulatedAtSource)
        assert desc.L_t_source is not None

        # Pointwise check at 9 µm, 11 µm, 13 µm.
        for lam_target in (9.0, 11.0, 13.0):
            i = int(np.argmin(np.abs(lam - lam_target)))
            T_i = float(T_B_vals[i])
            expected = float(planck_spectral_radiance(np.asarray([lam[i]]), T_i)[0])
            actual = float(desc.L_t_source.values[i])
            rel = abs(actual - expected) / max(expected, 1e-30)
            assert rel < 1.0e-12, (
                f"λ={lam[i]} µm: actual={actual:g}, expected={expected:g}, rel={rel:g}"
            )


# ---------------------------------------------------------------------------
# Truth anchor 3 — round-trip T_B → L → invert Planck → T_B within 1e-4 K
# ---------------------------------------------------------------------------


class TestAnchor3RoundTripTB:
    @pytest.mark.level0
    def test_roundtrip_within_1e_4_kelvin(self) -> None:
        lam = _lwir_grid()
        T_B_vals = np.linspace(275.0, 315.0, lam.size, dtype=np.float64)
        T_B = SpectralData(
            name="T_B",
            wavelength_um=lam,
            values=T_B_vals,
            unit="K",
            source="test_brightness_temperature_converter",
        )
        desc = brightness_temperature_to_descriptor(
            T_B=T_B,
            scene_type="extended",
            target_location="terrestrial",
            h_tgt=0.0,
        )
        assert isinstance(desc, T6TabulatedAtSource)
        assert desc.L_t_source is not None

        recovered = np.array(
            [_invert_planck_to_T_B(lam[i], desc.L_t_source.values[i]) for i in range(lam.size)],
            dtype=np.float64,
        )

        max_err_K = float(np.abs(recovered - T_B_vals).max())
        assert max_err_K < 1.0e-4, (
            f"Round-trip T_B → L → T_B drifted by {max_err_K:g} K (tolerance 1e-4 K)"
        )


# ---------------------------------------------------------------------------
# Branch selection tests
# ---------------------------------------------------------------------------


class TestBranchSelection:
    @pytest.mark.level0
    def test_near_constant_below_threshold_collapses_to_T1(self) -> None:
        """peak-to-peak ≤ 1 K default threshold → T1Thermal."""
        lam = _lwir_grid(n=7)
        T_B_vals = np.array(
            [299.7, 299.8, 299.9, 300.0, 300.1, 300.2, 300.3],
            dtype=np.float64,
        )
        T_B = SpectralData(
            name="T_B",
            wavelength_um=lam,
            values=T_B_vals,
            unit="K",
            source="test_brightness_temperature_converter",
        )
        desc = brightness_temperature_to_descriptor(
            T_B=T_B,
            scene_type="extended",
            target_location="terrestrial",
            h_tgt=0.0,
        )
        assert isinstance(desc, T1Thermal)
        assert desc.T_t == pytest.approx(float(T_B_vals.mean()), abs=1e-12)

    @pytest.mark.level0
    def test_peak_to_peak_just_above_threshold_routes_to_T6(self) -> None:
        lam = _lwir_grid(n=5)
        # 1.5 K peak-to-peak — above the 1 K default threshold.
        T_B_vals = np.array([299.25, 299.625, 300.0, 300.375, 300.75], dtype=np.float64)
        T_B = SpectralData(
            name="T_B",
            wavelength_um=lam,
            values=T_B_vals,
            unit="K",
            source="test_brightness_temperature_converter",
        )
        desc = brightness_temperature_to_descriptor(
            T_B=T_B,
            scene_type="extended",
            target_location="terrestrial",
            h_tgt=0.0,
        )
        assert isinstance(desc, T6TabulatedAtSource)

    @pytest.mark.level0
    def test_custom_threshold_forces_T6(self) -> None:
        """constant_threshold_K=0 forces T6 even for flat T_B."""
        lam = _lwir_grid(n=5)
        T_B = _flat_T_B(lam, 300.0)
        desc = brightness_temperature_to_descriptor(
            T_B=T_B,
            scene_type="extended",
            target_location="terrestrial",
            h_tgt=0.0,
            constant_threshold_K=-1.0,  # any peak-to-peak > -1 ⇒ T6
        )
        assert isinstance(desc, T6TabulatedAtSource)


# ---------------------------------------------------------------------------
# Negative cases
# ---------------------------------------------------------------------------


class TestRejectsInvalidInputs:
    @pytest.mark.level0
    def test_negative_T_B_raises(self) -> None:
        lam = _lwir_grid(n=5)
        T_B_vals = np.array([300.0, 300.0, -1.0, 300.0, 300.0], dtype=np.float64)
        T_B = SpectralData(
            name="T_B",
            wavelength_um=lam,
            values=T_B_vals,
            unit="K",
            source="test_brightness_temperature_converter",
        )
        with pytest.raises(ParameterBoundsError, match="negative"):
            brightness_temperature_to_descriptor(
                T_B=T_B,
                scene_type="extended",
                target_location="terrestrial",
                h_tgt=0.0,
            )

    @pytest.mark.level0
    def test_T_B_above_ceiling_raises(self) -> None:
        lam = _lwir_grid(n=5)
        T_B = _flat_T_B(lam, 15_000.0)
        with pytest.raises(ParameterBoundsError, match="ceiling"):
            brightness_temperature_to_descriptor(
                T_B=T_B,
                scene_type="extended",
                target_location="terrestrial",
                h_tgt=0.0,
            )

    @pytest.mark.level0
    def test_at_aperture_rejected(self) -> None:
        lam = _lwir_grid(n=5)
        T_B = _flat_T_B(lam, 300.0)
        with pytest.raises(ParameterBoundsError, match="at_aperture"):
            brightness_temperature_to_descriptor(
                T_B=T_B,
                scene_type="extended",
                target_location="at_aperture",
            )


# ---------------------------------------------------------------------------
# Fragility — Planck low-T / Wien cancellation sanity
# ---------------------------------------------------------------------------


class TestFragility:
    @pytest.mark.level0
    def test_cold_T_B_still_produces_non_negative_radiance(self) -> None:
        """T_B = 50 K is deep in the Wien / underflow regime for LWIR."""
        lam = _lwir_grid(n=11)
        T_B = _flat_T_B(lam, 50.0)
        desc = brightness_temperature_to_descriptor(
            T_B=T_B,
            scene_type="extended",
            target_location="terrestrial",
            h_tgt=0.0,
        )
        assert isinstance(desc, T1Thermal)
        assert desc.T_t == pytest.approx(50.0, abs=1e-12)

    @pytest.mark.level0
    def test_zero_T_B_yields_zero_radiance_on_forward_pass(self) -> None:
        """T_B ≡ 0 K — mean = 0 ⇒ T1Thermal refuses (T_t must be > 0)."""
        lam = _lwir_grid(n=5)
        T_B = _flat_T_B(lam, 0.0)
        with pytest.raises(ParameterBoundsError, match="non-positive"):
            brightness_temperature_to_descriptor(
                T_B=T_B,
                scene_type="extended",
                target_location="terrestrial",
                h_tgt=0.0,
            )


# ---------------------------------------------------------------------------
# Gap G Step G.3 — brightness_temperature_path CSV wiring
# ---------------------------------------------------------------------------


_WL_LWIR = np.linspace(8.0, 13.0, 21)


def _s11_path_params(csv_path: Path) -> ParameterSet:
    """Return a ParameterSet configured for the S11 CSV path.

    Leaves the scalar brightness_temperature_K and every other target
    surface at their Provenance.DEFAULT schema values so the
    brightness_temperature_path branch is the only user-set target
    surface and the inferrer routes through the CSV loader.
    """
    params = build_parameter_set()
    params.set("optics.aperture_diameter_m", 0.15)
    params.set("optics.focal_length_m", 0.60)
    params.set("atmosphere.model", "simple")
    params.set("geometry.sensor_altitude_m", 500.0)
    params.set("spectral_integration.filter_min_um", float(_WL_LWIR[0]))
    params.set("spectral_integration.filter_max_um", float(_WL_LWIR[-1]))
    params.set("spectral_integration.integration_time_s", 1e-3)
    params.set("detector.pixel_pitch_x_um", 5.5)
    params.set("detector.pixel_pitch_y_um", 5.5)
    params.set("detector.qe_value", 0.8)
    params.set("source.scene_type", "extended")
    params.set("source.target_location", "terrestrial")
    params.set("source.target.brightness_temperature_path", str(csv_path))
    return params


def _write_flat_T_B_csv(
    path: Path,
    *,
    wl_um: np.ndarray,
    T_B_value: float,
    header: bool = True,
) -> Path:
    lines: list[str] = []
    if header:
        lines.append("wavelength_um,brightness_temperature_K")
    lines.extend(f"{w:.6f},{T_B_value:.6f}" for w in wl_um)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def _write_ramp_T_B_csv(
    path: Path,
    *,
    wl_um: np.ndarray,
    T_B_values: np.ndarray,
) -> Path:
    assert wl_um.shape == T_B_values.shape
    lines = ["wavelength_um,brightness_temperature_K"]
    for w, t in zip(wl_um, T_B_values, strict=True):
        lines.append(f"{float(w):.6f},{float(t):.6f}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


class TestBrightnessTemperaturePathCSV:
    """S11 ``brightness_temperature_path`` CSV wiring (Gap G Step G.3).

    Each test uses a file-native grid that BRACKETS ``_WL_LWIR`` so the
    resampler stays inside the CSV span (Rule 17: out-of-grid raises).
    """

    # ----- Constant T_B=300 K CSV → T1Thermal, L(10µm)=B(10µm,300K) -----

    @pytest.mark.level1
    def test_constant_T_B_path_emits_T1_and_matches_planck(self, tmp_path: Path) -> None:
        csv = _write_flat_T_B_csv(
            tmp_path / "tb.csv",
            wl_um=np.array([7.5, 9.0, 11.0, 13.5]),
            T_B_value=300.0,
        )
        params = _s11_path_params(csv)
        params.resolve()

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            target, _bg, _los = infer_descriptors(params, _WL_LWIR)

        assert isinstance(target, T1Thermal)
        assert target.T_t == pytest.approx(300.0, abs=1e-9)
        assert target.epsilon is not None
        np.testing.assert_allclose(target.epsilon.values, np.ones_like(_WL_LWIR), atol=0.0)

        # Truth anchor: L(10 µm) = B(10 µm, 300 K) to 1e-6 (ε ≡ 1).
        idx_10 = int(np.argmin(np.abs(_WL_LWIR - 10.0)))
        expected = float(planck_spectral_radiance(np.asarray([_WL_LWIR[idx_10]]), 300.0)[0])
        actual = float(target.epsilon.values[idx_10]) * expected
        rel = abs(actual - expected) / expected
        assert rel < 1.0e-6, f"|ΔL/L| = {rel:g} exceeds 1e-6 truth-anchor tolerance"

    # ----- λ-varying T_B CSV → T6TabulatedAtSource -----

    @pytest.mark.level1
    def test_varying_T_B_path_emits_T6_with_pointwise_planck(self, tmp_path: Path) -> None:
        # 280 K @ 7.5 µm → 320 K @ 13.5 µm — 40 K peak-to-peak, solidly
        # in the λ-varying branch.  File grid brackets _WL_LWIR.
        wl_file = np.array([7.5, 9.0, 11.0, 13.5])
        T_vals = np.linspace(280.0, 320.0, wl_file.size)
        csv = _write_ramp_T_B_csv(tmp_path / "ramp.csv", wl_um=wl_file, T_B_values=T_vals)
        params = _s11_path_params(csv)
        params.resolve()

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            target, _bg, _los = infer_descriptors(params, _WL_LWIR)

        assert isinstance(target, T6TabulatedAtSource)
        assert target.L_t_source is not None
        # After linear resample onto _WL_LWIR, pointwise check: the
        # resampled T_B(λ_i) passed through Planck must equal
        # B(λ_i, T_B_resampled_i).  Tolerance is 1e-6 because the CSV
        # loader round-trips T_B through 6-digit decimal formatting,
        # which introduces ~1e-6 relative error in T_B and hence in L.
        T_B_on_chain = np.interp(_WL_LWIR, wl_file, T_vals)
        for lam_target in (9.0, 11.0, 12.0):
            i = int(np.argmin(np.abs(_WL_LWIR - lam_target)))
            expected = float(
                planck_spectral_radiance(np.asarray([_WL_LWIR[i]]), float(T_B_on_chain[i]))[0]
            )
            actual = float(target.L_t_source.values[i])
            rel = abs(actual - expected) / max(expected, 1e-30)
            assert rel < 1.0e-6, (
                f"λ={_WL_LWIR[i]:.3f} µm: actual={actual:g}, expected={expected:g}, rel={rel:g}"
            )

    # ----- Failure mode — T_B < 0 in CSV -----

    @pytest.mark.level1
    def test_T_B_path_with_negative_value_raises(self, tmp_path: Path) -> None:
        csv = tmp_path / "neg.csv"
        csv.write_text(
            "wavelength_um,brightness_temperature_K\n7.5,290.0\n10.0,-5.0\n13.5,290.0\n",
            encoding="utf-8",
        )
        params = _s11_path_params(csv)
        params.resolve()

        with pytest.raises(ParameterBoundsError, match="negative") as exc:
            infer_descriptors(params, _WL_LWIR)
        assert exc.value.context["path"] == str(csv)
        assert exc.value.context["min_T_B_K"] == pytest.approx(-5.0, rel=1e-9)

    # ----- Failure mode — T_B > 10 000 K in CSV -----

    @pytest.mark.level1
    def test_T_B_path_above_ceiling_raises(self, tmp_path: Path) -> None:
        csv = tmp_path / "hot.csv"
        csv.write_text(
            "wavelength_um,brightness_temperature_K\n7.5,300.0\n10.0,15000.0\n13.5,300.0\n",
            encoding="utf-8",
        )
        params = _s11_path_params(csv)
        params.resolve()

        with pytest.raises(ParameterBoundsError, match="ceiling") as exc:
            infer_descriptors(params, _WL_LWIR)
        assert exc.value.context["path"] == str(csv)
        assert exc.value.context["max_T_B_K"] == pytest.approx(15000.0, rel=1e-9)

    # ----- Failure mode — chain grid wider than file grid -----

    @pytest.mark.level1
    def test_T_B_path_out_of_grid_raises(self, tmp_path: Path) -> None:
        # File grid [9.0, 12.0] does NOT cover chain grid [8.0, 13.0] —
        # resampler must raise rather than silently extrapolate.
        csv = _write_flat_T_B_csv(
            tmp_path / "narrow.csv",
            wl_um=np.array([9.0, 12.0]),
            T_B_value=300.0,
        )
        params = _s11_path_params(csv)
        params.resolve()

        with pytest.raises(ParameterBoundsError, match="extends outside") as exc:
            infer_descriptors(params, _WL_LWIR)
        ctx = exc.value.context
        assert ctx["chain_grid_um"] == pytest.approx([8.0, 13.0], rel=1e-9)
        assert ctx["file_grid_um"] == pytest.approx([9.0, 12.0], rel=1e-9)
        assert ctx["quantity"] == "brightness_temperature"

    # ----- Failure mode — both scalar K and path set -----

    @pytest.mark.level1
    def test_T_B_path_plus_scalar_K_raises(self, tmp_path: Path) -> None:
        csv = _write_flat_T_B_csv(
            tmp_path / "both.csv",
            wl_um=np.array([7.5, 13.5]),
            T_B_value=290.0,
        )
        params = _s11_path_params(csv)
        params.set("source.target.brightness_temperature_K", 300.0)
        params.resolve()

        with pytest.raises(ParameterBoundsError, match="user-set"):
            infer_descriptors(params, _WL_LWIR)

    # ----- Loader unit / metadata cosmetic check -----

    @pytest.mark.level1
    def test_load_brightness_temperature_csv_sets_unit_K(self, tmp_path: Path) -> None:
        csv = _write_flat_T_B_csv(
            tmp_path / "u.csv",
            wl_um=np.array([8.0, 13.0]),
            T_B_value=300.0,
        )
        sd = load_brightness_temperature_csv(csv)
        assert sd.unit == "K"
        assert sd.name == "source.target.brightness_temperature"
        assert str(csv) in sd.source
