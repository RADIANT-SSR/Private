"""Integration coverage for shape-driven sub_pixel targets (Q3 Phase 1).

Step 1.3 of the Target Definition Matrix Implementation Plan.  Sibling
of [test_use_case_matrix.py](test_use_case_matrix.py) and
[test_use_case_warnings.py](test_use_case_warnings.py): this file
exercises the shape-wiring path end-to-end for each entry in the v1
shape catalog (sphere, cylinder, flat_plate, box, cone) across a
representative sub_pixel cell per scene-type family.

Coverage matrix
---------------

For each shape:

* **Terrestrial sub_pixel LWIR** — cell 29 analog.
* **Airborne sub_pixel MWIR** — cell 44 analog.
* **Space sub_pixel LWIR** — cell 59 analog.  The plan specifies VIS
  for this slot, but a 300 K T1Thermal target in VIS yields essentially
  zero in-band radiance (Planck tail cutoff at ~4 µm); signal_DN is
  indistinguishable from the read-noise floor and does not probe the
  shape arithmetic.  LWIR keeps the signal non-trivial while still
  exercising the space scene-type family per the plan's intent.

Assertions per (shape, cell):

1. ``session.run(params)`` completes (no raise) — the full chain honors
   shape-driven A_t without aborting.
2. Signal in DN at the detector output is finite and non-negative.
3. ``descriptor.shape`` is an instance of the expected concrete shape
   class from [radiant.source.shapes](../../src/radiant/source/shapes/).
4. ``result.metrics['snr']`` is finite.

Negative path
-------------

``shape="sphere"`` + ``target_location="at_aperture"`` must raise
``ParameterBoundsError``: the S9 spec form provides a spectral radiance
already at the aperture plane, so there is no scene-frame geometry for
``shape.projected_area`` to operate on.  Guard lives in
[_inferrer.py](../../src/radiant/source/_inferrer.py) ``_build_target_descriptor``.

Reference:
[docs/RADIANT_Target_Definition_Matrix.md §3](../../docs/RADIANT_Target_Definition_Matrix.md),
[docs/Target_Definition_Implementation_Plan.md](../../docs/Target_Definition_Implementation_Plan.md)
Step 1.3.
"""

from __future__ import annotations

import warnings

import numpy as np
import pytest

from radiant.api.session import RadiantSession
from radiant.core.parameters import ParameterBoundsError, ParameterSet
from radiant.core.quantity import ReferenceFrame
from radiant.source.shapes import Box, Cone, Cylinder, FlatPlate, Sphere

# ---------------------------------------------------------------------------
# Regime grids and optics seeding — mirror the matrix / warnings sibling tests
# so cell numbering and results are comparable.
# ---------------------------------------------------------------------------


_REGIME_GRIDS: dict[str, np.ndarray] = {
    "VIS": np.linspace(0.4, 0.7, 31),
    "NIR": np.linspace(0.7, 1.0, 31),
    "SWIR": np.linspace(1.0, 2.5, 61),
    "MWIR": np.linspace(3.0, 5.0, 41),
    "LWIR": np.linspace(8.0, 13.0, 51),
}


def _seed_optics_detector_readout(params: ParameterSet, regime: str) -> None:
    """Regime-appropriate imaging seeds — identical to the matrix fixture."""
    if regime in ("VIS", "NIR"):
        pixel_pitch_um, read_noise_e, qe, dark_rate, t_int = 5.0, 5.0, 0.85, 50.0, 0.002
    elif regime == "SWIR":
        pixel_pitch_um, read_noise_e, qe, dark_rate, t_int = 15.0, 20.0, 0.70, 500.0, 0.005
    elif regime == "MWIR":
        pixel_pitch_um, read_noise_e, qe, dark_rate, t_int = 18.0, 20.0, 0.60, 800.0, 0.008
    else:  # LWIR
        pixel_pitch_um, read_noise_e, qe, dark_rate, t_int = 20.0, 12.0, 0.55, 800.0, 0.010

    wl = _REGIME_GRIDS[regime]
    params.set("optics.aperture_diameter_m", 0.15)
    params.set("optics.focal_length_m", 0.45)
    params.set("optics.transmission_scalar", 0.62)
    params.set("detector.pixel_pitch_x_um", pixel_pitch_um)
    params.set("detector.pixel_pitch_y_um", pixel_pitch_um)
    params.set("detector.qe_value", qe)
    params.set("detector.dark_rate_e_per_s", dark_rate)
    params.set("spectral_integration.filter_min_um", float(wl[0]))
    params.set("spectral_integration.filter_max_um", float(wl[-1]))
    params.set("spectral_integration.integration_time_s", t_int)
    params.set("readout.read_noise_e_rms", read_noise_e)
    params.set("readout.gain_e_per_dn", 2.0)
    params.set("readout.adc_bits", 14)


# ---------------------------------------------------------------------------
# Shape catalog × (dim-keys, dim-values) + expected concrete class.
# ---------------------------------------------------------------------------


# Each entry: (shape_name, {param_suffix: value}, expected_concrete_class).
# Dimensions chosen so projected area at nadir is ~1–10 m² — well within
# the sub_pixel regime bands the harness targets (projected_area_m2=100 m²
# at range_m=1e6 in the matrix sibling).  The exact sub_pixel cell here
# uses the matrix range of 1e6 m so √A/d is well above the point-source
# reclassify floor (0.01·PSF_FWHM) across every regime seed.
_SHAPES: tuple[tuple[str, dict[str, float], type], ...] = (
    ("sphere", {"shape_radius_m": 1.0}, Sphere),
    ("cylinder", {"shape_radius_m": 1.0, "shape_length_m": 2.0}, Cylinder),
    ("flat_plate", {"shape_length_m": 2.0, "shape_width_m": 3.0}, FlatPlate),
    ("box", {"shape_length_m": 1.0, "shape_width_m": 2.0, "shape_height_m": 3.0}, Box),
    ("cone", {"shape_base_radius_m": 1.0, "shape_height_m": 2.0}, Cone),
)


# Representative sub_pixel cells per scene-type family (matrix §3.2 / §3.3).
# (cell_id, target_location, regime).  See module docstring for the VIS →
# LWIR substitution on the space row.
_CELLS: tuple[tuple[str, str, str], ...] = (
    ("29", "terrestrial", "LWIR"),
    ("44", "airborne", "MWIR"),
    ("59", "no_atm_space", "LWIR"),
)


# ---------------------------------------------------------------------------
# Per-cell scenario builder
# ---------------------------------------------------------------------------


def _build_params(
    cell_id: str,
    target_location: str,
    regime: str,
    shape_name: str,
    shape_dims: dict[str, float],
) -> tuple[ParameterSet, RadiantSession]:
    """Seed a sub_pixel ParameterSet with the given shape on the given cell."""
    wl = _REGIME_GRIDS[regime]
    session = RadiantSession(wavelength_um=wl)
    params = session.default_params()

    # Target ε + T (back-compat surface; shape is the NEW axis).  Per-regime
    # temperatures match the matrix harness so thermal signal magnitudes
    # line up with the baseline sweep.
    T_t = {"VIS": 300.0, "NIR": 300.0, "SWIR": 400.0, "MWIR": 320.0, "LWIR": 300.0}[regime]
    params.set("source.target.temperature", T_t)
    params.set("source.target.emissivity", 0.95)

    # Scene type + range + fill_fraction: identical to the matrix sub_pixel
    # branch in test_use_case_matrix.py so √A/d and the angular-extent
    # guard fall in the same bucket.
    params.set("source.target_location", "auto")
    params.set("source.scene_type", "sub_pixel")
    params.set("geometry.target_range_m", 1.0e6)
    params.set("source.target.fill_fraction", 0.5)

    # Shape — THE axis this test exercises.  projected_area_m2 is left
    # unset (sentinel 0.0) so the Q3 precedence warning does not fire.
    params.set("source.target.shape", shape_name)
    for suffix, value in shape_dims.items():
        params.set(f"source.target.{suffix}", float(value))

    # Location-specific geometry (matches the matrix sibling).
    if target_location == "airborne":
        params.set("geometry.target_altitude_m", 10_000.0)
        params.set("atmosphere.model", "simple")
        params.set("atmosphere.standard_atmosphere", "midlat_summer")
        params.set("geometry.sensor_altitude_m", 800_000.0)
    elif target_location == "no_atm_space":
        params.set("atmosphere.model", "exo")
        params.set("geometry.sensor_altitude_m", 800_000.0)
    else:  # terrestrial
        params.set("geometry.target_altitude_m", 0.0)
        params.set("atmosphere.model", "simple")
        params.set("atmosphere.standard_atmosphere", "midlat_summer")
        params.set("geometry.sensor_altitude_m", 800_000.0)

    _seed_optics_detector_readout(params, regime)
    params.resolve()
    return params, session


# ---------------------------------------------------------------------------
# Positive matrix: shape × cell end-to-end
# ---------------------------------------------------------------------------


class TestShapeSubPixelIntegration:
    """Every v1 shape runs end-to-end at one representative sub_pixel cell
    per scene-type family (terrestrial LWIR / airborne MWIR / space LWIR)."""

    @pytest.mark.level2
    @pytest.mark.parametrize("shape_name,shape_dims,expected_cls", _SHAPES)
    @pytest.mark.parametrize("cell_id,target_location,regime", _CELLS)
    def test_shape_cell_end_to_end(
        self,
        cell_id: str,
        target_location: str,
        regime: str,
        shape_name: str,
        shape_dims: dict[str, float],
        expected_cls: type,
    ) -> None:
        params, session = _build_params(
            cell_id, target_location, regime, shape_name, shape_dims
        )

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            result = session.run(params)

        # 1. chain completed (session.run returned without raising).
        # 2. Signal in DN is finite and non-negative.
        signal_dn = result.signal_at(ReferenceFrame.DN).value
        assert np.all(np.isfinite(signal_dn)), (
            f"cell {cell_id} / {shape_name}: signal_DN contains non-finite"
        )
        assert np.all(signal_dn >= 0.0), (
            f"cell {cell_id} / {shape_name}: signal_DN has negative values"
        )

        # 3. Descriptor carries the expected concrete shape class.
        target_desc = result.stage_outputs["source"]["target"]
        assert isinstance(target_desc.shape, expected_cls), (
            f"cell {cell_id} / {shape_name}: descriptor.shape is "
            f"{type(target_desc.shape).__name__}, expected "
            f"{expected_cls.__name__}"
        )

        # 4. SNR metric is finite.
        snr = result.metrics.get("snr")
        assert snr is not None, (
            f"cell {cell_id} / {shape_name}: 'snr' missing from metrics"
        )
        assert np.isfinite(float(snr)), (
            f"cell {cell_id} / {shape_name}: SNR not finite (got {snr!r})"
        )


# ---------------------------------------------------------------------------
# Negative path: shape + S9 (at_aperture) is nonsensical — must raise
# ---------------------------------------------------------------------------


class TestShapeAtApertureRejected:
    """shape + target_location='at_aperture' must raise ParameterBoundsError.

    S9 bypasses target geometry entirely (user supplies L at the
    aperture plane).  A shape has nothing to act on there, so the
    inferrer refuses the combination with a Rule-15 error that points
    the user at the two valid resolutions (drop the shape, or switch
    target_location).
    """

    @pytest.mark.level2
    def test_shape_plus_at_aperture_raises(self) -> None:
        wl = _REGIME_GRIDS["LWIR"]
        session = RadiantSession(wavelength_um=wl)
        params = session.default_params()

        params.set("source.target.temperature", 300.0)
        params.set("source.target.emissivity", 0.95)
        params.set("source.target_location", "at_aperture")
        params.set("source.scene_type", "extended")
        params.set("source.target.shape", "sphere")
        params.set("source.target.shape_radius_m", 1.0)
        params.set("atmosphere.model", "simple")
        params.set("geometry.sensor_altitude_m", 800_000.0)

        _seed_optics_detector_readout(params, "LWIR")
        params.resolve()

        with (
            pytest.raises(ParameterBoundsError, match=r"at_aperture"),
            warnings.catch_warnings(),
        ):
            warnings.simplefilter("ignore", UserWarning)
            session.run(params)
