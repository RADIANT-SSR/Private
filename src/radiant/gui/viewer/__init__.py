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
  Geometry "Schematic" tab.

Pass 1 is the renderer core (the look). Pass 2 adds the angle arcs, leader labels, the
full shape library + dimension inputs, the RPY triad, and the angle-truth test — and
removes the now-unwired lifted VTK scene library (:mod:`radiant.gui.viewer.scene`, kept in
place but no longer rendered).
"""

from __future__ import annotations

from radiant.gui.viewer.viewer_state import ViewerState

__all__ = ["ViewerState"]
