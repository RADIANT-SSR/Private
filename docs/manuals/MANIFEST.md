# Manual-Suite PDFs — Provenance Manifest

Committed typeset builds of the four-volume RADIANT manual suite, kept in the
repository by owner instruction (2026-09-18) so the current manuals are readable
directly from the remote without a local TeX toolchain. Rule 26 record: these
are generated artifacts — regenerated wholesale, never hand-edited; a rebuild
that changes them replaces all four files and this manifest in one commit.

**Generator**: `python scripts/build_manual.py --all` (XeLaTeX; inputs are the
bound sources under `docs/theory/` and `docs/guides/` plus the build assets
under `scripts/manual_assets/`).
**Source commit**: `790c1976` (post GUI polish batch A and its figure recapture, 2026-09-20).

| File | Volume | Pages | SHA-256 |
|---|---|---|---|
| `radiant_theory.pdf` | I — Theory Manual | 86 | `d101ee3d9ebde993cb0a905f56437624da74fbd54bb6ddfc51869f6f0c880811` |
| `radiant_users_guide.pdf` | II — User's Guide | 102 | `434b0d65a48801209dab9866304d68bc7ddfd5474dc1a35ecb7ea588367b2073` |
| `radiant_tech_ref.pdf` | III — Technical Reference | 160 | `a7c7e17f81ca270c312789a921d6e1ffbef7acbb70222072ebf8c152a61ca79d` |
| `radiant_examples.pdf` | IV — Worked Examples & Validation | 177 | `12c1fade6e0d54c66ce92987299645cb4b3fb2d22e70db9cabab20724fe5de1a` |

Title pages print the version with a git-describe parenthetical when the build
tree sits past the release tag; a build on the tagged commit prints the bare
version.
