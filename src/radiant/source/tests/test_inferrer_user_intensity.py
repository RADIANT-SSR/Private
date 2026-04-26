"""Tests for the S10 user_intensity → T7IntensityAtSource inferrer wiring.

Phase 5 Step 5.1 of the Target Definition Matrix Implementation Plan
(ADR-0004): the inferrer routes ``source.target.user_intensity_path``
(a two-column ``(wavelength_um, I_t_source [W/sr/µm])`` CSV) through
:func:`radiant.source.converters.user_intensity.user_intensity_to_descriptor`
and emits a :class:`~radiant.core.descriptors.T7IntensityAtSource`
descriptor — the S10 escape-hatch descriptor for point-source targets.

Category B scope
----------------
- Dimensional audit: the converter does not mutate units (canonical
  W/sr/µm in → same out on the chain grid).  A vacuum chain-run verifies
  the intensity flows through the A_fict cancellation to a finite
  point-source SNR.
- Failure modes: mutual-exclusion rejections against every other
  thermal / reflective / S8 spec form; at_aperture guard; non-point
  scene_type guard; negative intensity; missing / empty / malformed
  CSV; grid out-of-bounds extrapolation.
- Serialization round-trip: T7IntensityAtSource round-trips via
  ``SpectralData.to_dict`` / ``from_dict`` without loss.
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
    T7IntensityAtSource,
)
from radiant.core.parameters import ParameterBoundsError, ParameterSet
from radiant.core.spectral import SpectralData
from radiant.source._inferrer import infer_descriptors
from radiant.source.converters.user_intensity import (
    load_user_intensity_csv,
    user_intensity_to_descriptor,
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
    I_value: float,
    header: bool = True,
) -> Path:
    """Write a two-column CSV with a constant I_t_source on ``wl_um``."""
    lines: list[str] = []
    if header:
        lines.append("wavelength_um,I_t_source_W_per_sr_per_um")
    for wl in wl_um:
        lines.append(f"{float(wl)},{float(I_value)}")
    path.write_text("\n".join(lines))
    return path


def _user_intensity_params(
    csv_path: Path,
    *,
    wl_um: np.ndarray = _WL_LWIR,
) -> ParameterSet:
    """Return a ParameterSet configured for the S10 fast-path.

    Forces ``scene_type='point_source'`` (matrix §7 row S10) and leaves
    the legacy (ε, T) / reflectance / S8 / S11 / S12 surfaces at their
    Provenance.DEFAULT schema values so the inferrer's ``_is_user_set``
    guards return False on them.
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
    params.set("source.scene_type", "point_source")
    params.set("source.target_location", "terrestrial")
    params.set("source.target.range_m", 100_000.0)
    params.set("source.target.user_intensity_path", str(csv_path))
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
# Truth Anchor 1 — chain run reaches finite SNR on a vacuum path
# ---------------------------------------------------------------------------


class TestUserIntensityChainRun:
    """S10 CSV routed through the inferrer drives the full chain to SNR > 0.

    Uses the ``exo`` vacuum atmosphere so τ_up ≡ 1 and L_path_up ≡ 0.
    Verifies that:

    1. The chain reaches PerformanceStage with finite SNR.
    2. SourceStage publishes ``projected_area_m2 = A_fict`` so the
       downstream single-camera-equation cancels to the correct
       point-source form (see ADR-0004 §Assembly contract).
    3. The at-aperture radiance ``L_ap = I / A_fict`` to within
       numerical tolerance (vacuum limit).
    """

    @pytest.mark.level2
    def test_chain_runs_on_vacuum_path(self, tmp_path: Path) -> None:
        I_value = 1.0  # W/sr/µm — sensible order-of-magnitude for LWIR
        csv_path = _write_flat_csv(
            tmp_path / "user_intensity.csv",
            wl_um=_WL_LWIR,
            I_value=I_value,
        )

        session = RadiantSession(wavelength_um=_WL_LWIR)
        params = session.default_params()
        params.set("atmosphere.model", "exo")
        params.set("geometry.sensor_altitude_m", 800_000.0)
        params.set("platform.h_sensor", 800_000.0)
        params.set("source.scene_type", "point_source")
        params.set("source.target_location", "terrestrial")
        params.set("source.target.range_m", 800_000.0)
        params.set("source.target.user_intensity_path", str(csv_path))
        _seed_optics_detector_readout_lwir(params)
        params.resolve()

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            result = session.run(params)

        assert math.isfinite(result.metrics["snr"])
        assert result.metrics["snr"] > 0.0

        # SourceStage must publish projected_area_m2 == A_fict so the
        # downstream camera equation cancels A_fict correctly.
        A_fict = T7IntensityAtSource.REFERENCE_AREA_M2
        published = result.stage_outputs["source"]["projected_area_m2"]
        assert published == pytest.approx(A_fict, rel=0.0, abs=0.0)

        # Vacuum limit: L_ap = I / A_fict.
        L_ap = result.frames["at_aperture"].spectral_radiance
        assert np.all(np.isfinite(L_ap))
        np.testing.assert_allclose(
            L_ap,
            I_value / A_fict,
            rtol=5e-3,
            atol=0.0,
        )

    @pytest.mark.level1
    def test_inferrer_emits_T7IntensityAtSource(self, tmp_path: Path) -> None:
        csv_path = _write_flat_csv(
            tmp_path / "user_intensity.csv",
            wl_um=_WL_LWIR,
            I_value=5.0,
        )
        params = _user_intensity_params(csv_path, wl_um=_WL_LWIR)
        params.resolve()

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            target, _bg, _los = infer_descriptors(params, _WL_LWIR)

        assert isinstance(target, T7IntensityAtSource)
        assert not isinstance(target, T1Thermal)
        assert target.I_t_source is not None
        assert target.scene_type == "point_source"

        # Values preserved on chain grid (flat input → flat output).
        np.testing.assert_allclose(
            target.I_t_source.values,
            np.full_like(_WL_LWIR, 5.0),
            rtol=1e-12,
            atol=0.0,
        )
        np.testing.assert_array_equal(target.I_t_source.wavelength_um, _WL_LWIR)
        assert target.I_t_source.unit == "W/sr/um"


# ---------------------------------------------------------------------------
# T7 descriptor guards
# ---------------------------------------------------------------------------


class TestT7DescriptorGuards:
    """T7IntensityAtSource.__post_init__ rejects unphysical payloads."""

    def _sd(
        self,
        values: np.ndarray,
        unit: str = "W/sr/um",
    ) -> SpectralData:
        wl = np.linspace(8.0, 13.0, values.size)
        return SpectralData(
            name="test.I",
            wavelength_um=wl,
            values=values,
            unit=unit,
            source="test::T7 guards",
        )

    @pytest.mark.level1
    def test_requires_I_t_source(self) -> None:
        with pytest.raises(ParameterBoundsError, match="I_t_source is required"):
            T7IntensityAtSource(
                scene_type="point_source",
                target_location="terrestrial",
                h_tgt=0.0,
                I_t_source=None,
            )

    @pytest.mark.level1
    def test_rejects_extended_scene_type(self) -> None:
        I_sd = self._sd(np.full(11, 1.0))
        with pytest.raises(ParameterBoundsError, match="scene_type"):
            T7IntensityAtSource(
                scene_type="extended",
                target_location="terrestrial",
                h_tgt=0.0,
                I_t_source=I_sd,
            )

    @pytest.mark.level1
    def test_rejects_sub_pixel_scene_type(self) -> None:
        I_sd = self._sd(np.full(11, 1.0))
        with pytest.raises(ParameterBoundsError, match="scene_type"):
            T7IntensityAtSource(
                scene_type="sub_pixel",
                target_location="terrestrial",
                h_tgt=0.0,
                I_t_source=I_sd,
            )

    @pytest.mark.level1
    def test_rejects_at_aperture_target_location(self) -> None:
        I_sd = self._sd(np.full(11, 1.0))
        # Note: base TargetDescriptor.__post_init__ also rejects
        # at_aperture + non-extended; either error message is acceptable.
        with pytest.raises(ParameterBoundsError, match="at_aperture"):
            T7IntensityAtSource(
                scene_type="point_source",
                target_location="at_aperture",
                I_t_source=I_sd,
            )

    @pytest.mark.level1
    def test_rejects_non_canonical_unit(self) -> None:
        I_sd = self._sd(np.full(11, 1.0), unit="W/m^2/sr/um")
        with pytest.raises(ParameterBoundsError, match="W/sr/um"):
            T7IntensityAtSource(
                scene_type="point_source",
                target_location="terrestrial",
                h_tgt=0.0,
                I_t_source=I_sd,
            )

    @pytest.mark.level1
    def test_rejects_negative_intensity(self) -> None:
        vals = np.full(11, 1.0)
        vals[5] = -1e-3
        I_sd = self._sd(vals)
        with pytest.raises(ParameterBoundsError, match="negative"):
            T7IntensityAtSource(
                scene_type="point_source",
                target_location="terrestrial",
                h_tgt=0.0,
                I_t_source=I_sd,
            )

    @pytest.mark.level1
    def test_no_A_t_or_shape_field(self) -> None:
        """T7 deliberately does not expose A_t / shape on the descriptor surface."""
        I_sd = self._sd(np.full(11, 1.0))
        t7 = T7IntensityAtSource(
            scene_type="point_source",
            target_location="terrestrial",
            h_tgt=0.0,
            I_t_source=I_sd,
        )
        assert not hasattr(t7, "A_t")
        assert not hasattr(t7, "shape")


# ---------------------------------------------------------------------------
# Converter pass-through
# ---------------------------------------------------------------------------


class TestConverterPassThrough:
    """The boundary converter does not reshape or rescale I_t_source."""

    @pytest.mark.level1
    def test_heaviside_I_preserved_by_converter(self) -> None:
        wl = np.linspace(8.0, 13.0, 41)
        step = 10.0  # µm
        I_vals = np.where(wl < step, 0.5, 2.0).astype(np.float64)
        I_sd = SpectralData(
            name="test.heaviside_I",
            wavelength_um=wl,
            values=I_vals,
            unit="W/sr/um",
            source="test_inferrer_user_intensity::heaviside",
        )

        target = user_intensity_to_descriptor(
            I_t_source=I_sd,
            scene_type="point_source",
            target_location="terrestrial",
            h_tgt=0.0,
        )

        assert isinstance(target, T7IntensityAtSource)
        assert target.I_t_source is not None
        np.testing.assert_array_equal(target.I_t_source.values, I_vals)
        np.testing.assert_array_equal(target.I_t_source.wavelength_um, wl)


# ---------------------------------------------------------------------------
# Serialization round-trip (Category B requirement)
# ---------------------------------------------------------------------------


class TestSerializationRoundTrip:
    """T7 round-trips via SpectralData.to_dict / from_dict without loss."""

    @pytest.mark.level1
    def test_spectraldata_round_trip_preserves_values_and_grid(self) -> None:
        wl = np.linspace(8.0, 13.0, 11)
        vals = np.linspace(0.3, 0.7, 11)
        I_sd = SpectralData(
            name="source.target.user_intensity",
            wavelength_um=wl,
            values=vals,
            unit="W/sr/um",
            source="test::roundtrip",
        )

        target = user_intensity_to_descriptor(
            I_t_source=I_sd,
            scene_type="point_source",
            target_location="terrestrial",
            h_tgt=0.0,
        )
        assert isinstance(target, T7IntensityAtSource)

        payload = target.I_t_source.to_dict()
        restored = SpectralData.from_dict(payload)

        np.testing.assert_array_equal(restored.values, vals)
        np.testing.assert_array_equal(restored.wavelength_um, wl)
        assert restored.unit == "W/sr/um"


# ---------------------------------------------------------------------------
# CSV loader — edge cases
# ---------------------------------------------------------------------------


class TestCSVLoader:
    @pytest.mark.level1
    def test_load_flat_csv_with_header(self, tmp_path: Path) -> None:
        csv_path = _write_flat_csv(
            tmp_path / "flat.csv",
            wl_um=_WL_LWIR,
            I_value=0.3,
            header=True,
        )
        sd = load_user_intensity_csv(csv_path)
        np.testing.assert_array_equal(sd.wavelength_um, _WL_LWIR)
        np.testing.assert_array_equal(sd.values, np.full_like(_WL_LWIR, 0.3))
        assert sd.unit == "W/sr/um"

    @pytest.mark.level1
    def test_load_flat_csv_without_header(self, tmp_path: Path) -> None:
        csv_path = _write_flat_csv(
            tmp_path / "noheader.csv",
            wl_um=_WL_LWIR,
            I_value=0.2,
            header=False,
        )
        sd = load_user_intensity_csv(csv_path)
        np.testing.assert_array_equal(sd.wavelength_um, _WL_LWIR)

    @pytest.mark.level1
    def test_missing_file_raises(self, tmp_path: Path) -> None:
        with pytest.raises(ParameterBoundsError, match="not found"):
            load_user_intensity_csv(tmp_path / "does_not_exist.csv")

    @pytest.mark.level1
    def test_empty_file_raises(self, tmp_path: Path) -> None:
        csv_path = tmp_path / "empty.csv"
        csv_path.write_text("")
        with pytest.raises(ParameterBoundsError, match="empty"):
            load_user_intensity_csv(csv_path)

    @pytest.mark.level1
    def test_single_row_raises(self, tmp_path: Path) -> None:
        csv_path = tmp_path / "one_row.csv"
        csv_path.write_text("wavelength_um,I\n10.0,5.0\n")
        with pytest.raises(ParameterBoundsError, match="fewer than 2"):
            load_user_intensity_csv(csv_path)

    @pytest.mark.level1
    def test_malformed_row_raises(self, tmp_path: Path) -> None:
        csv_path = tmp_path / "bad.csv"
        csv_path.write_text("wavelength_um,I\n10.0,5.0\nnot-a-number,7.0\n")
        with pytest.raises(ParameterBoundsError, match="floats"):
            load_user_intensity_csv(csv_path)


# ---------------------------------------------------------------------------
# Failure modes — converter rejection guards
# ---------------------------------------------------------------------------


class TestConverterRejections:
    @pytest.mark.level1
    def test_negative_intensity_raises(self) -> None:
        wl = np.linspace(8.0, 13.0, 11)
        I_bad = np.full_like(wl, 1.0)
        I_bad[5] = -1e-3
        I_sd = SpectralData(
            name="test.negative_I",
            wavelength_um=wl,
            values=I_bad,
            unit="W/sr/um",
            source="test::negative",
        )
        with pytest.raises(ParameterBoundsError, match="negative"):
            user_intensity_to_descriptor(
                I_t_source=I_sd,
                scene_type="point_source",
                target_location="terrestrial",
                h_tgt=0.0,
            )

    @pytest.mark.level1
    def test_at_aperture_rejected(self) -> None:
        wl = np.linspace(8.0, 13.0, 11)
        I_sd = SpectralData(
            name="test.I",
            wavelength_um=wl,
            values=np.full_like(wl, 1.0),
            unit="W/sr/um",
            source="test::at_aperture",
        )
        with pytest.raises(ParameterBoundsError, match="at_aperture"):
            user_intensity_to_descriptor(
                I_t_source=I_sd,
                scene_type="point_source",
                target_location="at_aperture",
            )

    @pytest.mark.level1
    def test_extended_scene_type_rejected(self) -> None:
        wl = np.linspace(8.0, 13.0, 11)
        I_sd = SpectralData(
            name="test.I",
            wavelength_um=wl,
            values=np.full_like(wl, 1.0),
            unit="W/sr/um",
            source="test::extended",
        )
        with pytest.raises(ParameterBoundsError, match="point_source"):
            user_intensity_to_descriptor(
                I_t_source=I_sd,
                scene_type="extended",
                target_location="terrestrial",
                h_tgt=0.0,
            )


# ---------------------------------------------------------------------------
# Failure modes — inferrer mutual-exclusion rejections
# ---------------------------------------------------------------------------


class TestInferrerRejections:
    @pytest.mark.level1
    def test_user_intensity_plus_temperature_raises(self, tmp_path: Path) -> None:
        """S10 + legacy (ε, T) over-specifies the target."""
        csv_path = _write_flat_csv(tmp_path / "u.csv", wl_um=_WL_LWIR, I_value=1.0)
        params = _user_intensity_params(csv_path, wl_um=_WL_LWIR)
        params.set("source.target.temperature", 300.0)
        params.set("source.target.emissivity", 0.9)
        params.resolve()

        with pytest.raises(ParameterBoundsError, match="mutually exclusive"):
            infer_descriptors(params, _WL_LWIR)

    @pytest.mark.level1
    def test_user_intensity_plus_reflectance_raises(self, tmp_path: Path) -> None:
        """S10 + S4 ρ — fast-paths collide."""
        csv_path = _write_flat_csv(tmp_path / "u.csv", wl_um=_WL_VIS, I_value=1.0)
        params = _user_intensity_params(csv_path, wl_um=_WL_VIS)
        params.set("source.target.reflectance", 0.5)
        params.resolve()

        with pytest.raises(ParameterBoundsError, match="mutually exclusive"):
            infer_descriptors(params, _WL_VIS)

    @pytest.mark.level1
    def test_user_intensity_plus_brightness_temperature_raises(self, tmp_path: Path) -> None:
        """S10 + S11 T_B — fast-paths collide."""
        csv_path = _write_flat_csv(tmp_path / "u.csv", wl_um=_WL_LWIR, I_value=1.0)
        params = _user_intensity_params(csv_path, wl_um=_WL_LWIR)
        params.set("source.target.brightness_temperature_K", 290.0)
        params.resolve()

        with pytest.raises(ParameterBoundsError, match="mutually exclusive"):
            infer_descriptors(params, _WL_LWIR)

    @pytest.mark.level1
    def test_user_intensity_plus_radiance_temperature_raises(self, tmp_path: Path) -> None:
        """S10 + S12 T_R — fast-paths collide."""
        csv_path = _write_flat_csv(tmp_path / "u.csv", wl_um=_WL_LWIR, I_value=1.0)
        params = _user_intensity_params(csv_path, wl_um=_WL_LWIR)
        params.set("source.target.radiance_temperature_K", 290.0)
        params.set("source.target.radiance_temperature_band_lo_um", 8.0)
        params.set("source.target.radiance_temperature_band_hi_um", 12.0)
        params.resolve()

        with pytest.raises(ParameterBoundsError, match="mutually exclusive"):
            infer_descriptors(params, _WL_LWIR)

    @pytest.mark.level1
    def test_user_intensity_plus_user_radiance_raises(self, tmp_path: Path) -> None:
        """S10 + S8 are different radiometric quantities — disjoint."""
        I_csv = _write_flat_csv(tmp_path / "i.csv", wl_um=_WL_LWIR, I_value=1.0)
        L_csv = _write_flat_csv(
            tmp_path / "l.csv",
            wl_um=_WL_LWIR,
            I_value=5.0,
        )
        params = _user_intensity_params(I_csv, wl_um=_WL_LWIR)
        params.set("source.target.user_radiance_path", str(L_csv))
        params.resolve()

        with pytest.raises(ParameterBoundsError, match="mutually exclusive"):
            infer_descriptors(params, _WL_LWIR)

    @pytest.mark.level1
    def test_negative_values_in_csv_raise_through_inferrer(self, tmp_path: Path) -> None:
        """Negative I in the CSV surfaces the converter guard at inference."""
        csv_path = tmp_path / "negative.csv"
        lines = ["wavelength_um,I"]
        for i, wl in enumerate(_WL_LWIR):
            val = -1.0 if i == 5 else 1.0
            lines.append(f"{float(wl)},{val}")
        csv_path.write_text("\n".join(lines))

        params = _user_intensity_params(csv_path, wl_um=_WL_LWIR)
        params.resolve()

        with pytest.raises(ParameterBoundsError, match="negative"):
            infer_descriptors(params, _WL_LWIR)

    @pytest.mark.level1
    def test_missing_csv_raises_actionable_error(self, tmp_path: Path) -> None:
        """A missing CSV surfaces a Rule-15 actionable error at inference."""
        params = _user_intensity_params(tmp_path / "does_not_exist.csv", wl_um=_WL_LWIR)
        params.resolve()

        with pytest.raises(ParameterBoundsError, match="not found"):
            infer_descriptors(params, _WL_LWIR)

    @pytest.mark.level1
    def test_grid_out_of_bounds_raises(self, tmp_path: Path) -> None:
        """CSV grid narrower than the chain grid refuses rather than extrapolating."""
        csv_path = _write_flat_csv(
            tmp_path / "narrow.csv",
            wl_um=np.linspace(9.0, 12.0, 11),  # narrower than _WL_LWIR
            I_value=1.0,
        )
        params = _user_intensity_params(csv_path, wl_um=_WL_LWIR)
        params.resolve()

        with pytest.raises(ParameterBoundsError, match="does not cover"):
            infer_descriptors(params, _WL_LWIR)
