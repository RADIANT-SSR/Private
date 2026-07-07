# Contributing to RADIANT Geometry

This module is the visual-design prototype for the production RADIANT
GUI's geometry tab. Three conventions matter most; the rest is in
[ARCHITECTURE.md](ARCHITECTURE.md) and the parent
[../../CLAUDE.md](../../CLAUDE.md).

## Rule 19 — One computation, one module

Each distinct primitive (vector, arc, glyph, shape) gets its own file
under `scene/<kind>/`. **Do not** bundle two primitives into one module
because they share a render call. The v1 audit found that "convenience"
bundling produces opaque modules where adding a sixth shape silently
breaks the second one.

Acceptable bundling:

- Tightly coupled helpers that share private state (e.g. the great-arc
  + tip-cone helper in `scene/arcs/_arc.py`).
- Pure constants (e.g. all Tier-1 → Tier-6 colors in `scene/style.py`).

Not acceptable:

- A `vectors.py` module that draws boresight + sun ray + surface normal
  in one file because they "all use add_vector_with_arrow."
- A `dialogs.py` module hosting Settings + About + Shortcuts in one
  file. Each dialog is its own concern; each goes in
  `app/dialogs/<dialog>.py`.

When in doubt: if a future contributor would search for the file by
the primitive name (`grep -l boresight scene/`), the name should be
`boresight.py`, not `vectors.py`.

## C7 — Scene library is Qt-free

The `scene/` package imports **nothing** from Qt. Not PySide6, not
PyQt5, not qtpy. This is enforced by
`tests/test_scene_imports_without_qt.py`; if you add a Qt import
anywhere under `scene/` the test fails.

The reason: decision D5 (lift `scene/` into `radiant.gui.scene` later)
and decision D6 / CU-033 (Trame web shell as a future option) both
depend on the scene library being a renderer-agnostic PyVista layer.

If you find yourself wanting `QSize` or `QColor` in a scene module,
you're in the wrong layer — that logic belongs in `app/`.

## Golden screenshots — review protocol

A test under `tests/test_scene_goldens_phase{N}.py` compares the
rendered output against a PNG pinned in `tests/golden_phase{N}/`. When
a code change moves the goldens, **do not** simply re-lock without
review:

1. Run the failing golden test with `--mpl-generate-path` (or PyVista's
   `regression_callback=`) to produce the candidate PNG.
2. Open the candidate next to the pinned PNG. Diff visually. Confirm
   the change is the one your code intended (not an off-by-one in label
   placement or a stylesheet reflow).
3. Mention the visual delta in the commit message: "Phase 4 labels
   shift 12 px right because the leader-line solver now repels labels
   from the viewport edge."
4. Re-lock the goldens in the same PR as the code change.

The Phase 6 theme switch invalidates every previously-pinned golden;
that re-lock is deferred under CU-042 because the local dev machine
cannot run the headless screenshot harness (`QtInteractor.__init__`
segfaults on offscreen GL). CI work in Phase 7 step 5 unblocks this.

## CU discipline (Rule 21 / 22 from CLAUDE.md)

Every latent issue you uncover while shipping a feature gets a CU
entry in [../../docs/tracking/Cleanup_Backlog.md](../../docs/tracking/Cleanup_Backlog.md)
**before your PR merges**. No silently-deferred debt. Required fields:
discovered, status, file, symptom, why-it-still-matters, suggested fix
+ category + effort.

A CU is closed only by a moved entry in the **Resolved** section with
the closing commit SHA. No phantom closure.

## Pure-function-first

The view-model (`app/view_model.py`), the layout solver
(`scene/labels/layout.py`), the canonical-view registry
(`scene/camera_views.py`), the highlight registry
(`scene/highlight.py`), and the status-bar formatter
(`app/status_bar_text.py`) are all pure functions you can unit-test
without a display. Keep new logic in this style — Qt belongs at the
edges.

## Running the test suite

```bash
# Pure-Python + offscreen-Qt panel tests (the default 229 tests):
pytest dev_tools/geometry_gui_v2/tests/

# Plus the full QtInteractor-backed window tests (8 additional):
RADIANT_GUI_FULL_WINDOW_TESTS=1 pytest dev_tools/geometry_gui_v2/tests/
```

The default 229-test pass is the gating bar for any PR. The full
window tests gate behind the env flag because offscreen GL contexts
segfault during `QtInteractor.__init__` on some platforms (notably
macOS without a virtual framebuffer).
