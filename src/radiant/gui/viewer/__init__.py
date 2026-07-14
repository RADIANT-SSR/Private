"""3D geometry viewer — the embedded PyVista scene over ``GeometryStage`` outputs.

Part A (ADR-0007 Phase 7 tasks 1–3): the lifted, Qt-free scene library
(:mod:`radiant.gui.viewer.scene`), the ``ViewerState`` adapter
(:mod:`radiant.gui.viewer.viewer_state`) that binds it to a chain evaluation, and the
``GeometryViewer`` (:mod:`radiant.gui.viewer.viewer_widget`) that embeds
``pyvistaqt.QtInteractor`` in the Geometry screen (with a graceful degradation panel when
VTK/OpenGL is unavailable).

Part B adds the interactions: click-to-reveal angle arcs, the shape-library switcher, and
the RPY body-axes triad.
"""

from __future__ import annotations

from radiant.gui.viewer.viewer_state import ViewerState

__all__ = ["ViewerState"]
