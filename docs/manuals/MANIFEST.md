# Manual-Suite PDFs — Provenance Manifest

Committed typeset builds of the four-volume RADIANT manual suite, kept in the
repository by owner instruction (2026-09-18) so the current manuals are readable
directly from the remote without a local TeX toolchain. Rule 26 record: these
are generated artifacts — regenerated wholesale, never hand-edited; a rebuild
that changes them replaces all four files and this manifest in one commit.

**Generator**: `python scripts/build_manual.py --all` (XeLaTeX; inputs are the
bound sources under `docs/theory/` and `docs/guides/` plus the build assets
under `scripts/manual_assets/`).
**Source commit**: `170ee948` (post CU-370 editorial fix campaign, 2026-09-18).

| File | Volume | Pages | SHA-256 |
|---|---|---|---|
| `radiant_theory.pdf` | I — Theory Manual | 86 | `b67f4416e02df7efd39716fc70ba5d22eec0977a45953c04d17d7d2bed235f90` |
| `radiant_users_guide.pdf` | II — User's Guide | 100 | `93fc4486802c20201e229b9b4bd08ff9a656912855963c15b3446642c36ee1c5` |
| `radiant_tech_ref.pdf` | III — Technical Reference | 159 | `c1b462cdd48af87acc78756d7e6d5be475742bc4382029412424a5e5613641c7` |
| `radiant_examples.pdf` | IV — Worked Examples & Validation | 173 | `e2e6ec78ef8f8c228c05bfa4095f95283bdaa081922429a812aabc949e717b5f` |

Title pages print the version with a git-describe parenthetical when the build
tree sits past the release tag; a build on the tagged commit prints the bare
version.
