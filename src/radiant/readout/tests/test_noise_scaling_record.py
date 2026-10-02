"""The per-term scaling record (Gap 133).

The load-bearing test here is the reconciliation: for every multiplicative
term, ``reported_factor × raw`` must equal what ``_scale_noise_term`` actually
produces. A report of a correlation class that has drifted from the code is
worse than no report, so the report is derived from the same helpers and then
pinned against the real dispatch.
"""

from __future__ import annotations

import math

import pytest

from radiant.core.noise_budget import ALL_NOISE_TERMS, SPATIAL_TERMS
from radiant.readout.coadds import CoaddMode
from radiant.readout.noise_scaling_record import (
    CORRELATION_CLASSES,
    describe_noise_scaling,
)
from radiant.readout.stage import _scale_noise_term

_GEOM = {
    "n_tdi": 4,
    "tdi_digital": False,
    "mx_on": 2,
    "my_on": 2,
    "px_off": 2,
    "py_off": 1,
    "n_coadds": 8,
    "coadd_mode": CoaddMode.SUM,
}


def _describe(term: str, **over: object):  # type: ignore[no-untyped-def]
    kw = dict(_GEOM)
    kw.update(over)
    return describe_noise_scaling(term, **kw)  # type: ignore[arg-type]


class TestItReconcilesWithTheRealDispatch:
    """The anti-drift guarantee."""

    @pytest.mark.level0
    @pytest.mark.parametrize(
        "term", sorted(ALL_NOISE_TERMS - {"flicker_1f", "counting_quantization", "packet_reset"})
    )
    def test_reported_factors_reproduce_the_applied_scaling(self, term: str) -> None:
        raw = 37.0
        rec = _describe(term)
        applied = _scale_noise_term(raw_value=raw, term_name=term, **_GEOM)  # type: ignore[arg-type]
        product = raw
        for factor in (rec.tdi_factor, rec.onchip_factor, rec.offchip_factor, rec.coadd_factor):
            if factor is not None:
                product *= factor
        assert product == pytest.approx(applied, rel=1e-12), term

    @pytest.mark.level0
    @pytest.mark.parametrize("digital", [False, True])
    def test_reconciliation_holds_under_both_tdi_modes(self, digital: bool) -> None:
        raw = 11.0
        for term in ("signal_shot", "prnu", "read_noise", "clutter"):
            rec = _describe(term, tdi_digital=digital)
            applied = _scale_noise_term(
                raw_value=raw, term_name=term, **{**_GEOM, "tdi_digital": digital}
            )  # type: ignore[arg-type]
            product = raw
            for f in (rec.tdi_factor, rec.onchip_factor, rec.offchip_factor, rec.coadd_factor):
                if f is not None:
                    product *= f
            assert product == pytest.approx(applied, rel=1e-12), (term, digital)

    @pytest.mark.level0
    @pytest.mark.parametrize("mode", list(CoaddMode))
    def test_reconciliation_holds_for_every_coadd_mode(self, mode: CoaddMode) -> None:
        raw = 5.0
        rec = _describe("dark_shot", coadd_mode=mode)
        applied = _scale_noise_term(
            raw_value=raw, term_name="dark_shot", **{**_GEOM, "coadd_mode": mode}
        )  # type: ignore[arg-type]
        product = raw * rec.tdi_factor * rec.onchip_factor * rec.offchip_factor * rec.coadd_factor
        assert product == pytest.approx(applied, rel=1e-12)


class TestTheCountingTerms:
    """Gap-117 terms bypass the generic dispatch, so they get their own oracle.

    Their first version in this module was classified read_like, which reports a
    TDI and an on-chip factor. The stage applies neither — n_counts already
    carries both — so the report would have double-counted. The reconciliation
    test caught it, which is the argument for having one.
    """

    @pytest.mark.level0
    @pytest.mark.parametrize("term", ["counting_quantization", "packet_reset"])
    def test_no_tdi_or_onchip_factor_is_reported(self, term: str) -> None:
        rec = _describe(term)
        assert rec.tdi_factor is None
        assert rec.onchip_factor is None
        assert rec.correlation_class == "post_conversion"

    @pytest.mark.level0
    @pytest.mark.parametrize("term", ["counting_quantization", "packet_reset"])
    def test_it_reconciles_against_the_stage_s_actual_two_step(self, term: str) -> None:
        """The stage applies off-chip binning then the co-add, and nothing else."""
        from radiant.readout.binning_offchip import offchip_scale_read_noise
        from radiant.readout.coadds import coadd_scale_temporal_noise

        raw = 23.0
        expected = coadd_scale_temporal_noise(
            offchip_scale_read_noise(raw, _GEOM["px_off"], _GEOM["py_off"]),  # type: ignore[arg-type]
            _GEOM["n_coadds"],  # type: ignore[arg-type]
            _GEOM["coadd_mode"],  # type: ignore[arg-type]
        )
        rec = _describe(term)
        assert raw * rec.offchip_factor * rec.coadd_factor == pytest.approx(expected, rel=1e-12)

    @pytest.mark.level0
    @pytest.mark.parametrize("term", ["counting_quantization", "packet_reset"])
    def test_the_note_says_why_rather_than_leaving_a_blank(self, term: str) -> None:
        assert "double-count" in _describe(term).note


class TestCorrelationClasses:
    @pytest.mark.level0
    def test_every_term_gets_a_known_class(self) -> None:
        for term in ALL_NOISE_TERMS:
            assert _describe(term).correlation_class in CORRELATION_CLASSES

    @pytest.mark.level0
    def test_spatial_terms_are_classified_spatial(self) -> None:
        for term in SPATIAL_TERMS:
            assert _describe(term).correlation_class == "spatial"

    @pytest.mark.level0
    def test_shot_terms_scale_as_sqrt_on_every_axis(self) -> None:
        rec = _describe("signal_shot")
        assert rec.tdi_factor == pytest.approx(math.sqrt(4), rel=1e-12)
        assert rec.coadd_factor == pytest.approx(math.sqrt(8), rel=1e-12)

    @pytest.mark.level0
    def test_fpn_scales_as_k_on_coadd_not_sqrt_k(self) -> None:
        """The distinction CU-381 turned on."""
        assert _describe("prnu").coadd_factor == pytest.approx(8.0, rel=1e-12)
        assert _describe("signal_shot").coadd_factor == pytest.approx(math.sqrt(8), rel=1e-12)

    @pytest.mark.level0
    def test_read_like_terms_are_not_multiplied_by_tdi_on_analog(self) -> None:
        assert _describe("read_noise", tdi_digital=False).tdi_factor == pytest.approx(1.0)

    @pytest.mark.level0
    def test_clutter_is_scene_correlated_in_both_tdi_modes(self) -> None:
        for digital in (False, True):
            rec = _describe("clutter", tdi_digital=digital)
            assert rec.tdi_factor == pytest.approx(4.0, rel=1e-12)
            assert "scene-correlated" in rec.note


class TestTheFlickerException:
    """The case the gap exists for: a term with no co-add factor at all."""

    @pytest.mark.level0
    def test_flicker_reports_no_coadd_factor(self) -> None:
        rec = _describe("flicker_1f")
        assert rec.coadd_factor is None
        assert rec.correlation_class == "transfer_function"

    @pytest.mark.level0
    def test_none_is_not_the_same_as_one(self) -> None:
        """A factor of 1.0 would claim 'nothing happened'; None says 'not a factor'."""
        assert _describe("flicker_1f").coadd_factor is not 1.0  # noqa: F632

    @pytest.mark.level0
    def test_the_note_explains_why_rather_than_inventing_an_exponent(self) -> None:
        note = _describe("flicker_1f").note
        assert "Dirichlet" in note
        assert "no single exponent" in note

    @pytest.mark.level0
    def test_flicker_still_reports_its_tdi_and_binning_factors(self) -> None:
        """Those axes ARE factors — only the co-add axis is not."""
        rec = _describe("flicker_1f")
        assert rec.tdi_factor == pytest.approx(math.sqrt(4), rel=1e-12)
        assert rec.onchip_factor is not None
        assert rec.offchip_factor is not None

    @pytest.mark.level0
    def test_flicker_tdi_is_n_under_digital_and_sqrt_n_under_analog(self) -> None:
        """Different physical pixels vs the same pixel re-read."""
        assert _describe("flicker_1f", tdi_digital=False).tdi_factor == pytest.approx(2.0)
        assert _describe("flicker_1f", tdi_digital=True).tdi_factor == pytest.approx(4.0)


class TestRendering:
    @pytest.mark.level0
    def test_a_none_factor_renders_as_a_dash_not_a_number(self) -> None:
        assert "—" in str(_describe("flicker_1f"))

    @pytest.mark.level0
    def test_the_line_names_the_term_and_its_class(self) -> None:
        line = str(_describe("prnu"))
        assert "prnu" in line and "spatial" in line
