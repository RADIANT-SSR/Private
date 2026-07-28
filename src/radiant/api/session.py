"""RadiantSession — public entry point for running the signal chain.

Builds a :class:`~radiant.core.chain.ChainRunner` with the full
stage set and exposes a ``.run(params)`` that returns a
:class:`~radiant.io.results.ChainResult`.
"""

from __future__ import annotations

import warnings
from typing import Any

import numpy as np
import numpy.typing as npt

from radiant.api._param_registry import build_parameter_set

# Stage imports — only api/ may import all physics stages.
from radiant.atmosphere.loaders import build_atmosphere_model, build_cn2_profile
from radiant.atmosphere.stage import AtmosphereStage
from radiant.core.chain import ChainRunner
from radiant.core.parameters import ParameterSet
from radiant.detector.stage import DetectorStage
from radiant.geometry.stage import GeometryStage
from radiant.io.results import ChainResult
from radiant.optics.stage import OpticsStage
from radiant.performance.stage import PerformanceStage
from radiant.platform.stage import PlatformStage
from radiant.readout.stage import ReadoutStage
from radiant.source.stage import SourceStage
from radiant.spectral_integration.stage import SpectralIntegrationStage


def _qe_temperature_factor(params: ParameterSet) -> float:
    """QE(T) linear factor ``1 + coeff·(T_det − T_ref)`` (Gap 48).

    Returns 1.0 when the coefficient is 0 (temperature-independent QE), so
    the default path is exactly unchanged.
    """
    try:
        coeff: float = params.get("detector.qe_temperature_coeff_per_K")
    except (KeyError, TypeError):
        return 1.0
    if coeff == 0.0:
        return 1.0
    t_det: float = params.get("detector.detector_temperature_K")
    t_ref: float = params.get("detector.qe_temperature_ref_K")
    return 1.0 + coeff * (t_det - t_ref)


def _load_zernike_wavefront(params: ParameterSet) -> Any | None:
    """Load optics.zernike_file into a ZERNIKE WavefrontError, or None when unset.

    The export's own reference wavelength is honored;
    ``optics.wfe_reference_wavelength_um`` is the fallback when the report has no
    parseable Wavelength header (both Rule 6 pre-chain: the stage never reads files).
    """
    try:
        path_str: str = params.get("optics.zernike_file")
    except (KeyError, TypeError):
        path_str = ""
    if not path_str:
        return None
    from radiant.io.zemax_zernike import load_zemax_zernike

    result = load_zemax_zernike(path_str)
    if result.reference_wavelength_um is not None:
        return result.to_wavefront_error()
    fallback: float = params.get("optics.wfe_reference_wavelength_um")
    return result.to_wavefront_error(reference_wavelength_um=fallback)


def _load_qe_curve(
    params: ParameterSet, wavelength_um: npt.NDArray[np.float64]
) -> npt.NDArray[np.float64] | None:
    """Build the spectral QE array from the config, or None for the scalar path.

    Combines two effects, both Rule 6 (file/parameter handling in the API
    layer, not a stage):

    - ``detector.qe_table_path`` (Gap 44): a wavelength-vs-QE CSV, evaluated
      onto the grid (past-cutoff QE = 0), superseding the scalar qe_value.
    - ``detector.qe_temperature_coeff_per_K`` (Gap 48): a linear QE(T)
      factor applied to whichever base QE is in effect.

    Returns None only when neither is active (no path *and* factor == 1), so
    the historical scalar-``qe_value`` path — and all goldens — are
    untouched by default. QE is clamped to [0, 1] with a ``UserWarning`` if
    the temperature factor pushes it out of range (Rule 17: no silent clip).
    """
    factor = _qe_temperature_factor(params)
    try:
        path_str: str = params.get("detector.qe_table_path")
    except (KeyError, TypeError):
        path_str = ""

    try:
        _material_probe: str = params.get("detector.qe_material")
    except (KeyError, TypeError):
        _material_probe = ""
    if not path_str and not _material_probe and factor == 1.0:
        return None

    try:
        material: str = params.get("detector.qe_material")
    except (KeyError, TypeError):
        material = ""

    if path_str:
        from radiant.io.qe_csv import load_qe_csv

        base = load_qe_csv(path_str).evaluate(wavelength_um, out_of_range="zero")
    elif material:
        # Gap 69: a named bundled detector QE curve. Resolved here per Rule 6;
        # unknown names are rejected with the legal vocabulary (Rule 17). QE = 0
        # past the library data span (the same cutoff convention as qe_table_path).
        from radiant.core.parameters import ParameterBoundsError
        from radiant.data.library import SpectralLibrary

        library = SpectralLibrary()
        known = library.detectors()
        if material not in known:
            raise ParameterBoundsError(
                what=f"detector.qe_material = {material!r} is not in the detector library",
                why="QE(λ) can only be resolved for bundled detector materials.",
                action=f"Choose one of: {', '.join(sorted(known))}; or supply "
                "a vendor curve via detector.qe_table_path.",
                context={"material": material, "known_materials": sorted(known)},
            )
        curve = library.detector_qe(material)
        base = np.interp(wavelength_um, curve.wavelength_um, curve.values, left=0.0, right=0.0)
    else:
        qe_value: float = params.get("detector.qe_value")
        base = np.full_like(wavelength_um, qe_value)

    qe = base * factor
    if qe.min() < 0.0 or qe.max() > 1.0:
        warnings.warn(
            f"QE(T) factor {factor:.4g} pushed QE outside [0, 1] "
            f"(min {qe.min():.4g}, max {qe.max():.4g}); clamping.",
            UserWarning,
            stacklevel=2,
        )
        qe = np.clip(qe, 0.0, 1.0)
    return qe


def _load_background_emissivity(params: ParameterSet) -> Any | None:
    """Resolve spectral background emissivity ε_g(λ), or None for grey.

    CU-008: the sub-pixel/point-source ``GroundBackground`` accepts a
    spectral ε_g(λ) from two config surfaces, resolved here per Rule 6
    (file/library I/O in the API layer, never in a stage):

    - ``source.background.emissivity_path`` — a two-column CSV (wins).
    - ``source.background.material`` — a named entry in
      :class:`radiant.data.SpectralLibrary` (e.g. ``vegetation_green``,
      ``snow``); ``"grey"`` (the default) returns None so the inferrer
      keeps the exact scalar back-compat path.

    Unknown material names are rejected with the legal vocabulary
    (Rule 17). Returns a native-grid :class:`SpectralData`; the inferrer
    resamples onto the chain grid.
    """
    try:
        path_str: str = params.get("source.background.emissivity_path")
    except (KeyError, TypeError):
        path_str = ""
    if path_str:
        from radiant.source.converters._csv import load_two_column_csv

        return load_two_column_csv(
            path_str,
            value_unit="",
            column_label="emissivity",
            sd_name="source.background.emissivity",
            sd_source_prefix="source.background.emissivity_path",
        )

    try:
        material: str = params.get("source.background.material")
    except (KeyError, TypeError):
        material = "grey"
    if material == "grey":
        return None

    from radiant.core.parameters import ParameterBoundsError
    from radiant.data.library import SpectralLibrary

    library = SpectralLibrary()
    known = library.materials()
    if material not in known:
        raise ParameterBoundsError(
            what=f"source.background.material = {material!r} is not in the spectral library",
            why="ε_g(λ) can only be resolved for library materials or 'grey'.",
            action=(
                f"Choose one of: grey, {', '.join(sorted(known))}; or supply "
                "a measured spectrum via source.background.emissivity_path."
            ),
            context={"material": material, "known_materials": sorted(known)},
        )
    return library.material(material)


class RadiantSession:
    """High-level session for running the RADIANT signal chain.

    Parameters
    ----------
    wavelength_um:
        The common spectral evaluation grid [µm]. All stages evaluate
        on this grid; no resampling occurs inside the chain.
    """

    def __init__(self, wavelength_um: npt.NDArray[np.float64]) -> None:
        self._wavelength_um = np.asarray(wavelength_um, dtype=np.float64)
        self._runner = ChainRunner(
            [
                GeometryStage(),
                SourceStage(),
                AtmosphereStage(),
                OpticsStage(),
                PlatformStage(),
                SpectralIntegrationStage(),
                DetectorStage(),
                ReadoutStage(),
                PerformanceStage(),
            ]
        )

    @property
    def stage_names(self) -> tuple[str, ...]:
        return self._runner.stage_names

    def run(
        self,
        params: ParameterSet,
        extra_stage_outputs: dict[str, dict[str, Any]] | None = None,
    ) -> ChainResult:
        """Execute the chain and return the result.

        Builds the configured atmosphere model before chain execution
        (Rule 6: any file I/O the model needs happens here, not inside
        ``AtmosphereStage.run``) and injects it via
        ``stage_outputs["atmosphere_config"]["model"]``.

        Parameters
        ----------
        params:
            Resolved parameter set.
        extra_stage_outputs:
            Optional additional pre-chain injections merged over the
            built-in ones — the Rule 6 route for non-scalar inputs, e.g.
            ``{"optics_config": {"psf_weighting_spectrum": spectral_data}}``
            (Gap 17) or ``{"optics_config": {"element_list": [...]}}``.

        The returned :class:`ChainResult` carries the provided
        ``params`` so that
        :meth:`~radiant.io.results.ChainResult.to_provenance_record`
        can include the resolved parameter set and any input file
        hashes recorded by :func:`radiant.io.config.load_config`.
        """
        atmosphere_model = build_atmosphere_model(params)
        initial: dict[str, dict[str, Any]] = {
            "atmosphere_config": {"model": atmosphere_model},
        }
        # Tabulated Cn² turbulence profile (Gap 110): the schema param
        # atmosphere.cn2_tabulated_file names an altitude-vs-Cn² CSV. Rule 6
        # keeps file I/O out of the stage, so parse it here and inject the
        # profile object; None for every other atmosphere.cn2_profile value.
        cn2_profile = build_cn2_profile(params)
        if cn2_profile is not None:
            initial["atmosphere_config"]["cn2_profile"] = cn2_profile
        # Spectral QE from a file (Gap 44): the schema param
        # detector.qe_table_path names a wavelength-vs-QE CSV. Rule 6 keeps
        # file I/O out of the stage, so load it here and inject the curve
        # onto the wavelength grid as spectral_integration.qe_curve (which
        # supersedes the scalar detector.qe_value). Past-cutoff QE is zero.
        qe_curve = _load_qe_curve(params, self._wavelength_um)
        if qe_curve is not None:
            initial.setdefault("spectral_integration", {})["qe_curve"] = qe_curve
        # Spectral background emissivity (CU-008): resolve the named
        # library material / CSV override here (Rule 6) and inject; the
        # source inferrer consumes it when building GroundBackground.
        bg_eps = _load_background_emissivity(params)
        if bg_eps is not None:
            initial.setdefault("source_config", {})["background_emissivity"] = bg_eps
        # Zemax Zernike wavefront from a file (GS-4 split 2): optics.zernike_file
        # names a 'Zernike Standard Coefficients' export. Rule 6 keeps file I/O out
        # of the stage: load here, inject the ZERNIKE WavefrontError (supersedes the
        # scalar wfe_mode path; an explicit extra_stage_outputs injection still wins
        # because extras merge after this block).
        zernike_wfe = _load_zernike_wavefront(params)
        if zernike_wfe is not None:
            initial.setdefault("optics_config", {})["wavefront_error"] = zernike_wfe
        for group, values in (extra_stage_outputs or {}).items():
            initial.setdefault(group, {}).update(values)
        state = self._runner.run(
            params,
            self._wavelength_um,
            initial_stage_outputs=initial,
        )
        return ChainResult(state, params=params)

    @staticmethod
    def default_params() -> ParameterSet:
        """Return a ParameterSet pre-loaded with the full 2B.5 schema."""
        return build_parameter_set()
