# Manual-Suite PDFs — Provenance Manifest

Committed typeset builds of the four-volume RADIANT manual suite, kept in the
repository by owner instruction (2026-09-18) so the current manuals are readable
directly from the remote without a local TeX toolchain. Rule 26 record: these
are generated artifacts — regenerated wholesale, never hand-edited; a rebuild
that changes them replaces all four files and this manifest in one commit.

**Generator**: `python scripts/build_manual.py --all` (XeLaTeX; inputs are the
bound sources under `docs/theory/` and `docs/guides/` plus the build assets
under `scripts/manual_assets/`).
**Source commit**: `c13dd51d` (post-v0.3.0 `main`, 2026-10-03).

| File | Volume | Pages | SHA-256 |
|---|---|---|---|
| `radiant_theory.pdf` | I — Theory Manual | 96 | `496f0854d4f5adaaa3bcbabc3aa06c2569863fc94bd0e6333830b7360e02f40e` |
| `radiant_users_guide.pdf` | II — User's Guide | 102 | `9e89a5fa8ceb1e58ab14f97eabd5e4646f9cad7f627535117d57e36bfffcf9c3` |
| `radiant_tech_ref.pdf` | III — Technical Reference | 162 | `738a6d37b7875ff0c5f28897b77528a05af8110891b9034a404427312e3d9ed4` |
| `radiant_examples.pdf` | IV — Worked Examples & Validation | 180 | `0a6668b98cc27ecbb26dcff97c6a6fe38b41746aee1b5c3ad6eff244a24a4e29` |

Title pages print the version with a git-describe parenthetical when the build
tree sits past the release tag; a build on the tagged commit prints the bare
version.

**Rebuild 2026-10-03** — the v0.3.0 builds were stale: the CU-380 warm-optics
work re-baselined four worked-example scenarios after the tag, so Volume IV
quoted superseded numbers. Rebuilt from current `main` with those sources
synced, plus the CU-384 and CU-391 documentation. Volume III grew 160 → 162
pages (the CU-391 refusal and CU-384 sentinel entries); the other three volumes
keep their page counts. The committed GUI screenshots in Volume IV's case-study
chapters still predate CU-380 — they cannot be regenerated headlessly — and
each chapter now says so in the text.
