# MODTRAN Staging Directory

This directory is the local staging area for RADIANT's MODTRAN validation
effort (`docs/plans/MODTRAN_Run_Matrix_Plan.md`). It holds **input decks
only**. RADIANT has never had real MODTRAN output pass through its
parser — every `.tp7` used in tests today is a hand-authored synthetic
fixture — so nothing in this repository fabricates a tape7 (MODTRAN's
radiative-transfer *output*). Doing so would defeat the entire point of
the plan: validating `SimpleAtmosphere` against an *independent*
reference. A tape7 synthesized by RADIANT's own atmospheric-physics
knowledge is not independent, no matter how physically motivated —
it would just be circular validation dressed up as external truth.

## What's here

- `decks/` — 39 rendered tape5 input decks, one per row of
  `docs/plans/modtran_run_matrix.csv`, plus `decks/MANIFEST.md`
  cross-referencing each deck to its run's purpose and any known
  caveats (e.g. CU-065's unverified Card 3 ANGLE convention).
  **Not committed** — regenerate with:

  ```
  python scripts/render_modtran_decks.py
  ```

  Deck rendering is deterministic (pure card-image formatting from
  `radiant.atmosphere.modtran.render_tape5`), so there is nothing to
  preserve in git; the generator script and the CSV are canonical
  (Rule 26/27).

## What's not here (and where it goes instead)

Once a real MODTRAN binary or donated tape7s become available, run the
decks in `decks/` and route the outputs per
`docs/plans/MODTRAN_Run_Matrix_Plan.md` §7 — **not** back into this
directory:

- **`tests/integration/fixtures/modtran/`** — the ~10 committed golden
  tape7s (A1, A3, B2, C1, C3, C7, D2, D5, E1, E2) that
  `Tape7Reader`/Gap-39/CU-011/Gap-38 regression tests assert against.
  Each entry needs its tape5, its tape7, and a `MANIFEST.md` naming the
  generating MODTRAN version (Rule 26).
- **`data/atmospheres/`** — the repackaged `InterpolatedAtmosphere` NPZ
  runtime library (25 of the 39 runs; see the plan §7.2 for which).

## Known deck-builder caveats

`decks/MANIFEST.md` (regenerated each run) flags, per deck:

- **CU-065** (deferred): Card 3's `ANGLE` field has not been verified
  against the real MODTRAN H1-relative zenith convention. Every deck
  in this directory currently writes RADIANT's own line-of-sight
  zenith directly; the matrix's `modtran_angle_at_h1_deg` column
  records what the correct value is believed to be if it differs.
  Verify against the MODTRAN manual before trusting any rendered
  `ANGLE` field.
- IEMSCT=3 (solar-irradiance mode, Block E) rows have no meaningful
  `path_zenith_rad` — RADIANT's line-of-sight concept doesn't apply to
  a ground-level irradiance calculation — and render it as a 0
  placeholder.

See `docs/tracking/Cleanup_Backlog.md` for CU-063/064/065/066/067/068/069,
all discovered while building this staging area.
