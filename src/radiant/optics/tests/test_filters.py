"""Tests for radiant.optics.filters.

Category C validation for filter shape functions:
- In-band equals peak_transmission
- Out-of-band equals oob_rejection
- Transition regions are monotonic
- Kirchhoff compliance of filter elements
"""

from __future__ import annotations

import numpy as np
import pytest

from radiant.optics.filters import (
    FilterSpec,
    FilterType,
    filter_to_element,
    make_filter_transmission,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

WL = np.linspace(1.0, 10.0, 1000)


# ---------------------------------------------------------------------------
# Bandpass
# ---------------------------------------------------------------------------


class TestBandpass:
    """Bandpass filter shape verification."""

    @pytest.mark.level0
    def test_center_equals_peak(self) -> None:
        """At band center, transmission == peak_transmission."""
        spec = FilterSpec(
            filter_type=FilterType.BANDPASS,
            center_um=4.0,
            fwhm_um=1.0,
            peak_transmission=0.95,
            oob_rejection=1e-4,
            name="bp",
        )
        sd = make_filter_transmission(spec, WL)
        # Find index closest to center
        idx = np.argmin(np.abs(WL - 4.0))
        assert sd.values[idx] == pytest.approx(0.95, abs=1e-6)

    @pytest.mark.level0
    def test_oob_far_from_band(self) -> None:
        """Far out-of-band wavelengths == oob_rejection."""
        spec = FilterSpec(
            filter_type=FilterType.BANDPASS,
            center_um=4.0,
            fwhm_um=1.0,
            peak_transmission=0.95,
            oob_rejection=1e-4,
            name="bp",
        )
        sd = make_filter_transmission(spec, WL)
        # Well outside band: 1.0 um and 9.0 um
        idx_low = np.argmin(np.abs(WL - 1.5))
        idx_high = np.argmin(np.abs(WL - 8.0))
        assert sd.values[idx_low] == pytest.approx(1e-4, abs=1e-6)
        assert sd.values[idx_high] == pytest.approx(1e-4, abs=1e-6)

    @pytest.mark.level0
    def test_in_band_flat(self) -> None:
        """Well inside the band, all values near peak."""
        spec = FilterSpec(
            filter_type=FilterType.BANDPASS,
            center_um=5.0,
            fwhm_um=2.0,
            peak_transmission=0.90,
            oob_rejection=1e-4,
            name="bp",
        )
        sd = make_filter_transmission(spec, WL)
        # Points clearly inside band (4.2 to 5.8 um, well within 4.0-6.0)
        in_band = (WL >= 4.2) & (WL <= 5.8)
        np.testing.assert_allclose(
            sd.values[in_band], 0.90, atol=1e-4,
        )


# ---------------------------------------------------------------------------
# Longpass
# ---------------------------------------------------------------------------


class TestLongpass:
    """Longpass filter shape verification."""

    @pytest.mark.level0
    def test_above_cuton_equals_peak(self) -> None:
        spec = FilterSpec(
            filter_type=FilterType.LONGPASS,
            cuton_um=3.5,
            peak_transmission=0.95,
            oob_rejection=1e-4,
            name="lp",
        )
        sd = make_filter_transmission(spec, WL)
        # Well above cuton
        idx = np.argmin(np.abs(WL - 7.0))
        assert sd.values[idx] == pytest.approx(0.95, abs=1e-6)

    @pytest.mark.level0
    def test_below_cuton_equals_oob(self) -> None:
        spec = FilterSpec(
            filter_type=FilterType.LONGPASS,
            cuton_um=3.5,
            peak_transmission=0.95,
            oob_rejection=1e-4,
            name="lp",
        )
        sd = make_filter_transmission(spec, WL)
        idx = np.argmin(np.abs(WL - 1.5))
        assert sd.values[idx] == pytest.approx(1e-4, abs=1e-6)

    @pytest.mark.level0
    def test_transition_monotonic(self) -> None:
        """Transition region should be monotonically increasing."""
        spec = FilterSpec(
            filter_type=FilterType.LONGPASS,
            cuton_um=5.0,
            peak_transmission=0.95,
            oob_rejection=1e-4,
            name="lp",
        )
        sd = make_filter_transmission(spec, WL)
        # Transition around 5.0 um +/- 0.25 um (edge_width = 0.5)
        mask = (WL >= 4.7) & (WL <= 5.3)
        transition = sd.values[mask]
        assert np.all(np.diff(transition) >= 0)


# ---------------------------------------------------------------------------
# Shortpass
# ---------------------------------------------------------------------------


class TestShortpass:
    """Shortpass filter shape verification."""

    @pytest.mark.level0
    def test_below_cutoff_equals_peak(self) -> None:
        spec = FilterSpec(
            filter_type=FilterType.SHORTPASS,
            cutoff_um=5.0,
            peak_transmission=0.95,
            oob_rejection=1e-4,
            name="sp",
        )
        sd = make_filter_transmission(spec, WL)
        idx = np.argmin(np.abs(WL - 2.0))
        assert sd.values[idx] == pytest.approx(0.95, abs=1e-6)

    @pytest.mark.level0
    def test_above_cutoff_equals_oob(self) -> None:
        spec = FilterSpec(
            filter_type=FilterType.SHORTPASS,
            cutoff_um=5.0,
            peak_transmission=0.95,
            oob_rejection=1e-4,
            name="sp",
        )
        sd = make_filter_transmission(spec, WL)
        idx = np.argmin(np.abs(WL - 8.0))
        assert sd.values[idx] == pytest.approx(1e-4, abs=1e-6)


# ---------------------------------------------------------------------------
# Notch
# ---------------------------------------------------------------------------


class TestNotch:
    """Notch filter shape verification."""

    @pytest.mark.level0
    def test_center_equals_min(self) -> None:
        """At notch center, transmission == min_transmission."""
        spec = FilterSpec(
            filter_type=FilterType.NOTCH,
            center_um=4.5,
            fwhm_um=1.0,
            peak_transmission=0.95,
            min_transmission=0.01,
            name="notch",
        )
        sd = make_filter_transmission(spec, WL)
        idx = np.argmin(np.abs(WL - 4.5))
        assert sd.values[idx] == pytest.approx(0.01, abs=1e-4)

    @pytest.mark.level0
    def test_outside_notch_equals_peak(self) -> None:
        spec = FilterSpec(
            filter_type=FilterType.NOTCH,
            center_um=4.5,
            fwhm_um=1.0,
            peak_transmission=0.95,
            min_transmission=0.01,
            name="notch",
        )
        sd = make_filter_transmission(spec, WL)
        # Well outside
        idx_low = np.argmin(np.abs(WL - 2.0))
        idx_high = np.argmin(np.abs(WL - 8.0))
        assert sd.values[idx_low] == pytest.approx(0.95, abs=1e-6)
        assert sd.values[idx_high] == pytest.approx(0.95, abs=1e-6)


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


class TestFilterSpecValidation:
    """Input validation for FilterSpec."""

    @pytest.mark.level1
    def test_bandpass_missing_center(self) -> None:
        with pytest.raises(ValueError, match="center_um"):
            FilterSpec(filter_type=FilterType.BANDPASS, fwhm_um=1.0)

    @pytest.mark.level1
    def test_bandpass_missing_fwhm(self) -> None:
        with pytest.raises(ValueError, match="fwhm_um"):
            FilterSpec(filter_type=FilterType.BANDPASS, center_um=4.0)

    @pytest.mark.level1
    def test_longpass_missing_cuton(self) -> None:
        with pytest.raises(ValueError, match="cuton_um"):
            FilterSpec(filter_type=FilterType.LONGPASS)

    @pytest.mark.level1
    def test_shortpass_missing_cutoff(self) -> None:
        with pytest.raises(ValueError, match="cutoff_um"):
            FilterSpec(filter_type=FilterType.SHORTPASS)

    @pytest.mark.level1
    def test_notch_missing_min(self) -> None:
        with pytest.raises(ValueError, match="min_transmission"):
            FilterSpec(
                filter_type=FilterType.NOTCH, center_um=4.0, fwhm_um=1.0,
            )

    @pytest.mark.level1
    def test_tabulated_missing_file(self) -> None:
        with pytest.raises(ValueError, match="transmission_file"):
            FilterSpec(filter_type=FilterType.TABULATED)

    @pytest.mark.level1
    def test_peak_out_of_range(self) -> None:
        with pytest.raises(ValueError, match="peak_transmission"):
            FilterSpec(
                filter_type=FilterType.BANDPASS,
                center_um=4.0,
                fwhm_um=1.0,
                peak_transmission=1.5,
            )


# ---------------------------------------------------------------------------
# Filter to element
# ---------------------------------------------------------------------------


class TestFilterToElement:
    """Verify filter_to_element produces valid OpticalElement."""

    @pytest.mark.level1
    def test_filter_element_eps_zero(self) -> None:
        """Filter element is simple refractive: eps = 0."""
        spec = FilterSpec(
            filter_type=FilterType.BANDPASS,
            center_um=4.0,
            fwhm_um=1.0,
            peak_transmission=0.90,
            oob_rejection=1e-4,
            name="test_bp",
        )
        elem = filter_to_element(spec, WL, 290.0, 0.05, 0.3)
        np.testing.assert_allclose(elem.emissivity.values, 0.0, atol=1e-12)

    @pytest.mark.level1
    def test_element_kind_is_filter(self) -> None:
        from radiant.optics.element import ElementKind

        spec = FilterSpec(
            filter_type=FilterType.LONGPASS,
            cuton_um=3.5,
            name="test_lp",
        )
        elem = filter_to_element(spec, WL, 290.0, 0.05, 0.3)
        assert elem.kind == ElementKind.FILTER
