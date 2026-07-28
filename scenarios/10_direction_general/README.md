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
| `10.1_ground_to_air_mwir_detection` | `ground_to_air` | E2 | Ground MWIR camera, up-looking 0–60° ζ_low ladder to a 10 km UAS: sky background behind the target, point-source regime boundary, full-chain detection walk, Rule-4 silence, anchored against MODTRAN K4/K6 |
| `10.2_air_to_air_level_irst` | `air_to_air` | E5 | Level arm at 10 km, MWIR IRST, 25–100 km range sweep: level-arm geometry, the horizon guard's clean→warn crossover, target kinematics (Gap 111) both doors, metric-relevance flip, anchored against MODTRAN L16–L20 |
| `10.3_ground_to_space_sst_visible` | `ground_to_space` | E3 | 1 m visible SST telescope, full up-looking column: HV-5/7 turbulence (seeing- vs diffraction-limited), GF-9 terminator shadow height, intensity-door point source; MODTRAN anchor deferred to owner batch 2 (vacuum identity + published-extinction cross-checks instead — the latter root-caused the Rayleigh-coefficient defect) |
| `10.4_leo_to_geo_exo` | `space_to_space` | up-looking exo | LEO→GEO SDA at θ_o = π exactly: vacuum identities bitwise (τ = 1, L_path = 0), slant = h_GEO − h_LEO exact, relative kinematics LEO vs GEO, detection range on a vacuum path |
