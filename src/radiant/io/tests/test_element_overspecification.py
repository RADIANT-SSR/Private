"""CU-365: the element parser refuses what it used to ignore.

An ``emissivity:`` key on any element, or a transfer key foreign to the row's
mode (``transmittance`` on a REFLECTIVE row, ``reflectance`` on a REFRACTIVE
one), was parsed past, retained in the document and round-tripped into saved
YAML while Kirchhoff derivation governed. Each case now raises an actionable
``ElementConfigError``; a clean entry still parses. Both refusal tests failed
on the pre-fix code.
"""

from __future__ import annotations

import numpy as np
import pytest

from radiant.io.element_config import ElementConfigError, parse_element_entries


def _mirror(**extra: object) -> dict[str, object]:
    return {"name": "m1", "transfer_mode": "REFLECTIVE", "reflectance": 0.98, **extra}


def _lens(**extra: object) -> dict[str, object]:
    return {"name": "l1", "transfer_mode": "REFRACTIVE", "transmittance": 0.95, **extra}


class TestEmissivityIsRefused:
    def test_on_a_mirror(self) -> None:
        with pytest.raises(ElementConfigError, match="not an element input") as info:
            parse_element_entries([_mirror(emissivity=0.05)])
        assert "1 − R" in str(info.value)

    def test_on_a_lens(self) -> None:
        with pytest.raises(ElementConfigError, match="not an element input"):
            parse_element_entries([_lens(emissivity=0.02)])


class TestForeignTransferKeysAreRefused:
    def test_transmittance_on_a_reflective_row(self) -> None:
        with pytest.raises(
            ElementConfigError, match="do not apply to transfer_mode = 'REFLECTIVE'"
        ):
            parse_element_entries([_mirror(transmittance=0.0)])

    def test_reflectance_on_a_refractive_row(self) -> None:
        with pytest.raises(
            ElementConfigError, match="do not apply to transfer_mode = 'REFRACTIVE'"
        ):
            parse_element_entries([_lens(reflectance=0.01)])


class TestCleanEntriesStillParse:
    def test_mirror_and_lens(self) -> None:
        elements = parse_element_entries(
            [_mirror(), _lens()], wavelength_um=np.linspace(3.0, 5.0, 5)
        )
        assert [e.name for e in elements] == ["m1", "l1"]
