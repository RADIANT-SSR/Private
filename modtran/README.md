# MODTRAN Staging Directory

This directory is the local staging area for RADIANT's MODTRAN work
(`docs/archive/MODTRAN_Run_Matrix_Plan.md`). It has two purposes that must
stay clearly separated:

1. **`decks/`** — real tape5 **input** decks, ready to run through an
   actual MODTRAN binary. Deterministic card-image formatting; no
   physics is computed here.
2. **`synthetic/`** — synthetic (**not real MODTRAN**) tape7 **output**
   files, for exercising the parsing/chain pipeline and scenario work
   before real MODTRAN access exists. See `synthetic/README.md` — it
   is not a substitute for real MODTRAN validation and must never be
   used to close Gap 38/39/CU-011, which need an independent reference,
   not RADIANT's own (however carefully sourced) approximation.

Real MODTRAN 6 output has passed through RADIANT's parser since the
2026-07-17 delivery, and the batch-1 up-looking / horizontal set followed
on 2026-07-26; the staged runs live tracked in git under `real_runs/` (owner decision 2026-08-02 — irreplaceable source data) with
their checksums committed at `real_runs_MANIFEST.sha256`. Nothing in this
repository fabricates a tape7 and presents it as MODTRAN-equivalent
physics; the `synthetic/` files are loudly labeled and physically
documented as a lesser tier (see below).

## What's here

- `decks/` — 125 rendered tape5 input decks, one per row of
  `docs/plans/modtran_run_matrix.csv`, plus `decks/MANIFEST.md`
  cross-referencing each deck to its run's purpose and any known
  caveats. **Not committed** — regenerate with:

  ```
  python scripts/render_modtran_decks.py
  ```

  Deck rendering is deterministic (pure card-image formatting from
  `radiant.atmosphere.modtran.render_tape5`), so there is nothing to
  preserve in git; the generator script and the CSV are canonical
  (Rule 26/27).

- `synthetic/` — 39 synthetic tape7 **outputs**, one per batch-0 run
  (blocks A–H only), built from
  real HITRAN line-by-line molecular transmittance (via RADIS) on an
  independently-built layered atmosphere, plus a simplified (not
  independent) aerosol/scattering term. **Not committed** — regenerate
  with:

  ```
  python scripts/generate_synthetic_tape7.py
  ```

  Full fidelity/independence breakdown, known physics gaps vs. real
  MODTRAN, and generation details: `synthetic/README.md`.

## What's not here (and where it goes instead)

Once a real MODTRAN binary or donated tape7s become available, run the
decks in `decks/` and route the outputs per
`docs/archive/MODTRAN_Run_Matrix_Plan.md` §7 — **not** back into this
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

- **Card 3 `ANGLE`** is written at the **H1** (sensor) convention while
  the matrix's `path_zenith_deg_radiant` is the path's **lower-endpoint**
  zenith. Down-looking (H1 above H2) the two differ by
  `ANGLE = 180° − zenith`; up-looking (H1 at or below H2) the sensor *is*
  the lower endpoint and `ANGLE = zenith` unchanged; ITYPE=1 writes the
  literal 90°. The convention was confirmed by three-way agreement
  (`render_tape5` == the matrix's hand-worked `modtran_angle_at_h1_deg`
  column == the delivered tape7 Card-3 echoes) across the delivered runs,
  K7 closing the elevated-lower-endpoint half (CU-065 resolved).
- IEMSCT=3 (solar-irradiance mode, Block E) rows have no meaningful
  `path_zenith_rad` — RADIANT's line-of-sight concept doesn't apply to
  a ground-level irradiance calculation — and render it as a 0
  placeholder.
- Any row whose `deck_builder_support` is not `current` is **not fully
  expressible** by `render_tape5`. Its deck still renders (so the rest of
  the card image is right) but needs a hand edit before it is run; the
  manifest flags it and the row's `notes` column says exactly what to
  change. Batch 2 has four such rows — see below.

See `docs/tracking/Cleanup_Backlog.md` for CU-063/064/065/066/067/068/069,
all discovered while building this staging area.

## Batch 2 — what to run (37 decks, rows M1…Q8)

Batch 2 is the deck set the archived `Geometry_Flexibility_Plan.md` close-out
deferred: it anchors the ground-to-space (SST) class, grows the up-looking
family a zenith axis, supplies the upwelling emission anchor
`RADIANT_Atmosphere.md` §3.1 is missing, makes the elevated-target
downwelling altitude-dependent, and calibrates the provisional horizon-guard
thresholds. Batch 1 (rows A1…L25) is complete; nothing here re-runs a
delivered geometry.

**Run every deck in `decks/` whose run_id starts with M, N, O, P or Q** —
37 decks. Regenerate them first with `python scripts/render_modtran_decks.py`
(they are gitignored, not committed). Every deck uses the same spectral
window as batch 1 (700–25 000 cm⁻¹ at 1.0 cm⁻¹ DV/FWHM, i.e. 0.4–14.3 µm),
so run time per deck is comparable.

| Block | Decks | What it is | Why |
|-------|-------|-----------|-----|
| **M** | M1–M8 (8) | Ground sensor up-looking, full column to space, LOS zenith 0 / 60 / 70.529 / 75.522 / 78.463 / 85 / 88 / 89.5° | The SST anchor class, on a fan spaced uniformly in **sec ζ** (1, 2, 3, 4, 5) plus three near-horizontal probes. The sec = 1.5 rung is the already-delivered H5. |
| **N** | N1–N10 (10) | Ground sensor up-looking to 1 / 3 / 5 / 10 / 20 km, at 48.2° and 60° | Gives the shipped `midlat_summer_uplooking_ladder` a **zenith axis**. Rectangular grid: 5 targets × 3 sec rungs (1.0 = the delivered K1–K5, 1.4999, 2.0). |
| **O** | O1–O5 (5) | Sensor at 1 / 5 / 10 / 10 / 100 km looking **down** at ground | The upwelling half of matched direction pairs, so the `L_path_up` missing-emission asymmetry can be *closed* rather than measured one-sided. |
| **P** | P1–P6 (6) | Up-looking at 48.2° from an **elevated** endpoint: 1 / 5 / 10 / 20 / 29 / 50 km | Makes `atm_emission_down` altitude-dependent instead of the ground-level H5 constant every elevated node carries today. |
| **Q** | Q1–Q8 (8) | Long horizontal paths at 5 km (71.4 / 150 / 319.3 / 500 km range), a refraction on/off pair, and two twilight tangent transits | Calibrates the provisional horizon-guard thresholds (Δh ≈ 100 m compute / ≈ 2 km raise) and gives the twilight `τ_sun` transit its first anchor. |

**Four Q rows need a hand edit before running** (their
`deck_builder_support` says so, and `decks/MANIFEST.md` flags them):

- **Q5** — byte-identical to `Q3.tp5` on purpose. Disable MODTRAN's ray
  bending for this run only, then run it. `Q3 − Q5` is the interior-tangent
  half of the refraction on/off pair.
- **Q6** — byte-identical to `M8.tp5` on purpose. Same: refraction off.
  `M8 − Q6` is the endpoint-minimum half.
- **Q7 / Q8** — set Card 3 `ANGLE` to `93.000` / `96.000` and `LENN` to `1`
  (long path through the tangent point). `render_tape5` cannot write an
  `ANGLE` past 90° because `AtmosphericGeometry` refuses a lower-endpoint
  zenith past 89.5°, so the deck renders `ANGLE 0.000` as a placeholder and
  the true value lives in the matrix's `modtran_angle_at_h1_deg` column.

Please **record which refraction switch you used for Q5/Q6** in
`real_runs/README.md` — RADIANT has no way to infer it from the tape7.

**Delivered 2026-08-03:** rows **P7/P8** (60/80 km elevated-endpoint downwelling) and **M9–M13** (the 900 m-site SST sec fan) landed via the owner's GitHub upload. **Q5/Q6 are now the only unrun rows** (the refraction pair — runnable only with a real ray-bending switch; the horizon-guard thresholds stay guard-banded without them).

**Owner deck audit, 2026-08-02.** The 33 rows M1–M8, N1–N10, O1–O5, P1–P6,
Q1–Q4 were audited safe and run as-is; these are the only rows the CU-224
gated half (P5), CU-181, and the sec-space axis actually need. The four
hand-edit rows are held back pending special handling:

- **Q5/Q6** — run **only** with a real ray-bending control; a byte-duplicate
  of Q3/M8 would deliver an exactly-zero refraction delta that reads as
  "refraction is negligible at the threshold". If the MODTRAN build exposes
  no such switch, skip both permanently — the horizon-guard thresholds then
  stay guard-banded per ADR-0011 decision 5 (the current documented state).
- **Q7/Q8** — MODTRAN's handling of the below-horizon sun (solar zenith
  93°/96°) in the radiance path is unverified. The anchor these runs exist
  for is **τ_sun only** (the LOS *is* the solar path; the deliverable is the
  TOT TRANS column), so the solar source function never enters the needed
  product. Probe protocol: if the IEMSCT=2 deck runs, the transmittance
  column is trustworthy regardless of the solar-source question; if MODTRAN
  rejects or mishandles it, rerun the same hand-edited geometry with
  **IEMSCT = 0** (transmittance-only) and record the mode deviation in
  `real_runs/README.md`. Sanity check: TOT TRANS nonzero, **well above**
  the M8 (89.5°) column, and Q8 above Q7 — the transits never descend
  below their tangent heights (~11.2 km Q7 / ~14.9 km Q8), so they see
  only thin high-altitude air, while M8 grazes from sea level (τ ≈ 0).
  (An earlier revision of this note had both orderings inverted; the
  2026-08-02 delivery measured VIS/MWIR/LWIR band-mean τ of
  0.156/0.390/0.550 for Q7 and 0.215/0.556/0.603 for Q8 vs
  1e-6/0.001/0.000 for M8, with the ANGLE=93/96 + LENN=1 hand-edits
  confirmed in the tape7 card echoes.)

**Where the outputs go.** Stage every delivered `.tp7` flat in
`modtran/real_runs/` named `<run_id>.tp7` (e.g. `real_runs/M1.tp7`), exactly
as batch 1 is staged — the directory is tracked in git as of 2026-08-02
(owner decision: the outputs are irreplaceable source data), so commit the
delivered files. Then regenerate the committed checksums:

```
python scripts/gen_modtran_manifest.py
python scripts/gen_modtran_manifest.py --check
```

Nothing else needs doing on delivery: the repackaging into
`data/atmospheres/` NPZ families and the promotion of the
`test_fixture`-marked runs into `tests/integration/fixtures/modtran/` are
coding tasks that run against the staged set (the `destination` column of
`docs/plans/modtran_run_matrix.csv` says which run goes where).
