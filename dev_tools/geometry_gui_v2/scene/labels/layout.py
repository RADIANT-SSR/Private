"""Force-directed label-position solver — screen-space deconfliction.

PLAN_v2.md §12 step 2:
  * Initial placement: each label is placed at a 60-pixel outward offset
    along the projected anchor's radial-from-centroid direction.
  * Iteration: 30 steps of (anchor-attraction + label-label repulsion +
    viewport-edge repulsion).
  * Output: per-label screen position + leader-line endpoints (anchor
    screen-xy → label screen-xy).

Round-3 S2 extension (anchor-mesh exclusion zone):
  * For labels whose anchor is a *mesh* (target body, satellite glyph,
    sun disc, background sphere), the caller supplies the projected
    screen-space AABB of that mesh, padded by
    ``MESH_EXCLUSION_PADDING_PX``. The solver:
      1. During iteration, applies a strong repulsive force from the
         exclusion-zone center whenever a label box still intersects.
      2. After convergence + label-label separation, runs a final hard
         pass that forcibly pushes any still-overlapping label out
         along the smaller-overlap axis.
  * This is a *hard* constraint: the post-solve guarantee is that no
    label box intersects its own anchor mesh's projected AABB. The
    iterative force is a soft hint that lets the solver converge to a
    consistent layout; the hard pass enforces the invariant.

Pure NumPy, no PyVista. The caller does the projection of world anchors
to screen space and feeds projected (xy, label_size) tuples in. This
keeps the solver testable in isolation and Qt-free.

Rule 19: own file. Force-directed layout is its own computation,
independent of anchor collection (``_anchors.py``) and label rendering
(``leader_label.py``).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import numpy.typing as npt

from dev_tools.geometry_gui_v2.scene import style

# Tunable knobs. These are not parameters in the RADIANT sense (no physics);
# they are visual-design constants. Names match PLAN_v2.md §12 step 2 verbatim.
#
# T5 tuning (visual remediation): the Phase-1 numbers placed every label on a
# 220-px ring around the *centroid* of the anchor cloud, which pushed labels
# far from their own anchors and produced long, crossing leader lines. The
# solver still converged to non-overlapping layouts (the hard test passed),
# but the intent of "label sits near its anchor" was lost. T5 swaps the
# centroid-ring initial placement for a per-anchor radial offset and
# tightens anchor attraction so the label-to-anchor distance stays short
# during the iterative solve.
INITIAL_OFFSET_PX: float = 90.0
ANCHOR_ATTRACTION_K: float = 0.05
LABEL_REPULSION_K: float = 2500.0
EDGE_REPULSION_K: float = 800.0
EDGE_PADDING_PX: float = 8.0
NUM_ITERATIONS: int = 60
CONVERGENCE_DELTA_PX: float = 0.5  # if max move < this, stop early.
# Final separation pass: directly push apart any boxes still overlapping
# after the iterative solve. Number of passes through the pair list.
SEPARATION_PASSES: int = 20

# Round-3 S2: anchor-mesh exclusion zone constants.
#
# ``MESH_EXCLUSION_PADDING_PX`` is the padding added to the projected
# mesh AABB before the solver treats it as forbidden territory — keeps a
# small but visible gap between the label box and the silhouette of the
# anchor mesh (e.g. the target sphere or the satellite diamond).
#
# ``MESH_EXCLUSION_K`` is the per-step force coefficient. It is tuned
# higher than ``LABEL_REPULSION_K``-on-typical-distances because the
# constraint is a *hard* one: violating "label sits inside the mesh
# silhouette" is worse than any other layout outcome. The post-solve
# hard-push pass guarantees the invariant even if this force isn't
# enough to converge in time.
MESH_EXCLUSION_PADDING_PX: float = 8.0
MESH_EXCLUSION_K: float = 200.0


@dataclass(frozen=True)
class LabelLayoutInput:
    anchor_screen_xy: npt.NDArray[np.float64]  # shape (2,)
    label_size_px: tuple[float, float]  # (width, height)
    # Round-3 S2: optional projected screen-space AABB of the anchor's
    # *mesh*, used to keep the label outside the mesh silhouette. Format
    # is ``(xmin, ymin, xmax, ymax)`` in pixels, already padded by the
    # caller via ``MESH_EXCLUSION_PADDING_PX``. ``None`` for anchors that
    # are points / vector-midpoints / arc-midpoints (no mesh silhouette
    # to avoid).
    mesh_bbox_px: tuple[float, float, float, float] | None = None


@dataclass(frozen=True)
class LabelLayoutResult:
    label_screen_xy: npt.NDArray[np.float64]  # shape (2,) — label center
    leader_anchor_xy: npt.NDArray[np.float64]  # shape (2,) — original anchor
    leader_label_xy: npt.NDArray[np.float64]  # shape (2,) — label position


def solve_layout(
    inputs: list[LabelLayoutInput],
    viewport_size_px: tuple[int, int],
) -> list[LabelLayoutResult]:
    """Run the force-directed solver and return per-label screen positions.

    Empty / single-label inputs are returned with the initial placement
    (no iteration needed).
    """
    n = len(inputs)
    if n == 0:
        return []

    width, height = float(viewport_size_px[0]), float(viewport_size_px[1])
    anchors = np.array([np.asarray(i.anchor_screen_xy, dtype=np.float64) for i in inputs])
    sizes = np.array([np.asarray(i.label_size_px, dtype=np.float64) for i in inputs])

    # Round-3 S2: pre-compute the per-label mesh-exclusion zones (padded
    # AABBs in screen pixels). ``None`` mesh bboxes become an "inactive"
    # row: zero half-extent and a center far off-screen, so the
    # vectorized intersection test never fires.
    has_mesh_bbox = np.zeros(n, dtype=bool)
    mesh_bbox_centers = np.zeros((n, 2), dtype=np.float64)
    mesh_bbox_half = np.zeros((n, 2), dtype=np.float64)
    for idx, inp in enumerate(inputs):
        if inp.mesh_bbox_px is None:
            continue
        xmin, ymin, xmax, ymax = inp.mesh_bbox_px
        if xmax <= xmin or ymax <= ymin:
            continue
        has_mesh_bbox[idx] = True
        mesh_bbox_centers[idx] = (0.5 * (xmin + xmax), 0.5 * (ymin + ymax))
        mesh_bbox_half[idx] = (0.5 * (xmax - xmin), 0.5 * (ymax - ymin))

    # Initial placement.
    centroid = anchors.mean(axis=0)
    if n == 1:
        # Single label: outward 60 px from screen center.
        radial = anchors[0] - np.array([width * 0.5, height * 0.5])
        norm = float(np.linalg.norm(radial))
        unit = radial / norm if norm > 1e-6 else np.array([1.0, 0.0])
        positions = anchors + unit * INITIAL_OFFSET_PX
        return [
            LabelLayoutResult(
                label_screen_xy=positions[0].copy(),
                leader_anchor_xy=anchors[0].copy(),
                leader_label_xy=positions[0].copy(),
            )
        ]

    # T5 tuning: place each label at INITIAL_OFFSET_PX along its own
    # anchor-from-centroid radial direction. Anchors at the centroid (zero
    # radial) fall back to a unit-x offset and let the iterative repulsion
    # spread them. This is intentionally per-anchor (not the centroid-ring
    # the Phase-1 solver used) so the initial state already honors "label
    # sits near its anchor"; the iterative pass then resolves overlaps
    # from this much better starting layout.
    deltas_init = anchors - centroid
    radial_norms = np.linalg.norm(deltas_init, axis=1)
    units = np.zeros_like(deltas_init)
    nonzero = radial_norms > 1e-6
    units[nonzero] = deltas_init[nonzero] / radial_norms[nonzero, None]
    units[~nonzero] = np.array([1.0, 0.0])
    positions = anchors + units * INITIAL_OFFSET_PX

    half_sizes = sizes * 0.5

    for _step in range(NUM_ITERATIONS):
        forces = np.zeros_like(positions)

        # Anchor attraction: pull each label back toward its anchor.
        forces += -ANCHOR_ATTRACTION_K * (positions - anchors)

        # Label-label repulsion (vectorized). For n labels, deltas[i,j] is
        # positions[i] - positions[j]. Forces are inverse-square along
        # delta, summed across each row to get net force on label i.
        deltas = positions[:, None, :] - positions[None, :, :]  # (n, n, 2)
        dist = np.linalg.norm(deltas, axis=2)  # (n, n)
        # Floor distance by half the larger label half-size so overlapping
        # labels don't blow up the inverse-cube term.
        min_dist = np.maximum(half_sizes[:, None, 0] + half_sizes[None, :, 0],
                              half_sizes[:, None, 1] + half_sizes[None, :, 1]) * 0.5
        d_eff = np.maximum(dist, min_dist)
        np.fill_diagonal(d_eff, np.inf)  # ignore self-interaction
        # Replace any zero-delta off-diagonal (co-located) with a small +x push.
        zero_mask = (dist < 1e-6) & ~np.eye(n, dtype=bool)
        deltas[zero_mask] = np.array([1.0, 0.0])
        d_eff[zero_mask] = 1.0
        inv_cube = LABEL_REPULSION_K / (d_eff ** 3)
        pair_forces = deltas * inv_cube[:, :, None]
        forces += pair_forces.sum(axis=1)

        # Round-3 S2: anchor-mesh exclusion. For each label whose anchor
        # has a mesh bbox, push the label center away from the bbox
        # center if the label box still intersects the (padded) mesh
        # bbox. Soft force during iteration; the post-solve hard-push
        # pass below guarantees the invariant.
        if np.any(has_mesh_bbox):
            for i in range(n):
                if not has_mesh_bbox[i]:
                    continue
                # AABB intersection test: separation gap on each axis.
                gap_x = abs(positions[i, 0] - mesh_bbox_centers[i, 0]) - (
                    half_sizes[i, 0] + mesh_bbox_half[i, 0]
                )
                gap_y = abs(positions[i, 1] - mesh_bbox_centers[i, 1]) - (
                    half_sizes[i, 1] + mesh_bbox_half[i, 1]
                )
                if gap_x < 0.0 and gap_y < 0.0:
                    delta = positions[i] - mesh_bbox_centers[i]
                    dnorm = float(np.linalg.norm(delta))
                    if dnorm < 1e-6:
                        # Co-located — push along +x as a tiebreaker.
                        unit = np.array([1.0, 0.0])
                    else:
                        unit = delta / dnorm
                    forces[i] += MESH_EXCLUSION_K * unit

        # Viewport-edge repulsion: linear push back from each wall.
        left_dist = positions[:, 0] - half_sizes[:, 0] - EDGE_PADDING_PX
        right_dist = (width - EDGE_PADDING_PX) - positions[:, 0] - half_sizes[:, 0]
        bot_dist = positions[:, 1] - half_sizes[:, 1] - EDGE_PADDING_PX
        top_dist = (height - EDGE_PADDING_PX) - positions[:, 1] - half_sizes[:, 1]

        forces[:, 0] += np.where(left_dist < 0, -EDGE_REPULSION_K * left_dist / (abs(left_dist) + 1.0) ** 2, 0.0)
        forces[:, 0] -= np.where(right_dist < 0, -EDGE_REPULSION_K * right_dist / (abs(right_dist) + 1.0) ** 2, 0.0)
        forces[:, 1] += np.where(bot_dist < 0, -EDGE_REPULSION_K * bot_dist / (abs(bot_dist) + 1.0) ** 2, 0.0)
        forces[:, 1] -= np.where(top_dist < 0, -EDGE_REPULSION_K * top_dist / (abs(top_dist) + 1.0) ** 2, 0.0)

        # Damped step.
        max_step = 12.0
        forces = np.clip(forces, -max_step, max_step)
        positions += forces

        # Hard clamp to viewport so we never drift off-screen between steps.
        positions[:, 0] = np.clip(
            positions[:, 0], half_sizes[:, 0] + EDGE_PADDING_PX,
            width - half_sizes[:, 0] - EDGE_PADDING_PX,
        )
        positions[:, 1] = np.clip(
            positions[:, 1], half_sizes[:, 1] + EDGE_PADDING_PX,
            height - half_sizes[:, 1] - EDGE_PADDING_PX,
        )

        if np.max(np.abs(forces)) < CONVERGENCE_DELTA_PX:
            break

    # Final separation pass: directly push apart any remaining overlapping
    # boxes. This is a hard guarantee for the deconfliction acceptance
    # test (PLAN_v2.md §12 step 6) — the iterative force solver is the
    # primary mechanism, but with N labels in a small viewport region the
    # equilibrium can still leave 1-2 px overlaps that this pass fixes.
    for _ in range(SEPARATION_PASSES):
        moved = False
        for i in range(n):
            for j in range(i + 1, n):
                dx = positions[i, 0] - positions[j, 0]
                dy = positions[i, 1] - positions[j, 1]
                overlap_x = (half_sizes[i, 0] + half_sizes[j, 0] + 2.0) - abs(dx)
                overlap_y = (half_sizes[i, 1] + half_sizes[j, 1] + 2.0) - abs(dy)
                if overlap_x > 0.0 and overlap_y > 0.0:
                    moved = True
                    # Push along the smaller-overlap axis (cheaper resolution).
                    if overlap_x < overlap_y:
                        push = overlap_x * 0.5 + 0.5
                        sign = 1.0 if dx >= 0.0 else -1.0
                        if dx == 0.0:
                            sign = 1.0 if i % 2 == 0 else -1.0
                        positions[i, 0] += sign * push
                        positions[j, 0] -= sign * push
                    else:
                        push = overlap_y * 0.5 + 0.5
                        sign = 1.0 if dy >= 0.0 else -1.0
                        if dy == 0.0:
                            sign = 1.0 if i % 2 == 0 else -1.0
                        positions[i, 1] += sign * push
                        positions[j, 1] -= sign * push
        # Re-clamp to viewport after the push.
        positions[:, 0] = np.clip(
            positions[:, 0], half_sizes[:, 0] + EDGE_PADDING_PX,
            width - half_sizes[:, 0] - EDGE_PADDING_PX,
        )
        positions[:, 1] = np.clip(
            positions[:, 1], half_sizes[:, 1] + EDGE_PADDING_PX,
            height - half_sizes[:, 1] - EDGE_PADDING_PX,
        )
        if not moved:
            break

    # Round-2 R6 (PLAN_v2_remediation_round2.md §7 step 4): hard cap on
    # label-to-anchor screen distance. The plan is explicit that "a label
    # that's 400 px from the thing it labels is worse than a label that
    # overlaps slightly" — so this clamp runs *after* separation and
    # accepts that it may re-introduce sub-pixel overlaps. The
    # iterative anchor-attraction term keeps most labels under the cap
    # already; this only acts on the outliers separation pushed too far.
    max_d = float(style.LABEL_MAX_ANCHOR_DISTANCE_PX)
    deltas_to_anchor = positions - anchors
    norms = np.linalg.norm(deltas_to_anchor, axis=1)
    too_far = norms > max_d
    if np.any(too_far):
        scale = np.where(too_far, max_d / np.maximum(norms, 1e-9), 1.0)
        positions = anchors + deltas_to_anchor * scale[:, None]
        # Re-clamp to viewport (the scale-down moves toward the anchor,
        # which is in-viewport, so this is mostly a no-op but cheap).
        positions[:, 0] = np.clip(
            positions[:, 0], half_sizes[:, 0] + EDGE_PADDING_PX,
            width - half_sizes[:, 0] - EDGE_PADDING_PX,
        )
        positions[:, 1] = np.clip(
            positions[:, 1], half_sizes[:, 1] + EDGE_PADDING_PX,
            height - half_sizes[:, 1] - EDGE_PADDING_PX,
        )

    # Round-3 S2: hard anchor-mesh exclusion. After every other pass
    # (including R6's max-distance clamp, which can pull a label back
    # toward its anchor and into the mesh), forcibly push every label
    # with a mesh bbox out along the smaller-overlap axis until the AABB
    # invariant holds. This is the post-solve guarantee — S2 outranks
    # R6's max-distance clamp because "label inside the mesh silhouette"
    # is always worse than "label slightly farther than 240 px from the
    # anchor".
    if np.any(has_mesh_bbox):
        for i in range(n):
            if not has_mesh_bbox[i]:
                continue
            for _ in range(SEPARATION_PASSES):
                gap_x = abs(positions[i, 0] - mesh_bbox_centers[i, 0]) - (
                    half_sizes[i, 0] + mesh_bbox_half[i, 0]
                )
                gap_y = abs(positions[i, 1] - mesh_bbox_centers[i, 1]) - (
                    half_sizes[i, 1] + mesh_bbox_half[i, 1]
                )
                if gap_x >= 0.0 or gap_y >= 0.0:
                    break
                # Push along the smaller-overlap axis.
                overlap_x = -gap_x
                overlap_y = -gap_y
                if overlap_x < overlap_y:
                    sign = 1.0 if positions[i, 0] >= mesh_bbox_centers[i, 0] else -1.0
                    positions[i, 0] += sign * (overlap_x + 0.5)
                else:
                    sign = 1.0 if positions[i, 1] >= mesh_bbox_centers[i, 1] else -1.0
                    positions[i, 1] += sign * (overlap_y + 0.5)
                # Stay inside the viewport. Clamping is per-axis and uses
                # the half-size so the *box* stays inside, not just the
                # center.
                positions[i, 0] = float(np.clip(
                    positions[i, 0],
                    half_sizes[i, 0] + EDGE_PADDING_PX,
                    width - half_sizes[i, 0] - EDGE_PADDING_PX,
                ))
                positions[i, 1] = float(np.clip(
                    positions[i, 1],
                    half_sizes[i, 1] + EDGE_PADDING_PX,
                    height - half_sizes[i, 1] - EDGE_PADDING_PX,
                ))

    return [
        LabelLayoutResult(
            label_screen_xy=positions[i].copy(),
            leader_anchor_xy=anchors[i].copy(),
            leader_label_xy=positions[i].copy(),
        )
        for i in range(n)
    ]


def boxes_overlap(
    center_a: npt.NDArray[np.float64], size_a: tuple[float, float],
    center_b: npt.NDArray[np.float64], size_b: tuple[float, float],
    tolerance_px: float = 1.0,
) -> bool:
    """Return True if two axis-aligned screen-space boxes overlap by more
    than ``tolerance_px`` on both axes."""
    dx = abs(center_a[0] - center_b[0]) - 0.5 * (size_a[0] + size_b[0])
    dy = abs(center_a[1] - center_b[1]) - 0.5 * (size_a[1] + size_b[1])
    return dx < -tolerance_px and dy < -tolerance_px
