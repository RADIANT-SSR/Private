"""ChainResult — read-only wrapper over the final ChainState.

Exposes raw frames, noise_terms, stage_outputs, history, metrics,
and backward-propagation query methods for expressing signal and
noise at any reference frame.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import numpy as np
import numpy.typing as npt

from radiant.core.chain import ChainState
from radiant.core.quantity import (
    ChainQuantity,
    ReferenceFrame,
    noise_at,
    signal_at,
)
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

    def signal_at_frame(
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
        return signal_at(self._state, frame)

    def noise_at_frame(
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
        return noise_at(self._state, frame, term_name)
