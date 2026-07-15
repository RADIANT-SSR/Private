"""Geometry viewer — the embedded 2D orthographic **schematic** over ``GeometryStage``.

The viewer is a crisp, antialiased line-schematic drawn with QPainter (ADR-0007,
superseded 2026-07-14 — the PyVista/VTK raster could not match the mockup's SVG line-art):

* :mod:`radiant.gui.viewer.projection` — the orthographic projection + direction math,
  ported verbatim from the ``geometry_viewer`` mockup's ``geometry.js``;
* :mod:`radiant.gui.viewer.schematic_view` — the ``SchematicView`` QPainter canvas that
  draws the scene (ground grid, axes, four vectors, glyphs, wireframe target, legend);
* :mod:`radiant.gui.viewer.viewer_state` — the ``ViewerState`` adapter binding a chain
  evaluation to the display fields (reused unchanged across the pivot);
* :mod:`radiant.gui.viewer.viewer_widget` — the ``GeometryViewer`` widget mounted in the
  Geometry "Schematic" tab;
* :mod:`radiant.gui.viewer.angle_overlay` — the interactive ``AngleToggleOverlay`` mounted
  bottom-left **on** the canvas (owner feedback 2026-07-14), mirroring the top-left VECTORS
  legend; each checkbox reveals/hides an angle arc via ``GeometryViewer.set_angle_revealed``;
* :mod:`radiant.gui.viewer.annotations` — the Qt-free angle-annotation catalog (names,
  symbols, frames, stage-truth keys) the schematic and the side panel share;
* :mod:`radiant.gui.viewer.angle_truth` — the viewer-local angle recomputation the
  consistency test checks against ``stage_outputs["geometry"]`` (§6.3, CU-133).

Pass 1 shipped the renderer core (the look). Pass 2 (shipped) adds the angle arcs + degree
labels, the altitude leader labels, the full shape library + dimension inputs, the RPY
triad, and the angle-truth test — and removed the retired lifted VTK scene library
(``radiant.gui.viewer.scene`` now holds only the allowlisted glyph ``palette``; CU-132).
"""

from __future__ import annotations

from radiant.gui.viewer.viewer_state import ViewerState

__all__ = ["ViewerState"]
