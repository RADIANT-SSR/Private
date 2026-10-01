"""The silently-zero near-field advisory (CU-380).

Level 0: the predicate's truth table, independent of the chain. Then the
end-to-end assertion that the shipped MWIR example — which carried this defect
through v0.2.0 and v0.3.0 — now says so.
"""

from __future__ import annotations

import numpy as np
import pytest

from radiant.core.spectral import SpectralData
from radiant.optics.element import ElementKind, OpticalElement
from radiant.optics.nearfield_advisory import (
    THERMAL_BAND_FLOOR_UM,
    nearfield_is_silently_zero,
    nearfield_zero_message,
)

_WL = np.array([3.5, 4.0, 5.0])


def _flat(value: float, name: str) -> SpectralData:
    return SpectralData(
        name=name,
        wavelength_um=_WL.copy(),
        values=np.full_like(_WL, value),
        unit="",
        source="test fixture",
    )


def _element(name: str, temperature_K: float) -> OpticalElement:
    """A mirror at *temperature_K*; R = 0.9 so eps = 1 - R = 0.1 when warm."""
    return OpticalElement(
        name=name,
        kind=ElementKind.MIRROR,
        temperature_K=temperature_K,
        transmittance=_flat(0.0, f"{name}.tau"),
        reflectance=_flat(0.9, f"{name}.rho"),
    )


def _call(**overrides: object) -> bool:
    kwargs: dict[str, object] = {
        "nearfield_enabled": True,
        "stray_includes_thermal": False,
        "elements": (_element("lumped", 0.0),),
        "band_max_um": 5.0,
    }
    kwargs.update(overrides)
    return nearfield_is_silently_zero(**kwargs)  # type: ignore[arg-type]


class TestPredicate:
    def test_fires_on_the_shipped_defect(self) -> None:
        """Thermal band, term enabled, synthesized 0 K lump — the CU-380 case."""
        assert _call() is True

    def test_silent_when_term_is_deliberately_off(self) -> None:
        assert _call(nearfield_enabled=False) is False

    def test_silent_when_stray_accounts_for_thermal(self) -> None:
        """Warm optics is then in the stray term; a zero near-field is correct."""
        assert _call(stray_includes_thermal=True) is False

    def test_silent_when_a_surface_can_emit(self) -> None:
        assert _call(elements=(_element("primary", 290.0),)) is False

    def test_fires_when_only_some_rows_lack_temperature(self) -> None:
        """A train of all-cold rows still warns, whatever mode produced it."""
        assert _call(elements=(_element("a", 0.0), _element("b", 0.0))) is True

    def test_silent_when_any_one_row_is_warm(self) -> None:
        """One emitting surface is enough — the term is no longer structurally zero."""
        assert _call(elements=(_element("a", 0.0), _element("b", 290.0))) is False

    @pytest.mark.parametrize("band_max_um", [0.7, 1.0, 2.0, THERMAL_BAND_FLOOR_UM])
    def test_silent_below_the_thermal_floor(self, band_max_um: float) -> None:
        """A VIS/NIR band's zero warm-optics term is the right answer."""
        assert _call(band_max_um=band_max_um) is False

    @pytest.mark.parametrize("band_max_um", [2.51, 5.0, 12.0])
    def test_fires_above_the_thermal_floor(self, band_max_um: float) -> None:
        assert _call(band_max_um=band_max_um) is True

    def test_mode_agnostic_by_construction(self) -> None:
        """The predicate takes no transmission mode — it asks about emission."""
        import inspect

        assert "mode" not in inspect.signature(nearfield_is_silently_zero).parameters


class TestMessage:
    def test_names_cause_consequence_and_both_remedies(self) -> None:
        msg = nearfield_zero_message(band_max_um=5.0, n_elements=1)
        assert "nearfield_enabled" in msg
        assert "0 K" in msg
        assert "optical_elements" in msg  # remedy 1
        assert "nearfield_enabled = 0" in msg  # remedy 2
        assert "5 um" in msg  # the band that triggered it

    def test_carries_units_on_every_number(self) -> None:
        msg = nearfield_zero_message(band_max_um=12.0, n_elements=3)
        assert "12 um" in msg
        assert "3 element(s)" in msg
