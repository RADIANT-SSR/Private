"""Level 0 tests for spider-vane pupil masking (scenario 1.5).

Truth anchors are geometric properties of the pupil mask (Rule 18):

- The default (no vanes / None spec) must reproduce the historical
  circular/obscured pupil EXACTLY — byte-identical (regression guard for
  all existing optics golden results).
- Struts remove pupil area, so the clear-aperture pixel count strictly
  decreases; more/wider struts remove more.
- A 4-strut spider at 0° offset zeroes the +x, +y, -x, -y axes; those
  pixels must be 0 in the mask.
- Struts spread energy out of the PSF core (diffraction spikes), lowering
  the peak — the physical signature spider vanes are known for.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from radiant.optics.aperture import CircularAperture
from radiant.optics.pupil_amplitude import SpiderVaneSpec, make_pupil_amplitude


class TestNoVaneRegression:
    def test_none_matches_bare_call(self) -> None:
        """vanes=None is byte-identical to the historical two-arg call."""
        a = make_pupil_amplitude(128, 0.0)
        b = make_pupil_amplitude(128, 0.0, None)
        assert np.array_equal(a, b)

    def test_inactive_spec_is_noop(self) -> None:
        """A spec with no struts or zero width changes nothing."""
        base = make_pupil_amplitude(128, 0.3)
        assert np.array_equal(base, make_pupil_amplitude(128, 0.3, SpiderVaneSpec(0, 0.02)))
        assert np.array_equal(base, make_pupil_amplitude(128, 0.3, SpiderVaneSpec(4, 0.0)))
        assert not SpiderVaneSpec(0, 0.02).active
        assert not SpiderVaneSpec(4, 0.0).active


class TestVaneGeometry:
    def test_struts_remove_area(self) -> None:
        clear = make_pupil_amplitude(256, 0.0).sum()
        vaned = make_pupil_amplitude(256, 0.0, SpiderVaneSpec(4, 0.03)).sum()
        assert vaned < clear

    def test_wider_struts_remove_more(self) -> None:
        thin = make_pupil_amplitude(256, 0.0, SpiderVaneSpec(4, 0.02)).sum()
        thick = make_pupil_amplitude(256, 0.0, SpiderVaneSpec(4, 0.06)).sum()
        assert thick < thin

    def test_more_struts_remove_more(self) -> None:
        three = make_pupil_amplitude(256, 0.0, SpiderVaneSpec(3, 0.03)).sum()
        six = make_pupil_amplitude(256, 0.0, SpiderVaneSpec(6, 0.03)).sum()
        assert six < three

    def test_four_strut_cross_zeroes_axes(self) -> None:
        """A 4-strut spider at 0° blanks the +x/+y/-x/-y axes."""
        npix = 128
        mask = make_pupil_amplitude(npix, 0.0, SpiderVaneSpec(4, 0.05))
        c = npix // 2
        # A few pixels out along +x and +y from centre (inside the aperture)
        assert mask[c, c + 10] == 0.0  # +x
        assert mask[c + 10, c] == 0.0  # +y
        assert mask[c, c - 10] == 0.0  # -x
        assert mask[c - 10, c] == 0.0  # -y

    def test_active_property(self) -> None:
        assert SpiderVaneSpec(4, 0.03).active
        assert not SpiderVaneSpec(0, 0.0).active


class TestClearArea:
    def test_spider_area_subtraction_anchor(self) -> None:
        """D=1 m, ε=0, 4 arms × 0.01 m: A = π/4 − 4·0.01·0.5 = 0.7654 m²."""
        ap = CircularAperture(aperture_diameter_m=1.0, n_spiders=4, spider_width_m=0.01)
        expected = math.pi / 4.0 - 4.0 * 0.01 * 0.5
        assert ap.clear_area_m2 == pytest.approx(expected, rel=1e-12)

    def test_no_spiders_matches_circular(self) -> None:
        ap = CircularAperture(aperture_diameter_m=0.5, obscuration_ratio=0.3)
        expected = (math.pi / 4.0) * 0.25 * (1.0 - 0.09)
        assert ap.clear_area_m2 == pytest.approx(expected, rel=1e-12)


class TestPsfEffect:
    def test_vanes_lower_psf_peak(self) -> None:
        """Struts scatter energy into spikes, lowering the normalised peak."""
        from radiant.optics.psf_mono import compute_psf
        from radiant.optics.sampling import compute_sampling

        config = compute_sampling(
            wavelength_m=0.55e-6,
            focal_length_m=1.0,
            aperture_diameter_m=0.2,
            pixel_pitch_m=5e-6,
            pupil_npix=128,
            psf_oversample=8,
        )
        clean = compute_psf(config, 0.0, None, None)
        vaned = compute_psf(config, 0.0, None, SpiderVaneSpec(4, 0.04))
        assert vaned.max() < clean.max()
