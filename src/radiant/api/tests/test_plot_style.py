"""Tests for the token-derived plot style (owner ruling 2026-08-03).

Three contracts are pinned here:

1. **Token mirror** — ``radiant.api.plot_style`` duplicates the GUI theme hex
   values because the API layer may not import ``radiant.gui`` (import rules +
   optional extra). This file is the drift gate the duplication is licensed by:
   if either side changes alone, these tests go red.
2. **CVD palette gate** — the categorical series order was *computed*, not
   eyeballed: adjacent pairs must hold OKLab ΔE·100 ≥ 15 for normal vision and
   ≥ 8 under Machado severity-1.0 protan/deutan/tritan simulation, in both
   themes. The raw config-accent slot order fails this (deutan ΔE ≈ 3.8);
   re-introducing it by "tidying" the order would silently break colour-blind
   legibility, which is why the gate is a test and not a comment.
3. **Style application** — every ``result.plot.*`` figure builds under the
   house rcParams, light by default, dark inside ``plot_theme(dark=True)``.
"""

from __future__ import annotations

import itertools
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any

import numpy as np
import numpy.typing as npt
import pytest

from radiant.api import plot_style
from radiant.api.plot import plot_noise_budget, plot_sweep

if TYPE_CHECKING:
    from radiant.api.sweep import SweepResult

# ------------------------------------------------------------------
# OKLab / CVD math (test-local port of the palette validator)
# ------------------------------------------------------------------

_MACHADO: dict[str, npt.NDArray[np.float64]] = {
    "protan": np.array(
        [
            [0.152286, 1.052583, -0.204868],
            [0.114503, 0.786281, 0.099216],
            [-0.003882, -0.048116, 1.051998],
        ]
    ),
    "deutan": np.array(
        [
            [0.367322, 0.860646, -0.227968],
            [0.280085, 0.672501, 0.047413],
            [-0.011820, 0.042940, 0.968881],
        ]
    ),
    "tritan": np.array(
        [
            [1.255528, -0.076749, -0.178779],
            [-0.078411, 0.930809, 0.147602],
            [0.004733, 0.691367, 0.303900],
        ]
    ),
}


def _hex_to_linear(h: str) -> npt.NDArray[np.float64]:
    h = h.lstrip("#")
    srgb = np.array([int(h[i : i + 2], 16) / 255.0 for i in (0, 2, 4)])
    return np.where(srgb <= 0.04045, srgb / 12.92, ((srgb + 0.055) / 1.055) ** 2.4)


def _linear_to_oklab(rgb: npt.NDArray[np.float64]) -> npt.NDArray[np.float64]:
    r, g, b = np.clip(rgb, 0.0, 1.0)
    lin_l = 0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b
    lin_m = 0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b
    lin_s = 0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b
    l_, m_, s_ = np.cbrt(lin_l), np.cbrt(lin_m), np.cbrt(lin_s)
    return np.array(
        [
            0.2104542553 * l_ + 0.7936177850 * m_ - 0.0040720468 * s_,
            1.9779984951 * l_ - 2.4285922050 * m_ + 0.4505937099 * s_,
            0.0259040371 * l_ + 0.7827717662 * m_ - 0.8086757660 * s_,
        ]
    )


def _delta_e(h1: str, h2: str, cvd: str | None = None) -> float:
    a, b = _hex_to_linear(h1), _hex_to_linear(h2)
    if cvd is not None:
        a, b = _MACHADO[cvd] @ a, _MACHADO[cvd] @ b
    return float(np.linalg.norm(_linear_to_oklab(a) - _linear_to_oklab(b)) * 100.0)


# ------------------------------------------------------------------
# 1. Token mirror (drift gate)
# ------------------------------------------------------------------


class TestTokensMirrorGuiTheme:
    def test_tokens_match_gui_theme(self) -> None:
        """The API copies of the theme hexes must equal the GUI owners' values."""
        pytest.importorskip("PySide6", reason="gui extra not installed — mirror gate needs it")
        from radiant.gui.themes import tokens as gui_tokens

        for api_side, gui_side in (
            (plot_style.LIGHT, gui_tokens.LIGHT),
            (plot_style.DARK, gui_tokens.DARK),
        ):
            for key, value in api_side.items():
                assert value == getattr(gui_side, key), (
                    f"plot_style token {key!r} ({value}) drifted from gui theme "
                    f"{gui_side.name!r} ({getattr(gui_side, key)}) — the API mirror in "
                    "plot_style.py must be updated in lock-step with gui/themes/tokens.py"
                )

    def test_series_hues_come_from_config_accents(self) -> None:
        """Every series colour is one of the theme's configuration accents."""
        pytest.importorskip("PySide6", reason="gui extra not installed — mirror gate needs it")
        from radiant.gui.themes import tokens as gui_tokens

        assert set(plot_style.SERIES_LIGHT) <= set(gui_tokens.LIGHT.config_accents)
        assert set(plot_style.SERIES_DARK) <= set(gui_tokens.DARK.config_accents)
        assert plot_style.OTHER_LIGHT in gui_tokens.LIGHT.config_accents
        assert plot_style.OTHER_DARK in gui_tokens.DARK.config_accents


# ------------------------------------------------------------------
# 2. CVD palette gate
# ------------------------------------------------------------------


class TestSeriesPaletteIsCvdSafe:
    @pytest.mark.parametrize(
        "series",
        [plot_style.SERIES_LIGHT, plot_style.SERIES_DARK],
        ids=["light", "dark"],
    )
    def test_adjacent_pairs_separate_for_normal_vision(self, series: tuple[str, ...]) -> None:
        for h1, h2 in itertools.pairwise(series):
            assert _delta_e(h1, h2) >= 15.0, f"{h1}->{h2} below the normal-vision floor"

    @pytest.mark.parametrize(
        "series",
        [plot_style.SERIES_LIGHT, plot_style.SERIES_DARK],
        ids=["light", "dark"],
    )
    def test_adjacent_pairs_separate_under_cvd_simulation(self, series: tuple[str, ...]) -> None:
        for h1, h2 in itertools.pairwise(series):
            for cvd in _MACHADO:
                de = _delta_e(h1, h2, cvd)
                assert de >= 8.0, (
                    f"{h1}->{h2} under {cvd} simulation: ΔE·100 = {de:.1f} < 8 — "
                    "adjacent series would be indistinguishable to colour-deficient "
                    "viewers; reorder or re-step the palette (see module docstring)"
                )

    def test_dark_series_is_index_matched_to_light(self) -> None:
        """Hue identity survives a theme toggle (same slot, same hue family)."""
        assert len(plot_style.SERIES_LIGHT) == len(plot_style.SERIES_DARK)


# ------------------------------------------------------------------
# 3. Style application
# ------------------------------------------------------------------


class TestStyleApplication:
    def test_light_style_applies_by_default(self) -> None:
        fig = plot_noise_budget((SimpleNamespace(name="signal_shot", value_e=1200.0),))
        assert fig.get_facecolor() == _rgba(plot_style.LIGHT["panel"])

    def test_prop_cycle_is_the_validated_series_order(self) -> None:
        cycle = plot_style.rcparams(dark=False)["axes.prop_cycle"]
        assert tuple(c["color"] for c in cycle) == plot_style.SERIES_LIGHT

    def test_resolve_stack_never_names_a_missing_family(self) -> None:
        resolved = plot_style.resolve_stack(("No Such Font 9x7", "DejaVu Sans"))
        assert "No Such Font 9x7" not in resolved
        assert resolved  # never empty


def _rgba(hex_color: str) -> tuple[float, float, float, float]:
    h = hex_color.lstrip("#")
    return tuple(int(h[i : i + 2], 16) / 255.0 for i in (0, 2, 4)) + (1.0,)  # type: ignore[return-value,unused-ignore]


# ------------------------------------------------------------------
# Noise budget scale contract
# ------------------------------------------------------------------


def _terms(*pairs: tuple[str, float]) -> tuple[SimpleNamespace, ...]:
    return tuple(SimpleNamespace(name=n, value_e=v) for n, v in pairs)


class TestNoiseBudgetScale:
    def test_log_is_the_default(self) -> None:
        fig = plot_noise_budget(_terms(("signal_shot", 1200.0), ("read_noise", 5.0)))
        assert fig.axes[0].get_xscale() == "log"

    def test_linear_is_selectable(self) -> None:
        fig = plot_noise_budget(
            _terms(("signal_shot", 1200.0), ("read_noise", 5.0)), scale="linear"
        )
        assert fig.axes[0].get_xscale() == "linear"

    def test_invalid_scale_raises_actionable(self) -> None:
        from radiant.api.errors import ApiValidationError

        with pytest.raises(ApiValidationError):
            plot_noise_budget(_terms(("signal_shot", 1.0)), scale="sqrt")

    def test_log_floor_moves_tiny_terms_to_caption(self) -> None:
        fig = plot_noise_budget(_terms(("signal_shot", 1200.0), ("dsnu", 0.0)))
        labels = [t.get_text() for t in fig.axes[0].get_yticklabels()]
        assert "DSNU" not in labels  # below the floor → not a bar
        captions = " ".join(t.get_text() for t in fig.texts)
        assert "DSNU" in captions  # …but named in the caption

    def test_linear_keeps_every_term(self) -> None:
        fig = plot_noise_budget(_terms(("signal_shot", 1200.0), ("dsnu", 0.0)), scale="linear")
        labels = [t.get_text() for t in fig.axes[0].get_yticklabels()]
        assert "DSNU" in labels

    def test_value_labels_carry_units(self) -> None:
        fig = plot_noise_budget(_terms(("signal_shot", 1200.0), ("read_noise", 5.0)))
        annotations = [t.get_text() for t in fig.axes[0].texts]
        assert any("e⁻" in t for t in annotations)


# ------------------------------------------------------------------
# Sweep saturation shading
# ------------------------------------------------------------------


class TestSweepSaturationShading:
    def _sweep(self, statuses: list[str] | None) -> SweepResult:
        from radiant.api.sweep import SweepResult

        values = np.array([0.1, 0.2, 0.3, 0.4])
        metrics = np.array([100.0, 200.0, 250.0, 251.0])
        results: tuple[Any, ...] = ()
        if statuses is not None:
            results = tuple(
                SimpleNamespace(well_status=lambda s=s: SimpleNamespace(status=s)) for s in statuses
            )
        return SweepResult(
            param_name="optics.aperture_diameter_m",
            values=values,
            metric_values=metrics,
            results=results,
            metric_name="snr",
        )

    def test_clipped_points_are_shaded_and_labelled(self) -> None:
        fig = plot_sweep(self._sweep(["ok", "ok", "clipped", "clipped"]))
        ax = fig.axes[0]
        assert ax.patches, "expected a shaded axvspan over the clipped values"
        assert any("saturated" in t.get_text() for t in ax.texts)

    def test_no_results_means_no_shading(self) -> None:
        fig = plot_sweep(self._sweep(None))
        assert not fig.axes[0].patches

    def test_all_ok_means_no_shading(self) -> None:
        fig = plot_sweep(self._sweep(["ok", "ok", "ok", "ok"]))
        assert not fig.axes[0].patches

    def test_axis_label_carries_schema_unit(self) -> None:
        fig = plot_sweep(self._sweep(None))
        assert fig.axes[0].get_xlabel() == "aperture diameter (m)"
