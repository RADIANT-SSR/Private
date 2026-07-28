# Series 10 — Direction-General Validation Scenarios

Validation scenarios for the **direction-general viewing geometry** delivered by
Geometry-Flexibility Phases 1–4 (`docs/adr/0011-generalized-viewing-geometry.md`,
`docs/plans/Geometry_Flexibility_Plan.md` §4 Phase 5).

Every earlier series (01–09) is a *space-to-ground* or *air-to-ground*
down-looking scene — the only geometry RADIANT accepted before ADR-0011. This
series exercises the eight scene classes that ADR-0011 opened up, one scenario
per priority cell of the observer × target grid, and validates the surfaces that
came with them:

- derived `scene_class` and its optional `geometry.scene_class` assertion
  (ADR-0011 decision 8);
- symmetric viewing-triangle solutions with $\theta_o \in [0, \pi]$
  (decision 2), including the level (equal-altitude) central-angle solution
  that subsumed the collocated carve-out (guardrail G4);
- segment-composed, direction-aware path products (decision 3) and the
  LOS-termination background selection;
- the horizon guard's two topologies and three verdicts (decision 6);
- scene-class-conditioned metric relevance as **data** (guardrail G3);
- target kinematics through both Gap 111 doors;
- the Phase-4 GUI surfaces — scene-class chip, schematic composition, θ_o /
  ζ_low arcs, Δh sag pill.

Each scenario also carries a **cross-model anchor** against the owner-run
MODTRAN 6 batch-1 up-looking / horizontal decks
(`docs/plans/modtran_run_matrix.csv`, runs `K1`–`K7` and `L1`–`L25`), so the new
path products are measured against a reference rather than merely exercised.

Folder layout, output policy, and the mandatory
`walkthrough.md` / `gaps.md` / `gui_workflow.md` trio are the same as every other
series — see `scenarios/README.md` and `docs/guides/scenario_testing.md`.

| Scenario | Scene class | Grid cell | What it validates |
|---|---|---|---|
| `10.2_air_to_air_level_irst` | `air_to_air` | E5 | Level arm at 10 km, MWIR IRST, 25–100 km range sweep: level-arm geometry, the horizon guard's clean→warn crossover, target kinematics (Gap 111) both doors, metric-relevance flip, anchored against MODTRAN L16–L20 |
