"""Scene package — now only the physics-domain glyph palette (post 2D-schematic pivot).

The lifted PyVista/VTK scene library that once lived here (``builder``, ``arcs/``,
``frames/``, ``glyphs/``, ``ground/``, ``labels/``, ``target/``, ``vectors/`` — ADR-0007
Part A/B) was removed when the 2D orthographic ``QPainter`` schematic fully replaced it
(CU-132, Rule 27 one-canonical-version). The **one** module that survives is
:mod:`radiant.gui.viewer.scene.palette` — the allowlisted physics-domain glyph-colour
constants the 2D canvas still imports (the ``tests/test_theme.py`` token-discipline
allowlist keys on this exact path, so ``palette.py`` stays here rather than moving).

Nothing else remains: the schematic renders via
:mod:`radiant.gui.viewer.schematic_view`, not ``build_static_scene``.
"""

from __future__ import annotations

__all__: list[str] = []
