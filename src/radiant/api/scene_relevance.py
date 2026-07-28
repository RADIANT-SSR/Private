"""Public API surface for the scene-class → metric-relevance map (ADR-0011, guardrail G3).

Re-exports the one declarative scene-class relevance map from
:mod:`radiant.performance.scene_relevance` so that view layers — the GUI, the
CLI — can show *which metrics a scene class turns off by default* without
importing a physics stage directly (the import-linter contract forbids
``radiant.gui`` → ``radiant.performance``; ``radiant.api`` is the sanctioned
bridge, the same precedent as :mod:`radiant.api.metric_groups` and
:mod:`radiant.api.geometry_modes`). The GUI's Geometry screen builds its
scene-class relevance preview from :func:`default_off_metrics`.

Why a re-export and not a second table: guardrail **G3** (Geometry-Flexibility
plan §3.5) requires scene-class conditioning to be *data in exactly one place*.
A GUI-side copy of the off-sets would be a second declaration that drifts from
the one the chain actually applies, so this module adds no data of its own — it
only widens the import contract.

The relevance shown through this bridge is a **default**: an analyst who
explicitly sets a ``performance.metrics.*`` group flag gets that group verbatim
(the Gap 96 override semantics). Callers presenting the off-set must say so.
"""

from __future__ import annotations

from radiant.performance.scene_relevance import (
    OFF_BY_TARGET_BAND,
    SCENE_CLASS_KEYS,
    SCENE_RELEVANCE,
    default_off_metrics,
    target_band_of,
)

__all__ = [
    "OFF_BY_TARGET_BAND",
    "SCENE_CLASS_KEYS",
    "SCENE_RELEVANCE",
    "default_off_metrics",
    "target_band_of",
]
