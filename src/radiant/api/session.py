"""RadiantSession — public entry point for running the signal chain.

Builds a :class:`~radiant.core.chain.ChainRunner` with the full
stage set and exposes a ``.run(params)`` that returns a
:class:`~radiant.io.results.ChainResult`.
"""

from __future__ import annotations

import numpy as np
import numpy.typing as npt

from radiant.api._param_registry import build_parameter_set

# Stage imports — only api/ may import all physics stages.
from radiant.atmosphere.loaders import build_atmosphere_model
from radiant.atmosphere.stage import AtmosphereStage
from radiant.core.chain import ChainRunner
from radiant.core.parameters import ParameterSet
from radiant.detector.stage import DetectorStage
from radiant.io.results import ChainResult
from radiant.optics.stage import OpticsStage
from radiant.performance.stage import PerformanceStage
from radiant.platform.stage import PlatformStage
from radiant.readout.stage import ReadoutStage
from radiant.source.stage import SourceStage
from radiant.spectral_integration.stage import SpectralIntegrationStage


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

    def run(self, params: ParameterSet) -> ChainResult:
        """Execute the chain and return the result.

        Builds the configured atmosphere model before chain execution
        (Rule 6: any file I/O the model needs happens here, not inside
        ``AtmosphereStage.run``) and injects it via
        ``stage_outputs["atmosphere_config"]["model"]``.

        The returned :class:`ChainResult` carries the provided
        ``params`` so that
        :meth:`~radiant.io.results.ChainResult.to_provenance_record`
        can include the resolved parameter set and any input file
        hashes recorded by :func:`radiant.io.config.load_config`.
        """
        atmosphere_model = build_atmosphere_model(params)
        state = self._runner.run(
            params,
            self._wavelength_um,
            initial_stage_outputs={"atmosphere_config": {"model": atmosphere_model}},
        )
        return ChainResult(state, params=params)

    @staticmethod
    def default_params() -> ParameterSet:
        """Return a ParameterSet pre-loaded with the full 2B.5 schema."""
        return build_parameter_set()
