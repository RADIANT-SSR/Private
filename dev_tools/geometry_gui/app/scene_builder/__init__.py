"""Scene-builder package.

Re-exports the orchestrator. All scene-building flows through `build_scene`.
Sub-modules export `*_traces(...)` functions that each return a list of
plotly traces — Rule 19: one primitive, one file.
"""

from dev_tools.geometry_gui.app.scene_builder.build_scene import build_scene

__all__ = ["build_scene"]
