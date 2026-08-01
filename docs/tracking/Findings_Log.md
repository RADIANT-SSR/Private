# RADIANT Findings Log

**Status:** Active — created 2026-07-31 (owner-ratified two-tier tracking strategy).

The sub-CU tier of Rule 21's intake. A finding lands here when it fails all four CU
intake tests (results-affecting, owner-gated, blocking, workflow-visible) but must
still be written down before its discovering PR merges — no silent debt, no ceremony
for trivia.

**Format** — one appended line per finding, newest last:

```
- YYYY-MM-DD `path:line` — one-sentence symptom. (origin: task or CU/commit)
```

**Exits** (exactly three):
1. **Promoted** — someone decides to work it: mint a CU citing this line, strike the line in the promoting commit.
2. **Struck** — fixed in passing: delete the line in the same PR that fixes it.
3. **Expired** — a quarterly sweep deletes lines nobody promoted. Deletion is legitimate: the intake test already ruled these non-critical.

Lines carry no IDs and need no reservation push (Rule 21 tier 2). Keep each line
self-contained — a reader must understand the finding without opening anything else.

---

## Log

- 2026-07-31 `src/radiant/gui/widgets/matplotlib_canvas.py` — one shiboken `RuntimeError: FigureCanvasQTAgg already deleted` printed to stderr per full GUI run (repro: `test_source_instrument.py::TestReflectiveTab::test_solar_rows_do_not_open_an_editor`). **Not** the queued-idle-draw race CU-313 assumed: this matplotlib's `_draw_idle` already guards with `_isdeleted(self)`, and clearing `_draw_pending` at both discard and `destroyed` was measured not to silence it (2026-07-31 attempt, discarded as redundant). The traceback shows the C++ object valid at the `_isdeleted` check, gone by `self.update()` after the Agg render inside the same `_draw_idle` call — the deletion lands *mid-draw*, mechanism unidentified. matplotlib's own `except: print_exc` is what prints it; the draw is on a dying canvas so nothing is lost. Next attempt should start by finding what destroys the canvas during an in-progress synchronous draw. (origin: demoted from CU-313; sharpened 2026-07-31)
- 2026-07-31 `src/radiant/atmosphere/interpolated.py` — the shipped up-looking ladder is rendered at a single solar zenith (30°), so every query at any other `solar_zenith_rad` emits the CU-167 "is IGNORED" `UserWarning` twice per run, training operators to ignore it; de-duplicate per run, or retire when a multi-solar-zenith family ships (MODTRAN batch 2). (origin: demoted from CU-307)
- 2026-07-31 `src/radiant/geometry/stage.py` — a config with a target below its own terrain (`site_elevation_m = 900`, `target_altitude_m = 0`) passes GeometryStage silently and raises only inside `cn2()` when an HV profile is selected; a GeometryStage consistency check (both endpoints ≥ site elevation) would catch it at the right stage with the right framing (Rule 16). (origin: demoted from CU-303)
- 2026-07-31 `scenarios/01…1.3/outputs/` (fig2, fig3), `scenarios/03…3.2/outputs/` (3 figs), `scenarios/03…3.4/outputs/` (3 figs) — 8 committed figures are not byte-reproducible from their own unmodified generators (suspected hash-dependent series/legend ordering, same family as the fixed CU-292); diagnose the ordering, fix at source, regenerate once with cause. (origin: demoted from CU-291)
- 2026-07-31 `CLAUDE.md` (gate battery) — `scenarios/` sits outside both the lint and pytest gate scopes and nothing records whether that is a decision or an oversight (822 ruff findings there, all style, all parse clean); decide and write one sentence next to the gate battery — if it ever joins, it needs per-file-ignores for the narrative-script idiom first. (origin: demoted from CU-278)
- 2026-07-31 `src/radiant/gui/widgets/scripting_console.py:624` — every figure plotted from the scripting console is retained in `self._figure_windows` forever, even after the analyst closes its window, so hours-long sessions grow the live widget tree unbounded and the theme toggle re-polishes dead figures; decide closed-figure semantics (gone vs reopenable), then prune on close (`WA_DeleteOnClose` + `destroyed` hook) or cap the set. (origin: demoted from CU-285)
- 2026-07-31 `src/radiant/gui/widgets/spectral_integration_inputs_form.py` — `integration_time_s` is presented on the Spectral-Integration view under an *Acquisition* heading; relocate when a cross-stage acquisition grouping (TDI/binning timing) is ever designed. Presentation only, no schema change. (origin: demoted from CU-137)
- 2026-07-31 `src/radiant/gui/viewer/schematic_view.py::_arc_label_text` — the arc value label hardcodes `"°"` instead of sourcing the unit from the output key; provably correct today (the four-entry arc catalog is angle-only) — revisit only if a non-angle annotatable output is added (with CU-118 / Gap 87). (origin: demoted from CU-126)
- 2026-07-31 `src/radiant/geometry/stage.py` (no attitude output) — platform/sensor attitude (`observer_{yaw,pitch,roll}_rad`) has no stage owner; ADR-0006 §4's "GeometryStage output vs viewer-local input" decision stays open with no v1 consumer. Decide at the first task that actually needs sensor/platform attitude. (origin: demoted from CU-122 half (ii); half (i), the broken `dev_tools/geometry_gui_v2` shell, was already resolved by deletion 2026-07-19)
- 2026-08-01 `modtran/README.md` ("What's not here") — the NPZ-library coverage sentence still counts "25 of the 39 runs", batch-0 arithmetic that predates the 88-row (now 125-row) matrix; it is explicitly scoped to the archived plan §7.2 so it was left as-is when the rest of the README was refreshed for batch 2. Reword against the current matrix at the next README touch. (origin: P0 batch-2 deck authoring, branch modtran/batch2-decks)
- 2026-08-01 `docs/architecture/RADIANT_Atmosphere.md:797` — the three-way ANGLE-agreement claim says it covers "every delivered row of the 88-row matrix"; still true (the matrix is 125 rows but only 88 are delivered), and it goes stale the moment batch 2 (rows M1–Q8) is delivered. Re-verify and reword at batch-2 ingestion. (origin: P0 batch-2 deck authoring, branch modtran/batch2-decks)
