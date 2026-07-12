"""Tests for the S8 user_radiance → T6TabulatedAtSource inferrer wiring.

Phase 4 Step 4.1 of the Target Definition Matrix Implementation Plan: the
inferrer routes ``source.target.user_radiance_path`` (a two-column
``(wavelength_um, L_t_source [W/m²/sr/µm])`` CSV) through the new
:func:`radiant.source.converters.user_radiance_to_descriptor` and emits
a :class:`~radiant.core.descriptors.T6TabulatedAtSource` descriptor
(ADR-0003 — the S8 escape-hatch descriptor).

Category B scope
----------------
- Dimensional audit: the converter does not mutate units (canonical
  W/m²/sr/µm in → same out on the chain grid).  A chain-run verifies
  the radiance flows to the aperture correctly in the vacuum limit.
- Failure modes: mutual-exclusion rejections against every other
  thermal / reflective spec form; at_aperture guard; negative
  radiance; missing / empty / malformed CSV.
- Serialization round-trip: T6TabulatedAtSource round-trips via
  ``to_dict`` / ``from_dict`` without loss.
"""

from __future__ import annotations

import math
import warnings
from pathlib import Path

import numpy as np
import pytest

from radiant.api._param_registry import build_parameter_set
from radiant.api.session import RadiantSession
from radiant.core.descriptors import (
    T1Thermal,
    T2Reflective,
    T6TabulatedAtSource,
)
from radiant.core.parameters import ParameterBoundsError, ParameterSet
from radiant.core.spectral import SpectralData
from radiant.source._inferrer import infer_descriptors
from radiant.source.converters.user_radiance import (
    load_user_radiance_csv,
    user_radiance_to_descriptor,
)

_WL_LWIR = np.linspace(8.0, 13.0, 21)
_WL_VIS = np.linspace(0.4, 0.8, 21)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_flat_csv(
    path: Path,
    *,
    wl_um: np.ndarray,
    L_value: float,
    header: bool = True,
) -> Path:
    """Write a two-column CSV with a constant L_t_source on ``wl_um``."""
    lines: list[str] = []
    if header:
        lines.append("wavelength_um,L_t_source_W_per_m2_per_sr_per_um")
    for wl in wl_um:
        lines.append(f"{float(wl)},{float(L_value)}")
    path.write_text("\n".join(lines))
    return path


def _user_radiance_params(
    csv_path: Path,
    *,
    wl_um: np.ndarray = _WL_LWIR,
) -> ParameterSet:
    """Return a ParameterSet configured for the S8 fast-path.

    Leaves the legacy (ε, T) / reflectance / brightness_temperature /
    radiance_temperature surfaces at their Provenance.DEFAULT schema
    values so the inferrer's ``_is_user_set`` guards return False on
    them and the S8 branch is reachable.
    """
    params = build_parameter_set()
    params.set("optics.aperture_diameter_m", 0.15)
    params.set("optics.focal_length_m", 0.60)
    params.set("atmosphere.model", "simple")
    params.set("geometry.sensor_altitude_m", 500.0)
    params.set("spectral_integration.filter_min_um", float(wl_um[0]))
    params.set("spectral_integration.filter_max_um", float(wl_um[-1]))
    params.set("spectral_integration.integration_time_s", 1e-3)
    params.set("detector.pixel_pitch_x_um", 5.5)
    params.set("detector.pixel_pitch_y_um", 5.5)
    params.set("detector.qe_value", 0.8)
    params.set("source.scene_type", "extended")
    params.set("source.target_location", "terrestrial")
    params.set("source.target.user_radiance_path", str(csv_path))
    return params


def _seed_optics_detector_readout_lwir(params: ParameterSet) -> None:
    """Minimal LWIR imaging system for the chain-run integration test."""
    params.set("optics.aperture_diameter_m", 0.15)
    params.set("optics.focal_length_m", 0.45)
    params.set("optics.transmission_scalar", 0.62)
    params.set("detector.pixel_pitch_x_um", 20.0)
    params.set("detector.pixel_pitch_y_um", 20.0)
    params.set("detector.qe_value", 0.55)
    params.set("detector.dark_rate_e_per_s", 800.0)
    params.set("spectral_integration.filter_min_um", 8.0)
    params.set("spectral_integration.filter_max_um", 13.0)
    params.set("spectral_integration.integration_time_s", 0.010)
    params.set("readout.read_noise_e_rms", 12.0)
    params.set("readout.gain_e_per_dn", 2.0)
    params.set("readout.adc_bits", 14)


# ---------------------------------------------------------------------------
# Truth Anchor 1 — chain run with user_radiance produces finite, nonzero L
# ---------------------------------------------------------------------------


class TestUserRadianceChainRun:
    """S8 CSV routed through the inferrer drives the full chain to SNR > 0.

    Uses the ``exo`` vacuum atmosphere so that there is no transport
    attenuation — the at-aperture radiance equals the at-source radiance
    to within the sampling fidelity of the spectral-integration trapz.
    """

    @pytest.mark.level2
    def test_chain_runs_and_at_aperture_matches_user_radiance(self, tmp_path: Path) -> None:
        L_value = 10.0  # W/m²/sr/µm — well above LWIR blackbody floor
        csv_path = _write_flat_csv(
            tmp_path / "user_radiance.csv",
            wl_um=_WL_LWIR,
            L_value=L_value,
        )

        session = RadiantSession(wavelength_um=_WL_LWIR)
        params = session.default_params()
        params.set("atmosphere.model", "exo")
        params.set("geometry.sensor_altitude_m", 800_000.0)
        params.set("source.target.user_radiance_path", str(csv_path))
        _seed_optics_detector_readout_lwir(params)
        params.resolve()

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            result = session.run(params)

        # Chain reached PerformanceStage and produced finite SNR > 0.
        assert math.isfinite(result.metrics["snr"])
        assert result.metrics["snr"] > 0.0

        # At-aperture radiance is finite and strictly positive.
        L_ap = result.frames["at_aperture"].spectral_radiance
        assert np.all(np.isfinite(L_ap))
        assert np.all(L_ap > 0.0)

        # Vacuum transport: L_aperture ≈ L_t_source (no attenuation).
        np.testing.assert_allclose(L_ap, L_value, rtol=5e-3, atol=0.0)

    @pytest.mark.level1
    def test_inferrer_emits_T6TabulatedAtSource(self, tmp_path: Path) -> None:
        csv_path = _write_flat_csv(
            tmp_path / "user_radiance.csv",
            wl_um=_WL_LWIR,
            L_value=5.0,
        )
        params = _user_radiance_params(csv_path, wl_um=_WL_LWIR)
        params.resolve()

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            target, _bg, _los = infer_descriptors(params, _WL_LWIR)

        assert isinstance(target, T6TabulatedAtSource)
        assert not isinstance(target, (T1Thermal, T2Reflective))
        assert target.L_t_source is not None

        # Values preserved on chain grid (flat input → flat output).
        np.testing.assert_allclose(
            target.L_t_source.values,
            np.full_like(_WL_LWIR, 5.0),
            rtol=1e-12,
            atol=0.0,
        )
        np.testing.assert_array_equal(target.L_t_source.wavelength_um, _WL_LWIR)


# ---------------------------------------------------------------------------
# Truth Anchor 2 — converter is pass-through on SpectralData input
# ---------------------------------------------------------------------------


class TestConverterPassThrough:
    """The boundary converter does not reshape or rescale L_t_source.

    The inferrer loads the CSV on the file's native grid and resamples
    onto the chain grid via ``TabulatedRadianceSource``; the converter
    itself is a pure dataclass constructor once the SpectralData
    arrives.  This test exercises the converter directly with a
    Heaviside step on a non-chain grid to confirm the values flow
    unchanged.
    """

    @pytest.mark.level1
    def test_heaviside_L_preserved_by_converter(self) -> None:
        wl = np.linspace(8.0, 13.0, 41)
        step = 10.0  # µm
        L_vals = np.where(wl < step, 2.0, 20.0).astype(np.float64)
        L_sd = SpectralData(
            name="test.heaviside_L",
            wavelength_um=wl,
            values=L_vals,
            unit="W/m^2/sr/um",
            source="test_inferrer_user_radiance::heaviside",
        )

        target = user_radiance_to_descriptor(
            L_t_source=L_sd,
            scene_type="extended",
            target_location="terrestrial",
            h_tgt=0.0,
        )

        assert isinstance(target, T6TabulatedAtSource)
        assert target.L_t_source is not None
        np.testing.assert_array_equal(target.L_t_source.values, L_vals)
        np.testing.assert_array_equal(target.L_t_source.wavelength_um, wl)


# ---------------------------------------------------------------------------
# Serialization round-trip (Category B requirement)
# ---------------------------------------------------------------------------


class TestSerializationRoundTrip:
    """T6TabulatedAtSource round-trips via SpectralData.to_dict / from_dict.

    T6TabulatedAtSource itself is a frozen dataclass; the heavy lifting
    lives in :class:`SpectralData`, which carries ``L_t_source``.  The
    round-trip proves the S8 boundary preserves the full user payload
    across serialize / deserialize.
    """

    @pytest.mark.level1
    def test_spectraldata_round_trip_preserves_values_and_grid(self) -> None:
        wl = np.linspace(8.0, 13.0, 11)
        vals = np.linspace(3.0, 7.0, 11)
        L_sd = SpectralData(
            name="source.target.user_radiance",
            wavelength_um=wl,
            values=vals,
            unit="W/m^2/sr/um",
            source="test::roundtrip",
        )

        target = user_radiance_to_descriptor(
            L_t_source=L_sd,
            scene_type="extended",
            target_location="terrestrial",
            h_tgt=0.0,
        )
        assert isinstance(target, T6TabulatedAtSource)

        payload = target.L_t_source.to_dict()
        restored = SpectralData.from_dict(payload)

        np.testing.assert_array_equal(restored.values, vals)
        np.testing.assert_array_equal(restored.wavelength_um, wl)
        assert restored.unit == "W/m^2/sr/um"


# ---------------------------------------------------------------------------
# CSV loader — edge cases
# ---------------------------------------------------------------------------


class TestCSVLoader:
    @pytest.mark.level1
    def test_load_flat_csv_with_header(self, tmp_path: Path) -> None:
        csv_path = _write_flat_csv(
            tmp_path / "flat.csv",
            wl_um=_WL_LWIR,
            L_value=3.0,
            header=True,
        )
        sd = load_user_radiance_csv(csv_path)
        np.testing.assert_array_equal(sd.wavelength_um, _WL_LWIR)
        np.testing.assert_array_equal(sd.values, np.full_like(_WL_LWIR, 3.0))
        assert sd.unit == "W/m^2/sr/um"

    @pytest.mark.level1
    def test_load_flat_csv_without_header(self, tmp_path: Path) -> None:
        csv_path = _write_flat_csv(
            tmp_path / "noheader.csv",
            wl_um=_WL_LWIR,
            L_value=2.0,
            header=False,
        )
        sd = load_user_radiance_csv(csv_path)
        np.testing.assert_array_equal(sd.wavelength_um, _WL_LWIR)

    @pytest.mark.level1
    def test_missing_file_raises(self, tmp_path: Path) -> None:
        with pytest.raises(ParameterBoundsError, match="not found"):
            load_user_radiance_csv(tmp_path / "does_not_exist.csv")

    @pytest.mark.level1
    def test_empty_file_raises(self, tmp_path: Path) -> None:
        csv_path = tmp_path / "empty.csv"
        csv_path.write_text("")
        with pytest.raises(ParameterBoundsError, match="empty"):
            load_user_radiance_csv(csv_path)

    @pytest.mark.level1
    def test_single_row_raises(self, tmp_path: Path) -> None:
        csv_path = tmp_path / "one_row.csv"
        csv_path.write_text("wavelength_um,L\n10.0,5.0\n")
        with pytest.raises(ParameterBoundsError, match="fewer than 2"):
            load_user_radiance_csv(csv_path)

    @pytest.mark.level1
    def test_malformed_row_raises(self, tmp_path: Path) -> None:
        csv_path = tmp_path / "bad.csv"
        csv_path.write_text("wavelength_um,L\n10.0,5.0\nnot-a-number,7.0\n")
        with pytest.raises(ParameterBoundsError, match="floats"):
            load_user_radiance_csv(csv_path)


# ---------------------------------------------------------------------------
# Failure modes — converter rejection guards
# ---------------------------------------------------------------------------


class TestConverterRejections:
    @pytest.mark.level1
    def test_negative_radiance_raises(self) -> None:
        wl = np.linspace(8.0, 13.0, 11)
        L_bad = np.full_like(wl, 5.0)
        L_bad[5] = -1e-3  # single sign-flip to trigger the guard
        L_sd = SpectralData(
            name="test.negative_L",
            wavelength_um=wl,
            values=L_bad,
            unit="W/m^2/sr/um",
            source="test::negative",
        )
        with pytest.raises(ParameterBoundsError, match="negative"):
            user_radiance_to_descriptor(
                L_t_source=L_sd,
                scene_type="extended",
                target_location="terrestrial",
                h_tgt=0.0,
            )

    @pytest.mark.level1
    def test_at_aperture_rejected(self) -> None:
        wl = np.linspace(8.0, 13.0, 11)
        L_sd = SpectralData(
            name="test.L",
            wavelength_um=wl,
            values=np.full_like(wl, 5.0),
            unit="W/m^2/sr/um",
            source="test::at_aperture",
        )
        with pytest.raises(ParameterBoundsError, match="at_aperture"):
            user_radiance_to_descriptor(
                L_t_source=L_sd,
                scene_type="extended",
                target_location="at_aperture",
            )


# ---------------------------------------------------------------------------
# Failure modes — inferrer mutual-exclusion rejections
# ---------------------------------------------------------------------------


class TestInferrerRejections:
    @pytest.mark.level1
    def test_user_radiance_plus_temperature_raises(self, tmp_path: Path) -> None:
        """S8 + legacy (ε, T) over-specifies the target radiance."""
        csv_path = _write_flat_csv(tmp_path / "u.csv", wl_um=_WL_LWIR, L_value=3.0)
        params = _user_radiance_params(csv_path, wl_um=_WL_LWIR)
        params.set("source.target.temperature", 300.0)
        params.set("source.target.emissivity", 0.9)
        params.resolve()

        with pytest.raises(ParameterBoundsError, match="mutually exclusive"):
            infer_descriptors(params, _WL_LWIR)

    @pytest.mark.level1
    def test_user_radiance_plus_reflectance_raises(self, tmp_path: Path) -> None:
        """S8 + S4 ρ over-specifies the target radiance."""
        csv_path = _write_flat_csv(tmp_path / "u.csv", wl_um=_WL_VIS, L_value=3.0)
        params = _user_radiance_params(csv_path, wl_um=_WL_VIS)
        params.set("source.target.reflectance", 0.5)
        params.resolve()

        with pytest.raises(ParameterBoundsError, match="mutually exclusive"):
            infer_descriptors(params, _WL_VIS)

    @pytest.mark.level1
    def test_user_radiance_plus_brightness_temperature_raises(self, tmp_path: Path) -> None:
        """S8 + S11 T_B over-specifies the target radiance."""
        csv_path = _write_flat_csv(tmp_path / "u.csv", wl_um=_WL_LWIR, L_value=3.0)
        params = _user_radiance_params(csv_path, wl_um=_WL_LWIR)
        params.set("source.target.brightness_temperature_K", 290.0)
        params.resolve()

        with pytest.raises(ParameterBoundsError, match="mutually exclusive"):
            infer_descriptors(params, _WL_LWIR)

    @pytest.mark.level1
    def test_user_radiance_plus_radiance_temperature_raises(self, tmp_path: Path) -> None:
        """S8 + S12 T_R over-specifies the target radiance."""
        csv_path = _write_flat_csv(tmp_path / "u.csv", wl_um=_WL_LWIR, L_value=3.0)
        params = _user_radiance_params(csv_path, wl_um=_WL_LWIR)
        params.set("source.target.radiance_temperature_K", 290.0)
        params.set("source.target.radiance_temperature_band_lo_um", 8.0)
        params.set("source.target.radiance_temperature_band_hi_um", 12.0)
        params.resolve()

        with pytest.raises(ParameterBoundsError, match="mutually exclusive"):
            infer_descriptors(params, _WL_LWIR)

    @pytest.mark.level1
    def test_negative_values_in_csv_raise_through_inferrer(self, tmp_path: Path) -> None:
        """Negative L in the CSV surfaces the converter guard at inference."""
        csv_path = tmp_path / "negative.csv"
        lines = ["wavelength_um,L"]
        for i, wl in enumerate(_WL_LWIR):
            val = -1.0 if i == 5 else 5.0
            lines.append(f"{float(wl)},{val}")
        csv_path.write_text("\n".join(lines))

        params = _user_radiance_params(csv_path, wl_um=_WL_LWIR)
        params.resolve()

        with pytest.raises(ParameterBoundsError, match="negative"):
            infer_descriptors(params, _WL_LWIR)

    @pytest.mark.level1
    def test_missing_csv_raises_actionable_error(self, tmp_path: Path) -> None:
        """A missing CSV surfaces a Rule-15 actionable error at inference."""
        params = _user_radiance_params(tmp_path / "does_not_exist.csv", wl_um=_WL_LWIR)
        params.resolve()

        with pytest.raises(ParameterBoundsError, match="not found"):
            infer_descriptors(params, _WL_LWIR)
