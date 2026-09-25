# Manual-Suite PDFs — Provenance Manifest

Committed typeset builds of the four-volume RADIANT manual suite, kept in the
repository by owner instruction (2026-09-18) so the current manuals are readable
directly from the remote without a local TeX toolchain. Rule 26 record: these
are generated artifacts — regenerated wholesale, never hand-edited; a rebuild
that changes them replaces all four files and this manifest in one commit.

**Generator**: `python scripts/build_manual.py --all` (XeLaTeX; inputs are the
bound sources under `docs/theory/` and `docs/guides/` plus the build assets
under `scripts/manual_assets/`).
**Source commit**: `5addc206` (tag `v0.3.0`, 2026-09-25).

| File | Volume | Pages | SHA-256 |
|---|---|---|---|
| `radiant_theory.pdf` | I — Theory Manual | 96 | `a19ec7ca4d58bed849b96366a94f37d97475517c0c53fbb45556e8ebc3e1a64d` |
| `radiant_users_guide.pdf` | II — User's Guide | 102 | `28b933e86f03188bfaed49c5830ac0be9f4ba0787d59eaf6d10316def1276f1a` |
| `radiant_tech_ref.pdf` | III — Technical Reference | 160 | `7a0382eb6b2b2a3cc8dcecb72516bbc8cd5f2ec93e4fa0b4444682b9600384b8` |
| `radiant_examples.pdf` | IV — Worked Examples & Validation | 180 | `432cadc3a337eeb6951a1e4c630a1464a9de5f7e94aad5c4ac82ab9fd32fba9c` |

Title pages print the version with a git-describe parenthetical when the build
tree sits past the release tag; a build on the tagged commit prints the bare
version.
