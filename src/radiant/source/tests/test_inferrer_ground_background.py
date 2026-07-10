"""CU-008 — spectral GroundBackground ε_g(λ) (task doc anchors A1–A6).

The sub-pixel/point-source ``GroundBackground`` resolves its emissivity
from three surfaces, in precedence order:

1. ``source.background.emissivity_path`` — measured CSV (API-layer load).
2. ``source.background.material`` — named ``radiant.data.SpectralLibrary``
   entry (API-layer load).
3. ``source.background.emissivity`` scalar — the ``material="grey"``
   back-compat path (exact pre-CU-008 behavior, no placeholder warning).

The API layer resolves 1/2 pre-chain (Rule 6) and injects the native-grid
``SpectralData``; the inferrer resamples onto the chain grid. These tests
drive both the API resolver (``_load_background_emissivity``) and the
inferrer routing (``infer_descriptors(background_emissivity=...)``).
"""

from __future__ import annotations

import warnings
from pathlib import Path

import numpy as np
import pytest

from radiant.api._param_registry import build_parameter_set
from radiant.api.session import RadiantSession, _load_background_emissivity
from radiant.core.descriptors import GroundBackground
from radiant.core.parameters import ParameterBoundsError
from radiant.data.library import SpectralLibrary
from radiant.io.config import load_config
from radiant.source._inferrer import infer_descriptors

REPO_ROOT = Path(__file__).resolve().parents[4]

_WL_LWIR = np.linspace(8.0, 13.0, 11)


def _sub_pixel_params(material: str | None = None, emissivity_path: str | None = None):
    params = build_parameter_set()
    load_config(REPO_ROOT / "examples" / "templates" / "lwir_aerial_survey.yaml", params)
    params.set("source.scene_type", "sub_pixel")
    params.set("source.target.fill_fraction", 0.5)
    if material is not None:
        params.set("source.background.material", material)
    if emissivity_path is not None:
        params.set("source.background.emissivity_path", emissivity_path)
    params.resolve()
    return params


class TestBackgroundEmissivityResolver:
    @pytest.mark.level0
    def test_a1_grey_default_returns_none(self) -> None:
        """A1: material='grey' (default) → None → exact scalar back-compat."""
        params = _sub_pixel_params()
        assert _load_background_emissivity(params) is None

    @pytest.mark.level0
    def test_a2_vegetation_matches_library(self) -> None:
        """A2: a named material returns the library's tabulated values."""
        params = _sub_pixel_params(material="vegetation_green")
        sd = _load_background_emissivity(params)
        lib = SpectralLibrary().material("vegetation_green")
        np.testing.assert_allclose(sd.values, lib.values, atol=1e-9)
        np.testing.assert_allclose(sd.wavelength_um, lib.wavelength_um, atol=1e-12)

    @pytest.mark.level0
    def test_a3_snow_matches_library(self) -> None:
        """A3: snow entry round-trips identically."""
        params = _sub_pixel_params(material="snow")
        sd = _load_background_emissivity(params)
        lib = SpectralLibrary().material("snow")
        np.testing.assert_allclose(sd.values, lib.values, atol=1e-9)

    @pytest.mark.level0
    def test_a4_path_overrides_material(self, tmp_path: Path) -> None:
        """A4: emissivity_path wins over a named material."""
        csv = tmp_path / "override.csv"
        csv.write_text("wavelength_um,emissivity\n7.0,0.5\n10.0,0.5\n14.0,0.5\n")
        params = _sub_pixel_params(material="vegetation_green", emissivity_path=str(csv))
        sd = _load_background_emissivity(params)
        np.testing.assert_allclose(sd.values, 0.5, atol=1e-12)

    @pytest.mark.level0
    def test_a5_unknown_material_rejected_with_vocabulary(self) -> None:
        """A5: unknown names raise with the legal vocabulary (Rule 17)."""
        params = _sub_pixel_params(material="bogus_unknown_material")
        with pytest.raises(ParameterBoundsError, match="grey"):
            _load_background_emissivity(params)


class TestInferrerRouting:
    @pytest.mark.level0
    def test_grey_limit_identity(self) -> None:
        """Truth anchor 1: grey scalar ε = 0.95 → constant ε_g(λ) to 1e-15."""
        params = _sub_pixel_params()
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            _, bg, _ = infer_descriptors(params, _WL_LWIR)
        assert isinstance(bg, GroundBackground)
        expected = params.get("source.background.emissivity")
        np.testing.assert_allclose(bg.epsilon_g.values, expected, atol=1e-15)

    @pytest.mark.level0
    def test_injected_spectrum_resampled_onto_grid(self) -> None:
        """Injected ε_g resamples onto the chain grid; values match library."""
        lib = SpectralLibrary().material("vegetation_green")
        params = _sub_pixel_params(material="vegetation_green")
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            _, bg, _ = infer_descriptors(params, _WL_LWIR, background_emissivity=lib)
        assert isinstance(bg, GroundBackground)
        expected = np.interp(_WL_LWIR, lib.wavelength_um, lib.values)
        np.testing.assert_allclose(bg.epsilon_g.values, expected, atol=1e-12)
        assert bg.epsilon_g.wavelength_um.shape == _WL_LWIR.shape

    @pytest.mark.level0
    def test_out_of_range_emissivity_rejected(self) -> None:
        """ε_g outside [0, 1] after resampling raises (Rule 17)."""
        from radiant.core.spectral import SpectralData

        bad = SpectralData(
            name="bad",
            wavelength_um=np.array([7.0, 14.0]),
            values=np.array([0.5, 1.7]),
            unit="",
            source="test",
        )
        params = _sub_pixel_params()
        with pytest.raises(ParameterBoundsError, match="0, 1"), warnings.catch_warnings():
            warnings.simplefilter("ignore")
            infer_descriptors(params, _WL_LWIR, background_emissivity=bad)


class TestEndToEnd:
    @pytest.mark.level2
    def test_a6_material_changes_chain_results(self) -> None:
        """A6: switching grey → snow changes the sub-pixel background
        radiometry non-trivially (snow LWIR ε ≈ 0.97–0.99 vs grey 0.9 with
        a different spectral shape), and the chain runs end-to-end."""

        def _run(material: str | None):
            session = RadiantSession(wavelength_um=np.linspace(8.0, 13.0, 201))
            params = session.default_params()
            load_config(REPO_ROOT / "examples" / "templates" / "lwir_aerial_survey.yaml", params)
            params.set("source.scene_type", "sub_pixel")
            params.set("source.regime_override", "sub_pixel")  # keep in-pixel bg
            params.set("source.target.fill_fraction", 0.3)
            params.set("source.target.projected_area_m2", 4.0)
            params.set("source.target.range_m", 3000.0)
            params.set("source.background.emissivity", 0.5)  # grey ≠ snow
            if material is not None:
                params.set("source.background.material", material)
            params.resolve()
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                return session.run(params)

        grey = _run(None)
        snow = _run("snow")
        s_grey = grey.stage_outputs["spectral_integration"]["signal_e"]
        s_snow = snow.stage_outputs["spectral_integration"]["signal_e"]
        # The (1-ff) background term differs between ε_g = 0.5 grey and
        # snow's ~0.98 LWIR emissivity → total pixel signal shifts > 5%.
        assert abs(s_snow - s_grey) / s_grey > 0.05
