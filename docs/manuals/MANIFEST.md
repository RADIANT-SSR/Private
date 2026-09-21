# Manual-Suite PDFs — Provenance Manifest

Committed typeset builds of the four-volume RADIANT manual suite, kept in the
repository by owner instruction (2026-09-18) so the current manuals are readable
directly from the remote without a local TeX toolchain. Rule 26 record: these
are generated artifacts — regenerated wholesale, never hand-edited; a rebuild
that changes them replaces all four files and this manifest in one commit.

**Generator**: `python scripts/build_manual.py --all` (XeLaTeX; inputs are the
bound sources under `docs/theory/` and `docs/guides/` plus the build assets
under `scripts/manual_assets/`).
**Source commit**: `bd977ae3` (tag `v0.2.0`, 2026-09-21).

| File | Volume | Pages | SHA-256 |
|---|---|---|---|
| `radiant_theory.pdf` | I — Theory Manual | 86 | `1320f01cb6aca46cbdce639c6ee49c1ab84632f493a16ec52e4d140043ded921` |
| `radiant_users_guide.pdf` | II — User's Guide | 102 | `965e5e8a05ae777b0e70933a141ace6512363ef755f81703bb1cc30a4f5b6402` |
| `radiant_tech_ref.pdf` | III — Technical Reference | 160 | `dbb9099f9b8dafcdd8a2dd5bafa5e78fad29d6d1931abc3c41aa541501b09cd9` |
| `radiant_examples.pdf` | IV — Worked Examples & Validation | 181 | `a35bf3d18f1242e71097b9ffb7c70274ccb4cc97f268dcd2b3fd1e09e2396f64` |

Title pages print the version with a git-describe parenthetical when the build
tree sits past the release tag; a build on the tagged commit prints the bare
version.
