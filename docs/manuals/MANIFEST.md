# Manual-Suite PDFs — Provenance Manifest

Committed typeset builds of the four-volume RADIANT manual suite, kept in the
repository by owner instruction (2026-09-18) so the current manuals are readable
directly from the remote without a local TeX toolchain. Rule 26 record: these
are generated artifacts — regenerated wholesale, never hand-edited; a rebuild
that changes them replaces all four files and this manifest in one commit.

**Generator**: `python scripts/build_manual.py --all` (XeLaTeX; inputs are the
bound sources under `docs/theory/` and `docs/guides/` plus the build assets
under `scripts/manual_assets/`).
**Source commit**: `84dfc8da` (post CU-379 defocus-coefficient fix, 2026-09-21; Volumes I and IV rebuilt, II and III unchanged since the CU-359 batch).

| File | Volume | Pages | SHA-256 |
|---|---|---|---|
| `radiant_theory.pdf` | I — Theory Manual | 95 | `06dfe345feb20554d39d339b4c5004daccec8a001509433bb2182b9ea1c65775` |
| `radiant_users_guide.pdf` | II — User's Guide | 102 | `20c90cf2f481b5f5f6b744a31dfd80523e6561d9394424648af35b5b38e0b855` |
| `radiant_tech_ref.pdf` | III — Technical Reference | 160 | `af2971bee6cd21fbc4522c50c35a13fc830bcf012adb8972e129f5629675e25e` |
| `radiant_examples.pdf` | IV — Worked Examples & Validation | 181 | `0f575b4492af35e4a1145f9f2587a604847ab6f0bf759728641af35d89d117d3` |

Title pages print the version with a git-describe parenthetical when the build
tree sits past the release tag; a build on the tagged commit prints the bare
version.
