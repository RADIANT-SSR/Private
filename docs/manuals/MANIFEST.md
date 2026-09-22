# Manual-Suite PDFs — Provenance Manifest

Committed typeset builds of the four-volume RADIANT manual suite, kept in the
repository by owner instruction (2026-09-18) so the current manuals are readable
directly from the remote without a local TeX toolchain. Rule 26 record: these
are generated artifacts — regenerated wholesale, never hand-edited; a rebuild
that changes them replaces all four files and this manifest in one commit.

**Generator**: `python scripts/build_manual.py --all` (XeLaTeX; inputs are the
bound sources under `docs/theory/` and `docs/guides/` plus the build assets
under `scripts/manual_assets/`).
**Source commit**: `6d7fb858` (post CU-359/CU-360 Volume I coverage batch, 2026-09-21).

| File | Volume | Pages | SHA-256 |
|---|---|---|---|
| `radiant_theory.pdf` | I — Theory Manual | 95 | `cca009891bd8f110bb9fbfd9351a2c3b1e79bc442293f52f30b2f5f5c91523ae` |
| `radiant_users_guide.pdf` | II — User's Guide | 102 | `20c90cf2f481b5f5f6b744a31dfd80523e6561d9394424648af35b5b38e0b855` |
| `radiant_tech_ref.pdf` | III — Technical Reference | 160 | `af2971bee6cd21fbc4522c50c35a13fc830bcf012adb8972e129f5629675e25e` |
| `radiant_examples.pdf` | IV — Worked Examples & Validation | 181 | `3363e6a9d5d0ee469e8a681ecc85ab0bf40643811cd2ccd3daf3c624bd9713b5` |

Title pages print the version with a git-describe parenthetical when the build
tree sits past the release tag; a build on the tagged commit prints the bare
version.
