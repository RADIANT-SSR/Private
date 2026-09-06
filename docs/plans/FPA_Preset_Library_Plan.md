# FPA Preset Library — Development and Test Plan

**Status:** Draft — awaiting owner ratification of §8.1 proposed decisions, §8.2 open questions, and the §4 roster cull.

**Date:** 2026-09-06
**Gap:** Gap 119 (`docs/tracking/gaps.md`)
**Category:** B overall (core abstraction: preset format + loader + application semantics); per-part data curation is Category B (dimensional audit per part); the GUI phase is Category D.
**Owner scope decisions already made (conversation, 2026-09-06):**
1. Reference documents: **commit the PDFs** — each preset's datasheet/paper lives in the repository so it is always available to reference alongside the preset. (Requires the Rule 26 carve-out and taxonomy home in §3.5.)
2. Seed set: **all four part classes** — cooled IR / digital-pixel (GeoSnap et al.), FLIR cores and microbolometers, RVS large-format, scientific/visible — with "a good number of examples" from deep research (§4).
3. Process: **plan-first** — this document is ratified before any code lands.
4. **Every FPA also ships as a RADIANT config file** — a document the ordinary config
   path can load, not only a library entry (§3.1a).

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

### 3.1a Every FPA is also a loadable RADIANT config (owner-directed 2026-09-06)

Each part must be usable through the **ordinary config path** — an analyst can start a
study from the part without the preset machinery at all. Two candidate mechanisms for
Phase 0 to decide (ratification does not need to pick one):

- **(a) Dual-role file**: the preset YAML *is* a valid RADIANT config document — its
  parameter entries live in (or compile trivially to) the standard `parameters:` shape,
  and `load_config` learns to accept (and skip) the preset metadata sections
  (`sources:`, provenance fields), the same way existing non-parameter sections are
  routed to their own readers. One file per part, no duplication.
- **(b) Generated config**: `scripts/gen_fpa_configs.py` renders
  `configs/fpa/<slug>.yaml` (standard config format, provenance as comments) from each
  preset, checked for freshness in the gate battery exactly like
  `gen_param_reference.py --check`. Two files per part, but zero loader changes.

Either way, the acceptance test is the same: `radiant run` (and the GUI's file-open)
consumes the per-part document directly, and the values that arrive in the
`ParameterSet` are identical to those the `fpa:` preset path applies.

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

**Method.** Three research passes (2026-09-06) fetched and read primary documents
directly — vendor datasheet PDFs (Teledyne's document CDN serves them ungated; Wayback
Machine for delisted ones), arXiv preprints of the refereed papers, Crossref for DOI
verification. **Every number in Appendix A was read from a fetched document during the
research session, none from model memory.** PDF acquisition for §3.5 is therefore
proven feasible from this environment; a handful of documents are gated (noted
per part). Full citations and caveats: Appendix A. Grades: **A** = formal datasheet
and/or refereed paper with stated conditions; **B** = vendor page/brochure numbers or
single-integrator measurements; **C** = structurally incomplete (ROIC-only part,
ITAR-thin, or unconditioned headline numbers).

**Attribution correction from research:** GeoSnap is a **Teledyne** (Rockwell/Teledyne
Imaging Sensors heritage) product line, not FLIR/SBF or RVS. The well-documented
public RVS windows are the JWST/MIRI Si:As arrays and the VIRGO-2K astronomy array;
RVS tactical/large-format parts have no public datasheets (ITAR).

### 4.1 Cooled IR and digital-pixel (10)

| Part | Type | Format / pitch | Band | Key public numbers | Grade |
|---|---|---|---|---|---|
| Teledyne GeoSnap-18 | digital-FPA (on-chip 14-bit ADC), HgCdTe | 2048² / 18 µm (stitchable to 3K×3K) | 0.4–15 µm custom cutoff | dual-gain well 0.18/2.6 Me-; ROIC noise 40/400 e-; QE 75 min/85 typ %; 85–100 Hz; T_op 45–300 K; measured LW device: well 2.75 Me-, 360 e- RMS, QE 79.7 % @ 10.6 µm | **A** |
| Teledyne GeoSnap-10 | digital-FPA, HgCdTe | 4K²–8K² / 10 µm | 1.05–14 µm custom | 14-bit on-chip ADC, ports/rates, T_op — but **no public well/noise/QE** | **C** (borrow GeoSnap-18 values, `basis: derived`) |
| Senseeker Oxygen RD0092-D080 | DROIC, column-parallel 14-bit (bare ROIC) | 1280×720 / 8 µm | detector-agnostic | dual-gain well 260 ke-/3.4 Me-; >120 dB HDR; >500 fps | **B/C** (no detector-side numbers by construction) |
| Senseeker Magnesium MIL RP0092 | true DPROIC, in-pixel counting | 1280×720 / 12 µm | detector-agnostic | well 8→>140 Me- programmable; LSB to 160 e-/count; digital residue; >110 dB; 120 fps | **B** (exercises Gap 117 exactly) |
| Senseeker Calcium RP0033-J200 | DPROIC | 640×512 / 20 µm (to 4K²) | detector-agnostic | well >40/400 Me-; **measured read noise @ 65 K: ~50 e- ITR / ~85 e- IWR** (high gain); >700 fps | **B+** (best public DROIC noise floor) |
| MIT LL DFPA | DPROIC research lineage | 256²/30 µm; 640×480/20 µm | SWIR–LWIR demos | 16-bit up/down counter (14–21 family); packet 1.2–8 ke-/count; ~230 Me- effective well; published 4-term noise model; digital TDI | **A** (paper; "generic DROIC" preset anchor for Gap 117) |
| RVS MIRI Si:As IBC (JWST) | analog ROIC, Si:As IBC | 1024² / 25 µm | ~5–28 µm | read noise 14 e-; dark 0.2/0.07 e-/s @ 6.7 K; QE ≥60 %; well ~250 ke- | **A** (best-documented cooled LWIR array in open literature) |
| RVS VIRGO-2K | analog ROIC, HgCdTe | 2048² / 20 µm | 0.75–2.45 µm | read noise ~24 e-; dark ~0.2 e-/s; QE ~90 % (1.0–2.35 µm); gain 4.19 e-/ADU | **A** |
| SCD BlackBird 1920 | digital ROIC, InSb IDCA | 1920×1536 / 10 µm | 1–5.4 µm (f/3 cold shield std) | NEDT <28 mK @ 2.5 Me- well, 70 % fill (f/# unstated); ≥120 Hz; 80 K | **B** |
| Lynred Daphnis-HD MW | HOT HgCdTe IDDCA | 1280×720 / 10 µm | 3.7–4.8 µm | NEDT 20 mK (293 K scene, 70 % fill, 2.7 Me- gain); wells 1.1/2.7/5.6 Me-; ≤110 K; 85 Hz; operability >99.8 % | **A−** |

### 4.2 Teledyne FLIR cores and uncooled microbolometers (7)

| Part | Type | Format / pitch | Band | Key public numbers | Grade |
|---|---|---|---|---|---|
| FLIR Neutrino LC | cooled MWIR core, HOT FPA (ISC0403 ROIC) | 640×512 / 15 µm | 3.4–≥4.9 µm | NEdT <25 mK (50 % fill, 30 °C BB); **well 7 Me-**; t_int 0.01–16 ms; f/5.5 cold shield; 60 Hz | **A−** (no K temp, no read noise) |
| FLIR Neutrino SX12 ISR1200 | cooled MWIR InSb (ISC1308) | 1280×1024 / 12 µm | 3.4–5.0 µm | **77 K**; 30/60 Hz; 14-bit — but **no public NEdT/well/noise** | **C** |
| FLIR Boson+ 640 | uncooled VOx microbolometer | 640×512 / 12 µm | 8–14 µm | NEDT ≤20 mK (f/1.0 lensless, 30 °C bkgd, high gain, conditions in 150-pp engineering datasheet); (f/#)²/τ scaling law; **τ_thermal 8 ms**; 60 Hz | **A** (best current public bolometer reference) |
| FLIR Tau 2 640 | uncooled VOx (EOL 2024) | 640×512 / 17 µm | 7.5–13.5 µm | NEdT <30/40/50 mK tiers — **unconditioned** (NDA appendix); 30 Hz | **C** (legacy flag + unconditioned-NEDT flag) |
| FLIR Tau 2+ 640 | uncooled VOx (EOL 2024) | 640×512 / 17 µm | 7.5–13.5 µm | NEdT <25 mK (unconditioned) | **C** (legacy) |
| FLIR Lepton 3.5 | uncooled VOx micro-core | 160×120 / 12 µm | 8–14 µm | <50 mK (integral f/1.1); 8.7 Hz; τ ~12 ms (from Lepton 2.5 eng. datasheet — family inference) | **B+** |
| Lynred ATTO640 | uncooled microbolometer | 640×480 / 12 µm | LWIR (band not printed!) | **NETD <60 mK (f/1, 300 K, 30 Hz)** — cleanest fully-conditioned bolometer NETD found; τ 10 ms; operability >99.5 % | **A−** |

All uncooled parts publish no electron-domain quantities — every bolometer preset uses
the NEDT-specified path and inherits the Gap 101 limitation (referenced, not fixed,
by this plan).

### 4.3 Scientific and visible (8)

| Part | Type | Format / pitch | Band | Key public numbers | Grade |
|---|---|---|---|---|---|
| Teledyne H2RG (1.75/2.5/5.3 µm cutoffs) | HgCdTe hybrid | 2048² / 18 µm | 0.4 µm–cutoff | QE ≥70/80 %; dark ≤0.05 e-/s (@ 120/77/37 K per cutoff); CDS read ≤30/18/15 e-; well ≥80 ke- (65 ke- for 5.3 µm); JWST-achieved: 6 e- in 1000 s up-the-ramp | **A** |
| Teledyne H4RG-10 (Roman WFI) | HgCdTe hybrid | 4096² / 10 µm | 0.5–2.5 µm | QE ~90 %; dark <0.005 e-/s @ ~95 K; 5–6 e- in 180 s multi-accum; full well needs one lookup (Mosby 2020, OA) | **A−** |
| Teledyne e2v CCD273-84 (Euclid VIS) | BSI full-frame CCD | 4096×4132 / 12 µm | 550–900 nm | DQE peak 94 % @ 650 nm; well ≥175 ke-; chain noise ≤4.5 e- @ 70 kHz; gain 3.5 e-/DN, 16-bit; 153 K | **A** |
| e2v CCD42-40 (BI AIMO) | scientific CCD | 2048×2052 / 13.5 µm | 200–1060 nm | QE 85 % (midband); well 100 ke- typ; 3 e- RMS @ 20 kHz; dark 250–500 e-/pix/s @ 293 K + scaling law | **A** (datasheet is Wayback-archived) |
| Sony IMX455 | BSI full-frame CMOS | 9576×6388 / 3.76 µm | 0.35–1.0 µm | refereed characterization: QE peak 80 % @ 475 nm; 3.5 e- RMS, 50 ke-, 0.763 e-/ADU (Mode 1 gain 0); dark 0.011 e-/s @ 263 K; 16-bit | **A** (mode must be pinned) |
| Gpixel GSENSE400BSI | BSI sCMOS | 2048² / 11 µm | 0.35–1.0 µm | QE 95 % @ 560 nm; well 91 ke-; 1.6 e- (high gain); 12-bit dual-gain HDR 93.9 dB; dark 42 e-/s @ 303 K | **B** |
| Sony IMX250 (Pregius gen2) | GS industrial CMOS | 2464×2056 / 3.45 µm | 0.3–1.0 µm | EMVA 1288: QE 67.6 % @ 550 nm; well 10.6 ke-; 2.15 e-; gain 2.70 e-/DN | **A−** (camera-level EMVA) |
| Sony IMX990 SenSWIR | InGaAs-on-Si hybrid | 1296×1032 / 5 µm | 0.4–1.7 µm | QE >75 % @ 1.2 µm; EMVA: well 143 ke-, 196 e- RMS, dark 4 ke-/s @ 15 °C; global shutter, on-chip 12-bit | **B+** |

A TDI/line-scan heritage part was not completed; best candidates for a follow-up
tranche: Teledyne DALSA TDI family, or the Landsat-8/9 OLI Teledyne SiPIN hybrid
(Knight & Kvaran 2014, *Remote Sensing* 6, 10286, open access). Leonardo SAPHIRA
(HgCdTe e-APD) is a strong candidate the research excluded rather than cite from
memory.

### 4.4 Recommended tranches

- **Tranche 1 (Phase 1)**: GeoSnap-18, GeoSnap-10 (derived-basis), Neutrino LC,
  Boson+ 640, H2RG-2.5 µm — covers analog-cooled, digital-FPA, bolometric, and
  scientific classes, all grade A/A− except the owner-named GeoSnap-10.
- **Tranche 2**: MIRI Si:As, VIRGO-2K, Calcium RP0033 (+ generic-DROIC preset from
  the MIT LL DFPA paper), Daphnis-HD MW, ATTO640, Lepton 3.5.
- **Tranche 3**: CCD273-84, CCD42-40, IMX455, IMX990, SCD BlackBird 1920, H4RG-10,
  Magnesium RP0092, GSENSE400BSI, IMX250.
- **Hold / thin**: Tau 2 and Tau 2+ (EOL + unconditioned NEDT — include only if the
  owner wants legacy parts), Oxygen RD0092 and SX12 ISR1200 (structural gaps), BAE
  Athena / DRS Tenum (no fetchable public data), RVS tactical parts (ITAR).

## 5. Phases

| Phase | Scope | Category | Exit criteria |
|---|---|---|---|
| **0 — Format + loader** | Preset YAML format (§3.1), `FPAPreset`/`FPALibrary` (§3.3), format-validation errors, Rule 26 carve-out + taxonomy amendment + manifest skeleton, `Provenance.PRESET` | B | Loader round-trips a fixture preset; format violations raise actionable errors; `mypy --strict`, docs amended in lock-step |
| **1 — Seed curation, tranche 1** | GeoSnap-10/-18 + one FLIR cooled core + one microbolometer + H2RG (exact tranche set at ratification from §4), PDFs + manifest rows, per-part dimensional audit, per-part loadable config (§3.1a) | B | Every tranche-1 preset passes schema validation (§6), minimum-set check (§3.2), cited files present + hashed; every part loads through the ordinary config path |
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
   Relatedly, §3.1a mechanism (dual-role file vs generated config) — input welcome,
   otherwise Phase 0 decides.
3. **Roster cull**: which §4 parts are in, and tranche ordering beyond tranche 1.
4. **Scope boundary**: cameras/cores (Boson: FPA + lens + electronics) are more than
   an FPA — presets model the *FPA/ROIC through readout* only, and optics values from
   a core datasheet are out of scope (they belong in optics element documents). Confirm.

---

## Appendix A — Roster Source Register (research session 2026-09-06)

Every document below was fetched and read during the research session; URLs are the
actual fetch URLs (Wayback URLs where the live page is delisted or bot-walled). This
register is the Phase 1 acquisition list for §3.5.

### A.1 Cooled IR / digital-pixel

**GeoSnap-18** — (1) datasheet, Teledyne Imaging Sensors, DOPSR #23-S-0343, Nov 2022:
`https://www.teledyne-si.com/en-us/Products-and-Services_/Documents/Infrared%20and%20Visible%20FPAs/GeoSnap_18.pdf`;
(2) product leaflet Apr 2025:
`https://www.teledynespaceimaging.com/en-us/Products_/Documents/GeoSnap/GeoSnap-18%20Product%20Leaflet%20Apr%202025.pdf`;
(3) Bowens et al., Proc. SPIE 13103 (2024), DOI 10.1117/12.3018499, arXiv:2405.20440
(measured LW device: 2.75 Me- well, 360 e- RMS, dark 3.3×10⁵ e-/s @ 45 K, QE 79.7 ± 8.3 % @ 10.6 µm);
(4) Leisenring et al., Astron. Nachr. 344 (2023), DOI 10.1002/asna.20230103, arXiv:2306.05470.
*Caveat: vendor 40/400 e- is ROIC-only noise; use paper values for LWIR presets.*

**GeoSnap-10** — leaflet Apr 2025:
`https://www.teledynespaceimaging.com/en-us/Products_/Documents/GeoSnap/GeoSnap-10%20Product%20Leaflet%20Apr%202025.pdf`.
*No public radiometrics; preset borrows GeoSnap-18 per-pixel values, `basis: derived`.*

**Senseeker** — Oxygen RD0092-D080: `https://www.senseeker.com/products/RD0092-D080.htm`;
Magnesium MIL RP0092: `https://www.senseeker.com/products/RP0092-D120.htm` (well 8→>140 Me-,
LSB to 160 e-/count, digital residue, 22-bit internal); Calcium RP0033-J200:
`https://www.senseeker.com/products/RP0033-J200.htm` (measured read noise @ 65 K:
~50 e- ITR / ~85 e- IWR high-gain; ~330/~700 e- low-gain). *Datasheets request-gated;
product-page spec tables are the public record. ROIC-only parts: detector-side values
absent by construction.*

**MIT LL DFPA** — Schultz et al., "Digital-Pixel Focal Plane Array Technology,"
Lincoln Laboratory Journal 20(2):36–51, 2014; free PDF via Wayback:
`http://web.archive.org/web/20141222135440id_/http://www.ll.mit.edu:80/publications/journal/pdf/vol20_no2/20_2_2_Schultz.pdf`
(read in full: 16-bit up/down counter, packet 1200–8000 e-/count, ~230 Me- effective
well, C_int ≈ 1 fF, √(LSB/12) quantization + published 4-term noise model, digital TDI,
T_op 68–85 K). Also: Kelly et al., Proc. SPIE 5902 (2005), DOI 10.1117/12.619284;
Tyrrell et al., IEEE TED 56(11), 2009, DOI 10.1109/TED.2009.2030719 (paywalled);
Goyal et al., Opt. Express 22:14392 (2014), open access.

**RVS MIRI Si:As IBC** — Rieke et al., PASP 127:665 (2015), DOI 10.1086/682257,
arXiv:1508.02362 (Table 1); Ressler et al., PASP 127:675 (2015), DOI 10.1086/682258,
arXiv:1508.02417; Gáspár et al., arXiv:2011.11908.

**RVS VIRGO-2K** — Sutherland et al., A&A 575, A25 (2015), DOI
10.1051/0004-6361/201424973, arXiv:1409.4780; ESO VIRCAM page:
`https://www.eso.org/sci/facilities/paranal/decommissioned/vircam/inst.html`.
*Pitch 20 µm is family-standard; paper-derived 19.8 µm — mark `derived`. Focal-plane
~72 K is a secondary-source inference.*

**SCD BlackBird 1920** — datasheet:
`https://www.scd-infrared.com/wp-content/uploads/2026/03/Blackbird-1920.pdf`; page:
`https://www.scd-infrared.com/products/blackbird-1920/`. *NEDT f/# unstated (std cold
shield f/3); flag condition.*

**Lynred Daphnis-HD MW** — page: `https://www.lynred.com/products/daphnis-hd-mw`;
datasheet (ungated):
`https://www.lynred.com/sites/default/files/2026-07/R3_Daphnis-HD-MW_2026.pdf`.
*Verify NEDT f/# in the PDF before locking the preset.*

### A.2 FLIR cores / microbolometers

**Neutrino LC** — product page (spec table), archived 2019-04-12:
`http://web.archive.org/web/20190412075002/https://www.flir.com/products/neutrino-swapc-series`
(the linked LC datasheet PDFs are 404 live and unarchived — the page table is the
citable record); Neutrino LC OGI datasheet, rev 2025-06-18:
`https://flir.netx.net/file/asset/59789/original/attachment`.
*Missing: FPA temperature in kelvin, read noise, QE curve; InSb attribution is via the
ISR derivative — `basis: assumed` on the bare core's material.*

**Neutrino SX12 ISR1200 / ISR family** — Ground ISR page, archived 2022-03-21:
`http://web.archive.org/web/20220321111039/https://www.flir.com/products/neutrino-ground-isr-series`;
Neutrino ISR Series datasheet, rev 2026-02-09:
`https://flir.netx.net/file/asset/43081/original/attachment`. *No public NEdT/well/
noise; DRI figures are NV-IPM modeled, not measured.*

**Boson+ 640** — datasheet rev 2026-04-30:
`https://flir.netx.net/file/asset/43192/original/attachment`; **engineering datasheet**
Doc 102-2013-45 Release 114, 2025-09-05, 150 pp, EAR99:
`https://flir.netx.net/file/asset/55485/original/attachment` (Table 13 + §11.1: NEDT
acceptance conditions — f/1.0 lensless, 30 °C background, high gain, averager off —
plus the (f/#)²/τ lens-scaling law; Table 1: τ_thermal 8 ms); product page archived
2025-05-18: `http://web.archive.org/web/20250518202958/https://www.flir.com/products/boson-plus/`.

**Tau 2 640** — datasheet rev 2025-02-05:
`https://flir.netx.net/file/asset/5631/original/attachment`; EOL notice 2024-02-16:
`https://flir.netx.net/file/asset/66666/original/attachment`; engineering spec
102-PS242-40 Rev 141 (2015), 46 pp:
`https://flir.netx.net/file/asset/12422/original/attachment` (radiometric conditions
NDA-only, Appendix A). *NEdT tiers unconditioned; datasheet and product page disagree
(30/40/50 vs 30/50/60 mK) — cite the dated PDF.*

**Tau 2+ 640** — datasheet rev 2023-10-24:
`https://flir.netx.net/file/asset/41543/original/attachment`.

**Lepton 3.5** — Lepton 3 & 3.5 datasheet (2018-05-17), via Wayback:
`http://web.archive.org/web/20190130073441/https://www.flir.com/globalassets/imported-assets/document/lepton-3-3.5-datasheet.pdf`;
Lepton-with-Radiometry engineering datasheet, Doc 500-0763-01-09 Rev 110, 74 pp
(Lepton 2.5, 80×60/17 µm — τ ~12 ms, 35 mK typical, spectral-response figure §13):
`http://web.archive.org/web/20190301062301/https://www.flir.com/globalassets/imported-assets/document/lepton-engineering-datasheet---with-radiometry.pdf`.
*τ and typical NETD are Lepton 2.5 measurements; family inference for the 3.5.*

**Lynred ATTO640** — page archived 2021-10-16:
`http://web.archive.org/web/20211016001513/https://lynred.com/products/atto640`;
datasheet RÉF 06/2020/01 via Wayback:
`http://web.archive.org/web/20211208002816/https://www.lynred.com/sites/default/files/2021-08/Atto640%20datasheet%20.pdf`.
*Spectral band in µm not printed in either document; material (a-Si) is inferred.*

*Dead ends this session: BAE Athena 1920 (bot-walled incl. Wayback), DRS Tenum (no
captures), Neutrino SX12 bare-core datasheet (never archived).*

### A.3 Scientific / visible

**H2RG** — Teledyne datasheet TSI-0855 (2022-02-25, DOPSR 22-S-1034):
`https://www.teledyne-si.com/en-us/Products-and-Services_/Documents/Infrared%20and%20Visible%20FPAs/TSI-0855%20H2RG%20Brochure-25Feb2022.pdf`;
STScI Roman RDox "WFI Detectors":
`https://roman-docs.stsci.edu/roman-instruments/the-wide-field-instrument/wfi-detectors`;
Le Graët et al., arXiv:2209.01831 (IPC/gain methodology).

**H4RG-10** — Mosby et al., JATIS 6(4), 046001 (2020), DOI 10.1117/1.JATIS.6.4.046001
(open access — *full-well lookup pending from this paper*); STScI RDox page above.

**CCD273-84** — Euclid Collaboration: Cropper et al., "Euclid. II. The VIS
Instrument," A&A 697, A2 (2025), DOI 10.1051/0004-6361/202450996, arXiv:2405.13492
(§2.3.1, §3.1.1, Table 2, §6.1.1–6.1.2).

**CCD42-40 (BI AIMO)** — e2v datasheet A1A-100012 v9 (2016-09), delisted; Wayback:
`http://web.archive.org/web/20211207011528/https://www.teledyne-e2v.com/shared/content/resources/File/documents/Imaging%202017/CCDs%20-%20Full-Frame%20Spectroscopic%20%26%20Scientific/CCD42-40/3.%20BI,%20AIMO/1208.pdf`.
*Confirm current availability/version with Teledyne e2v.*

**IMX455** — Alarcon et al., PASP 135, 055001 (2023), DOI 10.1088/1538-3873/acd04a,
arXiv:2302.03700 (Tables 1–3; QHY600M Pro). *Mode-dependent — preset pins Mode #1
gain 0 (3.5 e-, 50 ke-, 0.763 e-/ADU). Measured QE ~9 % below the manufacturer curve.*

**GSENSE400BSI** — Gpixel spec page via Wayback:
`http://web.archive.org/web/20230327002416/https://www.gpixel.com/products/area-scan-en/gsense/gsense400bsi/`
(full datasheet registration-gated). *Dark current quoted at 303 K — scale for cooled
operation.*

**IMX250** — LUCID Vision Labs Atlas 5.0 MP EMVA 1288 data:
`https://thinklucid.com/product/atlas-5-mp-imx250/`. *Camera-level; other integrators
differ slightly.*

**IMX990** — Sony spec page:
`https://www.sony-semicon.com/en/products/is/industry/swir/imx990-991.html`; LUCID
Atlas SWIR EMVA 1288: `https://thinklucid.com/product/atlas-swir-1-3mp-model-imx990/`.
*Sony publishes mV-domain only; electron-domain values are LUCID EMVA @ gain 0 dB,
15 °C — label the condition.*
