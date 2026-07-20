"""Tests for radiant.atmosphere.omega0_eff (Gap 38 ω₀_eff lookup).

Category C validation:

Truth anchors (the table itself is the anchor — derived by inverting the
diffuse-sky closed form against the real MODTRAN 6 flux tables, and
independently re-derived from the staged files by
``tests/integration/test_modtran_real_runs.py::
test_omega0_eff_derivation_matches_pinned_table``):

1. Band values match the pinned integration table exactly.
2. Physical ordering: urban (soot) darkest in VIS/NIR; ω₀ falls
   VIS → SWIR for every aerosol.
3. Piecewise structure: constant within bands, edge-extended outside.
"""

from __future__ import annotations

import numpy as np
import pytest

from radiant.atmosphere.errors import AtmosphereValidationError
from radiant.atmosphere.omega0_eff import OMEGA0_EFF_TABLE, omega0_eff


class TestTableValues:
    @pytest.mark.level0
    def test_matches_integration_pinned_table(self) -> None:
        """The library table and the independently pinned integration
        reference (test_modtran_real_runs.OMEGA0_EFF) must stay equal —
        the integration side carries the re-derivation guard against the
        staged MODTRAN files, so equality chains this module to the
        delivered flux data."""
        from tests.integration.test_modtran_real_runs import OMEGA0_EFF

        for aerosol, bands in OMEGA0_EFF.items():
            vis, nir, swir = OMEGA0_EFF_TABLE[aerosol]
            assert vis == pytest.approx(bands["VIS"], abs=1e-12)
            assert nir == pytest.approx(bands["NIR"], abs=1e-12)
            assert swir == pytest.approx(bands["SWIR"], abs=1e-12)

    @pytest.mark.level0
    def test_physical_ordering(self) -> None:
        for i in (0, 1):  # VIS, NIR
            assert OMEGA0_EFF_TABLE["urban"][i] < OMEGA0_EFF_TABLE["rural"][i]
            assert OMEGA0_EFF_TABLE["urban"][i] < OMEGA0_EFF_TABLE["maritime"][i]
        for aerosol in OMEGA0_EFF_TABLE:
            assert OMEGA0_EFF_TABLE[aerosol][2] < OMEGA0_EFF_TABLE[aerosol][0]


class TestLookup:
    @pytest.mark.level0
    def test_band_selection_and_edge_extension(self) -> None:
        """λ = 0.30 (edge-ext), 0.55 (VIS), 1.0 (NIR), 2.0 (SWIR),
        4.0 µm (edge-ext) map to the expected band values."""
        lam = np.array([0.30, 0.55, 1.0, 2.0, 4.0])
        vis, nir, swir = OMEGA0_EFF_TABLE["rural"]
        np.testing.assert_allclose(
            omega0_eff(lam, "rural"), [vis, vis, nir, swir, swir], rtol=0.0, atol=0.0
        )

    @pytest.mark.level0
    def test_band_edges(self) -> None:
        """Exactly at an edge the longer-wavelength band applies
        (half-open [lo, hi) bands)."""
        lam = np.array([0.7, 1.4])
        vis, nir, swir = OMEGA0_EFF_TABLE["maritime"]
        np.testing.assert_allclose(omega0_eff(lam, "maritime"), [nir, swir])

    @pytest.mark.level0
    def test_bounded_zero_one(self) -> None:
        lam = np.linspace(0.2, 15.0, 500)
        for aerosol in OMEGA0_EFF_TABLE:
            w = omega0_eff(lam, aerosol)
            assert np.all((w > 0.0) & (w < 1.0))

    @pytest.mark.level0
    def test_unknown_aerosol_actionable_error(self) -> None:
        with pytest.raises(AtmosphereValidationError, match="tropospheric"):
            omega0_eff(np.array([0.55]), "tropospheric")
