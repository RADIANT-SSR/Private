# Manual-Suite PDFs — Provenance Manifest

Committed typeset builds of the four-volume RADIANT manual suite, kept in the
repository by owner instruction (2026-09-18) so the current manuals are readable
directly from the remote without a local TeX toolchain. Rule 26 record: these
are generated artifacts — regenerated wholesale, never hand-edited; a rebuild
that changes them replaces all four files and this manifest in one commit.

**Generator**: `python scripts/build_manual.py --all` (XeLaTeX; inputs are the
bound sources under `docs/theory/` and `docs/guides/` plus the build assets
under `scripts/manual_assets/`).
**Source commit**: `cfcaf082` (post docs-drift batch C/D, 2026-09-20).

| File | Volume | Pages | SHA-256 |
|---|---|---|---|
| `radiant_theory.pdf` | I — Theory Manual | 86 | `5b27da2b69deb9f36720d8bf3e489c529c3e50fb8a7ab1d328528500769735b4` |
| `radiant_users_guide.pdf` | II — User's Guide | 102 | `242d6d44e61fced43be0f8539e7327e7420c0f0d2ccaeb4be448b5695f55cd26` |
| `radiant_tech_ref.pdf` | III — Technical Reference | 160 | `cc987a4eab7d6fd67d2380d30b873e268928d2500d9239dddcaf67fb72062959` |
| `radiant_examples.pdf` | IV — Worked Examples & Validation | 181 | `cf9b6570ab30513b699a69a5db1c4cd4b57a067296dbf8d04540c82fbe6f80a0` |

Title pages print the version with a git-describe parenthetical when the build
tree sits past the release tag; a build on the tagged commit prints the bare
version.
