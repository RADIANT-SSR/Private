"""Level 0 tests for the D*/NEP/NETD noise-spec converters (scenario 6.1).

Truth anchors from the standard radiometric definitions (Rule 18):

- D*: A_d = 1e-4 cm² (100 µm pixel), Δf = 1 Hz, D* = 1e10 Jones →
  NEP = √(1e-4·1)/1e10 = 1e-2/1e10 = 1e-12 W.
- NEP↔σ_e: NEP = σ_e·hc/(η·λ·t_int); round-trip is exact.
- NEP↔NETD: NEP = 1e-12 W, dP/dT = 1e-11 W/K → NETD = 0.1 K.
- Integrating bandwidth: t_int = 0.01 s → Δf = 50 Hz.
"""

from __future__ import annotations

import pytest

from radiant.performance.detectivity import (
    DetectivityError,
    dstar_from_nep,
    nep_from_dstar,
)
from radiant.performance.nep_electrons import (
    NepElectronsError,
    integrating_bandwidth_hz,
    nep_from_noise_electrons,
    noise_electrons_from_nep,
)
from radiant.performance.nep_netd import NepNetdError, nep_from_netd, netd_from_nep


class TestDetectivity:
    def test_nep_anchor(self) -> None:
        assert nep_from_dstar(1e10, 1e-4, 1.0) == pytest.approx(1e-12, rel=1e-12)

    def test_dstar_a3_anchor(self) -> None:
        """Track A3 §9d anchor: D* = √(A_d·Δf)/NEP.

        NEP=1e-14 W, A_d=4.0e-6 cm² (note cm², not m²), Δf=1000 Hz →
        D* = √(4e-6·1000)/1e-14 = √4e-3/1e-14 = 0.06324555/1e-14 =
        6.324555e12 cm·√Hz/W. Pins the area-in-cm² convention (m² would be
        100× off) and the √(A·Δf) form.
        """
        assert dstar_from_nep(1e-14, 4.0e-6, 1000.0) == pytest.approx(6.324555e12, rel=1e-6)

    def test_roundtrip(self) -> None:
        nep = nep_from_dstar(1e10, 1e-4, 100.0)
        assert dstar_from_nep(nep, 1e-4, 100.0) == pytest.approx(1e10, rel=1e-12)

    def test_higher_dstar_lower_nep(self) -> None:
        assert nep_from_dstar(1e11, 1e-4, 1.0) < nep_from_dstar(1e10, 1e-4, 1.0)

    def test_zero_area_raises(self) -> None:
        with pytest.raises(DetectivityError, match="area_cm2"):
            nep_from_dstar(1e10, 0.0, 1.0)


class TestNepElectrons:
    def test_nep_absolute_anchor(self) -> None:
        """Absolute hand anchor for NEP (audit finding B1-2).

        The round-trip/scaling/monotonicity tests below all share the
        ``wavelength_um * 1e-6`` conversion, so a dropped 1e-6 (10⁶ error) or a
        wrong hc cancels and passes. Hand calc: σ_e=100, η=0.7, λ=10 µm,
        t=0.01 s → NEP = 100·hc/(0.7·10e-6·0.01) = 2.8377797959270403e-16 W
        (hc = 1.98644586e-25 J·m, CODATA 2018). rel=1e-6 catches the λ slip.
        """
        assert nep_from_noise_electrons(100.0, 0.7, 10.0, 0.01) == pytest.approx(
            2.8377797959270403e-16, rel=1e-6
        )

    def test_roundtrip(self) -> None:
        nep = nep_from_noise_electrons(100.0, 0.7, 10.0, 0.01)
        assert noise_electrons_from_nep(nep, 0.7, 10.0, 0.01) == pytest.approx(100.0, rel=1e-12)

    def test_nep_scales_with_noise(self) -> None:
        base = nep_from_noise_electrons(100.0, 0.7, 10.0, 0.01)
        assert nep_from_noise_electrons(200.0, 0.7, 10.0, 0.01) == pytest.approx(
            2.0 * base, rel=1e-12
        )

    def test_longer_integration_lower_nep(self) -> None:
        """More integration time ⇒ the same electrons imply less power."""
        assert nep_from_noise_electrons(100.0, 0.7, 10.0, 0.02) < nep_from_noise_electrons(
            100.0, 0.7, 10.0, 0.01
        )

    def test_bandwidth_anchor(self) -> None:
        assert integrating_bandwidth_hz(0.01) == pytest.approx(50.0, rel=1e-12)

    def test_bad_qe_raises(self) -> None:
        with pytest.raises(NepElectronsError, match="qe"):
            nep_from_noise_electrons(100.0, 1.5, 10.0, 0.01)


class TestNepNetd:
    def test_netd_anchor(self) -> None:
        assert netd_from_nep(1e-12, 1e-11) == pytest.approx(0.1, rel=1e-12)

    def test_roundtrip(self) -> None:
        nep = nep_from_netd(0.05, 3e-11)
        assert netd_from_nep(nep, 3e-11) == pytest.approx(0.05, rel=1e-12)

    def test_zero_dpdt_raises(self) -> None:
        with pytest.raises(NepNetdError, match="dp_dt"):
            netd_from_nep(1e-12, 0.0)


class TestChainConsistency:
    def test_dstar_to_netd_via_nep(self) -> None:
        """Datasheet chain: D* → NEP → NETD is self-consistent."""
        nep = nep_from_dstar(2e10, 1e-4, 50.0)  # A_d, Δf
        netd = netd_from_nep(nep, 5e-11)
        # Invert back to D*.
        nep_back = nep_from_netd(netd, 5e-11)
        assert dstar_from_nep(nep_back, 1e-4, 50.0) == pytest.approx(2e10, rel=1e-9)
