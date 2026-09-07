# Scenario 2.8 GUI Workflow — FPA Part Library (Gap 119, plan Phase 3)

What the GUI must let Mike do, and where it does it.

1. **Open the study**: File → Open → `inputs/geosnap18_mwir_leo.yaml`. The
   `fpa: geosnap-18` key applies on load; the first evaluation runs with the
   preset values already in place.
2. **Detector stage → "FPA part library" row** (one compact line above the
   Inputs card — live-review iteration 2026-09-06): status label ("no part
   applied"), **Choose part & apply…**, **Open datasheet/paper**.
3. **Choose part & apply…** opens the part-library dialog: a table of all 21
   shipped parts with **Kind** (FPA vs "ROIC — needs detector", Gap 121),
   Class, Band, and the basis census (how many values are datasheet / paper /
   derived / assumed) — data quality visible *before* applying. Selecting a
   row shows the description + citations in the details pane; **Apply
   preset** (or double-click) makes the one `sensor.apply_fpa` call. The
   status row updates: "geosnap-18: 12 applied" (plus "N kept (explicit
   wins)" when the study already pinned some). The host re-evaluates exactly
   as after a field edit; the noise budget, detector illustration, and
   outputs readout all refresh.
4. **Details…** opens the per-parameter report: which dot-paths the preset
   set, which explicit values won, the basis census, and the citation titles.
5. **Open datasheet/paper** opens the committed PDF
   (`docs/validation/fpa_datasheets/geosnap18_datasheet_2022.pdf`) in the
   system viewer; for parts whose only public source is a web page (e.g. the
   Senseeker DPROICs) it opens the citation URL instead.
6. **Override**: Mike edits "Dark rate" in the Inputs card below — ordinary
   field edit, explicit value, wins over any later preset re-apply (and the
   report row of a re-apply says so).
7. **Remove** (owner request 2026-09-06): the Remove button on the row clears
   the preset (one `sensor.remove_fpa` call) — preset-seeded values revert to
   their defaults for a custom solution, Mike's explicit edits survive, and
   the study re-evaluates. Choosing a different part in the dialog does this
   implicitly first, so switching parts never mixes two presets' values.
   When the removed preset was supplying required parameters (GeoSnap's pixel
   pitch has no schema default), the study is an expected incomplete state:
   no modal, no failed run — the card lists the dot-paths to set, every
   result flips to its stale marker, and the status bar names what to set
   (the CU-322 advisory pattern).

Display-unit rule holds throughout: preset values are stored in
datasheet-native units but display in the session display units like every
other field.

Covered by `src/radiant/gui/tests/test_fpa_part_selector.py` (offscreen);
live review pending per the GUI live-review rule.
