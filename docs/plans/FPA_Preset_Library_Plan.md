# FPA Preset Library — Development and Test Plan

**Status:** Draft — awaiting owner ratification of §8.1 proposed decisions, §8.2 open questions, and the §4 roster cull.

**Date:** 2026-09-06
**Gap:** Gap 119 (`docs/tracking/gaps.md`)
**Category:** B overall (core abstraction: preset format + loader + application semantics); per-part data curation is Category B (dimensional audit per part); the GUI phase is Category D.
**Owner scope decisions already made (conversation, 2026-09-06):**
1. Reference documents: **commit the PDFs** — each preset's datasheet/paper lives in the repository so it is always available to reference alongside the preset. (Requires the Rule 26 carve-out and taxonomy home in §3.5.)
2. Seed set: **all four part classes** — cooled IR / digital-pixel (GeoSnap et al.), FLIR cores and microbolometers, RVS large-format, scientific/visible — with "a good number of examples" from deep research (§4).
3. Process: **plan-first** — this document is ratified before any code lands.

**Read first:**
`docs/architecture/RADIANT_Master_Architecture.md`,
`docs/architecture/RADIANT_Parameter_System.md` (Provenance, unit-aware `set()`),
`docs/architecture/RADIANT_Detector.md`,
`docs/architecture/RADIANT_Readout.md` (incl. Gap 117 digital-counting parameters),
`docs/OPERATING_MODEL.md` (§1 closed taxonomy, §5 naming — both amended by this plan),
`src/radiant/data/library.py` (the bundled-data precedent this extends).

---

## 1. Objective

Ship a curated library of **named FPA/ROIC parts** — real detectors an analyst selects by
name instead of transcribing a datasheet: Teledyne GeoSnap digital-pixel MWIR arrays,
Teledyne FLIR camera cores, Raytheon Vision Systems large-format arrays, scientific parts
(H2RG, sCMOS), and uncooled microbolometers. A preset is a reviewed bundle of
`detector.*` and `readout.*` parameter values, each value carrying **per-parameter source
attribution** to a citation, and each citation backed by a **committed reference
document** (vendor datasheet or published paper) so the numbers are auditable forever.

Three properties are non-negotiable:

1. **Provenance travels with every number.** A preset value without a source and a
   basis grade does not ship. "Where did 6.0 ke⁻ full well come from?" is answerable
   from the preset file alone.
2. **Presets seed; the user overrides.** Applying a preset never locks a parameter.
   Explicit user/config values always win, and the result records which preset values
   were overridden.
3. **Presets are partial by design.** A datasheet never specifies everything RADIANT
   can model. A preset sets only what its sources support; everything else keeps the
   schema default, and the boundary between the two is explicit and inspectable.

## 2. What Exists Today

| Surface | State | Reuse |
|---|---|---|
| `radiant.data.SpectralLibrary` (`src/radiant/data/library.py`) | Bundled reference data by *material*: QE curves (`tables/detectors/*.csv`), emissivities, solar spectrum; manifest-driven; ships in the wheel | The packaging + loading precedent. The FPA library is a sibling module (Rule 19: own file), same `tables/` root |
| `detector.qe_material` resolution (`api/session.py`) | API layer resolves a library name to a `SpectralData` pre-chain (Rule 6: stages never read files) | The exact layering the preset apply step follows: `data/` loads, `api/` validates against schema and applies |
| `ParameterSet.set(name, value, provenance, source, unit=…)` | Unit-aware boundary conversion (Rule 2) + `Provenance` enum + free-text source label | Presets store values in **datasheet-native units** and convert at `set()`; a new `Provenance.PRESET` variant labels them |
| Gap 117 digital-counting readout (`readout.architecture`, `counter_bits`, `count_packet_e`, `residue_readout`, `max_count_rate_hz`) | DELIVERED 2026-09-05 | GeoSnap-class presets are the first real parts to exercise this chain |
| `detector.*` / `readout.*` schemas | ~30 + ~22 parameters | The target namespace. **No schema change is expected in Phases 0–3**; curation may surface parameters worth adding (each is its own gap/CU, not scope creep here) |

## 3. Design

### 3.1 Preset document format

One YAML file per part: `src/radiant/data/tables/fpa/<slug>.yaml` (slug: lowercase,
hyphenated — `geosnap-18.yaml`, `flir-boson-640.yaml`). Ships in the wheel like the
rest of `tables/`. Format:

```yaml
fpa_preset: 1                # format version
name: geosnap-18
vendor: Teledyne FLIR
model: GeoSnap-18
part_class: cooled_ir_droic   # cooled_ir | cooled_ir_droic | uncooled_bolometer | scientific_visible | swir
material: HgCdTe
band: {label: MWIR, cut_on_um: 3.0, cut_off_um: 5.3}
description: >
  1280×1024, 18 µm pitch digital-pixel MWIR FPA; in-pixel 16-bit counting ROIC.

parameters:
  detector.pixel_pitch_x_um:   {value: 18.0, unit: um,   source: ds2023, basis: datasheet, location: "p. 2, spec table"}
  detector.n_pixels_cross:     {value: 1280, unit: null, source: ds2023, basis: datasheet, location: "p. 2"}
  readout.architecture:        {value: digital_counting, unit: null, source: spie2021, basis: paper, location: "§2"}
  readout.counter_bits:        {value: 16,   unit: null, source: spie2021, basis: paper, location: "§2, Fig. 3"}
  readout.count_packet_e:      {value: 4.4e3, unit: e-,  source: spie2021, basis: derived, location: "LSB well / 2^16, §3"}
  detector.dark_rate_e_per_s:  {value: 1.0e5, unit: e-/s, source: null,   basis: assumed, note: "typical MW HgCdTe @ 110 K; no public figure"}
  # … only parameters the sources support; nothing else appears here.

qe_table: null                # optional: a tables/detectors/<name>.csv shipped with the part

sources:
  ds2023:
    type: vendor_datasheet
    title: "GeoSnap Product Datasheet"
    publisher: Teledyne FLIR
    year: 2023
    url: https://…
    file: geosnap_datasheet_2023.pdf        # docs/validation/fpa_datasheets/<file>
  spie2021:
    type: paper
    title: "…"
    authors: "…"
    venue: "Proc. SPIE 11xxx"
    year: 2021
    doi: 10.1117/…
    file: geosnap_spie_2021.pdf

notes: >
  Free-text curation notes: what the sources disagree on, what regime the NEDT
  figure assumes, etc.
```

Format rules:

- **`basis` is a closed enum**: `datasheet` (vendor-published spec), `paper`
  (peer-reviewed/conference measurement), `derived` (computed from sourced numbers —
  the `location` states the arithmetic), `assumed` (curator judgment — `source: null`,
  mandatory `note`). Consumers can filter on it; the GUI displays it.
- **Values are stored in the source document's native unit** and converted at
  `params.set(…, unit=…)` — Rule 2 (convert at boundaries only) and auditability: the
  number in the YAML is the number printed in the PDF. `unit: null` for dimensionless
  and enum values.
- **Every `parameters:` entry needs `source` + `basis` + `location`** (except
  `basis: assumed`, which needs `note` instead of `source`/`location`). A preset with
  an unattributed value fails validation.
- **No emissivity, no over-specification**: presets set only `detector.*`/`readout.*`
  dot-paths. Preset application goes through the ordinary `ParameterSet` machinery, so
  bounds/enum/consistency validation is identical to hand entry (Rule 16).

### 3.2 Partial-preset semantics

A preset sets exactly the parameters its sources support. Per part class there is a
**minimum viable set** the curation phase must meet before a part ships (else it stays
in the roster as "blocked — thin public data"):

| Part class | Minimum set |
|---|---|
| All | pitch (x, y), format, band, material |
| Cooled IR (analog) | + well capacity, read noise, operating T, QE (value or curve) |
| Cooled IR DROIC | + `readout.architecture`, counter bits, packet size, residue flag |
| Uncooled bolometer | + NEDT (with f/# and scene conditions in `notes`), frame rate, time constant — electron-domain values are usually unpublished; the preset marks them `assumed` or omits them (Gap 101's bolometric-detector limitation applies and is referenced, not fixed, here) |
| Scientific/visible | + QE curve or peak, well, read noise, dark current (with T) |

### 3.3 `FPALibrary` loader — `src/radiant/data/fpa.py`

New module (Rule 19), sibling of `library.py`; imports `radiant.core` + stdlib + yaml
only (import rules for `data/`). Surface:

```python
lib = FPALibrary()                    # optional data_root override, like SpectralLibrary
lib.names() -> list[str]
lib.part(name) -> FPAPreset           # frozen dataclass: metadata + entries + sources
```

`FPALibrary` validates **format** (required fields, basis enum, source-key references,
`file:` naming) at load and raises actionable errors (Rule 15). It cannot validate
against the parameter **schema** (`data/` may not import stage `_schema.py`); that
happens at apply time in the API layer (§3.4) and exhaustively in tests (§6).

### 3.4 Application semantics (API layer)

- **Config YAML**: a top-level `fpa: <name>` key in the sensor config (parsed by the
  io/api layer alongside the existing non-parameter sections). Applied **before** the
  config's `parameters:` — explicit config values override preset values.
- **Scripting**: `sensor.apply_fpa("geosnap-18")` (exact name/home on the `Sensor` /
  session surface decided at Phase 2 against the current API doc).
- Each applied value: `params.set(dotpath, value, provenance=Provenance.PRESET,
  source=f"fpa:geosnap-18/{source_key}", unit=…)`. A new `Provenance.PRESET` enum
  variant (public-surface addition → CHANGELOG + Parameter System doc, Rule 20/29).
- **Override reporting**: applying a preset returns (and the run result records) the
  list of preset parameters, and which of them a later user/config set displaced —
  the same inspectability standard as the rest of the provenance system.
- If the preset names a `qe_table`, apply sets `detector.qe_material` to the shipped
  curve, same resolution path as today.

### 3.5 Committed reference documents (owner-ratified 2026-09-06)

- **Home**: `docs/validation/fpa_datasheets/` — proposed as the least-invasive fit:
  `validation/` already holds "truth anchors … that current tests reference," which is
  precisely what these PDFs are (a §6 test asserts every cited `file:` exists and
  matches its manifest hash). The alternative — a new top-level `docs/references/`
  folder — needs a taxonomy row; §8.2 asks the owner to choose.
- **Manifest**: `docs/validation/fpa_datasheets/MANIFEST.md` — one row per file:
  filename, title, source URL, retrieval date, SHA-256, citing preset(s). Append-only,
  collision-hygiene rules apply (registry-style small commits).
- **Rule 26 carve-out** (lands in the Phase 0 PR, in lock-step with this plan's
  ratification): committed binaries extend to *(c) a reference document that a shipped
  data product cites as provenance, listed in a manifest with source URL, retrieval
  date, and hash*. CLAUDE.md Rule 26 and `OPERATING_MODEL.md` amended in the same PR.
- **Not shipped in the wheel**: the PDFs stay repo-only (`MANIFEST.in` excludes them);
  the preset YAML citations (title/venue/DOI/URL) are what a wheel user gets. The GUI
  open-datasheet action opens the repo file when present, else the URL.
- **Copyright**: vendor datasheets and SPIE papers are redistributable-with-care at
  best. Owner accepted the risk for this private repository (2026-09-06); freely
  downloadable primary sources are preferred at curation time, and the manifest's URL
  column records where each came from.

### 3.6 GUI surface (Phase 3, Category D)

- Detector-stage contextual form gains a **part selector** (grouped by part class)
  with an "open datasheet/paper" action and a provenance view: which parameters the
  preset set, each value's basis grade, and which the user has overridden
  (the Provenance display rules from the contextual-layout design apply).
- Display units stay the user's choice (GUI display-unit hard rule) — preset-native
  units affect storage, never display.
- A new scenario exercises the workflow end-to-end and ships `gui_workflow.md`
  (scenario workflow hard rule). The GUI live-review rule applies: no merge before an
  owner-witnessed live run.

## 4. Candidate Roster (deep-research result — owner culls at ratification)

> **Placeholder — research in flight.** Three research passes (cooled IR/DROIC, FLIR
> cores + microbolometers, scientific/visible) are compiling the roster with full
> citations and per-part data-quality grades. This section is filled before the plan
> is submitted for ratification.

## 5. Phases

| Phase | Scope | Category | Exit criteria |
|---|---|---|---|
| **0 — Format + loader** | Preset YAML format (§3.1), `FPAPreset`/`FPALibrary` (§3.3), format-validation errors, Rule 26 carve-out + taxonomy amendment + manifest skeleton, `Provenance.PRESET` | B | Loader round-trips a fixture preset; format violations raise actionable errors; `mypy --strict`, docs amended in lock-step |
| **1 — Seed curation, tranche 1** | GeoSnap-10/-18 + one FLIR cooled core + one microbolometer + H2RG (exact tranche set at ratification from §4), PDFs + manifest rows, per-part dimensional audit | B | Every tranche-1 preset passes schema validation (§6), minimum-set check (§3.2), cited files present + hashed |
| **2 — Application semantics** | Config `fpa:` key, `apply_fpa` API, override reporting, `qe_table` hookup, CHANGELOG + API/Parameter System doc updates | B | Preset→override→run flow covered by integration test; a GeoSnap preset drives the Gap 117 counting chain in a golden test |
| **3 — GUI part selector** | §3.6; scenario + `gui_workflow.md`; live review | D | Owner-witnessed live run; GUI suite green |
| **4 — Roster completion** | Remaining ratified roster in tranches (RVS/thin-data parts last, each shipping only if it clears §3.2 minimums) | B | Each tranche: same gates as Phase 1 |

Phases 0–2 are plain-battery work (schema untouched ⇒ no forced full-GUI run, but
Phase 2 touches `api/` ⇒ full battery). Phase 3 is a GUI diff plus scenario files —
scoped GUI battery per the ratified gate rules.

## 6. Testing and Validation

- **Level 0 (Phase 0)**: format fixtures — valid preset loads; each violation class
  (missing basis, dangling source key, unknown field, bad version) raises its error.
- **Exhaustive schema conformance (Phase 1+)**: a test (living outside `data/`, e.g.
  `tests/test_fpa_presets.py`, where importing schema + data is legal) applies **every
  shipped preset** to a fresh `ParameterSet` — every dot-path exists in the schema,
  every value passes bounds/enum validation, every unit string converts. This is the
  check `data/` itself cannot perform (§3.3).
- **Provenance completeness**: every parameter entry attributed per §3.1; every cited
  `file:` exists under the datasheets home and matches the manifest SHA-256.
- **Minimum-set check**: every shipped preset meets its §3.2 class minimum.
- **Golden (Phase 2)**: one full-chain run from a GeoSnap preset (digital-counting
  branch) and one from a scientific part, pinned.
- **Per-part dimensional audit** (Category B): recorded in each curation PR using the
  standard audit table — datasheet unit → stored unit → canonical unit per parameter.

## 7. Risks and Watch Items

- **Thin public data (RVS and friends)**: ITAR/limited-distribution parts may never
  clear the §3.2 minimum. The roster marks them; they ship late or not at all rather
  than shipping guesswork. A part that can't ship stays listed in §4 with its blocker.
- **Marketing numbers vs measured numbers**: brochure NEDT/well figures without stated
  conditions get `basis: datasheet` but a mandatory conditions note; when a paper and
  a datasheet disagree, the preset takes the primary measurement and `notes` records
  the disagreement.
- **Schema pressure**: curation will find quantities RADIANT can't hold (e.g.
  bolometer time constant — Gap 101 territory). Each becomes a gap/finding per Rule
  21, never an ad-hoc schema addition inside a curation PR.
- **Staleness**: vendors revise datasheets. The manifest's retrieval date + hash pin
  what the preset was curated against; a revision is a new file + preset update, not
  an in-place mutation.
- **Wheel size**: presets are text (KB); PDFs are repo-only (§3.5). No size risk.

## 8. For Ratification

### 8.1 Proposed decisions

1. Preset format v1 as specified in §3.1 (native-unit storage, closed basis enum,
   per-parameter attribution).
2. Seed-first-tranche = GeoSnap-10, GeoSnap-18, one FLIR cooled core, one
   microbolometer core, H2RG (final SKUs from §4).
3. `Provenance.PRESET` variant + override-reporting semantics (§3.4).
4. Rule 26 carve-out text (§3.5) amended into CLAUDE.md + Operating Model in the
   Phase 0 PR.

### 8.2 Open questions (owner input needed)

1. **PDF home**: `docs/validation/fpa_datasheets/` (no new top-level folder) vs a new
   `docs/references/` taxonomy row. §3.5 recommends the former.
2. **Config key name**: `fpa:` vs `detector_preset:` at the config top level.
3. **Roster cull**: which §4 parts are in, and tranche ordering beyond tranche 1.
4. **Scope boundary**: cameras/cores (Boson: FPA + lens + electronics) are more than
   an FPA — presets model the *FPA/ROIC through readout* only, and optics values from
   a core datasheet are out of scope (they belong in optics element documents). Confirm.
