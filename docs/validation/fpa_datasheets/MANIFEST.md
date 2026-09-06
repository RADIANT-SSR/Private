# FPA Reference Documents — Manifest

Committed reference PDFs (vendor datasheets, papers) cited by the shipped FPA
presets in `src/radiant/data/tables/fpa/`, per CLAUDE.md Rule 26(c)
(owner-ratified 2026-09-06, Gap 119). Repo-only — never shipped in the wheel;
wheel users get each preset's citation URL/DOI instead.

Rules (plan §3.5):

- One row per file, append-only; commit manifest rows with the file they
  describe. A vendor revision is a **new file + preset update**, never an
  in-place replacement.
- `tests/test_fpa_presets.py` (lands with the first preset) asserts every
  `file:` a preset cites exists here and matches its SHA-256.
- Prefer freely downloadable primary sources; the acquisition URL column
  records where each came from (Wayback URL when the live document is
  delisted). Fetch-URL register: plan Appendix A.

| File | Title | Source URL | Retrieved | SHA-256 | Citing preset(s) |
|---|---|---|---|---|---|

*(No documents yet — Phase 0 establishes the home; tranche-1 curation adds the
first rows.)*
