# Remediation Blockers

## BLOCKER B0 — `dev_tools/geometry_gui_v2/` is entirely untracked in git

**Discovered:** 2026-04-28, before T1 branch creation.

**Symptom:**
The remediation work order in `PLAN_v2_remediation_agent.md` and the wrapping
prompt both describe Phases 0–7 of `PLAN_v2.md` as "shipped." The wrapping
prompt instructs:

> Branch: create `fix/visual-remediation` off `main` before T1.

But `git ls-files dev_tools/geometry_gui_v2/` returns nothing. `git log --all
-- dev_tools/geometry_gui_v2/` returns nothing. The directory exists in the
working tree (173 files, 1.5 MB) but is uncommitted in every branch and every
worktree (7 inspected). Phases 0–7 are *physically present on disk* but are
not *committed history* anywhere I can see.

**Why this matters:**
- The remediation premise is "build T1–T10 on top of shipped Phase 0–7." If I
  branch off `main`, the v2 baseline is a 173-file untracked blob, not a
  reviewable commit history.
- The plan asks for "one branch off `main` → one commit per task." A first
  commit on the new branch would have to be either (a) the entire 173-file
  Phase 0–7 baseline as a single squash, or (b) per-task commits that mix
  baseline lift with remediation, which violates "one task one commit."
- I cannot tell which files in the working tree are "Phase 0–7 ship" versus
  uncommitted in-progress work that someone else is mid-edit on. Several
  other untracked items in the same `git status` (PLAN_v2.md in the *v1*
  geometry_gui directory, an Excel `.~lock` file, audit_2026/) suggest a
  general uncommitted-work situation.

**What I tried:**
1. `git ls-files dev_tools/geometry_gui_v2/` → empty.
2. `git log --all --oneline -- dev_tools/geometry_gui_v2/` → empty.
3. Inspected each of the 7 locked worktrees (`worktree-agent-*`); none of
   them contain v2 files in their commit trees.
4. Verified the current branch (`chore/cu-007-mwir-t3mixed-routing`) is
   ahead of `main` by 3 commits, none of which touch v2.

**What I need from the human reviewer to unblock:**

Pick one of:

1. **Commit the existing Phase 0–7 baseline first.** I create
   `fix/visual-remediation` off `main`, commit the entire untracked v2
   tree as a single "Phase 0–7 baseline lift" commit, then start T1 on top.
   Risk: I cannot distinguish baseline files from in-progress work that
   may be sitting in the working tree from someone else's session.

2. **Point me to the actual baseline branch / commit.** If Phase 0–7 was
   committed somewhere I cannot see (a remote, a stashed branch, a
   different repo), tell me where, and I will branch off that point.

3. **Confirm that the untracked tree IS the baseline,** and authorize a
   single bulk-commit of the 173 files as the starting point.

**I have not switched branches, created the remediation branch, or modified
anything.** Per the spec ("Do not silently work around the spec"), I'm
stopping here for direction before T1.

**Resolution (2026-04-29):** Reviewer authorised path (3) — the untracked
tree IS the baseline. Bulk-committed as `a2fb700` ("Phase 0–7 baseline
lift"); T1–T10 followed as one-task-one-commit. See
[REMEDIATION_REPORT.md](REMEDIATION_REPORT.md) for the full landing
sequence.

---

## BLOCKER R9-B1 — `extended_default`: pixel-cell footprint missing

**Discovered:** 2026-04-29, R9 visual verification.

**View:** `extended_default` (`SceneState.default()` with
`regime_override="extended"`).

**Check:** Round-2 plan §10 step 4, special-case requirement —
*"the pixel-cell footprint must be visible as a translucent square
on the ground, not as an opaque orange block hiding the geometry
beneath."*

**Symptom:**
[`tests/golden/round2/extended_default.png`](tests/golden/round2/extended_default.png)
is geometrically identical to `sphere_default.png` apart from the
target label's regime tag changing from `(sub_pixel)` to
`(extended)`. There is **no translucent square primitive** drawn on
the ground at the pixel-cell footprint location. The viewer cannot
see the pixel-cell that defines the extended-scene regime.

**Root cause (code-read):**
1. `grep -r pixel_cell dev_tools/geometry_gui_v2/scene/` — no module
   emits a ground-plane translucent square keyed off
   `regime_override == "extended"` or off the canonical pixel-cell
   geometry.
2. The diet pass (commit `19e4077`) shipped without ever wiring a
   pixel-cell footprint primitive; round 1 did not include one
   either. The plan's special-case check assumes a primitive that
   was never built.

**What I tried:**
- Re-rendered with `regime_override="extended"` to confirm — no
  change beyond the regime tag.
- Searched for any `pixel_cell`, `extended_footprint`, `cell_box`
  primitive under `scene/` — none exist.

**Why this is filed as a blocker rather than fixed in R9:**
Building a new translucent ground-plane primitive that maps to the
canonical pixel-cell geometry, gates on `regime_override`, and ships
with its own Phase-1 golden is a Rule-19 standalone task, not a
visual-remediation polish. R9's mandate is "verify the existing
work"; building net-new primitives is out of scope.

**Suggested fix:**
Open a CU under `docs/Cleanup_Backlog.md` titled
*"Add `scene/extended_pixel_cell.py` ground-plane translucent
footprint primitive"*. Effort: ~2 hours. Category: B (core
abstraction — needs its own dimensional-audit + Phase-1 golden).

---

## BLOCKER R9-B2 — `point_source_default`: distinct marker missing

**Discovered:** 2026-04-29, R9 visual verification.

**View:** `point_source_default` (`SceneState.default()` with
`regime_override="point_source"`).

**Check:** Round-2 plan §10 step 4, special-case requirement —
*"the point-source marker must be visible and clearly distinguished
from the regular sub-pixel target indicator."*

**Symptom:**
[`tests/golden/round2/point_source_default.png`](tests/golden/round2/point_source_default.png)
is geometrically identical to `sphere_default.png` apart from the
target label's regime tag changing from `(sub_pixel)` to
`(point_source)`. There is **no distinct marker primitive** —
the same teal sphere is drawn at the same target location.
A user comparing the two views would not be able to tell they
represent different radiometric regimes from the geometry alone.

**Root cause (code-read):**
1. `grep -r point_source dev_tools/geometry_gui_v2/scene/` — no
   module emits a marker primitive keyed off
   `regime_override == "point_source"`.
2. Same situation as R9-B1: the special-case check assumes a
   primitive that was never built.

**What I tried:**
- Re-rendered with `regime_override="point_source"` — no change
  beyond the regime tag.
- Searched for any `point_source_marker`, `pt_marker`, `pin_glyph`
  primitive under `scene/` — none exist.

**Why this is filed as a blocker rather than fixed in R9:**
Same Rule-19 reasoning as R9-B1 — adding a distinct marker
primitive (e.g., a small cross or pin glyph at the target location
that replaces or augments the sphere when regime is
`point_source`) is its own standalone task with its own golden.

**Suggested fix:**
Open a CU under `docs/Cleanup_Backlog.md` titled *"Add
`scene/point_source_marker.py` distinct point-source target
indicator"*. Effort: ~1 hour. Category: B.

---

## BLOCKER R9-B3 — Interactive verification gated by CU-042

**Discovered:** 2026-04-29, R9 plan §10 step 6.

**Check:** Round-2 plan §10 step 6, interactive run — confirm
default scene loads to iso camera, slider drag updates 3D scene in
real time, view-cube clicks navigate, frame chip updates, no Qt
warnings.

**Symptom:**
The interactive run is gated by **CU-042** (QtInteractor offscreen-GL
segfault). The 8 skipped tests in the v2 suite are precisely the
QtInteractor paths protected behind CU-042's skip marker. Pixel
verification of:
- view-cube widget (top-right)
- world-axis gnomon (bottom-left)
- right-dock readouts panel (4 sections, eye-icon toggles)
- left-dock parameter panel (5 sections, 19 sliders + 19 spinboxes,
  shape dropdown, regime + background radios)
- frame-indicator chip (top-left)

cannot be obtained on this machine without CU-042 closure.

**Mitigation (what we have):**
The wiring contract for every Qt-shell surface is verified by unit
tests:
- `tests/test_view_cube.py` (T2)
- `tests/test_world_axes_gnomon.py` (T4)
- `tests/test_readouts_panel.py` (15 tests, R7)
- `tests/test_parameters_panel.py` (15 tests, R8)
- `tests/test_scene_phase4.py` (label deconfliction)

The 16 ms slider-drag debounce, signal emission semantics, and
`set_state` no-feedback-loop guarantees are all unit-tested.
What remains unverified is **pixel layout**: the interactor-bound
widgets render correctly only at runtime under a real Qt event loop,
which CU-042 prevents.

**Why this is filed as a blocker rather than fixed in R9:**
CU-042 is an upstream environment issue (QtInteractor + offscreen
GL on this machine); it is not a defect introduced by the
remediation. The plan acknowledges this risk in its preamble.

**Suggested fix:**
Resolve CU-042 (probably by switching to a software GL backend
under offscreen, or by capturing screenshots from the developer's
local machine which has a real display attached). Re-run the
interactive checklist once CU-042 is closed.
