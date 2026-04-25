"""ChainResult — read-only wrapper over the final ChainState.

Exposes raw frames, noise_terms, stage_outputs, history, metrics,
and backward-propagation query methods for expressing signal and
noise at any reference frame.
"""

from __future__ import annotations

import warnings
from collections.abc import Mapping
from typing import Any

import numpy as np
import numpy.typing as npt

from radiant.core.chain import ChainState
from radiant.core.quantity import (
    ChainQuantity,
    ReferenceFrame,
)
from radiant.core.quantity import noise_at as _quantity_noise_at
from radiant.core.quantity import signal_at as _quantity_signal_at
from radiant.core.radiometry import NoiseTerm, RadiometricFrame


class ChainResult:
    """Read-only view over a completed chain run.

    Parameters
    ----------
    state:
        The final :class:`ChainState` produced by
        :meth:`ChainRunner.run`.
    """

    def __init__(self, state: ChainState) -> None:
        self._state = state

    @property
    def state(self) -> ChainState:
        """The underlying ChainState (read-only access)."""
        return self._state

    @property
    def wavelength_um(self) -> npt.NDArray[np.float64]:
        """The common spectral grid [µm]."""
        return self._state.wavelength_um

    @property
    def frames(self) -> Mapping[str, RadiometricFrame]:
        """All registered radiometric frames (read-only mapping)."""
        return self._state.frames

    @property
    def noise_terms(self) -> tuple[NoiseTerm, ...]:
        """All noise contributions."""
        return self._state.noise_terms

    @property
    def stage_outputs(self) -> Mapping[str, Mapping[str, Any]]:
        """Per-stage metadata (read-only nested mapping)."""
        return self._state.stage_outputs

    @property
    def history(self) -> tuple[str, ...]:
        """Ordered tuple of stage names that executed."""
        return self._state.history

    @property
    def metrics(self) -> Mapping[str, float]:
        """Computed performance metrics (read-only mapping)."""
        return self._state.metrics

    # ------------------------------------------------------------------
    # Backward propagation queries
    # ------------------------------------------------------------------

    def signal_at(
        self,
        frame: ReferenceFrame | str,
    ) -> ChainQuantity:
        """Get the signal expressed at a target reference frame.

        Parameters
        ----------
        frame:
            Target reference frame (enum or string like "at_aperture").

        Returns
        -------
        ChainQuantity
            Signal value at the requested frame.
        """
        if isinstance(frame, str):
            frame = ReferenceFrame(frame)
        return _quantity_signal_at(self._state, frame)

    def noise_at(
        self,
        frame: ReferenceFrame | str,
        term_name: str | None = None,
    ) -> ChainQuantity:
        """Get noise (total or specific term) at a target reference frame.

        Parameters
        ----------
        frame:
            Target reference frame.
        term_name:
            If provided, return only the named noise term.
            If None, return total noise (RSS).

        Returns
        -------
        ChainQuantity
            Noise value at the requested frame.
        """
        if isinstance(frame, str):
            frame = ReferenceFrame(frame)
        return _quantity_noise_at(self._state, frame, term_name)

    # ------------------------------------------------------------------
    # Deprecated aliases (CU-NEW-03 — to be removed after 0.2.0)
    # ------------------------------------------------------------------

    def signal_at_frame(
        self,
        frame: ReferenceFrame | str,
    ) -> ChainQuantity:
        """Deprecated alias for :meth:`signal_at`. Issues DeprecationWarning."""
        warnings.warn(
            "ChainResult.signal_at_frame() is deprecated; use signal_at() instead. "
            "The old name will be removed in RADIANT 0.2.0.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.signal_at(frame)

    def noise_at_frame(
        self,
        frame: ReferenceFrame | str,
        term_name: str | None = None,
    ) -> ChainQuantity:
        """Deprecated alias for :meth:`noise_at`. Issues DeprecationWarning."""
        warnings.warn(
            "ChainResult.noise_at_frame() is deprecated; use noise_at() instead. "
            "The old name will be removed in RADIANT 0.2.0.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.noise_at(frame, term_name)

    # ------------------------------------------------------------------
    # Performance metric convenience accessors
    # ------------------------------------------------------------------

    def snr(self) -> float:
        """Signal-to-noise ratio (dimensionless). Reads ``metrics['snr']``.

        Raises
        ------
        KeyError
            If SNR was not computed for this run (e.g., scenario routed through
            a metric mode that did not populate ``metrics['snr']``). Inspect
            ``self.metrics`` to see what was actually computed.
        """
        return float(self._state.metrics["snr"])

    def nedt(self) -> float:
        """Noise-equivalent delta-temperature in kelvin. Reads ``metrics['nedt_K']``.

        Raises
        ------
        KeyError
            If NEDT was not computed for this run.
        """
        return float(self._state.metrics["nedt_K"])

    def niirs(self) -> float:
        """National Imagery Interpretability Rating Scale value. Reads ``metrics['niirs']``.

        Raises
        ------
        KeyError
            If NIIRS was not computed for this run.
        """
        return float(self._state.metrics["niirs"])
