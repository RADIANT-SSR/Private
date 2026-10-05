# Manual-Suite PDFs — Provenance Manifest

Committed typeset builds of the four-volume RADIANT manual suite, kept in the
repository by owner instruction (2026-09-18) so the current manuals are readable
directly from the remote without a local TeX toolchain. Rule 26 record: these
are generated artifacts — regenerated wholesale, never hand-edited; a rebuild
that changes them replaces all four files and this manifest in one commit.

**Generator**: `python scripts/build_manual.py --all` (XeLaTeX; inputs are the
bound sources under `docs/theory/` and `docs/guides/` plus the build assets
under `scripts/manual_assets/`).
**Source commit**: `33cda60c` (the **v0.4.0** tag, 2026-10-04).

| File | Volume | Pages | SHA-256 |
|---|---|---|---|
| `radiant_theory.pdf` | I — Theory Manual | 97 | `00f9e6705d91c229a43b89a93a6b2e4e90a8c7562fa0ba85226a9d1cdafe8edd` |
| `radiant_users_guide.pdf` | II — User's Guide | 102 | `bec4e732ff065a96116011db0305e820299f6d2d950dc2ffb388ab0a733252f3` |
| `radiant_tech_ref.pdf` | III — Technical Reference | 162 | `3bd101101a20a462bea6bb4b809b65759d9c68b54bcfd3c14f948cce5b6a64d5` |
| `radiant_examples.pdf` | IV — Worked Examples & Validation | 185 | `bf17e717f050dc4d21c1d53244e81fae582a7ed32dd1902b602030f00f08b3e7` |

Title pages print the version with a git-describe parenthetical when the build
tree sits past the release tag; a build on the tagged commit prints the bare
version.

**Build at v0.4.0 (2026-10-04)** — built on the tagged commit, so the title pages
print the bare version. Volume I grew 96 → 97 pages (the first-order cavity rule and the
removal of the refractive-index input) and Volume IV grew 180 → 185 (the new
transmission-doors syntax reference, bound with the "how you drive it" chapters rather
than with the case studies, because it answers what shape a config takes — the question
an analyst has before they have a result to interpret). Volumes II and III keep their
page counts.

**Rebuild 2026-10-03** — the v0.3.0 builds were stale: the CU-380 warm-optics
work re-baselined four worked-example scenarios after the tag, so Volume IV
quoted superseded numbers. Rebuilt from current `main` with those sources
synced, plus the CU-384 and CU-391 documentation. Volume III grew 160 → 162
pages (the CU-391 refusal and CU-384 sentinel entries); the other three volumes
keep their page counts.
