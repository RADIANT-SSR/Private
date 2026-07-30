"""The ``SkyBackground`` (matrix B2) assembly arm.

A **pass-through** arm since CU-254: the sky radiance handed in is evaluated
from the sensor over the whole LOS, so it is already the at-aperture
background and the arm applies no transport at all (``τ ≡ 1``,
``L_path ≡ 0``).  It used to be the ``GroundBackground`` arm with the source
plane moved to the target (``L_sky·τ_full_up + L_path_full``), which made the
assembled background depend on where along a fixed ray the target sat.

What is asserted here is that identity (and that ``τ_full_up`` /
``L_path_full`` are genuinely *not* consulted), the source-emission/at-aperture
consistency, and the Rule-17 refusals — plus the zero-drift statement that the
sky keyword changes nothing for the four pre-existing variants.
"""

from __future__ import annotations

import numpy as np
import pytest

from radiant.atmosphere._quantities import AtmosphericQuantities
from radiant.atmosphere.assembly import (
    assemble_background_at_aperture,
    assemble_background_source_emission,
)
from radiant.core.descriptors import (
    AtApertureBackground,
    ColdSpaceBackground,
    GroundBackground,
    SkyBackground,
    UserSpectralBackground,
)
from radiant.core.parameters import ParameterBoundsError
from radiant.core.spectral import SpectralData


@pytest.fixture
def wl() -> np.ndarray:
    return np.linspace(8.0, 13.0, 26)


@pytest.fixture
def atm(wl: np.ndarray) -> AtmosphericQuantities:
    """A bundle shaped like the up/level topology publishes: the observer leg
    in both the ``*_up`` and the ``*_full`` slots."""
    tau = np.linspace(0.30, 0.60, wl.size)
    path = np.linspace(0.8, 1.4, wl.size)
    return AtmosphericQuantities(
        wavelength_um=wl,
        tau_sun=np.full_like(wl, 0.5),
        tau_up=tau,
        tau_full_up=tau.copy(),
        E_TOA=np.full_like(wl, 10.0),
        E_sky_scattered=np.zeros_like(wl),
        E_sky_thermal=np.full_like(wl, 2.0),
        L_path_up=path,
        L_path_full=path.copy(),
    )


class TestSkyArm:
    @pytest.mark.level0
    def test_at_aperture_is_the_sky_itself(
        self, wl: np.ndarray, atm: AtmosphericQuantities
    ) -> None:
        """L_bg,aperture = L_sky [W/m²/sr/µm] — no transport (CU-254)."""
        sky = np.linspace(0.05, 0.25, wl.size)
        got = assemble_background_at_aperture(
            SkyBackground(), atm, None, sky_radiance_at_aperture=sky
        )
        np.testing.assert_array_equal(got, sky)

    @pytest.mark.level0
    def test_observer_leg_fields_are_not_consulted(
        self, wl: np.ndarray, atm: AtmosphericQuantities
    ) -> None:
        """The arm must ignore τ_full_up / L_path_full entirely.

        This is the regression guard for CU-254: the defect was precisely that
        the arm re-propagated an already-composed quantity, so perturbing the
        observer leg while holding the sky fixed must not move the answer.
        """
        sky = np.linspace(0.05, 0.25, wl.size)
        perturbed = AtmosphericQuantities(
            wavelength_um=atm.wavelength_um,
            tau_sun=atm.tau_sun,
            tau_up=atm.tau_up,
            tau_full_up=np.full_like(wl, 0.01),
            E_TOA=atm.E_TOA,
            E_sky_scattered=atm.E_sky_scattered,
            E_sky_thermal=atm.E_sky_thermal,
            L_path_up=atm.L_path_up,
            L_path_full=np.full_like(wl, 99.0),
        )
        base = assemble_background_at_aperture(
            SkyBackground(), atm, None, sky_radiance_at_aperture=sky
        )
        moved = assemble_background_at_aperture(
            SkyBackground(), perturbed, None, sky_radiance_at_aperture=sky
        )
        np.testing.assert_array_equal(base, moved)  # type: ignore[arg-type]

    @pytest.mark.level0
    def test_source_emission_is_the_sky_itself(
        self, wl: np.ndarray, atm: AtmosphericQuantities
    ) -> None:
        """Gap 91: a pass-through arm's source emission is its at-aperture value."""
        sky = np.linspace(0.05, 0.25, wl.size)
        got = assemble_background_source_emission(
            SkyBackground(), atm, None, sky_radiance_at_aperture=sky
        )
        np.testing.assert_array_equal(got, sky)

    @pytest.mark.level0
    def test_gap91_round_trip_holds_exactly(
        self, wl: np.ndarray, atm: AtmosphericQuantities
    ) -> None:
        """at_aperture == source_emission, the pass-through-variant identity."""
        sky = np.linspace(0.05, 0.25, wl.size)
        ap = assemble_background_at_aperture(
            SkyBackground(), atm, None, sky_radiance_at_aperture=sky
        )
        src = assemble_background_source_emission(
            SkyBackground(), atm, None, sky_radiance_at_aperture=sky
        )
        np.testing.assert_array_equal(ap, src)

    @pytest.mark.level0
    def test_zero_sky_is_a_zero_background(
        self, wl: np.ndarray, atm: AtmosphericQuantities
    ) -> None:
        """The LEO→GEO vacuum limit: no medium anywhere, so no background."""
        got = assemble_background_at_aperture(
            SkyBackground(), atm, None, sky_radiance_at_aperture=np.zeros_like(wl)
        )
        np.testing.assert_array_equal(got, np.zeros_like(wl))


class TestFailureModes:
    @pytest.mark.level0
    def test_missing_sky_raises_rather_than_defaulting_to_zero(
        self, atm: AtmosphericQuantities
    ) -> None:
        """Rule 17: a silently-zero background inflates SNR."""
        with pytest.raises(ParameterBoundsError) as exc:
            assemble_background_at_aperture(SkyBackground(), atm, None)
        message = str(exc.value)
        assert "sky_radiance_at_aperture is None" in message
        assert "inflate SNR" in message

    @pytest.mark.level0
    def test_off_grid_sky_raises(self, atm: AtmosphericQuantities) -> None:
        with pytest.raises(ParameterBoundsError, match="does not match"):
            assemble_background_at_aperture(
                SkyBackground(), atm, None, sky_radiance_at_aperture=np.zeros(3)
            )

    @pytest.mark.level0
    def test_negative_sky_raises(self, wl: np.ndarray, atm: AtmosphericQuantities) -> None:
        bad = np.zeros_like(wl)
        bad[3] = -1e-9
        with pytest.raises(ParameterBoundsError, match="negative"):
            assemble_background_at_aperture(
                SkyBackground(), atm, None, sky_radiance_at_aperture=bad
            )

    @pytest.mark.level0
    def test_source_emission_arm_shares_the_refusal(self, atm: AtmosphericQuantities) -> None:
        with pytest.raises(ParameterBoundsError, match="sky_radiance_at_aperture is None"):
            assemble_background_source_emission(SkyBackground(), atm, None)


class TestZeroDriftForOtherVariants:
    @pytest.mark.level0
    def test_new_keyword_is_inert_for_the_pre_existing_variants(
        self, wl: np.ndarray, atm: AtmosphericQuantities
    ) -> None:
        """Passing a sky array alongside a non-sky descriptor changes nothing."""
        sky = np.linspace(0.05, 0.25, wl.size)
        epsilon_g = SpectralData(
            name="bg.eps", wavelength_um=wl, values=np.full_like(wl, 0.95), unit="", source="t"
        )
        l_bg = SpectralData(
            name="bg.L",
            wavelength_um=wl,
            values=np.full_like(wl, 3.0),
            unit="W/m^2/sr/um",
            source="t",
        )
        for bg in (
            AtApertureBackground(L_bg_aperture=None),
            ColdSpaceBackground(),
            UserSpectralBackground(L_bg=l_bg),
        ):
            without = assemble_background_at_aperture(bg, atm, None)
            with_sky = assemble_background_at_aperture(bg, atm, None, sky_radiance_at_aperture=sky)
            np.testing.assert_array_equal(without, with_sky)  # type: ignore[arg-type]
        assert GroundBackground(epsilon_g=epsilon_g, T_g=290.0) is not None

    @pytest.mark.level0
    def test_none_background_still_returns_none(self, atm: AtmosphericQuantities) -> None:
        assert assemble_background_at_aperture(None, atm, None) is None
        assert assemble_background_source_emission(None, atm, None) is None
