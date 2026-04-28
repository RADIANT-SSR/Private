"""Force-directed label-position solver — screen-space deconfliction.

PLAN_v2.md §12 step 2:
  * Initial placement: each label is placed at a 60-pixel outward offset
    along the projected anchor's radial-from-centroid direction.
  * Iteration: 30 steps of (anchor-attraction + label-label repulsion +
    viewport-edge repulsion).
  * Output: per-label screen position + leader-line endpoints (anchor
    screen-xy → label screen-xy).

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

# Tunable knobs. These are not parameters in the RADIANT sense (no physics);
# they are visual-design constants. Names match PLAN_v2.md §12 step 2 verbatim.
INITIAL_OFFSET_PX: float = 60.0
INITIAL_RING_RADIUS_PX: float = 220.0  # angular-slot ring radius for n > 1 labels
ANCHOR_ATTRACTION_K: float = 0.02
LABEL_REPULSION_K: float = 4000.0
EDGE_REPULSION_K: float = 800.0
EDGE_PADDING_PX: float = 8.0
NUM_ITERATIONS: int = 60
CONVERGENCE_DELTA_PX: float = 0.5  # if max move < this, stop early.
# Final separation pass: directly push apart any boxes still overlapping
# after the iterative solve. Number of passes through the pair list.
SEPARATION_PASSES: int = 20


@dataclass(frozen=True)
class LabelLayoutInput:
    anchor_screen_xy: npt.NDArray[np.float64]  # shape (2,)
    label_size_px: tuple[float, float]  # (width, height)


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

    # Multi-label: angular-slot placement on a ring around the centroid.
    # Sort labels by their anchor's angle from centroid (so adjacent slots
    # belong to anchors that are visually close — minimizes leader-line
    # crossings).
    deltas_init = anchors - centroid
    angles = np.arctan2(deltas_init[:, 1], deltas_init[:, 0])
    order = np.argsort(angles)
    slot_angles = np.linspace(0.0, 2.0 * np.pi, n, endpoint=False)
    positions = np.empty_like(anchors)
    ring_r = min(
        INITIAL_RING_RADIUS_PX,
        0.4 * min(width, height),
    )
    for slot_idx, anchor_idx in enumerate(order):
        a = slot_angles[slot_idx]
        positions[anchor_idx] = centroid + ring_r * np.array([np.cos(a), np.sin(a)])

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
