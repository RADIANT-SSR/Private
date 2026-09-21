# Manual-Suite PDFs — Provenance Manifest

Committed typeset builds of the four-volume RADIANT manual suite, kept in the
repository by owner instruction (2026-09-18) so the current manuals are readable
directly from the remote without a local TeX toolchain. Rule 26 record: these
are generated artifacts — regenerated wholesale, never hand-edited; a rebuild
that changes them replaces all four files and this manifest in one commit.

**Generator**: `python scripts/build_manual.py --all` (XeLaTeX; inputs are the
bound sources under `docs/theory/` and `docs/guides/` plus the build assets
under `scripts/manual_assets/`).
**Source commit**: `d146a4c4` (post usability-audit fix batches 1–5 and the CU-371 figure recapture, 2026-09-20; the examples volume also carries the MTF-budget caption edit committed with these files).

| File | Volume | Pages | SHA-256 |
|---|---|---|---|
| `radiant_theory.pdf` | I — Theory Manual | 86 | `79ed7c299e7605f42863fd5fbcf7f0e2a995271b91f187bce7d7b03f039c522c` |
| `radiant_users_guide.pdf` | II — User's Guide | 102 | `c6d74eb1ec30fef6465c27477023ba995f2c43406b19917cb5633186980cb850` |
| `radiant_tech_ref.pdf` | III — Technical Reference | 160 | `a21740341193d60b860382acf72c742c6ccf66378dba0141e9b01dd13e2a944c` |
| `radiant_examples.pdf` | IV — Worked Examples & Validation | 177 | `ee540d39ea6068a8079817b073eba09c878982977cf498ed045230b24f7e63c7` |

Title pages print the version with a git-describe parenthetical when the build
tree sits past the release tag; a build on the tagged commit prints the bare
version.
