"""The substrate absorption figure (Gap 142 §9).

The log axis is the reason this figure exists rather than being a line on the coating
plot: alpha spans orders of magnitude inside a transparency window, so on a linear axis
the transparent region — which is most of the useful band — collapses onto zero.
"""

from __future__ import annotations

import matplotlib
import numpy as np
import pytest

matplotlib.use("Agg")

from radiant.api.errors import ApiValidationError  # noqa: E402
from radiant.api.substrate_absorption import plot_substrate_absorption  # noqa: E402
from radiant.data.substrate import SubstrateLibrary  # noqa: E402


class TestTheLogAxis:
    @pytest.mark.level1
    def test_alpha_is_logarithmic_by_default(self) -> None:
        figure = plot_substrate_absorption("calcium_fluoride")
        assert figure.axes[0].get_yscale() == "log"

    @pytest.mark.level1
    def test_n_stays_linear(self) -> None:
        """n is a percent-level variation; a log axis would flatten it."""
        figure = plot_substrate_absorption("calcium_fluoride")
        assert figure.axes[1].get_yscale() == "linear"

    @pytest.mark.level1
    def test_the_default_can_be_overridden_deliberately(self) -> None:
        figure = plot_substrate_absorption("germanium", log_alpha=False)
        assert figure.axes[0].get_yscale() == "linear"

    @pytest.mark.level1
    def test_the_span_that_motivates_the_log_axis_is_real(self) -> None:
        """Measured, not asserted from the docstring: CaF2's alpha spans >1000x."""
        material = SubstrateLibrary().material("calcium_fluoride")
        alpha = np.asarray(material.alpha_per_m)
        assert alpha.max() / alpha[alpha > 0].min() > 1000.0


class TestTheFigureSaysWhatTheMaterialIs:
    @pytest.mark.level1
    def test_the_title_carries_window_reference_temperature_and_tier(self) -> None:
        title = plot_substrate_absorption("germanium").axes[0].get_title()
        assert "Germanium (Ge)" in title
        assert "window" in title and "µm" in title
        assert "293 K" in title
        assert "tier B" in title
        assert "class-typical" in title  # the flag an analyst must not have to look up

    @pytest.mark.level1
    def test_a_measured_material_is_not_flagged(self) -> None:
        title = plot_substrate_absorption("zinc_selenide").axes[0].get_title()
        assert "measured anchors" in title
        assert "class-typical" not in title

    @pytest.mark.level1
    def test_the_label_matches_the_picker_exactly(self) -> None:
        """One label rule; it was briefly written twice."""
        from radiant.api.substrate import available_substrates

        info = next(i for i in available_substrates() if i.name == "zinc_sulphide_ms")
        assert info.label in plot_substrate_absorption("zinc_sulphide_ms").axes[0].get_title()


class TestBandShading:
    @pytest.mark.level1
    def test_a_band_is_shaded_on_both_panels(self) -> None:
        figure = plot_substrate_absorption("germanium", band_um=(3.0, 5.0))
        for axis in figure.axes[:2]:
            assert axis.patches, "evaluation band not shaded"

    @pytest.mark.level1
    def test_no_band_shades_nothing(self) -> None:
        figure = plot_substrate_absorption("germanium")
        assert not figure.axes[0].patches

    @pytest.mark.level1
    def test_the_full_window_is_drawn_not_just_the_band(self) -> None:
        """The point of the figure: see the band against the material's whole window."""
        material = SubstrateLibrary().material("germanium")
        line = plot_substrate_absorption("germanium", band_um=(3.0, 5.0)).axes[0].lines[0]
        drawn = line.get_xdata()
        assert float(np.min(drawn)) == pytest.approx(material.window_um[0], abs=1e-6)
        assert float(np.max(drawn)) == pytest.approx(material.window_um[1], abs=1e-6)


class TestUnknownMaterial:
    @pytest.mark.level1
    def test_it_raises_an_api_error_not_a_library_error(self) -> None:
        with pytest.raises(ApiValidationError) as excinfo:
            plot_substrate_absorption("unobtainium")
        assert "unknown substrate" in str(excinfo.value)
