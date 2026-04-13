"""Tests for NIIRS dispatcher and IIRS.

See RADIANT_Metrics.md §4.6.
"""

from __future__ import annotations

from radiant.performance.iirs import compute_iirs
from radiant.performance.niirs import compute_niirs


class TestNIIRSDispatcher:
    def test_vis_uses_giqe5(self) -> None:
        result = compute_niirs(1.0, 1.0, 0.7, 0.7, 50.0, band="vis")
        assert result.niirs > 0

    def test_mwir_uses_iirs(self) -> None:
        result = compute_niirs(1.0, 1.0, 0.7, 0.7, 50.0, band="mwir")
        assert result.niirs > 0

    def test_lwir_uses_iirs(self) -> None:
        result = compute_niirs(1.0, 1.0, 0.7, 0.7, 50.0, band="lwir")
        assert result.niirs > 0

    def test_vis_equals_giqe5_directly(self) -> None:
        """Dispatcher result for 'vis' should match direct GIQE-5."""
        from radiant.performance.giqe import compute_giqe5

        r1 = compute_niirs(1.0, 1.0, 0.7, 0.7, 50.0, band="vis")
        r2 = compute_giqe5(1.0, 1.0, 0.7, 0.7, 50.0)
        assert r1.niirs == r2.niirs


class TestIIRS:
    def test_basic(self) -> None:
        result = compute_iirs(1.0, 1.0, 0.7, 0.7, 50.0)
        assert result.niirs > 0

    def test_same_as_giqe5_for_v1(self) -> None:
        """For v1, IIRS uses the same GIQE-5 formula."""
        from radiant.performance.giqe import compute_giqe5

        r_iirs = compute_iirs(1.0, 1.0, 0.7, 0.7, 50.0)
        r_giqe = compute_giqe5(1.0, 1.0, 0.7, 0.7, 50.0)
        assert r_iirs.niirs == r_giqe.niirs
