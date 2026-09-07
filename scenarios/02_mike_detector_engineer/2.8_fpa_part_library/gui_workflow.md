# Scenario 2.8 GUI Workflow — FPA Part Library (Gap 119, plan Phase 3)

What the GUI must let Mike do, and where it does it.

1. **Open the study**: File → Open → `inputs/geosnap18_mwir_leo.yaml`. The
   `fpa: geosnap-18` key applies on load; the first evaluation runs with the
   preset values already in place.
2. **Detector stage → "FPA part library" card** (new, above the Inputs card):
   - The part combo lists all 21 shipped parts, grouped by class (Cooled IR /
     digital-pixel counting / Uncooled bolometer / Scientific-visible / SWIR),
     each as "Vendor Model (slug)".
   - Selecting a part shows the blurb: band, parameter count, and the basis
     census (how many values are datasheet / paper / derived / assumed) —
     Mike sees data quality *before* applying.
3. **Apply preset** — one click = one `sensor.apply_fpa` call. The report row
   appears: "geosnap-18: 11 parameter(s) applied" (plus "N kept their
   explicit values (explicit wins)" when the study already pinned some).
   The host re-evaluates exactly as after a field edit; the noise budget,
   detector illustration, and outputs readout all refresh.
4. **Details…** opens the per-parameter report: which dot-paths the preset
   set, which explicit values won, the basis census, and the citation titles.
5. **Open datasheet/paper** opens the committed PDF
   (`docs/validation/fpa_datasheets/geosnap18_datasheet_2022.pdf`) in the
   system viewer; for parts whose only public source is a web page (e.g. the
   Senseeker DPROICs) it opens the citation URL instead.
6. **Override**: Mike edits "Dark rate" in the Inputs card below — ordinary
   field edit, explicit value, wins over any later preset re-apply (and the
   report row of a re-apply says so).

Display-unit rule holds throughout: preset values are stored in
datasheet-native units but display in the session display units like every
other field.

Covered by `src/radiant/gui/tests/test_fpa_part_selector.py` (offscreen);
live review pending per the GUI live-review rule.
