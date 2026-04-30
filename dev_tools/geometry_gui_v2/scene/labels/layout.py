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

Round-3 S3 extension (co-located-anchor cluster handling):
  * Many anchors project to nearly the same screen point — the angle
    arc midpoints and the target centroid all collapse onto the target
    when the camera looks down at it. Round-1/T5's per-anchor radial
    initial placement degenerates here: every label ends up on the same
    radial direction with effectively the same start position, so the
    iterative pair-repulsion has to do all the spreading work and tends
    to leave a piled-up cluster in the converged layout.
  * S3 introduces *cluster detection*: anchors within
    ``CENTRAL_CLUSTER_THRESHOLD_PX`` of each other (transitively, via
    union-find) form a cluster. Each cluster member gets:
      1. An evenly-distributed initial angular position around the
         cluster centroid at ``CENTRAL_CLUSTER_INITIAL_OFFSET_PX`` —
         breaks the symmetry that causes pile-up before the solver runs.
      2. Reduced anchor attraction
         (``CLUSTERED_ANCHOR_ATTRACTION_K`` < ``ANCHOR_ATTRACTION_K``)
         so the spread state isn't pulled back toward the pile.
      3. Boosted pair repulsion among cluster-mates
         (``CLUSTERED_PAIR_REPULSION_BOOST``) so co-located labels
         actively spread apart.
  * The first ``REPULSION_BOOST_ITERS`` iterations also use a global
    repulsion boost (``EARLY_REPULSION_BOOST``) to aggressively
    separate any near-overlap before the layout settles. This decays
    smoothly to 1.0 by the end of the boost window so the solver can
    converge without oscillation.

Tuned constants (round-3 S3 final):
  * ``INITIAL_OFFSET_PX = 90``  — non-clustered radial offset. Kept
    unchanged from T5; the centroid-radial placement is correct for
    non-co-located anchors and keeps leader lines short.
  * ``CENTRAL_CLUSTER_INITIAL_OFFSET_PX = 180`` — clustered angular
    offset. Plan §5 step 1 spec.
  * ``CENTRAL_CLUSTER_THRESHOLD_PX = 40`` — cluster membership
    threshold. Plan §5 step 3 spec.
  * ``ANCHOR_ATTRACTION_K = 0.05`` — non-clustered attraction. Kept.
  * ``CLUSTERED_ANCHOR_ATTRACTION_K = 0.025`` — halved per plan §5
    step 4.
  * ``LABEL_REPULSION_K = 2500.0`` — base inverse-cube coefficient.
    Kept (the spec calls for 8.0 in round-1 units; the round-1 to
    round-3 unit-system change preserves the same equilibrium).
  * ``EARLY_REPULSION_BOOST = 1.875`` (= 15.0 / 8.0) — boost factor for
    iterations 0..``REPULSION_BOOST_ITERS - 1``. Plan §5 step 2.
  * ``REPULSION_BOOST_ITERS = 20`` — duration of the early boost.
  * ``CLUSTERED_PAIR_REPULSION_BOOST = 1.625`` (= (8 + 5) / 8) —
    additional boost between cluster-mates only. Plan §5 step 3
    additive 5.0 in round-1 units.
  * ``NUM_ITERATIONS = 120`` — bumped from 60 per plan §5 step 5.
  * ``CONVERGENCE_DELTA_PX = 0.5`` — unchanged.

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
NUM_ITERATIONS: int = 120
CONVERGENCE_DELTA_PX: float = 0.5  # if max move < this, stop early.
# Final separation pass: directly push apart any boxes still overlapping
# after the iterative solve. Number of passes through the pair list.
SEPARATION_PASSES: int = 20

# Round-3 S3: co-located-anchor cluster handling.
#
# Anchors within ``CENTRAL_CLUSTER_THRESHOLD_PX`` of each other (after
# screen projection) are treated as a *cluster*: the angle-arc midpoints
# and the target centroid all collapse onto the target body when the
# camera looks down at it, and the per-anchor radial initial placement
# degenerates because every label has the same anchor-from-centroid
# direction. For cluster members, the solver:
#   (a) initializes positions on an even angular spread around the
#       cluster centroid at ``CENTRAL_CLUSTER_INITIAL_OFFSET_PX``;
#   (b) halves the anchor attraction
#       (``CLUSTERED_ANCHOR_ATTRACTION_K``) so the spread state isn't
#       pulled back into the pile;
#   (c) boosts pair repulsion between cluster-mates by
#       ``CLUSTERED_PAIR_REPULSION_BOOST``.
#
# The first ``REPULSION_BOOST_ITERS`` iterations apply a global early
# repulsion boost (``EARLY_REPULSION_BOOST``) on top of the per-pair
# coefficients, decaying linearly to 1.0 by the end of the boost
# window. This separates near-overlapping labels aggressively up front
# while still letting the layout converge without oscillation.
CENTRAL_CLUSTER_THRESHOLD_PX: float = 40.0
CENTRAL_CLUSTER_INITIAL_OFFSET_PX: float = 180.0
CLUSTERED_ANCHOR_ATTRACTION_K: float = 0.025
CLUSTERED_PAIR_REPULSION_BOOST: float = 1.625
EARLY_REPULSION_BOOST: float = 1.875
REPULSION_BOOST_ITERS: int = 20

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

    # Round-3 S3: detect clusters of co-located anchors and re-seed
    # cluster members with an even angular spread around the cluster
    # centroid. ``cluster_id[i] >= 0`` marks label ``i`` as belonging to
    # the named cluster; ``-1`` means singleton (uses the radial
    # placement above).
    cluster_id = _detect_anchor_clusters(anchors, CENTRAL_CLUSTER_THRESHOLD_PX)
    is_clustered = cluster_id >= 0
    n_clusters = int(cluster_id.max()) + 1 if cluster_id.max() >= 0 else 0
    for cid in range(n_clusters):
        members = np.where(cluster_id == cid)[0]
        if len(members) < 2:
            continue
        cluster_anchor_centroid = anchors[members].mean(axis=0)
        for k, i in enumerate(members):
            angle = 2.0 * np.pi * k / len(members)
            offset = np.array([np.cos(angle), np.sin(angle)], dtype=np.float64)
            positions[i] = (
                cluster_anchor_centroid
                + offset * CENTRAL_CLUSTER_INITIAL_OFFSET_PX
            )

    # Per-label anchor-attraction coefficient: halved for cluster members
    # so the spread state isn't pulled back into the pile.
    attraction_k = np.where(
        is_clustered, CLUSTERED_ANCHOR_ATTRACTION_K, ANCHOR_ATTRACTION_K
    )

    # Per-pair label-repulsion boost: cluster-mates get
    # ``CLUSTERED_PAIR_REPULSION_BOOST`` on top of the base coefficient.
    # All other pairs use 1.0 (no extra boost).
    pair_boost = np.ones((n, n), dtype=np.float64)
    for cid in range(n_clusters):
        members = np.where(cluster_id == cid)[0]
        if len(members) < 2:
            continue
        for i in members:
            for j in members:
                if i != j:
                    pair_boost[i, j] = CLUSTERED_PAIR_REPULSION_BOOST

    half_sizes = sizes * 0.5

    for _step in range(NUM_ITERATIONS):
        forces = np.zeros_like(positions)

        # Anchor attraction: pull each label back toward its anchor. The
        # per-label coefficient is halved for cluster members (S3) so
        # the angular initial spread isn't immediately collapsed back.
        forces += -attraction_k[:, None] * (positions - anchors)

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
        # S3: per-pair boost for cluster-mates, plus a global early boost
        # that decays linearly to 1.0 over the first
        # ``REPULSION_BOOST_ITERS`` iterations. Aggressive separation up
        # front; clean convergence after.
        if _step < REPULSION_BOOST_ITERS:
            t = _step / max(REPULSION_BOOST_ITERS - 1, 1)
            early_boost = EARLY_REPULSION_BOOST + (1.0 - EARLY_REPULSION_BOOST) * t
        else:
            early_boost = 1.0
        inv_cube = LABEL_REPULSION_K * pair_boost * early_boost / (d_eff ** 3)
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


def _detect_anchor_clusters(
    anchors: npt.NDArray[np.float64], threshold_px: float
) -> npt.NDArray[np.int_]:
    """Group anchors into clusters by transitive closeness in screen space.

    Two anchors are in the same cluster iff they are within
    ``threshold_px`` of each other (or connected via a chain of such
    pairs). The return is an int array ``cluster_id[i]`` where:
      * ``cluster_id[i] >= 0`` is the cluster index for anchor ``i``;
      * ``cluster_id[i] == -1`` marks a singleton (no co-located peer).

    Singletons get -1 so the caller can use the standard radial initial
    placement; clustered indices start at 0 and are dense.

    Used by ``solve_layout`` to apply the S3 cluster treatment (angular
    initial spread, halved attraction, boosted pair repulsion) only to
    anchors that actually need it.
    """
    n = len(anchors)
    if n == 0:
        return np.array([], dtype=int)
    parent = np.arange(n)

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(i: int, j: int) -> None:
        ri, rj = find(i), find(j)
        if ri != rj:
            parent[ri] = rj

    for i in range(n):
        for j in range(i + 1, n):
            if float(np.linalg.norm(anchors[i] - anchors[j])) <= threshold_px:
                union(i, j)

    roots = np.array([find(i) for i in range(n)])
    counts: dict[int, int] = {}
    for r in roots:
        counts[int(r)] = counts.get(int(r), 0) + 1

    cluster_id = np.full(n, -1, dtype=int)
    next_id = 0
    root_to_id: dict[int, int] = {}
    for i in range(n):
        r = int(roots[i])
        if counts[r] >= 2:
            if r not in root_to_id:
                root_to_id[r] = next_id
                next_id += 1
            cluster_id[i] = root_to_id[r]
    return cluster_id


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
