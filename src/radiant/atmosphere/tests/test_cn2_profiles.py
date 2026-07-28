"""Level-0 tests for the Cn² profile family selector (Gap 110)."""

from __future__ import annotations

import numpy as np
import pytest

from radiant.atmosphere.cn2_hufnagel_valley import HufnagelValleyCn2
from radiant.atmosphere.cn2_profiles import (
    CN2_PROFILE_DIRECT,
    CN2_PROFILE_NAMES,
    Cn2Profile,
    resolve_cn2_profile,
)
from radiant.atmosphere.cn2_tabulated import TabulatedCn2Profile
from radiant.atmosphere.errors import AtmosphereValidationError


def _table() -> TabulatedCn2Profile:
    return TabulatedCn2Profile(altitude_m=np.array([0.0, 1000.0]), cn2_m23=np.array([1e-14, 1e-16]))


class TestSelector:
    @pytest.mark.level0
    def test_direct_returns_no_profile(self) -> None:
        assert (
            resolve_cn2_profile(
                CN2_PROFILE_DIRECT, hv_wind_rms_m_s=21.0, hv_ground_strength_m23=1.7e-14
            )
            is None
        )

    @pytest.mark.level0
    def test_hufnagel_valley_carries_the_parameters(self) -> None:
        profile = resolve_cn2_profile(
            "hufnagel_valley", hv_wind_rms_m_s=30.0, hv_ground_strength_m23=5.0e-14
        )
        assert isinstance(profile, HufnagelValleyCn2)
        assert profile.wind_rms_m_s == 30.0
        assert profile.ground_strength_m23 == 5.0e-14

    @pytest.mark.level0
    def test_tabulated_passes_the_injected_profile_through(self) -> None:
        table = _table()
        assert (
            resolve_cn2_profile(
                "tabulated",
                hv_wind_rms_m_s=21.0,
                hv_ground_strength_m23=1.7e-14,
                tabulated=table,
            )
            is table
        )

    @pytest.mark.level0
    def test_tabulated_without_injection_is_actionable(self) -> None:
        with pytest.raises(AtmosphereValidationError, match="cn2_tabulated_file"):
            resolve_cn2_profile("tabulated", hv_wind_rms_m_s=21.0, hv_ground_strength_m23=1.7e-14)

    @pytest.mark.level0
    def test_unknown_selector_lists_the_supported_values(self) -> None:
        with pytest.raises(AtmosphereValidationError, match="hufnagel_valley"):
            resolve_cn2_profile("slc_day", hv_wind_rms_m_s=21.0, hv_ground_strength_m23=1.7e-14)

    @pytest.mark.level0
    def test_both_implementations_satisfy_the_protocol(self) -> None:
        assert isinstance(HufnagelValleyCn2(), Cn2Profile)
        assert isinstance(_table(), Cn2Profile)

    @pytest.mark.level0
    def test_selector_names_match_the_schema_enum(self) -> None:
        from radiant.atmosphere._schema import CN2_PROFILE

        assert CN2_PROFILE.enum_values == CN2_PROFILE_NAMES
        assert CN2_PROFILE.default == CN2_PROFILE_DIRECT
