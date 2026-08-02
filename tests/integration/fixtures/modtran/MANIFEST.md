# Promoted MODTRAN Test Fixtures — Manifest

**Status:** Active

Rows of `docs/plans/modtran_run_matrix.csv` whose `destination` column reads
`test_fixture + shipped_library` are *promoted*: besides feeding the shipped
atmosphere library, their full-resolution MODTRAN output is pinned by a
parse-level anchor test, so a parser change, a re-staging accident, or a silent
data swap fails loud rather than moving a library band mean by a fraction a
golden might tolerate.

## Where the bytes live

`modtran/real_runs/<run>.tp7` — **tracked in git** since the owner's 2026-08-02
decision (commit `c2587fd`: the delivered MODTRAN output is irreplaceable source
data). Integrity is carried by `modtran/real_runs_MANIFEST.sha256`, verified by
`tests/integration/test_modtran_manifest.py`.

Copies are deliberately **not** made into this directory. The promotion
convention was written when `modtran/real_runs/` was gitignored and a committed
subset was the only way to give CI real data (run-matrix plan §7.1); tracking the
delivery in git satisfies that purpose directly, and a second copy of five 4.3 MB
tape7s would be 21 MB of duplicated committed data with two sources of truth —
Rules 26 and 27 both forbid it. This manifest is therefore the promotion record;
the anchor test is the promotion's teeth.

## Promoted runs

| Run | Geometry | Direction | SHA-256 (prefix) | Anchor test |
|-----|----------|-----------|------------------|-------------|
| `M1` | 0 → 100 km, LOS zenith 0° (sec 1.0), midlat_summer | up | `b9654147…` | `test_batch2_fixture_anchors.py` |
| `N4` | 0 → 10 km, LOS zenith 48.2° (sec 1.4999), midlat_summer | up | `885e285d…` | `test_batch2_fixture_anchors.py` |
| `N9` | 0 → 10 km, LOS zenith 60° (sec 2.0), midlat_summer | up | `5d2d824b…` | `test_batch2_fixture_anchors.py` |
| `O1` | 1 km → 0, nadir (Card-3 ANGLE 180°), midlat_summer | down | `6b0bbbb7…` | `test_batch2_fixture_anchors.py` |
| `P1` | 1 → 100 km, LOS zenith 48.2°, midlat_summer | up | `e597a21b…` | `test_batch2_fixture_anchors.py` |

All five are batch-2 rows (delivered 2026-08-02), MODTRAN 6, `ITYPE=2`,
`IEMSCT=2`, `IMULT=1`, 700–25000 cm⁻¹ at 1 cm⁻¹ / FWHM 1 cm⁻¹, `SURREF=0`,
solar zenith 30° / azimuth 0°.

## Input decks

The rendered tape5 for each row is regenerated deterministically — it is pure
card-image formatting, so there is nothing to preserve in git (Rule 26):

```
python scripts/render_modtran_decks.py
```

`tests/integration/test_uplooking_horizontal_anchors.py` re-renders each row's
deck from the matrix and asserts it reproduces the delivered Card-3 echo, which
is the deck's real committed contract.
