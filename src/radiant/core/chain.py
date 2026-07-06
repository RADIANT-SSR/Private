"""Signal-chain protocol, state, and runner.

Implements the Stage protocol (runtime-checkable), the frozen
``ChainState`` with ``MappingProxyType``-wrapped collection fields
(per CLAUDE.md Rule 7 and Jason's 2B.5 design decisions), and a
``ChainRunner`` that iterates stages and auto-records history.

Design decisions baked into this file (Jason-confirmed 2026-04-09):

1. ``ChainState.frames``, ``stage_outputs``, ``mtf_terms``, ``metrics``
   are typed as ``Mapping`` and frozen at construction via
   ``types.MappingProxyType``. Direct mutation raises ``TypeError``.
2. ``stage_outputs`` is a nested ``Mapping[str, Mapping[str, Any]]``;
   both the outer and inner dicts are wrapped.
3. ``ChainRunner`` validates stage-name uniqueness up front.
4. If a stage's returned state does not include its own name in
   ``history``, ``ChainRunner`` auto-appends it.
"""

from __future__ import annotations

import types
from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from typing import Any, Protocol, runtime_checkable

import numpy as np
import numpy.typing as npt

from radiant.core.parameters import ParameterSet
from radiant.core.provenance import new_run_id
from radiant.core.radiometry import NoiseTerm, RadiometricFrame

# ---------------------------------------------------------------------------
# Stage protocol
# ---------------------------------------------------------------------------


@runtime_checkable
class Stage(Protocol):
    """Protocol every chain stage must implement."""

    @property
    def name(self) -> str: ...

    def run(self, state: ChainState, params: ParameterSet) -> ChainState: ...


# ---------------------------------------------------------------------------
# ChainState
# ---------------------------------------------------------------------------


def _freeze_map(d: Mapping[str, Any] | dict[str, Any]) -> types.MappingProxyType[str, Any]:
    """Wrap a dict (or Mapping) in a read-only proxy."""
    return types.MappingProxyType(dict(d))


def _freeze_nested_map(
    d: Mapping[str, Mapping[str, Any]] | dict[str, dict[str, Any]],
) -> types.MappingProxyType[str, types.MappingProxyType[str, Any]]:
    """Wrap a dict-of-dicts in read-only proxies (both levels)."""
    return types.MappingProxyType({k: types.MappingProxyType(dict(v)) for k, v in d.items()})


@dataclass(frozen=True)
class ChainState:
    """Immutable, accumulating state flowing through the signal chain.

    All ``Mapping`` fields are wrapped in ``MappingProxyType`` at
    construction so that direct mutation raises ``TypeError``.

    Stages never mutate the input state — they call ``with_*`` helpers
    which return a *new* ``ChainState`` with the addition applied.
    """

    wavelength_um: npt.NDArray[np.float64]

    frames: Mapping[str, RadiometricFrame] = field(default_factory=dict)
    stage_outputs: Mapping[str, Mapping[str, Any]] = field(default_factory=dict)
    noise_terms: tuple[NoiseTerm, ...] = ()
    mtf_terms: Mapping[str, npt.NDArray[np.float64]] = field(default_factory=dict)
    spatial_freq_cycles_per_mrad: npt.NDArray[np.float64] | None = None
    metrics: Mapping[str, float] = field(default_factory=dict)
    history: tuple[str, ...] = ()
    run_id: str | None = None

    def __post_init__(self) -> None:
        # Coerce wavelength to float64.
        wl = np.asarray(self.wavelength_um, dtype=np.float64)
        object.__setattr__(self, "wavelength_um", wl)

        # Freeze all Mapping fields so mutation raises TypeError.
        object.__setattr__(self, "frames", _freeze_map(self.frames))
        object.__setattr__(self, "stage_outputs", _freeze_nested_map(self.stage_outputs))
        object.__setattr__(self, "mtf_terms", _freeze_map(self.mtf_terms))
        object.__setattr__(self, "metrics", _freeze_map(self.metrics))

    # ----- with_* helpers — each returns a NEW state --------------------

    def with_frame(self, frame: RadiometricFrame) -> ChainState:
        """Add (or replace) a named frame."""
        new_frames = dict(self.frames)
        new_frames[frame.name] = frame
        return replace(self, frames=new_frames)

    def with_stage_output(self, stage: str, key: str, value: Any) -> ChainState:
        """Stash a value under ``stage_outputs[stage][key]``."""
        outer: dict[str, dict[str, Any]] = {k: dict(v) for k, v in self.stage_outputs.items()}
        inner = outer.setdefault(stage, {})
        inner[key] = value
        return replace(self, stage_outputs=outer)

    def with_noise(self, term: NoiseTerm) -> ChainState:
        """Append a noise term."""
        return replace(self, noise_terms=self.noise_terms + (term,))

    def with_mtf(self, term_name: str, mtf: npt.NDArray[np.float64]) -> ChainState:
        """Add (or replace) a named MTF term."""
        new_mtf = dict(self.mtf_terms)
        new_mtf[term_name] = mtf
        return replace(self, mtf_terms=new_mtf)

    def with_spatial_freq(self, freq_cycles_per_mrad: npt.NDArray[np.float64]) -> ChainState:
        """Set the shared spatial-frequency grid for MTF terms."""
        return replace(self, spatial_freq_cycles_per_mrad=freq_cycles_per_mrad)

    def with_metric(self, key: str, value: float) -> ChainState:
        """Add (or replace) a named metric."""
        new_metrics = dict(self.metrics)
        new_metrics[key] = value
        return replace(self, metrics=new_metrics)

    def with_history(self, stage_name: str) -> ChainState:
        """Append ``stage_name`` to the history tuple."""
        return replace(self, history=self.history + (stage_name,))


# ---------------------------------------------------------------------------
# ChainRunner
# ---------------------------------------------------------------------------


class ChainRunner:
    """Executes an ordered list of stages against a common parameter set.

    Validates stage-name uniqueness at construction. During execution,
    auto-appends a history entry if the stage's returned state doesn't
    already contain it.
    """

    def __init__(self, stages: list[Stage]) -> None:
        names = [s.name for s in stages]
        dupes = [n for n in names if names.count(n) > 1]
        if dupes:
            raise ValueError(
                f"ChainRunner: duplicate stage names detected: {sorted(set(dupes))}. "
                "Every stage in the chain must have a unique name."
            )
        self._stages = list(stages)

    @property
    def stage_names(self) -> tuple[str, ...]:
        """Ordered tuple of registered stage names."""
        return tuple(s.name for s in self._stages)

    def run(
        self,
        params: ParameterSet,
        wavelength_um: npt.NDArray[np.float64],
        *,
        run_id: str | None = None,
        initial_stage_outputs: Mapping[str, Mapping[str, Any]] | None = None,
    ) -> ChainState:
        """Execute the chain and return the final accumulated state.

        Parameters
        ----------
        params, wavelength_um:
            ParameterSet and shared spectral grid (µm).
        run_id:
            Optional caller-supplied run identifier. Required to be
            unique across runs by C13. If ``None``, a fresh UUID4 is
            generated. The value is carried on the returned
            :class:`ChainState` and accessible via
            :attr:`ChainResult.provenance.run_id`.
        initial_stage_outputs:
            Optional pre-chain injections seeded into
            ``state.stage_outputs`` before the first stage runs. This is
            the Rule 6 hook: file-derived objects (e.g. the atmosphere
            model under ``atmosphere_config``, the optical element list
            under ``optics_config``) are loaded by the IO/API layer and
            injected here, so stages never read files. Keys must not
            collide with stage names.
        """
        rid = run_id if run_id is not None else new_run_id()
        state = ChainState(
            wavelength_um=np.asarray(wavelength_um, dtype=np.float64),
            run_id=rid,
        )
        if initial_stage_outputs is not None:
            for namespace, outputs in initial_stage_outputs.items():
                for key, value in outputs.items():
                    state = state.with_stage_output(namespace, key, value)
        for stage in self._stages:
            new_state = stage.run(state, params)
            # Auto-record history if the stage didn't self-record.
            if not new_state.history or new_state.history[-1] != stage.name:
                new_state = new_state.with_history(stage.name)
            state = new_state
        return state
