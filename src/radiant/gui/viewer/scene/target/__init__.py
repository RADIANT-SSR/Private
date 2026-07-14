"""Target-mesh dispatcher.

Per Rule 19 / C5: one file per target shape (sphere, cylinder, cone, box,
flat_plate, extended_cell). This ``__init__`` only dispatches by
``state.target_shape`` — it does *not* build any geometry itself.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from radiant.gui.viewer.viewer_state import ViewerState as SceneState

if TYPE_CHECKING:
    import pyvista as pv


def add_to_plotter(plotter: pv.Plotter, state: SceneState) -> None:
    """Dispatch to the per-shape module based on ``state.target_shape``.

    The dispatcher imports lazily so that adding a new shape only touches
    its own file plus this map — and so unused shape modules never
    instantiate their PyVista meshes during scene build.
    """
    kind = state.target_shape
    if kind == "sphere":
        from radiant.gui.viewer.scene.target import sphere

        sphere.add_to_plotter(plotter, state)
        return
    if kind == "cylinder":
        from radiant.gui.viewer.scene.target import cylinder

        cylinder.add_to_plotter(plotter, state)
        return
    if kind == "cone":
        from radiant.gui.viewer.scene.target import cone

        cone.add_to_plotter(plotter, state)
        return
    if kind == "box":
        from radiant.gui.viewer.scene.target import box

        box.add_to_plotter(plotter, state)
        return
    if kind == "flat_plate":
        from radiant.gui.viewer.scene.target import flat_plate

        flat_plate.add_to_plotter(plotter, state)
        return
    raise ValueError(
        f"scene.target.add_to_plotter: unknown target_shape={kind!r}. "
        f"Expected one of sphere/cylinder/cone/box/flat_plate."
    )
